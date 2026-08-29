# -*- coding: utf-8 -*-
"""BUG-2026-08-29-003：采购入库明细表供应商手工输入（不点选下拉）筛选失效。

根因：in_order.html 的供应商筛选 JS 只做「全名/全编码精确匹配」回填
supplier_id（findSupplierByName 用 ===），手工输入部分名称（如「欧姆」）
时 hidden.supplier_id 为空，提交后供应商条件整体失效——占位文案却写着
「输入名称快速匹配」。合同编号/工程名称后端本就是 %kw% 模糊，无需改。

修复：
① app.py 新增共享 helper _apply_order_partner_text_filter（按名称/编码
  contains 大小写不敏感匹配往来单位 supplier/customer）；
② in_order_list 与 export_in_order：supplier_id 为空时回退 supplier_name 模糊；
③ in_order.html 输入框补 name="supplier_name"，分页/导出/清除链接回填该参数。

T1. 部分名称「欧姆」能匹配「欧姆电气」的入库单。
T2. 部分编码（大小写不敏感）也能匹配。
T3. 往来来源为客户的其他入库单同样按客户名模糊匹配。
T4. 空关键词不过滤（返回全部）。
T5. 无匹配关键词 → 0 条。
T6. 路由/导出/模板契约：in_order.py 与 export.py 在 supplier_id 为空时回退
    supplier_name；in_order.html 输入框带 name=supplier_name 且分页、导出、
    清除链接均回填该参数。
"""
from __future__ import annotations

import os
import re
import sys
import uuid
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
from app import (  # noqa: E402
    Customer, InOrder, Supplier, _apply_order_partner_text_filter, db,
)

import pytest  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture(autouse=True)
def _app_ctx():
    """每个用例包在 app context 内（db 操作必需）。"""
    with app_module.app.app_context():
        yield

IN_ORDER_PY = (ROOT / "app" / "routes" / "in_order.py").read_text(encoding="utf-8")
EXPORT_PY = (ROOT / "app" / "routes" / "export.py").read_text(encoding="utf-8")
TPL = (ROOT / "app" / "templates" / "in_order.html").read_text(encoding="utf-8")


def _fresh_db():
    db.drop_all()
    db.create_all()


def _uid():
    return uuid.uuid4().hex[:8]


def _seed():
    """三张入库单：欧姆电气（采购入库）/ 石湾精工（采购入库）/ 东莞万通（客户，其他入库）。"""
    _fresh_db()
    s1 = Supplier(name="欧姆电气有限公司", code="SUP-OM-" + _uid())
    s2 = Supplier(name="石湾精工螺丝", code="SUP-BW-" + _uid())
    c1 = Customer(name="东莞万通电气实业有限公司", code="CUS-WT-" + _uid())
    db.session.add_all([s1, s2, c1])
    db.session.flush()
    o1 = InOrder(order_no="IN-T1-" + _uid(), warehouse="WH001", supplier_id=s1.id)
    o2 = InOrder(order_no="IN-T2-" + _uid(), warehouse="WH001", supplier_id=s2.id)
    o3 = InOrder(order_no="IN-T3-" + _uid(), warehouse="WH001", customer_id=c1.id,
                 business_type="其他入库")
    db.session.add_all([o1, o2, o3])
    db.session.commit()
    return o1, o2, o3


def _filtered(kw):
    q = db.session.query(InOrder)
    return _apply_order_partner_text_filter(q, InOrder, kw).all()


def test_t1_partial_name_matches():
    o1, _, _ = _seed()
    got = _filtered("欧姆")
    assert [o.id for o in got] == [o1.id], "部分名称「欧姆」应匹配「欧姆电气」的入库单"


def test_t2_partial_code_case_insensitive():
    _, o2, _ = _seed()
    sup2 = db.session.get(Supplier, o2.supplier_id)
    token = sup2.code.split("-")[1].lower()  # "bw"（原码大写，验证 ilike）
    got = _filtered(token)
    assert [o.id for o in got] == [o2.id], "部分编码（大小写不敏感）应能匹配供应商编码"


def test_t3_customer_name_matches_for_other_inbound():
    _, _, o3 = _seed()
    got = _filtered("万通")
    assert [o.id for o in got] == [o3.id], "客户名（往来来源）也应参与模糊匹配"


def test_t4_empty_keyword_filters_nothing():
    _seed()
    assert len(_filtered("")) == 3
    assert len(_filtered("   ")) == 3


def test_t5_no_match_returns_empty():
    _seed()
    assert _filtered("不存在的往来单位xyz") == []


def test_t6_route_export_template_contract():
    # 路由：supplier_id 为空时回退文本模糊匹配
    m = re.search(
        r"supplier_id = request\.args\.get\('supplier_id', type=int\) or 0\n(?P<seg>.*?)\n        if business_type_filter:",
        IN_ORDER_PY, re.S)
    assert m, "未定位到 in_order_list 供应商筛选段"
    seg = m.group("seg")
    assert "if supplier_id:" in seg and "else:" in seg, "必须保留 id 精确分支"
    assert "_apply_order_partner_text_filter" in seg and "supplier_name" in seg, (
        "supplier_id 为空时必须回退 supplier_name 模糊匹配"
    )
    assert "'supplier_name': supplier_name_filter" in IN_ORDER_PY, "filters 必须带 supplier_name 供模板回填"

    # 导出链路同样接入，保证导出与页面筛选一致
    m2 = re.search(
        r"supplier_id = request\.args\.get\('supplier_id', type=int\) or 0\n(?P<seg>.*?)\n        if business_type_filter:",
        EXPORT_PY, re.S)
    assert m2, "未定位到 export_in_order 供应商筛选段"
    seg2 = m2.group("seg")
    assert "_apply_order_partner_text_filter" in seg2 and "supplier_name" in seg2, (
        "导出也必须支持 supplier_name 模糊匹配，否则筛选后导出结果与页面不一致"
    )

    # 模板：输入框提交文本 + 各链接回填
    assert 'name="supplier_name"' in TPL, "供应商输入框必须提交 supplier_name"
    assert "supplier_name=filters.supplier_name" in TPL, "分页链接必须回填 supplier_name"
    assert "supplier_name={{ filters.supplier_name|urlencode }}" in TPL, "导出链接必须回填 supplier_name"
    assert "or filters.supplier_name %}" in TPL, "清除按钮条件必须包含 supplier_name"
