# -*- coding: utf-8 -*-
"""P1-1 回归：入库单下推时来源单仓库必填。

背景（源码核实，非照抄计划文档）：
  P1-1 计划里点名的 4 处「仓库必填缺口」实测大多已被更早的批次修完
  （委外发料/收料、期初、调拨——前端 required + 默认选中 + 后端必填/active 校验全都在）。
  唯一真缺口：in_order_push（入库单下推）的目标草稿直接继承 order.warehouse，
  来源单无仓库时会写出**空仓库草稿**——出库/售后出库单完成时仓库必填，
  这种草稿永远无法完成，只能删掉重建（死单）。

修复：
  1. 后端 create_in_order_push：来源单无仓库 → 400 拒绝，不允许静默写空仓库；
  2. 前端 in_order_push.html：无仓库时顶部警示 + 禁用「创建目标草稿」按钮。

验收点：
  T1. 来源单无仓库 → POST /in_order/<id>/push 返回 400，msg 含「仓库」；
  T2. 来源单有仓库 → 下推成功（控制组，证明不是这条校验误拦）；
  T3. 无仓库时下推页渲染警示且按钮 disabled；
  T4. 有仓库时下推页无警示且按钮可用。
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
from app import InOrder, InOrderItem, Material, Unit, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_NO_WAREHOUSE_MSG = "来源入库单未指定仓库"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    from app import User
    unit = Unit(code="U1", name="个")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    mat = Material(code="M001", name="测试物料", spec="S1", unit=unit, stock=100, price=10)
    db.session.add_all([unit, wh, user, mat])
    db.session.commit()
    return mat


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _make_completed_in_order(mat, warehouse, order_no):
    order = InOrder(
        order_no=order_no, business_type="采购入库",
        status="completed", warehouse=warehouse, total_amount=100,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=mat.id,
        quantity=10, price=10, amount=100,
    ))
    db.session.commit()
    return order


def _setup(warehouse):
    """造一个有/无仓库的已完成入库单，返回 (client, order_id, item_id)。"""
    with app_module.app.app_context():
        _reset_db()
        mat = _seed()
        order = _make_completed_in_order(mat, warehouse, "IN-P1-1-001")
        order_id = order.id
        item_id = InOrderItem.query.filter_by(in_order_id=order.id).first().id
    client = app_module.app.test_client()
    _login(client)
    return client, order_id, item_id


def _push_payload(item_id, suffix):
    return {
        "target_type": "other_out",
        "request_id": "req-p1-1-%s" % suffix,
        "purpose": "测试下推",
        "items": [{"source_item_id": item_id, "quantity": 5}],
    }


class TestInOrderPushWarehouseRequired:
    def test_T1_push_rejected_when_source_has_no_warehouse(self):
        client, order_id, item_id = _setup(warehouse="")
        resp = client.post(f"/in_order/{order_id}/push", json=_push_payload(item_id, "t1"))
        assert resp.status_code == 400, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data["status"] == "error", data
        assert "仓库" in (data.get("msg") or ""), data

    def test_T2_push_succeeds_when_source_has_warehouse(self):
        """控制组：有仓库的来源单必须能下推，证明 T1 不是被误拦。"""
        client, order_id, item_id = _setup(warehouse="仓库A")
        resp = client.post(f"/in_order/{order_id}/push", json=_push_payload(item_id, "t2"))
        data = resp.get_json()
        assert data["status"] == "success", data

    def test_T3_push_page_warns_and_disables_when_no_warehouse(self):
        client, order_id, _ = _setup(warehouse="")
        html = client.get(f"/in_order/{order_id}/push?target=other_out").get_data(as_text=True)
        assert 'id="noWarehouseWarning"' in html, "无仓库时下推页必须渲染警示条"
        assert _NO_WAREHOUSE_MSG in html, "警示文案必须说明原因"
        import re
        btn = re.search(r'<button[^>]*id="createDraft"[^>]*>', html)
        assert btn, "找不到创建目标草稿按钮"
        assert "disabled" in btn.group(0), "无仓库时创建按钮必须禁用"

    def test_T4_push_page_normal_when_has_warehouse(self):
        client, order_id, _ = _setup(warehouse="仓库A")
        html = client.get(f"/in_order/{order_id}/push?target=other_out").get_data(as_text=True)
        assert 'id="noWarehouseWarning"' not in html, "有仓库时不应渲染警示条"
        import re
        btn = re.search(r'<button[^>]*id="createDraft"[^>]*>', html)
        assert btn, "找不到创建目标草稿按钮"
        assert "disabled" not in btn.group(0), "有仓库时创建按钮必须可用"
