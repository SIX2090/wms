# -*- coding: utf-8 -*-
"""按流水净额回填 location_inventory（F2.10 ③，审计报告 §1.3）。

背景
----
「库位管理」（系统设置 location_management_enabled）是**高危开关**：开启后
`get_warehouse_stock_quantities` 由「按流水 location 聚合」切换到「按
location_inventory 聚合」。实测生产库 location_inventory 全表仅 2 行（且均为
脏数据），其余 1243 个物料库位账恒为 0 → 一旦开启，库存查询/报表/手机端全部
显示 0、所有出库被拒、存量单据调整/调拨完成全面失败。故开启前必须先把库位账
按流水净额回填对齐（`find_location_ledger_mismatches` 判据通过才允许开启）。

本脚本做什么
------------
对每个 (material_id, warehouse_id)（warehouse_id 非空）：

    target  = Σ stock_transaction.quantity   （该物料该仓的流水净额）
    current = Σ location_inventory.quantity
    delta   = target - current

    |target - current| <= tolerance  → 已一致，跳过（保证幂等）
    否则调整「仓库桶行」（location == 该仓 名称/编码 的那行）使其合计等于 target；
    没有桶行则新建一行（location = 仓库名，回退编码）。

为什么回填行用「仓库名」作为 location
------------------------------------
`app._stock_location_from_warehouse` 是全库唯一「仓库 → 库位字符串」口径，
取 name（回退 code）；出/入库等业务路径写库位账时用的正是仓库名。故回填行用
仓库名，可让后续业务 `update_location_inventory(...)` 命中同一行、原地增减，
而不是再新建一行。历史上那 2 行脏数据用的是仓库编码（WH001/WH002），本脚本
按 (material_id, warehouse_id) 定位桶行时**名称与编码都认**，不会漏。

不猜归属
--------
warehouse_id IS NULL 的流水/库位行**不参与回填**（与
`scripts/verify_inventory_identity.py` 的 UNATTRIBUTED 桶、`INVENTORY_TRUTH.md`
§3.2 同口径）——归属不明的历史行保留 NULL 由人工确认，绝不自动并入某个默认仓。

幂等 / 安全
-----------
* **默认 dry-run**：只打印将要执行的变更，绝不写库；加 ``--apply`` 才写入。
* 幂等：回填后重跑，所有 (物料, 仓) 均已一致 → 零变更。
* 单事务：所有写入包在一个 ``BEGIN IMMEDIATE`` 事务里，任一失败整体回滚。
* ``--skip-adjust``：只做「补建」（该 (物料,仓) 尚无任何库位行时新建），
  不动已有行。**默认不加**该开关时会一并调平已有但与流水不符的行——其中就
  包括审计 §1.3 登记的那 2 行脏数据（m727/m615），即计划里的第 ② 步
  （**需先备份、停机执行**，见 docs/WMS修复计划_2026-10-11.md）。

用法
----
    # 1) dry-run 核对（对真实库只读，不改任何数据）
    python scripts/backfill_location_inventory.py --db app/instance/inventory.db
    # 2) 备份 + 停机后真正执行
    python scripts/backfill_location_inventory.py --db app/instance/inventory.db --apply
    # 3) 只补建缺失行、不调平已有行
    python scripts/backfill_location_inventory.py --db app/instance/inventory.db --apply --skip-adjust
    # 4) 机器可读（供流水线/验收消费）
    python scripts/backfill_location_inventory.py --db ... --json

不 import app：本脚本只用 sqlite3 直连，不触发生产硬门禁（A14）。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

DEFAULT_TOLERANCE = 0.01


# ---------------------------------------------------------------------------
# 纯函数（不碰 DB，供 tests/test_f2_10_backfill_location_inventory.py 单测）
# ---------------------------------------------------------------------------
def compute_plan(txn_net, loc_rows, warehouse_names,
                 tolerance=DEFAULT_TOLERANCE, skip_adjust=False):
    """计算回填计划（纯函数，无副作用）。

    参数：
      txn_net         : {(material_id, warehouse_id): 净额}  （已按 (物料,仓) 聚合）
      loc_rows        : [(id, material_id, warehouse_id, location, quantity), ...]
                        warehouse_id 为 None 的行会被忽略（不猜归属）
      warehouse_names : {warehouse_id: (name, code)}  —— 用于定位「仓库桶行」与
                        生成新行 location（name 优先，回退 code）
      tolerance       : 浮点容差
      skip_adjust     : True 时只补建（无任何库位行的 key），不动已有行

    返回计划 dict：
      {
        "inserts": [{"material_id","warehouse_id","location","quantity"}],
        "adjusts": [{"id","material_id","warehouse_id","location","from","to"}],
        "skipped_consistent": int,      # 已一致（幂等跳过）
        "skipped_adjust": int,          # --skip-adjust 下跳过的「需调平已有行」
        "manual_review": [{"material_id","warehouse_id","reason",...}],
        "keys_total": int,              # 参与判定的 (物料,仓) 数
      }
    """
    loc_by_key = {}
    for row in loc_rows:
        row_id, mid, wid, location, qty = row[0], row[1], row[2], row[3], row[4]
        if wid is None:
            continue  # 未归属库位行不参与、不猜归属
        loc_by_key.setdefault((mid, wid), []).append((row_id, location, float(qty or 0)))

    plan = {"inserts": [], "adjusts": [], "skipped_consistent": 0,
            "skipped_adjust": 0, "manual_review": [], "keys_total": 0}

    for key in sorted(set(txn_net) | set(loc_by_key), key=lambda k: (str(k[0]), str(k[1]))):
        mid, wid = key
        plan["keys_total"] += 1
        target = round(float(txn_net.get(key, 0.0)), 2)
        rows = loc_by_key.get(key, [])
        current = sum(q for _, _, q in rows)

        if abs(target - current) <= tolerance:
            plan["skipped_consistent"] += 1
            continue

        delta = target - current
        name, code = warehouse_names.get(wid, (None, None))
        bucket_candidates = {c for c in (name, code) if c}
        bucket = next((r for r in rows if r[1] in bucket_candidates), None)

        if bucket is not None:
            if skip_adjust:
                # --skip-adjust：只补建缺失行，不调平已有行
                plan["skipped_adjust"] += 1
                continue
            new_qty = round(bucket[2] + delta, 2)
            if new_qty < -tolerance:
                # 调平会把该行压成负数 → 不自动处理，交人工（安全优先）
                plan["manual_review"].append({
                    "material_id": mid, "warehouse_id": wid,
                    "reason": f"调平后桶行 quantity={new_qty} 为负，需人工核对",
                    "target": target, "current": current})
                continue
            plan["adjusts"].append({
                "id": bucket[0], "material_id": mid, "warehouse_id": wid,
                "location": bucket[1], "from": round(bucket[2], 2), "to": new_qty})
            continue

        # 无桶行
        if delta < -tolerance:
            # 无桶行却需减少 → 只能去改别的库位行，风险高，交人工
            plan["manual_review"].append({
                "material_id": mid, "warehouse_id": wid,
                "reason": "无仓库桶行但需减少库位账，需人工核对",
                "target": target, "current": current})
            continue
        location = name or code
        if not location:
            plan["manual_review"].append({
                "material_id": mid, "warehouse_id": wid,
                "reason": "仓库名称与编码均为空，无法生成库位行",
                "target": target, "current": current})
            continue
        plan["inserts"].append({
            "material_id": mid, "warehouse_id": wid,
            "location": location, "quantity": round(delta, 2)})

    return plan


# ---------------------------------------------------------------------------
# DB 采集（只读）
# ---------------------------------------------------------------------------
def collect_txn_net(conn):
    """{(material_id, warehouse_id): 净额}；warehouse_id IS NULL 的流水不参与。"""
    rows = conn.execute(
        "SELECT material_id, warehouse_id, SUM(quantity) FROM stock_transaction "
        "WHERE warehouse_id IS NOT NULL "
        "GROUP BY material_id, warehouse_id"
    ).fetchall()
    return {(r[0], r[1]): float(r[2] or 0) for r in rows}


def collect_location_rows(conn):
    """[(id, material_id, warehouse_id, location, quantity), ...]（含 NULL 归属行）。"""
    rows = conn.execute(
        "SELECT id, material_id, warehouse_id, location, quantity "
        "FROM location_inventory"
    ).fetchall()
    return [tuple(r) for r in rows]


def collect_warehouse_names(conn):
    """{warehouse_id: (name, code)}。"""
    rows = conn.execute("SELECT id, name, code FROM warehouse").fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def collect_unattributed(conn):
    """未归属（warehouse_id IS NULL）的流水统计，单列让人看见（不猜归属）。"""
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(quantity), 0) FROM stock_transaction "
        "WHERE warehouse_id IS NULL"
    ).fetchone()
    return {"count": int(row[0] or 0), "sum": round(float(row[1] or 0), 2)}


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def apply_plan(conn, plan):
    """在单个 BEGIN IMMEDIATE 事务内执行 plan，返回 (inserted, adjusted)。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for ins in plan["inserts"]:
            conn.execute(
                "INSERT INTO location_inventory "
                "(material_id, warehouse_id, location, quantity, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (ins["material_id"], ins["warehouse_id"], ins["location"],
                 ins["quantity"], now, now),
            )
        for adj in plan["adjusts"]:
            conn.execute(
                "UPDATE location_inventory SET quantity = ?, updated_at = ? WHERE id = ?",
                (adj["to"], now, adj["id"]),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(plan["inserts"]), len(plan["adjusts"])


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------
def backfill(db_path=None, apply=False, tolerance=DEFAULT_TOLERANCE,
             skip_adjust=False, as_json=False):
    if db_path is None:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "app", "instance", "inventory.db")
    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        _emit(as_json, error=f"数据库不存在: {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        plan = compute_plan(
            collect_txn_net(conn),
            collect_location_rows(conn),
            collect_warehouse_names(conn),
            tolerance=tolerance,
            skip_adjust=skip_adjust,
        )
        unattributed = collect_unattributed(conn)

        inserted = adjusted = 0
        if apply:
            inserted, adjusted = apply_plan(conn, plan)

        result = {
            "db": db_path,
            "dry_run": not apply,
            "tolerance": tolerance,
            "skip_adjust": skip_adjust,
            "keys_total": plan["keys_total"],
            "skipped_consistent": plan["skipped_consistent"],
            "skipped_adjust": plan["skipped_adjust"],
            "planned_inserts": len(plan["inserts"]),
            "planned_adjusts": len(plan["adjusts"]),
            "manual_review": plan["manual_review"],
            "unattributed": unattributed,
            "inserted": inserted,
            "adjusted": adjusted,
            "inserts": plan["inserts"],
            "adjusts": plan["adjusts"],
        }
        _emit(as_json, result=result)
        return 0
    finally:
        conn.close()


