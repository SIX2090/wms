# -*- coding: utf-8 -*-
"""P1-3 空态回归锁（第 3 批 / JS 渲染列表）。

这两个页面的列表是 **JS 拼 HTML** 出来的，加不了 Jinja `{% else %}`，只能在 JS 分支里补空态。
pytest 里没有 JS 引擎，所以锁的是**结构与口径**而不是运行时渲染：

  batch_import.html  —— renderOpeningStockPreview() 里 rows 为空时，tbody 必须给出空态行，
                        colspan 必须等于**同一段 JS 里 thead 实测的 <th> 数**（列数变了立刻报警）。
  document_ocr.html  —— renderResult() 里 res.items 存在但为空时，必须给出"未识别到物料明细行"。

刻意不断言实现细节（比如具体用 if 还是三元），只锁「空集合必须有可见空态」这个契约。
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TPL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "templates"
)


def _src(name):
    with open(os.path.join(TPL_DIR, name), encoding="utf-8") as f:
        return f.read()


# ===================== batch_import.html =====================

_BI_EMPTY_GUARD = "if (!rows.length)"
_BI_TH_OPEN = "<thead class=\"table-light\">"


def _bi_guard_pos(src):
    pos = src.find(_BI_EMPTY_GUARD)
    assert pos != -1, "batch_import.html 找不到 rows 为空的判断分支"
    return pos


def _bi_th_count(src):
    """实测 renderOpeningStockPreview 里 JS 拼出的 thead 有多少个 <th>。"""
    start = src.find(_BI_TH_OPEN)
    assert start != -1, "batch_import.html 找不到 JS 拼的 <thead>"
    end = src.find("</thead>", start)
    assert end != -1, "batch_import.html 的 <thead> 没有闭合"
    return len(re.findall(r"<th\b", src[start:end], re.I))


def test_bi_t1_empty_guard_exists():
    assert _BI_EMPTY_GUARD in _src("batch_import.html")


def test_bi_t2_empty_row_appended_to_table_body():
    """空态行必须拼进 tbl（表格体字符串），不能只是别处 alert 一句。"""
    src = _src("batch_import.html")
    pos = _bi_guard_pos(src)
    block = src[pos:pos + 300]
    assert "tbl +=" in block, "空态行没有拼进表格体变量 tbl"
    assert "<tr>" in block and "</tr>" in block, "空态行不是完整的 <tr>"


def test_bi_t3_colspan_matches_js_th_count():
    src = _src("batch_import.html")
    pos = _bi_guard_pos(src)
    block = src[pos:pos + 300]
    m = re.search(r'colspan="(\d+)"', block)
    assert m, "空态行缺少 colspan"
    assert int(m.group(1)) == _bi_th_count(src), (
        f"空态 colspan={m.group(1)} 但 JS 里 thead 实测 {_bi_th_count(src)} 列"
    )


def test_bi_t4_empty_text_present():
    src = _src("batch_import.html")
    pos = _bi_guard_pos(src)
    assert "没有解析到任何数据行" in src[pos:pos + 300], "空态文案缺失或不在该分支内"


def test_bi_t5_guard_inside_preview_function():
    """守卫必须在 renderOpeningStockPreview 里，别加错函数。"""
    src = _src("batch_import.html")
    fn = src.find("function renderOpeningStockPreview")
    assert fn != -1
    pos = _bi_guard_pos(src)
    # 函数结束的下一个顶层 function 之前
    nxt = src.find("\nfunction ", fn + 10)
    assert fn < pos < (nxt if nxt != -1 else len(src)), "空态守卫不在 renderOpeningStockPreview 内"


# ===================== document_ocr.html =====================

_DO_ELSE = "else if (res.items)"


def test_do_t1_empty_branch_exists():
    src = _src("document_ocr.html")
    assert _DO_ELSE in src, "document_ocr.html 找不到 res.items 为空的分支"


def test_do_t2_branch_is_else_of_items_block():
    """必须是「items 有值 → 出表，items 为空数组 → 出提示」的 else 关系，
    不能用 `if (!res.items.length)` 独立写，否则 items 为 undefined 时会误报。"""
    src = _src("document_ocr.html")
    pos = src.find(_DO_ELSE)
    # items 块本身有几百行，窗口要够宽才看得到它的 if
    before = src[max(0, pos - 2500):pos]
    assert "res.items && res.items.length > 0" in before, (
        "else 分支没有紧跟 items 非空判断（必须是同一 if 的 else，"
        "不能写成独立的 if (!res.items.length)，否则 items 为 undefined 时会误报）"
    )


def test_do_t3_empty_text_present():
    src = _src("document_ocr.html")
    pos = src.find(_DO_ELSE)
    assert "未识别到物料明细行" in src[pos:pos + 300], "空态文案缺失或不在该分支内"


def test_do_t4_uses_alert_not_bare_text():
    src = _src("document_ocr.html")
    pos = src.find(_DO_ELSE)
    assert "alert" in src[pos:pos + 300], "空态应是可见的 alert 提示块"


def test_do_t5_still_has_global_fallback():
    """原有的「整份结果为空」兜底不能被这次改动顶掉。"""
    src = _src("document_ocr.html")
    assert "未能识别到有效的单据信息" in src, "整份结果为空的兜底提示被误删"


# ===================== 反回归：两处文案都必须在模板源码里 =====================

@pytest.mark.parametrize("name,needle", [
    ("batch_import.html", "没有解析到任何数据行"),
    ("document_ocr.html", "未识别到物料明细行"),
])
def test_t6_text_in_template_source(name, needle):
    assert needle in _src(name), f"{name} 源码里找不到空态文案（别改成运行时动态生成）"
