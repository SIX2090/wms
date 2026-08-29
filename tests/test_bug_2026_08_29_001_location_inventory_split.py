# -*- coding: utf-8 -*-
"""BUG-2026-08-29-001：库位账静默分裂与出库缺仓库级库存校验。

根因：
① ``update_location_inventory`` 在库位为空时直接 ``return (True, '')``，
   调用方（手机端扫码 mobile.py、原生接口 native_api.py）据此判定成功，
   导致总账已扣减而库位账未动，账实静默分裂且无任何报错。
② ``complete_out_order`` / ``batch_complete_out_order`` 只按全局库存校验，
   未按「出库仓库」维度校验，A 仓库存不足时可用 B 仓库存蒙混过关。

T1. 启用库位管理 + 空库位 → 显式失败并返回中文原因（不再静默成功）。
T2. 未启用库位管理 + 空库位 → 保持旧行为 (True, '')。
T3. 数量为 0（无变动）→ 仍视为成功，不影响既有调用方。
T4. 空白库位（'   '）经 strip 后同样失败。
T5. 两处出库预检锚点：走仓库级库存聚合，且不足时先 rollback 再 api_error。
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest import mock

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
    Material, MaterialCategory, Unit, db, update_location_inventory,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _fresh_db():
    """每个用例一个干净的内存库，互不污染。"""
    db.drop_all()
    db.create_all()


def _make_material(code="T-001"):
    suffix = uuid.uuid4().hex[:8]
    cat = MaterialCategory(code="CAT-%s" % suffix, name="测试分类")
    unit = Unit(code="UNT-%s" % suffix, name="个")
    db.session.add_all([cat, unit])
    db.session.flush()
    mat = Material(code=code, name="测试物料", category_id=cat.id, unit_id=unit.id)
    db.session.add(mat)
    db.session.flush()
    return mat


def test_t1_empty_location_fails_when_location_management_enabled():
    """启用库位管理时必须显式失败，不能静默返回成功。"""
    with app_module.app.app_context():
        _fresh_db()
        mat = _make_material("T-101")
        with mock.patch.object(app_module, "location_management_enabled",
                               return_value=True):
            ok, msg = update_location_inventory(mat, "", 5)
        assert ok is False
        assert "未指定库位" in msg


def test_t2_empty_location_ok_when_location_management_disabled():
    """未启用库位管理时保持旧行为，不回归。"""
    with app_module.app.app_context():
        _fresh_db()
        mat = _make_material("T-102")
        with mock.patch.object(app_module, "location_management_enabled",
                               return_value=False):
            ok, msg = update_location_inventory(mat, "", 5)
        assert ok is True
        assert msg == ""


def test_t3_zero_delta_still_success():
    """数量为 0（无变动）仍视为成功，避免打断既有调用方。"""
    with app_module.app.app_context():
        _fresh_db()
        mat = _make_material("T-103")
        with mock.patch.object(app_module, "location_management_enabled",
                               return_value=True):
            ok, msg = update_location_inventory(mat, "", 0)
        assert ok is True
        assert msg == ""


def test_t4_blank_location_stripped_then_fails():
    """纯空白库位经 strip 后等同空库位，必须同样失败。"""
    with app_module.app.app_context():
        _fresh_db()
        mat = _make_material("T-104")
        with mock.patch.object(app_module, "location_management_enabled",
                               return_value=True):
            ok, msg = update_location_inventory(mat, "   ", -3)
        assert ok is False
        assert "未指定库位" in msg


def test_t5_out_order_warehouse_level_precheck_anchor():
    """单条/批量出库完成前都必须按出库仓库维度校验库存。"""
    src = (ROOT / "app" / "routes" / "out_order.py").read_text(encoding="utf-8")
    # 两处（complete_out_order / batch_complete_out_order）都走仓库级库存聚合
    assert src.count("get_warehouse_stock_quantities") >= 2
    # 不足时先回滚事务再返回错误，避免残留半成品
    assert "db.session.rollback()" in src
    assert "库存不足" in src
