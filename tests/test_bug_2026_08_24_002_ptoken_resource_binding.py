# -*- coding: utf-8 -*-
"""BUG-2026-08-24-002：打印 ptoken 资源绑定回归测试。

修复前：`print_token_or_login_required` 只验 ptoken 有效性与 10 分钟时效，
不校验 URL 路径中的单据 id 与 ptoken 绑定 PrintJob 的对应关系——一个泄露的
有效 ptoken 可在有效期内对 4 条打印路由重放，枚举任意单据打印页
（供应商/价格/数量/客户等商业数据批量泄露，只读）。

修复后：装饰器按路由声明的 job_type 校验绑定——
in_order/out_order/material_archive 比对 PrintJob.target_id 与路径 id，
label 比对 PrintJob.target_ids 与查询 ids 集合；不一致即走未授权（302 跳登录）。
Web 会话（已登录）路径不做绑定校验，行为不变。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (InOrder, Material, OutOrder, OutOrderItem, PrintJob, Unit,
                 User, Warehouse, db)  # noqa: E402
from utils import generate_print_token  # noqa: E402


def _login(client, username='admin'):
    return client.post(
        "/login",
        data={"username": username, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    """种子数据与 tests/test_print_queue.py 保持一致（打印页渲染已验证可用）。"""
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    admin = User(username="admin",
                 password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    db.session.add_all([wh, unit, admin])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    in_order = InOrder(order_no="IN-TEST-001", warehouse="默认仓", status="completed")
    out_order = OutOrder(order_no="OUT-TEST-001", warehouse="默认仓", status="completed")
    db.session.add_all([mat, in_order, out_order])
    db.session.flush()
    db.session.add(OutOrderItem(out_order_id=out_order.id, material_id=mat.id,
                                quantity=10, price=5, amount=50))
    db.session.commit()


def _ids():
    with app_module.app.app_context():
        return {
            'material': Material.query.filter_by(code='M001').first().id,
            'in_order': InOrder.query.filter_by(order_no='IN-TEST-001').first().id,
            'out_order': OutOrder.query.filter_by(order_no='OUT-TEST-001').first().id,
        }


def _job_and_token(job_type, target_id=None, target_ids=None):
    """建一条打印任务并为其签发 ptoken（模拟代理认领后的打印 URL）。"""
    with app_module.app.app_context():
        job = PrintJob(job_type=job_type, target_id=target_id, target_ids=target_ids)
        db.session.add(job)
        db.session.commit()
        return job.id, generate_print_token(job.id, job.workstation_id)


def _assert_rejected(resp):
    """未授权：302 跳登录页（浏览器）或 401/403；页面不得含任何单据数据。"""
    assert resp.status_code in (302, 401, 403)
    body = resp.get_data(as_text=True)
    assert 'OUT-TEST-001' not in body
    assert 'IN-TEST-001' not in body


@pytest.fixture()
def client():
    """未登录客户端：只走 ptoken 路径。"""
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed()
    yield app_module.app.test_client()


# ==================== 绑定总览（A9 要求的本名测试） ====================

def test_print_token_or_login_required(client):
    """装饰器绑定总览：正确单据放行；错误单据/类型/无 token/无效 token 拒绝。"""
    out_id = _ids()['out_order']
    _, token = _job_and_token('out_order', target_id=out_id)
    # 正确单据 → 200
    resp = client.get(f'/out_order/{out_id}/print?ptoken={token}')
    assert resp.status_code == 200
    assert 'OUT-TEST-001' in resp.get_data(as_text=True)
    # 同一 token 换单据 id → 拒绝（修复前为 200/404 直接到达视图，即本 BUG）
    _assert_rejected(client.get(f'/out_order/{out_id + 999}/print?ptoken={token}'))
    # 同一 token 换单据类型（in_order 路由）→ 拒绝
    _assert_rejected(client.get(f"/in_order/{_ids()['in_order']}/print?ptoken={token}"))
    # 无 token / 无效 token → 拒绝
    _assert_rejected(client.get(f'/out_order/{out_id}/print'))
    _assert_rejected(client.get(f'/out_order/{out_id}/print?ptoken=garbage'))


# ==================== 各 job_type 绑定 ====================

def test_ptoken_in_order_binding(client):
    in_id = _ids()['in_order']
    _, token = _job_and_token('in_order', target_id=in_id)
    assert client.get(f'/in_order/{in_id}/print?ptoken={token}').status_code == 200
    _assert_rejected(client.get(f'/in_order/{in_id + 999}/print?ptoken={token}'))


def test_ptoken_material_archive_binding(client):
    mat_id = _ids()['material']
    _, token = _job_and_token('material_archive', target_id=mat_id)
    resp = client.get(f'/material_archive/{mat_id}/print?ptoken={token}')
    assert resp.status_code == 200
    assert 'M001' in resp.get_data(as_text=True)
    _assert_rejected(client.get(f'/material_archive/{mat_id + 999}/print?ptoken={token}'))


def test_ptoken_label_ids_binding(client):
    mat_id = _ids()['material']
    _, token = _job_and_token('label', target_ids=str(mat_id))
    resp = client.get(f'/label/batch_print?ids={mat_id}&ptoken={token}')
    assert resp.status_code == 200
    # 超集 / 空集 / 不同物料 → 全部拒绝
    _assert_rejected(client.get(f'/label/batch_print?ids={mat_id},{mat_id + 1}&ptoken={token}'))
    _assert_rejected(client.get(f'/label/batch_print?ids=&ptoken={token}'))
    _assert_rejected(client.get(f'/label/batch_print?ids={mat_id + 1}&ptoken={token}'))


# ==================== 边界与既有行为 ====================

def test_ptoken_nonexistent_job_rejected(client):
    """ptoken 指向不存在的 PrintJob（任务已删）→ 拒绝。"""
    with app_module.app.app_context():
        token = generate_print_token(99999, None)
    _assert_rejected(client.get(f"/out_order/{_ids()['out_order']}/print?ptoken={token}"))


def test_ptoken_expired_rejected(client):
    """过期 ptoken（10 分钟时效）→ 拒绝。"""
    jid, _ = _job_and_token('out_order', target_id=_ids()['out_order'])
    with app_module.app.app_context(), \
            mock.patch('time.time', return_value=time.time() - 3600):
        old_token = generate_print_token(jid, None)
    _assert_rejected(client.get(f"/out_order/{_ids()['out_order']}/print?ptoken={old_token}"))


def test_ptoken_token_from_other_job_rejected(client):
    """同类型不同任务的 ptoken 也不能互换（job A 的 token 打不开 job B 的单据）。"""
    out_id = _ids()['out_order']
    _, token_a = _job_and_token('out_order', target_id=out_id)
    # job B 指向另一张（不存在的）出库单；用 B 的 token 开 A 的单据 → 拒绝
    _, token_b = _job_and_token('out_order', target_id=out_id + 999)
    _assert_rejected(client.get(f'/out_order/{out_id}/print?ptoken={token_b}'))
    # A 的 token 开 A 的单据 → 200（对照）
    assert client.get(f'/out_order/{out_id}/print?ptoken={token_a}').status_code == 200


def test_web_session_path_unchanged(client):
    """Web 会话（已登录）不做 ptoken 绑定校验，仍可打开任意单据打印页。"""
    _login(client)
    ids = _ids()
    assert client.get(f"/out_order/{ids['out_order']}/print").status_code == 200
    assert client.get(f"/in_order/{ids['in_order']}/print").status_code == 200
    assert client.get(f"/material_archive/{ids['material']}/print").status_code == 200
    assert client.get(f"/label/batch_print?ids={ids['material']}").status_code == 200
