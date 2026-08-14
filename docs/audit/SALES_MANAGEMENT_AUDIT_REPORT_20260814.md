# 销售管理模块专项审计报告

- 审计日期：2026-08-14
- 审计范围：`app/routes/sales.py`（1894 行）、`app/routes/out_order.py`（销售出库完成路径）、`app/app.py` 中 `SalesOrder`/`SalesOrderItem` 模型与 `sync_sales_order_shipment`/`recalculate_sales_order`/`build_sales_outbound_draft`、销售模板与静态 JS
- 审计维度：数据一致性、仓库与库位必填、删除保护与状态机、权限与 CSRF、导出与打印字段完整性、SQL 注入与 XSS
- 对照基线：`AGENTS.md` 仓库与库位必填规则、A1-A10 防 BUG 规则、`PURCHASE_MANAGEMENT_AUDIT_REPORT_20260814.md` 同类修复模式

## 一、审计结论概览

| 维度 | 结论 |
|---|---|
| 权限与 CSRF | ✅ 基本合规：12 个 POST/PUT/DELETE 路由均带 `@require_role` + `@login_required`，无 CSRF 裸露 |
| SQL 注入 | ✅ 无注入面：全部 ORM 参数化，`f'%{var}%'` 仅构造 LIKE 通配符参数值 |
| XSS | ✅ 模板转义规范：`innerHTML` 均经 `esc/escAttr/escapeHtml`；`|tojson|safe` 为正确惯用法 |
| 数据一致性 | ❌ 1 个 P0 + 5 个 P1：状态机可被出库完成"复活"已取消订单；并发下推缺写锁；`shipped_quantity` 非原子回写；超量出库；编辑丢链 |
| 仓库必填 | ❌ 系统性违规：16 个报表/导出路由把仓库当可选筛选，未传时返回全仓数据；出库完成缺 active 复核（PUR-AUDIT-003 同类问题） |
| 删除/状态机 | ❌ cancel 不检查 pending 出库草稿；delete 不检查 OutOrder 引用 |
| 导出字段完整性 | ❌ 4 个导出 + 1 个打印模板缺「合同单号」「工程名称」字段，与列表页/详情页不一致 |

最高优先级：**P0-1 + P1-1 组合**构成确定性数据损坏链——"确认→下推草稿→取消订单→完成草稿"即可让 cancelled 订单被静默复活并扣减库存，必须先修。

---

## 二、问题清单（按严重级别）

### P0 阻断

#### SALES-AUDIT-001 `recalculate_sales_order` 无条件覆盖 `cancelled` 状态，已取消销售订单可被出库完成"复活"

