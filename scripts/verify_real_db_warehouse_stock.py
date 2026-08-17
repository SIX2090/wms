# -*- coding: utf-8 -*-
"""只读验证：真实库中仓库级库存聚合是否与全局 Material.stock 一致。

对每个仓库调用 get_warehouse_stock_quantities，汇总后与 Material.stock 对比，
确认关库位管理+多仓库下报表口径不再为 0 / 不串仓。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
# 使用真实库：不设置 DATABASE_URL，走 app 默认 instance/inventory.db

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, Warehouse, get_warehouse_stock_quantities,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def main():
    with app_module.app.app_context():
        warehouses = Warehouse.query.order_by(Warehouse.id).all()
        print(f"仓库数: {len(warehouses)}")
        global_by_material = {}
        for m in Material.query.all():
            global_by_material[m.id] = float(m.stock or 0)

        per_wh = {}
        for wh in warehouses:
            per_wh[wh.id] = get_warehouse_stock_quantities(wh)
            total = sum(per_wh[wh.id].values())
            print(f"  {wh.name}({wh.code}): 聚合物料数={len(per_wh[wh.id])}, 总库存={total:.2f}")

        # 汇总各仓库库存，与全局 Material.stock 对比（允许 1e-6 误差）
        summed = {}
        for wh_map in per_wh.values():
            for mid, qty in wh_map.items():
                summed[mid] = summed.get(mid, 0.0) + qty

        mismatch = 0
        for mid, gqty in global_by_material.items():
            sqty = summed.get(mid, 0.0)
            if abs(gqty - sqty) > 1e-6:
                mismatch += 1
                if mismatch <= 10:
                    m = Material.query.get(mid)
                    print(f"  [DIFF] material={m.code if m else mid} global={gqty:.2f} wh_sum={sqty:.2f}")
        print(f"全局 vs 仓库汇总 不一致物料数: {mismatch}")

        # 展示每个仓库库存 Top 5
        for wh in warehouses:
            top = sorted(per_wh[wh.id].items(), key=lambda kv: -kv[1])[:5]
            if top:
                print(f"  {wh.name} Top5:")
                for mid, qty in top:
                    m = Material.query.get(mid)
                    print(f"    {m.code if m else mid} {m.name if m else ''}: {qty:.2f}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
