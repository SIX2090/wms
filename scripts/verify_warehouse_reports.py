# -*- coding: utf-8 -*-
"""BUG-2026-08-17-00X 验证：关库位管理+多仓库时，仓库级库存聚合正确。

直接复用 app 的 add_stock / deduct_stock_atomic / get_warehouse_stock_quantities，
用内存库跑一遍 A 仓入库、B 仓入库、A 仓出库，验证：
  T1. A 仓聚合 = 10，B 仓聚合 = 5（不串仓）
  T2. A 仓出库 3 后，A 仓 = 7，B 仓仍 = 5
  T3. 流水 location 已写入仓库名（可直接按 location 聚合）
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Material, MaterialCategory, StockTransaction, Unit, Warehouse,
    add_stock, deduct_stock_atomic, get_warehouse_stock_quantities,
    set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(name)


def main():
    with app_module.app.test_request_context():
        db.drop_all()
        db.create_all()
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

        # T1: A 仓入库 10、B 仓入库 5
        ok, err = add_stock(mat, 10, 'in', 'in_order', 9, warehouse=wh_a)
        check("T1a add_stock A 仓入库", ok, err or "")
        ok, err = add_stock(mat, 5, 'in', 'in_order', 10, warehouse=wh_b)
        check("T1b add_stock B 仓入库", ok, err or "")
        db.session.commit()

        stock_a = get_warehouse_stock_quantities(wh_a)
        stock_b = get_warehouse_stock_quantities(wh_b)
        check("T1c A 仓聚合=10", abs(stock_a.get(mat.id, 0) - 10) < 1e-9,
              f"实际 {stock_a.get(mat.id, 0)}")
        check("T1d B 仓聚合=5", abs(stock_b.get(mat.id, 0) - 5) < 1e-9,
              f"实际 {stock_b.get(mat.id, 0)}")

        # T2: A 仓出库 3
        ok, err, _ = deduct_stock_atomic(mat.id, 3, 'out', 'out_order', 11,
                                         warehouse=wh_a)
        check("T2a deduct_stock_atomic A 仓出库", ok, err or "")
        db.session.commit()
        stock_a = get_warehouse_stock_quantities(wh_a)
        stock_b = get_warehouse_stock_quantities(wh_b)
        check("T2b A 仓聚合=7", abs(stock_a.get(mat.id, 0) - 7) < 1e-9,
              f"实际 {stock_a.get(mat.id, 0)}")
        check("T2c B 仓仍=5", abs(stock_b.get(mat.id, 0) - 5) < 1e-9,
              f"实际 {stock_b.get(mat.id, 0)}")

        # T3: 流水 location 已写入仓库名
        txns = StockTransaction.query.order_by(StockTransaction.id).all()
        locs = [t.location for t in txns]
        check("T3a 入库流水 location=仓库A", locs[0] == "仓库A", f"实际 {locs[0]!r}")
        check("T3b 入库流水 location=仓库B", locs[1] == "仓库B", f"实际 {locs[1]!r}")
        check("T3c 出库流水 location=仓库A", locs[2] == "仓库A", f"实际 {locs[2]!r}")

    print()
    if failures:
        print(f"FAILED: {len(failures)} 项未通过 -> {failures}")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
