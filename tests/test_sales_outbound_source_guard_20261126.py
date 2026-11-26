# -*- coding: utf-8 -*-
"""BUG-2026-11-26-009: 销售出库强制来源订单开关与全入口防旁路回归，及独立三账巡检脚本回归。"""
from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
import sys

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
from app import db
from tests.document_revision_client import document_post

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import run_scheduled_ledger_check as ledger_runner  # noqa: E402


@pytest.fixture
def sales_guard_case(monkeypatch):
    monkeypatch.setitem(app_module.app.config, 'TESTING', True)
    monkeypatch.setitem(app_module.app.config, 'WTF_CSRF_ENABLED', False)
    with app_module.app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        admin = app_module.User(
            username='sales-guard-admin',
            password_hash=generate_password_hash('fixture-pw'),
            role='admin',
            must_change_password=False,
        )
        wh_a = app_module.Warehouse(code='SG-A', name='销售甲仓', status='active', is_default=True)
        wh_b = app_module.Warehouse(code='SG-B', name='销售乙仓', status='active')
        unit = app_module.Unit(code='SG-U', name='个')
        cat = app_module.MaterialCategory(code='SG-C', name='销售分类')
        cust = app_module.Customer(code='SG-CUST', name='测试客户甲')
        db.session.add_all([admin, wh_a, wh_b, unit, cat, cust])
        db.session.flush()
        mat = app_module.Material(
            code='SG-M1', name='销售测试件', unit_id=unit.id, category_id=cat.id,
            stock=100.0, price=10.0,
        )
        mat2 = app_module.Material(
            code='SG-M2', name='销售测试件二', unit_id=unit.id, category_id=cat.id,
            stock=50.0, price=20.0,
        )
        db.session.add_all([mat, mat2])
        db.session.flush()
        db.session.add_all([
            app_module.StockTransaction(
                material_id=mat.id, warehouse_id=wh_a.id, location=wh_a.name,
                quantity=60.0, transaction_type='opening', reference_type='opening_stock', reference_id=1,
            ),
            app_module.StockTransaction(
                material_id=mat.id, warehouse_id=wh_b.id, location=wh_b.name,
                quantity=40.0, transaction_type='opening', reference_type='opening_stock', reference_id=2,
            ),
            app_module.StockTransaction(
                material_id=mat2.id, warehouse_id=wh_a.id, location=wh_a.name,
                quantity=50.0, transaction_type='opening', reference_type='opening_stock', reference_id=3,
            ),
        ])
        so = app_module.SalesOrder(
            order_no='SO-SG-001', date=date.today(), customer_id=cust.id,
            warehouse=wh_a.name, warehouse_id=wh_a.id, status='confirmed',
            shipment_status='pending', operator_id=admin.id,
        )
        db.session.add(so)
        db.session.flush()
        soi = app_module.SalesOrderItem(
            sales_order_id=so.id, material_id=mat.id,
            quantity=10.0, shipped_quantity=0.0, price=10.0, amount=100.0,
        )
        db.session.add(soi)
        app_module.set_system_setting('location_management_enabled', '0')
        db.session.commit()
        ids = {
            'admin': admin.id,
            'wh_a': wh_a.id,
            'wh_b': wh_b.id,
            'cust': cust.id,
            'mat': mat.id,
            'mat2': mat2.id,
            'so': so.id,
            'soi': soi.id,
        }
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(ids['admin'])
        sess['_fresh'] = True
    yield client, ids
    with app_module.app.app_context():
        db.session.remove()


def test_sales_outbound_requires_order(sales_guard_case):
    """A9 入口测试：sales_outbound_requires_order 默认开启且响应系统设置切换。"""
    _, _ = sales_guard_case
    with app_module.app.app_context():
        assert 'sales_outbound_requires_order' in app_module.SYSTEM_SETTING_DEFINITIONS
        assert app_module.sales_outbound_requires_order() is True
        app_module.set_system_setting('sales_outbound_requires_order', '0')
        db.session.commit()
        assert app_module.sales_outbound_requires_order() is False
        app_module.set_system_setting('sales_outbound_requires_order', '1')
        db.session.commit()
        assert app_module.sales_outbound_requires_order() is True


