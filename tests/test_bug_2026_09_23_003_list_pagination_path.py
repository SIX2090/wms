"""BUG-2026-09-23-003：明细表翻页跳进「其他 XX 明细表」（入库 + 出库两侧，R6 收口）。

现场（用户走查）：采购入库明细表（/in_order?type=purchase_in）分页有
「上一页 1 2 3 4 … 61 62 下一页」，点第 2 页后**整页变成其他入库明细表**。

根因（两层叠加）：
  1. `in_order_list` 视图同时挂在两个 URL 规则上——
     `@app.route('/in_order')` 与 `@app.route('/other_in_order')`。
     Flask 的 `url_for('in_order_list')` 在「同一 endpoint 对应多条规则」时
     **只稳定解析到后注册的那条**，即 `/other_in_order`。
  2. `in_order.html` 的四处分页链接全部走 `url_for('in_order_list', ...)`，
     于是采购入库明细表的翻页链接被生成为
     `/other_in_order?page=2&type=purchase_in`。
     而路由内 `raw_type = 'other_in' if request.path == '/other_in_order' else ...`
     一旦命中 `/other_in_order` 就**强制覆盖 type=other_in**，
     连请求里带的 `type=purchase_in` 也被丢弃 → 页面切到其他入库明细表。

R6 收口（同根因兄弟点，一并修复）：
  * `out_order_list` 完全同构（`/out_order` + `/other_out_order`，`raw_bt` 同理），
    `out_order.html` 三处分页链接同病 —— 领料/销售/采购退货出库明细表翻页
    会跳到其他出库明细表；
  * 非分页消费点 `sales_order_detail.html` 的「最近出库草稿」也走
    `url_for('out_order_list', search=...)`，会把销售出库草稿链到 /other_out_order，
    该页强制 business_type=其他出库 → 用户点进去按单号也搜不到那张单。

修复：后端把本次请求的真实 path 显式传给模板（`list_base_path`），
分页与「清除」链接一律用 `list_base_path` 拼查询串，不再经过 `url_for`。

断言（以真实 HTTP 请求端到端验证，非源码字符串匹配）：
  T1 采购入库明细表第 1 页 HTML 中，**不存在** /other_in_order 翻页链接
  T2 采购入库明细表翻页链接必须保留 type=purchase_in 且走 /in_order
  T3 其他入库明细表（/other_in_order）翻页仍留在 /other_in_order（不被误伤）
  T4 真实跟随翻页链接：/in_order?type=purchase_in&page=2 返回的仍是采购入库明细表
  T5 直接用 url_for 的旧写法确实会解析到 /other_in_order（锁死根因认知）
  T6 模板中不得再残留 url_for('in_order_list') 调用（结构性防回归）
  T7 筛选表单隐藏字段 type 不得渲染成空值（否则明细表退化成「采购入库单」）
  T8 分页链接不得携带字面量 None
  T1o~T7o 出库侧同构断言（其他出库明细表、sales_order_detail 草稿链接）
"""
import html as html_lib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
TPL = APP_DIR / "templates" / "in_order.html"
TPL_OUT = APP_DIR / "templates" / "out_order.html"
TPL_SALES_DETAIL = APP_DIR / "templates" / "sales_order_detail.html"


# --------------------------------------------------------------------------
# 端到端夹具：真实建单 + 真实走 HTTP，确保翻页 HTML 是用真实数据渲染出来的
# --------------------------------------------------------------------------
@pytest.fixture
def wms_env():
    """函数级夹具：每条用例从干净 schema 开始，用后重建还库。

    为何不用模块级/autouse 共享 ctx（R7 / A12 同族教训）：
    本仓库 CI 以 ``-n 4 --dist loadfile`` 跑全量套件，同一 worker 进程会连续
    跑多个测试文件。若本模块在**模块级** push 一个常驻 app_context 并向共享库
    塞入 ``is_default=True`` 的仓库，就会顶掉**后续文件**的默认仓库，
    使那些文件的单据查询被 AGENTS.md §二 的「仓库必填」兜底过滤成空集，
    表现为「单独跑全绿、全量跑变红」的顺序依赖假失败。
    故改为函数级：建库 → 播种 → 用 → 拆干净。
    """
    import sys

    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    import app as wms

    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    ctx = wms.app.app_context()
    ctx.push()
    try:
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        _seed(wms)
        yield wms
    finally:
        # 与 setup 对称：重建空 schema，交还干净数据库，杜绝跨文件污染
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        ctx.pop()


