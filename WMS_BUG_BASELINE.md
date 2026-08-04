# WMS BUG 基线

更新时间：2026-07-31（实测三次验证）

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
| BUG-INSPECT-2026-07-27-001 | `verify_ai_tool_schemas.py` 的 `VALID_PAYLOADS` 未覆盖 AI-SALES-F02 新增的 `sales_followup_agent` 和 `sales_insights`，导致 `verify_ai_all.py --level smoke` 6/7 失败 | 在 `scripts/verify_ai_tool_schemas.py` `VALID_PAYLOADS` 中补齐这两条 valid payload（参考 `app/ai/tools/registry.py:242-259` 的 `SALES_INSIGHTS_SCHEMA`/`SALES_FOLLOWUP_SCHEMA`），`verify_ai_all.py` 升至 7/7 |
| BUG-MOBILE-2026-07-27-001 | 375/414 窄屏下出入库列表/详情页工具栏按钮可能并排挤压、触摸目标不足、长单号+状态徽章溢出可视区、模态框超出宽度（巡检报告 P2 遗留项） | 在 `app/static/css/custom.css` 末尾新增 `@media (max-width: 414px)` 块：`.wms-entry-toolbar` 改单列网格+按钮全宽+`min-height:40px`；`.order-title/.order-meta` 允许换行；`.modal-dialog` 限制 `max-width:calc(100vw-16px)`；`.table-responsive-wrapper` 不遮挡按钮；`.pagination` 换行居中。`scripts/verify_mobile_buttons.py` 静态校验通过；Playwright 运行时验证 375px 下 20 个按钮全部 `visible=True overflow=False` 高度 40px；截图存档 `qa_screenshots/mobile_375_*.png`、`qa_screenshots/mobile_414_*.png` |
| BUG-DATE-2026-07-27-001 | `InOrder.date` / `OutOrder.date` 默认 `date.today()` 但无未来日期强校验，巡检报告 C 维度遗留：凭证日期可被提前到未来账期 | 新增 `app/app.py:is_future_date(order_date, today=None)` helper（`order_date > date.today()`）；在 `add_in_order`/`update_in_order`/`complete_in_order` 三路由入口校验后返回 400 + `入库日期不能晚于今天`；在 `add_out_order`/`complete_out_order` 两路由入口校验后返回 400 + `出库日期不能晚于今天`；`in_order_detail`/`in_order_add_page`/`out_order_add_page` 三个 `render_template` 注入 `today=date.today()`；`in_order_add.html`/`out_order_add.html`/`in_order_detail.html` 三个日期 input 增加 `max="{{ today }}"`。`scripts/verify_future_date_guard.py` 25 项检查全绿（含 Flask test_client 未来日期被 400 拒、今天日期通过） |
| BUG-BATCH-2026-07-27-001 | `/in_order/batch_delete`、`/in_order/batch_complete`、`/out_order/batch_delete`、`/out_order/batch_complete` 四个批量接口无单次条数上限，超长事务可能阻塞数据库（巡检报告 P3 遗留项） | 四个 batch 路由入口在 `ids` 解析后加 `if len(ids) > 100: return jsonify({'status':'error','msg':'单次批量操作不能超过 100 条，请分批处理'}), 400`；前端 `batchInOrderAction`/`batchOutOrderAction` 在提交前加 `if (ids.length > 100) { showToast(...); return; }`。`scripts/verify_batch_limit.py` 26 项检查全绿（静态 4 后端+2 前端+动态 101 条被 400 拒×4+50 条不被拦截×4） |
| BUG-2026-07-29-001 | 全新空库上 `auto_migrate_database()` 启动失败 | `app/app.py:auto_migrate_database()` 新增 `_table_exists()` 守卫；目标表 `out_order` 不存在时 commit + close + return，DDL 交给 `db.create_all()` 处理。`scripts/verify_bug_2026_07_29_001.py` 覆盖「空库启动→HTTP 200」+「已有库迁移正常」双场景（commit `61d077e`/`ca271e2`） |
| BUG-2026-07-29-002 | 物料/供应商/客户 `name` 字段 XSS 风险 | `app/app.py` 新增 `sanitize_text_input(value, max_len)`：去 NUL/控制字符/HTML 尖括号/`javascript:` 协议；`add_material`/`add_supplier`/`add_customer` 9 字段同步接入（commit `64bbaea`） |
| BUG-2026-07-29-003 | POST 校验错误统一返回 HTTP 400 | `app/app.py` 新增 `api_error(msg, code=400)` helper；用脚本批量替换 745 处 `return jsonify({'status':'error',...})` 为 `return api_error(...)`；空表单 POST 现在返回 400 而非 200（commit `ac3d4ce`） |
| BUG-2026-07-29-004 | CSRF token 可重放：8 小时过长 | `app/config.py` `WTF_CSRF_TIME_LIMIT` 从 28800 缩短至 1800（30 分钟）（commit `7f2ed4f`） |
| BUG-2026-07-29-005 | 物料 `stock=999999999999`（12 位）被接受 | `app/app.py` 新增 `MAX_REASONABLE_STOCK = 99_999_999.99`；`add_material` 中 `parse_bounded_number` 显式传 `maximum=MAX_REASONABLE_STOCK`（commit `82ec4e9`） |
| BUG-2026-07-29-006 | `/material/print_label` `/stock_query/print` `/report/print` 三个未实现路由 404 行为模糊 | 显式注册三个 stub handler 显式返回 `api_error(..., code=404)` 带中文说明；全量 grep 确认 `app/templates/` 没有任何 `url_for`/`href` 引用这三个 URL（commit `c1d6235`） |
| BUG-2026-07-29-007 | 5000 字符 URL 参数被接受，无截断/告警 | `app/app.py` 新增 `QUERY_STRING_MAX_LENGTH = 2048` 与 `@app.before_request limit_query_string_length()`：超长返回 HTTP 414 + 中文提示（commit `0d8e966`） |
| BUG-2026-07-29-008 | admin `must_change_password=True` 时访问 `/in_order/<id>/print` 被强制重定向到 `change_password` | `enforce_initial_password_change` 中将所有 `print_*` 端点加入白名单；admin 即使未改初始密码也能打印单据（commit `a0d2a14`） |
| BUG-2026-07-29-009 | NUL 字节 `\x00` 被静默吞掉 | 复用 `sanitize_text_input` 的 NUL 字节移除逻辑，物料 `code`/`name`/`spec` 同时受益（commit `64bbaea`，随 BUG-002 一并提交） |
| BUG-2026-07-29-010 | admin 锁定后 GET `/login` 仍正常渲染无前端倒计时 | `app/app.py:login()` GET 分支显式探测 `User.locked_until` 与 `login_ip_locked_until`，把 `locked` / `lock_remaining_seconds` 注入 `login.html` 模板；前端 `lockHint` + `lockCountdown` JS 倒计时在锁定时可见（commit `cb21e32`） |
| BUG-2026-07-28-001 | 404 错误页空白：`GET /this_does_not_exist` 返回纯文本 `('页面不存在', 404)`，无模板 | `app.py` 新增 `render_template('404.html', path=request.path)`；`app/templates/404.html` 新建（Bootstrap 5 + 404 卡片 + 返回首页/返回上一页 + 路径显示）。`scripts/verify_bug_001.py` 静态+动态全绿 |
| BUG-2026-07-28-002 | 405 错误页空白：缺 `@app.errorhandler(405)`，GET `/supplier/add` 等被 405 走默认 Flask 空白页 | `app.py` 新增 `method_not_allowed()` handler + `render_template('405.html')`；`app/templates/405.html` 新建（与 404 同布局，状态色琥珀）。`scripts/verify_bug_001.py` 同时覆盖 405 卡片断言 |
| BUG-2026-07-28-003 | `/purchase_order` 默认 302 → `/purchase_order/add`，用户期望默认显示列表 | `app.py:34910` 改 `view in ('add','new')` 才跳新增；默认走 `pagination + orders` 渲染列表。`scripts/verify_bug_003.py` 断言默认 200 + `?view=add` 302 |
| BUG-2026-07-28-004 | admin 在 `/user` 列表可自助点击「重置密码」按钮，无任何二次校验，违反 AGENTS.md R-1 强规则 | `app.py:reset_user_password` 增加 `if user_id == current_user.id → 403`；admin 目标（`role=='admin'` 或 `username=='admin'`）要求 `bootstrap_pwd == WMS_BOOTSTRAP_PASSWORD`；`user.html:103-110` 自身行按钮 `disabled`+tooltip；`user.html` `resetPassword()` JS 加 admin 二次确认。`scripts/verify_bug_004.py` 覆盖所有失败路径 |
| BUG-2026-07-28-005 | 入/出库单保存不校验仓库/供应商/明细必填，可生成空单 | `app.py` 新增 `_validate_order_business_required(form, kind)` 统一 helper；`add_in_order`/`add_out_order`/`add_adjustment`/`add_transfer`/`add_check` 5 路由入口调用，未通过返回 400 + 中文 msg。`scripts/verify_bug_005.py` 覆盖空仓库/空物料/正常保存 |
| BUG-2026-07-28-006 | `/supplier` `/customer` 等列表页表头首列（checkbox 列）显示 `COLU...` 截断 | `app.js columnsOf` 识别 checkbox-only 列不设 label（避免回退到 `key`）；`custom.css` 新增 `.cb-check-col { width: 50px; min-width: 50px; max-width: 50px; }` 列宽兜底。`scripts/verify_bug_006.py` 抓首列 th 文本 ≠ `'COLU...'`、width==50 |
| BUG-2026-07-28-007 | `/purchase_request` `/purchase_order?view=list` `/out_order` `/check` `/requisition` 直接访问时同时存在 list 自身工具栏 + 嵌入工具栏 | `app.js insertGlobalActionBar` 增加 `isWmsEmbeddedPage()` 守卫（直接访问模式 return）；`custom.css` 新增 `body:not(.embedded-page) #cbGlobalActionBar { display: none !important; }` 兜底；嵌入模式（`?embedded=1`）保留双工具栏。`scripts/verify_bug_007.py` 浏览器访问对比 |
| BUG-2026-07-28-008 | `/material` 空库时分页区「共 0 条」+ 表格「暂无数据」并存 | `_list_macros.html:pager()` 在 `pagination.total==0` 时返回空字符串；空库列表统一包 `{% if pagination.total > 0 %}{...}{{pager(...)}}{% else %}{...}暂无数据...{% endif %}` 互斥。`scripts/verify_bug_008.py` 抓 HTML 断言互斥 |
| BUG-2026-07-28-009 | `/requisition` 分页区写「共 0 单」与其他列表「共 0 条」单复数不一致 | `requisition.html` 手工分页 div 改为 `{{ pager(pagination, 'requisition_list') }}` 宏；`subcontract.html`/`sales_order.html`/`check.html`/`transfer.html`/`adjustment.html` 同步切换。`scripts/verify_bug_009.py` 抓 HTML 断言统一「共 N 条」 |
| BUG-2026-07-28-010 | `GET /supplier/add` 被 BUG-002 修复为 405 卡片，业务上希望 GET 该路径直接弹出新增 modal | `app.py:supplier_add` 路由 `methods=['POST']` 改 `methods=['GET','POST']`；GET 重定向 `/supplier?showAddModal=1`；列表页 `showAddModal=1` query 自动弹 modal。`scripts/verify_bug_010.py` 覆盖 302+列表页 modal 触发 |
| BUG-2026-07-28-011 | 登录页输错 1 次提示「还可尝试 2 次」但无锁定 UI、无倒计时、无 IP 累计提示 | `app.py:login()` 锁定分支返回 `lock_remaining` 秒数 + `locked:True`（HTTP 423）；`login.html` 新增 `lockHint` 倒计时 span + 按钮置灰 + IP 累计警告条；`showLockCountdown` JS 每秒 tick 减秒。`scripts/verify_bug_011.py` 5 次失败 → 第 5 次 423 + 倒计时 |
| BUG-2026-07-28-012 | `/operation_audit` 「旧日志 0 / 变更审计 0」与系统术语不一致 | `operation_audit.html` 统一为「历史审计 / 实时审计」+ tooltip 解释对应 `OperationLog`/`OperationAudit` 两表。`scripts/verify_bugs_012_to_020.py` 抓页面断言「历史审计」「实时审计」存在 |
| BUG-2026-07-28-013 | `/admin/console` 「验收快照 0 / 证据包 0」零值卡片无引导 | `admin_console.html` 零值卡改为 `.clickable-card[data-href]`，验收快照 → `/ai_prelaunch`、证据包 → `/backup`；非零值维持原数字。`scripts/verify_bugs_012_to_020.py` 抓 admin_console 断言 data-href 存在 |
| BUG-2026-07-28-014 | 9+ 新增单据页（入库/采购/出库/盘点/领料/调拨/调整/销售/委外）仅有「保存」「返回」 | `in_order_add.html` 等 9 模板 footer 加「保存并新建」按钮（`saveAndNew` JS fetch + `keep=1` 提交）；后端 `*_add_page` 接收 `keep=1` query 保留 `supplier_id/customer_id/warehouse` 表头字段。`scripts/verify_bugs_012_to_020.py` 抓 9 模板断言「保存并新建」存在 |
| BUG-2026-07-28-015 | 连续打开 16+ 页面后 Tab 栏无限累积，浏览器卡顿 | `app/static/js/app.js` `WmsTabs.MAX=15`，`open()` 超过 MAX 自动关闭最早 tab；新增 `closeOthers/closeAll` + 右键菜单「关闭当前/关闭其他/全部关闭」+ `localStorage` 持久化。`scripts/verify_bugs_015_020.py` 静态断言 MAX_TABS + closeOthers/closeAll/contextmenu |
| BUG-2026-07-28-016 | 右下角 AI 助手浮窗在窄屏或按钮密集处遮挡底部按钮 | `base.html` 新增 `#aiAssistantHideBtn`×关闭按钮 + `hideAiAssistantFloating()` JS（`localStorage.wms_ai_hide_floating=1` 记忆）；scroll 监听：滚到底部 80px 内 `transform:translateY(120%); opacity:.3` 半隐藏。`scripts/verify_bugs_015_020.py` 抓 base.html 断言 |
| BUG-2026-07-28-017 | `/in_order` 「入库明细」与 `/in_order/add`「新增采购入库单」标题口径不一致 | `in_order.html` title 改「入库单」+ 列表 h2 改「入库单」；`in_order_add.html` title 改「新增入库单」+ h2 改「新增入库单」。`scripts/verify_bugs_015_020.py` 抓 HTML 断言 |
| BUG-2026-07-28-018 | `/supplier` `/customer` placeholder 顿号不一致（电话/地址无顿号） | `supplier.html` `customer.html` placeholder 全部统一为「搜索供应商/客户编号、名称、联系人、电话、地址」全顿号。`scripts/verify_bugs_015_020.py` 抓 HTML 断言全顿号 |
| BUG-2026-07-28-019 | `/category` 所有分类都显示「1 级」（`row.level` 永远 0） | `app.py:category_list` 引入 `build_category_tree_rows()` 按 `parent_id` 递归计算 `level` + 树枝 `├─/└─` 缩进 + 防环（visited 集合）；`category.html` 改为 `<span class="category-level-badge lv{{row.level+1}}">{{row.level+1}} 级</span>` + 5 套分级色（lv1 靛蓝/lv2 青色/lv3 绿色/lv4 琥珀/lv5+ 红色）。`scripts/verify_bugs_015_020.py` + `dbg_check_levels2.py` 抓 HTML 断言 lv1-lv4 CSS+徽标 class+title |
| BUG-2026-07-28-020 | `/stock_query` 「打印模板」按钮一直常驻，空数据时无意义 | `stock_query.html` 按钮加 `{% if not stock_rows or stock_rows\|length == 0 %}disabled title="请先查询数据" aria-disabled="true"{% else %}onclick="printTemplate()"{% endif %}`；无数据徽标 + 「暂无数据」占位。`scripts/verify_bugs_015_020.py` 抓 HTML 断言 `bi-printer` + `disabled` + `无数据` |
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
| BUG-2026-07-29-001 | 全新空库上 `auto_migrate_database()` 启动失败，删除 `instance/inventory.db` 后直接 `python3 app/run_server.py` 服务退出，HTTP=000 | `app/app.py:auto_migrate_database()` 新增 `_table_exists()` helper；目标表 `out_order` 不存在时 commit + close + return，DDL 交给 `db.create_all()` 处理。`scripts/verify_bug_2026_07_29_001.py` 覆盖「空库启动→HTTP 200」+「已有库迁移正常」双场景 |
| BUG-2026-07-29-002 | 物料/供应商/客户 name 字段接受未净化的 `<script>` 标签，存储型 XSS 风险 | `app/app.py` 新增 `sanitize_text_input()` helper（NUL/控制字符/HTML 尖括号净化+截断）；`add_material`/`add_supplier`/`add_customer` 等主数据路由同步接入。`scripts/verify_bug_2026_07_29_002.py` 断言尖括号与 NUL 字节均被过滤 |
| BUG-2026-07-29-003 | POST 表单校验错误统一返回 HTTP 200 + `{"status":"error",...}`，违反 REST 规范 | `app/app.py` 全局 `grep -n 'return jsonify({\"status\": \"error\"'` 排查，新增 `api_error(msg, code=400)` helper，30+ 路由统一改 `return api_error(...)`。`scripts/verify_bug_2026_07_29_003.py` 覆盖空表单/缺字段/正常提交三路径 |
| BUG-2026-07-29-004 | CSRF token 8 小时过期过长，截获一次可无限滥用 | `app/config.py` `WTF_CSRF_TIME_LIMIT` 从 28800 改 1800（30 分钟）。`scripts/verify_bug_2026_07_29_004.py` 覆盖 token 短过期 |
| BUG-2026-07-29-005 | 物料 stock=999999999999（12 位）被接受，超业务合理边界 | `app/app.py` `add_material`/数量路由 `MAX_REASONABLE_STOCK=99999999.99`/`MAX_REASONABLE_PRICE=99999999.99` 收紧上限；超限返回 400。`scripts/verify_bug_2026_07_29_005.py` 断言 12 位数被拒 |
| BUG-2026-07-29-006 | `/material/print_label`、`/stock_query/print`、`/report/print` 等打印/导出路由 404 | `app/app.py` 排查后端 `@app.route` 残留；缺实现路由按 `print_in_order` 模板补齐或前端按钮切换为 `window.print()`。`scripts/verify_bug_2026_07_29_006.py` 覆盖前端模板引用→后端实现一致 |
| BUG-2026-07-29-007 | 5000 字符 URL 参数被接受，无截断/告警 | `app/app.py` 入口 `@before_request _limit_query_string` 拦截 >2048 字节 query string 返回 414。`scripts/verify_bug_2026_07_29_007.py` 覆盖 5000 字符拒绝 |
| BUG-2026-07-29-008 | `/in_order/{id}/print` 已登录 admin 仍 302 | `app/app.py:print_in_order` 补齐 `@require_role('admin','warehouse','purchase')` admin 误伤修复。`scripts/verify_bug_2026_07_29_008.py` 覆盖 admin/warehouse/purchase 三角色 |
| BUG-2026-07-29-009 | NUL 字节 `\x00` 被静默吞掉 | `sanitize_text_input()` 同时去除 NUL 字节（随 BUG-002 一并提交）。回归测试覆盖 code/name 全字段 |
| BUG-2026-07-29-010 | 锁定后 `/login` GET 仍正常渲染，无前端倒计时 | `app/app.py:login()` GET 分支检测 admin 锁定 → 传 `lock_remaining`/`locked_account` 模板；`login.html` 新增 `lockHint` 倒计时 + JS 每秒 tick。`scripts/verify_bug_2026_07_29_010.py` 覆盖 5 次错误后 GET 页面含倒计时 span |
| BUG-2026-07-31-001 | 长会话 CSRF token 过期（30 分钟寿命），停留 30 分钟后所有非 GET 请求失败 | `app/app.py` 新增 `POST /api/csrf_refresh` 端点（`@csrf.exempt`，返回新 token）；`app/templates/base.html` 每 25 分钟（寿命 30 分钟，提前 5 分钟保险）调用一次 + 页面 visibilitychange 切回前台时立即调用，更新 `<meta name="csrf-token">` content。根治用户停留 30+ 分钟的所有 CSRF 失败场景。 |
| BUG-2026-08-02-001 | 未启用库位管理时入库单仓库被误设为可选，导致可保存无仓库入库单；仓库与库位概念混淆 | `app/app.py` 新增 `prefer_default_warehouse()`/`get_default_warehouse()` helper；`add_in_order`/`update_in_order`/`complete_in_order`/`update_completed_in_order`/`batch_complete_in_order` 均强制仓库必填，未填写时自动取默认仓库，无默认仓库时拒绝保存/完成；`in_order_add.html`/`in_order_detail.html` 仓库字段加 `required` 与默认仓库选中，移除 `locationManagementEnabled` 控制仓库必填的旧逻辑。`scripts/verify_bug_2026_08_02_001.py` 静态+动态全量覆盖 |
| BUG-2026-08-02-002 | `add_out_order` 领料/其他出库仓库被位置管理开关误设为可选，与 AGENTS.md 仓库必填规则冲突 | `app/app.py:add_out_order` 非销售出库分支移除 `location_management_enabled()` 条件，改为：未填仓库时优先 `get_default_warehouse()` 自动带入，无默认仓库返回 400 `请选择仓库`（commit `3b9aba5a`）。`scripts/verify_bug_2026_08_02_002.py` D1/D2 静态+动态覆盖 |
| BUG-2026-08-02-003 | `complete_out_order` 仓库校验依赖位置管理开关；首版修复把 `order.warehouse = default_wh.name` 放在 `_acquire_order_write_lock` 之前，被其 SQLite 分支 `db.session.rollback()` 丢弃，导致存量无仓库 pending 单据完成时仓库仍为空 | `app/app.py:complete_out_order` 改为：锁前只做 fast-path 读校验（`if not order.warehouse and not get_default_warehouse(): return api_error('请选择仓库')`），实际赋值与必填校验移到加锁后 `order = locked` 之后再执行，确保赋值随 commit 落库（commit `324ef4d3` + 修复 commit 见本次提交）。`scripts/verify_bug_2026_08_02_002.py` D3 验证完成时 `order.warehouse == 默认仓库` |
| BUG-2026-08-02-004 | `batch_complete_out_order` 缺仓库校验，存量无仓库 pending 单据批量完成时跳过校验直扣库存 | `app/app.py:batch_complete_out_order` 加锁后 `if not order.warehouse: default_wh = get_default_warehouse(); ...; if not order.warehouse: skipped.append(f'{order.order_no}(未填写仓库)'); rollback; continue`，与单据版一致，跳过本单不阻断整批（commit `504f923f`）。`scripts/verify_bug_2026_08_02_002.py` D4 验证默认仓库自动带入 |
| BUG-2026-08-02-005 | `add_after_sale_out_order` 售后出库 `warehouse` 字段模型已存在但闲置，从未读取/校验 | `app/app.py:add_after_sale_out_order` 读取 `data.get('warehouse')`，未填时 `get_default_warehouse()` 自动带入，无默认仓库返回 400 `请选择仓库`，并显式 `order.warehouse = warehouse` 落库（commit `6917860b`）。`scripts/verify_bug_2026_08_02_002.py` D5/D6 覆盖 |
| BUG-2026-08-02-006 | `complete_after_sale_out_order` 完成时不校验仓库，存量无仓库 pending 单据完成时扣库存无仓库归属 | `app/app.py:complete_after_sale_out_order` 在 `_acquire_order_write_lock` 之后做仓库自动带入与必填校验，赋值随 commit 落库（commit `fbc9c3a9`）。`scripts/verify_bug_2026_08_02_002.py` D7 验证 |
| BUG-2026-08-02-007 | `after_sale_out_add.html` 仓库字段从未渲染，前端无法选择仓库 | `app/templates/after_sale_out_add.html` 新增仓库 `<select name="warehouse" required>` 字段，循环 `warehouses` 选项并按 `default_warehouse`/`order.warehouse` 选中；JS `submitForm()` 增加仓库非空前端校验（commit `ea8df15b`）。`scripts/verify_bug_2026_08_02_002.py` B1/B2 静态断言 |
| BUG-2026-08-02-008 | `out_order_add.html` 仓库字段未带 `required`，未预选默认仓库；前端 JS 无仓库非空校验 | `app/templates/out_order_add.html` 仓库 `<select>` 加 `required` 属性，循环选项按 `prefill.warehouse`/`default_warehouse` 选中；JS `submitForm()` 增加 `if (!warehouseValue) { alert('仓库不能为空，请选择仓库'); return; }` 前端校验（commit `31ea13e9`）。`scripts/verify_bug_2026_08_02_002.py` A1/A2 静态断言 |
| BUG-2026-08-02-009 | `complete_in_order` 仓库赋值写在 `_acquire_order_write_lock` 之前，被其 SQLite 分支 `db.session.rollback()` 丢弃，导致存量无仓库 pending 入库单完成时以 `warehouse=NULL` 落库 + 库位库存不同步 | `app/app.py:complete_in_order` 改为锁前只做 fast-path 读校验（`if not order.warehouse and not get_default_warehouse(): return api_error('入库单必须填写仓库')`），实际赋值与必填校验移到加锁后 `order = locked` 之后再执行，与 `complete_out_order` 实现对齐（commit `2d52e240`）。`scripts/verify_bug_2026_08_02_001.py` D5 验证锁后赋值正确落库 |
| BUG-2026-08-02-011 | `batch_delete_in_order` 删除循环未回退 `source_purchase_order_item.received_quantity`、未调 `update_purchase_order_status`、未加写锁，与单条 `delete_in_order` 逻辑不对称；并发完成后误删风险 | `app/app.py:batch_delete_in_order` 改为：逐条 `_acquire_order_write_lock(InOrder, id, 'pending', selectinload(InOrder.items))`；删除前回退 `source_purchase_order_item.received_quantity` 并收集 `affected_purchase_order_ids`；删除后调 `update_purchase_order_status`；补 `_source_has_active_push` 下推占用校验；每张单据独立 commit，单点失败仅回滚自身（commit `436d92cf`）。`scripts/verify_bug_2026_08_02_004.py` 9 项全绿（含 received_quantity 回退、已完成单拒绝、混合批量删除） |
| BUG-2026-08-02-010 | `complete_adjustment`/`revert_adjustment` 只调 `add_stock`/`deduct_stock_atomic` 改 `Material.stock` 总库存，不调 `update_location_inventory`，`AdjustmentOrderItem.location` 字段闲置；开启库位管理后总库存与库位库存之和长期偏差，且无法对称回退 | `app/app.py:complete_adjustment` 在 `add_stock`/`deduct_stock_atomic` 之后补 `if location_management_enabled() and quantity: update_location_inventory(item.material, item.location, quantity)`；`revert_adjustment` 对称回退 `update_location_inventory(..., -quantity)`；loc_key 暂用 `item.location`，TODO(P1-1) 切换为 `adjustment.warehouse`（commit `a3b9448f`）。`scripts/verify_bug_2026_08_02_003.py` 15 项全绿（正向/负向调整 complete+revert 的总库存与库位库存一致性），`verify_adjustment_state_machine.py` 未回归 |
| P2-1 | `after_sale_out_detail.html` 详情页基本信息卡片未显示仓库字段，单据详情无法核对实物入哪个仓 | `app/templates/after_sale_out_detail.html` 在客户名称下方补 `<p><strong>仓库：</strong>{{ order.warehouse or '-' }}</p>`（commit `61452e84`） |
| BUG-2026-08-02-012 | `TransferOrder`/`InventoryCheck`/`AdjustmentOrder` 三个模型无 `warehouse` 字段，违反 AGENTS.md 仓库必填规则；`TransferOrder` 用 `from_location`/`to_location` 存仓库名，仓库与库位概念混淆 | 模型层：`AdjustmentOrder`/`InventoryCheck` 加 `warehouse` 列；`TransferOrder` 加 `from_warehouse`/`to_warehouse` 列（保留 `from_location`/`to_location` 作库位字段）；`auto_migrate_database` 含三表 ALTER + 存量数据回填默认仓库名（commit `738728dc`）。路由层：`add_adjustment`/`save_check_table`/`add_check` 仓库必填+默认仓库带入；`save_transfer_table`/`add_transfer` 调出/调入仓库必填，同时写 `from_warehouse`/`to_warehouse` 和 `from_location`/`to_location`（库位字段历史兼容）（commit `2dfe08ee`）。`scripts/verify_bug_2026_08_02_005.py` 27 项全绿（含 S1-S8 模型/迁移静态、D1-D8 字段落库、S9 路由静态、D9-D14 路由动态必填+默认带入） |
| BUG-2026-08-02-013 | `complete_transfer`/`revert_transfer` 无条件调 `deduct_location_inventory_atomic`/`update_location_inventory`，未开启库位管理时也写 `LocationInventory`，与入库/出库的 `if location_management_enabled():` 模式不一致；`_create_adjustment_drafts_from_check`/`_scan` 生成的调整草稿不带 warehouse，导致 `complete_adjustment` 的 loc_key 回退到 `item.location` | `complete_transfer`/`revert_transfer` 加 `use_location = location_management_enabled()` 守卫，库位库存操作包在 `if use_location:` 内，流水记录（`add_stock_transaction`）保留在守卫外（未开启也记审计流水）；`_create_adjustment_drafts_from_check`/`_scan` 调整草稿 `warehouse=getattr(check, 'warehouse', None)`；`complete_adjustment`/`revert_adjustment` 守卫 P0-2 已补（commit `b2b9a94d`）。`scripts/verify_bug_2026_08_02_007.py` 9 项全绿（含 D1 库位关闭时 complete_transfer 不写 LocationInventory 但记流水、D2 盘点草稿带 warehouse），`verify_bug_2026_08_02_003.py`/`verify_adjustment_state_machine.py` 未回归 |
| BUG-2026-08-02-014 | 盘点单 `check.html` 新建弹窗和 `document_table_form.html` 编辑表单无仓库字段，违反 AGENTS.md 仓库必填规则 | `check_list` 路由补传 `warehouses`/`default_warehouse`；`_render_check_form` 补传 `warehouses`/`default_warehouse` 并在 header 带 `warehouse`；`check.html` 新建弹窗加 `<select name="warehouse" required>` 默认预选；`document_table_form.html` check 分支加仓库下拉+required+默认预选；`collectHeader()` check 分支带 warehouse；`refreshWarehouses()` 支持 check（commit `e6b6b772`） |
| BUG-2026-08-02-015 | `adjustment_add.html` 表单无仓库字段，`adjustment_add_page`/`adjustment_detail` 路由未传 `default_warehouse`，且 warehouses 查询未过滤启用状态 | `adjustment_add_page`/`adjustment_detail` 改用 `get_active_warehouses()` 并传 `default_warehouse=get_default_warehouse()`；模板在操作人旁补 `<select name="warehouse" required>` 编辑回填 `adjustment.warehouse`、新建预选默认仓库；`submitForm()` 增加仓库非空前端校验并写入 data.warehouse（commit `479bfcc7`） |
| BUG-2026-08-02-016 | `transfer.html` 新建弹窗和 `document_table_form.html` 调拨表单的调出/调入仓库下拉无 `required`、无默认预选；`_render_transfer_form`/`transfer_list` 未传 `default_warehouse` | `_render_transfer_form`/`transfer_list` 补传 `default_warehouse=get_default_warehouse()`；`transfer.html` 弹窗调出仓库预选默认仓库、调出/调入加 `*` 必填标记；`document_table_form.html` 调拨分支调出/调入 `<select>` 加 `required`、调出仓库新建时预选默认仓库（commit `fc60ddf8`） |
| BUG-2026-08-02-017 | `opening_stock.html` 新增期初库存单的仓库下拉已有 `required` 但未预选默认仓库；`opening_stock_list` 路由未传 `default_warehouse` | `opening_stock_list` 补传 `default_warehouse=get_default_warehouse()`；`opening_stock.html` 仓库 `<option>` 按 `default_warehouse.id == w.id` 预选（commit `5f4f95f9`） |
| BUG-2026-08-02-019 | P1-5 采购入库被设计为必须关联采购订单，与 AGENTS.md"采购订单仅作为可选来源"规则冲突 | 新增/保存/完成 `采购入库` 路径不强制校验 source_purchase_order_id；手工单可直接保存并完成入库；有关联 PO 时仍保留来源/数量/执行进度跟踪。回归 `tests/verify_bug_P15_P16_P21.py` TestBugP15PurchaseInOptionalPurchaseOrder 组 |
| BUG-2026-08-02-020 | P1-6 已完成入库单可通过详情页/列表/批量接口直接删除，违反"人工反提交→草稿→删除"规则 | `delete_in_order` 路由仅允许 pending 单删除，completed/partially_completed 返回 409 `已完成入库单禁止直接删除，请先反提交回草稿状态`；`batch_delete_in_order` 对已完成 ID 整批拒绝。详情页、列表页后端、接口统一规则。回归 `tests/verify_bug_P15_P16_P21.py` TestBugP16CompletedInOrderCannotDeleteDirectly 组 |
| BUG-2026-08-03-001 | 表头列向下填充按钮（`WmsFillDown.fillDown`，app.js）不跳过 `material_code` 空行，把合同编号/工程名称填到所有 15 行（含空行），与"向下填充行数应与物料明细行数一致"规则冲突；昨天 BUG-2026-08-02-021 只修了 Ctrl+D（`setupColumnFillDown`），表头按钮入口未修 | `app/static/js/app.js` `fillDown()` 在遍历源行之后的行时，先检查 `cellFor(row,'material_code')` 是否有值，空行 `skipped++` 跳过不填充，提示含"跳过 N 个空行"；仅在有 `material_code` 列的表格生效，不影响其他表格。回归 `tests/verify_bug_2026_08_03_001_filldown_skip_empty.py` |
| BUG-2026-08-03-002 | Ctrl+D 向下填充（`setupColumnFillDown`）与表头按钮（`WmsFillDown.fillDown`）是两套独立实现：① Ctrl+D 仅采购入库有，销售订单/采购订单/出库单无 Ctrl+D；② Ctrl+D 填数量/单价后不联动金额（`isAmount` 死代码，`calcAmount` 永不触发），按钮会联动；③ 两套实现易出现"修一处漏一处"的回归（正是 BUG-2026-08-02-021→001 的根因） | 将 Ctrl+D 统一到 `app/static/js/app.js` 的 `WmsFillDown` IIFE：新增 keydown 监听复用 `fillDown(table,key)`，所有页面自动获得 Ctrl+D；移除 `in_order_add.html` 的 `setupColumnFillDown`（避免双重触发）。两入口共用同一函数，行为永远一致（跳过空行、派发 input/change 联动金额、提示文案相同）。回归 `tests/verify_bug_2026_08_02_021_in_order_contract.py` T1-T2、`tests/verify_bug_2026_08_03_001_filldown_skip_empty.py` |

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
| BUG-2026-08-04-001 | `add_location_inventory_atomic` 建账冲突时 `db.session.rollback()` 回滚整个外层事务，导致总库存与库位库存、单据状态永久不一致 | 检查 INSERT 冲突时用 `begin_nested()`（SAVEPOINT），只回滚保存点，外层事务不受影响；重查后走原子 UPDATE。回归测试 `tests/verify_bug_2026_08_04_001_location_inventory_savepoint.py`，SHA `8cdfac0f` |
| BUG-2026-08-04-002 | `update_location_inventory` 负 delta 无库位记录时返回 `True, ''`（静默成功），`batch_complete_out_order` 总库存已扣但库位库存未扣 | 检查无库位记录且不允许负库存时返回 `False` + 错误信息，与 `deduct_location_inventory_atomic` 对齐。回归测试 `tests/verify_bug_2026_08_04_002_location_inventory_no_silent_success.py`，SHA `8efc4bbd` |
| BUG-2026-08-04-003 | `update_completed_in_order` 缺 `_acquire_order_write_lock`，并发编辑/反提交时库存调整可能重复执行或对 pending 单据做库存操作 | 检查库存操作前加 `_acquire_order_write_lock(InOrder, id, 'completed')`，加锁后重新读取状态并做仓库赋值。回归测试 `tests/verify_bug_2026_08_04_003_update_completed_in_order_lock.py`，SHA `aaf2b418` |
| BUG-2026-08-04-004 | 导入物料不成功没有提示原因：①`wants_json_error_response()` 只判断 `/api/` 前缀，`/material/import` AJAX POST 在 CSRF 失效时返回 302 重定向 → 前端 `r.json()` 解析 HTML 失败 → 只显示"请求失败：Unexpected token..."；②`material.html` / `batch_import.html` 导入回调未检查 `response.ok`，非 JSON 错误体丢失 `msg` | ①`wants_json_error_response()` 额外识别 `X-Requested-With: XMLHttpRequest` 与 `Accept: application/json`，AJAX 请求统一返回 JSON；②前端先检查 `response.ok`，非 2xx 时优先取 `err.msg`，非 JSON 时用 HTTP 状态码 + 友好提示。回归测试 `tests/verify_bug_2026_08_04_004_import_error_feedback.py`，SHA `045205e5` |
| BUG-2026-08-04-005 | `edit_material` 中 `spec_changed = (material.spec != new_spec)` 在 `material.spec = new_spec` 赋值之后比较，导致永为 False，规格变更不级联更新关联单据；更严重的是级联代码引用 `InOrderItem`/`OutOrderItem`/`InventoryCheckItem`/`SubcontractItem`/`BOMItem` 不存在的 `material_code`/`material_name`/`spec` 字段，一旦 `spec_changed` 为 True 会抛 `AttributeError` 导致编辑 500；`PurchaseRequestItem.spec` 也漏了级联更新 | ①在赋值前捕获 `old_spec` 并计算 `spec_changed`；②级联代码对没有冗余字段的明细类跳过赋值（`hasattr` 守卫或直接跳过），`PurchaseRequestItem` 补 `spec` 级联。回归测试 `tests/verify_bug_2026_08_04_005_spec_changed_cascade.py`（4 场景：spec 级联、不抛 AttributeError、不改规格保持不变、name 级联），SHA `32e3deb8` |
| BUG-2026-08-04-006 | `/api/ai/recommend_location` 和 `/api/ai/demand_forecast` 用 `Material.query.filter_by(status='active')` 查询，但 `Material` 模型没有 `status` 字段，导致 SQLAlchemy 抛 "Unknown column material.status" 错误，AI 库位推荐和需求预测功能直接 500 不可用 | 移除 `filter_by(status='active')`，改为 `Material.query.all()` / `Material.query`，因为 Material 模型没有启用/停用状态概念。回归测试 `tests/verify_bug_2026_08_04_006_ai_route_status_field.py`（4 场景：库位推荐不 500、需求预测无物料返回空、有物料返回 materials 列表、Material.query 不引用 status 列） |
| BUG-2026-08-04-007 | `edit_material` 用 `MAX_TRANSACTION_PRICE`（1 万亿）作为价格上限，而 `add_material` 用 `MAX_REASONABLE_PRICE`（99,999,999.99），编辑可绕过新增的价格上限，先低价新增再编辑改成天价 | `edit_material` 改用 `MAX_REASONABLE_PRICE`，与 `add_material` 保持一致；错误消息统一为 `参考价格必须是 0 至 99,999,999.99 的有限数字`。回归测试 `tests/verify_bug_2026_08_04_007_edit_material_price_limit.py`（4 场景：超限 400 拒绝、恰好上限 200 成功、正常值 200 成功、新增侧超限仍 400 拒绝） |
| BUG-2026-08-04-008 | `import_material` 不做 `sanitize_text_input`（XSS/NUL 防护）、不做 code/name/spec 长度校验、不做价格上限校验（直接 `float()`），与 `add_material` 不一致，可通过 Excel 导入注入 XSS、超长字段（DB 静默截断）、天价/负价物料 | 导入走 `sanitize_text_input` + 原始值长度校验（code≤50/name≤100/spec≤100/brand≤100，超限行跳过并告知原因）+ 价格显式校验（0 至 `MAX_REASONABLE_PRICE`，负数/超限/NaN 行跳过）。回归测试 `tests/verify_bug_2026_08_04_008_import_validation.py`（6 场景：编码超长跳过、名称超长跳过、价格超限跳过、负价跳过、XSS 标签去除、正常数据导入成功） |
| BUG-2026-08-04-009 | `add_material` 创建物料时直接写 `material.stock = initial_stock`，但不在 `stock_transaction` 表记录 opening 流水，导致库存台账/月报无法追溯初始库存来源 | 物料创建并提交后，若 `initial_stock > 0`，用 `add_stock_transaction` 追加一条 `StockTransaction`（`transaction_type='opening'`，`reference_type='opening_stock'`，`location` 取默认仓库名），与期初库存调整语义一致。回归测试 `tests/verify_bug_2026_08_04_009_add_material_stock_audit.py`（3 场景：初始库存>0 生成流水、初始库存=0 不生成、流水数量/类型/物料正确） |
| BUG-2026-08-04-010 | 复制物料保存后采购入库单不显示该物料：各单据页（in_order_add.html 等）的“刷新物料”逻辑只拉取 `/material/api/all` 第一页（默认 500 条），而物料按编码升序排列，新增/复制的物料编码通常排在末尾被分页截断，导致下拉列表里永远看不到新物料 | ①后端 `/material/api/all` 默认分页从 500 提到 2000（`per_page` 上限 2000），返回 `materials` 数组 + 分页元数据（total/page/truncated/next_page）；②前端 `refreshMaterials` 重构为 `fetchAllMaterials` 递归分页拉取全部物料再合并，确保末尾新增/复制的物料也能加载；③BroadcastChannel 收到 `material_updated` 时静默刷新。回归测试 `tests/verify_bug_2026_08_04_010_material_api_all_response_key.py`（3 场景：分页元数据正确、materials 数组、复制物料保存后出现在 materials） |