- **文件**：[app/app.py:28803-28812](file:///workspace/app/app.py#L28803-L28812)
- **根因**：
  ```python
  if total_quantity <= 0 or shipped_total_qty <= 0:
      order.shipment_status = 'pending'
      if order.status not in ('draft', 'cancelled'):   # 只有本分支保护 cancelled
          order.status = 'confirmed'
  elif shipped_total_qty + STOCK_COMPARE_EPSILON >= total_quantity:
      order.shipment_status = 'shipped'
      order.status = 'closed'                          # 无条件覆盖
  else:
      order.shipment_status = 'partial'
      order.status = 'confirmed'                       # 无条件覆盖
  ```
  `partial`/`shipped` 两个分支直接写死 `confirmed`/`closed`，未做 `if order.status != 'cancelled'` 守卫。
- **触发链（确定性，无需并发）**：
  1. 确认销售订单 → `confirmed`
  2. 下推生成出库草稿 → OutOrder `pending`，此时 `shipped_quantity=0`
  3. 取消销售订单 → 因 `shipped_quantity=0` 通过校验 → `status='cancelled'`
  4. 完成 OutOrder → `sync_sales_order_shipment` 写 `shipped_quantity>0` → `recalculate_sales_order` 走 `partial`/`shipped` 分支 → **`cancelled` 被改回 `confirmed`/`closed`**
- **后果**：取消操作被静默撤销，库存已真实扣减。违反 AGENTS.md「取消是人工动作」边界，破坏状态机。
- **修复建议**：`partial`/`shipped` 分支同样加 `if order.status != 'cancelled'` 守卫；`sync_sales_order_shipment` 入口 `if order and order.status == 'cancelled': return None` 防御纵深。

---

### P1 严重

#### SALES-AUDIT-002 `cancel_sales_order` 不检查已存在的 pending 销售出库草稿

- **文件**：[app/routes/sales.py:1058-1067](file:///workspace/app/routes/sales.py#L1058-L1067)
- **根因**：仅校验 `order.status in ('draft','confirmed')` 与 `any(item.shipped_quantity > EPSILON)`，**不查询** `OutOrder(source_sales_order_id=order.id, status='pending')`。对比同文件 `create_sales_outbound_from_selection` 在 `sales.py:368-373` 明确做了 pending 草稿检查，cancel 却没有。
- **后果**：confirmed 订单已有 pending 出库草稿时仍可被取消，留下指向 cancelled 订单的孤儿草稿；该草稿一旦完成即触发 SALES-AUDIT-001 复活。
- **修复建议**：cancel 前增加 `OutOrder.query.filter_by(source_sales_order_id=order.id, status='pending').first()` 检查，存在则拒绝取消（提示先处理出库草稿）。

#### SALES-AUDIT-003 `create_sales_outbound_draft` / `batch_create_sales_outbound` 未加写锁，并发可生成重复草稿导致超扣

- **文件**：[app/routes/sales.py:675-717](file:///workspace/app/routes/sales.py#L675-L717)（`create_sales_outbound_draft`，`SalesOrder.query...get_or_404` 无 `with_for_update`）、[sales.py:756-789](file:///workspace/app/routes/sales.py#L756-L789)（`batch_create_sales_outbound`，无锁）；去重逻辑在 [app/app.py:28852-28860](file:///workspace/app/app.py#L28852-L28860)（`build_sales_outbound_draft` 用普通 SELECT 做 pending 去重）
- **根因**：`build_sales_outbound_draft` 的 pending 去重是 check-then-act，外层两个路由都没有 `_acquire_order_write_lock` 或 `with_for_update`。两个并发事务都读到无 pending 草稿 → 都 insert → 同一销售订单出现两张草稿，数量之和可超订单剩余。对照 `create_sales_outbound_from_selection`（`sales.py:337-348`）对 SQLite 用 `BEGIN IMMEDIATE`、对其它库用 `with_for_update()` 串行化，另两个路径没有等价保护。
- **后果**：两张草稿各自完成后，`deduct_stock_atomic` 原子扣了两份库存（正确扣减），但 `shipped_quantity` 被 `recalculate_sales_order` 的 `min(..., qty)` 截断到订单数量，超扣部分在销售单上不可见 → 库存账实不一致。
- **修复建议**：两个路由在调用 `build_sales_outbound_draft` 前用 `_acquire_order_write_lock(SalesOrder, id, ('confirmed','closed'), selectinload(SalesOrder.items))` 加锁并重读状态；或在 `OutOrder` 上加 `(source_sales_order_id, status)` 唯一约束从 DB 层兜底。

#### SALES-AUDIT-004 `sync_sales_order_shipment` 对 `shipped_quantity` 用非原子 read-modify-write，并发完成同一销售订单的多张出库单会丢失更新

- **文件**：[app/app.py:28844](file:///workspace/app/app.py#L28844)
- **根因**：
  ```python
  sales_item.shipped_quantity = max(0, (sales_item.shipped_quantity or 0) + quantity_sign * (outbound_item.quantity or 0))
  ```
  Python 层读-改-写，非条件 UPDATE。`complete_out_order`（`out_order.py:659`）只对 `OutOrder` 加 `_acquire_order_write_lock`，**未锁 SalesOrder/SalesOrderItem**。两张引用同一销售订单的 OutOrder 并发完成时，两者都读到同一 `shipped_quantity` 旧值 → 后提交者覆盖前者（lost update）。
- **后果**：库存原子扣了 2 份（`deduct_stock_atomic` 是条件 UPDATE，正确），但 `shipped_quantity` 只累加了 1 份 → 销售单执行进度低于实际出库量。
- **修复建议**：改为原子条件 UPDATE（类似 `deduct_stock_atomic` 的 `sa_update(SalesOrderItem).where(id==...).values(shipped_quantity=shipped_quantity+delta)`），或在 `complete_out_order` 内对关联 `SalesOrderItem` 行 `with_for_update`。

#### SALES-AUDIT-005 出库单编辑重建明细时丢失 `source_sales_order_item_id`，破坏发货回写链路

- **文件**：[app/routes/out_order.py:412-440](file:///workspace/app/routes/out_order.py#L412-L440)（`add_out_order` 编辑分支）
- **根因**：编辑 pending 出库单时先 `db.session.delete(item)` 全删，再从 `submitted_items` 重建 `OutOrderItem`，重建字段只有 `material_id/quantity/price/amount/remark/contract_id/...`，**不含 `source_sales_order_item_id`**。
- **后果**：编辑后的出库单在 `sync_sales_order_shipment` 里 `outbound_item.source_sales_order_item_id` 为 None，退化为按 `material_id` 在 `items_by_material` 模糊匹配；同一销售订单存在多条同物料明细时，`len(candidates)==1` 不成立 → 跳过回写 → `shipped_quantity` 漏更新。
- **修复建议**：编辑重建时从前端回传或从原明细保留 `source_sales_order_item_id`；并在重建后校验该字段非空。

#### SALES-AUDIT-006 `complete_out_order` 不校验出库数量 ≤ 销售订单未发货数量，叠加编辑路径允许超量出库

- **文件**：[app/routes/out_order.py:679-706](file:///workspace/app/routes/out_order.py#L679-L706)（`complete_out_order` 循环只 `deduct_stock_atomic`，无 remaining 校验）；编辑无校验在 `out_order.py:417-440`
- **根因**：草稿生成阶段有数量校验（`build_sales_outbound_draft` 在 `app.py:28879-28881` 校验 `quantity - remaining <= EPSILON`；选单路径 `sales.py:365-367` 同样校验），但 `complete_out_order` 完成时**不重新校验**。编辑出库草稿可任意改大数量且不校验。`recalculate_sales_order` 又用 `min(max(...,0), qty)` 截断到订单数量，**掩盖**超发。
- **后果**：通过"生成小数量草稿 → 编辑改大数量 → 完成"可超量出库；库存按实际出库量扣减，但销售单 `shipped_quantity` 被截断到订单量，超发部分库存无任何单据对应。
- **修复建议**：`complete_out_order` 在扣库存前对每条 `source_sales_order_item_id` 校验 `outbound_item.quantity ≤ remaining`，超量则拒绝；编辑出库单时同样校验。

---

### P1 仓库规则违规

#### SALES-AUDIT-007 报表类路由系统性未将仓库作为必填筛选条件（违反 AGENTS.md 报表规则）

- **文件**：[app/routes/sales.py](file:///workspace/app/routes/sales.py) 多个路由
- **规则依据**：AGENTS.md「库存查询、出入库报表、库存台账的查询入口必须将仓库作为必填条件，后端未收到仓库参数时返回空结果或 400」
- **现状**：销售模块**全部报表/导出路由**把仓库当可选筛选，未传时返回**全仓库**数据，无一合规：

| 路由 | 行号 | 现状 |
|---|---|---|
| `sales_outflow_report` | 1493-1580 | `selected_warehouse` 为空则不 filter，返回全部出库 |
| `export_sales_outflow_report` | 1582-1657 | 同上 |
| `sales_trend_report` | 1659-1705 | 为空则返回全部订单 |
| `export_sales_trend_report` | 1707-1753 | 同上 |
| `sales_execution_report` | 1755-1789 | 经 `_sales_report_orders()`，warehouse 为空不 filter |
| `export_sales_execution_report` | 1791-1821 | 同上 |
| `sales_price_analysis` | 1823-1864 | 同上 |
| `export_sales_price_analysis` | 1866-1894 | 同上 |
| `sales_reconciliation_report` | 1323-1375 | 为空不 filter |
| `export_sales_reconciliation_report` | 1377-1396 | 同上 |
| `sales_report` | 1398-1491 | 为空不 filter |
| `export_sales_report` | 1272-1321 | `warehouse_id` 为空不 filter |
| `export_sales_outbound` | 889-936 | **完全没有 warehouse 参数**，仅 status/search |
| `export_sales_orders` | 1203-1270 | **完全没有 warehouse 参数** |
| `sales_dashboard` | 938-986 | 无 warehouse 筛选，跨仓库汇总（看板性质，可降级 P2） |
| `sales_exceptions` | 988-1052 | 无 warehouse 筛选（异常工作台，可降级 P2） |

- **根因**：所有报表统一采用 `if selected_warehouse: filter(...)` 的「有则过滤、无则全量」模式，缺少 `else: return 空/400` 分支。`export_sales_outbound`/`export_sales_orders` 甚至连 warehouse 入口都没有。
- **修复建议**：在每个报表/导出路由入口统一解析 warehouse，未提供且无默认仓库时返回空结果或 400；可在 `_sales_report_orders`/`_sales_report_filters_context` 集中加「warehouse 必填」校验；`export_sales_outbound`、`export_sales_orders` 需补 warehouse 必填参数。

#### SALES-AUDIT-008 销售出库完成未在写锁后复核仓库 active 状态（PUR-AUDIT-003 同类问题）

- **文件**：[app/routes/out_order.py:634-637](file:///workspace/app/routes/out_order.py#L634-L637)（锁前校验）、[out_order.py:659-677](file:///workspace/app/routes/out_order.py#L659-L677)（锁后仅校验非空，未复核 active）
- **根因**：`complete_out_order` 对 `business_type=='销售出库'` 的单据，仅在**获取写锁之前**调用 `validate_sales_outbound_warehouse(order)`（校验 `status=='active'`）。但在 `_acquire_order_write_lock` 加锁之后，只做了 `if not order.warehouse` 的非空补默认仓校验，**没有重新调用 `validate_sales_outbound_warehouse` 或 `assert_warehouse_active`**。草稿建立后仓库被停用，仍可完成出库并扣减库存。
- **对比**：`in_order.py:1389-1393` 的 PUR-AUDIT-003 修复正是在加锁后补了 `assert_warehouse_active(order.warehouse, allow_empty=False)`。销售出库完成路径遗漏了同款修复。
- **修复建议**：在 `out_order.py:677` 加锁后追加：对 `business_type=='销售出库'` 分支重新调用 `validate_sales_outbound_warehouse(order)`，失败则 `db.session.rollback()` 并 `return api_error(...)`。

---

### P1 导出字段完整性

#### SALES-AUDIT-009 销售订单导出/报表/打印缺合同单号与工程名称字段

参考用户已确认的要求「采购入库/领料单导出必须有合同单号、工程名称字段」，销售订单导出应保持一致。`SalesOrder` 模型已有 `contract_no`/`project_name`/`project_no` 字段，列表页 `sales_order.html` 与详情页 `sales_order_detail.html` 均已展示，但导出/打印环节遗漏：

| 子项 | 文件:行号 | 现状 | 修复 |
|---|---|---|---|
| `export_sales_orders` | [sales.py:1244](file:///workspace/app/routes/sales.py#L1244) | 表头有 `项目号`，**无 `合同单号`、`工程名称`** | 表头追加两列；数据行追加 `order.contract_no or ''`、`order.project_name or ''` |
| `export_sales_report` | [sales.py:1296](file:///workspace/app/routes/sales.py#L1296) | **完全无 contract_no/project_no/project_name** | 表头追加 `'合同单号','工程名称'`；数据行追加对应值 |
| `export_sales_execution_report` | [sales.py:1815](file:///workspace/app/routes/sales.py#L1815) | **无 contract_no/project_name** | 表头追加合同/工程两列；数据行追加 `order.contract_no or ''`、`order.project_name or ''` |
| 打印模板 `_render_generic_document_print` | [sales.py:823-836](file:///workspace/app/routes/sales.py#L823-L836) | `info` 含 `('项目号', order.project_no or '')`，**无 `合同编号`、`工程名称`** | 在 `info` 列表追加 `('合同编号', order.contract_no or '')`、`('工程名称', order.project_name or '')` |

- **可选补充（P2）**：`export_sales_outflow_report`（[sales.py:1617](file:///workspace/app/routes/sales.py#L1617)）已通过 `oo.source_sales_order_id` 关联到 `SalesOrder`，零成本可补合同/工程；`export_sales_outbound`（[sales.py:900](file:///workspace/app/routes/sales.py#L900)）需先确认是否与 `out_order.py` 重复路由。

---

### P2 一般

| 编号 | 维度 | 文件:行号 | 问题 |
|---|---|---|---|
| SALES-AUDIT-010 | 删除保护 | sales.py:1073-1097 | `delete_sales_order` / `batch_delete_sales_orders` 仅校验 `status=='draft'`，不检查 `OutOrder.source_sales_order_id` 引用，防御性缺失 |
| SALES-AUDIT-011 | 状态机 | out_order.py:762-795 | 删除 pending 出库单后未清理 `SalesOrder.shipment_order_no`，详情展示陈旧单号 |
| SALES-AUDIT-012 | 并发 | sales.py:334-357 | `create_sales_outbound_from_selection` 锁 `SalesOrderItem` 但不锁 `SalesOrder`，status 检查存在 TOCTOU |
| SALES-AUDIT-013 | 仓库规则 | sales.py:456-460,593-597 | 订单新增/编辑未「自动带入默认仓库」，直接拒绝（规则一不完整） |
| SALES-AUDIT-014 | 前端规则 | sales_order_add.html:537, sales_order_edit.html:479 | 仓库 `<select>` 无 `required` 属性，未默认选中默认仓库 |
| SALES-AUDIT-015 | 库位规则 | sales.py:672-717,753-789,296-421 | 三个下推草稿创建路由未在库位管理启用时校验 location 必填（完成时才兜底） |
| SALES-AUDIT-016 | 列表隔离 | sales.py:163-282,858-887 | 列表页未按仓库/角色隔离数据 |
| SALES-AUDIT-017 | A8 | sales.py 全部 POST 路由 | 未使用 pydantic BaseModel（存量豁免，技术债） |
| SALES-AUDIT-018 | 风格分裂 | out_order.py:694-702 vs 937-940 | 单张完成用 `deduct_location_inventory_atomic`，批量完成用 `update_location_inventory`，函数入口不一致 |
| SALES-AUDIT-019 | JS 合规 | excel-table.js:524 | `console.log`（带 allow-console 豁免，仍属业务代码 console 调用） |
| SALES-AUDIT-020 | JS 合规 | sales_order_edit.html:1220, sales_order_add.html:1276 | `console.warn`（A3 正则不覆盖 + 模板内联 JS 不扫描） |
| SALES-AUDIT-021 | 工具盲区 | lint_wms_rules.py:413 | A3-A5 只扫描 `app/static/js/`，不覆盖模板内联 `<script>` |

---

## 三、修复优先级建议

1. **P0-1 + P1-2 组合阻断**：先修 `recalculate_sales_order` 状态守卫 + `cancel_sales_order` 检查 pending 草稿，二者组合即可阻断"取消后被复活"的确定性数据损坏链。
2. **P1-3/4/5/6 并发与超量**：加写锁、原子回写 `shipped_quantity`、完成时校验 remaining、编辑保留 `source_sales_order_item_id`。
3. **P1-7 报表仓库必填**：在 `_sales_report_orders`/`_sales_report_filters_context` 集中加门禁，影响面最广。
4. **P1-8 出库完成 active 复核**：照搬 `in_order.py:1389-1393` 的 PUR-AUDIT-003 写法。
5. **P1-9 导出字段补齐**：参考已完成的 PUR-AUDIT-004 模式，4 个导出 + 1 个打印补合同单号、工程名称。

---

## 四、合规项（已正确实现，供对照）

1. 出库下推三路由均调用 `validate_sales_warehouse` 校验仓库必填 + active。
2. 销售订单确认/批量确认在状态变更前均复核仓库 active。
3. 出库完成时库位必填已由 `out_order.py:675-677` 兜底。
4. 权限装饰器：全部 12 个 POST/PUT/DELETE 路由均带 `@require_role` + `@login_required`，无遗漏。
5. SQL 均为 ORM 参数化，未见字符串拼接。
6. 模板 `innerHTML` 均经 `esc/escAttr/escapeHtml` 转义；`|tojson|safe` 为正确惯用法。
7. 库存扣减统一走 `deduct_stock_atomic`（条件 UPDATE，原子）+ `deduct_location_inventory_atomic`，未直接改 `Material.stock`。

---

## 五、修复任务映射（建议登记到 WMS_BUG_BASELINE.md）

| 建议 BUG ID | 对应审计项 | 优先级 |
|---|---|---|
| BUG-2026-08-14-005 | SALES-AUDIT-001 | P0 |
| BUG-2026-08-14-006 | SALES-AUDIT-002 | P1 |
| BUG-2026-08-14-007 | SALES-AUDIT-003 + SALES-AUDIT-004 + SALES-AUDIT-006（并发与超量一组） | P1 |
| BUG-2026-08-14-008 | SALES-AUDIT-005 | P1 |
| BUG-2026-08-14-009 | SALES-AUDIT-007 | P1 |
| BUG-2026-08-14-010 | SALES-AUDIT-008 | P1 |
| BUG-2026-08-14-011 | SALES-AUDIT-009 | P1 |
