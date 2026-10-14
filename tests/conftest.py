# -*- coding: utf-8 -*-
"""pytest 会话级环境固定。

根因（BUG-2026-08-05-002）：pytest 按字母序收集测试模块时，
test_get_default_warehouse.py 等先于 test_material_delete_missing_ai_table.py
导入 app 模块且未设置 DATABASE_URL，app 被缓存为文件库配置；
后续模块再设置内存库 env 已无效，guarded_drop_all 拒绝 drop_all。

conftest.py 先于一切测试模块导入，在此固定内存库环境，
使 app 首次导入即使用 sqlite:///:memory:，与导入顺序无关。
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
# BUG-2026-09-19-003：app 模块导入期按默认 FLASK_ENV=production 执行
# validate_production_security_config，新增的生产门禁要求显式放行不安全
# 会话 Cookie。测试走内存库 + HTTP，显式 opt-in 以便 app 可导入。
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

# BUG-2026-08-07-002：pytest 全量跑时 3 个 golden 测试收集报
# "'app' is not a package"。根因：其他测试模块先 sys.path.insert(APP_DIR)
# 并 `import app`（命中 app/app.py 模块，无 __path__），此后
# `from app.fix_db_columns import ...` / `from app.ai... import ...`
# 包语义导入失败。单跑时 /workspace 在 sys.path，app 以 namespace 包
# 加载故可过——结果依赖导入顺序，属测试隔离缺陷。
#
# 修复：conftest 抢先以模块语义导入 app（与所有业务测试一致），
# 再补 __path__ 指向 APP_DIR，使 `import app.ai.xxx` /
# `import app.fix_db_columns` 也能沿该路径解析，两种语义共存。
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
_APP_DIR = _ROOT / "app"
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

import app as _wms_app  # noqa: E402

if not hasattr(_wms_app, "__path__"):
    _wms_app.__path__ = [str(_APP_DIR)]


# F2.2 / S3：登录失败单 IP 限流是**进程内**状态（app/rate_limit.py），测试间必须隔离，
# 否则前一个用例累积的失败计数会让后续用例的登录请求被 429 误拦（且 test_client 默认
# 远端地址统一为 127.0.0.1，天然共享同一个限流 key）。
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_login_rate_limit():
    try:
        import rate_limit as _rl
        _rl.reset()
    except Exception:
        pass
    yield
    try:
        import rate_limit as _rl
        _rl.reset()
    except Exception:
        pass


@pytest.fixture
def bom_case(monkeypatch):
    from app import app, db, BOM, BOMItem, Material, MaterialCategory, Unit, User
    from flask import g
    from werkzeug.security import generate_password_hash
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    # Each request must load its user afresh, even while the fixture holds an app context.
    def refresh_fixture_user():
        g.pop('_login_user', None)
    hooks = dict(app.before_request_funcs)
    hooks[None] = [refresh_fixture_user, *hooks.get(None, [])]
    monkeypatch.setattr(app, 'before_request_funcs', hooks)
    with app.app_context():
        db.session.remove()
        db.drop_all()
        db.create_all()
        unit = Unit(code='B-U', name='个')
        category = MaterialCategory(code='B-C', name='测试分类')
        user = User(username='bom-audit', role='admin',
                    password_hash=generate_password_hash('fixture-only'),
                    must_change_password=False)
        db.session.add_all([unit, category, user])
        db.session.flush()
        material = Material(code='B-M', name='测试子件', spec='审计规格',
                            unit_id=unit.id, category_id=category.id, price=5, stock=10)
        bom = BOM(bom_no='BOM-AUDIT', product_code='B-P', product_name='审计产品',
                  version='V1', status='active', total_cost=10)
        db.session.add_all([material, bom])
        db.session.flush()
        db.session.add(BOMItem(bom_id=bom.id, material_id=material.id,
                              quantity=2, unit_id=unit.id, unit_cost=5, total_cost=10))
        db.session.commit()
        ids = {'bom': bom.id, 'material': material.id, 'unit': unit.id, 'user': user.id}
        client = app.test_client()
        client.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        assert client.post('/login', data={'username':'bom-audit','password':'fixture-only'}).status_code == 302
        yield client, ids
        db.session.remove()
