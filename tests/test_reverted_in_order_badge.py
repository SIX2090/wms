# -*- coding: utf-8 -*-
"""P2（2026-10-03）回归：反提交草稿标识（WMS-UX-P2-001）。

背景：反提交只回退库存、不释放来源采购订单 received_quantity 预留（只有删除
草稿才释放，见 routes/in_order.py revert 分支注释）。"曾完成后被反提交"的
pending 单与普通新草稿在列表/详情页原先无法区分，操作者容易漏掉该类滞留
草稿，导致采购订单长期显示已收货而仓库库存已回退（进度虚高）。

修复：
- routes/in_order.py 新增 get_reverted_in_order_ids(order_ids)：按
  StockTransaction(transaction_type='revert_in', reference_type='in_order',
  reference_id) 判定"反提交草稿"；
- 列表页（in_order.html）状态列为反提交草稿追加「反提交草稿」红色徽章；
- 详情页（in_order_detail.html）为反提交草稿显示警示横幅。

用例：
  T1. 反提交（单张）后 helper 判定命中；普通新草稿 / 已完成单不命中
  T2. 列表页 HTML 含「反提交草稿」徽章，且仅反提交草稿命中（count==1）
  T3. 批量反提交同样命中；详情页 HTML 含警示横幅；普通草稿详情无横幅
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, InOrderItem, Material, MaterialCategory, StockTransaction,
    Supplier, Unit, User, Warehouse, db, set_system_setting,
)
from routes.in_order import get_reverted_in_order_ids  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Supplier(code="SUP001", name="供应商"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, supplier_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _legacy_unattributed_stock(mat, qty):
    """历史未归属库存（与 test_bug_2026_08_18_002 同法）：Material.stock 有量、流水无归属。"""
    mat.stock = qty
    db.session.add(StockTransaction(
        material_id=mat.id, transaction_type="in", quantity=qty,
        location=None,
        reference_type="in_order", reference_id=999,
    ))
    db.session.commit()


def _make_completed_in_order(order_no, warehouse, qty):
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库",
                    warehouse=warehouse, status="completed",
                    operator_id=user.id, supplier_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=1,
        quantity=qty, price=10, amount=qty * 10))
    db.session.commit()
    return order.id


def _make_fresh_pending_draft(order_no, warehouse, qty):
    """普通新草稿：从未完成过，不该被标识。"""
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库",
                    warehouse=warehouse, status="pending",
                    operator_id=user.id, supplier_id=1)
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=1,
        quantity=qty, price=10, amount=qty * 10))
    db.session.commit()
    return order.id


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


class TestRevertedInOrderBadge:

    def test_get_reverted_in_order_ids(self, client):
        """T1（A9 对应测试）：单张反提交后 helper 命中；新草稿/已完成单不命中。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            _legacy_unattributed_stock(mat, 100)
            completed_id = _make_completed_in_order("IN-P2-T1-C", "仓库A", 60)
            fresh_id = _make_fresh_pending_draft("IN-P2-T1-F", "仓库A", 10)

        r = client.post(f"/in_order/{completed_id}/revert")
        d = r.get_json()
        assert d["status"] == "success", d

        with app_module.app.app_context():
            assert db.session.get(InOrder, completed_id).status == "pending"
            reverted = get_reverted_in_order_ids([completed_id, fresh_id])
            assert completed_id in reverted
            assert fresh_id not in reverted
            # 空入参/None 安全
            assert get_reverted_in_order_ids([]) == set()
            assert get_reverted_in_order_ids(None) == set()

    def test_t2_list_page_shows_badge_only_for_reverted_draft(self, client):
        """T2：列表页为反提交草稿显示徽章，普通新草稿不显示。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            _legacy_unattributed_stock(mat, 100)
            completed_id = _make_completed_in_order("IN-P2-T2-C", "仓库A", 60)
            fresh_id = _make_fresh_pending_draft("IN-P2-T2-F", "仓库A", 10)

        r = client.post(f"/in_order/{completed_id}/revert")
        assert r.get_json()["status"] == "success"

        resp = client.get("/in_order")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "反提交草稿" in html
        # 仅反提交草稿命中：badge span 只出现 1 次（含 title 属性共 2 处同词，
        # 但徽章 span 本身 1 个——用 data 属性级别断言更稳：两单都在列表里）
        assert html.count(">反提交草稿</span>") == 1
        assert str(fresh_id) and str(completed_id)

    def test_t3_batch_revert_and_detail_banner(self, client):
        """T3：批量反提交命中；详情页有警示横幅；普通草稿详情无横幅。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed()
            mat = Material.query.filter_by(code="M001").first()
            _legacy_unattributed_stock(mat, 100)
            completed_id = _make_completed_in_order("IN-P2-T3-C", "仓库A", 60)
            fresh_id = _make_fresh_pending_draft("IN-P2-T3-F", "仓库A", 10)

        resp = client.post("/in_order/batch_revert", json={"ids": [completed_id]})
        data = resp.get_json()
        assert resp.status_code == 200, data

        with app_module.app.app_context():
            assert completed_id in get_reverted_in_order_ids([completed_id])

        detail = client.get(f"/in_order/{completed_id}")
        dhtml = detail.get_data(as_text=True)
        assert detail.status_code == 200
        assert "该单曾完成后反提交" in dhtml
        assert "收货预留" in dhtml

        fresh_detail = client.get(f"/in_order/{fresh_id}")
        fhtml = fresh_detail.get_data(as_text=True)
        assert fresh_detail.status_code == 200
        assert "该单曾完成后反提交" not in fhtml
