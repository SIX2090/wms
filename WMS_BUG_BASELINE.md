# WMS BUG 基线

更新时间：2026-10-03（持续滚动更新；BUG 条目 427 条：2026-07 共 42 条，2026-08 共 220 条，2026-09 共 165 条，最新 BUG-2026-09-30-002；另含非 BUG 条目：LABEL-FIX-2026-09-29-001~005、FEAT-2026-09-22-001、FEAT-2026-09-24-001、FEAT-2026-10-03-001、WECOM-BOT-001、INV-AUDIT/VULN/CONF 系列等）

用途：把已经核验过的问题固定下来，避免不同 AI 模型每天重复报告同一批“疑似 BUG”。后续扫描结果必须先对照本文件：已修复项看回归，误报项不重复报，暂缓项只在风险条件变化时重新评估。新 BUG 登记前先 grep 本文件查同根因历史（AGENTS.md 防反复规则 R6），同模式复发必须同时修复全部同类消费点。

| BUG-2026-09-13-012 | [P1] Windows 下 SQLite 相对路径返回反斜杠，导致迁移路径与测试/部署路径语义不一致 | 已修复（2026-09-13）：_resolve_sqlite_db_path 对相对路径规范化并统一返回正斜杠，避免 Windows 路径比较和跨平台迁移失败。R6：已 grep 路径解析与数据库迁移消费点，未发现同类未修复实现。验证：tests/test_auto_migrate_db_path.py 5 passed，静态门禁通过。 |

| BUG-2026-09-13-013 | [P2] Windows 启动回归及验证脚本子进程编码不一致，readerthread 解码失败使 stdout=None | 已修复并验证（2026-09-13）：7 个启动回归与 scripts/verify_wms_bugs.py 的 19 个 Python 子进程调用明确设置子进程 PYTHONIOENCODING=utf-8、父进程 encoding=utf-8，保留严格解码和原有数据库/日志断言。R6：同类点已排查；与 BUG-2026-08-07-002 的导入隔离根因不同。专项 pytest 29 passed；verify_wms_bugs.py exit=0 且无 UnicodeDecodeError/readerthread；两项静态门禁通过。仅修测试验证链路，不改生产启动或业务数据。 |

| BUG-2026-09-13-014 | [P2] 图片回归测试未关闭静态响应，Windows 删除失败；固定迁移文件名被旧运行污染 | 已修复并验证（2026-09-13）：两项测试使用 tmp_path 独立静态/上传/旧图目录，monkeypatch 恢复配置与工作目录；通过响应上下文关闭文件句柄，再执行原有删除清理。保留默认上传根目录、HTTP 200、PNG 类型和逐字节内容断言；迁移加强为首次精确复制 1 个、再次复制 0 个。R6：同类点已排查该文件两处静态响应和迁移实现；不修改生产上传/迁移逻辑，不删除旧运行或生产图片。专项连续两轮各 2 passed；全量 pytest tests -q --tb=short --disable-warnings：1632 passed、85 skipped、1934 warnings、0 failed（251 秒）。 |

| BUG-2026-09-13-015 | [P1] 销售看板与异常页仍按全局库存判断缺货，其他仓有货掩盖本仓不足 | 已修复并验证（2026-09-13）：两个页面通过共享 _sales_analysis_stock 按仓库 ID 优先、历史名称/编码兼容解析，使用 get_warehouse_stock_quantities；按请求缓存同仓库存，不回退全局或默认仓。无效/空/停用仓库明确在页面提示库存待人工确认，不伪造缺货结论。R6：与 BUG-2026-09-13-010 同根因的非 AI 页面遗漏；sales.py 全部库存读取点已排查，剩余下推两处原已使用仓库口径，现无 material.stock 裸用。新增测试 tests/test_bug_2026_09_13_015_sales_page_stock.py：初始 8 项失败，修复扩充后 13 passed，覆盖双仓隔离、ID 优先、历史编码流水、部分发货余量、无效/停用仓库、缓存、真实模板渲染及只读不改库存。全量 pytest tests -q --tb=short --disable-warnings：1645 passed、85 skipped、1934 warnings、0 failed；verify_wms_bugs.py 与双静态门禁通过。未运行会创建业务记录的 full_smoke_test.py，使用隔离数据库真实页面 GET 渲染回归替代。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-016 | [P1] 批量出库漏停用仓库校验、缺失物料触发异常，单张/批量未统一累计需求预检 | 已修复并验证（2026-09-13）：共享 _out_order_stock_error，单张及批量写锁内解析有效启用仓库、拒绝不存在物料及非正数量、累计同物料需求后按仓库库存预检；删除批量全局库存读取，保留逐项原子扣减及整单回滚。R6：复查 BUG-2026-08-16-004/021 与 BUG-2026-09-13-002，同类点已排查两完成入口。初始 3 failed/2 passed，扩充后专项 8 passed；覆盖停用仓、历史编码库存、重复明细、重复完成、坏单后继续好单、模拟第二次扣减失败整单回滚。全量 pytest tests -q --tb=short --disable-warnings：1653 passed、85 skipped、0 failed（257 秒）。不执行生产单据，使用隔离 SQLite 路由回归替代写生产的 smoke 脚本。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-017 | [P1] 盘点单行新增无效仓库回退全局库存，漏区域/冻结与写锁边界 | 已修复并验证（2026-09-13）：写锁内重检状态及物料，空单可用默认仓，空仓历史已有明细/冻结时拒绝擅自归属；仓库必须有效启用，按仓库库存取账面，保存 area/location，启用库位时区域必填，按物料+区域判重并首次设置 frozen_at。R6：对照 BUG-2026-09-13-003/004 和 BUG-2026-09-02-004，表格保存/导入/单行更新已检查，补齐单行新增消费点。初始 7 failed；新增 9 项回归覆盖双仓历史编码、默认仓、停用/无效仓、分区重复、库位必填、冻结不漂移、写锁状态变更、旧空仓有明细拒绝归属；全量 pytest tests -q --tb=short --disable-warnings：1662 passed、85 skipped、0 failed（264 秒）。隔离 SQLite HTTP 回归替代生产写入 smoke，未操作生产单据。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-018 | [P2] 手机扫码累加缺少明确数量反馈、移除按钮直接删除且按列表索引操作 | 源码已修改，Android 编译/真机验收待完成（2026-09-13）：addScanLine 独立 scanFeedback 回显本次与累计数量，页面及相机弹窗可见、不借用提交成功状态；删除增加编码/名称/规格/区域/数量确认，按物料+区域重新定位并复核数量，提交期间禁加行/删除。R6：三类扫码页共用基类和 ViewModel；保留盘点替换确认、900ms 节流、原声音震动及开关；期初独立页面不改，多单位明确不做。新增 3 项源码接线测试先红后绿，与既有物料回显共 8 passed；全量 Python pytest 1683 passed、85 skipped、0 failed，不代表 Kotlin 编译通过。gradlew.bat --offline :app:compileDebugKotlin 实际失败：JAVA_HOME 未设置且找不到 java；本机未发现 Android SDK，未生成 APK，未做真机测试，不能标记上线完成。验收需重新构建安装 APK，检查取消/确认删除、数量变更拒绝误删、连续重复扫描与盘点替换，手机库存预检/草稿恢复/库位/单据附件另批推进。 |

| BUG-2026-09-13-019 | [P1] Android 出库提交前按全局库存逐行预检，未累计同物料需求 | 后端已验证，App 源码已接入、编译/真机验收待完成（2026-09-13）：对照 BUG-2026-09-13-016、BUG-2026-09-03-004，同根因的新消费点 native_api_outbound；最终原子扣减已有防护，不能据此断言可超发。新增 Bearer 角色保护、pydantic 校验的只读 /api/outbound/preflight；共享仓库级累计预检供实际提交复核，提示本仓可用量与本次累计量。保留最终扣减、负库存配置和离线幂等；预检业务拒绝不入离线队列，网络失败沿用暂存。库位明细校验仍由最终扣减兜底，下一批库位选择收口；多单位不改。R6：同类点已排查 Web 单张/批量、Android 展示与提交。新增测试初始 8 failed，扩充后专项及部门/合同/网页联动 36 passed；全量 pytest tests -q --tb=short --disable-warnings：1694 passed、85 skipped、0 failed；lint_wms_rules --staged 0 违规。只读测试确认不新建单据/流水/幂等记录，覆盖历史空 ID 编码库存、双仓隔离、累计需求、停用仓、负库存策略、认证与非法输入。本机缺 Java/Android SDK，未构建安装 APK；后端服务重启后接口生效，App 需构建发版。 |

| BUG-2026-09-13-020 | [P1] 手机入出库未提交清单仅在内存，杀进程丢失 | 源码已修改，Android 编译/真机验收待完成（2026-09-13）：与 BUG-2026-09-03-003 断点续盘不同，离线队列只保存已点击提交的作业。新增 DataStore 编辑草稿，服务器+账号+作业类型隔离，恢复清单/名称规格品牌/仓库/部门/领料人/合同；StateFlow 监听、Mutex 串行保存，删空删除草稿，保存失败常驻提示。提交前落盘幂等键，进程中断恢复后禁止修改原请求，只允许复用原键核实；出库核实不重复执行只读预检，以免已成功扣库后预检不足阻碍幂等回放。业务明确拒绝允许修改，认证/服务端异常保留原键；成功或离线确实入队后清空。R6：同类点已排查入出库与既有盘点恢复，保留盘点专用实现，不改多单位。新增 3 项源码接线测试先红后绿，关联 17 passed；全量 Python 1697 passed、85 skipped、0 failed；后续保护调整专项仍 17 passed。实际 gradlew.bat --offline :app:compileDebugKotlin 因无 JAVA_HOME/java 失败，Python 测试不代表 Android 编译或杀进程验收通过。需在具备 SDK 的环境构建，真机验证杀进程恢复、换账号/服务器隔离、删空不复活、弱网入队与提交中断原键核实后再上线。 |

| BUG-2026-09-13-021 | [P1] Android 入出库扫码行没有库位选择，启用库位管理时只能提交空库位 | 源码已修改，Android 编译/真机验收待完成（2026-09-13）：对照仓库/库位必填规则与 native_api_outbound/native_api_inbound 最终校验；出库页新增库位编码输入并写入每个扫码/手工行，提交沿用后端库位必填拒绝。当前输入支持手工编码/粘贴库位标签文本，尚未实现独立库位列表/扫码库位标签解析，下一阶段可增强。多单位不改。R6：复查入库、出库、盘点，盘点已有区域字段；新增源码接线测试。 |

| BUG-2026-09-13-022 | [P0] 手机按行写库位但未保存单据表头库位，后续反提交无法准确定位；关闭库位时入库仍写隐藏库位账 | 已修复并验证（2026-09-13）：R6 排查入出库两路，Web 单据反提交采用 order.location；现有单据仅支持单个表头库位，因此移动端一单强制同库位并持久化，跨库位必须分单，不伪装支持多库位单据。关闭库位管理时忽略来端库位且不写 LocationInventory；库位预检按所选仓库+库位累计，不拿其他库位余额兜底。历史已完成单据不自动修改，旧空表头归属待人工核对。新增隔离数据库测试 7 项先红后绿，预检关联 18 passed；全量 pytest tests -q --tb=short --disable-warnings：1707 passed、85 skipped、0 failed。后端服务需重启；Android 未编译/真机测试，不代表已上线。 |

### BUG-2026-09-13-021 补充修复记录（2026-09-13）

- 原输入框只接通出库，入库没有入口，不能算库位选择完成。本次改为入出库共用 ScanLocationSelector，支持分页取全本仓已有库位、手工输入、相机扫描标签；启用状态未确认时阻止新提交，关闭时隐藏控件并清除行库位。
- 换仓清空旧库位与候选，忽略旧仓迟到响应；库位选择应用到本单全部行并随编辑草稿恢复。既有单据只能一个表头库位，跨库位分单，配合 BUG-2026-09-13-022 避免反提交回退错位。
- 全仓查无默认库位配置字段，接口如实返回 default_location=null，不将仓库物理地址或库存最多库位冒充默认。后续配置默认库位属于独立主数据需求。
- 新增 tests/test_native_api_location_options.py 验证双仓隔离、分页全集、认证、无效仓及关闭模式；源码回归检查共享入口与标签扫描。全量初次 1708 passed、85 skipped、1 failed，为旧源码测试绑定 addScanLine 形参名；已调整该断言并保留物料补全行为检查。Android 缺 Java/SDK，未编译/安装，真机验收仍待完成。

### MOBILE-DOCUMENT-EVIDENCE-001（2026-09-13，新增能力，非重复BUG）

- 单据拍照取证独立于物料图片，使用 DocumentEvidence 关联入库/出库单；每单最多3张JPEG，长边1600像素、单张300KB上限，与单据同一事务提交，失败整单回滚。
- 仅人工提交携带照片；图片随原请求离线暂存。读取接口按单据创建人/管理员授权，不公开静态图片地址；后端解码验证并重编码清理元数据。
- 后端隔离测试 5 passed，Python 语法检查通过；Android 已接入相机权限入口、JPEG 压缩、每单最多3张、随请求发送并进入编辑草稿恢复。照片仍只在人工点击提交后写库，业务拒绝不进离线队列。Android 编译/真机验收仍待具备 Java/SDK 的环境完成；需真机验证权限拒绝、照片大小、离线暂存与服务端查看。

### MOBILE-PERMISSION-001（2026-09-13，权限体验修复）

- Android 安装包只能声明危险权限，不能绕过系统静默授予相机/麦克风；原应用仅在扫码或语音功能进入后才分别请求，设备若已将权限设为“禁止”时现场才发现不可用。
- 首次实现的 Compose 权限门禁在现场版本出现启动即退出现象，无法取得设备 logcat，按最小风险回退为 Activity 原生 `requestPermissions`：业务导航正常启动，同时在 `onCreate` 请求 `CAMERA` 与 `RECORD_AUDIO`；拒绝时 Toast 提示，扫码/语音功能继续由各自入口做权限兜底。已授权设备不会重复弹窗。
- 回归：`tests/test_android_startup_permissions.py` 与扫码直开测试共 5 passed；本机无 Java/Android SDK，未完成 APK 编译和真机权限弹窗验收，需安装新 APK 后确认不再崩溃。
- `ad39926` 的 Android APK Build #474 曾显示红叉，但该运行日志接口返回 GitHub 403，无法取得具体编译错误；本地同样因无 Java/SDK 无法重现。当前源码已改为 Activity 原生请求，后续新提交的 CI 结果作为实际构建依据。
- `76c8fea` 触发的新构建仍在同一 Build Release 步骤失败；本次进一步去掉 `ActivityCompat` 依赖，直接调用 Activity 原生 `requestPermissions`，减少厂商/依赖兼容面。

### BUG-2026-09-13-023（2026-09-13，Android 启动崩溃：本地持久化未兜底）

- **现场证据**：用户截图 `Screenshot_20260913_235020_com.factory.wms.jpg`，系统弹「WMS扫码屡次停止运行」，状态栏「取货中」。`WMS扫码` 即 `com.factory.wms` 的 `android:label`，`MainActivity` 为唯一 Activity（Compose 单 Activity 架构），故为**主进程启动期崩溃**，非单功能失效。
- **根因（代码实证，非推测）**：崩溃点在**数据持久化层**，不在权限层。`AppNavGraph` 组合期一次性创建 11 个 ViewModel（`NavGraph.kt:81-91`），每个都构造 `WmsRepository`；而 `WmsRepository` 构造期同步执行 `AppDatabase.getDatabase(context)`（Room 建库），且 `encryptedPrefs` 用 `EncryptedSharedPreferences`（依赖 Android Keystore）。`AuthViewModel.init` 的协程**直接读取**两者且**无 try/catch**：任一步失败（Keystore 失效 / 库文件损坏 / 磁盘满）都会让协程抛未捕获异常 → 杀进程。佐证：同文件 `logout()` 早已有 try/catch，**`getSavedToken()` 没有**——不对称。
- **为何前 5 次修复无效**：`MOBILE-PERMISSION-001` 的 `90a0ef9`/`ad39926`/`b9516a9`/`e950815` 全部围绕权限门禁，方向本身偏离根因；且该缺陷登记已写明「无法取得设备 logcat」，属**盲改**。权限门禁只需从主路径移开即可（现版本已正确），但数据层未兜底，崩溃条件依然存在。
- **修复（三层兜底，均降级不中断启动）**：
  ① `WmsRepository.kt`：`db` 改 `AppDatabase?`（构造期建库失败降级为无本地缓存）；`encryptedPrefs` 改可空（创建失败置 null 并删除损坏 prefs 文件）；`getSavedToken()` 自身 try/catch；`saveLoginInfo` 写失败不阻断登录；`logout()` 的 DataStore 清理补 try/catch；新增 `safeCache()` / `logOperation()` 统一入口，本地写失败只记 WARN；`offlineQueue` 改可空（本地库不可用时降级为直连提交，入队前判空且**不谎报"已暂存"**）。
  ② `AppDatabase.kt`：`getDatabase()` 建库失败先 `deleteDatabase` 再重建一次（本地库为可重建缓存，不值得牺牲启动）；抽出 `buildDatabase()` 并提常量 `DB_NAME`。
  ③ `AuthViewModel.kt`：会话还原整体 try/catch，失败降级为未登录（`isLoggedIn=false`），绝不因本地缓存问题导致 App 打不开；401 登出链路同样兜底。
  连带适配：`ScanViewModel` 订阅离线计数改可空安全调用。
- **R6 同根因排查**：全量 grep 可空引用连锁，发现并修复 `recordOperationLog` 内 **3 处** `operationLogDao.insert` 未改安全调用（`db` 可空化后会编译失败），另行核对 `WmsApplication.warmUpOfflineQueue` 已用 `runCatching` 无需改。
- **验证**：新增 `tests/test_android_startup_crash_resilience.py` **7/7 passed**（锁死三层兜底断言，防后续重构删掉 try/catch 导致复发）；相关安卓/移动端回归 **177 passed / 4 skipped**；**全量 pytest 1724 passed / 85 skipped / 0 failed**；`lint_wms_rules.py --staged` **0 违规**。
- **未完成项（重要）**：沙箱无 Java/Android SDK（历史工具链已随沙箱重建丢失，重新下载 kotlinc 仅得 2.9MB 残缺包），**未能执行 `./gradlew assembleRelease`**。按 `BUG-2026-09-12-006` 已确立规则「Kotlin 改动须以 CI `assembleRelease` 结果为唯一验收依据，未确认 CI 转绿不得声称完成」，**本次修复的编译验收仍待 CI 确认**。
- **阻塞线索（需现场核对）**：台账 `MOBILE-PERMISSION-001` 已记 `Android APK Build` 自 **#424** 起每次在 `Build Release APK (R8 瘦身)` 步骤失败（**#423 为最后一个绿版**）。若该状态持续，则 **APK 产物从未更新**，现场设备安装的始终是 #423 之前的旧包——这可能是「装了新包仍是同样问题」的直接原因。需在 Actions 页面确认最新构建是否转绿。
- **补充修复（2026-09-14，`b6497c7` 推送后 CI 反馈）**：推送后 CI 实际跑出 **Android APK Build #481 = failure**，失败步骤正是 `Build Release APK (R8 瘦身)`，报错唯一一条：
  ```
  e: .../ui/viewmodel/scan/ScanViewModel.kt:303:48 'return' is prohibited here.
  > Task :app:compileReleaseKotlin FAILED
  ```
  **根因**：本次修复给 `ScanViewModel.init` 写了 `val queue = repository.offlineQueue ?: return`。Kotlin **不允许在 `init` 块内使用 `return`**（没有可返回的函数体）——这是语法级硬错误，属本次改动新引入。**修复**：改为显式判空包裹 `if (queue != null) { ... }`。同时回查全仓库 Kotlin 源码，确认无第二处「init 块内 return」（其余 `?: return` 均在普通函数体内，合法）。
- **连带修复（同一 CI 运行暴露）**：**`WMS CI #970 = failure`**，`Verify regression - verify_*.py` 步骤 **6 个测试失败**，全部是**字符串/正则硬编码了修复前的旧写法**，代码语义本身正确：
  | 测试 | 失败原因 | 处置 |
  |---|---|---|
  | `verify_p2_e_logout_sync_commit::t1/t2` | 断言 `encryptedPrefs.edit().clear().commit()` 无安全调用；实际改成了 `prefs.edit()...` | **代码同时存在真 bug**：原 `encryptedPrefs?.edit()?.clear()?.commit()` 安全调用链在 prefs 为 null 时整链短路，`commit()` 是否执行不可知、返回值被 `?.` 吞掉，违背 P2-E「必须真正同步落盘」。已改为 `val prefs = encryptedPrefs; if (prefs != null) { if (!prefs.edit().clear().commit()) 记 WARN }`，测试断言同步放宽并补「不得用 apply()」断言 |
  | `verify_bug_2026_08_12_009::t4` | 断言 `encryptedPrefs.getString(KEY_TOKEN`，实际为安全调用 `?.getString` | 测试断言放宽为 `encryptedPrefs\?*\.\s*getString(` |
  | `verify_bug_2026_09_12_008::test_009` | 断言 `offlineQueue.enqueue(`，实际为 `queue != null && queue.enqueue(` | 断言改为 `queue\.enqueue\(` + 校验先判空 |
  | `verify_android_offline_hint::t3` | 正则要求 `materialDao.getByCode`，实际为 `runCatching { materialDao?.getByCode }` | 正则放宽，仍强制 `fromCache`/`cachedAtMillis` 语义 |
  | `verify_bug_2026_08_11_004::t3` | 断言 `submitOpeningStock` 内直调 `operationLogDao.insert`，实际已统一走 `logOperation()` | 断言改为必须调用 `logOperation()` + 全文件校验落库链路仍在 |
- **补充验证（2026-09-14）**：上述 6 个测试 + 本 BUG 新增回归 **40 passed**；**全量 pytest 1724 passed / 85 skipped / 0 failed**（286s）；`lint_wms_rules.py --staged` **0 违规**。
- **APK 分发链核验（2026-09-14）——含一处自我更正**：
  - 经 `gh-proxy.com` 打通 GitHub API（`api.github.com` 直连 000、`ghproxy.net` 对 API 返 403），可读 Actions 状态与日志。
  - `#481`（`b6497c7`）`failure`；`#970` WMS CI 同批 `failure`。二者根因已定位并修复（见上两条）。
  - 修复推送 `1c8c67d` 后：**`#482 Android APK Build` = success**（#423 以来首次全绿，13 步含 assembleRelease / lintRelease / testReleaseUnitTest / 上传 APK / 发布 Release 全通过）、**`#971 WMS CI` = success**、`#1266 WMS AI Verification` = success。
  - **⚠ 自我更正**：先前据 AXML 字符串池顺序误判「Release APK 的 `versionCode=15`，全历史不存在，属幽灵包」。用 `pyaxmlparser` 精确解析后确认真实值为 **`versionCode=14` / `versionName=3.8.0`**，与源码 `build.gradle.kts` **完全一致**；字符串池中的 `'15'` 实为 `minSdkVersion` 的残留，属解析误读。**「版本号幽灵包」结论作废。**
  - **但「现场装的是旧包」这一核心判断仍然成立，且有更强证据**：对 Release 资产做 dex 常量池逐项比对——
    | 修复标志串（本次新增） | 旧包（#481 前，SHA `92a46c14…`） | 新包（#482 后，SHA `2fb3e7dc…`） |
    |---|---|---|
    | `本地数据库不可用` | 无 | **有** |
    | `加密存储不可用` | 无 | **有** |
    | `降级为无本地缓存` | 无 | **有** |
    | `降级为待登录状态` | 无 | **有** |
    | `读取 token 失败，按未登录处理` | 无 | **有** |
    | `会话还原失败，降级为未登录` | 无 | **有** |
    | `建库失败，尝试删除本地库重建` | 无 | **有** |
    | 对照组 `wms_database` / `wms_secure_prefs` / `WmsRepo` / `离线队列预热失败` | 有 | 有 |
  - **结论**：CI 自 #424 起持续失败期间，Release 资产确实停在 #423 时代的旧代码（无任何本次修复标志串），这解释了「现场重装仍是老问题」。**现已修复：`#482` 转绿并成功发布新包，新包经 dex 级验证确认包含全部三层兜底修复。**
  - **生效条件**：用户需**卸载旧包后重新安装**新版（`app-release.apk` / Release 直链 `wms-mobile-scan.apk`）。因 `versionCode` 仍为 14 未递增，覆盖安装可能被系统拒（同版本号覆盖），**卸载重装是稳妥路径**；建议后续提交统一递增 `versionCode`。

- **第二轮修复（2026-09-14 08:15，现场复测仍崩溃 → 定位到真正的第二根因）**：
  - **新现场证据**：用户装新包后复测，截图显示 `WMS扫码屡次停止运行` 与系统弹框「**是否允许"WMS扫码"访问相机？1/2**」**同屏出现**。崩溃时刻从「冷启动」变为「首次进入扫码页、请求权限时」，且这是全新安装后的首次授权路径。
  - **根因（权限线路）**：`MainActivity.onCreate` 中调用了 `requestPermissions(arrayOf(CAMERA, RECORD_AUDIO), ...)`，且位置在 **`setContent{}` 之前**。`Activity.requestPermissions()` 是**同步打断式**调用——它让 Activity 立即进入 PAUSED 去显示系统弹框；此时 `setContent` 尚未执行、Compose View 树尚未建立，用户响应弹框后 Activity 恢复，回调与组合撞在未初始化的宿主上 → **进程被杀**。
  - **为何前 5 次修复全部无效**：`MOBILE-PERMISSION-001` 的 5 个提交（`90a0ef9` 加权限门禁 / `ad39926` 改 Activity 原生请求 / `b9516a9` 换 API / `e950815` 简化）**全部在更换「用什么 API 申请」，从未质疑「在 `onCreate` 里、`setContent` 之前申请」这个调用位置本身**；`e950815` 还把 `onRequestPermissionsResult` 一并删除，导致权限回调**无人处理**。台账早已记「无法取得设备 logcat」，属盲改——本次现场截图首次给出了「弹框与崩溃同屏」这一决定性线索。
  - **修复**：**彻底移除 `MainActivity` 的启动期权限申请**（连带删除 `REQUEST_STARTUP_PERMISSIONS` 常量与 `Manifest` import）。依据：两个权限**都已具备**按需申请的 Compose 机制，启动期申请纯属冗余——
    | 权限 | 现有按需申请位置 |
    |---|---|
    | CAMERA | `ui/components/ScannerDialog.kt:145-161`（`rememberLauncherForActivityResult` + `LaunchedEffect`，进扫码弹窗时请求） |
    | RECORD_AUDIO | `ui/components/VoiceAssistant.kt:80-137`（同机制，启用语音时请求） |
  - **R6 同根因排查**：全量 grep `requestPermissions` —— 移除后全项目**零调用**，`WmsApplication` 亦无权限申请，确认无第二处启动期申请。
  - **反向回归**：重写 `tests/test_android_startup_permissions.py`。**原文件正是锁死错误行为的元凶**——它断言 `MainActivity` 必须包含 `requestPermissions(`（`test_startup_requests_both_permissions_before_app_navigation`），使该写法无法被修正。新版改为 5 项反向断言：MainActivity **不得**出现 `requestPermissions(`（去注释后校验）与 `REQUEST_STARTUP_PERMISSIONS`；两个权限必须由 Compose 组件按需申请；`setContent`/`AppNavGraph` 组合完整。
  - **验证**：`test_android_startup_permissions.py` + `test_android_startup_crash_resilience.py` **12 passed**；**全量 pytest 1726 passed / 85 skipped / 0 failed**；`lint_wms_rules.py --staged` **0 违规**。
  - **CI 验收（`b99a586`）**：`#484 Android APK Build` **success**、`#973 WMS CI` **success**、`#1268 WMS AI Verification` **success**。
  - **字节码级验证（androguard 反汇编 Release APK）**：第三代包（SHA256 `1074141f…`）的 `Lcom/factory/wms/MainActivity;.onCreate(Landroid/os/Bundle;)V` 共 **42 个方法调用，权限调用数 = 0**，全部为 `setContent` / `enableEdgeToEdge` / Window 组合逻辑；对照第二代包（`2fb3e7dc…`）该方法内仍含 `requestPermissions`。**确证启动期权限申请已从产物中消失。**
  - 三代产物标志串总表（dex 常量池）：
    | 标志串 | #481前(旧) | #482后 | #484后 |
    |---|---|---|---|
    | `本地数据库不可用` | 无 | 有 | 有 |
    | `加密存储不可用` | 无 | 有 | 有 |
    | `降级为无本地缓存` | 无 | 有 | 有 |
    | `降级为待登录状态` | 无 | 有 | 有 |
    | `读取 token 失败，按未登录处理` | 无 | 有 | 有 |
    | `会话还原失败，降级为未登录` | 无 | 有 | 有 |
    | `建库失败，尝试删除本地库重建` | 无 | 有 | 有 |
    | 对照 `wms_database` / `WmsRepo` | 有 | 有 | 有 |
  - **教训**：改动 Android 启动路径时，**不能在 `onCreate` 中做任何会打断 Activity 生命周期的同步操作**（权限申请、`startActivityForResult` 等）——必须让 `setContent` 先完成。测试若硬编码实现细节（如"必须调用某 API"），会把错误锁死，应断言**行为契约**而非**实现手段**。

### BUG-2026-09-14-026（2026-09-14，加固：Gson 非空契约破坏入口与冷启动会话兜底）

