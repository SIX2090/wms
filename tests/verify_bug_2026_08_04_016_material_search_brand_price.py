# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-016 回归测试：/api/material/search 返回的物料载荷缺少 brand 与 price 字段。

问题：in_order_detail.html 使用 /api/material/search 做物料快速搜索，并在
fillAddMaterialInfo() 中读取 material.brand 与 material.price（第 736/743 行）。
而 api_material_payload() 遗漏了这两个字段，导致入库单详情页新增物料时品牌恒为空、
单价恒为 0.00，覆盖了物料档案里已维护的品牌与价格。

修复：api_material_payload() 补充 brand 与 price 字段（对 /api/material/search 与
/api/material/info 等所有调用方均为新增字段，向后兼容）。

不变量：/api/material/search 返回的每条物料数据必须包含 brand 与 price，
并且与 Material 记录一致。
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
from app import (  # noqa: E402
    db, MaterialCategory, Unit, Supplier, Material,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    from werkzeug.security import generate_password_hash
    from app import User
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        brand="测试品牌", price=12.34,
        category=cat, unit=unit, supplier=sup,
        stock=0, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, user, mat])
    db.session.commit()
    return {"mat": mat, "user": user}


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


class TestMaterialSearchPayloadBrandPrice:
    def test_search_returns_brand_and_price(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            mat = seeds["mat"]
            client = _make_client()

            resp = client.get("/api/material/search?kw=" + mat.code)
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data.get("status") == "success", data
            items = data.get("data") or []
            assert len(items) == 1, f"应命中 1 条物料，实际 {len(items)}: {items}"

            item = items[0]
            assert item["code"] == mat.code
            assert item["brand"] == "测试品牌", \
                f"BUG: /api/material/search 未返回 brand，实际 {item.get('brand')!r}"
            assert float(item["price"]) == 12.34, \
                f"BUG: /api/material/search 未返回 price，实际 {item.get('price')!r}"

    def test_info_returns_brand_and_price(self):
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            mat = seeds["mat"]
            client = _make_client()

            resp = client.get("/api/material/info?code=" + mat.code)
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data.get("status") == "success", data
            item = data.get("data") or {}
            assert item.get("brand") == "测试品牌", \
                f"BUG: /api/material/info 未返回 brand，实际 {item.get('brand')!r}"
            assert float(item.get("price") or 0) == 12.34, \
                f"BUG: /api/material/info 未返回 price，实际 {item.get('price')!r}"