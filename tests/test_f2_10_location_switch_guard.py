# -*- coding: utf-8 -*-
"""F2.10 ①：开启「库位管理」前的前置校验（审计报告 §1.3 高危）路由测试。

覆盖 ``save_system_settings`` 在 ``location_management_enabled`` 由 0→1 时：
  * 库位账与流水账一致 → 允许开启；
  * 存在不一致 → 400 拒绝，且开关保持关闭；
  * 已是开启状态（无 0→1 跃迁）→ 不再重复校验；
  * 拒绝时用回滚保证不产生半写入。
"""
from __future__ import annotations

import os
import re
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (LocationInventory, Material, StockTransaction,  # noqa: E402
                 Warehouse, db, location_management_enabled, set_system_setting)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

KEY = "location_management_enabled"


def _setup_client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        from app import ensure_default_system_settings
        ensure_default_system_settings()
        db.session.add(app_module.User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False))
        db.session.commit()
    client = app_module.app.test_client()
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login",
                data={"username": "admin", "password": "admin", "csrf_token": token})
    return client


def _seed_consistent():
    """三账一致：①=Σ②=Σ③=5。"""
    wh = Warehouse(code="WH001", name="项目仓")
    db.session.add(wh)
    db.session.commit()
    mat = Material(code="M001", name="一致物料", stock=5.0)
    db.session.add(mat)
    db.session.commit()
    db.session.add(LocationInventory(material_id=mat.id, warehouse_id=wh.id,
                                     location="项目仓", quantity=5.0))
    db.session.add(StockTransaction(material_id=mat.id, transaction_type="入库",
                                    quantity=5.0, warehouse_id=wh.id))
    db.session.commit()


def _seed_mismatch():
    """库位账 5、流水净额 0、总账 0 → ②≠③ 且 ①≠②。"""
    wh = Warehouse(code="WH001", name="项目仓")
    db.session.add(wh)
    db.session.commit()
    mat = Material(code="M002", name="脏数据物料", stock=0.0)
    db.session.add(mat)
    db.session.commit()
    db.session.add(LocationInventory(material_id=mat.id, warehouse_id=wh.id,
                                     location="WH001", quantity=5.0))
    db.session.commit()


def _post_enable(client):
    return client.post("/system_settings/save", data={KEY: "1"},
                       content_type="application/x-www-form-urlencoded")


class TestLocationSwitchGuard:
    def test_consistent_allows_enable(self):
        client = _setup_client()
        with app_module.app.app_context():
            _seed_consistent()
        resp = _post_enable(client)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()["status"] == "success"
        with app_module.app.app_context():
            assert location_management_enabled() is True

    def test_mismatch_rejects_enable(self):
        client = _setup_client()
        with app_module.app.app_context():
            _seed_mismatch()
        resp = _post_enable(client)
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "error"
        assert "库位管理" in body["msg"]
        assert "backfill_location_inventory" in body["msg"]
        # 拒绝后开关必须仍为关闭（回滚生效）
        with app_module.app.app_context():
            assert location_management_enabled() is False

    def test_empty_db_allows_enable(self):
        client = _setup_client()
        resp = _post_enable(client)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()["status"] == "success"

    def test_already_enabled_skips_recheck(self):
        # 已开启状态下再次提交（无 0→1 跃迁），即便有脏数据也不触发校验
        client = _setup_client()
        with app_module.app.app_context():
            _seed_mismatch()
            set_system_setting(KEY, "1")
            db.session.commit()
        resp = _post_enable(client)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert resp.get_json()["status"] == "success"


def test_find_location_ledger_mismatches():
    """判据本身：脏数据 → 报出仓级差异；一致 → 空（A9 覆盖新增业务函数）。"""
    from services.warehouse_stock_service import find_location_ledger_mismatches

    _setup_client()  # 初始化内存库
    with app_module.app.app_context():
        _seed_mismatch()
        findings = find_location_ledger_mismatches(limit=20)
    assert findings, "库位账 5 / 流水 0 应被判为不一致"
    assert "wh_location_vs_txn" in {f["dimension"] for f in findings}

    # 换成三账一致的数据 → 判据应返回空
    _setup_client()
    with app_module.app.app_context():
        _seed_consistent()
        findings = find_location_ledger_mismatches(limit=20)
    assert findings == []

