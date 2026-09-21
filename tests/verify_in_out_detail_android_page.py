#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-MOB-RPT-F01 收尾：安卓端「出入库明细消费页」静态验证。

本地无 Android SDK（与台账约定一致：Android 改动由 CI assembleRelease/testReleaseUnitTest
校验），本脚本对源码做特征断言：
  T1 接口链路：WmsApiService / WmsRepository / ViewModel 三处 in_out_detail 贯通，
     仓库必填参数 warehouse_id 必传（AGENTS.md §二）；
  T2 数据模型与端点契约一致（summary 三字段 / 分页元数据 / 可空字段判空声明）；
  T3 ViewModel 状态机：仓库未选不发请求、翻页守卫、日期钳制、resetToday；
  T4 页面 UI：仓库选择（无"全部仓库"）、方向 chips、日期范围导航钳制、汇总卡、
     空态文案、滚动翻页 footer；
  T5 接线：Screen 路由注册、NavGraph composable、首页入口卡；
  T6 版本号纪律（BUG-2026-09-14-027）：versionCode 25 / versionName 3.9.1；
  T7 纯逻辑单测文件存在且覆盖钳制用例。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app" / "android-native-wms" / "app" / "src"
MAIN = ROOT / "main" / "java" / "com" / "factory" / "wms"
TEST = ROOT / "test" / "java" / "com" / "factory" / "wms"

api = (MAIN / "data" / "api" / "WmsApiService.kt").read_text(encoding="utf-8")
repo = (MAIN / "data" / "repository" / "WmsRepository.kt").read_text(encoding="utf-8")
models = (MAIN / "data" / "model" / "InOutDetailReportModels.kt").read_text(encoding="utf-8")
vm = (MAIN / "ui" / "viewmodel" / "report" / "InOutDetailReportViewModel.kt").read_text(encoding="utf-8")
screen = (MAIN / "ui" / "screens" / "InOutDetailReportScreen.kt").read_text(encoding="utf-8")
home = (MAIN / "ui" / "screens" / "HomeScreen.kt").read_text(encoding="utf-8")
routes = (MAIN / "ui" / "navigation" / "Screen.kt").read_text(encoding="utf-8")
nav = (MAIN / "ui" / "navigation" / "NavGraph.kt").read_text(encoding="utf-8")
gradle = (ROOT.parent / "build.gradle.kts").read_text(encoding="utf-8")
unit_test = (TEST / "InOutDetailDateLogicTest.kt").read_text(encoding="utf-8")

checks = []

def check(name, cond):
    checks.append((name, bool(cond)))

# T1 接口链路贯通 + 仓库必填
check("T1a ApiService.inOutDetailReport 指向 in_out_detail 端点",
      '@GET("api/mobile/report/in_out_detail")' in api and "suspend fun inOutDetailReport(" in api)
check("T1b warehouse_id 为必传 Query（无默认值）",
      '@Query("warehouse_id") warehouseId: String' in api)
check("T1c Repository.getInOutDetailReport 透传日期/方向/分页",
      "suspend fun getInOutDetailReport(" in repo
      and "api.inOutDetailReport(" in repo
      and "startDate = startDate?.takeIf" in repo
      and "pageSize = pageSize" in repo)
check("T1d ViewModel 经 repository 拉取并带方向/关键字",
      "repository.getInOutDetailReport(" in vm
      and "direction = s.direction.apiValue" in vm
      and "keyword = s.keyword" in vm)

# T2 模型契约
check("T2a summary 三字段（笔数/入库合计/出库合计）",
      "total_count" in models and "total_in_quantity" in models and "total_out_quantity" in models)
check("T2b 分页元数据四字段",
      '"total") val total: Int' in models and '"total_pages") val totalPages: Int' in models)
check("T2c 可空字段可空声明（BUG-2026-08-24-007 防 NPE）",
      "val spec: String? = null" in models and "val operator: String? = null" in models
      and "val location: String? = null" in models)
check("T2d direction 字段（in/out/zero 着色用）", '"direction") val direction: String? = null' in models)

