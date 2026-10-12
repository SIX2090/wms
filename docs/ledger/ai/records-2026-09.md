# AI 台账 · 记录归档 2026-09

> 本分片由 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md §16 完成记录小节及散装记录` 拆出（F4.4（2026-10-13））。
> 查询：`python scripts/query_ledger.py --task <ID>`。

---

#### ARCH-MODELS-01（进行中）— app.py 模型区按域抽取到 app/models/ 包

- 完成日期：2026-09-15（AA-1 核心业务模型 64 个 + AA-2 AI 模型 26 个，共 90 个全部迁出）
- 目标：把 `app/app.py` 模型区（原 L4136–L7353，约 3200 行）的 90 个 `db.Model` 类按域抽取到 `app/models/` 包，`app.py` 以门面导入保持全部既有调用点零改动。app.py 是 god-object（34,307 行 / 892 函数 / 90 模型 / 102 遗留路由），本次先摘收益最大、风险最低的模型层。
- 关联历史任务：`SYS-AUDIT-010`（曾评估 SystemSetting 迁 `models.py` 后暂缓，理由"架构改动大、回归风险高"）；`AI-REFACTOR-APP-SPLIT`（路由拆分先例，register-on-app 保持 endpoint 名不变）。重启条件：1727 用例全量回归兜底 + 门面模式（调用点零改动）+ 用户明确授权。
- 业务边界：纯结构搬迁，不改任何模型字段/关系/表名/迁移 DDL，不改业务逻辑、权限、事务边界；不建任何新分支（仅 `main`）。
- 改动模块（AA-1）：
  - 新增 `app/models/__init__.py`：包文档 + 6 域模块 `from models.<domain> import *` 汇总。
  - 新增 `app/models/core.py`（8 模型：User/LoginLog/ApiToken/MobileApiRequest/OperationAudit/Notification/UserFieldConfig/SystemSetting）。
  - 新增 `app/models/master_data.py`（10 模型：Employee/MaterialCategory/Unit/Supplier/Customer/Warehouse/Department/Contract/Material/MaterialImage）。
  - 新增 `app/models/print.py`（8 模型：PrintWorkstation/PrintDevice/PrintRouteRule/PrintJob/LabelTemplate/InOrderPrintTemplate/OutOrderPrintTemplate/ExcelPrintTemplate）。
  - 新增 `app/models/documents.py`（34 模型：出入库及业务单据 OpeningStock/InOrder/OutOrder/InventoryCheck*/Subcontract*/BOM*/ProductionRequisition*/Transfer*/Adjustment*/AfterSaleOut*/Purchase*/Sales*）。
  - 新增 `app/models/inventory.py`（2 模型：LocationInventory/StockTransaction）。
  - 新增 `app/models/wechat.py`（2 模型：WechatShareConfig/WechatShareLog）。
  - `app/app.py`：删除模型区 1380 行（含前导空行），改为 `from models import (...)` 门面（64 名）；`User.increment_failed_count` 内 `max_login_failures()`/`account_lock_minutes()` 改为运行时延迟导入（两者留守 app.py）；`User` 6 个方法补 `# no-test:reason=ARCH-MODELS-01 ...` 豁免注释（满足 A9）。
  - 删除 `app/models.py` 存根（12 行，仅 `from app import db`，无人引用；不删会与 `app/models/` 包命名冲突并致循环导入）。
  - `tests/test_filter_advanced.py`：`test_performance_index_declared_in_model_and_migration` 模型侧检索范围由仅 `app.py` 扩展为 `app/app.py + app/models/*.py`（迁移 DDL 仍在 app.py），断言意图不变。
  - 改动模块（AA-2）：新增 `app/models/ai.py`（26 模型：AIMaterialAlias/AIRun/AIToolCall/AIRollbackEvent/AIManualFallbackTask/AIRolloutAudit/AIAcceptanceDailySnapshot/AIAcceptanceEvidencePackage/AIRequestIdempotency/AIDraftIdempotency/AIFieldFeedback/AIKnowledgeVersion/AIAgentRunLock/AIAgentRetryRecord/AIAgentHumanConfirmation/AICleanupLog/AIDocumentJob/AIDocumentItem/AIDocumentFieldConfirmation/AIDocumentAttempt/AIDocumentFeedback/AIAgentTask/AIAgentStep/AIPatrolRule/AIPatrolAlert/AIPatrolSchedule）；`app.py` 再删 686 行、门面追加 `from models.ai import (...)`；`app/models/__init__.py` 增加 ai 域聚合。
- 关键设计：`from models import X` 与 `from db import db` 均为平铺导入，与 `document_evidence.py`（既有"独立模型文件 + app.py 门面导入"先例）、`run_server.py`、`app.py` 现状一致；`app/models/core.py`（含 User）整体置于 `from document_evidence import DocumentEvidence` 之后，规避对 `document_evidence` 的循环依赖。
- 验证命令及结果：
  - `python3 scripts/lint_wms_rules.py --staged` → 0 违规（A1–A11）。
  - `python3 scripts/lint_no_raw_post_fetch.py` → 通过。
  - 门面完整性快照：迁移前后 `dir(app)` 公开名 1263 → 1263（丢失 0 / 新增 0）。
  - `pytest tests/ -q` → **1727 passed, 84 skipped, 0 failed**（AA-1、AA-2 均与迁移前基线一致）。
  - 首轮曾现 6 failed（索引测试按 app.py 源码文本计数），修正检索范围后全绿。
  - AA-2 后 `grep -c 'db\.Model' app/app.py` → 1（仅 L929 迁移注释），代码层面 0 模型残留。
