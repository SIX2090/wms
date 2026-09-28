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
* **P0-1 仓级分解（2026-09-27）**：物料级 ①=Σ② 只能证明**总数**对，不能证明
  **分布**对（A 仓多 100 / B 仓少 100 时合计仍相等，物料级核对全绿）。
  新增 `build_warehouse_rows` / `find_warehouse_mismatches` 把 ② 按
  `warehouse_id` 拆开逐仓对账，抓 AGENTS.md R2 要求的"多仓库隔离"。
  `warehouse_id IS NULL` 的历史行单列 `unattributed` 待确认，**不猜归属**
  （INVENTORY_TRUTH.md §3.2）。
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

    兼容 P0-1：locations / transactions 元素允许带第 3 项 warehouse_id
    （见 build_warehouse_rows）。**本函数的返回值与旧版逐字一致**，
    仓库维度由 build_warehouse_rows 单独承载，避免改动既有对外口径。
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
    for item in locations:
        mid, qty = item[0], item[1]
        row = rows.setdefault(mid, {"code": "", "ledger": 0.0, "locations": 0.0,
                                    "txns": 0.0, "location_rows": 0})
        row["locations"] += float(qty or 0)
        row["location_rows"] += 1
    for item in transactions:
        mid, qty = item[0], item[1]
        row = rows.setdefault(mid, {"code": "", "ledger": 0.0, "locations": 0.0,
                                    "txns": 0.0, "location_rows": 0})
        row["txns"] += float(qty or 0)
    return rows


# ---------------------------------------------------------------------------
# P0-1：仓库维度分解（抓"仓级串仓"）
#
# 为什么必须有这一层
# ------------------
# 物料级恒等式 ① = Σ② 只能证明**总数**对，不能证明**分布**对。
#   A 仓库位账多 100、B 仓库位账少 100 → Σ② 仍等于 ①，物料级核对**全绿**，
#   但两个仓库各自都是错的。这正是 AGENTS.md R2 要求必验的"多仓库隔离"，
#   也是 BUG-2026-09-02-001 / 09-03-001/002/004 的同一根因方向。
# 本层把 ② 按 warehouse_id 拆开，逐仓与"该仓流水净额"对账。
# ---------------------------------------------------------------------------
UNATTRIBUTED = "__unattributed__"  # warehouse_id IS NULL 的历史行（R2：不猜归属）


def build_warehouse_rows(locations, transactions):
    """按 (material_id, warehouse_id) 汇总库位账与流水账。

    参数：
      locations    : [(material_id, quantity, warehouse_id), ...]  # 第 3 项可空
      transactions : [(material_id, quantity, warehouse_id), ...]  # 第 3 项可空

    返回 {material_id: {"by_wh": {wh_key: {"locations","txns"}},
                        "locations_total","txns_total",
                        "unattributed_locations","unattributed_txns"}}

    `warehouse_id is None` 归入 UNATTRIBUTED 桶**单独计数，不并入任何真实仓库**
    —— INVENTORY_TRUTH.md §3.2「无法唯一确定归属的历史行保留 NULL，不得自动
    归入任意默认仓库」。这样的"看得见的空洞"才能被发现，而不是被猜没了。
    """
    rows = {}

    def _bucket(mid):
        return rows.setdefault(mid, {
            "by_wh": {},
            "locations_total": 0.0,
            "txns_total": 0.0,
            "unattributed_locations": 0.0,
            "unattributed_txns": 0.0,
        })

    def _wh(wid):
        return UNATTRIBUTED if wid is None else wid

    for item in locations:
        mid, qty, wid = item[0], item[1], (item[2] if len(item) > 2 else None)
        row = _bucket(mid)
        q = float(qty or 0)
        slot = row["by_wh"].setdefault(_wh(wid), {"locations": 0.0, "txns": 0.0})
        slot["locations"] += q
        row["locations_total"] += q
        if wid is None:
            row["unattributed_locations"] += q

    for item in transactions:
        mid, qty, wid = item[0], item[1], (item[2] if len(item) > 2 else None)
        row = _bucket(mid)
        q = float(qty or 0)
        slot = row["by_wh"].setdefault(_wh(wid), {"locations": 0.0, "txns": 0.0})
        slot["txns"] += q
        row["txns_total"] += q
        if wid is None:
            row["unattributed_txns"] += q

    return rows


def find_warehouse_mismatches(rows, wh_rows, tolerance=DEFAULT_TOLERANCE):
    """逐 (物料, 仓库) 比对库位账 vs 流水账，返回仓级不一致清单。

    判据：某物料在某仓库的库位账净额，应当等于**该仓库**的流水净额。
    只对真实仓库判（UNATTRIBUTED 桶不判——历史行归属本就不确定，
    按 R2 精神列为待确认而非判错，与 ledger_vs_txn 的处理一致）。

    每个条目：{"material_id","code","warehouse_id","dimension",
              "locations","txns","delta"}，dimension="wh_location_vs_txn"。
    """
    findings = []
    for mid, wr in sorted(wh_rows.items(), key=lambda kv: str(kv[0])):
        code = rows.get(mid, {}).get("code", "")
        for wid, slot in sorted(wr["by_wh"].items(),
                                key=lambda kv: str(kv[0])):
            if wid == UNATTRIBUTED:
                continue
            if abs(slot["locations"] - slot["txns"]) > tolerance:
                findings.append({
                    "material_id": mid,
                    "code": code,
                    "warehouse_id": wid,
                    "dimension": "wh_location_vs_txn",
                    "locations": round(slot["locations"], 2),
                    "txns": round(slot["txns"], 2),
                    "delta": round(slot["locations"] - slot["txns"], 2),
                })
    return findings


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


