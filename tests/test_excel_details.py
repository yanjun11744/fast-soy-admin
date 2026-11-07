"""Parent/child exports use isolated models and never access existing business tables."""

from base64 import b64decode
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
from pydantic import Field
from tortoise import fields
from tortoise.context import tortoise_test_context
from tortoise.expressions import Q

from app.core.exceptions import BizErrorHandle
from app.core.soft_delete import SoftDeleteManager, SoftDeleteMixin
from app.utils import BaseModel, BizError, CRUDBase, CRUDRouter, ExcelConfig, ExcelDetail, PageQueryBase, SchemaBase, SearchFieldConfig, SqidId, encode_id, make_optional


class ExportParent(BaseModel):
    number = fields.CharField(max_length=40, unique=True)
    name = fields.CharField(max_length=40)
    secret = fields.CharField(max_length=40, default="hidden")


class ExportChild(BaseModel, SoftDeleteMixin):
    parent_id: int | None
    parent: fields.ForeignKeyNullableRelation[ExportParent] = fields.ForeignKeyField("app_system.ExportParent", null=True)
    label = fields.CharField(max_length=40)
    amount = fields.DecimalField(max_digits=20, decimal_places=6)
    owner_id = fields.IntField(default=1)
    secret = fields.CharField(max_length=40, default="hidden-child")

    class Meta:
        manager = SoftDeleteManager()


class ExportNote(BaseModel):
    parent_id: int
    parent: fields.OneToOneRelation[ExportParent] = fields.OneToOneField("app_system.ExportParent")
    note = fields.CharField(max_length=40)


class ParentCreate(SchemaBase):
    number: str = Field(title="单号")
    name: str = Field(title="名称")
    secret: str = "hidden"


class ParentSearch(PageQueryBase):
    name: str | None = None


class ChildCreate(SchemaBase):
    parent_id: SqidId | None
    label: str = Field(title="项目")
    amount: Decimal = Field(title="金额")


class NoteCreate(SchemaBase):
    parent_id: SqidId
    note: str = Field(title="备注")


@pytest.fixture
async def detail_export() -> AsyncIterator[tuple[FastAPI, CRUDRouter, CRUDRouter, list[ExportParent]]]:
    async with tortoise_test_context(modules=[__name__], app_label="app_system", connection_label="details", use_tz=False):
        async def parent_scope(_request: object) -> Q:
            return Q(number__startswith="VISIBLE")

        async def child_scope(_request: object) -> Q:
            return Q(owner_id=1)

        # Parent intentionally appears before children, matching any models.py declaration order.
        parent = CRUDRouter(
            "/parents", CRUDBase(ExportParent), create_schema=ParentCreate,
            update_schema=make_optional(ParentCreate, "ParentUpdate"), list_schema=ParentSearch,
            excel=ExcelConfig(("number", "name"), details=(
                ExcelDetail("明细", lambda: child, "parent_id"), ExcelDetail("备注", lambda: note, "parent_id"),
            )),
            exclude_fields=["secret"], excel_scope_filter=parent_scope,
            search_fields=SearchFieldConfig(contains_fields=["name"]),
        )
        child = CRUDRouter(
            "/children", CRUDBase(ExportChild), create_schema=ChildCreate, list_schema=PageQueryBase,
            excel=ExcelConfig(("label", "amount", "parent_id")), exclude_fields=["secret", "owner_id"],
            excel_scope_filter=child_scope, list_order=["-id"],
        )
        note = CRUDRouter("/notes", CRUDBase(ExportNote), create_schema=NoteCreate, list_schema=PageQueryBase, excel=ExcelConfig(("note", "parent_id")))
        parents = [await ExportParent.create(number=number, name=name) for number, name in [
            ("VISIBLE-1", "match"), ("VISIBLE-2", "match"), ("VISIBLE-3", "other"), ("HIDDEN-4", "match"),
        ]]
        for index, item in enumerate(parents, start=1):
            await ExportChild.create(parent_id=item.pk, label=f"L{index}", amount="1.123456")
            await ExportNote.create(parent_id=item.pk, note=f"N{index}")
        await ExportChild.create(parent_id=parents[0].pk, label="=1+1", amount="2.654321")
        await ExportChild.create(parent_id=parents[0].pk, label="scope-hidden", amount="3", owner_id=2)
        await ExportChild.create(parent_id=parents[0].pk, label="deleted", amount="4", deleted_at=datetime(2026, 11, 1))
        await ExportChild.create(parent_id=None, label="unlinked", amount="5")
        api = FastAPI()
        api.add_exception_handler(BizError, BizErrorHandle)
        api.include_router(parent.router)
        yield api, parent, child, parents


@pytest.mark.asyncio(loop_scope="session")
async def test_export_detail_selection_scope_order_and_precision(detail_export: tuple) -> None:
    app, _, _, parents = detail_export
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/parents/export", json={
            "name": "match", "ids": [encode_id(item.pk) for item in parents],
            "size": 1, "current": 2, "orderBy": ["-id"], "parentFields": ["number"],
        })
    assert response.json()["code"] == "0000"
    workbook = load_workbook(BytesIO(b64decode(response.json()["data"]["content"])))
    try:
        assert workbook.sheetnames == ["Data", "明细", "备注"]
        assert list(workbook["Data"].values) == [("单号", "名称"), ("VISIBLE-2", "match"), ("VISIBLE-1", "match")]
        assert list(workbook["明细"].values) == [
            ("父表：单号", "项目", "金额", "parent_id"),
            ("VISIBLE-2", "L2", "1.123456", encode_id(parents[1].pk)),
            ("VISIBLE-1", "=1+1", "2.654321", encode_id(parents[0].pk)),
            ("VISIBLE-1", "L1", "1.123456", encode_id(parents[0].pk)),
        ]
        assert workbook["明细"]["B3"].data_type == "s"
        assert list(workbook["备注"].values)[1:] == [("VISIBLE-2", "N2", encode_id(parents[1].pk)), ("VISIBLE-1", "N1", encode_id(parents[0].pk))]
    finally:
        workbook.close()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("selection", [None, [], ["name", "number"]])
