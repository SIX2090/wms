# 原 86 条历史待修记录复核（2026-11-04）

## 范围与结论

代码基准：`cbc37a382dbe39390802d67a198a4924882234e2`（复核结束时与实时远端 main 一致）。原清单还原自历史基线 `873ae26`，旧解析口径 open=86；本表保留原 86 个 ID，不将统计脚本搜索到的全部 ID 数量当作实际缺陷总数。

| 结论 | 数量 |
|---|---:|
| 代码已修复／能力已实现 | 82 |
| 部分完成 | 1 |
| 用户决定暂缓 | 1 |
| 误报，无需修复 | 1 |
| 按现行开发流程处理 | 1 |
| 合计 | 86 |

“已修复”限代码、接口回归与 CI；本次未逐项验收生产功能、Android 真机安装操作或实体打印。既有生产生效记录保留，不能用本次隔离测试替代现场验收。

## 状态回填与保留项

- `BUG-2026-08-17-001`、`BUG-2026-09-16-018`、`BUG-2026-09-16-019`：将旧“待确认”改为“已修复”，记录代码/CI 已确认及生产现场未逐项验证的边界。
- `BUG-2026-08-16-018`：标“部分完成”。pip-audit 与 gitleaks 已接入且通过；当前工作流明确因性能移除覆盖率统计，不宣称覆盖率仍在运行。
- `BUG-2026-08-16-011`：保持用户已决定的“暂缓/推迟”，不自动提高密码强度要求。
- `BUG-2026-09-22-008`：由“已交付”澄清为“误报”，采购订单是采购入库的可选来源。
- `BUG-2026-07-31-002`：改为“已接受（现行流程）”；直接在 main 提交是明确的开发策略。当前 protected=true 不证明强制 PR/必需 CI 已启用。

## 统计工具的局限

旧报告按所属章节和编号首次出现位置分类，没有读取每行修复内容，导致原 86 行中的已修复、已实现、误报和暂缓条目均可能被归入待修。当前 `scripts/monthly_bug_review.py::build_status_index` 仍沿用章节/首次出现口径；本轮只更正文档，未修统计脚本。脚本计数及其历史快照回归不能作为当前真实积压数量的唯一依据。

若后续修统计脚本，应单独明确表格状态、正文状态、仅引用 ID 与重复登记的优先级，并以逐 ID 解析测试验证；不能为新统计结果直接放宽或删除历史断言。覆盖率恢复属于开发验证能力的可选改进，密码策略已有暂缓决定；本次未确认原清单中另有必须补修的业务故障。

## 验证证据

