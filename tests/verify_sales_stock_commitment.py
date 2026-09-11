# -*- coding: utf-8 -*-
"""STOCK-TRUTH / P1-6 回归：销售订单库存占用（软占用派生计算）。

根因：销售链路对库存一无所知——下单不校验、下推不校验，直到仓库
出库时才发现没货（超卖的实际发生路径）。

方案（D1 决策：审批通过后占用）：
- 占用是**查询**不是**状态**：可用量 = 仓库级库存 − 已承诺未发量，
  后者由 SalesOrderItem 实时算出（get_committed_quantities），
  **不加 reserved_quantity 字段**——那是三账铁律之外的第四套口径。
- 口径 = status='confirmed'（已审批）且 shipment_status != 'shipped'，
  与 api_sales_order_selectable 的可选订单口径一致；草稿不占用。
- 下单软校验（warning 不阻断）+ 下推硬校验（400 阻断）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

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
from app import (Customer, Material, MaterialCategory, SalesOrder,  # noqa: E402
                 SalesOrderItem, StockTransaction, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """两个仓库 + 客户 + 物料 M-COMMIT（无库位管理，走流水兜底口径）。"""
    db.session.add(User(username="sales", password_hash=generate_password_hash("admin"),
                        role="sales", must_change_password=False))
    wh_a = Warehouse(name="A仓", code="WHA", status="active")
    wh_b = Warehouse(name="B仓", code="WHB", status="active")
    customer = Customer(code="C01", name="客户一")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh_a, wh_b, customer, unit, cat])
    db.session.flush()
    material = Material(code="M-COMMIT", name="承诺测试件", spec="T1", stock=100,
                        min_stock=0, price=1.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh_a": wh_a, "wh_b": wh_b, "customer": customer, "material": material}


def _seed_stock(material, warehouse, quantity):
    """双仓库下 get_warehouse_stock_quantities 按流水聚合（不走单仓回退），
    必须写真实入库流水才能让仓库级库存可见。"""
    db.session.add(StockTransaction(
        material_id=material.id, transaction_type="in", quantity=quantity,
        warehouse_id=warehouse.id, location=warehouse.name,
    ))
    db.session.commit()


def _make_order(material, warehouse, quantity, status, shipped=0, shipment_status="pending"):
    order = SalesOrder(
        order_no=f"SO-{status}-{warehouse.code}-{quantity}-{shipped}",
        customer_id=1, warehouse=warehouse.name, warehouse_id=warehouse.id,
        status=status, shipment_status=shipment_status,
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(SalesOrderItem(sales_order_id=order.id, material_id=material.id,
                                  quantity=quantity, shipped_quantity=shipped, price=1.0))
    db.session.commit()
    return order


def test_t1_confirmed_order_counts_as_committed():
    """T1: confirmed 未发完订单计入占用（库存 100 + 占用 80 → 可用量 20）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh_a"], 100)
        _make_order(seed["material"], seed["wh_a"], 80, "confirmed")
        committed = app_module.get_committed_quantities(seed["wh_a"].id)
        assert committed[seed["material"].id] == 80
        stock = app_module.get_warehouse_stock_quantities(seed["wh_a"]).get(seed["material"].id, 0)
        available = stock - committed.get(seed["material"].id, 0)
        assert available == 20


def test_t2_draft_order_not_committed():
    """T2: 草稿订单不占用（D1：下单是意向，审批才是承诺）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _make_order(seed["material"], seed["wh_a"], 80, "draft")
        assert app_module.get_committed_quantities(seed["wh_a"].id) == {}


def test_t3_exclude_self_for_edit():
    """T3: exclude_sales_order_id 生效——改单不把本单旧量算进占用。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        order = _make_order(seed["material"], seed["wh_a"], 80, "confirmed")
        _make_order(seed["material"], seed["wh_a"], 30, "confirmed")
        assert app_module.get_committed_quantities(seed["wh_a"].id)[seed["material"].id] == 110
        assert app_module.get_committed_quantities(
            seed["wh_a"].id, exclude_sales_order_id=order.id)[seed["material"].id] == 30


