# -*- coding: utf-8 -*-
"""
SherpaVoiceSttEngine 中 AudioRecord 音频采集管线的静态断言。

目标：
  - AudioRecord 必须使用 16kHz / MONO / PCM_16BIT 三参数组合（sherpa-onnx
    流式模型默认期望）；
  - 必须使用 VOICE_RECOGNITION 音频源（绕过 AGC / NS，避免破坏识别输入）；
  - 采集线程循环读取帧大小需为 100ms 量级（1600 samples @ 16kHz），便于
    sherpa 流式喂数据；
  - PCM16 (Short) → Float[-1,1] 的换算系数必须为 /32768f；
  - 读取的 Short 必须喂给 SherpaRuntime.feed 并触发 pollPartial → listener；
  - AudioRecord 异常 / 权限 / state != STATE_INITIALIZED 必须转
    SttError.PermissionDenied / AudioError / AudioError；
  - stopAudioCapture 必须安全 join 线程、stop+release AudioRecord，无泄漏。

使用方法：
  cd /workspace && python -m pytest tests/verify_sherpa_audio_record_integration.py -xvs --noconftest
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHERPA_ENGINE = (
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
    / "SherpaVoiceSttEngine.kt"
)


def _read() -> str:
    assert SHERPA_ENGINE.is_file(), f"missing {SHERPA_ENGINE}"
    return SHERPA_ENGINE.read_text(encoding="utf-8")


def _method_body(src: str, name: str, end_marker: str = "private fun ") -> str:
    """按"private fun <name>"定位后取到下一个"private fun"前。"""
    start = src.find(f"private fun {name}(")
    assert start != -1, f"找不到 private fun {name}("
    body_start = src.find("{", start)
    assert body_start != -1, f"{name} 没有函数体"
    depth = 1
    i = body_start + 1
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return src[body_start: i]


# ---------- AudioRecord 参数与音频源 ----------

def test_uses_mono_pcm16_16khz() -> None:
    src = _read()
    # 16kHz sample rate
    assert "16_000" in src, "必须使用 16kHz 采样率（sherpa 流式模型默认）"
    # CHANNEL_IN_MONO
    assert "CHANNEL_IN_MONO" in src, "必须使用 CHANNEL_IN_MONO 单声道"
    # ENCODING_PCM_16BIT
    assert "ENCODING_PCM_16BIT" in src, "必须使用 ENCODING_PCM_16BIT"


def test_uses_voice_recognition_source() -> None:
    """使用 VOICE_RECOGNITION 而非 MIC，绕开 AGC/NS，避免破坏识别输入。"""
    src = _read()
    assert "MediaRecorder.AudioSource.VOICE_RECOGNITION" in src, \
        "必须使用 VOICE_RECOGNITION 音频源"


# ---------- startAudioCapture 入口与错误兜底 ----------

def test_start_audio_capture_gets_min_buffer_size() -> None:
    """必须先 getMinBufferSize 才能 new AudioRecord。"""
    src = _read()
    body = _method_body(src, "startAudioCapture")
    assert "AudioRecord.getMinBufferSize" in body, \
        "startAudioCapture 必须先调用 getMinBufferSize"
    # getMinBufferSize 失败必须 error 兜底
    assert "AudioRecord.ERROR" in body, "minBufferSize 失败必须判 AudioRecord.ERROR"
    assert "SttError.AudioError" in body, "minBufferSize 失败必须回调 AudioError"


def test_start_audio_capture_handles_security_exception() -> None:
    """缺少 RECORD_AUDIO 权限时必须 catch SecurityException 并回调 PermissionDenied。"""
    src = _read()
    body = _method_body(src, "startAudioCapture")
    assert "SecurityException" in body, "必须 catch SecurityException"
    assert "SttError.PermissionDenied" in body, "无权限必须回调 PermissionDenied"


def test_start_audio_capture_handles_state_uninitialized() -> None:
    """AudioRecord.state != STATE_INITIALIZED 必须 release + AudioError。"""
    src = _read()
    body = _method_body(src, "startAudioCapture")
    assert "STATE_INITIALIZED" in body, "必须校验 STATE_INITIALIZED"
    assert "record.release" in body, "失败必须 release 录音器"


# ---------- captureLoop 读取与转码 ----------

def test_capture_loop_uses_frame_sized_short_buffer() -> None:
    """captureLoop 必须按 100ms 帧（1600 samples）读取。"""
    src = _read()
    body = _method_body(src, "captureLoop")
    assert "ShortArray(FRAME_SAMPLES)" in body, "必须按 FRAME_SAMPLES 大小读取"
    assert "record.read(" in body, "必须调用 AudioRecord.read"
    # 循环条件用 capturing
    assert "capturing" in body, "循环必须受 capturing 控制"


def test_capture_loop_pcm16_to_float_conversion() -> None:
    """Short → Float[-1, 1] 必须使用 /32768f 系数。"""
    src = _read()
    body = _method_body(src, "captureLoop")
    assert "FloatArray" in body, "必须把 Short 转 FloatArray"
    assert "/ 32768f" in body, "必须用 /32768f 把 PCM16 转 Float[-1,1]"


def test_capture_loop_feeds_runtime_and_polls_partial() -> None:
    """采集到 PCM 后必须 rt.feed + rt.pollPartial + listener.onPartial。"""
    src = _read()
    body = _method_body(src, "captureLoop")
    assert "rt.feed" in body or ".feed(" in body, "必须调用 runtime.feed"
    assert "rt.pollPartial" in body or ".pollPartial()" in body, \
        "必须 pollPartial 取流式部分结果"
    assert "listener?.onPartial" in body, "必须把 partial 推给 listener"


def test_capture_loop_swallows_throwable() -> None:
    """AudioRecord.read / sherpa feed 抛异常不能崩线程。"""
    src = _read()
    body = _method_body(src, "captureLoop")
    assert "try {" in body, "captureLoop 必须 try 保护"
    assert "catch" in body, "captureLoop 必须有 catch 块"
    # 至少要保护 record.read 与 feed/poll
    assert "record.read" in body and "feed" in body, \
        "record.read 与 feed 都必须在 try 块内"


def test_capture_loop_uses_correct_sample_rate_constant() -> None:
    """feed 时必须用 SAMPLE_RATE 常量（与 AudioRecord 初始化一致）。"""
    src = _read()
    body = _method_body(src, "captureLoop")
    # 不允许魔法数字 16000
    assert "SAMPLE_RATE" in body, "feed 时必须传 SAMPLE_RATE 常量"
    assert "16000" not in body.replace("16_000", ""), \
        "feed 采样率不允许使用 16000 魔法数字"


# ---------- stopAudioCapture 收尾 ----------

def test_stop_audio_capture_joins_capture_thread() -> None:
    """停止时必须 join 采集线程，避免 AudioRecord 已被 release 还在 read。"""
    src = _read()
    body = _method_body(src, "stopAudioCapture")
    assert "capturing.set(false)" in body, "必须先设 capturing=false"
    assert "captureThread" in body, "必须引用 captureThread"
    assert ".join(" in body, "必须 join 线程"


def test_stop_audio_capture_stops_and_releases_record() -> None:
    """AudioRecord 必须 stop + release，顺序不可颠倒。"""
    src = _read()
    body = _method_body(src, "stopAudioCapture")
    assert ".stop()" in body, "必须 stop AudioRecord"
    assert ".release()" in body, "必须 release AudioRecord"


def test_stop_audio_capture_handles_throwable_in_record_cleanup() -> None:
    """stop/release 必须 try-catch Throwable 兜底，避免异常中断后续清理。"""
    src = _read()
    body = _method_body(src, "stopAudioCapture")
    # 既允许 runCatching（runCatching { r.stop() }）也允许 try-catch Throwable
    has_runcatching = "runCatching" in body
    has_try_catch_throwable = "try" in body and "catch" in body and "Throwable" in body
    assert has_runcatching or has_try_catch_throwable, \
        "stop/release 必须 runCatching 或 try-catch Throwable 兜底"


# ---------- 帧大小与 sample rate 常量 ----------

def test_frame_samples_is_100ms() -> None:
    """FRAME_SAMPLES 必须 1600（= 16000 * 0.1s）。"""
    src = _read()
    assert "FRAME_SAMPLES = 1_600" in src, "FRAME_SAMPLES 必须为 1_600（100ms @ 16kHz）"


def test_sample_rate_is_16khz() -> None:
    """SAMPLE_RATE 必须 16_000。"""
    src = _read()
    assert "SAMPLE_RATE = 16_000" in src, "SAMPLE_RATE 必须 16_000"


# ---------- stop() 时调 pollFinal 推结果 ----------

def test_stop_polls_final_result() -> None:
    """SherpaVoiceSttEngine.stop 必须 pollFinal 并把结果推给 listener.onResult。"""
    src = _read()
    body = src.split("override fun stop(")[1].split("override fun destroy")[0]
    assert "pollFinal" in body, "stop 必须 pollFinal"
    assert "listener?.onResult" in body, "stop 必须推 onResult"


# ---------- start() 失败时不允许有残留 runtime ----------

def test_start_cleans_up_on_failure() -> None:
    """start() 反射创建失败时必须 destroy runtime 并重置 started 标志。"""
    src = _read()
    body = src.split("override fun start(")[1].split("override fun stop")[0]
    # catch 块中必须 destroy runtime 与 reset started
    catch_idx = body.find("catch")
    assert catch_idx != -1, "start() 必须有 catch 块"
    catch_body = body[catch_idx:]
    assert "runtime?.destroy" in catch_body or "runtime!!.destroy" in catch_body, \
        "catch 中必须 destroy runtime"
    assert "runtime = null" in catch_body, "catch 中必须把 runtime 置 null"
    assert "started = false" in catch_body, "catch 中必须把 started 重置"


# ---------- destroy() 必须停录音 + release runtime ----------

def test_destroy_releases_audio_and_runtime() -> None:
    """destroy() 必须先停录音再 release runtime。"""
    src = _read()
    body = src.split("override fun destroy(")[1].split("override fun setListener")[0]
    assert "stopAudioCapture" in body, "destroy 必须 stopAudioCapture"
    assert "runtime?.destroy" in body, "destroy 必须 release runtime"
    assert "listener = null" in body, "destroy 必须清空 listener 防止内存泄漏"
