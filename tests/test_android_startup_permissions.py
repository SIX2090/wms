from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/MainActivity.kt'
MANIFEST = ROOT / 'app/android-native-wms/app/src/main/AndroidManifest.xml'


def test_manifest_declares_camera_and_microphone():
    source = MANIFEST.read_text(encoding='utf-8')
    assert 'android.permission.CAMERA' in source
    assert 'android.permission.RECORD_AUDIO' in source


def test_startup_requests_both_permissions_before_app_navigation():
    source = MAIN.read_text(encoding='utf-8')
    assert 'RequestMultiplePermissions()' in source
    assert 'Manifest.permission.CAMERA' in source
    assert 'Manifest.permission.RECORD_AUDIO' in source
    assert 'LaunchedEffect(Unit)' in source
    assert 'if (missing.isEmpty())' in source
    assert 'AppNavGraph()' in source


def test_denied_permissions_open_system_settings():
    source = MAIN.read_text(encoding='utf-8')
    assert 'Settings.ACTION_APPLICATION_DETAILS_SETTINGS' in source
    assert '去设置开启权限' in source
