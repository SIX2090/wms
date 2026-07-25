# -*- coding: utf-8 -*-
"""AI-R07-F02 / AI-R07-F02-FIX-01：未建档物料建议分类，并按「分类三位数字+流水」编料号。

# AI_TASK: AI-R07-F02-FIX-01

编码规则（业务约定）：
- 分类编码用三位数字，如 100=电线、101=螺丝
- 物料编号 = 分类三位 + 流水三位，共 6 位数字
- 例：分类 100 下第一种料 → 100001；第二种 → 100002
- 规格/名称（如 2.5平方、螺丝8*5）写在名称/规格字段，不编进料号

纯逻辑 + 依赖注入：不写库、不自动建档。人工确认后才创建；库存仍为 0。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence


# 名称/原文中的常见词 → 用于命中分类名称（分类名含这些词即可）
CATEGORY_KEYWORD_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('螺丝', ('螺丝', '螺钉', '螺栓', '螺柱')),
    ('螺母', ('螺母', '螺帽')),
    ('垫圈', ('垫圈', '华司', '介子')),
    ('电线', ('电线', '电缆', '导线', '软线')),
    ('电缆', ('电缆', '电线')),
    ('开关', ('开关', '断路器', '空开')),
    ('断路器', ('断路器', '塑壳', '微型断路', '空开')),
    ('接触器', ('接触器',)),
    ('继电器', ('继电器',)),
    ('互感器', ('互感器', 'CT')),
    ('端子', ('端子', '接线端子')),
    ('铜排', ('铜排', '母排')),
    ('轴承', ('轴承',)),
    ('指示灯', ('指示灯', '信号灯')),
    ('熔断', ('熔断', '保险丝')),
    ('按钮', ('按钮',)),
    ('变频器', ('变频器', '变频')),
)

# 流水号位数（分类 3 位 + 流水 3 位 = 6 位料号）
CATEGORY_CODE_DIGITS = 3
SERIAL_DIGITS = 3
SERIAL_MAX = 10 ** SERIAL_DIGITS - 1  # 999


@dataclass(frozen=True)
class CategoryInfo:
    id: int
    code: str
    name: str


@dataclass(frozen=True)
class CategoryCodeSuggestion:
    category_id: Optional[int]
    category_code: str
    category_name: str
    suggested_code: str
    confidence: float
    reason: str
    candidates: tuple[dict[str, Any], ...] = ()


def normalize_text(value: Any) -> str:
    text = str(value or '').strip().lower()
    if not text:
        return ''
    text = text.replace('×', 'x').replace('*', 'x').replace('Ｘ', 'x').replace('ｘ', 'x')
    text = re.sub(r'\s+', '', text)
    return text


def normalize_spec_token(spec: Any) -> str:
    """规格规范化（仅用于展示/匹配辅助，不写入料号）。"""
    raw = str(spec or '').strip().upper()
    if not raw:
        return ''
    raw = raw.replace('×', 'X').replace('*', 'X').replace('ｘ', 'X').replace('Ｘ', 'X')
    raw = re.sub(r'\s+', '', raw)
    raw = re.sub(r'[^A-Z0-9._-]+', '-', raw)
    raw = re.sub(r'-{2,}', '-', raw).strip('-._')
    return raw[:24]


def category_digit_prefix(code: Any, fallback_id: Optional[int] = None) -> Optional[str]:
    """从分类编码提取三位数字前缀。

    - '100' / '100电线' → '100'
    - 不足三位的纯数字左侧补零：'7' → '007'
    - 超过三位取前三位：'1001' → '100'
    - 无数字时：若有 fallback_id，用 id 模 1000 补成三位（尽量不中断建议）
    """
    digits = re.sub(r'\D', '', str(code or ''))
    if digits:
        if len(digits) >= CATEGORY_CODE_DIGITS:
            return digits[:CATEGORY_CODE_DIGITS]
        return digits.zfill(CATEGORY_CODE_DIGITS)
    if fallback_id is not None:
        try:
            n = abs(int(fallback_id)) % (10 ** CATEGORY_CODE_DIGITS)
            return f'{n:0{CATEGORY_CODE_DIGITS}d}'
        except (TypeError, ValueError):
            return None
    return None


def next_category_serial_code(
    category_prefix: str,
    existing_codes: Iterable[str],
    offset: int = 0,
) -> str:
    """在指定三位分类下取下一流水号：100001、100002…"""
    prefix = re.sub(r'\D', '', str(category_prefix or ''))
    if len(prefix) != CATEGORY_CODE_DIGITS:
        raise ValueError(f'分类前缀必须是 {CATEGORY_CODE_DIGITS} 位数字，收到: {category_prefix!r}')
    existing = {str(c or '').strip().upper() for c in existing_codes if c}
    pattern = re.compile(rf'^{prefix}(\d{{{SERIAL_DIGITS}}})$')
    highest = 0
    for code in existing:
        m = pattern.fullmatch(str(code).strip())
        if m:
            highest = max(highest, int(m.group(1)))
    seq = highest + 1 + max(0, int(offset or 0))
    if seq < 1:
        seq = 1
    if seq > SERIAL_MAX:
        # 流水用尽时扩展为更多位，仍以前缀开头，避免硬失败
        candidate = f'{prefix}{seq}'
    else:
        candidate = f'{prefix}{seq:0{SERIAL_DIGITS}d}'
    guard = 0
    while candidate.upper() in existing and guard < 10000:
        seq += 1
        candidate = f'{prefix}{seq:0{SERIAL_DIGITS}d}' if seq <= SERIAL_MAX else f'{prefix}{seq}'
        guard += 1
    return candidate


def build_suggested_code(
    *,
    category: Optional[CategoryInfo],
    spec: Any = '',  # 规格不进入料号，保留参数兼容调用方
    existing_codes: Iterable[str],
    offset: int = 0,
    fallback_code: str = '',
) -> str:
    """有分类：分类三位+流水；无分类：回退 fallback（如 AIyyMMdd###）。"""
    del spec  # 明确不使用规格拼料号
    existing_list = list(existing_codes)
    if not category:
        return str(fallback_code or '').strip() or next_category_serial_code('999', existing_list, offset)
    prefix = category_digit_prefix(category.code, fallback_id=category.id)
    if not prefix:
        return str(fallback_code or '').strip() or next_category_serial_code('999', existing_list, offset)
    return next_category_serial_code(prefix, existing_list, offset)


