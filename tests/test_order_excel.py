"""Order Excel headers use business names; weight units belong to the UI."""

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise.context import tortoise_test_context
from tortoise.exceptions import IntegrityError

from app.business.order_management.api.manage import order_crud
from app.business.order_management.models import Order
from app.business.order_management.schemas import OrderCreate
from app.core.crud import CRUDBase
from app.core.ctx import CTX_USER
from app.core.excel import ExcelConfig, read_excel, write_excel
from app.core.exceptions import BizError, BizErrorHandle
from app.core.router import CRUDRouter
from app.system.models import User


@pytest.mark.parametrize("weight_headers", [("净重", "毛重"), ("netWeight", "grossWeight"), ("net_weight", "gross_weight")])
def test_order_import_recognizes_weight_headers_without_units(weight_headers: tuple[str, str]) -> None:
    config = order_crud.excel
    assert config is not None
    content = write_excel(["订单号", "项目号", "名称", *weight_headers], [["IMPORT-1", "PART-1", "示例", "1.123456", "2.654321"]])
    rows = read_excel(content, OrderCreate, config)
    assert rows[0].net_weight == Decimal("1.123456")
    assert rows[0].gross_weight == Decimal("2.654321")


def test_order_template_and_export_use_weight_headers_without_units() -> None:
    config = order_crud.excel
    assert config is not None
    headers, _ = config.resolve(OrderCreate)
    assert headers[config.fields.index("net_weight")] == "净重"
    assert headers[config.fields.index("gross_weight")] == "毛重"
    data = OrderCreate(order_no="EXPORT-1", part_no="PART-1", name="示例", net_weight=Decimal("1.123456"), gross_weight=Decimal("2.654321"))
    content = write_excel(headers, [[getattr(data, name) for name in config.fields]])
    imported = read_excel(content, OrderCreate, config)[0]
    assert imported == data


@pytest.fixture
async def order_excel_client() -> AsyncIterator[AsyncClient]:
    async with tortoise_test_context(
        modules=["app.business.order_management.models"],
        app_label="app_system",
        connection_label="conn_system",
        use_tz=False,
    ):
        api = FastAPI()
        api.add_exception_handler(BizError, BizErrorHandle)
        api.include_router(order_crud.router)
        async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
            yield client


@pytest.mark.asyncio(loop_scope="session")
async def test_order_excel_updates_existing_and_creates_new_with_audit(order_excel_client: AsyncClient) -> None:
    original = await Order.create(order_no="EXISTING", part_no="P-1", name="旧名称", net_weight="1", customer="保留用户", quantity=5, created_by="creator")
    token = CTX_USER.set(User(user_name="importer"))
    content = write_excel(
        ["订单号", "项目号", "名称", "净重", "用户", "数量"],
        [["EXISTING", "P-2", "新名称", "2.123456", None, 0], ["NEW", "P-3", "新增", "3", "新用户", 1]],
    )
    try:
        preview = await order_excel_client.post("/orders/import-preview", files={"file": ("orders.xlsx", content)})
        assert preview.json()["data"]["errors"] == []
        await original.refresh_from_db()
        assert original.name == "旧名称"
        assert await Order.all().count() == 1
        for _ in range(2):
            response = await order_excel_client.post("/orders/import", files={"file": ("orders.xlsx", content)})
            assert response.json()["data"]["importedCount"] == 2
        await original.refresh_from_db()
        assert await Order.all().count() == 2
        assert original.part_no == "P-2"
        assert original.name == "新名称"
        assert original.net_weight == Decimal("2.123456")
        assert original.quantity == 0
        assert original.customer == "保留用户"
        assert original.created_by == "creator"
        assert original.updated_by == "importer"
        assert (await Order.get(order_no="NEW")).created_by == "importer"
    finally:
        CTX_USER.reset(token)


@pytest.mark.asyncio(loop_scope="session")
async def test_order_excel_rolls_back_updates_and_creates_on_write_failure(order_excel_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original = await Order.create(order_no="EXISTING", part_no="P-1", name="旧名称", net_weight="1")
    create = order_crud.controller.create

    async def fail_last(obj_in: OrderCreate) -> Order:
        if obj_in.order_no == "FAIL":
            raise IntegrityError("simulated constraint failure")
        return await create(obj_in=obj_in)

    monkeypatch.setattr(order_crud.controller, "create", fail_last)
    content = write_excel(
        ["订单号", "项目号", "名称", "净重"],
        [["EXISTING", "P-1", "新名称", "2"], ["NEW", "P-2", "新增", "3"], ["FAIL", "P-3", "失败", "4"]],
    )
    response = await order_excel_client.post("/orders/import", files={"file": ("orders.xlsx", content)})
    assert "第 4 行" in response.json()["msg"]
    await original.refresh_from_db()
    assert original.name == "旧名称"
    assert original.net_weight == Decimal("1")
    assert await Order.all().count() == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_excel_without_update_key_keeps_create_only_behavior(order_excel_client: AsyncClient) -> None:
    api = FastAPI()
    api.add_exception_handler(BizError, BizErrorHandle)
    crud = CRUDRouter(prefix="/items", controller=CRUDBase(Order), create_schema=OrderCreate, excel=ExcelConfig(fields=("order_no", "part_no", "name", "net_weight")))
    api.include_router(crud.router)
    original = await Order.create(order_no="EXISTING", part_no="P-1", name="旧名称", net_weight="1")
    content = write_excel(["订单号", "项目号", "名称", "净重"], [["EXISTING", "P-1", "新名称", "2"]])
    async with AsyncClient(transport=ASGITransport(app=api), base_url="http://test") as client:
        response = await client.post("/items/import", files={"file": ("orders.xlsx", content)})
    assert response.json()["code"] != "0000"
    await original.refresh_from_db()
    assert original.name == "旧名称"


@pytest.mark.parametrize("key", ["missing", "customer"])
def test_excel_update_key_must_be_a_required_import_field(key: str) -> None:
    with pytest.raises(ValueError, match="required configured field"):
        ExcelConfig(fields=tuple(OrderCreate.model_fields), update_key=key).resolve(OrderCreate)


def test_excel_update_key_must_be_unique_and_update_enabled() -> None:
    from app.business.order_management.schemas import OrderUpdate

    with pytest.raises(ValueError, match="unique non-null"):
        CRUDRouter(prefix="/items", controller=CRUDBase(Order), create_schema=OrderCreate, update_schema=OrderUpdate, excel=ExcelConfig(fields=tuple(OrderCreate.model_fields), update_key="part_no"))
    with pytest.raises(ValueError, match="enabled update route"):
        CRUDRouter(prefix="/items", controller=CRUDBase(Order), create_schema=OrderCreate, excel=ExcelConfig(fields=tuple(OrderCreate.model_fields), update_key="order_no"))
