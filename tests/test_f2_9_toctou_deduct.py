# -*- coding: utf-8 -*-
"""F2.9：TOCTOU 并发扣减加固（审计 §1.2 高危）回归测试。

核心缺陷：``deduct_stock_atomic`` 原实现是「先 SELECT ``get_warehouse_stock_quantities``
做仓库级校验 → 再条件 UPDATE 扣总账」两条语句，之间存在窗口——两个并发出库请求都读到
「仓库库存充足」，随后各自 UPDATE 成功（总账条件 ``Material.stock >= qty`` 仍成立），
仓库账被扣成负数。

修复：把仓库级校验下推为 UPDATE ... WHERE 的相关子查询（``_wh_stock_guards``），
使「校验 + 扣减」成为**同一条原子 SQL**；移动端/原生端出库另在路由层取
``BEGIN IMMEDIATE`` 写锁串行化（见 routes/mobile.py、routes/native_api.py）。

本文件用**确定性交错**模拟两并发请求（repo 既有写锁测试同式——内存库无法跨线程共享，
故不用真线程）：先让请求 A 读到过期的「充足」快照，再由请求 B 真正扣减，最后让 A 的
条件 UPDATE 执行——断言 A 被原子守卫拒绝、仓库账不为负。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")

from sqlalchemy import func  # noqa: E402

import app as app_module  # noqa: E402
from app import (Material, StockTransaction, Warehouse,  # noqa: E402
                 _wh_stock_guards, db, deduct_stock_atomic, set_system_setting)

app_module.app.config["TESTING"] = True


def _reset():
    db.drop_all()
    db.create_all()


def _mk_warehouse(code, name):
    w = Warehouse(code=code, name=name)
    db.session.add(w)
    db.session.commit()
    return w


def _mk_material(code, stock):
    m = Material(code=code, name=code, stock=stock)
    db.session.add(m)
    db.session.commit()
    return m


def _add_txn(material_id, warehouse_id, qty, location=None):
    db.session.add(StockTransaction(
        material_id=material_id, transaction_type='in',
        quantity=qty, warehouse_id=warehouse_id, location=location))
    db.session.commit()


def _wh_net(material_id, warehouse_id):
    return float(db.session.query(func.coalesce(func.sum(StockTransaction.quantity), 0))
                 .filter(StockTransaction.material_id == material_id,
                         StockTransaction.warehouse_id == warehouse_id).scalar() or 0)


class TestWhStockGuards:
    """``_wh_stock_guards`` 各门控分支：仅当 SQL 口径与 Python 校验等价时才下推。"""

    def test_returns_condition_when_equivalent(self):
        with app_module.app.app_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 5.0)
            guards = _wh_stock_guards(m.id, w1, 4)
            assert len(guards) == 1, "多仓 + 有归属流水 → 应下推仓库级守卫"

    def test_skips_single_warehouse(self):
        # 单仓系统：仓库级 == 全局总账，既有 Material.stock>=qty 条件已覆盖
        with app_module.app.app_context():
            _reset()
            w1 = _mk_warehouse("WH001", "唯一仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 5.0)
            assert _wh_stock_guards(m.id, w1, 4) == []

    def test_skips_when_location_management_enabled(self):
        with app_module.app.app_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 5.0)
            set_system_setting('location_management_enabled', '1')
            db.session.commit()
            try:
                assert _wh_stock_guards(m.id, w1, 4) == []
            finally:
                set_system_setting('location_management_enabled', '0')
                db.session.commit()

    def test_skips_unattributed_material(self):
        # 物料库存全部无法归属（warehouse_id/location 全空）→ 回退总账，不下推
        with app_module.app.app_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, None, 5.0, location=None)
            assert _wh_stock_guards(m.id, w1, 4) == []

    def test_skips_when_allow_negative_stock(self):
        with app_module.app.app_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 5.0)
            set_system_setting('allow_negative_stock', '1')
            db.session.commit()
            try:
                assert _wh_stock_guards(m.id, w1, 4) == []
            finally:
                set_system_setting('allow_negative_stock', '0')
                db.session.commit()


class TestToctouDeduct:
    """确定性交错模拟并发双扣：仓库账绝不为负。

    用 ``test_request_context``（同时提供 app 与 request 上下文）——扣减成功路径会写
    StockTransaction 并访问 ``current_user``，需请求上下文才能解析为匿名用户。
    """

    def test_stale_snapshot_is_caught_by_atomic_guard(self, monkeypatch):
        """A 读到过期快照(5) → B 已把 W1 扣到 1 → A 的条件 UPDATE 必须被守卫拒绝。"""
        with app_module.app.test_request_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            w2 = _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            # 真实仓库账：W1 只有 1（另 4 在 W2）；总账 5。
            _add_txn(m.id, w1.id, 1.0)
            _add_txn(m.id, w2.id, 4.0)

            # 模拟并发窗口：A 读到的是 B 扣减之前的「过期充足快照」。
            monkeypatch.setattr(app_module, "get_warehouse_stock_quantities",
                                lambda wh: {m.id: 5.0})
            ok, err, mat = deduct_stock_atomic(
                m.id, 4, transaction_type='out', warehouse=w1)

            assert ok is False, "过期快照下的扣减必须被原子守卫拒绝（否则仓库账为负）"
            assert ('并发' in (err or '')) or ('不足' in (err or '')), err

            db.session.expire_all()
            # 账面不为负：总账与 W1 仓库净额均未变化
            assert Material.query.get(m.id).stock == 5.0
            assert _wh_net(m.id, w1.id) == 1.0

    def test_normal_deduct_succeeds_when_warehouse_sufficient(self):
        with app_module.app.test_request_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 5.0)

            ok, err, mat = deduct_stock_atomic(
                m.id, 3, transaction_type='out', warehouse=w1)
            assert ok is True, err

            db.session.expire_all()
            assert Material.query.get(m.id).stock == 2.0
            assert _wh_net(m.id, w1.id) == 2.0

    def test_guard_counts_legacy_null_warehouse_location_rows(self):
        """历史遗留行（warehouse_id NULL，location==仓库名）应计入下推口径。"""
        with app_module.app.test_request_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, None, 5.0, location=w1.name)

            ok, err, mat = deduct_stock_atomic(
                m.id, 4, transaction_type='out', warehouse=w1)
            assert ok is True, err
            db.session.expire_all()
            assert Material.query.get(m.id).stock == 1.0

    def test_python_precheck_still_rejects_plain_insufficiency(self):
        """非并发场景：Python 侧仓库校验先行拒绝（不进入 UPDATE）。"""
        with app_module.app.test_request_context():
            _reset()
            w1 = _mk_warehouse("WH001", "一号仓")
            w2 = _mk_warehouse("WH002", "二号仓")
            m = _mk_material("M001", 5.0)
            _add_txn(m.id, w1.id, 1.0)
            _add_txn(m.id, w2.id, 4.0)

            ok, err, mat = deduct_stock_atomic(
                m.id, 4, transaction_type='out', warehouse=w1)
            assert ok is False
            assert '不足' in (err or '')
            db.session.expire_all()
            assert Material.query.get(m.id).stock == 5.0
