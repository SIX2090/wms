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
