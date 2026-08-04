#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 供应商（supplier）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_<domain>_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 supplier_list），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（Supplier 模型、_get_master_list_filters 等）在各路由函数内
#   延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志统一使用 current_app.logger 替代 app.logger。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 supplier_* 各路由测试覆盖
def register_supplier_routes(app):
    @app.route('/supplier')
    @login_required
    def supplier_list():
        from app import (
            Supplier,
            _apply_master_order,
            _apply_simple_search,
            _get_master_list_filters,
        )
        search, status_filter, sort_by, sort_order = _get_master_list_filters('code')
        allowed_sorts = {'id', 'code', 'name', 'contact', 'phone', 'created_at'}
        query = _apply_simple_search(Supplier.query, Supplier, search, ['code', 'name', 'contact', 'phone', 'address'])
        query, sort_by = _apply_master_order(query, Supplier, sort_by, sort_order, allowed_sorts, 'code')
        suppliers = query.all()
        return render_template('supplier.html', suppliers=suppliers, filters={'search': search, 'status': status_filter}, sort_by=sort_by, sort_order=sort_order)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/supplier/add', methods=['GET', 'POST'])
    @require_role('warehouse')
    @login_required
    def add_supplier():
        from app import Supplier, api_error, sanitize_text_input
        # BUG-2026-07-28-010 修复：直接 GET /supplier/add 不再 405；
        # 重定向到列表页并携带 showAddModal=1，由 supplier.html JS 自动弹出新增 modal
        if request.method == 'GET':
            return redirect(url_for('supplier_list') + '?showAddModal=1')
        # BUG-2026-07-29-002/009: 供应商主数据字段走 sanitize_text_input
        code = sanitize_text_input(request.form.get('code'), max_len=50)
        name = sanitize_text_input(request.form.get('name'), max_len=100)
        if not code:
            return api_error('请输入供应商编号')
        if not name:
            return api_error('请输入供应商名称')
        # BUG-F02-02 修复：供应商主数据长度截断防护
        # DB 列宽：code=50/name=100/contact=50/phone=20/address=200
        if len(code) > 50:
            return api_error(f'供应商编号不能超过 50 个字符（当前 {len(code)}）')
        if len(name) > 100:
            return api_error(f'供应商名称不能超过 100 个字符（当前 {len(name)}）')
        contact = sanitize_text_input(request.form.get('contact'), max_len=50)
        if len(contact) > 50:
            return api_error(f'联系人不能超过 50 个字符（当前 {len(contact)}）')
        phone = sanitize_text_input(request.form.get('phone'), max_len=20)
        if len(phone) > 20:
            return api_error(f'电话不能超过 20 个字符（当前 {len(phone)}）')
        address = sanitize_text_input(request.form.get('address'), max_len=200)
        if len(address) > 200:
            return api_error(f'地址不能超过 200 个字符（当前 {len(address)}）')
        if Supplier.query.filter_by(code=code).first():
            return api_error('供应商编号已存在')
        if Supplier.query.filter_by(name=name).first():
            return api_error('供应商名称已存在')
        supplier = Supplier(
            code=code,
            name=name,
            contact=contact or None,
            phone=phone or None,
            address=address or None
        )
        db.session.add(supplier)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"数据库操作失败: {e}")
            return api_error("操作失败", code=500)
        return jsonify({'status': 'success', 'id': supplier.id, 'name': supplier.name})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/supplier/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_supplier():
        from app import Supplier, api_error
        ids = request.json.get('ids', [])
        for id in ids:
            sup = db.session.get(Supplier, id)
            if sup:
                # In stock
                if sup.in_orders:
                    return api_error(f'供应商“{sup.name}”已有关联入库单，不能删除')

                # Related materials
                if sup.materials:
                    return api_error(f'供应商“{sup.name}”已关联物料，不能删除')

                # 采购订单引用（原删除逻辑只检查入库单和物料，未覆盖采购单与委外单，
                # 删除后会因外键悬空导致采购/委外页面 500）
                if sup.purchase_orders:
                    return api_error(f'供应商“{sup.name}”已有关联采购订单，不能删除')

                # 委外相关单据引用
                if sup.subcontract_orders:
                    return api_error(f'供应商“{sup.name}”已有关联委外加工单，不能删除')
                if sup.subcontract_issues:
                    return api_error(f'供应商“{sup.name}”已有关联委外发料单，不能删除')
                if sup.subcontract_receives:
                    return api_error(f'供应商“{sup.name}”已有关联委外收货单，不能删除')

                db.session.delete(sup)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    @app.route('/supplier/<int:supplier_id>')
    @require_role('warehouse')
    @login_required
    def get_supplier(supplier_id):
        """M-01：行级编辑 - 返回供应商详情 JSON。"""
        from app import Supplier
        sup = db.session.get(Supplier, supplier_id)
        if not sup:
            return jsonify({'status': 'error', 'msg': '供应商不存在'}), 404
        return jsonify({
            'status': 'success',
            'supplier': {
                'id': sup.id, 'code': sup.code, 'name': sup.name,
                'contact': sup.contact or '', 'phone': sup.phone or '',
                'address': sup.address or ''
            }
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/supplier/<int:supplier_id>/edit', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def edit_supplier(supplier_id):
        """M-01：供应商行级编辑。"""
        from app import Supplier, api_error
        sup = db.session.get(Supplier, supplier_id)
        if not sup:
            return jsonify({'status': 'error', 'msg': '供应商不存在'}), 404
        code = (request.form.get('code') or '').strip()
        name = (request.form.get('name') or '').strip()
        if not code:
            return api_error('请输入供应商编号')
        if not name:
            return api_error('请输入供应商名称')
        # BUG-F02-02 修复：供应商编辑入口同样 5 字段长度校验
        if len(code) > 50:
            return jsonify({'status': 'error', 'msg': f'供应商编号不能超过 50 个字符（当前 {len(code)}）'}), 400
        if len(name) > 100:
            return jsonify({'status': 'error', 'msg': f'供应商名称不能超过 100 个字符（当前 {len(name)}）'}), 400
        contact = (request.form.get('contact') or '').strip()
        if len(contact) > 50:
            return jsonify({'status': 'error', 'msg': f'联系人不能超过 50 个字符（当前 {len(contact)}）'}), 400
        phone = (request.form.get('phone') or '').strip()
        if len(phone) > 20:
            return jsonify({'status': 'error', 'msg': f'电话不能超过 20 个字符（当前 {len(phone)}）'}), 400
        address = (request.form.get('address') or '').strip()
        if len(address) > 200:
            return jsonify({'status': 'error', 'msg': f'地址不能超过 200 个字符（当前 {len(address)}）'}), 400
        dup = Supplier.query.filter_by(code=code).first()
        if dup and dup.id != supplier_id:
            return api_error('供应商编号已存在')
        dup = Supplier.query.filter_by(name=name).first()
        if dup and dup.id != supplier_id:
            return api_error('供应商名称已存在')
        sup.code = code
        sup.name = name
        sup.contact = contact or None
        sup.phone = phone or None
        sup.address = address or None
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'编辑供应商失败: {e}')
            return jsonify({'status': 'error', 'msg': '编辑失败'}), 500
        return jsonify({'status': 'success', 'msg': '供应商编辑成功'})