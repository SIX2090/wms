from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-orchestrator-secret'
sys.path.insert(0, str(APP_DIR))

from ai.orchestrator import dispatch_registered_tool


class CaptureLogger:
    def __init__(self) -> None:
        self.warnings: list[tuple[object, ...]] = []

    def warning(self, *args: object) -> None:
        self.warnings.append(args)


def _ai_warehouse_insights_response(message, context=None):
    return {'message': message, 'context': context or {}}


def wrong_handler_name(message, context=None):
    return {'unexpected': True}


def main() -> int:
    failures: list[str] = []
    logger = CaptureLogger()

    result = dispatch_registered_tool(
        'warehouse_insights',
        'check warehouse',
        {'page_url': '/stock'},
        {'warehouse_insights': _ai_warehouse_insights_response},
        logger,
    )
    if result != {'message': 'check warehouse', 'context': {'page_url': '/stock'}}:
        failures.append(f'valid dispatch returned {result!r}')

    missing = dispatch_registered_tool(
        'unknown_tool',
        'message',
        {},
        {'warehouse_insights': _ai_warehouse_insights_response},
        logger,
    )
    if missing is not None:
        failures.append('unknown tool should return None')

    mismatch = dispatch_registered_tool(
        'warehouse_insights',
        'message',
        {},
        {'warehouse_insights': wrong_handler_name},
        logger,
    )
    if mismatch is not None:
        failures.append('handler name mismatch should return None')
    if not logger.warnings:
        failures.append('handler name mismatch should log a warning')

    if failures:
        print('FAIL AI-ORCHESTRATOR:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-ORCHESTRATOR: registered tool dispatch validates registry handlers')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
