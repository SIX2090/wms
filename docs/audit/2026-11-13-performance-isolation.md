# BUG-2026-11-08-010：性能脚本同根因安全迁移候选

本候选固定来源为 `80aa229c0e0a5d93911f6779bebd1e0924812faa` 的 Git 源码导出；不读取/复制生产数据库、备份、凭据或运行目录。独立私有副本准备，不修改共享 main 的工作文件、Git 索引、版本与台账。

## 旧风险与消费者

- `perf_baseline.py` 导入即改环境和模块搜索路径；运行直接新建文件库、自选后释放端口再交 waitress 绑定，存在端口接管窗口。公共登录 helper 接受任意 URL，普通 requests 会跟随重定向，没有 PID/nonce/监听能力证明。活动调用为 `.github/workflows/perf.yml`；`tests/test_perf_baseline.py` 只导入统计函数。
- `perf_export_baseline.py` 导入即切 cwd、创建临时目录/库、改数据库环境并导入 app。没有活动工作流调用；现有回归仅在说明中引用其历史测量值。原测量是 Flask test_client + tracemalloc，不是 TCP HTTP。
- 已完整核对现有 `smoke_isolation.py` 的 OwnedSocketLease/IsolatedSession、run_smoke_in_ci.py 的服务端监听传递/nonce、run_ci_isolated.py 与 ci_test_entry.py 的精确 Git 导出、network-none、只读源码与 OS 证明。本候选直接复用现有租约和 Session，不降低其来源/响应校验，不修改启动器、selector 或证明格式。

## 新执行边界

两个入口和共享 `perf_runtime.py` 的普通导入均无 app、数据库、网络、子进程、环境变更、cwd/sys.path 修改或目录创建副作用，保留原统计函数供纯测试导入。

运行只允许现有 Linux 真隔离启动器：先核实内核/容器能力，再拒绝继承目标与预载 app/config，随后导入新应用，核验实际 SQLite memory engine 与 database_list 无附加文件。在本次新内存库创建随机独占合成账号密码，不接受用户凭据；不触及真实账号或生产库。运行条件发生变化、未知来源、身份/nonce 不符立即失败。

HTTP 基线继续测真实 waitress HTTP，并发/热身/十端点统计、p95 双阈值和告警用途保持。套接字由本进程 bind 127.0.0.1:0 后连续持有，拒绝低位/生产端口，经现有 OwnedSocketLease 关联当前 PID、64 字符十六进制 nonce 与监听；同一 socket 直接交 waitress，不释放端口再绑定。WSGI 仅给自有响应加随机 nonce；请求前核对监听，写请求前先由 GET 校验响应 nonce。IsolatedSession 拒绝代理与其他 origin，新会话额外拒绝自动重定向；所有调用显式 allow_redirects=False，身份错误不计入普通延迟错误后继续。关闭时仅回收本次会话、dispatcher、私有 channel map、listener 和线程，不操作全局服务。

导出基线保留原 test_client/tracemalloc 语义，改用同等验证的新内存库、专属合成登录；只接受相对端点，禁止重定向，核对客户端与新应用归属。所有 JSON 只写本次隔离 tmpfs `output/perf_current.json` 或 `output/perf_export_current.json`；拒绝其他输出路径和链接。两入口均设明确运行量上限。

## 测量 profile 与旧基线不可比

新 HTTP 结果明确记录 `measurement_profile=sqlite-memory-waitress-v2`；旧无标记历史基线按 `sqlite-file-waitress-v1`。存储变化会影响耗时，不能机械解释为同口径改善或回退。不同 profile 或没有共同端点时输出 `comparison.status=incomparable`、GitHub warning 和“未作性能通过或回归判定”，不进入 p95 判定，不输出“无超阈值回归”；--strict 返回 2。告警模式仍返回正常执行码，工作流的 advisory 语义保留，不能据此宣称性能通过。

相同 profile 使用原相对 >50% 且绝对 >50ms 双阈值，regression_alerts 不弱化。原 `scripts/perf_baseline.json` 文件完全不改，不用本次 memory 值覆盖旧 file 基线。导出结果也显式标记 `sqlite-memory-flask-test-client-export-v2`，与旧磁盘测量不可直接同比。

## 工作流与验证入口

perf.yml 原先在宿主直接调用改为：

```sh
python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py --seconds 2 --compare scripts/perf_baseline.json --output output/perf_current.json
```

Docker 依赖安装仍由现有只读源码构建阶段完成，运行期保持 network-none，未开启外部网络。上传路径为启动器导出的 `output/perf_current.json`。文档分流与 continue-on-error/advisory 聚合规则保留。