- 隔离源码副本，测试使用内存或临时 SQLite；原仓库未提交产品改动、生产数据库及服务未参与测试。
- pytest 首轮 738 passed / 90 skipped / 0 failed；相邻接口补核 67 passed / 0 failed，共 805 passed / 90 skipped / 0 failed。两轮测试文件不重叠。90 项跳过均来自既有筛选参数测试：85 项无筛选表单，5 项由 JS 动态收集参数。
- 旧“待确认”三模块分别 20、19、8 项通过；期初草稿另执行 5 个原 JS 函数场景，覆盖空页/已有行渲染不写草稿、未保存退出落草稿、保存后取消待写以及卸载不复活。
- [WMS CI 41842840867](https://github.com/SIX2090/wms/actions/runs/41842840867) 与 [AI 验证 41842840915](https://github.com/SIX2090/wms/actions/runs/41842840915) 均精确匹配代码基准且 completed/success；WMS CI 包含三个全站测试分片、四个 verify 分片、冒烟、静态和安全检查。
- [Android 41740259322](https://github.com/SIX2090/wms/actions/runs/41740259322) 的构建、lint、JVM 单元测试 success；提交 `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba` 为目标祖先，Android 工程与构建工作流无变化，复用证明通过。

生效确认：2026-11-04，Codex 核查以上代码/CI 证据并回填历史状态；不包含生产数据修改、服务重启或真机验收。本文档更新的提交与 CI 结果以实际交付记录为准。

## 本次文档更正验证

2026-11-04：仅修改两个历史台账分片、旧质量报告说明及本复核记录，不修改统计脚本或业务功能。台账拆分、查询与 staged 读取、README/库存文档定位相邻回归 54 passed；严格 AI 台账与编码检查通过。额外核对原 86 个 ID 唯一且完整、相对链接存在，月度统计脚本的逐 ID 历史快照在文档更正前后完全相同。旧测试断言未修改；本次新增的是人工复核结论，不以保留旧脚本输出掩盖其分类局限。

## 86 项逐条清单

按原编号计数；一条历史记录可能含多个子问题，本表不将测试实例数当作缺陷数。

| 序 | 原编号 | 内容摘要 | 本次结论 | 对照测试／依据 |
|---:|---|---|---|---|
| 1 | BUG-2026-07-31-002 | `main` 分支未设置 protected branch，开发者可直接 push 绕过 PR + review | 按现行规则处理 | 现行 AGENTS + 远端 protected=true |
| 2 | BUG-2026-08-16-003 | [P0] 新增物料带初始库存走 ORM 直改 `Material(stock=initial_stock)`，不写库位账不写 OpeningStock，且物料与流水两次独立 commit 非原子（… | 已修复 / 已实现 | [test_bug_2026_08_16_003_material_initial_stock_location.py](../../tests/test_bug_2026_08_16_003_material_initial_stock_location.py) 4 passed |
| 3 | BUG-2026-08-16-005 | [P1] `batch_complete_in_order` 批量完成跳过 `validate_purchase_in_order_source`（入库须关联 PO 开关）、`_check_in_… | 已修复 / 已实现 | [test_bug_2026_08_16_005_batch_complete_in_guards.py](../../tests/test_bug_2026_08_16_005_batch_complete_in_guards.py) 4 passed |
| 4 | BUG-2026-08-16-006 | [P1] `add_stock`/`deduct_stock_atomic` 写 StockTransaction 不填 location（仅 transfer 写），而 `get_warehou… | 已修复 / 已实现 | [test_bug_2026_08_16_006_stock_transaction_warehouse_location.py](../../tests/test_bug_2026_08_16_006_stock_transaction_warehouse_location.py) 5 passed |
| 5 | BUG-2026-08-16-007 | [P1] `stock_query` 页面把 `material.stock` 全局总数当仓库级库存展示，LocationInventory 行不按所选仓库过滤；同文件 `api_query_se… | 已修复 / 已实现 | [test_bug_2026_08_16_007_stock_query_warehouse_filter.py](../../tests/test_bug_2026_08_16_007_stock_query_warehouse_filter.py) 2 passed |
| 6 | BUG-2026-08-16-009 | [P1] `revert_in_order`/`update_completed_in_order` 库存充足校验用 `check_stock_sufficient`→`material.stoc… | 已修复 / 已实现 | [test_bug_2026_08_16_009_revert_in_order_warehouse_level.py](../../tests/test_bug_2026_08_16_009_revert_in_order_warehouse_level.py) 3 passed |
| 7 | BUG-2026-08-16-011 | [P1] `validate_password_strength` 仅校验长度≥6，无复杂度/弱口令黑名单/与用户名相同检查（`123456`、`admin123` 均合法）；新增用户、改密、管理… | 用户决定暂缓 | validate_password_strength 现有实现 + 用户暂缓记录 |
| 8 | BUG-2026-08-16-012 | [P1] `OperationAudit` 结构化审计表实质未启用：唯一写入函数 `log_audit` 全库 0 调用，所有操作仅 OperationLog 纯文本，删物料/改单价/反提交/改角… | 已修复 / 已实现 | [test_bug_2026_08_16_012_document_audit.py](../../tests/test_bug_2026_08_16_012_document_audit.py) 5 passed；[test_bug_2026_08_16_012_material_audit.py](../../tests/test_bug_2026_08_16_012_material_audit.py) 4 passed；[test_bug_2026_08_16_012_user_audit.py](../../tests/test_bug_2026_08_16_012_user_audit.py) 4 passed |
| 9 | BUG-2026-08-16-013 | [P1] AI 路由 30+ 端点（`app/ai/routes.py`、`app/ai/v2_routes.py`）仅 `@login_required` 无角色门禁，viewer/user 只… | 已修复 / 已实现 | [test_bug_2026_08_16_013_ai_role_gate.py](../../tests/test_bug_2026_08_16_013_ai_role_gate.py) 43 passed |
| 10 | BUG-2026-08-16-014 | [P1] 售后出库新增无库位校验（无 location_management_enabled 校验、无 assert_warehouse_active），模板 `after_sale_out_ad… | 已修复 / 已实现 | [test_bug_2026_08_16_014_after_sale_out_add_location.py](../../tests/test_bug_2026_08_16_014_after_sale_out_add_location.py) 3 passed |
| 11 | BUG-2026-08-16-015 | [P1] 调拨新建弹窗 `transfer.html` 只有 from_location/to_location 两个 select 且选项是仓库名，无独立库位字段；后端把 from_locati… | 已修复 / 已实现 | [test_bug_2026_08_16_015_transfer_double_field.py](../../tests/test_bug_2026_08_16_015_transfer_double_field.py) 4 passed |
| 12 | BUG-2026-08-16-017 | [P1] `tests/` 下 100 个 verify_*.py（约 17,012 行，含 60+ BUG 回归与 38 个 app.py 拆分校验）不被 pytest 默认收集也不在任何 CI… | 已修复 / 已实现 | WMS CI 四个 verify 分片均成功 |
| 13 | BUG-2026-08-16-018 | [P1] CI 无代码覆盖率（无 pytest-cov）无安全扫描（pip-audit/bandit/gitleaks 全无），依赖漏洞与密钥泄露无门禁，覆盖盲区不可量化 | 部分完成 | ci.yml 安全扫描与移除覆盖率的明确记录 |
| 14 | BUG-2026-08-16-019 | [P2] 安全加固批量：SystemSetting 明文存 LLM/ASR API Key、`/api/login`（`native_api.py:251`）与 `report.py:203` 把… | 已修复 / 已实现 | [test_bug_2026_08_16_019_secret_encryption.py](../../tests/test_bug_2026_08_16_019_secret_encryption.py) 5 passed；[test_audit_b8_error_sanitization.py](../../tests/test_audit_b8_error_sanitization.py) 1 passed；[test_secret_encryption_fail_closed.py](../../tests/test_secret_encryption_fail_closed.py) 7 passed |
| 15 | BUG-2026-08-16-020 | [P2] 并发与一致性批量：`delete_purchase_order`/`batch_delete` 无写锁（引用孤儿竞态，`purchase_order.py:895-961`）、`reve… | 已修复 / 已实现 | [test_bug_2026_08_16_020_concurrency_consistency.py](../../tests/test_bug_2026_08_16_020_concurrency_consistency.py) 4 passed；[test_pur_audit_002_delete_protection.py](../../tests/test_pur_audit_002_delete_protection.py) 9 passed；[test_p1_subcontract_receive_delete_write_lock.py](../../tests/test_p1_subcontract_receive_delete_write_lock.py) 5 passed；[test_web_document_idempotency.py](../../tests/test_web_document_idempotency.py) 42 passed |
| 16 | BUG-2026-08-16-022 | [P1] Android 原生端手工添加物料与扫码共用提交后打印能力，但 APK `versionCode`/`versionName` 未随该能力发布递增；运营下载页只提供已部署 signed … | 已修复 / 已实现 | [test_print_auto_after_scan.py](../../tests/test_print_auto_after_scan.py) 9 passed；[test_print_queue.py](../../tests/test_print_queue.py) 34 passed |
| 17 | BUG-2026-08-16-023 | [P1] `.testvenv/` 本地 Python 虚拟环境的 7,815 个文件被误提交，GitHub `actions/setup-python` 的 pip 缓存扫描 `.testven… | 已修复 / 已实现 | .gitignore、远端 Git 树及当前 CI |
| 18 | BUG-2026-08-17-001 | 部署兜底脚本 `fix_db_columns.py` 缺少 `in_order`/`out_order` 的 `location` 与 `in_order.auto_push_requisitio… | 已修复 / 已实现 | [test_fix_db_columns.py](../../tests/test_fix_db_columns.py) 20 passed |
| 19 | BUG-2026-08-17-002 | ①关库位管理+多仓库时，所有仓库级报表（库存报表、库存台账、仓库月报）使用 `Material.stock` 全局数而非按仓库聚合，导致"有库存查不出来"；`add_stock`/`deduct_… | 已修复 / 已实现 | [test_bug_2026_08_16_006_stock_transaction_warehouse_location.py](../../tests/test_bug_2026_08_16_006_stock_transaction_warehouse_location.py) 5 passed；[test_bug_2026_08_17_000_warehouse_report_fallback.py](../../tests/test_bug_2026_08_17_000_warehouse_report_fallback.py) 2 passed；[test_bug_2026_08_17_002_revert_in_order_without_warehouse.py](../../tests/test_bug_2026_08_17_002_revert_in_order_without_warehouse.py) 3 passed |
| 20 | BUG-2026-08-17-003 | 采购订单执行、供应商采购汇总、物料采购汇总、采购价格分析和委外加工报表虽然要求选择仓库，但采购查询未按入库仓库归属过滤，委外查询未按 `SubcontractOrder.warehouse` 过滤… | 已修复 / 已实现 | [test_bug_2026_08_17_003_purchase_subcontract_warehouse_reports.py](../../tests/test_bug_2026_08_17_003_purchase_subcontract_warehouse_reports.py) 2 passed |
| 21 | BUG-2026-08-17-004 | 数据仪表盘未提供仓库筛选，入库、出库、库存、库存金额、趋势、月度金额和库存排行全部使用全局数据，多仓库环境下报表口径串仓 | 已修复 / 已实现 | [test_bug_2026_08_17_004_report_dashboard_warehouse_filter.py](../../tests/test_bug_2026_08_17_004_report_dashboard_warehouse_filter.py) 2 passed |
| 22 | BUG-2026-08-23-001 | 手机 APP 扫码入库卡片只显示物料编码+数量，缺名称/品牌/规格。根因：卡片物料详情展示与 `addScanLine` 接口补全能力在 commit `17df8a1c`（2026-08-20）… | 已修复 / 已实现 | [test_bug_2026_08_23_001_mobile_scan_card_material_details.py](../../tests/test_bug_2026_08_23_001_mobile_scan_card_material_details.py) 5 passed |
| 23 | BUG-2026-08-23-002 | 采购入库单「下推领料单」链路卡顿。实测「提交+自动下推领料单」（100 明细）一次请求发 835 条 SQL、耗时 350~407ms，其中 **202 条（24%）是对 `system_sett… | 已修复 / 已实现 | [test_bug_2026_08_23_002_push_chain_settings_cache.py](../../tests/test_bug_2026_08_23_002_push_chain_settings_cache.py) 3 passed |
| 24 | BUG-2026-08-23-003 | 内置打印代理在数据库 schema 未就绪（缺表/缺列：库文件丢失、路径错配或被外部重建）时，`_agent_loop` 兜底每 3 秒 `log.exception` 刷完整 traceback… | 已修复 / 已实现 | [test_local_print_agent.py](../../tests/test_local_print_agent.py) 18 passed |
| 25 | BUG-2026-08-23-004 | 端口 8080 被旧 WMS 实例占用时（现场最高频启动失败原因，Windows 报 WinError 10048），`run_server.py` 直接抛英文 `OSError: [Errno … | 已修复 / 已实现 | [test_run_server_port_hint.py](../../tests/test_run_server_port_hint.py) 3 passed |
| 26 | BUG-2026-08-28-001 | 手机端「待确认」页（mobile_scan.html mode=confirm）调用 `/api/mobile/in_order/list`、`/api/mobile/out_order/list… | 已修复 / 已实现 | [test_bug_2026_08_28_001_mobile_confirm_pagination.py](../../tests/test_bug_2026_08_28_001_mobile_confirm_pagination.py) 4 passed |
| 27 | BUG-2026-08-28-002 | 手机 APP「每日报表」（采购入库/领料单）明细列表只能看到 20 条，但汇总统计显示更多明细（如 58 明细）——汇总基于全集，明细列表被分页截断。根因：Android `WmsReposito… | 已修复 / 已实现 | [verify_bug_2026_08_28_002_daily_report_all_pages.py](../../tests/verify_bug_2026_08_28_002_daily_report_all_pages.py) 6 passed |
| 28 | BUG-2026-09-02-001 | Android 原生端 `/api/stocktake` 扫码盘点取全局账面库存：INV-AUDIT-003 已把手机端（`mobile.py` `scan_submit`）盘点账面改成仓库级 `… | 已修复 / 已实现 | [test_inv_audit_003_fix01_native_stocktake_warehouse_scope.py](../../tests/test_inv_audit_003_fix01_native_stocktake_warehouse_scope.py) 3 passed |
| 29 | BUG-2026-09-02-003 | 扫码盘点单创建即 `status='completed'` 且全系统无任何作废/删除/回退端点（UI 无入口、API 无路由）：扫错物料/数量/仓库后无法纠正——要么放任错误调整草稿被审核提交（库… | 已修复 / 已实现 | [test_inv_revert_001_check_scan_void.py](../../tests/test_inv_revert_001_check_scan_void.py) 8 passed |
| 30 | BUG-2026-09-03-001 | Excel 导入盘点单不处理仓库（R6 排查 BUG-2026-09-02-001 同族遗漏点）：`/check/import`（`app/routes/check.py`）导入模板无"仓库"列，… | 已修复 / 已实现 | [verify_bug_2026_09_03_001_check_import_warehouse.py](../../tests/verify_bug_2026_09_03_001_check_import_warehouse.py) 6 passed |
| 31 | BUG-2026-09-03-002 | 手机端物料接口"系统库存"展示固定取全局 Material.stock（R6 排查 BUG-2026-09-02-001 同族展示侧遗漏）：mobile_material_payload 的 st… | 已修复 / 已实现 | [verify_bug_2026_09_03_002_mobile_display_warehouse_stock.py](../../tests/verify_bug_2026_09_03_002_mobile_display_warehouse_stock.py) 7 passed |
| 32 | BUG-2026-09-15-001 | 数据仪表盘「AI解读」按钮死按钮（R6 同 BUG-F02-09"调未定义函数"模式）：`report_dashboard.html` 的按钮（onclick=requestAiInsights(… | 已修复 / 已实现 | [verify_bug_2026_09_15_001_dashboard_ai_insights_button.py](../../tests/verify_bug_2026_09_15_001_dashboard_ai_insights_button.py) 3 passed |
| 33 | BUG-2026-09-15-002 | 采购入库单/销售出库单新增页「智能分享」按钮提示误导（文案由 BUG-2026-08-05-006 引入，R6 同根因排查）：`in_order_add.html`/`out_order_add.… | 已修复 / 已实现 | [verify_bug_2026_09_15_002_smart_share_hint.py](../../tests/verify_bug_2026_09_15_002_smart_share_hint.py) 5 passed |
| 34 | BUG-2026-09-15-003 | 期初库存页「导入导出模板」「粘贴导入」「批量导入」三个功能全是半成品，用户反馈"根本没法用"（R6 同根因 BUG-2026-08-05-006 的漏网消费点）：①「导入导出模板」按钮只调 `sh… | 已修复 / 已实现 | [test_opening_stock_import.py](../../tests/test_opening_stock_import.py) 11 passed |
| 35 | BUG-2026-09-15-004 | 新增期初库存单「日期」改不了（用户反馈"新增期初库存单为什么改不了日期？"）。根因是前端日期链路完全断裂、后端无从接收：①表头 `<input type="date" value="{{ doc_… | 已修复 / 已实现 | [test_opening_stock_import.py](../../tests/test_opening_stock_import.py) 11 passed |
| 36 | BUG-2026-09-15-006 | 期初库存单头部三个字段是"摆设"（用户反馈"这个地方的功能有个屁用"）：opening_stock.html 新增期初库存单头部——①备注（headerRemark）有输入框但 saveDocum… | 已修复 / 已实现 | [test_bug_2026_09_15_006_opening_stock_header_fields.py](../../tests/test_bug_2026_09_15_006_opening_stock_header_fields.py) 5 passed |
| 37 | BUG-2026-09-16-013 | 期初建账"摸黑录入"：全系统无任何"哪些物料还没建账"的视图（P1-A 新增能力）。期初库存只有「单据列表」和「按单编辑」两个视角，都以**已录入的数据**为中心——仓管员录到一半，无法回答"仓库… | 已修复 / 已实现 | [test_opening_stock_progress.py](../../tests/test_opening_stock_progress.py) 26 passed |
| 38 | BUG-2026-09-16-014 | 内联事件处理器用双引号包 `tojson` 导致按钮静默失效（R6 同族预防性排查，本次实装中踩到并当场修复）：`tojson` 过滤器产出**双引号** JSON（`"M-0001"`），若写成… | 已修复 / 已实现 | [test_opening_stock_progress.py](../../tests/test_opening_stock_progress.py) 26 passed |
| 39 | BUG-2026-09-16-015 | `parse_float_value(value, None)` 必然抛 TypeError，把「数量填了非数字」这类普通用户输入错误升格成 500 服务器内部错误（P1-B 预检实装中发现，属存… | 已修复 / 已实现 | [test_opening_stock_import_dry_run.py](../../tests/test_opening_stock_import_dry_run.py) 16 passed；[test_p0_nan_quantity_guard.py](../../tests/test_p0_nan_quantity_guard.py) 12 passed |
| 40 | BUG-2026-09-16-016 | 期初导入「文件内重复」误判：校验失败的行也占用去重键，导致同一 (物料, 仓库) 的后一条**合法**行被当成重复丢弃（P1-B 预检实装中发现，属存量缺陷）。根因：`app/routes/bat… | 已修复 / 已实现 | [test_opening_stock_import_dry_run.py](../../tests/test_opening_stock_import_dry_run.py) 16 passed |
| 41 | BUG-2026-09-16-017 | 手机端期初「建完就瞎」：只能建账，看不到建了什么、建错了也改不了（P1-C 新增能力）。① `GET /api/opening_stock` 写死 `.limit(200)`——**把分页上限当成… | 已修复 / 已实现 | [test_opening_stock_mobile_list_edit.py](../../tests/test_opening_stock_mobile_list_edit.py) 26 passed |
| 42 | BUG-2026-09-16-018 | 期初录入草稿「幽灵写入 / 保存后复活」（P1-D 实现过程中浏览器实测复现，属本次新增功能的自身缺陷）：把 `scheduleDraftSave()` 放在 `renderRows()` 末尾，… | 已修复 / 已实现 | [test_opening_stock_entry_draft.py](../../tests/test_opening_stock_entry_draft.py) 19 passed |
| 43 | BUG-2026-09-16-019 | 门禁脚本「断言钉死文件位置」，致 WMS CI 长期红灯失去信号价值（排查 CI 时发现的**门禁自身**缺陷，非业务代码缺陷）：ARCH-MODELS-01（2026-09-15）把 19 张 … | 已修复 / 已实现 | [test_verify_wms_bugs_gate.py](../../tests/test_verify_wms_bugs_gate.py) 8 passed |
| 44 | BUG-2026-09-17-001 | [P2] 合同/工程档案修改工程名称后，历史单据上的工程名称不同步（用户原话：「更改工程名称之前单据上的工程名称没有同步更改」，实测：HD260904 档案名已改为「淮安第三园区纯废水七期、八期安… | 已修复 / 已实现 | [test_contract_rename_sync.py](../../tests/test_contract_rename_sync.py) 5 passed |
| 45 | BUG-2026-09-18-001 | [P2] 物料档案列表（/material）行高亮仍是**单级**（只比 `min_stock`），低于安全库存（danger 档）但高于最低库存的物料在列表里**完全不被标注**——两级化（AI… | 已修复 / 已实现 | [test_bug_2026_09_18_001_material_list_two_band_highlight.py](../../tests/test_bug_2026_09_18_001_material_list_two_band_highlight.py) 4 passed |
| 46 | BUG-2026-09-18-002 | [P2] 「安全库存(reorder_point) 不得小于最低库存(min_stock)」这条不变量只在**批量设置**（显式冲突拒绝）与**Excel 导入**（clamp 提到 min）两处… | 已修复 / 已实现 | [test_bug_2026_09_18_002_material_threshold_validation.py](../../tests/test_bug_2026_09_18_002_material_threshold_validation.py) 5 passed |
| 47 | BUG-2026-09-18-003 | [P2] 手机端「两级判定」（low=破最低库存红线、danger=破安全库存预警线）在 F04 统一到了预警列表/首页/库存查询，但**扫码结果卡「库存充足/不足」徽标**与**查库存列表行数量… | 已修复 / 已实现 | [test_bug_2026_09_18_003_android_scan_badge_two_band.py](../../tests/test_bug_2026_09_18_003_android_scan_badge_two_band.py) 6 passed |
| 48 | BUG-2026-09-18-004 | [P2] 电脑端与手机端「安全库存预警」**口径分裂**：电脑端 /alert 页与首页一律按**全局** `Material.stock` 判定，手机端（/api/mobile/alert/li… | 已修复 / 已实现 | [test_bug_2026_09_18_004_alert_warehouse_scope.py](../../tests/test_bug_2026_09_18_004_alert_warehouse_scope.py) 4 passed |
| 49 | BUG-2026-09-18-005 | [P2] 两端口径分裂的**首页残留**：手机端首页 dashboard 早已能切仓库（BUG-2026-09-10-010），电脑端 /alert 页也在 BUG-2026-09-18-004 … | 已修复 / 已实现 | [test_bug_2026_09_18_005_home_alert_warehouse_scope.py](../../tests/test_bug_2026_09_18_005_home_alert_warehouse_scope.py) 4 passed |
| 50 | BUG-2026-09-22-014 | [P1] **采购类报表按仓库查询恒为空**：Web 端打开「采购订单执行统计表」，仓库选「WH-TEST - 测试主仓」点查询，页面显示「当前条件下没有数据 / 共 0 条」，而库里明明有 10… | 已修复 / 已实现 | [test_bug_2026_08_17_003_purchase_subcontract_warehouse_reports.py](../../tests/test_bug_2026_08_17_003_purchase_subcontract_warehouse_reports.py) 2 passed；[test_bug_2026_09_22_014_followup_write_side_and_r6.py](../../tests/test_bug_2026_09_22_014_followup_write_side_and_r6.py) 6 passed；[test_bug_2026_09_22_014_purchase_report_warehouse_code.py](../../tests/test_bug_2026_09_22_014_purchase_report_warehouse_code.py) 4 passed |
| 51 | BUG-2026-09-18-006 | [P1] 手机端**出库/入库页「提交」按钮被顶出屏幕且滚不回来**，单据提交不了（现场：出库→手工添加，看不到提交按钮） | 已修复 / 已实现 | [test_bug_2026_09_18_006_scan_submit_button_offscreen.py](../../tests/test_bug_2026_09_18_006_scan_submit_button_offscreen.py) 6 passed |
| 52 | BUG-2026-09-18-007 | [P2] 手机端扫码页标题**写死「扫码」**，与「手动添加」入口矛盾（现场：从出库→手工添加进去，标题却是「扫码出库」，底部 Tab 又是「出库」，三套口径并存，怀疑进错页面） | 已修复 / 已实现 | [test_bug_2026_09_18_007_scan_title_copy.py](../../tests/test_bug_2026_09_18_007_scan_title_copy.py) 6 passed |
| 53 | BUG-2026-09-18-008 | [P0] 手机端**入库单头字段整条链路缺失**：`/api/inbound` **一个单据头业务字段都没读**，`supplier_id` / `contract_id` / `contract… | 已修复 / 已实现 | [test_bug_2026_09_18_008_mobile_inbound_header_fields.py](../../tests/test_bug_2026_09_18_008_mobile_inbound_header_fields.py) 11 passed |
| 54 | BUG-2026-09-18-009 | [P1] 手机端扫码页基类**用「按钮文案」驱动功能开关**：`ScanScreenBase` 里 `if (submitLabel == "提交入库" \|\| submitLabel ==… | 已修复 / 已实现 | [test_bug_2026_09_18_009_scan_base_explicit_flags.py](../../tests/test_bug_2026_09_18_009_scan_base_explicit_flags.py) 8 passed |
| 55 | BUG-2026-09-18-010 | [P1] 手机端**入库确认弹窗信息缺失且无前置校验**：四个扫码页的"提交前确认"里入库页是**信息最少的一个**——出库页显示领料部门/领料人，盘点页显示盘点仓库+盘点单且未选时明确警告「尚未… | 已修复 / 已实现 | [test_bug_2026_09_18_010_inbound_submit_dialog.py](../../tests/test_bug_2026_09_18_010_inbound_submit_dialog.py) 7 passed |
| 56 | BUG-2026-09-18-011 | [P3] 手机端出库提交按钮文案**「提交出库」与「确认出库」两套说法并存**：同一屏里底部按钮是「提交出库」，而点开后的确认弹窗标题、主按钮都是「确认出库」，弹窗正文又是「…确认提交出库？」——… | 已修复 / 已实现 | [test_bug_2026_09_18_011_outbound_confirm_outbound_label.py](../../tests/test_bug_2026_09_18_011_outbound_confirm_outbound_label.py) 7 passed |
| 57 | BUG-2026-09-18-012 | [P1] 出库/入库明细表按「合同编号/工程名称」筛选**粒度错配**：筛选条件填「合同编号 = HD260909」，列表里却出现合同编号 `HD260708` 的行，用户反馈「为什么不能按合同编… | 已修复 / 已实现 | [test_bug_2026_09_18_012_out_detail_contract_filter_granularity.py](../../tests/test_bug_2026_09_18_012_out_detail_contract_filter_granularity.py) 8 passed |
| 58 | BUG-2026-09-18-013 | [P1] 单据明细**「同物料跨合同」被合并成一行**：物料编号/名称/规格相同、但**合同编号不同**的明细行被自动合并，导致合同归属与金额溯源全部错误。同一物料按不同合同分批入库是常见业务（用… | 已修复 / 已实现 | [test_bug_2026_09_18_013_no_material_merge_across_contract.py](../../tests/test_bug_2026_09_18_013_no_material_merge_across_contract.py) 21 passed |
| 59 | BUG-2026-09-20-014 | [P1] **采购退货出库（P1-7）能力完全不存在**：整改方案 §P1-7 实测「类不存在，但开关已存在」——系统设置里早有 `purchase_return_requires_order`（… | 已修复 / 已实现 | [test_r6_startup_migration_column_guard.py](../../tests/test_r6_startup_migration_column_guard.py) 3 passed；[verify_purchase_return_outbound.py](../../tests/verify_purchase_return_outbound.py) 18 passed |
| 60 | BUG-2026-09-21-002 | [P2] **BUG-2026-08-25-002 同根因复发**（R6：记录级链接必须新开标签页）：P1-7 采购退货出库（2c272b08，2026-09-20）在 `out_order_de… | 已修复 / 已实现 | [test_bug_2026_08_25_002_doc_links_new_tab.py](../../tests/test_bug_2026_08_25_002_doc_links_new_tab.py) 3 passed |
| 61 | BUG-2026-09-21-001 | [P1] 采购入库单新增页明细表**表头/表体/表尾三种列序互不一致**：d0c53730（2026-09-19，入库明细新增批次号/有效期捕获，P0 可追溯性）在 `in_order_add.h… | 已修复 / 已实现 | [test_in_order_add_detail_column_alignment.py](../../tests/test_in_order_add_detail_column_alignment.py) 2 passed |
| 62 | BUG-2026-09-21-003 | [P1] **编辑入库草稿会静默清空行级批次号/有效期**（d0c53730 批次/有效期功能漏改回填路径，R6）：①`routes/in_order.py` 的 `edit_items`（编辑草… | 已修复 / 已实现 | [test_bug_2026_09_21_003_in_order_edit_batch_expiry.py](../../tests/test_bug_2026_09_21_003_in_order_edit_batch_expiry.py) 4 passed |
| 63 | BUG-2026-09-21-004 | [P3] **四个单据页表尾合计行/空态行与表头列数不齐**（「表头加列、表尾忘改」同类，R6）：①sales_order_add / sales_order_edit——08 月行级合同/工程列… | 已修复 / 已实现 | [test_doc_footer_column_alignment.py](../../tests/test_doc_footer_column_alignment.py) 5 passed |
| 64 | BUG-2026-09-21-005 | [P0] **删库重建静默清空离线待同步队列，且恢复分支实为死代码**（手机端 APP 审查发现）：`AppDatabase.getDatabase` 的兜底策略是"建库失败→`deleteDat… | 已修复 / 已实现 | [test_bug_2026_09_21_005_offline_queue_backup.py](../../tests/test_bug_2026_09_21_005_offline_queue_backup.py) 7 passed |
| 65 | BUG-2026-09-22-001 | [P1] Android `PendingQueueRebuildProtectionTest` 在 CI 上**顺序依赖偶发失败**（check_ci_green 门禁 #695 拦下；属 R6… | 已修复 / 已实现 | PendingQueueRebuildProtectionTest 清理实现 + Android JVM CI |
| 66 | BUG-2026-09-22-002 | [P3] 采购入库「数量」字段两处体验硬伤（用户走查）：①输入框 `type="number"` 自带浏览器上下箭头（spinner），点击/滚轮极易误增减；②数量为整数时被 `toFixed(2… | 已修复 / 已实现 | [test_bug_2026_09_22_002_in_order_qty_format.py](../../tests/test_bug_2026_09_22_002_in_order_qty_format.py) 6 passed |
| 67 | BUG-2026-09-22-003 | [P1] 采购申请单物料编码输入框死引用 `selectBtn` 致一连串功能失效（用户走查）：`purchase_request_add.html` 的 `bindMaterialInput` … | 已修复 / 已实现 | [test_bug_2026_09_22_003_pr_material_selectbtn.py](../../tests/test_bug_2026_09_22_003_pr_material_selectbtn.py) 5 passed |
| 68 | BUG-2026-09-22-004 | [P1] 采购申请单明细物料编码框无法像采购入库单那样关键词快速匹配（用户走查）：`purchase_request_add.html` 与 `in_order_add.html` 物料联想口径不… | 已修复 / 已实现 | [test_bug_2026_09_22_004_pr_material_keyword_search.py](../../tests/test_bug_2026_09_22_004_pr_material_keyword_search.py) 9 passed |
| 69 | BUG-2026-09-22-005 | [P1] **批量完成采购退货出库单漏挂防超退闸**（采购模块审查发现，批量/单据门禁不对称）：单据版 `complete_out_order` 在 P1-7 已挂 `purchase_retur… | 已修复 / 已实现 | [test_bug_2026_09_22_005_batch_complete_purchase_return_gate.py](../../tests/test_bug_2026_09_22_005_batch_complete_purchase_return_gate.py) 2 passed |
| 70 | BUG-2026-09-22-006 | [P1] **批量完成销售退货入库单漏挂防超退闸**（BUG-2026-09-22-005 的同根因兄弟点，批量/单据门禁不对称）：单据版 `complete_in_order` 在 P1-5 已… | 已修复 / 已实现 | [test_bug_2026_09_22_006_batch_complete_sales_return_gate.py](../../tests/test_bug_2026_09_22_006_batch_complete_sales_return_gate.py) 2 passed |
| 71 | BUG-2026-09-22-008 | **[误报·非 BUG；代码未改动]** 审查曾疑「已完成采购入库单编辑保存（`update_completed_in_order` 的 is_new 分支）漏配『采购入库必须关联采购订单』门禁，… | 误报，无需修复 | purchase_in_order_requires_order() == False |
| 72 | BUG-2026-09-22-009 | [P1] **编辑保存已被入库单引用的采购订单会拆掉下游来源链**（保存路径缺引用保护，与删除路径不对称）：`save_purchase_order` 编辑分支的守卫只有 `order.statu… | 已修复 / 已实现 | [test_bug_2026_09_22_009_po_save_inbound_reference.py](../../tests/test_bug_2026_09_22_009_po_save_inbound_reference.py) 3 passed |
| 73 | BUG-2026-09-22-010 | [P1] **手填单号可击穿采购退货来源的类型与状态防线**（保存路径的来源解析与选源接口口径不一致）：选源接口 `/api/purchase_in_order/selectable` 明确只返回… | 已修复 / 已实现 | [test_bug_2026_09_22_010_purchase_return_source_type_status.py](../../tests/test_bug_2026_09_22_010_purchase_return_source_type_status.py) 5 passed |
| 74 | BUG-2026-09-22-011 | [P2] **采购单下推入库两条入口对「重复明细」口径不一致，按单下推静默少入库并击穿超量校验**：同一采购明细 id 在请求体内出现多次时，`purchase_order.py` 两条入口处理相… | 已修复 / 已实现 | [test_bug_2026_09_22_011_push_duplicate_item_aggregation.py](../../tests/test_bug_2026_09_22_011_push_duplicate_item_aggregation.py) 9 passed |
| 75 | BUG-2026-09-22-012 | [P1] **采购申请保存路径物料解析失败静默降级为 `material_id=None`，造出「有明细无物料」的僵尸申请单**：`add_purchase_request`（新增/编辑共用入口）… | 已修复 / 已实现 | [test_bug_2026_09_22_012_purchase_request_material_resolve.py](../../tests/test_bug_2026_09_22_012_purchase_request_material_resolve.py) 9 passed |
| 76 | BUG-2026-09-22-013 | [P1] **出库明细报表无业务类型隔离，采购退货出库混进「领料」口径且无法筛除**：`_filtered_out_detail_query`（领料明细报表 / 出入库汇总报表 / Excel 导… | 已修复 / 已实现 | [test_bug_2026_09_22_013_out_detail_business_type_isolation.py](../../tests/test_bug_2026_09_22_013_out_detail_business_type_isolation.py) 13 passed；[verify_bug_2026_08_02_018_report.py](../../tests/verify_bug_2026_08_02_018_report.py) 8 passed |
| 77 | BUG-2026-09-22-016 | [P1] **手工建的采购单不计入采购申请下推进度，同一申请可被反复下推（超采一倍）**（R6 同模式：关联字段只在一条入口写入）：`build_purchase_request_executio… | 已修复 / 已实现 | [test_bug_2026_09_22_016_manual_po_counts_toward_request.py](../../tests/test_bug_2026_09_22_016_manual_po_counts_toward_request.py) 9 passed |
| 78 | BUG-2026-09-23-002 | [P1] **报表状态列翻译残缺，采购单 `partial`/`closed` 原样显示英文、中英混杂**（R6 同型：翻译逻辑多消费点各自内联、覆盖不全）：`report_view.html` … | 已修复 / 已实现 | [test_bug_2026_09_23_002_report_status_label_coverage.py](../../tests/test_bug_2026_09_23_002_report_status_label_coverage.py) 4 passed |
| 79 | BUG-2026-09-23-003 | [P1] **明细表翻页跳进「其他 XX 明细表」：同一视图挂多条 URL 规则，`url_for` 只解析到后注册那条**（R6 同根因两处消费点 + 一处非分页消费点，一并收口）。现场（用户走… | 已修复 / 已实现 | [test_bug_2026_08_29_003_supplier_text_filter.py](../../tests/test_bug_2026_08_29_003_supplier_text_filter.py) 6 passed；[test_bug_2026_09_23_003_list_pagination_path.py](../../tests/test_bug_2026_09_23_003_list_pagination_path.py) 15 passed；[test_filter_params_follow.py](../../tests/test_filter_params_follow.py) 52 passed |
| 80 | BUG-2026-09-23-004 | [P1] **采购入库明细表浏览器全量走查：5 个独立问题（含 3 处 R6 同根因兄弟点）**。现场（用户走查，要求「用浏览器登录 wms 系统，在采购入库明细页面所有的地方操作一遍找出所有的问… | 已修复 / 已实现 | [test_bug_2026_09_23_004_in_order_page_audit.py](../../tests/test_bug_2026_09_23_004_in_order_page_audit.py) 25 passed |
| 81 | BUG-2026-09-23-005 | [P1] **全局操作栏（`#cbGlobalActionBar`）在列表页的 4 项缺陷**（用户走查：截图标红工具条，问「红色框内的按钮哪些需要优化」）。澄清审计对象：红框里的**不是**各页… | 已修复 / 已实现 | [test_bug_2026_09_23_005_actionbar_list_page.py](../../tests/test_bug_2026_09_23_005_actionbar_list_page.py) 12 passed |
| 82 | BUG-2026-09-23-006 | [P1] **全局操作栏与「页面自带工具栏」按钮重复（BUG-2026-09-23-005 明确推迟的「工具栏去重」独立轮）+ 1 项越界渲染**。审计对象仍是 `app.js` `insertG… | 已修复 / 已实现 | [test_bug_2026_09_23_006_toolbar_dedupe.py](../../tests/test_bug_2026_09_23_006_toolbar_dedupe.py) 9 passed |
| 83 | BUG-2026-09-23-007 | [P1] **测试侧缺陷修复**：原「存量缺陷登记」`tests/test_bug_2026_09_23_004_in_order_page_audit.py::test_t13_batch_co… | 已修复 / 已实现 | [test_bug_2026_09_23_004_in_order_page_audit.py](../../tests/test_bug_2026_09_23_004_in_order_page_audit.py) 25 passed |
| 84 | BUG-2026-09-23-008 | [P1] **两个同路由别名列表页整片绕过 BUG-005/BUG-006 修复（`isWmsListPage` 用 `listUrl` 严格等值，只认规范 URL）**（R6 同根因：同一「列表… | 已修复 / 已实现 | [test_bug_2026_09_23_008_list_aliases.py](../../tests/test_bug_2026_09_23_008_list_aliases.py) 7 passed |
| 85 | BUG-2026-09-24-001 | [P1] **库存台账明细「日期」列显示流水创建时间（created_at）而非单据日期**（R6 同根因三处消费点 + 一处运行期累加顺序，一并收口）。现场（用户走查）：台账明细的日期与实际单据… | 已修复 / 已实现 | [test_bug_2026_09_24_001_ledger_document_date.py](../../tests/test_bug_2026_09_24_001_ledger_document_date.py) 7 passed |
| 86 | BUG-2026-09-22-007 | [P1] **采购退货出库的两个明细级接口可绕过防超退闸**（接口层与保存层校验不对称）：P1-7 的防超退设计是「**有来源**明细逐行计限、**无来源**行跳过」（兼容开关关闭期的历史退货），… | 已修复 / 已实现 | [test_bug_2026_09_22_007_purchase_return_item_endpoints.py](../../tests/test_bug_2026_09_22_007_purchase_return_item_endpoints.py) 4 passed |
