#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 售后出库（after_sale_out）域路由。
#
# 批量拆分模式：与合同（contract）域一致，采用「register_after_sale_out_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 after_sale_out_list、
# add_after_sale_out_order、complete_after_sale_out_order 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（AfterSaleOutOrder 模型、AfterSaleOutOrderItem、
#   各辅助函数 _get_order_list_filters / _apply_status_date_filters / api_error /
#   _workbook_response / validate_excel_extension / validate_excel_size /
#   _read_import_sheet / _get_excel_cell / _get_excel_number / _order_no_from_row 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_xxx_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 after_sale_out_* 各路由测试覆盖
def register_after_sale_out_routes(app):
    @app.route('/after_sale_out')
    @login_required
    def after_sale_out_list():
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword)
        from sqlalchemy.orm import selectinload, joinedload
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'order_no', 'date', 'customer', 'reason', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = AfterSaleOutOrder.query.options(
            selectinload(AfterSaleOutOrder.items).joinedload(AfterSaleOutOrderItem.material)
        )
        query = _apply_status_date_filters(query, AfterSaleOutOrder, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed'))
            conditions = [
                AfterSaleOutOrder.order_no.like(search_like),
                AfterSaleOutOrder.customer.like(search_like),
                AfterSaleOutOrder.contact.like(search_like),
                AfterSaleOutOrder.phone.like(search_like),
                AfterSaleOutOrder.reason.like(search_like),
                AfterSaleOutOrder.remark.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(AfterSaleOutOrder.status == status_from_search)
            query = query.outerjoin(
                AfterSaleOutOrderItem, AfterSaleOutOrderItem.after_sale_out_order_id == AfterSaleOutOrder.id
            ).outerjoin(Material, AfterSaleOutOrderItem.material_id == Material.id).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(AfterSaleOutOrder, sort_by, AfterSaleOutOrder.created_at)
        query = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template('after_sale_out.html', pagination=pagination, filters=filters, sort_by=sort_by, sort_order=sort_order, per_page=per_page)

    @app.route('/after_sale_out/<int:id>')
    @login_required
    def after_sale_out_detail(id):
        from app import AfterSaleOutOrder, DocumentPushLine, get_recent_operation_logs
        order = AfterSaleOutOrder.query.get_or_404(id)
        push_source = DocumentPushLine.query.filter_by(
            target_document_type='after_sale_out', target_document_id=order.id, status='active'
        ).first()
        return render_template('after_sale_out_detail.html', order=order, push_source=push_source, operation_logs=get_recent_operation_logs('after_sale_out_order', id))

    @app.route('/after_sale_out/<int:id>/print')
    @login_required
    def print_after_sale_out(id):
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, Material,
                         _fmt_date, _material_row_common, _operator_name,
                         _render_generic_document_print)
        from sqlalchemy.orm import selectinload, joinedload
        order = AfterSaleOutOrder.query.options(
            joinedload(AfterSaleOutOrder.operator),
            selectinload(AfterSaleOutOrder.items).joinedload(AfterSaleOutOrderItem.material).joinedload(Material.unit),
        ).get_or_404(id)
        rows = [_material_row_common(item) for item in order.items]
        return _render_generic_document_print({
            'title': '售后出库单',
            'subtitle': 'AFTER-SALE OUTBOUND',
            'number_label': '出库单号',
            'number': order.order_no,
            'date_label': '出库日期',
            'date': _fmt_date(order.date),
            'status': order.status,
            'info': [
                ('客户名称', order.customer or ''),
                ('联系人', order.contact or ''),
                ('联系电话', order.phone or ''),
                ('售后原因', order.reason or ''),
                ('制单人', _operator_name(order)),
                ('总金额', f'{order.total_amount or 0:.2f}'),
            ],
            'remark': order.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '出库数量', 'right'),
                ('price', '单价', 'right money'),
                ('amount', '金额', 'right money'),
                ('remark', '备注', ''),
            ],
            'rows': rows,
            'total_amount': order.total_amount or sum(row.get('amount', 0) or 0 for row in rows),
            'signatures': ['制单', '客户签收', '售后', '仓库'],
        })

    @app.route('/after_sale_out/add')
    @login_required
    def after_sale_out_add_page():
        from datetime import datetime
        from app import (Customer, Material, Unit, generate_order_no,
                         get_active_warehouses, get_default_warehouse,
                         serialize_customer, serialize_material, serialize_unit)
        from sqlalchemy.orm import joinedload
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        customers = Customer.query.order_by(Customer.code.asc(), Customer.id.asc()).all()
        order_no = generate_order_no('ASO')
        order_date = datetime.now().strftime('%Y-%m-%d')
        return render_template(
                              'after_sale_out_add.html',
                              page_title='新增售后出库单',
                              order=None,
                              materials=[serialize_material(material) for material in materials],
                              units=[serialize_unit(unit) for unit in units],
                              customers=[serialize_customer(customer) for customer in customers],
                              warehouses=get_active_warehouses(),
                              default_warehouse=get_default_warehouse(),
                              location_management_enabled=location_management_enabled(),
                              order_id=None, order_no=order_no, order_date=order_date,
                              initial_items=[])

    @app.route('/after_sale_out/<int:id>/edit')
    @login_required
    def after_sale_out_edit_page(id):
        from datetime import date
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, Customer,
                         Material, Unit, get_active_warehouses, get_default_warehouse,
                         serialize_customer, serialize_material, serialize_unit)
        from sqlalchemy.orm import joinedload
        order = AfterSaleOutOrder.query.options(
            joinedload(AfterSaleOutOrder.items).joinedload(AfterSaleOutOrderItem.material).joinedload(Material.unit)
        ).get_or_404(id)
        if order.status != 'pending':
            flash('只有待完成的售后出库单可以编辑。', 'warning')
            return redirect(url_for('after_sale_out_detail', id=id))
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        customers = Customer.query.order_by(Customer.code.asc(), Customer.id.asc()).all()
        initial_items = []
        for item in order.items:
            material = item.material
            initial_items.append({
                'material_code': material.code if material else '',
                'material_name': material.name if material else '',
                'spec': material.spec if material else '',
                'unit_name': material.unit.name if material and material.unit else '',
                'stock': float(material.stock or 0) if material else 0,
                'quantity': float(item.quantity or 0),
                'price': float(item.price or 0),
                'remark': item.remark or '',
            })
        return render_template(
            'after_sale_out_add.html',
            page_title='编辑售后出库单',
            order=order,
            materials=[serialize_material(material) for material in materials],
            units=[serialize_unit(unit) for unit in units],
            customers=[serialize_customer(customer) for customer in customers],
            warehouses=get_active_warehouses(),
            default_warehouse=get_default_warehouse(),
            location_management_enabled=location_management_enabled(),
            order_id=order.id,
            order_no=order.order_no,
            order_date=(order.date if order.date else date.today()).strftime('%Y-%m-%d'),
            initial_items=initial_items)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_after_sale_out_order():
        from datetime import date
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, DocumentPushLine,
                         Material, OutOrder, SalesOrder, _clean_int,
                         assert_warehouse_active, api_error,
                         generate_order_no, get_default_warehouse, location_management_enabled,
                         log_operation,
                         parse_date_value, parse_float_value, round_to_2_decimals)
        from flask_login import current_user
        try:
            payload = request.get_json(silent=True)
            data = payload if isinstance(payload, dict) else request.form
            order_id = data.get('order_id')
            if order_id in ('', 'None', 'null'):
                order_id = None
            elif order_id:
                try:
                    order_id = int(order_id)
                except (TypeError, ValueError):
                    order_id = None

            order_no = (data.get('order_no') or '').strip() or generate_order_no('ASO')
            order_date = parse_date_value(data.get('date'), date.today())
            if not order_date:
                return api_error('日期格式不正确，请重新选择日期')
            customer = (data.get('customer') or '').strip()
            contact = (data.get('contact') or '').strip()
            phone = (data.get('phone') or '').strip()
            reason = (data.get('reason') or '').strip()
            remark = (data.get('remark') or '').strip()
            # BUG-2026-08-02-005 修复：售后出库仓库必填，模型字段已存在但之前闲置。
            warehouse = (data.get('warehouse') or '').strip()
            # P1-BUGFIX: 库位（开启库位管理时必填，AGENTS.md 规则二）
            location = (data.get('location') or '').strip()
            source_sales_order_id = _clean_int(data.get('source_sales_order_id'))
            source_out_order_id = _clean_int(data.get('source_out_order_id'))
            if source_sales_order_id and not db.session.get(SalesOrder, source_sales_order_id):
                return jsonify({'status': 'error', 'msg': '来源销售订单不存在'}), 400
            if source_out_order_id and not db.session.get(OutOrder, source_out_order_id):
                return jsonify({'status': 'error', 'msg': '来源销售出库单不存在'}), 400

            # BUG-2026-08-02-005 修复：仓库必填，未填写时自动带入默认仓库，无默认仓库则拒绝保存。
            if not warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            if not warehouse:
                return jsonify({'status': 'error', 'msg': '请选择仓库'}), 400
            # BUG-2026-08-16-014：仓库必须处于启用状态（与完成路由/其他单据一致）
            wh_ok, wh_msg = assert_warehouse_active(warehouse, allow_empty=False)
            if not wh_ok:
                return jsonify({'status': 'error', 'msg': wh_msg}), 400
            # BUG-2026-08-16-014：库位管理启用时库位必填（AGENTS.md 规则二），
            # 否则草稿无法录入库位，完成路由的库位门禁会卡死工作流。
            if location_management_enabled() and not location:
                return jsonify({'status': 'error', 'msg': '库位管理已启用，请选择库位'}), 400

            if order_id:
                order = db.session.get(AfterSaleOutOrder, order_id)
                if not order:
                    return api_error('售后出库单不存在，请刷新后重试')
                if order.status != 'pending':
                    return api_error('已完成的售后出库单不能修改')
                if DocumentPushLine.query.filter_by(
                    target_document_type='after_sale_out', target_document_id=order.id, status='active'
                ).first():
                    return jsonify({'status': 'error', 'msg': '下推生成的售后出库草稿必须从来源单重新选择明细，不能通过普通编辑接口重建明细。'}), 409
            else:
                order = AfterSaleOutOrder.query.filter_by(order_no=order_no).first()
                if order:
                    if order.status != 'pending':
                        return api_error('售后出库单号已存在，不能重复保存')
                else:
                    order = AfterSaleOutOrder(
                        order_no=order_no,
                        status='pending',
                        operator_id=current_user.id
                    )
            db.session.add(order)
            db.session.flush()

            order.order_no = order_no
            order.date = order_date
            # customer字段已移除，使用department和purpose代替
            order.customer = customer
            order.contact = contact
            order.phone = phone
            order.reason = reason
            order.source_sales_order_id = source_sales_order_id
            order.source_out_order_id = source_out_order_id
            order.warehouse = warehouse
            order.location = location
            order.responsibility = (data.get('responsibility') or '').strip() or None
            order.customer_feedback = (data.get('customer_feedback') or '').strip() or None
            order.remark = remark

            items_data = []
            if isinstance(payload, dict):
                items_data = payload.get('items', []) or []
            elif request.form.get('items'):
                try:
                    items_data = json.loads(request.form.get('items', '[]'))
                except json.JSONDecodeError:
                    items_data = []

            if not items_data:
                return api_error('请至少添加一条售后出库明细')

            for existing_item in list(order.items):
                db.session.delete(existing_item)
            db.session.flush()

            total_amount = 0
            for item_data in items_data:
                material_code = (item_data.get('code') or item_data.get('material_code') or '').strip()
                material = Material.query.filter_by(code=material_code).first()
                if not material:
                    return api_error(f'物料 {material_code} 不存在')
                quantity = parse_float_value(item_data.get('quantity'), 0)
                if quantity <= 0:
                    return api_error(f'物料 {material_code} 的数量必须大于0')
                price = parse_float_value(item_data.get('price'), material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                total_amount = round_to_2_decimals(total_amount + amount)
                item = AfterSaleOutOrderItem(
                    after_sale_out_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    remark=(item_data.get('remark') or '').strip() or None
                )
                db.session.add(item)

            order.total_amount = round_to_2_decimals(total_amount)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('保存失败，请稍后重试')
            log_operation('保存售后出库单', f'售后出库单：{order.order_no}', 'after_sale_out_order', order.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': order.id, 'order_no': order.order_no})
        except Exception as e:
            db.session.rollback()
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/<int:id>/complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def complete_after_sale_out_order(id):
        from app import (AfterSaleOutOrder, _acquire_order_write_lock, allow_negative_stock,
                         api_error, deduct_stock_atomic, get_default_warehouse,
                         is_stock_sufficient, location_management_enabled, log_operation,
                         normalize_stock_quantity, update_location_inventory)
        from app import Material
        from sqlalchemy.orm import selectinload
        try:
            order = AfterSaleOutOrder.query.get_or_404(id)
            if order.status != 'pending':
                return api_error('该售后出库单已提交，不能重复操作')
            if not order.items:
                return api_error('请至少添加一条售后出库明细')

            locked, ok = _acquire_order_write_lock(
                AfterSaleOutOrder, id, 'pending', selectinload(AfterSaleOutOrder.items)
            )
            if not ok:
                return jsonify({'status': 'error', 'msg': '该售后出库单状态已变化，不能重复完成'}), 409
            order = locked

            # BUG-2026-08-02-006 修复：售后出库完成时仓库必填校验，与出库单一致。
            # 存量未填仓库的 pending 单据完成时先自动带入默认仓库，无默认仓库才拒绝。
            if not order.warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    order.warehouse = default_wh.name
            if not order.warehouse:
                return api_error('请选择仓库')

            # P1-BUGFIX: 库位管理启用时 location 必填（AGENTS.md 规则二）
            if location_management_enabled() and not (order.location or '').strip():
                db.session.rollback()
                return api_error('库位管理已启用，请选择库位')

            for item in order.items:
                material = db.session.get(Material, item.material_id)
                if material:
                    current_stock = normalize_stock_quantity(material.stock or 0)
                    quantity = normalize_stock_quantity(item.quantity or 0)
                    if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                        return api_error(f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}')

            for item in order.items:
                material = db.session.get(Material, item.material_id)
                if material:
                    # 使用原子扣减避免并发超卖（FOR UPDATE 条件 UPDATE），并检查返回值
                    ok, error_msg, _ = deduct_stock_atomic(material.id, item.quantity or 0,
                        transaction_type='after_sale_out',
                        reference_type='after_sale_out_order',
                        reference_id=order.id,
                        remark=f'After-sales outbound order {order.order_no}',
                        warehouse=order.warehouse)
                    if not ok:
                        db.session.rollback()
                        return api_error(error_msg or '库存扣减失败')
                    # 同步库位库存（与 batch_complete_out_order 对称），
                    # 库位管理与总库存独立维护，必须显式同步。
                    # P1-BUGFIX: 开启库位管理时优先用 order.location，未开库位时退回 order.warehouse
                    if location_management_enabled():
                        loc_dim = (order.location or '').strip() or order.warehouse
                        if loc_dim:
                            loc_ok, loc_err = update_location_inventory(
                                material, loc_dim, -(item.quantity or 0),
                                warehouse=order.warehouse,
                            )
                            if not loc_ok:
                                db.session.rollback()
                                return api_error(loc_err or '库位库存扣减失败')

            order.status = 'completed'
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('提交失败，请稍后重试')
            log_operation('售后出库完成', f'售后出库单：{order.order_no}', 'after_sale_out_order', order.id)
            return jsonify({'status': 'success', 'msg': '提交成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/<int:id>/revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def revert_after_sale_out_order(id):
        from app import (AfterSaleOutOrder, _acquire_order_write_lock, add_stock, api_error,
                         location_management_enabled, log_operation,
                         update_location_inventory)
        from sqlalchemy.orm import selectinload
        try:
            order = AfterSaleOutOrder.query.get_or_404(id)
            if order.status != 'completed':
                return api_error('只有已完成的售后出库单可以反提交')

            locked, ok = _acquire_order_write_lock(
                AfterSaleOutOrder, id, 'completed', selectinload(AfterSaleOutOrder.items)
            )
            if not ok:
                return jsonify({'status': 'error', 'msg': '该售后出库单状态已变化，不能重复反提交'}), 409
            order = locked

            for item in order.items:
                if item.material and (item.quantity or 0) > 0:
                    ok, err = add_stock(
                        item.material,
                        item.quantity or 0,
                        transaction_type='revert_after_sale_out',
                        reference_type='after_sale_out_order',
                        reference_id=order.id,
                        remark=f'反提交售后出库 {order.order_no}',
                        warehouse=order.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存恢复失败')
                    # 同步还原库位库存（与 complete_after_sale_out_order 对称），
                    # 库位管理与总库存独立维护，必须显式同步。
                    # P1-BUGFIX: 开启库位管理时优先用 order.location，未开库位时退回 order.warehouse
                    if location_management_enabled():
                        loc_dim = (order.location or '').strip() or order.warehouse
                        if loc_dim:
                            loc_ok, loc_err = update_location_inventory(
                                item.material, loc_dim, item.quantity or 0,
                                warehouse=order.warehouse,
                            )
                            if not loc_ok:
                                db.session.rollback()
                                return api_error(loc_err or '库位库存还原失败')

            order.status = 'pending'
            db.session.commit()
            log_operation('售后出库反提交', f'售后出库单：{order.order_no}', 'after_sale_out_order', order.id)
            return jsonify({'status': 'success', 'msg': '反提交成功，库存已恢复'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'售后出库反提交失败: {e}')
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_after_sale_out_order(id):
        from app import (AfterSaleOutOrder, _acquire_order_write_lock,
                         _release_document_push_lines, api_error, log_operation)
        from sqlalchemy.orm import selectinload
        order = AfterSaleOutOrder.query.get_or_404(id)
        # 与其他模块一致：仅草稿状态可删除，用 != 'pending' 而非 == 'completed'
        if order.status != 'pending':
            return api_error('只有草稿状态的售后出库单可以删除')

        try:
            # 重新锁定并校验草稿状态，防止并发完成后仍被物理删除。
            locked, ok = _acquire_order_write_lock(AfterSaleOutOrder, id, 'pending', [
                selectinload(AfterSaleOutOrder.items),
            ])
            if not ok:
                return jsonify({'status': 'error', 'msg': '该售后出库单状态已变更；已完成单请先反提交后再删除'}), 409
            order = locked

            _release_document_push_lines('after_sale_out', order.id, f'目标草稿 {order.order_no} 已删除')
            for item in list(order.items):
                db.session.delete(item)
            db.session.delete(order)
            db.session.commit()
            log_operation('删除售后出库单', f'售后出库单：{order.order_no}', 'after_sale_out_order', order.id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/<int:id>/copy', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def copy_after_sale_out_order(id):
        # Copy an after-sale outbound order into a new draft order.
        from datetime import date
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, api_error,
                         generate_order_no, log_operation, round_to_2_decimals)
        from sqlalchemy.orm import joinedload
        from flask_login import current_user
        source = AfterSaleOutOrder.query.options(
            joinedload(AfterSaleOutOrder.items),
        ).get_or_404(id)
        if not source.items:
            return api_error('原售后出库单没有明细，不能复制')

        try:
            new_order = AfterSaleOutOrder(
                order_no=generate_order_no('ASO'),
                date=date.today(),
                customer=source.customer,
                customer_id=source.customer_id,
                warehouse=source.warehouse or '',
                location=getattr(source, 'location', '') or '',
                contact=source.contact,
                phone=source.phone,
                reason=source.reason,
                source_sales_order_id=None,
                source_out_order_id=None,
                responsibility=source.responsibility,
                customer_feedback=source.customer_feedback,
                remark=(f'由售后出库单 {source.order_no} 复制生成'
                        + (f'；原备注：{source.remark}' if source.remark else '')),
                status='pending',
                operator_id=current_user.id,
                total_amount=0,
            )
            db.session.add(new_order)
            db.session.flush()

            copied_count = 0
            total_amount = 0
            for item in source.items:
                qty = round_to_2_decimals(item.quantity or 0)
                price = round_to_2_decimals(item.price or 0)
                amount = round_to_2_decimals(qty * price)
                db.session.add(AfterSaleOutOrderItem(
                    after_sale_out_order_id=new_order.id,
                    material_id=item.material_id,
                    quantity=qty,
                    price=price,
                    amount=amount,
                    remark=item.remark,
                    contract_id=item.contract_id,
                    contract_no=item.contract_no,
                    project_name=item.project_name,
                ))
                total_amount = round_to_2_decimals(total_amount + amount)
                copied_count += 1

            if copied_count <= 0:
                db.session.rollback()
                return api_error('原售后出库单没有有效明细，不能复制')

            new_order.total_amount = total_amount
            db.session.commit()
            log_operation('复制售后出库单', f'{source.order_no} -> {new_order.order_no}', 'after_sale_out_order', new_order.id)
            return jsonify({
                'status': 'success',
                'msg': '复制成功，已生成新的售后出库草稿',
                'id': new_order.id,
                'order_no': new_order.order_no,
                'redirect_url': url_for('after_sale_out_detail', id=new_order.id),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'复制售后出库单失败: {e}')
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/batch_delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_after_sale_out():
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem,
                         _acquire_order_write_lock, api_error,
                         _release_document_push_lines, log_operation)
        from sqlalchemy.orm import selectinload
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的售后出库单')

        orders = AfterSaleOutOrder.query.filter(AfterSaleOutOrder.id.in_(ids)).all()
        # 与其他模块一致：仅草稿状态可删除
        blocked = [order.order_no for order in orders if order.status != 'pending']
        if blocked:
            return api_error('以下售后出库单非草稿状态，不能删除：' + '、'.join(blocked))

        deleted_count = 0
        skipped = []
        # 逐条加写锁并独立提交，单点失败仅回滚自身，不影响其余单据。
        for order_id in ids:
            order_no = None
            try:
                locked, ok = _acquire_order_write_lock(
                    AfterSaleOutOrder, order_id, 'pending', selectinload(AfterSaleOutOrder.items)
                )
                if not ok or locked is None:
                    existing = AfterSaleOutOrder.query.get(order_id)
                    order_no = existing.order_no if existing else f'ID:{order_id}'
                    skipped.append(f'{order_no}(状态已变更)')
                    db.session.rollback()
                    continue
                order = locked
                order_no = order.order_no
                _release_document_push_lines('after_sale_out', order.id, f'目标草稿 {order.order_no} 已批量删除')
                for item in list(order.items):
                    db.session.delete(item)
                db.session.delete(order)
                db.session.commit()
                deleted_count += 1
            except Exception:
                db.session.rollback()
                skipped.append(f'{order_no or f"ID:{order_id}"}(错误)')
                app.logger.exception('批量删除售后出库单失败: ID=%s', order_id)

        msg = f'批量删除完成，共删除 {deleted_count} 张售后出库单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        log_operation('批量删除售后出库单', f'共删除 {deleted_count} 张售后出库单', 'after_sale_out_order')
        return jsonify({'status': 'success', 'msg': msg, 'deleted': deleted_count, 'skipped': skipped})

    @app.route('/export/template/after_sale_out')
    @login_required
    def export_after_sale_out_template():
        from app import _workbook_response
        return _workbook_response(
            'after_sale_out_template.xlsx',
            '售后出库导入模板',
            ['单据编号', '日期', '客户', '联系人', '电话', '售后原因', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注'],
            [['ASO24010001', '2024-01-01', '示例客户', '李四', '13800138000', '售后换货', 'MAT001', '示例物料', '规格A', '个', 1, 0, '']],
        )

    @app.route('/after_sale_out/download_template')
    @login_required
    def download_after_sale_out_template():
        from app import _workbook_response
        return _workbook_response(
            'after_sale_out_template.xlsx',
            '售后出库导入模板',
            ['单据编号', '日期', '客户', '联系人', '电话', '售后原因', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注'],
            [['ASO24010001', '2024-01-01', '示例客户', '李四', '13800138000', '售后换货', 'MAT001', '示例物料', '规格A', '个', 1, 0, '']],
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/after_sale_out/import', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def import_after_sale_out():
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, _find_or_create_customer,
                         _find_or_create_material, _get_excel_cell, _get_excel_number,
                         _import_result, _order_no_from_row, _parse_excel_date,
                         _read_import_sheet, api_error, round_to_2_decimals,
                         validate_excel_extension, validate_excel_size)
        from flask_login import current_user
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的售后出库文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['单据编号', '售后出库单号', '订单编号'],
            'date': ['日期'],
            'customer': ['客户'],
            'contact': ['联系人'],
            'phone': ['电话', '手机'],
            'reason': ['售后原因', '原因'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量'],
            'price': ['单价', '价格'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'customer', 'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（客户、物料编码、数量）。检测到的表头：{", ".join(header_row)}')
            orders_by_no = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                customer_name = _get_excel_cell(row, col_map, 'customer')
                material_code = _get_excel_cell(row, col_map, 'material_code')
                quantity = _get_excel_number(row, col_map, 'quantity')
                if not customer_name or not material_code or quantity <= 0:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：客户、物料编码为空或数量不正确')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'ASO')
                order = orders_by_no.get(order_no)
                if not order:
                    if AfterSaleOutOrder.query.filter_by(order_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：售后出库单号 {order_no} 已存在')
                        continue
                    contact = _get_excel_cell(row, col_map, 'contact')
                    phone = _get_excel_cell(row, col_map, 'phone')
                    _find_or_create_customer(customer_name, contact, phone)
                    order = AfterSaleOutOrder(
                        order_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        customer=customer_name,
                        contact=contact,
                        phone=phone,
                        reason=_get_excel_cell(row, col_map, 'reason'),
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        status='pending',
                        operator_id=current_user.id,
                        total_amount=0,
                    )
                    db.session.add(order)
                    db.session.flush()
                    orders_by_no[order_no] = order
                    order_count += 1
                material = _find_or_create_material(
                    material_code,
                    _get_excel_cell(row, col_map, 'material_name'),
                    _get_excel_cell(row, col_map, 'spec'),
                    _get_excel_cell(row, col_map, 'unit'),
                )
                price = _get_excel_number(row, col_map, 'price', material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                order.total_amount = (order.total_amount or 0) + amount
                item_remark = (_get_excel_cell(row, col_map, 'remark') or '').strip() or None
                db.session.add(AfterSaleOutOrderItem(
                    after_sale_out_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=amount,
                    remark=item_remark,
                ))
                item_count += 1
            db.session.commit()
            return _import_result('售后出库单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'售后出库导入失败: {e}')
            return api_error(f'售后出库导入失败：{str(e)}')