def _seed(wms):
    """建 13 张采购入库单 + 12 张其他入库单 + 13 张领料单 + 12 张其他出库单。

    per_page 白名单是 [10,20,50,100,200]，故要出现分页控件必须 >=11 行
    （列表按「单据左连接明细」展开，每单 1 行明细 → 13 行 → per_page=10 时 2 页）。
    """
    from datetime import date

    from app import (InOrder, InOrderItem, Material, OutOrder, OutOrderItem,
                     User, Warehouse)

    wms.db.session.add_all([
        User(username="bug923003", password_hash="unused-test-hash",
             role="admin", must_change_password=False),
        User(username="bug923003o", password_hash="unused-test-hash",
             role="admin", must_change_password=False),
        # AGENTS.md §二：仓库是必填项，无默认仓库时列表会被兜底过滤成空集。
        Warehouse(code="BUG923003-W", name="主仓库", status="active", is_default=True),
        Material(code="BUG923003-M", name="翻页测试物料", stock=0),
        Material(code="BUG923003-OM", name="出库翻页物料", stock=0),
    ])
    wms.db.session.flush()
    mat = Material.query.filter_by(code="BUG923003-M").first()
    omat = Material.query.filter_by(code="BUG923003-OM").first()

    for i in range(1, 14):
        o = InOrder(order_no=f"BUG923003-P{i:02d}", date=date(2026, 9, 23),
                    business_type="采购入库", status="pending", warehouse="主仓库")
        wms.db.session.add(o)
        wms.db.session.flush()
        wms.db.session.add(InOrderItem(in_order_id=o.id, material_id=mat.id,
                                       quantity=1, price=1, amount=1))
    for i in range(1, 13):
        o = InOrder(order_no=f"BUG923003-O{i:02d}", date=date(2026, 9, 23),
                    business_type="其他入库", status="pending", warehouse="主仓库")
        wms.db.session.add(o)
        wms.db.session.flush()
        wms.db.session.add(InOrderItem(in_order_id=o.id, material_id=mat.id,
                                       quantity=1, price=1, amount=1))

    for biz, n, prefix in (("领料单", 13, "Q"), ("其他出库", 12, "Z")):
        for i in range(1, n + 1):
            o = OutOrder(order_no=f"BUG923003-{prefix}{i:02d}", date=date(2026, 9, 23),
                         business_type=biz, status="pending", warehouse="主仓库")
            wms.db.session.add(o)
            wms.db.session.flush()
            wms.db.session.add(OutOrderItem(out_order_id=o.id, material_id=omat.id,
                                            quantity=1, price=1, amount=1))
    wms.db.session.commit()


@pytest.fixture
def client(wms_env):
    user = wms_env.User.query.filter_by(username="bug923003").first()
    with wms_env.app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        yield c


@pytest.fixture
def client_out(wms_env):
    user = wms_env.User.query.filter_by(username="bug923003o").first()
    with wms_env.app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        yield c


def _page_links(html: str) -> list:
    """取出分页控件里的所有 href（上一页 / 页码 / 下一页），排除禁用 span。"""
    nav = re.search(r'<nav aria-label="分页导航">(.*?)</nav>', html, re.S)
    assert nav, "页面未渲染分页控件（数据不足或模板改动）"
    hrefs = re.findall(r'class="page-link"\s+href="([^"]+)"', nav.group(1))
    # Jinja 在属性里把 & 转义为 &amp; 是正常 HTML 行为，浏览器会自动还原；
    # 测试必须按浏览器语义还原后再请求，否则服务端会收到名为 "amp;type" 的参数。
    return [html_lib.unescape(h) for h in hrefs]


