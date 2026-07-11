from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DocumentEvaluationResult:
    sample_count: int
    header_accuracy: float
    line_recall: float
    quantity_accuracy: float
    material_match_accuracy: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            'sample_count': self.sample_count,
            'header_accuracy': self.header_accuracy,
            'line_recall': self.line_recall,
            'quantity_accuracy': self.quantity_accuracy,
            'material_match_accuracy': self.material_match_accuracy,
        }


def evaluate_document_samples(samples: list[dict[str, Any]]) -> DocumentEvaluationResult:
    header_total = 0
    header_ok = 0
    expected_lines = 0
    recalled_lines = 0
    quantity_total = 0
    quantity_ok = 0
    material_total = 0
    material_ok = 0

    for sample in samples:
        expected = sample.get('expected') or {}
        actual = sample.get('actual') or {}
        for field in ('document_type', 'supplier', 'customer', 'order_no'):
            expected_value = _clean(expected.get(field))
            if not expected_value:
                continue
            header_total += 1
            if _clean(actual.get(field)) == expected_value:
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
                if expected_code and matched.get('code') == expected_code:
                    material_ok += 1
                elif expected_name and matched.get('name') == expected_name:
                    material_ok += 1

    return DocumentEvaluationResult(
        sample_count=len(samples),
        header_accuracy=_ratio(header_ok, header_total),
        line_recall=_ratio(recalled_lines, expected_lines),
        quantity_accuracy=_ratio(quantity_ok, quantity_total),
        material_match_accuracy=_ratio(material_ok, material_total),
    )


def _clean(value: Any) -> str:
    return str(value or '').strip().lower()


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
    for index, actual in enumerate(actual_items):
        if expected.get('code') and actual.get('code') == expected.get('code'):
            return actual_items.pop(index)
    for index, actual in enumerate(actual_items):
        if expected.get('name') and actual.get('name') == expected.get('name'):
            return actual_items.pop(index)
    return None


def _ratio(ok: int, total: int) -> float:
    if total <= 0:
        return 1.0
    return round(ok / total, 4)
