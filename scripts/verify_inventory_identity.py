#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""库存三账恒等式校验器（P2-3 前置：判据先行）。

为什么先做它
------------
P2-3 要做"三账写入单点收敛"（`add_stock` / `deduct_stock_atomic` 不自动同步
库位账，靠 35 个消费点手工双写，是 BUG-2026-08-16-002 / 08-04-002 的温床）。
**在动手术之前必须先有判据**：恒等式不成立时能立刻发现，而不是等用户在报表里
看到账实不符。本脚本提供这个判据，并在后续每个迁移 atomic action 后复跑。

恒等式（INVENTORY_TRUTH.md §1）
------------------------------
    ① material.stock（总账，全局合计）
      = Σ② location_inventory.quantity（按物料汇总）
      = Σ③ stock_transaction.quantity（按物料汇总，带符号）

用法
----
    python scripts/verify_inventory_identity.py --db "sqlite:///c:/wms/app/instance/inventory.db"
    python scripts/verify_inventory_identity.py --db ... --json
    python scripts/verify_inventory_identity.py --db ... --top 20

设计要点
--------
* **纯函数与 app 导入分离**：`build_identity_rows` / `find_mismatches` 不依赖
  Flask，可直接单测（A9）；只 `main()` 延迟导入 app。
* **两个维度分开报**：
  - `ledger_vs_location`（① vs ②）：关库位管理时 location_inventory 为空，
    属预期，单独以 `no_location_rows` 标注而非判为不一致；
  - `ledger_vs_txn`（① vs ③）：历史数据（期初导入早于流水制度）可能天然有差，
    列为「待人工确认」而非直接判错。
