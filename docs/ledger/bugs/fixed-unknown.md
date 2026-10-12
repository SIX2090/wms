# BUG 基线 · 已修复归档 unknown

> 本分片由 `WMS_BUG_BASELINE.md「已修复并纳入回归」` 拆出（F4.4（2026-10-13））。
> 查询：`python scripts/query_ledger.py --task <ID>`。

| 编号 | 问题 | 回归检查 |
|---|---|---|
| 编号 | 问题 | 回归检查 |
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
| BUG-NEW-001-FIX-01 | 已完成入库单可被详情页或接口直接物理删除 | 后端只允许删除 `pending`；已完成单必须先反提交回退库存，详情页不显示完成单删除按钮 |
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
| BUG-NEW3-005 | `batch_complete_in_order` 缺单据写锁、循环外 commit 致并发重复审核/部分失败整体回滚 | 每单 `_acquire_order_write_lock(InOrder,id,'pending')`、循环内独立 `commit`、失败仅回滚自身，SHA `7d2272a4` |
| BUG-NEW3-006 | `batch_complete_out_order` 缺单据写锁致并发重复扣库存/重复推进销售发货进度 | 每单 `_acquire_order_write_lock(OutOrder,id,'pending')`、循环内独立 `commit`，SHA `9d6a2ea1` |
| BUG-NEW3-007 | `batch_revert_in_order` 缺锁+`deduct_stock` 读改写竞态+循环外 commit | 每单加锁+改 `deduct_stock_atomic`+循环内独立 `commit`，SHA `60f365b4` |
| BUG-NEW3-008 | 售后出库完成/反提交未同步库位库存，启用库位管理后总库存与库位库存长期不一致 | `complete_after_sale_out_order` 和 `revert_after_sale_out_order` 在原子扣减/恢复后调用 `update_location_inventory`，失败回滚，SHA `0b56db5d` |
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
| BUG-F02-01 | 基础资料列表默认按 `created_at desc` 排序，与查字典习惯相反 | `app.py` `_get_master_list_filters` 默认 `sort_by='code'`/`order='asc'`，5 个 list 路由同步；模板统一用 `sort_th` 宏。`audit_screenshots/verify_f02_01_sort.py` 33/33 |
| BUG-F02-02 | 物料/供应商/客户 6 个 add/edit 路由对 code/name/spec/purpose/remark/contact/phone/address 不做长度校验，DB 静默截断 | `app.py` 6 路由入口加 11 字段长度校验（code 50/name 100/spec 100/purpose 200/remark 500/contact 50/phone 20/address 200）；超限返 400 + 中文 msg。`audit_screenshots/verify_f02_02_truncate.py` 30/30 |
| BUG-F02-03 | 标签模板设计页点"保存布局"后端 404，前端 `data.status === 'success'` 假阳性，误报保存成功 | `app.py` 新增 `save_label_template_layout`（`@require_role admin/warehouse` + layout 非空/类型校验 + 审计 log）；`label_template_detail.html` `saveLayout()` 加 `response.ok` 检查 + `_savingLayout` 守卫 + `spinner-border` 反馈 + `console.error` 详细错误。`audit_screenshots/verify_f02_03_label_save.py` 16/16 |
| BUG-F02-04 | 仓库被停用/删除后，入库单仍可选用，导致库存归属不明 | `app.py` 新增 `is_warehouse_active`/`assert_warehouse_active` helper；`add_in_order`/`update_in_order` 入口校验；不通过返 400 + 中文 msg。`audit_screenshots/verify_f02_04_warehouse.py` 12/12 |
| BUG-F02-05 | `location_management_enabled=False` 时入库单前端仍把仓库字段渲染为必填 | `in_order_add.html` 仓库字段包 `{% if location_management_enabled() %}` 条件渲染；JS 同步用 `locationManagementEnabled` 控制必填；`add_in_order` 后端同步允许空仓库。`audit_screenshots/verify_f02_05_location_off.py` 13/13 |
| BUG-F02-06 | 普通用户没有自助改自己资料（电话/邮箱/备注）的入口；admin 改他人审计缺 `last_modified_by` | `app.py` 新增 `edit_my_profile`（仅改 email/phone/bio，邮箱/电话格式校验，长度限制 200/30/500，不可改 username/role/status/password）+ User 模型加 `email/phone/bio` 列 + 迁移；`edit_user` `log_operation` 显式带 `last_modified_by=current_user.username`；`my_profile.html` + 侧边栏入口。`audit_screenshots/verify_f02_06_profile.py` 17/17 |
| BUG-F02-07 | 主数据列表分页 `per_page` 无上限校验，URL 不记忆每页大小 | `app.py` 5 list 路由统一 `per_page` 白名单 [10,20,50,100,200]，默认 20；`_list_macros.html` 新增 `per_page_select` 宏；`base.html` 自动绑定 `.per-page-select` 切换 URL。`audit_screenshots/verify_f02_07_pagination.py` 17/17 |
| BUG-F02-08 | purchase/sales 等非授权角色可访问 `/label_template/<id>` 设计页，点保存才 403 | `app.py` `label_template_detail` 加 `@require_role('admin','warehouse')`。`audit_screenshots/verify_f02_08_template_perm.py` 4/4 |
| BUG-F02-09 | `material.html` 标签模板设计器 16 处调用从未定义的 `saveTemplateToStorage()`，任何编辑交互即抛 `ReferenceError`，设计结果无法持久化 | `material.html` 新增 `saveTemplateToStorage()`（序列化当前编辑器状态到 `localStorage.labelTemplateDraft`）+ `restoreTemplateDraft()`（无已保存模板时自动恢复草稿）+ `saveTemplate()` 成功后清除草稿。`audit_screenshots/verify_f02_09_10_frontend.py` 14/15（浏览器实测项因本机无浏览器跳过） |
| BUG-F02-10 | `warehouse.html`/`department.html`/`employee.html` 的 GET 筛选表单内含 `csrf_token` 隐藏域，筛选后 token 明文出现在地址栏 URL | 三个模板 GET 表单删除 `csrf_token` 隐藏域（POST 模态框表单保留）。`audit_screenshots/verify_f02_09_10_frontend.py` 静态+线上 HTTP 双重验证通过 |
| P2-1 | `after_sale_out_detail.html` 详情页基本信息卡片未显示仓库字段，单据详情无法核对实物入哪个仓 | `app/templates/after_sale_out_detail.html` 在客户名称下方补 `<p><strong>仓库：</strong>{{ order.warehouse or '-' }}</p>`（commit `61452e84`） |
| INV-AUDIT-001 | 真实库位库存无法正确汇总到仓库库存：`get_warehouse_stock_quantities(warehouse)` 用 location 字符串匹配仓库名汇总，库位字符串与仓库名不一致或库位启用前后命名漂移时，仓库库存与总库存长期不一致 | `app/app.py` 新增 `resolve_inventory_warehouse_id(value)` 统一解析仓库 ID（None/实例/ID/名称/编码）；`update_location_inventory` / `add_location_inventory_atomic` / `deduct_location_inventory_atomic` 新增 `warehouse` / `warehouse_id` 参数并写入 `LocationInventory.warehouse_id`；`get_warehouse_stock_quantities` 改为按 `warehouse_id` 汇总，旧 location 字符串数据无 `warehouse_id` 时回退按 location 字符串匹配仓库名（兼容历史数据，不自动归入默认仓库）。回归：`tests/test_inv_audit_001_002_location_inventory_warehouse_isolation.py` 18/18 PASSED（resolve_inventory_warehouse_id 多形态解析、跨仓同名库位隔离、仓库级汇总正确、历史 location 字符串回退）。commit `d7fc6599` + `13c8a392` |
| INV-AUDIT-002 | 库位库存缺少仓库维度，`LocationInventory` 唯一约束为 `(material_id, location)`，不同仓库下同名库位被合并成一行库存；跨仓调拨同名库位相互覆盖 | `LocationInventory` 唯一约束改为 `(material_id, warehouse_id, location)`；新增 Alembic 迁移 `8b17c4d90a2e_location_inventory_warehouse_compat` 添加 `warehouse_id` 列并重建唯一约束；`auto_migrate_database` 增加 SQLite 表重建逻辑（SQLite 不支持 `ALTER TABLE DROP CONSTRAINT`，用 batch_alter_table 重建表结构 + 数据回填）；历史数据无法确定仓库归属的保留为未归属，不自动归入默认仓库。回归：`tests/test_inv_audit_001_002_location_inventory_warehouse_isolation.py::TestCrossWarehouseSameLocationNotMerged` 验证 A 仓 A1=10 与 B 仓 A1=5 不被合并；`tests/test_location_inventory_warehouse_migration.py` 验证迁移逻辑。commit `d7fc6599` |
| INV-AUDIT-003 | 移动扫码入库/出库/盘点未统一执行仓库必填规则，且库存校验直接读取全局 `Material.stock` 跨仓数量，可凭其他仓库库存扣减本仓库 | `app/routes/mobile.py` `scan_submit` 接入 `resolve_request_warehouse` 强制仓库必填（未提供或无效时 400），库存校验改用 `get_warehouse_stock_quantities(warehouse)` 返回仓库级库存；`update_location_inventory` 调用传入 `warehouse` 参数确保 `warehouse_id` 写入；库位字段独立解析不再与仓库名混淆。回归：`tests/test_inv_audit_003_mobile_scan_warehouse_scope.py` 7/7 PASSED（仓库必填拒绝、仓库级库存校验、跨仓库存隔离、入/出/盘均落 warehouse_id）。commit `2b47d8e7` |
| INV-AUDIT-004 | 旧物料模糊查询接口 `POST /api/query/search` 未校验仓库参数，直接返回全局 `Material.stock`，违反 AGENTS.md「库存查询仓库必填筛选」规则 | `app/routes/stock_query.py` `api_query_search` 接入 `resolve_request_warehouse` 强制仓库必填（无默认仓库时返回 400「请选择仓库」），`stock` 字段改用 `get_warehouse_stock_quantities(warehouse)` 返回仓库级库存，不再回退全局 `Material.stock`。回归：`tests/test_inv_audit_004_query_search_warehouse_scope.py` 7/7 PASSED（仓库必填校验、仓库级库存返回、跨仓库存不泄漏 A 仓查不到 B 仓库存、默认仓库回退）。commit `9b1d779c` |
| INV-AUDIT-005 | 调拨/盘点/调整/普通出库/移动端 stocktake 的仓库存在性及 active 状态校验不一致：部分路由只校验非空不校验存在，部分路由不校验 active，可对已停用仓库或不存在仓库名生成单据 | `app/app.py` 新增 `resolve_active_inventory_warehouse(value, warehouse_id)` 与 `validate_inventory_warehouse(value, warehouse_id)` 辅助函数，按 ID/名称/编码统一解析并校验 `status='active'`；`app/routes/transfer.py`（from_warehouse/to_warehouse）、`app/routes/check.py`（warehouse）、`app/routes/adjustment.py`（warehouse）、`app/routes/out_order.py`（领料/其他出库 warehouse）、`app/routes/native_api.py`（stocktake warehouse）全部接入 `validate_inventory_warehouse`，校验失败返回 400，校验通过用规范化仓库名回写单据字段。回归：`tests/test_inv_audit_005_warehouse_active_validation.py` 23/23 PASSED（辅助函数多形态解析 + active 过滤、各路由对不存在/已停用仓库拒绝、对 active 仓库通过且规范化回写）。commit `da22cc81` |
