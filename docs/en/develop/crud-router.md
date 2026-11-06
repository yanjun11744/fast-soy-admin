# CRUDRouter

A factory that mass-generates the 6 standard REST routes; pair with [`CRUDBase`](/en/develop/crud) and [API conventions](/en/develop/api). Kills 90% of boilerplate.

Source: `app/core/router.py`.

## Generated routes

| Name | Method + path | Enabled when | Body / Param |
|---|---|---|---|
| `list` | `POST /{prefix}/search` | `list_schema` provided | `list_schema` (with `current/size/orderBy`) |
| `get` | `GET /{prefix}/{item_id}` | always | `item_id: SqidPath` |
| `create` | `POST /{prefix}` | `create_schema` provided | `create_schema` |
| `update` | `PATCH /{prefix}/{item_id}` | `update_schema` provided | `item_id` + `update_schema` |
| `delete` | `DELETE /{prefix}/{item_id}` | always | `item_id` |
| `batch_delete` | `DELETE /{prefix}` | always | `CommonIds` (`{ids: [...]}`) |

`tree_endpoint=True` adds `GET /{prefix}/tree`.

## Minimal example

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
    summary_prefix="Tag",
)
router = tag_crud.router
```

`prefix` must start with a slash (`/tags`); the last segment becomes the resource name in the generated paths.

## Full parameters

```python
CRUDRouter(
    prefix: str,
    controller: CRUDBase,
    create_schema: type[BaseModel] | None = None,
    update_schema: type[BaseModel] | None = None,
    list_schema: type[BaseModel] | None = None,
    search_fields: SearchFieldConfig | None = None,
    summary_prefix: str = "",
    list_order: list[str] | None = None,           # default ["id"]
    exclude_fields: list[str] | None = None,       # to_dict exclusion
    enable_routes: set[str] | None = None,         # default all
    record_transform: Callable | None = None,      # async def transform(obj) -> dict
    soft_delete: bool = False,                     # use controller.soft_remove
    tree_endpoint: bool = False,                   # register GET /tree
    action_dependencies: dict[str, Sequence] | None = None,
)
```

### `search_fields: SearchFieldConfig`

```python
SearchFieldConfig(
    contains_fields=[...],     # __contains
    icontains_fields=[...],    # __icontains
    exact_fields=[...],        # equal
    iexact_fields=[...],       # __iexact
    in_fields=[...],           # __in
    range_fields=[...],        # expects {field}_start / {field}_end on the schema
)
```

See [`build_search`](/en/develop/crud#build_search--auto-build-q-from-a-schema).

### `enable_routes` — disable some routes

```python
crud = CRUDRouter(..., enable_routes={"list", "get"})  # read-only
```

### `record_transform` — custom return shape

Default: `await obj.to_dict(exclude_fields=...)`. To preload relations or compose fields:

```python
async def transform(obj: Product) -> dict:
    d = await obj.to_dict()
    await obj.fetch_related("warehouse")
    d["warehouseName"] = obj.warehouse.name
    return d

CRUDRouter(..., record_transform=transform)
```

> Recommended only for small field-composition cases. For N+1 optimization (`select_related` / `prefetch_related`) use `@override("list")` directly.

### `soft_delete` — soft delete

Requires the model to inherit `SoftDeleteMixin`.

```python
CRUDRouter(..., soft_delete=True)
# delete       → controller.soft_remove
# batch_delete → controller.soft_batch_remove
```

### `tree_endpoint` — tree

Requires the model to have `parent_id` (recommended via `TreeMixin`). The generated `GET /resources/tree` uses `_build_nested_tree(records, parent_id_key="parentId", root_value=0)`.

### `action_dependencies` — per-route dependencies

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

**Critical**: `action_dependencies` apply to `@override("create")`-replaced routes too — customization can't accidentally drop the permission check.

## Customize a route: `@crud.override`

To customize, **don't** redeclare `@router.post("/users")` — `_OrderedRouter`'s sort will hit the default route. Use:

```python
@user_crud.override("create")
async def _create_user(user_in: UserCreate, request: Request):
    ...
    return Success(...)
