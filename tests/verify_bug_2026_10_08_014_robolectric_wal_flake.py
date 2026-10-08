# -*- coding: utf-8 -*-
"""BUG-2026-10-08-014：PendingQueueRebuildProtectionTest 顽固性偶发第三次复发修复。

背景：
  本测试类的「rebuild preserving queue keeps pending rows」在 CI 三次复发：
    - BUG-2026-09-21-005：初发（建立本类）
    - BUG-2026-09-22-001：复发（加 purgeDatabase：关连接+删主文件与侧车）
    - BUG-2026-10-08-014：第三次复发——302b2c1 run SIGBUS 崩 JVM、
      74eedaf run 断言 expected:<1> but was:<0>
  前两次修法都是「清理更狠」，没打在根因上。

根因（本次定案）：
  plantRawDatabase 用 openOrCreateDatabase + use{} 种数据，WAL 模式下关闭时
  刚写入的行可能仍留在 -wal 侧车未 checkpoint 到主文件。
  backupPendingOperations 先以 OPEN_READONLY 打开——只读打开无法恢复 WAL 索引，
  读不到刚种的行 → 备份为空 → rebuildPreservingQueue 删库重建后自然是空。
  是否触发取决于前序用例（getDatabase catch delegates...）留下的 Room 实例
  何时完成 WAL 恢复，纯时序/顺序漂移——正是「每次挂的方法都不同」的原因。

修复：
  plantRawDatabase 关闭前执行 PRAGMA wal_checkpoint(TRUNCATE) 把 WAL 数据
  合并进主文件并截断侧车，再兜底删除 -wal/-shm——任何打开方式都能读到，
  与用例执行顺序彻底无关。

本文件为静态契约测试，防止回退。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEST_KT = (
    ROOT
    / "app/android-native-wms/app/src/test/java/com/factory/wms/PendingQueueRebuildProtectionTest.kt"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_bug_014_file_exists():
    assert TEST_KT.exists(), f"缺文件: {TEST_KT}"


def test_bug_014_wal_checkpoint_in_plant():
    """种库后必须强制 WAL checkpoint（根因修复，不得回退）。"""
    src = _read(TEST_KT)
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in src, \
        "BUG-014：plantRawDatabase 缺 wal_checkpoint(TRUNCATE)"


def test_bug_014_checkpoint_inside_plant_method():
    """checkpoint 必须在 plantRawDatabase 函数体内（不是散落在别处）。"""
    src = _read(TEST_KT)
    start = src.index("private fun plantRawDatabase")
    # 取到该函数结束（下一个 fun 或类尾）
    next_fun = src.find("\n    @Test", start)
    body = src[start: next_fun if next_fun != -1 else len(src)]
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in body, \
        "BUG-014：checkpoint 不在 plantRawDatabase 函数体内"


def test_bug_014_sidecar_cleanup_after_checkpoint():
    """checkpoint 后必须兜底删除 -wal/-shm 侧车（OPEN_READONLY 不再受 WAL 影响）。"""
    src = _read(TEST_KT)
    start = src.index("private fun plantRawDatabase")
    next_fun = src.find("\n    @Test", start)
    body = src[start: next_fun if next_fun != -1 else len(src)]
    assert '"-wal"' in body and '"-shm"' in body, \
        "BUG-014：plantRawDatabase 缺 -wal/-shm 侧车清理"
    assert ".delete()" in body, "BUG-014：侧车清理未调用 delete()"


def test_bug_014_checkpoint_before_close():
    """checkpoint 必须在 use{} 块内（库仍打开时），不能在关闭后执行。"""
    src = _read(TEST_KT)
    start = src.index("private fun plantRawDatabase")
    next_fun = src.find("\n    @Test", start)
    body = src[start: next_fun if next_fun != -1 else len(src)]
    checkpoint_idx = body.index("PRAGMA wal_checkpoint(TRUNCATE)")
    use_close_idx = body.index("raw.version = userVersion")
    # checkpoint 在 version 设置之后、use 块结束之前（raw 前缀说明仍在 use 作用域）
    assert checkpoint_idx > use_close_idx, \
        "BUG-014：checkpoint 应在种完数据后执行"
    assert "raw.rawQuery(\"PRAGMA wal_checkpoint(TRUNCATE)\"" in body, \
        "BUG-014：checkpoint 必须通过 raw 连接执行（use 块内）"


def test_bug_014_existing_purge_kept():
    """既有 purgeDatabase 防护（关连接+删主文件与侧车）不得丢失。"""
    src = _read(TEST_KT)
    assert "closeSingletonInstance()" in src
    assert "resetSingleton()" in src
    assert '"-journal"' in src  # purgeDatabase 里的完整侧车清单


APP_DB = (
    ROOT
    / "app/android-native-wms/app/src/main/java/com/factory/wms/data/local/AppDatabase.kt"
)


def _backup_method_body(src: str) -> str:
    """取 backupPendingOperations 函数体（到下一个 internal fun 或类尾）。"""
    start = src.index("internal fun backupPendingOperations")
    next_fun = src.find("\n        internal fun", start + 10)
    return src[start: next_fun if next_fun != -1 else len(src)]


def test_bug_014_backup_readempty_falls_back_to_readwrite():
    """真根因修复：OPEN_READONLY 读到空（WAL 未恢复）时必须回退 OPEN_READWRITE。

    原回退只在「只读打开抛异常」时触发；Robolectric 影子 SQLite 下只读打开
    可以成功但不执行 WAL recovery → 读到空 → 备份静默为空 → 删库重建丢单。
    """
    src = _read(APP_DB)
    body = _backup_method_body(src)
    assert "只读读到空" in body or "只读备份为空" in body, \
        "BUG-014：backupPendingOperations 缺「只读读到空 → 回退读写」修复"
    assert "dbFile.length() > 0L" in body, \
        "BUG-014：回退必须以文件非空为前提（空库不浪费读写打开）"
    # 只读分支里必须先尝试 OPEN_READONLY
    readonly_idx = body.index("SQLiteDatabase.OPEN_READONLY")
    readwrite_fallback_idx = body.index("OPEN_READWRITE", readonly_idx)
    assert readonly_idx < readwrite_fallback_idx, \
        "BUG-014：必须先只读、再回退读写（顺序不得反）"


def test_bug_014_backup_readwrite_fallback_reads_rows():
    """回退读写打开后必须真正执行读行（不是只打开不读）。"""
    src = _read(APP_DB)
    body = _backup_method_body(src)
    # 读写回退分支里必须复用 readRows 读取逻辑（局部函数）
    assert "fun readRows" in body, "BUG-014：备份读行逻辑必须抽成 readRows 局部函数复用"
    # readRows(it) 在三个分支各出现一次（只读主路径 + 只读空回退 + 只读打开失败回退）
    assert body.count("readRows(it)") >= 3, \
        "BUG-014：只读主路径/只读空回退/只读打开失败回退都必须用 readRows 读行"


def test_bug_014_bug_comment_present():
    """修复处必须有 BUG-2026-10-08-014 注释说明根因（防回退时不知为何）。"""
    src = _read(APP_DB)
    body = _backup_method_body(src)
    assert "BUG-2026-10-08-014" in body, \
        "BUG-014：backupPendingOperations 缺根因注释"
    assert "WAL" in body, "BUG-014：注释必须说明 WAL 未恢复根因"
