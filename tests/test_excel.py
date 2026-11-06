"""Excel boundary and HTTP tests use only the suite's in-memory database."""

from base64 import b64decode
from datetime import date
from decimal import Decimal
from io import BytesIO

import httpx
import pytest
from fastapi import Depends, FastAPI
from openpyxl import Workbook, load_workbook
from pydantic import Field
from tortoise.expressions import Q

from app.cli.generator import gen_api_manage, gen_init_data
from app.cli.options import BackendFeatureOptions, DataScopeOption
from app.cli.parser import FieldInfo, ModelInfo
from app.cli.web_generator import gen_service_ts, gen_view_index
from app.core.base_schema import PageQueryBase, SchemaBase
from app.core.crud import CRUDBase
from app.core.excel import ExcelColumn, ExcelConfig, ExcelImportOptions, parse_excel, read_excel, write_excel
from app.core.exceptions import BizError, BizErrorHandle
from app.core.router import CRUDRouter, SearchFieldConfig
from app.core.sqids import encode_id
from app.system.models.dictionary import Dictionary


class Row(SchemaBase):
    item_name: str = Field(title="名称")
    amount: Decimal
    due_date: date
    details: dict | None = None
    large_number: int = 9007199254740993


def test_excel_roundtrip_preserves_types_and_formula_text():
    content = write_excel(list(Row.model_fields), [["=SUM(1,2)", Decimal("1.2300"), date(2026, 10, 30), {"ok": True}, 9007199254740993]])
    result = read_excel(content, Row, tuple(Row.model_fields))
    assert result[0].item_name == "=SUM(1,2)"
    assert result[0].amount == Decimal("1.2300")
    assert result[0].due_date == date(2026, 10, 30)
    assert result[0].details == {"ok": True}
    assert result[0].large_number == 9007199254740993


@pytest.mark.parametrize("headers", [["名称", "amount", "dueDate"], ["itemName", "amount", "due_date"]])
def test_excel_accepts_titles_and_aliases(headers):
    content = write_excel(headers, [["example", "2.0", "2026-10-30"]])
    assert read_excel(content, Row, tuple(Row.model_fields))[0].item_name == "example"


@pytest.mark.parametrize(
    "headers,rows",
    [
        (["item_name", "itemName", "due_date"], [["private", 1, "2026-10-30"]]),
        (["item_name"], [["private"]]),
        (["item_name", "amount", "due_date"], [["private", "invalid", "2026-10-30"]]),
        (["item_name", "amount", "due_date"], []),
    ],
)
def test_excel_rejects_bad_headers_and_rows_without_leaking_values(headers, rows):
    with pytest.raises(BizError) as error:
        read_excel(write_excel(headers, rows), Row, tuple(Row.model_fields))
    assert "private" not in error.value.msg
    assert "hidden" not in error.value.msg


def test_excel_rejects_formulas_and_row_limit(monkeypatch):
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["item_name", "amount", "due_date"])
    sheet.append(["=1+1", 1, "2026-10-30"])
    stream = BytesIO()
    workbook.save(stream)
    with pytest.raises(BizError, match="公式"):
        read_excel(stream.getvalue(), Row, tuple(Row.model_fields))
    monkeypatch.setattr("app.core.excel.MAX_ROWS", 1)
    with pytest.raises(BizError, match="最多"):
        read_excel(write_excel(["item_name", "amount", "due_date"], [["a", 1, "2026-10-30"], ["b", 1, "2026-10-30"]]), Row, tuple(Row.model_fields))


class DictionaryRow(SchemaBase):
    dict_type: str
    label: str
    value: str


class DictionarySearch(PageQueryBase):
    label: str | None = None


