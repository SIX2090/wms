# -*- coding: utf-8 -*-
"""2026-11-25 盘点单 & 库存调整单全面审计修复回归测试。

覆盖：
- P0-1: 调整单表头切换盘盈↔盘亏同步明细数量符号并校验库存
- P0-2: save_check_table 校验非法/负实盘数量
- P0-3: merge_material_duplicates 拦截同盘点单/同草稿调整单合并
- P0-4: _acquire_order_write_lock 在 native_request(atomic=False) 下加写锁并重读
- P1-1: 有历史流水的反提交调整单禁止改日期/换仓
- P1-2: 仓库更名后普通反提交保留原 StockTransaction.warehouse_id
- P1-3: 调整单保存聚合重复行盘亏数量及库位库存
- P1-4: _create_adjustment_drafts_from_check_scan 单次扣减账面 + 填库位 + validate_stocktake_adjustment
- P1-5: _warehouse_delete_blockers 校验 InventoryCheck / InventoryCheckScan
- P1-6: delete_user 校验盘点/调整/扫码引用，返回 400
- P1-7: 扫码盘点作废仅管理员或原盘点人可执行，跨仓管返回 403
- P1-8: 库位管理开启时 H5/Native 盘点强制填写库位或回退默认库位
- P1-9: _ai_check_draft & draft_check_agent 正确检查盘点与盘亏调整草稿
- P1-10: AI 创建盘点单写 frozen_at、确认台保留非默认仓及含 `/` `.` 编码
- P1-12: 新建 save_check_table 返回 X-WMS-Document-Revision 响应头
- P2-1/2/3/4/9/15: 反冲流水不计出库、中文标签、作废扫码排除、删盘点审计、导入空单拦截、打印与模板
"""
from __future__ import annotations

import io
import os
import sys
import types
from datetime import date, datetime
from pathlib import Path

import pytest
from flask import g
from openpyxl import Workbook, load_workbook
from werkzeug.security import generate_password_hash

from tests.document_revision_client import document_post

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
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

_ctx = app_module.app.app_context()


@pytest.fixture(autouse=True, scope="module")
def _release_app_ctx():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _reset():
    g.pop("_system_setting_cache", None)
    db.session.remove()
    db.drop_all()
    db.create_all()


def _seed_user(username, role="admin", password="pw"):
    u = app_module.User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        status="active",
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    return u


def _seed_warehouse(code, name, is_default=False):
    w = app_module.Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.flush()
    return w


def _seed_unit(name="个", code="PCS"):
    u = app_module.Unit(name=name, code=code)
    db.session.add(u)
    db.session.flush()
    return u


def _seed_material(code, name, unit, warehouse=None, stock=0.0, location="", status="active"):
    m = app_module.Material(code=code, name=name, unit_id=unit.id, stock=0.0, status=status)
    db.session.add(m)
    db.session.flush()
    if stock and warehouse is not None:
        m.stock = stock
        db.session.add(app_module.StockTransaction(
            material_id=m.id,
            transaction_type="in",
            quantity=stock,
            location=location or warehouse.name,
            warehouse_id=warehouse.id,
            created_at=datetime.now(),
        ))
        if location:
            db.session.add(app_module.LocationInventory(
                material_id=m.id,
                warehouse_id=warehouse.id,
                location=location,
                quantity=stock,
            ))
    db.session.flush()
    return m


def _login_web(client, user):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def _bearer(client, username, password="pw"):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _set_setting(key, value):
    app_module.set_system_setting(key, value)
    db.session.commit()
    g.pop("_system_setting_cache", None)


