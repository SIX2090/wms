# -*- coding: utf-8 -*-
"""P1-7 回归：采购退货出库单（business_type='采购退货出库'）。

根因：采购来的料有质量问题/多到货要退回给供应商时无处落账——走"其他出库"
丢失与原采购入库单的关联（退货率无法统计、供应商对账无据），或不入账
（账实分叉的最大来源）。

方案（与 P1-5 销售退货入库同构，D2 决策：独立单据类型）：
- 复用 OutOrder + business_type='采购退货出库' + customer 字段归属退货供应商；
- OutOrder.source_in_order_id / OutOrderItem.source_in_order_item_id 关联原单；
- 防超退：退货量 ≤ 原采购入库行 quantity − 已退量聚合；
  **已退量是聚合查询不是状态字段**（不在 InOrderItem 上加 returned_quantity，
  防第四套口径，与 P1-5、STOCK-TRUTH-P16 占用账同一决策哲学，
  见 INVENTORY_TRUTH.md §2.1.1）；
- 库存扣减复用 complete_out_order 的 apply_stock_delta 管道
  （总账+流水+库位账三账单点写入口，业务类型无关），不新增库存写入口。

测试覆盖：
- 单测：validate_purchase_return_quantity / purchase_return_remaining_check
- T1  三账一致（总账余额/流水增量/库位账余额）
- T2  流水 warehouse_id 正确归属
- T3  超退在保存阶段被拒
- T4  整单多行独立计限
- T5  完成阶段真闸（并发窗口内两张草稿，后者被聚合口径拦下）
- T6  幂等：重复完成不重复扣库存
- T7  开关关闭时允许无来源
- T8a 开关开启（默认）时无来源被拒
- T8b 退货供应商必填
- T9  非采购退货单不得挂采购入库来源
- T10 列表页 type=purchase_return 别名与列头切换
- T11 新增页采购退货模式渲染
- T12 AI 不参与（高敏动作）
- T13 /api/purchase_in_order/selectable 选源接口
- T14 编辑草稿保留行级来源关联（防重建丢来源）
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
# validate_production_security_config，要求显式放行不安全会话 Cookie。
# 本脚本走内存库 + HTTP，显式 opt-in 以便 app 可导入（与 tests/conftest.py 一致）。
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

import datetime  # noqa: E402

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Customer, InOrder, InOrderItem, LocationInventory, Material,  # noqa: E402
                 MaterialCategory, OutOrder, OutOrderItem, StockTransaction,
                 Supplier, Unit, User, Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    """仓库 + 供应商 + 物料。仓库置为默认（列表页按默认仓库作用域过滤）。"""
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    wh = Warehouse(name="退货出库仓", code="WHP", status="active", is_default=True)
    supplier = Supplier(code="S01", name="退货供应商")
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([wh, supplier, unit, cat])
    db.session.flush()
    material = Material(code="M-PRET", name="采购退货测试件", spec="T1", stock=0,
                        min_stock=0, price=3.0, unit_id=unit.id, category_id=cat.id)
    db.session.add(material)
    db.session.commit()
    return {"wh": wh, "supplier": supplier, "material": material}


_seq = [0]


def order_no_seq():
    _seq[0] += 1
    return f"{_seq[0]:03d}"


def _make_in_order(material, warehouse, rows, status="completed"):
    """采购入库单：rows = [quantity, ...]（同一入库单多行，均同一物料）。

    注意业务上多行同物料罕见，但聚合口径必须对「多行独立计限」正确，
    故 T4 用两条 InOrderItem 覆盖。
    """
    order = InOrder(order_no=f"IN-PRET-{order_no_seq()}", date=datetime.date.today(),
                    business_type="采购入库", supplier_id=1, status=status,
                    warehouse=warehouse.name)
    db.session.add(order)
    db.session.flush()
    items = []
    for quantity in rows:
        ii = InOrderItem(in_order_id=order.id, material_id=material.id,
                         quantity=quantity, price=3.0, amount=quantity * 3.0)
        db.session.add(ii)
        items.append(ii)
    db.session.commit()
    return order, items


def _seed_stock(material, warehouse, quantity, location=""):
    """把库存真实写进三账（总账+流水+库位账），而不是直接改 Material.stock。

    理由：出库完成校验的是**按仓库存**（WarehouseStock），直接改
    Material.stock 只会得到"可用 0.00"的假失败。走 apply_stock_delta
    与生产路径同源，测试才有意义。
    原语内部读 current_user（流水 operator_id），需请求上下文提供匿名用户
    （与 tests/test_p2_3_subcontract_apply_stock_delta.py::_stock_in 同一手法）。
    不在此提交：调用方在同一次 commit 里落库，避免 commit 触发 expire 后
    取到脱离 Session 的实例。
    """
    from app.services.warehouse_stock_service import apply_stock_delta
    with app_module.app.test_request_context():
        ok, err = apply_stock_delta(
            material, quantity, transaction_type="opening_in",
            reference_type="test_seed", reference_id=0,
            warehouse=warehouse.name, location=location)
    assert ok, f"造库存失败：{err}"
    db.session.flush()


def _return_payload(warehouse_name, items, supplier_id=None, source_in_order_id=None,
                    source_in_order_no=None, location="", order_no=None):
    """items = [(material_code, quantity, source_in_order_item_id|None)]"""
    payload = {
        "order_no": order_no or f"PR-RET-{order_no_seq()}",
        "business_type": "采购退货出库",
        "date": "2026-09-11",
        "warehouse": warehouse_name,
        "location": location,
        "items": [
            {"code": code, "quantity": qty, "price": 3.0,
             **({"source_in_order_item_id": sid} if sid else {})}
            for code, qty, sid in items
        ],
    }
    if supplier_id is not None:
        payload["customer"] = "退货供应商"
    if source_in_order_id is not None:
        payload["source_in_order_id"] = source_in_order_id
    if source_in_order_no is not None:
        payload["source_in_order_no"] = source_in_order_no
    return payload


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


def _set_setting(key, value):
    from app import SystemSetting
    row = SystemSetting.query.filter_by(key=key).first()
    if row:
        row.value = value
    else:
        db.session.add(SystemSetting(key=key, value=value))
    db.session.commit()


def test_purchase_return_requires_order():
    """A9 同名：开关读取——默认开；系统设置写 0 即关闭。

    该开关决定「采购退货是否必须关联来源采购入库单」。
    """
    with app_module.app.app_context():
        _reset_db()
        _seed_base()
        # 未配置 → 默认开
        assert app_module.purchase_return_requires_order() is True
        _set_setting("purchase_return_requires_order", "0")
        assert app_module.purchase_return_requires_order() is False
        _set_setting("purchase_return_requires_order", "1")
        assert app_module.purchase_return_requires_order() is True


def test_validate_purchase_return_quantity():
    """行级限额 = 原入库行 quantity − 已退聚合；超退拒绝。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_in_order(seed["material"], seed["wh"], [10])
        ii = items[0]
        # 无已退：可退 10
        ok, _ = app_module.validate_purchase_return_quantity(ii, 10)
        assert ok
        ok, msg = app_module.validate_purchase_return_quantity(ii, 10.01)
        assert not ok and "可退数量 10.00" in msg
        # 造一张已完成退货单（回填 4），可退变 6
        order = OutOrder(order_no="PR-SEED-1", date=datetime.date.today(),
                         business_type="采购退货出库", customer="退货供应商",
                         warehouse=seed["wh"].name, status="completed",
                         source_in_order_id=ii.in_order_id)
        db.session.add(order)
        db.session.flush()
        db.session.add(app_module.OutOrderItem(
            out_order_id=order.id, material_id=seed["material"].id,
            source_in_order_item_id=ii.id, quantity=4, price=3.0, amount=12.0))
        db.session.commit()
        ok, _ = app_module.validate_purchase_return_quantity(ii, 6)
        assert ok, "已退 4 后应可退 6"
        ok, msg = app_module.validate_purchase_return_quantity(ii, 6.01)
        assert not ok and "可退数量 6.00" in msg


