# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-010 回归测试：WMS 侧结构化错误码映射 + 连接级安全重试。

根因：
- `_wechat_share_send_image` 只返回 (sent, message)，丢弃助手端的机器可读 code，
  WMS 侧只能靠 `_wechat_share_status_from_send_result` 关键词匹配猜测 failed/pending，
  新错误文案漏配关键词即误判为 pending，排障全靠读全文。
- 无任何重试：助手短暂重启窗口期（连接被拒绝）时一次失败即记 failed；
  但若对读超时也盲目重试，请求可能已被助手执行，会重复粘贴/发送。

修复：
- `_wechat_share_send_image` 返回 (status, code, message) 结构化三元组，
  status ∈ {sent, pending, failed} 直接落库，code 机器可读；
- 仅 ConnectionError（请求未到达助手、零副作用）自动重试 1 次；
  Timeout 不重试，防止重复发送。

验收点：
T1. 助手返回 error+code（focus_lost）→ failed 且 code 原样透传。
T2. 助手返回 ready → pending（待人工确认）。
T3. 首次 ConnectionError、第二次成功 → sent，且恰好请求 2 次（安全重试生效）。
T4. Timeout → failed(helper_timeout)，仅请求 1 次（禁止重试防重复发送）。
T5. HTTP 403 → failed(auth_failed)。
T6. 两次 ConnectionError → failed(helper_offline)，恰好请求 2 次。
T7. 未配置 helper_url → pending(helper_not_configured)，不发请求。
T8. 调用方 `_wechat_share_order` 落库 status 与错误码后缀。
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import requests  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False
app_module.app.config["WECHAT_HELPER_TOKEN"] = "test-helper-token-010"


def _make_config(**overrides):
    defaults = dict(
        helper_url="http://127.0.0.1:8765/send",
        sender_name="",
        sender_wechat_id="",
        receiver_name="张三",
        receiver_wechat_id="",
        receiver_search_key="张三",
        receiver_type="person",
        auto_send=False,
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


def _make_image(tmp_path):
    image_path = tmp_path / "share.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nfake-png-bytes")
    return str(image_path)


class _FakeResponse:
    def __init__(self, payload=None, status_code=200, ok=True):
        self._payload = payload or {}
        self.status_code = status_code
        self.ok = ok

    def json(self):
        return self._payload


def _send(config, image, monkeypatch, post_side_effect):
    calls = []

    def fake_post(url, data=None, files=None, headers=None, timeout=None):
        calls.append(url)
        result = post_side_effect(len(calls))
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr("requests.post", fake_post)
    with app_module.app.app_context():
        outcome = app_module._wechat_share_send_image(config, image)
    return outcome, calls


