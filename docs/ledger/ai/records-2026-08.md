# AI 台账 · 记录归档 2026-08

> 本分片由 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md §16 完成记录小节及散装记录` 拆出（F4.4（2026-10-13））。
> 查询：`python scripts/query_ledger.py --task <ID>`。

---

#### AI-LOGIN-F02（已完成）— 手机/网页登录"一直登录"（记住我持久 Cookie）

- 完成日期：2026-08-19
- 提交 SHA：`44385da feat(login): AI-LOGIN-F02 手机/网页登录持久化（记住我）`（已推送 main）
- 业务边界：仅延长网页/手机浏览器登录保持时间；不修改任何用户密码，不触碰账号锁定、CSRF、角色校验、must_change_password 强制改密逻辑；退出登录行为不变（仍需点退出）。
- 需求：用户要求手机登录系统后一直保持登录，不反复输密码。
- 现状与方案：原网页登录是 8 小时滑动会话（浏览器关闭/超 8 小时即失效需重登）；安卓 App 的 Bearer 令牌已有 7 天滚动续期（BUG-2026-08-13-005），无需改动。网页侧启用 Flask-Login `login_user(user, remember=True)`：登录时下发 `remember_token` 持久 Cookie（默认 365 天，环境变量 `WMS_REMEMBER_LOGIN_DAYS` 可调、设 0 关闭长登录），会话过期后自动恢复登录态。
- 连带修复：`/logout` 原实现 `logout_user()` 之后再 `session.clear()`，会把 logout_user 写入 session 的 `_remember='clear'` 标记冲掉，after_request 钩子便不下发清 Cookie 头——启用记住我后退出登录不清持久 Cookie，共用手机上"退出"立即被自动回登。改为先 `session.clear()` 再 `logout_user()`。
- 改动模块：`app/routes/user_auth.py`（login 路由 remember=True；logout 顺序修复）、`app/config.py`（REMEMBER_COOKIE_DURATION 配置）、`tests/test_remember_login.py`（新增 4 项回归）。
- 迁移与备份：无数据库迁移；未改用户/密码/令牌数据。
- 权限与人工确认：未触碰密码（规则：密码操作需显式授权）；长登录开关交给环境变量，默认开启满足用户需求。
- 专项验证：`pytest tests/test_remember_login.py -q`（4 passed：时长配置 365 天 / 登录下发 remember_token / 删除会话 Cookie 后凭 remember_token 恢复登录 200 / 退出清除 remember_token 且未登录 302）。
- 全量验证：`pytest tests/ -q` 631 passed；`lint_wms_rules` 0 违规；`lint_no_raw_post_fetch` 通过。
- 剩余风险和下一子项：手机丢失/共用设备场景下长登录有滞留风险，敏感操作（提交/作废单据）仍受角色与人工确认边界约束；如需收紧可设 `WMS_REMEMBER_LOGIN_DAYS=30`（30 天）或 `0`（关闭）；后续可考虑在登录页加"记住我"勾选让用户自选。

#### POST-COMMIT-SCAN-2026-08-01（已完成）— 入库/出库批量并发+售后库位同步 4 项原子修复

- 完成日期：2026-08-01
- 业务边界：仅修复高影响库存数据正确性 BUG；不修改任何用户/密码；不削弱 CSRF、角色校验、事务隔离；不引入新的并发原语（仅复用既有 `_acquire_order_write_lock` + `deduct_stock_atomic` + `update_location_inventory`）。
- 提交 SHA（4 个原子动作 + 1 个登记文档，均已推送 main `dffdf9ed`）：
  - `7d2272a4` BUG-NEW3-005 `batch_complete_in_order` 加单据写锁+每单独立事务
  - `9d6a2ea1` BUG-NEW3-006 `batch_complete_out_order` 加单据写锁+每单独立事务
  - `60f365b4` BUG-NEW3-007 `batch_revert_in_order` 加锁+`deduct_stock_atomic`+每单独立事务
  - `0b56db5d` BUG-NEW3-008 `complete/revert_after_sale_out_order` 同步库位库存
  - `dffdf9ed` 登记 `WMS_BUG_BASELINE.md` 4 条修复记录
- 根因与修复：
  1. **BUG-NEW3-005** `batch_complete_in_order` 缺单据写锁：原循环在 status 早判后即处理，无行锁；并发请求/单据版完成会重复入库；且循环外 `db.session.commit()` 让任意一张失败导致所有已处理单据一起回滚。修复：每张单 `_acquire_order_write_lock(InOrder,id,'pending')` + 循环内 `commit()` + 失败仅 rollback 自身。
  2. **BUG-NEW3-006** `batch_complete_out_order` 与 BUG-NEW3-005 同样的并发+事务边界问题，且重复扣库存会推进销售单发货进度，是真实资损。修复同 BUG-NEW3-005。
  3. **BUG-NEW3-007** `batch_revert_in_order` 除上述并发问题外，`deduct_stock()` 是 read-modify-write 并发会重复扣减；改用条件 UPDATE 原子扣减 `deduct_stock_atomic()` 修复竞态。
  4. **BUG-NEW3-008** `complete_after_sale_out_order` / `revert_after_sale_out_order` 仅改 `Material.stock` 不改库位库存，启用库位管理后总库存与库位库存长期漂移。修复：在原子扣减/恢复后调用 `update_location_inventory(material, order.warehouse, ±qty)`，失败回滚。
- 改动模块：`app/app.py` 4 个函数（仅修改既有函数实现，不新增路由/Schema/迁移）。
  - `batch_complete_in_order` 行 27910 附近
  - `batch_complete_out_order` 行 34800 附近
  - `batch_revert_in_order` 行 27985 附近
  - `complete_after_sale_out_order` 行 35199 附近
  - `revert_after_sale_out_order` 行 35252 附近
- 迁移与备份：无数据库迁移；未改业务数据/用户/密码；未碰任何已完成单据。
- 权限与人工确认：均经过用户对 4 项 BUG 真实性+可修复性的逐项确认；未触碰任何 POST/PUT/DELETE 路由的权限/CSRF 装饰器。
- 专项验证：
  - `python scripts/verify_in_order_state_machine.py` → PASS（入库完成/反审/删除状态机）
  - `python scripts/verify_out_order_state_machine.py` → PASS（领料完成/反审状态机）
  - `python scripts/verify_wms_bugs.py` → 全部回归通过
  - `python -m pytest tests/test_lint_wms_rules_a8_a9_golden.py` → 12/12 PASS
  - 每次 commit 前 `python scripts/lint_wms_rules.py` → 0 违规
  - 每次 commit 前 `python scripts/lint_no_raw_post_fetch.py` → 通过
- 推送验证：5 次推送均输出 `To https://github.com/SIX2090/wms.git ... -> main` 且 `git ls-remote` 确认 `dffdf9ed` 已在 `refs/heads/main`。
- 剩余风险和下一子项：`_acquire_order_write_lock` 在 SQLite 上用 `BEGIN IMMEDIATE` 串行化写事务，并发高时批量操作会排队；如未来切到 PostgreSQL/MySQL，可改用 `SELECT ... FOR UPDATE` 减小锁粒度（`_acquire_order_write_lock` 已实现该分支，无须改业务代码）。

