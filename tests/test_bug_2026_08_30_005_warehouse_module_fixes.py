# -*- coding: utf-8 -*-
"""
BUG-2026-08-30-005 回归测试：仓库管理模块审计修复

修复内容：
  W1 盘点单「系统库存」改仓库级口径（check.py save_check_table / add_check_item），
     多仓库下不再把 A+B 合计当系统库存，避免盘盈盘亏算错。
  W2 编辑仓库名称时同步所有单据表冗余的 warehouse 文本字段
     （InOrder/OutOrder/PurchaseOrder/SubcontractOrder/ProductionRequisition/
      AfterSaleOutOrder/SalesOrder + TransferOrder 的 from/to），
     存编号的行不受影响。
  W4 仓库新增/编辑校验 status 值域（仅 active/inactive）。

断言：
  T1. 盘点保存：多仓库下 system_stock 默认 = 该仓库库存（100），非全局合计（150）
  T2. 盘点添加明细：add_check_item 系统库存 = 仓库级
  T3. 改仓库名：各单据表旧名称行同步为新名称，存编号的行保持不动
  T4. 仓库新增非法 status 被拒绝
"""
from __future__ import annotations

import os
import re
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
from app import (AfterSaleOutOrder, InOrder, InventoryCheck,  # noqa: E402
                 InventoryCheckItem, Material, OutOrder, ProductionRequisition,
                 SubcontractOrder, TransferOrder, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={"username": "admin", "password": "admin",
                                "csrf_token": token})
    return client


class TestBug20260830005:
    def setup_method(self):
        with app_module.app.test_request_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            whA = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            whB = Warehouse(code="WHB", name="仓库B", status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([whA, whB, unit, user])
            db.session.flush()
            mat = Material(code="M001", name="电缆", unit_id=unit.id,
                           price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            # 仓库A 100，仓库B 50（全局合计 150）
            app_module.add_stock(mat, 100, transaction_type='opening', warehouse=whA)
            app_module.add_stock(mat, 50, transaction_type='opening', warehouse=whB)
            # 各类单据：仓库A 存「名称」、仓库B 存「编号」（模拟手机端）
            io_name = InOrder(order_no="IN-NAME", date=date.today(), warehouse="仓库A",
                              status="completed", operator_id=user.id)
            io_code = InOrder(order_no="IN-CODE", date=date.today(), warehouse="WHA",
                              status="completed", operator_id=user.id)
            oo_name = OutOrder(order_no="OUT-NAME", date=date.today(), warehouse="仓库A",
                               status="completed", operator_id=user.id)
            sc = SubcontractOrder(order_no="SC-NAME", date=date.today(), warehouse="仓库A",
                                  status="completed", operator_id=user.id)
            req = ProductionRequisition(req_no="REQ-NAME", date=date.today(),
                                        warehouse="仓库A", status="completed",
                                        operator_id=user.id)
            after = AfterSaleOutOrder(order_no="AS-NAME", date=date.today(),
                                      warehouse="仓库A", status="completed",
                                      operator_id=user.id)
            tr = TransferOrder(transfer_no="TR-NAME", date=date.today(),
                               from_warehouse="仓库A", to_warehouse="仓库B",
                               from_location="仓库A", to_location="仓库B",
                               status="completed", operator_id=user.id)
            db.session.add_all([io_name, io_code, oo_name, sc, req, after, tr])
            db.session.commit()
            self.whA_id, self.whB_id, self.mat_id = whA.id, whB.id, mat.id
            self.client = _make_client()

    def _save_check(self, warehouse_name, system_stock=None):
        items = [{'code': 'M001', 'name': '电缆'}]
        if system_stock is not None:
            items[0]['system_stock'] = system_stock
        return self.client.post(
            '/check/save_table',
            json={'header': {'warehouse': warehouse_name}, 'items': items},
        )

    def test_T1_check_save_uses_warehouse_level_stock(self):
        resp = self._save_check('仓库A')
        assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
        check_id = resp.get_json()['id']
        with app_module.app.app_context():
            check = InventoryCheck.query.get(check_id)
            item = check.items[0]
            assert item.system_stock == 100, \
                f"盘点系统库存应为仓库A的 100，实际 {item.system_stock}（全局合计 150）"

    def test_T2_check_add_item_uses_warehouse_level_stock(self):
        resp = self._save_check('仓库A')
        check_id = resp.get_json()['id']
        # 先删掉明细，再走 add_item 接口
        with app_module.app.app_context():
            check = InventoryCheck.query.get(check_id)
            for it in list(check.items):
                db.session.delete(it)
            db.session.commit()
        resp2 = self.client.post(f'/check/{check_id}/add_item',
                                 data={'material_id': self.mat_id})
        assert resp2.status_code == 200, resp2.get_data(as_text=True)[:200]
        with app_module.app.app_context():
            item = InventoryCheckItem.query.filter_by(inventory_check_id=check_id).first()
            assert item.system_stock == 100, \
                f"add_item 系统库存应为仓库级 100，实际 {item.system_stock}"

    def test_T3_rename_warehouse_syncs_all_documents(self):
        resp = self.client.post(
            f'/warehouse/{self.whA_id}/edit',
            data={'code': 'WHA', 'name': '仓库A新', 'type': '', 'location': '',
                  'status': 'active', 'remark': ''},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
        with app_module.app.app_context():
            # 存旧名称的行应同步为新名称
            assert InOrder.query.filter_by(order_no="IN-NAME").first().warehouse == "仓库A新"
            assert OutOrder.query.filter_by(order_no="OUT-NAME").first().warehouse == "仓库A新"
            assert SubcontractOrder.query.filter_by(order_no="SC-NAME").first().warehouse == "仓库A新"
            assert ProductionRequisition.query.filter_by(req_no="REQ-NAME").first().warehouse == "仓库A新"
            assert AfterSaleOutOrder.query.filter_by(order_no="AS-NAME").first().warehouse == "仓库A新"
            tr = TransferOrder.query.filter_by(transfer_no="TR-NAME").first()
            assert tr.from_warehouse == "仓库A新", "调拨 from_warehouse 未同步"
            assert tr.to_warehouse == "仓库B", "to_warehouse 不应被误改"
            # 存编号的行不应被改动
            assert InOrder.query.filter_by(order_no="IN-CODE").first().warehouse == "WHA"

    def test_T4_add_warehouse_rejects_invalid_status(self):
        resp = self.client.post('/warehouse/add',
                                data={'code': 'WHX', 'name': '仓库X',
                                      'status': 'hacked', 'type': '', 'location': '',
                                      'remark': ''})
        assert resp.status_code == 400, "非法 status 应被拒绝"