def test_unsourced_sales_outbound_blocked_across_save_complete_batch_copy_item_and_mobile(sales_guard_case):
    """默认开启时，无来源销售出库在保存、单张完成、批量完成、复制、裸增行和手机确认均被拦截。"""
    client, ids = sales_guard_case

    # 1. 页面提示可见
    add_page = client.get('/out_order/add?type=sale')
    assert add_page.status_code == 200
    assert 'data-sales-source-required-notice' in add_page.get_data(as_text=True)

    # 2. 直接保存无来源销售出库被拒，且不落库
    r_save = document_post(client, '/out_order/add', json={
        'date': date.today().isoformat(),
        'warehouse_id': ids['wh_a'],
        'business_type': '销售出库',
        'customer': '测试客户甲',
        'items': [{'code': 'SG-M1', 'quantity': 5, 'price': 10}],
    })
    assert r_save.get_json()['status'] == 'error', r_save.get_json()
    assert '来源销售订单' in r_save.get_json()['msg']
    with app_module.app.app_context():
        assert app_module.OutOrder.query.count() == 0

    # 3. 构造存量无来源销售出库草稿，验证复制/裸增行/单张完成/批量完成/手机确认均被拦
    with app_module.app.app_context():
        legacy = app_module.OutOrder(
            order_no='SO-LEGACY-NOSRC', date=date.today(),
            business_type='销售出库', warehouse='销售甲仓',
            customer='测试客户甲', status='pending', operator_id=ids['admin'],
        )
        db.session.add(legacy)
        db.session.flush()
        db.session.add(app_module.OutOrderItem(
            out_order_id=legacy.id, material_id=ids['mat'],
            quantity=5.0, price=10.0, amount=50.0,
        ))
        db.session.commit()
        legacy_id = legacy.id
        txn_before = app_module.StockTransaction.query.count()

    r_copy = document_post(client, f'/out_order/{legacy_id}/copy', json={})
    assert r_copy.status_code == 409, r_copy.get_json()

    r_add_item = document_post(client, f'/out_order/{legacy_id}/item/add', data={
        'material_code': 'SG-M2', 'quantity': '2', 'price': '20',
    })
    assert r_add_item.get_json()['status'] == 'error', r_add_item.get_json()

    r_complete = document_post(client, f'/out_order/{legacy_id}/complete?force=true', json={})
    assert r_complete.get_json()['status'] == 'error', r_complete.get_json()
    assert '来源销售订单' in r_complete.get_json()['msg']

    r_batch = client.post('/out_order/batch_complete', json={'ids': [legacy_id]})
    assert r_batch.status_code == 400, r_batch.get_json()
    assert r_batch.get_json()['completed'] == 0

    r_mobile = client.post(
        f'/mobile/api/scan_draft_confirm/{legacy_id}',
        json={'order_type': 'out'},
    )
    assert r_mobile.status_code == 400, r_mobile.get_json()
    assert '来源销售订单' in r_mobile.get_json()['msg']

    with app_module.app.app_context():
        assert db.session.get(app_module.OutOrder, legacy_id).status == 'pending'
        assert db.session.get(app_module.Material, ids['mat']).stock == 100.0
        assert app_module.StockTransaction.query.count() == txn_before


