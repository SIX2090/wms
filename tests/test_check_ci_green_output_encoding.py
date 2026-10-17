# -*- coding: utf-8 -*-
"""BUG-2026-10-17-006 回归锁：`check_ci_green.py` 在非 UTF-8 控制台不得崩溃。

背景：AGENTS.md §三 把 `python scripts/check_ci_green.py` 列为**开工前置门禁**的
推荐检查方式，但脚本用 ✅/❌/🚫 等 emoji 直接 print。中文 Windows 控制台默认
cp936（GBK）编码不了这些字符，`print` 抛 UnicodeEncodeError —— 生产平台的
默认控制台上，这条门禁命令**一条输出都打不出来就直接 traceback 退出**。

修复口径：按 stdout 的编码能力自动降级为 ASCII 标记（`[OK]` / `[FAIL]` …），
并在输出前把 stdout 的 errors 设为 `replace` 兜底；UTF-8 环境（Linux CI）仍保留 emoji。

本文件是回退验证的载体：把 `icons()`/`marks()` 降级逻辑去掉后，
`test_gbk_console_reports_green_without_crash` 会以 UnicodeEncodeError 失败。
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_ci_green.py"

_spec = importlib.util.spec_from_file_location("check_ci_green_under_test", SCRIPT)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def _run(monkeypatch, encoding: str, conclusion: str = "success"):
    """用指定编码的 stdout 跑一次 main()，返回 (rc, 输出文本)。"""
    buf = io.BytesIO()
    stream = io.TextIOWrapper(buf, encoding=encoding, newline="\n")

    def fake_latest_run(workflow_file, token):
        return {
            "status": "completed",
            "conclusion": conclusion,
            "run_number": 42,
            "head_sha": "0123456789abcdef0123",
            "created_at": "2026-10-17T00:00:00Z",
            "html_url": "https://example.invalid/run/42",
        }

    monkeypatch.setattr(sys, "stdout", stream)
    monkeypatch.setattr(sys, "argv", ["check_ci_green.py"])
    monkeypatch.setattr(gate, "resolve_token", lambda: None)
    monkeypatch.setattr(gate, "latest_run", fake_latest_run)

    rc = gate.main()
    stream.flush()
    return rc, buf.getvalue().decode(encoding)


def test_gbk_console_reports_green_without_crash(monkeypatch):
    """复现现场：cp936 控制台下必须正常输出并放行，而不是 UnicodeEncodeError。"""
    rc, text = _run(monkeypatch, "gbk")
    assert rc == 0
    assert "[OK]" in text
    assert "允许开工" in text
    # 降级后不应残留任何无法被 gbk 表示的字符
    assert "\u2705" not in text


def test_gbk_console_reports_blocked_without_crash(monkeypatch):
    """阻断路径同样不得崩：非绿时给 ASCII 标记 + rc=1。"""
    rc, text = _run(monkeypatch, "gbk", conclusion="failure")
    assert rc == 1
    assert "[FAIL]" in text
    assert "[BLOCKED]" in text
    assert "门禁阻断" in text


def test_utf8_console_keeps_emoji(monkeypatch):
    """反向保护：Linux CI 的 UTF-8 输出保持原样，避免过度降级成纯 ASCII。"""
    rc, text = _run(monkeypatch, "utf-8")
    assert rc == 0
    assert "✅" in text
    assert "[OK]" not in text


def test_can_encode_detects_unsupported_chars():
    """探测函数本身的契约：不可编码 → False；未知编码 → False（不抛异常）。"""
    assert gate.can_encode("abc", "gbk") is True
    assert gate.can_encode("✅", "gbk") is False
    assert gate.can_encode("✅", "no-such-codec") is False
