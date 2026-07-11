from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding='utf-8')


def main() -> int:
    app_py = read_text('app/app.py')
    routes_py = read_text('app/ai/routes.py')
    handlers_py = read_text('app/ai/handlers.py')
    legacy_py = read_text('app/ai/legacy.py')
    idempotency_py = read_text('app/ai/idempotency.py')

    failures: list[str] = []

    expected_routes = {
        "@ai_bp.get('/tools')",
        "@ai_bp.post('/chat/clear')",
        "@ai_bp.post('/draft_check')",
        "@ai_bp.post('/warehouse_assistant')",
        "@ai_bp.post('/chat/stream')",
    }
    for route in sorted(expected_routes):
        if route not in routes_py:
            failures.append(f'missing Blueprint route: {route}')

    forbidden_app_routes = {
        "@app.route('/api/ai/tools'",
        "@app.route('/api/ai/chat/clear'",
        "@app.route('/api/ai/draft_check'",
        "@app.route('/api/ai/warehouse_assistant'",
        "@app.route('/api/ai/chat/stream'",
    }
    for route in sorted(forbidden_app_routes):
        if route in app_py:
            failures.append(f'monolithic app route still present: {route}')

    if 'from ai.routes import ai_bp' not in app_py or 'app.register_blueprint(ai_bp)' not in app_py:
        failures.append('app does not import and register ai_bp')

    if 'from app import _ai_' in routes_py:
        failures.append('routes.py imports legacy app _ai functions directly')
    if 'from app import _ai_' in handlers_py or "import_module('app')" in handlers_py:
        failures.append('handlers.py imports legacy app functions directly instead of using ai.legacy')

    expected_handler_calls = {
        'return handle_draft_check(payload)',
        'return handle_warehouse_assistant(payload)',
        'return handle_chat_stream(payload)',
    }
    for call in sorted(expected_handler_calls):
        if call not in routes_py:
            failures.append(f'routes.py missing handler proxy call: {call}')

    expected_handler_bridges = {
        "draft_check_response('检查当前草稿', context)",
        'warehouse_assistant_request(payload or {})',
        'chat_stream_request(payload or {})',
    }
    for bridge in sorted(expected_handler_bridges):
        if bridge not in handlers_py:
            failures.append(f'handlers.py missing legacy proxy call: {bridge}')

    expected_legacy_bridges = {
        "import_module('app')",
        "'_ai_draft_check_response'",
        "'_ai_handle_warehouse_assistant_request'",
        "'_ai_handle_chat_stream_request'",
    }
    for bridge in sorted(expected_legacy_bridges):
        if bridge not in legacy_py:
            failures.append(f'legacy.py missing app bridge: {bridge}')

    if '@ai_idempotent_request\ndef warehouse_assistant' not in routes_py:
        failures.append('warehouse_assistant Blueprint route is not idempotent')
    if '@ai_idempotent_request\ndef chat_stream' not in routes_py:
        failures.append('chat_stream Blueprint route is not idempotent')
    if 'def ai_idempotent_request(view_function)' not in idempotency_py:
        failures.append('idempotency module missing Blueprint-safe decorator')
    if 'def configure_ai_idempotency_service' not in idempotency_py:
        failures.append('idempotency module missing service configuration')

    if failures:
        print('FAIL AI-PLATFORM-BOUNDARIES:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-PLATFORM-BOUNDARIES: AI routes, handler proxies, and idempotency boundaries are enforced')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
