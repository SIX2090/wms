# -*- coding: utf-8 -*-
"""ARCH-OS-DOC-01 回归：期初库存多单据化（新增/编辑/删除/回冲/改日期）。

用户诉求（原话）：「期初库存单据，我要做几张怎么新增，因为有很多仓库很多
物料很多仓管人员，导入的期初库存单据怎么修改日期」。

改造前 opening_stock 是一张平铺台账，唯一约束钉死在 (material_id, warehouse_id)
上——同物料同仓只能有一行，想分几张单根本做不到。改造后引入单据头
opening_stock_doc，唯一约束收窄为 (material_id, warehouse_id, doc_id)，
同一张单内不重复、跨单据可重复；库存按 (物料, 仓库) 汇总所有单据的明细行。

本文件锁定改造后的行为契约，重点是**账务正确性**——多单据化最容易出的错
不是建单失败，而是：
  · 明细行 doc_id 丢失（建出来不归属任何单据，首/上/下/末 永远找不到它）；
  · 差额算法被改坏（同一物料多行导致库存重复累加或漏算）；
  · 删行/删单不回冲（库存虚高，账实不符）。

覆盖：
  T1  同物料同仓可建多张单，库存为各单据之和
  T2  同一张单内 (物料,仓库) 重复被拒绝
  T3  明细行必须归属单据（doc_id 不为空）——防止"孤儿明细行"回归
  T4  编辑单据数量按差额入账，不重复累加
  T5  单据头日期覆盖明细行日期（"改日期"整单生效）
  T6  删行自动回冲库存
  T7  删单物理删除并全额回冲
  T8  改日期接口同步明细行且不动账
  T9  单据不存在返回 404
  T10 明细缺仓库被拒绝（R6：重构不得放松校验）
  T11 单号形如 QS+YYMM+4 位且全局唯一
  T12 兼容路径 batch_save 不传 doc_id 时仍能建单（旧前端/旧脚本不炸）
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
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import app as flask_app  # noqa: E402
from app import (  # noqa: E402
    Material,
    OpeningStock,
    OpeningStockDoc,
    StockTransaction,
    Unit,
    User,
    Warehouse,
    db,
)

flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


class TestOpeningStockMultiDoc:
    """期初库存多单据 CRUD 与账务差额。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        self._wipe()

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()

        self.wh1 = Warehouse(code="W1", name="一号仓", status="active")
        self.wh2 = Warehouse(code="W2", name="二号仓", status="active")
        db.session.add_all([self.wh1, self.wh2])
        db.session.flush()

        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0)
        self.m2 = Material(code="M002", name="螺母", unit_id=unit.id, stock=0)
        db.session.add_all([self.m1, self.m2])
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        self._wipe()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _wipe(self):
        for model in (OpeningStock, OpeningStockDoc, StockTransaction,
                      Material, Warehouse, Unit, User):
            db.session.query(model).delete()
        db.session.commit()

    def _login(self):
        """建管理员并登录（与项目既有测试同款做法）。"""
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
            db.session.commit()
        self.client.post("/login",
                         data={"username": "admin", "password": "admin"},
                         content_type="application/x-www-form-urlencoded")

    # ---- 工具 ----

    def _save(self, payload):
        resp = self.client.post("/opening_stock/save", json=payload)
        try:
            return resp.status_code, resp.get_json()
        except Exception:  # pragma: no cover - 兜底便于定位 500
            return resp.status_code, {"raw": resp.data[:300].decode("utf-8", "replace")}

    def _stock(self, material):
        db.session.expire_all()
        return db.session.get(Material, material.id).stock

    def _line(self, doc_id, material, warehouse):
        return OpeningStock.query.filter_by(
            doc_id=doc_id, material_id=material.id, warehouse_id=warehouse.id
        ).first()

    # ---- T1 多单据 + 汇总 ----

    def test_t1_same_material_warehouse_multiple_docs(self):
        st1, b1 = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        st2, b2 = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-10",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 50, "price": 6}],
        })
        assert st1 == 200 and st2 == 200, (b1, b2)
        assert b1["doc_id"] != b2["doc_id"]
        # 改造前这里会撞 uix_opening_stock_material_warehouse 唯一约束
        assert self._stock(self.m1) == 150.0
        assert OpeningStockDoc.query.count() == 2

    # ---- T2 单内去重 ----

    def test_t2_duplicate_material_warehouse_in_one_doc_rejected(self):
        st, body = self._save({
            "date": "2026-09-01",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 10, "price": 1},
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 20, "price": 1},
            ],
        })
        assert st == 400, body
        assert "重复" in body["msg"]
        assert OpeningStockDoc.query.count() == 0

    # ---- T3 明细行必须归属单据（本次改造踩过的真实 bug）----

    def test_t3_lines_always_carry_doc_id(self):
        """_apply_opening_stock_balance 曾用返回值赋 doc_id，新建时静默丢失。"""
        st, body = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 10, "price": 1},
                {"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                 "quantity": 20, "price": 1},
            ],
        })
        assert st == 200, body
        doc = db.session.get(OpeningStockDoc, body["doc_id"])
        assert len(doc.lines) == 2
        assert all(line.doc_id == doc.id for line in doc.lines)
        assert OpeningStock.query.filter(OpeningStock.doc_id.is_(None)).count() == 0

    # ---- T4 差额入账 ----

    def test_t4_edit_quantity_uses_delta(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        doc_id = b["doc_id"]
        # 同数量保存：不重复累加
        st, body = self._save({
            "doc_id": doc_id, "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        assert st == 200 and body["changed_count"] == 0, body
        assert self._stock(self.m1) == 100.0
        # 改数量：按差额
        st, body = self._save({
            "doc_id": doc_id, "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 130, "price": 5}],
        })
        assert st == 200 and body["changed_count"] == 1, body
        assert self._stock(self.m1) == 130.0

    # ---- T5 单头日期覆盖明细 ----

    def test_t5_header_date_overrides_line_dates(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 10, "price": 1, "date": "2020-01-01"},
                {"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                 "quantity": 20, "price": 1},
            ],
        })
        doc = db.session.get(OpeningStockDoc, b["doc_id"])
        assert {line.date for line in doc.lines} == {date(2026, 9, 1)}

    # ---- T6 删行回冲 ----

    def test_t6_removed_line_reverses_stock(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 100, "price": 5},
                {"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                 "quantity": 20, "price": 3},
            ],
        })
        doc_id = b["doc_id"]
        assert self._stock(self.m2) == 20.0
        st, body = self._save({
            "doc_id": doc_id, "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        assert st == 200 and body["removed_count"] == 1, body
        assert self._stock(self.m2) == 0.0
        assert self._stock(self.m1) == 100.0
        assert self._line(doc_id, self.m2, self.wh2) is None

    # ---- T7 删单物理删除 + 全额回冲 ----

    def test_t7_delete_doc_reverses_and_removes(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                 "quantity": 80, "price": 1},
                {"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                 "quantity": 30, "price": 1},
            ],
        })
        doc_id = b["doc_id"]
        assert self._stock(self.m1) == 80.0 and self._stock(self.m2) == 30.0

        resp = self.client.post(f"/opening_stock/{doc_id}/delete")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "success" and body["reversed_count"] == 2

        assert self._stock(self.m1) == 0.0
        assert self._stock(self.m2) == 0.0
        assert db.session.get(OpeningStockDoc, doc_id) is None
        assert OpeningStock.query.filter_by(doc_id=doc_id).count() == 0

    # ---- T8 改日期接口 ----

    def test_t8_date_endpoint_syncs_lines_without_touching_stock(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 60, "price": 2}],
        })
        doc_id = b["doc_id"]
        resp = self.client.post(f"/opening_stock/{doc_id}/date",
                                json={"date": "2026-07-01"})
        assert resp.status_code == 200, resp.data[:300]
        assert resp.get_json()["line_count"] == 1

        db.session.expire_all()
        doc = db.session.get(OpeningStockDoc, doc_id)
        assert doc.date == date(2026, 7, 1)
        assert all(line.date == date(2026, 7, 1) for line in doc.lines)
        # 改期不动账
        assert self._stock(self.m1) == 60.0

    def test_t8b_date_endpoint_rejects_empty_date(self):
        _, b = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 5, "price": 1}],
        })
        resp = self.client.post(f"/opening_stock/{b['doc_id']}/date",
                                json={"date": ""})
        assert resp.status_code == 400

    # ---- T9 404 ----

    def test_t9_missing_doc_returns_404(self):
        assert self.client.get("/opening_stock/99999").status_code == 404
        assert self.client.post("/opening_stock/99999/delete").status_code == 404
        assert self.client.post("/opening_stock/99999/date",
                                json={"date": "2026-01-01"}).status_code == 404

    def test_t9b_save_into_missing_doc_returns_404(self):
        """指定了不存在的 doc_id：明细合法时必须明确报 404 而不是静默新建。

        注意顺序：save 先归一化明细再查单头，所以明细本身不合法时先返回 400
        （校验前置是对的，避免为一条明显非法的请求去查库）。这里给一条合法
        明细，专门验证"单据不存在"这条错误路径。
        """
        st, body = self._save({
            "doc_id": 99999, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 5, "price": 1}],
        })
        assert st == 404, body
        assert "不存在" in body["msg"]
        assert OpeningStockDoc.query.count() == 0

    # ---- T10 校验不得放松（R6）----

    def test_t10_line_without_warehouse_rejected(self):
        st, body = self._save({
            "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "quantity": 5, "price": 1}],
        })
        # A8 规则要求写路由用 pydantic 校验，缺字段在入参层就被拦下并给出中文提示
        assert st == 400, body
        assert "仓库" in body["msg"], body

    def test_t10b_missing_material_rejected(self):
        st, body = self._save({
            "date": "2026-09-01",
            "items": [{"material_id": 99999, "warehouse_id": self.wh1.id,
                       "quantity": 5, "price": 1}],
        })
        assert st == 400 and "物料" in body["msg"], body

    def test_t10c_inactive_warehouse_rejected(self):
        self.wh2.status = "inactive"
        db.session.commit()
        st, body = self._save({
            "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh2.id,
                       "quantity": 5, "price": 1}],
        })
        assert st == 400 and "停用" in body["msg"], body

    def test_t10d_negative_quantity_rejected(self):
        """数量/单价的非负约束由 pydantic 与业务校验双重把关。"""
        st, body = self._save({
            "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": -5, "price": 1}],
        })
        assert st == 400 and "数量" in body["msg"], body

    def test_t10e_non_numeric_quantity_rejected(self):
        st, body = self._save({
            "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": "abc", "price": 1}],
        })
        assert st == 400 and "数量" in body["msg"], body

    def test_t10f_items_must_be_list(self):
        st, body = self._save({"date": "2026-09-01", "items": "xxx"})
        assert st == 400, body

    # ---- T11 单号格式与唯一性 ----

    def test_t11_doc_no_format_and_uniqueness(self):
        numbers = []
        for idx in range(3):
            st, b = self._save({
                "warehouse_id": self.wh1.id, "date": f"2026-09-0{idx + 1}",
                "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                           "quantity": 1, "price": 1}],
            })
            assert st == 200, b
            numbers.append(b["doc_no"])
        assert len(set(numbers)) == 3, numbers
        assert all(re.fullmatch(r"QS\d{8}", no) for no in numbers), numbers

    # ---- T12 兼容路径 ----

    def test_t12_batch_save_without_doc_id_still_creates_doc(self):
        """旧前端/旧脚本不带 doc_id：必须仍能落库并归入兼容单据。"""
        resp = self.client.post("/opening_stock/batch_save", json={
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 25, "price": 4, "date": "2026-09-05"}],
        })
        assert resp.status_code == 200, resp.data[:300]
        assert self._stock(self.m1) == 25.0
        assert OpeningStock.query.filter(OpeningStock.doc_id.is_(None)).count() == 0

    # ---- T13 Excel 导入归单 ----

    def _xlsx(self, rows):
        import io

        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["仓库编码", "物料编码", "物料名称", "数量", "单价", "备注", "日期"])
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    def _import(self, rows):
        resp = self.client.post("/opening_stock/import", data={
            "file": (self._xlsx(rows), "opening.xlsx"),
        }, content_type="multipart/form-data")
        assert resp.status_code == 200, resp.data[:300]
        return resp.get_json()

    def test_t13_import_batch_becomes_one_document(self):
        """整批导入归入一张单据，并回传 doc_id/doc_no/详情链接。"""
        body = self._import([
            ["W1", "M001", "螺丝", 100, 5, "首批", "2026-08-20"],
            ["W2", "M002", "螺母", 20, 3, "", ""],
        ])
        assert body["imported"] == 2 and body["skipped"] == 0, body
        assert body["doc_no"] and body["doc_no"].startswith("QS"), body
        assert body["detail_url"] == f"/opening_stock/{body['doc_id']}"
        assert body["errors"] == []

        doc = db.session.get(OpeningStockDoc, body["doc_id"])
        assert doc is not None and len(doc.lines) == 2
        assert all(line.doc_id == doc.id for line in doc.lines)
        assert self._stock(self.m1) == 100.0
        assert self._stock(self.m2) == 20.0

    def test_t13b_second_import_creates_new_doc_not_edits_old(self):
        """重复导入叠加而不是覆盖：跨单据允许同物料同仓（用户要多张单）。"""
        first = self._import([["W1", "M001", "螺丝", 100, 5, "", ""]])
        second = self._import([["W1", "M001", "螺丝", 30, 5, "", ""]])
        assert first["doc_id"] != second["doc_id"]
        assert OpeningStockDoc.query.count() == 2
        assert self._stock(self.m1) == 130.0

    def test_t13c_import_scoped_to_its_own_document(self):
        """导入只在本批单据内匹配行，不会误改上一批单据的明细。"""
        first = self._import([["W1", "M001", "螺丝", 100, 5, "", ""]])
        self._import([["W1", "M001", "螺丝", 30, 5, "", ""]])
        db.session.expire_all()
        doc = db.session.get(OpeningStockDoc, first["doc_id"])
        assert len(doc.lines) == 1
        assert doc.lines[0].quantity == 100.0  # 未被第二批改动

    def test_t13d_all_bad_rows_leave_no_empty_document(self):
        before = OpeningStockDoc.query.count()
        body = self._import([["W9", "M999", "不存在", 5, 1, "", ""]])
        assert body["imported"] == 0 and body["skipped"] == 1, body
        assert body["doc_id"] is None and body["doc_no"] is None
        assert OpeningStockDoc.query.count() == before
        assert body["errors"][0].startswith("第 2 行"), body

    def test_t13e_imported_doc_date_is_editable(self):
        """用户核心诉求：导入进来的单据要能改日期。"""
        body = self._import([["W1", "M001", "螺丝", 60, 2, "", ""]])
        resp = self.client.post(f"/opening_stock/{body['doc_id']}/date",
                                json={"date": "2026-01-15"})
        assert resp.status_code == 200, resp.data[:300]
        db.session.expire_all()
        doc = db.session.get(OpeningStockDoc, body["doc_id"])
        assert doc.date == date(2026, 1, 15)
        assert all(line.date == date(2026, 1, 15) for line in doc.lines)
        assert self._stock(self.m1) == 60.0  # 改期不动账


