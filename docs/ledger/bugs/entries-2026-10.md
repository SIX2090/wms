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

## BUG-2026-10-06-003：AI v1 低库存报告与 v2 工具口径分叉（总账列 + max_stock 补货算法）
- **现象**（深度检测遗留问题复核，用户拍板立即修复）：AI 对话关键词入口（"补货建议/低库存报告"/intent=analysis_low_stock，app.py:10064 `_ai_analysis_low_stock_report()`）与 v2 工具 `/api/ai/v2/tools/inventory/low-stock` 同数据不同结果：① v1 读 `Material.stock` 总账列且无 stock-truth 豁免（A11 违规：低库存判定属校验语境）；② v1 建议补货量按 `max_stock - stock` 计算，v2 按 safety_stock 口径，同一物料两入口给出不同补货数字；③ v1 排序只按 min_stock 差值，无两级告警概念。
- **根因**：v1 是 BUG-2026-10-05-003/10-06-002 两轮修复都漏掉的平行入口——同类口径问题的"同语义入口全量排查"没覆盖到 app.py 内嵌的 v1 版本（教训同 10-06-001：dashboard 只有一条代码路径却漏改）。
- **修复**（app.py `_ai_analysis_low_stock_report()` 重写）：直接转调 v2 工具 `low_stock_report()` 渲染 markdown（R6 防口径分叉：单一实现源）——全仓汇总口径（Σ②库位账）、两级告警（low/danger 列）、补货量按 safety_stock 口径，开关关闭保持"未启用"提示。表头新增"预警级别"列。
- **验证**：3 场景回归测试全绿——B1 v1/v2 同数据同结果（danger 档 M001 两边都报、库存数一致、M002 normal 两边都不报）/ B2 开关关闭不报 / B3 **两仓脏数据场景**（总账 stock=999 但 B仓流水仅 5 → 全仓汇总 5≤min_stock 应报 low；旧实现读总账列会误判 normal 漏报——本用例在修复前确实红）。存量防破坏：10-05-003/004 + 10-06-001/002 共 20 项全绿。
- **回归锁**：`tests/test_bug_2026_10_06_003_v1_low_stock_report_scope.py`（3 用例）。
- **推送与 CI**：待 push（atomic action：`fix(ai): BUG-2026-10-06-003 v1 低库存报告转调 v2 工具统一口径`）。

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
- 验证：旧相关基线21通过，新锁5 failed / 7 passed；回退三路由后5 failed / 7 passed；恢复后专项及相邻108通过，包括前3项修复、PC/扫码盘点、调整、多仓及库存文档引用；未放宽断言。
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
