# -*- coding: utf-8 -*-
"""手机扫码出入库草稿制回归测试。

流程：
1. 批量提交 /mobile/api/scan_batch_draft 生成 status='pending' 草稿，
   不动库存、不打印（审核兜底）。
2. 手机端 /mobile/api/scan_draft_confirm/<id> 人工确认后才动库存，
   并触发打印任务（enqueue_auto_print_job）。
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


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, name, stock=0, price=5):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=name, stock=stock, price=price, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_warehouse("W001", "默认仓", is_default=True)
    c = app_module.app.test_client()
    _login(c)
    yield c


def _stock_of(material_id):
    from app import get_warehouse_stock_quantities, Warehouse
    from app import location_management_enabled
    wh = Warehouse.query.filter_by(name="默认仓").first()
    with app_module.app.app_context():
        qty = get_warehouse_stock_quantities(wh).get(material_id, 0)
        return qty


class TestScanBatchDraft:
    """批量提交生成 pending 草稿，不动库存。"""

    def test_batch_draft_in_generates_single_pending_order(self, client):
        with app_module.app.app_context():
            m1 = _seed_material("M001", "物料A", stock=0)
            m2 = _seed_material("M002", "物料B", stock=0)
            m1_id, m2_id = m1.id, m2.id
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={
                "mode": "in",
                "lines": [
                    {"material_code": "M001", "quantity": 3},
                    {"material_code": "M002", "quantity": 5},
                ],
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        assert body["data"]["order_type"] == "in"
        assert body["data"]["item_count"] == 2

        from app import InOrder
        with app_module.app.app_context():
            order = InOrder.query.get(body["data"]["order_id"])
            assert order is not None
            assert order.status == "pending"
            assert len(order.items) == 2
            # 未确认前库存不变
            assert _stock_of(m1_id) == 0
            assert _stock_of(m2_id) == 0

    def test_batch_draft_requires_valid_material(self, client):
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "in", "lines": [{"material_code": "NOPE", "quantity": 1}]},
        )
        assert resp.status_code == 404
        assert resp.get_json()["status"] == "error"

    def test_batch_draft_requires_lines(self, client):
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "in", "lines": []},
        )
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"


class TestScanDraftConfirm:
    """确认草稿才动库存并打印。"""

    def test_confirm_in_moves_stock_and_prints(self, client):
        with app_module.app.app_context():
            m = _seed_material("M001", "物料A", stock=0)
            m_id = m.id
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "in", "lines": [{"material_code": "M001", "quantity": 4}]},
        )
        order_id = resp.get_json()["data"]["order_id"]

        confirm = client.post(
            f"/mobile/api/scan_draft_confirm/{order_id}",
            json={"order_type": "in"},
        )
        assert confirm.status_code == 200, confirm.get_data(as_text=True)
        assert confirm.get_json()["status"] == "success"

        from app import InOrder, PrintJob
        with app_module.app.app_context():
            order = InOrder.query.get(order_id)
            assert order.status == "completed"
            assert _stock_of(m_id) == 4
            job = PrintJob.query.filter_by(job_type="in_order", target_id=order_id).first()
            assert job is not None, "确认后应发送打印任务"

    def test_confirm_out_deducts_stock(self, client):
        with app_module.app.app_context():
            m = _seed_material("M001", "物料A", stock=10)
            m_id = m.id
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "out", "lines": [{"material_code": "M001", "quantity": 3}]},
        )
        order_id = resp.get_json()["data"]["order_id"]

        confirm = client.post(
            f"/mobile/api/scan_draft_confirm/{order_id}",
            json={"order_type": "out"},
        )
        assert confirm.status_code == 200, confirm.get_data(as_text=True)
        from app import OutOrder, PrintJob
        with app_module.app.app_context():
            order = OutOrder.query.get(order_id)
            assert order.status == "completed"
            assert _stock_of(m_id) == 7
            job = PrintJob.query.filter_by(job_type="out_order", target_id=order_id).first()
            assert job is not None

    def test_confirm_in_sufficient_stock_check_for_out(self, client):
        """出库草稿库存不足时确认必须失败，且状态保持 pending。"""
        with app_module.app.app_context():
            m = _seed_material("M001", "物料A", stock=0)
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "out", "lines": [{"material_code": "M001", "quantity": 5}]},
        )
        order_id = resp.get_json()["data"]["order_id"]

        confirm = client.post(
            f"/mobile/api/scan_draft_confirm/{order_id}",
            json={"order_type": "out"},
        )
        assert confirm.status_code == 400
        assert confirm.get_json()["status"] == "error"
        from app import OutOrder
        with app_module.app.app_context():
            assert OutOrder.query.get(order_id).status == "pending"

    def test_confirm_already_confirmed_rejected(self, client):
        with app_module.app.app_context():
            _seed_material("M001", "物料A", stock=0)
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "in", "lines": [{"material_code": "M001", "quantity": 1}]},
        )
        order_id = resp.get_json()["data"]["order_id"]
        assert client.post(f"/mobile/api/scan_draft_confirm/{order_id}", json={"order_type": "in"}).status_code == 200
        # 二次确认必须失败
        second = client.post(f"/mobile/api/scan_draft_confirm/{order_id}", json={"order_type": "in"})
        assert second.status_code == 400

    def test_confirm_wrong_order_type_rejected(self, client):
        with app_module.app.app_context():
            _seed_material("M001", "物料A", stock=0)
        resp = client.post(
            "/mobile/api/scan_batch_draft",
            json={"mode": "in", "lines": [{"material_code": "M001", "quantity": 1}]},
        )
        order_id = resp.get_json()["data"]["order_id"]
        # in 草稿用 out 确认 → 加锁失败
        resp2 = client.post(f"/mobile/api/scan_draft_confirm/{order_id}", json={"order_type": "out"})
        assert resp2.status_code == 400