def test_mixed_sourced_and_unsourced_rows_blocked(sales_guard_case):
    """部分行有来源、部分行无来源的销售出库也会被拦截，不能夹带无来源行。"""
    _, ids = sales_guard_case
    with app_module.app.app_context():
        draft = app_module.OutOrder(
            order_no='SO-MIXED-001', date=date.today(),
            business_type='销售出库', warehouse='销售甲仓',
            customer='测试客户甲', status='pending', operator_id=ids['admin'],
        )
        db.session.add(draft)
        db.session.flush()
        db.session.add_all([
            app_module.OutOrderItem(
                out_order_id=draft.id, material_id=ids['mat'],
                source_sales_order_item_id=ids['soi'], quantity=3.0, price=10.0, amount=30.0,
            ),
            app_module.OutOrderItem(
                out_order_id=draft.id, material_id=ids['mat2'],
                source_sales_order_item_id=None, quantity=2.0, price=20.0, amount=40.0,
            ),
        ])
        db.session.commit()
        ok, msg = app_module.sales_outbound_remaining_check(draft)
        assert ok is False
        assert '来源销售订单' in msg


def test_sourced_sales_outbound_mobile_confirm_checks_remaining_and_syncs_shipped(sales_guard_case):
    """手机端确认关联销售出库草稿同样拦截超发，并在合法确认后回写 shipped_quantity。"""
    client, ids = sales_guard_case
    with app_module.app.app_context():
        over_draft = app_module.OutOrder(
            order_no='SO-MOB-OVER', date=date.today(),
            business_type='销售出库', warehouse='销售甲仓',
            customer='测试客户甲', source_sales_order_id=ids['so'],
            status='pending', operator_id=ids['admin'],
        )
        ok_draft = app_module.OutOrder(
            order_no='SO-MOB-OK', date=date.today(),
            business_type='销售出库', warehouse='销售甲仓',
            customer='测试客户甲', source_sales_order_id=ids['so'],
            status='pending', operator_id=ids['admin'],
        )
        db.session.add_all([over_draft, ok_draft])
        db.session.flush()
        db.session.add_all([
            app_module.OutOrderItem(
                out_order_id=over_draft.id, material_id=ids['mat'],
                source_sales_order_item_id=ids['soi'], quantity=15.0, price=10.0, amount=150.0,
            ),
            app_module.OutOrderItem(
                out_order_id=ok_draft.id, material_id=ids['mat'],
                source_sales_order_item_id=ids['soi'], quantity=4.0, price=10.0, amount=40.0,
            ),
        ])
        db.session.commit()
        over_id, ok_id = over_draft.id, ok_draft.id

    r_over = client.post(f'/mobile/api/scan_draft_confirm/{over_id}', json={'order_type': 'out'})
    assert r_over.status_code == 400, r_over.get_json()
    assert '超过' in r_over.get_json()['msg']

    r_ok = client.post(f'/mobile/api/scan_draft_confirm/{ok_id}', json={'order_type': 'out'})
    assert r_ok.status_code == 200 and r_ok.get_json()['status'] == 'success', r_ok.get_json()

    with app_module.app.app_context():
        assert db.session.get(app_module.OutOrder, ok_id).status == 'completed'
        assert db.session.get(app_module.SalesOrderItem, ids['soi']).shipped_quantity == 4.0
        assert db.session.get(app_module.SalesOrder, ids['so']).shipment_status == 'partial'
        assert db.session.get(app_module.Material, ids['mat']).stock == 96.0


