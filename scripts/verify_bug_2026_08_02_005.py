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
