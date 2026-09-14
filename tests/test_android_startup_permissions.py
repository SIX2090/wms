"""Android 启动期权限申请的反向回归（BUG-2026-09-13-023 第二轮）。

现场证据：截图显示 `WMS扫码屡次停止运行` 与系统「是否允许访问相机？1/2」
弹框**同屏出现**——崩溃触发点即权限弹框本身。

根因：`Activity.requestPermissions()` 是同步打断式调用，会让 Activity
立即 PAUSED 去显示系统弹框。此前它在 `MainActivity.onCreate` 中的位置在
`setContent{}` **之前**，因此弹框出现时 Compose 尚未初始化；用户响应后
Activity 恢复，回调撞在未初始化的宿主上 → 进程被杀。

历史教训：MOBILE-PERMISSION-001 的 5 次提交全在更换申请 API，从未质疑
调用位置，故全部无效。**本文件即用于防止「启动期申请权限」这类写法回潮。**

正确做法：权限按需、在 Compose 内申请，二者均已具备：
  - CAMERA       → ui/components/ScannerDialog.kt
  - RECORD_AUDIO → ui/components/VoiceAssistant.kt
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/MainActivity.kt'
MANIFEST = ROOT / 'app/android-native-wms/app/src/main/AndroidManifest.xml'
SCANNER = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/ui/components/ScannerDialog.kt'
VOICE = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/ui/components/VoiceAssistant.kt'


def test_manifest_declares_camera_and_microphone():
    """清单仍须声明两个权限（按需申请的前提）。"""
    source = MANIFEST.read_text(encoding='utf-8')
    assert 'android.permission.CAMERA' in source
    assert 'android.permission.RECORD_AUDIO' in source


def test_main_activity_must_not_request_permissions_at_startup():
    """MainActivity 不得在启动期申请权限——这是崩溃根因，必须为空。"""
    source = MAIN.read_text(encoding='utf-8')
    # 去掉注释后检查，避免注释里的说明文字误触发
    code_lines = [
        ln for ln in source.split('\n')
        if not ln.strip().startswith('//')
    ]
    code = '\n'.join(code_lines)
    assert 'requestPermissions(' not in code, (
        "MainActivity 出现 requestPermissions() —— BUG-2026-09-13-023 根因回潮！"
        "该方法在 onCreate 中同步打断 Activity，使其在 Compose 初始化前 PAUSED，"
        "用户响应权限弹框后进程被杀。权限必须改为按需、在 Compose 内申请。"
    )
    assert 'REQUEST_STARTUP_PERMISSIONS' not in code, (
        "MainActivity 残留启动期权限请求码，说明启动期申请逻辑未被彻底移除"
    )


def test_camera_permission_requested_lazily_in_compose():
    """相机权限必须在扫码弹窗内按需申请。"""
    source = SCANNER.read_text(encoding='utf-8')
    assert 'rememberLauncherForActivityResult' in source
    assert 'Manifest.permission.CAMERA' in source
    assert 'LaunchedEffect' in source


def test_microphone_permission_requested_lazily_in_compose():
    """麦克风权限必须在语音组件内按需申请。"""
    source = VOICE.read_text(encoding='utf-8')
    assert 'rememberLauncherForActivityResult' in source
    assert 'Manifest.permission.RECORD_AUDIO' in source


def test_main_activity_still_composes_nav_graph():
    """移除权限申请后，UI 组合必须保持完整。"""
    source = MAIN.read_text(encoding='utf-8')
    assert 'setContent {' in source
    assert 'AppNavGraph()' in source
    # setContent 不得被任何前置的权限调用打断
    assert source.index('setContent {') < source.index('AppNavGraph()')
