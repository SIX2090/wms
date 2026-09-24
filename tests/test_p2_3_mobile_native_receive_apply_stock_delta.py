# -*- coding: utf-8 -*-
"""P2-3 批 5：mobile / native_api 全量改道 + 委外快速收货补漏的回归锁（A9）。

本批范围与结论
--------------
1. **mobile.py 4 处**（扫码入库 / 扫码出库 / 草稿确认入库 / 草稿确认出库）
   收敛到 `apply_stock_delta`，库位账同步由入口按 `location_management_enabled()`
   自行决定；库位键口径逐字沿用 `location` 与 `order.location or order.warehouse`。
2. **native_api.py 2 处**（Android 扫码入库 / 出库）同样收敛。
   入库侧原有 `if document_location:` 与入口内部 `if location_management_enabled():`
   等价（`_native_document_location` 未开库位管理时返回 `''`）；
   出库侧 BUG-2026-08-16-020「仅开库位管理时写库位账」语义由入口同判。
3. **app.py `api_subcontract_quick_receive` 补漏**：老 API
   `/api/subcontract/quick_receive` 原仅 `add_stock` 只写①总账+③流水，
   开启库位管理时**从不写②库位账** —— BUG-2026-09-20-008 的**同型第二处**
   （008 修的是同文件的 `quick_issue`，414 行的 R6 排查把
   `routes/subcontract.py` 的网页版当成了全部，漏了这套老 API）。
4. **requisition.py 本批跳过**：扣减侧用 `deduct_location_inventory_atomic`
   会绕过 `update_location_inventory` 的「无库位记录且不允许负库存即失败」
   检查，收敛会改变失败语义，按 R8 不做净改变，单独评估。

函数名即 A9 锚点（lint 按 test_<函数名> 精确匹配）。
"""
from __future__ import annotations

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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    InOrder, InOrderItem, LocationInventory, Material, MaterialCategory,
    StockTransaction, SubcontractOrder, SubcontractReceive,
    SubcontractReceiveItem, Supplier, Unit, User, Warehouse, db,
    generate_order_no, set_system_setting,
)
from werkzeug.security import generate_password_hash  # noqa: E402
from services.warehouse_stock_service import apply_stock_delta  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

MOBILE_SRC = (APP_DIR / "routes" / "mobile.py").read_text(encoding="utf-8")
NATIVE_SRC = (APP_DIR / "routes" / "native_api.py").read_text(encoding="utf-8")
APP_SRC = (APP_DIR / "app.py").read_text(encoding="utf-8")

RAW_PRIMITIVES = (
    "add_stock(", "deduct_stock(", "deduct_stock_atomic(",
    "update_location_inventory(", "deduct_location_inventory_atomic(",
)

# 已收敛的路由函数（结构锁锚点）
MOBILE_ROUTES = (
    "mobile_scan_submit", "mobile_scan_draft_confirm",
)
NATIVE_ROUTES = (
    "native_api_inbound", "native_api_outbound",
)

WAREHOUSE = "批5仓"
LOCATION = "B5-01"


def _seed():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        unit = Unit(code="PCS", name="个")
        warehouse = Warehouse(code="B5_WH", name=WAREHOUSE, status="active",
                              is_default=True)
        supplier = Supplier(code="B5_SUP", name="批5供应商")
        category = MaterialCategory(name="默认分类", code="CAT-B5")
        user = User(username="admin", password_hash=generate_password_hash("admin"),
                    role="admin", status="normal", must_change_password=False)
        db.session.add_all([unit, warehouse, supplier, category, user])
        db.session.commit()
        material = Material(code="B5_MAT", name="批5物料", spec="S",
                            category_id=category.id, unit_id=unit.id,
                            supplier_id=supplier.id, stock=0, price=1)
        db.session.add(material)
        db.session.commit()
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
        return material.id


@pytest.fixture()
def client():
    _seed()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"})
    return c


def _material_id():
    with app_module.app.app_context():
        return Material.query.filter_by(code="B5_MAT").one().id


def _loc_qty(location=LOCATION):
    with app_module.app.app_context():
        mid = _material_id()
        wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
        inv = LocationInventory.query.filter_by(
            material_id=mid, location=location, warehouse_id=wh.id).first()
        return inv.quantity if inv else None


