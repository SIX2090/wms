# -*- coding: utf-8 -*-
"""F4.1 回归：round_to_2_decimals 改为 ROUND_HALF_UP（财务四舍五入）。

原实现 ``round(fval * 100) / 100`` 双重偏差：
  - Python 内置 round 为银行家舍入（half-to-even）：1.005 → 1.00
  - ``fval * 100`` 引入二进制浮点误差：1.005 * 100 = 100.49999999999999

本测试锁定十进制字面精确舍入行为，并保证 NaN/Infinity 防线不回归。
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")

from utils import round_to_2_decimals  # noqa: E402


def test_round_to_2_decimals():
    """验收核心：1.005 必须进位为 1.01（原实现给 1.00）。"""
    assert round_to_2_decimals(1.005) == 1.01
    assert round_to_2_decimals(0.005) == 0.01
    assert round_to_2_decimals(2.675) == 2.68
    assert round_to_2_decimals(1234.565) == 1234.57


def test_round_half_up_negative():
    """ROUND_HALF_UP 对负数同样远离零方向进位。"""
    assert round_to_2_decimals(-1.005) == -1.01
    assert round_to_2_decimals(-0.005) == -0.01


def test_round_below_half_stays():
    """未过半不入位。"""
    assert round_to_2_decimals(1.004) == 1.0
    assert round_to_2_decimals(1.0049) == 1.0


def test_round_regular_values_unchanged():
    """常规值不受影响，兼容既有调用方。"""
    assert round_to_2_decimals(3.14) == 3.14
    assert round_to_2_decimals(100) == 100.0
    assert round_to_2_decimals(0.1 + 0.2) == 0.3
    assert round_to_2_decimals("2.5") == 2.5


def test_rejects_nan_and_infinity():
    """P0 防线不回归：非有限值统一返回 0.0。"""
    for bad in (float("nan"), float("inf"), float("-inf")):
        r = round_to_2_decimals(bad)
        assert math.isfinite(r) and r == 0.0


def test_rejects_none_and_garbage():
    """None / 非数值字符串返回 0.0。"""
    assert round_to_2_decimals(None) == 0.0
    assert round_to_2_decimals("abc") == 0.0
    assert round_to_2_decimals(object()) == 0.0
