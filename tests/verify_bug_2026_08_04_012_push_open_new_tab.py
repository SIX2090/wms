# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-012 回归测试：采购入库单详情页"下推领料单/其他出库/售后出库"必须在新标签页打开

原 Bug：采购入库单详情页（in_order_detail.html）的"下推"菜单三个链接是普通
`<a href>` 锚点，点击后在当前标签页跳转到下推页，导致原采购入库单详情页被替换
（界面关闭），用户无法在查看原单的同时进入领料单/出库单界面。

修复：给三个下推链接添加 `target="_blank" rel="noopener"`，在新标签页打开下推页，
原采购入库单详情页保持打开。

测试策略：
  T1. 已完成采购入库单详情页，"下推领料单"链接带 target="_blank" 且 rel="noopener"
  T2. 三个下推链接（领料单/其他出库/售后出库）都带 target="_blank"
  T3. 下推链接 href 指向 /in_order/<id>/push 且带对应 target 参数
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
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "user": user}


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


def _make_completed_purchase_in_order(mat, qty=10):
    order = InOrder(
        order_no="IN-PUSH-001",
        business_type="采购入库",
        status="completed",
        warehouse="仓库A",
        total_amount=qty * 10,
    )
    db.session.add(order)
    db.session.flush()
    item = InOrderItem(
        in_order_id=order.id,
        material_id=mat.id,
        quantity=qty,
        price=10,
        amount=qty * 10,
    )
    db.session.add(item)
    db.session.commit()
    return order, item


class TestBug20260804012PushOpenNewTab:
    """采购入库单详情页下推链接必须在新标签页打开。"""

    def test_T1_requisition_push_link_has_target_blank(self):
        """下推领料单链接带 target="_blank" 且 rel="noopener"。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, _ = _make_completed_purchase_in_order(seeds["mat"])
            resp = client.get(f"/in_order/{order.id}")
            assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
            html = resp.get_data(as_text=True)
            # 找到"下推领料单"链接
            m = re.search(
                r'<a class="dropdown-item" target="_blank"\s+rel="noopener"\s+href="([^"]*push\?target=requisition)"[^>]*>下推领料单</a>',
                html,
            )
            assert m, "下推领料单链接必须带 target=\"_blank\" rel=\"noopener\" 且指向 push?target=requisition"
            assert f"/in_order/{order.id}/push?target=requisition" in m.group(1), \
                f"href 应指向下推页，实际 {m.group(1)}"

    def test_T2_all_three_push_links_have_target_blank(self):
        """三个下推链接（领料单/其他出库/售后出库）都带 target="_blank"。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, _ = _make_completed_purchase_in_order(seeds["mat"])
            html = client.get(f"/in_order/{order.id}").get_data(as_text=True)
            for target in ("requisition", "other_out", "after_sale_out"):
                m = re.search(
                    r'<a class="dropdown-item" target="_blank"\s+rel="noopener"\s+'
                    r'href="([^"]*push\?target=' + target + r')"',
                    html,
                )
                assert m, f"{target} 下推链接必须带 target=\"_blank\""

    def test_T3_push_href_includes_order_id(self):
        """下推链接 href 带当前入库单 id 与对应 target 参数。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, _ = _make_completed_purchase_in_order(seeds["mat"])
            html = client.get(f"/in_order/{order.id}").get_data(as_text=True)
            assert f"/in_order/{order.id}/push?target=requisition" in html
            assert f"/in_order/{order.id}/push?target=other_out" in html
            assert f"/in_order/{order.id}/push?target=after_sale_out" in html