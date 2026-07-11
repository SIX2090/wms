from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-handlers-secret'
sys.path.insert(0, str(APP_DIR))

from ai import handlers


def main() -> int:
    failures: list[str] = []
    calls: list[tuple[str, object, object]] = []

    original_draft_check = handlers.draft_check_response
    original_warehouse = handlers.warehouse_assistant_request
    original_chat_stream = handlers.chat_stream_request

    def fake_draft_check(message, context=None):
        calls.append(('draft_check', message, context))
        return {'status': 'draft'}

    def fake_warehouse(payload):
        calls.append(('warehouse', payload, None))
        return {'status': 'warehouse'}

    def fake_chat_stream(payload):
        calls.append(('chat_stream', payload, None))
        return {'status': 'stream'}

    handlers.draft_check_response = fake_draft_check
    handlers.warehouse_assistant_request = fake_warehouse
    handlers.chat_stream_request = fake_chat_stream
    try:
        if handlers.handle_draft_check({'page_url': ' /out_order/new '}) != {'status': 'draft'}:
            failures.append('handle_draft_check did not return bridge result')
        if handlers.handle_warehouse_assistant({'message': 'hi'}) != {'status': 'warehouse'}:
            failures.append('handle_warehouse_assistant did not return bridge result')
        if handlers.handle_chat_stream({'message': 'hi'}) != {'status': 'stream'}:
            failures.append('handle_chat_stream did not return bridge result')
    finally:
        handlers.draft_check_response = original_draft_check
        handlers.warehouse_assistant_request = original_warehouse
        handlers.chat_stream_request = original_chat_stream

    expected_calls = [
        ('draft_check', '检查当前草稿', {'page_url': '/out_order/new'}),
        ('warehouse', {'message': 'hi'}, None),
        ('chat_stream', {'message': 'hi'}, None),
    ]
    if calls != expected_calls:
        failures.append(f'handler bridge calls mismatch: {calls!r}')

    routes_py = (ROOT / 'app' / 'ai' / 'routes.py').read_text(encoding='utf-8')
    handlers_py = (ROOT / 'app' / 'ai' / 'handlers.py').read_text(encoding='utf-8')
    legacy_py = (ROOT / 'app' / 'ai' / 'legacy.py').read_text(encoding='utf-8')

    if 'from app import _ai_' in routes_py:
        failures.append('routes.py directly imports legacy app AI functions')
    if 'from app import _ai_' in handlers_py or "import_module('app')" in handlers_py:
        failures.append('handlers.py directly imports legacy app module')
    if "import_module('app')" not in legacy_py:
        failures.append('legacy.py does not centralize legacy app imports')

    if failures:
        print('FAIL AI-HANDLERS:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-HANDLERS: route handlers delegate through the centralized legacy bridge')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
