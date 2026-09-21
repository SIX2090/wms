# -*- coding: utf-8 -*-
"""AI-MOB-LDG-F01 回归闸门：手机端库存台账页源码锚点。

库存台账页（按单一物料查看期初/入/出/结存流水链，只读）由以下链路组成，
任一环节被改没，功能即静默消失（沙箱无 Android SDK，编译证据在 CI
`Android APK Build`，本测试是源码级第一道闸门）：

  后端 GET /api/mobile/report/stock_ledger
    → WmsApiService.stockLedgerReport（@GET 声明 + material_code 必传）
    → WmsRepository.getStockLedgerReport（ensureSession + safeCall）
    → StockLedgerReportViewModel（物料/仓库双必填才查询、init 不自动加载、
      loadMore 分页守卫）
    → StockLedgerReportScreen（物料选择引导空态、汇总卡、分页列表）
    → Screen.StockLedgerReport 路由声明 → NavGraph composable（路由内惰性
      viewModel()，BUG-2026-09-14-032 教训）→ HomeScreen 功能卡入口。

纯静态源码断言（无 app context，符合 A12/R7），外加括号平衡兜底。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANDROID = os.path.join(REPO, 'app', 'android-native-wms')
MAIN = os.path.join(ANDROID, 'app', 'src', 'main', 'java', 'com', 'factory', 'wms')
TEST = os.path.join(ANDROID, 'app', 'src', 'test', 'java', 'com', 'factory', 'wms')

MODELS = os.path.join(MAIN, 'data', 'model', 'StockLedgerReportModels.kt')
API = os.path.join(MAIN, 'data', 'api', 'WmsApiService.kt')
REPO_KT = os.path.join(MAIN, 'data', 'repository', 'WmsRepository.kt')
VM = os.path.join(MAIN, 'ui', 'viewmodel', 'report', 'StockLedgerReportViewModel.kt')
SCREEN = os.path.join(MAIN, 'ui', 'screens', 'StockLedgerReportScreen.kt')
NAV_SCREEN = os.path.join(MAIN, 'ui', 'navigation', 'Screen.kt')
NAV_GRAPH = os.path.join(MAIN, 'ui', 'navigation', 'NavGraph.kt')
HOME = os.path.join(MAIN, 'ui', 'screens', 'HomeScreen.kt')
JVM_TEST = os.path.join(TEST, 'StockLedgerRangeLogicTest.kt')
GRADLE = os.path.join(ANDROID, 'app', 'build.gradle.kts')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _strip_comments(text):
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//.*$', '', text, flags=re.M)
    return text


def _brace_balance(text):
    depth = 0
    cleaned = re.sub(r'""".*?"""', '', text, flags=re.S)
    cleaned = re.sub(r"'''.*?'''", '', cleaned, flags=re.S)
    for line in cleaned.splitlines():
        line = re.sub(r'//.*$', '', line)
        line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
        depth += line.count('(') - line.count(')')
    return depth


def test_T1_models_shape_and_nullable_fields():
    src = _strip_comments(_read(MODELS))
    for cls in ('StockLedgerReportData', 'StockLedgerWarehouse',
                'StockLedgerMaterial', 'StockLedgerSummary', 'StockLedgerItem'):
        assert f'data class {cls}' in src, f'{cls} 缺失'
    for field in ('"summary"', '"items"', '"total"', '"page"',
                  '"page_size"', '"total_pages"', '"opening_balance"',
                  '"total_in_quantity"', '"total_out_quantity"',
                  '"ending_balance"', '"balance_quantity"',
                  '"in_quantity"', '"out_quantity"', '"warehouse_stock"'):
        assert f'@SerializedName({field})' in src, f'字段 {field} 缺失'
    # BUG-2026-08-24-007：可空字段必须 `?= null`（Gson Unsafe 防 NPE）
    assert 'val warehouseStock: Double? = null' in src
    assert 'val truncated: Boolean? = null' in src


def test_T2_api_service_endpoint_declared():
    src = _strip_comments(_read(API))
    assert '@GET("api/mobile/report/stock_ledger")' in src
    m = re.search(r'suspend fun stockLedgerReport\((.*?)\): Response', src, re.S)
    assert m, 'stockLedgerReport 方法缺失'
    params = m.group(1)
    assert '@Query("warehouse_id")' in params
    assert '@Query("material_code")' in params, '物料编码必传参数缺失'
    assert '@Query("start_date")' in params and '@Query("end_date")' in params
    assert 'Response<ApiEnvelope<StockLedgerReportData>>' in src


def test_T3_repository_wrapper():
    src = _strip_comments(_read(REPO_KT))
    m = re.search(r'suspend fun getStockLedgerReport\(', src)
    assert m, 'getStockLedgerReport 缺失'
    body = src[m.start():m.start() + 900]
    assert 'ensureSession()' in body
    assert 'safeCall' in body
    assert 'api.stockLedgerReport(' in body
    # 空串转 null（不发给服务端）
    assert 'takeIf { it.isNotBlank() }' in body


def test_T4_viewmodel_query_guards():
    src = _strip_comments(_read(VM))
    # init 不自动加载（BUG-2026-08-24-006：启动组合期可能未登录）
    init_m = re.search(r'init \{(.*?)\n    \}', src, re.S)
    assert init_m, 'init 块缺失'
    assert 'refresh()' not in init_m.group(1), 'init 不得自动加载'
    assert 'loadWarehouses()' not in init_m.group(1), 'init 不得自动加载'
    # 查询双必填：仓库 + 物料（缺一不发请求）
    assert re.search(r'val warehouseId = s\.selectedWarehouseId \?: return', src)
    assert re.search(r'val material = s\.selectedMaterial \?: return', src)
    # loadMore 分页守卫
    assert 'if (s.isLoading || s.isLoadingMore || !pager.hasMore || !s.queried) return' in src
    # 复用既有分页状态机
    assert 'StockDailyPager()' in src
    # 日期范围纯逻辑抽出（JVM 可测）
    assert 'object StockLedgerRangeLogic' in src
    assert 'fun reconciles(' in src


def test_T5_screen_guide_and_components():
    src = _strip_comments(_read(SCREEN))
    assert 'fun StockLedgerReportScreen(' in src
    # 物料未选引导空态（单一物料口径）
    assert '请先选择物料' in src
    assert 'WarehouseSelector(' in src
    assert 'WmsEmptyState(' in src
    # 汇总四格：期初/入/出/期末
    for label in ('"期初"', '"入库"', '"出库"', '"期末结存"'):
        assert label in src, f'汇总格 {label} 缺失'
    # 截断告警透传
    assert 'uiState.truncated' in src
    # 物料搜索对话框走 ViewModel（不直连 API）
    assert 'viewModel.searchMaterials()' in src
    assert 'viewModel.selectMaterial(candidate)' in src


def test_T6_navigation_registered_with_lazy_viewmodel():
    nav = _strip_comments(_read(NAV_SCREEN))
    assert 'data object StockLedgerReport : Screen("stock_ledger_report", "库存台账")' in nav
    graph = _strip_comments(_read(NAV_GRAPH))
    m = re.search(r'composable\(Screen\.StockLedgerReport\.route\) \{(.*?)\n                \}', graph, re.S)
    assert m, 'NavGraph 未注册 StockLedgerReport 路由'
    # 路由内惰性创建（BUG-2026-09-14-032：不得在 NavGraph 顶层饿汉）
    assert 'viewModel()' in m.group(1)
    assert 'import com.factory.wms.ui.viewmodel.report.StockLedgerReportViewModel' in _read(NAV_GRAPH)


def test_T7_home_entry_card():
    src = _strip_comments(_read(HOME))
    m = re.search(r'FunctionCard\(\s*title = "库存台账"', src)
    assert m, '首页缺「库存台账」功能卡'
    window = src[m.start():m.start() + 400]
    assert 'Screen.StockLedgerReport' in window


def test_T8_version_bumped():
    src = _read(GRADLE)
    assert 'versionCode = 26' in src, 'versionCode 未递增（无法覆盖安装，BUG-2026-09-14-027）'
    assert 'versionName = "3.9.2"' in src
    assert 'AI-MOB-LDG-F01' in src, '版本 changelog 注释缺失'


def test_T9_jvm_test_exists():
    src = _read(JVM_TEST)
    assert 'class StockLedgerRangeLogicTest' in src
    assert 'reconciles' in src


def test_T10_brace_balance():
    for path in (MODELS, API, REPO_KT, VM, SCREEN, NAV_SCREEN, NAV_GRAPH, HOME, JVM_TEST):
        assert _brace_balance(_read(path)) == 0, f'{os.path.basename(path)} 括号不平衡'
