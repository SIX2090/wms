# BUG-2026-11-08-010：34入口能力核查与有限采购诊断候选

源码基线：`3b2cc4475ee6e16669166c8d0288e95c843c76aa`。本子任务只读核查这些现有源码，不以脚本存在、pytest通过数或静态PASS替代实际诊断能力。下表“已有”指安全入口提供对应业务阶段及输出，明确列出的网络/浏览器/范围差异仍未覆盖；本轮没有本机执行WMS。源自旧固定8080、LIVE库与真实凭据的34入口全部维持首条拒绝，不机械放开。

## 逐项结论

归类为 {'已有安全等价能力': 3, '应恢复': 17, '已废弃只保历史': 14}。这是入口处置分类，不是独立BUG数，也不是34项全部恢复。

| 原入口 | 处置 | 现有可核查能力与缺口 |
|---|---|---|
| `tests/diag_full_flow.py` | 已有安全等价能力 | diagnose_synthetic_push.diagnose：保存/完成/下推/重放阶段 ms、HTTP、库存和草稿不变量；是应用链路，不能当 TCP 延迟 |
| `tests/diag_http.py` | 应恢复 | 旧用途是登录/来源详情/下推页/目标详情真实 HTTP 分段；新下推诊断仅部分应用阶段，perf HTTP 仅列表 GET，仍缺相同有限 TCP 场景 |
| `tests/diag_live_get.py` | 应恢复 | 旧来源/领料详情时延输出尚未完整恢复；full_smoke 有页面状态，未输出该来源/目标明细组合分段 |
| `tests/diag_live_push.py` | 已有安全等价能力 | diagnose_synthetic_push：新库生成入库并下推草稿，输出耗时/唯一草稿/库存，不再写既有库；网络外延不覆盖 |
| `tests/diag_lock_contention.py` | 应恢复 | test_native_request_concurrent 有真实连接与锁断言；没有独立下推等待/释放时序诊断，仍是缺口 |
| `tests/diag_push_live.py` | 应恢复 | 真实 TCP 下推写入计时缺口同 diag_http；应用链路已有 diagnose_synthetic_push，不重复造旧 LIVE 工具 |
| `tests/diag_seed_big.py` | 已废弃只保历史 | 持久当前库造500明细不再恢复；新下推诊断可显式1–500行全新合成造数，500行证据单列，不承诺持久seed |
| `tests/diag_seed_live.py` | 已废弃只保历史 | 向当前库插既有单号的辅助工具退役；新下推场景自己创建/销毁合成库，无需LIVE seed |
| `scripts/edge_case_rules_test.py` | 应恢复 | verify_in_order_state_machine 有状态/库存边界PASS，相关pytest有仓库/重复完成等强断言；仍缺原多边界逐项诊断输出 |
| `scripts/verify_unit_delete.py` | 应恢复 | full_smoke 有单位页面/导出/API状态；没有引用中单位拒删及删除结果的同等诊断 |
| `scripts/endpoint_sweep.py` | 已废弃只保历史 | 任意端点含POST扫测不再恢复；安全有限页面/导出覆盖由run_smoke_in_ci→full_smoke提供，不宣称全路由全操作 |
| `scripts/system_functional_test.py` | 应恢复 | full_smoke 覆盖页面/导出/基础资料状态，state_machine覆盖单类状态；非完整工具栏/单据CRUD阶段等价 |
| `scripts/wms_e2e_visual.py` | 应恢复 | material_browser_check只覆盖明确物料浏览器样本，不等价全系统视觉/截图输出 |
| `scripts/verify_login.py` | 已有安全等价能力 | run_smoke_in_ci→full_smoke 的合成账号登录、改密、认证API逐项HTTP/PASS输出；不碰真实账号 |
| `scripts/verify_login_pw.py` | 已废弃只保历史 | 常见密码尝试是旧排障方式，不恢复；合成登录正反例已有测试/隔离smoke |
| `scripts/verify_base_materials.py` | 应恢复 | full_smoke 仅创建合成物料等基本状态；基础资料编辑/删除引用边界需独立有限场景 |
| `scripts/verify_category_add.py` | 应恢复 | check_add_category_generate与分类测试有业务断言；没有分类新增完整CLI诊断输出 |
| `scripts/verify_category_toolbar.py` | 应恢复 | material_category_navigation与p2_delete_category有回归；不是全工具栏浏览器行为诊断 |
| `scripts/repro_push_timing.py` | 应恢复 | 应用下推阶段已有；真实TCP写入阶段同diag_http缺口，不将pytest耗时当接口分段 |
| `scripts/archive/_challenge.py` | 已废弃只保历史 | 混合数据库/浏览器试验无稳定边界，保留历史；需要的有限功能按活动清单恢复 |
| `scripts/archive/_bench_push.py` | 已废弃只保历史 | 归档重复工具不复活；业务已有下推诊断，剩余TCP缺口由活动diag_http条跟踪 |
| `scripts/archive/_bench_lock.py` | 已废弃只保历史 | 与活动diag_lock_contention重复；锁诊断缺口保留在活动条，不新增另一入口 |
| `scripts/archive/_bench_big.py` | 已废弃只保历史 | 归档重复大单工具不复活；新下推行数参数/活动TCP缺口分别跟踪 |
| `scripts/archive/_full_demo.py` | 已废弃只保历史 | 旧浏览器演示不是稳定回归验收，不复活真实数据演示 |
| `scripts/archive/_full_demo2.py` | 已废弃只保历史 | 同上，保留历史截图脚本，不计能力恢复 |
| `scripts/archive/_demo_login.py` | 已废弃只保历史 | 旧默认账号浏览器演示退役，合成登录已有安全smoke |
| `scripts/archive/_trae_login.py` | 已废弃只保历史 | 旧默认账号浏览器演示退役，合成登录已有安全smoke |
| `scripts/e2e_business_flow.py` | 应恢复 | 现有采购/销售/库存回归分段，不等价完整业务CLI；本次仅补采购单一路径，不宣称销售/盘点全恢复 |
| `scripts/e2e_purchase_flow_10sets.py` | 应恢复 | 申请/订单/报表强回归多为直接造状态；缺真实路由串联诊断。本次优先单供应商一条申请的部分收货/反提交场景，其他9组仍缺 |
| `scripts/crawl_all_pages.py` | 已废弃只保历史 | 任意全站爬取工具退役；有限显式页面检查由full_smoke输出，未覆盖页不伪称全站通过 |
| `scripts/capture_mobile_screenshots.py` | 应恢复 | 缺375/414两宽度入出库列表/详情合成截图组合，源码/物料单页浏览器不能替代 |
| `scripts/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py` | 应恢复 | 现有embedded_duplicate_fab静态断言不是实际浏览器双按钮交互证据 |
| `scripts/audit/scan_all_menus.py` | 应恢复 | menu_document_regressions/menu_report_queries验证真实菜单与单据规则，但不是全菜单→页面标题逐项诊断 |
| `scripts/archive/_wms_browser_e2e_real.py` | 已废弃只保历史 | 真实账号/业务的旧浏览器演示不复活；有限合成浏览器场景另按活动项跟踪 |

