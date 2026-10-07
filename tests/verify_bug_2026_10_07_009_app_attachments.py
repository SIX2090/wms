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
    assert 'pypdf' in content


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
    """App 聊天页有相机入口（AUDIT-2026-10-07-009-P1 后改全尺寸 TakePicture 链路）"""
    screen_kt = Path(__file__).parent.parent / 'app' / 'android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt'
    content = screen_kt.read_text(encoding='utf-8')
    assert 'cameraCapture' in content
    assert 'rememberCameraLauncherWithPermission' in content


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


# ==================== AUDIT-2026-10-07-009 五条缺陷修复验证 ====================

def _screen_content():
    return (Path(__file__).parent.parent / 'app' / 'android-native-wms' /
            'app' / 'src' / 'main' / 'java' / 'com' / 'factory' / 'wms' / 'ui' /
            'screens' / 'AssistantChatScreen.kt').read_text(encoding='utf-8', errors='replace')


def _viewmodel_content():
    return (Path(__file__).parent.parent / 'app' / 'android-native-wms' /
            'app' / 'src' / 'main' / 'java' / 'com' / 'factory' / 'wms' / 'ui' /
            'viewmodel' / 'ai' / 'AssistantChatViewModel.kt').read_text(encoding='utf-8', errors='replace')


def test_fix_p1_camera_full_resolution():
    """P1修复：拍照用 TakePicture+FileProvider（非低清缩略图契约）"""
    content = _screen_content()
    assert 'TakePicturePreview' not in content, '仍在用低清缩略图契约'
    assert 'rememberCameraLauncherWithPermission' in content, '未复用全尺寸相机组件'


def test_fix_p1_file_name_display_name():
    """P1修复：文件名从 ContentResolver 查 DISPLAY_NAME（非 lastPathSegment）"""
    content = _screen_content()
    assert 'OpenableColumns.DISPLAY_NAME' in content, '未用 DISPLAY_NAME 查真实文件名'
    # lastPathSegment 只允许作为 DISPLAY_NAME 查询失败时的兜底（runCatching 之后）
    fallback_pos = content.find('it.lastPathSegment')
    display_pos = content.find('OpenableColumns.DISPLAY_NAME')
    assert display_pos >= 0 and fallback_pos > display_pos, 'lastPathSegment 应只作兜底'


def test_fix_p2_attachment_preview_bar():
    """P2修复：附件预览条（可视反馈 + 移除按钮）"""
    content = _screen_content()
    assert 'clearPendingAttachments' in content, '预览条无移除入口'
    assert '已选' in content, '无附件已选提示文案'


def test_fix_p2_attachment_only_send():
    """P2修复：有附件时允许空文本发送"""
    vm = _viewmodel_content()
    assert 'hasAttachment' in vm, '未实现附件时空文本放行'
    assert '请识别附件内容' in vm, '纯附件请求无占位文案'
    screen = _screen_content()
    assert 'pendingImage != null || uiState.pendingFile != null' in screen, '发送按钮未联动附件状态'


def test_fix_p3_mime_sniffing():
    """P3修复：图片 MIME 按二进制头嗅探（非写死 jpeg）"""
    api_py = Path(__file__).parent.parent / 'app' / 'routes' / 'native_api.py'
    content = api_py.read_text(encoding='utf-8', errors='replace')
    assert "b'\\x89PNG" in content, '无 PNG 嗅探'
    assert 'image/webp' in content, '无 WEBP 嗅探'
    assert "f'data:image/jpeg;base64,{req.image}'" not in content, 'MIME 仍写死 jpeg'


def test_feature_010_clipboard_image_detection():
    """FEATURE-010：App 切前台检测剪贴板图片，弹「添加为附件」提示"""
    content = _screen_content()
    assert 'CLIPBOARD_SERVICE' in content, '未接入剪贴板服务'
    assert 'ON_RESUME' in content, '未监听切前台事件'
    assert '检测到剪贴板图片' in content, '无剪贴板图片提示文案'
    assert 'lastClipboardPromptedUri' in content, '无同图去重（会反复弹）'
    # 已有附件时不打扰
    assert 'alreadyHasAttachment' in content, '已有附件时仍会弹提示'


def test_fix_011_gallery_clipboard_compressed():
    """FIX-011：相册/剪贴板图片统一压缩（最长边 1600px + JPEG85），防 413"""
    content = _screen_content()
    # 相册路径和剪贴板路径都必须走解码压缩，不能直接 readBytes
    gallery_section = content[content.find('val galleryLauncher'):content.find('val fileLauncher')]
    assert 'BitmapFactory.decodeStream' in gallery_section, '相册仍直传原图'
    assert gallery_section.count('readBytes()') == 0, '相册未压缩直传'
    clipboard_section = content[content.find('clipboardImageDetected.value != null'):content.find('Scaffold(')]
    assert 'BitmapFactory.decodeStream' in clipboard_section, '剪贴板仍直传原图'


def test_feature_012_image_in_message_model():
    """FEATURE-012：图片进消息模型（AssistantChatMessage 有 image 字段，发送时存入）"""
    vm = _viewmodel_content()
    assert 'val image: String? = null' in vm, '消息模型无 image 字段'
    # send() 时 pendingImage 必须写入消息（不再用完即弃）
    send_section = vm[vm.find('fun send(text: String)'):vm.find('fun setPendingImage')]
    assert 'AssistantChatMessage(' in send_section, 'send 未构造消息'
    assert send_section.find('image = image') != -1, '图片未存入消息模型'


def test_feature_012_bubble_thumbnail_and_viewer():
    """FEATURE-012：气泡渲染图片缩略图 + 点击全屏查看器"""
    content = _screen_content()
    # 气泡里渲染缩略图（有图时不再只有文字占位）
    bubble_section = content[content.find('private fun AssistantMessageBubble'):content.find('private fun FullScreenImageViewer')]
    assert 'message.image != null' in bubble_section, '气泡不区分有无图片'
    assert 'BitmapFactory.decodeByteArray' in bubble_section, '气泡不解码图片'
    assert 'onImageClick' in bubble_section, '缩略图不可点击'
    # 全屏查看器
    viewer_section = content[content.find('private fun FullScreenImageViewer'):]
    assert 'detectTransformGestures' in viewer_section, '查看器不支持缩放'
    assert 'detectTapGestures' in viewer_section, '查看器不支持点击关闭'
    assert 'coerceIn(1f, 6f)' in viewer_section, '缩放倍数无上限保护'
    # 消息列表把点击回调接进气泡
    assert 'AssistantMessageBubble(message) { img -> viewerImage.value = img }' in content, '点击回调未接线'
