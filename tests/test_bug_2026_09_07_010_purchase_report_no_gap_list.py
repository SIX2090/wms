# -*- coding: utf-8 -*-
"""BUG-2026-09-07-010 回归：采购报表页撤下「缺失报表差距清单」。

背景：/purchase_report 页面把 6 项「缺少报表 / 当前差距 / 优先级」直接
展示给最终用户——产品路线图应在开发台账跟踪，业务页面只呈现可用能力。

断言：
  T1. /purchase_report 页面不再出现「缺少报表」「当前差距」「优先级」。
  T2. 可用报表卡片仍正常渲染（可用能力不回归）。
  T3. 路由不再向模板传 missing_reports（源码锚点）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


class TestBug20260907010:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            db.session.add(User(username="admin",
                                password_hash=generate_password_hash("admin"),
                                role="admin", must_change_password=False))
            db.session.commit()

    def _page(self):
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get("/purchase_report")
        assert r.status_code == 200
        return r.get_data(as_text=True)

    def test_T1_gap_list_removed(self):
        html = self._page()
        for text in ("缺少报表", "当前差距", "missing_reports", "采购退货统计"):
            assert text not in html, f"页面不得再展示缺失清单内容: {text}"

    def test_T2_available_reports_kept(self):
        html = self._page()
        for text in ("采购订单执行统计表", "供应商采购汇总表", "采购价格分析表"):
            assert text in html, f"可用报表卡片不得受影响: {text}"

    def test_T3_route_no_longer_passes_missing_reports(self):
        src = (APP_DIR / "routes" / "report.py").read_text(encoding="utf-8")
        assert "missing_reports" not in src, "路由不得再构造/传 missing_reports"
