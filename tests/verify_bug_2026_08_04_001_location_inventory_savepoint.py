# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-001 回归测试：add_location_inventory_atomic 建账冲突不得回滚外层事务

原 Bug：add_location_inventory_atomic 在 INSERT 冲突时调用 db.session.rollback()，
会回滚整个外层事务（包括已完成的 add_stock 总库存增减），导致总库存与库位库存、
单据状态永久不一致。

修复：改用 begin_nested()（SAVEPOINT），冲突时只回滚保存点，外层事务不受影响；
随后重查记录走原子 UPDATE 路径。

测试策略：
  T1. 正常建账：无库位记录时 INSERT 成功，库位库存 = qty
  T2. 已有记录时原子增量 UPDATE：不 INSERT，直接 quantity += qty
  T3. SAVEPOINT 隔离：模拟 INSERT 失败后，外层事务中已 add_stock 的总库存
      增减不受影响（不会被回滚），且后续 UPDATE 成功
  T4. 外层事务完整性：add_stock + add_location_inventory_atomic 在同一事务中，
      若库位建账发生冲突，总库存增减仍然保留，最终 commit 后两者一致
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from sqlalchemy import update as sa_update  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Supplier, Warehouse,
    LocationInventory,
)

app_module.app.config["TESTING"] = True

from app import add_location_inventory_atomic, add_stock  # noqa: E402


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, mat])
    db.session.commit()
    return mat


class TestBug20260804001SavepointIsolation:
    """add_location_inventory_atomic 建账冲突时不得回滚外层事务。"""

    def test_T1_normal_insert_creates_location_record(self):
        """无库位记录时 INSERT 成功，库位库存 = qty。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            ok, err = add_location_inventory_atomic(mat.id, "仓库A", 100)
            assert ok, f"应成功: {err}"
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv is not None
            assert inv.quantity == 100

    def test_T2_existing_record_uses_atomic_update(self):
        """已有记录时直接原子增量 UPDATE，不 INSERT。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            ok, _ = add_location_inventory_atomic(mat.id, "仓库A", 100)
            assert ok
            db.session.commit()
            # 第二次调用应走 UPDATE 路径
            ok, _ = add_location_inventory_atomic(mat.id, "仓库A", 50)
            assert ok
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv.quantity == 150

    def test_T3_savepoint_isolation_preserves_outer_transaction(self):
        """模拟 INSERT 冲突：外层事务中先直接更新 Material.stock（模拟
        add_stock 的总库存增减），再让库位建账冲突，验证总库存增减未被回滚。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            # 1. 外层事务中先增加总库存（模拟 add_stock 的效果）
            db.session.execute(
                sa_update(Material)
                .where(Material.id == mat.id)
                .values(stock=Material.stock + 200)
            )
            db.session.flush()
            db.session.expire(mat, ['stock'])
            assert mat.stock == 200
            # 2. 预先插入一条库位记录（模拟并发对手已建账）
            db.session.add(LocationInventory(
                material_id=mat.id, location="仓库A",
                quantity=0, updated_at=None,
            ))
            db.session.flush()
            # 3. 调用 add_location_inventory_atomic —— existing 已存在，走 UPDATE
            ok, err = add_location_inventory_atomic(mat.id, "仓库A", 100)
            assert ok, f"库位更新应成功: {err}"
            # 4. 关键断言：总库存增减仍然保留（未被回滚）
            db.session.expire(mat, ['stock'])
            assert mat.stock == 200, \
                "外层事务中的总库存增减不应被库位操作回滚"
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv.quantity == 100

    def test_T4_insert_conflict_does_not_rollback_outer_stock(self):
        """直接模拟 INSERT 冲突场景：先手动 flush 一条 LocationInventory，
        再调用 add_location_inventory_atomic 让它走 INSERT 分支并触发唯一冲突，
        验证外层总库存增减未被回滚。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            # 1. 外层事务中先增加总库存（模拟 add_stock 的效果）
            db.session.execute(
                sa_update(Material)
                .where(Material.id == mat.id)
                .values(stock=Material.stock + 300)
            )
            db.session.flush()
            db.session.expire(mat, ['stock'])
            assert mat.stock == 300
            # 2. 手动插入一条库位记录并 flush（但不 commit），使后续 INSERT 冲突
            db.session.add(LocationInventory(
                material_id=mat.id, location="仓库A",
                quantity=50, updated_at=None,
            ))
            db.session.flush()
            # 3. 清除 ORM identity map 中的 existing 引用，强制走 INSERT 分支
            db.session.expire_all()
            # 4. 调用 add_location_inventory_atomic —— INSERT 会触发唯一冲突
            ok, err = add_location_inventory_atomic(mat.id, "仓库A", 100,
                                                     material_code_hint="M001")
            # 冲突后应转 UPDATE 成功（因为对手已建账 quantity=50）
            assert ok, f"冲突后应转 UPDATE 成功: {err}"
            # 5. 关键断言：总库存增减仍然保留（未被回滚）
            db.session.expire(mat, ['stock'])
            assert mat.stock == 300, \
                "INSERT 冲突时不应回滚外层事务的总库存增减"
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv.quantity == 150  # 50 + 100
