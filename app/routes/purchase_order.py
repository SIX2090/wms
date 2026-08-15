#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 采购订单（purchase_order）域路由。
#
# 批量拆分模式：与销售（sales）/采购入库（in_order）域一致，采用
# 「register_purchase_order_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 purchase_order_list、save_purchase_order、purchase_order_detail、
# create_in_order_from_purchase_order 等），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（PurchaseOrder 模型、PurchaseOrderItem、Supplier、Material、
#   InOrder、InOrderItem、PurchaseRequest、Unit、STOCK_COMPARE_EPSILON、
#   各辅助函数 api_error / generate_order_no / log_operation / parse_date_value /
#   parse_float_value / round_to_2_decimals / _get_order_list_filters /
#   _apply_status_date_filters / _apply_header_or_item_contract_filters /
#   _find_or_create_supplier / _find_or_create_material / _read_import_sheet /
#   _get_excel_cell / _get_excel_number / _order_no_from_row / _parse_excel_date /
#   validate_excel_extension / validate_excel_size / _import_result /
#   _workbook_response / _render_generic_document_print / _material_row_common /
#   _fmt_date / _operator_name / serialize_material / serialize_supplier /
#   get_active_warehouses / get_recent_operation_logs / build_purchase_order_execution /
#   build_purchase_order_todo_summary / update_purchase_order_status /
#   validate_purchase_receive_quantity / recalculate_order_total /
#   purchase_order_status_label / purchase_order_to_in_order_enabled /
#   _create_in_order_from_purchase_order_core 等）在各路由函数内延迟导入
#   （请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_purchase_order_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 purchase_order_* 各路由测试覆盖
def register_purchase_order_routes(app):
    @app.route('/purchase_order')
    @require_role('warehouse', 'purchase')
    @login_required
    def purchase_order_list():
        from datetime import date
        from sqlalchemy.orm import joinedload
        from app import (Material, PurchaseOrder, PurchaseOrderItem, PurchaseRequest,
                         Supplier, STOCK_COMPARE_EPSILON,
                         _apply_header_or_item_contract_filters,
                         _apply_status_date_filters, _get_order_list_filters,
                         build_purchase_order_execution,
                         build_purchase_order_todo_summary,
                         purchase_order_status_label, round_to_2_decimals)
        # BUG-2026-07-28-003 修复：直接访问 /purchase_order 必须落到列表页；
        # 不再无脑重定向到新增页。保留 ?view=add/new 显式跳新增的兼容行为，
        # 同时支持嵌入式调用（embedded=1）保持原语义。
        view = (request.args.get('view') or '').strip().lower()
        if view in ('add', 'new'):
            return redirect(url_for('purchase_order_add_page'))
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'partial', 'completed', 'closed', 'open'))
        supplier_id = request.args.get('supplier_id', type=int) or 0
        allowed_sorts = {'order_no', 'date', 'expected_date', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'

        query = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.purchase_request),
            joinedload(PurchaseOrder.items),
        )
        status_for_base_filter = '' if status_filter == 'open' else status_filter
        query = _apply_status_date_filters(query, PurchaseOrder, status_for_base_filter, date_start, date_end)
        if status_filter == 'open':
            query = query.filter(PurchaseOrder.status.in_(('pending', 'partial')))
        if supplier_id:
            query = query.filter(PurchaseOrder.supplier_id == supplier_id)
        if search:
            search_like = f'%{search}%'
            query = query.outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.id).outerjoin(
                PurchaseRequest, PurchaseOrder.purchase_request_id == PurchaseRequest.id
            ).filter(db.or_(
                PurchaseOrder.order_no.like(search_like),
                PurchaseOrder.remark.like(search_like),
                Supplier.name.like(search_like),
                PurchaseRequest.request_no.like(search_like),
            ))
        contract_no_filter = (request.args.get('contract_no') or '').strip()
        project_name_filter = (request.args.get('project_name') or '').strip()
        query = _apply_header_or_item_contract_filters(
            query, PurchaseOrder, PurchaseOrderItem, 'purchase_order_id',
            contract_no_filter=contract_no_filter,
            project_name_filter=project_name_filter,
        )

        sort_col = getattr(PurchaseOrder, sort_by, PurchaseOrder.created_at)
        query = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        qty_stats = {}
        for order in pagination.items:
            item_execution = build_purchase_order_execution(order)
            total_qty = round_to_2_decimals(sum(item.get('order_quantity', 0) for item in item_execution.values()))
            pushed_qty = round_to_2_decimals(sum(item.get('pushed_quantity', 0) for item in item_execution.values()))
            completed_qty = round_to_2_decimals(sum(item.get('completed_quantity', 0) for item in item_execution.values()))
            pending_receive_qty = round_to_2_decimals(sum(item.get('pending_receive_quantity', 0) for item in item_execution.values()))
            remaining_to_push = round_to_2_decimals(sum(item.get('remaining_to_push', 0) for item in item_execution.values()))
            if order.status == 'closed':
                execution_status = 'closed'
            elif completed_qty + STOCK_COMPARE_EPSILON >= total_qty and total_qty > 0:
                execution_status = 'completed'
            elif completed_qty > 0:
                execution_status = 'partial_completed'
            elif pushed_qty > 0:
                execution_status = 'pushed'
            else:
                execution_status = 'pending'
            qty_stats[order.id] = {
                'total_qty': total_qty,
                'pushed_qty': pushed_qty,
                'completed_qty': completed_qty,
                'pending_receive_qty': pending_receive_qty,
                'remaining_to_push': remaining_to_push,
                'status': execution_status,
                'received_qty': pushed_qty,
                'remaining_qty': remaining_to_push,
            }
        suppliers = Supplier.query.order_by(Supplier.code.asc(), Supplier.id.asc()).all()
        summary = build_purchase_order_todo_summary()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'supplier_id': supplier_id,
            'contract_no': contract_no_filter,
            'project_name': project_name_filter,
        }
        return render_template(
            'purchase_order.html',
            pagination=pagination,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            filters=filters,
            suppliers=suppliers,
            qty_stats=qty_stats,
            today=date.today(),
            summary=summary,
            status_label=purchase_order_status_label,
        )

    @app.route('/purchase_order/export')
    @login_required
    def export_purchase_order():
        from sqlalchemy.orm import joinedload
        from app import (Material, PurchaseOrder, PurchaseOrderItem, PurchaseRequest,
                         Supplier, _apply_status_date_filters, _get_order_list_filters,
                         _workbook_response, purchase_order_status_label,
                         round_to_2_decimals)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'partial', 'completed', 'closed'))
        supplier_id = request.args.get('supplier_id', type=int) or 0
        query = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material).joinedload(Material.unit),
        )
        query = _apply_status_date_filters(query, PurchaseOrder, status_filter, date_start, date_end)
        if supplier_id:
            query = query.filter(PurchaseOrder.supplier_id == supplier_id)
        if search:
            search_like = f'%{search}%'
            query = query.outerjoin(Supplier, PurchaseOrder.supplier_id == Supplier.id).outerjoin(
                PurchaseRequest, PurchaseOrder.purchase_request_id == PurchaseRequest.id
            ).filter(db.or_(
                PurchaseOrder.order_no.like(search_like),
                PurchaseOrder.remark.like(search_like),
                Supplier.name.like(search_like),
                PurchaseRequest.request_no.like(search_like),
            ))
        query = query.order_by(PurchaseOrder.date.desc(), PurchaseOrder.id.desc())
        rows = []
        for order in query.all():
            if order.items:
                for item in order.items:
                    remain_qty = round_to_2_decimals((item.quantity or 0) - (item.received_quantity or 0))
                    rows.append([
                        order.order_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order.supplier.name if order.supplier else '',
                        order.expected_date.strftime('%Y-%m-%d') if order.expected_date else '',
                        purchase_order_status_label(order.status),
                        item.material.code if item.material else '',
                        item.material.name if item.material else '',
                        item.material.spec if item.material else '',
                        item.material.unit.name if item.material and item.material.unit else '',
                        item.quantity or 0,
                        item.received_quantity or 0,
                        remain_qty,
                        item.price or 0,
                        item.amount or 0,
                        order.remark or '',
                    ])
            else:
                rows.append([
                    order.order_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    order.supplier.name if order.supplier else '',
                    order.expected_date.strftime('%Y-%m-%d') if order.expected_date else '',
                    purchase_order_status_label(order.status),
                    '', '', '', '', 0, 0, 0, 0, 0, order.remark or '',
                ])
        return _workbook_response(
            'purchase_orders.xlsx',
            '采购单',
            ['采购单号', '日期', '供应商', '预计到货', '状态', '物料编码', '物料名称', '规格', '单位', '采购数量', '已入库', '未入库', '单价', '金额', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/import', methods=['POST'])
    @require_role('purchase')
    @login_required
    def import_purchase_order():
        from flask_login import current_user
        from app import (Material, PurchaseOrder, PurchaseOrderItem,
                         _find_or_create_material, _find_or_create_supplier,
                         _get_excel_cell, _get_excel_number, _import_result,
                         _order_no_from_row, _parse_excel_date, _read_import_sheet,
                         api_error, round_to_2_decimals, validate_excel_extension,
                         validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的采购单文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['采购单号', '单据编号', '订单编号'],
            'date': ['日期', '采购日期'],
            'supplier': ['供应商'],
            'expected_date': ['预计到货', '预计到货日期', '期望到货'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量', '采购数量'],
            'price': ['单价', '价格'],
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
                order_no = _order_no_from_row(row, col_map, 'order_no', 'PO')
                order = orders_by_no.get(order_no)
                if not order:
                    if PurchaseOrder.query.filter_by(order_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：采购单号 {order_no} 已存在')
                        continue
                    supplier_name = _get_excel_cell(row, col_map, 'supplier')
                    supplier = _find_or_create_supplier(supplier_name)
                    order = PurchaseOrder(
                        order_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        supplier_id=supplier.id if supplier else None,
                        expected_date=_parse_excel_date(_get_excel_cell(row, col_map, 'expected_date'), None) if _get_excel_cell(row, col_map, 'expected_date') else None,
                        status='pending',
                        remark=_get_excel_cell(row, col_map, 'remark'),
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
                order.total_amount = round_to_2_decimals((order.total_amount or 0) + amount)
                db.session.add(PurchaseOrderItem(
                    purchase_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    received_quantity=0,
                    price=price,
                    amount=amount,
                    remark=_get_excel_cell(row, col_map, 'remark'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('采购单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购单导入失败: {e}')
            return api_error(f'采购单导入失败：{str(e)}')

    @app.route('/purchase_order/add')
    @login_required
    def purchase_order_add_page():
        from datetime import datetime
        from sqlalchemy.orm import joinedload
        from app import (Material, Supplier, generate_order_no, serialize_material,
                         serialize_supplier)
        materials = Material.query.options(joinedload(Material.unit)).order_by(Material.code.asc(), Material.id.asc()).all()
        suppliers = Supplier.query.order_by(Supplier.code.asc(), Supplier.id.asc()).all()
        order_no = generate_order_no('PO')
        order_date = datetime.now().strftime('%Y-%m-%d')
        return render_template(
            'purchase_order_add.html',
            order=None,
            order_id=None,
            order_no=order_no,
            order_date=order_date,
            expected_date='',
            materials=[serialize_material(material) for material in materials],
            suppliers=[serialize_supplier(supplier) for supplier in suppliers],
            page_title='新增采购订单',
        )

    @app.route('/purchase_order/<int:id>/edit')
    @login_required
    def purchase_order_edit_page(id):
        from datetime import datetime
        from sqlalchemy.orm import joinedload
        from app import (Material, PurchaseOrder, PurchaseOrderItem, Supplier,
                         serialize_material, serialize_supplier)
        order = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material).joinedload(Material.unit),
        ).get_or_404(id)
        if order.status != 'pending':
            flash('只有未入库的采购单可以编辑。', 'warning')
            return redirect(url_for('purchase_order_detail', id=id))
        materials = Material.query.options(joinedload(Material.unit)).order_by(Material.code.asc(), Material.id.asc()).all()
        suppliers = Supplier.query.order_by(Supplier.code.asc(), Supplier.id.asc()).all()
        return render_template(
            'purchase_order_add.html',
            order=order,
            order_id=order.id,
            order_no=order.order_no,
            order_date=order.date.strftime('%Y-%m-%d') if order.date else datetime.now().strftime('%Y-%m-%d'),
            expected_date=order.expected_date.strftime('%Y-%m-%d') if order.expected_date else '',
            materials=[serialize_material(material) for material in materials],
            suppliers=[serialize_supplier(supplier) for supplier in suppliers],
            page_title='编辑采购单',
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/save', methods=['POST'])
    @require_role('purchase')
    @login_required
    def save_purchase_order():
        from datetime import date
        from flask_login import current_user
        from app import (Material, PurchaseOrder, PurchaseOrderItem, Supplier,
                         _find_or_create_supplier, api_error, generate_order_no,
                         log_operation, parse_date_value, parse_float_value,
                         round_to_2_decimals)
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

            order_no = (data.get('order_no') or '').strip() or generate_order_no('PO')
            order_date = parse_date_value(data.get('date'), date.today())
            if not order_date:
                return api_error('采购日期格式不正确，请重新选择日期')
            expected_date = parse_date_value(data.get('expected_date'))
            supplier_id = data.get('supplier_id')
            supplier_name = (data.get('supplier_name') or '').strip()
            try:
                supplier_id = int(supplier_id) if supplier_id not in (None, '', 'null', 'None') else None
            except (TypeError, ValueError):
                supplier_id = None
            supplier = db.session.get(Supplier, supplier_id) if supplier_id else None
            if supplier_id and not supplier:
                return api_error('请选择有效的供应商')
            if not supplier and supplier_name:
                supplier = _find_or_create_supplier(supplier_name)
                supplier_id = supplier.id if supplier else None
            remark = (data.get('remark') or '').strip()
            contract_id = data.get('contract_id')
            contract_no = (data.get('contract_no') or '').strip()
            project_name = (data.get('project_name') or '').strip()

            if order_id:
                order = db.session.get(PurchaseOrder, order_id)
                if not order:
                    return api_error('采购单不存在，请刷新后重试')
                if order.status != 'pending':
                    return api_error('只有未入库的采购单可以编辑')
            else:
                order = PurchaseOrder.query.filter_by(order_no=order_no).first()
                if order:
                    return api_error('采购单号已存在，不能重复保存')
                order = PurchaseOrder(order_no=order_no, status='pending', operator_id=current_user.id)
                db.session.add(order)
                db.session.flush()

            items_data = []
            if isinstance(payload, dict):
                items_data = payload.get('items', []) or []
            elif request.form.get('items'):
                try:
                    items_data = json.loads(request.form.get('items', '[]'))
                except json.JSONDecodeError:
                    items_data = []
            valid_items = []
            for item_data in items_data:
                if not isinstance(item_data, dict):
                    continue
                material_code = (item_data.get('material_code') or item_data.get('code') or '').strip()
                if item_data.get('material_id') or material_code:
                    valid_items.append(item_data)
            if not valid_items:
                return api_error('请至少添加一条采购明细')

            for existing_item in list(order.items):
                db.session.delete(existing_item)
            db.session.flush()

            order.order_no = order_no
            order.date = order_date
            order.expected_date = expected_date
            order.supplier_id = supplier_id
            order.remark = remark
            order.contract_id = int(contract_id) if contract_id else None
            order.contract_no = contract_no or None
            order.project_name = project_name or None

            order_total = 0
            for item_data in valid_items:
                material_id = item_data.get('material_id')
                material_code = (item_data.get('material_code') or item_data.get('code') or '').strip()
                material = None
                if material_id:
                    try:
                        material = db.session.get(Material, int(material_id))
                    except (TypeError, ValueError):
                        material = None
                if not material and material_code:
                    material = Material.query.filter_by(code=material_code).first()
                if not material:
                    db.session.rollback()
                    return api_error(f'物料 {material_code or material_id or ""} 不存在')

                quantity = round_to_2_decimals(parse_float_value(item_data.get('quantity'), 0))
                if quantity <= 0:
                    db.session.rollback()
                    return api_error(f'物料 {material.code} 的数量必须大于0')
                price = round_to_2_decimals(parse_float_value(item_data.get('price'), material.price or 0))
                amount = round_to_2_decimals(quantity * price)
                order_total += amount
                db.session.add(PurchaseOrderItem(
                    purchase_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    received_quantity=0,
                    price=price,
                    amount=amount,
                    remark=(item_data.get('remark') or '').strip(),
                    contract_id=int(item_data.get('contract_id')) if item_data.get('contract_id') else None,
                    contract_no=(item_data.get('contract_no') or '').strip() or None,
                    project_name=(item_data.get('project_name') or '').strip() or None,
                ))

            order.total_amount = round_to_2_decimals(order_total)
            order.status = 'pending'
            db.session.commit()
            log_operation('保存采购单', f'采购单：{order.order_no}', 'purchase_order', order.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': order.id, 'order_no': order.order_no})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存采购单失败: {e}')
            return api_error('保存失败，请稍后重试')

    @app.route('/purchase_order/<int:id>')
    @login_required
    def purchase_order_detail(id):
        from sqlalchemy.orm import joinedload
        from app import (InOrder, InOrderItem, Material, PurchaseOrder, PurchaseOrderItem,
                         build_purchase_order_execution, get_active_warehouses,
                         get_recent_operation_logs, purchase_order_status_label)
        order = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.purchase_request),
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material).joinedload(Material.unit),
        ).get_or_404(id)
        item_ids = [item.id for item in order.items]
        related_query = InOrder.query.outerjoin(InOrderItem, InOrderItem.in_order_id == InOrder.id).filter(
            db.or_(
                InOrder.source_purchase_order_id == order.id,
                InOrderItem.source_purchase_order_item_id.in_(item_ids) if item_ids else False,
            )
        ).distinct()
        related_in_orders = related_query.order_by(
            InOrder.date.desc(),
            InOrder.id.desc()
        ).all()
        warehouses = get_active_warehouses()
        item_execution = build_purchase_order_execution(order)
        return render_template(
            'purchase_order_detail.html',
            order=order,
            related_in_orders=related_in_orders,
            warehouses=warehouses,
            status_label=purchase_order_status_label,
            item_execution=item_execution,
            operation_logs=get_recent_operation_logs('purchase_order', id),
        )

    @app.route('/purchase_order/<int:id>/print')
    @login_required
    def print_purchase_order(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, PurchaseOrder, PurchaseOrderItem, _fmt_date,
                         _material_row_common, _operator_name,
                         _render_generic_document_print, purchase_order_status_label,
                         round_to_2_decimals)
        order = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrder.purchase_request),
            joinedload(PurchaseOrder.operator),
            selectinload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material).joinedload(Material.unit),
        ).get_or_404(id)
        rows = [
            _material_row_common(
                item,
                extra={
                    'received_quantity': item.received_quantity or 0,
                    'remaining_quantity': round_to_2_decimals((item.quantity or 0) - (item.received_quantity or 0)),
                }
            )
            for item in order.items
        ]
        return _render_generic_document_print({
            'title': '采购订单',
            'subtitle': 'PURCHASE ORDER',
            'number_label': '采购单号',
            'number': order.order_no,
            'date_label': '采购日期',
            'date': _fmt_date(order.date),
            'status': order.status,
            'status_label': purchase_order_status_label(order.status),
            'info': [
                ('供应商', order.supplier.name if order.supplier else ''),
                ('预计到货', _fmt_date(order.expected_date)),
                ('来源申请', order.purchase_request.request_no if order.purchase_request else ''),
                ('制单人', _operator_name(order)),
                ('创建时间', _fmt_date(order.created_at)),
                ('总金额', f'{order.total_amount or 0:.2f}'),
            ],
            'remark': order.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '采购数量', 'right'),
                ('received_quantity', '已入库', 'right'),
                ('remaining_quantity', '未入库', 'right'),
                ('price', '单价', 'right money'),
                ('amount', '金额', 'right money'),
                ('remark', '备注', ''),
            ],
            'rows': rows,
            'total_amount': order.total_amount or sum(row.get('amount', 0) or 0 for row in rows),
            'signatures': ['制单', '采购', '供应商', '仓库'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/create_in_order_from_selection', methods=['POST'])
    @require_role('warehouse', 'purchase')
    @login_required
    def create_in_order_from_purchase_order_selection():
        from datetime import date
        from flask_login import current_user
        from sqlalchemy.orm import joinedload
        from app import (InOrder, InOrderItem, PurchaseOrder, PurchaseOrderItem, api_error,
                         assert_warehouse_active, generate_order_no, get_default_warehouse,
                         log_operation, parse_float_value,
                         purchase_order_to_in_order_enabled, recalculate_order_total,
                         round_to_2_decimals, update_purchase_order_status,
                         validate_purchase_receive_quantity)
        if not purchase_order_to_in_order_enabled():
            return api_error('系统已关闭采购订单下推入库单')
        payload = request.get_json(silent=True) or {}
        selected_items = payload.get('items') or []
        if not isinstance(selected_items, list) or not selected_items:
            return api_error('请选择要转换的采购单明细')

        warehouse = (payload.get('warehouse') or '').strip()
        if not warehouse:
            warehouse = (get_default_warehouse() or '').strip()
        if not warehouse:
            return api_error('请选择仓库')
        # PUR-AUDIT-001 修复：assert_warehouse_active 返回 (ok, msg) 二元组，
        # 非空元组恒为真，导致 (True, '') 也触发拒绝，选单下推功能不可用。
        # 必须解构后按 ok 判断，仅在 not ok 时返回 msg。
        wh_ok, wh_msg = assert_warehouse_active(warehouse, allow_empty=False)
        if not wh_ok:
            return api_error(wh_msg)
        remark = (payload.get('remark') or '').strip()
        selected_qty_by_item_id = {}
        for row in selected_items:
            if not isinstance(row, dict):
                continue
            item_id = row.get('purchase_order_item_id') or row.get('item_id') or row.get('id')
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                continue
            quantity = round_to_2_decimals(parse_float_value(row.get('quantity'), 0))
            if quantity <= 0:
                continue
            selected_qty_by_item_id[item_id] = round_to_2_decimals(
                selected_qty_by_item_id.get(item_id, 0) + quantity
            )
        if not selected_qty_by_item_id:
            return api_error('请选择大于 0 的转换数量')

        source_items = PurchaseOrderItem.query.options(
            joinedload(PurchaseOrderItem.purchase_order).joinedload(PurchaseOrder.supplier),
            joinedload(PurchaseOrderItem.material),
        ).filter(PurchaseOrderItem.id.in_(selected_qty_by_item_id.keys())).all()
        if len(source_items) != len(selected_qty_by_item_id):
            return api_error('部分采购单明细不存在，请刷新后重试')

        supplier_ids = set()
        purchase_order_ids = set()
        conversion_items = []
        for item in source_items:
            order = item.purchase_order
            if not order or order.status not in ('pending', 'partial'):
                return api_error('只能选择未入库或部分入库的采购单明细')
            receive_qty = selected_qty_by_item_id[item.id]
            material_code = item.material.code if item.material else item.material_id
            valid_qty, qty_msg = validate_purchase_receive_quantity(item, receive_qty, material_code)
            if not valid_qty:
                return api_error(qty_msg)
            supplier_ids.add(order.supplier_id or 0)
            purchase_order_ids.add(order.id)
            conversion_items.append((item, order, receive_qty))
        if len(supplier_ids) > 1:
            return api_error('采购入库单只能选择同一供应商的采购单明细')

        try:
            purchase_order_nos = sorted({order.order_no for _, order, _ in conversion_items})
            in_order = InOrder(
                order_no=generate_order_no('IN'),
                date=date.today(),
                supplier_id=(next(iter(supplier_ids)) or None),
                business_type='采购入库',
                purpose='选单生成采购入库',
                warehouse=warehouse,
                source_purchase_order_id=next(iter(purchase_order_ids)) if len(purchase_order_ids) == 1 else None,
                remark=remark or ('由采购单选单生成：' + '、'.join(purchase_order_nos)),
                status='pending',
                operator_id=current_user.id,
            )
            db.session.add(in_order)
            db.session.flush()

            affected_orders = set()
            for item, order, receive_qty in conversion_items:
                price = round_to_2_decimals(item.price or (item.material.price if item.material else 0) or 0)
                db.session.add(InOrderItem(
                    in_order_id=in_order.id,
                    material_id=item.material_id,
                    source_purchase_order_item_id=item.id,
                    quantity=receive_qty,
                    price=price,
                    amount=round_to_2_decimals(receive_qty * price),
                ))
                item.received_quantity = round_to_2_decimals((item.received_quantity or 0) + receive_qty)
                affected_orders.add(order)

            recalculate_order_total(in_order)
            for order in affected_orders:
                update_purchase_order_status(order)
            db.session.commit()
            log_operation('采购单选单生成采购入库单', f'{", ".join(purchase_order_nos)} -> {in_order.order_no}', 'in_order', in_order.id)
            return jsonify({
                'status': 'success',
                'msg': '采购入库单生成成功',
                'id': in_order.id,
                'order_no': in_order.order_no,
                'redirect_url': url_for('in_order_detail', id=in_order.id),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购单选单生成采购入库单失败: {e}')
            return api_error('生成采购入库单失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/<int:id>/copy', methods=['POST'])
    @require_role('purchase')
    @login_required
    def copy_purchase_order(id):
        from datetime import date
        from flask_login import current_user
        from sqlalchemy.orm import joinedload
        from app import (PurchaseOrder, PurchaseOrderItem, api_error, generate_order_no,
                         log_operation, round_to_2_decimals)
        source = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material),
        ).get_or_404(id)
        if not source.items:
            return api_error('原采购单没有明细，不能复制')
        try:
            new_order = PurchaseOrder(
                order_no=generate_order_no('PO'),
                date=date.today(),
                supplier_id=source.supplier_id,
                expected_date=None,
                purchase_request_id=None,
                status='pending',
                remark=f'由采购单 {source.order_no} 复制生成',
                operator_id=current_user.id,
                total_amount=0,
            )
            db.session.add(new_order)
            db.session.flush()
            total_amount = 0
            for item in source.items:
                quantity = round_to_2_decimals(item.quantity or 0)
                if quantity <= 0:
                    continue
                price = round_to_2_decimals(item.price or 0)
                amount = round_to_2_decimals(quantity * price)
                total_amount += amount
                db.session.add(PurchaseOrderItem(
                    purchase_order_id=new_order.id,
                    material_id=item.material_id,
                    purchase_request_item_id=None,
                    quantity=quantity,
                    received_quantity=0,
                    price=price,
                    amount=amount,
                    remark=item.remark,
                ))
            if total_amount <= 0:
                db.session.rollback()
                return api_error('原采购单没有有效数量，不能复制')
            new_order.total_amount = round_to_2_decimals(total_amount)
            db.session.commit()
            log_operation('复制采购单', f'{source.order_no} -> {new_order.order_no}', 'purchase_order', new_order.id)
            return jsonify({
                'status': 'success',
                'msg': '复制成功',
                'id': new_order.id,
                'order_no': new_order.order_no,
                'redirect_url': url_for('purchase_order_edit_page', id=new_order.id),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'复制采购单失败: {e}')
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/<int:id>/create_in_order', methods=['POST'])
    @require_role('warehouse', 'purchase')
    @login_required
    def create_in_order_from_purchase_order(id):
        from sqlalchemy.orm import joinedload
        from app import (PurchaseOrder, PurchaseOrderItem, _create_in_order_from_purchase_order_core,
                         api_error, parse_float_value, round_to_2_decimals)
        order = PurchaseOrder.query.options(
            joinedload(PurchaseOrder.items).joinedload(PurchaseOrderItem.material),
            joinedload(PurchaseOrder.supplier),
        ).get_or_404(id)

        payload = request.get_json(silent=True) or request.form
        warehouse = (payload.get('warehouse') or '').strip()
        remark = (payload.get('remark') or '').strip()
        submitted_items = payload.get('items') if isinstance(payload, dict) else None

        try:
            submitted_qty_by_id = None
            if isinstance(submitted_items, list):
                submitted_qty_by_id = {}
                for row in submitted_items:
                    if not isinstance(row, dict):
                        continue
                    item_id = row.get('item_id') or row.get('id')
                    try:
                        item_id = int(item_id)
                    except (TypeError, ValueError):
                        continue
                    submitted_qty_by_id[item_id] = round_to_2_decimals(parse_float_value(row.get('quantity'), 0))
                if not submitted_qty_by_id:
                    return api_error('请选择要下推入库的采购明细')
            in_order, error = _create_in_order_from_purchase_order_core(
                order,
                warehouse=warehouse,
                remark=remark,
                submitted_qty_by_id=submitted_qty_by_id,
            )
            if error:
                return api_error(error)
            return jsonify({
                'status': 'success',
                'msg': '采购入库单生成成功',
                'id': in_order.id,
                'order_no': in_order.order_no,
                'redirect_url': url_for('in_order_detail', id=in_order.id)
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'采购单下推入库单失败: {e}')
            return api_error('生成采购入库单失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/<int:id>/close', methods=['POST'])
    @require_role('purchase')
    @login_required
    def close_purchase_order(id):
        from app import PurchaseOrder, api_error, log_operation
        order = PurchaseOrder.query.get_or_404(id)
        if order.status not in ('pending', 'partial'):
            return api_error('只有未入库或部分入库的采购单可以关闭')
        payload = request.get_json(silent=True) or request.form
        reason = (payload.get('reason') or '').strip()
        try:
            order.status = 'closed'
            if reason:
                order.remark = ((order.remark or '') + f'\n关闭原因：{reason}').strip()
            db.session.commit()
            log_operation('关闭采购单', f'采购单：{order.order_no}', 'purchase_order', order.id)
            return jsonify({'status': 'success', 'msg': '采购单已关闭'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'关闭采购单失败: {e}')
            return api_error('关闭失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/<int:id>/reopen', methods=['POST'])
    @require_role('purchase')
    @login_required
    def reopen_purchase_order(id):
        from app import PurchaseOrder, api_error, log_operation, update_purchase_order_status
        order = PurchaseOrder.query.get_or_404(id)
        if order.status != 'closed':
            return api_error('只有已关闭的采购单可以重新打开')
        try:
            order.status = 'pending'
            update_purchase_order_status(order)
            db.session.commit()
            log_operation('重新打开采购单', f'采购单：{order.order_no}', 'purchase_order', order.id)
            return jsonify({'status': 'success', 'msg': '采购单已重新打开', 'status': order.status})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'重新打开采购单失败: {e}')
            return api_error('重新打开失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/<int:id>/delete', methods=['POST'])
    @require_role('purchase')
    @login_required
    def delete_purchase_order(id):
        from sqlalchemy.orm import joinedload
        from app import (InOrder, PurchaseOrder, PurchaseOrderItem, api_error,
                         has_inbound_reference, log_operation)
        order = PurchaseOrder.query.options(joinedload(PurchaseOrder.items)).get_or_404(id)
        if order.status != 'pending':
            return api_error('只有未入库的采购单可以删除')
        # PUR-AUDIT-002：同时检查表头和行级来源，防止多来源选单入库被遗漏
        if has_inbound_reference(order.id):
            return api_error('该采购单已有下游入库单，不能删除')
        try:
            order_no = order.order_no
            for item in list(order.items):
                db.session.delete(item)
            db.session.delete(order)
            db.session.commit()
            log_operation('删除采购单', f'采购单：{order_no}', 'purchase_order', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'删除采购单失败: {e}')
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/purchase_order/batch_delete', methods=['POST'])
    @require_role('purchase')
    @login_required
    def batch_delete_purchase_order():
        from sqlalchemy.orm import joinedload
        from app import (InOrder, PurchaseOrder, PurchaseOrderItem, api_error,
                         has_inbound_reference, log_operation,
                         purchase_order_status_label)
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的采购单')

        orders = PurchaseOrder.query.options(joinedload(PurchaseOrder.items)).filter(PurchaseOrder.id.in_(ids)).all()
        blocked = []
        delete_orders = []
        for order in orders:
            if order.status != 'pending':
                blocked.append(f'{order.order_no}（{purchase_order_status_label(order.status)}）')
                continue
            # PUR-AUDIT-002：同时检查表头和行级来源，防止多来源选单入库被遗漏
            if has_inbound_reference(order.id):
                blocked.append(f'{order.order_no}（已有入库单）')
                continue
            delete_orders.append(order)
        if blocked:
            return api_error('以下采购单不能删除：' + '、'.join(blocked))

        try:
            deleted = 0
            for order in delete_orders:
                for item in list(order.items):
                    db.session.delete(item)
                db.session.delete(order)
                deleted += 1
            db.session.commit()
            log_operation('批量删除采购单', f'共删除 {deleted} 张采购单', 'purchase_order')
            return jsonify({'status': 'success', 'msg': f'删除成功，共删除 {deleted} 张采购单'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除采购单失败: {e}')
            return api_error('删除失败，请稍后重试')