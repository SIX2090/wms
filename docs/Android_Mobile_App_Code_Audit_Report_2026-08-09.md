# Android Mobile App 全面代码审计报告

> 审计目标：`/workspace/app/android-native-wms/`（Kotlin + Jetpack Compose）
> 审计日期：2026-08-09
> 审计范围：app 模块（业务代码）全部 Kotlin/XML 源文件 + AndroidManifest + 资源文件
> 审计基准：`AGENTS.md` 仓库规则 + `DEVELOPMENT_RULES.md` A1–A10 + 历史 BUG 类型
> 审计方法：源码静态扫描（无动态运行/真机截图）

## 0. 审计结论摘要

| 维度 | 评级 | 说明 |
|---|---|---|
| 安全（FileProvider / 权限 / 网络） | 良好 | FileProvider 配置正确、权限运行时申请 + 设置引导齐全；网络白名单策略完善 |
| 业务逻辑 BUG | 良好 | 近期已修复 BUG-2026-08-09-001/002/003；本次未发现新增紧急 BUG |
| 代码质量（重复/可读性/资源泄露） | 中等 | 大量 UI 屏幕代码重复（拍照/识别/盘点三屏 90% 一致），扫描线/仓库加载等逻辑存在重复 |
| 资源泄露 | 良好 | CameraX + ML Kit 已通过 `DisposableEffect(Unit){ onDispose {...} }` 释放 |

**总体评级：生产可用，无 P0/P1 安全或 BUG 风险；建议在下一个迭代周期对 UI 层做"模板化/可复用组件"重构以消减 ~40% 重复代码。**

> 复核说明：本报告已与当前 `main` 分支代码对齐。报告初稿中的 P1-A（盘点仓库必填缺失）、P1-C（`extracted` 自引用）两项在后来的代码演进中已被解决，现更新为「已解决」状态。

---

## 1. 审计范围与目录结构

```
app/android-native-wms/app/src/main/
├── AndroidManifest.xml
├── java/com/factory/wms/
│   ├── MainActivity.kt
│   ├── WmsApplication.kt
│   ├── data/
│   │   ├── api/        AuthEventBus, RetrofitClient, WmsApiService
│   │   ├── local/      AppDatabase, DatabaseMigrations, MaterialDao, MaterialEntity, OperationLogDao, OperationLogEntity
│   │   ├── model/      ApiEnvelope, DashboardModels, InboundDraftModels, LoginData, LoginRequest, MaterialDto, OpeningStockModels, ScanRequests, SubmitResult
│   │   └── repository/ WmsRepository
│   ├── ui/
│   │   ├── components/ ScannerDialog, VoiceAssistant, WarehousePicker
│   │   ├── navigation/ NavGraph, Screen
│   │   ├── screens/    AiScreens, HomeScreen, LoginScreen, OpeningStockScreen, ProfileScreen, ScanScreenBase, ScanScreens
│   │   ├── theme/      Color, Theme, Type
│   │   └── viewmodel/  ai, auth, home, opening, scan, voice
│   └── util/           FormatUtils
└── res/
    ├── xml/            file_paths, network_security_config
    └── (其他资源)
```

---

## 2. 安全审计

### 2.1 FileProvider（拍照保存）

**结论：配置正确，最小权限原则已遵守。**

`AndroidManifest.xml` L35–L43：

```xml
<provider
    android:name="androidx.core.content.FileProvider"
    android:authorities="${applicationId}.fileprovider"
    android:exported="false"
    android:grantUriPermissions="true">
    <meta-data
        android:name="android.support.FILE_PROVIDER_PATHS"
        android:resource="@xml/file_paths" />
</provider>
```

`res/xml/file_paths.xml` 仅暴露 `cacheDir/camera/` 子目录：

```xml
<paths xmlns:android="http://schemas.android.com/apk/res/android">
    <cache-path name="camera_cache" path="camera/" />
</paths>
```

