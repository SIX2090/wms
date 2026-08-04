# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-008 回归测试：物料导入缺少长度和价格上限校验

原 Bug：
  import_material 不做 sanitize_text_input（XSS/NUL）、不做 code/name/spec
  长度校验、不做价格上限校验（直接 float()），与 add_material 不一致。
  可通过 Excel 导入注入 XSS、超长字段（DB 静默截断）、天价物料。

修复：
  导入走 sanitize_text_input + 长度校验（code≤50/name≤100/spec≤100/
  brand≤100）+ parse_bounded_number(MAX_REASONABLE_PRICE)，超限行跳过
  并在 skip_details 中给出原因。

测试：
  T1. 编码超 50 字符 → 跳过，skip_details 含 "编码不能超过50"
  T2. 名称超 100 字符 → 跳过，skip_details 含 "名称不能超过100"
  T3. 价格 > 99,999,999.99 → 跳过，skip_details 含 "参考价格"
  T4. 价格为负数 → 跳过，skip_details 含 "参考价格"
  T5. 名称含 <script> XSS → 导入成功但标签被去除
  T6. 正常数据 → 导入成功
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path
from io import BytesIO

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db, User, Material  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


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


def _make_xlsx(rows, headers=None):
    """Build an in-memory Excel file. headers defaults to standard columns."""
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    if headers is None:
        headers = ["编码", "名称", "规格", "品牌", "单价"]
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _import(client, buf, filename="test.xlsx"):
    return client.post(
        "/material/import",
        data={"file": (buf, filename)},
        content_type="multipart/form-data",
        headers=AJAX_HEADERS,
    )


class TestBug20260804008ImportValidation:
    """物料导入必须有长度和价格上限校验，与 add_material 一致。"""

    def test_T1_code_too_long_skipped(self):
        """编码超 50 字符 → 跳过，skip_details 含原因。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            long_code = "A" * 51
            buf = _make_xlsx([[long_code, "测试物料", "规格", "", 10]])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["count"] == 0
            assert "编码不能超过50" in data.get("warnings", "")

    def test_T2_name_too_long_skipped(self):
        """名称超 100 字符 → 跳过，skip_details 含原因。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            long_name = "B" * 101
            buf = _make_xlsx([["M001", long_name, "规格", "", 10]])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["count"] == 0
            assert "名称不能超过100" in data.get("warnings", "")

    def test_T3_price_above_limit_skipped(self):
        """价格 > 99,999,999.99 → 跳过，skip_details 含原因。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            buf = _make_xlsx([["M001", "测试物料", "规格", "", 100000000]])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["count"] == 0
            assert "参考价格" in data.get("warnings", "")

    def test_T4_negative_price_skipped(self):
        """价格为负数 → 跳过，skip_details 含原因。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            buf = _make_xlsx([["M001", "测试物料", "规格", "", -50]])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success"
            assert data["count"] == 0
            assert "参考价格" in data.get("warnings", "")

    def test_T5_xss_in_name_sanitized(self):
        """名称含 <script> → 导入成功但标签被去除。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            buf = _make_xlsx([["M001", "<script>alert(1)</script>轴承", "规格", "", 10]])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success", data
            assert data["count"] == 1
            mat = Material.query.filter_by(code="M001").first()
            assert mat is not None
            assert "<script>" not in mat.name
            assert ">" not in mat.name
            assert "alert" in mat.name  # 文本保留，标签去除

    def test_T6_normal_data_imported(self):
        """正常数据 → 导入成功。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            buf = _make_xlsx([
                ["M001", "轴承", "6204", "SKF", 25.5],
                ["M002", "螺母", "M8", "", 0.3],
            ])
            client = app_module.app.test_client()
            _login(client)
            resp = _import(client, buf)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "success", data
            assert data["count"] == 2
            assert Material.query.filter_by(code="M001").first() is not None
            assert Material.query.filter_by(code="M002").first() is not None
