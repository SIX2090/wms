# -*- coding: utf-8 -*-
"""BUG-2026-09-10-007 回归（静态契约）：手机日报日期必须跨天自动刷新。

现象：ReportViewModel 在 App 启动时被创建，date 只在 init 取一次当天；
Android 进程常在后台存活数日，用户隔天打开报表页仍按启动日查询，
表现为「今天的记录查不到」（顶部日期其实显示的是旧日期）。

修复：UiState 增加 dateIsToday 标记；load() 在今天模式下先校正为系统当天；
手动翻天脱离今天模式，点「回到今天」重新进入今天模式。

验收：
- T1 UiState 必须有 dateIsToday 字段
- T2 load() 必须在今天模式下校正 date
- T3 shiftDay 必须脱离今天模式（避免用户翻到的日期被覆盖）
- T4 resetToday 必须恢复今天模式
"""
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
VM = (WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/"
      "ui/viewmodel/report/ReportViewModel.kt")


def _vm() -> str:
    return VM.read_text(encoding="utf-8")


def test_t1_ui_state_has_today_flag():
    src = _vm()
    assert "val dateIsToday: Boolean = true" in src, "ReportUiState 缺少 dateIsToday 标记"


def test_t2_load_refreshes_date_in_today_mode():
    src = _vm()
    load_start = src.index("fun load()")
    load_body = src[load_start:src.index("fun selectType")]
    assert "dateIsToday" in load_body, "load() 未判断今天模式"
    assert "apiDateFormat.format(Date())" in load_body, "load() 未校正为系统当天"


def test_t3_shift_day_leaves_today_mode():
    src = _vm()
    body = src[src.index("fun shiftDay"):src.index("fun resetToday")]
    assert "dateIsToday = false" in body, "手动翻天后必须脱离今天模式"


def test_t4_reset_today_restores_today_mode():
    src = _vm()
    body = src[src.index("fun resetToday"):src.index("fun clearError")]
    assert "dateIsToday = true" in body, "回到今天必须恢复今天模式"