def _title(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return m.group(1).strip() if m else ""


# --------------------------------------------------------------------------
# T1 / T2：采购入库明细表翻页不得离开 /in_order
# --------------------------------------------------------------------------
def test_t1_purchase_in_pagination_has_no_other_in_order_link(client):
    resp = client.get("/in_order?type=purchase_in&per_page=10")
    assert resp.status_code == 200
    links = _page_links(resp.get_data(as_text=True))
    assert links, "采购入库明细表未渲染出翻页链接"
    bad = [h for h in links if h.startswith("/other_in_order")]
    assert not bad, (
        f"采购入库明细表的分页链接指向了其他入库明细表（BUG-2026-09-23-003 复发）：{bad}"
    )


def test_t2_purchase_in_pagination_keeps_in_order_and_type(client):
    resp = client.get("/in_order?type=purchase_in&per_page=10")
    html = resp.get_data(as_text=True)
    links = _page_links(html)
    assert links, "采购入库明细表未渲染出翻页链接"
    for href in links:
        assert href.startswith("/in_order?"), (
            f"翻页链接未落在 /in_order 上：{href}"
        )
        assert "type=purchase_in" in href, (
            f"翻页链接丢失 type=purchase_in，翻页后会串到别的表：{href}"
        )


# --------------------------------------------------------------------------
# T3：其他入库明细表自身翻页不被误伤（防「修 A 坏 B」，R8）
# --------------------------------------------------------------------------


def test_t3_other_in_pagination_stays_on_other_in_order(client):
    resp = client.get("/other_in_order?per_page=10")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    links = _page_links(html)
    assert links, "其他入库明细表未渲染出翻页链接（种子数据不足）"
    for href in links:
        assert href.startswith("/other_in_order?"), (
            f"其他入库明细表翻页跑到了别的表：{href}"
        )
        assert "type=purchase_in" not in href, (
            f"其他入库明细表翻页串入了采购入库类型：{href}"
        )


# --------------------------------------------------------------------------
# T4：真实跟随翻页链接，落在采购入库明细表
# --------------------------------------------------------------------------


def test_t4_following_page2_link_stays_on_purchase_in(client):
    first = client.get("/in_order?type=purchase_in&per_page=10")
    links = _page_links(first.get_data(as_text=True))
    nxt = [h for h in links if "page=2" in h]
    assert nxt, "未找到第 2 页链接（种子数据不足）"
    second = client.get(nxt[0])
    assert second.status_code == 200
    html = second.get_data(as_text=True)
    # 后端对 /other_in_order 会强制 type=other_in → 页面标题变成「其他入库明细表」
    assert "其他入库明细表" not in _title(html), (
        f"跟随第 2 页链接后进入了其他入库明细表（BUG-2026-09-23-003 复发）：{nxt[0]}"
    )
    assert _title(html) == "采购入库明细表", (
        f"跟随第 2 页链接后未停在采购入库明细表：{_title(html)}（链接 {nxt[0]}）"
    )


# --------------------------------------------------------------------------
# T5：锁死根因认知——url_for 在双规则下确实解析到 /other_in_order
# --------------------------------------------------------------------------


def test_t5_url_for_in_order_list_resolves_to_other_in_order():
    import app as wms
    from flask import url_for

    with wms.app.test_request_context():
        resolved = url_for("in_order_list")
    assert resolved == "/other_in_order", (
        "Flask 对 in_order_list 的 url_for 解析行为已变化"
        f"（现解析为 {resolved}）——本 BUG 的前提假设需重新评估，"
        "但 T1/T2/T4 的端到端断言仍必须保持绿"
    )


# --------------------------------------------------------------------------
# T6：结构性防回归——模板不得再残留 url_for('in_order_list') 调用
# --------------------------------------------------------------------------


def test_t6_template_has_no_url_for_in_order_list_call():
    src = TPL.read_text(encoding="utf-8")
    # 去掉 Jinja 注释块 {# ... #} 后再找，注释里提到该名字是允许的
    body = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    offenders = re.findall(r"url_for\(\s*['\"]in_order_list['\"]", body)
    assert not offenders, (
        f"in_order.html 仍有 {len(offenders)} 处 url_for('in_order_list') 调用；"
        "该方法在双 URL 规则下会解析到 /other_in_order，必须改用 list_base_path"
    )
    assert "list_base_path" in body, (
        "模板未使用后端传入的 list_base_path，分页路径无法与当前表保持一致"
    )


# --------------------------------------------------------------------------
# T7：筛选表单不得把 type 渲染成空值，否则筛选/翻页后明细表退化成「采购入库单」
# --------------------------------------------------------------------------


def test_t7_hidden_type_field_is_not_blank(client):
    html = client.get("/in_order?type=purchase_in&per_page=10").get_data(as_text=True)
    m = re.search(r'<input type="hidden" name="type" value="([^"]*)"', html)
    assert m, "页面未渲染隐藏的 type 字段"
    assert m.group(1) == "purchase_in", (
        f"隐藏字段 type 渲染为 {m.group(1)!r}（应为 purchase_in）——"
        "在购入库明细表提交筛选后，type 丢失会让标题退化为「采购入库单」"
    )


# --------------------------------------------------------------------------
# T8：分页链接不得携带字面量 None（embedded=None 这类空值应省略）
# --------------------------------------------------------------------------


def test_t8_pagination_links_have_no_literal_none(client):
    links = _page_links(client.get("/in_order?type=purchase_in&per_page=10").get_data(as_text=True))
    bad = [h for h in links if "=None" in h]
    assert not bad, f"分页链接携带字面量 None（参数被渲染成字符串 'None'）：{bad[0]}"


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t1o_has_no_other_out_order_link(client_out):
    resp = client_out.get("/out_order?per_page=10")
    assert resp.status_code == 200
    links = _page_links(resp.get_data(as_text=True))
    assert links, "领料出库明细表未渲染出翻页链接"
    bad = [h for h in links if h.startswith("/other_out_order")]
    assert not bad, (
        f"领料出库明细表的分页链接指向了其他出库明细表（BUG-2026-09-23-003 同根因复发）：{bad[0]}"
    )


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t2o_stays_on_out_order(client_out):
    links = _page_links(client_out.get("/out_order?per_page=10").get_data(as_text=True))
    for href in links:
        assert href.startswith("/out_order?"), f"翻页链接未落在 /out_order 上：{href}"


# --------------------------------------------------------------------------
# T3：其他出库明细表自身翻页不被误伤
# --------------------------------------------------------------------------


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t3_other_out_side_pagination_stays_on_other_out_order(client_out):
    resp = client_out.get("/other_out_order?per_page=10")
    assert resp.status_code == 200
    links = _page_links(resp.get_data(as_text=True))
    assert links, "其他出库明细表未渲染出翻页链接（种子数据不足）"
    for href in links:
        assert href.startswith("/other_out_order?"), (
            f"其他出库明细表翻页跑到了别的表：{href}"
        )


# --------------------------------------------------------------------------
# T4：真实跟随第 2 页链接，仍停在领料明细表
# --------------------------------------------------------------------------


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t4o_following_page2_stays_on_out_side(client_out):
    links = _page_links(client_out.get("/out_order?per_page=10").get_data(as_text=True))
    nxt = [h for h in links if "page=2" in h]
    assert nxt, "未找到第 2 页链接（种子数据不足）"
    html = client_out.get(nxt[0]).get_data(as_text=True)
    assert _title(html) == "领料明细表", (
        f"跟随第 2 页链接后未停在领料明细表：{_title(html)}（链接 {nxt[0]}）"
    )


# --------------------------------------------------------------------------
# T5：锁死根因
# --------------------------------------------------------------------------


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t5o_url_for_out_order_list_resolves_to_other_out_order():
    import app as wms
    from flask import url_for

    with wms.app.test_request_context():
        resolved = url_for("out_order_list")
    assert resolved == "/other_out_order", (
        f"Flask 对 out_order_list 的 url_for 解析行为已变化（现为 {resolved}）"
    )


# --------------------------------------------------------------------------
# T6 / T7：结构性防回归
# --------------------------------------------------------------------------


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t6o_out_order_template_has_no_url_for_out_order_list_call():
    src = TPL_OUT.read_text(encoding="utf-8")
    body = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    offenders = re.findall(r"url_for\(\s*['\"]out_order_list['\"]", body)
    assert not offenders, (
        f"out_order.html 仍有 {len(offenders)} 处 url_for('out_order_list') 调用；"
        "该方法在双 URL 规则下会解析到 /other_out_order，必须改用 list_base_path"
    )
    assert "list_base_path" in body, (
        "模板未使用后端传入的 list_base_path，分页路径无法与当前表保持一致"
    )


# ----------------------------------------------------------------------
# 出库侧同根因兄弟点（R6 收口）
# ----------------------------------------------------------------------
def test_t7o_sales_order_detail_draft_link_not_via_url_for_out_order_list():
    src = TPL_SALES_DETAIL.read_text(encoding="utf-8")
    body = re.sub(r"\{#.*?#\}", "", src, flags=re.S)
    assert "url_for('out_order_list'" not in body, (
        "sales_order_detail.html 的「最近出库草稿」仍走 url_for('out_order_list')，"
        "会链到 /other_out_order（其他出库明细表）→ 按单号搜不到该销售出库单"
    )
