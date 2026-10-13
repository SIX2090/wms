# -*- coding: utf-8 -*-
"""守护：Robolectric 必须走全局 LEGACY SQLite，开关只有一处，且不得切journal_mode。

## 事故背景

Android APK Build 连续 3 次红灯（8d3cbf19/ 67f9c741 / 55cac2c7），失败步骤
始终是 ``Unit tests (BUG-2026-08-16-021)``，报错：

    Process 'Gradle Test Executor 1' finished with non-zero exit value 134

134 不是断言失败。日志里全部用例都 PASSED，然后 JVM 被native 层 SIGSEGV 带走：

    # Problematic frame:
    #  C  [librobolectric-nativeruntime.so+0x43eabf]
    #     android::nativeClose(_JNIEnv*, _jclass*, long)+0xf

崩溃发生在 ScanFeedbackTest 打开 SQLiteConnection 之后。

## 为什么这是第二次踩同一个坑

2026-09-21 修 BUG-2026-09-21-005（删库重建清空离线队列）时已遇到过同类崩溃：
Robolectric 原生 SQLite 在切换 WAL 时于 ``walIndexAppend`` SIGBUS。当时的
解法是给**那一个**测试类加 ``@SQLiteMode(SQLiteMode.Mode.LEGACY)``。

但 native 崩溃的触发条件是「本进程是否碰过 SQLite」，**与具体测试类无关**。
只要还有任何一个测试类建库（ScanFeedbackTest 就通过 ScanViewModel →
WmsRepository 间接建库），同一个 worker 里的全部用例都会被一起带走，且
Gradle 只能报 exit 134，不指向任何具体断言。

## 本测试锁定的约束

1. ``app/src/test/resources/robolectric.properties`` 必须存在且含
   ``sqliteMode=LEGACY``、``sdk=31``；
2. **不得有任何测试类挂``@SQLiteMode``** —— 零例外。全局 LEGACY 生效时
   Robolectric 根本不加载 native runtime，类级 NATIVE 覆盖会直接抛
   ``UnsatisfiedLinkError: nativeFinalizeStatement``，不是「更稳」而是「必挂」；
3. **测试代码不得切换 journal_mode / 做wal_checkpoint** —— 这是 2026-10-13
   那条 SIGBUS 的真正触发点，详见下面「同一个根因的两种表现」。

## 同一个根因的两种表现（为什么第 3 条才是关键）

把开关下沉到全局 LEGACY 后，Android 单测从「JVM 猝死」变成 1 例可定位的失败：

    PendingQueueRebuildProtectionTest >
      rebuild preserving queue keeps pending rows FAILED
    SQLiteDatabaseLockedException: DB[31] step() [COMMIT] [database is locked]

当时的判断是「本类需要 WAL 语义，LEGACY 不适合它」，于是加类级注解放回
NATIVE —— 结果更糟：``UnsatisfiedLinkError: nativeFinalizeStatement``。

真正的原因在测试自己的种数据函数里。``plantRawDatabase`` 里有两行：

    raw.rawQuery("PRAGMA journal_mode=TRUNCATE", null).close()
    raw.rawQuery("PRAGMA wal_checkpoint(TRUNCATE)", null).close()

它们是BUG-2026-10-08-014 期间为对抗「WAL recovery 读到空」加的补救。但
``plantRawDatabase`` 第一件事就是 ``purgeDatabase()``，把主文件连同
-wal/-shm/-journal **整个删掉**—— 新建文件默认就是 rollback journal 模式，
根本不是 WAL。这两行是对不存在的问题出手，而它们恰好制造了两种故障：

* NATIVE 引擎：切 journal_mode 会走进 ``walIndexAppend`` → SIGBUS（exit 134）；
* LEGACY 引擎：切换留下未完成事务 → 下一次 openDatabase 提交时 SQLITE_BUSY。

**表面毫不相干的两个症状，同出一源。** 删掉这两行后该类回归全局 LEGACY，
零例外通过。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_APP = ROOT / "app" / "android-native-wms" / "app"
PROPS = ANDROID_APP / "src" / "test" / "resources" / "robolectric.properties"
TEST_SRC = ANDROID_APP / "src" / "test" / "java"
# 备份文件与生成物不参与判定
_SKIP_DIR_PARTS = ("build",)


def _kotlin_test_files() -> list[Path]:
    if not TEST_SRC.exists():
        return []
    return sorted(
        p
        for p in TEST_SRC.rglob("*.kt")
        if not any(part in _SKIP_DIR_PARTS for part in p.parts)
    )


def _strip_comments(text: str) -> str:
    """去掉 ``//`` 行注释与 ``/* */`` 块注释，只留可执行代码。

    判据必须只看代码：这几条约束的历史说明里反复出现被禁写法的**字面**
    （``PRAGMA journal_mode=TRUNCATE``、``@SQLiteMode(NATIVE)``），
    若不剥离注释，守护测试会因说明文字而误报自己。
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def test_scan_target_is_not_empty():
    """扫描目标必须真的非空，否则下面所有判据都是空转的假绿。

    本文件第一版把 ``"src" "test"`` 漏了逗号，路径拼成 ``srctest``，
    ``_kotlin_test_files()`` 恒返回空列表，5 条判据全部「通过」——
    而真实代码里正挂着违规注解。这类bug 只在有违规样本时才暴露，
    故必须有一条测试直接断言「扫到了东西」。
    """
    files = _kotlin_test_files()
    assert files, (
        f"未扫到任何 Kotlin 测试文件（TEST_SRC={TEST_SRC}）。"
        f"路径拼接出错会让所有判据空转——请先确认该目录存在且路径正确。"
    )
    # 至少要包含本守护测试间接针对的那几个类，否则说明路径指到了别处
    names = {p.name for p in files}
    assert "PendingQueueRebuildProtectionTest.kt" in names, (
        f"扫描结果不含 PendingQueueRebuildProtectionTest.kt（实际扫到 {len(names)} "
        f"个文件），TEST_SRC 很可能指错了目录。"
    )


