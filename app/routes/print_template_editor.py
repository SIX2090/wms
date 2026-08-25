#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 打印模板在线编辑（PRINT-TEMPLATE-F02）路由模块。
#
# 浏览器"在线修改打印模板"：把 Excel 模板序列化为 JSON 网格供前端编辑，
# 编辑完成回写模板文件。所有导入/出库（及后续其他单据）打印模板共用一个
# 内核路由，注册时指定模板模型即可。
#
# 路由：
#   GET  /{prefix}_print_template/<id>/edit   在线编辑页面
#   GET  /{prefix}_print_template/<id>/grid   读取模板网格 JSON
#   POST /{prefix}_print_template/<id>/grid   保存（覆盖）模板网格（仅 admin）
#
# 安全：
# - grid POST 走 pydantic 校验（A8），sheet/cell/值类型/占位符白名单全部校验；
# - 回写前对全部占位符做白名单校验，任何非法占位符立即 400 且不落盘（原子性）；
# - PRINT-TEMPLATE-F05-A2 起支持样式（styles）与列宽/行高回写，样式键白名单
#   校验，语义「有值=设置 / 显式 null=清除 / 缺失=保持」；
# - PRINT-TEMPLATE-F05-A3 起支持合并/取消合并（merges/unmerges），坐标用删除
#   前原始行号、删行后自动平移；del_rows 与合并区相交一律 400（防坏文件）。
from __future__ import annotations

import re

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from pydantic import BaseModel, field_validator

from db import db
from utils import require_role


# ==================== pydantic 输入模型（A8） ====================

_GRID_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')
_GRID_BORDER_VALUES = frozenset({
    'thin', 'medium', 'thick', 'dashed', 'double', 'hair', 'dotted',
})


class _CellStyleModel(BaseModel):
    """单元格样式（PRINT-TEMPLATE-F05-A2）。

    语义：字段提供且有值=设置；显式 null=清除；字段缺失=保持不变
    （路由层用 exclude_unset dump 保留该语义）。
    """
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    font_name: str | None = None
    font_size: float | None = None
    font_color: str | None = None
    bg_color: str | None = None
    h_align: str | None = None
    v_align: str | None = None
    wrap: bool | None = None
    border: dict[str, str | None] | None = None

    @field_validator('font_name')
    @classmethod
    def validate_font_name(cls, v):
        if v is not None and (not v.strip() or len(v) > 30):
            raise ValueError('font_name 必须是 1-30 字符的字体名')
        return v

    @field_validator('font_size')
    @classmethod
    def validate_font_size(cls, v):
        if v is not None and not (6 <= v <= 72):
            raise ValueError('font_size 必须在 6-72 之间')
        return v

    @field_validator('font_color', 'bg_color')
    @classmethod
    def validate_color(cls, v):
        if v is not None and not _GRID_COLOR_RE.match(v):
            raise ValueError('颜色必须是 #RRGGBB 格式')
        return v

    @field_validator('h_align')
    @classmethod
    def validate_h_align(cls, v):
        if v is not None and v not in ('left', 'center', 'right'):
            raise ValueError('h_align 只支持 left/center/right')
        return v

    @field_validator('v_align')
    @classmethod
    def validate_v_align(cls, v):
        if v is not None and v not in ('top', 'center', 'bottom'):
            raise ValueError('v_align 只支持 top/center/bottom')
        return v

    @field_validator('border')
    @classmethod
    def validate_border(cls, v):
        if v is None:
            return v
        if not isinstance(v, dict):
            raise ValueError('border 必须是对象')
        unknown = set(v) - {'top', 'right', 'bottom', 'left'}
        if unknown:
            raise ValueError('不支持的边框边：%s' % '、'.join(sorted(unknown)))
        for edge, edge_style in v.items():
            if edge_style is None or edge_style == 'none':
                continue
            if edge_style not in _GRID_BORDER_VALUES:
                raise ValueError('边框样式 %s 不受支持' % edge_style)
        return v


class _MergeModel(BaseModel):
    """合并区域（PRINT-TEMPLATE-F05-A3），坐标为删除前的原始行号。"""
    row: int
    col: int
    rowspan: int
    colspan: int

    @field_validator('row', 'col', 'rowspan', 'colspan')
    @classmethod
    def validate_positive(cls, v):
        if not isinstance(v, int) or v < 1:
            raise ValueError('合并区域坐标必须是正整数')
        return v


