# -*- coding: utf-8 -*-
"""BUG-2026-10-05-003 回归：AI 库存工具 Stock 导入错误 + A11 仓库级口径。

根因：app/ai/tools/inventory.py 4 处 `from app import db, Material, Stock`
引用已废弃的 Stock 模型（app.py 无该类），调用 material_query /
inventory_health / low_stock_report / stock_value_analysis 即 ImportError 500。

修复（v2，A11 合规）：
  - material_query / inventory_health / low_stock_report：改
    get_all_warehouses_stock_quantities() 全仓汇总口径（Σ②库位账），
    不回退全局 Material.stock；
  - stock_value_analysis：纯展示聚合，保留 material.stock 并加
    `# stock-truth:reason=` 豁免注释（INVENTORY_TRUTH.md §5）。

测试用例：
  T1. 四个工具函数全部可调用且返回结构正确（无 ImportError）。
  T2. 仓库级口径断言：仅 A 仓入库 20 件时 quantity=20、low_stock_report
      不误报（阈值 5）、health 无低库存/负库存计数；价值分析走总账
      （①总账 20）仍得 200。
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

import app as app_module  # noqa: E402
if not hasattr(app_module, "__path__"):
    app_module.__path__ = [str(APP_DIR)]
from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Warehouse, User, add_stock,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed():
    db.drop_all()
    db.create_all()
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
        admin,
    ])
    db.session.commit()
    mat = Material(code="M001", name="铜排", spec="T2",
                   category_id=1, unit_id=1, stock=0, price=10, min_stock=5)
    db.session.add(mat)
    db.session.commit()
    return mat, admin


class TestAIInventoryTools:

    def test_tools_callable_and_structure(self):
        """T1：四工具无 ImportError，返回结构正确。"""
        with app_module.app.app_context():
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="仓库A")
                assert ok, err
                db.session.commit()

            from app.ai.tools.inventory import (
                material_query, inventory_health, low_stock_report,
                stock_value_analysis,
            )
            r1 = material_query("铜排")
            assert r1 and r1[0]["code"] == "M001"
            r2 = inventory_health()
            assert {"health_score", "low_stock_count", "negative_stock_count",
                    "slow_moving_count", "materials"} <= set(r2.keys())
            assert isinstance(low_stock_report(), list)
            r4 = stock_value_analysis()
            assert {"total_value", "material_count", "by_category"} <= set(r4.keys())

    def test_warehouse_scope_not_global(self):
        """T2：仓库级口径断言（A11）——A 仓 20 件，阈值 5。"""
        with app_module.app.app_context():
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="仓库A")
                assert ok, err
                db.session.commit()

            from app.ai.tools.inventory import (
                material_query, inventory_health, low_stock_report,
                stock_value_analysis,
            )
            # material_query 走全仓汇总（Σ②）：A 仓 20 → quantity=20
            r1 = material_query("铜排")
            assert r1[0]["quantity"] == 20, f"仓库级口径错误: {r1}"
            assert r1[0]["alert_status"] == "normal"

            # 低库存判定不误报（20 > 5）
            assert low_stock_report() == []

            # 健康度：无低库存/负库存；slow_moving（无出库流水）正常计 1
            r2 = inventory_health()
            assert r2["low_stock_count"] == 0
            assert r2["negative_stock_count"] == 0

            # 价值分析：展示口径走总账①（add_stock 已同步 ①=20），200
            r4 = stock_value_analysis()
            assert r4["total_value"] == 200.0
            assert r4["material_count"] == 1
