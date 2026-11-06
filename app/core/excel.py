"""Bounded XLSX conversion. Only explicitly configured schema fields cross this boundary."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from io import BytesIO
from typing import TYPE_CHECKING, Any, get_args, get_origin
from zipfile import ZipFile

import orjson
from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from pydantic import BaseModel, Field, ValidationError

from app.core.base_schema import SchemaBase
from app.core.code import Code
from app.core.exceptions import BizError

if TYPE_CHECKING:
    from app.core.router import CRUDRouter

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000
MAX_COLUMNS = 200
MAX_HEADER_ROWS = 100


@dataclass(frozen=True)
class ExcelColumn:
    """Excel-only display title and exact aliases; never changes JSON API aliases."""

    title: str | None = None
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExcelDetail:
    """A declared child resource; the lazy reference permits either declaration order."""

    sheet_name: str
    resource: Callable[[], CRUDRouter]
    parent_field: str


@dataclass(frozen=True)
class ExcelConfig:
    """Opt in for simple CRUD resources. Fields are schema names, never arbitrary model fields."""

    fields: tuple[str, ...]
    columns: Mapping[str, ExcelColumn] = field(default_factory=dict)
    # None keeps create-only imports; "id" enables Sqid round trips.
    update_key: str | None = None
    details: tuple[ExcelDetail, ...] = ()

    def resolve(self, schema: type[BaseModel]) -> tuple[list[str], dict[str, str]]:
        """Compile one unambiguous name registry shared by templates and imports."""
        if not self.fields or len(set(self.fields)) != len(self.fields) or not set(self.fields) <= schema.model_fields.keys():
            raise ValueError("Excel fields must be unique nonempty create_schema field names")
        if len(self.fields) > MAX_COLUMNS:
            raise ValueError("Excel supports at most 200 fields")
        if not self.columns.keys() <= set(self.fields):
            raise ValueError("Excel columns must belong to configured fields")
        if self.update_key not in (None, "id") and (self.update_key not in self.fields or not schema.model_fields[self.update_key].is_required()):
            raise ValueError("Excel update_key must be a required configured field")
        headers: list[str] = []
        aliases: dict[str, str] = {}
        for name in self.fields:
            info = schema.model_fields[name]
            column = self.columns.get(name, ExcelColumn())
            title = column.title if column.title is not None else info.title or name
            headers.append(title)
            if isinstance(column.aliases, str):
                raise ValueError(f"Excel aliases for {name} must be a tuple of strings")
            for label in (name, info.alias, info.title, title, *column.aliases):
                if label is None:
                    continue
                if not isinstance(label, str) or not label.strip():
                    raise ValueError(f"Excel labels for {name} must be nonempty strings")
                if label in aliases and aliases[label] != name:
                    raise ValueError(f"Excel alias {label!r} conflicts between {aliases[label]} and {name}")
                aliases[label] = name
        return headers, aliases


class ExcelImportOptions(SchemaBase):
    """Column positions map to whitelisted schema names; null explicitly ignores a column."""

    sheet: str | None = None
    header_row: int | None = Field(default=None, ge=1, le=MAX_HEADER_ROWS)
    columns: list[str | None] | None = Field(default=None, max_length=MAX_COLUMNS)


class ExcelPreviewField(SchemaBase):
    name: str
    title: str
    required: bool


class ExcelPreviewColumn(SchemaBase):
    index: int
    header: str
    field: str | None
    samples: list[str]


class ExcelPreview(SchemaBase):
    sheets: list[str]
    sheet: str | None = None
    header_row: int | None = None
    fields: list[ExcelPreviewField]
    columns: list[ExcelPreviewColumn] = Field(default_factory=list)
    row_count: int = 0
    errors: list[str] = Field(default_factory=list)


@dataclass
class ExcelImportResult:
    preview: ExcelPreview
    rows: list[tuple[int, BaseModel]] = field(default_factory=list)


def write_excel(headers: list[str], records: list[list[Any]]) -> bytes:
    return write_excel_sheets([("Data", headers, records)])


def write_excel_sheets(sheets: Sequence[tuple[str, list[str], list[list[Any]]]]) -> bytes:
    """Validate all cells before streaming any sheets, retaining the single-sheet text rules."""
    converted_sheets: list[tuple[str, list[list[Any]]]] = []
    names: set[str] = set()
    for title, headers, records in sheets:
        if not title or len(title) > 31 or any(char in title for char in r"\/*?:[]") or title.casefold() in names:
            raise ValueError("Excel sheet names must be unique, valid and at most 31 characters")
        names.add(title.casefold())
        if len(headers) > MAX_COLUMNS or len(records) > MAX_ROWS:
            raise BizError(Code.REQUEST_VALIDATION, f"每张工作表最多 {MAX_ROWS} 行、{MAX_COLUMNS} 列，请缩小导出范围")
        converted_rows: list[list[Any]] = []
        for row in [headers, *records]:
            converted = []
            for value in row:
                if isinstance(value, Enum):
                    value = value.value
                if isinstance(value, (dict, list)):
                    value = orjson.dumps(value).decode()
                elif isinstance(value, (datetime, date, time, Decimal)):
                    value = str(value)
                elif isinstance(value, int) and not isinstance(value, bool) and abs(value) >= 10**15:
                    value = str(value)
                if isinstance(value, str) and (len(value) > 32767 or ILLEGAL_CHARACTERS_RE.search(value)):
                    raise BizError(Code.REQUEST_VALIDATION, "数据超过 Excel 单元格长度限制或包含不支持的字符")
                converted.append(value)
            converted_rows.append(converted)
        converted_sheets.append((title, converted_rows))
    workbook = Workbook(write_only=True)
    try:
        for title, rows in converted_sheets:
            sheet = workbook.create_sheet(title)
            for row in rows:
                cells = []
                for value in row:
                    cell = WriteOnlyCell(sheet, value=value)
                    # Text must stay text, including formula-looking values and long IDs.
                    if isinstance(value, str):
                        cell.data_type = "s"
                    cells.append(cell)
                sheet.append(cells)
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()
    finally:
        workbook.close()


@contextmanager
def _open_excel(content: bytes) -> Iterator[Workbook]:
    """Close the workbook on every path and bound decompression before parsing XML."""
    workbook = None
    try:
        if len(content) > MAX_FILE_BYTES:
            raise BizError(Code.REQUEST_VALIDATION, "Excel 文件不能超过 5MB")
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                raise BizError(Code.REQUEST_VALIDATION, "Excel 解压后超过 50MB")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        yield workbook
    except BizError:
        raise
    except Exception as exc:
        raise BizError(Code.REQUEST_VALIDATION, "无法读取 Excel，请上传有效的 .xlsx 文件") from exc
    finally:
        if workbook is not None:
            workbook.close()


def _find_header(sheet: Any, aliases: dict[str, str], required: set[str]) -> int | None:
    candidates: list[int] = []
    best = (0, 0)
    for number, row in enumerate(sheet.iter_rows(max_row=MAX_HEADER_ROWS, max_col=MAX_COLUMNS + 1), start=1):
        if any(cell.data_type == "f" for cell in row):
            continue
        matches = {aliases[cell.value] for cell in row if isinstance(cell.value, str) and cell.value in aliases}
        score = (len(matches & required), len(matches))
        if matches and score > best:
            best, candidates = score, [number]
        elif matches and score == best:
            candidates.append(number)
    return candidates[0] if len(candidates) == 1 else None


def _convert_row(row: Any, columns: list[str | None], schema: type[BaseModel]) -> BaseModel:
    data: dict[str, Any] = {}
    for name, cell in zip(columns, row, strict=False):
        if name is None or cell.value is None:
            continue
        value = cell.value
        annotation = schema.model_fields[name].annotation
        types = (annotation, *get_args(annotation))
        if isinstance(value, str) and any(t in (dict, list) or get_origin(t) in (dict, list) for t in types):
            try:
                value = orjson.loads(value)
            except orjson.JSONDecodeError as exc:
                raise BizError(Code.REQUEST_VALIDATION, f"字段 {name} 不是有效的 JSON") from exc
        data[name] = value
    try:
        return schema.model_validate(data)
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
        raise BizError(Code.REQUEST_VALIDATION, f"校验失败，字段: {fields}") from exc


def parse_excel(
    content: bytes,
    schema: type[BaseModel],
    config: ExcelConfig,
    options: ExcelImportOptions | None = None,
) -> ExcelImportResult:
    """Inspect and validate without writes. Both preview and commit use this exact path."""
    titles, aliases = config.resolve(schema)
    options = options or ExcelImportOptions()
    fields = [ExcelPreviewField(name=name, title=title, required=schema.model_fields[name].is_required()) for name, title in zip(config.fields, titles, strict=True)]
    required = {item.name for item in fields if item.required}
    with _open_excel(content) as workbook:
        preview = ExcelPreview(sheets=workbook.sheetnames, fields=fields)
        result = ExcelImportResult(preview)
        if options.sheet is None and len(workbook.worksheets) != 1:
            preview.errors.append("Excel 包含多个工作表，请选择要导入的工作表")
            return result
        selected = options.sheet if options.sheet is not None else workbook.sheetnames[0]
        if selected not in workbook.sheetnames:
            raise BizError(Code.REQUEST_VALIDATION, "所选工作表不存在")
        preview.sheet = selected
        sheet = workbook[selected]
        sheet.reset_dimensions()
        header_row = options.header_row or _find_header(sheet, aliases, required)
        if header_row is None:
            preview.errors.append("无法唯一确定表头，请指定前 100 行中的表头行")
            return result
        preview.header_row = header_row
        rows = sheet.iter_rows(min_row=header_row)
        header = list(next(rows, ()))
        while header and header[-1].value is None:
            header.pop()
        if not header or len(header) > MAX_COLUMNS:
            preview.errors.append("Excel 表头不能为空，最多支持 200 列")
            return result
        if any(cell.data_type == "f" for cell in header):
            preview.errors.append("Excel 表头包含公式，请转换为值")
            return result
        columns = [aliases.get(cell.value) if isinstance(cell.value, str) else None for cell in header]
        if options.columns is not None:
            if len(options.columns) != len(header) or any(name is not None and name not in config.fields for name in options.columns):
                raise BizError(Code.REQUEST_VALIDATION, "字段映射必须与表头列数一致，且只能使用允许导入的字段")
            columns = options.columns
        mapped = [name for name in columns if name is not None]
        if len(set(mapped)) != len(mapped):
            preview.errors.append("多列对应同一个字段，请调整字段映射")
        if missing := required - set(mapped):
            preview.errors.append(f"Excel 缺少必填列: {', '.join(sorted(missing))}")
        if not mapped:
            preview.errors.append("请至少选择一个要导入的字段")
        preview.columns = [
            ExcelPreviewColumn(index=index, header=str(cell.value) if cell.value is not None else "", field=name, samples=[]) for index, (cell, name) in enumerate(zip(header, columns, strict=True))
        ]
        can_validate = not preview.errors
        for row_number, row in enumerate(rows, start=header_row + 1):
            if row_number > header_row + MAX_ROWS:
                raise BizError(Code.REQUEST_VALIDATION, f"Excel 最多允许 {MAX_ROWS} 行")
            if all(cell.value is None for cell in row):
                continue
            preview.row_count += 1
            if preview.row_count <= 3:
                for column, cell in zip(preview.columns, row, strict=False):
                    column.samples.append(str(cell.value)[:120] if cell.value is not None else "")
            # Reject formulas even in ignored columns; never evaluate workbook contents.
            error = None
            if any(cell.data_type == "f" for cell in row):
                error = "包含公式，请转换为值"
            elif any(cell.value is not None for cell in row[len(columns) :]):
                error = "存在无表头数据或超过 200 列"
            elif can_validate:
                try:
                    item = _convert_row(row, columns, schema)
                    result.rows.append((row_number, item))
                except BizError as exc:
                    error = exc.msg
            if error and len(preview.errors) < 20:
                preview.errors.append(f"第 {row_number} 行{error}")
        if not preview.row_count:
            preview.errors.append("Excel 没有可导入的数据")
        return result


def read_excel(
    content: bytes,
    schema: type[BaseModel],
    names: tuple[str, ...] | ExcelConfig,
) -> list[BaseModel]:
    """Backward-compatible conversion API; aliases always match literally."""
    config = names if isinstance(names, ExcelConfig) else ExcelConfig(names)
    result = parse_excel(content, schema, config)
    if result.preview.errors:
        raise BizError(Code.REQUEST_VALIDATION, result.preview.errors[0])
    return [item for _, item in result.rows]
