# 独立全面审计整改计划与进度（2026-11-04）

用户授权：按计划执行，统一修复、统一验证、统一提交、统一推送。每个大项独立形成交付批次，精确目标完整 CI 验收前不进入下一批业务写入。固定独立审计 74 分的七维权重，不用测试条数代表功能完成率，不预先增加评分。

隔离工作目录：`C:/wms_audit/20261104_remediation/repo`，直接 main。保留原 `C:/wms` 未提交改动；生产有两位独立账号使用者，二人确认均从 `https://gd2026.top` 登录。业务验证只用合成内存库或本次专用测试库；开发阶段不操作生产库或服务。后续明确授权的生产发布、每日只读在线备份和监护启用按各自回执单列，不执行生产业务测试写入、账号修改或未授权恢复。

| 大项 | 对应发现 | 冻结范围与验收 | 状态 |
|---|---|---|---|
| 整改-01 依赖与登录安全 | IA-01、02 | 锁定安全依赖，检查实际解释器/导入版本；HTTPS 会话与记住登录 Cookie；双账号登录、刷新、恢复、退出、超时和可信 HTTP 兼容；真实 Windows 包及 Chrome 验证 | fe806cc7代码交付：CI41937764115第2次、AI41937764128成功；Android41937038001成功且输入无变；已于2026-11-05 14:21随85df6437启用匹配依赖及HTTPS配置；[生效证据](2026-11-05-document-revision-production.md) |
| 整改-02 自动备份与故障恢复 | IA-03、04 | 接通实际入口或独立调度，备份失败可见；有限重试及单实例；合成 WAL 库备份/恢复和隔离进程故障演练 | 19e66b05代码交付：WMS CI41950700388、AI41950700369、Windows包41951263572成功；Android成功祖先且输入无变；[范围与隔离证据](2026-11-05-scheduled-operations.md)；2026-11-05 15:31监护实际接管、取消一小时时限，15:35真实SYSTEM备份成功；每日02:00/保留30天，[生产回执与未到时项](2026-11-05-scheduled-operations-production.md) |
| 整改-03 双账号覆盖与输入校验 | IA-05、06 | 核对 Web、Android、API 版本令牌消费点；缺令牌不静默覆盖；错误字段类型返回 4xx 且不写入；首存、幂等、多仓和相邻单据回归 | 代码及生产生效完成：85df6437，2026-11-05 14:21切换；完整CI、实际发布包及公网核验通过；[上线证据](2026-11-05-document-revision-production.md)；真机待硬件 |
| 整改-04 发布一致性与暂停功能状态 | IA-07、08 | 源码、覆盖文件、依赖及配置身份可追溯、空目录复现；暂停设备/微信入口说明真实状态 | 本地候选与六组真实Chrome通过，隔离冒烟121/121；统一回归及文档引用纠正见[第四项记录](2026-11-05-release-identity-and-paused-operations.md)。未推送/未部署；待主干全绿后合入上游，验收精确完整CI及Windows实际包；不自动启用真实外发或打印 |
| 整改-05 全站前端与模块维护 | IA-09、10、11 | 冻结完整页面/内联执行点/具体模块清单；按物料、出入库、库存报表、其他业务、管理页面逐批完成 CSP、字段标签及有明确收益的模块拆分；每批实际交互和相邻回归 | 待执行；清单未完不把试点当整项完成 |

IA-12 主机容量持续观察：串行、低优先级本地检查，大规模回归交 CI；不在生产宿主进行压力测试，不先购买硬件。

每批记录问题数、验证证据、提交、push、目标 CI、生产生效和受限项。硬件、真实外发、付费 AI、生产恢复属于独立现场验收，不能用代码检查冒充完成。

## 整改-01 本地证据

