# -*- coding: utf-8 -*-
"""区域分行盘点回归（多人分区盘，物料分散多处汇总正确）。

用户场景：几个人分区/分仓盘点，同一物料（如 M001）分处多个区域
（A1/A2），各盘各的区，系统须把各区实盘分行记录并正确合计，
生成差异时只按"实盘合计 − 仓库账面"记一笔，不能多区重复扣减。

覆盖：
T1. 同物料不同区域两次扫码 → 批次按 (物料, 区域) 分行两行，
    InventoryCheckItem.area / InventoryCheckScanItem.area 均落库
T2. 同物料同区域再次扫码 → 拒绝（提示已由谁盘点），不覆盖
T3. 分区盘点完成 → 调整草稿该物料只生成一条净额：账面 20、
    实盘 A1=12 + A2=7 = 19 → 净 −1（而非把账面扣两次 −8−13=−21）
T4. 未填区域（原模式）同物料仍只一行，行为不回归
T5. 模型/建表含 area 列（inventory_check_item / inventory_check_scan_item）

注意（:memory: 跨 app context 换连接丢表）：本模块所有 DB 与 HTTP 调用
都在同一个 app context 内完成，test_client 请求不脱离外层 ctx。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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

_ctx = app_module.app.app_context()

# R7：模块级 autouse fixture 包 push/pop（收集期不压栈）。
import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _module_app_ctx():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _reset_db():
    db.drop_all()
    db.create_all()


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code="M001", global_stock=0.0):
    from app import Material
    m = Material(code=code, name=f"物料{code}", stock=global_stock)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_txn_stock(material, warehouse, qty):
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id, transaction_type="in", quantity=qty,
        location=warehouse.name, warehouse_id=warehouse.id, created_at=datetime.now()))
    db.session.commit()


def _scan(client, code, warehouse, actual, area=None, check_id=None):
    payload = {"mode": "check", "code": code, "warehouse": warehouse,
               "actual_stock": actual}
    if area is not None:
        payload["area"] = area
    if check_id is not None:
        payload["check_id"] = check_id
    return client.post("/mobile/api/scan_submit", json=payload)


def _new_env():
    """重置并返回 (admin, m, batch)，批次 A 仓待扫。"""
    from app import InventoryCheck, User
    _reset_db()
    _seed_admin()
    admin = User.query.first()
    m = _seed_material("M001", 0.0)
    wa = _seed_warehouse("WA", "A仓")
    wb = _seed_warehouse("WB", "B仓")
    _seed_txn_stock(m, wa, 20)
    batch = InventoryCheck(check_no=f"CK2609{datetime.now().microsecond % 100000:05d}",
                           warehouse="A仓", status="pending", operator_id=admin.id, frozen_at=None)
    db.session.add(batch)
    db.session.commit()
    return admin, m, batch


def test_t1_same_material_split_rows_by_area():
    """T1：同物料 A1=12、A2=7 → 批次两行，area 落库。"""
    with app_module.app.app_context():
        _a, _m, batch = _new_env()
        batch_id = batch.id
        c = app_module.app.test_client()
        _login_web(c)
        assert _scan(c, "M001", "A仓", 12, area="A1", check_id=batch.id).status_code == 200
        assert _scan(c, "M001", "A仓", 7, area="A2", check_id=batch.id).status_code == 200

        from app import InventoryCheck, InventoryCheckScanItem
        check = db.session.get(InventoryCheck, batch_id)
        rows = sorted(check.items, key=lambda i: i.area)
        assert len(rows) == 2, "同物料两个区域应占两行"
        assert [r.area for r in rows] == ["A1", "A2"]
        assert rows[0].actual_stock == 12 and rows[1].actual_stock == 7
        areas = {si.area for si in InventoryCheckScanItem.query.all()}
        assert {"A1", "A2"} <= areas


def test_t2_same_area_rescan_rejected():
    """T2：同一区域重复扫码被拒，不覆盖已盘数。"""
    with app_module.app.app_context():
        _a, _m, batch = _new_env()
        batch_id = batch.id
        c = app_module.app.test_client()
        _login_web(c)
        assert _scan(c, "M001", "A仓", 12, area="A1", check_id=batch.id).status_code == 200
        r = _scan(c, "M001", "A仓", 9, area="A1", check_id=batch.id)
        assert r.status_code == 400, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "error"
        assert "已由" in body["msg"] and "A1" in body["msg"], body
        from app import InventoryCheck
        check = db.session.get(InventoryCheck, batch_id)
        assert len(check.items) == 1
        assert check.items[0].actual_stock == 12, "同区重复扫码不得覆盖已盘数"


def test_t3_complete_creates_single_net_adjustment():
    """T3：分区盘点完成 → 该物料只生成一条净额调整（19−20=−1），不是 −21。"""
    with app_module.app.app_context():
        _a, _m, batch = _new_env()
        batch_id = batch.id
        c = app_module.app.test_client()
        _login_web(c)
        _scan(c, "M001", "A仓", 12, area="A1", check_id=batch.id)
        _scan(c, "M001", "A仓", 7, area="A2", check_id=batch.id)

        r = c.post(f"/check/{batch_id}/complete")
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["status"] == "success", r.get_json()

        from app import AdjustmentOrder, AdjustmentOrderItem
        draft = AdjustmentOrder.query.filter_by(source_type="check", source_id=batch_id).first()
        assert draft is not None, "应有调整草稿"
        items = AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).all()
        assert len(items) == 1, f"分区差异必须合并成一条净调整，实际 {len(items)} 条"
        assert items[0].quantity == -1.0, f"净差异应为 19-20=-1，实际 {items[0].quantity}"


def test_t4_without_area_keeps_single_row():
    """T4：不填区域=原行为，同物料扫第二次被拒，批次只有一行。"""
    with app_module.app.app_context():
        _a, _m, batch = _new_env()
        batch_id = batch.id
        c = app_module.app.test_client()
        _login_web(c)
        assert _scan(c, "M001", "A仓", 12, check_id=batch.id).status_code == 200
        r = _scan(c, "M001", "A仓", 7, check_id=batch.id)
        assert r.status_code == 400
        from app import InventoryCheck
        check = db.session.get(InventoryCheck, batch_id)
        assert len(check.items) == 1
        assert (check.items[0].area or "") == ""


def test_t5_area_columns_exist():
    """T5：两张盘点明细表均含 area 列。"""
    with app_module.app.app_context():
        _reset_db()
        cols_i = [c[1] for c in db.session.execute(db.text("PRAGMA table_info(inventory_check_item)")).fetchall()]
        cols_s = [c[1] for c in db.session.execute(db.text("PRAGMA table_info(inventory_check_scan_item)")).fetchall()]
        assert "area" in cols_i
        assert "area" in cols_s
