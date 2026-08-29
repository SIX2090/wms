# -*- coding: utf-8 -*-
"""BUG-2026-08-29-002：库存台账末行结存排序错乱与明细静默截断。

根因：
① ``_collect_ledger_rows`` 按 ``(日期, 物料代码, 单号)`` 排序，单据号字典序
   不等于发生时间顺序；同一天同一物料多笔流水时，翻到该物料最后一行看到的
   ``balance_quantity`` 并非最终结存（实测 6 个物料受影响，如 201033 实际
   结存 0 但页面末行显示 800）。
② 明细查询写死 ``.limit(5000)`` 且按 ``material_id`` 升序截断——流水超过
   上限后，物料 ID 较大的流水整段丢失，结存静默归零且无任何提示。

T1. ``LEDGER_ROW_LIMIT`` 常量存在且提高到 50000（原硬编码 5000）。
T2. 源码中不再出现写死的 ``.limit(5000)`` 截断。
T3. 超限时先计数再告警，且告警提示缩小查询范围（不再静默）。
T4. 排序键含真实发生时间与流水 ID，返回前清除临时字段（结构不泄漏）。
T5. 无仓库筛选时返回空列表（AGENTS.md 报表仓库必填规则不回归）。
"""
from __future__ import annotations

import inspect
import os
import re
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

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

APP_PY = (APP_DIR / "app.py").read_text(encoding="utf-8")
# 只针对台账函数本体做断言，避免误伤其他报表里同名的 .limit(5000)
LEDGER_SRC = inspect.getsource(app_module._collect_ledger_rows)


def test_t1_ledger_row_limit_raised():
    """明细上限提为 50000 常量，显著高于原硬编码 5000。"""
    limit = getattr(app_module, "LEDGER_ROW_LIMIT", None)
    assert limit is not None, "LEDGER_ROW_LIMIT 常量缺失"
    assert int(limit) == 50000
    assert int(limit) > 5000


def test_t2_no_hardcoded_limit_5000():
    """台账明细中不得再出现写死的 .limit(5000)；必须改用常量。"""
    assert not re.search(r"\.limit\(\s*5000\s*\)", LEDGER_SRC)
    assert ".limit(LEDGER_ROW_LIMIT)" in LEDGER_SRC


def test_t3_overflow_warns_instead_of_silent_truncate():
    """超限前先 count，超限时告警并提示缩小范围（不再静默截断）。"""
    assert "ledger_total = query.count()" in LEDGER_SRC
    assert "ledger_total > LEDGER_ROW_LIMIT" in LEDGER_SRC
    assert "app.logger.warning" in LEDGER_SRC
    assert "请缩小查询范围" in LEDGER_SRC


def test_t4_sort_uses_real_time_and_cleans_temp_fields():
    """排序按发生时间+流水 ID（可跨行），返回前清除 _ts/_txn_id 临时字段。"""
    match = re.search(r"rows\.sort\(key=.*?\)\s*\n", LEDGER_SRC, re.S)
    assert match is not None, "未找到台账排序语句"
    sort_src = match.group(0)
    assert "_ts" in sort_src, "排序键缺少真实发生时间"
    assert "_txn_id" in sort_src, "排序键缺少流水 ID 兜底"
    # 返回前必须清掉临时字段，避免 rows 结构泄漏给调用方与前端
    assert "row.pop('_ts'" in LEDGER_SRC or 'row.pop("_ts"' in LEDGER_SRC
    assert "row.pop('_txn_id'" in LEDGER_SRC or 'row.pop("_txn_id"' in LEDGER_SRC


def test_t5_no_warehouse_returns_empty():
    """报表仓库必填规则不回归：无仓库条件直接返回空。"""
    with app_module.app.app_context():
        assert app_module._collect_ledger_rows({}) == []