def test_p0_1_header_only_adjustment_type_flip_updates_sign_and_checks_loss_stock():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh, stock=3.0)
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    r_create = client.post("/adjustment/add", json={
        "date": "2026-11-25",
        "adjustment_type": "surplus",
        "warehouse_id": wh.id,
        "items": [{"material_id": mat.id, "quantity": 5, "reason": "盘盈"}],
    })
    assert r_create.status_code == 200, r_create.get_data(as_text=True)
    adj_id = r_create.get_json()["id"]

    # Header-only flip surplus -> loss must reject when warehouse stock (3) < loss qty (5)
    r_bad = document_post(client, "/adjustment/add", json={
        "order_id": adj_id,
        "date": "2026-11-25",
        "adjustment_type": "loss",
        "warehouse_id": wh.id,
        "remark": "改为盘亏",
    })
    assert r_bad.status_code == 400
    assert "库存不足" in (r_bad.get_json().get("msg") or "")

    # Top up stock to 10 -> header-only flip succeeds and flips item.quantity sign to -5
    mat.stock = 10.0
    db.session.add(app_module.StockTransaction(
        material_id=mat.id, transaction_type="in", quantity=7.0,
        location=wh.name, warehouse_id=wh.id, created_at=datetime.now(),
    ))
    db.session.commit()

    r_ok = document_post(client, "/adjustment/add", json={
        "order_id": adj_id,
        "date": "2026-11-25",
        "adjustment_type": "loss",
        "warehouse_id": wh.id,
        "remark": "改为盘亏",
    })
    assert r_ok.status_code == 200, r_ok.get_data(as_text=True)
    adj = db.session.get(app_module.AdjustmentOrder, adj_id)
    assert adj.adjustment_type == "loss"
    assert adj.items[0].quantity == -5.0

    r_done = document_post(client, f"/adjustment/{adj_id}/complete", json={})
    assert r_done.status_code == 200, r_done.get_data(as_text=True)
    db.session.expire_all()
    assert db.session.get(app_module.Material, mat.id).stock == 5.0


def test_p0_2_and_p1_12_save_check_table_validates_actual_stock_and_emits_revision():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh, stock=10.0)
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    for bad_actual in (-3, "not-a-number"):
        r_bad = client.post("/check/save_table", json={
            "date": "2026-11-25",
            "header": {"warehouse_id": wh.id, "remark": ""},
            "items": [{"material_id": mat.id, "actual_stock": bad_actual}],
        })
        assert r_bad.status_code == 400, r_bad.get_data(as_text=True)

    r_ok = client.post("/check/save_table", json={
        "date": "2026-11-25",
        "header": {"warehouse_id": wh.id, "remark": "新建"},
        "items": [{"material_id": mat.id, "actual_stock": 8}],
    })
    assert r_ok.status_code == 200, r_ok.get_data(as_text=True)
    assert r_ok.headers.get("X-WMS-Document-Revision"), "新建盘点单保存必须返回文档版本头"


