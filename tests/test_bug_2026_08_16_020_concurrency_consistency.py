# -*- coding: utf-8 -*-
"""BUG-2026-08-16-020 回归：并发与一致性批量。

修复项：
- 020-1 取号并发：generate_order_no 加进程内互斥锁串行化 read-seq+1，
        SQLite 下 with_for_update 是 no-op，避免并发撞号吃 500。
- 020-2 删除死分支：revert_check 原按 check_in/check_out 流水回退库存的
        分支全库无写入从不执行，已删除；反提交只删除未提交的调整草稿。
        （PO 删除加写锁、revert_transfer 原子扣减、native_api 出库守卫、
        委外补锁等由存量 test_pur_audit_002_delete_protection 等覆盖。）
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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    AdjustmentOrder, AdjustmentOrderItem, InventoryCheck, InventoryCheckItem,
    Material, MaterialCategory, Unit, User, Warehouse, db, generate_order_no,
    normalize_stock_quantity,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, stock=10, price=10,
        min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "user": user}


def test_generate_order_no_unique():
    """取号互斥锁下仍能产出唯一单号（覆盖 _generate_order_no_locked）。"""
    with app_module.app.app_context():
        _reset_db()
        from app import InOrder
        numbers = set()
        for _ in range(20):
            no = generate_order_no("IN")
            numbers.add(no)
            # 真实业务取号后即落库，末号随之推进，故每次不等
            db.session.add(InOrder(order_no=no, business_type="测试", warehouse="仓库A"))
        db.session.commit()
        assert len(numbers) == 20


def test_generate_order_no_out_maps_to_ou():
    """OUT 前缀映射为 OU，符合既有约定。"""
    with app_module.app.app_context():
        _reset_db()
        no = generate_order_no("OUT")
        assert no.startswith("OU")


def test_revert_check_deletes_pending_adjustment_draft():
    """反提交盘点：删除未提交的调整单草稿，无 check_in/check_out 死分支回退。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed()

        check = InventoryCheck(
            check_no="CK-001", warehouse="仓库A",
            status="completed", operator_id=seed["user"].id,
        )
        db.session.add(check)
        db.session.flush()
        db.session.add(InventoryCheckItem(
            inventory_check_id=check.id, material_id=seed["mat"].id,
            system_stock=10, actual_stock=12, difference=2,
        ))

        # 盘点完成后生成的未提交调整单草稿（真实库存变动路径）
        adj = AdjustmentOrder(
            adjustment_no="ADJ-001", warehouse="仓库A",
            adjustment_type="profit", source_type="check", source_id=check.id,
            status="pending", operator_id=seed["user"].id,
        )
        db.session.add(adj)
        db.session.flush()
        db.session.add(AdjustmentOrderItem(
            adjustment_order_id=adj.id, material_id=seed["mat"].id,
            location="", quantity=2, unit_id=seed["mat"].unit_id,
        ))
        db.session.commit()

        client = app_module.app.test_client()
        login_page = client.get("/login").get_data(as_text=True)
        import re as _re
        m = _re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
        token = m.group(1) if m else ""
        client.post("/login",
                    data={"username": "admin", "password": "admin", "csrf_token": token})

        resp = client.post(f"/check/{check.id}/revert")
        body = resp.get_json()
        assert body["status"] == "success"

        db.session.refresh(check)
        assert check.status == "pending"
        # 未提交的调整草稿被删除
        assert AdjustmentOrder.query.get(adj.id) is None


def test_revert_check_blocked_when_adjustment_completed():
    """有已提交调整单时，盘点不能直接反提交。"""
    with app_module.app.app_context():
        _reset_db()
        seed = _seed()

        check = InventoryCheck(
            check_no="CK-002", warehouse="仓库A",
            status="completed", operator_id=seed["user"].id,
        )
        db.session.add(check)
        db.session.flush()
        db.session.add(InventoryCheckItem(
            inventory_check_id=check.id, material_id=seed["mat"].id,
            system_stock=10, actual_stock=12, difference=2,
        ))
        adj = AdjustmentOrder(
            adjustment_no="ADJ-002", warehouse="仓库A",
            adjustment_type="profit", source_type="check", source_id=check.id,
            status="completed", operator_id=seed["user"].id,
        )
        db.session.add(adj)
        db.session.commit()

        client = app_module.app.test_client()
        login_page = client.get("/login").get_data(as_text=True)
        import re as _re
        m = _re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
        token = m.group(1) if m else ""
        client.post("/login",
                    data={"username": "admin", "password": "admin", "csrf_token": token})

        resp = client.post(f"/check/{check.id}/revert")
        body = resp.get_json()
        assert body["status"] == "error"
        assert "调整单已提交" in body.get("msg", "")