from __future__ import annotations

from ai.legacy import chat_stream_request, draft_check_response, warehouse_assistant_request


def handle_draft_check(payload):
    payload = payload or {}
    context = {'page_url': (payload.get('page_url') or '').strip()}
    return draft_check_response('检查当前草稿', context)


def handle_warehouse_assistant(payload):
    return warehouse_assistant_request(payload or {})


def handle_chat_stream(payload):
    return chat_stream_request(payload or {})
