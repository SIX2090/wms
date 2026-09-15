# -*- coding: utf-8 -*-
"""BUG-2026-09-15-009 回归：期初库存重构为「单据列表 + 单据编辑分离」。

用户诉求（原话）：「重新写期初库存模块，我要的是一个单据而不是乱七八糟的东西」，
并选定形态「单据列表+单据编辑分离」——列表页只列单据（单据号/日期/仓库/明细行数/
合计金额/备注），点开某张才进单据编辑；去掉同页堆叠的「台账查询 + 录入网格」。

改造：
  - GET /opening_stock        → 渲染 opening_stock_list.html（单据列表）；
  - GET /opening_stock/<id>   → opening_stock.html（纯单据编辑，无台账面板）；
  - GET /opening_stock/add    → opening_stock.html（新建空白单据，不预填台账记录）。

覆盖：
  T1 列表页只列单据（含单据号/打开链接/明细行数/合计金额列）
  T2 单据编辑页不再出现"查询已建账期初库存"台账面板
  T3 新建页也不再有台账面板（纯单据录入）
  T4 仓库筛选只列出涉及该仓的单据
  T5 关键字按单据号搜索
  T6 列表正确显示明细行数与合计金额
  T7 前端静态断言：列表页按钮/函数/端点/列齐全
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

LIST_TEMPLATE = APP_DIR / "templates" / "opening_stock_list.html"
EDITOR_TEMPLATE = APP_DIR / "templates" / "opening_stock.html"


class TestOpeningStockDocList:
    """单据列表 + 编辑分离的页面行为契约。"""

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

    def _save(self, payload):
        resp = self.client.post("/opening_stock/save", json=payload)
        return resp.status_code, resp.get_json()

    def _doc_no(self, doc_id):
        return db.session.get(OpeningStockDoc, doc_id).doc_no

    def _seed_two_docs(self):
        """wh1 一张（m1 100×5=500），wh2 一张（m2 50×2=100）。"""
        st1, b1 = self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5}],
        })
        st2, b2 = self._save({
            "warehouse_id": self.wh2.id, "date": "2026-09-02",
            "items": [{"material_id": self.m2.id, "warehouse_id": self.wh2.id,
                       "quantity": 50, "price": 2}],
        })
        assert st1 == 200 and st2 == 200, (b1, b2)
        return b1["doc_id"], b2["doc_id"]

    # ---- T1 列表页只列单据 ----

    def test_t1_list_page_renders_documents(self):
        d1, d2 = self._seed_two_docs()
        no1, no2 = self._doc_no(d1), self._doc_no(d2)
        resp = self.client.get("/opening_stock")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "期初" in html
        assert no1 in html and no2 in html, "列表应显示单据号"
        assert f"/opening_stock/{d1}" in html, "应提供打开单据的链接"
        assert "明细行数" in html and "合计金额" in html, "应有单据级列"
        # 不再出现旧台账的物料级列头
        assert "查询已建账期初库存" not in html

    # ---- T2 编辑页无台账面板 ----

    def test_t2_editor_has_no_ledger_panel(self):
        d1, _ = self._seed_two_docs()
        resp = self.client.get(f"/opening_stock/{d1}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "查询已建账期初库存" not in html, "编辑页不应再堆台账查询面板"
        # 但仍是单据编辑页
        assert "期初库存单" in html

    # ---- T3 新建页无台账面板、从空白单据开始 ----

    def test_t3_add_page_is_blank_document(self):
        self._seed_two_docs()  # 已有数据也不应预填进新建页
        resp = self.client.get("/opening_stock/add")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "查询已建账期初库存" not in html
        # 新建页不再把台账全部记录预填进录入网格
        assert "const existingRows = [" in html

    # ---- T4 仓库筛选 ----

    def test_t4_warehouse_filter(self):
        d1, d2 = self._seed_two_docs()
        no1, no2 = self._doc_no(d1), self._doc_no(d2)
        resp = self.client.get(f"/opening_stock?warehouse_id={self.wh1.id}")
        html = resp.get_data(as_text=True)
        assert no1 in html, "应列出涉及一号仓的单据"
        assert no2 not in html, "不应列出仅涉及二号仓的单据"

    # ---- T5 关键字按单据号搜索 ----

    def test_t5_search_by_doc_no(self):
        d1, d2 = self._seed_two_docs()
        no1, no2 = self._doc_no(d1), self._doc_no(d2)
        resp = self.client.get(f"/opening_stock?search={no1}")
        html = resp.get_data(as_text=True)
        assert no1 in html
        assert no2 not in html

    # ---- T6 行数与合计金额正确 ----

    def test_t6_line_count_and_total_amount(self):
        d1, _ = self._seed_two_docs()
        no1 = self._doc_no(d1)
        resp = self.client.get("/opening_stock")
        html = resp.get_data(as_text=True)
        # d1：1 行，合计 100*5 = 500.00
        assert "500.00" in html, f"单据 {no1} 合计金额应显示 500.00"

    # ---- T7 前端静态断言 ----

    def test_t7_list_template_wired(self):
        html = LIST_TEMPLATE.read_text(encoding="utf-8")
        assert "删除全部" in html
        assert "function deleteAllOpeningStock()" in html
        assert "/opening_stock/delete_all" in html
        assert "function deleteDoc(" in html
        assert "/delete" in html
        assert "WMS.api.post" in html, "业务 JS 禁原生 fetch，须走 WMS.api"
        for col in ("单据号", "明细行数", "合计金额", "备注"):
            assert col in html, col

    def test_t7b_editor_template_detached(self):
        html = EDITOR_TEMPLATE.read_text(encoding="utf-8")
        # 编辑器不再放全量删除入口与台账面板
        assert "deleteAllOpeningStock" not in html
        assert "查询已建账期初库存" not in html
        # 仍保留单据编辑所需的导航与保存
        assert "navigateOpeningDoc" in html
        assert "window.__OPENING_DOC__" in html