def test_t4_shipped_and_partial_exclusion():
    """T4: 发完（shipped）不计入；部分发货只算未发余量。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _make_order(seed["material"], seed["wh_a"], 50, "confirmed",
                    shipped=50, shipment_status="shipped")
        _make_order(seed["material"], seed["wh_a"], 40, "confirmed",
                    shipped=10, shipment_status="partial")
        committed = app_module.get_committed_quantities(seed["wh_a"].id)
        assert committed[seed["material"].id] == 30, "发完的 50 不算，部分发货只算 40-10=30"


def test_t5_warehouse_scope_isolation():
    """T5: 占用按仓库隔离——A 仓占用不影响 B 仓可用量（防 R2 类多仓回归）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _make_order(seed["material"], seed["wh_a"], 80, "confirmed")
        assert app_module.get_committed_quantities(seed["wh_a"].id)[seed["material"].id] == 80
        assert app_module.get_committed_quantities(seed["wh_b"].id) == {}, "B 仓必须有独立占用口径"


def test_get_committed_quantities():
    """A9 同名综合冒烟：confirmed 占用、draft 排除、仓库隔离一次覆盖。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _make_order(seed["material"], seed["wh_a"], 80, "confirmed")
        _make_order(seed["material"], seed["wh_a"], 50, "draft")
        _make_order(seed["material"], seed["wh_b"], 99, "confirmed")
        assert app_module.get_committed_quantities(seed["wh_a"].id) == {seed["material"].id: 80}
        assert app_module.get_committed_quantities(seed["wh_b"].id) == {seed["material"].id: 99}


def test_t6_derived_readonly():
    """T6: 派生函数只读——函数体不得出现 db.session.add/commit。"""
    src = (APP_DIR / "app.py").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^def get_committed_quantities\(", src, re.M)
    assert m, "函数必须存在"
    rest = src[m.start():]
    nm = re.search(r"^def \w+\(", rest[1:], re.M)
    body = rest[:nm.start() + 1] if nm else rest
    assert "db.session.add" not in body
    assert "db.session.commit" not in body


# ─────────────────────────────────────────────────────────────────────
# 路由级：下单/改单软校验（STOCK-TRUTH-P16 改动 2，提示不阻断）
# ─────────────────────────────────────────────────────────────────────

def _make_client(role="sales"):
    with app_module.app.app_context():
        if not User.query.filter_by(username=role).first():
            db.session.add(User(username=role, password_hash=generate_password_hash("admin"),
                                role=role, must_change_password=False))
            db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": role, "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _add_payload(customer_id, warehouse_id, rows):
    return {
        "customer_id": customer_id,
        "warehouse_id": warehouse_id,
        "items": [{"code": code, "quantity": qty, "price": 1.0} for code, qty in rows],
    }


def test_t7_add_returns_warning_not_block():
    """T7: 下单缺口 → 仍 success 但 warnings 含缺口提示（软校验不阻断）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh_a"], 100)
        _make_order(seed["material"], seed["wh_a"], 80, "confirmed")  # 占用 80
        customer_id, wh_id = seed["customer"].id, seed["wh_a"].id
    client = _make_client()
    resp = client.post("/sales/add", json=_add_payload(customer_id, wh_id, [("M-COMMIT", 30)]))
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success", "软校验不得阻断保存"
    assert data["warnings"] and "缺口 10" in data["warnings"][0], data["warnings"]
    assert "M-COMMIT 测试件" in data["warnings"][0] or "承诺测试件" in data["warnings"][0]


def test_t8_frontend_displays_warnings():
    """T8: 前端 save() 消费 warnings——toast 提示 + 展示文本 + 延迟跳转（静态断言）。

    本系统页面层不渲染 flash（仅 login.html 有），提示通道是 JSON -> showToast，
    故对两个表单页的 save() 做静态断言防止后端 warnings 无消费端。
    """
    for tpl in ("sales_order_add.html", "sales_order_edit.html"):
        html = (APP_DIR / "templates" / tpl).read_text(encoding="utf-8", errors="ignore")
        assert "result.warnings" in html, f"{tpl} 必须消费 warnings"
        assert "showToast(result.warnings[0], 'warning'" in html, f"{tpl} 必须 toast 警告"
        assert "库存缺口警告" in html, f"{tpl} 状态区必须展示警告文本"