def excel_app(scope=None, dependencies=None, config=None):
    crud = CRUDRouter(
        prefix="/items",
        controller=CRUDBase(Dictionary),
        create_schema=DictionaryRow,
        update_schema=DictionaryRow,
        list_schema=DictionarySearch,
        excel=config or ExcelConfig(tuple(DictionaryRow.model_fields)),
        search_fields=SearchFieldConfig(contains_fields=["label"]),
        excel_scope_filter=scope,
        action_dependencies=dependencies,
    )
    api = FastAPI()
    api.add_exception_handler(BizError, BizErrorHandle)
    api.include_router(crud.router)
    return api


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_http_import_export_and_rollback(app, monkeypatch):
    async def scope(_request):
        return Q(dict_type="excel-test")

    api = excel_app(scope)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        headers = list(DictionaryRow.model_fields)
        content = write_excel(headers, [["excel-test", "visible", "one"], ["excel-other", "visible", "two"]])
        response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
        assert response.json()["data"] == {"importedCount": 2, "createdCount": 2, "updatedCount": 0}
        response = await client.post("/items/export", json={"label": "visible", "size": 1, "current": 2})
        data = response.json()["data"]
        exported = read_excel(b64decode(data["content"]), DictionaryRow, tuple(headers))
        assert len(exported) == 1
        assert exported[0].dict_type == "excel-test"
        template = (await client.get("/items/import-template")).json()
        workbook = load_workbook(BytesIO(b64decode(template["data"]["content"])))
        assert list(workbook.active.values) == [tuple(headers)]
        workbook.close()
        invalid = write_excel(headers, [["excel-test", "rollback", "three"], ["excel-test", "duplicate", "one"]])
        response = await client.post("/items/import", files={"file": ("items.xlsx", invalid)})
        assert response.json()["code"] != "0000"
        assert not await Dictionary.filter(dict_type="excel-test", value="three").exists()
        bad = await client.post("/items/import", files={"file": ("items.xls", content)})
        assert bad.json()["code"] != "0000"
        filtered = await client.post("/items/export", json={"label": "missing"})
        workbook = load_workbook(BytesIO(b64decode(filtered.json()["data"]["content"])))
        assert workbook.active.max_row == 1
        workbook.close()
        with monkeypatch.context() as limits:
            limits.setattr("app.core.router.MAX_ROWS", 1)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=excel_app()), base_url="http://test") as limited:
                response = await limited.post("/items/export", json={})
                assert response.json()["code"] != "0000"
            limits.setattr("app.core.router.MAX_FILE_BYTES", 10)
            response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
            assert response.json()["code"] != "0000"
    await Dictionary.filter(dict_type__in=["excel-test", "excel-other"]).delete()


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_inherits_action_permissions():
    async def deny():
        raise BizError("2201", "denied")

    api = excel_app(dependencies={"create": [Depends(deny)], "list": [Depends(deny)]})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        for path, method, kwargs in [
            ("/items/import-template", "get", {}),
            ("/items/export", "post", {"json": {}}),
            ("/items/import", "post", {"files": {"file": ("a.xlsx", b"invalid")}}),
            ("/items/import-preview", "post", {"files": {"file": ("a.xlsx", b"invalid")}}),
        ]:
            response = await client.request(method, path, **kwargs)
            assert response.json()["code"] == "2201"


def test_generator_includes_excel_and_scope_by_default():
    model = ModelInfo(name="Customer", cn_name="客户", fields=[FieldInfo("name", "CharField", "str"), FieldInfo("owner_id", "IntField", "int")])
    options = BackendFeatureOptions(button_auth_models={"Customer"}, data_scope={"Customer": DataScopeOption("owner_id", "owner_id")})
    backend = gen_api_manage("crm", [model], {"Customer": ["name"]}, backend_options=options)
    compile(backend, "manage.py", "exec")
    assert "excel=ExcelConfig(fields=('name', 'owner_id'), update_key='id')" in backend
    assert "excel_scope_filter=_customer_excel_scope" in backend
    assert '"import": [require_buttons("B_CRM_CUSTOMER_IMPORT")]' in backend
    assert '"export": [require_buttons("B_CRM_CUSTOMER_EXPORT")]' in backend
    init = gen_init_data("crm", [model], button_auth_models={"Customer"})
    assert "B_CRM_CUSTOMER_IMPORT" in init and "B_CRM_CUSTOMER_EXPORT" in init
    frontend = gen_view_index("crm", model, ["name"], button_auth=True)
    assert "<ExcelTransfer" in frontend
    assert "hasAuth('B_CRM_CUSTOMER_IMPORT')" in frontend
    assert "fetchExportCustomer(searchParams)" in frontend
    assert ':selected-ids="checkedRowKeys"' in frontend
    assert ':export-selected-api="ids => fetchExportCustomer({ ...searchParams, ids })"' in frontend
    service = gen_service_ts("crm", [model])
    assert "/import-template" in service and "/export" in service and "createExcelFormData" in service
    assert "multipart/form-data" in service
    assert "createExcelFormData(file, options)" in service
    assert "fetchPreviewImportCustomer" in service and "/import-preview" in service
    assert "request<ExcelImportResult>" in service
    assert "CustomerSearchParams & { ids?: string[] }" in service
    assert ':preview-api="fetchPreviewImportCustomer"' in frontend


