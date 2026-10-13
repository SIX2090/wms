# -*- coding: utf-8 -*-
"""守护：Robolectric 必须走全局 LEGACY SQLite，且开关只有一处。

## 事故背景

Android APK Build 连续 3 次红灯（8d3cbf19 / 67f9c741 / 55cac2c7），失败步骤
始终是 ``Unit tests (BUG-2026-08-16-021)``，报错：

    Process 'Gradle Test Executor 1' finished with non-zero exit value 134

134 不是断言失败。日志里全部用例都PASSED，然后 JVM 被native 层SIGSEGV 带走：

    # Problematic frame:
    #  C  [librobolectric-nativeruntime.so+0x43eabf]
    #     android::nativeClose(_JNIEnv*, _jclass*, long)+0xf

崩溃发生在 ScanFeedbackTest 打开 SQLiteConnection 之后。

## 为什么这是第二次踩同一个坑

2026-09-21修 BUG-2026-09-21-005（删库重建清空离线队列）时已遇到过同类崩溃：
Robolectric 原生 SQLite 在切换 WAL 时于 ``walIndexAppend`` SIGBUS。当时的
解法是给**那一个**测试类加 ``@SQLiteMode(SQLiteMode.Mode.LEGACY)``。

但 native 崩溃的触发条件是「本进程是否碰过 SQLite」，**与具体测试类无关**。
只要还有任何一个测试类建库（ScanFeedbackTest 就通过 ScanViewModel →
WmsRepository 间接建库），同一个 worker 里的全部用例都会被一起带走，且
Gradle 只能报 exit134，不指向任何具体断言。

## 本测试锁定的约束

1. ``app/src/test/resources/robolectric.properties`` 必须存在且含
   ``sqliteMode=LEGACY`` —— 全局唯一开关；
2. 测试类上不得再挂 ``@SQLiteMode``—— 两处配置必然漂移，且逐类加注解的
   治标方式已经失败过一次。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID_APP = ROOT / "app" / "android-native-wms" / "app"
PROPS = ANDROID_APP / "src" / "test" / "resources" / "robolectric.properties"
TEST_SRC = ANDROID_APP / "src" / "test" / "java"


def _kotlin_test_files() -> list[Path]:
    if not TEST_SRC.exists():
        return []
    return sorted(TEST_SRC.rglob("*.kt"))


class TestRobolectricSqliteModeIsGlobal:
    def test_global_properties_exist(self):
        assert PROPS.is_file(), (
            f"缺少全局 Robolectric 配置 {PROPS}。\n"
            f"删除它会让 SDK 26+ 回落到原生 SQLite，在 GitHub Actions runner 上"
            f"触发 native SIGSEGV / SIGBUS（exit 134，整次 JVM 被杀、且不指向"
            f"任何断言）。若确要改回 NATIVE，请先在真机/ instrumented test 上"
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
            f"{PROPS.name} 未把 sdk 钉到 31（现场设备 HUAWEI LIO-AN00 是 "
            f"Android 12 / sdk 31）。不钉住的话默认值会随 Robolectric 版本漂移。"
        )

    def test_no_class_level_sqlite_mode_annotation(self):
        """禁止测试类再挂 @SQLiteMode——全局开关已是唯一入口。

        两处配置会漂移；更重要的是，逐类加注解的治标方式已经被
        BUG-2026-09-21-005 那次修复证伪过一次。
        """
        offenders = []
        for path in _kotlin_test_files():
            text = path.read_text(encoding="utf-8", errors="replace")
            # 只看注解用法（@SQLiteMode），注释里的说明不算
            if re.search(r"^\s*@SQLiteMode\b", text, re.M):
                offenders.append(path.name)
        assert not offenders, (
            f"这些测试类挂了类级 @SQLiteMode：{offenders}。\n"
            f"请改由 app/src/test/resources/robolectric.properties 统一施加——"
            f"native 崩溃取决于进程是否碰过 SQLite，与具体测试类无关，"
            f"逐类加注解必然漏（2026-10-13 ScanFeedbackTest 即是漏网的那个）。"
        )

    def test_properties_file_has_migration_rationale(self):
        """配置里的注释必须记录「为什么是 LEGACY」，否则后人会当成无用配置删掉。

        这不是文档洁癖：本文件正是被当成「多余的旧配置」而删掉过一次，
        代价是三连红。
        """
        text = PROPS.read_text(encoding="utf-8")
        assert "SIGBUS" in text and "SIGSEGV" in text, (
            f"{PROPS.name} 的注释须同时记录两条已确认的 native 崩溃路径"
            f"（SIGBUS / SIGSEGV）。缺了它，后来者无从判断能否删掉这个配置。"
        )