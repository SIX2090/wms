# -*- coding: utf-8 -*-
"""P2-1 压测基线脚本纯逻辑单元测试（A9）。

只测 scripts/perf_baseline.py 中不依赖 Flask/app 的纯函数：
percentile / summarize / regression_alerts。app 相关压测装置由 CI 的
perf.yml 实际运行验证（含 waitress 起服与 10 接口测量）。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import perf_baseline as pb  # noqa: E402


class TestPercentile:
    def test_empty(self):
        assert pb.percentile([], 95) == 0.0

    def test_single(self):
        assert pb.percentile([5.0], 95) == 5.0

    def test_interpolates(self):
        values = [float(i) for i in range(1, 101)]  # 1..100
        assert pb.percentile(values, 50) == 50.5
        # 95 分位：rank = 0.95 * 99 = 94.05 → 95 + 0.05 ≈ 95.05
        assert abs(pb.percentile(values, 95) - 95.05) < 0.01

    def test_max_below_100pct(self):
        assert pb.percentile([1.0, 2.0, 3.0], 100) == 3.0


class TestSummarize:
    def test_basic_stats(self):
        s = pb.summarize([10.0, 20.0, 30.0, 40.0], elapsed_s=2.0, errors=1)
        assert s["count"] == 4
        assert s["errors"] == 1
        assert s["rps"] == 2.0
        assert s["mean_ms"] == 25.0
        assert s["max_ms"] == 40.0
        assert s["p50_ms"] == 25.0

    def test_empty_no_crash(self):
        s = pb.summarize([], elapsed_s=3.0, errors=2)
        assert s["count"] == 0
        assert s["mean_ms"] == 0.0
        assert s["errors"] == 2


class TestRegressionAlerts:
    BASE = {
        "stock_query": {"p95_ms": 100.0, "label": "库存查询"},
        "material": {"p95_ms": 20.0, "label": "物料列表"},
    }

    def test_no_regression_no_alert(self):
        cur = {
            "stock_query": {"p95_ms": 120.0, "label": "库存查询"},
            "material": {"p95_ms": 22.0, "label": "物料列表"},
        }
        assert pb.regression_alerts(self.BASE, cur) == []

    def test_alert_needs_both_conditions(self):
        # 相对 +60% 但绝对仅 +12ms（< 50ms 绝对阈值）→ 不告警（百分比噪声）
        cur = {"material": {"p95_ms": 32.0, "label": "物料列表"}}
        assert pb.regression_alerts(self.BASE, cur) == []
        # 相对 +60% 且绝对 +60ms → 告警
        cur = {"stock_query": {"p95_ms": 160.0, "label": "库存查询"}}
        alerts = pb.regression_alerts(self.BASE, cur)
        assert len(alerts) == 1
        assert alerts[0]["key"] == "stock_query"
        assert alerts[0]["delta_pct"] == 60.0

    def test_missing_baseline_key_skipped(self):
        cur = {"new_ep": {"p95_ms": 999.0, "label": "新接口"}}
        assert pb.regression_alerts(self.BASE, cur) == []


class TestEndpointContract:
    def test_ten_get_endpoints(self):
        # P2-1 约定：10 个最高频只读 GET 接口
        assert len(pb.ENDPOINTS) == 10
        keys = {e["key"] for e in pb.ENDPOINTS}
        assert {"stock_query", "in_order_list", "out_order_list",
                "material_search", "opening_stock", "check_list"} <= keys

    def test_alert_thresholds_positive(self):
        assert pb.ALERT_REL_PCT > 0 and pb.ALERT_ABS_MS > 0
