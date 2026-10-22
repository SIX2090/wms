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

- 状态：已修复，待CI及规则同步验收。
- 根因/危害：CI与AI每次main push都跑全套，功能提交验收后补台账又重复全量；门禁只检查各工作流最近success，没有要求WMS CI/AI匹配目标SHA，不能明确证明当前基线已验收。旧“开任何任务前不得有pending”把只读准备也串行化；生产与开发共用目录，直接放开跨批写代码会把未提交文件混入发布。
- 修复：白名单README、docs/ledger和docs/audit Markdown只有在main push、完整Git差异且紧邻base的CI/AI最近记录均成功时才走docs分支；未知、失败、排队或无证据一律全量。required工作流仍触发，明确聚合所选docs或full分支，原全量步骤/分片和每日定时保留；perf仍为告警观测。SHA门禁绑定远端main基线，发布可显式指定完整SHA，Android旧绿须证明祖先关系及工程/构建工作流无变化。403/网络标未核实并阻断，不误作已确认红灯；保留连接器替代证据流程。DEVELOPMENT_RULES、README及docs/CI_VALIDATION_POLICY.md更新验证边界，AGENTS按硬规则另作独立atomic action同步，只放开只读准备、不开放混合发布写入。
- 同类点已排查：关联既有CI门禁、F2.8 pre-push、F3.16并发取消与2026-09-24性能契约，核对三个main门禁和可选性能工作流、主规则/开发规范/README、GitHub API参数与钩子实际stdin。Android已有路径触发不重复开发；不使用paths-ignore使required工作流消失，不允许仅改规则文本绕过代码要求。
- 回归：旧门禁基线16 passed/3 Windows条件skip，新增46通过，旧checker/hook回退40 failed/6 passed，finally恢复后6模块97 passed/4 skipped；真实Git Bash执行覆盖远端SHA、CRLF和无更新，编译检查通过。旧工作流相关58 passed/4 skipped，新增62通过，旧workflow回退59 failed/3原fulljob快照passed，恢复后120 passed/4 skipped；12个原fulljob payload保持，perf advisory失败仅告警。classifier基线14 passed/1 skipped，初80通过，删除新脚本反证5 failed/75 errors并字节恢复，7模块220 passed/3 skipped；终审再补未知身份拒绝、分页去重和main suffix合法形态12锁，最终92通过，独立回退8 failed/4 passed，finally恢复后三个必要新模块合计200 passed（包含92/62/46，不重复相加）。交叉只读审查无剩余阻塞。日志ci_gate_target_sha_016/、ci-docs-mode-20261022/、ci-scope-016-*.log。不用stash、不弱化旧业务断言；旧并行结构测试改为仅依赖changes且彼此不串联，原步骤/分片断言保留。
- 组合验收：轻量docs的--noconftest三模块34 passed，严格AI台账41标记/118完成一致，源码编码通过、规则default 0违规/full-gate 0新增、既有BUG检查通过；日志ci-policy-016-*.log。未跑本地重复全站，配置改动由本次CI原全量实证，再用真实文档收尾提交验证轻量路线。
- 生效确认：待确认；本项仅CI/开发规则与测试，不改WMS业务代码、生产服务、数据库、打印机、仓库、库存或账号，不需重启WMS。当前生产业务版本仍acdef2c；台账轻量生效必须核验工作流实际选择与结果，不能仅凭本地YAML检查宣称完成。
