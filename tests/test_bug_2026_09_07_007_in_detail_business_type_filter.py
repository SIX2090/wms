# -*- coding: utf-8 -*-
"""BUG-2026-09-07-007 回归：入库明细报表前端补「业务类型」筛选控件。

背景：后端自 BUG-2026-08-18-004 起支持 business_type 筛选
（采购入库/产品入库/其他入库），但 report_view.html 一直没有对应控件，
前端无法按入库类型过滤（只能手改 URL）。

断言：
  T1. 模板锚点：in_detail 条件下渲染 business_type 下拉与三个选项。
  T2. 渲染 /report/view/in_detail 页面 HTML 含该控件。
  T3. 渲染 /report/view/out_detail 页面 HTML 不含该控件（仅入库明细显示）。
  T4. 端到端：API 按 business_type=产品入库 只返回产品入库行。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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
from app import InOrder, InOrderItem, Material, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


class TestBug20260907007:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh, unit, user])
            db.session.flush()
            mat = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.wh_id = wh.id
            for btype in ("采购入库", "产品入库", "其他入库"):
                order = InOrder(order_no=f"IN-{btype}", date=date.today(),
                                warehouse="仓库A", status="completed",
                                operator_id=user.id, business_type=btype)
                db.session.add(order)
                db.session.flush()
                db.session.add(InOrderItem(in_order_id=order.id, material_id=mat.id,
                                           quantity=1, price=10.0, amount=10.0))
            db.session.commit()

    def _login_client(self):
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        return client

    def test_T1_template_anchor(self):
        tpl = (ROOT / "app" / "templates" / "report_view.html").read_text(encoding="utf-8")
        assert "report_type == 'in_detail'" in tpl, "控件必须限定仅入库明细渲染"
        assert 'name="business_type"' in tpl, "缺业务类型下拉"
        for option in ("采购入库", "产品入库", "其他入库"):
            assert f'value="{option}"' in tpl, f"缺选项 {option}"

    def test_T2_in_detail_page_has_control(self):
        client = self._login_client()
        r = client.get("/report/view/in_detail")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'name="business_type"' in html, "入库明细页必须渲染业务类型控件"

    def test_T3_out_detail_page_has_no_control(self):
        client = self._login_client()
        r = client.get("/report/view/out_detail")
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'name="business_type"' not in html, "出库明细页不得渲染业务类型控件"

    def test_T4_api_end_to_end_filter(self):
        client = self._login_client()
        r = client.get(f"/report/api/in_detail?warehouse_id={self.wh_id}&business_type=产品入库")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 1, f"按产品入库筛选应只命中 1 行，实际 {data['total']}"
        assert data['data'][0]['business_type'] == '产品入库'
        assert data['data'][0]['order_no'] == 'IN-产品入库'
