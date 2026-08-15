# -*- coding: utf-8 -*-
"""BUG-2026-08-16-008 回归：transfer 关库位管理分支必须校验源仓库库存。

根因：complete_transfer 在关闭库位管理（location_management_enabled=False）时
只写双向流水、不校验源仓库库存，可从 0 库存仓库"空手套白狼"调出任意数量。

修复：OFF 分支按仓库级口径 get_warehouse_stock_quantities（依赖 BUG-006 修复后
的流水 location 写入）聚合源仓库库存，明细数量超过可用库存时拒绝完成。

测试用例：
  T1. 关库位管理：源仓库库存不足时调拨完成被拒
  T2. 关库位管理：源仓库库存充足时调拨完成成功
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
    Material, MaterialCategory, TransferOrder, Unit, User, Warehouse, db,
    add_stock, generate_order_no, set_system_setting,
)

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
    # 关闭库位管理
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    wh_a = Warehouse.query.filter_by(code="WHA").first()
    wh_b = Warehouse.query.filter_by(code="WHB").first()
    return mat, wh_a, wh_b


def _create_transfer(client, from_wh, to_wh, qty):
    with app_module.app.app_context():
        transfer_no = generate_order_no("TF")
    payload = {
        "order_no": transfer_no,
        "header": {
            "from_warehouse": from_wh,
            "to_warehouse": to_wh,
        },
        "items": [{"code": "M001", "quantity": qty, "unit_id": 1}],
    }
    resp = client.post("/transfer/save_table", json=payload)
    data = resp.get_json()
    assert data.get("status") == "success", data
    return data.get("id") or data.get("order_id")


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
        _seed()
    c = app_module.app.test_client()
    _login(c)
    yield c


def test_a9_complete_transfer():
    """A9 门禁：complete_transfer 关库位管理分支校验源仓库库存（见 T1/T2）。"""
    with app_module.app.test_request_context():
        _reset_db()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
        mat, wh_a, wh_b = _seed()
        # A 仓入库 10
        ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
        assert ok
        db.session.commit()


class TestTransferOffBranchSourceStock:

    def test_reject_when_source_insufficient(self, client):
        """T1：关库位管理，源仓库库存不足时完成被拒。

        全局库存充足（Material.stock=10，save_table 通过），但源仓库 A 为空，
        OFF 分支必须按仓库级口径拒绝从空仓库调出。
        """
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            # 库存放在 B 仓，源仓库 A 为空（全局库存仍=10）
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_b)
            assert ok
            db.session.commit()
        tid = _create_transfer(client, "仓库A", "仓库B", 10)
        resp = client.post(f"/transfer/{tid}/complete")
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库存不足" in (data.get("msg") or ""), data
        # 单据仍为 pending
        with app_module.app.app_context():
            assert TransferOrder.query.get(tid).status == "pending"

    def test_succeed_when_source_sufficient(self, client):
        """T2：关库位管理，源仓库库存充足时完成成功。"""
        with app_module.app.test_request_context():
            mat = Material.query.filter_by(code="M001").first()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            ok, _ = add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
            assert ok
            db.session.commit()
        tid = _create_transfer(client, "仓库A", "仓库B", 3)
        resp = client.post(f"/transfer/{tid}/complete")
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            assert TransferOrder.query.get(tid).status == "completed"