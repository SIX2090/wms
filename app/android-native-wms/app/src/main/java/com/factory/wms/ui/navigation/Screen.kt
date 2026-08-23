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
    data object Profile : Screen("profile", "我的")
}