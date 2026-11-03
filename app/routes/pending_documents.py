#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 待办单据（pending_documents）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_<domain>_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 pending_documents），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login），不导入 app，避免循环导入。
# - app.py 内部定义（PENDING_DOCUMENT_MODULES、_build_pending_document_rows、
#   PurchaseRequest、SubcontractOrder 等）在路由函数内延迟导入（请求期才执行），
#   避免 app.py 模块加载期触发循环导入。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import render_template, request
from flask_login import login_required


# no-test:reason=路由注册辅助函数，能力由该路由测试覆盖
def register_pending_documents_routes(app):
    # AI_TASK: AI-R10
    # Sub-repair AI-R10-F02: read-only recovery of the workbench's missing queue link.
    @app.route('/ai/drafts')
    @login_required
    def ai_processing_drafts():
        from app import AIDraftIdempotency
        from flask_login import current_user
        from flask import abort
        if current_user.role not in ('admin', 'warehouse'):
            abort(403)
        page = max(1, request.args.get('page', 1, type=int))
        pagination = AIDraftIdempotency.query.filter_by(status='processing').order_by(
            AIDraftIdempotency.created_at.desc(), AIDraftIdempotency.id.desc()
        ).paginate(page=page, per_page=30, error_out=False)
        return render_template('ai_processing_drafts.html', pagination=pagination)

    @app.route('/pending_documents')
    @login_required
    def pending_documents():
        from app import (
            PENDING_DOCUMENT_MODULES,
            _build_pending_document_rows,
            PurchaseRequest,
            SubcontractOrder,
        )
        module_filter = (request.args.get('module') or '').strip()
        status_filter = (request.args.get('status') or '').strip()
        search = (request.args.get('search') or '').strip()
        allowed_modules = {item['key'] for item in PENDING_DOCUMENT_MODULES}
        if module_filter not in allowed_modules:
            module_filter = ''
        allowed_statuses = {'pending', 'approved', 'processing'}
        if status_filter not in allowed_statuses:
            status_filter = ''

        rows = _build_pending_document_rows(module_filter, status_filter, search)
        module_counts = []
        total_count = 0
        for config in PENDING_DOCUMENT_MODULES:
            count = config['model'].query.filter(config['model'].status.in_(config['status'])).count()
            module_counts.append({
                'key': config['key'],
                'label': config['label'],
                'icon': config.get('icon') or 'bi-file-earmark-text',
                'count': count,
            })
            total_count += count

        status_counts = {
            'pending': sum(config['model'].query.filter_by(status='pending').count() for config in PENDING_DOCUMENT_MODULES if 'pending' in config['status']),
            'approved': PurchaseRequest.query.filter_by(status='approved').count(),
            'processing': SubcontractOrder.query.filter_by(status='processing').count(),
        }
        return render_template(
            'pending_documents.html',
            rows=rows,
            module_counts=module_counts,
            total_count=total_count,
            status_counts=status_counts,
            filters={'module': module_filter, 'status': status_filter, 'search': search},
        )
