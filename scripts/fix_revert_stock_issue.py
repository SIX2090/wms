#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键诊断并修复：反提交提示"库存不足"但实际有库存的问题。

用法：
  cd /你的仓库路径
  python3 scripts/fix_revert_stock_issue.py

功能：
  1. 自动检测数据库类型（SQLite / MySQL / PostgreSQL）
  2. 查找所有"已完成但无法反提交"的入库单
  3. 检查库存流水 location 归属
  4. 对历史未归属流水（location 为空）的物料，修复流水 location 为单据仓库
  5. 输出诊断报告

安全：默认只读诊断，加 --fix 才执行修复。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, InOrderItem, Material, StockTransaction, Warehouse, db,
    get_warehouse_stock_quantities, location_management_enabled,
)
from sqlalchemy import text


def get_db_url():
    return os.environ.get("DATABASE_URL") or os.environ.get("WMS_DATABASE_URI") or "sqlite:///wms.db"


def detect_db_type():
    url = get_db_url()
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("mysql"):
        return "mysql"
    if url.startswith("postgresql"):
        return "postgres"
    return "unknown"


def diagnose():
    fix_mode = "--fix" in sys.argv

    print("=" * 70)
    print("反提交库存不足问题 - 一键诊断")
    print("=" * 70)
    print(f"数据库: {get_db_url()}")
    print(f"数据库类型: {detect_db_type()}")
    print(f"库位管理: {'开启' if location_management_enabled() else '关闭'}")
    print()

    # 1. 找所有已完成的入库单
    completed_orders = InOrder.query.filter(InOrder.status == 'completed').all()
    print(f"已完成入库单: {len(completed_orders)} 张")

    problem_orders = []
    for order in completed_orders:
        wh_key = (order.warehouse or '').strip()
        if not wh_key:
            continue
        wh_obj = Warehouse.query.filter(
            db.or_(Warehouse.name == wh_key, Warehouse.code == wh_key)
        ).order_by(Warehouse.id.asc()).first()
        if not wh_obj:
            problem_orders.append((order, '仓库解析失败'))
            continue

        warehouse_stock = get_warehouse_stock_quantities(wh_obj)
        for item in order.items:
            wh_stock = warehouse_stock.get(item.material_id, 0)
            mat = item.material
            if not mat:
                continue
            global_stock = mat.stock or 0
            required = item.quantity or 0
            if wh_stock < required and global_stock >= required:
                problem_orders.append((order, f'物料 {mat.code} 仓库级{wh_stock:.2f} < 需要{required:.2f}，但全局{global_stock:.2f}'))

    print(f"\n问题单据: {len(problem_orders)} 张")
    print("-" * 70)

    if not problem_orders:
        print("✓ 未发现问题单据。如果仍有问题，请确认服务已重启。")
        return

    for order, reason in problem_orders:
        print(f"  {order.order_no} ({order.warehouse}): {reason}")

    # 2. 检查问题物料的流水 location 归属
    print("\n" + "=" * 70)
    print("库存流水 location 归属分析")
    print("=" * 70)

    problem_mat_ids = set()
    for order, _ in problem_orders:
        for item in order.items:
            if item.material:
                problem_mat_ids.add(item.material_id)

    for mat_id in sorted(problem_mat_ids):
        mat = Material.query.get(mat_id)
        if not mat:
            continue
        rows = StockTransaction.query.filter(
            StockTransaction.material_id == mat_id
        ).order_by(StockTransaction.id.desc()).limit(10).all()

        null_count = StockTransaction.query.filter(
            StockTransaction.material_id == mat_id,
            db.or_(StockTransaction.location.is_(None), StockTransaction.location == ''),
        ).count()
        total_count = StockTransaction.query.filter(
            StockTransaction.material_id == mat_id
        ).count()

        print(f"\n物料 {mat.code} ({mat.name}): 全局库存={mat.stock:.2f}, 流水总数={total_count}, 未归属流水={null_count}")
        if null_count > 0:
            print(f"  → 发现 {null_count} 条未归属流水（location 为空）")
            if fix_mode:
                print(f"  → [修复模式] 将未归属流水的 location 设为单据仓库")
                # 找到这些流水对应的入库单仓库
                for order, _ in problem_orders:
                    for item in order.items:
                        if item.material_id == mat_id:
                            wh_key = (order.warehouse or '').strip()
                            if wh_key:
                                StockTransaction.query.filter(
                                    StockTransaction.material_id == mat_id,
                                    db.or_(StockTransaction.location.is_(None), StockTransaction.location == ''),
                                    StockTransaction.reference_type == 'in_order',
                                    StockTransaction.reference_id == order.id,
                                ).update({'location': wh_key}, synchronize_session=False)
                                print(f"    修复入库单 {order.order_no} 的 {null_count} 条流水 location → {wh_key}")
            else:
                print(f"  → 运行 python3 scripts/fix_revert_stock_issue.py --fix 自动修复")

        for row in rows[:5]:
            loc = row.location if row.location else '(空)'
            print(f"    流水#{row.id}: {row.transaction_type} {row.quantity:.2f} location={loc}")

    if fix_mode:
        db.session.commit()
        print("\n✓ 修复完成。请重新测试反提交。")
    else:
        print("\n诊断完成。加 --fix 参数执行修复。")


if __name__ == '__main__':
    with app_module.app.app_context():
        diagnose()
