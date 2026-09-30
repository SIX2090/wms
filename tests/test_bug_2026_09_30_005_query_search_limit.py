# -*- coding: utf-8 -*-
"""BUG-2026-09-30-005 回归：/api/query/search 必须有界返回（LIMIT + has_more）。

修复前（M1 基线 E4 实测）：`.all()` 无 LIMIT 无分页，宽关键词命中全量物料时
单请求返回全部行——5000 物料 4.73s / 664KB，违反 AGENTS.md §七 R1
（列表接口不得让调用方隐式拿到"全量"）。

修复后（本文件锁死）：
1. 默认 limit=100：150 命中只返回前 100 条，has_more=True；
2. 自定义 limit 生效（10 → 10 条）；
3. limit 上限 500（传 9999 被钳到 500）、下限 1；
4. 非法 limit（非数字）回退默认 100，不 500；
5. 小结果集（< limit）has_more=False，全量返回，字段内容不变；
6. 排序仍为 Material.code 升序（首页=最小编码）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse_with_default():
    from app import Warehouse
    w = Warehouse(code="WHA", name="仓库A", status="active", is_default=True)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_materials(n, prefix="MB"):
    from app import Material
    ms = [Material(code=f"{prefix}{i:04d}", name=f"轴承{i}", stock=0) for i in range(n)]
    db.session.add_all(ms)
    db.session.commit()
    return ms


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_warehouse_with_default()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"},
           content_type="application/x-www-form-urlencoded")
    yield c


class TestQuerySearchLimit:
    """BUG-2026-09-30-005：LIMIT 有界返回锁。"""

    def test_t1_default_limit_100_and_has_more(self, client):
        with app_module.app.app_context():
            _seed_materials(150)
        resp = client.post("/api/query/search", data={"keyword": "MB"})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success"
        assert len(body["data"]) == 100, "默认 limit 必须 100，实际 %d" % len(body["data"])
        assert body["limit"] == 100
        assert body["has_more"] is True, "150 命中只返回 100，必须提示 has_more"

    def test_t2_custom_limit_honored(self, client):
        with app_module.app.app_context():
            _seed_materials(150)
        resp = client.post("/api/query/search", data={"keyword": "MB", "limit": "10"})
        body = resp.get_json()
        assert len(body["data"]) == 10
        assert body["limit"] == 10
        assert body["has_more"] is True

    def test_t3_limit_capped_at_500(self, client):
        with app_module.app.app_context():
            _seed_materials(150)
        resp = client.post("/api/query/search", data={"keyword": "MB", "limit": "9999"})
        body = resp.get_json()
        assert body["limit"] == 500, "超上限必须钳到 500"
        assert len(body["data"]) == 150
        assert body["has_more"] is False

    def test_t4_invalid_limit_falls_back(self, client):
        with app_module.app.app_context():
            _seed_materials(150)
        resp = client.post("/api/query/search", data={"keyword": "MB", "limit": "abc"})
        body = resp.get_json()
        assert body["limit"] == 100, "非法 limit 回退默认 100"
        assert len(body["data"]) == 100

    def test_t5_small_result_full_and_fields_intact(self, client):
        with app_module.app.app_context():
            ms = _seed_materials(3)
        resp = client.post("/api/query/search", data={"keyword": "MB"})
        body = resp.get_json()
        assert len(body["data"]) == 3
        assert body["has_more"] is False
        first = body["data"][0]
        assert first["code"] == "MB0000" and first["name"] == "轴承0"
        assert set(first.keys()) >= {"id", "code", "name", "spec", "stock", "unit", "supplier"}

    def test_t6_order_by_code_asc_first_page(self, client):
        with app_module.app.app_context():
            _seed_materials(150)
        resp = client.post("/api/query/search", data={"keyword": "MB", "limit": "5"})
        body = resp.get_json()
        codes = [r["code"] for r in body["data"]]
        assert codes == ["MB0000", "MB0001", "MB0002", "MB0003", "MB0004"], codes