def summarize(rows, findings, wh_findings=None, wh_rows=None):
    """汇总：物料总数、有库位账的物料数、各维度不一致条数。

    P0-1：新增仓级维度 `mismatch_wh_location_vs_txn` 与未归属统计。
    `wh_findings` / `wh_rows` 缺省时保持旧行为（向后兼容既有调用与测试）。
    """
    summary = {
        "materials": len(rows),
        "materials_with_location_rows": sum(1 for r in rows.values() if r["location_rows"] > 0),
        "mismatch_ledger_vs_location": sum(
            1 for f in findings if f["dimension"] == "ledger_vs_location"),
        "mismatch_ledger_vs_txn": sum(
            1 for f in findings if f["dimension"] == "ledger_vs_txn"),
        "findings": findings,
    }
    if wh_findings is not None or wh_rows is not None:
        wh_findings = wh_findings or []
        wh_rows = wh_rows or {}
        # 未归属桶：既非错误也非"无数据"，单列让人看见（INVENTORY_TRUTH.md §3.2）
        unattributed = [
            {"material_id": mid,
             "code": rows.get(mid, {}).get("code", ""),
             "locations": round(wr["unattributed_locations"], 2),
             "txns": round(wr["unattributed_txns"], 2)}
            for mid, wr in sorted(wh_rows.items(), key=lambda kv: str(kv[0]))
            if wr["unattributed_locations"] or wr["unattributed_txns"]
        ]
        summary["mismatch_wh_location_vs_txn"] = sum(
            1 for f in wh_findings if f["dimension"] == "wh_location_vs_txn")
        summary["warehouse_findings"] = wh_findings
        summary["unattributed_materials"] = len(unattributed)
        summary["unattributed"] = unattributed
    return summary


# ---------------------------------------------------------------------------
# CLI（延迟导入 app，扫真实库）
# ---------------------------------------------------------------------------
def collect_from_app():
    """从当前 app 的库里取三份数据（只读，零写操作）。

    P0-1：库位账与流水账额外带出 `warehouse_id`（第 3 项），供仓级分解使用。
    """
    from app import app as flask_app, db  # noqa: PLC0415
    from app import LocationInventory, Material, StockTransaction  # noqa: PLC0415

    with flask_app.app_context():
        materials = [(m.id, m.code, m.stock) for m in Material.query.all()]
        locations = [(li.material_id, li.quantity, li.warehouse_id)
                     for li in LocationInventory.query.all()]
        transactions = [(t.material_id, t.quantity, t.warehouse_id)
                        for t in StockTransaction.query.all()]
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
    # P0-1：仓级分解（抓"仓级串仓"——物料级合计对、但各仓各自错）
    wh_rows = build_warehouse_rows(locations, transactions)
    wh_findings = find_warehouse_mismatches(rows, wh_rows, args.tolerance)
    summary = summarize(rows, findings, wh_findings, wh_rows)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        # 判据用途：①≠② 或 仓级 ②≠③ 均视为硬失败；
        # ① vs ③ 差异多为历史遗留（期初早于流水制度），列为待确认不阻断。
        return 1 if (summary["mismatch_ledger_vs_location"]
                     or summary.get("mismatch_wh_location_vs_txn")) else 0

    print("=" * 66)
    print("  库存三账恒等式校验（INVENTORY_TRUTH.md §1：① = Σ② = Σ③）")
    print("=" * 66)
    print(f"  物料总数           : {summary['materials']}")
    print(f"  有库位账的物料     : {summary['materials_with_location_rows']}")
    print(f"  ①≠②（总账 vs 库位）: {summary['mismatch_ledger_vs_location']}")
    print(f"  ①≠③（总账 vs 流水）: {summary['mismatch_ledger_vs_txn']}（历史遗留多为待确认）")
    print(f"  ②≠③ 仓级（库位 vs 流水）: {summary['mismatch_wh_location_vs_txn']}"
          f"（P0-1：抓仓级串仓）")
    if summary["unattributed_materials"]:
        print(f"  ⚠️  有未归属历史行（warehouse_id IS NULL）的物料: "
              f"{summary['unattributed_materials']}（不猜归属，单列待确认）")
    if findings:
        print("-" * 66)
        for f in findings[: args.top]:
            print(f"  [{f['dimension']}] {f['code'] or f['material_id']}: "
                  f"总账={f['ledger']} 对照={f['other']} 差={f['delta']}")
        if len(findings) > args.top:
            print(f"  ... 另有 {len(findings) - args.top} 条（--top 调大查看）")
    if wh_findings:
        print("-" * 66)
        for f in wh_findings[: args.top]:
            print(f"  [仓级] {f['code'] or f['material_id']} @仓库{f['warehouse_id']}: "
                  f"库位账={f['locations']} 流水={f['txns']} 差={f['delta']}")
        if len(wh_findings) > args.top:
            print(f"  ... 另有 {len(wh_findings) - args.top} 条仓级差异（--top 调大查看）")
    if not findings and not wh_findings:
        print("  ✅ 三账恒等式全部成立（含仓级分解）")
    print("=" * 66)
    return 1 if (summary["mismatch_ledger_vs_location"]
                 or summary["mismatch_wh_location_vs_txn"]) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