**安全要点确认**：
- ✅ `android:exported="false"`：未对第三方应用暴露入口
- ✅ `android:grantUriPermissions="true"`：仅在拍照期间临时授权，关闭即失效
- ✅ `path="camera/"`：限定子目录，避免把整个 cacheDir 暴露
- ✅ `cacheDir` 而非 `filesDir` / `getExternalFilesDir`：避免污染用户可见存储

**潜在风险（低）**：
- 拍照后写入的临时文件 `cacheDir/camera/{prefix}_{ts}.jpg` 没有主动清理逻辑，长期使用会累积占用空间。建议在 `WmsApplication.onCreate()` 注册 `WorkManager` 周期清理 >24h 旧文件。
- 状态：可接受改进项，不构成 BUG。

### 2.2 权限申请

**结论：所有危险权限均有运行时申请 + 引导逻辑，无 SecurityException 风险。**

| 权限 | 申请位置 | 处理 |
|---|---|---|
| `CAMERA` | `rememberCameraLauncherWithPermission()` (`AiScreens.kt` L1675–1724) | 检查 → `RequestPermission` → 拒绝时 Snackbar + 跳设置页 |
| `CAMERA`（扫码） | `ScannerDialog.kt` L81–97 | 拒绝时 Toast + 关闭对话框 |
| `RECORD_AUDIO` | `VoiceAssistant.kt` L70–80 | 拒绝时 Snackbar 提示 |
| `INTERNET` | Manifest 声明即可 | — |

**安全要点确认**：
- ✅ 所有拍照入口（3 个屏幕 × 1 处 = 3 处）已统一走 `rememberCameraLauncherWithPermission()` helper，杜绝裸 `cameraLauncher.launch()` 漏权限检查
- ✅ 权限拒绝有可发现性引导（"去设置"按钮 + `Settings.ACTION_APPLICATION_DETAILS_SETTINGS`），避免"拒绝一次后无法再开相机"的用户体验死循环
- ✅ 旧 `BUG-2026-08-09-003`（未授权直接 `launch` 引发 SecurityException 闪退）已修复并有 7 项回归测试

### 2.3 网络安全

**结论：网络白名单 + debug 分离策略合理，无明文 HTTP 风险。**

`res/xml/network_security_config.xml`：

| 配置 | 值 | 含义 |
|---|---|---|
| `base-config cleartextTrafficPermitted` | `false` | release 构建默认禁明文 |
| 域名白名单 | `127.0.0.1` / `localhost` / `10.0.2.2` | 仅放行本机/模拟器 |
| `debug-overrides` | `cleartextTrafficPermitted="true"` | debug 构建放开，便于局域网联调 |
| 信任锚 | `system` | 仅系统证书，不信任用户/中间人 |

**安全要点确认**：
- ✅ `RetrofitClient` 超时配置（15/30/30 秒）合理，避免慢连接占用资源
- ✅ `BuildConfig.DEBUG` 控制的日志拦截器（`L40`）在 release 自动关闭，**不打印 header**（`L37` 注释明确），避免 Authorization token 泄漏到 logcat
- ✅ `authInterceptor` 401 处理在 `/api/login` 路径短路（L28–32），避免登录失败被误判为令牌失效

**潜在风险（低）**：
- `ApiEnvelope.displayMessage()` 优先取后端 `message`/`msg` 字段并直接 `Log.w` / `Exception` 抛出。如果后端被攻击者控制，可能注入回前端显示。建议在 `displayMessage()` 入口增加长度截断（如 ≤200 字符）+ HTML 标签过滤。
- 状态：建议 P2 改进，不构成紧急 BUG。

### 2.4 Token / 凭据存储

**结论：使用 AndroidX Security 加密存储，无明文落盘风险。**

`WmsRepository.kt` L36–47：

```kotlin
private val encryptedPrefs by lazy {
    val masterKey = MasterKey.Builder(context)
        .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
        .build()
    EncryptedSharedPreferences.create(
        context,
        "wms_secure_prefs",
        masterKey,
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
    )
}
```

