# -*- coding: utf-8 -*-
"""BUG-2026-08-16-019 回归：敏感配置（API Key）加密存储。

根因：SystemSetting 以明文存储 ai_llm_api_key，数据库泄露即告钥泄露。

修复：新增 _secret_encrypt/_secret_decrypt（Fernet 对称加密，密钥由 SECRET_KEY
派生），保存时加密落库（enc: 前缀），读取时解密；历史明文值向后兼容原样返回。

回归：round-trip 一致；落库非明文；_ai_llm_api_key 读回明文；历史明文可读。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import SystemSetting, _ai_llm_api_key, _secret_decrypt, _secret_encrypt, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False
app_module.app.config["SECRET_KEY"] = "test-secret-key-for-bug-019-encryption"


def _reset_db():
    db.drop_all()
    db.create_all()


def test_secret_roundtrip():
    with app_module.app.app_context():
        _reset_db()
        plain = "sk-abcdef1234567890"
        token = _secret_encrypt(plain)
        assert token.startswith("enc:")
        assert plain not in token
        assert _secret_decrypt(token) == plain


def test_secret_encrypt_empty_returns_empty():
    with app_module.app.app_context():
        _reset_db()
        assert _secret_encrypt("") == ""
        assert _secret_decrypt("") == ""


def test_secret_decrypt_legacy_plaintext_backward_compat():
    with app_module.app.app_context():
        _reset_db()
        legacy = "sk-legacy-plaintext-key"
        assert _secret_decrypt(legacy) == legacy


def test_secret_decrypt_wrong_key_returns_empty():
    with app_module.app.app_context():
        _reset_db()
        token = _secret_encrypt("sk-secret")
        app_module.app.config["SECRET_KEY"] = "a-different-key"
        try:
            assert _secret_decrypt(token) == ""
        finally:
            app_module.app.config["SECRET_KEY"] = "test-secret-key-for-bug-019-encryption"


def test_ai_llm_api_key_reads_decrypted_and_env_fallback():
    with app_module.app.app_context():
        _reset_db()
        # 1) 落库密文后读取还原明文
        token = _secret_encrypt("sk-persisted-key")
        db.session.add(SystemSetting(key="ai_llm_api_key", value=token))
        db.session.commit()
        assert _ai_llm_api_key() == "sk-persisted-key"
        # 2) 无持久化值时回退环境变量
        db.session.query(SystemSetting).filter_by(key="ai_llm_api_key").delete()
        db.session.commit()
        app_module.app.config["WMS_LLM_API_KEY"] = "sk-env-key"
        try:
            assert _ai_llm_api_key() == "sk-env-key"
        finally:
            app_module.app.config.pop("WMS_LLM_API_KEY", None)