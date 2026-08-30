# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-003 回归测试：手机 WMS 语音功能卡在"正在聆听"

根因：
  app/android-native-wms/.../ui/viewmodel/voice/VoiceCommandViewModel.kt
  在国内 / 无 Google 服务的 Android 设备上，SpeechRecognizer 可能既不回调
  onBeginningOfSpeech 也不回调 onError，UI 永远停在"正在聆听，请说出指令…"
  初始 message，没有退出路径。onError 也没细分 ERROR_NETWORK / ERROR_SERVER /
  ERROR_CLIENT 等关键错误码。

修复（第一阶段，已合入 main）：
  - 引入 listenTimeoutJob：startListening 启动兜底超时（原 8 秒）；
  - stopListening / onPartial / onResult / onError 四个出口取消该 Job；
  - 超时后主动 destroy engine 并写入 error="识别超时，请重试"；
  - onError（AndroidVoiceSttEngine）保留 ERROR_NETWORK / ERROR_SERVER /
    ERROR_CLIENT / ERROR_TOO_MANY_REQUESTS 五个细分提示。

AI-MOB-APK-003（2026-08-30）超时阈值上调 8s -> 15s：
  现场反馈「手机语音一直识别超时」。8 秒兜底在真机上过于激进——从按下
  麦克风、引擎初始化、到说完一句「入库 合同 HT-2026-001 数量 20」，
  云端 ASR 往返常常超过 8 秒，指令还没说完就被判定超时，用户体感就是
  「一直超时」。故上调至 15 秒，仍保留兜底退出路径（不构成新的卡死风险）。

重构（第二阶段，本文件覆盖）：
  - 把 SpeechRecognizer 的具体实现抽到 [VoiceSttEngine] 接口里；
  - ViewModel 只依赖接口 + 工厂，不再直接 import android.speech.*；
  - 通过 [VoiceSttEngineRegistry] 选引擎，默认走 AndroidVoiceSttEngine，
    后续步骤会接 SherpaVoiceSttEngine。

