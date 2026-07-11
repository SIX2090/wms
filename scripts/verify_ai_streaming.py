from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
sys.path.insert(0, str(APP_DIR))

from ai.streaming import sse_event, stream_response_payload


def parse_sse(line: str) -> dict[str, object]:
    assert line.startswith('data: ')
    assert line.endswith('\n\n')
    return json.loads(line[6:])


def main() -> int:
    failures: list[str] = []

    event = parse_sse(sse_event('token', '你好'))
    if event != {'type': 'token', 'content': '你好'}:
        failures.append(f'sse_event payload mismatch: {event!r}')

    payload_events = [parse_sse(line) for line in stream_response_payload(
        'abcdefg',
        cards=[{'title': 'card'}],
        actions=[{'label': 'open'}],
        chunk_size=3,
    )]
    expected = [
        {'type': 'token', 'content': 'abc'},
        {'type': 'token', 'content': 'def'},
        {'type': 'token', 'content': 'g'},
        {'type': 'cards', 'content': [{'title': 'card'}]},
        {'type': 'actions', 'content': [{'label': 'open'}]},
        {'type': 'done', 'content': 'abcdefg'},
    ]
    if payload_events != expected:
        failures.append(f'stream_response_payload sequence mismatch: {payload_events!r}')

    empty_events = [parse_sse(line) for line in stream_response_payload('')]
    if empty_events != [{'type': 'done', 'content': ''}]:
        failures.append(f'empty response should only emit done: {empty_events!r}')

    if failures:
        print('FAIL AI-STREAMING:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print('PASS AI-STREAMING: SSE events and response payload ordering are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
