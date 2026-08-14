#!/usr/bin/env python3
"""
BUG-2026-08-02-002 ~ 008 验证：出库单与售后出库单仓库必填且与库位管理无关，
未填写时自动取默认仓库。

覆盖修复：
  - BUG-002 add_out_order 领料/其他出库仓库必填
  - BUG-003 complete_out_order 无条件仓库必填
  - BUG-004 batch_complete_out_order 仓库校验
  - BUG-005 add_after_sale_out_order 仓库字段
  - BUG-006 complete_after_sale_out_order 仓库校验
  - BUG-007 售后出库前端仓库字段
  - BUG-008 出库单前端仓库 required
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


def extract_function_body(source: str, func_name: str) -> str:
    # 路由函数已迁移到 register_*_routes(app) 内，缩进 4 空格。
    match = re.search(rf"^    def\s+{re.escape(func_name)}\s*\([^)]*\):", source, re.M)
    if not match:
        return ""
    next_match = re.search(r"^    def\s+\w+\s*\(", source[match.end():], re.M)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start():end]


# ============== 静态检查 ==============
out_order_py = read_text("app/routes/out_order.py")
after_sale_out_py = read_text("app/routes/after_sale_out.py")
out_order_add_html = read_text("app/templates/out_order_add.html")
after_sale_out_add_html = read_text("app/templates/after_sale_out_add.html")

# 1. out_order_add.html 仓库 select 必填
record(
    "A1-out_order_add-required",
    'name="warehouse" required' in out_order_add_html,
    "出库新增页仓库字段带 required",
)
record(
    "A2-out_order_add-default-selected",
    "default_warehouse" in out_order_add_html,
    "出库新增页模板支持默认仓库选中",
)

# 2. after_sale_out_add.html 仓库 select 必填
record(
    "B1-after_sale_out_add-required",
    'name="warehouse" required' in after_sale_out_add_html,
    "售后出库新增页仓库字段带 required",
)
record(
    "B2-after_sale_out_add-default-selected",
    "default_warehouse" in after_sale_out_add_html,
    "售后出库新增页模板支持默认仓库选中",
)

# 3. 关键函数均含默认仓库逻辑 + 必填校验（函数已迁移到 out_order / after_sale_out 路由模块）
out_funcs = [
    "add_out_order",
    "complete_out_order",
    "batch_complete_out_order",
]
for func in out_funcs:
    body = extract_function_body(out_order_py, func)
    has_default = "get_default_warehouse()" in body
    has_required = re.search(r"请选择仓库|未填写仓库", body) is not None
    record(
        f"C-{func}",
        has_default and has_required,
        f"{func} 含默认仓库逻辑={has_default} 含必填校验={has_required}",
    )

after_sale_funcs = [
    "add_after_sale_out_order",
    "complete_after_sale_out_order",
]
for func in after_sale_funcs:
    body = extract_function_body(after_sale_out_py, func)
    has_default = "get_default_warehouse()" in body
    has_required = re.search(r"请选择仓库|未填写仓库", body) is not None
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
    from app import AfterSaleOutOrder, Material, OutOrder, OutOrderItem, User, Warehouse

    wh = Warehouse.query.filter_by(name="默认测试仓").first()
    if not wh:
        wh = Warehouse(code="DEFAULT-TEST", name="默认测试仓", status="active", is_default=True)
        db.session.add(wh)
    other_wh = Warehouse.query.filter_by(name="其他测试仓").first()
    if not other_wh:
        other_wh = Warehouse(code="OTHER-TEST", name="其他测试仓", status="active", is_default=False)
        db.session.add(other_wh)

    material = Material.query.filter_by(code="TEST-MAT").first()
    if not material:
        material = Material(
            code="TEST-MAT",
            name="测试物料",
            spec="",
            stock=1000,
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
    return wh, other_wh, material


def set_prefer_default_warehouse(value: str):
    from app import SystemSetting

    setting = SystemSetting.query.filter_by(key="prefer_default_warehouse").first()
    if not setting:
        setting = SystemSetting(key="prefer_default_warehouse", value=value)
        db.session.add(setting)
    else:
        setting.value = value
    db.session.commit()
    if hasattr(app_module, "_system_setting_cache"):
        app_module._system_setting_cache.clear()


with flask_app.app_context():
    db.create_all()
    default_wh, other_wh, material = create_test_data()
    suffix = str(int(time.time()))[-6:]

    client = flask_app.test_client()
    login_client(client)

    # ---------- D1: add_out_order 关闭默认仓库 + 空仓库 → 400 ----------
    set_prefer_default_warehouse("0")
    rv = client.post(
        "/out_order/add",
        json={
            "order_no": f"OUT{suffix}01",
            "date": "2026-08-02",
            "business_type": "领料单",
            "warehouse": "",
            "items": [{"code": material.code, "quantity": 1, "price": 1}],
        },
    )
    record(
        "D1-add_out_order-no-default-rejected",
        rv.status_code == 400 and "仓库" in rv.get_json(force=True).get("msg", ""),
        f"无默认仓库且未填仓库时 add_out_order 返回 {rv.status_code}",
    )

    # ---------- D2: add_out_order 开启默认仓库 + 空仓库 → 自动取默认 ----------
    set_prefer_default_warehouse("1")
    rv = client.post(
        "/out_order/add",
        json={
            "order_no": f"OUT{suffix}02",
            "date": "2026-08-02",
            "business_type": "领料单",
            "warehouse": "",
            "items": [{"code": material.code, "quantity": 1, "price": 1}],
        },
    )
    data = rv.get_json(force=True)
    record(
        "D2-add_out_order-default-assigned",
        rv.status_code == 200,
        f"开启默认仓库后 add_out_order 返回 {rv.status_code}, msg={data.get('msg')}",
    )

    # ---------- D3: complete_out_order 存量无仓库 pending 单据自动取默认 ----------
    from app import OutOrder, OutOrderItem

    order_no_d3 = f"OUT{suffix}03"
    order_d3 = OutOrder(
        order_no=order_no_d3,
        date=date(2026, 8, 2),
        business_type="领料单",
        warehouse="",
        status="pending",
        operator_id=1,
    )
    db.session.add(order_d3)
    db.session.flush()
    item_d3 = OutOrderItem(
        out_order_id=order_d3.id,
        material_id=material.id,
        quantity=1,
        price=1,
        amount=1,
    )
    db.session.add(item_d3)
    db.session.commit()

    rv = client.post(f"/out_order/{order_d3.id}/complete")
    db.session.refresh(order_d3)
    record(
        "D3-complete_out_order-default-assigned",
        rv.status_code == 200 and order_d3.warehouse == default_wh.name,
        f"complete_out_order 自动默认仓库={order_d3.warehouse!r}, status={rv.status_code}",
    )

    # ---------- D4: batch_complete_out_order 存量无仓库 pending 单据自动取默认 ----------
    order_no_d4 = f"OUT{suffix}04"
    order_d4 = OutOrder(
        order_no=order_no_d4,
        date=date(2026, 8, 2),
        business_type="领料单",
        warehouse="",
        status="pending",
        operator_id=1,
    )
    db.session.add(order_d4)
    db.session.flush()
    item_d4 = OutOrderItem(
        out_order_id=order_d4.id,
        material_id=material.id,
        quantity=1,
        price=1,
        amount=1,
    )
    db.session.add(item_d4)
    db.session.commit()

    rv = client.post("/out_order/batch_complete", json={"ids": [order_d4.id]})
    db.session.refresh(order_d4)
    record(
        "D4-batch_complete_out_order-default-assigned",
        rv.status_code == 200 and order_d4.warehouse == default_wh.name,
        f"batch_complete_out_order 自动默认仓库={order_d4.warehouse!r}, status={rv.status_code}",
    )

    # ---------- D5: add_after_sale_out_order 关闭默认仓库 + 空仓库 → 400 ----------
    set_prefer_default_warehouse("0")
    rv = client.post(
        "/after_sale_out/add",
        json={
            "order_no": f"ASO{suffix}01",
            "date": "2026-08-02",
            "customer": "测试客户",
            "warehouse": "",
            "reason": "质量问题",
            "items": [{"code": material.code, "quantity": 1, "price": 1}],
        },
    )
    record(
        "D5-add_after_sale_out_order-no-default-rejected",
        rv.status_code == 400 and "仓库" in rv.get_json(force=True).get("msg", ""),
        f"无默认仓库且未填仓库时 add_after_sale_out_order 返回 {rv.status_code}",
    )

    # ---------- D6: add_after_sale_out_order 开启默认仓库 + 空仓库 → 自动取默认 ----------
    set_prefer_default_warehouse("1")
    rv = client.post(
        "/after_sale_out/add",
        json={
            "order_no": f"ASO{suffix}02",
            "date": "2026-08-02",
            "customer": "测试客户",
            "warehouse": "",
            "reason": "质量问题",
            "items": [{"code": material.code, "quantity": 1, "price": 1}],
        },
    )
    data = rv.get_json(force=True)
    record(
        "D6-add_after_sale_out_order-default-assigned",
        rv.status_code == 200,
        f"开启默认仓库后 add_after_sale_out_order 返回 {rv.status_code}, msg={data.get('msg')}",
    )

    # ---------- D7: complete_after_sale_out_order 存量无仓库 pending 单据自动取默认 ----------
    from app import AfterSaleOutOrder, AfterSaleOutOrderItem

    order_no_d7 = f"ASO{suffix}03"
    order_d7 = AfterSaleOutOrder(
        order_no=order_no_d7,
        date=date(2026, 8, 2),
        customer="测试客户",
        warehouse="",
        reason="质量问题",
        status="pending",
        operator_id=1,
    )
    db.session.add(order_d7)
    db.session.flush()
    item_d7 = AfterSaleOutOrderItem(
        after_sale_out_order_id=order_d7.id,
        material_id=material.id,
        quantity=1,
        price=1,
        amount=1,
    )
    db.session.add(item_d7)
    db.session.commit()

    rv = client.post(f"/after_sale_out/{order_d7.id}/complete")
    db.session.refresh(order_d7)
    record(
        "D7-complete_after_sale_out_order-default-assigned",
        rv.status_code == 200 and order_d7.warehouse == default_wh.name,
        f"complete_after_sale_out_order 自动默认仓库={order_d7.warehouse!r}, status={rv.status_code}",
    )

    # ---------- 清理测试数据 ----------
    for o in (order_d3, order_d4):
        for it in list(o.items):
            db.session.delete(it)
    db.session.commit()
    db.session.delete(order_d4)
    db.session.delete(order_d3)
    for it in list(order_d7.items):
        db.session.delete(it)
    db.session.commit()
    db.session.delete(order_d7)
    # 删除由 add 路由创建的草稿/已完成单
    for o in OutOrder.query.filter(OutOrder.order_no.in_([f"OUT{suffix}01", f"OUT{suffix}02"])).all():
        for it in list(o.items):
            db.session.delete(it)
        db.session.delete(o)
    for o in AfterSaleOutOrder.query.filter(
        AfterSaleOutOrder.order_no.in_([f"ASO{suffix}01", f"ASO{suffix}02"])
    ).all():
        for it in list(o.items):
            db.session.delete(it)
        db.session.delete(o)
    # 恢复测试物料库存，避免影响其他回归测试
    material.stock = 1000
    db.session.commit()

failures = [r for r in results if r[1] == "FAIL"]
if failures:
    print(f"\n共 {len(failures)} 项失败")
    for cp, status, detail in failures:
        print(f"  {status}: {cp} - {detail}")
    raise SystemExit(1)
print("\n全部通过")
raise SystemExit(0)