def _emit(as_json, result=None, error=None):
    if as_json:
        print(json.dumps(error and {"error": error} or result,
                         ensure_ascii=False, indent=2))
        return
    if error:
        print(f"✗ {error}", file=sys.stderr)
        return
    r = result
    mode = "DRY-RUN（未写入）" if r["dry_run"] else "APPLY（已写入）"
    print("=" * 66)
    print(f"  location_inventory 回填（F2.10 ③） —— {mode}")
    print("=" * 66)
    print(f"  数据库                 : {r['db']}")
    print(f"  (物料,仓) 判定总数     : {r['keys_total']}")
    print(f"  已一致（跳过）         : {r['skipped_consistent']}")
    print(f"  需调平已有行（跳过）   : {r['skipped_adjust']}"
          + ("（--skip-adjust 生效）" if r["skip_adjust"] else ""))
    print(f"  待补建 insert          : {r['planned_inserts']}")
    print(f"  待调平 adjust          : {r['planned_adjusts']}")
    if r["unattributed"]["count"]:
        print(f"  ⚠️  未归属流水(不参与)  : {r['unattributed']['count']} 条 / "
              f"净额 {r['unattributed']['sum']}（warehouse_id IS NULL，不猜归属）")
    if r["manual_review"]:
        print("-" * 66)
        print(f"  ⚠️  需人工核对 {len(r['manual_review'])} 条（不自动处理）：")
        for m in r["manual_review"][:10]:
            print(f"      m{m['material_id']}@w{m['warehouse_id']}: {m['reason']}"
                  f"（target={m['target']} current={m['current']}）")
    if r["adjusts"]:
        print("-" * 66)
        print("  调平明细（含审计 §1.3 的 2 行脏数据）：")
        for a in r["adjusts"][:20]:
            print(f"      id={a['id']} m{a['material_id']}@w{a['warehouse_id']} "
                  f"[{a['location']}] {a['from']} → {a['to']}")
    if r["inserts"]:
        print("-" * 66)
        print("  补建样例（最多 10 条）：")
        for i in r["inserts"][:10]:
            print(f"      m{i['material_id']}@w{i['warehouse_id']} "
                  f"[{i['location']}] += {i['quantity']}")
        if len(r["inserts"]) > 10:
            print(f"      ... 另有 {len(r['inserts']) - 10} 条")
    if r["dry_run"]:
        print("-" * 66)
        print("  这是 dry-run，未写入任何数据。确认无误后加 --apply 执行"
              "（建议先备份 + 停机）。")
    else:
        print("-" * 66)
        print(f"  已写入：补建 {r['inserted']} 行，调平 {r['adjusted']} 行。")
    print("=" * 66)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="按流水净额回填 location_inventory（F2.10 ③，默认 dry-run）")
    ap.add_argument("--db", help="SQLite 库文件路径（默认 app/instance/inventory.db）")
    ap.add_argument("--apply", action="store_true",
                    help="真正写入（默认只 dry-run，不写库）")
    ap.add_argument("--skip-adjust", action="store_true",
                    help="只补建缺失行，不调平已有行（不触碰 §1.3 的 2 行脏数据）")
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE,
                    help="浮点容差（默认 0.01）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)
    return backfill(db_path=args.db, apply=args.apply, tolerance=args.tolerance,
                    skip_adjust=args.skip_adjust, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
