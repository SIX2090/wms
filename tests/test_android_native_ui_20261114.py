"""Consumer wiring contracts; real measurement and interaction run in Android unit tests."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"


def read(relative):
    return (SRC / relative).read_text(encoding="utf-8")


def function(source, name):
    start = source.index("fun " + name + "(")
    # Default callback lambdas belong to the signature, not the function body.
    paren = source.index("(", start)
    depth = 0
    for end in range(paren, len(source)):
        depth += (source[end] == "(") - (source[end] == ")")
        if depth == 0:
            break
    brace = source.index("{", end)
    depth = 0
    for index in range(brace, len(source)):
        depth += (source[index] == "{") - (source[index] == "}")
        if depth == 0:
            return source[start:index + 1]
    raise AssertionError("Unclosed function: " + name)


def test_all_four_report_rows_keep_complete_quantities():
    for filename, name in (
        ("InOutDetailReportScreen.kt", "InOutDetailItemRow"),
        ("ReportScreens.kt", "DailyReportItemRow"),
        ("StockDailyReportScreen.kt", "StockDailyItemRow"),
        ("StockLedgerReportScreen.kt", "StockLedgerItemRow"),
    ):
        body = function(read("ui/screens/" + filename), name)
        assert "width(110.dp)" not in body, filename
        assert "softWrap = true" in body, filename
        assert "fontFeatureSettings = \"tnum\"" in body, filename
        # Keep the existing format and source quantity; never fit by rounding again.
        assert "formatQty(" in body, filename


def test_manual_entry_has_persistent_error_and_respects_stocktake_zero_policy():
    base = read("ui/screens/ScanScreenBase.kt").split("// Manual add dialog", 1)[1]
    assert "isError = quantityInputError(manualQty, allowZeroQuantity) != null" in base
    assert "supportingText =" in base
    assert "KeyboardActions(onDone = { onManualAdd() })" in base
    assert "manualCode.isNotBlank() && quantityInputError(manualQty, allowZeroQuantity) == null" in base
    stocktake = function(read("ui/screens/ScanScreens.kt"), "StocktakeScreen")
    assert stocktake.count("manualQty.toQtyOrNull(allowZero = true)") == 2
    assert "allowZeroQuantity = true" in stocktake


def test_stocktake_and_confirmation_keep_numeric_details_complete():
    row = function(read("ui/screens/StocktakeRecordScreens.kt"), "StocktakeRecordDetailRow")
    quantities = row.split("val unit =", 1)[1]
    assert "maxLines" not in quantities
    assert quantities.count("softWrap = true") == 2
    assert "账面" in quantities and "实盘" in quantities and "item.difference" in quantities
    ledger = read("ui/screens/StockLedgerReportScreen.kt")
    selected_material = ledger.split("val sub = listOfNotNull(", 1)[1].split("Spacer", 1)[0]
    assert "本仓结存" in selected_material
    assert "TextOverflow.Ellipsis" not in selected_material
    assert 'formatQuantity(uiState.totalQuantity)}" to Int.MAX_VALUE' in read("ui/screens/ScanScreens.kt")
    voice = read("ui/components/VoiceOutDraftDialogs.kt").split("val parsedBits =", 1)[1].split("@Composable", 1)[0]
    assert "state.quantity" in voice and "softWrap = true" in voice
    assert "maxLines" not in voice


def test_global_and_scan_status_share_account_scoped_projection():
    manager = read("data/repository/OfflineQueueManager.kt")
    assert "_displayState.value = queueDisplayState(rows, session)" in manager
    global_status = read("ui/components/GlobalQueueStatus.kt")
    assert "snapshot.forSession(session)" in global_status
    assert "queue.retryFailed()" in global_status
    scan = read("ui/viewmodel/scan/ScanViewModel.kt")
    assert "queue.displayState.collect" in scan
    assert "snapshot.forSession(RetrofitClient.sessionSnapshot())" in scan
    assert "queue.pendingCount.collect" not in scan
    nav = read("ui/navigation/NavGraph.kt")
    assert "GlobalQueueStatus(RetrofitClient.sessionSnapshot())" in nav
    assert "authState.isLoggedIn" in nav
    assert "currentRoute !in setOf(Screen.Inbound.route, Screen.Outbound.route, Screen.Stocktake.route))" in nav


def test_all_primary_entry_points_use_saved_navigation_and_input():
    nav = read("ui/navigation/NavGraph.kt")
    assert "navController.navigatePrimary(screen.route)" in nav
    helper = function(nav, "NavHostController.navigatePrimary")
    for contract in ("saveState = true", "launchSingleTop = true", "restoreState = true"):
        assert contract in helper
    assert nav.count("navController.navigatePrimary(") == 4
    for filename in ("ScanScreens.kt", "OpeningStockScreen.kt"):
        source = read("ui/screens/" + filename)
        assert 'var manualCode by rememberSaveable { mutableStateOf("") }' in source
        assert 'var manualQty by rememberSaveable { mutableStateOf("1") }' in source


def test_report_summaries_wrap_without_competing_for_one_row():
    for filename, name, count in (
        ("ReportScreens.kt", "DailyReportSummaryContent", 3),
        ("InOutDetailReportScreen.kt", "InOutSummaryContent", 3),
        ("StockDailyReportScreen.kt", "StockDailySummaryContent", 4),
        ("StockLedgerReportScreen.kt", "LedgerSummaryContent", 4),
    ):
        source = read("ui/screens/" + filename)
        assert "fun " + name + "(" in source, filename
        body = function(source, name)
        assert "Column(" in body
        assert body.count("Row(Modifier.fillMaxWidth()") == 2
        assert body.count("modifier = Modifier.weight(1f)") == count
        assert "quantityDisplayText(value)" in source
        assert "containerColor = Primary.copy(alpha = 0.08f).compositeOver(MaterialTheme.colorScheme.background)" in source


def test_white_gradient_controls_use_shared_dark_scrim():
    assert "Color.Black.copy(alpha = 0.12f)" in read("ui/theme/Color.kt")
    home = read("ui/screens/HomeScreen.kt")
    header = function(read("ui/components/WmsComponents.kt"), "WmsGradientHeader")
    assert home.count(".background(GradientControlScrim)") == 2
    assert ".background(GradientControlScrim)" in header
