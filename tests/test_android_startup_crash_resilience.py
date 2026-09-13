"""BUG-2026-09-13-023：Android 启动崩溃韧性（本地持久化失败不得杀进程）。

背景：现场反馈 Android 客户端「WMS扫码屡次停止运行」（Screenshot_20260913_235020）。
经代码实证，崩溃发生在 App 冷启动链路：AppNavGraph 组合期一次性创建 11 个 ViewModel，
每个都构造 WmsRepository（同步建 Room 库 + 惰性建 EncryptedSharedPreferences），
而 AuthViewModel.init 的协程直接读取加密存储且**无 try/catch**。
任一持久化读取失败（Keystore 失效 / 库文件损坏 / 磁盘满）都会让协程抛未捕获异常
→ 杀进程 → 用户看到"屡次停止运行"。

本测试用源码断言锁死三层兜底，防止后续重构把 try/catch 删掉导致问题复发。
覆盖文件：
  - data/repository/WmsRepository.kt
  - data/local/AppDatabase.kt
  - ui/viewmodel/auth/AuthViewModel.kt
  - ui/viewmodel/scan/ScanViewModel.kt
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KOTLIN_ROOT = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"

REPOSITORY = KOTLIN_ROOT / "data/repository/WmsRepository.kt"
APP_DATABASE = KOTLIN_ROOT / "data/local/AppDatabase.kt"
AUTH_VIEW_MODEL = KOTLIN_ROOT / "ui/viewmodel/auth/AuthViewModel.kt"
SCAN_VIEW_MODEL = KOTLIN_ROOT / "ui/viewmodel/scan/ScanViewModel.kt"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_repository_wraps_database_creation_in_try_catch():
    """WmsRepository 构造期建库必须可失败：返回可空 db 而非抛异常。"""
    source = _read(REPOSITORY)
    assert "private val db: AppDatabase? = try {" in source
    assert "AppDatabase.getDatabase(context)" in source
    # 可空 DAO：所有调用点必须走安全调用
    assert "private val materialDao = db?.materialDao()" in source
    assert "private val operationLogDao = db?.operationLogDao()" in source
    assert "private val pendingOperationDao = db?.pendingOperationDao()" in source


def test_repository_cache_writes_never_throw():
    """本地缓存写入必须走 safeCache 统一入口，失败只记日志。"""
    source = _read(REPOSITORY)
    assert "private suspend fun safeCache(block: suspend () -> Unit)" in source
    assert "本地缓存写入失败（已忽略）" in source
    # 期初库存操作日志必须经 safeCache（DAO 已可空）
    assert "logOperation(" in source
    assert "operationLogDao?.insert(" in source


def test_encrypted_prefs_degrades_instead_of_crashing():
    """EncryptedSharedPreferences 创建失败必须降级为 null，并重置损坏文件。"""
    source = _read(REPOSITORY)
    assert "private val encryptedPrefs: android.content.SharedPreferences? by lazy {" in source
    assert "private fun createEncryptedPrefs(): android.content.SharedPreferences {" in source
    assert "private fun resetSecurePrefsFile()" in source
    assert "加密存储不可用，已降级为待登录状态" in source
    # token 读取必须自身兜底（Keystore 中途失效）
    assert "读取 token 失败，按未登录处理" in source
    # 保存失败不得阻断登录（内存态 token 仍可用）
    assert "保存 token 失败（本次会话仍可用）" in source


def test_repository_offline_queue_is_nullable_when_db_unavailable():
    """本地库不可用时离线队列返回 null，且入队处不得谎报"已暂存"。"""
    source = _read(REPOSITORY)
    assert "val offlineQueue: OfflineQueueManager? by lazy {" in source
    assert "val dao = pendingOperationDao ?: return@lazy null" in source
    # 入队前判空，null 时按"暂存失败"处理
    assert "val queue = offlineQueue" in source
    assert "val queued = queue != null && queue.enqueue(" in source


def test_app_database_recovers_by_recreating_corrupted_file():
    """建库失败时先删库重建一次（本地库为可重建缓存）。"""
    source = _read(APP_DATABASE)
    assert 'private const val DB_NAME = "wms_database"' in source
    assert "private fun buildDatabase(context: Context): AppDatabase" in source
    assert "建库失败，尝试删除本地库重建" in source
    assert "appContext.deleteDatabase(DB_NAME)" in source


def test_auth_view_model_init_cannot_kill_process():
    """AuthViewModel.init 的会话还原必须整体 try/catch。"""
    source = _read(AUTH_VIEW_MODEL)
    assert "会话还原失败，降级为未登录" in source
    assert "catch (e: Exception)" in source
    # 401 登出链路同样兜底
    assert "401 登出处理异常（已忽略）" in source
    # 降级后必须停留在未登录态，不得误判已登录
    assert "_uiState.value = _uiState.value.copy(isLoggedIn = false)" in source


def test_scan_view_model_tolerates_missing_offline_queue():
    """ScanViewModel 订阅离线队列计数时必须容忍 null。

    BUG-2026-09-13-023 追加修复：#481 CI 暴露 Kotlin 硬编译错误
    `ScanViewModel.kt:303:48 'return' is prohibited here`——init 块内不允许
    使用 `return` 做提前退出。必须改为 `if (queue != null) { ... }` 包裹。
    此断言即为防止该类写法回潮。
    """
    source = _read(SCAN_VIEW_MODEL)
    # 必须用 if 判空包裹，不能写成 `?: return`
    assert "val queue = repository.offlineQueue\n        if (queue != null) {" in source
    assert "?: return\n" not in source.split("init {")[1].split("}")[0] if "init {" in source else True
    assert "repository.offlineQueue?.retryFailed()" in source
