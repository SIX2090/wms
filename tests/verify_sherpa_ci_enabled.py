# -*- coding: utf-8 -*-
"""AI-MOB-VOICE-F01-fix3（2026-08-26）回归检查：CI 默认构建必须带 sherpa 离线语音。

背景：语音功能"不能用"的根因是默认 APK 未打包 sherpa 模型、云端引擎又依赖
腾讯云密钥环境变量（部署常漏配）。修复 = CI 构建默认开 -Pwms.sherpa=true
并下载模型打进 APK；同时按 BUG-2026-08-16-022 规矩递增版本号（6 / 3.3.0）。

用例：
  T1. android-build.yml 构建步骤带 -Pwms.sherpa=true
  T2. android-build.yml 含 downloadSherpaModel 步骤且在 Build 之前
  T3. android-build.yml 含模型文件存在性校验（download task 失败只 warn，必须显式校验）
  T4. build.gradle.kts 版本号 >= (6, "3.3.0")（含 sherpa 的 APK 必须能作为更新安装）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".github" / "workflows" / "android-build.yml").read_text(encoding="utf-8")
GRADLE = (ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts").read_text(encoding="utf-8")


def test_ci_build_with_sherpa_flag() -> None:
    """T1：assembleDebug 必须带 -Pwms.sherpa=true。"""
    assert re.search(r"assembleDebug\s+-Pwms\.sherpa=true", CI), \
        "Build Debug APK 步骤必须带 -Pwms.sherpa=true，否则打出的 APK 无离线语音"


def test_ci_download_model_before_build() -> None:
    """T2：downloadSherpaModel 步骤必须存在且在 Build Debug APK 之前。"""
    dl = CI.find("downloadSherpaModel")
    build = CI.find("Build Debug APK")
    assert dl != -1, "CI 缺 downloadSherpaModel 步骤"
    assert build != -1, "CI 缺 Build Debug APK 步骤"
    assert dl < build, "downloadSherpaModel 必须在 Build Debug APK 之前执行"


def test_ci_verify_model_present() -> None:
    """T3：必须显式校验 4 个模型文件（download task 失败只 warn 不 fail）。"""
    for f in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        assert f in CI, f"CI 缺模型文件校验：{f}"
    assert "assets/sherpa-onnx/stream" in CI, "CI 缺模型目录校验"


def test_version_bumped_for_sherpa() -> None:
    """T4：版本号 >= 6 / 3.3.0（BUG-2026-08-16-022：能力合入必须递增版本号）。"""
    m_code = re.search(r"versionCode\s*=\s*(\d+)", GRADLE)
    m_name = re.search(r'versionName\s*=\s*"([\d.]+)"', GRADLE)
    assert m_code and m_name, "build.gradle.kts 缺 versionCode/versionName"
    assert int(m_code.group(1)) >= 6, \
        f"含 sherpa 的 APK versionCode 必须 >= 6（当前 {m_code.group(1)}），否则手机不识别为更新"
    assert m_name.group(1) >= "3.3.0", \
        f"含 sherpa 的 APK versionName 必须 >= 3.3.0（当前 {m_name.group(1)}）"
