"""BUG-2026-09-21-005：删库重建不得静默清空离线待同步队列（源码门禁）。

背景：`AppDatabase.getDatabase` 的恢复策略是"建库失败 → 删库重建"，但本库除
物料缓存/操作日志（可重建）外还有 `pending_operations`——工人已提交、尚未
联网同步的离线单据，是**不可重建的业务数据**。此前 `deleteDatabase` 把它一并
抹掉且无日志、无告警；更糟的是 Room `build()` 惰性打开库文件，"库损坏/迁移缺失"
的异常根本不会在建库时抛出，删库恢复分支实际是死代码，异常会推迟到 ViewModel
组合期的某次 DAO 调用随机爆出（BUG-2026-09-13-023 的闪退路径）。

修复（详见 AppDatabase.kt）：
  1. buildDatabase 构建后立即 `openHelper.writableDatabase` 强制真实打开，
     让恢复分支对触发场景真实可达；
  2. 删库前 `backupPendingOperations` 用原生 SQLite 只读备份队列表
     （绕开 Room——Room 校验失败往往正是触发点）；
  3. 重建后 `restorePendingOperations` 经 openHelper 原样回补；
  4. 备份/回补失败记 ERROR（R5：失败必须让人知道），不阻断启动。

本测试锁死上述接线的顺序与存在性，防止后续重构把备份/回补删掉导致问题复发。
运行时行为由 Android 侧 Robolectric 测试 PendingQueueRebuildProtectionTest 覆盖
（本沙箱无 Android SDK，编译与 JVM 测试以 CI 的 testReleaseUnitTest 为准）。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DATABASE = (
    ROOT
    / "app/android-native-wms/app/src/main/java/com/factory/wms/data/local/AppDatabase.kt"
)


def _read() -> str:
    return APP_DATABASE.read_text(encoding="utf-8")


def test_backup_runs_before_delete_and_restore_runs_after_rebuild():
    """恢复路径顺序必须是：备份 → 删库 → 重建 → 回补。"""
    source = _read()
    i_backup = source.index("val backup = backupPendingOperations(appContext)")
    i_delete = source.index("appContext.deleteDatabase(DB_NAME)")
    i_rebuild = source.index("val rebuilt = buildDatabase(appContext)")
    i_restore = source.index("restorePendingOperations(rebuilt, backup)")
    assert i_backup < i_delete < i_rebuild < i_restore, (
        "删库前必须先备份 pending_operations、重建后必须回补，"
        "否则离线待同步单据会被静默清空（BUG-2026-09-21-005）"
    )
    # getDatabase 的 catch 分支必须委托到同一实现，不得另写一套漏掉备份
    assert "rebuildPreservingQueue(appContext)" in source


def test_backup_bypasses_room_with_raw_readonly_sqlite():
    """备份必须用原生 SQLite 只读直读，不得再经会失败的 Room 校验。"""
    source = _read()
    assert "internal fun backupPendingOperations(context: Context)" in source
    assert "SQLiteDatabase.OPEN_READONLY" in source
    assert "FROM pending_operations" in source
    # 可空列必须显式处理，不得读成字符串 "null"
    assert "c.isNull(3)" in source and "c.isNull(7)" in source


def test_restore_writes_via_open_helper_not_dao():
    """回补走 openHelper.writableDatabase（getDatabase 在主线程同步执行，DAO 禁主线程）。"""
    source = _read()
    assert "internal fun restorePendingOperations(db: AppDatabase" in source
    assert "db.openHelper.writableDatabase" in source
    assert "SQLiteDatabase.CONFLICT_REPLACE" in source


def test_failures_are_loud_error_logs_not_silent():
    """备份/回补失败必须 ERROR 级大声记录（R5），不得静默吞掉。"""
    source = _read()
    assert "离线待同步单据备份失败" in source
    assert "离线待同步单据回补失败" in source
    assert source.count("Log.e(") >= 2


def test_eager_open_makes_recovery_branch_reachable():
    """buildDatabase 必须构建后立即打开，否则恢复分支是死代码（Room 惰性打开）。"""
    source = _read()
    assert ".also { it.openHelper.writableDatabase }" in source


def test_rebuildable_data_comment_no_longer_false():
    """旧注释谎称"只存放物料缓存与操作日志、均可重建"——该错误认知即本 BUG 根因。"""
    source = _read()
    assert "本地库只存放物料缓存与" not in source
    assert "不可重建" in source


def test_existing_recovery_wording_kept_for_resilience_gate():
    """与 test_android_startup_crash_resilience.py 的既有断言保持兼容。"""
    source = _read()
    assert "建库失败，尝试删除本地库重建" in source
    assert "appContext.deleteDatabase(DB_NAME)" in source
