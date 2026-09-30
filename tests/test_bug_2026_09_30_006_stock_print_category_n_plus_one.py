# -*- coding: utf-8 -*-
"""BUG-2026-09-30-006 回归：/report/stock/print 的 category 懒加载 N+1 锁。

现象（M1 基线 E1）：库存 Excel 导出 5000 物料 2.68s / 内存 20.7MB，线性增长。
根因之一：`Material.query.options(joinedload(Material.unit)).all()` 只预加载
unit，循环体内 `m.category.name`（无 category 也触发查询）逐物料懒加载——
5000 物料 = 5000 次额外 SQL。

修复：joinedload(Material.category)。本文件锁死：
1. 查询计数锁——60 物料（各配独立分类）导出期间 SQL ≤ 20 条
   （修复前 ~70 条：1 主查 + 60 category 懒加载 + 库存聚合 + 开销）；
2. 内容正确性锁——「分类」列显示分类名（eager loading 不改变导出内容）。
"""
from __future__ import annotations

import io
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

N_MATERIALS = 60


def _reset_db():
    db.drop_all()
    db.create_all()


class TestStockPrintCategoryNPlusOne:

    def teardown_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()

    def test_stock_print_query_bounded_and_category_column(self):
        from sqlalchemy import event
        from app import Material, MaterialCategory, Unit, Warehouse

        with app_module.app.app_context():
            _reset_db()
            db.session.add(User_seed())
            db.session.commit()
            wh = Warehouse(code="WHA", name="仓库A", status="active", is_default=True)
            db.session.add(wh)
            db.session.flush()
            unit = Unit(code="PCS", name="个")
            db.session.add(unit)
            db.session.flush()
            # 每物料一个独立分类：懒加载无法共享，最坏 N+1 场景
            for i in range(N_MATERIALS):
                cat = MaterialCategory(code=f"C{i:03d}", name=f"分类{i}")
                db.session.add(cat)
                db.session.flush()
                db.session.add(Material(code=f"MS{i:04d}", name=f"物料{i}",
                                        stock=0, unit_id=unit.id, category_id=cat.id))
            db.session.commit()
            wh_id = wh.id

        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"},
                    content_type="application/x-www-form-urlencoded")

        counter = {"n": 0}

        def _count(conn, cursor, statement, parameters, context, executemany):
            counter["n"] += 1

        with app_module.app.app_context():
            event.listen(db.engine, "before_cursor_execute", _count)
            try:
                resp = client.get(f"/report/stock/print?warehouse_id={wh_id}")
            finally:
                event.remove(db.engine, "before_cursor_execute", _count)

        # --- 锁 1：查询数有界（修复前 60 物料 ≈ 1+60+聚合+开销 ~70 条；修复后 ~10 条） ---
        assert resp.status_code == 200, resp.status_code
        assert counter["n"] <= 20, (
            f"库存导出期间 SQL 查询数 {counter['n']} 超阈值 20——"
            f"category 懒加载 N+1 疑似回归（N_MATERIALS={N_MATERIALS}，"
            f"修复后预期 ~10 条，修复前 ~70 条）"
        )

        # --- 锁 2：分类列显示分类名（eager loading 不改变导出内容） ---
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(resp.data))
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        headers = rows[0]
        cat_idx = headers.index('分类')
        data = rows[1:]
        assert len(data) == N_MATERIALS, f"行数 {len(data)} != {N_MATERIALS}"
        by_code = {r[0]: r for r in data}
        row0 = by_code["MS0000"]
        assert row0[cat_idx] == "分类0", f"分类列错误：{row0[cat_idx]!r}"
        # 全集校验：每行分类名与物料序号一致
        for i in range(N_MATERIALS):
            r = by_code[f"MS{i:04d}"]
            assert r[cat_idx] == f"分类{i}", r


def User_seed():
    from app import User
    return User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
