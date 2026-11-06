"""Excel update acceptance tests use an isolated in-memory database."""

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import Field
from tortoise import fields
from tortoise.context import tortoise_test_context
from tortoise.expressions import Q

from app.core.base_model import AuditMixin, BaseModel
from app.core.base_schema import PageQueryBase, SchemaBase
from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER
from app.core.excel import ExcelConfig, write_excel
from app.core.exceptions import BizError, BizErrorHandle
from app.core.router import CRUDRouter
from app.core.sqids import encode_id
from app.core.types import SqidId


class ImportItem(BaseModel, AuditMixin):
    id = fields.IntField(primary_key=True)
    code = fields.CharField(max_length=50, unique=True)
    name = fields.CharField(max_length=50)
    quantity = fields.IntField(default=1)
    remark = fields.CharField(max_length=100, null=True)
    owner_id = fields.IntField(null=True)


class ItemRow(SchemaBase):
    code: str
    name: str
    quantity: int = 1
    remark: str | None = None
    owner_id: SqidId | None = None


@pytest.fixture
async def excel_db() -> AsyncIterator[None]:
    async with tortoise_test_context(modules=[__name__], app_label="app_system", connection_label="conn_system", use_tz=False):
        yield


def api_for(key: str, scope=None, update_schema=ItemRow, policy=None) -> FastAPI:
    crud = CRUDRouter(
        "/items",
        CRUDBase(ImportItem),
        create_schema=ItemRow,
        update_schema=update_schema,
        list_schema=PageQueryBase,
        excel=ExcelConfig(tuple(ItemRow.model_fields), update_key=key),
        excel_scope_filter=scope,
        data_policy=policy,
    )
    api = FastAPI()
    api.add_exception_handler(BizError, BizErrorHandle)
    api.include_router(crud.router)
    return api


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("key", ["id", "code"])
async def test_mixed_import_counts_preserves_blanks_zero_identity_and_audit(excel_db, key: str) -> None:
    original = await ImportItem.create(code="existing", name="old", quantity=5, remark="keep", owner_id=1234, created_by="creator")
    token = CTX_USER.set(SimpleNamespace(user_name="importer"))
    headers = ["code", "name", "quantity", "remark", "ownerId"]
    rows = [["existing", "updated", 0, None, encode_id(1234)], ["new", "created", 2, "new", encode_id(5678)]]
    if key == "id":
        headers.insert(0, "ID")
        rows = [[encode_id(original.id), *rows[0]], [None, *rows[1]]]
    content = write_excel(headers, rows)
    try:
        async with AsyncClient(transport=ASGITransport(app=api_for(key)), base_url="http://test") as client:
            preview = await client.post("/items/import-preview", files={"file": ("items.xlsx", content)})
            assert preview.json()["data"]["errors"] == []
            await original.refresh_from_db()
            assert original.name == "old"
            response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
            assert response.json()["data"] == {"importedCount": 2, "createdCount": 1, "updatedCount": 1}
            await original.refresh_from_db()
            assert original.name == "updated" and original.quantity == 0 and original.remark == "keep"
            assert original.created_by == "creator" and original.updated_by == "importer"
            assert original.created_at is not None
            assert (await ImportItem.get(code="new")).created_by == "importer"
            assert (await ImportItem.get(code="new")).owner_id == 5678
            # Re-import exported records: all rows update, and IDs stay stable.
            from base64 import b64decode

            exported = (await client.post("/items/export", json={})).json()["data"]
            response = await client.post("/items/import", files={"file": ("items.xlsx", b64decode(exported["content"]))})
            assert response.json()["data"] == {"importedCount": 2, "createdCount": 0, "updatedCount": 2}
            assert await ImportItem.all().count() == 2
            await original.refresh_from_db()
            assert original.owner_id == 1234
    finally:
        CTX_USER.reset(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_id_import_rolls_back_updates_and_new_rows_on_later_conflict(excel_db) -> None:
    original = await ImportItem.create(code="existing", name="old")
    content = write_excel(["ID", "code", "name"], [[encode_id(original.id), "existing", "updated"], [None, "new", "new"], [None, "new", "duplicate"]])
    async with AsyncClient(transport=ASGITransport(app=api_for("id")), base_url="http://test") as client:
        response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
        assert "第 4 行" in response.json()["msg"]
    await original.refresh_from_db()
    assert original.name == "old"
    assert await ImportItem.all().count() == 1


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("key", ["id", "code"])
@pytest.mark.parametrize("policy", [False, True])
async def test_import_cannot_update_outside_scope(excel_db, key: str, policy: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    original = await ImportItem.create(code="hidden", name="old")

    async def scope(_request):
        return Q(code__in=["visible", "hidden"]) if policy else Q(code="visible")

    async def apply_policy(*args, **kwargs):
        return Q(code="visible")

    monkeypatch.setattr("app.core.policy.apply_data_policy", apply_policy)

    headers = ["code", "name"]
    rows = [["hidden", "updated"]]
    if key == "id":
        headers.insert(0, "ID")
        rows[0].insert(0, encode_id(original.id))
    async with AsyncClient(transport=ASGITransport(app=api_for(key, scope, policy="test" if policy else None)), base_url="http://test") as client:
        response = await client.post("/items/import", files={"file": ("items.xlsx", write_excel(headers, rows))})
        assert "不允许更新" in response.json()["msg"]
    await original.refresh_from_db()
    assert original.name == "old"


@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_or_missing_id_never_creates_a_record(excel_db) -> None:
    async with AsyncClient(transport=ASGITransport(app=api_for("id")), base_url="http://test") as client:
        for record_id in ["!invalid!", encode_id(9999)]:
            content = write_excel(["ID", "code", "name"], [[record_id, "new", "new"]])
            response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
            assert response.json()["code"] != "0000"
        assert await ImportItem.all().count() == 0


def test_update_config_requires_a_unique_key_and_update_route() -> None:
    with pytest.raises(ValueError, match="unique non-null"):
        api_for("name")
    with pytest.raises(ValueError, match="enabled update route"):
        api_for("code", update_schema=None)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_schema_validation_rolls_back_without_leaking_cell_values(excel_db) -> None:
    class UpdateRow(ItemRow):
        quantity: int = Field(default=1, ge=0)

    original = await ImportItem.create(code="existing", name="old")
    content = write_excel(["code", "name", "quantity"], [["existing", "private", -1]])
    async with AsyncClient(transport=ASGITransport(app=api_for("code", update_schema=UpdateRow)), base_url="http://test") as client:
        response = await client.post("/items/import", files={"file": ("items.xlsx", content)})
        assert "更新字段校验失败" in response.json()["msg"]
        assert "private" not in response.json()["msg"]
    await original.refresh_from_db()
    assert original.name == "old"
