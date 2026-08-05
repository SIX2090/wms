# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：库存调整（adjustment）域路由迁移到 routes/adjustment.py。

register-on-app 模式（register_adjustment_routes(app)），endpoint 名与 URL 不变。

验收点：
A1. 核心 endpoint 已注册，且无 adjustment.xxx 前缀重复。
A2. URL 路径保持不变。
A3. 库存调整列表页可渲染（200）。
A4. 新增库存调整单成功（需物料/默认仓库）。
A5. 拆分模块 routes/adjustment.py 可正常导入并暴露 register_adjustment_routes。
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
from app import AdjustmentOrder, AdjustmentOrderItem, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = [
    "adjustment_list", "adjustment_add_page", "adjustment_detail",
    "print_adjustment", "add_adjustment", "complete_adjustment",
    "revert_adjustment", "delete_adjustment", "batch_delete_adjustment",
    "export_adjustment", "import_adjustment",
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


_MATERIAL_ID = {"id": None}


def _seed_base():
    from app import Material, MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="ACAT", name="调整分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="AWH", name="调整仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="AM1", name="调整物料", category_id=cat.id, unit_id=unit.id, stock=100, price=5)
    db.session.add(mat)
    db.session.commit()
    _MATERIAL_ID["id"] = mat.id


class TestAdjustmentRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        with app_module.app.app_context():
            for ep in ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
                assert f"adjustment.{ep}" not in app_module.app.view_functions, f"adjustment.{ep} 重复注册"
        from flask import url_for
        with app_module.app.test_request_context():
            assert url_for("adjustment_list") == "/adjustment"
            assert url_for("adjustment_add_page") == "/adjustment/add"
            assert url_for("add_adjustment") == "/adjustment/add"
            assert url_for("adjustment_detail", id=1) == "/adjustment/1"
            assert url_for("print_adjustment", id=1) == "/adjustment/1/print"
            assert url_for("complete_adjustment", id=1) == "/adjustment/1/complete"
            assert url_for("revert_adjustment", id=1) == "/adjustment/1/revert"
            assert url_for("delete_adjustment", id=1) == "/adjustment/1/delete"
            assert url_for("batch_delete_adjustment") == "/adjustment/batch_delete"
            assert url_for("export_adjustment") == "/adjustment/export"
            assert url_for("import_adjustment") == "/adjustment/import"

    def test_module_importable(self):
        # 拆分模块可正常导入且暴露注册入口（不注册到 app，避免与内联路由重复）
        import routes.adjustment as adjustment_module
        assert hasattr(adjustment_module, "register_adjustment_routes")
        assert callable(adjustment_module.register_adjustment_routes)

    def test_list_page(self):
        client = self._setup()
        _login(client)
        resp = client.get("/adjustment")
        assert resp.status_code == 200
        assert "库存调整" in resp.get_data(as_text=True)

    def test_add_adjustment(self):
        client = self._setup()
        _login(client)
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "surplus",
            "warehouse": "调整仓",
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 5, "reason": "盘点差异测试"}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            adj = db.session.get(AdjustmentOrder, data["id"])
            assert adj is not None
            assert adj.status == "pending"
            assert adj.adjustment_type == "surplus"
            assert adj.warehouse == "调整仓"
            assert len(adj.items) == 1
            assert adj.items[0].quantity == 5
            assert adj.items[0].reason == "盘点差异测试"

    def test_complete_and_revert_adjustment(self):
        client = self._setup()
        _login(client)
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "loss",
            "warehouse": "调整仓",
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 3, "reason": "盘亏测试"}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        adj_id = data["id"]
        with app_module.app.app_context():
            adj = db.session.get(AdjustmentOrder, adj_id)
            assert adj.items[0].quantity == -3
        # 完成（盘亏扣减库存）
        resp = client.post(f"/adjustment/{adj_id}/complete")
        assert resp.get_json()["status"] == "success"
        with app_module.app.app_context():
            adj = db.session.get(AdjustmentOrder, adj_id)
            assert adj.status == "completed"
        # 已完成单不可直接删除
        resp = client.post(f"/adjustment/{adj_id}/delete")
        assert resp.get_json()["status"] != "success"
        # 反提交回退库存
        resp = client.post(f"/adjustment/{adj_id}/revert")
        assert resp.get_json()["status"] == "success"
        with app_module.app.app_context():
            adj = db.session.get(AdjustmentOrder, adj_id)
            assert adj.status == "pending"

    def test_delete_draft_adjustment(self):
        client = self._setup()
        _login(client)
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "surplus",
            "warehouse": "调整仓",
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 2, "reason": "草稿删除测试"}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        adj_id = data["id"]
        resp = client.post(f"/adjustment/{adj_id}/delete")
        assert resp.get_json()["status"] == "success"
        # 批量删除
        resp = client.post("/adjustment/add", json={
            "adjustment_type": "surplus",
            "warehouse": "调整仓",
            "items": [{"material_id": _MATERIAL_ID["id"], "quantity": 1, "reason": "批量删除测试"}],
        })
        data = resp.get_json()
        assert data["status"] == "success", data
        resp = client.post("/adjustment/batch_delete", json={"ids": [data["id"]]})
        assert resp.get_json()["status"] == "success"