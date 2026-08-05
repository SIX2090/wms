# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：库存查询（stock_query）域路由迁移到 routes/stock_query.py。

采用 register-on-app 模式（register_stock_query_routes(app)），endpoint 名保持不变
（stock_query_print_not_implemented、stock_query、api_query_search），
URL 路径不变，因此模板/导航中的 url_for 引用无需改动。

验收点：
S1. 3 个 endpoint 已注册，且仍是未加前缀的原始 endpoint 名，
    不存在 stock_query.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/stock_query、/stock_query/print、/api/query/search）。
S3. /stock_query 页面在 seed 物料 + 默认仓库后返回 200。
S4. /stock_query/print 返回 404（api_error code=404）。
S5. /api/query/search：空 keyword 返回 api_error；有效 keyword 返回 success。
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

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

STOCK_QUERY_ENDPOINTS = [
    "stock_query_print_not_implemented",
    "stock_query",
    "api_query_search",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_base():
    """Create category / unit / default warehouse / material."""
    from app import MaterialCategory, Unit, Warehouse, Material
    cat = MaterialCategory(code="CAT1", name="分类1")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="WH001", name="材料仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="M1", name="轴承", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat.id


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _setup():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_base()
    client = _make_client()
    _login(client)
    return client


class TestStockQueryRegister:
    def test_endpoints_and_urls(self):
        """S1/S2：3 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in STOCK_QUERY_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in STOCK_QUERY_ENDPOINTS:
                assert f"stock_query.{ep}" not in app_module.app.view_functions, f"stock_query.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("stock_query") == "/stock_query"
                assert url_for("stock_query_print_not_implemented") == "/stock_query/print"
                assert url_for("api_query_search") == "/api/query/search"

    def test_stock_query_page_returns_200(self):
        """S3：seed 物料 + 默认仓库后，/stock_query 返回 200。"""
        client = _setup()
        resp = client.get("/stock_query")
        assert resp.status_code == 200, resp.status_code

    def test_stock_query_print_returns_not_implemented(self):
        """S4：/stock_query/print 返回 404（api_error code=404）。"""
        client = _setup()
        resp = client.get("/stock_query/print")
        assert resp.status_code == 404, resp.status_code
        data = resp.get_json()
        assert data is not None
        assert data["status"] == "error"

    def test_api_query_search_empty_keyword(self):
        """S5a：/api/query/search 空 keyword 返回 api_error。"""
        client = _setup()
        resp = client.post("/api/query/search", data={"keyword": "  "})
        assert resp.status_code == 400, resp.status_code
        data = resp.get_json()
        assert data["status"] == "error"

    def test_api_query_search_valid_keyword(self):
        """S5b：/api/query/search 有效 keyword 返回 success 且含物料。"""
        client = _setup()
        resp = client.post("/api/query/search", data={"keyword": "M1"})
        assert resp.status_code == 200, resp.status_code
        data = resp.get_json()
        assert data["status"] == "success", data
        assert len(data["data"]) >= 1
        assert data["data"][0]["code"] == "M1"