from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def main() -> int:
    from ai.prompts import CURRENT_PROMPT_VERSION, get_prompt_spec
    from ai.providers import OpenAICompatibleConfig, build_chat_payload
    from ai.schemas import validate_json_schema_payload
    from ai.tools.registry import validate_ai_tool_input

    failures: list[str] = []

    schema = {
        'type': 'object',
        'required': ['material_code', 'quantity'],
        'additionalProperties': False,
        'properties': {
            'material_code': {'type': 'string'},
            'quantity': {'type': 'number', 'minimum': 0},
        },
    }
    if not validate_json_schema_payload(schema, {'material_code': 'A001', 'quantity': 1}).valid:
        failures.append('schema validator rejected a valid object payload')
    invalid = validate_json_schema_payload(schema, {'material_code': 'A001', 'quantity': -1, 'extra': True})
    if invalid.valid or 'minimum' not in ' '.join(invalid.errors) or 'additional property' not in ' '.join(invalid.errors):
        failures.append('schema validator did not report numeric bounds and additional properties')

    if not validate_ai_tool_input('warehouse_insights', {'page_url': '/stock', 'page_title': 'Stock'}).valid:
        failures.append('registered tool input validation rejected default object schema')
    if validate_ai_tool_input('missing_tool', {}).valid:
        failures.append('registered tool input validation accepted an unknown tool')

    prompt = get_prompt_spec()
    if prompt.version != CURRENT_PROMPT_VERSION or 'Never auto-submit' not in prompt.system_prompt:
        failures.append('current prompt version is not available or missing safety boundary text')

    config = OpenAICompatibleConfig(
        enabled=True,
        endpoint='https://api.example.test/v1/chat/completions',
        model='wms-model',
        api_key='secret-key',
        timeout_seconds=12,
        max_tokens=256,
        vision_enabled=True,
    )
    if not config.configured or not config.safe_endpoint:
        failures.append('OpenAI-compatible provider config should be configured and safe for HTTPS')
    if config.redacted().get('api_key') != '***':
        failures.append('provider redaction exposed the API key')
    if OpenAICompatibleConfig(True, 'http://example.test/v1', 'm', 'k', 1, 1).safe_endpoint:
        failures.append('provider safety accepted non-local HTTP endpoint')
    payload = build_chat_payload(config, [{'role': 'user', 'content': 'hello'}], stream=True)
    if payload.get('model') != 'wms-model' or payload.get('stream') is not True or payload.get('max_tokens') != 256:
        failures.append('chat payload builder did not preserve model, stream, or token settings')

    if failures:
        print('FAIL AI-PLATFORM-FOUNDATIONS:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-PLATFORM-FOUNDATIONS: schemas, prompts, providers, and tool input validation are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
