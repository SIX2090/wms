# -*- coding: utf-8 -*-
"""P2 物料选择改服务端搜索 —— 首屏裁剪 + 联想走 API + 编辑草稿不丢物料。

背景：新增入库单页原把**全部物料**（Material.query.all()）序列化后内联进
HTML，前端全量缓存 + filter。物料上万时：①首屏 HTML 体积与解析耗时线性增长；
②新建物料档案后必须手动「刷新物料」（或输入未命中时自动补刷新）才可见。

本次改造：
  * 首屏只内联「初始缓存」：编辑草稿单时单据已有物料 + 按编码升序前 300 条
  * 前端联想改为请求 /api/material/search（服务端按 编码/名称/规格/品牌 匹配，
    带防抖与请求序号防竞态），本地缓存降级为网络异常兜底
  * 点击下拉项时若缓存缺失，回源 /api/material/search 精确取一次

测试用例：
  T1. 首屏内联物料数被裁剪（不随物料总量线性增长）
  T2. 编辑草稿单时，单据已有物料必须仍在内联缓存中（否则渲染不出名称）
  T3. 模板已改为服务端搜索（含防抖、竞态保护、降级兜底）
  T4. /api/material/search 支持按名称与品牌模糊匹配（前端依赖的口径）
"""
from __future__ import annotations

import os
import re
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import db, Warehouse, User, Material, InOrder, InOrderItem, Unit  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

IN_ADD = APP_DIR / "templates" / "in_order_add.html"
CACHE_LIMIT = 300


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(with_materials=0):
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    unit = Unit(code="PCS", name="个")
    db.session.add_all([wh, user, unit])
    db.session.flush()
    for i in range(with_materials):
        db.session.add(Material(
            code=f"M{i:05d}", name=f"物料{i}", spec=f"S{i}", brand="品牌A", unit_id=unit.id, price=1.0, stock=0,
        ))
    db.session.commit()


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _inline_materials(body: str) -> list:
    """从页面里抽出 `const materials = [...]` 内联的物料数组。"""
    m = re.search(r"const materials = (\[.*?\]);\n", body, re.S)
    assert m, "页面应内联 const materials = [...]"
    import json
    return json.loads(m.group(1))


def test_T1_initial_cache_is_truncated():
    """物料 700 条时，首屏内联应被裁剪到初始缓存上限。"""
    with app_module.app.app_context():
        _reset_db()
        _seed(with_materials=700)
    body = _make_client().get("/in_order/add").data.decode("utf-8", errors="replace")
    inline = _inline_materials(body)
    assert len(inline) <= CACHE_LIMIT, \
        f"首屏内联物料应 <= {CACHE_LIMIT} 条，实际 {len(inline)}"


def test_T2_draft_order_materials_kept_in_cache():
    """编辑草稿单时，单据已有明细引用的物料必须仍在内联缓存里。"""
    with app_module.app.app_context():
        _reset_db()
        _seed(with_materials=700)
        # 取一条编码排在末尾的物料（必然不在前 300 条内）
        late = Material.query.order_by(Material.code.desc()).first()
        late_code = late.code
        order = InOrder(order_no="IN-P2-001", warehouse="仓库A", business_type="采购入库", status="pending")
        db.session.add(order)
        db.session.flush()
        db.session.add(InOrderItem(
            in_order_id=order.id, material_id=late.id,
            quantity=1, price=1.0, amount=1.0,
        ))
        db.session.commit()
        order_id = order.id

    body = _make_client().get(f"/in_order/add?order_id={order_id}").data.decode("utf-8", errors="replace")
    inline = _inline_materials(body)
    codes = {m.get("code") for m in inline}
    assert late_code in codes, \
        f"草稿单引用的物料 {late_code} 必须在初始缓存内（否则渲染不出名称）"
    assert late_code in body, "页面应能显示草稿单该行物料"


def test_T3_template_uses_server_side_search():
    """模板已改为服务端搜索：含 API 调用、防抖、竞态保护与本地降级。"""
    src = IN_ADD.read_text(encoding="utf-8")
    assert "/api/material/search" in src, "前端应调用 /api/material/search"
    assert "MATERIAL_SEARCH_LIMIT_HINT" in src, "应有搜索上限常量"
    body = src[src.index("function showDropdown("):]
    body = body[:body.index("function selectMaterial(")]
    assert "clearTimeout" in body and "setTimeout" in body, "服务端搜索应做防抖"
    assert "materialSearchState" in body and "seq" in body, "应有请求序号防竞态"
    assert "filterLocalMaterials" in body, "网络异常时应降级为本地缓存过滤"


def test_T4_search_api_matches_name_and_brand():
    """/api/material/search 按 名称 / 品牌 模糊匹配（前端联想的服务端口径）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed(with_materials=0)
        unit = Unit.query.first()
        db.session.add_all([
            Material(code="MAT-A", name="不锈钢螺栓", spec="M8", brand="东明", unit_id=unit.id, price=1, stock=0),
            Material(code="MAT-B", name="橡胶垫片", spec="DN50", brand="华信", unit_id=unit.id, price=1, stock=0),
        ])
        db.session.commit()

    client = _make_client()
    # 按名称命中
    res = client.get("/api/material/search?kw=螺栓").get_json()
    assert res.get("status") == "success", res
    codes = {m["code"] for m in res.get("data", [])}
    assert "MAT-A" in codes, "按名称应能命中"
    assert "MAT-B" not in codes, "不应返回无关物料"

    # 按品牌命中
    res = client.get("/api/material/search?kw=华信").get_json()
    codes = {m["code"] for m in res.get("data", [])}
    assert "MAT-B" in codes, "按品牌应能命中"
