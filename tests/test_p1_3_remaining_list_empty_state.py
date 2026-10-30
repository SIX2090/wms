# -*- coding: utf-8 -*-
"""P1-3 空态回归锁（第 2 批）：7 处「无数据只看得到表头 / 整块消失」的列表。

背景（WMS完善现有功能开发计划.md §3 P1-3）：空数据列表页要能分清「加载失败」与「真没数据」。

覆盖（colspan 一律**实测** thead 的 <th> 数，不写死数字——列数变了测试会立刻报警）：
  打印模板 5 处：print_in / print_out / print_in_with_excel / print_out_with_excel /
                 print_in_with_html（明细行空时显示「无明细行」）
  业务页 2 处  ：sales_report（物料钻取）、document_table_form（批次扫码记录）

设计要点：
  * T3 用**独立 Jinja Environment** 渲染，不受 Flask 模板缓存影响；
    裸 Environment 没有 Flask 的全局量，需自行 stub url_for / csrf_token / get_flashed_messages。
  * `_with_excel` 两个模板原本在明细为空时会补 8 行空白占位，空态行会紧跟 8 行空格，
    故同时断言「无明细时不补空白行」（T4）。
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
TPL_DIR = os.path.join(APP_DIR, "templates")

jinja2 = pytest.importorskip("jinja2")

# (模板文件, 遍历的集合变量名, 空态文案关键字, 该表在模板中的序号/thead 顺序)
TARGETS = [
    ("print_in.html", "order.items", "无明细行", 0),
    ("print_out.html", "order.items", "无明细行", 0),
    ("print_in_with_excel.html", "order.items", "无明细行", 0),
    ("print_out_with_excel.html", "order.items", "无明细行", 0),
    ("print_in_with_html.html", "order.items", "无明细行", 0),
    ("sales_report.html", "drill_items", "没有此物料的销售明细", 0),
    ("document_table_form.html", "batch_meta.scans", "暂无扫码盘点记录", 0),
]


def _src(name):
    with open(os.path.join(TPL_DIR, name), encoding="utf-8") as f:
        return f.read()


def _for_block(src, collection):
    """取出 `{% for ... in <collection> %}` … `{% endfor %}` 块（做 for/endfor 配对）。"""
    m = re.search(r"\{%-?\s*for\s+[^%]*\bin\s+" + re.escape(collection) + r"\s*-?%\}", src)
    assert m, f"模板里找不到遍历 {collection} 的 for 循环"
    depth, i = 0, m.start()
    while True:
        t = re.compile(r"\{%-?\s*(for|endfor)\b").search(src, i)
        assert t, "for 没有配对的 endfor"
        if t.group(1) == "for":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return m.start(), t.end()
        i = t.end()


def _thead_th_count(src, for_pos):
    """for 之前最近一个 <thead>…</thead> 里的 <th> 数。"""
    head = src.rfind("<thead", 0, for_pos)
    assert head != -1, "找不到 <thead>，无法确定 colspan"
    end = src.find("</thead>", head)
    seg = src[head:end if end != -1 else for_pos]
    return len(re.findall(r"<th\b", seg, re.I))


def _table_fragment(src, for_pos):
    """截出 for 所属表格的片段：<table …> … </tbody></table>。

    刻意**只渲染这一段**而不是整页：整页 extends base.html，需要 config / template /
    order.total_amount 等一堆 Flask 上下文，补桩会越补越脆；而空态只与这张表有关。
    """
    head = src.rfind("<thead", 0, for_pos)
    assert head != -1, "找不到 <thead>"
    tstart = src.rfind("<table", 0, head)
    assert tstart != -1, "找不到 <table>"
    tend = src.find("</tbody>", for_pos)
    assert tend != -1, "找不到 </tbody>"
    return src[tstart:tend] + "</tbody></table>"


@pytest.fixture(scope="module")
def env():
    e = jinja2.Environment(loader=jinja2.FileSystemLoader(TPL_DIR))
    # 裸 Environment 没有 Flask 注入的全局量，缺失会让渲染抛 UndefinedError
    e.globals.setdefault("url_for", lambda *a, **k: "#")
    e.globals.setdefault("csrf_token", lambda: "test-csrf")
    e.globals.setdefault("get_flashed_messages", lambda *a, **k: [])
    return e


# ---------- T1：for 块内必须有 {% else %} ----------
@pytest.mark.parametrize("name,collection,hint,_", TARGETS)
def test_t1_for_has_else_branch(name, collection, hint, _):
    src = _src(name)
    s, e = _for_block(src, collection)
    assert "{% else %}" in src[s:e], f"{name} 遍历 {collection} 的 for 块缺 {{% else %}} 空态分支"


# ---------- T2：空态文案存在 ----------
@pytest.mark.parametrize("name,collection,hint,_", TARGETS)
def test_t2_empty_text_present(name, collection, hint, _):
    src = _src(name)
    s, e = _for_block(src, collection)
    assert hint in src[s:e], f"{name} 空态文案「{hint}」不在 {collection} 的 for 块内"


# ---------- T3：colspan 实测等于 thead 的 <th> 数 ----------
@pytest.mark.parametrize("name,collection,hint,_", TARGETS)
def test_t3_colspan_matches_th_count(name, collection, hint, _):
    src = _src(name)
    s, e = _for_block(src, collection)
    block = src[s:e]
    m = re.search(r'colspan="(\d+)"', block)
    assert m, f"{name} 空态行缺少 colspan"
    th = _thead_th_count(src, s)
    assert int(m.group(1)) == th, (
        f"{name} 空态 colspan={m.group(1)} 但 thead 实测 {th} 列"
    )


# ---------- T4：_with_excel 无明细时不得再补 8 行空白 ----------
@pytest.mark.parametrize("name", ["print_in_with_excel.html", "print_out_with_excel.html"])
def test_t4_excel_padding_skipped_when_empty(name):
    src = _src(name)
    s, e = _for_block(src, "order.items")
    tail = src[e:e + 400]
    pad = re.search(r"\{%-?\s*for\s+_\s+in\s+range\(\[8", tail)
    assert pad, f"{name} 找不到补空白行的填充循环"
    assert "{% if order.items %}" in tail, (
        f"{name} 填充循环没有被 {{% if order.items %}} 包住，"
        "明细为空时会在空态行后再补 8 行空格"
    )


# ---------- T5：渲染验证——空集合出空态，非空集合不出 ----------
class _Order:
    """最小订单桩：items 为空 / 非空两种。"""

    def __init__(self, items):
        self.items = items
        self.contract_no = ""


class _Item:
    def __init__(self, code):
        self.material = _Material(code)
        self.quantity = 1
        self.price = 1.0
        self.amount = 1.0
        self.remark = ""
        self.contract_no = ""


class _Material:
    def __init__(self, code):
        self.code = code
        self.name = "测试物料"
        self.brand = ""
        self.spec = "-"
        self.unit = None


@pytest.mark.parametrize("name,collection,hint,_", TARGETS)
def test_t5_render_empty_and_non_empty(env, name, collection, hint, _):
    if name == "document_table_form.html":
        ctx_empty = {"batch_meta": {"scans": [], "scan_count": 0}}
        ctx_full = {"batch_meta": {"scans": [{"check_no": "C1", "date": "", "operator": "",
                                              "created_at": "", "item_count": 1}],
                                   "scan_count": 1}}
    elif name == "sales_report.html":
        ctx_empty = {"drill_material_code": "M1", "drill_material_name": "物料",
                     "drill_items": []}
        ctx_full = {"drill_material_code": "M1", "drill_material_name": "物料",
                    "drill_items": [{"order_id": 1, "order_no": "SO1", "date": "",
                                     "customer": "c", "salesperson": "s", "quantity": 1,
                                     "shipped_quantity": 0, "price": 1.0, "tax_rate": 0.13,
                                     "untaxed_amount": 1.0, "tax_amount": 0.13,
                                     "tax_included_amount": 1.13}]}
    else:
        ctx_empty = {"order": _Order([])}
        ctx_full = {"order": _Order([_Item("M001")])}

    src = _src(name)
    s, _e = _for_block(src, collection)
    frag = _table_fragment(src, s)
    tpl = env.from_string(frag)
    out_empty = tpl.render(**ctx_empty)
    assert hint in out_empty, f"{name}：集合为空时渲染结果里没有空态文案「{hint}」"

    out_full = tpl.render(**ctx_full)
    assert hint not in out_full, f"{name}：有数据时不应显示空态文案"