- 推送验证（AA-1）：常规 HTTPS push 被网络层拦（`gnutls_handshake() failed`），按 AGENTS.md §8.1 走 API 通道（Git Data API 四步重放）推送成功：远程 commit `da4074d2870ca3e7632a180b8eeb9924ddbabfd9`，反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD 已更新、11 个文件变更与预期一致（本地 `6bbe17d` ↔ 远程 `da4074d`，内容一致）。
- 推送验证（AA-2）：常规 HTTPS push 被拦，走 API 通道推送成功：远程 commit `58084f5ee24f7de3f02284705a8360c1b6ad494c`，反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD 更新、4 个文件变更与预期一致（本地 `f03ad6e` ↔ 远程 `58084f5`，内容一致）。
- 状态：**已完成**（90 个模型全部迁出 app.py）。
- 剩余风险和下一子项：
  - 残留污染点已清理：`db.Model` 在 app.py 仅剩 1 处注释文字（L929 迁移注释），非代码引用。
  - app.py 仍留 892 函数 / 102 路由 / 305 处 SQL，helper 层（`get_default_warehouse` 等）与路由层尚未下沉。
  - 函数体内 `from app import (...)` 延迟导入是架构债（routes 反向依赖 app.py），需后续以 app/services 解耦。

#### ARCH-OS-IMPORT（已完成）— 期初库存"导入导出模板 / 批量导入 / 粘贴导入"补齐

- 完成日期：2026-09-15
- 关联 BUG：`BUG-2026-09-15-003`（R6 同根因 `BUG-2026-08-05-006` 漏网消费点；台账 P1-B 遗留的 `/opening_stock/import` 重定向 stub）。
- 目标：修复期初库存页三个半成品导入功能（用户反馈"根本没法用"），接入仓库既有集中式批量导入框架，不重复造轮子。
- 业务边界：仅补齐导入/模板能力，复用 `batch_save` 同一校验/入账路径，不改库存口径、事务边界、权限模型；不建任何新分支（仅 `main`）。
- 改动模块：
  - `app/routes/opening_stock.py`：新增 `GET /opening_stock/import/template`（openpyxl 生成含表头+示例行 xlsx，供批量导入使用）。
  - `app/routes/batch_import.py`：`/opening_stock/import` 由"重定向 stub"改为真实 Excel 导入——解析 xlsx → 复用 `batch_save` 同一校验/入账路径（`_apply_opening_stock_balance`），示例行/缺列/不存在仓/重复键/停用仓正确跳过，仓库必填报错（不静默默认仓回落，符合 AGENTS.md 仓库必填），补 `@require_role('warehouse')`（顺带修复 app.py:3446 点名的角色校验缺失）。
  - `app/templates/batch_import.html`：新增 opening_stock 导入卡片（含下载模板链接），接入既有 `.import-form` 集中式上传框架。
  - `app/templates/opening_stock.html`：「导入导出模板」按钮由提示改为 `/opening_stock/import/template` 真实下载；「导入」按钮指向 `/batch_import?type=opening_stock`；「粘贴导入」由 `prompt()` 单行改为多行 textarea modal（`pasteImportModal`）并经 `/opening_stock/batch_save` 统一入库；`saveDocument` 与粘贴导入均改走 `WMS.api`（消除原生 fetch）；`exportRows` CSV 加 BOM 修复 Excel 打开中文乱码。
  - `tests/test_opening_stock_import.py`：新增 5 项回归。
- 验证命令及结果：
  - `python3 scripts/lint_wms_rules.py --staged` → 0 违规（A1–A11）。
  - `python3 scripts/lint_no_raw_post_fetch.py` → 通过。
  - `pytest tests/test_opening_stock_import.py` → 5/5 PASS。
  - 功能冒烟（session 注入登录，参照既有 opening_stock 测试模式）：模板下载 xlsx 200、Excel 导入入账 100、示例行跳过、不存在仓跳过全 PASS。
  - `pytest tests/ -q` → **1727+5 passed, 84 skipped, 0 failed**。
- 推送验证：常规 HTTPS push 被拦，走 API 通道推送成功：远程 commit `412cee9d2f0795b532c064a1d959113443110fcf`，反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD 更新、7 个文件变更与预期一致（本地 `0755428` ↔ 远程 `412cee9`，内容一致）。
- 备注：模板 + 后端改动，**生产需重启 WMS 服务生效（R3）**。

### AI-CI-GREEN-001：WMS CI 存量红灯排查修复（2026-09-17 立项）

