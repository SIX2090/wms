# -*- coding: utf-8 -*-
"""
手机端语音指令 ASR 路由（POST /mobile/api/asr）回归测试。

覆盖：
T1. 端点注册（mobile_asr）。
T2. 未配置腾讯云密钥 -> 400。
T3. 未上传音频 -> 400。
T4. 不支持的音频格式 -> 400。
T5. 音频超限 -> 400。
T6. 未登录 / 无 Bearer -> 401。
T7. 成功：mock 腾讯云返回文本 -> 200 + text。
T8. 腾讯云报错 -> 502。
"""
from __future__ import annotations

import os
import sys
import unittest
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

import app as app_module  # noqa: E402
from app import ApiToken, User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

API_ENDPOINTS = ["mobile_asr"]

_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt \x00\x00\x00\x00\x00\x00\x00\x00data\x00\x00\x00\x00"


def _reset_db():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from werkzeug.security import generate_password_hash
        u = User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        )
        db.session.add(u)
        db.session.commit()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    r = client.post("/login", data={
        "username": "admin",
        "password": "admin",
        "login_mode": "user",
        "usage_consent": "1",
    })
    assert r.status_code in (200, 302), r.get_data(as_text=True)
    return {}


def _set_credentials():
    os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
    os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"


def _clear_credentials():
    os.environ.pop("TENCENTCLOUD_SECRET_ID", None)
    os.environ.pop("TENCENTCLOUD_SECRET_KEY", None)


def test_t1_endpoint_registered():
    from routes.mobile import register_mobile_routes
    import inspect
    src = inspect.getsource(register_mobile_routes)
    assert "/mobile/api/asr" in src
    assert "def mobile_asr" in src


def test_t2_missing_credentials_returns_400():
    _reset_db()
    _clear_credentials()
    client = _make_client()
    _login(client)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(_WAV), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "未配置腾讯云 ASR 密钥" in r.get_json()["msg"]


def test_t3_no_audio_returns_400():
    _reset_db()
    _set_credentials()
    client = _make_client()
    _login(client)
    r = client.post("/mobile/api/asr", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "请上传音频" in r.get_json()["msg"]


def test_t4_unsupported_format_returns_400():
    _reset_db()
    _set_credentials()
    client = _make_client()
    _login(client)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(b"x"), "cmd.exe")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "不支持的音频格式" in r.get_json()["msg"]


def test_t5_audio_too_large_returns_400():
    _reset_db()
    _set_credentials()
    client = _make_client()
    _login(client)
    big = b"0" * (11 * 1024 * 1024)
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(big), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400
    assert "不能超过" in r.get_json()["msg"]


def test_t6_unauthorized_returns_401():
    _reset_db()
    _set_credentials()
    client = _make_client()
    r = client.post(
        "/mobile/api/asr",
        data={"audio": (BytesIO(_WAV), "cmd.wav")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 401


def test_t7_success_returns_text():
    _reset_db()
    _set_credentials()
    client = _make_client()
    _login(client)
    with mock.patch("tencent_asr.sentence_recognition", return_value="入库") as m:
        r = client.post(
            "/mobile/api/asr",
            data={"audio": (BytesIO(_WAV), "cmd.wav")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["status"] == "success"
    assert payload["text"] == "入库"
    m.assert_called_once()


def test_t8_tencent_error_returns_502():
    _reset_db()
    _set_credentials()
    client = _make_client()
    _login(client)
    from tencent_asr import TencentAsrError
    with mock.patch(
        "tencent_asr.sentence_recognition",
        side_effect=TencentAsrError("腾讯云 ASR 错误 X: 参数错误"),
    ):
        r = client.post(
            "/mobile/api/asr",
            data={"audio": (BytesIO(_WAV), "cmd.wav")},
            content_type="multipart/form-data",
        )
    assert r.status_code == 502
    assert "腾讯云 ASR 错误" in r.get_json()["msg"]