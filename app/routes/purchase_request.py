#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 采购申请（purchase_request）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_purchase_request_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 purchase_request_list、
# add_purchase_request、purchase_request_detail、approve_purchase_request 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（PurchaseRequest、PurchaseRequestItem、PurchaseOrder、
#   PurchaseOrderItem、Material、Unit、Supplier、各辅助函数 _get_order_list_filters /
#   _apply_status_date_filters / _apply_purchase_request_search / _apply_header_or_item_contract_filters /
#   round_to_2_decimals / purchase_request_item_has_material / purchase_request_item_data_has_material /
#   build_purchase_request_execution / generate_order_no / parse_date_value / parse_float_value /
#   api_error / log_operation / update_purchase_order_status / serialize_material / serialize_unit /
#   serialize_supplier / _material_row_common / _render_generic_document_print / _fmt_date /
#   _operator_name / validate_excel_extension / validate_excel_size / _read_import_sheet /
#   _get_excel_cell / _get_excel_number / _order_no_from_row / _parse_excel_date /
#   _find_or_create_material / _find_or_create_supplier / _import_result 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_purchase_request_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 purchase_request_* 各路由测试覆盖
def register_purchase_request_routes(app):
    @app.route('/purchase_request')
    @login_required
    def purchase_request_list():
        from sqlalchemy.orm import joinedload
        from app import (PurchaseRequest, STOCK_COMPARE_EPSILON,
                         _apply_purchase_request_search, _apply_status_date_filters,
                         _get_order_list_filters, build_purchase_request_execution,
                         purchase_request_item_has_material, round_to_2_decimals)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'approved', 'rejected', 'completed'))
        allowed_sorts = {'request_no', 'date', 'applicant', 'department', 'urgency', 'expected_date', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'

        query = PurchaseRequest.query.options(joinedload(PurchaseRequest.items))
        query = _apply_status_date_filters(query, PurchaseRequest, status_filter, date_start, date_end)
        query = _apply_purchase_request_search(query, search)

        sort_col = getattr(PurchaseRequest, sort_by, PurchaseRequest.created_at)
        query = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        execution_stats = {}
        for request_order in pagination.items:
            valid_items = [item for item in request_order.items if purchase_request_item_has_material(item)]
            item_execution = build_purchase_request_execution(valid_items)
            request_qty = round_to_2_decimals(sum(item.get('request_quantity', 0) for item in item_execution.values()))
            ordered_qty = round_to_2_decimals(sum(item.get('ordered_quantity', 0) for item in item_execution.values()))
            received_qty = round_to_2_decimals(sum(item.get('received_quantity', 0) for item in item_execution.values()))
            remaining_to_order = round_to_2_decimals(sum(item.get('remaining_to_order', 0) for item in item_execution.values()))
            if request_order.status == 'rejected':
                execution_status = 'rejected'
            elif received_qty + STOCK_COMPARE_EPSILON >= request_qty and request_qty > 0:
                execution_status = 'completed'
            elif ordered_qty > 0 or received_qty > 0:
                execution_status = 'partial'
            elif request_order.status == 'approved':
                execution_status = 'approved'
            else:
                execution_status = 'pending'
            execution_stats[request_order.id] = {
                'request_quantity': request_qty,
                'ordered_quantity': ordered_qty,
                'received_quantity': received_qty,
                'remaining_to_order': remaining_to_order,
                'status': execution_status,
            }
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template(
            'purchase_request.html',
            pagination=pagination,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
            execution_stats=execution_stats,
        )

    @app.route('/purchase_request/<int:id>')
    @login_required
    def purchase_request_detail(id):
        from app import (PurchaseOrder, PurchaseRequest, build_purchase_request_execution,
                         purchase_request_item_has_material)
        request_order = PurchaseRequest.query.get_or_404(id)
        valid_items = [item for item in request_order.items if purchase_request_item_has_material(item)]
        related_purchase_orders = PurchaseOrder.query.filter_by(purchase_request_id=request_order.id).order_by(PurchaseOrder.id.asc()).all()
        item_execution = build_purchase_request_execution(valid_items)
        item_purchase_orders = {item.id: [] for item in valid_items}
        for po in related_purchase_orders:
            for po_item in po.items:
                if po_item.purchase_request_item_id in item_purchase_orders:
                    item_purchase_orders[po_item.purchase_request_item_id].append(po)
        return render_template(
            'purchase_request_detail.html',
            order=request_order,
            valid_items=valid_items,
            related_purchase_orders=related_purchase_orders,
            item_execution=item_execution,
            item_purchase_orders=item_purchase_orders,
        )

    @app.route('/purchase_request/<int:id>/print')
    @login_required
    def print_purchase_request(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, PurchaseRequest, PurchaseRequestItem,
                         _fmt_date, _material_row_common, _operator_name,
                         _render_generic_document_print, purchase_request_item_has_material)
        request_order = PurchaseRequest.query.options(
            joinedload(PurchaseRequest.operator),
            selectinload(PurchaseRequest.items).joinedload(PurchaseRequestItem.material).joinedload(Material.unit),
            selectinload(PurchaseRequest.items).joinedload(PurchaseRequestItem.unit),
            selectinload(PurchaseRequest.items).joinedload(PurchaseRequestItem.supplier),
        ).get_or_404(id)
        valid_items = [item for item in request_order.items if purchase_request_item_has_material(item)]
        rows = [
            _material_row_common(
                item,
                price=item.estimated_price or 0,
                amount=item.estimated_amount or 0,
                extra={'supplier': item.supplier.name if item.supplier else (item.supplier_name or '')}
            )
            for item in valid_items
        ]
        urgency_label = {'normal': '普通', 'urgent': '紧急', 'emergency': '特急'}.get(request_order.urgency, request_order.urgency or '')
        return _render_generic_document_print({
            'title': '采购申请单',
            'subtitle': 'PURCHASE REQUEST',
            'number_label': '申请单号',
            'number': request_order.request_no,
            'date_label': '申请日期',
            'date': _fmt_date(request_order.date),
            'status': request_order.status,
            'info': [
                ('申请人', request_order.applicant or ''),
                ('申请部门', request_order.department or ''),
                ('紧急程度', urgency_label),
                ('期望到货', _fmt_date(request_order.expected_date)),
                ('申请原因', request_order.reason or ''),
                ('制单人', _operator_name(request_order)),
            ],
            'remark': request_order.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '申请数量', 'right'),
                ('price', '预计单价', 'right money'),
                ('amount', '预计金额', 'right money'),
                ('supplier', '推荐供应商', ''),
                ('remark', '备注', ''),
            ],
            'rows': rows,
            'total_amount': request_order.total_amount or sum(row.get('amount', 0) or 0 for row in rows),
            'signatures': ['申请', '部门审核', '采购审核', '批准'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/create_purchase_order', methods=['POST'])
    @require_role('purchase')
    @login_required
    def create_purchase_order_from_request(id):
        from datetime import date
        from flask_login import current_user
        from sqlalchemy.orm import joinedload
        from app import (PurchaseOrder, PurchaseOrderItem, PurchaseRequest,
                         PurchaseRequestItem, STOCK_COMPARE_EPSILON, api_error,
                         build_purchase_request_execution, generate_order_no,
                         log_operation, parse_float_value, purchase_request_item_has_material,
                         round_to_2_decimals, update_purchase_order_status)
        payload = request.get_json(silent=True) or {}
        request_order = PurchaseRequest.query.options(
            joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.material),
            joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.supplier),
        ).get_or_404(id)
        if request_order.status not in ('approved', 'completed'):
            return api_error('采购申请需审核通过后才能生成采购单')
        valid_items = [item for item in request_order.items if item.material_id and purchase_request_item_has_material(item)]
        if not valid_items:
            return api_error('采购申请没有可下推的物料明细')

        try:
            item_execution = build_purchase_request_execution(valid_items)
            selected_quantities = {}
            selected_items = payload.get('items') if isinstance(payload, dict) else None
            if selected_items is not None:
                if not isinstance(selected_items, list) or not selected_items:
                    return api_error('请选择要下推的采购申请明细')
                valid_item_by_id = {item.id: item for item in valid_items}
                for selected in selected_items:
                    if not isinstance(selected, dict):
                        return api_error('下推明细格式不正确')
                    try:
                        item_id = int(selected.get('purchase_request_item_id') or selected.get('item_id') or 0)
                    except (TypeError, ValueError):
                        item_id = 0
                    req_item = valid_item_by_id.get(item_id)
                    if not req_item:
                        return api_error('下推明细不属于当前采购申请')
                    remaining_qty = round_to_2_decimals(item_execution.get(item_id, {}).get('remaining_to_order', 0))
                    quantity = round_to_2_decimals(parse_float_value(selected.get('quantity'), remaining_qty))
                    if quantity <= 0:
                        return api_error('本次下推数量必须大于 0')
                    if quantity - remaining_qty > STOCK_COMPARE_EPSILON:
                        return api_error('本次下推数量不能大于未下推数量')
                    selected_quantities[item_id] = round_to_2_decimals(selected_quantities.get(item_id, 0) + quantity)
                for item_id, quantity in selected_quantities.items():
                    remaining_qty = round_to_2_decimals(item_execution.get(item_id, {}).get('remaining_to_order', 0))
                    if quantity - remaining_qty > STOCK_COMPARE_EPSILON:
                        return api_error('同一明细累计下推数量不能大于未下推数量')
                push_items = [valid_item_by_id[item_id] for item_id in selected_quantities.keys()]
            else:
                push_items = [
                    item for item in valid_items
                    if item_execution.get(item.id, {}).get('remaining_to_order', 0) > STOCK_COMPARE_EPSILON
                ]
            if not push_items:
                existing_orders = PurchaseOrder.query.filter_by(purchase_request_id=request_order.id).order_by(PurchaseOrder.id.asc()).all()
                if existing_orders:
                    existing = existing_orders[0]
                    return jsonify({
                        'status': 'success',
                        'msg': '该采购申请已全部下推',
                        'id': existing.id,
                        'order_no': existing.order_no,
                        'ids': [order.id for order in existing_orders],
                        'order_nos': [order.order_no for order in existing_orders],
                        'redirect_url': url_for('purchase_order_detail', id=existing.id)
                    })
                return api_error('采购申请没有可下推数量')

            grouped_items = {}
            for req_item in push_items:
                supplier_id = req_item.supplier_id or (req_item.material.supplier_id if req_item.material else None) or 0
                grouped_items.setdefault(supplier_id, []).append(req_item)
            if len(grouped_items) > 1:
                created_orders = []
                for supplier_id, group_items in grouped_items.items():
                    order = PurchaseOrder(
                        order_no=generate_order_no('PO'),
                        date=date.today(),
                        supplier_id=supplier_id or None,
                        purchase_request_id=request_order.id,
                        expected_date=request_order.expected_date,
                        status='pending',
                        remark=f'由采购申请 {request_order.request_no} 下推生成',
                        operator_id=current_user.id,
                    )
                    db.session.add(order)
                    db.session.flush()

                    for req_item in group_items:
                        price = round_to_2_decimals(req_item.estimated_price or (req_item.material.price if req_item.material else 0) or 0)
                        quantity = round_to_2_decimals(selected_quantities.get(req_item.id, item_execution.get(req_item.id, {}).get('remaining_to_order', req_item.quantity or 0)))
                        if quantity <= 0:
                            continue
                        db.session.add(PurchaseOrderItem(
                            purchase_order_id=order.id,
                            purchase_request_item_id=req_item.id,
                            material_id=req_item.material_id,
                            quantity=quantity,
                            received_quantity=0,
                            price=price,
                            amount=round_to_2_decimals(quantity * price),
                            remark=req_item.remark or ''
                        ))

                    db.session.flush()
                    db.session.expire(order, ['items'])
                    update_purchase_order_status(order)
                    created_orders.append(order)

                if not created_orders:
                    db.session.rollback()
                    return api_error('采购申请没有有效数量，不能生成采购单')
                db.session.commit()
                log_operation(
                    '采购申请下推采购单',
                    f'{request_order.request_no} -> {", ".join(order.order_no for order in created_orders)}',
                    'purchase_order',
                    created_orders[0].id
                )
                return jsonify({
                    'status': 'success',
                    'msg': f'已按供应商生成 {len(created_orders)} 张采购单',
                    'id': created_orders[0].id,
                    'order_no': created_orders[0].order_no,
                    'ids': [order.id for order in created_orders],
                    'order_nos': [order.order_no for order in created_orders],
                    'redirect_url': url_for('purchase_order_detail', id=created_orders[0].id)
                })

            supplier_id = next(iter(grouped_items.keys()), 0) or None
            order = PurchaseOrder(
                order_no=generate_order_no('PO'),
                date=date.today(),
                supplier_id=supplier_id,
                purchase_request_id=request_order.id,
                expected_date=request_order.expected_date,
                status='pending',
                remark=f'由采购申请 {request_order.request_no} 下推生成',
                operator_id=current_user.id,
            )
            db.session.add(order)
            db.session.flush()

            for req_item in push_items:
                price = round_to_2_decimals(req_item.estimated_price or (req_item.material.price if req_item.material else 0) or 0)
                quantity = round_to_2_decimals(selected_quantities.get(req_item.id, item_execution.get(req_item.id, {}).get('remaining_to_order', req_item.quantity or 0)))
                if quantity <= 0:
                    continue
                db.session.add(PurchaseOrderItem(
                    purchase_order_id=order.id,
                    purchase_request_item_id=req_item.id,
                    material_id=req_item.material_id,
                    quantity=quantity,
                    received_quantity=0,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                    remark=req_item.remark or ''
                ))

            db.session.flush()
            db.session.expire(order, ['items'])
            update_purchase_order_status(order)
            db.session.commit()
            log_operation('采购申请下推采购单', f'{request_order.request_no} -> {order.order_no}', 'purchase_order', order.id)
            return jsonify({
                'status': 'success',
                'msg': '采购单生成成功',
                'id': order.id,
                'order_no': order.order_no,
                'redirect_url': url_for('purchase_order_detail', id=order.id)
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购申请下推采购单失败: {e}')
            return api_error('生成采购单失败，请稍后重试')

    @app.route('/purchase_request/add')
    @login_required
    def purchase_request_add_page():
        from datetime import datetime
        from sqlalchemy.orm import joinedload
        from app import (Material, Supplier, Unit, generate_order_no, serialize_material,
                         serialize_supplier, serialize_unit)
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        suppliers = Supplier.query.all()
        request_no = generate_order_no('PR')
        request_date = datetime.now().strftime('%Y-%m-%d')
        return render_template(
                              'purchase_request_add.html',
                              page_title='新增采购申请单',
                              order=None,
                              materials=[serialize_material(material) for material in materials],
                              units=[serialize_unit(unit) for unit in units],
                              suppliers=[serialize_supplier(supplier) for supplier in suppliers],
                              request_id=None, request_no=request_no, request_date=request_date,
                              initial_items=[])

    @app.route('/purchase_request/<int:id>/edit')
    @login_required
    def purchase_request_edit_page(id):
        from datetime import date
        from sqlalchemy.orm import joinedload
        from app import (Material, PurchaseRequest, PurchaseRequestItem, Supplier, Unit,
                         serialize_material, serialize_supplier, serialize_unit)
        request_order = PurchaseRequest.query.options(
            joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.material).joinedload(Material.unit),
            joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.unit),
            joinedload(PurchaseRequest.items).joinedload(PurchaseRequestItem.supplier),
        ).get_or_404(id)
        if request_order.status != 'pending':
            flash('只有待审批的采购申请单可以编辑。', 'warning')
            return redirect(url_for('purchase_request_detail', id=id))
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        suppliers = Supplier.query.all()
        initial_items = []
        for item in request_order.items:
            material = item.material
            unit = item.unit or (material.unit if material and material.unit else None)
            initial_items.append({
                'material_id': item.material_id or (material.id if material else None),
                'material_code': item.material_code or (material.code if material else ''),
                'material_name': item.material_name or (material.name if material else ''),
                'spec': item.spec or (material.spec if material else ''),
                'unit_id': item.unit_id or (unit.id if unit else None),
                'unit_name': unit.name if unit else '',
                'stock': float(material.stock or 0) if material else 0,
                'quantity': float(item.quantity or 0),
                'estimated_price': float(item.estimated_price or 0),
                'supplier_id': item.supplier_id or (item.supplier.id if item.supplier else None),
                'supplier_name': item.supplier.name if item.supplier else (item.supplier_name or ''),
            })
        return render_template(
            'purchase_request_add.html',
            page_title='编辑采购申请单',
            order=request_order,
            materials=[serialize_material(material) for material in materials],
            units=[serialize_unit(unit) for unit in units],
            suppliers=[serialize_supplier(supplier) for supplier in suppliers],
            request_id=request_order.id,
            request_no=request_order.request_no,
            request_date=(request_order.date if request_order.date else date.today()).strftime('%Y-%m-%d'),
            initial_items=initial_items)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/add', methods=['POST'])
    @require_role('purchase')
    @login_required
    def add_purchase_request():
        from datetime import date
        from flask_login import current_user
        from app import (Material, PurchaseRequest, PurchaseRequestItem, Supplier,
                         api_error, generate_order_no, log_operation, parse_date_value,
                         parse_float_value, purchase_request_item_data_has_material)
        try:
            payload = request.get_json(silent=True)
            data = payload if isinstance(payload, dict) else request.form
            request_id = data.get('request_id')
            if request_id in ('', 'None', 'null'):
                request_id = None
            elif request_id:
                try:
                    request_id = int(request_id)
                except (TypeError, ValueError):
                    request_id = None

            request_no = (data.get('request_no') or '').strip() or generate_order_no('PR')
            request_date = parse_date_value(data.get('date'), date.today())
            if not request_date:
                return api_error('申请日期格式不正确，请重新选择日期')
            applicant = (data.get('applicant') or '').strip()
            department = (data.get('department') or '').strip()
            urgency = (data.get('urgency') or 'normal').strip() or 'normal'
            if urgency not in {'normal', 'urgent', 'emergency'}:
                urgency = 'normal'
            expected_date = parse_date_value(data.get('expected_date'))
            reason = (data.get('reason') or '').strip()
            remark = (data.get('remark') or '').strip()

            if request_id:
                request_order = db.session.get(PurchaseRequest, request_id)
                if not request_order:
                    return api_error('采购申请单不存在，请刷新后重试')
                if request_order.status != 'pending':
                    return api_error('只有待审批的采购申请单可以修改')
            else:
                request_order = PurchaseRequest.query.filter_by(request_no=request_no).first()
                if request_order:
                    if request_order.status != 'pending':
                        return api_error('采购申请单号已存在，不能重复保存')
                else:
                    request_order = PurchaseRequest(
                        request_no=request_no,
                        status='pending',
                        operator_id=current_user.id
                    )
            db.session.add(request_order)
            db.session.flush()

            request_order.request_no = request_no
            request_order.date = request_date
            request_order.applicant = applicant
            request_order.department = department
            request_order.urgency = urgency
            request_order.expected_date = expected_date
            request_order.reason = reason
            request_order.remark = remark

            items_data = []
            if isinstance(payload, dict):
                items_data = payload.get('items', []) or []
            elif request.form.get('items'):
                try:
                    items_data = json.loads(request.form.get('items', '[]'))
                except json.JSONDecodeError:
                    items_data = []

            valid_items_data = [
                item_data for item_data in items_data
                if purchase_request_item_data_has_material(item_data)
            ]

            if not valid_items_data:
                return api_error('请至少添加一条采购明细')

            for existing_item in list(request_order.items):
                db.session.delete(existing_item)
            db.session.flush()

            total_amount = 0
            for item_data in valid_items_data:
                material_id = item_data.get('material_id')
                material_code = (item_data.get('material_code') or item_data.get('code') or '').strip()
                material = None
                if material_id:
                    material = db.session.get(Material, material_id)
                if not material and material_code:
                    material = Material.query.filter_by(code=material_code).first()

                quantity = parse_float_value(item_data.get('quantity'), 0)
                if quantity <= 0:
                    return api_error(f'物料 {material_code or item_data.get("material_name", "")} 的数量必须大于0')

                estimated_price = parse_float_value(item_data.get('estimated_price'), 0)
                estimated_amount = quantity * estimated_price
                total_amount += estimated_amount

                unit_id = item_data.get('unit_id')
                supplier_id = item_data.get('supplier_id')
                try:
                    unit_id = int(unit_id) if unit_id not in (None, '', 'null', 'None') else None
                except (TypeError, ValueError):
                    unit_id = None
                try:
                    supplier_id = int(supplier_id) if supplier_id not in (None, '', 'null', 'None') else None
                except (TypeError, ValueError):
                    supplier_id = None
                supplier_name = (item_data.get('supplier_name') or item_data.get('supplier') or '').strip()
                supplier = db.session.get(Supplier, supplier_id) if supplier_id else None
                if not supplier and supplier_name:
                    supplier_lookup = supplier_name.lower()
                    supplier = Supplier.query.filter(
                        db.or_(
                            db.func.lower(Supplier.name) == supplier_lookup,
                            db.func.lower(Supplier.code) == supplier_lookup
                        )
                    ).first()
                supplier_id = supplier.id if supplier else None
                if supplier:
                    supplier_name = supplier.name

                item = PurchaseRequestItem(
                    purchase_request_id=request_order.id,
                    material_id=material.id if material else None,
                    material_name=(item_data.get('material_name') or (material.name if material else '')).strip(),
                    material_code=material_code or (material.code if material else ''),
                    spec=(item_data.get('spec') or (material.spec if material else '') or '').strip(),
                    quantity=quantity,
                    unit_id=unit_id,
                    estimated_price=estimated_price,
                    estimated_amount=estimated_amount,
                    supplier_id=supplier_id,
                    supplier_name=supplier_name or None,
                    remark=(item_data.get('remark') or '').strip()
                )
                db.session.add(item)

            request_order.total_amount = total_amount
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '保存失败，请稍后重试'}), 500
            log_operation('保存采购申请单', f'采购申请单：{request_order.request_no}', 'purchase_request', request_order.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': request_order.id, 'request_no': request_order.request_no})
        except Exception as e:
            db.session.rollback()
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/approve', methods=['POST'])
    @require_role('purchase')
    @login_required
    def approve_purchase_request(id):
        from app import PurchaseRequest, api_error, log_operation
        try:
            request_order = PurchaseRequest.query.get_or_404(id)
            if request_order.status != 'pending':
                return api_error('只有待审批的采购申请单可以审批')
            request_order.status = 'approved'
            db.session.commit()
            log_operation('采购申请审批通过', f'采购申请单：{request_order.request_no}', 'purchase_request', request_order.id)
            return jsonify({'status': 'success', 'msg': '操作完成'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/reject', methods=['POST'])
    @require_role('purchase')
    @login_required
    def reject_purchase_request(id):
        from app import PurchaseRequest, api_error, log_operation
        try:
            data = request.get_json(silent=True) or {}
            request_order = PurchaseRequest.query.get_or_404(id)
            if request_order.status != 'pending':
                return api_error('只有待审批的采购申请单可以驳回')
            request_order.status = 'rejected'
            request_order.remark = data.get('remark', request_order.remark)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500
            log_operation('采购申请驳回', f'采购申请单：{request_order.request_no}', 'purchase_request', request_order.id)
            return jsonify({'status': 'success', 'msg': '操作完成'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/revert', methods=['POST'])
    @require_role('purchase')
    @login_required
    def revert_purchase_request(id):
        from app import PurchaseOrder, PurchaseRequest, api_error, log_operation
        try:
            request_order = PurchaseRequest.query.get_or_404(id)
            if request_order.status not in ('approved', 'completed'):
                return api_error('只有已审批或已完成的采购申请单可以反审')
            downstream_count = PurchaseOrder.query.filter_by(purchase_request_id=request_order.id).count()
            if downstream_count > 0:
                return api_error('该采购申请已有下游采购单，不能反审；请先删除下游采购单')
            request_order.status = 'pending'
            db.session.commit()
            log_operation('采购申请反审', f'采购申请单：{request_order.request_no}', 'purchase_request', request_order.id)
            return jsonify({'status': 'success', 'msg': '反审成功，采购申请已退回待审批'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购申请反审失败: {e}')
            return api_error('反审失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/complete', methods=['POST'])
    @require_role('purchase')
    @login_required
    def complete_purchase_request(id):
        from app import PurchaseRequest, api_error, log_operation
        try:
            request_order = PurchaseRequest.query.get_or_404(id)
            if request_order.status != 'approved':
                return api_error('只有已审批的采购申请单可以完成')
            request_order.status = 'completed'
            db.session.commit()
            log_operation('采购申请完成', f'采购申请单：{request_order.request_no}', 'purchase_request', request_order.id)
            return jsonify({'status': 'success', 'msg': '操作完成'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/<int:id>/delete', methods=['POST'])
    @require_role('purchase')
    @login_required
    def delete_purchase_request(id):
        from app import PurchaseRequest, api_error, log_operation
        try:
            request_order = PurchaseRequest.query.get_or_404(id)
            if request_order.status not in ('pending', 'rejected'):
                return api_error('只有待审批或已驳回的采购申请单可以删除')

            request_no = request_order.request_no

            # 删除明细
            for item in list(request_order.items):
                db.session.delete(item)

            # 删除主单
            db.session.delete(request_order)

            # 提交事务
            db.session.commit()

            # 记录日志
            log_operation('删除采购申请单', f'采购申请单：{request_no}', 'purchase_request', id)

            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'删除采购申请单失败: {str(e)}')
            return api_error(f'删除失败：{str(e)}')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/batch_delete', methods=['POST'])
    @require_role('purchase')
    @login_required
    def batch_delete_purchase_request():
        from app import PurchaseRequest, PurchaseRequestItem, api_error, log_operation
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的采购申请单')

        requests_list = PurchaseRequest.query.filter(PurchaseRequest.id.in_(ids)).all()
        blocked = [req.request_no for req in requests_list if req.status not in ('pending', 'rejected')]
        if blocked:
            return api_error('只能删除待审批或已驳回的采购申请：' + '、'.join(blocked))

        try:
            PurchaseRequestItem.query.filter(PurchaseRequestItem.purchase_request_id.in_(ids)).delete(synchronize_session=False)
            deleted = PurchaseRequest.query.filter(PurchaseRequest.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            log_operation('批量删除采购申请单', f'共删除 {deleted} 张采购申请单', 'purchase_request')
            return jsonify({'status': 'success', 'msg': f'删除成功，共删除 {deleted} 张采购申请单'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除采购申请单失败: {e}')
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_request/import', methods=['POST'])
    @require_role('purchase')
    @login_required
    def import_purchase_request():
        from flask_login import current_user
        from app import (PurchaseRequest, PurchaseRequestItem, _find_or_create_material,
                         _find_or_create_supplier, _get_excel_cell, _get_excel_number,
                         _import_result, _order_no_from_row, _parse_excel_date,
                         _read_import_sheet, api_error, round_to_2_decimals,
                         validate_excel_extension, validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的采购申请文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['申请编号', '单据编号', '采购申请号'],
            'date': ['日期'],
            'applicant': ['申请人'],
            'department': ['部门'],
            'urgency': ['紧急程度'],
            'expected_date': ['期望到货', '期望日期'],
            'reason': ['申请原因', '原因'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量'],
            'price': ['预估单价', '单价', '价格'],
            'supplier': ['推荐供应商', '供应商'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（物料编码、数量）。检测到的表头：{", ".join(header_row)}')
            orders_by_no = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                material_code = _get_excel_cell(row, col_map, 'material_code')
                quantity = _get_excel_number(row, col_map, 'quantity')
                if not material_code or quantity <= 0:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料编码为空或数量不正确')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'PR')
                order = orders_by_no.get(order_no)
                if not order:
                    if PurchaseRequest.query.filter_by(request_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：采购申请号 {order_no} 已存在')
                        continue
                    urgency_text = _get_excel_cell(row, col_map, 'urgency') or '普通'
                    urgency = {'普通': 'normal', '正常': 'normal', '紧急': 'urgent', '特急': 'emergency'}.get(urgency_text, urgency_text)
                    if urgency not in {'normal', 'urgent', 'emergency'}:
                        urgency = 'normal'
                    order = PurchaseRequest(
                        request_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        applicant=_get_excel_cell(row, col_map, 'applicant'),
                        department=_get_excel_cell(row, col_map, 'department'),
                        urgency=urgency,
                        expected_date=_parse_excel_date(_get_excel_cell(row, col_map, 'expected_date'), None) if _get_excel_cell(row, col_map, 'expected_date') else None,
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
                supplier_name = _get_excel_cell(row, col_map, 'supplier')
                supplier = _find_or_create_supplier(supplier_name)
                price = _get_excel_number(row, col_map, 'price', material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                order.total_amount = (order.total_amount or 0) + amount
                db.session.add(PurchaseRequestItem(
                    purchase_request_id=order.id,
                    material_id=material.id,
                    material_name=material.name,
                    material_code=material.code,
                    spec=material.spec or '',
                    quantity=quantity,
                    unit_id=material.unit_id,
                    estimated_price=price,
                    estimated_amount=amount,
                    supplier_id=supplier.id if supplier else None,
                    supplier_name=supplier.name if supplier else supplier_name or None,
                    remark=_get_excel_cell(row, col_map, 'remark'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('采购申请单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购申请导入失败: {e}')
            return api_error(f'采购申请导入失败：{str(e)}')