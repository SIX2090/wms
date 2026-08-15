#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 库存调整（adjustment）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_adjustment_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 adjustment_list、
# add_adjustment、adjustment_detail、complete_adjustment 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（AdjustmentOrder 模型、AdjustmentOrderItem、Material、Unit、
#   Warehouse、各辅助函数 _get_order_list_filters / _apply_status_date_filters /
#   _status_from_search_keyword / generate_order_no / serialize_material /
#   get_active_warehouses / get_default_warehouse / _serialize_adjustment_item_for_form /
#   _material_row_common / _render_generic_document_print / _fmt_date / _operator_name /
#   api_error / round_to_2_decimals / normalize_stock_quantity / allow_negative_stock /
#   is_stock_sufficient / log_operation / _acquire_order_write_lock /
#   location_management_enabled / add_stock / deduct_stock_atomic /
#   update_location_inventory / _workbook_response / validate_excel_extension /
#   validate_excel_size / _read_import_sheet / _get_excel_cell / _get_excel_number /
#   _order_no_from_row / _parse_excel_date / _find_or_create_material / _import_result 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_adjustment_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import jsonify, render_template, request
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 adjustment_* 各路由测试覆盖
def register_adjustment_routes(app):
    @app.route('/adjustment')
    @login_required
    def adjustment_list():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (AdjustmentOrder, AdjustmentOrderItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed', 'cancelled'))
        adjustment_type = (request.args.get('adjustment_type') or '').strip()
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'adjustment_no', 'date', 'adjustment_type', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = AdjustmentOrder.query.options(
            joinedload(AdjustmentOrder.operator),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.material).joinedload(Material.unit)
        )
        query = _apply_status_date_filters(query, AdjustmentOrder, status_filter, date_start, date_end)
        if adjustment_type in ('surplus', 'loss'):
            query = query.filter(AdjustmentOrder.adjustment_type == adjustment_type)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed', 'cancelled'))
            conditions = [
                AdjustmentOrder.adjustment_no.like(search_like),
                AdjustmentOrder.remark.like(search_like),
                AdjustmentOrderItem.reason.like(search_like),
                AdjustmentOrderItem.location.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(AdjustmentOrder.status == status_from_search)
            query = query.outerjoin(AdjustmentOrderItem, AdjustmentOrderItem.adjustment_order_id == AdjustmentOrder.id).outerjoin(
                Material, AdjustmentOrderItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(AdjustmentOrder, sort_by, AdjustmentOrder.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        adjustments = pagination.items
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'adjustment_type': adjustment_type,
        }
        return render_template('adjustment.html', adjustments=adjustments, pagination=pagination, filters=filters, sort_by=sort_by, sort_order=sort_order, per_page=per_page)

    @app.route('/adjustment/add', methods=['GET'])
    @login_required
    def adjustment_add_page():
        """库存调整表格编辑页面"""
        from datetime import date
        from sqlalchemy.orm import joinedload
        from app import (Material, Unit, generate_order_no, get_active_warehouses,
                         get_default_warehouse, serialize_material)
        adjustment_no = generate_order_no('ADJ')
        materials = Material.query.options(joinedload(Material.unit)).order_by(Material.code.asc()).all()
        materials_json = [serialize_material(m) for m in materials]
        units = Unit.query.order_by(Unit.name.asc()).all()
        units_json = [{'id': u.id, 'name': u.name} for u in units]
        # BUG-2026-08-02-015：调整单仓库必填，仅列出启用仓库并预选默认仓库
        warehouses = get_active_warehouses()

        return render_template('adjustment_add.html',
                             adjustment=None,
                             order_id='',
                             adjustment_no=adjustment_no,
                             adjustment_date=date.today().strftime('%Y-%m-%d'),
                             selected_type='surplus',
                             remark='',
                             materials=materials_json,
                             units=units_json,
                             warehouses=warehouses,
                             default_warehouse=get_default_warehouse(),
                             existing_items=[],
                             readonly=False,
                             page_title='新增库存调整单')

    @app.route('/adjustment/<int:id>')
    @login_required
    def adjustment_detail(id):
        """库存调整单详情和草稿编辑页面"""
        from datetime import date
        from sqlalchemy.orm import joinedload, selectinload
        from app import (AdjustmentOrder, AdjustmentOrderItem, Material, Unit,
                         _serialize_adjustment_item_for_form, get_active_warehouses,
                         get_default_warehouse, serialize_material)
        adjustment = AdjustmentOrder.query.options(
            joinedload(AdjustmentOrder.operator),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.material).joinedload(Material.unit),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.unit)
        ).get_or_404(id)
        materials = Material.query.options(joinedload(Material.unit)).order_by(Material.code.asc()).all()
        materials_json = [serialize_material(m) for m in materials]
        units = Unit.query.order_by(Unit.name.asc()).all()
        units_json = [{'id': u.id, 'name': u.name} for u in units]
        # BUG-2026-08-02-015：调整单仓库必填，仅列出启用仓库并预选默认仓库
        warehouses = get_active_warehouses()
        readonly = adjustment.status != 'pending'

        return render_template('adjustment_add.html',
                             adjustment=adjustment,
                             order_id=adjustment.id,
                             adjustment_no=adjustment.adjustment_no,
                             adjustment_date=(adjustment.date or date.today()).strftime('%Y-%m-%d'),
                             selected_type=adjustment.adjustment_type,
                             remark=adjustment.remark or '',
                             materials=materials_json,
                             units=units_json,
                             warehouses=warehouses,
                             default_warehouse=get_default_warehouse(),
                             existing_items=[_serialize_adjustment_item_for_form(item) for item in adjustment.items],
                             readonly=readonly,
                             page_title=('查看库存调整单' if readonly else '编辑库存调整单'))

    @app.route('/adjustment/<int:id>/print')
    @login_required
    def print_adjustment(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (AdjustmentOrder, AdjustmentOrderItem, Material,
                         _fmt_date, _material_row_common, _operator_name,
                         _render_generic_document_print)
        adjustment = AdjustmentOrder.query.options(
            joinedload(AdjustmentOrder.operator),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.material).joinedload(Material.unit),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.unit),
        ).get_or_404(id)
        type_label = '盘盈增加库存' if adjustment.adjustment_type == 'surplus' else '盘亏减少库存' if adjustment.adjustment_type == 'loss' else adjustment.adjustment_type
        rows = [
            _material_row_common(
                item,
                quantity=abs(item.quantity or 0),
                extra={
                    'location': item.location or '',
                    'direction': '增加' if (item.quantity or 0) > 0 else '减少',
                    'reason': item.reason or '',
                }
            )
            for item in adjustment.items
        ]
        return _render_generic_document_print({
            'title': '库存调整单',
            'subtitle': 'INVENTORY ADJUSTMENT',
            'number_label': '调整单号',
            'number': adjustment.adjustment_no,
            'date_label': '调整日期',
            'date': _fmt_date(adjustment.date),
            'status': adjustment.status,
            'info': [
                ('调整类型', type_label),
                ('来源类型', adjustment.source_type or 'manual'),
                ('制单人', _operator_name(adjustment)),
                ('创建时间', _fmt_date(adjustment.created_at)),
            ],
            'remark': adjustment.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('location', '库位', ''),
                ('direction', '方向', 'center'),
                ('quantity', '调整数量', 'right'),
                ('reason', '原因', ''),
            ],
            'rows': rows,
            'signatures': ['制单', '审核', '仓库', '财务'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_adjustment():
        from datetime import date, datetime
        from flask_login import current_user
        from app import (AdjustmentOrder, AdjustmentOrderItem, Material, allow_negative_stock,
                         api_error, generate_order_no, get_default_warehouse,
                         is_stock_sufficient, location_management_enabled,
                         log_operation, normalize_stock_quantity, round_to_2_decimals,
                         validate_inventory_warehouse)
        # Support both JSON and form data
        if request.is_json:
            data = request.get_json(silent=True) or {}
            order_id = data.get('order_id') or data.get('id')
            adjustment_no = (data.get('adjustment_no') or '').strip()
            adjustment_type = (data.get('adjustment_type') or '').strip()
            date_str = (data.get('date') or '').strip()
            remark = (data.get('remark') or '').strip()
            warehouse = (data.get('warehouse') or '').strip()
            items_data = data.get('items', [])
            replace_items = 'items' in data
        else:
            order_id = request.form.get('order_id')
            adjustment_no = (request.form.get('adjustment_no') or '').strip()
            adjustment_type = (request.form.get('adjustment_type') or '').strip()
            date_str = (request.form.get('date') or '').strip()
            remark = (request.form.get('remark') or '').strip()
            warehouse = (request.form.get('warehouse') or '').strip()
            items_data = []
            material_id = request.form.get('material_id')
            quantity = request.form.get('quantity')
            if material_id and quantity:
                items_data.append({
                    'material_id': material_id,
                    'quantity': quantity,
                    'location': request.form.get('location'),
                    'reason': request.form.get('reason'),
                })
            replace_items = bool(items_data)

        if order_id and order_id not in ('None', '', 'null'):
            try:
                order_id = int(order_id)
            except (TypeError, ValueError):
                order_id = None
        else:
            order_id = None

        try:
            if not adjustment_no:
                adjustment_no = generate_order_no('ADJ')

            if adjustment_type not in ('surplus', 'loss'):
                return api_error('请选择调整类型')

            # BUG-2026-08-02-013：仓库必填（AGENTS.md 规则），未填写时自动带入默认仓库
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

            if order_id:
                adjustment = AdjustmentOrder.query.get(order_id)
                if not adjustment:
                    return api_error('库存调整单不存在，请刷新后重试')
                if adjustment.status != 'pending':
                    return api_error('只有草稿状态的调整单可以修改')
                same_no_order = AdjustmentOrder.query.filter(
                    AdjustmentOrder.adjustment_no == adjustment_no,
                    AdjustmentOrder.id != order_id
                ).first()
                if same_no_order:
                    return api_error('调整单号已存在，不能重复保存')
            else:
                # Check if adjustment order already exists
                adjustment = AdjustmentOrder.query.filter_by(adjustment_no=adjustment_no).first()
                if adjustment:
                    if adjustment.status != 'pending':
                        return api_error('调整单号已存在，不能重复保存')
                else:
                    adjustment = AdjustmentOrder(
                        adjustment_no=adjustment_no,
                        adjustment_type=adjustment_type,
                        source_type='manual',
                        status='pending',
                        operator_id=current_user.id,
                        date=date.today()
                    )
                    db.session.add(adjustment)

            if replace_items and not items_data:
                return api_error('请至少填写一条调整明细')

            if date_str:
                try:
                    adjustment.date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    return api_error('日期格式不正确')

            adjustment.adjustment_no = adjustment_no
            adjustment.adjustment_type = adjustment_type
            adjustment.remark = remark
            adjustment.warehouse = warehouse
            if not adjustment.operator_id:
                adjustment.operator_id = current_user.id

            # Process items if provided.
            if replace_items:
                db.session.flush()
                # Clear existing items
                AdjustmentOrderItem.query.filter_by(adjustment_order_id=adjustment.id).delete()

                for item_data in items_data:
                    material = None
                    material_id = item_data.get('material_id')
                    if material_id:
                        try:
                            material = Material.query.get(int(material_id))
                        except (TypeError, ValueError):
                            material = None
                    material_code = (item_data.get('code') or item_data.get('material_code') or '').strip()
                    if not material and material_code:
                        material = Material.query.filter_by(code=material_code).first()
                    if not material:
                        return api_error(f'物料不存在：{material_code or material_id}')
                    try:
                        quantity = round_to_2_decimals(item_data.get('quantity', 0))
                    except (TypeError, ValueError):
                        return api_error(f'物料 {material.code} 的数量必须是数字')
                    if quantity <= 0:
                        return api_error(f'物料 {material.code} 的数量必须大于0')
                    if quantity > 999999:
                        return api_error(f'物料 {material.code} 的数量超过合理范围（最大 999999）')

                    # Check stock for loss type
                    current_stock = normalize_stock_quantity(material.stock or 0)
                    if adjustment_type == 'loss' and not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                        return api_error(f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}')

                    location = (item_data.get('location') or '').strip()
                    reason = (item_data.get('reason') or '').strip()

                    # P1-BUGFIX: 开启库位管理时 item 级 location 必填（AGENTS.md 规则二）
                    if location_management_enabled() and not location:
                        return api_error(f'库位管理已启用，物料 {material.code} 请填写库位')

                    # Store signed quantity based on adjustment type
                    signed_quantity = quantity if adjustment_type == 'surplus' else -quantity

                    item = AdjustmentOrderItem(
                        adjustment_order_id=adjustment.id,
                        material_id=material.id,
                        location=location or None,
                        quantity=signed_quantity,
                        unit_id=material.unit_id,
                        reason=reason
                    )
                    db.session.add(item)

            db.session.commit()

            log_operation('保存库存调整单', f'调整单：{adjustment.adjustment_no}', 'adjustment', adjustment.id)
            return jsonify({'status': 'success', 'msg': '保存成功', 'id': adjustment.id, 'adjustment_no': adjustment.adjustment_no})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调整单保存失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/<int:id>/complete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def complete_adjustment(id):
        from sqlalchemy.orm import selectinload
        from app import (AdjustmentOrder, _acquire_order_write_lock, add_stock, api_error,
                         deduct_stock_atomic, location_management_enabled, log_operation,
                         update_location_inventory)
        adjustment = AdjustmentOrder.query.get_or_404(id)
        if adjustment.status != 'pending':
            return api_error('只有草稿状态的调整单可以完成')
        if not adjustment.items:
            return api_error('调整单没有明细，无法完成')
        if not adjustment.warehouse:
            return api_error('调整单未指定仓库，无法完成')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复调整库存
            locked, ok = _acquire_order_write_lock(AdjustmentOrder, id, 'pending', selectinload(AdjustmentOrder.items))
            if not ok:
                return api_error('该调整单已提交，不能重复操作')
            adjustment = locked
            if not adjustment.items:
                db.session.rollback()
                return api_error('调整单没有明细，无法完成')
            # BUG-2026-08-02-010 修复：开启库位管理时同步库位库存，避免总库存与库位库存之和产生偏差。
            # P1-1 已为 AdjustmentOrder 加 warehouse 字段，loc_key 优先 adjustment.warehouse
            # （单据级仓库），无则回退 item.location（行级库位）。
            use_location = location_management_enabled()
            # P1-BUGFIX: 开启库位管理时 item 级 location 必填（AGENTS.md 规则二），
            # 防止存量草稿或绕过前端校验的请求把仓库名当作库位维度调整。
            if use_location:
                for item in adjustment.items:
                    if not item.material_id:
                        continue
                    if not (item.location or '').strip():
                        db.session.rollback()
                        return api_error(f'库位管理已启用，物料 {item.material.code if item.material else item.material_id} 请填写库位')
            for item in adjustment.items:
                if not item.material_id:
                    continue
                quantity = item.quantity or 0
                if quantity > 0:
                    ok, err = add_stock(
                        item.material,
                        quantity,
                        transaction_type='adjustment_in',
                        reference_type='adjustment',
                        reference_id=adjustment.id,
                        remark=item.reason or adjustment.remark or '',
                        warehouse=adjustment.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存增加失败')
                elif quantity < 0:
                    ok, err, _ = deduct_stock_atomic(
                        item.material_id,
                        abs(quantity),
                        transaction_type='adjustment_out',
                        reference_type='adjustment',
                        reference_id=adjustment.id,
                        remark=item.reason or adjustment.remark or '',
                        warehouse=adjustment.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err)
                # 库位库存同步：update_location_inventory 内部按 delta 正负自动分发 add/deduct。
                # P1-BUGFIX: 开启库位管理时优先用 item.location（行级库位），未开库位退回 adjustment.warehouse。
                if use_location and quantity:
                    loc_key = (item.location or '').strip() or (adjustment.warehouse or '').strip()
                    if loc_key:
                        loc_ok, loc_err = update_location_inventory(item.material, loc_key, quantity, warehouse=adjustment.warehouse)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存更新失败')

            adjustment.status = 'completed'
            db.session.commit()
            log_operation('完成库存调整', f'调整单：{adjustment.adjustment_no}', 'adjustment', id)
            return jsonify({'status': 'success', 'msg': '库存调整已完成'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调整完成失败: {e}')
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/<int:id>/revert', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def revert_adjustment(id):
        from sqlalchemy.orm import selectinload
        from app import (AdjustmentOrder, _acquire_order_write_lock, add_stock, api_error,
                         deduct_stock_atomic, location_management_enabled, log_operation,
                         update_location_inventory)
        adjustment = AdjustmentOrder.query.get_or_404(id)
        if adjustment.status != 'completed':
            return api_error('只有已完成的调整单可以反提交')
        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复回退
            locked, ok = _acquire_order_write_lock(AdjustmentOrder, id, 'completed', selectinload(AdjustmentOrder.items))
            if not ok:
                return api_error('该调整单已反提交，不能重复操作')
            adjustment = locked
            # BUG-2026-08-02-010 修复：反提交时对称回退库位库存（与 complete 方向相反）。
            # P1-1 已为 AdjustmentOrder 加 warehouse 字段，loc_key 优先 adjustment.warehouse
            # （单据级仓库），无则回退 item.location（行级库位）。
            use_location = location_management_enabled()
            for item in adjustment.items:
                if not item.material_id:
                    continue
                quantity = item.quantity or 0
                if quantity > 0:
                    ok, err, _ = deduct_stock_atomic(
                        item.material_id,
                        quantity,
                        transaction_type='revert_adjustment_in',
                        reference_type='adjustment',
                        reference_id=adjustment.id,
                        remark=f'反提交库存调整 {adjustment.adjustment_no}',
                        warehouse=adjustment.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err)
                elif quantity < 0:
                    ok, err = add_stock(
                        item.material,
                        abs(quantity),
                        transaction_type='revert_adjustment_out',
                        reference_type='adjustment',
                        reference_id=adjustment.id,
                        remark=f'反提交库存调整 {adjustment.adjustment_no}',
                        warehouse=adjustment.warehouse,
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存恢复失败')
                # 库位库存对称回退：complete 时 +quantity，revert 时 -quantity；
                # complete 时 -quantity，revert 时 +quantity。即 -quantity。
                # P1-BUGFIX: 开启库位管理时优先用 item.location（行级库位），未开库位退回 adjustment.warehouse。
                if use_location and quantity:
                    loc_key = (item.location or '').strip() or (adjustment.warehouse or '').strip()
                    if loc_key:
                        loc_ok, loc_err = update_location_inventory(item.material, loc_key, -quantity, warehouse=adjustment.warehouse)
                        if not loc_ok:
                            db.session.rollback()
                            return api_error(loc_err or '库位库存回退失败')
            adjustment.status = 'pending'
            db.session.commit()
            log_operation('反提交库存调整', f'调整单：{adjustment.adjustment_no}', 'adjustment', id)
            return jsonify({'status': 'success', 'msg': '反提交成功，库存已恢复'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调整反提交失败: {e}')
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_adjustment(id):
        from app import (AdjustmentOrder, AdjustmentOrderItem,
                         _acquire_order_write_lock, api_error, log_operation)
        adjustment = AdjustmentOrder.query.get_or_404(id)
        if adjustment.status != 'pending':
            return api_error('只有草稿状态的调整单可以删除')

        try:
            # 重新锁定并校验草稿状态，防止并发完成后仍被物理删除。
            locked, ok = _acquire_order_write_lock(AdjustmentOrder, id, 'pending')
            if not ok:
                return jsonify({'status': 'error', 'msg': '该调整单状态已变更；已完成单请先反提交后再删除'}), 409
            adjustment = locked

            AdjustmentOrderItem.query.filter_by(adjustment_order_id=id).delete()
            db.session.delete(adjustment)
            db.session.commit()
            log_operation('删除库存调整单', f'调整单：{adjustment.adjustment_no}', 'adjustment', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调整单删除失败: {e}')
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/batch_delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_delete_adjustment():
        from app import (AdjustmentOrder, AdjustmentOrderItem,
                         _acquire_order_write_lock, api_error, log_operation)
        payload = request.get_json(silent=True) or {}
        ids = payload.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的库存调整单')

        adjustments = AdjustmentOrder.query.filter(AdjustmentOrder.id.in_(ids)).all()
        blocked = [adjustment.adjustment_no for adjustment in adjustments if adjustment.status != 'pending']
        if blocked:
            return api_error('只能删除草稿调整单：' + '、'.join(blocked))

        deleted_count = 0
        skipped = []
        # 逐条加写锁并独立提交，单点失败仅回滚自身，不影响其余单据。
        for adjustment_id in ids:
            adjustment_no = None
            try:
                locked, ok = _acquire_order_write_lock(AdjustmentOrder, adjustment_id, 'pending')
                if not ok or locked is None:
                    existing = AdjustmentOrder.query.get(adjustment_id)
                    adjustment_no = existing.adjustment_no if existing else f'ID:{adjustment_id}'
                    skipped.append(f'{adjustment_no}(状态已变更)')
                    db.session.rollback()
                    continue
                adjustment = locked
                adjustment_no = adjustment.adjustment_no
                AdjustmentOrderItem.query.filter_by(adjustment_order_id=adjustment_id).delete()
                db.session.delete(adjustment)
                db.session.commit()
                deleted_count += 1
            except Exception:
                db.session.rollback()
                skipped.append(f'{adjustment_no or f"ID:{adjustment_id}"}(错误)')
                app.logger.exception('批量删除库存调整单失败: ID=%s', adjustment_id)

        msg = f'批量删除完成，共删除 {deleted_count} 张库存调整单'
        if skipped:
            msg += f'，跳过 {len(skipped)} 张：{", ".join(skipped[:10])}'
        log_operation('批量删除库存调整单', f'共删除 {deleted_count} 张调整单', 'adjustment')
        return jsonify({'status': 'success', 'msg': msg, 'deleted': deleted_count, 'skipped': skipped})

    @app.route('/adjustment/export')
    @login_required
    def export_adjustment():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (AdjustmentOrder, AdjustmentOrderItem, Material, _apply_status_date_filters,
                         _get_order_list_filters, _status_from_search_keyword, _workbook_response)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed', 'cancelled'))
        adjustment_type_filter = (request.args.get('adjustment_type') or '').strip()
        allowed_sorts = {'adjustment_no', 'date', 'adjustment_type', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = AdjustmentOrder.query.options(
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.material).joinedload(Material.unit),
            selectinload(AdjustmentOrder.items).joinedload(AdjustmentOrderItem.unit),
        )
        query = _apply_status_date_filters(query, AdjustmentOrder, status_filter, date_start, date_end)
        if adjustment_type_filter in ('surplus', 'loss'):
            query = query.filter(AdjustmentOrder.adjustment_type == adjustment_type_filter)
        if search:
            search_like = f'%{search}%'
            status_from_search = _status_from_search_keyword(search, ('pending', 'completed', 'cancelled'))
            conditions = [
                AdjustmentOrder.adjustment_no.like(search_like),
                AdjustmentOrder.remark.like(search_like),
                AdjustmentOrderItem.reason.like(search_like),
                AdjustmentOrderItem.location.like(search_like),
                Material.code.like(search_like),
                Material.name.like(search_like),
                Material.spec.like(search_like),
            ]
            if status_from_search:
                conditions.append(AdjustmentOrder.status == status_from_search)
            query = query.outerjoin(AdjustmentOrderItem, AdjustmentOrderItem.adjustment_order_id == AdjustmentOrder.id).outerjoin(
                Material, AdjustmentOrderItem.material_id == Material.id
            ).filter(db.or_(*conditions)).distinct()
        sort_col = getattr(AdjustmentOrder, sort_by, AdjustmentOrder.created_at)
        orders = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for order in orders:
            order_type = '盘盈' if order.adjustment_type == 'surplus' else '盘亏'
            if order.items:
                for item in order.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        order.adjustment_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order_type,
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        abs(item.quantity or 0),
                        item.location or '',
                        item.reason or '',
                        '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')),
                        order.remark or '',
                    ])
            else:
                rows.append([order.adjustment_no, order.date.strftime('%Y-%m-%d') if order.date else '', order_type, '', '', '', '', 0, '', '', '草稿' if order.status == 'pending' else ('已完成' if order.status == 'completed' else (order.status or '')), order.remark or ''])
        return _workbook_response(
            'adjustment_orders.xlsx',
            '库存调整',
            ['单据编号', '日期', '调整类型', '物料编码', '物料名称', '规格', '单位', '数量', '库位', '原因', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/adjustment/import', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def import_adjustment():
        from flask_login import current_user
        from app import (AdjustmentOrder, AdjustmentOrderItem, _find_or_create_material,
                         _get_excel_cell, _get_excel_number, _import_result, _order_no_from_row,
                         _parse_excel_date, _read_import_sheet, api_error, validate_excel_extension,
                         validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的库存调整文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['单据编号', '调整单号', '订单编号'],
            'date': ['日期'],
            'adjustment_type': ['调整类型', '类型'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量'],
            'location': ['库位', '位置'],
            'reason': ['原因'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'adjustment_type', 'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（调整类型、物料编码、数量）。检测到的表头：{", ".join(header_row)}')
            orders_by_no = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                material_code = _get_excel_cell(row, col_map, 'material_code')
                quantity = _get_excel_number(row, col_map, 'quantity')
                raw_type = _get_excel_cell(row, col_map, 'adjustment_type')
                if '亏' in raw_type or raw_type.lower() in ('loss', 'out', 'minus'):
                    adjustment_type = 'loss'
                else:
                    adjustment_type = 'surplus'
                if not material_code or quantity <= 0:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料编码为空或数量不正确')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'ADJ')
                order = orders_by_no.get(order_no)
                if not order:
                    if AdjustmentOrder.query.filter_by(adjustment_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：调整单号 {order_no} 已存在')
                        continue
                    order = AdjustmentOrder(
                        adjustment_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        adjustment_type=adjustment_type,
                        source_type='import',
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
                db.session.add(AdjustmentOrderItem(
                    adjustment_order_id=order.id,
                    material_id=material.id,
                    location=_get_excel_cell(row, col_map, 'location') or None,
                    quantity=quantity if order.adjustment_type == 'surplus' else -quantity,
                    unit_id=material.unit_id,
                    reason=_get_excel_cell(row, col_map, 'reason'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('库存调整单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存调整导入失败: {e}')
            return api_error(f'库存调整导入失败：{str(e)}')