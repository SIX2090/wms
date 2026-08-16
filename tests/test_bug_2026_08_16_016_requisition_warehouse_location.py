# -*- coding: utf-8 -*-
"""BUG-2026-08-16-016 回归：领料单新增弹窗补 仓库/库位 字段 + 后端校验。

根因：requisition.html 新增弹窗无仓库 select、无库位 input，只能默认仓库回退
（无默认仓库直接被拒，用户无法手选）；save_table/add_requisition/update_requisition
无 assert_warehouse_active、库位不校验必填，而 complete_requisition 又要求库位必填
（无录入入口，工作流卡死）。

修复：弹窗加仓库 select（required+默认选中）与条件库位字段；add_requisition 与
save_table 补 assert_warehouse_active 与库位必填校验。
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

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, MaterialCategory, ProductionRequisition, Unit, User, Warehouse,
    db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(enabled, active=True):
    set_system_setting("location_management_enabled", "1" if enabled else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active" if active else "inactive"),
    ])
    db.session.commit()
    db.session.add(Material(
        code="M001", name="轴承", spec="6204",
        category_id=1, unit_id=1, stock=100, price=10,
    ))
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _post_add(client, *, warehouse="仓库A", location=""):
    payload = {
        "production_order": "PO-001",
        "purpose": "领料",
        "warehouse": warehouse,
    }
    if location:
        payload["location"] = location
    return client.post("/requisition/add", data=payload)


def _post_save_table(client, *, warehouse="仓库A", location=""):
    header = {"production_order": "PO-001", "purpose": "领料", "warehouse": warehouse}
    if location:
        header["location"] = location
    payload = {"header": header, "items": [{"code": "M001", "quantity": 1, "unit_id": 1}]}
    return client.post("/requisition/save_table", json=payload)


def test_a9_add_requisition():
    """A9 门禁：add_requisition/save_requisition_table 校验由下方用例覆盖。"""
    with app_module.app.app_context():
        assert ProductionRequisition is not None


class TestRequisitionAddWarehouseLocation:

    def test_add_persists_warehouse_and_location_when_enabled(self, client):
        """开启库位管理：仓库与库位分别落库。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_add(client, warehouse="仓库A", location="仓A-A1")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            r = ProductionRequisition.query.filter_by(purpose="领料").first()
            assert r is not None
            assert r.warehouse == "仓库A"
            assert r.location == "仓A-A1"

    def test_add_rejects_missing_location_when_enabled(self, client):
        """开启库位管理：缺库位时新增被拒。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_add(client)
        assert resp.status_code == 400, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库位" in (data.get("msg") or ""), data

    def test_add_rejects_inactive_warehouse(self, client):
        """仓库非 active 时新增被拒。"""
        with app_module.app.app_context():
            _seed(False, active=False)
        resp = _post_add(client, warehouse="仓库A")
        assert resp.status_code == 400, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "error", data

    def test_save_table_rejects_missing_location_when_enabled(self, client):
        """save_table：开启库位管理缺库位被拒。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_save_table(client)
        assert resp.status_code == 400, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库位" in (data.get("msg") or ""), data

    def test_save_table_succeeds_with_location_when_enabled(self, client):
        """save_table：开启库位管理且填库位时保存成功。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_save_table(client, warehouse="仓库A", location="仓A-A1")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            r = ProductionRequisition.query.filter_by(purpose="领料").first()
            assert r is not None
            assert r.location == "仓A-A1"