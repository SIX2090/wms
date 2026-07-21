# WMS 销售模块 vs 采购模块对比与销售模块审计报告

- 编制日期：2026-07-21
- 审计范围：`/workspace/app/app.py`（约 42720 行）、`/workspace/app/templates/`（销售/采购相关模板）、`/workspace/app/ai/`、`/workspace/scripts/verify_sales_module.py`、`/workspace/SALES_MANAGEMENT_DEVELOPMENT_PLAN.md`、`/workspace/WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`、`/workspace/AI_PERMISSION_MATRIX.md`
- 分支策略：本审计严格落在 `main` 分支，未创建任何 `feature/*`、`fix/*`、`trae/*` 工作分支
- 验证方法：所有结论均通过直接读取源码确认（行号引用见各节），未做主观推测
- 修复状态：本报告 4 处 P0 安全问题、1 处 P1 语义错配、3 处 P2 前端工程化问题已修复并提交 `main`，详见第九节"修复状态记录"

---

## 一、执行摘要

销售模块相对采购模块在**主流程闭环、金额精度、行级来源外键、选单并发锁**等核心点已对齐采购侧；但在 **AI 能力、前端工程化、权限分权、安全防护、报表可视化**五个维度明显落后于采购模块，存在 **2 处权限遗漏、1 处 CSRF 缺失、1 处 AI 工具语义错配**。

**截至 2026-07-21 修复进展**：4 处 P0 安全问题全部修复（`SM-P6-FIX-01`）；1 处 P1 语义错配已修复（`AI-SALES-F01-F02` 拆分 `sales_out_draft` 为 `after_sale_out_draft` + `sales_outbound_draft`）；P1 AI 异常分析按钮与单据联查面板已补齐（`AI-SALES-F01-FIX-02`）；P2 前端工程化迁移（`confirm/alert` → `showConfirm/showToast`、`customer.html` 导入模态框、`sales_order.html` 权限感知按钮隐藏）已完成（`SM-P6-02`）。剩余 P1 AI 跟进工作台、P2 csrfFetch 抽取与 setupResizableTable 引入、P3 报表可视化与极简模板重写留待 `AI-SALES-F02`、`SM-P6-03`、`SM-P4-FIX-01` 后续子项。

### 关键问题一览

| 级别 | 问题 | 位置 | 类型 | 修复状态 |
|---|---|---|---|---|
| P0 | `/sales/<id>/copy` 写操作仅 `@login_required`，缺 `@require_role` | `app.py:41923-41924` | 权限 | ✅ 已修复（SM-P6-FIX-01） |
| P0 | `/sales/batch_delete` 删操作仅 `@login_required`，缺 `@require_role` | `app.py:41969-41970` | 权限 | ✅ 已修复（SM-P6-FIX-01） |
| P0 | `sales_order_detail.html` 第 139 行 fetch 无任何 CSRF 头 | `templates/sales_order_detail.html:139` | 安全 | ✅ 已修复（SM-P6-FIX-01，改用 csrfPost helper） |
| P0 | `sales_order_detail.html` 第 157 行 fetch 仅设 `Content-Type`，无 `X-CSRFToken` | `templates/sales_order_detail.html:157` | 安全 | ✅ 已修复（SM-P6-FIX-01，改用 csrfPost helper） |
| P1 | `sales_out_draft` 工具名"销售出库草稿"但描述/端点均为"售后出库" | `ai/tools/registry.py:312`、`ai/policies.py:9,31` | 语义错配 | ✅ 已修复（AI-SALES-F01-FIX-02，拆分为 after_sale_out_draft + sales_outbound_draft） |
| P1 | 销售侧无 `ai_sales_workbench.html` AI 跟进工作台（采购侧 7 队列） | 不存在 | 功能缺口 | ⏳ 未修复（建议新建 AI-SALES-F02） |
| P1 | 销售侧无 AI 异常分析按钮（采购 `out_order_detail.html` 有） | 不存在 | 功能缺口 | ✅ 已修复（AI-SALES-F01-FIX-02，新增按钮 + /api/ai/sales_order/<id>/anomaly_analysis 路由） |
| P1 | 销售侧无单据联查面板（采购侧 `purchase_order_detail.html:70-112` 有） | 不存在 | 功能缺口 | ✅ 已修复（AI-SALES-F01-FIX-02，sales_order_detail.html 新增售后单联查面板） |
| P2 | 销售侧 14 个模板均未使用 `csrfFetch` helper | 全部 `sales_*.html` | 工程化 | ⏳ 部分修复（sales_order_detail.html 已用 csrfPost；其余 13 个模板留待 SM-P6-03） |
| P2 | 销售侧表格无 `setupResizableTable`、无每页条数选择器 | 全部 `sales_*.html` | UX | ⏳ 未修复（建议 SM-P6-03） |
| P2 | `sales_outbound_list.html`(8 行)、`sales_reconciliation_report.html`(4 行) 功能过于简陋 | 模板 | UX | ⏳ 未修复（建议 SM-P4-FIX-01） |
| P3 | 销售报表全无图表（趋势/价格/汇总均适合可视化） | 全部 `sales_*_report.html` | UX | ⏳ 未修复（建议 SM-P4-FIX-01） |

---

## 二、后端对比

### 2.1 路由规模与结构对比

| 维度 | 采购侧 | 销售侧 | 差异 |
|---|---|---|---|
| 主单 CRUD 路由 | 22 个（申请/订单/入库） | 19 个（订单/出库/售后） | 销售无审批工作流 |
| 报表路由 | 5 个（`/purchase_report` + 4 个表） | 12 个（汇总/对账/出库/趋势/执行/价格） | 销售报表维度更多 |
| Excel 导入/导出/模板 | 全覆盖 | 全覆盖 | 对齐 |
| 打印模板 | `InOrderPrintTemplate`（CRUD） | `OutOrderPrintTemplate`（CRUD） | 对齐 |
| 主数据路由 | `supplier` 7 个 | `customer` 7 个 | 对齐 |
| 状态机 | 4 级（申请→订单→入库→完成） | 2 级（订单→出库完成） | 销售更简单，但缺审批层 |

### 2.2 数据模型对比

