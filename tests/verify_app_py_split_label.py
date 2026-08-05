# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：标签打印（label）域路由迁移到 routes/label.py。

register-on-app 模式（register_label_routes(app)），endpoint 名与 URL 不变。

验收点：
L1. 核心 endpoint 已注册，且无 label.xxx 前缀重复。
L2. URL 路径保持不变（/label/batch_print）。
L3. 带 ids 参数时返回 200（页面正常渲染）。
L4. 不带 ids 参数时返回 200（空列表）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "print_batch_labels",
]
URLS = [
    "/label/batch_print",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_base():
    from app import Material, MaterialCategory, Unit
    cat = MaterialCategory(code="LCAT", name="标签分类")
    unit = Unit(code="PCS", name="个")
    db.session.add_all([cat, unit])
    db.session.flush()
    mat = Material(code="LM1", name="标签物料", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat.id


def _setup():
    # 校验迁移模块可正常导入（模块级仅稳定依赖，不触发循环导入）。
    # 注意：不在此重复调用 register_label_routes(app)，否则会与 app.py 中
    # 同名存量 endpoint 冲突（Flask 会抛 overwriting assertion）。
    # 标签域路由由 app.py 注册，endpoint 名与 URL 与迁移模块完全一致。
    from routes.label import register_label_routes
    assert callable(register_label_routes)
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        mat_id = _seed_base()
    client = _make_client()
    _login(client)
    return client, mat_id


def test_endpoints_registered():
    rules = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    for ep in ENDPOINTS:
        assert ep in rules, f"endpoint {ep} 未注册"
    # register-on-app 模式不应产生 label.xxx 前缀的 endpoint
    assert not any(ep.startswith("label.") for ep in rules)


def test_batch_print_with_ids_returns_200():
    client, mat_id = _setup()
    resp = client.get(f"/label/batch_print?ids={mat_id}")
    assert resp.status_code == 200, f"带 ids 请求 -> {resp.status_code}"


def test_batch_print_without_ids_returns_200():
    client, _ = _setup()
    resp = client.get("/label/batch_print")
    assert resp.status_code == 200, f"无 ids 请求 -> {resp.status_code}"