## 核查方法与优先项

核对 full_smoke_test.record/_run_smoke、run_smoke_in_ci.serve_isolated 与 socket/nonce 证明；其实际输出是HTTP状态/PASS/FAIL、页面/导出/合成物料等有限场景，不包含完整采购申请→采购单→收货/反提交的数量快照。核对 tests/test_purchase_request_completed_receipts.py、test_purchase_report_completed_receipts.py、test_bug_2026_09_22_011_push_duplicate_item_aggregation.py：业务断言有价值，但多为直造单据关系、直接改变状态或仅调用单一环节，不能当全链路诊断输出。tests/test_native_request_concurrent.py 有真正双连接与锁断言，仍不是旧下推等待时序的独立诊断。本轮选择采购一个缺口，不引入文件库/监听或新框架。

所有引用的 pytest/verify 应只通过已有真实 Linux 隔离启动器运行；个别旧 verify 只有memory环境设置，不能直接在宿主当安全独立入口。本轮未执行这些入口，更未通过尝试生产连接来验证安全。

## 本次单一候选场景与边界

候选新增 `diagnose_synthetic_purchase.py --scenario purchase-receipt`，复用已合入 diagnose_synthetic_push._check 与 perf_runtime.initialize_synthetic_app/relative_target 的真实内核身份、新内存库、合成账号与目标检查，不修改原诊断/性能/Windows候选。场景固定单供应商、单物料、申请10、首次收货4、第二次收货6，实际走保存申请→审核→下推采购单→创建4入库草稿→完成→反提交→重新完成→生成6入库→完成，再验证申请/采购单实收、待收、双仓库存、报表、来源关联以及无重复下单。

