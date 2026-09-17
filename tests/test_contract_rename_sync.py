# -*- coding: utf-8 -*-
"""合同/工程档案改名同步历史单据回归测试（BUG-2026-09-17-001）。

用户原话：「更改工程名称之前单据上的工程名称没有同步更改」。
修复：编辑/批量导入改名（改号）时，sync_contract_project_name() 同步全部
冗余存储合同编号/工程名称的单据头与明细行（9 张表，两种引用方式）。

覆盖：
T1（A9 同名）：直接调用 sync_contract_project_name——9 张表全部命中
   （contract_id 外键引用 + contract_no 纯字符串引用两种方式），他合同隔离。
T2：编辑路由改名 → 历史单据（含已完成状态）头/行同步，成功消息带同步条数。
T3：编辑路由改号 → 单据 contract_no 与 project_name 同步跟随。
T4：批量导入改名 → 历史单据同步，导入消息带同步条数。
T5：无变更编辑（名字未改）→ 不触碰任何历史行。
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

OLD_NAME = "广州汇侨"
NEW_NAME = "淮安第三园区纯废水七期、八期安装工程"


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client, username="admin", password="admin"):
    return client.post(
        "/login",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from app import User
    db.session.add(User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_all_document_rows(contract, other_contract):
    """在 9 张冗余表各造一行：HD1 引用目标合同（外键/字符串两种）、HD2 对照组。

    返回 {表名: 行对象}，键即 model.__tablename__。
    """
    from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, InOrder,
                     InOrderItem, Material, OutOrder, OutOrderItem,
                     PurchaseOrder, PurchaseOrderItem, SalesOrder,
                     SalesOrderItem, Customer)

    m = Material(code="M001", name="控制箱", stock=0)
    c = Customer(code="C001", name="测试客户")
    db.session.add_all([m, c])
    db.session.commit()

    rows = {}

    in_o = InOrder(order_no="IN-T1", warehouse="项目仓", status="completed",
                   contract_no="HD1", project_name=OLD_NAME)
    out_o = OutOrder(order_no="OUT-T1", warehouse="项目仓", status="completed",
                     contract_no="HD1", project_name=OLD_NAME)
    po = PurchaseOrder(order_no="PO-T1", contract_no="HD1", project_name=OLD_NAME)
    so = SalesOrder(order_no="SO-T1", customer_id=c.id, warehouse="项目仓",
                    contract_no="HD1", project_name=OLD_NAME)
    aso = AfterSaleOutOrder(order_no="AS-T1", warehouse="项目仓")
    # 对照组：另一合同 HD2 的单据不得被波及
    in_o2 = InOrder(order_no="IN-T2", warehouse="项目仓", status="completed",
                    contract_no="HD2", project_name="别的工程")
    db.session.add_all([in_o, out_o, po, so, aso, in_o2])
    db.session.commit()
    rows[InOrder.__tablename__] = in_o
    rows[OutOrder.__tablename__] = out_o
    rows[PurchaseOrder.__tablename__] = po
    rows[SalesOrder.__tablename__] = so

    # 明细行：InOrderItem 走 contract_id 外键引用；OutOrderItem 走纯字符串引用
    rows[InOrderItem.__tablename__] = InOrderItem(
        in_order_id=in_o.id, material_id=m.id, quantity=4, price=1, amount=4,
        contract_id=contract.id, contract_no="HD1", project_name=OLD_NAME)
    rows[OutOrderItem.__tablename__] = OutOrderItem(
        out_order_id=out_o.id, material_id=m.id, quantity=1, price=1, amount=1,
        contract_no="HD1", project_name=OLD_NAME)
    rows[AfterSaleOutOrderItem.__tablename__] = AfterSaleOutOrderItem(
        after_sale_out_order_id=aso.id, material_id=m.id, quantity=1, price=1,
        amount=1, contract_no="HD1", project_name=OLD_NAME)
    rows[PurchaseOrderItem.__tablename__] = PurchaseOrderItem(
        purchase_order_id=po.id, material_id=m.id, quantity=1,
        contract_no="HD1", project_name=OLD_NAME)
    rows[SalesOrderItem.__tablename__] = SalesOrderItem(
        sales_order_id=so.id, material_id=m.id, quantity=1,
        contract_no="HD1", project_name=OLD_NAME)
    item_rows = [rows[InOrderItem.__tablename__], rows[OutOrderItem.__tablename__],
                 rows[AfterSaleOutOrderItem.__tablename__],
                 rows[PurchaseOrderItem.__tablename__],
                 rows[SalesOrderItem.__tablename__]]
    db.session.add_all(item_rows)
    db.session.commit()
    # 跨请求断言必须按 (模型, 主键) 重新查询——请求结束后旧会话对象已 detach
    rows[InOrder.__tablename__] = in_o
    rows[OutOrder.__tablename__] = out_o
    rows[PurchaseOrder.__tablename__] = po
    rows[SalesOrder.__tablename__] = so
    keys = {table: (type(row), row.id) for table, row in rows.items()}
    keys["_other"] = (type(in_o2), in_o2.id)
    return keys


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    return app_module.app.test_client()


@pytest.fixture()
def contracts(client):
    from app import Contract
    with app_module.app.app_context():
        hd1 = Contract(contract_no="HD1", project_name=OLD_NAME, status="active")
        hd2 = Contract(contract_no="HD2", project_name="别的工程", status="active")
        db.session.add_all([hd1, hd2])
        db.session.commit()
        return hd1.id, hd2.id


class TestSyncContractProjectNameHelper:
    def test_sync_contract_project_name(self, contracts):
        """T1（A9）：9 张冗余表全部同步；外键与纯字符串两种引用都命中；他合同隔离。"""
        from app import Contract, sync_contract_project_name
        hd1_id, hd2_id = contracts
        with app_module.app.app_context():
            hd1 = db.session.get(Contract, hd1_id)
            hd2 = db.session.get(Contract, hd2_id)
            rows = _seed_all_document_rows(hd1, hd2)

            counts = sync_contract_project_name(hd1.id, "HD1", "HD1", NEW_NAME)
            db.session.commit()

            # 9 张表每表 1 行被同步
            assert len(counts) == 9, f"9 张表都应命中，实际 {counts}"
            assert all(v == 1 for v in counts.values())
            for table, (model, pk) in rows.items():
                if table.startswith("_"):
                    continue
                obj = db.session.get(model, pk)
                assert obj.project_name == NEW_NAME, f"{table} 未同步"

            other_model, other_pk = rows["_other"]
            assert db.session.get(other_model, other_pk).project_name == "别的工程", \
                "对照组 HD2 单据被误改"

            # 无匹配时返回空、不报错
            assert sync_contract_project_name(None, "HD999", "HD999", "X") == {}


class TestContractEditRouteSync:
    def test_edit_rename_syncs_documents(self, client, contracts):
        """T2：编辑改名 → 历史单据（含 completed）同步；消息含同步条数。"""
        from app import Contract
        hd1_id, _ = contracts
        with app_module.app.app_context():
            hd1 = db.session.get(Contract, hd1_id)
            rows = _seed_all_document_rows(hd1, None)
        _login(client)
        r = client.post(f"/contract/{hd1_id}/edit", data={
            "contract_no": "HD1",
            "project_name": NEW_NAME,
            "status": "active",
            "remark": "",
        })
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success"
        assert "同步更新" in body["msg"], f"成功消息应含同步条数，实际：{body['msg']}"
        with app_module.app.app_context():
            for table, (model, pk) in rows.items():
                if table.startswith("_"):
                    continue
                obj = db.session.get(model, pk)
                assert obj.project_name == NEW_NAME, f"{table} 未同步"

    def test_edit_renumber_syncs_no_and_name(self, client, contracts):
        """T3：改号 → 单据 contract_no 与 project_name 一起跟随。"""
        from app import Contract, InOrder
        hd1_id, _ = contracts
        with app_module.app.app_context():
            hd1 = db.session.get(Contract, hd1_id)
            _seed_all_document_rows(hd1, None)
        _login(client)
        r = client.post(f"/contract/{hd1_id}/edit", data={
            "contract_no": "HD260904",
            "project_name": NEW_NAME,
            "status": "active",
            "remark": "",
        })
        assert r.status_code == 200, r.get_data(as_text=True)
        with app_module.app.app_context():
            doc = InOrder.query.filter_by(order_no="IN-T1").first()
            assert doc.contract_no == "HD260904"
            assert doc.project_name == NEW_NAME

    def test_edit_no_change_does_not_touch(self, client, contracts):
        """T5：名字未改的保存不触发同步（消息不含同步条数，行保持原值）。"""
        from app import Contract, InOrder
        hd1_id, _ = contracts
        with app_module.app.app_context():
            hd1 = db.session.get(Contract, hd1_id)
            _seed_all_document_rows(hd1, None)
        _login(client)
        r = client.post(f"/contract/{hd1_id}/edit", data={
            "contract_no": "HD1",
            "project_name": OLD_NAME,
            "status": "active",
            "remark": "只改备注",
        })
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert "同步更新" not in body["msg"]
        with app_module.app.app_context():
            doc = InOrder.query.filter_by(order_no="IN-T1").first()
            assert doc.project_name == OLD_NAME


class TestContractImportSync:
    def _make_xlsx(self, rows):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["合同编号", "工程名称", "状态", "备注"])
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def test_import_rename_syncs_documents(self, client, contracts):
        """T4：批量导入更新工程名 → 历史单据同步，导入消息含同步条数。"""
        from app import Contract, InOrder
        hd1_id, _ = contracts
        with app_module.app.app_context():
            hd1 = db.session.get(Contract, hd1_id)
            _seed_all_document_rows(hd1, None)
        _login(client)
        buf = self._make_xlsx([["HD1", NEW_NAME, "启用", ""]])
        r = client.post(
            "/contract/import",
            data={"file": (buf, "contracts.xlsx")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success"
        assert "更新 1 条" in body["msg"]
        assert "同步更新" in body["msg"], f"导入消息应含同步条数，实际：{body['msg']}"
        with app_module.app.app_context():
            doc = InOrder.query.filter_by(order_no="IN-T1").first()
            assert doc.project_name == NEW_NAME
