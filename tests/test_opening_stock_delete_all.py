# -*- coding: utf-8 -*-
"""BUG-2026-09-15-008 回归：一键删除全部期初库存（物理删除 + 库存回冲）。

用户诉求（原话）：「我要删除已导入的全部期初但删除不了」。根因是台账页
没有任何删除"已建账/已导入"记录的入口——工具栏「删除」只清空未保存的
录入行（clearEntryRows），已建账记录必须钻进对应单据页点"删除本单"才能
逐张删，批量导入的数据想清空重来根本无从下手。

本次新增 `POST /opening_stock/delete_all`：
  - 物理删除全部 OpeningStock 明细行 + 全部 OpeningStockDoc 单据头；
  - 逐行 `_reverse_opening_stock_line` 回冲库存（含 doc_id 为 NULL 的历史直连行）；
  - 与"删除本单"同规则：回冲后库存变负照常删除，仅在消息里中文提示；
  - pydantic `confirm: bool` 服务端二次确认（A8 输入校验）。

前端工具栏新增「删除全部」按钮（双确认 + WMS.api，禁原生 fetch），并把
易混淆的「删除」改名「清空录入」。

覆盖：
  T1 全删：库存全额回冲归零，明细行与单据头清空
  T2 confirm 缺失 / 非 true → 400，数据不动
  T3 无记录时调用返回成功（幂等，不报错）
  T4 doc_id 为 NULL 的历史直连行也被删除并回冲
  T5 未登录访问被拦截（302 跳登录，不删除）
  T6 删除了就没有流水（BUG-2026-09-16-007）：全删后 opening 流水清零、
     不新增负向回冲流水
  T7 前端静态断言：删除全部按钮 + deleteAllOpeningStock + 端点齐全
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

# BUG-2026-09-15-009 起，「删除全部」按钮与 deleteAllOpeningStock 移到单据列表页
# opening_stock_list.html（opening_stock.html 已变为纯单据编辑页，不再放全量删除入口）。
TEMPLATE = APP_DIR / "templates" / "opening_stock_list.html"


class TestOpeningStockDeleteAll:
    """一键删除全部期初库存的后端账务与权限契约。"""

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
        return resp.status_code, resp.get_json()

    def _stock(self, material):
        db.session.expire_all()
        return db.session.get(Material, material.id).stock

    def _delete_all(self, payload):
        resp = self.client.post("/opening_stock/delete_all", json=payload)
        try:
            return resp.status_code, resp.get_json()
        except Exception:  # pragma: no cover - 兜底便于定位 500
            return resp.status_code, {"raw": resp.data[:300].decode("utf-8", "replace")}

    def _seed_two_docs(self):
        """建两张单：m1@wh1=100、m2@wh2=50，制造非零库存。"""
        st1, b1 = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        st2, b2 = self._save({
            "warehouse_id": self.wh2.id, "date": "2026-09-01",
            "items": [{"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                       "quantity": 50, "price": 2}],
        })
        assert st1 == 200 and st2 == 200, (b1, b2)
        return b1["doc_id"], b2["doc_id"]

    # ---- T1 全删 + 全额回冲 ----

    def test_t1_delete_all_reverses_stock_and_clears(self):
        self._seed_two_docs()
        assert self._stock(self.m1) == 100.0
        assert self._stock(self.m2) == 50.0
        assert OpeningStock.query.count() == 2
        assert OpeningStockDoc.query.count() == 2

        st, body = self._delete_all({"confirm": True})
        assert st == 200, body
        assert body["status"] == "success"
        assert body["reversed_count"] == 2
        assert body["deleted_docs"] == 2

        # 库存全额回冲归零
        assert self._stock(self.m1) == 0.0
        assert self._stock(self.m2) == 0.0
        # 明细行与单据头都清空
        assert OpeningStock.query.count() == 0
        assert OpeningStockDoc.query.count() == 0

    # ---- T2 confirm 必填（A8 服务端二次确认）----

    def test_t2_confirm_required(self):
        self._seed_two_docs()
        # 缺 confirm
        st, body = self._delete_all({})
        assert st == 400, body
        # confirm 非 true
        st, body = self._delete_all({"confirm": False})
        assert st == 400, body
        # 数据未被删除
        assert OpeningStock.query.count() == 2
        assert OpeningStockDoc.query.count() == 2
        assert self._stock(self.m1) == 100.0

    # ---- T3 空记录幂等 ----

    def test_t3_empty_is_success(self):
        st, body = self._delete_all({"confirm": True})
        assert st == 200, body
        assert body["status"] == "success"
        assert body["reversed_count"] == 0
        assert OpeningStock.query.count() == 0

    # ---- T4 历史直连行（doc_id 为 NULL）也被删并回冲 ----

    def test_t4_orphan_lines_removed_and_reversed(self):
        # 直接造一条 doc_id 为 NULL 的历史台账行，并把库存加上去
        orphan = OpeningStock(
            doc_id=None, material_id=self.m1.id, warehouse_id=self.wh1.id,
            quantity=30, price=1, amount=30, remark="历史直连",
        )
        db.session.add(orphan)
        m1 = db.session.get(Material, self.m1.id)
        m1.stock = 30.0
        db.session.commit()
        assert OpeningStock.query.filter(OpeningStock.doc_id.is_(None)).count() == 1
        assert self._stock(self.m1) == 30.0

        st, body = self._delete_all({"confirm": True})
        assert st == 200, body
        assert OpeningStock.query.count() == 0
        assert self._stock(self.m1) == 0.0

    # ---- T5 未登录被拦截 ----

    def test_t5_unauthenticated_cannot_delete(self):
        self._seed_two_docs()
        anon = flask_app.test_client()
        # 测试夹具的会话共享：本类 setup 已登录 self.client，而手动 push 的常驻
        # app_context 会把登录态泄漏给后续 test_client（生产真实 HTTP 无此问题，
        # 干净上下文实测匿名即 302）。先显式 logout 确保匿名，再断言安全契约。
        anon.get("/logout")
        resp = anon.post("/opening_stock/delete_all", json={"confirm": True})
        # 安全契约：未登录绝不能删除任何数据（拦截形式 302 跳登录或 401/403 均可）。
        assert resp.status_code in (302, 401, 403)
        assert OpeningStock.query.count() == 2
        assert OpeningStockDoc.query.count() == 2
        assert self._stock(self.m1) == 100.0
        # 响应绝不能是成功的删除
        try:
            body = resp.get_json() or {}
        except Exception:
            body = {}
        assert body.get("status") != "success"

    # ---- T6 删除了就没有流水（BUG-2026-09-16-007）----

    def test_t6_delete_all_removes_transactions_no_reversal_rows(self):
        self._seed_two_docs()
        # 建账时每行各写一条 +N 流水
        assert StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening").count() == 2
        neg_before = StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0,
        ).count()

        st, body = self._delete_all({"confirm": True})
        assert st == 200, body

        # 全删后流水物理清零，且不再新增任何负向回冲流水
        assert StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening").count() == 0
        neg_after = StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0,
        ).count()
        assert neg_after == neg_before


class TestOpeningStockDeleteAllFrontend:
    """前端静态断言：按钮/函数/端点接线齐全（防回归为死按钮）。"""

    def test_t7_toolbar_button_and_handler_wired(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        assert "删除全部" in html, "工具栏应有「删除全部」按钮"
        assert "function deleteAllOpeningStock()" in html, "应定义 deleteAllOpeningStock()"
        assert 'onclick="deleteAllOpeningStock()"' in html, "按钮应绑定 deleteAllOpeningStock()"
        assert "/opening_stock/delete_all" in html, "应调用全量删除端点"
        assert "WMS.api.post" in html, "全量删除应走 WMS.api（禁原生 fetch）"