**背景**：用户发现 GitHub `WMS CI` 工作流全部红色。逐条核对运行日志得出：
- 推送前后失败完全一致：`8d578ba8`（推送前）与 `d4fcf0f6`（AI-MOB-RPT-F02 后端）均为 **51 failed + 124 errors + 1818 passed**，失败清单逐项相同 → 存量问题，与 RPT-F02 无关。
- 失败三群：①`test_p1_*_location_required`（7F，库位必填校验在全量套件中"失效"：期望拒绝实际保存成功）；②`test_print_*`（约 40F，登录/权限断言错乱：期望 302/403 实际 200）；③`TestOpeningStock*`（124E，setup 阶段 `FOREIGN KEY constraint failed`）。
- **污染实锤**：同样测试本地单跑/小组跑全部通过（`test_opening_stock_doc_list.py` 单跑 8/8、p1+print 组跑 26/26），只在 1900+ 测试同进程全量跑时失败 → 测试间共享状态（模块级环境变量 / app.config / DB 连接 / 登录态 / 系统设置开关）被前面的测试文件污染。
- 历史对照：09-12/09-13 期间全量本地跑仍接近全绿（1683P/0F）， breakage 为 09-15~09-16 引入。同类先例：BUG-2026-08-07-002（conftest 抢先导入修测试隔离）。
- 附带发现：`tests/verify_*.py` 不被主 pytest 收集（命名不匹配 `test_*.py`），靠 CI「Verify regression」分流步骤执行；但该步骤排在失败的「Unit tests + coverage」之后被跳过 → verify 文件在 WMS CI 红灯期间完全不执行（AI-MOB-RPT-F02 的新测试因此未在 WMS CI 跑到，仅靠本地 + WMS AI Verification 覆盖）。

**排查计划**：①本地全量复现（对齐 CI `pytest tests/ -q`）；②按字母序对三群失败做污染二分（候选污染区：test_a*~test_o* 段）；③逐群修复污染源（优先治本：污染文件自身收口状态）；④全量绿后观察 GitHub CI 转绿；⑤顺手评估「verify 分流步骤被前置失败跳过」的结构性问题（`if: always()` 或调整步骤顺序）。

**排查记录**：（进行中，随 atomic action 推进补充）

> 收口（2026-09-17）：001 定位的三群污染（test_p1_*_location_required / test_print_* / TestOpeningStock*）
> 已由提交 `05e936b3`（AI-CI-GREEN-001 本体）修复，主套件恢复全绿。此后 WMS CI 仍红，
> 但红点已从「Unit tests + coverage」前移到其**下游**的「Verify regression - verify_*.py」步骤，
> 属**另一批、另一类**问题，故拆分为 **AI-CI-GREEN-002** 独立立项排查，不混进本项。

### AI-CI-GREEN-002：WMS CI 第二批红灯清零（verify 分流步骤，2026-09-17 立项）

**背景**：用户看到 `WMS CI` 仍有多条红色运行，要求「请修复这些红色的」。逐条核对 GitHub
Actions 运行与 job 内 15 个步骤的 conclusion，得出精确落点：

- 失败并非全流程皆红，而是**只有第 12 步「Verify regression - verify_*.py」失败**；
  前 11 步（含 lint 双门禁、verify_wms_bugs、Unit tests + coverage、pip-audit、gitleaks）
  全部 ✅，第 13 步 Smoke test 因前置失败被 skip。
- 同一批运行里 `Android APK Build` ✅、`WMS AI Verification` ✅ —— 印证问题与产品代码无关。
- 覆盖 `ab0cdf8d` / `54dbd5e6` / `45cc8be3` 三次运行，红灯文件恒定 2 个，与 AI-MOB-RPT-F03 改动无因果关系。
- 日志下载受限：`/logs` 端点 302 到 `productionresultssa6.blob.core.windows.net`，该域名在沙箱内
  被 DNS 解析到保留地址 `198.18.0.33`（代理黑洞），TLS 直接 EOF，多种解析/端口探测均不可达。
  改用 **job steps API 精确定位失败步骤** + **本地 173 个 verify 文件全量复现**（对齐 CI 的分流逻辑与
  60s 超时），两条独立路径结论一致。

**本地复现（对齐 CI 分流）**：173 个 `tests/verify_*.py` 中失败 2 个 ——
`verify_app_py_split_batch_import.py`（2F）、`verify_voice_out_draft_ui.py`（顶层断言 1F，
被 pytest 收集时表现为 INTERNALERROR + exit 1）。

**根因（两处均为测试侧，产品代码零改动）**：

① `verify_app_py_split_batch_import.py` —— 断言未跟随架构演进
   - ARCH-OS-IMPORT 已把 `/opening_stock/import` 从「空 stub：重定向到 /batch_import」
     升级为**真实的 Excel 批量导入**（解析 xlsx → 复用 `_apply_opening_stock_balance`
     同一校验/入账路径，含 dry-run 预检两段式），endpoint 名随之由
     `opening_stock_import_stub` 变为 `opening_stock_import`。
   - 这是**正确的产品行为**，但用例 P4 仍按「一律 3xx 跳转 /batch_import」断言：
     `test_endpoints_registered` 找不到旧 endpoint 名而失败；
     `test_stub_routes_redirect` 对未上传文件的 POST 期望 3xx，实际拿到 400（api_error）而失败。
   - 与 AGENTS.md 中既有 F1~F9 属**同一类**（测试侧重未跟上产品/架构变更），
     不是新引入的缺陷。

② `verify_voice_out_draft_ui.py` —— 自相矛盾的脆弱断言（写入即坏）
   - T1c 断言字面量 `'voiceDraftViewModel = voiceDraftViewModel,'`，但 NavGraph 出于
     BUG-2026-09-14-032（语音 VM **惰性创建**、未登录不构造）必须写成
     `voiceDraftViewModel = viewModel(),` —— 该调用点**根本不存在同名局部变量**可供赋值。
   - 更关键：T1c 与同组 T1d（断言存在 `val voiceDraftViewModel: VoiceOutDraftViewModel = viewModel()`）
     **逻辑互斥** —— 有独立 val 才可能写 `= voiceDraftViewModel,`，而 T1c 又要求那个 val 不存在，
     两条**在任何版本都不可能同时通过**。经 `git log -L` 追溯，该矛盾自本文件引入
     （`ebf2e04`，2026-09-16 10:42）起就存在，从未通过 —— 是一颗被 `known_failures`
     机制长期掩盖的哑弹，而非回归。
   - 顺带发现 T5d 内嵌 `'最后' not in dl` 亦为**条件恒真**空断言（中文词恰不在该 Kotlin 源码中），
     既无正向契约、又会让后续实现者误以为该词是禁用语。最坏后果是**红灯被误读成实现缺陷**。

