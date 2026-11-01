"""Settlement acceptance tests run exclusively against an isolated in-memory database."""

from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from tortoise.context import tortoise_test_context

from app.business.order_management.models import Order
from app.business.weighbridge_settlement import services
from app.business.weighbridge_settlement.api.manage import router
from app.business.weighbridge_settlement.calculation import calculate
from app.business.weighbridge_settlement.models import SettlementRate, WeighingLine, WeighingTicket
from app.business.weighbridge_settlement.schemas import WeighingTicketCreate, WeighingTicketUpdate
from app.core.ctx import CTX_USER_ID
from app.core.dependency import PermissionControl
from app.core.init_app import register_exceptions
from app.utils import BizError, decode_id, encode_id


@pytest.fixture
async def settlement_db():
    async with tortoise_test_context(
        modules=["app.business.order_management.models", "app.business.weighbridge_settlement.models"],
        app_label="app_system",
        connection_label="conn_system",
        use_tz=False,
    ):
        token = CTX_USER_ID.set(1)
        rate = await SettlementRate.create(process_name="喷漆", price=Decimal("2.5000"))
        yield rate
        CTX_USER_ID.reset(token)


def payload(rate, **overrides):
    data = dict(
        ticketNo="T-001",
        weighingDate="2026-11-01",
        weight="100.001",
        rateId=encode_id(rate.id),
        lines=[
            dict(orderId=None, partNo="manual-1", name="手动一", unitWeight="1.000001", quantity=3),
            dict(orderId=None, partNo="manual-2", name="手动二", unitWeight="2.000000", quantity=2),
        ],
    )
    return {**data, **overrides}


def edit_payload(detail, **overrides):
    keys = ["id", "orderId", "orderNo", "partNo", "name", "unitWeight", "quantity"]
    return {**{key: detail[key] for key in ["ticketNo", "weighingDate", "weight", "revision"]}, "lines": [{key: line[key] for key in keys} for line in detail["lines"]], **overrides}


@pytest.mark.parametrize("weight,price,count", [("100.001", "2.5000", 3), ("0.002", "99.9999", 30), ("999999.999", "0.0001", 7)])
def test_decimal_residuals(weight, price, count):
    amount, lines = calculate(Decimal(weight), Decimal(price), [dict(unit_weight=Decimal("1.000001"), quantity=3) for _ in range(count)])
    assert sum(row["allocated_weight"] for row in lines) == Decimal(weight)
    assert sum(row["amount"] for row in lines) == amount
    assert all(row["allocated_weight"] >= 0 and row["amount"] >= 0 for row in lines)
    assert amount == (Decimal(weight) * Decimal(price)).quantize(Decimal(".01"), rounding="ROUND_HALF_UP")
    assert [row["position"] for row in lines] == list(range(1, count + 1))


