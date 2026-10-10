# -*- coding: utf-8 -*-
"""FIX-2026-10-10 F1/F2：查库存够用判断 + 出入库流水查询（失败注入测试）。

F1：机械回退（LLM 不可用）也必须输出够/不够结论。
F2：流水问法判定 + 与查库存互斥 + 同名多规格物料聚合流水。

不依赖真实库：内存库 + 打桩。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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

import pytest  # noqa: E402

_ctx = app_module.app.app_context()


@pytest.fixture(autouse=True, scope="module")
def _push_ctx():
    _ctx.push()
    db.drop_all()
    db.create_all()
    yield
    _ctx.pop()


class _Unit:
    def __init__(self, name='条'):
        self.name = name


def _make_material(mid=1, stock=5, reorder=10, min_stock=0, name='铜排', spec='100*10'):
    m = MagicMock()
    m.id = mid
    m.code = f'LPY{mid:04d}'
    m.name = name
    m.spec = spec
    m.unit = _Unit()
    m.reorder_point = reorder
    m.min_stock = min_stock
    return m


def _login_ctx():
    from models.core import User
    from flask_login import login_user
    ctx = app_module.app.test_request_context('/assistant/chat', method='POST')
    ctx.push()
    u = User.query.filter_by(role='admin').first() or User.query.first()
    if u:
        login_user(u)
    return ctx


# ---------- F1：够用判断（机械回退） ----------

def test_f1_low_stock_warns_replenish():
    """低于安全库存必须输出 ⚠️ 补货提醒（LLM 失败时机械回退也不能只报数字）。"""
    m = _make_material(stock=5, reorder=10)
    ctx = _login_ctx()
    try:
        with patch.object(app_module, '_ai_is_stock_query_question', return_value=True), \
             patch.object(app_module, '_ai_capability_allowed', return_value=True), \
             patch.object(app_module, '_ai_llm_parse_stock_intent', return_value=None), \
             patch.object(app_module, '_ai_find_materials_from_message', return_value=[m]), \
             patch.object(app_module, 'get_default_warehouse') as gw, \
             patch.object(app_module, 'get_warehouse_stock_quantities', return_value={1: 5.0}), \
             patch.object(app_module, '_voice_llm_chat', return_value=None), \
             patch.object(app_module, '_build_stock_query_llm_prompt', return_value=''):
            gw.return_value = MagicMock(name='材料仓')
            resp = app_module._ai_stock_query_response('铜排够不够')
    finally:
        ctx.pop()
    assert resp is not None, "应触发查库存工具"
    reply = json.loads(resp.get_data())['reply']
    assert '低于' in reply and '补货' in reply, f"应含低于+补货结论：{reply}"


def test_f1_enough_stock_says_sufficient():
    """高于安全库存应说库存充足。"""
    m = _make_material(stock=50, reorder=10)
    ctx = _login_ctx()
    try:
        with patch.object(app_module, '_ai_is_stock_query_question', return_value=True), \
             patch.object(app_module, '_ai_capability_allowed', return_value=True), \
             patch.object(app_module, '_ai_llm_parse_stock_intent', return_value=None), \
             patch.object(app_module, '_ai_find_materials_from_message', return_value=[m]), \
             patch.object(app_module, 'get_default_warehouse') as gw, \
             patch.object(app_module, 'get_warehouse_stock_quantities', return_value={1: 50.0}), \
             patch.object(app_module, '_voice_llm_chat', return_value=None), \
             patch.object(app_module, '_build_stock_query_llm_prompt', return_value=''):
            gw.return_value = MagicMock(name='材料仓')
            resp = app_module._ai_stock_query_response('铜排够不够')
    finally:
        ctx.pop()
    reply = json.loads(resp.get_data())['reply']
    assert '充足' in reply, f"应含充足结论：{reply}"


# ---------- F2：流水问法判定 ----------

def test_f2_flow_questions_detected():
    assert app_module._ai_is_flow_query_question('上周进了多少铜排')
    assert app_module._ai_is_flow_query_question('本月指示灯用了多少')
    assert app_module._ai_is_flow_query_question('铜排出入库流水')


def test_f2_stock_questions_not_flow():
    assert not app_module._ai_is_flow_query_question('查一下铜排的库存')
    assert not app_module._ai_is_flow_query_question('铜排还有多少')


def test_f2_stock_query_excludes_flow_words():
    """查库存判定必须排除流水词，避免两个工具抢同一问题。"""
    assert not app_module._ai_is_stock_query_question('上周进了多少铜排')
    assert not app_module._ai_is_stock_query_question('本月铜排出库了多少')


# ---------- F2：同名多规格聚合（内存库真实查询） ----------

def test_f2_same_name_ids_aggregated():
    """同名多规格「铜排」应聚合全部规格流水，明细带 [规格] 标签。"""
    from models.master_data import Material
    from models.inventory import StockTransaction
    now = datetime.now()
    mats = []
    for code, spec in (('T_LP1', '100*10'), ('T_LP2', '50*5')):
        m = Material(code=code, name='铜排测试X', spec=spec, min_stock=0, reorder_point=0)
        db.session.add(m)
        mats.append(m)
    db.session.flush()
    db.session.add_all([
        StockTransaction(material_id=mats[0].id, transaction_type='in', quantity=5,
                         created_at=now - timedelta(days=1)),
        StockTransaction(material_id=mats[1].id, transaction_type='in', quantity=5,
                         created_at=now - timedelta(days=1)),
    ])
    db.session.commit()

    ctx = _login_ctx()
    try:
        with patch.object(app_module, '_ai_is_flow_query_question', return_value=True), \
             patch.object(app_module, '_ai_capability_allowed', return_value=True), \
             patch.object(app_module, '_ai_llm_parse_stock_intent', return_value=None), \
             patch.object(app_module, '_ai_find_materials_from_message',
                          side_effect=lambda msg, limit=8: mats), \
             patch.object(app_module, '_voice_llm_chat', return_value=None):
            resp = app_module._ai_flow_query_response('最近铜排测试X进了多少')
    finally:
        ctx.pop()
        StockTransaction.query.filter(
            StockTransaction.material_id.in_([m.id for m in mats]),
            StockTransaction.reference_id.is_(None)).delete(synchronize_session=False)
        Material.query.filter(Material.code.in_(['T_LP1', 'T_LP2'])).delete(
            synchronize_session=False)
        db.session.commit()

    assert resp is not None
    reply = json.loads(resp.get_data())['reply']
    assert '入库合计' in reply and '10' in reply, f"应聚合 2 规格 5+5=10：{reply}"
    assert '[100*10]' in reply and '[50*5]' in reply, f"明细应带规格标签：{reply}"


def test_f2_flow_query_mounted_in_dispatcher():
    """流水工具必须挂到 warehouse_insights 链路最前 + 独立工具表。"""
    assert getattr(app_module, '_ai_flow_query_response', None) is not None
    assert 'stock_flow_query' in app_module.AI_TOOL_DISPATCHERS
    # warehouse_insights 是闭包，无法直接查列表；用源码断言挂载点
    import inspect
    src = inspect.getsource(app_module._ai_warehouse_insights_response)
    assert '_ai_flow_query_response' in src, "流水查询应挂在 warehouse_insights 链路"
