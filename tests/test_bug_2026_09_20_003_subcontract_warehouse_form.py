# -*- coding: utf-8 -*-
"""BUG-2026-09-20-003 回归：委外发料/收货新增表单补仓库字段（P1-1 仓库必填落地缺口）。

修复前：subcontract_issue.html / subcontract_receive.html 新增模态框根本不带
仓库字段，用户无法选择，只能依赖后端「父单继承→默认仓」静默兜底——多仓库
部署下用户不知道单据落哪个仓，违反 AGENTS.md 仓库必填的可感知原则。

修复后要求：
- 两个列表页渲染的新增表单含 name="warehouse" + required + 默认仓 selected
  + 委外单选项带 data-warehouse 联动；
- 显式选择仓库提交 → 按所选仓库落单（不再被父单/默认仓静默覆盖）；
- 不传仓库（API/旧客户端）→ 保留父单继承兜底（向后兼容）。
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

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Material, MaterialCategory, SubcontractIssue,  # noqa: E402
                 SubcontractOrder, SubcontractReceive, Supplier, Unit, User,
                 Warehouse, db, set_system_setting)


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
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="加工厂"),
            Warehouse(code="WH01", name="主仓", status="active", is_default=True),
            Warehouse(code="WH02", name="委外仓", status="active", is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(code="M-RAW", name="原材料", spec="S",
                                category_id=1, unit_id=1, supplier_id=1, stock=100, price=1))
        db.session.add(SubcontractOrder(order_no="SC001", supplier_id=1,
                                        warehouse="主仓", status="processing"))
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _order_id():
    with app_module.app.app_context():
        return SubcontractOrder.query.filter_by(order_no="SC001").one().id


# ---------- 表单渲染 ----------

def test_issue_form_has_required_warehouse_select(client):
    html = client.get("/subcontract_issue").get_data(as_text=True)
    assert 'name="warehouse"' in html
    assert 'id="issueWarehouse"' in html
    assert "请选择仓库" in html
    # required + 默认仓 selected + 委外单联动数据
    m = re.search(r'<select[^>]*name="warehouse"[^>]*>', html)
    assert m and "required" in m.group(0)
    assert 'data-warehouse="主仓"' in html
    default_opt = re.search(
        r'<option value="主仓"[^>]*selected[^>]*>', html)
    assert default_opt, "默认仓应预选中"


def test_receive_form_has_required_warehouse_select(client):
    html = client.get("/subcontract_receive").get_data(as_text=True)
    assert 'name="warehouse"' in html
    assert 'id="receiveWarehouse"' in html
    m = re.search(r'<select[^>]*name="warehouse"[^>]*>', html)
    assert m and "required" in m.group(0)
    assert 'data-warehouse="主仓"' in html
    assert re.search(r'<option value="主仓"[^>]*selected[^>]*>', html)


# ---------- 提交行为 ----------

def test_issue_add_uses_explicit_warehouse(client):
    resp = client.post("/subcontract/issue/add", data={
        "subcontract_order_id": str(_order_id()),
        "warehouse": "委外仓",
        "remark": "显式选仓",
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
        assert issue.warehouse == "委外仓"


def test_receive_add_uses_explicit_warehouse(client):
    resp = client.post("/subcontract/receive/add", data={
        "subcontract_order_id": str(_order_id()),
        "warehouse": "委外仓",
        "remark": "显式选仓",
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        receive = SubcontractReceive.query.order_by(SubcontractReceive.id.desc()).first()
        assert receive.warehouse == "委外仓"


def test_issue_add_without_warehouse_keeps_parent_fallback(client):
    """API/旧客户端不传仓库：保留父单继承兜底（向后兼容，不受本次表单改动影响）。"""
    resp = client.post("/subcontract/issue/add", data={
        "subcontract_order_id": str(_order_id()),
        "remark": "未传仓库",
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
        assert issue.warehouse == "主仓"


def test_receive_add_without_warehouse_keeps_parent_fallback(client):
    resp = client.post("/subcontract/receive/add", data={
        "subcontract_order_id": str(_order_id()),
        "remark": "未传仓库",
    })
    body = resp.get_json()
    assert body["status"] == "success", body
    with app_module.app.app_context():
        receive = SubcontractReceive.query.order_by(SubcontractReceive.id.desc()).first()
        assert receive.warehouse == "主仓"
