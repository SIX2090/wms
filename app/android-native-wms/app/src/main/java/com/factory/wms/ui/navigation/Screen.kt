package com.factory.wms.ui.navigation

sealed class Screen(val route: String, val title: String) {
    data object Login : Screen("login", "登录")
    data object Home : Screen("home", "首页")
    data object Inbound : Screen("inbound", "扫码入库")
    data object Outbound : Screen("outbound", "扫码出库")
    data object StockQuery : Screen("stock_query", "查库存")
    data object Stocktake : Screen("stocktake", "扫码盘点")
    data object OpeningStock : Screen("opening_stock", "期初库存")
    data object DocumentOcr : Screen("document_ocr", "识别单据")
    data object ObjectRecognize : Screen("object_recognize", "识物")
    data object StocktakeRecognize : Screen("stocktake_recognize", "识物盘点")
    data object MaterialArchive : Screen("material_archive", "物料档案")
    data object MaterialArchiveDetail : Screen("material_archive_detail", "物料档案图片")
    data object DailyReport : Screen("daily_report", "每日报表")
    data object StocktakeRecord : Screen("stocktake_record", "盘点记录")
    data object Profile : Screen("profile", "我的")

    /**
     * 首页概览「待处理单据」下钻（AI-MOB-DRILLDOWN-01）。
     *
     * 路由带两个查询参数：`wid` 仓库 id（后端 resolve_request_warehouse 要它做
     * 多仓隔离）与 `wname` 仓库名（标题展示用，非 id 时不传也可）。
     * 仓库必须从首页带过来——列表接口在缺仓库时会回退到服务端默认仓，
     * 与用户在首页看到的口径不一致（首页默认落第一个真实仓，
     * 见 HomeViewModel.loadWarehouses）。
     */
    data object OverviewOrders : Screen("overview_orders?wid={wid}&wname={wname}", "待处理单据")

    /** 首页概览「库存告警」下钻（AI-MOB-DRILLDOWN-01）。参数语义同 [OverviewOrders]。 */
    data object OverviewAlerts : Screen("overview_alerts?wid={wid}&wname={wname}", "库存告警")
}