@pytest.mark.parametrize(
    "fields,excluded,expected",
    [
        ([FieldInfo("code", "CharField", "str", unique=True)], [], "update_key='code'"),
        ([FieldInfo("code", "CharField", "str", unique=True), FieldInfo("email", "CharField", "str", unique=True)], [], "update_key='id'"),
        ([FieldInfo("code", "CharField", "str", unique=True, required=False)], [], "update_key='id'"),
        ([FieldInfo("code", "CharField", "str", unique=True), FieldInfo("name", "CharField", "str")], ["code"], "update_key='id'"),
    ],
)
def test_generator_selects_only_unambiguous_required_unique_keys(fields: list[FieldInfo], excluded: list[str], expected: str) -> None:
    model = ModelInfo(name="Customer", cn_name="客户", fields=fields)
    options = BackendFeatureOptions(exclude_fields={"Customer": excluded})
    backend = gen_api_manage("crm", [model], {}, backend_options=options)
    compile(backend, "manage.py", "exec")
    assert expected in backend


def test_generator_keeps_create_only_excel_when_update_is_disabled_or_id_is_excluded() -> None:
    model = ModelInfo(name="Customer", cn_name="客户", fields=[FieldInfo("name", "CharField", "str")])
    for options in [BackendFeatureOptions(enable_routes={"Customer": {"create", "list"}}), BackendFeatureOptions(exclude_fields={"Customer": ["id"]})]:
        backend = gen_api_manage("crm", [model], {}, backend_options=options)
        assert "update_key=" not in backend


@pytest.mark.asyncio(loop_scope="session")
async def test_selected_export_intersects_ids_search_and_permissions(app, monkeypatch):
    async def scope(_request):
        return Q(dict_type="selected-export")

    async def policy(*args, **kwargs):
        return Q(value__not="policy-hidden")

    monkeypatch.setattr("app.core.policy.apply_data_policy", policy)
    rows = [
        await Dictionary.create(dict_type="selected-export", label="match", value="chosen"),
        await Dictionary.create(dict_type="selected-export", label="match", value="unselected"),
        await Dictionary.create(dict_type="selected-export", label="other", value="filtered"),
        await Dictionary.create(dict_type="selected-export-other", label="match", value="hidden"),
        await Dictionary.create(dict_type="selected-export", label="match", value="policy-hidden"),
    ]
    # Exercise both independent permission filters in the actual export endpoint.
    crud = CRUDRouter(
        prefix="/items",
        controller=CRUDBase(Dictionary),
        create_schema=DictionaryRow,
        list_schema=DictionarySearch,
        excel=ExcelConfig(tuple(DictionaryRow.model_fields)),
        search_fields=SearchFieldConfig(contains_fields=["label"]),
        excel_scope_filter=scope,
        data_policy="test-policy",
    )
    api = FastAPI()
    api.include_router(crud.router)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
            ids = [encode_id(row.id) for row in rows if row.value != "unselected"]
            response = await client.post("/items/export", json={"ids": ids + ids[:1], "label": "match", "size": 1, "current": 2})
            exported = read_excel(b64decode(response.json()["data"]["content"]), DictionaryRow, tuple(DictionaryRow.model_fields))
            assert [row.value for row in exported] == ["chosen"]
            empty = await client.post("/items/export", json={"ids": [encode_id(rows[3].id)]})
            workbook = load_workbook(BytesIO(b64decode(empty.json()["data"]["content"])))
            assert workbook.active.max_row == 1
            workbook.close()
    finally:
        await Dictionary.filter(id__in=[row.id for row in rows]).delete()


