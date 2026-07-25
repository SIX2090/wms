# WMS BUG 基线

更新时间：2026-07-26

用途：把已经核验过的问题固定下来，避免不同 AI 模型每天重复报告同一批“疑似 BUG”。后续扫描结果必须先对照本文件：已修复项看回归，误报项不重复报，暂缓项只在风险条件变化时重新评估。

## 判定规则

| 类型 | 进入条件 | 处理方式 |
|------|----------|----------|
| 真实 BUG | 有代码证据、可触发路径、错误结果 | 修复并加入回归验证 |
| 风险项 | 理论可触发，但依赖配置或边界条件 | 记录缓解措施，必要时加监控 |
| 配置项 | 生产环境需要强制配置或关闭调试 | 固化配置检查 |
| 误报 | 代码已有保护，或不符合实际业务流程 | 记录原因，不重复报 |
| 暂缓 | 技术限制或迁移成本较高 | 明确风险和后续条件 |

## 已修复并纳入回归

| 编号 | 问题 | 回归检查 |
|------|------|----------|
| BUG-001 | commit 失败后仍返回 success | `scripts/verify_wms_bugs.py` 检查高风险回归模式 |
| BUG-002 | 库存扣减无事务隔离 | 检查 `deduct_stock()` 委托原子扣减，避免读改写扣减 |
| BUG-004 | 仓库/部门新增编辑删除缺异常处理 | 人工代码审查加自动高风险扫描 |
| BUG-005 | 物料复制编码硬编码 6 位 | 检查复制编码函数不再依赖固定 6 位 |
| BUG-006 | 期初库存调整无锁 | 检查使用库存原子增量更新 |
| BUG-009 | document 事件监听器泄漏 | 检查重复绑定前移除旧 handler |
| BUG-010 | ExcelTable cloneNode 清监听器副作用 | 检查不再使用 cloneNode 替换单元格 |
| BUG-011 | 重复创建导入模态框 | 检查已有模态框时直接复用 |
| BUG-012 | 导出列错位 | 检查按导出列映射数据 |
| VULN-001 | 打印 HTML 净化失败返回空 | 检查异常时返回安全错误 HTML |
| CONF-001 | 生产环境 SECRET_KEY 未强制 | 检查 production 必须配置 SECRET_KEY 或显式允许自动密钥 |
| CONF-002 | 开发配置默认 SQL_ECHO | 检查默认不启用 SQL 日志 |
| CONF-004 | SQLite 并发限制 | 检查启用 WAL、busy_timeout、外键 |
| VULN-003 | 部分 POST 表单缺 CSRF 字段 | 检查模板中普通 POST 表单含 `csrf_token` |
| VULN-004 | 密码强度不一致 | 检查新增用户和重置密码复用同一强度校验 |
| BUG-NEW-001 | 删除已完成入库单遗漏库位库存回退 | 检查 `delete_in_order()` 删除 completed 单据时调用 `update_location_inventory()` |
| BUG-NEW-003 | 采购入库来源规则不一致 | 采购入库允许手工录入，采购订单仅为可选来源；有关联订单时继续校验来源和数量 |
| BUG-NEW-005 | 默认密码策略不一致 | 已统一为优先使用 `WMS_BOOTSTRAP_PASSWORD`，未设置且首次创建管理员时使用 `admin`；安装和启动不得重置已有密码 |
| BUG-NEW-008 | 微信分享默认配置硬编码私人信息 | 检查源码不含私人姓名/微信号默认值 |
| BUG-NEW-009 | Excel 导入组件列名拼入 HTML 存在 XSS 风险 | 检查必填列通过 `textContent` 写入 |
| BUG-NEW-013 | 入库单下推缺少来源和数量控制 | 采购入库、其他入库可下推领料、其他出库和售后出库草稿；必须校验完成状态、可下推数量、幂等及客供阻断 |
| BUG-NEW-014 | 批量完成出库单失败回滚后计数和事务不一致 | 检查每张出库单独立提交，失败单独回滚 |
| BUG-NEW-015 | 单号生成固定截取末尾 4 位 | 检查按前缀+年月后的完整数字后缀递增 |
| BUG-NEW2-001 | 入库路径未检查 `add_stock()` 返回值 | 检查 Android 入库、手机扫码入库等核心路径失败即回滚 |
| BUG-NEW2-002 | 入库路径未检查库位库存更新返回值 | 检查 Android 入库和手机扫码入库库位失败即回滚 |
| BUG-NEW2-003 | 期初库存并发更新读取旧值缺少锁 | 检查期初库存新增/编辑/批量保存读取时使用 `with_for_update()`，库存更新仍用原子增量 |
| BUG-NEW2-004 | 盘点完成直接改库存或不生成调整单 | 检查普通盘点和扫码盘点完成后生成库存调整草稿，库存变化由调整单提交执行 |
| BUG-NEW3-001 | `add_stock()` 返回值未检查导致流水和库存可能不一致 | 检查所有 `add_stock()` 调用必须接收并处理返回值 |
| AI-AUTH-001 | AI 草稿和敏感分析权限校验分散，存在能力扩展后越权风险 | 检查 AI 草稿、文档确认和敏感分析统一通过 `AI_CAPABILITY_ROLES` 校验 |
| AI-AUTH-002 | 销售 AI 能力 `sales_insights` / `sales_followup_agent` 上线后未纳入权限矩阵自动化覆盖 | 检查 `scripts/verify_ai_permission_matrix.py` 的 `EXPECTED` 含上述能力，且 `ROLES` 含 `sales` |
| AI-IDEMPOTENCY-001 | AI 重复点击、网络重试或 SSE 重连可能重复生成草稿 | 检查普通响应和 SSE 使用持久化 `request_id`，重复请求只执行一次并重放结果 |
| AI-ENCODING-001 | AI 采购入库业务类型和确认框存在历史乱码 | 检查已知乱码常量不得重新出现 |
| AI-AUDIT-001 | AI 请求和能力授权缺少持久化审计，无法复盘模型、耗时和权限结果 | 检查每个首次请求创建 `AIRun`，能力校验写入 `AIToolCall`，幂等重放不重复创建运行记录 |
| BUG-SALES-001 | `SalesOrder` 缺 `customer_id` 外键，依赖 customer 字符串文本，无法关联客户主数据 | 检查 `SalesOrder.customer_id` 为 `nullable=False` 外键到 `customer.id` |
| BUG-SALES-002 | `SalesOrder` 缺 `warehouse_id` 外键，依赖 warehouse 字符串，报表仓库筛选无法关联 Warehouse 表 | 检查 `SalesOrder.warehouse_id` 为外键到 `warehouse.id`，历史数据已回填 |
| BUG-SALES-003 | `OutOrderItem` 缺行级来源外键，无法追溯到销售订单明细 | 检查 `OutOrderItem.source_sales_order_item_id` 为外键到 `sales_order_item.id` |
| BUG-SALES-004 | `OutOrder` 缺头级来源外键，依赖 `purpose` 字符串解析 | 检查 `OutOrder.source_sales_order_id` 为外键到 `sales_order.id`，`source_sales_order` relationship 已建立 |
| BUG-SALES-005 | 销售出库缺跨仓库边界校验，可能扣错仓库库存 | 检查出库时 `material.stock` 减扣后不为负，且按 `SalesOrder.warehouse_id` 校验仓库一致性 |
| BUG-SALES-006 | 销售选单接口 `/api/sales_order/selectable` 无并发保护，高并发可能重复生成出库草稿 | 检查选单接口使用 `BEGIN IMMEDIATE` 串行化 |
| BUG-SALES-007 | `SalesOrder` 金额字段使用 `Float` 类型，精度不足导致对账偏差 | 检查 `SalesOrder.total_amount`/`untaxed_amount`/`tax_amount`/`shipped_amount`/`remaining_amount` 均为 `Numeric(18,2)` |
| BUG-SALES-008 | `/sales/<id>/copy` 和 `/sales/batch_delete` 缺 `@require_role`，仅 `@login_required` 越权风险 | 检查 12 个 `/sales/*` POST 路由全部含 `@require_role('warehouse','purchase','sales')`（SM-P6-FIX-01） |
| BUG-SALES-009 | `sales_order_detail.html` 两处 fetch 调用缺 `X-CSRFToken` 头，存在 CSRF 漏洞 | 检查模板 fetch 调用使用 `csrfPost` helper 或继承 `base.html` 全局 `window.fetch` wrapper（SM-P6-FIX-01） |
| BUG-SALES-010 | `sales_out_draft` AI 工具语义错配：工具名"销售出库草稿"但描述/端点均为"售后出库" | 检查 `sales_out_draft` 标记为 deprecated alias，新增 `after_sale_out_draft`（端点 `add_after_sale_out_order`）+ `sales_outbound_draft`（端点 `create_sales_outbound_draft`）（AI-SALES-F01-FIX-02） |
| BUG-SALES-011 | `VALID_ROLES` 缺 `'sales'` 角色，导致 `sales_out_draft` 工具合规检查失败 | 检查 `VALID_ROLES` 包含 `'sales'`（AI-BUG-F02 / `b374565`） |
| BUG-SALES-012 | 销售模块无 AI 异常分析与单据联查能力，对比采购侧 `out_order_detail.html` 缺失 | 检查 `sales_order_detail.html` 含 AI 异常分析按钮 + `/api/ai/sales_order/<id>/anomaly_analysis` 只读路由 + 售后单联查面板（AI-SALES-F01-FIX-02） |
| BUG-SALES-013 | 销售模块无 AI 履约跟进工作台，对比采购侧 `AI-R11-F01` 7 队列结构缺失 | 检查 `ai_sales_workbench.html` + `sales_followup_workbench.py` 7 队列 + `sales_followup` Agent + `sales_insights` 工具 + 3 路由（AI-SALES-F02） |
| BUG-SALES-014 | 销售模板散用 `confirm()`/`alert()` 原生 API，与系统级 `showConfirm`/`showToast` 不一致 | 检查 5 个销售模板（`sales_outbound_selection.html`/`customer.html`/`after_sale_out.html`/`after_sale_out_add.html`/`after_sale_out_detail.html`）不再含 `confirm(`/`alert(` 调用（SM-P6-02） |
| BUG-SALES-015 | `sales_order.html` 工具栏 + 行内写按钮无角色权限感知隐藏，`user`/`production` 角色可见写操作入口 | 检查写按钮包裹 `{% if current_user.role in ['admin','warehouse','purchase','sales'] %}`，后端 `@require_role` 仍二次校验（SM-P6-02） |
| BUG-SALES-016 | `customer.html` 完全无客户导入入口，与 `supplier.html` 结构不一致 | 检查 `customer.html` 含 `importModal` 模态框 + AJAX 提交 + `csrf_token` + `notifyMasterDataChanged('customer_updated')` 广播（SM-P6-02） |
| LOGIN-CSRF-001 | Web `/login` 被 `@csrf.exempt` 豁免，无 CSRF token 的 POST 仍可建立会话 | 检查 `app.login` 不在 `csrf._exempt_views`，`app.native_api_login` 仍豁免，`login.html` 含 `csrf_token`，无 token POST `/login` 返回 400 |

