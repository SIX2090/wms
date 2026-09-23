"""BUG-2026-09-23-004：采购入库明细表浏览器全量走查发现的问题（5 项，R6 收口）。

现场（用户走查，要求「用浏览器登录 wms 系统，在采购入库明细页面所有的地方
操作一遍找出所有的问题」）：走查后确认以下 5 个问题并修复。

  A-1（P1）单页时「共 N 条记录」整块消失
       `in_order.html` 用 `{% if pagination.pages > 1 %}` 把
       「每页显示选择器 + 共 N 条记录」与分页导航**一起**包住。
       结果只有 1 页时整块不渲染：用户筛完条件最需要知道总数，偏偏这时看不到，
       只能数表格行数，也无法判断是否还有下一页。
       同根因兄弟 `out_order.html` 完全同构（R6）。

  A-2（P1）「金额」列排序名不副实
       明细表 `query` 已 `outerjoin(InOrderItem)` 按明细行展开，模板「金额」列
       渲染的是明细行金额 `item.amount`；但排序键写成
       `getattr(InOrder, 'total_amount')`，打到**单据头**的冗余汇总列（页面根本
       不展示）。一个单据多行共享同一个 total_amount，该键无法在行间区分先后，
       ORDER BY 退化成按主键序——用户点「金额 ⇅」后可见列完全无序。
       同根因兄弟 `out_order.py` 完全同构（R6）。

  A-3（P2）「清除」链接泄漏 `embedded=None`
       `{'type': ..., 'embedded': request.args.get('embedded')}|urlencode`
       未过滤 None，Jinja 把 Python None 渲染成字符串 "None"，产出
       `/in_order?type=purchase_in&embedded=None` 垃圾参数并一路传播。
       （同文件分页链接侧已有 `rejectattr('1','none')`，此处漏了。）

  A-4（P2）批量接口同类校验返回码不一致
       空选时 batch_complete / batch_delete 走 `api_error`（400），
       而 batch_print / batch_export 返回裸 `jsonify`（200）。
       前端 batchInOrderAction 恰好只看 body 不看状态码所以暂未暴露，
       但任何统一拦截器 / 网关 / 「非 2xx 即报错」封装都会让后两者静默失败。

  A-5（P2）batch_complete 对「一张都没成功」回 success
       传入一批根本不存在的 id（orders 为空、completed=0）时回
       `status=success, completed=0`，前端弹绿色成功 + reload，
       用户完全察觉不到自己选的东西一张都没生效。

断言（以真实 HTTP 请求端到端验证，非源码字符串匹配）：
  T1  单页结果（结果 <= per_page）必须仍渲染「共 N 条记录」
  T2  多页结果渲染的「共 N 条记录」总数正确
  T3  「每页显示」选择器在单页时也必须可见（否则用户无法调整每页条数）
  T4  单页时「共 N 条记录」的 total 与真实行数一致
  T5  sort=total_amount 必须按**明细行金额**排序（asc 单调不减 / desc 单调不增）
  T6  金额升序与降序结果必须不同（锁死「排序退化为主键序」这一根因）
  T7  金额排序结果不得与 order_no 排序结果相同（根因判据）
  T8  未传 embedded 时，「清除」链接不得出现字面量 None
  T9  传了 embedded=1 时，「清除」链接必须保留 embedded=1（不误伤）
  T10 批量接口空选：四个接口必须同为 400
  T11 batch_complete 传不存在 id 不得回 success
  T12 batch_complete 传入匹配到但全被跳过的单据时，不得静默回 success
  T1o~T3o 出库侧 A-1 同构断言（其他出库明细表）+ A-2 出库金额排序

关于列定位：入库表 20 列、出库表 17 列，两者「金额」列下标并不相同。
本文件的取列辅助函数一律**按表头 data-column-key 定位**，不写死下标——
否则「入库能过、出库静默取空样本」会变成假绿（本轮即踩过该坑）。
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
TPL = APP_DIR / "templates" / "in_order.html"
TPL_OUT = APP_DIR / "templates" / "out_order.html"


# --------------------------------------------------------------------------
# 端到端夹具：真实建单 + 真实走 HTTP，确保 HTML 是用真实数据渲染出来的
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
    """建 26 张采购入库单（每单 2 行明细，金额随单号单调递增）+ 8 张其他入库单
    + 13 张领料单 + 6 张其他出库单。

    设计要点：
      * 采购入库单数 26 > 默认 per_page=20 → 有分页（A-1 的多页对照）；
      * 每单 2 行明细，行金额 = 数量 × 单价，且**随 i 单调递增**，
        保证「按行金额排序」与「按单据主键序」结果必然不同（A-2 判据 T7）；
      * 单据头 total_amount 故意设成与行金额无关的值，这样若排序键仍打
        单据头，T5/T6/T7 会立刻变红（对 A-2 的修复做真锁）；
      * 领料单 13 张 > per_page=10 → 出库侧 A-1 可测。
    """
    from datetime import date

    from app import (InOrder, InOrderItem, Material, OutOrder, OutOrderItem,
                     User, Warehouse)

    wms.db.session.add_all([
        User(username="bug923004", password_hash="unused-test-hash",
             role="admin", must_change_password=False),
        User(username="bug923004o", password_hash="unused-test-hash",
             role="admin", must_change_password=False),
        # AGENTS.md §二：仓库是必填项，无默认仓库时列表会被兜底过滤成空集。
        Warehouse(code="BUG923004-W", name="主仓库", status="active", is_default=True),
        Material(code="BUG923004-M", name="走查物料", stock=0),
        Material(code="BUG923004-OM", name="出库走查物料", stock=0),
    ])
    wms.db.session.flush()
    mat = Material.query.filter_by(code="BUG923004-M").first()
    omat = Material.query.filter_by(code="BUG923004-OM").first()

    # 采购入库：26 单 × 2 行；第 i 单两行金额为 i 与 4i（第 i 单金额区间互不重叠）
    for i in range(1, 27):
        o = InOrder(order_no=f"BUG923004-P{i:03d}", date=date(2026, 9, 23),
                    business_type="采购入库", status="pending", warehouse="主仓库",
                    # 单据头汇总列故意与行金额无关：旧的「按单据头排序」实现
                    # 不可能通过 T5/T6/T7
                    total_amount=9999 - i)
        wms.db.session.add(o)
        wms.db.session.flush()
        wms.db.session.add_all([
            InOrderItem(in_order_id=o.id, material_id=mat.id,
                        quantity=i, price=1, amount=float(i)),
            InOrderItem(in_order_id=o.id, material_id=mat.id,
                        quantity=i, price=4, amount=float(4 * i)),
        ])

    # 其他入库：8 单（1 页对照）
    for i in range(1, 9):
        o = InOrder(order_no=f"BUG923004-O{i:02d}", date=date(2026, 9, 23),
                    business_type="其他入库", status="pending", warehouse="主仓库")
        wms.db.session.add(o)
        wms.db.session.flush()
        wms.db.session.add(InOrderItem(in_order_id=o.id, material_id=mat.id,
                                       quantity=1, price=1, amount=1))

    # 领料单 13 张（per_page=10 时 2 页）+ 其他出库 6 张（1 页）
    for biz, n, prefix in (("领料单", 13, "Q"), ("其他出库", 6, "Z")):
        for i in range(1, n + 1):
            o = OutOrder(order_no=f"BUG923004-{prefix}{i:02d}", date=date(2026, 9, 23),
                         business_type=biz, status="pending", warehouse="主仓库",
                         total_amount=9999 - i)
            wms.db.session.add(o)
            wms.db.session.flush()
            wms.db.session.add_all([
                OutOrderItem(out_order_id=o.id, material_id=omat.id,
                             quantity=i, price=1, amount=float(i)),
                OutOrderItem(out_order_id=o.id, material_id=omat.id,
                             quantity=i, price=4, amount=float(4 * i)),
            ])
    wms.db.session.commit()


@pytest.fixture
def client(wms_env):
    user = wms_env.User.query.filter_by(username="bug923004").first()
    with wms_env.app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        yield c


@pytest.fixture
def client_out(wms_env):
    user = wms_env.User.query.filter_by(username="bug923004o").first()
    with wms_env.app.test_client() as c:
        with c.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
        yield c


# --------------------------------------------------------------------------
# 解析辅助
# --------------------------------------------------------------------------
def _visible_text(html: str) -> str:
    """粗略取出「可见」文本：先剥掉 <script>/<style>/注释，再剥标签。

    不直接用整页字符串搜关键词，是为了避免 script 里的同名 JS 字符串
    （如 '共' / '条记录' 出现在模板 JS 中）造成假阳性。
    """
    s = re.sub(r"<script\b.*?</script>", " ", html, flags=re.S | re.I)
    s = re.sub(r"<style\b.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s)


def _total_in_page(html: str):
    """返回「条，共 N 条记录」里的 N；不存在返回 None。"""
    s = _visible_text(html)
    m = re.search(r"共\s*(\d+)\s*条记录", s)
    return int(m.group(1)) if m else None


def _has_per_page_select(html: str) -> bool:
    """「每页显示」选择器是否渲染（以 200 这个 per_page 白名单值为标志）。"""
    return bool(re.search(r'<option value="200"', html))


def _tbody_row_count(html: str) -> int:
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S)
    if not body:
        return 0
    return len(re.findall(r"<tr\b", body.group(1)))


def _column_index(html: str, key: str):
    """按表头 data-column-key 定位列下标。

    入库表 20 列、出库表 17 列，「金额」列下标不同（13 vs 11）。
    写死下标会让出库侧静默取到空样本——那是一种**假绿**，
    比失败更危险，所以这里必须按语义定位。
    """
    head = re.search(r"<thead[^>]*>(.*?)</thead>", html, re.S)
    assert head, "页面无表头，无法定位列"
    ths = re.findall(r"<th\b[^>]*>", head.group(1))
    for idx, th in enumerate(ths):
        m = re.search(r'data-column-key="([^"]+)"', th)
        if m and m.group(1) == key:
            return idx
    return None


def _col_texts(html: str, key: str):
    """按 data-column-key 取出该列每行的纯文本。"""
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S)
    assert body, "页面无表格数据"
    idx = _column_index(html, key)
    assert idx is not None, f"表头未找到 data-column-key={key!r} 的列"
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) <= idx:
            continue
        out.append(re.sub(r"\s+", " ",
                          re.sub(r"<[^>]+>", "", tds[idx])).strip())
    return out


def _amounts(html: str):
    """按表格行顺序取出「金额」列的数值（去掉 ¥ 与千分位）。

    列位置由表头 ``data-column-key="amount"`` 决定，入/出库表各自适用。
    """
    out = []
    for text in _col_texts(html, "amount"):
        m = re.search(r"¥?\s*([\d,]+(?:\.\d+)?)", text)
        if m:
            out.append(float(m.group(1).replace(",", "")))
    return out


def _order_nos(html: str):
    """按表格行顺序取出单号列（入库单号 / 领料单号，两者 key 均为 order_no）。"""
    return _col_texts(html, "order_no")


def _clear_href(html: str):
    m = re.search(r'<a\s+href="([^"]*)"[^>]*class="btn btn-outline-secondary btn-sm"\s*>清除</a>', html)
    return m.group(1) if m else None


def _is_sorted(seq, ascending=True):
    if len(seq) < 2:
        return True
    pairs = zip(seq, seq[1:])
    return all((a <= b) if ascending else (a >= b) for a, b in pairs)


# ==========================================================================
# A-1：单页时「共 N 条记录」必须仍然渲染
# ==========================================================================
def test_t1_single_page_still_shows_total(client):
    """A-1：筛选后结果只剩 1 页时，仍必须渲染「共 N 条记录」。

    旧实现把总数文案与分页导航用同一个 `pagination.pages > 1` 包住，
    单页时整块消失；本用例在修复前必红。
    """
    # 列表按「单据左连接明细」展开：26 单 × 2 行 = 52 条明细记录。
    # per_page 白名单是 [10,20,50,100,200]，故用 200 才能压到 1 页。
    r = client.get("/in_order?type=purchase_in&per_page=200")
    assert r.status_code == 200
    total = _total_in_page(r.get_data(as_text=True))
    assert total is not None, "单页结果下「共 N 条记录」整块消失（A-1 回归）"
    assert total == 52, f"总数应为 52（26 单 × 2 行），实际 {total}"


def test_t2_multi_page_total_is_correct(client):
    """A-1 对照：多页时总数依然正确（修复不得影响原有多页路径）。"""
    r = client.get("/in_order?type=purchase_in&per_page=10")  # 52 行 → 6 页
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert _total_in_page(html) == 52
    assert re.search(r'<nav aria-label="分页导航">', html), "多页必须仍有分页导航"


def test_t3_per_page_select_visible_on_single_page(client):
    """A-1：单页时「每页显示」选择器也必须可见。

    否则用户被卡死在当前 per_page 上——想调大每页条数却没入口。
    """
    r = client.get("/in_order?type=purchase_in&per_page=200")
    html = r.get_data(as_text=True)
    assert _has_per_page_select(html), "单页时「每页显示」选择器消失（A-1 回归）"


def test_t4_single_page_total_matches_rows(client):
    """A-1：单页时显示的总数必须与该页实际渲染的行数一致（口径自洽）。"""
    r = client.get("/in_order?type=purchase_in&status=pending&per_page=200")
    html = r.get_data(as_text=True)
    total = _total_in_page(html)
    rows = _tbody_row_count(html)
    assert total is not None, "单页结果下无总数文案"
    assert total == rows == 52, f"总数 {total} 与实际行数 {rows} 不一致"


def test_t1o_out_order_single_page_still_shows_total(client_out):
    """A-1（R6 同根因）：其他出库明细表单页时同样必须渲染「共 N 条记录」。"""
    r = client_out.get("/out_order?business_type=其他出库")
    assert r.status_code == 200
    total = _total_in_page(r.get_data(as_text=True))
    assert total is not None, "出库明细表单页时「共 N 条记录」消失（A-1 R6 回归）"
    assert total == 12, f"其他出库应 12 条明细（6 单 × 2 行），实际 {total}"


def test_t3o_out_order_per_page_select_on_single_page(client_out):
    """A-1（R6）：出库侧单页时「每页显示」选择器也必须可见。"""
    r = client_out.get("/out_order?business_type=其他出库")
    assert _has_per_page_select(r.get_data(as_text=True)), \
        "出库明细表单页时「每页显示」选择器消失（A-1 R6 回归）"


# ==========================================================================
# A-2：金额列排序必须按「明细行金额」
# ==========================================================================
def test_t5_amount_sort_is_actually_sorted(client):
    """A-2：sort=total_amount 必须按可见的明细行金额排序。

    旧实现排序键打到单据头冗余列（一单多行共享同值，无法区分先后），
    ORDER BY 退化成主键序，可见的金额列完全无序。修复前本用例必红。
    """
    asc = _amounts(client.get("/in_order?type=purchase_in&per_page=200"
                              "&sort=total_amount&order=asc").get_data(as_text=True))
    desc = _amounts(client.get("/in_order?type=purchase_in&per_page=200"
                               "&sort=total_amount&order=desc").get_data(as_text=True))
    assert len(asc) >= 20, f"样本太少，无法判定排序：{len(asc)}"
    assert _is_sorted(asc, True), f"金额升序结果并非升序（A-2 回归）：{asc[:12]}"
    assert _is_sorted(desc, False), f"金额降序结果并非降序（A-2 回归）：{desc[:12]}"


def test_t6_amount_asc_differs_from_desc(client):
    """A-2：金额升序与降序的结果必须不同。

    若排序键实际未生效（退化为主键序），asc 与 desc 会得到同一序列。
    """
    asc = _amounts(client.get("/in_order?type=purchase_in&per_page=200"
                              "&sort=total_amount&order=asc").get_data(as_text=True))
    desc = _amounts(client.get("/in_order?type=purchase_in&per_page=200"
                               "&sort=total_amount&order=desc").get_data(as_text=True))
    assert asc != desc, "金额 asc 与 desc 结果完全相同，说明排序未生效（A-2 回归）"


def test_t7_amount_sort_differs_from_order_no_sort(client):
    """A-2 根因判据：按金额排序的结果不得等同于按单号排序。

    这直接锁死「排序键打到单据头 → 退化为按单据维度」这一根因：
    旧的实现下两者序列**完全一致**。
    """
    by_amount = _order_nos(client.get("/in_order?type=purchase_in&per_page=200"
                                      "&sort=total_amount&order=asc").get_data(as_text=True))
    by_order_no = _order_nos(client.get("/in_order?type=purchase_in&per_page=200"
                                        "&sort=order_no&order=asc").get_data(as_text=True))
    assert by_amount != by_order_no, (
        "按金额排序与按单号排序结果完全相同，说明排序键未落到行金额（A-2 根因未修）"
    )


def test_t5o_out_order_amount_sort(client_out):
    """A-2（R6 同根因）：出库明细表金额排序同样必须按明细行金额生效。

    出库表 17 列、入库表 20 列，「金额」列下标不同；此处通过表头
    data-column-key 定位，确保取到的是真列而不是静默空样本。
    """
    html_asc = client_out.get("/out_order?business_type=领料单&per_page=200"
                              "&sort=total_amount&order=asc").get_data(as_text=True)
    html_desc = client_out.get("/out_order?business_type=领料单&per_page=200"
                               "&sort=total_amount&order=desc").get_data(as_text=True)
    asc = _amounts(html_asc)
    desc = _amounts(html_desc)
    assert len(asc) >= 20, f"样本太少（列定位可能失效）：{len(asc)}"
    assert _is_sorted(asc, True), f"出库金额升序未生效（A-2 R6 回归）：{asc[:12]}"
    assert _is_sorted(desc, False), f"出库金额降序未生效（A-2 R6 回归）：{desc[:12]}"
    assert asc != desc, "出库金额 asc 与 desc 相同，排序未生效（A-2 R6 回归）"


def test_t7o_out_order_amount_sort_differs_from_order_no(client_out):
    """A-2（R6 根因判据）：出库侧按金额排序不得等同于按单号排序。"""
    by_amount = _order_nos(client_out.get("/out_order?business_type=领料单&per_page=200"
                                          "&sort=total_amount&order=asc").get_data(as_text=True))
    by_order_no = _order_nos(client_out.get("/out_order?business_type=领料单&per_page=200"
                                            "&sort=order_no&order=asc").get_data(as_text=True))
    assert by_amount != by_order_no, (
        "出库侧按金额排序与按单号排序结果完全相同，说明排序键未落到行金额（A-2 R6 未修）"
    )


# ==========================================================================
# A-3：「清除」链接不得泄漏 embedded=None
# ==========================================================================
def test_t8_clear_link_has_no_literal_none(client):
    """A-3：未传 embedded 时，清除链接不得出现字面量 None。"""
    # 先带一个筛选条件，让「清除」按钮渲染出来
    r = client.get("/in_order?type=purchase_in&status=pending")
    href = _clear_href(r.get_data(as_text=True))
    assert href, "未渲染「清除」链接（筛选状态下应可见）"
    assert "None" not in href, f"清除链接泄漏字面量 None（A-3 回归）：{href}"
    assert href.startswith("/in_order?"), f"清除链接未落在 /in_order：{href}"


def test_t8b_pagination_links_have_no_literal_none(client):
    """A-3 延伸：分页链接同样不得出现字面量 None（与清除链接口径一致）。"""
    html = client.get("/in_order?type=purchase_in&per_page=10").get_data(as_text=True)
    nav = re.search(r'<nav aria-label="分页导航">(.*?)</nav>', html, re.S)
    assert nav, "未渲染分页控件"
    for h in re.findall(r'href="([^"]*)"', nav.group(1)):
        assert "None" not in h, f"分页链接泄漏字面量 None（A-3 回归）：{h}"


def test_t9_clear_link_keeps_embedded_when_present(client):
    """A-3 不误伤：显式传了 embedded=1 时，清除链接必须保留它。"""
    r = client.get("/in_order?type=purchase_in&status=pending&embedded=1")
    href = _clear_href(r.get_data(as_text=True))
    assert href, "未渲染「清除」链接"
    assert "embedded=1" in href, f"清除链接丢了 embedded=1：{href}"


# ==========================================================================
# A-4 / A-5：批量接口契约
# ==========================================================================
def _csrf(client):
    html = client.get("/in_order?type=purchase_in").get_data(as_text=True)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    return m.group(1) if m else ""


@pytest.mark.parametrize("path", [
    "/in_order/batch_complete",
    "/in_order/batch_delete",
    "/in_order/batch_print",
    "/in_order/batch_export",
])
def test_t10_batch_empty_selection_returns_400(client, path):
    """A-4：四个批量接口对「空选」必须返回同一契约（400）。

    旧实现 batch_print / batch_export 回 200，与另两个的 400 不一致。
    """
    h = {"Content-Type": "application/json", "X-CSRFToken": _csrf(client)}
    r = client.post(path, json={"ids": []}, headers=h)
    assert r.status_code == 400, (
        f"{path} 空选返回 {r.status_code}，应为 400（A-4 回归：批量接口契约不一致）"
    )
    body = r.get_json()
    assert body and body.get("status") == "error"


@pytest.mark.parametrize("path", [
    "/in_order/batch_complete",
    "/in_order/batch_print",
    "/in_order/batch_export",
])
def test_t11_batch_unknown_ids_not_success(client, path):
    """A-5：传入不存在的 id 不得回 success。

    旧实现 batch_complete 回 `status=success, completed=0`，前端据此弹绿色成功
    并 reload，用户察觉不到一张都没生效。
    """
    h = {"Content-Type": "application/json", "X-CSRFToken": _csrf(client)}
    r = client.post(path, json={"ids": ["999999"]}, headers=h)
    body = r.get_json()
    assert body is not None, f"{path} 未返回 JSON"
    assert body.get("status") == "error", (
        f"{path} 对不存在的 id 回了 status={body.get('status')}（A-5 回归：假成功）"
    )
    assert r.status_code == 400, (
        f"{path} 对不存在的 id 返回 {r.status_code}，应为 400"
    )


def test_t12_batch_complete_all_skipped_not_silent_success(client):
    """A-5：匹配到单据但全部被跳过（非 pending）时，同样不得静默回 success。

    构造：把这些单先置为 completed，再走 batch_complete ——
    orders 非空但 completed=0，旧实现会回 success + 「共审核 0 张」。
    """
    wms = client.application
    assert wms  # 让静态检查知道 client 绑定了 app
    # 通过真实接口先把一张 pending 单完成，使其不再 pending
    h = {"Content-Type": "application/json", "X-CSRFToken": _csrf(client)}
    html = client.get("/in_order?type=purchase_in&status=pending").get_data(as_text=True)
    ids = re.findall(r'class="check-item" value="(\d+)"', html)
    assert ids, "未取到可操作的单据 id"
    target = ids[0]
    done = client.post("/in_order/batch_complete", json={"ids": [target]}, headers=h)
    assert done.get_json().get("status") == "success", "前置：首次完成应成功"
    # 再对同一张（此时已 completed）重复调用 → 匹配到但被跳过
    again = client.post("/in_order/batch_complete", json={"ids": [target]}, headers=h)
    body = again.get_json()
    assert body.get("status") == "error", (
        f"对已被跳过的单据回了 status={body.get('status')}（A-5 回归：静默成功）"
    )
    assert again.status_code == 400
    # 契约必须同时携带 completed：既有回归锁
    # tests/test_bug_2026_08_16_005_batch_complete_in_guards.py 的 T1/T2/T4
    # 正是用 `completed == 0` 判断「被业务校验跳过、库存未入账」。
    # 若这里把 completed 丢掉（或改用 api_error 丢了字段），那些既有消费点会 KeyError。
    assert body.get("completed") == 0, (
        f"error 分支丢失 completed 字段（A-5 契约回归）：{body}"
    )


def test_t12b_error_branch_keeps_completed_and_reason(client):
    """A-5 契约锁：`completed == 0` 的错误分支必须同时保留 `completed` 与逐单原因。

    背景（R6 口径一致性）：仓库里对同一接口存在两类消费点——
      * 前端 `batchInOrderAction` 只看 `data.status`：必须拿到 error 才不会
        弹绿色成功 + reload（本 BUG 的诉求）；
      * `tests/test_bug_2026_08_16_005_batch_complete_in_guards.py` 的 T1/T2/T4
        只看 `data["completed"] == 0` 与 `data["msg"]` 里的具体原因子串
        （如「入库日期晚于今天」「未入库数量」），用来证明「被跳过、库存未入账」。
    初版修复直接改用 `api_error(msg)`，**丢掉了 completed 字段**，导致那两个
    既有回归锁 KeyError 变红。正确做法是「status 改 error，同时保留 completed
    与 msg 原因」，让两类消费点同时满足，而不是去放宽任何一边的断言。
    """
    h = {"Content-Type": "application/json", "X-CSRFToken": _csrf(client)}
    html = client.get("/in_order?type=purchase_in&status=pending").get_data(as_text=True)
    ids = re.findall(r'class="check-item" value="(\d+)"', html)
    assert ids, "未取到可操作的单据 id"
    target = ids[0]
    assert client.post("/in_order/batch_complete", json={"ids": [target]},
                       headers=h).get_json().get("status") == "success"
    again = client.post("/in_order/batch_complete", json={"ids": [target]}, headers=h)
    body = again.get_json()
    assert body["status"] == "error"
    assert again.status_code == 400
    # 关键：字段齐全，两类消费点都能工作
    assert body["completed"] == 0, f"error 分支必须保留 completed：{body}"
    assert "跳过" in body["msg"], f"error 分支必须保留逐单跳过原因：{body}"
    assert body.get("skipped"), f"error 分支必须保留 skipped 明细：{body}"

    # 未匹配到单据时也必须带 completed，前端与脚本读同一字段不会 KeyError
    miss = client.post("/in_order/batch_complete", json={"ids": ["999999"]}, headers=h)
    mbody = miss.get_json()
    assert miss.status_code == 400
    assert mbody["status"] == "error"
    assert mbody["completed"] == 0, f"未找到单据分支也必须保留 completed：{mbody}"


def test_t13_batch_complete_happy_path_still_works(client):
    """A-4/A-5 不误伤：正常的批量完成必须仍然返回 success。"""
    h = {"Content-Type": "application/json", "X-CSRFToken": _csrf(client)}
    html = client.get("/in_order?type=purchase_in&status=pending").get_data(as_text=True)
    ids = re.findall(r'class="item-check" value="(\d+)"', html) or \
        re.findall(r'class="check-item" value="(\d+)"', html)
    assert ids, "未取到可操作单据"
    # 同一张单据会因「明细行展开」出现多行、携带重复 id；去重后再取 2 张不同单据，
    # 否则两个 id 可能指向同一张单，第二次会被当成「非 pending」跳过。
    uniq = list(dict.fromkeys(ids))
    assert len(uniq) >= 2, f"去重后不足 2 张单据：{uniq[:5]}"
    r = client.post("/in_order/batch_complete", json={"ids": uniq[:2]}, headers=h)
    body = r.get_json()
    assert body.get("status") == "success", f"正常批量完成失败：{body}"
    assert body.get("completed") == 2, f"应完成 2 张不同单据，实际 {body}"


# ==========================================================================
# 结构性防回归：模板不得回退到「总数被 pages>1 包住」的写法
# ==========================================================================
def test_t14_template_total_not_gated_by_pages():
    """A-1 结构性锁：`共 N 条记录` 所在行不得落在 `pages > 1` 条件之内。

    注意：不能简单用 find() 比较两处字符串的位置——该模板的 JS 段里也可能出现
    `pagination.pages` 字样。这里只比较**模板表达式**层级的位置：取总数文案所在
    的 Jinja 块，并断言在它之前「已开启的 pages>1 条件」数量为 0。
    """
    for path, label in ((TPL, "入库"), (TPL_OUT, "出库")):
        src = path.read_text(encoding="utf-8")
        total = src.find("共 {{ pagination.total }} 条记录")
        assert total != -1, f"{label}模板未找到总数文案"

        # 统计总数文案之前出现过的 {% if pagination.pages > 1 %} 与对应 {% endif %}
        # 用「最后一个未被闭合的 if」判断总数是否被包住。
        depth = 0
        pos = 0
        while pos < total:
            nif = src.find("{% if pagination.pages > 1 %}", pos)
            nend = src.find("{% endif %}", pos)
            if nif != -1 and (nend == -1 or nif < nend) and nif < total:
                depth += 1
                pos = nif + 1
            elif nend != -1 and nend < total:
                depth = max(0, depth - 1)
                pos = nend + 1
            else:
                break
        assert depth == 0, (
            f"{label}模板的「共 N 条记录」仍被 `{{% if pagination.pages > 1 %}}` 包住，"
            "单页时会被吞掉（A-1 结构性回归）"
        )