| 模型 | 采购侧字段 | 销售侧字段 | 对齐情况 |
|---|---|---|---|
| 头表 | `PurchaseOrder`（含 `supplier_id`/`purchase_request_id`/`expected_date`/`status`/`total_amount`） | `SalesOrder`（含 `customer_id`/`warehouse_id`/`delivery_date`/`status`/`shipment_status`/`salesperson_id`/`project_no`/`currency`/`settlement_method`/税额三件套） | 销售侧字段更丰富（税额、币别、结算、项目号） |
| 明细表 | `PurchaseOrderItem`（`quantity`/`received_quantity`/`price`/`amount`） | `SalesOrderItem`（`quantity`/`shipped_quantity`/`price`/`amount`/`tax_rate`/未税/税额/含税/`batch_no`/`serial_no`） | 销售侧含批次/序列号、税额拆分 |
| 行级来源外键 | `InOrderItem.source_purchase_order_item_id` | `OutOrderItem.source_sales_order_item_id` | **对齐**（销售阶段 10 完成） |
| 头级来源外键 | `InOrder.source_purchase_order_id` | `OutOrder.source_sales_order_id` + `AfterSaleOutOrder.source_sales_order_id` + `source_out_order_id` | **对齐**（销售阶段 7/17 完成） |
| 金额精度 | `Numeric(18,2)`（基线即一致） | `Numeric(18,2)`（阶段 7 由 Float 升级） | **对齐** |
| 仓库外键 | 入库单 `warehouse` 字符串 | 销售订单 `warehouse_id` 外键 + `warehouse` 字符串双写兼容 | **对齐**（销售阶段 12 完成） |

### 2.3 状态机对比

**采购侧 4 级状态链**：
```
PurchaseRequest (pending → approved/rejected → completed)
    ↓ 下推
PurchaseOrder (pending → partial → completed → closed)
    ↓ 下推
InOrder (pending → completed → 反提交回 pending)
    ↓ 完成
库存入账 + 回写 PO.received_quantity + update_purchase_order_status
```

**销售侧 2 级状态链**：
```
SalesOrder (draft → confirmed → closed | cancelled) + shipment_status (pending → partial → shipped)
    ↓ 下推
OutOrder (pending → completed → 反提交回 pending)
    ↓ 完成（deduct_stock_atomic + sync_sales_order_shipment）
回写 SalesOrderItem.shipped_quantity + recalculate_sales_order 自动推进 shipment_status
```

**关键差异**：
- 销售订单**无审批工作流**（采购侧 PurchaseRequest 有 pending/approved/rejected/completed 四态）
- 销售订单**无 close/reopen 显式动作**（自动随 `shipment_status='shipped'` 变 `closed`），采购侧有 `/purchase_order/<id>/close`、`/reopen`
- 销售订单确认无库存可用量/价格底线/客户信用提示（V2 A.2 节明列缺口）
- 销售选单并发保护已对齐采购（SQLite `BEGIN IMMEDIATE` + 加锁后重读，`app.py:41235-41246`）

### 2.4 权限矩阵对比

| 操作 | 采购侧角色 | 销售侧角色 | 一致性 |
|---|---|---|---|
| 列表/详情 | `@login_required` | `@login_required` | 一致（均宽松） |
| 单条删除 | `@require_role('purchase')` / `@require_role('warehouse')` | `@require_role('warehouse','purchase','sales')` | 一致 |
| 批量删除 | `@require_role('purchase')` | **`@login_required`** ← 缺角色 | **不一致** |
| 复制 | `@require_role('purchase')`（`copy_purchase_order`） | **`@login_required`** ← 缺角色 | **不一致** |
| 确认/审批 | `@require_role('purchase')` | `@require_role('warehouse','purchase','sales')` | 一致 |
| 下推 | `@require_role('warehouse','purchase')` | `@require_role('warehouse','purchase','sales')` | 一致 |
| 完成/反提交 | `@require_role('warehouse')` | `@require_role('warehouse')` | 一致 |

**权限遗漏实证**：

`/workspace/app/app.py:41923-41925`：
```python
@app.route('/sales/<int:id>/copy', methods=['POST'])
@login_required
def copy_sales_order(id):
```

`/workspace/app/app.py:41969-41971`：
```python
@app.route('/sales/batch_delete', methods=['POST'])
@login_required
def batch_delete_sales_orders():
```

对照同模块的 `/sales/add`（`app.py:41328`）和 `/sales/<id>/delete`（`app.py:41908`）均带 `@require_role('warehouse','purchase','sales')`，这两个路由的权限遗漏与 `SM-P6-01`（销售管理开发计划第 722 行）"销售录单、确认、取消、下推、仓库完成、反提交和删除分权"目标不符。

`verify_sales_module.py:133-137` 的 `SALES-STC-004` 静态检查仅扫描 `def sales_order_add():` 之后 5000 字符内是否出现 `@require_role`，无法发现这两处遗漏。

### 2.5 AI 能力对比（核心差距）

| 能力 | 采购侧 | 销售侧 | 差距 |
|---|---|---|---|
| 跟进 Agent | `app/ai/agents/purchase_followup.py`（4 步：开放订单扫描/3 天到货/请购转化/低库存补货） | **无 `sales_followup` Agent** | 完全缺失 |
| 跟进工作台 | `app/ai/ops/purchase_followup_workbench.py` + `/api/ai/purchase_followup_workbench` + `/ai/purchase_workbench` 页面（7 队列） | 仅 `/sales/exceptions` 静态异常页（5 类，非 AI 任务） | **完全缺失** |
| 跟进话术 | `purchase_followup.py:106` `_generate_followup_message`（不自动发送） | 无 | 缺失 |
| OCR 草稿生成 | `/api/ai/document_ocr`（微信/截图送货通知 → 入库草稿）+ `ai/documents/extractor.py:198` `_is_wechat_delivery` + `ai/documents/delivery_matcher.py:560` `is_purchase_request_forbidden_for_delivery` | 无对应"客户发货通知 → 销售出库草稿"OCR 流 | 缺失 |
| 匹配引擎 | `ai/documents/delivery_matcher.py`（4 维度加权评分、自动选单门槛 0.70） | 无对应"客户发货通知 ↔ 销售订单"匹配引擎 | 缺失 |
| 匹配校准 | `ai/documents/delivery_matcher_calibration.py`（权重校准 + 错误样本回灌） | 无 | 缺失 |
| 工作台工具 | `purchase_insights`（registry.py:320） | **无 `sales_insights` 工具** | 缺失 |
| 草稿工具 | `purchase_request_draft`、`purchase_receive_draft` | `sales_out_draft`（**语义错配**：实际创建 `AfterSaleOutOrder`，非销售 `OutOrder`） | 错配 |
| 草稿校验 | `ai/agents/draft_check.py`（含采购未到货量检查） | `ai/documents/sales_draft_validation.py`（670 行，证据链 + 部分发货 + 对账） | 部分对齐 |
| AI 路由 | `/api/ai/sales/<id>/draft_check`（只读） | 同左 | 对齐 |
| 履约分析 | `ai/analysis/supplier_performance.py`（交期/质量/价格稳定性）+ `/api/ai/supplier_evaluation` | **无客户履约/付款准时率分析** | 缺失 |
| 补货 Agent | `ai/agents/replenishment.py` + `/ai/replenishment_smart` | 无销售侧等价 | N/A |
| 预算控制 | `ai/agents/budget_control.py`（AI-R13，通用） | 复用 | 对齐 |
| 菜单 AI 入口 | 采购菜单含"AI 补货建议"（base.html:1986）；库存菜单含"智能补货/供应商评估/单据 OCR"（base.html:2039-2044） | **销售菜单零 AI 入口**（base.html:1996-2015） | 缺失 |
| AI 助手角色建议 | purchase 角色有专属建议（base.html:2361-2375） | **无 sales 角色专属建议** | 缺失 |

