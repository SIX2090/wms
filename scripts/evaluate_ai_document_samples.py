from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
SAMPLE_DIR = ROOT / 'samples' / 'ai_documents'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.documents.evaluation import evaluate_document_samples


def main() -> int:
    if not SAMPLE_DIR.exists():
        print(f'NO-SAMPLES: create {SAMPLE_DIR} and add JSON samples with expected/actual sections')
        return 0
    samples = []
    for path in sorted(SAMPLE_DIR.glob('*.json')):
        samples.append(json.loads(path.read_text(encoding='utf-8')))
    if not samples:
        print(f'NO-SAMPLES: {SAMPLE_DIR} contains no *.json samples')
        return 0
    result = evaluate_document_samples(samples)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
