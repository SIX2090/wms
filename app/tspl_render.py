# -*- coding: utf-8 -*-
"""芯烨（Xprinter）TSPL 标签指令渲染器（PRINT-TEMPLATE TSPL 直出通道）。

把 LabelTemplate 的毫米网格布局渲染为 TSPL 指令文本，供打印代理直发
芯烨打印机（跳过浏览器/Windows 驱动），相比 HTML 页面打印：定位更准、
出纸更快、条码由打印机内置指令绘制更清晰、扫描识别率更高。

模板坐标单位是 mm（width/height/cell_width/cell_height，外加
layout.cells 的 row/col 网格坐标与可选 rowHeights），渲染时按 dpi
换算为 dot（203dpi≈8 dot/mm，300dpi≈12 dot/mm）。

字段类型与 TSPL 命令映射：
- barcode → BARCODE（一维码 Code128，内容由打印机绘制）
- qrcode  → QRCODE（二维码，内容由打印机绘制）
- 其余文本字段（name/code/spec/unit_name/stock/category_name/
  supplier_name/price/date 等）→ TEXT

中文限制：TSPL 内置点阵字体（"0"~"8"）不含中文字形，中文内容改用
TSS 向量字体（"TSS24.BF2"，需打印机已下载该字体）；纯 ASCII/数字
内容用内置 "0" 等宽字体。

本模块为纯逻辑、无 Flask/数据库依赖，便于独立单元测试；坏输入不抛
异常（跳过无效单元格），保证坏模板不会让打印链路崩溃。
"""
from __future__ import annotations

# 渲染为 TSPL BARCODE / QRCODE 的字段名；其余字段一律按 TEXT 处理。
BARCODE_FIELD = "barcode"
QRCODE_FIELD = "qrcode"

# 参考分辨率（dots per inch）。芯烨标签机常见 203 / 300 dpi。
DEFAULT_DPI = 203
# mm -> inch 换算分母。
_MM_PER_INCH = 25.4


def mm_to_dot(mm, dpi=DEFAULT_DPI):
    """毫米换算为打印机 dot（四舍五入取整）。"""
    try:
        dpi = float(dpi)
    except (TypeError, ValueError):
        dpi = float(DEFAULT_DPI)
    if dpi <= 0:
        dpi = float(DEFAULT_DPI)
    try:
        mm = float(mm)
    except (TypeError, ValueError):
        mm = 0.0
    return int(round(mm * dpi / _MM_PER_INCH))