- ✅ `auth_token` 走 AES-256-GCM 加密 + AES-256-SIV 键派生
- ✅ 非敏感的 `base_url` / `username` / `role` 走 DataStore（性能更好，职责分离）
- ✅ 登出时同步清空加密 SharedPreferences + DataStore + RetrofitClient 内存（`logout()` L81–87）

### 2.5 反 XSS / 内容安全

- ✅ `WmsApiService` 使用 `GsonConverterFactory` 反序列化 JSON，未在客户端做 HTML 拼接
- ✅ 后端响应经过 `ApiEnvelope` 信封包裹，类型安全
- ✅ 拍照保存的本地图片仅供 `AsyncImage` 加载，无 WebView/HTML 注入面

---

## 3. 业务逻辑 BUG 审计（参考历史 BUG 类型）

> 参照 `WMS_BUG_BASELINE.md` 历史模式逐项排查。本次审计**未发现新增 P0/P1 BUG**。

### 3.1 参考 BUG-2026-08-09-001 模式（ML Kit 回调空结果）

**检查项**：`barcodeScanner.process(image).addOnSuccessListener { barcodes -> ... }` 中是否在 `barcodes` 为空时错误地置位"已识别"标志。

- `ScannerDialog.kt` L188–194：`for (barcode in barcodes) { val rawValue = barcode.rawValue; if (!rawValue.isNullOrEmpty() && scannedFlag.compareAndSet(false, true)) { ... } }` ✅ 仅在 `rawValue` 非空时置位
- 回归测试：`verify_bug_2026_08_09_001_scanner_dialog_flag.py` T1–T4 全部存在

### 3.2 参考 BUG-2026-08-09-002 模式（CameraX 1.3+ 互斥 API）

**检查项**：`ImageAnalysis.Builder()` 是否同时调用 `setTargetAspectRatio` 和 `setTargetResolution`（互斥，抛 IllegalArgumentException）。

- `ScannerDialog.kt` L163–167：仅使用 `ResolutionSelector` + `AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY` + `ResolutionStrategy.HIGHEST_AVAILABLE_STRATEGY` ✅
- 已确认无 `setTargetAspectRatio` 或 `setTargetResolution` 残留调用

### 3.3 参考 BUG-2026-08-09-003 模式（拍照权限+MediaStore NPE）

**检查项**：
- ① 所有 `cameraLauncher.launch(...)` 调用是否经权限 helper
- ② 是否有 `MediaStore.Images.Media.insertImage(...)` 残留
- ③ 是否有 `Uri.parse(null)` 风险
- ④ 是否有 `Uri.parse(path)` 残留

| 文件 | `cameraLauncher.launch` 裸调用 | `insertImage` | `Uri.parse` |
|---|---|---|---|
| `AiScreens.kt` | 0（全部经 helper） | 0 | 0 |
| `ScannerDialog.kt` | N/A（CameraX） | 0 | 0 |

- 回归测试：`verify_bug_2026_08_09_003_takepicture_permission_and_path.py` T1–T7 全部存在

### 3.4 仓库必填规则（AGENTS.md 强约束）

**检查项**：所有出入库单据/盘点/期初的提交路径是否校验仓库必填。

| 提交路径 | 文件 | 必填校验 | 备注 |
|---|---|---|---|
| `submitInbound` | `ScanViewModel.kt` L133–168 | ✅ L137–140 `if (warehouse == null) error = "请选择仓库"` | 同时校验 `lines.isEmpty` |
| `submitOutbound` | `ScanViewModel.kt` L170–206 | ✅ L174–177 同上 | — |
| `submitStocktake` | `ScanViewModel.kt` L208–242 | ✅ L212–215 `if (warehouse == null) { error = "请选择仓库"; return }` | 同时校验 `lines.isEmpty` |
| `submitOpeningStock` | `OpeningStockViewModel.kt` L110–150 | ✅ L112–115 | 同时校验 `lines.isEmpty` |
| `submitInboundDraft` (OCR) | `AiViewModel.kt` L114–178 | ✅ L153–156 | — |