**修复（1 个 atomic action）**：
- `tests/verify_app_py_split_batch_import.py`：把「三个模块一律当空 stub」改为
  **按每个入口各自的正确契约分流断言** —— 仍是空 stub 的 user/label_template 断言 3xx 跳转
  `/batch_import`；已实现真实导入的 opening_stock 断言 400 + JSON + 文案含「文件」。
  并新增 `test_real_import_routes_report_error_instead_of_redirect`，钉死
  「真实导入接口不许以 3xx 伪装成一次成功导航」—— 这条比原断言**守卫更强**，
  没有采用「把失败的 URL 从清单里删掉」的偷懒做法（删掉等于放弃对该端点的守卫）。
- `tests/verify_voice_out_draft_ui.py`：T1c 改为正则，**同时接受**两种合法传参形态
  （`voiceDraftViewModel = voiceDraftViewModel,` 与 `= viewModel()`），
  不再把实现细节（用不用独立 val）当作契约；删除 T5d 的恒真空断言；
  **新增 T12 断言健壮性守卫**把本次两条教训固化成可执行断言：
   - T12a 禁止同一标识符出现「互斥对」断言（防再写一次 T1c/T1d 式矛盾）；
   - T12b 禁止纯中文否定式恒真断言（防再写一次 T5d 式空断言）。
   T12 只扫**可执行条件表达式**、剔除注释与失败提示文案（否则守卫会被自己的错误输出触发），
  且已用**注入反例**反向验证：注入 T1c 旧形态与 `'最后' not in dl` 后 T12a/T12b 双双变红，
   还原后 53/53 全绿 —— 证明守卫不是恒真装饰。
- `scripts/_routes.json`：同步该 endpoint 名（**1 行**改动；注意必须走文本替换，
  用 `json.dumps` 整体重写会把整个文件缩进格式改掉，产生 4553 行伪 diff）。

**验证**：
| 检查项 | 修前 | 修后 |
| --- | --- | --- |
| `verify_voice_out_draft_ui.py` | 50 通过 / 1 失败 | **53 通过 / 0 失败** |
| `verify_app_py_split_batch_import.py` | 6 通过 / 2 失败 | **9 通过 / 0 失败** |
| 主套件 `pytest tests/` | — | **1998 passed / 85 skipped / 0 failed** |
| lint A1–A11 | 0 违规 | 0 违规 |
| 禁止裸调非 GET fetch | 通过 | 通过 |
| verify_wms_bugs 静态回归 | 通过 | 通过 |
| 全量 `tests/verify_*.py`（173 文件，对齐 CI 分流） | 失败 2 文件 | **失败 0 文件** |

**生效条件**：无产品代码改动，**无需重启 WMS 服务、无需重新出包 APK**；
仅需推送 main 后 CI 重新运行即验证转绿。

**教训（可复用）**：
1. 断言要断「契约」而不是「写法」——写死 `x = x,` 这类实现细节，实现一换写法测试就假红；
   正反两种合法形态都应接受。
2. 引入新断言时先自问「这条在**当前**代码上会过吗」——T1c/T1d 互斥说明当时没有实跑就提交；
   本批已用 T12 系列把这类问题挡在合入前。
3. CI 红灯定位优先用 **job steps API**（`/actions/runs/<id>/jobs`）拿到失败步骤号，
   比拉完整日志更快且不受产物域名可达性影响。

### UI-EMPTY-STATE-2026-09-20：委外三页主列表空态（完善计划 P1-3，2026-09-20 立项）

**背景**：`WMS完善现有功能开发计划.md` §3 P1-3 记录「空数据页只剩表头，分不清加载失败还是真没数据」，
列为影响日常实用第 1 位。扫描 `app/templates` 全部 `<tbody>{% for %}` 块，命中 15 处缺空态，
其中属**服务端渲染主列表**且确实裸奔的先取委外三页（委外是本阶段正在动的模块，改动面最小、风险最低）。

**改动**（仅模板，不动逻辑）：
| 文件 | colspan | 空态文案 |
| --- | --- | --- |
| `app/templates/subcontract.html` | 12 | 暂无委外加工单，点击「新增委外加工单」开始创建 |
| `app/templates/subcontract_issue.html` | 9 | 暂无委外发料单 |
| `app/templates/subcontract_receive.html` | 11 | 暂无委外收货单 |

colspan 由脚本**数 `thead` 里 `<th>` 实测得出**，不是照抄上一版——写错会在非空态列位产生断行。

**回归锁**：新增 `tests/test_p1_3_subcontract_list_empty_state.py`（10 项，A9 要求）：
T1 空态分支与文案存在；T2 colspan == 自动清点的 `<th>` 数；T3 Jinja 独立环境渲染：
列表空 → 渲染空态、列表非空 → 不渲染；T4 反回归——文案必须出现在**模板源码**里（防止以后改成 JS 注入后
静态锁失效）。Jinja 裸 `Environment` 需自行 stub `url_for` / `csrf_token` / `get_flashed_messages`
三个全局量，否则渲染报 `UndefinedError`（首跑 3 红即此因）。

