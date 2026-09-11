# -*- coding: utf-8 -*-
"""AI-VOICE-OUT-F01 静态契约（Android）：parseCommand 建单意图分支。

核心要求：说「领8*25螺丝 1000个」必须解析成建单意图（CreateOutboundDraft），
而不是只跳转出库页；同时「领料」「出库」这类纯导航语必须保持原行为（无回归）。

验收：
- T1 VoiceCommand 新增 CreateOutboundDraft 子类，携带语音原文
- T2 建单意图判定必须**排在**「领料/出库」导航分支之前（否则永远被抢走）
- T3 判定条件：含建单动词 且（含数字 或 残余物料词 ≥2 字）
- T4 剥离动词后按长度降序（先剥「领料单」再剥「领」，避免残留）
- T5 detectOutboundDraft 辅助函数存在且为 private
- T6 既有导航分支完整保留（无回归）
- T7 逻辑等价性：用 Python 复刻判定算法，验证关键用例分类正确
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
VM = ANDROID / "ui/viewmodel/voice/VoiceCommandViewModel.kt"


def _src():
    return VM.read_text(encoding="utf-8")


# ── T1 新增指令类型 ─────────────────────────────────────────────

def test_t1_create_outbound_draft_command_exists():
    src = _src()
    assert "data class CreateOutboundDraft(" in src
    assert "val rawText: String" in src
    assert "val keywordHint: String" in src
    # 必须是 VoiceCommand 的子类
    idx = src.index("data class CreateOutboundDraft(")
    assert "VoiceCommand(" in src[idx:idx + 400]


# ── T2 优先级：建单必须在导航之前 ───────────────────────────────

def test_t2_draft_detection_precedes_navigation_branches():
    src = _src()
    fn_start = src.index("fun parseCommand(")
    fn_end = src.index("private val VOICE_DRAFT_VERBS")
    body = src[fn_start:fn_end]

    draft_pos = body.index("detectOutboundDraft(t)")
    lingliao_pos = body.index('lt.contains("领料")')
    chuku_pos = body.index('lt.contains("出库")')

    assert draft_pos < lingliao_pos, "建单判定必须在「领料」导航之前"
    assert draft_pos < chuku_pos, "建单判定必须在「出库」导航之前"


# ── T3 判定条件 ─────────────────────────────────────────────────

def test_t3_detection_condition():
    src = _src()
    idx = src.index("private fun detectOutboundDraft")
    body = src[idx:idx + 1600]
    assert "VOICE_DRAFT_VERBS.any" in body, "必须检查建单动词"
    assert "hasNumber" in body, "必须检查是否含数字"
    assert "residual.length < 2" in body, "残余物料词不足 2 字不判建单"


# ── T4 动词剥离顺序 ─────────────────────────────────────────────

def test_t4_verbs_stripped_longest_first():
    src = _src()
    idx = src.index("private fun detectOutboundDraft")
    body = src[idx:idx + 1600]
    assert "sortedByDescending { it.length }" in body, \
        "必须先剥长词（领料单）再剥短词（领），避免残留"


# ── T5 辅助函数 ─────────────────────────────────────────────────

def test_t5_detection_helper_is_private():
    src = _src()
    assert "private fun detectOutboundDraft(" in src
    assert "private val VOICE_DRAFT_VERBS" in src
    # 建单动词表必须含领料族与出库族
    for verb in ("领料单", "出库单", "领料", "出库", "领"):
        assert f'"{verb}"' in src, f"建单动词表缺少 {verb}"


# ── T6 既有导航分支无回归 ───────────────────────────────────────

def test_t6_navigation_branches_preserved():
    src = _src()
    for branch in (
        'lt.contains("识物盘点")',
        'lt.contains("入库")',
        'lt.contains("领料")',
        'lt.contains("出库")',
        'lt.contains("期初")',
        'lt.contains("盘点")',
        'lt.contains("库存")',
        'lt.contains("首页")',
        'lt.contains("返回")',
        'lt.contains("退出")',
    ):
        assert branch in src, f"导航分支丢失（回归）：{branch}"
    assert "VoiceCommand.Navigate(Screen.Outbound)" in src
    assert "VoiceCommand.GoBack" in src
    assert "VoiceCommand.GoHome" in src
    assert "VoiceCommand.Logout" in src
    assert "VoiceCommand.Unrecognized" in src


# ── T7 逻辑等价性验证 ───────────────────────────────────────────

# 与 Kotlin detectOutboundDraft 等价的 Python 复刻
_VERBS = ["领料单", "出库单", "领用单", "领料", "领用", "领取",
          "出库", "领", "出", "拿", "发", "要"]
_SEPS = set("乘叉杠×xX*·-")


def _detect(text):
    if not any(v in text for v in _VERBS):
        return None
    stem = text
    for v in sorted(_VERBS, key=len, reverse=True):
        stem = stem.replace(v, " ")
    has_num = any(c.isdigit() for c in stem)
    residual = "".join(
        c for c in stem if not (c.isdigit() or c in _SEPS)
    ).replace(" ", "").strip()
    if not has_num and len(residual) < 2:
        return None
    return residual


def test_t7_logic_equivalence_draft_intent():
    """这些必须判定为建单意图。"""
    for text in (
        "领8*25螺丝 1000个",
        "领8*25螺丝",
        "领内六角螺丝 100个",
        "要轴承6204 10个",
        "出8*25螺丝 30个",
        "领M8*25螺栓 200套",
    ):
        assert _detect(text) is not None, f"{text} 应判定为建单意图"


def test_t7b_logic_equivalence_navigation_intent():
    """这些必须保持导航行为（无回归）。"""
    for text in ("领料", "出库", "领料出库", "查库存", "盘点", "返回", "首页", "入库", "识物"):
        assert _detect(text) is None, f"{text} 应保持导航，不该被判成建单"