```

`override` does three things:

1. Removes the default route (matched by path + methods)
2. Registers your function on the same path / methods / summary
3. Auto-mounts `action_dependencies[name]`

Standard signatures (or call `crud.get_route_info("create")`):

```text
list:         async def list_items(obj_in: <list_schema>)
get:          async def get_item(item_id: SqidPath)
create:       async def create_item(obj_in: <create_schema>)
update:       async def update_item(item_id: SqidPath, obj_in: <update_schema>)
delete:       async def delete_item(item_id: SqidPath)
batch_delete: async def batch_delete(obj_in: CommonIds)
```

Parameters can be **freely extended** (FastAPI dependency semantics):

```python
@user_crud.override("update")
async def _update(item_id: SqidPath, obj_in: UserUpdate, request: Request):
    redis = request.app.state.redis
    ...
```

::: warning Omit a schema and the route isn't generated
If `product_crud` doesn't pass `create_schema`, no `POST /products` is registered. That's intentional — it lets you hand-write `@router.post("/products")` without conflict. Inventory's product create uses this pattern.
:::

## Mount extra endpoints on the router

`crud.router` is a regular `APIRouter`; mount anything beyond the standard 6:

```python
router = dept_crud.router

@router.post("/warehouses/{dept_id}/products", summary="Bulk assign products")
async def assign_products(dept_id: SqidPath, body: AssignProducts):
    ...
    return Success(...)
```

## Wiring template for a business module

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
    summary_prefix="Warehouse",
    soft_delete=True,
    tree_endpoint=True,
    action_dependencies={
        "create": [require_buttons("B_INVENTORY_WAREHOUSE_CREATE")],
        "update": [require_buttons("B_INVENTORY_WAREHOUSE_EDIT")],
        "delete": [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
        "batch_delete": [require_buttons("B_INVENTORY_WAREHOUSE_DELETE")],
    },
)

# Top router: module prefix + default deps here
router = APIRouter(prefix="/inventory", tags=["inventory"], dependencies=[DependPermission])
router.include_router(dept_crud.router)

# api/__init__.py aggregates manage / dept / my sub-routers into the top router
```

The module's `api/__init__.py` must export `router: APIRouter` for autodiscover to mount it under `/api/v1/business/`.

## Static-path priority

`CRUDRouter.router` is an `_OrderedRouter` — every `add_api_route` re-sorts so non-`{...}` paths come first. This guarantees later-mounted `GET /resources/pages` isn't shadowed by an earlier `GET /resources/{item_id}`.

> If you `router.routes.append(...)` directly, the sort doesn't run — don't.

## See also

- [CRUDBase](/en/develop/crud)
- [API conventions](/en/develop/api)
- [Schema base](/en/develop/schema)
- [Auth](/en/develop/auth) — `require_buttons` / `require_roles`

## Excel titles, exact aliases and import preview

### Parent and child exports

When both models are selected for generation (for example `--models Order,OrderLine`), the generator detects same-module foreign keys and one-to-one child relationships and adds `ExcelConfig.details`. Multiple direct children are supported; self-relations, cross-module references, many-to-many relations and plain integer IDs are not inferred. Children must have a list route and exportable fields.

Generated parent exports first ask which parent fields to repeat on each child row. The workbook keeps the full `Data` parent sheet and adds a sheet per direct child, grouped in parent export order and using the child's configured order within each group. Parent columns have the `父表：` prefix to distinguish duplicate child titles. Empty results keep their headers.

`POST /resources/export` accepts `parentFields?: string[] | null` using internal field names from the parent Excel allowlist. Omitted or `null` includes all parent export fields; `[]` includes none. Unknown, excluded and duplicate names are rejected. This changes only child sheets, not the main sheet or import template. Each sheet is limited to 10000 rows and 200 combined parent/child columns; oversized exports fail rather than truncate.

Existing modules can opt in with `ExcelConfig(fields=("order_no",), details=(ExcelDetail(sheet_name="Lines", resource=lambda: order_line_crud, parent_field="order_id"),))`. Import `ExcelDetail` from `app.utils`. The lazy child `CRUDRouter` reference permits either declaration order. On `ExcelTransfer`, supply `export-parent-fields` as `{ name, label }[]`, `export-api="parentFields => fetchExportOrder({ ...searchParams, parentFields })"`, and `export-selected-api="(ids, parentFields) => fetchExportOrder({ ...searchParams, ids, parentFields })"`.