**验证**：
| 检查项 | 结果 |
| --- | --- |
| `pytest tests/test_p1_3_subcontract_list_empty_state.py` | 10 passed |
| 委外相关既有测试（29 项） | 全过 |
| `scripts/lint_wms_rules.py` | 0 违规 |
| 禁止裸调非 GET fetch | 通过 |

**生效条件（R3）**：改的是 Jinja 模板，Flask 非 debug 下模板缓存不会自动失效，
**必须重启 WMS 服务才看得到空态**；无需重新出包 APK（手机端不涉及这三个页面）。

**教训（可复用）**：
1. **GitHub MCP `get_file_contents` 返回的 sha 是「行尾归一化后」算的**——CRLF 文件的远端 sha 与本地
   `git rev-parse HEAD:<path>` 恒不等。推送校验不能只比 sha，否则 CRLF 模板会**永久误报 MISMATCH**。
   必须回退到**逐字节内容比对**（拉 `raw.githubusercontent.com` 原始字节）；且该域名在受限网络下
   SSL 常 `UNEXPECTED_EOF`，单次失败不等于不一致，**要重试**（本轮 4 次重试后 4/4 OK）。
2. 空态 colspan 必须实测 `<th>` 数，目测会错。

**遗留子项**（不在本 atomic action）：`document_ocr.html`、`batch_import.html`、`sales_report.html`、
`ai_feedback_review.html`、`document_table_form.html`、`_list_macros.html`。
`warehouse.html` / `in_order_push.html` 经复核属 JS 渲染结果表或已有空态，不在本批。


### UI-EMPTY-STATE-2026-09-20-B2：7 处列表空态补齐（完善计划 P1-3 第 2 批，2026-09-20 立项）

**背景**：第 1 批（委外三页）落地后，我给出的「剩余 6 个页面」清单是**错的**——扫描判据只认
`{% for %}` 块内的 `{% else %}`，把已有空态的页面误判成缺口。用修正判据全仓重扫后得到真缺口 7 处。

**⚠️ 判据教训（本次核心）**：空态至少有三种合法写法，只认一种必然误报：
1. `{% for %}…{% else %}`（第 1 批用的写法）
2. `{% if 集合 %}` 包住**整张表** + `{% else %}` —— else 在 `<table>` **外面**，只看 `<table>…</tbody>` 会漏判
3. `{% endfor %}` 之后补 `{% if not 集合 %}` 空行

另有两类假阳性：`<tbody>` 里的 for 可能是 `<select><option>`（弹窗表单，不是列表）；
`pagination.iter_pages` 分页控件不需要空态。
**结构性扫描要"宁漏勿错"，且必须抽样打开源码复核后再下结论。**（同类错误已犯两次：
BUG-2026-09-20-007 把确定性缺陷误判成顺序污染；本次把已有空态误判成缺口。）

**改动**（7 处，仅模板，不动业务逻辑）：
| 文件 | colspan | 处理 |
| --- | --- | --- |
| `print_in.html` / `print_out.html` | 9 | 明细 for 加 `{% else %}`「无明细行」 |
| `print_in_with_excel.html` / `print_out_with_excel.html` | 9 | 同上；**并把补 8 行空白的填充循环用 `{% if order.items %}` 包住**（否则空态行后跟 8 行空格） |
| `print_in_with_html.html` | 8 | 「无明细行」 |
| `sales_report.html` | 11 | 原 `{% if drill_material_code and drill_items %}` 使空数据**整块消失**（点了钻取没反应）→ 放宽为 `{% if drill_material_code %}` + for-else |
| `document_table_form.html` | 5 | `{% if batch_meta.scans %}` → `{% if batch_meta.scans is defined %}`（否则 `{% else %}` 永远渲染不到）+ for-else |

**回归锁**：`tests/test_p1_3_remaining_list_empty_state.py` 30 项：
7 处 × {for 块有 `{% else %}` / 文案在块内 / **colspan == 实测 thead `<th>` 数**}
+ 2 个 excel 变体的「空态时不得再补空白行」+ 7 处渲染验证（空集合出空态、非空不出）。
- **T5 首跑 7 红**：整模板渲染要 `config` / `template` / `order.total_amount` 等一堆 Flask 上下文，
  补桩越补越脆 → 改为**只截取 `<table>…</tbody>` 片段渲染**，30 全过且更精准。

**验证**：新测试 30 passed；受影响既有测试（print/sales/check/opening_stock/document_table/subcontract）
585 项无 F/E；`lint_wms_rules.py` 0 违规。

**生效条件（R3）**：改 Jinja 模板，非 debug 下模板缓存不失效 → **必须重启 WMS 服务**；无需重新出包 APK。

**真·遗留**：`batch_import.html`、`document_ocr.html` —— 列表由 JS 渲染，需改 JS 而非 Jinja，不在本批。


### UI-EMPTY-STATE-2026-09-20-B3：JS 渲染列表空态 2 处（完善计划 P1-3 收口，2026-09-20 立项）

**背景**：P1-3 前两批都用 Jinja 空态解决，剩余 2 处列表是 **JS 拼 HTML** 渲染的
（`batch_import.html` 的预检结果表、`document_ocr.html` 的识别结果表），加不了 `{% else %}`，
只能在 JS 分支里补。这是 P1-3 的收口批次。

