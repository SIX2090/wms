# -*- coding: utf-8 -*-
"""BUG-2026-09-16-011 回归：期初库存单据网格补库位列（AGENTS.md 规则二）。

问题：开启库位管理后，出入库单据「仓库和库位均为必填」，但期初库存网格
**没有库位列**——后端 `_apply_opening_stock_balance` 与 `/opening_stock/save`
早已支持 location 入参，前端却没有任何录入入口，期初永远落不到真实库位
（只能以仓库名作占位行进库位账）。手机端同样无库位选择（另行任务）。

改造（与入库单 in_order_add.html 同口径）：
  - 两个编辑页路由把 `location_management_enabled()` 传入模板；
  - 开启时网格显示「库位」列（红星必填标识），编辑已有单据回填行库位；
  - `collectItems()` 携带 location，保存前逐行必填校验（空行跳过）；
  - 空态 colspan 随开关 +1（GRID_COLSPAN），避免列数对不上表头。

覆盖：
  T1 开启库位管理：新建页渲染库位列头 + LOCATION_ENABLED=true
  T2 关闭库位管理：不渲染库位列头 + LOCATION_ENABLED=false
  T3 编辑页回填：明细行 location 值注入 existingRows
  T4 保存全链路：带 location 保存后落库，再编辑仍能回填（端到端接线）
  T5 静态契约：collectItems 携带 location / emptyRow 含 location /
     网格单元格与必填校验存在 / 空态 colspan 用 GRID_COLSPAN
"""
from __future__ import annotations

import os
import re
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
    set_system_setting,
)

flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False

EDITOR_TEMPLATE = APP_DIR / "templates" / "opening_stock.html"


class TestOpeningStockLocationColumn:
    """期初网格库位列的页面行为与保存链路契约。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        self._wipe()
        set_system_setting("location_management_enabled", "0")

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()
        self.wh1 = Warehouse(code="W1", name="一号仓", status="active")
        db.session.add(self.wh1)
        db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0, price=5)
        db.session.add(self.m1)
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        set_system_setting("location_management_enabled", "0")
        self._wipe()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _wipe(self):
        from app import LocationInventory
        for model in (OpeningStock, OpeningStockDoc, StockTransaction,
                      LocationInventory,
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

    # ---- T1 开启：新建页渲染库位列 ----

    def test_t1_add_page_shows_location_column_when_enabled(self):
        set_system_setting("location_management_enabled", "1")
        resp = self.client.get("/opening_stock/add")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "库位" in html, "开启库位管理后新建页未渲染库位列"
        assert "const LOCATION_ENABLED = true;" in html

    # ---- T2 关闭：不渲染库位列 ----

    def test_t2_add_page_hides_location_column_when_disabled(self):
        resp = self.client.get("/opening_stock/add")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "const LOCATION_ENABLED = false;" in html
        assert "库位 <span" not in html, "关闭库位管理时不应渲染库位列头"

    # ---- T3 编辑页回填行库位 ----

    def _seed_doc_with_location(self):
        resp = self.client.post("/opening_stock/save", json={
            "warehouse_id": self.wh1.id, "date": "2026-09-16",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 5, "location": "A-01-03"}],
        })
        body = resp.get_json()
        assert resp.status_code == 200 and body["status"] == "success", body
        return body["doc_id"]

    def test_t3_edit_page_refills_row_location(self):
        set_system_setting("location_management_enabled", "1")
        doc_id = self._seed_doc_with_location()
        resp = self.client.get(f"/opening_stock/{doc_id}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'location: "A-01-03"' in html, "编辑页未把行库位回填进 existingRows"

    # ---- T4 保存全链路落库 ----

    def test_t4_save_persists_location(self):
        set_system_setting("location_management_enabled", "1")
        doc_id = self._seed_doc_with_location()
        line = OpeningStock.query.filter_by(doc_id=doc_id).first()
        assert line is not None
        assert line.location == "A-01-03", f"库位未落库：{line.location!r}"
        # 库位账同步到真实库位而非仓库名占位行（BUG-2026-08-16-002 口径）
        from app import LocationInventory
        inv = LocationInventory.query.filter_by(
            material_id=self.m1.id, warehouse_id=self.wh1.id).all()
        assert any(row.location == "A-01-03" and (row.quantity or 0) == 100
                   for row in inv), f"库位账未落到真实库位：{[(r.location, r.quantity) for r in inv]}"

    # ---- T5 静态契约 ----

    def test_t5_template_static_contract(self):
        src = EDITOR_TEMPLATE.read_text(encoding="utf-8")
        # collectItems 必须携带 location（否则填了也传不到后端）
        collect = re.search(r"function collectItems\(\).*?\n}", src, flags=re.DOTALL)
        assert collect and "location:" in collect.group(0), "collectItems 未携带 location"
        # emptyRow 必须含 location 字段
        empty = re.search(r"function emptyRow\(\).*?\n}", src, flags=re.DOTALL)
        assert empty and "location: ''" in empty.group(0), "emptyRow 缺少 location 字段"
        # 网格单元格与开关守卫
        assert "LOCATION_ENABLED" in src and "data-field=\"location\"" in src, (
            "网格未按 LOCATION_ENABLED 渲染库位单元格"
        )
        # 空态 colspan 不得再写死 12
        assert 'colspan="${GRID_COLSPAN}"' in src, "空态行未使用 GRID_COLSPAN"
        # 必填校验（规则二）
        assert "未填写库位" in src, "保存前缺少库位必填校验提示"
