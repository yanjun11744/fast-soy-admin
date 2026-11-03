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

新增四个接口，保持原有六个 CRUD 接口不变：

| 接口 | 用途 |
| --- | --- |
| `GET /customers/import-template` | 下载只有字段表头的模板 |
| `POST /customers/import-preview` | 只读识别、字段映射和整表校验，不写入数据库 |
| `POST /customers/import` | multipart 上传，字段名为 `file`；提交时重新校验 |
| `POST /customers/export` | 使用列表搜索条件筛选；可附加 `ids` 导出所选记录，忽略当前页码和每页数量 |

模板、导出接口通过 `Success(data={"filename": "...xlsx", "content": "Base64..."})` 返回文件，前端 `ExcelTransfer` 组件配合 `downloadExcel` 下载，沿用统一请求、鉴权和 Token 刷新流程。导入成功返回 `Success(data={"importedCount": N})`，页面刷新第一页。

导出请求沿用搜索字段，额外支持 `ids?: SqidId[]`：省略或传 `null` 导出全部匹配记录；传数组时仅导出所选 ID 与当前筛选、`data_policy`、`excel_scope_filter` 的交集。空数组、非法 ID 或超过 10000 个 ID 均拒绝，不会回退为全量导出。所选记录仍按列表排序，重复 ID 不会重复导出，已删除或不可见记录不会出现在结果中。

新生成页面的“导出 Excel”下拉菜单提供“导出筛选结果”和“导出所选（N 条）”，未勾选时禁用后者。已有页面可按下面接入，service 的导出参数类型扩展为 `SearchParams & { ids?: string[] }`；不传 `export-selected-api` 的旧页面保留原单按钮。选择范围沿用表格现有行为，不额外实现跨页全选。

```vue
<ExcelTransfer
  :export-api="() => fetchExportCustomer(searchParams)"
  :export-selected-api="ids => fetchExportCustomer({ ...searchParams, ids })"
  :selected-ids="checkedRowKeys"
  :import-api="fetchImportCustomer"
  :template-api="fetchCustomerImportTemplate"
/>
```

- 仅支持 `.xlsx`，上传最大 5MB，解压后最大 50MB，每次选择一个工作表、表头后最多 10000 行、最多 200 列；导出最多 10000 条，超限时必须缩小筛选范围，不会静默截断。
- 模板与导出表头优先使用 `ExcelColumn.title`，其次使用 Schema `Field(title=...)`，最后回退字段名；现有英文表头仍可导入。
- 导入表头只与字段名、Schema alias、Schema title、Excel title 和显式别名精确匹配。不去空格、不忽略大小写、不转换全半角、不做模糊推荐。不同字段的名称或别名冲突时，路由初始化直接报错。
- 自动扫描前 100 行，通过必填字段命中数和全部字段命中数识别唯一表头候选；不能唯一确定时必须指定 `headerRow`。多工作表必须选择 `sheet`，不会自动合并。
- 空行跳过、空单元格按未提供处理；必填字段仍由创建 Schema 校验。未精确匹配的列默认忽略，也可在预览中手动指定目标字段；多列映射到同一个字段时阻止导入。
- 默认导入只创建记录，不按 ID 覆盖已有记录。先校验整张表，再在模型所在数据库事务中逐条调用 `controller.create`，保留创建审计；唯一键、外键冲突会全部回滚。失败提示行号和字段，不回显单元格数据。
- 可通过 `ExcelConfig(update_key="order_no", fields=(...))` 按唯一业务字段更新或新增。匹配字段必须是配置内的创建 Schema 必填字段，且模型字段唯一、非空、非主键；必须启用更新路由并提供覆盖导入字段的更新 Schema。订单已按订单号启用；其他模块默认仍只新增。匹配成功调用 `controller.update`，保留 ID、创建时间和创建人；空单元格或未映射字段不覆盖原值，`0` 等非空值正常更新。仍需提供原创建模板的全部必填字段，同文件重复匹配键按行顺序更新，后行提供的值生效；任何写入失败都回滚整批新增和更新。成功返回的 `importedCount` 是处理行数，包含新增和更新，继续沿用导入接口权限。
- JSON 字段使用 JSON 文本；日期时间使用 ISO 格式；外键沿用 Sqid 字符串；大整数与 Decimal 以文本保存，避免 Excel 精度丢失。上传中的公式拒绝导入；导出的公式形文本以字符串存储。
- Excel 字段只能来自 `create_schema` 的显式白名单，不能包含 `exclude_fields`；生成器自动排除这些字段。不要将密码、Token 等敏感字段配置到白名单。
- 未开启 `excel` 的现有 CRUD 不会新增任何接口。禁用 `create` 时不注册导入、预览和模板接口；禁用 `list` 时不注册导出接口。

