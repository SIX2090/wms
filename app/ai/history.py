from __future__ import annotations


AI_CHAT_HISTORY_MAX_TURNS = 10
_AI_CHAT_HISTORY: dict[int, list[dict[str, str]]] = {}


def get_history(user_id: int) -> list[dict[str, str]]:
    if not user_id:
        return []
    return list(_AI_CHAT_HISTORY.get(user_id, []))


def append_history(user_id: int, role: str, content: str) -> None:
    if not user_id or not content:
        return
    history = _AI_CHAT_HISTORY.setdefault(user_id, [])
    history.append({'role': role, 'content': content})
    while len(history) > AI_CHAT_HISTORY_MAX_TURNS * 2:
        del history[:2]


def clear_history(user_id: int) -> None:
    if user_id and user_id in _AI_CHAT_HISTORY:
        del _AI_CHAT_HISTORY[user_id]
