#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 盘点（check）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_check_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 check_list、check_detail、
# save_check_table、add_check、complete_check、revert_check、
# add_check_item、update_check_item、update_check、copy_check、
# delete_check、batch_delete_check、delete_check_item、export_check、
# import_check、export_single_check、print_single_check 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（InventoryCheck 模型、InventoryCheckItem、Material、
#   AdjustmentOrder、AdjustmentOrderItem、StockTransaction、get_default_warehouse、
#   get_active_warehouses、generate_order_no、log_operation、api_error、
#   round_to_2_decimals、parse_float_value、_clean_int、_parse_form_date、
#   _material_from_payload、_render_check_form、_acquire_order_write_lock、
#   _create_adjustment_drafts_from_check、normalize_stock_quantity、
#   deduct_stock_atomic、add_stock、_workbook_response、validate_excel_extension、
#   validate_excel_size、_read_import_sheet、_get_excel_cell、_order_no_from_row、
#   _parse_excel_date、_find_or_create_material、_get_excel_number、_import_result、
#   _get_order_list_filters、_apply_status_date_filters、_status_from_search_keyword 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_check_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json

from flask import jsonify, render_template, request, send_file
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 check_* 各路由测试覆盖
def register_check_routes(app):
    @app.route('/check')
    @login_required
    def check_list():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword, get_active_warehouses,
                         get_default_warehouse)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'check_no', 'date', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = InventoryCheck.query.options(
            joinedload(InventoryCheck.operator),
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material)
        )
        query = _apply_status_date_filters(query, InventoryCheck, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed'))
            conditions = [
                InventoryCheck.check_no.like(search_like),
                InventoryCheck.remark.like(search_like),
                InventoryCheckItem.reason.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(InventoryCheck.status == status_from_search)
            query = query.outerjoin(InventoryCheckItem, InventoryCheckItem.inventory_check_id == InventoryCheck.id).outerjoin(
                Material, InventoryCheckItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(InventoryCheck, sort_by, InventoryCheck.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        checks = pagination.items
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template(
            'check.html',
            checks=checks,
            pagination=pagination,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            per_page=per_page,
            # BUG-2026-08-02-014：盘点列表新增弹窗需要仓库下拉 + 默认仓库预选
            warehouses=get_active_warehouses(),
            default_warehouse=get_default_warehouse(),
        )

    @app.route('/check/<int:id>')
    @login_required
    def check_detail(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InventoryCheck, InventoryCheckItem, Material, _render_check_form)
        check = InventoryCheck.query.options(
            joinedload(InventoryCheck.operator),
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit)
        ).get_or_404(id)
        return _render_check_form(check)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/save_table', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def save_check_table():
        from datetime import date
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, _clean_int,
                         _material_from_payload, _parse_form_date, api_error,
                         generate_order_no, get_default_warehouse, log_operation,
                         parse_float_value, round_to_2_decimals,
                         validate_inventory_warehouse)
        data = request.get_json(silent=True) or {}
        order_id = _clean_int(data.get('order_id'))
        check_no = (data.get('order_no') or data.get('check_no') or '').strip() or generate_order_no('CK')
        header = data.get('header') or {}
        items_data = data.get('items') or []

        if not items_data:
            return api_error('请至少填写一条盘点明细')

        # BUG-2026-08-02-013：仓库必填（AGENTS.md 规则），未填写时自动带入默认仓库
        warehouse = (header.get('warehouse') or data.get('warehouse') or '').strip()
        if not warehouse:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse:
            return api_error('请选择仓库')
        # INV-AUDIT-005：仓库必须存在且 active
        wh_obj, wh_err = validate_inventory_warehouse(warehouse)
        if wh_err:
            return api_error(wh_err)
        warehouse = wh_obj.name

        try:
            if order_id:
                check = db.session.get(InventoryCheck, order_id)
                if not check:
                    return api_error('盘点单不存在，请刷新后重试')
                if check.status != 'pending':
                    return api_error('只有草稿状态的盘点单可以修改')
                duplicate = InventoryCheck.query.filter(InventoryCheck.check_no == check_no, InventoryCheck.id != order_id).first()
                if duplicate:
                    return api_error('盘点单号已存在')
            else:
                check = InventoryCheck.query.filter_by(check_no=check_no).first()
                if check:
                    if check.status != 'pending':
                        return api_error('盘点单号已存在')
                else:
                    check = InventoryCheck(check_no=check_no, status='pending', operator_id=current_user.id)
                    db.session.add(check)

            check.check_no = check_no
            check.date = _parse_form_date(data.get('date'), check.date if order_id else date.today())
            check.remark = (header.get('remark') or '').strip()
            check.warehouse = warehouse
            if not check.operator_id:
                check.operator_id = current_user.id
            db.session.flush()
            InventoryCheckItem.query.filter_by(inventory_check_id=check.id).delete()

            for item_data in items_data:
                material = _material_from_payload(item_data)
                if not material:
                    return api_error(f'物料不存在：{item_data.get("code") or ""}')
                system_stock = round_to_2_decimals(parse_float_value(item_data.get('system_stock'), material.stock or 0))
                actual_stock = round_to_2_decimals(parse_float_value(item_data.get('actual_stock'), system_stock))
                db.session.add(InventoryCheckItem(
                    inventory_check_id=check.id,
                    material_id=material.id,
                    system_stock=system_stock,
                    actual_stock=actual_stock,
                    difference=round_to_2_decimals(actual_stock - system_stock),
                    reason=(item_data.get('reason') or item_data.get('remark') or '').strip()
                ))

            db.session.commit()
            log_operation('保存盘点单', f'盘点单：{check.check_no}', 'check', check.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': check.id, 'order_no': check.check_no})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存盘点单表格失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_check():
        from flask_login import current_user
        from app import (InventoryCheck, api_error, generate_order_no,
                         get_default_warehouse, log_operation,
                         validate_inventory_warehouse)
        try:
            remark = (request.form.get('remark') or '').strip()
            # BUG-2026-08-02-013：仓库必填，未填写时自动带入默认仓库
            warehouse = (request.form.get('warehouse') or '').strip()
            if not warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            if not warehouse:
                return api_error('请选择仓库')
            # INV-AUDIT-005：仓库必须存在且 active
            wh_obj, wh_err = validate_inventory_warehouse(warehouse)
            if wh_err:
                return api_error(wh_err)
            warehouse = wh_obj.name
            check_no = generate_order_no('CK')
            check = InventoryCheck(
                check_no=check_no,
                remark=remark,
                warehouse=warehouse,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(check)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500
            log_operation('盘点单创建', f'盘点单：{check.check_no}', 'check', check.id)
            return jsonify({'status': 'success', 'id': check.id})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def complete_check(id):
        from sqlalchemy.orm import selectinload
        from app import (InventoryCheck, _acquire_order_write_lock,
                         _create_adjustment_drafts_from_check, api_error, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('当前盘点单状态不可完结')

        if not check.items:
            return api_error('盘点单没有明细，无法完成')
        if not check.warehouse:
            return api_error('盘点单未指定仓库，无法完成')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复生成调整草稿
            locked, ok = _acquire_order_write_lock(InventoryCheck, id, 'pending', selectinload(InventoryCheck.items))
            if not ok:
                return api_error('该盘点单已提交，不能重复操作')
            check = locked
            if not check.items:
                db.session.rollback()
                return api_error('盘点单没有明细，无法完成')
            drafts, error = _create_adjustment_drafts_from_check(check)
            if error:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': error}), 400

            check.status = 'completed'
            db.session.commit()
            draft_nos = ', '.join(order.adjustment_no for order in drafts)
            if drafts:
                log_operation('盘点完成', f'盘点单：{check.check_no}，生成调整草稿：{draft_nos}', 'check', id)
                return jsonify({
                    'status': 'success',
                    'msg': f'盘点完成，已生成库存调整草稿：{draft_nos}。请审核调整单后提交库存变动。',
                    'adjustment_ids': [order.id for order in drafts],
                    'adjustment_nos': [order.adjustment_no for order in drafts],
                })

            log_operation('盘点完成', f'盘点单：{check.check_no}，无库存差异', 'check', id)
            return jsonify({'status': 'success', 'msg': '盘点完成，无库存差异，不需要生成调整单'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'盘点完成失败：{e}')
            return api_error('盘点完成失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def revert_check(id):
        from sqlalchemy.orm import selectinload
        from app import (AdjustmentOrder, InventoryCheck, StockTransaction,
                         _acquire_order_write_lock, add_stock, api_error,
                         deduct_stock_atomic, log_operation, normalize_stock_quantity)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'completed':
            return api_error('只有已完成的盘点单可以反提交')
        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复回退
            locked, ok = _acquire_order_write_lock(InventoryCheck, id, 'completed', selectinload(InventoryCheck.items))
            if not ok:
                return api_error('该盘点单已反提交，不能重复操作')
            check = locked
            linked_adjustments = AdjustmentOrder.query.filter_by(source_type='check', source_id=check.id).all()
            completed_adjustments = [order.adjustment_no for order in linked_adjustments if order.status == 'completed']
            if completed_adjustments:
                db.session.rollback()
                return api_error('该盘点单生成的调整单已提交，不能直接反提交盘点单：' + ', '.join(completed_adjustments))

            transactions = StockTransaction.query.filter(
                StockTransaction.reference_type == 'inventory_check',
                StockTransaction.reference_id == check.id,
                StockTransaction.transaction_type.in_(('check_in', 'check_out'))
            ).all()
            for transaction in transactions:
                material = transaction.material
                if not material:
                    continue
                quantity = normalize_stock_quantity(transaction.quantity or 0)
                if quantity > 0:
                    ok, err, _ = deduct_stock_atomic(
                        material.id,
                        quantity,
                        transaction_type='revert_check_in',
                        reference_type='inventory_check',
                        reference_id=check.id,
                        remark=f'反提交盘点 {check.check_no}',
                        warehouse=check.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err)
                elif quantity < 0:
                    ok, err = add_stock(
                        material,
                        abs(quantity),
                        transaction_type='revert_check_out',
                        reference_type='inventory_check',
                        reference_id=check.id,
                        remark=f'反提交盘点 {check.check_no}',
                        warehouse=check.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存恢复失败')
            for order in linked_adjustments:
                if order.status == 'pending':
                    for item in list(order.items):
                        db.session.delete(item)
                    db.session.delete(order)
            check.status = 'pending'
            db.session.commit()
            log_operation('反提交盘点', f'盘点单：{check.check_no}', 'check', id)
            if transactions:
                return jsonify({'status': 'success', 'msg': '反提交成功，库存已恢复到盘点前'})
            return jsonify({'status': 'success', 'msg': '反提交成功，已删除未提交的库存调整草稿'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'盘点反提交失败: {e}')
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/add_item', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_check_item(id):
        """添加盘点明细"""
        from app import (InventoryCheck, InventoryCheckItem, Material, api_error, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以添加明细')
        
        material_id = request.form.get('material_id')
        if not material_id:
            return api_error('请选择物料')
        
        try:
            material_id = int(material_id)
        except (ValueError, TypeError):
            return api_error('物料ID格式不正确')
        
        material = Material.query.get(material_id)
        if not material:
            return api_error('物料不存在')
        
        # 检查是否已存在该物料的盘点记录
        existing_item = InventoryCheckItem.query.filter_by(
            inventory_check_id=id, 
            material_id=material_id
        ).first()
        
        if existing_item:
            return api_error(f'物料 {material.code} 已存在于盘点单中')
        
        try:
            # 创建盘点明细，系统库存为当前库存，实际库存默认为系统库存
            system_stock = material.stock or 0
            item = InventoryCheckItem(
                inventory_check_id=id,
                material_id=material_id,
                system_stock=system_stock,
                actual_stock=system_stock,
                difference=0
            )
            db.session.add(item)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '添加失败，请稍后重试'}), 500
            
            log_operation('添加盘点明细', f'盘点单：{check.check_no}，物料：{material.code}', 'check', id)
            return jsonify({'status': 'success', 'msg': '盘点明细添加成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/item/<int:item_id>', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_check_item(id, item_id):
        """更新盘点明细的实际库存"""
        from app import (InventoryCheck, InventoryCheckItem, api_error, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以修改明细')
        
        item = InventoryCheckItem.query.get_or_404(item_id)
        if item.inventory_check_id != id:
            return api_error('盘点明细不属于当前盘点单')
        
        try:
            actual_stock = float(request.form.get('actual_stock', item.actual_stock))
        except (ValueError, TypeError):
            return api_error('实际库存必须是数字')
        
        try:
            item.actual_stock = actual_stock
            item.difference = actual_stock - item.system_stock
            db.session.commit()
            
            log_operation('更新盘点明细', f'盘点单：{check.check_no}，物料：{item.material.code if item.material else ""}', 'check', id)
            return jsonify({'status': 'success', 'msg': '盘点数量已更新'})
        except Exception as e:
            db.session.rollback()
            return api_error('更新失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/update', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_check(id):
        from app import InventoryCheck, api_error, log_operation
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以修改')
        try:
            remark = (request.form.get('remark') or '').strip()
            check.remark = remark
            db.session.commit()
            log_operation('修改盘点单', f'盘点单：{check.check_no}', 'check', id)
            return jsonify({'status': 'success', 'msg': '修改成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('修改失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/copy', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def copy_check(id):
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, api_error,
                         generate_order_no, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        try:
            check_no = generate_order_no('CK')
            new_check = InventoryCheck(
                check_no=check_no,
                remark=check.remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(new_check)
            db.session.flush()
            for item in check.items:
                new_item = InventoryCheckItem(
                    inventory_check_id=new_check.id,
                    material_id=item.material_id,
                    system_stock=item.system_stock,
                    actual_stock=item.actual_stock,
                    difference=item.difference
                )
                db.session.add(new_item)
            db.session.commit()
            log_operation('复制盘点单', f'从 {check.check_no} 复制为 {new_check.check_no}', 'check', new_check.id)
            return jsonify({'status': 'success', 'msg': '复制成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_check(id):
        """删除盘点单"""
        from app import (InventoryCheck, InventoryCheckItem,
                         _acquire_order_write_lock, api_error, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以删除')

        try:
            # 重新锁定并校验草稿状态，防止并发完成后仍被物理删除。
            locked, ok = _acquire_order_write_lock(InventoryCheck, id, 'pending')
            if not ok:
                return jsonify({'status': 'error', 'msg': '该盘点单状态已变更；已完成单请先反提交后再删除'}), 409
            check = locked

            # 删除明细
            InventoryCheckItem.query.filter_by(inventory_check_id=id).delete()
            db.session.delete(check)
            db.session.commit()

            log_operation('删除盘点单', f'盘点单：{check.check_no}', 'check', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/batch_delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_check():
        """批量删除盘点单"""
        from app import (InventoryCheck, InventoryCheckItem,
                         _acquire_order_write_lock, api_error, log_operation)
        try:
            data = request.get_json(silent=True) or {}
            ids = data.get('ids')
            if not ids:
                ids = json.loads(request.form.get('ids', '[]'))
            if not ids:
                return api_error('请选择要删除的盘点单')

            deleted_count = 0
            skipped = []
            # 逐条加写锁并独立提交，单点失败仅回滚自身，不影响其余单据。
            for check_id in ids:
                check_no = None
                try:
                    locked, ok = _acquire_order_write_lock(InventoryCheck, check_id, 'pending')
                    if not ok or locked is None:
                        # 重新读取单号用于跳过提示
                        existing = InventoryCheck.query.get(check_id)
                        check_no = existing.check_no if existing else f'ID:{check_id}'
                        skipped.append(f'{check_no}(状态已变更)')
                        db.session.rollback()
                        continue
                    check = locked
                    check_no = check.check_no
                    InventoryCheckItem.query.filter_by(inventory_check_id=check_id).delete()
                    db.session.delete(check)
                    db.session.commit()
                    deleted_count += 1
                except Exception:
                    db.session.rollback()
                    skipped.append(f'{check_no or f"ID:{check_id}"}(错误)')
                    app.logger.exception('批量删除盘点单失败: ID=%s', check_id)

            msg = f'成功删除 {deleted_count} 个盘点单'
            if skipped:
                msg += f'，跳过 {len(skipped)} 个：{", ".join(skipped[:10])}'

            log_operation('批量删除盘点单', f'删除 {deleted_count} 个盘点单', 'check', None)
            return jsonify({'status': 'success', 'msg': msg, 'deleted': deleted_count, 'skipped': skipped})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_check_item(id, item_id):
        """删除盘点明细"""
        from app import InventoryCheck, InventoryCheckItem, api_error, log_operation
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以删除明细')
        
        item = InventoryCheckItem.query.get_or_404(item_id)
        if item.inventory_check_id != id:
            return api_error('盘点明细不属于当前盘点单')
        
        try:
            material_code = item.material.code if item.material else ''
            db.session.delete(item)
            db.session.commit()
            
            log_operation('删除盘点明细', f'盘点单：{check.check_no}，物料：{material_code}', 'check', id)
            return jsonify({'status': 'success', 'msg': '盘点明细删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    @app.route('/check/export')
    @login_required
    def export_check():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword, _workbook_response)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'check_no', 'date', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = InventoryCheck.query.options(
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit)
        )
        query = _apply_status_date_filters(query, InventoryCheck, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed'))
            conditions = [
                InventoryCheck.check_no.like(search_like),
                InventoryCheck.remark.like(search_like),
                InventoryCheckItem.reason.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(InventoryCheck.status == status_from_search)
            query = query.outerjoin(InventoryCheckItem, InventoryCheckItem.inventory_check_id == InventoryCheck.id).outerjoin(
                Material, InventoryCheckItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(InventoryCheck, sort_by, InventoryCheck.created_at)
        checks = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for check in checks:
            if check.items:
                for item in check.items:
                    material = item.material
                    rows.append([
                        check.check_no,
                        check.date.strftime('%Y-%m-%d') if check.date else '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        material.unit.name if material and material.unit else '',
                        item.system_stock or 0,
                        item.actual_stock or 0,
                        item.difference or 0,
                        item.reason or '',
                        '草稿' if check.status == 'pending' else ('已完成' if check.status == 'completed' else (check.status or '')),
                        check.remark or '',
                    ])
            else:
                rows.append([check.check_no, check.date.strftime('%Y-%m-%d') if check.date else '', '', '', '', '', 0, 0, 0, '', '草稿' if check.status == 'pending' else ('已完成' if check.status == 'completed' else (check.status or '')), check.remark or ''])
        return _workbook_response(
            'inventory_checks.xlsx',
            '库存盘点',
            ['单据编号', '日期', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异数量', '差异原因', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/import', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def import_check():
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, _find_or_create_material,
                         _get_excel_cell, _get_excel_number, _import_result,
                         _order_no_from_row, _parse_excel_date, _read_import_sheet,
                         api_error, round_to_2_decimals, validate_excel_extension,
                         validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的库存盘点文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['单据编号', '盘点单号', '订单编号'],
            'date': ['日期'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'system_stock': ['系统库存', '账面库存'],
            'actual_stock': ['实际库存', '盘点库存'],
            'reason': ['差异原因', '原因'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'material_code', 'actual_stock'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（物料编码、实际库存）。检测到的表头：{", ".join(header_row)}')
            checks_by_no = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                material_code = _get_excel_cell(row, col_map, 'material_code')
                if not material_code:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料编码为空')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'CK')
                check = checks_by_no.get(order_no)
                if not check:
                    if InventoryCheck.query.filter_by(check_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：盘点单号 {order_no} 已存在')
                        continue
                    check = InventoryCheck(
                        check_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        status='pending',
                        operator_id=current_user.id,
                    )
                    db.session.add(check)
                    db.session.flush()
                    checks_by_no[order_no] = check
                    order_count += 1
                material = _find_or_create_material(
                    material_code,
                    _get_excel_cell(row, col_map, 'material_name'),
                    _get_excel_cell(row, col_map, 'spec'),
                    _get_excel_cell(row, col_map, 'unit'),
                )
                system_stock = _get_excel_number(row, col_map, 'system_stock', material.stock or 0)
                actual_stock = _get_excel_number(row, col_map, 'actual_stock', system_stock)
                db.session.add(InventoryCheckItem(
                    inventory_check_id=check.id,
                    material_id=material.id,
                    system_stock=system_stock,
                    actual_stock=actual_stock,
                    difference=round_to_2_decimals(actual_stock - system_stock),
                    reason=_get_excel_cell(row, col_map, 'reason'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('库存盘点单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存盘点导入失败: {e}')
            return api_error(f'库存盘点导入失败：{str(e)}')

    @app.route('/check/<int:id>/export')
    @login_required
    def export_single_check(id):
        import io
        from openpyxl import Workbook
        from app import InventoryCheck
        check = InventoryCheck.query.get_or_404(id)
        wb = Workbook()
        ws = wb.active
        ws.title = '盘点单'
        ws.append(['单据编号', '日期', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异数量', '备注'])
        if check.items:
            for item in check.items:
                ws.append([
                    check.check_no,
                    check.date.strftime('%Y-%m-%d') if check.date else '',
                    item.material.code if item.material else '',
                    item.material.name if item.material else '',
                    item.material.spec if item.material else '',
                    item.material.unit.name if item.material and item.material.unit else '',
                    item.system_stock or 0,
                    item.actual_stock or 0,
                    item.difference or 0,
                    item.reason or ''
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name=f'check_{check.check_no}.xlsx', as_attachment=True)

    @app.route('/check/<int:id>/print')
    @login_required
    def print_single_check(id):
        from sqlalchemy.orm import joinedload
        from app import InventoryCheck, InventoryCheckItem, Material
        check = InventoryCheck.query.options(
            joinedload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit),
            joinedload(InventoryCheck.operator)
        ).get_or_404(id)
        return render_template('check_print.html', check=check)