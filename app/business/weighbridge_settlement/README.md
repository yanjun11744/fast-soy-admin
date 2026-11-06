# 磅单结算

继续使用本模块自动发现和 API 权限机制。工序价格使用原 CRUD；磅单作为主从表整体保存，所有写入由 `services.py` 处理。

## 数据与计算

- 磅单新增可选 `images` 字段，保存最多 5 张系统上传图片的相对 URL，旧记录为 `NULL`。新增、编辑支持上传和移除引用，列表显示缩略图，详情支持放大预览；上传中禁止提交，已结算磅单继续只读。旧客户端更新时省略 `images` 会保留原图片，显式传 `[]` 或 `null` 可清空。上传沿用 `B_SYSTEM_UPLOAD_CREATE` 权限，普通角色需由管理员授予现有上传权限；不修改权限种子。图片沿用系统公开图片存储机制。
- 关联订单通过注册的 `app_system.Order` 查询；不修改或自动创建正式订单。
- 手动明细 `order_id=NULL`，项目号、名称、单重、实际数量必填。
- 保存明细顺序为请求数组顺序，后端生成从 1 开始的 `position`。保留已有明细 ID，差异删除、新增、更新均在一个事务中。
- 更新请求必须携带 `revision`；未携带 `rateId` 时保留工序名称与价格快照，显式携带时读取当前启用工序价格。未更换订单的既有明细继续使用历史订单快照。
- 重量与金额使用 Decimal、ROUND_HALF_UP。末行承担余差；极小重量和多明细场景下，中间行分摊上限为剩余量，避免末行负数。
- 详情锁定主表后读取数据库明细，避免并发保存期间读到不同版本的主从表。
- 结算会校验明细及合计，并递增 revision；已结算主从表禁止更新和删除。
- 磅单单表 Excel 导入已关闭，防止绕过明细和快照校验；工序价格 Excel 功能及磅单只读导出保留。
- 磅单筛选/勾选导出在原 `Data` 主表之外增加“订单明细”工作表，每行包含磅单编号、明细顺序、订单号、项目号、名称、净重、毛重、实际过磅数量及结算数据。关联订单和手动明细均导出保存时的快照，不读取当前订单资料；筛选条件与勾选 ID 取交集，导出不受当前分页限制。主表、明细各最多 10000 行，超限会提示缩小筛选范围，不截断明细。
- 结算接口中的 Decimal 以字符串返回，保持精度；前端预览调用后端试算接口，最终保存仍重新计算。

## 接口

