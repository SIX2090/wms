# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：标签模板 + 条码 + 二维码（label + barcode + qrcode）域路由
迁移到 routes/label_barcode.py。

采用 register-on-app 模式（register_label_barcode_routes(app)），endpoint 名保持不变
（label_template_list / add_label_template / label_template_detail / delete_label_template /
save_label_template_layout / preview_label_template / print_labels / set_default_template /
api_label_template_list / api_label_template_detail / generate_barcode / api_barcode_image /
api_qrcode_image），URL 路径不变，因此模板/导航中的 url_for(...) 引用无需改动。

验收点：
S1. 13 个 endpoint 已注册，仍是无前缀的原始 endpoint 名，不存在 label_barcode.xxx 重复。
S2. URL 路径保持不变。
S3. routes/label_barcode.py 可导入，register_label_barcode_routes 存在。
S4. 标签模板新增/列表 API/详情 API/设默认/保存布局/删除 工作正常。
S5. 条码与二维码图片生成返回 PNG；/barcode/generate 缺 code 返回 400。
S6. 标签模板列表页可渲染。
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

LABEL_BARCODE_ENDPOINTS = [
    "label_template_list",
    "add_label_template",
    "label_template_detail",
    "delete_label_template",
    "save_label_template_layout",
    "preview_label_template",
    "print_labels",
    "set_default_template",
    "api_label_template_list",
    "api_label_template_detail",
    "generate_barcode",
    "api_barcode_image",
    "api_qrcode_image",
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


class TestLabelBarcodeRegister:
    def _setup(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        return _make_client()

    def test_module_importable(self):
        """S3：routes/label_barcode.py 可导入，register 函数存在。"""
        from routes.label_barcode import register_label_barcode_routes
        assert callable(register_label_barcode_routes)

    def test_endpoints_and_urls(self):
        """S1/S2：13 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in LABEL_BARCODE_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in LABEL_BARCODE_ENDPOINTS:
                assert f"label_barcode.{ep}" not in app_module.app.view_functions, \
                    f"label_barcode.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("label_template_list") == "/label_template"
                assert url_for("add_label_template") == "/label_template/add"
                assert url_for("label_template_detail", id=1) == "/label_template/1"
                assert url_for("delete_label_template", id=1) == "/label_template/1/delete"
                assert url_for("save_label_template_layout", id=1) == "/label_template/1/save_layout"
                assert url_for("preview_label_template", id=1) == "/label_template/1/preview"
                assert url_for("print_labels", id=1) == "/label_template/1/print"
                assert url_for("set_default_template", id=1) == "/label_template/1/set_default"
                assert url_for("api_label_template_list") == "/label_template/api/list"
                assert url_for("api_label_template_detail", id=1) == "/label_template/api/1/detail"
                assert url_for("generate_barcode") == "/barcode/generate"
                assert url_for("api_barcode_image", code="ABC") == "/api/barcode/ABC"
                assert url_for("api_qrcode_image", data="xyz") == "/api/qrcode/xyz"

    def test_label_template_page(self):
        """S6：标签模板列表页可渲染。"""
        client = self._setup()
        _login(client)
        resp = client.get("/label_template")
        assert resp.status_code == 200
        assert "标签模板" in resp.get_data(as_text=True)

    def test_label_template_crud(self):
        """S4：新增/列表 API/详情 API/设默认/保存布局/删除。"""
        client = self._setup()
        _login(client)
        # 新增
        r = client.post("/label_template/add", data={
            "name": "标准模板", "width": "100", "height": "60",
            "cols": "4", "rows": "5", "is_default": "on",
        })
        assert r.get_json()["status"] == "success", r.get_json()
        # 重复名称拒绝
        r_dup = client.post("/label_template/add", data={"name": "标准模板"})
        assert r_dup.status_code == 409, r_dup.status_code
        # 列表 API
        lst = client.get("/label_template/api/list")
        assert lst.get_json()["status"] == "success"
        assert len(lst.get_json()["templates"]) == 1
        tid = lst.get_json()["templates"][0]["id"]
        # 详情 API
        det = client.get(f"/label_template/api/{tid}/detail")
        assert det.get_json()["status"] == "success"
        assert det.get_json()["template"]["name"] == "标准模板"
        # 保存布局
        lay = client.post(
            f"/label_template/{tid}/save_layout",
            headers={"Content-Type": "application/json"},
            data='{"layout": [{"type": "text", "x": 1, "y": 1}]}',
        )
        assert lay.get_json()["status"] == "success", lay.get_json()
        # 设默认
        sd = client.post(f"/label_template/{tid}/set_default")
        assert sd.get_json()["status"] == "success", sd.get_json()
        # 删除
        dl = client.post(f"/label_template/{tid}/delete")
        assert dl.get_json()["status"] == "success", dl.get_json()
        with app_module.app.app_context():
            from app import LabelTemplate
            assert LabelTemplate.query.get(tid) is None

    def test_barcode_qrcode(self):
        """S5：条码/二维码 PNG 生成；/barcode/generate 缺 code 返回 400。"""
        client = self._setup()
        _login(client)
        # /barcode/generate 缺 code
        r = client.get("/barcode/generate")
        assert r.status_code == 400
        assert r.get_json()["status"] == "error"
        # 条码图片
        rb = client.get("/api/barcode/6204")
        assert rb.status_code == 200
        assert rb.data[:8] == b"\x89PNG\r\n\x1a\n"
        # 二维码图片
        rq = client.get("/api/qrcode/hello")
        assert rq.status_code == 200
        assert rq.data[:8] == b"\x89PNG\r\n\x1a\n"