# T3 ViewModel 状态机
check("T3a 仓库未选不发请求（仓库必填）",
      "val warehouseId = _uiState.value.selectedWarehouseId ?: return" in vm)
check("T3b loadMore 守卫（加载中/无更多/未查询不拉）",
      "if (s.isLoading || s.isLoadingMore || !pager.hasMore || !s.queried) return" in vm)
check("T3c 开始日期钳制不越过结束日期", "fun shiftStart(start: String, end: String" in vm
      and "return if (next > end) end else next" in vm)
check("T3d 结束日期钳制上限今天、下限开始日期",
      "if (next > todayStr) next = todayStr" in vm and "if (next < start) next = start" in vm)
check("T3e resetToday 恢复只看今天", "fun resetToday()" in vm)
check("T3f 默认选中第一个真实仓并立即查询（与库存日报同模式）",
      "list.first().id?.toString()" in vm and "if (nextSelected != current) refresh()" in vm)

# T4 页面 UI
check("T4a 仓库选择无「全部仓库」（只列真实仓）",
      "showDefaultWarehouse = false" in screen and "allowAll = false" in screen)
check("T4b 方向三 chips（全部/入库/出库）",
      "InOutDirection.values().forEach" in screen and "FilterChip(" in screen)
check("T4c 开始后翻禁越结束、结束后翻禁越今天",
      "nextEnabled = uiState.startDate < uiState.endDate" in screen
      and "nextEnabled = uiState.endDate < todayStr" in screen)
check("T4d 汇总卡三格（笔数/入库合计/出库合计）",
      'InOutSummaryCell("笔数"' in screen and 'InOutSummaryCell("入库合计"' in screen
      and 'InOutSummaryCell("出库合计"' in screen)
check("T4e 空态区分过滤/无流水两种文案",
      "该范围内无出入库流水" in screen and "未找到匹配流水" in screen)
check("T4f 数量带符号着色（出库 -红 / 入库 +绿）",
      'if (isOut) "-" else "+"' in screen and "if (isOut) Error else Success" in screen)
check("T4g 滚动到底自动翻页 + 已加载全部 footer",
      "shouldLoadMore" in screen and "已加载全部" in screen)
check("T4h spec 判空展示（BUG-2026-08-24-007）", "if (!item.spec.isNullOrBlank())" in screen)

# T5 接线
check("T5a Screen 路由注册 in_out_detail_report",
      'data object InOutDetailReport : Screen("in_out_detail_report", "出入库明细")' in routes)
check("T5b NavGraph composable 接线 + ViewModel import",
      "composable(Screen.InOutDetailReport.route)" in nav
      and "import com.factory.wms.ui.viewmodel.report.InOutDetailReportViewModel" in nav)
check("T5c 首页入口卡（出入库明细 · 日期范围按仓流水）",
      '"出入库明细"' in home and "Screen.InOutDetailReport" in home)

# T6 版本号纪律（BUG-2026-09-14-027）
# 原断言把 versionCode/versionName 钉死在 25/3.9.1（F01 发版时的版本号），
# 后续任何合法版本递增都会把它打破——本断言的意图是「发版必递增 + changelog
# 可溯」，而不是「版本永远是 25」（同 BUG-2026-09-18-011 修 -009 硬编码文案
# 的教训：测试不应阻止合法改动）。改为校验纪律本身。
import re as _re
_vc = _re.search(r'versionCode\s*=\s*(\d+)', gradle)
check("T6 版本号纪律：versionCode>=25 且 changelog 记录 AI-MOB-RPT-F01",
      _vc is not None and int(_vc.group(1)) >= 25 and 'AI-MOB-RPT-F01' in gradle)

# T7 纯逻辑单测
check("T7 InOutDetailDateLogicTest 覆盖钳制用例",
      "shiftStart clamps to end date" in unit_test and "shiftEnd clamps to today" in unit_test
      and "crosses month and year boundary" in unit_test)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(("PASSED" if ok else "FAILED") + f"  {name}")
print(f"\n{len(checks) - len(failed)}/{len(checks)} PASSED")
if failed:
    print("FAILED:", ", ".join(failed))
    sys.exit(1)
