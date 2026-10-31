"""
order_management 管理接口 — CRUD。
"""

from fastapi import APIRouter

from app.business.order_management.controllers import order_controller
from app.business.order_management.schemas import (
    OrderCreate,
    OrderSearch,
    OrderUpdate,
)
from app.utils import CRUDRouter, ExcelConfig, SearchFieldConfig

order_crud = CRUDRouter(
    prefix="/orders",
    controller=order_controller,
    create_schema=OrderCreate,
    excel=ExcelConfig(fields=('order_no', 'part_no', 'name', 'unit_weight', 'unit', 'quantity', 'received_quantity', 'total_weight', 'order_due_date', 'completed_date', 'process_route', 'customer')),
    update_schema=OrderUpdate,
    list_schema=OrderSearch,
    route_key_prefix="order_management.orders",
    search_fields=SearchFieldConfig(contains_fields=['order_no', 'part_no', 'name', 'unit', 'process_route', 'customer']),
    summary_prefix="订单资料",
)

router = APIRouter(tags=["order_management"])
router.include_router(order_crud.router)
