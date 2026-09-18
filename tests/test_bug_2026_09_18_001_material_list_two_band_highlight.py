# -*- coding: utf-8 -*-
"""BUG-2026-09-18-001 回归：物料档案列表高亮对齐两级判定。

背景（R6 同类点排查）：AI-CI-GREEN-005-F04/F05 把「两级判定」（low=破最低库存
红线、danger=破安全库存预警线）统一到了 /alert 页、首页、库存查询页和手机端，
但**物料档案列表**（`/material`，`material.html`）的行高亮仍是旧的单级逻辑
`stock <= min_stock` —— 低于安全库存（danger 档）但高于最低库存的物料在列表里
**完全不被标注**，而这正是两级化要消灭的"同一批物料不同页面不同答案"。

本测试把列表高亮钉死为两级：
  low    = stock <= min_stock                 → table-danger / text-danger（红）
  danger = min_stock < stock <= safety_stock  → table-warning / text-warning（黄）
  （safety_stock = max(reorder_point, min_stock)，与 /alert 页同口径）

注：物料列表用全局 Material.stock（管理总览视角），本测试据此构造全局库存。
"""
from __future__ import annotations

import os
import re
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
from app import db, User, Material  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login_client():
    """建库 + 建 admin + 开预警开关，返回已登录的 web client。"""
    from werkzeug.security import generate_password_hash

    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()

    client = app_module.app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return client


def _seed(code, *, min_stock=0.0, reorder_point=0.0, stock=0.0):
    with app_module.app.app_context():
        m = Material(code=code, name=f"物料{code}", stock=stock,
                     min_stock=min_stock, reorder_point=reorder_point)
        db.session.add(m)
        db.session.commit()


def _render_material_page(client):
    resp = client.get("/material?per_page=200")
    assert resp.status_code == 200, resp.get_data(as_text=True)[:500]
    return resp.get_data(as_text=True)


def _row_classes(html, code):
    """返回 (该行 <tr> 的 class, 该行 stock 列 <td> 的 class)。"""
    m = re.search(r'<tr[^>]*>.*?' + re.escape(code) + r'.*?</tr>', html, re.DOTALL)
    assert m, f"页面里找不到物料 {code} 的行"
    row = m.group(0)
    tr_cls = re.search(r'<tr[^>]*class="([^"]*)"', row)
    tr_cls = tr_cls.group(1) if tr_cls else ''
    stock_td = re.search(r'<td data-column-key="stock"[^>]*class="([^"]*)"', row)
    stock_td = stock_td.group(1) if stock_td else ''
    return tr_cls, stock_td


def test_danger_band_row_highlighted_yellow():
    """T1：danger 档（低于安全库存但高于最低库存）必须标黄——旧单级逻辑完全漏掉它。"""
    client = _login_client()
    _seed("M-DANGER", min_stock=10, reorder_point=50, stock=30)  # 10<30<=50 → danger
    html = _render_material_page(client)
    tr_cls, stock_td = _row_classes(html, "M-DANGER")
    assert "table-warning" in tr_cls, (
        f"danger 档整行应 table-warning 标黄，实际 class={tr_cls!r}；"
        "若为空说明列表仍是只比 min_stock 的旧单级逻辑"
    )
    assert "text-warning" in stock_td, f"danger 档库存数字应 text-warning，实际 {stock_td!r}"
    assert "table-danger" not in tr_cls, "danger 档不应误标为红色 low 档"


def test_low_band_row_highlighted_red():
    """T2：low 档（破最低库存红线）必须标红（与 /alert 页 low=红 一致）。"""
    client = _login_client()
    _seed("M-LOW", min_stock=10, reorder_point=50, stock=5)  # 5<=10 → low
    html = _render_material_page(client)
    tr_cls, stock_td = _row_classes(html, "M-LOW")
    assert "table-danger" in tr_cls, f"low 档整行应 table-danger 标红，实际 {tr_cls!r}"
    assert "text-danger" in stock_td, f"low 档库存数字应 text-danger，实际 {stock_td!r}"


def test_normal_and_disabled_not_highlighted():
    """T3：正常与未设阈值的物料不得标注任何预警色。"""
    client = _login_client()
    _seed("M-OK", min_stock=10, reorder_point=50, stock=80)  # 80>50 → normal
    _seed("M-X", min_stock=0, reorder_point=0, stock=0)      # 未设阈值 → disabled
    html = _render_material_page(client)

    tr_cls, stock_td = _row_classes(html, "M-OK")
    assert "table-danger" not in tr_cls and "table-warning" not in tr_cls, (
        f"正常物料不应标预警色，实际 {tr_cls!r}"
    )
    assert "text-danger" not in stock_td and "text-warning" not in stock_td

    tr_cls, stock_td = _row_classes(html, "M-X")
    assert "table-danger" not in tr_cls and "table-warning" not in tr_cls, (
        f"未设阈值物料不应标预警色，实际 {tr_cls!r}"
    )


def test_only_safety_set_still_flags_danger():
    """T4：只设安全库存（min_stock=0, reorder_point=50）、库存 30 → 仍应标黄。

    safety_stock = max(50, 0) = 50，30 <= 50 且 30 > min(0) → danger。
    这是"只设安全库存"物料在旧单级逻辑下永远漏报的场景。
    """
    client = _login_client()
    _seed("M-SAFEONLY", min_stock=0, reorder_point=50, stock=30)
    html = _render_material_page(client)
    tr_cls, _ = _row_classes(html, "M-SAFEONLY")
    assert "table-warning" in tr_cls, (
        f"只设安全库存且库存 30<=50 应标黄，实际 {tr_cls!r}"
    )
