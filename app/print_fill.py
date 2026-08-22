# -*- coding: utf-8 -*-
"""Excel 打印模板填充引擎（PRINT-TEMPLATE-F01）。

打印模板仅允许 Excel：用户上传带 `{占位符}` 的 .xlsx 模板，打印时选择模板后，
本模块把单据数据填充进模板并生成可下载的 .xlsx。

支持的占位符：
- 单据级：{order.order_no}、{order.date}、{order.supplier.name}、
  {order.supplier.contact}、{order.supplier.phone}、{order.supplier.address}、
  {order.customer}、{order.purpose}、{order.remark}、{order.picker}、
  {order.operator.username}、{total_quantity}、{total_amount}、{print_date}
- 明细级：{item.material.code}、{item.material.name}、{item.material.spec}、
  {item.material.brand}、{item.material.unit.name}、{item.quantity}、
  {item.price}、{item.amount}、{item.contract_no}、{item.project_name}、
  {item.remark}

模板内第一处含 `{item.` 的行视为"明细模板行"，其下方到首个含订单级占位符
（如 {total_*} / {order.} / {print_date}）之前的行为"示例数据行"。填充时按实际
明细条数在明细块上复制/删除行，并从明细模板行复制样式与会合计性保证版式一致。
"""
from __future__ import annotations

import io
import os
import re
import zipfile
from copy import copy
from datetime import datetime

from openpyxl import load_workbook

_PLACEHOLDER_RE = re.compile(r'\{([^{}]+)\}')
# 明细扩展时判断"明细块结束边界"用到的订单级占位符前缀
_ORDER_LEVEL_HINTS = ('{total_', '{order.', '{print_date}', '{today}')

# 合法占位符：order.* / item.* 为通配（按属性路径解析），其余为显式白名单
_EXPLICIT_TOKENS = ('total_quantity', 'total_amount', 'print_date', 'today')

# 上传时防超大/解压炸弹/畸形文件的安全阈值
_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50MB 解压后上限
_MAX_TEMPLATE_ROWS = 2000
_MAX_TEMPLATE_COLS = 100


def _is_supported_placeholder(token):
    return token.startswith('order.') or token.startswith('item.') or token in _EXPLICIT_TOKENS


def validate_template_file(raw: bytes) -> str:
    """校验上传的打印模板原始字节，返回错误信息；合法则返回空串。

    覆盖三类问题：
    - 损坏/非 xlsx（openpyxl 打开失败或解压非法）→ 明确报错而非运行时失败
    - 超大文件 / zip 解压炸弹（解压后体积超限）→ 拒绝
    - 模板里含引擎不支持的 {占位符} → 拒绝，避免打印时静默输出原文
    """
    if not raw:
        return '打印模板文件为空'
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        total = sum(i.file_size for i in zf.infolist())
        zf.close()
    except zipfile.BadZipFile:
        return '不是有效的 Excel 文件（仅支持 .xlsx）'
    if total > _MAX_UNCOMPRESSED_BYTES:
        return '打印模板文件解压后过大，请压缩后重新上传'
    try:
        workbook = load_workbook(io.BytesIO(raw), read_only=False)
    except zipfile.BadZipFile:
        return '不是有效的 Excel 文件（仅支持 .xlsx）'
    except Exception:  # noqa: BLE001 开放异常：解析层面的任何失败都按坏文件处理
        return 'Excel 文件损坏或无法解析，请重新上传有效的 .xlsx 模板'
    try:
        for ws in workbook.worksheets:
            if (ws.max_row or 0) > _MAX_TEMPLATE_ROWS or (ws.max_column or 0) > _MAX_TEMPLATE_COLS:
                return f'工作表「{ws.title}」规模过大（行>%d 或列>%d），请精简模板' % (
                    _MAX_TEMPLATE_ROWS, _MAX_TEMPLATE_COLS)
            for row in ws.iter_rows():
                for cell in row:
                    if isinstance(cell.value, str):
                        for token in _PLACEHOLDER_RE.findall(cell.value):
                            if not _is_supported_placeholder(token):
                                return '模板包含不支持的占位符 {%s}，请使用 order.* / item.* / %s' % (
                                    token, ' / '.join(_EXPLICIT_TOKENS))
    finally:
        workbook.close()
    return ''


