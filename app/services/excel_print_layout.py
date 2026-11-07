"""Size generated print cells without editing saved templates or business values."""
from copy import copy
from functools import lru_cache
import math
import re
import unicodedata

from openpyxl.utils import column_index_from_string, get_column_letter, range_boundaries
from PIL import ImageFont

_FONT_FILES = {
    '宋体': ('simsun.ttc', 'simsun.ttc'), 'simsun': ('simsun.ttc', 'simsun.ttc'),
    '新宋体': ('simsun.ttc', 'simsun.ttc'), 'nsimsun': ('simsun.ttc', 'simsun.ttc'),
    '楷体': ('simkai.ttf', 'simkai.ttf'), 'kaiti': ('simkai.ttf', 'simkai.ttf'),
    '仿宋': ('simfang.ttf', 'simfang.ttf'), 'fangsong': ('simfang.ttf', 'simfang.ttf'),
    '微软雅黑': ('msyh.ttc', 'msyhbd.ttc'), 'microsoft yahei': ('msyh.ttc', 'msyhbd.ttc'),
    'calibri': ('calibri.ttf', 'calibrib.ttf'), 'arial': ('arial.ttf', 'arialbd.ttf'),
    'times new roman': ('times.ttf', 'timesbd.ttf'),
}


@lru_cache(maxsize=32)
def _print_font(name, bold):
    files = _FONT_FILES.get(str(name or '').lower())
    if not files:
        return None
    try:
        return ImageFont.truetype(files[bool(bold)], 64)
    except OSError:
        return None


def print_column_width(sheet, column):
    """Convert Excel character widths to pixels, including its five-pixel padding."""
    dimension = sheet.column_dimensions.get(get_column_letter(column))
    if dimension is None:
        dimension = next((item for item in sheet.column_dimensions.values()
            if (item.min or column_index_from_string(item.index)) <= column <=
               (item.max or item.min or column_index_from_string(item.index))), None)
    if dimension is not None and dimension.hidden:
        return 0
    width = dimension.width if dimension is not None else sheet.sheet_format.defaultColWidth
    width = float(width if width is not None else 8.43)
    width = min(255, max(0, width)) if math.isfinite(width) else 8.43
    return math.floor(width * 12 if width < 1 else width * 7 + 5)


def print_row_height(sheet, row):
    """Read visible row height in points without creating row dimensions."""
    dimension = sheet.row_dimensions.get(row)
    if dimension is not None and dimension.hidden:
        return 0
    height = dimension.height if dimension is not None else None
    return min(409.5, max(1, float(height or sheet.sheet_format.defaultRowHeight or 15)))


def print_cell_width(sheet, cell, right, end_column=None):
    """Allow ordinary Excel text to use adjacent empty, undecorated cells."""
    end = end_column or cell.column
    width = sum(print_column_width(sheet, column) for column in range(cell.column, end + 1))
    if (end != cell.column or cell.alignment.wrap_text or
            cell.alignment.horizontal not in (None, 'general', 'left') or
            any(getattr(getattr(cell.border, side), 'style', None) for side in ('left', 'right', 'top', 'bottom'))):
        return width
    for column in range(end + 1, right + 1):
        following = sheet.cell(cell.row, column)
        if (following.value not in (None, '') or following.fill.patternType or
                any(getattr(getattr(following.border, side), 'style', None) for side in ('left', 'right', 'top', 'bottom')) or
                any(merged.min_row <= cell.row <= merged.max_row and
                    merged.min_col <= column <= merged.max_col for merged in sheet.merged_cells.ranges)):
            break
        if any(getattr(image.anchor, '_from', None) is not None and
               image.anchor._from.row + 1 == cell.row and image.anchor._from.col + 1 == column
               for image in sheet._images):
            break
        width += print_column_width(sheet, column)
    return width


