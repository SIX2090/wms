# -*- coding: utf-8 -*-
"""远程打印队列（print_queue）回归测试。

覆盖：
- 创建任务（out_order / in_order / label / material_archive 四种 job_type）
- 参数校验（非法 job_type、缺失 target_id、copies 越界）
- next 拉取顺序（FIFO）+ 状态置 printing
- complete / fail 状态流转
- 僵尸任务回收（printing 超时 → pending/failed）
- 单台电脑场景下不重复拉取
- 物料档案打印页渲染（/material_archive/<id>/print）
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

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
from app import (Material, OutOrder, PrintDevice, PrintJob, PrintRouteRule,
                 PrintWorkstation, User, Warehouse, db)  # noqa: E402


def _login(client, username='admin'):
    return client.post(
        "/login",
        data={"username": username, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    db.session.add(User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    db.session.commit()


def _seed_out_order():
    """建一张草稿出库单用于打印测试。"""
    from app import InOrder, OutOrderItem, Material, Unit
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100)
    in_order = InOrder(order_no="IN-TEST-001", warehouse="默认仓", status="completed")
    db.session.add_all([mat, in_order])
    db.session.flush()
    order = OutOrder(order_no="OUT-TEST-001", warehouse="默认仓", status="completed")
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(out_order_id=order.id, material_id=mat.id, quantity=10, price=5, amount=50))
    db.session.commit()
    return order


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _seed_out_order()
    c = app_module.app.test_client()
    _login(c)
    yield c


# ==================== 创建任务 ====================

def test_create_out_order_job(client):
    """领料单打印任务创建成功。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'out_order', 'target_id': 1, 'copies': 2,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['job_id'] > 0
    with app_module.app.app_context():
        job = PrintJob.query.get(data['job_id'])
        assert job.job_type == 'out_order'
        assert job.target_id == 1
        assert job.copies == 2
        assert job.status == 'pending'


def test_create_in_order_job(client):
    """采购入库单打印任务创建成功。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'in_order', 'target_id': 1,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'success'


def test_create_label_job(client):
    """物料标签打印任务创建成功（target_ids 为逗号分隔字符串）。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'label', 'target_ids': '1',
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    data = resp.get_json()
    with app_module.app.app_context():
        job = PrintJob.query.get(data['job_id'])
        assert job.target_ids == '1'
        assert job.target_id is None


def test_create_material_archive_job(client):
    """物料档案打印任务创建成功（target_id 为物料 ID）。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'material_archive', 'target_id': 1,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['job_id'] > 0
    with app_module.app.app_context():
        job = PrintJob.query.get(data['job_id'])
        assert job.job_type == 'material_archive'
        assert job.target_id == 1
        assert job.status == 'pending'


def test_material_archive_nonexistent_material(client):
    """物料不存在时创建物料档案打印任务返回 404。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'material_archive', 'target_id': 99999,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 404
    assert '物料不存在' in resp.get_json()['msg']


# ==================== 参数校验 ====================

def test_invalid_job_type(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'invalid', 'target_id': 1,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 400
    assert 'job_type' in resp.get_json()['msg']


def test_missing_target_id(client):
    """out_order 类型缺失 target_id 应被拒。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'out_order',
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 400
    assert 'target_id' in resp.get_json()['msg']


def test_label_missing_target_ids(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'label',
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 400
    assert 'target_ids' in resp.get_json()['msg']


def test_copies_out_of_range(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    resp = client.post('/print_queue/jobs', json={
        'job_type': 'out_order', 'target_id': 1, 'copies': 100,
    }, headers={'X-CSRFToken': csrf})
    assert resp.status_code == 400


# ==================== next 拉取 ====================

def test_next_returns_oldest_pending(client):
    """next 返回最早创建的 pending 任务，且状态置为 printing。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    # 创建两条任务
    r1 = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                     headers={'X-CSRFToken': csrf}).get_json()
    r2 = client.post('/print_queue/jobs', json={'job_type': 'in_order', 'target_id': 1},
                     headers={'X-CSRFToken': csrf}).get_json()
    # next 应返回第一条
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['job']['id'] == r1['job_id']
    assert data['job']['job_type'] == 'out_order'
    assert data['job']['print_url'] == '/out_order/1/print'
    # 再 next 返回第二条
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert data['job']['id'] == r2['job_id']
    # 再 next 队列空
    resp = client.get('/print_queue/next')
    assert resp.get_json()['status'] == 'empty'
    # 数据库状态确认
    with app_module.app.app_context():
        jobs = PrintJob.query.order_by(PrintJob.id.asc()).all()
        assert jobs[0].status == 'printing'
        assert jobs[1].status == 'printing'


