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
    # text 是 WmsOutlinedActionButton 的第一个参数，onClick 在其后——
    # 取「扫码添加」到「手动添加」之间的按钮体
    camera_button = source.split(CAMERA_LABEL, 1)[1].split(MANUAL_LABEL, 1)[0]
    assert 'showCameraScanner = true' in camera_button
    assert 'onShowScanner' not in camera_button


def test_manual_entry_remains_separate_from_camera_entry():
    source = SCREENS.read_text(encoding='utf-8')
    camera_button = source.split(CAMERA_LABEL, 1)[1].split(MANUAL_LABEL, 1)[0]
    manual_button = source.split(MANUAL_LABEL, 1)[1][:600]
    assert 'showCameraScanner = true' in camera_button
    assert 'onShowScanner' in manual_button