**改动**（2 处，仅模板内 JS，不动接口与业务逻辑）：
| 文件 | 处理 |
| --- | --- |
| `batch_import.html` | `renderOpeningStockPreview()` 里 `rows.forEach` 之前加 `if (!rows.length)`，向 `tbl` 拼一行 colspan=7 空态「预检结果为空：文件里没有解析到任何数据行」。刻意**不重排 forEach 缩进**，最小侵入。 |
| `document_ocr.html` | `renderResult()` 给 `if (res.items && res.items.length > 0)` 补 `else if (res.items)` 分支，输出 alert「未识别到物料明细行，请检查图片清晰度，或改用手工录入。」 |

**设计取舍（可复用）**：
- `document_ocr` 用 `else if (res.items)` 而**不是**独立的 `if (!res.items.length)`：
  `res.items` 为 undefined（错误/异常响应）时后者会误报「未识别到物料明细行」，掩盖真实错误。
  已用回归锁 T2 钉死「必须是同一 if 的 else」。
- `batch_import` 原本 rows 为空时除裸表头外还有一句 foot「没有可导入的行」，但表体仍是空白，
  正是 P1-3 要治的症状；故补表体空态，foot 保留。

**回归锁**：`tests/test_p1_3_js_list_empty_state.py` 12 项。
pytest 里没有 JS 引擎，**锁结构与口径而非运行时渲染**：
守卫存在 / 空态行确实拼进表格体变量 `tbl`（不是别处 alert）/ **colspan == 同一段 JS 里 thead 实测的 `<th>` 数** /
文案在分支内 / 原有「整份结果为空」兜底未被顶掉 / 文案必须在模板源码里。
刻意不断言实现细节（不关心用 if 还是三元），只锁「空集合必须有可见空态」这个契约。

**验证**：新测试 12 passed；`test_lint_wms_rules_a14_golden.py` 带 PATH 单独跑 6 passed
（不带 PATH 时 setup 抛 `FileNotFoundError`——本机 PATH 缺 git 的老问题，与本次改动无关，不要误判为回归）；
受影响既有测试 277 项除上述 3 个环境 error 外无 F；lint 0 违规。

**生效条件（R3）**：模板改动，**必须重启 WMS 服务**才生效；JS 在浏览器端执行，无需重新出包 APK。

**P1-3 状态：全仓清零**（第 1 批 3 + 第 2 批 7 + 第 3 批 2 = 12 处）。

---

## UI-FORM-REQUIRED-2026-09-20-B1 —— P1-2 采购订单新建表单必填校验

**症状**：`purchase_order_add.html` 保存时逐条 `showToast` + 立刻 `return`，只报第一条错误，
用户改完再点才知道还有下一条。

**⚠️ 计划文档原描述有误**：原文称 4 个页面「全页 required=0，提交后靠 JS alert() 一次性报错」。
实测这四个页面**一个 `alert(` 都没有**，且 `sales_order_add` / `sales_order_edit` 早已具备
`save()` 包装 + `showValidation(messages)` 的「一次收集全部」机制。真缺口只有采购订单与售后出库单两页。

**关键认知（反直觉，务必记住）**：这些页面的保存按钮都是 `type="button"`，`<form>` **从不原生提交**，
所以模板上的 `required` 属性自己不会拦人。只加 `required` 不配套 JS = 假必填。

**改动**（`purchase_order_add.html`）：
- 采购日期 / 供应商加 `required`；明细行数量 `min` 由 `0` 改 `0.01`（单价保持 `min="0"`，赠品可为 0）
- `submitForm` 由逐条早退改为 `collectPurchaseValidationErrors()` → `showPurchaseValidation()` → `if (errors.length) return`
- 新增 `#purchaseOrderValidationPanel` 面板 + 一次性高亮 `wms-row-error` / `wms-cell-error`
- 表头校验直接扫 `#purchaseOrderForm [required]`，label 取自 `.form-label`，`SELECT` 用「请选择」、其余用「请填写」
- 未填物料编码的空白行跳过校验（页面预置 30 行空白行）

**回归锁**：`tests/test_p1_2_purchase_order_validation.py` 15 项。
锁结构与口径：required 存在 / qty min=0.01 而 price min=0 / 面板默认 `display:none` 且 `.show` 才 `display:block` /
旧早退分支已消失 / **收集 → 展示 → 再发请求** 的顺序 / 行级错误必须带 `rowIndex` + `selector` + 行号 /
展示前必须清空上次高亮 / 空白行不校验 / Jinja 仍可编译。

**验证**：新测试 15 passed；lint 4 项 + 采购关联 34 项全过；预提交钩子 0 违规。
本地 `3948923`，远端 `1cbd7d5`，三工作流全绿。

---

## UI-FORM-REQUIRED-2026-09-20-B2 —— P1-2 售后出库单新建表单必填校验

**症状（比采购单更严重）**：`after_sale_out_add.html` 把 `return` 写在明细行 `for` 循环**内部**——
第 1 行数量为空就直接退出，后面 29 行根本不检查。同时仓库的 `required` 有 JS 校验、库位的 `required`
却没有，红色星号形同虚设（后端 `BUG-2026-08-16-014` 会拒，但要等一次往返才知道）。

**改动**（`after_sale_out_add.html`）：
- 一次遍历 `collectAfterSaleOutRows()` 同时产出 `items` 与全部行级错误，不再循环内 return
- 日期 / 客户名称加 `required`；数量 `min` 0 → 0.01
- 表头校验扫 `#addForm [required]` → 仓库与库位都真的拦得住
  （库位在 `{% if location_management_enabled %}` 内，未开启时不渲染，与后端口径一致）