def test_next_no_pending_returns_empty(client):
    resp = client.get('/print_queue/next')
    assert resp.status_code == 200
    assert resp.get_json()['status'] == 'empty'


def test_label_print_url(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    client.post('/print_queue/jobs', json={'job_type': 'label', 'target_ids': '1'},
                headers={'X-CSRFToken': csrf})
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert data['job']['print_url'] == '/label/batch_print?ids=1'


def test_material_archive_print_url(client):
    """物料档案任务的 print_url 指向档案打印页。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    client.post('/print_queue/jobs', json={'job_type': 'material_archive', 'target_id': 1},
                headers={'X-CSRFToken': csrf})
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert data['job']['job_type'] == 'material_archive'
    assert data['job']['print_url'] == '/material_archive/1/print'


def test_material_archive_print_page(client):
    """物料档案打印页可正常渲染（含物料信息与档案图片区）。"""
    from app import MaterialImage
    with app_module.app.app_context():
        material = Material.query.filter_by(code='M001').first()
        if material and MaterialImage.query.filter_by(material_id=material.id).count() == 0:
            db.session.add(MaterialImage(material_id=material.id, image='uploads/material_images/test.jpg', sort_order=0))
            db.session.commit()
        mat_id = material.id
    resp = client.get(f'/material_archive/{mat_id}/print')
    assert resp.status_code == 200
    assert '物料档案' in resp.get_data(as_text=True)
    assert 'M001' in resp.get_data(as_text=True)


def test_material_archive_print_page_missing(client):
    """物料不存在时打印页返回 404。"""
    resp = client.get('/material_archive/99999/print')
    assert resp.status_code == 404


def test_autoprint_page_renders(client):
    """BUG-2026-08-19-008：autoprint 打印页渲染即 500。

    _autoprint_script.html 原 `request.args.get('copies', 1, type=int)` 在
    Jinja 作用域里 int 未定义，带 autoprint=1（代理认领任务后必带）打开
    任何打印页都抛 UndefinedError → 500，整条代理静默打印链路断裂。"""
    with app_module.app.app_context():
        material = Material.query.filter_by(code='M001').first()
        mat_id = material.id
    resp = client.get(f'/material_archive/{mat_id}/print?autoprint=1&copies=2&ptoken=x')
    assert resp.status_code == 200
    assert 'var copies = 2;' in resp.get_data(as_text=True)
    # 同一 include 的出库单/入库单打印页同样必须可渲染
    for url in ('/out_order/1/print?autoprint=1', '/in_order/1/print?autoprint=1'):
        assert client.get(url).status_code == 200


def test_autoprint_page_closes_window_after_print(client):
    """BUG-2026-08-19-009：autoprint 打印页打完份数后必须 window.close()。

    打印代理以 kiosk-printing 打开打印页并等待浏览器进程退出；页面不
    自关则代理等满 print_timeout（默认 120s）后强杀进程，并把已出纸的
    任务上报为 failed。"""
    with app_module.app.app_context():
        material = Material.query.filter_by(code='M001').first()
        mat_id = material.id
    resp = client.get(f'/material_archive/{mat_id}/print?autoprint=1&copies=2&ptoken=x')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'window.close' in html
    # 只在 autoprint 模式自关，人工打开打印页不受影响
    resp = client.get(f'/material_archive/{mat_id}/print')
    assert 'window.close' not in resp.get_data(as_text=True)


def test_copies_in_url(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1, 'copies': 3},
                headers={'X-CSRFToken': csrf})
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert 'copies=3' in data['job']['print_url']


# ==================== complete / fail ====================

def test_complete_job(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    r = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                    headers={'X-CSRFToken': csrf}).get_json()
    client.get('/print_queue/next')  # 拉取并置 printing
    resp = client.post(f'/print_queue/jobs/{r["job_id"]}/complete', json={},
                       headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        assert job.status == 'done'
        assert job.printed_at is not None


def test_fail_job(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    r = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                    headers={'X-CSRFToken': csrf}).get_json()
    client.get('/print_queue/next')
    resp = client.post(f'/print_queue/jobs/{r["job_id"]}/fail',
                       json={'error_msg': '打印机离线'},
                       headers={'X-CSRFToken': csrf})
    assert resp.status_code == 200
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        assert job.status == 'failed'
        assert job.error_msg == '打印机离线'


# ==================== 僵尸任务回收 ====================

def test_stale_printing_job_recycled_to_pending(client):
    """printing 超过 5 分钟且未达 MAX_ATTEMPTS → 重置 pending。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    r = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                    headers={'X-CSRFToken': csrf}).get_json()
    client.get('/print_queue/next')  # 置 printing
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        # 模拟 6 分钟前创建并已拉取
        job.created_at = datetime.now() - timedelta(minutes=6)
        job.attempts = 1
        db.session.commit()
    # 再次 next 应回收并重新拉取
    resp = client.get('/print_queue/next')
    data = resp.get_json()
    assert data['status'] == 'success'
    assert data['job']['id'] == r['job_id']
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        assert job.status == 'printing'


