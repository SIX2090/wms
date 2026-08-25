"""统一 Excel 打印模板中心（PRINT-TEMPLATE-F01/F03/F04）。

所有单据、列表、报表、标签的 Excel 打印模板统一在此管理与在线设计
（参考简道云打印模板）：
- 列表/筛选/上传/下载/设默认/删除（F01/F03）；
- 每张模板「在线编辑」跳转 /global_print_template/<id>/edit 网格编辑器（F02）；
- 「在线新建」免上传：按注册表/报表列定义复制内置模板生成新模板并直达
  在线编辑器（F04 A5）；
- 业务编码按模板分类联动（单据 10 种 / 列表 / 报表 report_* / 标签）。
"""
from __future__ import annotations

import os
import re
import shutil
from datetime import datetime

from flask import jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required
from pydantic import BaseModel, field_validator

from db import db
from utils import require_role

TARGET_TYPES = {
    'document': '单据打印',
    'list': '列表打印',
    'report': '报表打印',
    'label': '标签打印',
}

_TARGET_CODE_RE = re.compile(r'^[a-z0-9_]{1,80}$')


def _model():
    from app import ExcelPrintTemplate
    return ExcelPrintTemplate


def _code_options():
    """各分类可选业务编码（上传/在线新建表单联动）。"""
    from doc_print_excel import (DOC_EXCEL_PRINT_TYPES,
                                 LABEL_EXCEL_PRINT_TYPES,
                                 TABLE_EXCEL_PRINT_TYPES)
    options = {key: [] for key in TARGET_TYPES}
    for code, spec in DOC_EXCEL_PRINT_TYPES.items():
        options['document'].append({'code': code, 'label': spec['label']})
    for code, spec in TABLE_EXCEL_PRINT_TYPES.items():
        options[spec['target_type']].append(
            {'code': code, 'label': spec['label']})
    for code, spec in LABEL_EXCEL_PRINT_TYPES.items():
        options['label'].append({'code': code, 'label': spec['label']})
    try:
        from app import REPORT_DEFINITIONS
        for rtype, definition in REPORT_DEFINITIONS.items():
            options['report'].append({
                'code': f'report_{rtype}', 'label': definition['title']})
    except Exception:  # noqa: BLE001 报表定义不可达时仅缺联动选项
        pass
    return options


def _is_registered_code(target_type, target_code):
    """校验业务编码在该分类下已注册（内置模板可生成）。"""
    from doc_print_excel import (DOC_EXCEL_PRINT_TYPES,
                                 LABEL_EXCEL_PRINT_TYPES,
                                 TABLE_EXCEL_PRINT_TYPES)
    if target_type == 'document':
        return target_code in DOC_EXCEL_PRINT_TYPES
    if target_type == 'label':
        return target_code in LABEL_EXCEL_PRINT_TYPES
    if target_type == 'list':
        return target_code in TABLE_EXCEL_PRINT_TYPES and \
            TABLE_EXCEL_PRINT_TYPES[target_code]['target_type'] == 'list'
    if target_type == 'report':
        if target_code in TABLE_EXCEL_PRINT_TYPES:
            return TABLE_EXCEL_PRINT_TYPES[target_code]['target_type'] == 'report'
        return target_code.startswith('report_')
    return False


class CreateBlankTemplateRequest(BaseModel):
    """在线新建模板请求（A8 pydantic 校验）。"""
    name: str
    target_type: str
    target_code: str

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = (v or '').strip()
        if not v or len(v) > 100:
            raise ValueError('模板名称必填且不超过 100 字')
        return v

    @field_validator('target_type')
    @classmethod
    def validate_target_type(cls, v: str) -> str:
        v = (v or '').strip()
        if v not in TARGET_TYPES:
            raise ValueError('模板分类不合法')
        return v

    @field_validator('target_code')
    @classmethod
    def validate_target_code(cls, v: str) -> str:
        v = (v or '').strip()
        if not _TARGET_CODE_RE.match(v):
            raise ValueError('业务编码只能包含小写字母、数字和下划线')
        return v


def _report_columns_for_blank(report_type):
    """取报表列定义用于生成内置模板；失败返回 None。"""
    try:
        from app import (REPORT_DEFINITIONS, Warehouse, _build_report_payload,
                         get_default_warehouse)
        if report_type not in REPORT_DEFINITIONS:
            return None
        warehouse = get_default_warehouse() or Warehouse.query.filter_by(
            status='active').first()
        filters = {
            'start_date': None, 'end_date': None,
            'warehouse_id': warehouse.id if warehouse else 0,
            'warehouse': warehouse.name if warehouse else '',
            'warehouse_code': '', 'business_type': '', 'material_code': '',
            'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
            'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 1,
            'hide_zero': False, 'export': '',
        }
        payload = _build_report_payload(report_type, filters)
        return payload['title'], payload['columns']
    except Exception:  # noqa: BLE001 列定义不可达时由调用方给指引
        return None


def _blank_source_path(target_type, target_code, static_folder):
    """在线新建的源模板绝对路径；无法生成返回 None。"""
    from doc_print_excel import (DOC_EXCEL_PRINT_TYPES,
                                 LABEL_EXCEL_PRINT_TYPES,
                                 TABLE_EXCEL_PRINT_TYPES,
                                 _builtin_template_abspath,
                                 generate_report_builtin_template)
    if target_code in DOC_EXCEL_PRINT_TYPES \
            or target_code in TABLE_EXCEL_PRINT_TYPES \
            or target_code in LABEL_EXCEL_PRINT_TYPES:
        return _builtin_template_abspath(static_folder, target_code)
    if target_type == 'report' and target_code.startswith('report_'):
        report_type = target_code[len('report_'):]
        candidate = os.path.join(static_folder, 'uploads', 'print_templates',
                                 f'builtin_report_{report_type}_default.xlsx')
        if os.path.exists(candidate):
            return candidate
        meta = _report_columns_for_blank(report_type)
        if not meta:
            return None
        title, columns = meta
        content = generate_report_builtin_template(title, columns)
        if content is None:
            return None
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
        with open(candidate, 'wb') as f:
            f.write(content.read())
        return candidate
    return None