def test_p0_3_merge_material_duplicates_blocks_shared_check_and_pending_adjustment():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    m1 = _seed_material("M001", "料1", unit, wh, stock=10.0)
    m2 = _seed_material("M002", "料2", unit, wh, stock=5.0)
    ck = app_module.InventoryCheck(check_no="CK-M1", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck)
    db.session.flush()
    db.session.add_all([
        app_module.InventoryCheckItem(inventory_check_id=ck.id, material_id=m1.id, system_stock=10, actual_stock=10, difference=0),
        app_module.InventoryCheckItem(inventory_check_id=ck.id, material_id=m2.id, system_stock=5, actual_stock=5, difference=0),
    ])
    db.session.commit()

    with pytest.raises(ValueError, match="盘点单"):
        app_module.merge_material_duplicates(m1.id, m2.id, identity_confirmed=True)

    for row in list(ck.items):
        db.session.delete(row)
    db.session.delete(ck)
    adj = app_module.AdjustmentOrder(
        adjustment_no="ADJ-M1", adjustment_type="surplus", source_type="manual",
        warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add(adj)
    db.session.flush()
    db.session.add_all([
        app_module.AdjustmentOrderItem(adjustment_order_id=adj.id, material_id=m1.id, quantity=2),
        app_module.AdjustmentOrderItem(adjustment_order_id=adj.id, material_id=m2.id, quantity=3),
    ])
    db.session.commit()

    with pytest.raises(ValueError, match="待审库存调整单"):
        app_module.merge_material_duplicates(m1.id, m2.id, identity_confirmed=True)


def test_p0_4_acquire_order_write_lock_runs_lock_when_native_request_not_atomic():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    ck = app_module.InventoryCheck(check_no="CK-LOCK", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck)
    db.session.commit()

    with app_module.app.test_request_context("/api/stocktake", method="POST"):
        g.native_request = {"atomic": False}
        locked, ok = app_module._acquire_order_write_lock(app_module.InventoryCheck, ck.id, "pending")
        assert ok is True
        assert locked is not None and locked.id == ck.id
        db.session.rollback()


def test_p1_1_and_p1_2_reverted_adjustment_locks_date_warehouse_and_renamed_wh_revert():
    _reset()
    admin = _seed_user("admin", "admin")
    wh1 = _seed_warehouse("W1", "旧一仓", is_default=True)
    wh2 = _seed_warehouse("W2", "二仓")
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh1, stock=10.0)
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    r_create = client.post("/adjustment/add", json={
        "date": "2026-11-25",
        "adjustment_type": "surplus",
        "warehouse_id": wh1.id,
        "items": [{"material_id": mat.id, "quantity": 4, "reason": "盘盈"}],
    })
    assert r_create.status_code == 200
    adj_id = r_create.get_json()["id"]
    assert document_post(client, f"/adjustment/{adj_id}/complete", json={}).status_code == 200

    # Rename warehouse before reverting -> reversal transaction must retain wh1.id
    wh1.name = "新一仓"
    db.session.commit()

    r_rev = document_post(client, f"/adjustment/{adj_id}/revert", json={})
    assert r_rev.status_code == 200, r_rev.get_data(as_text=True)
    rev_txn = app_module.StockTransaction.query.filter_by(
        reference_type="adjustment", reference_id=adj_id, transaction_type="revert_adjustment_in"
    ).one()
    assert rev_txn.warehouse_id == wh1.id

    # Reverted adjustment with history cannot change date or warehouse
    r_date = document_post(client, "/adjustment/add", json={
        "order_id": adj_id,
        "date": "2026-11-20",
        "adjustment_type": "surplus",
        "warehouse_id": wh1.id,
        "items": [{"material_id": mat.id, "quantity": 4, "reason": "盘盈"}],
    })
    assert r_date.status_code == 400
    assert "不能更改日期" in (r_date.get_json().get("msg") or "")

    r_wh = document_post(client, "/adjustment/add", json={
        "order_id": adj_id,
        "date": "2026-11-25",
        "adjustment_type": "surplus",
        "warehouse_id": wh2.id,
        "items": [{"material_id": mat.id, "quantity": 4, "reason": "盘盈"}],
    })
    assert r_wh.status_code == 400
    assert "不能更换仓库" in (r_wh.get_json().get("msg") or "")


def test_p1_3_adjustment_aggregates_duplicate_loss_rows_and_location_stock():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh, stock=10.0, location="A1")
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    # 6 + 6 = 12 > 10 must be rejected
    r1 = client.post("/adjustment/add", json={
        "date": "2026-11-25",
        "adjustment_type": "loss",
        "warehouse_id": wh.id,
        "items": [
            {"material_id": mat.id, "quantity": 6},
            {"material_id": mat.id, "quantity": 6},
        ],
    })
    assert r1.status_code == 400
    assert "库存不足" in (r1.get_json().get("msg") or "")

    # Location management ON: loc A1 has 6, warehouse has 10; 4 + 4 at A1 = 8 > 6 must be rejected
    _set_setting("location_management_enabled", "1")
    loc_row = app_module.LocationInventory.query.filter_by(material_id=mat.id, warehouse_id=wh.id, location="A1").one()
    loc_row.quantity = 6.0
    db.session.add(app_module.LocationInventory(material_id=mat.id, warehouse_id=wh.id, location="B1", quantity=4.0))
    db.session.commit()

    r2 = client.post("/adjustment/add", json={
        "date": "2026-11-25",
        "adjustment_type": "loss",
        "warehouse_id": wh.id,
        "items": [
            {"material_id": mat.id, "quantity": 4, "location": "A1"},
            {"material_id": mat.id, "quantity": 4, "location": "A1"},
        ],
    })
    assert r2.status_code == 400
    assert "库位 A1" in (r2.get_json().get("msg") or "")