- **来源**：`BUG-2026-09-13-025` 交付时自列的遗留项，本轮动手修。
- **性质**：**预防性加固**，非用户已触发的线上故障。按 `BUG-2026-08-24-007` 已确立的故障模式
  （Gson 走 `Unsafe.allocateInstance` 绕过 Kotlin 构造器 → 非空字段被静默置 null → UI 层裸调 → 主线程 NPE → 整 App 崩溃）全量排查剩余入口后，定位两处：

  **① `WmsRepository.loadEditDraft()` —— 唯一没有 try/catch 的反序列化入口**

  | 对比项 | 状态 |
  |---|---|
  | `loadStocktakeDraft()` | 有 try/catch（既有正确范式） |
  | `loadEditDraft()` | **无** try/catch，异常直接抛到冷启动链路 |

  `ScanEditDraft` 的 `lines: List<DraftScanLine>`、`contractNo: String`、
  `inboundBusinessType: String` 均为 Kotlin 非空声明，Gson 反序列化时可被置 null。
  脏值经 `ScanViewModel.restoreEditDraft()` 的 `_uiState.copy(contractNo = draft.contractNo)`
  （平台类型赋值，编译器**不插** `checkNotNull`）静默进入 UI 状态，随后在 UI 层裸调即崩。

  **② `WmsRepository.getWarehouses()` —— 缺 `ensureSession()`**

  | 方法 | `ensureSession()` |
  |---|---|
  | `getDepartments()` | ✅ |
  | `getEmployees()` | ✅ |
  | `getWarehouses()` | ❌ **缺失** |

  该方法在冷启动首页（`HomeViewModel.init → loadDashboard`）即可能被调用，早于
  `AuthViewModel` 的异步会话还原（`BUG-2026-08-24-006` 描述的同一竞态）。
  `safeCall` 有兜底故**不崩**，但会出现「首个请求不带 baseUrl/token」的功能瑕疵。

- **修复**（`WmsRepository.kt`，+46 行）：

  ```kotlin
  suspend fun loadEditDraft(key: String): ScanEditDraft? {
      val json = context.dataStore.data.first()[stringPreferencesKey(key)] ?: return null
      return try {
          Gson().fromJson(json, ScanEditDraft::class.java)?.let { sanitizeEditDraft(it) }
      } catch (e: Exception) {
          android.util.Log.w("WmsRepo", "读取改单草稿失败，按无草稿处理: ${e.message}")
          null
      }
  }

  // 表达式体 + runCatching：任一处因脏数据抛异常，整体退化为"无草稿"
  private fun sanitizeEditDraft(draft: ScanEditDraft): ScanEditDraft? = runCatching {
      val safeLines = draft.lines.mapNotNull { entry ->
          val code = entry.line.material_code
          if (code.isBlank()) null else entry   // material_code 空的脏行无法定位物料，丢弃
      }
      draft.copy(lines = safeLines)
  }.getOrNull()
  ```
  另在 `getWarehouses()` 首行补 `ensureSession()`。

- **为什么选 `runCatching` 而不是逐字段 `?: 默认值`**：
  逐字段判空会因 Kotlin 认为字段非空而触发 `USELESS_ELVIS` / `SENSELESS_COMPARISON`
  等告警，需成片 `@Suppress`（且本地无 Kotlin 编译器可验证，风险不可控——
  上一次编译错误就导致 #486 整包未产出）。`runCatching` 包裹是**零告警、零语法歧义**
  的写法，语义等价：脏字段导致任一处抛 NPE → 整体退化为 null（"无草稿"）→
  引导用户重扫，而不是把 null 带去 UI。能安全修补的坏行（`material_code` 为空）
  在 `runCatching` 内用 `mapNotNull` 剔除，属于正常路径。

- **验收（可复现）**：

  | 项 | 结果 |
  |---|---|
  | 新增回归测试 | `tests/verify_bug_2026_09_14_026_gson_nonnull_and_session.py`，**10 项** |
  | 全量测试 | **1726 passed / 85 skipped / 0 failed** |
  | 预提交门禁 | 0 处违规 |
  | CI | `#490 Android APK Build` **success**、`#1274 AI Verification` success |
  | 反向验证 | **三种破坏场景全部被精准捕获**（去 runCatching+坏行过滤 → 2 项失败；去 `ensureSession` → 2 项失败；去 try/catch → 1 项失败） |
  | 字节码级验收 | 新包字符串池含本轮新增日志 `"读取改单草稿失败，按无草稿处理: "` → 改动确已编译进 APK；`MainActivity.onCreate` 权限调用数仍为 **0** |

  > 注：#490 编译成功意义特殊——这是本地无 Kotlin 编译器可用的情况下，
  > 通过**选择零告警写法**而非"事后修编译错误"来规避 `#486` 那类事故的第一次实践。

- **测试自身的两处缺陷（本轮自查发现并修正，值得记录）**：
  1. **函数体截取用了近似匹配**：原以 `find("\n    private fun ", 1)` 找下一个成员，
     但 `sanitizeEditDraft` 后面紧跟的是 `suspend fun`（缩进不同）→ 匹配失败 →
     body 吞掉整个文件余下部分 → 断言在噪声里"碰巧"命中 → **假绿**。
     改为**大括号配对**精确截取（表达式体函数的 `.getOrNull()` 在括号外，单独处理）。
  2. **同名测试函数重复定义**：改稿时旧版未删，Python 后定义覆盖前者，
     实际跑的是宽松的旧断言。已删除重复项。
  > 教训：**断言写完全绿不算数，必须反向破坏验证能红**。第一次反向验证时测试全绿，
  > 才发现测试本身是假的——如果跳过这一步，就会带着两个假测试提交。
- **未修（已确认安全，不动）**：`OfflineQueueManager.replay()` 的三个 `fromJson`
  调用点外层已有 `catch (e: Exception)` 兜底（`doSync` 内），异常会被转成
  `markFailure` 并保留中文原因，**不会崩溃**。按"只改必要处"原则保持原样，
  并加了一条回归断言锁住该兜底不被移除。

### BUG-2026-09-14-027（2026-09-14，「WMS扫码屡次停止运行」复现：versionCode 冻结致分发陷阱）

- **现场**：用户再次反馈系统弹「WMS扫码屡次停止运行」，与 BUG-2026-09-13-023 截图同症状。
- **R6 同根因排查（先查历史，未盲改）**：命中 BUG-2026-09-13-023。该 BUG 已实证并修复两个根因——①启动期数据持久化三层兜底（WmsRepository/AppDatabase/AuthViewModel）；②onCreate 里 setContent 之前申请权限。本次在 main HEAD（8f8c17d）逐项复核：`MainActivity.onCreate` 无 `requestPermissions`（仅留根因注释），`WmsRepository.kt:42/85/169`、`AppDatabase.kt:47`、`AuthViewModel.kt:64` 兜底标志串齐全——**两修复均在源码，无回退**；台账今日已对官方 Release APK（#488/#490）做字节码级验证，含全部修复标志串。**故非代码回归。**
- **真正根因（分发陷阱）**：`app/build.gradle.kts` 的 `versionCode` 自 14 起被**冻结**，`versionName` 停 3.8.0。Android 按 versionCode 判新旧：同号覆盖安装不替换旧代码、用户在「应用信息」里永远看到 3.8.0 无法分辨新旧包 → 现场设备长期停留在修复前旧包，崩溃"屡次复现"。BUG-2026-09-13-023 早已建议「统一递增 versionCode」但一直未执行，本轮落实。
- **修复（独立 atomic action，仅改构建脚本版本号与注释，不动业务代码）**：`versionCode` 14→15、`versionName` 3.8.0→3.8.1，并补「每次发版必须递增 versionCode」注释。
- **回归**：新增 `tests/verify_bug_2026_09_14_027_versioncode_increment.py` 3 项（versionCode≥15 防冻结/倒退、versionName 同步递增、防复发注释在位），连同既有版本契约测试（均用 `>=` 断言）共 **26 passed**（沙箱无 Java/Android SDK，静态契约测试，本地无法编译 APK）。
- **生效条件与验收（重要）**：本改动需 CI `Android APK Build` 转绿产出 versionCode=15 新包后，用户**卸载旧包（连同可能损坏的本地库/Keystore）再重装** 3.8.1；此后覆盖安装可正常替换、可在「应用信息」核对版本号。**若装完 3.8.1 仍崩溃，则为未发现的第三根因，须现场抓 logcat 诊断，禁止再盲改**（BUG-2026-09-13-023 五次盲改教训）。
- **CI 验收（已确认，commit `694bbcb4`）**：`Android APK Build` / `WMS CI` / `WMS AI Verification` **三工作流全部 success**（含本次新增的 verify 回归测试）；Release 资产 `wms-mobile-scan.apk`（25,095,683 字节）已于 2026-09-14T07:53:09Z 更新为 versionCode=15 / 3.8.1 新包，固定直链即刻生效。生产/用户侧生效仍须**卸载旧包后重装 3.8.1**（覆盖安装此后亦可正常替换）。
- **用户侧终验（2026-09-14，结案）**：用户依次卸载重装 3.8.1 → 3.8.2 → 3.8.3 全部成功安装（3.8.2 崩溃报告页自报版本「3.8.2 (16)」证明 versionCode 链路正常递增、覆盖安装正常替换），分发陷阱解除。

### BUG-2026-09-14-028（2026-09-14，3.8.1 仍冷启动闪退 → 加应用内崩溃报告页捕获第三根因）

- **现场**：用户确认已装 3.8.1（versionCode=15，含 BUG-2026-09-13-023 两修复 + BUG-2026-09-14-027 版本解冻），**打开应用仍立即闪退**。这坐实存在**未被发现的第三根因**——此前两个根因均已修复且字节码级验证，却仍复发。
- **关键判断（不再盲改）**：历轮修复全程**没有拿到过一次 logcat/堆栈**，修的都是"看起来会崩的点"。本次先复核冷启动全链路代码：`WmsApplication.onCreate` 4 处调用（崩溃日志器/相机缓存清理/ScanFeedback 预热/离线队列预热）均有兜底；`MainActivity` 仅 `enableEdgeToEdge`+`setContent`；组合期 14 个 ViewModel 的 `init` 块全部有 try/catch 或为空；R8 16 条 keep 规则覆盖 model/api/room/security/camera/mlkit/ui。**静态看无裸露崩溃点 → 真凶只能在运行期（设备/R8/数据相关），必须拿到真实堆栈才能定位。**
- **障碍**：`WmsApplication` 的崩溃日志器（BUG-2026-09-13-001）已把堆栈写入 `filesDir/crash/last_crash.txt`，但 **release 包在非 root 手机上无法用 adb 读取该私有目录**（release 非 debuggable，`run-as` 不可用），文件形同虚设；用户不熟电脑，adb 路径不可行。
- **修复（诊断桩，非业务改动、不改崩溃行为）**：`MainActivity.setContent` 内加门控——检测到 `crash/last_crash.txt` 存在时，**先渲染零依赖静态页 `CrashReportScreen`（不加载会崩的 AppNavGraph/不建任何 ViewModel/不触网/不读库）**，把堆栈直接显示在屏幕上，附「复制崩溃信息」（写剪贴板）与「我已记录，继续使用」（删文件后进主界面）两入口。用户截图/粘贴回传即可定位真凶。即使主界面必崩，报告页也能稳定渲染——这是"崩了还能打开看到错误"的关键。
- **回归**：新增 `tests/verify_bug_2026_09_14_028_crash_report_screen.py` 5 项（读 filesDir 崩溃文件、有崩溃先报告页不进 AppNavGraph、报告页零依赖不建 ViewModel、有复制+继续两入口、dismiss 删文件），连同 BUG-2026-09-14-027 共 **8 passed**。版本号 15→16 / 3.8.1→3.8.2 便于用户核对装的是带报告页的包。
- **生效条件与下一步**：CI 转绿产出 3.8.2 后，用户卸载重装 → 让 App 崩一次 → 再打开即见报告页 → 截图/复制堆栈回传。**拿到真实堆栈前不再做任何"修复"**（BUG-2026-09-13-023 五次盲改教训）。
- **CI 验收（已确认，commit `76adfb4`）**：`Android APK Build` #494 success，Release 资产已更新为 3.8.2（versionCode=16）。
- **用户侧终验（2026-09-14，使命达成）**：真机 3.8.2 冷启动崩溃后再开，报告页稳定渲染，用户复制回传完整堆栈——**正是该堆栈定位出 BUG-2026-09-14-029 真凶**。诊断桩按设计完成使命，作为常驻安全网保留：今后任何崩溃用户都能自助取证回传，不再依赖 adb（release 包非 debuggable 无法 run-as 读私有目录的死角就此补上）。

### BUG-2026-09-14-029（2026-09-14，「WMS扫码屡次停止运行」真实根因：离线队列构造期急切解析 api）

- **现场证据（首次拿到真实堆栈）**：BUG-2026-09-14-028 的应用内崩溃报告页在真机 3.8.2 上捕获 `last_crash.txt`：
  ```
  RuntimeException: Cannot create an instance of class ScanViewModel
    at ...NavGraphKt.AppNavGraph
  Caused by: IllegalStateException: 服务器地址未配置，请先登录并填写服务器地址
    at RetrofitClient.getApiService
    at ScanViewModel.<init>
  ```
  设备 HUAWEI LIO-AN00 / sdk 31 / version 3.8.2(16)。**这是历轮首次拿到决定性堆栈——印证"无 logcat 盲改必失败"。**
- **根因（代码实证）**：`AppNavGraph` 组合期创建 `ScanViewModel` → 其 `init`（`ScanViewModel.kt:304`）**同步**访问 `repository.offlineQueue`（**不在 safeCall 内**）→ `offlineQueue` 的 lazy 构造 `OfflineQueueManager` 时**急切**解析 `api`（`WmsRepository.api` getter = `RetrofitClient.apiService`，`RetrofitClient.kt:73` 在 `baseUrl` 空时 `check` 抛 `IllegalStateException`）→ fresh install / 清除数据 / 未登录时 baseUrl 为空 → 冷启动组合期抛异常 → 闪退。
- **与前两轮"修复"的关系（为何一直不好）**：BUG-2026-09-13-023 修的数据持久化（Room/Keystore/AuthViewModel）与权限路径**都不是本次真凶**；本轮崩溃在**网络层 api 的构造期急切解析**。`apiService` 的 `check` 是**故意安全守卫**（防 token 发往未配置服务器），不能删；真正错误是 `OfflineQueueManager` 构造期就解析 api（它仅在 `replay()` 同步时才用 api）。
- **R6 同根因排查**：协程内 api 访问（getDashboard/getWarehouses 等）全走 `safeCall`（`WmsRepository.kt:907`，catch Exception 兜底）→ 安全；`.offlineQueue` 全项目仅 3 处：`WmsApplication:114`（已 runCatching）、`ScanViewModel:304`（init 同步，本次崩点）、`ScanViewModel:321`（用户触发）——修复后三处均安全。`OfflineQueueManager.getInstance` 全项目仅 `WmsRepository:60` 一处调用。
- **修复**：`OfflineQueueManager` 构造改收 `apiProvider: () -> WmsApiService`，内部 `by lazy { apiProvider() }` 延迟到 `replay()` 首用时才解析 api（彼时已登录、baseUrl 已配置；即便仍为空也由 `doSync` 的 try/catch 兜为失败，不崩）；`getInstance` 同步改签名；`WmsRepository.offlineQueue` 改传惰性 `{ api }`。**构造期彻底不碰网络层。**
- **回归**：新增 `tests/verify_bug_2026_09_14_029_offlinequeue_lazy_api.py` 4 项（构造收 provider 非 eager api、内部 by lazy 解析、getInstance 收 provider、repository 传 { api } 非裸 api），连同 027/028 共 **12 passed**。版本 16→17 / 3.8.2→3.8.3。
- **生效条件**：CI 转绿产出 3.8.3 后用户卸载重装，fresh install 冷启动不再闪退，可正常进入登录页。
- **CI 验收（已确认，commit `e1aea42`）**：`Android APK Build` #495 / `WMS CI` / `WMS AI Verification` 三工作流全部 success；Release 资产于 2026-09-14T09:34:52Z 更新为 3.8.3（versionCode=17）新包（沙箱代理通道下载 APK 屡被截断无法字节级校验，但 #495 构建自本提交 + 资产更新时间紧随其后 + 用户装此包后闪退消失——此前 3.8.2 上 100% 复现——行为变化即含修复的实证）。
- **用户侧终验（2026-09-14，已修复结案）**：真机 HUAWEI LIO-AN00 卸载重装 3.8.3，fresh install 冷启动**不再闪退**，正常进入登录页并**登录成功**。期间一次「登录失败(502)」经外网实测排查为服务器端后端进程停止（见 BUG-2026-09-14-030），与 App 无关；服务器恢复后登录即成功，反证 App 冷启动与网络链路均正常。**至此「WMS扫码屡次停止运行」三根因（023 数据持久化+权限、027 versionCode 冻结、029 离线队列构造期急切解析 api）全部闭环结案。**

### BUG-2026-09-14-035（2026-09-14，手机端物料档案只显示前 50 条：搜索接口 `.limit(50)` 截断 + 进入不加载）

- **发现方式**：用户要求「手机端物料档案能展示所有物料」。
- **根因（代码实证）**：①后端 `/mobile/api/material_archive/search` 硬编码 `.limit(50)`——空关键字浏览也只返回前 50（R1：默认上限被当成全量）；②`MaterialArchiveSearchScreen` 为纯搜索屏，进入不自动加载，空关键字显示「输入关键字搜索物料」。
- **连带隐患**：`_archive_material_payload` 的 `image_count` 逐物料 `COUNT`、`unit`/`category` 惰性加载——若直接取全会放大为 N+1（数千次 SQL）。
- **R6 同根因排查**：与 BUG-2026-09-07-003/004（报表截断）、BUG-2026-09-10-009（日报逐页翻页 R1）同 R1 模式；grep 移动端列表接口，本 search 为唯一硬编码小 limit 的物料主数据浏览接口，其余（库存/订单/预警）均已分页带 `total_pages`。
- **修复**：①后端返回全部匹配物料（主数据量可控），附 `total`/`truncated` 元数据，安全上限 `_MATERIAL_ARCHIVE_BROWSE_MAX=5000`；`image_count` 改一次 GROUP BY 批量预取（`_safe_material_image_counts`），`unit`/`category` `joinedload` 预加载——取全收敛为常量次 SQL；②Android 进入即 `LaunchedEffect(Unit){ viewModel.search() }` 自动加载全部，空态文案改为「暂无物料档案」。
- **回归**：新增 `tests/verify_bug_2026_09_14_035_material_archive_show_all.py` 6 项（空关键字返回全部 60 条+total、N+1 SQL≤12、超限 truncated+真实 total、关键字过滤、批量 image_count 正确、Android 自动加载静态断言+无硬编码 limit）；既有 `verify_mobile_material_archive_api.py` 12 项同步全绿；`lint_wms_rules` / `lint_no_raw_post_fetch` 0 违规。
- **生效条件**：后端改动拉取后**重启 WMS 服务生效**（R3，接口可先 `?keyword=` 自查）；**Android 改动需 CI `assembleRelease` 产出新 APK 后重装**（本地沙箱无 Java/SDK，编译验收以 CI 为准，BUG-2026-09-12-006 规则）。

### BUG-2026-09-19-001（2026-09-19，售后出库完成校验用全局库存：A 仓掩护 B 仓超卖）

- **发现方式**：按计划文档 P0-1「存量 material.stock 总账校验清零」，扫描 `app/routes` 下所有裸用 `material.stock` 的校验点，对照 A11/R2 收口。
- **根因（代码实证）**：`after_sale_out.py` 的 `complete_after_sale_out_order` 完成前预检用 `normalize_stock_quantity(material.stock or 0)`（全局总账）判断库存是否足够；两个仓库同物料时，只要 A 仓有货，B 仓售后出库单就能完成——**双仓隔离失效**。此前 `deduct_stock_atomic` 的最终扣减虽已做仓库级校验，但兜底只对 `transaction_type` 以 `revert` 开头的反提交生效；售后出库遇历史遗留库存（warehouse_id/location 全空）照样被拒，属同一根因的另一消费点（R6）。
- **R6 同根因排查**：`after_sale_out.py`/`adjustment.py`（关联结算）两个裸校验点已一并修复；`in_order.py`/`check.py`/`purchase_request.py`/`stock_query.py`/`mobile.py`/`material.py`/`app.py` 其余 `material.stock` 读法（展示/对账/AI 工具）不在 A11 校验语境，属存量基线，按需逐项收口到计划 P0-1/P2-3。
- **修复**：①校验改用单据仓库的 `get_warehouse_stock_quantities(wh_obj)`，仅当该物料全部库存无法归属仓库（`_material_stock_unattributed`）时回退全局口径兜底——与 `deduct_stock_atomic` 的合法语义完全一致；②`deduct_stock_atomic` 的兜底判据从「revert 开头 + 无归属」统一为「任何出库类型 + 无归属」，堵住「有库存却拒绝出库」的同根因复发。
- **回归**：新增 `tests/test_bug_2026_09_19_001_after_sale_out_warehouse_stock.py` 2 项（双仓掩护必须拒绝；无归属历史库存回退放行），配合既有 `test_p1_after_sale_out_location_required.py` 共 7 passed；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动拉取后**重启 WMS 服务生效**。

### BUG-2026-09-19-002（2026-09-19，库存调整单报损校验用全局库存：双仓口径不隔离）

- **根因（代码实证）**：`adjustment.py` 的 `add_adjustment` 保存报损单时用 `normalize_stock_quantity(material.stock or 0)`（全局总账）校验，A 仓有库存即可掩护 B 仓报损——与 BUG-2026-09-19-001 同一根因的另一消费点。
- **修复**：报损校验改用单据仓库（`wh_obj` 已由 `validate_inventory_warehouse` 在上方解析并保证有效启用）走 `get_warehouse_stock_quantities`；`allow_negative_stock` 开启时行为不变；无归属历史库存同样回退全局口径。
- **回归**：新增 `tests/test_bug_2026_09_19_002_adjustment_warehouse_stock.py` 2 项（双仓掩护必须拒绝 + 无归属放行）；整体连同 `test_p1_after_sale_out_location_required.py` 共 9 passed；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动拉取后**重启 WMS 服务生效**。

### BUG-2026-09-19-003（2026-09-19，生产会话 Cookie 安全仅靠启动告警：默认不拦截裸 HTTP 部署）

- **发现方式**：09-13 审计 AUDIT-2026-09-13-003（P1）落地；`validate_production_security_config` 此前只挡 `WMS_DISABLE_CSRF`，`SESSION_COOKIE_SECURE=False` 仅打 warning，运维可无视告警长期裸跑 HTTP。
- **根因（代码实证）**：`app/config.py` 生产配置 `SESSION_COOKIE_SECURE` 默认 false，`app/app.py` 启动期只 `logger.warning`，无任何阻断或显式确认机制——审计行动项要求的「阻止启动或显式放行」未实现。
- **修复**：①`validate_production_security_config` 新增硬门禁——生产环境既未 `SESSION_COOKIE_SECURE=true` 也未显式 `WMS_ALLOW_INSECURE_COOKIE=1` 时 `raise RuntimeError` 阻止启动；②显式放行后启动期告警由 warning 升级为 `logger.critical`，点名放行依据与消除方式；③`PRODUCTION_DEPLOYMENT_CHECKLIST.md` 配置检查新增硬门禁条目（HTTPS 设 `SESSION_COOKIE_SECURE=true` / 内网 HTTP 显式 `WMS_ALLOW_INSECURE_COOKIE=1`）；④`tests/conftest.py` 显式 `WMS_ALLOW_INSECURE_COOKIE=1`（内存库 + HTTP 测试环境 opt-in，保证 app 可导入）。
- **回归**：`tests/test_production_security_config.py` 扩充至 14 项全绿（无放行拒绝启动、显式放行通过、secure=true 无需放行、非生产跳过、原 CSRF 门禁回归）；`test_bug_2026_09_19_001/002` 4 项回归通过验证 app 导入链路；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动拉取后**重启 WMS 服务生效**。**注意（行为变更）**：生产重启前必须二选一配置——HTTPS 部署设 `SESSION_COOKIE_SECURE=true`，受信内网 HTTP 部署显式设 `WMS_ALLOW_INSECURE_COOKIE=1`，否则服务拒绝启动。

### BUG-2026-09-19-004（2026-09-19，访问令牌明文入库：库文件/备份外泄即全量接管——08-16-010 暂缓项按预案落地）

- **背景**：BUG-2026-08-16-010（`ApiToken.token` 与 `PrintWorkstation.auth_token` 明文入库、明文等值匹配）2026-08-16 用户拍板暂缓，触发条件为「接入真实生产环境且外泄风险升高」。2026-09-19 用户决定按台账预案（sha256 哈希存储 + 一次性返显 + 存量平滑迁移）执行，本条目登记修复。
- **根因（代码实证）**：`native_api.py` `/api/login` 与 `print_routing.py` 新增/重置工作站把 `secrets.token_urlsafe` 明文直接写库；`get_bearer_user`（`app.py`）与 `_workstation_from_token`（`print_queue.py`）按明文等值匹配；`/print_routing` 页面与 `download_agent` 部署包长期回显/预填明文令牌。
- **修复**：①新增 `app.hash_access_token()`（`"sha256:<hex>"` 前缀）与 `is_hashed_access_token()`；②签发/重置一律存哈希，明文仅在响应中一次性返显（`/api/login`、工作站新增、重置令牌）；③两处校验先按哈希查、未命中按明文兜底——命中存量明文行**原位升级为哈希**（平滑迁移，移动端 App 与已部署打印代理零变更）；④回显收口——`/print_routing` 令牌框哈希行显示「已安全存储，不可回显」并隐藏复制按钮、`download_agent` 哈希行预填重置指引占位符、`/admin/mobile_tokens` 哈希行显示「哈希存储」；⑤内置 LOCAL-SERVER 工作站（`local_print_agent.py`，app 初始化早期执行、不能反向 import，就地计算同款哈希）同步改哈希存储。
- **回归**：新增 `tests/test_bug_2026_09_19_004_token_hash_storage.py` 6 项（登录返显明文+库内哈希、哈希 Bearer 鉴权、明文 ApiToken/工作站令牌鉴权通过且原位升级、新增/重置一次性返显+旧令牌失效）；同步适配既有断言——`test_print_routing_admin.py`（新增工作站库内为哈希、download_agent 哈希行占位符+存量明文行仍可预填）、`verify_bug_2026_08_13_005`（`_make_token` 改哈希稳态，写放大断言不失真）；相关 10 个套件 172 项全绿；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动拉取后**重启 WMS 服务生效**。存量明文令牌行随首次使用自动升级为哈希，未使用的明文行最迟 7 天（令牌有效期）自然过期失效；工作站令牌需要明文时在 `/print_routing` 页面「重置令牌」一次性获取。

### BUG-2026-09-23-001（2026-09-23，新增测试三方依赖未钉 requirements-test.txt：CI unit-tests 收集期整批中断，main 留红违反 §三）

- **发现方式**：按 §三 CI 全绿门禁开工前检查，`scripts/check_ci_green.py` 返回 rc=1——`WMS CI` #1208 failure（`Android APK Build` #719、`WMS AI Verification` #1503 均 success），失败 job 为 `unit-tests` 的 pytest 步骤（`lint-and-static`、`verify-and-smoke` 均绿）。
- **根因（代码实证，R8 实证形态「本地看着绿就推送」）**：BUG-2026-09-22-015 的提交 `1e0b08c` 新增 `tests/test_bug_2026_09_22_015_dropdown_class_collision.py`，其中 `from bs4 import BeautifulSoup`（T3/T4 用 bs4 解析合成 HTML、模拟 `querySelector` 文档序命中），但 **`beautifulsoup4` 从未钉入 `app/requirements-test.txt`**——CI `unit-tests` job 只安装这一个清单。作者本地环境恰好预装 bs4，本地 17 项全绿即推送；CI 容器无 bs4 → 收集期 `ModuleNotFoundError: No module named 'bs4'` → pytest-xdist `Interrupted: 1 error during collection` 整批中断 → `WMS CI` 在 `main` 留红，其后所有 atomic action 都被门禁阻断。与 BUG-2026-09-20-004 同族：**修复提交自身引入 CI 红**。
- **修复**：`app/requirements-test.txt` 钉 `beautifulsoup4==4.15.0`（测试侧依赖钉版，PyYAML 为先例；pip-audit 只扫生产 `app/requirements.txt`，不受影响）。
- **R6 同根因排查**：AST 全量扫描 `tests/` 全部文件的顶层 import，与两份 requirements 清单逐一比对——其余三方 import 均被清单覆盖，或可解析为项目本地模块（`app/routes/`、`scripts/`、`app/utils.py` 等），**唯一缺失即 beautifulsoup4，同类点已排查**。
- **回归**：新增 `tests/test_bug_2026_09_23_001_test_deps_pinned.py` **3 项**（T0 清单存在性；T1 全量扫描 tests/ 三方 import 必须全部被 requirements-test.txt 钉住，未钉即列出 文件:行号 精准变红；T2 清单内依赖必须 `包名==版本` 钉版，杜绝「钉名不钉版」的版本漂移回潮）。**缺陷注入验证**：①移除 pin 后 T1 精准变红且只报 `bs4 → beautifulsoup4` 一处；②还原 pin + 卸载 bs4 复现 CI 症状（收集期 `ModuleNotFoundError` + `Interrupted: 1 error during collection`）；③恢复后新测试 3 项全绿、015 的 17 项全绿。**全量基线**：修复前（模拟修复环境装 bs4）`pytest tests/ -q -p no:pylama -n 4 --dist loadfile` = 2552 passed / 86 skipped / 0 failed（104s）；修复后含新测试 = **2555 passed / 86 skipped / 0 failed**（97s），新增 3 项与增量完全吻合、零既有失败；`lint_wms_rules.py` 0 违规、`lint_no_raw_post_fetch.py` 通过。
- **生效条件**：CI 环境依赖清单改动，push 到 `main` 后由 GitHub Actions 自动生效（无需重启生产服务）。
- **生效确认**：**已确认（2026-09-23 08:23）**——推送 `a330a93a` 后以 `python3 scripts/check_ci_green.py` 核对，返回 **rc=0**，三工作流全绿且均指向本次提交：`Android APK Build` #720 success、`WMS AI Verification` #1504 success、`WMS CI` #1209 success（原 #1208 failure）。§三 门禁放行恢复。

