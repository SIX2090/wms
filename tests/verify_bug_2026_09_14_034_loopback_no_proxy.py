# -*- coding: utf-8 -*-
"""
BUG-2026-09-14-034 回归测试：本机回环 HTTP 调用绝不走系统/环境代理。

根因：
- 服务器为拉取 GitHub 代码常驻代理软件。代理开启"系统代理"后写入 Windows 注册表/
  环境变量，Python requests 默认读取并把发往 127.0.0.1 的回环请求也路由到代理监听
  端口（现场实测 10090）。代理无法处理回环目标 → 微信分享批量 HTTP 502、健康检查
  read timeout（截图：助手不可用 HTTPConnectionPool(host='127.0.0.1', port=10090)）。
- 受影响消费点（R6 全量排查）：
  WMS 侧 app.py `_wechat_share_send_image`（POST /send）、`_wechat_share_get_helper_health`（GET /health）；
  助手侧 wechat_helper.py `poll_once`（GET 任务 / GET 图片 / POST 回报 ×2）。

修复：
- 统一显式传 `proxies={'http': None, 'https': None}`（模块常量 `_LOOPBACK_NO_PROXY`）。
  requests 合并环境代理用 setdefault，显式 None 优先生效，`select_proxy` 返回 None → 直连本机，
  与代理开关状态无关；无需用户记得"不用就关代理"。

验收点：
T1. `_wechat_share_send_image` 调用 requests.post 时携带 proxies={'http': None, 'https': None}。
T2. `_wechat_share_get_helper_health` 调用 requests.get 时携带同样的 no-proxy。
T3. 机制证明：设置 HTTP(S)_PROXY 环境变量后，requests 合并代理+select_proxy 仍返回 None（直连）。
T4. 助手 wechat_helper.py 定义 _LOOPBACK_NO_PROXY 且 poll_once 的 4 处回环调用均带 proxies（静态断言，
    助手 Windows-only 无法 import，按仓库惯例做源码校验）。
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

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True

HELPER_SRC = (ROOT / "app" / "wechat_helper.py").read_text(encoding="utf-8")
NO_PROXY = {"http": None, "https": None}


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


class _SentResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"status": "sent", "code": "ok", "msg": "已发送"}


class _HealthResponse:
    ok = True
    status_code = 200

    def json(self):
        return {"status": "ok", "wechat_window_found": True}


class TestSendImageNoProxy:
    def test_t1_send_image_passes_no_proxy(self, tmp_path, monkeypatch):
        """T1：直推 /send 必须带 proxies={'http': None, 'https': None}。"""
        monkeypatch.setitem(app_module.app.config, "WECHAT_HELPER_TOKEN", "tok-034")
        captured = {}

        def fake_post(url, data=None, files=None, headers=None, timeout=None, proxies=None):
            captured["url"] = url
            captured["proxies"] = proxies
            return _SentResponse()

        monkeypatch.setattr("requests.post", fake_post)
        with app_module.app.app_context():
            status, code, _ = app_module._wechat_share_send_image(
                _make_config(), _make_image(tmp_path)
            )
        assert status == "sent"
        assert captured["url"] == "http://127.0.0.1:8765/send"
        assert captured["proxies"] == NO_PROXY, captured["proxies"]


class TestHealthNoProxy:
    def test_t2_health_passes_no_proxy(self, monkeypatch):
        """T2：健康检查 GET /health 必须带同样的 no-proxy。"""
        app_module._WECHAT_SHARE_HEALTH_CACHE.update({"url": "", "at": None, "health": None})
        captured = {}

        def fake_get(url, timeout=None, proxies=None):
            captured["url"] = url
            captured["proxies"] = proxies
            return _HealthResponse()

        monkeypatch.setattr("requests.get", fake_get)
        with app_module.app.app_context():
            health = app_module._wechat_share_get_helper_health(_make_config())
        assert health["online"] is True
        assert captured["url"] == "http://127.0.0.1:8765/health"
        assert captured["proxies"] == NO_PROXY, captured["proxies"]
        app_module._WECHAT_SHARE_HEALTH_CACHE.update({"url": "", "at": None, "health": None})


class TestMechanismProof:
    def test_t3_env_proxy_is_overridden_to_direct(self, monkeypatch):
        """T3：设置 HTTP(S)_PROXY 后，显式 proxies=None 仍让回环 URL 直连。

        用 requests 自身的 merge_environment_settings + select_proxy 证明：
        即便环境/系统代理存在，`_LOOPBACK_NO_PROXY` 也让 select_proxy 返回 None（不选中任何代理）。
        """
        import requests
        from requests.utils import select_proxy

        monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:10090")
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:10090")
        monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:10090")
        # 确保没有 no_proxy 把回环单独放行（否则测不出"覆盖代理"这一行为）
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)

        session = requests.Session()  # trust_env 默认 True，模拟线上 requests 默认行为
        url = "http://127.0.0.1:8765/send"

        # 对照：不传 no-proxy 时，环境代理确实会被选中（证明代理存在且会劫持回环）
        merged_default = session.merge_environment_settings(url, {}, False, None, None)["proxies"]
        assert select_proxy(url, merged_default) == "http://127.0.0.1:10090", merged_default

        # 修复：传 _LOOPBACK_NO_PROXY 时，select_proxy 返回 None → 直连
        merged_fixed = session.merge_environment_settings(
            url, dict(app_module._LOOPBACK_NO_PROXY), False, None, None
        )["proxies"]
        assert select_proxy(url, merged_fixed) is None, merged_fixed


class TestHelperSourceNoProxy:
    def test_t4_helper_poll_calls_bypass_proxy(self):
        """T4：助手定义 _LOOPBACK_NO_PROXY 且 poll_once 全部回环 requests 调用带 proxies。"""
        assert '_LOOPBACK_NO_PROXY = {"http": None, "https": None}' in HELPER_SRC
        count = HELPER_SRC.count("proxies=_LOOPBACK_NO_PROXY")
        # poll_once 内 4 处：GET tasks / GET image / POST report(成功) / POST report(失败)
        assert count >= 4, f"助手回环调用绕过代理至少 4 处，实际 {count} 处"
