# -*- coding: utf-8 -*-
"""F2.12 回归：入库单三处不对称缺陷（审计报告 §1.4）。

BUG-A：`revert_in_order` 的「未归属流水归属修正」是死代码——它写在
       `_acquire_order_write_lock` **之前**，而该锁在 SQLite 分支第一步就是
       `db.session.rollback()`，锁前的 UPDATE 被整段丢弃。批量版
       `batch_revert_in_order` 的同一段写在加锁后，是有效的。
       修复：把「校验 + 归属修正」整体移到加锁之后（与批量版对齐）。

BUG-B：已完成入库单「改量减库存」分支漏了未归属兜底（删除明细分支有）→
       同一张单「删行能过、改小被拒」。
       修复：改量分支补齐 `wh_obj is not None` 判空 + `_material_stock_unattributed`
       两级兜底，与删除分支同口径。

BUG-C：`warehouse_stock` 在 `update_completed_in_order` 循环外只算一次，
       循环内多路写入复用陈旧快照 → 同单多行同物料时前一行已落账的扣减
       不会被后一行的校验看见（放行/误拒都可能）。
       修复：改为按行现取（`get_warehouse_stock_quantities(wh_obj)`）。
"""
from __future__ import annotations

import inspect
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
    InOrder, InOrderItem, Material, MaterialCategory, StockTransaction, Supplier,
    Unit, User, Warehouse, db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture()
def scene():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        set_system_setting("location_management_enabled", "0")
        set_system_setting("allow_negative_stock", "0")
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="供应商"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
            Warehouse(code="WHB", name="仓库B", status="active"),
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
        ])
        db.session.commit()
        mat = Material(code="M001", name="轴承", category_id=1, unit_id=1,
                       supplier_id=1, stock=0, price=10)
        db.session.add(mat)
        db.session.commit()
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"},
                    content_type="application/x-www-form-urlencoded")
        yield client, mat
        db.session.remove()
        db.drop_all()
        db.create_all()


def _completed_order(mat, warehouse, quantities, order_no="IN-F212"):
    user = User.query.filter_by(username="admin").first()
    order = InOrder(order_no=order_no, business_type="采购入库",
                    warehouse=warehouse, status="completed", operator_id=user.id,
                    supplier_id=1)
    db.session.add(order)
    db.session.flush()
    items = []
    for q in quantities:
        item = InOrderItem(in_order_id=order.id, material_id=mat.id,
                           quantity=q, price=10, amount=q * 10)
        db.session.add(item)
        items.append(item)
    db.session.commit()
    return order.id, [i.id for i in items]


# ---------------------------------------------------------------------------
# BUG-A：归属修正必须在加锁之后（结构不变量）
#
# 为什么用结构断言而非端到端行为断言：`revert_in_order` 的归属修正分支要求
# 「仓库级不足 + 全局充足 + 存在未归属流水 + 该物料并非全部未归属」，而在这套
# 分层兜底（`_material_stock_unattributed` / `_filter_txn_list_by_warehouse_scope`
# / `deduct_stock_atomic` 自身的仓库级复核）共同作用下，端到端不可构造出
# 「修正后仍能成功提交」的场景——修正本身不改变仓库级聚合值。故锁死**结构
# 不变量**：修正段必须出现在 `_acquire_order_write_lock` 之后，与批量版一致。
# ---------------------------------------------------------------------------
def _src(fn):
    return inspect.getsource(fn)


