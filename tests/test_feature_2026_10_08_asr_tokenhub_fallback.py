# -*- coding: utf-8 -*-
"""
FEATURE-2026-10-08-ASR 回归：语音识别回退 TokenHub 同步 ASR（wand-asr-v1）。

背景：腾讯云一句话识别是独立付费产品（无免费额度），生产机未配置
TENCENTCLOUD_SECRET_ID/KEY 时 /mobile/api/asr 直接 400 报错，App 语音功能全挂。
改造：无腾讯密钥时回退 TokenHub 同步 ASR（复用 LLM 网关同一把 API Key），
识别结果同样过 correct_voice_asr_text 领域词纠正兜底。

本文件覆盖：
  1. _asr_call_tokenhub 请求 payload 结构（model/data/source/voice_encode_format）；
  2. 端点推导（base_url -> origin + /v1/wand/asrproxy/sync_transcribe）；
  3. 错误处理（连接失败 / HTTP 错误 / 空 text / status 非 completed）；
  4. 路由回退接线（无腾讯密钥 -> 走 TokenHub，不再 400）；
  5. 回退结果同样应用领域词纠正（饮料 -> 领料）；
  6. 有腾讯密钥时行为不变（仍走 sentence_recognition，热词权重 100）。
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ["WMS_ALLOW_INSECURE_COOKIE"] = "1"

import app as app_module  # noqa: E402
from app import User, db, _asr_call_tokenhub, _asr_tokenhub_endpoint  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt \x00\x00\x00\x00\x00\x00\x00\x00data\x00\x00\x00\x00"


def _reset_db():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
        db.session.commit()


def _login(client):
    r = client.post("/login", data={
        "username": "admin", "password": "admin",
        "login_mode": "user", "usage_consent": "1",
    })
    assert r.status_code in (200, 302), r.get_data(as_text=True)


def _enable_llm(monkeypatch, base_url="https://tokenhub.example.com/v1", api_key="sk-test"):
    monkeypatch.setattr(app_module, "_ai_llm_enabled", lambda overrides=None: True)
    monkeypatch.setattr(app_module, "_ai_llm_api_key", lambda overrides=None: api_key)
    monkeypatch.setattr(app_module, "get_system_setting", lambda key, default="": (
        base_url if key == "ai_llm_base_url" else default))
    monkeypatch.setattr(app_module, "_ai_llm_headers", lambda overrides=None: {
        "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})


# ── 单元：端点推导 ──────────────────────────────────────────────

def test_tokenhub_endpoint_from_base_url(monkeypatch):
    monkeypatch.setattr(app_module, "get_system_setting", lambda key, default="":
                        "https://tokenhub.example.com/v1" if key == "ai_llm_base_url" else default)
    monkeypatch.setattr(app_module.app.config, "get",
                        lambda k, d=None: None)
    assert _asr_tokenhub_endpoint() == \
        "https://tokenhub.example.com/v1/wand/asrproxy/sync_transcribe"


def test_tokenhub_endpoint_empty_when_no_base_url(monkeypatch):
    monkeypatch.setattr(app_module, "get_system_setting", lambda key, default="": "")
    assert _asr_tokenhub_endpoint() == ""


def test_tokenhub_endpoint_with_chat_completions_suffix(monkeypatch):
    monkeypatch.setattr(app_module, "get_system_setting", lambda key, default="":
                        "http://10.0.0.1:7863/v1/chat/completions" if key == "ai_llm_base_url" else default)
    assert _asr_tokenhub_endpoint() == \
        "http://10.0.0.1:7863/v1/wand/asrproxy/sync_transcribe"


# ── 单元：_asr_call_tokenhub payload 与错误处理 ────────────────

class _Resp:
    def __init__(self, ok=True, status_code=200, json_data=None, text=""):
        self.ok = ok
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_asr_call_tokenhub_payload_structure(monkeypatch):
    _enable_llm(monkeypatch)
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return _Resp(json_data={"status": "completed",
                                "output": {"text": "入库 10 个"}})

    monkeypatch.setattr(app_module.requests, "post", fake_post)
    text, err = _asr_call_tokenhub(_WAV, voice_format="wav")
    assert err == ""
    assert text == "入库 10 个"
    assert captured["url"] == "https://tokenhub.example.com/v1/wand/asrproxy/sync_transcribe"
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    payload = captured["json"]
    assert payload["model"] == "wand-asr-v1"
    assert payload["source"] == "zh"
    assert payload["voice_encode_format"] == "wav"
    import base64 as _b64
    assert payload["data"] == _b64.b64encode(_WAV).decode("ascii")
    assert captured["timeout"] >= 60


def test_asr_call_tokenhub_llm_not_configured(monkeypatch):
    monkeypatch.setattr(app_module, "_ai_llm_enabled", lambda overrides=None: True)
    monkeypatch.setattr(app_module, "_ai_llm_api_key", lambda overrides=None: "")
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "API Key" in err


def test_asr_call_tokenhub_connection_error(monkeypatch):
    _enable_llm(monkeypatch)
    import requests as _rq
    monkeypatch.setattr(app_module.requests, "post",
                        mock.Mock(side_effect=_rq.RequestException("boom")))
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "连接失败" in err


def test_asr_call_tokenhub_http_error(monkeypatch):
    _enable_llm(monkeypatch)
    resp = _Resp(ok=False, status_code=401, json_data={
        "error": {"message": "Invalid API key", "code": "401"}})
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "语音识别服务返回错误" in err


def test_asr_call_tokenhub_empty_text(monkeypatch):
    _enable_llm(monkeypatch)
    resp = _Resp(json_data={"status": "completed", "output": {"text": ""}})
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "未识别到语音内容" in err


def test_asr_call_tokenhub_bad_json(monkeypatch):
    _enable_llm(monkeypatch)
    resp = _Resp(json_data=None, text="not json")
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "响应格式异常" in err


def test_asr_call_tokenhub_unfinished_status(monkeypatch):
    _enable_llm(monkeypatch)
    resp = _Resp(json_data={"status": "failed", "error": {"message": "audio too short"}})
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    text, err = _asr_call_tokenhub(_WAV)
    assert text is None
    assert "status=failed" in err


# ── 路由：回退接线 ─────────────────────────────────────────────

def test_asr_route_fallback_without_tencent_keys(monkeypatch):
    """无腾讯密钥时不再 400，改走 TokenHub ASR。"""
    os.environ.pop("TENCENTCLOUD_SECRET_ID", None)
    os.environ.pop("TENCENTCLOUD_SECRET_KEY", None)
    _reset_db()
    _enable_llm(monkeypatch)
    resp = _Resp(json_data={"status": "completed",
                            "output": {"text": "入库 10 个"}})
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    client = app_module.app.test_client()
    _login(client)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(_WAV), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, (r.status_code, r.get_data(as_text=True))
    payload = r.get_json()
    assert payload["status"] == "success"
    assert payload["text"] == "入库 10 个"


def test_asr_route_fallback_applies_domain_correction(monkeypatch):
    """回退识别结果同样过领域词纠正：饮料 -> 领料。"""
    os.environ.pop("TENCENTCLOUD_SECRET_ID", None)
    os.environ.pop("TENCENTCLOUD_SECRET_KEY", None)
    _reset_db()
    _enable_llm(monkeypatch)
    resp = _Resp(json_data={"status": "completed",
                            "output": {"text": "饮料五个"}})
    monkeypatch.setattr(app_module.requests, "post", mock.Mock(return_value=resp))
    client = app_module.app.test_client()
    _login(client)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(_WAV), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    assert r.get_json()["text"] == "领料五个"


def test_asr_route_fallback_error_returns_502(monkeypatch):
    """回退链路失败返回 502 + 可读 msg，不再笼统 400。"""
    os.environ.pop("TENCENTCLOUD_SECRET_ID", None)
    os.environ.pop("TENCENTCLOUD_SECRET_KEY", None)
    _reset_db()
    _enable_llm(monkeypatch)
    monkeypatch.setattr(app_module, "_asr_call_tokenhub",
                        lambda audio, voice_format="wav": (None, "未识别到语音内容"))
    client = app_module.app.test_client()
    _login(client)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(_WAV), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 502
    assert "未识别到语音内容" in r.get_json()["msg"]


def test_asr_route_tencent_still_preferred_when_configured(monkeypatch):
    """有腾讯密钥时行为不变：仍走 sentence_recognition + 热词。"""
    os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
    os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
    try:
        _reset_db()
        client = app_module.app.test_client()
        _login(client)
        with mock.patch("tencent_asr.sentence_recognition", return_value="入库") as m:
            r = client.post(
                "/mobile/api/asr",
                data={"audio": (BytesIO(_WAV), "cmd.wav")},
                content_type="multipart/form-data",
            )
        assert r.status_code == 200
        m.assert_called_once()
        assert "入库|100" in m.call_args.kwargs["hotword_list"]
    finally:
        os.environ.pop("TENCENTCLOUD_SECRET_ID", None)
        os.environ.pop("TENCENTCLOUD_SECRET_KEY", None)