class TestOpeningStockFrontendWiring:
    """ARCH-OS-DOC-01 前端接线：模板/JS 必须与后端单据模型一致。

    这些是静态断言（不需要起服务），锁定三条最容易断的接线：
    - 详情页必须把单据上下文注入给 JS，否则前端不知道在编辑哪张单；
    - 保存必须走 /opening_stock/save 并带 doc_id，否则永远新建；
    - JS 模块表必须注册 opening_stock，否则导航组不会渲染。
    """

    TEMPLATE = ROOT / "app" / "templates" / "opening_stock.html"
    APP_JS = ROOT / "app" / "static" / "js" / "app.js"

    def test_template_injects_document_context(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        assert "window.__OPENING_DOC__" in html
        assert "const OPENING_DOC = window.__OPENING_DOC__ || null;" in html

    def test_template_has_real_navigation_buttons(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        for target in ("first", "prev", "next", "last"):
            assert f"navigateOpeningDoc('{target}')" in html, target
        assert "function navigateOpeningDoc(" in html
        assert "/api/document_navigation/opening_stock" in html

    def test_template_saves_through_document_endpoint(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        assert "WMS.api.post('/opening_stock/save'" in html
        assert "if (OPENING_DOC) payload.doc_id = OPENING_DOC.id;" in html
        # 不应再直接打 batch_save（那会永远新建兼容单，编辑失效）
        assert "WMS.api.post('/opening_stock/batch_save'" not in html

    def test_template_has_delete_current_doc(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        assert "function deleteCurrentDoc()" in html
        assert "/delete" in html

    def test_app_js_registers_opening_stock_module(self):
        js = self.APP_JS.read_text(encoding="utf-8")
        assert "opening_stock: {" in js
        assert "tableId: 'openingGrid'" in js
        assert "'/opening_stock/{id}'" in js

    def test_app_js_recognises_opening_stock_document_paths(self):
        js = self.APP_JS.read_text(encoding="utf-8")
        assert r"/^\/opening_stock\/add$/" in js
        assert r"/^\/opening_stock\/\d+$/" in js
        assert "'#openingGrid'" in js


class TestEnsureOpeningStockDocColumns:
    """R6 兜底：ensure_opening_stock_doc_columns 必须给存量库补出 doc_id。

    起因：doc_id 起初只写在 auto_migrate_database() 里，而生产批处理默认
    WMS_NO_DB_TOUCH=1 会把整个迁移跳过。存量库重启后一查 opening_stock.doc_id
    就是 500（no such column）。本用例直接在一个"没有 doc_id 的旧库"上跑
    兜底函数，验证补列成功、数据不丢、可重复执行。
    """

    def test_ensure_opening_stock_doc_columns(self, tmp_path):
        """A9 规范要求的同名测试入口：补齐存量库缺失的 doc_id 列。"""
        import sqlite3

        from app import ensure_opening_stock_doc_columns

        db_file = str(tmp_path / "a9.db")
        conn = sqlite3.connect(db_file)
        conn.execute(
            "CREATE TABLE opening_stock ("
            " id INTEGER PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,"
            " date DATE, quantity FLOAT, price FLOAT, amount FLOAT, remark VARCHAR(500))"
        )
        conn.execute(
            "INSERT INTO opening_stock (material_id, warehouse_id, quantity)"
            " VALUES (7, 2, 33)"
        )
        conn.commit()
        conn.close()

        ensure_opening_stock_doc_columns(db_file)

        conn = sqlite3.connect(db_file)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(opening_stock)")}
        rows = conn.execute("SELECT material_id, quantity FROM opening_stock").fetchall()
        conn.close()
        assert "doc_id" in cols
        assert rows == [(7, 33.0)]

    def test_ensure_opening_stock_doc_columns_adds_doc_id(self, tmp_path):
        import sqlite3

        from app import ensure_opening_stock_doc_columns

        db_file = str(tmp_path / "legacy.db")
        conn = sqlite3.connect(db_file)
        conn.execute(
            "CREATE TABLE opening_stock ("
            " id INTEGER PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,"
            " date DATE, quantity FLOAT, price FLOAT, amount FLOAT, remark VARCHAR(500))"
        )
        conn.execute(
            "INSERT INTO opening_stock (material_id, warehouse_id, quantity)"
            " VALUES (1, 1, 10)"
        )
        conn.commit()
        cols_before = {r[1] for r in conn.execute("PRAGMA table_info(opening_stock)")}
        conn.close()
        assert "doc_id" not in cols_before

        ensure_opening_stock_doc_columns(db_file)

        conn = sqlite3.connect(db_file)
        cols_after = {r[1] for r in conn.execute("PRAGMA table_info(opening_stock)")}
        rows = conn.execute("SELECT material_id, quantity FROM opening_stock").fetchall()
        conn.close()
        assert "doc_id" in cols_after
        assert rows == [(1, 10.0)], "补列不得丢数据"

    def test_ensure_opening_stock_doc_columns_is_idempotent(self, tmp_path):
        import sqlite3

        from app import ensure_opening_stock_doc_columns

        db_file = str(tmp_path / "legacy2.db")
        conn = sqlite3.connect(db_file)
        conn.execute(
            "CREATE TABLE opening_stock ("
            " id INTEGER PRIMARY KEY, material_id INTEGER, quantity FLOAT)"
        )
        conn.commit()
        conn.close()

        ensure_opening_stock_doc_columns(db_file)
        ensure_opening_stock_doc_columns(db_file)  # 再跑一次不应抛错

        conn = sqlite3.connect(db_file)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(opening_stock)")]
        conn.close()
        assert cols.count("doc_id") == 1, "幂等：doc_id 不应重复添加"

    def test_ensure_opening_stock_doc_columns_skips_missing_db(self, tmp_path):
        """全新部署（库文件还没建）应静默跳过，交给 create_all。"""
        from app import ensure_opening_stock_doc_columns
        ensure_opening_stock_doc_columns(str(tmp_path / "not-created-yet.db"))
