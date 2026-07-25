# -*- coding: utf-8 -*-
"""AI-R07-F02：未建档物料按名称/规格建议分类，并按分类生成可编辑料号。

# AI_TASK: AI-R07-F02

纯逻辑 + 依赖注入：不写库、不自动建档。生产由 app.py 注入分类列表与已有编码。
人工确认后才创建物料；库存仍为 0。
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
    """规格压缩为料号可用片段，如 8*5 / 8×5 → 8X5。"""
    raw = str(spec or '').strip().upper()
    if not raw:
        return ''
    raw = raw.replace('×', 'X').replace('*', 'X').replace('ｘ', 'X').replace('Ｘ', 'X')
    raw = re.sub(r'\s+', '', raw)
    raw = re.sub(r'[^A-Z0-9._-]+', '-', raw)
    raw = re.sub(r'-{2,}', '-', raw).strip('-._')
    return raw[:24]


def sanitize_code_prefix(code: Any, fallback: str = 'MAT') -> str:
    text = re.sub(r'[^A-Za-z0-9]+', '', str(code or '').upper())
    if text:
        return text[:12]
    fb = re.sub(r'[^A-Za-z0-9]+', '', str(fallback or 'MAT').upper()) or 'MAT'
    return fb[:12]


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
        # 分类名或编码能对上提示词
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


def next_code_with_prefix(base: str, existing_codes: Iterable[str], offset: int = 0) -> str:
    """在 base / base-001 形式上找空号。base 可含分类前缀与规格，如 LS-8X5。"""
    raw = str(base or '').strip().upper()
    raw = re.sub(r'[^A-Z0-9._-]+', '-', raw)
    raw = re.sub(r'-{2,}', '-', raw).strip('-._')
    if not raw:
        raw = 'MAT'
    existing = {str(c or '').strip().upper() for c in existing_codes if c}
    off = max(0, int(offset or 0))
    if raw not in existing and off <= 0:
        return raw
    highest = 0
    pattern = re.compile(rf'^{re.escape(raw)}-(\d+)$')
    for code in existing:
        m = pattern.fullmatch(code)
        if m:
            highest = max(highest, int(m.group(1)))
        elif code == raw:
            highest = max(highest, 0)
    seq = max(1, highest + 1 + off)
    candidate = f'{raw}-{seq:03d}'
    # 极端冲突时继续递增
    guard = 0
    while candidate in existing and guard < 1000:
        seq += 1
        candidate = f'{raw}-{seq:03d}'
        guard += 1
    return candidate


def build_suggested_code(
    *,
    category: Optional[CategoryInfo],
    spec: Any = '',
    existing_codes: Iterable[str],
    offset: int = 0,
    fallback_code: str = '',
) -> str:
    existing_list = list(existing_codes)
    if not category:
        return str(fallback_code or '').strip() or next_code_with_prefix('AI', existing_list, offset)
    prefix = sanitize_code_prefix(category.code, fallback=f'C{category.id}')
    spec_part = normalize_spec_token(spec)
    base = f'{prefix}-{spec_part}' if spec_part else prefix
    # next_code_with_prefix 把整段当 prefix 扫描 -NNN
    return next_code_with_prefix(base, existing_list, offset)


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
    return CategoryCodeSuggestion(
        category_id=cat.id,
        category_code=cat.code or '',
        category_name=cat.name or '',
        suggested_code=code,
        confidence=float(score),
        reason=reason,
        candidates=candidates,
    )
