# -*- coding: utf-8 -*-
"""P1-7③：建账语义收敛到 apply_opening_balance 后的行为钉子。

为什么是**第三个**入口（不是塞进 apply_stock_delta）：
    物料初始库存 / 期初建账的 ①总账是**调用方自己定的**——新增物料时
    Material.stock 在构造时就被赋成 initial_stock，期初单据里则由
    _apply_opening_stock_balance 的 sa_update 自己加减差额。
    若走 apply_stock_delta，它会 add_stock 再涨一次 ①，
    **初始库存直接翻倍**（这就是判据 T7 钉住的东西）。

三个入口的语义边界（本文件逐条固化）：
    apply_stock_delta      入/出库：改 ① + ③ + ②
    apply_transfer_pair    调拨：① 不动 + 双向 ③ + ②
    apply_opening_balance  建账：① 不动（调用方负责）+ ③ + ②

测试用例：
  T1. 入口语义（开库位）：① 不动、③ 一条 opening +q、② +q
  T2. 关库位：只写 ③，② 不写（与既有 no_location_rows 口径一致）
  T3. quantity == 0：不写任何账、直接成功（与 material.py initial_stock>0 一致）
  T4. 负数量（期初调减差额）：③ 写负、② 同步减——为下一阶段期初收敛预留
  T5. 路由端到端（新增物料带初始库存）：① == Σ③ == initial，① 没有被翻倍
  T6. 路由端到端（开库位）：① == Σ② == Σ③
"""
from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory, Material, MaterialCategory, StockTransaction, Unit,
    User, Warehouse, db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TOL = 0.01


# ────────────────────────── 夹具 ──────────────────────────

def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client):
    client.post("/login",
                data={"username": "p17o", "password": "admin"},
                content_type="application/x-www-form-urlencoded")


def _seed(location_on: bool):
    set_system_setting("location_management_enabled", "1" if location_on else "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        User(username="p17o", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
    c = app_module.app.test_client()
    yield c


# ────────────────────────── 三账读数 ──────────────────────────

def _ledger(mat_id):
    with app_module.app.app_context():
        return float(Material.query.get(mat_id).stock or 0)


def _txn_sum(mat_id):
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mat_id).all()
        return float(sum((r.quantity or 0) for r in rows))


def _loc_sum(mat_id):
    with app_module.app.app_context():
        rows = LocationInventory.query.filter_by(material_id=mat_id).all()
        return float(sum((r.quantity or 0) for r in rows))


def _txn_types(mat_id):
    with app_module.app.app_context():
        rows = StockTransaction.query.filter_by(material_id=mat_id).all()
        return sorted(r.transaction_type for r in rows)


# ────────────────────────── T1~T4 入口语义 ──────────────────────────