def test_purchase_return_remaining_check():
    """整单校验：多行独立计限、无来源行跳过、原行不存在跳过。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_in_order(seed["material"], seed["wh"], [10, 5])
        order = OutOrder(order_no="PR-SEED-2", date=datetime.date.today(),
                         business_type="采购退货出库", customer="退货供应商",
                         warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add_all([
            app_module.OutOrderItem(out_order_id=order.id, material_id=seed["material"].id,
                                    source_in_order_item_id=items[0].id,
                                    quantity=10, price=3.0, amount=30.0),
            app_module.OutOrderItem(out_order_id=order.id, material_id=seed["material"].id,
                                    quantity=3, price=3.0, amount=9.0),  # 无来源
        ])
        db.session.commit()
        ok, msg = app_module.purchase_return_remaining_check(order)
        assert ok, f"行1 退 10（=入库量）+ 无来源行 3 都应放行：{msg}"
        # 行1 超 1 → 整单拒绝
        order.items[0].quantity = 11
        db.session.commit()
        ok, msg = app_module.purchase_return_remaining_check(order)
        assert not ok and "可退数量 10.00" in msg


def test_t1_three_ledgers_consistent():
    """T1（核心）：退货完成走 complete_out_order 的 apply_stock_delta 管道 → 三账增量一致。

    开启库位管理（location_management_enabled='1'）以覆盖库位账写入口：
    关闭时库位账不写是设计行为（INVENTORY_TRUTH §2.1 ③→① 兜底口径）。
    注意出库方向：delta 为负，故三账增量同为 -8。
    """
    from app import SystemSetting
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        _set_setting("location_management_enabled", "1")
        seed = _seed_base()
        # 先造库存（模拟已入库 20，退货 8 后剩 12）；库位须与后续退货行一致
        _seed_stock(seed["material"], seed["wh"], 20, location="PRT-01")
        _, items = _make_in_order(seed["material"], seed["wh"], [8])
        seed_data.update(material_id=seed["material"].id, wh_id=seed["wh"].id,
                         wh_name=seed["wh"].name, supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["wh_name"],
                              [("M-PRET", 8, seed_data["ii_id"])],
                              supplier_id=seed_data["supplier_id"],
                              source_in_order_id=seed_data["in_order_id"],
                              location="PRT-01")
    resp = client.post("/out_order/add", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    data = resp.get_json()
    assert data["status"] == "success", data
    order_id = data["id"]

    resp = client.post(f"/out_order/{order_id}/complete")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]

    with app_module.app.app_context():
        material = db.session.get(Material, seed_data["material_id"])
        stock_after = material.stock
        txn_qty = db.session.query(
            db.func.coalesce(db.func.sum(StockTransaction.quantity), 0)
        ).filter_by(material_id=material.id, transaction_type="out",
                    reference_type="out_order", reference_id=order_id).scalar()
        loc_qty = db.session.query(
            db.func.coalesce(db.func.sum(LocationInventory.quantity), 0)
        ).filter_by(material_id=material.id, warehouse_id=seed_data["wh_id"]).scalar()
        # 三账各自口径：
        #   ① 总账 Material.stock —— 余额，20-8=12
        #   ③ 流水 StockTransaction.quantity —— 有符号增量，本单 -8
        #   ② 库位账 LocationInventory.quantity —— 余额，20-8=12
        assert stock_after == 12, f"总账余额应为 12（20-8），实际 {stock_after}"
        assert float(txn_qty) == -8, f"本单流水增量应为 -8，实际 {txn_qty}"
        assert float(loc_qty) == 12, f"库位账余额应为 12（20-8），实际 {loc_qty}"
        order = db.session.get(OutOrder, order_id)
        assert order.source_in_order_id is not None, "单头必须聚合来源采购入库单"
        assert order.source_in_order_no.startswith("IN-PRET-"), "冗余单号必须回填"
        assert order.business_type == "采购退货出库"


def test_t2_stock_txn_warehouse_id():
    """T2：退货流水 warehouse_id 必须正确归属（INVENTORY_TRUTH §3 铁律）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        _, items = _make_in_order(seed["material"], seed["wh"], [5])
        seed_data.update(material_id=seed["material"].id, wh_id=seed["wh"].id,
                         wh_name=seed["wh"].name, supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["wh_name"],
                              [("M-PRET", 5, seed_data["ii_id"])],
                              supplier_id=seed_data["supplier_id"],
                              source_in_order_id=seed_data["in_order_id"])
    resp = client.post("/out_order/add", json=payload)
    order_id = resp.get_json()["id"]
    client.post(f"/out_order/{order_id}/complete")

    with app_module.app.app_context():
        txn = StockTransaction.query.filter_by(
            material_id=seed_data["material_id"], reference_type="out_order",
            reference_id=order_id).first()
        assert txn is not None, "采购退货必须产生库存流水"
        assert txn.warehouse_id == seed_data["wh_id"], \
            f"流水必须归属退货仓库，实际 warehouse_id={txn.warehouse_id}"


