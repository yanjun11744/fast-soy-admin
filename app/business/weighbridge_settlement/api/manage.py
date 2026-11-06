"""Generated rate CRUD and ticket aggregate endpoints, under the existing permission manifest."""

from base64 import b64encode

from fastapi import APIRouter
from tortoise.expressions import Q

from app.business.weighbridge_settlement import services
from app.business.weighbridge_settlement.controllers import settlement_rate_controller, weighing_ticket_controller
from app.business.weighbridge_settlement.export import TICKET_EXCEL, export_tickets
from app.business.weighbridge_settlement.schemas import (
    OrderLookup,
    PreviewInput,
    RevisionInput,
    SettlementRateCreate,
    SettlementRateSearch,
    SettlementRateUpdate,
    WeighingTicketCreate,
    WeighingTicketExport,
    WeighingTicketOut,
    WeighingTicketSearch,
    WeighingTicketUpdate,
)
from app.utils import CommonIds, CRUDRouter, DependPermission, ExcelConfig, ResponseModel, SearchFieldConfig, SqidPath, Success

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

# Only the read-only generated search remains. All aggregate writes go through the service;
# no single-table Excel import endpoint is registered for tickets.
weighing_ticket_crud = CRUDRouter(
    prefix="/weighing_tickets",
    controller=weighing_ticket_controller,
    create_schema=WeighingTicketOut,
    excel=TICKET_EXCEL,
    update_schema=WeighingTicketUpdate,
    list_schema=WeighingTicketSearch,
    enable_routes={"list"},
    route_key_prefix="weighbridge_settlement.weighing_tickets",
    search_fields=SearchFieldConfig(contains_fields=["ticket_no", "process"], exact_fields=["is_settled", "rate_id"], range_fields=["weighing_date"]),
    summary_prefix="磅单信息",
)

router = APIRouter(tags=["weighbridge_settlement"], dependencies=[DependPermission])


@weighing_ticket_crud.override("export")
async def export_ticket_excel(obj_in: WeighingTicketExport) -> Success:
    search = weighing_ticket_controller.build_search(obj_in, **vars(weighing_ticket_crud.search_fields))
    if obj_in.ids is not None:
        search &= Q(id__in=obj_in.ids)
    content = await export_tickets(search, obj_in.order_by or weighing_ticket_crud.list_order)
    return Success(data={"filename": "weighing_tickets.xlsx", "content": b64encode(content).decode()})


@router.get("/settlement_rates/options", summary="可选启用工序", name="weighbridge_settlement.settlement_rates.options")
async def rate_options() -> Success:
    return Success(data=await services.rate_options())


@router.post("/weighing_tickets/order-options", summary="按项目号匹配订单", name="weighbridge_settlement.weighing_tickets.order_options")
async def order_options(obj_in: OrderLookup) -> Success:
    return Success(data=await services.order_options(obj_in))


@router.post("/weighing_tickets/preview", summary="Decimal结算试算", name="weighbridge_settlement.weighing_tickets.preview")
async def preview(obj_in: PreviewInput) -> Success:
    return Success(data=services.preview(obj_in))


@router.post("/weighing_tickets", summary="创建磅单及明细", name="weighbridge_settlement.weighing_tickets.create", response_model=ResponseModel[WeighingTicketOut])
async def create_ticket(obj_in: WeighingTicketCreate) -> Success:
    return Success(data=await services.save_ticket(obj_in))


@router.get("/weighing_tickets/{item_id}", summary="磅单完整详情", name="weighbridge_settlement.weighing_tickets.get", response_model=ResponseModel[WeighingTicketOut])
async def get_ticket(item_id: SqidPath) -> Success:
    return Success(data=await services.detail(item_id))


@router.patch("/weighing_tickets/{item_id}", summary="更新未结算磅单及明细", name="weighbridge_settlement.weighing_tickets.update", response_model=ResponseModel[WeighingTicketOut])
async def update_ticket(item_id: SqidPath, obj_in: WeighingTicketUpdate) -> Success:
    return Success(data=await services.save_ticket(obj_in, item_id))


@router.post("/weighing_tickets/{item_id}/settle", summary="确认结算", name="weighbridge_settlement.weighing_tickets.settle", response_model=ResponseModel[WeighingTicketOut])
async def settle_ticket(item_id: SqidPath, obj_in: RevisionInput) -> Success:
    return Success(data=await services.settle_ticket(item_id, obj_in.revision))


@router.delete("/weighing_tickets/{item_id}", summary="删除未结算磅单", name="weighbridge_settlement.weighing_tickets.delete")
async def delete_ticket(item_id: SqidPath) -> Success:
    await services.delete_tickets([item_id])
    return Success()


@router.delete("/weighing_tickets", summary="批量删除未结算磅单", name="weighbridge_settlement.weighing_tickets.batch_delete")
async def delete_tickets(obj_in: CommonIds) -> Success:
    await services.delete_tickets(obj_in.ids)
    return Success()


router.include_router(settlement_rate_crud.router)
router.include_router(weighing_ticket_crud.router)
