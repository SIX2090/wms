# 2026-10-21 审计报告复核与整改

复核基线：main `d2437fd992ba6c55b6379c4c03872e78f70288b5`。按用户要求先复核、逐项整改、最后修绿 CI。本次顺序由用户明确覆盖开工全绿门禁；不降低测试或安全扫描要求。

## 结论与逐项处置

原报告混用了历史发现、整改前复现和当前状态。CI/Pillow 风险属实，但不能据此推断其他修复未合并；安全入口和库存的五项主要代码缺陷已修复，不应重复开发。生产进程生效情况不由源码或 CI 推断。

| 项目 | 复核结论与证据 | 处置 |
|---|---|---|
| CI / Pillow | WMS CI #1664 的 lint-and-static job 118905712636，pip-audit 明确报 12.3.0 的8项 CVE，修复版13.0.0；其余测试、冒烟、gitleaks jobs/steps通过 | 依赖修复作为本轮最后代码动作；不忽略 CVE、不关闭扫描 |
| A04 会话 CSRF | `app/session_csrf.py:6`、`app/routes/mobile.py:76`；实际使用会话必须验证 token，有效 Bearer 保持可用 | 复跑真实请求/装饰器测试通过；前缀豁免不等于最终写接口无校验 |
| A05 API 登录限流 | `app/routes/native_api.py:911` 起使用共享 `login_fail:{ip}`，未知账号及错密码计数 | 跨账号、跨登录入口、窗口恢复及 IP 隔离测试通过 |
| 开库位即事故 | `app/routes/system_settings.py:95` 已在0→1时调用 `find_location_ledger_mismatches`，差异拒绝并回滚 | 开关路由测试通过；没有切换生产开关或回填账务 |
| 并发扣减非原子 | `app/app.py:4771` 已先取写锁并包含 `_wh_stock_guards` 条件 SQL；mobile/native 路由已有写锁 | F2.9确定性交错、多仓/历史归属回归通过；不能声称所有数据库和所有并发场景均已证明 |
| 反提交归属死代码 | `app/routes/in_order.py:2437` 加锁在前，2451起归属修正在后 | F2.12专项通过，原报告重复历史已修问题 |
| 恢复能力仅纸面 | 已有 `restore_backup.py` 的SQLite备份API恢复、占用检测、结构校验、恢复前留底及WAL回归 | 本次另完成现有每日备份的真实隔离恢复，见下 |
| 备份冷拷贝 | `scripts/online_backup.py` 使用只读源连接+SQLite backup API；不能把10月10日旧问题当作当前实现 | 现有备份/恢复测试通过 |
| 模板 safe | alert命中的是JS逻辑或而非Jinja过滤器；sales_reconciliation_report先tojson；打印输出已有沙箱+白名单净化（app.py:35193、utils.py:461） | 原报告不能据裸字符串命中认定漏洞；本次未进行全站XSS攻击面审计 |
| 本地云密钥 | 被Git忽略的 `run_wms_task.bat` 仍含腾讯云凭证字面量，未输出内容；不是已提交源码泄露证据 | BUG-2026-10-21-001登记待处理；需凭证迁移与云端轮换，不能直接删配置导致OCR中断 |
| 架构债务 | AST统计app.py为94个@app.route、36,235行；routes目录49个直接.py文件、services为5个；与报告102/36,219/54/4不一致 | 大文件仍属真实技术债；按下面计划迁移，禁止凭行数立即重构 |
| 测试数字 | 当前tests根目录526个test_*.py；文件、函数、参数化测试用例统计口径不同 | 不把4699个函数当作4699个已执行通过用例；历史4340 passed为当时证据 |
| 工单领料收敛 | INVENTORY_TRUTH批6仍明确待语义评估 | 保持独立评估，不在依赖修复中改库存语义 |
| 治理评价 | CI红灯证明阻塞扫描发现风险，不能等同于“门禁失效” | 索引明确区分原始发现、后续修复、本轮验证及生产生效 |

## 恢复演练与生产只读核验

源备份：`C:\wms_backups\auto_daily_20261021_020000_inventory.db`（5,242,880字节）。
在系统临时目录创建并删除一个空测试库后，显式指定 `--db <临时目录>/drill.db --yes` 调用现有恢复工具，退出0。未使用默认生产目标。临时目录完成后自动清理。

源与恢复库完整SQL逻辑转储的SHA-256相等：`40edde882dc5f12674dacba684b5b76960bb8eb75ca7552baf7d55632d9632a8`。仅记录摘要，不保存/输出业务内容及凭证。

两者均 integrity_check=ok，外键违规0，1331物料、4仓库、3989流水、1库位账行，负库存0、总账与流水差异0。生产库通过mode=ro连接核验，同样计数与上述检查通过；生产和备份全库摘要不同，不把备份时点等同当前生产状态。报告的1317/3918/2等数字已经过时。没有宣称库位关闭时三账全部相等，也没有由检查行数推断孤儿和乱码全部不存在。

本次仅证明这一个备份在当前工具下可恢复且库存合计一致；未启动恢复库上的WMS做人工单据验收，也不代表所有历史备份均可恢复。

## 本轮测试证据

统一设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`，测试使用内存库或临时文件库。

- `python -m pytest tests/test_audit_20261020_remaining.py tests/test_f2_10_location_switch_guard.py tests/test_audit_restore_safety.py tests/test_audit_backup_catalog.py -q -p no:pylama --tb=short`：109 passed。
- `python -m pytest tests/test_f2_9_toctou_deduct.py tests/test_f2_12_in_order_asymmetry.py tests/test_warehouse_stock_service.py tests/test_backup_scheduler.py -q -p no:pylama --tb=short`：35 passed。

## 后续分阶段迁移计划

1. 先建立待迁移路由清单，以函数/端点名引用替代易漂移行号；与既有AI台账任务查重。
2. 优先选择只读、依赖少的路由组；每组只移动结构，URL、权限、CSRF和响应契约不变。
3. 每组先跑模块基线，再迁移并跑模块、相邻、全量和冒烟；独立commit/push并验收CI。
4. 库存写链路、工单领料批6保留独立语义评估，缺少可证明等价性的证据时只登记。

本轮不启动季度级重构，不重复实现已经通过验证的防护。生产服务未重启、密码未修改、数据库未恢复/初始化/回填。部署生效及云密钥迁移轮换属于未闭环项。