### 中文表头与精确别名

通常只需在创建 Schema 中设置 `Field(title="客户名称")`。额外名称在 Excel 配置中声明，不改变 JSON API 的 alias：

```python
from app.utils import ExcelColumn, ExcelConfig

excel = ExcelConfig(
    fields=("name", "phone"),
    columns={
        "name": ExcelColumn(aliases=("客户姓名", "Customer Name")),
        "phone": ExcelColumn(title="手机号码", aliases=("联系电话", "Phone")),
    },
)
```

`Phone` 不会匹配 `phone ` 或 `PHONE`。同一字段重复声明同一个名称允许，不同字段占用相同名称会报错。`columns` 的键必须属于 `fields` 白名单。

### 预览与确认导入

新生成的前端页面已经接好 `previewApi`。已生成页面需更新 service，并为 `ExcelTransfer` 传入 `:preview-api="fetchPreviewImportCustomer"`；未提供此属性的旧页面仍沿用直接导入。

预览与提交均接收 multipart `file`，以及可选的 `options` JSON 字符串：

```json
{"sheet":"客户清单","headerRow":3,"columns":["name","phone",null]}
```

- `sheet`：工作表的准确名称；单工作表可省略。
- `headerRow`：1–100 的实际表头行号；省略时自动识别。
- `columns`：按原始列顺序提供内部字段名，`null` 表示用户明确忽略此列；省略时按精确别名识别，未匹配列默认忽略。必须与表头列数一致，不能使用白名单之外的字段。

预览返回工作表、表头行、目标字段、每列前 3 条样例（每格最多 120 字符）、非空行数和最多 20 条错误。修改映射后必须重新校验才能确认导入。文件在确认时重新上传并完整解析，不保存临时文件、不信任前端预览结果；错误使用实际工作表行号。

预览只校验表格和 Schema，不执行 `controller.create`，因此数据库唯一键、外键或业务创建流程仍可能在最终提交时报错并回滚。日期、枚举和外键仍遵循原有格式；本次不加入字典值翻译或名称转 ID，也不扩展 `.xls`、CSV、多级合并表头。

### 权限与自定义流程

生成模块继续使用模块的 API 权限依赖。开启 `--button-auth` 时，还会生成 `B_<MODULE>_<MODEL>_IMPORT` / `EXPORT` 两个按钮及接口依赖：预览、模板与导入共享 IMPORT，导出使用 EXPORT；普通角色需要在角色管理中分别授权 API 和按钮。不会自动为现有角色扩大权限。

手工接入时可以用 `action_dependencies` 配置 `import`、`import_preview`、`import_template`、`export`。导入默认继承 `create`；预览与模板默认继承 `import`；导出默认继承 `list`。新预览路由仍需给普通角色授权对应 API，不会自动扩大现有角色权限。

默认导出复用搜索配置、排序、`data_policy` 和显式传入的异步 `excel_scope_filter(request) -> Q`。生成器的 `--data-scope` 会为导出生成与列表相同的行级过滤。若自行 override 列表查询，必须同步导出的约束或使用 `@crud.override("export")`，防止越过数据范围。

默认导入只适用于简单 CRUD；它不会调用 `@crud.override("create")` 的 API 函数。涉及密码哈希、业务状态机、缓存失效、事件或跨表写入时，应使用 `@crud.override("import")` 接入相同业务 service，并保留事务与权限校验。用户、角色等系统专用页面未自动开启导入，避免绕过它们已有的业务流程。
