"""
weighbridge_settlement business module manifest.
"""

from app.business.weighbridge_settlement.api import router
from app.business.weighbridge_settlement.init_data import INIT_DATA
from app.utils import BusinessModule, BusinessRouter, PermissionSpec

module = BusinessModule(
    name="weighbridge_settlement",
    title="磅单结算",
    version="0.1.0",
    routers=[BusinessRouter(router=router, auth="permission")],
    permissions=PermissionSpec(init_data=INIT_DATA),
)
