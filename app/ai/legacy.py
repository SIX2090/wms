from __future__ import annotations

from importlib import import_module
from typing import Any


def _legacy_app():
    return import_module('app')


def call_legacy_ai_function(name: str, *args, **kwargs) -> Any:
    handler = getattr(_legacy_app(), name)
    return handler(*args, **kwargs)


def draft_check_response(message: str, context: dict[str, object] | None = None):
    return call_legacy_ai_function('_ai_draft_check_response', message, context)


def warehouse_assistant_request(payload: dict[str, object]):
    return call_legacy_ai_function('_ai_handle_warehouse_assistant_request', payload)


def chat_stream_request(payload: dict[str, object]):
    return call_legacy_ai_function('_ai_handle_chat_stream_request', payload)
