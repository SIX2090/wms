# -*- coding: utf-8 -*-
"""回归测试：物料删除在旧库缺新增 AI 关联表时不得返回 500 HTML。

背景（BUG-2026-08-05）：delete_material 迁移到 routes/material.py 后新增了对
AIMaterialAlias / AIDocumentItem 的引用检查，但整段 if 未 try/except；且 ORM
db.session.delete(material) 会级联加载 ai_aliases / ai_document_items backref。
若生产库为旧库、缺少新增的 ai_material_alias / ai_document_item 表，删除任意物料
都会抛 OperationalError -> 500 HTML -> 前端 response.json() 报
"Unexpected token T, 'Internal S'... is not valid JSON"，表现为所有物料都删不掉。

修复：引用检查逐表 try/except（缺表视为无引用）；主数据删除改用 raw SQL，
绕过 ORM 级联加载缺失表。本测试复现缺表场景并断言返回 JSON 200。
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
    Material, MaterialCategory, Supplier, Unit, User, Warehouse, db,
)


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True  # 若回归 500，会让异常上抛使测试失败
    with app_module.app.app_context():
        db.drop_all()  # 内存库允许重建，保证每个测试拿到干净库
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
        m = Material(code="M-NOREF", name="无引用", spec="S",
                     category_id=1, unit_id=1, supplier_id=1, stock=0, price=1)
        db.session.add(m)
        db.session.commit()
        db.session.add(_material_id(m))
        db.session.commit()
    c = app_module.app.test_client()
    page = c.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    c.post("/login", data={
        "username": "admin", "password": "admin",
        "csrf_token": token.group(1) if token else "",
    })
    yield c


def _material_id(m):
    return Material.query.filter_by(code=m.code).first()


def _drop_ai_document_item_table():
    with app_module.app.app_context():
        db.session.execute(db.text("DROP TABLE IF EXISTS ai_document_item"))
        db.session.commit()


def test_delete_material_succeeds_when_ai_document_item_table_missing(client):
    """缺 ai_document_item 表时，删除无引用物料必须返回 JSON 200 而非 500 HTML。"""
    with app_module.app.app_context():
        mat = Material.query.filter_by(code="M-NOREF").first()
        mat_id = mat.id
    _drop_ai_document_item_table()

    resp = client.post("/material/delete", json={"ids": [mat_id]})
    ctype = resp.headers.get("Content-Type", "")
    body = resp.get_data(as_text=True)
    assert "application/json" in ctype, f"必须返回 JSON，实际 Content-Type={ctype}，body={body[:80]!r}"
    assert "Internal Server Error" not in body, "不得返回 500 HTML 页面"
    assert resp.status_code == 200, f"删除应成功，实际 status={resp.status_code}"
    data = resp.get_json()
    assert data["status"] == "success", f"应删除成功，实际 {data}"

    with app_module.app.app_context():
        assert db.session.get(Material, mat_id) is None, "物料应已被删除"


def test_delete_material_still_blocks_referenced_when_ai_table_missing(client):
    """缺 ai_document_item 表时，被采购订单引用的物料仍应业务拒绝（400 JSON）。"""
    with app_module.app.app_context():
        from app import PurchaseOrder, PurchaseOrderItem
        mat = Material.query.filter_by(code="M-NOREF").first()
        mat_id = mat.id
        po = PurchaseOrder(order_no="PO-X", supplier_id=1, status="pending", total_amount=0)
        db.session.add(po)
        db.session.commit()
        db.session.add(PurchaseOrderItem(
            purchase_order_id=po.id, material_id=mat_id, quantity=1, price=1, amount=1))
        db.session.commit()
    _drop_ai_document_item_table()

    resp = client.post("/material/delete", json={"ids": [mat_id]})
    ctype = resp.headers.get("Content-Type", "")
    assert "application/json" in ctype, "必须返回 JSON"
    assert resp.status_code == 400, f"被引用物料应返回 400 业务拒绝，实际 {resp.status_code}"
    data = resp.get_json()
    assert data["status"] == "error", f"应拒绝删除，实际 {data}"