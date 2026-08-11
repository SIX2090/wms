# -*- coding: utf-8 -*-
"""BUG-2026-08-11-017 回归测试：移动端物料档案图片加载失败无可见状态。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID_ROOT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
RETROFIT_CLIENT = ANDROID_ROOT / "data" / "api" / "RetrofitClient.kt"
ARCHIVE_SCREENS = ANDROID_ROOT / "ui" / "screens" / "MaterialArchiveScreens.kt"
APPLICATION = ANDROID_ROOT / "WmsApplication.kt"


def test_t1_retrofit_client_exposes_shared_okhttp_client():
    """图片下载必须复用 API 的 Bearer 认证客户端。"""
    source = RETROFIT_CLIENT.read_text(encoding="utf-8")
    assert "fun sharedOkHttpClient(): OkHttpClient = okHttpClient" in source


def test_t2_application_configures_coil_with_shared_client():
    """Coil 全局 ImageLoader 必须使用统一 OkHttpClient。"""
    source = APPLICATION.read_text(encoding="utf-8")
    assert "newImageLoader" in source
    assert "RetrofitClient.sharedOkHttpClient()" in source
    assert "OkHttpClientFetcherFactory" in source


def test_t3_archive_image_error_is_visible_to_operator():
    """单张物料图片下载失败不能只保留灰色背景。"""
    source = ARCHIVE_SCREENS.read_text(encoding="utf-8")
    assert "AsyncImagePainter.State.Error" in source
    assert 'Text("图片加载失败")' in source


def test_t4_archive_image_uses_resolved_url_only_when_present():
    """空 URL 必须直接显示失败状态，避免空模型静默降级为灰块。"""
    source = ARCHIVE_SCREENS.read_text(encoding="utf-8")
    assert "val imageUrl = resolveImageUrl(image.url)" in source
    assert "if (imageUrl.isBlank())" in source