Child rows are limited to the exported parent IDs and reuse the child's Excel allowlist, excluded fields, data policy, export scope filter, configured default manager (including soft deletion) and record transform. Parent export permission grants access to the explicitly declared child exports; grant it accordingly. Custom list constraints must also be applied through `excel_scope_filter`; custom export overrides are not invoked. Combined generation shares the backend exclusions; standalone `gen-web` accepts `--exclude-fields Order:secret` to match the backend.

This adds read-only child export, not aggregate import. To import the parent sheet back, select `Data` in the import preview. Existing generated modules are not overwritten automatically; preserve custom business logic when adopting this feature.

`POST /customers/export` accepts the list search fields plus optional `ids: SqidId[]`. Omitted or `null` IDs export all matching records. An array exports the intersection of selected IDs, search filters, `data_policy` and `excel_scope_filter`, preserving list order and ignoring pagination. Empty arrays, invalid IDs and arrays exceeding 10000 IDs are rejected; duplicate IDs do not duplicate rows. Deleted or inaccessible records are excluded.

Generated pages provide an export dropdown with “Export filtered results” and “Export selected (N)”; selection export is disabled when nothing is checked. Existing pages can pass `:selected-ids="checkedRowKeys"` and `:export-selected-api="ids => fetchExportCustomer({ ...searchParams, ids })"` to `ExcelTransfer`, and extend the service parameter type to `SearchParams & { ids?: string[] }`. Without `export-selected-api`, the original single export button remains. Selection follows the table's existing behavior; no cross-page select-all is added.

Enable Excel for simple resources with `excel=ExcelConfig(fields=("name", "phone"))`. Templates and exports use `ExcelColumn.title`, then the create Schema's `Field(title=...)`, then the field name. Original field names remain accepted on import.

```python
from app.utils import ExcelColumn, ExcelConfig

excel = ExcelConfig(
    fields=("name", "phone"),
    columns={
        "name": ExcelColumn(aliases=("Customer Name",)),
        "phone": ExcelColumn(title="Phone number", aliases=("Mobile", "联系电话")),
    },
)
```

Headers match field names, Schema aliases/titles, Excel titles and explicit aliases literally. Case, spaces, line breaks and full-width characters are significant; no fuzzy matching or normalization is performed. Conflicting labels across fields fail at router initialization. Excel aliases do not change JSON API aliases.

| Endpoint | Behavior |
| --- | --- |
| `GET /customers/import-template` | Download the template |
| `POST /customers/import-preview` | Detect columns and validate the sheet without database writes |
| `POST /customers/import` | Revalidate the file and create records in one transaction |
| `POST /customers/export` | Export matching records with list filters and configured data scope |

Preview and import accept multipart `file` and an optional JSON string named `options`:

```json
{"sheet":"Customers","headerRow":3,"columns":["name","phone",null]}
```

`sheet` is required for workbooks with multiple sheets. `headerRow` is a 1-based row number within the first 100 rows; omit it to detect a unique candidate based on exact required-field matches and total field matches. `columns` maps each source column to a whitelisted internal field name, with `null` explicitly ignoring a column. Unknown columns are ignored by default and can be mapped manually in the preview. Duplicate target fields and missing required fields still block import.

The preview includes sheet names, selected header row, target fields, the first three samples per column (up to 120 characters per sample), nonempty row count and up to 20 errors. Generated pages connect `ExcelTransfer.previewApi` automatically. Existing pages need a preview service and the `preview-api` prop; without it they retain direct import. Any selection or mapping change requires revalidation before confirmation. Confirmation uploads and parses the file again; no temporary upload storage is used.

Only `.xlsx` is supported: 5MB compressed, 50MB uncompressed, at most 200 columns and 10,000 row positions after the selected header. Formula cells are rejected, including ignored columns. Blank cells are treated as missing. Dates, JSON, enums and Sqid foreign keys keep their existing formats; dictionary translation, name-to-ID resolution, `.xls`, CSV and multi-level headers are not included.

The preview validates the Schema without invoking `controller.create`; database constraints and business creation failures can still occur during confirmation and roll back the whole import. Errors refer to physical worksheet row numbers without echoing invalid cell values. Complex creation flows should override `import` and use their business service.

Import defaults to the create action dependencies; preview and template default to the import action dependencies; export defaults to list. The new preview API still needs API permission grants for ordinary roles. No role seeds or existing grants are changed. Export keeps configured list filters, `data_policy` and `excel_scope_filter`; custom list overrides must apply equivalent export constraints.
