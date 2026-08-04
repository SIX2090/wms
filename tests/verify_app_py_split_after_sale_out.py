# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：售后出库（after_sale_out）域路由迁移到 routes/after_sale_out.py。

采用 register-on-app 模式（register_after_sale_out_routes(app)），endpoint 名保持不变
（如 after_sale_out_list、add_after_sale_out_order、complete_after_sale_out_order），
URL 路径不变，因此模板/导航中的 url_for('after_sale_out_list') 等引用无需改动。

验收点：
S1. 14 个 endpoint（after_sale_out_list / after_sale_out_detail /
    print_after_sale_out / after_sale_out_add_page / after_sale_out_edit_page /
    add_after_sale_out_order / complete_after_sale_out_order /
    revert_after_sale_out_order / delete_after_sale_out_order /
    copy_after_sale_out_order / batch_delete_after_sale_out /
    export_after_sale_out_template / download_after_sale_out_template /
    import_after_sale_out）已注册，且仍是未加前缀的原始 endpoint 名，
    不存在 after_sale_out.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变。
S3. 售后出库列表页可渲染（200，含"售后出库"字样）。
S4. 新增售后出库单成功（需仓库、明细）。
S5. 完成售后出库单成功（库存扣减）；反提交成功（库存恢复）。
S6. 删除待完成售后出库单成功；已完成的不可删除。
S7. 复制售后出库单生成新草稿。
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
from app import db, AfterSaleOutOrder, Material  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

