from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def sse_event(event_type: str, content: Any) -> str:
    return f'data: {json.dumps({"type": event_type, "content": content}, ensure_ascii=False)}\n\n'


def stream_response_payload(reply_text: str, cards=None, actions=None, *, chunk_size: int = 3) -> Iterable[str]:
    reply_text = reply_text or ''
    for index in range(0, len(reply_text), chunk_size):
        yield sse_event('token', reply_text[index:index + chunk_size])
    if cards:
        yield sse_event('cards', cards)
    if actions:
        yield sse_event('actions', actions)
    yield sse_event('done', reply_text)
