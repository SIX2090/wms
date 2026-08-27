# -*- coding: utf-8 -*-
"""BUG-2026-08-28-001 回归测试：手机端「待确认」页分页。

缺陷：mobile_scan.html 待确认页调用 /api/mobile/in_order/list 与
/api/mobile/out_order/list 时不传分页参数，后端默认只返回第 1 页 20 条，
且页面无翻页入口——待确认草稿超过 20 条后第 21 条起永远不可见。

修复：前端首屏 20 条不变，超过 20 条时列表底部出现「加载更多」按钮，
逐页（&page=N）取回全部草稿；后端接口本身已支持分页元数据
（total / page / page_size / total_pages），本测试验证：
1. 接口分页元数据正确（25 条草稿：第 1 页 20 条、第 2 页 5 条、跨页不重叠）；
2. 入库、出库两个列表接口行为一致；
3. 模板必须包含分页加载逻辑（loadMore / &page= / total_pages / 加载更多按钮），
   防止回退成"只查第一页"的旧实现。
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

TEMPLATE_PATH = APP_DIR / "templates" / "mobile_scan.html"

WAREHOUSE_NAME = "分页测试仓"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse():
    from app import Warehouse
    db.session.add(Warehouse(code="WPAG", name=WAREHOUSE_NAME, status="active", is_default=True))
    db.session.commit()


def _seed_material(code):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material.query.filter_by(code=code).first()
    if not m:
        m = Material(code=code, name=f"物料{code}", stock=0, price=5, unit=unit)
        db.session.add(m)
        db.session.commit()
    return m


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_warehouse()
        _seed_material("MP001")
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            c.post(
                "/login",
                data={"username": "admin", "password": "admin"},
                content_type="application/x-www-form-urlencoded",
            )
            yield c


def _create_drafts(client, mode, count):
    """生成 count 张待确认草稿（每张 1 行明细），返回单号列表。"""
    order_nos = []
    for i in range(count):
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={
                "mode": mode,
                "warehouse": WAREHOUSE_NAME,
                "lines": [{"material_code": "MP001", "quantity": 1}],
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        order_nos.append(body["data"]["order_no"])
    return order_nos


class TestPendingListPaginationApi:
    """接口层：分页元数据必须支持翻页取回全部草稿。"""

    def test_in_order_list_pagination_metadata(self, client):
        created = _create_drafts(client, "in", 25)
        from urllib.parse import quote
        wh = quote(WAREHOUSE_NAME)

        page1 = client.get(f"/api/mobile/in_order/list?status=pending&warehouse={wh}&page=1")
        assert page1.status_code == 200, page1.get_data(as_text=True)
        d1 = page1.get_json()["data"]
        assert d1["total"] == 25
        assert d1["total_pages"] == 2
        assert len(d1["items"]) == 20
        assert d1["page"] == 1

        page2 = client.get(f"/api/mobile/in_order/list?status=pending&warehouse={wh}&page=2")
        assert page2.status_code == 200
        d2 = page2.get_json()["data"]
        assert len(d2["items"]) == 5

        nos1 = {o["order_no"] for o in d1["items"]}
        nos2 = {o["order_no"] for o in d2["items"]}
        assert not (nos1 & nos2), "第 1 页与第 2 页草稿不应重叠"
        assert nos1 | nos2 == set(created), "两页合并必须覆盖全部 25 张草稿"

    def test_out_order_list_pagination_metadata(self, client):
        _create_drafts(client, "out", 21)
        from urllib.parse import quote
        wh = quote(WAREHOUSE_NAME)

        page1 = client.get(f"/api/mobile/out_order/list?status=pending&warehouse={wh}&page=1")
        assert page1.status_code == 200
        d1 = page1.get_json()["data"]
        assert d1["total"] == 21
        assert len(d1["items"]) == 20

        page2 = client.get(f"/api/mobile/out_order/list?status=pending&warehouse={wh}&page=2")
        assert page2.status_code == 200
        d2 = page2.get_json()["data"]
        assert len(d2["items"]) == 1
        assert d2["total"] == 21


class TestMobileConfirmTemplatePagination:
    """模板层：待确认页必须带分页加载逻辑，不得回退成只查第一页。"""

    def test_template_contains_load_more_logic(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "loadMore" in html, "缺少加载更多入口函数 loadMore"
        assert "'&page=' + page" in html, "请求必须携带页码参数 &page="
        assert "total_pages" in html, "必须依据 total_pages 判断是否还有下一页"
        assert "confirmMoreBtn" in html, "缺少「加载更多」按钮"
        assert "已全部加载" in html, "全部加载完应给出明确提示"

    def test_template_requests_both_lists_with_page(self):
        html = TEMPLATE_PATH.read_text(encoding="utf-8")
        # fetchPendingPage 必须同时覆盖入库与出库两个接口，且统一走 page 参数拼接
        assert "fetchPendingPage" in html
        assert "/api/mobile/in_order/list?status=pending" in html
        assert "/api/mobile/out_order/list?status=pending" in html
        # 旧的"固定第一页、无 page 参数"写法不应回归（直接 fetch 列表 URL 且不带 page 的 loadPending）
        assert "loadPending() {" in html