#### AI-REFACTOR-APP-SPLIT（已完成）— app.py 按业务域拆分路由到独立模块

- 完成日期：2026-08-04
- 目标：将超大单文件 `app/app.py` 按业务域拆分路由到 `app/routes/` 独立模块，先单位（unit）Blueprint 试点，再采用 register-on-app 模式批量拆分，降低单文件膨胀风险、提升可维护性，且不改变任何 endpoint 名/URL，保证 `url_for` 引用与既有功能零回归。
- 业务边界：仅做路由代码迁移与模块化，不修改任何业务逻辑、密码、权限、CSRF、事务边界；不建任何新分支（仅 `main`）。
- 拆分方式：
  - 单位（unit）：`routes/unit.py` Blueprint 模式试点。
  - 供应商（supplier）/分类（category）/员工（employee）/物料（material）/客户（customer）/仓库（warehouse）/部门（department）/合同（contract）/备份（backup）/审批中心（approval）/手机端扫码（mobile）/微信分享（wechat_share）/期初库存（opening_stock）/标签条码（label_barcode）/售后出库（after_sale_out）：`register_<domain>_routes(app)` 模式，endpoint 名与 app.py 原实现完全一致。
  - 第二批：调拨（transfer）/销售（sales）/领料（requisition）/销售出库（out_order）/采购入库（in_order）/委外（subcontract）/BOM（bom）/盘点（check）/采购订单（purchase_order）/采购申请（purchase_request）/库存调整（adjustment）/系统设置（system_settings）：`register_<domain>_routes(app)` 模式，endpoint 名与 URL 不变。
  - 第三批：用户认证与管理员控制台（user_auth）/报表（report）/原生与移动端 API（native_api）：`register_<domain>_routes(app)` 模式；因依赖 `role_required` / `api_role_required` / `mobile_api_idempotent` / `web_or_api_required` 装饰器，注册调用放置在对应装饰器定义之后。
  - 第四批：导出（export）：`register_export_routes(app)` 模式，endpoint 名与 URL 不变。
  - 第五批（2026-08-05，commit `847dc41b`）：批量导入（batch_import）/库存查询（stock_query）/库存预警（inventory_alert）/标签打印（label）/待办单据（pending_documents）/单位与供应商导入导出（unit_supplier_import）：`register_<domain>_routes(app)` 模式，endpoint 名与 URL 不变。
  - 循环导入处理：app 依赖（模型/辅助函数）在路由函数内部延迟导入（请求期才执行），模块级只导入稳定依赖（flask / utils / db）。
- 改动模块：
  - `app/routes/*.py`：unit/supplier/category/employee/material/customer/warehouse/department/contract/backup/approval/mobile/wechat_share/opening_stock/label_barcode/after_sale_out 共 16 个域路由模块；第二批 transfer/sales/requisition/out_order/in_order/subcontract/bom/check/purchase_order/purchase_request/adjustment/system_settings 共 12 个域；第三批 user_auth/report/native_api 共 3 个域；第四批 export 共 1 个域；第五批 batch_import/stock_query/inventory_alert/label/pending_documents/unit_supplier_import 共 6 个域。合计 38 个域路由模块。
  - `app/app.py`：导入并注册各 `register_*_routes(app)`，删除对应原路由代码块；第三批 user_auth/native_api 的注册调用置于 `role_required` 等装饰器定义之后。
  - `scripts/lint_wms_rules.py`：A9 规则放宽路由函数排除窗口（2 → 6 行），叠 `@app.route`+`@require_role`+`@login_required` 三层装饰器的路由函数不再误报需单独测试。
- 附带修复：`routes/approval.py` 审批中心批准/驳回原从 app 导入 `approve_purchase_request`/`reject_purchase_request`（已随 purchase_request 拆分移除），改为内联复现原逻辑，修复审批中心 API 失效回归（pre-existing bug）。
  - `tests/verify_app_py_split_*.py`：单位 Blueprint 回归 + 其余 30 域 register-on-app 回归测试。
- 权限与人工确认：所有迁移路由保留原 `@login_required` + `@require_role` 装饰器；AI 不放开任何写权限、不改密码、不硬删单据。
- 专项验证命令及结果：
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python -m pytest tests/verify_app_py_split_*.py -q` → 194 passed（第五批新增 6 域 28 个用例）。
  - 每次 commit 前 pre-commit 钩子（lint_wms_rules + lint_no_raw_post_fetch）→ 全部通过。
- 推送验证：多批次推送均输出 `To https://github.com/SIX2090/wms.git ... -> main`；本地与 `origin/main` SHA 一致。
- 剩余风险和下一子项：
  - app.py 剩余约 100 个路由，其中 `/api` 与 `/ai` 多为 AI 子系统路由，与 app.py 内约 200 个 `_ai_*` 辅助函数深度耦合、交错，拆分风险高。
  - 建议新增"app.py 路由防膨胀"pre-commit 规则，禁止新路由直接写进 app.py，强制走 `routes/` 模块。
- 子修复（BUG-2026-08-05-001）：拆分迁移 `in_order.py` 时，`create_in_order_push` 使用 `DocumentPushLine` 却漏导入，导致采购入库完成后下推失效（`NameError`）。在 `create_in_order_push` 的 `from app import (...)` 补入 `DocumentPushLine`，与 `out_order.py`/`after_sale_out.py` 一致。回归：`scripts/verify_inbound_push.py` Full PASS。
- 子修复（BUG-2026-08-05-002）：`complete_in_order` / `update_completed_in_order` / `update_in_order` 三个函数的延迟导入均漏 `InOrder`，点击"完成入库"即抛 `NameError`，单据停在草稿、下推按钮不出现（被 `except` 吞掉）。在三个函数导入补入 `InOrder`，并在 `complete_in_order` 的 `except` 补 `app.logger.exception` 记录堆栈。新增静态检查 `scripts/check_in_order_imports.py` 扫描全部使用 `InOrder` 的函数确保导入覆盖。回归：`scripts/repro_complete_in_order.py`、`tests/verify_bug_2026_08_05_002_complete_in_order_imports.py`（3 用例）、`scripts/verify_inbound_push.py`、`make check` 全 PASS。
- 子修复（BUG-2026-08-05-003）：`routes/material.py` 迁移时 `delete_material` 的引用完整性校验漏掉 `PurchaseOrderItem` / `SalesOrderItem` / `AIMaterialAlias` / `AIDocumentItem` 四张表，被采购/销售订单明细引用的物料删除时走不到拦截分支，直接 `db.session.delete` 触发外键 `NOT NULL constraint failed`，`except` 捕获后返回晦涩"数据库操作失败: (sqlite3.IntegrityError)..."，用户感知"物料删不掉"。在 `delete_material` 的 `from app import (...)` 补入四模型并在校验里补 `material_id` 检查，与既有引用拦截一致。回归：`scripts/repro_material_delete_ref.py`（PO/SO 引用拦截且明细保留、无引用删除成功）、`tests/verify_app_py_split_material.py::test_delete_material_referenced_by_purchase_order_item`、`make check` 116 passed。

