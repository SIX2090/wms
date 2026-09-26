#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-MOB-RPT-F03 安卓端「库存日报日期翻页 + 自动展示 >0 结存」静态验证。

本地无 Android SDK（与台账约定一致：Android 改动由 CI assembleRelease/testReleaseUnitTest
校验），本脚本对源码做特征断言：
  T1 接口链路 date 参数贯通：WmsApiService / WmsRepository / ViewModel 三处一致；
  T2 日期导航：shiftDay / resetToday / 今天模式校正存在，且钳制未来日期；
  T3 页面 UI：前后翻页箭头 + 回到今天 + 到今天禁用后翻；
  T4 空态文案与 >0 口径一致（「该仓当天无结存物料」）；
  T5 文案对齐用户口径：副标题为「各物料每日结存 · 按仓展示」。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

api = (ROOT / "data" / "api" / "WmsApiService.kt").read_text(encoding="utf-8")
repo = (ROOT / "data" / "repository" / "WmsRepository.kt").read_text(encoding="utf-8")
vm = (ROOT / "ui" / "viewmodel" / "report" / "StockDailyReportViewModel.kt").read_text(encoding="utf-8")
screen = (ROOT / "ui" / "screens" / "StockDailyReportScreen.kt").read_text(encoding="utf-8")
home = (ROOT / "ui" / "screens" / "HomeScreen.kt").read_text(encoding="utf-8")
# AI-APP-FIX-402：日期导航 UI 已收敛为公共组件 WmsDateNavRow（前后箭头/回到今天/禁用
# 后翻都在组件内实现），页面只负责接线（onPrev/onNext/nextEnabled/onResetToday）。
components = (ROOT / "ui" / "components" / "WmsComponents.kt").read_text(encoding="utf-8")

checks = []

def check(name, cond):
    checks.append((name, bool(cond)))

# T1 date 参数链路贯通
check("T1a ApiService.stockDailyReport 带 date Query 参数", '@Query("date") date: String? = null' in api)
check("T1b Repository.getStockDailyReport 带 date 形参并透传", "date: String? = null" in repo and "date = date?.takeIf" in repo)
check("T1c ViewModel 调用时传 date", "date = _uiState.value.date.takeIf" in vm)

# T2 日期导航状态机
check("T2a shiftDay 存在且钳制未来", "fun shiftDay(offset: Int)" in vm and "if (next > today) return" in vm)
check("T2b resetToday 恢复今天模式", "fun resetToday()" in vm and "dateIsToday = true" in vm)
check("T2c 今天模式跨天自动校正", "if (_uiState.value.dateIsToday)" in vm)

# T3 页面 UI（FIX-402 后：页面经 WmsDateNavRow 接线，箭头实体在组件内）
check("T3a 前一天/后一天箭头",
      "WmsDateNavRow(" in screen
      and "onPrev = { viewModel.shiftDay(-1) }" in screen
      and "onNext = { viewModel.shiftDay(1) }" in screen
      and "ChevronLeft" in components and "ChevronRight" in components)
check("T3b 回到今天按钮", "回到今天" in components and "viewModel.resetToday()" in screen)
check("T3c 到达今天禁用后翻",
      "nextEnabled = uiState.date <" in screen
      and "IconButton(onClick = onNext, enabled = nextEnabled)" in components)
check("T3d 历史日期数据截至显示（generatedAt 空时 --:--）", 'uiState.generatedAt ?: "--:--"' in screen)

# T4 空态与 >0 口径
check("T4 空态主文案为「该仓当天无结存物料」", "该仓当天无结存物料" in screen)

# T5 文案对齐
check("T5a 页头副标题「各物料每日结存 · 按仓展示」", "各物料每日结存 · 按仓展示" in screen)
check("T5b 首页卡片副标题「按仓展示 · 各物料每日结存」", "按仓展示 · 各物料每日结存" in home)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(("PASSED" if ok else "FAILED") + f"  {name}")
print(f"\n{len(checks) - len(failed)}/{len(checks)} PASSED")
if failed:
    print("FAILED:", ", ".join(failed))
    sys.exit(1)
