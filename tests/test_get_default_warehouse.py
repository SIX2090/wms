"""A9: 覆盖 get_default_warehouse helper 的单元测试。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as app_module  # noqa: E402
from app import SystemSetting, Warehouse, db  # noqa: E402


def _ensure_clean():
    Warehouse.query.filter(db.or_(Warehouse.code.in_(["A9-DEFAULT", "A9-OTHER"]), Warehouse.is_default == True)).delete(  # noqa: E712
        synchronize_session=False
    )
    db.session.commit()


def test_get_default_warehouse_returns_active_default():
    with app_module.app.app_context():
        db.create_all()
        _ensure_clean()
        wh = Warehouse(
            code="A9-DEFAULT", name="默认仓A9", status="active", is_default=True
        )
        db.session.add(wh)
        other = Warehouse(
            code="A9-OTHER", name="其他仓A9", status="active", is_default=False
        )
        db.session.add(other)

        setting = SystemSetting.query.filter_by(key="prefer_default_warehouse").first()
        if not setting:
            setting = SystemSetting(key="prefer_default_warehouse", value="1")
            db.session.add(setting)
        else:
            setting.value = "1"
        db.session.commit()

        result = app_module.get_default_warehouse()
        assert result is not None
        assert result.id == wh.id
        assert result.name == "默认仓A9"

        _ensure_clean()


def test_get_default_warehouse_disabled_returns_none():
    with app_module.app.app_context():
        db.create_all()
        _ensure_clean()
        wh = Warehouse(
            code="A9-DEFAULT", name="默认仓A9", status="active", is_default=True
        )
        db.session.add(wh)

        setting = SystemSetting.query.filter_by(key="prefer_default_warehouse").first()
        if not setting:
            setting = SystemSetting(key="prefer_default_warehouse", value="0")
            db.session.add(setting)
        else:
            setting.value = "0"
        db.session.commit()

        result = app_module.get_default_warehouse()
        assert result is None

        _ensure_clean()