def register_print_template_center_routes(app):
    @app.route('/print_templates')
    @login_required
    def print_templates():
        model = _model()
        target_type = (request.args.get('target_type') or '').strip()
        query = model.query
        if target_type in TARGET_TYPES:
            query = query.filter_by(target_type=target_type)
        templates = query.order_by(model.target_type, model.target_code, model.is_default.desc(), model.updated_at.desc()).all()
        return render_template(
            'print_template_center.html', templates=templates,
            target_types=TARGET_TYPES, selected_type=target_type,
            code_options=_code_options())

    @app.route('/print_templates/create_blank', methods=['POST'])
    @login_required
    @require_role('admin')
    def create_blank_print_template():
        """在线新建：复制内置模板生成新模板并直达在线编辑器（免本地上传）。"""
        from pydantic import ValidationError
        try:
            req = CreateBlankTemplateRequest.model_validate(
                request.form.to_dict())
        except ValidationError as e:
            return jsonify({'status': 'error', 'msg': f'参数错误：{e}'}), 400
        if not _is_registered_code(req.target_type, req.target_code):
            return jsonify({
                'status': 'error',
                'msg': '该分类下未注册此业务编码，请从下拉建议中选择'}), 400
        source = _blank_source_path(req.target_type, req.target_code,
                                    app.static_folder)
        if not source or not os.path.exists(source):
            return jsonify({
                'status': 'error',
                'msg': '内置模板暂不可用：请先在对应打印/报表页执行一次模板打印，'
                       '或改用上传 .xlsx 方式新建'}), 400
        rel_dir = os.path.join('uploads', 'print_templates')
        os.makedirs(os.path.join(app.static_folder, rel_dir), exist_ok=True)
        filename = 'custom_%s_%s.xlsx' % (
            req.target_code, datetime.now().strftime('%Y%m%d%H%M%S%f'))
        dest = os.path.join(app.static_folder, rel_dir, filename)
        shutil.copyfile(source, dest)
        model = _model()
        template = model(
            name=req.name, target_type=req.target_type,
            target_code=req.target_code, template_type='excel',
            excel_template_path=f'/static/uploads/print_templates/{filename}',
            is_default=False)
        db.session.add(template)
        db.session.commit()
        return redirect(f'/global_print_template/{template.id}/edit')

    @app.route('/print_templates/upload', methods=['POST'])
    @login_required
    @require_role('admin')
    def upload_print_template():
        model = _model()
        name = (request.form.get('name') or '').strip()
        target_type = (request.form.get('target_type') or '').strip()
        target_code = (request.form.get('target_code') or '').strip()
        upload = request.files.get('excel_file')
        if not name or target_type not in TARGET_TYPES or not target_code:
            return jsonify({'status': 'error', 'msg': '请完整填写模板名称、模板分类和业务编码'}), 400
        if not upload or not upload.filename or os.path.splitext(upload.filename)[1].lower() != '.xlsx':
            return jsonify({'status': 'error', 'msg': '仅支持 .xlsx 格式'}), 400
        from print_fill import validate_template_file
        raw = upload.read()
        error = validate_template_file(raw)
        if error:
            return jsonify({'status': 'error', 'msg': error}), 400
        upload.stream.seek(0)
        from app import save_print_template_file
        path = save_print_template_file(upload, 'global', app.static_folder)
        is_default = request.form.get('is_default') == '1'
        if is_default:
            model.query.filter_by(target_type=target_type, target_code=target_code, is_default=True).update({'is_default': False})
        template = model(name=name, target_type=target_type, target_code=target_code, template_type='excel', excel_template_path=path, is_default=is_default)
        db.session.add(template)
        db.session.commit()
        return redirect(url_for('print_templates'))

    @app.route('/print_templates/<int:template_id>/set_default', methods=['POST'])
    @login_required
    @require_role('admin')
    def set_print_template_default(template_id):
        model = _model()
        template = db.session.get(model, template_id)
        if template is None:
            return jsonify({'status': 'error', 'msg': '模板不存在'}), 404
        model.query.filter_by(target_type=template.target_type, target_code=template.target_code, is_default=True).update({'is_default': False})
        template.is_default = True
        db.session.commit()
        return jsonify({'status': 'success'})

    @app.route('/print_templates/<int:template_id>/download')
    @login_required
    def download_print_template(template_id):
        model = _model()
        template = db.session.get(model, template_id)
        if template is None:
            return jsonify({'status': 'error', 'msg': '模板不存在'}), 404
        from print_fill import template_file_abspath
        path = template_file_abspath(template.excel_template_path, app.static_folder)
        if not path or not os.path.exists(path):
            return jsonify({'status': 'error', 'msg': '模板文件不存在'}), 404
        return send_file(path, as_attachment=True, download_name=f'{template.name}.xlsx')

    @app.route('/print_templates/<int:template_id>/delete', methods=['POST'])
    @login_required
    @require_role('admin')
    def delete_print_template_center(template_id):
        model = _model()
        template = db.session.get(model, template_id)
        if template is None:
            return jsonify({'status': 'error', 'msg': '模板不存在'}), 404
        db.session.delete(template)
        db.session.commit()
        return jsonify({'status': 'success'})
