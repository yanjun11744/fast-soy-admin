"""
weighbridge_settlement 初始化数据 — 菜单、角色、种子数据。

启动时由 autodiscover 自动发现并执行 init()。
所有操作幂等，重复启动不会重复创建。
"""

from app.system.services import apply_init_data

INIT_DATA = {
    "menus": [
        {
            "menu_name": "磅单结算",
            "route_name": "weighbridge-settlement",
            "route_path": "/weighbridge-settlement",
            "order": 8,
            "icon": "mdi:application-cog-outline",
            "i18n_key": "route.weighbridge-settlement",
            "reconcile": {"menus": True, "buttons": False},
            "children": [
                {
                    "menu_name": "工序招采价格",
                    "route_name": "weighbridge-settlement_settlement-rate",
                    "route_path": "/weighbridge-settlement/settlement-rate",
                    "component": "view.weighbridge-settlement_settlement-rate",
                    "order": 1,
                    "icon": "mdi:table",
                    "i18n_key": "route.weighbridge-settlement_settlement-rate",
                },
                {
                    "menu_name": "磅单信息",
                    "route_name": "weighbridge-settlement_weighing-ticket",
                    "route_path": "/weighbridge-settlement/weighing-ticket",
                    "component": "view.weighbridge-settlement_weighing-ticket",
                    "order": 2,
                    "icon": "mdi:table",
                    "i18n_key": "route.weighbridge-settlement_weighing-ticket",
                },
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