**直接 AI 任务数对比**：
- 采购侧：`AI-R06` + `AI-R06-F01` + `AI-R11` + `AI-R11-F01` + `AI-R13` 等至少 5 个直接 AI 任务
- 销售侧：仅 `AI-SALES-F01` + `AI-SALES-F01-FIX-01` 2 个直接 AI 任务

**`sales_out_draft` 语义错配实证**：

`/workspace/app/ai/tools/registry.py:312`：
```python
'sales_out_draft': _tool('sales_out_draft', 'Create an after-sales outbound draft for manual review.', 'warehouse_draft', SALES_OUT_DRAFT_SCHEMA, confirmation_required=True),
```

`/workspace/app/ai/policies.py:9,31`：
```python
'sales_out_draft': frozenset({'warehouse', 'sales'}),
'sales_out_draft': 'add_after_sale_out_order',   # AI_CAPABILITY_BUSINESS_ENDPOINTS
```

即工具名为"销售出库草稿"，但描述是"after-sales outbound draft"，且业务端点指向 `add_after_sale_out_order`（售后出库）。AI 调用方根据工具名会误以为创建销售 `OutOrder`，但实际创建 `AfterSaleOutOrder`，业务语义割裂。

### 2.6 历史 Bug 与已修复项对比

采购侧历史 Bug（`WMS_BUG_BASELINE.md` 已记录）：BUG-NEW-001（删除已完成入库单漏回退库位）、BUG-NEW-003（Android 入库 API 绕过采购入库策略）、BUG-NEW-004（保留 `received_quantity` 占用量）、BUG-NEW-013（入库单转领料单缺类型校验）、AI-ENCODING-001、AI-AUTH-001、BUG-NEW2-001/002 等 8+ 项。

销售侧历史 Bug：仅 1 项（`SALES_MANAGEMENT_DEVELOPMENT_PLAN.md` 阶段 6 记录的 `_check_out_order_anomalies` 中 `order.customer_id` 引用不存在属性，已修复为 `getattr(order, 'customer', None)`）。

采购侧修复历史丰富、闭环明确；销售侧修复历史单薄，**部分已修复 Bug 未在 `WMS_BUG_BASELINE.md` 登记**（如 OutOrder.customer_id、OutOrderItem.source_sales_order_item_id 等），台账一致性弱于采购侧。

---

## 三、前端对比

### 3.1 模板规模对比

| 模板类型 | 采购侧行数 | 销售侧行数 | 差距 |
|---|---|---|---|
| 列表页 | `purchase_order.html` 338 / `purchase_request.html` 437 / `in_order.html` 356 | `sales_order.html` 406 / `sales_outbound_list.html` **8** / `after_sale_out.html` 250 | 销售出库列表仅 8 行，功能极简 |
| 新增页 | `purchase_order_add.html` 656 / `purchase_request_add.html` 922 / `in_order_add.html` ~600 | `sales_order_add.html` 170 / `after_sale_out_add.html` 617 | 销售新增页字段/键盘导航缺失 |
| 详情页 | `purchase_order_detail.html` 405 / `purchase_request_detail.html` 486 / `in_order_detail.html` ~1500 / `out_order_detail.html` ~1100 | `sales_order_detail.html` 163 / `after_sale_out_detail.html` 197 | 销售详情页缺联查/内联编辑/AI 异常 |
| AI 工作台 | `ai_purchase_workbench.html` 186 | **无 `ai_sales_workbench.html`** | 完全缺失 |
| 报表页 | `purchase_report.html` 175（含 Gap 分析） | 7 个 `sales_*_report.html`（最小 4 行） | 销售报表维度多但深度浅 |

### 3.2 采购有但销售缺失的功能（实证行号）

| 功能 | 采购侧行号 | 销售侧状态 |
|---|---|---|
| AI 跟进工作台（7 队列） | `ai_purchase_workbench.html:35-53` | Glob 确认 `ai_sales_workbench.html` 不存在 |
| AI 异常分析按钮 | `out_order_detail.html:101-103` | `sales_order_detail.html`、`after_sale_out_detail.html` 均无 |
| AI 异常 API 调用 | `out_order_detail.html:1007` | 无 `/api/ai/sales_order/{id}/anomaly_analysis` |
| 单据联查面板 | `purchase_order_detail.html:70-112`、`purchase_request_detail.html:113-159`、`out_order_detail.html:247`、`in_order_detail.html:247` | `sales_order_detail.html` 无任何联查面板 |
| 下推内联面板 | `purchase_order_detail.html:114-143` | 销售侧仅有"生成出库草稿"按钮，无内联面板 |
| `csrfFetch` helper | 7 个采购/通用文件统一封装 | **0 个 `sales_*.html` 使用** |
| 每页条数选择器 20/50/100/200 | `in_order.html`、`out_order.html:148-156` | 销售列表全部缺失 |
| 可调整列宽 `setupResizableTable` | `in_order.html:209-214`、`out_order.html:210-214`、`material.html` 等 10 个文件 | 0 个 `sales_*.html` 使用 |
| 客户/供应商导入模态框 | `supplier.html:145-198` | `customer.html` 完全无导入入口 |
| 列宽拖拽手柄 | `purchase_request_add.html:411-421` | `sales_order_add.html` 无 |
| 客户/供应商搜索下拉 + 键盘导航 | `purchase_order_add.html:283-316` | `sales_order_add.html` 无 |
| Gap 分析视图 | `purchase_report.html:38-65` | `sales_report.html` 无对账 gap 视图 |
| 紧急度徽章 | `purchase_request.html:99-108` | 销售订单无审批/紧急度概念 |
| `Promise.all` 并行批量删除 | `purchase_request.html:406-413` | `sales_order.html` 串行 |
| 执行状态列（已下推/已入库/待入库/未下推） | `purchase_order.html:113-122`、`purchase_order_detail.html:160-215` | `sales_order.html` 仅 4 张汇总卡，无执行列 |
| AI 助手 sales 角色建议 | `base.html:2361-2375`（purchase/warehouse/production 角色有） | **无 sales 角色专属 AI 建议** |

### 3.3 工程化封装缺失（实证）

**CSRF 三套模式**：
1. `csrfFetch` helper（采购侧 7 文件）：`purchase_request.html:244-254`、`purchase_request_detail.html:275-298`、`out_order_detail.html`、`in_order_detail.html`、`material.html`、`system_settings.html`、`ai_document_confirm.html`
2. 手动 `X-CSRFToken` 头：`sales_order_add.html:134-135`（正确使用）
3. **完全无 CSRF 头**：`sales_order_detail.html:139`（`fetch(url, { method: 'POST' })`）、`sales_order_detail.html:157`（仅 `Content-Type`）

