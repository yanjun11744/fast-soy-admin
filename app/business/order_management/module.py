"""
order_management business module manifest.
"""

from app.business.order_management.api import router
from app.business.order_management.init_data import INIT_DATA
from app.utils import BusinessModule, BusinessRouter, PermissionSpec

module = BusinessModule(
    name="order_management",
    title="订单管理",
    version="0.1.0",
    routers=[BusinessRouter(router=router, auth="permission")],
    permissions=PermissionSpec(init_data=INIT_DATA),
)
