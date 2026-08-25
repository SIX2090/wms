# -*- coding: utf-8 -*-
"""移动端出库合同编号（选填）回归测试（2026-08-24 用户需求）。

需求：
- App 扫码出库/手工出库增加选填「合同编号」字段，支持快速匹配
  （输入片段如 0709 即可匹配 HD260709）；
- 命中合同档案时回填 contract_id/project_name，未命中保留用户输入文本；
- 合同编号为选填，缺省不影响出库提交。

覆盖：
- GET /api/mobile/contracts：片段模糊匹配 contract_no / project_name、
  仅返回启用合同、大小写不敏感、未认证 401；
- POST /api/outbound：contract_no 命中档案（大小写不敏感）回填 contract_id/
  project_name 且明细继承；未命中保留原文本；缺省不填正常出库。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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

TODAY = date.today()


def _seed():
    from app import Contract, Material, Unit, User, Warehouse

    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    wh = Warehouse(code="WH01", name="材料仓", status="active", is_default=True)
    unit = Unit(code="U1", name="个")
    db.session.add_all([wh, unit])
    db.session.flush()
    db.session.add(Material(code="MAT001", name="6204轴承", spec="20*47*14",
                            stock=100, price=1.5, unit=unit))
    db.session.add_all([
        Contract(contract_no="HD260709", project_name="城东配电工程", status="active"),
        Contract(contract_no="HD260800", project_name="城西照明工程", status="active"),
        Contract(contract_no="OLD260101", project_name="已停用工程", status="disabled"),
    ])
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        _seed()
        db.session.remove()
    c = app_module.app.test_client()
    yield c
    with app_module.app.app_context():
        db.session.remove()


def _bearer(c):
    resp = c.post("/api/login", json={"username": "admin", "password": "admin"})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {"Authorization": f"Bearer {resp.get_json()['data']['token']}"}


class TestMobileContractsSearch:
    def test_fragment_matches_contract_no(self, client):
        resp = client.get("/api/mobile/contracts?keyword=0709", headers=_bearer(client))
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        assert [i["contract_no"] for i in items] == ["HD260709"]
        assert items[0]["project_name"] == "城东配电工程"

    def test_fragment_case_insensitive(self, client):
        resp = client.get("/api/mobile/contracts?keyword=hd26", headers=_bearer(client))
        assert resp.status_code == 200
        nos = {i["contract_no"] for i in resp.get_json()["data"]["items"]}
        assert nos == {"HD260709", "HD260800"}

    def test_inactive_contract_excluded(self, client):
        resp = client.get("/api/mobile/contracts?keyword=2601", headers=_bearer(client))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["items"] == []

    def test_keyword_matches_project_name(self, client):
        resp = client.get("/api/mobile/contracts?keyword=照明", headers=_bearer(client))
        assert resp.status_code == 200
        assert [i["contract_no"] for i in resp.get_json()["data"]["items"]] == ["HD260800"]

    def test_requires_auth(self, client):
        resp = client.get("/api/mobile/contracts?keyword=0709")
        assert resp.status_code == 401


class TestMobileOutboundContract:
    def _post_outbound(self, client, headers, **extra):
        payload = {
            "warehouse_code": "WH01",
            "lines": [{"material_code": "MAT001", "quantity": 2}],
        }
        payload.update(extra)
        resp = client.post("/api/outbound", json=payload, headers=headers)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()["data"]["order_no"]

    def test_contract_hit_backfills_archive_fields(self, client):
        headers = _bearer(client)
        # 小写输入也应命中档案并回填规范编号
        order_no = self._post_outbound(client, headers, contract_no="hd260709")
        with app_module.app.app_context():
            from app import Contract, OutOrder
            order = OutOrder.query.filter_by(order_no=order_no).one()
            contract = Contract.query.filter_by(contract_no="HD260709").one()
            assert order.contract_id == contract.id
            assert order.contract_no == "HD260709"
            assert order.project_name == "城东配电工程"
            # 明细级冗余同步
            for item in order.items:
                assert item.contract_id == contract.id
                assert item.contract_no == "HD260709"
                assert item.project_name == "城东配电工程"

    def test_contract_miss_keeps_raw_text(self, client):
        headers = _bearer(client)
        order_no = self._post_outbound(client, headers, contract_no="FOO123")
        with app_module.app.app_context():
            from app import OutOrder
            order = OutOrder.query.filter_by(order_no=order_no).one()
            assert order.contract_id is None
            assert order.contract_no == "FOO123"
            assert order.project_name is None

    def test_contract_optional(self, client):
        headers = _bearer(client)
        order_no = self._post_outbound(client, headers)
        with app_module.app.app_context():
            from app import OutOrder
            order = OutOrder.query.filter_by(order_no=order_no).one()
            assert order.status == "completed"
            assert order.contract_id is None
            assert order.contract_no is None
