# BUG-2026-11-08-010：合成诊断能力恢复候选

基线：`80aa229c0e0a5d93911f6779bebd1e0924812faa`。本轮不解除 34 个旧入口首条拒绝语句，不向它们传真实地址或凭据。生产数据库、生产备份、现役服务、真实账号及单据均不在验证范围。

## 新入口与实际能力

`scripts/diagnose_synthetic_push.py --scenario inbound-push --rows 1` 仅接受一个显式场景和 1–500 行合成明细。执行前复用 `require_isolated_test_runtime()` 核对内核隔离身份，再用 `require_synthetic_memory_database()` 拒绝继承目标/预载应用；导入后再次核对 engine URL 与 `PRAGMA database_list` 均无文件。

在全新内存库创建独占合成账号、仓库、供应商、单位和物料，实际执行首次保存入库→完成→渲染下推页→创建领料草稿→同请求重放。HTTP 全部为 Flask `test_client`，不创建监听，不接受 URL、文件库、账号或任意命令参数。诊断以 `WMS_SYNTHETIC_DIAGNOSTIC=` 输出机器可读 JSON，包含五阶段 HTTP 状态和毫秒耗时、来源/目标状态、目标数量和单数、入库前后/下推后库存与重放验证结果。任一业务或库存断言失败即非零退出；使用显式检查，不受 Python `-O` 影响。

这是应用/数据库/模板链路的合成耗时，不能当真实网络、代理、硬件或生产性能证据。`--rows 500` 可操作 500 明细合成场景；候选实际应用测试只选择 1 和 25 行，500 行仍待隔离运行证据。

Linux 必须在现有启动器签发的真实只读源码、network-none 容器内运行：

```sh
python scripts/run_ci_isolated.py -- python scripts/diagnose_synthetic_push.py --scenario inbound-push --rows 25
```

该命令必须针对已提交的精确源码运行；启动器拒绝脏源码，不能在宿主直接用内存 URI 或环境标志冒充隔离。现有启动器已允许非空 Python 命令，无需扩大 selector、关闭 guard 或改证明格式。自动实际回归由 `tests/test_synthetic_push_diagnostic_20261113.py::test_actual_synthetic_push_reports_stages_stock_draft_and_replay` 在同一真实 Linux 容器内的新进程运行。Windows 子进程需要启动器另发 LPAC 能力，自动测试明确跳过，不伪造父能力；本机尚无可核验通用 LPAC 启动器。

## 34 个旧入口逐项盘点

“合成替代”表示新场景覆盖相应业务/分段耗时，不表示旧脚本恢复、完整 HTTP 基准或其他业务等价。无替代的能力继续登记未完成。

