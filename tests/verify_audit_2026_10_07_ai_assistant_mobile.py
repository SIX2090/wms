# -*- coding: utf-8 -*-
"""AUDIT-2026-10-07-P1~P6：手机端 AI 助手审计修复的静态契约测试。

审计发现的 6 个问题（P=Priority）：
  P1 AI 请求超时链路断裂——App readTimeout 30s < 后端 LLM 超时上限 60s+
  P2 聊天页与全局悬浮语音球双麦克风冲突
  P3 assistantChat 缺 ensureSession 冷启动竞态
  P4 识别超时文案矛盾（"8 秒内说出" vs "说完停顿即自动识别"）
  P5 清空对话无确认弹窗，误触丢整段对话
  P6 发送失败消息不退回输入框

修复方式与对应文件：
  P1 RetrofitClient.kt——llmTimeoutInterceptor + withReadTimeout(120s)
  P2 NavGraph.kt——currentRoute == AssistantChat.route 时隐藏悬浮层
  P3 WmsRepository.kt——assistantChat 先 ensureSession()
  P4 AssistantVoiceInputViewModel.kt——统一为「剩余 N 秒」倒计时文案
  P5 AssistantChatScreen.kt——showClearConfirm 确认弹窗
  P6 AssistantChatViewModel.kt + Screen——failedDraft 退回输入框
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RETROFIT = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/api/RetrofitClient.kt"
NAVGRAPH = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/navigation/NavGraph.kt"
REPO = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"
VOICE_VM = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/ai/AssistantVoiceInputViewModel.kt"
CHAT_VM = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/ai/AssistantChatViewModel.kt"
CHAT_SCREEN = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/AssistantChatScreen.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_files_exist():
    for p in (RETROFIT, NAVGRAPH, REPO, VOICE_VM, CHAT_VM, CHAT_SCREEN):
        assert p.exists(), f"缺文件: {p}"


# ── P1：LLM 长请求独立超时 ──────────────────────────────────────────

def test_p1_llm_timeout_interceptor_exists():
    """拦截器存在且用 withReadTimeout（不是只加 header 的假实现）。"""
    src = _read(RETROFIT)
    assert "llmTimeoutInterceptor" in src, "P1：llmTimeoutInterceptor 不存在"
    assert "withReadTimeout" in src, "P1：未使用 withReadTimeout"


def test_p1_llm_paths_covered():
    """三条 LLM 路径都在拦截器覆盖列表里。"""
    src = _read(RETROFIT)
    for path in (
        "/api/mobile/assistant_chat",
        "/api/mobile/voice_intent",
        "/api/mobile/voice_out_draft",
    ):
        assert f'"{path}"' in src or f'endsWith("{path}")' in src, f"P1：{path} 未覆盖"
    assert "endsWith(\"/api/mobile/assistant_chat\")" in src


def test_p1_timeout_value():
    """超时常量 120s 定义且被引用。"""
    src = _read(RETROFIT)
    assert "LLM_READ_TIMEOUT_SECONDS" in src, "P1：超时常量缺失"
    assert "120L" in src, "P1：超时值不是 120s"


def test_p1_interceptor_registered():
    """拦截器注册进 OkHttpClient（挂在 auth 之后、logging 之前/之后皆可）。"""
    src = _read(RETROFIT)
    assert ".addInterceptor(llmTimeoutInterceptor)" in src, "P1：拦截器未注册"
    # 原有拦截器仍在
    assert ".addInterceptor(authInterceptor)" in src


# ── P2：聊天页隐藏悬浮语音球 ────────────────────────────────────────

def test_p2_overlay_hidden_on_chat_route():
    """悬浮层条件加 currentRoute != AssistantChat.route。"""
    src = _read(NAVGRAPH)
    assert "Screen.AssistantChat.route" in src, "P2：NavGraph 未引用 AssistantChat 路由"
    assert "currentRoute != Screen.AssistantChat.route" in src, "P2：隐藏条件缺失"


# ── P3：ensureSession 兜底 ─────────────────────────────────────────

def test_p3_ensure_session_called():
    """assistantChat 在 safeCall 前调 ensureSession()。"""
    src = _read(REPO)
    marker = "suspend fun assistantChat"
    idx = src.find(marker)
    assert idx >= 0, "P3：assistantChat 函数不存在"
    body = src[idx: idx + 1200]
    assert "ensureSession()" in body, "P3：assistantChat 未调 ensureSession"
    assert body.index("ensureSession()") < body.index("safeCall"), "P3：ensureSession 应在 safeCall 前"


# ── P4：语音文案统一 ──────────────────────────────────────────────

def test_p4_contradictory_copy_removed():
    """「说完停顿即自动识别」虚假提示已删除。"""
    src = _read(VOICE_VM)
    assert "说完停顿即自动识别" not in src, "P4：虚假文案仍在"


def test_p4_countdown_copy_consistent():
    """倒计时文案与超时文案口径一致（都从常量/剩余秒数出发）。"""
    src = _read(VOICE_VM)
    assert "正在聆听（剩余 $remaining 秒）" in src, "P4：倒计时文案缺失"
    assert "识别超时：请点按麦克风后 $VOICE_LISTEN_SECONDS_TEXT 秒内说出问题" in src, "P4：超时文案缺常量引用"
    assert 'VOICE_LISTEN_SECONDS_TEXT = "8"' in src, "P4：秒数常量缺失"


# ── P5：清空确认弹窗 ──────────────────────────────────────────────

def test_p5_clear_confirm_dialog():
    """清空按钮先弹确认，不再直接 clearConversation。"""
    src = _read(CHAT_SCREEN)
    assert "showClearConfirm = true" in src, "P5：点击清空未置确认标记"
    assert "showClearConfirm = false" in src, "P5：确认弹窗无法关闭"
    # 确认后才真正清空
    assert "viewModel.clearConversation()" in src, "P5：确认回调未调 clearConversation"
    # 空列表点击不弹窗（guard 存在）
    assert "uiState.messages.isNotEmpty()" in src, "P5：空对话也弹确认"


# ── P6：失败退回输入框 ────────────────────────────────────────────

def test_p6_failed_draft_in_viewmodel():
    """UiState 增加 failedDraft；失败回调写入；有 consume 方法。"""
    src = _read(CHAT_VM)
    assert "val failedDraft: String? = null" in src, "P6：failedDraft 字段缺失"
    assert "failedDraft = trimmed" in src, "P6：失败回调未写入 draft"
    assert "fun consumeFailedDraft()" in src, "P6：consume 方法缺失"


def test_p6_screen_restores_draft():
    """Screen 收 failedDraft 回填输入框（不覆盖已输入内容）。"""
    src = _read(CHAT_SCREEN)
    assert "uiState.failedDraft" in src, "P6：Screen 未监听 failedDraft"
    assert "input.isBlank()" in src, "P6：回填未做空白保护"


if __name__ == "__main__":
    import sys
    passed = failed = 0
    for name, fn in sorted(
        (n, f) for n, f in list(globals().items())
        if n.startswith("test_") and callable(f)
    ):
        try:
            fn()
            passed += 1
            print(f"PASS {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {name}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