> 审计复核（基于当前 main 代码）：三个提交路径（`submitInbound`/`submitOutbound`/`submitStocktake`）均已补仓库必填校验，与 AGENTS.md"仓库必填"规则一致，**无 P1-A 风险**。

### 3.5 401 单次触发（参考 BUG-2026-08-09 历史教训）

**检查项**：401 事件是否会被并发请求多次触发，导致重复跳转登录页。

- ✅ `AuthEventBus.unauthorizedSignaled: AtomicBoolean`（L17）`compareAndSet(false, true)` 保证单次触发
- ✅ `AuthViewModel.init` 在 `AuthEventBus.unauthorizedEvents.collect` 中只调 `logout()`，不重复导航
- ✅ 登录成功时 `AuthEventBus.reset()`（L60）复位门闩

### 3.6 数据库迁移

**检查项**：`AppDatabase` 是否禁用破坏性迁移。

- ✅ `AppDatabase.kt` L29–32：显式禁用 `fallbackToDestructiveMigration`，仅 `addMigrations(*DatabaseMigrations.ALL)`
- ✅ `DatabaseMigrations.kt` 已记录约束：schema 变更必须显式登记
- 状态：策略正确，**未发现迁移丢数据风险**

### 3.7 幂等键

**检查项**：所有写操作是否携带 `X-Idempotency-Key` 防止重复提交。

| 接口 | 幂等键 | 备注 |
|---|---|---|
| `/api/inbound` | ✅ `newRequestId()` UUID | `WmsRepository.submitInbound` L156 |
| `/api/outbound` | ✅ | L182 |
| `/api/stocktake` | ✅ | L207 |
| `/api/opening_stock` | ✅ | L270 |
| `/api/mobile/inbound_draft` | ✅ | L298 |
| `/api/ai/document_ocr` | ❌ 无幂等键 | 上传图片成本高，重试浪费带宽 |
| `/mobile/api/recognize_material` | ❌ 无幂等键 | 同上 |

- **潜在风险（低）**：识别类接口无幂等键，弱网下用户多次点击"开始识别"会发起多次请求。**不构成数据 BUG**（后端通常按内容去重），但浪费带宽/算力。
- 建议：在 `multipart` 头加入 `X-Idempotency-Key: <UUID>`，与现有写操作保持一致。

### 3.8 UI 状态机（屏 → 屏切换）

**检查项**：屏内 Composable 状态是否在 `popBackStack` 后正确清理。

- ✅ `AiScreens.kt` 中 `selectedImageUri`、`countQty` 用 `remember { mutableStateOf(...) }`，随 Composable 出栈自动丢弃
- ✅ `ScannerDialog` 通过 `DisposableEffect(Unit) { onDispose { cameraProvider?.unbindAll(); analysisExecutor.shutdown(); barcodeScanner.close() } }`（L100–109）释放 CameraX + ML Kit
- ✅ `VoiceCommandViewModel.onCleared()` 调 `speechRecognizer?.destroy()` 释放 `SpeechRecognizer`（L167–171）

**潜在风险（低）**：
- `WmsRepository.encryptedPrefs` 用 `by lazy` 延迟创建，但**不会在用户登出时主动清除加密文件**。`logout()` 只清空键值，物理文件仍残留加密 token（虽然无法解出明文）。如果攻击者拿到设备 root + keystore，可能存在风险。
- 建议：登出时调 `encryptedPrefs.edit().clear().commit()`（同步提交）确保 token 在闪存上被覆写。
- 状态：Android 设备级风险，App 端可做加固措施。

---

## 4. 代码质量审计

### 4.1 重复代码（最高优先级改进项）

#### 4.1.1 三个"拍照/选择图片"屏 90% 重复

`AiScreens.kt` 中：
- `DocumentOcrScreen`（L57–714，658 行）
- `ObjectRecognizeScreen`（L717–1124，408 行）
- `StocktakeRecognizeScreen`（L1127–1567，441 行）