class _GridSheetModel(BaseModel):
    """一个工作表内的编辑动作。"""
    name: str
    upserts: list[tuple[int, int, object]] = []
    del_rows: list[int] = []
    styles: list[tuple[int, int, _CellStyleModel]] = []
    col_widths: dict[str, float] = {}
    row_heights: dict[str, float] = {}
    merges: list[_MergeModel] = []
    unmerges: list[tuple[int, int]] = []

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('工作表名称不能为空')
        return v

    @field_validator('upserts', mode='before')
    @classmethod
    def validate_upserts(cls, v):
        value = v or []
        if not isinstance(value, list):
            raise ValueError('upserts 必须是数组')
        for item in value:
            if not (isinstance(item, (list, tuple)) and len(item) == 3):
                raise ValueError('每个单元格必须是 [行, 列, 值]')
            r, c = item[0], item[1]
            if not isinstance(r, int) or not isinstance(c, int):
                raise ValueError('行列坐标必须是整数')
            val = item[2]
            if val is not None and not isinstance(val, (str, int, float, bool)):
                raise ValueError('单元格值只支持字符串或数值')
        return value

    @field_validator('del_rows', mode='before')
    @classmethod
    def validate_del_rows(cls, v):
        value = v or []
        if not isinstance(value, list):
            raise ValueError('del_rows 必须是数组')
        if any(not isinstance(x, int) or x < 1 for x in value):
            raise ValueError('待删除行号必须是正整数')
        return value

    @field_validator('col_widths', 'row_heights', mode='before')
    @classmethod
    def validate_dimensions(cls, v):
        value = v or {}
        if not isinstance(value, dict):
            raise ValueError('尺寸必须是 {序号: 数值} 对象')
        for k, dim in value.items():
            if not str(k).isdigit() or int(k) < 1:
                raise ValueError('尺寸序号必须是正整数')
            if isinstance(dim, bool) or not isinstance(dim, (int, float)) \
                    or dim <= 0:
                raise ValueError('尺寸数值必须是正数')
        return value

    def to_engine_payload(self) -> dict:
        """转换为引擎入参；styles 按 exclude_unset 保留「缺失=保持」语义。"""
        return {
            'name': self.name,
            'upserts': [list(u) for u in self.upserts],
            'del_rows': list(self.del_rows),
            'styles': [[r, c, s.model_dump(exclude_unset=True)]
                       for (r, c, s) in self.styles],
            'col_widths': dict(self.col_widths),
            'row_heights': dict(self.row_heights),
            'merges': [m.model_dump() for m in self.merges],
            'unmerges': [list(u) for u in self.unmerges],
        }


class PrintTemplateGridRequest(BaseModel):
    """保存模板网格请求体。"""
    sheets: list[_GridSheetModel] = []


# ==================== 内核实现 ====================

_META = {
    'in_order': {'label': '入库单'},
    'out_order': {'label': '领料单/出库单'},
    'global': {'label': '通用 Excel 模板'},
}


def _model_for(prefix):
    """按前缀延迟解析模板模型（请求期才 import app，避免模块加载期循环导入）。"""
    from app import ExcelPrintTemplate, InOrderPrintTemplate, OutOrderPrintTemplate
    return {
        'in_order': InOrderPrintTemplate,
        'out_order': OutOrderPrintTemplate,
        'global': ExcelPrintTemplate,
    }.get(prefix)


def _grid_page(prefix, template_id):
    model = _model_for(prefix)
    template = db.session.get(model, template_id)
    if template is None:
        return jsonify({'status': 'error', 'msg': '模板不存在'}), 404
    return render_template(
        'print_template_editor.html',
        template_id=template.id,
        template_name=template.name,
        is_default=bool(template.is_default),
        prefix=prefix,
        template_label=_META.get(prefix, {}).get('label', ''),
    )


def _grid_read(prefix, template_id):
    import os
    from app import api_error
    from print_fill import serialize_print_template_grid, template_file_abspath

    model = _model_for(prefix)
    template = db.session.get(model, template_id)
    if template is None:
        return api_error('模板不存在', 404)
    if not template.excel_template_path:
        return api_error('打印模板缺少 Excel 文件', 404)
    template_path = template_file_abspath(template.excel_template_path,
                                          _static_folder())
    if not template_path or not os.path.exists(template_path):
        return api_error('打印模板文件不存在', 404)
    try:
        grid = serialize_print_template_grid(template_path)
    except Exception as e:  # noqa: BLE001 开放异常：坏文件一律 400
        return api_error(f'模板解析失败：{e}', 400)
    return jsonify({
        'status': 'success',
        'template': {
            'id': template.id,
            'name': template.name,
            'is_default': bool(template.is_default),
            'prefix': prefix,
        },
        'sheets': grid['sheets'],
    })


