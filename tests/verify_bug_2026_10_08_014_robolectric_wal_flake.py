# -*- coding: utf-8 -*-
"""BUG-2026-10-08-014：PendingQueueRebuildProtectionTest 顽固性偶发第四次复发修复。

## 历史

本测试类的「rebuild preserving queue keeps pending rows」在 CI 多次复发：

  - BUG-2026-09-21-005：初发（建立本类），NATIVE 引擎切 journal_mode 触发
    ``walIndexAppend`` SIGBUS，整次 JVM 被杀（exit 134）；
  - BUG-2026-09-22-001：复发（加 purgeDatabase：关连接 + 删主文件与侧车）；
  - BUG-2026-10-08-014：第三次复发（302b2c1 SIGBUS、74eedaf 断言
    expected:<1> but was:<0>）。

前两次修法都是「清理更狠」；第三次加了 ``PRAGMA journal_mode=TRUNCATE`` +
``PRAGMA wal_checkpoint(TRUNCATE)``，并用**本文件**把它锁成契约防回退。

## 第四次复发：那份契约本身就是根因

2026-10-13 把 Robolectric 开关下沉到全局 ``sqliteMode=LEGACY``（消除
``nativeClose`` SIGSEGV）后，Android 单测从「JVM 猝死」变成 1 例可定位失败：

    SQLiteDatabaseLockedException: DB[31] step() [COMMIT] [database is locked]
      at SQLiteConnection.setLocaleFromConfiguration
      at PendingQueueRebuildProtectionTest.kt:288

当时判断是「本类需要 WAL 语义，LEGACY 不适合它」，于是加类级
``@SQLiteMode(NATIVE)`` 例外 —— CI 立刻否掉：

    java.lang.UnsatisfiedLinkError:
      'void ...SQLiteConnectionNatives.nativeFinalizeStatement(long, long)'

**全局 LEGACY 生效时 Robolectric 根本不加载 native runtime**，类级 NATIVE 覆盖
不是「更稳」而是必然崩。按测试类区分引擎这条路不成立——引擎是**进程级**状态。

## 真正的根因

LEGACY 下那个 SQLITE_BUSY 从来不是引擎问题，是那两行 PRAGMA：

    raw.rawQuery("PRAGMA journal_mode=TRUNCATE", null).close()     ← 对不存在的问题出手
    raw.rawQuery("PRAGMA wal_checkpoint(TRUNCATE)", null).close()

``plantRawDatabase`` 第一件事就是 ``purgeDatabase()``，把主文件连同
-wal/-shm/-journal **整个删掉**。新建文件默认就是 rollback journal 模式，
**根本不是 WAL**——切journal_mode 无从切起，checkpoint 也无checkpoint 可做。

而这同一个根因在两种引擎下表现完全不同：

  ===========  ==========================  ======================================
  引擎          表现                        机制
  ===========  ==========================  ======================================
  NATIVE       exit 134，整次 JVM 被杀      切 journal_mode 走进 walIndexAppend → SIGBUS
  LEGACY       SQLITE_BUSY，可定位          切换留下未完成事务 → 下一次 openDatabase 提交撞锁
  ===========  ==========================  ======================================

表面毫不相干的两类故障，同出一源。

## 本次修复

删除那两行 PRAGMA。删除后该类回归全局 LEGACY，**零例外**通过（CI 80 tests
全绿）。本文件同步把契约**反转**为禁令：不再是「必须有 checkpoint」，
而是「不得切 journal_mode」。

教训：**当一份「防回退」契约本身是根因时，它会一代代把错误结论锁死。**
本文件此前的四条断言正是那两行 PRAGMA 的「锁」，第三次复发时的修法被它固化，
第四次复发又得从它手里把结论抢回来。

仍需保留的防护（真实有效，未随本次改动失效）：

  - ``purgeDatabase`` 的关连接 + 删主文件与侧车（隔离前提）；
  - ``AppDatabase.backupPendingOperations`` 的「只读读到空 → 回退读写」兜底
    （生产代码的防御层，与测试侧无关）。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TEST_KT = (
    ROOT
    / "app/android-native-wms/app/src/test/java/com/factory/wms/PendingQueueRebuildProtectionTest.kt"
)

APP_DB = (
    ROOT
    / "app/android-native-wms/app/src/main/java/com/factory/wms/data/local/AppDatabase.kt"
)


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """剥离注释，只留可执行代码。

    必要性：本文件与被测类都必须在注释里写明「不要切 journal_mode」及其理由，
    若判据不剥离注释，会因说明文字而误报自己。
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)


def _plant_body(src: str) -> str:
    """取 plantRawDatabase 函数体（到下一个 @Test 或类尾）。"""
    start = src.index("private fun plantRawDatabase")
    next_fun = src.find("\n    @Test", start)
    return src[start: next_fun if next_fun != -1 else len(src)]


def _backup_method_body(src: str) -> str:
    """取 backupPendingOperations 函数体（到下一个 internal fun 或类尾）。"""
    start = src.index("internal fun backupPendingOperations")
    next_fun = src.find("\n        internal fun", start + 10)
    return src[start: next_fun if next_fun != -1 else len(src)]