三屏重复内容（估算）：

| 重复模块 | 行数（合计） | 重复度 |
|---|---|---|
| `imagePicker` + `launchCamera` 声明 | ~12 × 3 = 36 | 100% |
| 空状态卡片（`Icon` + 标题 + 描述） | ~50 × 3 = 150 | 90% |
| 已选图片预览 + 清除按钮 | ~40 × 3 = 120 | 95% |
| "开始识别" / 识别中 loading 按钮 | ~30 × 3 = 90 | 90% |
| "拍照 / 选择图片" 双按钮 Row | ~35 × 3 = 105 | 90% |
| `LaunchedEffect(uiState.error)` 错误 snackbar | ~5 × 3 = 15 | 100% |
| TopAppBar + 返回按钮 | ~25 × 3 = 75 | 95% |
| `OcrResultRow` 私有函数 | 共用 ✅ | — |

**重复总量估算：~590 行**（约 1500 行业务代码中占 40%）。

**改进建议（中等优先级）**：
抽离共用 Composable `ImageCaptureStage`：

```kotlin
@Composable
fun ImageCaptureStage(
    title: String,
    subtitle: String,
    accentColor: Color,
    emptyIcon: ImageVector,
    emptyHint: String,
    buttonLabel: String,
    onImageReady: (Uri) -> Unit,
    onError: (String) -> Unit
) { /* 通用 UI */ }
```

#### 4.1.2 `addScanLine` / `addLine` 业务逻辑重复

- `ScanViewModel.addScanLine`（L52–65）合并相同 material_code 行并累加数量
- `OpeningStockViewModel.addLine`（L80–96）合并相同 materialCode 行但**覆盖**数量

**差异点**：扫码入库是累加，期初库存是覆盖（一个物料只对应一个期初数量）。

**改进建议（低优先级）**：
抽离 `MutableList<T>.mergeByKey(key, mergeStrategy: (T, T) -> T)` 工具函数，统一两处实现。

#### 4.1.3 `loadWarehouses` 在 3 个 ViewModel 中重复

- `ScanViewModel.loadWarehouses`（L82–103）
- `AiViewModel.loadWarehouses`（L91–108）
- `OpeningStockViewModel.loadWarehouses`（L49–70）

三处实现几乎一致（仓库列表 + 默认选中 + loading 状态），仅 UIState 结构不同。

**改进建议（中等优先级）**：
抽离 `BaseWarehouseAwareViewModel`，通过协程 + `Flow<List<WarehouseDto>>` 暴露仓库数据。

### 4.2 可读性

#### 4.2.1 顶级 `@Composable` 函数过长

- `DocumentOcrScreen` 一个函数 658 行（含嵌套 UI）
- 建议：拆分为 `OcrResultsSection`、`InboundDraftFormSection`、`DraftResultSection` 三个私有 Composable，主屏只负责编排

#### 4.2.2 `match_count` 字段命名混合 snake_case / camelCase

`WmsApiService.kt` L102–133：

```kotlin
data class OcrItem(
    val code: String?,    // 已是 camelCase
    val name: String?,
    val spec: String?,
    val quantity: Double?,
    val price: Double?,
    val matched: Boolean?,
    val unit: String?
)

data class DocumentOcrResult(
    ...
    val match_count: Int?,   // snake_case ← 不一致
    ...
)
```

`OcrItem` 内部字段已统一为 camelCase；但 `DocumentOcrResult.match_count` 与 `RecognizeMaterialResult.match_count`（L139）仍为 snake_case。Kotlin 习惯用 camelCase（后端反序列化时 `@SerializedName` 桥接）。建议统一为 `matchCount`，并加 `@SerializedName("match_count")`。

#### 4.2.3 `DocumentOcrResult.extracted` 已改为专用类型（已解决）

`WmsApiService.kt` L112–133：

