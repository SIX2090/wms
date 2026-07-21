#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-BUG-F06 中低优 bug 专项验证脚本。

检查 G1-G6 修复点：
- G1 add_material 4 参数（min_stock/max_stock/reorder_point/alert_days）必须用
  parse_float_value/parse_int_value，不得有裸 float()/int() 解析
- G2 edit_material alert_days 必须用 parse_int_value
- G3 AI 路由 4 处 limit/window_hours 必须用 parse_int_value
- G4 数量解析 6 处必须用 parse_float_value，不得有裸 float(request.form.get('quantity'...))
- G5 标签模板 4 参数必须用 parse_float_value/parse_int_value
- G6 utils.py 必须有 parse_int_value 定义
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    failures: list[str] = []

    # ── G6: utils.py 必须有 parse_int_value ──
    utils_src = read_text("app/utils.py")
    if "def parse_int_value(" not in utils_src:
        failures.append("G6: app/utils.py 缺少 parse_int_value 定义")
    # parse_int_value 必须处理 None/空串/异常/越界
    if "minimum" not in utils_src or "maximum" not in utils_src:
        failures.append("G6: app/utils.py parse_int_value 必须支持 minimum/maximum 夹紧")

    # ── G1: add_material 4 参数 ──
    app_src = read_text("app/app.py")
    # 找到 add_material 函数体（从 def add_material 到下一个 def）
    add_material_match = re.search(
        r"def add_material\(.*?\n(?=def |\Z)", app_src, re.S
    )
    if not add_material_match:
        failures.append("G1: app/app.py 未找到 add_material 函数")
    else:
        add_material_body = add_material_match.group(0)
        # alert_days 必须用 parse_int_value
        if re.search(r"alert_days\s*=\s*int\(", add_material_body):
            failures.append("G1: add_material 中 alert_days 仍使用裸 int() 解析")
        if "parse_int_value" not in add_material_body:
            failures.append("G1: add_material 未使用 parse_int_value 解析 alert_days")
        # min_stock/max_stock/reorder_point 必须用 parse_float_value
        if re.search(r"min_stock\s*=\s*float\(", add_material_body):
            failures.append("G1: add_material 中 min_stock 仍使用裸 float() 解析")
        if re.search(r"max_stock\s*=\s*float\(", add_material_body):
            failures.append("G1: add_material 中 max_stock 仍使用裸 float() 解析")
        if re.search(r"reorder_point\s*=\s*float\(", add_material_body):
            failures.append("G1: add_material 中 reorder_point 仍使用裸 float() 解析")

    # ── G2: edit_material alert_days ──
    edit_material_match = re.search(
        r"def edit_material\(.*?\n(?=def |\Z)", app_src, re.S
    )
    if not edit_material_match:
        failures.append("G2: app/app.py 未找到 edit_material 函数")
    else:
        edit_material_body = edit_material_match.group(0)
        if re.search(r"alert_days\s*=\s*int\(", edit_material_body):
            failures.append("G2: edit_material 中 alert_days 仍使用裸 int() 解析")
        if "parse_int_value" not in edit_material_body:
            failures.append("G2: edit_material 未使用 parse_int_value 解析 alert_days")

    # ── G3: AI 路由 4 处 limit/window_hours ──
    # api_ai_data_cleanup_logs, api_ai_launch_acceptance, api_ai_rollout_audit,
    # api_ai_rollout_fallback_tasks
    ai_route_names = [
        "api_ai_data_cleanup_logs",
        "api_ai_launch_acceptance",
        "api_ai_rollout_audit",
        "api_ai_rollout_fallback_tasks",
    ]
    for route_name in ai_route_names:
        route_match = re.search(
            rf"def {route_name}\(.*?\n(?=def |\Z)", app_src, re.S
        )
        if not route_match:
            failures.append(f"G3: app/app.py 未找到 {route_name} 函数")
            continue
        route_body = route_match.group(0)
        # 不得有裸 int(request.args.get('limit'...)) 或 int(request.args.get('window_hours'...))
        if re.search(r"int\(request\.args\.get\(['\"](?:limit|window_hours)['\"]", route_body):
            failures.append(
                f"G3: {route_name} 仍使用裸 int() 解析 limit/window_hours"
            )
        # 必须用 parse_int_value
        if "parse_int_value" not in route_body:
            failures.append(
                f"G3: {route_name} 未使用 parse_int_value 解析 limit/window_hours"
            )

    # ── G4: 数量解析 6 处 ──
    # add_bom_item, add_subcontract_item, add_subcontract_issue_item,
    # add_subcontract_receive_item (quantity + scrap_quantity), add_transfer_item
    g4_functions = [
        "add_bom_item",
        "add_subcontract_item",
        "add_subcontract_issue_item",
        "add_subcontract_receive_item",
        "add_transfer_item",
    ]
    for func_name in g4_functions:
        func_match = re.search(
            rf"def {func_name}\(.*?\n(?=def |\Z)", app_src, re.S
        )
        if not func_match:
            failures.append(f"G4: app/app.py 未找到 {func_name} 函数")
            continue
        func_body = func_match.group(0)
        # 不得有 float(request.form.get('quantity'...)) 或 float(request.form.get('scrap_quantity'...))
        if re.search(
            r"float\(request\.form\.get\(['\"](?:quantity|scrap_quantity)['\"]",
            func_body,
        ):
            failures.append(
                f"G4: {func_name} 仍使用裸 float() 解析 quantity/scrap_quantity"
            )
        # 必须用 parse_float_value
        if "parse_float_value" not in func_body:
            failures.append(
                f"G4: {func_name} 未使用 parse_float_value 解析数量"
            )

    # ── G5: 标签模板 4 参数 ──
    add_label_match = re.search(
        r"def add_label_template\(.*?\n(?=def |\Z)", app_src, re.S
    )
    if not add_label_match:
        failures.append("G5: app/app.py 未找到 add_label_template 函数")
    else:
        add_label_body = add_label_match.group(0)
        # width/height 不得用裸 float()
        if re.search(r"width\s*=\s*float\(", add_label_body):
            failures.append("G5: add_label_template 中 width 仍使用裸 float() 解析")
        if re.search(r"height\s*=\s*float\(", add_label_body):
            failures.append("G5: add_label_template 中 height 仍使用裸 float() 解析")
        # cols/rows 不得用裸 int()
        if re.search(r"cols\s*=\s*int\(", add_label_body):
            failures.append("G5: add_label_template 中 cols 仍使用裸 int() 解析")
        if re.search(r"rows\s*=\s*int\(", add_label_body):
            failures.append("G5: add_label_template 中 rows 仍使用裸 int() 解析")
        # 必须用 parse_float_value 和 parse_int_value
        if "parse_float_value" not in add_label_body:
            failures.append("G5: add_label_template 未使用 parse_float_value 解析 width/height")
        if "parse_int_value" not in add_label_body:
            failures.append("G5: add_label_template 未使用 parse_int_value 解析 cols/rows")

    if failures:
        print("FAIL MEDIUM-LOW-FIXES:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS MEDIUM-LOW-FIXES: G1-G6 全部修复点检测到加固")
    return 0


if __name__ == "__main__":
    sys.exit(main())