不接受URL、数据库路径、账号密码、真实单号或任意业务操作参数。HTTP仅新应用test_client相对路径，禁止自动重定向，不创建监听。阶段输出仅状态、毫秒和数量/库存摘要，不输出密码、nonce、token或业务payload。真实WMS只交既有标准Linux CI；普通宿主进程先于app/数据库/网络拒绝。本次有限场景不等于原十组采购、销售/库存全链路、锁竞争或浏览器能力全部恢复。


## 采购候选实际输出与验收

该固定场景仅在新内存库显式选择库位关闭、允许采购单下推入库的正向夹具；没有修改生产设置，也不替代库位开启等其他业务回归。12个实际路由阶段输出HTTP状态与毫秒，7个实际数据快照输出申请实收/待收、采购已推预留/已完成/待收/待推、全局与A/B仓库存、仓库采购执行报表和入库数量。数量序列实收为0→0→4→0→4→4→10，预留为0→4→4→4→4→10→10；反提交只回库存和实收，不释放仍存在草稿的采购预留，重完成不能双计。读取的是实际模型/业务执行器/报表结果，预期只用于严格校验，不把预期数字冒充观测值。

现有业务规定采购单尚无任何入库单时没有可确认仓库归属，仓库报表应空。候选对此明确输出 report_has_warehouse_assignment=false、报表数量None；首次入库草稿分配A仓后才校验报表数量，B仓报表始终无行。不得为此诊断修改既有报表归属或把未归属采购量硬分到默认仓。

```sh
python scripts/run_ci_isolated.py -- python scripts/diagnose_synthetic_purchase.py --scenario purchase-receipt
```

标准启动器只验证精确已提交源码，未知来源/脏源码/宿主直接调用会拒绝。`tests/test_synthetic_purchase_diagnostic_20261113.py::test_actual_purchase_routes_receipts_revert_and_reports_in_isolated_linux` 在真实Linux边界内新进程执行此CLI，断言12阶段、7快照、申请与采购重试各唯一、最终两张入库和来源/报表不变量。本机只执行5项源码/无I/O反例与相邻安全检查，没有运行WMS；合入后实际路由和业务断言须以目标CI为准，不能把本机源码通过计为采购业务通过。

本批三新增文件的整批源码回退在私有副本按文档→测试→入口逆序移除，核对全部2505源码blob恢复到固定基线；旧版缺少有限采购诊断的验收明确失败，精确恢复候选后重验。这个旧红是诊断能力缺失，不是声称旧业务源码采购失败；本轮没有更改业务源码。完整实际行为/相邻业务与目标SHA CI由主任务验收。BUG-010仍保留上述未覆盖能力，不按34/34完成。生效确认：待人工确认。


统一集成范围：销售/主兼容修复、采购有限诊断及005的台账登记/查询修正共19文件；58源码/Node方法、20原DOM参数实例、24安全方法及11台账/CLI实例分别验证，清单行为重叠不计为功能数。最终整批逆序回退和精确CI按 combined-sales-purchase-r8-proof.json 与后续目标记录；45真实销售实例及1采购子进程仍待标准隔离CI，当前不预填完成。模板生产需重启 WMS 服务生效，未实际重启；生效确认：待人工确认。


最终20文件验收：19文件整批逆序已证明2442基线源码精确、旧回归失败且恢复后58源码/Node+20原DOM参数+24安全+11台账/CLI实例通过；审阅未交付候选又发现历史price=NULL仍空白却改量/税会清零金额。本次在行赋值前原子拒绝并中文要求明确填价（可填0），仅备注/明确0或3.5对照保持。新增2源码方法/4实际ORM实例，原候选两子例真实清0失败。20文件通过补充提交→逆序补充→逆序原19→精确基线→正序恢复，私有源码整批字节相同；恢复后60源码/Node方法、20原DOM参数、24安全方法、11台账/CLI实例通过。不同计数口径分别报告，不换算成BUG数；原315/141/19/1快照/断言不动。49真实销售ORM实例及采购12阶段子进程待精确CI，当前不报这些已通过。证明 combined-sales-purchase-20-r8-proof.json；生产需重启 WMS 服务生效，生效确认待人工确认。