### BUG-2026-09-20-001（2026-09-20，修复→生效无确认回路：启动日志看不到版本/配置/迁移状态——R3 反复模式机械化落地）

- **发现方式**：计划 P0-3。AGENTS.md 与台账反复出现「改了没重启/没装新包」（R3、R4 共 23+ 条），修复与生效之间没有确认回路；启动日志无版本与配置自检，现场无法核对"跑的是哪份代码、什么配置"。
- **根因（代码实证）**：`run_server.py` 启动只打印 URL/端口，无版本号（仓库连 `version.py` 都没有）、无配置项状态、无迁移结果；`SESSION_COOKIE_SECURE=False` 这类关键风险此前只在 warning 里一笔带过。
- **修复**：①新增 `app/version.py`（日期基 semver `2026.09.1`）与 `app/startup_check.py`——`build_config_check_line()` 输出 `wms vX.Y.Z (<git短SHA>) config-check: env=…; session_cookie=…; csrf=…; secret_key=…; db=…; migrate=pending-init`（git SHA 直接读 `.git/HEAD`+refs 解析，不调 git 命令适配 PATH 受限环境；**只报配置状态不报敏感值本体**）；②`build_db_check_line()` 在 `initialize_database` 后检查迁移哨兵（api_token 表、print_workstation.auth_token、opening_stock.location、location_inventory.warehouse_id——均选自 R3 反复迁移点），缺失报 `missing:` 不阻断启动；③`run_server.main()` 启动日志第一行落 config-check、初始化后落 db-check，控制台 banner 同步打印两行。
- **回归**：新增 `tests/test_bug_2026_09_20_001_startup_self_check.py` 8 项（行格式/三种 cookie 状态/敏感值不落行/git SHA 解析/哨兵 ok 与 missing/接线顺序静态断言）；`test_r6_startup_migration_column_guard`+`test_auto_migrate_db_path` 8 项回归绿；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动拉取后**重启 WMS 服务生效**；生效确认方式——启动日志/控制台第一行出现 `wms v2026.09.1 (…) config-check:` 即为本改动在跑。

### BUG-2026-09-20-002（2026-09-20，R3 台账登记无「生效确认」强制字段：A13 规则机械化）

- **发现方式**：计划 P0-3.2。R3 要求修复→生效有确认回路，但台账登记只写「生效条件」、无人核对"是否真的生效"，靠自觉。
- **修复**：`scripts/lint_wms_rules.py` 新增 **A13 规则**（`RuleA13BaselineEffectConfirmation`）——`WMS_BUG_BASELINE.md` 在 git staged 新增行中出现条目头（`### BUG-/WECOM-/INV-/PUR-/SALES-/SYS-/AUDIT-`）时，要求该条目块内含「生效确认」字样，否则 pre-commit 拦截；编辑存量条目、计数行不触发（与 A8/A9/A10/A11 同为"新增代码生效"规则）。同步更新：`DEVELOPMENT_RULES.md` 规则清单 12→13 条 + A13 行；`AGENTS.md` R3 补机械化防护说明（启动自检 + A13）；lint 脚本 docstring 规则列表。
- **回归**：新增 `tests/test_lint_wms_rules_a13_golden.py` 3 项（缺字段拦截/含字段通过/非条目编辑不触发，临时 git 仓库模拟 staged）；既有 A8/A9/A10 黄金测试 18 项回归绿；本条目自身含「生效确认」字段（规则自举验证）。
- **生效条件**：改动拉取后本地 pre-commit 钩子即生效（无需重启服务）；CI lint 同步覆盖。
- **生效确认**：待确认——下次登记新 BUG 条目时 pre-commit 应能拦截缺「生效确认」字段的写法（golden 测试已在临时仓库验证三种场景）。

### BUG-2026-09-20-003（2026-09-20，委外发料/收货新增表单无仓库字段：静默兜底默认仓，用户无感知）

- **发现方式**：计划 P1-1（AGENTS.md §二 仓库必填落地缺口实测）。
- **根因（代码实证）**：`subcontract_issue.html` / `subcontract_receive.html` 新增模态框根本没有仓库字段；后端 `add_subcontract_issue` / `add_subcontract_receive` 只能走「父单继承→默认仓」静默兜底——多仓库部署下用户不知道单据落哪个仓，发料/收货仓与委外单不一致时也无处纠正。
- **修复**：①两个列表路由补 `warehouses` / `default_warehouse` 上下文；②两个模板新增模态框加 `name="warehouse"` + `required` + 默认仓预选中（对齐 in_order_add 范式），委外加工单选项带 `data-warehouse`，选中父单自动联动其仓库；③提交前 JS 拦截空仓库。后端兜底链（父单继承→默认仓）保留不动——API/旧客户端不传仓库行为不变（向后兼容）。另实测 `opening_stock.html` 表头仓库**已是**默认仓预选中且行级仓库必填（pydantic `warehouse_id: int = Field(gt=0)`），「不指定（各行自选）」为合法设计，计划中该项按已达标处理、无需改动。
- **回归**：新增 `tests/test_bug_2026_09_20_003_subcontract_warehouse_form.py` 6 项（两表单 required/默认 selected/data-warehouse 渲染断言；显式选仓落单；未传仓库保留父单继承）；既有委外 6 套件 32 项全绿；`lint_wms_rules --staged` 0 违规。
- **生效条件**：模板改动拉取后**重启 WMS 服务生效**（R3）。
- **生效确认**：待确认——重启后打开委外发料/收货新增弹窗，应见「仓库 *」下拉且默认仓已选中，切换委外加工单时仓库自动跟随父单。

### BUG-2026-09-20-004（2026-09-20，BUG-2026-09-19-003 回归：Cookie 硬门禁漏排查 CI/验证脚本消费点，main 两工作流变红）

- **发现方式**：用户核对 GitHub Actions 看板，指出 `WMS CI` #1096–#1100 连续 5 个提交全红，AGENTS.md §三「CI 全绿门禁」被持续违反（门禁要求任一非绿即不得提交新 atomic action）。
- **根因（代码实证，R6 同根因未排查所有消费点）**：BUG-2026-09-19-003 引入 `validate_production_security_config` 生产硬门禁后，只给 `tests/conftest.py` 补了 `WMS_ALLOW_INSECURE_COOKIE=1`，**漏排查所有「以 production 启动服务 / 导入 app」的非 pytest 消费点**：
  1. `scripts/run_smoke_in_ci.py:50` 显式 `FLASK_ENV=production` 且无 opt-in → `app/run_server.py` 导入期 `raise RuntimeError` 服务拒启 → CI 冒烟 30s 超时全废（`WMS CI` 红）。
  2. `scripts/verify_ai_business_quality_dashboard.py` 测试 1/2 `from app import app` 无 opt-in → 8 项挂 2 项（`WMS AI Verification` 红）。
  3. 同模板隐患（当前未爆）：`verify_ai_purchase_workbench_page.py`、`verify_ai_warehouse_workbench_page.py` 同缺 opt-in；`verify_ai_provider_evaluation.py` 该段被 `except Exception` 吞掉后静默打印「跳过」，属假绿。
- **修复**：①`scripts/run_smoke_in_ci.py` 启动 env 增加 `WMS_ALLOW_INSECURE_COOKIE=1`（与 conftest 同口径，CI 走 HTTP + 测试库，属受信环境显式放行）；②`verify_ai_business_quality_dashboard.py` / `verify_ai_purchase_workbench_page.py` / `verify_ai_warehouse_workbench_page.py` 三处 env 预设段补 `WMS_ALLOW_INSECURE_COOKIE=1`；③`verify_ai_provider_evaluation.py` 测试 5 的 `os_env.setdefault` 段补同项（消除被吞异常掩盖的假绿）；④新增回归测试锁定「CI 脚本必须显式 opt-in」这一契约，防止再次漏排查。
- **回归**：新增 `tests/test_bug_2026_09_20_004_ci_cookie_optin.py`（覆盖 smoke 脚本 env 注入、4 个 verify 脚本的 opt-in 预设、缺省则门禁复现）；本地以 `FLASK_ENV=production` 实跑 `run_smoke_in_ci.py` 前 2 阶段确认服务可启动；`lint_wms_rules --staged` 0 违规。
- **生效条件**：改动 push 到 `main` 后由 GitHub Actions 自动生效（无需重启生产服务；CI 环境为独立容器）。**注意**：本修复不改变生产行为，生产部署仍须按 BUG-2026-09-19-003 二选一配置。
- **生效确认**：**已确认（2026-09-20 01:35）**——推送 `99cbd960` 后 `python scripts/check_ci_green.py` 返回 rc=0，三工作流全绿且均指向本次提交：`Android APK Build` #612 success、`WMS AI Verification` #1396 success（原 #1395 failure）、`WMS CI` #1101 success（原 #1100 failure）。门禁放行恢复。

### BUG-2026-09-20-005（2026-09-20，启动回填在空库/未建表时报 `no such table: warehouse`：ERROR 噪音刷屏）

- **发现方式**：排查 BUG-2026-09-20-004 时在 CI 日志（`WMS AI Verification` #1395）中发现，每跑一个 verify 脚本都刷一组完整 traceback，虽不阻断但与真实故障混在一起，削弱日志可读性。
- **根因（代码实证）**：`app/app.py:27115` `backfill_stock_txn_warehouse_id()` 在 `initialize_database()` 建表**之前**的导入期执行 `Warehouse.query.all()`；CI/空库场景下表尚未创建，SQLAlchemy 抛 `sqlite3.OperationalError: no such table: warehouse`，被 `except` 捕获后记 ERROR「下次启动重试」。
- **修复（2026-09-20，本次落地）**：新增 `_stock_txn_backfill_ready()` 前置表存在性探测——用 `sqlalchemy.inspect(...).has_table()`（与 `app/routes/native_api.py::_ensure_login_schema` 同款写法）检查 `stock_transaction` / `warehouse` / `location_inventory` 三张回填必需表；模块级调用点改为「先探测，缺表则降级 `logger.info` 静默跳过，齐备才回填」。探测本身失败（引擎未就绪）同样返回 False——宁可静默跳过（回填幂等，下次启动重试）也不在导入期抛异常。**注**：探测函数自带 app context 兜底（Flask-SQLAlchemy 3.x 下 `db.engine` 需活跃 context，否则 `RuntimeError: Working outside of application context`），调用方无需预 push。
- **回归**：新增 `tests/test_bug_2026_09_20_005_backfill_table_guard.py` **8 项**（三表齐备→True / 缺 warehouse→False / 缺 stock_transaction→False / 缺 location_inventory→False / 全空库→False / 探测抛异常→False 不外泄 / 真库上 backfill 仍正常回填且幂等（守卫未误伤治本路径）/ 接线校验守卫先于回填调用防回归）。连同 `test_bug_2026_08_27_005`（T1–T11 回填语义）+ `test_ensure_stock_transaction_warehouse_id_column`（补列）共 **28 项全绿**；`lint_wms_rules --staged` 0 违规。
- **R6 同根因排查**：grep 全仓 `with app.app_context()` 的模块级调用点，确认导入期仅有回填这一处查表——`backup_sqlite_on_startup()`（app.py:3068）是文件级备份不查表；`run_due_wechat_share_jobs()`（app.py:22549）是运行时调度入口。**同类点已排查，无第二处**。
- **生效条件**：改动拉取后**生产需重启 WMS 服务生效**（导入期逻辑，随服务启动执行；首次重启即见效）。
- **生效确认**：**已确认（2026-09-20 02:08 本地 + 03:05 CI + 04:37 台账推送后复验）**——①本地空库端到端实测：设 `DATABASE_URL` 指向全新空 sqlite 文件后导入 `app`，捕获 ERROR 级日志 **0 行**、`no such table: warehouse` **不再出现**，改为 INFO「启动回填跳过：前置表尚未建好（空库/首启导入期），下次启动重试」；真库路径 28 项回归全绿证明治本未打折。②CI 门禁（提交 `186b42b`）：`check_ci_green.py` 返回 **rc=0**，三工作流全绿——`Android APK Build` #618、`WMS AI Verification` #1402、`WMS CI` #1107，均 success。③台账补登后推送 `9f67cb1b`，CI 再次全绿——`Android APK Build` #619、`WMS AI Verification` #1403、`WMS CI` #1108，均 success。**§三 后置条件完全闭环。**

### BUG-2026-09-20-007（2026-09-20，Windows 路径被拼进 `python -c` 源码触发 unicodeescape：期初库存迁移回归锁 10/11 项恒失败）

- **发现方式**：收尾 BUG-2026-09-20-005 时做全量测试定性，一度把 `test_opening_stock_migration.py` 的失败误判为「跨用例顺序污染」（因单独跑部分用例曾通过）。**后经 `--tb=short` 复现取证，推翻该结论**——这是**确定性环境缺陷，与执行顺序无关**（教训：定性前必须看 traceback，不能只凭"单独跑是否通过"下结论）。
- **根因（代码实证）**：`tests/test_opening_stock_migration.py:93` 的 `_run_migration()` 把路径**直接拼进**传给 `python -c` 的源码字符串：
  `os.environ['DATABASE_URL'] = 'sqlite:///{db_file}'`
  Windows 下 `db_file` 形如 `C:\Users\...\legacy.db`，其中的 `\U` 被 Python 源码解析器当作 **unicode 转义** → 子进程当场
  `SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes in position 12-13: truncated \UXXXXXXXX escape`。
  注意同函数内 `{str(APP_DIR)!r}` 因加了 `!r` 而安全，**唯独 `{db_file}` 漏了**——同一函数两种写法并存，是典型的一致性疏漏。
- **危害（远超"一条测试失败"）**：这 11 项是 **BUG-2026-09-15-007（期初库存分单）的迁移回归锁**，覆盖迁移幂等性、数据无损、备份表一致性、单据号格式等核心契约。它们恒失败意味着**该 P1 改造的迁移防护网整体失效**，且失败信息「迁移进程未正常完成」与真实迁移缺陷无法区分——真出问题时会被当成噪音忽略。
- **修复**：`_run_migration()` 改为**经环境变量传递**参数（`WMS_TEST_APP_DIR` / `WMS_TEST_MIGRATE_TIMES` / `DATABASE_URL`），子进程源码**只读不拼**；`subprocess.run` 显式传 `env=env`；路径统一 `replace('\\', '/')` 成正斜杠，根除转义歧义。修法刻意选「环境变量传参」而非简单加 `!r`——后者仍依赖"记得加"，前者从机制上不可能踩坑。
- **回归**：新增 `tests/test_bug_2026_09_20_007_subprocess_path_escape.py` **5 项**回归锁——①源码内不得字面赋值 `DATABASE_URL`；②不得出现未加 `!r` 的 `sqlite:///{db_file}` 插值；③`subprocess.run` 必须传 `env=`；④**机制证明**（真实启动子进程用 `C:\Users\x` 拼源码，确证抛 `unicodeescape`，证明约束不是洁癖）；⑤被修文件语法正确、`_run_migration` 可调用。修复后 `test_opening_stock_migration.py` **由 10 failed → 11 passed**。
- **R6 同根因排查**：grep 全仓 `DATABASE_URL.*=.*'sqlite:///` 的源码内插模式，**全仓仅此 1 处**，已修，**无第二处**。
- **生效条件**：仅改测试代码（不含生产逻辑），**无需重启服务**；CI 环境同步生效。
- **生效确认**：**已确认（2026-09-20 04:50）**——`test_opening_stock_migration.py` 单独跑 **11 passed**（修复前 10 failed）；新增回归锁 **5 passed**；`lint_wms_rules --staged` 0 违规。
- **附：全量串跑仍存在的失败（已定性为存量顺序污染，非本次引入，登记备查）**：本机全量串跑（约 2300 例）有约 8 个 `test_ensure_*` 的 `*_even_when_no_db_touch` 用例及几个打印模板用例失败，但**单独跑全部通过**（8 个 ensure 文件合计 37 passed），属**跨用例状态污染**。且 CI 三工作流（含完整测试套件）在 `186b42b`/`9f67cb1b` 上均全绿，证明这些失败**是本机环境特有、不在 CI 复现**。已单独登记为待办，不阻塞当前工作。

### BUG-2026-09-20-008（2026-09-20，委外发料只扣总账、不扣库位账：开启库位管理时 ①≠Σ② 账实分裂）

- **发现方式**：P2-3 前置侦察——用本次新增的写入点扫描（`add_stock`/`deduct_stock_atomic` 调用点后 80 行内是否出现库位同步）对全仓 **23 个调用点**分类：**22 处已双写**，唯 `app/app.py:7218`（委外发料 `subcontract_issue`）无 `update_location_inventory` / `deduct_location_inventory_atomic` / `location_management_enabled`；并已确认该函数区间（7150–7330）内**没有任何库位写入**。
- **根因（代码实证）**：委外发料明细循环内只调 `deduct_stock_atomic(material.id, quantity, ..., warehouse=issue.warehouse)` 扣 **①总账**并写 **③流水**，**未同步②库位账**。而 `INVENTORY_TRUTH.md §2.1` 明确"`add_stock`/`deduct_stock_atomic` 不会自动同步库位账，调用方必须自己再调一次 `update_location_inventory`；**新代码必须两层同时写**"——调整单（`adjustment.py:451` 扣减 + `:481` 同步）等 22 处都遵守了，委外发料这一处漏了。
- **危害**：**开启库位管理时**，每发一笔料，①总账减少而②库位账不变 → 恒等式 `① = Σ②` 被打破；库存查询/报表（仓库级/库位级口径）与物料列表（全局总账）数字对不上，且**无任何报错**——与 `BUG-2026-08-16-002` 同型的**静默账实分裂**。关闭库位管理时不显现（无库位账可对照），属条件触发。
- **状态**：**已修复**（2026-09-20）。
- **修复（1 个 atomic action）**：`api_subcontract_quick_issue`（`app/app.py`，`/api/subcontract/quick_issue`）
  发料循环内新增库位账同步——`use_location = location_management_enabled()`；
  扣减成功后 `update_location_inventory(material, issue.location or issue.warehouse,
  -(quantity), warehouse=issue.warehouse)`，失败即 `rollback` 并显式报错。
  **库位键取值口径经用户拍板**：委外发料明细无 `location` 字段，回退发料单仓库
  （`issue.location or issue.warehouse`）——与反提交端 `subcontract.py:1380`
  （BUG-2026-08-16-001）**逐字一致**，避免扣减与回退落在不同库位。
- **回归**：新增 `tests/test_bug_2026_09_20_008_subcontract_issue_location_sync.py`
  **4 项**——①开启库位管理时发料后 ①=②（恒等式成立）；②库位键与反提交端同键
  （断言 `issue.location or issue.warehouse`）；③关闭库位管理时不改库位账（向后兼容）；
  ④库位账缺失必须报错且①未被扣（**不静默成功**）。
  **回退验证（证明锁有效，非自证）**：临时回退到修复前版本跑同一套用例，
  第 1 项失败（`②库位账必须同步扣减到 5`，实际仍为 10）、第 4 项失败
  （`库位账缺失必须报错，实际: success`——正是"静默账实分裂"的实证据）；
  恢复修复后 4 项全过。
- **R6 同根因排查**：23 个 `add_stock`/`deduct_stock_atomic` 调用点已全量分类，除本处外
  **22 处均已双写**（adjustment / in_order / out_order / subcontract_receive / requisition /
  mobile / native_api / after_sale_out），**无第二处缺口**。另核：网页版快速发料
  `/subcontract/<id>/issue`（`routes/subcontract.py:292`）与本 API 是**两套实现**，
  网页版早已同步（BUG-2026-08-16-001），本次修的是漏掉的那套。
- **生效条件**：路由逻辑改动，**需重启 WMS 服务生效**（R3）。
- **生效确认**：**已确认（2026-09-20 12:45）**——推送 `eafec63` 后
  `python scripts/check_ci_green.py` rc=0：三工作流全绿且均指向本次提交
  （`Android APK Build` #661、`WMS AI Verification` #1445、`WMS CI` #1150）。
  其中 `WMS CI` 的 unit-tests job 跑全量 pytest，已含本次新增的 4 项回归锁。
  判据：`scripts/verify_inventory_identity.py` 可复跑验证 ①=Σ②。
  ⚠️ 生产侧仍需**重启 WMS 服务**后本修复才对用户可见（R3 同源）。
- **⚠️ 本条 R6 排查结论不完备（2026-09-25 补充，见 BUG-2026-09-25-001）**：
  原文称「23 个调用点已全量分类…**无第二处缺口**」，**该结论是错的**——
  它把 `routes/subcontract.py` 的网页版当成了全部实现，**漏掉了
  `app/app.py` 里那套更老的 API**（收货方向同型缺口）。

### BUG-2026-09-25-001（2026-09-25，委外快速收货老 API 只写总账、不写库位账：BUG-2026-09-20-008 的同型第二处）

- **发现方式**：P2-3 批 5 收敛侦察——按「23 个调用点」逐点确认时发现，
  008 的 R6 结论把 `routes/subcontract.py::quick_receive_subcontract`（网页版，
  batch 4 已收敛）当成了 `subcontract_receive` 方向的**全部实现**，
  **漏掉了 `app/app.py::api_subcontract_quick_receive`**
  （`/api/subcontract/quick_receive`，老 API）——它与 008 修好的
  `api_subcontract_quick_issue` 同文件、同层。
- **根因（代码实证）**：该函数只调 `add_stock(material, quantity, …)` 写
  **①总账 + ③流水**，函数区间内**没有任何** `update_location_inventory` /
  `deduct_location_inventory_atomic` / `location_management_enabled` 调用。
  而 008 的修复只覆盖了**发料**方向，**收货**方向这套老 API 被漏掉。
- **危害**：**开启库位管理时**，每收一笔货 ①总账增加而②库位账不变 →
  恒等式 `① = Σ②` 被打破；且**无任何报错**——与 008 / BUG-2026-08-16-002
  同型的**静默账实分裂**。关闭库位管理时不显现（条件触发）。
- **状态**：**已修复**（2026-09-25）。
- **修复（P2-3 批 5 的一个 atomic action）**：`api_subcontract_quick_receive`
  改道唯一入口 `services.warehouse_stock_service.apply_stock_delta`
  （`transaction_type='subcontract_receive'`）。库位键不显式传入——
  本路由的 `SubcontractReceive` **未设 location 字段**，入口内部回退
  `location or _stock_location_from_warehouse(warehouse)`，与网页版
  `location or warehouse` **逐字一致**，收发两端不会落在不同库位。
- **同批一并收敛**：`routes/mobile.py` 4 处（扫码入/出库、草稿确认入/出库）、
  `routes/native_api.py` 2 处（Android 扫码入/出库）→ 同上入口。
  均为**纯重构**（等价性已逐条论证：开关判定与库位键口径与原实现同判）。
- **刻意未收敛**：`routes/requisition.py` 扣减侧用
  `deduct_location_inventory_atomic`，绕过 `update_location_inventory` 的
  「无库位记录且不允许负库存即失败」检查（BUG-2026-08-04-002 口径），
  收敛会**改变失败语义**，按 R8 不做净改变，**单独评估**。
- **回归**：新增 `tests/test_p2_3_mobile_native_receive_apply_stock_delta.py`
  **11 项**（结构锁 4 + 行为锁 7）。
  **回退验证（证明锁有效，非自证）**：临时回退 `app.py:7539` 到修复前，
  4 项立刻变红，其中 `test_quick_receive_api_syncs_location_inventory_when_enabled`
  报「②库位账未同步」——正是静默账实分裂的实证据；恢复后 11 项全过。
- **门禁同步**：`scripts/verify_wms_bugs.py` 的 `BUG-NEW2-001` / `BUG-NEW2-006`
  原先断言源码必须出现 `add_stock` + `update_location_inventory` 字面量，
  收敛后自然失效。已更新为「必须经入口 **且** 检查返回值」——**意图不变**；
  并**实测注入「忽略返回值」的坏代码仍被拦截**，证明断言未被削弱。
- **R6 同根因排查（本次做对的部分）**：全仓库存原语调用点重新分类，
  确认除上述 7 处外，`app.py` 仅余 2 处 `update_location_inventory`
  属**期初建账专用路径**（`_apply_opening_stock_balance` / 回冲，总账不走
  `add_stock`，不在收敛范围）；`quick_issue`（L7450）已被 008 修好，不重复改。
- **生效条件**：改动含 `app.py` 与路由逻辑，**生产需重启 WMS 服务生效**（R3）。
- **生效确认**：**已确认（2026-09-25 07:38）**——推送 `ae926776fdc2` 后
  `python scripts/check_ci_green.py` rc=0：三工作流全绿且均指向本次提交
  （`Android APK Build` #744 @42f6d10（本次未动 Android 代码，沿用上一提交）、
  `WMS AI Verification` #1537 @ae926776fdc2、`WMS CI` #1242 @ae926776fdc2，均 success）。
  其中 `WMS CI` 的 unit-tests job 跑全量 pytest，已含本次新增的 11 项回归锁。
  本地验证：专项 11 passed；全量 2675 passed / 86 skipped / 0 failed；
  `verify_wms_bugs.py` rc=0；`lint_wms_rules` 0 违规；`lint_no_raw_post_fetch` 通过。
  判据：`scripts/verify_inventory_identity.py` 可复跑验证 ①=Σ②。
  ⚠️ 生产侧仍需**重启 WMS 服务**后本修复才对用户可见（R3 同源）。

### BUG-2026-09-20-006（2026-09-20，R6「排查所有同类消费点」长期靠自觉：新增 A14 规则机械化）

- **发现方式**：修复 BUG-2026-09-20-004 过程中复盘——R6 自 2026-08-28 列入 AGENTS.md 后一直是**纯人工自检**（无 lint 防护），本次正是它失效：生产 Cookie 硬门禁引入后只改了 `tests/conftest.py`，`scripts/` 下 5 个同类消费点全部漏掉。
- **根因（代码实证）**：R1–R6 中 R2/R3/R7 已有 A11/A13/A12 三条机械化防护，唯独 R6（同根因多消费点）无对应规则；`scripts/lint_wms_rules.py` 对 `scripts/` 目录下的 app 导入链路完全无覆盖。
- **修复**：新增 **A14 规则**（`RuleA14ProductionGateConsumerOptIn`）——`scripts/*.py` 的 **staged 新增行**中若出现 app 引用（`from app import app` / `import app`）且脚本未显式设置 `WMS_ALLOW_INSECURE_COOKIE`（与 conftest 同口径的生产硬门禁 opt-in），则 pre-commit 拦截。放行条件：切 testing 环境 / 本次未新增 app 引用行 / 行尾 `# allow-no-optin`。**判定粒度刻意取"新增行是否引入 app 引用"而非"文件被改过"**——后者会把仅改空行的存量脚本判违规，误报不可接受（初版即踩此坑，已由 golden 测试第 5 例锁定）。同步更新 `DEVELOPMENT_RULES.md`（13→14 条 + A14 行 + 汇总行）、`AGENTS.md`（§六标题/目录/速查表 12→14 条、补登 A13+A14、§四 A1-A14、R6 补机械化说明——其中 A13 文案为本轮补漏）。
- **回归**：新增 `tests/test_lint_wms_rules_a14_golden.py` 6 项（无 opt-in 拦截 / 有 opt-in 放行 / testing 放行 / 不导入 app 放行 / 改空行不误报 / 存量脚本新增 app 引用行拦截）；连同 A13 golden 3 项 + 门禁相关 23 项共 32 项全绿；`lint_wms_rules` 0 违规。
- **生效条件**：改动拉取后本地 pre-commit 钩子即生效（无需重启服务）；CI lint 同步覆盖。
- **生效确认**：**已确认（2026-09-20 01:47）**——推送 `e9708d39` 后 `python scripts/check_ci_green.py` 返回 rc=0，三工作流全绿且均指向本次提交（`Android APK Build` #613、`WMS AI Verification` #1397、`WMS CI` #1102，均 success）。规则本身由 golden 测试六场景验证；A13 文案漏改一并补齐。

### WECOM-BOT-001（2026-09-14，新增能力：微信分享接入「企业微信群机器人」通道，非重复BUG）

