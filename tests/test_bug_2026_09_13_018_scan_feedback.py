from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms'


def test_scan_merge_feedback_is_separate_from_submit_success():
    source = (ANDROID / 'ui/viewmodel/scan/ScanViewModel.kt').read_text(encoding='utf-8')
    body = source.split('fun addScanLine(', 1)[1].split('fun existingLineQuantity', 1)[0]
    assert 'scanFeedback =' in body
    assert '已累计' in body
    assert 'formatQuantity' in body
    assert 'if (_uiState.value.isLoading) return' in body


def test_removal_uses_confirmed_identity_and_quantity_not_index():
    source = (ANDROID / 'ui/viewmodel/scan/ScanViewModel.kt').read_text(encoding='utf-8')
    body = source.split('fun removeScanLine(', 1)[1].split('\n    fun ', 1)[0]
    assert 'expected: ScanLine' in body
    assert 'expected.material_code' in body
    assert 'expected.location_code' in body
    assert 'expected.quantity' in body
    assert 'isLoading' in body
    assert 'totalQuantity = current.sumOf' in body


def test_confirmation_and_camera_feedback_are_connected():
    screen = (ANDROID / 'ui/screens/ScanScreenBase.kt').read_text(encoding='utf-8')
    dialog = (ANDROID / 'ui/components/ScannerDialog.kt').read_text(encoding='utf-8')
    assert 'pendingRemoval = line' in screen
    assert 'viewModel.removeScanLine(line)' in screen
    assert '确认移除物料' in screen
    assert 'feedbackMessage = scanFeedback' in screen
    assert 'feedbackMessage ?: "已加入：$lastScannedCode"' in dialog
