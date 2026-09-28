# -*- coding: utf-8 -*-
"""P2-3 前置：三账恒等式校验器纯逻辑单元测试（A9）。

只测 scripts/verify_inventory_identity.py 中不依赖 Flask/app 的纯函数
（build_identity_rows / find_mismatches / summarize），并覆盖 P2-3 要治的
那个 BUG 类别：**只写总账、不写库位账**（BUG-2026-08-16-002 / 08-04-002）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verify_inventory_identity as v  # noqa: E402


class TestBuildIdentityRows:
    def test_aggregates_three_accounts(self):
        rows = v.build_identity_rows(
            materials=[(1, "A001", 100.0)],
            locations=[(1, 60.0), (1, 40.0)],
            transactions=[(1, 120.0), (1, -20.0)],
        )
        r = rows[1]
        assert r["ledger"] == 100.0
        assert r["locations"] == 100.0
        assert r["txns"] == 100.0
        assert r["location_rows"] == 2

    def test_null_quantity_counted_as_zero(self):
        rows = v.build_identity_rows(
            materials=[(1, "A001", 5.0)],
            locations=[(1, None)],
            transactions=[(1, None)],
        )
        assert rows[1]["locations"] == 0.0
        assert rows[1]["txns"] == 0.0

    def test_material_without_material_master_still_listed(self):
        # 孤儿库位/流水（物料已删）也要出现在结果里，不能静默消失
        rows = v.build_identity_rows(
            materials=[], locations=[(99, 3.0)], transactions=[(99, 3.0)]
        )
        assert 99 in rows
        assert rows[99]["ledger"] == 0.0


class TestFindMismatches:
    def test_consistent_three_accounts_no_findings(self):
        rows = v.build_identity_rows([(1, "A001", 50.0)], [(1, 50.0)], [(1, 50.0)])
        assert v.find_mismatches(rows) == []

    def test_catches_ledger_without_location_sync(self):
        """P2-3 的 BUG 类别：消费点只 add_stock 没同步库位账 → ①≠② 必须被抓到。"""
        rows = v.build_identity_rows(
            materials=[(1, "A001", 100.0)],
            locations=[(1, 60.0)],
            transactions=[(1, 100.0)],
        )
        findings = v.find_mismatches(rows)
        assert len(findings) == 1
        f = findings[0]
        assert f["dimension"] == "ledger_vs_location"
        assert f["ledger"] == 100.0
        assert f["other"] == 60.0
        assert f["delta"] == 40.0

    def test_catches_ledger_vs_txn_drift(self):
        rows = v.build_identity_rows([(2, "B002", 30.0)], [(2, 30.0)], [(2, 25.0)])
        findings = v.find_mismatches(rows)
        assert [f["dimension"] for f in findings] == ["ledger_vs_txn"]
        assert findings[0]["delta"] == 5.0

    def test_no_location_rows_not_flagged_as_location_mismatch(self):
        """关库位管理时无库位账属预期，不应判为 ①≠②。"""
        rows = v.build_identity_rows([(3, "C003", 10.0)], [], [(3, 10.0)])
        assert v.find_mismatches(rows) == []
        assert rows[3]["location_rows"] == 0

    def test_tolerance_absorbs_rounding(self):
        rows = v.build_identity_rows([(4, "D004", 10.0)], [(4, 10.004)], [(4, 10.0)])
        assert v.find_mismatches(rows, tolerance=0.01) == []
        rows2 = v.build_identity_rows([(4, "D004", 10.0)], [(4, 10.5)], [(4, 10.0)])
        assert len(v.find_mismatches(rows2, tolerance=0.01)) == 1


class TestSummarize:
    def test_counts_by_dimension(self):
        rows = v.build_identity_rows(
            materials=[(1, "A", 100.0), (2, "B", 30.0)],
            locations=[(1, 60.0), (2, 30.0)],
            transactions=[(1, 100.0), (2, 25.0)],
        )
        s = v.summarize(rows, v.find_mismatches(rows))
        assert s["materials"] == 2
        assert s["materials_with_location_rows"] == 2
        assert s["mismatch_ledger_vs_location"] == 1
        assert s["mismatch_ledger_vs_txn"] == 1


class TestP01WarehouseDimension:
    """P0-1 回归锁（2026-09-27）：仓级串仓必须被抓到。

    物料级 ①=Σ② 只能证明**总数**对，不能证明**分布**对。
    本类锁死的是：A 仓少算 / B 仓多算、合计恰好相等时，
    仓级维度必须报错——这正是 AGENTS.md R2「多仓库隔离」的最低要求，
    也是 BUG-2026-09-02-001 / 09-03-001/002/004 的同一根因方向。
    """

    def test_warehouse_cross_contamination_is_caught(self):
        """核心回归：物料级全绿但仓级串仓 → 仓级必须报出 2 条。"""
        rows = v.build_identity_rows(
            materials=[(1, "M1", 100.0)],
            locations=[(1, 20.0), (1, 80.0)],      # 应 A=60 / B=40，被写坏
            transactions=[(1, 60.0), (1, 40.0)],
        )
        # 物料级：总数仍 100，合计相等 → 旧版判据在此全绿（P0-1 的漏网口）
        assert v.find_mismatches(rows) == []

        wh = v.build_warehouse_rows(
            locations=[(1, 20.0, "WHA"), (1, 80.0, "WHB")],
            transactions=[(1, 60.0, "WHA"), (1, 40.0, "WHB")],
        )
        wh_findings = v.find_warehouse_mismatches(rows, wh)
        assert len(wh_findings) == 2
        by_wh = {f["warehouse_id"]: f for f in wh_findings}
        assert by_wh["WHA"]["delta"] == -40.0   # 库位 20 − 流水 60
        assert by_wh["WHB"]["delta"] == 40.0    # 库位 80 − 流水 40
        assert all(f["dimension"] == "wh_location_vs_txn" for f in wh_findings)

        s = v.summarize(rows, v.find_mismatches(rows), wh_findings, wh)
        assert s["mismatch_wh_location_vs_txn"] == 2

    def test_correct_warehouse_split_stays_green(self):
        """对照：仓级正确时不得误报（防止修成"见仓库就报"）。"""
        rows = v.build_identity_rows(
            materials=[(1, "M1", 100.0)],
            locations=[(1, 60.0), (1, 40.0)],
            transactions=[(1, 60.0), (1, 40.0)],
        )
        wh = v.build_warehouse_rows(
            locations=[(1, 60.0, "WHA"), (1, 40.0, "WHB")],
            transactions=[(1, 60.0, "WHA"), (1, 40.0, "WHB")],
        )
        assert v.find_warehouse_mismatches(rows, wh) == []

    def test_null_warehouse_not_guessed_into_any_warehouse(self):
        """R2/INVENTORY_TRUTH.md §3.2：NULL 历史行保留 NULL，不得猜归属。

        既不能判错（归属本就不确定），也不能被静默并进某个真实仓库。
        """
        rows = v.build_identity_rows(
            materials=[(1, "M1", 50.0)],
            locations=[(1, 50.0)],
            transactions=[(1, 50.0)],
        )
        wh = v.build_warehouse_rows(
            locations=[(1, 50.0, None)], transactions=[(1, 50.0, None)]
        )
        assert v.find_warehouse_mismatches(rows, wh) == []
        assert list(wh[1]["by_wh"].keys()) == [v.UNATTRIBUTED]
        assert wh[1]["unattributed_locations"] == 50.0

        s = v.summarize(rows, v.find_mismatches(rows), [], wh)
        assert s["unattributed_materials"] == 1

    def test_cross_warehouse_pair_still_caught_when_total_matches(self):
        """最刁钻形态：一仓多、另一仓等额少，且混入 NULL 桶，仍必须抓到。"""
        rows = v.build_identity_rows(
            materials=[(2, "M2", 30.0)],
            locations=[(2, 50.0), (2, -20.0)],
            transactions=[(2, 30.0)],
        )
        wh = v.build_warehouse_rows(
            locations=[(2, 50.0, 7), (2, -20.0, 8)],
            transactions=[(2, 10.0, 7), (2, 20.0, 8)],
        )
        findings = v.find_warehouse_mismatches(rows, wh)
        assert {f["warehouse_id"] for f in findings} == {7, 8}

    def test_backward_compat_untagged_tuples(self):
        """向后兼容：2 元组入参（无 warehouse_id）不炸，按 NULL 处理。"""
        wh = v.build_warehouse_rows(
            locations=[(1, 10.0)], transactions=[(1, 10.0)]
        )
        assert wh[1]["by_wh"][v.UNATTRIBUTED]["locations"] == 10.0

    def test_summarize_without_wh_keeps_legacy_keys(self):
        """向后兼容：summarize 不传仓级参数时，输出键与旧版一致。"""
        rows = v.build_identity_rows([(1, "A", 5.0)], [(1, 5.0)], [(1, 5.0)])
        s = v.summarize(rows, v.find_mismatches(rows))
        assert "warehouse_findings" not in s
        assert "mismatch_wh_location_vs_txn" not in s
