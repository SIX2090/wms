# -*- coding: utf-8 -*-
"""BUG-2026-09-22-014 补全轮：R6 收敛遗漏点 + 写侧规范化。

评审 BUG-2026-09-22-014 首轮修复时发现三处不完整：
1. R6 收敛遗漏 5 处单边匹配：adjustment 列表/导出、check 列表/导出、
   手机端首页 dashboard（/api/mobile/dashboard）今日进出统计；
2. 首轮根因叙述不准——移动端 inbound 早已规范化为仓库名（order_warehouse =
   warehouse.name），真正写入源头是 Web JSON/表单 API 原文落库
   （in_order add/update 的 order.warehouse = 客户端原文）；
3. 只修读侧没修写侧：原文落库不堵，新数据会继续混写（编码/名称/大小写变体）。

本轮断言：
  T1 手机端 dashboard：编码写法的入库单计入今日入库统计（不丢数）
  T2 调整单列表：编码写法的调整单按仓库可查
  T3 盘点单列表：编码写法的盘点单按仓库可查
  T4 写侧规范化：POST /in_order/add 传仓库编码，落库为规范化仓库名
  T5 写侧拒绝：POST /in_order/add 传未知仓库，400 拒绝且不产生单据
"""
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import (  # noqa: E402
    db,
    AdjustmentOrder,
    InOrder,
    InOrderItem,
    InventoryCheck,
    Material,
    MaterialCategory,
    Supplier,
    Unit,
    User,
    Warehouse,
    _warehouse_document_match_clause,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed():
    db.drop_all()
    db.create_all()
    unit = Unit(name="个", code="PCS")
    category = MaterialCategory(name="默认分类", code="DEFAULT")
    supplier = Supplier(name="供应商A", code="SUP-A")
    wh = Warehouse(name="测试主仓", code="WH-TEST", status="active")
    user = User(username="wh_review_admin", role="admin",
                status="normal", must_change_password=False,
                password_hash=generate_password_hash("admin"))
    material = Material(code="M001", name="轴承", spec="6204", stock=0,
                        price=10, unit_id=unit.id, category_id=category.id)
    db.session.add_all([unit, category, supplier, wh, user, material])
    db.session.commit()
    return wh, material, supplier


def _login(client):
    resp = client.post("/login",
                       data={"username": "wh_review_admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code in (200, 302)


def test_t1_mobile_dashboard_counts_code_written_inbound():
    """T1：编码写法的入库单必须计入手机端首页今日入库统计。"""
    with app_module.app.app_context():
        wh, material, supplier = _seed()
        order = InOrder(order_no="IN-CODE", date=date.today(),
                        supplier_id=supplier.id, business_type="采购入库",
                        warehouse=wh.code,          # ← 编码写法
                        status="completed", total_amount=50)
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                                   quantity=5, price=10, amount=50))
        db.session.commit()

        client = app_module.app.test_client()
        _login(client)
        resp = client.get(f"/api/mobile/dashboard?warehouse_id={wh.id}")
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        body = resp.get_json()
        payload = body.get("data") or body
        today_in = (payload.get("today_inbound_quantity")
                    or payload.get("today_in_quantity")
                    or payload.get("today_in") or 0)
        assert float(today_in) == 5.0, (
            f"编码写法的入库单未计入 dashboard，实际 today_in={today_in}, "
            f"keys={sorted(payload.keys())[:12]}"
        )


def test_t2_adjustment_list_matches_code_written():
    """T2：编码写法的调整单按仓库可查（读侧双匹配）。"""
    with app_module.app.app_context():
        wh, material, _ = _seed()
        db.session.add(AdjustmentOrder(
            adjustment_no="ADJ-CODE", date=date.today(),
            warehouse=wh.code, status="completed", adjustment_type="surplus"))
        db.session.commit()
        clause = _warehouse_document_match_clause(AdjustmentOrder.warehouse, wh)
        found = AdjustmentOrder.query.filter(clause).all()
        assert [a.adjustment_no for a in found] == ["ADJ-CODE"], (
            f"编码写法的调整单查不到，实际={found}"
        )


def test_t3_check_list_matches_code_written():
    """T3：编码写法的盘点单按仓库可查（读侧双匹配）。"""
    with app_module.app.app_context():
        wh, material, _ = _seed()
        db.session.add(InventoryCheck(
            check_no="CHK-CODE", date=date.today(),
            warehouse=wh.code, status="pending"))
        db.session.commit()
        clause = _warehouse_document_match_clause(InventoryCheck.warehouse, wh)
        found = InventoryCheck.query.filter(clause).all()
        assert [c.check_no for c in found] == ["CHK-CODE"], (
            f"编码写法的盘点单查不到，实际={found}"
        )


def test_t4_write_side_normalizes_code_to_name():
    """T4：传仓库编码建单，落库必须是规范化仓库名。"""
    with app_module.app.app_context():
        wh, material, supplier = _seed()
        client = app_module.app.test_client()
        _login(client)
        resp = client.post("/in_order/add", json={
            "business_type": "采购入库",
            "supplier_id": supplier.id,
            "warehouse": "WH-TEST",             # ← 编码输入
            "items": [{"code": "M001", "quantity": 5, "price": 10}],
        })
        body = resp.get_json()
        assert body["status"] == "success", body
        stored = InOrder.query.get(body["id"])
        assert stored.warehouse == "测试主仓", (
            f"落库未规范化，实际 warehouse={stored.warehouse!r}"
        )


def test_t5_write_side_rejects_unknown_warehouse():
    """T5：传未知仓库直接 400 拒绝，且不产生单据。"""
    with app_module.app.app_context():
        wh, material, supplier = _seed()
        before = InOrder.query.count()
        client = app_module.app.test_client()
        _login(client)
        resp = client.post("/in_order/add", json={
            "business_type": "采购入库",
            "supplier_id": supplier.id,
            "warehouse": "不存在的仓库XYZ",
            "items": [{"code": "M001", "quantity": 5, "price": 10}],
        })
        assert resp.status_code == 400, resp.get_data(as_text=True)[:300]
        assert InOrder.query.count() == before, "未知仓库不应产生单据"


def test_t6_write_side_accepts_name_unchanged():
    """T6：传仓库名建单行为不回归（仍成功且落库为仓库名）。"""
    with app_module.app.app_context():
        wh, material, supplier = _seed()
        client = app_module.app.test_client()
        _login(client)
        resp = client.post("/in_order/add", json={
            "business_type": "采购入库",
            "supplier_id": supplier.id,
            "warehouse": "测试主仓",              # ← 名称输入
            "items": [{"code": "M001", "quantity": 5, "price": 10}],
        })
        body = resp.get_json()
        assert body["status"] == "success", body
        stored = InOrder.query.get(body["id"])
        assert stored.warehouse == "测试主仓"
