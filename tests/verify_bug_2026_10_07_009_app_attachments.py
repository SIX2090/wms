"""BUG-2026-10-07-009 契约测试：App AI 助手支持图片/文件上传

验证 assistant_chat 接口支持 image（base64）和 file（base64 + file_name）。
"""

import re
from pathlib import Path


def test_backend_accepts_image():
    """后端 AssistantChatRequest 支持 image 字段"""
    api_py = Path(__file__).parent.parent / 'app' / 'routes' / 'native_api.py'
    content = api_py.read_text(encoding='utf-8', errors='replace')
    assert 'image: str | None' in content
    assert 'BUG-2026-10-07-009' in content


def test_backend_accepts_file():
    """后端 AssistantChatRequest 支持 file + file_name 字段"""
    api_py = Path(__file__).parent.parent / 'app' / 'routes' / 'native_api.py'
    content = api_py.read_text(encoding='utf-8', errors='replace')
    assert 'file: str | None' in content
    assert 'file_name: str | None' in content


def test_backend_passes_images_to_handler():
    """后端把 images 传给 _ai_handle_warehouse_assistant_request"""
    api_py = Path(__file__).parent.parent / 'app' / 'routes' / 'native_api.py'
    content = api_py.read_text(encoding='utf-8', errors='replace')
    assert "'images': images" in content or '"images": images' in content


def test_backend_passes_files_to_handler():
    """后端把 files 传给 _ai_handle_warehouse_assistant_request"""
    api_py = Path(__file__).parent.parent / 'app' / 'routes' / 'native_api.py'
    content = api_py.read_text(encoding='utf-8', errors='replace')
    assert "'files': files" in content or '"files": files' in content


def test_app_handles_images():
    """_ai_handle_warehouse_assistant_request 支持 images"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'def _ai_handle_warehouse_assistant_request\(.*?\n(.*?)(?=\ndef |\Z)', content, re.DOTALL)
    assert match
    func_body = match.group(1)
    assert 'payload.get(\'images\')' in func_body or 'payload.get("images")' in func_body


def test_app_normalizes_files():
    """_ai_normalize_file_attachments 函数存在"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    assert 'def _ai_normalize_file_attachments(' in content
    assert 'BUG-2026-10-07-009' in content


def test_app_parses_excel():
    """_ai_parse_excel_bytes 函数存在"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    assert 'def _ai_parse_excel_bytes(' in content
    assert 'openpyxl' in content


def test_app_parses_pdf():
    """_ai_parse_pdf_bytes 函数存在"""
    app_py = Path(__file__).parent.parent / 'app' / 'app.py'
    content = app_py.read_text(encoding='utf-8', errors='replace')
    assert 'def _ai_parse_pdf_bytes(' in content
    assert 'PyPDF2' in content


def test_android_viewmodel_supports_image():
    """App ViewModel 支持 pendingImage"""
    vm_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/ai/AssistantChatViewModel.kt'
    content = vm_kt.read_text(encoding='utf-8')
    assert 'pendingImage: String?' in content
    assert 'setPendingImage' in content


def test_android_viewmodel_supports_file():
    """App ViewModel 支持 pendingFile"""
    vm_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/ai/AssistantChatViewModel.kt'
    content = vm_kt.read_text(encoding='utf-8')
    assert 'pendingFile: Pair<String, String>?' in content
    assert 'setPendingFile' in content


def test_android_screen_has_attach_button():
    """App 聊天页有 + 按钮"""
    screen_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt'
    content = screen_kt.read_text(encoding='utf-8')
    assert 'Icons.Outlined.Add' in content
    assert 'showAttachMenu' in content


def test_android_screen_has_camera_launcher():
    """App 聊天页有相机 launcher"""
    screen_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt'
    content = screen_kt.read_text(encoding='utf-8')
    assert 'cameraLauncher' in content
    assert 'TakePicturePreview' in content


def test_android_screen_has_gallery_launcher():
    """App 聊天页有相册 launcher"""
    screen_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt'
    content = screen_kt.read_text(encoding='utf-8')
    assert 'galleryLauncher' in content
    assert 'GetContent' in content


def test_android_screen_has_file_launcher():
    """App 聊天页有文件 launcher"""
    screen_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt'
    content = screen_kt.read_text(encoding='utf-8')
    assert 'fileLauncher' in content
