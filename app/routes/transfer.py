#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 调拨（transfer）域路由。
#
# 批量拆分模式：register_transfer_routes(app) 直接在 app 上注册路由，
# endpoint 名保持不变（transfer_list、save_transfer_table、complete_transfer 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（TransferOrder 模型、TransferOrderItem、
#   各辅助函数 _get_order_list_filters / _apply_status_date_filters / api_error /
#   _render_transfer_form / _workbook_response / validate_excel_extension 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_transfer_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import io
from datetime import date, datetime

from flask import flash, jsonify, redirect, render_template, request, url_for, send_file
from flask_login import login_required, current_user

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 transfer_* 各路由测试覆盖
def register_transfer_routes(app):

    @app.route('/transfer')
    @login_required
    def transfer_list():
        from app import (Material, TransferOrder, TransferOrderItem, _apply_status_date_filters, _get_order_list_filters, _status_from_search_keyword, get_active_warehouses, get_default_warehouse)
        from sqlalchemy.orm import joinedload, selectinload
        from flask import render_template, request
        """库存调拨单列表"""
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed', 'cancelled'))
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'transfer_no', 'date', 'from_location', 'to_location', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = TransferOrder.query.options(
            joinedload(TransferOrder.operator),
            selectinload(TransferOrder.items).joinedload(TransferOrderItem.material)
        )
        query = _apply_status_date_filters(query, TransferOrder, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed', 'cancelled'))
            conditions = [
                TransferOrder.transfer_no.like(search_like),
                TransferOrder.from_location.like(search_like),
                TransferOrder.to_location.like(search_like),
                TransferOrder.remark.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(TransferOrder.status == status_from_search)
            query = query.outerjoin(TransferOrderItem, TransferOrderItem.transfer_order_id == TransferOrder.id).outerjoin(
                Material, TransferOrderItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(TransferOrder, sort_by, TransferOrder.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        transfers = pagination.items
        warehouses = get_active_warehouses()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template('transfer.html', transfers=transfers, pagination=pagination, warehouses=warehouses, default_warehouse=get_default_warehouse(), filters=filters, sort_by=sort_by, sort_order=sort_order, per_page=per_page)

    @app.route('/transfer/add', methods=['GET'])
    @login_required
    def transfer_add_page():
        from app import (_render_transfer_form)
        return _render_transfer_form()

    @app.route('/transfer/<int:id>')
    @login_required
    def transfer_detail(id):
        from app import (Material, TransferOrder, TransferOrderItem, _render_transfer_form)
        from sqlalchemy.orm import joinedload, selectinload
        """库存调拨单详情"""
        transfer = TransferOrder.query.options(
            joinedload(TransferOrder.operator),
            selectinload(TransferOrder.items).joinedload(TransferOrderItem.material).joinedload(Material.unit),
            selectinload(TransferOrder.items).joinedload(TransferOrderItem.unit)
        ).get_or_404(id)
        return _render_transfer_form(transfer)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/save_table', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def save_transfer_table():
        from app import (TransferOrder, TransferOrderItem, _clean_int, _material_from_payload, _parse_form_date, allow_negative_stock, api_error, generate_order_no, is_stock_sufficient, log_operation, normalize_stock_quantity, parse_float_value, round_to_2_decimals)
        from flask import jsonify, request
        data = request.get_json(silent=True) or {}
        order_id = _clean_int(data.get('order_id'))
        transfer_no = (data.get('order_no') or data.get('transfer_no') or '').strip() or generate_order_no('TF')
        header = data.get('header') or {}
        items_data = data.get('items') or []
        from_location = (header.get('from_location') or '').strip()
        to_location = (header.get('to_location') or '').strip()
        # BUG-2026-08-02-013：仓库必填（AGENTS.md 规则）。
        # 优先读 from_warehouse/to_warehouse（新字段），未提供时回退 from_location/to_location
        # （历史兼容：旧前端把仓库名存到 from_location/to_location）。
        from_warehouse = (header.get('from_warehouse') or from_location or '').strip()
        to_warehouse = (header.get('to_warehouse') or to_location or '').strip()

        # 未开启库位管理时，from_location/to_location 与仓库相同；
        # 开启库位管理时，from_location/to_location 作为库位字段（可为空，由前端控制）。
        if not from_warehouse:
            return api_error('请选择调出仓库')
        if not to_warehouse:
            return api_error('请选择调入仓库')
        if from_warehouse == to_warehouse and (not from_location or from_location == to_location):
            return api_error('调出仓库和调入仓库不能相同')
        if not items_data:
            return api_error('请至少填写一条调拨明细')

        try:
            if order_id:
                transfer = db.session.get(TransferOrder, order_id)
                if not transfer:
                    return api_error('调拨单不存在，请刷新后重试')
                if transfer.status != 'pending':
                    return api_error('只有草稿状态的调拨单可以修改')
                duplicate = TransferOrder.query.filter(TransferOrder.transfer_no == transfer_no, TransferOrder.id != order_id).first()
                if duplicate:
                    return api_error('调拨单号已存在')
            else:
                transfer = TransferOrder.query.filter_by(transfer_no=transfer_no).first()
                if transfer:
                    if transfer.status != 'pending':
                        return api_error('调拨单号已存在')
                else:
                    transfer = TransferOrder(transfer_no=transfer_no, status='pending', operator_id=current_user.id)
                    db.session.add(transfer)

            transfer.transfer_no = transfer_no
            transfer.date = _parse_form_date(data.get('date'), transfer.date if order_id else date.today())
            transfer.from_warehouse = from_warehouse
            transfer.to_warehouse = to_warehouse
            # from_location/to_location 保留为库位字段；未开启库位管理时与仓库相同（历史兼容）
            transfer.from_location = from_location or from_warehouse
            transfer.to_location = to_location or to_warehouse
            transfer.remark = (header.get('remark') or '').strip()
            if not transfer.operator_id:
                transfer.operator_id = current_user.id
            db.session.flush()
            TransferOrderItem.query.filter_by(transfer_order_id=transfer.id).delete()

            for item_data in items_data:
                material = _material_from_payload(item_data)
                if not material:
                    return api_error(f'物料不存在：{item_data.get("code") or ""}')
                quantity = round_to_2_decimals(parse_float_value(item_data.get('quantity'), 0))
                if quantity <= 0:
                    return api_error(f'物料 {material.code} 的数量必须大于0')
                current_stock = normalize_stock_quantity(material.stock or 0)
                if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                    return api_error(f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}')
                price = round_to_2_decimals(parse_float_value(item_data.get('price'), material.price or 0))
                db.session.add(TransferOrderItem(
                    transfer_order_id=transfer.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=_clean_int(item_data.get('unit_id')) or material.unit_id,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                    remark=(item_data.get('remark') or '').strip() or None
                ))

            db.session.commit()
            log_operation('保存调拨单', f'调拨单：{transfer.transfer_no}', 'transfer', transfer.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': transfer.id, 'order_no': transfer.transfer_no})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存调拨单表格失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_transfer():
        from app import (TransferOrder, api_error, generate_order_no, log_operation)
        from flask import jsonify, request
        """新增库存调拨单"""
        try:
            from_location = (request.form.get('from_location') or '').strip()
            to_location = (request.form.get('to_location') or '').strip()
            remark = (request.form.get('remark') or '').strip()
            # BUG-2026-08-02-013：仓库必填（AGENTS.md 规则）。
            # 优先读 from_warehouse/to_warehouse（新字段），未提供时回退 from_location/to_location
            # （历史兼容：旧前端把仓库名存到 from_location/to_location）。
            from_warehouse = (request.form.get('from_warehouse') or from_location or '').strip()
            to_warehouse = (request.form.get('to_warehouse') or to_location or '').strip()

            # 未开启库位管理时，from_location/to_location 与仓库相同；
            # 开启库位管理时，from_location/to_location 作为库位字段（可为空，由前端控制）。
            if not from_warehouse:
                return api_error('请选择调出仓库')
            if not to_warehouse:
                return api_error('请选择调入仓库')
            if from_warehouse == to_warehouse and (not from_location or from_location == to_location):
                return api_error('调出仓库和调入仓库不能相同')

            transfer_no = generate_order_no('TF')
            transfer = TransferOrder(
                transfer_no=transfer_no,
                from_warehouse=from_warehouse,
                to_warehouse=to_warehouse,
                # from_location/to_location 保留为库位字段；未开启库位管理时与仓库相同（历史兼容）
                from_location=from_location or from_warehouse,
                to_location=to_location or to_warehouse,
                remark=remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(transfer)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '创建失败，请稍后重试'}), 500
        
            log_operation('新增调拨单', f'调拨单：{transfer_no}', 'transfer', transfer.id)
            return jsonify({'status': 'success', 'msg': '调拨单创建成功', 'id': transfer.id})
        except Exception as e:
            db.session.rollback()
            return api_error('创建失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/item/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_transfer_item(id):
        from app import (Material, TransferOrder, TransferOrderItem, allow_negative_stock, api_error, is_stock_sufficient, normalize_stock_quantity, parse_float_value, round_to_2_decimals)
        from flask import jsonify, request
        """添加调拨明细"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以添加明细')
    
        try:
            material_code = (request.form.get('material_code') or '').strip()
            quantity = parse_float_value(request.form.get('quantity'), 0)
            price = round_to_2_decimals(parse_float_value(request.form.get('price'), 0))

            if not material_code:
                return api_error('请选择物料')
            if quantity <= 0:
                return api_error('数量必须大于0')
        
            material = Material.query.filter_by(code=material_code).first()
            if not material:
                return api_error(f'物料 {material_code} 不存在')
        
            # 检查库存是否充足
            current_stock = normalize_stock_quantity(material.stock or 0)
            if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                return api_error(f'物料 {material_code} 库存不足，当前库存：{current_stock:.2f}')
        
            item = TransferOrderItem(
                transfer_order_id=id,
                material_id=material.id,
                quantity=quantity,
                unit_id=material.unit_id,
                price=price,
                amount=round_to_2_decimals(quantity * price),
                remark=(request.form.get('remark') or '').strip() or None
            )
            db.session.add(item)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '添加失败，请稍后重试'}), 500
        
            return jsonify({'status': 'success', 'msg': '调拨明细添加成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_transfer_item(id, item_id):
        from app import (TransferOrder, TransferOrderItem, api_error)
        from flask import jsonify
        """删除调拨明细"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以删除明细')
    
        item = TransferOrderItem.query.get_or_404(item_id)
        if item.transfer_order_id != id:
            return api_error('调拨明细不属于当前调拨单')
    
        try:
            db.session.delete(item)
            db.session.commit()
            return jsonify({'status': 'success', 'msg': '调拨明细删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/item/<int:item_id>/update', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_transfer_item(id, item_id):
        from app import (TransferOrder, TransferOrderItem, api_error, parse_float_value, round_to_2_decimals)
        from flask import jsonify, request
        """修改调拨明细"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以修改明细')

        item = TransferOrderItem.query.get_or_404(item_id)
        if item.transfer_order_id != id:
            return api_error('调拨明细不属于当前调拨单')

        try:
            quantity = round_to_2_decimals(parse_float_value(request.form.get('quantity'), item.quantity))
            price = round_to_2_decimals(parse_float_value(request.form.get('price'), item.price or 0))
            if quantity <= 0:
                return api_error('数量必须大于0')
            if item.material and (item.material.stock or 0) < quantity:
                return api_error(f'物料 {item.material.code} 库存不足，当前库存：{item.material.stock or 0}')

            item.quantity = quantity
            item.price = price
            item.amount = round_to_2_decimals(quantity * price)
            if 'remark' in request.form:
                item.remark = (request.form.get('remark') or '').strip() or None
            db.session.commit()
            return jsonify({'status': 'success', 'msg': '修改成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'调拨明细修改失败: {e}')
            return api_error('修改失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/batch_delete_items', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_transfer_items(id):
        from app import (TransferOrder, TransferOrderItem, api_error)
        from flask import jsonify, request
        """批量删除调拨明细"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以删除明细')

        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or request.form.getlist('ids[]') or request.form.getlist('ids')
        try:
            ids = [int(item_id) for item_id in ids]
        except (TypeError, ValueError):
            return api_error('请选择要删除的明细')

        if not ids:
            return api_error('请选择要删除的明细')

        try:
            TransferOrderItem.query.filter(
                TransferOrderItem.transfer_order_id == id,
                TransferOrderItem.id.in_(ids)
            ).delete(synchronize_session=False)
            db.session.commit()
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除调拨明细失败: {e}')
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def complete_transfer(id):
        from app import (TransferOrder, _acquire_order_write_lock, add_stock_transaction, api_error, deduct_location_inventory_atomic, location_management_enabled, log_operation, update_location_inventory)
        from sqlalchemy.orm import selectinload
        from flask import jsonify
        """完成调拨"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('当前调拨单状态不可完成')

        if not transfer.items:
            return api_error('调拨单没有明细，无法完成')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复扣库位库存
            locked, ok = _acquire_order_write_lock(TransferOrder, id, 'pending', selectinload(TransferOrder.items))
            if not ok:
                return api_error('该调拨单已提交，不能重复操作')
            transfer = locked
            if not transfer.items:
                db.session.rollback()
                return api_error('调拨单没有明细，无法完成')
            # BUG-2026-08-02-013：与入库/出库对齐，未开启库位管理时不写 LocationInventory。
            # 调拨不改变总库存：开启库位管理时在 from_location 原子扣减、to_location 累加；
            # 未开启时只记录双向流水（审计用），不动 LocationInventory。
            use_location = location_management_enabled()
            for item in transfer.items:
                if not item.material_id:
                    continue
                material_code = item.material.code if item.material else str(item.material_id)
                quantity = item.quantity or 0
                if use_location:
                    ok, err = deduct_location_inventory_atomic(
                        item.material_id, transfer.from_location, quantity,
                        material_code_hint=material_code,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err)
                    # 调入方向用老的 update_location_inventory 自动建账即可（非破坏性）
                    ok_in, err_in = update_location_inventory(item.material, transfer.to_location, quantity)
                    if not ok_in:
                        db.session.rollback()
                        return api_error(err_in)
                add_stock_transaction(
                    item.material, -quantity, 'transfer_out',
                    reference_type='transfer',
                    reference_id=transfer.id,
                    location=transfer.from_location,
                    remark=f'调拨到 {transfer.to_location}'
                )
                add_stock_transaction(
                    item.material, quantity, 'transfer_in',
                    reference_type='transfer',
                    reference_id=transfer.id,
                    location=transfer.to_location,
                    remark=f'来自 {transfer.from_location}'
                )

            transfer.status = 'completed'
            db.session.commit()
            log_operation('完成调拨', f'调拨单：{transfer.transfer_no}', 'transfer', id)
            return jsonify({'status': 'success', 'msg': '调拨完成'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'调拨完成失败：{e}')
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def revert_transfer(id):
        from app import (TransferOrder, _acquire_order_write_lock, add_stock_transaction, api_error, location_management_enabled, log_operation, update_location_inventory)
        from sqlalchemy.orm import selectinload
        from flask import jsonify
        """反提交调拨单"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'completed':
            return api_error('只有已完成的调拨单可以反提交')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库位库存重复回退
            locked, ok = _acquire_order_write_lock(TransferOrder, id, 'completed', selectinload(TransferOrder.items))
            if not ok:
                return api_error('该调拨单已反提交，不能重复操作')
            transfer = locked
            # BUG-2026-08-02-013：与 complete_transfer 对称，未开启库位管理时不写 LocationInventory。
            use_location = location_management_enabled()
            for item in transfer.items:
                if item.material:
                    quantity = item.quantity or 0
                    if use_location:
                        ok, error_msg = update_location_inventory(item.material, transfer.to_location, -quantity)
                        if not ok:
                            db.session.rollback()
                            return api_error(error_msg)
                        loc_ok, loc_err = update_location_inventory(item.material, transfer.from_location, quantity)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '来源库位库存恢复失败')
                    add_stock_transaction(
                        item.material, quantity, 'transfer_in',
                        reference_type='transfer',
                        reference_id=transfer.id,
                        location=transfer.from_location,
                        remark=f'反提交调拨 {transfer.transfer_no}'
                    )
                    add_stock_transaction(
                        item.material, -quantity, 'transfer_out',
                        reference_type='transfer',
                        reference_id=transfer.id,
                        location=transfer.to_location,
                        remark=f'反提交调拨 {transfer.transfer_no}'
                    )

            transfer.status = 'pending'
            db.session.commit()
            log_operation('反提交调拨', f'调拨单：{transfer.transfer_no}', 'transfer', id)
            return jsonify({'status': 'success', 'msg': '反提交成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'反提交调拨失败: {e}')
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/update', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_transfer(id):
        from app import (TransferOrder, api_error, log_operation)
        from flask import jsonify, request
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以修改')
        try:
            remark = (request.form.get('remark') or '').strip()
            transfer.remark = remark
            db.session.commit()
            log_operation('修改调拨单', f'调拨单：{transfer.transfer_no}', 'transfer', id)
            return jsonify({'status': 'success', 'msg': '修改成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('修改失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/copy', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def copy_transfer(id):
        from app import (TransferOrder, TransferOrderItem, api_error, generate_order_no, log_operation)
        from flask import jsonify
        transfer = TransferOrder.query.get_or_404(id)
        try:
            transfer_no = generate_order_no('TF')
            new_transfer = TransferOrder(
                transfer_no=transfer_no,
                from_location=transfer.from_location,
                to_location=transfer.to_location,
                remark=transfer.remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(new_transfer)
            db.session.flush()
            for item in transfer.items:
                new_item = TransferOrderItem(
                    transfer_order_id=new_transfer.id,
                    material_id=item.material_id,
                    quantity=item.quantity,
                    unit_id=item.unit_id,
                    price=item.price or 0,
                    amount=item.amount or 0,
                    remark=item.remark
                )
                db.session.add(new_item)
            db.session.commit()
            log_operation('复制调拨单', f'从 {transfer.transfer_no} 复制为 {new_transfer.transfer_no}', 'transfer', new_transfer.id)
            return jsonify({'status': 'success', 'msg': '复制成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_transfer(id):
        from app import (TransferOrder, TransferOrderItem,
                         _acquire_order_write_lock, api_error, log_operation)
        from flask import jsonify
        """删除调拨单"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以删除')

        try:
            # 重新锁定并校验草稿状态，防止并发完成后仍被物理删除。
            locked, ok = _acquire_order_write_lock(TransferOrder, id, 'pending')
            if not ok:
                return jsonify({'status': 'error', 'msg': '该调拨单状态已变更；已完成单请先反提交后再删除'}), 409
            transfer = locked

            # 删除明细
            TransferOrderItem.query.filter_by(transfer_order_id=id).delete()
            db.session.delete(transfer)
            db.session.commit()

            log_operation('删除调拨单', f'调拨单：{transfer.transfer_no}', 'transfer', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/batch_delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_transfer():
        from app import (TransferOrder, TransferOrderItem,
                         _acquire_order_write_lock, api_error, log_operation)
        from flask import jsonify, request
        """批量删除草稿调拨单"""
        ids = request.form.getlist('ids[]') or request.form.getlist('ids')
        data = request.get_json(silent=True) or {}
        if not ids and data.get('ids'):
            ids = data.get('ids')
        try:
            ids = [int(item_id) for item_id in ids]
        except (TypeError, ValueError):
            return api_error('请选择要删除的记录')

        if not ids:
            return api_error('请选择要删除的记录')

        transfers = TransferOrder.query.filter(TransferOrder.id.in_(ids)).all()
        blocked = [transfer.transfer_no for transfer in transfers if transfer.status != 'pending']
        if blocked:
            return api_error('只能删除草稿调拨单：' + '、'.join(blocked))

        deleted_count = 0
        skipped = []
        # 逐条加写锁并独立提交，单点失败仅回滚自身，不影响其余单据。
        for transfer_id in ids:
            transfer_no = None
            try:
                locked, ok = _acquire_order_write_lock(TransferOrder, transfer_id, 'pending')
                if not ok or locked is None:
                    existing = TransferOrder.query.get(transfer_id)
                    transfer_no = existing.transfer_no if existing else f'ID:{transfer_id}'
                    skipped.append(f'{transfer_no}(状态已变更)')
                    db.session.rollback()
                    continue
                transfer = locked
                transfer_no = transfer.transfer_no
                TransferOrderItem.query.filter_by(transfer_order_id=transfer_id).delete()
                db.session.delete(transfer)
                db.session.commit()
                deleted_count += 1
            except Exception:
                db.session.rollback()
                skipped.append(f'{transfer_no or f"ID:{transfer_id}"}(错误)')
                app.logger.exception('批量删除调拨单失败: ID=%s', transfer_id)

        msg = f'批量删除完成，共删除 {deleted_count} 张调拨单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        log_operation('批量删除调拨单', f'共删除 {deleted_count} 张调拨单', 'transfer')
        return jsonify({'status': 'success', 'msg': msg, 'deleted': deleted_count, 'skipped': skipped})

    @app.route('/transfer/export')
    @login_required
    def export_transfer():
        from app import (Material, TransferOrder, TransferOrderItem, _apply_status_date_filters, _get_order_list_filters, _status_from_search_keyword, _workbook_response)
        from sqlalchemy.orm import selectinload
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed', 'cancelled'))
        allowed_sorts = {'transfer_no', 'date', 'from_location', 'to_location', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = TransferOrder.query.options(
            selectinload(TransferOrder.items).joinedload(TransferOrderItem.material).joinedload(Material.unit),
            selectinload(TransferOrder.items).joinedload(TransferOrderItem.unit),
        )
        query = _apply_status_date_filters(query, TransferOrder, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed', 'cancelled'))
            conditions = [
                TransferOrder.transfer_no.like(search_like),
                TransferOrder.from_location.like(search_like),
                TransferOrder.to_location.like(search_like),
                TransferOrder.remark.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(TransferOrder.status == status_from_search)
            query = query.outerjoin(TransferOrderItem, TransferOrderItem.transfer_order_id == TransferOrder.id).outerjoin(
                Material, TransferOrderItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(TransferOrder, sort_by, TransferOrder.created_at)
        orders = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for order in orders:
            if order.items:
                for item in order.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        order.transfer_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order.from_location or '',
                        order.to_location or '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        item.quantity or 0,
                        item.price or 0,
                        item.amount or 0,
                        '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')),
                        order.remark or '',
                    ])
            else:
                rows.append([order.transfer_no, order.date.strftime('%Y-%m-%d') if order.date else '', order.from_location or '', order.to_location or '', '', '', '', '', 0, 0, 0, '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')), order.remark or ''])
        return _workbook_response(
            'transfer_orders.xlsx',
            '库存调拨',
            ['单据编号', '日期', '调出仓库', '调入仓库', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '金额', '状态', '备注'],
            rows,
        )

    @app.route('/export/template/transfer')
    @login_required
    def export_transfer_template():
        from app import (_workbook_response)
        return _workbook_response(
            'transfer_template.xlsx',
            '库存调拨导入模板',
            ['单据编号', '日期', '调出仓库', '调入仓库', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注'],
            [['TF24010001', '2024-01-01', '材料仓', '成品仓', 'MAT001', '示例物料', '规格A', '个', 10, 0, '']],
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/import', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def import_transfer():
        from app import (TransferOrder, TransferOrderItem, _find_or_create_material, _find_or_create_warehouse, _get_excel_cell, _get_excel_number, _import_result, _order_no_from_row, _parse_excel_date, _read_import_sheet, api_error, round_to_2_decimals, validate_excel_extension, validate_excel_size)
        from flask import request
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的库存调拨文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['单据编号', '调拨单号', '订单编号'],
            'date': ['日期'],
            'from_location': ['调出仓库', '调出库', '源仓库'],
            'to_location': ['调入仓库', '调入库', '目标仓库'],
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
            required = {'from_location', 'to_location', 'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（调出仓库、调入仓库、物料编码、数量）。检测到的表头：{", ".join(header_row)}')
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
                order_no = _order_no_from_row(row, col_map, 'order_no', 'TF')
                order = orders_by_no.get(order_no)
                if not order:
                    if TransferOrder.query.filter_by(transfer_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：调拨单号 {order_no} 已存在')
                        continue
                    from_location = _get_excel_cell(row, col_map, 'from_location')
                    to_location = _get_excel_cell(row, col_map, 'to_location')
                    if not from_location or not to_location or from_location == to_location:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：调出/调入仓库不正确')
                        continue
                    _find_or_create_warehouse(from_location)
                    _find_or_create_warehouse(to_location)
                    order = TransferOrder(
                        transfer_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        from_location=from_location,
                        to_location=to_location,
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        status='pending',
                        operator_id=current_user.id,
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
                db.session.add(TransferOrderItem(
                    transfer_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                    remark=(_get_excel_cell(row, col_map, 'remark') or '').strip() or None,
                ))
                item_count += 1
            db.session.commit()
            return _import_result('库存调拨单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调拨导入失败: {e}')
            return api_error(f'库存调拨导入失败：{str(e)}')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/transfer/<int:id>/batch_add_items', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_add_transfer_items(id):
        from app import (Material, TransferOrder, TransferOrderItem, allow_negative_stock, api_error, is_stock_sufficient, parse_float_value, round_to_2_decimals)
        from flask import jsonify, request
        """批量粘贴添加调拨明细，格式：编码,数量,单价"""
        transfer = TransferOrder.query.get_or_404(id)
        if transfer.status != 'pending':
            return api_error('只有草稿状态的调拨单可以添加明细')

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
                quantity = parse_float_value(parts[1] if len(parts) > 1 else None, 0)
                price = parse_float_value(parts[2] if len(parts) > 2 else None, 0)
                if not material_code or quantity <= 0:
                    errors.append(f'第 {line_no} 行格式不正确')
                    continue

                material = Material.query.filter_by(code=material_code).first()
                if not material:
                    errors.append(f'第 {line_no} 行物料不存在：{material_code}')
                    continue
                if not allow_negative_stock() and not is_stock_sufficient(material.stock or 0, quantity):
                    errors.append(f'第 {line_no} 行库存不足：{material_code}')
                    continue

                item = TransferOrderItem(
                    transfer_order_id=id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id,
                    price=round_to_2_decimals(price),
                    amount=round_to_2_decimals(quantity * price)
                )
                db.session.add(item)
                added += 1

            if added == 0:
                return api_error(errors[0] if errors else '未添加任何明细')
            db.session.commit()
            msg = f'成功添加 {added} 条'
            if errors:
                msg += '，部分行失败：' + '；'.join(errors[:3])
            return jsonify({'status': 'success', 'msg': msg})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量添加调拨明细失败: {e}')
            return api_error('添加失败，请稍后重试')

    @app.route('/transfer/<int:id>/export')
    @login_required
    def export_single_transfer(id):
        from app import (TransferOrder)
        from flask import send_file
        from openpyxl import Workbook
        order = TransferOrder.query.get_or_404(id)
        wb = Workbook()
        ws = wb.active
        ws.title = '调拨单'
        ws.append(['单据编号', '日期', '调出仓库', '调入仓库', '物料编码', '物料名称', '规格', '单位', '数量', '备注'])
        if order.items:
            for item in order.items:
                ws.append([
                    order.transfer_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    order.from_location or '',
                    order.to_location or '',
                    item.material.code if item.material else '',
                    item.material.name if item.material else '',
                    item.material.spec if item.material else '',
                    item.material.unit.name if item.material and item.material.unit else '',
                    item.quantity or 0,
                    order.remark or ''
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name=f'transfer_{order.transfer_no}.xlsx', as_attachment=True)

    @app.route('/transfer/<int:id>/print')
    @login_required
    def print_single_transfer(id):
        from app import (Material, TransferOrder, TransferOrderItem)
        from sqlalchemy.orm import joinedload
        from flask import render_template
        """调拨单打印页"""
        transfer = TransferOrder.query.options(
            joinedload(TransferOrder.items).joinedload(TransferOrderItem.material).joinedload(Material.unit),
            joinedload(TransferOrder.operator)
        ).get_or_404(id)
        return render_template('transfer_print.html', transfer=transfer)
