#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进程内滑动窗口限流器（F2.2 / S3：登录失败单 IP 全局限流）。

设计取舍：
- **进程内**：WMS 以单进程多线程（waitress）运行，进程内计数足够；不引入 Redis 等
  新依赖做跨进程共享。
- **滑动窗口**：用 deque 保存窗口内事件时间戳，天然过期，避免固定窗口的边界突发。
- **标准库**：仅 threading + time + collections。
"""
from __future__ import annotations

import threading
import time
from collections import deque

_LOCK = threading.Lock()
_BUCKETS: "dict[str, deque]" = {}


def _prune(bucket: deque, cutoff: float) -> None:
    """丢弃窗口外（<= cutoff）的时间戳。"""
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()


def is_rate_limited(key: str, limit: int, window_seconds: float, now: float | None = None) -> bool:
    """当前窗口内该 key 的事件数是否已达上限（只读，不记录）。"""
    if limit <= 0:
        return False
    ts = time.monotonic() if now is None else now
    with _LOCK:
        bucket = _BUCKETS.get(key)
        if not bucket:
            return False
        _prune(bucket, ts - window_seconds)
        return len(bucket) >= limit


def record_failure(key: str, window_seconds: float, now: float | None = None) -> int:
    """记录一次事件，返回窗口内累计事件数。"""
    ts = time.monotonic() if now is None else now
    with _LOCK:
        bucket = _BUCKETS.setdefault(key, deque())
        _prune(bucket, ts - window_seconds)
        bucket.append(ts)
        return len(bucket)


def reset(key: str | None = None) -> None:
    """清空限流状态（测试 / 运维用）。"""
    with _LOCK:
        if key is None:
            _BUCKETS.clear()
        else:
            _BUCKETS.pop(key, None)
