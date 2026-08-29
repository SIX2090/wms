# -*- coding: utf-8 -*-
"""sherpa-onnx 打包回归检查（契约于 2026-08-29 反转，见 AI-MOB-APK-001）。

历史（AI-MOB-VOICE-F01-fix3，2026-08-26）：语音"不能用"的根因是默认 APK 未打包
sherpa 模型、云端引擎又依赖腾讯云密钥（当时未配置），故 CI 默认开
`-Pwms.sherpa=true` 把模型打进 APK。

现状（AI-MOB-APK-001，2026-08-29）：腾讯云密钥已配置，且
`VoiceSttEngineRegistry.defaultSelector` 中 `CloudAsrVoiceSttEngine.isAvailable()`
恒为 true —— 引擎链永远走云端，sherpa 引擎一次都不会被用到。此时 sherpa 模型
（约 70MB）+ AAR（4 种 ABI 的 .so）随 APK 打包纯属浪费体积，故 CI 默认不再打包。

开关与 download task 全部保留，需要离线语音时给构建加 `-Pwms.sherpa=true` 即可，
T5–T7/T9 守护这部分能力不被破坏。

用例：
  T1. CI 的 gradlew 构建命令不得再带 -Pwms.sherpa=true（APK 瘦身）
  T2. CI 不得再有 downloadSherpaModel / downloadSherpaAar 步骤
  T3. CI 不得再有模型四件套存在性校验步骤
  T4. 版本号已递增（BUG-2026-08-16-022：产物变更必须递增，手机才能识别为更新）
  T5. build.gradle 的 defaultUrl 仍指向真实存在的官方模型（开关恢复时可用）
  T6. download task 仍会把模型文件平铺重命名为标准四件套
  T7. 引擎仍支持从 assets 复制模型到 filesDir
  T8. -Pwms.sherpa 开关机制保留（可按需重新启用）
  T9. AAR 仍在 .gitignore 排除（构建产物不进 git）
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".github" / "workflows" / "android-build.yml").read_text(encoding="utf-8")
GRADLE = (ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts").read_text(encoding="utf-8")


def test_ci_build_without_sherpa_flag() -> None:
    """T1（2026-08-29 反转）：gradlew 构建命令不得再带 -Pwms.sherpa=true。

    只检查真正的构建命令（run: ./gradlew ...），不扫注释——注释里写明
    "如何恢复离线语音"是有价值的文档，不该被当成违规。
    """
    gradle_cmds = [
        ln.strip() for ln in CI.splitlines()
        if re.match(r"\s*run:\s*\./gradlew", ln)
    ]
    assert gradle_cmds, "CI 未找到任何 ./gradlew 构建命令，本用例前提失效"
    bad = [c for c in gradle_cmds if "-Pwms.sherpa=true" in c]
    assert not bad, (
        "CI 的 gradlew 构建命令不得再带 -Pwms.sherpa=true：云端（腾讯云）引擎 "
        "isAvailable() 恒为 true，sherpa 模型一次都不会被用到，打进 APK 纯属浪费体积。"
        f"违规命令：{bad}"
    )


def test_ci_no_sherpa_download_steps() -> None:
    """T2（反转）：不得再有模型/AAR 下载步骤。"""
    assert "downloadSherpaModel" not in CI, "CI 仍有 downloadSherpaModel 步骤（应随打包一并移除）"
    assert "downloadSherpaAar" not in CI, "CI 仍有 downloadSherpaAar 步骤（应随打包一并移除）"


def test_ci_no_model_verify_step() -> None:
    """T3（反转）：模型校验步骤随打包一并移除。"""
    for f in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        assert f not in CI, f"CI 仍有模型文件校验：{f}（已不打模型，校验应移除）"
    assert "assets/sherpa-onnx/stream" not in CI, "CI 仍有模型目录校验（已不打模型）"


def test_version_bumped_for_slim_apk() -> None:
    """T4：产物变更必须递增版本号（BUG-2026-08-16-022），否则手机不识别为更新。"""
    m_code = re.search(r"versionCode\s*=\s*(\d+)", GRADLE)
    m_name = re.search(r'versionName\s*=\s*"([^"]+)"', GRADLE)
    assert m_code and m_name, "build.gradle.kts 缺 versionCode/versionName"
    assert int(m_code.group(1)) >= 8, (
        f"瘦身 APK 的 versionCode 必须 >= 8（当前 {m_code.group(1)}），否则手机不识别为更新"
    )
    assert m_name.group(1) >= "3.5.0", (
        f"瘦身 APK 的 versionName 必须 >= 3.5.0（当前 {m_name.group(1)}）"
    )


# ---------- 保留能力守护（开关恢复时可直接使用） ----------

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


def test_sherpa_switch_preserved_in_gradle() -> None:
    """T8（改造）：-Pwms.sherpa 开关机制必须保留，只是 CI 默认不打包。"""
    assert 'project.findProperty("wms.sherpa")' in GRADLE, \
        "build.gradle.kts 缺 -Pwms.sherpa 开关（离线语音需可按需恢复）"
    assert "SHERPA_ENABLED" in GRADLE, "缺 SHERPA_ENABLED buildConfigField"
    assert "SHERPA_MODEL_DIR" in GRADLE, "缺 SHERPA_MODEL_DIR buildConfigField"


def test_aar_gitignored() -> None:
    """T9：AAR 是构建期下载产物，必须在 .gitignore 排除（不进 git）。"""
    gi = (ROOT / "app" / "android-native-wms" / ".gitignore").read_text(encoding="utf-8")
    assert "app/libs/*.aar" in gi, ".gitignore 缺 app/libs/*.aar 排除规则"
