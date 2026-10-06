# -*- coding: utf-8 -*-
"""AI-ASSISTANT-HISTORY-001 回归：PC 对话历史持久化与恢复。

背景：主聊天通道（warehouse_assistant / chat_stream）的历史只写
ai/history.py 的内存字典 `_AI_CHAT_HISTORY`（10 轮上限，重启即丢），
DB 层 AIConversation/AIMessage 表和 REST API 全存在但从未被主通道写入。
修复：`_ai_append_history` 升级为内存 + DB 双写；`/api/ai/chat/clear`
同步归档 DB 会话；前端面板打开时从 REST API 恢复最近活跃会话。

断言：
  T1. _ai_append_history 双写：内存和 DB（AIConversation + AIMessage x2）都落。
  T2. 连续两轮对话累计 4 条 AIMessage，且会话只有 1 个（复用 active 会话）。
  T3. 模拟进程重启（清空内存字典）后，下一条 user 消息落库时把 DB 历史
      回填进内存，_ai_get_history 能看到恢复的上下文。
  T4. /api/ai/chat/clear 后：内存清空 + DB 会话变 archived，且新对话
      建在新会话里（不再往已归档会话追加）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# A12/R7：模块顶层禁止裸 app context push/pop，统一放 autouse fixture
_ctx = app_module.app.app_context()


import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="module")
def _push_ctx():
    _ctx.push()
    yield
    _ctx.pop()


USER_ID = 101


def _reset():
    """重建内存库 + 清空内存历史。"""
    db.drop_all()
    db.create_all()
    from ai.history import _AI_CHAT_HISTORY
    _AI_CHAT_HISTORY.pop(USER_ID, None)


def test_t1_append_history_writes_both_memory_and_db():
    """T1：双写——内存 + DB 都有。"""
    from ai.models import AIConversation, AIMessage
    _reset()
    app_module._ai_append_history(USER_ID, 'user', '查一下A001库存')
    app_module._ai_append_history(USER_ID, 'assistant', 'A001 当前库存 120')

    assert app_module._ai_get_history(USER_ID) == [
        {'role': 'user', 'content': '查一下A001库存'},
        {'role': 'assistant', 'content': 'A001 当前库存 120'},
    ], "内存历史应保留原行为"
    conv = AIConversation.query.filter_by(user_id=USER_ID).first()
    assert conv is not None, "应创建 AIConversation"
    assert conv.status == 'active'
    assert conv.title == '查一下A001库存', "会话标题取首条 user 消息前 30 字"
    msgs = AIMessage.query.filter_by(conversation_id=conv.id).all()
    assert len(msgs) == 2, "应落 2 条 AIMessage（user + assistant）"
    assert [m.role for m in msgs] == ['user', 'assistant']
    assert [m.content for m in msgs] == ['查一下A001库存', 'A001 当前库存 120']


def test_t2_two_rounds_one_conversation():
    """T2：连续两轮对话 4 条消息，仍只有 1 个 active 会话。"""
    from ai.models import AIConversation, AIMessage
    _reset()
    for role, content in [
        ('user', '查一下A001库存'), ('assistant', 'A001 当前库存 120'),
        ('user', '低库存有哪些'), ('assistant', 'B003 库存 2 低于安全线'),
    ]:
        app_module._ai_append_history(USER_ID, role, content)

    convs = AIConversation.query.filter_by(user_id=USER_ID).all()
    assert len(convs) == 1, "两轮对话应复用同一会话"
    msgs = AIMessage.query.filter_by(conversation_id=convs[0].id).order_by(
        AIMessage.created_at.asc()).all()
    assert len(msgs) == 4, "应累计 4 条消息"


def test_t3_memory_restored_from_db_after_restart():
    """T3：进程重启（内存清空）后，DB 历史自动回填内存。"""
    from ai.models import AIConversation, AIMessage
    from ai.history import _AI_CHAT_HISTORY
    _reset()
    app_module._ai_append_history(USER_ID, 'user', '查一下A001库存')
    app_module._ai_append_history(USER_ID, 'assistant', 'A001 当前库存 120')

    # 模拟重启：只清内存，DB 保留
    _AI_CHAT_HISTORY.pop(USER_ID, None)
    assert app_module._ai_get_history(USER_ID) == []

    # 新一轮 user 消息到达 → 落库时应回填
    app_module._ai_append_history(USER_ID, 'user', '那B003呢')
    restored = app_module._ai_get_history(USER_ID)
    roles = [m['role'] for m in restored]
    assert roles == ['user', 'assistant', 'user'], (
        f"重启后应恢复 DB 历史并含新消息，实际 {roles}")
    assert restored[0]['content'] == '查一下A001库存'
    assert restored[2]['content'] == '那B003呢'

    # DB 侧：仍是同一会话，累计 3 条
    convs = AIConversation.query.filter_by(user_id=USER_ID).all()
    assert len(convs) == 1
    assert AIMessage.query.filter_by(conversation_id=convs[0].id).count() == 3


def test_t4_clear_archives_conversation_and_starts_new():
    """T4：chat/clear 归档 DB 会话；新对话进新会话。"""
    from ai.models import AIConversation, AIMessage
    _reset()
    app_module._ai_append_history(USER_ID, 'user', '查一下A001库存')
    app_module._ai_append_history(USER_ID, 'assistant', 'A001 当前库存 120')

    with app_module.app.test_request_context():
        from flask_login import login_user
        admin = app_module.User.query.get(USER_ID)
        if admin is None:
            from werkzeug.security import generate_password_hash
            admin = app_module.User(
                id=USER_ID, username='hist_user',
                password_hash=generate_password_hash('x'),
                role='admin', must_change_password=False)
            db.session.add(admin)
            db.session.commit()
        login_user(admin)
        client = app_module.app.test_client()
        resp = client.post('/api/ai/chat/clear')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'success'

    conv = AIConversation.query.filter_by(user_id=USER_ID).first()
    assert conv.status == 'archived', "clear 后会话应归档"

    # 新对话：应建新 active 会话，不污染已归档会话
    app_module._ai_append_history(USER_ID, 'user', '新话题：今日优先级')
    convs = AIConversation.query.filter_by(user_id=USER_ID).order_by(
        AIConversation.id).all()
    assert len(convs) == 2, "应创建第二个会话"
    assert convs[0].status == 'archived' and convs[1].status == 'active'
    assert AIMessage.query.filter_by(conversation_id=convs[1].id).count() == 1