def test_p1_4_check_scan_adjustment_single_book_deduction_and_void_validation():
    _reset()
    from services.stocktake import validate_stocktake_adjustment

    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    wh2 = _seed_warehouse("W2", "二仓")
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh, stock=100.0)
    scan = app_module.InventoryCheckScan(
        check_no="CS-001", date=date.today(), warehouse=wh.name,
        status="completed", operator_id=admin.id,
    )
    db.session.add(scan)
    db.session.flush()
    # Two pallets (40 + 70 = 110 vs book 100 => net +10 surplus, NOT 40-100 + 70-100 = -90)
    db.session.add_all([
        app_module.InventoryCheckScanItem(check_scan_id=scan.id, material_id=mat.id, area="A1", system_stock=100, actual_stock=40, difference=-60),
        app_module.InventoryCheckScanItem(check_scan_id=scan.id, material_id=mat.id, area="A2", system_stock=100, actual_stock=70, difference=-30),
    ])
    db.session.commit()

    created, create_err = app_module._create_adjustment_drafts_from_check_scan(scan)
    assert create_err is None, create_err
    db.session.commit()
    assert len(created) == 1
    adj = created[0]
    assert adj.adjustment_type == "surplus"
    assert len(adj.items) == 1
    assert adj.items[0].quantity == 10.0
    assert adj.items[0].location == "A1"

    assert validate_stocktake_adjustment(adj, wh) is None
    scan.status = "void"
    db.session.commit()
    assert "已作废" in (validate_stocktake_adjustment(adj, wh) or "")
    scan.status = "completed"
    adj.warehouse = wh2.name
    db.session.commit()
    assert "不一致" in (validate_stocktake_adjustment(adj, wh2) or "")


def test_p1_5_and_p1_6_warehouse_and_user_delete_blockers():
    _reset()
    admin = _seed_user("admin", "admin")
    staff = _seed_user("staff1", "warehouse")
    staff.status = "disabled"
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    ck = app_module.InventoryCheck(check_no="CK-BLK", warehouse=wh.name, status="pending", operator_id=staff.id)
    db.session.add(ck)
    db.session.commit()

    blockers = app_module._warehouse_delete_blockers(wh)
    assert any("盘点单" in label for label, _ in blockers)

    client = app_module.app.test_client()
    _login_web(client, admin)
    r_del = client.post("/user/delete", json={"ids": [staff.id]})
    assert r_del.status_code == 400
    assert "盘点单" in (r_del.get_json().get("msg") or "")


def test_p1_7_cross_user_scan_void_forbidden_while_owner_and_admin_allowed():
    _reset()
    admin = _seed_user("admin", "admin")
    u1 = _seed_user("wh1", "warehouse")
    viewer = _seed_user("viewer1", "viewer")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    _seed_material("M001", "轴承", unit, wh, stock=20.0)
    ck = app_module.InventoryCheck(check_no="CK-VOID", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck)
    db.session.commit()

    client = app_module.app.test_client()
    h1 = _bearer(client, "wh1")
    hv = _bearer(client, "viewer1")

    r_sub = client.post("/api/stocktake", headers=h1, json={
        "mode": "scan", "warehouse": wh.name, "check_id": ck.id,
        "lines": [{"material_code": "M001", "actual_stock": 18}],
    })
    assert r_sub.status_code == 200, r_sub.get_data(as_text=True)
    scan = app_module.InventoryCheckScan.query.one()

    # Non-warehouse viewer cannot void scans on either native or H5 endpoint
    r_forbid_native = client.post("/api/stocktake/void", headers=hv, json={"check_no": scan.check_no})
    assert r_forbid_native.status_code == 403
    r_forbid_h5 = client.post(f"/mobile/api/check_scan/{scan.id}/void", headers=hv)
    assert r_forbid_h5.status_code == 403

    # Warehouse operator can void and audit records the acting user
    r_ok = client.post("/api/stocktake/void", headers=h1, json={"check_no": scan.check_no})
    assert r_ok.status_code == 200, r_ok.get_data(as_text=True)
    assert db.session.get(app_module.InventoryCheckScan, scan.id).status == "void"
    audit = app_module.OperationAudit.query.filter_by(operation="void_check_scan", target_id=scan.id).one()
    assert audit.user_id == u1.id


