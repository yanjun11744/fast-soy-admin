"""Bounded XLSX conversion. Only explicitly configured schema fields cross this boundary."""

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from io import BytesIO
from typing import Any, get_args, get_origin
from zipfile import ZipFile

import orjson
from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from pydantic import BaseModel, ValidationError

from app.core.code import Code
from app.core.exceptions import BizError

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 10000


@dataclass(frozen=True)
class ExcelConfig:
    """Opt in for simple CRUD resources. Fields are schema names, never arbitrary model fields."""

    fields: tuple[str, ...]


def write_excel(headers: list[str], records: list[list[Any]]) -> bytes:
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
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Data")
    for row in converted_rows:
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
    workbook.close()
    return output.getvalue()


def read_excel(content: bytes, schema: type[BaseModel], names: tuple[str, ...]) -> list[BaseModel]:
    """Validate the entire sheet before any writes. Errors never include cell contents."""
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
                raise BizError(Code.REQUEST_VALIDATION, "Excel 解压后超过 50MB")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            if len(workbook.worksheets) != 1:
                raise BizError(Code.REQUEST_VALIDATION, "Excel 必须只有一个工作表")
            sheet = workbook.worksheets[0]
            sheet.reset_dimensions()
            if len(names) > 200:
                raise BizError(Code.REQUEST_VALIDATION, "Excel 最多支持 200 个字段")
            rows = sheet.iter_rows(max_col=len(names) + 1)
            header = list(next(rows, ()))
            while header and header[-1].value is None:
                header.pop()
            aliases: dict[str, str] = {name: name for name in names}
            labels: dict[str, set[str]] = {}
            for name in names:
                info = schema.model_fields[name]
                for label in (info.alias, info.title):
                    if label:
                        labels.setdefault(label, set()).add(name)
            for label, matches in labels.items():
                if len(matches) == 1 and label not in aliases:
                    aliases[label] = next(iter(matches))
            columns = [aliases.get(str(cell.value)) for cell in header]
            if not columns or None in columns or len(set(columns)) != len(columns):
                raise BizError(Code.REQUEST_VALIDATION, "Excel 表头为空、重复或包含未知字段，请使用导入模板")
            missing = [name for name in names if schema.model_fields[name].is_required() and name not in columns]
            if missing:
                raise BizError(Code.REQUEST_VALIDATION, f"Excel 缺少必填列: {', '.join(missing)}")
            result: list[BaseModel] = []
            for row_number, row in enumerate(rows, start=2):
                if row_number > MAX_ROWS + 1:
                    raise BizError(Code.REQUEST_VALIDATION, f"Excel 最多允许 {MAX_ROWS} 行")
                if all(cell.value is None for cell in row):
                    continue
                if any(cell.data_type == "f" for cell in row):
                    raise BizError(Code.REQUEST_VALIDATION, f"第 {row_number} 行包含公式，请转换为值")
                if any(cell.value is not None for cell in row[len(columns) :]):
                    raise BizError(Code.REQUEST_VALIDATION, f"第 {row_number} 行存在无表头数据")
                data: dict[str, Any] = {}
                for name, cell in zip(columns, row, strict=False):
                    if name is None or cell.value is None:
                        continue
                    value = cell.value
                    annotation = schema.model_fields[name].annotation
                    types = (annotation, *get_args(annotation))
                    if isinstance(value, str) and any(t in (dict, list) or get_origin(t) in (dict, list) for t in types):
                        value = orjson.loads(value)
                    data[name] = value
                try:
                    result.append(schema.model_validate(data))
                except ValidationError as exc:
                    fields = ", ".join(".".join(map(str, error["loc"])) for error in exc.errors())
                    raise BizError(Code.REQUEST_VALIDATION, f"第 {row_number} 行校验失败，字段: {fields}") from exc
            if not result:
                raise BizError(Code.REQUEST_VALIDATION, "Excel 没有可导入的数据")
            return result
        finally:
            workbook.close()
    except BizError:
        raise
    except Exception as exc:
        raise BizError(Code.REQUEST_VALIDATION, "无法读取 Excel，请上传有效的 .xlsx 文件") from exc