下列路径统一前缀 `/api/v1/business/weighbridge_settlement`，需要现有 API 权限。新增端点需要通过项目 API 刷新机制发现，并在角色管理中授予相应权限；本次不修改角色、菜单或按钮种子。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/settlement_rates/options` | 启用工序与价格 |
| POST | `/weighing_tickets/order-options` | 项目号搜索，精确匹配优先，最多 50 条 |
| POST | `/weighing_tickets/preview` | Decimal 试算 |
| POST | `/weighing_tickets/search` | 原生成列表查询 |
| POST | `/weighing_tickets/export` | 导出磅单及对应订单明细（筛选或所选记录） |
| GET | `/weighing_tickets/{id}` | 磅单及按 position 排序的全部明细 |
| POST | `/weighing_tickets` | 事务创建主从表 |
| PATCH | `/weighing_tickets/{id}` | 完整聚合更新，revision 必填 |
| POST | `/weighing_tickets/{id}/settle` | 确认结算，revision 必填 |
| DELETE | `/weighing_tickets/{id}` | 删除未结算磅单 |
| DELETE | `/weighing_tickets` | 整体事务删除未结算磅单，任一已结算则全部拒绝 |

对外所有资源 ID 均使用 Sqids。禁止客户端提交 price、process、totalAmount、isSettled 等服务端计算或控制的字段。

## 迁移

图片字段迁移由 `just makemigrations` 自动生成于 `migrations/app_system/0007_auto_20261106_1815.py`，仅执行 `ALTER TABLE "biz_settlement_ticket" ADD COLUMN "images" JSONB;`，字段可空、保留已有磅单。需按根 AGENTS.md 在 SQL 审阅确认后执行 `just migrate`，再使用新版本接口。

本次已按用户确认对当前配置的开发数据库应用 0007 迁移；其他环境仍需单独应用。

自动生成 `migrations/app_system/0004_auto_20261101_1059.py`，仅执行：

```sql
ALTER TABLE "biz_settlement_line" ALTER COLUMN "order_id" DROP NOT NULL;
ALTER TABLE "biz_settlement_line" ALTER COLUMN "order_no" DROP NOT NULL;
```

保留已有记录、外键、索引和唯一约束。按根 AGENTS.md 要求，审阅 SQL 并确认目标数据库后执行 `just migrate`；迁移前不能向旧 NOT NULL 表写入手动明细。

## 验证

后端测试 `tests/test_weighbridge_settlement.py` 使用隔离的 SQLite 内存数据库，不读取或写入现有业务数据。覆盖 Decimal 余差、混合录入、数据库回显、差异更新、历史快照、事务回滚、并发 revision 冲突、写权限和结算锁定。

前端测试 `modules/__tests__/settlement-editor.test.ts` 覆盖打开编辑保留原价、主动重新选择工序、已结算只读、搜索防抖、同项目号多候选及实际数量独立输入。

已按用户确认在当前 PostgreSQL 数据库应用 0004 迁移，并核对两个字段均可空。仍需通过浏览器完成新增、刷新详情、编辑与确认结算的端到端验收。

## 本次交付文件

- `models.py`：手动明细可空订单关系、可空订单号。
- `schemas.py`：聚合输入、详情输出、乐观锁、试算及搜索参数；工序价格校验。
- `calculation.py`（新增）：Decimal 分摊及余差、存储范围校验。
- `services.py`：快照读取、完整详情、事务差异保存、结算及删除保护、订单查询。
- `api/manage.py`：沿用生成列表及工序 CRUD，磅单写接口接入业务 Service。
- `migrations/app_system/0004_auto_20261101_1059.py`（新增）：两个字段可空迁移。
- `tests/test_weighbridge_settlement.py`（新增）：后端结算验收测试。
- `web/src/views/weighbridge-settlement/weighing-ticket/index.vue`：详情、结算、锁定操作及只读导出。
- `web/src/views/weighbridge-settlement/weighing-ticket/modules/weighing-ticket-operate-drawer.vue`：主从表编辑、快照展示、试算及详情加载。
- 同目录 `weighing-line-editor.vue`、`weighing-line-table.vue`（新增）：搜索与手动录入、详情明细表。
- 同目录 `__tests__/settlement-editor.test.ts`（新增）：前端交互验收测试。
- `web/src/views/weighbridge-settlement/settlement-rate/modules/settlement-rate-operate-drawer.vue`：招采价格四位小数及默认启用。
- `web/src/service/api/weighbridge_settlement-manage.ts`、`web/src/typings/api/weighbridge_settlement-manage.d.ts`：聚合 API 和精确 Decimal 字符串类型。
- `web/src/locales/langs/_generated/weighbridge_settlement/{zh-cn.ts,en-us.ts,types.d.ts}`：中英交互文案和类型。
- `web/{eslint.config.js,.oxlintrc.json,.oxfmtrc.json}`：忽略 AppleDouble 和构建输出。

没有删除文件，没有修改订单模块、系统权限逻辑、角色种子或既有业务数据。

## 本次实际检查结果

- `just dbhistory`、`just makemigrations`：成功，自动生成 0004。
- `uv run tortoise sqlmigrate app_system 0004_auto_20261101_1059`：已检查 SQL，仅两个 DROP NOT NULL。
- 迁移前 `uv run tortoise migrate --dry-run`：仅 0004 待应用，0 回滚。
- 用户确认后执行 `just migrate`：0004 应用成功；随后 dry-run 显示 `No migrations to apply`。
- 只读查询 PostgreSQL `information_schema.columns`：`biz_settlement_line.order_id`、`order_no` 均为 `is_nullable=YES`，未读取业务记录。
- `just fmt`：执行过，并清理了格式化工具带出的无关文件变化。
- `just check frontend`：通过，含 lint、格式化、类型检查及 39 项测试。
- `just build frontend`：生产构建通过。
- 清理无关变化后重新执行 `just lint frontend`、`just typecheck frontend`、`just test frontend`：均通过。
- `uv run basedpyright app/business/weighbridge_settlement`：0 错误、0 警告。
- 后端结算专项：11 项通过。项目命令不支持指定测试文件，因此通过 `PYTEST_ADDOPTS` 选择结算测试并排除无法收集的既有 CLI 测试。
- 后端扩展回归：排除三个无法收集的 CLI 测试文件后，210 项通过，1 项 Radar 测试因沙箱禁止 `sysctl()` 失败。
- `just check` 未全绿：后端类型门禁存在既有 CLI 路径问题（`app.cli` 缺失，实际文件位于 `app/business/cli`，共 63 个相关类型错误）。原始后端全套测试同样有 3 个测试文件无法收集。
- `just check-boundaries` 被同一 CLI 问题阻断；另加载原边界检查器，对结算模块源码执行检查通过，扫描时排除了 `._*`。
- `git diff --check`：通过。

所有 uv 命令均使用可写临时缓存 `UV_CACHE_DIR=/private/tmp/fast-soy-uv`。后端自动化测试使用隔离内存数据库；未执行真实浏览器端到端验收。
