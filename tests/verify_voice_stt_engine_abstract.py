# -*- coding: utf-8 -*-
"""
语音识别引擎抽象层（VoiceSttEngine）静态断言。

目标：
  - VoiceSttEngine / VoiceSttListener / SttConfig / SttError 接口签名固定；
  - SttError.toUserMessage 覆盖 12 个枚举；
  - VoiceCommandViewModel 依赖 VoiceSttEngineFactory 工厂，不直接 new 具体引擎；
  - VoiceSttEngineRegistry 提供 setSelector / create 默认实现，且默认实现回落到
    AndroidVoiceSttEngine（兼容现有 UI 行为，不破坏国内无 Google 设备场景）；
  - 为后续 SherpaVoiceSttEngine 留好接入点（registry selector 可替换）。

使用方法：
  cd /workspace && python -m pytest tests/verify_voice_stt_engine_abstract.py -xvs --noconftest
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_DIR = (
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
    / "viewmodel"
    / "voice"
)
ENGINE_IFACE = VOICE_DIR / "VoiceSttEngine.kt"
VM_FILE = VOICE_DIR / "VoiceCommandViewModel.kt"
ANDROID_ENGINE = VOICE_DIR / "AndroidVoiceSttEngine.kt"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


# ---------- VoiceSttEngine 接口签名 ----------

def test_engine_interface_methods_present() -> None:
    src = _read(ENGINE_IFACE)
    for sig in (
        "fun isAvailable(): Boolean",
        "fun start(config: SttConfig = SttConfig())",
        "fun stop()",
        "fun destroy()",
        "fun setListener(listener: Listener?)",
    ):
        assert sig in src, f"VoiceSttEngine 接口必须声明 {sig}"


def test_listener_three_callbacks_present() -> None:
    src = _read(ENGINE_IFACE)
    for sig in (
        "fun onPartial(text: String)",
        "fun onResult(texts: List<String>)",
        "fun onError(error: SttError)",
    ):
        assert sig in src, f"VoiceSttListener 接口必须声明 {sig}"


def test_stt_error_has_twelve_entries() -> None:
    src = _read(ENGINE_IFACE)
    expected = {
        "NoMatch",
        "SpeechTimeout",
        "Busy",
        "AudioError",
        "PermissionDenied",
        "NetworkError",
        "NetworkTimeout",
        "ServerError",
        "ClientError",
        "TooManyRequests",
        "EngineUnavailable",
        "Unknown",
    }
    # 从 enum 块起始到 companion object 之前的 body 段，避免注释里分号误切
    enum_start = src.find("enum class SttError")
    assert enum_start != -1, "找不到 enum class SttError"
    enum_open = src.find("{", enum_start)
    enum_close = src.find("\n}", enum_open)
    body = src[enum_open: enum_close]
    for name in expected:
        # enum 写法："Name," 或最后一个 "Name;"
        assert f" {name}," in body or f" {name};" in body, \
            f"SttError 缺少 {name}"


def test_stt_error_to_user_message_covers_all_branches() -> None:
    src = _read(ENGINE_IFACE)
    body_start = src.find("fun toUserMessage(): String = when (this) {")
    assert body_start != -1, "SttError.toUserMessage 缺失"
    block = src[body_start: src.find("};", body_start) + 2]
    for name in (
        "NoMatch",
        "SpeechTimeout",
        "Busy",
        "AudioError",
        "PermissionDenied",
        "NetworkError",
        "NetworkTimeout",
        "ServerError",
        "ClientError",
        "TooManyRequests",
        "EngineUnavailable",
        "Unknown",
    ):
        assert f"{name} ->" in block, f"toUserMessage 缺少 {name} 分支"


def test_stt_config_defaults() -> None:
    src = _read(ENGINE_IFACE)
    assert "val language: String = \"zh-CN\"" in src, "SttConfig.language 默认必须是 zh-CN"
    assert "val partialResults: Boolean = true" in src, "SttConfig.partialResults 默认 true"
    assert "val maxResults: Int = 5" in src, "SttConfig.maxResults 默认 5"


# ---------- AndroidVoiceSttEngine 实现 ----------

def test_android_engine_implements_interface() -> None:
    src = _read(ANDROID_ENGINE)
    assert ": VoiceSttEngine" in src, "AndroidVoiceSttEngine 必须实现 VoiceSttEngine"
    assert "class AndroidVoiceSttEngine(" in src


def test_android_engine_uses_speech_recognizer() -> None:
    src = _read(ANDROID_ENGINE)
    for token in (
        "SpeechRecognizer.createSpeechRecognizer",
        "RecognizerIntent.ACTION_RECOGNIZE_SPEECH",
        "SpeechRecognizer.RESULTS_RECOGNITION",
    ):
        assert token in src, f"AndroidVoiceSttEngine 必须调用 {token}"


def test_android_engine_releases_old_recognizer_on_start() -> None:
    src = _read(ANDROID_ENGINE)
    body = src.split("override fun start(")[1].split("override fun stop(")[0]
    assert "releaseRecognizer()" in body, "start 必须先 release 旧 recognizer"


# ---------- ViewModel 依赖工厂而非具体实现 ----------

def test_viewmodel_depends_on_factory() -> None:
    src = _read(VM_FILE)
    assert "engineFactory: VoiceSttEngineFactory" in src, \
        "VoiceCommandViewModel 必须通过 VoiceSttEngineFactory 工厂获取引擎"
    assert "DefaultEngineFactory" in src, \
        "VoiceCommandViewModel 必须有默认工厂（向后兼容现有 UI 调用）"


def test_viewmodel_does_not_new_engine_directly() -> None:
    src = _read(VM_FILE)
    # 只检查 VoiceCommandViewModel 类体内不能直接 new；VoiceSttEngineRegistry
    # 的默认 fallback 是允许的（它是注册中心的实现细节）。
    class_open = src.find("class VoiceCommandViewModel(")
    assert class_open != -1, "找不到 VoiceCommandViewModel 类"
    # 找到与该类匹配的右花括号
    brace_open = src.find("{", class_open)
    depth = 1
    i = brace_open + 1
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    class_body = src[class_open: i]
    assert "AndroidVoiceSttEngine(" not in class_body, \
        "VoiceCommandViewModel 类体内不应直接 new AndroidVoiceSttEngine，必须走 factory/registry"


def test_viewmodel_uses_engine_listener_indirectly() -> None:
    src = _read(VM_FILE)
    # engineListener 必须有 onPartial / onResult / onError 三个回调
    for sig in (
        "override fun onPartial(text: String)",
        "override fun onResult(texts: List<String>)",
        "override fun onError(error: SttError)",
    ):
        assert sig in src, f"engineListener 必须实现 {sig}"


# ---------- 引擎注册中心 ----------

def test_registry_has_set_selector_and_create() -> None:
    src = _read(VM_FILE)
    assert "object VoiceSttEngineRegistry" in src, \
        "必须有 VoiceSttEngineRegistry 单例"
    assert "fun setSelector(" in src, "Registry 必须提供 setSelector"
    assert "fun create(" in src, "Registry 必须提供 create"
    assert "DefaultEngineFactory" in src, "DefaultEngineFactory 必须复用 Registry.create"


def test_default_selector_returns_android_engine() -> None:
    """默认选择器必须回落到 AndroidVoiceSttEngine，保证现有 UI 不退化。"""
    src = _read(VM_FILE)
    # selectAndroidDefault 或 selector 默认值应包含 AndroidVoiceSttEngine
    body = src[src.find("object VoiceSttEngineRegistry"):]
    assert "AndroidVoiceSttEngine(context)" in body, \
        "VoiceSttEngineRegistry 默认选择器必须返回 AndroidVoiceSttEngine"