@pytest.mark.asyncio(loop_scope="session")
async def test_manual_and_matched_persistence_snapshot_revision_and_lock(settlement_db):
    rate = settlement_db
    order = await Order.create(order_no="O-1", part_no="P-1", name="原名称", unit_weight="3.123456", quantity=999)
    data = payload(rate)
    data["lines"].insert(0, dict(orderId=encode_id(order.id), quantity=2))
    saved = await services.save_ticket(WeighingTicketCreate.model_validate(data))
    ticket_id = decode_id(saved["id"])
    assert len(saved["lines"]) == 3
    assert saved["lines"][0]["quantity"] == 2
    assert saved["lines"][0]["unitWeight"] == "3.123456"
    assert all(row["orderId"] is None for row in saved["lines"][1:])
    assert await Order.all().count() == 1
    assert await services.detail(ticket_id) == saved
    await SettlementRate.filter(id=rate.id).update(price=Decimal("9.9999"), enabled=False)
    await Order.filter(id=order.id).update(name="新名称", unit_weight="9.000000")
    original_ids = [line["id"] for line in saved["lines"]]
    changed = edit_payload(saved, weight="120.001")
    changed["lines"] = list(reversed(changed["lines"]))
    updated = await services.save_ticket(WeighingTicketUpdate.model_validate(changed), ticket_id)
    assert updated["price"] == "2.5" or Decimal(updated["price"]) == Decimal("2.5000")
    assert updated["lines"][-1]["name"] == "原名称"
    assert [line["id"] for line in updated["lines"]] == list(reversed(original_ids))
    with pytest.raises(BizError, match="其他用户"):
        await services.save_ticket(WeighingTicketUpdate.model_validate(changed), ticket_id)
    with pytest.raises(BizError, match="已启用"):
        await services.save_ticket(WeighingTicketUpdate.model_validate(edit_payload(updated, rateId=encode_id(rate.id))), ticket_id)
    await SettlementRate.filter(id=rate.id).update(enabled=True)
    refreshed = await services.save_ticket(WeighingTicketUpdate.model_validate(edit_payload(updated, rateId=encode_id(rate.id))), ticket_id)
    assert Decimal(refreshed["price"]) == Decimal("9.9999")
    settled = await services.settle_ticket(ticket_id, refreshed["revision"])
    assert settled["isSettled"] is True
    with pytest.raises(BizError, match="已结算"):
        await services.save_ticket(WeighingTicketUpdate.model_validate(edit_payload(settled)), ticket_id)
    with pytest.raises(BizError, match="已结算"):
        await services.delete_tickets([ticket_id])
    # A matched order may be reused in a different ticket.
    data["ticketNo"] = "T-002"
    await services.save_ticket(WeighingTicketCreate.model_validate(data))
    assert await WeighingTicket.all().count() == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_diff_update_removes_and_adds_lines(settlement_db):
    saved = await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db)))
    data = edit_payload(saved)
    deleted = decode_id(data["lines"].pop()["id"])
    data["lines"].append(dict(orderId=None, partNo="new", name="新增", unitWeight="2.123456", quantity=5))
    updated = await services.save_ticket(WeighingTicketUpdate.model_validate(data), decode_id(saved["id"]))
    assert updated["lines"][0]["id"] == saved["lines"][0]["id"]
    assert not await WeighingLine.filter(id=deleted).exists()
    assert len(updated["lines"]) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_create_and_update_roll_back_on_line_failure(settlement_db, monkeypatch):
    saved = await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db)))
    original_create = WeighingLine.create.__func__
    calls = 0

    async def fail_second(cls, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected storage failure")
        return await original_create(cls, **kwargs)

    monkeypatch.setattr(WeighingLine, "create", classmethod(fail_second))
    with pytest.raises(RuntimeError):
        await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db, ticketNo="FAIL")))
    assert await WeighingTicket.all().count() == 1
    assert await WeighingLine.all().count() == 2
    calls = 1
    changed = edit_payload(saved, weight="888.001")
    changed["lines"] = [dict(orderId=None, partNo="new", name="新行", unitWeight="1", quantity=1)]
    with pytest.raises(RuntimeError):
        await services.save_ticket(WeighingTicketUpdate.model_validate(changed), decode_id(saved["id"]))
    assert await services.detail(decode_id(saved["id"])) == saved