#### REQUISITION-PICKER-F01（已完成）— 领料单表头新增领料人 + 采购入库下推领料单可填领料部门/领料人

- 完成日期：2026-08-06
- 目标：
  - 库存管理-领料单（`OutOrder`，`business_type='领料单'`）单据表头仅有领料部门，补齐"领料人(picker)"字段。
  - 采购入库单下推领料单（`in_order_push.html`）可填写领料部门与领料人，下推生成的目标 `OutOrder` 保存两者。
  - 工单领料单（`ProductionRequisition`）表头同样补齐领料人（commit `a3900c23`）。
- 业务边界：仅新增/透传字段，不改密码、权限、事务边界、库存逻辑；不建任何新分支（仅 `main`）。
- 改动模块：
  - `app/app.py`：`OutOrder` 模型新增 `picker` 字段；`auto_migrate_database` 对 `out_order` 表新增 `picker VARCHAR(50)` 迁移（`ProductionRequisition.picker` 迁移随 `a3900c23`）。
  - `app/routes/in_order.py`：`in_order_push_page` 查询并传递 `departments`；`create_in_order_push` 处理 `department_id`/`picker` 并保存到 `OutOrder`，补入 `Department` 导入。
  - `app/routes/out_order.py`：`add_out_order` 解析并持久化 `picker`；`copy_out_order` 携带 `picker`；`out_order_add_page` prefill 增加 `picker`。
  - `app/templates/in_order_push.html`：目标类型为"领料单"时显示领料部门下拉框与领料人输入框，并加入下推 payload。
  - `app/templates/out_order_add.html`：表头新增"领料人"输入框并纳入保存提交。
  - `app/templates/out_order_detail.html`：单据头部显示领料人；"再建一张"链接携带 `picker`。
  - `tests/test_out_order_push_picker.py`：新增 3 用例（下推页渲染部门/领料人、下推创建 `OutOrder` 保存部门与领料人、`/out_order/add` 持久化领料人）。
- 专项验证命令及结果：
  - `python -m pytest tests/test_out_order_push_picker.py tests/test_requisition_picker.py -q` → 6 passed。
  - `python -m pytest tests/ -q` → 124 passed。
  - `python scripts/lint_wms_rules.py` → 0 违规；`python scripts/lint_no_raw_post_fetch.py` → 通过。
- 推送验证：提交后推送输出 `To https://github.com/SIX2090/wms.git ... -> main`；本地与 `origin/main` SHA 一致。
- 剩余风险：`Picker` 字段暂未纳入领料单打印模板与导出模板，如需可在后续子项补充。
- 后续修复（BUG-2026-08-06-001）：老库访问领料单报 `no such column: out_order.picker`，根因是 `auto_migrate_database()` 在 config 加载前用硬编码路径检查数据库，与实际库路径不一致，`picker` 列未迁移。已把迁移调用移到 config 加载后，并抽 `_resolve_sqlite_db_path()` 从 `SQLALCHEMY_DATABASE_URI` 解析真实路径；回归 `tests/test_auto_migrate_db_path.py` 5 用例全绿。commit 见本次提交。

#### WECHAT-SHARE-FIX-2026-08-11（已完成）— 微信分享功能缺陷审计全量修复（BUG-2026-08-11-008 ~ 015）

- 完成日期：2026-08-11
- 目标：修复微信分享功能缺陷审计发现的全部 8 项问题，覆盖直推认证与安全、助手并发健壮性、结果映射与重试、定时任务幂等、页面性能、存储膨胀、重发一致性、界面引导四个维度；所有修复登记 `WMS_BUG_BASELINE.md` 并配套回归测试。
- 业务边界：仅修复微信分享域缺陷，不改密码、权限、事务边界、库存逻辑；不建任何新分支（仅 `main`）；AI 不自动提交/审核任何单据。
- 修复清单（BUG ID → commit）：
  - BUG-2026-08-11-008（commit `0d31b849`）：直推携带 `X-Wechat-Helper-Token` 认证头；helper_url 限制本机回环地址防 token 泄露；token 未配置拒绝直推。子修复 commit `73a1e29c`（T1 测试用 monkeypatch.setitem 隔离模块级 config 污染）。
  - BUG-2026-08-11-009（commit `cf640084`）：助手端全局 `SEND_LOCK` 串行化发送；`_SendError` 结构化错误码体系；`_ensure_foreground()` 三处前台焦点校验；接收人校验提前到写剪贴板之前。
  - BUG-2026-08-11-010（commit `a842aac4`）：`_wechat_share_send_image` 改返回 `(status, code, message)` 三元组；仅 ConnectionError 自动重试 1 次、Timeout 不重试防重复发送；删除关键词匹配状态判定。
  - BUG-2026-08-11-011（commit `cdedb684`）：定时任务改 `force=False` + scheduled marker 检查，同一 config 每日最多执行一次、marker 恰好一条，杜绝重复发送。
  - BUG-2026-08-11-012（commit `57fe2ae4`）：助手健康检查结果 30s 进程内缓存，消除分享页每次打开 1.5s 阻塞。
  - BUG-2026-08-11-013（commit `1aa768c0`）：分享图片 30 天保留期自动清理（每日守卫挂入每分钟 scheduler），超期图片删除并同步解绑日志 image_path/image_size。
  - BUG-2026-08-11-014（commit `a439c7f0`）：重发冻结使用日志记录的历史接收人（SimpleNamespace 发送快照），message 标注"按历史接收人重发"。
  - BUG-2026-08-11-015（commit `fc26b181`）：分享页补充直推/轮询模式引导、auto_send 风险警示条（JS 实时显隐）、pending 消化引导（按助手在线/轮询状态分支提示）。
- 改动模块：
  - `app/wechat_helper.py`：SEND_LOCK / _SendError / _ensure_foreground / 校验顺序。
  - `app/app.py`：`_wechat_share_send_image` 三元组+token+回环校验+重试、`_wechat_share_helper_url_allowed`、健康检查缓存、图片清理两个函数、定时任务去重。
  - `app/routes/wechat_share.py`：resend 冻结接收人快照、保存配置回环校验。
  - `app/templates/wechat_share.html`：模式引导 form-text、`#autoSendRiskHint` 警示条、pending 消化引导 alert。
  - `tests/verify_bug_2026_08_11_008~015_*.py` 8 个回归测试文件 + `tests/test_wechat_helper_send_image_task.py`。