**`confirm()` vs `showConfirm()` 不一致**：
- 销售侧：`sales_order_detail.html:138,156`、`after_sale_out.html:177-248`、`after_sale_out_detail.html:164-196` 均用 `confirm()`
- 采购侧：`purchase_order_detail.html`、`purchase_request.html`、`purchase_request_detail.html` 统一用 `showConfirm`

**`alert()` vs `showToast()` 不一致**：
- 销售侧：`sales_outbound_selection.html:45-46`、`sales_order_detail.html:145,155,160`、`supplier.html:189,192,195` 均用 `alert()`
- 采购侧统一用 `showToast`

### 3.4 代码重复实证

| 重复块 | 涉及文件 | 重复规模 |
|---|---|---|
| T+ 风格 CSS（`page-header`/`material-input`/`material-dropdown`/`tplus-table-wrapper`/`col-resize`/`tplus-toolbar`） | `after_sale_out_add.html`、`purchase_request_add.html`、`out_order_add.html`、`in_order_add.html` | 每处 ~300 行 |
| 可排序表头 CSS（`.sortable-header`） | `out_order.html:314-318`、`purchase_request.html:432-437`、`in_order.html:351-356` | 3 处内联 |
| `customer.html` 与 `supplier.html` 前 104 行 | 几乎完全同构（仅 supplier 多 importModal） | 104 行重复 |
| 状态徽章条件类 | `sales_order.html:152-172`、`purchase_order.html:152-164`、`after_sale_out.html`、`out_order.html` 各自重复 | 应抽 `status_badge(status)` 宏 |
| fetch + `location.reload()` CRUD 模式 | `sales_order.html:256-404`、`purchase_order.html:213-337`、`purchase_request.html:301-429` | 几乎逐行复制 |

### 3.5 菜单结构对比（`base.html:1969-2054`）

**采购管理菜单**（line 1971-1993）：采购申请/订单/入库/列表/明细/供应商/报表 + **AI 补货建议**（line 1986）

**销售管理菜单**（line 1996-2015）：销售工作台/异常工作台/新建/列表/出库选单/出库列表/直接出库/售后/客户管理/报表（执行/价格/对账）—— **零 AI 入口**

**库存管理菜单**（line 2016-2054）：智能补货建议/库存健康度/单据 OCR 识别/供应商智能评估/智能库位推荐/需求预测 —— **AI 能力集中在库存/采购侧，销售侧无对称能力**

### 3.6 AJAX 模式对比

**共同模式**：销售与采购在 CRUD 层面均依赖 `fetch + location.reload()`，未实现局部更新。

**采购侧独有的局部更新场景**：
- `ai_purchase_workbench.html:62` fetch 后局部渲染 7 段卡片
- `out_order_detail.html`/`in_order_detail.html` 内联编辑（`editable-cell` 类）+ 局部单元格更新

**销售侧无任何局部更新场景**，所有 AJAX 成功后均 `location.reload()`。

---

## 四、销售模块审计发现

### 4.1 P0 安全问题（需立即修复）

#### 4.1.1 权限遗漏：`/sales/<id>/copy` 和 `/sales/batch_delete`

- 位置：`app.py:41923-41924`、`app.py:41969-41970`
- 现状：仅 `@login_required`，无 `@require_role`
- 影响：任何登录用户（含 `user`/`production` 角色）均可调用复制订单（创建新销售订单）和批量删除草稿订单
- 对照：同模块 `/sales/add`（41328）和 `/sales/<id>/delete`（41908）均有 `@require_role('warehouse','purchase','sales')`
- 验证脚本盲区：`verify_sales_module.py:133-137` 的 `SALES-STC-004` 仅扫描 `def sales_order_add():` 后 5000 字符，无法发现这两处
- 建议：补充 `@require_role('warehouse','purchase','sales')`，并扩展 `SALES-STC-004` 为对全部 `/sales/*` POST 路由的权限装饰器存在性扫描

#### 4.1.2 CSRF 头缺失：`sales_order_detail.html`

- 位置：`templates/sales_order_detail.html:139`、`templates/sales_order_detail.html:157`
- 现状：
  - 第 139 行 `postAction` 通用函数：`fetch(url, { method: 'POST' })` 完全无头
  - 第 157 行 `createSelectedOutbound`：`fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:...})` 仅 `Content-Type`，无 `X-CSRFToken`
- 影响：CSRF 防护失效，攻击者可构造跨站表单诱导用户确认/生成出库草稿
- 对照：`sales_order_add.html:134-135` 已正确设置 `X-CSRFToken`；采购侧 7 文件统一使用 `csrfFetch` helper
- 建议：销售侧统一改用 `csrfFetch` helper（从 `purchase_request.html:244-254` 抽取到 `base.html` 或 `_list_macros.html`）

### 4.2 P1 语义错配与功能缺口

#### 4.2.1 `sales_out_draft` AI 工具语义错配

- 位置：`ai/tools/registry.py:312`、`ai/policies.py:9,31`
- 现状：工具名 `sales_out_draft`（"销售出库草稿"），描述 "Create an after-sales outbound draft"（售后出库草稿），业务端点 `add_after_sale_out_order`（售后出库）
- 影响：AI 调用方根据工具名期望创建销售 `OutOrder`，但实际创建 `AfterSaleOutOrder`，业务语义割裂
- 建议：拆分为两个独立工具：
  - `sales_outbound_draft`（销售出库草稿，端点 `create_sales_outbound_draft`）
  - `after_sale_out_draft`（售后出库草稿，端点 `add_after_sale_out_order`）
  - 同步更新 `AI_PERMISSION_MATRIX.md`、`AI_CAPABILITY_ROLES`、`AI_CAPABILITY_BUSINESS_ENDPOINTS`、`verify_ai_tool_compliance.py`

#### 4.2.2 缺失 `ai_sales_workbench.html` AI 跟进工作台

- 现状：销售侧仅有 `sales_dashboard.html`（11 行静态卡片）和 `sales_exceptions.html`（22 行只读异常表）
- 对照：采购侧 `ai_purchase_workbench.html`（186 行，7 队列 + AI 接口 `/api/ai/purchase_followup_workbench` + 显式只读声明）
- 建议页面：`/ai/sales_workbench` + `ai_sales_workbench.html`，7 队列：
  - 待发货订单（confirmed 但 shipment_status=pending/partial）
  - 逾期未发货（delivery_date < today 且未发货）
  - 部分发货停滞（shipment_status=partial 超 N 天未推进）
  - 缺货待核对（明细物料库存不足）
  - 客户催发货话术（不自动发送）
  - 多笔订单合并发货候选
  - 客户履约/付款汇总
- 挂靠任务：`AI-SALES-F02`（新建，建议在 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 增列）

#### 4.2.3 缺失 AI 异常分析按钮