def test_p1_8_location_management_requires_area_on_mobile_and_native_stocktake():
    _reset()
    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    _seed_material("M001", "轴承", unit, wh, stock=20.0, location="A1")
    ck = app_module.InventoryCheck(check_no="CK-LOC", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck)
    db.session.commit()
    _set_setting("location_management_enabled", "1")

    client = app_module.app.test_client()
    h = _bearer(client, "admin")

    # Empty area without default location -> 400 on both native and H5
    r_n1 = client.post("/api/stocktake", headers=h, json={
        "mode": "scan", "warehouse": wh.name, "check_id": ck.id,
        "lines": [{"material_code": "M001", "actual_stock": 19, "area": ""}],
    })
    assert r_n1.status_code == 400

    r_h1 = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check", "code": "M001", "warehouse": wh.name,
        "actual_stock": 19, "check_id": ck.id, "area": "",
    })
    assert r_h1.status_code == 400

    # With area -> succeeds
    r_n2 = client.post("/api/stocktake", headers=h, json={
        "mode": "scan", "warehouse": wh.name, "check_id": ck.id,
        "lines": [{"material_code": "M001", "actual_stock": 19, "area": "A1"}],
    })
    assert r_n2.status_code == 200, r_n2.get_data(as_text=True)


def test_p1_9_and_p1_10_ai_check_draft_and_confirmed_draft_fixes():
    _reset()
    from ai.agents.draft_check import draft_check_agent, format_draft_check_report

    admin = _seed_user("admin", "admin")
    wh1 = _seed_warehouse("W1", "默认仓", is_default=True)
    wh2 = _seed_warehouse("W2", "项目二仓")
    unit = _seed_unit()
    m_special = _seed_material("M-01/A.2", "特种轴承", unit, wh2, stock=5.0)
    m_inactive = _seed_material("M-OFF", "停用料", unit, wh2, stock=5.0, status="inactive")
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    with app_module.app.test_request_context("/"):
        from flask_login import login_user
        login_user(admin)
        # Confirmed check draft preserves non-default warehouse and special code + sets frozen_at
        draft, err = app_module._ai_create_confirmed_document_draft(
            "check",
            [{"material_id": m_special.id, "quantity": 3}],
            source_text="请盘点 项目二仓",
        )
        assert err is None, err
        ck = app_module.InventoryCheck.query.filter_by(check_no=draft["order_no"]).one()
        assert ck.warehouse == wh2.name
        assert ck.frozen_at is not None
        assert ck.items[0].material_id == m_special.id

        # _ai_check_draft on uncounted check reports uncounted warning, NOT "数量必须大于 0"
        reply, _cards = app_module._ai_check_draft("check", ck)
        assert "未录入实盘" in reply
        assert "数量必须大于 0" not in reply

        # Inactive material blocked in AI check draft
        _, err_inact = app_module._ai_create_check_draft(
            "盘点 项目二仓", manual_confirmation=True, resolved_items=[(m_inactive, 1)]
        )
        assert err_inact and "已停用" in err_inact

        # Confirmed adjustment draft (loss > stock rejected; loss <= stock succeeds)
        _, err_over = app_module._ai_create_confirmed_document_draft(
            "adjustment",
            [{"material_id": m_special.id, "quantity": 9}],
            source_text="项目二仓 盘亏",
            adjustment_type="loss",
        )
        assert err_over and "库存不足" in err_over

        adj_draft, err_adj = app_module._ai_create_confirmed_document_draft(
            "adjustment",
            [{"material_id": m_special.id, "quantity": 2}],
            source_text="项目二仓 盘亏",
            adjustment_type="loss",
        )
        assert err_adj is None, err_adj
        adj = app_module.AdjustmentOrder.query.filter_by(adjustment_no=adj_draft["order_no"]).one()
        assert adj.warehouse == wh2.name
        assert adj.adjustment_type == "loss"
        assert adj.items[0].quantity == -2.0
        adj_reply, _ = app_module._ai_check_draft("adjustment", adj)
        assert "检查通过" in adj_reply

    # draft_check_agent: multi-pallet check allowed & adjustment header reason not required
    fake_check = types.SimpleNamespace(
        warehouse="项目二仓",
        items=[
            types.SimpleNamespace(material_id=1, actual_stock=3, has_actual_count=True),
            types.SimpleNamespace(material_id=1, actual_stock=4, has_actual_count=True),
        ],
    )
    check_run = draft_check_agent(admin.id, fake_check, order_type="check")
    check_report = format_draft_check_report(check_run)
    assert "检查通过" in check_report, check_report

    fake_adj = types.SimpleNamespace(
        warehouse="项目二仓",
        adjustment_type="loss",
        items=[types.SimpleNamespace(material_id=1, quantity=-2)],
    )
    adj_run = draft_check_agent(admin.id, fake_adj, order_type="adjustment")
    adj_report = format_draft_check_report(adj_run)
    assert "检查通过" in adj_report, adj_report


