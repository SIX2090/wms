# -*- coding: utf-8 -*-
"""
WECOM-BOT-001 回归测试：微信分享接入「企业微信群机器人」通道。

背景：
- 本机助手 UI 自动化有"窗口必须常开+不能切窗口"的结构性限制；企业微信群机器人
  webhook（POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXX）以
  image(base64+md5) 原生图直发，摆脱该限制且图片不过第三方图床。
- 配置存 system_setting['wechat_share_wecom_webhook']（免迁移）；调度器
  `_wechat_share_deliver`：配 webhook→企业微信，否则回退本机助手（向后兼容）。

验收点：
T1. 调度器：配 webhook 走 wecom，未配走 helper。
T2. `_wechat_share_send_wecom`：image 载荷含正确 base64+md5、proxies 直连；errcode 0→sent、非 0→failed(wecom_<errcode>)。
T3. 图片超 `_WECOM_IMAGE_MAX_BYTES` 触发 Pillow 重编码（产出 JPEG）。
T4. webhook 白名单：qyapi https send 通过；http/外网/错路径/空 拒绝。
T5. caption markdown 先于 image 发送。
"""
from __future__ import annotations

import hashlib
import io
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

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True

WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=testkey"


def _make_png(tmp_path, size=(40, 40)):
    from PIL import Image
    path = tmp_path / "share.png"
    Image.new("RGB", size, (200, 30, 30)).save(path, "PNG")
    return str(path)


class _Resp:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class TestDispatcher:
    def test_t1_routes_to_wecom_when_configured(self, monkeypatch):
        calls = {}

        def fake_wecom(w, p, caption=""):
            calls["wecom"] = (w, caption)
            return ("sent", "ok", "ok")

        def fake_helper(c, p):
            calls["helper"] = True
            return ("sent", "ok", "ok")

        monkeypatch.setattr(app_module, "_wechat_share_wecom_webhook", lambda: WEBHOOK)
        monkeypatch.setattr(app_module, "_wechat_share_send_wecom", fake_wecom)
        monkeypatch.setattr(app_module, "_wechat_share_send_image", fake_helper)
        outcome = app_module._wechat_share_deliver(types.SimpleNamespace(), "/tmp/x.png", caption="c")
        assert outcome[0] == "sent"
        assert "wecom" in calls and "helper" not in calls
        assert calls["wecom"] == (WEBHOOK, "c")

    def test_t1b_falls_back_to_helper_when_not_configured(self, monkeypatch):
        calls = {}

        def fake_wecom(w, p, caption=""):
            calls["wecom"] = True
            return ("sent", "ok", "ok")

        def fake_helper(c, p):
            calls["helper"] = True
            return ("sent", "ok", "ok")

        monkeypatch.setattr(app_module, "_wechat_share_wecom_webhook", lambda: "")
        monkeypatch.setattr(app_module, "_wechat_share_send_wecom", fake_wecom)
        monkeypatch.setattr(app_module, "_wechat_share_send_image", fake_helper)
        outcome = app_module._wechat_share_deliver(types.SimpleNamespace(), "/tmp/x.png")
        assert outcome[0] == "sent"
        assert "helper" in calls and "wecom" not in calls


class TestSendWecom:
    def _run(self, tmp_path, monkeypatch, resp_payload, caption=""):
        captured = []

        def fake_post(url, json=None, timeout=None, proxies=None):
            captured.append({"url": url, "json": json, "proxies": proxies})
            return _Resp(resp_payload)

        monkeypatch.setattr("requests.post", fake_post)
        image = _make_png(tmp_path)
        with app_module.app.app_context():
            outcome = app_module._wechat_share_send_wecom(WEBHOOK, image, caption=caption)
        return outcome, captured, image

    def test_t2_image_payload_and_success(self, tmp_path, monkeypatch):
        outcome, captured, image = self._run(tmp_path, monkeypatch, {"errcode": 0, "errmsg": "ok"})
        assert outcome == ("sent", "ok", "已推送到企业微信群")
        assert len(captured) == 1
        call = captured[0]
        assert call["url"] == WEBHOOK
        assert call["proxies"] == {"http": None, "https": None}, "必须直连不走系统/环境代理"
        body = call["json"]
        assert body["msgtype"] == "image"
        expected_md5 = hashlib.md5(open(image, "rb").read()).hexdigest()
        assert body["image"]["md5"] == expected_md5
        assert body["image"]["base64"], "base64 不能为空"

    def test_t2b_errcode_maps_to_failed(self, tmp_path, monkeypatch):
        outcome, _, _ = self._run(tmp_path, monkeypatch, {"errcode": 93000, "errmsg": "invalid webhook"})
        assert outcome[0] == "failed"
        assert outcome[1] == "wecom_93000"
        assert "invalid webhook" in outcome[2]

    def test_t2c_invalid_webhook_rejected_before_request(self, tmp_path, monkeypatch):
        calls = []
        monkeypatch.setattr("requests.post", lambda *a, **kw: calls.append(a))
        image = _make_png(tmp_path)
        with app_module.app.app_context():
            outcome = app_module._wechat_share_send_wecom("https://evil.example.com/hook", image)
        assert outcome[0] == "failed"
        assert outcome[1] == "invalid_wecom_webhook"
        assert calls == [], "非法 webhook 不得发起 HTTP 请求"


class TestImageReencode:
    def test_t3_oversize_triggers_jpeg_reencode(self, tmp_path, monkeypatch):
        image = _make_png(tmp_path, size=(60, 60))
        raw = open(image, "rb").read()
        monkeypatch.setattr(app_module, "_WECOM_IMAGE_MAX_BYTES", 100)  # 强制触发重编码
        data = app_module._wechat_share_wecom_image_bytes(image)
        assert len(raw) > 100, "前提：原图需超过阈值"
        assert data[:2] == b"\xff\xd8", "超限应重编码为 JPEG（FFD8 魔数）"


class TestWebhookWhitelist:
    def test_t4_whitelist(self):
        ok = app_module._wechat_share_wecom_webhook_allowed
        assert ok("https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc") is True
        assert ok("https://qyapi.weixin.qq.com/cgi-bin/webhook/send") is True
        assert ok("https://qyapi.weixin.qq.com/cgi-bin/webhook/send/") is True
        assert ok("http://qyapi.weixin.qq.com/cgi-bin/webhook/send") is False, "必须 https"
        assert ok("https://evil.example.com/cgi-bin/webhook/send") is False, "主机必须是 qyapi"
        assert ok("https://qyapi.weixin.qq.com/cgi-bin/webhook/other") is False, "路径必须固定"
        assert ok("") is False
        assert ok(None) is False


class TestCaptionOrdering:
    def test_t5_caption_markdown_sent_before_image(self, tmp_path, monkeypatch):
        outcome, captured, _ = TestSendWecom()._run(
            tmp_path, monkeypatch, {"errcode": 0, "errmsg": "ok"}, caption="**入库单 IN001**"
        )
        assert outcome[0] == "sent"
        assert len(captured) == 2, "caption + image 共 2 条"
        assert captured[0]["json"]["msgtype"] == "markdown"
        assert captured[0]["json"]["markdown"]["content"] == "**入库单 IN001**"
        assert captured[1]["json"]["msgtype"] == "image"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
