#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 库存预警（inventory_alert）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_inventory_alert_routes(app)」直接在 app 上注册路由，endpoint 名
# 保持不变（alert_list、batch_update_alert_thresholds），与 app.py 内原有 url_for
# 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils / sqlalchemy），不导入
#   app，避免循环导入。
# - app.py 内部定义（Material、MaterialCategory、Supplier、inventory_alert_enabled、
#   _material_alert_status_values、log_operation 等）在各路由函数内延迟导入（请求期
#   才执行），避免 app.py 模块加载期触发循环导入。
# - 日志统一使用 current_app.logger 替代 app.logger。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import current_app, flash, json, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy.orm import joinedload

from db import db
from utils import require_role, round_to_2_decimals


def _parse_alert_threshold_value(payload, key, label):
    value = payload.get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None or str(value).strip() == '':
        return False, None, None
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return False, None, f'{label}必须是数字'
    if parsed < 0:
        return False, None, f'{label}不能小于 0'
    return True, round_to_2_decimals(parsed), None


def _parse_alert_material_ids(raw_ids):
    ids = []
    seen = set()
    for raw_id in raw_ids or []:
        try:
            material_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if material_id <= 0 or material_id in seen:
            continue
        seen.add(material_id)
        ids.append(material_id)
    return ids