- **背景**：本机助手 UI 自动化存在「微信窗口必须常开 + 不能切窗口」的**结构性**限制（BUG-2026-09-14-034 已修系统代理劫持回环，但窗口/焦点前提无法靠加固消除）。方案评估：无企业微信时第三方推送服务（WxPusher/PushPlus）均**只能发链接且需上传第三方图床**（隐私 + 有效期问题），故采用**免费企业微信群机器人 webhook**——唯一能同时满足「原生图 + 不开窗口 + 图片不出内网」的通道。
- **机制**：`POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX`，`image`（base64+md5，≤2MB）原生图直发 + `markdown` 摘要；国内 endpoint **直连**（`proxies={'http': None, 'https': None}`，复用 BUG-2026-09-14-034 思路，防代理错误路由出境被拒）；图片内联**不经过第三方图床**；每机器人限 20 条/分，批量推送单与单 `sleep(3)` 节流。
- **实现**：配置存 `system_setting['wechat_share_wecom_webhook']`（**免数据库迁移**）；新增 `_wechat_share_wecom_webhook` / `_wechat_share_wecom_webhook_allowed`（白名单仅 qyapi 官方 send 端点，防 SSRF/key 泄露）/ `_wechat_share_wecom_image_bytes`（>2MB Pillow 重编码）/ `_wechat_share_send_wecom` / `_wechat_share_deliver` **调度器**——配 webhook 走企业微信、未配回退本机助手（**完全向后兼容**）；`_wechat_share_order` 组装 markdown 摘要（单号/供应商/明细数/合计），重发路由同步分流；设置页新增 webhook 输入框（FormData + base.html 全局 fetch 拦截器，**免改 JS**）。
- **回归**：新增 `tests/verify_wecom_bot_001_channel.py` **8 项**（调度切换、image 载荷 base64+md5+proxies 直连、errcode 映射、超限重编码 JPEG、webhook 白名单、caption 先于图）；连同微信分享既有用例全绿；`lint_wms_rules` / `lint_no_raw_post_fetch` 0 违规。
- **生效条件**：**生产需重启 WMS 服务**（模板缓存刷新，R3）。真实联调需用户免费注册企业微信→建群加机器人→把 webhook 填入「微信分享」设置页→点「立即执行」验证（单元测试以 mock webhook 完成，未触达真实腾讯接口）。

### BUG-2026-09-14-034（2026-09-14，微信分享批量「HTTP 502」+ 健康检查 10090 超时：系统代理劫持本机回环请求）

- **发现方式**：现场报障。用户截图：微信分享记录批量「失败：微信发送助手返回错误：HTTP 502（错误码：http_502）」，当前状态面板「发送助手 不可用」，报错 `HTTPConnectionPool(host='127.0.0.1', port=10090): Read timed out. (read timeout=1.5)`，待发送/失败积压 160 条。
- **根因（代码 + 现场证据，非推测）**：服务器为拉取 GitHub 代码常驻代理软件。代理开启「系统代理」后写入 Windows 注册表/环境变量代理（监听 `127.0.0.1:10090`）。WMS 侧 `_wechat_share_send_image`（POST /send）、`_wechat_share_get_helper_health`（GET /health）与助手侧 `poll_once` 均用 Python `requests` 默认行为调用本机回环地址（127.0.0.1:8765 / 8080）；requests 读取系统代理后把回环请求路由到 10090，代理无法处理回环目标 → 回 HTTP 502（POST /send）或 read timeout（GET /health）。**关键佐证**：健康检查报错端口是 **10090（代理端口）而非 8765（助手端口）**——证明请求被发去了代理。与 BUG-2026-09-14-030 的 502（服务器后端进程停止）根因不同。
- **R6 同根因排查**：grep 全仓对回环 helper 的 requests 调用，确认消费点共 6 处——WMS 侧 2 处（app.py /send、/health）+ 助手侧 4 处（wechat_helper.py `poll_once` 的 GET tasks / GET image / POST report ×2），全部同一根因，本次一并修复；未发现其它对回环 helper 的 requests 调用点。
- **修复**：新增模块常量 `_LOOPBACK_NO_PROXY = {'http': None, 'https': None}`（app.py 与 wechat_helper.py 各一），6 处回环调用统一显式传 `proxies=_LOOPBACK_NO_PROXY`。原理：requests 合并环境代理用 `setdefault`，显式 `None` 优先生效，`select_proxy` 返回 `None` → 直连本机，与代理开关状态无关，用户无需「不用就关代理」。
- **回归**：新增 `tests/verify_bug_2026_09_14_034_loopback_no_proxy.py` 4 项——T1 /send 携带 no-proxy、T2 /health 携带 no-proxy、T3 机制证明（设 HTTP(S)_PROXY 且清 NO_PROXY 后，`merge_environment_settings`+`select_proxy` 仍返回 None 直连；对照组不传 no-proxy 时代理确被选中）、T4 助手源码静态断言（Windows-only 无法 import，按仓库惯例）；并为 008/010/012 现有测试桩补 `proxies` 形参适配新关键字。相关用例 **27 passed**（含 008/009/010/012 全绿）。
- **生效条件**：仅改 WMS 主服务与微信助手进程对本机回环的 HTTP 调用方式，不改业务数据、不改助手 UI 自动化/剪贴板/前台校验逻辑；**生产需重启 WMS 服务（及微信助手进程）生效**。

### BUG-2026-09-14-033（2026-09-14，Android 单元测试门禁自建起一直空跑：无测试目录、无测试依赖）

- **发现方式**：移动端工程质量走查（非现场报障）。属**流程性缺陷**——门禁显示绿色但从未拦住任何东西。
- **缺陷事实（两条并存，共同导致 `testReleaseUnitTest` 形同虚设）**：
  1. `.github/workflows/android-build.yml` 自 **BUG-2026-08-16-021** 起就包含步骤 `./gradlew testReleaseUnitTest`，但 **`app/src/test` 目录根本不存在**；
  2. `app/build.gradle.kts` 的 `dependencies` 里**没有任何测试依赖**（junit / robolectric / coroutines-test / androidx.test 全无）——即便写了测试也无法编译。
- **为何一直没被发现**：Gradle 对"零测试源"的 `testReleaseUnitTest` 任务会**以 NO-SOURCE 成功退出**，CI 显示绿色。门禁"看起来有"，实际从未运行过一行断言。
- **后果（这才是关键）**：项目所谓 55 个"Android 测试"**全部是 Python 正则匹配 Kotlin 源码字符串**——能防"某行守卫被删"，但**测不出任何运行时行为**。这正是 **BUG-2026-09-14-029（冷启动闪退）要修 5 轮才定位到真凶**的根因：每轮改完只能靠真机人肉验证，而沙箱/CI 又编译不了 APK，形成"盲改 → 真机复现 → 再盲改"的循环。
- **修复（补基础设施 + 首批真实测试）**：
  1. `build.gradle.kts` 新增 `testOptions.unitTests { isIncludeAndroidResources = true; isReturnDefaultValues = true }`（Robolectric 读资源与 Manifest 所必需）；
  2. 新增测试依赖：`junit:junit:4.13.2`、`org.jetbrains.kotlinx:kotlinx-coroutines-test:1.8.1`、`org.robolectric:robolectric:4.14.1`、`androidx.test:core:1.6.1`、`androidx.test.ext:junit:1.2.1`、`com.squareup.okhttp3:mockwebserver:4.12.0`、`androidx.arch.core:core-testing:2.2.0`；
  3. 新建 `app/src/test/java/com/factory/wms/` 及**首批真实可执行测试**（Robolectric，`@Config(sdk=[31])` 对齐现场机型 HUAWEI LIO-AN00）：
     - `RetrofitClientSessionTest.kt`（8 例）：锁死 `apiService` 在 baseUrl 未配置时**必须抛 IllegalStateException** 且消息可读（BUG-2026-09-14-029 的安全守卫语义——防后人为"不崩"而删守卫致 token 泄漏到占位地址）；尾斜杠容错；登出后守卫恢复；token 生命周期；共享 OkHttpClient 实例稳定（Coil 复用连接池）；`setBaseUrl` 并发读写不产生"新 baseUrl + 旧 retrofit"中间态。
     - `OfflineQueueStateMachineTest.kt`（8 例）：用**真实 Room 内存库**验证状态机——①`syncing` 记录确实取不到（**这就是静默丢数据的机制**）②`resetStuckSyncing` 后必须重新可见（BUG-2026-09-12-008 核心）③达上限记录落 `failed` 且被 `countFailed` 统计（用户必须看得见）④**出口完整性**：pending∪failed 覆盖全部非成功路径，任何记录不得停留在 syncing ⑤`resetToPending` 清零次数与原因（否则刚重置就被下次失败打回）⑥`upsert` 按 requestId 幂等（弱网重复点击不产生重复单据的本地保障）⑦补传按入队时间升序（防同物料先出后入被颠倒）。
- **回归**：新增 `tests/verify_bug_2026_09_14_033_android_unit_test_infra.py` 10 项——测试目录存在、含真实 `@Test`、3 个必需依赖已声明、Robolectric 资源开关已开、CI 仍保留 `testReleaseUnitTest`、**覆盖三个真实崩溃根因的契约**（baseUrl 守卫 / syncing 非终态 / 失败可见）、**反向断言禁止占位断言**（`assertTrue(true)` 之类糊弄门禁）、BUG 已登记基线。
- **验证局限性（如实记录）**：沙箱无 Kotlin 工具链且 Maven Central / GitHub Releases 下载均被网络策略阻断（kotlinc 13.7MB 处截断、repo1.maven.org 不可达），**本地无法编译运行该 Kotlin 测试**。已改用**逐项 API 签名一致性核对**代替：核对 6 个 `RetrofitClient` 成员、11 个 DAO 方法、7 个 Entity 属性、5 个常量、`data class`（`copy()` 依赖）、`AppDatabase` 抽象类声明——**全部与源码一致**。
- **CI 验收（已确认，含门禁有效性对照实验）**：
  - `Android APK Build` **#499**（`a9e4b132`，常规构建）：**全步骤 success**，含 `Unit tests (BUG-2026-08-16-021)` success；
  - **门禁有效性对照实验**：临时提交一个**必然失败**的测试探针（`assertEquals(1, 2)`），CI **#500**（`c100c254`）结果 `Unit tests` 步骤 **failure**，而 `Build Release APK (R8 瘦身)` 与 `Lint` **均 success**。该对照一次性证明三件事：①Kotlin 测试源**真实参与编译**（若测试有语法/依赖错误，编译与 Lint 阶段就会红，不会走到测试步骤）②Robolectric 及各测试依赖**正确解析** ③**门禁真实生效**——故意失败的断言被成功拦截。探针随后已移除，远端 main 重置回 `a9e4b132`（净变更零）。
  - **结论**：门禁从「`app/src/test` 不存在 → Gradle NO-SOURCE 空跑却显示绿色」变为「**有真实测试且能拦截失败**」，BUG-2026-09-14-033 完成闭环。
- **生效条件**：Android 改动；**不影响 APK 产物行为**（仅新增测试代码与 `testImplementation` 依赖，`implementation` 未变），无需重装。

### BUG-2026-09-14-032（2026-09-14，NavGraph 组合根饿汉创建全部 ViewModel：崩溃放大 + 启动开销 + 竞态温床）

- **发现方式**：移动端工程质量走查（非现场报障）。属**结构性缺陷**——无直接崩溃复现，但为既有崩溃的**放大器**，且是 BUG-2026-08-24-006 的**未根治根因**。
- **根因**：`AppNavGraph()` 函数体开头一次性创建 **14 个 ViewModel**：

  ```kotlin
  val authViewModel = viewModel()
  val inboundScanViewModel = viewModel(key = "inbound_scan")
  ... （共 14 个，含 4 个 ScanViewModel 副本）
  val overviewListViewModel = viewModel(key = "overview_list")
  ```

  `AppNavGraph` 是**全 App 的组合根**，在 `MainActivity.setContent` 第一帧即被调用——故这 14 行等价于「App 一启动就构造所有页面的 ViewModel」。

- **三个具体危害**：
  1. **崩溃放大（最严重）**：任一 VM 构造期抛异常 = 整个进程闪退。BUG-2026-09-14-029 的 `ScanViewModel.<init>` 抛 `IllegalStateException`（baseUrl 未配置）正是**被这里放大**成"打开应用即闪退"——若按需创建，该 VM 只在用户进入扫码页时才构造，最多是一个页面打不开，不会全 App 崩溃。
  2. **启动开销与内存常驻**：14 个 VM 及其依赖的 `WmsRepository` / Room DAO / 协程作用域全部常驻，其中语音/AI/期初/报表等页面用户可能从不打开。
  3. **竞态温床**：VM 在"会话尚未还原"（`AuthViewModel.init` 异步读 DataStore + EncryptedSharedPreferences，耗时数百毫秒）时已被构造，其 init 中的网络请求必然读到空 baseUrl。
- **R6 同根因排查（关键）**：命中 **BUG-2026-08-24-006**——其描述就是「`AppNavGraph` 组合阶段即创建 `ReportViewModel` 并在 init 立即 load()，与会话还原竞态 → 报表页报『服务器地址未配置』」。当时的修复是①`ReportViewModel.init` 改为不自动加载②`WmsRepository` 加 `ensureSession()` 兜底。**两处都是对症补丁，饿汉创建这个根因从未消除**——证据：`StocktakeRecordViewModel.init` 与 `ReportViewModel.init` 里都留着「BUG-2026-08-24-006：不能在 init 拉数据」的注释，说明**同一个根因已被迫用「禁止在 init 做事」这种约束反复绕行**，而 VM 本身仍在启动期被无谓构造。本次从根上消除，使这类约束不再必要。
- **修复（结构收敛，不改任何业务逻辑）**：
  - `AppNavGraph` **顶层只保留 `authViewModel`**（`startDestination` 依赖其 `isLoggedIn`，且必须在导航建立前存在）；
  - 其余 **13 个 VM 全部下沉到各自 `composable(...)` 路由内**按需创建（18 个创建点，含跨路由共用项）；
  - 语音悬浮层两个 VM 移入 `if (authState.isLoggedIn)` 分支内创建——未登录时完全不构造。
- **实例语义保持不变（关键论证）**：路由内 `viewModel()` 的宿主是 **Activity 级 `ViewModelStore`**，同一 key 跨路由**复用同一实例**，故：
  - 4 个 `ScanViewModel` 用不同 key（`inbound_scan`/`outbound_scan`/`stock_query`/`stocktake`）→ 各自独立，与修复前一致（否则入库明细会串到出库页）；
  - `AiViewModel` 在 `DocumentOcr`/`ObjectRecognize`/`StocktakeRecognize` 三处均用默认 key（按类型）→ **同一实例**，与修复前共享语义一致；
  - `VoiceOutDraftViewModel` 在语音悬浮层与 `Outbound` 路由两处同类型 → **同一实例**，语音建单草稿与出库页读写同一份状态；
  - 物料档案列表页与详情页共用 `MaterialArchiveViewModel` → 同一实例，选中态不丢。
- **用户可见影响**：启动时构造的 VM 由 14 个降至 **1 个**（登录页场景）；首屏后按实际访问逐个构造。启动更快、内存更低、**单页 VM 故障不再拖垮全 App**。
- **回归**：新增 `tests/verify_bug_2026_09_14_032_navgraph_lazy_viewmodels.py` 11 项——① 组合根顶层无饿汉创建（仅允许 authViewModel）② 反向保证 authViewModel 仍在顶层（防误下沉致启动落错页）③ 5 个带 key 的 VM 必须在路由内且 key 保留（防串页）④ 每个创建点必须位于 composable 路由或已登录分支内 ⑤ 语音 VM 受 isLoggedIn 守卫 ⑥ 同一 key 不得赋予不同 VM 类型 ⑦ BUG 已登记基线。**全绿**（预跑时基线未登记项按预期失败，证明测试有效）。
- **生效条件**：Android 改动，需产出新 APK 后重装；无需后端重启。

### BUG-2026-09-14-031（2026-09-14，Compose 列表 key 塌缩为常量致页面崩溃隐患：4 处 items key 兜底缺失）

- **发现方式**：移动端工程质量走查（非现场报障）。属**潜在缺陷**——当前后端 id 均为自增主键故未触发，但契约上未设防。
- **根因（形式）**：`items(list, key = { it.id ?: 0 })`。模型 id 声明为可空 `Int?`（`MaterialDto`/`AlertItemDto`/`MobileOrderDto` 均如此）。一旦后端下发 **2 条以上 id 为 null** 的数据（异常响应 / 分页拼接 / 未落库临时行），所有 key 塌缩为同一个 `0`；Compose `LazyColumn` **要求 key 唯一**，重复即抛 `IllegalArgumentException` → 页面崩溃。
- **关键设计原则（为何不能用常量兜底）**：`key` 的用途是「跨重组的稳定身份」。用常量兜底等于**主动放弃身份唯一性**——它不是"无害的降级"，而是把「数据异常」放大成「应用崩溃」。正确兜底必须逐级取**仍具区分度**的字段。
- **修复（4 处消费点，统一为「id 有效 → 业务唯一码 → hashCode」三级兜底）**：

  | 文件:行 | 修复前 | 修复后 |
  |---|---|---|
  | `ScanScreens.kt`（查库存列表） | `key = { it.id ?: 0 }` | `key = { it.id ?: it.code ?: it.hashCode() }` |
  | `OverviewListScreen.kt`（库存告警） | `key = { it.id ?: 0 }` | `key = { it.id ?: it.code ?: it.hashCode() }` |
  | `OverviewListScreen.kt`（单据下钻） | `key = { it.id ?: 0 }` | `key = { it.id ?: it.orderNo ?: it.hashCode() }` |
  | `StocktakeRecordScreens.kt`（盘点记录） | `key = { it.id }` | `key = { if (it.id != 0L) it.id else it.checkNo ?: it.hashCode() }` |

- **第 4 处为 R6 扩展命中**：`StocktakeRecordDto.id` 是**非空 `Long = 0`**，`key = { it.id }` 静态看"安全"，但该默认值使其与前者**同根因**——Gson 反序列化遇缺失字段落 0，多条即冲突。既然在修同一根因，一并收敛（R6：同根因全量排查，不修一半）。
- **R6 同根因排查**：全项目 `items(...key=...)` 共 6 处，逐一核验——`MaterialArchiveScreens.kt:224`（三材料三级兜底）与 `:552`（图片 `id ?: hashCode`）**原本就是正确范式**，本次修复即以其为参照标准；其余 4 处为本次修复对象。修复后全项目**零**常量塌缩 key。
- **回归**：新增 `tests/verify_bug_2026_09_14_031_list_key_uniqueness.py` 7 项——①~③ 三处消费点 key 必含 `hashCode()` 兜底 ④ 盘点记录 key 必判 `id != 0L` 且含 `checkNo`/`hashCode` ⑤ **全项目反向断言**（正则扫描所有 `key = { }`，禁止 `?: 0` / `?: ""` 常量塌缩——根因形式的机器可检约束）⑥ 既有正确范式（MaterialArchiveScreens）不得被误伤 ⑦ BUG 已登记基线。**11 passed**（含修复前预跑：基线未登记项按预期失败，证明测试有效）。
- **生效条件**：Android 改动，需产出新 APK 后重装；**当前无现场触发路径，属预防性修复**，不影响既有已装版本正常使用。

### BUG-2026-09-14-030（2026-09-14，手机登录「502」：服务器后端进程停止，非 App/代码缺陷）

- **现场**：用户装 3.8.3 后 App 正常打开进入登录页（029 闪退已愈），点登录报「登录失败(502)」。
- **R6 同根因排查**：命中 BUG-2026-08-11-001（登录 502）——但该次是**后端在跑、`WMS_NO_DB_TOUCH=1` 缺表 → `/api/login` 未捕获 OperationalError → 500**，仅登录接口异常。本次外网实测 `https://gd2026.top` **首页、登录接口全部端点 502**，响应头 `Server: nginx/1.30.0` —— nginx 网关存活、上游 WMS 后端（Waitress `0.0.0.0:8080`）整体不可达。**不同根因：后端进程停了，不是后端报错。**
- **判定**：`start_wms_auto.bat` 以前台控制台进程运行后端（窗口打印 "Press Ctrl+C to stop"），**窗口被关闭 / 服务器重启或休眠即后端停止** → nginx 对全部请求回 502。非代码缺陷，不改代码。
- **处置与恢复验证（外网实测）**：服务器侧重跑启动脚本后，首页 302→`/login` 200（登录页正常渲染）、`POST /api/login` 对测试账号返回 401「账号或密码错误」（正常业务响应，证明 nginx→Waitress→数据库全链路健康），用户随后真机登录成功。
- **遗留风险与建议（未实施，待用户确认）**：生产后端依赖前台窗口进程，关窗/重启/休眠 = 全员断联且无自愈。建议注册为 Windows 服务或任务计划程序（开机自启 + 崩溃自动重启 + 无窗口常驻），一次性配置彻底消除该风险。

### BUG-2026-09-13-025（2026-09-14，分发链核验：用户"解析包时出现问题"= 下载截断，非代码缺陷）

- **现场**：用户装包后截图系统提示「解析包时出现问题」，无法安装。
- **判定**：**不是代码缺陷**。安卓在解析阶段即拒收，说明 APK 文件头尾不齐——下载中途断流。正常包 `25,095,687` 字节；截断包无 EOCD 结尾，非合法 ZIP。
- **核验动作**：从固定 Release（tag `android-apk`）重新拉取，逐项校验并留证：

  | 校验项 | 结果 |
  |---|---|
  | 文件大小 | 25,095,687 字节（与 CI 产物一致） |
  | ZIP 结构（EOCD） | 通过，`testzip()` 无损坏项 |
  | 条目数 | 424 |
  | 包名 / 版本 | `com.factory.wms` / versionCode **14**、versionName **3.8.0** |
  | MD5 | `bf2bdbcb548dc61b04df857813bec865` |
  | SHA256 | `6c51f8ebb324fa1157c8b53926f8e7e3…` |

- **CI 全绿（本轮）**：`#488 Android APK Build` success（`e5eff9c`）、`#1272 AI Verification` success、`#977 WMS CI` success。对照 `#486` 为 failure（即 `BUG-2026-09-13-024` 的那次回归，该次**无包产出**）。
- **字节码级验收（androguard，两代包对照）**：

  | 验证项 | 线上固定 Release 包 | 工作区旧包 |
  |---|---|---|
  | `MainActivity.onCreate` 权限相关调用数 | **0** | **0** |

  两代包均确认启动期权限申请已移除（对应 `BUG-2026-09-13-023` 第二根因修复）。
  注：`encryptedPrefs` / `getSavedToken` 等私有成员名经 R8 混淆后无法在字符串池直接检索，故改以**方法调用序列**为验收口径——`MainActivity.onCreate` 的指令级调用数是不可伪造的硬证据。
- **全量测试**：`1726 passed / 85 skipped / 0 failed`。
- **分发结论**：固定 Release 直链
  `https://github.com/SIX2090/wms/releases/download/android-apk/wms-mobile-scan.apk`
  每次推送后由 CI 自动覆盖，永远为最新包。工作区 `/workspace/wms-mobile-scan.apk` 已替换为 #488 产物（MD5 同上）。
- **教训**：**"装不上"与"装上了崩"是两条完全不同的路径**，前两轮把「解析包失败」并入「启动崩溃」一起排查，属于归因错误。分发链完整性应作为独立环节先验，再谈代码。

### BUG-2026-09-13-024（2026-09-14，我造成的回归：陈旧基线导致 6 个公共 API 与 3 个源文件被删，APK 构建 40 处编译错误）

- **现场**：`Android APK Build #486`（远端 `7d2f81c6aa`）`step 8 Build Release APK (R8 瘦身)` = failure，卡在 `:app:compileReleaseKotlin`，**40 处错误全部集中在 `ScanViewModel.kt`**：
  ```
  e: ScanViewModel.kt:151:34 Unresolved reference 'editDraftKey'
  e: ScanViewModel.kt:190:24 Unresolved reference 'saveEditDraft'
  e: ScanViewModel.kt:265:37 Unresolved reference 'getLocationOptions'
  e: ScanViewModel.kt:1041:60 Too many arguments for
      'suspend fun submitInbound(request: InboundRequest): Result<SubmitResult>'
  e: ScanViewModel.kt:1109:72 No parameter with name 'replay' found
  ```
  因该包未产出新 APK，**用户手机上仍是旧包**——这正是"修了一百遍还是修不好"的直接原因：改动根本没到用户手上。
- **根因**：上一提交 `bda6623` 修启动崩溃时**基线取错**——编辑的是本地工作树中一份陈旧副本，而非远端最新版。该提交把远端 `WmsRepository.kt` 从 **933 行裁到 863 行**，删除 6 个已被 `ScanViewModel` 依赖的成员（`editDraftKey` / `saveEditDraft` / `loadEditDraft` / `getLocationOptions` / `submitInbound(requestId)` / `submitOutbound(requestId, replay)`），并连带删除 3 个源文件（`data/model/LocationOptions.kt`、`data/model/ScanEditDraft.kt`、`ui/components/ScanLocationSelector.kt`）。
- **为何本地与 AI 自查都没拦住（本次最重要的方法论教训）**：
  ① 沙箱无 Compose/AGP，本地编译只能做「基线 vs HEAD 错误集**差集**」。而当时对比的两侧**都带这个缺陷**，差集为空 → 误判为"干净"。**差集法只能发现「本次新增」，发现不了「本来就不该被删的」。**
  ② 更早一轮还误判过「本地 main 与远端同源」：实际 `git merge-base HEAD origin/main` **为空**（零共同提交），本地是一条与远端完全无关的历史。在该前提下做的所有"基线对比"都不可信。
  ③ CI 日志一度取不到（`actions/jobs/*/logs` → 302 到 `productionresultssaN.blob.core.windows.net`，沙箱 DNS 把它解析到伪 IP `198.18.0.33` 导致 TLS 失败；`WebFetch` 又在 Android SDK 许可协议大段文本处被截断）。**本次打通方法**：用 `223.5.5.5` 的 DoH 拿真实 IP，再 `curl --resolve <host>:443:<真实IP>` 直连，成功取得 191,908 字节完整日志——**这是拿到真实编译错误的唯一路径，后续勿再走弯路**。
- **修复**：将 `WmsRepository.kt` / `AuthViewModel.kt` 逐字节恢复到 `cc73fb0`（#485 全绿）版本。核对确认远端**已有等价且更完整的启动崩溃防护**（即 BUG-2026-09-13-023：`encryptedPrefs` 可空降级 + `resetSecurePrefsFile` 自愈 + `AuthViewModel.init` 整体 try/catch），故 `bda6623` 的这部分改动本身即为**重复实现**，回退无功能损失。
- **保留项**：`bda6623` 中唯一确有增量价值的一项——`WmsApplication` 的**进程级崩溃落盘器**（`setDefaultUncaughtExceptionHandler` → `filesDir/crash/last_crash.txt`）。现场此前只有"屡次停止运行"一句系统弹窗、拿不到任何堆栈，该装置让下次崩溃可直接定位；刻意**不吞异常**（原样交回系统默认处理），避免把崩溃变成静默数据错误。
- **验证**：
  - 本地 kotlinc 全树编译（排除 Compose 包）**0 error**；对照修复前同一条命令报 **40 error，与远端 CI 日志逐条一致**。
  - `WmsRepository.kt` / `AuthViewModel.kt` 与 `cc73fb0` **逐字节一致**（`git hash-object` 相同）；`WmsApplication.kt` 仅新增 `installCrashLogger()` 定义 + `onCreate` 内一行调用。
  - `tests/verify_android_startup_crash_safety.py` **6/6 passed**；**逐条破坏性测试复验**：去掉 try/catch、去掉处理器安装、让处理器吞异常——三种注入均被捕获。其中"只定义不调用"一项经复验确认为**空跑**（只断言 `installCrashLogger` 字符串存在，函数定义本身就能满足），已改为按花括号配平取 `onCreate` 体、校验内部确有调用。
  - 关联启动/编译门禁 **26 passed**；**全量 pytest 1727 passed / 84 skipped / 0 failed**（较修复前 1563 passed 多出 164 项——即被误删文件所携带的测试已回归）。
  - 远端 `66cd2c0f9c`：**`Android APK Build #487` = success（13 步全绿，含 assembleRelease / lintRelease / testReleaseUnitTest / 上传 / 发布 Release）**、`WMS AI Verification #1271` = success、APK 资产已更新至 `2026-09-14T03:02:03Z`（25,095,687 字节）。
- **R6 固化的规则**：
  ① 改任何文件前，先确认本地基线即远端最新（`git merge-base --is-ancestor HEAD origin/main` 非空且 `git diff origin/main -- <file>` 为空），**不得凭工作树现状假设基线正确**；
  ② Android 编译验收以 CI `assembleRelease` 为准，差集法不得作为"无新增错误"的充分证据；
  ③ 取 CI 日志用 DoH 真实 IP + `--resolve` 直连，不因 302/截断就放弃取证。

## 判定规则