```kotlin
data class DocumentOcrResult(
    ...
    val extracted: ExtractedDocument?   // 专用类型，非自引用 ✅
)

data class ExtractedDocument(
    @SerializedName("document_type") val documentType: String?,
    val supplier: String?,
    @SerializedName("order_no") val orderNo: String?,
    @SerializedName("purchase_order_no") val purchaseOrderNo: String?,
    val date: String?,
    val items: List<OcrItem>?,
    val remarks: String?
)
```

**结论（已修复）**：`extracted` 字段已从自引用 `DocumentOcrResult?` 重构为专用 `ExtractedDocument?`，不再存在 Gson 递归反序列化的栈溢出风险。`RecognizeMaterialResult.extracted` 同样使用专用 `ExtractedMaterial?`（L142–149）。

### 4.3 资源泄露

#### 4.3.1 CameraX + ML Kit 释放（已修复）

- ✅ `ScannerDialog` `DisposableEffect` 释放三件套
- 回归测试覆盖

#### 4.3.2 `Bitmap` 临时文件累积

- 拍照临时文件路径：`cacheDir/camera/{prefix}_{ts}.jpg`
- 多次拍照不会自动清理

**改进建议（低优先级）**：
- 方案 A：在 `WmsApplication` 注册 `WorkManager` 周期清理 >24h 文件
- 方案 B：每次启动时清空 `cacheDir/camera/` 目录
- 方案 C：在 `saveBitmapToCacheAndGetUri` 中先清旧文件再写新文件

#### 4.3.3 `Bitmap.recycle()`

- `uriToMultipart()` 解码的 bitmap 在 `withContext(Dispatchers.IO)` 内未显式 `recycle()`。Bitmap 内存由 GC 回收，但大图（>2MB）可能短暂占用堆。
- 状态：低风险，不构成 BUG。

### 4.4 错误处理

#### 4.4.1 `error` 字段消费后清空存在竞态

- 多个 `LaunchedEffect(uiState.error)` 监听 `uiState.error`，调用 `viewModel.clearError()`
- 如果 `error` 在 ViewModel 内部多次更新（如 `submitInbound` 先 `error = "..."` 又因异步 race 被覆盖为 `null`），可能出现"error 闪现 + 立即清空"导致 UI 抖动

**建议（低优先级）**：在 ViewModel 暴露"已消费 error"的 one-shot `SharedFlow<UiEvent>`，避免 StateFlow 抖动。

#### 4.4.2 `handleResponse<T>` `Unit as T` 强转

`WmsRepository.kt` L321–324：

```kotlin
if (data != null) {
    Result.success(data)
} else {
    @Suppress("UNCHECKED_CAST")
    Result.success(Unit as T)
}
```

**潜在风险（低）**：
如果后端在无 `data` 时返回 `null`（即 `{ "status": "success", "data": null }`），调用方会拿到 `Result.success(Unit)`，对非 Unit 类型的泛型调用 `.fold { it.xxx }` 会因 `Unit.xxx` 编译失败/运行期 NPE。

**建议**：在 WmsApiService 端声明 `suspend fun someEndpoint(): Response<ApiEnvelope<Unit>>` 显式表达无 data 场景。

---

## 5. 测试与可维护性

### 5.1 现有回归测试（已落地）

| BUG ID | 测试文件 | 覆盖项 |
|---|---|---|
| BUG-2026-08-09-001 | `verify_bug_2026_08_09_001_scanner_dialog_flag.py` | T1–T4：修复模式存在、旧写法清零、rawValue 守卫、failure listener |
| BUG-2026-08-09-002 | `verify_bug_2026_08_09_002_camerax_resolution_selector.py` | T1–T4：3 import 在场、死 import 清、互斥 API 清零、ResolutionSelector 链式配置 |
| BUG-2026-08-09-003 | `verify_bug_2026_08_09_003_takepicture_permission_and_path.py` | T1–T7：FileProvider provider/authority、file_paths、3 launcher 经 helper、裸 launch 清零、Uri.parse(null) 清零、helper 存在、saveBitmapToCacheAndGetUri 调用 |