## 已确认误报

| 编号 | 原问题 | 误报原因 |
|------|--------|----------|
| BUG-003 | 委外收货数量双倍计算 | 源码已有 autoflush 处理说明，sum 查询没有额外加本次数量 |
| BUG-008 | 全局确认框变量竞态 | 当前实现已使用确认队列，不存在 resolver 覆盖 |

## 降级或暂缓项

| 编号 | 状态 | 说明 |
|------|------|------|
| BUG-007 | 低风险 | 原问题主要是死代码/防御性分支，不是核心业务矛盾 |
| VULN-002 | 低风险 | `|safe` 使用前已有 sanitize 保护，继续保持净化入口即可 |
| CONF-003 | 低风险 | 生产配置已修正，环境部署时仍需确认 HTTPS/Cookie 配置 |
| SQLite 并发能力 | 已修复单机并发边界 | 已启用 WAL、60 秒 busy timeout、外键、原子库存更新；启动迁移使用排他事务串行执行。高并发生产环境仍建议迁移 MySQL/PostgreSQL |
| BUG-NEW-002 | 暂不按 BUG | `update_completed_in_order()` 的库位增减路径支持正负 `qty_diff`，新增、删除、数量变更均已有库位同步 |
| BUG-NEW-004 | 已修复 | 保留 `received_quantity` 作为防重复下推的占用量；采购订单状态改为仅汇总 `completed` 入库单，草稿和待提交入库不再提前把订单标记为已入库 |
| BUG-NEW-007 | 已修正字段语义 | `api_material_payload()` 不再把 `warehouse_code` 直接复制给 `location_code`，库位启用时取库位库存记录 |
| BUG-NEW-010 | 低风险体验项 | `makeKey()` 已会规范化 `embedded` 参数；未确认恢复错配。仅提高恢复标签数量上限 |
| BUG-NEW-012 | 低风险体验项 | 登录页占位链接/勾选框不影响核心业务；初始密码展示必须与 BUG-NEW-005 和 `AGENTS.md` 一致 |
| BUG-NEW-016 | 已修复 | 自动迁移在检查字段前执行 SQLite `BEGIN EXCLUSIVE` 并等待最多 60 秒；迁移失败将阻止进程继续启动，避免多个 worker 重复 DDL 或带不完整结构运行 |
| BUG-NEW-017 | 误报 | 报告描述为“日志不包含具体 SQL，不利排查”，不是“敏感 SQL 泄露” |
| BUG-NEW2-005 | 低风险设计项 | `log_operation()` 是独立的 best-effort 日志提交，当前多在业务提交后调用；不按核心数据 BUG 处理 |
| JS-NEW2-001 | 低风险兜底 | `confirmDialog()` 缺 DOM 时降级 `window.confirm()` 是可用性兜底，不影响数据正确性 |
| JS-NEW2-002 | 低风险兜底 | `toast()` 缺容器时降级 `alert()` 是可用性兜底，不影响核心业务 |
| SEC-NEW2-001 | 已有保护 | `/api/login` 是换取 token 的原生 API；入库/出库/盘点有 `@api_required`，微信助手有独立授权，不移除 CSRF 豁免 |
| SEC-NEW2-002 | 平台限制 | Windows 对 `chmod 0600` 支持有限，属于部署环境权限控制问题；生产应放在受限账户/目录下运行 |

## 每日使用方式

```powershell
.\scripts\python.cmd scripts\verify_wms_bugs.py
.\scripts\python.cmd scripts\scan_wms_risks.py
```

规则：`verify_wms_bugs.py` 失败才需要立即处理；`scan_wms_risks.py` 输出的是候选风险，必须人工判真后才能进入 BUG 修复。