| BUG-2026-09-13-008 | [P0] 微信助手编码损坏及字面反引号换行导致 SyntaxError，模块无法加载且全量 pytest 收集中断 | **已修复并验证（2026-09-13），发布以本次 Git 记录为准**：根因为 f46e472/27b330a 的错误文本写入；依据原始 51ddf0c 恢复完整 UTF-8 内容和被吞并的代码行，保留预期的中文安全错误提示，改为只记录异常类型的 warning，禁止回传异常原文或 traceback 刷屏。R6：复查 BUG-2026-08-11-009 与 08-16-019；恢复既有发送串行锁、焦点校验、无 token 拒绝逻辑，不触发实际微信发送。新增模拟 /send 解析异常的回归，相关 pytest 12 passed；py_compile 通过。全量 pytest tests -q --tb=short：1626 passed、85 skipped、4 failed（253 秒），四项均为既有 Windows 路径和图片文件占用问题：test_auto_migrate_db_path 两项、test_material_image_static_path 两项；收集阻断已解除，未进行真实微信发送。 |
| BUG-2026-09-13-011 | [P1] AI 草稿校验（`_ai_check_draft`）用全局 `Material.stock` 做库存校验，多仓库口径串仓/误判（原文编码损坏，本条依据残留技术关键词重建，请以 Git 历史为准） | **已修复（2026-09-13，重建）**：按单据仓库（`order.warehouse`/`from_warehouse`）解析仓库并改用仓库级 `get_warehouse_stock_quantities` 校验；R6 同类点已排查。验证：py_compile 通过；生产需重启 WMS 服务生效。 |
| BUG-2026-09-13-010 | [P1] AI-SALES-F02 shortage analysis used global Material.stock and a 50-row query limit, causing cross-warehouse false shortage results and incomplete counts | Fixed 2026-09-13: both consumers now validate SalesOrder warehouse and use get_warehouse_stock_quantities; invalid/empty historical warehouses are skipped with a warning; count scans the full result set while display remains capped at 5. R6 checked _ai_sf_query_short_stock and _ai_sf_query_customer_followup_list. Verification: py_compile, static gates, and 8 regression tests passed. Production requires WMS service restart. |
| BUG-2026-09-13-009 | [P1] 委外发料快速发料、新增明细、完成入口使用全局 `Material.stock` 校验，跨仓库会误判库存；完成入口同物料多行未累计需求可绕过库存限制 | **已修复（2026-09-13）**：三处入口统一按单据仓库解析 `validate_inventory_warehouse` + `get_warehouse_stock_quantities` 校验；新增明细和完成入口累计同物料需求；保留原子扣减、负库存开关、历史仓库兼容和人工完成边界。R6：同类点已排查并一次覆盖快速发料/新增明细/完成三处。验证：委外库存与删除流水回归 26 passed；py_compile、git diff --check、静态门禁待提交前执行。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-007 | [P1] 领料草稿保存缺少仓库函数导入导致保存失败；新增无库存检查、修改和批量未累计同物料需求 | **已修复并验证（2026-09-13），发布以本次 Git 记录为准**：补齐保存导入，保存/新增/修改/批量统一按单据仓库校验累计需求，修改排除自身旧数量、遵守负库存设置，错误消息使用仓库库存。整单失败主动回滚，批量保持部分成功语义。R6：对照 BUG-2026-08-16-016、09-13-002/006，领料同类点已排查；完成仍走带仓库的原子扣减，导入草稿由完成兜底，不改变人工提交边界。新测试 tests/test_bug_2026_09_13_007_requisition_stock.py 修复前 9 failed/12 passed，修复后 21 passed；加上库存、库位必填、删除锁、领料人及自动推单回归共 68 passed。双仓、历史编码流水、明细累计和草稿不改库存均验证。全量 pytest 因旧 wechat_helper.py 语法错误在收集期中断；排除该文件的尝试在 240 秒超时，不能报告全量通过。 |

| BUG-2026-09-13-006 | [P1] 调拨草稿新增、修改、批量添加仍使用全局库存；表格保存与明细入口未累计重复物料需求 | **已修复并本地验证（2026-09-13），推送以本次 Git 记录为准**：四个草稿入口按来源仓库校验，单行修改排除自身原数量，新增与批量加入既有行需求；表格整单保存累计请求数量，超额回滚。批量保持原有部分成功语义，只累计实际接受行；负库存开关一致生效。新增 16 项真实 SQLite 路由回归，覆盖空源仓/其他仓充足、历史 NULL warehouse_id 编码流水、重复行超额、失败保留原明细、草稿不写库存及总账等于两仓合计。相关四文件测试 57 passed。修正两个原回归夹具：为库位必填测试提供真实仓库库存；完成校验测试直接构造历史草稿，不再依赖空仓通过保存。R6：对照 BUG-2026-08-16-008 与 BUG-2026-09-13-002，同类点已排查，transfer.py 中剩余全局库存校验均清除；完成/反提交沿用现有累计校验并回归通过。Excel 导入属于草稿录入，不以库存充足作为导入承诺，最终完成仍有库存门禁。跨模块领料、委外、销售与 AI 草稿问题不在本次修复完成范围，仍待处理。验证命令：python -m pytest tests/test_bug_2026_09_13_002_warehouse_deductions.py tests/test_bug_2026_08_16_008_transfer_off_branch_source_stock.py tests/test_inv_audit_005_warehouse_active_validation.py tests/test_p1_transfer_location_required.py -q。 |

| BUG-2026-09-13-005 | [P1] 分区盘点在实盘汇总前跳过零差异区域，导致实盘漏计、盘盈被算成盘亏，并绕过多库位合并限制 | **本地修复并验证，远程发布待核验（2026-09-13）**：有区域行无论行级差异是否为零都参与合计与库位边界校验，最终净差异为零才不生成调整。R6：同类点已排查，扫码独立调整走差异求和而非分区实盘减单份账面，零差异过滤不影响其和，未修改其语义。新增 6 项真实 SQLite 路由回归（盘盈+2、合计无差异、盘亏、单区零差异、全部零库存、多库位包含零差异区域时拒绝），与区域保存/复制回归共 13/13。全量 1588 passed/85 skipped/4 failed；4 项在原始 SHA 51ddf0c 上同样失败，均为 Windows 路径/图片文件占用既有测试问题；静态回归通过。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-004 | [P1] PC 盘点保存忽略区域且只按物料匹配，重复新行重复计差异、多区域互相覆盖；Excel 同类入口漏防重复区域 | **本地修复并验证，远程发布待核验（2026-09-13）**：表格按物料+区域 upsert，拒绝请求内重复键、历史重复行显式要求处理；库位启用时区域必填。页面新增区域录入、复制、提交和回显；Excel 接收区域并跳过重复键/缺库位行。R6：复查 09-02-004、09-06-005；同类点已排查，扫码批次已有物料+区域键，复制已保留区域，单行添加已有物料判重。`pytest tests/test_bug_2026_09_13_004_check_row_identity.py tests/test_bug_2026_09_13_003_check_warehouse_freeze.py tests/test_inv_batch_001b_check_freeze_upsert.py tests/verify_bug_2026_09_03_001_check_import_warehouse.py -q` 20/20；涵盖重复拒绝无部分写入、多区域往返/删除/冻结、库位必填、人工完成后仅生成调整草稿、Excel 判重。**生产需重启 WMS 服务生效**。 |

| BUG-2026-09-13-003 | [P1] 已冻结盘点单换仓后沿用旧仓账面，导致调整错误归属新仓库 | **本地修复并验证，远程发布待核验（2026-09-13）**：保存写锁内按仓库 ID 校验冻结身份，有明细禁止换仓；同仓名称/编码等价，空单可选新仓。R6：复查 BUG-2026-09-02-004 与 09-03-001，同类点已排查，其他盘点更新不修改仓库、导入已拒绝同单跨仓。`pytest tests/test_bug_2026_09_13_003_check_warehouse_freeze.py tests/test_inv_batch_001b_check_freeze_upsert.py -q` 9/9（换仓拒绝且原行不变、编码别名、空单换仓、原冻结回归）。生产需重启 WMS 服务生效。 |

| BUG-2026-09-13-002 | [P1] 关库位模式下售后出库、负向库存调整、正向调整反提交仍只校验全局总账；调拨完成未累计重复物料，反提交未校验调入仓余额，导致串仓和负库存 | **本地修复并验证，远程发布待核验（2026-09-13）**：`deduct_stock_atomic` 在物料写锁内按仓库检查余额，覆盖所有携带仓库的扣减消费点；保留全不可归属历史反提交兼容。调拨完成与反提交累计同物料数量并在写流水前拒绝超额。R6：复查 BUG-2026-08-16-008/009 与 08-18-002，同类点已排查，统一扣减入口同时覆盖委外发料等遗漏点。回归 `tests/test_bug_2026_09_13_002_warehouse_deductions.py` 10/10（三类扣减失败回滚及成功、历史编码流水、多行调拨双向扣减、总账=各仓合计）；库存相关扩大回归 372 passed/10 skipped/1 Windows 启动测试失败待基线核验；`scripts/verify_wms_bugs.py` 通过。审计旧夹具补齐真实库存，禁止用空仓成功反提交作为预期。生产需重启 WMS 服务生效；提交/推送结果以 Git 记录和交付报告为准。 |

| BUG-2026-09-13-001 | [P2·资源错配] **Waitress 线程数写死默认 16，与部署机实际核数脱钩**：`run_server.py` 原为 `threads = int(os.environ.get("WMS_THREADS", "16"))`——该值是 2026-08 为缓解生产日志 queue depth 12 由 8 上调而来，但**当时未与 CPU 核数挂钩**。生产实际为 2 vCPU / 2GB 腾讯云低配机（任务管理器实测内存常驻 70%）：Python GIL 下同进程纯计算无法多核并行，16 线程在 2 核机上**不增吞吐**，只徒增内存占用（每线程栈 + 每请求 Flask 上下文）与上下文切换开销，内存压力反过来加剧慢请求与 `waitress.queue` 排队 | **已修复（2026-09-13）**：新增 `_default_waitress_threads()`（**4 起步、每核 4、封顶 16**——2 核→8、4 核及以上→16 保持既有行为不变）与 `_resolve_waitress_threads(env)`（`WMS_THREADS` 显式设置且非空白时优先，空串回落自适应默认，非法值维持 int() 启动期快速失败）；`main()` 改用 `_resolve_waitress_threads(os.environ)`。R6：已 grep 台账无"线程数默认值"同类历史（8→16 注释为唯一相关记录，本次在其语义上扩展而非回退）；同类消费点已排查——`app.py`/`start_qa_server.py` 的 `threads=8`/`threads=4` 为 CI/QA 专用入口，不受影响。回归：`tests/test_bug_2026_09_13_001_adaptive_threads.py` 6/6（核数缩放 / 封顶 16 / cpu_count=None 兜底 / 环境变量优先 / 空串回落 / 反向断言源码不再含写死 "16"）+ 既有 `test_run_server_port_hint.py` 1/1。**生效条件**：纯后端改动，拉取后**重启 WMS 服务生效**；需保留 16 线程的现场可设 `WMS_THREADS=16` 显式固定 |
| BUG-2026-09-10-011 | [P2] 手机端错误提示吞掉服务端原因：`WmsRepository` 有 **20 处** `catch (e: Exception) { Result.failure(Exception("网络错误: ${e.message}")) }`，而 `handleResponse` 本身已正确透传服务端 `msg`（如「请选择进行中的盘点单」「请选择仓库」）——外层 catch 把它覆盖成「网络错误: ...」，现场看到"网络错误"却反复重试（实为业务前置条件未满足，网络完全正常）；`getMaterialInfo` 的缓存兜底分支同样吞原因 | **已修复（2026-09-10）**：新增 `WmsRepository.BusinessException`（companion object 内，标记"服务端已给出明确原因"）+ 私有 `safeCall { }` 统一包装——先捕获 `BusinessException` 原样放行，仅兜底 `catch (Exception)` 才标注「网络错误」；`handleResponse` 三条失败路径（success 无 data / envelope 非 ok / HTTP 非 2xx）统一产出 `BusinessException`；**20 处调用点全部收口**（含 3 个 submit 级联 catch、日报逐页翻页、期初库存保存、物料缓存兜底）。R6：`grep 网络错误` 复查无存量未收口写法。回归：`tests/verify_bug_2026_09_10_011_repository_error_message.py` 6/6（BusinessException 位置 / safeCall 捕获顺序 / handleResponse 产出类型 / **无遗留直包写法** / 关键接口走 safeCall / 级联 catch 放行）。**生效条件**：Android 改动，需产出新 APK 后重装 |
| BUG-2026-09-12-008 | [P0·静默丢数据] **离线队列补传失败不回写状态，记录永久卡死 `SYNCING`（AI-MOB-OFFLINE-01 自身缺陷，且属 R6 复发）**：`OfflineQueueManager.doSync()` 中 `replay(op)` 返回 `false`（"未知作业类型"这类确定性失败）时走 `else { failCount++ }`，**未调用 `markFailure` 回写状态**；而该行此前已被 `dao.markSyncing()` 置为 `syncing`。致命点在于**三处消费点全部按状态过滤**——`listPending()` 只取 `status='pending'`（补传再也取不到它）、`countPending()` 只算 pending、`countFailed()` 只算 failed——于是这条作业在**补传队列、待同步角标、失败告警三个界面上同时消失，UI 完全无感知**，唯一出路是 App 进程重启触发 `resetStuckSyncing()`。讽刺之处：`PendingOperationDao.kt:55-56` 的注释白纸黑字写着「不复位就永远补传不出去——**静默丢数据，正是本任务要根治的问题**」，即该功能正是为消灭静默丢数据而建，却在错误分支里把同一问题重造了一遍。R6：已 grep 全仓 `markSyncing` 写入点（仅 1 处）、`STATUS_SYNCING` 引用点（仅实体/DAO/本类），确认同类消费点仅此一处 | **已修复（2026-09-12）**：`else` 分支补 `markFailure(op, "未知作业类型 \`${op.operationType}\`，无法补传", forceFail = true)` 并加 `Log.w`；因"未知类型"重试一万次也不会变，故 `forceFail=true` 直接落 `failed` 交人工处理（而非回 pending 空转）。同时把 `replay()` 的 KDoc 改为显式声明「**false 表示确定性失败，调用方必须回写状态，绝不可直接丢弃返回值**」，把契约钉在签名文档上，防止后续新增 `return false` 路径再犯。<br>**附带修正（同根因文案）**：`buildSummary()` 全失败分支原文案为「N 条同步失败，**请检查网络**后重试」——但失败原因可能是业务拒绝（盘点单已结束）或未知类型，与网络无关，会让作业员反复切网络却始终无效（与 BUG-2026-09-10-011「把非网络原因说成网络原因」同模式）。改为「N 条同步失败，已保留在本机待处理（详见失败列表）」。<br>**验证**：`tests/verify_bug_2026_09_12_008_offline_queue_state_machine.py` 10/10。其中 `test_008_syncing_not_terminal_in_behavior_model` 是**可执行状态机模型**——把 Kotlin 逻辑等价翻译为 Python 真实跑一遍"补传返回 false"路径，断言①无任何记录停留在 syncing ②未知类型记录落 failed 且能被 `countFailed` 统计 ③成功记录被删除；并内置**对照组**复现修复前行为（老实现下该行停在 syncing 且 `countPending()==0 && countFailed()==0`），证明缺陷真实存在而非臆测。`test_no_syncing_written_without_writeback_paths` 额外断言 `markSyncing` 全类仅 1 处调用且失败出口 ≥2 处，锁住"状态机出口完整性"。<br>**同类点已排查**：`markSyncing` 前的 `break`（中途断网）发生在置状态**之前**，当前条仍为 pending，不存在残留路径——已核对控制流顺序。**生效条件**：Android 改动，需产出新 APK 后重装；无需后端重启 |
| BUG-2026-09-12-009 | [P1·信任性缺陷] **`enqueue()` 非 suspend，落库前就返回 true，向用户谎报"已暂存"**：`OfflineQueueManager.enqueue()` 签名为非 suspend 的 `fun ... : Boolean`，内部 `scope.launch { dao.upsert(...) }` 后**立即 `return true`**；调用方 `WmsRepository.submitWithOfflineFallback` 拿到 `true` 即抛 `OfflineQueuedException`，UI 显示「网络不可用，XXX 已暂存，联网后自动提交」。但此刻写库**可能尚未发生、甚至可能失败**（磁盘满 / DB 损坏 / 序列化异常）——数据并不在本地，用户却被引导放心离开。此缺陷比 008 更隐蔽：**只在失败时反向暴露**（正常路径行为正确），属"善意 bug"（函数内确有仓库必填硬校验，看着严谨）。离线暂存这条链路的全部价值就建立在"暂存一定成功"上，返回值却与真实结果无关 | **已修复（2026-09-12）**：①`enqueue` 改为 `suspend fun`，直接 `return runCatching { dao.upsert(...); refreshCounts(); true }.getOrElse { Log.e(...); false }`——**落库完成才返回**，失败明确返回 false；②调用方 `submitWithOfflineFallback` 本就在 suspend 上下文，直接 await 无需改语法；③**同时修正失败分支文案**：原为 `Exception("网络错误: ${e.message}")`，统一把原因说成网络（同 BUG-2026-09-10-011 模式，实际可能是本地存储异常，会误导排查方向），改为 `Exception("提交失败且本地暂存未成功，请保持本页重试（原因：${e.message}）")`，明确告知"数据没保住"，让用户自己决定重扫或重试。<br>**验证**：`test_009_enqueue_is_suspend`（含**反向断言**：函数体内不得再出现 `scope.launch` 异步落库后立即 return 的旧写法）、`test_009_enqueue_failure_returns_false`（失败分支必须返回 false）、`test_009_repository_does_not_lie_when_queue_fails`（入队失败不得复用"已暂存"措辞）。**同类点已排查**：全仓 `grep "\.enqueue("` 仅 1 个调用点；`grep "return true"` 确认无其他 fire-and-forget 假成功。**生效条件**：Android 改动，需产出新 APK 后重装 |
| BUG-2026-09-12-010 | [P1·重复扣库存] **三个提交入口无 `isLoading` 守卫，弱网重复点按产生重复单据**：`ScanViewModel` 的 `submitInbound` / `submitOutbound` / `submitStocktake` **在置 `isLoading=true` 前后均无并发守卫**（`grep "if (_uiState.value.isLoading)"` 计数为 **0**），UI 三个确认按钮的 `enabled` 也不含 `isLoading`。当前仅靠 `onClick` 中先 `showSubmitDialog = false` 关掉弹窗、按钮随对话框消失来遮蔽——**纯时序侥幸**：一旦弹窗改为不关闭、或用户极速双击/手势穿透、或后续加"重试"按钮，即触发重复提交。而每次提交都会 `newRequestId()`（`UUID.randomUUID()`）生成**全新幂等键**，后端 `mobile_api_idempotent` 只能对**同一** key 去重，**无法识别两次不同 key 的相同业务**→ 两张单据、库存扣两次。这是"幂等键只防重试不防重复提交"的语义盲区 | **已修复（2026-09-12）**：**双层防护**——①ViewModel 三个入口各加 `if (_uiState.value.isLoading) return@launch`，置于 `val state = _uiState.value` 之前（源码守卫，与 UI 无关）；②UI 三个确认按钮 `enabled` 追加 `!uiState.isLoading`。盘点按钮因原已带「仓库+盘点单必选」前置校验，改为**与运算追加**而非覆盖（`enabled = selectedWarehouse != null && selectedCheckOrder != null && !isLoading`），保住原有校验不被削弱。<br>**验证**：`test_010_all_submits_have_isloading_guard`（三个方法都有守卫，且断言**守卫位置必须在置 `isLoading=true` 之前**，否则会自己挡住自己）、`test_010_ui_buttons_disabled_while_loading`（三个按钮的 `enabled` 表达式块均含 `!uiState.isLoading`，并断言盘点按钮的两项前置校验仍在）。<br>**回归影响（已修）**：本次改动打坏了既有测试 `tests/verify_android_stocktake_check_order.py::test_screen_ui_and_confirm_gate`——该测试断言按钮 `enabled` 为**单行字面量** `"uiState.selectedWarehouse != null && uiState.selectedCheckOrder != null"`，被多行写法打破。已将该断言改为**语义断言**（从 `viewModel.submitStocktake()` 调用点定位按钮块，断言块内含盘点单校验 + isLoading 守卫），既保留原意又不再依赖格式；该文件 6/6 通过。**生效条件**：Android 改动，需产出新 APK 后重装 |
| BUG-2026-09-12-011 | [P1·承诺未兑现] **离线队列靠扫码页懒加载初始化，"联网自动补传"对部分用户路径完全不生效**：`WmsApplication.onCreate()` **没有任何离线队列预热**（`grep "syncPending\|offlineQueue"` 计数为 **0**），而 `WmsRepository.offlineQueue` 是 `by lazy`，其 `init` 块承载两件必须发生的事——① `dao.resetStuckSyncing()` 复位进程被杀残留的 syncing 记录；② 注册 `networkMonitor.onlineChanges` 网络恢复监听。首次访问发生在 `ScanViewModel`（扫码页渲染时才创建），**因此：用户断网入库→提交成功暂存→此后再未打开扫码页→网络恢复→队列既不复位也不补传，什么都不会发生**。数据其实在库里，但产品对用户承诺的"联网后自动提交"落空；若恰有 syncing 残留，还会叠加 BUG-2026-09-12-008 的卡死。根因是**初始化时机绑定在页面生命周期上，而职责属于进程级**——队列是全局基础设施，不该由某个页面的打开与否来决定其是否启动 | **已修复（2026-09-12）**：`WmsApplication` 新增进程级 `appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)` 与 `repository: WmsRepository by lazy { WmsRepository(this) }`，`onCreate()` 末尾调用 `warmUpOfflineQueue()` —— 在后台协程里 `runCatching { repository.offlineQueue }` 触发实例化，从而让 `init` 的复位与网络监听与用户操作路径**无关**地生效。要点：①**必须后台执行**，不得阻塞主线程（`onCreate` 是关键路径）；②`SupervisorJob` 隔离失败，预热异常不得影响启动或崩溃；③懒加载 `repository` 避免给启动增加无谓开销，其内部 DB/Retrofit 均为单例，多建实例不产生重复资源；④`getInstance` 的 `synchronized` 双检锁保证幂等，重复调用无副作用。顺带把文件内日志 TAG 由字面量 `"WmsApp"` 收敛为 `private companion object` 常量（原 2 处硬编码）。<br>**验证**：`test_011_application_warms_up_offline_queue`（断言 `onCreate` 确实调用预热、预热体走 `appScope.launch` 不阻塞主线程、引用了 `offlineQueue`）。**生效条件**：Android 改动，需产出新 APK 后重装；无需后端重启 |
| BUG-2026-09-12-006 | [P0·CI 阻断] **AI-MOB-OFFLINE-01 提交后 Android CI 全红（`./gradlew assembleRelease` 编译失败），两处 Kotlin 编译错误**——用户先发现「修不了 BUG 反而增加 BUG」：`Android APK Build` 工作流自 `#424` 起每次都在 `Build Release APK (R8 瘦身)` 步骤失败（`#423` 为最后一个绿版，之间恰为本次 5 个提交）。根因两处，**均非逻辑错误，而是 Kotlin 类型可见性/初始化顺序写错**：<br>①**`DatabaseMigrations.kt` 属性初始化顺序**：`object DatabaseMigrations` 内 `val ALL: Array<Migration> = arrayOf(MIGRATION_1_2)` 写在 `private val MIGRATION_1_2` **之前**。Kotlin `object` 属性初始化严格按源码顺序执行，初始化 `ALL` 时 `MIGRATION_1_2` 尚未赋值，编译器直接报 `variable 'MIGRATION_1_2' must be initialized`（硬编译错误，非警告）。<br>②**companion 嵌套类跨文件引用不可解析**：`OfflineQueueManager.kt` 与 `ScanViewModel.kt` 分别写 `WmsRepository.BusinessException`（2 处）与 `WmsRepository.OfflineQueuedException`（3 处）。这两个类定义在 `WmsRepository` 的 `companion object` 内，**Kotlin 不支持 `Outer.NestedClass` 这种跨文件点号访问 companion 的嵌套类**，必须 `import ...WmsRepository.Companion.X` 后直接用短名。此前基线中 `BusinessException` 只在 `WmsRepository.kt` 同文件内使用（同文件内 `BusinessException` 短名可见），所以从未暴露；`OfflineQueueManager.kt` 是**仓库内首个跨文件引用该嵌套类的文件**，首次触发。R6：同根因在 2 个文件、5 个引用点同时存在，一并修复 | **已修复（2026-09-12）**：①`ALL` 移至 `MIGRATION_1_2` 之后，并补注释说明「新增迁移须追加到 `ALL` 之前、切勿上移该行」；②两文件改为 `import com.factory.wms.data.repository.WmsRepository.Companion.BusinessException` / `...Companion.OfflineQueuedException`，5 处引用改短名（KDoc 里的全限定写法保留，用于指明确切来源）；③顺带修正 `OfflineQueueManager.kt` 的 `ApiEnvelope` import——原写 `data.api.ApiEnvelope`（该包无此类）实为 `data.model.ApiEnvelope`，同样导致 `unresolved reference`。<br>**验证方式（可复现）**：沙箱内自建真实 Kotlin 工具链——kotlinc 1.9.24 + **真实 Android SDK platform-35 `android.jar`**（`dl.google.com` 经 `--resolve 220.181.174.97` 可达）+ Room/Retrofit/OkHttp/Gson/coroutines/DataStore/Security/lifecycle 的**真实 AAR/JAR**。对照编译 `#423`（绿版基线与 HEAD，逐条 diff 错误集合：基线 6303 条、修复后 HEAD 6347 条，**「相比基线多出的错误」已归零**（唯一残留 1 条 `ScanViewModel collect` 经证实为隔离编译缺失 AndroidX 的共模噪声——基线在 `VoiceAssistant.kt`/`NavGraph.kt`/`AuthViewModel.kt` 同类位置已有 3 条同款）。核心文件**零错误产出 182 个 class**；`DatabaseMigrations.kt` 修复前复现 `must be initialized`、修复后消失，形成「改前复现→改后消失」闭环证据。<br>回归：全量 Python **1535 passed、85 skipped、6 failed**（6 项为条码/Excel 打印，`git stash` 比对确认改动前即失败，系沙箱缺条码渲染依赖）；lint 双门禁 **0 违规**。**生效条件**：Android 改动，CI 出包后重装；**无需后端重启**。**教训（写入规则）**：Android/Kotlin 改动**不能只靠「语法检查」或「单文件编译」判定通过**——本次两处均为语法合法、单文件看不出、仅全项目编译才暴露的错误。后续 Kotlin 改动须以 CI `assembleRelease` 结果为唯一验收依据，未确认 CI 转绿不得声称完成 |
| BUG-2026-09-12-003 | [P1] 手机端查库存列表模式看不到库位、品牌（BUG-2026-09-10-003 的遗留未覆盖面，专家走查+实测坐实）：`/api/mobile/stock/query` 响应字典只下发 id/code/name/spec/unit/category/supplier/stock/price/min_stock/reorder_point，**漏下发 `brand` 与 `locations`**；而扫码路径（`mobile_material_payload`）两者均下发。根因是时间线错位——列表模式 `AI-MOB-STOCK-F01` 于 **2026-08-09** 引入，而补 `locations` 的 `BUG-2026-09-10-003` 于 **2026-09-10** 才修，**当时只覆盖了扫码路径**（其测试甚至明确断言"所有消费点都带 locations"），列表接口被漏掉。后果：同一物料、同一仓库、库位数据真实存在时，**扫码能看到「货在货架A-03 50 件」，列表里看不到**——作业员必须逐个点进去扫才能知道货在哪，而"查库存看到总量却不知道在哪、还得挨个扫"正是列表模式本该解决的问题；`brand` 则是 `Material` 表真实存在的列、`StockListRow` 已渲染但数据永远为空 | **已修复（2026-09-12，commit 见下）**：①`mobile_api_stock_query` 响应补齐 `brand`（`m.brand or ''`）与 `locations`；②**复用** `build_material_locations_map`（BUG-2026-09-10-004 为消除 N+1 引入的批量预取函数）而非逐条查询，实测 50 条物料逐条查 = **50 条 SQL**、批量 IN = **1 条**（快 5.8x），并继承其与 `/api/material/search`、`/api/material/all` 完全一致的口径（非零、数量降序、库位升序、IN 分批 500），避免同根因在多消费点分叉（R6）；③为该函数新增可选参数 `legacy_location_names`——传入时额外纳入 `warehouse_id IS NULL` 且 `location` 等于本仓名/编码的历史行，**不传则保持原精确匹配行为**（search/all 两处调用点零改动）。做此扩展的原因经实测：不兼容历史行会出现「`get_warehouse_stock_quantities` 汇总 70 但库位明细只列 50」的不一致，违反 **R2 第 3 条（汇总=明细）**。回归：`tests/test_bug_2026_09_12_003_android_stock_query_locations.py` 8/8（brand+locations 下发 / 零库存库位不列 / **R2-1 多仓隔离 A 仓不串 B 仓** / **R2-2 历史 NULL warehouse_id 兼容** / 关库位管理为空 / **防 N+1 退化**（本页 20 条物料 location_inventory SQL 为常量级）/ 第 2 页同样带字段 / **R2-3 汇总=明细** + 共用函数向后兼容）；既有 `test_bug_2026_09_10_004_material_search_n_plus_one.py` 6/6 与 `09_10_002`/`09_10_003`/`08_16_007` 共 14 项零回归；全量 **1530 passed、85 skipped**（另 6 项条码/Excel 打印失败经 `git stash` 比对确认**改动前即失败**，系沙箱缺条码渲染依赖，与本次无关）；lint 双门禁 0 违规。**生效条件**：纯后端改动，拉取后**重启 WMS 服务生效**（R3）；Android 侧 `MaterialDto` 早有 `brand`/`locations` 字段与渲染逻辑，**无需改代码、无需重装 APK 即可显示库位分布** |
| BUG-2026-09-10-010 | [P1] 手机首页概览只统计系统默认仓（与 009 日报同根因，用户走查发现）：`/api/mobile/dashboard` 不带仓库参数、服务端一律回退 `get_default_warehouse()`，首页四张卡（今日入库量/出库量/待处理/库存告警）**只反映默认仓**；4 仓以上用户在非默认仓作业时首页数字明显偏小甚至为 0，与日报跨仓盲区并存 | **已修复（2026-09-10）**：①后端支持 `warehouse_id / warehouse_code / warehouse` 指定仓库，显式 `all` = 全部仓库汇总（口径与 009 日报严格一致，缺省仍回退默认仓、非法仓仍 400）；告警在 all 模式下**按物料去重**（任一仓低于最低库存计一次，不被仓库数放大）；响应新增 `warehouse` / `warehouse_id` / `all_warehouses`；②Android `getDashboard(warehouseId)` + `HomeViewModel`（warehouses / selectedWarehouseId / loadWarehouses / selectWarehouse）+ 首页概览条标题行加仓库切换；③R6 同类收敛：把日报页的 `WarehouseSelector` **提取为共享组件** `ui/components/WarehouseSelector.kt`，报表页改用共享组件，消除两份实现漂移风险。回归：`tests/test_bug_2026_09_10_010_dashboard_warehouse_scope.py` 9/9（指定仓隔离 / **全部合计 = 各仓之和 R2** / 跨仓待处理累加 / 缺省回退默认仓 / 响应标记 / 非法仓仍 400 / **告警去重** / 数量合计 / 昨日不串今日） + `tests/verify_bug_2026_09_10_010_home_warehouse_selector.py` 7/7（API 参数 / Repository 透传 / ViewModel 状态 / 页面接入 / 共享组件与报表页复用 / DTO 字段 / 进入即加载仓库）。**生效条件**：后端改动拉取后**重启 WMS 服务生效**（R3）；App 下拉需产出新 APK 后重装 |
| BUG-2026-09-10-009 | [P1] 手机每日报表固定只查系统默认仓，多仓用户「查不到今天的记录」：手机报表页请求 `/api/mobile/report/daily_detail` 不带任何仓库参数，服务端 `resolve_request_warehouse` 一律回退 `get_default_warehouse()`，录在其他仓的单据**一条都进不了日报**（首页今日入库/出库同源同口径，同样只算默认仓）。用户在用仓库 4 个以上，当天单据录在非默认仓即表现为「今天查不到」 | **已修复（2026-09-10，commit 本次提交）**：①后端支持 `warehouse_id / warehouse_code / warehouse` 指定仓库；显式传 `all` = 全部仓库汇总（用户主动跨仓，不是「未指定仓库」，不违反 AGENTS.md 仓库必填；缺省仍回退默认仓、非法仓仍 400）；明细行新增 `warehouse` 字段，响应新增 `warehouse_id` / `all_warehouses`，诊断统计（pending_orders / other_type_orders）同步跨仓；②Android 顶部新增 `WarehouseSelector`（默认仓库 / 各仓 / 全部仓库汇总），进入页面先拉仓库列表再查报表，`dailyReportDetail` 与逐页翻页均携带 warehouse_id（R1），全部仓库模式明细行显示来源仓，`DailyReportItem.warehouse` 可空兼容旧版后端。回归：`tests/test_bug_2026_09_10_009_daily_report_warehouse_scope.py` 7/7（指定仓隔离 / **全部合计 = 各仓之和 R2** / all 模式明细带仓名 / 缺省仍回退默认仓 / 响应标记 / 非法仓仍 400 / 跨仓 pending 累加） + `tests/verify_bug_2026_09_10_009_report_warehouse_selector.py` 6/6（API 参数 / Repository 逐页透传 / ViewModel 状态 / 选择器含全部仓与默认仓 / 字段可空 / 加载顺序）。**生效条件**：后端拉取后**重启 WMS 服务生效**（R3），接口侧可先手工用 `&warehouse_id=N` 自查；App 下拉需 GitHub Actions 产出新 APK 后重装 |
| BUG-2026-09-10-008 | [P2] 手机每日报表空态不说明「为什么查不到」：报表只统计「已完成」单据，而 PC 端入库/出库保存后默认 `pending`（需人工点完成），现场只能看到一句「当日暂无领料单明细」，无法区分「没单 / 单没完成 / 业务类型不对 / 查错仓库」，只能反复反馈「今天的记录查不到」 | **已修复（2026-09-10，commit 本次提交）**：`ReportModels.DailyReportData` 新增可空 `warehouse / serverToday / diagnostics`（`DailyReportDiagnostics`：business_types / pending_orders / other_type_orders，全部可空——旧版后端无该节点时 Gson 置 null），`ReportScreens` 空态文案由固定句改为 `emptyStateHint()`：①待完成单据数>0 → 提示「今日该仓还有 N 张单据未完成（电脑端录入后需点『完成』才会计入报表）」；②否则有其他类型已完成单 → 列出「产品入库 3 单」等；③否则回退基础文案；日期条在日期下方显示实际查询的仓库。回归：`tests/verify_bug_2026_09_10_008_report_empty_hint.py` 6/6 PASSED（模型字段齐全且可空 / diagnostics 模型存在 / 空态走动态函数 / **hint 对 diagnostics 与 pendingOrders 判空**（BUG-2026-08-24-007 同模式：Gson 绕过构造器默认值）/ 日期条显示仓库 / 两类原因均覆盖）。**生效条件**：Android 改动，需 GitHub Actions 产出新 APK 后重装；不重装时旧版 App 只是拿不到诊断字段，空态仍显示原文案（后端已兼容） |
| BUG-2026-09-12-005 | [P1] PC/移动端物料搜索带仓库时「库存总数」与「库位分布」口径分裂（BUG-2026-09-12-003 修复过程中同根因排查发现，实测坐实）：`/api/material/search?warehouse=X` 的响应里，`stock` 走 `get_warehouse_stock_quantities`（**含**历史 NULL warehouse_id 兼容），而 `locations` 走 `build_material_locations_map`（默认**仅** `warehouse_id` 精确匹配）——同一响应出现 **`stock=70` 但库位明细只列 `50`**（实测复现）。后果：作业员看到库存 70 件、按库位分布去货架找货，**有 20 件永远找不到**（货在历史行上）。R6：与 BUG-2026-09-12-003 同根因（口径在多个消费点分叉），属该函数被复用时未同步兼容逻辑所致 | **已修复（2026-09-12，commit 见下）**：`material_search_api` 在带仓库上下文时构造 `legacy_location_names = [wh.name] + [wh.code]`（名称与编码，去重）传入 `build_material_locations_map`，使其与 `get_warehouse_stock_quantities` 严格同口径；无仓上下文时保持 `None`（全局视图不按仓过滤，行为不变）。**同时核对 `/api/material/all`：该接口 `wh_obj=None`、本就是全局口径（stock 走 `Material.stock`、locations 不过滤），不存在分叉，无需改动**——避免了盲目套用修复。回归：`tests/test_bug_2026_09_12_005_material_search_location_consistency.py` 5/5（**带仓搜索 stock == locations 明细之和 R2-3** / 历史行按仓库**编码**写入时同样纳入 / **R2-1 B 仓历史行不串入 A 仓** / 无仓上下文行为不变 / 防 N+1 退化）；既有 `09-10-004`/`09-12-003`/`09-10-003`/`09-10-002` 共 23 项零回归；lint 双门禁 0 违规。**生效条件**：纯后端改动，拉取后**重启 WMS 服务生效**（R3）；无数据库迁移 |
| BUG-2026-09-10-007 | [P2] 手机每日报表日期跨天不刷新：`ReportViewModel` 在 App 启动（AppNavGraph 组合）时创建，`date` 只在 `init` 取一次 `Date()`；Android 进程常在后台存活数日，用户隔天打开报表页仍按启动日查询，顶部日期显示的也是旧日期——表现为「今天的记录查不到」（点「回到今天」可临时绕过） | **已修复（2026-09-10，commit 本次提交）**：`ReportUiState` 新增 `dateIsToday`（默认 true）；`load()` 在今天模式下先把 `date` 校正为系统当天再查询（进入报表页时触发，ViewModel 复用也不过期）；`shiftDay()` 手动翻天置 `dateIsToday=false`（避免用户翻到的日期被自动校正覆盖），`resetToday()` 恢复 true。回归：`tests/verify_bug_2026_09_10_007_report_date_refresh.py` 4/4 PASSED（UiState 有标记 / load 校正 / 翻天脱离 / 回到今天恢复）。**生效条件**：Android 改动，需产出新 APK 后重装 |
| BUG-2026-09-10-006 | [P1] 手机原生端出库业务类型与 PC 领料单不是同一个：`POST /api/outbound` 固定写 `business_type='Android扫码出库'`，而 PC 领料单是 `'领料单'`——后果①每日报表 requisition 严格等值 `'领料单'`，**手机扫的库在日报里一条都不出现**（首页「今日出库」却显示有数，因为 dashboard 不区分业务类型）；②PC 领料单列表默认口径 `business_type == '领料单' or is None`，**手机出的库在 PC 上也看不到**。R6：与 09-10-005 同根因（业务类型口径分裂），两处一并修 | **已修复（2026-09-10，commit 本次提交）**：`/api/outbound` 出库统一写 `business_type='领料单'`（手机端出库即仓库领料），来源仍由 `purpose`（领用部门/「Android原生端提交」）与 `remark` 区分；`ScanRequests.OutboundRequest` 默认 `business_type` 同步为「领料单」（契约一致）。R6 同类点排查：全仓 `grep 'Android扫码出库'` 仅此两处生产点，历史单据由 09-10-005 的报表口径兼容命中，无需数据迁移。回归：`tests/test_bug_2026_09_10_006_outbound_business_type.py` 4/4 PASSED（出库写领料单 / **当日即出现在日报** / 出现在 PC 领料列表口径 / Android 契约一致）；既有 `test_mobile_outbound_contract.py`、`test_print_auto_after_scan.py` 零回归。**生效条件**：后端改动，拉取后**重启 WMS 服务生效**（R3） |
| BUG-2026-09-10-005 | [P1] 手机每日报表「查不到今天的记录」，且无任何可诊断线索：`/api/mobile/report/daily_detail` 的 requisition 严格等值 `business_type='领料单'`，而手机原生端出库写的是 `'Android扫码出库'` → 手机出的库**永远进不了日报**；同时报表只统计 `status='completed'`，PC 端入库/出库保存后默认 `pending`（需人工点完成）→ 当天录的单查不到；响应里既没有仓库名也没有待完成数，空结果无法区分原因。用户实测反馈「手机 app 每日报表查不到今天的记录」（09-10） | **已修复（2026-09-10，commit 本次提交）**：①requisition 口径改为业务类型集合 `('领料单', 'Android扫码出库')` + 空类型兜底（`business_type IS NULL` 按领料计，与 PC 领料单列表 `out_order_list` 口径一致），销售出库/其他出库仍排除（口径不扩大）；②响应新增 `warehouse`（实际查询仓库）、`server_today`、`diagnostics{business_types, pending_orders, other_type_orders}`——待完成单据数与「当天该仓已完成但类型不在本口径内」的分布，供手机端空态给出明确原因。回归：`tests/test_bug_2026_09_10_005_daily_report_scope.py` 8/8 PASSED（手机扫码出库进日报 / 空类型按领料 / 销售·其他出库排除 / diagnostics 字段 / pending 只报不进明细 / 其他类型计数 / **R2 多仓隔离**含显式 warehouse_id 切仓 / 昨日不串今日）；既有 `test_mobile_report_daily_detail.py` 12/12 零回归。**生效条件**：后端改动，拉取后**重启 WMS 服务生效**（R3）；无数据库迁移 |
| BUG-2026-09-10-004 | [P2] 手机端查库存带仓库搜索 N+1 性能缺陷（09-10-002 遗留、专家走查确认）：`/api/material/search` 带 warehouse 时 `api_material_payload` **逐物料**调 `get_warehouse_stock_quantities`（每次都是全仓聚合查询）+ 逐物料查 `LocationInventory` 库位分布，命中上限 100 条时高达 200+ 次查询，手机端搜索明显卡顿；`/api/material/all` 库位分布同样逐物料查询（1000 条上限即 1000 次） | **已修复（2026-09-10）**：`api_material_payload` 签名扩展 `warehouse_stock_map`/`locations_map` 预取参数（不传保持原逐物料行为，单物料 `/api/material/info` 不变）；新增 `build_material_locations_map`（一次 IN 分组查询替代 N 次单查，IN 分批 500 兼容变量受限数据库，过滤/排序口径与逐物料路径严格一致——非零、数量降序、库位升序、带仓按 warehouse_id 过滤 R2）；search 接口固定为 1 次全仓聚合 + 1 次库位批量查询（与命中数无关），all 接口库位分布同步批量化。回归：`tests/test_bug_2026_09_10_004_material_search_n_plus_one.py` 6/6（带仓搜索聚合固定 1 次/库位查询固定 2 次且命中数变化不变/all 接口库位批量化/批量路径与单物料 info 路径 stock+locations+min_stock 等字段严格一致/无仓上下文 0 次聚合+全局口径不变/预取函数空入参与分批边界）；存量 09-10-002/003 物料 API 15 项全过；全量 **1436 passed、84 skipped、0 failed**；lint 双门禁 0 违规。**生效条件**：纯后端改动，拉取后**重启 WMS 服务生效**（Android 无需改代码、无需重装 APK）。**遗留说明**：手机端查库存离线容忍（Room 缓存陈旧度标注）属架构级特性另行任务评估 |
| BUG-2026-09-10-003 | [P1] 手机端查库存两个误导性缺陷（专家走查实测）：①结果卡「库存充足/不足」徽标按 `stock > minStock` 判断，但 `api_material_payload` **不下发 min_stock**——DTO 字段恒 null→0，退化为"大于 0 即充足"，现场按徽标拣货会误判（结果卡"最低库存/再订货点"两个 InfoChip 同理恒显 0）；②现场找货第二高频问题「货在哪个库位」无答案——payload 仅在开启库位管理时返回数量最多的单个 location_code，无各库位数量分布 | **已修复（2026-09-10）**：①`api_material_payload` 新增 `min_stock`/`reorder_point` 真实下发（Material 模型早有字段，纯新增向后兼容，Android 徽标与 InfoChip 无需改代码即变真值）；②payload 新增 `locations` 数组——开启库位管理时返回该物料全部非零库位及数量（按数量降序、有仓库上下文按 warehouse_id 过滤与该仓账面口径一致 R2、未开启为空列表），`location_code` 保持"数量最多库位"原语义不变；Android `MaterialDto` 增加 `locations`/`MaterialLocationDto`（默认 null 保持 Entity 映射构造兼容），查库存结果卡新增「库位分布」区块逐行展示库位+数量。回归：`tests/test_bug_2026_09_10_003_material_payload_min_stock_locations.py` 5/5（min_stock/reorder_point 真值下发/库位分布非零+降序+location_code 原语义/带仓上下文 B 仓 999 不串入 R2/关库位管理为空/search 同步携带）+ `tests/test_bug_2026_09_10_003_android_stock_locations_display.py` 3/3（DTO 字段与默认兼容/徽标按 minStock 比较+InfoChip 锚点/库位分布区块锚点）；存量物料 API/位置相关 161 项零回归；Kotlin 括号平衡校验通过；lint 双门禁 0 违规。**生效条件**：后端改动拉取后**重启 WMS 服务生效**（徽标与 InfoChip 立即变真值）；「库位分布」展示需 GitHub Actions 产出新 APK 后用户重装。**说明**：price 字段是否随手机端下发按角色裁剪（专家走查 P3 项）与带仓搜索 N+1 性能（09-10-002 遗留）均另行任务 |
| BUG-2026-09-10-002 | [P1] Android 查库存输「电线」点查询只弹「物料不存在」，且模糊候选只显示前 8 条、名称/规格/品牌挤一行省略号截断（用户实测要求：候选列出包含关键词的所有物料、名称规格品牌显示齐全）。三层原因：①查询按钮/键盘搜索键走 `/api/material/info` 精确编码查询，非编码关键词必报「物料不存在」（后端 `/api/material/search` 早已支持模糊，按钮路径没接上）；②`ScanScreens.kt` 候选 `take(8)` 截断；③候选项 subtitle 单行 `maxLines=1 + Ellipsis`，长名称/规格/品牌被截去 | **已修复（2026-09-10）**：①`ScanViewModel.kt` 新增 `queryMaterialByKeyword`——先 `getMaterialInfo` 精确查编码，未命中回退 `searchMaterial` 模糊列表（全部命中写入 materialSuggestions 交页面展示；模糊也无命中不写 error，页面空态提示「未找到包含「kw」的物料」，避免 toast+空态双提示；不触碰 scannedCode 防 LaunchedEffect 重复查询），放大镜按钮与新增键盘 IME Search 键统一走该入口；②`ScanScreens.kt` 候选去掉 `take(8)`，列出全部命中（`heightIn(max=360.dp)` + `verticalScroll` 内部滚动）；③候选项改三行完整展示（编码加粗 / 名称整行 / 「规格: x 品牌: y」行），候选区块内无 `maxLines=1`/Ellipsis 截断；④后端 `/api/material/search` 配套 R1 显式化——上限魔法数 100 提为常量 `MATERIAL_SEARCH_API_LIMIT`，响应新增 `total`/`truncated`（命中超上限时调用方可知"全量 N 条、本次前 100 条"，字段新增向后兼容，Android 仅读 data 不受影响）。回归：`tests/test_bug_2026_09_10_002_material_search_total.py` 4/4（名称/规格/品牌三处模糊命中全返回且字段齐全/超上限 total=真实全量+truncated=True/无关键词 total 正确/info 精确未命中契约不变）+ `tests/test_bug_2026_09_10_002_android_stock_query_display.py` 4/4（按钮与 IME 走回退入口/无 take(N) 截断+可滚动/候选项名称规格品牌齐全无省略号/空态提示锚点）；存量 09-03-004 物料 API 21 项、search 相关 36 项全过；Kotlin 编辑区括号平衡校验通过；`scripts/lint_wms_rules.py --staged` 与 `lint_no_raw_post_fetch.py` 均 0 违规。**生效条件**：后端改动拉取后**重启 WMS 服务生效**；Android 侧 GitHub Actions（android-build.yml）产出新 APK 后用户手机重新下载安装生效。**遗留说明**：带 warehouse 搜索时 `api_material_payload` 逐物料调 `get_warehouse_stock_quantities`（N+1 聚合，100 条≈100 次仓库级汇总查询），属性能项非本次显示缺陷根因，另行任务优化 |
| BUG-2026-09-10-001 | [P1] 反提交+删除草稿后库存台账仍显示已删除单据（用户实测领料单 out_order-111/out_order-169 残留）：BUG-2026-08-17-006 只修了采购入库单删除清流水，**R6 同类消费点排查不全复发**——领料单/工单领料单/调拨单/库存调整单/售后出库单/委外发料单/委外收货单 7 类单据的删除与批量删除路由均不写 `StockTransaction` 清理，反提交产生的反向流水（revert_out/revert_requisition/transfer 反向/revert_adjustment/revert_after_sale_out/revert_issue/revert_receive）与完成流水一起成为指向已删除单据的悬挂引用，台账 `_collect_ledger_rows` 全量直读流水故照常显示 | **已修复（2026-09-10，R6 全消费点一次补齐）**：6 个路由文件 12 处删除端点（`out_order.py`/`requisition.py`/`transfer.py`/`adjustment.py`/`after_sale_out.py`/`subcontract.py` 各自的单删+批删）在 `_acquire_order_write_lock` 写锁内同步清理 `reference_type`+`reference_id` 匹配的 StockTransaction，与 `delete_in_order` 对齐；历史悬挂流水用 `scripts/cleanup_orphan_document_transactions.py`（默认预演、`--confirm-delete` 执行、删除时按类型回连主表二次确认防误删重建单据，含历史 `reference_type='check'` 兜底）。**R6 同类点全量排查结论**：`in_order` 已由 17-006 覆盖；`opening_stock` 流水由 delete_material 引用完整性守卫拦截（有流水物料禁删）；现版本盘点经调整单写流水（随 adjustment 覆盖），历史 'check' 流水由清理脚本兜底；台账查询层不加读时过滤（8 张单据表存在性回连代价高，删除点清理+脚本与 17-006 先例一致）。回归：`tests/test_bug_2026_09_10_001_delete_document_ledger_cleanup.py` 16/16（7 类单据单删+批删清流水/反提交→删除全流程/不误删他单流水/无流水草稿空操作）+ `tests/test_cleanup_orphan_document_transactions.py` 3/3（预演不写库/确认删除/重建单据不误删）；存量 17-006 回归 3/3、删除/反提交相关 89 项全过；全量 **1411 passed、84 skipped、0 failed**；`scripts/lint_wms_rules.py --staged` 与 `lint_no_raw_post_fetch.py` 均 0 违规。**生效条件**：纯后端改动，拉取后**重启 WMS 服务生效**；存量台账中的历史悬挂流水需手工执行清理脚本（先预演确认，再 `--confirm-delete`） |
| BUG-2026-09-06-005 | [P1] 启用库位管理时盘点差异调整明细缺少库位，且同物料跨多个区域合并时无法可靠归属 | **已修复（2026-09-06）**：差异调整写入盘点区域作为库位；缺失区域或多区域合并时阻止生成草稿，避免错误记账。回归：`tests/test_bug_2026_09_06_004_check_copy_and_location.py`。**生效条件**：后端改动，拉取后重启 WMS |
| BUG-2026-09-06-006 | [P1] Android 盘点提交未携带库位/区域，启用库位管理且有差异时无法生成可过账调整单 | **已修复（2026-09-06）**：Android 盘点页增加盘点库位/区域输入，按行提交 area；后端兼容 location/location_code，并在库位管理开启且产生差异时强制校验。相同物料可按不同库位分别记录。回归：`tests/test_bug_2026_09_06_006_android_stocktake_location.py`。**生效条件**：后端重启并重新构建发布 Android APK |
| BUG-2026-09-06-004 | [P1] 复制盘点单丢失仓库和区域语义，并复制旧实盘/差异结果，形成假已盘数据 | **已修复（2026-09-06）**：复制时保留并校验仓库，按当前仓库账面重新冻结；实际库存重置为账面、差异清零、盘点归属不复制，保留区域。回归：`tests/test_bug_2026_09_06_004_check_copy_and_location.py`。**生效条件**：后端改动，拉取后重启 WMS |

