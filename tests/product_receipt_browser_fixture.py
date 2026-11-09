"""Disposable HTTP fixture for the product receipt acceptance check."""
# 禁止在隔离能力验证完成前导入或执行。
raise RuntimeError('浏览器测试服务已阻止：隔离能力尚未证明')
import argparse
import os
from pathlib import Path
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--port', required=True, type=int)
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if root == Path(tempfile.gettempdir()).resolve() or not root.is_relative_to(Path(tempfile.gettempdir()).resolve()):
        parser.error('use a dedicated temporary directory')
    if args.port in (8080, 5098) or not 1024 <= args.port <= 65535:
        parser.error('use an isolated port')
    database = root/'synthetic.db'
    if database.exists():
        parser.error('refusing to reuse an existing database')
    for key in list(os.environ):
        if key.startswith(('WMS_', 'AI_', 'OPENAI_', 'WECHAT_', 'TENCENTCLOUD_')):
            os.environ.pop(key, None)
    os.environ.update(DATABASE_URL='sqlite:///'+database.as_posix(), WMS_NO_DB_TOUCH='1',
                      WMS_SKIP_AUTO_UPDATE='1', WMS_ALLOW_INSECURE_COOKIE='1',
                      SESSION_COOKIE_SECURE='false', SECRET_KEY='product-fixture-only',
                      FLASK_ENV='production', WMS_SKIP_STARTUP_BACKUP='1', WMS_LOCAL_PRINT_AGENT='0',
                      AUTO_BACKUP_ENABLED='false', LOG_FILE=str(root/'app.log'),
                      UPLOAD_FOLDER=str(root/'uploads'))
    repository = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository/'app'))
    from db import db
    import models as m
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from werkzeug.security import generate_password_hash
    engine = create_engine('sqlite:///'+database.as_posix())
    db.metadata.create_all(engine)
    with Session(engine) as session:
        user = m.User(username='admin', role='admin', password_hash=generate_password_hash('Admin@123'), must_change_password=False)
        unit = m.Unit(code='PR-U', name='台')
        customer = m.Customer(code='PR-C', name='产品测试客户')
        warehouse = m.Warehouse(code='PR-W', name='产品测试仓', is_default=True, status='active')
        session.add_all([user, unit, customer, warehouse, m.Supplier(code='PR-S', name='测试供应商'),
                         m.MaterialCategory(code='400', name='设备成品')])
        session.flush()
        session.add(m.Material(code='PR-M', name='低压配电柜', spec='GGD-001', unit_id=unit.id, stock=0, price=12.34))
        session.commit()
    engine.dispose()
    import app as w
    @w.app.after_request
    def identify_fixture(response):
        response.headers['X-WMS-Product-Fixture'] = root.name
        return response
    with w.app.app_context():
        assert Path(w.db.engine.url.database).resolve() == database
        w.ensure_default_system_settings()
        w.db.session.commit()
    w.app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