* A14 合规：脚本引用 app，显式 opt-in 生产硬门禁。
"""
from __future__ import annotations

# A14（R6 机械化）：scripts/ 下引用 app 必须显式放行生产硬门禁，且必须在
# 任何 app 导入之前设置（app 导入全部延迟到 main() 内）。
import os

os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
os.environ.setdefault("WMS_DEBUG", "0")

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

# 浮点容差：金额/数量经 round_to_2_decimals 后允许 0.01 级误差
DEFAULT_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# 纯函数（不依赖 Flask/app，供 tests/test_inventory_identity_checker.py 单测）
# ---------------------------------------------------------------------------
def build_identity_rows(materials, locations, transactions):
    """把三份数据按 material_id 汇总成恒等式对照行。

    参数均为可迭代的轻量结构：
      materials    : [(material_id, code, stock), ...]
      locations    : [(material_id, quantity), ...]        # 可空 quantity 计 0
      transactions : [(material_id, quantity), ...]        # 带符号
    返回 {material_id: {"code","ledger","locations","txns","location_rows"}}。
    """
    rows = {}
    for mid, code, stock in materials:
        rows[mid] = {
            "code": code,
            "ledger": float(stock or 0),
            "locations": 0.0,
            "txns": 0.0,
            "location_rows": 0,
        }
    for mid, qty in locations:
        row = rows.setdefault(mid, {"code": "", "ledger": 0.0, "locations": 0.0,
                                    "txns": 0.0, "location_rows": 0})
        row["locations"] += float(qty or 0)
        row["location_rows"] += 1
    for mid, qty in transactions:
        row = rows.setdefault(mid, {"code": "", "ledger": 0.0, "locations": 0.0,
                                    "txns": 0.0, "location_rows": 0})
        row["txns"] += float(qty or 0)
    return rows


def find_mismatches(rows, tolerance=DEFAULT_TOLERANCE):
    """逐物料比对三个口径，返回不一致清单。

    每个条目：{"material_id","code","dimension","ledger","other","delta"}
    dimension ∈ {"ledger_vs_location","ledger_vs_txn"}。
    location_rows == 0 时不判 ledger_vs_location（关库位管理时无库位账属预期）。
    """
    findings = []
    for mid, row in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if row["location_rows"] > 0 and abs(row["ledger"] - row["locations"]) > tolerance:
            findings.append({
                "material_id": mid,
                "code": row["code"],
                "dimension": "ledger_vs_location",
                "ledger": round(row["ledger"], 2),
                "other": round(row["locations"], 2),
                "delta": round(row["ledger"] - row["locations"], 2),
            })
        if abs(row["ledger"] - row["txns"]) > tolerance:
            findings.append({
                "material_id": mid,
                "code": row["code"],
                "dimension": "ledger_vs_txn",
                "ledger": round(row["ledger"], 2),
                "other": round(row["txns"], 2),
                "delta": round(row["ledger"] - row["txns"], 2),
            })
    return findings


def summarize(rows, findings):
    """汇总：物料总数、有库位账的物料数、两维度不一致条数。"""
    return {
        "materials": len(rows),
        "materials_with_location_rows": sum(1 for r in rows.values() if r["location_rows"] > 0),
        "mismatch_ledger_vs_location": sum(
            1 for f in findings if f["dimension"] == "ledger_vs_location"),
        "mismatch_ledger_vs_txn": sum(
            1 for f in findings if f["dimension"] == "ledger_vs_txn"),
        "findings": findings,
    }


# ---------------------------------------------------------------------------
# CLI（延迟导入 app，扫真实库）
# ---------------------------------------------------------------------------
def collect_from_app():
    """从当前 app 的库里取三份数据（只读，零写操作）。"""
    from app import app as flask_app, db  # noqa: PLC0415
    from app import LocationInventory, Material, StockTransaction  # noqa: PLC0415

    with flask_app.app_context():
        materials = [(m.id, m.code, m.stock) for m in Material.query.all()]
        locations = [(li.material_id, li.quantity) for li in LocationInventory.query.all()]
        transactions = [(t.material_id, t.quantity) for t in StockTransaction.query.all()]
    return materials, locations, transactions


def main():
    ap = argparse.ArgumentParser(description="库存三账恒等式校验器（P2-3 前置判据）")
    ap.add_argument("--db", help="SQLAlchemy URL，如 sqlite:///c:/wms/app/instance/inventory.db")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE, help="浮点容差")
    ap.add_argument("--top", type=int, default=10, help="最多列出多少条明细")
    ap.add_argument("--json", action="store_true", help="输出 JSON（供流水线消费）")
    args = ap.parse_args()

    if args.db:
        os.environ["DATABASE_URL"] = args.db
    materials, locations, transactions = collect_from_app()
    rows = build_identity_rows(materials, locations, transactions)
    findings = find_mismatches(rows, args.tolerance)
    summary = summarize(rows, findings)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        # 判据用途：仅当"开了库位管理却有 ①≠②"时视为硬失败；
        # ① vs ③ 差异多为历史遗留（期初早于流水制度），列为待确认不阻断。
        return 1 if summary["mismatch_ledger_vs_location"] else 0

    print("=" * 66)
    print("  库存三账恒等式校验（INVENTORY_TRUTH.md §1：① = Σ② = Σ③）")
    print("=" * 66)
    print(f"  物料总数           : {summary['materials']}")
    print(f"  有库位账的物料     : {summary['materials_with_location_rows']}")
    print(f"  ①≠②（总账 vs 库位）: {summary['mismatch_ledger_vs_location']}")
    print(f"  ①≠③（总账 vs 流水）: {summary['mismatch_ledger_vs_txn']}（历史遗留多为待确认）")
    if findings:
        print("-" * 66)
        for f in findings[: args.top]:
            print(f"  [{f['dimension']}] {f['code'] or f['material_id']}: "
                  f"总账={f['ledger']} 对照={f['other']} 差={f['delta']}")
        if len(findings) > args.top:
            print(f"  ... 另有 {len(findings) - args.top} 条（--top 调大查看）")
    else:
        print("  ✅ 三账恒等式全部成立")
    print("=" * 66)
    return 1 if summary["mismatch_ledger_vs_location"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