@pytest.mark.asyncio(loop_scope="session")
async def test_http_lookup_validation_and_no_crud_bypass(settlement_db):
    app = FastAPI()
    app.include_router(router)
    register_exceptions(app)
    app.dependency_overrides[PermissionControl.has_permission] = lambda: None
    for number, part in [(1, "AB-partial"), (2, "AB"), (3, "AB")]:
        await Order.create(order_no=f"O-{number}", part_no=part, name="test", unit_weight="1.123456")
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        options = await client.get("/settlement_rates/options")
        assert options.json()["data"][0]["processName"] == "喷漆"
        invalid_rate = await client.patch(f'/settlement_rates/{encode_id(settlement_db.id)}', json={'price': '0'})
        assert invalid_rate.json()['code'] != '0000'

        found = (await client.post("/weighing_tickets/order-options", json={"partNo": "AB", "limit": 3})).json()["data"]
        assert len(found) == 3
        assert [row["partNo"] for row in found] == ["AB", "AB", "AB-partial"]
        assert len({row["id"] for row in found}) == 3
        invalid = await client.post("/weighing_tickets", json=payload(settlement_db, totalAmount="1", isSettled=True))
        assert invalid.json()["code"] != "0000"
        created = (await client.post("/weighing_tickets", json=payload(settlement_db))).json()["data"]
        exported = await client.post('/weighing_tickets/export', json={'ids': [created['id']]})
        assert exported.json()['code'] == '0000'
        assert exported.json()['data']['filename'].endswith('.xlsx')
        settled = await client.post(f"/weighing_tickets/{created['id']}/settle", json={"revision": 1})
        assert settled.json()["data"]["isSettled"] is True
        forbidden = await client.patch(f"/weighing_tickets/{created['id']}", json=edit_payload(created))
        assert forbidden.json()["code"] == "4603"
        deleted = await client.delete(f"/weighing_tickets/{created['id']}")
        assert deleted.json()["code"] == "4603"
        bulk = await client.request("DELETE", "/weighing_tickets", json={"ids": [created["id"]]})
        assert bulk.json()["code"] == "4603"
        imported = await client.post("/weighing_tickets/import")
        assert imported.status_code in (404, 405)


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_edits_allow_only_one_winner(settlement_db):
    import asyncio

    saved = await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db)))
    ticket_id = decode_id(saved['id'])
    results = await asyncio.gather(*[
        services.save_ticket(WeighingTicketUpdate.model_validate(edit_payload(saved, weight=weight)), ticket_id)
        for weight in ('111.001', '222.002')
    ], return_exceptions=True)
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, BizError) for result in results) == 1
    current = await services.detail(ticket_id)
    assert current['revision'] == 2
    assert sum(Decimal(row['allocatedWeight']) for row in current['lines']) == Decimal(current['weight'])


@pytest.mark.asyncio(loop_scope="session")
async def test_invalid_lines_and_foreign_ids_are_rejected(settlement_db):
    from pydantic import ValidationError

    for invalid in [dict(quantity=0), dict(quantity=1.5), dict(quantity=True), dict(unitWeight='0')]:
        data = payload(settlement_db)
        data['lines'][0].update(invalid)
        with pytest.raises(ValidationError):
            WeighingTicketCreate.model_validate(data)
    data = payload(settlement_db)
    data['lines'][0]['name'] = ' '
    with pytest.raises(BizError):
        await services.save_ticket(WeighingTicketCreate.model_validate(data))
    saved = await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db)))
    other = await services.save_ticket(WeighingTicketCreate.model_validate(payload(settlement_db, ticketNo='OTHER')))
    changed = edit_payload(saved)
    changed['lines'][0]['id'] = other['lines'][0]['id']
    with pytest.raises(BizError, match='不属于'):
        await services.save_ticket(WeighingTicketUpdate.model_validate(changed), decode_id(saved['id']))
    assert await services.detail(decode_id(saved['id'])) == saved


@pytest.mark.asyncio(loop_scope="session")
async def test_mutations_require_backend_permission(settlement_db):
    app = FastAPI()
    app.include_router(router)
    register_exceptions(app)
    async with AsyncClient(transport=ASGITransport(app), base_url='http://test') as client:
        result = await client.post('/weighing_tickets', json=payload(settlement_db))
        assert result.json()['code'] != '0000'
    assert await WeighingTicket.all().count() == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_decimal_response_uses_fixed_precision_not_exponent_notation(settlement_db):
    data = payload(settlement_db, weight="1000.000")
    data['lines'] = [dict(orderId=None, partNo='P', name='Power of ten', unitWeight='1.000000', quantity=1000)]
    saved = await services.save_ticket(WeighingTicketCreate.model_validate(data))
    assert saved['weight'] == '1000.000'
    assert saved['price'] == '2.5000'
    assert saved['lines'][0]['theoreticalWeight'] == '1000.000000'
    assert saved['lines'][0]['allocatedWeight'] == '1000.000'
    assert saved['lines'][0]['amount'] == '2500.00'
