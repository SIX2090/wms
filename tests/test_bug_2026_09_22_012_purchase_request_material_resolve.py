# -*- coding: utf-8 -*-
"""BUG-2026-09-22-012 回归测试：采购申请保存时禁止物料静默降级。

问题：
  采购申请保存路径（`add_purchase_request`，新增与编辑共用）在物料解析失败时
  **不报错**，直接把 `material_id` 落成 `None`。而
  `purchase_request_item_data_has_material` 判定「有效行」只看是否填了
  material_id / material_code / material_name 三者之一——于是产生一张
  「有明细但无物料」的申请单：
    - 下推 `create_purchase_order_from_request` 按 `item.material_id and ...`
      过滤，这些行走不到；整单全是这种行时永远返回「采购申请没有可下推的物料明细」；
    - 表头 total_amount 却已把这些行的金额累加进去（金额虚高）；
    - 单据状态是 approved，删除只允许 pending/rejected → 用户看到的是
      「不能下推、不能删除」，须自行想到先「反审」退回 pending 才有出路。
  触发路径真实：新增页的物料编码是**自由文本输入框**（名称/规格只读，靠选择
  回填），用户手打编码边输边提交即可稳定复现。

修复：保存时若用户表达了「该行对应某个物料」（给了 material_id 或 material_code）
      但解析不到，则明确报错（含行号与编码/ID），拒绝落库。

测试用例：
  T1. 传不存在的 material_code → 报错、且单据与明细均未落库
  T2. 传不存在的 material_id → 报错、且单据与明细均未落库
  T3. 存在编码但物料不匹配（大小写/空格）→ 报错（不做模糊匹配，防止误指）
  T4. 合法 material_id → 保存成功、material_id 正确落库（不得误伤正常路径）
  T5. 合法 material_code → 保存成功（按编码解析的既有能力保留）
  T6. 编辑态：原单据明细合法，改成不存在编码 → 报错且**原明细不被清空**
  T7. 仅填 material_name、不填编码与 id → 保持既有兼容行为（允许保存）
  T8. 存量卡死单据可经 revert 退回 pending 后删除（确认既有出路，非新增能力）
  T9. 多行场景：第 2 行编码不存在时报错应指出行号，第 1 行合法也不落库
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, User, Material, MaterialCategory, Unit, PurchaseRequest, PurchaseRequestItem  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_MAT = {}


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    cat = MaterialCategory(code="PRCAT", name="采购分类")
    unit = Unit(code="PCS", name="个")
    db.session.add_all([cat, unit])
    db.session.flush()
    mat = Material(code="PRM1", name="采购物料", category_id=cat.id, unit_id=unit.id,
                   stock=100, price=5)
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([mat, user])
    db.session.commit()
    _MAT["id"] = mat.id
    _MAT["code"] = mat.code


def _client():
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"})
    return client


def _payload(items, request_no="PR-ERR-1"):
    return {
        "request_no": request_no,
        "date": "2026-09-22",
        "applicant": "张三",
        "department": "采购部",
        "urgency": "normal",
        "expected_date": "2026-09-30",
        "reason": "测试",
        "remark": "",
        "items": items,
    }


class TestMaterialResolveRejected:
    """T1/T2/T3：物料解析失败必须报错且不落库。"""

    def _fresh(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        return _client()

    def test_unknown_material_code_rejected(self):
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_code": "NOT-EXIST-001", "quantity": 5, "estimated_price": 10}]))
        body = resp.get_json()
        assert body["status"] == "error", body
        assert "不存在" in body.get("msg", "")
        with app_module.app.app_context():
            assert PurchaseRequest.query.count() == 0
            assert PurchaseRequestItem.query.count() == 0

    def test_unknown_material_id_rejected(self):
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_id": 999999, "material_name": "幽灵物料", "quantity": 5,
              "estimated_price": 10}]))
        body = resp.get_json()
        assert body["status"] == "error", body
        with app_module.app.app_context():
            assert PurchaseRequest.query.count() == 0

    def test_case_mismatch_code_rejected(self):
        """既有实现是 filter_by(code=...) 精确匹配，不做大小写模糊——保持一致并显式报错。"""
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_code": "prm1", "quantity": 5, "estimated_price": 10}]))
        body = resp.get_json()
        assert body["status"] == "error", body
        with app_module.app.app_context():
            assert PurchaseRequest.query.count() == 0


class TestValidMaterialStillAccepted:
    """T4/T5：正常路径不得误伤。"""

    def _fresh(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        return _client()

    def test_valid_material_id_saved(self):
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_id": _MAT["id"], "quantity": 5, "estimated_price": 10}],
            request_no="PR-OK-1"))
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            order = PurchaseRequest.query.filter_by(request_no="PR-OK-1").first()
            assert order is not None
            items = PurchaseRequestItem.query.filter_by(purchase_request_id=order.id).all()
            assert len(items) == 1
            assert items[0].material_id == _MAT["id"]
            assert abs(float(order.total_amount) - 50.0) < 1e-6

    def test_valid_material_code_saved(self):
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_code": _MAT["code"], "quantity": 2, "estimated_price": 5}],
            request_no="PR-OK-2"))
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            order = PurchaseRequest.query.filter_by(request_no="PR-OK-2").first()
            assert order is not None
            items = PurchaseRequestItem.query.filter_by(purchase_request_id=order.id).all()
            assert items[0].material_id == _MAT["id"]


class TestEditAndNameOnly:
    """T6/T7：编辑态不丢原明细；仅名称保持兼容。"""

    def _fresh(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        return _client()

    def test_edit_with_bad_code_keeps_existing_items(self):
        client = self._fresh()
        ok = client.post("/purchase_request/add", json=_payload(
            [{"material_id": _MAT["id"], "quantity": 5, "estimated_price": 10}],
            request_no="PR-EDIT-1"))
        assert ok.get_json()["status"] == "success"
        with app_module.app.app_context():
            order = PurchaseRequest.query.filter_by(request_no="PR-EDIT-1").first()
            order_id = order.id
            before = PurchaseRequestItem.query.filter_by(purchase_request_id=order_id).count()
            assert before == 1

        # 编辑成不存在的编码：save 会先 delete 原明细再重建，报错必须在删除之前拦下，
        # 否则单据被清空却带着错误返回——比原问题更糟。
        bad = client.post("/purchase_request/add", json={
            **_payload([{"material_code": "NOPE-9", "quantity": 3, "estimated_price": 1}]),
            "request_id": order_id,
        })
        assert bad.get_json()["status"] == "error"
        with app_module.app.app_context():
            after = PurchaseRequestItem.query.filter_by(purchase_request_id=order_id).count()
            assert after == before, "报错路径不得清空原明细"

    def test_name_only_row_kept_compatible(self):
        client = self._fresh()
        resp = client.post("/purchase_request/add", json=_payload(
            [{"material_name": "手工填写的名称", "quantity": 1, "estimated_price": 3}],
            request_no="PR-NAME-1"))
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            order = PurchaseRequest.query.filter_by(request_no="PR-NAME-1").first()
            items = PurchaseRequestItem.query.filter_by(purchase_request_id=order.id).all()
            assert len(items) == 1
            assert items[0].material_id is None


class TestMultiRowRowNumber:
    """T9：多行报错指出行号，且整单不落库。"""

    def test_second_row_bad_reports_row_number(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        client = _client()
        resp = client.post("/purchase_request/add", json=_payload(
            [
                {"material_id": _MAT["id"], "quantity": 1, "estimated_price": 5},
                {"material_code": "BAD-ROW-2", "quantity": 1, "estimated_price": 5},
            ],
            request_no="PR-ROW-1",
        ))
        body = resp.get_json()
        assert body["status"] == "error", body
        assert "第 2 行" in body.get("msg", ""), body
        with app_module.app.app_context():
            assert PurchaseRequest.query.count() == 0


class TestStuckDocumentHasExit:
    """T8：确认既有反审出路（不算新增能力，用于锁定现状）。"""

    def test_revert_then_delete(self):
        with app_module.app.app_context():
            _reset_db()
            _seed()
        client = _client()
        client.post("/purchase_request/add", json=_payload(
            [{"material_id": _MAT["id"], "quantity": 5, "estimated_price": 10}],
            request_no="PR-STUCK-1"))
        with app_module.app.app_context():
            order_id = PurchaseRequest.query.filter_by(request_no="PR-STUCK-1").first().id

        assert client.post(f"/purchase_request/{order_id}/approve",
                           json={}).get_json()["status"] == "success"
        # approved 态不能直接删除
        assert client.post(f"/purchase_request/{order_id}/delete",
                           json={}).get_json()["status"] == "error"
        # 反审退回 pending 后可删除
        assert client.post(f"/purchase_request/{order_id}/revert",
                           json={}).get_json()["status"] == "success"
        assert client.post(f"/purchase_request/{order_id}/delete",
                           json={}).get_json()["status"] == "success"
        with app_module.app.app_context():
            assert PurchaseRequest.query.filter_by(request_no="PR-STUCK-1").first() is None