@lru_cache(maxsize=8192)
def _character_width(character, half_width=False, font=None):
    if unicodedata.combining(character):
        return 0
    if unicodedata.east_asian_width(character) in ('W', 'F'):
        return 1
    if font is not None:
        return font.getlength(character) / font.size
    if half_width and ord(character) < 128:
        return .5
    if character in 'WMwm@%':
        return 1
    if character.isspace():
        return .4
    if character.isupper():
        return .8
    if character.isalnum():
        return .65
    return .55


def _line_count(text, width, size, bold, font_name):
    lines = 0
    half_width = str(font_name or '').lower() in ('宋体', '新宋体', '楷体', '仿宋', 'simsun', 'nsimsun', 'kaiti', 'fangsong')
    font = _print_font(font_name, bool(bold))
    unit = size * 96 / 72 * (1.05 if bold and font is None else 1)
    for paragraph in text.replace('\t', '    ').split('\n'):
        lines += 1
        used = 0
        for token in re.findall(r'[A-Za-z0-9_]+|.', paragraph):
            advance = sum(_character_width(character, half_width, font) for character in token) * unit
            if advance <= width:
                if used and used + advance > width:
                    lines += 1
                    used = 0
                used += advance
            else:
                for character in token:
                    advance = _character_width(character, half_width, font) * unit
                    if used and used + advance > width:
                        lines += 1
                        used = 0
                    used += advance
    return lines


def fit_print_rows(sheet, *, strict=False):
    """Grow generated rows for complete text; preserve values, merges and hidden data."""
    from services.report_print_preview import _display_value
    references = re.findall(r'\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?\d+', str(sheet.print_area or ''))
    bounds = [range_boundaries(reference) for reference in references] or [(1, 1, sheet.max_column, sheet.max_row)]
    merges = {(merged.min_row, merged.min_col): merged for merged in sheet.merged_cells.ranges}
    for left, top, right, bottom in bounds:
        if (right - left + 1) * (bottom - top + 1) > 150000:
            if strict:
                raise ValueError('打印区域过大，请精简模板或缩小打印范围')
            continue
        for row in sheet.iter_rows(min_row=top, max_row=bottom, min_col=left, max_col=right):
            for cell in row:
                if (cell.value in (None, '') or cell.data_type == 'f' or not print_row_height(sheet, cell.row) or
                        not print_column_width(sheet, cell.column) or cell.alignment.textRotation or
                        re.search(r'\{img_(?:barcode|qrcode):', str(cell.value))):
                    continue
                merged = merges.get((cell.row, cell.column))
                end_row, end_column = (merged.max_row, merged.max_col) if merged else (cell.row, cell.column)
                if end_row > bottom or end_column > right:
                    continue
                try:
                    text = _display_value(cell)
                except ValueError:
                    text = str(cell.value)
                size = min(72, max(6, float(cell.font.sz or 11)))
                width = max(1, print_cell_width(sheet, cell, right, end_column) - 8)
                count = _line_count(text, width, size, cell.font.bold, cell.font.name)
                if not cell.alignment.wrap_text and count > 1:
                    alignment = copy(cell.alignment)
                    alignment.wrap_text = True
                    cell.alignment = alignment
                    width = max(1, sum(print_column_width(sheet, col)
                        for col in range(cell.column, end_column + 1)) - 8)
                    count = _line_count(text, width, size, cell.font.bold, cell.font.name)
                needed = math.ceil(count * size * 1.2 + 3)
                visible_rows = [number for number in range(cell.row, end_row + 1) if print_row_height(sheet, number)]
                if strict and needed > 409.5 * len(visible_rows):
                    raise ValueError(f'单元格 {cell.coordinate} 内容过长，请加宽列、拆分内容或调整模板后打印')
                extra = needed - sum(print_row_height(sheet, number) for number in visible_rows)
                for number in reversed(visible_rows):
                    if extra <= 0:
                        break
                    height = print_row_height(sheet, number)
                    growth = min(extra, 409.5 - height)
                    sheet.row_dimensions[number].height = height + growth
                    extra -= growth