| BUG-2026-09-15-007 | [P1] 期初库存无法分单、导入单据不能改日期、首/上/下/末 功能缺失（用户原话：「期初库存单据，我要做几张怎么新增，因为有很多仓库很多物料很多仓管人员，导入的期初库存单据怎么修改日期，首 上下末功能要有」）。根因是数据模型不支持：`opening_stock` 是一张平铺台账，唯一约束 `uix_opening_stock_material_warehouse` 钉死在 `(material_id, warehouse_id)` 上，同物料同仓只能存在一行，"按仓库/物料/建账人分几张单"在模型层就做不到；没有单据头、没有单号，所以既无法定位"某一张单"来改日期，`DOCUMENT_NAVIGATION_MODULES` 里也无从注册导航。Excel 导入把每行直接 upsert 进台账，用户导入完看不到"这是哪一批"，更无从改日期。改造前 4 个导航键是硬编码 disabled 的死按钮（BUG-2026-09-15-005 曾因"无可导航单据"把它们删除） | **已修复（2026-09-15，ARCH-OS-DOC-01）**：引入单据头 `opening_stock_doc`（`doc_no` QS+YYMM+4位、`date` 建账日期、`warehouse_id` 可空、`status`、`remark`、`operator_id`），`opening_stock` 加 `doc_id` 外键，唯一键收窄为 `(material_id, warehouse_id, doc_id)`——**单内不重复、跨单据可重复**，同物料同仓多张单成为合法状态。期初库存口径随之定义为「某 (物料,仓库) 在所有单据中明细行数量之和」（见 `INVENTORY_TRUTH.md` §2.1.2）。新增单据级 CRUD：`POST /opening_stock/save`（无 doc_id 取号建单；有则改单头+逐行 upsert+差集删行并回冲）、`GET /opening_stock/add`、`GET /opening_stock/<id>`（单据详情页）、`POST /opening_stock/<id>/delete`（物理删除+全额回冲）、`POST /opening_stock/<id>/date`（改期同步该单全部明细行、不动账）、`POST /opening_stock/<id>/line/<line_id>/delete`；原 JSON 明细接口迁至 `/opening_stock/line/<id>`（endpoint 名不变）。Excel 导入整批归入一张新单据并回传 `doc_id`/`doc_no`/`detail_url`（行匹配加 `doc_id` 过滤，防跨单误改；全错行不留空单）；二次导入生成新单而非覆盖。前端注册 `opening_stock` 进 `WMS_ACTION_MODULES`（`navigator: true`），工具栏 4 个"首/上/下/末张"由死按钮改为真实跳转（`/api/document_navigation/opening_stock`），详情页注入 `window.__OPENING_DOC__` 回填明细，保存/粘贴导入统一走 `/opening_stock/save` 并带 `doc_id`（原先打 batch_save 会永远新建兼容单，编辑已有单据完全失效）。**开发中修复的两个真实缺陷**：①`_apply_opening_stock_balance` 的 `doc_id` 曾由调用方对返回值赋值，而新建明细行时函数内部创建对象、调用方变量仍为 None，赋值静默丢失 → 明细行不归属任何单据、导航永远找不到它（表面"保存成功"数据是错的），改为 `doc_id` 参数传入；②`/opening_stock/<id>/date` 500（`name 'datetime' is not defined`，延迟导入漏项）。**R6 兜底**：`doc_id` 起初只写在 `auto_migrate_database()`，生产批处理默认 `WMS_NO_DB_TOUCH=1` 会整体跳过迁移，存量库重启后一查即 500（`no such column: opening_stock.doc_id`）——新增 `ensure_opening_stock_doc_columns()` 无条件幂等补列并在启动期注册，使 `test_r6_startup_migration_column_guard` 保持 0 缺口（补兜底而非登记欠账）。迁移在 `auto_migrate_database()` 内幂等执行：建单据头表 + `ALTER TABLE opening_stock ADD COLUMN doc_id` + 检测到遗留 `UNIQUE(material_id, warehouse_id)` 时 12 步重建表（备份 `opening_stock_backup_mw001` + 行数一致性校验）+ 按 `(date, warehouse_id)` 回填历史单据。**回归**：新增 `tests/test_opening_stock_multi_doc.py` 33 项（同物料同仓多单据/单内去重/明细行必带 doc_id/差额入账不重复累加/单头日期覆盖明细/删行回冲/删单物理删除+全额回冲/改日期同步不动账/404/R6 校验不放松含 pydantic 中文提示/单号格式/兼容路径/Excel 整批归单/前端接线/ensure 兜底）、`tests/test_opening_stock_migration.py` 11 项、`tests/test_opening_stock_doc_no.py` 6 项、`tests/test_opening_stock_doc_navigation.py` 9 项；`tests/test_bug_2026_09_15_005` T1/T5 按新契约收窄（导航键由"必须不存在"反转为"必须存在且接通"）；`tests/verify_app_py_split_opening_stock.py` 两处断言随 JSON 明细接口路径更新。相关全量 **191 passed、6 skipped、0 failed**；`scripts/lint_wms_rules.py` 0 违规。**生效条件**：后端+模板+JS 改动，拉取后**重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存。**注意**：写路由按 A8 补 pydantic 输入模型（`OpeningStockDocRequest`/`OpeningStockDateRequest`），pydantic 英文校验错误已本地化为中文（"第 1 行仓库为必填项"） |

| BUG-2026-09-15-008 | [P1] 期初库存"删除不了"已建账/已导入记录（用户原话：「我要删除已导入的全部期初但删除不了」）。根因：台账页没有任何删除"已建账"记录的入口——工具栏「删除」经 BUG-2026-09-15-005 重定义为 `clearEntryRows()`，只清空**未保存**的录入行，对已入账记录完全无效；已建账/已导入数据只能钻进对应单据页逐张点"删除本单"，批量导入的一批想清空重来无从下手；台账面板也无逐行删/删全部 | **已修复（2026-09-15）**：新增 `POST /opening_stock/delete_all`——物理删除全部 `OpeningStock` 明细行 + 全部 `OpeningStockDoc` 单据头，逐行 `_reverse_opening_stock_line` 回冲库存（含 `doc_id` 为 NULL 的历史直连台账行），与"删除本单"同规则（回冲后库存变负照常删除、仅中文提示不阻断）；按 A8 用 pydantic `confirm: bool` 做服务端二次确认，缺/非 true 返回 400 数据不动。前端工具栏新增「删除全部」危险按钮（双确认 + `WMS.api`，禁原生 fetch），并把易混淆的「删除」改名「清空录入」以区分"清未保存"与"删已建账"。**注意**：测试夹具手动 push 常驻 app_context 会把登录态泄漏给后续 test_client（生产真实 HTTP 无此问题，干净上下文实测匿名 302 拦截），匿名用例需先显式 logout 再断言。回归 `tests/test_opening_stock_delete_all.py` 7/7（全删回冲归零/confirm 必填/空记录幂等/孤儿行回冲/未登录拦截/负向流水/前端按钮静态断言），期初库存全量 103 passed，`lint_wms_rules.py` 0 违规。后端+模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |

| BUG-2026-09-15-009 | [P1] 期初库存页把"台账查询 + 录入网格"堆在同一页，"单据"概念被淹没（用户原话：「重新写期初库存模块，我要的是一个单据而不是什乱七八糟的东西」，并选定形态「单据列表+单据编辑分离」）。根因：`/opening_stock` 列表页既是只读物料级台账、又内嵌可编辑录入网格并预填全部记录；新建页 `/add` 也把台账全部记录预填进网格——一页三合一，用户找不到"一张单据"在哪 | **已修复（2026-09-15）**：拆分为单据列表 + 单据编辑两页。`/opening_stock` 改渲染新模板 `opening_stock_list.html`——只列**单据**（单据号/日期/仓库/明细行数/合计金额/备注，操作列：打开进 `/opening_stock/<id>`、删除），含「新增单据」「批量导入」「删除全部」（BUG-2026-09-15-008 入口随迁）按钮，查询按单据号/备注/仓库（`warehouse.has`）、仓库筛选（表头或任一明细行 `lines.any`）、分页；路由 `opening_stock_list` 由查明细行 `OpeningStock` 改为查单据头 `OpeningStockDoc` 并按单聚合行数/金额/仓库展示（多仓标"多仓库"）。编辑器 `opening_stock.html`（`/<id>` 与 `/add`）移除台账查询面板成为纯单据编辑页，新建页不再预填全部记录（`existingRows` 非编辑分支置空，从空白单据开始），工具栏加「返回列表」，「删除全部」入口移到列表页；保留旧锚点 `#opening-query-panel`（随面板迁到列表页查询卡片，供深链兼容）。物料级期初余额汇总仍可在单据编辑页"汇总"页签或库存报表查看。回归：新增 `tests/test_opening_stock_doc_list.py` 9 项（列表只列单据/编辑与新建页无台账面板/仓库筛选/按号搜索/行数金额/前后端静态断言）；`test_bug_2026_09_15_005` T8 按新契约收窄（锚点迁列表页）；`test_opening_stock_delete_all` T7 改指列表模板；期初库存全量 **111 passed、0 failed**，`lint_wms_rules.py` 0 违规。后端+模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |
| BUG-2026-09-16-001 | [P2] 期初库存明细行没有「勾选批量删除」——只能逐行点删除图标，几十行的导入单要按几十次（用户原话：「期初库存有无删除整张单据功能？有无选择行删除功能？」→ 确认后指示：「把批量删行做出来」）。根因：两条既有删行路径都不满足批量诉求——①每行右侧删除图标 `deleteRow(index)` 只做 `rows.splice()`，删的是**前端数组**，必须再点「保存」才由后端差集回冲落库（用户删完直接离开页面则行不消失，且界面无任何提示）；②后端 `POST /opening_stock/<id>/line/<line_id>/delete` 单行接口自 ARCH-OS-DOC-01 起就**从未被前端接线**（死接口，A9 无覆盖），且一次仅删一行。整表亦无 `checkbox`/全选，全仓库 grep 零命中 | **已修复（2026-09-16）**：新增 `POST /opening_stock/<id>/lines/delete`（`batch_delete_opening_stock_lines`）——一次删多行、逐行 `_reverse_opening_stock_line` 回冲库存后 `db.session.delete`，回冲后库存为负照常删除、仅返回中文提示不阻断（与 `delete_opening_stock_doc` 同规则，避免同类点规则漂移）。**入参**按 A8 走 pydantic `OpeningStockLineIdsRequest(line_ids: list[int], min_length=1)`，缺失/空列表/非整数/非正数一律 400 且数据不动；`line_ids` 去重保序，同一 id 传多次只删一次、只回冲一次（防库存被重复扣减，T7 覆盖）。**越权防护**：`OpeningStock.id.in_(line_ids) AND doc_id == id` 查回后必须 `len(lines) == len(line_ids)`，混入他单的 line_id 即整批 400、一行不删、库存不动（不能只校验第一条就放行）。**原子性**：任一行回冲失败整体 `rollback`，保证「要么全删全回冲，要么原样保留」，不留半残状态。前端 `opening_stock.html` 明细表加勾选列（表头全选 `#openingCheckAll` + 每行 `.opening-row-check`），实现 `batchDeleteSelectedRows()`：**已保存行**（有 `line_id`）走新批量接口立即落库+回冲，**未保存行**仅从录入网格移除，混选时确认框分别报出两类数量，并新增「删除选中行」按钮与「已勾选 N 行」计数提示。**关键实现点**：勾选态用与 `rows` 同下标的 `selectedFlags` 数组存在**数据层**而非读 DOM——`renderRows()` 会整体重建 tbody，DOM 勾选态随之下线，改数量/加行/插入行后必然丢失；`insertRowAfter` 同步 `splice` 勾选位避免勾到相邻行，`DOMContentLoaded` 先 `syncSelectedFlags` 再首次渲染。全选框含 `indeterminate` 半选态。**回归**：新增 `tests/test_opening_stock_batch_delete_lines.py` 8 项（批删按行回冲且未选行不串账/越权整批拒绝/入参缺失空表非正数拒绝/单据不存在 404/未登录拦截/负向流水/重复 id 幂等/前端勾选列与端点静态断言）；**变异测试验证 T2 有效性**（临时关闭越权校验后 T2 如期 FAIL，确认测试非空跑）；期初库存全量 **123 passed、1 skipped、0 failed**（原 111 + 新增 8），`scripts/lint_wms_rules.py` 0 违规、`lint_no_raw_post_fetch.py` 通过；`scripts/verify_wms_bugs.py` 无新增 FAIL（4 个 AI 模块 FAIL 为改动前既有基线，已 stash 对比确认）。**真实浏览器 E2E 已实测通过**：Chromium 直连 `?embedded=1` 内容页，19/19 断言全过、零 `pageerror`——勾选 2 行→提示「已勾选 2 行」→全选/取消→未勾选时点删除被拦截→批量删除后剩 M003 一行→库存 M001 90→80、M002 140→120 按各自数量精确回冲、未删的 M003 200→200 不串账、合计金额 ¥600→¥300 正确重算。后端+模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存。**E2E 踩坑记录（供后续复用）**：tab-shell 会复用已打开标签页（同 URL 不重载，曾出现 doc5 页面 `__OPENING_DOC__.id` 仍是 4 的假象），且外层壳对 Playwright 报 zero-size 致 `wait_for_selector` 可见性等待超时；绕行方案是直连 `?embedded=1` 并用 `state="attached"` / `click(force=True)` |
| BUG-2026-09-16-002 | [P3] 期初库存单行删除接口 `/opening_stock/<id>/line/<line_id>/delete` 是**死接口**：自 ARCH-OS-DOC-01 引入起全仓库零调用点（前端 `opening_stock.html`、`app/static/js` 业务代码、Android App、`tests/` 均无引用），且无 A9 测试覆盖；一次仅删一行，用户诉求的"勾选多行一次删掉"用不上它 | **已废弃移除（2026-09-16）**：判定为 BUG-2026-09-16-001 批量接口的**能力重复实现**，按 R6"同一能力不留两处实现、避免规则各自漂移"直接删除路由（非仅标 deprecated 注释——留着仍会被后人误接成第三条删行路径）。**移除前已全仓库确认零消费方**：`grep` 模板 / 静态 JS / Java / Kotlin / Dart / tests / scripts 全部无调用。**替代方案**：删单行请调 `POST /opening_stock/<id>/lines/delete` 传单个 `line_id`——语义、回冲规则、越权防护与返回体完全一致，且该接口额外具备 A8 入参校验与去重幂等。原实现以 tombstone 注释完整留档在 `app/routes/opening_stock.py`（含 404 文案、越权校验、回冲理由串），供日后追溯，并写明"不要恢复本接口"的原因。**回归**：新增 `TestDeprecatedSingleLineDeleteRoute` 2 项锁死结局——①断言路由表不再注册该路径（并断言 `/lines/delete` 仍在，确保删的是死接口而非把删行能力整体删掉）；②手工拼老 URL 只能得 404。**变异测试验证有效性**：临时恢复该路由后两项如期 FAIL。期初库存全量 **125 passed、1 skipped、0 failed**（上一轮 123 + 新增 2），`scripts/lint_wms_rules.py` 0 违规，`verify_wms_bugs.py` 无新增 FAIL（4 个 AI 模块 FAIL 为既有基线）。后端路由删除，**生产需重启 WMS 服务生效（R3）** |
| BUG-2026-09-16-004 | [P2] 期初库存**导出**功能不可用（用户原话：「期初单据导出功能也有问题」，未给现象，实测复现出三处叠加缺陷，任一处都足以让文件不可用）：①**换行符写错 → 整个文件塌成一行**——`new Blob([...lines.join('\\n')])` 写在单引号字符串里，`'\\n'` 是「反斜杠+n」两个字面字符而非换行符，导出内容成了 `"仓库编码","物料编码",…"备注"\n"WH001",…`（其中的 \n 是可见文本），Excel/WPS 打开只有第 1 行有内容、其余全挤在一个单元格；同仓库 `in_order_add.html` / `out_order_add.html` 用的都是正确的 `'\n'`，只有本模板写错，属 R6 意义上的"同能力他处正确、此处漂移"。②**导出列序与导入列序不一致 → 导出的文件无法回导**——导出原为 9 列（仓库,物料编码,物料名称,规格,单位,数量,单价,期初余额,备注），而粘贴导入 `parsePasteLines` 按 6 列取值（仓库,编码,数量,单价,备注,日期），即"导出的第 3 列是名称、导入却当成数量"，用户「导出→改价格→导回」的常规闭环必然失败。③**导入解析不认引号 → 带引号的 CSV 每列都解错**——原用 `line.split(/Tab 或逗号/)` 裸切，不剥引号也不识别引号内逗号，`"M001"` 解析出带引号的 `"M001"`（物料匹配失败），`"含逗号,的备注"` 还会被从中间切开导致整体错列。node 实证：导出行 `"WH001","M001","轴承",…` 回导后得到 仓库=`"WH001"`、物料编码=`"M001"`、数量=`"轴承"`——全列错位 | **已修复（2026-09-16）**：①换行改为真实 `'\n'`（与 `in_order_add.html`/`out_order_add.html` 同口径），前置 BOM 保证 Excel 正确识别 UTF-8 中文；②导出列序统一到后端 `/opening_stock/import/template` 官方模板的 9 列（仓库编码,物料编码,物料名称,规格,单位,数量,单价,备注,日期），表头行与数据行统一走 `csvCell()` 加引号（原表头是裸 `join(',')` 与数据行格式不一致），新增 `warehouseCodeById` 映射取真实仓库编码，日期取真实存在的 `headerDocDate`（原引用的 `docDate` 元素在模板中并不存在，会导致日期列恒空）；③导入侧新增 `splitCsvLine()`——支持双引号包裹、`""` 转义、引号内逗号，同时兼容原有裸 Tab/逗号文本；`parsePasteLines` 自动跳过表头行、按 `parts.length >= 9` 识别导出格式列序，保证「导出→改→粘贴导入」闭环；④顺带修两处体验缺陷：空单据点导出原静默下载一个只有表头的文件，现提示「没有可导出的明细行」并 return；导出文件名改为带单据号（`opening_stock_QS26090001.csv`，新建单据为 `_new`），不再多单互相覆盖。**回归**：新增 `tests/test_opening_stock_export_csv.py` 12 项——T1 换行必须真实且不得含字面量反斜杠n、T1b 静态兜底扫非注释代码、T2 表头与后端官方模板列序逐字一致（单一事实来源交叉校验）、T3 导出→回导字段逐项一致（含带逗号备注不裂列）、T4 `splitCsvLine` 引号/转义/引号内逗号/裸 Tab、T5 表头行自动跳过、T6 空单据提示不下载、T6b 非空单据文件名带单据号、T7 原有宽松粘贴格式（Tab/裸逗号/缺日期列）行为不变、T8-T10 静态契约。**测试设计要点**：测试不重写一份 JS 逻辑做"模拟"，而是从模板**抽取真实函数**在 node 中执行（`exportRows` 真实跑，仅桩掉 Blob/URL/createElement 截获产出），否则实现与测试各写一套、改了实现测试仍绿。**三组变异测试验证用例有效性**：①换行还原成 `'\\n'` → T1/T1b/T3 如期 FAIL；②列序回退为旧 9 列 → T2 如期 FAIL；③删掉空单据守卫 → T6 如期 FAIL。**真实浏览器 E2E 通过（16/16 断言、零 pageerror）**：Chromium 登录 → 新建单据灌 3 行 → 点导出实际下载文件 → 校验含真实换行（4 非空行）、无字面量反斜杠n、表头列序与官方模板一致、3 数据行、带逗号备注未裂列 → 把导出的 CSV 原文喂回 `parsePasteLines` 得 3 行零错误。模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |
| BUG-2026-09-16-005 | [P2] 期初库存明细行**行内删除图标静默失效**：`deleteRow(index)` 只做 `rows.splice()`，删的是**前端数组**——已建账的行必须再点一次「保存」才会由后端差集回冲落库，而界面**没有任何提示**。用户点删除图标看见行消失了、以为删成功就直接离开页面，下次打开该行又回来了（库存也没回冲），属"看着生效、实际没落库"的静默失效。此为 BUG-2026-09-16-001 批量删行排查时一并发现的同根因遗留点（当时用户未拍板，本轮按指令「全部都要修」处理） | **已修复（2026-09-16）**：`deleteRow` 按行是否已建账分流，与 `batchDeleteSelectedRows` **完全同一口径**（避免同类点规则漂移 R6）——①**已建账行**（有 `line_id`）→ 弹确认框（文案说明「已建账，将立即从库存中扣回，此操作不可恢复」）→ 确认后调 `POST /opening_stock/<id>/lines/delete` 传单个 id，立即物理删除 + 库存回冲，成功后本地摘行并提示；**接口失败时不摘行**，避免界面显示已删而后端其实还在；②**未保存行** → 仅从录入网格移除（不发任何请求），但明确提示「已移除「XXX」（尚未保存，点「保存」后才生效）」，不再让用户误以为已落库；③无 `OPENING_DOC` 时兜底本地移除，不误打 `/opening_stock/null/lines/delete`。删除图标 tooltip 也按状态区分（已建账显示「删除本行（已建账，将立即回冲库存）」，未保存显示「删除本行（尚未保存）」）。**回归**：新增 `tests/test_opening_stock_delete_row_persist.py` 8 项——T1 已建账行走批量接口（断言 URL 与 payload 为单 id）且成功后摘行、T2 确认框须提及库存回冲且用户取消则不发请求行不动、T3 接口失败时行必须保留、T4 未保存行不发请求且提示含「尚未保存」、T5 无单据不误打 null id、T6-T8 静态契约（不得退回"只 splice 不落库不提示"的三无实现）。**测试方式同 BUG-2026-09-16-004**：抽取模板真实 `deleteRow` 在 node 中执行，桩掉 confirm/WMS.api/toast 记录调用序列。**变异测试验证有效性**：把 `deleteRow` 还原成旧的静默 splice 实现后，6 项如期 FAIL。**真实浏览器 E2E 通过**：点第 2 行（M002）删除图标 → 本地立即摘除 → **刷新页面确认该行不再复活**（证明真正落库，而不只是从 DOM 消失）→ 未保存行删除后弹出「尚未保存」提示；服务端核对一致：单据明细由 3 行变 2 行、`Material` M002 stock 由 5 回冲为 **0**、`StockTransaction` 新增 `qty=-5.0 / remark=期初单据删行回冲` 负向流水。模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |
| BUG-2026-08-25-002-补 | [P2] `batch_import.html` 遗漏一处记录级链接新窗口规则（**既有基线失败，非本次改动引入**）：`tests/test_bug_2026_08_25_002_doc_links_new_tab.py::test_t1` 在 `main` 上即 FAIL，报 `batch_import.html: <a class="btn btn-sm btn-outline-primary mt-1" href="' + res.detail_url + '">`。根因：BUG-2026-08-25-002 当时统一了 36 个模板 77+ 处记录级链接加 `target="_blank" rel="noopener"`，但 `batch_import.html` 里这处**由导入结果动态拼接**的「查看单据 X（可改日期）」链接漏加——该链接指向 ARCH-OS-DOC-01 整批导入生成的期初库存单据，属"进入某一项"的记录级链接，却在本页跳转，导入结果页（含成功/告警/错误明细）被顶掉。**归属确认**：已用 `git stash -u` 在干净 `main` 基线复跑，失败信息逐字一致，确认与本轮改动无关，属历史遗漏 | **已修复（2026-09-16）**：为该动态链接补 `target="_blank" rel="noopener"`，与其余记录级链接口径统一，保留导入结果页便于对照。**回归**：`tests/test_bug_2026_08_25_002_doc_links_new_tab.py` **3 passed**（原为 1 failed 2 passed）。另全仓库重新扫描一遍记录级链接（`url_for('*_detail')` / `detail_url` / `_edit_page` / `safeJumpUrl(`），除该处外仅剩 7 处未加新窗口——逐条核对**全部是测试文件 EXCLUSIONS 中显式登记的排除项**（详情页同记录「编辑」模式切换与「返回」回退导航），按规则本就应保持本页跳转，无误伤。模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |

| BUG-2026-09-16-006 | [P1] 生产打开期初库存单据列表即 500：`sqlite3.OperationalError: no such table: opening_stock_doc`（2026-09-16 生产日志实测，栈顶 `routes/opening_stock.py:54 opening_stock_list` 的 `query.paginate`；启动日志同时显示 `[Auto-Fix] opening_stock.doc_id 已补缺列` + `Startup database initialization skipped by environment`）。根因：ARCH-OS-DOC-01 引入的单据头表 `opening_stock_doc` **建表**只发生在 `db.create_all()` / `auto_migrate_database()`（Step 1），历史行归单只在 `auto_migrate_database()`（Step 5）；而 `start_wms_offline.bat` / `start_wms_auto.bat` 默认 `WMS_NO_DB_TOUCH=1` 把迁移整体跳过，BUG-2026-09-15-007 的 `ensure_opening_stock_doc_columns()` 只补了 `opening_stock.doc_id` **列**、没建**表**——「功能上线前建的存量库 + WMS_NO_DB_TOUCH=1 重启」叠加态下表根本不存在，单据列表/首上下末导航/新增/编辑/删除**所有消费点**齐 500。**R6 同根因历史已查**：BUG-2026-08-22-001（缺 `excel_print_template` 表）、BUG-2026-09-12（缺 `department` 表）均为"建表只在迁移里、迁移被开关跳过"，当时各修各的消费点，本次为第 3 次复发 | **已修复（2026-09-16）**：新增 `ensure_opening_stock_doc_table()`，仿 `ensure_excel_print_template_table` 独立 sqlite 连接、独立于迁移开关无条件执行、幂等（WAL + `busy_timeout=60000`，失败仅记日志不阻断启动，锁冲突下次启动自愈，R4），启动期注册在 `ensure_opening_stock_doc_columns()` 之后。**防 R6 漂移**：建表 DDL 与历史回填从 `auto_migrate_database()` 抽出公共函数 `_create_opening_stock_doc_table()` / `_backfill_opening_stock_docs()`，迁移与兜底**两处共用同一实现**（静态测试锁死 DDL/INSERT 全仓库各只有一份）。**必须回填而非只建空表**：只建空表会让单据列表"能打开但空空如也"，用户历史期初在界面上等同消失（数据没丢也会误认丢失而重复录入）；回填口径与迁移一致——按 (建账日期, 仓库) 归单、单号 QS+YYMM+4位、`date` 为 NULL 的行保守不归单、只加归属不改账（quantity/price/amount 与 Material.stock 不动）。**职责边界**：老库 `UNIQUE(material_id, warehouse_id)` 的 12 步重建与 `uix_opening_stock_line_doc` 唯一索引仍属 `auto_migrate_database()`（极端脏数据下建唯一索引失败会连累建表回滚，兜底路径不碰）；`doc_id` 列顺带兜底使函数与注册顺序无关。**回归**：新增 `tests/test_ensure_opening_stock_doc_table.py` 8 项——缺表补建（列/索引/归单分组/单号递增/NULL日期不归单/不改账）、原 500 分页查询恢复、幂等重复执行、已有表与人工改动不动、全新库建空表、库文件不存在静默返回、迁移与兜底共用公共函数静态断言、**子进程 `import app` + `WMS_NO_DB_TOUCH=1` 模拟生产启动完整复现**（缺表被补建、历史归单 3 张单）。期初库存/迁移/ensure 相关 **193 passed、1 skipped、0 failed**；`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端改动，**生产需重启 WMS 服务生效（R3）**——重启后兜底自动建表归单，无需人工操作数据库 |

| BUG-2026-09-16-007 | [P2] 期初库存单据删除后台账仍残留流水（用户原话：「期初库存被我删除了怎么还有单据，搞得乱七八糟的」→ 明确口径「我的要求是删除了就没有流水」）。根因：`_reverse_opening_stock_line` 删单/删行时**追加一条 quantity=-N 回冲流水**（remark=期初单据删除回冲/删行回冲/批量删行回冲/全量删除回冲），明细行物理删除后，其建账 +N 与回冲 -N 两条流水都留在 `stock_transaction`，库存台账继续显示单据编号 `opening_stock-<id>` 指向已不存在明细行的记录（悬挂引用）。且与本仓库既有惯例不一致——入库单/出库单/调整单/售后出库单删除时都是**同步删除自身流水**（in_order.py:2029 / out_order.py:1072 / adjustment.py:576 / after_sale_out.py:538，注释明写「避免库存台账保留指向已删除单据的悬挂引用」），期初库存是唯一走"加回冲流水"的岔路（R6 同能力两处口径漂移） | **已修复（2026-09-16）**：①**删除路径改口径**：`_reverse_opening_stock_line` 不再追加 -N 回冲流水，改为**物理删除该明细行的全部库存流水**（建账 +N 与历次编辑差额；数量为 0 的行也先清流水再早退，覆盖"先建 5 再改 0"残留的 +5/-5 编辑流水）；库存余额回冲（Material.stock / 库位账）与负库存中文提示口径不变，`reason` 参数保留仅兼容既有调用点。5 处删除消费点（整单删除/保存差集删行×2/批量删行/删除全部）共用同一函数，一次改动全部收口。②**历史数据清理**：新增 `cleanup_dangling_opening_stock_transactions()`，启动期独立于迁移开关无条件幂等执行（busy_timeout=60000，失败仅记日志不阻断，R4）——物理删除「reference_type='opening_stock' 且 reference_id 已不在 opening_stock 表」的悬挂流水；**误删防护**：material.py「新增物料初始库存」流水复用同 reference_type 但 reference_id 是 **material.id**（remark='新增物料初始库存'），按 remark 排除（id 域会撞号，仅靠 id 无法区分）。**回归**：新增 `tests/test_cleanup_dangling_opening_stock_transactions.py` 5 项（悬挂 +N/-N/NULL-remark 清理、存世行与 material.id 域与他类型流水保留、幂等、缺表/缺文件静默、整单删除集成、启动接线与删除语义静态断言）；改写 `test_opening_stock_batch_delete_lines.py` T6 与 `test_opening_stock_delete_all.py` T6 为新契约（流水物理移除、无新增负向流水、未删行不串账、库存回冲不变）。**测试基建踩坑**：新测试类初版逐表 wipe 在全量 pytest 共享内存库下撞 `foreign_keys=ON`（app.py:6062 引擎级强制）残留行级联出 3 failed+1 error；改为 `drop_all+create_all`（test_material_delete_missing_ai_table 同款）后，选择集（72 文件）**289 passed、0 failed**，与干净 main 基线（284 passed）差值恰为新增 5 项，54 个 subprocess 型 ERROR 为改动前既有基线。`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端改动，**生产需重启 WMS 服务生效（R3）**——重启时自动清理历史悬挂流水，台账即刻干净 |

| BUG-2026-09-16-008 | [P2] 从未使用打印却每天半夜收到「打印任务滞留」告警（用户原话：「我没有打印为什么有这个消息」，截图两条告警时间 2026-09-15 00:00:35 / 2026-09-16 00:00:00，同一任务 ID 9 / 出库单 ID 169）。根因链路：①手机扫码/移动端提交入出库成功后 `enqueue_auto_print_job` **无条件**自动创建打印任务（docstring 明写"任务始终创建"），用户没点打印、提交动作本身就建了任务；②无任何在线打印工作站，任务永远 pending；③`check_print_health` 每分钟巡检按「同一任务**当日**只告警一次」去重——任务跨天仍 pending，每天零点过后第一次巡检即重新告警；④打印工作台只有完成/失败接口，**没有取消任务能力**，滞留任务用户删不掉，骚扰无解 | **已修复（2026-09-16，按用户拍板「加自动打印总开关」）**：①新增系统设置 `auto_print_on_submit`「提交后自动打印」（默认**开**，保持既有行为不影响依赖自动打印的场景；系统设置 → 打印参数可关）。②关闭后 `enqueue_auto_print_job` 入口直接返回 None 不建任务——6 个自动调用点（mobile 扫码提交×2/草稿确认×2、native App 入出库×2）共用同一函数一次收口（R6），调用点均不使用返回值，业务单据照常提交，手动打印（手机端"打印单据"按钮走 `/print_queue/jobs`，`source_event='manual'`）不受影响。③`check_print_health` 巡检在开关关闭时把滞留的**自动来源** pending 任务逐批作废（`status='cancelled'` + 中文作废原因），手动任务与阈值内新任务不动；作废在告警开关判断**之前**执行，队列卫生与告警解耦，作废后自然不再产生滞留告警——用户关掉开关后**无需重启**，下一分钟巡检即清净。新增 `AUTO_PRINT_SOURCE_EVENTS` 常量登记全部自动来源事件（静态测试锁定调用点字面量 ⊆ 常量，新增调用点漏登记即报红）。**回归**：新增 `tests/test_auto_print_on_submit_switch.py` 5 项（默认开建任务/关闭不建/关闭巡检只作废滞留自动任务且不再告警/开启巡检不作废/静态接线）；`tests/test_print_alerts.py::test_check_print_health` 适配 stats 新增 `auto_cancelled` 键。打印/移动端/原生接口相关 **488 passed、0 failed**；`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端改动，**生产需重启 WMS 服务生效（R3）**；重启后到「系统设置 → 打印参数」关闭「提交后自动打印」，约 1 分钟内滞留任务自动作废、告警停止 |

| BUG-2026-09-16-009 | [P1] 手机端（Android）提交的期初库存**不归任何单据**：`native_api.py` 的 `native_api_opening_stock_submit` 调 `_apply_opening_stock_balance` 时**漏传 `doc_id`**，明细行 `doc_id=NULL`。后果（跨端黑洞）：手机上建的期初在 PC 端 `/opening_stock` 单据列表**永远看不到**、不能按单打开/改日期/删除，只剩「删除全部」一条路；`_opening_stock_compat_doc` 的 docstring 明写兼容单就是为「粘贴导入、移动端」等无单调用方准备的，但移动端原生 API 这条接线被漏接。此为 ARCH-OS-DOC-01 改造时的同类漏接点（batch_save 兼容分支已接，native_api 漏接），与 BUG-2026-09-15-007 开发期缺陷①（`doc_id` 赋值静默丢失）同根因族 | **已修复（2026-09-16）**：`native_api_opening_stock_submit` 取 `_opening_stock_compat_doc(payload.get('date'), generate_order_no)` 并把 `doc_id=compat_doc.id` 传入入账函数——与 batch_save 兼容分支**同一口径**：无单写入统一归 QSLEGACY+YYMM 兼容单（幂等复用，不会每提交一次建一张单把列表刷爆），「同 (物料,仓库) 单行 upsert」语义不变。**自愈历史数据**：`_apply_opening_stock_balance` 既有逻辑在 `doc_id` 非空时会把历史 NULL 悬空行收养进该单，手机端下次提交同 (物料,仓库) 即自动归单，无需人工修数。**回归**：`tests/verify_mobile_opening_stock_api.py` 新增 3 项——S6 提交行 doc_id 非空且归 QSLEGACY 单 + PC 端 `/opening_stock` 列表页 HTML 可见该单号（跨端可见性闭环）、S7 历史 doc_id=NULL 悬空行被收养且数量按差额更新、S8 静态契约锁死「提交链路必须传 doc_id」防重构再漏。期初库存/原生 API 相关 **158 passed、1 skipped、0 failed**（原 155 + 新增 3）；`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端改动，**生产需重启 WMS 服务生效（R3）** |

| BUG-2026-09-16-010 | [P1] 手机端期初建账两处操作硬伤（仓库管理专家评审 2026-09-16，用户拍板"先做 P0"）：①**连续扫码同一条码数量被覆盖成 1**——`OpeningStockViewModel.addLine` 对同编码行做 `existing.copy(quantity = quantity)` **覆盖**合并，扫码回调每次又只传 manualQty（默认 1），仓管扫 100 个轴承提交数量恒为 1，AI-MOB-CONTINUOUS-SCAN-01 的连续扫描在期初场景名存实亡（扫码场景按"件"计数，合并必须累加；同仓库入库扫码 `ScanViewModel` 即累加口径，此处为 R6 同能力漂移）；②**已录入行不能改数量**——行卡片只有删除按钮，数量录错只能删行重扫 | **已修复（2026-09-16）**：①`addLine` 同编码合并改为**累加**（`existing.quantity + quantity`），连续扫 N 次即 N 件，手动添加同编码亦为累加语义；②新增 `updateLineQuantity(index, quantity)`（确切值、负数拦截）+ 行卡片 `clickable` 打开编辑弹窗（数字键盘 + ±1 步进 + 「删除该行」「取消」），"扫码/添加负责加、点行负责改成对的数"两条路径互补。弹窗索引防御：行已被移除时自动关闭不崩溃。**回归**：新增 `tests/verify_android_opening_qty_merge.py` 4 项静态契约——T1 累加语义锁死（`existing.quantity + quantity` 必须在、`copy(quantity = quantity)` 出现即红）、T2 ViewModel 声明与非负校验、T3 行卡片 clickable + 弹窗接线、T4 连续扫描加行链路未断。Android 相关契约测试 **35 passed、0 failed**（含 continuous_scan / vm_method_pairing / keyword_search / scan_feedback / qty_keyboard 无回归）。纯 Kotlin App 改动，**随下次 APK 构建发布生效**，服务端无需重启 |