def test_setting_disabled_allows_unsourced_and_other_out_unaffected(sales_guard_case):
    """关闭开关后兼容免关联销售出库；开启开关时「其他出库」不受影响。"""
    client, ids = sales_guard_case

    # 开关开启时，其他出库照常保存并完成
    r_other = document_post(client, '/out_order/add', json={
        'date': date.today().isoformat(),
        'warehouse_id': ids['wh_a'],
        'business_type': '其他出库',
        'customer': '测试客户甲',
        'items': [{'code': 'SG-M1', 'quantity': 3, 'price': 10}],
    })
    assert r_other.status_code == 200 and r_other.get_json()['status'] == 'success', r_other.get_json()
    other_id = r_other.get_json()['id']
    r_other_done = document_post(client, f'/out_order/{other_id}/complete?force=true', json={})
    assert r_other_done.get_json()['status'] == 'success', r_other_done.get_json()

    # 关闭开关后允许无来源销售出库保存与完成
    with app_module.app.app_context():
        app_module.set_system_setting('sales_outbound_requires_order', '0')
        db.session.commit()
    r_free = document_post(client, '/out_order/add', json={
        'date': date.today().isoformat(),
        'warehouse_id': ids['wh_a'],
        'business_type': '销售出库',
        'customer': '测试客户甲',
        'items': [{'code': 'SG-M1', 'quantity': 2, 'price': 10}],
    })
    assert r_free.status_code == 200 and r_free.get_json()['status'] == 'success', r_free.get_json()
    free_id = r_free.get_json()['id']
    r_free_done = document_post(client, f'/out_order/{free_id}/complete?force=true', json={})
    assert r_free_done.get_json()['status'] == 'success', r_free_done.get_json()
    with app_module.app.app_context():
        assert db.session.get(app_module.Material, ids['mat']).stock == 95.0