class TestBug014NoJournalModeSwitch:
    """核心契约：不得切 journal_mode。"""

    def test_bug_014_file_exists(self):
        assert TEST_KT.exists(), f"缺文件: {TEST_KT}"

    def test_bug_014_no_journal_mode_switch(self):
        """plantRawDatabase 不得切 journal_mode —— 这正是两次故障的共同根因。

        NATIVE 下会走进 walIndexAppend 触发 SIGBUS（exit 134），LEGACY 下留下
        未完成事务导致后续 openDatabase 抛 SQLITE_BUSY。
        """
        code = _strip_comments(_read(TEST_KT))
        hits = re.findall(r"PRAGMA\s+(?:journal_mode\s*=|wal_checkpoint)", code, re.I)
        assert not hits, (
            f"BUG-014：测试代码又切起了 journal_mode / wal_checkpoint（{hits}）。\n"
            f"plantRawDatabase 先purgeDatabase() 把库文件与侧车整个删掉，新建文件"
            f"默认就不是 WAL，这个切换是对不存在的问题出手——它曾把同一个根因"
            f"劈成两种故障：NATIVE 引擎 SIGBUS（exit 134，整次 JVM 被杀）、"
            f"LEGACY 引擎 SQLITE_BUSY。"
        )

    def test_bug_014_rationale_documented(self):
        """删除处必须留注释说明「为什么不再需要切」，否则会被当无用代码重加。

        本文件此前正是把那个错误做法锁成契约的元凶；反转后的契约若不写清理由，
        下一个遇到「只读打开读到空」的人会照旧把它加回来。
        """
        src = _read(TEST_KT)
        body = _plant_body(src)
        assert "journal_mode" in body, (
            "BUG-014：plantRawDatabase 内未记录 journal_mode 相关的说明。"
            "删除了防护而不写清理由，等于把同一个坑留给下一个人。"
        )


class TestBug014IsolationStillInPlace:
    """隔离防护仍然必须保留（真实有效，与本次根因无关）。"""

    def test_bug_014_existing_purge_kept(self):
        """purgeDatabase（关连接 + 删主文件与侧车）是隔离前提，不得丢失。"""
        src = _read(TEST_KT)
        assert "closeSingletonInstance()" in src
        assert "resetSingleton()" in src
        assert '"-journal"' in src, "purgeDatabase 必须删 -journal（rollback journal 侧车）"
        assert '"-wal"' in src and '"-shm"' in src, "purgeDatabase 必须删 -wal/-shm 侧车"

    def test_bug_014_sidecar_cleanup_after_plant(self):
        """种完数据后仍要兜底删侧车，让后续 OPEN_READONLY 打开自洽主文件。"""
        body = _plant_body(_read(TEST_KT))
        assert "-wal" in body and "-shm" in body, (
            "BUG-014：plantRawDatabase 缺 -wal/-shm 侧车清理"
        )
        assert ".delete()" in body, "BUG-014：侧车清理未调用 delete()"

    def test_bug_014_plant_purges_first(self):
        """种数据前必须先 purge —— 这正是「新建文件不是 WAL」的前提。"""
        body = _plant_body(_read(TEST_KT))
        purge_idx = body.index("purgeDatabase()")
        create_idx = body.index("openOrCreateDatabase")
        assert purge_idx < create_idx, (
            "BUG-014：必须先 purgeDatabase() 再建库，否则新文件可能继承 WAL 模式——"
            "而这正是 journal_mode 切换曾经看起来必要的前提"
        )


class TestBug014BackupFallbackInProduction:
    """生产代码的兜底（只读读到空 → 回退读写）仍须保留。

    这是 AppDatabase 侧的防御层，与测试侧的 PRAGMA 无关：即使真机上某个路径
    真的产出了非自洽主文件，它仍应让备份不静默为空。
    """

    def test_bug_014_backup_readempty_falls_back_to_readwrite(self):
        """OPEN_READONLY 读到空（WAL 未恢复）时必须回退 OPEN_READWRITE。

        原回退只在「只读打开抛异常」时触发；Robolectric 影子 SQLite 下只读打开
        可以成功但不执行 WAL recovery → 读到空 → 备份静默为空 → 删库重建丢单。
        """
        body = _backup_method_body(_read(APP_DB))
        assert "只读读到空" in body or "只读备份为空" in body, (
            "BUG-014：backupPendingOperations 缺「只读读到空 → 回退读写」修复"
        )
        assert "dbFile.length() > 0L" in body, (
            "BUG-014：回退必须以文件非空为前提（空库不浪费读写打开）"
        )
        readonly_idx = body.index("SQLiteDatabase.OPEN_READONLY")
        readwrite_fallback_idx = body.index("OPEN_READWRITE", readonly_idx)
        assert readonly_idx < readwrite_fallback_idx, (
            "BUG-014：必须先只读、再回退读写（顺序不得反）"
        )

    def test_bug_014_backup_readwrite_fallback_reads_rows(self):
        """回退读写打开后必须真正执行读行（不是只打开不读）。"""
        body = _backup_method_body(_read(APP_DB))
        assert "fun readRows" in body, "BUG-014：备份读行逻辑必须抽成 readRows 局部函数复用"
        assert body.count("readRows(it)") >= 3, (
            "BUG-014：只读主路径 / 只读空回退 / 只读打开失败回退都必须用 readRows 读行"
        )

    def test_bug_014_bug_comment_present(self):
        """修复处必须有 BUG-2026-10-08-014 注释说明根因（防回退时不知为何）。"""
        body = _backup_method_body(_read(APP_DB))
        assert "BUG-2026-10-08-014" in body, "BUG-014：backupPendingOperations 缺根因注释"
        assert "WAL" in body, "BUG-014：注释必须说明 WAL 未恢复根因"
