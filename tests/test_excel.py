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
from app.core.excel import ExcelConfig, read_excel, write_excel
from app.core.exceptions import BizError, BizErrorHandle
from app.core.router import CRUDRouter, SearchFieldConfig
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


@pytest.mark.parametrize("headers,rows", [
    (["item_name", "amount", "due_date", "secret"], [["private", 1, "2026-10-30", "hidden"]]),
    (["item_name", "itemName", "due_date"], [["private", 1, "2026-10-30"]]),
    (["item_name"], [["private"]]),
    (["item_name", "amount", "due_date"], [["private", "invalid", "2026-10-30"]]),
    (["item_name", "amount", "due_date"], []),
])
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


def excel_app(scope=None, dependencies=None):
    crud = CRUDRouter(
        prefix="/items", controller=CRUDBase(Dictionary), create_schema=DictionaryRow,
        list_schema=DictionarySearch, excel=ExcelConfig(tuple(DictionaryRow.model_fields)),
        search_fields=SearchFieldConfig(contains_fields=["label"]),
        excel_scope_filter=scope, action_dependencies=dependencies,
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
        assert response.json()["data"]["importedCount"] == 2
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
        ]:
            response = await client.request(method, path, **kwargs)
            assert response.json()["code"] == "2201"


def test_generator_includes_excel_and_scope_by_default():
    model = ModelInfo(name="Customer", cn_name="客户", fields=[FieldInfo("name", "CharField", "str"), FieldInfo("owner_id", "IntField", "int")])
    options = BackendFeatureOptions(button_auth_models={"Customer"}, data_scope={"Customer": DataScopeOption("owner_id", "owner_id")})
    backend = gen_api_manage("crm", [model], {"Customer": ["name"]}, backend_options=options)
    compile(backend, "manage.py", "exec")
    assert "excel=ExcelConfig(fields=('name', 'owner_id'))" in backend
    assert "excel_scope_filter=_customer_excel_scope" in backend
    assert '"import": [require_buttons("B_CRM_CUSTOMER_IMPORT")]' in backend
    assert '"export": [require_buttons("B_CRM_CUSTOMER_EXPORT")]' in backend
    init = gen_init_data("crm", [model], button_auth_models={"Customer"})
    assert "B_CRM_CUSTOMER_IMPORT" in init and "B_CRM_CUSTOMER_EXPORT" in init
    frontend = gen_view_index("crm", model, ["name"], button_auth=True)
    assert "<ExcelTransfer" in frontend
    assert "hasAuth('B_CRM_CUSTOMER_IMPORT')" in frontend
    assert "fetchExportCustomer(searchParams)" in frontend
    service = gen_service_ts("crm", [model])
    assert "/import-template" in service and "/export" in service and "new FormData()" in service
    assert "multipart/form-data" in service


def test_excel_is_opt_in_and_respects_route_and_field_boundaries():
    controller = CRUDBase(Dictionary)
    normal = CRUDRouter("/items", controller, create_schema=DictionaryRow, list_schema=DictionarySearch)
    assert not any("import" in route.path or "export" in route.path for route in normal.router.routes)
    restricted = CRUDRouter("/items", controller, create_schema=DictionaryRow, list_schema=DictionarySearch,
                            enable_routes={"get"}, excel=ExcelConfig(tuple(DictionaryRow.model_fields)))
    assert len(restricted.router.routes) == 1
    with pytest.raises(ValueError, match="excluded"):
        CRUDRouter("/items", controller, create_schema=DictionaryRow, excel=ExcelConfig(("value",)), exclude_fields=["value"])
    with pytest.raises(ValueError, match="create_schema"):
        CRUDRouter("/items", controller, create_schema=DictionaryRow, excel=ExcelConfig(("unknown",)))


@pytest.mark.parametrize("value", ["x" * 32768, "invalid\x00text"])
def test_excel_export_rejects_unrepresentable_cells_without_truncation(value):
    with pytest.raises(BizError, match="单元格"):
        write_excel(["name"], [[value]])