基线 `a01b1bbeab9c303c644bddd388f6ee424b7676c9`：WMS CI [41854937486](https://github.com/SIX2090/wms/actions/runs/41854937486)、AI [41854937484](https://github.com/SIX2090/wms/actions/runs/41854937484) 成功；Android [41740259322](https://github.com/SIX2090/wms/actions/runs/41740259322) 的 `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba` 是祖先，Android 工程及工作流无差异。

- 已有 pypdf 清单锁定 6.21.4，问题在实际运行环境仍加载 6.21.2；没有重复修改已正确的版本锁。
- 显式锁定 certifi 2026.10.18。依据：[certifi 官方公告](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)、[pypdf 官方公告](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5849-834g-hvw5)。未放宽 pip-audit、TLS 或 CSP。
- 新增 `tools/check_runtime_dependencies.py`，只读清单、发行包元数据和 PDF/TLS 模块实际导入版本/路径，不导入 WMS、不访问业务库；版本不一致、缺包、导入被旧文件覆盖或清单未锁定时失败。便携构建使用**包内解释器**执行检查并生成 `runtime-dependencies.json`；便携验收在初始化合成库之前执行同一检查。
- 记住登录 Cookie 的 Secure 跟随会话配置，HttpOnly 固定开启、SameSite=Lax；TestingConfig 显式保留 HTTP。现有可信 HTTP 模式和人工选择是否记住登录不改变。用户的生产 HTTPS 入口需要在未来发布时设置 `SESSION_COOKIE_SECURE=true`，不能把本次代码提交说成生产已生效。
- 修前 9 模块 130 passed；新增 16 项及相邻组合 146 passed。物理整批回退后 15 failed/1 对照 passed，随后逐字节恢复全部候选产品文件；没有修改既有测试断言。
- 真实 Chrome 使用仅绑定 localhost:18945 的合成 HTTPS 服务和两个专用仓管账号：登录、刷新、只保留记住登录凭证后的恢复、点击退出、退出后受保护页面回登录、另一账号继续使用均通过；两种 Cookie Secure/HttpOnly/SameSite 均正确，页面异常为零。仅对本次自签名 localhost 证书忽略信任错误；生产/外网 TLS 校验未关闭。测试服务已停止。
- 新隔离 Python 环境 pip check 通过；真实 PDF 安全/正常/损坏/加密/多页等现有回归通过；requests 使用新 certifi 正常校验证书，访问 PyPI HTTPS 返回 200。系统解释器仍报告旧 pypdf/certifi，证明门禁可识别审计中的实际漂移；没有对系统解释器执行安装或升级。

Windows 嵌入式 Python 实际构建成功；用最终验收驱动在一次性目录验证包内依赖、无Flasgger、新合成库初始化、拒绝再次初始化且已有库哈希不变、受保护启动、中文登录和静态资源通过。验收进程明确关闭本地打印代理及自动备份，备份/上传目录限制在临时安装内；相关45项补充回归通过（与146项重叠，不相加）。候选包来自仅含程序文件的临时main仓库，未覆盖任何既有安装。

收尾：最终产品文件再次物理整批回退，15项失败、1项对照通过，所有候选文件哈希准确恢复，证明见 `r8-batch01-final/proof.json`。A1–A14、A11全量、全量棘轮、非GET请求、源编码、严格AI台账均通过；候选环境完整冻结清单的59个发行包由pip-audit查询，未发现已知漏洞，没有忽略项。远端随后新增 `04245ed4cd08cde0322184d732bd512740c4837a` 的3个生产部署回执文档，程序文件无差异；本批保留这些回执，核实其CI和AI均成功后统一推送。

### 2026-11-05 首次 CI 失败及 R8 重做

首次发布 `5a753090f705bc915dc9622fe4df8cf451d2e946` 的 [WMS CI 41861873403](https://github.com/SIX2090/wms/actions/runs/41861873403) 实际失败。API和页面曾持续显示queued，但聚合日志明确报告unit-tests-shard-2失败，因此以失败日志为准，不把排队或其他分片成功当整批完成。失败为 `test_f4_4_ledger_split.py::TestMonthlyReviewEquivalence::test_status_distribution_matches_pre_split`：本批119/120两条新增登记漏列入 `POST_SPLIT_BUGS`，使历史fixed计数变成317而非315。本地完整台账模块复现1 failed/9 passed；AI聚合、其余单测、四个verify分片、smoke、真实浏览器任务日志均成功。

已用 `5f183805` 整批revert，确认完整tree回到绿色基线04245ed4，台账模块10 passed。随后完整重做原批次，只额外补119/120两项明确的状态登记；原始 `STATUS_DIST_BASELINE`、逐项状态断言及历史计数断言均未改变，不忽略未知条目，不自动从当前台账推导期望结果。产品文件与5a753090完全一致，之前真实Chrome、运行包及物理回退证据仍对应同一产品内容。重做后的整批及台账相邻14模块181 passed；证据 `batch01-ci-reproduce.xml`、`batch01-ci-ledger-baseline.xml`、`batch01-r8-unified.xml`。后续精确新SHA的完整CI验收仍是交付前置条件；生产未部署本批。

重做收尾：`verify_wms_bugs.py`、暂存A1–A14、非GET请求、源编码和严格AI台账全部退出0。`batch01-r8-correction-proof.json`核实整批回退tree、产品内容及全部原测试函数/断言AST一致，测试差异严格只有两条登记。未来批次新增BUG台账时，把已有台账守恒模块纳入相邻回归，不通过修改历史统计基线消除失败。

证据目录 `C:/wms_audit/20261104_remediation/evidence`：`batch01-baseline.xml`、`batch01-unified.xml`、`batch01-package-final.xml`、`batch01-physical-rollback.xml`、`r8-batch01/proof.json`、`cookie-browser-acceptance.json`、`existing-runtime-check.json`、`candidate-runtime-check.json`、`candidate-environment.txt`、`outbound-https.json`、`package-build.log`、`package-acceptance.log`。统一门禁、实际 push 与精确 CI 结果将在本批交付回执补齐；补齐前不报告交付完成。

## 发布时如何验收运行依赖

使用准备启动服务的同一个解释器，在对应发布目录执行：

```powershell
& '<发布包的Python路径>' tools/check_runtime_dependencies.py --json
```

退出码必须为 0，核对 pypdf/certifi 的实际导入路径和版本；再执行对应解释器的 `-m pip check`。检查不替代完整 CI 或业务验收，也不自动升级运行中的 Python。切换前保留完整旧源码、覆盖层、解释器和原启动配置；代码回退不得覆盖仍在使用的数据库。待依赖包、HTTPS 登录、回退组合完整验收后再安排生产生效窗口。
