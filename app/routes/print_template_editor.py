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
# - 仅支持编辑单元格值与删除整行，合并单元格与样式由引擎保留，不在此增删。
from __future__ import annotations

from flask import jsonify, render_template, request
from flask_login import current_user, login_required
from pydantic import BaseModel, field_validator

from db import db
from utils import require_role


# ==================== pydantic 输入模型（A8） ====================

class _GridSheetModel(BaseModel):
    """一个工作表内的编辑动作。"""
    name: str
    upserts: list[tuple[int, int, object]] = []
    del_rows: list[int] = []

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


class PrintTemplateGridRequest(BaseModel):
    """保存模板网格请求体。"""
    sheets: list[_GridSheetModel] = []


# ==================== 内核实现 ====================

_META = {
    'in_order': {'label': '入库单'},
    'out_order': {'label': '领料单/出库单'},
}


def _model_for(prefix):
    """按前缀延迟解析模板模型（请求期才 import app，避免模块加载期循环导入）。"""
    from app import InOrderPrintTemplate, OutOrderPrintTemplate
    return {
        'in_order': InOrderPrintTemplate,
        'out_order': OutOrderPrintTemplate,
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

    sheets_data = [s.model_dump() for s in req.sheets]
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
    for prefix in ('in_order', 'out_order'):
        _install(app, prefix)


def _install(app, prefix):
    page_ep = f'{prefix}_print_template_editor_page'
    read_ep = f'{prefix}_print_template_grid_read'
    write_ep = f'{prefix}_print_template_grid_write'

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