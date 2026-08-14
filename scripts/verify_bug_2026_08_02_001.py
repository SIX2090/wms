#!/usr/bin/env python3
"""
BUG-2026-08-02-001 验证：入库单仓库必填且与库位管理无关，未填写时自动取默认仓库。

覆盖：
  1. 前端模板仓库字段为必填并默认带出默认仓库
  2. 后端 add_in_order / update_in_order / complete_in_order /
     update_completed_in_order / batch_complete_in_order 均强制仓库必填
  3. 未填写仓库时自动使用默认仓库；无默认仓库时拒绝保存/完成
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import db  # noqa: E402

flask_app = app_module.app
results = []


def record(checkpoint: str, ok: bool, detail: str) -> None:
    results.append((checkpoint, "PASS" if ok else "FAIL", detail))
    print(f"{'PASS' if ok else 'FAIL'}: {checkpoint} - {detail}")


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


# ============== 静态检查 ==============
in_order_py = read_text("app/routes/in_order.py")
in_order_add_html = read_text("app/templates/in_order_add.html")
in_order_detail_html = read_text("app/templates/in_order_detail.html")

# 1. in_order_add.html 仓库 select 必填且无库位管理条件
record(
    "A1-in_order_add-required",
    'name="warehouse" required' in in_order_add_html,
    "新增页仓库字段带 required",
)
record(
    "A2-in_order_add-no-location-gate",
    "locationManagementEnabled" not in in_order_add_html,
    "新增页 JS 不再用 locationManagementEnabled 控制仓库必填",
)
record(
    "A3-in_order_add-default-selected",
    "default_warehouse" in in_order_add_html,
    "新增页模板支持默认仓库选中",
)

# 2. in_order_detail.html 仓库 select 必填且支持默认仓库
record(
    "B1-in_order_detail-required",
    'name="warehouse" required' in in_order_detail_html,
    "详情页仓库字段带 required",
)
record(
    "B2-in_order_detail-default-selected",
    "default_warehouse" in in_order_detail_html,
    "详情页模板支持默认仓库选中",
)

# 3. app.py 中关键函数均有仓库必填逻辑
required_funcs = [
    "add_in_order",
    "update_in_order",
    "complete_in_order",
    "update_completed_in_order",
    "batch_complete_in_order",
]
for func in required_funcs:
    body = ""
    match = re.search(rf"^    def\s+{re.escape(func)}\s*\([^)]*\):", in_order_py, re.M)
    if match:
        next_match = re.search(r"^    def\s+\w+\s*\(", in_order_py[match.end() :], re.M)
        end = match.end() + next_match.start() if next_match else len(in_order_py)
        body = in_order_py[match.start() : end]
    has_default = "get_default_warehouse()" in body
    has_required = re.search(r"请选择仓库|必须填写仓库|未填写仓库", body) is not None
    record(
        f"C-{func}",
        has_default and has_required,
        f"{func} 含默认仓库逻辑={has_default} 含必填校验={has_required}",
    )


# ============== 动态检查 ==============
flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


def login_client(client):
    with client.session_transaction() as sess:
        sess["_user_id"] = "1"
        sess["_fresh"] = True


def create_test_data():
    from app import Material, Supplier, User, Warehouse

    wh = Warehouse.query.filter_by(name="默认测试仓").first()
    if not wh:
        wh = Warehouse(code="DEFAULT-TEST", name="默认测试仓", status="active", is_default=True)
        db.session.add(wh)
    other_wh = Warehouse.query.filter_by(name="其他测试仓").first()
    if not other_wh:
        other_wh = Warehouse(code="OTHER-TEST", name="其他测试仓", status="active", is_default=False)
        db.session.add(other_wh)

    supplier = Supplier.query.filter_by(name="测试供应商").first()
    if not supplier:
        supplier = Supplier(name="测试供应商", code="TEST-SUP")
        db.session.add(supplier)

    material = Material.query.filter_by(code="TEST-MAT").first()
    if not material:
        material = Material(
            code="TEST-MAT",
            name="测试物料",
            spec="",
            stock=0,
            price=1,
        )
        db.session.add(material)

    user = User.query.filter_by(id=1).first()
    if not user:
        from werkzeug.security import generate_password_hash

        user = User(
            id=1,
            username="testuser",
            password_hash=generate_password_hash("Password123!"),
            role="warehouse",
            status="normal",
        )
        db.session.add(user)

    db.session.commit()
    return wh, other_wh, supplier, material


with flask_app.app_context():
    db.create_all()
    default_wh, other_wh, supplier, material = create_test_data()
    suffix = str(int(time.time()))[-6:]

    client = flask_app.test_client()
    login_client(client)

    # 关闭 prefer_default_warehouse 时无默认仓库应被拒绝
    from app import SystemSetting

    setting = SystemSetting.query.filter_by(key="prefer_default_warehouse").first()
    if not setting:
        setting = SystemSetting(key="prefer_default_warehouse", value="0")
        db.session.add(setting)
    else:
        setting.value = "0"
    db.session.commit()

    rv = client.post(
        "/in_order/add",
        json={
            "order_no": f"IN{suffix}01",
            "date": "2026-08-02",
            "business_type": "采购入库",
            "supplier_id": supplier.id,
            "warehouse": "",
            "items": [
                {"code": material.code, "quantity": 10, "price": 1}
            ],
        },
    )
    record(
        "D1-add-no-default-rejected",
        rv.status_code == 400 and "仓库" in rv.get_json(force=True).get("msg", ""),
        f"无默认仓库且未填仓库时 add_in_order 返回 {rv.status_code}",
    )

    # 开启 prefer_default_warehouse 后未填仓库应自动取默认仓库
    setting.value = "1"
    db.session.commit()
    # 刷新内存缓存（get_system_setting_bool 可能有缓存）
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()

    rv = client.post(
        "/in_order/add",
        json={
            "order_no": f"IN{suffix}02",
            "date": "2026-08-02",
            "business_type": "采购入库",
            "supplier_id": supplier.id,
            "warehouse": "",
            "items": [
                {"code": material.code, "quantity": 10, "price": 1}
            ],
        },
    )
    data = rv.get_json(force=True)
    record(
        "D2-add-default-assigned",
        rv.status_code == 200,
        f"开启默认仓库后 add_in_order 返回 {rv.status_code}, msg={data.get('msg')}",
    )

    # 完成入库单时无仓库自动取默认仓库
    from app import InOrder

    order_no = f"IN{suffix}03"
    order = InOrder(
        order_no=order_no,
        date=date(2026, 8, 2),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse="",
        status="pending",
        operator_id=1,
    )
    db.session.add(order)
    db.session.flush()
    from app import InOrderItem

    item = InOrderItem(
        in_order_id=order.id,
        material_id=material.id,
        quantity=10,
        price=1,
        amount=10,
    )
    db.session.add(item)
    db.session.commit()

    # D3：完成入库单时无仓库自动取默认仓库。
    # 必须传 force=true 跳过异常检测（D2 已建过同供应商+同物料+今日的入库单，
    #  _check_in_order_anomalies 会判定为重复单据并返回 status='warning' 200，
    #  不会执行完成逻辑，warehouse 自然不会被赋值——那不是 BUG-2026-08-02-009 的回归点）。
    db.session.refresh(order)
    rv = client.post(f"/in_order/{order.id}/complete?force=true")
    data = rv.get_json(force=True)
    db.session.refresh(order)
    record(
        "D3-complete-default-assigned",
        rv.status_code == 200 and data.get("status") == "success" and order.warehouse == default_wh.name,
        f"complete_in_order 自动默认仓库={order.warehouse!r}, status={rv.status_code}, resp={data.get('status')}",
    )

    # 批量完成时无仓库自动取默认仓库
    order_no2 = f"IN{suffix}04"
    order2 = InOrder(
        order_no=order_no2,
        date=date(2026, 8, 2),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse="",
        status="pending",
        operator_id=1,
    )
    db.session.add(order2)
    db.session.flush()
    item2 = InOrderItem(
        in_order_id=order2.id,
        material_id=material.id,
        quantity=5,
        price=1,
        amount=5,
    )
    db.session.add(item2)
    db.session.commit()

    rv = client.post("/in_order/batch_complete", json={"ids": [order2.id]})
    data = rv.get_json(force=True)
    db.session.refresh(order2)
    record(
        "D4-batch-complete-default-assigned",
        rv.status_code == 200 and order2.warehouse == default_wh.name,
        f"batch_complete_in_order 自动默认仓库={order2.warehouse!r}, status={rv.status_code}",
    )

    # ---------- D5: complete_in_order 存量无仓库 pending 单据完成时仓库赋值须落库 ----------
    # BUG-2026-08-02-009：锁前赋值被 _acquire_order_write_lock 的 SQLite rollback 丢弃，
    # 导致 order.warehouse 仍为空。修复后赋值移到锁后，应正确落库。
    order_no3 = f"IN{suffix}05"
    order3 = InOrder(
        order_no=order_no3,
        date=date(2026, 8, 2),
        business_type="采购入库",
        supplier_id=supplier.id,
        warehouse="",
        status="pending",
        operator_id=1,
    )
    db.session.add(order3)
    db.session.flush()
    item3 = InOrderItem(
        in_order_id=order3.id,
        material_id=material.id,
        quantity=3,
        price=1,
        amount=3,
    )
    db.session.add(item3)
    db.session.commit()

    rv = client.post(f"/in_order/{order3.id}/complete?force=true")
    db.session.refresh(order3)
    data5 = rv.get_json(force=True)
    record(
        "D5-complete-default-persisted-after-lock",
        rv.status_code == 200 and data5.get("status") == "success" and order3.warehouse == default_wh.name,
        f"complete_in_order 锁后赋值落库={order3.warehouse!r}, status={rv.status_code}, resp={data5.get('status')}",
    )

    # 清理测试数据：先删明细再删头，避免 NOT NULL 外键冲突
    for o in (order, order2, order3):
        for it in list(o.items):
            db.session.delete(it)
    db.session.commit()
    db.session.delete(order3)
    db.session.delete(order2)
    db.session.delete(order)
    # 删除由 add_in_order 创建的入库单
    for o in InOrder.query.filter(InOrder.order_no.in_([f"IN{suffix}01", f"IN{suffix}02"])).all():
        for it in list(o.items):
            db.session.delete(it)
        db.session.delete(o)
    db.session.commit()

failures = [r for r in results if r[1] == "FAIL"]
if failures:
    print(f"\n共 {len(failures)} 项失败")
    raise SystemExit(1)
print("\n全部通过")
raise SystemExit(0)
