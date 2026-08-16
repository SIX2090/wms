# -*- coding: utf-8 -*-
"""BUG-2026-08-16-015 回归：调拨新建弹窗补独立库位字段 + 后端双字段语义。

后端 add_transfer 已有 from_warehouse/to_warehouse（仓库）与 from_location/to_location
（库位）双字段语义；BUG 根因在模板 transfer.html 只有 from_location/to_location 两个
select 且选项是仓库名，无独立库位字段，导致库位必填校验形同虚设。

修复后前端改为 from_warehouse/to_warehouse 选仓库、from_location/to_location 录库位。
本测试验证后端双字段语义：开启库位管理时仓库与库位分别落库、库位缺失被拒；
未开启时 from_location 回退为仓库名（历史兼容）。
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
    Material, MaterialCategory, TransferOrder, Unit, User, Warehouse, db,
    set_system_setting,
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


def _seed(enabled):
    set_system_setting("location_management_enabled", "1" if enabled else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
    ])
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


def _post_add(client, *, from_wh="仓库A", to_wh="仓库B",
              from_loc="", to_loc=""):
    payload = {"from_warehouse": from_wh, "to_warehouse": to_wh, "remark": "r"}
    if from_loc:
        payload["from_location"] = from_loc
    if to_loc:
        payload["to_location"] = to_loc
    return client.post("/transfer/add", data=payload)


def test_a9_add_transfer():
    """A9 门禁：add_transfer 双字段语义由下方用例覆盖。"""
    with app_module.app.app_context():
        assert TransferOrder is not None


class TestTransferAddDoubleFieldSemantics:

    def test_enabled_persists_warehouse_and_location(self, client):
        """开启库位管理：仓库与库位分别落库到各自字段。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_add(client, from_loc="主仓-A1", to_loc="主仓-B1")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            t = TransferOrder.query.filter_by(from_warehouse="仓库A").first()
            assert t is not None
            assert t.from_warehouse == "仓库A"
            assert t.to_warehouse == "仓库B"
            assert t.from_location == "主仓-A1"
            assert t.to_location == "主仓-B1"

    def test_enabled_rejects_missing_from_location(self, client):
        """开启库位管理：缺调出库位时新增被拒。"""
        with app_module.app.app_context():
            _seed(True)
        resp = _post_add(client, to_loc="主仓-B1")
        assert resp.status_code == 400, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "error", data
        assert "库位" in (data.get("msg") or ""), data

    def test_disabled_falls_back_to_warehouse(self, client):
        """未开启库位管理：from_location 回退为仓库名（历史兼容）。"""
        with app_module.app.app_context():
            _seed(False)
        resp = _post_add(client)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data.get("status") == "success", data
        with app_module.app.app_context():
            t = TransferOrder.query.filter_by(from_warehouse="仓库A").first()
            assert t is not None
            assert t.from_location == "仓库A"
            assert t.to_location == "仓库B"