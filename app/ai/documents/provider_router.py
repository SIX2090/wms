"""AI-R05：视觉/OCR Provider 路由决策层。

# AI_TASK: AI-R05

设计目标（验收：模型路由可解释、可配置、可回滚）：
- 可解释：每次路由决策返回 RoutingDecision，含 choice + reason + evidence。
- 可配置：ProviderRouterConfig 暴露阈值与开关，运行时可注入新配置。
- 可回滚：决策记录含 config_version，可序列化审计；改回旧配置即回滚。

路由策略：
- 表格/单据图片 + 清晰度达标 → VISION_MODEL（视觉模型擅长版式识别）
- 纯文本 + 规则明确（微信发货通知等）→ DETERMINISTIC_TEXT（确定性解析，无 API 成本）
- 视觉不可用 / 全局降级标志 → FALLBACK_LOCAL（本地规则兜底）

本模块只做"决策"，不调用任何外部 Provider，不持有 API Key，符合
"日志不得泄露密钥"约束。实际调用由调用方根据 decision.choice 执行。
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ProviderChoice(str, Enum):
    """路由选择的解析通道。"""

    VISION_MODEL = 'vision_model'           # 视觉/多模态模型
    DETERMINISTIC_TEXT = 'deterministic_text'  # 确定性文本解析（无 API 成本）
    FALLBACK_LOCAL = 'fallback_local'       # 本地规则兜底


# 微信发货通知等"规则明确纯文本"的关键词（命中即优先走确定性解析）
# 例：明天发鑫达 6204轴承 100套，M8螺母 500个
WECHAT_DELIVERY_KEYWORDS = (
    '今天发', '明天发', '后天发', '上午发', '下午发', '晚上发',
    '发货', '送货', '出货', '到货', '发 ',
)

# 表格/单据类图片特征：长宽比接近 A4/票据，且非极端长条
DOCUMENT_ASPECT_RANGE = (0.4, 2.5)


@dataclass(frozen=True)
class ProviderRouterConfig:
    """路由配置（可注入、可回滚）。

    所有阈值集中在此，改配置即改路由行为；旧配置可恢复以回滚。
    """

    enable_vision_model: bool = True
    enable_deterministic_text: bool = True
    enable_fallback_local: bool = True
    # 图片清晰度低于此值不优先视觉（与 image_preprocessing.BLUR_THRESHOLD 对齐）
    vision_min_blur_score: float = 500.0
    # 全局降级开关：开启后所有图片走 FALLBACK_LOCAL（紧急回滚用）
    force_fallback: bool = False
    # 微信发货通知关键词
    deterministic_text_keywords: tuple[str, ...] = WECHAT_DELIVERY_KEYWORDS
    # 单据图片长宽比范围
    document_aspect_range: tuple[float, float] = DOCUMENT_ASPECT_RANGE

    @property
    def config_version(self) -> str:
        """配置指纹，用于审计追溯与回滚比对。"""
        payload = (
            f'{self.enable_vision_model}|{self.enable_deterministic_text}|'
            f'{self.enable_fallback_local}|{self.vision_min_blur_score}|'
            f'{self.force_fallback}|{self.deterministic_text_keywords}|'
            f'{self.document_aspect_range}'
        )
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12]


@dataclass(frozen=True)
class RoutingDecision:
    """单次路由决策结果（可解释、可序列化审计）。"""

    choice: ProviderChoice
    reason: str                          # 中文可解释原因
    evidence: dict[str, Any] = field(default_factory=dict)
    config_version: str = ''             # 关联的配置指纹，支持回滚比对

    def to_dict(self) -> dict[str, Any]:
        return {
            'choice': self.choice.value,
            'reason': self.reason,
            'evidence': dict(self.evidence),
            'config_version': self.config_version,
        }


def route_document(
    *,
    source_type: str = 'image',
    has_image: bool = False,
    image_blur_score: Optional[float] = None,
    image_aspect_ratio: Optional[float] = None,
    text_content: str = '',
    config: Optional[ProviderRouterConfig] = None,
    vision_available: bool = True,
) -> RoutingDecision:
    """根据输入特征与配置选择解析通道。

    Args:
        source_type: 输入来源（image/text/excel）
        has_image: 是否含图片
        image_blur_score: 图片清晰度（拉普拉斯方差），来自 image_preprocessing
        image_aspect_ratio: 图片长宽比
        text_content: 文本内容（纯文本输入时用于规则匹配）
        config: 路由配置，None 用默认
        vision_available: 视觉模型是否可用（系统设置/Feature Flag 综合判定）

    Returns:
        RoutingDecision：可解释的路由决策
    """
    cfg = config or ProviderRouterConfig()

    # 1. 紧急回滚：force_fallback 直接走本地兜底
    if cfg.force_fallback:
        return RoutingDecision(
            choice=ProviderChoice.FALLBACK_LOCAL,
            reason='全局降级开关已开启，所有输入走本地规则兜底',
            evidence={'trigger': 'force_fallback'},
            config_version=cfg.config_version,
        )

    # 2. 纯文本输入 + 规则明确 → 确定性解析（无 API 成本）
    if source_type == 'text' and text_content:
        if cfg.enable_deterministic_text and _is_deterministic_text(text_content, cfg):
            return RoutingDecision(
                choice=ProviderChoice.DETERMINISTIC_TEXT,
                reason='纯文本且命中微信发货通知等规则关键词，优先确定性解析（无 API 成本）',
                evidence={
                    'source_type': source_type,
                    'matched_keywords': _matched_keywords(text_content, cfg),
                },
                config_version=cfg.config_version,
            )
        # 纯文本但规则不明确，仍走确定性解析（文本无法走视觉）
        if cfg.enable_deterministic_text:
            return RoutingDecision(
                choice=ProviderChoice.DETERMINISTIC_TEXT,
                reason='纯文本输入，走确定性文本解析',
                evidence={'source_type': source_type, 'rule_matched': False},
                config_version=cfg.config_version,
            )

    # 3. 图片输入
    if has_image or source_type == 'image':
        # 视觉不可用 → 兜底
        if not vision_available or not cfg.enable_vision_model:
            if cfg.enable_fallback_local:
                return RoutingDecision(
                    choice=ProviderChoice.FALLBACK_LOCAL,
                    reason='视觉模型不可用或未启用，走本地规则兜底',
                    evidence={
                        'vision_available': vision_available,
                        'enable_vision_model': cfg.enable_vision_model,
                    },
                    config_version=cfg.config_version,
                )

        # 清晰度不达标 → 仍走视觉但记录风险（图片无确定性替代）
        blur_evidence: dict[str, Any] = {}
        if image_blur_score is not None:
            blur_evidence['blur_score'] = image_blur_score
            blur_evidence['min_required'] = cfg.vision_min_blur_score
            blur_evidence['below_threshold'] = image_blur_score < cfg.vision_min_blur_score
        if image_aspect_ratio is not None:
            lo, hi = cfg.document_aspect_range
            blur_evidence['aspect_ratio'] = image_aspect_ratio
            blur_evidence['in_document_range'] = lo <= image_aspect_ratio <= hi

        below = blur_evidence.get('below_threshold', False)
        reason = '图片输入，走视觉模型识别'
        if below:
            reason = '图片输入，走视觉模型识别（清晰度低于阈值，识别准确率可能下降）'

        return RoutingDecision(
            choice=ProviderChoice.VISION_MODEL,
            reason=reason,
            evidence=blur_evidence,
            config_version=cfg.config_version,
        )

    # 4. 兜底
    return RoutingDecision(
        choice=ProviderChoice.FALLBACK_LOCAL,
        reason='未知输入类型，走本地规则兜底',
        evidence={'source_type': source_type},
        config_version=cfg.config_version,
    )


def _is_deterministic_text(text: str, cfg: ProviderRouterConfig) -> bool:
    """判断文本是否命中确定性解析规则（微信发货通知等）。"""
    if not text:
        return False
    compact = text.replace(' ', '').lower()
    return any(kw.replace(' ', '') in compact for kw in cfg.deterministic_text_keywords)


def _matched_keywords(text: str, cfg: ProviderRouterConfig) -> list[str]:
    """返回命中的关键词列表（证据）。"""
    if not text:
        return []
    compact = text.replace(' ', '').lower()
    return [
        kw for kw in cfg.deterministic_text_keywords
        if kw.replace(' ', '') in compact
    ]


# ---- 重试证据保留（验收：超时、错误 JSON、模型不可用时可重试且不丢证据）----

# 触发重试的错误关键词（在 error 字符串中匹配，大小写不敏感）
RETRYABLE_ERROR_KEYWORDS = ('timeout', 'timed out', 'connection', 'unavailable',
                            '503', '502', '504', 'reset', 'temporarily')


@dataclass(frozen=True)
class RetryAttempt:
    """单次调用尝试记录（不含完整敏感原文）。"""

    attempt_no: int
    error_type: str            # ''=成功；timeout/invalid_json/unavailable/other
    error_message: str         # 已截断至 200 字符（脱敏）
    duration_ms: float
    has_reply: bool            # 是否拿到回复（即使 JSON 解析失败）


@dataclass(frozen=True)
class CallEvidence:
    """调用证据：保留重试链路，即使全失败也不丢证据。

    不含 API Key、不含完整回复原文、不含 base64 图片，符合
    AI-R05"日志不得泄露密钥或完整敏感原文"约束。
    """

    attempts: tuple[RetryAttempt, ...]
    total_attempts: int
    success: bool
    final_error_type: str
    final_error_message: str   # 已脱敏
    total_duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            'attempts': [
                {
                    'attempt_no': a.attempt_no,
                    'error_type': a.error_type,
                    'error_message': a.error_message,
                    'duration_ms': round(a.duration_ms, 2),
                    'has_reply': a.has_reply,
                }
                for a in self.attempts
            ],
            'total_attempts': self.total_attempts,
            'success': self.success,
            'final_error_type': self.final_error_type,
            'final_error_message': self.final_error_message,
            'total_duration_ms': round(self.total_duration_ms, 2),
        }


def _classify_error(error: str) -> str:
    """对错误字符串分类（不含敏感数据，仅做关键词匹配）。"""
    if not error:
        return ''
    low = error.lower()
    if 'timeout' in low or 'timed out' in low:
        return 'timeout'
    if 'unavailable' in low or 'connection' in low or any(c in low for c in ('503', '502', '504', 'reset')):
        return 'unavailable'
    if 'json' in low or 'choices' in low or 'content' in low and 'empty' in low:
        return 'invalid_json'
    return 'other'


def _is_retryable(error: str) -> bool:
    """判断错误是否可重试（超时/网络/服务不可用）。"""
    if not error:
        return False
    low = error.lower()
    return any(kw in low for kw in RETRYABLE_ERROR_KEYWORDS)


def call_with_evidence(
    fn: Any,
    *,
    max_retries: int = 1,
) -> tuple[Any, Any, str, CallEvidence]:
    """包裹一次 vision 调用，记录重试证据。

    Args:
        fn: 无参可调用，返回 (reply, extracted, error) 三元组
        max_retries: 失败后最大重试次数（仅对超时/网络/服务不可用重试）

    Returns:
        (reply, extracted, error, CallEvidence)：即使全失败也返回证据
    """
    import time as _time

    attempts: list[RetryAttempt] = []
    total_start = _time.perf_counter()
    reply, extracted, error = None, None, ''
    attempt_no = 0

    for attempt_no in range(1, max_retries + 2):  # 1 次主调用 + max_retries 次重试
        start = _time.perf_counter()
        try:
            reply, extracted, error = fn()
        except Exception as exc:  # noqa: BLE001 - 记录证据后继续
            error = str(exc)
            reply, extracted = None, None
        duration_ms = (_time.perf_counter() - start) * 1000

        err_type = _classify_error(error)
        attempts.append(RetryAttempt(
            attempt_no=attempt_no,
            error_type=err_type,
            error_message=(error or '')[:200],
            duration_ms=duration_ms,
            has_reply=reply is not None and bool(reply),
        ))

        if not error:
            break  # 成功
        if not _is_retryable(error):
            break  # 不可重试错误（如 invalid_json），不再重试
        if attempt_no > max_retries:
            break  # 达到重试上限

    total_duration_ms = (_time.perf_counter() - total_start) * 1000
    success = not error
    final_err_type = _classify_error(error) if error else ''
    evidence = CallEvidence(
        attempts=tuple(attempts),
        total_attempts=attempt_no,
        success=success,
        final_error_type=final_err_type,
        final_error_message=(error or '')[:200],
        total_duration_ms=total_duration_ms,
    )
    return reply, extracted, error, evidence
