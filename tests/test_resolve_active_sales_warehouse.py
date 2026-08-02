"""A9: 覆盖 resolve_active_sales_warehouse helper 的单元测试。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import Warehouse, db  # noqa: E402


def _ensure_clean():
    Warehouse.query.filter(
        Warehouse.code.in_(["A9-SALES-01", "A9-SALES-02", "A9-SALES-03"])
    ).delete(synchronize_session=False)
    db.session.commit()


def test_resolve_by_id():
    with app_module.app.app_context():
        db.create_all()
        _ensure_clean()
        wh = Warehouse(code="A9-SALES-01", name="销售仓A9", status="active", is_default=False)
        db.session.add(wh)
        db.session.commit()

        result = app_module.resolve_active_sales_warehouse(warehouse_id=wh.id)
        assert result is not None
        assert result.id == wh.id

        _ensure_clean()


def test_resolve_by_name():
    with app_module.app.app_context():
        db.create_all()
        _ensure_clean()
        wh = Warehouse(code="A9-SALES-02", name="销售仓B9", status="active", is_default=False)
        db.session.add(wh)
        db.session.commit()

        result = app_module.resolve_active_sales_warehouse(value="  销售仓B9  ")
        assert result is not None
        assert result.id == wh.id

        _ensure_clean()


def test_resolve_inactive_returns_none():
    with app_module.app.app_context():
        db.create_all()
        _ensure_clean()
        wh = Warehouse(code="A9-SALES-03", name="停用仓A9", status="inactive", is_default=False)
        db.session.add(wh)
        db.session.commit()

        result = app_module.resolve_active_sales_warehouse(value="停用仓A9")
        assert result is None

        result_by_id = app_module.resolve_active_sales_warehouse(warehouse_id=wh.id)
        assert result_by_id is None

        _ensure_clean()
