# -*- coding: utf-8 -*-
"""BUG-2026-08-16-012 回归（A1 物料域）：物料增删改/单价写结构化变更审计。

根因：OperationAudit 表/展示页早已存在，但 log_audit 全库 0 调用，高危操作
（物料增删改/单价等）无结构化前后值留痕，只有 OperationLog 的松散文本。

修复：add_material / edit_material（含单价变化）/ delete_material 在业务 commit
后调用 log_audit 写 old_data/new_data。

测试用例：
  T1. 新增物料 → OperationAudit 有 add_material 且 new_data 非空
  T2. 编辑物料改单价 → edit_material 有 old_data + new_data，price 旧→新
  T3. 删除物料 → delete_material 有 old_data（被删快照）
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, MaterialCategory, OperationAudit, Unit, User, Warehouse, db,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _latest_audit(op):
    return (OperationAudit.query
            .filter_by(operation=op)
            .order_by(OperationAudit.id.desc())
            .first())


def test_a9_material_audit():
    """A9 门禁：物料增删改/单价接入 log_audit（见 T1/T2/T3）。"""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_request_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WH01", name="主仓", is_default=True),
        ])
        db.session.commit()
        mat = Material(code="M-AUDIT", name="轴承", spec="6204",
                       category_id=1, unit_id=1, stock=0, price=10)
        db.session.add(mat)
        db.session.commit()
        assert Material.query.filter_by(code="M-AUDIT").first() is not None


class TestMaterialAudit:

    def test_add_material_writes_audit(self, client):
        resp = client.post("/material/add", data={
            "code": "M-ADD", "name": "新增料", "spec": "S",
            "brand": "", "price": "12.5", "stock": "0",
        })
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("add_material")
            assert audit is not None, "新增物料未写结构化审计"
            assert audit.target_type == "material"
            assert "新增料" in (audit.target_name or "")
            new_data = json.loads(audit.new_data)
            assert new_data.get("code") == "M-ADD"
            assert abs((new_data.get("price") or 0) - 12.5) < 1e-6

    def test_edit_material_price_change_audits_old_new(self, client):
        with app_module.app.app_context():
            db.session.add(Material(code="M-EDIT", name="编辑料", spec="S",
                                    category_id=1, unit_id=1, stock=0, price=8))
            db.session.commit()
            mid = Material.query.filter_by(code="M-EDIT").first().id
        resp = client.post(f"/material/edit/{mid}", data={
            "code": "M-EDIT", "name": "编辑料", "spec": "S", "brand": "",
            "price": "99.9", "stock": "0", "min_stock": "0", "max_stock": "0",
            "alert_days": "30", "purpose": "", "remark": "",
        })
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("edit_material")
            assert audit is not None, "编辑物料未写结构化审计"
            assert audit.target_id == mid
            old_data = json.loads(audit.old_data)
            new_data = json.loads(audit.new_data)
            assert abs((old_data.get("price") or 0) - 8) < 1e-6
            assert abs((new_data.get("price") or 0) - 99.9) < 1e-6
            assert old_data.get("code") == "M-EDIT"

    def test_delete_material_writes_audit(self, client):
        with app_module.app.app_context():
            db.session.add(Material(code="M-DEL", name="删除料", spec="S",
                                    category_id=1, unit_id=1, stock=0, price=5))
            db.session.commit()
            mid = Material.query.filter_by(code="M-DEL").first().id
        resp = client.post("/material/delete", json={"ids": [mid]})
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("delete_material")
            assert audit is not None, "删除物料未写结构化审计"
            old_data = json.loads(audit.old_data)
            assert old_data[0].get("code") == "M-DEL"
            assert old_data[0].get("id") == mid
            assert Material.query.get(mid) is None