class TestApplyOpeningBalanceEntry:

    def test_apply_opening_balance(self, client):
        """T1（开库位）：① 不动、③ 一条 opening +q、② +q。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=True)
            mat = Material(code="M-OP", name="建账料", spec="S",
                           category_id=1, unit_id=1, stock=8, price=10)
            db.session.add(mat)
            db.session.commit()
            mid = mat.id
            from services.warehouse_stock_service import apply_opening_balance
            ok, msg = apply_opening_balance(
                mat, 8, warehouse=Warehouse.query.filter_by(code="WHA").first())
            assert ok, msg
            db.session.commit()
        # ① 由调用方定（构造时已赋 8），入口绝不能再动它——否则翻倍成 16
        assert abs(_ledger(mid) - 8) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 8) <= TOL, _txn_sum(mid)
        assert _txn_types(mid) == ['opening'], _txn_types(mid)
        assert abs(_loc_sum(mid) - 8) <= TOL, _loc_sum(mid)

    def test_apply_opening_balance_without_location_management(self, client):
        """T2（关库位）：只写 ③，② 保持空（既有 no_location_rows 口径）。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=False)
            mat = Material(code="M-OP", name="建账料", spec="S",
                           category_id=1, unit_id=1, stock=5, price=10)
            db.session.add(mat)
            db.session.commit()
            mid = mat.id
            from services.warehouse_stock_service import apply_opening_balance
            ok, msg = apply_opening_balance(
                mat, 5, warehouse=Warehouse.query.filter_by(code="WHA").first())
            assert ok, msg
            db.session.commit()
        assert abs(_ledger(mid) - 5) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 5) <= TOL, _txn_sum(mid)
        assert abs(_loc_sum(mid) - 0) <= TOL, _loc_sum(mid)

    def test_apply_opening_balance_zero_quantity_writes_nothing(self, client):
        """T3：0 数量不写任何账（与 material.py initial_stock>0 同口径）。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=True)
            mat = Material(code="M-OP", name="建账料", spec="S",
                           category_id=1, unit_id=1, stock=0, price=10)
            db.session.add(mat)
            db.session.commit()
            mid = mat.id
            from services.warehouse_stock_service import apply_opening_balance
            ok, msg = apply_opening_balance(mat, 0)
            assert ok, msg
            db.session.commit()
        assert _txn_types(mid) == [], _txn_types(mid)
        assert abs(_loc_sum(mid) - 0) <= TOL, _loc_sum(mid)

    def test_apply_opening_balance_negative_delta(self, client):
        """T4：负数量（期初改单调减差额）→ ③ 写负、② 同步减。"""
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=True)
            mat = Material(code="M-OP", name="建账料", spec="S",
                           category_id=1, unit_id=1, stock=10, price=10)
            db.session.add(mat)
            db.session.commit()
            mid = mat.id
            wh = Warehouse.query.filter_by(code="WHA").first()
            from services.warehouse_stock_service import apply_opening_balance
            # 先建账 10（入口已同步写好 ②，无需再手写 update_location_inventory）
            assert apply_opening_balance(mat, 10, warehouse=wh)[0]
            db.session.commit()
            # 期初由 10 调减到 4：差额 -6
            ok, msg = apply_opening_balance(mat, -6, warehouse=wh)
            assert ok, msg
            db.session.commit()
        assert abs(_txn_sum(mid) - 4) <= TOL, _txn_sum(mid)
        assert abs(_loc_sum(mid) - 4) <= TOL, _loc_sum(mid)
        assert abs(_ledger(mid) - 10) <= TOL, _ledger(mid)  # ① 仍由调用方负责


# ────────────────────────── T5~T6 路由端到端 ──────────────────────────

class TestMaterialAddInitialStockRoute:

    def _add_material(self, client, stock, *, location_on):
        with app_module.app.test_request_context():
            _reset_db()
            _seed(location_on=location_on)
        _login(client)
        resp = client.post("/material/add", data={
            "code": "M-INIT",
            "name": "初始库存料",
            "spec": "S",
            "category_id": "1",
            "unit_id": "1",
            "stock": str(stock),
            "price": "10",
            "min_stock": "0",
            "safety_stock": "0",
            "max_stock": "0",
            "alert_days": "30",
        }, content_type="application/x-www-form-urlencoded")
        body = resp.get_json()
        assert body.get("status") == "success", body
        return body

    def test_add_material_with_initial_stock_not_doubled(self, client):
        """T5（关库位）：① == Σ③ == initial —— ① 没有被入口再涨一次。"""
        self._add_material(client, 12, location_on=False)
        with app_module.app.app_context():
            mat = Material.query.filter_by(code="M-INIT").first()
            assert mat is not None
            mid = mat.id
        assert abs(_ledger(mid) - 12) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 12) <= TOL, _txn_sum(mid)
        assert _txn_types(mid) == ['opening'], _txn_types(mid)

    def test_add_material_with_initial_stock_location_ledger(self, client):
        """T6（开库位）：三账恒等 ① == Σ② == Σ③ == initial。"""
        self._add_material(client, 12, location_on=True)
        with app_module.app.app_context():
            mat = Material.query.filter_by(code="M-INIT").first()
            assert mat is not None
            mid = mat.id
        assert abs(_ledger(mid) - 12) <= TOL, _ledger(mid)
        assert abs(_txn_sum(mid) - 12) <= TOL, _txn_sum(mid)
        assert abs(_loc_sum(mid) - 12) <= TOL, _loc_sum(mid)
