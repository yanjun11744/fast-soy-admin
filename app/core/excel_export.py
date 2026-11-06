"""Read bounded child sheets through each declared resource's export field and scope rules."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

from fastapi import Request
from tortoise.fields.relational import ForeignKeyFieldInstance, OneToOneFieldInstance
from tortoise.models import Model

from app.core.code import Code
from app.core.excel import MAX_COLUMNS, MAX_ROWS, ExcelConfig
from app.core.exceptions import BizError
from app.core.policy import apply_data_policy

if TYPE_CHECKING:
    from pydantic import BaseModel

    from app.core.router import CRUDRouter


async def export_record(resource: CRUDRouter, schema: type[BaseModel], config: ExcelConfig, obj: Model) -> list[Any]:
    if resource.record_transform:
        record = await resource.record_transform(obj)
        return [record.get(schema.model_fields[name].alias or name) for name in config.fields]
    values = {name: getattr(obj, name) for name in config.fields}
    record = schema.model_construct(**values).model_dump(mode="json", include=set(config.fields))
    return [record.get(name) for name in config.fields]


async def detail_sheets(
    parent: CRUDRouter,
    config: ExcelConfig,
    headers: list[str],
    objects: list[Any],
    records: list[list[Any]],
    parent_fields: list[str] | None,
    request: Request,
) -> list[tuple[str, list[str], list[list[Any]]]]:
    selected = list(config.fields) if parent_fields is None else parent_fields
    if len(set(selected)) != len(selected) or not set(selected) <= set(config.fields):
        raise BizError(Code.REQUEST_VALIDATION, "父表导出字段包含未允许或重复的字段")
    indexes = [config.fields.index(name) for name in selected]
    parent_headers = [f"父表：{headers[index]}" for index in indexes]
    parent_records = {obj.pk: [record[index] for index in indexes] for obj, record in zip(objects, records, strict=True)}
    sheets = []
    names = {"data"}
    for detail in config.details:
        resource = detail.resource()
        child_config = resource.excel
        schema = resource.create_schema
        model = resource.controller.model
        relation = model._meta.fields_map.get(detail.parent_field.removesuffix("_id"))
        if not detail.parent_field.endswith("_id") or not isinstance(relation, (ForeignKeyFieldInstance, OneToOneFieldInstance)) or relation.related_model is not parent.controller.model:
            raise ValueError("Excel detail must reference its parent through an explicit FK/one-to-one ID field")
        if child_config is None or schema is None or "list" not in resource.enable_routes:
            raise ValueError("Excel detail resource requires an enabled list and Excel configuration")
        if set(child_config.fields) & set(resource.exclude_fields):
            raise ValueError("Excel detail fields cannot include excluded fields")
        title = detail.sheet_name
        if title.casefold() in names:
            raise ValueError("Excel detail sheet names must be unique")
        names.add(title.casefold())
        child_headers, _ = child_config.resolve(schema)
        if len(parent_headers) + len(child_headers) > MAX_COLUMNS:
            raise BizError(Code.REQUEST_VALIDATION, f"子表导出最多 {MAX_COLUMNS} 列，请减少父表字段")
        query = model.filter(**{f"{detail.parent_field}__in": list(parent_records)})
        if resource.data_policy:
            module = resource.route_key_prefix.split(".", 1)[0] if resource.route_key_prefix else None
            query = query.filter(await apply_data_policy(resource.data_policy, module=module))
        if resource.excel_scope_filter:
            query = query.filter(await resource.excel_scope_filter(request))
        children = await query.order_by(*resource.list_order).limit(MAX_ROWS + 1)
        if len(children) > MAX_ROWS:
            raise BizError(Code.REQUEST_VALIDATION, f"子表 {title} 导出最多 {MAX_ROWS} 行，请缩小筛选范围")
        grouped: dict[Any, list[list[Any]]] = defaultdict(list)
        for child in children:
            parent_id = getattr(child, detail.parent_field)
            grouped[parent_id].append([*parent_records[parent_id], *await export_record(resource, schema, child_config, child)])
        rows = [row for obj in objects for row in grouped[obj.pk]]
        sheets.append((title, [*parent_headers, *child_headers], rows))
    return sheets
