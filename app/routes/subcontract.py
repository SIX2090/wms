#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 委外（subcontract）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_subcontract_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 subcontract_list、
# add_subcontract、subcontract_issue_list、subcontract_receive_list 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（SubcontractOrder、SubcontractItem、SubcontractIssue、
#   SubcontractIssueItem、SubcontractReceive、SubcontractReceiveItem、Material、
#   Supplier、Unit 及各辅助函数 _get_order_list_filters / _apply_subcontract_search /
#   _apply_subcontract_issue_search / _apply_subcontract_receive_search /
#   _subcontract_status_label / _subcontract_issue_status_label /
#   _subcontract_receive_status_label / _acquire_order_write_lock /
#   get_recent_operation_logs / serialize_material / _material_row_common /
#   _render_generic_document_print / _fmt_date / _operator_name / api_error 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_subcontract_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明。
from __future__ import annotations

from flask import jsonify, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 subcontract_* 各路由测试覆盖
def register_subcontract_routes(app):
    @app.route('/subcontract')
    @login_required
    def subcontract_list():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractItem, SubcontractOrder, Supplier,
                         _apply_status_date_filters, _apply_subcontract_search,
                         _get_order_list_filters, parse_date_value)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'processing', 'completed', 'cancelled'))
        deadline_start = parse_date_value(request.args.get('deadline_start'))
        deadline_end = parse_date_value(request.args.get('deadline_end'))
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'order_no', 'date', 'supplier_id', 'deadline', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractOrder.query.options(
            joinedload(SubcontractOrder.supplier),
            joinedload(SubcontractOrder.operator),
            selectinload(SubcontractOrder.items).joinedload(SubcontractItem.material)
        )
        query = _apply_status_date_filters(query, SubcontractOrder, status_filter, date_start, date_end)
        if deadline_start:
            query = query.filter(SubcontractOrder.deadline >= deadline_start)
        if deadline_end:
            query = query.filter(SubcontractOrder.deadline <= deadline_end)
        query = _apply_subcontract_search(query, search)
        sort_col = getattr(SubcontractOrder, sort_by, SubcontractOrder.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        orders = pagination.items
        suppliers = Supplier.query.all()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'deadline_start': deadline_start.strftime('%Y-%m-%d') if deadline_start else '',
            'deadline_end': deadline_end.strftime('%Y-%m-%d') if deadline_end else '',
        }
        return render_template('subcontract.html', orders=orders, pagination=pagination, suppliers=suppliers, filters=filters, sort_by=sort_by, sort_order=sort_order, per_page=per_page)

    @app.route('/subcontract/progress')
    @login_required
    def subcontract_progress_page():
        from sqlalchemy.orm import joinedload
        from app import Material, SubcontractOrder, Unit
        orders = SubcontractOrder.query.order_by(SubcontractOrder.created_at.desc()).all()
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        return render_template('subcontract_progress.html', orders=orders, materials=materials, units=units)

    @app.route('/subcontract/<int:id>')
    @login_required
    def subcontract_detail(id):
        from sqlalchemy.orm import joinedload
        from app import (Material, SubcontractOrder, Supplier, Unit,
                         get_recent_operation_logs, serialize_material)
        order = SubcontractOrder.query.get_or_404(id)
        materials = Material.query.options(joinedload(Material.unit)).all()
        units = Unit.query.all()
        suppliers = Supplier.query.order_by(Supplier.name.asc()).all()
        return render_template(
            'subcontract_detail.html',
            order=order,
            materials=[serialize_material(material) for material in materials],
            units=units,
            suppliers=suppliers,
            operation_logs=get_recent_operation_logs('subcontract', id),
        )

    @app.route('/subcontract/<int:id>/print')
    @login_required
    def print_subcontract(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractItem, SubcontractOrder, _fmt_date,
                         _material_row_common, _operator_name, _render_generic_document_print)
        order = SubcontractOrder.query.options(
            joinedload(SubcontractOrder.supplier),
            joinedload(SubcontractOrder.operator),
            selectinload(SubcontractOrder.items).joinedload(SubcontractItem.material).joinedload(Material.unit),
            selectinload(SubcontractOrder.items).joinedload(SubcontractItem.unit),
        ).get_or_404(id)
        rows = [
            _material_row_common(
                item,
                price=item.material.price if item.material else 0,
                amount=(item.quantity or 0) * (item.material.price or 0) if item.material else 0,
                extra={
                    'returned_quantity': item.returned_quantity or 0,
                    'loss': item.loss or 0,
                }
            )
            for item in order.items
        ]
        return _render_generic_document_print({
            'title': '委外加工单',
            'subtitle': 'SUBCONTRACT ORDER',
            'number_label': '委外单号',
            'number': order.order_no,
            'date_label': '委外日期',
            'date': _fmt_date(order.date),
            'status': order.status,
            'info': [
                ('加工厂商', order.supplier.name if order.supplier else ''),
                ('联系人', order.contact or ''),
                ('联系电话', order.phone or ''),
                ('交货期限', _fmt_date(order.deadline)),
                ('制单人', _operator_name(order)),
                ('总金额', f'{order.total_amount or 0:.2f}'),
            ],
            'remark': order.remark or '',
            'columns': [
                ('code', '产品编码', ''),
                ('name', '产品名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '委外数量', 'right'),
                ('returned_quantity', '已回数量', 'right'),
                ('loss', '损耗', 'right'),
                ('price', '参考单价', 'right money'),
                ('amount', '参考金额', 'right money'),
            ],
            'rows': rows,
            'total_amount': order.total_amount or sum(row.get('amount', 0) or 0 for row in rows),
            'signatures': ['制单', '委外确认', '仓库', '财务'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract():
        from flask_login import current_user
        from app import (SubcontractOrder, api_error, generate_order_no,
                         log_operation, parse_date_value)
        try:
            supplier_id = request.form.get('supplier_id')
            order_no = (request.form.get('order_no') or '').strip()
            contact = (request.form.get('contact') or '').strip()
            phone = (request.form.get('phone') or '').strip()
            deadline = parse_date_value(request.form.get('deadline'))
            remark = (request.form.get('remark') or '').strip()

            if not order_no:
                order_no = generate_order_no('SC')

            order = SubcontractOrder(
                order_no=order_no,
                supplier_id=int(supplier_id) if supplier_id else None,
                contact=contact,
                phone=phone,
                deadline=deadline,
                remark=remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(order)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500
            log_operation('新建委外单', f'委外单：{order_no}', 'subcontract', order.id)
            return jsonify({'status': 'success'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/item/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract_item(id):
        from app import (Material, SubcontractItem, SubcontractOrder, api_error,
                         parse_float_value, round_to_2_decimals)
        order = SubcontractOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有草稿状态的委外单可以添加明细')
        try:
            material_code = (request.form.get('material_code') or '').strip()
            quantity = parse_float_value(request.form.get('quantity'), 0)
            unit_id = request.form.get('unit_id')

            material = Material.query.filter_by(code=material_code).first()
            if not material:
                return api_error('物料编码不存在')
            if quantity <= 0:
                return api_error('委外数量必须大于 0')

            item = SubcontractItem(
                subcontract_order_id=id,
                material_id=material.id,
                quantity=quantity,
                unit_id=int(unit_id) if unit_id else (material.unit_id or None)
            )
            db.session.add(item)
            db.session.flush()
            order.total_amount = round_to_2_decimals(sum(
                (order_item.quantity or 0) * (order_item.material.price or 0)
                for order_item in order.items
            ))
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500
            return jsonify({'status': 'success', 'msg': '委外明细新增成功', 'id': item.id})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/item/<int:item_id>/delete', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_subcontract_item(id, item_id):
        from app import (SubcontractItem, SubcontractOrder, api_error, round_to_2_decimals)
        order = SubcontractOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有草稿状态的委外单可以删除明细')
        item = SubcontractItem.query.get_or_404(item_id)
        if item.subcontract_order_id != id:
            return api_error('委外明细不存在或已被删除')
        db.session.delete(item)
        db.session.flush()
        order.total_amount = round_to_2_decimals(sum(
            (order_item.quantity or 0) * (order_item.material.price or 0)
            for order_item in order.items
            if order_item.id != item_id
        ))
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/issue', methods=['POST'])
    @require_role('production')
    @login_required
    def quick_issue_subcontract(id):
        from flask_login import current_user
        from app import (Material, SubcontractIssue, SubcontractIssueItem,
                         SubcontractOrder, allow_negative_stock, api_error,
                         deduct_stock_atomic, generate_order_no, is_stock_sufficient,
                         log_operation, normalize_stock_quantity, parse_float_value,
                         round_to_2_decimals)
        order = SubcontractOrder.query.get_or_404(id)
        material_code = (request.form.get('material_code') or '').strip()
        quantity = round_to_2_decimals(parse_float_value(request.form.get('quantity'), 0))
        if not material_code:
            return api_error('请输入物料编码')
        if quantity <= 0:
            return api_error('发料数量必须大于 0')

        material = Material.query.filter_by(code=material_code).first()
        if not material:
            return api_error('物料编码不存在')
        current_stock = normalize_stock_quantity(material.stock or 0)
        if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
            return api_error(f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}')

        try:
            issue_no = generate_order_no('SF')
            issue = SubcontractIssue(
                issue_no=issue_no,
                subcontract_order_id=id,
                supplier_id=order.supplier_id,
                status='completed',
                operator_id=current_user.id
            )
            db.session.add(issue)
            db.session.flush()
            db.session.add(SubcontractIssueItem(
                issue_id=issue.id,
                material_id=material.id,
                quantity=quantity,
                unit_id=material.unit_id
            ))
            # 使用原子扣减并检查返回值，避免并发超卖
            ok, error_msg, _ = deduct_stock_atomic(material.id, quantity,
                         transaction_type='subcontract_issue',
                         reference_type='subcontract_issue',
                         reference_id=issue.id)
            if not ok:
                db.session.rollback()
                return api_error(error_msg or '库存扣减失败')
            if order.status == 'pending':
                order.status = 'processing'
            db.session.commit()
            log_operation('委外发料', f'委外发料单：{issue_no}', 'subcontract_issue', issue.id)
            return jsonify({'status': 'success', 'msg': '发料成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'委外快速发料失败: {e}')
            return api_error('发料失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/receive', methods=['POST'])
    @require_role('production')
    @login_required
    def quick_receive_subcontract(id):
        from flask_login import current_user
        from app import (Material, SubcontractOrder, SubcontractReceive,
                         SubcontractReceiveItem, add_stock, api_error, generate_order_no,
                         log_operation, parse_float_value, round_to_2_decimals)
        order = SubcontractOrder.query.get_or_404(id)
        material_code = (request.form.get('material_code') or '').strip()
        quantity = round_to_2_decimals(parse_float_value(request.form.get('quantity'), 0))
        price = round_to_2_decimals(parse_float_value(request.form.get('price'), 0))
        if not material_code:
            return api_error('请输入产品编码')
        if quantity <= 0:
            return api_error('收货数量必须大于 0')

        material = Material.query.filter_by(code=material_code).first()
        if not material:
            return api_error('产品编码不存在')

        try:
            receive_no = generate_order_no('SR')
            receive = SubcontractReceive(
                receive_no=receive_no,
                subcontract_order_id=id,
                supplier_id=order.supplier_id,
                status='completed',
                total_quantity=quantity,
                total_scrap=0,
                operator_id=current_user.id
            )
            db.session.add(receive)
            db.session.flush()
            db.session.add(SubcontractReceiveItem(
                receive_id=receive.id,
                material_id=material.id,
                quantity=quantity,
                scrap_quantity=0,
                unit_id=material.unit_id,
                price=price,
                amount=round_to_2_decimals(quantity * price)
            ))
            ok, msg = add_stock(material, quantity,
                                transaction_type='subcontract_receive',
                                reference_type='subcontract_receive',
                                reference_id=receive.id)
            if not ok:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': msg or '库存增加失败'}), 500

            total_required = sum((item.quantity or 0) for item in order.items)
            total_received = sum((item.quantity or 0) for receive_order in order.receive_orders for item in receive_order.items) + quantity
            if total_required and total_received >= total_required:
                order.status = 'completed'
            elif order.status == 'pending':
                order.status = 'processing'
            db.session.commit()
            log_operation('委外收货', f'委外收货单：{receive_no}', 'subcontract_receive', receive.id)
            return jsonify({'status': 'success', 'msg': '收货成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'委外快速收货失败: {e}')
            return api_error('收货失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/edit', methods=['POST'])
    @require_role('production')
    @login_required
    def edit_subcontract_header(id):
        """编辑委外单基础信息（仅 pending 状态可编辑）"""
        from app import SubcontractOrder, Supplier, api_error, log_operation, parse_date_value
        order = SubcontractOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有待处理状态的委外单可以编辑')

        data = request.get_json(silent=True) or request.form
        try:
            if 'date' in data and data.get('date'):
                new_date = parse_date_value(data.get('date'))
                if new_date:
                    order.date = new_date
            if 'deadline' in data:
                deadline_str = (data.get('deadline') or '').strip()
                order.deadline = parse_date_value(deadline_str) if deadline_str else None
            if 'contact' in data:
                order.contact = (data.get('contact') or '').strip() or None
            if 'phone' in data:
                order.phone = (data.get('phone') or '').strip() or None
            if 'remark' in data:
                order.remark = (data.get('remark') or '').strip() or None
            if 'supplier_id' in data and data.get('supplier_id'):
                try:
                    supplier_id = int(data.get('supplier_id'))
                    if Supplier.query.get(supplier_id):
                        order.supplier_id = supplier_id
                except (TypeError, ValueError):
                    pass
            db.session.commit()
            log_operation('编辑委外单', f'委外单：{order.order_no}', 'subcontract', id)
            return jsonify({'status': 'success', 'msg': '保存成功'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'编辑委外单失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/copy', methods=['POST'])
    @require_role('production')
    @login_required
    def copy_subcontract(id):
        """复制委外加工单为新草稿（不复制发料/收货关联，避免脏数据）。"""
        from datetime import date
        from flask_login import current_user
        from sqlalchemy.orm import selectinload
        from app import (SubcontractItem, SubcontractOrder, api_error, generate_order_no,
                         log_operation, round_to_2_decimals)
        source = SubcontractOrder.query.options(
            selectinload(SubcontractOrder.items),
        ).get_or_404(id)
        if not source.items:
            return api_error('原委外单没有产品明细，不能复制')

        try:
            new_order = SubcontractOrder(
                order_no=generate_order_no('SUB'),
                date=date.today(),
                supplier_id=source.supplier_id,
                contact=source.contact,
                phone=source.phone,
                deadline=source.deadline,
                remark=(f'由委外单 {source.order_no} 复制生成'
                        + (f'；原备注：{source.remark}' if source.remark else '')),
                status='pending',
                operator_id=current_user.id,
                total_amount=0,
            )
            db.session.add(new_order)
            db.session.flush()

            total_amount = 0
            for item in source.items:
                qty = round_to_2_decimals(item.quantity or 0)
                if qty <= 0:
                    continue
                price = round_to_2_decimals(item.material.price if item.material and item.material.price else 0)
                amount = round_to_2_decimals(qty * price)
                db.session.add(SubcontractItem(
                    subcontract_order_id=new_order.id,
                    material_id=item.material_id,
                    quantity=qty,
                    returned_quantity=0,
                    loss=0,
                ))
                total_amount = round_to_2_decimals(total_amount + amount)

            new_order.total_amount = total_amount
            db.session.commit()
            log_operation('复制委外单', f'{source.order_no} -> {new_order.order_no}', 'subcontract', new_order.id)
            return jsonify({
                'status': 'success',
                'msg': '复制成功，已生成新的委外单草稿',
                'id': new_order.id,
                'order_no': new_order.order_no,
                'redirect_url': url_for('subcontract_detail', id=new_order.id),
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'复制委外单失败: {e}')
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/submit', methods=['POST'])
    @require_role('production')
    @login_required
    def submit_subcontract(id):
        """提交委外单（pending -> processing）"""
        from app import SubcontractOrder, api_error, log_operation
        order = SubcontractOrder.query.get_or_404(id)
        if order.status != 'pending':
            return api_error('只有待处理状态的委外单可以提交')
        if not order.items:
            return api_error('请先添加产品明细再提交')
        try:
            order.status = 'processing'
            db.session.commit()
            log_operation('提交委外单', f'委外单：{order.order_no}', 'subcontract', id)
            return jsonify({'status': 'success', 'msg': '委外单已提交，进入加工中'})
        except Exception:
            db.session.rollback()
            return api_error('提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/revert_to_pending', methods=['POST'])
    @require_role('production')
    @login_required
    def revert_subcontract_to_pending(id):
        """反提交委外单（processing/cancelled -> pending）"""
        from app import SubcontractOrder, api_error, log_operation
        order = SubcontractOrder.query.get_or_404(id)
        if order.status == 'completed':
            return api_error('已完结的委外单请使用「反完结」按钮')
        if order.status == 'pending':
            return api_error('该委外单已经是待处理状态')
        # 已发料或已收货的反提交需要先回滚库存
        if order.issue_orders:
            return api_error('该委外单已发料，不能反提交')
        try:
            order.status = 'pending'
            db.session.commit()
            log_operation('反提交委外单', f'委外单：{order.order_no}', 'subcontract', id)
            return jsonify({'status': 'success', 'msg': '反提交成功，单据已回到待处理'})
        except Exception:
            db.session.rollback()
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/delete', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_subcontract(id):
        from app import SubcontractItem, SubcontractOrder, api_error
        order = SubcontractOrder.query.get_or_404(id)
        # 仅待处理状态可删除，避免删除已发料/已收货/进行中的委外单造成库存与单据不一致
        if order.status != 'pending':
            return api_error('只有待处理状态的委外加工单可以删除')
        # 已有发料/收货单据关联的委外单不能删除，否则会破坏外键与库存追溯链
        if order.issue_orders:
            return api_error('该委外加工单已有关联发料单，不能删除')
        if order.receive_orders:
            return api_error('该委外加工单已有关联收货单，不能删除')
        SubcontractItem.query.filter_by(subcontract_order_id=id).delete()
        db.session.delete(order)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/batch_delete', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_delete_subcontract():
        from app import SubcontractItem, SubcontractOrder, api_error
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的委外加工单')
        for oid in ids:
            order = db.session.get(SubcontractOrder, oid)
            if not order:
                continue
            # 批量删除同样需要状态与关联校验，跳过不符合条件的单据并返回提示
            if order.status != 'pending':
                return api_error(f'委外加工单“{order.order_no}”非待处理状态，不能删除')
            if order.issue_orders:
                return api_error(f'委外加工单“{order.order_no}”已有关联发料单，不能删除')
            if order.receive_orders:
                return api_error(f'委外加工单“{order.order_no}”已有关联收货单，不能删除')
            SubcontractItem.query.filter_by(subcontract_order_id=oid).delete()
            db.session.delete(order)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/batch_update_status', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_update_subcontract_status():
        from app import SubcontractOrder, api_error
        data = request.get_json(silent=True)
        if isinstance(data, dict):
            ids = data.get('ids', [])
            status = data.get('status', data.get('action', 'pending'))
        else:
            ids = request.form.getlist('ids')
            status = request.form.get('status') or request.form.get('action') or 'pending'

        try:
            ids = [int(item) for item in ids]
        except (TypeError, ValueError):
            return api_error('委外单参数格式错误')

        if status not in {'pending', 'processing', 'completed', 'cancelled'}:
            return api_error('目标状态不合法')

        updated = 0
        for oid in ids:
            order = db.session.get(SubcontractOrder, oid)
            if order:
                order.status = status
                updated += 1
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success', 'count': updated, 'msg': f'状态更新成功，共处理 {updated} 条'})

    @app.route('/subcontract/export')
    @login_required
    def export_subcontract():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractItem, SubcontractOrder,
                         _apply_status_date_filters, _apply_subcontract_search,
                         _get_order_list_filters, _subcontract_status_label,
                         _workbook_response, parse_date_value)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'processing', 'completed', 'cancelled'))
        deadline_start = parse_date_value(request.args.get('deadline_start'))
        deadline_end = parse_date_value(request.args.get('deadline_end'))
        allowed_sorts = {'order_no', 'date', 'supplier_id', 'deadline', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractOrder.query.options(
            joinedload(SubcontractOrder.supplier),
            selectinload(SubcontractOrder.items).joinedload(SubcontractItem.material).joinedload(Material.unit),
            selectinload(SubcontractOrder.items).joinedload(SubcontractItem.unit),
        )
        query = _apply_status_date_filters(query, SubcontractOrder, status_filter, date_start, date_end)
        if deadline_start:
            query = query.filter(SubcontractOrder.deadline >= deadline_start)
        if deadline_end:
            query = query.filter(SubcontractOrder.deadline <= deadline_end)
        query = _apply_subcontract_search(query, search)
        sort_col = getattr(SubcontractOrder, sort_by, SubcontractOrder.created_at)
        orders = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for order in orders:
            if order.items:
                for item in order.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        order.order_no,
                        order.date.strftime('%Y-%m-%d') if order.date else '',
                        order.supplier.name if order.supplier else '',
                        order.contact or '',
                        order.phone or '',
                        order.deadline.strftime('%Y-%m-%d') if order.deadline else '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        item.quantity or 0,
                        item.returned_quantity or 0,
                        item.loss or 0,
                        _subcontract_status_label(order.status),
                        order.remark or '',
                    ])
            else:
                rows.append([order.order_no, order.date.strftime('%Y-%m-%d') if order.date else '', order.supplier.name if order.supplier else '', order.contact or '', order.phone or '', order.deadline.strftime('%Y-%m-%d') if order.deadline else '', '', '', '', '', 0, 0, 0, _subcontract_status_label(order.status), order.remark or ''])
        return _workbook_response(
            'subcontract_orders.xlsx',
            '委外加工',
            ['单据编号', '日期', '加工厂商', '联系人', '电话', '交货期限', '物料编码', '物料名称', '规格', '单位', '数量', '已回数量', '损耗', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/import', methods=['POST'])
    @require_role('production')
    @login_required
    def import_subcontract():
        from flask_login import current_user
        from app import (SubcontractItem, SubcontractOrder, _find_or_create_material,
                         _find_or_create_supplier, _get_excel_cell, _get_excel_number,
                         _import_result, _order_no_from_row, _parse_excel_date,
                         _read_import_sheet, api_error, round_to_2_decimals,
                         validate_excel_extension, validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的委外加工文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['单据编号', '委外加工单号', '委外单号'],
            'date': ['日期'],
            'supplier': ['加工厂商', '供应商'],
            'contact': ['联系人'],
            'phone': ['电话'],
            'deadline': ['交货期限', '交期'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['数量'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'supplier', 'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（加工厂商、物料编码、数量）。检测到的表头：{", ".join(header_row)}')
            orders_by_no = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                supplier_name = _get_excel_cell(row, col_map, 'supplier')
                material_code = _get_excel_cell(row, col_map, 'material_code')
                quantity = _get_excel_number(row, col_map, 'quantity')
                if not supplier_name or not material_code or quantity <= 0:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：加工厂商、物料编码为空或数量不正确')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'SC')
                order = orders_by_no.get(order_no)
                if not order:
                    if SubcontractOrder.query.filter_by(order_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：委外单号 {order_no} 已存在')
                        continue
                    supplier = _find_or_create_supplier(supplier_name)
                    order = SubcontractOrder(
                        order_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        supplier_id=supplier.id if supplier else None,
                        contact=_get_excel_cell(row, col_map, 'contact'),
                        phone=_get_excel_cell(row, col_map, 'phone'),
                        deadline=_parse_excel_date(_get_excel_cell(row, col_map, 'deadline'), None) if _get_excel_cell(row, col_map, 'deadline') else None,
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
                order.total_amount = (order.total_amount or 0) + round_to_2_decimals(quantity * (material.price or 0))
                db.session.add(SubcontractItem(
                    subcontract_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id,
                ))
                item_count += 1
            db.session.commit()
            return _import_result('委外加工单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'委外加工导入失败: {e}')
            return api_error(f'委外加工导入失败：{str(e)}')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/complete', methods=['POST'])
    @require_role('production')
    @login_required
    def complete_subcontract_order(id):
        """完结委外单"""
        from app import SubcontractOrder, api_error, log_operation
        order = SubcontractOrder.query.get_or_404(id)
        if order.status == 'completed':
            return api_error('该委外单已完结')
        if order.status == 'cancelled':
            return api_error('已取消的委外单不能完结')
        
        try:
            order.status = 'completed'
            db.session.commit()
            
            log_operation('完结委外单', f'委外单：{order.order_no}', 'subcontract', id)
            return jsonify({'status': 'success', 'msg': '委外单已完结'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/<int:id>/revert', methods=['POST'])
    @require_role('production')
    @login_required
    def revert_subcontract_order(id):
        """反完结委外单"""
        from app import SubcontractOrder, api_error, log_operation
        order = SubcontractOrder.query.get_or_404(id)
        if order.status != 'completed':
            return api_error('只有已完结的委外单可以反完结')
        try:
            order.status = 'processing' if any(issue.status == 'completed' for issue in order.issue_orders) or any(receive.status == 'completed' for receive in order.receive_orders) else 'pending'
            db.session.commit()
            log_operation('反完结委外单', f'委外单：{order.order_no}', 'subcontract', id)
            return jsonify({'status': 'success', 'msg': '反完结成功'})
        except Exception:
            db.session.rollback()
            return api_error('反完结失败，请稍后重试')

    @app.route('/subcontract_issue')
    @app.route('/subcontract/issue')
    @login_required
    def subcontract_issue_list():
        """委外发料单列表"""
        from datetime import date
        from sqlalchemy.orm import joinedload, selectinload
        from app import (SubcontractIssue, SubcontractIssueItem, SubcontractOrder,
                         Supplier, Unit, _apply_status_date_filters,
                         _apply_subcontract_issue_search, _get_order_list_filters)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'issue_no', 'date', 'subcontract_order_id', 'supplier_id', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractIssue.query.options(
            joinedload(SubcontractIssue.subcontract_order),
            joinedload(SubcontractIssue.supplier),
            joinedload(SubcontractIssue.operator),
            selectinload(SubcontractIssue.items).joinedload(SubcontractIssueItem.material)
        )
        query = _apply_status_date_filters(query, SubcontractIssue, status_filter, date_start, date_end)
        query = _apply_subcontract_issue_search(query, search)
        sort_col = getattr(SubcontractIssue, sort_by, SubcontractIssue.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        issues = pagination.items
        subcontract_orders = SubcontractOrder.query.filter_by(status='processing').all()
        suppliers = Supplier.query.all()
        units = Unit.query.all()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template(
            'subcontract_issue.html',
            issues=issues,
            pagination=pagination,
            subcontract_orders=subcontract_orders,
            suppliers=suppliers,
            units=units,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            per_page=per_page,
            today=date.today()
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/add', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract_issue():
        """新增委外发料单"""
        from flask_login import current_user
        from app import (Material, SubcontractIssue, SubcontractIssueItem,
                         SubcontractOrder, api_error, generate_order_no, log_operation,
                         parse_float_value, round_to_2_decimals)
        try:
            subcontract_order_id = request.form.get('subcontract_order_id')
            issue_no = (request.form.get('issue_no') or '').strip()
            remark = (request.form.get('remark') or '').strip()
            
            if not subcontract_order_id:
                return api_error('请选择委外加工单')
            
            subcontract_order = SubcontractOrder.query.get(int(subcontract_order_id))
            if not subcontract_order:
                return api_error('委外加工单不存在')
            
            if not issue_no:
                issue_no = generate_order_no('SF')
            
            issue = SubcontractIssue(
                issue_no=issue_no,
                subcontract_order_id=int(subcontract_order_id),
                supplier_id=subcontract_order.supplier_id,
                remark=remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(issue)
            db.session.flush()

            material_ids = request.form.getlist('material_id')
            material_codes = request.form.getlist('material_code')
            quantities = request.form.getlist('quantity')
            unit_ids = request.form.getlist('unit_id')
            remarks = request.form.getlist('item_remark')
            added = 0
            for idx, material_id in enumerate(material_ids):
                quantity = round_to_2_decimals(parse_float_value(quantities[idx] if idx < len(quantities) else None, 0))
                material_code = (material_codes[idx] if idx < len(material_codes) else '').strip()
                if (not material_id and not material_code) or quantity <= 0:
                    continue
                material = None
                if material_id:
                    try:
                        material = db.session.get(Material, int(material_id))
                    except (TypeError, ValueError):
                        material = None
                if not material and material_code:
                    material = Material.query.filter_by(code=material_code).first()
                if not material:
                    continue
                unit_id = unit_ids[idx] if idx < len(unit_ids) else ''
                db.session.add(SubcontractIssueItem(
                    issue_id=issue.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=int(unit_id) if unit_id else material.unit_id,
                    remark=remarks[idx] if idx < len(remarks) else ''
                ))
                added += 1
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '创建失败，请稍后重试'}), 500
            
            log_operation('新增委外发料单', f'发料单：{issue_no}', 'subcontract_issue', issue.id)
            return jsonify({'status': 'success', 'msg': '委外发料单创建成功', 'id': issue.id})
        except Exception as e:
            db.session.rollback()
            return api_error('创建失败，请稍后重试')

    @app.route('/subcontract/issue/<int:id>')
    @app.route('/subcontract_issue/<int:id>')
    @login_required
    def subcontract_issue_detail_fragment(id):
        from app import SubcontractIssue
        issue = SubcontractIssue.query.get_or_404(id)
        rows = [
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">',
            '<thead><tr><th>物料编码</th><th>物料名称</th><th class="text-end">数量</th><th>单位</th><th>备注</th></tr></thead><tbody>'
        ]
        for item in issue.items:
            rows.append(
                f'<tr><td>{item.material.code if item.material else ""}</td>'
                f'<td>{item.material.name if item.material else ""}</td>'
                f'<td class="text-end">{item.quantity or 0:.2f}</td>'
                f'<td>{item.unit.name if item.unit else ""}</td>'
                f'<td>{item.remark or ""}</td></tr>'
            )
        if not issue.items:
            rows.append('<tr><td colspan="5" class="text-center text-muted">暂无明细</td></tr>')
        rows.append('</tbody></table></div>')
        return ''.join(rows)

    @app.route('/subcontract/issue/<int:id>/print')
    @app.route('/subcontract_issue/<int:id>/print')
    @login_required
    def print_subcontract_issue(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractIssue, SubcontractIssueItem, _fmt_date,
                         _material_row_common, _operator_name, _render_generic_document_print)
        issue = SubcontractIssue.query.options(
            joinedload(SubcontractIssue.subcontract_order),
            joinedload(SubcontractIssue.supplier),
            joinedload(SubcontractIssue.operator),
            selectinload(SubcontractIssue.items).joinedload(SubcontractIssueItem.material).joinedload(Material.unit),
            selectinload(SubcontractIssue.items).joinedload(SubcontractIssueItem.unit),
        ).get_or_404(id)
        rows = [_material_row_common(item) for item in issue.items]
        return _render_generic_document_print({
            'title': '委外发料单',
            'subtitle': 'SUBCONTRACT ISSUE',
            'number_label': '发料单号',
            'number': issue.issue_no,
            'date_label': '发料日期',
            'date': _fmt_date(issue.date),
            'status': issue.status,
            'info': [
                ('委外加工单', issue.subcontract_order.order_no if issue.subcontract_order else ''),
                ('加工厂商', issue.supplier.name if issue.supplier else ''),
                ('制单人', _operator_name(issue)),
                ('创建时间', _fmt_date(issue.created_at)),
            ],
            'remark': issue.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '发料数量', 'right'),
                ('remark', '备注', ''),
            ],
            'rows': rows,
            'signatures': ['制单', '发料', '委外签收', '仓库主管'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/<int:id>/item/add', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/<int:id>/item/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract_issue_item(id):
        """添加委外发料明细"""
        from app import (Material, SubcontractIssue, SubcontractIssueItem,
                         allow_negative_stock, api_error, is_stock_sufficient,
                         normalize_stock_quantity, parse_float_value)
        issue = SubcontractIssue.query.get_or_404(id)
        if issue.status != 'pending':
            return api_error('只有待发料状态可以添加明细')
        
        try:
            material_code = (request.form.get('material_code') or '').strip()
            quantity = parse_float_value(request.form.get('quantity'), 0)

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
            
            item = SubcontractIssueItem(
                issue_id=id,
                material_id=material.id,
                quantity=quantity,
                unit_id=material.unit_id
            )
            db.session.add(item)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '添加失败，请稍后重试'}), 500
            
            return jsonify({'status': 'success', 'msg': '发料明细添加成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/<int:id>/complete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/<int:id>/complete', methods=['POST'])
    @require_role('production')
    @login_required
    def complete_subcontract_issue(id):
        """完成委外发料"""
        from sqlalchemy.orm import selectinload
        from app import (SubcontractIssue, _acquire_order_write_lock,
                         allow_negative_stock, api_error, deduct_stock_atomic,
                         is_stock_sufficient, log_operation, normalize_stock_quantity)
        issue = SubcontractIssue.query.get_or_404(id)
        if issue.status != 'pending':
            return api_error('只有待发料状态可以完成发料')

        if not issue.items:
            return api_error('发料单没有明细，无法完成')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复扣库存
            locked, ok = _acquire_order_write_lock(SubcontractIssue, id, 'pending', selectinload(SubcontractIssue.items))
            if not ok:
                return api_error('该委外发料单已提交，不能重复操作')
            issue = locked
            if not issue.items:
                db.session.rollback()
                return api_error('发料单没有明细，无法完成')
            # 先检查库存是否充足
            for item in issue.items:
                if item.material:
                    current_stock = normalize_stock_quantity(item.material.stock or 0)
                    quantity = normalize_stock_quantity(item.quantity or 0)
                    if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                        db.session.rollback()
                        return jsonify({
                            'status': 'error',
                            'msg': f'物料 {item.material.code} 库存不足，当前库存：{current_stock:.2f}'
                        })

            # 扣减库存（使用原子扣减并检查返回值，避免并发超卖与失败仍标记 completed）
            for item in issue.items:
                if item.material:
                    ok, error_msg, _ = deduct_stock_atomic(item.material_id, item.quantity or 0,
                                 transaction_type='subcontract_issue',
                                 reference_type='subcontract_issue',
                                 reference_id=issue.id)
                    if not ok:
                        db.session.rollback()
                        return api_error(error_msg or '库存扣减失败')

            issue.status = 'completed'
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return api_error('提交失败，请稍后重试')

            log_operation('完成委外发料', f'发料单：{issue.issue_no}', 'subcontract_issue', id)
            return jsonify({'status': 'success', 'msg': '委外发料完成，库存已扣减'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/<int:id>/revert', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/<int:id>/revert', methods=['POST'])
    @require_role('production')
    @login_required
    def revert_subcontract_issue(id):
        """反提交委外发料"""
        from sqlalchemy.orm import selectinload
        from app import (SubcontractIssue, _acquire_order_write_lock, add_stock,
                         api_error, log_operation)
        issue = SubcontractIssue.query.get_or_404(id)
        if issue.status != 'completed':
            return api_error('只有已发料的委外发料单可以反提交')
        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复恢复
            locked, ok = _acquire_order_write_lock(SubcontractIssue, id, 'completed', selectinload(SubcontractIssue.items))
            if not ok:
                return api_error('该委外发料单已反提交，不能重复操作')
            issue = locked
            for item in issue.items:
                if item.material:
                    ok, err = add_stock(item.material, item.quantity or 0,
                                        transaction_type='revert_subcontract_issue',
                                        reference_type='subcontract_issue',
                                        reference_id=issue.id,
                                        remark=f'反提交委外发料 {issue.issue_no}')
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存恢复失败')
            issue.status = 'pending'
            db.session.commit()
            log_operation('反提交委外发料', f'发料单：{issue.issue_no}', 'subcontract_issue', id)
            return jsonify({'status': 'success', 'msg': '反提交成功，库存已恢复'})
        except Exception:
            db.session.rollback()
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/<int:id>/delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/<int:id>/delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/delete/<int:id>', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_subcontract_issue(id):
        """删除委外发料单"""
        from app import SubcontractIssue, SubcontractIssueItem, api_error, log_operation
        issue = SubcontractIssue.query.get_or_404(id)
        if issue.status != 'pending':
            return api_error('只有待发料状态可以删除')
        
        try:
            # 删除明细
            SubcontractIssueItem.query.filter_by(issue_id=id).delete()
            db.session.delete(issue)
            db.session.commit()
            
            log_operation('删除委外发料单', f'发料单：{issue.issue_no}', 'subcontract_issue', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/batch_delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/batch_delete', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_delete_subcontract_issue():
        from app import (SubcontractIssue, SubcontractIssueItem, api_error, log_operation)
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的委外发料单')
        issues = SubcontractIssue.query.filter(SubcontractIssue.id.in_(ids)).all()
        blocked = [issue.issue_no for issue in issues if issue.status != 'pending']
        if blocked:
            return api_error('只能删除待发料单据：' + '、'.join(blocked))
        try:
            SubcontractIssueItem.query.filter(SubcontractIssueItem.issue_id.in_(ids)).delete(synchronize_session=False)
            deleted = SubcontractIssue.query.filter(SubcontractIssue.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            log_operation('批量删除委外发料单', f'共删除 {deleted} 张发料单', 'subcontract_issue')
            return jsonify({'status': 'success', 'msg': f'删除成功，共删除 {deleted} 张委外发料单'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除委外发料单失败: {e}')
            return api_error('删除失败，请稍后重试')

    @app.route('/subcontract_issue/export')
    @app.route('/subcontract/issue/export')
    @login_required
    def export_subcontract_issue():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractIssue, SubcontractIssueItem,
                         _apply_status_date_filters, _apply_subcontract_issue_search,
                         _get_order_list_filters, _subcontract_issue_status_label,
                         _workbook_response)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'issue_no', 'date', 'subcontract_order_id', 'supplier_id', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractIssue.query.options(
            joinedload(SubcontractIssue.subcontract_order),
            joinedload(SubcontractIssue.supplier),
            selectinload(SubcontractIssue.items).joinedload(SubcontractIssueItem.material).joinedload(Material.unit),
            selectinload(SubcontractIssue.items).joinedload(SubcontractIssueItem.unit),
        )
        query = _apply_status_date_filters(query, SubcontractIssue, status_filter, date_start, date_end)
        query = _apply_subcontract_issue_search(query, search)
        sort_col = getattr(SubcontractIssue, sort_by, SubcontractIssue.created_at)
        issues = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for issue in issues:
            if issue.items:
                for item in issue.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        issue.issue_no,
                        issue.date.strftime('%Y-%m-%d') if issue.date else '',
                        issue.subcontract_order.order_no if issue.subcontract_order else '',
                        issue.supplier.name if issue.supplier else '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        item.quantity or 0,
                        _subcontract_issue_status_label(issue.status),
                        item.remark or issue.remark or '',
                    ])
            else:
                rows.append([issue.issue_no, issue.date.strftime('%Y-%m-%d') if issue.date else '', issue.subcontract_order.order_no if issue.subcontract_order else '', issue.supplier.name if issue.supplier else '', '', '', '', '', 0, _subcontract_issue_status_label(issue.status), issue.remark or ''])
        return _workbook_response(
            'subcontract_issues.xlsx',
            '委外发料',
            ['发料单号', '日期', '委外加工单号', '加工厂商', '物料编码', '物料名称', '规格', '单位', '数量', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_issue/import', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/issue/import', methods=['POST'])
    @require_role('production')
    @login_required
    def import_subcontract_issue():
        from flask_login import current_user
        from app import (SubcontractIssue, SubcontractIssueItem, SubcontractOrder,
                         _find_or_create_material, _find_or_create_supplier,
                         _get_excel_cell, _get_excel_number, _import_result,
                         _order_no_from_row, _parse_excel_date, _read_import_sheet,
                         api_error, validate_excel_extension, validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的委外发料文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['发料单号', '单据编号'],
            'date': ['日期'],
            'subcontract_no': ['委外加工单号', '委外单号'],
            'supplier': ['加工厂商', '供应商'],
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
                issue_no = _order_no_from_row(row, col_map, 'order_no', 'SF')
                issue = orders_by_no.get(issue_no)
                if not issue:
                    if SubcontractIssue.query.filter_by(issue_no=issue_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：发料单号 {issue_no} 已存在')
                        continue
                    subcontract_no = _get_excel_cell(row, col_map, 'subcontract_no')
                    subcontract_order = SubcontractOrder.query.filter_by(order_no=subcontract_no).first() if subcontract_no else None
                    supplier = subcontract_order.supplier if subcontract_order else _find_or_create_supplier(_get_excel_cell(row, col_map, 'supplier'))
                    issue = SubcontractIssue(
                        issue_no=issue_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        subcontract_order_id=subcontract_order.id if subcontract_order else None,
                        supplier_id=supplier.id if supplier else None,
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        status='pending',
                        operator_id=current_user.id,
                    )
                    db.session.add(issue)
                    db.session.flush()
                    orders_by_no[issue_no] = issue
                    order_count += 1
                material = _find_or_create_material(
                    material_code,
                    _get_excel_cell(row, col_map, 'material_name'),
                    _get_excel_cell(row, col_map, 'spec'),
                    _get_excel_cell(row, col_map, 'unit'),
                )
                db.session.add(SubcontractIssueItem(
                    issue_id=issue.id,
                    material_id=material.id,
                    quantity=quantity,
                    unit_id=material.unit_id,
                    remark=_get_excel_cell(row, col_map, 'remark'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('委外发料单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'委外发料导入失败: {e}')
            return api_error(f'委外发料导入失败：{str(e)}')

    @app.route('/subcontract_receive')
    @app.route('/subcontract/receive')
    @login_required
    def subcontract_receive_list():
        """委外收货单列表"""
        from datetime import date
        from sqlalchemy.orm import joinedload, selectinload
        from app import (SubcontractOrder, SubcontractReceive, SubcontractReceiveItem,
                         Supplier, Unit, _apply_status_date_filters,
                         _apply_subcontract_receive_search, _get_order_list_filters)
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        page = max(1, request.args.get('page', default=1, type=int))
        per_page = request.args.get('per_page', default=20, type=int)
        if per_page not in (20, 50, 100, 200):
            per_page = 20
        allowed_sorts = {'receive_no', 'date', 'subcontract_order_id', 'supplier_id', 'total_quantity', 'total_scrap', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractReceive.query.options(
            joinedload(SubcontractReceive.subcontract_order),
            joinedload(SubcontractReceive.supplier),
            joinedload(SubcontractReceive.operator),
            selectinload(SubcontractReceive.items).joinedload(SubcontractReceiveItem.material)
        )
        query = _apply_status_date_filters(query, SubcontractReceive, status_filter, date_start, date_end)
        query = _apply_subcontract_receive_search(query, search)
        sort_col = getattr(SubcontractReceive, sort_by, SubcontractReceive.created_at)
        pagination = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).paginate(page=page, per_page=per_page, error_out=False)
        receives = pagination.items
        subcontract_orders = SubcontractOrder.query.filter_by(status='processing').all()
        suppliers = Supplier.query.all()
        units = Unit.query.all()
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template(
            'subcontract_receive.html',
            receives=receives,
            pagination=pagination,
            subcontract_orders=subcontract_orders,
            suppliers=suppliers,
            units=units,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            per_page=per_page,
            today=date.today()
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/add', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract_receive():
        """新增委外收货单"""
        from flask_login import current_user
        from app import (Material, SubcontractOrder, SubcontractReceive,
                         SubcontractReceiveItem, api_error, generate_order_no,
                         log_operation, parse_float_value, round_to_2_decimals)
        try:
            subcontract_order_id = request.form.get('subcontract_order_id')
            receive_no = (request.form.get('receive_no') or '').strip()
            remark = (request.form.get('remark') or '').strip()
            
            if not subcontract_order_id:
                return api_error('请选择委外加工单')
            
            subcontract_order = SubcontractOrder.query.get(int(subcontract_order_id))
            if not subcontract_order:
                return api_error('委外加工单不存在')
            
            if not receive_no:
                receive_no = generate_order_no('SR')
            
            receive = SubcontractReceive(
                receive_no=receive_no,
                subcontract_order_id=int(subcontract_order_id),
                supplier_id=subcontract_order.supplier_id,
                remark=remark,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(receive)
            db.session.flush()

            material_ids = request.form.getlist('material_id')
            material_codes = request.form.getlist('material_code')
            quantities = request.form.getlist('quantity')
            scrap_quantities = request.form.getlist('scrap_quantity')
            unit_ids = request.form.getlist('unit_id')
            prices = request.form.getlist('price')
            remarks = request.form.getlist('item_remark')
            total_quantity = 0
            total_scrap = 0
            for idx, material_id in enumerate(material_ids):
                quantity = round_to_2_decimals(parse_float_value(quantities[idx] if idx < len(quantities) else None, 0))
                scrap_quantity = round_to_2_decimals(parse_float_value(scrap_quantities[idx] if idx < len(scrap_quantities) else None, 0))
                price = round_to_2_decimals(parse_float_value(prices[idx] if idx < len(prices) else None, 0))
                material_code = (material_codes[idx] if idx < len(material_codes) else '').strip()
                if (not material_id and not material_code) or quantity <= 0:
                    continue
                material = None
                if material_id:
                    try:
                        material = db.session.get(Material, int(material_id))
                    except (TypeError, ValueError):
                        material = None
                if not material and material_code:
                    material = Material.query.filter_by(code=material_code).first()
                if not material:
                    continue
                unit_id = unit_ids[idx] if idx < len(unit_ids) else ''
                db.session.add(SubcontractReceiveItem(
                    receive_id=receive.id,
                    material_id=material.id,
                    quantity=quantity,
                    scrap_quantity=scrap_quantity,
                    unit_id=int(unit_id) if unit_id else material.unit_id,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                    remark=remarks[idx] if idx < len(remarks) else ''
                ))
                total_quantity += quantity
                total_scrap += scrap_quantity
            receive.total_quantity = total_quantity
            receive.total_scrap = total_scrap
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '创建失败，请稍后重试'}), 500
            
            log_operation('新增委外收货单', f'收货单：{receive_no}', 'subcontract_receive', receive.id)
            return jsonify({'status': 'success', 'msg': '委外收货单创建成功', 'id': receive.id})
        except Exception as e:
            db.session.rollback()
            return api_error('创建失败，请稍后重试')

    @app.route('/subcontract/receive/<int:id>')
    @app.route('/subcontract_receive/<int:id>')
    @login_required
    def subcontract_receive_detail_fragment(id):
        from app import SubcontractReceive
        receive = SubcontractReceive.query.get_or_404(id)
        rows = [
            '<div class="table-responsive"><table class="table table-sm table-bordered mb-0">',
            '<thead><tr><th>物料编码</th><th>物料名称</th><th class="text-end">收货数量</th><th class="text-end">报废数量</th><th>单位</th><th class="text-end">单价</th><th class="text-end">金额</th></tr></thead><tbody>'
        ]
        for item in receive.items:
            rows.append(
                f'<tr><td>{item.material.code if item.material else ""}</td>'
                f'<td>{item.material.name if item.material else ""}</td>'
                f'<td class="text-end">{item.quantity or 0:.2f}</td>'
                f'<td class="text-end">{item.scrap_quantity or 0:.2f}</td>'
                f'<td>{item.unit.name if item.unit else ""}</td>'
                f'<td class="text-end">{item.price or 0:.2f}</td>'
                f'<td class="text-end">{item.amount or 0:.2f}</td></tr>'
            )
        if not receive.items:
            rows.append('<tr><td colspan="7" class="text-center text-muted">暂无明细</td></tr>')
        rows.append('</tbody></table></div>')
        return ''.join(rows)

    @app.route('/subcontract/receive/<int:id>/print')
    @app.route('/subcontract_receive/<int:id>/print')
    @login_required
    def print_subcontract_receive(id):
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractReceive, SubcontractReceiveItem, _fmt_date,
                         _material_row_common, _operator_name, _render_generic_document_print)
        receive = SubcontractReceive.query.options(
            joinedload(SubcontractReceive.subcontract_order),
            joinedload(SubcontractReceive.supplier),
            joinedload(SubcontractReceive.operator),
            selectinload(SubcontractReceive.items).joinedload(SubcontractReceiveItem.material).joinedload(Material.unit),
            selectinload(SubcontractReceive.items).joinedload(SubcontractReceiveItem.unit),
        ).get_or_404(id)
        rows = [
            _material_row_common(
                item,
                price=item.price or 0,
                amount=item.amount or 0,
                extra={'scrap_quantity': item.scrap_quantity or 0}
            )
            for item in receive.items
        ]
        return _render_generic_document_print({
            'title': '委外入库单',
            'subtitle': 'SUBCONTRACT RECEIVE',
            'number_label': '入库单号',
            'number': receive.receive_no,
            'date_label': '入库日期',
            'date': _fmt_date(receive.date),
            'status': receive.status,
            'info': [
                ('委外加工单', receive.subcontract_order.order_no if receive.subcontract_order else ''),
                ('加工厂商', receive.supplier.name if receive.supplier else ''),
                ('收货数量', f'{receive.total_quantity or 0:.2f}'),
                ('报废数量', f'{receive.total_scrap or 0:.2f}'),
                ('制单人', _operator_name(receive)),
                ('创建时间', _fmt_date(receive.created_at)),
            ],
            'remark': receive.remark or '',
            'columns': [
                ('code', '物料编码', ''),
                ('name', '物料名称', ''),
                ('spec', '规格', ''),
                ('unit', '单位', 'center'),
                ('quantity', '收货数量', 'right'),
                ('scrap_quantity', '报废数量', 'right'),
                ('price', '单价', 'right money'),
                ('amount', '金额', 'right money'),
                ('remark', '备注', ''),
            ],
            'rows': rows,
            'total_quantity': receive.total_quantity or sum(row.get('quantity', 0) or 0 for row in rows),
            'total_amount': sum(row.get('amount', 0) or 0 for row in rows),
            'signatures': ['制单', '收货', '质检', '仓库'],
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/<int:id>/item/add', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/<int:id>/item/add', methods=['POST'])
    @require_role('production')
    @login_required
    def add_subcontract_receive_item(id):
        """添加委外收货明细"""
        from app import (Material, SubcontractReceive, SubcontractReceiveItem,
                         api_error, parse_float_value)
        receive = SubcontractReceive.query.get_or_404(id)
        if receive.status != 'pending':
            return api_error('只有待收货状态可以添加明细')
        
        try:
            material_code = (request.form.get('material_code') or '').strip()
            quantity = parse_float_value(request.form.get('quantity'), 0)
            scrap_quantity = parse_float_value(request.form.get('scrap_quantity'), 0)

            if not material_code:
                return api_error('请选择物料')
            if quantity <= 0:
                return api_error('收货数量必须大于0')
            
            material = Material.query.filter_by(code=material_code).first()
            if not material:
                return api_error(f'物料 {material_code} 不存在')
            
            item = SubcontractReceiveItem(
                receive_id=id,
                material_id=material.id,
                quantity=quantity,
                scrap_quantity=scrap_quantity,
                unit_id=material.unit_id
            )
            db.session.add(item)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '添加失败，请稍后重试'}), 500
            
            return jsonify({'status': 'success', 'msg': '收货明细添加成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/<int:id>/complete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/<int:id>/complete', methods=['POST'])
    @require_role('production')
    @login_required
    def complete_subcontract_receive(id):
        """完成委外收货"""
        from sqlalchemy.orm import selectinload
        from app import (SubcontractReceive, _acquire_order_write_lock, add_stock,
                         api_error, log_operation)
        receive = SubcontractReceive.query.get_or_404(id)
        if receive.status != 'pending':
            return api_error('只有待收货状态可以完成收货')

        if not receive.items:
            return api_error('收货单没有明细，无法完成')

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复入库
            locked, ok = _acquire_order_write_lock(SubcontractReceive, id, 'pending', selectinload(SubcontractReceive.items))
            if not ok:
                return api_error('该委外收货单已提交，不能重复操作')
            receive = locked
            if not receive.items:
                db.session.rollback()
                return api_error('收货单没有明细，无法完成')
            # 增加库存
            total_quantity = 0
            total_scrap = 0
            for item in receive.items:
                if item.material:
                    # 走 add_stock 写流水+归一化，与 quick_receive_subcontract 对称
                    ok, err = add_stock(item.material, item.quantity or 0,
                                        transaction_type='subcontract_receive',
                                        reference_type='subcontract_receive',
                                        reference_id=receive.id,
                                        remark=f'完成委外收货 {receive.receive_no}')
                    if not ok:
                        db.session.rollback()
                        return api_error(err or '库存增加失败')
                    total_quantity += item.quantity or 0
                    total_scrap += item.scrap_quantity or 0

            receive.status = 'completed'
            receive.total_quantity = total_quantity
            receive.total_scrap = total_scrap
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500

            log_operation('完成委外收货', f'收货单：{receive.receive_no}', 'subcontract_receive', id)
            return jsonify({'status': 'success', 'msg': '委外收货完成，库存已增加'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/<int:id>/revert', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/<int:id>/revert', methods=['POST'])
    @require_role('production')
    @login_required
    def revert_subcontract_receive(id):
        """反提交委外收货"""
        from sqlalchemy.orm import selectinload
        from app import (SubcontractReceive, _acquire_order_write_lock, api_error,
                         deduct_stock, log_operation)
        receive = SubcontractReceive.query.get_or_404(id)
        if receive.status != 'completed':
            return api_error('只有已入库的委外收货单可以反提交')
        try:
            # 加写锁并重新读取状态，避免多 worker 并发反提交导致库存重复回退
            locked, ok = _acquire_order_write_lock(SubcontractReceive, id, 'completed', selectinload(SubcontractReceive.items))
            if not ok:
                return api_error('该委外收货单已反提交，不能重复操作')
            receive = locked
            for item in receive.items:
                if item.material:
                    ok, error_msg = deduct_stock(
                        item.material,
                        item.quantity or 0,
                        transaction_type='revert_subcontract_receive',
                        reference_type='subcontract_receive',
                        reference_id=receive.id,
                        remark=f'反提交委外收货 {receive.receive_no}'
                    )
                    if not ok:
                        db.session.rollback()
                        return api_error(error_msg or '库存回退失败')
            receive.status = 'pending'
            db.session.commit()
            log_operation('反提交委外收货', f'收货单：{receive.receive_no}', 'subcontract_receive', id)
            return jsonify({'status': 'success', 'msg': '反提交成功，库存已回退'})
        except Exception:
            db.session.rollback()
            return api_error('反提交失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/<int:id>/delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/<int:id>/delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/delete/<int:id>', methods=['POST'])
    @require_role('production')
    @login_required
    def delete_subcontract_receive(id):
        """删除委外收货单"""
        from app import SubcontractReceive, SubcontractReceiveItem, api_error, log_operation
        receive = SubcontractReceive.query.get_or_404(id)
        if receive.status != 'pending':
            return api_error('只有待收货状态可以删除')
        
        try:
            # 删除明细
            SubcontractReceiveItem.query.filter_by(receive_id=id).delete()
            db.session.delete(receive)
            db.session.commit()
            
            log_operation('删除委外收货单', f'收货单：{receive.receive_no}', 'subcontract_receive', id)
            return jsonify({'status': 'success', 'msg': '删除成功'})
        except Exception as e:
            db.session.rollback()
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/batch_delete', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/batch_delete', methods=['POST'])
    @require_role('production')
    @login_required
    def batch_delete_subcontract_receive():
        from app import (SubcontractReceive, SubcontractReceiveItem, api_error, log_operation)
        data = request.get_json(silent=True) or {}
        ids = data.get('ids') or request.form.getlist('ids')
        ids = [int(item_id) for item_id in ids if str(item_id).isdigit()]
        if not ids:
            return api_error('请选择要删除的委外入库单')
        receives = SubcontractReceive.query.filter(SubcontractReceive.id.in_(ids)).all()
        blocked = [receive.receive_no for receive in receives if receive.status != 'pending']
        if blocked:
            return api_error('只能删除待入库单据：' + '、'.join(blocked))
        try:
            SubcontractReceiveItem.query.filter(SubcontractReceiveItem.receive_id.in_(ids)).delete(synchronize_session=False)
            deleted = SubcontractReceive.query.filter(SubcontractReceive.id.in_(ids)).delete(synchronize_session=False)
            db.session.commit()
            log_operation('批量删除委外入库单', f'共删除 {deleted} 张入库单', 'subcontract_receive')
            return jsonify({'status': 'success', 'msg': f'删除成功，共删除 {deleted} 张委外入库单'})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量删除委外入库单失败: {e}')
            return api_error('删除失败，请稍后重试')

    @app.route('/subcontract_receive/export')
    @app.route('/subcontract/receive/export')
    @login_required
    def export_subcontract_receive():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (Material, SubcontractReceive, SubcontractReceiveItem,
                         _apply_status_date_filters, _apply_subcontract_receive_search,
                         _get_order_list_filters, _subcontract_receive_status_label,
                         _workbook_response)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'receive_no', 'date', 'subcontract_order_id', 'supplier_id', 'total_quantity', 'total_scrap', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = SubcontractReceive.query.options(
            joinedload(SubcontractReceive.subcontract_order),
            joinedload(SubcontractReceive.supplier),
            selectinload(SubcontractReceive.items).joinedload(SubcontractReceiveItem.material).joinedload(Material.unit),
            selectinload(SubcontractReceive.items).joinedload(SubcontractReceiveItem.unit),
        )
        query = _apply_status_date_filters(query, SubcontractReceive, status_filter, date_start, date_end)
        query = _apply_subcontract_receive_search(query, search)
        sort_col = getattr(SubcontractReceive, sort_by, SubcontractReceive.created_at)
        receives = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc()).all()
        for receive in receives:
            if receive.items:
                for item in receive.items:
                    material = item.material
                    unit = item.unit or (material.unit if material and material.unit else None)
                    rows.append([
                        receive.receive_no,
                        receive.date.strftime('%Y-%m-%d') if receive.date else '',
                        receive.subcontract_order.order_no if receive.subcontract_order else '',
                        receive.supplier.name if receive.supplier else '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        unit.name if unit else '',
                        item.quantity or 0,
                        item.scrap_quantity or 0,
                        item.price or 0,
                        item.amount or 0,
                        _subcontract_receive_status_label(receive.status),
                        item.remark or receive.remark or '',
                    ])
            else:
                rows.append([receive.receive_no, receive.date.strftime('%Y-%m-%d') if receive.date else '', receive.subcontract_order.order_no if receive.subcontract_order else '', receive.supplier.name if receive.supplier else '', '', '', '', '', 0, 0, 0, 0, _subcontract_receive_status_label(receive.status), receive.remark or ''])
        return _workbook_response(
            'subcontract_receives.xlsx',
            '委外入库',
            ['入库单号', '日期', '委外加工单号', '加工厂商', '物料编码', '物料名称', '规格', '单位', '收货数量', '报废数量', '单价', '金额', '状态', '备注'],
            rows,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract_receive/import', methods=['POST'])
    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/subcontract/receive/import', methods=['POST'])
    @require_role('production')
    @login_required
    def import_subcontract_receive():
        from flask_login import current_user
        from app import (SubcontractOrder, SubcontractReceive, SubcontractReceiveItem,
                         _find_or_create_material, _find_or_create_supplier,
                         _get_excel_cell, _get_excel_number, _import_result,
                         _order_no_from_row, _parse_excel_date, _read_import_sheet,
                         api_error, round_to_2_decimals, validate_excel_extension,
                         validate_excel_size)
        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的委外入库文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)
        aliases = {
            'order_no': ['入库单号', '单据编号'],
            'date': ['日期'],
            'subcontract_no': ['委外加工单号', '委外单号'],
            'supplier': ['加工厂商', '供应商'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'quantity': ['收货数量', '入库数量', '数量'],
            'scrap_quantity': ['报废数量', '报废'],
            'price': ['单价', '价格'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'material_code', 'quantity'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（物料编码、收货数量）。检测到的表头：{", ".join(header_row)}')
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
                receive_no = _order_no_from_row(row, col_map, 'order_no', 'SR')
                receive = orders_by_no.get(receive_no)
                if not receive:
                    if SubcontractReceive.query.filter_by(receive_no=receive_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：入库单号 {receive_no} 已存在')
                        continue
                    subcontract_no = _get_excel_cell(row, col_map, 'subcontract_no')
                    subcontract_order = SubcontractOrder.query.filter_by(order_no=subcontract_no).first() if subcontract_no else None
                    supplier = subcontract_order.supplier if subcontract_order else _find_or_create_supplier(_get_excel_cell(row, col_map, 'supplier'))
                    receive = SubcontractReceive(
                        receive_no=receive_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        subcontract_order_id=subcontract_order.id if subcontract_order else None,
                        supplier_id=supplier.id if supplier else None,
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        status='pending',
                        total_quantity=0,
                        total_scrap=0,
                        operator_id=current_user.id,
                    )
                    db.session.add(receive)
                    db.session.flush()
                    orders_by_no[receive_no] = receive
                    order_count += 1
                material = _find_or_create_material(
                    material_code,
                    _get_excel_cell(row, col_map, 'material_name'),
                    _get_excel_cell(row, col_map, 'spec'),
                    _get_excel_cell(row, col_map, 'unit'),
                )
                scrap_quantity = _get_excel_number(row, col_map, 'scrap_quantity', 0)
                price = _get_excel_number(row, col_map, 'price', material.price or 0)
                amount = round_to_2_decimals(quantity * price)
                receive.total_quantity = (receive.total_quantity or 0) + quantity
                receive.total_scrap = (receive.total_scrap or 0) + scrap_quantity
                db.session.add(SubcontractReceiveItem(
                    receive_id=receive.id,
                    material_id=material.id,
                    quantity=quantity,
                    scrap_quantity=scrap_quantity,
                    unit_id=material.unit_id,
                    price=price,
                    amount=amount,
                    remark=_get_excel_cell(row, col_map, 'remark'),
                ))
                item_count += 1
            db.session.commit()
            return _import_result('委外入库单', order_count, item_count, skip, skip_details)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'委外入库导入失败: {e}')
            return api_error(f'委外入库导入失败：{str(e)}')