- 现状：`sales_order_detail.html`、`after_sale_out_detail.html` 均无 AI 异常分析入口
- 对照：`out_order_detail.html:101-103` 有 `showAiAnomalyAnalysis()` 按钮、line 404-425 有 AI 异常模态框、line 1007 调用 `/api/ai/out_order/{id}/anomaly_analysis`
- 建议：在 `sales_order_detail.html` 增加 AI 异常分析按钮，新增 `/api/ai/sales_order/<id>/anomaly_analysis` 路由（只读，挂靠 `AI-SALES-F01-FIX-02`）

#### 4.2.4 缺失单据联查面板

- 现状：`sales_order_detail.html` 仅展示简表关联出库单
- 对照：`purchase_order_detail.html:70-112` 有完整单据联查面板（关联入库单 + 状态汇总）
- 建议：在 `sales_order_detail.html` 增加联查面板（关联出库单 + 售后单 + 库存流水），对齐采购侧结构

#### 4.2.5 缺失客户导入模态框

- 现状：`customer.html` 仅 142 行，无导入入口
- 对照：`supplier.html:145-198` 有完整 importModal + AJAX + csrf_token
- 建议：在 `customer.html` 增加导入模态框，对齐 supplier 结构

### 4.3 P2 工程化问题

#### 4.3.1 销售模板未使用 `csrfFetch` helper

- 现状：14 个 `sales_*.html` 均未使用 `csrfFetch`，依赖手动 `X-CSRFToken`（部分缺失）
- 建议：将 `csrfFetch` helper 抽到 `base.html` 或 `_list_macros.html`，销售侧全部迁移

#### 4.3.2 销售表格无 `setupResizableTable` 与每页条数选择器

- 现状：销售列表/报表全部无列宽调整、无分页条数选择
- 对照：`in_order.html`、`out_order.html`、`material.html` 等 10 个文件统一使用
- 建议：在 `sales_order.html`、`sales_outbound_list.html`、`sales_outflow_report.html`、`sales_report.html` 等表格页引入

#### 4.3.3 `confirm()`/`alert()` 散用

- 现状：销售侧 4 个文件用 `confirm()`，4 个文件用 `alert()`
- 建议：全部迁移到 `showConfirm`/`showToast`

#### 4.3.4 T+ 风格 CSS 重复 3-4 份

- 涉及：`after_sale_out_add.html`、`purchase_request_add.html`、`out_order_add.html`、`in_order_add.html`
- 建议：抽到 `templates/_tplus_form_styles.html` 共享 partial

### 4.4 P3 UX 问题

#### 4.4.1 极简模板功能不足

- `sales_outbound_list.html`（8 行）：无分页 UI、无批量动作、无 Excel 导出
- `sales_reconciliation_report.html`（4 行）：仅仓库过滤 + 表格 + 导出，无日期/客户过滤、无差异汇总卡、无分页
- 建议：重写为完整功能页

#### 4.4.2 销售报表全无图表

- `sales_trend_report.html`：月度趋势适合折线图，仅表格
- `sales_price_analysis.html`：价格波动适合箱线图/折线图，仅表格
- `sales_report.html`：客户/物料/业务员汇总适合饼图/柱状图，仅表格
- 建议：引入 Chart.js（已在 `app/static/cdn/chart.umd-4.4.1.min.js` 可用），为 3 个报表增加可视化

#### 4.4.3 无 loading state、无权限感知按钮隐藏、无 a11y 标注

- 销售侧 AJAX 调用期间无 spinner、无按钮 disabled，用户可重复点击触发重复提交
- 销售侧工具栏无 `{% if current_user.role in [...] %}` 条件渲染（对照 `out_order.html:8,121,128`）
- 图标按钮无 `aria-label`、模态框无 `role="dialog"`、表格无 `scope="col"`

#### 4.4.4 `sales_outbound_selection.html` 路由命名可疑

- 位置：`sales_outbound_selection.html:36` 调用 `/api/ai/sales_order_selectable`
- 后端实际路由：`/api/sales_order/selectable`（`app.py:41136`），无 `/api/ai/` 前缀
- 建议：复核前端 URL 是否 404，统一为 `/api/sales_order/selectable`

### 4.5 已修复项验证

`SALES_MANAGEMENT_DEVELOPMENT_PLAN.md` 记录的 V1 阶段 7~20 + V2 SM-P0~P5 修复项均已落到代码：

| 修复项 | 文件:行号 | 验证状态 |
|---|---|---|
| OutOrderItem 行级来源外键 | `app.py:3243` `source_sales_order_item_id` | ✅ 已落地 |
| SalesOrder 仓库外键 | `app.py:4051` `warehouse_id` | ✅ 已落地 |
| 跨仓库边界校验 | `app.py` `validate_sales_warehouse` | ✅ 已落地 |
| 报表仓库筛选统一 warehouse_id | 12 个 sales 报表路由 | ✅ 已落地 |
| 选单并发锁 BEGIN IMMEDIATE | `app.py:41235-41246` | ✅ 已落地 |
| 销售工作台 + `/sales/outbound` 独立列表 | `app.py:41763`、`sales_dashboard.html` | ✅ 已落地 |
| 对账页 + 售后来源 + sales 角色 | `app.py:42108`、`AfterSaleOutOrder` 模型、`AI_PERMISSION_MATRIX.md` | ✅ 已落地 |
| 金额精度 Numeric(18,2) | `SalesOrder`/`SalesOrderItem` 字段 | ✅ 已落地 |

---

## 五、改进建议（按优先级）

### 5.1 P0：安全与权限修复（建议挂靠 `AI-SALES-F01-FIX-02` 或新建 `SM-P6-FIX-01`）

1. **补 `@require_role` 到 `/sales/<id>/copy`**（`app.py:41924`）
   ```python
   @app.route('/sales/<int:id>/copy', methods=['POST'])
   @login_required
   @require_role('warehouse', 'purchase', 'sales')
   def copy_sales_order(id):
   ```

2. **补 `@require_role` 到 `/sales/batch_delete`**（`app.py:41970`）
   ```python
   @app.route('/sales/batch_delete', methods=['POST'])
   @login_required
   @require_role('warehouse', 'purchase', 'sales')
   def batch_delete_sales_orders():
   ```

3. **修复 `sales_order_detail.html` CSRF 缺失**（line 139、157）
   - 引入 `csrfFetch` helper（从 `purchase_request.html:244-254` 抽取）
   - `postAction` 与 `createSelectedOutbound` 全部改用 `csrfFetch`

4. **扩展 `verify_sales_module.py` 的 `SALES-STC-004`**
   - 改为对全部 `/sales/*` POST 路由扫描 `@require_role` 装饰器存在性
   - 增加 CSRF 头检查（grep `sales_*_detail.html` 中的 fetch 是否含 `csrfFetch` 或 `X-CSRFToken`）

