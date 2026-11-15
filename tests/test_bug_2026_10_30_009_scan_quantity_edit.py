"""Android UI 接线契约；状态/持久化的真实执行另见 ScanQuantityEditTest.kt。"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "app/android-native-wms/app"
SRC = ANDROID / "src/main/java/com/factory/wms"


def read(path):
    return (SRC / path).read_text(encoding="utf-8")


def test_all_transaction_scan_screens_share_quantity_editor():
    screens = read("ui/screens/ScanScreens.kt")
    for name, next_name in (("InboundScreen", "OutboundScreen"),
                            ("OutboundScreen", "StockQueryScreen"),
                            ("StocktakeScreen", None)):
        body = screens.split(f"fun {name}(", 1)[1]
        if next_name:
            body = body.split(f"fun {next_name}(", 1)[0]
        assert "ScanScreenBase(" in body
        assert ("allowZeroQuantity = true" in body) == (name == "StocktakeScreen")
    assert "allowZeroQuantity: Boolean = false" in read("ui/screens/ScanScreenBase.kt")


def test_quantity_badge_opens_prefilled_editor_with_visible_hint():
    base = read("ui/screens/ScanScreenBase.kt")
    editor = read("ui/components/ScanQuantityStepper.kt")
    assert 'ScanQuantityStepper(line = line' in base
    assert 'draft = quantityDrafts[quantityKey(line)]' in base
    assert 'viewModel.setQuantityDraft(quantityKey(line), draft)' in base
    assert 'pendingSubmissionId == null' in base
    assert 'draft?.raw ?: formatQuantity(line.quantity)' in editor
    assert 'KeyboardType.Decimal' in editor and 'BasicTextField' in editor
    assert 'contentDescription = "减少数量：' in editor and 'contentDescription = "增加数量：' in editor
    assert editor.count('Modifier.size(48.dp)') >= 2 and '.heightIn(min = 48.dp)' in editor


def test_dialog_saves_exact_quantity_and_cancel_does_not_write():
    base = read("ui/screens/ScanScreenBase.kt")
    editor = read("ui/components/ScanQuantityStepper.kt")
    assert 'viewModel.updateScanLineQuantity(expected, quantity, allowZeroQuantity)' in base
    assert 'KeyboardType.Decimal' in editor and 'ImeAction.Done' in editor
    assert 'onDone = {' in editor and 'commit(it, draft.raw)' in editor
    assert 'Text("确定数量")' in editor and 'Text("取消")' in editor
    assert 'raw.text.toQtyOrNull(allowZero)' in editor
    assert 'expected = line.quantity; value = TextFieldValue(formatQuantity(line.quantity)); onDraft(null)' in editor
    assert 'viewModel.uiState.value.quantityDrafts.isEmpty()' in base
    # Actual edits, cancel, stale rows and rapid +/- are verified by Compose and ViewModel tests.


def test_state_update_guards_stale_rows_and_recomputes_summary():
    vm = read("ui/viewmodel/scan/ScanViewModel.kt")
    body = vm.split("fun updateScanLineQuantity(", 1)[1].split("fun existingLineQuantity(", 1)[0]
    assert "if (draftEditingBlocked()) return false" in body
    assert "!quantity.isFinite()" in body
    assert "location_code.orEmpty() == expected.location_code.orEmpty()" in body
    assert "matches.singleOrNull()" in body
    assert "current[index].quantity != expected.quantity" in body
    assert "current[index].copy(quantity = quantity)" in body
    assert "current.sumOf { it.quantity }" in body
    assert "current.add(" not in body


def test_existing_opening_editor_and_scan_accumulation_are_preserved():
    screen = read("ui/screens/OpeningStockScreen.kt")
    assert "viewModel.updateLineQuantityExpected(line.uiId, line.quantity, qty)" in screen
    assert "uiState.quantityDrafts.containsKey(line.uiId)" in screen
    assert "viewModel.removeLineExpected(line.uiId, line.quantity)" in screen
    assert "quantity = existing.quantity + line.quantity" in read("ui/viewmodel/scan/ScanViewModel.kt")


def test_apk_version_can_update_existing_installation():
    gradle = (ANDROID / "build.gradle.kts").read_text(encoding="utf-8")
    assert int(re.search(r"versionCode\s*=\s*(\d+)", gradle)[1]) >= 29
    assert tuple(map(int, re.search(r'versionName\s*=\s*"([\d.]+)"', gradle)[1].split("."))) >= (3, 9, 5)
