# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：物料（material）域路由迁移到 routes/material.py。

采用 register-on-app 模式（register_material_routes(app)），endpoint 名保持不变
（如 material_list），URL 路径不变，因此模板/导航中的 url_for('material_list')
等引用无需改动。

验收点：
S1. 16 个 endpoint（material_list/material_api_list/material_api_all/add_material/
    get_material/material_image_candidates/material_image_select/copy_material/
    edit_material/delete_all_materials/fix_empty_fields/delete_material/
    download_material_template/export_material/import_material/
    material_print_label_not_implemented）已注册，且仍是未加前缀的原始 endpoint 名
    （与 app.py 原实现一致），不存在 material.xxx 带前缀的重复 endpoint。
S2. URL 路径保持不变（/material、/material/api/list、/material/api/all、
    /material/add、/material/<id>、/material/<id>/image_candidates、
    /material/<id>/image_select、/material/<id>/copy、/material/edit/<id>、
    /material/delete_all、/material/fix_empty_fields、/material/delete、
    /material/download_template、/material/export、/material/import、
    /material/print_label）。
S3. 物料列表页可渲染（200，含"物料"字样）。
S4. 新增物料成功；编码必填/重复被拒绝。
S5. 读取物料详情成功。
S6. 行级编辑成功；编码重复（不同物料）被拒绝。
S7. 删除物料：无业务引用时删除成功。
S8. 导入物料：合法行新增，重复编码跳过。
"""
from __future__ import annotations

import io
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
from app import db, Material  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

MATERIAL_ENDPOINTS = [
    "material_list",
    "material_api_list",
    "material_api_all",
    "add_material",
    "get_material",
    "material_image_candidates",
    "material_image_select",
    "copy_material",
    "edit_material",
    "delete_all_materials",
    "fix_empty_fields",
    "delete_material",
    "download_material_template",
    "export_material",
    "import_material",
    "material_print_label_not_implemented",
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


def _add_material(client, code="M001", name="轴承", **extra):
    data = {"code": code, "name": name}
    data.update(extra)
    return client.post("/material/add", data=data)


class TestMaterialRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：16 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in MATERIAL_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            # 不应出现带前缀的重复 endpoint
            for ep in MATERIAL_ENDPOINTS:
                assert f"material.{ep}" not in app_module.app.view_functions, f"material.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("material_list") == "/material"
                assert url_for("material_api_list") == "/material/api/list"
                assert url_for("material_api_all") == "/material/api/all"
                assert url_for("add_material") == "/material/add"
                assert url_for("get_material", id=1) == "/material/1"
                assert url_for("material_image_candidates", id=1) == "/material/1/image_candidates"
                assert url_for("material_image_select", id=1) == "/material/1/image_select"
                assert url_for("copy_material", id=1) == "/material/1/copy"
                assert url_for("edit_material", id=1) == "/material/edit/1"
                assert url_for("delete_all_materials") == "/material/delete_all"
                assert url_for("fix_empty_fields") == "/material/fix_empty_fields"
                assert url_for("delete_material") == "/material/delete"
                assert url_for("download_material_template") == "/material/download_template"
                assert url_for("export_material") == "/material/export"
                assert url_for("import_material") == "/material/import"
                assert url_for("material_print_label_not_implemented") == "/material/print_label"

    def test_material_list(self):
        """S3：列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/material")
        assert resp.status_code == 200
        assert "物料" in resp.get_data(as_text=True)

    def test_specification_fields_use_wide_layout(self):
        client = self._setup()
        _login(client)
        page = client.get("/material").get_data(as_text=True)
        assert 'class="col-md-6"' in page
        assert 'name="spec" id="add_spec" maxlength="100"' in page
        assert 'name="spec" id="edit_spec" maxlength="100"' in page

    def test_add_material(self):
        """S4：新增成功、编码必填、重复被拒绝。"""
        client = self._setup()
        _login(client)
        resp = _add_material(client, code="M001", name="轴承")
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Material.query.filter_by(code="M001").first() is not None
        # 编码必填
        r1 = _add_material(client, code="", name="轴承2")
        assert r1.get_json()["status"] == "error"
        # 编码重复
        r2 = _add_material(client, code="M001", name="轴承3")
        assert r2.get_json()["status"] == "error"

    def test_get_material(self):
        """S5：读取物料详情。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        with app_module.app.app_context():
            mid = Material.query.filter_by(code="M001").first().id
        g = client.get(f"/material/{mid}")
        data = g.get_json()
        assert data["status"] == "success"
        assert data["material"]["code"] == "M001"

    def test_edit_material(self):
        """S6：行级编辑成功；编码改为另一物料占据的编码被拒绝。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        _add_material(client, code="M002", name="螺母")
        with app_module.app.app_context():
            m1 = Material.query.filter_by(code="M001").first().id
            m2 = Material.query.filter_by(code="M002").first().id
        resp = client.post(f"/material/edit/{m1}", data={"code": "M001", "name": "深沟球轴承", "spec": "6204"})
        assert resp.get_json()["status"] == "success", resp.get_json()
        with app_module.app.app_context():
            assert Material.query.get(m1).name == "深沟球轴承"
        # 编码改为另一物料已占用的编码
        r = client.post(f"/material/edit/{m1}", data={"code": "M002", "name": "深沟球轴承"})
        assert r.get_json()["status"] == "error"

    def test_delete_material(self):
        """S7：无业务引用时删除成功。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        with app_module.app.app_context():
            mid = Material.query.filter_by(code="M001").first().id
        resp = client.post("/material/delete", json={"ids": [mid]})
        data = resp.get_json()
        assert data["status"] == "success", data
        with app_module.app.app_context():
            assert Material.query.get(mid) is None

    def test_delete_material_referenced_by_purchase_order_item(self):
        """S7b：被采购/销售订单项引用的物料应被引用完整性拦截，返回清晰业务提示而非数据库外键错误。"""
        from app import Customer, PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem, Supplier, Unit, MaterialCategory, User
        client = self._setup()
        _login(client)
        with app_module.app.app_context():
            unit = Unit(name="个", code="PCS")
            cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
            sup = Supplier(code="SUP001", name="供应商")
            cus = Customer(code="C001", name="客户")
            db.session.add_all([unit, cat, sup, cus])
            db.session.commit()
            # 被采购订单项引用
            m_po = Material(code="M-PO", name="被采购订单引用", unit_id=unit.id, category_id=cat.id, supplier_id=sup.id)
            db.session.add(m_po)
            po = PurchaseOrder(order_no="PO-001", supplier_id=sup.id, status="pending", total_amount=0)
            db.session.add(po)
            db.session.flush()
            po_item = PurchaseOrderItem(purchase_order_id=po.id, material_id=m_po.id, quantity=5, price=2, amount=10)
            db.session.add(po_item)
            # 被销售订单项引用
            m_so = Material(code="M-SO", name="被销售订单引用", unit_id=unit.id, category_id=cat.id, supplier_id=sup.id)
            db.session.add(m_so)
            so = SalesOrder(order_no="SO-001", customer_id=cus.id, status="pending", total_amount=0)
            db.session.add(so)
            db.session.flush()
            so_item = SalesOrderItem(sales_order_id=so.id, material_id=m_so.id, quantity=3, price=5, amount=15)
            db.session.add(so_item)
            db.session.commit()
            po_id, so_id = m_po.id, m_so.id
        # 被采购订单引用：不删除，返回清晰错误，不抛数据库外键异常
        resp = client.post("/material/delete", json={"ids": [po_id]})
        data = resp.get_json()
        assert data["status"] == "error", data
        assert "数据库操作失败" not in data.get("msg", ""), data
        with app_module.app.app_context():
            assert Material.query.get(po_id) is not None
            assert PurchaseOrderItem.query.filter_by(material_id=po_id).first() is not None
        # 被销售订单引用：同样拦截，明细保留
        resp = client.post("/material/delete", json={"ids": [so_id]})
        data = resp.get_json()
        assert data["status"] == "error", data
        assert "数据库操作失败" not in data.get("msg", ""), data
        with app_module.app.app_context():
            assert Material.query.get(so_id) is not None
            assert SalesOrderItem.query.filter_by(material_id=so_id).first() is not None

    def test_import_material(self):
        """S8：合法行新增、重复编码跳过、空行跳过。"""
        client = self._setup()
        _login(client)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "物料导入模板"
        ws.append(["物料编码", "物料名称", "品牌", "规格", "单价"])
        ws.append(["IM001", "导入轴承", "SKF", "6204", 12.5])
        ws.append(["IM002", "导入螺母", "", "M8", 0.5])
        ws.append(["", "", "", "", ""])  # 空行，应跳过
        ws.append(["IM001", "重复轴承", "", "", 1])  # 重复编码，应跳过
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = client.post(
            "/material/import",
            data={"file": (buf, "materials.xlsx")},
            content_type="multipart/form-data",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "共导入 2 条" in data["msg"], data
        with app_module.app.app_context():
            assert Material.query.filter_by(code="IM001").first() is not None
            assert Material.query.filter_by(code="IM002").first() is not None

    def test_delete_all_materials(self):
        """delete_all_materials：线上禁用批量删除，返回 403。"""
        client = self._setup()
        _login(client)
        resp = client.post("/material/delete_all")
        assert resp.status_code == 403
        assert resp.get_json()["status"] == "error"

    def test_fix_empty_fields(self):
        """fix_empty_fields：修复空分类/单位/供应商字段。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        resp = client.post("/material/fix_empty_fields")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "已修复" in data["msg"], data

    def test_copy_material(self):
        """copy_material：生成复制草稿，返回建议编码。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        with app_module.app.app_context():
            mid = Material.query.filter_by(code="M001").first().id
        resp = client.post(f"/material/{mid}/copy")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["material"]["suggested_code"], data
        assert data["material"]["source_id"] == mid

    def test_material_image_select(self):
        """material_image_select：未提供图片 URL 时返回 400（不触发网络请求）。"""
        client = self._setup()
        _login(client)
        _add_material(client, code="M001", name="轴承")
        with app_module.app.app_context():
            mid = Material.query.filter_by(code="M001").first().id
        resp = client.post(f"/material/{mid}/image_select", json={})
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"