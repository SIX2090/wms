# -*- coding: utf-8 -*-
"""芯烨 TSPL 标签指令渲染器（app/tspl_render.py）单元测试。

覆盖：
- mm -> dot 换算（203 / 300 dpi）
- 指令头尾（SIZE/GAP/DIRECTION/CLS/PRINT）
- 文本字段渲染 + 网格坐标换算（col*cell_width、row*cell_height）
- rowHeights 实际行高累加的 y 偏移
- 一维码（BARCODE/Code128）与二维码（QRCODE）渲染
- 中文内容切换 TSS 向量字体
- 双引号转义、无效/空内容单元格跳过、坏输入不抛异常
"""
from __future__ import annotations

import tspl_render
from tspl_render import mm_to_dot, render_label_tspl


def make_template(**overrides):
    template = {
        "width": 90,
        "height": 50,
        "cols": 5,
        "rows": 6,
        "cell_width": 18,
        "cell_height": 8,
        "layout": {"cells": [], "rowHeights": []},
    }
    template.update(overrides)
    return template


def cell(**kwargs):
    base = {"row": 0, "col": 0, "field": "name", "style": {}}
    base.update(kwargs)
    return base


# ---------- mm -> dot ----------

def test_mm_to_dot():
    """A9 对应测试：mm_to_dot 基本换算。"""
    assert mm_to_dot(25.4, 203) == 203
    assert mm_to_dot(1, 300) == 12


def test_mm_to_dot_203dpi():
    assert mm_to_dot(25.4, 203) == 203
    assert mm_to_dot(1, 203) == 8
    assert mm_to_dot(0, 203) == 0


def test_mm_to_dot_300dpi():
    assert mm_to_dot(25.4, 300) == 300
    assert mm_to_dot(1, 300) == 12


def test_mm_to_dot_bad_input():
    assert mm_to_dot("abc", 203) == 0
    assert mm_to_dot(10, 0) == mm_to_dot(10, 203)  # 非法 dpi 回退 203


# ---------- 头尾结构 ----------

def test_header_and_footer():
    tspl = render_label_tspl(make_template(), {})
    lines = tspl.splitlines()
    assert lines[0] == "SIZE 90 mm, 50 mm"
    assert lines[1] == "GAP 2 mm, 0 mm"
    assert "DIRECTION 1" in lines
    assert "CLS" in lines
    assert lines[-1] == "PRINT 1,1"


# ---------- 文本字段 + 坐标 ----------

def test_text_field_grid_coords():
    # row=1,col=1, cell 18x8mm => x=18mm=144dot, y=8mm=64dot (203dpi)
    tpl = make_template(layout={"cells": [cell(row=1, col=1, field="name",
                                               style={"fontSize": 10})]})
    tspl = render_label_tspl(tpl, {"name": "ABC123"})
    assert 'TEXT 144,64,"0",' in tspl
    assert '"ABC123"' in tspl


def test_rowheights_offsets():
    # rowHeights=[24,36,22]：row=2 => y=24+36=60mm=480dot
    tpl = make_template(layout={"cells": [cell(row=2, col=0, field="name")],
                                "rowHeights": [24, 36, 22]})
    tspl = render_label_tspl(tpl, {"name": "X"})
    assert "TEXT 0,480," in tspl


def test_chinese_uses_tss_font():
    tpl = make_template(layout={"cells": [cell(field="name")]})
    tspl = render_label_tspl(tpl, {"name": "6204轴承"})
    assert '"TSS24.BF2"' in tspl
    assert "6204轴承" in tspl


def test_font_scale_from_size():
    tpl = make_template(layout={"cells": [cell(field="code", style={"fontSize": 20})]})
    tspl = render_label_tspl(tpl, {"code": "WL001"})
    # ASCII 基准 8 => 20/8 ≈ 2
    assert '"0",0,2,2,' in tspl


# ---------- 条码 / 二维码 ----------

def test_barcode_field():
    tpl = make_template(layout={"cells": [cell(field="barcode", barcodeHeight=14)]})
    tspl = render_label_tspl(tpl, {"code": "WL001"})
    # barcodeHeight 14mm => 112dot；内容回退 code
    assert 'BARCODE 0,0,"128",112,1,0,2,2,"WL001"' in tspl


def test_barcode_prefers_barcode_value():
    tpl = make_template(layout={"cells": [cell(field="barcode")]})
    tspl = render_label_tspl(tpl, {"barcode": "B999", "code": "WL001"})
    assert '"B999"' in tspl


def test_qrcode_field():
    tpl = make_template(layout={"cells": [cell(field="qrcode")]})
    tspl = render_label_tspl(tpl, {"code": "WL001"})
    assert 'QRCODE 0,0,M,4,A,0,"WL001"' in tspl


def test_barcode_empty_content_skipped():
    tpl = make_template(layout={"cells": [cell(field="barcode")]})
    tspl = render_label_tspl(tpl, {})
    assert "BARCODE" not in tspl


# ---------- 健壮性 ----------

def test_escape_quotes():
    tpl = make_template(layout={"cells": [cell(field="name")]})
    tspl = render_label_tspl(tpl, {"name": '5" 轴承'})
    assert '"5\' 轴承"' in tspl


def test_skip_invalid_cells():
    tpl = make_template(layout={"cells": [
        "not-a-dict",
        cell(field=None),
        cell(field="name"),          # 有内容
        cell(field="spec"),          # data 无 spec -> 空跳过
    ]})
    tspl = render_label_tspl(tpl, {"name": "N1"})
    assert tspl.count("TEXT") == 1


def test_bad_template_and_data_no_crash():
    assert render_label_tspl(None, None).startswith("SIZE")
    assert "PRINT 1,1" in render_label_tspl("x", [])


def test_static_text_cell():
    # 无对应字段时用 cell.text 作为静态文字
    tpl = make_template(layout={"cells": [cell(field="label", text="合格") ]})
    tspl = render_label_tspl(tpl, {})
    assert "合格" in tspl


def test_render_label_tspl():
    """A9 对应测试：render_label_tspl 端到端渲染含文本与一维码。"""
    tpl = make_template(layout={"cells": [
        cell(field="name"),
        cell(field="barcode", barcodeHeight=14),
    ]})
    tspl = render_label_tspl(tpl, {"name": "6204轴承", "code": "WL001"})
    assert tspl.startswith("SIZE 90 mm, 50 mm")
    assert "TEXT" in tspl
    assert "BARCODE" in tspl and '"WL001"' in tspl
    assert tspl.rstrip().endswith("PRINT 1,1")


def test_module_exposes_api():
    assert callable(tspl_render.render_label_tspl)
    assert callable(tspl_render.mm_to_dot)