class TestRobolectricSqliteModeIsGlobal:
    def test_global_properties_exist(self):
        assert PROPS.is_file(), (
            f"缺少全局 Robolectric 配置 {PROPS}。\n"
            f"删除它会让 SDK 26+ 回落到原生 SQLite，在 GitHub Actions runner 上"
            f"触发 native SIGSEGV / SIGBUS（exit 134，整次 JVM 被杀、且不指向"
            f"任何断言）。若确要改回 NATIVE，请先在真机 / instrumented test 上"
            f"验证稳定性，并同步更新本测试。"
        )

    def test_global_properties_uses_legacy(self):
        text = PROPS.read_text(encoding="utf-8")
        m = re.search(r"^\s*sqliteMode\s*=\s*(\S+)\s*$", text, re.M)
        assert m, f"{PROPS.name} 缺少 sqliteMode 配置项"
        assert m.group(1).upper() == "LEGACY", (
            f"sqliteMode={m.group(1)}，应为 LEGACY。"
            f"原生 SQLite 在 CI runner 上有两条已确认的崩溃路径"
            f"（walIndexAppend SIGBUS / nativeClose SIGSEGV）。"
        )

    def test_global_properties_pins_sdk(self):
        """sdk 必须显式钉住，避免随 Robolectric 版本默认值漂移。"""
        text = PROPS.read_text(encoding="utf-8")
        assert re.search(r"^\s*sdk\s*=\s*31\s*$", text, re.M), (
            f"{PROPS.name} 未把 sdk 钉到 31（现场设备 HUAWEI LIO-AN00 是"
            f"Android 12 / sdk 31）。不钉住的话默认值会随Robolectric 版本漂移。"
        )

    def test_no_class_level_sqlite_mode(self):
        """任何测试类都不得挂类级 ``@SQLiteMode`` —— 零例外。

        曾经留过一个「本类需要 WAL 语义」的例外，实测两条路都堵死：

        * 走全局 LEGACY 时Robolectric 不加载 native runtime，类级 NATIVE 覆盖
          直接抛 ``UnsatisfiedLinkError: nativeFinalizeStatement``；
        * 挂 LEGACY 看似可行，但该类当时的失败另有根因（见
          ``test_no_journal_mode_switch``），修掉根因后根本不需要例外。

        也就是说「按测试类区分引擎」这条路在 Robolectric 上不成立——引擎是
        进程级状态，不是类级状态。
        """
        offenders = [
            path.name
            for path in _kotlin_test_files()
            if re.search(r"^\s*@SQLiteMode\b", path.read_text(encoding="utf-8", errors="replace"), re.M)
        ]
        assert not offenders, (
            f"这些测试类挂了类级 @SQLiteMode：{offenders}。\n"
            f"请删掉该注解，改由 app/src/test/resources/robolectric.properties "
            f"统一施加。native 崩溃取决于进程是否碰过 SQLite，与具体测试类无关，"
            f"逐类加注解必然漏（2026-10-13 ScanFeedbackTest 即是漏网的那个）；"
            f"而全局 LEGACY 下类级 NATIVE 覆盖会抛 UnsatisfiedLinkError。\n"
            f"若本类确实需要 native 语义，请先在真机上确认，那是另一套测试"
            f"（instrumented test），不该放在 JVM 单测里。"
        )

    def test_no_journal_mode_switch(self):
        """测试代码不得切journal_mode / 做 wal_checkpoint。

        这是 2026-10-13 那两次 Android 红灯的**共同根因**：
        NATIVE 下切 journal_mode 触发 walIndexAppend SIGBUS；LEGACY 下切换留下
        未完成事务，后续 openDatabase 提交时抛 SQLITE_BUSY。

        而切它是没有意义的——``plantRawDatabase`` 先purgeDatabase() 把库文件
        连同侧车整个删掉，新文件默认就是 rollback journal 模式，本来就不是 WAL。

        判据只看可执行代码（注释里引用这些语句作说明是允许且必要的）。
        """
        offenders: list[str] = []
        for path in _kotlin_test_files():
            code = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
            hits = [
                m.group(0)
                for m in re.finditer(
                    r"PRAGMA\s+(?:journal_mode\s*=|wal_checkpoint)", code, re.I
                )
            ]
            if hits:
                offenders.append(f"{path.name}: {sorted(set(hits))}")

        assert not offenders, (
            f"这些测试在运行期切journal_mode / 做 wal_checkpoint：{offenders}。\n"
            f"该操作在 NATIVE 引擎触发 walIndexAppend SIGBUS（exit 134，整次 JVM "
            f"被杀），在 LEGACY 引擎留下未完成事务导致后续 openDatabase 抛"
            f"SQLITE_BUSY。若目的是「让只读打开能读到刚写入的行」，请确保种数据"
            f"前已删除库文件与 -wal/-shm/-journal 侧车（新建文件本就不是 WAL，"
            f"不需要任何切换）。"
        )

    def test_properties_file_has_migration_rationale(self):
        """配置里的注释必须记录「为什么是 LEGACY」，否则后人会当成无用配置删掉。

        这不是文档洁癖：本文件正是被当成「多余的旧配置」而删掉过一次，
        代价是三连红。故要求同时记下 SIGBUS 与 SIGSEGV 两条路径。
        """
        text = PROPS.read_text(encoding="utf-8")
        assert "SIGBUS" in text and "SIGSEGV" in text, (
            f"{PROPS.name} 的注释须同时记录两条已确认的 native 崩溃路径"
            f"（SIGBUS / SIGSEGV）。缺了它，后来者无从判断能否删掉这个配置。"
        )

    def test_properties_file_documents_journal_mode_trap(self):
        """配置注释须点明「切 journal_mode 是共同根因」，防止有人再加回来。

        该结论是踩了两次（SIGBUS、SQLITE_BUSY）才换来的，只写在提交信息里
        等于没写——提交信息不会随代码一起被读到。
        """
        text = PROPS.read_text(encoding="utf-8")
        assert "journal_mode" in text, (
            f"{PROPS.name} 未提及 journal_mode。该切换是 2026-10-13 两类失败的"
            f"共同根因（NATIVE→SIGBUS，LEGACY→SQLITE_BUSY），须在配置里留痕，"
            f"否则后人会把它当无害的「保险措施」再加回来。"
        )
