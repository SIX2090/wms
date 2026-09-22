# -*- coding: utf-8 -*-
"""BUG-2026-09-22-005 回归：批量完成采购退货出库单必须补防超退闸。

根因：单据版 complete_out_order 在 P1-7 已挂 purchase_return_remaining_check
真闸（加锁后整单校验，有来源明细逐行 退货量 ≤ 原采购入库行 quantity −
已退量聚合），但 batch_complete_out_order 只对 '销售出库' 挂了
sales_outbound_remaining_check，'采购退货出库' 漏配——任何绕过保存校验
改大数量的草稿（明细接口直改、开关切换前的存量单、并发窗口内第二张
草稿）经批量完成即超量退货，且批量跳过即放行、无人工复核通道。

覆盖：
- T1 超退草稿在批量完成中被跳过（状态保持 pending、msg 带"可退数量"），
     同批合法草稿正常完成且库存只扣合法单；
- T2 无来源行不受闸门误伤（与单据版语义一致：无来源行跳过校验）。
"""
from __future__ import annotations

import os
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
# BUG-2026-09-19-003：app 导入期按默认 FLASK_ENV=production 执行
# validate_production_security_config，要求显式放行不安全会话 Cookie
# （与 tests/conftest.py、verify_purchase_return_outbound.py 一致）。
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

import datetime  # noqa: E402

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import InOrder, InOrderItem, Material, MaterialCategory, OutOrder, \
    OutOrderItem, Supplier, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """仓库（默认）+ 供应商 + 物料，与 verify_purchase_return_outbound.py 同构。"""
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="批量退货仓", code="WHBC", status="active", is_default=True)
    supplier = Supplier(code="S01", name="退货供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-BCPR", name="批量退货测试件", spec="T1", stock=0,
                        min_stock=0, price=3.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "supplier": supplier, "material": material}


def _seed_stock(material, warehouse, quantity):
    """走 apply_stock_delta 把库存真实写进总账/流水（与生产路径同源）。"""
    from app.services.warehouse_stock_service import apply_stock_delta
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            material, quantity, transaction_type="opening_in",
            reference_type="test_seed", reference_id=0,
            warehouse=warehouse.name, location="")
    assert ok, f"造库存失败：{err}"
    db.session.flush()


def _make_in_order(material, warehouse, quantity):
    """已完成采购入库单一行，返回 (in_order_id, in_order_item_id)。"""
    order = InOrder(order_no=f"IN-BCPR-{datetime.date.today():%m%d}-1",
                    date=datetime.date.today(), business_type="采购入库",
                    supplier_id=1, status="completed", warehouse=warehouse.name)
    db.session.add(order)
    db.session.flush()
    ii = InOrderItem(in_order_id=order.id, material_id=material.id,
                     quantity=quantity, price=3.0, amount=quantity * 3.0)
    db.session.add(ii)
    db.session.commit()
    return order.id, ii.id


def _make_return_draft(order_no, material, warehouse, in_order_id, ii_id, quantity,
                       customer="退货供应商"):
    """DB 直造采购退货出库草稿（绕过保存校验，模拟改大后的草稿/存量单）。

    customer 可定制：异常检测的「重复单据」按 同日+同物料+同客户 匹配，
    测试里两张草稿须用不同客户名，避免误触重复告警（系统既有行为，
    重复检测不看单据状态）。
    """
    order = OutOrder(order_no=order_no, date=datetime.date.today(),
                     business_type="采购退货出库", customer=customer,
                     warehouse=warehouse.name, status="pending",
                     source_in_order_id=in_order_id)
    db.session.add(order)
    db.session.flush()
    db.session.add(OutOrderItem(
        out_order_id=order.id, material_id=material.id,
        source_in_order_item_id=ii_id if ii_id else None,
        quantity=quantity, price=3.0, amount=quantity * 3.0))
    db.session.commit()
    return order.id


def _make_client(role="warehouse"):
    with app_module.app.app_context():
        if not User.query.filter_by(username=role).first():
            db.session.add(User(username=role, password_hash=generate_password_hash("admin"),
                                role=role, must_change_password=False))
            db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": role, "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def test_t1_batch_complete_blocks_over_return():
    """T1（核心）：超退草稿批量完成被跳过，同批合法草稿正常完成。

    场景：入库 10，草稿 A 退 6（合法）、草稿 B 退 11（直造绕过保存校验，
    模拟"保存后改大"）。批量完成必须只放行 A；B 保持 pending 且 msg
    指明"可退数量 10.00"，库存只扣 A 的 6。
    """
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        in_order_id, ii_id = _make_in_order(seed["material"], seed["wh"], 10)
        good_id = _make_return_draft("PR-BC-GOOD", seed["material"], seed["wh"],
                                      in_order_id, ii_id, 6, customer="退货供应商甲")
        bad_id = _make_return_draft("PR-BC-BAD", seed["material"], seed["wh"],
                                    in_order_id, ii_id, 11, customer="退货供应商乙")
        seed_data.update(material_id=seed["material"].id, good_id=good_id, bad_id=bad_id)

    client = _make_client()
    resp = client.post("/out_order/batch_complete",
                       json={"ids": [seed_data["good_id"], seed_data["bad_id"]]})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    assert data["completed"] == 1, f"只应完成 1 张合法草稿，实际 {data}"
    assert "PR-BC-BAD" in data["msg"], f"超退草稿必须出现在跳过名单：{data['msg']}"
    assert "可退数量" in data["msg"], f"跳过原因必须是防超退闸：{data['msg']}"

    with app_module.app.app_context():
        good = db.session.get(OutOrder, seed_data["good_id"])
        bad = db.session.get(OutOrder, seed_data["bad_id"])
        assert good.status == "completed", "合法草稿必须正常完成"
        assert bad.status == "pending", "超退草稿必须保持待审核"
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 44, f"库存只应扣合法单 6（50-6），实际 {stock}"


def test_t2_batch_complete_no_source_rows_not_blocked():
    """T2：无来源行不受闸门误伤（与单据版 purchase_return_remaining_check
    语义一致：无来源行跳过校验，兼容开关关闭期间的历史退货单）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 10)
        # DB 直造无来源草稿（模拟 purchase_return_requires_order 关闭期间的存量单）
        order = OutOrder(order_no="PR-BC-NOSRC", date=datetime.date.today(),
                         business_type="采购退货出库", customer="退货供应商",
                         warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add(OutOrderItem(out_order_id=order.id,
                                    material_id=seed["material"].id,
                                    quantity=2, price=3.0, amount=6.0))
        db.session.commit()
        seed_data.update(order_id=order.id, material_id=seed["material"].id)

    client = _make_client()
    resp = client.post("/out_order/batch_complete",
                       json={"ids": [seed_data["order_id"]]})
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    assert data["completed"] == 1, f"无来源行草稿不应被防超退闸误伤：{data}"

    with app_module.app.app_context():
        order = db.session.get(OutOrder, seed_data["order_id"])
        assert order.status == "completed", "无来源草稿应正常完成"
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 8, f"库存应扣 2（10-2），实际 {stock}"
