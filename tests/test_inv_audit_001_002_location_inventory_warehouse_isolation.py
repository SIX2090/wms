# -*- coding: utf-8 -*-
"""INV-AUDIT-001 / INV-AUDIT-002 回归测试：

1. 不同仓库的同名库位不得被合并到同一条 LocationInventory 记录
   （修复前旧唯一约束 (material_id, location) 会强制合并）。
2. get_warehouse_stock_quantities 必须按 warehouse_id 汇总，
   不得回退全局 Material.stock，且能兼容 warehouse_id IS NULL
   但 location == 仓库名的历史行。
3. update_location_inventory / add_location_inventory_atomic /
   deduct_location_inventory_atomic 必须按 warehouse_id 精确匹配，
   不传 warehouse 时仅匹配 IS NULL 的历史行。
4. resolve_inventory_warehouse_id 支持 None / Warehouse / int / str。
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

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, name):
    from app import Material
    m = Material(code=code, name=name, stock=0)
    db.session.add(m)
    db.session.commit()
    return m


def _enable_location_management():
    from app import set_system_setting
    set_system_setting("location_management_enabled", "1")
    db.session.commit()


class TestResolveInventoryWarehouseId:
    """resolve_inventory_warehouse_id 辅助函数。"""

    def test_none_returns_none(self):
        from app import resolve_inventory_warehouse_id
        with app_module.app.app_context():
            _reset_db()
            assert resolve_inventory_warehouse_id(None) is None

    def test_int_passthrough(self):
        from app import resolve_inventory_warehouse_id
        with app_module.app.app_context():
            _reset_db()
            assert resolve_inventory_warehouse_id(42) == 42
            assert resolve_inventory_warehouse_id(0) == 0

    def test_warehouse_instance_returns_id(self):
        from app import resolve_inventory_warehouse_id
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("WH001", "材料仓")
            assert resolve_inventory_warehouse_id(w) == w.id

    def test_str_resolves_by_name_or_code(self):
        from app import resolve_inventory_warehouse_id
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w = _seed_warehouse("WH001", "材料仓")
            assert resolve_inventory_warehouse_id("WH001") == w.id
            assert resolve_inventory_warehouse_id("材料仓") == w.id

    def test_str_unknown_returns_none(self):
        from app import resolve_inventory_warehouse_id
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_warehouse("WH001", "材料仓")
            assert resolve_inventory_warehouse_id("不存在仓库") is None
            assert resolve_inventory_warehouse_id("") is None


class TestCrossWarehouseSameLocationNotMerged:
    """INV-AUDIT-002 核心修复：不同仓库的同名库位不得合并。"""

    def test_same_location_different_warehouses_kept_separate(self):
        """同一物料、同一库位名、不同仓库：必须各自建账，互不干扰。"""
        from app import LocationInventory, update_location_inventory
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            w2 = _seed_warehouse("WH002", "成品仓")
            m = _seed_material("M001", "TestMat")

            ok, err = update_location_inventory(m, "A1", 10, warehouse=w1)
            assert ok, err
            ok, err = update_location_inventory(m, "A1", 5, warehouse=w2)
            assert ok, err

            rows = LocationInventory.query.filter_by(material_id=m.id, location="A1").all()
            assert len(rows) == 2, f"expected 2 rows (one per warehouse), got {len(rows)}"
            by_wh = {r.warehouse_id: r.quantity for r in rows}
            assert by_wh == {w1.id: 10.0, w2.id: 5.0}, by_wh

    def test_deduct_only_affects_specified_warehouse(self):
        """扣减某仓库库位库存不得影响另一仓库的同名库位。"""
        from app import LocationInventory, update_location_inventory
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            w2 = _seed_warehouse("WH002", "成品仓")
            m = _seed_material("M001", "TestMat")

            update_location_inventory(m, "A1", 10, warehouse=w1)
            update_location_inventory(m, "A1", 5, warehouse=w2)

            ok, err = update_location_inventory(m, "A1", -3, warehouse=w1)
            assert ok, err

            rows = {r.warehouse_id: r.quantity
                    for r in LocationInventory.query.filter_by(material_id=m.id, location="A1").all()}
            assert rows == {w1.id: 7.0, w2.id: 5.0}, rows

    def test_deduct_wrong_warehouse_does_not_touch_other(self):
        """对不存在库位库存的仓库扣减：不得误扣另一仓库的同名库位。"""
        from app import LocationInventory, update_location_inventory
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            w2 = _seed_warehouse("WH002", "成品仓")
            m = _seed_material("M001", "TestMat")

            update_location_inventory(m, "A1", 10, warehouse=w1)
            # w2/A1 不存在记录，扣减应失败（默认不允许负库存）
            ok, err = update_location_inventory(m, "A1", -3, warehouse=w2)
            assert not ok, "expected failure when deducting from empty warehouse-2 location"
            # w1/A1 库存应保持不变
            row = LocationInventory.query.filter_by(
                material_id=m.id, warehouse_id=w1.id, location="A1"
            ).first()
            assert row.quantity == 10.0, row.quantity


class TestGetWarehouseStockQuantitiesIsolation:
    """INV-AUDIT-001 修复：get_warehouse_stock_quantities 按 warehouse_id 汇总。"""

    def test_summarizes_by_warehouse_id(self):
        from app import (
            LocationInventory, get_warehouse_stock_quantities,
        )
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            w2 = _seed_warehouse("WH002", "成品仓")
            m = _seed_material("M001", "TestMat")
            _enable_location_management()

            # 在 w1 多个库位 + w2 一个库位
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w1.id,
                                             location="A1", quantity=10))
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w1.id,
                                             location="A2", quantity=3))
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w2.id,
                                             location="A1", quantity=5))
            db.session.commit()

            q1 = get_warehouse_stock_quantities(w1)
            q2 = get_warehouse_stock_quantities(w2)
            assert q1.get(m.id) == 13.0, q1
            assert q2.get(m.id) == 5.0, q2

    def test_legacy_null_row_attributed_by_location_string(self):
        """warehouse_id 为 NULL 但 location == 仓库名的历史行应被正确归属。"""
        from app import (
            LocationInventory, get_warehouse_stock_quantities,
        )
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            w2 = _seed_warehouse("WH002", "成品仓")
            m = _seed_material("M001", "TestMat")
            _enable_location_management()

            # 历史 NULL 行：location 直接是仓库名
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=None,
                                             location="材料仓", quantity=7))
            # 新数据：按 warehouse_id 精确归属
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w1.id,
                                             location="A1", quantity=10))
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w2.id,
                                             location="A1", quantity=5))
            db.session.commit()

            q1 = get_warehouse_stock_quantities(w1)
            q2 = get_warehouse_stock_quantities(w2)
            # w1 = 10 (新) + 7 (历史 NULL + location='材料仓') = 17
            assert q1.get(m.id) == 17.0, q1
            # w2 = 5 (新)，历史 NULL 行 location='材料仓' 不归属 w2
            assert q2.get(m.id) == 5.0, q2

    def test_empty_warehouse_returns_empty_dict(self):
        from app import get_warehouse_stock_quantities
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            assert get_warehouse_stock_quantities(w1) == {}

    def test_no_global_material_stock_fallback(self):
        """即使 Material.stock 有值，也绝不被 get_warehouse_stock_quantities 使用。"""
        from app import (
            Material, get_warehouse_stock_quantities,
        )
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            m = Material(code="M001", name="TestMat", stock=999)  # 全局库存有值
            db.session.add(m)
            db.session.commit()
            _enable_location_management()
            # 无任何 LocationInventory 记录 -> 应返回空 dict，不得取 Material.stock
            q1 = get_warehouse_stock_quantities(w1)
            assert q1 == {}, q1


class TestLegacyCallersWithNullWarehouse:
    """不传 warehouse 的旧调用方仍能正常工作（仅匹配 IS NULL 行）。"""

    def test_update_without_warehouse_matches_null_row(self):
        from app import LocationInventory, update_location_inventory
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            m = _seed_material("M001", "TestMat")

            # 插入一个 warehouse_id=NULL 的历史行
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=None,
                                             location="A1", quantity=5))
            db.session.commit()

            # 旧调用方不传 warehouse：应匹配 NULL 行
            ok, err = update_location_inventory(m, "A1", 3)
            assert ok, err

            row = LocationInventory.query.filter_by(
                material_id=m.id, location="A1"
            ).first()
            assert row.warehouse_id is None
            assert row.quantity == 8.0, row.quantity

    def test_update_without_warehouse_does_not_touch_warehouse_id_rows(self):
        """旧调用方不传 warehouse 时不得误改已归属仓库的行。"""
        from app import LocationInventory, update_location_inventory
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
            m = _seed_material("M001", "TestMat")

            # 已归属仓库的行
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=w1.id,
                                             location="A1", quantity=10))
            db.session.commit()

            # 旧调用方不传 warehouse：应建新 NULL 行，不得改 w1 行
            ok, err = update_location_inventory(m, "A1", 3)
            assert ok, err

            rows = LocationInventory.query.filter_by(
                material_id=m.id, location="A1"
            ).all()
            by_wh = {r.warehouse_id: r.quantity for r in rows}
            assert by_wh == {w1.id: 10.0, None: 3.0}, by_wh


# ---------------------------------------------------------------------------
# A9 规则要求：新增/修改的业务函数必须有同名 test_<func_name> 测试。
# 以下函数名严格匹配 app.py 中的 def 名称，供 lint_wms_rules.py 识别。
# ---------------------------------------------------------------------------

def test_resolve_inventory_warehouse_id():
    """resolve_inventory_warehouse_id 综合回归。"""
    from app import resolve_inventory_warehouse_id
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        w = _seed_warehouse("WH001", "材料仓")
        assert resolve_inventory_warehouse_id(None) is None
        assert resolve_inventory_warehouse_id(w) == w.id
        assert resolve_inventory_warehouse_id(w.id) == w.id
        assert resolve_inventory_warehouse_id("WH001") == w.id
        assert resolve_inventory_warehouse_id("材料仓") == w.id
        assert resolve_inventory_warehouse_id("不存在") is None


def test_update_location_inventory():
    """update_location_inventory 综合回归：warehouse 维度隔离。"""
    from app import LocationInventory, update_location_inventory
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
        w2 = _seed_warehouse("WH002", "成品仓")
        m = _seed_material("M001", "TestMat")

        ok, err = update_location_inventory(m, "A1", 10, warehouse=w1)
        assert ok, err
        ok, err = update_location_inventory(m, "A1", 5, warehouse=w2)
        assert ok, err
        ok, err = update_location_inventory(m, "A1", -3, warehouse=w1)
        assert ok, err

        rows = {r.warehouse_id: r.quantity
                for r in LocationInventory.query.filter_by(
                    material_id=m.id, location="A1").all()}
        assert rows == {w1.id: 7.0, w2.id: 5.0}, rows


def test_add_location_inventory_atomic():
    """add_location_inventory_atomic 综合回归：warehouse_id 精确匹配。"""
    from app import (
        LocationInventory, add_location_inventory_atomic,
    )
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
        m = _seed_material("M001", "TestMat")

        ok, err = add_location_inventory_atomic(
            m.id, "A1", 10, material_code_hint=m.code, warehouse_id=w1.id)
        assert ok, err
        ok, err = add_location_inventory_atomic(
            m.id, "A1", 5, material_code_hint=m.code, warehouse_id=None)
        assert ok, err

        rows = {(r.warehouse_id, r.location): r.quantity
                for r in LocationInventory.query.filter_by(material_id=m.id).all()}
        # warehouse_id=w1 行和 NULL 行各自独立
        assert rows == {(w1.id, "A1"): 10.0, (None, "A1"): 5.0}, rows


def test_deduct_location_inventory_atomic():
    """deduct_location_inventory_atomic 综合回归：warehouse_id 精确扣减。"""
    from app import (
        LocationInventory, add_location_inventory_atomic,
        deduct_location_inventory_atomic,
    )
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        w1 = _seed_warehouse("WH001", "材料仓", is_default=True)
        w2 = _seed_warehouse("WH002", "成品仓")
        m = _seed_material("M001", "TestMat")

        # 两个仓库同名库位各建 10
        add_location_inventory_atomic(m.id, "A1", 10, warehouse_id=w1.id)
        add_location_inventory_atomic(m.id, "A1", 10, warehouse_id=w2.id)

        # 仅扣 w1
        ok, err = deduct_location_inventory_atomic(
            m.id, "A1", 3, material_code_hint=m.code, warehouse_id=w1.id)
        assert ok, err

        rows = {r.warehouse_id: r.quantity
                for r in LocationInventory.query.filter_by(
                    material_id=m.id, location="A1").all()}
        assert rows == {w1.id: 7.0, w2.id: 10.0}, rows
