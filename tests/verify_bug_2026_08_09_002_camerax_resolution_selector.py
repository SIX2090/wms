# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-002 回归测试：Android App 扫码显示"摄像头不可用"

根因：
  app/android-native-wms/.../ui/components/ScannerDialog.kt 的 ImageAnalysis 构建中
  同时调用 setTargetAspectRatio(AspectRatio.RATIO_16_9) 和
  setTargetResolution(android.util.Size(1280, 720))。CameraX 1.3+ 这两个 API 互斥，
  构造阶段即抛 IllegalArgumentException，bindToLifecycle 失败，预览区显示
  "摄像头不可用 / Cannot use both setTargetResolution and setTargetAspectRatio on
  the same config."，ML Kit 永远收不到任何帧。

修复：
  改用 CameraX 1.3+ 官方推荐的 ResolutionSelector + AspectRatioStrategy +
  ResolutionStrategy 写法：16:9 比例（硬件不支持时回退 4:3）+ 最高可用分辨率，
  国产机多摄/不同分辨率自动适配，避免崩溃。

具体断言：
  T1. 必须导入 ResolutionSelector / AspectRatioStrategy / ResolutionStrategy
  T2. 旧死 import androidx.camera.core.AspectRatio 已清掉
  T3. ImageAnalysis 不再调用 .setTargetAspectRatio() / .setTargetResolution()
  T4. 改用 .setResolutionSelector() 传入 AspectRatioStrategy +
      ResolutionStrategy；比例策略使用 16:9 优先 + 自动回退；分辨率策略使用
      HIGHEST_AVAILABLE_STRATEGY

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_002_camerax_resolution_selector.py -xvs --noconftest
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNER_KT = (
    ROOT
    / "app"
    / "android-native-wms"
    / "app"
    / "src"
    / "main"
    / "java"
    / "com"
    / "factory"
    / "wms"
    / "ui"
    / "components"
    / "ScannerDialog.kt"
)


def _source() -> str:
    return SCANNER_KT.read_text(encoding="utf-8")


def test_t1_resolution_selector_imports_present():
    """必须导入 ResolutionSelector 三个相关类"""
    src = _source()
    for cls in ("AspectRatioStrategy", "ResolutionSelector", "ResolutionStrategy"):
        assert (
            f"import androidx.camera.core.resolutionselector.{cls}" in src
        ), f"缺少 import: androidx.camera.core.resolutionselector.{cls}"


def test_t2_dead_aspectratio_import_removed():
    """androidx.camera.core.AspectRatio 已无业务引用，import 必须清掉"""
    src = _source()
    # 没在 import 段，也没有任何 AspectRatio.xxx 引用
    assert "import androidx.camera.core.AspectRatio" not in src, (
        "死 import 未清：AspectRatio 已无业务引用"
    )
    assert not re.search(r"\bAspectRatio\.", src), (
        "AspectRatio. 仍被引用，import 不能删"
    )


def test_t3_legacy_mutually_exclusive_apis_removed():
    """.setTargetAspectRatio() / .setTargetResolution() 必须彻底清掉（互斥 API 不能再混用）"""
    src = _source()
    assert not re.search(r"\.setTargetAspectRatio\s*\(", src), (
        ".setTargetAspectRatio() 仍存在，CameraX 1.3+ 会抛 IllegalArgumentException"
    )
    assert not re.search(r"\.setTargetResolution\s*\(", src), (
        ".setTargetResolution() 仍存在，与 setTargetAspectRatio 互斥"
    )


def test_t4_resolution_selector_strategy_wiring():
    """ResolutionSelector 必须使用 16:9 优先 + 最高可用分辨率策略"""
    src = _source()

    # 构造 ResolutionSelector
    assert re.search(
        r"ResolutionSelector\.Builder\(\)\s*"
        r"\.setAspectRatioStrategy\([^)]*RATIO_16_9[^)]*\)"
        r"\s*\.setResolutionStrategy\([^)]*HIGHEST_AVAILABLE_STRATEGY[^)]*\)"
        r"\s*\.build\(\)",
        src,
    ), "ResolutionSelector 配置不完整：必须使用 16:9 比例 + 最高可用分辨率"

    # 比例策略：16:9 优先 + 不支持时自动回退（_FALLBACK_AUTO_）
    assert "RATIO_16_9_FALLBACK_AUTO_STRATEGY" in src, (
        "比例策略应为 RATIO_16_9_FALLBACK_AUTO_STRATEGY（硬件不支持 16:9 时回退 4:3）"
    )

    # 分辨率策略：硬件能给的最高分辨率
    assert "HIGHEST_AVAILABLE_STRATEGY" in src, (
        "分辨率策略应为 HIGHEST_AVAILABLE_STRATEGY（国产机多摄自动适配）"
    )

    # ImageAnalysis.Builder 通过 .setResolutionSelector() 接入
    assert re.search(
        r"ImageAnalysis\.Builder\(\)\s*\.setResolutionSelector\s*\(\s*resolutionSelector\s*\)",
        src,
    ), "ImageAnalysis 必须通过 setResolutionSelector(resolutionSelector) 接入"
