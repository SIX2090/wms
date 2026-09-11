# -*- coding: utf-8 -*-
"""AI-VOICE-OUT-F01 静态契约（Android）：VoiceOutDraftViewModel 编排。

流程（两阶段协议）：
  ① 语音文本 → dry_run=true 解析+匹配
     ├─ success    → CONFIRMING（唯一命中，省用户点选）
     ├─ multiple   → NEED_CHOICE（列表点选，R5 不替用户决定）
     └─ not_found  → NOT_FOUND（展示"听成了什么+试过什么"）
  ② 用户确认 → dry_run=false 建 pending 草稿
  ③ CREATED → 导航出库页核对

验收：
- T1 阶段枚举完整（含 NEED_CHOICE / NOT_FOUND / CREATED）
- T2 两跳协议：dryRun 先 true 后 false
- T3 唯一命中自动带入 selected 并进 CONFIRMING
- T4 多命中进 NEED_CHOICE，需 chooseMaterial 才进 CONFIRMING
- T5 数量不猜：editableQuantity 为空时 createDraft 报错（R5）
- T6 仓库必填校验
- T7 只建草稿：请求 dryRun=false 且不含提交/完成动作
- T8 经 repository.createVoiceOutDraft（safeCall 链路）
- T9 诊断字段：strategiesTried / degraded 透传给 UI
- T10 CREATED 后带回 orderId/orderNo/lines 供出库页预填
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
VM = ANDROID / "ui/viewmodel/voice/VoiceOutDraftViewModel.kt"


def _src():
    return VM.read_text(encoding="utf-8")


# ── T1 阶段枚举 ─────────────────────────────────────────────────

def test_t1_stage_enum_complete():
    src = _src()
    assert "enum class VoiceDraftStage" in src
    for stage in ("IDLE", "PARSING", "NEED_CHOICE", "CONFIRMING",
                  "CREATING", "CREATED", "NOT_FOUND"):
        assert stage in src, f"缺少阶段 {stage}"


# ── T2 两跳协议 ─────────────────────────────────────────────────

def test_t2_two_phase_protocol():
    src = _src()
    parse_idx = src.index("fun parseAndMatch(")
    create_idx = src.index("fun createDraft()")
    parse_body = src[parse_idx:create_idx]
    create_body = src[create_idx:src.index("fun clearError()")]

    assert "dryRun = true" in parse_body, "第一跳必须是 dry_run=true（只解析不建单）"
    assert "dryRun = false" in create_body, "第二跳必须是 dry_run=false（建草稿）"


# ── T3 唯一命中 ─────────────────────────────────────────────────

def test_t3_unique_hit_goes_to_confirming():
    src = _src()
    assert '"success" -> base.copy(' in src
    idx = src.index('"success" -> base.copy(')
    body = src[idx:idx + 200]
    assert "VoiceDraftStage.CONFIRMING" in body
    assert "selected = matches.firstOrNull()" in body


# ── T4 多命中 ───────────────────────────────────────────────────

def test_t4_multiple_requires_user_choice():
    src = _src()
    idx = src.index('"multiple" -> base.copy(')
    body = src[idx:idx + 120]
    assert "VoiceDraftStage.NEED_CHOICE" in body, "多命中必须回退人工选择（R5）"
    # 必须有进入 CONFIRMING 的唯一通道
    assert "fun chooseMaterial(" in src


# ── T5 数量不猜 ─────────────────────────────────────────────────

def test_t5_quantity_not_guessed():
    src = _src()
    idx = src.index("fun createDraft()")
    body = src[idx:idx + 900]
    assert "editableQuantity.trim().toDoubleOrNull()" in body
    assert "qty == null || qty <= 0" in body, "数量为空或非正数必须拒绝（不猜，R5）"
    assert "请填写领料数量" in body


# ── T6 仓库必填 ─────────────────────────────────────────────────

def test_t6_warehouse_required():
    src = _src()
    idx = src.index("fun createDraft()")
    body = src[idx:idx + 1100]
    assert "请先选择仓库" in body


# ── T7 只建草稿 ─────────────────────────────────────────────────

def test_t7_draft_only_no_completion():
    src = _src()
    # 不得出现提交/完成/审核/删除等动作
    for forbidden in ("submitOutbound", "completeOrder", "deductStock",
                      "approve", "audit", "delete"):
        assert forbidden not in src, f"语音建单不得包含 {forbidden}（AI 边界）"


# ── T8 走 repository ────────────────────────────────────────────

def test_t8_uses_repository_layer():
    src = _src()
    assert src.count("repository.createVoiceOutDraft(") == 2, \
        "两跳都应经 repository（safeCall 链路）"


# ── T9 诊断字段 ─────────────────────────────────────────────────

def test_t9_diagnostics_passed_to_ui():
    src = _src()
    assert "strategiesTried = result.strategiesTried.orEmpty()" in src
    assert "degraded = result.degraded ?: false" in src
    assert "normalizedText = result.normalizedText.orEmpty()" in src


# ── T10 建单结果供预填 ──────────────────────────────────────────

def test_t10_created_result_for_prefill():
    src = _src()
    assert "createdOrderId = result.orderId" in src
    assert "createdOrderNo = result.orderNo.orEmpty()" in src
    assert "createdLines = lines" in src


# ── 附加：不复位仓库上下文 ──────────────────────────────────────

def test_reset_keeps_warehouse_context():
    src = _src()
    idx = src.index("fun reset()")
    body = src[idx:idx + 400]
    assert "warehouses = _uiState.value.warehouses" in body
    assert "selectedWarehouse = _uiState.value.selectedWarehouse" in body
