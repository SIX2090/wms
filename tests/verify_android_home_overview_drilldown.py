# -*- coding: utf-8 -*-
"""首页「今日概览」数据可下钻 —— 静态契约测试（AI-MOB-DRILLDOWN-01）。

需求背景（用户原话：「手机端 wms 系统现在有功能，你要做的是把功能做到精细化」）：
首页四个数字里，两个点了没反应、一个点了看不到想看的东西：

| 位置         | 改造前                                   | 问题                                     |
|--------------|------------------------------------------|------------------------------------------|
| 今日入库     | → 扫码入库页                             | 正常                                     |
| 今日出库     | → 扫码出库页                             | 正常                                     |
| 待处理单据   | screen = null                            | **点了完全没反应**                       |
| 库存告警     | → 查库存页（空白搜索框）                 | 看到数字但不知道**是哪些物料**           |

诊断发现的根因：后端 `app/routes/native_api.py` 早就提供
`/api/mobile/alert/list`、`/api/mobile/in_order/list`、`/api/mobile/out_order/list`
三个列表接口，**Android 端一个都没接**——12 个 `/api/mobile/*` 接口只用了 6 个。

本测试锁定的契约（任何一条被改坏都要红）：
1. DTO 字段与后端 payload 一一对应（`_in_order_payload` / `_out_order_payload` /
   alert list 的 items）——字段名写错会静默变成 null，界面上不报错只是空白。
2. 三条 Retrofit 声明存在，且**仓库参数走 `warehouse_id`**（首页存的是仓库 id，
   用 id 可规避同名仓库歧义）。
3. Repository 三个方法存在且走 `safeCall`（服务端业务提示不被"网络错误"覆盖）。
4. ViewModel 具备分页 / 状态筛选 / 防竞态 / 错误分级（首屏失败置 error、
   翻页失败不清空已有数据）。
5. **接线完整**：Screen 路由（带 wid/wname 查询参数）、NavGraph composable 注册、
   HomeScreen 两个入口不再是 null / StockQuery。
6. 路由参数必须从首页带出当前仓库——缺仓库时后端会回退服务端默认仓，
   与用户首页看到的口径不一致（首页默认落第一个真实仓）。
7. 版本递增 versionCode ≥ 13 / versionName ≥ 3.7.2。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "app" / "android-native-wms"
SRC = ANDROID / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
GRADLE = ANDROID / "app" / "build.gradle.kts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _p(rel: str) -> str:
    return _read(SRC / rel)


# A9:no-test=reason=下面各 test_ 函数即本契约测试本体，被测对象为 Android 源码文本


def _version_code(gradle: str) -> int:
    m = re.search(r"versionCode\s*=\s*(\d+)", gradle)
    assert m, "build.gradle.kts 未找到 versionCode"
    return int(m.group(1))


def _version_tuple(gradle: str) -> tuple:
    m = re.search(r'versionName\s*=\s*"([\d.]+)"', gradle)
    assert m, "build.gradle.kts 未找到 versionName"
    return tuple(int(x) for x in m.group(1).split("."))


# ── 1. 后端契约：字段名必须与 payload 一致 ──

def test_backend_endpoints_exist_and_require_warehouse():
    """三个列表接口都在，且都强制解析仓库（AGENTS.md 多仓隔离）。

    接口被删/被改成不需要仓库都会红：前者手机端直接 404，
    后者会让列表跨仓泄露数据。
    """
    src = _read(ROOT / "app" / "routes" / "native_api.py")

    for route in (
        "/api/mobile/alert/list",
        "/api/mobile/in_order/list",
        "/api/mobile/out_order/list",
    ):
        assert f"@app.route('{route}')" in src, f"后端缺少 {route}"

    # 三个接口各自都必须走 resolve_request_warehouse 并在失败时 400
    for func in ("mobile_api_alert_list", "mobile_api_in_order_list", "mobile_api_out_order_list"):
        m = re.search(rf"def {func}\(\):([\s\S]{{0,2500}})", src)
        assert m, f"未找到 {func}"
        body = m.group(1)
        assert "resolve_request_warehouse(request.args)" in body, f"{func} 未解析仓库"
        assert "if wh_err:" in body and "api_json_error(wh_err, 400)" in body, (
            f"{func} 仓库缺失时未返回 400"
        )


def test_backend_order_payload_field_names():
    """单据 payload 字段名锁定。

    DTO 与后端靠字段名对齐，不靠类型系统——后端改名而前端不改，
    Gson 会把字段静默填成 null，界面只是空白、日志里啥也看不到。
    """
    src = _read(ROOT / "app" / "app.py")

    m = re.search(r"def _in_order_payload\(order\):([\s\S]*?)\ndef ", src)
    assert m, "未找到 _in_order_payload"
    inbound = m.group(1)
    for field in ("order_no", "date", "business_type", "warehouse", "status",
                  "total_amount", "operator", "remark", "created_at", "item_count"):
        assert f"'{field}'" in inbound, f"入库单 payload 缺少 {field}"

    m = re.search(r"def _out_order_payload\(order\):([\s\S]*?)\ndef ", src)
    assert m, "未找到 _out_order_payload"
    outbound = m.group(1)
    for field in ("order_no", "date", "business_type", "warehouse", "department",
                  "status", "total_amount", "operator", "remark", "created_at", "item_count"):
        assert f"'{field}'" in outbound, f"出库单 payload 缺少 {field}"

    # 告警口径：<= 最低库存算告警（等于也算，是有意设计，不是 bug）
    alert = re.search(r"def mobile_api_alert_list\(\):([\s\S]*?)\n    @app\.route", src)
    assert alert is None or True  # 端点本身在 native_api.py，下面单独查
    na = _read(ROOT / "app" / "routes" / "native_api.py")
    assert "'gap': max(0, (m.min_stock or 0) - normalize_stock_quantity(quantities.get(m.id, 0)))" in na, (
        "告警缺口 gap 计算口径变了——手机端「缺 X」徽章会失真"
    )
    assert "normalize_stock_quantity(quantities.get(m.id, 0)) <= (m.min_stock or 0)" in na, (
        "告警判定改为 < 会与首页 alert_count 口径不一致（首页用 <=，等于最低库存也算告警）"
    )


# ── 2. DTO ──

def test_dto_field_names_match_backend():
    """DTO 的 @SerializedName 必须覆盖后端全部 snake_case 字段。"""
    src = _p("data/model/MobileListModels.kt")

    assert "data class AlertItemDto" in src
    assert "data class AlertListData" in src
    assert "data class MobileOrderDto" in src
    assert "data class MobileOrderListData" in src

    for sn in ('@SerializedName("min_stock")', '@SerializedName("reorder_point")',
               '@SerializedName("order_no")', '@SerializedName("business_type")',
               '@SerializedName("total_amount")', '@SerializedName("created_at")',
               '@SerializedName("item_count")', '@SerializedName("page_size")',
               '@SerializedName("total_pages")'):
        assert sn in src, f"MobileListModels 缺少 {sn}"

    # 出库单部门字段（后端 department 取部门名或客户名兜底）
    assert "val department: String?" in src, "缺少 department——出库单看不到领料部门"


# ── 3. API + Repository ──

def test_retrofit_declarations_use_warehouse_id():
    """三条 Retrofit 声明存在，仓库参数必须是 warehouse_id。"""
    src = _p("data/api/WmsApiService.kt")

    for path in ("api/mobile/alert/list", "api/mobile/in_order/list", "api/mobile/out_order/list"):
        assert f'@GET("{path}")' in src, f"缺少 Retrofit 声明 {path}"

    assert src.count('@Query("warehouse_id") warehouseId: String') >= 3, (
        "三条声明的仓库参数应为必填 String（非 String?），避免漏传时静默回退默认仓"
    )
    assert src.count('@Query("status") status: String? = null') >= 2, (
        "入库/出库单需要 status 筛选参数"
    )


def test_repository_methods_use_safe_call():
    """三个 Repository 方法都要走 safeCall（服务端业务提示不被覆盖为「网络错误」）。"""
    src = _p("data/repository/WmsRepository.kt")

    for fn in ("suspend fun getAlertList(", "suspend fun getInOrderList(", "suspend fun getOutOrderList("):
        assert fn in src, f"Repository 缺少 {fn}"

    for api_call in ("api.getAlertList(", "api.getInOrderList(", "api.getOutOrderList("):
        # 每个调用点前面必须是 safeCall {
        idx = src.index(api_call)
        window = src[max(0, idx - 120):idx]
        assert "safeCall" in window, f"{api_call} 未走 safeCall"

    # 空串状态要归一成 null，避免 ?status= 被后端当无效值
    assert 'status?.takeIf { it.isNotBlank() }' in src, "status 空串未归一为 null"


# ── 4. ViewModel ──

def test_viewmodel_supports_three_kinds_and_paging():
    """一个 ViewModel 承载三种列表，具备分页 / 筛选 / 防竞态 / 错误分级。"""
    src = _p("ui/viewmodel/list/OrderListViewModel.kt")

    assert "enum class ListKind" in src
    for kind in ("ALERT", "IN_ORDER", "OUT_ORDER"):
        assert kind in src, f"ListKind 缺少 {kind}"

    # 分页
    assert "fun loadMore()" in src
    assert "if (s.page >= s.totalPages) return" in src, "缺少翻页边界保护"
    assert "val nextPage = if (reset) 1 else s.page + 1" in src

    # 筛选
    assert "fun setStatusFilter(status: String?)" in src
    # 从首页「待处理单据」进来默认只看待处理
    assert 'statusFilter = if (kind == ListKind.ALERT) null else "pending"' in src, (
        "进入待处理单据列表应默认筛选 pending"
    )

    # 错误分级：翻页失败不清空已有数据
    assert "error = if (reset) (message ?: \"加载失败\") else _uiState.value.error" in src, (
        "翻页失败不应清空已有列表"
    )
    assert "isLoadingMore = !reset" in src

    # 缺仓库要显式报错，不能静默发请求
    assert 'error = "缺少仓库上下文"' in src


def test_viewmodel_start_is_idempotent():
    """同一 (kind, warehouseId) 重复 start 不重复请求（避免重组时抖动）。"""
    src = _p("ui/viewmodel/list/OrderListViewModel.kt")
    assert "if (s.kind == kind && s.warehouseId == warehouseId && !s.isFirstLoad) return" in src, (
        "start 幂等保护缺失——页面重组会反复打接口"
    )


# ── 5. 接线完整性（本文件最核心的断言）──

def test_screen_routes_carry_warehouse_params():
    """两条下钻路由必须带 wid / wname 查询参数。"""
    src = _p("ui/navigation/Screen.kt")

    assert 'data object OverviewOrders : Screen("overview_orders?wid={wid}&wname={wname}"' in src, (
        "待处理单据路由缺少仓库参数——后端会回退默认仓，与首页口径不一致"
    )
    assert 'data object OverviewAlerts : Screen("overview_alerts?wid={wid}&wname={wname}"' in src, (
        "库存告警路由缺少仓库参数"
    )


def test_home_screen_wires_both_entries():
    """首页两个入口必须真的指向下钻页（这是用户报的原始问题）。"""
    src = _p("ui/screens/HomeScreen.kt")

    # 「待处理单据」此前是 screen = null
    assert "screen = Screen.OverviewOrders" in src, "待处理单据仍未接线（点了没反应）"
    assert "screen = Screen.OverviewAlerts" in src, "库存告警未指向告警明细"

    # 「库存告警」不应再跳查库存的空白搜索框
    overview_block = src[src.index("private? fun TodayOverviewBar".replace("private? ", "")):]
    overview_block = overview_block[:overview_block.index("private data class OverviewItem")]
    assert "screen = Screen.StockQuery" not in overview_block, (
        "库存告警仍跳查库存——用户看到数字却不知道是哪些物料"
    )
    assert "screen = null" not in overview_block, (
        "概览条仍存在不可点击项"
    )


def test_navgraph_registers_destinations_with_repo_context():
    """NavGraph 注册两个 composable，并把首页仓库通过路由参数传下去。"""
    src = _p("ui/navigation/NavGraph.kt")

    assert "Screen.OverviewAlerts.route," in src, "未注册告警下钻目的地"
    assert "Screen.OverviewOrders.route," in src, "未注册单据下钻目的地"
    assert "OverviewListScreen(" in src
    assert "OverviewTarget.ALERT" in src and "OverviewTarget.PENDING_ORDERS" in src

    # 参数声明
    assert 'navArgument("wid")' in src and 'navArgument("wname")' in src, (
        "下钻目的地未声明 wid/wname 参数"
    )
    assert 'type = NavType.StringType' in src

    # 从首页带出当前仓库
    assert "Screen.OverviewOrders, Screen.OverviewAlerts ->" in src, (
        "首页跳转未区分下钻路由——不会拼仓库参数"
    )
    assert "homeViewModel.uiState.value.selectedWarehouseId" in src, (
        "未把首页当前仓库 id 传下去"
    )

    # 拼接前必须转义（仓库名可能含 / ? 空格 中文）
    assert "encodeQueryValue(" in src, "路由参数未转义——仓库名含 / 或 ? 会拼坏路由"
    assert 'replace("{wid}"' in src and 'replace("{wname}"' in src

    # 单个 ViewModel 实例复用（两个入口共用一个 key）
    assert 'viewModel(key = "overview_list")' in src, (
        "下钻 ViewModel 未用稳定 key——两个入口会各拿一份状态"
    )


def test_drilldown_screen_reads_target_and_warehouse():
    """下钻页要按 target 初始化，且仓库为空时不发请求。"""
    src = _p("ui/screens/OverviewListScreen.kt")

    assert "enum class OverviewTarget { ALERT, PENDING_ORDERS }" in src
    assert "fun OverviewListScreen(" in src
    assert "warehouseId: String," in src and "warehouseName: String," in src

    # 仓库为空不该发请求
    assert "if (warehouseId.isNotBlank())" in src, "仓库为空时仍会发请求"

    # 待处理单据页提供 入库单/出库单 切换 + 状态筛选
    assert "ListKind.IN_ORDER to \"入库单\"" in src
    assert "ListKind.OUT_ORDER to \"出库单\"" in src
    assert '"pending" to "待处理"' in src

    # 滑到底自动翻页
    assert "shouldLoadMore" in src and "onLoadMore()" in src

    # 空态提示（告警页要说明"本仓"口径）
    assert "本仓暂无库存告警" in src


def test_drilldown_screen_uses_shared_empty_state_and_header():
    """复用项目统一组件，避免各页自造一套视觉。"""
    src = _p("ui/screens/OverviewListScreen.kt")
    assert "WmsEmptyState(" in src
    assert "WmsGradientHeader(" in src


def test_version_bumped():
    """版本递增：versionCode ≥ 13 / versionName ≥ 3.7.2。"""
    gradle = _read(GRADLE)
    assert _version_code(gradle) >= 13
    assert _version_tuple(gradle) >= (3, 7, 2)
