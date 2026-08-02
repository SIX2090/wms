#!/usr/bin/env python3
"""
BUG-2026-08-02-010 回归测试：complete_adjustment / revert_adjustment 同步库位库存。

覆盖：
  1. 静态检查：complete_adjustment / revert_adjustment 含 update_location_inventory 调用
  2. 动态检查（开启库位管理）：
     - 创建带 item.location='测试库位A' 的 pending 调整单（quantity > 0）
     - complete 后 LocationInventory 该库位数量已增加，且 Material.stock 也已增加
     - revert 后 LocationInventory 该库位数量已回退，且 Material.stock 也已回退
  3. 动态检查（负向调整 quantity < 0）：complete 扣库位库存，revert 加回
"""
from __future__ import annotations

import os
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


# ============== 静态检查 ==============
app_py = read_text("app/app.py")

# 抽取 complete_adjustment 函数体
import re

def extract_func(text: str, name: str) -> str:
    m = re.search(rf"^def\s+{re.escape(name)}\s*\([^)]*\):", text, re.M)
    if not m:
        return ""
    nm = re.search(r"^def\s+\w+\s*\(", text[m.end():], re.M)
    end = m.end() + nm.start() if nm else len(text)
    return text[m.start():end]


complete_body = extract_func(app_py, "complete_adjustment")
revert_body = extract_func(app_py, "revert_adjustment")

record(
    "S1-complete-has-location-sync",
    "update_location_inventory" in complete_body and "location_management_enabled()" in complete_body,
    "complete_adjustment 含 update_location_inventory + location_management_enabled 判断",
)
record(
    "S2-revert-has-location-sync",
    "update_location_inventory" in revert_body and "location_management_enabled()" in revert_body,
    "revert_adjustment 含 update_location_inventory + location_management_enabled 判断",
)
record(
    "S3-revert-direction-opposite",
    "-quantity" in revert_body,
    "revert_adjustment 用 -quantity 对称回退（与 complete 方向相反）",
)


# ============== 动态检查 ==============
flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


def login_client(client):
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True


def ensure_setting(key: str, value: str):
    from app import SystemSetting

    setting = SystemSetting.query.filter_by(key=key).first()
    if not setting:
        setting = SystemSetting(key=key, value=value)
        db.session.add(setting)
    else:
        setting.value = value
    db.session.commit()
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()
    return setting


def get_loc_qty(material_id: int, location: str):
    from app import LocationInventory

    inv = LocationInventory.query.filter_by(material_id=material_id, location=location).first()
    return float(inv.quantity or 0) if inv else 0.0