def test_stale_printing_job_failed_after_max_attempts(client):
    """printing 超时且 attempts >= MAX_ATTEMPTS → 标记 failed。"""
    from routes.print_queue import MAX_ATTEMPTS
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    r = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                    headers={'X-CSRFToken': csrf}).get_json()
    client.get('/print_queue/next')
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        job.created_at = datetime.now() - timedelta(minutes=6)
        job.attempts = MAX_ATTEMPTS
        db.session.commit()
    resp = client.get('/print_queue/next')
    assert resp.get_json()['status'] == 'empty'  # 已 failed，不再返回
    with app_module.app.app_context():
        job = PrintJob.query.get(r['job_id'])
        assert job.status == 'failed'
        assert '超时' in (job.error_msg or '')


# ==================== 单台电脑不重复拉取 ====================

def test_no_duplicate_pull(client):
    """同一任务不会被拉取两次（拉取即置 printing）。"""
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    r = client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                    headers={'X-CSRFToken': csrf}).get_json()
    first = client.get('/print_queue/next').get_json()
    second = client.get('/print_queue/next').get_json()
    assert first['status'] == 'success'
    assert second['status'] == 'empty'
    assert first['job']['id'] == r['job_id']


# ==================== station / stats ====================

def test_station_page(client):
    resp = client.get('/print_queue/station')
    assert resp.status_code == 200
    assert b'print_station' in resp.data or b'\xe6\x89\x93\xe5\x8d\xb0\xe5\xb7\xa5\xe4\xbd\x9c\xe7\xab\x99' in resp.data  # "打印工作站"


def test_stats(client):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    client.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1},
                headers={'X-CSRFToken': csrf})
    client.post('/print_queue/jobs', json={'job_type': 'in_order', 'target_id': 1},
                headers={'X-CSRFToken': csrf})
    client.get('/print_queue/next')  # 一条变 printing
    resp = client.get('/print_queue/stats')
    data = resp.get_json()
    assert data['status'] == 'success'
    s = data['stats']
    assert s['pending'] == 1
    assert s['printing'] == 1
    assert s['done'] == 0
    assert s['failed'] == 0