def _num(value, default):
    """宽松数值解析，失败回退默认值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _fmt_num(value):
    """格式化 mm 数值，整数去掉小数点，便于生成简洁的 SIZE/GAP 指令。"""
    f = float(value)
    return str(int(f)) if f == int(f) else ("%g" % f)


def _is_cjk(text):
    """判断文本是否包含 CJK 汉字（决定用 TSS 向量字体还是内置点阵字体）。"""
    for ch in str(text):
        if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
            return True
    return False


def _escape(text):
    """TSPL 字符串以双引号包裹，内容里的双引号会截断指令，统一替换为单引号。"""
    return str(text).replace('"', "'").replace("\\", " ")


def _text_command(x_dot, y_dot, content, font_size):
    """生成 TEXT 指令。中文用 TSS 向量字体，ASCII 用内置 "0" 字体。"""
    if _is_cjk(content):
        font = "TSS24.BF2"
        base = 24.0
    else:
        font = "0"
        base = 8.0
    scale = max(1, min(10, int(round(_num(font_size, 10) / base))))
    return 'TEXT {x},{y},"{f}",0,{s},{s},"{c}"'.format(
        x=x_dot, y=y_dot, f=font, s=scale, c=_escape(content))


def _barcode_command(x_dot, y_dot, content, height_mm, dpi):
    """生成一维码（Code128）指令。条码高度 mm->dot，缺省 10mm。"""
    height_dot = mm_to_dot(height_mm if height_mm else 10, dpi)
    return 'BARCODE {x},{y},"128",{h},1,0,2,2,"{c}"'.format(
        x=x_dot, y=y_dot, h=height_dot, c=_escape(content))


def _qrcode_command(x_dot, y_dot, content):
    """生成二维码指令（纠错级 M，模块宽 4 dot，自动版本）。"""
    return 'QRCODE {x},{y},M,4,A,0,"{c}"'.format(
        x=x_dot, y=y_dot, c=_escape(content))


def _row_offset_mm(row, cell_height, row_heights):
    """计算某行起始 y 偏移（mm）。有 rowHeights 时按实际行高累加。"""
    if row_heights and row < len(row_heights):
        return sum(_num(h, cell_height) for h in row_heights[:row])
    return row * cell_height


def _render_cell(cell, data, cell_width, cell_height, row_heights, dpi):
    """渲染单个单元格为一条 TSPL 指令；无效/空内容返回空串。"""
    if not isinstance(cell, dict):
        return ""
    field = cell.get("field")
    if not field:
        return ""
    row = int(_num(cell.get("row"), 0))
    col = int(_num(cell.get("col"), 0))
    x_dot = mm_to_dot(col * cell_width, dpi)
    y_dot = mm_to_dot(_row_offset_mm(row, cell_height, row_heights), dpi)
    style = cell.get("style") if isinstance(cell.get("style"), dict) else {}
    font_size = _num(style.get("fontSize"), 10)

    if field == BARCODE_FIELD:
        content = str(data.get("barcode") or data.get("code") or "").strip()
        if not content:
            return ""
        return _barcode_command(x_dot, y_dot, content, cell.get("barcodeHeight"), dpi)
    if field == QRCODE_FIELD:
        content = str(data.get("qrcode") or data.get("code") or "").strip()
        if not content:
            return ""
        return _qrcode_command(x_dot, y_dot, content)

    value = data.get(field)
    if value is None:
        # 兼容把静态标签文字放在 cell.text 的用法。
        value = cell.get("text") or ""
    content = str(value).strip()
    if not content:
        return ""
    return _text_command(x_dot, y_dot, content, font_size)


def render_label_tspl(template, data, dpi=DEFAULT_DPI, gap_mm=2):
    """把标签模板 + 数据渲染为完整 TSPL 指令文本。

    参数：
      template: dict，含 width/height/cell_width/cell_height(mm) 与
                layout（dict，含 cells 列表、可选 rowHeights）。
      data:     dict，字段名 -> 值（如 {'name':..,'code':..,'barcode':..}）。
      dpi:      打印机分辨率，默认 203。
      gap_mm:   标签间隙（mm），默认 2。

    返回：以换行分隔的 TSPL 指令字符串，末尾含 PRINT 1,1。
    坏输入不抛异常，返回仅含头尾的最小指令。
    """
    if not isinstance(template, dict):
        template = {}
    if not isinstance(data, dict):
        data = {}
    width_mm = _num(template.get("width"), 90)
    height_mm = _num(template.get("height"), 50)
    cell_width = _num(template.get("cell_width"), 20)
    cell_height = _num(template.get("cell_height"), 10)
    layout = template.get("layout") if isinstance(template.get("layout"), dict) else {}
    cells = layout.get("cells") if isinstance(layout.get("cells"), list) else []
    row_heights = layout.get("rowHeights") if isinstance(layout.get("rowHeights"), list) else []

    lines = [
        "SIZE {w} mm, {h} mm".format(w=_fmt_num(width_mm), h=_fmt_num(height_mm)),
        "GAP {g} mm, 0 mm".format(g=_fmt_num(gap_mm)),
        "DIRECTION 1",
        "CLS",
    ]
    for cell in cells:
        command = _render_cell(cell, data, cell_width, cell_height, row_heights, dpi)
        if command:
            lines.append(command)
    lines.append("PRINT 1,1")
    return "\n".join(lines) + "\n"
