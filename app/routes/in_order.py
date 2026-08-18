#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 采购入库（in_order）域路由。
#
# 批量拆分模式：与销售（sales）/领料（requisition）/出库（out_order）域一致，
# 采用「register_in_order_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 in_order_list、in_order_detail、add_in_order、complete_in_order 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（InOrder 模型、InOrderItem、InOrderPrintTemplate、Material、
#   Supplier、Customer、PurchaseOrder、PurchaseOrderItem、OutOrder、OutOrderItem、
#   AfterSaleOutOrder、AfterSaleOutOrderItem、OperationLog、DocumentPushLine、
#   WechatShareConfig、Unit、INBOUND_PUSH_TARGETS、STOCK_COMPARE_EPSILON、
#   各辅助函数 api_error / generate_order_no / log_operation / parse_float_value /
#   round_to_2_decimals / normalize_stock_quantity / get_active_warehouses /
#   get_default_warehouse / validate_purchase_receive_quantity /
#   purchase_in_order_requires_order / in_order_duplicate_material_mode /
#   find_duplicate_in_order_item / is_purchase_in_order /
#   should_block_purchase_over_receive / update_purchase_order_status /
#   assert_warehouse_active / is_future_date / parse_date_value / _clean_int /
#   _acquire_order_write_lock / _source_has_active_push / _in_order_push_quantities /
#   _in_order_push_source_type / _in_order_push_history / _push_target_url /
#   _check_in_order_anomalies / _ai_llm_configured / _ai_call_llm_chat /
#   _wechat_share_order / add_stock / deduct_stock / deduct_stock_atomic /
#   update_location_inventory / location_management_enabled / allow_negative_stock /
#   check_stock_sufficient / is_stock_sufficient / recalculate_order_total /
#   get_default_print_template / _render_html_print_content / create_print_template /
#   set_default_print_template / delete_print_template /
#   _print_template_query_from_args / build_purchase_order_execution /
#   get_recent_operation_logs / serialize_material / serialize_unit /
#   serialize_customer / serialize_supplier 等）在各路由函数内延迟导入
#   （请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_in_order_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json
import math

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from db import db
from utils import print_token_or_login_required, require_role


