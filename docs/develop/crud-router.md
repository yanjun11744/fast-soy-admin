# CRUDRouter

`CRUDRouter` 批量生成 6 条标准 REST 路由，配合 [`CRUDBase`](./crud.md) 和 [API 约定](./api.md) 使用，消灭 90% 的样板代码。

源码：[app/core/router.py](../../../app/core/router.py)。

## 生成的 6 条标准路由

| 名称 | 方法 + 路径 | 启用条件 | Body / Param |
|---|---|---|---|
| `list` | `POST /{prefix}/search` | 传 `list_schema` | `list_schema`（含 `current/size/orderBy`） |
| `get` | `GET /{prefix}/{item_id}` | 始终 | `item_id: SqidPath` |
| `create` | `POST /{prefix}` | 传 `create_schema` | `create_schema` |
| `update` | `PATCH /{prefix}/{item_id}` | 传 `update_schema` | `item_id` + `update_schema` |
| `delete` | `DELETE /{prefix}/{item_id}` | 始终 | `item_id` |
| `batch_delete` | `DELETE /{prefix}` | 始终 | `CommonIds`（`{ids: [...]}`） |

`tree_endpoint=True` 时额外注册 `GET /{prefix}/tree`。

## 最简用法

```python
from app.utils import CRUDBase, CRUDRouter, SearchFieldConfig

tag_controller = CRUDBase(model=Tag)

tag_crud = CRUDRouter(
    prefix="/tags",
    controller=tag_controller,
    create_schema=TagCreate,
    update_schema=TagUpdate,
    list_schema=TagSearch,
    search_fields=SearchFieldConfig(
        contains_fields=["name"],
        exact_fields=["category"],
    ),
    summary_prefix="标签",
)
router = tag_crud.router
```

`prefix` 必须以斜杠开头（`/tags`），资源名（最后一段）会被用作生成的路径片段。

## 完整参数

```python
CRUDRouter(
    prefix: str,
    controller: CRUDBase,
    create_schema: type[BaseModel] | None = None,
    update_schema: type[BaseModel] | None = None,
    list_schema: type[BaseModel] | None = None,
    search_fields: SearchFieldConfig | None = None,
    summary_prefix: str = "",
    list_order: list[str] | None = None,           # 默认 ["id"]
    exclude_fields: list[str] | None = None,       # to_dict 排除
    enable_routes: set[str] | None = None,         # 默认全部
    record_transform: Callable | None = None,      # async def transform(obj) -> dict
    soft_delete: bool = False,                     # 走 controller.soft_remove
    tree_endpoint: bool = False,                   # 注册 GET /tree
    action_dependencies: dict[str, Sequence] | None = None,
)
```

### `search_fields: SearchFieldConfig`

```python
SearchFieldConfig(
    contains_fields=[...],     # __contains
    icontains_fields=[...],    # __icontains
    exact_fields=[...],        # 直接相等
    iexact_fields=[...],       # __iexact
    in_fields=[...],           # __in
    range_fields=[...],        # 期望 schema 含 {field}_start / {field}_end
)
```

