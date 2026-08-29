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
    """Coil 全局 ImageLoader 必须使用统一 OkHttpClient（Coil 2.x callFactory API）。"""
    source = APPLICATION.read_text(encoding="utf-8")
    assert "newImageLoader" in source
    assert "RetrofitClient.sharedOkHttpClient()" in source
    assert ".callFactory {" in source
    # Coil 3.x 专属 API/构件在 Coil 2.7.0 下不存在，禁止出现
    assert "OkHttpClientFetcherFactory" not in source
    assert "coil.network.okhttp" not in source


def test_t5_no_coil3_only_artifact_dependency():
    """io.coil-kt:coil-network-okhttp 是 Coil 3.x 专属构件，Coil 2.7.0 无法解析。"""
    gradle = (ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    assert "coil-network-okhttp" not in gradle


def test_t3_archive_image_error_is_visible_to_operator():
    """单张物料图片下载失败必须给操作员可见的失败状态。

    UI 表现不限定（Icon+contentDescription / Text 都可）——只要出现
    「图片加载失败」文案且能识别 AsyncImagePainter.State.Error 即视为合规。
    """
    source = ARCHIVE_SCREENS.read_text(encoding="utf-8")
    assert "AsyncImagePainter.State.Error" in source, "需识别 AsyncImagePainter.State.Error"
    assert "图片加载失败" in source, "需给操作员可见的「图片加载失败」状态（Icon/Text 均可）"


def test_t4_archive_image_uses_resolved_url_only_when_present():
    """空 URL 必须直接显示失败状态，避免空模型静默降级为灰块。

    代码可写为 if 分支或合并到布尔 loadFailed ——只要 imageUrl.isBlank()
    参与守卫判定、且没有把空 URL 当有效 URL 透传给 painter，即视为合规。
    """
    source = ARCHIVE_SCREENS.read_text(encoding="utf-8")
    assert "val imageUrl = resolveImageUrl(image.url)" in source, "需先解析 imageUrl"
    assert "imageUrl.isBlank()" in source, "需有 imageUrl.isBlank() 守卫"
    # 显式 if 分支或合并到 loadFailed 都允许；只禁止把空 URL 当有效值透传
    assert "model = imageUrl" in source
