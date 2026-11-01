"""
weighbridge_settlement 管理接口 — CRUD。
"""

from fastapi import APIRouter

from app.business.weighbridge_settlement.controllers import settlement_rate_controller, weighing_ticket_controller
from app.business.weighbridge_settlement.schemas import (
    SettlementRateCreate,
    SettlementRateSearch,
    SettlementRateUpdate,
    WeighingTicketCreate,
    WeighingTicketSearch,
    WeighingTicketUpdate,
)
from app.utils import CRUDRouter, ExcelConfig, SearchFieldConfig

settlement_rate_crud = CRUDRouter(
    prefix="/settlement_rates",
    controller=settlement_rate_controller,
    create_schema=SettlementRateCreate,
    excel=ExcelConfig(fields=("process_name", "price", "enabled")),
    update_schema=SettlementRateUpdate,
    list_schema=SettlementRateSearch,
    route_key_prefix="weighbridge_settlement.settlement_rates",
    search_fields=SearchFieldConfig(contains_fields=["process_name"], exact_fields=["enabled"]),
    summary_prefix="工序招采价格",
)

weighing_ticket_crud = CRUDRouter(
    prefix="/weighing_tickets",
    controller=weighing_ticket_controller,
    create_schema=WeighingTicketCreate,
    excel=ExcelConfig(fields=("ticket_no", "weighing_date", "weight", "process", "price", "total_amount", "is_settled", "revision", "rate_id")),
    update_schema=WeighingTicketUpdate,
    list_schema=WeighingTicketSearch,
    route_key_prefix="weighbridge_settlement.weighing_tickets",
    search_fields=SearchFieldConfig(contains_fields=["ticket_no", "process"], exact_fields=["is_settled", "rate_id"], range_fields=["weighing_date"]),
    summary_prefix="磅单信息",
)

router = APIRouter(tags=["weighbridge_settlement"])
router.include_router(settlement_rate_crud.router)
router.include_router(weighing_ticket_crud.router)