详见 [`build_search`](./crud.md#build_search--从-schema-自动构建-q)。

### `enable_routes` — 关闭某些路由

```python
crud = CRUDRouter(..., enable_routes={"list", "get"})  # 只读
```

### `record_transform` — 自定义返回 dict

默认列表 / 详情都用 `await obj.to_dict(exclude_fields=...)`。需要做关联预加载或拼字段时：

```python
async def transform(obj: Product) -> dict:
    d = await obj.to_dict()
    await obj.fetch_related("warehouse")
    d["warehouseName"] = obj.warehouse.name
    return d

CRUDRouter(..., record_transform=transform)
```

> 仅推荐少量字段补齐场景。需要 N+1 优化（`select_related` / `prefetch_related`）时直接 `@override("list")` 更直接。

### `soft_delete` — 软删除

需要模型继承 `SoftDeleteMixin`。

```python
CRUDRouter(..., soft_delete=True)
# delete       → controller.soft_remove
# batch_delete → controller.soft_batch_remove
```

### `tree_endpoint` — 树形端点

需要模型有 `parent_id` 字段（建议继承 `TreeMixin`）。生成的 `GET /resources/tree` 用 `_build_nested_tree(records, parent_id_key="parentId", root_value=0)` 把扁平列表组装成嵌套结构。

### `action_dependencies` — 按路由挂依赖

```python
CRUDRouter(
    ...,
    action_dependencies={
        "create":       [require_buttons("B_INVENTORY_WAREHOUSE_CREATE")],
        "update":       [require_buttons("B_INVENTORY_WAREHOUSE_EDIT")],
        "delete":       [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
        "batch_delete": [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
    },
)
```

**关键特性**：`action_dependencies` 对 `@override("create")` 替换的路由**同样生效**——所以业务上不会出现"自定义实现忘了挂权限"的事故。

## 自定义某条路由：`@crud.override`

需要自定义逻辑时**不要**重新写一个 `@router.post("/users")` 覆盖——会被 `_OrderedRouter` 排序后命中默认路由。请用：

```python
@user_crud.override("create")
async def _create_user(user_in: UserCreate, request: Request):
    ...   # 自定义逻辑
    return Success(...)
```

`override` 做了三件事：

1. 从 router 中移除默认实现（按 path + methods 精确匹配）
2. 用你的函数注册到同一 path / methods / summary
3. 自动挂上 `action_dependencies[name]` 的依赖

各路由的标准签名（也可以 `crud.get_route_info("create")` 查）：

```text
list:         async def list_items(obj_in: <list_schema>)
get:          async def get_item(item_id: SqidPath)
create:       async def create_item(obj_in: <create_schema>)
update:       async def update_item(item_id: SqidPath, obj_in: <update_schema>)
delete:       async def delete_item(item_id: SqidPath)
batch_delete: async def batch_delete(obj_in: CommonIds)
```

参数可以**任意扩展**（FastAPI 依赖语义），如：

```python
@user_crud.override("update")
async def _update(item_id: SqidPath, obj_in: UserUpdate, request: Request):
    redis = request.app.state.redis
    ...
```

::: warning 不传 schema 不会生成对应路由
`product_crud` 没传 `create_schema` 时，CRUDRouter 不会注册 `POST /products`。这正好让你能在同一 router 上手写 `@router.post("/products")` 而不被覆盖——库存模块的商品创建就是这样。
:::

## 适用边界 — 别让 CRUDRouter 上瘾

`CRUDRouter` 是给**贫血资源**用的——字典、标签、仓库、分类这种纯 CRUD 表。聚合根（用户、角色、订单、工单等带状态、带副作用的资源）**不要硬塞进 CRUDRouter**。

::: danger 触发改写信号
满足以下任一条件，立刻把该资源改写为显式 `@router.post(...)` + `services/`，不要继续 `@crud.override`：

- override 数 ≥ 3（标准 6 路由覆盖一半，抽象已无收益）
- 任一 override 内出现 `in_transaction` / `redis` / 跨模型写
- 资源是聚合根或带状态机
- 写操作有副作用（发通知、写审计、触发事件、失效缓存）
:::

### `@crud.override` 内禁止出现

下面这些必须下沉到 `services/`，api 层只做"参数转发 + 包响应"：

- `in_transaction(...)` —— 事务编排是 service 的事
- `request.app.state.redis` / 任何 Redis 客户端调用
- 跨模型的 `create` / `update` / `delete`（含 `m2m.add` / `m2m.clear`）
- 调用其他模块的 service / 发事件 / 写审计

### 正确范式

```python
# services/users.py
async def create_user_with_roles(redis, user_in: UserCreate) -> User:
    if await user_controller.get_by_email(user_in.user_email):
        raise BizError(code=Code.DUPLICATE_USER_EMAIL, msg="该邮箱已被注册")
    async with in_transaction(get_db_conn(User)):
        user = await user_controller.create(obj_in=user_in)
        await user_controller.update_roles_by_code(user, user_in.by_user_role_code_list)
    return user

# api/users.py
@crud.override("create")
async def _create_user(user_in: UserCreate, request: Request):
    user = await create_user_with_roles(request.app.state.redis, user_in)
    return Success(msg="创建成功", data={"createdId": encode_id(user.id)})
```

仓库内参考实现：

- [`app/system/api/users.py`](https://github.com/sleep1223/fast-soy-admin/blob/main/app/system/api/users.py) ＋ [`app/system/services/user.py`](https://github.com/sleep1223/fast-soy-admin/blob/main/app/system/services/user.py)
- [`app/system/api/apis.py`](https://github.com/sleep1223/fast-soy-admin/blob/main/app/system/api/apis.py) ＋ [`app/system/services/api.py`](https://github.com/sleep1223/fast-soy-admin/blob/main/app/system/services/api.py)

> 这条约定也作为 PR review checklist 第 15 条强制执行，见 [架构总览 / 强制约定清单](../getting-started/architecture.md)。

## 在 router 上加额外端点

`crud.router` 是普通 `APIRouter`，标准 6 路由之外的端点直接挂：

```python
router = dept_crud.router

@router.post("/warehouses/{dept_id}/products", summary="批量分配商品")
async def assign_products(dept_id: SqidPath, body: AssignProducts):
    ...
    return Success(...)
```

## 业务模块的接线模板

```python
# app/business/inventory/api/manage.py
from fastapi import APIRouter

from app.utils import CRUDRouter, DependPermission, SearchFieldConfig, require_buttons

dept_crud = CRUDRouter(
    prefix="/warehouses",
    controller=warehouse_controller,
    create_schema=WarehouseCreate,
    update_schema=WarehouseUpdate,
    list_schema=WarehouseSearch,
    search_fields=SearchFieldConfig(contains_fields=["name", "code"]),
    summary_prefix="仓库",
    soft_delete=True,
    tree_endpoint=True,
    action_dependencies={
        "create": [require_buttons("B_INVENTORY_WAREHOUSE_CREATE")],
        "update": [require_buttons("B_INVENTORY_WAREHOUSE_EDIT")],
        "delete": [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
        "batch_delete": [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
    },
)

# 主路由：可以在此挂模块前缀和默认依赖
router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[DependPermission])
router.include_router(dept_crud.router)

# api/__init__.py 把 manage / dept / my 三个子 router 汇总到顶层 router
```

业务模块的 `api/__init__.py` 必须导出 `router: APIRouter`，autodiscover 才能挂载到 `/api/v1/business/`。

## 路由顺序：静态优先

`CRUDRouter.router` 是 `_OrderedRouter`，每次 `add_api_route` 后自动重排：不含 `{...}` 的路径排在前面。这保证后挂的 `GET /resources/pages` 不会被先挂的 `GET /resources/{item_id}` 遮蔽。

> 如果你在 router 上手动 `router.routes.append(...)` 绕过 `add_api_route`，排序不会触发——别这么干。

## 相关

- [CRUDBase](./crud.md) — `controller.list / build_search / soft_remove ...`
- [API 约定](./api.md) — 路径 / 方法 / 命名 / 响应
- [Schema 基类](./schema.md) — `PageQueryBase` / `make_optional` / `CommonIds`
- [认证与权限](./auth.md) — `require_buttons` / `require_roles`

## Excel 导入与导出

`just cli-crud`、`just cli-gen-all` 和 `just cli-gen` 生成的业务接口默认配置 Excel 能力；`just cli-gen-web` 生成对应的模板下载、导入和导出操作。现有模块不会自动改写，已生成的模块需要手工接入或在备份并确认自定义代码后重新生成。

简单资源可显式开启：

```python
from app.utils import CRUDRouter, ExcelConfig

crud = CRUDRouter(
    prefix="/customers",
    controller=customer_controller,
    create_schema=CustomerCreate,
    update_schema=CustomerUpdate,
    list_schema=CustomerSearch,
    excel=ExcelConfig(fields=("name", "phone")),
)
```

新增三个接口，保持原有六个 CRUD 接口不变：

| 接口 | 用途 |
| --- | --- |
| `GET /customers/import-template` | 下载只有字段表头的模板 |
| `POST /customers/import` | multipart 上传，字段名为 `file` |
| `POST /customers/export` | 使用列表搜索 Schema 筛选，导出全部匹配记录，忽略当前页码和每页数量 |

模板、导出接口通过 `Success(data={"filename": "...xlsx", "content": "Base64..."})` 返回文件，前端 `ExcelTransfer` 组件配合 `downloadExcel` 下载，沿用统一请求、鉴权和 Token 刷新流程。导入成功返回 `Success(data={"importedCount": N})`，页面刷新第一页。

- 仅支持 `.xlsx`，上传最大 5MB，解压后最大 50MB，单工作表、最多 10000 行；导出最多 10000 条，超限时必须缩小筛选范围，不会静默截断。
- 表头支持 Schema 字段名、camelCase 别名和无歧义的字段标题。推荐直接使用下载模板。空行跳过、空单元格按未提供处理；必填字段仍由创建 Schema 校验。
- 导入只创建记录，不按 ID 覆盖已有记录。先校验整张表，再在模型所在数据库事务中逐条调用 `controller.create`，保留创建审计；唯一键、外键冲突会全部回滚。失败提示行号和字段，不回显单元格数据。
- JSON 字段使用 JSON 文本；日期时间使用 ISO 格式；外键沿用 Sqid 字符串；大整数与 Decimal 以文本保存，避免 Excel 精度丢失。上传中的公式拒绝导入；导出的公式形文本以字符串存储。
- Excel 字段只能来自 `create_schema` 的显式白名单，不能包含 `exclude_fields`；生成器自动排除这些字段。不要将密码、Token 等敏感字段配置到白名单。
- 未开启 `excel` 的现有 CRUD 不会新增任何接口。禁用 `create` 时不注册导入和模板接口；禁用 `list` 时不注册导出接口。

### 权限与自定义流程

生成模块继续使用模块的 API 权限依赖。开启 `--button-auth` 时，还会生成 `B_<MODULE>_<MODEL>_IMPORT` / `EXPORT` 两个按钮及接口依赖：模板与导入共享 IMPORT，导出使用 EXPORT；普通角色需要在角色管理中分别授权 API 和按钮。不会自动为现有角色扩大权限。

手工接入时可以用 `action_dependencies` 配置 `import`、`import_template`、`export`。未显式配置时分别继承 `create`、`create`、`list` 的动作依赖。

默认导出复用搜索配置、排序、`data_policy` 和显式传入的异步 `excel_scope_filter(request) -> Q`。生成器的 `--data-scope` 会为导出生成与列表相同的行级过滤。若自行 override 列表查询，必须同步导出的约束或使用 `@crud.override("export")`，防止越过数据范围。

默认导入只适用于简单 CRUD；它不会调用 `@crud.override("create")` 的 API 函数。涉及密码哈希、业务状态机、缓存失效、事件或跨表写入时，应使用 `@crud.override("import")` 接入相同业务 service，并保留事务与权限校验。用户、角色等系统专用页面未自动开启导入，避免绕过它们已有的业务流程。
