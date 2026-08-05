# -*- coding: utf-8 -*-
"""BUG-2026-08-05-005 回归：AJAX JSON POST 的 5xx 必须返回 JSON，且错误处理器自身不能再抛错。

背景：前端 csrfFetch/postJsonForAction 发 JSON POST 时只带
``Content-Type: application/json``（浏览器 fetch 默认 ``Accept: */*``、不带
``X-Requested-With``）。旧版 ``wants_json_error_response()`` 漏判这类请求，
视图一旦抛异常，``handle_exception`` 返回英文纯文本 "Internal Server Error"，
前端 ``r.json()`` 抛 ``Unexpected token 'I', "Internal S"... is not valid JSON"``，
真实错误原因完全丢失（物料删除等批量操作受影响）。

验收点：
T1. JSON POST（无 X-Requested-With、Accept=*/*）触发 500 时返回 JSON 错误体。
T2. 500/CSRF 错误处理器内 db.session.rollback 失败时，仍返回 JSON/文本响应，
    异常不得逃出错误处理器（否则 waitress 兜底返回英文纯文本 500）。
T3. CSRF 校验失败的 JSON POST 返回 JSON 400 而非重定向/纯文本。
"""
from __future__ import annotations

import os
import sys
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
from app import db  # noqa: E402

# 必须关闭 TESTING，否则异常直接传播给测试客户端，走不到错误处理器
app_module.app.config["TESTING"] = False
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _register_raising_route():
    """注册一个必抛异常的测试路由（仅测试用，不经 login/CSRF 拦截）。"""
    if "__test_raise_500" in app_module.app.view_functions:
        return

    @app_module.app.route("/__test_raise_500", methods=["POST"])
    @app_module.csrf.exempt
    def __test_raise_500():
        raise RuntimeError("boom")


_register_raising_route()


def _client():
    return app_module.app.test_client()


class TestJsonErrorResponse:
    def test_500_returns_json_for_json_post(self):
        """T1：JSON POST 触发 500 时必须返回 JSON，不再是英文纯文本。"""
        resp = _client().post("/__test_raise_500", json={"x": 1})
        assert resp.status_code == 500
        assert resp.is_json, resp.get_data(as_text=True)[:120]
        data = resp.get_json()
        assert data["status"] == "error"
        assert "服务器内部错误" in data["msg"]
        assert "Internal Server Error" not in resp.get_data(as_text=True)

    def test_500_returns_json_even_when_rollback_fails(self, monkeypatch):
        """T2：错误处理器里 rollback 再抛错，响应仍必须是 JSON（异常不得逃出处理器）。"""
        with app_module.app.app_context():
            sess = db.session()

            def _broken_rollback(*args, **kwargs):
                raise RuntimeError("connection broken")

            monkeypatch.setattr(type(sess), "rollback", _broken_rollback)
            resp = _client().post("/__test_raise_500", json={"x": 1})
        assert resp.status_code == 500
        assert resp.is_json, resp.get_data(as_text=True)[:120]
        assert resp.get_json()["status"] == "error"

    def test_csrf_error_returns_json_for_json_post(self):
        """T3：CSRF 失败的 JSON POST 返回 JSON 400，前端能拿到可读 msg。"""
        app_module.app.config["WTF_CSRF_ENABLED"] = True
        try:
            resp = _client().post("/material/delete", json={"ids": [1]})
        finally:
            app_module.app.config["WTF_CSRF_ENABLED"] = False
        assert resp.status_code == 400
        assert resp.is_json, resp.get_data(as_text=True)[:120]
        assert resp.get_json()["status"] == "error"
        assert "安全令牌" in resp.get_json()["msg"]

    def test_wants_json_error_response_detects_json_body(self):
        """T1 补充：仅 Content-Type: application/json（无 XHR/Accept 头）即视为 JSON 调用。"""
        with app_module.app.test_request_context(
            "/material/delete",
            method="POST",
            data="{}",
            content_type="application/json",
            headers={"Accept": "*/*"},
        ):
            assert app_module.wants_json_error_response() is True
        # 普通表单 POST 仍按页面请求处理（返回 HTML/重定向）
        with app_module.app.test_request_context(
            "/material/delete",
            method="POST",
            data="ids=%5B1%5D",
            content_type="application/x-www-form-urlencoded",
        ):
            assert app_module.wants_json_error_response() is False
