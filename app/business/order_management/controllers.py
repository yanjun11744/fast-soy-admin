"""
order_management controllers — 基于 CRUDBase 的控制器。
"""

from app.business.order_management.models import Order
from app.utils import CRUDBase

order_controller = CRUDBase(model=Order)
