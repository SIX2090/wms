# -*- coding: utf-8 -*-
"""BUG-2026-09-20-005 回归：启动回填在空库/未建表时不再刷 ERROR traceback。

背景：``backfill_stock_txn_warehouse_id()`` 在 ``app/app.py`` 模块**导入期**
执行，而 ``initialize_database()``（建表）发生在导入期之后。CI / 全新部署的
空库场景下 ``warehouse`` 表尚不存在，函数第一步 ``Warehouse.query.all()`` 即抛
``sqlite3.OperationalError: no such table: warehouse``，被外层 ``except`` 捕获
后记一整组 ERROR traceback（「下次启动重试」）。虽不阻断开机，但每个 verify
脚本/每次导入都刷一组完整堆栈，与真实故障混在一起，削弱日志可读性。

修复：新增 ``_stock_txn_backfill_ready()`` 前置表存在性探测
（``sqlalchemy.inspect(...).has_table``），任一前置表缺失即返回 False，调用方
降级为 INFO 静默跳过；探测本身失败也返回 False（宁可静默跳过，回填幂等，下次
启动重试），绝不在导入期抛异常。

验收：
T1. 三张前置表齐备 → _stock_txn_backfill_ready() 返回 True。
T2. 缺 warehouse 表（BUG 原始场景，空库）→ 返回 False，且不抛异常。
T3. 缺 stock_transaction 表 → 返回 False。
T4. 缺 location_inventory 表 → 返回 False。
T5. 引擎不可用（探测本身抛异常）→ 返回 False，不向上抛。
T6. 正常库上 backfill 仍可执行（守卫未误伤治本路径）。
T7. 接线校验：模块级调用点先探测再回填，且不再裸调 backfill（防回归）。
"""
from __future__ import annotations

import os
import sys
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
    db, Material, MaterialCategory, StockTransaction, Unit, Warehouse,
    _stock_txn_backfill_ready, backfill_stock_txn_warehouse_id,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_REQUIRED_TABLES = ("stock_transaction", "warehouse", "location_inventory")


class _FakeInspector:
    """按给定表名集合模拟 sqlalchemy Inspector.has_table()。"""

    def __init__(self, present):
        self._present = set(present)

    def has_table(self, name):
        return name in self._present


def _patch_inspector(present):
    """把 app 模块内 sa_inspect(db.engine) 替换为假 inspector。"""
    return mock.patch(
        "sqlalchemy.inspect",
        return_value=_FakeInspector(present),
    )


class TestBackfillReadinessProbe:

    def test_all_tables_present_returns_true(self):
        """T1：三张前置表齐备 → True（正常库/生产路径）。"""
        with _patch_inspector(_REQUIRED_TABLES):
            assert _stock_txn_backfill_ready() is True

    def test_missing_warehouse_returns_false(self):
        """T2：缺 warehouse（BUG 原始空库场景）→ False，不抛异常。"""
        present = {"stock_transaction", "location_inventory"}
        with _patch_inspector(present):
            assert _stock_txn_backfill_ready() is False

    def test_missing_stock_transaction_returns_false(self):
        """T3：缺 stock_transaction → False。"""
        present = {"warehouse", "location_inventory"}
        with _patch_inspector(present):
            assert _stock_txn_backfill_ready() is False

    def test_missing_location_inventory_returns_false(self):
        """T4：缺 location_inventory → False。"""
        present = {"stock_transaction", "warehouse"}
        with _patch_inspector(present):
            assert _stock_txn_backfill_ready() is False

    def test_empty_database_returns_false(self):
        """T2 变体：完全空库（一表未建）→ False。"""
        with _patch_inspector(set()):
            assert _stock_txn_backfill_ready() is False

    def test_probe_exception_returns_false(self):
        """T5：探测本身失败 → False，绝不向上抛（导入期安全）。"""
        with mock.patch("sqlalchemy.inspect", side_effect=RuntimeError("engine down")):
            assert _stock_txn_backfill_ready() is False


class TestBackfillStillWorks:

    def test_backfill_runs_on_real_db(self):
        """T6：守卫未误伤——建好表的真库上 backfill 仍正常执行。"""
        with app_module.app.test_request_context():
            db.drop_all()
            db.create_all()
            db.session.add_all([
                Unit(name="个", code="PCS"),
                MaterialCategory(name="默认分类", code="CAT"),
                Warehouse(id=1, code="WHA", name="仓库A", is_default=True,
                          status="active"),
            ])
            db.session.commit()
            mat = Material(code="M001", name="轴承", spec="6204",
                           category_id=1, unit_id=1, stock=0, price=10)
            db.session.add(mat)
            db.session.commit()
            # 一条 location 为仓库名的历史流水，应被回填
            db.session.add(StockTransaction(
                material_id=mat.id, transaction_type="in", quantity=5,
                location="仓库A", reference_type="in_order", reference_id=1,
            ))
            db.session.commit()

            # 真库上探测应为 True
            assert _stock_txn_backfill_ready() is True
            n = backfill_stock_txn_warehouse_id()
            assert n == 1, f"应回填 1 条，实际 {n}"
            txn = StockTransaction.query.first()
            assert txn.warehouse_id == 1

            # 幂等：再跑一次应为 0
            assert backfill_stock_txn_warehouse_id() == 0


class TestStartupWiring:

    def test_guard_precedes_backfill_call(self):
        """T7：模块级调用点必须先探测再回填（防回归为裸调）。"""
        app_py = Path(__file__).resolve().parents[1] / "app" / "app.py"
        text = app_py.read_text(encoding="utf-8")
        probe_idx = text.find("if not _stock_txn_backfill_ready():")
        call_idx = text.find("_backfilled = backfill_stock_txn_warehouse_id()")
        assert probe_idx > 0, "BUG-2026-09-20-005 复发：启动接线缺少前置表探测"
        assert call_idx > 0, "backfill 启动调用缺失"
        assert probe_idx < call_idx, (
            "BUG-2026-09-20-005 复发：backfill 调用必须先经 "
            "_stock_txn_backfill_ready() 守卫"
        )
