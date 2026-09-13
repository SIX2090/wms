from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreenBase.kt'


def test_scan_button_opens_camera_directly():
    source = SCREENS.read_text(encoding='utf-8')
    action = source.split('Text("扫码添加"', 1)[0].split('Action buttons', 1)[1]
    assert 'showCameraScanner = true' in action
    assert 'onShowScanner' not in action


def test_manual_entry_remains_separate_from_camera_entry():
    source = SCREENS.read_text(encoding='utf-8')
    camera_button = source.split('Text("扫码添加"', 1)[0].split('Action buttons', 1)[1]
    manual_button = source.split('Text("手动添加"', 1)[0].split('Text("扫码添加"', 1)[1]
    assert 'showCameraScanner = true' in camera_button
    assert 'onShowScanner' in manual_button
