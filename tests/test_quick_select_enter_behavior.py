# -*- coding: utf-8 -*-
"""AI-WMS-FILTER-004 回归：筛选框回车直接按关键词搜索（不再默认选中第一项）。

背景（用户反馈）：
    物料档案页输入「电线」按回车，期望右侧列表显示**所有**包含
    「电线」的物料（如「BV电线」「电线电缆」）。实际却被 quick-select
    劫持：菜单可见时 Enter 默认选中第一项候选、回填其物料编码并自动
    提交，列表只剩被选中的那一条。

修复口径（app/static/js/quick-select.js）：
    1. ↑↓ 主动高亮后 Enter = 确认选中该项（精确选择语义不变）；
    2. 搜索型筛选框（data-ks-submit="1"）无主动高亮时 Enter = 放行
       表单默认提交，用当前关键词做模糊搜索；
    3. 纯候选选择框（无 submit 标记）保留「Enter 选中第一项」效率行为；
    4. activeItem() 不再默认回退第一项。

本文件锁住两端：
    - 后端：/material?search=电线 返回所有名称/编码/品牌/规格包含
      「电线」的物料（LIKE %kw% 四字段 or 匹配，此前已具备，防回退）；
    - 前端：quick-select.js 的 Enter 分支契约（防回退）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import Material, MaterialCategory, Unit, User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

QS_JS = (APP_DIR / "static" / "js" / "quick-select.js").read_text(encoding="utf-8")
MATERIAL_HTML = (APP_DIR / "templates" / "material.html").read_text(encoding="utf-8")


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.add_all([
            Unit(name="米", code="M"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        ])
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _mk_material(code, name, spec="", brand=""):
    unit = Unit.query.first()
    cat = MaterialCategory.query.first()
    db.session.add(Material(
        code=code, name=name, spec=spec, brand=brand,
        unit_id=unit.id, category_id=cat.id,
    ))


# ---------------- 后端：关键词包含匹配（用户场景的列表页链路） ----------------

def test_material_list_search_returns_all_substring_matches(client):
    """输入「电线」→ 列表显示所有包含「电线」的物料，不相关的除外。

    覆盖 name / code / brand / spec 四个字段的子串命中。
    """
    with app_module.app.app_context():
        _mk_material("WL-0001", "BV电线", spec="2.5平方")
        _mk_material("WL-0002", "电线电缆", spec="YJV-3x4")
        _mk_material("DX-0003", "护套电线", brand="远东")
        _mk_material("DL-0004", "电力电缆")          # 不含「电线」二字
        _mk_material("PG-0005", "电线管", spec="JDG20")  # 名称含「电线」
        db.session.commit()

    resp = client.get("/material?search=%E7%94%B5%E7%BA%BF")  # URL 编码的「电线」
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    for expect in ("BV电线", "电线电缆", "护套电线", "电线管"):
        assert expect in html, "搜索「电线」应返回包含它的物料：%s" % expect
    assert "电力电缆" not in html, "「电力电缆」不含「电线」，不应出现在结果里"


# ---------------- 前端：quick-select Enter 分支契约（防回退） ----------------

def test_active_item_does_not_fallback_to_first():
    """activeItem() 只认 ↑↓ 主动高亮，不再默认回退第一项。

    这是「Enter 直接搜索」与「Enter 选中候选」能被区分的前提。
    """
    assert "items[0] || null" not in QS_JS, (
        "activeItem() 回退第一项的旧实现又回来了——"
        "它会让搜索框的 Enter 永远等价于选中第一条候选"
    )
    assert "AI-WMS-FILTER-004" in QS_JS, (
        "Enter 新语义的注释标记丢失，请确认改动未被回滚"
    )


def test_enter_released_for_search_boxes_with_submit_flag():
    """搜索型筛选框（data-ks-submit="1"）无主动高亮时，Enter 放行表单提交。"""
    # Enter 分支必须先看主动高亮（activeItem），再按 data-ks-submit 放行
    assert "var picked = activeItem();" in QS_JS
    assert "input.getAttribute('data-ks-submit') !== '1'" in QS_JS, (
        "Enter 分支缺少 data-ks-submit 判断——搜索框回车会退化为选中第一项"
    )


def test_enter_still_picks_first_for_pure_selector_boxes():
    """纯候选选择框（无 submit 标记）保留「Enter 选中第一项」效率行为。"""
    m = re.search(
        r"if \(input\.getAttribute\('data-ks-submit'\) !== '1'\) \{.*?"
        r"commit\(input, items\[0\]\);.*?\}",
        QS_JS, re.S)
    assert m, (
        "无 submit 标记的选择框应保留 Enter 选中第一项的行为，"
        "否则弹窗内实体选择器的键盘效率会回退"
    )


def test_material_page_search_box_is_search_semantics():
    """物料档案页搜索框必须是搜索语义（data-ks-submit="1"）。

    它是用户「输入电线 → 右侧显示所有包含电线的物料」的主入口。
    """
    m = re.search(r'<input[^>]*name="search"[^>]*data-ks="material"[^>]*>', MATERIAL_HTML)
    assert m, "material.html 的搜索框未挂 data-ks=material"
    assert 'data-ks-submit="1"' in m.group(0), (
        "物料搜索框缺少 data-ks-submit=\"1\"，Enter 放行搜索的路径不会生效"
    )