class TestStructuredCodeMapping:
    def test_t1_helper_error_code_passthrough(self, tmp_path, monkeypatch):
        """T1：助手 error+code 原样透传为 (failed, code, msg)。"""
        outcome, _ = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: _FakeResponse({"status": "error", "code": "focus_lost", "msg": "微信窗口不在前台"}),
        )
        status, code, msg = outcome
        assert status == "failed"
        assert code == "focus_lost"
        assert "前台" in msg

    def test_t2_helper_ready_maps_pending(self, tmp_path, monkeypatch):
        """T2：助手 ready（已粘贴待人工确认）→ pending。"""
        outcome, _ = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: _FakeResponse({"status": "ready", "code": "ok", "msg": "已粘贴到微信会话"}),
        )
        assert outcome[0] == "pending"
        assert outcome[1] == "ok"

    def test_t3_connection_error_retried_once(self, tmp_path, monkeypatch):
        """T3：首次连接失败、第二次成功 → sent，恰好 2 次请求。"""
        outcome, calls = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: (
                requests.exceptions.ConnectionError("connection refused")
                if n == 1
                else _FakeResponse({"status": "sent", "code": "ok", "msg": "已发送"})
            ),
        )
        assert outcome[0] == "sent"
        assert len(calls) == 2, f"应安全重试 1 次，实际请求 {len(calls)} 次"

    def test_t4_timeout_never_retried(self, tmp_path, monkeypatch):
        """T4：读超时不重试（请求可能已执行），仅 1 次请求。"""
        outcome, calls = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: requests.exceptions.ReadTimeout("read timed out"),
        )
        status, code, msg = outcome
        assert status == "failed"
        assert code == "helper_timeout"
        assert "人工" in msg
        assert len(calls) == 1, f"超时禁止自动重试，实际请求 {len(calls)} 次"

    def test_t5_http_403_auth_failed(self, tmp_path, monkeypatch):
        """T5：HTTP 403 → failed(auth_failed)。"""
        outcome, _ = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: _FakeResponse({"msg": "forbidden"}, status_code=403, ok=False),
        )
        assert outcome[0] == "failed"
        assert outcome[1] == "auth_failed"
        assert "token" in outcome[2].lower()

    def test_t6_persistent_connection_error_offline(self, tmp_path, monkeypatch):
        """T6：持续连接失败 → failed(helper_offline)，恰好 2 次请求。"""
        outcome, calls = _send(
            _make_config(), _make_image(tmp_path), monkeypatch,
            lambda n: requests.exceptions.ConnectionError("connection refused"),
        )
        assert outcome[0] == "failed"
        assert outcome[1] == "helper_offline"
        assert len(calls) == 2

    def test_t7_no_helper_url_pending_no_request(self, tmp_path, monkeypatch):
        """T7：未配置 helper_url → pending(helper_not_configured)，零请求。"""
        calls = []
        monkeypatch.setattr("requests.post", lambda *a, **kw: calls.append(a))
        with app_module.app.app_context():
            # 同时屏蔽环境变量兜底，模拟完全未配置
            old_env = os.environ.pop("WMS_WECHAT_HELPER_URL", None)
            try:
                outcome = app_module._wechat_share_send_image(
                    _make_config(helper_url=""), _make_image(tmp_path)
                )
            finally:
                if old_env is not None:
                    os.environ["WMS_WECHAT_HELPER_URL"] = old_env
        assert outcome[0] == "pending"
        assert outcome[1] == "helper_not_configured"
        assert calls == []

    def test_t8_share_order_persists_status_and_code(self, tmp_path, monkeypatch):
        """T8：_wechat_share_order 落库 status=failed 且 message 附错误码。"""
        monkeypatch.setattr(
            "requests.post",
            lambda *a, **kw: _FakeResponse(
                {"status": "error", "code": "focus_lost", "msg": "微信窗口不在前台"}
            ),
        )
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from app import InOrder, WechatShareConfig, WechatShareLog

            config = WechatShareConfig(
                sender_name="", sender_wechat_id="",
                receiver_name="张三", receiver_wechat_id="",
                receiver_search_key="张三", receiver_type="person",
                share_time="15:30", share_in_order=True,
                immediate_on_complete=False, enabled=True, auto_send=False,
                helper_url="http://127.0.0.1:8765/send",
            )
            db.session.add(config)
            import datetime as _dt
            order = InOrder(
                order_no="RK20260811001", warehouse="默认仓库",
                date=_dt.date.today(), status="completed", purpose="测试",
            )
            db.session.add(order)
            db.session.commit()

            monkeypatch.setattr(
                app_module, "_build_order_share_image",
                lambda o, k: (types.SimpleNamespace(getvalue=lambda: b"\x89PNG"), "x.png"),
            )
            monkeypatch.setattr(
                app_module, "_wechat_share_output_dir", lambda: str(tmp_path)
            )
            log, action = app_module._wechat_share_order(
                config, order, trigger_type="manual", force=False
            )
            db.session.commit()
            assert action == "created"
            assert log.status == "failed"
            assert "focus_lost" in log.message
            assert WechatShareLog.query.filter_by(order_no="RK20260811001").count() == 1
