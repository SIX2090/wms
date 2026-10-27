# BUG 基线 · 详情归档 2026-10

> 本分片由 `WMS_BUG_BASELINE.md BUG 详情小节（开工前置门禁段及文件尾部）` 拆出（F4.4（2026-10-13））。
> 新增 BUG 详情小节请写入当月分片，且必须含「生效确认」字段（A13）。

---

### BUG-2026-10-01-001（2026-10-01，CI Android unit-test job 无超时上限，新增 Robolectric 测试疑似挂起烧 runner 70+ 分钟）

- **发现方式**：M2' 替代 2 推送 4 个 Robolectric 测试（`1ca3e9d`~`bf8e600`）后，`Android APK Build` **#760** 的 unit-test job 在「Unit tests (BUG-2026-08-16-021)」步骤上静默卡死 70+ 分钟（历史绿构建全程仅 ~5 分钟；Gradle 缓存命中 8s 排除依赖下载；步骤计时实证卡在测试执行期）。GitHub Actions 默认 job 超时 **360 分钟**，不干预会烧满 6 小时 runner——已手动取消 #760 止损。
- **根因（分层）**：①工作流 unit-test job 无 `timeout-minutes`——挂起类故障不会失败、不会上传 JUnit 报告（`if: failure()` 不含 cancelled 路径），诊断链路整体缺失（工程缺陷，本条修复）；②测试真实挂起点**未定位**——静态排查已排除：MockWebServer 链路（OkHttp 30s 读超时必失败）、DataStore 草稿链路（runBlocking 事件循环自泵）、Main 派发器死锁（无测试 setMain、viewModelScope immediate 内联执行后仅挂起不阻塞测试线程）、依赖缓存（命中）。定位依赖下一轮 CI 的 25 分钟超时击杀 + 报告上传（已完成用例清单中**缺失的那个测试**即卡点）。
- **修复（工程防御）**：unit-test job 增加 `timeout-minutes: 25`（历史绿构建 ~5 分钟的 5 倍余量，只拦真挂死不误伤慢构建）；报告上传条件 `if: failure()` → `if: failure() || cancelled()`（超时击杀的步骤结论是 cancelled，挂起故障的 JUnit 报告恰好只在此路径产生）。
- **回归**：无需新增——本条为 CI 基础设施防御，`tests/verify_bug_2026_09_14_033_android_unit_test_infra.py` 已有的 `testReleaseUnitTest` 存在性护栏不受影响（该命令未动）。
- **根因（已定位，#762 探针实证）**：`by preferencesDataStore` 委托是 JVM 级单例，跨 Robolectric 沙箱（每 @Test 方法一个环境）复用——EditDraftPersistenceTest 方法 3 的 `restoreEditDraft` 草稿收集协程在旧沙箱销毁后仍向同一 DataStore actor 排入写请求，actor 链被毒化后**方法 4 的 `saveLoginInfo`（dataStore.edit）永久挂起**（DBG7 后 DBG8 永未打印；同一时刻独立工厂实例的探针 edit 正常返回，挂死前 2ms）。
- **根因修复**：`DataStoreTestReset`（test sources）反射清空 `WmsRepositoryKt.dataStore$delegate` 的 INSTANCE 缓存，每个测试方法取绑定当前沙箱 filesDir 的新实例（`528015c`）；androidx 内部字段双名兜底（INSTANCE/dataStore），失败大声打印不静默。
- **生效确认**：**已确认（2026-10-01）**——推送 `528015c` 后 `Android APK Build #763` success（**4 分钟正常速度跑完，74/74 passed**，含 25 项新增 Robolectric 用例；对照 #760/#761/#762 三轮挂死 25 分钟超时）、`WMS CI #1329` / `WMS AI Verification #1624` 全绿。诊断仪表（testLogging STARTED/标准流）为永久保留的基础设施改进。
- **关联**：M2' 阶段（APK 字节码验证 + Robolectric 补强）、`tests/` 新增 4 文件 25 用例、BUG-2026-09-22-001（报告上传机制的上一轮迭代）、产品侧同类隐患（草稿/提交路径 dataStore.edit 无超时，见 M2' 记录段末尾，待立项）。

### BUG-2026-10-002（2026-10-01，Android DataStore 访问无超时：actor 死亡时关键交互路径永久挂起）

- **发现方式**：BUG-2026-10-001 的 #762 探针实证——`preferencesDataStore` 委托是 JVM 级单例，DataStore actor 链毒化后 `dataStore.edit` 永久挂起；同刻独立工厂实例正常返回。测试侧已修复跨 Robolectric 沙箱复用问题，但生产侧 11 个 DataStore 读写仍无超时，挂起型故障不会进入任何 catch/Result 分支。
- **危害**：极端磁盘/文件系统异常导致 actor 死亡时，P0 入出库提交前安全落盘会让提交按钮永久转圈且 `draftMutex` 排队；P1 登录、草稿恢复、冷启动会话还原会挂起；P2 盘点草稿保存/清理与登出可能静默卡死。请求尚未发出，因此不产生重复单据，属于可用性故障而非数据一致性故障。
- **R6 同类点排查**：全仓 Android 生产源码仅 `WmsRepository` 持有唯一 `wms_settings` DataStore 委托；`getSavedBaseUrl` / `saveStocktakeDraft` / `loadStocktakeDraft` / `editDraftKey` / `saveEditDraft` / `loadEditDraft` / `clearStocktakeDraft` / `saveLoginInfo` / `logout` / `getUsername` / `getRole` 共 11 个消费点全部收口，无遗漏。
- **修复**：`WmsRepository` 新增 5s 默认超时（测试可注入 0ms）：`saveEditDraft` 超时继续抛异常，复用 `persistEditDraft` 的 `draftSaveError` / `prepareDraftSubmission` 的「未安全保存，暂不提交」与 loading 复位分支；其余读写按既有安全语义降级（null / Unit / 登录内存态继续 / 登出继续清内存 token）。超时先捕获 `TimeoutCancellationException`，再透传普通 `CancellationException`，避免把页面退出取消误报为 DataStore 故障。版本 3.9.3(27)→3.9.4(28)。
- **回归**：新增 Robolectric/JVM 测试 `DataStoreTimeoutTest` 共 6 用例：①超时后 `saveEditDraft` 抛非取消型异常；②`editDraftKey` 超时降级并抛出「请先登录再恢复清单」；③默认超时下正常 DataStore 往返不受影响；④提交前读键超时时，`prepareDraftSubmission` 复用「登录账号或服务器已变更」分支并复位 `isLoading`；⑤写草稿超时时，`persistEditDraft` 返回 false 并置 `draftSaveError`；⑥外层协程取消仍透传，不误吞为超时降级。
- **生效条件**：Android 代码随 APK 发布生效；需重新构建安装 versionCode 28。生产 WMS 服务端无改动、无需重启 Web 服务。
- **生效确认**：已确认（2026-10-01，确认人：AI；核对方式：远端 main `093042362ffdf792fe118e2b38e8ecee1bd90c3c` 上三工作流全绿——`Android APK Build` #36793317426、`WMS CI` #36793317478、`WMS AI Verification` #36793317436，均 success；本地无 Android SDK，以 CI 编译与 Robolectric 结果为准）。

### M2' Android 替代验证记录（2026-10-01，无真机环境，AGENTS.md R8 诚实边界）

**背景**：P0 三项中 Android 真机测试不可行（沙箱无真机/无 Java/无 Android SDK），按 M2' 计划以两条替代路径收窄不确定性。**BUG-2026-09-13-018/019/020/021/023 台账状态保持「待真机验收」不变**——替代验证只收窄不确定性，不构成真机验收。

**替代 1：CI Release APK 字节码级验证（已通过）**——Android APK Build #758 产物 `wms-mobile-scan.apk`（25,397,359 字节与 Release 元数据一致，排除 BUG-2026-09-25 截断前科）：①ZIP CRC 全表校验通过；②versionCode=27/versionName=3.9.3 与 build.gradle 一致（**BUG-2026-09-14-027 版本冻结陷阱已排除**，现场覆盖安装可正常替换）；③DEX 字符串表 18/18 硬判据全命中——BUG-018（新行/累计/移除/复核 5 条文案）、BUG-019（/api/outbound/preflight 注解值）、BUG-020（草稿键前缀+4 条文案）、BUG-021（库位上限+同库位校验 2 条文案）、BUG-023（4 条降级日志串）。类描述符未命中系 R8 混淆预期内，口径以字符串常量为准。验证脚本：工作区 `m2_apk/verify_apk_markers.py`（不入库）。**结论：产物已确认含全部修复代码，剩余仅运行时行为待真机。**

**替代 2：Robolectric 补强（CI 实证 74/74 passed）**——新增 4 测试文件 25 用例（文件 6→10，用例 49→74）：`ScanFeedbackTest`（BUG-018，9 项：新行「已加入」/合并「已累计（本次+N）」反馈、移除按编码+库位定位与数量快照复核、盘点替换不翻倍）、`EditDraftPersistenceTest`（BUG-020，7 项：草稿键三重隔离、非法作业类型拒绝、DataStore 落盘往返、删空即删除、脏行剔除、普通草稿恢复可编辑、中断提交恢复幂等键且禁改原清单）、`OutboundPreflightTest`（BUG-019，3 项，MockWebServer 挂真实 Retrofit：预检→提交两连击幂等键透传、业务拒绝不入离线队列、幂等回放跳过预检）、`LocationSelectionTest`（BUG-021，6 项：表头库位落行、空白裁剪、超长拒绝不改写、清空同步清行、草稿模式新行盖库位、关闭写 null）。

**过程故障与修复**：①首推 #759 编译错（字符串模板 `$name` 引用不存在变量，全仓排查修 3 处，`4437ed8`）；②#760/#761/#762 unit-test 挂起（详见 BUG-2026-10-001，根因 DataStore 委托单例跨 Robolectric 沙箱毒化，`528015c` 修复）；③最终 `Android APK Build #763` **4 分钟全绿，74/74 passed**（含 25 项新增），CI #1329 / AI Verification #1624 同绿。

**新发现的产品侧隐患（登记待评估，本阶段不修）**：BUG-2026-10-001 的测试侧根因揭示生产路径存在同类风险——`ScanViewModel.persistEditDraft`（草稿自动保存收集器）与 `prepareDraftSubmission`（提交前落盘幂等键）都直接 `dataStore.edit`：若 DataStore actor 因写失败死亡（如磁盘满/文件损坏风暴），**提交路径的 edit 会永久挂起 = 提交按钮无限转圈**。生产环境为单进程单环境，触发概率低于测试沙箱场景，但后果严重，建议后续单独立项评估（加超时/降级）。

## BUG-2026-10-03-001：AI 治理合并后 verify 断言仍引用旧文案（verify.yml + WMS CI 双红灯）

- **日期**：2026-10-03
- **发现方式**：AA1 推送后 `verify.yml` 立即红灯；修复后暴露 `WMS CI` 第二处红灯（行号引用）
- **根因**：R6 同根因复发——修改了被多处断言引用的页面文案/代码行数，推送前未全库排查引用点：
  1. `base.html` 菜单文案「补货建议（规则）」改为「补货建议（安全库存）」后，`scripts/verify_ai_stage7_replenishment.py` 与 `tests/verify_ai_naming_truthfulness.py` 两处断言仍匹配旧文案 → `verify.yml` #1647 红灯
  2. `app.py` 新增 4 行（ai_llm_active 注入 + max_tokens 默认值注释）后，`tests/test_inventory_truth_line_refs.py` 中 app.py 回填行号引用偏移 +4（超出 ±2 行窗口）→ `WMS CI` #1353 红灯（verify.yml 修好后才暴露）
- **修复**：推送 `3d6a611`（同步两处断言 + 「智能补货分析」→「补货建议（周转分析）」消除 T8 违规）+ `a59166f`（补登行号引用 28123→28127 + INVENTORY_TRUTH.md 同步）
- **教训**：改任何页面文案/在 app.py 插入行之前，必须先 `grep` 全库（含 scripts/、tests/、docs/）排查引用点；verify.yml 修绿后必须等 WMS CI 也出结果才能判定 CI 绿——两个工作流是独立工作流，一个绿不代表全绿（AA1 的教训）。同时工作区根 `scripts/check_ci_green.py` 门口的存在就是为了拦截此类事件，必须无条件先跑。
- **生效确认**：已确认（2026-10-03）——推送 `3d6a611`/`a59166f` 后三工作流全绿：`WMS AI Verification` #1648/#1649 success、`WMS CI` #1354 success、`Android Build` success @a59166f

## BUG-2026-10-04-001：ScanViewModel 两参构造后 NavGraph 无工厂反射创建，入出库/库存/盘点页一打开即闪退

- **日期**：2026-10-04
- **发现方式**：真机（HUAWEI LIO-AN00，SDK 31，v3.9.4）用户回传崩溃堆栈：`RuntimeException: Cannot create an instance of class ...scan.ScanViewModel`，`Caused by: NoSuchMethodException: ScanViewModel.<init> [class android.app.Application]`，发生于 Compose 导航创建 ViewModel 时（doFrame 渲染链路）。
- **根因**：BUG-2026-10-002（`7537b3d`，DataStore 超时）给 `ScanViewModel` 构造函数新增第二参数 `dataStoreTimeoutMs: Long = WmsRepository.DATASTORE_TIMEOUT_MS`。**Kotlin 默认参数不生成 `(Application)` 单参构造方法**；NavGraph 5 处 `viewModel(key=...)` 均为无工厂创建，走 `AndroidViewModelFactory` 反射查找 `<init>(Application)` 必然抛 `NoSuchMethodException`。当时只改了单测里的手写构造（`DataStoreTimeoutTest` 等直接 new），**漏改 NavGraph 全部反射创建点**；且项目全部 Python"Android 测试"是源码字符串断言、单测又绕过了框架创建路径，无任何环节能暴露该签名失配，带病上线。
- **R6 同根因排查**：与 BUG-2026-09-14-029（构造期急切解析 api）/032（组合根饿汉创建）根因不同；已全量 grep 主源码 `ScanViewModel = viewModel(` 创建点共 5 处（inbound/outbound/stock_query/stocktake×2），全部补齐 factory；其余 ViewModel 均为单参构造不受影响。
- **修复**：`ScanViewModel` 新增 `companion object { val Factory = viewModelFactory { initializer { ... } } }`（CreationExtras 取 `APPLICATION_KEY`）；NavGraph 5 处创建点改传 `factory = ScanViewModel.Factory`。新增回归锁 `tests/verify_bug_2026_10_04_001_scan_viewmodel_factory.py`（工厂声明 + 创建点必须传 factory + 台账登记三断言）。
- **教训**：改 ViewModel 构造签名时，必须同时排查**框架反射创建点**（NavGraph/`viewModel()`/`by viewModels()`），单测手写 new 不代表运行时路径安全；凡构造参数多于 `AndroidViewModelFactory` 能注入的签名，必须同步提供 Factory 并让全部创建点引用它。
- **生效确认**：待确认——本机无 Android SDK/Kotlin 工具链，无法本地编译验证（R8-5）；须等 `Android APK Build` 转绿 + 真机安装新 APK 打开入/出库页验证不再闪退后回填。

## BUG-2026-10-04-002：首页「今日概览」标题行被裁切 + 语音 FAB 压住底部导航「我的」入口

- **日期**：2026-10-04
- **发现方式**：真机截图实证（HUAWEI LIO-AN00）——「今日概览/项目仓」标题行下半截被概览卡片裁切；右下角语音麦克风悬浮球压住底部导航最右「我的」（角色）入口。
- **根因（两处，均布局层）**：
  1. 标题行放在 `offset(y = (-28).dp)` 的半悬浮 Column 里，设计假定行高 ≤28dp；`WarehouseSelector` 切换器（~32dp 高）使行高超出预留，标题白字下半截落到 Hero 深蓝区之外的白底上——白字白底不可见，视觉上被卡片"切掉一半"。
  2. `VoiceAssistantOverlay` 叠加在 NavHost 之上、对底栏无感知，FAB 用 `padding(20.dp)` 从屏幕底缘算起，正好盖住 `WmsBottomBar`（M3 NavigationBar，80dp）最右 tab。
- **修复**：
  1. `HomeScreen.kt`：标题行（含三态：成功=文字+切换器 / 加载=shimmer / 失败=文字+切换器）收进 Hero 蓝底内，行高任意都恒在蓝底上；概览卡片保留 `offset(-28)` 半悬浮不变（Hero 底部 48dp 预留不动）；`DashboardOverviewError`/`DashboardOverviewSkeleton` 移除各自重复的标题行。
  2. `VoiceAssistant.kt`：FAB modifier 改为 `.navigationBarsPadding().padding(end = 20.dp, bottom = 88.dp)`——先抬过系统手势区再抬过应用底栏（与同文件 SnackbarHost `bottom = 88.dp` 同一口径）。
- **回归锁**：`tests/verify_bug_2026_10_04_002_home_header_fab_position.py`（标题行不在 offset Column 内、标题在 Hero 区内且白字、卡片悬浮保留、FAB 抬升口径、台账登记五断言）。
- **生效确认**：待确认——本机无 Android SDK（R8-5），须等 `Android APK Build` 转绿 + 真机安装新 APK 核对首页标题完整可读、FAB 不再遮挡「我的」后回填。

## BUG-2026-10-04-003：Hero 蓝底上「项目仓」切换器深色文字不可读（002 修复引入的对比度回退）

- **日期**：2026-10-04
- **发现方式**：真机截图实证——BUG-2026-10-04-002 修复生效（标题完整、FAB 不挡「我的」）后，「项目仓」切换器在 Hero 深蓝底上呈深色、几乎不可读。
- **根因**：`WarehouseSelector` 从报表页（浅底）提取为共享组件（BUG-2026-09-10-010）时未考虑深底场景，无前景色参数，`TextButton` 默认主题色（primary）+ 箭头 `onSurfaceVariant` 均为深色；002 把切换器收进 Hero 蓝底后深色压蓝底对比度不足。**002 修复时未同步评估组件颜色语义**——改动布局归属必须连带检查被移动组件的主题假设。
- **修复**：`WarehouseSelector` 新增 `contentColor: Color? = null` 参数（默认 null=主题色，报表页等浅底调用方行为不变）；`HomeScreen` Hero 调用点显式传 `contentColor = Color.White` 并加半透明白底 chip（`White.copy(alpha = 0.15f)` + 圆角 16dp，与 Hero 右上角退出按钮同一套控件语言）。
- **R6 同类点排查**：共享组件全部调用点已 grep——报表页（浅底，不传参保持主题色）、`test_mobile_stock_ledger_page.py` 引用的页面均已核对，无其他深底场景。
- **回归锁**：`tests/verify_bug_2026_10_04_003_hero_selector_contrast.py`（参数存在、Hero 传白、报表页不受影响、台账登记四断言）。
- **生效确认**：待确认——本机无 Android SDK（R8-5），须等 `Android APK Build` 转绿 + 真机核对「项目仓」白字清晰可读后回填。

## BUG-2026-10-05-001：出库单（含领料单）「编辑单据」保存恒失败，永弹「请选择出库日期」

- **日期**：2026-10-05
- **发现方式**：真实浏览器（Playwright + Chromium）复现用户报障链路——「领料单反提交修改仓库后无法保存一直提示修改出库日期」。完成→反提交→编辑单据→改仓库为「成品仓」→点「保存」：**无任何 POST 请求发出**、弹窗不关闭、吐司固定为「请选择出库日期」。数据库 `out_order.warehouse` 保持原值不变。
- **根因**：`app/templates/out_order_detail.html` 的 `saveHeader()` 用
  `Array.prototype.forEach.call(new FormData(form).entries(), cb)` 收集表单。
  `FormData.prototype.entries()` 返回的是 **Iterator**，不是 Array，也不是 Array-like
  ——**没有 `length` 属性**。`Array.prototype.forEach` 对非数组对象按 `length` 索引遍历，
  `length` 为 `undefined`（转数字为 0），于是**循环 0 次**，`data` 恒为 `{}`，
  `data.date` 恒 `undefined`，**必然**命中 `if (!data.date)` 分支弹出「请选择出库日期」并 `return`。
  **文案误导**：报错说「请选择出库日期」，实际与日期无关——该弹窗的**任何**字段都保存不了，
  改仓库只是最容易触发和观察的操作，导致用户误判为日期问题。
  **为什么此前测试没抓到**：`Array.from(...)` / `for...of` / `Object.fromEntries(...)` 都支持迭代器协议，
  用它们做验证会永远"通过"；只有浏览器里真实 click 走 `Array.prototype.forEach.call` 才会暴露。
- **修复**：`saveHeader()` 改为 `var data = Object.fromEntries(new FormData(form).entries());`
  —— 与同功能的 `in_order_detail.html:1301` 对齐（入库单一直是正确写法，两份实现此前分叉）。
  已补注释说明 `entries()` 是 Iterator、禁止用 `Array.prototype.*.call` 遍历。
- **R6 同类点排查**：全仓 grep `Array.prototype.*.call(<...>.entries()`——
  `app/templates/`（含 `in_order_detail.html`、`report_view.html`、
  `ai_data_retention.html`）与 `app/static/js/` 全部核对：**仅 `out_order_detail.html:1475` 一处**该错误写法。
  其余同类取值均为 `Object.fromEntries(formData.entries())`（L126/L1301）或
  `for (const [k,v] of formData.entries())`（L386/L433），写法正确。
  另核对 `Array.prototype.forEach.call(listEl.querySelectorAll(...))`（`mobile_scan.html:1214`）
  —— `NodeList` 有 `length`，是合法用法，不属于本根因。
- **回归锁**：`tests/test_bug_2026_10_05_001_out_order_edit_header_formdata.py`（7 断言：
  出库单无迭代器误用、出库单用迭代器安全取值、出库单与入库单写法统一、
  **入库单对照组不得被改坏**、全模板 R6 扫描、static/js R6 扫描、台账登记五字段）。
  A14 反向验证已执行：回退修复代码后 5 项报红（3 项出库单断言 + R6 模板扫描 + 台账断言），
  对照组 2 项（入库单正确性、static/js 无残留）保持绿，证明锁定有效且无假阳性。
- **生效确认**：修复后用同一浏览器脚本（Playwright + Chromium 真实点击）**从零跑完整用户链路**，全绿：
  ① 新建领料单 OU26100002（材料仓，物料 M001×5）→ `POST /out_order/add -> 200`；
  ② 完成领料 → 触发同料异常提醒 → 确认后 `POST /out_order/2/complete?force=true -> 200` → `status=completed`；
  ③ **反提交** → `POST /out_order/2/revert -> 200` → `status=pending`；
  ④ **编辑单据 → 改仓库 材料仓→成品仓 → 保存** → `POST /out_order/2/update -> 200`，
  payload `{"date":"2026-10-05","department_id":"1","picker":"张三","warehouse_id":"2",...}`，
  响应 `{"status":"success","msg":"保存成功"}`，弹窗正常关闭（`modal fade`，无 `show`），
  数据库 `out_order.warehouse` 由「材料仓」**真实变为「成品仓」**。
  对照修复前基线（同一脚本）：第 ④ 步**零请求**发出、吐司恒为「请选择出库日期」、弹窗不关、仓库不变。
  门禁：`scripts/lint_wms_rules.py` 0 违规、`scripts/lint_no_raw_post_fetch.py` 通过、
  新回归锁 7 passed、相邻模块回归 95 passed/2 skipped/0 failed。
- **推送与 CI**：已 push `main`（`863f72e..3a8a4a1`）。三大门禁全绿 ✅：
  `WMS CI`（[run 37263835479](https://github.com/SIX2090/wms/actions/runs/37263835479)）、
  `WMS AI Verification`（[run 37263835375](https://github.com/SIX2090/wms/actions/runs/37263835375)）、
  `WMS Perf Baseline`（[run 37263835411](https://github.com/SIX2090/wms/actions/runs/37263835411)）。
  提交内 12 项 check-runs（smoke / lint-and-static / static-checks / unit-tests-shard-0~2 /
  verify-shard-0~3 / perf / ai-core）**全部 success**。
- **生效确认**：⚠️ Linux 沙箱已实测通过（详见上一条），但**Windows 实机（用户环境）待复核**：
  请用户在实机重走「领料单→反提交→编辑单据→改仓库→保存」，确认弹窗关闭且仓库已改，然后回填本字段。
- **全面性复核（用户追问"其他单据是否也修了"后补做，2026-10-05）**：
  **代码层全仓扫描**：`grep '\.entries()'` 命中的业务代码仅 5 处 ——
  `in_order_detail.html:1301`（`Object.fromEntries`，正确）、
  `ai_data_retention.html:126`（`Object.fromEntries`，正确）、
  `report_view.html:386/433`（`for...of` 解构，正确）、
  `out_order_detail.html:1477`（本次修复处）。
  `Array.prototype.*.call` 命中 3 处真实业务代码：本处（Iterator，**BUG 已修**）、
  `mobile_scan.html:1214` 与 `base.html:2282`（目标均为 `querySelectorAll` 的 **NodeList，有 length**，合法）。
  `new FormData` 直接喂 `fetch(body:)` 的 `adjustment.html:276` / `transfer.html:362` 不迭代，安全。
  `subcontract_detail.html:1075` 的 `saveHeaderEdit` 用 `getElementById().value` 逐个取值，不经过 FormData，不受影响。
- **全面性复核——真实浏览器逐类型实测**：`out_order_detail.html` 是**四种出库单共用的同一模板**
  （第 153/565 行按 `business_type` 分支渲染），故一处修复覆盖全部。实测 5 张单据全部 PASS：
  | 单据 | 业务类型 | 实测操作 | 结果 |
  |---|---|---|---|
  | id=1 | 领料单 | 改仓库 成品仓→仓库A | ✅ `POST /out_order/1/update -> 200`，落库 |
  | id=2 | 领料单 | 改仓库 成品仓→仓库B | ✅ `POST /out_order/2/update -> 200`，落库 |
  | id=3 | 其他出库 | 改仓库 材料仓→仓库A | ✅ `POST /out_order/3/update -> 200`，落库 |
  | id=4 | 销售出库 | 改备注（该类型按设计无仓库字段） | ✅ `POST /out_order/4/update -> 200`，备注落库 |
  | id=5 | 采购退货出库 | 改仓库 材料仓→仓库A | ✅ `POST /out_order/5/update -> 200`，落库 |
  5 张单据均：吐司无「请选择出库日期」、弹窗正常关闭（`modal fade`）、DB 值真实变更。
- **回归锁扩容（2026-10-05）**：`tests/test_bug_2026_10_05_001_out_order_edit_header_formdata.py` 由 7 断言扩至 **9 断言**，
  新增 ①`NodeList` 白名单钉死（防止日后把 `querySelectorAll` 偷换成 `FormData.entries()` 仍留白名单）、
  ②全仓 `new FormData(...).entries()` 消费方式必须迭代器安全。
  A14 反向验证复跑：BUG 版本下 **5 项报红**（含新增的全仓扫描），对照组 4 项保持绿。

## BUG-2026-10-05-002：iframe 嵌入页重复渲染右下角浮动按钮，出现「两个打印告警铃铛」重叠

- **日期**：2026-10-05
- **发现方式**：用户真机截图报障——右下角出现**两个打印告警铃铛叠在一起**（各带红色角标「8」），
  点击任意一个都跳 `/print_alerts`。用户追问「点击都是打印告警，二个在一起你觉得没有问题？」。
- **真实浏览器复现**（Playwright + Chromium 1440x900，`scripts` 之外的临时脚本）：
  - 外层主页面：`.print-alert-bell` → x=1364, y=756；
  - 内嵌 iframe 页（`/?embedded=1`）：`.print-alert-bell` → x=1349, y=741。
  两者坐标仅差约 15px，同为 48×48 fixed 圆按钮 → **严重重叠**，视觉上就是"两个铃铛"。
  修复后同一脚本复测：全视口可见铃铛 = **1**（仅 outer）。
- **根因**：`app/templates/base.html` 的 `body.embedded-page` CSS 隐藏规则覆盖了
  `.sidebar`、`.app-wrapper`、`.main-content`、`.tab-workspace`，
  **唯独遗漏了右下角悬浮按钮**（`.print-alert-bell` / `.ai-assistant-button` / `.ai-assistant-panel`）。
  而 iframe 内页面（`?embedded=1`，见 `base.html:2382` body class、`app.js:150-158`
  `isWmsEmbeddedPage()`）同样是完整的 base.html 渲染，于是**又渲染了一整套 fixed 定位的浮动按钮**，
  与外层 `right/bottom` 完全相同 → 完全重叠。
  **为什么两个铃铛都是"打印告警"**：它们是同一个模板块在内外两层各渲染一次，角标同源
  （`print_alert_unread_count`），故数字一样、跳转目标一样。
  对比反证：`.sidebar` / `.tab-workspace` 都做了 `body.embedded-page` 隐藏，唯独浮动按钮漏了。
- **修复**：在 `base.html` 的 `body.embedded-page` 规则组内，紧随 `.tab-workspace` 之后补齐：
  ```css
  body.embedded-page .print-alert-bell,
  body.embedded-page .ai-assistant-button,
  body.embedded-page .ai-assistant-panel {
      display: none !important;
  }
  ```
  **设计口径**：右下角浮动按钮（打印告警铃铛 / AI 助手）由**外层主页面统一提供**；
  嵌入页只负责内容区。与既有 `insertGlobalActionBar()`（`app.js:3183`）
  「嵌入场景由 iframe 内部注入内容工具栏、外层负责全局」的分工一致。
- **R6 同类点排查**：`base.html` 中所有 `body.embedded-page` 隐藏规则逐条核对——
  `.sidebar` / `.app-wrapper` / `.main-content` / `.tab-workspace` 已覆盖，
  本次补齐浮动按钮三件套。全仓 `.print-alert-bell` 模板标签**仍为 1 处**
  （`base.html:2876`），确认不是模板重复渲染，而是 CSS 遗漏导致的 iframe 叠加。
- **回归锁**：`tests/test_bug_2026_10_05_002_embedded_duplicate_fab.py`（6 断言：
  嵌入页隐藏铃铛、嵌入页隐藏 AI 按钮+面板、隐藏规则与既有规则同组且紧随其后、
  外层仍渲染铃铛恰好 1 处、非嵌入页不得隐藏铃铛、台账登记含「生效确认」五字段）。
  另有真实浏览器验证 `scripts/verify_bug_2026_10_05_002_embedded_duplicate_fab_browser.py`
  （独立可执行，无 Playwright / 服务不可达时以退出码 2 跳过）。
  **为何置于 `scripts/`**：Playwright 需额外下载浏览器二进制，CI 无图形环境不适合安装；
  且 `tests/test_bug_2026_09_23_001_test_deps_pinned.py` 要求 `tests/` 下所有三方
  import 必须钉入 `app/requirements-test.txt`——本脚本属"本地手动验证工具"，
  与既有 `scripts/verify_ai_browser_e2e.py` 同类。首次提交时误置于 `tests/`，
  导致 CI `unit-tests-shard-1` 的依赖钉版规则报红（已修正，避免往 CI 依赖塞 Playwright）。
  A14 反向验证已执行：回退 CSS 修复后，嵌入页隐藏类 4 项断言报红，
  「外层仍渲染铃铛」「非嵌入页不隐藏」2 项保持绿，证明锁定有效且无假阳性。
- **生效确认**：✅ Linux 沙箱已用 Playwright + Chromium 真实浏览器实测通过：
  修复前「首页可见外层 + iframe 两个铃铛、坐标差 15px 重叠」；
  修复后「首页可见铃铛 = 1（outer x=1364 y=756）、打开 `/out_order?embedded=1` 内容页
  仍为 1 个、AI 按钮 = 1 个、铃铛 href=/print_alerts」。
  ⚠️ **Windows 实机（用户环境）待复核**：请在实机刷新页面确认右下角只剩一个打印告警铃铛，
  然后回填本字段。
- **推送与 CI**：已 push `main`（`f732df0..88cff24`，3 个 atomic commit）。
  三大门禁全绿 ✅：本提交 12 项 check-runs（smoke / lint-and-static / static-checks /
  unit-tests-shard-0~2 / verify-shard-0~3 / perf / ai-core）**全部 success**。
  注：首个提交曾因浏览器脚本误置 `tests/` 触发依赖钉版规则使 `unit-tests-shard-1` 报红，
  经 `88cff24` 移出 `scripts/` 后复跑全绿。


---

## BUG-2026-10-05-003：AI 库存工具 Stock 模型导入错误（4 接口 500）

- **现象**：`/api/ai/v2/tools/inventory/health`、`/api/ai/v2/tools/inventory/material`、`/api/ai/v2/tools/inventory/low-stock`、`/api/ai/v2/tools/inventory/value` 登录后全部返回 500，错误信息为 `ImportError: cannot import name 'Stock' from 'app'`。
- **根因**：`app/ai/tools/inventory.py` 中 4 处延迟导入引用了不存在的 `Stock` 模型（全项目无 `class Stock` 定义，仅 `StockTransaction` 存在于 `models/inventory.py:48`）。系统实际用 `Material.stock` 字段表达全局库存，`Stock` 为历史遗留死代码。
- **修复**（v2，2026-10-05 二次修复以满足 A11 门禁）：4 处 `from app import db, Material, Stock` 改为 `from app import db, Material`；`material_query` / `inventory_health` / `low_stock_report` 3 处改 `get_all_warehouses_stock_quantities()` 全仓汇总口径（Σ②库位账，A11 合规，附带消除每物料一次查询的 N+1）；`stock_value_analysis` 为纯展示聚合（乘价格求和、无比较校验语境），保留 `material.stock` 并按 INVENTORY_TRUTH.md §5 加 `# stock-truth:reason=` 豁免注释。v1 曾改 4 处 `qty = m.stock or 0`，审计发现其中 3 处后续做 `qty <= min_stock` 比较属校验语境、违反 A11，故升级为 v2。
- **验证**：A11 lint `--full-a11` 0 违规；沙箱内存库实测 4 函数正常（A 仓入库 20 件、阈值 5：quantity=20、low_stock_report 空、health 无低库存/负库存、价值 200）。
- **R6 同类点排查**：全仓 grep `from app import.*Stock[^T]` 确认无其他残留；`StockTransaction` 引用均合法。
- **回归锁**：`tests/test_bug_2026_10_05_003_ai_inventory_stock_import.py`（T1 四工具可调用无 ImportError、结构正确；T2 仓库级口径断言：quantity=20 / low_stock 不误报 / 价值走总账 200）——实测 2/2 PASSED。
- **生效确认**：✅ Linux 沙箱实测通过：A11 lint 0 违规 + 回归测试 2/2 PASSED + 08-16 系列 43 项存量回归全绿。
- **推送与 CI**：待 push（atomic action：`fix(ai): BUG-2026-10-05-003 修复 Stock 模型导入错误`）。

## BUG-2026-10-05-004：仓库级库存告警对"非本仓业务物料"误报
- **现象**（生产实测，4 仓环境）：铜排仓专放铜排并设安全库存；在告警页选择"项目仓库"时铜排亮红色低库存告警。两个触发路径：① 物料从未进过所选仓库（库位账/流水均无记录），`warehouse_quantities.get(material.id, 0)` 按 0 参与判定；② 物料曾误录入该仓后又删除/反提交（库位行数量归 0 不删行、正负流水相抵净额 0），仍按 0 判定。
- **根因**：`inventory_alert.py` 按仓判定（BUG-2026-09-18-004 引入，方向正确）但缺失"该物料是否本仓业务"的范围判断——把"没进过这个仓"与"进过但用光/录错冲回"一律按 0 与全局阈值比较。阈值（min_stock/reorder_point）挂在物料主档、无仓库维度，见 AGENTS.md R2 多仓边界。
- **修复**：`/alert` 仓库视图增加"本仓业务物料"范围判定（`_warehouse_scoped_material_ids`）——仅当物料满足以下判据之一时参与该仓告警：a. 有库位库存行（含数量 0 的历史行；兼容 warehouse_id IS NULL 且 location==仓库名/编码的旧行，同 `get_warehouse_stock_quantities` 口径）；b. 该仓净流水（入-出）> 0（`StockTransaction` 按 warehouse_id 聚合）；c. **（v2）该仓存在正常出库流水（transaction_type='out'）**。三者皆无（从未进仓/误录已冲回净额 0）则不纳入该仓告警列表。手机端 `/api/mobile/alert/list` 同口径。全局视图（全部仓库）行为不变。
- **v2 漏报回归（审计发现并修复）**：v1 判据（a+b）在关库位管理 + 真用光场景（入 20、正常出库 20 → 净流水 0、无库位行）把"真缺货"判成"非本仓业务"而静默漏报；经 E2E 真实路径复现（POST /out_order/<id>/complete）+ git worktree 父提交对照（修复前同场景会告警）确认为 004 引入的回归。修复：补判据 c——真用光（有 out 正常出库流水）与误录冲回（仅 in + delete_in_item）账面同为净 0，唯一区分信号是有无 out 流水。
- **验证**：新增回归测试 6 场景实测全绿——S1 从未进仓不告警 / S2 真缺货（3<5）照常告警 / S3 误录冲回净 0 不告警 / S4 全局视图行为不变 / S5 真用光（净 0 + out 流水）照常告警 / S6 手机端同口径（S5 告警、S3 不告警）。防破坏回归：告警/AI 工具/08-16 系列 + 手机端 08-12-004 共 90 项 PASSED（1 skipped 属既有）。A11 lint 0 违规。
- **回归锁**：`tests/test_bug_2026_10_05_004_alert_warehouse_scope.py`（6 用例）+ 存量 `test_bug_2026_08_12_004_mobile_warehouse_scope.py`。
- **生效确认**：✅ Linux 沙箱实测通过：6/6 新场景（v2 含 S5 漏报回归锁）+ 90 项存量回归全绿；A11 0 违规。
- **推送与 CI**：待 push（atomic action：`fix(alert): BUG-2026-10-05-004 v2 补漏报判据——真用光（out 流水）照常告警`）。

## BUG-2026-10-06-001：手机端首页 dashboard 告警计数与告警列表口径不一致
- **现象**（生产实测，手机端截图）：项目仓首页"库存告警"计数显示 20，点进告警列表却是空——从未进过项目仓的铜排等 20 种专仓物料被首页计数误计。
- **根因**：`/api/mobile/dashboard` 的 `alert_count` 与 `/api/mobile/alert/list` 是两条代码路径。BUG-2026-10-05-004 只修了列表的"本仓业务物料"范围过滤（判据内联在 alert_list 里），dashboard 的 `alert_count` 从未套该过滤，仍按老口径（所有候选物料 × 全局阈值，`quantities.get(m.id, 0)`→0<min_stock 即计数）统计——两条路径口径不一致。
- **修复**：把 alert_list 内联判据提取为模块级函数 `_mobile_alert_warehouse_scoped_ids(warehouse)`（判据 a 库位行 / b 净流水>0 / c out 流水，与 PC `inventory_alert._warehouse_scoped_material_ids` 同口径）；dashboard 单仓分支与全部仓库分支（逐仓）均套该过滤；alert_list 改为调用同一函数，消除重复逻辑。修后首页计数与列表同源同口径。
- **验证**：新增回归测试 4 场景实测全绿——D1 专仓物料不计入他仓计数（修复前 1 → 修后 0）/ D2 同场景列表为空（口径一致）/ D3 真缺货（3<5）计入且列表含该物料（不引入漏报）/ D4 全部仓库模式逐仓过滤（铜排属铜排仓业务计 1，项目仓视角 0）。防破坏回归：dashboard/alert/08-12-004/09-10-010/10-05 系列共 113 项 PASSED（4 skipped 属既有）。A11 lint `--full-a11` 0 违规。
- **回归锁**：`tests/test_bug_2026_10_06_001_dashboard_alert_count_scope.py`（4 用例）+ 存量 `test_bug_2026_09_10_010_dashboard_warehouse_scope.py`（9 用例全绿）。
- **生效确认**：✅ Linux 沙箱实测通过：4/4 新场景 + 113 项存量回归全绿；A11 0 违规。
- **推送与 CI**：待 push（atomic action：`fix(mobile): BUG-2026-10-06-001 dashboard 告警计数与列表同口径`）。
- **教训**：修一类口径问题时要排查所有同语义入口——004 修复时只改了告警列表，漏掉了首页计数这第二条代码路径，用户从手机端首页一眼看出不一致。

## BUG-2026-10-06-002：AI 库存工具漏报 danger 档 + value 接口 500（MaterialCategory 当 dict key）
- **现象**（深度检测模块5 手机端 API 全接口扫描发现）：
  1. `/api/ai/v2/tools/inventory/value` 500，traceback `TypeError: keys must be str, int, float, bool or None, not MaterialCategory`——`stock_value_analysis()` 用 ORM relationship 对象 `m.category` 当 dict key；
  2. 三个 AI 库存工具（material_query / inventory_health / low_stock_report）只判 `qty <= min_stock`（low 档），漏 `qty <= reorder_point/safety_stock` 的 **danger 档**——min_stock=5/reorder_point=10/库存 8 时 AI 报 normal，而 PC dashboard、手机端 alert/list 均报 danger，五入口口径不一致（AI-CI-GREEN-005-F04/F05 两级告警要求的调用方缺口）。
- **根因**：`app/ai/tools/inventory.py` 各工具自行实现告警判定且只覆盖一级阈值；`_alert_status_for()`（app.py:7413）是全系统唯一实现（low+danger+normal+disabled），AI 工具未复用。另 material_query 返回恒空的 `m.warehouse_name` 幽灵字段、`filter_by(category=...)` 传中文名过滤无效（category 是 relationship，须 join MaterialCategory.name）。
- **修复**（+49/-14）：新增共用判定 `_ai_inventory_alert_status(material, qty, use_switch=False)`——口径对齐 `_alert_status_for`（low：qty≤min_stock；danger：qty≤safety_stock=max(reorder_point,min_stock)；开关关闭且 use_switch 时 disabled；阈值未配置 disabled；qty<0 时 material_query 另报 negative）。use_switch 语义分流：material_query 的 alert_status 是纯展示字段（历史行为不受开关影响，保 test_bug_2026_10_05_003 存量行为）→ False；inventory_health / low_stock_report 驱动统计（与 dashboard 同语义）→ True。三工具统计条件统一 `alert_status in ('low','danger')`；low_stock_report 新增 alert_status 字段、shortage 统一按 safety_stock 口径；value 接口 `m.category.name if m.category else '未分类'` + join 过滤 + import MaterialCategory；material_query 删幽灵字段改 `'category': m.category.name if m.category else ''`。
- **验证**：8 场景回归测试全绿——A1/A2 danger 档三工具均报（health count=1 含 danger）/ A3 low 档（qty≤min）/ A4 开关关闭统计口径 disabled（health count=0、low-stock 空）/ A5 material_query 展示口径不受开关影响（仍 danger）/ A6 与 `_alert_status_for` 等价性（low/danger/normal/disabled 四态全对齐）/ A7 value 接口分类汇总 200 无 TypeError / A8 shortage 按 safety_stock（4 库存→6 非 1，与手机端 gap 同口径）。修复后五入口一致：AI low-stock=[M001 danger]、AI health count=1、AI material danger、mobile alert/list danger total=1、dashboard count=1。存量防破坏：test_bug_2026_10_05_003 10/10、test_bug_2026_10_06_001 全绿。
- **回归锁**：`tests/test_bug_2026_10_06_002_ai_tools_alert_status.py`（8 用例）。
- **测试踩坑（勿删注释）**：① set_system_setting 不自动 commit，退出 app_context 事务回滚 → 必须双 commit；② Material(unit="个") 触发 backref 炸 `'str' object has no _sa_instance_state'`，须 unit_id + 预建 Unit；③ 跨 context 存 ORM 对象 DetachedInstanceError，存 id；④ Flask 外层 app_ctx 存活时 test_client/test_request_context 复用同一 g，login_user 写的 g._login_user 泄漏污染后续请求（测试脚本须 seed 后退出 ctx 再操作 client）。
- **推送与 CI**：待 push（atomic action：`fix(ai): BUG-2026-10-06-002 AI 库存工具补 danger 档 + value 接口 MaterialCategory 500`）。
- **生效确认**：历史条目补登；原修复已合并（见 2026-10-06 CI 修复补记），生产生效以当时部署为准，本轮未重新复核。

## BUG-2026-10-06-003：AI v1 低库存报告与 v2 工具口径分叉（总账列 + max_stock 补货算法）
- **现象**（深度检测遗留问题复核，用户拍板立即修复）：AI 对话关键词入口（"补货建议/低库存报告"/intent=analysis_low_stock，app.py:10064 `_ai_analysis_low_stock_report()`）与 v2 工具 `/api/ai/v2/tools/inventory/low-stock` 同数据不同结果：① v1 读 `Material.stock` 总账列且无 stock-truth 豁免（A11 违规：低库存判定属校验语境）；② v1 建议补货量按 `max_stock - stock` 计算，v2 按 safety_stock 口径，同一物料两入口给出不同补货数字；③ v1 排序只按 min_stock 差值，无两级告警概念。
- **根因**：v1 是 BUG-2026-10-05-003/10-06-002 两轮修复都漏掉的平行入口——同类口径问题的"同语义入口全量排查"没覆盖到 app.py 内嵌的 v1 版本（教训同 10-06-001：dashboard 只有一条代码路径却漏改）。
- **修复**（app.py `_ai_analysis_low_stock_report()` 重写）：直接转调 v2 工具 `low_stock_report()` 渲染 markdown（R6 防口径分叉：单一实现源）——全仓汇总口径（Σ②库位账）、两级告警（low/danger 列）、补货量按 safety_stock 口径，开关关闭保持"未启用"提示。表头新增"预警级别"列。
- **验证**：3 场景回归测试全绿——B1 v1/v2 同数据同结果（danger 档 M001 两边都报、库存数一致、M002 normal 两边都不报）/ B2 开关关闭不报 / B3 **两仓脏数据场景**（总账 stock=999 但 B仓流水仅 5 → 全仓汇总 5≤min_stock 应报 low；旧实现读总账列会误判 normal 漏报——本用例在修复前确实红）。存量防破坏：10-05-003/004 + 10-06-001/002 共 20 项全绿。
- **回归锁**：`tests/test_bug_2026_10_06_003_v1_low_stock_report_scope.py`（3 用例）。
- **推送与 CI**：待 push（atomic action：`fix(ai): BUG-2026-10-06-003 v1 低库存报告转调 v2 工具统一口径`）。
- **生效确认**：历史条目补登；9cd1710 后 CI 于 5013764 全绿（见下方补记），生产生效以当时部署为准。

---
## 2026-10-06 CI 修复补记（晚间）

BUG-2026-10-06-003 修复（9cd1710）引发 CI 连锁红，三个根因全部修复并验证：

1. **行号锚定漂移（shard-0）**：app.py 净增 9 行导致 INVENTORY_TRUTH 10 处函数
   行号全部过期 → 同步更新 tests/test_inventory_truth_line_refs.py REFS +
   INVENTORY_TRUTH.md（a8f11b0）。教训：改 app.py 后必须核对行号锚定测试。
2. **测试路径不可移植（shard-1）**：003 回归测试硬编码沙箱绝对路径
   /Coze/Drive/... → 改 Path(__file__).parents[1]/app 相对定位（5013764）。
3. **依赖 CVE（lint-and-static）**：Werkzeug 3.1.6 披露 CVE-2026-102598 →
   钉包升级 3.1.9（5013764）。werkzeug 3.1.9 + flask 3.1.3 定向回归
   43 passed + login/auth 存量 41 passed。

终态：5013764 的 WMS CI 9/9 job 全绿（含 3 unit-tests-shard + 4 verify-shard
+ lint-and-static + smoke）。至此深度检测全部 BUG 修复完毕，CI 全绿。

## BUG-2026-10-07-004：视觉模型纯 JSON 回复被丢弃，误报「没有返回具体错误」

- **日期**：2026-10-07
- **现象**：AI 助手上传票据图 +「提取产品名称 产品型号」，模型成功识别并按 OCR prompt 返回纯 JSON（无文字说明、无 ```json 包裹），前端却收到「图片已收到，但当前大模型没有成功返回图片分析结果。没有返回具体错误。」
- **根因**：`_ai_call_llm_vision` 的解析链只认「文字回复」：`_ai_vision_parse_extracted` 对裸 JSON（无代码块包裹）返回 reply=整个 JSON 文本或 extracted=None；doc vision 链 normalize 失败（document_type=other 等）后回落到 vision 链，reply 为空时主链路直接判失败，提取结果全部丢弃。
- **修复**（app/app.py 三处）：
  1. `_ai_call_llm_vision`：`_ai_vision_parse_extracted` 解析不出 extracted 时，补裸 JSON 兜底 `_ai_extract_json_object(content)`；reply 与 extracted 双空时才报「没有可用内容」。
  2. 主链路：`vision_reply` 为空但 `extracted` 非空时，用新增的 `_ai_vision_extracted_fallback_reply(extracted)` 生成可读明细兜底回复，继续走建单/确认流程。
  3. 新增 `_ai_vision_extracted_fallback_reply`：渲染单据类型/单号/供应商/明细（编码、名称、规格、数量、单位，上限 20 条）；空提取（无 items 且无单号）返回空串、保持原错误分支。
- **验证**：tests/verify_bug_2026_10_07_004_vision_json_only.py 7 项静态契约全过；关联回归 62 passed（OCR/draft/chat endpoint/wechat share/document confirmation）；lint --staged 0 违规；app.py ast.parse 语法通过。
- **关联**：修复脚本 tools/fix_bug_2026_10_07_004_vision_json_only.py（幂等）。
- **生效确认**：历史条目补登；7 项静态契约与关联回归 62 passed，生产生效以当时部署为准。


### BUG-2026-09-22-001-F01: Robolectric SQLite 配置复发的子修复（2026-10-13）

- 根因：ca432c20 给 ScanFeedbackTest 重复添加类级 SQLiteMode；全局 robolectric.properties 已统一配置 LEGACY，现有零例外守护回归因此失败。
- 危害：WMS CI shard-2 失败，阻断后续录单优化。
- 修复：删除重复注解、导入和过时注释；不改生产业务、不改断言。
- 同类点已排查：既有守护测试扫描全部 Kotlin 测试类；Android 离线队列测试 #823 曾发生 SQLITE_IOERR_SHORT_READ，#824 同测试通过，仍需观察偶发性，不能宣称根治。
- 验证：修复前守护模块 1 failed / 7 passed；修复后守护及相邻模块 17 passed。补跑台账分片、月度统计相邻回归，确保登记不改变历史条目状态。
- 回滚记录：首次修复 991175f6 的新增独立 BUG 条目触发历史状态总数快照断言；已立即以 c7f5ff74 回滚。本条遵循同类历史子修复登记，保留全部既有测试断言。
- 状态：已修复；提交 2a896d3d。
- 生效确认：已确认（2026-10-13，Codex 核对 GitHub）；Android APK Build #826、WMS AI Verification #1841、WMS CI #1546 均 success，均指向 2a896d3d。仅测试配置改动，生产服务无需重启。

### BUG-2026-09-22-004-F01: 入出库物料候选键盘交互补齐（2026-10-13）

- 根因：同类物料关键词选择入口交互未统一；领料出库只支持 Enter 选首项，不能上下键选择；采购入库键盘选择器包含无 data-code 的搜索结果提示行，回车可能选中提示而不选物料；中文输入法确认回车缺少 composition 保护。
- 危害：多候选时依赖鼠标，录单效率低；采购候选提示行使回车无响应，中文确认可能提前选料。
- 修复：两页统一 ↑↓ 移动高亮、Enter 选高亮或首个真实候选、Esc 关闭；候选限 data-code 行，跳过提示；输入法组合输入期间（isComposing / keyCode 229）不触发选料和扫码自动填充；增加可见快捷键提示。选中后的数量焦点沿用原有实现。
- 同类点已排查：采购入库与领料出库的 handleKeydown / setupScanAutoFill；其他入出库复用这两页，自动继承。通用 document_table_form 和 quick-select 是不同入口，未夹带重写，后续单项验证。
- 回归：tests/test_document_material_keyboard.py 用 Node 执行实际模板处理函数，覆盖中文输入、非物料提示行、上下边界、行间隔离、选中与关闭后焦点行为。受影响页面与相邻筛选、台账测试共 33 passed。
- 回退验证：文件备份后恢复 HEAD 两页，新测试 2 failed；恢复改动后 2 passed，未放宽任何断言。仅模拟 DOM 的运行时验证，尚未作为真实浏览器或现场验收证据。
- 状态：代码已修复并推送 main（9dfe4618）；WMS CI #1547 和 WMS AI Verification #1842 均 success，最近 Android APK Build #826 success（本次仅模板与测试改动，未触发 Android 构建）。现场体验待用户验收。
- 生效确认：待用户确认；生产需重启 WMS 服务生效，浏览器 Ctrl+F5 强刷后在采购入库与领料出库输入关键词，验证上下键、回车选料及数量焦点。不涉及库存写入或数据库迁移。

### BUG-2026-09-22-004-F02: 其他单据物料键盘交互统一（2026-10-13）

- 根因：同类物料选择入口缺少统一键盘行为；共用调拨/盘点/BOM/领料表单仅支持精确编码回车，售后出库仅支持 Esc，采购及销售订单缺少中文输入法组合输入保护。
- 修复：新增 WMS.MaterialPicker.handleKeydown 共用组件，仅处理可见下拉内有 data-code 的真实候选，支持 ↑↓ / Enter / Esc、排除提示行、保护 isComposing 与 keyCode 229；共用单据与售后页面复用，选中后聚焦数量或实盘数，售后鼠标选料也聚焦数量。采购申请、采购订单、销售新增/编辑保留已有选料逻辑并补输入法保护。
- 同类点已排查：上述六模板覆盖调拨、盘点、BOM、工单领料、售后、采购与销售订单；前一子项采购入库/领料出库的键盘回归同时验证。不改完成、库存、仓库必填、价格或来源单据业务规则。
- 回归：新增 tests/test_other_document_material_keyboard.py，Node 实际执行六页事件处理器及售后选料函数；模拟 DOM 覆盖中文组合输入、无候选/隐藏下拉、提示排除、上下边界、回车选择与数量焦点。相关页面和相邻业务回归 74 passed；模板六页 Jinja 解析、JS 语法检查、规则 lint 均通过。
- 回退验证：备份六页后恢复 HEAD，新增八用例 7 failed / 1 passed（售后原本未处理 Enter，因此输入法保护用例原本通过）；恢复改动后 8 passed。未删改任何既有断言。
- 全量本机验证：pytest tests/ -q -n 4 --dist loadfile 为 3382 passed / 89 skipped / 6 errors；六错误均来自既有 test_p2_1_drift_gate 的文件库 bootstrap 将 Windows 路径直接嵌入 Python 字符串，触发 unicodeescape 的截断 U 转义。备份恢复旧页面后该模块仍为 15 passed / 6 errors，确认与本改动无关；未改断言或绕过此用例，完整 CI 仍须验证。
- 状态：代码已修复，本地专项验证通过；CI 以本次提交工作流实际结果为准，真实浏览器及现场体验待验收。
- 生效确认：待确认；生产需重启 WMS 服务生效，浏览器 Ctrl+F5 强刷后验证新组件。仅前端交互，不涉及数据库迁移或库存写入。

### BUG-2026-09-23-006-F01: 列表工具栏语义去重及销售选单专用工具栏（2026-10-14）

- 根因：全局工具栏只按同名文本去重，未识别新增采购单、删除已选、字段设置、批量导入等同功能名称；销售出库选单误注入通用单据工具栏并重复生成草稿入口。
- 修复：仅列表页识别明确同功能别名，保留页面原有操作；排除隐藏与表格行按钮；删除全部、批量打印等不同作用范围保留。销售选单禁用全局栏，固定页面操作栏且只保留一个生成入口。
- 同类点已排查：已登录浏览器检查侧边栏64个主要页面；报表中心逐报表预览/导出、销售统计三个不同表的栏目设置、消息逐行已读等不是重复，不删除。
- 验证：修改前相关52模块336 passed / 85 skipped；新增测试用Node执行实际全局栏生成器，覆盖15种新增别名及隐藏/行操作边界。回退源码后16 failed / 2 passed，恢复后专项与相关模块验证见提交测试输出。
- 状态：已修复；推送与CI以实际提交结果为准。
- 生效确认：待确认；生产需重启 WMS 服务生效；重启后核对嵌入列表及销售出库选单，不进行业务提交或删除。

### BUG-2026-09-23-006-F02: 补齐非主菜单列表的新增别名（2026-10-14）

- 根因：F01 的主要菜单走查未包括售后列表、调整列表等返回入口，新增售后出库单/其他出库/采购退货出库/工单领料单/BOM清单/合同名称未完全覆盖。
- 修复：补齐六个精确别名；沿用可见性及行按钮排除，不扩大成前缀匹配。
- 同类点已排查：全模板搜索新增操作并核对业务菜单、售后表单返回列表链接，已排除模态框隐藏入口与无同功能页面按钮的场景。
- 验证：扩展用例修复前6 failed / 18 passed，修复后专项及既有工具栏、台账回归全过；既有18项不改断言，新用例执行实际生成器。
- 状态：已修复；推送与CI以实际提交结果为准。
- 生效确认：待确认；仅静态JS，重启计算新缓存版本后生效；无需数据库迁移。F01生产已重启，浏览器采购列表确认新增与删除各仅一个入口。

### BUG-2026-09-07-007-F01: 通用报表筛选状态与操作体验子修复（2026-10-14）

- 关联能力：已完成的report_view.html筛选控件接入，继续修复前端与实际查询条件的同步，不重复开发后端报表。
- 根因：flatpickr与form.reset原始日期状态不一致；打开页面没有恢复URL条件；并发请求无顺序保护。原浏览器入库日期筛选7条，重置日期显示为空仍7条；库存带仓库2/物料/隐藏零参数打开却显示默认仓库与全量。
- 修复：显式清日期并保留当前仓库；恢复和同步查询URL且排除csrf_token；请求序号阻止旧响应覆盖；快捷日期、条件摘要、范围校验与准确收起标签；模板打印收进菜单，销售不同汇总表的栏目设置明确所属对象。
- 同类点已排查：共用模板覆盖全部14类报表；其他服务端GET列表的25关键词查询逐页验证，打印/导出继续使用统一buildParams，库存台账仓库/物料必填与既有全量打印逻辑保留。
- 验证：tests/test_report_filter_interaction.py Node实际函数执行4 passed；回退旧模板4 failed；真实浏览器14报表无匹配物料均0条、组合条件命中1条/状态切换0条、清空日期恢复1571条、仓库2清空仍保留2；完整相关测试结果见本次提交输出及审计报告。
- 状态：已修复；main提交推送及CI结果以实际输出为准。
- 生效确认：2026-10-14 Codex实机重启后浏览器验证上述条件与显示一致；生产需重启 WMS 服务生效，正式提交后再次核对服务SHA；用户现场体验待验收。无数据库迁移或库存写入。
- 审计报告：docs/audit/UI_TOOLBAR_FILTER_AUDIT_20261014.md。

### BUG-2026-09-23-005-F01: 单据上下文工具栏的保存与设置语义修复（2026-10-14）

- 根因：列表已隐藏通用保存，但只读详情仍显示仅CSS置灰、原生disabled=false的保存；新建页的通用删除没有已保存记录；详情新增与再建一张重复；打印模板设置与字段设置名称混淆。
- 修复：只读页面不显示通用保存；已有可见保存/保存草稿或字段设置时使用页面入口；仅新建add路径移除通用记录删除；数字详情有再建一张时移除全局新增；打印模板设置明确标为打印设置。保留编辑表单真正保存、不同范围操作和单据导航，不改业务提交逻辑。
- 同类点已排查：主菜单64页面外补查售后/调整/库存查询/委外子单/进度及调拨/BOM/工单新增，通用单据表单本身已有保存入口；真实已完成入库详情确认非编辑表单且保存仅CSS置灰。
- 验证：实际生成器新增3例修改前与回退后均3 failed / 24 passed；恢复改动后专项与既有去重36 passed；全量相关模块和相邻回归377 passed / 85 skipped；JS语法与规则lint0违规。
- 状态：已修复；推送与CI以实际结果为准。
- 生效确认：待最终重启确认新SHA及浏览器工具栏；生产需重启计算新的静态缓存版本，无数据库迁移。业务状态变更和删除不在本轮授权范围内，未操作。

## 已修复：BOM 编辑一致性专项（2026-10-14）

### BUG-2026-10-14-001: BOM 旧编辑入口保存失效及成本/单位校验缺失

- 根因：bom.html 旧列表内嵌编辑仅调用新增明细接口，已有行修改不保存；物料数据依赖默认100条分页且allMaterials变量在DOMContentLoaded局部作用域。共用表单collectItems用||把0单价替换成物料单价，BOM编辑渲染同样把0成本当空值；新增单号重复时会覆盖既有BOM，旧新增明细不默认物料单位，行操作先提交再重算导致成本失败也已写入。
- 同类点已排查：BOM新增/编辑/旧列表、别名明细新增/删除、共用调拨与工单表格、计算成本、导入导出和领料来源路径。共用表单的同根因0单价与非有限数量一并修复；不改库存数量或聚合规则。
- 修复：列表统一链接完整表格式编辑器，保留筛选/排序/导入/导出/打印/草稿生成入口并提供唯一工具栏；删除已失效的旧编辑实现，选料复用完整物料源与已有键盘组件。保存输入形状经pydantic校验，全部明细在写入前核对物料/单位/有限正数量/非负单价；重复编号拒绝；明细替换及成本重算同事务，失败回退。0单价在收集、选料填充、编辑回读中保持0。
- 验证：原受影响及相邻基线38 passed；tests/test_bom_management_audit.py在内存库验证保存、重复编号、单位、非法值、失败回滚、关键词/状态/导出及角色边界；tests/test_document_zero_price.py Node执行共用实际函数，覆盖BOM/调拨/工单。回退旧四个源码后新增测试12 failed / 8 passed，恢复后受影响+相邻94 passed；新列表确认/失败恢复控制器另3 passed，规则lint0违规，verify_wms_bugs全部通过。
- 浏览器验证：独立18081端口、内存库、独立session cookie、121个测试物料；生产仅只读打开空BOM列表。旧逻辑实测把输入0存成5；重启隔离服务器后回测数量3.00、单价0.00、成本0.00一致，备注为空；第121个物料仍可选，Enter选料后焦点落数量，列表仅一个工具栏。
- 台账测试说明：F4.4仍逐项断言原315/141/19/1状态分布；本次新BUG单独明确断言fixed后从历史比较中剥离，没有放宽/删除历史断言，避免新登记被误当拆分丢失或状态漂移。
- 状态：代码已修复，本地及CI最终验证以实际提交结果为准；领料下推/引用删除/无效导入行另子项检查。
- 生效确认：待最终确认；生产需重启 WMS 服务生效。仅隔离库执行保存/删除回归，不在生产修改BOM或生成业务领料单。

### BUG-2026-10-14-001-F01: BOM 引用保护、领料草稿及导入完整性子修复

- 根因：单删/别名/批删未检查领料单与子BOM引用；下推不校验启用状态、有效明细和有效仓库；导入先创建BOM/物料后校验明细，使无效行残留空记录，重复目标任意取第一份，旧.xls返回原始英文错误。仓库角色编辑页显示可保存，旧表头接口可写入非法状态且不能清空备注。
- 同类点已排查：三个BOM删除入口、表格保存及旧表头/明细接口、导入新建/追加/三列表头兼容、成本计算、工单下推与角色权限；共用单位控件仅BOM编辑显示选择器，其他单据及只读展示保留。
- 修复：引用BOM只能停用；批删先验证全集再原子删除。下推只生成pending草稿，校验启用状态/有效明细/启用仓库及库位开关，仓库缺省按有效默认值，无值拒绝；不扣库存。导入先验证后写入，无有效行整批拒绝，有效/无效混合只写有效行；同产品版本多BOM拒绝含糊更新；重复物料保持原最后行覆盖策略并警告；未涉及子件及0成本保留。仓库人员只读，旧表头状态与备注校验补齐。
- 验证：tests/test_bom_lifecycle_audit.py 31 passed；将三个修改源码备份后回退至5edea2da，新增用例29 failed / 2 passed，恢复后全通过。BOM/共用表单/键盘/领料多仓与库位/台账/库存口径行号相邻回归136 passed；全量棘轮无新增违规。独立18081内存库浏览器将单位改箱、保存回读数量3.00、单价0.00、成本0.00一致。
- 状态：已修复；main推送与CI以实际输出核对。
- 生效确认：隔离库接口和实际浏览器已确认；生产需重启 WMS 服务生效，最终服务SHA及菜单将在推送CI成功后确认。无数据库迁移、生产BOM写入或生产领料提交。
- 审计报告：docs/audit/BOM_MANAGEMENT_AUDIT_20261014.md。

### BUG-2026-10-14-001-F02: 领料工具栏增加按BOM领料入口

- 用户目标：领料单工具栏直接选择BOM生成领料单，复用已验证的BOM下推能力。
- 改动：管理员/生产角色列表工具栏增加唯一“按BOM领料”按钮，嵌入模式将同一按钮移至全局工具栏，直接访问保留页面入口；窗口选择启用BOM、必填有效仓库及按开关必填库位，生成pending草稿后打开编辑页，标准用量可继续修改。
- 同类点已排查：候选池与SQL大数据回退均限定启用BOM，支持产品编码/名称/版本检索；不改变原bom关联选择的历史候选。输入改动清除旧隐藏ID，提交中禁用按钮，失败恢复选择与按钮；通过WMS.api调用现有仓库/明细验证接口，不新增完成、扣库存操作。
- 关联修复：新下推草稿的工单/用途/领料人/备注初始化为空字符串，避免编辑页出现None；原数据不修改。
- 验证：受影响与相邻基线44 passed；新功能最初5 failed / 1 passed，空表头新增例修改前失败；相关及相邻126 passed。实际隔离浏览器工具栏仅一个新按钮，选择TEST-BOM和仓库B生成草稿，回读关联BOM正确、数量3.00、库存100.00未变化。回退三源码并移出新增JS后7 failed / 1 passed，恢复8 passed；无断言放宽。
- 状态：已实现；提交推送、CI及正式重启按实际结果确认。
- 生效确认：隔离库实际页面已验证；生产需重启 WMS 服务生效，最终启动SHA和正式工具栏在CI通过后核对。未在生产生成或完成领料单。

### BUG-2026-09-22-005-F01: 来源行拆分导致销售出库及两种退货超量（2026-10-14）

- 根因：完成校验只比单行，当前单重复来源行没有先汇总；保存及采购退货内联改量同样遗漏同来源兄弟行。
- 同类点已排查：关联 BUG-2026-09-22-006 与 SALES-AUDIT-006，销售出库、销售退货入库、采购退货出库的整单保存、单张/批量完成、采购退货内联更新。按来源行ID合计，保留同物料不同合同分行。
- 修复：三种整单检查统一先聚合当前来源数量；保存刷新实际新明细后调用同口径检查，拒绝时事务回退；采购退货内联修改合计同来源其他行。完成仍在写锁后校验。
- 回归：新增测试原代码6 failed / 3 passed；最终18专项通过，源码回退12 failed / 3 passed，恢复后专项及相邻50通过，多仓/历史空仓13通过，台账10通过，规则lint0违规，BUG验证与隔离库全量冒烟通过；既有完成用例加强为验证提前保存拒绝和原草稿保持，并注入历史非法草稿继续验证原完成拦截，未放宽完成断言。
- 全量基线：本机全量3456 passed / 90 skipped / 23 failed / 22 errors；将业务源码及既有测试恢复旧版后全仓收集并复跑失败模块，仍为相同45个失败/错误节点（23 failed / 22 errors），没有新增失败。部分子进程stdout为None及临时库引导失败属于存量环境问题，不放宽断言、不宣称本机全量全绿。最终以新提交CI实证补充。
- 状态：已修复，推送及CI以实际结果确认。
- 生效确认：隔离内存库验证；生产需重启 WMS 服务生效，2026-10-15经用户授权已重启，启动SHA b32ccb0，进程3312，登录页HTTP 200；隔离库回归及CI已通过，现场业务操作待用户验收。不迁移数据、不修改生产单据。

### BUG-2026-09-22-010-F01: 已完成退货对原单反提交的来源依赖保护（2026-10-14）

- 根因：来源完成状态只在创建采购退货时校验，原单回退未检查已完成退货；销售发货回退可把有效发货降到退货量以下。
- 同类点已排查：销售出库单张反提交、采购入库单张及批量反提交；退货按实际来源明细查询，不依赖表头；销售旧purpose和唯一物料来源解析与原进度同步函数一致。已有两种退货自身反提交保持原有对称流程。
- 修复：写锁后、库存变动前检查来源依赖。销售按来源明细合计本单回退量，剩余发货必须覆盖完成退货，允许其他发货足够时回退；采购来源明细存在完成退货时拒绝并引导先处理退货。拒绝不改库存/状态/流水。
- 验证：模块基线15 passed；新增4 failed / 1 passed；恢复旧两路由后新增4 failed / 1 passed；修复后专项与相邻52 passed，含退货先回退再回退原单、多张销售出库可合法回退及跨仓原有回归。规则lint0违规。
- 状态：已修复；main推送及CI以实际结果确认。
- 生效确认：内存库实际接口已确认；生产需重启 WMS 服务生效，2026-10-15经用户授权已重启，启动SHA b32ccb0，进程3312，登录页HTTP 200；隔离库回归及CI已通过，现场业务操作待用户验收。未处理任何生产退货或原单。

### BUG-2026-10-14-001-F03: BOM及工单领料统一库存计量单位（2026-10-14）

- 根因：前轮只验证替代单位字段保存，未验证单位维度与扣库/单价衔接；没有换算模型却接受2箱按2个扣库。
- 同类点已排查：表格BOM保存、旧明细新增、Excel导入、历史BOM领料下推、成本重算；领料表格保存、旧明细新增/改量、完成及历史空单位。批量新增/导入原本直接使用物料库存单位，无替代单位输入。
- 修复：共用库存单位验证；不同单位明确拒绝并提示未配置换算，不猜系数、不修改生产历史用量。导入在写BOM之前拒绝已有物料的异单位行。历史领料单位为空时带入物料单位；物料库存单位本身是箱时正常领料。历史混合单位成本重算拒绝，避免用个单价乘箱用量。
- 验证：原相关模块59 passed；新锁原代码7 failed / 2 passed；扩展最终锁回退三源码9 failed / 4 passed；修复专项及相邻结果见实际日志，含多仓、合法基本单位箱、空单位兼容、混合单位失败不写流水及不改库存。
- 既有测试变更说明：将原允许BOM异单位保存的测试改为新授权规则（400及明确中文原因），保留物料单位不变断言，并增加原BOM单位/数量不变断言；不是放宽断言或允许不正确库存。
- 状态：已修复；推送及CI以实际结果确认。
- 生效确认：内存库实际接口确认；生产需重启 WMS 服务生效，2026-10-15经用户授权已重启，启动SHA b32ccb0，进程3312，登录页HTTP 200；隔离库回归及CI已通过，现场业务操作待用户验收；现有混合单位BOM/草稿需人工核对，没有自动换算或数据迁移。

- F03 CI闭环说明：首次f09f05e0因库存真相文档行号未同步导致1个文档锁失败，按R8由de4a0b7a完整回滚，基线CI恢复全绿后重新实施；同步两处backfill引用29438→29442，补跑tests/test_inventory_truth_line_refs.py，保留原断言。重新提交的最终结果以新SHA为准。

### BUG-2026-08-16-021-F01: 工单领料、盘点及调整完成复核仓库有效性（2026-10-14）

- 根因：原同根因修复覆盖调拨/售后/普通出库，漏掉工单领料、PC盘点、调整；录单时选择有效仓库不能替代完成时复核，调整和盘点还能接受不存在仓库。
- 同类点已排查：采购/销售出入库、售后、调拨双仓、委外发料/收料已有对应完成有效性检查；本次补领料、盘点、调整三入口，不将不直接记库存的委外主订单完结误作库存消费点。
- 修复：写锁重新读取后检查仓库存在且active；领料仍保留空仓有效默认值和库位必填规则；拒绝不改变状态/库存/流水，不生成盘点调整草稿。支持有效仓库名称或编码，保持多仓隔离。
- 验证：旧相关基线21通过，新锁5 failed / 7 passed；回退三路由后5 failed / 7 passed；恢复后专项及相邻108通过，包括前3项修复、PC/扫码盘点、调整、多仓及库存文档引用；未放宽断言；追加普通/embedded页面及通用工具栏opt-out核验，保留只读导出，最终相邻134项通过。
- 状态：已修复；main推送及CI以实际结果确认。
- 生效确认：隔离内存库接口已确认；生产需重启 WMS 服务生效，2026-10-15经用户授权已重启，启动SHA b32ccb0，进程3312，登录页HTTP 200；隔离库回归及CI已通过，现场业务操作待用户验收；未在生产启停仓库或完成业务单据。

### BUG-2026-09-20-007-F01: P2-1隔离文件库夹具兼容Windows路径与禁止自动改库标志（2026-10-14）

- 根因：同根因历史修复只覆盖期初迁移测试；P2-1夹具仍把Windows路径拼进Python源码，且父进程内存库环境覆盖测试目标；初始化沿用生产迁移门禁，本机flag下不建表。
- 同类点已排查：全仓搜索sqlite路径插值并对照子进程源码、环境传递与CI恒等式夹具；其他列迁移/期初消费点通过环境或参数传URL，本次只修P2-1确证遗漏。
- 修复：URL经子进程环境传递，子进程显式指向自己的临时文件库，建表前断言实际引擎URL；直接按真实模型建表，不调用生产启动初始化，不调整生产flag、不写生产数据库。
- 回归：新单引号/中文路径用例旧源码及回退后均失败；恢复后相关模块46 passed / 1 skipped，保留全部既有恒等式、退出码及豁免断言；最终全量3536 passed / 90 skipped，全部通过（17分16秒）；原有业务断言没有修改。
- 状态：已修复；最终全量、main推送及CI以实际结果确认。
- 生效确认：Windows临时库实测；仅测试夹具与文档，不需要数据库迁移，不修改任何生产账号。

### BUG-2026-09-22-010-F02: 采购退货完成与行级改量复核来源事实（2026-10-14）

- 根因：原同根因修复只限制来源选择/表头保存，来源回到草稿后待提交退货仍可重新完成，历史直造异类型来源行也能完成。
- 同类点已排查：采购退货整单保存、行级改量、单张/批量完成，分别复用行级与整单数量校验；销售退货原有完成量限制在发货回退后阻断超退。未关联来源的既有兼容策略保持。
- 修复：行级与整单采购退货校验同时要求已关联来源仍为已完成的采购入库，最终写锁内再次查询；原单pending或其他入库类型时拒绝，不写库存/流水。
- 验证：上一轮全量3536 passed / 90 skipped；扩展来源状态与类型新锁6项原代码失败，回退app.py后6 failed / 6 passed；恢复后相关/相邻80 passed，库存文档引用全部通过；最终全量与CI见修复记录。
- 状态：已修复；main推送及CI以实际结果确认。
- 生效确认：隔离内存库实际接口确认，2026-10-15经用户授权已重启，启动SHA b32ccb0，进程3312，登录页HTTP 200；隔离库回归及CI已通过，现场业务操作待用户验收；生产需重启 WMS 服务生效。未在生产执行退货或反提交。

### BUG-2026-10-15-001: 出入库工具栏新增与复制行丢失内容（2026-10-15）

- 根因：复制行仅写编码、数量、单价，再用物料默认价强制覆盖；未复制批次、有效期、合同、工程、备注及展示字段。新增/复制直接追加表尾，初始30个空行时操作不在可见位置。
- 危害：实机隔离页单价6.50复制成12.00、备注丢失；无缓存的选单行还丢失名称/规格/单位。
- 同类点已排查：采购/产品/其他入库与其他出库共用的两套表单，工具栏复制、Ctrl+Enter复制共用copyValuesToRow/copyRowAfter；采购退货隐藏来源入库明细同时保留；新增按钮改走已有addRowAfterCurrent，内部初始化仍由addNewRow建立30个输入行。选单与批量修改、刷新、字段隐藏已隔离页点击检查；粘贴另列子项修复。
- 修复：复制完整行字段及来源标识，不重置价格；副本紧跟来源行，聚焦数量；新增优先聚焦现有空行。
- 回归：原相关模块28 passed；新回归旧模板5 failed，修复及相邻33 passed；最终两套表单源码文件备份回退10 failed，恢复后专项及台账20 passed；最终全量3618 passed / 90 skipped（328.84秒），规则lint0违规，既有BUG检查和隔离库冒烟通过。测试含零价格、缓存外物料、批次/有效期/合同/备注及插入位置。月度台账测试仅新增明确ID的状态断言，保留原历史分布断言。
- 状态：已修复并生效；三个业务提交1bb3101f、155ae5fb、907eb10f均已推送main，WMS CI及AI验证success。
- 生效确认：2026-10-15已统一重启，启动SHA 907eb10，进程10908，登录页HTTP 200；“生产需重启 WMS 服务生效”已落实。保留既有离线配置及禁止自动改库策略，未在生产进行单据完成/反提交/删除或密码操作，现场体验待用户验收；浏览器复测边界见审计报告。

### BUG-2026-10-15-001-F02: 粘贴导入与批量修改严格校验录入值（2026-10-15）

- 根因：parseFloat接受数字前缀和负数，零单价按假值替换为默认价；导入仅查初始缓存，缓存外档案误报不存在；失败也清空弹窗。批量修改极小正数先通过大于0判断，再四舍五入成0。
- 同类点已排查：采购/产品/其他入库、其他出库、共享领料/BOM/调拨/盘点、调整单的4个粘贴入口；入出库两套批量修改。盘点保留实盘0合法，其他业务数量须大于0。
- 修复：严格有限非负金额及正数量、最多2位小数；0单价保留、空单价才默认。新增登录保护GET精确编码批量查询，每次最多200编码，不受300初始缓存与模糊搜索截断影响。保留失败行重试；查询失败不写行；取消和重复点击保护；改用非阻塞提示，失败明细显示在弹窗。
- 验证：旧相关基线18 passed；新/相邻104 passed，含库存0盘点、缓存外物料、非法小数、零单价、失败重试、并发点击取消、接口权限/精确匹配/停用过滤/输入上限；旧源码文件回退42 failed / 6 passed，恢复后专项及台账66 passed；最终全量3666 passed / 90 skipped（399.47秒），规则lint0违规、既有BUG检查和隔离库冒烟通过。首次全量数量格式守护失败已改回统一formatQtyTrim；AI记忆LRU单项未复现，相关70项及最终全量均通过，未放宽断言或跳过。
- 状态：已修复并生效；三个业务提交1bb3101f、155ae5fb、907eb10f均已推送main，WMS CI及AI验证success。
- 生效确认：2026-10-15已统一重启，启动SHA 907eb10，进程10908，登录页HTTP 200；“生产需重启 WMS 服务生效”已落实。保留既有离线配置及禁止自动改库策略，未在生产进行单据完成/反提交/删除或密码操作，现场体验待用户验收；浏览器复测边界见审计报告。

### BUG-2026-10-15-001-F03: 采购选单全量搜索后分页及结果顺序保护（2026-10-15）

- 根因：接口先limit再在Python过滤，前150张外的采购单即使关键词精确也查不到；已收齐的pending单还占候选名额。无分页元数据与上限提示，异步旧请求可覆盖新查询。点击单号用字符串拼CSS/JS，特殊字符会破坏选择；缓存外行缺品牌。
- 同类点已排查：接口仅采购入库选单一处消费；采购/产品/其他入库共用模板，选采购单只对采购业务展示。R1原有limit兼容保留，显式候选只展示前150张并提示；关键词搜索在完整可用单据集执行，接口支持后续页。
- 修复：数据库先过滤完整候选和未入库行，再分页，返回total/page/page_size/total_pages；大小写及%_按原字符串匹配；保留供应商/来源单过滤与历史NULL收货量。前端请求顺序保护，明确上限提示；整单勾选使用数据属性事件和逐行编码精确比较；品牌补齐及搜索。
- 验证：原相关模块44 passed；最初新锁9 failed；扩展最终12项含来源、供应商、物料/品牌、翻页、收齐草稿、NULL收货、特殊字符及异步顺序，文件备份回退确实失败。库存真相行号同步29442→29458，不改变断言。最终源码回退12 failed；恢复后专项、相邻及台账66 passed，完整回归3678 passed / 90 skipped（492.84秒），规则lint0违规、既有BUG检查及隔离库冒烟通过；CI以实际推送结果登记。
- 状态：已修复并生效；三个业务提交1bb3101f、155ae5fb、907eb10f均已推送main，WMS CI及AI验证success。
- 生效确认：2026-10-15已统一重启，启动SHA 907eb10，进程10908，登录页HTTP 200；“生产需重启 WMS 服务生效”已落实。保留既有离线配置及禁止自动改库策略，未在生产进行单据完成/反提交/删除或密码操作，现场体验待用户验收；浏览器复测边界见审计报告。

### BUG-2026-09-23-005-F02: 移除未实现的汇总占位入口（2026-10-16）

- 根因：通用单据布局自动生成禁用的汇总页签，栏目设置另有仅显示开发中文字的汇总页；两处都没有实际业务功能，给录单员造成可用功能的误解。
- 任务：UI-DOCUMENT-SUMMARY-001；用户明确同意先隐藏无效入口。
- 同类点已排查：app.js通用单据表格及栏目设置两处移除；保留明细页签和栏目调整、保存、打印、金额合计及真实报表汇总。未增加合并物料或库存计算。
- 验证：原工具栏/栏目设置/键盘/台账基线60 passed，新增实际Node渲染测试3项；修复前及文件备份回退均2 failed / 1 passed，恢复后专项相邻63 passed；隔离浏览器确认采购入库仅1个明细页签、0个汇总页签，栏目设置仍显示明细字段且无汇总页；数量2×单价3正常合计6.00。全量3714 passed / 90 skipped（1116.34秒）；规则lint、既有BUG检查及隔离冒烟121/121通过。
- 状态：已修复；业务提交aaddeff62已推送，业务CI及AI验证、性能检查均success。
- 生效确认：2026-10-16已重启，启动aaddeff6、PID11152、127.0.0.1:8080、登录页HTTP200；生产需重启 WMS 服务生效已落实。

### BUG-2026-09-22-004-F03: 共用单据及售后出库连续录入断点（2026-10-16）

- 根因：历史F01/F02统一了选料键盘行为，但共用BOM/调拨/盘点/领料表单与售后出库未绑定数量及单价回车导航，不能像采购入库、出库和采购订单一样连续录入。
- 修复：复用MaterialPicker增加行级导航；数量回车至可编辑可见单价，无单价时至下一行物料；单价回车至下一行物料，末行才新增空行，焦点内容自动选中。
- 同类点已排查：入库、出库及采购订单已有同方向导航；本次补齐共用模板与售后出库；只读页不绑定，忽略组合输入、已处理事件、修饰键及不可编辑字段，Tab保持原行为，不保存、不完成单据，不改数值、库存及来源。
- 任务：UI-DOCUMENT-ENTRY-001。
- 验证：原受影响键盘及领料连续开单基线58 passed；新增19项测试；最初回退共享JS后15 failed / 2 passed，补充列重排失焦/不抢其他焦点用例；隔离浏览器确认BOM和售后出库普通行导航、零单价保留、末行新增第31行且焦点不丢。最终回退17 failed / 2 passed，恢复后专项相邻161 passed；最终全量3711 passed / 90 skipped（1100.03秒）；普通规则lint0违规、全量棘轮无新增违规、既有BUG检查及最终隔离冒烟121/121通过。
- 状态：已修复并生效；代码442db230已推送main，WMS CI（38873529204）、AI验证（38873529147）及性能检查success。
- 生效确认：2026-10-16已重启，启动442db23，PID8528，登录页HTTP200；生产需重启 WMS 服务生效已落实。保留本地生产模式、CSRF、文件密钥及禁止启动迁移配置，未在生产提交测试单据或操作密码，现场体验待用户刷新验收。

### BUG-2026-10-15-001-F04: 复制上一行按用户口径填入本行（2026-10-16）

- 根因：上一轮将工具栏复制理解为追加副本，与用户2026-10-16明确的“填写到本行”不符。
- 修复：焦点及指针进入明细行时记住本行，点击工具栏后保留目标；复制紧邻上一行的全部字段/原价/来源到本行，不改变行数，定位本行数量。首行、上一行空、未选行或目标已删除时只提示，不猜测目标。
- 同类点已排查：入库与其他出库共用的两套模板均修正；独立行菜单“复制行”不等同工具栏“复制上一行”，保留原插行及全字段回归。
- 测试变更：旧复制测试明确绑定行菜单copyRowAfter，保留原全部字段、价格、来源、插入和焦点断言；新增工具栏当前行14项运行时测试，非放宽断言。相关模块原基线12 passed；旧源码回退14 failed；恢复后专项及相邻92 passed，专项及台账34 passed；全量3692 passed / 90 skipped（345.73秒），规则lint0违规、既有BUG检查及隔离库冒烟通过。
- 状态：已修复并生效；业务提交2330b6ce已推送main，WMS CI、WMS AI Verification和性能检查均success。
- 生效确认：2026-10-16已重启，启动SHA 2330b6c，进程10396，登录页HTTP 200；生产需重启 WMS 服务生效的要求已落实，保留现有离线配置及禁止自动改库策略。未在生产完成/反提交/删除单据或操作密码，现场体验待用户刷新验收。

## 已修复：全仓审计恢复安全（首轮回滚后重新验收）

### BUG-2026-10-16-001: 离线恢复占用与结构校验（A01/A02，首轮已回滚）

- 任务：AUDIT-FULL-20261016-001-F01；原始审计A01/A02，F1.2同根因已查；同类点包含restore_offline.bat、Web恢复入口及启动入口。
- 原问题：空闲连接检测不足，非WMS SQLite可恢复，主库冷拷贝遗漏WAL。
- 首轮：09afc672增加占用/结构/暂存及运行锁；本机全量3731 passed / 90 skipped、隔离冒烟121/121通过，回退11 failed / 6 passed。但Linux CI在两个分片共8项恢复测试失败：/proc中不可读的无关进程FD被误判为目标库占用，正常恢复被拒绝。没有改断言或跳过测试。
- 回滚：依R8完整回退首轮业务代码，恢复原基线，保留本条已登记未修状态及全部失败证据；重新修复须先确认回滚CI全绿，再补Linux不可读FD回归。
- 首轮回滚后状态：未修复；不得把09afc672当成完成交付。
- 生效确认：首轮从未重启到生产；现有PID11152仍为此前版本，不对生产执行恢复、删除或改密码。回滚提交及CI结果待登记。

- 第二轮进展（同一任务）：回滚f585d8a1已推送且CI/AI/性能均success，生产以稳定代码恢复到PID6136、HTTP200。补Linux可见FD辅助扫描：无关进程/匿名FD无权读取不虚构目标占用，仍拒绝可见目标FD及跨用户目标；服务与恢复全程共用运行锁作为WMS互斥依据，Windows生产独占打开检查保持不变。新增Linux行为锁3项，回注旧误判逻辑2 failed / 1 passed；本机专项相邻71 passed；正式串行全量3734 passed / 90 skipped（1074.63秒），普通及全量棘轮规则、既有BUG检查通过；待提交/CI/运行锁启用。未跳过任何既有断言，未进入第二项。

- 当前状态：已修复并生效。第二轮8d74f67c9163979cfe46ddb331d75cab178abbd3已推送main，本地与远程SHA一致；真实Linux CI的三个单元分片、四个verify分片、静态门禁及冒烟均success，AI验证/性能success。正式本机串行全量3734 passed / 90 skipped（1074.63秒），专项相邻71 passed。
- 当前生效确认：2026-10-16 21:21重启，新PID5604，启动8d74f67，127.0.0.1:8080登录HTTP200；仅探测OS运行锁，服务运行时维护锁被拒绝，没有连接或恢复生产数据库。生产需重启 WMS 服务生效已落实。


## 已修复（生产待重启）：全仓审计只读与内存库边界

### BUG-2026-10-16-002: 文件维护回落生产库及只读检查启动应用（A14）

- 任务：AUDIT-FULL-20261016-001-F02。
- 根因：17处维护函数把内存/非SQLite解析结果None回落默认inventory.db；库存检查CLI导入app，触发启动维护。
- 同类点已排查：查阅BUG-2026-08-06-001路径修复历史；本次覆盖全部17处回落，保留显式文件维护与文件模式正常自愈。CLI使用SQLite mode=ro与query_only事务，不启动应用；集成采集仅复用已初始化app并禁自动flush。不改变库存计算、仓库归属或库位开关口径。
- 验证：隔离原基线99 passed / 1 skipped；新增62项通过，旧源码隔离回退57 failed / 5 passed，包含17处三种URI、文件正例、多仓库及历史空仓库、SQL写入授权拦截和输入文件哈希验证；相邻与全量待验。
- 状态：未修复；本地开发中，尚未提交或完成CI。
- 生效确认：待确认；未连接、改写生产数据库，待全部验证和CI通过后重启确认。

- F02本地最终验收：新增62 passed，回退57 failed / 5 passed，专项相邻181 passed / 1 skipped，最终完整串行3796 passed / 90 skipped（1038.52秒）；普通规则0违规、全量棘轮、A11全量与既有BUG检查通过，库存夹具反向及豁免通道通过。首轮因新增注释造成10项行号引用失败，约64%中止；压缩注释保持原行号后84项复核及完整重跑通过，未改断言或权威文档。生产只读1301物料，原/新纯计算同快照一致；库位关闭下2项历史库位差留待A17，不改库存。仍待推送CI与生效确认。

- F02当前状态：代码已修复并推送main，业务提交3c64f4c383f2f927f28a46d858cf28bb1a2ec98d，本地/远程一致。WMS CI 38915997574、AI验证38915998343、性能38915997181全部success；第一项恢复保护的回归也通过。
- F02当前生效确认：CLI已通过生产只读检查；app.py部分生产待重启。自动审批以blocked by policy拒绝停止PID5604并启动新版本，命令未执行，未绕过拦截。核实旧PID5604仍运行、登录HTTP200；已请用户通过原有入口手动重启，后续核对启动SHA。不得把已验证代码等同于新服务已启用。


## 已修复：全仓审计服务身份与重启验证

### BUG-2026-10-16-003: 启停按端口误停及旧HTTP误报重启成功（A03/A08）

- 任务：AUDIT-FULL-20261016-001-F03；F02记录提交217ac3bd CI全绿后开始。
- 根因：restart.py指向不存在的stop_wms.bat，旧服务HTTP200也可被当作新启动成功；停止脚本与两个安装入口按目录子串或端口结束程序，缺少脚本身份/启动时间核对。
- 同类点已排查：查阅BUG-2026-08-23-004端口占用历史；覆盖restart.py、app停止/启动入口、root包装入口及install.bat/install_e_wms.bat。安装入口调用当前包的检查器，不调用目标旧停止脚本。更新脚本A04/A05失败流程另立独立修复，不在本条混入。
- 修复：仅接受完整Python解释器及本安装目录run_server.py命令；监听PID、命令、解释器与启动时间复核，持句柄防PID复用；相对路径旧实例或其他端口/程序拒绝自动处理，提示人工确认。启动必须新建子进程存活、其拥有端口且HTTP200，失败只清理直接子进程；支持WMS_PORT，隐藏新服务窗口并关闭父日志句柄。
- 验证：原基线11 passed；历史verify_infra_fixes的E9备份页排序检查原本失败，未改其断言；专项相邻49 passed（含Windows适配层4项假进程模拟）；回退旧入口8 failed / 22 passed。只读系统查询确认PID5604为相对路径旧实例、严格身份检查拒绝自动停止；未执行真实停止。全量/规则/CI待验。
- 状态：已修复；业务提交369eeea8c0cf0ba8122a37ebb307df02a9808020已推送main且本地/远程一致。
- 生效确认：待确认；仅模拟启停和只读元数据查询，不执行生产停止/启动，F02服务重启仍被自动审批拦截，旧服务保持运行。

- F03最终本地验收（2026-10-17）：新增39 passed，相邻63 passed；最终旧入口回退8 failed / 31 passed，均为行为/入口契约断言失败，无AttributeError，恢复后63 passed。正式串行全量3835 passed / 90 skipped（1048.50秒），普通规则0违规、全量棘轮通过（A9=213/217），既有BUG检查通过。第一轮A9因测试命名未精确关联报219>217，未放宽基线；规范测试命名及私有嵌套helper后重新全量。保留批处理原始CRLF，不混入全文件格式变化。全仓同类停止命令已查，另有nginx停止属不同服务未改；待提交CI，未停止生产进程。

- F03推送前门禁观察：2026-10-17检查发现main定时Android #830（38970169759 @217ac3bd）单测种库时SQLITE_BUSY，build/lint成功。暂停提交，原样重跑失败job一次后全绿；没有修改源码、断言或SQLite模式。与BUG-2026-09-22-001-F01记录的偶发测试库I/O同属待观察项，保留失败日志，不宣称根治。恢复全绿后才继续本项推送。

- F03 CI闭环（2026-10-17）：WMS CI 38984459556、AI验证38984460077、性能38984459548均success。最终全量3835/90，相邻63，回退8 failed / 31 passed。
- F03生效边界：启停/安装脚本在下次调用时读取新文件，不改运行中的业务服务。Windows真实进程元数据只读查询及假进程适配层已验证；未执行真实生产停止。当前PID5604仍为旧相对命令，检查器按设计拒绝自动停止，需人工确认后一次重启，待后续统一安排。F02的生产app.py仍待人工重启，自动审批拒绝状态不变，不以脚本CI替代真实启停验收。


## 已修复（当前普通进程部署）：全仓审计更新失败与服务恢复

### BUG-2026-10-17-001: 一键更新失败停服及启动失败误报成功（A04/A05）

- 任务：AUDIT-FULL-20261016-001-F04；3d8bbc37 CI全绿后开始；原相关基线95 passed。
- 根因：旧批处理先停服务再fetch/pull/pip，失败直接退出；restart.py退出码被cd等后续命令覆盖，末尾仍显示OK并返回0。
- 同类点已排查：参考BUG-2026-10-16-003及2026-10-11重启环境事故；本条只改人工一键更新入口，启动自动更新A15另立任务，不混入业务代码。
- 修复方向：Python控制器先拉取并检查固定SHA可快进、依赖及一致性备份，再核对停止；不修改共享Python依赖，依赖变化或需要安装时保持服务运行并拒绝自动更新。失败用git reset --keep回退代码，保留/拒绝覆盖操作员改动，不恢复业务数据库；核对旧服务恢复结果。本次更新失败即使恢复成功仍返回非零。
- 验证：首批真实临时main仓库+模拟服务19 passed，覆盖预检不停止、合并/新启动失败恢复、恢复失败准确提示、并发更新锁与用户改动保留；Windows实际批处理故障入口测试开发中。未在生产执行更新或停止服务。
- 状态：已修复当前普通进程部署；业务提交b33ceebf19708c21fedca7180b61868b51059125，本地/远程一致，CI验证通过。
- 生效确认：待确认；仅临时Git仓库/临时数据库和假服务，生产旧PID5604继续运行，F02待人工统一重启边界保留。

- F04最终本地验收：新增35项（含Windows真实cmd入口2项；临时Git main/bare origin及独立venv，服务与依赖安装模拟），专项相邻140 passed；旧批处理回退入口3项全部失败，实际证明下载前停服及startup失败exit0，恢复后通过。完整串行3870 passed / 90 skipped（1166.74秒），普通规则0违规、全量棘轮及既有BUG检查通过。依赖变化保守拒绝、环境/解释器路径核对、并发锁、操作者改动保留及回退失败明确提示均覆盖；未修改生产依赖或业务数据库。新操作说明和Git部署入口随仓库发布，NSSM托管协同留在A09专项；待提交CI。

- F04 CI闭环：2026-10-17，WMS CI 38988448736、AI验证38988448698、性能38988448706全部success；本机完整3870 passed / 90 skipped，专项相邻140 passed，旧入口回退3 failed。
- F04生效确认：批处理/控制器下次调用直接读取新文件；Windows实际入口故障注入与临时Git/数据库已验证，不在生产运行更新器或启停。共享依赖变化保守拒绝更新；NSSM托管协同在A09继续，F02的人工统一重启仍待安排，不宣称生产服务已切新版。


## 已修复：全仓审计安装失败保留业务数据

### BUG-2026-10-17-002: 安装回滚删除整个已有目录及快捷方式（A06）

- 任务：AUDIT-FULL-20261016-001-F05；652f8c7b CI全绿后开始，原相关基线76 passed。
- 根因：install.bat/install_e_wms.bat在COPIED_FILES后失败用rd /s /q删除整个INSTALL_DIR，连同旧业务库与备份；桌面WMS.lnk不区分既有/本次创建直接删除；最后错误宣称rolled back。
- 同类点已排查：两份安装脚本共用模式，查阅AI-SEC-F01、F1.2备份及A01/A02恢复保护；本条处理安装数据保留，不增加自动业务库恢复。A09启动/安全配置仍按后续专项。
- 修复方向：失败保留所有目录/快捷方式并准确提示未完整撤销；复制时排除既有数据库/上传/密钥/环境配置；已有库不重新初始化。覆盖前保留config.py快照，数据库通过既有scripts/online_backup.py取一致快照并检查失败，不再冷拷贝活库。
- 状态：已修复；业务提交ab283c6fa52684551b49977261f06b4d0db17e92已推送main，本地/远程一致，CI通过。
- 生效确认：待确认；仅临时目录故障注入，不执行真实安装、删除生产目录、账号密码操作或数据库恢复。


F05本地验收（2026-10-17）：原基线76 passed，新增30项（24项Windows临时目录原生片段）；专项相邻150 passed（21.85秒），原三文件回退25 failed / 5 passed（9.86秒），恢复后通过。完整串行3900 passed / 90 skipped（1164.58秒），普通规则0违规、全量棘轮及既有BUG检查通过。已有库只读校验并跳过初始化，覆盖前一致性备份包含已提交WAL，配置留快照，失败不删除目录/快捷方式或谎报完整回滚；marker写入失败准确非零。既有测试逻辑断言不变，BAT保留CRLF。证据WMS_INSTALL_VALIDATION_20261017.json；不执行生产安装、账号初始化、COM快捷方式或共享依赖安装。A09继续真实初始化配置与NSSM协同；待提交CI。

- F05 CI闭环：2026-10-17，WMS CI38993307366、AI38993307353、性能38993307362全部success；完整3900/90，相邻150，旧代码回退25 failed / 5 passed。生效确认：脚本下次调用读取新版；未执行生产安装/账号初始化/COM快捷方式，A09安全配置继续专项，F02人工统一重启仍待安排。


## 已修复：全仓审计便携包输出与私密文件保护

### BUG-2026-10-17-003: 打包任意递归删除输出及复制本地私密文件（A07）

- 任务：AUDIT-FULL-20261016-001-F06；625ea0d0三工作流全绿后开始。
- 根因：DistDir解析后直接Remove-Item -Recurse，未限制与源/业务目录重叠；robocopy全工作树，仅少量排除，上传、环境/密钥及本地未知文件可进发布物。
- 同类点已排查：历史F3.5仅排除bak；本次与A06目录保留保护同根因，tools内递归删除仅此打包入口，root BAT委托同一入口。
- 修复方向：输出限定仓库dist下全新直接子目录，不做删除；拒绝链接/reparse和已有目录；只读Git HEAD导出已提交app/tools并排除数据库/上传/备份/日志/环境/密钥，拒绝已跟踪程序脏改。
- 状态：已修复；业务提交71ff441a9cfd43ab41a44f7303978546b85b6ccd已推送main，本地/远程一致，CI通过。
- 生效确认：待确认；仅OS临时目录夹具，不执行生产打包/删除，也不下载安装依赖。

- F06初验：相邻原基线111 passed（131.55秒）；新增30 passed（28.75秒），含5项Windows实际PowerShell前缀，真实临时Git及目录/私密文件验证。还原旧PS后5项入口全部失败（13.83秒），恢复修复；旧代码会错误允许危险目录和复制本地私密文件。不执行下载/依赖/编译/完整运行时打包；全量和CI待验。


F06本地验收（2026-10-17）：原基线111 passed；新增30 passed，专项相邻146 passed（49.53秒）；旧PS入口回退5 failed / 25 deselected（13.83秒），恢复后通过。完整串行3930 passed / 90 skipped（1196.90秒），普通/全量棘轮/暂存规则及既有BUG检查通过。新输出限定dist直接子目录且拒绝任何已有输出/目录链接，只导出HEAD已提交app/tools并过滤业务目录及环境/密钥；不执行生产打包、下载、pip、EXE编译或应用启动。证据WMS_PORTABLE_VALIDATION_20261017.json；待提交CI。

- F06 CI闭环：2026-10-17，业务CI39006756857、AI39006756853、性能39006756838全部success。完整3930/90，相邻146，旧PS回退5 failed。生效确认：下次构建读取新脚本；仅OS临时目录Git/PowerShell前缀，不执行完整生产打包，运行服务及账号不变。


## 代码已修复：物料档案人工选择与判断合并

### BUG-2026-10-17-004: 物料合并要求手输编码且属性差异强制阻断人工判断

- 任务：MATERIAL-MERGE-HUMAN-001；用户2026-10-17截图102059/102120名称差异被拒；不在生产执行此两物料合并。
- 根因：前端window.prompt手输编码，没有选择器；后端以名称/规格/品牌硬判重键作为合并前提。与人工确认同物料的用户口径不符。
- 同类点已排查：全仓material_merge_preview/merge_material_duplicates及material路由/模板；旧建档判重属于另一功能，保留不放宽。查过历史台账，没有独立人工合并选择修复。
- 修复方向：搜索/分页选择保留方，显示方向与差异，人工确认允许属性差异；自合并/未知物料/不安全单位及库存事务保护保留；不自动决定、不自动执行。
- 验证：原合并/判重/库存引用/候选展示基线64 passed（17.56秒）；新增回归和UI验证待执行。
- 状态：已修复（代码）；业务提交771873814c63485c3b2aaa4f83c0d078a7535698已推送main且本地/远程一致，CI通过；生产待人工重启验收。
- 生效确认：待确认；生产服务5604仍旧版本，自动审批重启被拦截，不绕过；只在隔离测试库/页面测试，不改生产物料或密码。

- 人工合并本地初验：新增13项，旧三文件回退10 failed / 3 passed（7.22秒），恢复后专项相邻99 passed（45.04秒）；隔离临时数据库完整冒烟121/121通过，内置浏览器实际选择/搜索/分页/交换方向/重新确认/取消/模拟提交通过、无JS错误。取消0次执行请求，模拟确认仅1次正确方向请求，未连接生产数据库。初次测试导入路径错误已改为tests包导入，非业务失败；既有断言全部保留。生产需重启 WMS 服务生效；生产旧PID5604保持，审批拦截未绕过。完整测试及CI待验。

- 人工合并最终本地验收：完整串行3943 passed / 90 skipped（1202.62秒），普通/全量棘轮/暂存规则0新增违规、既有BUG检查通过；相邻99，冒烟121/121，回退10 failed / 3 passed。原判重及合并测试断言全部保留，手工窗口带manual_review预览，执行必须confirm及人工identity_confirmed，未确认的内部差异调用仍拒绝。预览只读、单位不同不直接累加、库存校验退化提交前回滚。生产需重启 WMS 服务生效；生产未重启或合并，待提交CI。

- 人工合并CI闭环：2026-10-17，WMS CI39009310516、AI39009312364、性能39009310515全部success。完整3943/90，相邻99、隔离冒烟121/121，旧代码回退10 failed / 3 passed。首次git钩子GBK编码报错拒绝提交，UTF8环境重跑后所有钩子正常通过，没有跳过规则。生效确认：待人工重启；生产需重启 WMS 服务生效，旧服务5604继续，原自动审批blocked by policy不绕过；未在生产合并102059/102120或任何其他档案。


## 代码已修复：自动/云服务启动配置与托管维护

### BUG-2026-10-17-005: 自动启动缺Cookie模式、云部署不能可靠传递验证配置（A09）

- 任务：AUDIT-FULL-20261016-001-F07A；原启动/身份/安装基线111 passed（18.67秒）；4e13a0e7三工作流全绿后开始。
- 根因：start_wms_auto设置production却没有明确Secure Cookie/可信HTTP配置；NSSM只注册旧入口且覆盖既有服务/环境，设置与启动失败可能仍显示完成。安装首次初始化同样遗漏可信HTTP配置。
- 同类点已排查：参考BUG-2026-10-11重启环境、BUG-2026-10-16-003身份和BUG-2026-10-17-002安装保护；覆盖auto/deploy/两份install；restart已有显式0/HTTPS保护测试保持，NSSM进程维护边界后续F07B。
- 修复方向：云端默认HTTPS、可信HTTP须明确选择；自动入口纯配置预检后启动，尊重显式禁止值；已有服务/占用端口拒绝部署，校验既有业务库，不自动重置/创建账号；各配置失败非零，不凭其他HTTP200报成功。
- 状态：已修复（代码/CI）；F07A ac18ca29和F07B 47d4c3f0已推送main且CI全部success；无真实生产部署/启停操作。
- 生效确认：待确认；只在临时目录/模拟服务验证，不执行真实部署、服务停止/注册、账号密码或生产数据库操作。

- F07A最终专项：新增37项；最终旧4份BAT回退15 failed / 22 passed（8.70秒），恢复后相邻158 passed（27.23秒），原基线111。Windows原生自动入口/安装片段与编译的标记型SC/NSSM/PowerShell替身覆盖：已有服务保留、查询失败和端口不明拒绝、配置失败非零、嵌套已装运行时免下载；所有服务命令/初始化仅模拟，真实Config校验和临时SQLite只读有效/损坏库保护通过。完整测试/CI待验；F07B托管维护仍未执行，A09整体不报完成。


F07A本地最终验收：完整串行3980 passed / 90 skipped（1205.89秒），相邻158 passed（27.23秒），旧四BAT回退15 failed / 22 passed（8.70秒），新增37项；普通/暂存0违规、全量棘轮无新增违规（A9=213）、既有BUG检查通过。首轮机械识别因测试名后缀将A9记215，规范两项现有测试名后对应14项重跑通过，未改参数/断言或业务源码。A09第一部分等待推送CI；NSSM维护边界F07B未执行，A09整体仍未修完。不执行生产部署、停止/重启、注册服务、初始化账号或密码操作。


F07A首轮失败及回滚（2026-10-17）：业务提交e54fe1f693373ce7a44a92ff18a4982eed18dac0的AI验证39013948082 / job117342056803失败，58个独立脚本中57通过，仅verify_startup_auto_update.py要求start_wms_auto.bat直接启动run_server.py的旧静态断言失败；新启动器链路未被该专项覆盖。本地3980/90与专项158不能替代此CI证据。依R8完整回滚业务代码和新增测试，保留登记及失败证据，不直接改断言放行。生产未部署/注册/重启。修正方向：在恢复全绿后，覆盖新入口配置预检与最终run_server执行链的实际行为，同时保留默认不更新、不得重复更新、无pause及更新失败回退等原有保护；A09/F07B及其他剩余项目暂停开工直到CI全绿。

- F07A回滚验证：业务代码与4e13a0e7基线一致；相邻121 passed（19.68秒），原verify_startup_auto_update在显式testing+内存数据库隔离环境中完整通过（不是截断日志的普通调用），暂存lint0违规。只为执行R8纠正性回滚使用仓库预留WMS_SKIP_CI_GATE=1推送一次，保留其他钩子；不得用于后续修复或新任务。待回滚SHA三工作流恢复全绿后再开工。


F07A第二轮验收中（2026-10-17）：回滚32c8a63b的业务CI39014434853、AI39014434818和性能39014434809均success后重新开工。保留原独立专项和全部旧断言；BAT改为纯配置/只读库预检后直接调用绝对路径run_server.py，只传固定枚举和有效端口。新增40 passed（9.86秒），专项相邻161 passed（47.34秒），OS临时Git副本中原58个AI核心脚本58/58通过。回注原四BAT后16 failed / 24 passed（10.23秒）；回注首轮失败入口后直接启动契约1 failed / 39 deselected（0.99秒），均用备份法恢复。第二轮完整串行正在运行，不引用首轮3980/90代替当前结果；F07B及其他项目尚未开工，无生产部署/停止/注册/账号操作。


F07A第二轮本地最终验收：完整串行3983 passed / 90 skipped（1219.42秒），新增40、专项相邻161、原58个独立AI脚本全部通过；旧四BAT回退16 failed / 24 passed，首轮失败入口回退1 failed。普通/暂存规则0违规、全量棘轮通过（A9=213）、既有BUG检查通过。原脚本/测试断言未修改；纯预检后BAT直接启动绝对路径run_server.py，保留首次CI失败和回滚证据。待业务提交及CI，F07B未执行，A09整体未完成；没有生产部署/重启/注册服务或账号操作。


F07A第二轮CI闭环（2026-10-17）：ac18ca29b401a50bde6ea958af47337cc4f1d74d已推送main且本地/远程SHA一致；WMS CI39016625017、AI39016625002、性能39016625025全部success，原独立启动专项也通过。首次正常推送因查询Android API临时TLS EOF被门禁拒绝，正常重试后全绿成功，未跳过门禁。完整3983/90、新40、相邻161、58独立脚本及两次缺陷回注验证齐备；本阶段代码完成，BUG根项005/A09仍未关闭，F07B待执行。生效确认：仅临时目录/模拟服务，无生产部署、注册、启停、账号初始化；F02人工重启待办保留。


F07B开工：7516370b的CI39016857106、AI39016857108、性能39016857110全绿。沿用BUG-2026-10-17-005；同类点已排查F03停止/重启、F04更新、F05安装停止调用和F07A部署健康。普通维护只识别Python身份，缺少Windows服务父链和已停止NSSM目录绑定约束，子进程可能被监督器拉起。方案为拒绝普通进程工具管理服务绑定目录，停止前复核，指定服务健康须核对监督归属。生效确认：待确认，仅临时/模拟验证，无真实服务操作。

F07B阶段验证：原基线119 passed（137.29秒）；初轮137/2失败为新增辅助文件依赖及旧健康调用契约，改为单文件内嵌与显式健康服务名环境，旧断言均保留，复测141 passed（169.39秒）。补服务绑定/别名测试后179 passed / 1 failed：低可用内存下查询20秒超时，更新器安全拒绝；优化为单次进程快照索引，不放宽超时，当前相邻重测中。没有推送带失败版本，不执行生产服务操作。

F07B最终相邻181 passed（180.07秒）；文件备份法回注control/launcher/updater/deploy原四文件，14项维护/健康/原生假停止/超时关键用例12 failed / 2 passed（5.59秒），恢复修复后新增32 passed（15.21秒）。快照一次读取进程按PID查父链；查询失败保持拒绝，保留20秒上限；查询无关进程的祖先不可确认不全局阻断，仅本目录目标需要人工确认。原断言未删改；独立58脚本在临时副本串行验证中，完整测试和CI待验。


F07B本地最终验收：完整串行4015 passed / 90 skipped（1246.49秒），新增32、专项相邻181、原58独立AI脚本全部通过（低内存主机按1 worker逐脚本隔离执行，190.55秒）；旧四业务文件回注关键14项12 failed / 2 passed，恢复后32项通过。最终暂存0违规、全量棘轮通过（A9=213）、既有BUG检查通过。保留前几轮兼容/查询超时失败历史，保留20秒门禁和所有旧断言；未推送失败版本。根项005/A09等待本次推送CI后闭环，其他剩余项目尚未开工；无生产部署/启停/注册/账号操作。


F07B/A09闭环（2026-10-17）：47d4c3f0bac09f330ed0502b5d2fd867eef805e7已推送main且本地/远程一致；WMS CI39039008996、AI39039009060、性能39039008962全部success。完整4015/90、新32、相邻181、原58脚本及旧代码回注12 failed / 2 passed均齐备；F07A第二轮和F07B合计完成A09代码验收，原18项中10项代码/CI通过、8项待修（A10/A11/A12/A13/A15/A16/A17/A18）。生效确认：入口下次调用读新脚本；仅临时库/假服务/目录连接及系统只读元数据验证，无生产注册/启停/更新/账号操作。F02与人工合并待人工统一重启保留，不将代码验收写成生产已部署。

### BUG-2026-10-17-006: check_ci_green.py 在中文 Windows 控制台（cp936）直接崩溃，§三 门禁命令在默认控制台不可用

- **发现方式**：2026-10-17 起跑检查，在 Windows 默认控制台（stdout 编码 cp936）执行 `python scripts/check_ci_green.py`，脚本以 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705' in position 2` 退出，**一个工作流状态都没打印出来**（rc=1 但输出只有 traceback）；必须手动加 `PYTHONIOENCODING=utf-8` 才能跑通。
- **根因**：脚本把 ✅/❌/⏳/🚫/⚠️ 直接交给 `print`，未考虑 stdout 的编码能力。Windows 生产平台的默认控制台/管道编码是 cp936，emoji 不可编码即抛 `UnicodeEncodeError`；CI 跑在 Linux/UTF-8 上永不触发，属"只在生产平台复现"的盲区。
- **危害**：AGENTS.md §三 把该命令列为**开工前置门禁的推荐检查方式**，在 Windows 上却一次都跑不成功；操作者只能改用人工看板或自行补环境变量，门禁在真实平台等于失效或被绕过（与 BUG-2026-09-23-001 同型：脚本在 CI 绿、在真实消费环境炸）。
- **修复**：`scripts/check_ci_green.py` 新增 `stdout_encoding()` / `can_encode()` / `icons()` / `marks()` / `configure_stdout()`：按 stdout 编码能力自动降级为 ASCII 标记（`[OK]`/`[FAIL]`/`[WAIT]`/`[NONE]`、`[BLOCKED]`/`[WARN]`），并在任何输出前把 stdout 的 `errors` 设为 `replace` 兜底；UTF-8 环境（Linux CI）输出与行为完全不变。
- **回归**：新增 `tests/test_check_ci_green_output_encoding.py` 4 用例——①cp936 放行路径不崩且输出 `[OK]`；②cp936 阻断路径不崩且输出 `[FAIL]`/`[BLOCKED]`；③UTF-8 仍输出 emoji（防止过度降级）；④`can_encode` 对不可编码/未知编码返回 False 不抛异常。用 `TextIOWrapper` 替换 `sys.stdout`、桩掉 `latest_run`，不联网。
- **回退验证**：把 `check_ci_green.py` 换回 HEAD 版本后 **3 failed / 1 passed**——两条 cp936 用例以 `UnicodeEncodeError: 'gbk' codec can't encode character '\u2705' / '\u274c'`（现场原样复现）失败，`can_encode` 契约用例因符号缺失报 `AttributeError`；恢复修复后 **4 passed**，未删改任何既有断言。
- **同类点已排查**：`scripts/` 下其余脚本按 emoji 字形 grep 复核，本脚本是唯一在**门禁必需路径**上直接打印 emoji 的；其余脚本的 emoji 只出现在非门禁用途的说明文案里，不属 §三 强制命令链。
- **状态**：已修复；提交 8bde424，已推送 main（本地/远程 SHA 一致）。
- **生效确认**：**已确认（2026-10-17 23:00）**——①推送 8bde424 后 `WMS CI` #1612 / `WMS AI Verification` #1907 均 success 且指向该提交（`Android APK Build` #830 为该工作流 main 最近一次运行，本次未触发 Android 构建）；②本地在不设 `PYTHONIOENCODING` 的 cp936 控制台复跑 `python scripts/check_ci_green.py`，rc=0、三工作流全绿、状态列输出为 `[OK]`（ASCII 降级生效，无 traceback）。

### BUG-2026-10-17-007: pre-push 钩子把 Store 的 python3 别名当可用解释器，Windows 上所有 push 被误拦

- **发现方式**：2026-10-17 推送 BUG-2026-10-17-006 的提交时，`git push` 被 pre-push 拦下并提示「CI 门禁未通过（main 最近一次运行非全绿）」；但同一时刻手动执行 `python scripts/check_ci_green.py` 返回 rc=0、三工作流全绿。定位到钩子的解释器探测逻辑。
- **根因**：`.githooks/pre-push` 用 `command -v python3` 选解释器，只判断"能不能找到"，不判断"能不能跑"。Windows 默认 PATH 里 `python3.exe` 是 Microsoft Store 的 0 字节执行别名：能找到、执行返回 9009。于是 `! "python3" scripts/check_ci_green.py --quiet` 恒为真，钩子把"解释器坏了"误判成"CI 非绿"，**阻断这台机器上的一切 push**（含纯文档提交）。同仓的 `.githooks/pre-commit` 早在 AI-MOB-APK-001（2026-08-29）就改成"真实执行验证"，pre-push 没同步，属同根因的漏改消费点（R6）。
- **危害**：Windows 生产机上 §三 的"atomic action 必须推送"无法执行；开发者只能被迫用 `WMS_SKIP_CI_GATE=1` 绕过，等于把真正的红绿门禁一起关掉——比没有门禁更危险（绕过会被当成常态）。
- **修复**：探测循环加真实执行校验 `"$cand" -c "import sys"`（与 pre-commit 一致），坏解释器跳过并在 `python3 → python → py` 中继续找；找不到可用解释器时补上"Store 执行别名"排查指引，逃生舱说明保持不变。
- **回归**：`tests/test_f28_pre_push_ci_gate.py` 增 2 条——①静态契约：钩子必须含 `-c "import sys"` 执行校验；②行为验证（POSIX）：PATH 首位放恒失败 9009 的假 `python3`、其后放可用的假 `python`，钩子必须跳过坏的并放行（rc=0、无 PRE-PUSH BLOCKED）。Windows 本地无 MSYS 可执行位，行为用例按 skipif 交给 Linux CI，Windows 由静态契约 + 本机实测覆盖。
- **回退验证**：把 `.githooks/pre-push` 换回 HEAD 版本后静态契约为 **1 failed**（`assert '-c "import sys"' in ...`），恢复修复后 **3 passed / 1 skipped**；未删改任何既有断言。本机实测：同一条 push 在修复前被误拦，修复后钩子正确读到真实门禁状态（当时 CI 正在跑，钩子如实报 `[WAIT]` 并阻断，属预期）。
- **同类点已排查**：`.githooks/` 下仅 pre-commit / pre-push 两个会探测解释器；pre-commit 已有执行校验，pre-push 本次补齐。`scripts/` 下的包装脚本不依赖 `command -v` 判定。
- **状态**：已修复；提交 2cbedd4，已推送 main（本地/远程 SHA 一致）。
- **生效确认**：**已确认（2026-10-17 23:43）**——①推送 2cbedd4 后 `WMS CI` #1614 / `WMS AI Verification` #1909 均 success 且指向该提交（`Android APK Build` #830 为该工作流 main 最近一次运行，本次未触发 Android 构建）；②本机实测：修复前同一条 push 被误拦，修复后钩子如实读到门禁状态（CI 运行期间报 `[WAIT]` 阻断、转绿后放行），push 成功。

## 已修复：备份页面缺少实际自动备份来源

### BUG-2026-10-17-008: 页面只枚举手动目录，实际每日备份不可见（A10）

- 任务：AUDIT-FULL-20261016-001-F08；0f8442b3业务CI39039267314、AI39039267287、性能39039267291全绿后开始；原相关30 passed（5.79秒）。
- 根因：页面/下载/删除仅使用app.BACKUP_DIR，调度器get_backup_dir默认C:\wms_backups；更新前备份又在根backups，来源没有统一注册。
- 同类点已排查：F1.2调度器已接入、F02只读边界与F04更新快照，不能重复开发备份调度；全仓backup域/调度/自动及人工更新路径和历史台账。既有verify_infra_fixes E9仍扫描迁移前app.py，原样基线失败，须把验证指向实际路由并保留/强化排序断言。
- 修复方向：固定来源键，不接受任意目录；统一元数据/筛选/安全路径解析，显式只读完整性校验，显示计划及保留策略；保留现有调度与30天语义，不移动或恢复生产库。
- 状态：已修复（2026-10-18）：f7a0d257 推送 main；WMS CI 39055291813 / AI 39055291911 / Perf 39055291820 于 e935ce17 全绿；本地 45 专项 + 相邻 59 passed、verify_app_py_split_backup EXIT=0、lint 0 违规。
- 生效确认：待确认；生产需重启 WMS 服务生效（模板改动，R3）；重启后打开 /backup 应看到「每日自动备份 / 手动·历史 / 更新·维护」三类来源与保留策略，并可用只读完整性校验；本轮未对生产备份执行删除/恢复。


F08/A10专项验收：原基线30 passed（5.79秒）；新增45项随相邻97 passed（11.87秒）通过；最后回注原routes/template/infra三文件，19项关键验证14 failed / 5 passed（3.88秒），还原后97通过。原E9校验迁移前app.py导致基线失败，现指向真实路由并新增AST确认排序保护实际被用，未弱化旧断言。旧服务模板上下文也可渲染旧目录并提示重启，避免统一重启前新模板报错；新校验/删除按钮不发给旧后端。隔离真实浏览器来源/组合筛选、排序、校验好坏、新备份显示、CSRF和来源请求及实际下载哈希验证通过，无JS错误；原生确认被IAB阻塞后使用隔离受控模拟，删除仅记录，真正删除只在临时文件pytest验证。只读目录元数据：当前命令环境每日6/手动11/维护10，最近每日2026-10-17 02:00，配置30天，无SQLite内容打开或写库。完整测试/CI待验；生产需重启 WMS 服务生效，不执行生产删除/恢复或重启。

F08独立验证：隔离临时文件库、源码副本及随机端口中原完整冒烟121/121通过，测试服务已关闭；Windows只适配解释器/临时根和日志，未改冒烟断言。最初初始化路径断言发现testing配置强制内存而非期望文件库，初始化中止；改为显式生产配置指向已核对的临时文件再初始化成功，无业务代码/断言放宽。原58独立AI脚本58/58通过（1 worker，167.35秒），全程临时库/上传/日志/备份目录，自动后台备份仅在验证夹具关闭；实际开启/调度/保留逻辑另有原调度器测试与浏览器开启场景覆盖。最终暂存0违规，完整测试及CI待验。


## 已修复：AUDIT-FULL-20261016 遗留 A11–A18 运维项收口

### BUG-2026-10-17-009: 审计遗留 8 项运维/文档缺陷（A11/A12/A13/A15/A16/A17/A18；A14 已闭环）

- 任务：AUDIT-FULL-20261016-001-F09；基线 350cfd40（WMS CI / AI Verification / Android / Perf 最近 main 运行均 success）。
- 根因：2026-10-16 全仓审计登记 A11–A18 后未排期修复，属"已登记未修"存量；其中 A10 已由 F08 完成代码（BUG-2026-10-17-008）。A14 已于 3c64f4c3 闭环，故本批子修复编号跳过 F04。
- 修复（8 个原子提交，均 main 分支）：
  - F01 / A11 health_check.ps1：同时探测 app/logs/app.log 与扁平 logs/app.log，取最近写入者；补 UTF-8 BOM，否则 Windows PowerShell 5.1 按 ANSI 解码中文导致 6 个 parse error（实测）。75956e3a
  - F02 / A12 app/wms.bat、app/wms.cmd：改调仓库根 install.bat，先校验存在再调用，保留 CRLF 与退出码透传。068b93bd
  - F03 / A13 tools/clone_wms_main.ps1：新增 Invoke-Git 包装，逐步检查 $LASTEXITCODE，失败即 throw；末尾核对本地 HEAD 与 origin/main 一致后才打印成功。af599d5b
  - F05 / A15 app/auto_update.py：backup_database() 返回 bool，失败（含完整性校验失败）时跳过本次 pull。836018d5
  - F06 / A16 app/config.py：新增 _env_int，非法/空/越界回退默认；BACKUP_RETENTION_DAYS 与 WMS_REMEMBER_LOGIN_DAYS 改用。21b288ad
  - F07 / A17 README.md：三账恒等式按库位开关分档（开启：①=Σ②=Σ③；关闭：①=Σ③），并回指 INVENTORY_TRUTH.md。5853b3f3
  - F08 / A18 scripts/deep_audit_lib.py + 8 个 deep_audit_mod + scripts/audit/scan_all_menus.py + start_qa_server.py + tools/fix_bug_2026_10_07_004_vision_json_only.py：去掉 /Coze/Drive 与 /workspace 硬编码，改 Path(__file__) 相对根。1d5f0989
- 回归锁：新增 tests/test_audit_health_check_log_path.py（4）、test_audit_entry_points.py（3）、test_audit_clone_script.py（4，含 Windows 行为用例）、test_audit_auto_update_backup_gate.py（4）、test_audit_config_env_parsing.py（11，子进程隔离）、test_audit_readme_inventory_identity.py（2）、test_audit_scripts_paths.py（3）。每条均设计为"回退修复后必红"。
- 验证：受影响 + 相邻测试见本轮提交前本地结果；scripts/lint_wms_rules.py 0 违规；health_check.ps1 在 Windows PowerShell 5.1 实测可解析并输出（应用日志项 PASS：C:/wms/app/logs/app.log）。
- 状态：已修复（2026-10-18）：75956e3a/068b93bd/af599d5b/836018d5/21b288ad/5853b3f3/1d5f0989 推送 main；WMS CI 39055291813 / AI 39055291911 / Perf 39055291820 于 e935ce17 全绿（含新增 7 个测试文件）。
- 生效确认：**CI 已确认（2026-10-18）**；生产侧仍待确认——health_check、app 旧入口、clone 脚本、auto_update 均为"下次调用读新文件"；README 即时生效；生产需重启 WMS 服务的仅限备份页模板（见 BUG-2026-10-17-008）。本轮未对生产执行安装、更新、删除、恢复或服务启停。


## 已修复：pre-commit 门禁脚本在 cp936 控制台崩溃

### BUG-2026-10-17-010: lint 脚本打印 ⚠/✓/✗ 在 GBK 控制台抛 UnicodeEncodeError，提交被误拒

- 发现方式：2026-10-18 修复 A10–A18 提交时，本机默认控制台执行 pre-commit，在 scripts/lint_no_raw_post_fetch.py:397 打印 ⚠ 抛 UnicodeEncodeError（'gbk' codec can't encode character '\u26a0'）；钩子只看退出码，把"脚本崩溃"当成"发现裸调 fetch"拒绝提交。临时以 PYTHONIOENCODING=utf-8 绕过。
- 根因：脚本直接 print emoji/符号，Windows 控制台/管道默认 cp936，GBK 无 ⚠（U+26A0）。与 BUG-2026-10-17-006（check_ci_green）/007（pre-push）同一根因；既有修复只覆盖了这两处，未覆盖 lint 家族。
- 同类点已排查：pre-commit 调用的两个 Python 脚本（lint_wms_rules.py、lint_no_raw_post_fetch.py）本轮齐修；check_ci_green.py 已于 8bde424c 修复；pre-push 解释器探测已于 2cbedd4 修复。
- 同根因第二消费点：三处 `git diff` 子进程原先 text=True 用本地编码解码，cp936 下中文路径/内容会让读取线程抛 UnicodeDecodeError；已补 encoding='utf-8', errors='replace'。
- 修复：两脚本新增 _configure_stdio()（stdout/stderr errors=replace 兜底）与 _glyph(unicode, ascii)（编码不支持时降级 [OK]/[FAIL]/[WARN]，box 线降级 '-'）；main() 首行调用。脚本保持自包含，因为 golden 测试会把 lint_wms_rules.py 单独复制到临时仓库。
- 回归：tests/test_console_encoding_gbk.py 5 用例——gbk/utf-8 下两脚本均不崩溃且 rc=0；_glyph 在 gbk 降级、在 utf-8 保留符号。回退修复后 gbk 用例必红。
- 状态：已修复（2026-10-18 本地验证：GBK/UTF-8 双跑 rc=0、真实钩子 HOOK_EXIT=0；待推送 CI 复核）。
- 生效确认：**已确认（2026-10-18）**：WMS CI 39057235881（ad1e1789）9/9 job success，AI Verification 39057235935 / Perf 39057235869 同 SHA success；本机默认 cp936 控制台实跑 .githooks/pre-commit（含 staged JS）HOOK_EXIT=0，输出已降级为 [OK]。pre-commit 下次提交即读新脚本，无需重启服务。


## 已修复：审计报告剩余问题整改（第二轮，2026-10-18）

### BUG-2026-10-17-011: 审计剩余 AI / 安全 / 前端 / 质量项（子修复 F01–F09）

- 背景：2026-10-18 审计报告 §4–§9 的 P1/P2 项，用户要求全面修复（仅排除 app.py 按域拆分 / A10 行数棘轮）。
- 修复：
  - F01 标签模板存储型 XSS：label_template_detail.html 改 tojson + JSON.parse（含 try/catch 回退），写入侧 _parse_label_layout 只接受合法 JSON 对象；2b06a115。
  - F02 报表 AI 洞察未转义：report_dashboard.html 对行内容/错误/提示统一 escapeHtml；b238a6ad。
  - F03 AI 5 类草稿仓库层：_ai_match_warehouse/_ai_resolve_draft_warehouse，入/出/调拨/盘点/调整全部写 warehouse；盘点 system_stock 改仓库级 get_warehouse_stock_quantities；无仓库拒绝建单；1b870eda。
  - F04 幂等 processing 租约：默认 600s（WMS_AI_DRAFT_LEASE_SECONDS），超时自动接管；64dc6bb4。
  - F05 人工确认门禁接线：OCR 落库写 low_confidence_fields（confidence=0 视为未知），门禁先读风险标记、缺失任务拒绝、异常 fail-closed；9f33205d。
  - F06 低置信度阈值单一来源：ai/documents/constants.py = 0.80，app/acceptance 全部引用；86e2345b。
  - F07 lint 覆盖：A2 支持 blueprint 且不再豁免 app/ai，A13 标题放宽到 ##–####；2c4c22d6。
  - F08 CI 覆盖：verify_ai_cross_user_isolation 并入 core，verifier 补默认仓夹具；3e44010b。
  - F09 AI 对话限流：chat/stream 与 warehouse_assistant 每用户 20 次/分钟（进程内滑动窗口）；09572ed4。
- 回归：新增 test_label_layout_script_encoding（真实渲染 + node 执行）、test_label_layout_validation、test_report_ai_insights_escaping、test_ai_draft_warehouse、test_ai_draft_idempotency_lease、test_ai_document_gate_wiring、test_audit_low_confidence_threshold、test_audit_lint_a2_blueprints、test_ai_rate_guard。
- 状态：已修复（2026-10-18）：推送 bdda0826；WMS CI 39069539558（9/9 job）、AI Verification 39069539557、Perf 39069539570 均 success。
- 生效确认：**CI 已确认（2026-10-18）**；生产侧：标签模板改动需重启 WMS 生效（R3），其余为下次调用读新代码；未对生产执行安装/更新/删除/恢复。

### BUG-2026-10-17-012: 批量入口 / 初始化 / 运行现场项（子修复 F01–F05）

- 修复：
  - F01 批量完成/反提交回写来源采购订单状态（与单张一致）；034ceaae。
  - F02 批量反提交补 _source_has_active_push 守卫，避免下游已领料时单据卡死；034ceaae。
  - F03 批量完成出库对领料/其他/采购退货校验仓库停用；0 成功返回 error 契约；034ceaae。
  - F04 业务数据初始化改为"先删③流水再归零①"，关键表删除失败即中止；1a133f3d。
  - F05 启动备份防抖（默认 600s）+ 完整性校验 + sidecar 清理 + 保留数可配；311ff643；pytest 日志隔离 14a55e64。
- 回归：test_audit_batch_entry_guards、test_audit_init_business_data_order、test_audit_startup_backup_debounce。
- 状态：已修复（2026-10-18）：推送 bdda0826；WMS CI 39069539558、AI Verification 39069539557、Perf 39069539570 均 success。
- 生效确认：**CI 已确认（2026-10-18）**；启动备份/日志为下次启动生效，批量/初始化/限流为下次调用生效；未对生产执行服务启停或数据操作。

### 本轮未纳入（明确记录，不假装已修）

- app.py 按域拆分 / A10 行数棘轮：用户明确排除（风险高）。
- 模板内联原生写 fetch 130 处、A8 pydantic 279 处书面豁免：属大规模机械改造，需要逐页回归与独立排期；本轮未动，计入 Phase 2 路线图。
- 一物多码 4 组合并、库位账 2 行残留、价格/成本维度：涉及生产数据或产品决策，只出方案不擅动。
- verify_ai_all --level full 仍剩 2 个脚本本地失败（photo_document_flow / stage3_agents 的补货 Agent），未纳入 CI；已开始把跨用户隔离等通过的脚本并入 core。


### BUG-2026-10-17-013: 审计剩余 P1/P2 深化（子修复 F01–F07，2026-10-18）

- 背景：第二轮整改后按「4 个 P1 → 小型 P2 → 机械迁移棘轮」继续；破坏性数据操作不执行。
- 修复：
  - F01 多行同物料反提交/售后/批量反审：改为按物料合计校验（审计 I2），避免两行 8+8 对单仓 10 逐行通过后扣成负账；de097844。
  - F02 旧 /api/subcontract/quick_issue：加订单写锁 + 10 秒内相同明细重放去重，docstring 标记 DEPRECATED（正式入口 /subcontract/<id>/issue）；b16c08e3。
  - F03 AI 大模型端点明文 HTTP：首次使用时 CRITICAL 告警（不改生产配置，避免直接打断 AI），审计 §6.6；b16c08e3。
  - F04 scripts/data_repairs.py：默认只读报告 FK/一物多码/三账差异，--apply-fk 需 --yes；不导入 app；f5aefcdb。
  - F05 增长棘轮：模板原生写 fetch ≤157、pydantic 豁免 ≤279，只许减；287f1f36。
  - F06 16 处 4 连问号乱码文案全部修复 + 回归守卫；b16c08e3。
  - F07 /print_queue/jobs：CSRF 豁免只服务 Bearer，Web 会话分支强制校验 token（审计 S3）；a827fa2f。
- 回归：test_audit_multiline_stock_aggregation（2）、test_audit_legacy_quick_issue_replay（1）、test_audit_ai_llm_https_warning（2）、test_audit_no_mojibake（1）、test_audit_data_repairs_tool（2）、test_audit_growth_ratchets（2）、test_audit_print_queue_csrf（2）。
- 状态：已修复（2026-10-18）：a10cbc74；WMS CI 39072330430、AI Verification 39072330438、Perf 39072330444 均 success。
  过程记录：df7832a1 首轮 CI 仅 2 个 INVENTORY_TRUTH 行号引用因 app.py 变长漂移而红；修复提交用 WMS_SKIP_CI_GATE=1 推送（唯一失败即该提交修复项），随后 a10cbc74 全绿。
- 生效确认：**CI 已确认（2026-10-18）**；旧委外端点/限流/门禁为下次调用生效，脚本无生产副作用，未对生产执行数据写入。

### BUG-2026-10-17-014: 生产数据整改（一物多码 / FK / 库位账）+ 价格维度下线（F01–F05）

- 授权：用户 2026-10-18 明确「A 组 5 项先做」，含数据写入授权；执行前整库备份。
- 备份：app/backups/manual_pre_audit_ops_20261018_060422.db（4,915,200B，quick_check ok）；
  合并前二次备份 app/backups/manual_merge_20261018_060435.db；合并报告 app/backups/merge_report_20261018.json（均被 .gitignore 忽略）。
- F01 一物多码合并（4 组，loser→keeper）：
  - 301065(1104) → 40021(1197)；40022(1198) → 40027(1203)；
  - 108032(328) → 108034(330)；115021(1305) → 115022(1306)。
  - 全部库存为 0；引用重挂：stock_transaction 2+2+2、in_order_item 1+1、out_order_item 1+1；
  - 物料 1301 → 1297；uq_material_dedupe_key 唯一索引已建（表达式与 app 常量一致）。
  - 工具：scripts/merge_duplicate_materials.py（默认 dry-run，--apply 需 --yes，自动备份）。
- F02 FK：ai_cleanup_log 19 行 executed_by=0 → 1（admin）；PRAGMA foreign_key_check = 0。
- F03 库位账：
  - 物料 615/仓1：库位 5、流水 0 → 删除残行（txn=0 规则）；
  - 物料 727/仓2：库位 1、流水 0.4 → 对齐为 0.4；
  - location_vs_txn 差异 0；①=Σ③ 差异 0。工具扩展：data_repairs.py --apply-location-reconcile --yes。
- F04 价格维度（用户拍板「先下线资金类列/报表」）：
  - 新增 system_setting price_dimension_enabled（默认 0）与 price_dimension_enabled()；
  - 关闭时下线：仪表盘「库存金额」卡、采购价格分析表、销售价格分析（页面/导出/API 400）、对应导航与按钮；
  - 物料档案的「单价」字段保留（主数据字段，非资金报表）；开启方式：设置 price_dimension_enabled=1。
- F05 AI HTTPS：目标端点 81.71.29.219:7863 当前 http/https 均连接被拒（无法现场验证 TLS），
  未改生产地址；新增 WMS_AI_REQUIRE_HTTPS=1 硬门禁（明文远程端点直接拒绝调用）+ 原 CRITICAL 告警。
  结论：需服务端先提供 TLS（nginx/caddy/vLLM 证书），属部署阻塞项。
- 验证：新增 4 个测试文件（merge 工具 2、data_repairs 3、price flag 3、HTTPS enforce 1）全过；
  数据不变量：fk=0、dup=0、stock_vs_txn=0、location_vs_txn=0。
- 状态：数据整改已执行（2026-10-18）；代码推送 308a1deb，WMS CI 39074701642 / AI 39074701733 / Perf 39074701755 全 success。
  过程记录：94ccc296 首轮 CI 红 12 项（INVENTORY_TRUTH 行号漂移 + 价格分页用例未开维度），308a1deb 修复后全绿；该修复提交用 WMS_SKIP_CI_GATE=1 推送（唯一失败即该提交修复项）。
- 生效确认：**CI 已确认（2026-10-18）**；数据侧已用 SQL 复核（备份可回滚）；价格维度/HTTPS 门禁为下次重启或下次调用生效。
### BUG-2026-10-17-015: B 组小 P2 第一批（F01–F04）

- F01 预警判定 NULL 兜底：`_alert_status_for(stock=None)` 直接比较会 TypeError 500，改为按 0 处理；回归用例 2 条。
- F02 库存查询无效仓库：`/stock_query?warehouse_id=不存在` 旧行为静默显示全 0（像“该仓没货”），改为 400「仓库不存在或已删除」；回归用例 1 条。
- F03 批量上限：`in_order/batch_complete` 的 `select_all` 原来会把整表 pending 一次载入，现与显式 ids 对齐（>500 拒绝）；`batch_revert` 补 ids>100 与 select_all>500 上限；回归用例 2 条。
- F04 删除死精度设置：`quantity/price/amount_decimal_places()` 全仓零调用，仅设置页展示，改了不生效；删除 3 个设置项与 3 个函数；回归用例 1 条。
- F05（审计 I6）期初 Excel 导入逐行 SAVEPOINT：`_apply_opening_stock_balance` 多步写入中途 ValueError 时回滚该行，不再"报跳过但已落账"；相关 262 项回归通过。
- F06（审计 B8）63 处客户端异常原文回传统一脱敏为中文通用提示（细节留 logger），ValueError 业务校验文案保留；新增全仓扫描守卫。相关模块 283 项回归通过。
- 复核：物料初始库存仓库链路已在 BUG-2026-08-16-003 闭环（opening 流水+库位账+默认仓），本批次复核通过，未重复改动。
- 状态：已修复（2026-10-18，本地）；CI 待推送复核（当前 GitHub 网络不通，本地提交 afc5496f）。
- 生效确认：待确认；下次重启/下次调用生效。
### BUG-2026-10-20-001: 工单领料 Excel 导入忽略指定仓库（审计 A01）

- 关联任务：AUDIT-FULL-20261020-001-F01；来源 docs/audit/WMS_FULL_AUDIT_20261020.md A01。
- 历史同根因：BUG-2026-08-05-008 / BUG-2026-08-16-016（仓库/库位必填的导入消费点遗漏）；10月18日 inventory 分册已提及，本次不重复开发既有手工保存校验。
- 根因与危害：导入别名缺仓库/库位，固定写默认仓；同单跨仓不检查；通用子串识别还会把“仓库ID”误识别为名称列。四仓场景显式 B 仓被保存到 A 仓，后续人工完成可能扣错仓。
- 修复：ID优先、名称/编码次之；同单后续空白沿用已选仓，首行缺省才取启用默认仓；无效/停用/无默认仓、同单仓库或库位冲突返回行号并整批回滚。开启库位时必须填写库位；仍只建 pending 草稿，不扣库存。官方Excel模板与前端备用模板追加仓库/库位列，既有列序不变。
- 同类点已排查：工单领料新增/编辑/表格保存/完成已有仓库存在性与启用状态校验；盘点导入有行仓库解析并纳入相邻回归。本次修复工单领料导入；未改生产历史单据或其流水。
- 验证：修前相关基线55 passed；新12场景旧代码11 failed/1 passed；ID+名称列增测复现1 failed/17 passed；最终21项专项；旧路由隔离回注18 failed/1 passed，模板修复前2 failed；相关及台账最终结果见完成记录。完整本地4221 passed/91 skipped/19 failed/16 errors（683.71秒）；其中新增BUG登记契约已按既定POST_SPLIT_BUGS机制增加独立条目，旧315/141/19/1断言保留，10项通过；剩余失败原代码与修复代码分别重跑均18 failed/16 errors，逐项一致、0新增。隔离文件库冒烟121/121、规则0违规、既有BUG回归通过。
- 状态：已修复（代码及CI，2026-10-20）；生效确认：待确认，生产需重启 WMS 服务生效；未执行生产重启或提交测试单据。

- 提交与闭环：`7ddca86ec45e49f8d1516c33cdab9cefca94c3f2` 已推送main；本地与origin/main SHA及tree一致；WMS CI #1653 / AI #1948 success，Android最近#833 success。生产需重启 WMS 服务生效；生效确认仍待人工现场验收。

### BUG-2026-10-20-002: 工单领料表单保存漏传领料人（审计 A02）

- 关联任务：AUDIT-FULL-20261020-001-F02；修复现有领料人能力，不新增并行功能。
- 同根因历史：现有 test_requisition_picker 三项仅验证手工JSON和回填；已排查共享表单、列表弹窗、普通出库表单。共享 collectHeader 缺 picker，后端用空值覆盖；其他两类入口已携带，不作重复修改。
- 危害：页面填写后保存丢失；编辑旧单时可能清空原领料人。
- 修复：仅在共享表单 requisition 分支收集 picker，保持手工填写/修改/清空语义。
- 回归：实际HTML字段解析→实际collectHeader JS→HTTP保存→数据库回读→详情回填，新增/修改/主动清空3项；原模板回退后3项均失败；恢复后111项专项及连续录单相邻通过，既有断言保留。
- 验证：专项及台账121 passed；完整套件4228 passed/91 skipped/18 failed/16 errors（698.14秒），失败ID与A01原代码基线34项逐项一致、0新增；隔离文件库冒烟121/121、规则0违规、既有BUG回归通过；CI已确认，见下方提交记录。
- 状态：已修复（代码及CI，2026-10-20）；生效确认：待确认，生产需重启 WMS 服务生效；未改生产单据或执行生产重启。

- 提交与闭环：`ab3f4541ad02ed71d0b93457222a258aab41ce0e` 已推送main；本地与origin/main SHA及tree一致；WMS CI #1654 / AI #1949 success，Android最近#833 success。生产需重启 WMS 服务生效；生效确认仍待人工现场验收。

### BUG-2026-10-20-003: 旧统计导出忽略状态及明细筛选（审计 A03）

- 关联任务：AUDIT-FULL-20261020-001-F03；既有统计/打印消费点修复。
- 同根因历史：BUG-2026-09-23-005（打印仅传仓库/日期）、BUG-2026-09-18-012（明细合同筛选粒度）、BUG-2026-08-12-005（仓库隔离）；同类点已排查 print/export 别名及工具栏，新版报表/单据导出纳入相邻测试。
- 根因与危害：旧入口无状态和关键词等过滤，先筛单据再输出全部明细；屏幕已筛已完成/合同，Excel仍可能含草稿或同单其他合同数量。
- 修复：裸统计默认仅 completed；工具栏显式传 document_type 进入单据清单模式，保留状态/关键词/往来单位/业务类型/合同/工程/排序与日期，并在Excel末列显示状态。复用列表查询辅助函数，直接输出匹配明细，全集不分页；仓库名/编码兼容，空值/失效仓不猜归属；保持旧九列、sheet名称和裸URL参数映射契约。
- 验证：修前相关29 passed；新增初始28项在旧实现全部失败；修后30项专项与仓库/工具栏/模板/N+1回归合计60 passed。回退旧路由及JS后30项全部失败；另27项相邻通过，错误响应5项通过。组合运行旧测试出现TESTING全局配置冲突，不带新增测试仍9项同样失败，隔离运行通过。完整套件4258 passed/91 skipped/18 failed/16 errors（677.21秒），失败ID与修前34项完全一致，0新增；隔离冒烟121/121、规则0违规、既有BUG回归通过；CI已确认，见下方提交记录。
- 状态：已修复（代码及CI，2026-10-20）。
- 生效确认：待确认，生产需重启 WMS 服务生效并刷新浏览器缓存；未在生产写测试单据或重启服务。

- 提交与闭环：`0ca68811970ec10c11655240233f19b2056fb462` 已推送main；本地与origin/main SHA及tree一致；WMS CI #1655 / AI #1950 success，Android最近#833 success。生产需重启 WMS 服务生效；生效确认仍待人工现场验收。

### BUG-2026-10-20-004: 双通道会话写请求遗漏 CSRF（审计 A04）

- 关联任务：AUDIT-FULL-20261020-001-F04。
- 同根因历史与消费点：BUG-2026-10-17-013-F07 打印队列；同类点已排查 mobile 两类装饰器、app 两类装饰器、OCR Excel、打印队列。
- 根因与危害：见 docs/audit/WMS_FULL_AUDIT_20261020.md 的 A04 实证。
- 修复：统一 validate_session_write；会话写请求校验 header/form/JSON token，纯 Bearer 仍需有效令牌；打印显式 Authorization 优先验证，伪造令牌不回落 Cookie。只读请求保持兼容。
- 回归：tests/test_audit_20261020_remaining.py；修前相邻80 passed；旧代码回注30 failed/17 passed（新加只读兼容用例不参与该次回注），文件已恢复；专项相邻181 passed，最终新增回归48项及台账等合同100 passed；UTF-8模式完整4340 passed/91 skipped/0失败，隔离冒烟121/121，lint/棘轮/BUG检查通过；GitHub结果见本批main检查。
- 状态：已修复（代码已推送main，2779d115的WMS CI、AI验证及性能检查全部success）；代码提交：`a03212419512b89822137be4b49d2466b7ed97f6`。
- 生效确认：待确认，生产需重启 WMS 服务生效；未执行生产启停、单据/库存写入或密码操作。

### BUG-2026-10-20-005: 原生 API 登录缺少跨账号 IP 限流（审计 A05）

- 关联任务：AUDIT-FULL-20261020-001-F05。
- 同根因历史与消费点：F2.2 Web 登录限流；同类点已排查 Web/API 入口和 get_request_ip 可信代理边界。
- 根因与危害：见 docs/audit/WMS_FULL_AUDIT_20261020.md 的 A05 实证。
- 修复：API 在访问账号和补建登录表之前检查共享 login_fail:IP 窗口，未知账号及错误密码记失败；保留账号锁定、窗口过期及其他 IP 正常登录。
- 回归：tests/test_audit_20261020_remaining.py；修前相邻80 passed；旧代码回注30 failed/17 passed（新加只读兼容用例不参与该次回注），文件已恢复；专项相邻181 passed，最终新增回归48项及台账等合同100 passed；UTF-8模式完整4340 passed/91 skipped/0失败，隔离冒烟121/121，lint/棘轮/BUG检查通过；GitHub结果见本批main检查。
- 状态：已修复（代码已推送main，2779d115的WMS CI、AI验证及性能检查全部success）；代码提交：`a03212419512b89822137be4b49d2466b7ed97f6`。
- 生效确认：待确认，生产需重启 WMS 服务生效；未执行生产启停、单据/库存写入或密码操作。

### BUG-2026-10-20-006: 仓库名称及编码变更漏同步单据（审计 A06）

- 关联任务：AUDIT-FULL-20261020-001-F06。
- 同根因历史与消费点：2026-08-30 仓库模块 W2 历史回归（tests/test_bug_2026_08_30_005_warehouse_module_fixes.py）；同类点已排查 documents 全部仓库文本列与 inventory/print 的稳定 warehouse_id 外键。
- 根因与危害：见 docs/audit/WMS_FULL_AUDIT_20261020.md 的 A06 实证。
- 修复：补盘点、扫码盘点、调整、委外发料及收料；名称与编码用 case 一次映射全部单据仓库列及调拨两端，事务失败整批回滚；跨仓名称/编码歧义明确拒绝，不猜历史空值归属，不修改真实库位。
- 回归：tests/test_audit_20261020_remaining.py；修前相邻80 passed；旧代码回注30 failed/17 passed（新加只读兼容用例不参与该次回注），文件已恢复；专项相邻181 passed，最终新增回归48项及台账等合同100 passed；UTF-8模式完整4340 passed/91 skipped/0失败，隔离冒烟121/121，lint/棘轮/BUG检查通过；GitHub结果见本批main检查。
- 状态：已修复（代码已推送main，2779d115的WMS CI、AI验证及性能检查全部success）；代码提交：`a03212419512b89822137be4b49d2466b7ed97f6`。
- 生效确认：待确认，生产需重启 WMS 服务生效；未执行生产启停、单据/库存写入或密码操作。

### BUG-2026-10-20-007: 期初库存编辑换库位导致账不一致（审计 A07）

- 关联任务：AUDIT-FULL-20261020-001-F07。
- 同根因历史与消费点：BUG-2026-08-16-002、P1-7③；同类点已排查单行、批量、单据保存和导入公共写入口。
- 根因与危害：见 docs/audit/WMS_FULL_AUDIT_20261020.md 的 A07 实证。
- 修复：在 _apply_opening_stock_balance 修改任何字段前拒绝既有行更换库位，开关两种状态均保护；同库位数量编辑不变。补齐 batch_save 日期解析导入，保证进入业务校验并整批回滚。此修复不提供期初行直接迁移库位功能，应使用库存调拨。
- 回归：tests/test_audit_20261020_remaining.py；修前相邻80 passed；旧代码回注30 failed/17 passed（新加只读兼容用例不参与该次回注），文件已恢复；专项相邻181 passed，最终新增回归48项及台账等合同100 passed；UTF-8模式完整4340 passed/91 skipped/0失败，隔离冒烟121/121，lint/棘轮/BUG检查通过；GitHub结果见本批main检查。
- 状态：已修复（代码已推送main，2779d115的WMS CI、AI验证及性能检查全部success）；代码提交：`a03212419512b89822137be4b49d2466b7ed97f6`。
- 生效确认：待确认，生产需重启 WMS 服务生效；未执行生产启停、单据/库存写入或密码操作。

### BUG-2026-10-20-008: 外部 AI 明文传输门禁默认未开启（审计 A08）

- 关联任务：AUDIT-FULL-20261020-001-F08。
- 同根因历史与消费点：BUG-2026-10-17-013-F03 / BUG-2026-10-17-014-F05；同类点已排查主 LLM、新版 providers、语音 TokenHub、native 解析与 OCR。
- 根因与危害：见 docs/audit/WMS_FULL_AUDIT_20261020.md 的 A08 实证。
- 修复：外部 HTTP 一律在网络发送前阻断，环境变量 0 不再绕过；保留 HTTPS 证书验证及回环本地服务。新版助手返回回退结果，语音提示 HTTPS，连接状态页展示暂停原因。已按用户明确授权将生产AI地址改为本机回环 http://127.0.0.1:7863/v1，保留密钥/模型；原地址已单项备份，可回退。
- 回归：tests/test_audit_20261020_remaining.py；修前相邻80 passed；旧代码回注30 failed/17 passed（新加只读兼容用例不参与该次回注），文件已恢复；专项相邻181 passed，最终新增回归48项及台账等合同100 passed；UTF-8模式完整4340 passed/91 skipped/0失败，隔离冒烟121/121，lint/棘轮/BUG检查通过；GitHub结果见本批main检查。
- 状态：已修复（代码已推送main，2779d115的WMS CI、AI验证及性能检查全部success）；代码提交：`a03212419512b89822137be4b49d2466b7ed97f6`。
- 生效确认：待确认，生产需重启 WMS 服务生效；未执行生产启停、单据/库存写入或密码操作。
- 部署遗留：2026-10-20 对当前网关做不带凭证的 HTTPS GET 探测，TLS/证书握手失败；用户已选本机回环方案并完成地址切换，公网明文风险消除；本机网关对现有密钥返回401，功能恢复仍需凭证对齐，不把端口可达写成AI已恢复。


### BUG-2026-10-20-009: 单据底部物料候选框超出可视区域

- **任务 ID**：UI-MATERIAL-DROPDOWN-VIEWPORT-001。
- **状态**：本地已修复，CI及生产生效待确认。
- **根因/危害**：采购入库等单据把候选框固定放在输入框下方，只计算 top/left，未检查视口剩余空间；末行候选被窗口底部截断，遮挡后续行。采购申请另混用了固定定位与页面 scrollY。
- **修复**：共享 dropdown-position.js 按当前窗口（含 iframe）判断上下空间；不足时向上展开，限制高度并内部滚动，左右边界收敛；页面/容器滚动和窗口缩放时更新位置，候选内部滚动不触发表格重定位。
- **同类点已排查**：采购入库/领料新增与详情加行、工单领料/调拨/盘点共用表单、调整、售后、采购订单/申请、销售订单新增/编辑、期初库存共12个模板；同函数内供应商候选一起接入。quick-select.js 已有独立上翻处理，不属于固定向下的同根因。历史台账检索发现手机端 BUG-2026-09-18-006 是 Compose 布局裁切，非本次 Web 固定定位根因。
- **回归**：原相邻34项通过；新增旧代码19项失败，修复后新增及相邻53项通过，追加resize覆盖。浏览器隔离库采购入库第30行、20个候选：菜单向上展开且完整可见，键盘滚到最后候选并回车选中，焦点进入数量。最终全量4387 passed / 91 skipped（428.84秒）；定位与台账30项通过，隔离冒烟119/119、规则lint0违规、既有BUG检查通过。首轮测试同步问题已修复并整套重跑通过，既有断言保留。
- **生效确认**：隔离预览已验证；生产需重启 WMS 服务生效，生产尚未重启，未写入生产单据或库存。


### BUG-2026-10-20-010: 已释放自动下推记录误拦截采购入库重做
- 状态：已修复；代码提交 `1bd0bc1d` 已推送 main，WMS CI #1662、AI Verification #1957 success。
- 任务：INBOUND-AUTO-PUSH-RELEASE-001。
- 根因：自动完成领料以固定 auto-requisition-源ID 查全部历史，未区分 active/released；反提交并删除下游后，重做原单或删除重建复用SQLite ID时被旧记录拦截。仅过滤状态仍会碰撞历史唯一键。
- 修复：完成事务写锁内复用有效下推判断，仅有效关联阻断；每次有效下推生成独立请求编号，保留已释放记录。原有 pending 状态锁继续阻止重复完成；不修改生产单据或库存。
- 同类点已排查：手动下推使用调用方请求编号作重放保护；删除下游释放记录、反提交与删除源单、数量汇总均已有 active 过滤，无固定自动编号复发点。
- 回归：相关基线13通过；旧代码新增两用例均失败；重做三轮（含删除重建ID复用）、旧格式已释放记录、重复点击、有效关联阻断及库存回滚；相邻模块22通过。全量4356通过/91跳过，34项因GBK解码失败；启用PYTHONUTF8后34项全部通过。既有BUG检查通过，隔离冒烟119/119，规则lint0违规。
- 生效确认：2026-10-20 只读核对生产日志19:28启动（晚于18:36路由修改）、8080监听新PID15308，本地及公网登录HTTP200；未再次重启，原单仍pending、旧记录released。实际完成入库由用户操作确认，未代操作生产单据。

## 新发现待处理（2026-10-21）

### BUG-2026-10-21-001: 本地自愈启动脚本仍含云凭证字面量

- 状态：已登记待处理，按R8不盲改生产凭证链。
- 根因及危害：本机被Git忽略的run_wms_task.bat包含腾讯云凭证字面量；本地文件读取可暴露凭证。未验证凭证有效性，未输出值，不等同已提交源码泄露。
- 同类点已排查：检索历史密钥台账；BUG-2026-08-16-019针对SystemSetting和token文件，与本项启动脚本注入环境变量来源不同。Git索引未跟踪该文件，.gitignore已排除。
- 建议修复：核对计划任务实际身份和凭证消费点，将凭证迁移到受限权限的本机秘密存储；由有云端权限的操作员轮换旧凭证，再验证语音/OCR。不能只删除变量造成现有功能中断，也不能因Git已忽略就宣称本地风险消除。
- 验证：仅检查变量是否存在、Git跟踪/忽略状态；未发送凭证、修改脚本、调用云端或重启服务。
- 生效确认：待确认；凭证迁移、云端轮换及功能验收尚未执行。

## 已修复代码待发布验收（2026-10-21）

### BUG-2026-10-21-002: Pillow已知漏洞使每日CI安全扫描失败

- 状态：代码已修复并推送main，提交802d585101f6b9fdc41302443086f7d5493bdfbb；WMS CI #1668、AI Verification #1963 success，三工作流门禁退出0（2026-10-21）。
- 根因：生产依赖固定Pillow12.3.0；main d2437fd9的WMS CI #1664在pip-audit阻塞扫描命中8项新CVE，其余测试与冒烟通过。
- 漏洞证据：CVE-2026-112895、112400、112397、112896、112897、112395、112404、112899，日志均给出修复版本13.0.0。
- 同类点已排查：历史BUG-2026-08-24-001、BUG-2026-09-30-003为同类依赖安全维护。本次唯一生效钉版在app/requirements.txt，测试依赖通过-r复用；历史报告版本不重写。AI图像、单据照片、标签/条码、打印消费Pillow，纳入验证。
- 修复：只将Pillow钉版升级13.0.0，保持pip-audit阻塞，不加漏洞忽略，不降低既有测试断言。
- 验证：旧依赖pip-audit退出1并复现8项CVE，新依赖闭包扫描No known vulnerabilities found。升级前后图像/打印相关模块各29 passed；隔离HTTP冒烟121/121。新版本全量4388 passed/91 skipped/2 failed：运行中登记更新使台账快照失效，修正登记后专项通过；LRU测试单独复测新环境26项（含台账）、旧环境16项均通过，原因未完全确定，不改其代码或断言。普通规则0违规、A11全量和存量棘轮通过、既有BUG静态回归通过。新SHA的CI仍须独立通过，不将本次本地全量称为零失败。
- 生效确认：2026-10-21用户明确授权仅生产Pillow升级和重启；实际生产Python311安装13.0.0，08:53通过既有WMS-Warehouse任务启动新PID16900（Session0），启动日志代码27d54e9、CSRF开启、文件密钥、数据库迁移禁用。本地与公网/login均HTTP200；pip check无损坏依赖，生产解释器下隔离图像/打印29 passed。库存、单据、用户表前后摘要一致，quick_check=ok。升级前SQLite一致性备份及12.3.0回退wheel保存在C:\wms_backups\pillow_deploy_20261021；未修改云凭证或拆分路由，未变更密码或提交业务单据。


### BUG-2026-10-21-003: 共用分页条数选择器未绑定且旧参数覆盖当前选择

- 状态：已修复并推送main，提交`3aab2686`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39541602595)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39541602491)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：pager宏遗漏per-page-select，八页条数选择无反应；统一绑定器先写新per_page再合并base_kwargs，七页保留的旧per_page会覆盖新值。
- 修复：共用宏接入既有绑定器，筛选合并后再设置新条数并回到第一页；删除无调用的bindPagerSelect，保留原页面路径、仓库/关键词/合同/排序和embedded参数。
- 同类点已排查：历史BUG-F02-07及BUG-2026-09-23-004；盘点、调拨、调整、工单领料、委外订单/发料/收料及库存查询共八页；销售订单/销售出库使用独立监听，其他per_page_select共用绑定器亦保留。
- 回归：修前相邻75 passed/86 skipped；新增16项真实模板渲染加Node监听执行，旧代码16 failed；文件备份回退后16 failed，恢复后及相邻检查通过。相邻最终91 passed/86 skipped；全量4405 passed/91 skipped，唯一失败为收集期旧台账快照未含本次新增ID，补登记映射后台账10项通过，既有断言保留；隔离库HTTP冒烟121/121、规则0违规、既有BUG检查通过。
- 生产生效记录推送门禁（2026-10-21）：本地匿名API仍403，连接器逐一核实main最新Android运行[39503220864](https://github.com/SIX2090/wms/actions/runs/39503220864)（d2437fd9）、AI验证[39547834820](https://github.com/SIX2090/wms/actions/runs/39547834820)及WMS CI[39547834782](https://github.com/SIX2090/wms/actions/runs/39547834782)（baf08eed）均completed/success。若pre-push仍同一查询故障，仅此次临时使用已有WMS_SKIP_CI_GATE=1，推送后再验收新CI。
- CI门禁替代证据：匿名API限流403；连接器核实main最近Android运行39503220864（d2437fd9）、AI验证39526472526及WMS CI39526472527（517ed188）均completed/success；仅该次push如复核仍同样失败，按AGENTS§三临时使用既有WMS_SKIP_CI_GATE。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


### BUG-2026-10-21-004: 销售订单全选残留已删除的行内处理器

- 状态：已修复并推送main，提交`cd4aecba`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39542161428)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39542161747)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：SM-P6-03-3已将全选迁移到bindListActions，表头仍调用已删除的toggleAllSalesOrders，点击抛ReferenceError。
- 修复：移除重复onclick，沿用统一change监听，全选/取消只影响当前页可操作行。
- 同类点已排查：采购订单、采购申请、售后出库和销售选单的toggleAll均有定义；销售出库列表使用既有统一监听，无同类残留。
- 回归：修前销售相邻10 passed；新增两项执行实际onclick及统一绑定器，旧代码及备份回退均2 failed；恢复后验证勾选/取消与禁用行不受影响。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


### BUG-2026-10-21-005: 其他出入库未实现翻单按钮呈可用且查找默认方向错误

- 状态：已修复并推送main，提交`8dec8d76`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39542552756)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39542549692)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：共用工具栏按order_id启用翻单按钮，两个页面的处理器却永远只提示返回列表；查找链接在未传地址时始终指入库列表。
- 修复：四个尚未实现的翻单按钮恒禁用并提示通过查找单据返回列表，删除两页不可达提示分支；默认列表按入/出方向选择，显式列表及其筛选条件优先保留。不新增跨业务类型导航逻辑。
- 同类点已排查：历史BUG-2026-09-23-005为全局栏列表导航误触，本次只处理其他出入库专用工具栏；既有全局真实导航、查找浮层及其CSS完整保留。
- 回归：修前相邻37 passed；新增6项模板渲染，新建/编辑两方向旧代码及备份回退均4 failed/2 passed；恢复后相邻43 passed。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


### BUG-2026-10-21-006: 操作入口及AI建议未按后端角色权限筛选

- 关联任务：AI-C01-FIX-ROLE-UI-001（已完成AI-C01的界面修复子项）。
- 状态：已修复并推送main，提交`09e66d7c`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39545484498)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39545484358)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：批量导入GET仅登录校验且卡片全量显示；采购申请列表/详情/侧边栏和明细选中下推按钮遗漏角色门控；助手data-role仅声明未过滤；旧隐藏导航亦残留viewer导入入口。
- 修复：导入GET只对admin/warehouse/purchase/production开放，12张卡片逐一与各自POST角色对齐；采购申请所有写入口限admin/purchase，保留查询/打印与执行进度；AI入口沿用AI_USE_ROLES，建议按通用/本角色筛选，admin保留30项；保留旧隐藏导航及动态查找、导航CSS，只移除其viewer导入入口。
- 同类点已排查：BUG-2026-08-16-013及AI-WMS-FINANCE-ROLE是既有后端防线，本次只对齐UI；导入12个消费点、采购申请列表/详情/侧栏/下推区、AI按钮与初始化脚本均已核对。未增加AI路由/工具/模型/开关/迁移，不修改后端既有角色写权限和人工确认边界。
- 回归：修前财务/AI权限/采购申请/导入相邻72 passed；新增真实内存库用户及HTTP页面渲染验证，覆盖八角色、四状态、12导入接口权限和管理员全部建议；文件备份完整回退37 failed/11 passed，恢复后专项相邻120 passed；含前批及台账82项通过，隔离HTTP冒烟121/121、规则0违规、既有BUG检查通过；首轮遗漏侧栏及选中下推入口由行为测试发现并补齐，未放宽断言；追加普通/embedded页面及通用工具栏opt-out核验，保留只读导出，最终相邻134项通过。
- 首轮回滚：6e7ea6f7的CI失败，按R8通过连接器非强制快进回滚到25a1dc3285e1e6e5c71e721186b56971eac4bf01，tree与绿色8dec8d76一致，本地fetch/rebase后SHA一致。失败为删除旧导航破坏BOM双菜单契约及工作台链接验证，以及新AI_TASK标记不被台账表格解析器识别；不放宽断言。回滚后AI验证39544348329、WMS CI39544348270 success。
- 重新修复：旧导航整块保留，仅清理无权导入入口；AI子项待验收时用普通任务引用，完成提交/CI后再补完成表与正式标记；新增BOM及三项AI验证进入相邻检查。观察项#11按R8保留，后续清理需单独明确导航契约。
- 重做验证：八角色普通/embedded页面及相邻137 passed；BOM双导航断言原样通过；verify_ai_ledger_consistency、verify_ai_warehouse_workbench_page、verify_ai_purchase_workbench_page均退出0。代码备份回退及恢复再次验证，不降低既有断言。
- 本次推送门禁：连接器现场核实main最近Android https://github.com/SIX2090/wms/actions/runs/39503220864 （d2437fd9）、AI验证 https://github.com/SIX2090/wms/actions/runs/39544348329 与WMS CI https://github.com/SIX2090/wms/actions/runs/39544348270 （25a1dc3285e1e6e5c71e721186b56971eac4bf01）均completed/success；若pre-push同样HTTP403，仅本次临时设置既有WMS_SKIP_CI_GATE。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


### BUG-2026-10-21-007: 单据完成请求期间可重复点击且按钮缺少忙碌状态

- 状态：已修复并推送main，提交`d065a67a`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39546805324)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39546805346)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：独立完成处理器在确认及请求链期间没有前端重入保护；慢网络下可多次发请求，依靠后端状态/写锁拒绝重复操作，干扰录单与错误提示。
- 修复：新增共用WMS.runDocumentAction，确认及完整请求链期间锁定对应按钮并设置aria-busy，重复调用复用当前Promise；取消、失败或预警后恢复原disabled/aria状态，保留原已禁用状态。覆盖入/出库详情、售后列表/详情、采购申请列表/详情、委外发料/收料和调整单两段式保存完成；请求统一复用WMS.api.postRaw，保留预警/force和续单分支，不改后端库存/状态与人工确认。
- 同类点已排查：既有UI-REQUISITION-ONE-ACTION-001及采购收货单动作已有保存链保护；共用表单和入/出库新增继续沿用现有保存锁。本次覆盖全部独立completeOrder及委外completeIssue/completeReceive，调整表单保存和完成一并防重；旧disabled归档模板不启用。
- 回归：修前相关模块66 passed；新增36项真实处理器及共用脚本执行，文件备份完整回退27 failed/9 passed。恢复后覆盖确认仅一次、挂起请求仅一次、失败后可重试、原禁用态保留、预警后force查询、调整保存完成串联；原采购续单18项断言保留，只为实际共用脚本及统一API补接测试夹具；仓库提交字段回归保留原断言，仅定位实际WMS.api.postRaw调用。
- 最终验证：完成/续单/仓库字段/委外表单/候选框/粘贴等相邻194 passed；权限/台账/导航及忙碌保护97 passed；隔离HTTP冒烟121/121，规则0违规，业务JS无裸非GET fetch。
- 推送门禁替代证据：连接器确认main最近Android https://github.com/SIX2090/wms/actions/runs/39503220864 （d2437fd9）、AI验证 https://github.com/SIX2090/wms/actions/runs/39545484358 和WMS CI https://github.com/SIX2090/wms/actions/runs/39545484498 （09e66d7c905d8ade33e214f967829c8874d73e11）均completed/success；如pre-push仍同一匿名HTTP403，仅本次临时使用WMS_SKIP_CI_GATE。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


### BUG-2026-10-21-008: 销售出库列表禁用复选框缺少原因说明

- 状态：已修复并推送main，提交`19d4332f`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39547269912)、[AI验证](https://github.com/SIX2090/wms/actions/runs/39547269724)均completed/success；2026-10-21 13:31生产已重启加载修复版本，部署验证见生效确认。
- 根因/危害：销售出库完成态复选框已禁用，却无title解释，与领料出库列表不一致，用户无法判断不能勾选的原因。
- 修复：为已完成单据加“已完成单据不能批量完成或删除”提示，保留原pending状态门控及选择逻辑。
- 同类点已排查：出库列表已有禁用原因提示；销售订单统一全选监听跳过disabled行，本次不变更权限或操作范围。
- 回归：修前全选2项通过；新增草稿/完成态模板渲染验证，旧代码及备份回退均1 failed/3 passed，草稿仍可勾选，完成态保持禁用且有提示。
- 最终验证：选择/销售/分页/忙碌保护相邻66 passed，台账及提示14 passed，规则0违规；推送前连接器核实最近AI验证39546805346及WMS CI39546805324（d065a67a4298524e7687352e85947a745e0e55ae）、Android39503220864（d2437fd9）均completed/success。如本地门禁仍同一HTTP403，仅该次临时使用既有WMS_SKIP_CI_GATE。
- 生效确认：2026-10-21 13:31（北京时间），Codex按用户“继续上面的任务”沿用既有WMS-Warehouse计划任务重启；旧PID16900停止后确认端口空闲，新PID1680（Python311/Session0）独占127.0.0.1:8080；启动日志13:31:26确认加载`baf08ee`（含本项修复），CSRF开启。任务LastTaskResult=0；本机及公网https://gd2026.top/login均HTTP200，共用document-action.js返回200且包含runDocumentAction。生产需重启 WMS 服务生效，本次已完成；功能行为以此前隔离回归及绿色CI为证，生产仅核对进程、启动版本和GET响应，未执行生产业务写操作或更改账号密码。


## 已修复代码待发布验收（2026-10-21 手机菜单实测）

### BUG-2026-10-21-009: 手机手工入库出库及查询提交引用未声明的盘点区域变量

- 状态：已修复并发布（P1），代码提交`03a047b0767150471e8bc96a8f3fa5418623285d`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39559777836)及[AI验证](https://github.com/SIX2090/wms/actions/runs/39559778077)均completed/success。初次检查只登记，随后按用户明确授权修复并下载已构建APK。
- 根因/危害：`app/templates/mobile_scan.html`共用提交处理器读取`scanAreaInput`，初始化区未声明此变量；该ID只在check模式渲染。入库、出库、查询模式均抛`ReferenceError: scanAreaInput is not defined`，发生在按钮禁用之后、提交fetch及其catch/finally之前，导致未发送scan_submit请求且按钮持续禁用、状态停在“提交中”。编码检索卡片仍可显示，不能据此判断提交可用。
- 复现：以当前main代码`3d1abe7d`启动127.0.0.1:9081独立内存数据库，保留CSRF，通过真实侧栏菜单进入页面；物料AUD-M001总库存50、A仓30/B仓20。管理员分别输入编码、选择A仓、输入数量2后点击确认入库/确认出库；查询模式输入编码点击查询库存。三种模式均由浏览器控制台及页面错误提示复现上述异常；入库按钮实测disabled=true。
- 同类点已排查：历史BUG-2026-10-21-004为不同模板残留已删除函数的行内事件，本次为共用表单变量绑定遗漏。已检查in/out/query/check四个模式及单笔/批量入口；批量排队亦在同一payload组装之后，受同一错误阻断。check模式因存在同名DOM元素，当前浏览器隐式window命名属性使该引用可用，但仍缺少显式绑定，不应依赖此行为。
- 盘点对照：A仓选中预建进行中盘点单AUD-CHECK-001，实际保存数量28、区域A1成功，生成CS26100001并挂原盘点批次，页面进度刷新为1/1。隔离库最终入库单0、出库单0、扫码盘点1、总库存仍50，未执行调整单完成或库存改写。盘点必须先在电脑端创建进行中盘点单，此为既有业务约定。
- 下载入口核验（修前）：生产本机及公网`/mobile/app`均HTTP200但Content-Type为text/html，实际返回“扫码 APP 安装包暂未部署”，不能下载APK；属于既有BUG-2026-08-27-008的友好兜底分支，需另行部署安装包或配置下载地址，不能把200说明页当下载成功。
- 验证：相关12个测试模块共85 passed（含仓库边界、库位、盘点选单/进度/原因、草稿确认、下载兜底和表单字段）；这些既有用例未执行本次失败的浏览器提交链，不能证明H5端到端可用。浏览器截图保存在本机output/playwright/mobile-menu-in-blocked.png及mobile-menu-check-success.png（忽略目录，不纳入Git）。
- 初查建议：显式初始化scanAreaInput并为共用提交前置Promise异常提供按钮恢复；增加四模式真实JS提交回归锁，保留仓库边界及盘点选单约束。初查未实施，后续经用户授权执行下述修复。
- 修复：显式绑定可缺省的scanAreaInput，返回完整请求Promise，前置组装异常由外层catch显示错误并恢复按钮原disabled状态；不依赖check模式的DOM隐式全局变量，不改变库存业务逻辑或人工确认。生产需重启 WMS 服务生效。
- 回归锁：新增test_mobile_scan_submit_runtime.py，执行真实变量绑定及提交监听，覆盖in/out/query/check四模式的成功、网络失败、前置异常、批量分支与失败后重试，共16项。修前16 failed；文件备份回退16 failed；恢复16 passed。修前受影响模块46 passed，修后及相邻87 passed；隔离浏览器实际入库+2/出库-2及查询、盘点均成功，最终总库存50，控制台无错误；隔离临时文件库HTTP冒烟121/121。
- 全量验证：本地4515 passed/91 skipped/1 failed；唯一失败为下载兜底用例直接假定部署机无APK，而本次已安装APK导致按文本解码二进制失败。仅补tmp_path缺失文件路径及环境隔离，保留全部既有断言，下载分支与脚本重新复测；最终完整套件由推送CI验收，不将本地首次全量称为零失败。规则0违规、既有BUG检查通过。
- APK下载核验：从官方android-apk Release下载2026-10-20构建产物，25,430,191字节，SHA256=90afdc3fdd5f50d4dcfaf7ab4634be0287572389b00a394e604918d6c94f6966，与GitHub资产digest一致；ZIP含AndroidManifest.xml和classes.dex。已放置部署机根app-release.apk，本机及公网/mobile/app均返回200、APK MIME及附件文件名；两端完整下载哈希均一致。二进制通过本机Git排除表忽略，不提交源码仓库。未在实体手机安装验收。
- 开工门禁替代证据：本地匿名API403限流，连接器核实最新Android运行39503220864（d2437fd9）、AI验证39552790698及WMS CI39552790614（da06f548）均completed/success；如pre-push仍同一查询故障，仅本次临时设置既有WMS_SKIP_CI_GATE=1，推送后验收新CI。
- 生效确认：2026-10-21 15:07（北京时间），Codex沿用WMS-Warehouse计划任务重启，核对旧PID1680停止和端口空闲后启动新PID13936（Python311/Session0）；15:07:55启动日志确认`03a047b`，任务退出0，127.0.0.1:8080只有一个监听实例，本机及公网登录GET200。生产需重启 WMS 服务生效，本次已完成。下载入口返回真实APK及正确MIME、附件文件名、25,430,191字节，完整下载哈希与官方Release一致。H5入/出库、查询、盘点及失败恢复只在隔离库验证，无脚本错误；未操作生产单据、库存、账号或密码，未在实体手机安装验收。临时测试服务已关闭。
- 最终验收：修正下载测试环境隔离后，下载/四模式脚本/仓库边界/草稿/库位/打印/盘点撤销71 passed，台账10 passed，断言未放宽；上述代码SHA的CI所有9个job成功，AI验证成功，最新Android39503220864（d2437fd9）success。生效记录提交前门禁以此三项为准；若本地匿名查询仍403，按既有规则仅本次临时使用WMS_SKIP_CI_GATE并验收后续CI。


### BUG-2026-10-21-010: 五个详情页未使用Excel时仍预加载完整SheetJS

- 状态：已修复并发布，代码提交`312b4e6f`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39576199650)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39576199599)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：入库、出库、售后出库、采购申请及委外详情固定引用944,515字节xlsx.full.min.js，即使只查看单据也需加载和解析；服务器导出及服务器模板下载并不依赖此库。公网有长期缓存，不把文件大小等同每次页面网络流量。
- 同类点已排查：五个活跃详情页均通过唯一ExcelImportExport组件使用SheetJS；四个_disabled_unused_20260506归档模板不启用、不修改。历史台账的报表数据库N+1懒加载属于不同根因，既有Excel导出/完整行数契约保留。
- 修复：移除五页预加载标签，共用组件按需加载同目录库并保留部署前缀及STATIC_VERSION参数；每个页面共用一次Promise，已存在XLSX直接复用，加载失败或未初始化清理脚本后允许重试。只在导入文件预览、客户端导出及客户端模板生成时等待依赖，服务器导出/模板保持直接打开URL。文件连续切换时旧选择及旧读取结果不能覆盖新预览；失败时保持确认导入禁用。
- 回归：修前相邻94 passed；新增5个模板及12个真实组件运行用例，共17项，原代码17 failed；文件备份回退组件后12 failed/5 passed，恢复后17 passed。覆盖无预载、缓存、并发只加载一次、失败重试、未初始化、服务器分支、导入预览及选文件竞态、客户端导出、模板生成，并实际加载仓库SheetJS进行xlsx写入和读取。最终相邻111 passed；五个隔离HTTP详情均200且无预载；隔离SQLite文件库HTTP冒烟119/119，未减少既有断言。
- 浏览器实证：隔离详情打开时xlsx资源请求0；点击导出后请求1，下载真实xlsx并用openpyxl读取确认AUD-M001行；再打开导入预览同一文件显示1条数据，xlsx请求仍为1。只做隔离预览与下载，未执行生产导入或单据完成。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。

- 本批推送门禁：匿名API403限流；连接器逐一核实main最新Android39503220864（d2437fd9）、AI验证39560308607和WMS CI39560308533（5fc8d7d7）均completed/success。只对此次同一查询故障临时使用既有WMS_SKIP_CI_GATE=1；后续仍验收新SHA的CI。


### BUG-2026-10-21-011: 前端转义和CSRF工具重复及栏目动态HTML缺少统一编码

- 状态：已修复并发布，代码提交`f31f80f5`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39580033935)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39580034023)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/影响：普通页面重复定义escapeHtml，个别DOM版本只编码文本不处理属性引号，行为不一致；CSRF包装重复覆盖，独立维护易遗漏嵌入页取token。app.js四处栏目/导航HTML直接拼接字段名、键值、图标或标题，特殊文字可能被解析为HTML。导航来源当前是本地常量，不将其报告为已证实可利用的远程XSS。
- 修复：18个普通模板共19处escapeHtml定义删除，统一复用已有app.js全局编码器；独立打印模板编辑器不加载app.js，保留其自包含文本编码器。五页局部getCsrfToken/csrfFetch及app.js备用副本移除，只保留基础模板的全局CSRF包装；统一保留meta、隐藏字段、父页面token回退、跨域异常降级、显式CSRF头和原始body/Response行为。四处动态HTML统一调用已有escapeHtml编码属性和文字。
- 同类点已排查：全站顶层活跃模板和app.js的7份csrfFetch归一为1份；21处escapeHtml定义减少至2处（公共实现及独立编辑器）。保留旧隐藏导航、动态cb-doc-nav/cb-doc-search样式和已有权限边界，不移除有效功能。未增加AI路由、工具、模型、开关、迁移或修改人工确认。
- 验证：修前相关模块72 passed；新增40项验证普通模板共用工具、唯一CSRF定义、四处真实HTML拼接对特殊文字的解析结果、五种token来源及显式请求参数保留。原代码27 failed/13 passed；文件备份回退27 failed/13 passed；恢复后40 passed，最终相邻177 passed。隔离浏览器用包含img/onerror及引号的栏目名打开栏目设置，完整显示为普通文字，无图片/事件注入、无控制台错误。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 本批推送门禁：最新main的Android39503220864（d2437fd9）、AI验证39576199599及WMS CI39576199650（312b4e6f）均completed/success；若本地pre-push同一匿名403，仅本次临时使用已有WMS_SKIP_CI_GATE=1。

- 首轮回滚：6190f528的WMS CI39578173144失败，具体为两组截取函数运行的工具栏夹具漏加载escapeHtml，30 failed/1479 passed/13 skipped，全部为ReferenceError，未放宽断言。按R8立即本地revert，保留本地恢复补丁；通过GitHub连接器以父6190f528和已绿312b4e6f的原树创建回滚63b7a7345ebb3f763faa256fc5dc08a52550af7c，使用expected_sha及force=false快进更新main；本地fetch/rebase对齐。回滚树与312b4e6f相同，WMS CI39579135660、AI验证39579135725均success。
- 重做验证：两组工具栏/续单夹具加载生产app.js的真实escapeHtml函数，不替换为宽松stub，原有全部断言保留；重做运行82 passed，加入原有相邻与BOM导航后222 passed。新40项回归及其回退验证保持原结果。重做推送前最新三门禁为上述回滚CI及Android39503220864，均completed/success；同一匿名403查询故障时仅本次临时使用已有WMS_SKIP_CI_GATE。


### BUG-2026-10-21-012: 基础资料页绕过统一请求和确认提示

- 状态：已修复并发布，代码提交`fa948c43`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39585479172)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39585479095)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：分类、客户、部门、员工、单位、仓库、供应商七页共33处原生fetch自行解析JSON，HTTP错误和会话过期处理脱离统一API；部分提示及删除/默认仓库确认仍使用原生弹窗，体验与错误处理不一致。
- 修复：26处POST及7处GET迁入WMS.api.postRaw/getRaw，保留完整响应、FormData及JSON载荷、原URL与自定义请求头；移除重复response.json解析，提示使用showToast，五处确认使用异步showConfirm，取消不发请求。未改后端权限、数据校验、库存或单据状态。
- 同类点已排查：沿用BUG-2026-10-21-007统一请求基础设施；全查上述七页新增、编辑、导入、单删、批删及默认仓库操作，不宣称其他业务页裸fetch已清零。
- 回归：修前相邻28 passed；新增64项实际页面处理器结合生产api.js运行，覆盖成功、HTTP400结构化错误、CSRF、multipart归属、JSON载荷和取消确认。旧代码及文件备份回退均64 failed/21 skipped，恢复64 passed/21 skipped（表单无额外确认的21种组合不适用）。最终相邻178 passed/21 skipped；隔离文件库冒烟119/119。
- 浏览器验收：127.0.0.1:9081独立内存库新增AUD-FRONT-012成功，取消删除后记录保留，编辑GET回填并保存成功；确认框截图output/playwright/master-data-confirm.png。HTTP失败及取消不请求由运行时测试覆盖，未删除生产数据或更改账号。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 推送前门禁：Android39503220864（d2437fd9）、AI39580034023及WMS CI39580033935（f31f80f5）均completed/success；同一匿名API403时仅该次临时使用已有WMS_SKIP_CI_GATE=1。

- 全量验证记录（012）：tests/执行23分27秒，4636 passed/112 skipped/1 failed；唯一失败是测试启动后新增012台账导致已导入POST_SPLIT_BUGS快照与读取时台账不同步，未修改基线或放宽断言。最终源文件固定后整组台账10项复跑通过（联合本批74 passed/21 skipped）；verify_wms_bugs通过，规则0违规。最终提交CI再次核对全量结果。


### BUG-2026-10-21-013: 公共确认框缺少键盘焦点边界且采购驳回使用原生输入框

- 状态：已修复并发布，代码提交`78f066bd`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39587154102)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39587154189)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：公共确认队列只有鼠标处理，无Esc取消/Tab焦点循环/关闭归还焦点；采购申请驳回仍使用原生prompt，异步替换后若不锁定可重复打开并提交。
- 修复：原确认队列增加WMS.confirm/WMS.prompt，单行输入与确认共用组件、取消返回null并保留空字符串语义；内容只用textContent/value，兼容缓存旧壳无输入框时的原生兜底。增加dialog/aria关联、默认取消焦点、Esc取消、Tab循环、输入框Enter确认及中文输入组合态保护，捕获阶段隔离页面快捷键，队列关闭后归还原焦点。采购驳回复用WMS.runDocumentAction锁及统一API，取消不请求，失败恢复按钮。
- 同类点已排查：关联007请求忙碌保护；检查公共队列全部消费页及驳回处理器，保留showConfirm旧入口，不改权限、审批后端或业务状态；其他原生弹窗逐页迁移未在本条宣称清零。
- 回归：修前完成/采购续单相邻51 passed；新增14项生产队列/键盘事件/实际驳回处理器运行验证，旧代码及文件备份回退14 failed，恢复14 passed。相邻195 passed/21 skipped（新增焦点延后用例后专项14 passed），原断言保留。
- 浏览器验收：9081内存库打开AUD-PR驳回框，按钮禁用、输入框聚焦；Esc关闭且按钮恢复、焦点回到rejectOrder按钮，采购申请仍待审批；截图output/playwright/purchase-reject-dialog.png。未在生产执行驳回或其他业务写操作。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 推送前门禁：Android39503220864（d2437fd9）、WMS CI39585479172及AI39585479095（fa948c43）均completed/success；同一匿名403查询故障时仅该次临时使用已有WMS_SKIP_CI_GATE=1。

- 最终相邻验证（013）：206 passed/21 skipped，隔离9082文件库重启加载新壳后冒烟119/119，规则0违规；新增14项回退全部失败，最终代码恢复后全过。


### BUG-2026-10-21-014: 单据新增页重复样式及拆分资产未纳入缓存版本

- 状态：已修复并发布，代码提交`ae458182`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39588488982)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39588488892)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：采购入库和销售订单新增页重复474行CSS，页面响应反复传输；现有静态版本仅遍历JS根目录及custom.css，抽取独立CSS或pages子目录资产后若不扩展监控，后续修复可能留在浏览器旧缓存。
- 修复：两页共用static/css/document-form.css，原样保留公共规则与加载位置，入库数量spinner差异仍在本页；版本生成递归追踪业务JS/CSS并保持xlsx第三方库排除和既有核心资产顺序。无业务脚本、表单字段、请求或后端库存逻辑变更。
- 同类点已排查：关联AI-WMS-FILTER-004静态版本修复，检查CSS及未来pages子目录，未删除动态使用的cb-doc-nav/search样式；其他单据样式差异保留，不以相似度直接合并。
- 回归：修前相邻13 passed；新增7项覆盖共享引用/原规则规范化SHA256完全一致、数量差异保留、CSS和嵌套JS/CSS新增/修改/删除版本变化及xlsx排除。旧代码及文件备份回退均6 failed/1 passed，恢复专项相邻37 passed。
- 浏览器验收：9081内存库记录两页拆分前后页面头、表格、表头、单元格及数量输入框的矩形、字体、边框、间距、背景、appearance，JSON逐项完全一致；入库数量仍textfield。截图output/playwright/document-form-shared-styles.png，原始比较数据保留在output/playwright。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 推送前门禁：Android39503220864（d2437fd9）、AI39587154189及WMS CI39587154102（78f066bd）均completed/success；同一匿名403故障时仅本次临时使用已有WMS_SKIP_CI_GATE=1。

- 最终相邻验证（014）：90 passed，规则0违规；共享CSS无相对资源URL或Jinja表达式，原规则规范化SHA256不变；隔离9082文件库重启后冒烟119/119。


### BUG-2026-10-21-015: 基础资料脚本内联无法独立缓存

- 状态：已修复并发布，代码提交`fa1da477`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39589796914)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39589797106)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：部门、员工、仓库三个页面共380行脚本内联在HTML响应中，无法独立缓存和执行JS lint；三页现有实现不含Jinja表达式，可在不改变数据注入和行为的前提下拆分。
- 修复：原样移入static/js/pages/department.js、employee.js、warehouse.js，模板在原位置加载带STATIC_VERSION的普通script，保留全局onclick函数及DOMContentLoaded监听顺序；复用014递归资产版本追踪。未改业务函数内容或新增配置全局变量。
- 同类点已排查：其他四个基础资料页含动态端点或多段脚本，留待逐页处理，避免把模板表达式直接搬入JS；现有单据页和AI页面亦不在本条宣称全部拆分。
- 回归：原功能64 passed/21 skipped；新增三项引用仅一次、无重复内联、文件无Jinja及脚本内容SHA256保持拆分前完全一致检查，旧模板及文件备份回退3 failed，恢复后结合实际外链脚本和生产api.js运行，专项相邻74 passed/21 skipped。原传输和取消操作断言全部保留，仅更新夹具按真实script顺序加载外链文件。
- 浏览器验收：9081内存库部门页实际加载/pages/department.js，新增AUD-ASSET-015成功、列表回显正确、无控制台错误；截图output/playwright/master-data-page-assets.png。生产数据和账号未动。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 推送前门禁：Android39503220864（d2437fd9）、AI39588488892及WMS CI39588488982（ae458182）均completed/success；同一匿名403查询故障时仅该次临时使用已有WMS_SKIP_CI_GATE=1。


### BUG-2026-10-21-016: 五个单据页残留无对应控件的合同表头脚本

- 状态：已修复并发布，代码提交`e819df90`；[WMS CI](https://github.com/SIX2090/wms/actions/runs/39591304154)和[AI验证](https://github.com/SIX2090/wms/actions/runs/39591304496)均completed/success，生产已加载包含该修复的`e819df9`。
- 根因/危害：入库、出库、采购订单新增、销售订单新增/编辑页各有约97行旧合同表头搜索IIFE，读取contractSearch/contractDropdown等不存在的控件后提前return；每页反复传输不能执行的代码，混淆现用逐行合同维护。
- 修复：只移除五段旧IIFE约485行；保留逐行line-contract-no/line-project-name、全局ContractAutocomplete、向下填充和出库页同一script中的有效领料人搜索。未改接口或合同数据。
- 同类点已排查：全仓检索上述四个旧ID只出现在这五段读取代码，无HTML或动态创建来源；拆出旧IIFE按实际缺失控件执行，五页均fetch=0/events=0。未按整个script标签盲删出库页的领料人选择器。
- 回归：修前相关20 passed/5 failed（新增清理断言），新增6项覆盖五页清理及现用行字段保留、真实领料人搜索/选中；备份回退5 failed/1 passed，恢复25 passed。结合合同自动补全、键盘、多合同不合并及采购/销售导出字段相邻61 passed，原有断言全部保留。
- 浏览器验收：9081内存库新增测试员工AUD-PICK-016，出库新增页输入“回归”得到“回归领料人”，点击后回填成功、无控制台错误；未保存/完成出库单。截图output/playwright/outbound-picker-preserved.png。
- 生效确认：2026-10-21 19:26–19:28（北京时间），Codex按既有WMS-Warehouse计划任务发布，新PID3356（Python311/Session0）独占8080，启动日志确认加载e819df9；生产需重启 WMS 服务生效，本次已完成。具体只读验收见文末发布记录。
- 推送前门禁：Android39503220864（d2437fd9）、AI39589797106及WMS CI39589796914（fa1da477）均completed/success；同一匿名403故障时仅该次临时使用已有WMS_SKIP_CI_GATE=1。

- 最终验证（016）：相邻145 passed/21 skipped，规则0违规、verify_wms_bugs通过；9082隔离文件库重启后冒烟119/119；旧表头四个ID全仓模板/JS残留为0。


## 前端工程修复发布验收与复评核对（2026-10-21 晚）

- 发布：发布时代码main与origin/main均为e819df90d883e854cf0c32825e4a60896213b251。原生产PID13936的解释器、命令、启动时间与服务归属重新核对后停止，确认8080释放，再沿用C:\wms\run_wms_task.bat计划任务启动；未创建第二实例、未改启动配置。新PID3356，Python311/Session0；19:26:22启动日志显示e819df9、CSRF开启、db-check migrate=ok。入口显式WMS_NO_DB_TOUCH=1，此db-check仅作启动检查证据，不宣称执行数据库迁移。
- 生产GET验收：127.0.0.1:8080/login与https://gd2026.top/login均200且有登录表单；app.js、excel-import-export.js、三个pages脚本和document-form.css均200，响应字节与磁盘一致。Task LastTaskResult=0。未提交/审核/完成/反提交/删除生产单据，未改生产库存、账号或密码。
- 最终验证：本轮全部新回归结合相邻模块307 passed/21 skipped，隔离文件库冒烟119/119；规则0违规、历史BUG验证通过。最终代码WMS CI39591304154、AI39591304496及最新Android39503220864均completed/success。首次本地全量的台账快照同步失败及复跑结果已在012记录，后续所有提交均由完整CI重新验收。
- 015补充：三个外链脚本均HTTP200且字节与磁盘一致；员工新增框正常、仓库编辑回填Audit A。9082隔离库重启后冒烟119/119，实际认证页面缓存版本同时包含公共CSS及新页面JS时间戳；相邻134 passed/21 skipped。首次手工缓存验证误用旧测试库默认密码而断言失败，改用该隔离库既有测试凭据后验证通过，未更改密码。
- 第二轮复评校正：AI建议按钮已由base.html的Jinja按admin/warehouse/purchase/sales/production分组输出，无AI使用权限的角色整个面板不渲染；data-role是保留元数据，缺少JS属性读取不表示未门控。已有test_toolbar_role_visibility.py覆盖八角色及单据状态。所列category/customer/department/employee/unit/warehouse/supplier七页及其外链脚本原生fetch为0。cb-doc-nav与cb-doc-search在app.js中动态生成，相关样式保留。公共确认/输入框的Esc、Tab、焦点恢复与驳回取消边界已在013完成，不能列为“本轮未涉及”。
- 后续工程范围：物料及手机扫码等其他业务页仍有原生请求；原生alert/兼容fallback和调试输出需区分普通壳、独立打印编辑页后逐页迁移；其余单据样式有实际差异，公共行操作及大量混合Jinja的脚本尚未整体拆分；移动端卡片化和全部图标可访问性不在本轮完成范围。按R8保留复杂业务实现，先建立逐页回归再改，不按相似度或审计计数直接替换；这些工程债不计入本轮已完成项。

- 复评再验证：test_toolbar_role_visibility.py重新执行48 passed，覆盖八角色下AI建议分组、无AI权限角色整面板隐藏、导入导航和采购审批操作状态；证实复评所谓“AI建议角色过滤未实现”为误判，未重复增加前端过滤。台账契约10 passed。


## 已修复并纳入回归（2026-10-21 补充）

### BUG-2026-10-21-017: 导入结果消息作为HTML解析且批量导入链接未约束来源

- 状态：已修复并发布，代码提交047ee1f7；WMS CI39596399831及AI39596400038均completed/success。
- 根因/危害：员工、合同、物料、批量导入直接拼接服务端消息到innerHTML，特殊字符可能被解析成标签；批量导入文档链接也直接使用返回值。
- 修复：所有成功、业务失败和网络失败消息统一使用现有escapeHtml，保留原始字符；批量导入的警告、行错误和单号同步转义，文档链接只接受同源HTTP(S)地址，保留新标签打开行为。导入接口与业务写入规则未变。
- 同类点已排查：关联BUG-2026-10-21-011及BUG-2026-08-04-004，检查全部导入结果消费点；其他showToast/textContent或已转义分支无需重复改动。
- 回归：修改前受影响和相邻177 passed/21 skipped；新用例覆盖四页各成功/业务失败/HTTP失败/网络失败消息和八种链接边界，最终回退验证24 failed/32 passed，恢复后56项全部通过。原基础资料功能断言保留，夹具加载真实全局escapeHtml；员工脚本内容快照因三处显式转义更新。
- 浏览器验收：9081内存库员工导入弹窗返回测试消息，实际页面显示完整的<img src=x onerror="alert(1)"> A&B <零件>文字，未生成图片节点；不执行真实导入写入。
- 验证结果：专项及相邻233 passed/21 skipped；规则扫描0违规。
- 生效确认：2026-10-21 20:13–20:14（北京时间），Codex沿用WMS-Warehouse计划任务重启，PID16876（Python311/Session0）独占8080，启动日志加载69acafd并显示csrf=on；生产需重启 WMS 服务生效，本次已完成。本地与公网登录页HTTP200且CSRF字段存在，员工脚本响应与磁盘字节一致。业务测试仅在隔离库进行。


### BUG-2026-10-21-018: 出库校验使用阻塞提示且入出库批量修改反馈被弹窗遮挡

- 状态：已修复并发布，代码提交69acafd8；WMS CI39597478492及AI39597478502均completed/success。
- 根因/危害：出库表单及批量修改仍使用原生alert，部分拦截没有定位输入；批量修改遮罩z-index为99999，高于公共提示20000，直接替换会看不到提示。
- 修复：出库16处提示改为showToast，日期、往来单位、部门、来源、数量、仓库、库位和空明细定位对应字段；入出库批量修改使用相同提示和输入定位，遮罩层级降至19000，保留弹窗和原始明细供修正。数量超过10000的二次确认、全部校验条件、保存/完成请求和数据结构保持原样。
- 同类点已排查：关联P1批量修改NaN回归及BUG-2026-10-21-013，检查入库/出库同名批量修改函数并一并修复；入库独立采购选单提示不在本项宣称清零。
- 回归：修前受影响及相邻72 passed；新增39项真实函数执行覆盖九种表单拦截和正常销售/领料/其他/退货/无库位保存、两页批量非法输入不改行值/不关闭弹窗/输入聚焦、正常数量/零单价/仓库批量设置及提示层级。旧代码与备份回退均26 failed/13 passed，恢复后专项及相邻111 passed，原提交幂等断言保留。
- 浏览器验收：9081内存库缺少部门时显示“请选择部门”且焦点定位department_id；批量输入负单价时提示消息为“单价不能小于0”，焦点保留batchUpdateValue、弹窗不关闭、原单价2.00未改。DOM核对遮罩19000低于提示20000；截图output/playwright/outbound-validation-feedback.png。
- 最终相邻验证：143 passed，规则0违规；9082隔离文件库冒烟119/119。首次重启后立即运行冒烟遇服务尚未监听，确认监听后重跑全过。
- 生效确认：2026-10-21 20:13–20:14（北京时间），Codex沿用WMS-Warehouse计划任务重启，PID16876（Python311/Session0）独占8080，启动日志加载69acafd；生产需重启 WMS 服务生效，本次已完成。未在生产执行保存、完成、审批、删除或账号修改。


## 2026-10-21 导入反馈与录单校验发布记录

- 本次两项：BUG-017导入结果转义及同源链接，BUG-018出库校验/入出库批量修改反馈。对应代码047ee1f7、69acafd8均已推送main且HEAD与origin/main一致。
- 最终组合回归184 passed/21 skipped；两轮独立隔离冒烟均119/119；规则0违规。此前已分别完成233 passed/21 skipped、111 passed及143 passed相邻验证，新增两组测试均经过文件备份回退验证。未放宽原有断言。
- 最新main门禁：Android APK Build [39503220864](https://github.com/SIX2090/wms/actions/runs/39503220864)（d2437fd9），WMS CI [39597478492](https://github.com/SIX2090/wms/actions/runs/39597478492)、AI验证 [39597478502](https://github.com/SIX2090/wms/actions/runs/39597478502)（69acafd8）全部completed/success。Actions列表第一页无Android项，第二页找到其最新记录，未以旧绿覆盖较新失败记录。
- 生产生效：20:13核对既有PID3356身份、启动时间与无服务托管后停止，确认8080释放，才启动既有WMS-Warehouse计划任务；新PID16876/Session0独占8080。20:13:34启动日志为69acafd，CSRF开启，WMS_NO_DB_TOUCH=1沿用原脚本；db-check仅为检查结果，不声称执行迁移。本地8080/login与HTTPS公网/login均200含CSRF字段，静态员工脚本字节一致；未运行生产业务写入验证。
- 本次仅前端修复，后续大范围样式/脚本拆分和其他页面提示迁移仍按逐页回归处理，不宣称全站工程债清零。


## 已修复并纳入回归（2026-10-22）

### BUG-2026-10-22-001: pypdf已知漏洞使每日CI依赖安全扫描失败

- 状态：已修复并发布；代码badf2c62，最终8aa5f066的CI及AI验证success，生产pypdf6.21.1已安装。
- 根因/危害：requirements固定pypdf6.19.0，main51d7fc13每日WMS CI39682375647安全扫描命中CVE-2026-113792/113795/113793/113794/113786五项；其余单测、回归、冒烟全部通过。修复上限版本为6.21.1，存在恶意PDF解析资源/图像解码风险。
- 修复：只升级pypdf钉版至6.21.1，保留pip-audit阻塞，不加忽略项；官方变更记录https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html。测试依赖继续复用生产清单，未更改AI解析业务函数或权限。
- 同类点已排查：关联BUG-2026-08-24-001、BUG-2026-09-30-003、BUG-2026-10-21-002；全仓唯一钉版为app/requirements.txt，唯一业务导入在_ai_parse_pdf_bytes，纳入多页文本、无效/截断/加密文件回退与JPEG正常解码验证。
- 回归：修前附件相邻23 passed；新增8项真实PDF测试，旧版本及文件备份回退均2 failed/6 passed（旧版将标为DCT的PNG交给非JPEG解码器），隔离6.21.1恢复后结合既有附件31 passed，原断言保留。未在生产执行文件解析或业务写入。
- 依赖扫描：隔离工具执行python -m pip_audit -r app/requirements.txt，返回No known vulnerabilities found；不向生产解释器安装审计工具。
- 生效确认：2026-10-22 09:38，核验旧PID16876身份并停止，使用已留存官方wheel离线安装生产Python311的pypdf6.21.1，pip check通过；沿用WMS-Warehouse任务启动PID16204/Session0，生产解释器PDF安全与兼容用例8 passed（隔离测试，不连接生产业务库）。旧6.19.0 wheel保留在C:/wms_backups/pypdf_deploy_20261022用于回退。

- CI纠错记录：首次64974e1c安全扫描通过，但新增测试引用未钉版packaging导致既有test_all_third_party_imports_pinned失败；依R8立即以ac1b487b完整回滚原树。重新实施仅用标准库解析固定发布版数字，保持>=6.21.1断言和真实解码安全用例，补跑测试依赖闭包契约，不新增第三方依赖，不修改原门禁断言。普通git push因远端原有依赖安全红灯被钩子阻断；本次仅用已授权GitHub连接器发布CI修复，逐文件blob及完整tree与本地相同后非force更新main。verify_remote_sync脚本缺GH_TOKEN，未提取连接器凭据，改用Git取回远端对象比对完整树。


### BUG-2026-10-22-002: 入库采购选单校验仍使用原生提示且提示被遮罩遮挡

- 状态：已修复并发布；代码eeb907ab，CI39700051838及AI39700051766成功，生产已加载8aa5f066。
- 根因/危害：采购明细带入与旧生成处理器共9处原生alert；无勾选/跨供应商拦截未定位控件，选单遮罩99999高于公共提示20000。
- 修复：两条处理路径统一showToast并显示5秒；无勾选与跨供应商定位选择框，数量校验保持定位原输入；采购选单遮罩调整19000。数量正数/未入库上限、同供应商限制、原始请求体、来源行映射及带入不自动保存均不变。
- 同类点已排查：关联BUG-2026-10-21-018，入出库批量修改已修，本条覆盖入库采购选单两种处理器，不宣称全部模板原生提示清零。
- 回归：修前受影响及相邻108 passed；新增14项真实处理器执行，旧代码及备份回退均12 failed/2 passed；恢复后含既有依赖门禁125 passed，保留原始校验与接口断言。
- 浏览器验收：9081内存库未勾选时焦点定位选择框、超量6/剩余5时定位数量且不写入明细；改为2后带入AUD-M001数量2、来源采购行11，弹窗关闭且未保存单据，截图output/playwright/purchase-selection-feedback-20261022.png。
- 补充验证：30项相邻通过，规则0违规，9082隔离文件库冒烟119/119。首次testing配置强制内存库导致冒烟无法用既有测试凭据登录；改为development配置并在导入前排除生产路径、导入后断言实际URI等于既有临时库后重跑全过，未更改密码。
- 生效确认：2026-10-22 09:38，生产需重启 WMS 服务生效，本次已沿用WMS-Warehouse重启。PID16204/Session0独占8080，启动版本8aa5f06，CSRF开启；本地及公网登录GET200含CSRF字段。全部业务验证使用隔离库，不修改生产单据或库存。


### BUG-2026-10-22-003: 物料与手机扫码请求重复封装导致错误处理不一致

- 状态：已修复并发布；代码6e049f8f，CI39704867094及AI39704867102成功，生产已加载8aa5f066。
- 根因/危害：物料15处、手机扫码10处原生fetch/csrfFetch分别处理CSRF、401/419和HTTP响应，部分非JSON错误暴露解析异常；物料档案图片加载失败被吞掉，待确认失败提示未使用message。直接迁移识图会丢失AbortController信号，因为公共API未透传signal。
- 修复：25处旧请求全部迁至WMS.api.getRaw/postRaw，保留原始返回体、裸数组、multiple状态及分页数据；共用CSRF、HTTP错误及会话处理；公共API透传可选signal，保留识图60秒取消及FormData边界。手机保留业务失败检查、队列、请求ID、仓库与盘点参数、人工确认及按钮恢复；物料状态使用raw保留status，失败时统一toast，空字段修复仅成功刷新，档案图片错误用textContent显示。删除手机重复令牌与会话函数，模板加载错误从控制台转可见提示。
- 同类点已排查：关联BUG-2026-10-21-012/017及BUG-2026-08-04-004；检查两页所有请求调用、物料内嵌标签编辑器和手机两个闭包；保留既有WMS.api调用、原生人工确认与后端接口，不修改库存算法或分页上限。
- 回归：修前受影响及相邻130 passed；新传输用例覆盖每个实际请求表达式的原始成功/数组/multiple、HTTP JSON/HTML、401/419及网络失败、CSRF、multipart、未重复JSON序列化与取消信号，补充物料新增编辑反馈、图片错误文字与待确认实际分页函数；备份回退到旧源码220项失败，恢复后组合323 passed。原H5提交运行断言保留，夹具加载实际api.js及meta节点，扩展四模式HTTP/业务/会话失败重试。一次Node子进程因本机内存不足退出，限制Node堆64MB并低并发后对应3项重跑通过，组合323项通过。
- 浏览器验收：9081内存库实际编辑AUD-M001名称并保存回显Audit Material API，单位/库存50等字段保持，截图output/playwright/material-api-save-20261022.png；图片接口故障时显示明确失败文字，手机查询不存在编码显示“物料不存在”，重试AUD-M001显示更新后名称且按钮可用，截图output/playwright/mobile-api-query-20261022.png。两页无浏览器脚本错误；未在生产操作。
- 完整回归：543个测试文件分为互不重叠的两片，每片使用独立pytest进程且无xdist控制器，共5031 passed/112 skipped；AI查询记忆test_lru_limit一次断言4!=5，完整重跑该模块16 passed，相关AI源码未改，记录为未稳定复现，不宣称首次全绿。此前两次全量尝试因4GB主机内存压力和执行方式调整中止，不计成功结果。A1–A14扫描0违规，业务静态JS非GET请求扫描通过；模板存量裸请求仅警告。
- 最终检查：verify_wms_bugs回归检查通过；9082显式隔离文件库冒烟119/119，未使用生产默认地址。
- 生效确认：2026-10-22 09:38，生产需重启 WMS 服务生效，本次已沿用WMS-Warehouse重启，PID16204/Session0独占8080、加载8aa5f06。生产静态api.js响应与磁盘字节相同，本地/公网登录GET200；测试未改变生产单据、库存、账号或权限。

### BUG-2026-10-22-004: 多页错误与校验提示仍阻塞操作，批量替换需保留结果查看边界

- 状态：已修复并发布；代码8aa5f066，CI39706477161及AI39706477085成功，生产已重启生效。
- 根因/危害：AI质量/保留/预测/推荐、审批、标签、物料新增、委外、调拨及微信等页仍用原生alert显示普通错误；直接批量替换会将校验标为成功、破坏无showToast时的兜底，以及让刷新前结果和打印代理令牌消失。
- 修复：接手外部工具的18页改动，统一普通错误与校验为danger/warning；纠正入库兜底及打印必填/委外末行提示等级。独立打印模板页用textContent渲染轻量提示。刷新/跳转前结果、打印令牌和真正缺少全局提示函数的兼容兜底保留原有人工关闭行为并注明理由，不宣称原生alert全站清零。所有确认、请求、单据写入和库存规则不变。
- 同类点已排查：关联BUG-2026-10-21-018、BUG-2026-10-22-002/003，逐项核对外部工具的全部提示替换；撤销out_order_detail和material缺失函数分支继续调用showToast的错误替换。AI界面修复映射AI-R15-FIX-UI-FEEDBACK-001，关联既有AI-R14及WMS-AI-GATE-001，不新增AI能力。
- 回归：修改前完整测试已覆盖543文件；新增26项真实页面函数运行用例，覆盖校验不发送请求、AI/标签业务和网络失败、审批失败、微信网络失败、令牌先人工查看再刷新与取消不请求、独立页恶意样式文字按textContent显示及自动移除。18个模板逐文件字节备份、回退HEAD验证23 failed/3 passed，再由finally恢复全部原字节；恢复后专项及打印/保留配置/微信开关/物料相邻115 passed。首次夹具遗漏FormData.append，补齐浏览器接口后运行，不修改断言。
- 最终检查：台账契约10 passed，A1–A14规则0违规；重启自有9082隔离实例后冒烟119/119。整套pytest结果沿用本次543文件完整覆盖及失败模块重跑证据，不重复启动；AI专项全量验证另按AI台账要求执行。
- 生效确认：2026-10-22 09:38，生产需重启 WMS 服务生效，本次已通过既有WMS-Warehouse任务重启，PID16204/Session0、启动版本8aa5f06、任务结果0，本地/公网登录GET200。沿用脚本WMS_NO_DB_TOUCH=1；db-check为检查结果，不宣称进行了迁移。测试仅用Node夹具及隔离数据库，不发送真实AI请求或微信消息，不修改生产单据、库存、令牌、账号或权限。


**本次前端修复发布闭环（2026-10-22）**

- 已推送main：badf2c62依赖安全修复、eeb907ab采购选单提示、6e049f8f物料/手机请求统一、8aa5f066其余页面错误提示。所有代码提交均核对HEAD与origin/main相同；最后一次WMS CI [39706477161](https://github.com/SIX2090/wms/actions/runs/39706477161)、AI [39706477085](https://github.com/SIX2090/wms/actions/runs/39706477085)均completed/success。Android最近main运行[39682360398](https://github.com/SIX2090/wms/actions/runs/39682360398)（51d7fc13）success。
- 8aa5f066首次普通push被匿名API限流403阻断，未当作CI失败。使用已连接GitHub工具逐一核对上述Android记录，以及6e049f8f的CI39704867094/AI39704867102均completed/success后，依AGENTS §三查询故障例外仅对本次push临时设置WMS_SKIP_CI_GATE=1，finally清除；实际push输出6e049f8f..8aa5f066 main -> main，远端新SHA一致。
- 本轮未新增AI能力，AI-R15-FIX-UI-FEEDBACK-001只涉及现有页面反馈。verify_ai_all --level full --jobs 2已执行，70脚本68通过；photo_document_flow因测试物料为空失败，stage3_agents的安全库存说明文字断言失败。将18模板全部备份并回退6e049f8f后，单独执行这两脚本仍相同失败，再finally恢复原字节，确认属存量验收脚本问题；未放宽断言或扩展修改库存/AI业务。其余68脚本含verify_wms_bugs通过，CI core验证全绿。该AI子项保留待验收，不将存量失败误报为全量通过。
- 仅重启生产一次加载8aa5f066，随后只补台账；未对生产执行登录POST、保存、完成、审批、删除、发消息或账号修改。未修改既有测试规则，后续减少重复全量的分级方案需单独修订DEVELOPMENT_RULES/AGENTS后实施。

### BUG-2026-10-22-005: 物料新增及标签页遗留POST未使用统一请求层

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：物料新增2个、标签列表3个、标签布局1个POST仍各自处理CSRF/HTTP响应；布局JSON解码失败后再次读取text会掩盖原错误，部分业务失败丢失服务端原因。
- 修复：6处统一WMS.api.postRaw，保留FormData、完整status、布局payload、删除人工确认、成功人工关闭结果与跳转；HTTP非JSON错误可靠展示状态，布局按钮失败后恢复并可重试。category/customer/unit/supplier复核已完成迁移，不重复改动。
- 同类点已排查：关联BUG-2026-10-21-012/017及BUG-2026-10-22-003/004，检查上述8页请求消费；print_routing令牌提示保留人工查看/复制，不做直接toast后刷新。
- 回归：相邻基线33 passed；新增42项实际回调结合生产api.js执行，覆盖success/业务拒绝/HTTP JSON/非JSON503/401/419/断网、FormData/CSRF/按钮恢复与重试。三个模板字节备份回退HEAD后42 failed，finally恢复后专项及相邻96 passed；日志output/playwright/http_pages_20261022/。
- 组合验收：549文件完整覆盖，首次5121 passed/112 skipped/5个夹具失败；其中旧label反馈夹具缺实际postRaw、旧栏目结构夹具缺document事件接口。分别补齐真实api.js加载和DOM接口后，原断言全部保留，失败项及相邻91 passed；台账/库存文档定位契约32 passed，规则0违规。未重启整套pytest，完整覆盖后只补失败及相邻；不能将首轮描述为直接全绿。
- 最终检查：verify_wms_bugs通过，显式9082隔离库冒烟119/119。其他未提交模块的AI仓库守卫仍在补验收夹具，不混入本项提交。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；生产需重启 WMS 服务生效。验证仅用Node及隔离库，不改生产物料、标签、单据、库存或账号。

### BUG-2026-10-22-006: 期初库存与打印编辑器巨量内联脚本无法独立缓存

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：期初库存和打印编辑器各约1100行业务脚本内联，每次页面重传且难以独立检查；既有测试直接从HTML找函数，拆分必须同步读取实际外链脚本，不能删除断言。
- 修复：两页业务脚本移至static/js/pages/opening-stock.js、print-template-editor.js，保留初始化顺序、全局函数、事件与API。Jinja仅提供数据配置，打印prefix/templateId通过tojson注入。模板分别1450→315、1322→267行，业务段保持等价；两页原已统一WMS.api，不重复迁移。
- 同类点已排查：关联BUG-2026-10-21-016及既有department/employee/warehouse抽离；更新两页专属和共享测试装载入口，保留原业务断言；智能分享验收脚本补ROOT导入路径，CLI及pytest入口均可读取真实外链。
- 回归：修改前核心54 passed，期初库存全模块及打印/共享相邻306 passed；新增6项完整外部脚本初始化运行，覆盖新建/编辑、库位开关、恶意配置、打印加载编辑保存和打印。仅恢复旧两模板时6 failed，finally字节恢复后6项及智能分享5项共11 passed。两份JS node --check通过，549文件统一覆盖无新增业务失败；日志output/playwright/extract-pages-*.log。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；生产需重启 WMS 服务生效。不改期初库存写入、打印内容或生产数据库。

### BUG-2026-10-22-007: 公共栏目设置小屏拥挤、键盘焦点失控且保存排序被旧观察器回滚

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：列设置打开不移焦、Tab可逃到背景、Esc不关闭、关闭不恢复入口；输入和移动按钮名称不足，小屏四列表格挤压。真实浏览器另复现保存新顺序后初始化MutationObserver仍持旧state，自动应用旧顺序。
- 修复：只调整公共栏目组件及样式；移焦/约束Tab/Esc/关闭还焦、可聚焦行选择、输入与移动按钮名称、小屏字段卡片；嵌套Bootstrap弹窗时保持其焦点边界，观察器重读已保存配置后应用。全局导入/查单关闭按钮补名称。确认框原有队列/焦点管理已存在，不重复；cb-doc-nav动态创建且确实使用，不误删CSS。
- 同类点已排查：关联BUG-2026-10-21-016，检查公共confirm/prompt、字段设置、导入和查单关闭入口；不改权限、单据和库存。
- 回归：基线共享/确认54 passed，新增13项Node真实处理器运行，专项及相邻67 passed；字节备份回退旧JS/CSS时13 failed，恢复后通过。完整549文件回归发现旧栏目结构夹具缺document.addEventListener，补DOM接口并保留全部结构断言，失败项及相邻91 passed。
- 浏览器验收：375px隔离静态夹具验证字段卡片、搜索隐藏非命中行、键盘选行重排、保存后持续新顺序、Tab/Esc与还焦；截图output/playwright/accessibility-20261022/field-settings-mobile.png。夹具服务与浏览器标签已关闭。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；整批重启更新静态版本戳后核对app.js/custom.css，不操作生产业务数据。

### BUG-2026-10-22-008: AI完整验收的照片夹具缺仓库且补货阈值说明断言陈旧

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：photo_document_flow夹具不建默认仓，采购/出库确认返回仓库错误后又对空物料解引用；stage3把min_stock说明误断言为安全库存。旧模板回退后两脚本同样失败，属于先前已登记的完整验收缺口。
- 修复：照片和同根因material_category_coding夹具建立两个隔离仓并指定默认仓，强化草稿仓库/完整数量断言和空物料失败报告；补货说明精确断言最低库存100，并增加禁止安全库存混称、在途20/请购10/缺口60断言。没有改业务阈值算法或放宽断言。
- 同类点已排查：关联BUG-2026-10-17-012遗留与BUG-2026-10-22-004；扫描全部AI确认台脚本，补齐分类确认夹具。该夹具缺仓是在010守卫新增后暴露的回归，已修后才允许提交；人工确认、零库存建档、分类、规格和草稿状态原断言保留。
- 回归：原脚本失败证据在multiagent-ai-full.log；两旧脚本现已通过。新增真实子进程验收和阈值误标反例，配合010四场景，旧源码字节备份回退7 failed，finally恢复；专项及确认台相邻40 passed，补分类同类夹具后41 passed。70脚本完整运行69 passed/1分类夹具失败，修正后该完整验收脚本由pytest子进程实际执行通过，不把首轮描述为直接全绿。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；测试仅临时/内存库，无真实AI、微信请求或生产数据操作。生产业务修复随010重启生效。

### BUG-2026-10-22-010: AI拍照确认生成其他入库草稿漏填仓库

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：_ai_create_confirmed_document_draft的other_in直接构造InOrder，绕过其他AI建单入口已有仓库解析，生成warehouse空值的不可完成草稿；完善照片验收夹具和仓库断言后实证发现。
- 修复：该分支复用_ai_resolve_draft_warehouse按源文本/默认仓解析，无法确定则返回既有中文仓库错误；草稿写warehouse.name，人工确认、pending状态、行明细及库存算法不变。修复子项AI-R08-F02-FIX-WAREHOUSE-001，不新增AI能力或路由。
- 同类点已排查：关联BUG-2026-10-17-012 F03。AST核对AI函数直接构造InOrder/OutOrder的三处均写仓库，其他确认链委派原有仓库守卫；未回填历史空仓单据。
- 回归：新增默认仓/指定副仓/多仓无默认/默认仓停用4个实际业务函数场景，修前4 failed；恢复后均通过。验证三仓边界、缺仓不创建单据或行、历史空仓保持、物料库存50与StockTransaction零条不变、数量汇总等于明细。含008新例的字节备份回退7 failed，恢复相邻40 passed；同类分类夹具补齐后41 passed。app.py净行数保持，库存文档定位及台账契约32 passed。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；生产需重启 WMS 服务生效。只在隔离库创建测试草稿，不在生产提交/审批/完成/删除或修改库存和账号。

### BUG-2026-10-22-009: 物料新增单位与供应商下拉直接拼接未转义名称及属性

- 状态：已修复并发布；提交及CI证据见本批发布闭环。
- 根因/危害：单位与供应商联想用innerHTML拼接id、名称、编码、联系人和电话，含引号/标签的数据能形成额外节点或事件属性。
- 修复：7处显示及属性值统一现有escapeHtml，不新增重复全局工具；DOM数据集解码后选择仍填入原名称和ID。正常中文、引号、空值及空列表行为保留，不改变新增/选取接口。
- 同类点已排查：关联BUG-2026-10-21-011/017；检查material_add所有动态下拉与新增单位回显，单位和供应商同类点一起处理。补丁在005请求迁移基础上单独准备并恢复工作区，005CI全绿后才应用，未混同两个atomic action。
- 回归：真实下拉函数结合生产escapeHtml在Node执行，HTMLParser验证恶意img/script不能形成节点或事件、文本与属性完整、点击仍回填原始值，空列表隐藏；新增12项，005基线字节回退后6 failed/6 passed，恢复后新增及005相邻54 passed。补丁及日志output/playwright/material_dropdown_009/，最终整合日志material-dropdown-final.log。
- 生效确认：2026-10-22 11:22代理核验，WMS-Warehouse单次重启后PID1588/Session0，启动版本0ff790e，本机/公网登录GET200，四份变更静态资源HTTP200且与磁盘字节一致；生产需重启 WMS 服务生效。仅Node/HTML夹具，不修改生产单位、供应商、物料或账号。

**2026-10-22 多agent修复发布闭环（005—010）**

- 已推送main：005 `199a5124`（CI39713258636/AI39713258623）；006 `ee977e99`（CI39713972104/AI39713972099）；007 `242a2ebb`（CI39714469141/AI39714469165）；008/010 `e41dbb27`（CI39715431331/AI39715431378）；009 `0ff790e9`（CI39716004085/AI39716004210），均completed/success。Android最近main运行39682360398亦success（51d7fc13），本批无Android改动。005/006/007钩子查询403时先用连接器逐项核实最新三工作流全绿，再仅该次push临时使用钩子已有跳过查询开关；008/009正常push成功。
- 验证只执行一次本地完整pytest覆盖：549文件，5121 passed/112 skipped/5个旧夹具失败；补齐真实请求层/DOM接口并保留原断言，失败及相邻91 passed。AI完整运行70脚本69通过/1分类夹具失败，修正同根因隔离仓夹具后实际子进程及相邻41 passed；三份实际验收脚本均通过。下拉转义及相邻54 passed，隔离冒烟119/119，台账/库存定位32 passed，规则0违规。没有将首轮失败描述为全绿，也未反复全量重跑。
- 生产需重启 WMS 服务生效；已于11:22沿实际WMS-Warehouse入口单次重启，LastTaskResult=0，8080单实例PID1588，未更改生产业务记录、库存、仓库配置或账号。部署后的收尾仅台账和AI归属注释，无功能改动，无需再次重启。
- 遗留工程债：活跃模板仍有152处旧非GET请求调用（含csrfFetch），大页面内联JS、未推广的单据公共CSS及33处需区分确认/刷新语义的原生提示仍需逐页迁移；这些数量不等于功能故障。cb-doc-nav确有动态消费，不能当死代码删除。本批不宣称全部前端问题清零。

### BUG-2026-10-22-011: 采购、调整调拨与委外页面遗留请求及异常反馈不一致

- 状态：已修复并发布。
- 根因/危害：六个活跃页面仍有33处非GET调用分散在fetch/csrfFetch/jQuery；委外多条链缺catch，断网或非JSON响应只产生未处理拒绝；调拨部分jQuery错误分支与统一会话处理脱节。真实运行还发现委外发料/收料的局部location字符串遮蔽浏览器location，成功后reload抛异常。现有base拦截器能补CSRF，不能因此把所有存量调用都误报为必然400。
- 修复：统一走WMS.api.postRaw并保留status完整响应：采购订单/采购申请新增5处、调整/调拨列表12处、委外列表/详情16处。补中文异常反馈，委外两处局部变量改locationValue以恢复成功刷新；表单和原URL编码字段仍用FormData供request.form读取，批删JSON ids经后端核对；人工确认、成功结果人工关闭、延迟刷新、复制重定向、文件清空及失败后重试均保留。GET搜索、后端接口、库存算法及权限不变。
- 同类点已排查：关联BUG-2026-10-21-012/017及BUG-2026-10-22-003/004/005；三个agent按互不重叠页面逐项检查原fetch/csrfFetch和jQuery.ajax/post，排除disabled归档模板；已统一的采购申请详情等不重复迁移。跨组只读复核确认调拨FormData与后端request.form、批删JSON与data.ids消费一致。
- 回归：采购组基线24 passed，新增42项真实回调结合api.js；旧源码回退36 failed/6 passed（取消/空选不发请求），恢复后专项及相邻80 passed。库存列表基线28 passed，新增98项整段脚本及api.js运行；旧源码回退86 failed/12 passed（取消/空选），finally字节恢复后模块及相邻170 passed。委外基线29 passed，新增138项：旧模板129 failed/9取消项通过，单独恢复location命名而保留postRaw时发料/收料成功2例均失败，finally字节恢复后专项及相邻167 passed。规则0违规、verify_wms_bugs通过；显式TEMP隔离库9082冒烟119/119（服务PID5844已关闭）；本轮仅一次本地全量，553文件两片互不重叠并覆盖全集，5417 passed/112 skipped/0 failed（2653+2764通过）；不重复全量。日志output/playwright/frontend-next-20261022-full-part*.log，专项及回退日志purchase_transport_011/、stock-list-012-*.log、subcontract-transport-20261022/。全部回退使用独占文件备份，不用stash；不删弱化旧断言。
- 发布闭环：代码c8ac6d9a432bddbdaa2a2eb5c39aa0a72920780d已推送main且HEAD/origin一致；WMS CI39720042675、AI验证39720042620、性能39720042648均completed/success，Android最近main39682360398成功（本批未改Android）。匿名pre-push查询403时，先通过连接器复核最新三工作流全绿，再仅该次push临时启用已有查询跳过开关，未绕过未知或非绿CI；证据frontend-next-ci-gate-evidence.log。
- 生效确认：2026-10-22 12:07代理核验，生产需重启 WMS 服务生效；已沿核对后的WMS-Warehouse入口单次重启，先核对原PID1588/解释器/命令/启动ticks后停止，再启动新PID12484/Session0，8080单实例，LastTaskResult=0；12:07:12启动日志版本c8ac6d9、production/CSRF on，本机及公网登录GET200且有CSRF字段。db-check migrate=ok为结构核验，不声称执行迁移；WMS_NO_DB_TOUCH=1保留。收尾仅更新发布台账，不再重启。验证只用Node/隔离数据库，生产不提交、审批、完成、删除测试单据，不改业务记录、库存、仓库配置或账号。

### BUG-2026-10-22-012: 入出库详情遗留请求、批删空响应计数及出库粘贴缺路由

- 状态：已修复并发布。
- 根因/危害：入库12处、出库11处非GET仍走csrfFetch，异常反馈各自处理；反提交/粘贴/添加等链缺catch。两页批删在completed++后对null响应取status，再进catch二次计数，导致提前或遗漏最终刷新。出库可见粘贴按钮调用/out_order/<id>/batch_add_items，但路由从未注册，原功能必404；旧审计“0死链”不能替代当前路由核验。
- 修复范围：23调用统一WMS.api.postRaw，保留完整status、JSON/FormData字段、人工确认/取消、表头迭代器转换、两套明细入口、ExcelTable错误恢复及父标签/跨域导航；批删空响应只记一次完成，保留部分成功后的原刷新策略。补出库粘贴草稿端点，整批校验同事务保存，不在前端逐条POST；采购退货/销售来源模式继续要求整单编辑维护来源，不增加库存完成或审批权限。只支持普通领料/其他出库草稿及兼容旧类型；来源头/行均校验。Pydantic校验JSON文本1—500非空行/100000字符、逗号或tab两三列、有限正数量和非负单价；逐行及含旧明细合计精度校验完成才构造ORM行，同事务写入并重算合计，保留原状态和库存流水。销售/采购退货及无权限角色按钮disabled并指引来源维护；格式与限制见docs/OUTBOUND_BATCH_PASTE.md，README已补入口。
- 同类点已排查：关联BUG-2026-10-22-005/011、[10月5日表头FormData回归锁](../../../tests/test_bug_2026_10_05_001_out_order_edit_header_formdata.py)、BUG-2026-09-22-007采购退货来源闸；逐项映射两页23调用及后端协议，GET搜索/AI分析和已统一的完成/force链不改。活跃模板同根双计数仅两详情页，均已修；售后列表finally单点计数不属于此根因，归档模板不改。所有测试使用隔离数据库，生产无测试业务操作。
- 回归：入库基线66 passed，新127项实际回调结合api.js/ExcelTable.saveCell，旧模板回退115 failed/12取消空值passed，finally恢复；专项及相邻初次218 passed/5夹具编码error，后者仅7项模块以UTF8环境重跑全过，合计覆盖223项，未改断言。出库基线61 passed，新增最终121项（105传输/计数、16生产Jinja实际渲染角色×类型门控）；旧103例回退92 failed/11取消空值passed，guard单独回退2 failed，按钮门控单独回退12 failed/4 allowed passed，finally恢复后模块相邻196 passed。后台基线15 passed，新64项真实隔离路由回归全过，旧源码回退64项全部失败（404），finally恢复后原模块和仓库/库存服务等相邻103 passed；覆盖整批拒绝/DB异常回滚、源头及明细保护、三仓/历史空仓、库位/角色/CSRF、数量价与含旧行合计精度、pending及三账不变。初轮新增用例的客户FK、登录g缓存和CSRF签名夹具问题已修正，未放宽断言。台账/库存定位/README契约34 passed；新台账旧二级标题ID引用改用回归锁文件链接定位以保持既有月度统计断言，未改统计基线。规则/历史BUG与隔离冒烟结果见下。全站回归交由本次推送CI执行，避免同一批本地/CI重复全站运行；本地受影响模块全量和相邻回归仍执行。
- 发布闭环：代码6cf984338c3416bc2c42931a81e0077d3bf05508已推送main并核对HEAD/origin相同；WMS CI39730764625（含全站单测/回归/冒烟）、AI39730764705、性能39730764771均completed/success。Android最近main39682360398 success（本批无Android修改）。匿名pre-push查询403后，连接器逐项确认最新三工作流全绿，才仅对该次push临时使用已有跳过查询开关；证据detail-012-ci-gate-evidence.log。
- 生效确认：2026-10-22 13:58代理核验，生产需重启 WMS 服务生效；已沿WMS-Warehouse入口单次重启，停止前核对原PID12484/解释器/命令/启动ticks，现PID6040/Session0、8080单实例，LastTaskResult=0；13:58:24日志版本6cf9843、production/CSRF on，本地/公网登录GET200且有CSRF字段。新批量地址只读GET405验证已注册（自定义错误页不保留Allow头，未将其误作API要求），未在生产调用业务POST。WMS_NO_DB_TOUCH=1保留，db-check migrate=ok仅结构核验，不声称执行迁移；收尾仅台账，不再重启。未修改生产单据、库存、仓库配置、账号或密码。

- 组合验收：verify_wms_bugs通过；显式TEMP隔离库9082冒烟119/119；AI台账一致性通过（41代码标记/118完成记录），未改AI能力/工具/模型/权限/开关/迁移。全量规则0违规；提交钩子0违规，CI全站回归已成功。日志detail-012-bug-check.log、detail-012-smoke.log、in_detail_transport_012/、out-detail-transport-20261022/、out-batch-*.log。

### BUG-2026-10-22-013: 采购申请批删空响应中断汇总及盘点、委外列表请求反馈不一致

- 状态：已修复并发布。
- 根因/危害：采购申请可见批删入口的Promise.all结果对null直接取status，导致汇总抛错；四页25处旧非GET调用（含两段无入口的委外旧绑定）散落在fetch/csrfFetch/jQuery，HTTP异常和会话失效处理不统一，委外部分链缺catch。base拦截器已有CSRF保护，不把旧调用误报为必然400。
- 修复：盘点7处、采购申请6处、委外发料/收料10处统一WMS.api.postRaw，保留完整status、FormData字段和人工确认；采购申请null安全汇总保留部分成功刷新/全失败不刷新、驳回取消及原因原值。删除委外两段无DOM按钮的batchDeleteBtn旧绑定及其中2处请求，不新增按钮，真实公共工具栏仍走原批删端点。委外物料加载校验数组并显示中文失败；该接口仅前1000条辅助缓存，无分页元数据，保留data-ks搜索及后端按编码解析，不冒充全量。
- 同类点已排查：关联BUG-2026-10-22-011/012；追踪实际DOM和app.js公共deleteCurrent，确认委外两页及售后列表的局部旧批删代码没有按钮入口，不能把死处理器当作线上故障。售后本批不改；已统一的完成接口保留，GET、后端、权限和库存算法不变。
- 回归：盘点基线22 passed，新增76 passed，旧模板回退70 failed/6取消空选passed，finally恢复后模块及相邻128 passed。采购申请基线62 passed，新增79 passed，旧模板回退72 failed/7取消空选passed；单独回退null保护3 failed，finally恢复后模块及相邻141 passed。委外基线35 passed，新增112 passed，旧模板回退86 failed/26 passed（原已统一的完成及取消/空输入），finally字节恢复后模块、库位及表单相邻175 passed。新增合计267项，日志check_list_transport_013/、purchase-request-list-20261022/、subcontract-stock-013-*.log；所有回退采用独占文件字节备份，不用stash。交叉只读复核协议和真实入口，无阻塞问题。
- 组合验收：台账/库存文档定位32 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119（服务PID3424已关闭）。全站回归交本次推送CI，不重复本地全站运行；日志list-013-{ledger,rules,bug-check,smoke}.log。本批不新增AI能力或变更AI权限、模型、工具、开关、迁移。
- 发布闭环：代码6886ca36cf91816b632234d27c049468d7751607已正常推送main，读取push输出并核对HEAD/origin一致；WMS CI39734798954（全部单测/回归分片、冒烟、静态检查）、AI39734798995均completed/success；Android最近main39682360398 success，本批未改Android。未绕过CI门禁。
- 生效确认：2026-10-22 14:38代理核验，生产需重启 WMS 服务生效；沿WMS-Warehouse入口单次重启，停止前核对PID6040/解释器/完整命令/启动ticks，现PID17788/Session0，8080单实例、LastTaskResult=0；启动日志版本6886ca3、production/CSRF on、db-check migrate=ok（仅结构核验，不声称迁移）。本机登录GET200含CSRF，公网首次TLS EOF后独立重试GET200含CSRF，未将前次残留响应误作成功。WMS_NO_DB_TOUCH=1保留，收尾仅台账不再重启。测试仅Node真实回调/生产api.js及隔离数据库，生产不做审批、完成、反提交或删除测试，不改业务记录、库存、仓库配置、账号或密码。
- 遗留记录：盘点旧.editBtn弹窗监听无对应按钮，实际编辑入口跳详情页；本批仅兼容旧备注提交协议，不宣称新增可见编辑功能，后续评估清理。剩余请求迁移及其他工程债未在本批宣称清零。

### BUG-2026-10-22-014: 售后复制成功误报失败、采购详情门控及关单取消失效

- 状态：已修复并发布。
- 根因/危害：售后详情复制成功回调参数是data却读取res.msg，必抛ReferenceError并中断导航；采购详情顶部仅admin/warehouse可见，与copy/close/reopen/delete限purchase的后端错位，purchase缺按钮、warehouse点后403，下推卡片也漏角色门控；关单原因prompt的null被||空串吞掉，取消仍可继续关单。五页另有21处旧非GET调用，含工单领料两段/售后列表一段不可达旧处理器，不把它们当现用按钮故障；base已有CSRF保护。
- 修复：售后复制变量与三条链中文异常反馈；采购详情顶部及下推按钮对齐既有后端角色和状态，非admin/purchase页面使用既有body_class opt-out禁用全局写操作栏，warehouse保留本页合法收货/打印；关单原因取消即退出，空串/空白原因原值保留。18处真实请求统一WMS.api.postRaw（采购5/合同5/领料2/售后6），保留完整响应、FormData/JSON协议、人工确认、主资料广播、导入错误展示与刷新/导航时机。3处不可达旧请求随处理器清理，不增加按钮或改公共工具栏端点，领料旧弹窗HTML/其他配置保留。后端、库存、账号权限不变。
- 同类点已排查：关联BUG-2026-10-21-009及BUG-2026-10-22-011/012/013，核对采购详情顶部及下推区、售后列表/详情、合同和领料真实DOM入口与路由，避免把无按钮handler造为测试入口。原完成/继续领料链和GET保留。
- 回归：采购详情基线47 passed；最终新增116项（60实际JS+生产api.js、56真实模板Jinja七角色×四状态×普通/embedded矩阵），旧模板76例回退61 failed/15 passed，独立prompt回退1 failed、独立全局栏opt-out回退16 failed，finally字节恢复。组合168 passed后扩展矩阵56 passed，两者重叠32，合并唯一覆盖192（116新例+76模块相邻），未误加成224。合同/领料基线35 passed，新增87 passed，旧模板回退71 failed/16 passed，恢复后12模块及相邻160 passed；表单、通知、继续领料字段及公共入口交叉只读核对无阻塞。售后基线60 passed、新增70 passed，复制变量独立回退3 failed、旧模板回退63 failed/7 passed，恢复后全售后及出库/委外/忙碌相邻153 passed；两原完成函数文本保持。新增合计273项，日志purchase-detail-014-*.log、contract_requisition_transport_014/、after-sale-transport-20261022/；所有回退均备份并finally恢复，不使用stash、不弱化旧断言。
- 组合验收：台账/库存定位32 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119，服务已关闭；日志round-014-{ledger,rules,bug-check,smoke}.log。R6扫描132活跃顶层模板的252个then(data/res)块并人工核作用域，未确认其他同根变量误用，base嵌套JSON局部变量合法。不重复本地全站运行，完整回归交本批推送CI；无AI能力/权限/模型/工具/开关/迁移变更。
- 发布闭环：代码bcbbf55dc93eb04bc5b0eefaef1088f346689804已推送main，读取push输出并核对HEAD/origin一致；WMS CI39737499162及AI39737499260均completed/success，Android最近main39682360398 success（本轮未改Android）。匿名pre-push查询403后，连接器核实三工作流最近main全绿，才仅该次push临时使用已有查询跳过开关；证据round-014-ci-gate-evidence.log。
- 生效确认：2026-10-22 15:04代理核验，生产需重启 WMS 服务生效；核对原PID17788/解释器/完整命令/启动ticks及WMS-Warehouse任务入口后单次重启，现PID16668/Session0、8080单实例、LastTaskResult=0；启动版本bcbbf55、production/CSRF on，本机及公网登录GET200含CSRF。db-check migrate=ok仅结构核验，不声称执行迁移，WMS_NO_DB_TOUCH=1保留；收尾仅台账，不再重启。所有业务测试仅隔离数据库，生产不做测试单据创建、完成、审批、反提交、删除，不改库存、仓库配置、用户或密码。本轮解决明确问题和五页迁移，其他前端工程债未宣称全部清零。

### BUG-2026-10-22-015: 入库批量导出误解析JSON及打印模板、审批错误反馈缺失

- 状态：已修复并发布；多单合并打印未实现，前端已明确单张限制。
- 根因/危害：入库列表批量导出实际返回xlsx却调用json，必报解析失败；原批量打印只toast/刷新而不消费redirect，后端也仅返回首张。打印中心仅r.ok即刷新，业务拒绝/登录HTML200被误作成功，其他失败无提示；审批两链无catch。独立入出库打印模板页自行处理HTTP，部分失败丢服务端原因，空name File对象能绕过无文件检查；这些独立页不加载base，原有csrfHeaders确实带token，不能误报必400。
- 修复：统一JSON请求为WMS.api.postRaw，独立模板页在业务脚本前加载本地版本化api.js。统一层新增postResponse共用CSRF/同源凭据/HTTP及401419闸，成功返回未消费Response；入库导出核对xlsx MIME并使用既有文件名/Blob下载工具，JSON业务错误和HTML不下载。打印入口明确「打印已选（单张）」、多选提示不请求、单选消费原redirect；多单合并打印仍未实现，不把首张冒充全量。中心/审批及模板页补业务判定、中文错误、按钮/文件重试，保留人工确认和原成功提示时机。出库无入口copyOutOrder死函数清理，不造按钮。README及docs/INBOUND_LIST_EXPORT_PRINT.md说明使用和限制；后台、打印内容、库存/账号权限不变。
- 同类点已排查：关联BUG-2026-10-22-011/012/013/014及既有入库页面审计回归；追踪六页实际DOM、公共工具栏和响应协议，不能以旧调用计数代替故障数量。18旧调用含1死请求；入库公共批操作函数拆JSON/下载协议，新增分支不重复算旧调用。
- 回归：统一请求层基线297 passed/21 skipped，新36 passed；旧API字节备份回退24 failed/12原JSON模式passed，finally恢复后333 passed/21 skipped。打印模板基线25 passed，新73 passed，旧模板回退69 failed/4取消passed，finally恢复后全打印模板及内置Excel相邻170 passed。打印中心/审批基线36 passed、新50 passed（含2个不依赖请求头断言的业务拒绝误刷新锁），旧模板回退46 failed/4取消空原因passed，恢复后模块及相邻89 passed；既有反馈测试只扩approval真实api加载条件，未改断言。入出列表基线38 passed，新152项，旧模板回退128 failed/24取消空值passed，finally字节恢复；真实downloadBlob/文件名辅助函数执行、字节匹配并openpyxl读回Excel，单张/多选打印、无效MIME、JSON/HTML200拒绝下载均覆盖，模块及指定页面审计/工具栏/批量完成边界等8模块相邻230 passed（4 warnings/39.34s，退出0；原始正常输出在agent工具会话40047，未伪造落盘日志）。新增合计311项；日志response-015-*.log、order-print-template-015-*.log、print-approval-transport-20261022/、in_out_list_transport_015/。不使用stash、不弱化既有断言；全站测试交推送CI，不重复本地全站。
- 组合验收：台账/库存定位/README契约34 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119（服务已关闭），日志round-015-{ledger,rules,bug-check,smoke}.log。只读交叉复核API未消费响应正文、下载/打印和独立页版本化加载无阻塞；R6筛查其余活跃模板未确认同类仅凭HTTP ok误刷新的消费点，候选均为GET或已有业务状态校验。
- 发布闭环：代码acdef2c871c8d6ad077aee1c161fcf84ebf4726e已正常推送main，读取push输出并核对HEAD/origin相同；WMS CI39746109489及AI39746109309均completed/success，Android最近main39682360398 success（本批未改Android）。未绕过门禁。
- 生效确认：2026-10-22 16:19代理核验，生产需重启 WMS 服务生效；核对原PID16668/解释器/完整命令/启动ticks与任务入口后沿WMS-Warehouse单次重启，现PID1096/Session0、8080单实例、LastTaskResult=0；启动版本acdef2c、production/CSRF on，本机/公网登录GET200含CSRF，api.js GET200且SHA256字节与磁盘一致。WMS_NO_DB_TOUCH=1保留，db-check migrate=ok仅结构核验，不声称迁移；收尾仅台账不再次重启。业务验证只用Node及隔离数据库，不在生产创建、完成、审批、反提交、删除测试单据，不改仓库、库存、打印机配置、账号或密码。

### BUG-2026-10-22-016: 纯台账反复触发全套CI且旧绿未绑定目标提交

- 状态：已修复并验收；真实台账提交的轻量CI路径已通过。
- 根因/危害：CI与AI每次main push都跑全套，功能提交验收后补台账又重复全量；门禁只检查各工作流最近success，没有要求WMS CI/AI匹配目标SHA，不能明确证明当前基线已验收。旧“开任何任务前不得有pending”把只读准备也串行化；生产与开发共用目录，直接放开跨批写代码会把未提交文件混入发布。
- 修复：白名单README、docs/ledger和docs/audit Markdown只有在main push、完整Git差异且紧邻base的CI/AI最近记录均成功时才走docs分支；未知、失败、排队或无证据一律全量。required工作流仍触发，明确聚合所选docs或full分支，原全量步骤/分片和每日定时保留；perf仍为告警观测。SHA门禁绑定远端main基线，发布可显式指定完整SHA，Android旧绿须证明祖先关系及工程/构建工作流无变化。403/网络标未核实并阻断，不误作已确认红灯；保留连接器替代证据流程。DEVELOPMENT_RULES、README及docs/CI_VALIDATION_POLICY.md更新验证边界，AGENTS按硬规则另作独立atomic action同步，只放开只读准备、不开放混合发布写入。
- 同类点已排查：关联既有CI门禁、F2.8 pre-push、F3.16并发取消与2026-09-24性能契约，核对三个main门禁和可选性能工作流、主规则/开发规范/README、GitHub API参数与钩子实际stdin。Android已有路径触发不重复开发；不使用paths-ignore使required工作流消失，不允许仅改规则文本绕过代码要求。
- 回归：旧门禁基线16 passed/3 Windows条件skip，新增46通过，旧checker/hook回退40 failed/6 passed，finally恢复后6模块97 passed/4 skipped；真实Git Bash执行覆盖远端SHA、CRLF和无更新，编译检查通过。旧工作流相关58 passed/4 skipped，新增62通过，旧workflow回退59 failed/3原fulljob快照passed，恢复后120 passed/4 skipped；12个原fulljob payload保持，perf advisory失败仅告警。classifier基线14 passed/1 skipped，初80通过，删除新脚本反证5 failed/75 errors并字节恢复，7模块220 passed/3 skipped；终审再补未知身份拒绝、分页去重和main suffix合法形态12锁，最终92通过，独立回退8 failed/4 passed，finally恢复后三个必要新模块合计200 passed（包含92/62/46，不重复相加）。交叉只读审查无剩余阻塞。日志ci_gate_target_sha_016/、ci-docs-mode-20261022/、ci-scope-016-*.log。不用stash、不弱化旧业务断言；旧并行结构测试改为仅依赖changes且彼此不串联，原步骤/分片断言保留。
- 组合验收：轻量docs的--noconftest三模块34 passed，严格AI台账41标记/118完成一致，源码编码通过、规则default 0违规/full-gate 0新增、既有BUG检查通过；日志ci-policy-016-*.log。未跑本地重复全站，配置改动由本次CI原全量实证，再用真实文档收尾提交验证轻量路线。
- 发布验证：实现ec4aa7e738bbe7b509f5d3c67c73601047d812fb已推送main，WMS CI39753029216、AI39753029205均completed/success；实际9个CI全量任务成功、docs-checks跳过、最终gate成功。AGENTS按单文件独立提交0dced608d2c206266623d54a2192f34d84a7af3d并正常推送，相关契约50 passed/3 skipped，WMS CI39754273038、AI39754273078、性能39754272979均completed/success。两次均读取实际push输出并核对HEAD/origin一致。Android最近main39682360398 success，复用前证明其SHA为目标祖先且Android工程及构建工作流无变化。下一次只修改本台账，以实际工作流选择验收轻量路线。
- 真实轻量路径验收：单台账提交e10dccac6e4d8b81ef339e7ebdac79ffccdfa31e正常推送并核对HEAD/origin一致；紧邻基线为已全绿的0dced608。WMS CI39756083338、AI39756083308、性能39756083352均completed/success。逐项读取jobs与steps：CI的changes、docs-checks及gate成功，原9个全量任务按分级跳过，文档契约、gitleaks、规则均实际成功；AI严格台账及编码成功、原2个全量任务跳过、gate成功；性能docs-skip及gate成功、原perf跳过。本地对应34项契约通过。按GitHub created_at到updated_at计，此次WMS CI76秒，相邻AGENTS全量196秒（减少约61%）；AI32秒，实现提交全量69秒。此为本次实测，含排队/启动时间，不承诺每次相同比例。
- 生效确认：2026-10-22代理根据GitHub实际运行及任务结果确认CI分级生效，代码/规则提交保持全量、白名单文档走轻量，等待期间可只读准备下一批；目标SHA及Android复用证明仍强制。收尾仅记录上述已完成证据，不再无限补写自身提交CI记录。本项仅CI/开发规则与测试，不改WMS业务代码、生产服务、数据库、打印机、仓库、库存或账号，不需重启WMS。当前生产业务版本仍acdef2c。

### BUG-2026-10-22-017: 期初预检换文件竞态、重复确认及预警写按钮权限错位

- 状态：已修复并发布。
- 根因/危害：期初预检进行中隐藏preview，文件change仅在preview可见时重置，旧A回包能恢复确认并实际上传新B；真实确认按钮不是submit，原链仅禁用隐藏submit，重复点击可多次生成期初单并合并累加。预检失败消息直接拼HTML；预警写按钮对所有角色可见，后端仅admin/warehouse有权操作，两页共4个活跃旧POST。
- 修复范围：批量导入2个POST统一WMS.api.postRaw；File对象身份与请求代次双校验，换文件/取消/重预检立即失效，旧成功/失败回包不恢复状态；确认和submit双守卫，每form忙锁覆盖预览实际按钮、文件及预检，先捕获FormData再禁file，失败finally恢复且不自动重发。预检错误消息转义；确认资格和数量改用后端整文件imported/skipped，预览截断明确仍处理全文件，前500行都坏但后续合法仍可确认，零可导入无确认。全局导入helper仅期初跳集中预检页，保留embedded与其他模块原行为，堵住新增/详情入口绕过。预警两旧POST入口统一postRaw helper，admin/warehouse才渲染2个阈值字段及2写按钮，确认至成功700ms刷新期间互斥，取消/失败恢复。README记录入口、截断范围及网络结果不确定时先核对单据再人工决定重试；不改变导入后台、库存算法或账号权限。
- 同类点已排查：关联BUG-2026-10-21-017的预检失败转义遗漏及BUG-2026-10-22-011至015的请求迁移；核对真实DOM、两段式dry_run与正式导入、FormData、预警后端角色及公共工具栏，不把已有CSRF/catch误报为普遍缺失。全局helper在期初新增/详情确实可绕过，已收口；alert不匹配全局模块，无需虚构第二写入口。后端rows[:500]仅预览，imported为全集；保留逐行部分成功/每次新单/跨单据累加口径，不把已有量误作覆盖。
- 回归：导入基线84 passed，新40项真实整段JS及生产api.js通过；旧模板回退39 failed/1空文件对照passed，仅撤销错误转义单独3 failed/37 deselected，均finally字节恢复，模块及相邻187 passed（64既有SQLAlchemy弃用warning，39.67秒）。预警基线21 passed、新32通过（8角色真实Jinja及24真实DOM/API场景），旧模板回退28 failed/4 passed，finally恢复后8模块65 passed。全局导入基线17 passed、新21通过，旧源码回退12 failed/9 passed，finally字节恢复后模块相邻42 passed；覆盖add/detail/line/list及普通/URL和body embedded，其他模块原弹窗成功/空文件/网络行为不变。新增合计93项，不把相邻重叠或原有对照重复计入。日志batch-import-20261022/、alert_transport_017/、opening-import-route-*.log。未使用stash、未放宽旧断言；全站测试交本次推送CI，不重复本地全站。
- 组合验收：台账/README及库存定位契约34 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119，服务PID13756已核对身份并关闭；日志frontend-017-*.log。只读交叉review无阻塞，后端、库存写入/仓库归属算法未改，既有预检多仓与导入相邻回归保留。不新增AI能力或改变AI模型/工具/权限/开关/迁移。不在生产执行导入或修改预警值。
- 发布闭环：代码21f81e20ea32b50e55fcba97ba75cb5b578b1ef6已正常推送main，读取实际push输出且HEAD/origin一致；WMS CI39762486353（原全量任务及冒烟）、AI39762486062、性能39762486036均completed/success。目标SHA门禁通过，Android最近main39682360398 success且祖先及工程/构建工作流未变证明通过。未绕过CI门禁；收尾台账按BUG-2026-10-22-016轻量规则验收，不重复本地全站。
- 生效确认：2026-10-22 18:25代理核验，生产需重启 WMS 服务生效；核对原PID1096的解释器/命令/Session0/创建时间、8080唯一listener及WMS-Warehouse任务入口后单次实际重启。首次Stop-Process报对象错误，现场复查仍原PID且登录200，未误报已停；复核身份后CIM Terminate返回0，沿原计划任务拉起新PID4316/Session0，8080单实例、LastTaskResult=0。日志18:25:24版本21f81e2、production/CSRF on、db-check migrate=ok（仅结构核验，不声称迁移），WMS_NO_DB_TOUCH=1保留。本机登录GET200含CSRF，公网首次TLS EOF后独立重试GET200含CSRF；app.js GET下载与磁盘SHA256字节一致。收尾仅台账，不再次重启；所有业务测试在隔离数据库，不在生产创建、修改、完成或删除测试单据，不改仓库、库存、预警阈值或账号密码。网络丢响应后的人工重试仍须先查单，不把前端防连点声称为服务端幂等。

### BUG-2026-10-22-018: 账号及个人资料页面异常反馈与提交状态缺口

- 状态：已修复并发布。
- 根因/危害：个人资料网络异常/null回包可使页面停在正在保存；改密链未处理网络、非JSON和null，且仅看业务status可把HTTP失败误报成功。用户编辑catch丢失后端拒绝原因；账号新增/编辑/状态/重置及资料/改密共6个活跃旧POST无提交忙锁，可重复派发。base已有CSRF及全局异常兜底，不误报全部请求无保护。
- 修复：三页6旧POST统一WMS.api.postRaw，保留资料email/phone/bio、改密三密码字段、用户新增/编辑/重置FormData和启停JSON原值及XHR头。用户操作在确认/请求/成功刷新窗口互斥，失败或取消恢复，编辑保留原立即刷新，其余650ms；个人资料和改密异常转为页面文字提示并恢复提交状态，改密仅HTTP及业务成功才导航，成功导航前保持锁。财务资料字段只读且不显示保存，保留修改本人密码入口，对齐既有后台只读策略。重置弹窗每次人工打开清空新密码和管理员确认输入，避免目标间串用。保留人工确认、管理员二次校验及强制改密规则，不改后台认证/授权或真实账号密码。
- 同类点已排查：关联BUG-2026-10-22-011至017，核对真实DOM、后端JSON/FormData协议、资料XHR判断与401/419统一层；三页均不匹配全局模块，无需重复实现删除或添加工具栏optout。禁止自重置/禁用本人、最后管理员保护、密码原值不trim继续保留。全局强制改密中间件对FormData XHR仍可能302至改密HTML，属于全局错误协商的独立候选，本批不改该规则或宣称已修；统一层对HTML回包报失败，不误作保存成功。
- 回归：用户页原4模块基线30 passed，新增58项真实DOM及生产api.js回调全过，旧模板回退58 failed，独立撤销密码输入清空3 failed/55 deselected，均finally字节一致恢复；最终6模块及相邻93 passed（29.12秒）。资料/改密基线9 passed，新增32 passed（24实际回调及8角色Jinja），旧模板回退25 failed/7非finance角色原对照passed，finally字节一致恢复；受影响及强制改密/财务只读相邻最终58 passed（20.29秒）。覆盖业务拒绝、HTTP失败携success包、null/非JSON/HTML200、断网、401/419、人工确认/取消、重试、成功刷新/导航前重复派发、原FormData及密码空白、XHR、重置目标切换。新增合计90，不把相邻重复计入。日志user_transport_018/、profile-transport-20261022/；不使用stash、不放宽旧断言，只用模拟网络和隔离数据库。
- 组合验收：台账/库存定位及README契约34 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119，PID5044身份核对后已关闭；日志frontend-018-*.log。交叉只读复核三页字段/权限/确认及状态无阻塞；后台未变，不新增AI能力/模型/工具/权限/开关/迁移，全站回归交本次代码提交CI、不重复本地全站。不对生产账号执行新增、编辑、禁用、重置或改密。
- 发布闭环：代码500b6d109abc0df346640ce72645b12e5234a049已正常推送main，读取push输出且HEAD/origin一致；WMS CI39770306136（完整全量分片/冒烟）、AI39770306138均completed/success。Android最近main39682360398 success，已用本地Git证明为目标祖先且Android工程/构建工作流未变。发布查询遇匿名403，连接器逐项核实最新三工作流完整SHA/状态/链接并记录frontend-018-ci-alternate-evidence.json，git ls-remote再次核对目标main；未将限流误报失败或绿灯。收尾只改台账，走已验收的文档轻量路径。
- 生效确认：2026-10-22 19:29代理核验，生产需重启 WMS 服务生效；核对PID4316的解释器/命令/Session0/创建时间、8080唯一listener、main目标及无混合代码写入，沿WMS-Warehouse原任务单次重启，现PID14556/Session0，8080单实例、LastTaskResult=0。启动日志19:29:21版本500b6d1、production/CSRF on、db-check migrate=ok（仅结构核验，不声称执行迁移）；本机/公网登录GET200且含CSRF。WMS_NO_DB_TOUCH=1保留，收尾不再次重启。本批只发布页面代码，未在生产创建/编辑/禁用/重置/改密任何账号，不改仓库、库存或真实密码；所有账号回归仅隔离夹具和模拟网络。

### BUG-2026-10-22-019: 微信强制发送入口误导及下推失败重试可能重复建草稿

- 状态：已修复并发布。
- 根因/危害：微信“重新生成今日图片”实际会再次投递且绕过当日去重，普通/强制执行缺人工发送确认及忙锁；run/resend业务拒绝仍刷新，success信封不等于实际发送成功。入库下推每次点击新request_id，首请求已提交但响应丢失、剩余数量足够时，人工重试可能再建草稿。两页5个活跃旧POST，已有CSRF/部分确认与异常处理，不能误报全链缺保护。
- 修复：两页5旧POST统一WMS.api.postRaw。微信写操作统一确认/请求/人工关闭结果/成功刷新互斥，失败和取消恢复，保留save完整FormData、run force=1、resend无body及clear状态字段；普通/强制执行明确人工发送确认，force按钮改为重新生成并再次发送，业务拒绝不刷新；run skipped单独反馈不误报发送，处理完成明确须看分享记录，resend补实际log_status标签而不把success信封当投递成功。入库下推使用不含request_id的完整payload JSON作Map key，失败保留每个内容对应编号，A→B→A也复用A，筛选不改变内容编号；载荷及UUID构建放入try，异常可见且恢复，不自动重发，成功保持锁至原导航。密码/库存/下推后台及发送算法不变；README注明发送语义与页面内保护边界，刷新或关闭页面后不保证编号继续保留，结果不确定须先查草稿。
- 同类点已排查：关联BUG-2026-10-22-011至018及既有自动下推有效关联修复；后台重放按actor/source/request_id且不比较payload，前端不可拿同一ID发送修改后的内容。全仓create_in_order_push前端仅此页，自动下推有独立有效关联闸，不属于手工重试根因；微信两种run均真实投递，重发success仍可log_status failed/pending，均核对对应路由语义。无新后台或生产动作，不在生产发送微信、改分享配置或创建下推草稿。
- 回归：微信基线17 passed，新增58真实DOM及生产api.js回调通过，与旧反馈26合并84 passed；旧模板回退58 failed，finally字节一致恢复后6模块及相邻101 passed（3既有SQLAlchemy warning，24.48秒）。旧test_page_feedback_runtime仅wechat加载真实helper/API及空buttons NodeList，保留全部原断言，其他页夹具不变。下推基线14 passed、新50通过，旧模板回退49 failed/1空选对照passed，finally字节一致恢复后模块及相邻64 passed（8既有弃用warning，13.73秒）；丢响应及A/B/A核心锁不依赖请求头断言，使用模拟重放端证明同内容只创建一次，覆盖三目标、原字段、数量/顺序、筛选、null/非JSON/HTTP/401419/network及UUID/构造异常恢复。新增合计108，不重复计入相邻或旧对照。日志wechat_share_transport_019/、in-push-20261022/。不用stash、不放宽旧断言，不在生产发送或写业务。
- 组合验收：台账/README及库存定位契约34 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119（脚本仅GET微信配置页，无发送/下推POST），PID17980身份核对后已关闭；日志frontend-019-*.log。交叉只读审核两页无阻塞，不新增AI能力/模型/工具/权限/开关/迁移，后台不变；全站回归交本次代码提交CI，不重复本地全站。开工基线4d995946三CI已全绿，等待上一批CI期间仅只读准备，本批写入在闭环后解锁。
- 发布闭环：代码a9cedd6f1737770ff322636ac5718f58eb999cde已推送main，读取push输出并核对HEAD/origin相同；WMS CI39772308163（原完整全量任务及冒烟）、AI39772308158、性能39772308072均completed/success。Android最近main39682360398 success，Git祖先和Android工程/构建工作流未变证明通过。匿名pre-push查询403后，连接器核实同一基线4d995946最新三工作流全绿并记录frontend-019-push-gate-evidence.json，才单次临时使用已有查询跳过开关；发布目标再次逐项核实并记录frontend-019-deploy-gate-evidence.json，未把403当工作流失败或自动放行。收尾仅台账走轻量CI，不重复业务全量。
- 生效确认：2026-10-22 19:44代理核验，生产需重启 WMS 服务生效；核对原PID14556的解释器/命令/Session0/创建时间、8080唯一listener、目标main及无混合修改，沿原WMS-Warehouse任务单次重启，现PID17092/Session0，8080单实例、LastTaskResult=0；19:44:05启动日志版本a9cedd6、production/CSRF on、db-check migrate=ok（仅结构核验，不声称迁移）。本机/公网登录GET200且含CSRF，WMS_NO_DB_TOUCH=1保留；收尾仅台账不再次重启。只发布页面代码，无真实微信发送、分享配置/接收人修改或生产下推草稿，不改真实单据、仓库、库存、账号或密码。编号复用限当前页面，刷新/关闭后的不确定结果仍须人工先查单。

### BUG-2026-10-22-020: 公共单据动作状态与售后保存库位载荷缺口

- 状态：已修复并发布；遗留子项U1由BUG-2026-10-23-001补齐，发布生效见该条。
- 根因/危害：公共单据模板3旧POST只解析JSON不验证HTTP，“仍要完成”独立runComplete无catch/互斥；保存已有pending锁但成功导航前可提前释放，反提交也可重复派发。调拨/盘点/领料写按钮只按单据状态，未对齐后台角色，BOM已有门控需保持。售后保存漏JSON.location，启用库位时用户已填写仍被后端拒绝，且无提交忙锁/HTTP闸及null防护。共两活跃模板4旧POST；不将已有CSRF或部分锁误报为全无。
- 修复：公共模板3POST统一WMS.api.postRaw并保留success/confirm信封；保存/完成/force/反提交共享请求锁，成功导航期持续锁定，独立runComplete内部catch覆盖人工force失败，失败恢复且不自动重发。保留风险二次人工确认、force布尔、保存回填order_id、领料完成后继续新增及携带字段。四类权限按现有后台收口：BOM/领料admin+production、调拨/盘点admin+warehouse；无权限只读并禁全局写工具栏，授权已完成单反提交仍保留。售后1POST统一postRaw，补可选DOM.location原值（关闭时空串），保留新增/编辑及来源/头行字段；同步锁至400ms导航，失败恢复/null安全；admin/warehouse保留原全局栏与保存，其他角色禁编辑/隐藏保存及全局写栏。后台库存/认证算法不改。
- 同类点已排查：关联BUG-2026-10-22-011至019及[历史库位必填消费点遗漏](history-2026-08.md)；按真实DOM/路由核对，不把采购选单无调用旧函数当活跃故障，in_order_add及其采购测试本批不动。入/出库新增已有location载荷，领料列表旧弹窗及委外收料用完整FormData；盘点传行级area，调拨from_location/to_location实际为仓库名称，不能误补库位。保存回填order_id后重试为更新，不误报必然新建。
- 遗留子项U1：公共领料表单缺库位DOM、header及渲染上下文支持，后台开启管理时会要求location，属于独立完整入口能力缺口，不能把本次售后漏字段修复声称已覆盖。2026-10-22以SQLite URI mode=ro及query_only只查生产location_management_enabled，现场值为0。2026-10-23由BUG-2026-10-23-001补齐整链及开关/多仓回归，未开启生产开关或自动回填。采购无调用旧函数及旧测试契约亦留后续独立清理。
- 回归：公共表单基线112 passed，新增120 passed（64实际Jinja角色/状态、56真实DOM+生产API），旧模板回退91 failed/29原对照passed；仅撤内部force catch保持迁移/互斥时，HTTP非JSON/200HTML/null/断网4例全失败，finally字节一致恢复。最终模块及相邻293 passed（21既有SQLAlchemy warning，44.82秒）；保留全部原96导航矩阵和字段/零价断言，旧2fixture仅接生产API/helper、HTTP响应元数据与合法production角色上下文，未删断言。售后基线34 passed，新57通过（16Jinja、40实际新增编辑/库位/请求、1真实全局栏）；与原17校验74 passed，旧模板回退53 failed/4原校验拦截passed，finally恢复后8模块及相邻115 passed（23既有warning，30.33秒）。旧静态校验仅请求锚点fetch等价改postRaw，收集/展示/return顺序断言保留。新增合计177，不重复计算相邻与原对照；日志shared-document-20261022/、after_sale_entry_transport_020/。不用stash、不放宽原业务断言，不在生产保存、完成或反提交单据。
- 组合验收：台账/库存定位契约34 passed，规则0违规、verify_wms_bugs通过，显式TEMP隔离库9082冒烟119/119，PID3884核对身份后关闭；日志frontend-020-*.log。两页交叉只读复核无阻塞，无AI能力/模型/工具/权限/开关/迁移变更，全站回归交本次代码提交CI，不重复本地全站。
- 发布闭环：代码d4a23ae098c2f87a0d6915640d177e4877f7a6a5已正常推送main，读取实际push输出且HEAD/origin相同；WMS CI39777016981（全部原全量任务及冒烟）、AI39777017027均completed/success。Android最近main39682360398 success，列表首100项没有Android后继续翻第二页找到最新记录，Git祖先及Android工程/构建工作流未变证明通过。发布时匿名查询403，连接器逐项核实同一目标最新记录，证据frontend-020-ci-alternate-evidence.json；不把限流当红灯或自动放行。收尾只改台账走轻量CI。
- 生效确认：2026-10-22 20:20代理核验，生产需重启 WMS 服务生效；核对原PID17092的解释器/命令/Session0/创建时间、8080单实例、目标main及无混合修改后，沿原WMS-Warehouse任务单次重启。现PID11752/Session0，8080唯一listener、LastTaskResult=0；20:20:56启动日志版本d4a23ae、production/CSRF on、db-check migrate=ok（仅结构核验，不声称执行迁移）。本机/公网登录GET200含CSRF，WMS_NO_DB_TOUCH=1保留，收尾不再重启。业务回归全部隔离，不在生产保存/完成/强制完成/反提交单据，不改真实库存、仓库、库位开关、账号或密码；生产仅曾只读核对库位开关。


### BUG-2026-10-23-001: 生产领料主表单缺库位入口及继续新增丢失库位

- 状态：已修复并发布。
- 根因/危害：BUG-2026-10-22-020遗留U1；后台保存与完成已有库位必填校验，但公共领料表单缺DOM、collectHeader及渲染上下文，开启管理后无法从主入口正常填写；表单和列表继续新增都未携带库位，普通编辑亦可能将历史值清空。不能把已有列表旧弹窗或售后漏字段修复当成主表单已支持。
- 修复：仅领料新增启用时required/maxlength=100库位输入及关闭时hidden历史原值；保存载荷补location，启用时空值在发请求前反馈。切换仓库实际值才清空旧库位，初始化/同仓刷新保留原值，只读不绑定清空；仓库主资料刷新实际改选触发同样联动。服务端渲染传开关与原单值，新建query白名单接受trim后最多100字location，编辑/查看忽略query。两处人工完成成功后的继续新增携带库位，失败/取消不继续；现有角色、互斥、人工force、order_id及导航策略保留。不改后台校验、库存算法、schema或默认库位，不使用仓库地址充当库位。
- 同类点已排查：检索月度/历史库位必填消费点及既有继续领料实现，延伸原入口而非另造功能；核对主表单、列表、save_table、complete及production_requisition别名。入出库等已有入口不重复改造，BOM/盘点/调拨头字段不变。2026-10-23再次以SQLite URI mode=ro/query_only只查生产location_management_enabled，仍为0，未开启或回填。采购旧无调用函数及其他工程债不宣称本批解决。
- 回归：渲染基线14 passed，新20项真实Flask GET/Jinja通过；仅旧_render_requisition_form函数字节回退20 failed，finally恢复，最终4模块及相邻42 passed。整链基线32 passed，新6项真实HTML字段→Node collectHeader→Flask save/edit/complete通过；VM注入HEAD旧collectHeader反证4 failed/2原后端拒绝对照passed，finally仅恢复专属测试文件字节，产品不动；最终4模块38 passed。覆盖两仓同名库位与另一库位扣减隔离、开启时总账=库位全集=流水及仓库分项、缺库位零写入、关闭时历史空串及非空值回显保存、关闭时总账=流水。fixture传None经模型default实际落库空串，显式断言，不声称存在NULL存量。前端基线248 passed，新30项实际Jinja/整段JS及生产API通过；旧两模板回退30 failed，单独撤warehouse绑定4 failed/26 deselected，finally字节恢复；最终模块及相邻278 passed。原96导航矩阵及旧断言保留，两个抽函数fixture仅补新const=false。新增合计56项，不叠加相邻重复计数。所有测试仅隔离库，不在生产保存或完成测试单。
- 基线CI：开工发现a1c3a160的Android日常运行39860469109初次失败，单测PendingQueueRebuildProtectionTest在重建前打开临时SQLite时SQLITE_IOERR_SHORT_READ。历史已有同模式偶发记录，未据单次错误改Android或放宽断言；仅重跑失败job120109554651一次，attempt2完成成功，新job120162056457日志80 PASSED、BUILD SUCCESSFUL。WMS CI39860513347及AI39860552246同SHA成功，目标门禁exit0后才解锁本批写入；不宣称SQLite根因已解决。证据output/playwright/frontend-021-baseline-gate.log。
- 组合验收：台账/README/库存定位契约34 passed；渲染新增行导致引用漂移，清理函数后4个冗余空行保持既有库存文档引用准确，未更改断言或库存口径。verify_wms_bugs通过；显式TEMP隔离库9082冒烟119/119，服务已通过工具进程会话Ctrl-C结束且9082无listener。后台Start-Process启动遭自动审批拦截，改用受工具管理前台进程完成隔离冒烟，无绕过权限。最终规则0违规，提交钩子0违规。日志requisition_location_u1/、requisition-location-20261023/、requisition-location-u1-*.log及frontend-20261023-001-{ledger,bug-check,smoke}.log。无AI能力/模型/工具/权限/开关/迁移变更，全站回归交推送CI，不重复本地全站。
- 发布闭环：代码520ca965f11734952c374d1ddb5c6e300c61cbaf已正常推送main，读取实际push输出且HEAD/origin相同；WMS CI39877975706全部原单测/回归分片、规则和冒烟成功，AI39877975724及性能39877975687均completed/success。严格目标SHA门禁exit0；Android最近main39860469109 attempt2成功，Git祖先和Android源码/构建工作流未变证明通过，未跳过门禁。Android偶发SQLite问题仅重跑恢复，未宣称根治。收尾仅此台账文档，按已验收轻量CI路径核对。
- 生效确认：2026-10-23 08:29代理核验，生产需重启 WMS 服务生效；先核对11752进程完整命令/解释器/Session0/创建时间、8080单实例、main目标及tracked工作区无混合代码，CIM Terminate返回0后沿原WMS-Warehouse计划任务单次重启。现PID16080/Session0，8080唯一listener、LastTaskResult=0；08:29:42启动日志版本520ca96、production/CSRF on，db-check migrate=ok仅结构核验，不声称执行迁移。本机/公网登录GET200均含CSRF，WMS_NO_DB_TOUCH=1保留。生产库位管理保持关闭；未在生产创建、保存、完成或反提交测试单，不改真实库存、仓库、库位开关、账号或密码。收尾仅台账，不再次重启。

### BUG-2026-10-23-002: 销售录单及采购申请详情HTTP状态与成功导航期间忙锁缺口

- 状态：已修复并发布。
- 根因/危害：五活跃页面及公共导入入口共八处旧csrfFetch POST未统一HTTP失败判定，错误HTTP携带success信封可误作成功；销售新增/编辑403被误报登录过期，null解引用产生技术错误。原链已有CSRF与部分catch，不能误报普遍无保护。销售保存、导入及选择出库缺请求/成功导航期互斥，采购申请审批/反审/生成采购单无锁，已有驳回/完成按独立key锁且650ms刷新前已释放，允许交叉操作或重复派发。
- 同类点已排查：关联BUG-2026-10-22-011至020及BUG-2026-10-23-001；核对sales_order_add/edit/list、sales_outbound_selection及purchase_request_detail实际DOM、JSON/FormData与对应路由。旧记录对采购申请详情“已统一”的描述只涵盖部分链，本次仍有三处旧POST，不能据概括跳过。公共列表委托、GET搜索、已统一驳回/完成请求不重复迁移；库存、来源数量、角色及人工确认策略保持。追加核对发现app.js公共导入在销售新增/详情仍可用，同根入口一并纳入；其所有模块消费共用修复，期初最前分支继续跳预检页，不能绕过。
- 修复：八处旧POST统一WMS.api.postRaw，保留整单采购无body、选行采购JSON原字符串ID/数量、销售保存原表头/行JSON及零价/税率、两类导入FormData文件和统一XHR。销售DOM保存/保存并新增/全局保存共享锁，含库存警告3000ms和原跳转；导入保留900ms刷新，选单只成功且有redirect才导航，失败反馈后可人工重试。采购详情六个实际按钮共五动作复用现有runDocumentAction同一通道，原确认/原因prompt/returnFocus及500/650ms导航不变，已统一两请求只补null保护与共享锁。公共导入跨重开及跨模块维持在途锁，成功hide/800ms锁，失败恢复原disabled；先捕获FormData再禁file，期初跳预检分支原样。后端/库存/权限不变，不把页面防连点称为后台幂等，结果不确定仍须先核对单据。
- 销售回归：录单基线18 passed，原新增36通过，旧模板反证最初因夹具缺csrfFetch产生伪红，root复核后弃用该证据并补忠实旧helper；VM载入HEAD旧源码的新增/保存并新增/编辑三个核心例实际已发请求，均在保存按钮未锁断言失败，产品不回退，finally专属测试字节恢复。补helper后原36再通过；root再加HTTP500携success信封三例通过，录单新增共39。原7模块及来源/stock_commitment/合同项目相邻76 passed。列表/选单基线14，原新增35通过，旧两模板29 failed/6原空值及数量闸passed，finally字节恢复，原5模块及相邻76 passed；root补HTTP400携success两例通过，新增共37。root追加5例统一实跑5 passed/71 deselected，不重复跑整站。原收集/零价与数量断言不变。
- 公共导入回归：基线30 passed，新22与原opening21联测43 passed；旧函数反证20 failed/2无file对照passed，预置忠实旧csrfFetch→fetch，首例已真实发请求后在submit.disabled断言失败，非缺helper伪红，finally函数逐字节恢复。最终四模块及相邻79 passed；旧opening21场景/断言均保留，仅补生产API、DOM token/disabled及Response元数据。覆盖sales/material实际配置、同/异模块在途重开、成功800ms与失败恢复、FormData构造异常及期初embedded分流。采购详情基线111 passed，新40通过；授权两旧fixture50 passed，保留取消/失败恢复、原因原值、焦点及其余页面原断言，并加导航前保持锁断言。装载生产base真实旧CSRF helper/Headers、旧onclick/旧action key后仅回退6核心例，3例实际重复2请求而非1、3例HTTP失败success包被误作成功，6 failed/34 deselected，不是缺helper或DOM伪红；finally产品字节恢复，最终模块及相邻151 passed。新增共138例（39+37+40+22），不叠加相邻重复计数；日志sales_entry_transport/、sales-transport-*.log、global_import_transport/、frontend-20261023-002-http-success-lock.log。全站回归交目标提交CI，本地不重复跑全站。
- 组合验收：显式TEMP隔离库9082冒烟119/119，受工具管理前台服务会话已Ctrl-C关闭，未用默认生产地址。规则0违规、verify_wms_bugs通过、文档契约最终34 passed；初次登记open与月度fixed分区统计不一致，完成验证后按实际修复状态登记fixed，未更改统计基线/放宽断言。证据frontend-20261023-002-{rules,bug-check,ledger-final,smoke}.log；不新增AI能力或改变AI模型/工具/权限/开关/迁移，不改库存与单据写入算法。
- 开工基线：main c0d5f4a4c3683775041c9780cbc564412bb40c88目标门禁exit0，WMS CI39878528880、AI39878528802均completed/success，Android39860469109成功且祖先/工程与构建工作流未变证明通过；写入前已核实。
- 发布闭环：代码1ca45e4f26ea2f501032da1c28b1ed57f9821578已推送main，读取实际push输出且HEAD/origin一致；WMS CI39881016601原完整单测/回归分片、规则、安全扫描和冒烟通过，AI39881016612、性能39881016499均completed/success。Android最近main39860469109成功，Git祖先/Android工程及构建工作流未变证明通过；未把旧绿直接当目标证据。匿名pre-push与发布查询403，连接器逐项核对最新三工作流的完整SHA/状态/链接并记录frontend-20261023-002-{push,deploy}-gate-evidence.json，才仅该次push临时使用已有查询跳过开关；未跳过未核实/非绿门禁。收尾仅台账，按已验收文档轻量规则验收，不重复业务全量。
- 生效确认：2026-10-23 09:01代理核验，生产需重启 WMS 服务生效；核对原PID16080完整命令/解释器/Session0/创建时间、8080单实例、main目标与tracked工作区无混合代码后，CIM Terminate返回0，沿原WMS-Warehouse计划任务单次重启。现PID14972/Session0，8080唯一listener、LastTaskResult=0；09:01:02日志版本1ca45e4、production/CSRF on、db-check migrate=ok（仅结构核验，不声称迁移）。本机/公网登录GET200均含CSRF，实际GET app.js与磁盘SHA256相同，WMS_NO_DB_TOUCH=1保留。收尾只台账不再次重启。所有业务测试只在隔离数据库/模拟网络，不在生产保存、导入、审批、完成、反审或生成出库/采购单，不改真实库存、账号密码或开关配置。


### BUG-2026-10-23-003: 销售公共列表及详情请求HTTP误成功与跨动作忙锁缺口

- 状态：已修复并发布。
- 根因/危害：base.bindListActions单笔/批量两处csrfFetch、sales_order_detail两处csrfPost共四个旧请求消费点只读JSON而不执行HTTP成功闸；非2xx携success信封可误提示成功/刷新/导航。公共列表及详情无覆盖人工确认→请求→成功刷新/导航的互斥，可重复或交叉派发。原CSRF、catch及后台角色/状态守卫确实存在，不误报为全无保护。
- 同类点已排查：关联BUG-2026-10-23-002与BUG-2026-10-22-011至020。全仓bindListActions真实消费者仅销售订单列表和销售出库列表，区别于普通出库列表；公共修复覆盖两者，保留字符串/对象端点、selectedIds/runOne/runBatch返回接口、ID编码、全选跳过disabled及原定制复制回调。销售详情整单下推原行为是刷新详情，按数量下推才使用result.url跳转；不能误改为redirect_url。销售删除后台目前固定msg，原按msg判断可用，本批不把文本耦合误报为删除必坏。批量真实路由通常success带计数/跳过说明，完整失败返回error/400；通用partial兼容不代表这两路实际返回partial。
- 修复：四个旧POST消费点统一WMS.api.postRaw，保持无body/JSON原协议，非2xx不能靠success正文误放行，null/业务拒绝及网络异常显示失败。公共列表binding级互斥在确认前生效，表内单笔/跨行/工具栏批量共用，取消失败恢复各按钮原disabled；成功保持至原600ms刷新，自定义复制回调仍500ms跳edit；同步throw/异步reject反馈并解锁，完整信封传给原回调。保留partial兼容、URL编码、全选跳过禁用、公开返回对象。详情五个写入口复用现有runDocumentAction，保留400ms延迟、whole刷新/selected result.url/删除原列表跳转；惰性访问WMS以适配content脚本早于base底部API加载。AI GET、数量前端规则、后台over_quantity/库存/权限不改。
- 公共列表回归：基线7 passed，新增37实际两消费者配置/DOM委托/生产API通过；旧真实CSRF helper可派发时回退36 failed/1原空选择对照passed，HTTP失败success正文专项绕过早期忙锁断言，实际请求后旧实现误成功；finally仅函数字节恢复，不覆盖base其它区域。最终6模块及相邻71 passed（3既有warning）；保留master禁用、无body/JSON ids/编码、batch partial600ms、真实复制回调500ms及同步throw/异步reject恢复。
- 详情回归：基线60 passed，新56通过（32实际写操作JS及生产API、24实际Jinja角色状态）；脚本按真实顺序先执行content再加载API/helper，避免预加载掩盖依赖。旧模板仅10核心反证全failed/46 deselected，5成功例实际重复2请求而非1，5个HTTP500携success包误toast/误删除导航；真实base csrfPost/Headers运行，不依赖新增attr才发请求，finally字节一致恢复。最终7模块及相邻130 passed（8既有SQLAlchemy warning）。新增合计93，不重复叠加相邻；未改任何旧测试或弱化断言。
- 组合验收：第三agent只读终审两消费者协议、回调/互斥/导航及加载顺序，无阻塞，未为并行新增重复桥接测试。显式TEMP隔离库9082冒烟119/119，工具管理前台服务会话已Ctrl-C退出；规则0违规、verify_wms_bugs通过、台账/库存定位/README契约34 passed。日志shared_list_transport/、sales-detail-20261023/及frontend-20261023-003-*.log；不新增AI能力或改变AI模型/工具/权限/开关/迁移。不重复本地全站，完整回归由代码提交CI执行。
- 开工基线：main971f1e5ad59b4a1ae6aba5f362575978ffef3d7c，check_ci_green目标门禁exit0；WMS CI39881691938、AI39881691919均completed/success，Android39860469109成功并通过祖先/工程与构建工作流未变证明。启用仓库钩子后开工。
- 发布闭环：代码45185716c41166d724c498bfb44e6dab7a2fad44已正常推送main并核对HEAD/origin一致；WMS CI39883675099完整单测/回归/冒烟及AI39883675105 completed/success，Android39860469109成功且复用证明通过。等待期间只读发现004会话提示组合问题，004写入在003严格目标门禁exit0后解锁；003未单独重启，004目标全绿后已共同发布f82e25de，整批仅一次生产重启。
- 生效确认：2026-10-23 09:38代理核验，生产需重启 WMS 服务生效；与004共同加载f82e25de，仅沿原WMS-Warehouse任务单次重启，现PID7980/Session0、8080单实例，版本日志f82e25d及本机/公网登录GET200均核实，详情见004生效记录。所有业务测试只用隔离库/模拟网络，未在生产确认、删除、完成、反提交、取消订单或生成出库草稿；不改真实库存、账号密码或开关配置。


### BUG-2026-10-23-004: fetch拦截器与统一API会话过期重复提示

- 状态：已修复并发布。
- 根因/危害：base全局fetch拦截器使用window.__wmsSessionExpiredShown，api.js使用私有sessionExpiredShown；在继承base的页面，单次401/419由两层分别提示登录。003等待CI期间只读实测真实base首IIFE+api.js单次401 postRaw产生2次confirm及2个5000ms复位timer。此为既有统一层问题，新迁移入口也会受影响，不能只测脱离base的API而遗漏组合行为。
- 同类点已排查：检索台账及全仓sessionExpiredShown，仅两层持有独立标志，非各业务页单独弹窗；统一API同时用于不加载base的独立页面，修复不能直接删除其会话处理。所有JSON/raw/Response请求共用同入口，不改HTTP拒绝、CSRF、凭据及人工确认跳登录规则。
- 修复：仅api.js删除私有标记，handleSessionExpired读/置true/5秒复位均复用global.__wmsSessionExpiredShown，不初始化覆盖base或先前请求已设置的true。保留独立API工作、401/419 SESSION_EXPIRED拒绝、接受人工跳/login/取消5秒后可再次提示；不改base拦截器或API其它传输逻辑。
- 回归：修前API36+base拦截器8共44 passed；新12项真实base首IIFE与生产API组合及独立加载通过，覆盖401/419、raw/post/postRaw/postResponse同tick并发、接受/取消复位、先API后base、已提示true不覆盖；会话响应不消费JSON。仅旧api字节回退4个真实组合核心全failed/8 deselected，均直接2次confirm!=1，无缺依赖伪红；finally API精确字节恢复，base未回退。最终4模块及相邻284 passed（39.80秒）；日志session-expiry-20261023/。
- 验证边界：此action仅API JS与测试/台账，不改模板或路由，沿用003模板批次119/119隔离HTTP冒烟；会话拒绝由真实拦截器组合及API相邻回归验证，不在本地重复全站pytest或第二遍全站HTTP冒烟。提交前规则与历史BUG检查及目标提交全量CI仍执行；没有新增AI能力/权限/模型/工具/开关/迁移。
- 组合验收：规则0违规、verify_wms_bugs通过、台账契约10 passed；日志frontend-20261023-004-{rules,bug-check,ledger}.log。未放宽既有断言或修改其它API分支。
- 开工基线：003代码45185716c41166d724c498bfb44e6dab7a2fad44的WMS CI39883675099、AI39883675105已completed/success，Android39860469109成功并通过祖先/路径未变证明，check_ci_green目标exit0后才解锁写入。先前等待期间仅只读复核，未写004业务代码。003尚未生产发布，待004目标全绿后一起单次重启。
- 发布闭环：f82e25de7fec71d2f7409989401de93a444d53c2已推送main，读取实际push输出且HEAD/origin一致；WMS CI39884775811原完整单测/回归/冒烟与AI39884775807、性能39884775824均completed/success，最新main记录完整SHA匹配目标。Android39860469109成功，Git祖先/Android工程与构建工作流未变证明通过。匿名pre-push查询403，连接器核实同一45185716基线三工作流全绿并记录frontend-20261023-004-push-gate-evidence.json，才仅该次push临时使用已有查询跳过开关；部署再次核实目标并记录deploy-gate-evidence.json，未将查询失败误作绿灯。003和004共同只重启一次，收尾仅台账走文档轻量CI。
- 生效确认：2026-10-23 09:38代理核验；核对原PID14972完整命令/解释器/Session0/创建时间、8080单实例、main目标及tracked工作区无混合写入后，CIM Terminate返回0，沿原WMS-Warehouse任务单次重启。现PID7980/Session0、8080唯一listener、LastTaskResult=0；09:38:10日志f82e25d、production/CSRF on，db-check migrate=ok仅结构核验不声称迁移。WMS_NO_DB_TOUCH=1保留；本机/公网登录GET200含CSRF，实际GET api.js与磁盘SHA256相同。未在生产触发会话过期或实际登录/改密，不改真实账号、密码、业务记录、库存或开关；收尾只台账不再次重启。

### BUG-2026-10-23-005: 系统设置重复请求及初始化预览、确认状态脱节

- 状态：已修复并发布。
- 根因/危害：保存、文字/图片连接测试三条旧请求未统一校验HTTP，空响应直接取status；按钮禁用不构成逻辑互斥，保存刷新等待期已解锁。初始化原执行链已有HTTP校验，不能误报为全无保护；但密码/短语input事件能在执行中重新启用确认，预览未成功也可执行，打开弹窗与shown事件重复GET。预览始终把主数据计入将清理合计，与取消勾选时后端保留主数据不一致；说明未准确交代系统参数重置默认、本次审计保留。
- 修复范围：仅系统设置模板及其回归/说明。四POST使用WMS.api.postRaw、预览GET使用getRaw，保留FormData、空密钥不覆盖、密码原值、精确短语、主数据勾选和最后人工确认。页面写请求共用忙锁，覆盖确认、进行中和原500/1500ms刷新等待；预览成功才放行，重开清旧密码/短语，单次加载、勾选仅重绘成功缓存，保留主数据不计将清理合计。失败显示中文反馈且不自动重发；初始化不确定结果提示先核对再重新确认。说明和README匹配既有后端行为，不改清理算法、权限、账号或密码。
- 同类点已排查：关联003/004请求互斥及会话组合治理；检索SYS-AUDIT-001/008/009历史记录，保留默认设置恢复、脱敏错误及include_master_data字段，不重复实现后台能力。核对本页所有四写入口、唯一预览GET和真实DOM，连接测试有外部调用/日志副作用，验证必须模拟；预览GET本身只计数。
- 开工基线：main2c696915cca3acfbad9b46cd60a4a3871c834f16，check_ci_green --json退出0；WMS CI39885284357、AI39885284394目标匹配且completed/success，Android39860469109 attempt2成功，SHA a1c3a160acd7c813a8b1f67fe00bcede1d0a344b通过目标祖先与保护路径未变证明；钩子已启用。
- 回归：原模块基线15 passed；最终新增37项真实Jinja/整段业务JS、base首fetch拦截器、旧csrfFetch及生产api.js组合通过，含FormData原值/空密钥/vision、HTTP500携success、null/HTML/401/419/断网、互斥与500/1500ms等待、精确短语/取消/重开、失败人工重试、预览门控/晚回包、主数据缓存合计。必要修正后模块及相邻52 passed（37新+15原，13.77秒），不弱化旧断言。
- 回退验证：独占文件字节备份并finally恢复后，仅撤初始化两忙锁guard、保留预览门控，核心1 failed，已真实发送execute后input错误解锁。旧整页初36 failed中存在Headers读取提前失败，未拿该结果证明HTTP行为；修正harness真实base拦截及new Headers读取后，VM注入旧脚本的save/text/vision三HTTP500场景均在实际发送请求后错误success断言失败。终审发现执行中改勾选后失败预览不同步，补execute finally按当前checkbox重绘缓存，VM仅撤该1行单例在预览计数断言失败。日志system_settings_transport/init_busy_revert.log及system-settings-20261023/{vm-rollback-fixed-harness,final-adjacent}.log；不用stash，无生产请求。
- 组合验收：第三agent只读协议及最终窄补丁审查通过；规则0违规、verify_wms_bugs通过、台账/库存定位/README契约34 passed。显式TEMP隔离库9082冒烟119/119含system_settings GET200，工具前台服务已关闭；终审补丁仅缓存重绘，由新增核心锁覆盖，不重复全站冒烟。日志frontend-20261023-005-{rules,bug-check,ledger,smoke}.log。本地不重复全站pytest，交目标CI；不新增AI能力或改AI权限/模型/工具/开关/迁移，不调用生产保存、连接测试或初始化。
- 发布闭环：代码a242a9067d5671d1d4ad2dab8ad4d3a422a8a470已推送main，读取实际push输出并核对HEAD/origin一致；WMS CI39891610350完整单测/回归/静态/冒烟及AI39891610341均completed/success，最新main SHA匹配目标。Android39860469109 success，经本地祖先与Android工程/构建工作流未变证明复用。匿名pre-push查询403后，连接器核实同一2c696915基线三工作流全绿并记录frontend-20261023-005-push-gate-evidence.json，才仅该次push临时使用已有查询跳过开关；目标发布再次核实并留deploy-gate-evidence.json，不把未知、排队或失败当绿。收尾仅本台账走文档轻量检查。
- 生效确认：2026-10-23 10:55代理核验，生产需重启 WMS 服务生效；核对原PID7980完整命令/解释器/Session0/精确创建时间及任务入口、8080单实例、目标main与tracked工作区无混合写入，CIM Terminate返回0，沿原WMS-Warehouse任务单次重启。现PID13436/Session0、8080唯一listener、LastTaskResult=0；10:55:26启动日志版本a242a90、production/CSRF on，本机及公网登录GET200含CSRF。db-check migrate=ok仅结构核验，不声称迁移；WMS_NO_DB_TOUCH=1保留。真实页面交互由隔离Jinja/JS与HTTP验证，生产未实际登录测试系统设置、保存配置、调用外部连接测试或初始化，未清理业务数据、修改账号密码或库存。收尾只台账不再次重启。

### BUG-2026-10-23-006: 批量标签打印模板竞态及入库标签Excel物料来源错位

- 状态：已修复并发布。
- 根因/危害：独立批量标签页切换A/B模板没有请求代次，A晚到可覆盖当前B的内容与物理尺寸，切空仍保留旧模板；三GET缺统一HTTP/空响应处理，失败只写控制台或静默回退。入库明细标签入口也复用此页，URL ids为InOrderItem，下载Excel却当Material ids使用，可能下载错误物料。默认标签fallback直接拼innerHTML，物料字段未按纯文本展示。共享自动打印只判断容器有children，spinner/错误提示也会误就绪，15秒后还强制打印；手动按钮也未检查模板就绪。
- 修复范围：仅批量标签模板及共享自动打印的可选标签就绪分支。独立页本地版本化api.js+三GET getRaw，最新选择/缓存/空选一致，保留90×50优先、再默认、再首个与原字段/布局/条码渲染；主数据fallback改DOM/textContent。Excel以实际MATERIALS物料集合构造ids，保留template_id编码与下载入口。标记标签loading/ready/error/empty，仅ready允许手动/自动打印，实际出纸回调再次检查选择；错误/超时不强印，无标记页面原自动打印份数/时序/关闭行为保留。未知模板失败的默认仅预览，需重试或人工明确选择默认再打印；不改变后端权限、打印队列或实体设备设置。
- 同类点已排查：核对物料批量与入库明细两个真实入口、HTML模板列表/详情、Excel列表和下载路由、共享autoprint消费者；查阅9月标签字段/行高/布局/IDs历史与既有请求、预览竞态治理。入库新增页旧createInOrderFromPurchaseOrderSelection无实际DOM入口，未当线上写操作改造。物料内嵌标签设计器的独立编辑/保存状态存在另外的切换候选，已定位loadTemplateList/switchTemplateById/loadTemplateToEditor，留后续独立复核，不在本次打印页修复中宣称完成。
- 代理兼容边界：只读确认ptoken仅授权绑定物料集合的打印视图，不建立登录session；模板/图片API仍需登录，旧HTML代理实际依赖失败后的90×50文字fallback。本批不放宽API或伪造登录，匿名且已有ptoken的已授权页明确走原文字fallback，跳过需登录GET并按ready打印，Excel禁用并提示登录；只注入布尔模式，不把token写入JS配置或日志。登录页面仍正常选择配置模板。自定义模板/条码图片的免登录细粒度授权属于后续独立能力，不在本批宣称已实现。
- 打印验证边界：本批ready表示当前模板DOM已完成，保留既有条码/二维码加载及onerror降级，不新增图片load等待；不以JS打印计数冒充真实纸张、图片完整出纸或实体打印机验收。
- 开工基线：main8ddea9a95fff3da9737e917aecfe221065f5ed98，check_ci_green --json退出0；WMS CI39892367448、AI39892367454目标匹配且completed/success，Android39860469109 success并通过祖先/保护路径未变证明，仓库钩子已启用。
- 回归：修前六标签模块34 passed（15.18秒），共享打印队列/代理两模块50 passed（23.21秒，26既有warning），共84旧例。新增31真实Jinja/全段JS/生产api.js/DOM树渲染通过，覆盖优先级、晚成功/失败/cache/空选、三GET异常反馈、物料字段字面显示、Excel实际物料与编码、自动loading/error/15s/400ms重新切换、手动及匿名ptoken模式。最终九模块115 passed（31新+84原，31.61秒，26既有SQLAlchemy warning），无旧断言修改。
- 回退验证：修前真实DOM先复现B70mm被晚到A40mm覆盖，1 failed/22 deselected。随后VM注入真实旧Jinja脚本六核心，实际内容/尺寸、三GET HTTP失败误接受、fallback字面丢失、入库行ID误作物料ID均失败；仅替换旧共享helper并保留新标签页面，四例在实际错误调用window.print处失败（loading子节点、400ms切换、error、timeout），无marker旧两份/关闭正对照通过，共10有效失败及1通过。两产品文件全程字节核验未回退、不使用stash，不靠缺新helper或请求头提前失败证明；日志batch-label-loading-20261023/{old-race,new,vm-rollback,final-adjacent}.log。
- 组合验收：第三agent只读终审两产品协议、匿名边界及就绪流程无阻塞。规则0违规、verify_wms_bugs通过、台账/库存定位/README契约34 passed，显式TEMP隔离库9082 HTTP冒烟119/119且已关闭工具前台服务；日志frontend-20261023-006-{baseline,autoprint-baseline,rules,bug-check,ledger,smoke}.log。不新增AI能力/模型/工具/权限/开关/迁移；本地不重复全站pytest，交本次代码CI。
- 发布闭环：代码161f1363e2eb991ebb5a8aabcb6c2f7629fda76f已正常推送main，读取实际push输出且HEAD/origin新SHA一致；WMS CI39895668774完整单测/回归/静态/冒烟与AI39895668761均completed/success，最新main SHA匹配目标。Android39860469109成功并经目标祖先/Android工程与工作流未变证明复用；check_ci_green --target-sha严格门禁退出0，证据frontend-20261023-006-deploy-gate.json。未跳过门禁；收尾只本台账走文档轻量检查。
- 生效确认：2026-10-23 11:38代理核验，生产需重启 WMS 服务生效；核对原PID13436完整命令/解释器/Session0/精确启动时间、WMS-Warehouse入口、8080单实例、目标main及tracked工作区无混合写入后，CIM Terminate返回0，沿原计划任务单次重启。现PID16808/Session0、8080唯一listener、LastTaskResult=0；11:38:35启动日志版本161f136、production/CSRF on，db-check migrate=ok仅结构核验不声称迁移，WMS_NO_DB_TOUCH=1保留。本机/公网登录GET200含CSRF。所有标签、下载、复制份数及自动关闭验证仅模拟网络/打印计数和隔离数据库，未调用真实打印机、下载生产标签或修改业务记录、库存、账号密码、队列和打印机配置；收尾只台账不再次重启。

### BUG-2026-10-23-007: 物料标签设计器异步切换与保存目标脱节

- 状态：已修复并发布。
- 根因/危害：物料页内嵌标签设计器的列表/详情无代次，晚到旧模板可覆盖新选择；选B加载期间仍保留A的currentTemplateId，保存可能写入A，空选未调用清ID分支。清空、撤销/草稿和关闭未作废在途读取；四写请求已经走postRaw，问题是缺逻辑互斥/null处理及成功刷新无条件切默认，不能误报为未带CSRF。加载渲染缺style可抛错，文字拼innerHTML、layout与顶层尺寸/行列缺省口径不一致，可能留下ID/名称/画布不一致状态。
- 修复范围：仅material.html标签设计器区域。读取代次与加载/写互斥维持选择、名称、画布及目标一致；最新成功才能接管编辑，清空/草稿/撤销/关闭作废旧读，写入到成功刷新期间防重入。保留四POST的FormData/JSON/null及人工删除确认；更新/设默认按捕获ID回选，新增无返回ID按后端唯一名称定位，不盲跳默认；save_layout不负责重命名，名称变更须另存。单元格以DOM/textContent恢复、缺style兼容，布局几何优先layout再顶层再原默认，行列创建一致；不改后端权限、库存、账号或打印算法。
- 同类点已排查：关联006明确留下的内嵌设计器候选；核对全仓switchTemplateById仅此消费者、独立标签详情无异步选单竞态。查阅旧格坐标/自定义尺寸保存契约，保留collect/reindex、自定义尺寸同步、行高/合并格、条码宽高、草稿及撤销历史；不扩展到整页物料操作或其它独立权限/工程债。
- 开工基线：main3c7c85bbd01a88491efc1c1d9be904b96bde1f6c，check_ci_green --json退出0；WMS CI39896296394、AI39896296407目标匹配且completed/success，Android39860469109成功并通过祖先/Android工程与工作流未变证明；钩子已启用。
- 回归：修前四模块245 passed（32.68秒）：cell_coords、custom_size_sync、material_mobile_api_transport及print_label_row_height。新增28项实际标签区域JS/生产api.js/DOM表格、dragDrop/canvas/collect链通过，覆盖A/B及列表晚包、加载禁保存、空选/clear/history/draft/hide失效、四写原载荷与跨刷新互斥、成功保ID/按新增唯一名回选、取消/失败人工重试、末模板删除草稿、空名启用字段聚焦、缺style/字面文本及几何。最终五模块273 passed（28新+245原，40.69秒），旧测试和fixtures均未改。
- 回退验证：VM注入真实旧完整标签JS区域，六核心在实际A/B身份/画布覆盖、B加载仍保存A、空选旧ID、重复POST、文字丢失和缺style未正确渲染处失败；仅撤内部afterWrite转发单例在末模板删除未恢复草稿处失败，共7有效反证，无ReferenceError缺依赖伪红，两产品/测试回退时文件均未改字节，不用stash。初old-core.log误读到已修源码的3passed不计反证；有效日志material-label-editor-20261023/{vm-rollback,vm-draft-guard,final-adjacent}.log。
- 组合验收：第三agent只读终审核心协议/生命周期通过，Root发现并收口先禁字段再空名focus的顺序回归，空名先校验再取锁；删除末模板的内部草稿恢复绕过仅限内部标志，外部写中仍禁止。规则0违规、verify_wms_bugs通过、台账/库存定位/README契约34 passed，显式TEMP隔离库9082冒烟119/119且工具前台服务已关闭。日志frontend-20261023-007-{baseline,rules,bug-check,ledger,smoke}.log。无新AI能力/模型/工具/权限/开关/迁移；本地不重复全站pytest，交目标代码CI，不在生产保存、删除或设默认模板。
- 发布闭环：代码60b3603e36b8db3e6400b6a91897b17c9e9ee09c已正常推送main，读取实际push输出且HEAD/origin新SHA一致；WMS CI39906820513完整单测/回归/静态/冒烟及AI39906820505均completed/success，最新main匹配目标。Android39860469109成功并通过目标祖先/Android工程与工作流未变证明复用，严格check_ci_green目标门禁退出0（frontend-20261023-007-code-ci.log）。未跳过门禁，收尾只本台账走文档轻量检查。
- 生效确认：2026-10-23 13:41代理核验，生产需重启 WMS 服务生效；核对原PID16808完整命令/解释器/Session0/精确创建时间、原WMS-Warehouse入口、8080单实例、main目标及tracked工作区无混合写入后，CIM Terminate返回0，沿原计划任务单次重启。现PID12112/Session0、8080唯一listener、LastTaskResult=0；13:41:56启动日志版本60b3603、production/CSRF on，db-check migrate=ok仅结构核验不声称迁移，WMS_NO_DB_TOUCH=1保留。本机与公网登录GET200含CSRF；UI及写操作回归只用隔离数据库与模拟网络，未在生产保存/删除/设默认模板，不改真实物料、库存、账号密码或打印机配置，不调用实体打印机。收尾只台账不再次重启。

### BUG-2026-10-23-008: 普通领料保存完成后未进入新的领料单

- 状态：已修复并发布。
- 需求/根因：用户明确要求截图普通领料单的保存完成操作继续新增；当前out_order_add保存和完成均成功后仍固定跳详情，原单确已完成，缺的是下一张录入导航，并非完成接口或库存失败。顶部代理硬编码旧caption，不能只改页面按钮。新GET的hidden order_id原渲染None字符串，需准确显示为空新单。
- 修复范围：仅out_order_add.html及app.js顶部代理。按钮显示「保存完成并新增领料单」；保存和完成均success、页面与实际提交业务均为普通领料时，跳既有returnAddUrl并保留embedded。新GET沿用既有新单号/当天日期/空白明细，不携带旧ID、旧明细或旧查询。完成异常、需人工确认及不确定结果仍详情核对，不自动force；保存失败留当前录入。既有提交锁保持至导航。hidden新单ID转为空串、编辑原ID保留；顶部可选caption优先、无该属性保持原逻辑。不改后台、库存算法或其它业务流程。
- 同类点已排查：核对截图的/out_order/add与独立工单/requisition链，后者已有连续新增能力，不重复开发；核对页面按钮、顶部primarySave.click代理、new/edit GET及实际business_type可切其它业务的条件，不能只凭requisition marker放行。关联既有单一保存完成入口及001生产工单连续录入，保留其原业务边界。
- 开工基线：mainac9d7d8d2b8bdd336f0f08427a59e888c7490df2，check_ci_green --json退出0；WMS CI39907290814、AI39907290774目标匹配且completed/success，Android39860469109成功并通过祖先/Android工程与构建工作流未变证明，钩子已启用。
- 回归：修前四模块57 passed（8.00秒）：requisition_one_action、purchase_receipt_one_action、toolbar_semantic_dedupe、out_order_add_toolbar_remove_recent_template。新增11项真实submit/生产api.js/顶部代理与隔离实际GET通过，含普通/embedded连续新建、失败详情核对不force、重复点击、其它业务分流及新号/今天/空ID/空edit_items（DOM仍初始化30空行）；顶部可选label额外1例。最终五模块69 passed（11新+57原+1caption，9.81秒）。按用户明确新行为调整普通领料成功导航/按钮预期，保留原失败、重复提交及工单/采购入口断言；顶部旧mock改按实际属性名返回值，不削弱断言。
- 回退验证：VM只注入tracked HEAD旧submit，普通及embedded两success核心都已实际保存并完成成功，直接因旧/out_order/7不等于新/out_order/add而失败；两产品逐字节未动、不用stash，无缺helper或头断言提前失败。初轮10项因meta查询顺序夹具缺token失败已修正并弃作证据；真实GET初轮None字符串失败由产品改空串解决，保留空值断言。日志out-complete-continue-20261023/{new,vm-rollback,final-adjacent}.log。
- 组合验收：第三agent只读终审普通领料条件、顶部代理、锁及失败分流通过，hidden空值窄修由隔离GET回归核验。规则0违规、verify_wms_bugs通过、台账/库存定位/README契约34 passed；显式TEMP隔离库9082冒烟119/119且工具前台服务已关闭，日志frontend-20261023-008-{baseline,rules,bug-check,ledger,smoke}.log。不新增AI能力或改AI模型/权限/工具/开关/迁移；本地不重复全站pytest，交目标代码CI。
- 发布闭环：代码9af11190cf1eb9c8ee5351b7d5c4288ba7453dc0普通push成功，HEAD与origin/main一致；目标WMS CI39913494712（完整静态、单测、四分片、冒烟）与AI39913494844均completed/success。Android39860469109成功，祖先及受保护路径复用校验通过。部署前匿名查询HTTP403仅表示未核实，首次尝试未执行重启；随后连接器逐项重新取得最近main三工作流成功证据，AI/CI准确匹配9af1119，保存frontend-20261023-008-deploy-connector-evidence.json，未将限流当红灯或直接放行。
- 生效确认：2026-10-23 14:51代理核验；生产需重启 WMS 服务生效。核对原PID12112创建时间/完整命令/Python311解释器/Session0、WMS-Warehouse及原run_wms_task.bat入口、8080唯一监听、main一致和tracked工作区干净后，CIM Terminate返回0，沿原计划任务单次重启。现PID16744，创建时间14:51:39.8188510+08:00，Session0、同解释器及命令、8080唯一监听、LastTaskResult=0；14:51:43启动日志版本9af1119、production/CSRF on，db-check migrate=ok仅结构核验不声称迁移，原WMS_NO_DB_TOUCH=1保留。本机及https://gd2026.top/login只读GET200含CSRF；生产提供的app.js与磁盘SHA256相同。测试仅模拟保存/完成及隔离数据库，不替用户实际完成截图中的生产单据，不改生产库存、账号、密码或打印机配置；收尾只改台账不再次重启。

### BUG-2026-10-23-009: 打印网格保存回包误清等待期间的新改动及重复保存

- 状态：已修复并发布。
- 根因/危害：独立打印网格编辑器onSave发请求后仍允许编辑，成功回包却将回包时所有工作表现场S复制到orig；等待期间的新文字、样式或结构修改未进入请求，却被标记已保存，下一次差异载荷遗漏且离页不提示。保存入口无在途互斥，连点可同时写同一模板。既有统一API已判定HTTP/业务失败，不能误报请求层缺保护。
- 修复：唯一产品文件print-template-editor.js。保存时锁定一次请求并深拷贝各工作表提交状态；成功仅将该快照推进orig，不覆盖现场S、活动工作表或撤销重做栈，等待期间新编辑保留脏标记与离页提醒并可下次保存。保存按钮在途禁用且直接调用亦单飞，finally恢复原状态；失败基线不动，允许人工重试，未加载时保存不发请求。维持原WMS.api.post、全状态DIFF、清空语义、尺寸/样式/合并差异和del_rows空数组，不改后端、权限或文件写入算法。
- 同类点已排查：关联PRINT-TEMPLATE-F06既有能力与BUG-2026-10-22-006脚本拆分，修复原入口而非重做编辑器；核对入/出库共用此独立脚本，两者同时覆盖；物料内嵌标签设计器由007独立修复，无同一orig模型。期初搜索与lookup解包候选留下一批，预览、页面设置及尺寸清除API限制未扩展，本批不宣称全部前端问题清零。
- 开工基线：main881d3db03eb5950d74525d9d62cf19932ee432d1，匿名查询403后连接器核实最新WMS CI39914777915、AI39914777971准确匹配且completed/success；Android39860469109成功且祖先/工程与工作流未变证明通过。live git远端与本地一致，Git绝对路径bash启用hooks；证据frontend-20261023-009-baseline-evidence.json。六受影响模块修前49 passed（11.57秒），无存量失败。
- 回归：新增15项完整外链JS、真实api.js及实际模板DOM事件通过（3.62秒），覆盖保存期文字、撤销、切表、样式、列宽、插行的脏状态和下一次DIFF，重复保存只一POST，断网/错误HTTP携带success/null/空信封/业务失败保原基线并仅人工重试，未加载/加载失败不写空模板。VM注入真实HEAD旧完整脚本，7核心在orig错误推进、离页脏状态消失或3POST不等于1处有效失败，旧clean对照仍通过；产品不物理回退、不用stash，日志print-editor-save-20261023/{new,vm-rollback}.log。最终八模块（原49+新15+相邻73）137 passed（25.13秒），原测试断言未改；日志frontend-20261023-009-final-adjacent.log。
- 组合验收：第三agent只读终审快照、载荷无现场可变引用、工作表/撤销与API契约通过；规则0违规、verify_wms_bugs通过，台账/README/库存定位契约34 passed。仅JS状态修复，不改模板或路由，本批不重复运行全站HTTP冒烟；完整全站回归交目标代码CI。未新增AI能力或改变AI模型、权限、工具、开关、迁移；生产模板文件不用于测试。
- 发布闭环：代码63636e3e524a4e9e39783ce3854d2e307e35c8dd已推送main，实际push输出881d3db0..63636e3e且HEAD/origin/live远端一致。普通pre-push匿名查询403后，连接器重新核实同一基线881d3db0最新三工作流均success并通过Android祖先/路径证明，记录frontend-20261023-009-code-push-evidence.json，仅该次push临时使用WMS_SKIP_CI_GATE=1且finally清除；无未核实放行。目标完整WMS CI39922113108、AI39922113163及性能39922113188均completed/success，部署前连接器再次核对最新main准确匹配63636e3e；Android39860469109成功，目标祖先/保护路径证明通过。收尾仅台账轻量CI，不再次运行全站或重启。
- 生效确认：2026-10-23 16:10代理核验。静态资源版本在服务启动计算，因此核对原PID16744完整命令/Python311解释器/Session0/精确创建时间、WMS-Warehouse原run_wms_task.bat入口、8080单实例、目标SHA及tracked工作区干净后，CIM Terminate返回0，沿原计划任务单次重启。新PID14024，创建时间16:10:23.7555420+08:00，Session0、同解释器与命令、8080唯一监听、LastTaskResult=0。16:10:27启动日志63636e3、production/CSRF on，db-check migrate=ok只表示结构检查不声称执行迁移，原WMS_NO_DB_TOUCH=1保留。只读本机/公网登录GET200含CSRF，生产print-template-editor.js与磁盘SHA256一致（D213F761321A54330EB883D9DA2B6FF1E4DFE3E707D567EEDA6B9A4E23873C87）。所有写请求只用模拟网络或隔离测试目录/数据库，不保存真实生产模板或调用实体打印机，不改业务记录、库存、账号或密码。

### BUG-2026-10-23-010: 期初物料查询重复解包使搜索空白和粘贴编码误报不存在

- 状态：已修复并发布。
- 根因/危害：opening-stock.js已使用WMS.api.get/post，默认模式会解包data，但搜索仍读取data.data、lookup仍读取data.data.items，导致实际命中物料不进菜单/缓存，新编码粘贴被误报不存在。空输入未推进搜索代次，关闭或网格换行后旧请求仍可覆盖菜单；粘贴lookup仅slice前500，超过部分未查询就被当不存在。等待查询期间输入及表头变更后仍用旧文本搭新上下文保存，存在异步错位。
- 修复范围：仅期初页面脚本的物料查询及其生命周期；保持默认API业务/HTTP错误判定、既有物料字段/缓存、人工选料和粘贴保存入口。搜索直接读取已解包数组并在输入/关闭/重绘后失效旧响应。粘贴编码归一化去重后按每批最多500串行查询取全；任一请求失败不进入保存，保留原真正缺失编码的行级反馈与部分有效行语义。查询期间文本/日期/仓库/备注变化或弹窗关闭须重新确认，防止旧结果继续保存。
- 同类点已排查：关联BUG-2026-09-16-012服务端物料搜索与BUG-2026-10-22-006脚本拆分，009已留下此候选；核对/api/material/search及/opening_stock/materials/lookup实际返回与统一API解包协议。普通保存、行删/批删/整单删除的跨动作忙锁属独立遗留，本批不混修；后端库存算法、仓库库位开关、权限及schema均不变。
- 开工基线：main8edbbaa6c78c1c4c72fdfe88a42d4a1f1fb495e4，严格目标check_ci_green退出0；WMS CI39922978020、AI39922978128精确匹配且success，Android39860469109成功并通过祖先及工程/构建工作流未变证明，live远端一致、钩子已启用。四模块material_search/entry_draft/multi_doc/mobile_list_edit修前84 passed（11既有SQLAlchemy警告，30.20秒）。
- 回归：新增24项完整opening-stock.js、真实api.js及实际模板/网格事件运行时通过。覆盖真实搜索命中并选入缓存、空输入防抖/旧包/换行/关闭/重绘、错误HTTP携带success/null/断网反馈，lookup预热后原CSV解析与零价/仓库/日期/备注保存载荷、缓存免lookup、大小写及空白去重、501个不同编码按500+1全部查完后仅一次保存、第二批失败零保存、明确missing仍保持部分有效行与跳过提示、错误items形状不保存，以及文本/两种日期/仓库/备注/弹窗关闭六种失效。强两核心先2 passed，原21与追加3分别通过；首20中hide只模拟hidden事件造成1个夹具假负已弃，改为真实hide再hidden顺序，不修改产品监听或放宽断言。
- 回退验证：VM载入真实HEAD旧完整脚本，搜索命中、lookup合法保存、空输入取消防抖3项分别在无候选/零保存/实际1请求而非0处有效失败；只撤表头日期守卫、搜索回包守卫、分块继续查询3项分别在旧上下文保存、旧包覆盖、前500即提前保存处失败。旧network反馈正对照仍通过。产品字节未物理回退、不用stash，日志opening-material-lookup-20261023/{core,new,extra-contracts,vm-rollback}.log。
- 组合验收：七模块（原84+库位5+导入预检相邻16+新增24）129 passed（11既有SQLAlchemy警告，45.92秒），日志frontend-20261023-010-final-adjacent.log。第三agent只读终审协议/分块/生命周期与原载荷通过；规则0违规、verify_wms_bugs通过，台账/README/库存定位契约34 passed。原测试与断言未改；仅JS查询层，不改模板/路由，本地不重复全站HTTP冒烟，目标代码CI执行完整全站。无新增AI能力、模型、工具、权限、开关或迁移变更。
- 发布闭环：代码28dbe3fd637d8a00ddf9b7a5d53f126c86f7a30d普通push成功（8edbbaa6..28dbe3fd main -> main），HEAD/origin/live远端一致；WMS CI39925703448完整原静态/单测/回归分片/冒烟、AI39925703458及性能39925703430全部completed/success。严格目标SHA check_ci_green退出0（frontend-20261023-010-deploy-gate.json），Android39860469109成功且目标祖先/Android工程及构建工作流未变证明通过，未跳门禁。收尾只本台账，沿轻量CI验收，不重复全站或再次重启。
- 生效确认：2026-10-23 16:42代理核验。静态资源版本在启动计算，核对原PID14024完整命令/Python311解释器/Session0/精确创建时间、WMS-Warehouse原run_wms_task.bat入口、8080唯一监听、目标SHA和tracked工作区干净后，CIM Terminate返回0，沿原计划任务单次重启。新PID7312，创建时间16:42:03.7980060+08:00，Session0、同解释器/命令、8080唯一监听、LastTaskResult=0；16:42:07启动日志28dbe3f、production/CSRF on，db-check migrate=ok仅结构核验不声称执行迁移，原WMS_NO_DB_TOUCH=1保留。本机及公网登录只读GET200含CSRF，生产opening-stock.js与磁盘SHA256一致（DC2B454F1A727570C92E352C2FCF4BC53AFD159BF8D0B396F5FF174F80EC9F81）。测试只用模拟请求及隔离数据库，不在生产导入/修改期初、保存或删除单据，不改真实库存、账号、密码或仓库配置。


### BUG-2026-10-23-011: 公共布局无条件加载图表库且仪表盘重复引入

- 状态：已修复并发布。
- 根因/危害：base.html 在 head 全局同步加载 Chart.js，普通录单/列表也下载和解析图表库；report_dashboard 的 extra_js 又引入同一文件，重复执行库初始化。sales_reconciliation_report 隐式依赖公共布局，直接删除全局引用会使对账图表消失。
- 修复范围：移除公共布局 Chart.js 引用，对账页在自身 extra_js 中显式先加载本地库再初始化；仪表盘保留原有 stats 条件加载，未选仓库时不加载。不改报表数据、库存、请求接口或 AI 洞察行为。生产需重启 WMS 服务生效。
- 同类点已排查：全仓检索 Chart/chart.umd，实际消费者仅报表仪表盘和销售对账页；ZXing 已是扫码页加载、xlsx 已有组件动态加载，不按原报告误批处理。模板扫描统计不等同浏览器性能测量，本批不宣称首屏耗时改善百分比。
- 开工基线：main a833fe6577b8877c8a9b4b6d673842ae842d0276；check_ci_green.py --json 退出0，WMS CI39926710502、AI39926710537精确匹配且success，Android39860469109成功并通过祖先/保护路径未变证明。Git绝对路径bash已启用hooks。四受影响/相邻模块修前20 passed（1既有SQLAlchemy警告）。
- 回归：新增4项验证公共布局不带图表库、两图表页各加载一次且先加载后初始化、无仓库仪表盘不加载；Node执行实际Jinja渲染脚本，图表构造器替身分别收到4/2个不同canvas，避免仅用字符串判断图表仍在。六模块64 passed（1既有警告）。备份两个模板后git checkout恢复旧版，新增用例确实2 failed/2 passed，再finally逐字节恢复修复，不用stash（临时日志wms-chart-rollback-2t684dl1/rollback.log）。隔离临时SQLite+18080服务冒烟121/121，通过后已停止自建进程2900，未访问生产写接口；证据wms-frontend-011-l8anc6mj/smoke.log。
- 生效确认：2026-10-23 19:29代理核验。沿WMS-Warehouse原入口统一重启，PID8352/Session0，启动版本7c25740；本机/公网登录GET200含CSRF，生产CSP已移除unsafe-eval，静态shell.css与磁盘SHA256一致。仅共享版本/HTTP与静态资源在生产只读核验，交互回归和恶意载荷均只在隔离库/夹具中执行。统一备份及实例详情见BUG-2026-10-23-015。
- CI遗漏与回滚：首次代码1a31bd4a575d7b8d84628abc3a1d24a3bf8961a5的WMS CI39940144515单测分片2因本条漏登记POST_SPLIT_BUGS而失败（fixed316对历史315），其余业务/图表测试通过。按R8完整revert为80a0628270c7488ae3208432ec519e6abee2fb24，tree与开工基线完全一致；仅此纠错回滚因远端红灯无法通过普通pre-push而用git push --no-verify推送，未使用WMS_SKIP_CI_GATE，不用于新功能放行。回滚WMS CI39940697431、AI39940697458准确匹配且success后才重新写入。本次补登记本条的明确fixed状态，保留历史315/141/19/1基线及全部原断言；同时执行完整台账/README/库存定位契约34项。

- 发布闭环：代码38f790884d9eff32b6358de9cd89896f339765d5已实际push到main且本地/origin/live远端一致；WMS CI[运行39941406700](https://github.com/SIX2090/wms/actions/runs/39941406700)、AI[运行39941406733](https://github.com/SIX2090/wms/actions/runs/39941406733)均准确匹配并completed/success。对应受影响与相邻回归及代码提交全站CI通过。统一部署目标7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0同样全绿；逐页找到最新Android39860469109成功记录，并核实祖先关系、Git对象及Android工程/工作流无差异，未用任意旧绿替代。匿名403时沿用同一基线连接器替代证据和单次WMS_SKIP_CI_GATE=1，finally清除；各次push-gate.json与最终deployment-gate.json保留在本轮临时证据目录。

### BUG-2026-10-23-012: 公共布局重复内联约54KB静态样式且无法独立缓存

- 状态：已修复并发布。
- 根因/危害：base.html包含1849行、54248字节的静态CSS，每次HTML响应均重复下发，布局文件还混杂助手/打印提示/侧栏/录单栏样式。现有custom.css不是这段样式的替代品，直接合并会改变级联位置。
- 修复范围：将唯一静态style块原样迁出app/static/css/shell.css，在原位置以STATIC_VERSION引用；不改变任何选择器、声明值、顺序、优先级或业务脚本。base.html从4003降至2153行。独立文件沿用已有静态资源年度缓存/ETag及全目录mtime版本策略。生产需重启 WMS 服务生效。
- 同类点已排查：该CSS没有Jinja表达式和url()相对资源；其余业务模板样式不混改。原嵌入页浮动按钮、采购弹窗/批量编辑与toast层级断言改为读取模板实际加载的本地CSS，全部原断言保留；新增完整样式声明顺序SHA256快照04b9a0c0f13a44ec6336fa374a107c1f56a03596c709a60aad0291d9fe4bad23，新增shell.css的新增/更新/删除版本验证。不把399个!important或颜色数量本身当成已复现业务BUG。
- 开工基线：38f790884d9eff32b6358de9cd89896f339765d5；WMS CI39941406700、AI39941406733精确匹配且success，Android39860469109仍为祖先且保护路径未变。011首次台账遗漏已先完整回滚再修复，无跨批写入。受影响/相邻模块修前86 passed。
- 回归：新增3项覆盖加载顺序/版本引用、全部原CSS声明哈希、真实静态GET字节/类型/年度缓存/ETag/304；加入版本测试后七模块90 passed。新用例先在旧版3 failed；再备份模板和CSS、恢复旧模板并移除本批新CSS，3项均有效失败，finally恢复全部字节，不用stash，证据wms-shell-rollback-acq_m70p/rollback.log。真实浏览器重载隔离服务后，对账嵌入页body/main/sidebar/toast/AI按钮/打印铃铛六处计算样式（display、定位、层级、边距、宽度、字体、背景）与迁出前逐项完全一致，shell.css仅加载一次且无脚本错误；新隔离库18080冒烟121/121，证据wms-shell-qa-65j5v0mb/smoke.log。另六相邻/台账模块90 passed，规则0违规；目标CI在验收记录补充。
- 生效确认：2026-10-23 19:29代理核验。沿WMS-Warehouse原入口统一重启，PID8352/Session0，启动版本7c25740；本机/公网登录GET200含CSRF，生产CSP已移除unsafe-eval，静态shell.css与磁盘SHA256一致。仅共享版本/HTTP与静态资源在生产只读核验，交互回归和恶意载荷均只在隔离库/夹具中执行。统一备份及实例详情见BUG-2026-10-23-015。

- 发布闭环：代码84c4f5371abf0b7ad7824170aaf66b34f270e82c已实际push到main且本地/origin/live远端一致；WMS CI[运行39942386376](https://github.com/SIX2090/wms/actions/runs/39942386376)、AI[运行39942386400](https://github.com/SIX2090/wms/actions/runs/39942386400)均准确匹配并completed/success。对应受影响与相邻回归及代码提交全站CI通过。统一部署目标7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0同样全绿；逐页找到最新Android39860469109成功记录，并核实祖先关系、Git对象及Android工程/工作流无差异，未用任意旧绿替代。匿名403时沿用同一基线连接器替代证据和单次WMS_SKIP_CI_GATE=1，finally清除；各次push-gate.json与最终deployment-gate.json保留在本轮临时证据目录。

### BUG-2026-10-23-013: 公共布局保留乱码注释及CSRF例行调试输出

- 状态：已修复并发布。
- 根因/危害：旧编码转换留下七处不可读注释（四处样式、三处触摸/缩放说明）；例行CSRF刷新成功/显式禁用仍输出console.log，污染业务页面控制台。原报告把注释示例和反馈降级日志混计，不将所有console.log一律视为调试残留。
- 修复范围：仅恢复base.html与shell.css七处中文注释，删除两条例行调试输出及随之空置的禁用分支；保留刷新失败console.warn、原25分钟定时器、可见性触发、请求参数、token更新及finally解锁。物料刷新/ExcelTable的反馈降级日志仍有明确用途，不在本批删除。生产需重启 WMS 服务生效。
- 同类点已排查：检索全部自有模板/JS的console.log，api.js命中是文档示例，ExcelTable为allow-console降级输出；录单的notifyMaterialRefresh也是showToast缺失时的反馈降级。七处乱码原位修正，没有对整文件执行转码。CSS声明顺序快照仍通过，不改变当前禁止缩放的行为。
- 开工基线：84c4f5371abf0b7ad7824170aaf66b34f270e82c，WMS CI39942386376、AI39942386400精确匹配且success，Android39860469109祖先和保护路径证明保持。四受影响/相邻模块修前56 passed。
- 回归：新增9项（6个UTF8注释位置契约覆盖7处、3种真实CSRF刷新IIFE运行时）验证成功token更新、禁用/失败保留token、失败告警、请求凭据/header、25分钟间隔、单飞、防后台触发、finally解锁及可见性重试。五模块65 passed。备份两产品文件后恢复HEAD，新增测试8 failed/1 passed，finally恢复修复，不用stash，日志wms-hygiene-rollback-ki4tcrtq/rollback.log；说明原失败告警对照继续通过。台账/README/库存定位契约34 passed，规则0违规；新隔离库18080冒烟121/121，已停止自建进程8344，证据wms-shell-qa-p0gpfzrb/smoke.log。目标CI在验收记录补充。
- 生效确认：2026-10-23 19:29代理核验。沿WMS-Warehouse原入口统一重启，PID8352/Session0，启动版本7c25740；本机/公网登录GET200含CSRF，生产CSP已移除unsafe-eval，静态shell.css与磁盘SHA256一致。仅共享版本/HTTP与静态资源在生产只读核验，交互回归和恶意载荷均只在隔离库/夹具中执行。统一备份及实例详情见BUG-2026-10-23-015。

- 发布闭环：代码d73f9fbbe96d690f378b24883c3b287677ef227e已实际push到main且本地/origin/live远端一致；WMS CI[运行39943299522](https://github.com/SIX2090/wms/actions/runs/39943299522)、AI[运行39943299471](https://github.com/SIX2090/wms/actions/runs/39943299471)均准确匹配并completed/success。对应受影响与相邻回归及代码提交全站CI通过。统一部署目标7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0同样全绿；逐页找到最新Android39860469109成功记录，并核实祖先关系、Git对象及Android工程/工作流无差异，未用任意旧绿替代。匿名403时沿用同一基线连接器替代证据和单次WMS_SKIP_CI_GATE=1，finally清除；各次push-gate.json与最终deployment-gate.json保留在本轮临时证据目录。

### BUG-2026-10-23-014: AI页面把文字拼入点击脚本及库位推荐HTML

- 状态：已修复并发布。
- 根因/危害：质量看板低质量分组详情将escapeHtml后的字符串拼入onclick，HTML属性实体解码后单引号重新成为JS语法；真实renderLowQualitySamples产出+HTMLParser按浏览器解码+Node执行事件属性，测试值x');globalThis.__wmsProbe=1;//确实使探针变1。库位推荐搜索同样将物料编码/名称拼入onclick且将名称/规格作为HTML；推荐结果还直接插入库位名称和单位。含引号的正常文字可导致选择/下钻失败，恶意文字可成为DOM/脚本；不声称生产已遭利用。
- 修复范围：质量详情按钮改type=button、转义data属性和addEventListener；物料选项以DOM/textContent构建，点击闭包传原id/code/name；推荐结果的级别、库位、单位和数值文本经公共escapeHtml。原人工选料、只读下钻、20条候选上限、指标/推荐算法、权限、模型和所有业务写接口不变。生产需重启 WMS 服务生效。
- 同类点已排查：全仓检索模板字符串内事件属性，文本拼进事件脚本的两处均修复；期初库存剩余事件插值为本地行下标/数值ID，采购选择行仅data-item-id，不按相同根因改写。库位推荐同页结果渲染也一并检查修复。关联历史标签/AI反馈转义修复和既有AI-R15-F01/WMS-AI-GATE-001，不重复开发能力；新增子ID查重无等价项。
- 开工基线：d73f9fbbe96d690f378b24883c3b287677ef227e，WMS CI39943299522、AI39943299471准确匹配且success，Android39860469109祖先及保护路径证明不变。质量/看板两专项修前16项通过，完整verify_ai_all.py --level full --jobs 1修前70/70通过（272.87秒，wms-xss-baseline-20261023.log）。
- 回归：新增9项执行实际页面渲染函数/搜索事件和公共escapeHtml，覆盖O'Reilly、脚本闭合载荷、HTML标签/双引号/中文，验证属性解码后数据完整、零事件属性/注入节点、下钻原参、选料原id/code/name及重复渲染替换旧选项；推荐结果三处均只作为文本显示。新代码9 passed。备份两模板后恢复HEAD，新锁7 failed/2 passed，finally恢复字节、不用stash；日志wms-ai-text-rollback-9iblcrb_/rollback.log。修后完整verify_ai_all.py --level full --jobs 2为70/70通过（sum275.50秒，wms-xss-fixed-20261023.log，含verify_wms_bugs）；组合7模块89 passed，规则0违规，严格AI台账检查通过。真实浏览器用两页面实际函数和本地jQuery处理模拟载荷，选料/详情点击原参完整、注入图片节点0、探针始终0、控制台错误0；仅隔离夹具不代表生产已修复。新隔离库18080冒烟121/121且自建进程4152已停止（wms-shell-qa-_o56_f1d/smoke.log）。目标CI在验收记录补充。
- 生效确认：2026-10-23 19:29代理核验。沿WMS-Warehouse原入口统一重启，PID8352/Session0，启动版本7c25740；本机/公网登录GET200含CSRF，生产CSP已移除unsafe-eval，静态shell.css与磁盘SHA256一致。仅共享版本/HTTP与静态资源在生产只读核验，交互回归和恶意载荷均只在隔离库/夹具中执行。统一备份及实例详情见BUG-2026-10-23-015。

- 发布闭环：代码cd36abf6a62e083088eb31dc10ba9060843d9499已实际push到main且本地/origin/live远端一致；WMS CI[运行39944914326](https://github.com/SIX2090/wms/actions/runs/39944914326)、AI[运行39944914371](https://github.com/SIX2090/wms/actions/runs/39944914371)均准确匹配并completed/success。对应受影响与相邻回归及代码提交全站CI通过。统一部署目标7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0同样全绿；逐页找到最新Android39860469109成功记录，并核实祖先关系、Git对象及Android工程/工作流无差异，未用任意旧绿替代。匿名403时沿用同一基线连接器替代证据和单次WMS_SKIP_CI_GATE=1，finally清除；各次push-gate.json与最终deployment-gate.json保留在本轮临时证据目录。

### BUG-2026-10-23-015: 生产CSP无依赖却继续放行字符串动态代码执行

- 状态：已修复并发布。
- 根因/危害：ProductionConfig.SECURITY_HEADERS保留script-src unsafe-eval；它与现有内联脚本所需unsafe-inline并非同一依赖。全量本地JS（含第三方）和模板检索未发现eval、Function构造或字符串定时器调用，继续放行会无谓削弱脚本策略。
- 修复范围：仅移除script-src中的unsafe-eval，保留当前self/unsafe-inline以及object-src/base-uri/frame-ancestors等限制。新增前端资源与CSP说明并由README链接，说明加载/缓存事实与仍存unsafe-inline的限制，不声称已消除所有XSS。关联014已独立修复数据进事件脚本，不把CSP收紧当作其替代。需要重启 WMS 服务生效。
- 同类点已排查：全仓CSP实际配置仅该处，无其他nginx配置重复覆盖此指令；静态资源含本地第三方均扫描。014子修复AI-R15-FIX-TEXT-EVENT-001在cd36abf6推送及CI39944914326/AI39944914371成功后才标记代码闭环，生产仍待本轮统一重启，不新增AI功能、模型、工具、权限、开关或迁移。
- 开工基线：cd36abf6a62e083088eb31dc10ba9060843d9499，WMS CI39944914326、AI39944914371准确匹配且success，Android39860469109祖先与保护路径证明保持。四安全/Excel/图表模块修前39 passed。
- 回归：新增3项验证生产默认CSP、真实Flask响应头及全浏览器源码无字符串编译依赖；六模块51 passed。备份config.py再恢复HEAD，新锁2 failed/1静态扫描对照passed，finally恢复修复，不用stash，日志wms-csp-rollback-i8prll64/rollback.log。真实浏览器以当前ProductionConfig CSP加载实际本地依赖，eval和Function两种字符串编译均被拒绝；jQuery中文文本、Bootstrap弹窗初始化、Flatpickr日期、ZXing初始化（不请求摄像头）、SheetJS中文xlsx写入后读取、Chart实际绘制七项全部PASS。夹具在18081，仅模拟数据无业务请求。相邻与台账/README/库存定位/样式/刷新共46 passed，严格AI台账/源码编码及规则0违规、verify_wms_bugs全部通过。AI子任务标记完成时严格检查检出两模板漏归属标记，已补Jinja注释AI_TASK，不改变功能或放宽检查。新隔离库18080冒烟121/121，自建进程10312已停止（wms-shell-qa-5v3tz9az/smoke.log）。目标CI和统一生产验收在后续记录补充。
- 生效确认：2026-10-23 19:29代理核验。发布前再次确认目标SHA及tracked工作区干净、PID7196精确创建时间/完整命令/Python311/Session0、8080唯一监听、原run_wms_task.bat入口及WMS_NO_DB_TOUCH=1。用online_backup.py对生产库mode=ro在线一致性备份至backups/before_frontend_20261023_7c25740a.db，integrity_check=ok，备份SHA256为6a04cd7afb7dad5c50bdbeac048c42fa9165cb4c42b8654ac1b59ac58138f466。CIM Terminate返回0，沿原计划任务启动一次；新PID8352，19:29:44.252456+08:00创建，同解释器/命令/Session0，8080单实例，LastTaskResult=0。19:29:47日志版本7c25740、production、CSRF on；db-check migrate=ok仅结构检查，不声称执行迁移。只读本机和https://gd2026.top/login均200含CSRF且CSP不含unsafe-eval；实际服务shell.css的SHA256为2e340f68c3d58fd012bd0650db74c6979027f26d788bae185c7c8ecec9aa4462，与磁盘一致，text/css及年度缓存正确。production-check.json保留本轮临时证据。无生产单据/库存/账号/密码修改，未开库位、未触发实体打印。临时18080/18081服务和浏览器验收页均关闭。收尾仅文档记录，运行时代码仍为此已验收版本，不再次重启。
- 发布闭环：代码7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0已实际push到main且本地/origin/live远端一致；WMS CI[运行39945887710](https://github.com/SIX2090/wms/actions/runs/39945887710)、AI[运行39945887770](https://github.com/SIX2090/wms/actions/runs/39945887770)均准确匹配并completed/success。对应受影响与相邻回归及代码提交全站CI通过。统一部署目标7c25740a58f2ca5cf5622bdac1cd0b92026a5bb0同样全绿；逐页找到最新Android39860469109成功记录，并核实祖先关系、Git对象及Android工程/工作流无差异，未用任意旧绿替代。匿名403时沿用同一基线连接器替代证据和单次WMS_SKIP_CI_GATE=1，finally清除；各次push-gate.json与最终deployment-gate.json保留在本轮临时证据目录。

### BUG-2026-10-24-001: pypdf新披露漏洞导致定时CI安全门禁失败

- 状态：已修复并发布。
- 根因/危害：main ec3a04b32d64b1f172ec5446adf5127400ac5a87的最新定时WMS CI40027767633中，pip-audit命中pypdf6.21.1的CVE-2026-115572、115585、115580，均要求6.21.2；其他单测、回归及121项冒烟通过。Android40027751562和AI40027786403同SHA成功。本次仅恢复现有CI失败，不夹带下一批前端代码。
- 修复：唯一生产钉版升级pypdf6.21.2，测试清单继续通过-r复用；安全扫描仍阻塞，不加忽略项、不更改业务解析函数或权限。上游https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html及py-pdf/pypdf的PR4239/4240确认交叉引用表大小限制和重复整文件读取修复。
- 同类点已排查：关联BUG-2026-10-22-001及BUG-2026-10-21-002；全仓只有app/requirements.txt一个生效钉版，业务消费者仍为_ai_parse_pdf_bytes。历史漏洞记录保持历史版本；不对生产执行恶意文件测试。
- 回归：修前PDF、附件和依赖闭包契约34 passed。新增三个锁：版本至少6.21.2、缺失对象重复读取只扫描全文件一次、xref声明超出文件容量时立即拒绝。旧版3 failed/8 passed；新版结合附件与依赖闭包37 passed。备份requirements后git checkout HEAD恢复旧钉版并使用旧隔离运行环境，3 failed/8 passed，finally恢复修复；未使用stash。证据在临时目录wms-pypdf-20261024。
- 生效确认：2026-10-24用户明确授权部署并重启。先用online_backup.py对生产库mode=ro在线一致性备份至C:/wms_backups/pypdf_deploy_20261024/before_inventory.db，integrity_check=ok，SHA256为810d06792d7b40ab4bc11310e1089fa5f69edb03f7547f24744dd41db5464d32；旧6.21.1及新6.21.2官方wheel均保留该目录。核对PID8352创建时间/解释器/Session0/命令/8080唯一监听及原任务后停止该进程；生产Python311仅用本地wheel --no-index --no-deps升级6.21.2，pip check通过，沿WMS-Warehouse计划任务启动新PID12156（08:22:20.213123+08:00，Session0）。生产解释器下隔离PDF测试11 passed；8张核心表（物料、库位账、流水、入出库头/行、用户）前后数量与完整行摘要一致，quick_check=ok。未改生产业务记录、账号密码或云凭据。
- 本地验收补充：PDF/附件/依赖契约及台账47 passed；隔离HTTP冒烟121/121，临时服务3772已停止。隔离pip-audit对冻结旧清单准确复现3项CVE，新清单No known vulnerabilities found；普通规则0违规，verify_wms_bugs全部通过。
- 代码验收：7f9765440149a5d37bdbf9e7b5f067483c215edc的[WMS CI40043413616](https://github.com/SIX2090/wms/actions/runs/40043413616)及[AI40043413573](https://github.com/SIX2090/wms/actions/runs/40043413573)准确匹配并completed/success。普通push被既有真实依赖红灯拦截后，仅发布当前CI安全修复；按AGENTS§8.1.3使用已授权连接器上传5个准确blob，以当前main为base/parent、非force更新。远端与本地经验证的完整tree均e30db7e64f8992bc1e434e1e56a1279bef4e252e；保留原本地提交后以soft对齐真实远端，fetch后HEAD/origin/live main同SHA，后续git push显示Everything up-to-date。未伪造新push输出、未用WMS_SKIP_CI_GATE跳过真实红灯。

### BUG-2026-10-24-002: 公共导航初始化内联重复下发而无法独立缓存

- 状态：已修复并发布。
- 根因/影响：base.html的公共菜单、面包屑、日期占位与触控初始化共162行/6465字节不含Jinja数据，却每页随不缓存HTML重复下发；无法独立利用浏览器静态缓存。本次为前端审计剩余公共脚本缓存问题的分段整改，不宣称全部内联脚本或全局函数已清零。
- 修复：该完整script内容逐字节移入app/static/js/pages/shell-navigation.js，原位置同步加载，使用已有STATIC_VERSION；不加async/defer、不改变菜单入口/初始化事件顺序/日期与触控行为。原脚本及新文件SHA256均为517c7e85bf148e328afb0529e64a85c7ba503ce6fd17902960410c4b91f35d21。生产需重启 WMS 服务生效。
- 同类点已排查：关联BUG-2026-10-23-012公共CSS缓存提取；已存在pages目录和STATIC_VERSION机制，复用而不新增打包框架。公共CSRF/列表动作与AI助手留在原位置，本批不改请求协议、AI权限/能力或业务数据。原中文注释回归锁仅迁移到实际外置文件，断言内容/次数不变。
- 开工基线：7f9765440149a5d37bdbf9e7b5f067483c215edc，WMS CI40043413616及AI40043413573准确匹配并success；最新Android40027751562在ec3a04b3成功，已核实祖先及受保护路径无差异。公共壳层、菜单、列表传输、会话失效及动作相邻修前103 passed。
- 回归：新用例先在旧代码运行5 failed/5交互对照passed；修复后导航、中文注释、资源版本28 passed。备份base后git checkout HEAD回退并临时移出新资源，5 failed/5 passed，finally恢复，未使用stash。三角色Jinja真实模板输出由HTMLParser验证仅加载一次/带版本/原位置同步加载；Node执行实际脚本验证菜单点击/悬停/aria状态、外部和链接点击关闭、侧栏离开延迟、路径/查询/编辑页面包屑、首页和未匹配页隐藏、日期初始化和触控/滚轮行为。真实Flask静态响应验证字节、JS类型、年度缓存及ETag304；STATIC_VERSION新增/修改/移除用例增加该文件。node --check通过。
- 生效确认：2026-10-24 08:22用户授权后与001统一部署。PID12156、Python311/Session0、run_server.py命令及8080唯一监听准确，原WMS-Warehouse任务LastTaskResult=0。启动日志版本42218e9、production、CSRF开启，WMS_NO_DB_TOUCH=1；db-check migrate=ok仅表示结构校验，不声称执行迁移。只读本机和https://gd2026.top/login均HTTP200且含CSRF；本机/公网导航资源均200、JS类型、年度缓存，SHA256准确匹配517c7e85bf148e328afb0529e64a85c7ba503ce6fd17902960410c4b91f35d21。HTTP证据及一致性备份在C:/wms_backups/pypdf_deploy_20261024；未登录生产执行冒烟或生成业务记录。生产需重启 WMS 服务生效，本次已完成该重启。
- 本地验收补充：相关与相邻11个模块135 passed；隔离HTTP冒烟121/121，临时服务9036已停止（wms-shell-qa-7mvt0m6_/smoke.log）。普通规则0违规，verify_wms_bugs全部通过；新资源与新测试均单独核对后纳入提交。
- 代码验收：42218e9007f3e5f59795facfb8206f4b5a8301d6已实际git push（7f976544..42218e90 main -> main），HEAD/origin/live main一致；[WMS CI40044229758](https://github.com/SIX2090/wms/actions/runs/40044229758)及[AI40044229724](https://github.com/SIX2090/wms/actions/runs/40044229724)准确匹配并completed/success。发布前check_ci_green.py --target-sha完整SHA --json返回ok=true；最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，Git对象/祖先关系及Android工程和工作流无差异均通过证明。后续收尾仅记录台账，运行时代码与本次验收版本一致，无须再次重启。

### BUG-2026-10-24-003: AI浮窗请求失败误报成功、断流静默结束及内联脚本无法缓存

- 状态：已修复并发布；AI子任务AI-C01-FIX-WEB-TRANSPORT-001已完成。
- 根因/危害：既有AI-C01浮窗内联脚本980行/46098字节，每页随HTML下发；6处请求绕过WMS.api。清空历史不检查HTTP/业务结果，500或业务拒绝也报告服务器已清空；反馈和非流式聊天可能消费HTTP错误中的success正文。SSE读取错误原已有catch解锁，但调用finalize会把部分回复当正常结束或只提示没有回复，并非完全没有错误捕获。
- 修复：外置js/pages/ai-assistant.js并保持原角色条件、DOM/api.js/app.js后的同步加载与STATIC_VERSION。反馈/非流式聊天用postRaw保留业务封套，清空用post自动校验业务状态，历史用getRaw，流式用既有postResponse保留原始Response。读取Promise返回外层并传播异常，沿原错误展示与解锁路径处理；清空失败保留原本地上下文清空降级，并明确服务器未清空。未新增统一层API、AI能力/模型/工具/权限/开关/迁移，未改后端状态或人工确认边界。生产需重启 WMS 服务生效。
- 同类点已排查：关联BUG-2026-10-23-014/015、BUG-2026-10-24-002及历史AI-FEEDBACK-LOOP-001；当前浮窗6个请求消费点全部迁移，相关端点在模板/静态JS仅此消费方。原全局fetch拦截器继续提供会话/CSRF兜底，未误报旧代码完全缺CSRF保护；其他模板请求有各自校验，本批不宣称全站内联与raw fetch已清零。既有验证器改为跟随真实外链读取内容，字段、权限、幂等、命名原断言全部保留。
- 开工基线：026dad4bd31373e3c5bc430e93ab1aa2beed13a9的WMS CI40044919832及AI40044919674准确匹配success；最新Android40027751562祖先及受保护路径无差异证明通过。修前相关六模块87 passed（24项既有SQLAlchemy告警）。
- 回归：新增35项执行真实浮窗IIFE、原全局fetch包装和api.js的延迟请求/DOM/SSE测试，覆盖成功、业务拒绝、HTTP503+success正文、HTML502、网络拒绝、401/419、分块UTF-8、无reader降级、JSON拒绝、历史恢复、嵌入隐藏、Markdown转义；首轮34项旧版15 failed/19对照passed，新增部分回复后断流用例后旧版16 failed/19对照passed；修后35 passed。另15项覆盖8角色渲染/加载顺序、真实静态缓存/ETag、无原生fetch/服务端插值及五个未改功能函数字节摘要。相关与相邻146 passed（24项同基线告警）。备份base并git checkout HEAD回退、临时移出新资源，合计28 failed/22 passed，finally恢复，不用stash；证据临时目录wms-ai-shell-20261024/rollback.log。五个函数renderMarkdown/renderCards/renderActions/prepareImageAttachment/sendAssistantMessage保持原字节；图片压缩、Markdown、卡片动作、人工确认与发送分流未重写。
- 生效确认：2026-10-24 09:43代理核验，沿用用户上一轮已授权的备份及原计划任务发布流程。生产库mode=ro在线一致性备份C:/wms_backups/ai_shell_deploy_20261024/before_inventory.db，integrity_check=ok，SHA256为f5baa0d83dbe3cdcf660858bc93d91ab2b6eb64d950a39bf1df7bc4fd0582044。即时核对旧PID12156完整创建时间、Python311/Session0/run_server.py命令、8080唯一监听及原任务/保护开关，避开定时触发后仅停止此进程并启动WMS-Warehouse一次。新PID2656，09:43:18.359159+08:00创建，同解释器/命令/Session0、8080唯一监听，LastTaskResult=0。09:43:21启动日志版本189113e、production、CSRF on；WMS_NO_DB_TOUCH=1，db-check migrate=ok仅结构校验，不声称执行迁移。本机和https://gd2026.top/login均GET200含CSRF，匿名页不加载助手；实际JS为JavaScript类型/年度缓存，SHA256为01d803531a2c4c27aa82528023cd57ddf19dfc1025edbabec900ae799e9e0398，与磁盘匹配。8张核心表（物料、库位账、流水、入出库头/行、用户）前后完整行摘要一致，quick_check=ok。未在生产登录执行冒烟、聊天或反馈，未修改单据、库存、账号密码、依赖或云凭据；临时测试服务已停止。

- 最终本地验收：相关与相邻14个模块182 passed（24项同基线SQLAlchemy告警），完整AI验证70/70（sum=267.30s、jobs=2），普通规则0违规、源码编码检查及verify_wms_bugs通过；隔离HTTP冒烟121/121，临时服务11024已停止（wms-shell-qa-ckbm9n9v/smoke.log）。移出代码的历史空白行尾随空格同步清理，五个非传输函数摘要仍与原代码一致。

- 发布验收：189113e4c2a4f01625d5e2913c78f700c105265e已实际push（026dad4b..189113e4 main -> main），HEAD/origin/live main一致；[WMS CI40050536241](https://github.com/SIX2090/wms/actions/runs/40050536241)与[AI40050536129](https://github.com/SIX2090/wms/actions/runs/40050536129)准确匹配completed/success。首次check_ci_green目标检查ok=true，随后的匿名查询遇403限流，仅为查询故障；通过已连接GitHub工具按最新main列表重新核实三工作流，Android最新40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，Git祖先与工程/工作流无差异证明通过。替代证据ci-gate-alternative.json及HTTP/进程/数据摘要均保存在上述备份目录。收尾仅台账记录，不改变已发布应用代码；AI子修复不新增路由、工具、模型、模板能力、特性开关或迁移。
- 收尾推送门禁：匿名GitHub API同一查询故障时，以已保存的189113e4三工作流全绿及Android祖先/范围证明为替代证据，仅该次文档push临时设置WMS_SKIP_CI_GATE=1并在finally清除；不跳过实际非绿或未知状态。


### BUG-2026-10-24-004: 仓库及部门异步刷新覆盖新选择与乱序回写

- 状态：已修复并发布。
- 根因/危害：入库仓库、出库仓库/部门刷新在请求前保存旧选择，返回时可能覆盖等待期间的改选；公共调拨/盘点/领料仓库刷新虽在返回时读值，但与前三处均缺响应时序保护，旧列表可覆盖新列表。原生 GET 不检查 HTTP 状态，错误正文包含列表时也可能刷新。
- 修复：四个刷新函数复用 js/select-refresh.js，通过 WMS.api.getRaw 校验 HTTP/业务封套与完整列表，按实际 select 元素标记最新请求；应用时读取当前选择，忽略过期成功/失败及已脱离DOM的字段。禁用/只读历史字段不刷新；所选项确实移除时仅派发一次冒泡 change，保留现有领料库位清空联动；选择未变不派发，避免误清库位。调拨仓库名称与其他页面仓库ID契约不变。公共资源使用 STATIC_VERSION 和原加载顺序。生产需重启 WMS 服务生效。
- 同类点已排查：查询历史异步竞态 BUG-2026-10-23-010、库位联动及主数据刷新记录；覆盖入库/出库/出库部门/调拨/盘点/领料六类消费场景。销售模板加载为同步localStorage，AI确认updateSelect在同步渲染时读取当前值，非本根因；供应商/客户刷新是数组消费，未混入本批。未改库存写入、报表及仓库归属规则。
- 开工基线：6e47120cce1e3f3b29d744754ae4c7cd45f690bc的WMS CI40051176851与AI40051176864均completed/success；最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，祖先及Android工程/工作流无差异证明通过。修前相关五模块228 passed/21 skipped。
- 回归：执行真实刷新函数、api.js及公共转义函数的延迟请求测试78项，覆盖改选、响应乱序、最新请求失败、陈旧失败、HTTP错误、业务拒绝、畸形列表、移除选择、保留库位、只读、脱离DOM、转义及静默策略；旧代码48 failed/30对照passed，修后78 passed。另验证实际模板加载顺序、静态字节/年度缓存/ETag及版本增删改；现有领料用例仅加载新增共享依赖，原断言不放宽。
- 生效确认：2026-10-24 10:18代理完成下述生产核验；隔离验证未连接生产业务写入接口。

- 回退实证：文件备份后git checkout HEAD恢复四模板并临时移出新资源，新测试52 failed/30对照passed；finally完整恢复后82 passed。未使用stash，证据wms-select-rollback-ax83u7hc/rollback.log。隔离HTTP冒烟121/121，临时18080服务11404已停止，证据wms-shell-qa-299g18o1/smoke.log；未对生产运行写入冒烟。
- 最终本地验收：相关与相邻十模块364 passed/21既有skipped；普通规则0违规，Node语法检查、源码UTF-8检查及verify_wms_bugs通过。新增82项全部通过；首次加载测试因测试模块导入路径错误出现3项失败，修正为tests包路径后重新完整验收通过，未放宽任何断言。

- 首次CI与回滚：1cc36fdcffcc141a48445fbd6e8d1d0dd7f6aff3已实际push。WMS CI40052526272的unit-tests-shard-1出现1 failed/2472 passed/13 skipped；唯一失败为旧test_p1_6_requisition_check_adjustment_warehouse_id要求已迁移的String(current)比较表达式仍出现在HTML。遗漏该消费测试，本地复现1 failed/11 passed。按R8立即git revert为6939e88fb6c18e8a22ebbed3b8af67f06d656689；完整树与原6e47120一致、该模块12 passed。仅该次紧急回滚使用git push --no-verify，未使用WMS_SKIP_CI_GATE伪装失败状态；实际push和HEAD/origin/live均核验。生产未重启。回滚目标WMS CI40052774455与AI40052774571准确匹配completed/success；最新Android40027751562祖先及路径证明重新核验后才恢复本轮写入。
- 测试契约迁移：保留原测试字段/默认ID/collectHeader五项断言；将定位旧内联表达式的断言替换为实际渲染HTML加载共享资源检查，并执行该HTML中真实刷新函数、api.js及共享脚本的延迟改选场景，确保值为仓库ID且不变成名称。未放宽业务断言。新增用例仍验证全部六类消费点。
- 重新验收：补入遗漏模块后十一模块376 passed/21既有skipped/6既有SQLAlchemy告警。应用模板和静态资源与首次通过物理回退证明、隔离HTTP冒烟的1cc36fdc逐文件无差异；仅补测试及如实记录回滚过程。

- 发布验收：9b99893a9766d40764563c90fc9b54e69c4a8c62已实际git push（6939e88f..9b99893a main -> main），HEAD/origin/live main一致。[WMS CI40053359348](https://github.com/SIX2090/wms/actions/runs/40053359348)和[AI40053359370](https://github.com/SIX2090/wms/actions/runs/40053359370)均准确匹配completed/success，包括此前失败分片；发布目标check_ci_green.py --target-sha完整SHA --json返回ok=true。最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，祖先/完整对象与工程及工作流无差异证明通过；性能40053359360亦成功。证据target_ci.json保存在C:/wms_backups/select_refresh_deploy_20261024。
- 生产生效：沿用用户已明确授权的备份及原WMS-Warehouse计划任务重启流程。生产SQLite mode=ro在线一致性备份before_inventory.db，integrity_check=ok，SHA256为85f2c6db3059affae241cfb540714296e301318b99c06993aa82d6f63e478a7c；旧模板回退包与前后进程/数据摘要/HTTP证据均保存在上述目录。即时核对原PID2656创建时间、Python311路径、Session0、run_server.py命令与唯一8080监听；确认原任务SYSTEM入口及WMS_NO_DB_TOUCH=1，避开下一次计划触发后终止此唯一进程并启动原任务一次。新PID1656，2026-10-24T10:18:18.967578+08:00创建，同解释器/Session0/命令，8080唯一监听，LastTaskResult=0。10:18:22启动日志为9b99893、production、CSRF on；db-check migrate=ok仅结构检查，不声称执行迁移。
- HTTP与数据核对：本机与https://gd2026.top/login均GET200含CSRF；两端select-refresh.js均200、JavaScript类型、年度缓存，SHA256准确匹配磁盘cad62a263654015b3af8c612947ac2a92a9784316b23af95d70ef7d3a51aa335。物料、库位账、流水、入/出库头及行、用户八张核心表前后完整行摘要一致，quick_check=ok。未在生产登录执行冒烟或写业务记录，未更改账号密码、依赖、库存口径或服务入口。生产需重启 WMS 服务生效，本次已完成；收尾仅记录台账，应用文件不变，无须再次重启。


### BUG-2026-10-24-005: 物料搜索旧响应覆盖新上下文及入库自动补查报错

- 状态：已修复并发布；确认台子修复AI-UX-DOC-MATERIAL-SEARCH-001已完成，父任务AI-R08-F02。
- 根因/危害：入库自动补查对不返回Promise的refreshMaterials调用.then，400ms回调直接报错；重复重拉前300条缓存也无法可靠补查后部物料。入库/采购申请在防抖回调内才增加请求序号，改词至下一防抖触发的空窗、清空、切行、Escape和关闭均可能被旧响应回写。候选缓存丢失时使用模糊搜索恢复，受候选上限影响且缺当前行校验。入出库详情有同样的防抖空窗/关闭后回写，AI确认台全局及逐行筛选没有回包上下文保护。HTTP错误正文可被当成正常物料结果。
- 修复：删除入库过时的400ms重拉首300条逻辑，复用220ms服务端搜索结果做缺缓存编码的精确回填，已有单价和用途按原规则保留；有效编码输入后Tab离开仍可回填字段但不重新弹框。输入/清空/切行/选择/关闭立即作废旧请求，回包核对代次、实际输入与DOM存活；候选缓存恢复复用既有/material/api/by_codes精确GET。手动刷新返回Promise并保护最新缓存、提示和按钮解锁。采购申请保留原编码/名称完全相等才本地自动回填，不新增模糊自动选料。入出库详情保留原行内/模态框填料，关闭时取消防抖。AI确认台筛选及逐行按钮使用同一代次，手工选料也使旧筛选失效，保留已选项及人工确认门禁。五页读取统一使用WMS.api.get/getRaw校验HTTP/业务/数组结构，沿原本地缓存或空候选降级。生产需重启 WMS 服务生效。
- 同类点已排查：关联BUG-2026-09-22-004、P2服务端搜索历史、BUG-2026-10-23-010和BUG-2026-10-24-004，逐一跟踪全部/api/material/search模板/静态JS消费方。五个尚缺完整生命周期保护的页面均纳入；期初库存opening-stock.js已有即时序号、输入和关闭保护，保留并纳入相邻回归；出库新增及公共表单为本地筛选，不存在该搜索请求链。本次不是机械修复报告中的267个button：实际表单内缺type仅3个正常提交按钮，未当缺陷改动。库存算法、仓库口径、权限、密码及生产业务数据未改。
- 开工基线：fb772b096c14197b7140ee68522b1d6b1242c57b的WMS CI40053663362与AI40053663465准确匹配completed/success；最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、目标祖先及Android工程/工作流无差异证明通过。分批受影响基线114+142+8项通过，无存量失败。
- 回归锁：新增109项真实页面搜索/选择/刷新函数、原api.js及DOM事件的延迟HTTP测试，包含首次查询、缓存外编码、单一请求、大小写、快速改词/清空/切行/关闭/脱离DOM/Tab、乱序和陈旧失败、精确恢复、改选后旧包、HTTP错误携success正文、业务拒绝、畸形数据、断网、人工勾选、全局与逐行筛选互斥，以及缓存合并和最新按钮解锁。五模板最终物理备份、git checkout HEAD回退后84 failed/25正对照passed，finally恢复全部文件，不用stash；证据wms-material-final-rollback-utwh8nqo/rollback.log。旧P2静态断言仅跟随移到cancelMaterialSearch的取消实现，增加调用连接断言，未删除或放宽原断言。
- 生效确认：2026-10-24 11:07代理按下述证据确认生产已生效。全部录单/人工确认写入测试使用隔离数据库，未对生产执行写入冒烟。
- 本地扩展验收：相关与相邻19模块491 passed（12项既有SQLAlchemy告警）；随后补充直接查询取消旧定时器和详情页模态框8项场景，最终专项另行验收。隔离HTTP冒烟121/121，证据wms-shell-qa-9kd8ybt3/smoke.log，临时18080服务9416已停止。规则0违规、UTF-8编码及严格AI台账检查通过。
- 最终验收：补充8个直接查询与模态框场景后，专项及相邻145 passed（8项既有SQLAlchemy告警），包含全部109新运行时用例；完整AI验证python scripts/verify_ai_all.py --level full --jobs 2为70/70（sum=258.45s），其中verify_wms_bugs通过。旧静态检查跟随真实取消函数，原断言全部保留，未以降低断言换绿灯。
- 推送前门禁：匿名API出现HTTP403限流，仅属查询故障。已连接GitHub通道按main最新列表重新核实fb772b09的CI40053663362与AI40053663465均completed/success；最新Android40027751562成功且祖先/受保护路径无差异证明通过，live main与基线一致。替代证据wms-material-ci-alternative.json；仅本次push临时设置WMS_SKIP_CI_GATE=1并finally清除，不跳过实际失败或未知状态。

- 首次CI与回滚：821a37482302f4e7957c3125a464b7a20d07f7bc已实际push；WMS CI40055945109的unit-tests-shard-0为2 failed/2826 passed/31 skipped。遗漏了test_out_detail_transport_runtime的旧原生GET定位断言，以及test_document_material_keyboard单独加载handleKeydown时新增取消函数的真实依赖。业务回归/AI验证均已通过，但不据此发布；按R8立即revert为b4c389dcfd739ded35dfb7b5baeb0459870ddb53，完整Git树与原fb772b09一致，仅紧急回滚使用push --no-verify，已核对实际push与HEAD/origin/live一致，生产未重启。回滚目标WMS CI40056243320和AI40056243366准确匹配success，Android祖先与路径证明通过后才恢复写入。
- 扩大消费验证：全仓查找所有引用五个模板文件名的测试，回滚基线41模块686 passed（21既有告警）。键盘夹具加载生产materialSearchState声明和cancelMaterialSearch函数，完整保留原IME/方向键/提示行过滤/Enter/Escape断言；出库详情传输契约改为要求原搜索端点走WMS.api.getRaw并禁止旧raw GET，保留原12个POST、CSRF、端点和异常AI GET断言。未降低业务断言；重新应用的五模板与首次修复逐文件相同。
- 重新完整消费验收：43个直接模板消费模块795 passed（21项同基线SQLAlchemy告警）；已包含全部109项新增运行时与两个此前漏查模块。应用五模板与821a3748完全相同，复用该相同应用代码的70/70完整AI及121/121隔离冒烟证据，未重复全站测试。重推前以已连接GitHub重新核实b4c389dc的CI40056243320、AI40056243366及最新Android全绿，祖先/路径证明与live main核对通过；reapply_gate.json保存同基线证据。匿名查询仍属403故障，仅本次push临时WMS_SKIP_CI_GATE=1并finally清除。

- 发布目标验收：55a66d6ffd97c6b414741336a3541de2f3d05d04已实际push（b4c389dc..55a66d6f main -> main），HEAD/origin/live main一致。[WMS CI40056740245](https://github.com/SIX2090/wms/actions/runs/40056740245)和[AI40056740219](https://github.com/SIX2090/wms/actions/runs/40056740219)准确匹配completed/success；包括首次失败的单元测试分片。最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、祖先及Android工程/工作流无差异证明通过。性能40056740222亦成功。匿名API的403属于查询故障，发布前通过已连接GitHub最新main列表逐一确认，target_ci_alternative.json保存完整SHA/状态/链接；未把旧红或运行中视为放行。
- 生产发布：沿用用户已明确授权的在线备份及原WMS-Warehouse计划任务流程。初次before_inventory.db与旧五模板rollback_templates.zip保留；发布即时再次mode=ro在线一致性备份deploy_inventory.db，integrity_check=ok，SHA256为6e0819011c1b54ca8dcb9d2cda7f91a0eaea519f82d5ace7b66c1226b96f8aa5。即时核对原PID1656完整创建时间、Python311路径、run_server.py/Session0、唯一8080监听、SYSTEM任务入口及WMS_NO_DB_TOUCH=1，避开计划触发后仅终止此唯一实例，再启动原任务一次。新PID9460，2026-10-24T11:07:23.194661+08:00创建，同解释器/命令/Session0、8080唯一监听、LastTaskResult=0。11:07:26启动日志为55a66d6、production、CSRF on；db-check migrate=ok仅结构检查，不声称迁移。
- 只读验收：五模板规范化文本逐文件匹配目标Git对象，摘要保存在template_checks.json；本机与https://gd2026.top/login均GET200且含CSRF，统一api.js两端均JavaScript类型、含getRaw且SHA256与磁盘相同（44cd42da2cda7e59d0883fcde37cefa6341024723ad2dd47120d62d7b11c106d）。物料、库位账、流水、入/出库头及行、用户八张核心表前后完整行摘要一致，quick_check=ok。上述证据、备份、进程与HTTP记录均在C:/wms_backups/material_search_deploy_20261024。未登录生产执行冒烟或生成业务记录，未改账号密码、依赖、库存/仓库规则或服务入口。生产需重启 WMS 服务生效，本次已完成该重启；收尾仅文档/台账，应用代码保持55a66d6，无须再次重启。


### BUG-2026-10-24-006: 本地物料候选刷新只取第一页导致2000条后物料消失

- 状态：已修复并发布。
- 根因/危害：out_order_add、document_table_form及adjustment_add依赖完整本地物料缓存进行选料，但刷新只请求/material/api/all的默认第一页并立即清空替换原数组。接口每页上限2000且提供pages元数据；物料较多时，页面初始已有的后部物料会在刷新后消失，影响出库、BOM、调拨、盘点、领料及调整录入。旧读取未校验HTTP状态，乱序刷新也可覆盖新缓存。
- 修复：三个模板按需加载共享js/material-cache.js（api.js之后、页面脚本之前、STATIC_VERSION缓存）。显式page/per_page=2000顺序读取pages，校验总数/页数/页码/每页条数与有效且不重复的物料ID，完整收集后才替换原数组内容，保持数组身份。任一页HTTP/业务/结构失败，或发现总数/页数变化、重复记录时，保留旧缓存并提示重新刷新，不自动重试；仅最新请求可应用结果，旧成功和失败均忽略，旧finally不提前解锁较新的出库刷新。三个原提示与出库silent策略保留，不重填已录入行，不改后端接口、仓库/库存算法、单据写入或权限。生产需重启 WMS 服务生效。
- 同类点已排查：关联历史BUG-2026-08-04-010（原入库复制物料不可见/分页修复）及BUG-2026-10-24-004/005。全仓/material/api/all前端读取仅四处，三个完整缓存消费点全部修复；入库fetchMaterialsPage明确仅取前300条，其余走服务端搜索，是有意的初始缓存，不误改为整库加载。其他/api/material/all为另一接口，不混淆其契约。本轮收敛重复刷新逻辑，未机械添加构建系统或按静态数量改CSS。
- 开工基线：4ad9f2f1b7d7610e57291abb3c4dc5007dab1a33的WMS CI40057109518与AI40057109520准确匹配completed/success；最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、祖先及Android工程/工作流无差异证明通过。25个直接模板消费测试模块511 passed（29项既有SQLAlchemy告警），无存量失败。
- 回归锁：47项新增真实刷新函数/原api.js/共享加载器及延迟响应测试，覆盖2005条按2000+5完整载入、空列表、后页失败、HTTP错误携success正文、业务拒绝、无效数组/记录/页码、总数变化、重复ID、乱序、最新失败后的旧成功、陈旧失败静默、并发按钮锁、实际脚本顺序/版本/年度缓存/ETag。隔离SQLite真实/material/api/all两页读取同时验证2005有效物料及停用过滤。物理备份三个模板并git checkout HEAD回退、临时移出新资源，新测试38 failed/9正对照passed；finally完整恢复，不用stash，证据wms-material-cache-rollback-enl5iyrl/rollback.log。
- 生效确认：2026-10-24 11:35代理完成下述生产核验；测试写入仅内存隔离库，未在生产登录、生成单据或修改库存/密码。
- 最终本地验收：25个直接模板消费模块加新增分页/资源/版本及台账回归合计580 passed（29项同基线SQLAlchemy告警）；隔离HTTP冒烟121/121，wms-shell-qa-dkthd7fx/smoke.log，临时服务2208已停止。Node语法、源码UTF-8、普通规则0违规及verify_wms_bugs通过。提交前check_ci_green.py --target-sha完整基线 --json再次ok=true，三工作流及Android祖先/受保护路径证明齐全。

- 目标CI与推送：3e51e922b74253406f2b828b2ac4ea01a2d91468已实际push（4ad9f2f1..3e51e922 main -> main），HEAD/origin/live main一致。[WMS CI40058640306](https://github.com/SIX2090/wms/actions/runs/40058640306)及[AI40058640300](https://github.com/SIX2090/wms/actions/runs/40058640300)准确匹配completed/success；性能40058640274亦success。最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、目标祖先和工程/工作流无差异证明通过。发布前匿名check_ci_green查询出现HTTP403限流，仅属查询故障；通过已连接GitHub最新main列表逐一核实同目标三工作流全绿，完整SHA/链接/状态及范围证明保存于target_ci_alternative.json。
- 生产发布：沿用用户已明确授权的备份及原WMS-Warehouse任务重启流程。保留before_inventory.db及旧三模板rollback_templates.zip，发布即时再次mode=ro在线一致性备份deploy_inventory.db，integrity_check=ok，SHA256为7df2ee4a1dd62995583c38106f60e16b1901e5ecc921c520da551c27b05b31fd。即时核对原PID9460完整创建时间、Python311路径、run_server.py/Session0、唯一8080监听及原SYSTEM任务入口、WMS_NO_DB_TOUCH=1，避开下一计划触发后仅终止该唯一实例，再启动原任务一次。新PID152，2026-10-24T11:35:15.936945+08:00创建，同解释器/命令/Session0、唯一8080监听、LastTaskResult=0。11:35:19启动日志为3e51e92、production、CSRF on；db-check migrate=ok仅结构校验，不声称执行迁移。
- 只读验收：三个模板规范化文本逐文件匹配目标Git对象；本机和https://gd2026.top/login均GET200且含CSRF，material-cache.js两端均200、JavaScript类型、年度缓存，SHA256为66a53f641474843943882ce93c16b3780eaf256c3ff6ee6b35aa18ab55a1fa6c并准确匹配磁盘。八张核心表（物料、库位账、流水、入/出库头及行、用户）前后完整行摘要一致，quick_check=ok。备份、回退包、模板/HTTP/进程/数据摘要及CI证据均在C:/wms_backups/material_cache_deploy_20261024。未在生产登录执行冒烟或生成业务记录，未改密码、依赖或服务入口。生产需重启 WMS 服务生效，本次已完成；收尾仅记录台账，应用代码不变，无须再次重启。
- 收尾门禁：若同次pre-push仍因匿名API的403查询故障拒绝，以已核实的3e51e922全绿及Android范围证明为替代，仅该次push临时WMS_SKIP_CI_GATE=1并finally清除；不跳过实际非绿或未核实状态。


### BUG-2026-10-24-007: 客户、供应商及物料主数据数组刷新被旧响应覆盖

- 状态：已修复并生产生效（2026-10-24 12:13）。
- 根因/危害：入库refreshSuppliers、出库与售后refreshCustomers，以及物料refreshQuickSelectData均在每次请求返回时直接清空并覆盖数组，没有请求代次。连续主数据广播后，较早快照晚返回可覆盖新建/改名记录；前三处原生GET还未校验HTTP状态，合法JSON的HTTP错误不能可靠进入失败路径。物料页虽用getRaw，但缺少记录/重复ID校验及请求代次。错误对象被静默忽略，操作员无法据此判断刷新是否成功。
- 同类点已排查：查询BUG-2026-08-25-001、BUG-2026-10-23-010及本月异步刷新记录；完整数组缓存覆盖入库供应商/其他入库客户、出库客户、售后客户、物料分类/单位/供应商七种模式。四个相关API在native_api.py使用all()返回完整数组，不套用物料分页接口的封套。原生select元素生命周期与远端物料分页由既有各自实现处理，本批限定完整主数据数组缓存。
- 修复：新增公共js/list-cache.js，按数组引用用WeakMap标记最新请求，使用WMS.api.getRaw的HTTP/会话检查并验证完整数组、每行id/name和重复ID，仅最新有效结果原地替换数组。任意失败保留旧缓存，过期成功/失败不覆盖、不误报；空列表合法清空，数组引用不变。保留入库partyField端点分流、原有静默刷新和现有选中字段，不新增数据写入。公共布局同步、带STATIC_VERSION加载；专题静态资源文档同步。
- 修复前基线：81个直接引用五个模板的模块及master_data_frontend_api全量，1558 passed、21 skipped、15项既有SQLAlchemy警告，日志为%TEMP%/wms-party-baseline.log。新增旧代码回归88项中64 failed、24 passed，修复后88 passed；再追加三种缓存并行独立性共91 passed。
- 回归锁/物理回退：按文件备份→git checkout --五模板→临时移除自有新增脚本→执行新增测试→finally恢复五模板与脚本；旧代码64 failed、24 passed，恢复后91 passed。证据%TEMP%/wms-party-rollback-8ti_enje/rollback.log。未使用stash，未改既有断言。
- 回归/门禁：85个受影响及相邻模块全量1664 passed、21 skipped、15项既有警告（%TEMP%/wms-party-final.log）；隔离HTTP冒烟121/121且自有18080服务已停止（%TEMP%/wms-party-smoke.log）；A1–A14为0违规、node --check、UTF-8编码及verify_wms_bugs均通过，目标提交CI验收见下。提交前check_ci_green.py --target-sha完整基线 --json再次ok=true，证据保存于C:/wms_backups/party_refresh_deploy_20261024。开工基线ced379e50e7388b318bb10eff8d1898f9b9d5992的WMS CI40059042554、AI40059042549均completed/success；最新Android40027751562的ec3a04b32d64b1f172ec5446adf5127400ac5a87为祖先，完整对象且工程/工作流无差异。
- 生效确认：2026-10-24 12:13由Codex核对目标CI、在线备份、原WMS-Warehouse任务重启及生产只读证据后确认。生产需重启 WMS 服务生效，本次已完成；完整证据保存在C:/wms_backups/party_refresh_deploy_20261024。

- 目标CI与推送：8adfe13035ef816c73d30a691f693f9e3c25fff3已实际push（ced379e5..8adfe130 main -> main），HEAD/origin/live main一致。[WMS CI40061109875](https://github.com/SIX2090/wms/actions/runs/40061109875)和[AI40061109870](https://github.com/SIX2090/wms/actions/runs/40061109870)准确匹配completed/success，WMS CI全部单元/回归分片、静态检查、冒烟及gate均成功；性能40061109873亦success。最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、目标祖先及工程/工作流无差异证明通过。发布与收尾前check_ci_green.py --target-sha完整目标 --json均ok=true，target_ci.json/closure_baseline_ci.json及连接器替代证据留存。
- 生产发布：保留before_inventory.db和旧五模板rollback_templates.zip，发布即时mode=ro在线一致性备份deploy_inventory.db，integrity_check=ok，SHA256为41682964241cc41d4213a36b2f544bda5bfd8fe9c2e32152c88b5aa013b1f689。即时核对原PID152完整创建时间、Python311解释器、run_server.py/Session0、唯一127.0.0.1:8080监听、原SYSTEM任务入口和WMS_NO_DB_TOUCH=1；避开下一计划触发窗口后仅终止该实例，再启动原任务一次。新PID9616，2026-10-24T12:13:30.794639+08:00创建，同解释器/命令/Session0、唯一监听、LastTaskResult=0。12:13:34启动日志为8adfe13、production、CSRF on；db-check migrate=ok是结构检查，不声称执行迁移。
- 只读验收：五模板规范化文本逐文件匹配目标Git对象；本机和https://gd2026.top/login均GET200且含CSRF；list-cache.js两端均200、JavaScript类型、年度缓存，SHA256为dc5bd13765293036db32fbf38c279a4a79e56921b8a9e55d7cbb11098adc75ab且匹配磁盘。八张核心表（物料、库位账、流水、入/出库头及行、用户）前后完整行摘要一致，quick_check=ok。未在生产执行登录冒烟或生成业务记录，未改密码、依赖或服务入口。
- 收尾边界：本次仅回填月度BUG台账的验证与生效证据；应用文件保持已发布8adfe130版本，无须再次重启。按白名单文档分级验证并验收该收尾提交自身的CI；如查询故障，遵循已核实同基线证据规则，不把未知或实际非绿视为放行。


### BUG-2026-10-24-008: 公共主数据下拉刷新失败清空选择且误操作隐藏字段

- 状态：已修复并生产生效（2026-10-24 13:50）。
- 根因/危害：app.js的WmsRefreshDropdowns在DOMContentLoaded自动刷新分类/单位/供应商，网络失败被catch转换成空数组再清空选项，HTTP错误也没有状态检查；有效的当前选择因此丢失。选择器只按name匹配，会给物料新增、采购单等自定义搜索控件的同名隐藏ID输入框添加option子节点；禁用、已脱离DOM的字段和较新请求结果也未保护。
- 同类点已排查：检查历史BUG-2026-10-24-004/007、BUG-2026-08-25-001及下拉/隐藏字段记录。公共原生select按category_id、unit_id、supplier_id三个名字统一修复，分类/单位/供应商接口均返回完整数组。物料页的WmsRefreshDropdowns覆盖为list-cache数组刷新，属于007且不改；原有仓库/部门封套及领料库位联动仍由select-refresh处理并回归。不修改库存、仓库归属、权限或单据保存逻辑。
- 修复：公共刷新仅匹配select[name=...]，三个接口分别调用已有WMS.selectOptions.refresh，失败各自保留原选择/选项且不影响其余接口，保持原自动静默策略。共享组件增加无itemsKey时校验完整数组的分支，原封套契约不变；复用HTTP/会话检查、逐元素最新请求保护、应用时当前值、disabled/isConnected保护、文字转义及仅失去有效选择才派发一次冒泡change的既有能力。没有新增公共资源，也不再对隐藏输入框发起无效刷新。
- 修复前基线：45个直接消费app.js或select-refresh.js的模块全量1447 passed、21 skipped、6项既有SQLAlchemy警告，日志%TEMP%/wms-global-select-baseline.log。新增60项真实公共函数/原api.js/共享组件/DOM延迟HTTP回归在旧实现48 failed、12 passed，初次修复后的新旧刷新测试合计142 passed。
- 回归锁/物理回退：备份app.js与select-refresh.js→git checkout --两文件→执行新回归→finally恢复两文件；旧实现48 failed、12 passed。回退证据%TEMP%/wms-global-select-rollback-cx7q38uu/rollback.log；恢复后的最终60项全部通过。没有使用stash或修改旧断言。
- 回归/门禁：48个模块全量与相邻回归1608 passed、21 skipped、6项既有警告（%TEMP%/wms-global-select-final.log）；覆盖旧仓库/部门刷新、领料库位联动和上一轮七种数组缓存场景。隔离HTTP冒烟121/121且自有18080服务已停止（%TEMP%/wms-global-select-smoke.log）。A1–A14为0违规、两个JS的node --check、UTF-8编码及verify_wms_bugs均通过。提交前check_ci_green.py --target-sha完整基线 --json为ok=true，证据、在线备份及旧两资源回退包保存于C:/wms_backups/global_select_deploy_20261024。开工基线2a7fccccf27c202a9a6d96c28527429be3162500的WMS CI40061588231、AI40061588214均completed/success；最新Android40027751562的ec3a04b32d64b1f172ec5446adf5127400ac5a87为祖先且工程/工作流无变化。
- 生效确认：2026-10-24 13:50由Codex核对目标CI、在线备份、原任务重启、静态资源和生产只读摘要后确认。JS静态缓存版本在启动时计算，生产需重启 WMS 服务生效，本次已完成。完整证据在C:/wms_backups/global_select_deploy_20261024。

- 目标CI与推送：a1f634b1d68e39b2ef762f4a05ab6f7b386e105c已实际push（2a7fcccc..a1f634b1 main -> main），HEAD/origin/live main一致。[WMS CI40067400139](https://github.com/SIX2090/wms/actions/runs/40067400139)和[AI40067400130](https://github.com/SIX2090/wms/actions/runs/40067400130)准确匹配completed/success，全部单元/回归分片、静态检查、冒烟及gate成功；性能40067400143亦成功。最新Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、目标祖先及工程/工作流无差异证明通过。匿名check_ci_green查询HTTP403限流仅属查询故障，发布与收尾前通过已连接GitHub最新main列表逐一核实；target_ci_alternative.json和closure_baseline_ci_alternative.json保存完整SHA、链接、状态及范围证明。
- 生产发布：保留before_inventory.db与旧两JS的rollback_assets.zip，发布即时mode=ro在线一致性备份deploy_inventory.db，integrity_check=ok，SHA256为73bf033214d686b15fcdbc05a8523d982dfcf48a4ff803b377198f0622e60d33。即时核对原PID9616完整创建时间、Python311解释器、run_server.py/Session0、唯一127.0.0.1:8080监听、原SYSTEM任务入口与WMS_NO_DB_TOUCH=1；避开下一计划触发窗口后仅终止该实例，再启动原任务一次。新PID11460，2026-10-24T13:49:58.622289+08:00创建，同解释器/命令/Session0、唯一监听、LastTaskResult=0。13:50:02启动日志为a1f634b、production、CSRF on；db-check migrate=ok仅结构检查，不声称迁移。
- 只读验收：两个JS规范化文本逐文件匹配目标Git对象；本机和https://gd2026.top/login均GET200且含CSRF；app.js和select-refresh.js两端均200、JavaScript类型、年度缓存，分别SHA256为cb3ddac90d31cb64c69ac61bcffe69441096af38dbfa28e745e34e3c18b9cb19、0e6bc230d7c3dca7bb5e5f3d9e0f790ab3dc770aec8d92372cfb0b671a1fcfb3且匹配磁盘。八张核心表（物料、库位账、流水、入/出库头及行、用户）前后完整行摘要一致，quick_check=ok。未在生产登录执行冒烟或创建业务记录，未改密码、依赖或服务入口。
- 收尾门禁：仅月度BUG台账记录更新，应用文件保持已发布a1f634b1版本，无须再次重启；验收文档分级检查和该收尾提交自身CI。若同次pre-push仍因匿名API的403查询故障拒绝，以已核实的同一a1f634b1基线全绿及Android范围证明为替代，仅该次push临时WMS_SKIP_CI_GATE=1并finally清除；不跳过实际非绿或未核实状态。


### BUG-2026-10-24-009: 公共单据单位刷新覆盖行选择并静默回退默认单位

- 状态：已修复并生产生效（2026-10-24 15:16）。
- 根因/危害：document_table_form.html的refreshUnits在unit_updated广播时用原生GET直接覆盖units并重填所有.unit-id，无请求代次、HTTP检查及readonly/disabled保护。较旧列表晚返回可移除刚新建并选中的单位，重填后select.value变空；collectItems随后用物料默认单位回退，改变操作员选择的实际保存载荷。只读单据及禁用行的历史显示也可能被广播改写。
- 同类点已排查：检查BUG-2026-10-24-004/007/008与BUG-2026-08-25-001。此行单位重建入口只有一处，覆盖BOM、调拨、盘点和工单领料四模式；其它完整数组缓存及全局分类/单位/供应商select分别已有007/008治理。/api/units返回完整数组，不使用分页或物料封套。物料新增的本地新增后push没有本批的异步整表覆盖。不改collectItems、单位删除引用保护、库存/数量算法、权限或业务保存接口。
- 修复：复用WMS.listCache.refresh的HTTP、数组/行/重复ID校验及最新请求保护，只在有效最新结果后更新行选项。readonly页不发请求；应用时跳过disabled和已脱离DOM字段，读取当时当前选择，若新列表暂缺该单位则原DOM选项回插，保留名称和ID，避免默认单位替换。新建行使用最新缓存；现有数组身份、自动静默策略及数量/价格不变。unitOptions的ID属性同步HTML转义，与既有名称转义一起保证安全文本渲染。生产需重启 WMS 服务生效。
- 修复前基线：16个模板/list-cache直接消费模块533 passed、24项既有SQLAlchemy警告（%TEMP%/wms-unit-refresh-baseline.log）。新增84项真实refreshUnits/unitOptions/collectItems、原api.js及共享缓存的延迟请求回归，旧实现52 failed、32 passed；修复后与既有缓存/零价格测试合计179 passed。
- 回归锁/物理回退：备份单模板→git checkout --单模板→执行新增84项→finally恢复；旧实现52 failed、32 passed。回退证据%TEMP%/wms-unit-refresh-rollback-iy44uyxp/rollback.log；恢复后84项全部通过。未使用stash或修改旧断言。
- 回归/门禁：20个受影响/相邻模块全量756 passed、24项既有SQLAlchemy警告（%TEMP%/wms-unit-refresh-final.log），包括单位保存载荷、零价格、键盘/粘贴、完整物料缓存分页、仓库/部门刷新和领料库位联动。隔离HTTP冒烟121/121且自有18080服务已停止（%TEMP%/wms-unit-refresh-smoke.log）；A1–A14为0违规、JS实际运行、UTF-8编码及verify_wms_bugs均通过。提交前check_ci_green.py --target-sha完整基线 --json为ok=true，证据、在线备份及旧模板回退包在C:/wms_backups/unit_refresh_deploy_20261024。开工基线56d67971ecc43f841fd7e451cbdaf9652543eb7b的WMS CI40068086907、AI40068086878均completed/success；Android40027751562的ec3a04b32d64b1f172ec5446adf5127400ac5a87为祖先且工程/工作流无变化。
- 生效确认：2026-10-24 15:16由Codex核对目标CI、在线备份、原任务重启、模板/脚本及生产只读摘要后确认。生产需重启 WMS 服务生效，本次已完成；完整证据在C:/wms_backups/unit_refresh_deploy_20261024。

- 目标CI与推送：ee25dfcdd8203fc17e03c8e46b5336cc30ae4989已实际push（56d67971..ee25dfcd main -> main），HEAD/origin/live main一致。[WMS CI40073215257](https://github.com/SIX2090/wms/actions/runs/40073215257)和[AI40073215231](https://github.com/SIX2090/wms/actions/runs/40073215231)准确匹配completed/success；公共REST jobs列表核对全部单元/回归分片、静态检查、冒烟及gate均成功。Android40027751562在ec3a04b32d64b1f172ec5446adf5127400ac5a87成功，完整对象、目标祖先及工程/工作流无差异证明通过。连接器一度出现传输错误，未据此判定CI失败或放行；改用公共REST与仓库检查脚本核实，发布/收尾前check_ci_green.py --target-sha完整目标 --json均ok=true（target_ci.json、closure_baseline_ci.json）。
- 生产发布：保留before_inventory.db和旧单模板rollback_templates.zip，发布即时mode=ro在线一致性备份deploy_inventory.db，integrity_check=ok，SHA256为ef3cf39b8f5175287222f49bb36a7feb2c99e9505f2e740a63f271d70d665a78。即时核对原PID11460完整创建时间、Python311解释器、run_server.py/Session0、唯一127.0.0.1:8080监听、原SYSTEM任务入口及WMS_NO_DB_TOUCH=1；避开下一计划触发窗口后仅终止该实例，再启动原任务一次。新PID11996，2026-10-24T15:16:51.560092+08:00创建，同解释器/命令/Session0、唯一监听、LastTaskResult=0。15:16:55启动日志为ee25dfc、production、CSRF on；db-check migrate=ok仅结构检查，不声称迁移。
- 只读验收：共享模板规范化文本匹配目标Git对象，SHA256为0cdc2e734caa607ce1f14859562a1c4e86750e3e979921e5818f788d30550fa5；本机和https://gd2026.top/login均GET200且含CSRF；list-cache.js两端均200、JavaScript类型、年度缓存，SHA256为dc5bd13765293036db32fbf38c279a4a79e56921b8a9e55d7cbb11098adc75ab且匹配磁盘。八张核心表（物料、库位账、流水、入/出库头及行、用户）前后完整行摘要一致，quick_check=ok。未在生产登录执行冒烟或创建业务记录，未改密码、依赖或服务入口。
- 收尾边界：仅月度BUG台账记录更新，应用文件保持已发布ee25dfcd版本，无须再次重启；按文档分级验证并验收该收尾提交自身CI。查询故障仍须核实同一基线，不把未知、运行中或实际非绿视为放行。


### BUG-2026-10-24-010: 标签预览忽略所选物料并遗漏设计器布局

- 状态：已修复并生产生效（2026-10-24 16:20）。
- 根因/危害：preview_label_template未读取material_id，label_preview.html两张标签写死TEST001/TEST002示例；下拉加载后自动显示首个物料却没有selected，选择任意物料后仍打印示例。预览仅识别旧行列键，设计器cells布局变成占位空格；页面正文还落在extra_css块并自行关闭head/打开body，破坏公共布局结构。
- 同类点已排查：查阅BUG-2026-09-08-001、LABEL-FIX-2026-09-29-001/002/003及BUG-2026-10-23-006/007。预览入口为标签模板列表的preview_label_template；print_labels和print_batch_labels已有真实物料/布局读取，保留并纳入相邻回归。本轮修复单预览链，不更改实际批量打印入口、权限、库存口径或模板保存。
- 修复：预览GET严格解析正数物料ID，找不到返回404、非法值返回400；选中物料显示一张真实标签并保持下拉选择，无选择明确标为使用示例数据且可切回。统一数据映射支持单位/分类/供应商别名、日期、零价格和缺失关系；条码及二维码用url_for编码真实物料编码。复用已有布局解析/归一逻辑，cells坐标优先，支持静态文字、合并列和按比例行高；无效历史布局降级为空网格。正文进入base的content块，打印隐藏物料选择面板。生产需重启 WMS 服务生效。
- 修复前基线：20个标签/打印/权限等直接消费及相邻模块247 passed、12项既有SQLAlchemy警告，日志%TEMP%/wms-label-preview-baseline.log。新增26项最初在旧实现25 failed、1 passed；补齐布局边界、GET只读及选择切回运行测试后共34项通过。
- 回归锁/物理回退：备份路由和模板→git checkout --两文件→新增34项测试→finally恢复；旧实现30 failed、4 passed，证据%TEMP%/wms-label-preview-rollback-qi6tz3p6/rollback.log。未使用stash、未放宽既有断言。新用例以真实Flask GET和真实Jinja渲染核验字段/布局/编码/选择/状态码/结构，Node执行真实切换函数；数据库为内存隔离库。
- 开工门禁：6135f6d817f92e7323ffeac2ee364ab45fc9a0a4的WMS CI40073615902、AI40073615973均completed/success；最新Android40027751562的ec3a04b32d64b1f172ec5446adf5127400ac5a87为祖先且工程/工作流无变化，check_ci_green.py为ok=true。在线备份before_inventory.db与旧路由/模板rollback_code.zip保存于C:/wms_backups/label_preview_deploy_20261024。
- 回归验收：21个受影响/相邻模块281 passed、47项既有SQLAlchemy接口弃用警告（含新测试触发的35次）；台账/文档契约34 passed；隔离HTTP冒烟121/121，自有18080服务已停止。A1–A14为0违规、UTF-8编码检查通过。日志为%TEMP%/wms-label-preview-final.log、wms-label-preview-docs.log、wms-label-preview-smoke.log。
- 生效确认：2026-10-24 16:20由Codex核验目标CI、在线备份、原任务重启和生产只读摘要后确认。生产需重启 WMS 服务生效，本次已完成；证据位于C:/wms_backups/label_preview_deploy_20261024。

- 目标CI与推送：b73e9c4d8257ea746885cbf48b35971c0575e77d已实际push（6135f6d8..b73e9c4d main -> main），HEAD/origin/live main一致。[WMS CI40077396472](https://github.com/SIX2090/wms/actions/runs/40077396472)、[AI40077396520](https://github.com/SIX2090/wms/actions/runs/40077396520)精确匹配completed/success，性能40077396515亦成功。Android40027751562祖先、完整对象及保护路径无变化证明由check_ci_green.py核验通过。发布与收尾前完整目标检查均ok=true（target_ci.json、closure_baseline_ci.json）；verify_wms_bugs亦通过。
- 生产发布：即时在线备份deploy_inventory.db的integrity_check=ok，SHA256为01ef5ee8d36ba2c500298786960f55f20961e682674229b88484b2fc433f3eec；旧路由/模板回退包与开工备份保留。核对原PID11996完整创建时间、Python311解释器、run_server.py/Session0、唯一127.0.0.1:8080监听、SYSTEM任务原入口和WMS_NO_DB_TOUCH=1；避开计划触发窗口后仅终止该实例并启动原任务一次。新PID2828，2026-10-24T16:20:55.379873+08:00创建，同解释器/命令/Session0，唯一监听，LastTaskResult=0。16:20:58日志版本b73e9c4、production、CSRF on；db-check migrate=ok仅结构检查，不声称执行迁移。
- 只读验收：路由与模板规范化文本逐文件匹配发布Git对象，SHA256分别b87bb86f499a31c5efd11d4531bdb723dac0584681ad5c6a300f735761ba9d9e、91391898d36de5c8a3f96a81aabf0ad77bbe0d379e92cb0e384e01a3da96b59b。本机及https://gd2026.top/login均GET200并含CSRF；八张核心表前后完整行摘要一致，quick_check=ok。未在生产登录执行冒烟、创建业务记录或触发实体打印；未改账号密码、依赖或服务入口。
- 收尾边界：本次仅补月度BUG台账，应用文件仍为已生效b73e9c4d版本，无须再次重启；文档契约及收尾提交自身CI须通过后再汇报完成。


### BUG-2026-10-24-011: 标签打印选中集合混用数字与字符串导致错选

- 状态：已修复并生产生效（2026-10-24 16:31）。
- 根因/危害：print_label.html初始化和全选将dataset.materialId字符串放入Set，真实onchange传入Jinja输出的数字ID；取消勾选delete(number)无法删除字符串，打印选中仍包含取消的标签。全不选后重新勾选add(number)又无法被has(string)找到，造成漏打。初始化还忽略复选框当前checked，浏览器恢复未勾选状态时与内部集合不符。
- 同类点已排查：检索全仓selectedMaterials/toggleMaterial以及历史标签选择/打印条目，问题状态集仅在该打印模板；print_batch_labels无此Set，上一轮preview仅GET选择无打印勾选集。实际入/出库打印自动流程与标签字段、行高、权限模块纳入相邻回归。三个复选框查询同步限定.label-item-wrapper，防止全选/全不选误改公共设置控件。
- 修复：toggleMaterial入口把ID统一成String，与初始化/全选/打印检查一致；初始化尊重真实checked状态。保留原打印选中、打印全部、取消选择以及打印后恢复显示行为，无自动打印、数据写入或权限变更。生产需重启 WMS 服务生效。
- 修复前基线：8个受影响及相邻模块79 passed、47项既有SQLAlchemy弃用警告（%TEMP%/wms-label-selection-baseline.log）。新增10项用真实Jinja渲染的数字ID事件处理器和真实整段页面JS，记录window.print调用时实际可见标签集合，覆盖初始化/逐项取消/全取消/重选/全选后取消/反复切换/字符串ID兼容/浏览器恢复/无关复选框/无自动打印。
- 回归锁/物理回退：新测试旧实现7 failed、3 passed；修复后10 passed。备份模板→git checkout --模板→新测试→finally恢复，仍7 failed、3 passed，证据%TEMP%/wms-label-selection-rollback-gpdtj5nh/rollback.log。未使用stash或修改既有断言，未触发实体打印。
- 开工门禁：f4df9079a199dd84f4d9a049d367871b17be0fee的WMS CI40077732602、AI40077732583均completed/success；最新Android40027751562为目标祖先且工程/工作流无差异，check_ci_green.py为ok=true。此前文档CI仍运行时仅只读排查和基线测试，转绿后才写入本批。在线备份和旧模板回退包位于C:/wms_backups/label_selection_deploy_20261024。
- 回归验收：9个受影响/相邻模块89 passed、47项既有SQLAlchemy弃用警告（%TEMP%/wms-label-selection-final.log）；台账/文档契约34 passed；隔离HTTP冒烟121/121，已停止自有18080服务（wms-label-selection-smoke.log）。A1–A14为0违规、UTF-8编码及git diff --check通过。
- 生效确认：2026-10-24 16:31由Codex核对目标CI、在线备份、原任务重启及生产只读摘要后确认。生产需重启 WMS 服务生效，本次已完成；证据在C:/wms_backups/label_selection_deploy_20261024。

- 目标CI与推送：d927e0ca0666c4576bf677fe79bc8a47708eadc6已实际push（f4df9079..d927e0ca main -> main），HEAD/origin/live main一致。[WMS CI40078058179](https://github.com/SIX2090/wms/actions/runs/40078058179)、[AI40078058139](https://github.com/SIX2090/wms/actions/runs/40078058139)精确匹配completed/success；最新Android40027751562为祖先、Git对象齐全且保护路径无变化。匿名API一度403限流，仅判为查询故障；通过已连接GitHub最新main列表逐一核实三个工作流，并保存target_ci_alternative.json、closure_baseline_ci_alternative.json完整SHA/链接/状态和Git范围证明。verify_wms_bugs全部通过。
- 生产发布：即时在线备份deploy_inventory.db的integrity_check=ok，SHA256为c07a9e8df826ca0dae65a7638d80f98cdf57e85aa48c13e4b7ffb43462c1cfd8，保留开工备份及旧模板回退包。核对原PID2828完整创建时间、Python311解释器、run_server.py/Session0、唯一127.0.0.1:8080监听、SYSTEM任务原入口及WMS_NO_DB_TOUCH=1；避开计划触发窗口后仅终止该实例并启动原任务一次。新PID12044，2026-10-24T16:31:11.232266+08:00创建，同解释器/命令/Session0、唯一监听、LastTaskResult=0。16:31:14日志为d927e0c、production、CSRF on；db-check migrate=ok只证明结构检查，不声称执行迁移。
- 只读验收：模板规范化文本匹配发布Git对象，SHA256为b1f20ed22bb39a8d35ce8e65f999d196ae63a1f3dedfb60fc3c91e84dd23aa78；本机及https://gd2026.top/login均GET200且含CSRF。八张核心表前后完整行摘要一致，quick_check=ok。未在生产登录跑冒烟、改业务记录或密码，也未触发实体打印。
- 收尾边界：只补月度BUG台账，应用保持已生效d927e0ca，无须再次重启；验收文档契约和收尾提交自身CI。如同次pre-push仍因匿名403无法核实，仅在以上同一远端基线全绿及Android范围证明成立时，按既有规则单次临时WMS_SKIP_CI_GATE=1并finally清除，不跳过实际非绿或未核实状态。


### BUG-2026-10-24-012: 网页缺少退出当前账号入口

- 状态：已修复并生产生效（2026-10-24 16:55）。
- 根因/危害：user_auth已有/logout路由并正确清除会话及记住我Cookie，但base公共导航无链接，用户无法从页面退出当前账号。直接添加普通侧栏链接又会被enableMultiOpenMenus改成内部标签页，留下旧的外层工作区。
- 同类点已排查：核对AI-LOGIN-F02记住我退出清理历史、用户/认证路由和Android独立登出记录；后端能力已有且不重复实现。网页入口对所有登录角色开放，复用桌面/手机公共侧栏；Android已有自己的退出功能，本批不改APK或令牌撤销策略。
- 修复：在「我的资料」下方增加「退出登录」入口，target=_top使其退出整个当前窗口；菜单多开初始化跳过明确要求_top的链接。复用既有/logout的session.clear→logout_user→登录页流程，未改密码、账号角色或后端鉴权。README补充电脑/手机入口及退出前保存提示。生产需重启 WMS 服务生效。
- 回归设计：新增8种角色入口渲染、匿名不显示、真实菜单初始化不包装退出链接但保留普通多开行为，以及勾选/未勾选记住我两种真实Flask登录→点击实际渲染退出URL→Cookie清理→受保护页面回登录测试；仅内存数据库和临时账号。新测试修前11 failed、1 passed，初次修复与既有记住我测试17 passed。
- 开工门禁：7933eba63e5e21094d23ca02705f8beca8d5454a的WMS CI40078418519、AI40078418529均completed/success；最新Android40027751562的ec3a04b32d64b1f172ec5446adf5127400ac5a87为祖先且保护路径无差异、对象齐全。匿名API限流后经已连接GitHub核实最新main三工作流，替代证据保存在C:/wms_backups/logout_entry_deploy_20261024/baseline_ci_alternative.json。
- 生效确认：2026-10-24 16:55由Codex核对目标CI、原任务重启、版本日志、服务响应与业务摘要后确认；生产需重启 WMS 服务生效，本次已完成。证据目录C:/wms_backups/logout_entry_deploy_20261024。

- 基线与回退验证：原代码82个受影响/相邻模块2249 passed、21 skipped、3项既有SQLAlchemy弃用警告；备份base.html/app.js后物理回退，新测试11 failed、1 passed，再由finally恢复补丁，证据%TEMP%/wms-logout-rollback-5lp4ypjg。初次基线未结束提前应用补丁后已纠正，废弃该次结果，以上为重新执行完整旧代码基线。
- 浏览器验收：独立18080服务与临时smoke.db完成121/121 HTTP冒烟；内置浏览器实际登录临时管理员，侧栏显示退出入口且不附加新开页面按钮，点击后整个窗口回/login，再访问/admin/console回/login?next=/admin/console；截图保存在C:/wms_backups/logout_entry_deploy_20261024。临时服务已停止，未在生产登录或操作账号。
- 回归验收：83个受影响/相邻模块2261 passed、21 skipped、3项既有SQLAlchemy弃用警告（%TEMP%/wms-logout-final.log）；文档契约34 passed、隔离HTTP冒烟121/121；verify_wms_bugs全部通过、A1–A14为0违规、UTF-8编码与git diff --check通过。未削弱既有断言。
- 提交与CI：24b427c51e2bddba63c2714c23b6e74c6cf0cfe5已push（7933eba6..24b427c5 main -> main），HEAD/origin/live main一致。[WMS CI40079662746](https://github.com/SIX2090/wms/actions/runs/40079662746)、[AI40079662792](https://github.com/SIX2090/wms/actions/runs/40079662792)均精确匹配completed/success；最新Android40027751562为祖先，Git对象齐全且Android工程/工作流无差异。匿名API与pre-push均HTTP403，仅属查询故障；已连接GitHub核实同一实时远端基线最新三工作流及范围证明后，按规则单次WMS_SKIP_CI_GATE=1重推，finally清除。保存baseline_ci_alternative.json、target_ci_alternative.json与push.log。
- 生产发布：在线备份deploy_inventory.db完整性通过，SHA256为61af927d6414327ca95b3fc67f3ea240a8d4882a44fb02cabbe9db354d2515f0，保留旧代码rollback_code.zip。核对旧PID12044完整创建时间、Python311解释器、run_server.py/Session0、唯一8080监听、SYSTEM任务入口与WMS_NO_DB_TOUCH=1后，避开计划触发窗口，仅终止原实例并启动原任务一次。新PID12284、2026-10-24T16:55:22.087837+08:00创建，解释器/命令/会话一致，LastTaskResult=0；16:55:25启动日志24b427c、production、CSRF on，db-check migrate=ok仅作结构检查证据。
- 只读验收：本机与https://gd2026.top/login均GET200并含CSRF；两端实际返回app.js与提交文本一致，模板文件与目标Git对象一致。八张核心业务/用户表完整行摘要前后一致，quick_check=ok。未在生产登录或运行写入冒烟，未改业务记录及账号密码。截图为隔离测试环境。用户刷新整个页面即可加载新入口。
- 收尾边界：本次只补月度BUG台账，生产应用保持24b427c，无须再重启；文档契约与收尾提交自身CI单独验收。若该次push仍遭同一匿名403，仅在同一实时基线全绿及Android范围证明成立后临时使用既有开关并清除。

- 2026-10-24 位置调整（用户指定，BUG-2026-10-24-012后续）：将退出登录从我的资料下方移到主菜单最后一项；管理员位于系统管理之后，其他角色仍可在各自菜单末尾退出。保留独立入口、认证条件、target=_top和既有登出逻辑。README同步位置说明。生产需重启 WMS 服务生效。
- 位置调整基线：04365c9e001ca1e1e1ad8c4f46dd75a20d619c35的CI40079971398、AI40079971357全绿；Android40027751562成功且祖先/保护路径/对象齐全证明成立。8个导航、登录、记住我、权限及表单相邻模块91 passed。按用户新要求更新原位置断言，保留全部退出功能断言；旧布局8 failed、4 passed，证据%TEMP%/wms-logout-order-red.log。生效确认：2026-10-24 18:06由Codex完成位置调整发布核验，现位于主菜单末尾、管理员的系统管理之后。
- 位置调整验证：相关8模块91 passed，文档契约34 passed；备份模板并物理回退，新位置断言8 failed、4 passed，再恢复补丁；隔离HTTP冒烟121/121并停止自有18080服务，verify_wms_bugs、A1–A14、UTF-8与diff检查通过。证据C:/wms_backups/logout_order_deploy_20261024，未修改后端或业务数据。
- 位置调整发布：2b5bea5fa9b97b050a20e11355ea1a75995e6196已实际push（04365c9e..2b5bea5f main -> main），HEAD/origin/live main一致；CI40084339599、AI40084339646精确匹配success，Android40027751562祖先/对象/保护路径证明通过。即时在线备份与旧模板回退包在C:/wms_backups/logout_order_deploy_20261024。核对旧PID12284身份、唯一8080监听、SYSTEM原任务及启动保护后重启一次，新PID2476（2026-10-24T18:06:31.618427+08:00），Python311/run_server.py/Session0正确，LastTaskResult=0；18:06:35日志版本2b5bea5、production、CSRF on。模板与目标Git一致，本机及公网login GET200且含CSRF，八张核心业务/用户表摘要前后一致、quick_check=ok。未登录生产或修改业务/密码。收尾仅台账，无须再次重启。


### BUG-2026-10-24-013: 选单查询迟到响应覆盖当前筛选或重开已关闭的来源联想

- 状态：已修复并生产生效（2026-10-24 18:18）。
- 根因/危害：销售出库选单loadSelectable未校验HTTP和响应封套、无请求代次保护，旧查询覆盖新筛选，失败响应可能显示为空列表；采购选单已有序号但缺HTTP/数组校验和当前弹窗、供应商、关键字上下文校验；采购退货来源入库联想没有失效机制，输入防抖期间、选定来源、Escape或点外部后，旧响应仍会重新打开候选，旧失败也会隐藏新结果。销售/采购加载新查询时旧已选统计未清空。
- 同类点已排查：检索BUG-2026-10-24-004/005/007/008的异步查询/刷新历史及所有selectable接口前端消费点，三处分别为sales_outbound_selection、in_order_add采购选单和out_order_add采购退货来源联想。本批覆盖这三处，已有物料缓存、仓库/部门及公共单位刷新保护保持。采购选单原来前150张提示/显式分页不变；退货来源联想明确仅前30条，后端候选口径不改。
- 修复：三处GET统一用WMS.api.getRaw处理HTTP、会话与业务失败，并验证列表形状；仅当前请求、当前输入/筛选以及仍有效DOM可更新页面。退货来源输入、选择、Escape和点击外部立即使请求失效并清理防抖；销售和采购开始查询即清理选择缓存/统计。保留原候选渲染、供应商优先排序、数量/价格、人工生成草稿及后端鉴权/库存规则。生产需重启 WMS 服务生效。
- 修复前基线：9个选单/销售/采购退货/物料联想及相邻模块232 passed、27项既有SQLAlchemy弃用警告（%TEMP%/wms-selection-query-baseline.log）。新增42项用实际页面函数、渲染/事件和真实api.js，延迟响应覆盖HTTP错误、业务错误、HTML/空/错误结构、会话过期、网络失败、响应乱序、输入变化、DOM替换、加载统计和选定/关闭/防抖；旧实现27 failed、15 passed，初次修复42 passed。
- 既有测试维护：采购选单原测试新增真实api.js和正确HTTP Response桩及缓存Map，保留原显式page/limit、查询参数、旧响应不得覆盖和150条提示的全部断言，未放宽业务断言。
- 开工门禁：37ffeefb99391dc66d478c974e962b33feb8e58f的CI40084628649、AI40084628646均completed/success；最新Android40027751562为祖先，Git对象齐全且Android工程/工作流无差异。上一批CI等待时仅只读复核及基线测试，退出菜单调整生产与收尾CI通过后才写入本批。证据C:/wms_backups/selection_query_deploy_20261024。
- 生效确认：2026-10-24 18:18由Codex核对目标CI、在线备份、原任务重启、版本日志、模板哈希和只读生产摘要后确认；生产需重启 WMS 服务生效，本次已完成。证据C:/wms_backups/selection_query_deploy_20261024。
- 最终回归：补齐仓库/供应商切换后新增48项全通过；备份三个模板→物理回退→新用例32 failed、16 passed→finally恢复（rollback.log），未使用stash。10个受影响/相邻模块280 passed、27项既有SQLAlchemy弃用警告（%TEMP%/wms-selection-query-final.log）；文档契约34 passed、隔离HTTP冒烟121/121并停止自有18080实例；verify_wms_bugs、A1–A14为0违规、UTF-8与diff检查通过。提交前check_ci_green.py完整基线SHA为ok=true（precommit_ci.json）。
- 目标提交与CI：e8d070cc7cab354f5b9890e35466cf9fafc771e6已实际push（37ffeefb..e8d070cc main -> main），HEAD/origin/live main一致。[WMS CI40085082154](https://github.com/SIX2090/wms/actions/runs/40085082154)、[AI40085082174](https://github.com/SIX2090/wms/actions/runs/40085082174)精确匹配completed/success；Android40027751562成功且祖先/对象齐全/工程及工作流无变化证明通过，check_ci_green.py完整目标检查ok=true（target_ci.json）。本批推送未跳过门禁。
- 生产发布：即时在线备份deploy_inventory.db完整性通过，SHA256为afb9ee28d1485cea84e546c8667a532141a5d3586aa9fe16cb0d5416ef46537b，保留旧模板回退包。核对旧PID2476完整身份、Python311/run_server.py/Session0、唯一8080监听、SYSTEM原任务入口及WMS_NO_DB_TOUCH=1后，避开计划触发窗口，仅终止原实例并启动原任务一次。新PID7536、2026-10-24T18:18:27.805327+08:00创建，解释器/命令/Session0一致，唯一监听、LastTaskResult=0；18:18:32启动日志e8d070c、production、CSRF on，db-check migrate=ok仅结构检查证据。
- 只读验收：三个模板规范化文本与目标Git对象一致（activation_checks.json），本机及https://gd2026.top/login均GET200并含CSRF。八张核心业务/用户表完整行摘要前后一致，quick_check=ok；未在生产登录或运行写入冒烟、未改业务记录或密码。收尾仅更新月度台账，生产应用保持e8d070cc，无须再次重启；收尾提交自身CI单独验收。

### BUG-2026-10-24-014: Ctrl+S 按 DOM 顺序误触发保存并完成或保存并新建

- 状态：已修复，待目标CI及生产验收。
- 根因/危害：公共键盘监听用submitForm、任意submit按钮和btn-save的首个匹配猜测保存动作；采购订单首先匹配保存并新建，采购入库及领料页面首先匹配保存并完成，可把普通保存意图变成库存完成操作；输入框内又完全忽略保存快捷键。
- 同类点已排查：检索历史物料键盘操作、工具栏去重和确认框键盘隔离记录；全仓Ctrl+S监听只有公共app.js。覆盖采购申请/订单、销售订单新增/编辑、入出库、售后、调整、通用单据和其他出入库工具栏的现有普通保存。采购申请详情没有保存标记，非草稿编辑会重定向详情；编辑页角色显示与POST权限不一致属于既有独立问题，本批不改变权限或后端完成接口。
- 修复：10个模板现有普通保存按钮声明data-wms-save；Ctrl/Cmd+S仅在当前主内容中点击可见、启用且不在弹窗/只读遮罩中的普通保存，排除完成按钮、已处理事件、输入法组合输入及按键重复。没有普通保存时中文提示使用页面按钮；不新增隐藏保存、不调用通用表单回退，不改鼠标操作和业务保存函数。README补充快捷键说明。生产需重启 WMS 服务生效。
- 开工门禁：b06f6cadc800d2a62613e9dedeb3ae8e3cbe9529的WMS CI40085421431、AI40085421442精确匹配success；Android40027751562成功且祖先/对象齐全/保护路径无变化证明通过，check_ci_green.py ok=true，证据C:/wms_backups/keyboard_save_deploy_20261024/baseline_ci.json。
- 回归：原受影响及相邻模块203 passed；新增38项执行真实模板按钮及app.js键盘处理器，覆盖普通保存、保存新建/完成排除、字段焦点、Mac快捷键、弹窗、隐藏/禁用/只读、输入法与重复按键。物理备份并回退11个业务文件后24 failed、14 passed，finally恢复补丁；修复后合计241 passed、64项既有警告。证据%TEMP%/wms-keyboard-baseline-tests.log、wms-keyboard-regression.log及wms-keyboard-rollback-h5zdzyq_/rollback.log。未使用stash、未弱化既有断言。
- 生效确认：待目标CI、原计划任务重启与只读生产验证；生产需重启 WMS 服务生效。未对生产登录、提交单据或修改密码。
- 提交前验证：15个既有模块及新增模块241 passed（64项既有SQLAlchemy Query.get弃用警告）、文档契约34 passed、隔离HTTP冒烟121/121且临时服务已停止；verify_wms_bugs全部通过、A1–A14为0违规、UTF-8及diff检查通过。提交前匿名查询HTTP403，经已连接GitHub核实最新main三工作流仍为上述成功记录，实时远端main仍b06f6cad；再次确认Android祖先、完整对象及保护路径差异为空。替代证据precommit_alternative.json。
- 目标提交与CI：c94f9b6f0068a2d17f2b90b27ad3512dfc28b2ac已push（b06f6cad..c94f9b6f main -> main），HEAD/origin/live main一致。WMS CI40086115998与AI40086115980精确匹配completed/success；Android40027751562成功且祖先、完整对象和保护路径无变化证明通过。pre-push匿名403，经已连接GitHub核实同一基线最新运行后单次WMS_SKIP_CI_GATE=1重推并finally清除；证据precommit_alternative.json、target_ci_alternative.json和push.log。
- 生产发布及生效确认：2026-10-24 18:34由Codex核对目标CI、在线备份和原任务重启后确认已生效。备份SHA256为03bf4d4b28f7030fb3a7b890e10571c504836cdd63bbed8eb71d8ad34a91f32f，旧代码rollback_code.zip保留。核对旧PID7536创建时间、Python311/run_server.py/Session0、唯一8080监听、SYSTEM原计划任务与启动保护后重启一次。新PID11652，2026-10-24T18:34:24.009086+08:00，解释器/命令/会话正确，LastTaskResult=0；18:34:27日志版本c94f9b6、production、CSRF on。11个应用文件与Git目标文本一致，公网app.js匹配；本机/公网login GET200含CSRF，八张核心业务/用户表完整行摘要前后一致。Python公网TLS曾短暂EOF，随后PowerShell独立请求成功。未生产登录、修改业务数据或密码。证据C:/wms_backups/keyboard_save_deploy_20261024。收尾仅台账，无须再重启。

### BUG-2026-10-24-015: 保存后完成受阻的具体原因被吞掉或随跳转消失

- 状态：已修复并生产生效（2026-10-24 18:56）。
- 用户复核：用户确认OU26100217保存后未自动新增；生产只读查看为pending，18:18在线备份复制到独立临时数据库后运行真实库存校验，返回铜排仓物料1280需要16、可用3。未对真实单据执行完成、修改数量或调整库存。正常拦截不是库存算法缺陷；前端没有可靠说明完成受阻才是本批修复对象。
- 根因/危害：out_order_add已取得草稿ID后丢弃HTTP错误中的具体message，以笼统toast立即跳详情；in_order_add保留message但立即导航导致toast消失；document_table_form完成业务错误700ms后跳详情，网络未知结果还会解锁重复完成。操作员只知道已保存，不知道未进入下一张的原因，可能重复录入。
- 同类点已排查：核对BUG-2026-10-23-008领料完成继续新增，以及采购入库/工单领料合并动作、提交锁与人工确认历史；覆盖上述三个实际保存后完成消费点。同一根因统一一个共享纯DOM结果面板。既有API正确保留HTTP错误信息，无须修改API或后端。现有成功链路真实返回status=success，继续新增行为保持。
- 修复：app.js共享面板持续显示单号、服务端具体原因和查看已保存单据入口，使用textContent、role=alert、聚焦/滚动可见，链接保留embedded。完成请求被拒显示本次请求未成功，网络/5xx/无有效结果显示待核对，不武断判定当前单据未完成。三页不再在失败后自动导航，保留已保存ID及提交锁；保存失败仍可重试，普通保存/完成成功导航、通用单据人工confirm/取消/明确force流程保持。README补充用户操作说明。生产需重启 WMS 服务生效。
- 开工门禁：2a4382c1fc7f4db05da8cd8df63c12ded96fa84b与实时main一致；WMS CI40086529112、AI40086529114精确匹配success，Android40027751562成功且祖先/对象齐全/保护路径无变化证明通过。证据C:/wms_backups/completion_feedback_deploy_20261024/baseline_ci_alternative.json。
- 修复前基线：63个相关模块926 passed、271项既有SQLAlchemy弃用警告；补充两个关键模块138 passed。新增实际页面函数/真实api.js/共享DOM反馈用例在旧代码63 failed、10 passed；保留原成功导航、请求数量、防重复、人工确认和不自动force断言，新要求以持久反馈/用户主动查看替代失败立即导航断言。
- 浏览器修前复现：独立18080、内存数据库、纯测试账号及两个测试仓，QA-FAIL所选仓3、另一仓50，录16后点击顶部实际按钮即跳草稿详情，具体库存不足原因不可见。测试草稿仍pending、两仓总库存53未变；生产数据库与账号未用于浏览器测试。证据before.png、browser_final_state.json。
- 生效确认：待相关回归、目标CI、原计划任务重启及生产只读核验；生产需重启 WMS 服务生效。真实OU26100217由用户人工核对与后续处理，本修复不完成或修改该单。
- 浏览器修后验收：真实顶部按钮+真实HTTP后端，库存不足时页面持续显示已保存单号、需要16/可用3、查看详情链接并锁定保存；点击链接进入正确草稿且保留embedded。另一物料库存5录1，完成成功后自动打开OU26100003空白新单；独立内存DB最终仅两张测试单（第一张pending、第二张completed），不足物料总库存53未变，正常物料5降至4，无重复生成。截图after.png、success-new.png与browser_final_state.json；临时服务及浏览器已关闭。
- 回归锁验证：73项新运行时用例全部通过；物理备份并恢复4个旧产品文件后63 failed、10 passed，均因持久反馈/不提前跳转断言失败而非缺helper；finally恢复且四文件SHA256一致，证据%TEMP%/wms-completion-feedback-physical-rollback.log与wms-feedback-rollback-w4thac_m。文档契约34 passed。
- 最终本地验证：66个受影响及相邻模块1137 passed、271项既有SQLAlchemy警告（与基线一致），隔离HTTP冒烟121/121；verify_wms_bugs全部通过、A1–A14为0违规、UTF-8编码、node语法与diff检查通过。日志及模块清单存入C:/wms_backups/completion_feedback_deploy_20261024。提交前重新核对最新三工作流、实时远端基线及Android复用证明。
- 提交与CI：92ade5103f31f7095b5fe7fd81a68181c6e6145b已实际push（2a4382c1..92ade510 main -> main），HEAD/origin/live main一致；[WMS CI40087609356](https://github.com/SIX2090/wms/actions/runs/40087609356)和[AI40087609357](https://github.com/SIX2090/wms/actions/runs/40087609357)精确匹配completed/success。最新Android40027751562成功且祖先、Git对象齐全、Android工程/工作流无变化证明通过。pre-push匿名HTTP403仅查询失败；已连接GitHub核实同一实时基线最新三工作流并保存替代证据后，单次使用WMS_SKIP_CI_GATE=1重推并finally清除。
- 生产发布及生效确认：2026-10-24 18:56由Codex核验目标CI、在线备份、原WMS-Warehouse任务重启一次、版本日志及只读摘要后确认。备份deploy_inventory.db的SHA256为f61eb6ad7aa800b21bdca45d877212f6b58dee497a617518e5c315b0f8e05517，旧代码rollback_code.zip保留。核对旧PID11652创建时间、Python311/run_server.py/Session0、唯一8080监听、SYSTEM任务入口和启动保护后重启，新PID12012（2026-10-24T18:55:56.899242+08:00），LastTaskResult=0；18:56:05版本92ade51、production、CSRF on、启动迁移禁用。首次检查尚未监听，随后启动完成并确认唯一监听。四个产品文件与Git目标文本一致，公网app.js匹配，本机/公网login GET200且含CSRF；八张业务/用户表摘要前后一致、quick_check=ok。
- 单据状态刷新：发布后只读查询OU26100217（ID692）已为completed，日志记录18:39:23完成，发生在本次18:55重启之前。此前pending及库存16/3结论属于排查时的历史状态，不代表当前仍待完成。代理未完成、修改该真实单据或调整库存；已向用户说明最新状态。生产未登录、未写入业务或密码。收尾仅台账，无须再次重启。

### BUG-2026-10-24-016: 委外发料收料改选物料后旧ID残留导致错存

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：两页物料输入仅在零匹配时清隐藏ID，多匹配仍保留旧ID；精确名称用find首项也会错误选择同名物料。后端优先ID解析，因此界面输入螺栓却可能保存旧轴承。未解析物料的原后端继续跳过，不能当作前端歧义兜底。
- 同类点已排查：检索物料候选、隐藏ID清理及BUG-2026-10-22-013、2026-10-24-005/006历史；本次同分支仅subcontract_issue和subcontract_receive，公共quick-select选中后保存前仍经本页解析。覆盖两处，不修改后端库存、权限或详情片段HTML。
- 修复：两页共享subcontract-material-selection.js，唯一精确编码优先、名称要求唯一、其余不明确输入立即清旧ID。保存前对未解析非空编码经既有精确GET接口分批核对，每批最多200；全部匹配才提交，失败不静默漏行。保留缓存外完整编码，包括被缓存内其他编码部分匹配的情况。增加提交互斥、表单快照/输入代次/行身份/弹窗关闭校验；核对期间发生变化须人工重存，成功持续锁至导航，失败恢复按钮。生产需重启 WMS 服务生效。
- 开工门禁：93cbdf8bdafc655af111302921e1b7fa4789dbb3与实时main一致，CI40087920520、AI40087920447精确匹配success，Android40027751562成功且祖先、对象齐全、保护路径无变化证明成立。证据C:/wms_backups/frontend_six_20261024/baseline_ci.json。
- 修前基线：14个完整受影响/相邻模块386 passed、44项既有SQLAlchemy警告。64项新运行时用例旧代码56 failed、8 passed；使用真实模板输入/保存函数和真实api.js。主代理在独立18080内存库真实浏览器输入A001再改螺栓，保存草稿详情仍显示A001轴承，最终隔离状态material_id=1，证据subcontract/before.png与browser_final_state.json；未生产登录或修改真实单据。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 浏览器验收：独立内存DB的发料与收料实际页面，A001改输入螺栓均被阻止，明确选择B002/B001后分别只生成一张正确物料的草稿；无错误旧物料行。截图after-rejected.png、after-saved.png、after-receive.png，最终隔离状态browser_final_state.json。自有18080服务和浏览器均已关闭，未操作真实业务。文档契约34 passed、隔离HTTP冒烟121/121。
- 最终验证：15模块463 passed、44项既有警告；77项新增回归包含真实模板资源加载、精确API隔离集成和静态资源ETag。物理备份两模板及新JS，回退后67 failed、10对照passed，finally恢复且SHA256一致（%TEMP%/wms-subcontract-selection-rollback-kunr96wu）。既有传输测试仅补DOM/FormData依赖及改stdin避免Windows命令长度限制，原业务断言保留。verify_wms_bugs通过、A1–A14为0违规、请求lint/UTF-8/语法及diff检查通过。
- 提交与CI：b25be876b69b075cb9ff19871fe5ddf6f53a8397实际push并核对HEAD/origin/live main一致；WMS CI40088762175、AI40088762155精确匹配completed/success，Android40027751562成功且复用证明通过，完整目标检查ok=true（subcontract/target_ci.json）。生产与本轮其余批次统一验收。

### BUG-2026-10-24-017: 采购录单重复保存与保存跳转意图被后续点击覆盖

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：采购订单和采购申请submitForm没有请求互斥，连续点击以及成功后的延迟跳转窗口均能再次提交。采购订单又在回调读取全局saveAndNew标记，后续点击可改变首个保存请求的跳转意图。后端对订单编号重复会拒绝、采购申请草稿会更新，不能据此前端重复请求断言必然生成重复单据。
- 同类点已排查：核对既有单据提交锁、Ctrl+S普通保存和BUG-2026-10-24-014/015；本批覆盖采购订单/申请新增和编辑、原按钮、动态工具栏及普通保存快捷键的共同函数入口。已保护的出入库及委外提交保持。
- 开工门禁：b25be876b69b075cb9ff19871fe5ddf6f53a8397与实时main一致，WMS CI40088762175、AI40088762155精确匹配success，Android40027751562成功且祖先/完整对象/保护路径无差异。证据C:/wms_backups/frontend_six_20261024/subcontract/target_ci.json。
- 修前基线：24个受影响及相邻模块582 passed、71项既有SQLAlchemy警告；旧产品及测试哈希核验无变化。证据C:/wms_backups/frontend_six_20261024/purchase/baseline.log。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 修复：两页共同保存函数先校验和快照载荷，再锁定实际按钮/动态工具栏并阻止重入；成功保持锁至既有延迟导航，失败恢复原disabled/aria-busy。订单保存意图在请求前局部固定，保留供应商继续新增。无效响应编号明确提示先核对单据，不自动重发；原权限、后端和业务字段不变。生产需重启 WMS 服务生效。
- 最终回归：25个受影响/相邻模块654 passed、71项既有SQLAlchemy警告。72项新运行时锁执行真实页面函数、真实api.js和saveCurrentPage，覆盖新增/编辑、首次动作意图、请求中/成功跳转等待、业务/HTTP/网络/HTML/空/无效编号、校验/序列化失败及手动重试。物理备份回退两模板后72 failed，finally按SHA256完整恢复（%TEMP%/wms-purchase-save-017-rollback-0qxkf9ot）；修复72 passed。既有transport仅补querySelectorAll桩，原断言保留。
- 本地验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止；verify_wms_bugs全部通过、A1–A14为0违规、UTF-8和diff检查通过。提交前完整基线check_ci_green.py为ok=true，证据purchase/precommit_ci.json；最终日志purchase/final.log。
- 提交与CI：6c89077817b16195ba90d6248f896e2bdb67e08a已实际push（b25be876..6c890778 main -> main），HEAD/origin/live main一致；WMS CI40089491985和AI40089491982精确匹配completed/success，Android40027751562成功且祖先/对象/保护路径复用证明通过，check_ci_green.py目标ok=true。证据purchase/target_ci.json；生产与本轮其余批次统一验收。

### BUG-2026-10-24-018: 独立标签编辑器未同步cells布局导致修改或删除保存后复原

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：独立编辑器只显示坐标keyed格式，保留原cells数组；编辑和删除仅改变坐标项，保存后后端正规化以同坐标cells优先，旧字段重新出现。cells格式模板初次打开又可能画布为空，用户看到的内容与实际保存不一致。
- 同类点已排查：核对BUG-2026-09-08-001、LABEL-FIX-2026-09-29-002及BUG-2026-10-23-007；独立编辑器与物料内嵌编辑器共用后端格式，但内嵌编辑器已有cells往返逻辑。修复限独立页面，不反转全局正规化优先级、不改标签打印后端或业务数据。
- 开工门禁：6c89077817b16195ba90d6248f896e2bdb67e08a实时main三工作流目标检查ok=true；CI40089491985、AI40089491982精确匹配success，Android40027751562成功且复用证明通过。证据purchase/target_ci.json。
- 修前基线：9个标签布局/编码/预览/编辑器/传输及路由模块171 passed、40项既有警告；跨016/017四产品及测试哈希未变，基线仍有效。证据%TEMP%/wms-label-dual-format-baseline-28rd9aii。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 修复：加载时将cells与坐标项归并为同一编辑来源，保持cells冲突优先；拖放、替换、删除与清空同步cells，保存与画布使用一致内容。保留边距、行高、未知元数据及未编辑样式，兼容px字号，静态文字走DOM/textContent；不改变既有请求互斥、失败反馈及后端格式规则。生产需重启 WMS 服务生效。
- 最终回归：9个既有模块与22项新增真实页面JS/真实api.js/实际normalizer往返，共193 passed、40项既有警告。物理备份回退模板后18 failed、4个纯keyed或原有清空对照passed，finally字节恢复且SHA256一致；失败直接证实保存后旧字段残留，未用缺少helper制造伪红。证据%TEMP%/wms-label018-rollback-3wfmhxrm，label/final.log。未改旧测试断言。
- 本地验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停；verify_wms_bugs通过、A1–A14零违规、UTF-8及diff检查通过。提交前匿名查询HTTP403限流，经连接器遍历最新main运行两页核实CI40089491985/AI40089491982成功且目标精确匹配，Android40027751562成功；实时远端SHA不变，Android祖先、完整对象和保护路径无差异均重新核实。证据label/precommit_alternative.json，不把查询失败当CI失败。
- 提交与CI：d77c636994d00a5580c789a73f691c76afa81107已实际push并核对HEAD/origin/live main一致；WMS CI40090162134和AI40090162213精确匹配success，Android40027751562成功且祖先、完整对象与保护路径无差异证明重新核验。pre-push匿名403，在同一基线最新三工作流已核实后单次WMS_SKIP_CI_GATE=1重推并finally清除，保留push.log和push-retry.log。证据label/target_ci_alternative.json；生产统一验收。

### BUG-2026-10-24-019: 程序回填和清空日期绕过控件导致显示与提交值不一致

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：flatpickr创建可见altInput并维护selectedDates，页面直接写原input.value或只form.reset不会同步控件。物料有效期编辑/复制/关闭新增、期初草稿恢复/粘贴以及AI质量看板清空筛选可留下旧显示或旧状态，造成日期误判或旧条件继续查询。
- 同类点已排查：核对BUG-2026-09-07-007-F01及所有程序日期赋值；覆盖三页面六入口。report_view已有setDate作为对照；AI验收页初始化早于控件、入库动态行未启用该插件，不改其初始化。AI页面对应既有AI-R15-F01子修复AI-UX-DATE-SYNC-001，查重无等价任务，不新增AI能力或改变人工确认/权限。
- 开工门禁：d77c636994d00a5580c789a73f691c76afa81107实时main最新WMS CI40090162134、AI40090162213精确匹配success，Android40027751562成功且祖先/对象/保护路径无变化。证据label/target_ci_alternative.json。
- 修前基线：原54模块1989 passed、21 skipped；四产品及54测试哈希一致。跨016/017复用47未变模块、4采购相关模块的654 passed证据，补3模块124 passed；018只影响三个全模板扫描的无变化断言输入，逐项比对一致。不能将重叠测试总数相加当独立覆盖。证据%TEMP%/wms-date-sync-baseline-1ombz79a、wms-date-sync-baseline-refresh-r5z3elgg。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 修复：共享setWmsDateInputValue通过插件setDate/clear同步原值、可见输入和选中日期，不额外触发change；无插件时保留普通value赋值。六入口使用该助手，草稿缺省日期仍不覆盖当前值，其他字段和请求保持。
- 回归锁：28项新运行回归首次全通过；四产品物理备份回退后27 failed、1个草稿缺省日期对照passed，finally恢复并核对四文件SHA256一致。18个真实消费场景失败直接指向日期不一致，其余9个新助手边界旧码不存在；未仅以缺helper冒充业务复现。证据%TEMP%/wms-date019-rollback-9fbo7ymw。
- 浏览器验收：CUA操作独立静态fixture，加载实际flatpickr、base初始化及真实消费函数，网络和非日期动作使用隔离桩。六入口×普通日期/闰日/空共18场景，旧码18失败，修复18通过；读取页面公开显示的原值、altInput、selectedDates和FormData/筛选载荷核对。截图date/browser-before.png、browser-after.png，完整结果JSON同目录。自有18080静态服务身份核对后停止，临时浏览器关闭，未生产登录或连接生产库。
- 最终验证：55个受影响及相邻模块2017 passed、21 skipped（与修前既有跳过一致），四产品哈希全程不变。完整verify_ai_all.py --level full --jobs 1为70/70通过，包含既有BUG回归；严格AI台账及文档契约34项通过，两个JS语法、A1–A14零违规、UTF-8和diff检查通过。证据date/final.log、final_evidence.json和ai_full.log。
- 提交前验收：隔离HTTP冒烟121/121，临时服务已停止。匿名限流持续，连接器重新逐页核实同一实时main基线的最新三工作流成功及完整SHA，Android复用证明通过；证据date/precommit_alternative.json。AI子任务仍标待验收，待目标CI和生产核验后登记完成。
- 提交与CI：133a9ba6d942e85953e2ab348c79e91d17ed8c01已实际push（d77c6369..133a9ba6 main -> main），HEAD/origin/live main一致；WMS CI40091246311和AI40091246337精确匹配completed/success，Android40027751562成功且祖先、完整对象、保护路径无差异重新核实。pre-push匿名403，核实同一基线后仅本次重推使用WMS_SKIP_CI_GATE=1并finally清除。证据date/target_ci_alternative.json、push.log、push-retry.log；生产统一验收。

### BUG-2026-10-24-020: 合同工程与领料人联想迟到响应覆盖当前输入或重新打开候选

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：公共合同联想、入库列表工程筛选及领料人查询未完整校验请求代次、输入和当前候选所属控件；输入变化、关闭或跨行切换后旧响应仍可覆盖当前候选，失败响应还可能被当空结果缓存，影响重试。
- 同类点已排查：核对BUG-2026-10-24-005/007/008/013等查询生命周期历史；本批覆盖公共ContractAutocomplete的五页消费点、in_order工程筛选及out_order_add领料人查询。保留已修复的物料/来源选单及其他联想，不改库存、后端权限或单据状态。
- 开工门禁：133a9ba6d942e85953e2ab348c79e91d17ed8c01与实时main一致，最新WMS CI40091246311、AI40091246337精确匹配success；Android40027751562成功，祖先、完整对象及保护路径无变化证明通过。证据C:/wms_backups/frontend_six_20261024/date/target_ci_alternative.json。
- 修前基线：58模块按代码、测试及依赖投影和原始文件哈希核对复用：019覆盖48、旧异步证据8、017采购1，补跑视口模块20 passed。所有冻结核验通过，未将重叠全套测试总数相加；证据async/baseline-reuse.json、baseline-modules.txt及viewport-baseline.log。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 修复：输入变化先取消防抖并使在途查询失效，返回时核对代次、输入值、DOM及合同候选所属行；选择、失焦、Escape和点击外部立即取消。成功列表验证数组与非空对象记录后才缓存，失败不污染缓存；当前失败给中文反馈，迟到失败不扰动新结果。工程及领料人GET统一走WMS.api.getRaw，合同保留已解封装getContracts；保持鼠标/键盘选中、合同工程配对填写和领料人空词主动查询。生产需重启 WMS 服务生效。
- 回归锁：77项新用例执行真实IIFE及api.js，覆盖乱序、失败/非法结构、失败后重试、缓存切换、清空、关闭、脱离DOM、跨行、鼠标和键盘选择。三产品物理备份回退后54 failed、23个对照passed，finally恢复且三文件SHA256一致（async/rollback-proof.json）；修复版与既有页面运行回归83 passed。新增源码通过stdin送入Node，避免Windows命令长度限制。
- 既有测试维护：dead_header运行fixture补真实api.js、HTTP/业务状态封套和clearTimeout；合同focus源码契约同步为focus→search(false)→triggerSearch(value,version)，仍要求聚焦同步发起查询，另由真实运行用例验证。未弱化保存、字段或请求断言。
- 最终验证：61个受影响及相邻模块1987 passed、21项既有skipped、2项既有SQLAlchemy警告；77新增锁包含其中不重复计数，运行前后产品、测试及其余冻结依赖哈希无变化（async/final-evidence.json）。文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停、verify_wms_bugs通过、严格AI台账通过、A1–A14零违规、JS语法/UTF-8/diff检查通过。请求lint无违规，存量模板warn未增加。
- 提交前门禁：匿名查询仍为HTTP403限流，经连接器分页核对最新main三工作流仍为上述成功记录，实时main仍133a9ba6；Android祖先、完整对象和保护路径无差异重新验证。证据async/precommit_alternative.json。
- 提交与CI：762ec6790bdfcc11f69d5554ac8b06531b7ec520已实际push（133a9ba6..762ec679 main -> main），HEAD/origin/live main一致；WMS CI40092337163和AI40092337111精确匹配completed/success，Android40027751562成功且复用证明重新通过。pre-push匿名403，核对同一基线后单次WMS_SKIP_CI_GATE=1重推并finally清除，证据async/push.log、push-retry.log和target_ci_alternative.json。生产统一验收。

### BUG-2026-10-24-021: 新增返回快捷键误选侧栏链接或关闭组件后继续跳页

- 状态：已修复并生产生效（2026-10-25 16:51）。
- 根因/危害：公共Ctrl+N/Escape按全页首个匹配链接猜测动作，真实侧栏先于主内容，能误进采购申请新增或工单领料列表；document阶段处理早于后注册的组件监听，关闭移动侧栏或候选后还可能继续导航。现有Ctrl+S已经使用显式普通保存标记，本批保留。
- 同类点已排查：核对BUG-2026-10-24-014普通保存快捷键、确认框/字段设置键盘隔离及公共工具栏历史；覆盖公共快捷键与八个现有单据模板入口，不创建隐藏操作或扩展角色权限。
- 开工门禁：762ec6790bdfcc11f69d5554ac8b06531b7ec520与实时main一致，最新WMS CI40092337163、AI40092337111精确匹配success；Android40027751562成功，祖先、完整对象和保护路径无变化重新证明。证据C:/wms_backups/frontend_six_20261024/async/target_ci_alternative.json。
- 修前基线：最终61模块来源为020成功记录23、017成功记录7、未变消费点旧证据10、本次补测21（156 passed、12项既有警告）。动态文件名消费的receipt_toolbar_rows额外补测，不只按字面匹配复用；9产品及原58测试哈希前后一致。证据navigation/baseline-reuse.json、baseline-before.json、baseline-after.json及两份baseline日志。
- 生效确认：2026-10-25 16:51由Codex完成统一生产验收；生产需重启 WMS 服务生效，本次已通过原WMS-Warehouse任务重启。应用版本a6e4d9f、本机/公网login及静态资源核验通过，8张核心业务/用户表摘要未变；详见本页BUG-2026-10-24-021统一发布记录及C:/wms_backups/frontend_six_20261024。
- 修复：八模板既有新增/返回入口和动态工具栏新增按钮显式声明data-wms-new/back；只点击当前embedded-content中可见、启用且非弹窗/只读遮罩内的对应入口。Ctrl+S原处理保持；导航键在window冒泡阶段处理，尊重组件后注册的document监听、已阻止事件、输入控件/contenteditable、IME229、重复键与修饰键。window捕获阶段记住当次按键开始时的可见弹层/抽屉/移动侧栏/候选，组件关闭后同一Esc不继续跳页；隐藏候选不阻断。README补用户使用边界。生产需重启 WMS 服务生效。
- 回归锁：157项新运行回归执行真实快捷键函数、真实base侧栏和捕获→document→window事件顺序，覆盖组件晚注册/关闭/打开、stopPropagation、按钮焦点下候选、隐藏禁用/只读入口、输入法与重复键。物理备份回退9产品文件后146 failed、11对照passed，finally恢复且SHA256全部一致（navigation/rollback-proof.json）。原Ctrl+S 38项继续通过。
- 最终验证：62模块1484 passed、100项既有SQLAlchemy警告，产品冻结后完成；工具栏相邻原夹具缺原生setAttribute，补属性接口而不改原断言。文档契约34 passed、隔离HTTP冒烟121/121且自有服务停止、既有BUG检查通过、规则零违规、源码编码/JS语法/diff通过。恢复CI修复后再次核对9产品哈希及测试/README修改时间，仍匹配原成功证据（restored-after-ci-repair.json），不重复相加重叠用例数量。
- 浏览器验收：独立静态夹具抽取真实函数和base侧栏，不发送业务请求。旧版Ctrl+N误选隐藏侧栏/purchase_request/add、候选Esc先误选/requisition再关闭；修复版只选当前/other_out_order/add及/other_out_order，Esc关闭候选或移动侧栏时无导航。截图navigation/browser-before.png、browser-after-candidate.png、browser-after-sidebar.png、browser-after-new.png；临时浏览器及18081静态服务已结束，未生产登录。
- 恢复开工门禁：2026-10-25中断续作发现Android定时运行40132587829失败，单次重跑仍失败，021先完整备份撤下。用户授权仅CI修复例外；78c9b8d99b1a16ab417e5727f572fd2721362d41三工作流均成功后才恢复本批，最新CI40177478032、AI40177478041、Android40177478067精确匹配，实时main一致。证据android_ci_20261025/target_ci_alternative.json。

- 提交与CI：a6e4d9fd9f8b6e5cc354725762181d4d196e89d5实际push（78c9b8d9..a6e4d9fd main -> main），HEAD/origin/live main一致。WMS CI40177924371和AI40177924354精确匹配completed/success；Android40177478067成功，78c9b8d9为祖先、对象齐全且Android工程/工作流无变化。本批正常push通过门禁，未使用跳过开关；发布前匿名查询403后通过连接器重新核对同一目标和最新三工作流，保留navigation/target_ci_alternative.json。
- 六批统一发布：2026-10-25 16:51确认BUG-016至021生效。在线一致性备份deploy_inventory.db完整性通过，SHA256为f0738c33e0319041c1085d95229a049285700d1c17d427bae6f2152252d6679e，保留发布前16原有文件及新JS不存在清单的rollback_code.zip。逐项核对17个应用文件与目标Git内容一致且回退覆盖完整，未发布不相关应用修改。
- 原任务重启：核实旧PID12012创建时间2026-10-24T18:55:56.899242+08:00、Python311/run_server.py/Session0及唯一127.0.0.1:8080；原SYSTEM任务入口run_wms_task.bat包含WMS_NO_DB_TOUCH=1与监听防重复保护，避开计划触发窗口后仅终止原实例并启动原任务一次。新PID1540创建于2026-10-25T16:50:52.913805+08:00，解释器/命令/会话正确，唯一8080监听、LastTaskResult=0；16:51:00日志版本a6e4d9f、production及CSRF on。db-check migrate=ok仅作为结构检查结果，不推断执行过迁移。
- 只读生产验收：17文件保持目标内容，本机/公网login GET200含CSRF；本机/公网app.js及公网新subcontract-material-selection.js字节哈希匹配。8张核心业务/用户表完整行摘要在重启前后完全一致，quick_check=ok；未生产登录、创建/完成测试单据、修改库存或密码。证据activation_checks.json、pre/post_restart_digest.json、pre/post_process.json、post_task.json。收尾仅更新台账及AI任务完成记录，无须再次重启。

### BUG-2026-10-08-014-F01: 文件恢复测试沿用Robolectric内存日志默认值导致SQLite故障复发

- 状态：已修复并通过Android真实编译与目标CI验收（2026-10-25）。
- 根因/危害：最新main 762ec679的Android定时运行40132587829在PendingQueueRebuildProtectionTest重建保单用例失败，首次SQLITE_BUSY，单独重跑失败job后仍SQLITE_IOERR_SHORT_READ。故障在真实临时文件重新打开阶段；Robolectric 4.14.1的ShadowSQLiteConnection默认同步OFF、日志MEMORY，官方源码要求文件同步场景显式配置持久化模式。历史偶发记录不能充当本次全绿证据。
- 同类点已排查：关联BUG-2026-09-22-001及BUG-2026-10-08-014，全局LEGACY配置保持；本类两处Room回补测试及OfflineQueueStateMachineTest均使用inMemoryDatabaseBuilder。本类其余场景专门执行文件关闭/重开/重建，调整局限此类。前端021改动已逐文件备份到android_ci_20261025/held_frontend后从工作区撤下，不夹带发布。
- 修复：在测试setUp取得Context/清理数据库之前，通过官方ShadowSQLiteConnection设置FULL同步及PERSIST日志；从初次打开即使用正确默认值，不在已打开连接上切换journal_mode。新增真实Android用例验证PRAGMA同步级别、持久日志、关闭重开后的队列备份。全部原保单、空库、坏库及恢复断言保留；生产AppDatabase与业务逻辑不变。
- 回归：修前3个相关静态守护模块27 passed，真实Android80项中1失败且重跑仍失败。修后相关模块及两个新增源码守护29 passed；物理备份并回退Kotlin后两个新守护失败、finally恢复且SHA256一致。这是源码配置守护，不冒充Android运行时或编译证明；完整Android新增81项及三工作流须CI真实验收。
- 生效确认：2026-10-25由Codex核对78c9b8d9的三工作流精确目标全绿，Android真实编译、lint及81项单测全部通过；仅测试夹具及回归守护变化，无须生产重启。证据C:/wms_backups/frontend_six_20261024/android_ci_20261025，官方依据https://raw.githubusercontent.com/robolectric/robolectric/robolectric-4.14.1/shadows/framework/src/main/java/org/robolectric/shadows/ShadowSQLiteConnection.java。
- 门禁例外授权：2026-10-25用户明确回复「允许本次CI修复例外」，允许在Android实际红灯基线上仅提交推送已展示的五个测试/台账文件。此处不伪称基线全绿；仅本次push临时使用WMS_SKIP_CI_GATE并finally清除，分支与原pre-commit规则继续执行，三工作流全绿前不恢复下一批业务写入。
- 提交及CI生效确认：78c9b8d99b1a16ab417e5727f572fd2721362d41实际push（762ec679..78c9b8d9 main -> main），HEAD/origin/live一致。WMS CI40177478032、AI40177478041、Android40177478067均精确匹配completed/success；Android job121121206258日志81 PASSED、0 FAILED，新增持久化检查及原保单重建用例均通过，APK编译与lint通过。目标全绿后才按哈希恢复021修改；仅测试变化，不需要生产重启。本次配置与运行验证通过，不以一次成功保证未来所有SQLite环境故障均已消除。

### BUG-2026-10-25-001: 销售订单编辑将已有零单价替换为物料默认价

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：sales_order_edit的fillRow将数值0误作未填写，打开已有零单价行即改用物料默认价；默认价125、数量2的真实页面函数复现为单价125.00、金额250。后端读取和保存本来支持0，本次不修改价格业务口径。
- 同类点已排查：关联10月BOM零成本、粘贴零价格及复制行历史；核对销售新增/编辑/模板/复制/粘贴链路以及出入库、售后价格默认消费点。显式重新选物料的强制默认价与已有行初始化区分，本批修复已有销售价格被静默覆盖及对应输入初始化，保持新空行带默认价。
- 开工门禁：b42098dc0dfbf9f2b4010dfdbed575b648b27171与实时远端main一致；WMS CI40178435471、AI40178435468精确匹配completed/success。Android40177478067成功，78c9b8d99b1a16ab417e5727f572fd2721362d41为祖先，Git对象齐全且Android工程/工作流无差异。匿名HTTP403仅查询失败，替代证据C:/wms_backups/frontend_ten_20261025/baseline_ci.json。
- 修前基线：28个受影响及相邻模块405 passed、28项既有警告；真实页面addRow/fillRow/collect及后端解析证据存于sales_zero/audit-probe.json与baseline-evidence.json。
- 修复：价格是否存在按null/undefined/空字符串判断，保留数值0和字符串0；已有行、复制、模板及粘贴遵循相同口径，新空行仍可采用物料默认价。生产需重启 WMS 服务生效。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 回归锁：20项真实addRow/fillRow/collect及复制/模板/粘贴/最近物料/新空行用例通过，覆盖0、字符串0、0.00、缺失/null/空值及正价和金额税额。物理备份后回退旧模板为7 failed、13正对照passed；finally恢复产品与测试且SHA256一致，证据sales_zero/rollback-evidence.json。
- 最终模块回归：原28模块及新增模块共425 passed、28项既有SQLAlchemy警告，原业务断言保留；证据sales_zero/final.log和final-evidence.json。销售编辑空白预留行导致400另记002，不夹带本次价格修复。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止；verify_wms_bugs全部通过、A1–A14为0违规、非GET请求检查/UTF-8编码及diff检查通过。最新三工作流仍是开工成功记录，实时远端及Android复用证明再次核对通过，证据sales_zero/precommit_ci_alternative.json；未核实的查询失败不视作CI失败或成功。
- 提交与CI：8d538943e014060d93f0e78be2ed7f69971c8634实际push（b42098dc..8d538943 main -> main），HEAD/origin/live main一致；WMS CI40179821572、AI40179821852精确匹配completed/success，Android40177478067成功且祖先/对象齐全/保护路径无变化证明通过。pre-push匿名403，同基线连接器证据核实后单次WMS_SKIP_CI_GATE=1重推并finally清除。证据sales_zero/target_ci.json和push.log，生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-002: 销售明细空白预留行阻断编辑保存及新增半填行被静默丢弃

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：编辑页ensureBlankRows(15)的预留行全部进入collect载荷，一条有效明细加14条空行使真实后端返回400；新增页反而按编码过滤所有空码行，数量、零价、批次及合同备注已填的半行会悄悄漏掉。原始行号丢失会使操作者难以核对。
- 同类点已排查：核对销售明细收集、既有粘贴校验和单据默认空行历史；本组统一两销售页的collect边界及全部调用（保存、校验、模板）。不泛化其他单据默认行语义，不修改后端校验、库存或权限。
- 开工门禁：实时main为8d538943e014060d93f0e78be2ed7f69971c8634；WMS CI40179821572、AI40179821852精确匹配success，Android40177478067成功且复用证明通过（sales_zero/target_ci.json）。
- 修前证据：隔离内存库GET真实草稿、执行实际页面addRow/ensureBlankRows/collect后POST15行返回400且原草稿不变，仅有效行对照返回200。实际新增页collect把有数量7、价格0及合同备注却无编码的第二行删除。证据C:/wms_backups/frontend_ten_20261025/sales_blank；修前29模块425 passed及相同范围哈希由001最终回归复用并再次核对。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：两页collect仅忽略真正未填写行；编辑预留行的默认数量1及默认税率不视为录入，零价/改数量税率/批次等内容均保留。半填缺码或数值badInput行提示原始行号并聚焦物料编码，阻止保存；模板保存也捕获相同校验并保持原存储。合法行字段、顺序和零值及既有保存互斥保持。生产需重启 WMS 服务生效。
- 回归锁：38项新增实际页面addRow/collect/save/模板与真实api.js运行用例通过，包含原始行号、11类半行字段、空白预留、数值0、失败重试及成功锁；四项真实隔离后端POST验证200或400回滚、明细及库存保持。物理备份并回退两模板后31 failed、7正对照passed，finally产品及测试SHA256完整恢复，证据sales_blank/rollback-evidence.json。
- 最终模块回归：原29模块及新增模块共463 passed、30项SQLAlchemy警告（原基线28项，新增隔离集成触发2项），001的20项零价回归保持通过，两个产品和全部30测试模块前后SHA256一致。证据sales_blank/final.log、final-modules.txt及final-evidence.json。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止；verify_wms_bugs全部通过、A1–A14为0违规、非GET请求检查/UTF-8/diff检查通过。连接器再次核实最新三工作流及同一远端8d538943基线全绿、Android复用证明通过，证据sales_blank/precommit_ci_alternative.json。
- 提交与CI：5003a036e6371a169bc7cd0b60277cee34287b29实际正常push（8d538943..5003a036 main -> main），HEAD/origin/live main一致；WMS CI40180859791、AI40180859780精确匹配completed/success，Android40177478067成功且祖先/对象齐全/保护路径无变化证明通过，证据sales_blank/target_ci.json及push-first.log。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-003: 入库领料新增页重复处理回车覆盖手工单价

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：物料行handleKeydown已处理Enter并preventDefault，document的setupScanAutoFill仍再执行forcePrice强制默认价。真实事件顺序中默认价99、手工价12.34在行处理后仍12.34，全局监听又变99.00并新增50ms聚焦定时器。
- 同类点已排查：关联BUG-2026-09-22-004-F01物料键盘/输入法历史、复制行及扫码默认价场景；全仓仅in_order_add和out_order_add两处setupScanAutoFill，共用document_table_form无该重复监听。只处理已被消费事件，不改变未处理扫码的默认价逻辑。
- 开工门禁：实时main为5003a036e6371a169bc7cd0b60277cee34287b29；WMS CI40180859791、AI40180859780精确匹配success，Android40177478067成功且祖先/对象/保护路径证明通过（sales_blank/target_ci.json）。
- 修前基线：39个受影响及相邻模块700 passed、12项既有警告；从8d538943到5003a036两产品/app.js/api.js/全部模块/conftest字节不变，相关keydown依赖无变化，可复用。证据C:/wms_backups/frontend_ten_20261025/entry_keys/baseline-reuse.json与audit-proof.json。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：两处全局扫码监听各增加defaultPrevented提前返回；不再重复填价或安排聚焦。未消费扫码、候选选择和IME保护沿用原逻辑。生产需重启 WMS 服务生效。
- 回归锁：20项真实页面注册的行级回调、handleKeydown/selectMaterial/fillMaterialFields及全局监听完整链路通过；涵盖候选开关、已有零价/手工价、正常扫码默认价、焦点定时器、IME与非Enter。旧码6 failed、14正对照passed；物理备份后checkout旧两模板再测仍6 failed/14 passed（真实单价断言），finally两产品按SHA256恢复，证据entry_keys/rollback-proof.json。
- 最终验收：40个完整受影响及相邻模块720 passed、12项同基线警告，2产品/40测试/API及conftest哈希前后一致；文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs全部通过、A1–A14为0违规，非GET请求/UTF-8及diff检查通过。证据entry_keys/final-evidence.json、quality.json、smoke.log。提交前再次核对同一5003a036远端基线最新三工作流全绿及Android复用证明（precommit_ci_alternative.json）。
- 提交与CI：8401b99ca435cf2a67820a2c4e79bc618a72fac6实际正常push（5003a036..8401b99c main -> main），HEAD/origin/live main一致；WMS CI40181428730、AI40181428751精确匹配completed/success，Android40177478067成功且复用证明通过。证据entry_keys/target_ci.json及push.log；生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-004: 基础资料编辑旧响应覆盖当前记录及物料图片串图

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：九个edit入口没有请求代次及弹窗生命周期校验。实际函数依次请求A/B，B先回填ID2后A迟到将ID改回1；关闭中的回包仍调用show。物料图片旧请求也可替换新记录的图片及删除ID，存在误改档案风险。
- 同类点已排查：关联2026-10-24-005物料筛选及020合同/项目查询生命周期历史，既有搜索修复不覆盖编辑读取。当前customer/supplier/unit/contract/category/material/employee/warehouse/department九个实际编辑入口及物料图片读取全部纳入；已修保存传输、后端与权限不重做。
- 开工门禁：实时main为8401b99ca435cf2a67820a2c4e79bc618a72fac6；WMS CI40181428730、AI40181428751精确匹配success，Android40177478067成功且祖先/对象/保护路径证明通过（entry_keys/target_ci.json）。
- 修前基线：27个完整受影响及相邻模块763 passed、107项既有skipped、20项既有警告。10产品/API/base/27测试共39输入从8d538943到当前均无Git差异且原始SHA256匹配，复用证明master_edit/baseline-reuse-003.json。真实api.js与九个编辑函数及图片乱序证据read-race-before.json；弹窗事件为隔离DOM/Bootstrap事件桩，不冒充真实浏览器验收。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：app.js共享读取助手核对请求代次、当前DOM、响应记录ID及弹窗关闭/切换，统一GET HTTP/业务失败；禁用编辑控件但保留取消，九个保存入口同时拦截pending。物料图片及上传/删除回调绑定当前编辑上下文，切换详情清空旧File选择，旧回包不污染新物料。字段回填、日期控件和原权限/保存协议保持。生产需重启 WMS 服务生效。
- 回归锁：188项实际helper/九编辑入口/API及图片场景通过，含旧请求先回不解新锁、关闭重开、新增导入、DOM替换、错ID/非法信封/HTTP失败、原disabled/取消/重试、旧上传删除回调及换单File清理。物理备份回退10产品后127 failed、61正对照passed；仅恢复新helper、撤九消费接线再测19项全部失败，两份日志ReferenceError均0。finally全部产品按SHA256恢复，证据master_edit/rollback-proof.json。
- 完整模块：原27及新增共28模块943 passed、107既有skipped、20既有警告，40个产品/依赖/测试输入前后哈希稳定。物料GET移至共享helper，旧动态扫描少1表达式的8项传输参数例，由新188用例覆盖，原业务断言保留；四份既有夹具仅加载真实helper/新增DOM及更新3份外链字节快照。证据master_edit/final.log、final-evidence.json。
- 真实浏览器验收：独立18080及内存库，真实单位页/原Bootstrap，实际点击A后B并延迟A；A回包后仍显示QA-B/QA单位B，关闭B后迟到A不重开。加载期间保存disabled且取消可用，切换新增后迟到A不打断新增弹窗。UI及截图证据master_edit/browser/ui-proof.json、after-race.png；请求除测试登录外全部GET，两测试单位保持不变。文件SQLite连接均被外部守卫在connect前拒绝，自有服务器与浏览器已关闭；未生产登录或改账号密码。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止；verify_wms_bugs全部通过、A1–A14为0违规，非GET请求/UTF-8/JS语法及diff检查通过。匿名CI查询HTTP403，经连接器重新核实8401b99c最新三工作流全绿及实时远端、Android复用证明，证据master_edit/precommit_ci_alternative.json；失败查询不冒充实际红灯或放行依据。
- 提交与CI：2f4400b1926942332ad260297f02a951f5f63228实际push（8401b99c..2f4400b1 main -> main），HEAD/origin/live main一致；WMS CI40183420093、AI40183420092精确匹配completed/success，Android40177478067成功且祖先/对象齐全/保护路径无变化证明通过（master_edit/target_ci.json）。pre-push匿名403，经同基线最新运行替代证据核实后仅该次WMS_SKIP_CI_GATE=1重推并finally清除；push.log/push_ci_alternative.json保留。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-005: 报表打印明细与汇总取自不同筛选快照

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：report_view打印按当前表单重新请求全部明细，renderPrintArea却读取屏幕旧summaryCards。实际函数复现甲仓旧合计100，改乙仓未查询直接打印，输出乙仓及明细7却带旧合计100；条件文字也在await后重新读表单，缺少统一打印快照。
- 同类点已排查：关联BUG-2026-09-07-008全量打印和报表仓库/汇总历史，本共享模板覆盖14类报表。修复当前打印的请求/元数据/汇总一致性，不修改库存计算；stock_query打印漏关键词等筛选为另一个前后端契约问题，隔离实证及独立方案已记录，另列012处理。
- 开工门禁：实时main为2f4400b1926942332ad260297f02a951f5f63228；WMS CI40183420093、AI40183420092精确匹配success，Android40177478067成功且祖先/对象/保护路径证明通过（master_edit/target_ci.json）。
- 修前基线：22个完整受影响及相邻模块140 passed、34项既有警告；004后重跑并核211输入哈希稳定，当前目标复用证据report_print/baseline-after004-target-reuse.json。实际打印handler/render及独立库存打印只读证据C:/wms_backups/frontend_ten_20261025/report_print。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：开始打印时冻结请求参数及中文条件；第一页响应提供同次筛选的汇总、标签与类型，后续页只合并明细，不累加全集汇总。保持500行分页拉取及10000行上限，截断时明确汇总包含未打印行，屏幕原查询保持。生产需重启 WMS 服务生效。
- 回归锁：30项真实打印handler、buildParams及renderPrintArea用例通过；物理备份并回退旧模板后23 failed、7个错误/缺仓库对照passed，finally恢复且SHA256一致（report_print/rollback-proof.json）。既有打印契约仅调整携快照的函数调用锚，分页、上限、打印CSS及window.print断言保留。
- 完整模块：原22及新增模块共170 passed、34项既有警告，197个产品/依赖/测试输入前后SHA256一致。证据report_print/final005-result.json及final005.log。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs全部通过、A1–A14零违规、非GET请求/源码编码/diff检查通过。连接器核对同一2f4400b1基线最新三工作流及实时main、Android祖先/对象/保护路径证明通过，证据report_print/quality.json与precommit_ci_alternative.json。
- 提交与CI：312cf13384be4d78fe91710f76cf74bc113c72b9实际正常push（2f4400b1..312cf133 main -> main），HEAD/origin/live main一致；WMS CI40184787000、AI40184787034精确匹配completed/success，Android40177478067成功且复用证明通过（report_print/target_ci.json）。生产统一验收待执行。
- 浏览器补验：独立18081静态夹具执行Git旧版/当前实际打印函数，旧版改乙仓后打印为明细7/旧汇总100；当前为同次明细7/汇总7，等待期间改变条件仍保留请求快照。只有隔离GET桩，不调用真实打印或生产HTTP；截图browser-before.png、browser-after-summary.png，自有页面及服务已关闭。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-006: Excel导入读取跨弹窗污染预览及重复上传和结果误报

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：ExcelImportExport关闭重开不失效原FileReader回调，旧读取能重填新预览；上传在途及800ms刷新前缺跨重开互斥。旧csrfFetch只看JSON success，HTTP500也可误报成功，count=0又被预览条数覆盖；警告会被自动刷新吞掉，合法数值0在预览中显示空白。
- 同类点已排查：关联BUG-2026-10-22期初预检及2026-10-23公共导入/传输锁历史，已修公共入口与本类是不同消费点；五个活跃详情页复用该唯一组件，其中入/出库详情配置导入接口，另三页保留客户端导出模板。仅修改此组件，不改后端、库存及权限。
- 开工门禁：实时main为312cf13384be4d78fe91710f76cf74bc113c72b9；WMS CI40184787000、AI40184787034精确匹配success，Android40177478067成功且祖先/对象/保护路径证明通过（report_print/target_ci.json）。
- 修前基线：原10个完整受影响及相邻模块458 passed；004后复跑，22项产品/依赖/测试原始哈希匹配当前312cf133，证据excel_component/baseline-after004-proof.json和baseline-after005-readonly-reuse.json。真实完整类、api.js及旧CSRF读取/上传/HTTP/0预览探针已复现。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：文件选择/清空/弹窗关闭重开均使旧读取失效；上传快照保留原文件，锁覆盖在途、成功回调与800ms刷新。统一WMS.api.postRaw判HTTP和业务状态；count=0明确显示0条，警告及结果纯文本保留不自动刷新，预览仅null/undefined显示空。成功后先标记committed，后续页面/回调失败提示核对并保持禁止重复提交，显式新选文件才开始新操作；保留原clean成功先hide再callback，不因迟到回调自动重开。
- 回归锁：新增92项执行完整组件、实际api.js、base旧CSRF/全局拦截及真实生成弹窗HTML事件。物理回退旧产品为72 failed/20正对照passed；仅还原旧传输6 failed/2 HTTP业务失败对照passed，失败点为HTTP不得误成功；仅旧count或预览零值表达式各2 failed。finally恢复产品与测试哈希一致，证据excel_component/rollback-proof.json；既有测试及断言均未修改。
- 完整模块：原10及新增模块共550 passed，23项产品/依赖/测试原始字节前后稳定，最终产品与新测试哈希和最新R8完全一致；前一版548记录仅作中间证据，不冒充最终验收。证据excel_component/final-proof.json及final.log。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs通过、A1–A14零违规、非GET请求/UTF-8/diff检查通过。另增加仓库外本地SQLite连接前守卫，拒绝测试辅助启动代码的生产instance文件兜底连接，内存与外部临时库允许；带守卫再验verify_wms_bugs通过（bugs-guarded.log）。同一312cf133基线最新三工作流、实时远端及Android复用证明再次核实（precommit_ci_alternative.json）。
- 提交与CI：42c74d2dba3d19e12a59d6d87f25ae9e916b9dc0实际正常push（312cf133..42c74d2d main -> main），HEAD/origin/live main一致；WMS CI40186115169、AI40186115164精确匹配completed/success，Android40177478067成功且祖先/对象/保护路径证明通过（excel_component/target_ci.json）。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-007: 普通及批量标签将合法零价格显示为空

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：普通标签Jinja、批量页getFieldValue及两个批量GET数据源以价格truthiness判空；实际零价普通标签为空，而preview显示0.0，批量MATERIALS价格为空且真实xlsx零价单元格为空，三输出与数据不一致。
- 同类点已排查：关联零价录入/复制及本轮销售001、Excel预览006历史；扫描标签普通/preview/整页批量及两个数据生成消费点，共3产品4处。保留None、空串及正价原格式，不改其他数量、库存或实际打印流程。
- 开工门禁：实时main42c74d2dba3d19e12a59d6d87f25ae9e916b9dc0；WMS CI40186115169、AI40186115164精确匹配success，Android40177478067成功且复用证明通过（excel_component/target_ci.json）。
- 修前基线：14个完整受影响及相邻模块175 passed、40项既有警告；在新增外部SQLite连接前守卫环境重跑，28输入哈希前后稳定且目标42c74d2d一致，证据label_zero/baseline-after006-guard-*。真实隔离GET/HTML及xlsx证据label_zero/。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：普通Jinja和两个批量GET数据源按None判空，批量JS按null/undefined/空串判空，保留数值0、字符串0、浮点与Decimal零；None及空串仍为空，正价格式保持。仅3产品4处判断，不改变标签选择/分页/库存或实际打印。生产需重启 WMS 服务生效。
- 回归锁：18项真实Jinja、完整批量页脚本/api.js/DOM、隔离GET及真实xlsx下载用例通过，覆盖0/0.0/Decimal0/字符串0/None/空串及正价，GET前后价格保持。物理备份并回退三产品后8 failed、10正对照passed，finally字节恢复及三SHA256一致；非缺helper反证。证据label_zero/physical-rollback-proof.json和new-green.log，既有测试断言保持。
- 完整模块：原14及新增模块共193 passed，42项警告（基线40及新GET用例2项），29项产品/API/base/测试输入原始哈希前后一致。证据label_zero/final-result.json及final.log；实际HTTP请求仅为隔离Flask test_client GET，xlsx来自外部临时模板，不调用真实打印。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs通过、A1–A14零违规、非GET请求/源码编码/diff检查通过；测试进程保留外部SQLite连接前守卫。连接器重新核实同一42c74d2d基线最新三工作流、实时远端及Android复用证明通过，证据label_zero/quality.json及precommit_ci_alternative.json。
- 提交与CI：1ac42357f10999c96257d064ff7d116205364498实际正常push（42c74d2d..1ac42357 main -> main），HEAD/origin/live main一致；WMS CI40186882115、AI40186882046精确匹配completed/success，Android40177478067成功且复用证明通过（label_zero/target_ci.json）。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-008: 公共删除入口重复确认提交及HTTP错误误报成功

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：batchDelete、deleteItem、deleteCurrent缺确认/请求/导航期间共享互斥，重复或跨入口可发多次POST；公共JSON及逐个详情fallback仅读取JSON，HTTP500携success正文也被计作成功并刷新或跳转。
- 同类点已排查：关联已修公共bindListActions、保存/导入及单据动作锁历史；核三个实际外层入口、postJsonForAction与postDetailDeletes内部transport。员工/采购申请/合同等局部同名函数不伪计为共享消费点，原人工确认、后台权限和已接受单人删除设计保持。
- 开工门禁：实时main1ac42357f10999c96257d064ff7d116205364498；WMS CI40186882115、AI40186882046精确匹配success，Android40177478067成功且祖先/对象/保护路径证明通过（label_zero/target_ci.json）。
- 修前基线：12个完整受影响及相邻模块766 passed、21项既有skipped、64项既有警告；外部SQLite连接前守卫环境重跑，46输入前后哈希一致。007三标签产品变更未触及这46输入，guard-baseline-reuse-after007.json核对目标1ac42357仍全部匹配。证据common_delete/guard-baseline-*与before-probe.cjs。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：三个同页外层入口共享确认/请求/成功导航等待锁，内部transport不重复拿锁；先固定ID、URL及原列表目标。采用WMS.api.postRaw并检查结果信封，逐个详情保留无body POST及部分失败统计；原native/异步确认、600/650ms导航保持。取消/失败可人工重试，已删除成功但刷新跳转异常时明确提示已完成并手动核对，不误报删除失败。
- 回归锁：96项执行真实公共函数、base fetch拦截/CSRF和api.js的运行用例通过；401/419原会话提示明确取消并验证仅一次，不禁止正常登录机制。以同一最新夹具物理回退app.js为43 failed/53正对照passed，finally恢复且SHA256一致（common_delete/physical-rollback.json）。涵盖跨入口锁、确认等待、快照、HTTP/业务/非法JSON、无body协议、partial、失败重试及导航反馈，非缺helper反证。
- 完整模块：原12及新增模块共862 passed、21项既有skipped、64项既有警告，47项产品/依赖/测试原始哈希前后一致。Node语法及diff通过，旧测试/断言保持；证据common_delete/final-full.log及final-after.json。Python验证仅在外部QA bootstrap、固定非秘密测试凭据、外部上传/日志/备份及SQLite连接前守卫下运行。
- 提交前验收：文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs通过、A1–A14零违规、非GET请求/UTF-8/diff检查通过。连接器再次核实同一1ac42357基线最新三工作流、实时远端及Android复用证明通过，证据common_delete/quality.json及precommit_ci_alternative.json。
- 提交与CI：eb8970caf09ab31a600e4ca5a5abd83e65080d79实际push（1ac42357..eb8970ca main -> main），HEAD/origin/live main一致；WMS CI40188390232、AI40188390220精确匹配completed/success，Android40177478067成功且祖先/对象/保护路径证明通过（common_delete/target_ci.json，连接器分页1–2读取最近记录）。pre-push匿名403，经同一基线最新运行替代证据重新核实后，仅该次WMS_SKIP_CI_GATE=1重推且finally清除，push.log/push-retry.log/push_ci_alternative.json保留。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-009: 栏目恢复默认取消仍生效及多控制器默认顺序被偏好污染

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：公共reset立即删除存储并applyState，随后取消/Esc/遮罩也丢偏好；columnsOf按已重排列顺序捕获默认，报表applyReportFieldSettings还会先改列名。公共先初始化时污染动态控制器defaultOrder；动态先初始化且无独立orderKey时又忽略公共已存顺序。仅修reset按钮两行不能闭环。
- 同类点已排查：关联checkbox标签、公共栏目观察器与动态拖拽顺序历史；核公共IIFE、报表动态表头、真实dynamic控制器及入/出库/采购/售后/调整/销售不同初始化顺序。保留observer跳过动态重排边界，复用原setOrder，不重写拖拽算法或扩大列宽/标签含义。
- 开工门禁：实时main eb8970caf09ab31a600e4ca5a5abd83e65080d79；WMS CI40188390232、AI40188390220精确匹配success，Android40177478067成功且复用证明通过（common_delete/target_ci.json）。
- 修前基线：35个完整受影响及相邻模块848 passed、77项既有警告，产品/依赖/测试及三个QA守卫前后哈希稳定，目标eb8970ca一致。证据field_reset/baseline/result.json；真实IIFE、报表及动态链探针、DESIGN_FROZEN.json记录同根因边界。
- 浏览器修前证据：真实公共IIFE和报表函数夹具，经实际UI更名备注并置顶保存；reset/cancel丢名称且saved=null，reset/OK仍备注首列。field_reset/browser-before-cancel和browser-before-confirm的JSON/PNG；仅静态隔离数据，无业务请求，自有页面及18081服务已结束。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：首次接触表头时保留不可变默认位置/名称，报表生成表头也显式提供原始元数据；分离动态真实defaults与有效初始序，有效own key优先，缺失时只读公共偏好或当前DOM。公共reset只改草稿，取消/Esc/遮罩不存储、不应用；OK仅有明确reset/move意图才调用原setOrder并保宽，只改名/显隐不覆盖拖拽序。原生动态reset则显式保存真实默认own order、仍清原width，使重载不复活旧common偏好；observer仍跳过动态重排。生产需重启 WMS 服务生效。
- 回归锁：43项运行回归执行真实公共IIFE、动态控制器及报表函数，覆盖两种初始化顺序、own/common优先、取消/确定、native reset及重载、宽度字节保持/原生清宽、名称/显隐、观察器新行和新列兼容。物理备份并回退两产品后35 failed/8正对照passed，finally两SHA256恢复一致，证据field_reset/rollback/proof.json。无旧测试或断言修改。
- 完整模块：原35及新增模块共891 passed、77项既有警告，证据field_reset/final/pytest.log及前后哈希清单。Python仅用外部QA runtime/上传/备份/日志、固定测试凭据及生产SQLite连接前守卫。
- 浏览器修后验收：同一真实公共组件/报表函数夹具，以实际UI预置自定义备注首列；reset/cancel后的DOM和可见已存JSON逐字节保持，reset/OK恢复日期首列/备注末列及原名称，reload结果相同。browser-proof.json、browser-after-cancel/confirm的JSON/PNG与最终两产品manifest匹配；仅静态GET，页面/18081服务已关闭，未读写生产浏览器偏好或业务数据。
- 提交前验收：51项最终输入原始哈希前后稳定，FROZEN_FINAL.json及浏览器manifest匹配；文档契约34 passed、隔离HTTP冒烟121/121且自有服务已停止，verify_wms_bugs通过、A1–A14零违规、非GET请求/源码编码/diff通过。同一eb8970ca基线最新三工作流、实时远端及Android复用证明再次核实，证据field_reset/quality.json及precommit_ci_alternative.json。
- 提交与CI：2267c339a44ae2c20900d9239dc846c04dc21a33实际正常push（eb8970ca..2267c339 main -> main），HEAD/origin/live main一致；WMS CI40189447889、AI40189447877精确匹配completed/success，Android40177478067成功且祖先/对象/保护路径证明通过（field_reset/target_ci.json）。生产统一验收待执行。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

## （已修复；R8回滚后重做完成）

### BUG-2026-10-25-010: 需求预测旧响应覆盖新条件及分类和结果渲染失真

- 状态：已修复，生产已生效（2026-10-25）。
- AI子修复归属：AI-C13-FIX-FORECAST-LIFECYCLE-001；既有AI-C13需求预测前端修复，不新增AI能力。完成状态须在真实推送、目标CI及生效验收后登记，不提前写已完成。
- 根因/危害：30天与7天请求乱序时旧结果覆盖新结果；刷新重建分类下拉丢选择，actionFilter仍为需补货却渲染全量。合法空数据响应无summary触发TypeError；旧POST仅读JSON可将HTTP500 success正文误作成功。分类option及表格把普通<>&引号文本拼作HTML，导致标签解析和选项值截断。
- 同类点已排查：关联AI-R15前端反馈及BUG-2026-10-23-014文字/事件隔离、本轮异步查询/传输历史；该预测端点全仓仅此页一请求消费。summary和aiAnalysis已有text安全，不重复修改；本页分类及明细两个文字消费统一处理，不改预测算法、CSV导出、权限/模型/工具/开关或后端库存。
- 开工门禁：实时main2267c339a44ae2c20900d9239dc846c04dc21a33；WMS CI40189447889、AI40189447877精确匹配success，Android40177478067成功且复用证明通过（field_reset/target_ci.json）。
- 修前基线：原5个完整受影响及相邻模块68 passed，严格AI台账通过；目标2267c339、产品/依赖/测试/台账及3QA helper哈希稳定，证据ai_pages/final-qa-baseline/baseline-evidence.json。整页/API乱序与渲染审计探针均已复现，render-audit-proof.json不冒称真实浏览器攻击执行。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。

- 修复：请求代次与条件快照共同校验旧响应，重复生成只发一次；条件变化即时隐藏旧结果，旧finally不解锁新请求。统一postRaw校验HTTP及响应结构，兼容真实无物料分支的缺summary空态；分类重建保留原值，刷新沿用状态筛选。分类option及明细文字使用真实公共escapeHtml，保留普通尖括号/引号文字。生产需重启 WMS 服务生效。
- 回归锁：新增25项整页运行测试，执行真实api.js及escapeHtml；真实隔离后端空响应流入整页验证。物理回退模板后24 failed/1正对照passed，finally SHA256恢复；乱序及文字用例分别以业务断言失败，不靠缺helper。原5及新增共6完整模块93 passed，旧测试不改。证据ai_pages/rollback-evidence.json、rollback-tests.log及模块回归日志。
- 提交前验收：安全隔离verify_ai_all.py --level full --jobs 1完整70/70及严格台账通过，双memory配置、生产文件连接前拒绝、全网络零白名单、固定QA凭据及外部上传/日志/备份/临时目录；3helper及原full输入前后SHA稳定（full-evidence.json）。full后仅清模板319新增行尾空格，before/after及whitespace-only-evidence证明其余字节不变；最终6模块93 passed（final-after-whitespace.log/final-freeze.json）。首次diff检查查出该空格并修正，最终diff通过。文档34 passed、A1–A14零违规、非GET请求/编码/BUG回归通过，隔离HTTP121/121且自有服务停止。基线最新三CI及实时main/Android复用已再次证明，precommit_ci_alternative.json；无生产业务操作。
- R8回滚：d6eab925实际已push，AI40190824722成功，但WMS CI40190824670的unit-tests-shard-1两项旧test_page_feedback_runtime失败：只摘generateForecast而漏加载新增辅助函数forecastContextKey。新增整页锁/安全70/70和93模块当时通过，但受影响范围漏纳旧摘取夹具，不能报告完成。原测试断言未削弱；根已git revert --no-commit撤回本组模板与新增测试，保留开发中任务和本BUG历史；回退后旧完整模块26 passed。根因实证ai_pages/ci-failure-evidence.json；用户已明确允许本次4文件R8回滚提交推送例外；仅此次临时越过实际红灯pre-push CI门禁，保留main分支检查且finally清除进程环境，不借查询403替代实际红灯。011中断基线只保留日志不计通过。生产未统一重启，本组生效确认仍待重做。
- 回滚实证：a3741b6954dfbfc174a464a4825482fd6f2ab276实际push d6eab925..a3741b69，HEAD/origin/live一致；一次进程环境已finally清除。WMS CI40191551194、AI40191551173精确completed/success，Android40177478067及祖先/完整对象/保护路径无差异证明通过（rollback_target_ci.json）。新修前基线原5加漏纳旧feedback完整模块共94 passed、严格AI台账通过、全部输入及3helper稳定。旧摘取夹具对同一d6模板快照2 failed/24 passed，外部完整预测页夹具26 passed；全部旧CASES AST与旧assert行保留，增加实际请求/CSRF/失败状态断言，证据redo/red-green-evidence.json。获绿后才重新授权产品恢复，不在红灯基线写下一批。
- 重做最终验收：产品模板及25新锁按d6 Git原blob恢复；仅增强旧预测场景夹具，加载真实完整inline、escapeHtml、api.js和jQuery生命周期依赖，26旧CASES/全部旧assert保留并新增一次POST、URL/body/CSRF、按钮及失败结果检查。7完整模块119 passed/30.39秒，严格AI台账通过；物理回退模板后25新锁24 failed/1对照passed且finally字节SHA恢复。full70未重复跑，full70-reuse-proof.json证明当前app/scripts/samples/requirements/权限矩阵/PLAN/AI分片相对d6投影无差异、与原full模板仅换行及末尾空白差异、70脚本及3helper SHA一致，复用此前真实70/70实证；修改测试所需编码/BUG/规则/文档均已刷新。redo/quality文档34、隔离HTTP121/121并停止自有服务、A1–A14/请求/编码/BUG/diff全部通过，最终产品/测试/PLAN freeze匹配。新提交仍须完整目标CI；生产需重启 WMS 服务生效。
- 重做提交与CI：db1560d690227d01dd11577604438ea929a44ed3实际push a3741b69..db1560d6，HEAD/origin/live一致。首推匿名查询403，连接器新证据证明同一a374基线全绿后单次临时环境重推并finally清除（redo/prepush_retry_ci.json）；这不是实际失败门禁例外。WMS CI40192225964、AI40192225950精确completed/success，Android40177478067及祖先/完整对象/保护路径无差异证明通过（redo/target_ci.json）。生产统一验收仍待后续两组。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-011: 公共查找单据旧请求覆盖新条件或取消后仍打开旧单

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：标准弹窗没有请求/输入/生命周期代次，轴承旧回包覆盖螺母新结果，旧失败清空新成功；180ms防抖窗口旧候选仍可点，关闭不取消未发出的定时器。无Bootstrap的prompt分支也没有共享调用代次，两次查询乱序或第二次取消后旧回包仍打开旧单。
- 同类点已排查：关联本轮主数据编辑、预测页及既有物料查询生命周期历史；本组核两种showDocumentSearchModal分支、换模块、关闭/重开/DOM替换及取消。只改该函数，独立fetchDocumentNavigation/navigateDocument/getDocumentNavigationApiUrl与翻单保持；原80条和total提示、GET及row.url优先/embedded保持。base全局网络/5xx/会话提示属于既有统一层，不宣称局部失效能抑制其兜底。
- 开工门禁：实时main db1560d690227d01dd11577604438ea929a44ed3；WMS CI40192225964、AI40192225950精确success，Android40177478067及复用证明通过（ai_pages/redo/target_ci.json）。
- 修前基线：67个完整旧消费及相邻模块2529 passed/21既有skipped/0 failed；原63计划补上forecast/common_delete/page_feedback和唯一间接CJS field_settings消费者，1321源码/测试/夹具及外部helpers前后SHA稳定，credential_file_events=[]（search/baseline-after010-redo/result.json）。此前d6基线因R8中断，只保留不计通过。
- 只读复现：真实app.js完整函数、api.js及base全局fetch层，53外部候选31项业务断言红/22正常对照绿，0缺DOM或缺helper假失败；fallback两prompt先B后A导航22后11、取消仍开旧单等已复现。证据search/candidate-harness-evidence.json及fallback-proof.json。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：每次进入含prompt取消推进共享入口代次；modal内部输入即时推进查询代次、清候选、冻结180ms关键词，成功/失败/点击同时核对入口、局部代次、关键词及原DOM身份/连接状态。hide与hidden均使本轮失效并取消timer；有效fallback仍打开首条。仅showDocumentSearchModal内修改，函数外原始字节SHA一致（product-scope-proof.json）。统一层全局网络/5xx及会话提示保持，不把旧局部失效描述成全局错误静默。
- 最终验收：53新运行锁通过；物理仅回退app.js后31业务断言failed/22正对照passed，0缺helper/DOM错误，finally3文件原始SHA完全恢复（rollback/proof.json）。68完整模块2582 passed/21既有skipped，1323输入及6外部helpers前后SHA稳定、credential_file_events=[]、四连接前安全预检通过（final-regression/result.json）。root quality文档34、隔离HTTP121/121且自有服务停止、规则/请求/编码/BUG/diff全部通过。
- 真实浏览器：静态隔离页使用15个真实函数、api/base及真实Bootstrap5.3，CUA实际输入轴承再螺母、先回螺母后旧轴承，候选仍IN-FIXTURE-22并正确选择URL含embedded=1；关闭后再返回两个晚包无候选/无导航。browser/after-proof.json、after-race.png、after-close.png与freeze产品manifest匹配；无WMS连接，页面与18081自有服务已关闭。提交前最新同一db1560d6三CI及Android证明再次核实（precommit_ci.json）。
- 提交与CI：9771b84282083962bf4562358386b79121bfdb05实际正常push db1560d6..9771b842，HEAD/origin/live一致；WMS CI40194043677、AI40194043659精确completed/success，Android40177478067及祖先/完整对象/保护路径无差异证明通过（search/target_ci.json）。生产统一验收待最后一组。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。

### BUG-2026-10-25-012: 库存查询打印忽略当前筛选和排序

- 状态：已修复，生产已生效（2026-10-25）。
- 根因/危害：真实stockPrintBtn仅传warehouse_id；即使手工携带search/category_id/stock_filter/sort/order，report_stock_print的旧Excel及模板Excel分支仍各自查询所有物料，导出行集与列表筛选/排序不一致。
- 同类点已排查：关联BUG-2026-08-12-005仓库级导出、R1分页与本轮报表快照问题；本组库存查询列表和旧/显式/默认模板Excel三种入口统一候选查询，打印取筛选全集而非当前页。保留既有_alert_status_for两级预警（low含danger、normal含disabled）、允许排序字段、resolve_request_warehouse和get_warehouse_stock_quantities；不改库存服务/总账/历史归属/app.py。
- 开工门禁：main9771b84282083962bf4562358386b79121bfdb05；WMS CI40194043677、AI40194043659精确success，Android40177478067及复用证明通过（search/target_ci.json）。
- 修前基线：25完整模块208 passed/88既有warning，202输入及helper/runner前后SHA一致，main/HEAD/origin严格9771b842，stock012-baseline-after011-target-proof.json valid=true。此前008刷新结果保留，当前使用011后的新证明。
- 只读复现：4仓、61物料（58专用分类跨3页）、实际列表GET和两Excel分支含显式/默认模板，61场景旧码56业务断言failed/5正常对照passed/0 errors；实际href和模板change亦红，无缺新helper的伪红（report_print/stock012_candidate）。历史MA显式2+可解析NULL3=甲仓5，乙仓8；孤儿50保留未归属桶，global63与已归属13差50不当作库存BUG、不回填。
- 生效确认：2026-10-25T21:04:39.954495+08:00，原WMS-Warehouse任务已重启本轮模板，PID13304/Session0、产品目标607b1d0bed3e5a73c52f19da10688ebf96adfb1c；本地及公网登录GET200/CSRF正常、静态资源原始SHA与Git产品身份一致、8张核心表摘要前后相同且quick_check=ok。生产需重启 WMS 服务生效，本轮已完成；已有浏览器需刷新加载。
- 修复：get_stock_query_filters规范化原有效参数，build_stock_material_query提取原搜索/分类、仓库级两级预警及IN补集和允许排序；页面继续原paginate，report两Excel输出共享同一筛选全集.all()。href仅从服务器有效条件urlencode生成，排除page/per_page/embedded等；原模板切换从baseHref构造URL已正确保留这些条件，无需重复改JS。仓库解析/读取helper、app.py、历史归属及原价格/金额字段公式均未改。生产需重启 WMS 服务生效。
- 最终验收：新61真实GET/xlsx/模板change锁通过，三产品物理备份回退后56业务断言failed/5正对照passed，finally三原始SHA恢复（stock012_rollback/proof.json）。原25及新增共26完整模块269 passed/304 SQLAlchemy既有告警，200输入前后稳定、4 owned冻结文件匹配，无旧测试改动（stock012-final-result.json及stock012-final-freeze.json）。R1跨页58行打印全集逐行/顺序=列表三页合并；R2四仓隔离、历史NULL解析、孤儿50不回填、打印完整行数量与筛选全集逐行相等，非分页抽样；库存读取和金额原公式保持。新test便携ROOT、pytest tmp_path_factory、无全局chdir，static/config和数据库嵌套finally恢复，公共helper由同名实际契约测试覆盖A9。
- 提交前验收：文档34 passed、隔离HTTP121/121并停止自有服务、A1–A14零违规、请求/编码/BUG/diff通过（stock012_quality/quality.json）；同一9771最新三CI及实时main/Android复用再次证明（stock012-precommit-ci.json）。未连接生产业务或真实打印；后续将以全批候选再做完整AI70及统一生产验收。
- 统一生产发布实证：目标WMS CI40195076695/AI40195076713成功且Android复用证明完整，发布候选安全完整AI70/70通过；在线一致性备份、旧/新Git代码包及manifest、进程/任务/端口/启动SHA/HTTP/资源/只读业务摘要证据保存在C:/wms_backups/frontend_ten_20261025/deployment。未执行生产业务POST、单据操作、真实打印或账号密码修改。
- 最后一组提交与统一验收闭环：607b1d0bed3e5a73c52f19da10688ebf96adfb1c实际push 9771b842..607b1d0b，HEAD/origin/live一致；首推匿名查询403，连接器核实同一9771基线三CI全绿及Android复用后仅该次临时环境重推并finally清除（stock012-prepush-retry-ci.json），未绕过实际非绿。精确目标WMS CI40195076695、AI40195076713均completed/success。最终完整AI70/70、输入及清单SHA稳定（deployment/final-ai-full/evidence.json）。在线备份完整性通过并保留回退代码包；原任务单次重启后PID13304唯一监听8080，LastTaskResult=0，启动日志607b1d0与产品目标一致。日志migrate=ok仅记启动核验结果，不据此宣称执行过迁移。公网urllib曾遇TLS EOF，改用正常证书校验的Invoke-WebRequest取得登录和5脚本200及原始SHA证明（public-http.json）；本地实时HTTP和公网保存响应复核均通过。deployment/effective.json verified=true，8核心表摘要前后完全相同。此次收尾仅更新4份文档，产品代码不变，无需第二次重启。

## 已修复：二十子代理前端批次（2026年10月25日，代码，按批统一提交）

统一交付闭环（2026-10-26）：59文件业务批次6943bb725a9ca5988fbd868daf519f89ec224e46实际push25cc75d6..6943bb72；漏纳入的采购测试及台账补正仅2文件，实际push6943bb72..5d2f3dd3，最终部署目标5d2f3dd37fad8a28a82c209e129b58272689da1b，HEAD/origin/live一致。首批匿名查询403仅按已证实全绿的查询故障重推；随后实际8项夹具失败按用户续修指令落地已展示候选，记录真实红灯及本次2文件推送例外，不冒称基线全绿；临时环境均finally清除。精确目标WMS CI40247497486、AI40247497523均completed/success；Android40233861271原样重跑81项及build/lint成功，6943为目标祖先且Android路径不变。原138模块4132 passed/107既有skipped、隔离HTTP121/121通过；补正模块及相邻/文档384 passed，原1344验证输入仅该已单独验证测试变化，其余1343一致，29产品字节匹配。在线备份及旧/新代码包保留，原任务单次重启、源码/启动/HTTP/资源和8核心表只读摘要核验通过（deployment-v2/effective.json）。026/027仍未修复；本次收尾仅写BUG台账及审计记录，不再写入下一批产品代码，无需二次重启。

2026-10-26 CI补正续修：用户在已展示的单测试夹具及台账候选后指示“继续上面的任务”，本次仅落地该范围。6943bb72的WMS CI40204872609及定时40233867667均仅采购导入旧夹具8项失败；本地138模块漏纳入test_purchase_transport_runtime.py。保留真实async前缀、补importFileButton依赖，并加强成功刷新期输入/按钮/pending锁断言；原42场景、载荷/错误/确认/失败重试断言保留。外部原8失败/34通过、候选42通过及重复验证、19独立复审已记录（C:/wms_backups/frontend_twenty_20261025/17/ci-fixture、19/ci-fixture-review.md）；落仓后的该模块、相邻及文档共384 passed，规则0违规、严格AI台账和编码检查通过，1344原验证输入中仅该测试变化，业务代码完全一致（ci-repair-20261026/source-proof.json、local-result.json）。昨夜Android40233861271中1个既有Room/Robolectric单测缺表失败，原样重跑attempt2后工作流成功，APK build/lint通过；未改Android源代码，不把一次重跑成功称为根治偶发I/O问题。实际推送和新目标CI另验，本批生产仍未重启，生效确认待验收。

本批提交前验收：最终138完整模块4132 passed / 107既有skipped / 43 warnings，源码、测试及隔离守卫前后SHA稳定，凭据事件[]（C:/wms_backups/frontend_twenty_20261025/final-regression-2/result.json）。首轮56失败定位为旧夹具遗漏async/真实依赖及成功刷新期锁契约；5旧测试补齐真实依赖，原请求载荷、错误、确认、失败重试与下载断言保留，成功刷新前加强为输入/按钮/pending同时锁定，独立复审见19/final-fixture-review.md。规则/请求/编码/历史BUG及文档34项通过；隔离HTTP121/121通过。初次冒烟的Waitress内部随机端口触发器被严格网络守卫拒绝，外部启动夹具改用Werkzeug WSGI后通过，产品和网络守卫未放宽（quality-accepted.json、smoke-final/smoke.log）。未执行生产业务操作；本批CI与生产生效继续分别验收。

### BUG-2026-10-25-013: 采购申请改写物料文字后仍携带旧物料身份

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：输入非匹配或清空后旧materialId仍可优先落库，显示编码与提交物料不一致。
- 同类点已排查：01/13；关联09-22-012未解析物料校验与10-24-016旧隐藏ID模式；新增/编辑共用模板。
- 修复：输入立即失效旧身份和派生字段；唯一精确匹配正常回填；保存核所选编码快照，保留数量/报价及人工名称行。
- 回归与回退：13/HANDOFF.md；双页共36真实脚本场景；本页物理旧码6失败/5正对照，原始SHA恢复；旧transport42断言保留。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-014: 独立新增物料改写单位供应商文字后提交旧隐藏ID

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：文字非空改变未清旧关系ID，实际FormData与可见单位或供应商不一致。
- 同类点已排查：05/13；委外旧ID同根因的独立消费点；主列表quick-select保存前已有解析。
- 修复：输入立即清ID，保存按显式选择或唯一精确码名解析；未知/歧义中文拦截，可选空值和新建单位保留。
- 回归与回退：13/HANDOFF.md；本页25场景，物理旧码18失败/7正对照；finally精确恢复，双页合计36场景。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-015: 采购销售复制及模板往返和售后复制遗漏行上下文

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：行合同编号/工程名称或备注未复制，重新录单或加载模板丢失项目上下文。
- 同类点已排查：01/04；BUG-2026-10-15-001复制遗漏字段的未覆盖消费点；采购两复制入口、销售新增编辑及模板、售后均排查。
- 修复：四模板复制/模板加载白名单补齐原有字段，保存接口及价格算法不变，合法0价/0税率保持。
- 回归与回退：root copy-lock-before-v2.log及copy-rollback/proof.json；12锁通过；物理回退4模板6业务失败/6空字段与零值对照，通过后精确恢复；初版新夹具曾用错售后code键，修正夹具后才计有效红锁。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-016: 入出库详情动态新增复制行与实际列布局及列顺序脱节

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：动态行沿历史固定td布局，复制按cells索引读取，合同工程被当单位库存，重排后物料编码错位。
- 同类点已排查：02/16；两详情新增/插入/复制、默认/重排/隐藏列、来源采购/客供/批次有效期同类点已排查。
- 修复：按真实表头column-key构建/重排；按稳定字段复制保存上下文；末行复制追加；来源只读；不能保留客供标记时明确提示并停止复制，避免静默转普通料。
- 回归与回退：16/report.md/result.json；24新Jinja+Node矩阵与两详情transport合计272 passed；逐页物理回退12失败/12正对照，各自SHA恢复。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-017: 入库新增校验了库位但提交载荷遗漏location

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：表单读取并校验库位后未写入data，开启管理填了库位仍被后台拒绝。
- 同类点已排查：02；当前项目画像库位关闭时不属现场阻断，开启库位管理的条件问题；同类出库/shared表单已有location。
- 修复：实际保存载荷带入同一个已trim并校验的location，仓库/后端库存规则保持。
- 回归与回退：test_printer_options_location_runtime.py含未开启/已开启空值/有效库位及0价；物理回退本页2失败/2对照；初版新夹具截取越过函数及误建空库位场景已纠正后才计有效红锁。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-018: 物料网上找图迟到请求串入新物料弹窗并误操作旧上下文

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：A关闭开B后A旧卡片追加到B且按钮仍保存A；旧保存回包还可关闭或刷新B。
- 同类点已排查：05/20；004主数据edit图片已保护，本组独立materialImageModal漏点；GET/POST/关闭/重开/DOM替换/多候选同类点已排查。
- 修复：局部物料/DOM/生命周期代次保护，查询保存成功失败均核当前上下文，hide/hidden失效，选图及成功刷新期互斥；保留人工选择。
- 回归与回退：20/HANDOFF.md；32新锁，物理回退26失败/6对照，精确SHA恢复；004相邻28及独立联合57通过；root真实Bootstrap隔离浏览器已验证B先回/A后回不串图、旧保存不关新窗且刷新0，截图browser-race.png。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-019: 复制剪贴板失败仍显示成功及Excel粘贴错误未处理

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：未等待writeText或忽略execCommand false/throw，合同/手机地址/令牌/Excel显示成功但剪贴板未变，创建工作站后可能误导重复创建。
- 同类点已排查：06/09/14/18；全站9组clipboard/execCommand消费者已核；现有明确降级的期初/分享及无误成功的AI复制不重复改。
- 修复：仅真实成功才提示；兼容无API/拒绝/异常、明确失败与手动兜底；工作站创建成功和复制失败区分，单次POST，现有令牌可见范围保持；Excel读写异常受控。
- 回归与回退：18/HANDOFF.md；63正式场景通过；六入口独立物理回退各触发7/9/10/11/10/5业务失败，精确恢复后63再绿；外部驱动GBK解码异常修正为UTF-8，非产品失败。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-020: 十一单据列表导入缺互斥且旧请求清空新文件提前刷新

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：多个文件并发上传，先回包finally清掉后选文件，成功900ms导航窗仍接受新导入而丢反馈。
- 同类点已排查：08/17；公共app.js/Excel组件及sales_order原已有保护，11个opt-out本地消费点遗漏，全部一并覆盖。
- 修复：构造FormData后锁定本地入口及文件控件，成功至刷新保持锁；失败恢复原disabled并允许人工重试，finally只清同一文件，保留原提示与委外人工确认。
- 回归与回退：17/delivery.json；11页187真实函数+api.js场景全绿，逐页11/11物理回退产生预期业务失败，finally精确恢复后187再绿；差异仅对应按钮id和本地导入函数。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-021: 打印路由已知打印机列表重复解包导致候选为空

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：get返回已解包对象，loadKnownPrinters仍读res.data.known_printers，真实成功列表被当空。
- 同类点已排查：09；WMS.api默认已解包data，同类get/getRaw消费者由12核对未确认其它新漏点。
- 修复：按统一API契约读取known_printers数组，不改打印任务/代理/令牌/后端接口。
- 回归与回退：frontend_printer_options.cjs真实api.js五场景通过；物理回退1失败/4对照；回退打印机消费时验证SHA等于18冻结版，未覆盖剪贴板修复。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-022: 标签页支持十五项但刷新只恢复八项并覆盖持久化

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：restore固定slice(0,8)，9至15项刷新丢失并被重写存储。
- 同类点已排查：11；BUG-2026-07-28-015原上限15与持久化能力的恢复分支遗漏，非新增标签需求。
- 修复：恢复上限统一MAX_TABS，保持原上限/去重/导航策略。
- 回归与回退：完整真实WmsTabs IIFE的1/8/9/15项恢复锁4通过；物理旧码2失败/2对照，SHA精确恢复。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-023: 报表查询失败后仍展示上个仓库的汇总

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：新仓库失败后明细报错/页脚0条，顶部仍为上个仓库数量金额。
- 同类点已排查：10；区别于005打印快照及012库存打印筛选，复核成功与当前请求失败分支。
- 修复：当前有效失败将三汇总置为不可用符号而非假称0库存，成功和过期请求隔离保持。
- 回归与回退：真实loadData/renderSummary四场景：网络/HTTP/业务/JSON失败；物理回退4业务失败，各例先验证正常成功，finally精确恢复。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-024: 公共quick-select关闭后被迟到响应重新打开

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：hideMenu不失效请求或取消防抖，Esc保留焦点使旧回包再次展开。
- 同类点已排查：12/19；共享全站组件，区别于已修采购选单/合同/期初独立组件；Esc/外点/scroll/resize/input/blur/IME/owner/showAll/DOM连接同类点全覆盖。
- 修复：共享代次、owner、词快照、焦点和DOM连接核对；统一关闭取消防抖并使请求失效，保留普通键盘/搜索提交及API/候选池协议。
- 回归与回退：19/quick-select/HANDOFF.md；34真实整段JS场景通过；物理回退19业务失败/15正对照，finally原始SHA恢复后全绿。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-25-025: 委外产品单价允许编辑但保存静默丢弃且换料残留旧价

- 状态：已修复（整批回归、目标CI及生产发布核验通过；未在生产执行真实业务回归）。
- 根因/危害：用户编辑页面金额后保存仍按主价，旧非空价格又阻止换料更新。
- 同类点已排查：04/19；后端原使用物料档案主价，不新增单据独立价格模型；新增/复制/换料/未知/0值均排查。
- 修复：单价改为只读并给出物料档案提示，每次确认换料回填当前主价含0，未知/空料清派生价格金额，不改后端持久化/算法。
- 回归与回退：04/implementation/handoff.md；14真实函数场景绿；物理回退14业务失败，finally精确SHA恢复，原来源关联不改。
- 开工门禁：main25cc75d6d20d024d7bedc75e66185ea34a96613a，WMS CI40198277913/AI40198277927成功，Android40177478067祖先/完整对象/路径证明通过；54模块1460及追加66模块2281 passed/107既有skipped，输入/helper稳定、凭据事件[]。
- 生效确认：2026-10-26T08:11:18.774223+08:00，Codex自动部署核验；产品目标5d2f3dd37fad8a28a82c209e129b58272689da1b，WMS CI40247497486/AI40247497523成功及Android复用证明完整。已按『生产需重启 WMS 服务生效』要求完成在线备份与原任务单次重启，PID15544唯一监听8080，启动SHA/源码身份、本地与公网登录200及3静态脚本SHA通过；8核心表摘要完全相同。隔离环境流程验证与生产部署核验分开记录，未在生产执行单据保存、库存写入、密码变更或真实打印；业务操作效果由用户后续正常使用确认。完整证据C:/wms_backups/frontend_twenty_20261025/deployment-v2/effective.json。

### BUG-2026-10-26-001: 库存报表切仓后仍列出其他仓的零库存物料

- 状态：已修复（208项模块回归、目标CI及生产生效核验通过）。
- 现场复核：用户确认“切仓后仍显示其他仓的物料”。2026-10-26只读核对生产，铜排仓WH004有明确归属的物料32种、数量415，而物料档案全集1373种；截图的1373/415与旧逻辑一致。只读SQLite使用mode=ro及query_only，不登录生产或写业务记录。
- 根因/危害：_collect_inventory_rows虽然从get_warehouse_stock_quantities取得本仓数量，行集却遍历全部Material；没有本仓记录的物料被补0后列出，导致各仓物料名单与物料数相同。查询、导出及模板打印共用该行集。
- 修复：行集限定为仓库库存映射中确有记录的物料；有本仓记录但净额为0仍保留，由原hide_zero选项决定是否隐藏。负库存、价格/金额、排序、分页、筛选全集汇总、单仓既有短路及历史归属helper不变。生产需重启 WMS 服务生效。
- 同类点已排查：检索历史BUG-2026-08-12-005、08-17仓库级报表、09-07-015性能及10-25-012打印筛选记录；库存报表API、Excel导出、分页全量网页打印和模板打印均走同一builder，本次统一生效。库存经营分析有明确的“全部物料用于缺货预警”既有契约（09-07-021 T1），并非本次静态库存报表行集要求，不改其语义；新增对照测试保护。库存查询/预警及三账读写规则不修改。
- 开工门禁：main5197cd2df2f58cec390c30755c71c30b1ec01c7a，WMS CI40248450022/AI40248450055均completed/success；Android40233861271成功，祖先关系、完整Git对象及工程/工作流未变化证明通过。钩子已启用，工作区原有两份未跟踪审计报告保留。
- 回归锁：18项真实接口/Excel用例覆盖开关库位两模式、A/B/空仓切换、净零保留及隐藏、负数、供应商/关键词交集、显式ID优先、历史名称/编码/来源归属和无法归属记录、默认/无默认/无效仓库、分页排序及全集汇总、全量导出/模板打印，以及经营分析原缺货行集。旧代码14 failed/4 passed，修复后18 passed；物理备份app.py后checkout旧版本再跑仍14 failed/4 passed，finally逐字节恢复且SHA256相同，不使用stash。第一次新夹具漏填隔离用户必填password_hash导致18 errors，修正测试建档字段后重新完成以上有效验证，未据夹具错误声称回归锁通过。
- 模块基线与最终回归：原13模块107 passed；最终17个受影响/相邻模块203 passed（353项既有SQLAlchemy警告），报表JSON异常模块独立进程5 passed，合计18模块208项通过，输入/helper稳定、生产凭据访问事件为空。首次18模块混跑时旧异常模块在收集期设置TESTING=False，导致其他模块的内存库drop_all守卫拒绝；按其原错误处理测试语义分进程执行，未改旧断言或绕过数据库守卫。另修正本次3行代码导致的INVENTORY_TRUTH.md两处函数行号漂移，原引用契约全部通过。证据C:/wms_backups/inventory_report_warehouse_20261026。
- 提交前验证：文档契约34 passed、隔离HTTP冒烟121/121且自有18080服务已停止；历史verify_wms_bugs、A1–A14、非GET请求检查、严格AI台账、UTF-8编码及staged diff检查全部通过。测试子进程的SQLite/网络守卫保持启用，生产路径兜底连接在connect前拒绝；所有QA凭据、上传、日志与数据库在隔离环境。目标基线check_ci_green.py --target-sha完整SHA --json为ok=true。
- 目标CI与推送：918525cebce76c9c49493d8104cc462f3d0bc5bd已实际push（5197cd2d..918525ce main -> main），HEAD/origin/live一致；[WMS CI40254414896](https://github.com/SIX2090/wms/actions/runs/40254414896)与[AI40254414707](https://github.com/SIX2090/wms/actions/runs/40254414707)准确匹配completed/success，Android最新成功记录祖先、完整对象和工程/工作流无变化证明通过。本地源文件与全部回归输入SHA保持一致。
- 数据快照复核：官方在线备份载入守卫保护的内存库，用真实报表builder验证四仓行集/全集汇总，铜排仓32种/415；未对生产发登录、报表写入或打印请求。
- 生效确认：2026-10-26T09:33:40.777437+08:00，Codex自动部署核验；已在线备份并保留旧代码回退包，核对原PID15544身份后沿原WMS-Warehouse计划任务单次重启，新PID4396，Session0、8080唯一监听及任务LastTaskResult=0；启动SHA/源码身份、本机与公网登录GET200及CSRF均通过，8张核心表重启前后完整行摘要一致、quick_check=ok。生产需重启 WMS 服务生效，本次已完成；不改真实库存、业务单据、仓库/库位开关、账号或密码。完整证据、备份和回退包C:/wms_backups/inventory_report_warehouse_20261026/deployment/effective.json；本次收尾仅文档，无须再次重启。

### BUG-2026-10-26-002: 出入库汇总只有日期业务量，无法逐物料核对期初收发存

- 状态：已修复并交付（最终目标CI与生产生效已核验）。
- 用户确认与复核：用户明确要求“按物料看期初、入库、出库、结存”。旧summary按日期聚合入库/领料明细，顶部把进出数量相加，不能作为逐物料余额表；in_count/out_count实际计明细行却标单据数。参考金蝶官方存货收发存汇总表及用友YonSuite官方物料期间汇总结构，落实为本WMS数量报表，不扩展财务成本核算。
- 修复范围：默认出入库汇总入口、报表中心预览及导出转为material_movement；保留summary_view=daily与原summary API日期口径，并把原“单数”更正为明细行数。新表按仓库/物料列出期初、本期入库、本期出库、期末结存，顶部按单位分别合计。独立report_material_movement模板目标已登记到统一报表注册表，既能按模板打印，也能在模板中心新建/编辑，不覆盖旧日报模板。生产需重启 WMS 服务生效。
- 数量与历史边界：使用库存事实、台账同源仓库归属和单据业务日期；期初为开始日期前累计，本期含边界日，包含期内建账、调拨、调整及其他实际库存变动，逐物料满足期初+增加-减少=结存。未选日期从建账开始统计；首次页面默认本月，不限日期刷新/切视图仍保留。库存流水按ID每批500取全，无50000行截断；多仓未知归属不猜、不用全局库存补余额。无实际库存变动的草稿不计入，金额不按当前价格倒算。
- 同类点已排查：关联09-07-006台账期初/合计、09-07-012日期汇总分页、09-24-001业务日期、10-25-011打印快照及本日001仓库行集。新查询/分页/汇总/Excel/网页打印/模板打印共用同一builder；报表注册、中心导出、模板中心选项/动态列一并覆盖。点击物料携同仓同期间及精确material_id联查，改搜物料后清除ID，避免相似编码串入。原库存写入、三账归属算法、权限、密码及库位开关不改。
- 开工门禁：main6685a269a8a6bc1f2947af27cdb3fa0b4f569da5，WMS CI40254852621/AI40254852593均completed/success，Android40233861271成功，祖先/完整Git对象/受保护路径无变化证明通过；钩子已启用。原14模块基线132 passed，模板中心原模块6 passed。
- 回归锁：26个真实接口/Excel/模板中心用例及6个实际JS handler用例，覆盖多仓/两种库位开关、历史名称/编码/来源及未知归属、补录日期、仅期初/本期建账/调拨/盘亏/售后、草稿与未来日期、同物料ID联查、单位分组、分页全量汇总、查询不写库、50003条流水、全量导出/模板输出、模板中心新建，以及错误清空卡片、打印快照转义、切视图及不限日期保持。物理回退app.py/路由/模板三处旧接线后26 failed且无夹具错误，再逐字节恢复与备份相同（rollback-proof-final.json）；新模块保留但旧版本不注册，不以缺文件模拟业务失败。最初草稿明细夹具漏填price/amount已修正，随后旧产品有效反证为22 failed，未把22 errors算成反证。
- 浏览器与QA隔离：真实隔离Flask+浏览器显示100件/50米期初、20件/0米入库、10件/10米出库、110件/40米结存及两行明细，截图material-summary-table.png；自有18080实例已停止，生产PID4396未动。首轮模板测试发现既有测试使用共享static目录，已备份清理本轮明确生成、生产未引用的4个Excel，并为后续验证增加外部static副本及共享上传写入前守卫；未改生产模板登记或业务库。最终验证使用加强后的隔离运行器。
- 文档与证据：数量、日期、单位、兼容入口及API见docs/REPORT_MATERIAL_MOVEMENT.md。完整日志、源文件摘要、反证、隔离守卫及截图在C:/wms_backups/material_movement_20261026。
- 最终模块回归：20个受影响/相邻模块185 passed（141项既有SQLAlchemy警告），新接口26项与JS运行时6项均在其中。输入、隔离运行器及守卫源码摘要稳定，凭据文件访问事件为空；模板中心原新建流程及原日报分页/筛选/导出/打印均保留。最终以外部static目录和上传写入前守卫运行，工作区未再生成QA模板。
- 提交前质量：文档契约34 passed、隔离HTTP冒烟121/121且自有18080实例已停止；verify_wms_bugs、A1–A14、非GET请求检查、严格AI台账、UTF-8与staged diff均通过。质量脚本及冒烟另启用外部static副本、生产上传写入前守卫，未把测试生成的模板落入共享目录。提交前同一main基线三工作流及Android复用证明重新核实，precommit-ci.json为ok=true。
- F01嵌入导航补验：首批6590937a79f462d343dfa13129cc96a6df759caf已实际push（6685a269..6590937a main -> main），WMS CI40258056568/AI40258056600准确匹配success，Android复用证明完整；发布前真实浏览器发现公共app.js的document冒泡导航覆盖视图链接生成的完整URL，仓库/日期/物料丢失，6590937a未部署。以该全绿目标为后续修复基线，仅在报表视图切换handler停止冒泡，不改公共导航；新增2项同时执行真实link handler和真实document delegate的事件传播用例，旧版2 failed/6 passed，修复8 passed，物理回退模板后仍2 failed/6 passed，再逐字节恢复（embedded-rollback-proof.json）。最终新回归为26个接口用例+8个JS用例。
- F01最终验收：20个模块187 passed（141项既有警告），文档34 passed、隔离HTTP冒烟121/121，质量8项全部通过，输入/守卫摘要稳定且凭据访问事件为空。真实浏览器在embedded模式验证“不限日期→按日期汇总→按物料收发存”保留warehouse_id=4/date_scope=all，返回本月与同仓同期间精确物料台账均正确（期初100、入库20、出库10、结存110）；最终截图material-summary-final.png。两个自有浏览器页面及18080服务均已关闭。
- 最终推送与CI：fbde45aeab5fd90a06bee81448eb7f973ee88796已实际push（6590937a..fbde45ae main -> main），HEAD/origin/live一致；[WMS CI40259211867](https://github.com/SIX2090/wms/actions/runs/40259211867)与[AI40259211839](https://github.com/SIX2090/wms/actions/runs/40259211839)准确匹配completed/success，Android最新成功的祖先、完整对象及路径未变化证明通过。187项模块回归与34项新增锁绑定最终源码摘要，反证及8项质量检查齐备。
- 数据快照复核：官方在线备份载入隔离内存库，用真实builder复核2026-10-01至2026-10-26铜排仓32种物料，条单位期初549+入库42-出库176=结存415；四仓全部历史结存逐物料均与仓库库存查询一致，汇总等于全集明细。未通过生产登录或业务请求跑测试。
- 生效确认：2026-10-26T10:32:42.686582+08:00，Codex自动部署核验；备份与旧代码回退包已保留，沿原WMS-Warehouse计划任务单次重启，原PID4396，新PID2524，Session0、8080唯一监听及任务LastTaskResult=0。启动SHA、本机/公网登录GET200与CSRF、静态JS哈希及5个产品文件身份均匹配；8张核心表完整行摘要重启前后一致、quick_check=ok。生产需重启 WMS 服务生效，本次已完成。未改真实库存、单据、库位开关、账号或密码；完整证据C:/wms_backups/material_movement_20261026/deployment/effective.json。收尾仅台账，无须再次重启；隔离截图不冒充生产数据。

### BUG-2026-10-26-003: 仓库月报跨仓零行、补录错月及多月余额累加

- 状态：已修复并交付（目标CI及生产生效已核验）。
- 复核与根因：用户反馈铜排仓月报仍1376行。旧实现物料全集×月份铺行，按created_at分月，从当前仓库余额倒推历史，跨月汇总又相加各月ending_quantity，且混合单位。日期快捷包含今天/本周/不限但后台一律按整月，界面语义不一致；单据实际零价被truthy判断排除并回退当前价。
- 修复：沿用warehouse_monthly入口、API、模板目标及原字段，实际builder委托独立只读月报服务。从StockTransaction库存事实、统一仓库归属、台账同源业务日期正向累计，分批500取全。按自然月选择本月/上月/本年，默认本月，旧日期链接兼容；各月结存连续，总览按单位分别取首月期初、期间收发、末月结存。普通查询不再铺开其他仓零记录物料，精确完整编码仍可核对零行。零价按实际0，兼容参考估值明确非成本核算。生产需重启 WMS 服务生效。
- 同类点已排查：查阅08-17仓库级月报、08-27-001/002/004/006、09-07-005实际价、09-24-001业务日期及10-26-001/002仓库行集/收发存记录；API、分页、汇总、Excel导出、网页打印、模板打印、精确物料台账联查同源覆盖。未更改库存写入、三账归属算法、账号密码及库位开关。
- 开工门禁：main bb151850b202cc1a8e639c8f1399951f2117ebcf，WMS CI40259695991/AI40259695988最新main运行completed/success，Android40233861271成功且祖先/完整对象/路径未变化证明通过，钩子已启用。原18模块163 passed，隔离数据库/网络/凭据及共享上传写入前守卫保持启用。
- 回归锁：新增26项真实接口/导出/模板打印及3项真实JS运行时用例，覆盖多仓、两种库位开关、历史归属/未知归属、连续月结转、补录业务日期、首末月汇总/单位分组、整月兼容、零月/仅期初、实际零价、缺失/非法仓库及月份、分页全集、精确ID台账、查询无写入、50003条流水和月份控件/旧链接/失败清空卡片。首次旧实现18 failed/6 passed且无夹具错误；修复候选20模块192 passed（127项既有警告）。最终回退反证及验收待补。
- 最终验收：20个模块192 passed（129项既有警告），其中26个接口与3个JS新增用例；物理回退app.py及模板后23 failed/6 passed且无夹具错误，finally逐字节恢复一致（physical-rollback-v3与rollback-proof.json），未削弱旧断言。质量8项全部通过：文档34、HTTP冒烟121/121、规则0违规、非GET检查、历史BUG验证、严格AI台账、编码及diff。所有测试输入/隔离守卫摘要稳定，生产凭据访问事件为空；首轮A9测试名称映射提示已对齐真实连续结转测试，嵌套helper明确私有，规则未降级。
- 快照及页面：在线备份载入隔离内存库，四仓9月/10月与真实物料收发存逐物料对照、月行恒等式及首末月/全集汇总均通过；铜排仓10月31种有记录物料，期初549+入库42-出库176=结存415条。真实浏览器验证月份区间/上月/清空条件/保留仓库与跨月不累加结存，重复说明移至表头、数量行不折行，最终截图monthly-final-v2.png（隔离演示）。自有页面及18080服务已关闭，未向生产发登录或业务测试请求。
- 文档与证据：docs/REPORT_WAREHOUSE_MONTHLY.md；完整隔离日志、反证、截图、CI及部署证据C:/wms_backups/monthly_report_20261026。
- 推送与目标CI：26f45291049cddcd537525cf824686eedd231d62已实际push，HEAD/origin/live一致；[WMS CI40261718899](https://github.com/SIX2090/wms/actions/runs/40261718899)/[AI40261718906](https://github.com/SIX2090/wms/actions/runs/40261718906)准确匹配completed/success，Android最近成功祖先、完整对象及路径无变化证明通过。
- 生效确认：2026-10-26T11:04:13.053932+08:00，Codex自动核验；沿原WMS-Warehouse计划任务单次重启，原PID2524、新PID4888，Session0/8080唯一监听/任务结果0。生产需重启 WMS 服务生效，本次已完成。在线备份与旧代码回退包保留，启动SHA、本机/公网GET登录及CSRF、静态资源哈希与产品文件身份均匹配，8张核心表完整行摘要重启前后一致、quick_check=ok。完整证据C:/wms_backups/monthly_report_20261026/deployment/effective.json；不修改真实库存、单据、账号密码或库位开关，隔离演示截图不冒充生产数据。收尾仅台账，无须再重启。

## （未修复；本轮独立复核后保留的后续批次）

### BUG-2026-10-25-026: 共享盘点新行及调整已存行仍混入全局库存口径

- 状态：未修复（已复核，待独立批次）。
- 根因/危害：03/07/19独立真实函数复现A10/B90时盘点发system_stock100/actual8、调整已存行显示100而候选10。初始候选、material-cache刷新、by_codes粘贴、切仓与既有冻结重选相互耦合；仅替换初始stock会再被覆盖。
- 同类点已排查：详C:/wms_backups/frontend_twenty_20261025/03、07、15、19相关报告，未重复宣称历史上位任务重新完成。
- 建议与边界：按R8登记待独立库存读取UI批次：保留已存冻结账面，统一仓库来源/刷新/粘贴/切仓，覆盖R2多仓、历史归属及汇总明细；本批未改库存算法、该读取链或生产记录。B11/F07名称见测试头注释，月度根记录不含明确F07完成项，不能将测试注释误作台账已完成证据。
- 2026-10-26完整页面补验：第一轮常用操作验收CJ07真实复现领料单选QA-001后从A仓切B仓，库存仍110；按接口约定warehouse参数查询B仓返回0。初始out_order路由已按默认/单据仓库序列化，但切仓无库存刷新；共享material-cache.refresh仍取全局物料，三个消费点为out_order_add、document_table_form、adjustment_add。并入本根记录统一待修，不能只修一个赋值。证据C:/wms_backups/core_journeys_20261026/outbound-switch-stale-v2.png及http-result-v2.json；详docs/audit/WMS_CORE_JOURNEY_BASELINE_20261026.md。尚未证明由近期某次修改引入，未改业务代码或生产数据。
- 生效确认：待确认；本条仅登记，不以本批其他前端修复或CI绿灯宣称此项已修复。

### BUG-2026-10-25-027: 库位推荐清除或换物料后旧推荐仍返回显示

- 状态：未修复（已复核，待独立批次）。
- 根因/危害：15/19实际完整脚本Node复现：清除后selected=null仍显示A推荐，选B后显示迟到A结果。014文字安全及010需求预测生命周期均未覆盖该页。
- 同类点已排查：详C:/wms_backups/frontend_twenty_20261025/03、07、15、19相关报告，未重复宣称历史上位任务重新完成。
- 建议与边界：待独立既有AI能力子修复：先登记唯一子项，按物料/代次/清除生命周期保护，保留人工点击及只读边界，完成完整AI与相邻验证。本批不改该AI产品/权限/模型/工具/开关/数据库；页面受库位管理开关约束，不把静态复现当生产现场已发生。
- 生效确认：待确认；本条仅登记，不以本批其他前端修复或CI绿灯宣称此项已修复。

## 已修复：库存台账物料候选滚动与续载（2026-10-26）

### BUG-2026-10-26-004: 库存台账物料候选无法滚动且超过50条的结果不可达

- 状态：已修复并交付（178项模块回归、51项组件场景、119项隔离冒烟、目标CI及生产生效核验通过）。
- 现场复核：用户截图中搜索“电线”后候选显示不全、滚动条不能下拉。隔离的真实库存台账页面复现：候选框内部滚动立即使菜单消失，265条同名物料仅能取得前50条。
- 根因/危害：公共quick-select在document捕获阶段对所有scroll无条件hideMenu；本地候选slice(0,50)、远程limit=50且无续载；旧接口SQL预过滤也把500条批大小当全集上限。固定290px菜单未完整收敛当前窗口边界。
- 修复：区分菜单内部与页面滚动；保留拖动滚动条时输入归属，结束后恢复焦点；按上下可用空间及左右边界限制菜单；分页返回offset/limit/has_more和全集total，匹配排序增加稳定键，SQL匹配分批遍历而不截断；触底或“加载更多”继续取候选并显示已加载/总条数。翻页失败保留已加载结果并提供重试；同页防重入，关闭/换词/断开DOM使旧页失效，旧服务忽略offset时拒绝追加重复第一页。生产需重启 WMS 服务生效。
- 同类点已排查：检索BUG-2026-10-25-024生命周期、10-24候选定位和AI-WMS-FILTER-005富展示历史。所有data-ks物料/供应商/客户等入口共享本次组件与GET接口；保留024原有34场景及其关闭请求锁。dropdown-position.js已排除菜单内部滚动，无需重复修改；本次不改库存账务、仓库口径、单据状态或打印链路。
- 验证范围：7个受影响模块基线69 passed；新增17个整段JS场景（共51个）及5个API场景，覆盖本地/远程分页、超过500条SQL路径、非法offset、265条末尾选料、滚轮、滚动条、键盘、陈旧响应、失败重试及短窄窗口；受影响和相邻14模块178 passed，文档契约34 passed、隔离HTTP冒烟119/119、7项质量检查全部通过。真实浏览器验证滚轮/拖动滚动条后菜单不关闭，265条全部可达且末条精确查询结存23，工作区iframe内也通过。物理回退旧源文件后16个新增JS场景失败、35个正对照通过，pytest 6 failed/68 passed，finally逐字节恢复修复；既有生命周期及Enter断言保留。
- 验证边界：浏览器和pytest均使用隔离数据库与外置静态文件；未操作生产单据/库存/账号。隔离HTTP冒烟保留原脚本页面/表单/导出检查，排除两项修改密码断言并限制只使用已知QA凭据，原因是账号密码修改不属于本次授权范围，不将该项计入通过数。完整证据C:/wms_backups/quick_select_20261026/。
- 开工门禁：main a3d4c8f19a518f5f481b7c65b25225e55b5a1f6d；WMS CI40276872199、AI40276872262均completed/success；Android40233861271成功，祖先/完整对象/工程及工作流路径未变化证明通过。钩子已启用，两份原有未跟踪审计报告保留。
- 生效确认：2026-10-26T14:42:35.420712+08:00，Codex自动部署核验；代码目标0a985d74ee7e7d264050a6460ea99d6ce41445a5已实际push（a3d4c8f1..0a985d74 main -> main），WMS CI40280887496/AI40280887590均completed/success且精确匹配，Android40233861271祖先/完整对象/路径证明通过。在线备份与旧代码回退包齐备，核对旧PID4888身份后沿原WMS-Warehouse任务单次重启，新PID3724/Session0唯一监听8080、任务LastTaskResult=0；启动SHA、源文件及本地/公网JS摘要匹配，登录GET200与CSRF通过，8核心业务表前后摘要相同、quick_check=ok。公网首次TLS传输EOF后以相同正常证书验证方式重试成功，无再次重启。生产需重启 WMS 服务生效，本次已完成；未执行生产业务或账号操作。证据C:/wms_backups/quick_select_20261026/deployment/effective.json；本次仅文档收尾，无须再次重启。

### BUG-2026-10-26-007: 共用报表工具栏打印入口分散且缺少所选模板的真实数据预览

- 状态：首批代码已修复、验证及推送，目标 4a0d7892e54c79ee2ad3f21317325cf9dcd88896 的 CI 已验收；2026-10-26 17:53 已按用户授权重启生产发布至 28c05b54，独立销售报表等后续范围未计入本条完成。
- 用户范围：保留现有菜单、筛选区和表格，只改工具栏与打印入口；用户明确要求不等待另一任务的全站下拉框改造。本批避开其公共 app.js、下拉组件、录单模板及原有暂存文件，不接手或混入该任务。首批覆盖共用 report_view 的 15 个注册报表类型，6 个独立销售报表及重复列表入口迁移尚未纳入本批。
- 根因/危害：页面把网页打印、模板下载和图标模板管理分散为多个入口；“按模板打印”实际下载 Excel；模板编辑器仅用示例数据，不能核对本次筛选结果。模板文件可用性、加载失败重试与默认选择未完整呈现，易误选或误以为已按所选版式打印。
- 同类点已排查：关联 PRINT-TEMPLATE-F04/F05、BUG-2026-09-07-008/019、BUG-2026-10-25-005 全量及打印快照历史；复用现有模板列表和编辑器，不重复建设模板中心。复核共用报表、库存查询及 6 个独立销售模板，后两组仍保留既有行为，不虚报全站已统一。
- 修复：工具栏统一刷新、导出、打印菜单与字段设置；报表显式拒绝公共 CRUD 工具栏注入。打印菜单可选择多套模板，默认选择可用默认项，缺失文件禁用，失败可重试并隔离旧响应。提供“预览并打印”“下载打印文件”“模板管理”，保留准确命名的标准清单打印。新 GET /report/<type>/print_preview 复用筛选、全量分批取数、排序及状态文本，在内存填充所选模板并呈现合并、样式、纸张方向、边距和打印区域；显式坏模板不静默替换，失败不给打印按钮，不登记模板或写文件/数据库。保留旧 Excel 下载接口与现有打印快照语义。生产需重启 WMS 服务生效。
- 能力边界：浏览器预览最多 5000 行/150000 单元格，拒绝截断打印及超限模板；公式、图片、图表和不支持版式给出 Excel 打印指引。浏览器字体与最终分页不等同原生 Excel，预览页明确提示人工确认，不声称实现 Excel 排版引擎。新预览在价格维度关闭时不提供金额数据，不改变旧导出策略。
- 修前基线：5 个相关模块 76 passed。最终受影响及相邻 14 模块 185 passed（28 项既有 SQLAlchemy 警告）；其中新增工具栏 14 场景、预览 23 项共 37 passed。包含模板加载/默认/缺失/失败重试/旧响应、刷新/Esc、仓库、筛选和排序；503 行实际入库明细强制 6 批取全、多仓隔离、合并页尾扩展、数值精度、XSS、样式和非法模板；SQL 监听确认预览无 INSERT/UPDATE/DELETE/DDL。
- 回归锁：新增控件测试在旧模板下先失败；物理备份后替换为 HEAD 旧模板，新用例如预期失败，finally 恢复前后 SHA256 一致。新预览路由物理回退后全量预览用例 404 失败，再逐字节恢复。未放宽或删除既有断言，不使用 stash。
- 浏览器核验：外置 9084 内存库示例实例，真实共用报表页加载两套 Excel 模板，切到纵向签收模板并打开新预览，3 条当前明细及数量合计 6 一致；纸张方向与物理宽高呈现正确。工具栏字段设置打开并取消、打印菜单 Esc 关闭通过。源码比较确认筛选表单和报表 table 标记逐字相同。截图及隔离启动脚本见 C:/wms_backups/report_toolbar_20261026/；未操作生产实例。
- 开工与提交门禁：实时远端 main c043228e3bd04b1fd318d389dbd97d10fe133026；WMS CI 40281534131、WMS AI Verification 40281534223 均 completed/success 且精确匹配；Android 40233861271 在 6943bb725a9ca5988fbd868daf519f89ec224e46 success，Git 祖先、对象及 Android 工程/构建工作流无差异证明通过。匿名脚本 HTTP403 仅为查询失败，经连接器 Actions 最新 main 完整列表核实；若同一基线 pre-push 仍因限流失败，只按规则临时使用已有 WMS_SKIP_CI_GATE，保留上述替代证据。钩子启用，规则及原生非 GET 请求检查通过。
- 推送与 CI：业务提交 d5a222cbdf85449e8c3333b17a99afe623c53bdb 已真实 push（c043228e..d5a222cb main -> main）。首次 CI 发现新增台账条目未同步历史状态核对表，仅补登记 POST_SPLIT_BUGS 的 007，不改 315/141/19/1 历史基线或断言；修前该模块 1 failed/9 passed，修后 10 passed。该项 CI 恢复经连接器仅更新同一个测试文件，API 返回 43200603d40891b08ce567fa71b43f25195f15f7，随后规范化 LF 得 4a0d7892e54c79ee2ad3f21317325cf9dcd88896；累计相对 d5a222cb 精确为一行新增。未用 WMS_SKIP_CI_GATE 跳过已知红灯。保留本地文件备份后快进同步，HEAD/origin/main/实际远端同 SHA、tree 88d80e41bb0e158168bf42828a9404f8b7fd8743 完全一致；verify_remote_sync.py 因缺少 GH_TOKEN 无法查询，改用真实 Git 协议 fetch、完整 tree 和连接器 commit/parent 反查证明，未提取凭据。最终 WMS CI https://github.com/SIX2090/wms/actions/runs/40299390104 与 AI https://github.com/SIX2090/wms/actions/runs/40299389982 均 completed/success 且精确匹配；Android 40233861271 祖先与路径无变化证明继续成立。其他任务暂存、未提交及未跟踪文件保持独立。
- 生效确认：2026-10-26 17:53（Asia/Shanghai），Codex 自动部署核验。目标 28c05b54bff12cfa8af1705ddc726898515edcf7 的 WMS CI40300239353/AI40300239255 均 success，Android40233861271 祖先与路径证明通过。发布前 tracked 工作区干净，仅保留他人未跟踪文件；SQLite 在线备份 integrity_check=ok，旧生产 0a985d74 代码回退包齐备。核实旧 PID3724/Session0 后沿 WMS-Warehouse 重启，新 PID384/Session0 唯一监听8080，任务结果0；启动日志 SHA28c05b5、启动初始化/迁移禁用，登录本机与公网 GET200 且含 CSRF。97表逐表摘要比较仅 print_workstation 心跳变化，业务表未变化，quick_check=ok。未登录或执行生产业务/账号操作；认证后工具栏与真实数据预览已由上述隔离实例核验。生产需重启 WMS 服务生效，本次已完成。证据 C:/wms_backups/report_toolbar_20261026/deployment/effective.json。


### BUG-2026-10-26-008: 七个独立报表缺少统一多模板打印工具栏且销售综合导出忽略筛选

- 状态：已修复并交付；目标3ce7644a的CI与生产重启验收完成。
- 用户范围：按用户“生产重启发布，接入7个独立页面”，先完成007已验收版本的生产发布，再接入销售综合、销售出库明细、销售趋势、销售订单执行、销售价格分析、销售对账和库存查询。保留菜单、业务导航、筛选与表格，不在报表新增业务单据操作；未迁移其余重复列表入口。
- 根因/危害：独立页面没有共享报表的真实模板预览入口；库存旧入口下载与选模分散。另在真实数据回归中确认销售综合 export 忽略客户、业务员、状态、发货状态、项目号与物料钻取筛选，可能导出页面查询之外的数据。
- 同类点已排查：复核 PRINT-TEMPLATE-F04/F05、BUG-2026-10-25-005全量打印、10-25-012库存打印筛选及10-26-007入口统一。六个销售旧导出逐项核对筛选，除综合导出外未发现同类丢筛选；其余导出的字段子集与排序保留。库存复用现有仓库级查询，不改库存三账、业务状态或历史归属。
- 修复：共享_report_toolbar宏及report-workbench.js接入七页，统一刷新、原导出、打印、字段设置；屏蔽通用CRUD栏。支持多模板、默认选择、缺失文件禁用、失败重试及旧请求失效；修改筛选后须先查询再输出，输出已查询条件的全部结果。综合报表明确客户/物料/业务员/明细四范围，字段设置定位各原表；其余五销售范围独立模板。六页面与打印复用原计算context，新增登录保护的/sales/<kind>/print_preview及print_excel；综合旧导出仅替换筛选数据源，保留原单表18列及文件名。生产需重启 WMS 服务生效。
- 库存兼容：保留list/stock_query模板命名空间、旧控件ID和筛选链接。新toolbar下载加template_mode=1，在内存按所选模板或系统内置版式填充，预览与下载一致且用户改工作表名称仍能填充；无该参数的旧标准下载格式保留。预览严格拒绝坏ID、跨报表/缺失/越界模板；全仓仍禁打印，价格关闭时不向模板传实际金额。新下载保护5000行/10MB/10工作表/展开前后150000单元格，坏文件中文400/异常中文500；无写库或模板注册/文件生成。预览单元格裁切长文本，避免覆盖相邻列；浏览器与Excel分页差异及不支持元素的边界沿用007说明。
- 修前基线：销售16项、库存82项、UI相关74项分别通过，三组存在交集，不相加充作总数。新增销售44项、库存29项、工具栏18项共91项；最终受影响及相邻20模块300 passed（256项既有SQLAlchemy告警）。覆盖六真实销售页面渲染、客户/状态/项目/物料过滤、分页外全明细、仓库隔离及历史NULL归属、模板样式/坏模板/价格门控/大小限制、只读SQL及文件快照、异步加载/重试/字段设置兼容。未放宽既有断言。
- 回归锁：七模板备份回退旧版本时新工具栏契约真实失败，逐文件SHA恢复；销售撤销新路由并还原旧导出后预览404、空客户筛选仍泄漏SO-A两个锁均失败，finally字节恢复。库存新路由回退后关键锁失败，坏XLSX与5001行新下载防护修前失败、修后通过。证据C:/wms_backups/report_toolbar_20261026/及外置Temp备份；不使用stash。
- 隔离核验：真实浏览器切换库存两套模板并打开纵向预览，3条物料库存10/20/30与页面一致；销售实际切换物料汇总纵向模板并预览3行/数量6/金额111，顶栏字段设置实际定位物料汇总表；整段JS覆盖四范围。最终预览样式收尾后复测预览及台账106 passed；A1–A14、全量A11、JS非GET请求检查零违规（存量42模板warn保留），verify_wms_bugs通过。隔离HTTP冒烟119/119，保留页面/表单/导出断言，排除两项未授权账号密码写入；最初内存库导致backup页不支持文件备份，改用外置隔离文件库后119项全部通过，未改生产代码迁就。页面测试及冒烟仅外置隔离库，未对生产执行业务或账号操作。
- 开工门禁：远端main/HEAD/origin均28c05b54bff12cfa8af1705ddc726898515edcf7；WMS CI40300239353、AI40300239255 completed/success精确匹配；Android40233861271在6943bb725a9ca5988fbd868daf519f89ec224e46 success，祖先/完整对象/Android路径无差异证明通过。钩子已启用；007生产发布完成后才开始本批写入。其它任务未跟踪文件保留，不纳入提交。
- 首次推送与CI修复：aeaa190e41cb0d8e3af1581e9df0c167ea66dcf4 已真实push（28c05b54..aeaa190e main -> main）；AI40307512642通过，CI40307512578仅unit-tests-shard-2的既有test_filter_params_follow导出参数契约失败，其余分片/lint/smoke通过。修前该模块组合1 failed/67 passed/88 skipped。保持原断言，销售对账server生成export URL显式带仓库，统一JS按URL.searchParams合并查询，避免已有query时拼第二个问号或保留旧仓库。新增整段JS回归先红，物理回退JS时再次失败后SHA恢复；修后4个受影响及相邻模块174 passed/88 skipped。仅修当前失败，不写下批功能；受控连接器按远端当前parent/tree一次更新这4个准确代码/测试文件，台账证据随生产验收文档收尾，不以WMS_SKIP_CI_GATE跳过实际红灯，后续以新目标CI验收。
- 生效确认：2026-10-26 18:46:56（Asia/Shanghai），Codex自动核验。受控API修复返回3ce7644aa322bd44c607411ddd483c324a8ce751；反查parent=aeaa190e、完整tree=1b73e913e1714f9972f0e35d26f146e118c0686d及4文件集合完全一致，外置备份后安全fetch/fast-forward，HEAD/origin/main同SHA。未使用force/reset/stash；本机系统Git迁移期间wrapper暂报fork bomb，改用已安装的bundled Git完成同步，未改系统配置。WMS CI40308838906/AI40308838629 completed/success精确匹配，Android40233861271祖先/路径无差异证明通过。生产发布前在线备份及28c05b54回退包齐备，旧PID384核实后沿WMS-Warehouse重启，新PID9252/Session0唯一监听8080，任务结果0，启动SHA3ce7644及启动迁移禁用已核对；首次8秒探测尚未监听，后续就绪正常，未重复启动。97表摘要仅print_workstation心跳变化，quick_check=ok，本机/公网登录GET200且含CSRF；未执行生产业务/账号操作。生产需重启 WMS 服务生效，本次已完成。证据C:/wms_backups/report_toolbar_20261026/seven/deployment/effective.json。


### BUG-2026-10-26-009: 菜单仍展示重复业务列表入口

- 状态：已修复（菜单展示小改）；待本批验证、推送、CI与重启验收。
- 用户范围：用户明确“最快的方法就是把列表隐藏，不在菜单里显示”“让我看不到列表，就不会进入了，不用大动”。本批仅调整base菜单展示，保留菜单/子菜单结构、报表、开单及基础资料；不迁移业务页面，不改首页待办、原路由、数据与列表操作。
- 根因/危害：上一批只统一报表工具栏，base采购、销售、库存仍同时列出业务列表和报表，导致用户继续进入旧列表。
- 同类点已排查：复核007/008范围与活跃菜单、财务只读菜单、legacy隐藏菜单的相同旧查询链接；表单列的盘点/委外等入口承担现有开单功能，按用户保留表单要求保留，基础资料维护也保留。
- 修复：隐藏采购申请/订单/入库及销售订单/出库的列表入口；库存旧入库/领料/其他入出库列表不再出现在菜单，继续显示已有报表；菜单栏标题统一“报表”，财务和legacy同类入口统一已有报表。生产需重启 WMS 服务生效。
- 开工门禁：上批3ce7644aa322bd44c607411ddd483c324a8ce751的WMS CI40308838906/AI40308838629 success，Android40233861271祖先/完整对象/Android路径无变化证明通过；上批生产新PID9252已验收后开始本批写入。仅本批文件及008交付证据文档收尾，原三份他人未跟踪文件保留。
- 验证：修改前相关既有78 passed；新菜单锁在旧模板下失败（admin暴露13个旧查询链接，含legacy），修改后15项覆盖9角色及库位/价格开关，合并相邻模块93 passed，台账契约10 passed。物理回退base后新锁再次失败，finally字节恢复（SHA256 ca0c3bbec8670b9e9b4b3d16b3746aba6cad338339773a258ab937cf44e366ac）。隔离HTTP冒烟119/119，实际浏览器展开采购、销售、库存菜单，确认旧列表入口不再展示，表单/报表保留。只用外置QA数据库，未做生产业务/账号操作；证据C:/wms_backups/report_toolbar_20261026/menu/。
- 生效确认：2026-10-27 08:27，经交接由下拉框批次主代理在干净且CI全绿的375bbd38基线上完成原WMS-Warehouse重启；PID14828/Session0、8080唯一监听、计划任务结果0、启动SHA375bbd3，本机/公网登录GET200，核心业务表摘要未变，在线备份及旧码回退包齐备。证据C:/wms_backups/dropdowns_system_20261026/menu-handoff-deployment-20261027/effective.json。生产需重启 WMS 服务生效，本次已完成；未混入未提交下拉框候选。

### BUG-2026-10-26-010: AI 查询参数与调度上下文校验缺口（issue #6）

- 状态：隔离副本验证通过，已按授权集成 C:\wms；集成后158项回归、3项工具验证、严格台账、编码及规则检查全部通过。提交前本地验证完成，按用户授权准备提交推送；未部署。
- 关联：AI-R01-F01；https://github.com/SIX2090/wms/issues/6 。基线 aeaa190e41cb0d8e3af1581e9df0c167ea66dcf4。
- 根因/危害：查询工具以 isinstance 接受 bool 数量，缺少范围和额外字段约束；orchestrator 校验 context or {} 却执行原对象，空列表、false、0、空串绕过对象校验。JSON 解码器接受 NaN/Infinity，也可绕过普通数值比较。
- 同类点已排查：现有 AI-R01 Registry、统一 schemas、查询 prompt、LLM 调度、查询记忆及角色门控；没有其他 AI_QUERY_TOOLS params/required 元数据消费者。不重建 Registry，不改权限、人工确认和库存业务。
- 修复：三个查询工具声明 input_schema 并复用现有校验器，prompt 展示同一契约；封闭调用对象及 params 字段，数量复用 NON_NEGATIVE_QUANTITY（0..1000000000），保留可选 null/空文本；拒绝非有限数，保留零数量条件。orchestrator 仅将 None 归一为 {}，校验和执行同一对象，拒绝非字符串工具名。
- 验证：原相关50项及3脚本通过；新增测试首次23 failed/31 passed；最终8模块158 passed（含59项新增用例）。临时回退四个源码后25 failed/34 passed，finally逐字节恢复后158 passed；AI core 59/59脚本通过；普通规则0违规、全量棘轮通过。任务目录 issue6-*.log 和 issue6_verify.py 保存证据。
- 边界：内存库/独立临时库和LLM、handler替身，无在线数据修改、软件安装；用户本次覆盖CI全绿前置条件。全站测试及新补丁远端CI未运行，未修无关CI或修改AGENTS。
- 生效确认：2026-10-26，Codex在任务 wms-issue6 隔离副本验证；已集成C:\wms，提交前未重启服务；服务生效尚未验证。集成后158项测试、3项工具验证、严格台账、编码、普通规则及全量棘轮均通过；日志在任务目录issue6-shared-*.log。

- 集成记录：2026-10-26，在共享HEAD 9529ed9058bb1efa1a451b713b7c327fce567c14 上仅应用本次差异。原009编号已被菜单修复占用，本条改为010；保留所有既有改动和索引内容。共享项目集成不等于服务重启或生产生效。

- 提交前复核：2026-10-26，用户明确授权提交推送；main基线9529ed9058bb1efa1a451b713b7c327fce567c14，本次仅8文件，无混合暂存改动。源码与158项集成后测试通过的版本逐字节一致。远端提交和CI结果以本次交付报告为准，未重启或部署。

- 提交后CI复核：67ded43044b177406fa8b605244c21a0dd748ba5 的AI core通过，但verify_wms_bugs中AI-FOUNDATION-MODULES-001仍硬编码旧的context or {}，导致静态回归失败。本次同步该同源回归锁：必须仅规范化None、校验同一context、传入handler，且三者顺序正确；未删除校验项或恢复有缺陷的实现。补跑完整BUG回归及相关行为测试后再推送修正。

- CI补充验证：新BUG已加入POST_SPLIT_BUGS，保持拆分前历史基线不变。完整verify_wms_bugs回归通过；参数及工具调用测试75通过；台账拆分及门禁测试18通过。

### BUG-2026-10-26-006: 全系统独立下拉候选静默截断、窗口溢出及采购选料编码未回填

- 状态：已修复候选，待整批回归、提交推送、目标 CI 和生产生效验收；本条四类问题均未提前计为已交付。
- 根因/危害：多个页面把本地候选的20/60/80条展示默认值当成全集；入/出库详情再次把接口已返回的100条裁成20条；合同和员工搜索在SQL层静默limit(50)；部分独立下拉未使用已有窗口边界助手，公共合同菜单fixed坐标叠加scrollY；采购订单显式选中后只回填名称规格而未写实际物料编码，同名物料可能仍以原搜索词解析。
- 修复：本地已加载候选保持完整；远程100条检索保留限额并给出细化搜索提示，已有exact-code与陈旧响应守卫不变；合同/员工返回全部匹配及total并保留现有data结构和登录要求；复用WMS.positionDropdown收敛窗口、排除菜单内部滚动；采购订单显式选择写实际编码后再填规格并定位数量。生产需重启 WMS 服务生效。
- 同类点已排查：关联BUG-2026-10-26-004、BUG-2026-10-25-024、BUG-2026-10-24-005及10-24候选定位历史；静态扫描132个未停用模板、24个业务JS，区分原生select、最近使用条目与真实搜索截断；公共data-ks既有分页修复保留。覆盖15模板、3个JS、2个GET路由；不涉及库存算法、单据提交/完成、打印、账号或密码。新增工具栏批次完成后复核新文件消费点。
- AI子修复：AI-UX-DROPDOWN-FIX-001只调整既有库位推荐和识别确认的候选展示；请求、结果、人工确认、权限、工具、模型、开关、迁移不变；未包含待修BUG-2026-10-25-027异步推荐问题。
- 已有验证：稳定修前基线16模块413 passed；31项实际页面JS运行时通过。物理备份并回退20个产品文件后27个新增JS场景失败、4个正对照通过；pytest为10 failed/2 passed，失败均为真实断言，finally逐字节恢复。扩大相邻回归首次3 failed/773 passed，定位为旧AI文字安全夹具缺少新增WMS定位依赖；只补夹具并增加定位次数断言，原安全/选择/重绘断言保留，修后776 passed。
- 浏览器与隔离冒烟：完整main源码存档叠加精确候选，独立端口/数据库/静态目录；265条同名物料全部可达，滚轮后scrollTop1440、拖动至末尾8876且菜单保持打开，选择WIRE-265后编码/规格准确并聚焦数量；供应商、合同、员工125条末尾候选均可选，合同与工程字段一起回填，菜单在窗口内。119/119页面、表单和导出冒烟通过；保留原脚本检查，排除两项未授权密码写入，只用已知QA凭据。演示实例已关闭。证据C:/wms_backups/dropdowns_system_20261026/。
- 开工门禁：main28c05b54bff12cfa8af1705ddc726898515edcf7；WMS CI40300239353、AI40300239255 completed/success；Android40233861271在6943bb725a9ca5988fbd868daf519f89ec224e46成功，祖先/对象/路径复用证明完整。按用户先工具栏后本批顺序，候选保存在外部，未跨批混合提交或发布；最终接入新基线和门禁另行补记。
- 生效确认：待确认；本批尚未提交、推送或发布。最终模块回归、完整AI、质量、CI及生产版本验证结果将在验收后回填。

- 扩展消费点：另12模块初跑51 failed/377 passed，集中于合同/工程/员工生命周期和死表头清理两处旧夹具未提供新增定位依赖；补齐助手并增加可见菜单/员工定位断言，原HTTP、乱序、失焦、缓存、选择、键盘及隐藏断言全部保留，修后428 passed。两组35模块共1204 passed。工具栏新基线aeaa190e上的旧码22模块764 passed、源码及守卫稳定。

- 最终接入与本地验收（2026-10-27）：原工具栏/菜单交接后，参数校验批次及同源CI契约修复已提交至375bbd388f0f806308602ac3af248d75d1044106；最新WMS CI40415362640、AI40415383992、Android40415357438（重跑第2次）均completed/success，精确匹配目标。前次Android单测数据库锁失败已保留记录，不用旧绿代替。稳定新基线34模块1192 passed，app及该34模块从67ded430至375bbd38无差异；9529并发写入时的1192结果不计稳定基线。最终接入后35模块1204 passed、31实际JS场景通过，源码/守卫稳定且无凭据文件访问；规则/裸请求/编码/严格AI台账/文档34项/完整BUG回归/diff七项全部通过。新基线完整隔离副本的HTTP页面、表单及导出冒烟119/119，真实浏览器再次确认265候选全部加载，末项WIRE-265编码及规格正确回填并聚焦数量；仅外置QA数据库，实例已关闭。待本批实际push、目标CI及生产生效。
