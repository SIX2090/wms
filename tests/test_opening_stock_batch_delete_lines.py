# -*- coding: utf-8 -*-
"""期初库存「勾选批量删行」回归（用户诉求：「把批量删行做出来」）。

背景：改造前只有两条删行路径——
  · 每行一个删除图标 → 只改前端 rows 数组，必须再点"保存"才落库；
  · 后端单行接口 `/opening_stock/<id>/line/<line_id>/delete` → 前端从未接线
    （死接口），且一次只删一行，几十行的导入单要按几十次。
本次补齐 `POST /opening_stock/<id>/lines/delete`：一次删多行、逐行回冲库存、
越权整体拒绝，前端加勾选列 + 表头全选 + 「删除选中行」按钮。
那条单行死接口已随之废弃移除（能力被本批量接口完全包含），T9 锁死该结局。

覆盖：
  T1 批量删 2 行：库存按各自数量回冲，剩余行与未选行不受影响
  T2 越权防护：混入他单的 line_id → 整批 400 且一行都不删
  T3 line_ids 缺失 / 空列表 / 非正数 → 400，数据不动
  T4 单据不存在 → 404
  T5 未登录访问被拦截（不删除）
  T6 回冲写入 StockTransaction 负向流水（账实可追溯）
  T7 重复 id 去重：只删一次、只回冲一次
  T8 前端静态断言：勾选列 + 全选 + 批量删除按钮 + 端点齐全
  T9 单行死接口已废弃：路由表不再注册，防止被无意恢复造成双实现漂移
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

TEMPLATE = APP_DIR / "templates" / "opening_stock.html"


class TestOpeningStockBatchDeleteLines:
    """批量删行的后端账务与权限契约。"""

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
        self.m3 = Material(code="M003", name="垫片", unit_id=unit.id, stock=0)
        db.session.add_all([self.m1, self.m2, self.m3])
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

    def _batch_delete(self, doc_id, payload):
        resp = self.client.post(f"/opening_stock/{doc_id}/lines/delete", json=payload)
        try:
            return resp.status_code, resp.get_json()
        except Exception:  # pragma: no cover - 兜底便于定位 500
            return resp.status_code, {"raw": resp.data[:300].decode("utf-8", "replace")}

    def _seed_doc(self, specs, warehouse=None):
        """建一张单：specs = [(material, quantity)]，返回 doc_id。"""
        wh = warehouse or self.wh1
        st, body = self._save({
            "warehouse_id": wh.id,
            "date": "2026-09-16",
            "items": [
                {"material_id": m.id, "warehouse_id": wh.id,
                 "quantity": q, "price": 5}
                for m, q in specs
            ],
        })
        assert st == 200, body
        return body["doc_id"]

    def _lines_of(self, doc_id):
        return (OpeningStock.query.filter_by(doc_id=doc_id)
                .order_by(OpeningStock.id.asc()).all())

    # ---- T1 批量删除 + 按行回冲 ----

    def test_t1_batch_delete_reverses_each_line(self):
        doc_id = self._seed_doc([(self.m1, 10), (self.m2, 20), (self.m3, 30)])
        assert self._stock(self.m1) == 10.0
        assert self._stock(self.m2) == 20.0
        assert self._stock(self.m3) == 30.0

        lines = self._lines_of(doc_id)
        assert len(lines) == 3
        # 删前两行（对应 M001=10、M002=20）
        target_ids = [lines[0].id, lines[1].id]
        st, body = self._batch_delete(doc_id, {"line_ids": target_ids})
        assert st == 200, body
        assert body["status"] == "success"
        assert body["deleted_count"] == 2
        assert body["reversed_count"] == 2

        # 被删两行按各自数量回冲归零；未选中的 M003 不受影响（不串账）
        assert self._stock(self.m1) == 0.0
        assert self._stock(self.m2) == 0.0
        assert self._stock(self.m3) == 30.0

        remain = self._lines_of(doc_id)
        assert len(remain) == 1
        assert remain[0].material_id == self.m3.id
        # 单据头保留（只删行不删单）
        assert OpeningStockDoc.query.filter_by(id=doc_id).count() == 1

    # ---- T2 越权：混入他单的行必须整批拒绝 ----

    def test_t2_cross_doc_line_id_rejected_atomically(self):
        doc_a = self._seed_doc([(self.m1, 10), (self.m2, 20)])
        doc_b = self._seed_doc([(self.m3, 30)])

        lines_a = self._lines_of(doc_a)
        lines_b = self._lines_of(doc_b)
        assert len(lines_a) == 2 and len(lines_b) == 1

        # 本单第一行 + 他单的行 → 必须整体 400，一行都不能删
        mixed = [lines_a[0].id, lines_b[0].id]
        st, body = self._batch_delete(doc_a, {"line_ids": mixed})
        assert st == 400, body
        assert body["status"] == "error"

        # A 单两行、B 单一行都原样保留，库存不动
        assert len(self._lines_of(doc_a)) == 2
        assert len(self._lines_of(doc_b)) == 1
        assert self._stock(self.m1) == 10.0
        assert self._stock(self.m2) == 20.0
        assert self._stock(self.m3) == 30.0

    # ---- T3 入参校验（A8 pydantic）----

    def test_t3_invalid_payload_rejected(self):
        doc_id = self._seed_doc([(self.m1, 10)])
        line_id = self._lines_of(doc_id)[0].id

        for payload in ({}, {"line_ids": []}, {"line_ids": None}, {"line_ids": "x"}):
            st, body = self._batch_delete(doc_id, payload)
            assert st == 400, (payload, body)
            assert body["status"] == "error"

        # 非正数 id 同样拒绝
        st, body = self._batch_delete(doc_id, {"line_ids": [0]})
        assert st == 400, body
        st, body = self._batch_delete(doc_id, {"line_ids": [-5]})
        assert st == 400, body

        # 数据始终没动
        assert len(self._lines_of(doc_id)) == 1
        assert self._stock(self.m1) == 10.0
        # 合法 id 仍可正常删除（确保上面的拒绝不是把接口打坏了）
        st, body = self._batch_delete(doc_id, {"line_ids": [line_id]})
        assert st == 200, body
        assert len(self._lines_of(doc_id)) == 0

    # ---- T4 单据不存在 ----

    def test_t4_missing_doc_returns_404(self):
        st, body = self._batch_delete(999999, {"line_ids": [1]})
        assert st == 404, body
        assert body["status"] == "error"

    # ---- T5 未登录被拦截 ----

    def test_t5_unauthenticated_cannot_delete(self):
        doc_id = self._seed_doc([(self.m1, 10), (self.m2, 20)])
        line_id = self._lines_of(doc_id)[0].id

        anon = flask_app.test_client()
        # 测试夹具常驻 app_context 会把登录态泄漏给后续 test_client，先显式 logout
        anon.get("/logout")
        resp = anon.post(f"/opening_stock/{doc_id}/lines/delete",
                         json={"line_ids": [line_id]})
        # 安全契约：未登录绝不能删任何数据（302 跳登录或 401/403 均可）
        assert resp.status_code in (302, 401, 403)
        assert len(self._lines_of(doc_id)) == 2
        assert self._stock(self.m1) == 10.0
        try:
            body = resp.get_json() or {}
        except Exception:
            body = {}
        assert body.get("status") != "success"

    # ---- T6 回冲写负向流水 ----

    def test_t6_reversal_writes_negative_transactions(self):
        doc_id = self._seed_doc([(self.m1, 10), (self.m2, 20)])
        before = StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0,
        ).count()

        line_ids = [l.id for l in self._lines_of(doc_id)]
        st, body = self._batch_delete(doc_id, {"line_ids": line_ids})
        assert st == 200, body

        after = StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0,
        ).count()
        # 两行各写一条负向回冲流水
        assert after - before == 2

    # ---- T7 幂等与重复 id ----

    def test_t7_duplicate_ids_deleted_once(self):
        doc_id = self._seed_doc([(self.m1, 10), (self.m2, 20)])
        lines = self._lines_of(doc_id)
        # 同一行的 id 传两次，只应删一次、只回冲一次，否则库存会被重复扣减
        dup = [lines[0].id, lines[0].id]
        st, body = self._batch_delete(doc_id, {"line_ids": dup})
        assert st == 200, body
        assert body["deleted_count"] == 1
        assert self._stock(self.m1) == 0.0
        assert self._stock(self.m2) == 20.0


class TestOpeningStockBatchDeleteFrontend:
    """前端静态断言：勾选列 / 全选 / 批量删除按钮与端点接线齐全。"""

    def test_t8_checkbox_column_and_handler_wired(self):
        html = TEMPLATE.read_text(encoding="utf-8")
        # 表头全选框 + 每行勾选框
        assert 'id="openingCheckAll"' in html, "表头应有全选框 #openingCheckAll"
        assert "opening-row-check" in html, "每行应有勾选框 class=opening-row-check"
        # 批量删除按钮与函数
        assert "删除选中行" in html, "工具栏应有「删除选中行」按钮"
        assert "function batchDeleteSelectedRows()" in html, "应定义 batchDeleteSelectedRows()"
        assert 'onclick="batchDeleteSelectedRows()"' in html, "按钮应绑定 batchDeleteSelectedRows()"
        # 端点与统一 API 层（禁原生 fetch）
        assert "/lines/delete" in html, "应调用批量删行端点"
        assert "WMS.api.post" in html, "批量删除应走 WMS.api（禁原生 fetch）"
        # 勾选态与全选联动
        assert "function syncCheckAllState()" in html
        assert "function onRowCheckToggle(" in html
        assert "indeterminate" in html, "全选框应体现半选态"
        # 勾选态必须提到数据层，否则 renderRows 重建 tbody 后勾选丢失
        assert "selectedFlags" in html, "勾选态需存于数据层以跨重渲染保持"


class TestDeprecatedSingleLineDeleteRoute:
    """T9：单行删除死接口已废弃移除，防止被无意恢复。"""

    def test_t9_single_line_route_removed(self):
        """路由表不得再注册 `/opening_stock/<id>/line/<line_id>/delete`。

        该接口自 ARCH-OS-DOC-01 起前端零调用（含 Android App 与全部 tests），
        且能力已被 `/lines/delete` 完全包含。两个接口并存会重新制造
        "同一能力两处实现、回冲规则各自漂移"的隐患（R6），故删除并用本用例锁死。
        删除单行请调 `/lines/delete` 传单个 line_id。
        """
        rules = {str(r.rule) for r in flask_app.url_map.iter_rules()}
        assert "/opening_stock/<int:id>/line/<int:line_id>/delete" not in rules, (
            "单行删除死接口已被废弃移除，不应重新注册；删单行请走 "
            "/opening_stock/<id>/lines/delete（传单个 line_id）"
        )
        # 批量接口必须仍在（确保上面删的是死接口、不是把删行能力整体删掉了）
        assert "/opening_stock/<int:id>/lines/delete" in rules

    def test_t9_single_line_route_returns_404(self):
        """即便有人手工拼老 URL，也只能拿到 404（不再有删行能力）。"""
        client = flask_app.test_client()
        resp = client.post("/opening_stock/1/line/1/delete", json={})
        assert resp.status_code == 404

