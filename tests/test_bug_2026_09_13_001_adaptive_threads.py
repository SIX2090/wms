"""BUG-2026-09-13-001 回归：Waitress 线程数默认按 CPU 核数自适应。

修复前：run_server.py 写死默认 16 线程（os.environ.get("WMS_THREADS", "16")）。
2 vCPU / 2GB 低配云主机上，GIL 决定 16 线程不增吞吐，只增内存与切换开销。
修复后：默认 4 起步、每核 4、封顶 16；WMS_THREADS 显式设置时优先。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"
os.environ["WMS_SKIP_AUTO_UPDATE"] = "1"

import run_server  # noqa: E402


def test_default_threads_scales_with_cores(monkeypatch):
    """每核 4 线程：1 核→4（起步）、2 核→8、4 核→16。"""
    monkeypatch.setattr(os, "cpu_count", lambda: 1)
    assert run_server._default_waitress_threads() == 4
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert run_server._default_waitress_threads() == 8
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    assert run_server._default_waitress_threads() == 16


def test_default_threads_capped_at_16(monkeypatch):
    """封顶 16：8 核及以上不再增加，保持大核数机器既有行为。"""
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    assert run_server._default_waitress_threads() == 16
    monkeypatch.setattr(os, "cpu_count", lambda: 64)
    assert run_server._default_waitress_threads() == 16


def test_default_threads_handles_none_cpu_count(monkeypatch):
    """os.cpu_count() 返回 None（极少数平台）时按 1 核处理，不崩。"""
    monkeypatch.setattr(os, "cpu_count", lambda: None)
    assert run_server._default_waitress_threads() == 4


def test_env_override_wins(monkeypatch):
    """WMS_THREADS 显式设置时优先于自适应默认；含空白也能解析。"""
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert run_server._resolve_waitress_threads({"WMS_THREADS": "6"}) == 6
    assert run_server._resolve_waitress_threads({"WMS_THREADS": " 12 "}) == 12


def test_env_empty_falls_back_to_adaptive(monkeypatch):
    """未设置或空字符串都走自适应默认（空串不得抛 ValueError）。"""
    monkeypatch.setattr(os, "cpu_count", lambda: 2)
    assert run_server._resolve_waitress_threads({}) == 8
    assert run_server._resolve_waitress_threads({"WMS_THREADS": ""}) == 8
    assert run_server._resolve_waitress_threads({"WMS_THREADS": "   "}) == 8


def test_no_hardcoded_16_default_in_source():
    """反向断言：源码中不得再出现写死的 "16" 默认值（防回退）。"""
    src = (APP_DIR / "run_server.py").read_text(encoding="utf-8")
    assert 'os.environ.get("WMS_THREADS", "16")' not in src
    assert "os.environ.get('WMS_THREADS', '16')" not in src
    assert "_resolve_waitress_threads(os.environ)" in src
