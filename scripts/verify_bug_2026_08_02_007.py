#!/usr/bin/env python3
"""
BUG-2026-08-02-013 回归测试：调拨/盘点/调整三类路由补 location_management_enabled() 判断。

覆盖：
  1. 静态检查：complete_transfer / revert_transfer 含 location_management_enabled() 守卫
  2. 静态检查：_create_adjustment_drafts_from_check / _scan 传递 warehouse 到调整草稿
  3. 动态检查：未开启库位管理时 complete_transfer 不写 LocationInventory（只记流水）
  4. 动态检查：complete_check 生成的调整草稿带 warehouse
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import db  # noqa: E402

flask_app = app_module.app
results = []


def record(checkpoint: str, ok: bool, detail: str) -> None:
    results.append((checkpoint, "PASS" if ok else "FAIL", detail))
    print(f"{'PASS' if ok else 'FAIL'}: {checkpoint} - {detail}")


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def _func_body(name: str) -> str:
    m = re.search(rf"^def\s+{re.escape(name)}\s*\([^)]*\):", app_py, re.M)
    if not m:
        return ""
    nxt = re.search(r"^def\s+\w+\s*\(", app_py[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(app_py)
    return app_py[m.start():end]


# ============== 静态检查 ==============
app_py = read_text("app/app.py")

# 1. complete_transfer / revert_transfer 含 location_management_enabled() 守卫
body_ct = _func_body("complete_transfer")
record(
    "S1-complete-transfer-location-guard",
    "use_location = location_management_enabled()" in body_ct
    and "if use_location:" in body_ct,
    "complete_transfer 含 location_management_enabled 守卫",
)

body_rt = _func_body("revert_transfer")
record(
    "S2-revert-transfer-location-guard",
    "use_location = location_management_enabled()" in body_rt
    and "if use_location:" in body_rt,
    "revert_transfer 含 location_management_enabled 守卫",
)

# 2. complete_adjustment / revert_adjustment 含 location_management_enabled() 守卫（P0-2 已修复）
body_ca = _func_body("complete_adjustment")
record(
    "S3-complete-adjustment-location-guard",
    "location_management_enabled()" in body_ca,
    "complete_adjustment 含 location_management_enabled 守卫",
)

body_ra = _func_body("revert_adjustment")
record(
    "S4-revert-adjustment-location-guard",
    "location_management_enabled()" in body_ra,
    "revert_adjustment 含 location_management_enabled 守卫",
)

# 3. _create_adjustment_drafts_from_check 传递 warehouse
body_cdf = _func_body("_create_adjustment_drafts_from_check")
record(
    "S5-check-draft-warehouse",
    "warehouse=getattr(check, 'warehouse', None)" in body_cdf,
    "_create_adjustment_drafts_from_check 传递 warehouse 到调整草稿",
)

body_cds = _func_body("_create_adjustment_drafts_from_check_scan")
record(
    "S6-check-scan-draft-warehouse",
    "warehouse=getattr(check, 'warehouse', None)" in body_cds,
    "_create_adjustment_drafts_from_check_scan 传递 warehouse 到调整草稿",
)

# 4. 确认 complete_transfer 的流水记录（add_stock_transaction）不在 use_location 守卫内
#    即未开启库位管理时仍记流水，只是不动 LocationInventory
record(
    "S7-transfer-txn-outside-guard",
    "add_stock_transaction(" in body_ct
    and body_ct.count("if use_location:") >= 1
    and body_ct.find("add_stock_transaction(") > body_ct.rfind("if use_location:"),
    "complete_transfer 流水记录在 use_location 守卫外（未开启也记流水）",
)


# ============== 动态检查 ==============
flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


with flask_app.app_context():
    db.create_all()

    from app import (
        Warehouse,
        User,
        Unit,
        Material,
        TransferOrder,
        TransferOrderItem,
        InventoryCheck,
        InventoryCheckItem,
        LocationInventory,
        StockTransaction,
        SystemSetting,
    )
    from werkzeug.security import generate_password_hash

    # 准备基础数据
    wh = Warehouse.query.filter_by(name="默认测试仓").first()
    if not wh:
        wh = Warehouse(code="DEFAULT-TEST", name="默认测试仓", status="active", is_default=True)
        db.session.add(wh)
    other_wh = Warehouse.query.filter_by(name="其他测试仓").first()
    if not other_wh:
        other_wh = Warehouse(code="OTHER-TEST", name="其他测试仓", status="active", is_default=False)
        db.session.add(other_wh)

    user = User.query.filter_by(id=1).first()
    if not user:
        user = User(
            id=1,
            username="testuser",
            password_hash=generate_password_hash("Password123!"),
            role="warehouse",
            status="normal",
            must_change_password=False,
        )
        db.session.add(user)

    unit = Unit.query.filter_by(code="PCS").first()
    if not unit:
        unit = Unit.query.filter_by(name="个").first()
    if not unit:
        unit = Unit(code="PCS", name="个")
        db.session.add(unit)

    material = Material.query.filter_by(code="TEST-MAT-T7").first()
    if not material:
        material = Material(code="TEST-MAT-T7", name="测试物料T7", spec="", stock=100, price=1, unit_id=unit.id)
        db.session.add(material)
    db.session.commit()

    # 关闭库位管理
    loc_setting = SystemSetting.query.filter_by(key="location_management_enabled").first()
    if not loc_setting:
        loc_setting = SystemSetting(key="location_management_enabled", value="0")
        db.session.add(loc_setting)
    else:
        loc_setting.value = "0"
    db.session.commit()
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()

    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True

    suffix = str(int(time.time()))[-6:]

    # ---------- D1: 未开启库位管理时 complete_transfer 不写 LocationInventory ----------
    # 先确保有一个 LocationInventory 记录存在（值为 0 或某个初始值），complete 后应不变
    loc_before = LocationInventory.query.filter_by(
        material_id=material.id, location=wh.name
    ).first()
    loc_before_qty = loc_before.quantity if loc_before else None

    tf = TransferOrder(
        transfer_no=f"TF{suffix}P13",
        date=date(2026, 8, 2),
        from_warehouse=wh.name,
        to_warehouse=other_wh.name,
        from_location=wh.name,
        to_location=other_wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(tf)
    db.session.flush()
    db.session.add(TransferOrderItem(
        transfer_order_id=tf.id,
        material_id=material.id,
        quantity=5,
        unit_id=unit.id,
        price=1,
        amount=5,
    ))
    db.session.commit()

    txn_before = StockTransaction.query.filter_by(reference_type='transfer', reference_id=tf.id).count()
    rv = client.post(f"/transfer/{tf.id}/complete")
    data1 = rv.get_json(force=True)
    db.session.refresh(tf)

    # complete 后 LocationInventory 不应有新增/变更（库位管理关闭）
    loc_after = LocationInventory.query.filter_by(
        material_id=material.id, location=wh.name
    ).first()
    loc_after_qty = loc_after.quantity if loc_after else None
    txn_after = StockTransaction.query.filter_by(reference_type='transfer', reference_id=tf.id).count()

    record(
        "D1-transfer-no-locinv-when-disabled",
        rv.status_code == 200
        and data1.get("status") == "success"
        and tf.status == "completed"
        and loc_before_qty == loc_after_qty
        and txn_after > txn_before,
        f"complete_transfer(库位关) status={tf.status}, locinv {loc_before_qty}->{loc_after_qty}, txn {txn_before}->{txn_after}",
    )

    # ---------- D2: complete_check 生成的调整草稿带 warehouse ----------
    # 创建一个有差异的盘点单
    check = InventoryCheck(
        check_no=f"CHK{suffix}P13",
        date=date(2026, 8, 2),
        warehouse=wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(check)
    db.session.flush()
    db.session.add(InventoryCheckItem(
        inventory_check_id=check.id,
        material_id=material.id,
        system_stock=100,
        actual_stock=105,  # 盘盈 5
        difference=5,
    ))
    db.session.commit()

    rv = client.post(f"/check/{check.id}/complete")
    data2 = rv.get_json(force=True)
    db.session.refresh(check)

    from app import AdjustmentOrder
    draft = AdjustmentOrder.query.filter_by(source_type='check', source_id=check.id).first()
    record(
        "D2-check-draft-has-warehouse",
        rv.status_code == 200
        and data2.get("status") == "success"
        and draft is not None
        and draft.warehouse == wh.name,
        f"complete_check 生成的调整草稿 warehouse={draft.warehouse if draft else None!r}",
    )

    # 清理
    try:
        if draft:
            for item in list(draft.items):
                db.session.delete(item)
            db.session.delete(draft)
        for item in list(check.items):
            db.session.delete(item)
        db.session.delete(check)
        for item in list(tf.items):
            db.session.delete(item)
        db.session.delete(tf)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ============== 汇总 ==============
print("\n" + "=" * 60)
fails = [r for r in results if r[1] == "FAIL"]
print(f"总计 {len(results)} 项，通过 {len(results) - len(fails)} 项，失败 {len(fails)} 项")
if fails:
    print("\n失败项：")
    for cp, st, dt in fails:
        print(f"  {st}: {cp} - {dt}")
    sys.exit(1)
print("✓ 全部通过")
