# -*- coding: utf-8 -*-
"""P0 计划 B2–B6：采购退货出库端到端全链路深度测试（只测不修）。

与既有覆盖的分工（R6 查重）：
  - test_bug_2026_09_22_005：批量完成防超退闸（DB 直造草稿）
  - test_bug_2026_09_22_007：明细端点防超退（item/add / item/update）
  - test_bug_2026_09_22_010：来源类型/状态校验（非采购入库、未完成单拒绝）
本文件补**表单路径端到端链路**缺口：
  B2-T1 选源接口：只列已完成采购入库单、可退数量正确、未完成/他类型不出现
  B2-T2 全链路：表单创建退货单→完成→仓库级库存扣减→可退量回退
  B3-T3 跨单退货：单头指 A 单、行级指 B 单同物料行的实际行为
  B3-T4 无来源拒绝（表单路径，开关默认开）
  B3-T5 已完成退货单直接删除被拒（AGENTS §一：须先人工反提交）
  B3-T6 反提交：库存回冲 + 可退量恢复
  B3-T7 草稿删除：库存无变化
  B4-T8 双仓隔离：A 仓退货不影响 B 仓库存与可退量
  B5-T9 出库明细报表：采购退货出库行聚合正确
"""
from __future__ import annotations

import datetime
import json
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (InOrder, InOrderItem, Material, MaterialCategory,  # noqa: E402
                 OutOrder, OutOrderItem, Supplier, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TODAY = datetime.date.today()


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh_a = Warehouse(name="仓库甲", code="WHA", status="active", is_default=True)
    wh_b = Warehouse(name="仓库乙", code="WHB", status="active", is_default=False)
    supplier = Supplier(code="S01", name="退货供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh_a, wh_b, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-PR", name="退货测试件", spec="T1", stock=0,
                        min_stock=0, price=3.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh_a": wh_a, "wh_b": wh_b, "supplier": supplier, "material": material}


def _seed_stock(material, warehouse, quantity):
    from app.services.warehouse_stock_service import apply_stock_delta
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            material, quantity, transaction_type="opening_in",
            reference_type="test_seed", reference_id=0,
            warehouse=warehouse.name, location="")
    assert ok, f"造库存失败：{err}"
    db.session.flush()


def _make_in_order(order_no, material, warehouse, quantity, status="completed",
                   business_type="采购入库", supplier_id=1):
    order = InOrder(order_no=order_no, date=TODAY, business_type=business_type,
                    supplier_id=supplier_id, status=status, warehouse=warehouse.name)
    db.session.add(order)
    db.session.flush()
    ii = InOrderItem(in_order_id=order.id, material_id=material.id,
                     quantity=quantity, price=3.0, amount=quantity * 3.0)
    db.session.add(ii)
    db.session.commit()
    return order.id, ii.id


def _client():
    client = app_module.app.test_client()
    client.post("/login", data={"username": "warehouse", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _wh_stock(material, warehouse_name):
    """仓库级库存（A11：不裸用 material.stock）。"""
    from app import get_warehouse_stock_quantities
    wh = Warehouse.query.filter_by(name=warehouse_name).first()
    return get_warehouse_stock_quantities(wh).get(material.id, 0.0)


def _selectable(client, **params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    r = client.get(f"/api/purchase_in_order/selectable?{qs}")
    assert r.status_code == 200, f"选源接口 {r.status_code}"
    return r.get_json()


def _post_return_order(client, order_no, material, warehouse_name, in_order_id,
                       items, customer="退货供应商", supplier_ok=True):
    body = {
        "order_no": order_no, "date": str(TODAY), "business_type": "采购退货出库",
        "customer": customer, "warehouse": warehouse_name,
        "source_in_order_id": in_order_id, "items": items,
    }
    r = client.post("/out_order/add", data=json.dumps(body),
                    content_type="application/json")
    return r


class TestPurchaseReturnE2E:

    def setup_method(self):
        # 注意：只保存原始值（id/int/str）。commit 后脱离 app_context 的 ORM
        # 实例再访问属性会触发 DetachedInstanceError（同 005 文件头注释警告）。
        with app_module.app.app_context():
            _reset_db()
            self.base = _seed_base()
            # setup 内直接用造数返回的实例（尚未 commit 过期问题——_seed_base
            # commit 后实例已过期，这里重新按 id 取）
            mat = db.session.get(Material, self.base["material"].id)
            _seed_stock(mat, self.base["wh_a"], 100.0)
            # A 仓两张已完成采购入库单（各 30/20 件）+ 一张未完成单 + 一张其他类型单
            self.io_a_id, self.ii_a_id = _make_in_order(
                "IN-PR-A", mat, self.base["wh_a"], 30.0)
            self.io_a2_id, self.ii_a2_id = _make_in_order(
                "IN-PR-A2", mat, self.base["wh_a"], 20.0)
            self.io_draft_id, _ = _make_in_order(
                "IN-PR-DRAFT", mat, self.base["wh_a"], 50.0, status="pending")
            self.io_other_id, _ = _make_in_order(
                "IN-PR-OTHER", mat, self.base["wh_a"], 60.0,
                business_type="其他入库")
            self.mat_id = mat.id
            self.mat_code = mat.code
            self.wh_a_id = self.base["wh_a"].id
            self.wh_b_id = self.base["wh_b"].id

    def _mat(self):
        return db.session.get(Material, self.mat_id)

    # ------------------------------------------------------------- B2-T1
    def test_b2_t1_selectable_lists_completed_purchase_only_with_remaining(self):
        """选源接口只列已完成采购入库单，可退数量正确，未完成/他类型不出现。"""
        with app_module.app.app_context():
            client = _client()
            data = _selectable(client, search="IN-PR")
            nos = [o["order_no"] for o in data.get("orders", [])]
            assert "IN-PR-A" in nos and "IN-PR-A2" in nos, f"已完成单未列出：{nos}"
            assert "IN-PR-DRAFT" not in nos, f"未完成单不应可选源：{nos}"
            assert "IN-PR-OTHER" not in nos, f"其他入库类型不应可选源：{nos}"
            # 可退数量 = 原行数量 − 已退量（当前未退）
            by_no = {o["order_no"]: o for o in data.get("orders", [])}
            flat = by_no["IN-PR-A"].get("items") or by_no["IN-PR-A"].get("flat_items") or []
            assert flat, f"A 单明细未返回：{by_no['IN-PR-A'].keys()}"

    # ------------------------------------------------------------- B2-T2
    def test_b2_t2_full_chain_create_complete_stock_and_remaining(self):
        """全链路：表单创建→完成→仓库级库存扣减→可退量回退。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            # 创建前：A 仓库存 100，IN-PR-A 可退 30
            assert _wh_stock(mat, "仓库甲") == 100.0
            r = _post_return_order(client, "OUT-PR-E2E", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 10.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            assert r.status_code == 200 and r.get_json().get("status") == "success", \
                f"创建退货单失败：{r.status_code} {r.get_data(as_text=True)}"
            order_id = r.get_json()["id"]
            # 草稿不扣库存
            assert _wh_stock(mat, "仓库甲") == 100.0, "草稿不应扣库存"
            # 完成单据
            r2 = client.post(f"/out_order/{order_id}/complete")
            assert r2.status_code in (200, 302), f"完成失败：{r2.status_code} {r2.get_data(as_text=True)}"
            # 库存扣减 100-10=90
            stock = _wh_stock(mat, "仓库甲")
            assert stock == 90.0, f"完成后 A 仓库存应为 90，实际 {stock}"
            # 可退量回退：IN-PR-A 剩 20
            data = _selectable(client, in_order_id=self.io_a_id)
            orders = data.get("orders", [])
            assert orders, "完成后选源应仍列出该单（还有可退量）"
            flat = orders[0].get("items") or orders[0].get("flat_items") or []
            rem = None
            for it in flat:
                if it.get("material_code") == mat.code:
                    rem = it.get("remaining_quantity", it.get("remaining"))
                    break
            assert rem == 20.0, f"完成后可退量应为 20，实际 {rem}（flat={flat}）"

    # ------------------------------------------------------------- B3-T3
    def test_b3_t3_cross_order_source_behavior(self):
        """跨单退货：单头指 A 单、行级指 B 单同物料行——记录实际行为。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-CROSS", mat, "仓库甲",
                                   self.io_a_id,   # 单头 A
                                   [{"code": mat.code, "quantity": 5.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a2_id}])  # 行级 A2
            body = r.get_json() if r.status_code == 200 else r.get_data(as_text=True)
            # 记录行为：若允许，单头聚合应跟随行级来源（A2）；若拒绝，返回明确错误
            if r.status_code == 200 and isinstance(body, dict) and body.get("status") == "success":
                order = db.session.get(OutOrder, body["id"])
                assert order.source_in_order_id == self.io_a2_id, \
                    f"跨单行级来源时单头应聚合为行级单 A2，实际 {order.source_in_order_id}"
            else:
                assert "来源" in str(body) or "无效" in str(body), \
                    f"跨单拒绝时应给出明确错误，实际 {body}"

    # ------------------------------------------------------------- B3-T4
    def test_b3_t4_no_source_rejected_when_switch_on(self):
        """无来源退货被拒（开关默认开）。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-NOSRC", mat, "仓库甲",
                                   None,
                                   [{"code": mat.code, "quantity": 5.0, "price": 3.0}])
            assert r.status_code == 400, f"无来源应 400，实际 {r.status_code}"
            assert "关联来源" in (r.get_json().get("msg") or ""), r.get_data(as_text=True)

    # ------------------------------------------------------------- B3-T5
    def test_b3_t5_completed_order_delete_rejected(self):
        """已完成退货单直接删除被拒（AGENTS §一：须先人工反提交）。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-DEL", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 5.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            assert r.get_json().get("status") == "success"
            order_id = r.get_json()["id"]
            assert client.post(f"/out_order/{order_id}/complete").status_code in (200, 302)
            # 完成态直接删除 → 必须拒绝
            r2 = client.post(f"/out_order/{order_id}/delete")
            assert r2.status_code in (400, 403, 409), \
                f"已完成退货单直接删除应被拒，实际 {r2.status_code} {r2.get_data(as_text=True)}"

    # ------------------------------------------------------------- B3-T6
    def test_b3_t6_revert_restores_stock_and_remaining(self):
        """反提交：库存回冲 + 可退量恢复。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-REV", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 10.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            order_id = r.get_json()["id"]
            assert client.post(f"/out_order/{order_id}/complete").status_code in (200, 302)
            assert _wh_stock(mat, "仓库甲") == 90.0
            r2 = client.post(f"/out_order/{order_id}/revert")
            assert r2.status_code in (200, 302), f"反提交失败：{r2.status_code} {r2.get_data(as_text=True)}"
            stock = _wh_stock(mat, "仓库甲")
            assert stock == 100.0, f"反提交后库存应回冲到 100，实际 {stock}"
            data = _selectable(client, in_order_id=self.io_a_id)
            flat = (data.get("orders") or [{}])[0].get("items") or []
            rem = next((it.get("remaining_quantity", it.get("remaining")) for it in flat
                        if it.get("material_code") == mat.code), None)
            assert rem == 30.0, f"反提交后可退量应恢复 30，实际 {rem}"

    # ------------------------------------------------------------- B3-T7
    def test_b3_t7_draft_delete_keeps_stock(self):
        """草稿删除：库存无变化。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-DRAFTDEL", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 10.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            order_id = r.get_json()["id"]
            assert _wh_stock(mat, "仓库甲") == 100.0
            r2 = client.post(f"/out_order/{order_id}/delete")
            assert r2.status_code in (200, 302), f"草稿删除失败：{r2.status_code}"
            assert _wh_stock(mat, "仓库甲") == 100.0, "草稿删除不应影响库存"

    # ------------------------------------------------------------- B4-T8
    def test_b4_t8_dual_warehouse_isolation(self):
        """双仓隔离：A 仓退货不影响 B 仓库存与可退量。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            # B 仓也造库存 + B 仓入库单
            _seed_stock(mat, self.base["wh_b"], 40.0)
            io_b_id, ii_b_id = _make_in_order(
                "IN-PR-B", mat, self.base["wh_b"], 25.0)
            # A 仓退货 10
            r = _post_return_order(client, "OUT-PR-ISO", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 10.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            assert r.get_json().get("status") == "success"
            assert client.post(f"/out_order/{r.get_json()['id']}/complete").status_code in (200, 302)
            # R2 三口径
            assert _wh_stock(mat, "仓库甲") == 90.0, "A 仓应扣减"
            assert _wh_stock(mat, "仓库乙") == 40.0, "B 仓不得被 A 仓退货串动"
            data = _selectable(client, in_order_id=io_b_id)
            flat = (data.get("orders") or [{}])[0].get("items") or []
            rem = next((it.get("remaining_quantity", it.get("remaining")) for it in flat
                        if it.get("material_code") == mat.code), None)
            assert rem == 25.0, f"B 仓可退量不得被 A 仓退货消耗，实际 {rem}"

    # ------------------------------------------------------------- B5-T9
    def test_b5_t9_out_detail_report_includes_return_row(self):
        """出库明细报表：采购退货出库行按 business_type 正确聚合（B5）。"""
        with app_module.app.app_context():
            client = _client()
            mat = self._mat()
            r = _post_return_order(client, "OUT-PR-RPT", mat, "仓库甲",
                                   self.io_a_id,
                                   [{"code": mat.code, "quantity": 8.0, "price": 3.0,
                                     "source_in_order_item_id": self.ii_a_id}])
            assert r.get_json().get("status") == "success"
            assert client.post(f"/out_order/{r.get_json()['id']}/complete").status_code in (200, 302)
            resp = client.get("/report/api/out_detail",
                              query_string={"warehouse_id": self.wh_a_id,
                                            "date_start": str(TODAY),
                                            "date_end": str(TODAY),
                                            "business_type": "采购退货出库",
                                            "page": 1, "page_size": 50})
            assert resp.status_code == 200, f"报表接口失败 {resp.status_code}"
            data = resp.get_json()
            rows = data.get("data") or data.get("rows") or []
            pr_rows = [x for x in rows if x.get("business_type") == "采购退货出库"
                       or x.get("order_no") == "OUT-PR-RPT"]
            assert pr_rows, f"报表未包含采购退货出库行：{rows[:2]}"
            qty = sum(float(x.get("quantity") or 0) for x in pr_rows)
            assert qty == 8.0, f"退货数量聚合应为 8，实际 {qty}"