# no-test:reason=路由注册辅助函数，能力由 alert_* 各路由测试覆盖
def register_inventory_alert_routes(app):
    @app.route('/alert')
    @login_required
    def alert_list():
        from app import (
            Material,
            MaterialCategory,
            Supplier,
            _material_alert_status_values,
            inventory_alert_enabled,
        )
        if not inventory_alert_enabled():
            flash('库存预警/安全库存尚未启用，当前不显示库存不足预警。', 'info')
            return redirect(url_for('material_list'))

        search = (request.args.get('search') or '').strip()
        status_filter = (request.args.get('status') or '').strip()
        category_id = request.args.get('category_id', type=int) or 0
        supplier_id = request.args.get('supplier_id', type=int) or 0
        sort_by = request.args.get('sort', 'code')
        sort_order = request.args.get('order', 'asc')
        if status_filter not in ('low', 'danger', 'normal', 'disabled'):
            status_filter = ''
        if sort_by not in {'code', 'name', 'spec', 'category', 'supplier', 'stock', 'min_stock', 'safety_stock', 'status'}:
            sort_by = 'code'
        if sort_order not in ('asc', 'desc'):
            sort_order = 'asc'

        material_query = Material.query.options(
            joinedload(Material.category),
            joinedload(Material.supplier)
        )
        if category_id:
            material_query = material_query.filter(Material.category_id == category_id)
        if supplier_id:
            material_query = material_query.filter(Material.supplier_id == supplier_id)
        materials = material_query.order_by(Material.code.asc(), Material.id.asc()).all()
        low_stock = []
        danger_stock = []
        normal_stock = []
        alert_materials = []

        status_terms = {
            'low': {'low', '最低', '低于最低库存', '低于最小库存', '库存不足', '不足'},
            'danger': {'danger', '安全', '低于安全库存', '预警'},
            'normal': {'normal', '正常', '库存正常'},
            'disabled': {'disabled', 'ignore', '忽略', '不预警', '无需预警', '未启用预警'},
        }
        status_labels = {
            'low': '低于最低库存',
            'danger': '低于安全库存',
            'normal': '正常',
            'disabled': '未启用预警',
        }
        search_status = ''
        if search:
            search_lower = search.lower()
            for key, terms in status_terms.items():
                if any(search_lower == term.lower() or search_lower in term.lower() or term.lower() in search_lower for term in terms):
                    search_status = key
                    break

        for material in materials:
            stock, min_stock, safety_stock, alert_status = _material_alert_status_values(material)

            display_item = {
                'id': material.id,
                'code': material.code,
                'name': material.name,
                'spec': material.spec,
                'category': material.category.name if material.category else '',
                'supplier': material.supplier.name if material.supplier else '',
                'stock': stock,
                'min_stock': min_stock,
                'safety_stock': safety_stock,
                'status': alert_status,
                'status_label': status_labels[alert_status],
            }

            if alert_status == 'low':
                low_stock.append(display_item)
            elif alert_status == 'danger':
                danger_stock.append(display_item)
            elif alert_status == 'normal':
                normal_stock.append(display_item)

            include_item = alert_status in ('low', 'danger')
            if status_filter:
                include_item = alert_status == status_filter
            if search:
                haystack = ' '.join([
                    str(material.code or ''),
                    str(material.name or ''),
                    str(material.spec or ''),
                    str(material.category.name if material.category else ''),
                    str(material.supplier.name if material.supplier else ''),
                    status_labels[alert_status],
                    alert_status,
                ]).lower()
                include_item = include_item and (search.lower() in haystack or search_status == alert_status)
            if include_item:
                alert_materials.append(display_item)

        reverse = sort_order == 'desc'
        if sort_by == 'status':
            status_rank = {'low': 0, 'danger': 1, 'normal': 2, 'disabled': 3}
            alert_materials.sort(key=lambda item: (status_rank.get(item['status'], 9), item['code'] or ''), reverse=reverse)
        else:
            alert_materials.sort(key=lambda item: (item.get(sort_by) if item.get(sort_by) is not None else ''), reverse=reverse)

        disabled_stock_count = len(materials) - len(low_stock) - len(danger_stock) - len(normal_stock)
        filters = {'search': search, 'status': status_filter, 'category_id': category_id, 'supplier_id': supplier_id}
        categories = MaterialCategory.query.order_by(MaterialCategory.code.asc(), MaterialCategory.id.asc()).all()
        suppliers = Supplier.query.order_by(Supplier.code.asc(), Supplier.id.asc()).all()
        return render_template('alert.html',
                             alert_materials=alert_materials,
                             low_stock_count=len(low_stock),
                             danger_stock_count=len(danger_stock),
                             normal_stock_count=len(normal_stock),
                             disabled_stock_count=disabled_stock_count,
                             categories=categories,
                             suppliers=suppliers,
                             filters=filters,
                             sort_by=sort_by,
                             sort_order=sort_order)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/alert/batch_update_thresholds', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_update_alert_thresholds():
        from app import Material, inventory_alert_enabled, log_operation
        if not inventory_alert_enabled():
            return jsonify({'status': 'error', 'msg': '库存预警/安全库存尚未启用'}), 400

        payload = request.get_json(silent=True) if request.is_json else request.form.to_dict(flat=False)
        payload = payload or {}
        action = payload.get('action')
        if isinstance(action, list):
            action = action[0] if action else ''
        action = (action or '').strip()
        raw_ids = payload.get('ids', [])
        if isinstance(raw_ids, str):
            try:
                raw_ids = json.loads(raw_ids)
            except (TypeError, ValueError, json.JSONDecodeError):
                raw_ids = [raw_ids]
        ids = _parse_alert_material_ids(raw_ids)
        if not ids:
            return jsonify({'status': 'error', 'msg': '请先选择要设置的物料'}), 400

        disable_alert = action == 'disable'
        if disable_alert:
            update_min = True
            update_safety = True
            min_stock = 0
            safety_stock = 0
        else:
            update_min, min_stock, min_error = _parse_alert_threshold_value(payload, 'min_stock', '最低库存')
            if min_error:
                return jsonify({'status': 'error', 'msg': min_error}), 400
            update_safety, safety_stock, safety_error = _parse_alert_threshold_value(payload, 'safety_stock', '安全库存')
            if safety_error:
                return jsonify({'status': 'error', 'msg': safety_error}), 400
            if not update_min and not update_safety:
                return jsonify({'status': 'error', 'msg': '最低库存和安全库存至少填写一项'}), 400
            if update_min and update_safety and safety_stock < min_stock:
                return jsonify({'status': 'error', 'msg': '安全库存不能低于最低库存'}), 400

        materials = Material.query.filter(Material.id.in_(ids)).order_by(Material.code.asc(), Material.id.asc()).all()
        if not materials:
            return jsonify({'status': 'error', 'msg': '选择的物料不存在'}), 404

        if update_safety and not update_min:
            max_min_stock = max((material.min_stock or 0) for material in materials)
            if safety_stock < max_min_stock:
                return jsonify({
                    'status': 'error',
                    'msg': f'安全库存不能低于已选物料中的最高最低库存（{round_to_2_decimals(max_min_stock)}）'
                }), 400

        updated_codes = []
        for material in materials:
            if update_min:
                material.min_stock = min_stock
                if not update_safety and (material.reorder_point or 0) < min_stock:
                    material.reorder_point = min_stock
            if update_safety:
                material.reorder_point = safety_stock
            updated_codes.append(material.code)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'批量更新库存预警值失败: {e}')
            return jsonify({'status': 'error', 'msg': '批量设置失败，请稍后重试'}), 500

        changes = []
        if disable_alert:
            changes.append('取消预警')
        else:
            if update_min:
                changes.append(f'最低库存={min_stock:g}')
            if update_safety:
                changes.append(f'安全库存={safety_stock:g}')
        log_operation(
            '批量取消库存预警' if disable_alert else '批量设置库存预警值',
            f'物料 {len(materials)} 个，{", ".join(changes)}',
            'material'
        )
        return jsonify({
            'status': 'success',
            'msg': f'已取消 {len(materials)} 个物料的库存预警' if disable_alert else f'已更新 {len(materials)} 个物料的预警值',
            'updated': len(materials),
            'codes': updated_codes[:20],
        })