# -*- coding: utf-8 -*-
"""AI-MOB-STOCK-F01 静态契约（Android）：查库存增加「列表模式」。

背景：橙子库存通等主流库存 App 都支持「库存列表」——按仓库浏览 + 关键字筛选 +
滚动分页；本仓库原先手机端只能扫码/输码查单个物料，看不到某仓的整体物料库存。
后端 `GET /api/mobile/stock/query`（app/routes/native_api.py）早已存在且带分页，
但 Android 端从未消费，本任务只做 Android 接入，不改后端。

验收（对应台账 AI-MOB-STOCK-F01）：
- T1 API 契约：列表查询带 warehouse 必填 + keyword/page/page_size，与后端一致
- T2 Repository：经 safeCall 包装，不吞异常、不绕过统一错误映射
- T3 ViewModel：持有列表状态与分页元数据，未选仓库时拦截并给出提示
- T4 R1 分页：按 total_pages 翻页取全，不把默认 page_size 当业务上限
- T5 换仓清空：切换仓库必须重置列表，避免展示上一仓数据（跨仓数据隔离）
- T6 Screen：存在扫码/列表模式切换；列表区块含搜索栏与空态
- T7 扫码模式无回归：原扫码查单物料的搜索栏与逻辑仍在
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
API = ANDROID / "data/api/WmsApiService.kt"
REPO = ANDROID / "data/repository/WmsRepository.kt"
VM = ANDROID / "ui/viewmodel/scan/ScanViewModel.kt"
SCREEN = ANDROID / "ui/screens/ScanScreens.kt"
MODELS = ANDROID / "data/model/StockQueryModels.kt"
ROUTES = ROOT / "app/routes/native_api.py"


def test_t1_api_contract_matches_backend():
    api = API.read_text(encoding="utf-8")
    assert '@GET("api/mobile/stock/query")' in api, "必须声明列表查询端点"
    assert 'fun stockQuery(' in api
    assert '@Query("warehouse") warehouse: String' in api, "仓库必填（非可空）"
    assert '@Query("keyword")' in api
    assert '@Query("page") page: Int = 1' in api
    assert '@Query("page_size") pageSize: Int' in api

    # 后端确实存在该端点且仓库必填，避免前后端契约漂移
    routes = ROUTES.read_text(encoding="utf-8")
    assert "'/api/mobile/stock/query'" in routes
    assert "resolve_request_warehouse(request.args)" in routes


def test_t2_repository_uses_safe_call():
    repo = REPO.read_text(encoding="utf-8")
    idx = repo.index("queryStockPage")
    body = repo[idx:idx + 700]
    assert "api.stockQuery(" in body
    assert "safeCall" in body, "必须经 safeCall 统一错误映射，不裸调 API"


def test_t3_view_model_holds_list_state():
    vm = VM.read_text(encoding="utf-8")
    for field in (
        "val stockListItems: List<MaterialDto> = emptyList()",
        "val stockListLoading: Boolean = false",
        "val stockListLoadingMore: Boolean = false",
        "val stockListError: String? = null",
        "val stockListKeyword: String = \"\"",
        "val stockListPage: Int = 0",
        "val stockListTotalPages: Int = 0",
        "val stockListTotal: Int = 0",
        "val stockListLoaded: Boolean = false",
    ):
        assert field in vm, f"缺少列表状态字段：{field}"
    for fn in (
        "fun loadStockList(",
        "fun loadMoreStockList()",
        "fun onStockListKeywordChange(",
        "fun clearStockList()",
        "fun clearStockListError()",
    ):
        assert fn in vm, f"缺少列表方法：{fn}"


def test_t4_warehouse_required_and_intercepted():
    vm = VM.read_text(encoding="utf-8")
    idx = vm.index("fun loadStockList(")
    body = vm[idx:idx + 1200]
    # 未选仓库必须拦截并给提示，且不得发起请求
    assert "selectedWarehouse" in body
    assert "请先选择仓库" in body
    assert "stockListError" in body
    assert "return" in body or "return@" in body


def test_t5_pagination_follows_total_pages_r1():
    vm = VM.read_text(encoding="utf-8")
    idx = vm.index("fun loadMoreStockList()")
    body = vm[idx:idx + 900]
    # R1：翻页以服务端 total_pages 为准，而非拿默认 page_size 当上限
    assert "stockListTotalPages" in body
    assert "stockListPage + 1" in body or "nextPage" in body
    assert "STOCK_LIST_PAGE_SIZE" in vm
    # 重入保护：加载中不得重复触发
    assert "stockListLoadingMore" in body


def test_t6_switch_warehouse_resets_list():
    vm = VM.read_text(encoding="utf-8")
    idx = vm.index("fun selectWarehouse(")
    body = vm[idx:idx + 1500]
    # 跨仓数据隔离：换仓后不得残留上一仓结果
    assert "clearStockList" in body or "stockListItems = emptyList()" in body


def test_t7_screen_has_mode_switch_and_list_section():
    screen = SCREEN.read_text(encoding="utf-8")
    assert "var listMode by remember" in screen, "缺少扫码/列表模式状态"
    assert "扫码查物料" in screen and "库存列表" in screen, "缺少模式切换入口"
    assert "private fun StockListSection(" in screen, "缺少列表区块"
    assert "private fun StockListRow(" in screen, "缺少列表行"
    # 列表区块必须带关键字搜索与分页加载
    idx = screen.index("private fun StockListSection(")
    body = screen[idx:screen.index("private fun StockListRow(")]
    assert "onKeywordChange" in body and "onSubmit" in body
    assert "onLoadMore" in body
    assert "LazyColumn" in body, "列表必须用 LazyColumn 分页渲染"
    assert "WmsEmptyState" in body, "空态必须有明确文案，避免空白误导"


def test_t8_scan_mode_no_regression():
    screen = SCREEN.read_text(encoding="utf-8")
    # 原扫码模式核心逻辑保留（BUG-2026-09-10-002 精确编码未命中回退模糊）
    assert "queryMaterialByKeyword" in screen
    assert "showScannerDialog" in screen
    assert "Icons.Outlined.QrCodeScanner" in screen


def test_t9_models_parse_pagination_envelope():
    models = MODELS.read_text(encoding="utf-8")
    assert "data class StockQueryPageData" in models
    for field in ('"items"', '"total"', '"page"', '"page_size"', '"total_pages"'):
        assert f"@SerializedName({field})" in models, f"缺少分页字段映射 {field}"
