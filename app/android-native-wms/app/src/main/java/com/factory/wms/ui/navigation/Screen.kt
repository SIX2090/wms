package com.factory.wms.ui.navigation

sealed class Screen(val route: String, val title: String) {
    /**
     * 注意：**[title] 是业务动作名，不写"扫码"**（BUG-2026-09-18-007）。
     *
     * 扫码只是录入手式之一：入库/出库页还有「手动添加」与语音建单，盘点页还有
     * 「识物盘点」。标题写"扫码出库"，用户从手工添加进去就会怀疑进错页面；
     * 且底部 Tab 早已是「入库 / 出库」，两套口径并存。故统一为动作名，
     * "扫码"只出现在按钮文案与副标题里。route 字符串与 title 解耦，不受影响。
     */
    data object Login : Screen("login", "登录")
    data object Home : Screen("home", "首页")
    data object Inbound : Screen("inbound", "入库")
    data object Outbound : Screen("outbound", "出库")
    data object StockQuery : Screen("stock_query", "查库存")
    data object Stocktake : Screen("stocktake", "盘点")
    data object OpeningStock : Screen("opening_stock", "期初库存")
    data object DocumentOcr : Screen("document_ocr", "识别单据")
    data object ObjectRecognize : Screen("object_recognize", "识物")
    data object StocktakeRecognize : Screen("stocktake_recognize", "识物盘点")
    data object MaterialArchive : Screen("material_archive", "物料档案")
    data object MaterialArchiveDetail : Screen("material_archive_detail", "物料档案图片")
    data object DailyReport : Screen("daily_report", "每日报表")
    data object StockDailyReport : Screen("stock_daily_report", "库存日报")
    data object InOutDetailReport : Screen("in_out_detail_report", "出入库明细")
    data object StockLedgerReport : Screen("stock_ledger_report", "库存台账")
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