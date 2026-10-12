# -*- coding: utf-8 -*-
"""F3.14：vision 通道阻塞缓解（审计 §7.6）。

契约：
- 地板超时 60s→30s：call_llm 收到的 timeout_override >= 30 且 < 60；
- 请求级信号量并发上限 2：第 3 个并发 vision 调用快速失败（不排队），
  返回 VISION_BUSY_MSG；信号量释放后可再次进入。
"""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, 'app')
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from ai import providers  # noqa: E402


def _vision_config():
    return providers.OpenAICompatibleConfig(
        enabled=True,
        endpoint='https://example.invalid/v1',
        model='glm-5v-test',
        api_key='sk-test',
        timeout_seconds=5,
        max_tokens=1024,
        vision_enabled=True,
    )


def test_vision_floor_timeout_is_30(monkeypatch):
    """拍板 #7①：timeout_override 地板由 60 降为 30。"""
    seen = {}

    def fake_call_llm(config, messages, **kwargs):
        seen.update(kwargs)
        return 'ok'

    monkeypatch.setattr(providers, 'call_llm', fake_call_llm)
    reply, _, err = providers.call_llm_vision(_vision_config(), 'sys', [])
    assert err is None and reply == 'ok'
    assert seen['timeout_override'] == 30
    assert seen['mode'] == 'vision'


def test_vision_semaphore_rejects_third_concurrent(monkeypatch):
    """拍板 #7②：并发上限 2，第 3 个快速失败且不误吞信号量。"""
    entered = threading.Event()
    release = threading.Event()

    def slow_call_llm(config, messages, **kwargs):
        entered.set()
        release.wait(timeout=5)
        return 'ok'

    monkeypatch.setattr(providers, 'call_llm', slow_call_llm)

    results = []

    def worker():
        results.append(providers.call_llm_vision(_vision_config(), 'sys', []))

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    assert entered.wait(timeout=5)
    time.sleep(0.2)  # 确保两个线程都已进入临界区

    # 第 3 个并发：快速失败，返回繁忙提示
    reply, extracted, err = providers.call_llm_vision(_vision_config(), 'sys', [])
    assert reply is None and extracted is None
    assert err == providers.VISION_BUSY_MSG

    release.set()
    t1.join(timeout=10)
    t2.join(timeout=10)
    assert all(r[0] == 'ok' for r in results), results

    # 信号量已归还：后续调用可正常进入
    monkeypatch.setattr(providers, 'call_llm', lambda *a, **k: 'ok')
    reply, _, err = providers.call_llm_vision(_vision_config(), 'sys', [])
    assert reply == 'ok' and err is None