def test_t3_over_return_rejected_on_save():
    """T3：保存阶段超退即被拦（validate_purchase_return_quantity 行级校验）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        _, items = _make_in_order(seed["material"], seed["wh"], [5])
        seed_data.update(wh_name=seed["wh"].name, supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["wh_name"],
                              [("M-PRET", 6, seed_data["ii_id"])],
                              supplier_id=seed_data["supplier_id"],
                              source_in_order_id=seed_data["in_order_id"])
    resp = client.post("/out_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error", "保存阶段必须拦超退"
    assert "可退数量 5.00" in data.get("msg", ""), data


def test_t4_multi_row_independent():
    """T4：一张采购入库单多行退货，各行独立计限。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _, items = _make_in_order(seed["material"], seed["wh"], [10, 4])
        order = OutOrder(order_no="PR-SEED-3", date=datetime.date.today(),
                         business_type="采购退货出库", customer="退货供应商",
                         warehouse=seed["wh"].name, status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add_all([
            app_module.OutOrderItem(out_order_id=order.id, material_id=seed["material"].id,
                                    source_in_order_item_id=items[0].id,
                                    quantity=10, price=3.0, amount=30.0),
            app_module.OutOrderItem(out_order_id=order.id, material_id=seed["material"].id,
                                    source_in_order_item_id=items[1].id,
                                    quantity=4, price=3.0, amount=12.0),
        ])
        db.session.commit()
        ok, msg = app_module.purchase_return_remaining_check(order)
        assert ok, f"行1 退满 10、行2 退满 4 各自独立，应放行：{msg}"
        # 行2 超 1 → 只报行2
        order.items[1].quantity = 5
        db.session.commit()
        ok, msg = app_module.purchase_return_remaining_check(order)
        assert not ok and "可退数量 4.00" in msg


def test_t5_over_return_rejected_on_complete():
    """T5：完成阶段真闸——两张草稿在「都还没完成」时各自保存成功，随后先后完成，
    第二张完成时必须被聚合口径拦下。

    这是真实并发场景的最小复现：并发窗口内两张草稿的保存校验都看到"已退 0"，
    各自放行；裁决权必须落在完成时的加锁 + 聚合校验上，否则会退超。
    """
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 50)
        _, items = _make_in_order(seed["material"], seed["wh"], [10])
        seed_data.update(material_id=seed["material"].id, wh_id=seed["wh"].id,
                         wh_name=seed["wh"].name, supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    # 两张草稿：都在"已退 0"的窗口内保存，均应成功
    drafts = []
    for _ in range(2):
        p = _return_payload(seed_data["wh_name"], [("M-PRET", 10, seed_data["ii_id"])],
                            supplier_id=seed_data["supplier_id"],
                            source_in_order_id=seed_data["in_order_id"])
        d = client.post("/out_order/add", json=p).get_json()
        assert d["status"] == "success", f"窗口内保存必须放行：{d}"
        drafts.append(d["id"])

    # 第一张完成：占满可退量
    r1 = client.post(f"/out_order/{drafts[0]}/complete")
    assert r1.status_code == 200, r1.get_data(as_text=True)[:200]
    # 第二张完成：已退量聚合为 10 → 可退 0 → 必须被拒
    r2 = client.post(f"/out_order/{drafts[1]}/complete")
    d2c = r2.get_json()
    assert d2c["status"] == "error", f"第二张超退必须被拒，实际 {d2c}"
    assert "可退数量 0.00" in d2c.get("msg", ""), d2c

    with app_module.app.app_context():
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 40, f"只应扣一次 10，总账应为 40，实际 {stock}"


def test_t6_duplicate_complete_idempotent():
    """T6：重复提交完成 → 第二次被幂等锁拒绝（不重复扣库存）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 30)
        _, items = _make_in_order(seed["material"], seed["wh"], [3])
        seed_data.update(material_id=seed["material"].id, wh_name=seed["wh"].name,
                         supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["wh_name"], [("M-PRET", 3, seed_data["ii_id"])],
                              supplier_id=seed_data["supplier_id"],
                              source_in_order_id=seed_data["in_order_id"])
    resp = client.post("/out_order/add", json=payload)
    order_id = resp.get_json()["id"]
    r1 = client.post(f"/out_order/{order_id}/complete")
    assert r1.status_code == 200, r1.get_data(as_text=True)[:200]
    r2 = client.post(f"/out_order/{order_id}/complete")
    data2 = r2.get_json()
    assert data2["status"] == "error", "第二次完成必须被拒"

    with app_module.app.app_context():
        stock = db.session.get(Material, seed_data["material_id"]).stock
        assert stock == 27, f"重复提交不得重复扣库存，总账应为 27，实际 {stock}"


def test_t7_switch_off_allows_no_source():
    """T7：开关 purchase_return_requires_order 关闭时，允许无来源的历史退货。"""
    seed_data = {}
    client = _make_client()

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 10)
        seed_data.update(wh_name=seed["wh"].name, supplier_id=seed["supplier"].id)
        _set_setting("purchase_return_requires_order", "0")
        assert app_module.purchase_return_requires_order() is False

    payload = _return_payload(seed_data["wh_name"], [("M-PRET", 2, None)],
                              supplier_id=seed_data["supplier_id"])
    resp = client.post("/out_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "success", data
    order_id = data["id"]

    with app_module.app.app_context():
        order = db.session.get(OutOrder, order_id)
        assert order.business_type == "采购退货出库"
        assert order.source_in_order_id is None, "无来源不得猜归属"


def test_t8_switch_on_requires_source():
    """T8a：开关开启（默认）时，无来源采购退货必须被拒。"""
    seed_data = {}
    client = _make_client()

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 10)
        seed_data.update(wh_name=seed["wh"].name, supplier_id=seed["supplier"].id)
        _set_setting("purchase_return_requires_order", "1")
        assert app_module.purchase_return_requires_order() is True

    payload = _return_payload(seed_data["wh_name"], [("M-PRET", 2, None)],
                              supplier_id=seed_data["supplier_id"])
    resp = client.post("/out_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error", data
    assert "必须关联来源采购入库单" in data.get("msg", ""), data


def test_t8b_supplier_required():
    """T8b：采购退货出库必须选择退货供应商。"""
    seed_data = {}
    client = _make_client()

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 10)
        seed_data.update(wh_name=seed["wh"].name)

    payload = _return_payload(seed_data["wh_name"], [("M-PRET", 2, None)])
    payload.pop("customer", None)
    resp = client.post("/out_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error" and "退货供应商" in data.get("msg", ""), data


def test_t9_source_from_other_business_type_rejected():
    """T9：非采购退货出库单不得挂采购入库来源（防串类型污染聚合口径）。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        db.session.add(Customer(code="C01", name="某客户"))
        _seed_stock(seed["material"], seed["wh"], 50)
        _, items = _make_in_order(seed["material"], seed["wh"], [5])
        seed_data.update(wh_name=seed["wh"].name, ii_id=items[0].id)

    client = _make_client()
    # 领料单（默认业务类型）带 source_in_order_item_id → 必须拒绝
    payload = {
        "order_no": f"OUT-BAD-{order_no_seq()}",
        "business_type": "领料单",
        "date": "2026-09-11",
        "warehouse": seed_data["wh_name"],
        "department_id": "",
        "items": [{"code": "M-PRET", "quantity": 1, "price": 3.0,
                   "source_in_order_item_id": seed_data["ii_id"]}],
    }
    # 领料单要求部门，先造一个部门并填 id，确保拦在来源校验而非前置必填
    with app_module.app.app_context():
        from app import Department
        dept = Department(code="D01", name="生产部", status="active")
        db.session.add(dept)
        db.session.commit()
        payload["department_id"] = dept.id

    resp = client.post("/out_order/add", json=payload)
    data = resp.get_json()
    assert data["status"] == "error", data
    assert "仅采购退货出库单可关联采购入库来源" in data.get("msg", ""), data


def test_t10_list_type_alias_purchase_return():
    """T10：列表页 type=purchase_return 别名可定位到采购退货出库单。

    列表按明细行展开（一个单据几条明细渲染几行），故造单必须带明细。
    """
    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        pr_order = OutOrder(order_no="PR-LIST-1", date=datetime.date.today(),
                            business_type="采购退货出库", customer="退货供应商",
                            warehouse=seed["wh"].name, status="pending")
        other_order = OutOrder(order_no="OUT-LIST-1", date=datetime.date.today(),
                               business_type="领料单", warehouse=seed["wh"].name, status="pending")
        db.session.add_all([pr_order, other_order])
        db.session.flush()
        db.session.add_all([
            app_module.OutOrderItem(out_order_id=pr_order.id, material_id=seed["material"].id,
                                    quantity=1, price=3.0, amount=3.0),
            app_module.OutOrderItem(out_order_id=other_order.id, material_id=seed["material"].id,
                                    quantity=1, price=3.0, amount=3.0),
        ])
        db.session.commit()

    client = _make_client()
    resp = client.get("/out_order?type=purchase_return")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
    html = resp.get_data(as_text=True)
    assert "PR-LIST-1" in html, "type=purchase_return 必须能查到采购退货出库单"
    assert "OUT-LIST-1" not in html, "不得混入领料单"
    assert "采购退货出库明细表" in html, "页面标题必须随业务类型切换"
    assert "退货供应商" in html, "列表列头必须改为退货供应商"
    assert "退货出库单号" in html, "列表列头必须改为退货出库单号"
    assert "/out_order/add?type=purchase_return" in html, "新增按钮必须指向采购退货入口"
    # 默认列表（不传 type）不得混入采购退货出库
    default_html = client.get("/out_order").get_data(as_text=True)
    assert "PR-LIST-1" not in default_html, "默认领料明细表不得混入采购退货出库单"
    assert "OUT-LIST-1" in default_html, "默认列表应展示领料单"


def test_t11_add_page_purchase_return_mode():
    """T11：GET /out_order/add?type=purchase_return 渲染采购退货出库模式。"""
    with app_module.app.app_context():
        _reset_db()
        _seed_base()
    client = _make_client()
    resp = client.get("/out_order/add?type=purchase_return")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    html = resp.get_data(as_text=True)
    assert "新增采购退货出库单" in html, "页面标题必须是采购退货出库单"
    assert "退货供应商" in html, "往来方标签必须是退货供应商"
    assert 'id="sourceInOrderNo"' in html, "必须渲染来源采购入库单号输入框"
    assert 'value="采购退货出库" selected' in html, "业务类型下拉必须默认选中采购退货出库"


def test_t12_no_ai_capability_registered():
    """T12：退货是高敏动作，AI 不参与——能力键台账不得含采购退货。

    镜像 P1-5 T5：AI 不得自动代执行退货出库（资金/物权流出不可逆）。
    """
    ledger = (ROOT / "app" / "ai" / "policies.py").read_text(encoding="utf-8", errors="ignore")
    assert "采购退货" not in ledger, "AI 能力键不得覆盖采购退货（高敏动作人工执行）"


def test_t13_in_order_selectable_api():
    """T13：/api/purchase_in_order/selectable 只返回已完成采购入库单，且带可退量。"""
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        done_order, done_items = _make_in_order(seed["material"], seed["wh"], [10], status="completed")
        # 立即取出标量：_make_in_order 内部 commit 会 expire 实例，
        # 跨 context 再读属性会 DetachedInstanceError。
        done_id, done_no, ii_id = done_order.id, done_order.order_no, done_items[0].id
        material_id = seed["material"].id
        wh_name = seed["wh"].name
        _make_in_order(seed["material"], seed["wh"], [7], status="pending")

    client = _make_client()
    resp = client.get("/api/purchase_in_order/selectable")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:200]
    data = resp.get_json()
    assert data["status"] == "success", data
    nos = [o["order_no"] for o in data["orders"]]
    assert done_no in nos, "必须返回已完成的采购入库单"
    assert len(nos) == 1, f"未完成的入库单不得出现，实际 {nos}"
    item = data["items"][0]
    assert item["remaining_quantity"] == 10, f"可退量应为 10，实际 {item['remaining_quantity']}"
    assert item["supplier_name"] == "退货供应商", "必须带供应商名（供前端按供应商排序）"

    # 造一张已完成退货 4，可退量应降为 6
    with app_module.app.app_context():
        order = OutOrder(order_no="PR-API-1", date=datetime.date.today(),
                         business_type="采购退货出库", customer="退货供应商",
                         warehouse=wh_name, status="completed",
                         source_in_order_id=done_id)
        db.session.add(order)
        db.session.flush()
        db.session.add(app_module.OutOrderItem(
            out_order_id=order.id, material_id=material_id,
            source_in_order_item_id=ii_id, quantity=4, price=3.0, amount=12.0))
        db.session.commit()

    data = client.get("/api/purchase_in_order/selectable").get_json()
    assert data["items"][0]["remaining_quantity"] == 6, \
        f"已退 4 后可退量应为 6，实际 {data['items'][0]['remaining_quantity']}"


