#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 领料出库（requisition）域路由。
#
# 批量拆分模式：与合同（contract）域一致，采用「register_requisition_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 requisition_list、
# requisition_detail、save_requisition_table、complete_requisition 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（ProductionRequisition 模型、ProductionRequisitionItem、
#   各辅助函数 _render_requisition_form / _get_order_list_filters /
#   _apply_status_date_filters / api_error / _workbook_response /
#   validate_excel_extension / validate_excel_size / _read_import_sheet /
#   _get_excel_cell / _get_excel_number / _order_no_from_row 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_xxx_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import jsonify, render_template, request, send_file
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 requisition_* 各路由测试覆盖
def register_requisition_routes(app):
    @app.route('/requisition')
    @login_required
    def requisition_list():
        from app import (BOM, Material, ProductionRequisition,
                         ProductionRequisitionItem, _apply_status_date_filters,
                         _get_order_list_filters, _status_from_search_keyword)
        from sqlalchemy.orm import joinedload, selectinload
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'req_no', 'date', 'production_order', 'purpose', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = ProductionRequisition.query.options(
            joinedload(ProductionRequisition.operator),
            joinedload(ProductionRequisition.bom),
            selectinload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.material)
        )
        query = _apply_status_date_filters(query, ProductionRequisition, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed'))
            conditions = [
                ProductionRequisition.req_no.like(search_like),
                ProductionRequisition.production_order.like(search_like),
                ProductionRequisition.purpose.like(search_like),
                ProductionRequisition.warehouse.like(search_like),
                ProductionRequisition.remark.like(search_like),
                BOM.bom_no.like(search_like),
                BOM.product_name.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(ProductionRequisition.status == status_from_search)
            query = query.outerjoin(BOM, ProductionRequisition.bom_id == BOM.id).outerjoin(
                ProductionRequisitionItem, ProductionRequisitionItem.requisition_id == ProductionRequisition.id
            ).outerjoin(Material, ProductionRequisitionItem.material_id == Material.id).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(ProductionRequisition, sort_by, ProductionRequisition.created_at)
        requisitions = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        boms = BOM.query.all()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template('requisition.html', requisitions=requisitions, boms=boms, filters=filters, sort_by=sort_by, sort_order=sort_order)

    @app.route('/production_requisition/add')
    @app.route('/production_requisition')
    @app.route('/requisition/add', methods=['GET'])
    @login_required
    def requisition_legacy_page():
        from app import _render_requisition_form
        return _render_requisition_form()

    @app.route('/requisition/<int:id>')
    @login_required
    def requisition_detail(id):
        from app import (Material, ProductionRequisition,
                         ProductionRequisitionItem, _render_requisition_form)
        from sqlalchemy.orm import joinedload, selectinload
        requisition = ProductionRequisition.query.options(
            joinedload(ProductionRequisition.operator),
            joinedload(ProductionRequisition.bom),
            selectinload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.material).joinedload(Material.unit),
            selectinload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.unit)
        ).get_or_404(id)
        return _render_requisition_form(requisition)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/save_table', methods=['POST'])
    @require_role('production')
    @login_required
    def save_requisition_table():
        from datetime import date
        from flask_login import current_user
        from app import (ProductionRequisition, ProductionRequisitionItem,
                         _clean_int, _material_from_payload, _parse_form_date,
                         allow_negative_stock, api_error, generate_order_no,
                         get_default_warehouse, is_stock_sufficient,
                         log_operation,
                         normalize_stock_quantity, parse_float_value,
                         round_to_2_decimals)
        data = request.get_json(silent=True) or {}
        order_id = _clean_int(data.get('order_id'))
        req_no = (data.get('order_no') or data.get('req_no') or '').strip() or generate_order_no('REQ')
        header = data.get('header') or {}
        items_data = data.get('items') or []

        if not items_data:
            return api_error('请至少填写一条工单领料明细')

        # BUG-2026-08-05-008：仓库必填（AGENTS.md 规则），未填写时自动带入默认仓库
        warehouse = (header.get('warehouse') or data.get('warehouse') or '').strip()
        if not warehouse:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse:
            return api_error('请选择仓库')

        try:
            if order_id:
                requisition = db.session.get(ProductionRequisition, order_id)
                if not requisition:
                    return api_error('工单领料单不存在，请刷新后重试')
                if requisition.status != 'pending':
                    return api_error('只有草稿状态的工单领料单可以修改')
                duplicate = ProductionRequisition.query.filter(
                    ProductionRequisition.req_no == req_no,
                    ProductionRequisition.id != order_id
                ).first()
                if duplicate:
                    return api_error('工单领料单号已存在')
            else:
                requisition = ProductionRequisition.query.filter_by(req_no=req_no).first()
                if requisition:
                    if requisition.status != 'pending':
                        return api_error('工单领料单号已存在')
                else:
                    requisition = ProductionRequisition(req_no=req_no, status='pending', operator_id=current_user.id)
                    db.session.add(requisition)

            requisition.req_no = req_no
            requisition.date = _parse_form_date(data.get('date'), requisition.date if order_id else date.today())
            requisition.bom_id = _clean_int(header.get('bom_id'))
            requisition.production_order = (header.get('production_order') or '').strip()
            requisition.purpose = (header.get('purpose') or '').strip()
            requisition.warehouse = warehouse
            requisition.remark = (header.get('remark') or '').strip()
            if not requisition.operator_id:
                requisition.operator_id = current_user.id
            db.session.flush()
            ProductionRequisitionItem.query.filter_by(requisition_id=requisition.id).delete()

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
                db.session.add(ProductionRequisitionItem(
                    requisition_id=requisition.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=_clean_int(item_data.get('unit_id')) or material.unit_id,
                    remark=(item_data.get('remark') or '').strip()
                ))

            db.session.commit()
            log_operation('保存工单领料单', f'工单领料单：{requisition.req_no}', 'requisition', requisition.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': requisition.id, 'order_no': requisition.req_no})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存工单领料单表格失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_requisition():
        from flask_login import current_user
        from app import (ProductionRequisition, api_error, generate_order_no,
                         get_default_warehouse, log_operation)
        try:
            bom_id = request.form.get('bom_id')
            production_order = (request.form.get('production_order') or '').strip()
            purpose = (request.form.get('purpose') or '').strip()
            remark = (request.form.get('remark') or '').strip()
            # BUG-2026-08-05-008：仓库必填，未填写时自动带入默认仓库
            warehouse = (request.form.get('warehouse') or '').strip()
            if not warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            if not warehouse:
                return api_error('请选择仓库')

            req_no = generate_order_no('REQ')
            requisition = ProductionRequisition(
                req_no=req_no,
                bom_id=int(bom_id) if bom_id else None,
                production_order=production_order,
                purpose=purpose,
                warehouse=warehouse,
                remark=remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(requisition)
            db.session.commit()
            log_operation('保存工单领料单', f'工单领料单：{req_no}', 'requisition', requisition.id)
            return jsonify({'status': 'success', 'id': requisition.id, 'msg': '保存成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存工单领料单失败: {e}')
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/update', methods=['POST'])
    @require_role('production')
    @login_required
    def update_requisition(id):
        from app import (ProductionRequisition, api_error,
                         get_default_warehouse, log_operation)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以修改')

        try:
            bom_id = request.form.get('bom_id')
            requisition.bom_id = int(bom_id) if bom_id else None
            requisition.production_order = (request.form.get('production_order') or '').strip()
            requisition.purpose = (request.form.get('purpose') or '').strip()
            # BUG-2026-08-05-008：仓库必填，未填写时自动带入默认仓库
            warehouse = (request.form.get('warehouse') or '').strip()
            if not warehouse:
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            if not warehouse:
                return api_error('请选择仓库')
            requisition.warehouse = warehouse
            requisition.remark = (request.form.get('remark') or '').strip()
            db.session.commit()
            log_operation('修改工单领料单', f'工单领料单：{requisition.req_no}', 'requisition', id)
            return jsonify({'status': 'success', 'msg': '保存成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'修改工单领料单失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/item/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_requisition_item(id):
        from app import (Material, ProductionRequisition,
                         ProductionRequisitionItem, api_error, parse_float_value,
                         round_to_2_decimals)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以添加明细')
        try:
            material_code = (request.form.get('material_code') or '').strip()
            quantity = round_to_2_decimals(parse_float_value(request.form.get('quantity'), 1))
            unit_id = request.form.get('unit_id')

            material = Material.query.filter_by(code=material_code).first()
            if not material:
                return api_error('物料编码不存在')
            if quantity <= 0:
                return api_error('工单领料数量必须大于 0')

            item = ProductionRequisitionItem(
                requisition_id=id,
                material_id=material.id,
                quantity=quantity,
                unit_id=int(unit_id) if unit_id else None
            )
            db.session.add(item)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500
            return jsonify({'status': 'success'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/item/<int:item_id>/update', methods=['POST'])
    @require_role('production')
    @login_required
    def update_requisition_item(id, item_id):
        from app import (ProductionRequisition, ProductionRequisitionItem,
                         api_error, parse_float_value, round_to_2_decimals)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以修改明细')

        item = ProductionRequisitionItem.query.get_or_404(item_id)
        if item.requisition_id != id:
            return api_error('工单领料明细不属于当前工单领料单')

        try:
            quantity = round_to_2_decimals(parse_float_value(request.form.get('quantity'), item.quantity))
            if quantity <= 0:
                return api_error('数量必须大于0')
            if item.material and (item.material.stock or 0) < quantity:
                return api_error(f'物料 {item.material.code} 库存不足，当前库存：{item.material.stock or 0}')

            item.quantity = quantity
            db.session.commit()
            return jsonify({'status': 'success', 'msg': '修改成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'工单领料明细修改失败: {e}')
            return api_error('修改失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_requisition_item(id, item_id):
        from app import (ProductionRequisition, ProductionRequisitionItem,
                         api_error)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以删除明细')
        item = ProductionRequisitionItem.query.get_or_404(item_id)
        if item.requisition_id != id:
            return api_error('工单领料明细不存在或已被删除')
        db.session.delete(item)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/batch_delete_items', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_delete_requisition_items(id):
        from app import (ProductionRequisition, ProductionRequisitionItem,
                         api_error)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以删除明细')

        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or []
        try:
            ids = [int(item_id) for item_id in ids]
        except (TypeError, ValueError):
            return api_error('请选择要删除的明细')
        if not ids:
            return api_error('请选择要删除的明细')

        try:
            ProductionRequisitionItem.query.filter(
                ProductionRequisitionItem.requisition_id == id,
                ProductionRequisitionItem.id.in_(ids)
            ).delete(synchronize_session=False)
            db.session.commit()
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除工单领料明细失败: {e}')
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/batch_add_items', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_add_requisition_items(id):
        from app import (Material, ProductionRequisition,
                         ProductionRequisitionItem, allow_negative_stock,
                         api_error, is_stock_sufficient, parse_float_value,
                         round_to_2_decimals)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('只有草稿状态的工单领料单可以添加明细')

        data = request.get_json(silent=True) or {}
        content = (data.get('content') or '').strip()
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
                if not allow_negative_stock() and not is_stock_sufficient(material.stock or 0, quantity):
                    errors.append(f'第 {line_no} 行库存不足：{material_code}')
                    continue
                db.session.add(ProductionRequisitionItem(
                    requisition_id=id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id
                ))
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
            app.logger.error(f'批量添加工单领料明细失败: {e}')
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/complete', methods=['POST'])
    @require_role('production')
    @login_required
    def complete_requisition(id):
        from sqlalchemy.orm import selectinload
        from app import (ProductionRequisition, _acquire_order_write_lock,
                         api_error, deduct_location_inventory_atomic,
                         deduct_stock, get_default_warehouse,
                         location_management_enabled, log_operation)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'pending':
            return api_error('当前工单领料单状态不可完结')
        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复扣库存
            locked, ok = _acquire_order_write_lock(ProductionRequisition, id, 'pending', selectinload(ProductionRequisition.items))
            if not ok:
                return api_error('当前工单领料单状态不可完结')
            requisition = locked
            # BUG-2026-08-05-008：加锁后再做仓库赋值与必填校验，避免锁前修改被 rollback 丢弃
            if not (requisition.warehouse or '').strip():
                default_wh = get_default_warehouse()
                if default_wh:
                    requisition.warehouse = default_wh.name
            if not (requisition.warehouse or '').strip():
                db.session.rollback()
                return api_error('请选择仓库')
            use_location = bool(location_management_enabled() and requisition.warehouse)
            for item in requisition.items:
                ok, error_msg = deduct_stock(item.material, item.quantity or 0,
                                             transaction_type='requisition',
                                             reference_type='requisition',
                                             reference_id=requisition.id)
                if not ok:
                    db.session.rollback()
                    return api_error(error_msg or f'物料 {item.material.code} 库存不足')
                # 原子扣库位（与 out_order 领料出库一致：仓库名即库位维度）
                if use_location:
                    ok2, err2 = deduct_location_inventory_atomic(
                        item.material_id, requisition.warehouse, item.quantity or 0,
                        material_code_hint=item.material.code if item.material else None,
                    )
                    if not ok2:
                        db.session.rollback()
                        return api_error(err2 or '库位库存扣减失败')
            requisition.status = 'completed'
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('提交失败，请稍后重试')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'工单领料完成失败: {e}')
            return api_error('提交失败，请稍后重试')
        log_operation('工单领料完成', f'工单领料单：{requisition.req_no}', 'requisition', id)
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/revert', methods=['POST'])
    @require_role('production')
    @login_required
    def revert_requisition(id):
        """工单领料单撤销"""
        from sqlalchemy.orm import selectinload
        from app import (ProductionRequisition, _acquire_order_write_lock,
                         add_stock, api_error, location_management_enabled,
                         log_operation, update_location_inventory)
        requisition = ProductionRequisition.query.get_or_404(id)
        if requisition.status != 'completed':
            return api_error('只有已完成的工单领料单可以撤销')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复恢复
            locked, ok = _acquire_order_write_lock(ProductionRequisition, id, 'completed', selectinload(ProductionRequisition.items))
            if not ok:
                return api_error('该工单领料单已撤销，不能重复操作')
            requisition = locked
            # 恢复库存（走 add_stock 写流水+归一化，与 complete_requisition 对称）
            for item in requisition.items:
                if item.material:
                    ok, err = add_stock(item.material, item.quantity or 0,
                                        transaction_type='revert_requisition',
                                        reference_type='requisition',
                                        reference_id=requisition.id,
                                        remark=f'撤销工单领料单 {requisition.req_no}')
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存恢复失败')
                    # BUG-2026-08-05-008：同步还原库位库存（与 complete_requisition 对称）
                    if location_management_enabled() and (requisition.warehouse or '').strip():
                        loc_ok, loc_err = update_location_inventory(item.material, requisition.warehouse, item.quantity or 0)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存还原失败')

            requisition.status = 'pending'
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('撤销失败，请稍后重试')

            log_operation('撤销工单领料单', f'工单领料单：{requisition.req_no}', 'requisition', id)
            return jsonify({'status': 'success', 'msg': '工单领料单已撤销，库存已恢复'})
        except Exception as e:
            db.session.rollback()
            return api_error('撤销失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/<int:id>/delete', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_requisition(id):
        from app import (ProductionRequisition, ProductionRequisitionItem)
        requisition = ProductionRequisition.query.get_or_404(id)
        # 仅允许删除草稿状态的单据，避免删除已生效单据导致库存丢失
        if requisition.status != 'pending':
            return jsonify({'status': 'error', 'msg': '只能删除草稿状态的工单领料单，已完成的请先反提交'}), 400
        ProductionRequisitionItem.query.filter_by(requisition_id=id).delete()
        db.session.delete(requisition)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/batch_delete', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_delete_requisition():
        from app import (ProductionRequisition, ProductionRequisitionItem,
                         api_error)
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的工单领料单')
        blocked = [
            requisition.req_no for requisition in ProductionRequisition.query.filter(ProductionRequisition.id.in_(ids)).all()
            if requisition.status != 'pending'
        ]
        if blocked:
            return api_error('只能删除草稿工单领料单：' + '、'.join(blocked))
        for rid in ids:
            ProductionRequisitionItem.query.filter_by(requisition_id=rid).delete()
            ProductionRequisition.query.filter_by(id=rid).delete()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    @app.route('/requisition/export')
    @login_required
    def export_requisition():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (BOM, Material, ProductionRequisition,
                         ProductionRequisitionItem, _apply_status_date_filters,
                         _get_order_list_filters, _status_from_search_keyword,
                         _workbook_response)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'req_no', 'date', 'production_order', 'purpose', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = ProductionRequisition.query.options(
            joinedload(ProductionRequisition.bom),
            selectinload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.material).joinedload(Material.unit),
            selectinload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.unit),
        )
        query = _apply_status_date_filters(query, ProductionRequisition, status_filter, date_start, date_end)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed'))
            conditions = [
                ProductionRequisition.req_no.like(search_like),
                ProductionRequisition.production_order.like(search_like),
                ProductionRequisition.purpose.like(search_like),
                ProductionRequisition.warehouse.like(search_like),
                ProductionRequisition.remark.like(search_like),
                BOM.bom_no.like(search_like),
                BOM.product_name.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(ProductionRequisition.status == status_from_search)
            query = query.outerjoin(BOM, ProductionRequisition.bom_id == BOM.id).outerjoin(
                ProductionRequisitionItem, ProductionRequisitionItem.requisition_id == ProductionRequisition.id
            ).outerjoin(Material, ProductionRequisitionItem.material_id == Material.id).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(ProductionRequisition, sort_by, ProductionRequisition.created_at)
        orders = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for order in orders:
            if order.items:
                for item in order.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        order.req_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order.warehouse or '',
                        order.production_order or '',
                        order.purpose or '',
                        order.bom.bom_no if order.bom else '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        item.quantity or 0,
                        item.issued_quantity or 0,
                        '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')),
                        item.remark or order.remark or '',
                    ])
            else:
                rows.append([order.req_no, order.date.strftime('%Y-%m-%d') if order.date else '', order.warehouse or '', order.production_order or '', order.purpose or '', order.bom.bom_no if order.bom else '', '', '', '', '', 0, 0, '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')), order.remark or ''])
        return _workbook_response(
            'requisitions.xlsx',
            '工单领料',
            ['单据编号', '日期', '仓库', '工单', '用途', 'BOM编号', '物料编码', '物料名称', '规格', '单位', '数量', '已领数量', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/requisition/import', methods=['POST'])
    @require_role('production')
    @login_required
    def import_requisition():
        from flask_login import current_user
        from app import (BOM, ProductionRequisition,
                         ProductionRequisitionItem, _find_or_create_material,
                         _get_excel_cell, _get_excel_number, _import_result,
                         _order_no_from_row, _parse_excel_date,
                         _read_import_sheet, api_error, get_default_warehouse,
                         validate_excel_extension,
                         validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的工单领料文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        # BUG-2026-08-05-008：导入的工单领料单自动带入默认仓库
        _default_wh = get_default_warehouse()
        import_default_warehouse = _default_wh.name if _default_wh else None
        aliases = {
            'order_no': ['单据编号', '工单领料单号', '订单编号'],
            'date': ['日期'],
            'production_order': ['工单', '生产令'],
            'purpose': ['用途'],
            'bom_no': ['BOM编号', 'bom'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量'],
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
                order_no = _order_no_from_row(row, col_map, 'order_no', 'REQ')
                order = orders_by_no.get(order_no)
                if not order:
                    if ProductionRequisition.query.filter_by(req_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：工单领料单号 {order_no} 已存在')
                        continue
                    bom_no = _get_excel_cell(row, col_map, 'bom_no')
                    bom = BOM.query.filter_by(bom_no=bom_no).first() if bom_no else None
                    order = ProductionRequisition(
                        req_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        production_order=_get_excel_cell(row, col_map, 'production_order'),
                        purpose=_get_excel_cell(row, col_map, 'purpose'),
                        bom_id=bom.id if bom else None,
                        warehouse=import_default_warehouse,
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
                db.session.add(ProductionRequisitionItem(
                    requisition_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id,
                    remark=_get_excel_cell(row, col_map, 'remark'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('工单领料单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'工单领料导入失败: {e}')
            return api_error(f'工单领料导入失败：{str(e)}')

    @app.route('/requisition/<int:id>/export')
    @login_required
    def export_single_requisition(id):
        from openpyxl import Workbook
        import io
        from app import ProductionRequisition
        order = ProductionRequisition.query.get_or_404(id)
        wb = Workbook()
        ws = wb.active
        ws.title = '工单领料单'
        ws.append(['单据编号', '日期', '仓库', '工单', '用途', '物料编码', '物料名称', '规格', '单位', '数量', '备注'])
        if order.items:
            for item in order.items:
                ws.append([
                    order.req_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    order.warehouse or '',
                    order.production_order or '',
                    order.purpose or '',
                    item.material.code if item.material else '',
                    item.material.name if item.material else '',
                    item.material.spec if item.material else '',
                    item.material.unit.name if item.material and item.material.unit else '',
                    item.quantity or 0,
                    item.remark or ''
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name=f'requisition_{order.req_no}.xlsx', as_attachment=True)

    @app.route('/requisition/<int:id>/print')
    @login_required
    def print_single_requisition(id):
        from sqlalchemy.orm import joinedload
        from app import (Material, ProductionRequisition,
                         ProductionRequisitionItem)
        requisition = ProductionRequisition.query.options(
            joinedload(ProductionRequisition.items).joinedload(ProductionRequisitionItem.material).joinedload(Material.unit),
            joinedload(ProductionRequisition.operator),
            joinedload(ProductionRequisition.bom)
        ).get_or_404(id)
        return render_template('requisition_print.html', requisition=requisition)