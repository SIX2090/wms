# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：调拨（transfer）域路由迁移到 routes/transfer.py。

采用 register-on-app 模式（register_transfer_routes(app)），endpoint 名保持不变
（如 transfer_list、add_transfer、complete_transfer、revert_transfer 等），
URL 路径不变，因此模板/导航中的 url_for 引用无需改动。

验收点：
S1. 21 个 endpoint 已注册，且仍是未加前缀的原始 endpoint 名，
    不存在 transfer.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变。
S3. 调拨列表页可渲染（200，含"库存调拨"或"调拨"字样）。
S4. 新增调拨单成功（需调出/调入仓库）。
S5. 添加调拨明细成功。
S6. 完成调拨单成功（状态 completed）；反提交成功（状态回 pending）。
S7. 待提交调拨单可删除；已完成不可删除。
S8. 复制调拨单生成新草稿。
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
from app import db, TransferOrder, TransferOrderItem, Material  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TRANSFER_ENDPOINTS = [
    "transfer_list",
    "transfer_add_page",
    "transfer_detail",
    "save_transfer_table",
    "add_transfer",
    "add_transfer_item",
    "delete_transfer_item",
    "update_transfer_item",
    "batch_delete_transfer_items",
    "complete_transfer",
    "revert_transfer",
    "update_transfer",
    "copy_transfer",
    "delete_transfer",
    "batch_delete_transfer",
    "export_transfer",
    "export_transfer_template",
    "import_transfer",
    "batch_add_transfer_items",
    "export_single_transfer",
    "print_single_transfer",
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
    """Create category / unit / two warehouses / material master data."""
    from app import MaterialCategory, StockTransaction, Unit, Warehouse
    cat = MaterialCategory(code="CAT1", name="分类1")
    unit = Unit(code="PCS", name="个")
    wh_from = Warehouse(code="WH001", name="材料仓", status="active", is_default=True)
    wh_to = Warehouse(code="WH002", name="成品仓", status="active", is_default=False)
    db.session.add_all([cat, unit, wh_from, wh_to])
    db.session.flush()
    mat = Material(code="M1", name="轴承", category_id=cat.id, unit_id=unit.id, stock=100, price=10)
    db.session.add(mat)
    db.session.flush()
    db.session.add(StockTransaction(
        material_id=mat.id,
        transaction_type="in",
        quantity=100,
        location=wh_from.name,
        reference_type="test_seed",
        reference_id=0,
        remark=""
    ))
    db.session.commit()
    return mat.id


DB_MATERIAL_ID = {"id": None}


def _add_transfer(client, **extra):
    payload = {
        "from_warehouse": "材料仓",
        "to_warehouse": "成品仓",
        "remark": "测试调拨",
    }
    payload.update(extra)
    return client.post("/transfer/add", data=payload)


def _add_item(client, order_id, code="M1", quantity=2, price=10):
    return client.post(f"/transfer/{order_id}/item/add", data={
        "material_code": code,
        "quantity": quantity,
        "price": price,
    })


class TestTransferRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            DB_MATERIAL_ID["id"] = _seed_base()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：21 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in TRANSFER_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in TRANSFER_ENDPOINTS:
                assert f"transfer.{ep}" not in app_module.app.view_functions, f"transfer.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("transfer_list") == "/transfer"
                assert url_for("transfer_add_page") == "/transfer/add"
                assert url_for("transfer_detail", id=1) == "/transfer/1"
                assert url_for("add_transfer") == "/transfer/add"
                assert url_for("add_transfer_item", id=1) == "/transfer/1/item/add"
                assert url_for("delete_transfer_item", id=1, item_id=2) == "/transfer/1/item/2/delete"
                assert url_for("complete_transfer", id=1) == "/transfer/1/complete"
                assert url_for("revert_transfer", id=1) == "/transfer/1/revert"
                assert url_for("copy_transfer", id=1) == "/transfer/1/copy"
                assert url_for("delete_transfer", id=1) == "/transfer/1/delete"
                assert url_for("batch_delete_transfer") == "/transfer/batch_delete"
                assert url_for("export_single_transfer", id=1) == "/transfer/1/export"
                assert url_for("print_single_transfer", id=1) == "/transfer/1/print"

    def test_list_page(self):
        """S3：调拨列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/transfer")
        assert resp.status_code == 200
        assert ("库存调拨" in resp.get_data(as_text=True)) or ("调拨" in resp.get_data(as_text=True))

    def test_add_transfer(self):
        """S4：新增调拨单成功。"""
        client = self._setup()
        _login(client)
        resp = _add_transfer(client)
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            order = db.session.get(TransferOrder, data["id"])
            assert order is not None
            assert order.from_warehouse == "材料仓"
            assert order.to_warehouse == "成品仓"
            assert order.status == "pending"

    def test_add_transfer_requires_warehouses(self):
        """S4b：缺调出/调入仓库时拒绝。"""
        client = self._setup()
        _login(client)
        r1 = _add_transfer(client, from_warehouse="")
        assert r1.get_json()["status"] == "error"
        r2 = _add_transfer(client, to_warehouse="")
        assert r2.get_json()["status"] == "error"
        r3 = _add_transfer(client, from_warehouse="材料仓", to_warehouse="材料仓")
        assert r3.get_json()["status"] == "error"

    def test_add_item_and_complete(self):
        """S5/S6：添加明细、完成调拨、反提交。"""
        client = self._setup()
        _login(client)
        order_id = _add_transfer(client).get_json()["id"]
        # 添加明细
        it = _add_item(client, order_id)
        assert it.get_json()["status"] == "success", it.get_json()
        with app_module.app.app_context():
            order = db.session.get(TransferOrder, order_id)
            assert len(order.items) == 1
            assert order.items[0].quantity == 2
        # 完成
        c = client.post(f"/transfer/{order_id}/complete")
        assert c.get_json()["status"] == "success", c.get_json()
        with app_module.app.app_context():
            assert db.session.get(TransferOrder, order_id).status == "completed"
        # 重复完成被拒绝
        c2 = client.post(f"/transfer/{order_id}/complete")
        assert c2.get_json()["status"] == "error"
        # 反提交
        r = client.post(f"/transfer/{order_id}/revert")
        assert r.get_json()["status"] == "success", r.get_json()
        with app_module.app.app_context():
            assert db.session.get(TransferOrder, order_id).status == "pending"

    def test_delete(self):
        """S7：待提交可删除；已完成不可删除。"""
        client = self._setup()
        _login(client)
        order_id = _add_transfer(client).get_json()["id"]
        d = client.post(f"/transfer/{order_id}/delete")
        assert d.get_json()["status"] == "success", d.get_json()
        with app_module.app.app_context():
            assert db.session.get(TransferOrder, order_id) is None

        order_id2 = _add_transfer(client).get_json()["id"]
        _add_item(client, order_id2)
        client.post(f"/transfer/{order_id2}/complete")
        d2 = client.post(f"/transfer/{order_id2}/delete")
        assert d2.get_json()["status"] == "error"
        with app_module.app.app_context():
            assert db.session.get(TransferOrder, order_id2) is not None

    def test_copy(self):
        """S8：复制调拨单生成新草稿。"""
        client = self._setup()
        _login(client)
        order_id = _add_transfer(client).get_json()["id"]
        _add_item(client, order_id)
        with app_module.app.app_context():
            orig_no = db.session.get(TransferOrder, order_id).transfer_no
        cp = client.post(f"/transfer/{order_id}/copy")
        data = cp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            new_order = TransferOrder.query.filter(
                TransferOrder.status == "pending",
                TransferOrder.transfer_no != orig_no,
            ).order_by(TransferOrder.id.desc()).first()
            assert new_order is not None
            assert len(new_order.items) == 1