# -*- coding: utf-8 -*-
"""R6 收口回归：单据表仓库过滤唯一判据（2026-09-25）。

根因：报表链路此前存在三种互斥的仓库判据——
  A. 单据表裸字符串匹配（InOrder.warehouse == filters['warehouse']）
  B. warehouse_id 外键 + 仓库级聚合（get_warehouse_stock_quantities）
  C. warehouse_id 优先 + location 字符串兜底（_warehouse_scoped_txn_condition）
A 最脆弱（改名即失配、混存即漏查、全程静默），且被手写复制到 7 处，
是「修一处漏一处」的温床（台账「仓库」根因出现 198 次，第一大来源）。

修复：新增 services/warehouse_scope.document_warehouse_filter 作为单据表
仓库过滤的唯一判据，7 处调用点全部改走该函数。本批为**纯收口、零行为变更**。

测试用例：
  T1. 仅名称：生成 [warehouse == 名称]
  T2. 仅编码：生成 [warehouse == 编码]
  T3. 名称+编码且不同：两个条件 OR
  T4. 名称与编码相同：不重复追加（只一个条件）
  T5. 两者皆空：返回 None（调用方跳过过滤，不得退化为全匹配以外的语义）
  T6. None 值：返回 None
  T7. 空白字符串：返回 None
  T8. 端到端：双仓单据按仓过滤不串仓（走 app._document_warehouse_scope）
  T9. 结构锁：app.py 不得再出现手写 match_any 仓库过滤片段
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, InOrder  # noqa: E402
from services.warehouse_scope import document_warehouse_filter  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


import pytest  # noqa: E402


@pytest.fixture()
def app_ctx():
    """每个用例独立的 app context（R7：顶层不得常驻 push/pop）。"""
    with app_module.app.app_context():
        yield


# ---------- T1-T7：判据函数行为 ----------

def test_t1_name_only():
    clause = document_warehouse_filter(InOrder, '材料仓', None)
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={'literal_binds': True}))
    assert 'in_order.warehouse = ' in compiled
    assert '材料仓' in compiled


def test_t2_code_only():
    clause = document_warehouse_filter(InOrder, None, 'WH001')
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={'literal_binds': True}))
    assert 'WH001' in compiled


def test_t3_name_and_code_distinct():
    clause = document_warehouse_filter(InOrder, '材料仓', 'WH001')
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={'literal_binds': True}))
    assert '材料仓' in compiled and 'WH001' in compiled
    assert ' OR ' in compiled.upper()


def test_t4_name_equals_code_no_dup():
    clause = document_warehouse_filter(InOrder, 'WH001', 'WH001')
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={'literal_binds': True}))
    # 名称与编码相同：只生成一个等值条件（不重复追加、不包 or_）
    assert compiled.count('in_order.warehouse =') == 1
    assert ' OR ' not in compiled.upper()


def test_t5_both_empty_returns_none():
    assert document_warehouse_filter(InOrder, '', '') is None


def test_t6_none_values_return_none():
    assert document_warehouse_filter(InOrder, None, None) is None


def test_t7_whitespace_returns_none():
    assert document_warehouse_filter(InOrder, '   ', '  ') is None


# ---------- T8：端到端双仓隔离 ----------

def test_t8_two_warehouse_isolation(app_ctx):
    _reset_db()
    orders = [
        ('IN-A', '项目仓'),
        ('IN-B', '库存仓'),
        ('IN-C', '项目仓'),
    ]
    for no, wh in orders:
        db.session.add(InOrder(order_no=no, warehouse=wh, status='completed'))
    db.session.commit()

    # 项目仓：应命中 2 条，且不含库存仓
    clause = app_module._document_warehouse_scope(
        InOrder, {'warehouse': '项目仓', 'warehouse_code': ''})
    rows = InOrder.query.filter(clause).all()
    assert sorted(r.order_no for r in rows) == ['IN-A', 'IN-C']

    # 库存仓：应命中 1 条
    clause = app_module._document_warehouse_scope(
        InOrder, {'warehouse': '库存仓', 'warehouse_code': ''})
    rows = InOrder.query.filter(clause).all()
    assert [r.order_no for r in rows] == ['IN-B']

    # 按编码命中同仓（历史混存场景）
    clause = app_module._document_warehouse_scope(
        InOrder, {'warehouse': '', 'warehouse_code': '项目仓'})
    rows = InOrder.query.filter(clause).all()
    assert sorted(r.order_no for r in rows) == ['IN-A', 'IN-C']


def test_t8b_no_warehouse_means_no_filter():
    """无条件时调用方必须跳过 filter，不得误加全匹配条件。"""
    assert app_module._document_warehouse_scope(
        InOrder, {'warehouse': '', 'warehouse_code': ''}) is None


# ---------- T9：结构锁，防手写片段回流 ----------

def test_t9_no_handwritten_match_any_left():
    import re as _re
    src = (APP_DIR / 'app.py').read_text(encoding='utf-8')
    # 只匹配真正的代码行（行首缩进后紧跟 match_any），排除注释与字符串说明
    leftover = _re.findall(
        r'^\s*match_any\s*=\s*\[.*?\.warehouse\s*==',
        src, flags=_re.MULTILINE)
    assert not leftover, (
        f'app.py 仍有 {len(leftover)} 处手写 match_any 仓库过滤片段，'
        '请改用 _document_warehouse_scope')
    assert '_document_warehouse_scope' in src
