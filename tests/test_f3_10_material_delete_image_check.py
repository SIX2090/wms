# -*- coding: utf-8 -*-
"""F3.10 物料删除补 MaterialImage 检查（审计 §3.4 低危）。

根因：delete_material 的引用检查未覆盖 MaterialImage——有图片的物料走
raw DELETE 撞 FK 后只落一个静默的「失败 N 条」，用户不知道失败原因。

修复：先查物料图片，有图片直接业务拒绝并在响应里给出
「<物料编码>：存在物料图片」的明确提示；其余业务引用失败也附原因。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, MaterialCategory, MaterialImage, Supplier, Unit, User,
    Warehouse, db,
)


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
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WH01", name="主仓"),
        ])
        db.session.commit()
    c = app_module.app.test_client()
    page = c.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    c.post("/login", data={
        "username": "admin", "password": "admin",
        "csrf_token": token.group(1) if token else "",
    })
    yield c


def _mk_material(code):
    with app_module.app.app_context():
        m = Material(code=code, name="F3.10物料", spec="S",
                     category_id=1, unit_id=1, supplier_id=1, stock=0, price=1)
        db.session.add(m)
        db.session.commit()
        return m.id


def test_delete_material_with_image_blocked_with_clear_message(client):
    """有图片的物料：删除被拒且响应明确提示「存在物料图片」。"""
    mat_id = _mk_material("M-IMG")
    with app_module.app.app_context():
        db.session.add(MaterialImage(material_id=mat_id, image="uploads/x.png"))
        db.session.commit()

    resp = client.post("/material/delete", json={"ids": [mat_id]})
    assert resp.status_code == 400, f"有图片应业务拒绝，实际 {resp.status_code}"
    data = resp.get_json()
    assert data["status"] == "error"
    assert "存在物料图片" in data.get("msg", "") or "存在物料图片" in str(data), \
        f"应提示存在物料图片，实际 {data}"

    with app_module.app.app_context():
        assert db.session.get(Material, mat_id) is not None, "物料不得被删除"


def test_delete_material_without_image_still_works(client):
    """无图片无引用物料：删除正常成功（行为不回归）。"""
    mat_id = _mk_material("M-NOIMG")
    resp = client.post("/material/delete", json={"ids": [mat_id]})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success", f"应删除成功，实际 {data}"
    with app_module.app.app_context():
        assert db.session.get(Material, mat_id) is None
