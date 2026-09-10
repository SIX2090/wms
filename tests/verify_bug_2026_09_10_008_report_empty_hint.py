# -*- coding: utf-8 -*-
"""BUG-2026-09-10-008 回归（静态契约）：日报空态必须说明「为什么查不到」。

背景：报表只统计「已完成」单据，PC 端录入保存后默认 pending（需人工点完成），
手机端只显示一句「当日暂无领料单明细」，现场无从判断是没单、单没完成、
业务类型不对还是查错仓库。

配套改动：
- 后端 daily_detail 输出 warehouse / server_today / diagnostics（见 001 测试）
- Android ReportModels 增加 warehouse / serverToday / diagnostics（可空）
- Android ReportScreens 空态文案动态化 + 日期条显示当前查询仓库

验收：
- T1 ReportModels 必须声明 warehouse / server_today / diagnostics 且可空
- T2 必须有 DailyReportDiagnostics（pending_orders / other_type_orders）
- T3 空态必须走 emptyStateHint，不得仍是硬编码单句
- T4 emptyStateHint 必须对 diagnostics 判空（旧版后端无该节点时 Gson 置 null）
- T5 日期条必须显示实际查询的仓库
- T6 空态文案必须提示「未完成」与「其他类型」两类原因
"""
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MODELS = (WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/"
          "data/model/ReportModels.kt")
SCREEN = (WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/"
          "ui/screens/ReportScreens.kt")


def test_t1_models_have_diagnostic_fields():
    src = MODELS.read_text(encoding="utf-8")
    for field, ser in (("warehouse", "warehouse"),
                       ("serverToday", "server_today"),
                       ("diagnostics", "diagnostics")):
        assert f'@SerializedName("{ser}")' in src, f"DailyReportData 缺少 {ser}"
        assert f"val {field}:" in src, f"DailyReportData 缺少字段 {field}"
    # 可空 + 默认值：旧版后端无该字段时 Gson 置 null，UI 必须判空
    assert 'val warehouse: String? = null' in src
    assert 'val diagnostics: DailyReportDiagnostics? = null' in src


def test_t2_diagnostics_model_exists():
    src = MODELS.read_text(encoding="utf-8")
    assert "data class DailyReportDiagnostics(" in src
    assert '@SerializedName("pending_orders")' in src
    assert '@SerializedName("other_type_orders")' in src


def test_t3_empty_state_uses_hint_function():
    src = SCREEN.read_text(encoding="utf-8")
    assert "emptyStateHint(uiState.report, uiState.reportType.label)" in src, (
        "空态必须调用 emptyStateHint（动态提示），不得硬编码"
    )
    assert "private fun emptyStateHint(" in src


def test_t4_hint_null_safe():
    src = SCREEN.read_text(encoding="utf-8")
    body = src[src.index("private fun emptyStateHint("):]
    body = body[:body.index("@Composable")]
    assert "?: return base" in body, "diagnostics 为 null（旧版后端）必须回退基础文案"
    assert "pendingOrders ?: 0" in body, "pendingOrders 必须判空"


def test_t5_date_bar_shows_warehouse():
    src = SCREEN.read_text(encoding="utf-8")
    assert 'uiState.report?.warehouse?.let' in src, "日期条需显示实际查询的仓库"


def test_t6_hint_covers_both_reasons():
    src = SCREEN.read_text(encoding="utf-8")
    assert "张单据未完成" in src, "空态需提示未完成单据（PC 录入后需点完成）"
    assert "其他类型单据" in src, "空态需提示业务类型不在统计口径内"