def test_bug_a_attribution_correction_after_lock():
    import app.routes.in_order as io_mod

    # 通过模块内注册的视图函数取源码：register_in_order_routes 内的闭包
    src = _src(io_mod.register_in_order_routes)
    single = src.split("def revert_in_order(id):", 1)[1]
    single = single.split("\n    @app.route", 1)[0]
    # 注意：必须匹配**调用**行，不能匹配函数顶部的 from app import ...（import
    # 里也含 `_acquire_order_write_lock` 字样，会把位置算错）。
    lock_at = single.index("locked, ok = _acquire_order_write_lock")
    correction_at = single.index("update({'location': order.warehouse.strip()}")
    assert lock_at < correction_at, (
        "BUG-A 回归：revert_in_order 的流水归属修正必须在 _acquire_order_write_lock "
        "之后，否则会被锁内的 db.session.rollback() 丢弃（死代码）")

    # 与批量版对齐：批量版同为「先加锁、后修正」
    batch = src.split("def batch_revert_in_order():", 1)[1]
    batch = batch.split("\n    @app.route", 1)[0]
    assert batch.index("locked, lock_ok = _acquire_order_write_lock") < batch.index(
        "update({'location': order.warehouse.strip()}")


# ---------------------------------------------------------------------------
# BUG-B：改量减库存分支补齐未归属兜底（与删除分支对称）
# ---------------------------------------------------------------------------
def test_bug_b_reduce_qty_with_legacy_unattributed_stock(scene):
    client, mat = scene
    with app_module.app.app_context():
        # 历史遗留：库存全部为未归属流水（location 为空、来源单据不存在）
        mat.stock = 50
        db.session.add(StockTransaction(
            material_id=mat.id, transaction_type="in", quantity=50,
            location=None, reference_type="in_order", reference_id=999))
        db.session.commit()
        order_id, item_ids = _completed_order(mat, "仓库A", [50], "IN-F212-B")

    # 改小数量（减库存 10）：仓库级聚合为 0，但全局有 50 → 应回退全局口径放行
    resp = client.post(f"/in_order/{order_id}/update_completed", json={
        "items": [{"id": item_ids[0], "quantity": 40, "price": 10}],
    })
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        item = db.session.get(InOrderItem, item_ids[0])
        assert item.quantity == 40
        assert db.session.get(Material, mat.id).stock == 40


def test_bug_b_symmetry_delete_also_passes(scene):
    """对称性：同样场景下「删除明细」分支本就放行，改量分支修复后行为一致。"""
    client, mat = scene
    with app_module.app.app_context():
        mat.stock = 50
        db.session.add(StockTransaction(
            material_id=mat.id, transaction_type="in", quantity=50,
            location=None, reference_type="in_order", reference_id=999))
        db.session.commit()
        order_id, item_ids = _completed_order(mat, "仓库A", [50], "IN-F212-B2")

    resp = client.post(f"/in_order/{order_id}/update_completed", json={
        "items": [], "deleted_items": [item_ids[0]],
    })
    data = resp.get_json()
    assert data.get("status") == "success", data


# ---------------------------------------------------------------------------
# BUG-C：仓库级快照按行现取（同单先增后减不得被陈旧快照误拒）
# ---------------------------------------------------------------------------
def test_bug_c_per_row_recompute(scene):
    client, mat = scene
    with app_module.app.app_context():
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        # A 仓 10（可归属），保证 _material_stock_unattributed 为 False
        mat.stock = 10
        db.session.add(StockTransaction(
            material_id=mat.id, transaction_type="in", quantity=10,
            warehouse_id=wh_a.id, location="仓库A"))
        db.session.commit()
        order_id, item_ids = _completed_order(mat, "仓库A", [100, 100], "IN-F212-C")

    # 第 1 行 +40（A 仓 10→50）；第 2 行 -30。
    # 修复前：第 2 行用循环外的陈旧快照（A=10）→ 10<30 误拒。
    # 修复后：第 2 行按行现取（A=50）→ 50>=30 放行。
    resp = client.post(f"/in_order/{order_id}/update_completed", json={
        "items": [
            {"id": item_ids[0], "quantity": 140, "price": 10},
            {"id": item_ids[1], "quantity": 70, "price": 10},
        ],
    })
    data = resp.get_json()
    assert data.get("status") == "success", data
    with app_module.app.app_context():
        assert db.session.get(InOrderItem, item_ids[0]).quantity == 140
        assert db.session.get(InOrderItem, item_ids[1]).quantity == 70
        assert db.session.get(Material, mat.id).stock == 20  # 10 + 40 - 30
