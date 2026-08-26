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


# ---------- fix3 后续修复（2026-08-26 CI run 32928804369 失败根因） ----------

ENGINE = (ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com"
          / "factory" / "wms" / "ui" / "viewmodel" / "voice" / "SherpaVoiceSttEngine.kt"
          ).read_text(encoding="utf-8")


def test_model_url_exists_in_release() -> None:
    """T5：默认模型 URL 必须指向官方 release 中真实存在的模型。

    原 URL（…-zh-en-2023-06-26）在 release 资产列表中不存在，
    GitHub 返回 Not Found，是 CI run 32928804369 模型下载失败的根因。"""
    m = re.search(
        r'val defaultUrl\s*=\s*"([^"]+)"\s*\+\s*"([^"]+)"', GRADLE)
    assert m, "未找到 defaultUrl 定义"
    url = m.group(1) + m.group(2)
    assert "zh-en-2023-06-26" not in url, \
        f"defaultUrl 禁止再引用不存在的模型（当前 {url}）"
    assert "sherpa-onnx-streaming-zipformer-zh-14M-2023-02-23" in url, \
        f"defaultUrl 必须是真实存在的 zh-14M-2023-02-23 模型（当前 {url}）"


def test_download_task_flattens_standard_filenames() -> None:
    """T6：download task 必须把顶层目录 + epoch/int8 后缀的文件平铺重命名为
    引擎期望的标准四件套（tokens.txt/encoder.onnx/decoder.onnx/joiner.onnx）。"""
    body = GRADLE[GRADLE.find('tasks.register("downloadSherpaModel")'):]
    assert "pickVariant" in body, "缺变体挑选逻辑（前缀匹配+int8 优先）"
    assert "int8" in body, "手机端必须优先 int8 量化变体"
    assert 'File(targetDir, "encoder.onnx")' in body, "encoder 必须重命名为 encoder.onnx"
    assert 'File(targetDir, "decoder.onnx")' in body, "decoder 必须重命名为 decoder.onnx"
    assert 'File(targetDir, "joiner.onnx")' in body, "joiner 必须重命名为 joiner.onnx"


def test_engine_installs_model_from_assets() -> None:
    """T7：引擎必须支持从 APK assets 复制模型到 filesDir（打通 assets→运行时最后一环）。"""
    assert "copyModelFromAssets" in ENGINE, "SherpaVoiceSttEngine 缺 assets→filesDir 复制"
    assert "BuildConfig.SHERPA_ENABLED" in ENGINE, "复制逻辑必须检查 SHERPA_ENABLED"
    assert "BuildConfig.SHERPA_MODEL_DIR" in ENGINE, "复制逻辑必须使用 SHERPA_MODEL_DIR 定位 assets"
    assert "appContext.assets.open" in ENGINE, "复制逻辑必须从 assets 读取模型"


def test_ci_downloads_and_verifies_aar() -> None:
    """T8：CI 必须下载并显式校验 AAR（AAR 只发 GitHub Releases，缺失会让
    checkDebugAarMetadata 失败——run 32930112111 的教训）。"""
    assert "downloadSherpaAar" in CI, "CI 缺 downloadSherpaAar 步骤"
    assert "libs/sherpa-onnx-1.13.6.aar" in CI, "CI 缺 AAR 文件存在性校验"
    dl = CI.find("downloadSherpaAar")
    build = CI.find("Build Debug APK")
    assert dl != -1 and build != -1 and dl < build, \
        "downloadSherpaAar 必须在 Build Debug APK 之前执行"


def test_aar_gitignored() -> None:
    """T9：AAR 是构建期下载产物，必须在 .gitignore 排除（不进 git）。"""
    gi = (ROOT / "app" / "android-native-wms" / ".gitignore").read_text(encoding="utf-8")
    assert "app/libs/*.aar" in gi, ".gitignore 缺 app/libs/*.aar 排除规则"
