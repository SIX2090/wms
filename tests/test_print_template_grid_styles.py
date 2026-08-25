# -*- coding: utf-8 -*-
"""打印模板网格样式序列化（PRINT-TEMPLATE-F05-A1）测试。

覆盖 serialize_print_template_grid 的样式/尺寸输出：
- 字体（加粗/斜体/下划线/字体名/字号/颜色）、背景色、对齐、自动换行、边框
- 空值但带边框的单元格（合计行边框格）也会输出
- col_widths / row_heights 仅输出显式设置的尺寸
- 合并锚点单元格同样携带 style
- theme/indexed 颜色不输出
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)


def _styled_workbook(path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    wb = Workbook()
    ws = wb.active
    ws.title = "模板"
    ws.cell(1, 1, "采购入库单")
    ws.cell(1, 1).font = Font(name="微软雅黑", size=16, bold=True,
                              color="FFFF0000")
    ws.cell(1, 1).alignment = Alignment(horizontal="center", vertical="center",
                                        wrap_text=True)
    ws.cell(1, 1).fill = PatternFill("solid", fgColor="FFFFF2CC")
    thin = Side(style="thin")
    # 空值但带边框的合计行单元格
    ws.cell(3, 2).border = Border(top=thin, right=thin, bottom=thin, left=thin)
    ws.cell(4, 1, "{item.material.name}")
    ws.cell(4, 1).font = Font(italic=True, underline="single")
    ws.merge_cells("A1:C1")
    ws.column_dimensions["B"].width = 20.5
    ws.row_dimensions[1].height = 30.0
    wb.save(path)
    wb.close()


def _cell_map(sheet):
    return {(c["row"], c["col"]): c for c in sheet["cells"]}


def test_serialize_outputs_font_fill_alignment(tmp_path):
    from print_fill import serialize_print_template_grid
    p = str(tmp_path / "t.xlsx")
    _styled_workbook(p)
    grid = serialize_print_template_grid(p)
    sheet = grid["sheets"][0]
    cells = _cell_map(sheet)
    title = cells[(1, 1)]
    assert title["merged"] is True
    style = title["style"]
    assert style["bold"] is True
    assert style["font_name"] == "微软雅黑"
    assert style["font_size"] == 16.0
    assert style["font_color"] == "#FF0000"
    assert style["bg_color"] == "#FFF2CC"
    assert style["h_align"] == "center"
    assert style["v_align"] == "center"
    assert style["wrap"] is True


def test_serialize_outputs_empty_cell_with_border(tmp_path):
    from print_fill import serialize_print_template_grid
    p = str(tmp_path / "t.xlsx")
    _styled_workbook(p)
    sheet = serialize_print_template_grid(p)["sheets"][0]
    cells = _cell_map(sheet)
    # 空值但带边框的单元格必须出现在网格里（否则边框样式丢失）
    assert (3, 2) in cells
    border = cells[(3, 2)]["style"]["border"]
    assert border == {"top": "thin", "right": "thin",
                      "bottom": "thin", "left": "thin"}
    item = cells[(4, 1)]
    assert item["style"]["italic"] is True
    assert item["style"]["underline"] is True


def test_serialize_outputs_dimensions(tmp_path):
    from print_fill import serialize_print_template_grid
    p = str(tmp_path / "t.xlsx")
    _styled_workbook(p)
    sheet = serialize_print_template_grid(p)["sheets"][0]
    assert sheet["col_widths"] == {"2": 20.5}
    assert sheet["row_heights"] == {"1": 30.0}


def test_serialize_skips_theme_color_and_default_style(tmp_path):
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from openpyxl.styles.colors import Color
    from print_fill import serialize_print_template_grid
    p = str(tmp_path / "t2.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "模板"
    ws.cell(1, 1, "纯文本无样式")
    ws.cell(2, 1, "主题色")
    ws.cell(2, 1).font = Font(color=Color(theme=1))
    wb.save(p)
    wb.close()
    sheet = serialize_print_template_grid(p)["sheets"][0]
    cells = _cell_map(sheet)
    # 默认样式单元格不输出 style 键
    assert "style" not in cells[(1, 1)]
    # theme 颜色不输出 font_color
    assert "font_color" not in cells[(2, 1)].get("style", {})
    assert sheet["col_widths"] == {}
    assert sheet["row_heights"] == {}