### 5.2 缺少的测试覆盖

| 缺失测试 | 建议 |
|---|---|
| `submitStocktake` 仓库必填 | 静态扫描 `ScanViewModel.kt` L208 是否有 `if (state.selectedWarehouse == null)` |
| `AuthEventBus` 单次触发语义 | 单元测试 `notifyUnauthorized()` 在 5 个并发协程同时触发时只 emit 1 次 |
| `saveBitmapToCacheAndGetUri` 失败 fallback | 注入 mock `FileProvider.getUriForFile` 抛异常，验证返回 null 不闪退 |
| `WmsRepository.handleResponse` 边界 | 测试 `envelope.data == null` 时 `Result.success(Unit)` 行为 |
| 三个 ViewModel 的 `loadWarehouses` 一致性 | 三个文件 import 路径 + 函数体 diff（应仅 UIState 结构不同） |

---

## 6. 建议改进项清单

| 编号 | 优先级 | 类别 | 改进项 | 工作量 |
|---|---|---|---|---|
| ~~P1-A~~ | ~~中~~ | ~~BUG~~ | ~~`submitStocktake` 补仓库必填校验~~ → **已解决**（当前 main 已校验） | — |
| P1-B | 中 | 重复代码 | 抽离 `ImageCaptureStage` Composable，合并三个拍照屏 590 行重复 | 2d |
| ~~P1-C~~ | ~~中~~ | ~~异常处理~~ | ~~`DocumentOcrResult.extracted` 自我引用~~ → **已解决**（现为 `ExtractedDocument?`） | — |
| P1-D | 中 | 幂等 | `documentOcr` / `recognizeMaterial` 加 `X-Idempotency-Key` 头 | 0.5d |
| P2-A | 低 | 资源 | 启动时清空 `cacheDir/camera/` 旧文件 | 0.5d |
| P2-B | 低 | 重复代码 | 抽离 `BaseWarehouseAwareViewModel` 合并 3 个 ViewModel 的 loadWarehouses | 1d |
| P2-C | 低 | 类型 | `DocumentOcrResult.match_count` / `RecognizeMaterialResult.match_count` 改 camelCase + `@SerializedName` | 0.1d |
| P2-D | 低 | 错误处理 | `displayMessage()` 加长度截断 + HTML 标签过滤 | 0.2d |
| P2-E | 低 | 安全 | `logout()` 同步 commit 清空加密 SharedPreferences | 0.1d |
| P2-F | 低 | 可读性 | 拆分 `DocumentOcrScreen` 为多个 Composable（保持单屏 <300 行） | 1d |
| P3-A | 极低 | 测试 | 补 `AuthEventBus` 并发触发单元测试 | 0.3d |

---

## 7. 与 WMS_BUG_BASELINE 关联

本次审计未触发新的 BUG 登记。审计报告写作时曾把「`submitStocktake` 缺仓库必填校验」列为待登记项（P1-A），但基于当前 main 代码复核，该提交路径已补校验，无需登记。

---

## 8. 审计工具与方法

| 方法 | 覆盖范围 |
|---|---|
| 源码全文阅读 | 全部 Kotlin 源文件（`ui/`、`data/`、`MainActivity.kt`、`WmsApplication.kt`） |
| Manifest / 资源审查 | `AndroidManifest.xml`、`res/xml/file_paths.xml`、`res/xml/network_security_config.xml` |
| 历史 BUG 模式对比 | `WMS_BUG_BASELINE.md` 中所有 `BUG-2026-08-09-*` 条目 |
| 仓库规则检查 | `AGENTS.md` 仓库必填规则、密码策略、相机权限流程 |
| 回归测试存在性 | `tests/verify_bug_2026_08_09_*.py` 三份脚本 |
| 静态分析辅助 | `ls`、`grep` 用于检查 import 残留、危险 API 残留 |

> 本次审计为**纯静态**审计，未运行模拟器/真机做动态行为验证。已发现的所有问题均已对应到具体文件 + 行号 + 修复建议。