with flask_app.app_context():
    db.create_all()

    # 准备测试数据
    from app import (
        AdjustmentOrder,
        AdjustmentOrderItem,
        Material,
        SystemSetting,
        Unit,
        User,
        Warehouse,
    )
    from werkzeug.security import generate_password_hash

    wh = Warehouse.query.filter_by(name="默认测试仓").first()
    if not wh:
        wh = Warehouse(code="DEFAULT-TEST", name="默认测试仓", status="active", is_default=True)
        db.session.add(wh)

    suffix = str(int(time.time()))[-6:]

    unit = Unit.query.filter_by(name="个").first()
    if not unit:
        unit = Unit(code=f"UNIT-{suffix}", name="个")
        db.session.add(unit)

    material = Material(
        code=f"ADJ-MAT-{suffix}",
        name="调整测试物料",
        spec="",
        stock=100.0,
        price=1,
        unit=unit,
    )
    db.session.add(material)

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

    db.session.commit()

    # 开启库位管理
    ensure_setting("location_management_enabled", "1")
    ensure_setting("prefer_default_warehouse", "0")

    client = flask_app.test_client()
    login_client(client)

    # ---------- D1: 正向调整（quantity > 0）complete 同步库位库存 ----------
    order_no_pos = f"ADJ{suffix}01"
    adj_pos = AdjustmentOrder(
        adjustment_no=order_no_pos,
        date=date(2026, 8, 2),
        adjustment_type="surplus",
        status="pending",
        operator_id=1,
    )
    db.session.add(adj_pos)
    db.session.flush()
    item_pos = AdjustmentOrderItem(
        adjustment_order_id=adj_pos.id,
        material_id=material.id,
        location="测试库位A",
        quantity=10,
        unit_id=unit.id,
        reason="正向调整测试",
    )
    db.session.add(item_pos)
    db.session.commit()

    stock_before = float(material.stock)
    loc_before = get_loc_qty(material.id, "测试库位A")

    rv = client.post(f"/adjustment/{adj_pos.id}/complete")
    db.session.refresh(adj_pos)
    db.session.refresh(material)
    data = rv.get_json(force=True)
    loc_after = get_loc_qty(material.id, "测试库位A")
    stock_after = float(material.stock)

    record(
        "D1-complete-pos-status",
        rv.status_code == 200 and data.get("status") == "success" and adj_pos.status == "completed",
        f"正向调整 complete 状态={adj_pos.status}, http={rv.status_code}, resp={data.get('status')}",
    )
    record(
        "D1-complete-pos-stock-up",
        abs((stock_after - stock_before) - 10.0) < 0.01,
        f"正向调整后总库存 {stock_before} -> {stock_after}（预期 +10）",
    )
    record(
        "D1-complete-pos-loc-up",
        abs((loc_after - loc_before) - 10.0) < 0.01,
        f"正向调整后库位库存 {loc_before} -> {loc_after}（预期 +10）",
    )

    # ---------- D2: 正向调整 revert 对称回退库位库存 ----------
    rv = client.post(f"/adjustment/{adj_pos.id}/revert")
    db.session.refresh(adj_pos)
    db.session.refresh(material)
    loc_after_revert = get_loc_qty(material.id, "测试库位A")
    stock_after_revert = float(material.stock)

    record(
        "D2-revert-pos-status",
        rv.status_code == 200 and adj_pos.status == "pending",
        f"正向调整 revert 状态={adj_pos.status}, http={rv.status_code}",
    )
    record(
        "D2-revert-pos-stock-back",
        abs(stock_after_revert - stock_before) < 0.01,
        f"正向调整 revert 后总库存 {stock_after_revert}（预期回到 {stock_before}）",
    )
    record(
        "D2-revert-pos-loc-back",
        abs(loc_after_revert - loc_before) < 0.01,
        f"正向调整 revert 后库位库存 {loc_after_revert}（预期回到 {loc_before}）",
    )

    # ---------- D3: 负向调整（quantity < 0）complete 扣库位库存 ----------
    # 先确保库位有库存（D2 已回退到 0，先做一次正向 complete 建账）
    client.post(f"/adjustment/{adj_pos.id}/complete")
    db.session.commit()
    stock_pre_neg = float(material.stock)
    loc_pre_neg = get_loc_qty(material.id, "测试库位A")

    order_no_neg = f"ADJ{suffix}02"
    adj_neg = AdjustmentOrder(
        adjustment_no=order_no_neg,
        date=date(2026, 8, 2),
        adjustment_type="loss",
        status="pending",
        operator_id=1,
    )
    db.session.add(adj_neg)
    db.session.flush()
    item_neg = AdjustmentOrderItem(
        adjustment_order_id=adj_neg.id,
        material_id=material.id,
        location="测试库位A",
        quantity=-5,
        unit_id=unit.id,
        reason="负向调整测试",
    )
    db.session.add(item_neg)
    db.session.commit()

    rv = client.post(f"/adjustment/{adj_neg.id}/complete")
    db.session.refresh(adj_neg)
    db.session.refresh(material)
    loc_after_neg = get_loc_qty(material.id, "测试库位A")
    stock_after_neg = float(material.stock)

    record(
        "D3-complete-neg-status",
        rv.status_code == 200 and adj_neg.status == "completed",
        f"负向调整 complete 状态={adj_neg.status}, http={rv.status_code}",
    )
    record(
        "D3-complete-neg-stock-down",
        abs((stock_pre_neg - stock_after_neg) - 5.0) < 0.01,
        f"负向调整后总库存 {stock_pre_neg} -> {stock_after_neg}（预期 -5）",
    )
    record(
        "D3-complete-neg-loc-down",
        abs((loc_pre_neg - loc_after_neg) - 5.0) < 0.01,
        f"负向调整后库位库存 {loc_pre_neg} -> {loc_after_neg}（预期 -5）",
    )

    # ---------- D4: 负向调整 revert 加回库位库存 ----------
    rv = client.post(f"/adjustment/{adj_neg.id}/revert")
    db.session.refresh(adj_neg)
    db.session.refresh(material)
    loc_after_neg_revert = get_loc_qty(material.id, "测试库位A")
    stock_after_neg_revert = float(material.stock)

    record(
        "D4-revert-neg-status",
        rv.status_code == 200 and adj_neg.status == "pending",
        f"负向调整 revert 状态={adj_neg.status}, http={rv.status_code}",
    )
    record(
        "D4-revert-neg-stock-back",
        abs(stock_after_neg_revert - stock_pre_neg) < 0.01,
        f"负向调整 revert 后总库存 {stock_after_neg_revert}（预期回到 {stock_pre_neg}）",
    )
    record(
        "D4-revert-neg-loc-back",
        abs(loc_after_neg_revert - loc_pre_neg) < 0.01,
        f"负向调整 revert 后库位库存 {loc_after_neg_revert}（预期回到 {loc_pre_neg}）",
    )

    # 清理测试数据
    try:
        for o in [adj_pos, adj_neg]:
            existing = AdjustmentOrder.query.get(o.id)
            if existing and existing.status == "completed":
                client.post(f"/adjustment/{o.id}/revert")
        db.session.commit()
        AdjustmentOrderItem.query.filter(
            AdjustmentOrderItem.adjustment_order_id.in_([adj_pos.id, adj_neg.id])
        ).delete(synchronize_session=False)
        AdjustmentOrder.query.filter(
            AdjustmentOrder.id.in_([adj_pos.id, adj_neg.id])
        ).delete(synchronize_session=False)
        from app import LocationInventory

        LocationInventory.query.filter_by(material_id=material.id, location="测试库位A").delete()
        db.session.delete(material)
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
