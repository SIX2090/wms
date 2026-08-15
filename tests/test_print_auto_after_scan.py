# -*- coding: utf-8 -*-
"""PRINT-ROUTING-F01-P2 回归测试：扫码后自动创建定向打印任务。

覆盖：
- Android 原生扫码入库（/api/inbound）成功后按路由规则自动创建 in_order 定向任务
- Android 原生扫码出库（/api/outbound）成功后按路由规则自动创建 out_order 定向任务
- 手机网页扫码提交（/mobile/api/scan_submit）mode=in/out 成功后自动创建定向任务
- 未配置路由规则时不阻塞业务操作，且不产生打印任务
"""
from __future__ import annotations

import os
import sys
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
from app import (PrintDevice, PrintJob, PrintRouteRule, PrintWorkstation,
                 User, Warehouse, db)  # noqa: E402


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """admin + 默认仓库 + 物料。"""
    from app import Material, Unit
    db.session.add(User(
        username="admin", password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100, price=5)
    db.session.add(mat)
    db.session.commit()
    return wh, mat


def _seed_route(business_event, warehouse):
    """为指定业务事件创建在线工作站 + 打印机 + 路由规则。"""
    ws = PrintWorkstation(
        code=f'WS-{business_event}', name=f'{business_event}工作站',
        device_id=f'device-{business_event}', warehouse_id=warehouse.id,
        status='online', enabled=True,
    )
    db.session.add(ws)
    db.session.flush()
    printer = PrintDevice(
        workstation_id=ws.id, system_name=f'Printer-{business_event}',
        display_name=f'{business_event}打印机', printer_type='mixed',
        enabled=True, status='online',
    )
    db.session.add(printer)
    db.session.flush()
    db.session.add(PrintRouteRule(
        name=f'{business_event}路由', business_event=business_event,
        warehouse_id=warehouse.id, workstation_id=ws.id, printer_id=printer.id,
        priority=10, enabled=True,
    ))
    ws_id = ws.id
    printer_id = printer.id
    db.session.commit()
    return ws_id, printer_id


def _seed_warehouse_stock(material, warehouse, qty):
    """写入仓库级库存流水（库位管理关闭时 get_warehouse_stock_quantities 据此汇总）。"""
    from datetime import datetime
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id, transaction_type='in', quantity=qty,
        location=warehouse.name, reference_type='test', remark='测试库存',
        created_at=datetime.now(),
    ))
    db.session.commit()


def _login(client, username='admin'):
    return client.post(
        "/login",
        data={"username": username, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _bearer_headers(client):
    """通过原生登录接口换取 Bearer Token。"""
    resp = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    token = resp.get_json()["data"]["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_base()
    c = app_module.app.test_client()
    _login(c)
    yield c


# ==================== Android 原生扫码入库 ====================

def test_enqueue_auto_print_job(client):
    """enqueue_auto_print_job 有路由时创建定向任务，无路由时返回 None。"""
    from routes.print_queue import enqueue_auto_print_job
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code='RWH0').first()
        ws_id, printer_id = _seed_route('in_order', wh)
        # 有路由：创建定向任务
        job = enqueue_auto_print_job(
            'in_order', 999, wh.name, created_by=1, source_event='scan_inbound',
        )
        assert job is not None
        assert job.workstation_id == ws_id
        assert job.printer_id == printer_id
        assert job.source_event == 'scan_inbound'
        db.session.commit()
        # 无路由（out_order 未配置）：返回 None 且不新增任务
        pre_count = PrintJob.query.count()
        none_job = enqueue_auto_print_job('out_order', 999, wh.name, source_event='scan_outbound')
        assert none_job is None
        assert PrintJob.query.count() == pre_count
        db.session.rollback()


def test_android_inbound_auto_creates_directed_job(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code='RWH0').first()
        ws_id, printer_id = _seed_route('in_order', wh)
    headers = _bearer_headers(client)
    resp = client.post("/api/inbound", json={
        "lines": [{"material_code": "M001", "quantity": 3}],
    }, headers=headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    order_no = resp.get_json()["data"]["order_no"]
    with app_module.app.app_context():
        from app import InOrder
        order = InOrder.query.filter_by(order_no=order_no).one()
        job = PrintJob.query.filter_by(target_id=order.id, job_type='in_order').one()
        assert job.status == 'pending'
        assert job.workstation_id == ws_id
        assert job.printer_id == printer_id
        assert job.route_rule_id is not None
        assert job.source_event == 'scan_inbound'
        assert job.created_by is not None


# ==================== Android 原生扫码出库 ====================

def test_android_outbound_auto_creates_directed_job(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code='RWH0').first()
        ws_id, printer_id = _seed_route('out_order', wh)
    headers = _bearer_headers(client)
    resp = client.post("/api/outbound", json={
        "lines": [{"material_code": "M001", "quantity": 2}],
    }, headers=headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    order_no = resp.get_json()["data"]["order_no"]
    with app_module.app.app_context():
        from app import OutOrder
        order = OutOrder.query.filter_by(order_no=order_no).one()
        job = PrintJob.query.filter_by(target_id=order.id, job_type='out_order').one()
        assert job.status == 'pending'
        assert job.workstation_id == ws_id
        assert job.printer_id == printer_id
        assert job.route_rule_id is not None
        assert job.source_event == 'scan_outbound'


# ==================== 手机网页扫码提交 ====================

def _seed_no_location():
    from app import set_system_setting
    set_system_setting("location_management_enabled", "0")
    db.session.commit()


def test_mobile_scan_submit_in_auto_creates_directed_job(client):
    with app_module.app.app_context():
        _seed_no_location()
        wh = Warehouse.query.filter_by(code='RWH0').first()
        _seed_route('in_order', wh)
    resp = client.post("/mobile/api/scan_submit", json={
        "mode": "in", "code": "M001", "quantity": 3,
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    order_no = resp.get_json()["data"]["order_no"]
    with app_module.app.app_context():
        from app import InOrder
        order = InOrder.query.filter_by(order_no=order_no).one()
        assert PrintJob.query.filter_by(
            target_id=order.id, job_type='in_order', source_event='scan_submit_in'
        ).count() == 1


def test_mobile_scan_submit_out_auto_creates_directed_job(client):
    with app_module.app.app_context():
        _seed_no_location()
        wh = Warehouse.query.filter_by(code='RWH0').first()
        from app import Material
        _seed_warehouse_stock(Material.query.filter_by(code='M001').one(), wh, 50)
        _seed_route('out_order', wh)
    resp = client.post("/mobile/api/scan_submit", json={
        "mode": "out", "code": "M001", "quantity": 2,
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    order_no = resp.get_json()["data"]["order_no"]
    with app_module.app.app_context():
        from app import OutOrder
        order = OutOrder.query.filter_by(order_no=order_no).one()
        assert PrintJob.query.filter_by(
            target_id=order.id, job_type='out_order', source_event='scan_submit_out'
        ).count() == 1


# ==================== 未配置路由时不阻塞且不产生任务 ====================

def test_android_inbound_no_route_still_succeeds_without_job(client):
    headers = _bearer_headers(client)
    resp = client.post("/api/inbound", json={
        "lines": [{"material_code": "M001", "quantity": 1}],
    }, headers=headers)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    order_no = resp.get_json()["data"]["order_no"]
    with app_module.app.app_context():
        from app import InOrder
        order = InOrder.query.filter_by(order_no=order_no).one()
        assert PrintJob.query.filter_by(target_id=order.id).count() == 0