`test_perf_isolation_20261113.py` 的纯源码/拒绝/模型测试可直接用 -I -S -B 执行，不导入 WMS或发任何 HTTP。真实应用测试仅在 Linux 既有隔离边界运行：新进程测十个 waitress HTTP 端点；新进程测四个导出/查询端点；另一个新进程验证旧 profile + --strict 必须返回 2 且结果不可比。Windows 明确跳过这些应用子进程，不伪造继承 LPAC 能力。

本机仅源码/模型及无 I/O 负测；没有可核验 LPAC，因此未运行真实 WMS、waitress 或导出。最终应用行为、线程清理及工作流必须由合入后的精确 SHA CI 实际验收，本候选不声称性能通过。BUG-010 的其他 34 入口未恢复能力仍按原盘点跟踪。

## 回退与生产

候选共六文件：两原脚本、一个共享运行模块、工作流、测试、本文档。私有副本按文档→测试→工作流→导出脚本→HTTP脚本→共享模块逆序恢复/移除，核对全部筛选源码 blob 回到固定 Git SHA，安全保护下重跑旧导入纯度反例证明原问题，再恢复候选重验。真实应用行为回退仍待 Linux CI，源码回退不能冒充实际性能回退验证。

本批不部署、不重启、不更改生产配置，不连接/读取/备份/恢复/修改生产数据库或备份。生产生效无需本轮操作。


本批统一验收补证：16文件在私有源码Git整批正常逆序回退，2430基线源码文件逐字节恢复；保留候选锁后，旧对账重复统计及旧性能导入副作用按预期失败；恢复后10份明确非空专项91方法通过。编码/严格AI台账/全量棘轮无新增通过（全量存量386，不是零违规）。2个实际应用方法（对账请求/collector及性能HTTP十端点+导出四端点+strict不可比）待目标LinuxCI，当前未计交付。回执 report-perf-r8-proof.json。生效确认：待人工确认。


实际运行纠正：bbe8f58e的性能job131837014832真实测量前九端点成功、err=0，inventory_alert没有成功样本，严格断言使任务失败。根因是新内存库的预警开关默认关，/alert返回302；旧工具自动跟随跳转会错误地将物料页当预警测量。此次仅在已验证内核隔离、实际内存engine及无附加文件后，以set_system_setting显式开启本次合成预警功能；200、禁止跳转和非空样本全部保持。两项新增测试执行真实seed与真实inventory_alert_enabled函数（使用无I/O模型），分别覆盖首次造数及已造数提前返回路径。原版两项确实失败，修复后通过；真实HTTP/导出测试仍须纠正目标CI，不把性能工作流告警聚合绿灯冒充perf job成功。生产开关未读写，未对现役服务发请求。生效确认：待人工确认。


本批集成最终补证：11文件正常逆序回退/恢复仅在私有源码Git进行，2436基线源码文件精确恢复；旧material输入9个数值断言及旧合成预警设置2断言失败，恢复后8份明确非空专项80方法通过。另直接执行真实工作流快照断言，ci/verify/perf三项及启动器/窗口/产物/checkout/告警策略五项故意漂移反例共8项通过；整批回退后的原快照测试对新性能隔离workflow确实失败，恢复后再次8项通过。原FULL_JOB_SNAPSHOTS哈希未改，精确校验允许的隔离launcher/容器依赖/output变化，其他payload仍全量哈希比较。bbe8f58e的WMS CI确有两项失败（perf实际预警与旧perf快照），不是拿告警gate绿灯作为通过。根因均已补具体修复，14新物料真实应用实例及性能子进程复验仍待本批精确CI。回执 material-perf-r8-proof.json；生效确认：待人工确认。


2026-11-13 精确统一验收：bbe8f58e 的两个已知失败已由 `3b2cc4475ee6e16669166c8d0288e95c843c76aa` 纠正，[WMS CI 43412495414](https://github.com/SIX2090/wms/actions/runs/43412495414)、[AI 43412495421](https://github.com/SIX2090/wms/actions/runs/43412495421)、[性能 43412495410](https://github.com/SIX2090/wms/actions/runs/43412495410) completed/success。三个单元分片4837/5177/4807 passed，39/28/135 skipped，178/173/904 subtests passed，合计14821 passed、202 skipped、1255 subtests passed。14新物料真实POST实例和实际性能子进程通过；十个HTTP端点均非空且err=0，四导出端点及strict不可比退出2亦通过。Android成功祖先8cba9986的43399657746输入不变。正常非强制push输出 `bbe8f58e..3b2cc447 main -> main`。Windows发行43413458951另行跟踪。旧失败记录保留，不把告警聚合绿或新内存profile解释为历史性能提升；生产生效待人工确认。