具体断言：
  T1. ViewModel 仍含 listenTimeoutJob: Job? 字段；
  T2. companion object 暴露 VOICE_LISTEN_TIMEOUT_MS = 15_000L
      （AI-MOB-APK-003：由 8_000L 上调）；
  T3. startListening 启动 listenTimeoutJob（含 delay 调用）；
  T4. startListening 超时分支会 destroy engine 并写 error="识别超时"；
  T5. stopListening 取消 listenTimeoutJob；
  T6. engineListener.onPartial / onResult / onError 都取消 listenTimeoutJob；
  T7. onCleared 取消 listenTimeoutJob；
  T8. ViewModel 不再直接 import android.speech.*（已下放给 AndroidVoiceSttEngine）；
  T9. AndroidVoiceSttEngine 内 onError 保留 ERROR_NETWORK / ERROR_SERVER /
      ERROR_CLIENT / ERROR_TOO_MANY_REQUESTS 四个细分分支。

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_003_voice_listen_timeout.py -xvs --noconftest
"""
from __future__ import annotations

import re
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
VOICE_VM = VOICE_DIR / "VoiceCommandViewModel.kt"
ANDROID_ENGINE = VOICE_DIR / "AndroidVoiceSttEngine.kt"

# AI-MOB-APK-003：兜底超时阈值（毫秒）。真机一句完整指令的云端 ASR 往返
# 常超过 8 秒，8s 会被用户感知为「一直超时」，故上调为 15 秒。
VOICE_LISTEN_TIMEOUT_MS = "15000"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _extract_function(src: str, signature: str) -> str:
    """通过 brace 计数提取 signature 之后第一个完整函数体。"""
    idx = src.find(signature)
    assert idx != -1, f"找不到 {signature}"
    brace_open = src.find("{", idx)
    assert brace_open != -1, f"{signature} 后找不到 '{{'"
    depth = 1
    i = brace_open + 1
    while i < len(src) and depth > 0:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"{signature} 括号不匹配"
    return src[brace_open + 1 : i - 1]


# ---------- ViewModel 层断言 ----------

def test_t1_listen_timeout_job_field() -> None:
    src = _read(VOICE_VM)
    assert re.search(r"private\s+var\s+listenTimeoutJob\s*:\s*Job\?\s*=", src), \
        "VoiceCommandViewModel 必须有 private var listenTimeoutJob: Job? 字段"


def test_t2_timeout_constant() -> None:
    src = _read(VOICE_VM)
    m = re.search(r"VOICE_LISTEN_TIMEOUT_MS\s*=\s*(\d+_?\d*)L", src)
    assert m, "必须定义 VOICE_LISTEN_TIMEOUT_MS 常量"
    raw = m.group(1).replace("_", "")
    assert raw == VOICE_LISTEN_TIMEOUT_MS, \
        f"VOICE_LISTEN_TIMEOUT_MS 必须 = {VOICE_LISTEN_TIMEOUT_MS}L（毫秒），实际={raw}"


def test_t2b_timeout_not_regressed_below_original() -> None:
    """AI-MOB-APK-003 门禁：阈值不得被回退到 8 秒以下（避免「一直超时」复发）。"""
    src = _read(VOICE_VM)
    m = re.search(r"VOICE_LISTEN_TIMEOUT_MS\s*=\s*(\d+_?\d*)L", src)
    assert m, "必须定义 VOICE_LISTEN_TIMEOUT_MS 常量"
    value = int(m.group(1).replace("_", ""))
    assert value >= 15000, \
        f"兜底超时不得回退到 15 秒以下（现场反馈 8 秒过小），实际={value}"


def test_t3_start_listening_launches_timeout_job() -> None:
    src = _read(VOICE_VM)
    body = _extract_function(src, "fun startListening(")
    assert "listenTimeoutJob?.cancel()" in body, "startListening 必须先取消旧 Job"
    assert "viewModelScope.launch" in body, "startListening 必须用 viewModelScope 启动超时 Job"
    # AI-MOB-APK-004：超时 Job 改为每秒 tick 的倒计时循环（总时长仍为
    # VOICE_LISTEN_TIMEOUT_MS），并在 UI 上显示剩余秒数。
    assert "val totalSeconds = VOICE_LISTEN_TIMEOUT_MS / 1000L" in body, \
        f"startListening 内的 Job 总时长必须仍为 {int(VOICE_LISTEN_TIMEOUT_MS) // 1000} 秒"
    assert "downTo 1" in body, "startListening 必须保留倒计时循环（downTo 1）"
    assert "剩余 $remaining 秒" in body, "倒计时必须把剩余秒数写入 UI message"
    assert "识别超时" in body, "startListening 内的 Job 超时分支必须写识别超时提示"


def test_t4_timeout_destroys_engine() -> None:
    src = _read(VOICE_VM)
    body = _extract_function(src, "fun startListening(")
    # 重构后超时分支走 VoiceSttEngine.stop / destroy，不再直接调 recognizer
    assert "alive.stop()" in body or "alive?.stop()" in body, \
        "超时分支需 stop engine"
    assert "alive.destroy()" in body or "alive?.destroy()" in body, \
        "超时分支需 destroy engine"
    assert "isListening = false" in body, "超时后必须把 isListening 改为 false"


def test_t5_stop_listening_cancels_job() -> None:
    src = _read(VOICE_VM)
    body = _extract_function(src, "fun stopListening(")
    assert "listenTimeoutJob?.cancel()" in body, "stopListening 必须取消 listenTimeoutJob"
    assert "listenTimeoutJob = null" in body, "stopListening 必须把 listenTimeoutJob 置 null"


def test_t6_engine_listener_cancels_job() -> None:
    """重构后由 engineListener.onPartial/onResult/onError 三个回调统一取消 Job。"""
    src = _read(VOICE_VM)
    listener_block = _extract_function(src, "private val engineListener =")
    for name in ("override fun onPartial(", "override fun onResult(", "override fun onError("):
        body = _extract_function(listener_block, name)
        assert "listenTimeoutJob?.cancel()" in body, \
            f"engineListener.{name.split('(')[0].split()[-1]} 必须取消 listenTimeoutJob"
        assert "listenTimeoutJob = null" in body, \
            f"engineListener.{name.split('(')[0].split()[-1]} 必须把 listenTimeoutJob 置 null"


def test_t7_on_cleared_cancels_job() -> None:
    src = _read(VOICE_VM)
    body = _extract_function(src, "override fun onCleared(")
    assert "listenTimeoutJob?.cancel()" in body, "onCleared 必须取消 listenTimeoutJob"


# ---------- 重构后 ViewModel 与 Engine 分层断言 ----------

def test_t8_viewmodel_does_not_import_android_speech() -> None:
    """SpeechRecognizer 已被下放到 AndroidVoiceSttEngine，ViewModel 不应再直接依赖。"""
    src = _read(VOICE_VM)
    assert "import android.speech" not in src, \
        "VoiceCommandViewModel 不应直接 import android.speech.*（已下放到 AndroidVoiceSttEngine）"
    assert "SpeechRecognizer" not in src, \
        "VoiceCommandViewModel 不应再出现 SpeechRecognizer 引用"


def test_t9_android_engine_keeps_four_error_branches() -> None:
    src = _read(ANDROID_ENGINE)
    body = _extract_function(src, "private fun mapError(")
    for branch in (
        "SpeechRecognizer.ERROR_NETWORK",
        "SpeechRecognizer.ERROR_SERVER",
        "SpeechRecognizer.ERROR_CLIENT",
        "SpeechRecognizer.ERROR_TOO_MANY_REQUESTS",
    ):
        assert branch in body, f"AndroidVoiceSttEngine.mapError 缺失 {branch} 分支"
