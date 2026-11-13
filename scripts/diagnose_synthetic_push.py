"""Synthetic inbound/push diagnostics; run through run_ci_isolated.py only.

No URL, credentials, database path, or output-file argument is accepted. HTTP
calls use the fresh application's test_client and never open a listening socket.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def _check(condition, message):
    if not condition:
        raise RuntimeError('合成诊断失败：' + message)


def diagnose(rows):
    """Return actual stage metrics and business invariants, never a PASS-only list."""
    if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 500:
        raise ValueError('合成明细数必须为 1 至 500 的整数')
    # Check authentic OS isolation before loading WMS or touching any database.
    sys.path.insert(0, str(ROOT))
    from scripts.verify_db_guard import require_isolated_test_runtime, require_synthetic_memory_database
    require_isolated_test_runtime()
    require_synthetic_memory_database()
    os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')
    sys.path.insert(0, str(ROOT / 'app'))
    import app as w
    from werkzeug.security import generate_password_hash

    w.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    nonce = uuid.uuid4().hex
    stages = []
    with w.app.app_context():
        _check(str(w.db.engine.url) == 'sqlite:///:memory:', '实际 engine 不是新建内存库')
        _check(all(not row[2] for row in w.db.session.execute(w.db.text('PRAGMA database_list'))),
               '实际 SQLite 已附加文件库')
        w.db.create_all()
        # No drop_all/cleanup of pre-existing data. Only this new process's
        # fresh memory engine is permitted above, and every identifier is owned.
        warehouse = w.Warehouse(code='DIAG-W-' + nonce, name='合成诊断仓-' + nonce,
                                is_default=True, status='active')
        unit = w.Unit(code='DIAG-U-' + nonce, name='合成个-' + nonce)
        supplier = w.Supplier(code='DIAG-S-' + nonce, name='合成供应商-' + nonce)
        user = w.User(username='synthetic-' + nonce,
                      password_hash=generate_password_hash('synthetic-' + nonce),
                      role='admin', status='normal', must_change_password=False)
        materials = [w.Material(code=f'DIAG-{nonce}-{index}', name=f'合成物料{index}',
                                unit=unit, stock=0, price=2) for index in range(rows)]
        w.db.session.add_all([warehouse, unit, supplier, user, *materials])
        w.db.session.commit()
        material_ids = [material.id for material in materials]
        material_codes = [material.code for material in materials]
        supplier_id, warehouse_name, username = supplier.id, warehouse.name, user.username
        client = w.app.test_client()

        def request(stage, method, path, **kwargs):
            target = urlsplit(path)
            _check(method in ('get', 'post') and path.startswith('/') and not path.startswith('//')
                   and not target.scheme and not target.netloc, '请求必须是合成 test_client 的相对路径')
            started = time.perf_counter()
            response = getattr(client, method)(path, follow_redirects=False, **kwargs)
            elapsed = (time.perf_counter() - started) * 1000
            stages.append(dict(stage=stage, elapsed_ms=round(elapsed, 3), http_status=response.status_code))
            _check(response.status_code == 200, stage + ' HTTP 状态异常')
            return response

        # All login data belongs exclusively to the newly-created memory DB.
        login = client.post('/login', data={'username': username, 'password': 'synthetic-' + nonce},
                            follow_redirects=False)
        _check(login.status_code in (200, 302), '合成账号登录失败')
        with client.session_transaction() as session:
            _check(str(session.get('_user_id', '')) == str(user.id), '合成登录身份未生效')
        created = request('save_inbound', 'post', '/in_order/add', json={
            'business_type': '采购入库', 'supplier_id': supplier_id,
            'warehouse': warehouse_name, 'auto_push_requisition': False,
            'items': [dict(code=code, quantity=2, price=2) for code in material_codes],
        }).get_json()
        _check(created and created.get('status') == 'success' and created.get('id'), '首次保存没有成功')
        source_id = created['id']
        completed = request('complete_inbound', 'post', f'/in_order/{source_id}/complete?force=1').get_json()
        _check(completed and completed.get('status') == 'success', '入库完成失败')
        source = w.db.session.get(w.InOrder, source_id)
        _check(source.status == 'completed' and len(source.items) == rows, '来源状态或明细数异常')
        stock_after_inbound = sum(float(w.db.session.get(w.Material, mid).stock) for mid in material_ids)
        _check(stock_after_inbound == rows * 2, '入库库存变化异常')
        request('render_push', 'get', f'/in_order/{source_id}/push')
        payload = dict(target_type='requisition', request_id='diag-' + nonce,
                       department_id=None, picker='合成诊断员', purpose='合成诊断',
                       items=[dict(source_item_id=item.id, quantity=1) for item in source.items])
        pushed = request('push_draft', 'post', f'/in_order/{source_id}/push', json=payload).get_json()
        _check(pushed and pushed.get('status') == 'success' and pushed.get('id'), '下推没有生成目标草稿')
        target_id = pushed['id']
        replay = request('replay_push', 'post', f'/in_order/{source_id}/push', json=payload).get_json()
        _check(replay and replay.get('status') == 'success' and replay.get('id') == target_id
               and replay.get('replayed') is True,
               '同请求重放产生不同目标')
        w.db.session.expire_all()
        target = w.db.session.get(w.OutOrder, target_id)
        target_count = w.OutOrder.query.count()
        target_quantity = sum(float(item.quantity) for item in target.items)
        stock_after_push = sum(float(w.db.session.get(w.Material, mid).stock) for mid in material_ids)
        _check(target.status == 'pending' and target_count == 1, '下推或重放没有保持唯一草稿')
        _check(len(target.items) == rows and target_quantity == rows, '目标明细与数量异常')
        _check(stock_after_push == stock_after_inbound, '仅生成草稿却改变库存')
        return dict(schema=1, scenario='inbound-push', transport='flask-test-client',
                    database='sqlite:///:memory:', rows=rows, stages=stages,
                    source_status=source.status, target_status=target.status,
                    target_count=target_count, target_quantity=target_quantity,
                    stock_before=0, stock_after_inbound=stock_after_inbound,
                    stock_after_push=stock_after_push, request_replayed=True)


def _rows(value):
    try:
        rows = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('合成明细数必须为 1 至 500 的整数') from None
    if not 1 <= rows <= 500:
        raise argparse.ArgumentTypeError('合成明细数必须为 1 至 500 的整数')
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=('inbound-push',))
    parser.add_argument('--rows', type=_rows, default=1, metavar='1..500')
    args = parser.parse_args(argv)
    report = diagnose(args.rows)
    print('WMS_SYNTHETIC_DIAGNOSTIC=' + json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
