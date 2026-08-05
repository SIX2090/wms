package com.factory.wms.ui.navigation

sealed class Screen(val route: String) {
    data object Login : Screen("login")
    data object Home : Screen("home")
    data object Inbound : Screen("inbound")
    data object Outbound : Screen("outbound")
    data object StockQuery : Screen("stock_query")
    data object Stocktake : Screen("stocktake")
    data object OpeningStock : Screen("opening_stock")
    data object DocumentOcr : Screen("document_ocr")
    data object ObjectRecognize : Screen("object_recognize")
}