async def test_export_detail_optional_parent_fields_and_empty_results(detail_export: tuple, selection: list[str] | None) -> None:
    app, _, _, parents = detail_export
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        for ids in ([encode_id(parents[0].pk)], [encode_id(parents[3].pk)]):
            payload = {"ids": ids, **({"parentFields": selection} if selection is not None else {})}
            response = await client.post("/parents/export", json=payload)
            assert response.json()["code"] == "0000"
            workbook = load_workbook(BytesIO(b64decode(response.json()["data"]["content"])))
            try:
                expected = ["父表：单号", "父表：名称"] if selection is None else [f"父表：{'单号' if name == 'number' else '名称'}" for name in selection]
                assert list(workbook["明细"].values)[0] == (*expected, "项目", "金额", "parent_id")
                assert workbook["明细"].max_row == (3 if ids[0] == encode_id(parents[0].pk) else 1)
            finally:
                workbook.close()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("selection", [["secret"], ["unknown"], ["number", "number"]])
async def test_export_detail_rejects_unlisted_and_duplicate_parent_fields(detail_export: tuple, selection: list[str]) -> None:
    app, *_ = detail_export
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/parents/export", json={"parentFields": selection})
    assert response.json()["code"] != "0000"
    assert "父表" in response.json()["msg"]


@pytest.mark.asyncio(loop_scope="session")
async def test_export_detail_applies_child_policy_and_transform(detail_export: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _, child, parents = detail_export
    async def policy(name: str, **kwargs: object) -> Q:
        assert name == "child-policy"
        return Q(label="L1")
    async def transform(obj: ExportChild) -> dict:
        return {"label": "transformed", "amount": str(obj.amount), "parentId": encode_id(obj.parent_id)}
    child.data_policy = "child-policy"
    child.record_transform = transform
    monkeypatch.setattr("app.core.excel_export.apply_data_policy", policy)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/parents/export", json={"ids": [encode_id(parents[0].pk)], "parentFields": []})
    workbook = load_workbook(BytesIO(b64decode(response.json()["data"]["content"])))
    try:
        assert list(workbook["明细"].values)[1:] == [("transformed", "1.123456", encode_id(parents[0].pk))]
    finally:
        workbook.close()


@pytest.mark.asyncio(loop_scope="session")
async def test_export_detail_limits_fail_without_partial_file(detail_export: tuple, monkeypatch: pytest.MonkeyPatch) -> None:
    app, _, _, parents = detail_export
    monkeypatch.setattr("app.core.excel_export.MAX_ROWS", 1)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/parents/export", json={"ids": [encode_id(parents[0].pk)]})
        assert response.json()["code"] != "0000"
        assert "子表" in response.json()["msg"]
        assert not response.json().get("data")
        monkeypatch.setattr("app.core.excel_export.MAX_ROWS", 10000)
        monkeypatch.setattr("app.core.excel_export.MAX_COLUMNS", 4)
        response = await client.post("/parents/export", json={})
        assert response.json()["code"] != "0000"
        assert "列" in response.json()["msg"]


@pytest.mark.asyncio(loop_scope="session")
async def test_detail_export_works_with_id_round_trip_parent_schema(detail_export: tuple) -> None:
    _, original, _, parents = detail_export
    crud = CRUDRouter(
        "/roundtrip", original.controller, create_schema=ParentCreate,
        update_schema=make_optional(ParentCreate, "RoundTripUpdate"), list_schema=ParentSearch,
        excel=replace(original.excel, update_key="id"), exclude_fields=["secret"],
    )
    app = FastAPI()
    app.include_router(crud.router)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/roundtrip/export", json={"ids": [encode_id(parents[0].pk)]})
    assert response.json()["code"] == "0000"
    workbook = load_workbook(BytesIO(b64decode(response.json()["data"]["content"])))
    try:
        assert list(workbook["Data"].values)[0] == ("ID", "单号", "名称")
        assert list(workbook["明细"].values)[0][:3] == ("父表：ID", "父表：单号", "父表：名称")
        assert list(workbook["明细"].values)[1][0] == encode_id(parents[0].pk)
    finally:
        workbook.close()


@pytest.mark.asyncio(loop_scope="session")
async def test_export_detail_keeps_route_permissions(detail_export: tuple) -> None:
    _, original, _, _ = detail_export
    async def denied() -> None:
        raise BizError("2201", "denied")
    guarded = CRUDRouter(
        "/guarded", original.controller, create_schema=ParentCreate, list_schema=ParentSearch,
        excel=original.excel, action_dependencies={"export": [Depends(denied)]},
    )
    app = FastAPI()
    app.add_exception_handler(BizError, BizErrorHandle)
    app.include_router(guarded.router)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/guarded/export", json={})
    assert response.json()["code"] == "2201"
