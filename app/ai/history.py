from __future__ import annotations


AI_CHAT_HISTORY_MAX_TURNS = 10
# (user_id, conversation_id)。不同会话不再共用一条内存。
_AI_CHAT_HISTORY: dict[tuple[int, int], list[dict[str, str]]] = {}
# 只记住电脑端入口自己的会话。手机端必须带回 conversation_id，不靠这条记忆。
_CHANNEL_CONVERSATION: dict[tuple[str, int], int] = {}


def _storage_key(user_id: int, conversation_id: int | None) -> tuple[int, int]:
    return (int(user_id), int(conversation_id or 0))


def get_history(user_id: int, conversation_id: int | None = None) -> list[dict[str, str]]:
    """返回指定会话的内存历史。未指定会话时不混读其他会话。"""
    if not user_id:
        return []
    if not conversation_id:
        return []
    return list(_AI_CHAT_HISTORY.get(_storage_key(user_id, conversation_id), []))


def append_history(
    user_id: int,
    role: str,
    content: str,
    conversation_id: int | None = None,
) -> None:
    if not user_id or not content:
        return
    history = _AI_CHAT_HISTORY.setdefault(_storage_key(user_id, conversation_id), [])
    history.append({'role': role, 'content': content})
    while len(history) > AI_CHAT_HISTORY_MAX_TURNS * 2:
        del history[:2]


def replace_history(
    user_id: int,
    conversation_id: int | None,
    messages: list[dict[str, str]],
) -> None:
    if not user_id:
        return
    _AI_CHAT_HISTORY[_storage_key(user_id, conversation_id)] = list(
        messages[-AI_CHAT_HISTORY_MAX_TURNS * 2:]
    )


def clear_history(user_id: int, conversation_id: int | None = None) -> None:
    """清空该用户的内存历史。指定会话时只清这一条。"""
    if not user_id:
        return
    if conversation_id:
        _AI_CHAT_HISTORY.pop(_storage_key(user_id, conversation_id), None)
        return
    dead = [key for key in _AI_CHAT_HISTORY if key[0] == int(user_id)]
    for key in dead:
        _AI_CHAT_HISTORY.pop(key, None)
    dead_channels = [key for key in _CHANNEL_CONVERSATION if key[1] == int(user_id)]
    for key in dead_channels:
        _CHANNEL_CONVERSATION.pop(key, None)


def remember_channel(channel: str, user_id: int, conversation_id: int) -> None:
    if channel and user_id and conversation_id:
        _CHANNEL_CONVERSATION[(channel, int(user_id))] = int(conversation_id)


def channel_conversation(channel: str, user_id: int) -> int | None:
    if not channel or not user_id:
        return None
    return _CHANNEL_CONVERSATION.get((channel, int(user_id)))


def forget_channel(channel: str, user_id: int) -> None:
    if channel and user_id:
        _CHANNEL_CONVERSATION.pop((channel, int(user_id)), None)


def find_entry_conversation(user_id, channel):
    """进程重启后，只找回这个入口自己写过标记的活跃会话。"""
    from ai.models import AIConversation, AIMessage

    tag = 'entry:pc' if channel == 'pc' else 'entry:mobile'
    return (
        AIConversation.query
        .join(AIMessage, AIMessage.conversation_id == AIConversation.id)
        .filter(
            AIConversation.user_id == user_id,
            AIConversation.status == 'active',
            AIMessage.prompt_version == tag,
        )
        .order_by(AIConversation.last_activity_at.desc(), AIConversation.id.desc())
        .first()
    )


def record_turn(user_id, role, content, conversation_id=None):
    """把一条消息写入指定会话，并返回实际写入的会话 id。

    显式 id 必须属于该用户且仍是 active，否则新建，不挂到别人的会话。
    电脑端没传 id 时只延续本入口记住的会话。手机端没传 id 时新建。
    同一请求里的 user/assistant 成对写入复用第一条得到的 id。
    落库失败只回滚并记日志，不把异常抛回助手回复。
    """
    from flask import current_app, g, has_app_context, has_request_context

    if not user_id or not content:
        return None
    channel = 'pc'
    bound_id = None
    requested_id = None
    if has_request_context():
        channel = getattr(g, 'ai_history_channel', None) or 'pc'
        bound_id = getattr(g, 'ai_bound_conversation_id', None)
        requested_id = getattr(g, 'ai_requested_conversation_id', None)
    explicit = conversation_id if conversation_id is not None else bound_id
    if explicit is None:
        explicit = requested_id
    try:
        from ai.audit import create_conversation, create_message, get_conversation, list_messages

        conv = None
        if explicit:
            try:
                explicit_id = int(explicit)
            except (TypeError, ValueError):
                explicit_id = None
            if explicit_id:
                conv = get_conversation(explicit_id, user_id=user_id)
                if conv is None or getattr(conv, 'status', None) != 'active':
                    conv = None
        elif channel == 'pc':
            remembered = channel_conversation('pc', user_id)
            if remembered:
                conv = get_conversation(int(remembered), user_id=user_id)
                if conv is None or getattr(conv, 'status', None) != 'active':
                    conv = None
            if conv is None:
                conv = find_entry_conversation(user_id, 'pc')
        if conv is None:
            conv = create_conversation(user_id, title=content[:30])
        if channel == 'pc':
            remember_channel('pc', user_id, conv.id)
        if has_request_context():
            g.ai_bound_conversation_id = conv.id

        prior = get_history(user_id, conv.id)
        append_history(user_id, role, content, conv.id)
        tag = 'entry:pc' if channel == 'pc' else 'entry:mobile'
        if role == 'user' and not prior:
            db_messages = list_messages(conv.id, limit=20, user_id=user_id)
            restored = [
                {'role': message.role, 'content': message.content}
                for message in db_messages
                if message.role in ('user', 'assistant')
            ]
            if restored:
                replace_history(
                    user_id,
                    conv.id,
                    restored + [{'role': role, 'content': content}],
                )
        create_message(conv.id, role, content, prompt_version=tag)
        return conv.id
    except Exception:
        from db import db

        db.session.rollback()
        if has_app_context():
            current_app.logger.exception(
                'AI-ASSISTANT-HISTORY-001 对话历史落库失败（不影响 AI 回复）'
            )
        return None
