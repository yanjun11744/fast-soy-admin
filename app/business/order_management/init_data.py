"""
order_management 初始化数据 — 菜单、角色、种子数据。

启动时由 autodiscover 自动发现并执行 init()。
所有操作幂等，重复启动不会重复创建。
"""

from app.system.services import apply_init_data

INIT_DATA = {
    "menus": [
        {
            "menu_name": "订单管理",
            "route_name": "order-management",
            "route_path": "/order-management",
            "order": 8,
            "icon": "mdi:application-cog-outline",
            "i18n_key": "route.order-management",
            "reconcile": {"menus": True, "buttons": False},
            "children": [
                {
                    "menu_name": "订单资料",
                    "route_name": "order-management_order",
                    "route_path": "/order-management/order",
                    "component": "view.order-management_order",
                    "order": 1,
                    "icon": "mdi:table",
                    "i18n_key": "route.order-management_order",
                }
            ],
        }
    ],
    "roles": [],
    "users": [],
    "dictionaries": [],
}


async def init() -> None:
    """模块初始化入口 — 由 autodiscover 调用。"""
    await apply_init_data(INIT_DATA)
    # 普通角色要看到该菜单，请在角色管理中授权，或在这里补充 _init_role_data()。
    # await _init_role_data()