# ==================== 未登录拒绝访问 ====================

def test_unauthenticated_create_rejected(client):
    """未登录用户不能创建打印任务。"""
    c = app_module.app.test_client()  # 全新未登录 client
    resp = c.post('/print_queue/jobs', json={'job_type': 'out_order', 'target_id': 1})
    # flask_login 默认 302 重定向到 /login
    assert resp.status_code in (302, 401)


def test_non_warehouse_user_cannot_report_print_result(client):
    with app_module.app.app_context():
        db.session.add(User(
            username='production',
            password_hash=generate_password_hash('admin'),
            role='production', must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    _login(c, username='production')
    resp = c.post(
        '/print_queue/jobs/1/complete',
        json={},
        headers={'X-Requested-With': 'XMLHttpRequest'},
    )
    assert resp.status_code == 403


def test_api_client_posts_json_with_content_type():
    api_js = (APP_DIR / 'static' / 'js' / 'api.js').read_text(encoding='utf-8')
    assert "headers['Content-Type'] = 'application/json';" in api_js
    assert 'data != null && !isFormData' in api_js


def test_routed_job_can_only_be_claimed_by_target_workstation(client):
    with app_module.app.app_context():
        warehouse = Warehouse.query.filter_by(code='RWH0').first()
        target = PrintWorkstation(
            code='RECEIVING-PC', name='收货台电脑', device_id='device-receiving',
            warehouse_id=warehouse.id, status='online', enabled=True,
        )
        other = PrintWorkstation(
            code='ISSUE-PC', name='发料台电脑', device_id='device-issue',
            warehouse_id=warehouse.id, status='online', enabled=True,
        )
        db.session.add_all([target, other])
        db.session.flush()
        printer = PrintDevice(
            workstation_id=target.id, system_name='Zebra ZD421',
            display_name='收货标签机', printer_type='label', enabled=True,
            status='online',
        )
        db.session.add(printer)
        db.session.flush()
        db.session.add(PrintRouteRule(
            name='主仓领料单', business_event='out_order', warehouse_id=warehouse.id,
            workstation_id=target.id, printer_id=printer.id, priority=10, enabled=True,
        ))
        target_id = target.id
        other_id = other.id
        printer_id = printer.id
        db.session.commit()

    with client.session_transaction() as sess:
        csrf = sess.get('csrf_token', '')
    created = client.post('/print_queue/jobs', json={
        'job_type': 'out_order', 'target_id': 1,
    }, headers={'X-CSRFToken': csrf}).get_json()
    with app_module.app.app_context():
        job = db.session.get(PrintJob, created['job_id'])
        assert job.workstation_id == target_id
        assert job.printer_id == printer_id
        assert job.route_rule_id is not None

    denied = client.get(f'/print_queue/workstations/{other_id}/next')
    assert denied.status_code == 200
    assert denied.get_json()['status'] == 'empty'

    claimed = client.get(f'/print_queue/workstations/{target_id}/next')
    assert claimed.status_code == 200
    assert claimed.get_json()['job']['id'] == created['job_id']
    assert claimed.get_json()['job']['printer_id'] == printer_id
    assert claimed.get_json()['job']['printer_system_name'] == 'Zebra ZD421'


def test_workstation_queue_requires_admin(client):
    with app_module.app.app_context():
        db.session.add(User(
            username='warehouse-user',
            password_hash=generate_password_hash('admin'),
            role='warehouse', must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    _login(c, username='warehouse-user')
    response = c.get('/print_queue/workstations/1/next', headers={
        'X-Requested-With': 'XMLHttpRequest',
    })
    assert response.status_code == 403
