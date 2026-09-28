# -*- coding: utf-8 -*-
"""P1-1 回归锁（2026-09-27）：`collect_from_app` 聚合下推不得改变判据结果。

背景
----
`scripts/verify_inventory_identity.py` 的 `collect_from_app()` 旧实现把
`stock_transaction`（append-only 流水表，仓库里增长最快的表）**逐行**实例化为
ORM 对象拉进内存，只为算两个 `GROUP BY ... SUM(quantity)` 聚合。P1-1 改为
**SQL 聚合下推**，行数与内存由「流水总行数」降到「(物料, 仓库) 组合数」。

本文件锁死的契约（注意措辞）
---------------------------
    ✅ 「聚合后累加结果等价」—— 下游判据的输入（`build_identity_rows` /
       `build_warehouse_rows` 的累加值）必须逐位相同；
    ❌ 而非「返回列表逐项相等」—— 下推版同一 `(物料,仓库)` 只出一行、
       旧版出 N 行，列表本来就不同，断言逐项相等是**错的测试**。

覆盖形态（对齐 R2 三口径）
-------------------------
1. 同 (物料, 仓库) 多行相加（含负数）；
2. `warehouse_id IS NULL` 历史行**不得被聚合丢失**（R2 历史脏数据兼容）；
3. 多仓库隔离（同一物料跨两个仓库各自独立）；
4. **判定结果**（findings / wh_findings / summary）两路径完全一致。

另附一条静态兜底：`collect_from_app` 的推送路径不得再出现全表 `.query.all()`
式的逐行读取（防日后被改回去，P1-1 静默失效）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
SCRIPTS_DIR = ROOT / "scripts"
for p in (str(APP_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
# 与 tests/test_p2b_three_ledger_guard.py 同一隔离模式：内存库 + 每测试 drop/create。
# 踩过的坑（本文件首版即栽在此）：改写 config.TestingConfig.SQLALCHEMY_DATABASE_URI
# 对**已初始化**的 app **不生效**（引擎与 session 已绑定），全量 pytest 下会读到
# 前序模块残留的库，断言 `materials == 2` 变成 3 —— 典型 R7 顺序依赖假失败。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"

import verify_inventory_identity as v  # noqa: E402
import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory,
    Material,
    StockTransaction,
    Warehouse,
    db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture
def scene():
    """函数级干净场景：每次 drop/create，杜绝顺序依赖。

    覆盖形态（对齐 R2 三口径）：
      M1 同一 (物料,仓库) 多行（含负数）+ NULL 归属行
      M2 跨两仓，各自独立
    """
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()

        w1 = Warehouse(name="P11仓A", code="P11-WA", status="active", is_default=False)
        w2 = Warehouse(name="P11仓B", code="P11-WB", status="active", is_default=False)
        m1 = Material(code="P11-M1", name="多行相加", stock=100.0)
        m2 = Material(code="P11-M2", name="跨两仓", stock=80.0)
        db.session.add_all([w1, w2, m1, m2])
        db.session.commit()

        txns = [
            (m1.id, 100.0, w1.id),   # A 仓：100 - 40 = 60
            (m1.id, -40.0, w1.id),
            (m1.id, 20.0, w2.id),    # B 仓 20
            (m1.id, 30.0, None),     # NULL 归属 30
            (m2.id, 50.0, w1.id),    # M2 A 仓 50
            (m2.id, 30.0, w2.id),    #    B 仓 30
        ]
        for mid, q, wid in txns:
            db.session.add(StockTransaction(material_id=mid, transaction_type="in",
                                            quantity=q, warehouse_id=wid))
        locs = [
            (m1.id, 60.0, w1.id, "P11-L1"),
            (m1.id, 20.0, w2.id, "P11-L2"),
            (m1.id, 30.0, None, "P11-L3"),
            (m2.id, 50.0, w1.id, "P11-L4"),
            (m2.id, 30.0, w2.id, "P11-L5"),
        ]
        for mid, q, wid, loc in locs:
            db.session.add(LocationInventory(material_id=mid, quantity=q,
                                             warehouse_id=wid, location=loc))
        db.session.commit()

        yield {"m1": m1.id, "m2": m2.id, "w1": w1.id, "w2": w2.id}
        db.session.rollback()


def _accumulate(triples):
    """把 (material_id, quantity, warehouse_id) 列表按 (物料,仓库) 累加。"""
    out = {}
    for mid, qty, wid in triples:
        key = (mid, wid)
        out[key] = out.get(key, 0.0) + float(qty or 0)
    return out


class TestAccumulationEquivalence:
    """两条路径的**累加结果**必须逐位相同（这是下游判据真正消费的形态）。"""

    def test_txn_accumulation_matches(self, scene):
        _, _, new_txns = v.collect_from_app(pushdown=True)
        _, _, old_txns = v.collect_from_app(pushdown=False)
        assert _accumulate(new_txns) == _accumulate(old_txns)

    def test_location_accumulation_matches(self, scene):
        _, new_locs, _ = v.collect_from_app(pushdown=True)
        _, old_locs, _ = v.collect_from_app(pushdown=False)
        assert _accumulate(new_locs) == _accumulate(old_locs)

    def test_materials_identical(self, scene):
        new_mats, _, _ = v.collect_from_app(pushdown=True)
        old_mats, _, _ = v.collect_from_app(pushdown=False)
        assert sorted(new_mats) == sorted(old_mats)


class TestAggregationSemantics:
    """下推版必须真的"聚合"：同 (物料,仓库) 只出一行。"""

    def test_pushdown_collapses_same_warehouse_rows(self, scene):
        _, _, txns = v.collect_from_app(pushdown=True)
        m1, w1 = scene["m1"], scene["w1"]
        rows = [t for t in txns if t[0] == m1 and t[2] == w1]
        assert len(rows) == 1, "同一 (物料,仓库) 应聚合为一行"
        assert rows[0][1] == pytest.approx(60.0), "100 + (-40) 应聚合为 60"

    def test_pushdown_multi_warehouse_isolated(self, scene):
        """R2 多仓隔离：同一物料在两个仓库各自独立聚合，不串仓。"""
        _, _, txns = v.collect_from_app(pushdown=True)
        m2 = scene["m2"]
        by_wh = {t[2]: t[1] for t in txns if t[0] == m2}
        assert by_wh[scene["w1"]] == pytest.approx(50.0)
        assert by_wh[scene["w2"]] == pytest.approx(30.0)

    def test_pushdown_keeps_null_warehouse_rows(self, scene):
        """R2 历史脏数据：NULL 归属行不得被 GROUP BY 静默丢弃。"""
        _, _, txns = v.collect_from_app(pushdown=True)
        m1 = scene["m1"]
        null_rows = [t for t in txns if t[0] == m1 and t[2] is None]
        assert len(null_rows) == 1
        assert null_rows[0][1] == pytest.approx(30.0)

    def test_pushdown_returns_plain_tuples_not_orm(self, scene):
        """下推版必须是裸元组（不再持有 ORM 对象，这才省内存）。"""
        mats, locs, txns = v.collect_from_app(pushdown=True)
        for row in tuple(mats) + tuple(locs) + tuple(txns):
            assert isinstance(row, tuple), f"应为裸元组，实际 {type(row)}"


class TestJudgementUnchanged:
    """最终判定结果必须完全一致 —— 这是 P1-1 属"净重构"的核心证据。"""

    @staticmethod
    def _run(pushdown):
        mats, locs, txns = v.collect_from_app(pushdown=pushdown)
        rows = v.build_identity_rows(mats, locs, txns)
        findings = v.find_mismatches(rows)
        wh_rows = v.build_warehouse_rows(locs, txns)
        wh_findings = v.find_warehouse_mismatches(rows, wh_rows)
        return v.summarize(rows, findings, wh_findings, wh_rows)

    def test_summary_identical(self, scene):
        assert self._run(True) == self._run(False)

    def test_findings_identical(self, scene):
        assert self._run(True)["findings"] == self._run(False)["findings"]
        assert (self._run(True)["warehouse_findings"]
                == self._run(False)["warehouse_findings"])

    def test_scene_numbers_are_as_expected(self, scene):
        """场景自检：确认夹具真的产出了预期的账（防夹具写错导致假绿）。"""
        s = self._run(True)
        # M1 总账 100；A 仓流水 60 / B 仓 20 / NULL 30 → Σ③ = 110 ≠ 100
        assert s["materials"] == 2
        assert s["mismatch_ledger_vs_txn"] >= 1


class TestAntiRegression:
    """静态兜底：防止有人把聚合下推改回全表逐行拉取（P1-1 静默失效）。"""

    def test_pushdown_path_has_no_full_table_all(self):
        src = (SCRIPTS_DIR / "verify_inventory_identity.py").read_text(encoding="utf-8")
        start = src.index("def collect_from_app(")
        end = src.index("def main()")
        body = src[start:end]
        # 推送路径必须用 group_by 聚合
        assert "group_by" in body, "collect_from_app 丢失聚合下推（group_by）"
        # 旧路径只能在 pushdown=False 分支里出现
        assert "if not pushdown:" in body, "缺少 pushdown 分支开关"
        # 推送分支内不得再有 StockTransaction.query.all()
        push_part = body.split("if not pushdown:")[1]
        tail = push_part.split("return materials, locations, transactions")[-1]
        assert "StockTransaction.query.all()" not in tail, (
            "推送路径又出现 StockTransaction.query.all() —— P1-1 被改回去了"
        )