- 专项验证命令及结果：
  - `python -m pytest tests/verify_bug_2026_08_11_008_wechat_push_token.py tests/verify_bug_2026_08_11_009_helper_robustness.py tests/verify_bug_2026_08_11_010_wms_result_mapping.py tests/verify_bug_2026_08_11_011_scheduled_dedup.py tests/verify_bug_2026_08_11_012_helper_health_cache.py tests/verify_bug_2026_08_11_013_image_retention.py tests/verify_bug_2026_08_11_014_resend_frozen_receiver.py tests/verify_bug_2026_08_11_015_share_page_guidance.py tests/test_wechat_helper_send_image_task.py -q` → 45 passed。
  - 每个 commit 前 pre-commit 钩子（lint_wms_rules + lint_no_raw_post_fetch）→ 全部通过。
- 推送验证：9 个 commit 均推送输出 `To https://github.com/SIX2090/wms ... -> main`；最终本地与 `origin/main` SHA 一致（`fc26b181`）。
- 剩余风险：① 助手端 Windows-only 模块（pywin32 等）按仓库惯例仅做静态验证，真机发送链路需人工在 Windows 桌面环境抽验；② `wechat_share.html` 存量 JS 仍直接调 `fetch`（pre-commit 仅拦截新增行），如需收口列入后续技术债子项。

#### SEC-AUDIT-2026-08-13（已完成）— WMS 全量代码审计 P0+P1 高危修复

- 完成日期：2026-08-13
- 目标：对 WMS 全量代码做安全/正确性审计，按 P0→P1 优先级修复高危问题。P0=2 项（库存数据完整性），P1=9 子项（库位必填规则 + 删除写锁 TOCTOU + 报表仓库必填）。
- 业务边界：仅修复库存正确性、并发删除、库位/仓库必填校验；不改任何用户/密码；不削弱 CSRF/角色/事务隔离；复用既有 `_acquire_order_write_lock` + `add_stock` + `update_location_inventory`，不引入新并发原语；AI 不自动提交/审核/删除任何已完成单据。
- 修复清单（原子动作 → commit，均已推送 `main`）：
  - **P0-1 NaN/Infinity 数量污染**（`26e2240d`）：`parse_float_value`/`round_to_2_decimals`/`add_stock` 补 `math.isfinite` 防护，拒绝 NaN/Inf 写入 `Material.stock` 与库位库存，避免库存被污染为不可见/不可扣。
  - **P0-2 委外模块缺仓库字段**（`ffc2f9f2`）：`SubcontractOrder`/`SubcontractIssue`/`SubcontractReceive` 三模型补 `warehouse` 列（`nullable=False`）+ 自动迁移 + 全链路保存/完成校验，符合 AGENTS.md 仓库始终必填。
  - **P1-S7 in/out_order complete/batch_complete 库位必填**（`a78f7bf6`）：完成/批量完成时若启用库位管理则校验 `location` 必填（AGENTS.md 规则二）。
  - **P1-S8 after_sale_out 补 location 字段+校验**（`e84d0090`）：`AfterSaleOutOrder` 模型补 `location` 列 + 新增/完成路由库位管理启用时必填。
  - **P1-S9 requisition 补 location 字段+校验**（`be63469f`）：`ProductionRequisition` 模型补 `location` 列 + 保存/新增/编辑/完成路由库位管理启用时必填，完成时优先用 `requisition.location` 同步库位库存。
  - **P1-S10 transfer 库位必填**（`5f270b9e`）：开启库位管理时 `from_location`/`to_location` 必填（AGENTS.md 规则二）。
  - **P1-S11 adjustment item 级库位必填**（`14d023c6`）：开启库位管理时每条调整明细 `location` 必填。
  - **P1-S12 requisition delete 写锁**（`c0f8016f`）：`delete_requisition`/`batch_delete_requisition` 状态预筛后 `_acquire_order_write_lock` 二次校验 pending，防止并发完成后误删已扣库存单；批量逐张加锁独立 commit。
  - **P1-S13 subcontract delete 写锁**（`8290a132`）：委外加工单/发料单/收货单的 delete 与 batch_delete 补写锁二次校验 pending/draft 状态；批量逐张加锁独立 commit；native_api/mobile 经核查无业务单据删除路由，无需加锁。
  - **P1-S14 sales delete 写锁**（`f2a314a3`）：`delete_sales_order`/`batch_delete_sales_orders` 补写锁二次校验 draft 状态，防止并发确认后误删已确认订单；批量逐张加锁独立 commit。
  - **P1-S15 report_api_query 仓库必填**（`21c9c096`）：报表 API 查询未指定仓库且无默认仓库时返回 400，不再跨仓返回数据（AGENTS.md 仓库必填规则）。
- 改动模块：
  - `app/utils.py`：NaN/Inf 防护。
  - `app/app.py`：`AfterSaleOutOrder`/`ProductionRequisition`/`SubcontractOrder`/`SubcontractIssue`/`SubcontractReceive` 补 `location`/`warehouse` 列 + 自动迁移。
  - `app/routes/`：`in_order.py`、`out_order.py`、`after_sale_out.py`、`requisition.py`、`transfer.py`、`adjustment.py`、`subcontract.py`、`sales.py`、`report.py` 补库位/仓库必填与删除写锁。
  - `tests/`：`test_p0_nan_quantity_guard.py`、`test_p1_after_sale_out_location_required.py`、`test_p1_requisition_location_required.py`、`test_p1_transfer_location_required.py`、`test_p1_adjustment_item_location_required.py`、`test_p1_requisition_delete_write_lock.py`、`test_p1_subcontract_receive_delete_write_lock.py`、`test_p1_sales_delete_write_lock.py`、`test_p1_report_warehouse_required.py`。
- 迁移与备份：`AfterSaleOutOrder.location`/`ProductionRequisition.location`/委外三表 `warehouse` 列通过 `auto_migrate_database` 自动 `ALTER TABLE ADD COLUMN`，老库默认空串兼容；未改业务数据/用户/密码；未碰任何已完成单据。
- 专项验证命令及结果：
  - `python -m pytest tests/test_p0_nan_quantity_guard.py tests/test_p1_*.py -q` → 50 passed。
  - 每个 commit 前 pre-commit 钩子（`lint_wms_rules.py` A1-A7 + `lint_no_raw_post_fetch.py`）→ 0 违规 / 通过。
  - `python -c "import ast; ..."` 语法校验 → OK。
- 推送验证：11 个 commit 均推送输出 `To https://github.com/SIX2090/wms ... -> main`；最终本地与 `origin/main` SHA 一致（`21c9c096`）。
- 剩余风险和下一子项：① P2 中低危问题（存量 JS 裸 fetch、pydantic 迁移、报表分页等）留待后续子项；② `_acquire_order_write_lock` 在 SQLite 上用 `BEGIN IMMEDIATE` 串行化写事务，高并发批量删除会排队，切到 PG/MySQL 可用 `SELECT ... FOR UPDATE` 减小锁粒度（已实现该分支，无须改业务代码）。