def test_t9_no_shortage_no_warning():
    """T9: 可用量充足时无警告（不误报）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh_a"], 100)
        customer_id, wh_id = seed["customer"].id, seed["wh_a"].id
    client = _make_client()
    resp = client.post("/sales/add", json=_add_payload(customer_id, wh_id, [("M-COMMIT", 30)]))
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["warnings"] == []


# ─────────────────────────────────────────────────────────────────────
# 路由级：下推硬校验（STOCK-TRUTH-P16 改动 3，作业指令必须拦）
# ─────────────────────────────────────────────────────────────────────

def _confirmed_order_with_stock(seed, warehouse, qty, stock):
    """confirmed 订单 + 仓库级流水库存（下推前置数据）。"""
    _seed_stock(seed["material"], warehouse, stock)
    return _make_order(seed["material"], warehouse, qty, "confirmed")


def test_t10_push_blocked_on_shortage():
    """T10: 下推缺口 → 400 且 msg 含『缺口』（create_sales_outbound_draft）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        order = _confirmed_order_with_stock(seed, seed["wh_a"], 30, stock=100)
        _make_order(seed["material"], seed["wh_a"], 80, "confirmed")  # 他人占用 80
        order_id = order.id
    client = _make_client()
    resp = client.post(f"/sales/{order_id}/create_outbound", json={})
    assert resp.status_code == 400
    msg = resp.get_json().get("msg", "")
    assert "缺口" in msg and "请先补货" in msg, msg
    # 可用量 = 100 - 80 = 20 < 30
    assert "20" in msg and "30" in msg, msg


def test_t11_push_multi_warehouse_isolation():
    """T11: 多仓隔离——A 仓有货 B 仓无货，B 仓订单下推必须拦（防 R2 类回归）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh_a"], 100)  # 只有 A 仓有货
        order_b = _make_order(seed["material"], seed["wh_b"], 10, "confirmed")
        order_b_id = order_b.id
    client = _make_client()
    resp = client.post(f"/sales/{order_b_id}/create_outbound", json={})
    assert resp.status_code == 400, "B 仓无货必须被拦，不得用全局库存蒙混"
    assert "缺口" in resp.get_json().get("msg", "")


def test_t12_push_allowed_when_sufficient():
    """T12: 可用量充足 → 下推成功（不误拦）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        order = _confirmed_order_with_stock(seed, seed["wh_a"], 30, stock=100)
        order_id = order.id
    client = _make_client()
    resp = client.post(f"/sales/{order_id}/create_outbound", json={})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["status"] == "success"


def test_t13_batch_push_skips_shortage():
    """T13: 批量下推——缺口单进 skipped（含库存不足），够量单正常生成。

    用两个物料隔离两张单的判断：ok 单的物料 1 库存充足；short 单的
    物料 2 库存 50 < 下推 90（排除自身后无其他占用，缺口 40）。
    """
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        unit = Unit.query.filter_by(code="GE").first()
        cat = MaterialCategory.query.filter_by(code="WJ").first()
        m2 = Material(code="M-COMMIT-2", name="承诺测试件二", spec="T2", stock=50,
                      min_stock=0, price=1.0, unit_id=unit.id, category_id=cat.id)
        db.session.add(m2)
        db.session.commit()
        _seed_stock(seed["material"], seed["wh_a"], 100)
        _seed_stock(m2, seed["wh_a"], 50)
        ok = _make_order(seed["material"], seed["wh_a"], 10, "confirmed")
        ok_id = ok.id
        short = _make_order(m2, seed["wh_a"], 90, "confirmed")
        short_id = short.id
    client = _make_client()
    resp = client.post("/sales/batch_create_outbound", json={"ids": [ok_id, short_id]})
    data = resp.get_json()
    assert data["status"] == "success"
    assert len(data["created"]) == 1
    assert data["created"][0]["sales_order_no"].startswith("SO-confirmed-WHA-10")
    assert len(data["skipped"]) == 1 and "库存不足" in data["skipped"][0]
    assert "缺口 40" in data["skipped"][0], data["skipped"]


def test_t14_selection_push_blocked_on_shortage():
    """T14: 选单下推缺口 → 400（create_sales_outbound_from_selection）。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh_a"], 20)
        order = _make_order(seed["material"], seed["wh_a"], 30, "confirmed")
        item_id = order.items[0].id
    client = _make_client()
    resp = client.post("/sales/create_outbound_from_selection", json={
        "items": [{"sales_order_item_id": item_id, "quantity": 30}],
    })
    assert resp.status_code == 400
    assert "缺口" in resp.get_json().get("msg", "")
