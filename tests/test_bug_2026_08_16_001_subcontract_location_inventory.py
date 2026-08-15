# -*- coding: utf-8 -*-
"""BUG-2026-08-16-001 回归：委外发料/收货必须同步写 LocationInventory 库位账。

审计发现（AUDIT-2026-08-16 P0-1）：委外发料（subcontract_issue）与委外收货
（subcontract_receive）的 6 个库存写入入口只改 Material.stock 总账 +
StockTransaction 流水，从不写 LocationInventory。开启库位管理后委外业务
全部错账：库存查询显示 0、按库位出库被余额不足拦截。

修复后要求：
- SubcontractIssue / SubcontractReceive 模型含 location 列；
- 开启库位管理时：快速发料/收货、完成发料/收货、反提交发料/收货
  均同步写库位账（未填库位以仓库名占位）；
- 开启库位管理时新增/快速发料缺库位直接拒绝；
- 未开启库位管理时不写库位账（向后兼容）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory, Material, MaterialCategory,
    SubcontractIssue, SubcontractIssueItem, SubcontractOrder, SubcontractReceive,
    SubcontractReceiveItem, Supplier, Unit, User, Warehouse, db,
    set_system_setting,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="加工厂"),
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
        db.session.add_all([
            Material(code="M-RAW", name="原材料", spec="S",
                     category_id=1, unit_id=1, supplier_id=1, stock=100, price=1),
            Material(code="M-FG", name="成品", spec="S",
                     category_id=1, unit_id=1, supplier_id=1, stock=0, price=2),
        ])
        db.session.commit()
        # 委外单（仓库必填）+ 委外产品明细
        order = SubcontractOrder(order_no="SC001", supplier_id=1,
                                 warehouse="主仓", status="processing")
        db.session.add(order)
        db.session.commit()
        # 原材料在主仓-A1 已有库位账基线（与总账 100 对齐），
        # 发料扣减库位必须已有行，否则按防错账规则拒绝。
        raw = Material.query.filter_by(code="M-RAW").first()
        wh = Warehouse.query.filter_by(name="主仓").first()
        db.session.add(LocationInventory(
            material_id=raw.id, warehouse_id=wh.id,
            location="主仓-A1", quantity=100))
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _ids():
    with app_module.app.app_context():
        order = SubcontractOrder.query.filter_by(order_no="SC001").first()
        raw = Material.query.filter_by(code="M-RAW").first()
        fg = Material.query.filter_by(code="M-FG").first()
        wh = Warehouse.query.filter_by(name="主仓").first()
        return order.id, raw, fg, wh


def _enable_location_mgmt(enabled):
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1" if enabled else "0")
        db.session.commit()


def _loc_rows(material_id, warehouse_id, location):
    with app_module.app.app_context():
        return LocationInventory.query.filter_by(
            material_id=material_id, warehouse_id=warehouse_id, location=location
        ).all()


def _stock(code):
    with app_module.app.app_context():
        mat = Material.query.filter_by(code=code).first()
        db.session.expire(mat, ["stock"])
        return mat.stock or 0


def test_models_have_location_column():
    """BUG-2026-08-16-001：两张委外单表必须含 location 列。"""
    with app_module.app.app_context():
        assert SubcontractIssue.__table__.columns.get("location") is not None, \
            "SubcontractIssue 缺少 location 列"
        assert SubcontractReceive.__table__.columns.get("location") is not None, \
            "SubcontractReceive 缺少 location 列"


def test_quick_issue_requires_location_when_enabled(client):
    """开启库位管理：快速发料缺库位必须拒绝。"""
    order_id, raw, _fg, _wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post(f"/subcontract/{order_id}/issue", data={
        "material_code": "M-RAW", "quantity": "1",
    })
    assert resp.get_json().get("status") == "error"
    assert "库位" in resp.get_json().get("msg", "")


def test_quick_issue_deducts_location_inventory(client):
    """开启库位管理：快速发料同步扣库位账，总账/库位账一致。"""
    order_id, raw, _fg, wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post(f"/subcontract/{order_id}/issue", data={
        "material_code": "M-RAW", "quantity": "10", "location": "主仓-A1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _loc_rows(raw.id, wh.id, "主仓-A1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 90) < 1e-6
    assert abs(_stock("M-RAW") - 90) < 1e-6


def test_quick_receive_adds_location_inventory(client):
    """开启库位管理：快速收货同步写库位账（未填库位以仓库名占位）。"""
    order_id, _raw, fg, wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post(f"/subcontract/{order_id}/receive", data={
        "material_code": "M-FG", "quantity": "5", "price": "2", "location": "主仓-B1",
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _loc_rows(fg.id, wh.id, "主仓-B1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 5) < 1e-6
    assert abs(_stock("M-FG") - 5) < 1e-6


def test_quick_receive_requires_location_when_enabled(client):
    """开启库位管理：快速收货缺库位必须拒绝（AGENTS.md 规则二）。"""
    order_id, _raw, fg, wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post(f"/subcontract/{order_id}/receive", data={
        "material_code": "M-FG", "quantity": "3", "price": "2",
    })
    assert resp.get_json().get("status") == "error"
    assert "库位" in resp.get_json().get("msg", "")


def test_legacy_receive_without_location_uses_warehouse_placeholder(client):
    """历史单据（无 location 值）完成收货：以仓库名占位写库位账。"""
    order_id, _raw, fg, wh = _ids()
    _enable_location_mgmt(True)
    with app_module.app.app_context():
        receive = SubcontractReceive(
            receive_no="SR-LEGACY", subcontract_order_id=order_id,
            supplier_id=1, warehouse="主仓", location="",
            status="pending", total_quantity=0, total_scrap=0)
        db.session.add(receive)
        db.session.flush()
        db.session.add(SubcontractReceiveItem(
            receive_id=receive.id, material_id=fg.id,
            quantity=3, scrap_quantity=0, unit_id=1, price=2, amount=6))
        db.session.commit()
        receive_id = receive.id
    resp = client.post(f"/subcontract/receive/{receive_id}/complete")
    assert resp.get_json().get("status") == "success", resp.get_json()
    rows = _loc_rows(fg.id, wh.id, "主仓")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 3) < 1e-6


def test_complete_and_revert_issue_sync_location_inventory(client):
    """发料单完成/反提交：总账与库位账同步扣减/恢复。"""
    order_id, raw, _fg, wh = _ids()
    _enable_location_mgmt(True)
    # 新建待发料单（带库位）
    resp = client.post("/subcontract/issue/add", data={
        "subcontract_order_id": str(order_id),
        "material_id": str(raw.id), "material_code": "M-RAW",
        "quantity": "20", "location": "主仓-A1",
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
        assert (issue.location or "") == "主仓-A1"
        issue_id = issue.id
    # 完成：总账 100→80，库位账基线行同步扣到 80
    resp = client.post(f"/subcontract/issue/{issue_id}/complete")
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock("M-RAW") - 80) < 1e-6
    rows = _loc_rows(raw.id, wh.id, "主仓-A1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 80) < 1e-6
    # 反提交：总账与库位账同步恢复
    resp = client.post(f"/subcontract/issue/{issue_id}/revert")
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock("M-RAW") - 100) < 1e-6
    rows = _loc_rows(raw.id, wh.id, "主仓-A1")
    assert abs((rows[0].quantity or 0) - 100) < 1e-6


def test_complete_and_revert_receive_sync_location_inventory(client):
    """收货单完成/反提交：总账与库位账同步增加/回退。"""
    order_id, _raw, fg, wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post("/subcontract/receive/add", data={
        "subcontract_order_id": str(order_id),
        "material_id": str(fg.id), "material_code": "M-FG",
        "quantity": "8", "price": "2", "location": "主仓-B1",
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        receive = SubcontractReceive.query.order_by(SubcontractReceive.id.desc()).first()
        assert (receive.location or "") == "主仓-B1"
        receive_id = receive.id
    resp = client.post(f"/subcontract/receive/{receive_id}/complete")
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock("M-FG") - 8) < 1e-6
    rows = _loc_rows(fg.id, wh.id, "主仓-B1")
    assert len(rows) == 1
    assert abs((rows[0].quantity or 0) - 8) < 1e-6
    # 反提交回退
    resp = client.post(f"/subcontract/receive/{receive_id}/revert")
    assert resp.get_json().get("status") == "success", resp.get_json()
    assert abs(_stock("M-FG") - 0) < 1e-6
    rows = _loc_rows(fg.id, wh.id, "主仓-B1")
    assert abs((rows[0].quantity or 0) - 0) < 1e-6


def test_add_issue_requires_location_when_enabled(client):
    """开启库位管理：新增发料单缺库位必须拒绝。"""
    order_id, raw, _fg, _wh = _ids()
    _enable_location_mgmt(True)
    resp = client.post("/subcontract/issue/add", data={
        "subcontract_order_id": str(order_id),
        "material_id": str(raw.id), "material_code": "M-RAW",
        "quantity": "1",
    })
    assert resp.get_json().get("status") == "error"
    assert "库位" in resp.get_json().get("msg", "")


def test_disabled_location_management_skips_location_inventory(client):
    """未开启库位管理：委外业务不改动库位账（向后兼容旧行为）。"""
    order_id, raw, _fg, wh = _ids()
    _enable_location_mgmt(False)
    resp = client.post(f"/subcontract/{order_id}/issue", data={
        "material_code": "M-RAW", "quantity": "10",
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        # 夹具预置的基线行保持不变，业务不新增/不扣减库位账
        rows = LocationInventory.query.filter_by(
            material_id=raw.id, warehouse_id=wh.id).all()
        assert len(rows) == 1
        assert abs((rows[0].quantity or 0) - 100) < 1e-6
    assert abs(_stock("M-RAW") - 90) < 1e-6