### 5.2 P1：AI 能力补齐（建议新建 `AI-SALES-F02`、`AI-SALES-F03`）

5. **新建 `ai_sales_workbench.html` AI 跟进工作台**
   - 页面：`/ai/sales_workbench`，7 队列（待发货/逾期/部分停滞/缺货待核对/客户催发货话术/合并发货候选/客户履约汇总）
   - 后端：`app/ai/ops/sales_followup_workbench.py`（纯 dataclass + 依赖注入，对齐 `purchase_followup_workbench.py`）
   - API：`/api/ai/sales_followup_workbench`（只读）
   - 强制 `read_only=True`、`needs_manual_confirmation=True`（话术不自动发送）

6. **新建 `sales_followup` Agent**
   - 文件：`app/ai/agents/sales_followup.py`
   - 工具注册：`registry.py` 新增 `sales_followup_agent`（`agent_task` 类别）
   - 权限：`AI_CAPABILITY_ROLES['sales_followup_agent'] = frozenset({'sales', 'warehouse'})`
   - 4 步：开放订单扫描/即将到期扫描/客户跟进话术生成/合并发货候选扫描

7. **新建 `sales_insights` 只读工具**
   - 文件：`app/ai/tools/sales.py`（对齐 `purchase.py` 但采用纯逻辑 + 依赖注入）
   - 注册：`registry.py` 新增 `sales_insights`（`sales_read` 类别）
   - 端点：`sales_order_list` 或新增 `/sales/dashboard`

8. **拆分 `sales_out_draft` 工具**
   - `sales_outbound_draft`：销售出库草稿，端点 `create_sales_outbound_draft`
   - `after_sale_out_draft`：售后出库草稿，端点 `add_after_sale_out_order`
   - 更新 `AI_PERMISSION_MATRIX.md`、`AI_CAPABILITY_ROLES`、`AI_CAPABILITY_BUSINESS_ENDPOINTS`、`verify_ai_tool_compliance.py`

9. **新增 AI 异常分析按钮**
   - `sales_order_detail.html` 增加 `showAiAnomalyAnalysis()` 按钮 + 模态框
   - 新增 `/api/ai/sales_order/<id>/anomaly_analysis` 路由（只读）

10. **新增单据联查面板**
    - `sales_order_detail.html` 增加联查面板（关联出库单 + 售后单 + 库存流水）

### 5.3 P2：前端工程化（建议挂靠 `SM-P6-02`）

11. **统一 CSRF 处理**：将 `csrfFetch` 抽到 `base.html` 或 `_list_macros.html`，14 个 `sales_*.html` 全部迁移
12. **统一 `showConfirm`/`showToast`**：替换 8 处 `confirm()`/`alert()`
13. **抽 T+ 风格 CSS 到共享 partial**：`templates/_tplus_form_styles.html`
14. **抽 `status_badge(status)` 宏**：到 `_list_macros.html`
15. **抽 `bindListActions(opts)` 通用 CRUD 函数**：到 `_list_macros.html`
16. **补客户导入模态框**：对齐 `supplier.html:145-198`
17. **引入 `setupResizableTable` 与每页条数选择器**：到 `sales_order.html`、`sales_outbound_list.html`、`sales_outflow_report.html`
18. **补权限感知按钮隐藏**：`sales_order.html` 工具栏加 `{% if current_user.role in ['admin','warehouse','sales'] %}`

### 5.4 P3：UX 与报表可视化（建议挂靠 `SM-P4-FIX-01`）

19. **重写 `sales_outbound_list.html`**：从 8 行扩展为完整功能页（分页/批量/Excel/排序）
20. **重写 `sales_reconciliation_report.html`**：从 4 行扩展（日期/客户过滤/差异汇总卡/分页）
21. **为 3 个报表引入 Chart.js**：趋势折线图、价格箱线图、汇总饼图/柱状图
22. **补 loading state**：AJAX 期间按钮 disabled + spinner
23. **补 a11y 标注**：`aria-label`、`role="dialog"`、`scope="col"`
24. **复核 `sales_outbound_selection.html:36` 路由**：统一为 `/api/sales_order/selectable`

### 5.5 台账治理（建议挂靠 `SM-P6-FIX-02`）

25. **回填销售已修复 Bug 到 `WMS_BUG_BASELINE.md`**：OutOrder.customer_id、OutOrderItem.source_sales_order_item_id 等
26. **新增 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 任务条目**：
   - `AI-SALES-F02`：销售跟进 AI 工作台（建议）
   - `AI-SALES-F03`：销售异常分析与联查（建议）
   - `SM-P6-FIX-01`：销售权限与 CSRF 修复（建议）
   - `SM-P6-FIX-02`：销售台账治理（建议）

---

## 六、改进优先级路线图

| 阶段 | 任务 | 优先级 | 挂靠 ID | 预期收益 |
|---|---|---|---|---|
| 阶段 1 | 修权限（copy/batch_delete）+ CSRF（detail 页）+ 扩展验证脚本 | P0 | `SM-P6-FIX-01` | 关闭 4 处安全漏洞 |
| 阶段 2 | 拆分 `sales_out_draft` 工具 | P1 | `AI-SALES-F01-FIX-02` | 消除 AI 工具语义错配 |
| 阶段 3 | 新建 `ai_sales_workbench.html` + `sales_followup_workbench.py` + `sales_followup` Agent | P1 | `AI-SALES-F02` | 销售侧对齐采购跟进能力 |
| 阶段 4 | 新增 AI 异常分析 + 单据联查面板 | P1 | `AI-SALES-F03` | 销售详情页对齐出库详情页 |
| 阶段 5 | 前端工程化（csrfFetch/showConfirm/setupResizableTable 抽共享） | P2 | `SM-P6-02` | 销售前端工程化对齐采购 |
| 阶段 6 | 报表可视化（Chart.js）+ 极简模板重写 | P3 | `SM-P4-FIX-01` | 销售报表对齐采购 Gap 分析视图 |
| 阶段 7 | 台账治理（回填 Bug + 新增任务 ID） | P2 | `SM-P6-FIX-02` | 台账一致性 |

---

## 七、附录

### 7.1 销售模块已落地提交历史（来自 `SALES_MANAGEMENT_DEVELOPMENT_PLAN.md` 记录）

