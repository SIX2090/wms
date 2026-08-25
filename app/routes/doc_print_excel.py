#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 全模块单据 Excel 模板打印路由（PRINT-TEMPLATE-F03 A2）。
#
# 需求（2026-08-25）：所有单据的打印模块都要支持在线 Excel 格式编辑
# （参考简道云 Excel 打印模板）。A1 已为 10 种单据在 excel_print_template
# 表同步内置默认模板（模板中心 / global_print_template/<id>/edit 可在线
# 编辑）；本模块把打印出口接到模板体系：
#
#   GET /{prefix}/<id>/print_excel            按所选（或默认）模板填充下载 .xlsx
#   GET /doc_print_templates/<target_code>.json  该单据可选模板列表（打印页选择器）
#
# 覆盖：check / transfer / requisition / purchase_order / sales_order(/sales 前缀)
# / adjustment / subcontract / subcontract_issue / subcontract_receive / after_sale_out。
# 入库单/领料单已有各自域内的 print_excel 实现，不在此重复注册。
#
# - 模块级只导入稳定依赖（flask / flask_login / doc_print_excel），模型在
#   请求期从 app 模块延迟取（避免 app.py 加载期循环导入）。
# - 模板解析/填充失败时 render_doc_excel_print 回退内置模板；正常必有结果。
from __future__ import annotations

from flask import abort, jsonify, request, send_file
from flask_login import login_required

from doc_print_excel import (
    DOC_EXCEL_PRINT_TYPES,
    TABLE_EXCEL_PRINT_TYPES,
    render_doc_excel_print,
)

# target_code → (URL 前缀, app 模块中的模型名)
_DOC_ROUTE_MODELS = {
    'check': ('check', 'InventoryCheck'),
    'transfer': ('transfer', 'TransferOrder'),
    'requisition': ('requisition', 'ProductionRequisition'),
    'purchase_order': ('purchase_order', 'PurchaseOrder'),
    'sales_order': ('sales', 'SalesOrder'),
    'adjustment': ('adjustment', 'AdjustmentOrder'),
    'subcontract': ('subcontract', 'SubcontractOrder'),
    'subcontract_issue': ('subcontract_issue', 'SubcontractIssue'),
    'subcontract_receive': ('subcontract_receive', 'SubcontractReceive'),
    'after_sale_out': ('after_sale_out', 'AfterSaleOutOrder'),
}

_XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _make_doc_print_excel_view(flask_app, target_code, model_name):
    """生成单据 Excel 模板打印视图（闭包绑定 target_code/模型名）。"""
    def _view(id):
        import app as app_module
        model = getattr(app_module, model_name)
        order = model.query.get_or_404(id)
        result = render_doc_excel_print(
            target_code, order,
            template_id=request.args.get('template_id', type=int),
            static_folder=flask_app.static_folder,
        )
        if result is None:
            abort(404)
        output, filename = result
        return send_file(output, download_name=filename,
                         as_attachment=True, mimetype=_XLSX_MIMETYPE)
    return _view


def register_doc_print_excel_routes(app):
    """注册全模块单据 Excel 模板打印路由（endpoint 统一 doc_print_excel_*）。"""
    for target_code, (prefix, model_name) in _DOC_ROUTE_MODELS.items():
        view = login_required(_make_doc_print_excel_view(
            app, target_code, model_name))
        app.add_url_rule(
            f'/{prefix}/<int:id>/print_excel',
            endpoint=f'doc_print_excel_{target_code}',
            view_func=view,
            methods=['GET'],
        )

    @app.route('/doc_print_templates/<target_code>.json',
               endpoint='doc_print_templates_json')
    @login_required
    def doc_print_templates_json(target_code):
        """返回某单据/列表/报表可选的 Excel 打印模板列表（打印页选择器用）。"""
        if target_code in DOC_EXCEL_PRINT_TYPES:
            target_type = 'document'
        elif target_code in TABLE_EXCEL_PRINT_TYPES:
            target_type = TABLE_EXCEL_PRINT_TYPES[target_code]['target_type']
        else:
            abort(404)
        from app import ExcelPrintTemplate
        from print_fill import template_file_abspath
        import os
        rows = ExcelPrintTemplate.query.filter_by(
            target_type=target_type, target_code=target_code,
        ).order_by(ExcelPrintTemplate.is_default.desc(),
                   ExcelPrintTemplate.updated_at.desc()).all()
        return jsonify({
            'status': 'success',
            'target_type': target_type,
            'target_code': target_code,
            'templates': [{
                'id': t.id,
                'name': t.name,
                'is_default': bool(t.is_default),
                'has_file': bool(
                    t.excel_template_path
                    and os.path.exists(template_file_abspath(
                        t.excel_template_path, app.static_folder) or '')),
                # 模板中心在线编辑入口（global 前缀适配全部 ExcelPrintTemplate）
                'edit_url': f'/global_print_template/{t.id}/edit',
            } for t in rows],
        })
