from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def main() -> int:
    from ai.documents.evaluation import evaluate_document_samples

    samples = [
        {
            'expected': {
                'document_type': 'in_order',
                'supplier': 'supplier a',
                'order_no': 'dn-001',
                'items': [
                    {'code': 'A001', 'name': 'bearing', 'quantity': 2},
                    {'code': 'A002', 'name': 'nut', 'quantity': 5},
                ],
            },
            'actual': {
                'document_type': 'in_order',
                'supplier': 'supplier a',
                'order_no': 'dn-001',
                'items': [
                    {'code': 'A001', 'name': 'bearing', 'quantity': 2},
                    {'code': 'A002', 'name': 'nut', 'quantity': 4},
                ],
            },
        }
    ]
    result = evaluate_document_samples(samples)
    assert result.sample_count == 1
    assert result.header_accuracy == 1.0
    assert result.line_recall == 1.0
    assert result.material_match_accuracy == 1.0
    assert result.quantity_accuracy == 0.5
    print('PASS AI-DOCUMENT-EVALUATION: golden-sample document metrics are computed deterministically')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
