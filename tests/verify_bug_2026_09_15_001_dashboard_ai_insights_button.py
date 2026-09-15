# -*- coding: utf-8 -*-
"""BUG-2026-09-15-001 回归测试：数据仪表盘「AI解读」按钮不得是死按钮。

根因：
- report_dashboard.html 中「AI解读」按钮（onclick=requestAiInsights()）无条件渲染，
  但 requestAiInsights() 函数与结果卡片 aiInsightsCard 都包在 {% if stats %} 内。
- 未选仓库且无默认仓库时 stats=None：按钮渲染、函数缺失 → 点击抛 ReferenceError，
  这是仪表盘无默认仓库时的默认落地态。

修复：
- 按钮同样包进 {% if stats %}，与函数同条件渲染。

验收点：
T1. 无仓库参数且无默认仓库（stats=None）：页面不含 AI解读按钮（不渲染死按钮）。
T2. 显式 warehouse_id（stats 有效）：按钮存在且 requestAiInsights() 已定义。
T3. 不变量：任何分支下「按钮存在」⟺「函数已定义」（防复发：单独加回按钮即失败）。
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
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _login(client):
    r = client.post("/login", data={"username": "admin", "password": "admin",
                                    "login_mode": "user", "usage_consent": "1"})
    assert r.status_code in (200, 302), r.get_data(as_text=True)


import pytest  # noqa: E402


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        # 建一个「非默认」仓库：不设 is_default，保证无参数请求时 stats=None 分支可复现
        from app import Warehouse
        db.session.add(Warehouse(code="WH01", name="测试仓", status="active", is_default=False))
        db.session.commit()
        wid = Warehouse.query.first().id
    c = app_module.app.test_client()
    _login(c)
    yield c, wid
    with app_module.app.app_context():
        from app import Warehouse
        Warehouse.query.delete()
        db.session.commit()


class TestAiInsightsButton:
    def test_t1_no_warehouse_no_dead_button(self, client):
        c, _ = client
        r = c.get("/report/dashboard")
        assert r.status_code == 200, r.get_data(as_text=True)
        html = r.get_data(as_text=True)
        assert "aiInsightsBtn" not in html, "stats=None 时不应渲染 AI解读按钮（死按钮）"
        assert "requestAiInsights" not in html, "stats=None 时函数与按钮都不应出现"

    def test_t2_with_warehouse_button_and_fn_present(self, client):
        c, wid = client
        r = c.get(f"/report/dashboard?warehouse_id={wid}")
        assert r.status_code == 200, r.get_data(as_text=True)
        html = r.get_data(as_text=True)
        assert "aiInsightsBtn" in html, "有仓库数据时 AI解读按钮应存在"
        assert "function requestAiInsights" in html, "有仓库数据时 requestAiInsights() 应已定义"

    def test_t3_button_iff_function_invariant(self, client):
        c, wid = client
        for url in ["/report/dashboard", f"/report/dashboard?warehouse_id={wid}",
                    f"/report/dashboard?warehouse_id=99999"]:
            r = c.get(url)
            assert r.status_code == 200
            html = r.get_data(as_text=True)
            has_btn = "aiInsightsBtn" in html
            has_fn = "function requestAiInsights" in html
            assert has_btn == has_fn, (
                f"{url}: 按钮({has_btn})与函数({has_fn})必须同条件渲染——"
                "按钮无函数=死按钮(ReferenceError)，函数无按钮=死代码"
            )