def test_p2_1_p2_2_p2_3_p2_4_p2_9_p2_15_labels_meta_audit_and_templates():
    _reset()
    from doc_print_excel import DOC_EXCEL_PRINT_TYPES

    admin = _seed_user("admin", "admin")
    wh = _seed_warehouse("W1", "一仓", is_default=True)
    unit = _seed_unit()
    mat = _seed_material("M001", "轴承", unit, wh, stock=20.0)
    db.session.commit()

    # P2-1: _outbound_txn_condition ignores negative reversal transactions
    t_rev = app_module.StockTransaction(
        material_id=mat.id, transaction_type="revert_adjustment_in",
        quantity=-5.0, location=wh.name, warehouse_id=wh.id, created_at=datetime.now(),
    )
    t_out = app_module.StockTransaction(
        material_id=mat.id, transaction_type="adjustment_out",
        quantity=-2.0, location=wh.name, warehouse_id=wh.id, created_at=datetime.now(),
    )
    db.session.add_all([t_rev, t_out])
    db.session.commit()
    out_ids = {t.id for t in app_module.StockTransaction.query.filter(app_module._outbound_txn_condition()).all()}
    assert t_out.id in out_ids
    assert t_rev.id not in out_ids

    # P2-2: labels & reference links
    assert "revert_adjustment_in" in app_module.TRANSACTION_TYPE_LABELS
    assert app_module.REPORT_REFERENCE_LINKS["inventory_check_scan"]["model"] is app_module.InventoryCheckScan
    assert "check" in app_module.REPORT_REFERENCE_LINKS

    # P2-3 & P2-4 & P2-9: void scan excluded from meta; delete_check writes OperationAudit; partial adjustment_status
    ck = app_module.InventoryCheck(check_no="CK-META", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck)
    db.session.flush()
    scan_void = app_module.InventoryCheckScan(check_no="CS-V", date=date.today(), warehouse=wh.name, status="void", check_id=ck.id, operator_id=admin.id)
    scan_ok = app_module.InventoryCheckScan(check_no="CS-OK", date=date.today(), warehouse=wh.name, status="completed", check_id=ck.id, operator_id=admin.id)
    db.session.add_all([scan_void, scan_ok])
    db.session.flush()
    db.session.add_all([
        app_module.AdjustmentOrder(adjustment_no="ADJ-P1", adjustment_type="surplus", source_type="check_scan", source_id=scan_ok.id, warehouse=wh.name, status="completed", operator_id=admin.id),
        app_module.AdjustmentOrder(adjustment_no="ADJ-P2", adjustment_type="loss", source_type="check_scan", source_id=scan_ok.id, warehouse=wh.name, status="pending", operator_id=admin.id),
    ])
    db.session.commit()

    meta = app_module._build_check_batch_meta(ck)
    assert meta["scan_count"] == 1
    assert [s["check_no"] for s in meta["scans"]] == ["CS-OK"]

    client = app_module.app.test_client()
    h = _bearer(client, "admin")
    r_list = client.get(f"/api/mobile/stocktake/list?warehouse_id={wh.id}", headers=h)
    assert r_list.status_code == 200
    items = r_list.get_json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["adjustment_status"] == "pending"

    # Mobile in_out_detail returns Chinese transaction type label
    r_rpt = client.get(f"/api/mobile/report/in_out_detail?warehouse_id={wh.id}", headers=h)
    assert r_rpt.status_code == 200
    labels = {row["transaction_type_label"] for row in r_rpt.get_json()["data"]["items"]}
    assert "库存调整入库冲回" in labels
    assert "revert_adjustment_in" not in labels

    # Web routes checks
    _login_web(client, admin)

    # P2-4: add_check category without category_id rejected
    r_cat = client.post("/check/add", data={"warehouse_id": str(wh.id), "scope": "category", "category_id": ""})
    assert r_cat.status_code == 400

    # P2-4: delete empty check writes OperationAudit
    ck_del = app_module.InventoryCheck(check_no="CK-DEL-AUD", warehouse=wh.name, status="pending", operator_id=admin.id)
    db.session.add(ck_del)
    db.session.commit()
    ck_del_id = ck_del.id
    r_del = document_post(client, f"/check/{ck_del_id}/delete")
    assert r_del.status_code == 200
    assert app_module.OperationAudit.query.filter_by(operation="delete_check", target_id=ck_del_id).first() is not None

    # P2-4: import_check with all invalid rows leaves no empty check order
    wb = Workbook()
    ws = wb.active
    ws.append(["单据编号", "日期", "仓库", "物料编码", "物料名称", "实际库存"])
    ws.append(["CK-EMPTY-BAD", "2026-11-25", wh.name, "NO-SUCH-MAT", "不存在", "5"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    client.post("/check/import", data={"file": (buf, "bad.xlsx")}, content_type="multipart/form-data")
    assert app_module.InventoryCheck.query.filter_by(check_no="CK-EMPTY-BAD").first() is None

    # P2-15: print_adjustment hides fake total_amount and uses Chinese source label; export_check_template has 仓库 & 区域/库位
    adj_p = app_module.AdjustmentOrder(
        adjustment_no="ADJ-PRT", adjustment_type="surplus", source_type="manual",
        warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add(adj_p)
    db.session.flush()
    db.session.add(app_module.AdjustmentOrderItem(adjustment_order_id=adj_p.id, material_id=mat.id, quantity=2))
    db.session.commit()
    r_prt = client.get(f"/adjustment/{adj_p.id}/print")
    assert r_prt.status_code == 200
    html = r_prt.get_data(as_text=True)
    assert "手工新增" in html
    assert "金额合计" not in html

    r_tpl = client.get("/export/template/check")
    assert r_tpl.status_code == 200
    tpl_wb = load_workbook(io.BytesIO(r_tpl.data))
    headers = [c.value for c in tpl_wb.active[1]]
    assert "仓库" in headers and "区域/库位" in headers
    assert DOC_EXCEL_PRINT_TYPES["check"]["columns"][-1] == ("库位/区域", "area", 12)
