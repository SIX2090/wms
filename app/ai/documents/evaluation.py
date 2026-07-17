"""文档识别质量评估指标。
# AI_TASK: AI-R03

AI-R03 起新增场景覆盖率、来源类别覆盖率和模糊匹配，用于衡量黄金样本库的覆盖完备性。
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DocumentEvaluationResult:
    """文档识别质量评估结果。

    AI-R03 起增加场景覆盖率和来源类别覆盖率，衡量黄金样本库的覆盖完备性。
    """
    sample_count: int
    header_accuracy: float
    line_recall: float
    quantity_accuracy: float
    material_match_accuracy: float
    # AI-R03 新增：场景覆盖率（0-1，覆盖的必备场景数 / 必备场景总数）
    scenario_coverage: float = 1.0
    # AI-R03 新增：来源类别覆盖率（0-1）
    source_category_coverage: float = 1.0
    # AI-R03 新增：覆盖的具体场景标签
    covered_scenarios: tuple[str, ...] = field(default_factory=tuple)
    # AI-R03 新增：缺失的必备场景标签
    missing_scenarios: tuple[str, ...] = field(default_factory=tuple)
    # AI-R03 新增：覆盖的来源类别
    covered_source_categories: tuple[str, ...] = field(default_factory=tuple)
    # AI-R03 新增：缺失的必备来源类别
    missing_source_categories: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            'sample_count': self.sample_count,
            'header_accuracy': self.header_accuracy,
            'line_recall': self.line_recall,
            'quantity_accuracy': self.quantity_accuracy,
            'material_match_accuracy': self.material_match_accuracy,
            'scenario_coverage': self.scenario_coverage,
            'source_category_coverage': self.source_category_coverage,
            'covered_scenarios': list(self.covered_scenarios),
            'missing_scenarios': list(self.missing_scenarios),
            'covered_source_categories': list(self.covered_source_categories),
            'missing_source_categories': list(self.missing_source_categories),
        }


# AI-R03 必备场景与来源类别（与 golden_samples.py 保持一致）
REQUIRED_SCENARIOS: frozenset[str] = frozenset({
    'normal', 'blurry', 'tilted', 'shadow', 'handwritten',
    'multipage', 'merged_cell', 'duplicate', 'unit_mixed',
})

REQUIRED_SOURCE_CATEGORIES: frozenset[str] = frozenset({
    'photo', 'scanned', 'wechat_screenshot', 'wechat_text', 'excel',
})


def evaluate_document_samples(samples: list[dict[str, Any]]) -> DocumentEvaluationResult:
    """评估文档识别质量。

    AI-R03 起同时计算场景覆盖率和来源类别覆盖率：
    - 样本 dict 可携带 scenario_tags(list[str]) 和 source_category(str) 元数据
    - 缺失元数据时按 normal/photo 计入，不阻塞回归测试
    """
    header_total = 0
    header_ok = 0
    expected_lines = 0
    recalled_lines = 0
    quantity_total = 0
    quantity_ok = 0
    material_total = 0
    material_ok = 0

    covered_scenarios: set[str] = set()
    covered_source_categories: set[str] = set()

    for sample in samples:
        expected = sample.get('expected') or {}
        actual = sample.get('actual') or {}
        for field_name in ('document_type', 'supplier', 'customer', 'order_no'):
            expected_value = _clean(expected.get(field_name))
            if not expected_value:
                continue
            header_total += 1
            # AI-R03：表头字段允许模糊匹配（全半角/空格/大小写归一化后相等即算正确）
            if _fuzzy_equal(_clean(actual.get(field_name)), expected_value):
                header_ok += 1

        actual_items = [_normalize_item(item) for item in actual.get('items') or [] if isinstance(item, dict)]
        unmatched_actual = list(actual_items)
        for expected_item in expected.get('items') or []:
            if not isinstance(expected_item, dict):
                continue
            expected_lines += 1
            normalized_expected = _normalize_item(expected_item)
            matched = _pop_best_match(normalized_expected, unmatched_actual)
            if matched is None:
                continue
            recalled_lines += 1
            if normalized_expected.get('quantity') is not None:
                quantity_total += 1
                if _same_quantity(normalized_expected.get('quantity'), matched.get('quantity')):
                    quantity_ok += 1
            expected_code = normalized_expected.get('code')
            expected_name = normalized_expected.get('name')
            if expected_code or expected_name:
                material_total += 1
                # AI-R03：物料编码/名称允许模糊匹配
                if expected_code and _fuzzy_equal(matched.get('code'), expected_code):
                    material_ok += 1
                elif expected_name and _fuzzy_equal(matched.get('name'), expected_name):
                    material_ok += 1

        # AI-R03：收集场景与来源覆盖
        for tag in sample.get('scenario_tags') or ['normal']:
            tag = str(tag).strip()
            if tag in REQUIRED_SCENARIOS:
                covered_scenarios.add(tag)
        src = str(sample.get('source_category') or 'photo').strip()
        if src in REQUIRED_SOURCE_CATEGORIES:
            covered_source_categories.add(src)

    missing_scenarios = set(REQUIRED_SCENARIOS) - covered_scenarios
    missing_source_categories = set(REQUIRED_SOURCE_CATEGORIES) - covered_source_categories

    return DocumentEvaluationResult(
        sample_count=len(samples),
        header_accuracy=_ratio(header_ok, header_total),
        line_recall=_ratio(recalled_lines, expected_lines),
        quantity_accuracy=_ratio(quantity_ok, quantity_total),
        material_match_accuracy=_ratio(material_ok, material_total),
        scenario_coverage=_ratio(len(covered_scenarios), len(REQUIRED_SCENARIOS)),
        source_category_coverage=_ratio(len(covered_source_categories), len(REQUIRED_SOURCE_CATEGORIES)),
        covered_scenarios=tuple(sorted(covered_scenarios)),
        missing_scenarios=tuple(sorted(missing_scenarios)),
        covered_source_categories=tuple(sorted(covered_source_categories)),
        missing_source_categories=tuple(sorted(missing_source_categories)),
    )


def _clean(value: Any) -> str:
    """基础清洗：去首尾空白 + 小写。"""
    return str(value or '').strip().lower()


def _normalize_text(value: str) -> str:
    """AI-R03 模糊匹配归一化：NFKC 全半角统一 + 去多余空白 + 小写。

    使用 unicodedata.normalize('NFKC') 覆盖所有全角字母/数字/标点，
    避免手工维护映射表遗漏（如全角 S/H 等）。
    """
    if not value:
        return ''
    # NFKC：全角->半角，兼容字符->规范形式（ﬁ->fi, ㈱->(株) 等）
    text = unicodedata.normalize('NFKC', value)
    text = text.lower().strip()
    # 折叠连续空白
    while '  ' in text:
        text = text.replace('  ', ' ')
    return text


def _fuzzy_equal(left: str, right: str) -> bool:
    """AI-R03 模糊相等：归一化后完全相等。"""
    return _normalize_text(left) == _normalize_text(right)


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        'code': _clean(item.get('code')),
        'name': _clean(item.get('name')),
        'spec': _clean(item.get('spec')),
        'quantity': _number(item.get('quantity')),
    }


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_quantity(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= 1e-6


def _pop_best_match(expected: dict[str, Any], actual_items: list[dict[str, Any]]) -> dict[str, Any] | None:
    # AI-R03：物料行匹配优先精确编码，其次模糊编码，再精确名称，最后模糊名称
    for index, actual in enumerate(actual_items):
        if expected.get('code') and actual.get('code') == expected.get('code'):
            return actual_items.pop(index)
    for index, actual in enumerate(actual_items):
        if expected.get('code') and _fuzzy_equal(actual.get('code'), expected.get('code')):
            return actual_items.pop(index)
    for index, actual in enumerate(actual_items):
        if expected.get('name') and actual.get('name') == expected.get('name'):
            return actual_items.pop(index)
    for index, actual in enumerate(actual_items):
        if expected.get('name') and _fuzzy_equal(actual.get('name'), expected.get('name')):
            return actual_items.pop(index)
    return None


def _ratio(ok: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(ok / total, 4)
