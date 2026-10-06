# -*- coding: utf-8 -*-
"""BUG-2026-10-06-003：_ai_analysis_low_stock_report 口径修复回归测试。

v1 对话关键词入口（"补货建议/低库存报告"）与 v2 AI 工具 low_stock_report()
同数据必须同结果：全仓汇总口径 + 两级告警（low/danger）+ 开关关闭时不报。

测试环境坑（勿删注释）：
- set_system_setting 不自动 commit，退出 app_context 会回滚 → 必须双 commit
- Material(unit=...) 是 relationship，必须用 unit_id + 预建 Unit
- 跨 context 存 ORM 对象会 DetachedInstanceError → 存 id
- Flask 外层 app_ctx 存活时 test_client 复用同一 g，login_user 泄漏 →
  seed 后必须退出 ctx 再操作 client
"""
import re
import sys
import os
from pathlib import Path

# CI 兼容：不得硬编码沙箱绝对路径（shard-1 曾因 /Coze/Drive/... 收集报错）
APP_DIR = str(Path(__file__).resolve().parents[1] / "app")
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
if not hasattr(app_module, "__path__"):
    app_module.__path__ = [str(APP_DIR)]
app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Warehouse, User, add_stock,
    StockTransaction,
)
from werkzeug.security import generate_password_hash  # noqa: E402


def _reset():
    from sqlalchemy import text
    with db.engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
    db.session.rollback()
    db.drop_all()
    db.create_all()


def setup_seed():
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset()
        admin = User(username="admin", password_hash=generate_password_hash("admin"),
                     role="admin", must_change_password=False)
        db.session.add(admin)
        db.session.add(Warehouse(code="WHA", name="A仓", is_default=True))
        cat = MaterialCategory(code="C1", name="铜排类")
        db.session.add(cat)
        db.session.add(Unit(code="PCS", name="个"))
        db.session.commit()
        app_module.set_system_setting("inventory_alert_enabled", "1")
        # set_system_setting 不会自动提交；不 commit 的话退出 app_context
        # 时该事务回滚（历史踩坑，勿删）。
        db.session.commit()
        return cat.id, admin.id


def make_client():
    c = app_module.app.test_client()
    page = c.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    c.post("/login", data={"username": "admin", "password": "admin",
                           "csrf_token": m.group(1)})
    return c


def get_v1_report(c, keyword="补货建议"):
    """走 AI 对话入口触发 v1 报告（LLM 未配置时本地规则触发）。"""
    from flask import session as flask_session  # noqa: F401
    r = c.post("/ai/chat", json={"message": keyword})
    return r


class TestBug20261006003:
    def test_v1_report_matches_v2_tool(self):
        """B1/B2：v1 与 v2 同数据同结果（danger 档也进报告；数字口径一致）。"""
        cat_id, _ = setup_seed()
        with app_module.app.app_context():
            # M001：min=5 / reorder=10 / 全仓库存 8 → danger 档
            db.session.add(Material(code="M001", name="铜排", spec="T2",
                                    category_id=cat_id, unit_id=1, stock=8,
                                    price=10, min_stock=5, reorder_point=10,
                                    max_stock=50))
            # M002：min=3 / 无 reorder / 库存 10 → normal，不进报告
            db.session.add(Material(code="M002", name="绝缘子", spec="10kV",
                                    category_id=cat_id, unit_id=1, stock=10,
                                    price=5, min_stock=3, reorder_point=None,
                                    max_stock=40))
            db.session.commit()
        c = make_client()
        from ai.tools.inventory import low_stock_report
        with app_module.app.app_context():
            v2 = low_stock_report()
        codes_v2 = sorted(r["code"] for r in v2)
        assert codes_v2 == ["M001"], f"v2 应只报 M001（danger），实际 {codes_v2}"
        v2_row = v2[0]
        assert v2_row["alert_status"] == "danger"
        # v2 shortage 按 safety_stock 口径：10-8=2
        assert v2_row["shortage"] == 2

        # v1：直接调函数验证（不经 /ai/chat 的意图分发，避免 LLM 配置影响）
        with app_module.app.app_context():
            report = app_module._ai_analysis_low_stock_report()
        # v1 报告必须包含 M001 且不包含 M002
        assert "M001" in report, f"v1 报告应含 M001（danger 档）：\n{report}"
        assert "M002" not in report, f"v1 报告不应含 M002（normal）：\n{report}"
        # v1 的当前库存列必须与 v2 quantity 一致（都是 8，全仓口径）
        for line in report.splitlines():
            if "M001" in line:
                cells = [cell.strip() for cell in line.split("|")]
                # | M001 | 名称 | 8 | 5 | 建议补货 |
                assert cells[3] == "8", f"v1 当前库存应为 8：{line}"

    def test_v1_report_off_switch(self):
        """B3：开关关闭时 v1 不报低库存（与 v2 disabled 口径一致）。"""
        cat_id, _ = setup_seed()
        with app_module.app.app_context():
            db.session.add(Material(code="M001", name="铜排", spec="T2",
                                    category_id=cat_id, unit_id=1, stock=8,
                                    price=10, min_stock=5, reorder_point=10))
            db.session.commit()
            app_module.set_system_setting("inventory_alert_enabled", "0")
            db.session.commit()
            report = app_module._ai_analysis_low_stock_report()
        assert "未启用" in report, f"开关关闭应提示未启用：\n{report}"
        assert "M001" not in report

    def test_v1_report_warehouse_stock_source(self):
        """B4：v1 库存读数必须来自全仓汇总（库位账），不是 Material.stock 总账列。

        构造：两仓系统（单仓有总账回退兜底，测不出差异），
        M001 总账 stock=999（脏数据），仅 B仓有流水 +5 →
        全仓汇总=5 ≤ min_stock(5) → 应报 low；
        若实现错误地读总账列 999，会误判 normal 而漏报。
        """
        cat_id, _ = setup_seed()
        with app_module.app.app_context():
            db.session.add(Material(code="M001", name="铜排", spec="T2",
                                    category_id=cat_id, unit_id=1, stock=999,
                                    price=10, min_stock=5, reorder_point=10))
            db.session.add(Warehouse(code="WHB", name="B仓"))
            db.session.commit()
            from app import StockTransaction
            from datetime import datetime
            db.session.add(StockTransaction(
                material_id=1, quantity=5, transaction_type="in",
                warehouse_id=2, location="B仓",
                created_at=datetime.now()))
            db.session.commit()
            report = app_module._ai_analysis_low_stock_report()
        assert "M001" in report, (
            f"两仓系统：总账 999 但 B仓流水仅 5 → 全仓汇总 5≤min_stock 应报 low；"
            f"若未报说明 v1 仍在读总账列：\n{report}"
        )
