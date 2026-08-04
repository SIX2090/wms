# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-002 回归测试：update_location_inventory 负 delta 无库位记录不得静默成功

原 Bug：update_location_inventory 在 quantity_delta < 0 且无库位记录、
不允许负库位库存时返回 True, ''（静默成功）。调用方（如 batch_complete_out_order）
在总库存已扣减但库位库存未扣减时仍认为操作成功，造成账实不一致。

修复：与 deduct_location_inventory_atomic 行为对齐，无库位记录且不允许
负库存时返回 False + 错误信息。

测试策略：
  T1. 负 delta + 无库位记录 + 不允许负库存 → 返回 False（不再静默成功）
  T2. 负 delta + 有库位记录 → 正常扣减，返回 True
  T3. 负 delta + 无库位记录 + 允许负库存 → 走 deduct_location_inventory_atomic 建账
  T4. 正 delta + 无库位记录 → 正常建账（add_location_inventory_atomic），返回 True
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
from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Supplier, Warehouse,
    LocationInventory, SystemSetting,
)

app_module.app.config["TESTING"] = True

from app import update_location_inventory, allow_negative_location_stock  # noqa: E402


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
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, mat])
    db.session.commit()
    return mat


def _set_allow_negative_location_stock(value: bool):
    """设置 allow_negative_location_stock 系统参数（'1'/'0' 格式）。"""
    setting = SystemSetting.query.filter_by(key='allow_negative_location_stock').first()
    if not setting:
        setting = SystemSetting(key='allow_negative_location_stock', value='1' if value else '0')
        db.session.add(setting)
    else:
        setting.value = '1' if value else '0'
    db.session.commit()


class TestBug20260804002NoSilentSuccess:
    """update_location_inventory 负 delta 无库位记录不得静默成功。"""

    def test_T1_negative_delta_no_record_returns_false(self):
        """负 delta + 无库位记录 + 不允许负库存 → 返回 False。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            _set_allow_negative_location_stock(False)
            # 确保无库位记录
            assert LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first() is None
            ok, err = update_location_inventory(mat, "仓库A", -50)
            assert not ok, f"无库位记录时应返回 False，但返回了 ok={ok}, err={err}"
            assert "无库位库存记录" in err or "库存不足" in err

    def test_T2_negative_delta_with_record_deducts(self):
        """负 delta + 有库位记录 → 正常扣减，返回 True。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            _set_allow_negative_location_stock(False)
            # 先建库位记录
            db.session.add(LocationInventory(
                material_id=mat.id, location="仓库A", quantity=100))
            db.session.commit()
            ok, err = update_location_inventory(mat, "仓库A", -30)
            assert ok, f"有库位记录时应成功: {err}"
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv.quantity == 70

    def test_T3_negative_delta_no_record_allows_negative(self):
        """负 delta + 无库位记录 + 允许负库存 → 走 deduct 建账。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            _set_allow_negative_location_stock(True)
            assert allow_negative_location_stock() is True
            ok, err = update_location_inventory(mat, "仓库A", -50)
            assert ok, f"允许负库存时应成功: {err}"
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv is not None
            assert inv.quantity == -50

    def test_T4_positive_delta_no_record_creates(self):
        """正 delta + 无库位记录 → 正常建账，返回 True。"""
        with app_module.app.app_context():
            _reset_db()
            mat = _seed()
            ok, err = update_location_inventory(mat, "仓库A", 100)
            assert ok, f"正 delta 建账应成功: {err}"
            db.session.commit()
            inv = LocationInventory.query.filter_by(
                material_id=mat.id, location="仓库A").first()
            assert inv is not None
            assert inv.quantity == 100