@pytest.mark.asyncio(loop_scope="session")
async def test_selected_export_rejects_empty_invalid_and_excessive_ids(monkeypatch):
    monkeypatch.setattr("app.core.router.MAX_ROWS", 2)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=excel_app()), base_url="http://test") as client:
        for ids in ([], ["!invalid!"], [encode_id(i) for i in range(1, 4)]):
            response = await client.post("/items/export", json={"ids": ids})
            assert response.status_code == 422
    schema = excel_app().openapi()
    export_body = schema["paths"]["/items/export"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    assert "Export" in export_body["$ref"]


def test_excel_is_opt_in_and_respects_route_and_field_boundaries():
    controller = CRUDBase(Dictionary)
    normal = CRUDRouter("/items", controller, create_schema=DictionaryRow, list_schema=DictionarySearch)
    assert not any("import" in route.path or "export" in route.path for route in normal.router.routes)
    restricted = CRUDRouter("/items", controller, create_schema=DictionaryRow, list_schema=DictionarySearch, enable_routes={"get"}, excel=ExcelConfig(tuple(DictionaryRow.model_fields)))
    assert len(restricted.router.routes) == 1
    with pytest.raises(ValueError, match="excluded"):
        CRUDRouter("/items", controller, create_schema=DictionaryRow, excel=ExcelConfig(("value",)), exclude_fields=["value"])
    with pytest.raises(ValueError, match="create_schema"):
        CRUDRouter("/items", controller, create_schema=DictionaryRow, excel=ExcelConfig(("unknown",)))


@pytest.mark.parametrize("value", ["x" * 32768, "invalid\x00text"])
def test_excel_export_rejects_unrepresentable_cells_without_truncation(value):
    with pytest.raises(BizError, match="单元格"):
        write_excel(["name"], [[value]])


def row_config() -> ExcelConfig:
    return ExcelConfig(
        fields=("item_name", "amount", "due_date"),
        columns={
            "item_name": ExcelColumn(aliases=("商品名称", "Item Name")),
            "amount": ExcelColumn(title="金额", aliases=("Amount",)),
            "due_date": ExcelColumn(title="到期日期"),
        },
    )


def test_excel_columns_share_titles_and_exact_aliases():
    config = row_config()
    titles, _ = config.resolve(Row)
    assert titles == ["名称", "金额", "到期日期"]
    for headers in (titles, ["商品名称", "Amount", "dueDate"], list(config.fields)):
        result = read_excel(write_excel(headers, [["example", 1, "2026-10-30"]]), Row, config)
        assert result[0].item_name == "example"
    assert Row.model_fields["amount"].alias == "amount"


@pytest.mark.parametrize("label", [" 名称", "名称 ", "名称\n", "item name", "ITEM NAME", "Ｉｔｅｍ Ｎａｍｅ", "商品名"])
def test_excel_never_normalizes_or_guesses_aliases(label):
    content = write_excel([label, "金额", "到期日期"], [["private", 1, "2026-10-30"]])
    with pytest.raises(BizError, match="缺少必填列"):
        read_excel(content, Row, row_config())


@pytest.mark.parametrize(
    "columns",
    [
        {"item_name": ExcelColumn(aliases=("amount",))},
        {"item_name": ExcelColumn(aliases=("金额",)), "amount": ExcelColumn(title="金额")},
        {"item_name": ExcelColumn(title="相同"), "amount": ExcelColumn(title="相同")},
        {"unknown": ExcelColumn(title="未知")},
        {"item_name": ExcelColumn(aliases=("",))},
        {"item_name": ExcelColumn(aliases="商品名称")},
    ],
)
def test_excel_rejects_ambiguous_or_invalid_column_configuration(columns):
    with pytest.raises(ValueError):
        ExcelConfig(("item_name", "amount", "due_date"), columns).resolve(Row)


def test_excel_detects_reordered_headers_after_preamble_and_keeps_physical_rows():
    content = write_excel(["报表标题"], [[], ["到期日期", "名称", "金额"], [], ["2026-10-30", "example", 1]])
    result = parse_excel(content, Row, row_config())
    assert not result.preview.errors
    assert result.preview.header_row == 3
    assert result.preview.row_count == 1
    assert result.rows[0][0] == 5
    assert result.rows[0][1].item_name == "example"


def test_excel_preview_ignores_unknown_columns_by_default_and_validates_mappings():
    content = write_excel(["名称", "金额", "到期日期", "其他"], [["example", 1, "2026-10-30", "private"]])
    preview = parse_excel(content, Row, row_config()).preview
    assert not preview.errors and preview.columns[-1].field is None
    assert read_excel(content, Row, row_config())[0].item_name == "example"
    options = ExcelImportOptions(columns=["item_name", "amount", "due_date", None])
    result = parse_excel(content, Row, row_config(), options)
    assert not result.preview.errors and len(result.rows) == 1
    for columns in (["item_name"], ["item_name", "amount", "due_date", "details"]):
        with pytest.raises(BizError, match="允许导入的字段"):
            parse_excel(content, Row, row_config(), ExcelImportOptions(columns=columns))
    duplicate = parse_excel(content, Row, row_config(), ExcelImportOptions(columns=["item_name", "amount", "due_date", "item_name"]))
    assert any("同一个字段" in error for error in duplicate.preview.errors)


def test_excel_selects_sheet_and_requires_a_unique_header_candidate():
    workbook = Workbook()
    for sheet in (workbook.active, workbook.create_sheet("Other")):
        sheet.append(["名称", "金额", "到期日期"])
        sheet.append(["example", 1, "2026-10-30"])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    assert parse_excel(stream.getvalue(), Row, row_config()).preview.sheet is None
    selected = parse_excel(stream.getvalue(), Row, row_config(), ExcelImportOptions(sheet="Other"))
    assert not selected.preview.errors and selected.preview.sheet == "Other"
    with pytest.raises(BizError, match="不存在"):
        parse_excel(stream.getvalue(), Row, row_config(), ExcelImportOptions(sheet="Missing"))
    repeated = write_excel(["名称", "金额", "到期日期"], [["名称", "金额", "到期日期"], ["example", 1, "2026-10-30"]])
    assert parse_excel(repeated, Row, row_config()).preview.header_row is None
    assert not parse_excel(repeated, Row, row_config(), ExcelImportOptions(header_row=2)).preview.errors


def test_excel_checks_json_and_ignored_formulas_without_leaking_values():
    config = ExcelConfig(("item_name", "amount", "due_date", "details"))
    invalid = write_excel(list(config.fields), [["private", 1, "2026-10-30", "secret-not-json"]])
    preview = parse_excel(invalid, Row, config).preview
    assert "JSON" in preview.errors[0] and "secret" not in preview.errors[0]
    workbook = Workbook()
    workbook.active.append(["名称", "金额", "到期日期", "其他"])
    workbook.active.append(["example", 1, "2026-10-30", "=1+1"])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    result = parse_excel(stream.getvalue(), Row, row_config(), ExcelImportOptions(columns=["item_name", "amount", "due_date", None]))
    assert "公式" in result.preview.errors[0]


def test_excel_does_not_silently_truncate_distant_columns():
    workbook = Workbook()
    workbook.active.append(["名称", "金额", "到期日期"])
    workbook.active.append(["example", 1, "2026-10-30"])
    workbook.active.cell(2, 250, "private")
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    assert "无表头数据" in parse_excel(stream.getvalue(), Row, row_config()).preview.errors[0]


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_http_preview_is_readonly_and_commit_rechecks_options(app):
    config = ExcelConfig(
        tuple(DictionaryRow.model_fields),
        {
            "dict_type": ExcelColumn(title="字典类型", aliases=("Type",)),
            "label": ExcelColumn(title="标签"),
            "value": ExcelColumn(title="值"),
        },
    )
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=excel_app(config=config)), base_url="http://test") as client:
        template = (await client.get("/items/import-template")).json()["data"]
        workbook = load_workbook(BytesIO(b64decode(template["content"])))
        assert list(workbook.active.values) == [("字典类型", "标签", "值")]
        workbook.close()
        content = write_excel(["Type", "标签", "值", "附加列"], [["preview-test", "label", "value", "private"]])
        files = {"file": ("items.xlsx", content)}
        preview = (await client.post("/items/import-preview", files=files)).json()["data"]
        assert preview["headerRow"] == 1 and preview["rowCount"] == 1 and not preview["errors"]
        assert not await Dictionary.filter(dict_type="preview-test").exists()
        options = '{"columns":["dict_type","label","value",null]}'
        checked = (await client.post("/items/import-preview", files=files, data={"options": options})).json()["data"]
        assert not checked["errors"]
        assert not await Dictionary.filter(dict_type="preview-test").exists()
        for invalid in ('{"columns":["dict_type","label","value","id"]}', '{"headerRow":0}', "not-json"):
            response = await client.post("/items/import", files=files, data={"options": invalid})
            assert response.json()["code"] != "0000"
        imported = (await client.post("/items/import", files=files)).json()
        assert imported["data"]["importedCount"] == 1
    await Dictionary.filter(dict_type="preview-test").delete()


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_template_and_preview_inherit_explicit_import_permission():
    async def deny():
        raise BizError("2201", "denied")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=excel_app(dependencies={"import": [Depends(deny)]})), base_url="http://test") as client:
        assert (await client.get("/items/import-template")).json()["code"] == "2201"
        response = await client.post("/items/import-preview", files={"file": ("items.xlsx", b"invalid")})
        assert response.json()["code"] == "2201"