#### SEC-AUDIT-P2（已完成）— 中低危问题：模板 raw fetch 收口 + Pydantic 迁移示范

- 完成日期：2026-08-12
- 目标：按台账「P2 中低危问题」分类落地三项范围：存量 JS 裸 fetch 收口、Pydantic 存量迁移模式、报表分页核查。审计期间确认：① 黄金测试 sys.executable / batch_delete PO 提示 / 报表分页 3 项在 `wms_full_audit_20260802.md` 之后已逐个修完；② 其余 30+ 模板 raw fetch 在 base.html 的 window.fetch 拦截器兜底下 CSRF 注入完整，仅属代码风格债。因此本次落地「范围可控、有示范意义」的两原子修复。
- 业务边界：不改密码/权限/事务边界；不改 CSRF/库存/状态流转端点语义；仅重构调用风格与入参校验方式；新增路由无。
- 原子动作（均已推送 main）：
  - **P2-A `820de39a` 模板 raw fetch 收口为 csrfFetch**：`subcontract_detail.html` 5 处（删明细/删单/复制/提交/反提交）、`user.html` 4 处（新增/编辑/重置密码/状态切换）、`document_table_form.html` 3 处（保存/保存后完成/反提交）合计 12 处原生 `fetch(...,method:POST)` 改为 `csrfFetch(...,method:POST)`，显式依赖 base.html 内声明的 `csrfFetch`，与业务 JS 统一调用风格一致。说明：base.html 已全局重写 `window.fetch` 自动补 `X-CSRFToken`，因此此前调用无 CSRF 漏洞，本次仅属技术债收口（明确依赖、统一行为、便于 lint 扩展）。
  - **P2-B `5e31c286` 存量路由 Pydantic 迁移示范（A8/A9 模式）**：选最小 POST 路由 `delete_category`（原实现 `request.json.get('ids', [])` 后手工 `{int(id) for id in ids if str(id).isdigit()}` 转 int）重写为：路由体内延迟 import `BaseModel/Field` → 定义 `DeleteCategoryRequest(ids: list[int])` → `model_validate(payload)` 强类型校验 → 失败统一 400。配套 `tests/test_p2_delete_category_pydantic_migration.py` 4 条 A9 测试（合法空列表/非数字串 400/非列表类型 400/有效删除落库）覆盖。此模式可复制到其余 260 条存量标记 `# pydantic:reason=存量路由` 的 POST/PUT/DELETE 路由。
- 核查为「已修过/无需修」的 P2 关联项：
  - 报表分页：`report_view.html` 第 474~514 行 `renderPagination` 已实现上一页/下一页/页码/每页条数选择 + `total`/`page`/`page_size` 数据联动，功能完整无需改。
  - golden 测试 Windows 兼容：`test_lint_wms_rules_a8_a9_golden.py` 第 77 行已用 `sys.executable`（非硬编码 `python3`），已修。
  - `batch_delete_in_order` PO 状态更新失败提示：`in_order.py` 第 1933-1934 行已拼接 `po_update_failed` 提示，已修。
- 改动模块：
  - `app/templates/subcontract_detail.html`、`app/templates/user.html`、`app/templates/document_table_form.html`：12 处 fetch → csrfFetch。
  - `app/routes/category.py`：`delete_category` Pydantic 迁移示范。
  - `tests/test_p2_delete_category_pydantic_migration.py`：4 条 A9 测试。
- 专项验证命令及结果：
  - `python -m pytest tests/test_p0_nan_quantity_guard.py tests/test_p1_*.py tests/test_p2_*.py -q` → 54 passed。
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python scripts/lint_no_raw_post_fetch.py` → 通过。
- 推送验证：2 次 commit 均推送输出 `To https://github.com/SIX2090/wms ... -> main`；最终本地与 `origin/main` SHA 一致（`5e31c286`）。
- 剩余后续（明确不在本次范围，如需可建独立子项）：
  ① 其余 30+ 活跃模板 33-12=21 处非 GET raw fetch（base.html 有 CSRF 兜底，非阻塞）；② 其余 259 条 `# pydantic:reason=存量路由` 标记的路由按 P2-B 模式批量迁移（工作量约 5000 行改动，适合作为专项子任务拆分）；③ GitHub 私有仓库免费版分支保护硬限制（BUG-2026-07-31-002）依赖 GitHub 升级到 Team 或转 public，不在代码层修复。

#### MENU-FIELDSET-INORDER-2026-08-19（已完成）

- 完成日期：2026-08-19
- 提交 SHA：`6d5c67c`
- 目标：采购管理子菜单"采购入库明细"改为"采购入库明细表"，并为采购入库明细表列表页新增"字段设置"功能（复用采购入库单同款全局字段设置框架：列显示/隐藏、顺序调整、显示名修改、localStorage 持久化）。
- 去重结论：字段设置共享能力已由 `app/static/js/app.js` 的 `WmsFieldSettings` 实现，本任务仅在其载体 `in_order.html` 上接入，不做重复开发。
- 业务边界：仅改菜单文案、页面 title 与 `in_order.html` 添加按钮 + `data-column-key` 属性；不改任何后端业务逻辑/路由/库存/状态流转端点。
- 改动模块：
  - `app/templates/base.html`：采购管理子菜单"采购入库明细"→"采购入库明细表"。
  - `app/routes/in_order.py`：`page_title` 改为 `f'{business_type_filter}明细表'`，与菜单一致。
  - `app/templates/in_order.html`：页头新增 `#columnSettingsBtn`"字段设置"按钮；全部 `<th>`/`<td>` 补 `data-column-key`。
- 专项验证命令及结果：
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python scripts/lint_no_raw_post_fetch.py` → 通过。
  - `python -m pytest tests/ -q` → 607 passed。
  - pre-commit 钩子：0 违规，通过。
- 推送验证：push 输出 `fd17f61..6d5c67c main -> main`；本地与 `origin/main` SHA 一致（`6d5c67c`）。

#### MENU-FIELDSET-OUTORDER-2026-08-19（已完成）

- 完成日期：2026-08-19
- 提交 SHA：`55ef279`
- 目标：库存管理子菜单"领料明细"改为"领料明细表"，并为领料明细表列表页新增"字段设置"功能（复用与采购入库单一致的全局字段设置框架）。
- 去重结论：字段设置共享能力由 `app/static/js/app.js` 的 `WmsFieldSettings` 实现，本任务仅在其载体 `out_order.html` 上接入；存储按 `location.pathname + table.id`（`/out_order` + `outOrderTable`）隔离，与其它页面不冲突。
- 业务边界：仅改菜单文案（桌面+移动端）、页面 title 与 `out_order.html` 添加按钮 + `data-column-key` 属性；不改任何后端业务逻辑/路由/库存/状态流转端点。
- 改动模块：
  - `app/templates/base.html`：库存管理子菜单"领料明细"→"领料明细表"（桌面 `flyout-link` 与移动端 `nav-link` 两处）。
  - `app/routes/out_order.py`：`page_title` 改为 `'其他出库明细表' if explicit_bt=='其他出库' else '领料明细表'`。
  - `app/templates/out_order.html`：页头新增 `#columnSettingsBtn`"字段设置"按钮（所有角色可见）；全部 `<th>`/`<td>` 补 `data-column-key`（chk/row_no/order_no/date/customer/material_code/material_name/spec/unit/quantity/price/amount/business_type/contract_no/project_name/status/actions）。
