# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F09：AI 对话端点进程内限流。"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ai import rate_guard  # noqa: E402


def setup_function():
    rate_guard.reset()


def test_limit_blocks_after_threshold():
    assert rate_guard.allow('u1', limit=2, window_seconds=60)[0] is True
    assert rate_guard.allow('u1', limit=2, window_seconds=60)[0] is True
    ok, retry = rate_guard.allow('u1', limit=2, window_seconds=60)
    assert ok is False
    assert retry >= 1


def test_keys_are_isolated():
    rate_guard.allow('a', limit=1, window_seconds=60)
    assert rate_guard.allow('b', limit=1, window_seconds=60)[0] is True


def test_window_expiry_allows_again():
    rate_guard.allow('c', limit=1, window_seconds=1)
    assert rate_guard.allow('c', limit=1, window_seconds=1)[0] is False
    time.sleep(1.05)
    assert rate_guard.allow('c', limit=1, window_seconds=1)[0] is True
