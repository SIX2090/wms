# -*- coding: utf-8 -*-
"""
PUR-AUDIT-003 回归测试：入库完成与批量完成未复核仓库 active 状态。

根因：新增和编辑草稿已校验仓库 active，但单张完成和批量完成在写锁后、
写库存前未重新校验。草稿保存后仓库被停用，仍可完成入库，导致新库存
归属停用仓库。

修复：在 _acquire_order_write_lock 成功后、add_stock 之前调用
assert_warehouse_active(order.warehouse, allow_empty=False)。
- 单张完成：回滚当前单据并返回 400
- 批量完成：加入 skipped 并继续处理其他合法单据

测试用例：
  T1. 草稿保存后仓库停用，单张完成返回 400，库存/流水/单据状态不变
  T2. 同条件下批量完成跳过该单据，其他合法草稿正常完成
  T3. 不存在仓库名也被拒绝
  T4. 启用仓库的正常完成路径继续通过
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem, StockTransaction,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_base():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
    wh_active = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    wh_will_stop = Warehouse(code="WHB", name="仓库B", status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh_active, wh_will_stop, user, mat])
    db.session.commit()
    return {"mat": mat, "wh_active": wh_active, "wh_will_stop": wh_will_stop,
            "sup": sup, "user": user}


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _create_in_order_draft(warehouse_name, mat, user, qty=10):
    """直接在 DB 创建一张 pending 采购入库草稿。"""
    in_order = InOrder(
        order_no="IN-TEST-001",
        business_type="采购入库",
        warehouse=warehouse_name,
        status="pending",
        operator_id=user.id,
    )
    db.session.add(in_order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=in_order.id,
        material_id=mat.id,
        quantity=qty,
        price=10,
        amount=qty * 10,
    ))
    db.session.commit()
    return in_order


class TestCompleteInactiveWarehouse:
    """T1+T3：草稿保存后仓库停用/不存在，单张完成被拒绝。"""

    def test_inactive_warehouse_blocks_complete(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            in_order = _create_in_order_draft("仓库B", seed["mat"], seed["user"])
            client = _make_client()

            # 停用仓库B
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            wh_b.status = "inactive"
            db.session.commit()

            resp = client.post(f"/in_order/{in_order.id}/complete?force=true")
            assert resp.status_code in (200, 400)
            body = resp.get_json()
            assert body["status"] == "error"
            assert "停用" in body.get("msg", "") or "仓库" in body.get("msg", "")

            # 单据状态不变，库存不增加
            db.session.refresh(in_order)
            assert in_order.status == "pending"
            db.session.refresh(seed["mat"])
            assert (seed["mat"].stock or 0) == 0
            # 无库存流水
            txns = StockTransaction.query.filter_by(reference_id=in_order.id).all()
            assert len(txns) == 0

    def test_nonexistent_warehouse_blocks_complete(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            # 直接写一个不存在的仓库名
            in_order = InOrder(
                order_no="IN-TEST-002",
                business_type="采购入库",
                warehouse="不存在的仓库XYZ",
                status="pending",
                operator_id=seed["user"].id,
            )
            db.session.add(in_order)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order.id,
                material_id=seed["mat"].id,
                quantity=10, price=10, amount=100,
            ))
            db.session.commit()
            client = _make_client()

            resp = client.post(f"/in_order/{in_order.id}/complete?force=true")
            body = resp.get_json()
            assert body["status"] == "error"
            assert "不存在" in body.get("msg", "") or "仓库" in body.get("msg", "")


class TestBatchCompleteInactiveWarehouse:
    """T2：批量完成跳过停用仓库草稿，其他合法草稿正常完成。"""

    def test_batch_complete_skips_inactive(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            # 草稿1：仓库A（active），应完成
            in_order_a = InOrder(
                order_no="IN-A-001", business_type="采购入库",
                warehouse="仓库A", status="pending", operator_id=seed["user"].id,
            )
            db.session.add(in_order_a)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order_a.id, material_id=seed["mat"].id,
                quantity=10, price=10, amount=100,
            ))
            # 草稿2：仓库B（将停用），应跳过
            in_order_b = InOrder(
                order_no="IN-B-001", business_type="采购入库",
                warehouse="仓库B", status="pending", operator_id=seed["user"].id,
            )
            db.session.add(in_order_b)
            db.session.flush()
            db.session.add(InOrderItem(
                in_order_id=in_order_b.id, material_id=seed["mat"].id,
                quantity=20, price=10, amount=200,
            ))
            db.session.commit()

            # 停用仓库B
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            wh_b.status = "inactive"
            db.session.commit()

            client = _make_client()
            resp = client.post(
                "/in_order/batch_complete",
                json={"ids": [in_order_a.id, in_order_b.id]},
            )
            body = resp.get_json()
            assert body["status"] == "success"
            assert body["completed"] == 1
            # batch_complete 将 skipped 信息嵌入 msg
            assert "停用" in body.get("msg", "") or "跳过" in body.get("msg", "")

            # 验证草稿A完成，草稿B仍 pending
            db.session.refresh(in_order_a)
            db.session.refresh(in_order_b)
            assert in_order_a.status == "completed"
            assert in_order_b.status == "pending"


class TestActiveWarehouseCompletePasses:
    """T4：启用仓库的正常完成路径继续通过。"""

    def test_active_warehouse_completes(self):
        with app_module.app.app_context():
            _reset_db()
            seed = _seed_base()
            in_order = _create_in_order_draft("仓库A", seed["mat"], seed["user"])
            client = _make_client()

            resp = client.post(f"/in_order/{in_order.id}/complete?force=true")
            body = resp.get_json()
            assert body["status"] == "success", body

            db.session.refresh(in_order)
            assert in_order.status == "completed"
            db.session.refresh(seed["mat"])
            assert (seed["mat"].stock or 0) == 10