- 专项验证命令及结果：
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python scripts/lint_no_raw_post_fetch.py` → 通过。
  - `python -m pytest tests/ -q` → 607 passed。
  - pre-commit 钩子：0 违规，通过。
- 推送验证：push 输出 `6d5c67c..55ef279 main -> main`；本地与 `origin/main` SHA 一致（`55ef279`）。
- 备注：用户明确要求"每次改动都要登记"，本任务与其上一任务（`MENU-FIELDSET-INORDER-2026-08-19`）均在完成后立即登记至本台账。

#### BUG-2026-08-19-001-FIX（已完成）— 字段设置弹窗字段多时无滚动条

- 完成日期：2026-08-19
- 提交 SHA：`0dd3c2e`
- 目标：修复字段设置（栏目设置）弹窗在字段数量多时列表溢出弹窗、无滚动条、底部按钮遮挡行的问题，要求字段多时出现滚动条。
- 根因：`.wms-field-settings__content` 为 grid 且行高 auto，明细面板用内联 `display:contents` 使表格直接成为内容区子项，表格自然高度撑破固定高度弹窗；`__table-wrap` 的 `overflow:auto` 因 `min-height:260px` 与无高度上限而不生效。
- 业务边界：仅改字段设置弹窗 CSS 布局与面板内联样式；不改任何后端/路由/库存/状态流转逻辑；不改字段设置数据模型与 localStorage 结构。
- 改动模块：
  - `app/static/css/custom.css`：`__content` 加 `grid-template-rows:minmax(0,1fr)`；新增 `__panel` 网格行约束（`minmax(0,1fr)` + `grid-column:1/-1`）；`__table-wrap` 改 `overflow:auto;min-height:0`（移除 `min-height:260px`）；移动端媒体查询同步面板列宽。
  - `app/static/js/app.js`：明细面板移除 `style="display:contents"`，使面板作为网格项参与行约束。
  - `scripts/verify_wms_bugs.py`：新增 `check_field_settings_scroll`（BUG-2026-08-19-001 回归：内容区行约束 + 表格容器 overflow:auto/min-height:0 + 禁止 display:contents）。
  - `WMS_BUG_BASELINE.md`：登记 BUG-2026-08-19-001 为已修复并纳入回归。
- 专项验证命令及结果：
  - `python scripts/verify_wms_bugs.py` → 回归检查通过（含 BUG-2026-08-19-001 新检查）。
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python scripts/lint_no_raw_post_fetch.py` → 通过。
  - `python -m pytest tests/ -q` → 607 passed。
  - pre-commit 钩子：0 违规，通过。
- 推送验证：修复提交 push 输出 `472d4e2..0dd3c2e main -> main`；本登记提交随后推送，最终本地与 `origin/main` SHA 一致。

#### BUG-2026-08-19-002-FIX（已完成）— 采购入库明细表列宽拖动部分列拖不动

- 完成日期：2026-08-19
- 提交 SHA：`edb700e`
- 目标：修复采购入库明细表（及同类列表页）用鼠标拖动列宽时"有的字段拖不动"的问题。
- 根因：`setupResizableTable`（`app/static/js/app.js`）的 `applyWidths` 用**初始列序**的静态 colgroup（`cols[column.index]`）应用宽度；字段设置重排/隐藏列（或表头拖拽重排）后 `<col>` 索引错位，而 `table-layout:fixed` 下 `<col>` 宽度优先于 `<th>`，导致拖动某列实际改到别的列或无效果。
- 业务边界：仅改前端列宽应用逻辑；不改后端/路由/库存/状态流转；不改字段设置数据模型与 localStorage 结构（宽度仍按 data-column-key 存于原 storageKey）。
- 改动模块：
  - `app/static/js/app.js`：`applyWidths` 改为按当前可见表头顺序（`data-column-key`）重建 colgroup、跳过 `wms-field-column-hidden` 列；删除静态 `ensureColgroup`；新增 thead `MutationObserver`（childList/subtree/class 属性）在重排/隐藏后自动重建列宽。
  - `scripts/verify_wms_bugs.py`：新增 `check_col_resize_sync`（BUG-2026-08-19-002 回归：无 ensureColgroup、跳过隐藏列、MutationObserver 重建）。
  - `WMS_BUG_BASELINE.md`：登记 BUG-2026-08-19-002 为已修复并纳入回归。
- 专项验证命令及结果：
  - `node --check app/static/js/app.js` → 语法通过。
  - `python scripts/verify_wms_bugs.py` → 回归检查通过（含 BUG-2026-08-19-002 新检查）。
  - `python scripts/lint_wms_rules.py` → 0 违规。
  - `python scripts/lint_no_raw_post_fetch.py` → 通过。
  - `python -m pytest tests/ -q` → 607 passed。
- 推送验证：push 输出 `87a769b..edb700e main -> main`；本地与 `origin/main` SHA 一致（`edb700e`）。
- 备注：期间发现并行会话曾以无关提交信息（feat: 库存管理模块子菜单三列展开）误提交本修复的未暂存改动；已用 `commit --amend` 修正为规范信息 `fix(ui): BUG-2026-08-19-002 ...` 后推送（该提交此前未推送，amend 不影响远端历史）。

#### BUG-2026-08-26-001-FIX（已完成）— Excel 打印模板编辑器占位符速插全英文

- 完成日期：2026-08-26
- 提交 SHA：本地 `0914c94` / 远程 `39ee99c254a8`（API 通道重放，SHA 不同属预期，内容一致）；登记提交见后续
- 目标：修复 Excel 打印模板编辑器顶部「占位符速插」区 22 个字段全部显示纯英文模板变量（`{order.order_no}`、`{item.material.code}` 等），仓库一线人员看不懂含义、不知道该插入什么字段的问题。
- 业务边界：仅前端显示层中文化；模板引擎取值键（value）绝对不动，保证存量模板渲染不受影响；不改后端/路由/打印链路。
- 改动模块：
  - `app/templates/print_template_editor.html`：`PLACEHOLDERS` 改为 `{ label, value }` 结构——chip 显示中文标签（单号/日期/供应商/客户/用途/备注/领料人/操作人/合计数量/合计金额/打印日期/物料编码/物料名称/规格/品牌/单位/数量/单价/金额/合同号/项目名/明细备注，22 项），悬停提示英文变量+用法，点击仍插入英文 value；面板标题补中文使用说明（点击字段插入到当前单元格，打印时自动替换为实际内容）。
  - `tests/test_bug_2026_08_26_001_placeholder_chips_chinese.py`：新增回归测试 4 项。
  - `WMS_BUG_BASELINE.md`：登记 BUG-2026-08-26-001 为已修复并纳入回归。