| BUG-2026-09-16-011 | [P1] 期初库存单据网格**没有库位列**（仓库管理专家评审 2026-09-16，用户拍板"先做 P0"）：开启库位管理后按 AGENTS.md 规则二「仓库和库位均为必填」，后端 `_apply_opening_stock_balance` 与 `/opening_stock/save` 早已接收 location 入参、编辑页 `edit_rows` 也带 location 字段，但前端网格没有任何库位录入入口——期初永远落不到真实库位，只能以仓库名作占位行进库位账（BUG-2026-08-16-002 的占位兜底被当成了常态）。入库单 `in_order_add.html` 已有「开关传模板 + 必填红星」的成熟模式，期初为漏接的同类点 | **已修复（2026-09-16，与入库单同口径）**：①`/opening_stock/add` 与 `/opening_stock/<id>` 两个路由把 `location_management_enabled()` 传入模板；②开启时网格在「仓库」列后渲染「库位」列（红星必填标识，`LOCATION_ENABLED`/`GRID_COLSPAN` 两个 JS 常量随开关注入，空态 colspan 由写死 12 改为常量避免列数错位）；③`existingRows`/`emptyRow`/`collectItems` 全链路携带 location——编辑已有单据行库位正确回填，保存时随 items 传到后端（后端原有支持，零改动）；④保存前必填校验：开启库位管理后非空行缺库位即拦截并中文提示行号（仓库兜底解析之后再校验），关闭时行为完全不变。**范围说明**：粘贴导入/Excel 模板/导出 CSV 的库位列与手机端库位选择另行任务，本轮只补网格录入主路径。**回归**：新增 `tests/test_opening_stock_location_column.py` 5 项——开/关两种开关态渲染、编辑页回填、保存落库且**库位账落到真实库位而非占位行**（端到端）、静态契约（collectItems/emptyRow/单元格守卫/GRID_COLSPAN/必填提示）。**测试基建踩坑**：夹具 `_wipe` 漏清 `LocationInventory` 导致整文件运行时 T3 残留库位账 100 + T4 再入 100 = 200 与断言不符（单跑 T4 必过、整跑必挂），已补清表。期初库存/库位相关 **319 passed、2 skipped、0 failed**；`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端+模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |

| BUG-2026-09-16-012 | [P1] 期初库存编辑页**整库内嵌物料**（仓库管理专家评审 2026-09-16，用户拍板"先做 P0"）：`/opening_stock/add` 与 `/opening_stock/<id>` 两个路由都执行 `Material.query.all()` 把全部物料序列化成 `materialData` 塞进页面，前端联想再全量 filter——物料上千时首屏 HTML 数 MB、联想卡顿，且属 R1 点名的"把全量当默认"模式。手机端 `/api/material/search` 早有服务端搜索能力，PC 期初页是漏改的同类点 | **已修复（2026-09-16）**：①两个编辑页路由删除整库查询与 `material_options` 内嵌（性能落点）；②联想改走既有 `GET /api/material/search?keyword=`（web 会话可用），防抖 200ms + 序号防竞态（后发先至丢弃旧结果），命中写入本地缓存 `materialCache`/`materialCodeIndex`；空关键字不再展示"全部物料前 30 条"（整库已不内嵌），改为提示输入关键字；③粘贴导入一次性几十~几百个编码，逐个调搜索会打满请求——新增 `POST /opening_stock/materials/lookup` 按编码**批量**预热缓存：A8 pydantic 校验（1~500 个、空白剔除、去重保序），**大小写不敏感匹配**（与原 `materialData.find` 的 toLowerCase 比较同口径，粘贴来源大小写差异不再误报"物料不存在"），payload 复用 `api_material_payload`（与移动端搜索同一构造器，R6 防字段漂移），返回 items + missing 清单；④`selectMaterial`/`parsePasteLines` 一律查缓存，`confirmPasteImport` 先 `extractPasteCodes` 批量预热（缓存已覆盖时零额外请求）再走原同步解析，行级校验逻辑零改动。**回归**：新增 `tests/test_opening_stock_material_search.py` 5 项（页面无内嵌+路由无整库查询静态锁、lookup 命中/missing/payload 字段齐、入参与未登录校验、同一 payload 构造器静态防漂移、模板契约）；`test_opening_stock_export_csv.py` harness 同步改缓存 Map + 真实抽取 `cacheMaterial`/`findMaterialByCode`（仍执行模板真实源码，非重写模拟），导出→回导闭环 12 项全过。**测试基建踩坑×2**：①静态断言须先剥注释/docstring，否则说明文字里的 `Material.query.all()` 字样误报；②夹具常驻 app_context 泄漏登录态，匿名用例须先显式 logout（同 BUG-2026-09-15-008 记录）。**基线对账**：大选择集（opening_stock or material，253 项）运行——干净基线 248 passed + 59 errors（既有共享内存库污染类），修复后 **254 passed + 59 errors**（ERROR 零新增；新测试文件改用 drop_all+create_all 免疫模式，未给基线添错）。`lint_wms_rules.py --staged` 0 违规、`lint_no_raw_post_fetch.py` 通过。后端+模板改动，**生产需重启 WMS 服务生效（R3）**，浏览器 Ctrl+F5 清缓存 |

| 类型 | 进入条件 | 处理方式 |
|------|----------|----------|
| 真实 BUG | 有代码证据、可触发路径、错误结果 | 修复并加入回归验证 |
| 风险项 | 理论可触发，但依赖配置或边界条件 | 记录缓解措施，必要时加监控 |
| 配置项 | 生产环境需要强制配置或关闭调试 | 固化配置检查 |
| 误报 | 代码已有保护，或不符合实际业务流程 | 记录原因，不重复报 |
| 暂缓 | 技术限制或迁移成本较高 | 明确风险和后续条件 |

## 仓库技术债清理

> 本节的变更**不是 BUG**（无功能缺陷、无错误结果），而是仓库卫生/技术债类改动：
> 清理误提交的运行期产物与一次性脚本。**单独成节，不计入「已修复并纳入回归」的 BUG 计数**，
> 避免污染 BUG 统计口径。

| 编号 | 背景 | 措施与验证 |
|------|------|----------|
| CLEAN-2026-09-28-001 | 仓库跟踪了 **87 项一次性产物**，均为零代码引用的开发残留：①运行期上传图片与 E2E 截图 56 项（`uploads/material_images/*.png` 39 + `app/uploads/material_images/*.jpg` 3 + `.wms_preview/*` 13 + `wms_after_login.png`）；②审计/报告 JSON 产物 8 项（`qa_scan_results.json`、`wms_*_audit*.json`、`wms_browser_e2e_*.json`、`wms_io_audit_data.json`、`performance_report_20260713_074147.json`、`scripts/_routes.json`——文件名带日期戳且无下游消费）；③调试脚本 9 项（`diag_push_tmp.py`/`timing_push_tmp.py`/`cdp_*.py`×3/`screenshot_wms.py`/`qa_scan.py`/`start_nginx.bat`/`stop_nginx.bat`）；④`scripts/_*.py` 14 项（一组自洽脚本族，`_btn_harness` 被 5 个同族脚本 import，但 CI/Makefile/hooks/pytest 全部零引用）。另：根级 `uploads/`、`app/uploads/`、`.wms_preview/` **未被 `.gitignore` 覆盖**（既有规则只挡了 `app/static/uploads/`），故运行期数据持续被误提交 | **已清理（2026-09-28，commit `fa8853d` / 远程 `fc3e3f88`）**：①全部用 `git rm --cached`（**保留本地文件**），87 项移除，跟踪文件 **1571 → 1484**（仓库体积约 −2.2M，其中运行期图片 ~1.6M）；②`.gitignore` 补 3 条**前导斜杠锚定**规则 `/uploads/`、`/app/uploads/`、`/.wms_preview/`（避免与既有 `app/static/uploads/` 第 26 行语义混淆），`git check-ignore -v` 逐条验证生效；③`python scripts/check_ci_green.py` 开工前确认三工作流全绿，CI 后 `WMS CI #1293` / `WMS AI Verification #1588` / `WMS Perf Baseline #148` 均 success；④全量回归 **2979 passed / 87 skipped / 0 failed**（与基线一致）。**生效确认**：commit `fa8853d`（本地）/ `fc3e3f88`（远程 main）；CI 三工作流 success（`WMS CI #1293 @fc3e3f88`）；仓库跟踪文件数 1484 已由 GitHub API `GET /git/trees?recursive=1` 复核。**纯仓库结构改动，不涉及 `app/` 运行时代码与模板，无 R3 重启要求（生产拉取后本地文件本就存在，运行不受影响）。** **两项「看似可删实为活依赖」经检查阶段识别并保留**：①`start_qa_server.py`——承载 `BUG-2026-09-25-003` 的现场证据（`WMS_BUG_BASELINE.md:1272/1274` 引用其 `:41` 绑定），且 `scripts/ci_check_inventory_identity.py:147` 注释"与 `start_qa_server.py` 的做法一致"（范式来源），删除会致台账悬空引用（违反 A13 可追溯性）；②`app/uploads/` **目录**须保留——CI 每个 job 执行 `mkdir -p app/logs app/instance app/uploads logs`，仅删其跟踪文件、不删目录。 **踩坑记录（供后续复用）**：1）**跨 `git` / GitHub API 比对文件名必须先统一编码**：`git ls-files` 默认开启 `core.quotepath`，中文名被转义加引号（`"AI-MOB-OFFLINE-01_\345\274\200..."`），而 API 返回原始 UTF-8，同一文件会被同时计入"删旧+加新"——本次首次比对误报"删除 111 / 新增 24"，改用 `git -c core.quotepath=false` 后恢复为真实的"87 / 0"；2）**`POST /git/trees` 带 `base_tree` 时，"不列在 tree 列表中" = 保留 base 条目，而非删除**——删除必须显式给 `{"path": p, "mode": "100644", "type": "blob", "sha": null}`；本次 API 推送首版因此静默未删（仅 `.gitignore` 生效），经"推送后校验远程 tree 文件数"发现并修正（`main` 为保护分支不可 force-push，故以新提交向前修正）；**推送前必须在创建 commit 之前断言新 tree 的文件数等于本地 `git ls-files`**；3）**演练环境必须是真的 git 仓库**：在 `tar` 解出的普通目录里跑测试，两个依赖 `git ls-tree`/`git ls-files` 的用例会因"非 git 仓库"报 exit 128 假失败；应改用 `git worktree add` 建真仓库副本；4）**图片零丢失的验证方法**：`comm` 比对根级 `uploads/material_images`(39) 与 `app/static/uploads/material_images`(42) 差异为 0，且 `app/utils.py:518 migrate_legacy_material_images()` 在 `legacy_dir` 缺失时 `return 0` 优雅跳过、存在时幂等补迁（启动日志实测 `Migrated 3 legacy material images to static uploads`）——**"删索引不删本地"是安全的前提**。 **未处理（留待决策，勿误认为已完成）**：`scripts/archive/`（30 项，其 `README.md` 自述为有意归档）与根目录 `.md` 计划/报告族（其中 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 为唯一 AI 开发总台账，禁止删除）；`§二 建议删` 的 `wms.cmd`/`install.cmd`/`说明.txt` 因 `build_portable_dist.bat` 会在发行包生成同名文件，需先确认打包流程。完整明细见 `/workspace/WMS仓库冗余文件清理明细.md`（含六维误删交叉验证） |

## 已修复并纳入回归

> **F4.4（2026-10-13） 拆分**：本章 325 条已按 BUG 编号月份迁移至 `docs/ledger/bugs/fixed-*.md`。
> 新修复条目登记到当月分片表尾（需含生效确认）。
>
> - [`fixed-2026-07.md`](docs/ledger/bugs/fixed-2026-07.md)（45 条）
> - [`fixed-2026-08.md`](docs/ledger/bugs/fixed-2026-08.md)（163 条）
> - [`fixed-2026-09.md`](docs/ledger/bugs/fixed-2026-09.md)（46 条）
> - [`fixed-unknown.md`](docs/ledger/bugs/fixed-unknown.md)（71 条）

## 已确认误报

| 编号 | 原问题 | 误报原因 |
|------|--------|----------|
| BUG-003 | 委外收货数量双倍计算 | 源码已有 autoflush 处理说明，sum 查询没有额外加本次数量 |
| BUG-008 | 全局确认框变量竞态 | 当前实现已使用确认队列，不存在 resolver 覆盖 |
| SCAN-2026-08-07-001 | `scan_wms_risks.py` 报 4 个 `\|safe` 候选：`alert.html:237`、`sales_reconciliation_report.html:147`、`print_out_with_html.html:63`、`print_in_with_html.html:67` | 逐个人工判真均为误报：①`alert.html` 全文件无 `\|safe`（行号漂移误匹配）；②`sales_reconciliation_report.html:147` 是 `chart_data\|tojson\|safe`，即 VULN-005 确立的标准安全写法；③两个打印模板的 `rendered_content` 由 `_render_html_print_content()` 生成，已经 `SandboxedEnvironment(autoescape=True)` 沙箱渲染 + `sanitize_print_html()` 白名单净化双重防护（VULN-001 已登记） |
| SCAN-2026-08-11-001 | 2026-08-11 全系统增量审计（app.py 28k 行 + routes/ 23k 行 + ai/ 21k 行 + JS 5k 行 + Android 增量）报 5 类疑似项 | 逐个人工判真均为误报：①"routes 未检查原子函数返回值"（transfer.py L427-438 / after_sale_out.py L390-406/L444-463）——源码逐条 `if not ok: rollback + return api_error`，证据齐全；②"providers.py 重试风暴/API key 泄漏"——`call_llm` 有界重试 `max_retries=2` + 指数退避 + 熔断器 `breaker`，日志只打异常对象不含 header/key；③"streaming.py 连接泄漏"——`stream_response_payload` 是纯字符串切片的有限生成器，Flask 响应结束自然关闭；④"app.py pickle RCE / 硬编码密钥 / 未参数化 SQL"——全仓 grep 无 `pickle/eval/exec/__import__`、无硬编码 password/secret/api_key，f-string SQL 仅存在于 `auto_migrate_database` 内部 DDL（表名/列名全部为代码内常量，非用户输入）；⑤"AI 路由缺权限"——`ai/routes.py` 17 条、`ai/v2_routes.py` 19 条全部 `@login_required`，能力校验在 tools 层 `AI_CAPABILITY_ROLES`（AI-AUTH-001 已登记）。审计同时确认：全部 `requests.*` 调用带 timeout；`subprocess` 仅存在于 restart.py/auto_update.py 固定参数部署脚本；无 `send_file/send_from_directory` 用户输入路径遍历；上传有 `MAX_CONTENT_LENGTH=50MB` + `ALLOWED_EXTENSIONS` + Excel 5MB 三层限制；lint A1-A10 0 违规、无裸非 GET fetch；`verify_ai_all.py --level smoke` 7/7 PASS（唯一失败项为沙箱缺 `requests` 依赖的环境问题，装依赖后 PASS，非代码问题） |

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
| BUG-2026-08-05-001 | 采购入库完成后下推单据功能失效：路由拆分迁移到 `app/routes/in_order.py` 时，`create_in_order_push` 使用了 `DocumentPushLine` 却漏导入，点击下推提交时抛 `NameError: name 'DocumentPushLine' is not defined`，页面提示"下推失败，请稍后重试" | 在 `create_in_order_push` 的 `from app import (...)` 中补入 `DocumentPushLine`，与 `out_order.py` / `after_sale_out.py` 的下推导入保持一致。回归：`scripts/verify_inbound_push.py`（6 种下推组合、追溯、数量上限、幂等、权限、库存生命周期、客供料拦截 Full PASS） |
| BUG-2026-08-05-002 | 采购入库单点击"完成入库"失败、单据停在草稿、下推按钮不出现：`complete_in_order` / `update_completed_in_order` / `update_in_order` 三个函数的延迟导入均漏 `InOrder`，点击完成入库即抛 `NameError: name 'InOrder' is not defined`，被 `except` 吞掉返回"提交失败，请稍后重试" | 在三个函数的 `from app import (...)` 中补入 `InOrder`；并在 `complete_in_order` 的 `except` 分支补 `app.logger.exception` 记录堆栈。新增静态检查 `scripts/check_in_order_imports.py` 扫描全部使用 `InOrder` 的函数确保导入覆盖。回归：`scripts/repro_complete_in_order.py`（完成入库→status=completed→can_push），`scripts/verify_inbound_push.py` Full PASS，`make check` 116 passed |
| BUG-2026-08-05-003 | 物料无法删除：`delete_material` 的引用完整性检查漏掉了 `PurchaseOrderItem` / `SalesOrderItem` / `AIMaterialAlias` / `AIDocumentItem` 四张表。被采购订单或销售订单明细引用的物料走不到"存在业务引用，建议改为停用"分支，直接 `db.session.delete(material)` 触发数据库外键 `NOT NULL constraint failed`，被 `except` 捕获返回晦涩的"数据库操作失败: (sqlite3.IntegrityError)..."，用户感知为"物料删不掉" | 在 `delete_material` 的 `from app import (...)` 补入 `PurchaseOrderItem` / `SalesOrderItem` / `AIMaterialAlias` / `AIDocumentItem`，并在引用完整性校验里补这四个表的 `material_id` 检查，与既有引用拦截逻辑一致。回归：`scripts/repro_material_delete_ref.py`（PO 引用/SO 引用被拦截且明细保留、无引用删除成功），新增 `tests/verify_app_py_split_material.py::test_delete_material_referenced_by_purchase_order_item`，`make check` 116 passed |
| BUG-2026-08-05-004 | 物料仍无法删除（前端报 `Unexpected token T, "Internal S"... is not valid JSON`）：`delete_material` 的引用完整性检查是裸 `AIMaterialAlias.query... or AIDocumentItem.query...` 连环查询，且删除走 `db.session.delete(material)`。当生产/旧库缺 AI 关联表（`ai_material_alias` / `ai_document_item`，AI 能力代码已上线但库未跑迁移）时，①引用检查首个缺表即抛 `OperationalError` 未捕获 → 整个接口打成 500 HTML；②即便引用检查侥幸通过，`db.session.delete` 触发 ORM 级联加载缺失 backref 表同样抛 500。前端把 HTML 当 JSON 解析 → 报 `Unexpected token 'T'`，用户感知"物料删不掉" | ①引用检查重构为逐表 `try/except` 循环，某表缺失/查询抛错时仅跳过该表（视为无引用）并记 warning，绝不把接口打成 500 HTML；②主数据删除改用 raw SQL `DELETE FROM material WHERE id=:id`（先清理 `LocationInventory`），绕过 `db.session.delete` 的 ORM 级联加载缺失 backref 表；单条失败 `db.session.rollback()` 防 PendingRollback 污染后续迭代。回归：`tests/test_material_delete_missing_ai_table.py`（2 用例：缺失 `ai_document_item` 表时删除无引用物料返回 JSON 200 且物料已删；被引用物料仍被拦截返回 JSON 400），`pytest` 2 passed，lint A1-A10 0 违规 |
| BUG-2026-08-05-005 | 物料删除报"Unexpected token 'I', "Internal S"... is not valid JSON"（BUG-2026-08-05-004 的防护层补强）：前端 `csrfFetch`/`postJsonForAction` 发 JSON POST 只带 `Content-Type: application/json`（fetch 默认 `Accept: */*`、不带 `X-Requested-With`），`wants_json_error_response()` 漏判这类请求；视图一旦抛异常，`handle_exception` 非 JSON 分支直接返回英文纯文本 `Internal Server Error`（DEBUG/非 DEBUG 两分支相同），前端 `r.json()` 解析失败，真实错误完全丢失；且 500/CSRF 处理器里 `db.session.rollback()` 未兜底，连接损坏时异常逃出 Flask 会被 waitress 兜底为英文纯文本 500 | ①`wants_json_error_response()` 新增 `request.is_json` 判断：请求体是 JSON 即视为 AJAX 调用，统一回 JSON 错误；②`handle_exception` 非 JSON 分支改为中文"服务器内部错误，请稍后重试"（DEBUG 附堆栈）；③新增 `_db_safe_rollback()`，500/Exception/CSRF 三个全局处理器的 rollback 全部兜底。回归：`tests/verify_bug_2026_08_05_005_error_handler_json.py`（JSON POST 触发 500 返回 JSON、rollback 失败仍返回 JSON、CSRF 失败返回 JSON 400、is_json 识别），`pytest tests/` 116+4 passed，lint 0 违规 |
| BUG-2026-08-05-006 | 采购入库单/销售出库单新增页复用"其他出入单"工具栏，导入/导出/导入导出模板/智能分享/首张/上一张/下一张/末张按钮均为"功能待开发"占位（原误登记为与本表 BUG-2026-08-05-001 重号，2026-08-05 审计更正编号） | 重写 `in_order_add.html`/`out_order_add.html` 的 `handleOtherOrderToolbar`：导入→`showPasteModal()` 粘贴导入；导出→`exportDetailRows()` 导出当前明细 CSV（带 BOM）；导入导出模板→`showImportTemplateHint()` 提示支持列；删除→`WMS.api.post('/in_order\|out_order/{id}/delete')` 后返回列表页；智能分享/首张/上一张/下一张/末张→引导提示（新增单无导航目标）。浏览器实测新增页全部工具栏按钮按预期工作，无"功能待开发"占位提示。commit `4696ba5d` |
| BUG-2026-08-05-007 | pytest 全量跑时 `tests/test_material_delete_missing_ai_table.py` 两用例 setup 报 `RuntimeError: Refusing db.drop_all outside testing in-memory database`：pytest 按字母序收集模块，`test_get_default_warehouse.py` 等先 `import app` 且未设 `DATABASE_URL`，app 被缓存为文件库配置；后续模块再设内存库 env 已无效，`guarded_drop_all` 拒绝执行。单跑该文件通过、全量跑即挂，属测试隔离缺陷 | 新增 `tests/conftest.py`：先于一切测试模块导入，`os.environ.setdefault` 固定 `DATABASE_URL=sqlite:///:memory:` / `WMS_BOOTSTRAP_PASSWORD=admin` / `WMS_DEBUG=0` / `WMS_SKIP_AUTO_UPDATE=1`，app 首次导入即内存库，与导入顺序无关。回归：`pytest tests/ -q` 118/118 passed（修复前 116 passed + 2 errors） |
| BUG-2026-08-05-008 | 工单领料单（`/requisition`，ProductionRequisition）全链路无仓库字段，违反 AGENTS.md「领料出库仓库必填」规则（2026-08-05 全面审计发现） | ①模型加 `warehouse` 列（nullable 兼容存量）+ `auto_migrate_database` 补列迁移并回填默认仓；②`document_table_form.html` requisition 分支加必填仓库下拉（新建预选默认仓）；③`save_requisition_table`/`add_requisition`/`update_requisition`/`complete_requisition` 全链路仓库必填校验（未填自动带入默认仓，无默认仓拒绝保存）；④`complete_requisition` 开启库位管理时按仓库原子扣库位库存、`revert_requisition` 对称还原；⑤列表页/打印模板/导出/报表（`_build_requisition_report` 按仓库过滤、`requisition_list` 关键词可搜仓库）全展示层贯通；⑥BOM 下推与 Excel 导入自动带入默认仓。回归：`tests/verify_app_py_split_requisition.py::TestRequisitionWarehouse`（6 场景：显式仓库保存、默认仓带入、无默认仓拒绝、save_table 携带、完成扣库存、反提交还原），`tests/verify_bug_P15_P16_P21.py` 报表守卫种子数据同步带仓库，`pytest tests/ -q` 118 passed，lint 0 违规，存量库迁移冒烟通过 |
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
| BUG-2026-08-04-011 | 采购入库单明细行合同编号/工程名称没有像物料编码那样的关键词快速输入：后端 `/api/contracts` 返回裸对象 `{"contracts":[...]}`，缺少标准信封 `{"status":"success","data":...}`，前端 `WMS.api.getContracts()`（api.js 统一请求层）在 `res.status==='success'` 判断处把该响应当作业务失败 reject，`ContractAutocomplete` 的 `.catch()` 吞掉错误导致下拉永远不渲染；同时 5 个单据页（in_order_add/sales_order_add/sales_order_edit/purchase_order_add/out_order_add）头部分级合同搜索用裸 fetch 并判断 `Array.isArray(list)`，对裸对象也永远为 false 同样失效 | ①后端 `/api/contracts` 改为返回标准信封 `{"status":"success","data":{"contracts":[...]}}`；②5 个单据页头部分级搜索改为从信封提取 contracts（兼容 data/裸对象/裸数组）。回归测试 `tests/verify_bug_2026_08_04_011_contract_api_envelope.py`（4 场景：标准信封、合同编号/工程名称关键词命中、getContracts 读取键与字段齐全、无关键词返回全部）。**验证确认**：5 个单据（in_order_add/purchase_order_add/sales_order_add/sales_order_edit/out_order_add）共用同一套 `WMS.ContractAutocomplete` 组件与同一 `/api/contracts` 信封接口，代码结构完全一致（均为 `line-contract-no`/`line-project-name` 输入框 + 新增行 `bindRow` + 初始化 `bindAll` + 头部信封提取）。浏览器真实键盘输入已在采购入库单（in_order_add）验证成功：合同编号输入 `HD` 弹出匹配合同下拉、工程名称输入 `工程` 弹出同一套下拉、`/api/contracts` 返回 200 信封、无 JS 报错。其余 4 单据因页面承载于 iframe、浏览器自动化工具无法进入 iframe 内部做真实输入，但代码实现与采购入库单完全一致，功能等价。 |

| BUG-2026-08-15-003 | 物料新增/编辑弹窗的规格输入框仅占四列布局的一列，长规格录入与核对困难 | 新增与编辑弹窗中的规格字段改为半行宽，保留 `maxlength=100` 与后端长度校验；回归测试 `tests/verify_app_py_split_material.py::TestMaterialRegister::test_specification_fields_use_wide_layout` |
| BUG-2026-08-15-004 | 采购入库单、领料单反提交回草稿后，详情页缺少明细编辑入口，无法修正数量、单价、合同编号、工程名称等 | 草稿详情增加“编辑明细”；编辑页仅允许 `pending` 状态加载，预填表头与行级字段，采购来源行 ID 保持不丢失。已完成单直接访问编辑 URL 返回 409；完成与反提交库存动作未放开。回归 `tests/verify_app_py_split_in_order.py`、`tests/verify_app_py_split_out_order.py`、`tests/verify_bug_2026_08_04_015_received_quantity_double_count.py` |
| BUG-2026-08-15-005 | 手机端发送采购入库单、领料单或物料标签打印任务时，`WMS.api.post` 缺少 `Content-Type: application/json`，后端 `request.get_json()` 读取空请求体并返回 400；桌面端任务完成/失败回写仅登录即可调用 | `app/static/js/api.js` 为非 FormData 请求自动设置 JSON Content-Type；`print_queue_complete`/`print_queue_fail` 限制为 admin/warehouse；`tests/test_print_queue.py` 覆盖三种任务、JSON 请求契约与非仓库回写拒绝。已推送 `main` |
| P2c | 拆分 `app/app.py`（单文件 2.7 万行） | **用户明确决定暂缓（2026-09-25）**：原话「拆APP.PY不要做，有很大的风险，时间也比较长」。理由：①app.py 承载全部路由与库存核心逻辑，拆分必然大面积改导入路径，一次改动面过大；②生产站 `gd2026.top` 单人在用，停机窗口有限，拆分带来的是重构收益不是功能收益，风险收益比不划算。**替代策略**：继续走「路由外移到 `app/routes/*.py` + 单函数改动」的渐进路线（已落地 `in_order.py`/`out_order.py`/`material.py` 等），每个 atomic action 只碰一个自洽改动，不在一次提交里跨文件改结构。**重启条件**：用户主动提出，或出现明确的编译/导入冲突无法用渐进方式解决 |

## 历史登记区（含已修复/已交付/误报/暂缓/待确认/未修复，状态以「状态」列为准）

> **2026-10-12 重命名说明（F3.4-②）**：本章原名「未修复/待处理」，审计（WMS全面审计报告_2026-10-10 §8）发现名不副实——章内 133 行中 96 行实为已修复/已交付。现重命名为「历史登记区」并补「状态」列（由行内处理记录推导），阅读时以状态列为准，勿再按章节名判断。真未修复项以状态「未修复/待确认」筛取。


> **F4.4（2026-10-13） 拆分**：本章 2 条已迁移至 `docs/ledger/bugs/history-*.md`。
>
> - [`history-2026-07.md`](docs/ledger/bugs/history-2026-07.md)（表格 1 条 + 小节 0 个）
> - [`history-2026-08.md`](docs/ledger/bugs/history-2026-08.md)（表格 0 条 + 小节 1 个）

## 每日使用方式

```powershell
# ⚠️ 开工前置门禁：三个工作流全绿才能开始任何任务（AGENTS.md §三）
.\scripts\python.cmd scripts\check_ci_green.py
.\scripts\python.cmd scripts\verify_wms_bugs.py
.\scripts\python.cmd scripts\scan_wms_risks.py
```

规则：
- `check_ci_green.py` 是**开工前置条件**：检查 `Android APK Build` / `WMS AI Verification` / `WMS CI` 三个工作流在 `main` 上最近一次运行是否全绿。**任一非绿即不得开工**，必须先修绿。退出码 0=全绿放行，1=阻断，2=检查本身失败（同样阻断）。
- `verify_wms_bugs.py` 失败才需要立即处理；`scan_wms_risks.py` 输出的是候选风险，必须人工判真后才能进入 BUG 修复。

三个工作流均已配置**每日定时触发**（`cron: '30 18 * * *'` = 北京时间 02:30），即使当天无人推代码也会自动跑一遍，以便发现依赖撤回 / 上游镜像失效这类**时间性故障**。


> **F4.4（2026-10-13） 拆分**：门禁段内历史 BUG 详情小节与文件尾部 BUG 详情小节已按月迁移至
> `docs/ledger/bugs/entries-*.md`。新增 BUG 详情写入当月分片（A13：必须含「生效确认」字段）。
>
> - [`entries-2026-09.md`](docs/ledger/bugs/entries-2026-09.md)（29 个小节）
> - [`entries-2026-10.md`](docs/ledger/bugs/entries-2026-10.md)（16 个小节）