| 旧入口 | 用途/当前价值 | 本轮处理与边界 |
|---|---|---|
| `tests/diag_full_flow.py` | 入库保存、完成、下推全流程分段计时 | 合成替代；真实网络耗时不覆盖 |
| `tests/diag_http.py` | 现役 HTTP 路由耗时 | 仅入库/下推页面由合成替代；其他端点待恢复 |
| `tests/diag_live_get.py` | 读取现役入库/下推页面 | 合成页面替代；不读取既有单据 |
| `tests/diag_live_push.py` | 对既有单据下推计时 | 合成下推/重放替代；禁止既有单据 |
| `tests/diag_lock_contention.py` | 现有文件库持写锁与 HTTP 竞争 | 未恢复；需要自有双连接文件库与受证明 HTTP 服务 |
| `tests/diag_push_live.py` | 现役下推写入与耗时 | 合成下推/重放替代 |
| `tests/diag_seed_big.py` | 向当前库造 500 行完成单 | 以新流程 --rows 500 替代造数；500 行实际验证待做 |
| `tests/diag_seed_live.py` | 当前库造数支持诊断 | 以新流程隔离造数替代；不恢复持久写库 |
| `scripts/edge_case_rules_test.py` | 完成、反提交、删除、仓库边界 | 未完整恢复；本轮只覆盖合成完成与下推；保留现有状态机回归 |
| `scripts/verify_unit_delete.py` | 单位删除引用约束 | 未恢复独立诊断；需专门合成单位/引用样本和断言 |
| `scripts/endpoint_sweep.py` | 批量扫 GET/POST 端点 | 不恢复任意端点写扫；逐路由明确合成样本后再做 |
| `scripts/system_functional_test.py` | 全站工具栏、导出、单据状态流 | 未完整恢复；仅入库/下推子链路合成替代 |
| `scripts/wms_e2e_visual.py` | 浏览器视觉巡检截图 | 未恢复；需要同启动器控制的合成服务与浏览器 |
| `scripts/verify_login.py` | 默认账号登录诊断 | 新场景验证独占合成账号登录；默认/真实账号不恢复 |
| `scripts/verify_login_pw.py` | 尝试常见密码 | 退役；不恢复猜真实账号密码能力 |
| `scripts/verify_base_materials.py` | 基础资料建改删 | 未完整恢复；本轮只创建独占合成基础资料 |
| `scripts/verify_category_add.py` | 分类新增 | 未恢复；现成分类测试可回归但不算独立诊断恢复 |
| `scripts/verify_category_toolbar.py` | 分类工具栏 | 未恢复；需要合成 UI 行为证据 |
| `scripts/repro_push_timing.py` | 下推时间分段 | 合成替代；不包含真实 TCP/WSGI 延时 |
| `scripts/archive/_challenge.py` | 浏览器/库混合挑战 | 历史归档继续退役；如有具体故障需迁移场景 |
| `scripts/archive/_bench_push.py` | 现役 HTTP 下推性能 | 合成分段替代；HTTP 基准待安全服务迁移 |
| `scripts/archive/_bench_lock.py` | 现有库写锁竞争 | 未恢复；同 diag_lock_contention 边界 |
| `scripts/archive/_bench_big.py` | 现役大单下推性能 | 合成行数参数替代业务链路；实际大单/HTTP 基准待验 |
| `scripts/archive/_full_demo.py` | 浏览器演示/截图 | 归档继续退役；不可当回归入口 |
| `scripts/archive/_full_demo2.py` | 浏览器演示/截图 | 归档继续退役；不可当回归入口 |
| `scripts/archive/_demo_login.py` | 默认账号浏览器演示 | 退役；真实账号不恢复 |
| `scripts/archive/_trae_login.py` | 默认账号浏览器演示 | 退役；真实账号不恢复 |
| `scripts/e2e_business_flow.py` | 采购/销售/库存全链路 | 未完整恢复；本轮只有入库/下推子链路 |
| `scripts/e2e_purchase_flow_10sets.py` | 十组采购申请到报表 | 未恢复；需专门完整采购合成样本 |
| `scripts/crawl_all_pages.py` | 抓取现役页面 | 未恢复任意抓取；需显式页面清单和合成角色 |
| `scripts/capture_mobile_screenshots.py` | 375/414 手机截图 | 未恢复；需要受控浏览器/服务、明确合成单据 |
| `scripts/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py` | 实际浏览器嵌入页双按钮 | 未恢复；源码回归不替代浏览器交互 |
| `scripts/audit/scan_all_menus.py` | 菜单与页面标题对应 | 未恢复独立扫描；现成菜单测试不是全站标题诊断 |
| `scripts/archive/_wms_browser_e2e_real.py` | 现役浏览器业务/截图 | 退役；不得复活真实业务账号/单据路径 |

## 调用点与同根因核查

对 scripts/tests/.github/Makefile/docs 的脚本名检索：34 项没有活动 CI 或 Makefile 执行调用；主要消费是 `test_diag_fail_closed_20261108.py`（8 项）、`test_unsafe_legacy_scripts_fail_closed_20261108.py`（26 项）及历史台账/说明。`test_audit_scripts_paths.py` 只检查旧菜单脚本源码路径。上述 68 个导入/执行拒绝反例必须全部保留。

同根因额外找到 `scripts/perf_baseline.py` 与 `scripts/perf_export_baseline.py`：自行配置新库/监听仍不等于内核隔离证明，公共 HTTP helper 缺少服务身份/重定向保护。`.github/workflows/perf.yml` 直接调用前者，`tests/test_perf_baseline.py` 导入它的纯函数。单加顶层 guard 会破坏现有 CI，故本轮不修改、不在宿主执行；后续须将性能工作流接入既有真正隔离启动器，并给自有监听、请求与重定向补完整证明后再验收。不得把这两个同类风险说成已修复。

## 验证口径与未完成

本候选本机仅运行纯源码/合成模型与无 I/O 拒绝测试，不导入 WMS，不连接数据库或网络。实际 WMS 分段诊断、1/25 行业务及库存断言需要合入后精确目标 CI 的真实 Linux 隔离环境验证。未取得该运行结果前，BUG-010 保持“安全阻断已交付，部分合成诊断候选待 CI，其他能力待恢复”；不得按 34/34 功能已恢复统计。

本批三个新增文件可在私有源码副本按文档→测试→入口逆序撤销，回到固定 SHA 的文件集合；这只证明整批源码回退，应用行为逆向证明需同精确 CI 补证。生产生效：本批不涉及生产部署或迁移。


集成批本机验收补证（2026-11-13）：本批 14 文件在私有源码 Git 整批正常逆序回退，2418 个基线源码文件逐字节核对；保留候选回归锁后，旧版销售金额与缺失安全诊断入口按预期失败；精确恢复后 18 个非空专项共 147 方法通过。纯源码编码与严格 AI 台账通过，全量棘轮无新增违规（存量 386，不是零违规）。本机不运行 WMS；新增实际应用 8 个金额实例、18 个事务/盘点/期初实例、1 个诊断子进程方法（1/25 行）等待目标隔离 CI。回执位于本聊天 parallel-audit-r8-proof.json；提交、推送及目标 CI 后续补证，生产生效待人工确认。