def test_t14_edit_draft_preserves_source_link():
    """T14：编辑草稿重建明细后，行级来源采购入库明细必须保留。

    这是 P1-5 SALES-AUDIT-005 的同构风险点：add_out_order 是「先删光明细再重建」，
    若前端不回填 source_in_order_item_id，重建后来源关联丢失、防超退闸形同虚设。
    本用例走完整闭环：建草稿 → 打开编辑页（断言回填）→ 原样重存 → 断言来源未丢。
    """
    seed_data = {}

    with app_module.app.app_context():
        _reset_db()
        seed = _seed_base()
        _seed_stock(seed["material"], seed["wh"], 20)
        _, items = _make_in_order(seed["material"], seed["wh"], [10])
        seed_data.update(wh_name=seed["wh"].name, supplier_id=seed["supplier"].id,
                         in_order_id=items[0].in_order_id, ii_id=items[0].id)

    client = _make_client()
    payload = _return_payload(seed_data["wh_name"], [("M-PRET", 4, seed_data["ii_id"])],
                              supplier_id=seed_data["supplier_id"],
                              source_in_order_id=seed_data["in_order_id"])
    d = client.post("/out_order/add", json=payload).get_json()
    assert d["status"] == "success", d
    order_id = d["id"]

    with app_module.app.app_context():
        item = OutOrderItem.query.filter_by(out_order_id=order_id).first()
        assert item.source_in_order_item_id == seed_data["ii_id"], "建单后行级来源必须落库"

    # 打开编辑页：来源单号与行级来源都应回填到页面（供前端原样回传）
    html = client.get(f"/out_order/add?order_id={order_id}").get_data(as_text=True)
    assert "新增采购退货出库单" in html, "编辑页也必须处于采购退货模式"
    assert "IN-PRET-" in html, "来源采购入库单号必须回填"
    assert str(seed_data["ii_id"]) in html, "行级来源采购入库明细必须回填到 edit_items"

    # 原样重存（模拟用户打开草稿后直接保存）
    payload2 = dict(payload)
    payload2["order_id"] = order_id
    payload2["order_no"] = "PR-RET-EDIT"
    d2 = client.post("/out_order/add", json=payload2).get_json()
    assert d2["status"] == "success", d2

    with app_module.app.app_context():
        item = OutOrderItem.query.filter_by(out_order_id=order_id).first()
        assert item.source_in_order_item_id == seed_data["ii_id"], \
            "编辑重存后行级来源必须保留（否则防超退闸失效）"
        order = db.session.get(OutOrder, order_id)
        assert order.source_in_order_id == seed_data["in_order_id"], "单头来源必须保留"