def _stock():
    with app_module.app.app_context():
        db.session.expire_all()
        return Material.query.filter_by(code="B5_MAT").one().stock or 0


def _ledger_net(types):
    with app_module.app.app_context():
        mid = _material_id()
        txns = StockTransaction.query.filter(
            StockTransaction.material_id == mid,
            StockTransaction.transaction_type.in_(types)).all()
        return sum(t.quantity for t in txns)


def _enable(enabled):
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "1" if enabled else "0")
        db.session.commit()


def _stock_in(qty, location=LOCATION):
    """铺底：走同一入口写三账（含库位账基线行）。"""
    with app_module.app.app_context():
        with app_module.app.test_request_context():
            material = Material.query.filter_by(code="B5_MAT").one()
            ok, err = apply_stock_delta(material, qty, transaction_type="in",
                                        warehouse=WAREHOUSE, location=location)
            assert ok, err
        db.session.commit()


def _create_receive_order():
    with app_module.app.app_context():
        order = SubcontractOrder(order_no=generate_order_no("WW"), supplier_id=1,
                                 warehouse=WAREHOUSE, status="pending")
        db.session.add(order)
        db.session.commit()
        return order.id


# ================================================================ 结构锁

def test_mobile_has_no_raw_stock_primitives():
    """mobile.py 不再裸调任何库存原语（批 5 收敛结论）。"""
    for lineno, line in enumerate(MOBILE_SRC.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for prim in RAW_PRIMITIVES:
            assert prim not in line, (
                f"mobile.py 第 {lineno} 行仍在裸调 {prim}，必须改道 apply_stock_delta")


def test_native_api_has_no_raw_stock_primitives():
    """native_api.py 不再裸调任何库存原语（批 5 收敛结论）。"""
    for lineno, line in enumerate(NATIVE_SRC.splitlines(), start=1):
        if line.strip().startswith("#"):
            continue
        for prim in RAW_PRIMITIVES:
            assert prim not in line, (
                f"native_api.py 第 {lineno} 行仍在裸调 {prim}，必须改道 apply_stock_delta")


def test_converged_routes_import_apply_stock_delta():
    """mobile / native_api 的收敛路由函数都必须经唯一入口导入。"""
    pairs = ([(MOBILE_SRC, f) for f in MOBILE_ROUTES]
             + [(NATIVE_SRC, f) for f in NATIVE_ROUTES])
    for src, func in pairs:
        start = src.index(f"def {func}(")
        nxt = src.find("\n    @app.route", start)
        body = src[start:nxt] if nxt != -1 else src[start:]
        assert "from services.warehouse_stock_service import apply_stock_delta" in body, (
            f"{func} 未导入 apply_stock_delta")


def test_quick_receive_routes_use_apply_stock_delta():
    """委外快速收货两套实现（老 API + 网页版）都必须经唯一入口。"""
    # app.py 老 API
    start = APP_SRC.index("def api_subcontract_quick_receive(")
    nxt = APP_SRC.find("\ndef validate_password_strength", start)
    body = APP_SRC[start:nxt]
    assert "apply_stock_delta(" in body, (
        "api_subcontract_quick_receive 未改道 apply_stock_delta")
    assert "add_stock(" not in body, (
        "api_subcontract_quick_receive 仍在裸调 add_stock（BUG-2026-09-20-008 同型缺口）")
    # 网页版（batch 4 已收敛，此处防回退）
    web = (APP_DIR / "routes" / "subcontract.py").read_text(encoding="utf-8")
    wstart = web.index("def quick_receive_subcontract(")
    wend = web.find("\n    @app.route", wstart)
    wbody = web[wstart:wend] if wend != -1 else web[wstart:]
    assert "apply_stock_delta(" in wbody, "网页版快速收货未用入口"


# ================================================================ 行为锁：委外快速收货补漏

def test_quick_receive_api_syncs_location_inventory_when_enabled(client):
    """核心：老 API 委外收货开启库位管理时必须同步②库位账，①=②。"""
    _stock_in(0)  # 仅确保库位账基线存在（数量 0）
    _enable(True)
    oid = _create_receive_order()
    mid = _material_id()
    resp = client.post("/api/subcontract/quick_receive",
                       json={"order_id": oid, "material_id": mid, "quantity": 7})
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        assert _stock() == 7, "①总账未入账"
        assert abs(_loc_qty(WAREHOUSE) - 7) < 1e-6, \
            "②库位账未同步（BUG-2026-09-20-008 同型：收货方向漏写是历史缺口）"


def test_quick_receive_api_location_key_is_warehouse(client):
    """库位键回退仓库名，与网页版 batch 4 的 `location or warehouse` 逐字一致。"""
    _stock_in(0)
    _enable(True)
    oid = _create_receive_order()
    mid = _material_id()
    assert client.post("/api/subcontract/quick_receive",
                       json={"order_id": oid, "material_id": mid,
                             "quantity": 4}).get_json().get("status") == "success"
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
        rows = LocationInventory.query.filter_by(
            material_id=mid, warehouse_id=wh.id).all()
        keys = sorted(r.location for r in rows)
        assert WAREHOUSE in keys, f"库位键应为仓库名回退，实际 {keys}"
        assert sum(r.quantity or 0 for r in rows) == 4, "库位账合计应为 4"


def test_quick_receive_api_skips_location_when_disabled(client):
    """未开库位管理：不写库位账（向后兼容）。"""
    _enable(False)
    oid = _create_receive_order()
    mid = _material_id()
    resp = client.post("/api/subcontract/quick_receive",
                       json={"order_id": oid, "material_id": mid, "quantity": 3})
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        assert _stock() == 3, "①总账照常入账"
        wh = Warehouse.query.filter_by(name=WAREHOUSE).one()
        rows = LocationInventory.query.filter_by(
            material_id=mid, warehouse_id=wh.id).all()
        assert not rows, "关库位管理时不得写库位账（BUG-2026-08-16-020 口径）"


def test_quick_receive_api_ledger_identity(client):
    """三账恒等式：①总账 = ③流水净额 = ②库位账（开启库位管理）。"""
    _enable(True)
    oid = _create_receive_order()
    mid = _material_id()
    assert client.post("/api/subcontract/quick_receive",
                       json={"order_id": oid, "material_id": mid,
                             "quantity": 5}).get_json().get("status") == "success"
    with app_module.app.app_context():
        stock, loc = _stock(), _loc_qty(WAREHOUSE)
        txn = _ledger_net(["subcontract_receive"])
        assert stock == 5 and abs(loc - 5) < 1e-6 and txn == 5, \
            f"恒等式 ①={stock} ②={loc} ③={txn} 不成立"


# ================================================================ 行为锁：mobile 扫码

def test_mobile_scan_inbound_three_ledgers(client):
    """手机扫码入库：三账同增（开启库位管理）。"""
    _enable(True)
    resp = client.post("/mobile/api/scan_submit", json={
        "mode": "in", "code": "B5_MAT", "quantity": 6,
        "warehouse": WAREHOUSE, "location": LOCATION,
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        assert _stock() == 6, "①总账未入账"
        assert _ledger_net(["in"]) == 6, "③流水未写"
        assert abs(_loc_qty(LOCATION) - 6) < 1e-6, "②库位账未同步"


def test_mobile_scan_outbound_three_ledgers(client):
    """手机扫码出库：三账同减（开启库位管理）。"""
    _enable(True)
    _stock_in(20)
    resp = client.post("/mobile/api/scan_submit", json={
        "mode": "out", "code": "B5_MAT", "quantity": 8,
        "warehouse": WAREHOUSE, "location": LOCATION,
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        assert _stock() == 12, "①总账未扣减"
        assert abs(_loc_qty(LOCATION) - 12) < 1e-6, "②库位账未同步扣减"


def test_mobile_scan_inbound_disabled_keeps_location_untouched(client):
    """关库位管理：手机扫码入库只动总账/流水，不写库位账。"""
    _enable(False)
    resp = client.post("/mobile/api/scan_submit", json={
        "mode": "in", "code": "B5_MAT", "quantity": 5,
        "warehouse": WAREHOUSE, "location": LOCATION,
    })
    assert resp.get_json().get("status") == "success", resp.get_json()
    with app_module.app.app_context():
        assert _stock() == 5
        wq = _loc_qty(LOCATION)
        assert wq in (None, 0), f"关库位管理不得写库位账，实际 {wq}"
