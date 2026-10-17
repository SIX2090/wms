# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F03：AI 端点为明文公网 HTTP 时必须告警。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as wms  # noqa: E402


def test_plaintext_remote_detection():
    f = wms._ai_llm_url_is_plaintext_remote
    assert f('http://81.71.29.219:7863/v1') is True
    assert f('http://api.example.com/v1') is True
    assert f('https://api.example.com/v1') is False
    assert f('http://127.0.0.1:7863/v1') is False
    assert f('http://localhost:7863/v1') is False
    assert f('') is False
    assert f(None) is False


def test_warning_is_wired_in_endpoint_builder():
    source = (APP / 'app.py').read_text(encoding='utf-8')
    assert '[SECURITY] AI LLM endpoint uses plaintext HTTP' in source
    assert 'def _ai_llm_url_is_plaintext_remote(' in source