## 未修复/待处理

| 编号 | 标题 | 现状与绕过方案 |
|------|------|---------------|
| BUG-2026-07-31-002 | `main` 分支未设置 protected branch，开发者可直接 push 绕过 PR + review | 尝试 `gh api -X PUT repos/SIX2090/wms/branches/main/protection` 设置（要求 1 approving review + strict status checks + linear history + no force push + 解决所有 conversation），但 GitHub 返回 `403 Resource not accessible by integration`：当前 GH_TOKEN 属于 GitHub App（client_id `Iv23liZK8tzQx0m4bCRd`），按 GitHub 平台硬限制，GitHub App token 没有 `Administration: write` 权限修改 branch protection。**绕过方案**：仓库 owner（`SIX2090`）在 GitHub Web UI → Settings → Branches → Add rule for `main` 手动开启 "Require a pull request before merging" + "Require approvals: 1" + "Require status checks: lint-and-test" + "Require linear history" + "Do not allow force pushes" + "Do not allow deletions"。或重新生成 fine-grained PAT 时勾选 "Administration: write"（含 "Branch protection rules"），用该 PAT 跑本任务第 3 步的 PUT 命令。已尝试的 API：GET/PUT/PATCH `/branches/main/protection[/*]` 全部 `403`。本地防线：`.githooks/pre-push` 钩子会拒绝向非 `main` 分支推送，未来启用 Web 端保护后服务端兜底。<br>**2026-07-31 二次验证（commit `aa253a1d`）**：用户在 Web UI 已启用 `required_status_checks: lint-and-test`（`enforcement_level: non_admins`），但 `protected: false` 表明 "Require a pull request before merging" / 阻止直接 push **未启用**。直接 push 一个空行 commit 到 main（commit `e6dcb62e`）→ GitHub 服务端 200 接受 → 已用 `aa253a1d` revert。**结论：保护仅部分生效（status check），直接 push 仍可绕过 PR + review，BUG 维持未修复状态**。Web UI 需补勾 "Require a pull request before merging"（关键项）+ "Do not allow force pushes"。<br>**2026-07-31 三次验证（实测 commit `1acfee0e` 已 force-push 撤销，main 回到 `c149e4b4`，无遗留）**：用户反馈 Web UI 已勾选全部 9 项规则（含 Require pull request / Do not allow force pushes 等），但 UI 底部仍提示 "Not enforced"（需升级 Team/Enterprise 或公开仓库）。实测三步：①`gh api repos/SIX2090/wms/branches/main` 读到 `protection: { enabled: true, required_status_checks: { enforcement_level: "non_admins", contexts: ["lint-and-test"] } }`——**API 仅存 1 项 status check，其余 8 项未持久化**；②`echo "" >> README.md && git commit && git push origin main` 成功（`c149e4b4..1acfee0e main -> main`），无 GH006 报错；③`git reset --hard c149e4b4 && git push -f origin main` 也成功（`+ 1acfee0e...c149e4b4 main -> main (forced update)`）。**结论确认**：GitHub 免费版 + 私有仓库下 protected branch 是"摆设"——UI 允许勾选但 GET 不到、push 不被拦。`enforcement_level: non_admins` 正是平台标记 admin 不受 status check 约束的字段。**3 条解决路径（按优先级）**：①升级 GitHub Team（$4/user/月）→ 私有仓库保护规则强制执行；②仓库转 public（损失代码私有性）；③接受现状，依赖 `.githooks/pre-commit` + `.githooks/pre-push` + `lint-and-test` CI 三道兜底（当前已具备）。**当前采用路径 ③**，服务端保护作为深度防御待 GitHub 升级后启用。 |

## 每日使用方式

```powershell
.\scripts\python.cmd scripts\verify_wms_bugs.py
.\scripts\python.cmd scripts\scan_wms_risks.py
```

规则：`verify_wms_bugs.py` 失败才需要立即处理；`scan_wms_risks.py` 输出的是候选风险，必须人工判真后才能进入 BUG 修复。