def _static_folder():
    try:
        from flask import current_app
        return current_app.static_folder
    except Exception:  # noqa: BLE001
        return None


def _preview_data(prefix, template_id):
    """打印预览示例数据（PRINT-TEMPLATE-F05-A5，GET 无需 pydantic）。"""
    from app import api_error
    from print_preview import build_preview_context

    model = _model_for(prefix)
    template = db.session.get(model, template_id)
    if template is None:
        return api_error('模板不存在', 404)
    if prefix in ('in_order', 'out_order'):
        target_type, target_code = prefix, ''
    else:
        target_type = getattr(template, 'target_type', '') or ''
        target_code = getattr(template, 'target_code', '') or ''
    try:
        context = build_preview_context(target_type, target_code)
    except Exception as e:  # noqa: BLE001 预览数据失败不给 500 详情
        return api_error(f'预览数据生成失败：{e}', 400)
    return jsonify({
        'status': 'success',
        'context': context,
        'target_type': target_type,
        'target_code': target_code,
    })


def _grid_write(prefix, template_id):
    import os
    import tempfile
    from app import api_error
    from print_fill import apply_print_template_grid, template_file_abspath

    try:
        req = PrintTemplateGridRequest.model_validate(
            request.get_json(silent=True) or {})
    except Exception as e:  # noqa: BLE001 pydantic 统一归为 400
        return api_error(f'参数错误：{e}', 400)

    model = _model_for(prefix)
    template = db.session.get(model, template_id)
    if template is None:
        return api_error('模板不存在', 404)
    if not template.excel_template_path:
        return api_error('打印模板缺少 Excel 文件', 404)
    template_path = template_file_abspath(template.excel_template_path,
                                          _static_folder())
    if not template_path or not os.path.exists(template_path):
        return api_error('打印模板文件不存在', 404)

    sheets_data = [s.to_engine_payload() for s in req.sheets]
    if not sheets_data:
        return api_error('没有需要保存的内容', 400)

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix='.tmpl_', suffix='.xlsx',
            dir=os.path.dirname(template_path),
        )
        os.close(fd)
        with open(tmp_path, 'wb') as f:
            f.write(apply_print_template_grid(template_path, sheets_data).read())
        os.replace(tmp_path, template_path)
        tmp_path = None
    except ValueError as e:
        return api_error(str(e), 400)
    except Exception as e:  # noqa: BLE001 写盘失败统一 500
        from app import app as _app
        _app.logger.error(f'打印模板在线保存失败: {e}')
        return api_error('保存失败，请稍后重试', 500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    template.updated_at = db.func.now()
    db.session.commit()
    return jsonify({'status': 'success', 'msg': '模板已更新'})


def register_print_template_editor_routes(app):
    """注册所有打印模板的在线编辑路由（入库/出库）。

    覆盖入库与出库打印模板；其他单据的打印模板接入时在此追加前缀即可。
    """
    for prefix in ('in_order', 'out_order', 'global'):
        _install(app, prefix)


def _install(app, prefix):
    page_ep = f'{prefix}_print_template_editor_page'
    read_ep = f'{prefix}_print_template_grid_read'
    write_ep = f'{prefix}_print_template_grid_write'
    preview_ep = f'{prefix}_print_template_preview_data'

    @app.route(f'/{prefix}_print_template/<int:template_id>/edit', endpoint=page_ep)
    @login_required
    def _edit_page(template_id, _prefix=prefix):
        return _grid_page(_prefix, template_id)

    @app.route(f'/{prefix}_print_template/<int:template_id>/grid', endpoint=read_ep)
    @login_required
    def _read_grid(template_id, _prefix=prefix):
        return _grid_read(_prefix, template_id)

    @app.route(f'/{prefix}_print_template/<int:template_id>/grid', methods=['POST'],
               endpoint=write_ep)
    @login_required
    @require_role('admin')
    def _write_grid(template_id, _prefix=prefix):
        return _grid_write(_prefix, template_id)

    @app.route(f'/{prefix}_print_template/<int:template_id>/preview_data',
               endpoint=preview_ep)
    @login_required
    def _preview(template_id, _prefix=prefix):
        return _preview_data(_prefix, template_id)