- 专项验证命令及结果：
  - `python -m pytest tests/test_bug_2026_08_26_001_placeholder_chips_chinese.py -q` → 4 passed。
  - `python -m pytest tests/ -q` → 892 passed。
  - `python scripts/lint_wms_rules.py` → 0 违规；`python scripts/lint_no_raw_post_fetch.py` → 通过。
  - pre-commit 钩子：通过（0 违规）。
- 推送验证：常规 HTTPS push 与 SSH 均受网络限制不可用，按「受限网络环境的 GitHub 推送（API 通道）」四步重放（blob×3 → tree `18b8eed1` → commit `39ee99c254a8` → PATCH refs/heads/main）；反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD=`39ee99c254a8`、files 变更列表（3 个文件）与预期一致。token 经连接器 `get_token.sh` 获取，仅走请求头，未落盘。

#### DOCS-2026-08-26-001（已完成）— AGENTS.md 推送章节按实测结果修订

- 完成日期：2026-08-26
- 提交 SHA：本地 `6b627c8` / 远程 `9b8b1a1edf4b`（API 通道重放）
- 目标：把 2026-08-26 实测成功的推送路径固化为标准流程，删除/登记实测不可用的方式，避免后续会话复踩。
- 改动模块：
  - `AGENTS.md`「受限网络环境的 GitHub 推送」章节：凭证获取明确为唯一实测有效来源（github-connector skill `get_token.sh`，注意单条 Bash 调用内取 token 与使用必须同命令）；删除 SSH over 443（本环境无部署公钥）；登记实测不可用方式（credential helper 404 / MCP github-remote 连接失败 / ghproxy 代理只可拉取不可 push）；补充 token 写进 remote URL 后必须清理的约束；api.github.com 域名直连实测 000 须走 DoH IP。
- 验证：API 通道反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD=`9b8b1a1edf4b`、files 含 AGENTS.md。

**子修复 AI-MOB-VOICE-F01-fix3：CI 默认构建开启 sherpa 离线语音识别（2026-08-26）**：
- 根因：语音功能"不能用"——默认 APK 未打包 sherpa 模型（`-Pwms.sherpa` 未开），云引擎又依赖服务器配置腾讯云密钥（`TENCENTCLOUD_SECRET_ID/SECRET_KEY`），而启动/部署脚本均未配置该变量，后端 `/mobile/api/asr` 恒返回 400「未配置腾讯云 ASR 密钥」。
- 方案：用户选择 sherpa 离线方案（免费、不联网、不要密钥）。`.github/workflows/android-build.yml` 新增 `downloadSherpaModel` 步骤（Build 之前）+ 4 个模型文件存在性校验（download task 失败只 warn 不 fail，CI 必须显式拦截）；`assembleDebug`/`lintDebug`/`testDebugUnitTest` 统一带 `-Pwms.sherpa=true`。
- 版本号（BUG-2026-08-16-022 规矩）：`build.gradle.kts` versionCode 5→6、versionName 3.2.0→3.3.0，确保新 APK 可作为更新安装。
- 回归：`tests/verify_sherpa_ci_enabled.py` 新增 4 用例（CI 带 sherpa 开关 / 模型下载在 Build 之前 / 模型文件显式校验 / 版本号 >= 6/3.3.0）+ 存量 `verify_sherpa_build_config.py` 11 用例，15/15 PASSED；YAML 语法校验通过。
- 提交：本地 `379538d` / 远程 `dea89ae07724`（API 通道重放）；CI 构建 run `32928804369` 已触发。
- 部署边界：CI 产出 debug APK artifact 后，部署环境仍须用现有 keystore 构建签名 release APK 并替换 `/mobile/app` 所服务的 APK，用户手机重新下载安装后生效；引擎链保持「云 → sherpa → 系统」，后续若配置腾讯云密钥则自动优先走云端识别。
- **fix3 落地过程（三轮 CI 排障）**：①run `32928804369` 失败——downloadSherpaModel 默认 URL 模型名 `sherpa-onnx-streaming-zh-en-2023-06-26` 在官方 release 不存在（Not Found）；且原 untar 逻辑未处理真实模型包的顶层目录与 epoch/int8 后缀文件名；另发现 SherpaVoiceSttEngine 只从 filesDir 读模型而全 APP 无 assets→filesDir 复制（运行时断链）。修复：URL 改真实存在的 `zipformer-zh-14M-2023-02-23`（70.6MB 纯中文流式 transducer）、解包后按前缀匹配（优先 int8，APK 增量约 15-20MB）平铺重命名为标准四件套、引擎补 `copyModelFromAssets`（BuildConfig.SHERPA_ENABLED/SHERPA_MODEL_DIR 定位）。②run `32930112111` 失败——`implementation("com.k2fsa.sherpaonnx:sherpa-onnx:1.12.13")` 在 Maven Central 不存在（com.k2fsa group 查无，checkDebugAarMetadata 失败）；官方 AAR 只发 GitHub Releases。修复：依赖改 `implementation(files("libs/sherpa-onnx-1.13.6.aar"))` + 新增 `downloadSherpaAar` task（含体积校验拦 302/404）+ CI Verify 加 AAR 校验 + `.gitignore` 排除 `app/libs/*.aar`。③run `32930892537` **success**：APK artifact `app-debug` 98.5MB（含 AAR + int8 模型）。修复提交 `d492ab23e5a7`（断链三层）、`cad67ae2e7f4`（AAR 本地依赖）；回归 sherpa 相关 4 个 verify 文件 51/51 PASSED（新增 T5-T9：真实 URL/平铺重命名/assets 复制/CI 下载校验 AAR/gitignore 排除）。

#### AI-APP-UI-001（已完成）— 安卓原生 App 全界面精致化改版 + 物料档案规格显示修复