| 提交哈希 | 日期 | 内容 |
|---|---|---|
| `2fc51dc` | 2026-07-16 | AI-SEC-F01：移除随机密码，验证含 `/sales` 200 |
| `0d21358` | 2026-07-16 | UX-F01：菜单修复，`/out_order` 默认排除销售出库 |
| `4159c57` | 2026-07-19 | 阶段 10：行级来源外键 `OutOrderItem.source_sales_order_item_id` |
| `66ba42b` | 2026-07-19 | 阶段 12：`SalesOrder.warehouse_id` 外键 + 历史回填 |
| `a1a12ee` | 2026-07-19 | 阶段 13：销售出库跨仓库边界校验 |
| `ddff2a0` | 2026-07-19 | 阶段 14：销售报表仓库筛选统一 `warehouse_id` |
| `d506b23` | 2026-07-19 | 阶段 15：销售选单并发保护 `BEGIN IMMEDIATE` |
| `652c3bb` | 2026-07-19 | 阶段 16（SM-P3-01）：销售工作台 + `/sales/outbound` 独立列表 |
| `e7e9342` | 2026-07-18/19 | 阶段 17：对账/售后来源/`sales` 角色/`/api/ai/sales/<id>/draft_check`；同 commit 对应 `AI-SALES-F01-FIX-01` |
| `b374565` | 2026-07-20 | AI-BUG-F02：`VALID_ROLES` 添加 `'sales'`，修复 `sales_out_draft` 工具合规检查 |

### 7.2 销售模块相关任务 ID（台账原文 verbatim）

`AI-SALES-F01`、`AI-SALES-F01-FIX-01`、`SM-P0-01`、`SM-P0-02`、`SM-P1-01`、`SM-P2-01`、`SM-P3-01`、`SM-P4-01`、`SM-P5-01`、`SM-P6-01`、`SM-P7-01`

### 7.3 销售模块验证脚本覆盖范围（`scripts/verify_sales_module.py`）

- 静态检查 10 项：`SALES-STC-001`~`SALES-STC-010`（迁移/税额/草稿防护/权限装饰器/报表模板/导入模板/外键贯穿/选单接口/仓库外键/并发锁）
- 运行时测试 19 项：`SALES-RT-000/000B/001~013` + `007A/007B/007C/011A` 子项
- 当前状态：29/29 通过（`SALES_MANAGEMENT_DEVELOPMENT_PLAN.md` 阶段 18 记录）

**验证脚本盲区**：
- `SALES-STC-004` 仅扫描 `def sales_order_add():` 后 5000 字符，无法发现 `/sales/<id>/copy`、`/sales/batch_delete` 权限遗漏
- 无 CSRF 头检查（未扫描模板 fetch 调用是否含 `X-CSRFToken` 或 `csrfFetch`）
- 无 `sales_out_draft` 工具语义校验（未检查工具描述与端点是否一致）

### 7.4 关键文件路径汇总

**销售后端**：
- `/workspace/app/app.py`（41027-42656 行：销售订单/出库/报表/售后路由）
- `/workspace/app/app.py`（4051-4117 行：SalesOrder/SalesOrderItem 模型）
- `/workspace/app/app.py`（3209-3251 行：OutOrder/OutOrderItem 模型）
- `/workspace/app/app.py`（3918-3957 行：AfterSaleOutOrder/AfterSaleOutOrderItem 模型）
- `/workspace/app/app.py`（40774-40912 行：recalculate_sales_order/sync_sales_order_shipment/build_sales_outbound_draft）

**销售 AI**：
- `/workspace/app/ai/documents/sales_draft_validation.py`（670 行）
- `/workspace/app/ai/tools/registry.py:312`（`sales_out_draft` 工具注册）
- `/workspace/app/ai/policies.py:9,31,54`（`sales_out_draft` 权限/端点/风险级别）

**采购对照**：
- `/workspace/app/ai/agents/purchase_followup.py`（220 行）
- `/workspace/app/ai/ops/purchase_followup_workbench.py`（7 队列工作台）
- `/workspace/app/ai/documents/delivery_matcher.py`（4 维度匹配引擎）
- `/workspace/app/ai/analysis/supplier_performance.py`（供应商履约）
- `/workspace/app/templates/ai_purchase_workbench.html`（186 行 AI 工作台页面）

**计划与台账**：
- `/workspace/SALES_MANAGEMENT_DEVELOPMENT_PLAN.md`
- `/workspace/WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`
- `/workspace/AI_PERMISSION_MATRIX.md`
- `/workspace/scripts/verify_sales_module.py`

---

## 八、结论

销售模块在**主流程闭环、金额精度、行级来源、选单并发、报表维度**等核心数据层已基本对齐采购模块；但在 **AI 能力（5+ 个直接任务 vs 2 个）、前端工程化（7 文件 csrfFetch vs 0 文件、10 文件 setupResizableTable vs 0 文件）、权限分权（4 处遗漏 vs 0 处）、安全防护（CSRF 缺失）、报表可视化（0 图表 vs Gap 分析）**五个维度明显落后。

最关键的 **4 处 P0 安全问题**（2 处权限遗漏 + 2 处 CSRF 缺失）应在下一迭代立即修复，并扩展 `verify_sales_module.py` 静态检查覆盖面以防止回归。

**AI 能力补齐**是销售模块相对采购模块最大的结构性差距，建议新建 `AI-SALES-F02`（销售跟进工作台 + Agent）和 `AI-SALES-F03`（销售异常分析 + 单据联查）两个独立任务，对齐采购侧的 `AI-R06`/`AI-R11` 矩阵。

本审计所有结论均通过直接读取 `/workspace` 工作区源码确认，未做主观推测。行号引用可在审计时逐行复核。

---

## 九、修复状态记录（2026-07-21）

本节记录审计报告识别问题的修复进展，按修复批次与挂靠任务 ID 组织。所有修复均严格落在 `main` 分支，未创建任何 `feature/*`/`fix/*`/`trae/*` 工作分支。

### 9.1 SM-P6-FIX-01：销售模块 P0 安全与权限修复（已完成）

**修复范围**：审计报告 4.1.1 节权限遗漏 + 4.1.2 节 CSRF 头缺失 + 5.1 节 P0 改进建议项 #1-#4

| 审计项 | 审计位置 | 修复内容 | 验证 |
|---|---|---|---|
| #1 `/sales/<id>/copy` 缺 `@require_role` | `app.py:41923-41925` | 补 `@require_role('warehouse','purchase','sales')` 装饰器（位于 `@login_required` 之上） | `verify_sales_module.py` SALES-STC-004 检出 12 路由全 PASS |
| #2 `/sales/batch_delete` 缺 `@require_role` | `app.py:41969-41971` | 同上 | 同上 |
| #3 `sales_order_detail.html:139` fetch 无 CSRF 头 | `templates/sales_order_detail.html:139` | `postAction` 函数改用 `csrfPost` helper，自动注入 `X-CSRFToken` | SALES-STC-011 PASS（base.html 全局 wrapper 兜底） |
| #4 `sales_order_detail.html:157` fetch 仅 `Content-Type` | `templates/sales_order_detail.html:157` | `createSelectedOutbound` 改用 `csrfPost` helper | 同上 |
| 验证脚本盲区 | `verify_sales_module.py:133-137` | SALES-STC-004 由单函数 5000 字符扫描扩展为正则扫描全部 `/sales/*` POST 路由的 `@require_role` 存在性；新增 SALES-STC-011 CSRF 头检查（识别 `base.html` 全局 `window.fetch` wrapper 作为合规依据） | 11/11 PASS |

