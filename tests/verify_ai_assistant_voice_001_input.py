# -*- coding: utf-8 -*-
"""AI-ASSISTANT-VOICE-001 回归：App AI 助手聊天页语音输入（静态契约）。

背景：AI 助手聊天页（AI-ASSISTANT-MOBILE-001）此前只有文本输入。本次新增
语音输入——复用语音指令链的 VoiceSttEngine 三级引擎回退（云 ASR → sherpa
本地 → Android 系统识别），识别文本回填输入框，不自动发送。

关键设计（本文件断言这些契约不被破坏）：
1. AssistantVoiceInputViewModel 是**纯文本输出**链路：识别结果经
   recognizedText SharedFlow 吐出，不解析指令、不导航、不自动发送
   （区别于 VoiceCommandViewModel 的指令链）。
2. 引擎复用 VoiceSttEngineFactory / VoiceSttEngineRegistry 抽象，
   不直接 new 具体引擎（与指令链同构，测试可注入 mock 工厂）。
3. 识别文本过 correctVoiceAsrText 领域词纠正（「饮料→领料」等同口径）。
4. 8 秒兜底超时 + onCleared 释放引擎（防国内设备静默挂起 + 麦克风泄漏）。
5. UI 层：麦克风按钮 + RECORD_AUDIO 权限申请 + 聆听弹窗 + 文本回填输入框。

使用方法：
  cd /workspace && python -m pytest tests/verify_ai_assistant_voice_001_input.py -xvs
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
MANIFEST = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "AndroidManifest.xml"
VOICE_VM = APP_ROOT / "ui" / "viewmodel" / "ai" / "AssistantVoiceInputViewModel.kt"
CHAT_SCREEN = APP_ROOT / "ui" / "screens" / "AssistantChatScreen.kt"
NAV_GRAPH = APP_ROOT / "ui" / "navigation" / "NavGraph.kt"
COMMAND_VM = APP_ROOT / "ui" / "viewmodel" / "voice" / "VoiceCommandViewModel.kt"


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


# ---------- ViewModel：纯文本输出链路 ----------

def test_voice_vm_exists_and_pure_text_output() -> None:
    """识别结果走 recognizedText SharedFlow，纯文本输出不解析指令。"""
    src = _read(VOICE_VM)
    # 纯文本输出：SharedFlow<String> + emit
    assert "val recognizedText: SharedFlow<String>" in src
    assert "_recognizedText.emit(text)" in src
    # 不做指令解析/导航：不引用指令链的解析与路由符号
    for forbidden in ("parseCommand", "resolveCommand", "detectOutboundDraft",
                      "understandVoiceIntent", "VoiceCommand."):
        assert forbidden not in src, f"语音输入链路不应包含指令解析符号 {forbidden}"


def test_voice_vm_reuses_stt_engine_abstraction() -> None:
    """引擎经 VoiceSttEngineFactory 注入（与指令链同构），不直接 new 具体引擎。"""
    src = _read(VOICE_VM)
    assert "engineFactory: VoiceSttEngineFactory" in src
    assert "engineFactory.create(context.applicationContext)" in src
    for forbidden in ("CloudAsrVoiceSttEngine(", "SherpaVoiceSttEngine(", "AndroidVoiceSttEngine("):
        assert forbidden not in src, f"不应直接构造具体引擎 {forbidden}"
    # 默认构造走 DefaultEngineFactory（三级回退）
    assert "this(application, DefaultEngineFactory)" in src


def test_voice_vm_applies_domain_correction() -> None:
    """识别文本过 correctVoiceAsrText 领域词纠正（同指令链口径）。"""
    src = _read(VOICE_VM)
    assert "correctVoiceAsrText(" in src
    # 纠正表在指令链文件中定义（单一真相源，双端不重复维护）
    cmd_src = _read(COMMAND_VM)
    assert "fun correctVoiceAsrText" in cmd_src


def test_voice_vm_timeout_and_lifecycle() -> None:
    """8 秒兜底超时 + 四个出口取消 + onCleared 释放引擎。"""
    src = _read(VOICE_VM)
    assert "VOICE_LISTEN_TIMEOUT_MS = 8_000L" in src
    # 超时出口：stopListening / onResult / onError / onCleared
    assert "listenTimeoutJob?.cancel()" in src
    assert "override fun onCleared()" in src
    assert "engine?.destroy()" in src


def test_voice_vm_engine_unavailable_and_error_detail() -> None:
    """引擎不可用即报 EngineUnavailable；错误 detail 优先于笼统文案且截断。"""
    src = _read(VOICE_VM)
    assert "SttError.EngineUnavailable.toUserMessage()" in src
    assert "MAX_ERROR_DETAIL_LEN" in src
    assert "take(MAX_ERROR_DETAIL_LEN)" in src


# ---------- UI 层：麦克风按钮 + 权限 + 弹窗 + 回填 ----------

def test_chat_screen_has_mic_button_and_permission_flow() -> None:
    """输入区麦克风按钮 + RECORD_AUDIO 权限申请 + 拒绝提示。"""
    src = _read(CHAT_SCREEN)
    assert "Manifest.permission.RECORD_AUDIO" in src
    assert "ActivityResultContracts.RequestPermission()" in src
    assert "需要麦克风权限才能使用语音输入" in src
    assert 'Icons.Outlined.Mic' in src
    assert 'contentDescription = "语音输入"' in src


def test_chat_screen_listening_dialog_and_partial() -> None:
    """聆听中弹窗：倒计时 message + 实时 partial 文本展示。"""
    src = _read(CHAT_SCREEN)
    assert "voiceState.isListening" in src
    assert "voiceState.partialText" in src
    assert "AlertDialog(" in src


def test_chat_screen_text_backfill_not_autosend() -> None:
    """识别文本回填输入框（追加式），不自动调用 send。"""
    src = _read(CHAT_SCREEN)
    assert "voiceViewModel.recognizedText.collect" in src
    # 回填是追加式：保留已输入文本，便于连续口述分段补充
    assert 'input = if (input.isBlank()) text else "$input$text"' in src


def test_chat_screen_wires_voice_view_model() -> None:
    """AssistantChatScreen 签名带 voiceViewModel 并收集其状态。"""
    src = _read(CHAT_SCREEN)
    assert "voiceViewModel: AssistantVoiceInputViewModel," in src
    assert "voiceViewModel.uiState.collectAsState()" in src


def test_nav_graph_provides_voice_view_model() -> None:
    """NavGraph 为聊天页创建 AssistantVoiceInputViewModel（VM 惰性创建惯例）。"""
    src = _read(NAV_GRAPH)
    assert "AssistantVoiceInputViewModel = viewModel()" in src
    assert "voiceViewModel = assistantVoiceViewModel" in src


def test_manifest_declares_record_audio() -> None:
    """AndroidManifest 已声明 RECORD_AUDIO（语音指令链时代已具备，防回归）。"""
    src = _read(MANIFEST)
    assert "android.permission.RECORD_AUDIO" in src