def template_file_abspath(excel_template_path, static_folder):
    """把模板记录的 excel_template_path（静态 URL）解析为绝对文件路径。"""
    if not excel_template_path:
        return None
    p = excel_template_path.replace('\\', '/')
    if p.startswith('/static/'):
        rel = p[len('/static/'):]
    elif p.startswith('uploads/'):
        rel = p
    else:
        # 历史/兜底：仅保留文件名放入 uploads/print_templates
        rel = os.path.join('uploads', 'print_templates', os.path.basename(p))
    return os.path.join(static_folder, rel)


def _num(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _fmt(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return '是' if value else '否'
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # 保留数值，供 Excel 计算与对齐
        return value
    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M')
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    return str(value)


def _resolve_path(obj, parts):
    for part in parts:
        if obj is None:
            return None
        attr = getattr(obj, part, None)
        if callable(attr):
            attr = attr()
        obj = attr
    return obj


class _Filler:
    """对单个工作表执行占位符填充与明细行扩展。"""

    def __init__(self, order, items, date_str):
        self.order = order
        self.items = items or []
        self.date_str = date_str or datetime.now().strftime('%Y-%m-%d')

    # ---------- 解析 ----------
    def order_value(self, token):
        """解析订单级占位符；明细占位符返回 _KEEP 哨兵。"""
        if token.startswith('item.'):
            return _KEEP
        if token == 'total_quantity':
            return _fmt(sum(_num(i.quantity) for i in self.items))
        if token == 'total_amount':
            return self.order.total_amount
        if token in ('print_date', 'today'):
            return self.date_str
        if token.startswith('order.'):
            return _fmt(_resolve_path(self.order, token.split('.')[1:]))
        return _fmt(_resolve_path(self.order, [token]))

    def item_value(self, token, item):
        if token.startswith('item.'):
            return _fmt(_resolve_path(item, token.split('.')[1:]))
        return self.order_value(token)

    @staticmethod
    def _replace_cell(text, resolver):
        """替换一个单元格中的占位符。

        整个单元格恰好是一个占位符时返回原始解析值，保留数值类型；
        否则在文本中逐个替换，未命中的 (item 或缺失) 保留原占位符文本。
        """
        if not isinstance(text, str):
            return text
        stripped = text.strip()
        full = _PLACEHOLDER_RE.fullmatch(stripped)
        if full:
            value = resolver(full.group(1))
            if value is _KEEP or value is None:
                return text
            return value

        def _repl(m):
            value = resolver(m.group(1))
            if value is _KEEP or value is None:
                return m.group(0)
            return str(value)

        return _PLACEHOLDER_RE.sub(_repl, text)

    # ---------- 填充 ----------
    def fill(self, ws):
        max_row = ws.max_row or 1
        max_col = ws.max_column or 1

        # 1) 定位"明细模板行"
        template_row = None
        col_cells = {}
        for r in range(1, max_row + 1):
            has_item = any(
                isinstance(ws.cell(r, c).value, str)
                and '{item.' in ws.cell(r, c).value
                for c in range(1, max_col + 1)
            )
            if has_item:
                template_row = r
                break

        # 无明细占位符：纯订单级模板
        if template_row is None:
            for r in range(1, max_row + 1):
                for c in range(1, max_col + 1):
                    cell = ws.cell(r, c)
                    if isinstance(cell.value, str):
                        cell.value = self._replace_cell(cell.value, self.order_value)
            return

        for c in range(1, max_col + 1):
            v = ws.cell(template_row, c).value
            if isinstance(v, str) and '{item.' in v:
                col_cells[c] = v

        # 边界须在订单级填充（step 2）之前基于原始模板计算：
        # 因为 step 2 会先把边界行的 {total_*}/{order.} 占位符替换成数值，
        # 若之后才探测边界，原始占位符已消失，无法识别明细块的结束行。
        boundary = self._find_boundary(ws, template_row, max_row, max_col)

        # 2) 订单级填充（跳过明细模板行；含 item 占位符的单元格仍可填充其中的订单级占位符）
        for r in range(1, max_row + 1):
            if r == template_row:
                continue
            for c in range(1, max_col + 1):
                cell = ws.cell(r, c)
                if isinstance(cell.value, str):
                    cell.value = self._replace_cell(cell.value, self.order_value)

        # 3) 明细行扩展
        sample_count = max(0, boundary - template_row - 1 if boundary else 0)
        item_count = len(self.items)

        if item_count == 0:
            for c, orig in col_cells.items():
                ws.cell(template_row, c).value = self._replace_cell(orig, lambda t: '')
            return

        capacity = sample_count + 1
        if item_count < capacity:
            # 删除多余的示例行
            ws.delete_rows(template_row + item_count, capacity - item_count)
        elif item_count > capacity:
            # 在示例块之后（边界行之前）插入缺失行
            ws.insert_rows(template_row + sample_count + 1, item_count - capacity)

        self._write_items(ws, template_row, col_cells, item_count)

    def _find_boundary(self, ws, template_row, max_row, max_col):
        """返回明细块结束边界的第一个订单级占位符行号（不含）；找不到返回 None。"""
        for r in range(template_row + 1, max_row + 1):
            for c in range(1, max_col + 1):
                v = ws.cell(r, c).value
                if not isinstance(v, str):
                    continue
                lowered = v
                if any(hint in lowered for hint in _ORDER_LEVEL_HINTS):
                    return r
                # 含非 item 占位符也算边界（更低优先，避免误吞纯文本示例行）
                if _contains_order_placeholder(v):
                    return r
        return None

    def _write_items(self, ws, template_row, col_cells, item_count):
        template_height = ws.row_dimensions[template_row].height
        for index in range(item_count):
            item = self.items[index]
            row_idx = template_row + index
            if template_height:
                ws.row_dimensions[row_idx].height = template_height
            for c, orig in col_cells.items():
                cell = ws.cell(row_idx, c)
                cell.value = self._replace_cell(
                    orig, lambda t, item=item: self.item_value(t, item)
                )
                source = ws.cell(template_row, c)
                cell._style = copy(source._style)


def _contains_order_placeholder(text):
    """文本是否含非 item 的占位符（用于边界探测的兜底）。"""
    if not isinstance(text, str):
        return False
    for token in _PLACEHOLDER_RE.findall(text):
        if not token.startswith('item.'):
            return True
    return False


_KEEP = object()


def build_filled_print_excel(template_path, order, items=None, date_str=None):
    """按订单数据填充 Excel 模板，返回可下载的 BytesIO。

    template_path：模板 .xlsx 的绝对路径；
    order：InOrder 或 OutOrder（含 items / supplier / operator 等关系）；
    items：默认取 order.items，也可显式传入。
    """
    workbook = load_workbook(template_path)
    filler = _Filler(order, items if items is not None else order.items, date_str)
    for ws in workbook.worksheets:
        filler.fill(ws)
    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


# ==================== 在线网格编辑（PRINT-TEMPLATE-F02） ====================
#
# 浏览器"在线修改打印模板"：把 .xlsx 模板序列化为 JSON 网格供前端编辑，
# 前端改完单元格值后回写。合并单元格只在左上角锚点处可编辑，样式/合并保持
# 原样，不在此处增删——避免前端破坏版式。

_SCALAR_TYPES = (str, int, float, bool)


def _cell_to_json(value):
    """把单元格值转为可 JSON 序列化的标量；其他类型（公式对象等）转字符串。"""
    if isinstance(value, _SCALAR_TYPES) and value is not None:
        if isinstance(value, bool):
            return value
        if isinstance(value, float):
            from math import isfinite
            return value if isfinite(value) else None
        return value
    if value is None:
        return None
    return str(value)


def _sheet_merge_anchors(ws):
    """返回该工作表所有合并区域的锚点（左上角单元格）集合 {(min_row, min_col)}。"""
    anchors = set()
    for rng in ws.merged_cells.ranges:
        anchors.add((rng.min_row, rng.min_col))
    return anchors


def serialize_print_template_grid(template_path):
    """把打印模板 .xlsx 序列化为浏览器网格 JSON。

    返回：{sheets: [{name, max_row, max_col, merges, cells}]}
    - merges: [{row, col, rowspan, colspan}]（仅给前端展示只读提示，编辑锚点=左上角）
    - cells: [{row, col, value, merged}]，只含非空单元格；合并区仅在锚点给出。
    """
    workbook = load_workbook(template_path, data_only=False)
    try:
        sheets = []
        for ws in workbook.worksheets:
            anchors = _sheet_merge_anchors(ws)
            merges = []
            for rng in ws.merged_cells.ranges:
                merges.append({
                    'row': rng.min_row,
                    'col': rng.min_col,
                    'rowspan': rng.max_row - rng.min_row + 1,
                    'colspan': rng.max_col - rng.min_col + 1,
                })
            cells = []
            for r in range(1, (ws.max_row or 1) + 1):
                for c in range(1, (ws.max_column or 1) + 1):
                    if (r, c) in anchors:
                        continue  # 非锚点合并格，值在锚点处读取
                    cell = ws.cell(r, c)
                    value = _cell_to_json(cell.value)
                    if value is not None and value != '':
                        cells.append({
                            'row': r, 'col': c, 'value': value,
                            'merged': False,
                        })
            # 合并锚点单元格（值为本身就是该区域的值）
            for (r, c) in sorted(anchors):
                value = _cell_to_json(ws.cell(r, c).value)
                cells.append({'row': r, 'col': c,
                              'value': value if value is not None else '',
                              'merged': True})
            cells.sort(key=lambda x: (x['row'], x['col']))
            sheets.append({
                'name': ws.title,
                'max_row': ws.max_row or 1,
                'max_col': ws.max_column or 1,
                'merges': merges,
                'cells': cells,
            })
        return {'sheets': sheets}
    finally:
        workbook.close()


def _validate_grid_value(value):
    """校验网格待回写值，返回错误信息；合法返回空串。"""
    if value is None:
        return ''
    if isinstance(value, bool):
        return ''
    if isinstance(value, (int, float)):
        return ''
    if isinstance(value, str):
        if len(value) > 32767:
            return '单元格文本过长，单格最多 32767 字符'
        for token in _PLACEHOLDER_RE.findall(value):
            if not _is_supported_placeholder(token):
                return '模板包含不支持的占位符 {%s}，请使用 order.* / item.* / %s' % (
                    token, ' / '.join(_EXPLICIT_TOKENS))
        return ''
    return '不支持的单元格值类型'


def apply_print_template_grid(template_path, sheets_data):
    """把前端编辑后的网格写回 .xlsx 模板。

    sheets_data: [{name, upserts:[[row, col, value], ...], del_rows:[row, ...]}]
    - upserts 写/覆盖单元格值（'' 或 None 清除单元格）；保留样式与合并。
    - del_rows 删除指定行（整行，序号由小到大），用于清理多余示例行。
    全程占位符白名单校验，任何非法占位符立即报错且不落盘（原子性）。
    """
    sheets_data = sheets_data or []
    workbook = load_workbook(template_path)
    try:
        sheets_map = {ws.title: ws for ws in workbook.worksheets}
        for sheet in sheets_data:
            name = (sheet.get('name') or '').strip()
            ws = sheets_map.get(name)
            if ws is None:
                raise ValueError(f'工作表「{name}」不存在')
            row_map = {}
            for (r, c, value) in (sheet.get('upserts') or []):
                r = int(r)
                c = int(c)
                if r < 1 or c < 1:
                    raise ValueError(f'单元格坐标无效：第{r}行第{c}列')
                if r > _MAX_TEMPLATE_ROWS or c > _MAX_TEMPLATE_COLS:
                    raise ValueError(f'单元格坐标超出上限：第{r}行第{c}列')
                msg = _validate_grid_value(value)
                if msg:
                    raise ValueError(f'第{r}行第{c}列：{msg}')
                row_map.setdefault(r, {})[c] = value
            # 先处理单元格值（行索引删除前基于原始行号）
            for r, cols in sorted(row_map.items()):
                for c, value in cols.items():
                    cell = ws.cell(r, c)
                    if value is None or (isinstance(value, str) and value.strip() == ''):
                        cell.value = None
                    else:
                        cell.value = value
            del_rows = sorted(set(int(x) for x in (sheet.get('del_rows') or [])), reverse=True)
            for r in del_rows:
                if r < 1:
                    continue
                ws.delete_rows(r, 1)
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return output
    finally:
        workbook.close()