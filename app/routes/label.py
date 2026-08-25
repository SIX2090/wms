#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 标签打印（label）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_label_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 print_batch_labels），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login），不导入 app，避免循环导入。
# - app.py 内部定义（模型 Material 等）在各路由函数内延迟导入（请求期才执行），
#   避免 app.py 模块加载期触发循环导入。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import render_template, request
from flask_login import login_required

from utils import print_token_or_login_required


# no-test:reason=路由注册辅助函数，能力由 print_batch_labels 路由测试覆盖
def register_label_routes(app):
    @app.route('/label/batch_print')
    @print_token_or_login_required(job_type='label')  # PRINT-ROUTING-F01-P3 + BUG-2026-08-24-002：ptoken 绑定目标物料集合
    def print_batch_labels():
        from datetime import datetime
        from sqlalchemy.orm import joinedload
        from app import Material
        ids = request.args.get('ids', '').split(',')
        ids = [int(i) for i in ids if i.strip().isdigit()]
        materials = Material.query.options(
            joinedload(Material.unit),
            joinedload(Material.category),
            joinedload(Material.supplier)
        ).filter(Material.id.in_(ids)).all() if ids else []

        materials_data = []
        for m in materials:
            materials_data.append({
                'id': m.id,
                'code': m.code or '',
                'name': m.name or '',
                'spec': m.spec or '',
                'unit_name': m.unit.name if m.unit else '',
                'category_name': m.category.name if m.category else '',
                'stock': str(m.stock) if m.stock else '0',
                'price': str(m.price) if m.price else '',
                'barcode': m.code or '',
                'date': datetime.now().strftime('%Y-%m-%d'),
                'supplier_name': m.supplier.name if m.supplier else ''
            })

        # 关键修复：materials_data 是 Python 列表，直接交给 Jinja2 tojson 序列化，
        # 避免 json.dumps + tojson 双重 JSON 化导致 MATERIALS 变成字符串，
        # 进而 MATERIALS.forEach 抛 TypeError，触发"加载失败/网络错误"。
        return render_template('print_batch_labels.html', materials=materials, materials_data=materials_data)

    @app.route('/label/batch_print_excel')
    @print_token_or_login_required(job_type='label')  # 与 batch_print 同一 ptoken 绑定（BUG-2026-08-24-002）
    def batch_print_labels_excel():
        """按所选（或默认）Excel 标签模板生成标签 .xlsx 下载（PRINT-TEMPLATE-F04 A3）。

        每物料一行，模板含 {img_barcode:item.barcode} 时嵌入 600DPI 条码图。
        无模板时 render_label_excel_print 回退内置物料标签模板，正常必有结果。
        """
        from flask import abort, send_file
        from sqlalchemy.orm import joinedload
        from app import Material
        from doc_print_excel import render_label_excel_print
        ids = request.args.get('ids', '').split(',')
        ids = [int(i) for i in ids if i.strip().isdigit()]
        materials = Material.query.options(
            joinedload(Material.unit),
            joinedload(Material.category),
            joinedload(Material.supplier)
        ).filter(Material.id.in_(ids)).all() if ids else []

        rows = []
        for m in materials:
            rows.append({
                'code': m.code or '',
                'name': m.name or '',
                'spec': m.spec or '',
                'unit_name': m.unit.name if m.unit else '',
                'category_name': m.category.name if m.category else '',
                'supplier_name': m.supplier.name if m.supplier else '',
                'stock': str(m.stock) if m.stock else '0',
                'price': str(m.price) if m.price else '',
                'barcode': m.code or '',
            })
        result = render_label_excel_print(
            'material_label', rows,
            template_id=request.args.get('template_id', type=int),
            static_folder=app.static_folder,
        )
        if result is None:
            abort(404)
        output, filename = result
        return send_file(
            output, download_name=filename, as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')