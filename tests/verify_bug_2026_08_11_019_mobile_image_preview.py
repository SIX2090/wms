"""BUG-2026-08-11-019 回归：手机端物料档案图片点击放大查看。

背景：Android 物料档案图片列表的缩略图没有绑定点击事件，
用户点击图片无反应，无法放大查看大图。

本测试做静态契约校验：
- T1: ArchiveImageCard 必须提供 onPreview 回调且图片区域可点击触发
- T2: 图片列表页必须持有预览状态并在大图地址非空时弹出全屏 Dialog
- T3: 预览大图必须 ContentScale.Fit 完整显示且点击可关闭
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREENS = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms" / "ui" / "screens" / "MaterialArchiveScreens.kt"


def _source() -> str:
    return SCREENS.read_text(encoding="utf-8")


def test_t1_card_has_preview_callback_and_clickable_image():
    """T1: 图片卡片必须接收 onPreview 回调，图片区域点击触发预览。"""
    source = _source()
    assert "onPreview: () -> Unit" in source
    assert ".clickable { onPreview() }" in source
    assert "onPreview = {" in source


def test_t2_screen_holds_preview_state_and_dialog():
    """T2: 列表页必须持有预览大图状态，非空时用全屏 Dialog 展示。"""
    source = _source()
    assert "previewImageUrl" in source
    assert "mutableStateOf<String?>(null)" in source
    assert "Dialog(" in source
    assert "onDismissRequest" in source


def test_t3_preview_dialog_fit_and_tap_to_dismiss():
    """T3: 预览大图必须完整适配（ContentScale.Fit）且点击可关闭。"""
    source = _source()
    assert "ContentScale.Fit" in source
    assert "previewImageUrl = null" in source