- label 提取时 `.replace('*', '')`，避免「请选择仓库 *」这种带星号的文案

**回归锁**：`tests/test_p1_2_after_sale_out_validation.py` 17 项。
除同批次的通用项外，额外钉死两块：
- **`collectAfterSaleOutRows` 里不得出现 `showToast`，且遍历内只允许「跳过空白行」的 `return`**——
  这条是本次最关键修复的回归锁，防止以后又有人在循环里 early return。
- 库位必须仍受 `location_management_enabled` 开关控制（位置在其分支之后）。

**验证**：新测试 17 passed（连同批 1 共 32 passed）；预提交钩子 0 违规。
本地 `2dc5fc4`，远端 `f1f5ee9`。

**生效条件（R3）**：改的是 Jinja 模板，**必须重启 WMS 服务**才生效。

**P1-2 状态**：本批完成采购订单 + 售后出库单两页。
`sales_order_add` / `sales_order_edit` 已有「一次收集」框架，仅校验项偏少（客户 + 至少一条明细），
留待后续按需扩充。

---

## FORM-WAREHOUSE-REQUIRED-2026-09-20 —— P1-1 入库单下推来源单仓库必填

**⚠️ 第 4 次踩同一个坑：P1-1 计划里的 4 条「缺口」源码核实后全部过时或不实**——
委外发料/收料（前端 required + 默认 selected + 后端 active 校验）、期初（AI-OS-MW-001）、
调拨（原生 submit 校验生效 + 后端拒同仓）都早已被更早批次修完或本就是刻意设计。

**唯一真缺口**：`create_in_order_push` 下推目标草稿直接 `warehouse=order.warehouse` 继承，
来源单无仓库时写出**空仓库死单草稿**（目标单完成时仓库必填，永远无法完成，只能删了重建）。

**修复**（双管齐下）：
- 后端 `app/routes/in_order.py`：锁定源单后即校验 `order.warehouse` 非空，否则 400 拒绝，
  提示「来源入库单未指定仓库，无法下推；请先在来源单补充仓库归属」——不允许静默写空仓库；
- 前端 `app/templates/in_order_push.html`：`{% if not order.warehouse %}` 时顶部 alert-warning 提示
  并给「创建目标草稿」按钮加 `disabled`。

**回归锁**：`tests/test_p1_1_in_order_push_warehouse_required.py` 4 项——
T1 无仓库 POST 下推 400 且 msg 含「仓库」；T2 有仓库控制组必须成功（证明不是误拦）；
T3 无仓库时页面渲染警示条 + 按钮 disabled；T4 有仓库时无警示 + 按钮可用。

**验证**：新测试 4 passed；下推/入库关联 29 项全过；预提交钩子 0 违规。
本地 `589ea7d`，远端 `1f198e0`。

**生效条件（R3）**：模板改动需重启 WMS 服务生效；后端改动同样需要重启进程。

**P1-1 状态：清零**（4 条描述 3 条早已完成、1 条刻意设计，真缺口 1 条已修）。
下一批候选：P1-4（fetch 统一层）、P0-1/P0-2/P0-3。

---

## P1-7 采购退货出库 —— 全量实现（2026-09-20）

**来源**：整改方案 `WMS_BUSINESS_AI_REMEDIATION_PLAN.md` §P1-7（`:492`）。方案原文结论是
「**类不存在，但开关已存在**」——`purchase_return_requires_order`（默认 `1`）在配置页写着
"为后续采购退货流程预留"，是**半成品而非零起点**。方案明确要求「**与 P1-5 保持同构，降低理解成本**」，
并建议 P1-5 验收通过后再做、复用其测试骨架。本项即按此执行。

**P1-5 前置确认**：销售退货入库（P1-5）已先行完成，P1-7 严格镜像其实现模式——
3 个模型列 + 3 个业务函数 + 模板 `party_label`/`party_field` 机制 + `type` 别名映射 +
单头聚合 + 冗余单号。

### 拆分为 3 个 atomic action

| # | 范围 | 提交 | 状态 |
|---|---|---|---|
| A1 | 模型列 `source_in_order_id`/`source_in_order_no`/`source_in_order_item_id` + 静态 ALTER 与启动期 `ensure_purchase_return_source_columns` 幂等兜底 | 远端 `4d756f5`（本地 `876ff62`，见下方 SHA 勘误） | 已提交（2026-09-20T12:57Z） |
| A2 | 业务逻辑 + 前端模板/页面 + 18 项回归测试 | 远端 `2c272b0`（本地 `d6fcb20`，见下方 SHA 勘误） | 已提交（2026-09-20T23:02Z） |
| A3 | 台账登记收尾（本文件 + `WMS_BUG_BASELINE.md`） | 本地 `0d2cb7f` / 远端 `97cc34d` | **已提交（2026-10-02）** |

### 验证

```bash
WMS_ALLOW_INSECURE_COOKIE=1 python -m pytest tests/verify_purchase_return_outbound.py -q
```

**18 passed**，覆盖：

