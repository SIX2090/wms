# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-004 回归测试：导入物料不成功没有提示原因

原 Bug：
  1) 后端 wants_json_error_response() 只判断 /api/ 前缀，
     /material/import AJAX POST 在 CSRF 失效或 4xx/5xx 时返回 302 重定向或 HTML，
     前端 fetch().then(r => r.json()) 解析失败，丢失真实原因。
  2) 前端 material.html / batch_import.html 的导入回调直接 .then(r => r.json())，
     没有 response.ok 检查；非 JSON 响应时 catch 只显示
     "请求失败：Unexpected token..." 完全丢失原因。

修复：
  - 后端 wants_json_error_response() 额外识别 X-Requested-With: XMLHttpRequest
    与 Accept: application/json，让 AJAX 请求统一拿到 JSON 错误响应。
  - 前端先检查 response.ok，再解析 JSON；非 JSON 时给出友好提示；
    JSON 错误体优先取 err.msg。

测试策略：
  T1. api_error 返回 400 + JSON，msg 字段存在
  T2. AJAX POST /material/import 不传文件 → 400 + JSON {'msg': '请选择...'}
  T3. AJAX POST /material/import 上传空文件 → 400 + JSON，msg 非空
  T4. AJAX POST /material/import 上传缺表头文件 → 400 + JSON，msg 含 "表头"/"列"
  T5. wants_json_error_response() 对 X-Requested-With: XMLHttpRequest 返回 True
  T6. CSRF 失效时 AJAX POST /material/import 返回 JSON 而非 302 重定向
"""
from __future__ import annotations

import os
import sys
import re
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
from app import db, User  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


class TestBug20260804004ImportErrorFeedback:
    """导入物料失败时前端必须收到明确的错误原因。"""

    def test_T1_api_error_returns_400_with_msg(self):
        """api_error 返回 400 + JSON，msg 字段存在。"""
        with app_module.app.test_request_context():
            from app import api_error
            resp, code = api_error("导入失败：测试原因")
            assert code == 400
            data = resp.get_json()
            assert data["status"] == "error"
            assert "测试原因" in data["msg"]

    def test_T2_ajax_no_file_returns_400_with_msg(self):
        """AJAX POST /material/import 不传文件 → 400 + JSON。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/material/import", headers=AJAX_HEADERS)
            assert resp.status_code == 400
            data = resp.get_json()
            assert data is not None, "AJAX 请求必须返回 JSON，不能是 HTML/302"
            assert data["status"] == "error"
            assert "请选择" in data["msg"]

    def test_T3_import_empty_file_returns_400_with_clear_msg(self):
        """AJAX 上传空文件 → 400 + 明确原因。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            from io import BytesIO
            resp = client.post("/material/import",
                               data={"file": (BytesIO(b""), "empty.xlsx")},
                               content_type="multipart/form-data",
                               headers=AJAX_HEADERS)
            assert resp.status_code == 400
            data = resp.get_json()
            assert data is not None, "AJAX 请求必须返回 JSON"
            assert data["status"] == "error"
            assert len(data["msg"]) > 5

    def test_T4_import_bad_header_returns_400_with_detail(self):
        """AJAX 上传缺表头文件 → 400 + msg 含 "表头"/"列"。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            client = app_module.app.test_client()
            _login(client)
            from io import BytesIO
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.append(["随便", "表头"])  # 缺少编码/名称列
            buf = BytesIO()
            wb.save(buf)
            buf.seek(0)
            resp = client.post("/material/import",
                               data={"file": (buf, "test.xlsx")},
                               content_type="multipart/form-data",
                               headers=AJAX_HEADERS)
            assert resp.status_code == 400
            data = resp.get_json()
            assert data is not None, "AJAX 请求必须返回 JSON"
            assert data["status"] == "error"
            assert "表头" in data["msg"] or "列" in data["msg"]

    def test_T5_wants_json_error_response_recognizes_ajax(self):
        """wants_json_error_response() 必须识别 AJAX 请求头。"""
        with app_module.app.test_request_context(
                "/material/import",
                method="POST",
                headers={"X-Requested-With": "XMLHttpRequest"}):
            from app import wants_json_error_response
            assert wants_json_error_response() is True

        with app_module.app.test_request_context(
                "/material/import",
                method="POST",
                headers={"Accept": "application/json"}):
            from app import wants_json_error_response
            assert wants_json_error_response() is True

        # 普通 GET 浏览器请求应返回 False（保持原有 HTML 错误页行为）
        with app_module.app.test_request_context(
                "/material",
                method="GET",
                headers={"Accept": "text/html"}):
            from app import wants_json_error_response
            assert wants_json_error_response() is False

    def test_T6_csrf_failure_ajax_returns_json_not_redirect(self):
        """CSRF 失效时 AJAX POST 必须返回 JSON，不能 302 重定向到首页。

        场景：用户停留超过 30 分钟，csrftoken 过期，再点"导入"。
        旧版本会返回 302 → 浏览器自动跟随 → 拿到首页 HTML →
        r.json() 抛 "Unexpected token '<'" → 用户看不到原因。
        修复后：AJAX 请求一律返回 JSON {status:'error', msg:'请求已过期...'}。
        """
        # 临时启用 CSRF，模拟生产环境
        app_module.app.config["WTF_CSRF_ENABLED"] = True
        try:
            with app_module.app.app_context():
                _reset_db()
                _seed_admin()
                client = app_module.app.test_client()
                _login(client)
                # 故意不带 csrf_token 提交
                from io import BytesIO
                resp = client.post("/material/import",
                                   data={"file": (BytesIO(b""), "empty.xlsx")},
                                   content_type="multipart/form-data",
                                   headers=AJAX_HEADERS)
                # 不能是 302 重定向
                assert resp.status_code != 302, \
                    "AJAX 请求 CSRF 失效时不能 302 重定向，会丢失原因"
                # 必须是 JSON
                data = resp.get_json()
                assert data is not None, \
                    "AJAX 请求 CSRF 失效时必须返回 JSON，不能是 HTML"
                assert data["status"] == "error"
                # msg 必须包含可读原因
                assert len(data["msg"]) > 5
        finally:
            app_module.app.config["WTF_CSRF_ENABLED"] = False
