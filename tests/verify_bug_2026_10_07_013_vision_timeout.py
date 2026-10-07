# -*- coding: utf-8 -*-
"""BUG-2026-10-07-013：识物/单据 OCR 走视觉 LLM 却被 App 30s 超时掐断。

背景：
  AUDIT-2026-10-07-P1 给 assistant_chat / voice_intent / voice_out_draft
  三条 LLM 路径加了 120s readTimeout 白名单，但同样走 _ai_call_llm_vision
  的两条视觉路径被漏了：
    - mobile/api/recognize_material（拍照识物）
    - api/ai/document_ocr（单据 OCR）
  后端视觉超时是 max(ai_llm_timeout_seconds, 60) = 60s+（app.py _ai_call_llm_vision），
  大图视觉识别常超 30s → App 默认 readTimeout=30s 先掐断 →
  用户只看到「网络错误: timeout」，以为识物功能全坏（用户实测反馈：识物根本无法用）。

修复：
  1. RetrofitClient.llmTimeoutInterceptor 白名单补上两条视觉路径。
  2. mobile_recognize_material 失败分支补 warning 日志（仅 user/size/reason，
     不含图片与供应商原始响应）——此前识物失败不留任何痕迹，现场排障只能靠猜。

本文件为静态契约测试，防止回归。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RETROFIT = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/api/RetrofitClient.kt"
MOBILE_ROUTES = ROOT / "app/routes/mobile.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_bug_013_files_exist():
    for p in (RETROFIT, MOBILE_ROUTES):
        assert p.exists(), f"缺文件: {p}"


# ── 1. App 端：视觉路径进 LLM 超时白名单 ────────────────────────────

def test_bug_013_recognize_material_in_llm_timeout_whitelist():
    """识物路径必须命中 120s 白名单（endsWith 匹配，兼容 base_url 前缀差异）。"""
    src = _read(RETROFIT)
    assert 'path.endsWith("/api/recognize_material")' in src, \
        "BUG-013：recognize_material 未进 llmTimeoutInterceptor 白名单"


def test_bug_013_document_ocr_in_llm_timeout_whitelist():
    """单据 OCR 路径必须命中 120s 白名单。"""
    src = _read(RETROFIT)
    assert 'path.endsWith("/api/ai/document_ocr")' in src, \
        "BUG-013：document_ocr 未进 llmTimeoutInterceptor 白名单"


def test_bug_013_existing_whitelist_kept():
    """P1 原有三条路径不得丢失（防止改一处丢一处）。"""
    src = _read(RETROFIT)
    for path in (
        "/api/mobile/assistant_chat",
        "/api/mobile/voice_intent",
        "/api/mobile/voice_out_draft",
    ):
        assert f'path.endsWith("{path}")' in src, f"BUG-013：{path} 从白名单丢失"


def test_bug_013_timeout_value_unchanged():
    """白名单超时仍为 120s 且常量为 Int（withReadTimeout 签名要求）。"""
    src = _read(RETROFIT)
    assert "LLM_READ_TIMEOUT_SECONDS: Int = 120" in src, "BUG-013：超时常量被改动"


# ── 2. 后端：识物失败必须留痕 ──────────────────────────────────────

def test_bug_013_recognize_failure_logged():
    """识物 LLM 失败分支必须打 warning（此前完全无日志，排障盲区）。"""
    src = _read(MOBILE_ROUTES)
    assert "识物失败 user=" in src, "BUG-013：识物失败分支缺少 warning 日志"
    # 日志必须截断 error，防止超长供应商响应刷爆日志
    assert "error[:200]" in src, "BUG-013：识物失败日志未截断 error 长度"


def test_bug_013_no_image_data_in_log():
    """新日志不得包含图片 base64 / data_url（敏感信息不入日志）。"""
    src = _read(MOBILE_ROUTES)
    assert "data_url, %s" not in src and "img_data, %s" not in src, \
        "BUG-013：识物日志疑似包含图片数据"


def test_bug_013_syntax_guard():
    """mobile.py 仍是合法 Python（防止注入破坏路由）。"""
    import ast
    ast.parse(src := _read(MOBILE_ROUTES))
    # 识物端点仍在
    assert "def mobile_recognize_material" in src
    # 限流与 10MB 上限仍在（防止重构时丢防护）
    assert "_recognize_rate_limited" in src
    assert "10 * 1024 * 1024" in src
