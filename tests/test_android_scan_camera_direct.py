from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreenBase.kt'

# AI-APP-FIX-404：扫码/手动按钮由自绘 OutlinedButton + Text("扫码添加") 收敛为
# WmsOutlinedActionButton(text = "扫码添加", ...)——文案由插槽改参数，断言锚点相应更新。
# 行为契约不变：「扫码添加」直达相机（showCameraScanner = true，不经手动弹窗 onShowScanner）；
# 「手动添加」保持走 onShowScanner 手动录入弹窗。

CAMERA_LABEL = 'text = "扫码添加"'
MANUAL_LABEL = 'text = "手动添加"'


def test_scan_button_opens_camera_directly():
    source = SCREENS.read_text(encoding='utf-8')
    camera_action = source.split('val startScan = {', 1)[1].split('}', 1)[0]
    buttons = source.split('val scanIcon = ', 1)[1].split(MANUAL_LABEL, 1)[0]
    assert 'continuousScanCount = 0' in camera_action and 'lastScannedCode = null' in camera_action
    assert 'showCameraScanner = true' in camera_action and 'onShowScanner' not in camera_action
    assert buttons.count(CAMERA_LABEL + ', onClick = startScan') == 2
    assert 'onShowScanner' not in buttons


def test_manual_entry_remains_separate_from_camera_entry():
    source = SCREENS.read_text(encoding='utf-8')
    manual_button = source.split(MANUAL_LABEL, 1)[1].split(')', 1)[0]
    assert 'onClick = onShowScanner' in manual_button
    assert 'startScan' not in manual_button