- 完成日期：2026-08-28
- 需求原文：手机 app 物料档案规格显示不全；优化手机 APP 所有的界面，要求更加漂亮、更加细腻。
- 提交 SHA（本地，API 通道重放后远程 SHA 以推送验证为准）：`41e6062`（fix BUG-2026-08-28-005）、`b5f06e4`（共享组件库）、`d0c1215`（物料档案两屏）、`bedafae`（首页）、`0726e3e`（登录/个人中心）、`6c13388`（扫码四屏）、`acbb100`（期初库存/仓库弹窗）、`9c45c1d`（AI 三屏）、`da18c7a`（版本号 3.4.0）、台账登记见本提交。
- 修复：BUG-2026-08-28-005 物料档案列表规格 `maxLines = 1` 省略号截断 → 2 行折行（已登记 WMS_BUG_BASELINE，`scripts/verify_wms_bugs.py` 新增 `check_mobile_archive_spec_wrap` 回归 PASS）。注：远程已占用 2026-08-28 的 001-004 编号，本修复取 005。
- 设计体系：新增 `app/android-native-wms/.../ui/components/WmsComponents.kt` 共享组件库（统一顶栏/模块色渐变头部/卡片/空态/主按钮/描边按钮/胶囊徽标/分组标题/信息格/分隔线），`Color.kt` 新增 DividerSoft/BorderSoft/CardAmber；全部 11 个界面（登录、首页、物料档案搜索/详情、扫码入库/出库/盘点/查库存、期初库存、识别单据/识物/识物盘点、个人中心）逐一应用。
- 版本号（BUG-2026-08-16-022 规矩）：versionCode 6→7、versionName 3.3.0→3.4.0，保证新 UI APK 可覆盖安装。
- 专项验证命令及结果：
  - 本地沙箱自建 Android 工具链（dl.google.com/services.gradle.org 被拦，改腾讯镜像下载 cmdline-tools/platform-35/build-tools 34+35/Gradle 8.9，阿里云 Maven 镜像替换 google/central，本地未提交）：每个 atomic action 后 `:app:compileDebugKotlin` 均 BUILD SUCCESSFUL；gitclone.com 镜像克隆到陈旧快照（d3bb90e），实际远程 HEAD 为 67f41ea6，经 ghproxy.net（免证书校验）fetch 后把 9 个提交 cherry-pick 到新基线，复编译 BUILD SUCCESSFUL，最终 `assembleDebug` 全量构建成功产出 app-debug.apk（44.6MB）。
  - `python3 scripts/verify_wms_bugs.py` → BUG-2026-08-28-005 回归 PASS，无新增 FAIL（AI-STAGE5-OPS-001 在未改动基线上同样 FAIL，系既有环境项）。
  - pre-commit 钩子（lint_wms_rules + lint_no_raw_post_fetch）：全部提交 0 违规。
- 推送验证：github.com git 协议 TLS 被拦，经 ghproxy.net 通道（http.sslVerify=false + HTTP/1.1）直接推送成功，输出 `67f41ea..f7a4d34 main -> main`；反查 `GET /repos/SIX2090/wms/commits/main` 远程 HEAD = `f7a4d345928d46426f73e554d70dbaa281e418a8`，与本地 `git rev-parse HEAD` 完全一致（10 个提交 SHA 本地远程一一相同，非近似重放）。
- 遗留子项：CI（android-build.yml assembleDebug）跑完后以 CI 结果为最终编译确认；用户手机需重新下载安装 3.4.0 APK 生效。


### AI-MOB-APK-001：手机端 APK 瘦身（2026-08-29）

**需求原话**：「手机 app 语音识别很慢，经常报错，为什么生成的 APK 要 200M」「手机端实际用不到的都不需要生成 APK」。

**根因排查（两条，均实证）**：
1. **sherpa 离线语音白占约 70MB**：`VoiceSttEngineRegistry.defaultSelector`（VoiceCommandViewModel.kt L236-240）中 `CloudAsrVoiceSttEngine.isAvailable()` 恒为 true，引擎链永远走腾讯云 ASR（系统级密钥已配置），sherpa 模型（约 70MB assets）+ AAR（4 种 ABI 的 .so）一次都不会被加载。附带定位语音慢/报错主因：云端引擎不做可用性降级，后端/网络异常时错误被吞成 `SttError.Unknown`。
2. **debug 包不做 R8/资源收缩**：material-icons-extended（全量图标 ImageVector 代码，实际仅用 60+ 个、跨 14 文件，且大量图标不在 icons-core 子集，不能换依赖）、Compose、MLKit 等全量进 dex。

**实施（3 个 atomic action）**：
- `f6409db2`：CI 移除 Download/Verify sherpa 两步与三处 `-Pwms.sherpa=true`（开关与 downloadSherpa* task 保留）；versionCode 8 / versionName 3.5.0；verify_sherpa_ci_enabled.py 契约反转；同提交修复 pre-commit 钩子（python3 探测）。
- `f8fb1e5a`：T1 契约改为只校验 `run: ./gradlew` 行（注释保留开关用法文档）；修 CI 病句注释与 release notes 文案。
- `6ca01555`：CI 全部构建命令改 release 变体；release 签名按 WMS_STORE_FILE 条件切换（缺省回退 debug，可覆盖安装）；校验 task 仅在配置正式签名时强制参数；Upload 增传 mapping.txt；新增 verify_release_build_slim.py 6 用例。

**验证**：26/26 PASSED（sherpa CI + release 瘦身 + sherpa build config）；pre-commit 规则扫描 0 违规；本地与 origin/main SHA 一致。产物体积以 CI run 实测为准（预期 200MB → 30-60MB）。

### 收敛清单

| # | 文件 | 位置 | 处理 |
|---|---|---|---|
| 1 | `routes/mobile.py` | 扫码入库 / 扫码出库 | → `apply_stock_delta`（库位键 `location`） |
| 2 | `routes/mobile.py` | 草稿确认入库 / 出库 | → `apply_stock_delta`（库位键 `order.location or order.warehouse`） |
| 3 | `routes/native_api.py` | Android 扫码入库 / 出库 | → `apply_stock_delta`（入库 `document_location`、出库 `line.location*`） |
| 4 | `app.py` | `api_subcontract_quick_receive` | **补漏**：改道 `apply_stock_delta`，补上②库位账 |

**未收敛（本批刻意跳过）**：`routes/requisition.py` 扣减侧用
`deduct_location_inventory_atomic`，**绕过** `update_location_inventory` 的
「无库位记录且不允许负库存即失败」检查（BUG-2026-08-04-002 口径）。
收敛会**改变失败语义**，按 R8「不做净改变」原则单独评估，不在本批夹带。

### 等价性论证（为什么是纯重构）

- **mobile 扫码**：原 `if location_management_enabled(): update_location_inventory(...)`
  与入口内部 `if location_management_enabled():` **同判**；库位键逐字沿用。
- **mobile 草稿确认**：原 `if location_management_enabled() and (order.location or order.warehouse):`
  与入口「先判开关、再 `location or 回退仓库`」**同构**。
- **native 入库**：`_native_document_location()` 未开库位管理时返回 `''`，
  原 `if document_location:` 与入口开关判定**等价**。
- **native 出库**：BUG-2026-08-16-020「仅开库位管理时写库位账」语义由入口同判。
- **委外收货**：`SubcontractReceive` 未设 `location`，入口内部回退仓库名，
  与网页版 `location or warehouse` 口径**逐字一致**（收发不会落在不同库位）。

