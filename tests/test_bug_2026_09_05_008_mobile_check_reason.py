# -*- coding: utf-8 -*-
"""BUG-2026-09-05-008 / FEATURE-2026-09-05-004 回归：手机盘点填行级差异原因。

问题：明细行有 reason 字段、PC 表格与 Excel 导入都能填差异原因，但手机
扫码只有"盘点区域"，盘出差异想当场备注（破损/串货/待查）只能回 PC 补填。

修复：
- scan_submit(check) 读取 payload 的 reason 并透传给 `_apply_scan_to_batch`；
- 已有行（PC 预置）被补盘时写入 reason（空值不覆盖 PC 已填原因）；
- 扫码新建行保留「手机扫码盘点」哨兵前缀，原因以「：」追加
  （`手机扫码盘点：破损2件`）——`_void_check_scan` 原按 `reason ==
  '手机扫码盘点'` 精确相等识别本次新建行，带了原因会误判为 PC 预置行、
  撤销时只重置不删除留下孤儿未盘行；故同步改为**前缀判定**
  `startswith('手机扫码盘点')`（精确哨兵仍匹配，向后兼容）；
- mobile_scan.html 盘点模式加「差异原因（可选）」输入框，随每笔扫码清空。

覆盖：
T1. 手机填原因盘 PC 预置行 → 批次行 reason 写入
T2. 不填原因时不覆盖 PC 已填原因
T3. 手机新建行：reason = 「手机扫码盘点：原因」，无原因时为纯哨兵
T4. 带原因的扫码新建行，撤销（void）仍整行删除而非重置为未盘
T5. 模板契约：差异原因输入框 + payload 透传 + 清空
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_ctx = app_module.app.app_context()

import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _seed_scene():
    """A仓；M001 预置未盘行（PC 已填原因"待查"）、M002 预置未盘行、M-NEW 无行。"""
    from werkzeug.security import generate_password_hash
    from app import (InventoryCheck, InventoryCheckItem, Material,
                     StockTransaction, User, Warehouse)
    db.drop_all()
    db.create_all()
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    wh = Warehouse(code="WA", name="A仓", status="active", is_default=True)
    db.session.add_all([admin, wh])
    db.session.commit()
    mats = {}
    for code, qty in [("M001", 10.0), ("M002", 20.0), ("M-NEW", 0.0)]:
        m = Material(code=code, name=f"物料{code}", stock=qty)
        db.session.add(m)
        db.session.flush()
        if qty:
            db.session.add(StockTransaction(
                material_id=m.id, transaction_type="in", quantity=qty,
                location=wh.name, warehouse_id=wh.id, created_at=datetime.now()))
        mats[code] = m
    db.session.commit()
    check = InventoryCheck(check_no="CK-R-001", warehouse="A仓",
                           status="pending", operator_id=admin.id)
    db.session.add(check)
    db.session.flush()
    db.session.add_all([
        InventoryCheckItem(inventory_check_id=check.id, material_id=mats["M001"].id,
                           system_stock=10, actual_stock=10, difference=0,
                           reason="待查"),
        InventoryCheckItem(inventory_check_id=check.id, material_id=mats["M002"].id,
                           system_stock=20, actual_stock=20, difference=0),
    ])
    db.session.commit()
    return check, mats


def _client():
    c = app_module.app.test_client()
    r = c.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), r.get_data(as_text=True)
    return c


def _bearer(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _scan(client, h, code, actual, check_id, reason=None):
    payload = {"mode": "check", "code": code, "warehouse": "A仓",
               "actual_stock": actual, "check_id": check_id}
    if reason is not None:
        payload["reason"] = reason
    return client.post("/mobile/api/scan_submit", headers=h, json=payload)


def _row(code, check_id):
    from app import InventoryCheckItem, Material
    m = Material.query.filter_by(code=code).one()
    return InventoryCheckItem.query.filter_by(
        inventory_check_id=check_id, material_id=m.id).first()


# T1 ───────────────────────────────────────────────────────────────
def test_t1_reason_written_to_preset_row():
    check, _m = _seed_scene()
    client = _client()
    h = _bearer(client)
    r = _scan(client, h, "M002", 17, check.id, reason="破损3件")
    assert r.status_code == 200, r.get_data(as_text=True)
    row = _row("M002", check.id)
    assert row.reason == "破损3件"
    assert row.actual_stock == 17.0


# T2 ───────────────────────────────────────────────────────────────
def test_t2_empty_reason_keeps_pc_reason():
    check, _m = _seed_scene()
    client = _client()
    h = _bearer(client)
    r = _scan(client, h, "M001", 9, check.id)  # 不传 reason
    assert r.status_code == 200, r.get_data(as_text=True)
    row = _row("M001", check.id)
    assert row.reason == "待查"  # PC 已填原因不被清空
    assert row.actual_stock == 9.0
    # 撤销本次扫码（重置回未盘）后带原因重盘 → 覆盖为手机填的原因
    rv = client.post(f"/mobile/api/check_scan/{r.get_json()['data']['check_id']}/void")
    assert rv.status_code == 200, rv.get_data(as_text=True)
    assert _row("M001", check.id).counted_at is None
    r2 = _scan(client, h, "M001", 9, check.id, reason="串货")
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert _row("M001", check.id).reason == "串货"


# T3 ───────────────────────────────────────────────────────────────
def test_t3_new_row_sentinel_with_reason():
    check, _m = _seed_scene()
    client = _client()
    h = _bearer(client)
    r = _scan(client, h, "M-NEW", 5, check.id, reason="盘盈待查")
    assert r.status_code == 200, r.get_data(as_text=True)
    row = _row("M-NEW", check.id)
    assert row.reason == "手机扫码盘点：盘盈待查"
    assert row.counted_at is not None


# T4 ───────────────────────────────────────────────────────────────
def test_t4_void_still_deletes_row_with_reason():
    """带原因的扫码新建行，撤销必须整行删除（前缀判定），不能只重置成未盘。"""
    from app import InventoryCheckItem
    check, _m = _seed_scene()
    client = _client()
    h = _bearer(client)
    r = _scan(client, h, "M-NEW", 5, check.id, reason="盘盈待查")
    scan_id = r.get_json()["data"]["check_id"]
    created = _row("M-NEW", check.id)
    assert created is not None
    before = InventoryCheckItem.query.filter_by(inventory_check_id=check.id).count()
    rv = client.post(f"/mobile/api/check_scan/{scan_id}/void")
    assert rv.status_code == 200, rv.get_data(as_text=True)
    after = InventoryCheckItem.query.filter_by(inventory_check_id=check.id).count()
    assert after == before - 1
    assert _row("M-NEW", check.id) is None  # 整行删除，无孤儿未盘行残留


# T5 ───────────────────────────────────────────────────────────────
def test_t5_template_contract():
    tpl = (ROOT / "app" / "templates" / "mobile_scan.html").read_text(encoding="utf-8")
    assert 'id="scanReasonInput"' in tpl
    assert "差异原因（可选）" in tpl
    assert "reason: scanReasonInput ? scanReasonInput.value : ''" in tpl
    assert "if (scanReasonInput) scanReasonInput.value = '';" in tpl
