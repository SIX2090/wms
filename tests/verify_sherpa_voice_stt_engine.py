# -*- coding: utf-8 -*-
"""
SherpaVoiceSttEngine / SherpaRuntime / VoiceSttEngineRegistry 选择器静态断言。

目标：
  - SherpaVoiceSttEngine 实现 VoiceSttEngine 接口并暴露 5 个标准方法；
  - isAvailable() 先校验模型文件（tokens.txt / encoder / decoder / joiner），
    再做 Class.forName 反射探测（避免硬依赖编译期类）；
  - 不引入模型 / 不在 classpath 时不抛异常，只返回 false；
  - SherpaRuntime 用反射调 OnlineRecognizer / OnlineStream API；
  - VoiceSttEngineRegistry 默认选择器先 sherpa 后 Android，提供 setSelector。

使用方法：
  cd /workspace && python -m pytest tests/verify_sherpa_voice_stt_engine.py -xvs --noconftest
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
SHERPA_ENGINE = VOICE_DIR / "SherpaVoiceSttEngine.kt"
SHERPA_RUNTIME = VOICE_DIR / "SherpaRuntime.kt"
VM_FILE = VOICE_DIR / "VoiceCommandViewModel.kt"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


# ---------- SherpaVoiceSttEngine 实现断言 ----------

def test_sherpa_engine_implements_interface() -> None:
    src = _read(SHERPA_ENGINE)
    assert "class SherpaVoiceSttEngine(" in src, "缺少 SherpaVoiceSttEngine 类"
    assert ": VoiceSttEngine" in src, "SherpaVoiceSttEngine 必须实现 VoiceSttEngine"


def test_sherpa_engine_has_five_methods() -> None:
    src = _read(SHERPA_ENGINE)
    for sig in (
        "override fun isAvailable(): Boolean",
        "override fun start(config: SttConfig)",
        "override fun stop()",
        "override fun destroy()",
        "override fun setListener(listener: VoiceSttListener?)",
    ):
        assert sig in src, f"SherpaVoiceSttEngine 必须实现 {sig}"


def test_sherpa_engine_checks_four_model_files() -> None:
    src = _read(SHERPA_ENGINE)
    body = src.split("override fun isAvailable")[1].split("override fun start")[0]
    for required in ("tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"):
        assert required in body, f"isAvailable 必须校验 {required}"


def test_sherpa_engine_uses_reflection_probe() -> None:
    """必须用 Class.forName 探测，不在编译期 import sherpa 类。"""
    src = _read(SHERPA_ENGINE)
    assert "Class.forName" in src or "SherpaRuntime.probeClassloader" in src, \
        "isAvailable 必须用 Class.forName 反射探测 sherpa-onnx 类"
    # 不应在 import / 顶层引用 sherpa 类；常量字符串里出现全限定名是允许的。
    assert "import com.k2fsa.sherpa" not in src, \
        "SherpaVoiceSttEngine 不应 import sherpa-onnx 顶层类（避免编译期硬依赖）"


def test_sherpa_engine_falls_back_on_unavailable() -> None:
    src = _read(SHERPA_ENGINE)
    body = src.split("override fun isAvailable")[1].split("override fun start")[0]
    # 模型缺失 / 类加载失败 → 返回 false，不抛异常
    assert "return false" in body, "isAvailable 必须能返回 false 触发 fallback"
    assert "isDirectory" in body or "isFile" in body, "isAvailable 必须校验文件存在"


def test_sherpa_engine_engulfs_throwable() -> None:
    """start() 内部必须 try-catch，避免无 sherpa 库时崩溃。"""
    src = _read(SHERPA_ENGINE)
    body = src.split("override fun start")[1].split("override fun stop")[0]
    assert "try {" in body, "start() 必须 try-catch 保护"
    assert "catch" in body, "start() 必须有 catch 块"


def test_sherpa_engine_emits_engine_unavailable_on_missing() -> None:
    src = _read(SHERPA_ENGINE)
    body = src.split("override fun start")[1].split("override fun stop")[0]
    assert "SttError.EngineUnavailable" in body, \
        "不可用时必须通过 listener 回调 SttError.EngineUnavailable"
    assert "listener?.onError" in body, "必须通过 listener.onError 回调"


# ---------- SherpaRuntime 反射包装 ----------

def test_sherpa_runtime_uses_class_forname() -> None:
    src = _read(SHERPA_RUNTIME)
    assert "Class.forName" in src, "SherpaRuntime 必须用 Class.forName"
    assert "import com.k2fsa.sherpa" not in src, \
        "SherpaRuntime 不应 import sherpa-onnx 类（编译期硬依赖）"


def test_sherpa_runtime_probes_classloader() -> None:
    src = _read(SHERPA_RUNTIME)
    assert "fun probeClassloader" in src, "必须提供 probeClassloader() 静态方法"
    assert "ClassNotFoundException" in src, "必须捕获 ClassNotFoundException"


def test_sherpa_runtime_create_returns_null_on_failure() -> None:
    src = _read(SHERPA_RUNTIME)
    body = src.split("fun create(")[1]
    # create 是 fun create(...): SherpaRuntime? = try {...} catch ...，catch 块末尾的 null 即为返回值
    assert "return null" in body or "} catch" in body, \
        "create() 必须 try-catch 并在 catch 块返回 null"
    assert "ClassNotFoundException" in body, "必须捕获 ClassNotFoundException"
    assert "Throwable" in body, "必须兜底 Throwable"


def test_sherpa_runtime_uses_java_lang_reflect() -> None:
    src = _read(SHERPA_RUNTIME)
    assert "import java.lang.reflect.Method" in src, "必须用 java.lang.reflect.Method"
    assert ".invoke(" in src, "必须用反射 invoke 调用"


# ---------- 引擎选择中心 ----------

def test_registry_default_prefers_sherpa() -> None:
    """默认选择器必须先 sherpa 再 Android。"""
    src = _read(VM_FILE)
    registry_body = src[src.find("object VoiceSttEngineRegistry"):]
    assert "SherpaVoiceSttEngine(context)" in registry_body, \
        "VoiceSttEngineRegistry 必须先实例化 SherpaVoiceSttEngine"
    assert "AndroidVoiceSttEngine(context)" in registry_body, \
        "VoiceSttEngineRegistry 必须有 AndroidVoiceSttEngine fallback"
    # 选择器顺序：先判 sherpa.isAvailable() 再决定
    assert "if (sherpa.isAvailable())" in registry_body or "if(sherpa.isAvailable())" in registry_body, \
        "必须根据 isAvailable() 决定是否使用 sherpa"
    # sherpa 的实例化必须出现在 AndroidVoiceSttEngine 实例化之前
    sherpa_idx = registry_body.find("SherpaVoiceSttEngine(context)")
    android_idx = registry_body.find("AndroidVoiceSttEngine(context)")
    assert sherpa_idx != -1 and android_idx != -1, "必须同时有 sherpa / android 实例化"
    assert sherpa_idx < android_idx, "sherpa 实例化必须先于 AndroidVoiceSttEngine"


def test_registry_set_selector_overrides() -> None:
    src = _read(VM_FILE)
    registry_body = src[src.find("object VoiceSttEngineRegistry"):]
    assert "fun setSelector(" in registry_body, "Registry 必须提供 setSelector"
    assert "this.selector = selector" in registry_body or "this.selector = " in registry_body, \
        "setSelector 必须覆盖 selector 字段"
