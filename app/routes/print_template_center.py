"""统一 Excel 打印模板中心。"""
from __future__ import annotations

import os

from flask import jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from db import db
from utils import require_role

TARGET_TYPES = {
    'document': '单据打印',
    'list': '列表打印',
    'report': '报表打印',
}


def _model():
    from app import ExcelPrintTemplate
    return ExcelPrintTemplate


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
        return render_template('print_template_center.html', templates=templates, target_types=TARGET_TYPES, selected_type=target_type)

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