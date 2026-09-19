# -*- coding: utf-8 -*-
"""采购入库明细表「关键词」增加物料名称/规格/品牌快速匹配——回归测试。

背景：`/in_order?type=purchase_in` 的关键词（search 参数）经
`_apply_in_order_search` 做 OR 模糊匹配。此前已覆盖 order_no/business_type/
purpose/供应商名/物料编码/物料名称/物料规格/来源采购单号，**唯独漏了物料品牌**。
本次在 OR 条件补 `Material.brand.like(...)`，与物料联想搜索
（app.py 物料下拉 code/name/spec/brand 四字段）口径对齐。

测试用例：
  T1. 关键词=品牌（西门子）-> 200 且命中单据（品牌维度生效，本次新增）
  T2. 关键词=规格片段（63A）/ 名称片段（断路器）-> 200 且命中（回归，未破坏原有口径）
  T3. 关键词=任意维度都不匹配 -> 200 且结果为空（不误配）
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
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
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# 各维度取值刻意互不重叠，确保 T1 命中只能来自 brand，T2 命中只能来自 spec/name。
ORDER_NO = "IN-BRAND-001"
MAT_CODE = "MCB-4P63A"
MAT_NAME = "微型断路器"
MAT_SPEC = "4P 63A"
MAT_BRAND = "西门子"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="供应商甲")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code=MAT_CODE, name=MAT_NAME, spec=MAT_SPEC, brand=MAT_BRAND,
        category=cat, unit=unit, supplier=sup,
        stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.flush()
    order = InOrder(
        order_no=ORDER_NO,
        date=date.today(),
        business_type="采购入库",
        warehouse="仓库A",
        supplier_id=sup.id,
        status="pending",
    )
    db.session.add(order)
    db.session.flush()
    db.session.add(InOrderItem(
        in_order_id=order.id, material_id=mat.id,
        quantity=5, price=10, amount=50,
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


def _search(keyword: str) -> str:
    client = _make_client()
    resp = client.get(f"/in_order?type=purchase_in&search={keyword}")
    assert resp.status_code == 200, f"关键词[{keyword}]返回 {resp.status_code}，应为 200"
    return resp.data.decode("utf-8", errors="replace")


def test_T1_keyword_matches_brand():
    """本次新增：关键词按物料品牌命中（此前品牌不在 OR 条件内，搜不到）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    body = _search(MAT_BRAND)
    assert ORDER_NO in body, f"按品牌[{MAT_BRAND}]搜索应命中单据 {ORDER_NO}"


def test_T2_keyword_still_matches_spec_and_name():
    """回归：规格/名称匹配不回退（本次仅新增 brand，不得破坏既有口径）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    assert ORDER_NO in _search("63A"), "按规格片段[63A]应命中"
    assert ORDER_NO in _search("断路器"), "按名称片段[断路器]应命中"


def test_T3_keyword_no_match_returns_empty():
    """任意维度都不匹配的关键词 -> 200 且不返回该单据（不误配）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    body = _search("不存在的关键词XYZ")
    assert ORDER_NO not in body, "不匹配的关键词不应返回单据"
