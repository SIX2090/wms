# -*- coding: utf-8 -*-
"""P0 回归：NaN/Infinity 数量不得污染库存。

漏洞链：float('nan') 不抛异常 → nan <= 0 为 False → 绕过上游校验 →
add_stock(material, nan) → Material.stock = stock + nan = nan →
该物料库存永久失效。

本测试锁定 parse_float_value / round_to_2_decimals / normalize_stock_quantity /
add_stock 四层防线均拒绝 NaN/Infinity/负数。
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")

from utils import (  # noqa: E402
    parse_float_value,
    round_to_2_decimals,
    normalize_stock_quantity,
)


# ==================== 纯函数测试（无需 app context） ====================

def test_parse_float_value_rejects_nan_string():
    """float('nan') 字符串必须返回 default(0)，不得返回 nan。"""
    result = parse_float_value('nan')
    assert math.isfinite(result), "NaN must not pass through parse_float_value"
    assert result == 0.0


def test_parse_float_value_rejects_inf_string():
    """float('inf') 字符串必须返回 default(0)。"""
    assert parse_float_value('inf') == 0.0
    assert parse_float_value('-inf') == 0.0


def test_parse_float_value_rejects_negative():
    """负数必须返回 default(0)。"""
    assert parse_float_value(-1) == 0.0
    assert parse_float_value('-5.5') == 0.0


def test_parse_float_value_accepts_valid():
    """正常正数不受影响。"""
    assert parse_float_value('3.14') == 3.14
    assert parse_float_value(0) == 0.0
    assert parse_float_value('100') == 100.0


def test_round_to_2_decimals_rejects_nan():
    """NaN 输入必须返回 0.0，不得返回 nan。"""
    result = round_to_2_decimals(float('nan'))
    assert result == 0.0
    assert math.isfinite(result)


def test_round_to_2_decimals_rejects_inf():
    """Infinity 输入必须返回 0.0。"""
    assert round_to_2_decimals(float('inf')) == 0.0
    assert round_to_2_decimals(float('-inf')) == 0.0


def test_round_to_2_decimals_accepts_valid():
    """正常值不受影响。"""
    assert round_to_2_decimals(3.14159) == 3.14
    assert round_to_2_decimals(None) == 0.0


def test_normalize_stock_quantity_rejects_nan():
    """NaN 经 normalize 后必须为 0.0。"""
    assert normalize_stock_quantity(float('nan')) == 0.0


def test_normalize_stock_quantity_rejects_inf():
    """Infinity 经 normalize 后必须为 0.0。"""
    assert normalize_stock_quantity(float('inf')) == 0.0


# ==================== add_stock 测试（需要 app context） ====================

@pytest.fixture()
def app_context():
    """提供带干净内存库的 app context。"""
    from werkzeug.security import generate_password_hash
    import app as app_module
    from app import Material, Unit, User, Warehouse, db

    app_module.app.config["WMS_DEBUG"] = "0"
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            Warehouse(code="WH01", name="主仓", is_default=True),
            Material(code="M-NANTEST", name="NaN测试物料", spec="S", stock=100.0),
        ])
        db.session.commit()
        yield


def test_add_stock_rejects_zero_or_negative(app_context):
    """add_stock 必须拒绝 qty <= 0，与 deduct_stock_atomic 对称。"""
    from app import Material, add_stock
    mat = Material.query.filter_by(code="M-NANTEST").first()
    ok, err = add_stock(mat, 0)
    assert not ok
    assert '大于 0' in err
    ok, err = add_stock(mat, -1)
    assert not ok
    assert '大于 0' in err


def test_add_stock_rejects_nan(app_context):
    """add_stock 必须拒绝 NaN，防止 Material.stock 被污染为 NaN。"""
    from app import Material, add_stock, db
    mat = Material.query.filter_by(code="M-NANTEST").first()
    original_stock = mat.stock or 0
    ok, err = add_stock(mat, float('nan'))
    assert not ok
    assert '大于 0' in err
    db.session.rollback()
    # 库存未被污染
    db.session.expire(mat, ['stock'])
    assert mat.stock == original_stock


def test_add_stock_accepts_valid(app_context):
    """add_stock 正常正数不受影响。"""
    from app import Material, add_stock, db
    mat = Material.query.filter_by(code="M-NANTEST").first()
    original_stock = mat.stock or 0
    ok, err = add_stock(mat, 10)
    assert ok
    db.session.commit()
    db.session.expire(mat, ['stock'])
    assert mat.stock == original_stock + 10
