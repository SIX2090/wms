# -*- coding: utf-8 -*-
"""F2.2 / S3 回归：进程内滑动窗口限流器（app/rate_limit.py）。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import rate_limit  # noqa: E402


def setup_function(_func):
    rate_limit.reset()


def test_is_rate_limited():
    """未达阈值不限流。"""
    k = "ip:1.2.3.4"
    assert not rate_limit.is_rate_limited(k, 3, 60, now=100.0)


def test_record_failure():
    """每次记录累加，返回窗口内累计数。"""
    k = "ip:1.2.3.4"
    for i in range(3):
        n = rate_limit.record_failure(k, 60, now=100.0 + i)
    assert n == 3


def test_is_rate_limited_after_threshold():
    k = "ip:1.2.3.4"
    for i in range(3):
        rate_limit.record_failure(k, 60, now=100.0 + i)
    assert rate_limit.is_rate_limited(k, 3, 60, now=103.0)


def test_window_slides_and_expires():
    k = "ip:5.6.7.8"
    for _ in range(3):
        rate_limit.record_failure(k, 60, now=0.0)
    assert rate_limit.is_rate_limited(k, 3, 60, now=10.0)
    # 窗口外事件被清理 → 不再限流
    assert not rate_limit.is_rate_limited(k, 3, 60, now=61.0)


def test_limit_zero_disables():
    k = "ip:9.9.9.9"
    for _ in range(100):
        rate_limit.record_failure(k, 60, now=0.0)
    assert not rate_limit.is_rate_limited(k, 0, 60, now=0.0)


def test_reset():
    k = "ip:reset"
    rate_limit.record_failure(k, 60, now=0.0)
    rate_limit.reset(k)
    assert not rate_limit.is_rate_limited(k, 1, 60, now=0.0)