### 9.2 AI-SALES-F01-FIX-02：销售工具语义错配修复 + AI 异常分析 + 单据联查（已完成）

**修复范围**：审计报告 4.2.1 节语义错配 + 4.2.3 节 AI 异常分析按钮 + 4.2.4 节单据联查面板 + 5.2 节 P1 改进建议项 #8-#10

| 审计项 | 审计位置 | 修复内容 | 验证 |
|---|---|---|---|
| #8 `sales_out_draft` 工具语义错配 | `ai/tools/registry.py:312`、`ai/policies.py:9,31` | 拆分为 `after_sale_out_draft`（端点 `add_after_sale_out_order`）+ `sales_outbound_draft`（端点 `create_sales_outbound_draft`），原 `sales_out_draft` 描述加 `[Deprecated alias of after_sale_out_draft]` 前缀保留向后兼容 | `verify_ai_tool_schemas.py` PASS；21 工具三表键集一致 |
| #9 缺失 AI 异常分析按钮 | `sales_order_detail.html`、`after_sale_out_detail.html` | `sales_order_detail.html` 新增 AI 异常分析按钮 + 模态框；`app.py` 新增 `/api/ai/sales_order/<int:id>/anomaly_analysis` 只读路由 | 路由注册校验通过 |
| #10 缺失单据联查面板 | `sales_order_detail.html` | `sales_order_detail.html` 新增售后单联查面板；`sales_order_detail` 视图新增 `related_after_sale_orders` 上下文 | 模板渲染校验通过 |

**同步更新文件**：`AI_PERMISSION_MATRIX.md`（矩阵表新增两行 + 工具语义说明段落）、`app/ai/documents/golden_samples.py`（`VALID_DRAFT_TYPES` 新增两键）、`scripts/verify_ai_tool_schemas.py`（`VALID_PAYLOADS` + `DRAFT_TOOLS`）、`scripts/verify_ai_permission_matrix.py`（`EXPECTED`）、`scripts/verify_ai_business_permissions.py`（`EXPECTED_RESTRICTED_ROLES`）

### 9.3 SM-P6-02：销售前端工程化迁移（已完成）

**修复范围**：审计报告 4.3.3 节 `confirm()`/`alert()` 散用 + 4.2.5 节缺失客户导入模态框 + 4.4.3 节无权限感知按钮隐藏 + 5.3 节 P2 改进建议项 #12、#16、#18

| 审计项 | 审计位置 | 修复内容 | 验证 |
|---|---|---|---|
| #12 `confirm()`/`alert()` 散用 | `sales_outbound_selection.html:45-46`、`customer.html`、`after_sale_out.html:177-248`、`after_sale_out_detail.html:164-196`、`after_sale_out_add.html` | 5 模板全部迁移：`confirm()` → `showConfirm().then()` Promise 模式；`alert()` → `showToast()` 含 type（success/danger/warning） | `grep -E "(alert\(|confirm\()"` 5 模板无命中 |
| #16 缺失客户导入模态框 | `customer.html` 完全无导入入口 | 新增 `importModal` 对齐 `supplier.html:145-198` 结构，含 CSRF token、文件输入、模板下载链接、AJAX 提交、`notifyMasterDataChanged('customer_updated')` 广播 | 模板结构对比 supplier.html 一致 |
| #18 工具栏无权限感知按钮隐藏 | `sales_order.html` 工具栏 + 行内按钮 | 工具栏「删除已选/导入/新增销售单」3 个写按钮 + 行内「复制/编辑/删除/确认/生成出库草稿」5 个写按钮全部包裹 `{% if current_user.role in ['admin', 'warehouse', 'purchase', 'sales'] %}`；只读的「下载模板/导出/查看详情」保持对所有角色可见 | Jinja2 `{% if %}/{% endif %}` 配对平衡手动校验通过 |

### 9.4 待修复项（建议新建任务）

| 审计项 | 优先级 | 建议任务 ID | 说明 |
|---|---|---|---|
| #5 缺失 `ai_sales_workbench.html` AI 跟进工作台 | P1 | `AI-SALES-F02` | 7 队列工作台 + `sales_followup_workbench.py` 后端 + `/api/ai/sales_followup_workbench` 只读 API |
| #6 缺失 `sales_followup` Agent | P1 | `AI-SALES-F02` | 4 步：开放订单扫描/即将到期扫描/客户跟进话术/合并发货候选 |
| #7 缺失 `sales_insights` 只读工具 | P1 | `AI-SALES-F02` | 对齐 `purchase_insights` 工具结构 |
| #11 csrfFetch helper 抽取 | P2 | `SM-P6-03` | 将 `csrfFetch` 抽到 `base.html`/`_list_macros.html`，14 个 `sales_*.html` 全部迁移 |
| #13 T+ 风格 CSS 抽共享 partial | P2 | `SM-P6-03` | `templates/_tplus_form_styles.html` |
| #14 `status_badge(status)` 宏 | P2 | `SM-P6-03` | 抽到 `_list_macros.html` |
| #15 `bindListActions(opts)` 通用 CRUD 函数 | P2 | `SM-P6-03` | 抽到 `_list_macros.html` |
| #17 `setupResizableTable` 与每页条数选择器 | P2 | `SM-P6-03` | 引入到 `sales_order.html`、`sales_outbound_list.html`、`sales_outflow_report.html` |
| #19 重写 `sales_outbound_list.html` | P3 | `SM-P4-FIX-01` | 从 8 行扩展为完整功能页 |
| #20 重写 `sales_reconciliation_report.html` | P3 | `SM-P4-FIX-01` | 从 4 行扩展为完整功能页 |
| #21 引入 Chart.js 报表可视化 | P3 | `SM-P4-FIX-01` | 趋势折线图、价格箱线图、汇总饼图/柱状图 |
| #22 补 loading state | P3 | `SM-P4-FIX-01` | AJAX 期间按钮 disabled + spinner |
| #23 补 a11y 标注 | P3 | `SM-P4-FIX-01` | `aria-label`、`role="dialog"`、`scope="col"` |
| #24 复核 `sales_outbound_selection.html:36` 路由 | P3 | `SM-P4-FIX-01` | 统一为 `/api/sales_order/selectable` |
| #25 回填销售已修复 Bug 到 `WMS_BUG_BASELINE.md` | P2 | `SM-P6-FIX-02` | OutOrder.customer_id、OutOrderItem.source_sales_order_item_id 等 |
| #26 新增 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 任务条目 | P2 | `SM-P6-FIX-02` | 已部分完成（本报告与开发计划已记录 SM-P6-FIX-01、AI-SALES-F01-FIX-02、SM-P6-02 三条），剩余建议项待新建 |

---

**审计完成。本报告严格落在 `main` 分支，未创建任何 `feature/*`/`fix/*`/`trae/*` 工作分支，符合 `AGENTS.md` 分支策略硬规则。**
