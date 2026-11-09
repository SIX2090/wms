"""Disposable browser fixture. Never accepts a production data directory/port."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.linux_test_runtime import require_subprocess_boundary
require_subprocess_boundary()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--port', required=True, type=int)
    parser.add_argument('--instance', required=True)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    temporary = Path(tempfile.gettempdir()).resolve()
    source = args.source_root.resolve(strict=True)
    repository = Path(__file__).resolve().parents[1]
    if root == temporary or not root.is_relative_to(temporary):
        parser.error('browser fixtures require a dedicated OS temporary directory')
    if source not in (repository, Path('/opt/wms-baseline')) and not source.is_relative_to(root.parent):
        parser.error('source must be this checkout or the same owned temporary rehearsal')
    if args.port != 0 and not 10240 <= args.port <= 65535:
        parser.error('use an isolated ephemeral test port')
    database = root / 'synthetic.db'
    if database.exists():
        parser.error('refusing to overwrite an existing database')
    for key in list(os.environ):
        if key.startswith(('WMS_', 'AI_', 'OPENAI_', 'WECHAT_', 'TENCENTCLOUD_', 'TOKENHUB_',
                           'DEEPSEEK_', 'DASHSCOPE_', 'GEMINI_', 'ANTHROPIC_', 'SILICONFLOW_')) or key in {
                               'DATABASE_URL', 'FLASK_ENV', 'SECRET_KEY', 'LOG_FILE', 'UPLOAD_FOLDER'}:
            os.environ.pop(key, None)
    os.environ.update(DATABASE_URL='sqlite:///' + database.as_posix(),
                      WMS_DATABASE_URI='sqlite:///' + database.as_posix(), WMS_NO_DB_TOUCH='1',
                      WMS_ALLOW_INSECURE_COOKIE='1', SESSION_COOKIE_SECURE='false', FLASK_ENV='production', SECRET_KEY='test-only-' + args.instance,
                      WMS_SKIP_AUTO_UPDATE='1', WMS_SKIP_STARTUP_BACKUP='1', WMS_LOCAL_PRINT_AGENT='0',
                      AUTO_BACKUP_ENABLED='false', LOG_FILE=str(root / 'app.log'), UPLOAD_FOLDER=str(root / 'uploads'),
                      OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    # Fixture isolation includes application HTTP clients; the browser itself
    # separately permits only this server's exact origin.
    import requests
    import urllib.request

    def refuse_http(*unused, **unused_options):
        raise RuntimeError('Synthetic browser fixture refuses outbound HTTP')

    requests.sessions.Session.request = refuse_http
    urllib.request.urlopen = refuse_http
    sys.path.insert(0, str(source / 'app'))
    from db import db
    import models as m
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from werkzeug.security import generate_password_hash
    engine = create_engine('sqlite:///' + database.as_posix())
    db.metadata.create_all(engine)
    with Session(engine) as session:
        users = [m.User(username=name, role='admin', password_hash=generate_password_hash('AuditOnly2026!'),
                        must_change_password=False) for name in ('browser-a', 'browser-b')]
        units = [m.Unit(code='PCS', name='个'), m.Unit(code='KG', name='千克')]
        suppliers = [m.Supplier(code='BS-A', name='合成供应商甲'), m.Supplier(code='BS-B', name='合成供应商乙')]
        warehouses = [m.Warehouse(code='BW-A', name='合成甲仓', status='active', is_default=True),
                      m.Warehouse(code='BW-B', name='合成乙仓', status='active')]
        session.add_all([*users, *units, *suppliers, *warehouses]); session.flush()
        material = m.Material(code='SYN-M', name='合成物料', unit_id=units[0].id, stock=25, price=2)
        session.add(material); session.flush()
        for warehouse, quantity in zip(warehouses, (20, 5)):
            session.add(m.LocationInventory(material_id=material.id, warehouse_id=warehouse.id, location='L-1', quantity=quantity))
            session.add(m.StockTransaction(material_id=material.id, warehouse_id=warehouse.id, location='L-1', quantity=quantity, transaction_type='in'))
        inbound = m.InOrder(order_no='BROWSER-IN', business_type='产品入库', warehouse=warehouses[0].name,
                            status='pending', operator_id=users[0].id, total_amount=2)
        outbound = m.OutOrder(order_no='BROWSER-OUT', business_type='其他出库', warehouse=warehouses[0].name,
                              purpose='合成测试', status='pending', operator_id=users[0].id, total_amount=2)
        session.add_all([inbound, outbound]); session.flush()
        session.add(m.InOrderItem(in_order_id=inbound.id, material_id=material.id, quantity=1, price=2, amount=2))
        session.add(m.OutOrderItem(out_order_id=outbound.id, material_id=material.id, quantity=1, price=2, amount=2))
        session.add(m.SystemSetting(key='location_management_enabled', value='0'))
        session.add(m.SystemSetting(key='allow_negative_stock', value='0'))
        session.commit()
    engine.dispose()
    os.chdir(source)
    import app as w
    from flask import abort, jsonify, request
    with w.app.app_context():
        assert Path(w.db.engine.url.database).resolve() == database
        assert {u.username for u in w.User.query.all()} == {'browser-a', 'browser-b'}
        assert w.app.config['WTF_CSRF_ENABLED']
        w.ensure_default_system_settings(); w.db.session.commit()
    lock = threading.Lock()

    @w.app.after_request
    def observe(response):
        response.headers['X-WMS-Isolated-Test'] = args.instance
        if request.method == 'POST' and request.path in ('/material/add', '/unit/add'):
            with lock:
                with (root / 'requests.jsonl').open('a', encoding='utf-8') as output:
                    output.write(json.dumps({'path': request.path, 'status': response.status_code}) + '\n')
            time.sleep(0.3)  # Test-only slow response; real handlers and transactions remain.
        return response

    @w.app.route('/__lab/state')
    def state():
        if request.headers.get('X-Lab-Instance') != args.instance:
            abort(403)
        return jsonify(materials=[{'code': row.code, 'stock': row.stock, 'unit_id': row.unit_id,
                                   'supplier_id': row.supplier_id} for row in w.Material.query.all()],
                       units=[{'id': row.id, 'code': row.code, 'name': row.name} for row in w.Unit.query.all()],
                       stock=sum(row.stock for row in w.Material.query.all()),
                       location_stock=sum(row.quantity for row in w.LocationInventory.query.all()),
                       transaction_stock=sum(row.quantity for row in w.StockTransaction.query.all()),
                       inbound=[{'status': row.status, 'remark': row.remark} for row in w.InOrder.query.all()],
                       outbound=[{'status': row.status, 'remark': row.remark} for row in w.OutOrder.query.all()])

    @w.app.route('/__lab/csp-probe.js')
    def csp_probe():
        if request.args.get('instance') != args.instance:
            abort(403)
        # Deliberate test payload, never part of an application asset or route.
        return ("window.__probeLoaded=true;try{eval('window.__probeEval=true')}"
                "catch(error){window.__probeEvalError=error.name}", 200,
                {'Content-Type': 'text/javascript; charset=utf-8'})

    from waitress import create_server
    server = create_server(w.app, host='127.0.0.1', port=args.port, threads=2)
    port = int(server.effective_port)
    if not 10240 <= port <= 65535:
        server.close()
        raise RuntimeError('OS allocated a forbidden test port')
    print(json.dumps({'ready': True, 'port': port, 'pid': os.getpid(), 'instance': args.instance}), flush=True)
    server.run()


if __name__ == '__main__':
    main()