def _create_standalone_ledger_db(path: Path, *, use_bins: bool = False):
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE system_setting (id INTEGER PRIMARY KEY, key TEXT, value TEXT);
        CREATE TABLE warehouse (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
        CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, stock REAL);
        CREATE TABLE stock_transaction (
            id INTEGER PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,
            location TEXT, quantity REAL, reference_type TEXT, reference_id INTEGER
        );
        CREATE TABLE location_inventory (
            id INTEGER PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,
            location TEXT, quantity REAL
        );
        CREATE TABLE notification (
            id INTEGER PRIMARY KEY, type TEXT NOT NULL, target_id INTEGER NOT NULL,
            title TEXT NOT NULL, content TEXT NOT NULL, is_read BOOLEAN NOT NULL,
            created_at DATETIME NOT NULL
        );
        CREATE TABLE in_order (id INTEGER PRIMARY KEY, order_no TEXT, warehouse TEXT);
        CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT, warehouse TEXT);
        CREATE TABLE adjustment_order (id INTEGER PRIMARY KEY, adjustment_no TEXT, warehouse TEXT);
        CREATE TABLE after_sale_out_order (id INTEGER PRIMARY KEY, order_no TEXT, warehouse TEXT);
        CREATE TABLE production_requisition (id INTEGER PRIMARY KEY, req_no TEXT, warehouse TEXT);
        CREATE TABLE subcontract_issue (id INTEGER PRIMARY KEY, issue_no TEXT, warehouse TEXT);
        CREATE TABLE subcontract_receive (id INTEGER PRIMARY KEY, receive_no TEXT, warehouse TEXT);
    """)
    con.execute("INSERT INTO system_setting (key, value) VALUES ('location_management_enabled', ?)",
                ('1' if use_bins else '0',))
    con.execute("INSERT INTO warehouse (id, code, name) VALUES (1, 'WH1', '甲仓'), (2, 'WH2', '乙仓')")
    con.execute("INSERT INTO material (id, code, stock) VALUES (1, 'M001', 15.0)")
    con.execute("INSERT INTO in_order (id, order_no, warehouse) VALUES (10, 'IN-10', '甲仓')")
    con.execute(
        "INSERT INTO stock_transaction (material_id, warehouse_id, location, quantity, reference_type, reference_id) "
        "VALUES (1, 1, '甲仓', 10.0, 'in_order', 10), (1, 2, '乙仓', 5.0, 'opening_stock', 1)"
    )
    if use_bins:
        con.execute(
            "INSERT INTO location_inventory (material_id, warehouse_id, location, quantity) "
            "VALUES (1, 1, 'A1', 10.0), (1, 2, 'B1', 5.0)"
        )
    con.commit()
    con.close()


def test_compute_reconciliation_summary(tmp_path):
    """独立三账巡检计算：平衡、总账差异、错仓来源与开库位分布差异均与主服务同口径。"""
    db_path = tmp_path / 'ledger.db'
    _create_standalone_ledger_db(db_path, use_bins=False)
    title, summary, metrics = ledger_runner.compute_reconciliation_summary(db_path)
    assert title == '全仓账簿核对 · 数量相符'
    assert summary == '总账与流水差异 0，库位核对关闭。流水与来源单据仓库不一致 0 组。仓库外键为空的流水 0 条。'
    assert metrics['global_diff'] == 0 and metrics['source_diff'] == 0

    # 制造 0.0001 差异与来源错仓
    con = sqlite3.connect(str(db_path))
    con.execute("UPDATE material SET stock = 15.0001 WHERE id = 1")
    con.execute("UPDATE in_order SET warehouse = '乙仓' WHERE id = 10")
    con.commit()
    con.close()
    title2, summary2, metrics2 = ledger_runner.compute_reconciliation_summary(db_path)
    assert title2 == '全仓账簿核对 · 发现差异'
    assert metrics2['global_diff'] == 1 and metrics2['source_diff'] == 1
    assert 'M001' in summary2 and 'in_order #10' in summary2


def test_upsert_reconciliation_notification(tmp_path):
    """同日重跑更新同一通知：内容不变保留已读，内容变化重置未读。"""
    db_path = tmp_path / 'notify.db'
    _create_standalone_ledger_db(db_path, use_bins=False)
    t1 = datetime(2026, 11, 26, 9, 0, 0)
    r1 = ledger_runner.upsert_reconciliation_notification(db_path, '全仓账簿核对 · 数量相符', '摘要A', now=t1)
    assert r1['action'] == 'inserted' and r1['target_id'] == 20261126

    con = sqlite3.connect(str(db_path))
    con.execute("UPDATE notification SET is_read = 1 WHERE type = 'inventory_reconciliation'")
    con.commit()
    con.close()

    r2 = ledger_runner.upsert_reconciliation_notification(
        db_path, '全仓账簿核对 · 数量相符', '摘要A', now=datetime(2026, 11, 26, 9, 5, 0)
    )
    assert r2['action'] == 'updated'
    con = sqlite3.connect(str(db_path))
    rows = con.execute("SELECT title, content, is_read FROM notification WHERE type = 'inventory_reconciliation'").fetchall()
    con.close()
    assert rows == [('全仓账簿核对 · 数量相符', '摘要A', 1)]

    r3 = ledger_runner.upsert_reconciliation_notification(
        db_path, '全仓账簿核对 · 发现差异', '摘要B', now=datetime(2026, 11, 26, 9, 10, 0)
    )
    assert r3['action'] == 'updated'
    con = sqlite3.connect(str(db_path))
    rows2 = con.execute("SELECT title, content, is_read FROM notification WHERE type = 'inventory_reconciliation'").fetchall()
    con.close()
    assert rows2 == [('全仓账簿核对 · 发现差异', '摘要B', 0)]


def test_run_ledger_check(tmp_path):
    """端到端运行独立三账巡检脚本（含 dry-run 与状态 JSON 落盘）。"""
    db_path = tmp_path / 'e2e.db'
    status_file = tmp_path / 'status' / 'last-run.json'
    _create_standalone_ledger_db(db_path, use_bins=True)

    dry = ledger_runner.run_ledger_check(db_path, dry_run=True, status_file=status_file)
    assert dry['ok'] is True and dry['dry_run'] is True and not status_file.exists()

    live = ledger_runner.run_ledger_check(db_path, dry_run=False, status_file=status_file)
    assert live['ok'] is True and live['title'] == '全仓账簿核对 · 数量相符'
    assert status_file.is_file()
    saved = json.loads(status_file.read_text(encoding='utf-8'))
    assert saved['metrics']['use_bins'] is True and saved['write_result']['action'] == 'inserted'
