"""Layout integration contracts; Compose measurements run in CompactLayoutTest on Android CI."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"


def read(path):
    return (SRC / path).read_text(encoding="utf-8")


def test_shared_header_has_no_measuring_decoration():
    header = read("ui/components/WmsComponents.kt").split("fun WmsGradientHeader(")[1].split("fun WmsCard(")[0]
    assert ".size(140.dp)" not in header
    assert ".size(90.dp)" not in header
    assert ".statusBarsPadding()" in header
    assert 'contentDescription = "返回"' in header


def test_home_and_profile_status_icons_follow_actual_safe_area_background():
    for name in ("HomeScreen.kt", "ProfileScreen.kt"):
        source = read("ui/screens/" + name)
        assert "StatusBarIconEffect(darkIcons = !isSystemInDarkTheme())" in source
        assert ".padding(padding)" in source


def test_nested_scaffolds_consume_only_applied_bottom_inset():
    source = read("ui/navigation/NavGraph.kt")
    assert ".padding(bottom = innerPadding.calculateBottomPadding())" in source
    assert ".consumeWindowInsets(PaddingValues(bottom = innerPadding.calculateBottomPadding()))" in source
    assert ".consumeWindowInsets(innerPadding)" not in source  # top inset was not applied


def test_optional_fields_collapse_but_warehouse_stays_visible():
    source = read("ui/screens/ScanScreens.kt")
    for name, next_name, warehouse, optional in (
        ("InboundScreen", "OutboundScreen", "收货仓库", "供应商（选填）"),
        ("OutboundScreen", "StockQueryScreen", "出库仓库", "领料部门（选填）"),
    ):
        screen = source.split(f"fun {name}(", 1)[1].split(f"fun {next_name}(", 1)[0]
        header = screen.split("header = {", 1)[1].split("detailsCount =", 1)[0]
        details = screen.split("details = {", 1)[1]
        assert warehouse in header and optional not in header
        assert optional in details
    base = read("ui/screens/ScanScreenBase.kt")
    assert "if (details != null || showEvidenceCapture)" in base
    assert 'title = "更多信息（选填）"' in base
    assert "scanState.evidence.size" in base
    assert "ScanLocationSelector(viewModel)" in base


def test_disclosure_is_saveable_closed_by_default_and_tall_enough_to_tap():
    source = read("ui/components/WmsExpandableSection.kt")
    assert "rememberSaveable { mutableStateOf(false) }" in source
    assert ".heightIn(min = 48.dp)" in source
    assert "if (expanded) content()" in source
    assert "Text(summary" in source


def test_clear_requires_confirmation_and_respects_pending_submission():
    source = read("ui/screens/ScanScreenBase.kt")
    summary = source.split("// Summary bar", 1)[1].split("// Scan list", 1)[0]
    assert "onClick = { showClearConfirmation = true }" in summary
    assert "viewModel.clearScanLines()" not in summary
    dialog = source.split("if (showClearConfirmation)", 1)[1].split("pendingQuantityEdit?.let", 1)[0]
    assert "!isLoading && scanState.pendingSubmissionId == null" in dialog
    assert "viewModel.clearScanLines()" in dialog.split("dismissButton", 1)[0]
    assert "viewModel." not in dialog.split("dismissButton", 1)[1]


def test_material_specs_are_not_truncated_and_quantity_edit_is_preserved():
    source = read("ui/screens/ScanScreenBase.kt")
    details = source.split("if (materialDetails.isNotBlank())", 1)[1].split("// 扫码/手动加入", 1)[0]
    assert "softWrap = true" in details
    assert "maxLines" not in details
    assert "pendingQuantityEdit = line" in source
    assert "viewModel.updateScanLineQuantity(line, quantity, allowZeroQuantity)" in source
    assert 'Text("修改"' in source


def test_empty_submit_removed_and_search_copy_fits_one_line():
    base = read("ui/screens/ScanScreenBase.kt")
    actions = base.split("// Bottom actions", 1)[1].split("// Manual add dialog", 1)[0]
    assert actions.index("if (scanLines.isNotEmpty())") < actions.index("WmsPrimaryButton(")
    assert "onClick = onSubmitClick" in actions
    assert ".padding(horizontal = 16.dp, vertical = 8.dp)" in actions
    assert 'placeholder = { Text("名称 / 编码 / 规格", maxLines = 1' in read("ui/screens/ScanScreens.kt")


def test_home_keeps_all_destinations_and_profile_shows_selectable_full_address():
    home = read("ui/screens/HomeScreen.kt")
    assert home.count("FunctionCard(") == 15
    assert '"常用操作" else "更多功能"' in home
    assert '"当前服务器"' not in home
    profile = read("ui/screens/ProfileScreen.kt")
    server = profile.split('ProfileSectionCard("服务器信息")', 1)[1].split('// ── 扫码设置', 1)[0]
    assert "SelectionContainer" in server and "uiState.baseUrl" in server
    assert "TextOverflow.Ellipsis" not in server
    assert "ScanFeedback.setEnabled(context, enabled)" in profile
