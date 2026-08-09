# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-003 回归测试：手机 WMS 语音功能卡在"正在聆听"

根因：
  app/android-native-wms/.../ui/viewmodel/voice/VoiceCommandViewModel.kt
  在国内 / 无 Google 服务的 Android 设备上，SpeechRecognizer 可能既不回调
  onBeginningOfSpeech 也不回调 onError，UI 永远停在"正在聆听，请说出指令…"
  初始 message，没有退出路径。onError 也没细分 ERROR_NETWORK / ERROR_SERVER /
  ERROR_CLIENT 等关键错误码。

修复：
  - 引入 listenTimeoutJob：startListening 启动 8 秒兜底超时；
  - stopListening / dispatchResults / onError 三个出口取消该 Job；
  - onBeginningOfSpeech 也取消 Job（用户开始说话 = recognizer 工作正常）；
  - 超时后主动 destroy recognizer 并写入 error="识别超时，请重试"；
  - onError 新增 ERROR_NETWORK / ERROR_NETWORK_TIMEOUT / ERROR_SERVER /
    ERROR_CLIENT / ERROR_TOO_MANY_REQUESTS 五个细分提示。

具体断言：
  T1. import 含 kotlinx.coroutines.{Job, delay}；
  T2. 类内含私有 listenTimeoutJob: Job? 字段；
  T3. companion object 暴露 VOICE_LISTEN_TIMEOUT_MS = 8_000L；
  T4. startListening 内启动 listenTimeoutJob（含 delay 调用）；
  T5. startListening 内超时分支会 destroy recognizer 并写 error；
  T6. stopListening 内取消 listenTimeoutJob；
  T7. dispatchResults 内取消 listenTimeoutJob；
  T8. onError 内取消 listenTimeoutJob；
  T9. onBeginningOfSpeech 内取消 listenTimeoutJob；
  T10. onError 内包含 ERROR_NETWORK / ERROR_SERVER / ERROR_CLIENT 三个分支。

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_003_voice_listen_timeout.py -xvs --noconftest
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_VM = (
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
    / "VoiceCommandViewModel.kt"
)


def _read() -> str:
    assert VOICE_VM.is_file(), f"missing {VOICE_VM}"
    return VOICE_VM.read_text(encoding="utf-8")


def test_t1_imports_job_and_delay() -> None:
    src = _read()
    assert "import kotlinx.coroutines.Job" in src, "必须 import kotlinx.coroutines.Job"
    assert "import kotlinx.coroutines.delay" in src, "必须 import kotlinx.coroutines.delay"


def test_t2_listen_timeout_job_field() -> None:
    src = _read()
    assert re.search(r"private\s+var\s+listenTimeoutJob\s*:\s*Job\?\s*=", src), \
        "VoiceCommandViewModel 必须有 private var listenTimeoutJob: Job? 字段"


def test_t3_timeout_constant() -> None:
    src = _read()
    m = re.search(r"VOICE_LISTEN_TIMEOUT_MS\s*=\s*(\d+_?\d*)L", src)
    assert m, "必须定义 VOICE_LISTEN_TIMEOUT_MS 常量"
    raw = m.group(1).replace("_", "")
    assert raw == "8000", f"VOICE_LISTEN_TIMEOUT_MS 必须 = 8000L（毫秒），实际={raw}"


def _extract_function(src: str, signature: str) -> str:
    """通过 brace 计数提取 signature 之后第一个完整函数体。"""
    idx = src.find(signature)
    assert idx != -1, f"找不到 {signature}"
    # 找到 signature 之后的第一个 '{'
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


def test_t4_start_listening_launches_timeout_job() -> None:
    src = _read()
    body = _extract_function(src, "fun startListening(")
    assert "listenTimeoutJob?.cancel()" in body, "startListening 必须先取消旧 Job"
    assert "viewModelScope.launch" in body, "startListening 必须用 viewModelScope 启动超时 Job"
    assert "delay(VOICE_LISTEN_TIMEOUT_MS)" in body, "startListening 内的 Job 必须 delay 8 秒"
    assert "识别超时" in body, "startListening 内的 Job 超时分支必须写识别超时提示"


def test_t5_timeout_destroys_recognizer() -> None:
    src = _read()
    body = _extract_function(src, "fun startListening(")
    # 超时分支必须 stopListening / cancel / destroy recognizer，并把 isListening 改为 false
    assert "stopListening()" in body, "超时分支需 stopListening"
    assert "cancel()" in body, "超时分支需 cancel recognizer"
    assert "destroy()" in body, "超时分支需 destroy recognizer"
    assert "isListening = false" in body, "超时后必须把 isListening 改为 false"


def test_t6_stop_listening_cancels_job() -> None:
    src = _read()
    body = _extract_function(src, "fun stopListening(")
    assert "listenTimeoutJob?.cancel()" in body, "stopListening 必须取消 listenTimeoutJob"
    assert "listenTimeoutJob = null" in body, "stopListening 必须把 listenTimeoutJob 置 null"


def test_t7_dispatch_results_cancels_job() -> None:
    src = _read()
    body = _extract_function(src, "private fun dispatchResults(")
    assert "listenTimeoutJob?.cancel()" in body, "dispatchResults 必须取消 listenTimeoutJob"
    assert "listenTimeoutJob = null" in body, "dispatchResults 必须把 listenTimeoutJob 置 null"


def test_t8_on_error_cancels_job() -> None:
    src = _read()
    body = _extract_function(src, "override fun onError(")
    assert "listenTimeoutJob?.cancel()" in body, "onError 必须取消 listenTimeoutJob"
    assert "listenTimeoutJob = null" in body, "onError 必须把 listenTimeoutJob 置 null"


def test_t9_on_beginning_of_speech_cancels_job() -> None:
    src = _read()
    body = _extract_function(src, "override fun onBeginningOfSpeech(")
    assert "listenTimeoutJob?.cancel()" in body, "onBeginningOfSpeech 必须取消 listenTimeoutJob（用户开始说话 = 识别器正常）"
    assert "listenTimeoutJob = null" in body, "onBeginningOfSpeech 必须把 listenTimeoutJob 置 null"


def test_t10_on_error_has_three_new_branches() -> None:
    src = _read()
    body = _extract_function(src, "override fun onError(")
    # 三个新分支
    assert "ERROR_NETWORK ->" in body or "ERROR_NETWORK_TIMEOUT ->" in body, \
        "onError 必须新增 ERROR_NETWORK 系列分支"
    assert "ERROR_SERVER ->" in body, "onError 必须新增 ERROR_SERVER 分支"
    assert "ERROR_CLIENT ->" in body, "onError 必须新增 ERROR_CLIENT 分支"


def test_t11_on_cleared_cancels_job() -> None:
    src = _read()
    body = _extract_function(src, "override fun onCleared(")
    assert "listenTimeoutJob?.cancel()" in body, "onCleared 必须取消 listenTimeoutJob"


def test_t12_no_duplicate_error_recognizer_busy() -> None:
    """修复时容易重复注册 ERROR_RECOGNIZER_BUSY 分支，这里兜底检查。"""
    src = _read()
    busy_count = src.count("ERROR_RECOGNIZER_BUSY ->")
    assert busy_count <= 1, f"ERROR_RECOGNIZER_BUSY 分支只能出现 1 次，实际 {busy_count} 次"
