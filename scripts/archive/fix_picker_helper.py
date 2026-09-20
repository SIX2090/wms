# -*- coding: utf-8 -*-
"""WMS 数据库修复：为 out_order 和 production_requisition 添加 picker 列。"""
import sqlite3
import sys

def main():
    if len(sys.argv) < 2:
        print("[ERROR] 用法: python fix_picker_helper.py <数据库路径>")
        sys.exit(1)

    db_path = sys.argv[1]
    print(f"[INFO] 数据库: {db_path}")

    conn = sqlite3.connect(db_path)

    # 处理 out_order 表
    cols = [r[1] for r in conn.execute("PRAGMA table_info(out_order)").fetchall()]
    print(f"[INFO] out_order 现有列: {cols}")
    if "picker" not in cols:
        conn.execute("ALTER TABLE out_order ADD COLUMN picker VARCHAR(50)")
        conn.commit()
        print("[OK] 已添加 out_order.picker")
    else:
        print("[OK] out_order.picker 已存在")

    # 处理 production_requisition 表
    pr_cols = [r[1] for r in conn.execute("PRAGMA table_info(production_requisition)").fetchall()]
    print(f"[INFO] production_requisition 现有列: {pr_cols}")
    if "picker" not in pr_cols:
        conn.execute("ALTER TABLE production_requisition ADD COLUMN picker VARCHAR(50)")
        conn.commit()
        print("[OK] 已添加 production_requisition.picker")
    else:
        print("[OK] production_requisition.picker 已存在")

    conn.close()
    print("\n[INFO] 修复完成！")

if __name__ == "__main__":
    main()
