"""Finite inbound/push TCP diagnosis inside the existing Linux test boundary.

Only 1 or25 newly-created rows are accepted. No URL, database, credentials,
document identity or output path can be supplied by the caller.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def _check(condition, message):
    if not condition:
        raise RuntimeError('合成TCP诊断失败：' + message)


def _tokens(response, *, revision=False):
    class _Tokens(HTMLParser):
        def handle_starttag(self, tag, attributes):
            attributes = dict(attributes)
            if tag == 'meta' and attributes.get('name') in ('csrf-token', 'document-revision'):
                self.values[attributes['name']] = attributes.get('content', '')
            elif tag == 'input' and attributes.get('name') == 'csrf_token':
                self.values.setdefault('csrf-token', attributes.get('value', ''))

    parser = _Tokens(convert_charrefs=True)
    parser.values = {}
    parser.feed(response.text)
    parser.close()
    csrf = parser.values.get('csrf-token')
    token = parser.values.get('document-revision') or response.headers.get('X-WMS-Document-Read-Revision')
    _check(bool(csrf), '实际页面缺少CSRF令牌')
    if revision:
        _check(bool(token), '实际来源页面缺少单据读取版本')
    return csrf, token


def _request(server, session, method, path, *, allowed=(200,), **kwargs):
    from scripts.perf_runtime import OwnedPerfHTTP, relative_target, require_runtime
    target = relative_target(path)
    _check(method in ('GET', 'POST'), '只允许固定场景的GET/POST')
    require_runtime()
    from scripts.smoke_isolation import IsolatedSession
    _check(type(server) is OwnedPerfHTTP and isinstance(session, IsolatedSession)
           and any(owned is session for owned in server.sessions), 'HTTP必须使用本次自有服务的会话')
    _check(session.lease is server.lease and session.identity == server.identity
           and session.base_url == server.base_url == server.lease.base_url
           and session.nonce == server.identity['nonce'], 'HTTP会话与监听身份不一致')
    _check(server.thread is not None and server.thread.is_alive(), '自有HTTP服务不在运行')
    server.lease.validate(server.identity)
    started = time.perf_counter()
    response = session.request(method, server.base_url + target, timeout=30,
                               allow_redirects=False, **kwargs)
    try:
        response.content
        _check(response.status_code in allowed, f'{method} {target} 返回HTTP {response.status_code}')
        return response, round((time.perf_counter() - started) * 1000, 3)
    finally:
        response.close()


def _snapshot(w, material_ids, warehouse_id, other_warehouse_id):
    with w.app.app_context():
        warehouse = w.db.session.get(w.Warehouse, warehouse_id)
        other = w.db.session.get(w.Warehouse, other_warehouse_id)
        own_stock = w.get_warehouse_stock_quantities(warehouse)
        other_stock = w.get_warehouse_stock_quantities(other)
        result = dict(stock=sum(float(w.db.session.get(w.Material, mid).stock) for mid in material_ids),
                      warehouse_stock=sum(float(own_stock.get(mid, 0)) for mid in material_ids),
                      other_warehouse_stock=sum(float(other_stock.get(mid, 0)) for mid in material_ids))
        w.db.session.remove()
        return result


def diagnose(rows):
    if type(rows) is not int or rows not in (1, 25):
        raise ValueError('合成TCP诊断明细数仅允许1或25')
    started = time.perf_counter()
    sys.path.insert(0, str(ROOT))
    from scripts.perf_runtime import (OwnedPerfHTTP, assert_memory_app,
                                      initialize_synthetic_app, require_runtime, source_sha)
    from scripts.verify_db_guard import require_synthetic_memory_database
    require_runtime()
    require_synthetic_memory_database()
    w, username, password = initialize_synthetic_app()
    assert_memory_app(w)
    # The existing performance initializer disables CSRF for its read-only samples.
    # This writable scenario restores the real form/session CSRF checks.
    w.app.config.update(WTF_CSRF_ENABLED=True)
    nonce = uuid.uuid4().hex
    with w.app.app_context():
        warehouse = w.Warehouse(code='TCP-A-' + nonce, name='合成TCP仓A-' + nonce,
                                is_default=True, status='active')
        other = w.Warehouse(code='TCP-B-' + nonce, name='合成TCP仓B-' + nonce, status='active')
        unit = w.Unit(code='TCP-U-' + nonce, name='合成TCP单位-' + nonce)
        supplier = w.Supplier(code='TCP-S-' + nonce, name='合成TCP供应商-' + nonce)
        materials = [w.Material(code=f'TCP-{nonce}-{index}', name=f'合成TCP物料{index}',
                                unit=unit, stock=0, price=2) for index in range(rows)]
        w.db.session.add_all([warehouse, other, unit, supplier, *materials])
        w.set_system_setting('location_management_enabled', '0')
        w.set_system_setting('purchase_receipt_strict_order', '0')
        w.db.session.commit()
        material_ids = [material.id for material in materials]
        codes = [material.code for material in materials]
        content = [(material.code, material.name) for material in materials]
        supplier_id, warehouse_id, other_id, warehouse_name = supplier.id, warehouse.id, other.id, warehouse.name
        w.db.session.remove()
    initial = _snapshot(w, material_ids, warehouse_id, other_id)
    _check(initial == dict(stock=0, warehouse_stock=0, other_warehouse_stock=0), '新合成物料并非零库存')
    stages, protocol_reads, authentication, security_checks = [], [], [], []
    from scripts.diagnose_synthetic_push import _detail_content

    with OwnedPerfHTTP(w, username, password) as server:
        session = server.session()
        login_page, elapsed = _request(server, session, 'GET', '/login')
        authentication.append(dict(phase='login_page', elapsed_ms=elapsed, http_status=login_page.status_code))
        login_csrf, _ = _tokens(login_page)
        login_response, elapsed = _request(server, session, 'POST', '/login', allowed=(200, 302), data={
            'username': username, 'password': password, 'usage_consent': '1',
            'login_mode': 'admin', 'csrf_token': login_csrf})
        authentication.append(dict(phase='login', elapsed_ms=elapsed, http_status=login_response.status_code))
        authenticated, elapsed = _request(server, session, 'GET', '/api/units')
        authentication.append(dict(phase='authenticated_api', elapsed_ms=elapsed, http_status=authenticated.status_code))
        _check('json' in authenticated.headers.get('Content-Type', ''), '合成账号没有有效登录')
        create_page, elapsed = _request(server, session, 'GET', '/in_order/add')
        csrf, _ = _tokens(create_page)
        protocol_reads.append(dict(phase='new_document_page', elapsed_ms=elapsed, http_status=200))

        def stage(name, method, path, **kwargs):
            response, elapsed = _request(server, session, method, path, **kwargs)
            stages.append(dict(stage=name, elapsed_ms=elapsed, http_status=response.status_code))
            return response

        headers = {'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest',
                   'X-Idempotency-Key': 'tcp-save-' + nonce}
        payload = dict(business_type='采购入库', supplier_id=supplier_id, warehouse=warehouse_name,
                       auto_push_requisition=False,
                       items=[dict(code=code, quantity=2, price=2) for code in codes])
        rejected, elapsed = _request(server, session, 'POST', '/in_order/add', allowed=(400,),
                                     json=payload, headers={'X-Requested-With': 'XMLHttpRequest'})
        security_checks.append(dict(phase='missing_csrf', elapsed_ms=elapsed, http_status=rejected.status_code))
        _check(rejected.json().get('status') == 'error', '缺CSRF的写入没有被拒绝')
        with w.app.app_context():
            _check(w.InOrder.query.count() == 0, 'CSRF拒绝仍生成了单据')
            w.db.session.remove()
        created = stage('save_inbound', 'POST', '/in_order/add', json=payload, headers=headers).json()
        _check(created.get('status') == 'success' and type(created.get('id')) is int, '首次保存失败')
        source_id = created['id']
        pending_page, elapsed = _request(server, session, 'GET', f'/in_order/{source_id}')
        csrf, revision = _tokens(pending_page, revision=True)
        protocol_reads.append(dict(phase='completion_snapshot', elapsed_ms=elapsed, http_status=200))
        invalid, elapsed = _request(server, session, 'POST', f'/in_order/{source_id}/complete?force=1', allowed=(409,),
                                    headers={'X-CSRFToken': csrf, 'X-WMS-Document-Revision': 'synthetic-invalid-revision',
                                             'X-Requested-With': 'XMLHttpRequest'})
        security_checks.append(dict(phase='invalid_revision', elapsed_ms=elapsed, http_status=invalid.status_code))
        _check(invalid.json().get('status') == 'error', '伪造单据版本没有被拒绝')
        _check(_snapshot(w, material_ids, warehouse_id, other_id) == initial, '无效版本请求改变了库存')
        completed = stage('complete_inbound', 'POST', f'/in_order/{source_id}/complete?force=1',
                          headers={'X-CSRFToken': csrf, 'X-WMS-Document-Revision': revision,
                                   'X-Requested-With': 'XMLHttpRequest'}).json()
        _check(completed.get('status') == 'success', '入库完成失败')
        before_push = _snapshot(w, material_ids, warehouse_id, other_id)
        _check(before_push == dict(stock=rows * 2, warehouse_stock=rows * 2, other_warehouse_stock=0),
               '入库库存或仓库归属异常')
        with w.app.app_context():
            source = w.db.session.get(w.InOrder, source_id)
            _check(source.status == 'completed' and len(source.items) == rows, '来源状态或行数异常')
            source_number = source.order_no
            items = [dict(source_item_id=item.id, quantity=1) for item in source.items]
            w.db.session.remove()
        source_page = stage('render_inbound_detail', 'GET', f'/in_order/{source_id}')
        stages[-1].update(_detail_content(source_page.text, source_number, content))
        csrf, revision = _tokens(source_page, revision=True)
        push_page = stage('render_push', 'GET', f'/in_order/{source_id}/push')
        csrf, _ = _tokens(push_page)
        push = dict(target_type='requisition', request_id='tcp-push-' + nonce,
                    department_id=None, picker='合成TCP诊断员', purpose='合成TCP诊断', items=items)
        headers = {'X-CSRFToken': csrf, 'X-WMS-Document-Revision': revision,
                   'X-Requested-With': 'XMLHttpRequest'}
        pushed = stage('push_draft', 'POST', f'/in_order/{source_id}/push', json=push, headers=headers).json()
        _check(pushed.get('status') == 'success' and type(pushed.get('id')) is int, '下推未生成草稿')
        target_id = pushed['id']
        replay = stage('replay_push', 'POST', f'/in_order/{source_id}/push', json=push, headers=headers).json()
        _check(replay.get('status') == 'success' and replay.get('id') == target_id
               and replay.get('replayed') is True, '重复请求没有复用原草稿')
        with w.app.app_context():
            target = w.db.session.get(w.OutOrder, target_id)
            source_status = w.db.session.get(w.InOrder, source_id).status
            target_number, target_status = target.order_no, target.status
            target_count = w.OutOrder.query.count()
            target_quantity = sum(float(item.quantity) for item in target.items)
            target_rows = len(target.items)
            links = w.DocumentPushLine.query.filter_by(source_document_id=source_id,
                                                       request_id=push['request_id']).all()
            _check(len(links) == rows and {line.target_document_id for line in links} == {target_id},
                   '来源分配没有保持唯一目标')
            w.db.session.remove()
        target_page = stage('render_target_detail', 'GET', f'/out_order/{target_id}')
        stages[-1].update(_detail_content(target_page.text, target_number, content))
        after_push = _snapshot(w, material_ids, warehouse_id, other_id)
        _check(source_status == 'completed' and target_status == 'pending' and target_count == 1 and target_rows == rows
               and target_quantity == rows, '下推没有保持唯一完整草稿')
        _check(after_push == before_push, '只生成草稿却改变了库存')
        response_identity_verified = session._identity_verified is True
        _check(response_identity_verified, '最终响应身份未验证')
    _check(not server.thread.is_alive() and server.listener.fileno() == -1,
           '自有TCP服务或监听没有关闭')
    return dict(schema=1, scenario='inbound-push-tcp', transport='tcp', source_sha=source_sha(),
                database='sqlite:///:memory:', rows=rows, stages=stages, protocol_reads=protocol_reads,
                authentication=authentication, security_checks=security_checks,
                elapsed_ms_total=round((time.perf_counter() - started) * 1000, 3),
                source_status=source_status, target_status=target_status, target_count=target_count,
                target_quantity=target_quantity, stock_before=initial['stock'], stock_after_inbound=before_push['stock'],
                stock_after_push=after_push['stock'], other_warehouse_stock=after_push['other_warehouse_stock'],
                request_replayed=True, csrf_enabled=True, missing_csrf_rejected=True,
                page_revision_used=True, invalid_revision_rejected=True,
                response_identity_verified=response_identity_verified,
                owned_listener_closed=True, owned_server_stopped=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', required=True, choices=('inbound-push-tcp',))
    parser.add_argument('--rows', type=int, choices=(1, 25), default=1)
    args = parser.parse_args(argv)
    print('WMS_SYNTHETIC_TCP_DIAGNOSTIC=' + json.dumps(diagnose(args.rows), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
