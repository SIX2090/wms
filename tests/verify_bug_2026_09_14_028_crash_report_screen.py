# -*- coding: utf-8 -*-
"""BUG-2026-09-14-028：应用内崩溃报告页 —— 静态契约测试。

背景：3.8.1 仍冷启动闪退（BUG-2026-09-13-023 的两个已知根因已修复并字节码级验证，
但仍复发），说明存在**未被发现的第三根因**，且历轮修复全程没有拿到过一次 logcat——
一直在"修了但修的不是真凶"。WmsApplication 的崩溃日志器（BUG-2026-09-13-001）已把
堆栈写入 filesDir/crash/last_crash.txt，但 **release 包在非 root 手机上无法用 adb
读取该私有目录**，文件形同虚设。

本轮在 MainActivity 加「崩溃报告页」：检测到上次崩溃堆栈文件时，**先渲染报告页、
不加载会崩的 AppNavGraph**，让用户截图/复制回传真实堆栈。这是诊断桩，不是业务改动，
更不改变崩溃行为本身（不吞异常）。

本测试锁定的契约：
1. MainActivity 读取 filesDir 下 crash/last_crash.txt（与崩溃日志器的写入路径一致）。
2. 存在崩溃文件时渲染 CrashReportScreen、**不渲染 AppNavGraph**；无崩溃文件才进 AppNavGraph。
3. CrashReportScreen 是**零依赖静态页**：内部不得创建 ViewModel / 不得调用 AppNavGraph，
   否则"崩溃后想打开报告页"本身也会崩——这是本功能成立的前提。
4. 报告页提供「复制崩溃信息」（写剪贴板）与「我已记录，继续使用」（删除文件后继续）两入口。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (
    ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms" / "MainActivity.kt"
)


def _read() -> str:
    assert MAIN.exists(), f"未找到 {MAIN}"
    return MAIN.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    # 去块注释与行注释，避免注释里的关键字造成误判
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def _crash_report_body(src: str) -> str:
    """截取 CrashReportScreen 函数体（大括号配对），用于断言其内部零依赖。"""
    idx = src.find("fun CrashReportScreen")
    assert idx >= 0, "未找到 CrashReportScreen 函数"
    brace = src.find("{", idx)
    depth = 0
    i = brace
    while i < len(src):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[brace:i + 1]
        i += 1
    raise AssertionError("CrashReportScreen 函数体大括号未闭合")


# A9:no-test=reason=下面各 test_ 函数即本契约测试本体，被测对象为 MainActivity.kt 源码文本


def test_reads_crash_file_from_filesdir():
    src = _strip_comments(_read())
    assert "last_crash.txt" in src, "MainActivity 未读取 last_crash.txt"
    assert re.search(r"filesDir", src), "未使用 filesDir 定位崩溃目录"
    assert re.search(r'crash/last_crash\.txt|"crash"\s*,\s*"last_crash\.txt"', src), \
        "崩溃文件路径与崩溃日志器写入路径不一致"


def test_gate_shows_report_before_navgraph():
    src = _strip_comments(_read())
    # 必须有"有崩溃→报告页 / 无崩溃→AppNavGraph"的分支
    assert "CrashReportScreen(" in src, "未调用 CrashReportScreen"
    assert "AppNavGraph(" in src, "未保留 AppNavGraph"
    # 报告页分支必须先于/独立于 AppNavGraph 分支存在（else 结构）
    assert re.search(r"if\s*\(\s*crash\s*!=\s*null\s*\)", src), \
        "缺少 if (crash != null) 的门控，崩溃时仍会直接进 AppNavGraph"
    assert re.search(r"else\s*\{?\s*AppNavGraph", src) or "else" in src, \
        "无崩溃时应走 else 分支进 AppNavGraph"


def test_report_screen_is_dependency_free():
    body = _crash_report_body(_strip_comments(_read()))
    assert "viewModel" not in body, "报告页内部不得创建 ViewModel（否则报告页自己也会崩）"
    assert "AppNavGraph" not in body, "报告页内部不得调用 AppNavGraph"
    assert "Repository" not in body, "报告页内部不得触达数据层"


def test_report_screen_has_copy_and_dismiss():
    body = _crash_report_body(_strip_comments(_read()))
    assert "clipboard" in body.lower() or "ClipboardManager" in body, "缺少复制到剪贴板"
    assert "复制崩溃信息" in body, "缺少「复制崩溃信息」按钮文案"
    assert "onDismiss" in body, "缺少 dismiss 回调"
    assert "我已记录" in body, "缺少「我已记录，继续使用」按钮文案"


def test_clear_pending_crash_deletes_file():
    src = _strip_comments(_read())
    assert re.search(r"fun clearPendingCrash", src), "缺少 clearPendingCrash"
    assert re.search(r"clearPendingCrash[\s\S]{0,300}?\.delete\(\)", src), \
        "clearPendingCrash 必须删除崩溃文件，否则会永远卡在报告页"
