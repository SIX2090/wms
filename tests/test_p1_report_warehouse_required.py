# -*- coding: utf-8 -*-
"""P1 回归：报表 API 查询必须将仓库作为必填条件。

S15 修复：report_api_query 在解析 filters 后，若未指定仓库且无默认仓库，
必须返回 400 拒绝（AGENTS.md 仓库必填规则——不指定仓库时不得返回数据）。
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
from app import User, Warehouse, db  # noqa: E402


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
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


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    c = app_module.app.test_client()
    _login(c)
    yield c


def test_report_api_query_rejects_without_warehouse(client):
    """未指定仓库且无默认仓库时，报表查询必须返回 400。"""
    # 不预置任何仓库（无默认仓库）
    resp = client.get("/report/api/in_summary")
    assert resp.status_code == 400, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data.get("status") == "error", data


def test_report_api_query_accepts_default_warehouse(client):
    """有默认仓库时，未显式传仓库应回退默认仓库并放行（不返回 400）。"""
    with app_module.app.app_context():
        wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
        db.session.add(wh)
        db.session.commit()
    resp = client.get("/report/api/in_summary")
    # 有默认仓库时应通过仓库校验（可能 200 或因其它原因非 400-warehouse）
    assert resp.status_code != 400 or "仓库" not in (resp.get_json() or {}).get("msg", "")


def test_report_api_query_accepts_explicit_warehouse(client):
    """显式指定 warehouse_id 时应通过仓库校验。"""
    with app_module.app.app_context():
        wh = Warehouse(code="W1", name="一号仓", status="active")
        db.session.add(wh)
        db.session.commit()
        wh_id = wh.id
    resp = client.get(f"/report/api/in_summary?warehouse_id={wh_id}")
    assert resp.status_code != 400 or "仓库" not in (resp.get_json() or {}).get("msg", "")
