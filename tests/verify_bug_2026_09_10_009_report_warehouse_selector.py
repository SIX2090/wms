# -*- coding: utf-8 -*-
"""BUG-2026-09-10-009 回归（Android 静态契约）：日报可切换仓库 / 看全部仓库。

背景：用户有 4 个以上在用仓库，手机每日报表请求不带仓库参数，服务端一律回退
系统默认仓，录在其他仓的单据在日报里完全看不到——「今天的记录查不到」的直接原因。

配套改动（后端见 test_bug_2026_09_10_009_daily_report_warehouse_scope.py）：
- WmsApiService.dailyReportDetail 增加 warehouse_id（仓 id 或 "all"）
- WmsRepository.getDailyReport 透传 warehouseId（含逐页翻页，R1）
- ReportViewModel：warehouses / selectedWarehouseId / loadWarehouses / selectWarehouse
- ReportScreens：顶部 WarehouseSelector（默认仓库 / 各仓 / 全部仓库汇总）
- DailyReportItem 增加可空 warehouse（全部仓库模式逐行显示来源仓）

验收：
- T1 API 必须带 warehouse_id 查询参数
- T2 Repository 签名带 warehouseId 且首屏与翻页都透传
- T3 ViewModel 必须持有 warehouses / selectedWarehouseId 并提供切换与加载
- T4 页面必须调用 WarehouseSelector 且提供「全部仓库」选项
- T5 明细行 warehouse 字段必须可空（旧版后端不下发，Gson 置 null）
- T6 加载顺序：进入页面先拉仓库列表再查报表
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
API = ANDROID / "data/api/WmsApiService.kt"
REPO = ANDROID / "data/repository/WmsRepository.kt"
VM = ANDROID / "ui/viewmodel/report/ReportViewModel.kt"
SCREEN = ANDROID / "ui/screens/ReportScreens.kt"
MODELS = ANDROID / "data/model/ReportModels.kt"


def test_t1_api_has_warehouse_param():
    src = API.read_text(encoding="utf-8")
    assert '@Query("warehouse_id")' in src, "dailyReportDetail 必须支持 warehouse_id"


def test_t2_repository_passes_warehouse_on_every_page():
    src = REPO.read_text(encoding="utf-8")
    body = src[src.index("suspend fun getDailyReport("):]
    body = body[:body.index("\n    suspend fun getOpeningStock")]
    assert "warehouseId: String? = null" in body, "getDailyReport 必须接受 warehouseId"
    # R1：逐页拉取时也必须带上，否则第 2 页起会退回默认仓
    assert body.count("api.dailyReportDetail(") == 2
    assert body.count("api.dailyReportDetail(type, date, warehouseId") == 2


def test_t3_view_model_holds_warehouse_state():
    src = VM.read_text(encoding="utf-8")
    assert "val warehouses: List<WarehouseDto> = emptyList()" in src
    assert "val selectedWarehouseId: String? = null" in src
    assert "fun loadWarehouses()" in src
    assert "fun selectWarehouse(warehouseId: String?)" in src
    assert "state.selectedWarehouseId" in src, "load() 必须把选中仓传给 repository"


def test_t4_screen_has_selector_with_all_option():
    src = SCREEN.read_text(encoding="utf-8")
    assert "WarehouseSelector(" in src
    assert 'onSelect("all")' in src, "必须提供「全部仓库（汇总）」选项"
    assert "onSelect(null)" in src, "必须保留「默认仓库」选项（兼容旧行为）"


def test_t5_item_warehouse_nullable():
    src = MODELS.read_text(encoding="utf-8")
    assert '@SerializedName("warehouse") val warehouse: String? = null' in src


def test_t6_loads_warehouses_before_report():
    src = SCREEN.read_text(encoding="utf-8")
    block = src[src.index("LaunchedEffect(Unit) {"):]
    block = block[:block.index("LaunchedEffect(uiState.error)")]
    assert block.index("loadWarehouses()") < block.index("viewModel.load()")
