# -*- coding: utf-8 -*-
"""R6 机制级守卫：auto_migrate_database 的新增列必须有「无条件兜底」覆盖。

R6 = 同一类生产事故反复复发（本文件建立时已第 5 次）：新业务的迁移列只写进
``app.py auto_migrate_database()``，而 ``start_wms_offline.bat`` /
``start_wms_auto.bat`` 默认 ``WMS_NO_DB_TOUCH=1`` 会把它整体跳过，
兜底的 ``app/fix_db_columns.py`` 往往没同步（``start_wms_auto.bat`` 更是
连 fix_db_columns 都不跑）。于是——

    功能上线前建好的存量库，重启后永远补不上这些列，
    一查即 sqlalchemy.exc.OperationalError: no such column: xxx → 500

已发生的 5 次：print_job（08-20）、excel_print_template（08-22）、
stock_transaction.warehouse_id（08-28）、盘点域 6 列（09-05）、
销售退货入库 3 列（09-12，本次）。

根治手段是「无条件执行的 ensure_* 兜底函数」：独立于迁移开关、幂等。
本测试是这条纪律的闸门——

1. **已知债务清单** ``KNOWN_GAP``：静态解析出「在 auto_migrate_database 里
   ADD、但没有 ensure_* 无条件兜底」的列，逐条登记在案，见光不死。
2. **增量闸门**：今后任何人在 auto_migrate_database 里加列却没同步补
   ensure_* 兜底，本测试立刻变红（新缺口不在清单里）。
3. **清单精确性**：清单必须与实测缺口完全一致——补了兜底就要把条目删掉，
   防止清单越滚越大、失真失效。

为什么 ``fix_db_columns.py`` 不算合规兜底：它只被 start_wms_offline.bat
调用，start_wms_auto.bat 不跑它，覆盖不到全部部署形态。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"

# auto_migrate_database 中「f-string 动态拼接」的 ALTER 数量（无法静态取列名）。
# 若这个数字变化，说明有人引入了新的动态形式，必须人工核对是否已被兜底覆盖，
# 否则动态列会绕过本闸门。改这里之前请先读懂上面第 2 条。
KNOWN_DYNAMIC_ALTERS = 4


def _function_source(src: str, name: str) -> str:
    """截取顶层 ``def name(...)`` 的函数体源码（到下一个顶层 def/class 为止）。"""
    m = re.search(rf'^def {re.escape(name)}\(', src, re.M)
    assert m, f"app.py 中未找到函数 {name}"
    nxt = [p for p in (src.find('\ndef ', m.end()), src.find('\nclass ', m.end())) if p != -1]
    return src[m.start():min(nxt)] if nxt else src[m.start():]


def _migration_columns(src: str) -> tuple[set[tuple[str, str]], int]:
    """从 auto_migrate_database 里取出 (表, 列) 集合 + 动态 f-string ALTER 数量。"""
    body = _function_source(src, 'auto_migrate_database')
    cols = set(re.findall(r'ALTER TABLE (\w+) ADD COLUMN (\w+)', body))
    dynamic = len(re.findall(r'ALTER TABLE \w+ ADD COLUMN \{', body))
    return cols, dynamic


def _unconditional_ensure_columns(src: str) -> set[tuple[str, str]]:
    """所有 ensure_* 兜底函数（无条件执行）覆盖到的 (表, 列) 集合。"""
    covered: set[tuple[str, str]] = set()
    for m in re.finditer(r'^def (ensure_\w+)\(', src, re.M):
        covered |= set(re.findall(r'ALTER TABLE (\w+) ADD COLUMN (\w+)', _function_source(src, m.group(1))))
    return covered


# ---- 已知债务：只有 auto_migrate_database 会加、没有无条件兜底的列 ----
# 这些列在 WMS_NO_DB_TOUCH=1 的存量库上重启补不上，属历史欠账，逐条列示。
# 补齐某一列的 ensure_* 兜底后，请把对应条目从这里删除（清单必须保持精确）。
KNOWN_GAP = {
    ("adjustment_order", "warehouse"),
    ("after_sale_out_order", "location"),
    ("after_sale_out_order_item", "remark"),
    ("ai_material_alias", "disabled"),
    ("ai_material_alias", "disabled_reason"),
    ("ai_tool_call", "denied_reason"),
    ("ai_tool_call", "denied_stage"),
    ("ai_tool_call", "role"),
    ("ai_tool_call", "source"),
    ("ai_tool_call", "user_id"),
    ("api_token", "last_used_at"),
    ("employee", "code"),
    ("in_order", "auto_push_requisition"),
    ("in_order", "business_type"),
    ("in_order", "customer_id"),
    ("in_order", "location"),
    ("in_order", "source_purchase_order_id"),
    ("in_order", "warehouse"),
    ("in_order_item", "is_customer_supplied"),
    ("in_order_item", "remark"),
    ("in_order_item", "source_purchase_order_item_id"),
    ("inventory_check", "warehouse"),
    ("inventory_check_scan", "warehouse"),
    ("location_inventory", "warehouse_id"),
    ("material", "brand"),
    ("material", "remark"),
    ("material_category", "code"),
    ("material_category", "parent_id"),
    ("opening_stock", "date"),
    ("opening_stock", "location"),
    ("opening_stock", "warehouse_id"),
    ("out_order", "business_type"),
    ("out_order", "customer"),
    ("out_order", "location"),
    ("out_order", "source_sales_order_id"),
    ("out_order", "warehouse"),
    ("out_order_item", "remark"),
    ("out_order_item", "source_sales_order_item_id"),
    ("print_workstation", "auth_token"),
    ("print_workstation", "last_heartbeat"),
    ("production_requisition", "location"),
    ("production_requisition", "picker"),
    ("production_requisition", "warehouse"),
    ("purchase_request_item", "supplier_name"),
    ("sales_order", "currency"),
    ("sales_order", "project_no"),
    ("sales_order", "remaining_amount"),
    ("sales_order", "salesperson_id"),
    ("sales_order", "settlement_method"),
    ("sales_order", "shipped_amount"),
    ("sales_order", "tax_amount"),
    ("sales_order", "untaxed_amount"),
    ("sales_order", "warehouse"),
    ("sales_order", "warehouse_id"),
    ("sales_order_item", "batch_no"),
    ("sales_order_item", "serial_no"),
    ("sales_order_item", "tax_amount"),
    ("sales_order_item", "tax_included_amount"),
    ("sales_order_item", "tax_rate"),
    ("sales_order_item", "untaxed_amount"),
    ("sales_order_item", "untaxed_price"),
    ("supplier", "code"),
    ("transfer_order", "from_warehouse"),
    ("transfer_order", "to_warehouse"),
    ("transfer_order_item", "amount"),
    ("transfer_order_item", "price"),
    ("transfer_order_item", "remark"),
    ("unit", "code"),
    ("user", "bio"),
    ("user", "email"),
    ("user", "login_ip_failed_count"),
    ("user", "login_ip_locked_until"),
    ("user", "login_lock_ip"),
    ("user", "must_change_password"),
    ("user", "phone"),
    ("warehouse", "is_default"),
    ("wechat_share_config", "auto_send"),
}


def test_no_new_column_without_unconditional_ensure():
    """增量闸门：新增迁移列必须有 ensure_* 无条件兜底，否则本测试变红。

    修法：在 app.py 加一个仿 ensure_sales_return_source_columns 的兜底函数
    （独立 sqlite 连接 + 无条件执行 + 幂等），并在模块导入阶段调用它；
    或者把该列登记进 KNOWN_GAP 并明确接受它会在 WMS_NO_DB_TOUCH=1 的
    存量库上炸——后者请想清楚，前 5 次事故都是这么来的。
    """
    src = APP_PY.read_text(encoding='utf-8')
    mig_cols, dynamic = _migration_columns(src)
    covered = _unconditional_ensure_columns(src)
    gap = mig_cols - covered

    new_gap = gap - KNOWN_GAP
    assert not new_gap, (
        "以下迁移列只在 auto_migrate_database() 里 ADD，没有 ensure_* 无条件兜底，"
        "WMS_NO_DB_TOUCH=1 时存量库重启补不上（R6 复发）。\n"
        "请补兜底函数，或显式登记进 KNOWN_GAP：\n  "
        + "\n  ".join(f"{t}.{c}" for t, c in sorted(new_gap))
    )

    # 清单里已修好的条目必须删掉，否则债务清单失真、失去闸门意义
    stale = KNOWN_GAP - gap
    assert not stale, (
        "以下列已有 ensure_* 兜底，请从 KNOWN_GAP 删除对应条目（清单须与实测一致）：\n  "
        + "\n  ".join(f"{t}.{c}" for t, c in sorted(stale))
    )


def test_dynamic_alter_count_unchanged():
    """动态 f-string ALTER 数量变化 → 人工核对（它会绕过本闸门）。"""
    src = APP_PY.read_text(encoding='utf-8')
    _, dynamic = _migration_columns(src)
    assert dynamic == KNOWN_DYNAMIC_ALTERS, (
        f"auto_migrate_database 里动态拼接的 ALTER 数量从 {KNOWN_DYNAMIC_ALTERS} "
        f"变成 {dynamic}：动态列无法静态取列名，请人工确认已有无条件兜底，"
        "再同步更新 KNOWN_DYNAMIC_ALTERS。"
    )


def test_known_gap_documented_not_growing():
    """债务规模只许缩小：记录当前缺口数，防止有人偷偷加列不补兜底。"""
    src = APP_PY.read_text(encoding='utf-8')
    mig_cols, _ = _migration_columns(src)
    covered = _unconditional_ensure_columns(src)
    gap = mig_cols - covered
    assert len(KNOWN_GAP) == len(gap), (
        f"KNOWN_GAP 登记 {len(KNOWN_GAP)} 条，实测缺口 {len(gap)} 条，两侧须一致"
    )