AFTER_SALE_OUT_ENDPOINTS = [
    "after_sale_out_list",
    "after_sale_out_detail",
    "print_after_sale_out",
    "after_sale_out_add_page",
    "after_sale_out_edit_page",
    "add_after_sale_out_order",
    "complete_after_sale_out_order",
    "revert_after_sale_out_order",
    "delete_after_sale_out_order",
    "copy_after_sale_out_order",
    "batch_delete_after_sale_out",
    "export_after_sale_out_template",
    "download_after_sale_out_template",
    "import_after_sale_out",
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
    u = User(username="admin", password_hash=generate_password_hash("admin"), role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_base():
    """Create category / unit / warehouse / material master data."""
    from app import MaterialCategory, Unit, Warehouse
    cat = MaterialCategory(code="CAT1", name="分类1")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="WH001", name="材料仓", status="active", is_default=True)
    db.session.add_all([cat, unit, wh])
    db.session.flush()
    mat = Material(code="M1", name="轴承", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat.id


DB_MATERIAL_ID = {"id": None}


def _add_after_sale_out(client, order_no="ASO-TEST-001", **extra):
    payload = {
        "order_no": order_no,
        "date": "2024-01-01",
        "customer": "测试客户",
        "warehouse": "材料仓",
        "items": [{"code": "M1", "quantity": 2, "price": 10}],
    }
    payload.update(extra)
    return client.post("/after_sale_out/add", json=payload)


class TestAfterSaleOutRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            DB_MATERIAL_ID["id"] = _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：14 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in AFTER_SALE_OUT_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in AFTER_SALE_OUT_ENDPOINTS:
                assert f"after_sale_out.{ep}" not in app_module.app.view_functions, f"after_sale_out.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("after_sale_out_list") == "/after_sale_out"
                assert url_for("after_sale_out_detail", id=1) == "/after_sale_out/1"
                assert url_for("print_after_sale_out", id=1) == "/after_sale_out/1/print"
                assert url_for("after_sale_out_add_page") == "/after_sale_out/add"
                assert url_for("after_sale_out_edit_page", id=1) == "/after_sale_out/1/edit"
                assert url_for("add_after_sale_out_order") == "/after_sale_out/add"
                assert url_for("complete_after_sale_out_order", id=1) == "/after_sale_out/1/complete"
                assert url_for("revert_after_sale_out_order", id=1) == "/after_sale_out/1/revert"
                assert url_for("delete_after_sale_out_order", id=1) == "/after_sale_out/1/delete"
                assert url_for("copy_after_sale_out_order", id=1) == "/after_sale_out/1/copy"
                assert url_for("batch_delete_after_sale_out") == "/after_sale_out/batch_delete"
                assert url_for("export_after_sale_out_template") == "/export/template/after_sale_out"
                assert url_for("download_after_sale_out_template") == "/after_sale_out/download_template"
                assert url_for("import_after_sale_out") == "/after_sale_out/import"

    def test_list_page(self):
        """S3：售后出库列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/after_sale_out")
        assert resp.status_code == 200
        assert "售后出库" in resp.get_data(as_text=True)

    def test_add_order(self):
        """S4：新增售后出库单成功。"""
        client = self._setup()
        _login(client)
        resp = _add_after_sale_out(client, order_no="ASO-TEST-001")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["order_no"] == "ASO-TEST-001"
        with app_module.app.app_context():
            order = AfterSaleOutOrder.query.filter_by(order_no="ASO-TEST-001").first()
            assert order is not None
            assert order.customer == "测试客户"
            assert order.warehouse == "材料仓"
            assert len(order.items) == 1

    def test_add_order_requires_items(self):
        """S4b：无明细时拒绝保存。"""
        client = self._setup()
        _login(client)
        resp = client.post("/after_sale_out/add", json={
            "order_no": "ASO-TEST-EMPTY",
            "date": "2024-01-01",
            "customer": "测试客户",
            "warehouse": "材料仓",
            "items": [],
        })
        assert resp.get_json()["status"] == "error"

    def test_add_order_requires_warehouse(self):
        """S4c：无仓库且无默认仓库时拒绝保存。"""
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            from app import Warehouse
            Warehouse.query.filter_by(name="材料仓").delete()
            db.session.commit()
        resp = client.post("/after_sale_out/add", json={
            "order_no": "ASO-TEST-NOWH",
            "date": "2024-01-01",
            "customer": "测试客户",
            "items": [{"code": "M1", "quantity": 2, "price": 10}],
        })
        assert resp.get_json()["status"] == "error"

    def test_complete_and_revert(self):
        """S5：完成扣库存、反提交恢复库存。"""
        client = self._setup()
        _login(client)
        resp = _add_after_sale_out(client, order_no="ASO-TEST-001")
        order_id = resp.get_json()["id"]
        # 完成
        c = client.post(f"/after_sale_out/{order_id}/complete")
        assert c.get_json()["status"] == "success", c.get_json()
        with app_module.app.app_context():
            assert db.session.get(AfterSaleOutOrder, order_id).status == "completed"
            assert db.session.get(Material, DB_MATERIAL_ID["id"]).stock == 98
        # 重复完成被拒绝
        c2 = client.post(f"/after_sale_out/{order_id}/complete")
        assert c2.get_json()["status"] == "error"
        # 反提交
        r = client.post(f"/after_sale_out/{order_id}/revert")
        assert r.get_json()["status"] == "success", r.get_json()
        with app_module.app.app_context():
            assert db.session.get(AfterSaleOutOrder, order_id).status == "pending"
            assert db.session.get(Material, DB_MATERIAL_ID["id"]).stock == 100

    def test_delete(self):
        """S6：删除待完成单成功；已完成单不可删除。"""
        client = self._setup()
        _login(client)
        resp = _add_after_sale_out(client, order_no="ASO-TEST-001")
        order_id = resp.get_json()["id"]
        # 待完成可删除
        d = client.post(f"/after_sale_out/{order_id}/delete")
        assert d.get_json()["status"] == "success", d.get_json()
        with app_module.app.app_context():
            assert db.session.get(AfterSaleOutOrder, order_id) is None

        # 已完成不可删除
        resp2 = _add_after_sale_out(client, order_no="ASO-TEST-002")
        order_id2 = resp2.get_json()["id"]
        client.post(f"/after_sale_out/{order_id2}/complete")
        d2 = client.post(f"/after_sale_out/{order_id2}/delete")
        assert d2.get_json()["status"] == "error"
        with app_module.app.app_context():
            assert db.session.get(AfterSaleOutOrder, order_id2) is not None

    def test_copy(self):
        """S7：复制售后出库单生成新草稿。"""
        client = self._setup()
        _login(client)
        resp = _add_after_sale_out(client, order_no="ASO-TEST-001")
        order_id = resp.get_json()["id"]
        cp = client.post(f"/after_sale_out/{order_id}/copy")
        data = cp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            new_order = AfterSaleOutOrder.query.get(data["id"])
            assert new_order.order_no != "ASO-TEST-001"
            assert new_order.status == "pending"
            assert len(new_order.items) == 1