# -*- coding: utf-8 -*-
"""
build.gradle.kts 引入 sherpa-onnx 依赖 + 模型下载 task 的静态断言。

目标：
  - 暴露 buildConfigField：SHERPA_ENABLED / SHERPA_MODEL_DIR；
  - 仅当 -Pwms.sherpa=true 时才 implementation("com.k2fsa.sherpaonnx:sherpa-onnx:...")；
  - 注册 downloadSherpaModel task，下载到 assets/sherpa-onnx/stream/；
  - 失败时仅 warn，不抛异常（保证 fallback 路径仍可用）；
  - 默认构建（不开 sherpa）不影响离线 / 国内网络受限环境。

使用方法：
  cd /workspace && python -m pytest tests/verify_sherpa_build_config.py -xvs --noconftest
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_GRADLE = (
    ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts"
)


def _read() -> str:
    assert BUILD_GRADLE.is_file(), f"missing {BUILD_GRADLE}"
    return BUILD_GRADLE.read_text(encoding="utf-8")


# ---------- buildConfigField 暴露 ----------

def test_sherpa_enabled_buildconfig_field() -> None:
    src = _read()
    assert 'buildConfigField("boolean", "SHERPA_ENABLED"' in src, \
        "必须声明 SHERPA_ENABLED buildConfigField"
    assert "wms.sherpa" in src, "SHERPA_ENABLED 必须读取 -Pwms.sherpa 属性"


def test_sherpa_model_dir_buildconfig_field() -> None:
    src = _read()
    assert '"SHERPA_MODEL_DIR"' in src, \
        "必须声明 SHERPA_MODEL_DIR buildConfigField"
    assert "sherpa-onnx/stream" in src, "默认模型目录必须为 sherpa-onnx/stream"


def test_sherpa_model_dir_overridable_by_env() -> None:
    src = _read()
    assert "WMS_SHERPA_MODEL_DIR" in src, \
        "SHERPA_MODEL_DIR 必须支持 WMS_SHERPA_MODEL_DIR 环境变量覆盖"


# ---------- AAR 依赖 ----------

def test_sherpa_dependency_is_local_aar() -> None:
    """sherpa-onnx 的 AAR 只发 GitHub Releases、不在 Maven Central（com.k2fsa
    group 不存在），必须本地 files() 依赖，禁止写 Maven 坐标（CI run 32930112111
    checkDebugAarMetadata 失败的根因）。"""
    src = _read()
    assert 'implementation(files("libs/sherpa-onnx-1.13.6.aar"))' in src, \
        "必须以本地 AAR 文件依赖 libs/sherpa-onnx-1.13.6.aar"
    assert "com.k2fsa.sherpaonnx:sherpa-onnx" not in src, \
        "禁止使用 Maven 坐标 com.k2fsa.sherpaonnx（Maven Central 不存在该构件）"
    assert 'tasks.register("downloadSherpaAar")' in src, \
        "必须注册 downloadSherpaAar task（从 GitHub Releases 下载 AAR 到 app/libs/）"


def test_sherpa_dependency_gated_by_property() -> None:
    src = _read()
    # 取整个 dependencies 块（从 "// sherpa-onnx 本地离线中文语音识别" 到下一个未缩进的 "}"）
    start = src.find("// sherpa-onnx 本地离线中文语音识别")
    assert start != -1, "缺少 sherpa-onnx 依赖注释"
    body = src[start:]
    assert "wms.sherpa" in body, "sherpa 依赖必须读取 wms.sherpa 属性"
    assert "toBooleanStrictOrNull" in body, "sherpa 依赖必须用 toBooleanStrictOrNull 解析开关"
    assert 'implementation(files("libs/sherpa-onnx-1.13.6.aar"))' in body, \
        "必须在开关开启时 implementation 引入本地 sherpa-onnx AAR"


# ---------- downloadSherpaModel task ----------

def test_download_sherpa_model_task_registered() -> None:
    src = _read()
    assert 'tasks.register("downloadSherpaModel")' in src, \
        "必须注册 downloadSherpaModel task"
    assert 'group = "sherpa"' in src, "task group 必须为 sherpa"


def test_download_target_assets_dir() -> None:
    src = _read()
    # 目标必须是 assets/sherpa-onnx/stream/，才能随 APK 一起打包
    assert "src/main/assets/sherpa-onnx/stream" in src, \
        "模型必须下载到 src/main/assets/sherpa-onnx/stream/ 才能打包进 APK"


def test_download_url_configurable() -> None:
    src = _read()
    assert "modelUrl" in src, "下载 URL 必须可通过 -PmodelUrl 配置"
    assert "github.com/k2-fsa/sherpa-onnx" in src, \
        "默认 URL 应指向 k2-fsa/sherpa-onnx 官方 release"


def test_download_required_files_checked() -> None:
    src = _read()
    # 取整个 task 块：从 tasks.register("downloadSherpaModel") 到文件结尾
    body = src[src.find('tasks.register("downloadSherpaModel")'):]
    for f in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        assert f in body, f"下载后必须校验 {f} 存在"


def test_download_failure_does_not_throw() -> None:
    """下载失败必须只 warn，不能 throw——保证默认构建（无网络）通过。"""
    src = _read()
    body = src[src.find('tasks.register("downloadSherpaModel")'):]
    assert "try {" in body, "下载逻辑必须 try-catch"
    assert "catch" in body, "必须有 catch 块"
    assert "logger.warn" in body, "失败时必须 logger.warn 而非 throw"
    assert "fallback" in body or "AndroidVoiceSttEngine" in body, \
        "失败提示必须提到 fallback 路径"


# ---------- settings.gradle.kts 仓库 ----------

def test_maven_central_in_settings() -> None:
    p = ROOT / "app" / "android-native-wms" / "settings.gradle.kts"
    src = p.read_text(encoding="utf-8")
    assert "mavenCentral()" in src, "settings.gradle.kts 必须包含 mavenCentral() 仓库"