| 用例 | 内容 |
|---|---|
| T1 | 三账一致：总账余额 12 / 本单流水增量 −8 / 库位账余额 12 |
| T2 | `stock_transaction.warehouse_id` 正确归属（不得为 NULL） |
| T3 | 保存期超退拒绝 |
| T4 | 一张来源入库单多行退货，各行独立计限 |
| T5 | 完成期真闸（两草稿并发窗口，后完成者被拒） |
| T6 | 重复完成幂等 |
| T7 / T8a / T8b | 开关关闭允许无来源 / 开启拒绝无来源 / 退货供应商必填 |
| T9 | 非采购退货单不得挂来源 |
| T10 | 列表别名与列头 |
| T11 | 新增页按模式渲染 |
| T12 | AI 不参与（无草稿） |
| T13 | 选源接口口径 |
| T14 | 编辑草稿保留行级来源 |

**全量回归**：`tests/verify_*.py` **174 文件 0 失败**（197.5s）；
主套件 **2403 passed / 86 skipped / 0 failed**；
`lint_wms_rules.py` 全量与 `--staged` 均 **0 违规**；
`lint_no_raw_post_fetch.py` 通过；`check_in_order_imports` 39 函数全覆盖；
R6 守卫 `tests/test_r6_startup_migration_column_guard.py` 3 passed。

**生效条件（R3）**：含 Jinja 模板与 `app.py` 改动，**生产需重启 WMS 服务生效**。
数据库列由启动期 `ensure_purchase_return_source_columns` 自动补齐，**无需手工执行迁移**。

**台账**：`WMS_BUG_BASELINE.md` 已登记 **BUG-2026-09-20-014**。

**整改方案状态**：P1-5（销售退货入库）+ **P1-7（采购退货出库）已完成** ——
整改方案 §P1 系列的**最后一项功能缺口清零**。

---

#### A3-1 提交号勘误（重要）

台账原记 A1=`876ff62`、A2=`d6fcb20`——这两个是**本地 SHA**，按 §8.1.3 API 通道推送后
远端产生了新的不同的 commit SHA，本地号在 GitHub 上**不可解析**
（`GET /repos/SIX2090/wms/commits/876ff62` → `No commit found for SHA`）。
后果：台账里的哈希指向不了任何可被审阅的提交，追溯链断掉。已补真值：

| atomic | 本地 SHA（旧记） | **远端 SHA（真值）** | 推送时间 | 变更文件 |
|---|---|---|---|---|
| A1 | `876ff62` | **`4d756f5`** | 2026-09-20T12:57Z | `app/app.py` +121、`app/fix_db_columns.py` +25、`app/models/documents.py` +8、`fix_p17_columns.py`（新增 +108）、`tests/test_ensure_purchase_return_source_columns.py`（新增 +183）、`tests/test_fix_db_columns.py` +80 |
| A2 | `d6fcb20` | **`2c272b0`** | 2026-09-20T23:02Z | `app/app.py` +91、`app/routes/in_order.py` +84、`app/routes/out_order.py` +144/-14、`app/templates/out_order*.html` ×3、`tests/verify_purchase_return_outbound.py`（新增 +733） |

**约定**：本节往后登记一律写「本地 ↔ 远端」双号，凡走 API 通道推送的提交必须反查
`GET /repos/SIX2090/wms/commits/<sha>` 确认可解析后再落账。

> 2026-10-02 补：本条规则首先适用于本任务自身——A3 通过后按 §8.1.4 核对
> 远端 HEAD `97cc34d`（parent `a4a1a3a`，2 文件变更）并 `git reset --hard origin/main`
> 对齐，随后单独提交把双号回填本行。

## P2-3 批 5 —— mobile / native_api 收敛 + 委外快速收货补漏（2026-09-25）

**来源**：P2-3「库存三账写入单点收敛」剩余写入点。前置批 1–4 已收敛
（in_order / out_order / after_sale_out / subcontract 等），本批处理侦察列出的
最后一批：`mobile.py` 4 处、`native_api.py` 2 处、`app.py` 1 处，共 **7 个写入点**。

### 核心发现：R6 排查自身有盲区（024-09-20-008 的结论不完备）

BUG-2026-09-20-008 的 R6 排查结论原文写「23 个调用点已全量分类，除本处外
**22 处均已双写**（… subcontract_receive …），**无第二处缺口**」。
**该结论是错的**：它把 `routes/subcontract.py` 的网页版当成了全部实现，
**漏掉了 `app/app.py` 里那套更老的 API**。

| 实现 | 路由 | 状态 |
|---|---|---|
| 网页版 | `routes/subcontract.py::quick_receive_subcontract` | batch 4 已收敛 ✅ |
| **老 API** | **`app/app.py::api_subcontract_quick_receive`** | **仅 `add_stock` 写①总账+③流水，从不写②库位账** ❌ |

这与 008 是**同型、同根因**（静默账实分裂：①减②不变、无任何报错），
只是发生在**收货方向**、且藏在**双轨实现的另一套**里。
本批按 008 的修法补上。

### 验证

```bash
WMS_ALLOW_INSECURE_COOKIE=1 python -m pytest tests/test_p2_3_mobile_native_receive_apply_stock_delta.py -q  # 11 passed
WMS_ALLOW_INSECURE_COOKIE=1 python -m pytest tests/ -q                                                      # 2675 passed / 86 skipped / 0 failed
python scripts/verify_wms_bugs.py                                                                            # rc=0
python scripts/lint_wms_rules.py --staged                                                                    # 0 违规
```

**生效条件（R3）**：改动含 `app.py` 与路由逻辑，**生产需重启 WMS 服务生效**。

**台账**：`WMS_BUG_BASELINE.md` 已登记 **BUG-2026-09-25-001**（委外快速收货漏写库位账）。

**P2-3 状态**：写入点收敛 **7/8 完成**；`requisition.py` 1 处待单独评估。

