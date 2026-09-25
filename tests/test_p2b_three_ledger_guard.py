# -*- coding: utf-8 -*-
"""P2b 降级方案：三账恒等式的「可开关运行时断言」。

为什么不是数据库级约束（CHECK / 触发器）：
    - CHECK 不能跨表、不能写子查询聚合，而恒等式 ① == Σ② == Σ③ 是跨表聚合，
      用 CHECK 根本表达不出来；
    - 触发器能表达，但每次写入都触发一次 SUM()，且本库历史上修过 100 多次
      库存问题、存量脏数据未知——一上线就会把整库写入锁死，没人敢担这个责。

所以降级为两层：
    1. 入口内可开关的运行时断言（本文件覆盖）：测试默认开、生产默认关，
       开了也只是告警，只有显式 strict 才抛——不能让一条对不上账的历史行
       把正常业务写挂；
    2. 既有的 CI 全库恒等式判据 scripts/verify_inventory_identity.py。

本文件要证明三件事：
    - 账平的时候，校验确实说平（不是恒真）；
    - 账歪的时候，校验确实能抓到（不是恒假）——人为把 ① 改歪来验；
    - 开关真的有效：生产模式（0）不校验、strict 才抛。
"""
from __future__ import annotations

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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, MaterialCategory, Unit, Warehouse, db, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TOL = 0.01


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(location_on: bool):
    """返回 material_id（跨 context 只传 id）。"""
    with app_module.app.test_request_context():
        _reset_db()
        set_system_setting("location_management_enabled", "1" if location_on else "0")
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        ])
        db.session.commit()
        mat = Material(code="M-P2B", name="守卫料", spec="S",
                       category_id=1, unit_id=1, stock=0, price=1)
        db.session.add(mat)
        db.session.commit()
        return mat.id


def _entry(mid, delta, **kw):
    """在 request context 里调入库/出库入口。"""
    with app_module.app.test_request_context():
        from services.warehouse_stock_service import apply_stock_delta
        mat = Material.query.get(mid)
        ok, msg = apply_stock_delta(
            mat, delta, transaction_type=kw.get('transaction_type', 'in'),
            reference_type='test', warehouse='仓库A')
        assert ok, msg
        db.session.commit()


def _verify(mid):
    with app_module.app.test_request_context():
        from services.warehouse_stock_service import verify_material_three_ledgers
        return verify_material_three_ledgers(mid)


def _break_ledger(mid, new_stock):
    """人为把 ① 总账改歪（模拟 BUG-2026-09-20-008 型静默账实分裂）。"""
    with app_module.app.test_request_context():
        mat = Material.query.get(mid)
        mat.stock = new_stock
        db.session.commit()


# ────────────────────────── 用例 ──────────────────────────

class TestThreeLedgerGuard:

    def test_verify_material_three_ledgers(self):
        """A9 精确命名：账平时说平、账歪时说歪，且能指出是哪一层歪了。"""
        mid = _seed(location_on=False)
        _entry(mid, 10)                     # ① +10、③ +10
        ok, detail = _verify(mid)
        assert ok, detail
        assert abs(detail['one'] - 10) <= TOL
        assert abs(detail['three'] - 10) <= TOL
        assert detail['location_on'] is False

        _break_ledger(mid, 99)              # 只改 ①，③ 不动 → 账实分裂
        ok, detail = _verify(mid)
        assert not ok, detail
        assert abs(detail['one'] - 99) <= TOL
        assert abs(detail['three'] - 10) <= TOL

    def test_verify_includes_location_ledger_when_enabled(self):
        """开库位时 ② 也参与校验。"""
        mid = _seed(location_on=True)
        _entry(mid, 10)
        ok, detail = _verify(mid)
        assert ok, detail
        assert detail['location_on'] is True
        assert abs(detail['two'] - 10) <= TOL, detail

    def test_guard_warns_without_breaking_when_ledgers_drift(self, monkeypatch):
        """默认（pytest 下自动开）：账歪只告警，不阻断业务。"""
        monkeypatch.delenv("WMS_THREE_LEDGER_ASSERT", raising=False)
        mid = _seed(location_on=False)
        _break_ledger(mid, 50)
        # 账是歪的，但写入照样成功（不许让历史脏数据把正常业务写挂）
        _entry(mid, 5)
        ok, _detail = _verify(mid)
        assert not ok

    def test_guard_strict_raises_on_drift(self, monkeypatch):
        """strict 模式下账歪即抛——证明这套校验真能抓到分叉。"""
        monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", "strict")
        mid = _seed(location_on=False)
        _break_ledger(mid, 50)
        with pytest.raises(AssertionError, match="三账恒等式不成立"):
            _entry(mid, 5)

    def test_guard_off_in_production_mode(self, monkeypatch):
        """生产模式（显式 0）：完全不校验，连查询都不做。"""
        monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", "0")
        mid = _seed(location_on=False)
        _break_ledger(mid, 50)
        _entry(mid, 5)                      # 不抛
        with app_module.app.test_request_context():
            from services.warehouse_stock_service import three_ledger_guard_enabled
            assert three_ledger_guard_enabled() is False

    def test_three_ledger_guard_enabled(self, monkeypatch):
        """A9 精确命名：开关本身要听环境变量的话。"""
        from services.warehouse_stock_service import three_ledger_guard_enabled
        for val in ("1", "true", "yes", "on", "strict", "STRICT"):
            monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", val)
            assert three_ledger_guard_enabled() is True, val
        for val in ("0", "false", "no", "off", "OFF"):
            monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", val)
            assert three_ledger_guard_enabled() is False, val

    def test_three_ledger_guard_strict(self, monkeypatch):
        """A9 精确命名：只有显式 strict 才算致命，其他开法都只告警。"""
        from services.warehouse_stock_service import three_ledger_guard_strict
        monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", "strict")
        assert three_ledger_guard_strict() is True
        for val in ("1", "on", "0", ""):
            monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", val)
            assert three_ledger_guard_strict() is False, val

    def test_guard_three_ledgers(self, monkeypatch):
        """A9 精确命名：账平返回 True；strict + 账歪则抛。"""
        monkeypatch.delenv("WMS_THREE_LEDGER_ASSERT", raising=False)
        mid = _seed(location_on=False)
        _entry(mid, 10)
        with app_module.app.test_request_context():
            from app import Material as _M
            from services.warehouse_stock_service import guard_three_ledgers
            assert guard_three_ledgers(_M.query.get(mid)) is True

        _break_ledger(mid, 77)
        monkeypatch.setenv("WMS_THREE_LEDGER_ASSERT", "strict")
        with app_module.app.test_request_context():
            from app import Material as _M
            from services.warehouse_stock_service import guard_three_ledgers
            with pytest.raises(AssertionError, match="三账恒等式不成立"):
                guard_three_ledgers(_M.query.get(mid))

    def test_entry_keeps_identity_after_in_and_out(self):
        """连做入库/出库后三账仍然平（入口本身没把账写歪）。"""
        mid = _seed(location_on=True)
        _entry(mid, 20, transaction_type='in')
        _entry(mid, -7, transaction_type='out')
        ok, detail = _verify(mid)
        assert ok, detail
        assert abs(detail['one'] - 13) <= TOL, detail
        assert abs(detail['three'] - 13) <= TOL, detail
        assert abs(detail['two'] - 13) <= TOL, detail
