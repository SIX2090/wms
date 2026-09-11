# -*- coding: utf-8 -*-
"""BUG-2026-09-10-010 回归（Android 静态契约）：首页概览可切换仓库 / 看全部仓库。

背景：与 BUG-2026-09-10-009（日报跨仓）同根因。首页 `getDashboard()` 不带仓库
参数，服务端一律回退系统默认仓，4 仓以上用户首页「今日入库/出库」只反映默认仓。

配套改动（后端见 test_bug_2026_09_10_010_dashboard_warehouse_scope.py）：
- WmsApiService.getDashboard 增加 warehouse_id（仓 id 或 "all"）
- WmsRepository.getDashboard 透传 warehouseId，并改用 safeCall 收口错误
- HomeViewModel：warehouses / selectedWarehouseId / loadWarehouses / selectWarehouse
- HomeScreen：概览条标题行加 WarehouseSelector（与报表页共用组件）
- ui/components/WarehouseSelector.kt：从报表页提取为共享组件，避免两处漂移

验收：
- T1 API 必须带 warehouse_id 查询参数
- T2 Repository 签名带 warehouseId 并透传
- T3 ViewModel 持有 warehouses / selectedWarehouseId 并提供加载与切换
- T4 页面调用共享 WarehouseSelector；首页下拉关闭「默认仓库」与「全部仓库（汇总）」选项
- T5 共享组件存在且报表页也改用它（不再各写一份）
- T6 DashboardDto 新增 warehouse 字段（服务端回传当前口径）
- T7 进入首页先加载仓库列表再查概览
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
API = ANDROID / "data/api/WmsApiService.kt"
REPO = ANDROID / "data/repository/WmsRepository.kt"
VM = ANDROID / "ui/viewmodel/home/HomeViewModel.kt"
SCREEN = ANDROID / "ui/screens/HomeScreen.kt"
SHARED = ANDROID / "ui/components/WarehouseSelector.kt"
REPORT_SCREEN = ANDROID / "ui/screens/ReportScreens.kt"
MODEL = ANDROID / "data/model/DashboardModels.kt"


def test_t1_api_has_warehouse_param():
    src = API.read_text(encoding="utf-8")
    body = src[src.index("suspend fun getDashboard("):]
    body = body[:body.index("Response<ApiEnvelope<DashboardDto>>")]
    assert '@Query("warehouse_id")' in body, "getDashboard 必须支持 warehouse_id"


def test_t2_repository_passes_warehouse():
    src = REPO.read_text(encoding="utf-8")
    body = src[src.index("suspend fun getDashboard("):]
    body = body[:body.index("\n    // ── 物料档案")]
    assert "warehouseId: String? = null" in body, "getDashboard 必须接受 warehouseId"
    assert "api.getDashboard(warehouseId)" in body, "必须把 warehouseId 透传给 API"


def test_t3_view_model_holds_warehouse_state():
    src = VM.read_text(encoding="utf-8")
    assert "val warehouses: List<WarehouseDto> = emptyList()" in src
    assert "val selectedWarehouseId: String? = null" in src
    assert "fun loadWarehouses()" in src
    assert "fun selectWarehouse(warehouseId: String?)" in src
    # 切换仓库后必须重新拉取概览
    body = src[src.index("fun selectWarehouse("):]
    assert "loadDashboard()" in body, "切换仓库后需重新加载概览"


def test_t4_screen_uses_warehouse_selector():
    src = SCREEN.read_text(encoding="utf-8")
    assert "WarehouseSelector(" in src, "首页必须提供仓库切换"
    assert "homeViewModel.selectWarehouse" in src
    assert "dashboard.warehouse" in src, "当前口径标签应取服务端回传的 warehouse"
    # 用户需求：首页下拉只列真实仓库，关闭「默认仓库」与「全部仓库（汇总）」
    assert "showDefaultWarehouse = false" in src, "首页下拉必须关闭「默认仓库」选项"
    assert "allowAll = false" in src, "首页下拉必须关闭「全部仓库（汇总）」选项"


def test_t5_shared_component_and_report_reuses_it():
    assert SHARED.exists(), "应存在共享组件 ui/components/WarehouseSelector.kt"
    shared = SHARED.read_text(encoding="utf-8")
    assert "fun WarehouseSelector(" in shared
    assert '"全部仓库（汇总）"' in shared, "共享组件必须提供全部仓库汇总选项"
    assert "allowAll" in shared

    report = REPORT_SCREEN.read_text(encoding="utf-8")
    assert "WarehouseSelector(" in report, "报表页应改用共享组件"
    assert "private fun WarehouseSelector(" not in report, "报表页不应再保留私有副本"


def test_t6_dashboard_dto_has_warehouse():
    src = MODEL.read_text(encoding="utf-8")
    assert "val warehouse: String? = null" in src
    assert "all_warehouses" in src


def test_t7_home_loads_warehouses_on_enter():
    src = SCREEN.read_text(encoding="utf-8")
    assert "homeViewModel.loadWarehouses()" in src, "进入首页需加载仓库列表"
    # 加载应先于/伴随概览查询，且不阻塞默认仓展示
    assert "LaunchedEffect(Unit)" in src
