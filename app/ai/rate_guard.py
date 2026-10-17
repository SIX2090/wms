# -*- coding: utf-8 -*-
"""AI 对话端点的轻量速率限制（BUG-2026-10-17-011-F09）。

审计 Q8：/api/ai/chat/stream 与 /warehouse_assistant 没有每分钟上限，
一次前端重试循环就能持续消耗 LLM 配额。本模块是进程内滑动窗口：
单机/单用户部署足够；多 worker 时每个进程独立计数（保守方向）。
"""
from __future__ import annotations

import threading
import time
from collections import deque

_LOCK = threading.Lock()
_BUCKETS: dict[str, deque[float]] = {}

DEFAULT_LIMIT = 20
DEFAULT_WINDOW_SECONDS = 60


def allow(key: str, limit: int = DEFAULT_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> tuple[bool, int]:
    """返回 (是否放行, 建议重试秒数)。"""
    now = time.monotonic()
    with _LOCK:
        bucket = _BUCKETS.setdefault(key, deque())
        while bucket and now - bucket[0] >= window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = max(1, int(window_seconds - (now - bucket[0])))
            return False, retry
        bucket.append(now)
        return True, 0


def reset() -> None:
    with _LOCK:
        _BUCKETS.clear()
