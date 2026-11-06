"""BUG-2026-08-11-018 回归：物料管理列表图片可点击放大预览。

背景：物料档案管理列表"图片"列的缩略图没有绑定任何点击事件，
用户点击图片无反应，无法查看大图。

本测试做静态契约校验：
- T1: 列表缩略图必须绑定预览点击事件（previewMaterialImage）
- T2: 模板必须提供大图预览 Modal（imagePreviewModal + imagePreviewImg）
- T3: previewMaterialImage 函数必须设置大图地址并弹出 Modal
"""
from pathlib import Path
import re

from tests.material_page_source import material_page_source

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "app" / "templates" / "material.html"


def _source() -> str:
    return material_page_source()


def test_t1_thumbnail_binds_preview_click():
    """T1: 列表图片缩略图点击必须触发大图预览。"""
    source = _source()
    assert 'data-column-key="image"' in source
    image = re.search(r'<img[^>]*data-material-action="previewMaterialImage"[^>]*>', source)
    assert image
    assert 'role="button"' in image[0] and 'tabindex="0"' in image[0]
    assert 'previewMaterialImage: function(node) { previewMaterialImage(node.src); }' in source
    assert "document.addEventListener(eventName, function(event)" in source


def test_t2_preview_modal_exists():
    """T2: 模板必须包含大图预览 Modal 及其 img 元素。"""
    source = _source()
    assert 'id="imagePreviewModal"' in source
    assert 'id="imagePreviewImg"' in source


def test_t3_preview_function_sets_src_and_shows_modal():
    """T3: previewMaterialImage 必须给大图赋值并显示 Modal。"""
    source = _source()
    assert "function previewMaterialImage(" in source
    start = source.index('function previewMaterialImage(')
    body = source[start:source.index('\n}', start) + 2]
    assert "getElementById('imagePreviewImg').src = src" in body
    assert "imagePreviewModal" in body
    assert 'modal.show()' in body
