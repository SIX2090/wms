# -*- coding: utf-8 -*-
"""AI-VOICE-OUT-F01 静态契约（Android 数据层）：语音建单接入。

配套后端：POST /api/mobile/voice_out_draft（见 tests/verify_mobile_voice_out_api.py）

验收：
- T1 API 契约：端点路径、幂等头、请求/响应类型与后端字段一致
- T2 Repository：经 safeCall 统一错误映射 + newRequestId 幂等键
- T3 DTO 字段：dry_run/material_code/quantity 与后端 pydantic 模型对齐
- T4 响应字段：preview 阶段（match_status/matches/strategies_tried）
- T5 响应字段：created 阶段（order_no/items/status）
- T6 候选物料含 score/strategy（支撑"按相似度排序 + 向用户解释"）
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms"
API = ANDROID / "data/api/WmsApiService.kt"
REPO = ANDROID / "data/repository/WmsRepository.kt"
MODELS = ANDROID / "data/model/VoiceOutDraftModels.kt"
BACKEND = ROOT / "app/routes/native_api.py"


def test_t1_api_endpoint_contract():
    api = API.read_text(encoding="utf-8")
    assert '@POST("api/mobile/voice_out_draft")' in api, "端点路径必须与后端一致"
    assert "suspend fun voiceOutDraft(" in api
    assert '@Header("X-Idempotency-Key") requestId: String' in api, "必须带幂等头"
    assert "VoiceOutDraftRequest" in api
    assert "ApiEnvelope<VoiceOutDraftResult>" in api

    # 后端确实注册了该端点
    backend = BACKEND.read_text(encoding="utf-8")
    assert "'/api/mobile/voice_out_draft'" in backend
    assert "mobile_api_idempotent('voice_out_draft')" in backend


def test_t2_repository_uses_safe_call_and_idempotency():
    repo = REPO.read_text(encoding="utf-8")
    idx = repo.index("createVoiceOutDraft")
    body = repo[idx:idx + 400]
    assert "api.voiceOutDraft(newRequestId()" in body, "必须显式传幂等键"
    assert "safeCall" in body, "必须经 safeCall 统一错误映射"


def test_t3_request_dto_matches_backend_schema():
    models = MODELS.read_text(encoding="utf-8")
    assert "data class VoiceOutDraftRequest" in models
    # 字段名必须与后端 pydantic 模型对齐
    assert "val text: String" in models
    assert '@SerializedName("warehouse_code")' in models
    assert "val picker: String? = null" in models
    assert '@SerializedName("dry_run") val dryRun: Boolean = true' in models
    assert '@SerializedName("material_code") val materialCode: String? = null' in models
    assert "val quantity: Double? = null" in models

    backend = BACKEND.read_text(encoding="utf-8")
    for field in ("text", "warehouse", "warehouse_code", "picker",
                  "dry_run", "material_code", "quantity"):
        assert field in backend, f"后端缺少字段 {field}"


def test_t4_preview_stage_fields():
    models = MODELS.read_text(encoding="utf-8")
    idx = models.index("data class VoiceOutDraftResult")
    body = models[idx:]
    for field in ('"heard_text"', '"normalized_text"', '"match_status"',
                  '"strategies_tried"'):
        assert field in body, f"缺少 preview 字段映射 {field}"
    assert "val matches: List<VoiceMaterialMatch>?" in body
    assert "val degraded: Boolean?" in body


def test_t5_created_stage_fields():
    models = MODELS.read_text(encoding="utf-8")
    idx = models.index("data class VoiceOutDraftResult")
    body = models[idx:]
    assert '"order_id"' in body
    assert '"order_no"' in body
    assert "val status: String?" in body
    assert "val items: List<VoiceOutDraftItem>?" in body


def test_t6_match_carries_score_and_strategy():
    models = MODELS.read_text(encoding="utf-8")
    idx = models.index("data class VoiceMaterialMatch")
    body = models[idx:models.index("data class VoiceOutDraftItem")]
    assert "val score: Int?" in body, "候选必须带相似度，支撑排序"
    assert "val strategy: String?" in body, "候选必须带命中策略，支撑向用户解释"
    assert "val code: String?" in body
    assert "val spec: String?" in body
