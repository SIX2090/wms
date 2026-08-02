#!/usr/bin/env python3
"""
BUG-2026-08-02-012 回归测试：TransferOrder / InventoryCheck / AdjustmentOrder 加 warehouse 字段。

覆盖：
  1. 静态检查：三个模型含 warehouse 字段定义
  2. 静态检查：auto_migrate_database 含三个表的迁移逻辑
  3. 动态检查：db.create_all() 后三个表含 warehouse 列
  4. 动态检查：AdjustmentOrder 可设置/读取 warehouse 字段
  5. 动态检查：InventoryCheck 可设置/读取 warehouse 字段
  6. 动态检查：TransferOrder 可设置/读取 from_warehouse / to_warehouse 字段
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


# ============== 静态检查 ==============
app_py = read_text("app/app.py")

# 1. 模型字段定义
record(
    "S1-adjustment-model-warehouse",
    "class AdjustmentOrder(db.Model):" in app_py
    and "warehouse = db.Column(db.String(100))" in app_py.split("class AdjustmentOrder(db.Model):")[1].split("class ")[0],
    "AdjustmentOrder 模型含 warehouse 字段定义",
)
record(
    "S2-check-model-warehouse",
    "class InventoryCheck(db.Model):" in app_py
    and "warehouse = db.Column(db.String(100))" in app_py.split("class InventoryCheck(db.Model):")[1].split("class ")[0],
    "InventoryCheck 模型含 warehouse 字段定义",
)
record(
    "S3-transfer-model-from-warehouse",
    "class TransferOrder(db.Model):" in app_py
    and "from_warehouse = db.Column(db.String(100))" in app_py.split("class TransferOrder(db.Model):")[1].split("class ")[0],
    "TransferOrder 模型含 from_warehouse 字段定义",
)
record(
    "S4-transfer-model-to-warehouse",
    "to_warehouse = db.Column(db.String(100))" in app_py.split("class TransferOrder(db.Model):")[1].split("class ")[0],
    "TransferOrder 模型含 to_warehouse 字段定义",
)

# 2. auto_migrate_database 迁移逻辑
record(
    "S5-migrate-transfer",
    "_table_exists('transfer_order')" in app_py
    and "ALTER TABLE transfer_order ADD COLUMN from_warehouse" in app_py
    and "ALTER TABLE transfer_order ADD COLUMN to_warehouse" in app_py,
    "auto_migrate 含 transfer_order from_warehouse/to_warehouse 迁移",
)
record(
    "S6-migrate-check",
    "_table_exists('inventory_check')" in app_py
    and "ALTER TABLE inventory_check ADD COLUMN warehouse" in app_py,
    "auto_migrate 含 inventory_check warehouse 迁移",
)
record(
    "S7-migrate-adjustment",
    "_table_exists('adjustment_order')" in app_py
    and "ALTER TABLE adjustment_order ADD COLUMN warehouse" in app_py,
    "auto_migrate 含 adjustment_order warehouse 迁移",
)
record(
    "S8-migrate-backfill-default",
    "SELECT name FROM warehouse WHERE is_default = 1" in app_py,
    "迁移脚本回填默认仓库名",
)


# ============== 动态检查 ==============
flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


with flask_app.app_context():
    db.create_all()

    from app import (
        AdjustmentOrder,
        InventoryCheck,
        TransferOrder,
        User,
        Warehouse,
        Unit,
    )
    from werkzeug.security import generate_password_hash
    import sqlite3

    # 3. 验证 DB 表结构含 warehouse 列
    db_path = os.path.join(str(APP_DIR), 'instance', 'inventory.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(adjustment_order)")
    adj_cols = [row[1] for row in cursor.fetchall()]
    record(
        "D1-adj-db-warehouse-col",
        'warehouse' in adj_cols,
        f"adjustment_order 表含 warehouse 列 (cols={adj_cols})",
    )

    cursor.execute("PRAGMA table_info(inventory_check)")
    ic_cols = [row[1] for row in cursor.fetchall()]
    record(
        "D2-ic-db-warehouse-col",
        'warehouse' in ic_cols,
        f"inventory_check 表含 warehouse 列 (cols={ic_cols})",
    )

    cursor.execute("PRAGMA table_info(transfer_order)")
    tf_cols = [row[1] for row in cursor.fetchall()]
    record(
        "D3-tf-db-from-warehouse-col",
        'from_warehouse' in tf_cols,
        f"transfer_order 表含 from_warehouse 列",
    )
    record(
        "D4-tf-db-to-warehouse-col",
        'to_warehouse' in tf_cols,
        f"transfer_order 表含 to_warehouse 列",
    )
    conn.close()

    # 准备测试数据
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

    db.session.commit()
    suffix = str(int(time.time()))[-6:]

    # 4. AdjustmentOrder 可设置/读取 warehouse
    adj = AdjustmentOrder(
        adjustment_no=f"ADJ{suffix}W01",
        date=date(2026, 8, 2),
        adjustment_type="surplus",
        warehouse=wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(adj)
    db.session.commit()
    db.session.refresh(adj)
    record(
        "D5-adj-warehouse-persist",
        adj.warehouse == wh.name,
        f"AdjustmentOrder.warehouse 落库读取 = {adj.warehouse!r}",
    )

    # 5. InventoryCheck 可设置/读取 warehouse
    ic = InventoryCheck(
        check_no=f"CHK{suffix}W01",
        date=date(2026, 8, 2),
        warehouse=wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(ic)
    db.session.commit()
    db.session.refresh(ic)
    record(
        "D6-ic-warehouse-persist",
        ic.warehouse == wh.name,
        f"InventoryCheck.warehouse 落库读取 = {ic.warehouse!r}",
    )

    # 6. TransferOrder 可设置/读取 from_warehouse / to_warehouse
    tf = TransferOrder(
        transfer_no=f"TF{suffix}W01",
        date=date(2026, 8, 2),
        from_warehouse=wh.name,
        to_warehouse=other_wh.name,
        from_location=wh.name,  # 历史兼容：未开库位时存仓库名
        to_location=other_wh.name,
        status="pending",
        operator_id=1,
    )
    db.session.add(tf)
    db.session.commit()
    db.session.refresh(tf)
    record(
        "D7-tf-from-warehouse-persist",
        tf.from_warehouse == wh.name,
        f"TransferOrder.from_warehouse 落库读取 = {tf.from_warehouse!r}",
    )
    record(
        "D8-tf-to-warehouse-persist",
        tf.to_warehouse == other_wh.name,
        f"TransferOrder.to_warehouse 落库读取 = {tf.to_warehouse!r}",
    )

    # ============== 路由层仓库必填校验（BUG-2026-08-02-013）==============
    # 静态检查：路由函数含仓库必填 + 默认仓库带入逻辑
    def _func_body(name: str) -> str:
        m = re.search(rf"^def\s+{re.escape(name)}\s*\([^)]*\):", app_py, re.M)
        if not m:
            return ""
        nxt = re.search(r"^def\s+\w+\s*\(", app_py[m.end():], re.M)
        end = m.end() + nxt.start() if nxt else len(app_py)
        return app_py[m.start():end]

    for fn in ("add_adjustment", "save_check_table", "add_check", "save_transfer_table", "add_transfer"):
        body = _func_body(fn)
        # 调整/盘点单：仓库必填 + 默认仓库带入
        # 调拨单：调出/调入仓库必填（不自动带入默认，因为两端同仓库会被拒）
        if fn in ("save_transfer_table", "add_transfer"):
            ok = ("请选择调出仓库" in body) and ("请选择调入仓库" in body)
            detail = f"{fn} 含调出/调入仓库必填校验"
        else:
            ok = ("get_default_warehouse()" in body) and ("请选择仓库" in body)
            detail = f"{fn} 含默认仓库逻辑+仓库必填校验"
        record(f"S9-{fn}-warehouse-required", ok, detail)

    # 动态检查：通过 test_client 验证路由行为
    from app import SystemSetting, Material, Unit  # noqa: F811

    # 准备物料 + 单位
    unit = Unit.query.filter_by(code="PCS").first()
    if not unit:
        # name 有 UNIQUE 约束，先按 name 查找
        unit = Unit.query.filter_by(name="个").first()
    if not unit:
        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
    material = Material.query.filter_by(code="TEST-MAT-W").first()
    if not material:
        material = Material(code="TEST-MAT-W", name="测试物料W", spec="", stock=100, price=1, unit_id=unit.id)
        db.session.add(material)
    db.session.commit()

    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True

    # 关闭 prefer_default_warehouse，验证无仓库时拒绝
    setting = SystemSetting.query.filter_by(key="prefer_default_warehouse").first()
    if not setting:
        setting = SystemSetting(key="prefer_default_warehouse", value="0")
        db.session.add(setting)
    else:
        setting.value = "0"
    db.session.commit()
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()

    suffix2 = str(int(time.time()))[-6:]

    # D9: add_adjustment 无仓库 + 无默认 → 400
    rv = client.post("/adjustment/add", json={
        "adjustment_no": f"ADJ{suffix2}R01",
        "adjustment_type": "surplus",
        "warehouse": "",
        "items": [{"material_id": material.id, "quantity": 1, "location": ""}],
    })
    record(
        "D9-add-adjustment-no-wh-rejected",
        rv.status_code == 400 and "仓库" in rv.get_json(force=True).get("msg", ""),
        f"add_adjustment 无仓库返回 {rv.status_code}",
    )

    # D10: save_check_table 无仓库 + 无默认 → 400
    rv = client.post("/check/save_table", json={
        "order_no": f"CHK{suffix2}R01",
        "header": {"warehouse": "", "remark": ""},
        "items": [{"material_id": material.id, "quantity": 1, "location": ""}],
    })
    record(
        "D10-save-check-no-wh-rejected",
        rv.status_code == 400 and "仓库" in rv.get_json(force=True).get("msg", ""),
        f"save_check_table 无仓库返回 {rv.status_code}",
    )

    # D11: save_transfer_table 无调出仓库 → 400
    rv = client.post("/transfer/save_table", json={
        "order_no": f"TF{suffix2}R01",
        "header": {"from_warehouse": "", "to_warehouse": other_wh.name},
        "items": [{"code": material.code, "quantity": 1, "price": 1}],
    })
    record(
        "D11-save-transfer-no-from-wh-rejected",
        rv.status_code == 400 and "调出仓库" in rv.get_json(force=True).get("msg", ""),
        f"save_transfer_table 无调出仓库返回 {rv.status_code}",
    )

    # D12: save_transfer_table 调出=调入 → 400
    rv = client.post("/transfer/save_table", json={
        "order_no": f"TF{suffix2}R02",
        "header": {"from_warehouse": wh.name, "to_warehouse": wh.name},
        "items": [{"code": material.code, "quantity": 1, "price": 1}],
    })
    record(
        "D12-save-transfer-same-wh-rejected",
        rv.status_code == 400 and "不能相同" in rv.get_json(force=True).get("msg", ""),
        f"save_transfer_table 调出=调入返回 {rv.status_code}",
    )

    # 开启 prefer_default_warehouse，验证自动带入默认仓库
    setting.value = "1"
    db.session.commit()
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()

    # D13: add_adjustment 无仓库 + 有默认 → 200 且 warehouse 落库
    from app import AdjustmentOrder as _Adj  # noqa: F811
    rv = client.post("/adjustment/add", json={
        "adjustment_no": f"ADJ{suffix2}R02",
        "adjustment_type": "surplus",
        "warehouse": "",
        "items": [{"material_id": material.id, "quantity": 1, "location": ""}],
    })
    data13 = rv.get_json(force=True)
    adj_r = _Adj.query.filter_by(adjustment_no=f"ADJ{suffix2}R02").first()
    record(
        "D13-add-adjustment-default-assigned",
        rv.status_code == 200 and data13.get("status") == "success" and adj_r and adj_r.warehouse == wh.name,
        f"add_adjustment 自动默认仓库={adj_r.warehouse if adj_r else None!r}, status={rv.status_code}",
    )

    # D14: save_check_table 无仓库 + 有默认 → 200 且 warehouse 落库
    from app import InventoryCheck as _IC  # noqa: F811
    rv = client.post("/check/save_table", json={
        "order_no": f"CHK{suffix2}R02",
        "header": {"warehouse": "", "remark": ""},
        "items": [{"material_id": material.id, "quantity": 1, "location": ""}],
    })
    data14 = rv.get_json(force=True)
    ic_r = _IC.query.filter_by(check_no=f"CHK{suffix2}R02").first()
    record(
        "D14-save-check-default-assigned",
        rv.status_code == 200 and data14.get("status") == "success" and ic_r and ic_r.warehouse == wh.name,
        f"save_check_table 自动默认仓库={ic_r.warehouse if ic_r else None!r}, status={rv.status_code}",
    )

    # 清理路由测试产生的单据
    try:
        for obj in (adj_r, ic_r):
            if obj:
                db.session.delete(obj)
        db.session.commit()
    except Exception:
        db.session.rollback()

    # 清理
    try:
        db.session.delete(adj)
        db.session.delete(ic)
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
