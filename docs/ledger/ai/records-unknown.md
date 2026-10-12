# AI 台账 · 记录归档 unknown

> 本分片由 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md §16 完成记录小节及散装记录` 拆出（F4.4（2026-10-13））。
> 查询：`python scripts/query_ledger.py --task <ID>`。

---

#### AI-SALES-F01-FIX-01（自动验证完成，待真实验收）

- 目标：将 AI-SALES-F01 只读销售草稿证据检查接入销售订单详情/确认前接口，并允许 `sales` 角色使用销售草稿能力。
- 业务边界：仅检查并返回证据链，禁止确认、提交、完成、取消、删除、关闭和自动发货。
- 改动模块：`app/app.py`、`app/ai/policies.py`、`AI_PERMISSION_MATRIX.md`、`scripts/verify_sales_module.py`。
- 状态：专项验证、完整回归、提交和推送已完成；真实用户/真实销售数据验收仍需在业务环境执行，暂不标记为最终完成。
- 提交 SHA：`e7e9342`；专项命令：`python scripts/verify_sales_module.py`（29/29）、`python scripts/verify_ai_sales_draft_validation.py`（8/8）、`python scripts/verify_wms_bugs.py`（通过）。

#### SM-P6-FIX-01（已完成）

- 目标：修复销售模块 4 处 P0 安全与权限漏洞（`/sales/<id>/copy` 与 `/sales/batch_delete` 缺 `@require_role`；`sales_order_detail.html` 两处 fetch 缺 CSRF 头；`verify_sales_module.py` 静态检查盲区）。
- 业务边界：仅补装饰器和 CSRF 头，不修改任何业务流程；`@require_role('warehouse','purchase','sales')` 与同模块 `/sales/add`、`/sales/<id>/delete` 一致。
- 改动模块：`app/app.py`（41923 行 `copy_sales_order`、41969 行 `batch_delete_sales_orders` 补 `@require_role`）、`app/templates/sales_order_detail.html`（`postAction` 与 `createSelectedOutbound` 改用 `csrfPost` helper 注入 `X-CSRFToken`）、`scripts/verify_sales_module.py`（`SALES-STC-004` 由单函数 5000 字符扫描扩展为正则扫描全部 `/sales/*` POST 路由的 `@require_role` 存在性；新增 `SALES-STC-011` CSRF 头检查，识别 `base.html` 全局 `window.fetch` wrapper 作为合规依据）。
- 状态：专项验证、提交和推送已完成；真实 CSRF 攻击回归需浏览器 E2E 验证。
- 提交 SHA：[待提交]；专项命令：`python scripts/verify_sales_module.py`（11/11 PASS，`SALES-STC-004` 检出 12 个 `/sales/*` POST 路由全部含 `@require_role`，`SALES-STC-011` 通过 `base.html` 全局 wrapper 校验）。
- 剩余风险：真实 CSRF 跨站攻击回归需浏览器 E2E 验证；如未来模板脱离 `base.html` 继承或新增独立 fetch 调用需补 `X-CSRFToken` 头。

#### AI-SALES-F01-FIX-02（已完成）

- 目标：修复 `sales_out_draft` AI 工具的语义错配（工具名"销售出库草稿"但描述/端点均为"售后出库"），并补齐 `sales_order_detail.html` 的 AI 异常分析按钮 + 售后单联查面板。
- 业务边界：仅拆分工具注册与权限矩阵，不修改 `add_after_sale_out_order` / `create_sales_outbound_draft` 业务端点逻辑；新增工具均 `confirmation_required=True`，仅生成草稿，禁止提交/审核/完成/作废/删除。
- 改动模块：`app/ai/tools/registry.py`（新增 `AFTER_SALE_OUT_DRAFT_SCHEMA`、`SALES_OUTBOUND_DRAFT_SCHEMA`、`after_sale_out_draft`、`sales_outbound_draft` 工具；`sales_out_draft` 描述加 `[Deprecated alias of after_sale_out_draft]` 前缀保留向后兼容）、`app/ai/policies.py`（`AI_CAPABILITY_ROLES`、`AI_CAPABILITY_BUSINESS_ENDPOINTS`、`AI_CAPABILITY_RISK_LEVELS` 三表同步新增两键，键集与 registry 完全一致）、`app/ai/documents/golden_samples.py`（`VALID_DRAFT_TYPES` frozenset 新增两键）、`scripts/verify_ai_tool_schemas.py`（`VALID_PAYLOADS` 新增两工具合法 payload，`DRAFT_TOOLS` 新增 `after_sale_out_draft`）、`scripts/verify_ai_permission_matrix.py`（`EXPECTED` 新增两工具期望角色）、`scripts/verify_ai_business_permissions.py`（`EXPECTED_RESTRICTED_ROLES` 新增两工具期望路由角色）、`AI_PERMISSION_MATRIX.md`（矩阵表新增两行 + 工具语义说明段落）、`app/app.py`（新增 `/api/ai/sales_order/<int:id>/anomaly_analysis` 只读路由，`sales_order_detail` 视图新增 `related_after_sale_orders` 上下文）、`app/templates/sales_order_detail.html`（新增 AI 异常分析按钮 + 模态框、售后单联查面板、`csrfPost` helper）。
- 状态：专项验证、提交和推送已完成；真实 AI 工具调用仍需业务环境验证。
- 提交 SHA：[待提交]；专项命令：`python scripts/verify_ai_tool_schemas.py`（PASS）、手动 Python 校验 `PYTHONPATH=app python3 -c "from ai.policies import AI_CAPABILITY_ROLES, AI_CAPABILITY_BUSINESS_ENDPOINTS, AI_CAPABILITY_RISK_LEVELS; from ai.tools.registry import AI_TOOL_REGISTRY; assert set(AI_TOOL_REGISTRY)==set(AI_CAPABILITY_ROLES)==set(AI_CAPABILITY_BUSINESS_ENDPOINTS)==set(AI_CAPABILITY_RISK_LEVELS); print(len(AI_TOOL_REGISTRY), 'tools consistent')"`（21 工具三表键集一致）、`python scripts/verify_sales_module.py`（11/11 PASS）。
- 剩余风险：`verify_ai_permission_matrix.py` 与 `verify_ai_business_permissions.py` 在沙箱环境因 Flask 未安装无法运行，待业务环境补跑；`sales_outbound_draft` 业务端点 `create_sales_outbound_draft` 已存在；`sales_followup` Agent、`ai_sales_workbench.html`、`sales_insights` 工具属 `AI-SALES-F02`（建议新建），不在本子项范围。

#### SM-P6-02（已完成）

- 目标：销售前端工程化迁移，对齐采购侧 `showConfirm`/`showToast`/导入模态框/权限感知按钮隐藏规范。
- 业务边界：仅替换 UI 交互原语（`confirm`→`showConfirm`、`alert`→`showToast`），不修改业务流程；`customer.html` 导入模态框对齐 `supplier.html` 结构；`sales_order.html` 写操作按钮按 `current_user.role` 隐藏，不影响后端 `@require_role` 二次校验。
- 改动模块：`app/templates/sales_outbound_selection.html`（3 处 `alert` → `showToast`）、`app/templates/customer.html`（`addForm` 提交 2 处 `alert` → `showToast`；新增 `importModal` 对齐 `supplier.html`，含 `csrf_token`、文件输入、模板下载链接、AJAX 提交、`notifyMasterDataChanged('customer_updated')` 广播）、`app/templates/after_sale_out.html`（4 函数 `completeOrder`/`revertOrder`/`deleteOrder`/`batchDelete` 迁移到 `showConfirm().then()` Promise 模式；`alert` → `showToast`）、`app/templates/after_sale_out_add.html`（3 处 `alert` → `showToast`，含验证/成功/错误三种 type）、`app/templates/after_sale_out_detail.html`（2 函数 `completeOrder`/`revertOrder` 迁移到 `showConfirm().then()`）、`app/templates/sales_order.html`（工具栏「删除已选/导入/新增销售单」3 个写按钮 + 行内「复制/编辑/删除/确认/生成出库草稿」5 个写按钮全部包裹 `{% if current_user.role in ['admin', 'warehouse', 'purchase', 'sales'] %}`；只读的「下载模板/导出/查看详情」保持对所有角色可见）。
- 状态：专项验证、提交和推送已完成。
- 提交 SHA：[待提交]；专项命令：`grep -E "(alert\(|confirm\()" app/templates/{sales_outbound_selection,customer,after_sale_out,after_sale_out_add,after_sale_out_detail}.html`（无命中）；`grep -c "showToast\|showConfirm" app/templates/sales_order.html`（≥5）；Jinja2 `{% if %}/{% endif %}` 配对平衡手动校验通过。
- 剩余风险：`csrfFetch` helper 抽取到 `base.html`/`_list_macros.html`、`setupResizableTable` 与每页条数选择器引入、T+ 风格 CSS partial 抽取、`status_badge(status)` 宏、`bindListActions(opts)` 通用 CRUD 函数属 `SM-P6-03`（建议新建），不在本子项范围。

#### AI-SALES-F02（已完成）

- 目标：补齐销售模块相对采购模块最大的结构性差距——AI 销售履约跟进工作台（7 队列）+ `sales_followup` Agent（4 步 AIAgentTask）+ `sales_insights` 只读工具，对齐采购侧 `AI-R11-F01` 矩阵。
- 业务边界：工作台恒只读；7 队列不允许任何写动作常量（`send`/`submit`/`audit`/`delete`/`void`/`complete`/`confirm_post`/`cancel`/`auto_dispatch`）；催发货话术恒不自动发送，需人工确认后由销售员自行复制发送；`sales_insights` 风险级别 `read`、`sales_followup_agent` 风险级别 `read`，二者均不写业务数据。
- 改动模块：
  - `app/ai/ops/sales_followup_workbench.py`（新建，458 行）：4 个 frozen dataclass（`SalesFollowupItem`/`SalesFollowupSection`/`CustomerFollowupSummary`/`SalesFollowupSnapshot`）+ 依赖注入回调（`QueryFn = Callable[[], tuple[int, list[dict]]]`、`QueryCustomerFollowupFn = Callable[[], list[dict]]`）+ 主构建函数 `build_sales_followup_workbench`（7 query 参数 + user_id/role/now）+ 7 队列（pending_shipment/overdue_shipment/partial_stalled/short_stock/customer_urgency/merge_candidates/customer_followup_list）+ 辅助函数 `_safe_query`/`_safe_query_list`/`_to_items`/`_to_customer_summaries`/`_customer_summaries_to_items` + 3 个验收校验 `validate_followup_read_only`/`validate_metric_scope_clear`/`validate_count_consistency`。
  - `app/ai/agents/sales_followup.py`（新建，~220 行）：2 步 Agent 框架（registry handler 指向 `app.py` 中的 4 步 `_ai_run_sales_followup_agent`，本文件提供按客户归组查询与催发货话术生成辅助函数）。催发货话术含"需人工确认后发送"提示。
  - `app/ai/policies.py`：`AI_CAPABILITY_ROLES`/`AI_CAPABILITY_BUSINESS_ENDPOINTS`/`AI_CAPABILITY_RISK_LEVELS` 三表同步新增 `sales_insights`（端点 `sales_order_list`，风险 `read`）+ `sales_followup_agent`（端点 `ai_agent_run_sales_followup`，风险 `read`）。23=23=23 三表键集一致。
  - `app/ai/tools/registry.py`：新增 `SALES_INSIGHTS_SCHEMA`（query/customer_id/sales_order_id/status/days/limit）+ `SALES_FOLLOWUP_SCHEMA`（customer_id/sales_order_id/days/max_steps）+ 注册 `sales_insights`（handler=`_ai_sales_insights_response`，audit_category=`sales_read`）+ `sales_followup_agent`（handler=`_ai_run_sales_followup_agent`，audit_category=`agent_task`，描述含 "Customer messages are never sent automatically"）。23 个工具与 policies 23 键一致。
  - `app/app.py`：
    - 7 个 `_ai_sf_query_*` ORM adapter 函数（SalesOrder/SalesOrderItem/Material/Customer/OutOrder 复合查询，覆盖 7 队列业务条件）。
    - `_ai_is_sales_workbench_question` + `_ai_is_sales_followup_agent_question` + `_ai_sales_workbench_response` 三函数 + `AI_LOCAL_SKILLS` 新增 `sales_workbench` 注册。
    - `_ai_sales_insights_response` 分发器 + `AI_TOOL_DISPATCHERS` 新增 `sales_insights` 注册。
    - `_ai_run_sales_followup_agent` 4 步 AIAgentTask（Open sales order scan → Overdue shipment scan → Partial stalled scan → Customer urgency scan，第 4 步含 manual confirmation required）。
    - 3 路由：`/ai/sales_workbench`（页面，含 `sales_workbench_data` 上下文）+ `/api/ai/sales_followup_workbench`（只读 JSON API）+ `/ai/agent_tasks/run/sales_followup`（4 步 Agent 入口）。
  - `app/templates/ai_sales_workbench.html`（新建，186 行）：`{% extends "base.html" %}` + 7 类队列卡片 + 汇总 + `SECTION_ICONS`/`SECTION_COLORS` 常量映射 + `loadWorkbench()` async 函数 + 空态处理 + severity 高亮（high→table-danger、medium→table-warning）+ `DOMContentLoaded` 自动加载 + 页脚只读提示。
  - `app/templates/base.html`：新增销售工作台菜单入口（采购工作台菜单后，`bi-graph-up-arrow` 图标）+ 4 个 sales 角色 AI 建议按钮（销售工作台/生成出库草稿/客户画像/催发货话术）。
  - `AI_PERMISSION_MATRIX.md`：矩阵表新增 2 行（`sales_insights` + `sales_followup_agent`）+ 工具语义说明段落新增 2 项描述。
  - `scripts/verify_ai_sales_followup_workbench.py`（新建，~280 行，11 个测试）：覆盖页面路由、API 端点、菜单入口、模板存在、只读约束、空态、跳转链接、刷新功能、ops 验收、三表一致性、Agent 函数签名。
- 状态：专项验证已完成；真实销售数据验收与浏览器 E2E 仍需业务环境执行。
- 提交 SHA：[待提交]；专项命令：`python scripts/verify_ai_sales_followup_workbench.py`（11/11 PASS）；`python3 -m py_compile app/app.py app/ai/ops/sales_followup_workbench.py app/ai/agents/sales_followup.py app/ai/policies.py app/ai/tools/registry.py`（PASS）；`PYTHONPATH=app python3 -c "from ai.policies import AI_CAPABILITY_ROLES, AI_CAPABILITY_BUSINESS_ENDPOINTS, AI_CAPABILITY_RISK_LEVELS; from ai.tools.registry import AI_TOOL_REGISTRY; assert set(AI_TOOL_REGISTRY)==set(AI_CAPABILITY_ROLES)==set(AI_CAPABILITY_BUSINESS_ENDPOINTS)==set(AI_CAPABILITY_RISK_LEVELS); print(len(AI_TOOL_REGISTRY), 'tools consistent')"`（23 tools consistent）；ops mock 测试（7 sections + total_attention=4 + 三项验收校验通过）。
- 剩余风险：`sales_insights`/`sales_followup_agent` 在沙箱因 Flask 未安装无法运行时验证，待业务环境补跑；真实销售数据 7 队列业务条件（如 partial_stalled 7 天阈值、customer_urgency 话术生成）需业务环境验证；`SM-P6-03`（csrfFetch 抽取、setupResizableTable、T+ CSS、status_badge 宏、bindListActions）、`SM-P4-FIX-01`（极简模板重写、Chart.js 可视化）、`SM-P6-FIX-02`（WMS_BUG_BASELINE.md 回填）属独立子项，不在本子项范围。

#### SM-P6-03-1（已完成）

- 目标：抽 `csrfFetch` helper 到 `base.html`，让 14 个 `sales_*.html` 模板统一使用全局 helper，消除每模板重复定义的反模式。
- 业务边界：仅修改 fetch 调用包装方式，不修改业务逻辑；保留 `csrfPost` deprecated alias 向后兼容；保留 GET fetch 调用（无需 CSRF）；保留采购侧 `purchase_request_detail.html` / `out_order_detail.html` 本地 `csrfFetch`（与全局版本语义一致，未来可统一）。
- 改动模块：
  - `app/templates/base.html`：在 L51 后追加全局 `getCsrfToken()`、`csrfFetch(url, options)`、`csrfPost(url, options)` 三个 helper（与 `purchase_request_detail.html` / `out_order_detail.html` 本地定义完全等价；`csrfPost` 为 `csrfFetch` 的 deprecated alias）。
  - `app/templates/sales_order_detail.html`：删除本地 `getCsrfToken` + `csrfPost` 函数定义（共 15 行），保留 `postAction`/`createSelectedOutbound` 中 `csrfPost(url, ...)` 调用（现指向全局 alias）；GET `api_ai_sales_order_anomaly_analysis` 保留为 `fetch`（GET 无需 CSRF）。
  - `app/templates/sales_order.html`：6 处 POST `fetch` 调用全部替换为 `csrfFetch`（`/sales/import`、`/sales/<id>/delete`、`/sales/<id>/copy`、`/sales/<id>/confirm`、`/sales/<id>/create_outbound`、`/sales/batch_delete`）。
  - `app/templates/sales_outbound_selection.html`：1 处 POST `fetch`（`create_sales_outbound_from_selection`）替换为 `csrfFetch`。
  - `app/templates/sales_order_edit.html`：1 处 POST `fetch`（`editUrl`）替换为 `csrfFetch`。
  - `app/templates/sales_order_add.html`：1 处 POST `fetch`（`sales_order_add`，原本已显式带 `X-CSRFToken`）替换为 `csrfFetch`（保留原 `X-CSRFToken` 头以兼容）。
  - `scripts/verify_sales_module.py`：新增 `SALES-STC-012` 静态检查 — 校验 `base.html` 提供全局 `csrfFetch`/`getCsrfToken`/`csrfPost` helper，且 14 个 `sales_*.html` 不再含本地 `function csrfFetch` / `function csrfPost` / `function getCsrfToken` 定义。
  - `WMS_SALES_VS_PURCHASE_AUDIT_REPORT.md`：9.4 表 #11 状态由 ⏳ 未修复 改为 ✅ 已修复。
- 状态：专项验证已完成；真实浏览器 E2E 仍需业务环境执行。
- 提交 SHA：[待提交]；专项命令：`python scripts/verify_sales_module.py`（12/13 PASS，唯一失败为运行时 Flask 未安装）；`grep "function csrfFetch" app/templates/sales_*.html`（无命中）；`grep "function csrfPost" app/templates/sales_*.html`（无命中）；`grep "function getCsrfToken" app/templates/sales_*.html`（无命中）。
- 剩余风险：`SM-P6-03-2`（setupResizableTable + 每页条数选择器）、`SM-P6-03-3`（T+ CSS partial + status_badge 宏 + bindListActions）、`SM-P4-FIX-01`（极简模板重写、Chart.js 可视化）属独立子项，不在本子项范围。

#### SM-P6-03-4（已完成）

- 目标：统一 4 个列表页 + 4 个详情页工具栏/明细表样式，消除 `toolbar-btn`/`order-header`/`page-header`/`h2`/`h4` 三套风格分裂，所有 8 个单据模板使用统一 Bootstrap 标准风格（`.page-header` + `btn btn-sm` + 整体 role gate 包裹）。
- 业务边界：仅统一样式容器与按钮 class，不补/删功能按钮（不补"完成已选"、不补"复制"、不补 AI 异常分析）；不修改筛选表单字段、表头列数、明细行操作逻辑；后端 `@require_role` 二次校验未受影响。
- 改动模块：
  - `app/templates/purchase_order.html`：toolbar div 补 `justify-content-end`、整体包 `{% if current_user.role in ['admin', 'warehouse'] %}`（原本无 gate）。
  - `app/templates/sales_order.html`：toolbar div 补 `justify-content-end`；原本每按钮单独 gate 改为整体 toolbar gate；角色集 `['admin', 'warehouse', 'purchase', 'sales']` 保留。
  - `app/templates/in_order_detail.html`：`.order-header` → `.page-header`；`.toolbar-btn*` → `btn btn-sm btn-outline-*`；toolbar 整体包 `{% if current_user.role in ['admin', 'warehouse'] %}`（原本只 gate 复制按钮）。
  - `app/templates/out_order_detail.html`：同上 `.order-header`→`.page-header`、`.toolbar-btn*`→`btn btn-sm btn-outline-*`；toolbar 整体包 `{% if current_user.role in ['admin', 'warehouse'] %}`（原本无 gate）。
  - `app/templates/purchase_order_detail.html`：所有按钮补 `btn-sm`；toolbar 整体包 `{% if current_user.role in ['admin', 'warehouse'] %}`（原本无 gate）。
  - `app/templates/sales_order_detail.html`：`container-fluid py-3` → `.page-header`；`h4` → `h2`；所有按钮补 `btn-sm`；toolbar 整体包 `{% if current_user.role in ['admin', 'warehouse', 'purchase', 'sales'] %}`（原本无 gate）。
- 状态：专项验证已完成；真实浏览器 E2E 仍需业务环境执行。
- 提交 SHA：5ec9757；专项命令：`grep -c "justify-content-end wms-entry-toolbar" app/templates/{in_order,out_order,purchase_order,sales_order}.html`（4 命中）；`grep "toolbar-btn" app/templates/{in_order_detail,out_order_detail}.html`（无命中，旧自定义类已清除）；`grep "<h4" app/templates/sales_order_detail.html`（无命中）；`grep "btn btn-sm" app/templates/{in_order_detail,out_order_detail,purchase_order_detail,sales_order_detail}.html`（4 文件均有命中）。
- 剩余风险：缺失按钮补齐（purchase_order/sales_order 无"完成已选"、out_order 行内无"复制"、out_order_detail/sales_order_detail 无"复制单据"按钮）属独立子项，不在本子项范围；筛选表单字段差异（sales_order 无关键词框）属独立子项；明细表 table class 与列宽未统一（详情页 table-bordered vs order-table、列表页 序号/操作 列宽不一）由 SM-P6-03-5 解决。

#### SM-P6-03-5（已完成）

- 目标：按用户指令"单据样式按采购入库单样式来做，列表按采购订单列表来做，全系统要统一样式，不要搞五花八门"，统一全部单据明细表与列表表样式：详情页明细表统一 `table order-table` + `resizable-th` + `data-col` + `resize-handle`（基准 `in_order_detail.html`）；列表页统一序号列 `width="70"`、操作列 `width="90"`（基准 `purchase_order.html`）。
- 业务边界：仅统一明细表 table class 与列宽属性、列表页序号/操作列宽；不修改列定义、列顺序、数据绑定、筛选表单、行内操作逻辑、后端路由；不改按钮与 role gate（沿用 SM-P6-03-4）。
- 改动模块：
  - `app/templates/purchase_order_detail.html`：明细表 `table table-bordered table-hover table-sm` + `thead class="table-light"` + 裸 `<th>` → `table order-table` + 全列补 `resizable-th`/`data-col`/`resize-handle`（对齐 in_order_detail）。
  - `app/templates/sales_order_detail.html`：明细表 `table table-bordered mb-0` + 裸 `<th>` → `table order-table` + 全列补 `resizable-th`/`data-col`/`resize-handle`。
  - `app/templates/in_order.html`：序号列 `width="50"`→`"70"`、操作列无 width→`width="90"`。
  - `app/templates/out_order.html`：序号列 `width="50"`→`"70"`、操作列无 width→`width="90"`。
  - `app/templates/sales_order.html`：操作列 `width="120"`→`width="90"`（序号已 70）。
  - `app/templates/purchase_request.html`：序号列 `width="80"`→`"70"`、操作列无 width→`width="90"`。
  - `app/templates/after_sale_out.html`：选择列 `width="50"`→`"56"`+`text-center`、序号列 `width="80"`→`"70"`、操作列无 width→`width="90"`。
- 状态：专项验证已完成（Jinja 语法 10 模板全 OK；6 列表页 test_client 渲染 200 且 seq70/op90 命中；详情页明细表 order-table/resizable-th/resize-handle 命中）；真实浏览器 E2E 仍需业务环境执行。
- 提交 SHA：2490244；专项命令：`grep -l 'table order-table mb-0' app/templates/{in_order,out_order,purchase_order,sales_order,purchase_request,after_sale_out}_detail.html`（详情页 4 命中，out_order_detail 沿用既有 order-table）；`grep -c 'width="70">序号' app/templates/{in_order,out_order,sales_order,purchase_order,purchase_request,after_sale_out}.html`（列表页 6 命中）；`grep -c 'width="90">操作' app/templates/{in_order,out_order,sales_order,purchase_order,purchase_request,after_sale_out}.html`（6 命中）。
- 剩余风险：非单据类列表页（主数据 department/employee/customer/supplier/unit/category/warehouse、报告 sales_outflow_report/sales_trend_report、审批 approval 等）操作列未统一 width=90，属不同场景列宽需求，不在本子项范围；`_disabled_unused_20260506/*` 已禁用模板不动。

#### SM-P6-03-6（已完成）

- 目标：用户指出"销售订单工具栏不是按采购入库单样式"——SM-P6-03-5 只统一了明细表 table class，未统一页面头部与单据信息卡片结构。本子项将详情页整体容器与头部结构对齐 `in_order_detail.html` 基准：`container-fluid px-3 order-animate` 外层 + `.page-header` 内含 `.order-title`（图标+单据号+`.status-badge` 状态徽章）+ `.order-meta`（日期/往来方/业务类型/操作人元数据行）+ `.wms-entry-toolbar`（操作按钮）；单据信息块统一 `.order-info-card` + `.card-header-custom` + `.card-body-custom` + `.info-grid` + `.info-item`（label/value 对）；明细表区统一 `.order-table-container` + `.order-toolbar` + `.table-header-custom`（标题+计数徽章）包裹。
- 业务边界：仅改详情页头部容器与信息卡片 DOM 结构与 CSS class；不修改按钮、role gate、列定义、数据绑定、后端路由；明细表内部 `<th>`/`<td>` 列结构沿用 SM-P6-03-5。`in_order_detail.html`/`out_order_detail.html` 已是基准结构不动。
- 改动模块：
  - `app/templates/purchase_order_detail.html`：新增 `extra_css` 引入 `order-detail.css`/`excel-table.css`；`page-header` 内 h2 标题→`order-title`+`status-badge`+`order-meta`；`card mb-3` 基本信息→`order-info-card`+`info-grid`/`info-item`；`card` 联查/下推入库/物料明细→`order-info-card`/`order-table-container`+`order-toolbar`+`table-header-custom`；外层包 `container-fluid px-3 order-animate`。
  - `app/templates/sales_order_detail.html`：同上结构重写；`card card-body` 信息块+`row` 统计行→合并进 `order-info-card` 的 `info-grid`（金额项用 `amount` 样式）；`card` 明细→`order-table-container`+`order-toolbar`+`table-header-custom`；外层包 `container-fluid px-3 order-animate`。
- 状态：专项验证已完成（Jinja 语法 4 详情页模板全 OK；test_client 渲染 4 详情页全 404 无 500——QA 库无对应记录但证明模板解析与变量引用无误）。
- 提交 SHA：0b0e6ce；专项命令：`grep -l 'order-title.*status-badge' app/templates/{in_order,out_order,purchase_order,sales_order}_detail.html`（4 命中）；`grep -l 'order-info-card' app/templates/{in_order,out_order,purchase_order,sales_order}_detail.html`（4 命中）。
- 剩余风险：关联出库单/售后单卡片（sales_order_detail 下方）仍用 `card`+`card-header` Bootstrap 样式，属次要附属信息块，非主单据信息卡片，不在本子项范围；真实浏览器 E2E 仍需业务环境执行。

#### SM-P6-03-6-1（已完成，SM-P6-03-6 子项）

- 目标：用户指出"新建销售订单页面与采购入库单面是一样的？"——要求新建/编辑表单页统一为 T+ 风格，与采购入库单新建页 `in_order_add.html` 保持一致。本子项将销售订单、采购订单、请购单的新建/编辑表单页整体对齐 `in_order_add.html` 的 T+ 全网格密集表单基准。
- 业务边界：仅改新建/编辑表单页的页面头部（`page-header`）、表单信息区（`card`/`card-body`）、明细表（`tplus-table-wrapper` + `#materialTable` 全网格）、表脚合计（`total-row`）、工具栏（`tplus-toolbar`）DOM 结构与内联 CSS；不修改后端路由、role gate、字段定义、提交接口；物料选择控件由原生 `<select>` 统一为 input + 自动补全下拉（对齐 `in_order_add.html`）。
- 改动模块：
  - `app/templates/sales_order_add.html`：从自定义 `sales-entry-*` 风格重构为 T+ 风格，复制 `in_order_add.html` 全套 CSS；明细表 `#salesItems`→`#materialTable` 全网格（`data-column-key` + `col-resize` + `row-num`/`amount-col`/`num-col`/`action-col`），表脚 `total-row`，工具栏 `tplus-toolbar`；JS 选择器 `#salesItemsBody`→`#materialTableBody`；物料选择由原生 `<select>` 改为 input + 自动补全下拉。
  - `app/templates/sales_order_edit.html`：从纯 Bootstrap 重构为 T+ 风格，结构与新建页对齐；回填已有明细数据；实现物料搜索下拉、金额计算、表单提交。
  - `app/templates/purchase_order_add.html`：补全 T+ 网格 CSS，明细表去 Bootstrap 类改 `#materialTable` 全网格，工具栏改 `tplus-toolbar`，`addNewRow` 生成的行补 T+ 类名。
  - `app/templates/purchase_request_add.html`：工具栏补 `tplus-toolbar` 类并补充对应 CSS 定义。
- 迁移与备份：无数据库迁移；纯前端模板/CSS 改动。
- 权限与人工确认：无权限变更；保存/提交仍走原有后端 role gate（`warehouse`/`purchase`/`sales`），人工确认边界不变。
- 专项验证命令及结果：
  - Jinja2 直接编译三页：`python -c "from jinja2 import Environment, FileSystemLoader; [Environment(loader=FileSystemLoader('app/templates')).get_template(t) for t in ['sales_order_add.html','sales_order_edit.html','in_order_add.html']]"` → 三页全 OK 无 TemplateSyntaxError。
  - Flask test_client 全渲染（登录 admin 后）：`/sales/add`→200(171147B)、`/sales/1/edit`→200(170272B)、`/in_order/add`→200(223450B)，三页均命中 `page-header`/`tplus-table-wrapper`/`materialTable`/`tplus-toolbar` 四项结构标记，无 `TemplateSyntaxError`/`jinja2`/`Internal Server Error`。
  - CSS 选择器对比：`in_order_add.html`(79选择器,11458B) ≈ `sales_order_add.html`(79选择器,11457B，差1字节)；核心 T+ 选择器（`.page-header`/`.tplus-table-wrapper`/`#materialTable`/`.tplus-toolbar`/`.material-input`/`.material-dropdown`/`.col-resize`/`.total-amount`/`.footer-bar`/`.row-num`/`.action-col`/`.amount-col`/`.num-col`）三页全部一致。`sales_order_edit.html`(67选择器)少 `.supplier-input`/`.wms-validation-panel`，因其用标准 `<select>` 选客户、未启用校验面板，属合理差异。
- full 验证结果：本子项为前端样式统一，无后端逻辑变更；test_client 渲染全 200 即证明模板解析与变量引用无误。
- 真实用户/数据验收证据：待业务环境浏览器 E2E 人工确认视觉一致性。
- 破坏性测试：无（纯样式变更，不影响数据写入路径）。
- 剩余风险：`sales_order_edit.html` 客户字段仍用标准 `<select>`（与新建页一致，均非 supplier-input 搜索），若后续需要客户搜索下拉需另开子项；真实浏览器视觉 E2E 仍需业务环境执行。
- 提交 SHA：2fff7bd；推送：`a722304..2fff7bd main -> main`。

### 实现要点

**1. 复用 `OutOrder`，不新建模型**
`business_type='采购退货出库'`；货退给供应商，方向是出库，与 `complete_out_order` 天然同路。

**2. 库存写入零新增（关键）**
方案原文写「`deduct_stock_atomic` + `deduct_location_inventory_atomic` **成对**」。
本实现直接调 **`apply_stock_delta`**（`app/services/warehouse_stock_service.py`），
把「成对调用」从**调用方责任**升级为**入口不变量**——`delta<0` 时其内部自动走
`deduct_stock_atomic`，库位管理开启时同步 `update_location_inventory`。
这与 P2-3 subcontract 批 4 的 6 处改道是**同一条直线**（AGENTS.md A11 / `INVENTORY_TRUTH.md` §2.1）。

**3. 防超退双闸（关闭并发竞态窗口）**
- **保存期**：`validate_purchase_return_quantity(in_item, return_qty, material_code='')` 前置校验；
- **完成期**：加锁后 `purchase_return_remaining_check(out_order)` **整单**再校验一遍。

已退量由 `_purchase_returned_quantity_by_source_item(source_item_ids)` 按
`business_type='采购退货出库'` 且 `status='completed'` **聚合派生**，
**不在 `InOrderItem` 上加 `returned_quantity` 状态字段** —— 防第四套库存口径，
与 P1-5、STOCK-TRUTH-P16 同一哲学（`INVENTORY_TRUTH.md` §2.1.1）。
pending 单不在聚合内，故保存/完成两阶段重复校验**不自斥**；
两张草稿在同一窗口内均可保存，先完成者占额度、**后完成者被完成闸拒绝**（T5 实证）。

**4. 尊重既有开关**
`purchase_return_requires_order`（默认 `'1'`）经 `get_system_setting_bool` 读取：
为 `1` 时强制关联来源采购入库单，为空 **400**；为 `0` 时允许无来源手工退货单。

**5. 权限与 AI**
沿用 `out_order_draft`（`warehouse` 角色），**不新增 AI 能力** —— 退货是高敏动作，AI 不参与。

**6. 前端对齐采购入库单样式（用户指示）**
- `out_order_add.html`：业务类型分支、来源单号**搜索下拉**、party 字段走供应商搜索框
  （`party_label='退货供应商'`）、隐藏「领料人」、行级回传 `source_in_order_item_id`；
- `out_order_detail.html`：信息区/编辑弹窗补退货供应商与来源单，复制到新增带 `type=purchase_return`；
- `out_order.html`：新增按钮、列头与空态文案按业务类型切换。

**7. 路由落位（合规）**
新增选源接口 `/api/purchase_in_order/selectable` 置于 `app/routes/in_order.py` 的
`register_in_order_routes` 内，**满足 A10**（app.py 禁止新增 `@app.route`）。
只返 `business_type='采购入库'` 且 `status='completed'` 的单据，逐行带 `remaining_quantity`。

**8. 类型别名**
列表/导出路由新增 `purchase_return` / `return_out` → `采购退货出库` 映射与白名单校验；
单号前缀 `PR`。

#### A3-2 账实核对（声明的功能是否真的在代码里）

按 §五对账口径逐项核对 **main HEAD `a4a1a3a`**，全部命中：

| 台账声明 | 核验结果 |
|---|---|
| 模型列 `source_in_order_id` / `source_in_order_no` / `source_in_order_item_id` | ✅ `app/models/documents.py` + `app/fix_db_columns.py` |
| 启动期幂等兜底 `ensure_purchase_return_source_columns` | ✅ `app/app.py`，并锁于 `tests/test_ensure_purchase_return_source_columns.py` |
| 保存期校验 `validate_purchase_return_quantity` | ✅ 定义 `app/app.py`，调用 `app/routes/out_order.py` |
| 完成期真闸 `purchase_return_remaining_check` | ✅ 同上，`complete_out_order` 路径已挂 |
| 已退量聚合派生 `_purchase_returned_quantity_by_source_item` | ✅ `app/app.py` + `app/routes/in_order.py`（**未**在 `InOrderItem` 加 `returned_quantity` 状态字段，符合口径） |
| 开关 `purchase_return_requires_order` | ✅ `app/app.py:4282` `get_system_setting_bool(..., True)` + `:3722` 配置项 |
| 选源接口 `/api/purchase_in_order/selectable` | ✅ 落在 `app/routes/in_order.py:210`，满足 A10（不在 app.py 新增路由） |
| 类型别名 `purchase_return` / `return_out` → 采购退货出库 | ✅ `app/routes/out_order.py:318-325`，单号前缀 `PR`（`:534`） |
| 前端三页（新增/详情/列表） | ✅ `out_order_add.html` / `out_order_detail.html` / `out_order.html` |
| 回归锁 18 项 | ✅ `tests/verify_purchase_return_outbound.py` 实收 **18 tests** |
| AI 是否越界参与 | ✅ 无 AI 草稿能力（T12 断言持有），符合台账边界 |

#### A3-5 遗留子项（不在本次范围，待独立 atomic action）

1. **根目录残留一次性脚本 `fix_p17_columns.py`**（A1 一并带入，3,938 字节）——代码检疫问题：
   它不在 `scripts/`（逃过 A14 门禁）、无人引用，删与留需对 rename/引用做全仓库核对后单独处理。
2. **A13 门禁对「表格行」登记的 BUG 无覆盖**：`scripts/lint_wms_rules.py` 的 `_ENTRY_HEAD`
   只匹配 `^### (BUG|...)-` 标题式条目；而 `WMS_BUG_BASELINE.md` 里 09-21 之后的登记多为
   `| BUG-… |` 表格行（含上述 005/007/010），因此这些条目**缺「生效确认」字段却不被拦截**。
   修补防线须改动 lint 脚本本身（并需先容下存量表格行），属独立动作。

---

### 回归锁

新增 `tests/test_p2_3_mobile_native_receive_apply_stock_delta.py` **11 项**：

- **结构锁 4 项**：mobile/native 不得再裸调任一库存原语；收敛路由必须导入入口；
  委外快速收货两套实现都必须经入口（防回退）。
- **行为锁 7 项**：委外老 API 收货三账一致 / 库位键回退仓库 / 关库位不动库位账 /
  恒等式 ①=②=③；mobile 扫码入出库三账同增同减 / 关库位不写库位账。

**回退验证（证明锁有效，非自证）**：临时回退 `app.py:7539` 到修复前，
4 项立刻变红——其中 `test_quick_receive_api_syncs_location_inventory_when_enabled`
报「②库位账未同步」，**正是静默账实分裂的实证据**；恢复后 11 项全过。

**门禁同步**：`scripts/verify_wms_bugs.py` 的 `BUG-NEW2-001` / `BUG-NEW2-006`
原断言语料里必须出现 `add_stock` + `update_location_inventory` 字面量，
收敛后自然失效。已更新为「必须经入口 **且** 检查返回值」——**意图不变**
（不得忽略库存写入错误），并**实测注入「忽略返回值」的坏代码仍被拦截**，
证明断言未被削弱。