def _category_hit_score(category: CategoryInfo, blob: str) -> tuple[float, str]:
    """blob 已 normalize_text。"""
    if not blob:
        return 0.0, ''
    cname = normalize_text(category.name)
    ccode = normalize_text(category.code)
    best = 0.0
    reason = ''
    if cname and cname in blob:
        best = 0.92
        reason = f'名称/规格含分类「{category.name}」'
    elif ccode and len(ccode) >= 2 and ccode in blob:
        best = 0.8
        reason = f'名称/规格含分类编码「{category.code}」'
    for label, hints in CATEGORY_KEYWORD_HINTS:
        if not any(normalize_text(h) in blob for h in hints):
            continue
        label_n = normalize_text(label)
        if label_n and (label_n in cname or label_n in ccode or any(normalize_text(h) in cname for h in hints)):
            score = 0.88
            if score > best:
                best = score
                reason = f'关键词「{label}」命中分类「{category.name}」'
    return best, reason


def rank_categories(
    *,
    name: Any,
    spec: Any = '',
    raw_text: Any = '',
    categories: Sequence[CategoryInfo],
    limit: int = 5,
) -> list[tuple[CategoryInfo, float, str]]:
    blob = normalize_text(f'{name or ""} {spec or ""} {raw_text or ""}')
    ranked: list[tuple[CategoryInfo, float, str]] = []
    for cat in categories:
        score, reason = _category_hit_score(cat, blob)
        if score > 0:
            ranked.append((cat, score, reason))
    ranked.sort(key=lambda item: (-item[1], item[0].code or '', item[0].id))
    return ranked[: max(1, int(limit or 5))]


def suggest_category_and_code(
    *,
    name: Any,
    spec: Any = '',
    raw_text: Any = '',
    categories: Sequence[CategoryInfo],
    existing_codes: Iterable[str],
    offset: int = 0,
    fallback_code: str = '',
) -> CategoryCodeSuggestion:
    ranked = rank_categories(name=name, spec=spec, raw_text=raw_text, categories=categories, limit=5)
    candidates = tuple(
        {
            'id': cat.id,
            'code': cat.code,
            'name': cat.name,
            'score': round(score, 4),
            'reason': reason,
        }
        for cat, score, reason in ranked
    )
    if not ranked or ranked[0][1] < 0.5:
        code = str(fallback_code or '').strip() or build_suggested_code(
            category=None, spec=spec, existing_codes=existing_codes, offset=offset, fallback_code=fallback_code
        )
        return CategoryCodeSuggestion(
            category_id=None,
            category_code='',
            category_name='',
            suggested_code=code,
            confidence=0.0,
            reason='未识别到明确分类，使用通用编号建议（可改）',
            candidates=candidates,
        )
    cat, score, reason = ranked[0]
    code = build_suggested_code(
        category=cat,
        spec=spec,
        existing_codes=existing_codes,
        offset=offset,
        fallback_code=fallback_code,
    )
    prefix = category_digit_prefix(cat.code, fallback_id=cat.id) or ''
    detail = f'{reason}；编号规则：分类{prefix}+流水 → {code}'
    return CategoryCodeSuggestion(
        category_id=cat.id,
        category_code=cat.code or '',
        category_name=cat.name or '',
        suggested_code=code,
        confidence=float(score),
        reason=detail,
        candidates=candidates,
    )
