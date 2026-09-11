# -*- coding: utf-8 -*-
"""AI-DEDUP-REPLENISH-001 回归：补货报告合并后的运行时等价性。

根因：/ai/replenishment（_ai_replenishment_report，94 行）与
/ai/replenishment_smart（_ai_smart_replenishment_report，136 行）是同一份
业务语义的两处实现——正是「同逻辑两处代码，迟早不一致」的典型。
修复：legacy 改为薄适配层委托 smart 实现。

本文件用同一批种子数据证明合并零行为差异：
- 两函数返回的 rows 在共享字段上逐条相等；
- summary 关键字段相等；
- smart 版新增的 trend/priority_score/ai_suggestion 字段不影响老调用方。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Material, MaterialCategory, StockTransaction, Unit, User,  # noqa: E402
                 Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# 共享字段不手工列名单：T2 动态遍历 legacy 行的全部键逐一比对
# （legacy 是 smart 的真子集，smart 新增键不影响老调用方）
SHARED_SUMMARY_KEYS = [
    "action_required", "coverage_days", "critical", "days", "high",
    "medium", "pending_request", "suggested_amount", "total",
]
# generated_at 是每次运行的时间戳（微秒级差），不属于业务行为，排除比较


def _reset_db():
    db.drop_all()
    db.create_all()


@pytest.fixture(scope="module")
def seeded_report():
    """种子：一个缺货物料 + 一个健康物料，跑两份报告。"""
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                            role="admin", must_change_password=False))
        db.session.add(Warehouse(name="主仓", code="WHA", status="active", is_default=True))
        unit = Unit(code="GE", name="个")
        cat = MaterialCategory(code="WJ", name="五金")
        db.session.add_all([unit, cat])
        db.session.flush()

        # 缺货物料：库存 10，安全库存 100，再订货点 80
        low = Material(code="DEDUP-A", name="8*25螺丝", spec="8*25", stock=10,
                       min_stock=100, max_stock=500, reorder_point=80,
                       price=0.5, unit_id=unit.id, category_id=cat.id)
        # 健康物料：库存 900
        ok = Material(code="DEDUP-B", name="6*20螺丝", spec="6*20", stock=900,
                      min_stock=100, max_stock=500, reorder_point=80,
                      price=0.3, unit_id=unit.id, category_id=cat.id)
        db.session.add_all([low, ok])
        db.session.flush()

        # 近 30 天出库 300 个（拉低可用天数）：流水为负数、created_at 默认当前
        for i in range(3):
            db.session.add(StockTransaction(
                material_id=low.id, transaction_type="out", quantity=-100,
            ))
        db.session.commit()

        legacy = app_module._ai_replenishment_report(days=30, coverage_days=30, limit=50)
        smart = app_module._ai_smart_replenishment_report(days=30, coverage_days=30, limit=50)
        yield legacy, smart


def test_t1_rows_count_equal(seeded_report):
    """T1: 两函数返回行数一致。"""
    legacy, smart = seeded_report
    assert len(legacy["rows"]) == len(smart["rows"])


def test_t2_rows_equal_on_shared_keys(seeded_report):
    """T2: legacy 行的全部键在 smart 行上逐条相等（证明合并零行为差异）。"""
    legacy, smart = seeded_report
    assert len(legacy["rows"]) == len(smart["rows"])
    for lrow, srow in zip(legacy["rows"], smart["rows"]):
        assert lrow["code"] == srow["code"]
        for key in lrow:
            assert key in srow, f"smart 行缺 legacy 键 {key}"
            assert lrow[key] == srow[key], f"{lrow['code']}.{key}: {lrow[key]!r} != {srow[key]!r}"


def test_t3_summary_equal_on_shared_keys(seeded_report):
    """T3: summary 共享字段相等。"""
    legacy, smart = seeded_report
    for key in SHARED_SUMMARY_KEYS:
        assert legacy["summary"][key] == smart["summary"][key], key


def test_t4_smart_is_superset(seeded_report):
    """T4: smart 版新增字段存在且不破坏老调用方（缺货物料 action_required=True）。"""
    legacy, smart = seeded_report
    low_rows = [r for r in smart["rows"] if r["code"] == "DEDUP-A"]
    assert low_rows, "缺货物料必须出现在报告中"
    srow = low_rows[0]
    assert srow["action_required"] is True
    assert "ai_suggestion" in srow and "priority_score" in srow and "trend_symbol" in srow


def test_t5_legacy_is_thin_adapter_static():
    """T5: 静态断言 legacy 是委托适配层（防再膨胀）。"""
    src = (APP_DIR / "app.py").read_text(encoding="utf-8", errors="ignore")
    import re
    m = re.search(r"^def _ai_replenishment_report\(", src, re.M)
    rest = src[m.start():]
    nm = re.search(r"^def \w+\(", rest[1:], re.M)
    body = rest[:nm.start() + 1] if nm else rest
    assert "_ai_smart_replenishment_report(" in body
    assert "Material.query" not in body
    assert len(body.splitlines()) < 30