# no-test:reason=路由注册辅助函数，能力由 in_order_* 各路由测试覆盖
def register_in_order_routes(app):
    @app.route('/in_order')
    @app.route('/other_in_order')
    @login_required
    def in_order_list():
        from sqlalchemy.orm import joinedload
        from app import (InOrder, InOrderItem, Material, PurchaseOrderItem, Supplier,
                         _apply_header_or_item_contract_filters, _apply_in_order_search,
                         _apply_status_date_filters, _get_order_list_filters,
                         get_active_warehouses, get_default_warehouse,
                         purchase_order_status_label, resolve_request_warehouse)
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        # 支持 ?type=purchase_in / ?type=product_in 英文简写参数，
        # 避免中文参数在 URL 中未经编码导致 Waitress Bad Request。
        # 同时向后兼容 ?business_type=采购入库（经正确编码的请求）。
        _type_alias = {
            'purchase_in': '采购入库',
            'product_in': '产品入库',
            'other_in': '其他入库',
        }
        business_type_filter = ''
        raw_type = 'other_in' if request.path == '/other_in_order' else (request.args.get('type') or '').strip()
        if raw_type in _type_alias:
            business_type_filter = _type_alias[raw_type]
        else:
            business_type_filter = (request.args.get('business_type') or '').strip()
            if business_type_filter not in ('采购入库', '产品入库', '其他入库'):
                business_type_filter = ''
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'order_no', 'date', 'supplier_id', 'business_type', 'purpose', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        sort_col = getattr(InOrder, sort_by, InOrder.created_at)
        # 按单据左连接明细展示，待完成但没有明细的单据也能查到。
        query = db.session.query(InOrder, InOrderItem).outerjoin(InOrderItem, InOrderItem.in_order_id == InOrder.id).options(
            joinedload(InOrder.supplier),
            joinedload(InOrder.customer),
            joinedload(InOrder.source_purchase_order),
            joinedload(InOrderItem.material).joinedload(Material.unit),
            joinedload(InOrderItem.source_purchase_order_item).joinedload(PurchaseOrderItem.purchase_order),
        )
        query = _apply_status_date_filters(query, InOrder, status_filter, date_start, date_end)
        warehouse, warehouse_error = resolve_request_warehouse(request.args)
        if warehouse:
            query = query.filter(InOrder.warehouse == warehouse.name)
        elif warehouse_error:
            query = query.filter(db.false())
        if business_type_filter:
            query = query.filter(InOrder.business_type == business_type_filter)
        query = _apply_in_order_search(query, search)
        contract_no_filter = (request.args.get('contract_no') or '').strip()
        project_name_filter = (request.args.get('project_name') or '').strip()
        query = _apply_header_or_item_contract_filters(
            query, InOrder, InOrderItem, 'in_order_id',
            contract_no_filter=contract_no_filter,
            project_name_filter=project_name_filter,
        )
        if sort_order == 'asc':
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        items = [
            type('InOrderListRow', (), {
                'in_order': order,
                'material': item.material if item else None,
                'source_purchase_order': (
                    item.source_purchase_order_item.purchase_order
                    if item and item.source_purchase_order_item and item.source_purchase_order_item.purchase_order
                    else order.source_purchase_order
                ),
                'quantity': item.quantity if item else 0,
                'price': item.price if item else 0,
                'amount': item.amount if item else 0,
                'contract_no': item.contract_no if item else '',
                'project_name': item.project_name if item else '',
            })()
            for order, item in pagination.items
        ]
        suppliers = Supplier.query.all()
        # 反向映射：中文业务类型 -> 英文 URL 参数，供模板生成分页/清除链接
        _type_reverse = {'采购入库': 'purchase_in', '产品入库': 'product_in', '其他入库': 'other_in'}
        filters = {
            'status': status_filter,
            'search': search,
            'business_type': business_type_filter,
            'type_param': _type_reverse.get(business_type_filter, ''),
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'contract_no': contract_no_filter,
            'project_name': project_name_filter,
            'warehouse_id': warehouse.id if warehouse else '',
        }
        page_title = f'{business_type_filter}明细' if business_type_filter else '采购入库单'
        return render_template(
            'in_order.html',
            items=items,
            suppliers=suppliers,
            pagination=pagination,
            sort_by=sort_by,
            sort_order=sort_order,
            per_page=per_page,
            filters=filters,
            page_title=page_title,
            purchase_order_status_label=purchase_order_status_label,
            warehouses=get_active_warehouses(),
            default_warehouse=get_default_warehouse(),
        )

    @app.route('/in_order/<int:id>')
    @login_required
    def in_order_detail(id):
        from datetime import date
        from sqlalchemy.orm import joinedload
        from app import (Customer, InOrder, InOrderItem, Material, PurchaseOrderItem,
                         Supplier, _in_order_push_history, _in_order_push_source_type,
                         build_purchase_order_execution, get_active_warehouses,
                         get_default_warehouse, get_recent_operation_logs,
                         location_management_enabled)
        order = InOrder.query.options(
            joinedload(InOrder.supplier),
            joinedload(InOrder.source_purchase_order),
            joinedload(InOrder.items).joinedload(InOrderItem.material).joinedload(Material.unit),
            joinedload(InOrder.items).joinedload(InOrderItem.source_purchase_order_item).joinedload(PurchaseOrderItem.purchase_order),
        ).get_or_404(id)
        source_purchase_orders = {}
        for item in order.items:
            source_item = item.source_purchase_order_item
            if source_item and source_item.purchase_order:
                source_purchase_orders[source_item.purchase_order.id] = source_item.purchase_order
        purchase_order_execution = {
            purchase_order_id: build_purchase_order_execution(purchase_order)
            for purchase_order_id, purchase_order in source_purchase_orders.items()
        }
        suppliers = Supplier.query.order_by(Supplier.name.asc(), Supplier.id.asc()).all()
        customers = Customer.query.order_by(Customer.name.asc(), Customer.id.asc()).all()
        warehouses = get_active_warehouses()
        warehouse_names = [warehouse.name for warehouse in warehouses]
        default_warehouse = get_default_warehouse()
        return render_template(
            'in_order_detail.html',
            order=order,
            suppliers=suppliers,
            push_history=_in_order_push_history(order),
            can_push=order.status == 'completed' and _in_order_push_source_type(order) is not None,
            customers=customers,
            warehouses=warehouses,
            warehouse_names=warehouse_names,
            default_warehouse=default_warehouse,
            location_management_enabled=location_management_enabled(),
            purchase_order_execution=purchase_order_execution,
            today=date.today(),
            operation_logs=get_recent_operation_logs('in_order', id),
        )

    @app.route('/in_order/<int:id>/push')
    @require_role('warehouse')
    @login_required
    def in_order_push_page(id):
        from sqlalchemy.orm import joinedload
        from app import (Customer, Department, INBOUND_PUSH_TARGETS, InOrder, InOrderItem, Material,
                         _in_order_push_quantities, _in_order_push_source_type,
                         normalize_stock_quantity)
        order = InOrder.query.options(
            joinedload(InOrder.items).joinedload(InOrderItem.material).joinedload(Material.unit)
        ).get_or_404(id)
        if order.status != 'completed':
            flash('仅已完成的采购入库单或其他入库单允许下推。', 'warning')
            return redirect(url_for('in_order_detail', id=id))
        if not _in_order_push_source_type(order):
            flash('当前入库业务类型不支持下推出库类单据。', 'warning')
            return redirect(url_for('in_order_detail', id=id))
        pushed = _in_order_push_quantities(order)
        lines = []
        for item in order.items:
            pushed_quantity = pushed.get(item.id, 0)
            is_customer_supplied = bool(item.is_customer_supplied)
            lines.append({
                'item': item,
                'in_quantity': normalize_stock_quantity(item.quantity or 0),
                'pushed_quantity': pushed_quantity,
                'available_quantity': 0 if is_customer_supplied else max(0, normalize_stock_quantity((item.quantity or 0) - pushed_quantity)),
                'is_customer_supplied': is_customer_supplied,
            })
        return render_template(
            'in_order_push.html', order=order, lines=lines,
            target_types=INBOUND_PUSH_TARGETS, customers=Customer.query.order_by(Customer.code.asc()).all(),
            departments=Department.query.filter_by(status='active').order_by(Department.code.asc(), Department.id.asc()).all(),
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/push', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def create_in_order_push(id):
        from datetime import date
        import math
        from flask_login import current_user
        from sqlalchemy.orm import selectinload
        from app import (AfterSaleOutOrder, AfterSaleOutOrderItem, Customer,
                         Department, DocumentPushLine, INBOUND_PUSH_TARGETS,
                         InOrder, OperationLog, OutOrder, OutOrderItem,
                         _acquire_order_write_lock, _clean_int,
                         _in_order_push_quantities, _in_order_push_source_type,
                         _push_target_url, generate_order_no, normalize_stock_quantity,
                         round_to_2_decimals)
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'status': 'error', 'msg': '请求数据格式不正确'}), 400
        target_type = (payload.get('target_type') or '').strip()
        request_id = (payload.get('request_id') or '').strip()
        if target_type not in INBOUND_PUSH_TARGETS:
            return jsonify({'status': 'error', 'msg': '请选择有效的下推目标单据'}), 400
        if not request_id or len(request_id) > 100:
            return jsonify({'status': 'error', 'msg': '请求编号不能为空或过长'}), 400

        existing = DocumentPushLine.query.filter_by(
            created_by=current_user.id, source_document_id=id, request_id=request_id
        ).filter(DocumentPushLine.source_document_type.in_(('purchase_in_order', 'other_in_order'))).first()
        if existing:
            return jsonify({
                'status': 'success', 'msg': '该请求已处理，未重复创建草稿',
                'id': existing.target_document_id,
                'order_no': existing.target_document_no,
                'url': _push_target_url(existing.target_document_type, existing.target_document_id),
                'replayed': True,
            })

        raw_items = payload.get('items')
        if not isinstance(raw_items, list) or not raw_items:
            return jsonify({'status': 'error', 'msg': '请至少选择一条可下推明细'}), 400
        try:
            requested = {}
            for raw in raw_items:
                item_id = int(raw.get('source_item_id'))
                quantity = float(raw.get('quantity'))
                if not math.isfinite(quantity) or quantity <= 0:
                    raise ValueError
                if item_id in requested:
                    return jsonify({'status': 'error', 'msg': f'来源明细 {item_id} 重复提交'}), 400
                requested[item_id] = normalize_stock_quantity(quantity)
        except (TypeError, ValueError, OverflowError):
            return jsonify({'status': 'error', 'msg': '下推数量必须是大于 0 的有效数字'}), 400

        try:
            locked, ok = _acquire_order_write_lock(InOrder, id, 'completed', selectinload(InOrder.items))
            if not ok:
                return jsonify({'status': 'error', 'msg': '来源单状态已变化，仅已完成单据允许下推'}), 409
            order = locked
            source_type = _in_order_push_source_type(order)
            if not source_type:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': '仅采购入库单和其他入库单允许下推'}), 400
            duplicate = DocumentPushLine.query.filter_by(
                created_by=current_user.id, source_document_type=source_type,
                source_document_id=id, request_id=request_id,
            ).first()
            if duplicate:
                db.session.rollback()
                return jsonify({
                    'status': 'success', 'msg': '该请求已处理，未重复创建草稿',
                    'id': duplicate.target_document_id, 'order_no': duplicate.target_document_no,
                    'url': _push_target_url(duplicate.target_document_type, duplicate.target_document_id),
                    'replayed': True,
                })

            source_items = {item.id: item for item in order.items}
            pushed = _in_order_push_quantities(order)
            selected = []
            for item_id, quantity in requested.items():
                item = source_items.get(item_id)
                if not item:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': f'来源明细 {item_id} 不属于当前入库单'}), 400
                if item.is_customer_supplied:
                    code = item.material.code if item.material else str(item.material_id)
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': f'物料 {code} 为客供料；当前系统尚未完成客供料所有权库存隔离，不能下推为普通出库单。'}), 409
                source_quantity = normalize_stock_quantity(item.quantity or 0)
                used_quantity = pushed.get(item_id, 0)
                available = max(0, normalize_stock_quantity(source_quantity - used_quantity))
                if quantity > available + 1e-6:
                    code = item.material.code if item.material else str(item.material_id)
                    db.session.rollback()
                    return jsonify({
                        'status': 'error',
                        'msg': f'物料 {code} 超出可下推数量：入库 {source_quantity:g}，已下推 {used_quantity:g}，可下推 {available:g}，本次 {quantity:g}',
                    }), 409
                selected.append((item, quantity))

            target_definition = INBOUND_PUSH_TARGETS[target_type]
            source_label = '采购入库单' if source_type == 'purchase_in_order' else '其他入库单'
            remark = f'由{source_label} {order.order_no} 下推生成'
            target_items = []
            if target_type in ('requisition', 'other_out'):
                if target_type == 'requisition':
                    department_id = _clean_int(payload.get('department_id'))
                    department = db.session.get(Department, department_id) if department_id else None
                else:
                    department = None
                target = OutOrder(
                    # Both outbound business types share the proven OU sequence;
                    # business_type, not an untracked prefix, distinguishes them.
                    order_no=generate_order_no('OUT'),
                    date=date.today(), business_type=target_definition['business_type'],
                    warehouse=order.warehouse, purpose=(payload.get('purpose') or '').strip() or None,
                    picker=(payload.get('picker') or '').strip() or None,
                    department_id=department.id if department else None,
                    customer=(payload.get('party') or '').strip() or None,
                    status='pending', operator_id=current_user.id, remark=remark,
                )
                if target_type == 'other_out' and not target.purpose:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': '下推其他出库单必须填写出库原因或用途'}), 400
                db.session.add(target)
                db.session.flush()
                for source_item, quantity in selected:
                    price = round_to_2_decimals(source_item.material.price or 0) if source_item.material else 0
                    target_item = OutOrderItem(
                        out_order_id=target.id, material_id=source_item.material_id,
                        quantity=quantity, price=price,
                        amount=round_to_2_decimals(quantity * price),
                        contract_id=source_item.contract_id, contract_no=source_item.contract_no,
                        project_name=source_item.project_name, remark=source_item.remark,
                    )
                    db.session.add(target_item)
                    db.session.flush()
                    target_items.append((source_item, quantity, target_item.id))
                target.total_amount = round_to_2_decimals(sum(quantity * (source_item.material.price or 0) for source_item, quantity in selected))
            else:
                customer_id = _clean_int(payload.get('customer_id'))
                customer = db.session.get(Customer, customer_id) if customer_id else None
                if not customer:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': '下推售后出库单必须选择有效客户'}), 400
                reason = (payload.get('reason') or '').strip()
                if not reason:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': '下推售后出库单必须填写售后原因'}), 400
                target = AfterSaleOutOrder(
                    order_no=generate_order_no('ASO'), date=date.today(), customer_id=customer.id,
                    customer=customer.name, contact=customer.contact, phone=customer.phone,
                    warehouse=order.warehouse, reason=reason, remark=remark,
                    status='pending', operator_id=current_user.id,
                )
                db.session.add(target)
                db.session.flush()
                for source_item, quantity in selected:
                    price = round_to_2_decimals(source_item.material.price or 0) if source_item.material else 0
                    target_item = AfterSaleOutOrderItem(
                        after_sale_out_order_id=target.id, material_id=source_item.material_id,
                        quantity=quantity, price=price,
                        amount=round_to_2_decimals(quantity * price),
                        contract_id=source_item.contract_id, contract_no=source_item.contract_no,
                        project_name=source_item.project_name, remark=source_item.remark,
                    )
                    db.session.add(target_item)
                    db.session.flush()
                    target_items.append((source_item, quantity, target_item.id))
                target.total_amount = round_to_2_decimals(sum(quantity * (source_item.material.price or 0) for source_item, quantity in selected))

            for source_item, quantity, target_item_id in target_items:
                db.session.add(DocumentPushLine(
                    source_document_type=source_type, source_document_id=order.id,
                    source_document_no=order.order_no, source_item_id=source_item.id,
                    target_document_type=target_type, target_document_id=target.id,
                    target_document_no=target.order_no, target_item_id=target_item_id,
                    pushed_quantity=quantity, status='active', request_id=request_id,
                    created_by=current_user.id,
                ))
            db.session.add(OperationLog(
                user_id=current_user.id, operation_type='单据下推',
                operation_content=f'{source_label} {order.order_no} 下推{target_definition["label"]} {target.order_no}（草稿）',
                target_type=target_type, target_id=target.id, ip_address=request.remote_addr,
            ))
            db.session.commit()
            return jsonify({
                'status': 'success', 'msg': f'{target_definition["label"]}草稿创建成功，库存未发生变化',
                'id': target.id, 'order_no': target.order_no,
                'url': _push_target_url(target_type, target.id), 'replayed': False,
            })
        except Exception as exc:
            db.session.rollback()
            app.logger.exception('入库单下推失败: %s', exc)
            return jsonify({'status': 'error', 'msg': '下推失败，请稍后重试'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/update', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_in_order(id):
        """Update the header fields of a draft inbound order."""
        from app import (Customer, InOrder, Supplier, _clean_int, api_error, assert_warehouse_active,
                         get_default_warehouse, is_future_date, location_management_enabled,
                         log_operation, parse_date_value, recalculate_order_total)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有草稿状态的入库单可以编辑')

        payload = request.get_json(silent=True)
        data = payload if isinstance(payload, dict) else request.form

        order_date = parse_date_value(data.get('date'), None)
        if not order_date:
            return api_error('日期格式不正确，请重新选择日期')
        if is_future_date(order_date):
            return jsonify({'status': 'error', 'msg': '入库日期不能晚于今天'}), 400

        supplier_id = _clean_int(data.get('supplier_id'))
        if supplier_id:
            supplier = db.session.get(Supplier, supplier_id)
            if not supplier:
                return api_error('请选择有效的供应商')
            order.supplier_id = supplier.id
        else:
            order.supplier_id = None
        customer_id = _clean_int(data.get('customer_id'))
        if customer_id:
            customer = db.session.get(Customer, customer_id)
            if not customer:
                return api_error('请选择有效的客户')
            order.customer_id = customer.id
        else:
            order.customer_id = None

        business_type = (data.get('business_type') or order.business_type or '').strip()
        if business_type in ('采购入库', '产品入库', '其他入库'):
            order.business_type = business_type

        order.date = order_date
        order.purpose = (data.get('purpose') or '').strip()
        warehouse = (data.get('warehouse') or '').strip()
        # BUG-2026-08-02-001 修复：仓库是入库单必填字段，与库位管理是否启用无关。
        # 未填写时若开启“录单优先取默认仓库”，自动带入默认仓库。
        if not warehouse:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse:
            return jsonify({'status': 'error', 'msg': '请选择仓库'}), 400
        order.warehouse = warehouse
        # 库位管理启用时库位为必填（AGENTS.md 规则二）
        location = (data.get('location') or '').strip()
        if location_management_enabled() and not location:
            return jsonify({'status': 'error', 'msg': '请选择库位'}), 400
        order.location = location
        order.remark = (data.get('remark') or '').strip()
        # BUG-F02-04 / BUG-2026-08-02-001 修复：保存前校验仓库是否启用/存在
        ok, wh_msg = assert_warehouse_active(order.warehouse, allow_empty=False)
        if not ok:
            return jsonify({'status': 'error', 'msg': wh_msg}), 400
        recalculate_order_total(order)

        try:
            db.session.commit()
            log_operation('编辑入库单', f'入库单：{order.order_no}', 'in_order', id)
            return jsonify({'status': 'success', 'msg': '保存成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'编辑入库单失败: {e}')
            return api_error('保存失败，请稍后重试')

    @app.route('/in_order/add')
    @app.route('/other_in_order/add')
    @login_required
    def in_order_add_page():
        from datetime import date, datetime
        from sqlalchemy.orm import joinedload
        from app import (Customer, Material, Supplier, Unit, generate_order_no,
                         get_active_warehouses, get_default_warehouse, location_management_enabled,
                         serialize_customer, serialize_material, serialize_supplier, serialize_unit)
        from app import InOrder, InOrderItem
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        order_id = request.args.get('order_id', type=int)
        order = None
        if order_id:
            order = InOrder.query.options(
                joinedload(InOrder.items).joinedload(InOrderItem.material).joinedload(Material.unit)
            ).get_or_404(order_id)
            if order.status != 'pending':
                abort(409, '只有反提交后的草稿入库单可以编辑')
        order_type = 'other_in' if request.path == '/other_in_order/add' else (request.args.get('type') or '').strip().lower()
        source_purchase_order_id = request.args.get('source_purchase_order_id', type=int) or None
        is_product_in = order.business_type == '产品入库' if order else order_type in ('product', 'product_in')
        is_other_in = order.business_type == '其他入库' if order else order_type in ('other', 'other_in')
        business_type = order.business_type if order else ('其他入库' if is_other_in else ('产品入库' if is_product_in else '采购入库'))
        order_no = order.order_no if order else generate_order_no('OI' if is_other_in else ('PI' if is_product_in else 'IN'))
        parties = Customer.query.order_by(Customer.code.asc()).all() if is_other_in else Supplier.query.all()
        warehouses = get_active_warehouses()
        default_warehouse = get_default_warehouse()
        order_date = datetime.now().strftime('%Y-%m-%d')
        return render_template('in_order_add.html', 
                             materials=[serialize_material(material) for material in materials],
                             units=[serialize_unit(unit) for unit in units],
                             suppliers=[serialize_customer(p) if is_other_in else serialize_supplier(p) for p in parties],
                             warehouses=warehouses,
                             default_warehouse=default_warehouse,
                             location_management_enabled=location_management_enabled(),
                             is_product_in=is_product_in,
                             is_other_in=is_other_in,
                             business_type=business_type,
                             default_purpose=order.purpose if order else ('客供料入库' if is_other_in else ('生产完工入库' if is_product_in else '采购到货入库')),
                             page_title='新增产品入库单' if is_product_in else ('新增其他入库单' if is_other_in else '新增采购入库单'),
                             supplier_required=not is_product_in,
                             party_field='customer_id' if is_other_in else 'supplier_id',
                             party_label='客户' if is_other_in else ('生产来源' if is_product_in else '供应商'),
                             return_list_url='/other_in_order' if is_other_in else '/in_order',
                             return_add_url='/other_in_order/add' if is_other_in else ('/in_order/add?type=product' if is_product_in else '/in_order/add'),
                             source_purchase_order_id=source_purchase_order_id,
                             prefill={
                                 'warehouse': order.warehouse if order else (request.args.get('warehouse') or '').strip(),
                                 'location': order.location if order else (request.args.get('location') or '').strip(),
                                 'purpose': order.purpose if order else (request.args.get('purpose') or '').strip(),
                                 'contract_id': str(order.contract_id or '') if order else (request.args.get('contract_id') or '').strip(),
                                 'contract_no': order.contract_no if order else (request.args.get('contract_no') or '').strip(),
                                 'project_name': order.project_name if order else (request.args.get('project_name') or '').strip(),
                                 'remark': order.remark if order else (request.args.get('remark') or '').strip(),
                                 'customer': (request.args.get('customer') or '').strip(),
                                 'department_id': (request.args.get('department_id') or '').strip(),
                                 'supplier_id': str(order.supplier_id or '') if order else (request.args.get('supplier_id') or '').strip(),
                                 'customer_id': str(order.customer_id or '') if order else (request.args.get('customer_id') or '').strip(),
                             },
                             order_id=order.id if order else None,
                             order_no=order_no,
                             order_date=order.date.strftime('%Y-%m-%d') if order and order.date else order_date,
                             edit_items=[{
                                 'material_code': item.material.code,
                                 'source_purchase_order_item_id': item.source_purchase_order_item_id,
                                 'quantity': item.quantity,
                                 'price': item.price,
                                 'contract_no': item.contract_no or '',
                                 'project_name': item.project_name or '',
                                 'remark': item.remark or '',
                             } for item in order.items] if order else [],
                             today=date.today())

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_in_order():
        from datetime import date, datetime
        from flask_login import current_user
        from app import (Customer, InOrder, InOrderItem, Material, PurchaseOrder,
                         PurchaseOrderItem, api_error, assert_warehouse_active,
                         generate_order_no, get_default_warehouse,
                         in_order_duplicate_material_mode, is_future_date,
                         location_management_enabled, log_operation,
                         purchase_in_order_requires_order, recalculate_order_total,
                         round_to_2_decimals, update_purchase_order_status,
                         validate_purchase_receive_quantity)
        # Support both form data and JSON
        if request.is_json:
            data = request.get_json(silent=True) or {}
            order_id = data.get('order_id')
            order_no = (data.get('order_no') or '').strip()
            supplier_id = data.get('supplier_id')
            customer_id = data.get('customer_id')
            date_str = (data.get('date') or '').strip()
            business_type = (data.get('business_type') or '').strip()
            purpose = (data.get('purpose') or data.get('business_type') or '').strip()
            warehouse = (data.get('warehouse') or '').strip()
            location = (data.get('location') or '').strip()
            auto_push_requisition = data.get('auto_push_requisition') in (True, 1, '1', 'true', 'True', 'yes', 'on')
            remark = (data.get('remark') or '').strip()
            items_data = data.get('items', [])
        else:
            order_id = request.form.get('order_id')
            order_no = (request.form.get('order_no') or '').strip()
            supplier_id = request.form.get('supplier_id')
            customer_id = request.form.get('customer_id')
            date_str = (request.form.get('date') or '').strip()
            business_type = (request.form.get('business_type') or '').strip()
            purpose = (request.form.get('purpose') or '').strip()
            warehouse = (request.form.get('warehouse') or '').strip()
            location = (request.form.get('location') or '').strip()
            auto_push_requisition = request.form.get('auto_push_requisition') in ('1', 'true', 'True', 'yes', 'on')
            remark = (request.form.get('remark') or '').strip()
            items_data = []

        # 合同/工程字段（JSON 与表单两种模式统一提取）
        contract_id = (data.get('contract_id') if request.is_json else request.form.get('contract_id'))
        contract_no = ((data.get('contract_no') if request.is_json else request.form.get('contract_no')) or '').strip()
        project_name = ((data.get('project_name') if request.is_json else request.form.get('project_name')) or '').strip()

        # BUG-2026-08-02-001 修复：仓库是入库单必填字段，与库位管理是否启用无关。
        # 未填写时若开启“录单优先取默认仓库”，自动带入默认仓库。
        if not warehouse:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse:
            return jsonify({'status': 'error', 'msg': '请选择仓库'}), 400

        # AGENTS.md 规则二：开启库位管理时，库位为必填项
        if location_management_enabled() and not location:
            return jsonify({'status': 'error', 'msg': '请选择库位'}), 400

        if request.is_json:
            if not isinstance(items_data, list) or not items_data:
                return jsonify({'status': 'error', 'msg': '入库单至少需要一条明细'}), 400
            for index, item_data in enumerate(items_data, 1):
                if not isinstance(item_data, dict):
                    return jsonify({'status': 'error', 'msg': f'第 {index} 行入库明细格式不正确'}), 400
                material_code = (item_data.get('code') or '').strip()
                if not material_code:
                    return jsonify({'status': 'error', 'msg': f'第 {index} 行请选择物料'}), 400
                material = Material.query.filter_by(code=material_code).first()
                if not material:
                    return jsonify({'status': 'error', 'msg': f'第 {index} 行物料 {material_code} 不存在'}), 400
                try:
                    quantity = round_to_2_decimals(item_data.get('quantity', 0))
                except (TypeError, ValueError):
                    quantity = 0
                if quantity <= 0:
                    return jsonify({'status': 'error', 'msg': f'第 {index} 行物料 {material_code} 的数量必须大于0'}), 400
        elif not order_id:
            # BUG-2026-07-28-005 修复：表单提交（无 items_json）也必须校验
            # 供应商 / 客户、明细必填，禁止空表单保存为已完成入库单。
            # 仓库必填逻辑已统一在上方处理。
            if business_type == '采购入库' and not supplier_id:
                return jsonify({'status': 'error', 'msg': '采购入库单必须选择供应商'}), 400
            if business_type == '其他入库' and not customer_id:
                return jsonify({'status': 'error', 'msg': '其他入库单必须选择客户'}), 400
            # 表单可附带 items_json 字符串（与 JSON 路径结构相同）
            items_json = (request.form.get('items_json') or '').strip()
            if items_json:
                try:
                    items_data = json.loads(items_json)
                except (ValueError, TypeError):
                    return jsonify({'status': 'error', 'msg': '明细 JSON 格式错误'}), 400
                if not isinstance(items_data, list) or not items_data:
                    return jsonify({'status': 'error', 'msg': '入库单至少需要一条明细'}), 400
                for index, item_data in enumerate(items_data, 1):
                    if not isinstance(item_data, dict):
                        return jsonify({'status': 'error', 'msg': f'第 {index} 行入库明细格式不正确'}), 400
                    material_code = (item_data.get('code') or '').strip()
                    if not material_code:
                        return jsonify({'status': 'error', 'msg': f'第 {index} 行请选择物料'}), 400
                    try:
                        quantity = round_to_2_decimals(item_data.get('quantity', 0))
                    except (TypeError, ValueError):
                        quantity = 0
                    if quantity <= 0:
                        return jsonify({'status': 'error', 'msg': f'第 {index} 行物料 {material_code} 的数量必须大于0'}), 400
            else:
                return jsonify({'status': 'error', 'msg': '入库单至少需要一条明细'}), 400

        if order_id and order_id not in ('None', '', 'null'):
            try:
                order_id = int(order_id)
            except (ValueError, TypeError):
                order_id = None
        else:
            order_id = None

        if business_type not in ('采购入库', '产品入库', '其他入库'):
            business_type = '产品入库' if order_no.startswith('PI') or purpose == '产品入库' else '采购入库'

        try:
            if order_id:
                order = db.session.get(InOrder, order_id)
                if not order:
                    return api_error('入库单不存在，请刷新后重试')
                if order.status != 'pending':
                    return api_error('只有待处理的入库单可以修改')
            else:
                if not order_no:
                    order_no = generate_order_no('IN')

                order = InOrder.query.filter_by(order_no=order_no).first()
                if order:
                    if order.status != 'pending':
                        return api_error('入库单号已存在，不能重复保存')
                else:
                    order = InOrder(
                        order_no=order_no,
                        date=date.today(),
                        business_type=business_type,
                        operator_id=current_user.id
                    )
                    db.session.add(order)
                    db.session.flush()

            if supplier_id:
                try:
                    order.supplier_id = int(supplier_id)
                except (TypeError, ValueError):
                    return api_error('请选择有效的供应商')
            else:
                order.supplier_id = None
            if customer_id:
                try:
                    customer = db.session.get(Customer, int(customer_id))
                except (TypeError, ValueError):
                    customer = None
                if not customer:
                    return api_error('请选择有效的客户')
                order.customer_id = customer.id
            else:
                order.customer_id = None

            if date_str:
                try:
                    order.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return api_error('日期格式不正确，请重新选择日期')
            if is_future_date(order.date):
                return jsonify({'status': 'error', 'msg': '入库日期不能晚于今天'}), 400

            order.business_type = business_type
            order.auto_push_requisition = bool(auto_push_requisition and business_type == '采购入库')
            order.purpose = purpose
            order.warehouse = warehouse
            order.location = location
            order.remark = remark
            order.contract_id = int(contract_id) if contract_id else None
            order.contract_no = contract_no or None
            order.project_name = project_name or None
            # BUG-2026-08-02-001 修复：仓库必填且必须有效（与库位管理是否启用无关）
            ok, wh_msg = assert_warehouse_active(order.warehouse, allow_empty=False)
            if not ok:
                return jsonify({'status': 'error', 'msg': wh_msg}), 400

            source_item_updates = []
            source_purchase_order_ids = set()
            existing_affected_purchase_order_ids = set()
            pending_in_order_items = {}
            if request.is_json and items_data and order.id:
                for old_item in list(order.items):
                    if old_item.source_purchase_order_item:
                        source_item = old_item.source_purchase_order_item
                        source_item.received_quantity = max(
                            0,
                            round_to_2_decimals((source_item.received_quantity or 0) - (old_item.quantity or 0))
                        )
                        if source_item.purchase_order:
                            existing_affected_purchase_order_ids.add(source_item.purchase_order.id)
                    db.session.delete(old_item)
                db.session.flush()

            # Process items if provided (JSON mode)
            if items_data:
                for item_data in items_data:
                    material_code = (item_data.get('code') or '').strip()
                    if not material_code:
                        return jsonify({'status': 'error', 'msg': '请选择物料后再保存'}), 400
                    material = Material.query.filter_by(code=material_code).first()
                    if not material:
                        return jsonify({'status': 'error', 'msg': f'物料 {material_code} 不存在'}), 400
                    try:
                        quantity = round_to_2_decimals(item_data.get('quantity', 0))
                    except (TypeError, ValueError):
                        return jsonify({'status': 'error', 'msg': f'物料 {material_code} 的数量格式不正确'}), 400
                    if quantity <= 0:
                        return jsonify({'status': 'error', 'msg': f'物料 {material_code} 的数量必须大于0'}), 400
                    try:
                        price = round_to_2_decimals(item_data.get('price', 0))
                    except (TypeError, ValueError):
                        price = 0
                    amount = round_to_2_decimals(quantity * price)
                    is_customer_supplied = item_data.get('is_customer_supplied') in (True, 1, '1', 'true', 'True', 'yes', 'on')
                    if is_customer_supplied and business_type != '其他入库':
                        return jsonify({'status': 'error', 'msg': f'物料 {material.code} 只有其他入库单可以标记为客供料'}), 400
                    if is_customer_supplied and not order.customer_id:
                        return jsonify({'status': 'error', 'msg': f'物料 {material.code} 已勾选客供，请先选择客户'}), 400
                    source_purchase_order_item_id = None
                    source_item_id = item_data.get('source_purchase_order_item_id')
                    if source_item_id:
                        try:
                            source_item = db.session.get(PurchaseOrderItem, int(source_item_id))
                        except (TypeError, ValueError):
                            source_item = None
                        if not source_item or source_item.material_id != material.id:
                            return api_error(f'采购单来源明细无效：{material.code}')
                        source_order = source_item.purchase_order
                        if not source_order or source_order.status not in ('pending', 'partial'):
                            return api_error('只能选择未入库或部分入库的采购单明细')
                        valid_qty, qty_msg = validate_purchase_receive_quantity(source_item, quantity, material.code)
                        if not valid_qty:
                            return api_error(qty_msg)
                        source_purchase_order_item_id = source_item.id
                        source_item_updates.append((source_item, quantity))
                        source_purchase_order_ids.add(source_order.id)
                    elif business_type == '采购入库' and purchase_in_order_requires_order():
                        return api_error(f'采购入库物料 {material.code} 必须关联采购订单明细')
                    duplicate_key = (material.id, source_purchase_order_item_id, is_customer_supplied)
                    duplicate_mode = in_order_duplicate_material_mode()
                    existing_item = pending_in_order_items.get(duplicate_key)
                    if existing_item:
                        if duplicate_mode == 'forbid':
                            return api_error(f'物料 {material.code} 在当前入库单中重复')
                        if duplicate_mode == 'merge':
                            existing_item.quantity = round_to_2_decimals((existing_item.quantity or 0) + quantity)
                            existing_item.amount = round_to_2_decimals((existing_item.quantity or 0) * (existing_item.price or 0))
                            continue
                    item = InOrderItem(
                        in_order_id=order.id,
                        material_id=material.id,
                        source_purchase_order_item_id=source_purchase_order_item_id,
                        quantity=quantity,
                        price=price,
                        amount=amount,
                        remark=(item_data.get('remark') or '').strip() or None,
                        contract_id=int(item_data.get('contract_id')) if item_data.get('contract_id') else None,
                        contract_no=(item_data.get('contract_no') or '').strip() or None,
                        project_name=(item_data.get('project_name') or '').strip() or None,
                        is_customer_supplied=is_customer_supplied,
                    )
                    db.session.add(item)
                    pending_in_order_items[duplicate_key] = item

            recalculate_order_total(order)
            if source_purchase_order_ids and len(source_purchase_order_ids) == 1:
                order.source_purchase_order_id = next(iter(source_purchase_order_ids))
            affected_orders = set()
            for source_item, quantity in source_item_updates:
                source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) + quantity)
                if source_item.purchase_order:
                    affected_orders.add(source_item.purchase_order)
            for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(existing_affected_purchase_order_ids)).all():
                affected_orders.add(purchase_order)
            for purchase_order in affected_orders:
                update_purchase_order_status(purchase_order)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('保存失败，请稍后重试')

            log_operation('保存入库单', f'入库单：{order.order_no}', 'in_order', order.id)
            app.logger.info(f'入库单创建成功：{order.order_no}')
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': order.id, 'order_no': order.order_no})
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'保存入库单失败: {e}')
            return api_error('保存失败，请稍后重试')

    # Inbound detail operations
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/item/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_in_order_item(id):
        """Add a detail row to a pending inbound order."""
        from app import (InOrder, InOrderItem, Material, PurchaseOrderItem, api_error,
                         find_duplicate_in_order_item, in_order_duplicate_material_mode,
                         is_purchase_in_order, log_operation, purchase_in_order_requires_order,
                         recalculate_order_total, round_to_2_decimals,
                         update_purchase_order_status, validate_purchase_receive_quantity)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有待处理的入库单可以添加明细')

        material_code = (request.form.get('material_code') or '').strip()
        if not material_code:
            return api_error('请选择物料后再添加')

        material = Material.query.filter_by(code=material_code).first()
        if not material:
            return api_error(f'物料 {material_code} 不存在')

        try:
            quantity = round_to_2_decimals(request.form.get('quantity', 0))
        except (TypeError, ValueError):
            return api_error('数量必须是数字')
        if quantity <= 0:
            return api_error('数量必须大于0')

        try:
            price = round_to_2_decimals(request.form.get('price', 0))
        except (TypeError, ValueError):
            return api_error('单价必须是数字')
        amount = round_to_2_decimals(quantity * price)
        source_purchase_order_item_id = None
        source_item = None
        source_item_id = request.form.get('source_purchase_order_item_id', type=int)
        if source_item_id:
            source_item = db.session.get(PurchaseOrderItem, source_item_id)
            if not source_item or source_item.material_id != material.id:
                return api_error(f'采购单来源明细无效：{material.code}')
            valid_qty, qty_msg = validate_purchase_receive_quantity(source_item, quantity, material.code)
            if not valid_qty:
                return api_error(qty_msg)
            source_purchase_order_item_id = source_item.id
        elif is_purchase_in_order(order) and purchase_in_order_requires_order():
            return api_error('采购入库必须关联采购订单，请从采购订单下推或选单生成入库单')

        duplicate_mode = in_order_duplicate_material_mode()
        duplicate_item = find_duplicate_in_order_item(order, material.id, source_purchase_order_item_id)
        if duplicate_item:
            if duplicate_mode == 'forbid':
                return api_error(f'物料 {material_code} 在当前入库单中重复')
            if duplicate_mode == 'merge':
                duplicate_item.quantity = round_to_2_decimals((duplicate_item.quantity or 0) + quantity)
                # 合并时若用户填入了新单价，应以新单价作为合并后单价；
                # 否则用户修改的 price 被静默丢弃，amount 仍按旧价计算，造成入库金额错误
                if price and price != round_to_2_decimals(duplicate_item.price or 0):
                    duplicate_item.price = price
                duplicate_item.amount = round_to_2_decimals((duplicate_item.quantity or 0) * (duplicate_item.price or 0))
                if source_item:
                    source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) + quantity)
                    update_purchase_order_status(source_item.purchase_order)
                recalculate_order_total(order)
                db.session.commit()
                log_operation('编辑入库单', f'入库单合并物料：{material_code}', 'in_order', id)
                return jsonify({'status': 'success', 'msg': '相同物料已自动合并'})

        try:
            item = InOrderItem(
                in_order_id=id,
                material_id=material.id,
                source_purchase_order_item_id=source_purchase_order_item_id,
                quantity=quantity,
                price=price,
                amount=amount,
                remark=(request.form.get('remark') or '').strip() or None
            )
            db.session.add(item)
            if source_item:
                source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) + quantity)
                update_purchase_order_status(source_item.purchase_order)
            recalculate_order_total(order)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '明细添加失败，请稍后重试'}), 500

            log_operation('编辑入库单', f'入库单新增物料：{material_code}', 'in_order', id)
            return jsonify({'status': 'success', 'msg': '明细添加成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('明细添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/batch_add_items', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_add_in_order_items(id):
        """Batch add inbound detail rows. Format per line: code,quantity,price."""
        from app import (InOrder, InOrderItem, Material, api_error, is_purchase_in_order,
                         log_operation, parse_float_value, purchase_in_order_requires_order,
                         recalculate_order_total, round_to_2_decimals)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有草稿状态的入库单可以添加明细')
        if is_purchase_in_order(order) and purchase_in_order_requires_order():
            return api_error('采购入库必须关联采购订单，不能批量添加无来源明细')

        data = request.get_json(silent=True) or {}
        content = (data.get('content') or request.form.get('content') or '').strip()
        if not content:
            return api_error('请输入物料信息')

        added = 0
        errors = []
        try:
            for line_no, raw_line in enumerate(content.splitlines(), start=1):
                line = raw_line.strip()
                if not line:
                    continue
                parts = [part.strip() for part in line.replace('\t', ',').split(',')]
                material_code = parts[0] if parts else ''
                quantity = round_to_2_decimals(parse_float_value(parts[1] if len(parts) > 1 else None, 0))
                if not material_code or quantity <= 0:
                    errors.append(f'第 {line_no} 行格式不正确')
                    continue

                material = Material.query.filter_by(code=material_code).first()
                if not material:
                    errors.append(f'第 {line_no} 行物料不存在：{material_code}')
                    continue

                default_price = material.price or 0
                price = round_to_2_decimals(parse_float_value(parts[2] if len(parts) > 2 else None, default_price))
                db.session.add(InOrderItem(
                    in_order_id=id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=round_to_2_decimals(quantity * price)
                ))
                added += 1

            if added == 0:
                return api_error(errors[0] if errors else '未添加任何明细')
            recalculate_order_total(order)
            db.session.commit()
            log_operation('编辑入库单', f'批量添加入库单明细：{order.order_no}', 'in_order', id)
            msg = f'成功添加 {added} 条'
            if errors:
                msg += '，部分行失败：' + '；'.join(errors[:3])
            return jsonify({'status': 'success', 'msg': msg})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量添加入库明细失败: {e}')
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/delete_item/<int:item_id>', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_in_order_item(id, item_id):
        """Delete a detail row from a pending inbound order."""
        from app import (InOrder, InOrderItem, api_error, log_operation)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有待处理的入库单可以删除明细')

        item = InOrderItem.query.get_or_404(item_id)
        if item.in_order_id != id:
            return api_error('明细不属于当前入库单')

        material_name = item.material.name if item.material else ''
        log_operation('编辑入库单', f'删除入库单明细：{material_name}', 'in_order', id)

        db.session.delete(item)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'数据库操作失败: {e}')
            return jsonify({'status': 'error', 'msg': '删除失败，请稍后重试'}), 500

        return jsonify({'status': 'success', 'msg': '删除成功'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def in_order_item_delete_alias(id, item_id):
        """Alias endpoint for deleting an inbound order item."""
        from app import (InOrder, InOrderItem, api_error, log_operation)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有待处理的入库单可以删除明细')

        item = InOrderItem.query.get_or_404(item_id)
        if item.in_order_id != id:
            return api_error('明细不属于当前入库单')

        material_name = item.material.name if item.material else ''
        log_operation('编辑入库单', f'删除入库单明细：{material_name}', 'in_order', id)

        db.session.delete(item)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'数据库操作失败: {e}')
            return jsonify({'status': 'error', 'msg': '删除失败，请稍后重试'}), 500

        return jsonify({'status': 'success', 'msg': '删除成功'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/item/update', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_in_order_item():
        """Update an inbound order item."""
        from app import (InOrderItem, STOCK_COMPARE_EPSILON, api_error, is_purchase_in_order,
                         purchase_in_order_requires_order, round_to_2_decimals,
                         should_block_purchase_over_receive, update_purchase_order_status)
        item_id = request.form.get('id', type=int)
        if not item_id:
            return api_error('缺少明细ID')
        item = InOrderItem.query.get_or_404(item_id)
        if item.in_order.status != 'pending':
            return api_error('只有待处理的入库单可以修改明细')
        old_quantity = item.quantity or 0
        new_quantity = round_to_2_decimals(request.form.get('quantity', item.quantity))
        # P0-BUGFIX: 数量必须为有限正数。原实现无 >0 校验，0/负数/NaN 可落库，
        # 经 complete_in_order → add_stock 污染 Material.stock。
        if not math.isfinite(new_quantity) or new_quantity <= 0:
            return api_error('数量必须大于 0')
        if is_purchase_in_order(item.in_order) and purchase_in_order_requires_order() and not item.source_purchase_order_item:
            return api_error('采购入库必须关联采购订单，请从采购订单下推或选单生成入库单')
        if item.source_purchase_order_item and should_block_purchase_over_receive():
            source_item = item.source_purchase_order_item
            available_qty = round_to_2_decimals((source_item.quantity or 0) - ((source_item.received_quantity or 0) - old_quantity))
            if new_quantity - available_qty > STOCK_COMPARE_EPSILON:
                material_code = item.material.code if item.material else item.material_id
                return api_error(f'物料 {material_code} 入库数量不能大于采购单未入库数量')
            source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) - old_quantity + new_quantity)
            update_purchase_order_status(source_item.purchase_order)
        item.quantity = new_quantity
        item.price = round_to_2_decimals(request.form.get('price', item.price))
        item.amount = round_to_2_decimals(item.quantity * item.price)
        if 'remark' in request.form:
            item.remark = (request.form.get('remark') or '').strip() or None
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success', 'msg': '保存成功'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/copy_to_out', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def copy_in_order_to_out(id):
        """Copy an inbound order into a draft outbound order."""
        from datetime import date
        from app import (InOrder, OutOrder, OutOrderItem, generate_order_no)
        in_order = InOrder.query.get_or_404(id)
        order_no = generate_order_no('OU')
        out_order = OutOrder(
            order_no=order_no,
            date=date.today(),
            customer=in_order.supplier.name if in_order.supplier else '',
            purpose=in_order.purpose or '',
            business_type='领料单',
            warehouse=in_order.warehouse or '',
            status='pending'
        )
        db.session.add(out_order)
        db.session.flush()
        for item in in_order.items:
            out_item = OutOrderItem(
                out_order_id=out_order.id,
                material_id=item.material_id,
                quantity=item.quantity,
                price=item.price,
                amount=item.amount,
                remark=item.remark
            )
            db.session.add(out_item)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success', 'msg': '操作完成', 'out_order_id': out_order.id})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/copy', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def copy_in_order(id):
        """Copy an inbound order into a new draft inbound order."""
        from datetime import date
        from flask_login import current_user
        from sqlalchemy.orm import joinedload
        from app import (InOrder, InOrderItem, Material, PurchaseOrderItem, api_error,
                         generate_order_no, log_operation, recalculate_order_total,
                         round_to_2_decimals, update_purchase_order_status,
                         validate_purchase_receive_quantity)
        source = InOrder.query.options(
            joinedload(InOrder.items).joinedload(InOrderItem.material),
            joinedload(InOrder.items).joinedload(InOrderItem.source_purchase_order_item).joinedload(PurchaseOrderItem.purchase_order),
        ).get_or_404(id)
        if not source.items:
            return api_error('原入库单没有明细，不能复制')

        business_type = source.business_type or '采购入库'
        source_item_updates = []
        affected_purchase_orders = set()
        try:
            for item in source.items:
                quantity = round_to_2_decimals(item.quantity or 0)
                if quantity <= 0:
                    continue
                if item.source_purchase_order_item_id:
                    source_item = item.source_purchase_order_item
                    source_order = source_item.purchase_order if source_item else None
                    if not source_item or not source_order or source_order.status not in ('pending', 'partial'):
                        return api_error('原入库单的采购来源已完成或关闭，请从采购订单重新下推生成入库单')
                    valid_qty, qty_msg = validate_purchase_receive_quantity(
                        source_item,
                        quantity,
                        item.material.code if item.material else item.material_id,
                    )
                    if not valid_qty:
                        return api_error(f'{qty_msg}。请从采购订单按剩余未入库数量重新下推。')
                    source_item_updates.append((source_item, quantity))
                    affected_purchase_orders.add(source_order)
            prefix = 'PI' if business_type == '产品入库' else 'IN'
            new_order = InOrder(
                order_no=generate_order_no(prefix),
                date=date.today(),
                supplier_id=source.supplier_id,
                customer_id=getattr(source, 'customer_id', None),
                business_type=business_type,
                purpose=source.purpose or business_type,
                warehouse=source.warehouse or '',
                location=getattr(source, 'location', '') or '',
                source_purchase_order_id=source.source_purchase_order_id if source_item_updates else None,
                contract_id=source.contract_id,
                contract_no=source.contract_no,
                project_name=source.project_name,
                remark=f'由入库单 {source.order_no} 复制生成' + (f'；原备注：{source.remark}' if source.remark else ''),
                status='pending',
                operator_id=current_user.id,
                total_amount=0,
            )
            db.session.add(new_order)
            db.session.flush()

            copied_count = 0
            for item in source.items:
                quantity = round_to_2_decimals(item.quantity or 0)
                if quantity <= 0:
                    continue
                price = round_to_2_decimals(item.price or 0)
                db.session.add(InOrderItem(
                    in_order_id=new_order.id,
                    material_id=item.material_id,
                    source_purchase_order_item_id=item.source_purchase_order_item_id if source_item_updates else None,
                    quantity=quantity,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                    remark=item.remark,
                    contract_id=item.contract_id,
                    contract_no=item.contract_no,
                    project_name=item.project_name,
                    is_customer_supplied=bool(getattr(item, 'is_customer_supplied', False)),
                ))
                copied_count += 1

            if copied_count <= 0:
                db.session.rollback()
                return api_error('原入库单没有有效数量，不能复制')

            for source_item, quantity in source_item_updates:
                source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) + quantity)
            for purchase_order in affected_purchase_orders:
                update_purchase_order_status(purchase_order)
            recalculate_order_total(new_order)
            db.session.commit()
            log_operation('复制入库单', f'{source.order_no} -> {new_order.order_no}', 'in_order', new_order.id)
            return jsonify({
                'status': 'success',
                'msg': '复制成功，已生成新的入库草稿',
                'id': new_order.id,
                'order_no': new_order.order_no,
                'redirect_url': url_for('in_order_detail', id=new_order.id),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'复制入库单失败: {e}')
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/check_anomalies', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def check_in_order_anomalies(id):
        """检查入库单异常，返回异常列表供前端确认。"""
        from app import (InOrder, _ai_call_llm_chat, _ai_llm_configured,
                         _check_in_order_anomalies, api_error)
        order = InOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('该入库单已提交，不能检查异常')

        anomalies = _check_in_order_anomalies(order)

        # 如果有异常且启用了AI，添加AI原因分析
        if anomalies and _ai_llm_configured():
            for anomaly in anomalies:
                # 生成AI分析提示
                prompt = f"作为仓库管理专家，请分析以下异常情况并给出简短建议（50字内）：\n"
                prompt += f"异常类型：{anomaly['type']}\n"
                prompt += f"物料：{anomaly['material']}\n"
                prompt += f"当前值：{anomaly['current']}\n"
                prompt += f"历史均值：{anomaly['average']}\n"
                prompt += f"偏离度：{anomaly['deviation']}\n"
                prompt += f"可能原因和建议："

                try:
                    ai_suggestion = _ai_call_llm_chat(prompt)
                    if ai_suggestion:
                        anomaly['ai_suggestion'] = ai_suggestion.strip()
                except Exception as e:
                    app.logger.warning(f'AI异常分析失败: {e}')

        return jsonify({
            'status': 'success',
            'anomalies': anomalies,
            'has_anomalies': len(anomalies) > 0
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def complete_in_order(id):
        """Complete an inbound order and add stock."""
        from sqlalchemy.orm import selectinload
        from app import (DocumentPushLine, InOrder, InOrderItem, OutOrder, OutOrderItem,
                         PurchaseOrder, PurchaseOrderItem, WechatShareConfig,
                         _acquire_order_write_lock, _check_in_order_anomalies,
                         _wechat_share_order, add_stock, api_error,
                         assert_warehouse_active,
                         deduct_location_inventory_atomic, deduct_stock_atomic,
                         generate_order_no, get_default_warehouse, is_future_date,
                         location_management_enabled, log_operation,
                         recalculate_order_total, resolve_inventory_warehouse_id,
                         round_to_2_decimals, update_location_inventory,
                         update_purchase_order_status, validate_purchase_in_order_source)
        from flask_login import current_user
        # 预加载 items + material，消除 _check_in_order_anomalies 中的 N+1 查询
        order = InOrder.query.options(
            selectinload(InOrder.items).selectinload(InOrderItem.material)
        ).get_or_404(id)
        if order.status != 'pending':
            return api_error('该入库单已提交，不能重复操作')

        if is_future_date(order.date):
            return jsonify({'status': 'error', 'msg': '入库日期不能晚于今天，请先修改单据日期'}), 400
        if not order.items:
            return api_error('请至少添加一条入库明细')
        # BUG-2026-08-02-009 修复：仓库是入库单必填字段，与库位管理是否启用无关。
        # 锁前只做 fast-path 读校验（不修改 order 对象），实际赋值放到加锁后完成。
        # 因为 _acquire_order_write_lock 在 SQLite 分支会 db.session.rollback()，
        # 锁前的 order.warehouse 修改会被丢弃，导致存量无仓库 pending 单据完成时
        # 以 warehouse=NULL 落库 + 库位库存不同步。
        if not order.warehouse and not get_default_warehouse():
            return api_error('入库单必须填写仓库')
        valid_source, source_msg = validate_purchase_in_order_source(order)
        if not valid_source:
            return api_error(source_msg)

        force_submit = request.args.get('force', '').lower() in ('true', '1', 'yes')
        if not force_submit:
            anomalies = _check_in_order_anomalies(order)
            if anomalies:
                return jsonify({
                    'status': 'warning',
                    'msg': '检测到异常，请确认是否继续提交',
                    'anomalies': anomalies
                })

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复入库。
            # 预加载 items.material + items.source_purchase_order_item.purchase_order，
            # 消除循环内逐条 lazy-load 导致的 N+1 查询（每条明细省 3 次查询）。
            locked, ok = _acquire_order_write_lock(InOrder, id, 'pending', [
                selectinload(InOrder.items).selectinload(InOrderItem.material),
                selectinload(InOrder.items).selectinload(InOrderItem.source_purchase_order_item).selectinload(PurchaseOrderItem.purchase_order),
            ])
            if not ok:
                return api_error('该入库单已提交，不能重复操作')
            order = locked
            if not order.items:
                db.session.rollback()
                return api_error('请至少添加一条入库明细')
            # 加锁后再做仓库赋值与必填校验，避免锁前修改被 rollback 丢弃。
            # 未填写时若开启“录单优先取默认仓库”，自动带入默认仓库。
            if not order.warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    order.warehouse = default_wh.name
            if not order.warehouse:
                db.session.rollback()
                return api_error('入库单必须填写仓库')
            # PUR-AUDIT-003：草稿保存后仓库可能被停用，完成前必须复核 active 状态
            wh_ok, wh_msg = assert_warehouse_active(order.warehouse, allow_empty=False)
            if not wh_ok:
                db.session.rollback()
                return api_error(wh_msg)
            # P1-BUGFIX: 库位管理启用时 location 必填（AGENTS.md 规则二）
            if location_management_enabled() and not (order.location or '').strip():
                db.session.rollback()
                return api_error('库位管理已启用，请选择库位')
            # BUG-2026-08-04-015 修复：移除 is_recompleted 递增。
            # 反提交（revert_in_order）不再释放 received_quantity 预留，
            # 因此重新完成时无需再次递增，避免 反提交→编辑→重新完成 双计数。
            # 采购单 received_quantity 由 /in_order/add 保存、update_completed、
            # delete_in_order 处维护，完成仅代表库存入账，不改变接收数量。
            affected_purchase_order_ids = set()
            for item in order.items:
                if item.material:
                    ok, err = add_stock(item.material, item.quantity,
                                        transaction_type='in',
                                        reference_type='in_order',
                                        reference_id=order.id,
                                        warehouse=order.warehouse)
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存增加失败')
                    if location_management_enabled() and (order.location or order.warehouse):
                        loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, item.quantity or 0, warehouse=order.warehouse)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存更新失败')
                if item.source_purchase_order_item:
                    if item.source_purchase_order_item.purchase_order:
                        affected_purchase_order_ids.add(item.source_purchase_order_item.purchase_order.id)

            order.status = 'completed'
            order.total_amount = sum((item.amount or 0) for item in order.items)
            for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_purchase_order_ids)).all():
                update_purchase_order_status(purchase_order)
            auto_requisition = None
            if order.auto_push_requisition:
                if order.business_type != '采购入库':
                    db.session.rollback()
                    return api_error('仅采购入库单可以自动下推领料单')
                request_id = f'auto-requisition-{order.id}'
                if DocumentPushLine.query.filter_by(
                    source_document_type='purchase_in_order', source_document_id=order.id,
                    request_id=request_id,
                ).first():
                    db.session.rollback()
                    return api_error('自动下推领料单已处理，不能重复操作')
                auto_requisition = OutOrder(
                    order_no=generate_order_no('OUT'), date=order.date,
                    business_type='领料单', warehouse=order.warehouse,
                    location=order.location, purpose='自动下推领料单', status='completed',
                    operator_id=current_user.id,
                    remark=f'由采购入库单 {order.order_no} 自动下推并完成领料',
                )
                db.session.add(auto_requisition)
                db.session.flush()
                use_location = bool(location_management_enabled() and (order.location or order.warehouse))
                for source_item in order.items:
                    price = round_to_2_decimals(source_item.material.price or 0) if source_item.material else 0
                    target_item = OutOrderItem(
                        out_order_id=auto_requisition.id, material_id=source_item.material_id,
                        quantity=source_item.quantity, price=price,
                        amount=round_to_2_decimals((source_item.quantity or 0) * price),
                        contract_id=source_item.contract_id, contract_no=source_item.contract_no,
                        project_name=source_item.project_name, remark=source_item.remark,
                    )
                    db.session.add(target_item)
                    db.session.flush()
                    stock_ok, stock_error, _ = deduct_stock_atomic(
                        source_item.material_id, source_item.quantity or 0,
                        transaction_type='out', reference_type='out_order',
                        reference_id=auto_requisition.id,
                        warehouse=order.warehouse,
                    )
                    if not stock_ok:
                        db.session.rollback()
                        return api_error(stock_error or '自动下推领料单扣减库存失败')
                    if use_location:
                        location_ok, location_error = deduct_location_inventory_atomic(
                            source_item.material_id, order.location or order.warehouse,
                            source_item.quantity or 0,
                            material_code_hint=source_item.material.code if source_item.material else None,
                            warehouse_id=resolve_inventory_warehouse_id(order.warehouse),
                        )
                        if not location_ok:
                            db.session.rollback()
                            return api_error(location_error or '自动下推领料单扣减库位库存失败')
                    db.session.add(DocumentPushLine(
                        source_document_type='purchase_in_order', source_document_id=order.id,
                        source_document_no=order.order_no, source_item_id=source_item.id,
                        target_document_type='requisition', target_document_id=auto_requisition.id,
                        target_document_no=auto_requisition.order_no, target_item_id=target_item.id,
                        pushed_quantity=source_item.quantity or 0, status='active',
                        request_id=request_id, created_by=current_user.id,
                    ))
                recalculate_order_total(auto_requisition)
            try:
                db.session.commit()
                share_now_config = WechatShareConfig.query.filter_by(enabled=True, immediate_on_complete=True, share_in_order=True).first()
                if share_now_config:
                    # 异步执行微信分享（图片渲染 + HTTP 请求），不阻塞完成响应
                    from app import _async_wechat_share_on_complete
                    from flask import current_app
                    _async_wechat_share_on_complete(
                        current_app._get_current_object(),
                        share_now_config.id, order.id, order.order_no,
                    )
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500

            log_operation('入库', f'入库单：{order.order_no}', 'in_order', id)
            if auto_requisition:
                log_operation('自动完成领料单', f'采购入库单：{order.order_no} 自动下推领料单：{auto_requisition.order_no}', 'out_order', auto_requisition.id)
            app.logger.info(f'入库单完成：{order.order_no}')
            return jsonify({
                'status': 'success',
                'msg': '提交成功' if not auto_requisition else f'提交成功，已自动下推并完成领料单 {auto_requisition.order_no}',
                'auto_requisition_id': auto_requisition.id if auto_requisition else None,
                'auto_requisition_no': auto_requisition.order_no if auto_requisition else None,
            })
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'入库单完成异常: order_id={id}, order_no={order.order_no}')
            return api_error('提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/update_completed', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_completed_in_order(id):
        """Update a completed inbound order and adjust stock differences."""
        from sqlalchemy.orm import selectinload
        from app import (InOrder, InOrderItem, Material, PurchaseOrder, PurchaseOrderItem,
                         STOCK_COMPARE_EPSILON, Warehouse, _acquire_order_write_lock,
                         _material_stock_unattributed, add_stock,
                         allow_negative_stock, api_error,
                         deduct_stock, get_default_warehouse, get_warehouse_stock_quantities,
                         is_stock_sufficient, location_management_enabled,
                         recalculate_order_total,
                         round_to_2_decimals, update_location_inventory,
                         update_purchase_order_status)
        order = InOrder.query.get_or_404(id)
        if order.status != 'completed':
            return api_error('只有已完成的入库单可以修改已入库明细')

        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return api_error('请求数据格式不正确，请刷新后重试')
        items_data = data.get('items', [])
        deleted_items = data.get('deleted_items', [])

        try:
            # BUG-2026-08-04-003 修复：原代码缺少 _acquire_order_write_lock，
            # 并发编辑已完成入库单或同时反提交（revert_in_order 已加锁）时，
            # 库存调整可能重复执行或对 pending 单据做库存操作。
            # 加锁后重新读取状态并做仓库赋值，与 complete_in_order 对称。
            # 预加载 items.material + items.source_purchase_order_item.purchase_order，
            # 消除循环内逐条 lazy-load 导致的 N+1 查询。
            locked, ok = _acquire_order_write_lock(InOrder, id, 'completed', [
                selectinload(InOrder.items).selectinload(InOrderItem.material),
                selectinload(InOrder.items).selectinload(InOrderItem.source_purchase_order_item).selectinload(PurchaseOrderItem.purchase_order),
            ])
            if not ok:
                return api_error('该入库单状态已变更，不能修改已入库明细')
            order = locked
            # BUG-2026-08-02-001 修复：已完成的入库单也必须有仓库。
            # 未填写时若开启“录单优先取默认仓库”，自动带入默认仓库。
            if not order.warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    order.warehouse = default_wh.name
            if not order.warehouse:
                db.session.rollback()
                return api_error('入库单必须填写仓库')

            # BUG-2026-08-16-009：删除/减量已完成入库单明细的库存充足校验改仓库级口径，
            # 避免多仓库下 A 仓库存掩护 B 仓明细回退、打穿 B 仓账面。
            wh_obj = None
            if (order.warehouse or '').strip():
                wh_key = order.warehouse.strip()
                wh_obj = Warehouse.query.filter(
                    db.or_(Warehouse.name == wh_key, Warehouse.code == wh_key)
                ).order_by(Warehouse.id.asc()).first()
            warehouse_stock = get_warehouse_stock_quantities(wh_obj) if wh_obj else {}

            affected_purchase_order_ids = set()
            # 1. Delete detail rows and reverse their stock changes
            for item_id in deleted_items:
                item = db.session.get(InOrderItem, item_id)
                if item and item.in_order_id == id:
                    if not allow_negative_stock():
                        required = item.quantity or 0
                        # BUG-2026-08-17-002：与 revert_in_order 同根因，仓库解析
                        # 失败时回退全局 Material.stock 口径。
                        if wh_obj is not None:
                            current_stock = warehouse_stock.get(item.material_id, 0)
                            # BUG-2026-08-18-002：仓库级聚合查不到该物料且其库存
                            # 全部为历史未归属流水（location 为空）时回退全局口径，
                            # 避免“明明有库存却拒绝删除明细/反提交”。
                            if not is_stock_sufficient(current_stock, required) and _material_stock_unattributed(item.material_id):
                                current_stock = item.material.stock if item.material else 0
                        else:
                            current_stock = item.material.stock if item.material else 0
                        if not is_stock_sufficient(current_stock, required):
                            db.session.rollback()
                            return api_error(f'物料 {item.material.code if item.material else "-"} 库存不足，当前库存：{current_stock:.2f}，需要：{required:.2f}')
                    # 使用 deduct_stock 写流水+归一化+库位还原，避免直接改 stock
                    ok, err = deduct_stock(item.material, item.quantity or 0,
                                           transaction_type='delete_in_item',
                                           reference_type='in_order',
                                           reference_id=order.id,
                                           remark=f'删除已完成入库单 {order.order_no} 明细回退库存',
                                           warehouse=order.warehouse)
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存回退失败')
                    if location_management_enabled() and (order.location or order.warehouse):
                        loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, -(item.quantity or 0), warehouse=order.warehouse)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存回退失败')
                    if item.source_purchase_order_item:
                        source_item = item.source_purchase_order_item
                        source_item.received_quantity = max(
                            0,
                            round_to_2_decimals((source_item.received_quantity or 0) - (item.quantity or 0))
                        )
                        if source_item.purchase_order:
                            affected_purchase_order_ids.add(source_item.purchase_order.id)
                    db.session.delete(item)

            # 2. Modify detail rows
            for item_data in items_data:
                item_id = item_data.get('id')
                is_new = item_data.get('is_new', False)

                if is_new:
                    # Add new detail row and apply stock change
                    material_code = (item_data.get('code') or item_data.get('material_code') or '').strip()
                    if not material_code:
                        return api_error('请选择物料后再添加')
                    material = Material.query.filter_by(code=material_code).first()
                    if not material:
                        return api_error(f'物料 {material_code} 不存在')

                    quantity = float(item_data['quantity'])
                    if not math.isfinite(quantity) or quantity <= 0:
                        return api_error(f'物料 {material_code} 的数量必须大于0')
                    price = float(item_data.get('price', 0))
                    amount = round_to_2_decimals(quantity * price)
                    source_purchase_order_item_id = None
                    source_item_id = item_data.get('source_purchase_order_item_id')
                    if source_item_id:
                        try:
                            source_item_id = int(source_item_id)
                        except (TypeError, ValueError):
                            return api_error('来源采购单明细格式不正确')
                        source_item = db.session.get(PurchaseOrderItem, source_item_id)
                        if not source_item or source_item.material_id != material.id:
                            return api_error('来源采购单明细与物料不匹配')
                        remain_qty = round_to_2_decimals((source_item.quantity or 0) - (source_item.received_quantity or 0))
                        if quantity - remain_qty > STOCK_COMPARE_EPSILON:
                            return api_error('新增明细数量不能大于来源采购单未下推数量')
                        source_item.received_quantity = round_to_2_decimals((source_item.received_quantity or 0) + quantity)
                        source_purchase_order_item_id = source_item.id
                        if source_item.purchase_order:
                            affected_purchase_order_ids.add(source_item.purchase_order.id)

                    new_item = InOrderItem(
                        in_order_id=id,
                        material_id=material.id,
                        quantity=quantity,
                        price=price,
                        amount=amount,
                        source_purchase_order_item_id=source_purchase_order_item_id,
                        remark=(item_data.get('remark') or '').strip() or None
                    )
                    db.session.add(new_item)
                    # 使用 add_stock 写流水+归一化+库位同步，避免直接改 stock
                    ok, err = add_stock(material, quantity,
                                        transaction_type='add_in_item',
                                        reference_type='in_order',
                                        reference_id=order.id,
                                        remark=f'已完成入库单 {order.order_no} 新增明细',
                                        warehouse=order.warehouse)
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存增加失败')
                    if location_management_enabled() and (order.location or order.warehouse):
                        loc_ok, loc_err = update_location_inventory(material, order.location or order.warehouse, quantity, warehouse=order.warehouse)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存更新失败')

                elif item_id:
                    item = db.session.get(InOrderItem, item_id)
                    if item and item.in_order_id == id:
                        old_qty = item.quantity
                        new_qty = float(item_data['quantity'])
                        if not math.isfinite(new_qty) or new_qty <= 0:
                            material_code = item.material.code if item.material else ''
                            return api_error(f'物料 {material_code} 的数量必须大于0')
                        new_price = float(item_data.get('price', 0))

                        qty_diff = new_qty - old_qty
                        if qty_diff < 0:
                            deduct_qty = abs(qty_diff)
                            if not allow_negative_stock():
                                current_stock = warehouse_stock.get(item.material_id, 0)
                                if not is_stock_sufficient(current_stock, deduct_qty):
                                    return api_error(f'物料 {item.material.code if item.material else "-"} 库存不足，当前库存：{current_stock:.2f}，需要：{deduct_qty:.2f}')
                        if item.source_purchase_order_item and abs(qty_diff) > STOCK_COMPARE_EPSILON:
                            source_item = item.source_purchase_order_item
                            effective_received_before = round_to_2_decimals((source_item.received_quantity or 0) - (old_qty or 0))
                            allowed_qty = round_to_2_decimals(max((source_item.quantity or 0) - effective_received_before, 0))
                            if new_qty - allowed_qty > STOCK_COMPARE_EPSILON:
                                return api_error('明细数量不能大于来源采购单未下推数量')
                            source_item.received_quantity = max(
                                0,
                                round_to_2_decimals((source_item.received_quantity or 0) + qty_diff)
                            )
                            if source_item.purchase_order:
                                affected_purchase_order_ids.add(source_item.purchase_order.id)
                        # 使用 add_stock/deduct_stock 写流水+归一化+库位同步，避免直接改 stock
                        if qty_diff > 0:
                            ok, err = add_stock(item.material, qty_diff,
                                                transaction_type='adjust_in_item',
                                                reference_type='in_order',
                                                reference_id=order.id,
                                                remark=f'修改已完成入库单 {order.order_no} 明细数量增加',
                                                warehouse=order.warehouse)
                            if not ok:
                                db.session.rollback()
                                return api_error(err or '库存增加失败')
                        elif qty_diff < 0:
                            ok, err = deduct_stock(item.material, abs(qty_diff),
                                                   transaction_type='adjust_in_item',
                                                   reference_type='in_order',
                                                   reference_id=order.id,
                                                   remark=f'修改已完成入库单 {order.order_no} 明细数量减少',
                                                   warehouse=order.warehouse)
                            if not ok:
                                db.session.rollback()
                                return api_error(err or '库存回退失败')
                        if location_management_enabled() and (order.location or order.warehouse) and qty_diff != 0:
                            loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, qty_diff, warehouse=order.warehouse)
                            if not loc_ok:
                                db.session.rollback()
                                return api_error(loc_err or '库位库存更新失败')

                        item.quantity = new_qty
                        item.price = new_price
                        item.amount = round_to_2_decimals(new_qty * new_price)
                        if 'remark' in item_data:
                            item.remark = (item_data.get('remark') or '').strip() or None

            recalculate_order_total(order)
            for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_purchase_order_ids)).all():
                update_purchase_order_status(purchase_order)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500
            return jsonify({'status': 'success', 'msg': '保存成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'更新入库单失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_in_order(id):
        from sqlalchemy.orm import selectinload
        from app import (InOrder, InOrderItem, PurchaseOrder, PurchaseOrderItem, StockTransaction,
                         _acquire_order_write_lock,
                         _source_has_active_push, api_error, log_audit, log_operation,
                         round_to_2_decimals, update_purchase_order_status)
        order = InOrder.query.get_or_404(id)
        if _source_has_active_push(id):
            return jsonify({'status': 'error', 'msg': '该入库单存在有效下推单据，不能删除；请先处理下游草稿。'}), 409
        if order.status != 'pending':
            return jsonify({
                'status': 'error',
                'msg': '已完成入库单不能直接删除，请先反提交回到草稿后再删除'
            }), 409

        try:
            # 重新锁定并校验草稿状态，防止并发完成后仍被物理删除。
            # 预加载 items.source_purchase_order_item.purchase_order，消除 N+1 查询。
            locked, ok = _acquire_order_write_lock(InOrder, id, 'pending', [
                selectinload(InOrder.items).selectinload(InOrderItem.source_purchase_order_item).selectinload(PurchaseOrderItem.purchase_order),
            ])
            if not ok:
                return jsonify({'status': 'error', 'msg': '该入库单状态已变更；已完成单请先反提交后再删除'}), 409
            order = locked

            affected_purchase_order_ids = set()
            for item in order.items:
                if item.source_purchase_order_item:
                    source_item = item.source_purchase_order_item
                    source_item.received_quantity = max(
                        0,
                        round_to_2_decimals((source_item.received_quantity or 0) - (item.quantity or 0))
                    )
                    if source_item.purchase_order:
                        affected_purchase_order_ids.add(source_item.purchase_order.id)

            for item in list(order.items):
                db.session.delete(item)
            # 已反提交的单据可物理删除；同步清理完成与反提交产生的库存流水，
            # 避免库存台账保留指向已删除入库单的悬挂引用。
            StockTransaction.query.filter_by(
                reference_type='in_order', reference_id=order.id
            ).delete(synchronize_session=False)
            db.session.delete(order)
            for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_purchase_order_ids)).all():
                update_purchase_order_status(purchase_order)
            db.session.commit()
            log_operation('删除入库单', f'入库单：{order.order_no}', 'in_order', id)
            # BUG-2026-08-16-012：删除入库单写结构化审计（old_data = 单号/仓库）
            log_audit(
                'delete_in_order', 'in_order', id,
                target_name=order.order_no,
                old_data={'order_no': order.order_no, 'warehouse': order.warehouse or ''},
                reason='草稿删除',
            )
            app.logger.info(f'入库单删除：{order.order_no}')
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def revert_in_order(id):
        from sqlalchemy.orm import selectinload
        from app import (InOrder, InOrderItem, PurchaseOrder, PurchaseOrderItem, StockTransaction,
                         Warehouse, _acquire_order_write_lock, _material_stock_unattributed,
                         _source_has_active_push, allow_negative_stock, api_error,
                         deduct_stock, get_warehouse_stock_quantities,
                         is_stock_sufficient, location_management_enabled,
                         log_audit, log_operation, normalize_stock_quantity, recalculate_order_total,
                         update_location_inventory, update_purchase_order_status)
        order = InOrder.query.get_or_404(id)
        if _source_has_active_push(id):
            return jsonify({'status': 'error', 'msg': '该入库单存在有效下推单据，不能反提交；请先处理下游单据。'}), 409
        if order.status != 'completed':
            return api_error('只有已完成的入库单可以反提交')

        # BUG-2026-08-16-009：反提交库存充足校验改仓库级口径（get_warehouse_stock_quantities），
        # 避免多仓库下 A 仓库存掩护 B 仓入库单反提交、打穿 B 仓账面。
        # OFF 模式按流水 location 聚合，ON 模式按 LocationInventory 聚合。
        wh_obj = None
        if (order.warehouse or '').strip():
            wh_key = order.warehouse.strip()
            wh_obj = Warehouse.query.filter(
                db.or_(Warehouse.name == wh_key, Warehouse.code == wh_key)
            ).order_by(Warehouse.id.asc()).first()
        warehouse_stock = get_warehouse_stock_quantities(wh_obj) if wh_obj else {}
        for item in order.items:
            quantity = normalize_stock_quantity(item.quantity or 0)
            if not allow_negative_stock():
                if wh_obj is not None:
                    current_stock = warehouse_stock.get(item.material_id, 0)
                    # BUG-2026-08-18-002：仓库级聚合查不到该物料且其库存
                    # 全部为历史未归属流水（location 为空）时回退全局口径，
                    # 避免“明明有库存却拒绝反提交”（与 update_completed_in_order、
                    # batch_revert_in_order 同一兜底）。
                    if not is_stock_sufficient(current_stock, quantity) and _material_stock_unattributed(item.material_id):
                        current_stock = item.material.stock if item.material else 0
                    # BUG-2026-08-18-002-fix：仓库级不足但全局充足时，检查该物料
                    # 是否有未归属流水（location 为空），如果有则把本单关联的未归属
                    # 流水修正到本单仓库，然后允许反提交。不碰其他仓库的已归属库存。
                    if not is_stock_sufficient(current_stock, quantity):
                        global_stock = item.material.stock if item.material else 0
                        if is_stock_sufficient(global_stock, quantity):
                            unattributed = StockTransaction.query.filter(
                                StockTransaction.material_id == item.material_id,
                                db.or_(StockTransaction.location.is_(None), StockTransaction.location == ''),
                            ).count()
                            if unattributed > 0:
                                StockTransaction.query.filter_by(
                                    reference_type='in_order', reference_id=order.id,
                                    material_id=item.material_id,
                                ).filter(
                                    db.or_(StockTransaction.location.is_(None), StockTransaction.location == '')
                                ).update({'location': order.warehouse.strip()}, synchronize_session=False)
                                current_stock = global_stock
                else:
                    # BUG-2026-08-17-002：老数据无仓库/仓库解析失败时，仓库级取数
                    # 不可用（warehouse_stock={} 会恒判库存不足），回退到全局
                    # Material.stock 口径——与 batch_revert_in_order、deduct_stock
                    # 实际回退口径一致，避免“有库存却拒绝反提交”。
                    current_stock = item.material.stock if item.material else 0
                if not is_stock_sufficient(current_stock, quantity):
                    return jsonify({
                        'status': 'error',
                        'msg': f'物料 {item.material.code if item.material else "-"} 库存不足，不能反提交'
                    })

        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复回退。
            # 预加载 items.material + items.source_purchase_order_item.purchase_order，
            # 消除循环内逐条 lazy-load 导致的 N+1 查询。
            locked, ok = _acquire_order_write_lock(InOrder, id, 'completed', [
                selectinload(InOrder.items).selectinload(InOrderItem.material),
                selectinload(InOrder.items).selectinload(InOrderItem.source_purchase_order_item).selectinload(PurchaseOrderItem.purchase_order),
            ])
            if not ok:
                return api_error('该入库单已反提交，不能重复操作')
            order = locked
            affected_purchase_order_ids = set()
            for item in order.items:
                ok, error_msg = deduct_stock(item.material, item.quantity or 0,
                             transaction_type='revert_in',
                             reference_type='in_order',
                             reference_id=order.id,
                             warehouse=order.warehouse)
                if not ok:
                    db.session.rollback()
                    return api_error(error_msg or '库存回退失败')
                # 同步还原库位库存（与 complete_in_order 对称），仅启用库位管理且有仓库时
                if location_management_enabled() and (order.location or order.warehouse):
                    loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, -(item.quantity or 0), warehouse=order.warehouse)
                    if not loc_ok:
                        db.session.rollback()
                        return api_error(loc_err or '库位库存还原失败')
                # BUG-2026-08-04-015 修复（received_quantity 双计数）：
                # 反提交只回退库存，不释放采购单 received_quantity 预留。
                # 该入库单仍为 pending，仍占用采购单“已下推”数量；
                # 只有删除该草稿（delete_in_order）才会释放预留。
                # 若此处释放，则与 batch_revert_in_order（不释放）行为不一致，
                # 且重新完成时 complete_in_order 的 is_recompleted 递增会导致重复计数。
                if item.source_purchase_order_item:
                    if item.source_purchase_order_item.purchase_order:
                        affected_purchase_order_ids.add(item.source_purchase_order_item.purchase_order.id)
            order.status = 'pending'
            recalculate_order_total(order)
            for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_purchase_order_ids)).all():
                update_purchase_order_status(purchase_order)
            db.session.commit()
            log_operation('反提交入库单', f'入库单：{order.order_no}', 'in_order', id)
            # BUG-2026-08-16-012：反提交入库单写结构化审计
            log_audit(
                'revert_in_order', 'in_order', id,
                target_name=order.order_no,
                old_data={'status': 'completed'},
                new_data={'status': 'pending'},
            )
            return jsonify({'status': 'success', 'msg': '操作完成'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/<int:id>/convert_to_out_order', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def convert_in_order_to_out_order(id):
        """将入库单转为领料单"""
        from datetime import date
        from flask_login import current_user
        from app import (InOrder, OutOrder, OutOrderItem, api_error, generate_order_no,
                         log_operation)
        in_order = InOrder.query.get_or_404(id)

        if in_order.status != 'completed':
            return api_error('只有已完成的入库单才能转为领料单')
        if in_order.business_type != '产品入库':
            return api_error('只有产品入库单可以转为领料单，采购入库单不能转换')

        try:
            # 生成领料单编号：必须复用 generate_order_no('OUT')，否则手动拼接的
            # OUT{YYYYMMDD} 序号既无 with_for_update 锁，又与全局 OUT 单号格式不一致，
            # 高并发下易与正常领料单单号冲突
            today = date.today()
            order_no = generate_order_no('OUT')

            # 创建领料单
            out_order = OutOrder(
                order_no=order_no,
                date=today,
                purpose=f'由入库单 {in_order.order_no} 转换',
                business_type='领料单',
                warehouse=in_order.warehouse or '',
                operator_id=current_user.id,
                status='pending',
                remark=in_order.remark or ''
            )
            db.session.add(out_order)
            db.session.flush()

            # 复制明细
            for in_item in in_order.items:
                out_item = OutOrderItem(
                    out_order_id=out_order.id,
                    material_id=in_item.material_id,
                    quantity=in_item.quantity,
                    price=in_item.price,
                    amount=in_item.amount,
                    remark=in_item.remark
                )
                db.session.add(out_item)

            db.session.commit()

            # 记录操作日志（放在commit之后，避免影响主事务）
            try:
                log_operation('入库单转领料单', f'入库单 {in_order.order_no} 转为领料单 {out_order.order_no}', 'out_order', out_order.id)
            except Exception as log_err:
                app.logger.error(f'记录日志失败: {log_err}')

            return jsonify({
                'status': 'success',
                'msg': '转换成功',
                'out_order_id': out_order.id,
                'out_order_no': out_order.order_no
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'入库单转领料单失败: {e}')
            return api_error(f'转换失败：{str(e)}')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/batch_delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_in_order():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InOrder, PurchaseOrder, StockTransaction, _acquire_order_write_lock,
                         _source_has_active_push, api_error, log_operation,
                         round_to_2_decimals, update_purchase_order_status)
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的入库单')
        if len(ids) > 100:
            return jsonify({'status': 'error', 'msg': '单次批量操作不能超过 100 条，请分批处理'}), 400

        orders = InOrder.query.options(joinedload(InOrder.supplier), joinedload(InOrder.items)).filter(InOrder.id.in_(ids)).all()
        # BUG-2026-08-02-011 修复：fast-path 校验非草稿单据，与 delete_in_order 对齐。
        # 已完成单必须先反提交回草稿再删除，禁止批量直接物理删除已完成单。
        blocked = [order.order_no for order in orders if order.status != 'pending']
        if blocked:
            return api_error('以下入库单已完成，不能删除：' + ', '.join(blocked))

        deleted_count = 0
        skipped = []
        affected_purchase_order_ids = set()
        # 逐条加写锁并独立提交，单点失败仅回滚自身，不影响其余单据。
        # 与 delete_in_order / batch_complete_in_order 实现保持对称。
        for order in list(orders):
            order_id = order.id
            order_no = order.order_no
            # 校验下推占用：存在有效下游草稿时不能删除，与 delete_in_order 一致
            if _source_has_active_push(order_id):
                skipped.append(f'{order_no}(存在下游单据)')
                continue
            try:
                # 重新加锁并校验草稿状态，防止并发完成/反提交后状态已变更。
                locked, ok = _acquire_order_write_lock(
                    InOrder, order_id, 'pending', selectinload(InOrder.items)
                )
                if not ok or locked is None:
                    skipped.append(f'{order_no}(状态已变更)')
                    db.session.rollback()
                    continue
                order = locked
                # 回退采购订单来源进度（与 delete_in_order 对齐）
                for item in list(order.items):
                    if item.source_purchase_order_item:
                        source_item = item.source_purchase_order_item
                        source_item.received_quantity = max(
                            0,
                            round_to_2_decimals((source_item.received_quantity or 0) - (item.quantity or 0))
                        )
                        if source_item.purchase_order:
                            affected_purchase_order_ids.add(source_item.purchase_order.id)
                    db.session.delete(item)
                StockTransaction.query.filter_by(
                    reference_type='in_order', reference_id=order.id
                ).delete(synchronize_session=False)
                db.session.delete(order)
                # 每张单据独立提交，保证单点失败仅回滚自身
                db.session.commit()
                deleted_count += 1
                log_operation('批量删除入库单', f'入库单：{order_no}', 'in_order', order_id)
            except Exception:
                db.session.rollback()
                skipped.append(f'{order_no}(错误)')
                app.logger.exception('批量删除入库单失败: %s', order_no)

        # 更新受影响的采购订单状态（已提交的单据不受后续 rollback 影响）
        po_update_failed = False
        try:
            for po_id in affected_purchase_order_ids:
                po = db.session.get(PurchaseOrder, po_id)
                if po:
                    update_purchase_order_status(po)
            db.session.commit()
        except Exception:
            db.session.rollback()
            po_update_failed = True
            app.logger.exception('批量删除入库单后更新采购订单状态失败')

        msg = f'批量删除完成，共删除 {deleted_count} 张入库单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        if po_update_failed:
            msg += '；但部分采购订单状态更新失败，请人工核对采购订单执行进度'
        return jsonify({
            'status': 'success',
            'msg': msg,
            'deleted': deleted_count,
            'skipped': skipped,
            'po_update_failed': po_update_failed,
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/batch_complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_complete_in_order():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InOrder, InOrderItem, WechatShareConfig, _acquire_order_write_lock,
                         _check_in_order_anomalies, _wechat_share_order, add_stock,
                         api_error, assert_warehouse_active, get_default_warehouse,
                         is_future_date, location_management_enabled,
                         update_location_inventory,
                         validate_purchase_in_order_source,
                         validate_purchase_receive_quantity)
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        select_all = payload.get('select_all', False)
        status_filter = payload.get('status', None)

        if select_all:
            query = InOrder.query
            if status_filter:
                query = query.filter(InOrder.status == status_filter)
            orders = query.options(joinedload(InOrder.items)).all()
        else:
            ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
            if not ids:
                return api_error('请选择要审核的入库单')
            if len(ids) > 100:
                return jsonify({'status': 'error', 'msg': '单次批量操作不能超过 100 条，请分批处理'}), 400
            orders = InOrder.query.options(joinedload(InOrder.items)).filter(InOrder.id.in_(ids)).all()

        completed = 0
        skipped = []
        for order in list(orders):
            # 防止列表中重复 id 触发同一单据被处理两次
            order_id = order.id
            if order.status != 'pending':
                skipped.append(order.order_no)
                continue
            if not order.items:
                skipped.append(f'{order.order_no}(无明细)')
                continue
            # 重新加锁并校验状态，避免并发批量/单据完成请求重复审核同一张单据。
            # 预加载 items.material 与来源采购单链，消除循环内逐条 lazy-load 的 N+1 查询。
            locked, lock_ok = _acquire_order_write_lock(
                InOrder, order_id, 'pending',
                [
                    selectinload(InOrder.items).selectinload(InOrderItem.material),
                    selectinload(InOrder.items).selectinload(InOrderItem.source_purchase_order_item),
                ]
            )
            if not lock_ok or locked is None:
                skipped.append(f'{order.order_no}(状态已变更)')
                db.session.rollback()
                continue
            order = locked
            # BUG-2026-08-16-005 修复：批量完成补齐与单据版 complete_in_order
            # 一致的业务校验，防止批量入口绕过单据完成门禁。
            # ① 未来日期拒绝（BUG-DATE-2026-07-27-001 同款规则）
            if is_future_date(order.date):
                skipped.append(f'{order.order_no}(入库日期晚于今天)')
                db.session.rollback()
                continue
            # ② 采购入库须关联采购订单（开关开启时）
            valid_source, source_msg = validate_purchase_in_order_source(order)
            if not valid_source:
                skipped.append(f'{order.order_no}({source_msg})')
                db.session.rollback()
                continue
            # BUG-2026-08-02-001 修复：批量完成时入库单也必须有仓库。
            # 未填写时若开启“录单优先取默认仓库”，自动带入默认仓库。
            if not order.warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    order.warehouse = default_wh.name
            if not order.warehouse:
                skipped.append(f'{order.order_no}(未填写仓库)')
                db.session.rollback()
                continue
            # PUR-AUDIT-003：草稿保存后仓库可能被停用，完成前必须复核 active 状态
            wh_ok, wh_msg = assert_warehouse_active(order.warehouse, allow_empty=False)
            if not wh_ok:
                skipped.append(f'{order.order_no}(仓库已停用)')
                db.session.rollback()
                continue
            # P1-BUGFIX: 库位管理启用时 location 必填（AGENTS.md 规则二）
            if location_management_enabled() and not (order.location or '').strip():
                skipped.append(f'{order.order_no}(未填写库位)')
                db.session.rollback()
                continue
            # ③ 超收复核：草稿期间来源 PO 的未入库数量可能被其他单推进，
            # 完成时按行级来源复核（与新增明细 validate_purchase_receive_quantity 同口径）
            over_qty = False
            for item in order.items:
                if not item.source_purchase_order_item_id:
                    continue
                source_item = item.source_purchase_order_item
                if not source_item:
                    continue
                valid_qty, qty_msg = validate_purchase_receive_quantity(
                    source_item, item.quantity or 0,
                    item.material.code if item.material else str(item.material_id))
                if not valid_qty:
                    skipped.append(f'{order.order_no}({qty_msg})')
                    over_qty = True
                    break
            if over_qty:
                db.session.rollback()
                continue
            # ④ 异常检测：批量无 force 交互通道，异常单一律跳过转人工单独审核
            anomalies = _check_in_order_anomalies(order)
            if anomalies:
                skipped.append(f'{order.order_no}(检测到异常，请单独审核)')
                db.session.rollback()
                continue
            try:
                for item in order.items:
                    if item.material:
                        ok, err = add_stock(item.material, item.quantity,
                                            transaction_type='in',
                                            reference_type='in_order',
                                            reference_id=order.id,
                                            warehouse=order.warehouse)
                        if not ok:
                            raise ValueError(err or '库存增加失败')
                        # 同步库位库存（与 complete_in_order 对称），仅启用库位管理且有仓库时
                        if location_management_enabled() and (order.location or order.warehouse):
                            loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, item.quantity, warehouse=order.warehouse)
                            if not loc_ok:
                                raise ValueError(loc_err or '库位库存更新失败')
                order.status = 'completed'
                order.total_amount = sum((item.amount or 0) for item in order.items)
                # 每张单据独立 commit，保证单点失败仅回滚自身，不影响后续单据
                db.session.commit()
                completed += 1
                share_now_config = WechatShareConfig.query.filter_by(enabled=True, immediate_on_complete=True, share_in_order=True).first()
                if share_now_config:
                    # 异步执行微信分享，不阻塞批量完成响应
                    from app import _async_wechat_share_on_complete
                    from flask import current_app
                    _async_wechat_share_on_complete(
                        current_app._get_current_object(),
                        share_now_config.id, order.id, order.order_no,
                    )
            except Exception as e:
                db.session.rollback()
                skipped.append(f'{order.order_no}(错误)')
        msg = f'批量审核完成，共审核 {completed} 张入库单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        return jsonify({'status': 'success', 'msg': msg, 'completed': completed})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order/batch_revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_revert_in_order():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InOrder, StockTransaction, Warehouse, _acquire_order_write_lock, _material_stock_unattributed,
                         allow_negative_stock,
                         api_error, deduct_stock_atomic, get_warehouse_stock_quantities, is_stock_sufficient,
                         location_management_enabled, normalize_stock_quantity,
                         recalculate_order_total, update_location_inventory)
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        select_all = payload.get('select_all', False)

        if select_all:
            orders = InOrder.query.options(joinedload(InOrder.items)).filter(InOrder.status == 'completed').all()
        else:
            ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
            if not ids:
                return api_error('请选择要反审的入库单')
            orders = InOrder.query.options(joinedload(InOrder.items)).filter(InOrder.id.in_(ids)).all()

        reverted = 0
        skipped = []
        for order in list(orders):
            # 防止列表中重复 id 触发同一单据被处理两次
            order_id = order.id
            if order.status != 'completed':
                skipped.append(order.order_no)
                continue
            # 重新加锁并校验状态，避免并发批量/单据反审请求重复回退同一张入库单
            # （重复反审会重复扣减库存）
            locked, lock_ok = _acquire_order_write_lock(
                InOrder, order_id, 'completed', selectinload(InOrder.items)
            )
            if not lock_ok or locked is None:
                skipped.append(f'{order.order_no}(状态已变更)')
                db.session.rollback()
                continue
            order = locked
            wh_obj = None
            if (order.warehouse or '').strip():
                wh_key = order.warehouse.strip()
                wh_obj = Warehouse.query.filter(
                    db.or_(Warehouse.name == wh_key, Warehouse.code == wh_key)
                ).order_by(Warehouse.id.asc()).first()
            warehouse_stock = get_warehouse_stock_quantities(wh_obj) if wh_obj else {}
            stock_insufficient = False
            for item in order.items:
                quantity = normalize_stock_quantity(item.quantity or 0)
                if wh_obj is not None:
                    stock = normalize_stock_quantity(warehouse_stock.get(item.material_id, 0))
                    # BUG-2026-08-18-002：仓库级聚合查不到该物料且其库存
                    # 全部为历史未归属流水（location 为空）时回退全局口径，
                    # 避免“明明有库存却被批量反提交跳过”（与 revert_in_order、
                    # update_completed_in_order 同一兜底）。
                    if not is_stock_sufficient(stock, quantity) and item.material and _material_stock_unattributed(item.material_id):
                        stock = normalize_stock_quantity(item.material.stock or 0)
                    # BUG-2026-08-18-002-fix：仓库级不足但全局充足时，检查该物料
                    # 是否有未归属流水（location 为空），如果有则把本单关联的未归属
                    # 流水修正到本单仓库，然后允许反提交。不碰其他仓库的已归属库存。
                    if not is_stock_sufficient(stock, quantity) and item.material:
                        global_stock = normalize_stock_quantity(item.material.stock or 0)
                        if is_stock_sufficient(global_stock, quantity):
                            unattributed = StockTransaction.query.filter(
                                StockTransaction.material_id == item.material_id,
                                db.or_(StockTransaction.location.is_(None), StockTransaction.location == ''),
                            ).count()
                            if unattributed > 0:
                                StockTransaction.query.filter_by(
                                    reference_type='in_order', reference_id=order.id,
                                    material_id=item.material_id,
                                ).filter(
                                    db.or_(StockTransaction.location.is_(None), StockTransaction.location == '')
                                ).update({'location': order.warehouse.strip()}, synchronize_session=False)
                                stock = global_stock
                else:
                    stock = normalize_stock_quantity(item.material.stock if item.material else 0)
                if item.material and not allow_negative_stock() and not is_stock_sufficient(stock, quantity):
                    skipped.append(f'{order.order_no}(库存不足)')
                    stock_insufficient = True
                    break
            if stock_insufficient:
                db.session.rollback()
                continue
            try:
                for item in order.items:
                    if item.material:
                        # 使用原子扣减避免并发超扣，并检查返回值
                        ok, error_msg, _ = deduct_stock_atomic(item.material_id, item.quantity or 0,
                                     transaction_type='revert_in',
                                     reference_type='in_order',
                                     reference_id=order.id,
                                     warehouse=order.warehouse)
                        if not ok:
                            raise ValueError(error_msg or '库存回退失败')
                        # 同步还原库位库存（与 complete_in_order 对称）
                        if location_management_enabled() and (order.location or order.warehouse):
                            loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, -(item.quantity or 0), warehouse=order.warehouse)
                            if not loc_ok:
                                raise ValueError(loc_err or '库位库存还原失败')
                order.status = 'pending'
                recalculate_order_total(order)
                # 每张单据独立 commit，保证单点失败仅回滚自身，不影响后续单据
                db.session.commit()
                reverted += 1
            except Exception as e:
                db.session.rollback()
                skipped.append(f'{order.order_no}(错误: {e})')
        msg = f'批量反审完成，共反审 {reverted} 张入库单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        return jsonify({'status': 'success', 'msg': msg, 'reverted': reverted})

    @app.route('/in_order/batch_print', methods=['POST'])
    @login_required
    def batch_print_in_order():
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return jsonify({'status': 'error', 'msg': '请选择要打印的入库单'})
        if len(ids) > 100:
            return jsonify({'status': 'error', 'msg': '单次批量打印不能超过 100 条'}), 400
        from app import InOrder
        orders = InOrder.query.filter(InOrder.id.in_(ids)).all()
        if not orders:
            return jsonify({'status': 'error', 'msg': '未找到符合条件的入库单'})
        order_nos = ', '.join([o.order_no for o in orders[:5]])
        if len(orders) > 5:
            order_nos += f' 等 {len(orders)} 张'
        return jsonify({
            'status': 'success',
            'msg': f'已选择 {len(orders)} 张入库单进行打印：{order_nos}',
            'count': len(orders),
            'redirect': f'/in_order/{orders[0].id}/print'
        })

    @app.route('/in_order/batch_export', methods=['POST'])
    @login_required
    def batch_export_in_order():
        import io
        from openpyxl import Workbook
        from flask import send_file
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return jsonify({'status': 'error', 'msg': '请选择要导出的入库单'})
        if len(ids) > 1000:
            return jsonify({'status': 'error', 'msg': '单次批量导出不能超过 1000 条'}), 400
        from sqlalchemy.orm import joinedload
        from app import InOrder
        orders = InOrder.query.options(joinedload(InOrder.items)).filter(InOrder.id.in_(ids)).all()
        if not orders:
            return jsonify({'status': 'error', 'msg': '未找到符合条件的入库单'})
        wb = Workbook()
        ws = wb.active
        ws.title = '入库单批量导出'
        ws.append(['单据编号', '日期', '业务类型', '供应商', '仓库', '物料编码', '物料名称', '规格', '合同单号', '工程名称', '单位', '数量', '单价', '金额', '状态', '备注'])
        for order in orders:
            if order.items:
                for item in order.items:
                    ws.append([
                        order.order_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order.business_type or '采购入库',
                        order.supplier.name if order.supplier else '',
                        order.warehouse or '',
                        item.material.code if item.material else '',
                        item.material.name if item.material else '',
                        item.material.spec if item.material else '',
                        item.contract_no or '',
                        item.project_name or '',
                        item.material.unit.name if item.material and item.material.unit else '',
                        float(item.quantity or 0),
                        float(item.price or 0),
                        float(item.amount or 0),
                        '已完成' if order.status == 'completed' else '待完成',
                        order.remark or ''
                    ])
            else:
                ws.append([
                    order.order_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    order.business_type or '采购入库',
                    order.supplier.name if order.supplier else '',
                    order.warehouse or '',
                    '', '', '', '', '', 0, 0, 0,
                    '已完成' if order.status == 'completed' else '待完成',
                    order.remark or ''
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        from datetime import datetime
        filename = f'入库单批量导出_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return send_file(output, download_name=filename, as_attachment=True,
                        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.route('/in_order/<int:id>/preview_template')
    @login_required
    def preview_in_order_template(id):
        from datetime import datetime
        from app import (InOrder, InOrderPrintTemplate, _render_html_print_content,
                         get_default_print_template)
        order = InOrder.query.get_or_404(id)
        template = get_default_print_template(InOrderPrintTemplate)

        if template and template.template_type == 'excel' and template.excel_template_path:
            return jsonify({
                'status': 'success',
                'msg': '操作完成',
                'type': 'excel',
                'template_path': template.excel_template_path
            })

        rendered = render_template(
            'print_in_with_html.html' if template and template.template_type == 'html' else 'print_in.html',
            order=order,
            template=template,
            rendered_content=_render_html_print_content(template.html_template_content, order=order, template=template, now=datetime.now()) if template and template.template_type == 'html' else ''
        )
        return jsonify({'status': 'success', 'msg': '操作完成', 'type': 'html', 'content': rendered})

    def _render_in_order_print(id):
        # PRINT-ROUTING-F01-P3：抽出的未装饰实现，供 /print（ptoken 免登录）复用，
        # 避免直接调用带 @login_required 的视图函数导致 ptoken 通过外层仍被内层重定向。
        from datetime import datetime
        from app import (InOrder, InOrderPrintTemplate, _render_html_print_content,
                         get_default_print_template)
        order = InOrder.query.get_or_404(id)
        template = get_default_print_template(InOrderPrintTemplate)
        if template:
            if template.template_type == 'excel':
                return render_template('print_in_with_excel.html', order=order, template=template)
            if template.template_type == 'html':
                rendered_content = _render_html_print_content(template.html_template_content, order=order, template=template, now=datetime.now())
                return render_template('print_in_with_html.html', order=order, template=template, rendered_content=rendered_content)
        return render_template('print_in.html', order=order)

    @app.route('/in_order/<int:id>/print_with_template')
    @login_required
    def print_in_order_with_template(id):
        return _render_in_order_print(id)

    @app.route('/in_order/<int:id>/print')
    @print_token_or_login_required  # PRINT-ROUTING-F01-P3：支持 ptoken 免登录（Windows 打印代理）
    def print_in_order(id):
        return _render_in_order_print(id)

    @app.route('/in_order/<int:id>/print_direct')
    @login_required
    def print_in_order_direct(id):
        from app import InOrder
        order = InOrder.query.get_or_404(id)
        return render_template('print_in.html', order=order)

    @app.route('/print_in_order_labels')
    @login_required
    def print_in_order_labels():
        from datetime import datetime
        from app import InOrderItem
        ids = request.args.get('ids', '').split(',')
        item_ids = [int(item_id) for item_id in ids if item_id.strip().isdigit()]
        items = InOrderItem.query.filter(InOrderItem.id.in_(item_ids)).all() if item_ids else []
        materials = [item.material for item in items if item.material]
        # 与 print_batch_labels 保持一致：传入 materials_data 以便前端 MATERIALS 正确初始化。
        materials_data = [
            {
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
                'supplier_name': m.supplier.name if m.supplier else '',
            }
            for m in materials
        ]
        return render_template('print_batch_labels.html', materials=materials, materials_data=materials_data)

    @app.route('/in_order_print_template')
    @login_required
    def in_order_print_template_list():
        from app import InOrderPrintTemplate, _print_template_query_from_args
        query, filters, sort_by, sort_order = _print_template_query_from_args(InOrderPrintTemplate)
        templates = query.all()
        return render_template('in_order_print_template.html', templates=templates, filters=filters, sort_by=sort_by, sort_order=sort_order)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order_print_template/add', methods=['POST'])
    @require_role('admin')
    @login_required
    def add_in_order_print_template():
        from app import InOrderPrintTemplate, create_print_template
        return create_print_template(InOrderPrintTemplate, 'in_order_template')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order_print_template/<int:template_id>/set_default', methods=['POST'])
    @require_role('admin')
    @login_required
    def set_default_in_order_print_template(template_id):
        from app import InOrderPrintTemplate, set_default_print_template
        return set_default_print_template(InOrderPrintTemplate, template_id)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/in_order_print_template/<int:template_id>/delete', methods=['POST'])
    @require_role('admin')
    @login_required
    def delete_in_order_print_template(template_id):
        from app import InOrderPrintTemplate, delete_print_template
        return delete_print_template(InOrderPrintTemplate, template_id)

    @app.route('/in_order/<int:id>/export')
    @login_required
    def export_single_in_order(id):
        import io
        from openpyxl import Workbook
        from app import InOrder
        order = InOrder.query.get_or_404(id)
        wb = Workbook()
        ws = wb.active
        ws.title = '入库单'
        ws.append(['单据编号', '日期', '用途', '供应商', '仓库', '物料编码', '物料名称', '规格', '合同单号', '工程名称', '单位', '数量', '单价', '金额', '备注'])
        if order.items:
            for item in order.items:
                ws.append([
                    order.order_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    order.purpose or '',
                    order.supplier.name if order.supplier else '',
                    order.warehouse or '',
                    item.material.code if item.material else '',
                    item.material.name if item.material else '',
                    item.material.spec if item.material else '',
                    item.contract_no or '',
                    item.project_name or '',
                    item.material.unit.name if item.material and item.material.unit else '',
                    item.quantity or 0,
                    item.price or 0,
                    item.amount or 0,
                    order.remark or ''
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name=f'in_order_{order.order_no}.xlsx', as_attachment=True)
