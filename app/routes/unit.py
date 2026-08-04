#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
计量单位（unit）域 Blueprint。

试点：从 app.py 拆分「基础资料-单位」的 5 个 CRUD 路由到此模块。
拆分原则：
- 完全保持原 URL（/unit、/unit/add、/unit/delete、/unit/<id>、/unit/<id>/edit）与业务逻辑不变。
- 依赖 app.py 内部定义（Unit 模型、_get_master_list_filters 等）时在函数内延迟导入，
  避免循环导入（参考 ai/routes.py 模式）。
- 日志统一使用 current_app.logger 替代 app.logger。
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, render_template, request
from flask_login import login_required

from db import db
from utils import require_role

unit_bp = Blueprint('unit', __name__)


@unit_bp.route('/unit')
@login_required
def unit_list():
    from app import (
        Unit,
        _apply_master_order,
        _apply_simple_search,
        _get_master_list_filters,
    )
    search, status_filter, sort_by, sort_order = _get_master_list_filters('code')
    allowed_sorts = {'id', 'code', 'name', 'created_at'}
    query = _apply_simple_search(Unit.query, Unit, search, ['code', 'name'])
    query, sort_by = _apply_master_order(query, Unit, sort_by, sort_order, allowed_sorts, 'code')
    units = query.all()
    return render_template(
        'unit.html',
        units=units,
        filters={'search': search, 'status': status_filter},
        sort_by=sort_by,
        sort_order=sort_order,
    )


@unit_bp.route('/unit/add', methods=['POST'])
@require_role('warehouse')
@login_required
def add_unit():
    from app import Unit, api_error
    code = (request.form.get('code') or '').strip()
    name = (request.form.get('name') or '').strip()
    if not code:
        return api_error('请输入单位编号')
    if not name:
        return api_error('请输入单位名称')
    if Unit.query.filter_by(code=code).first():
        return api_error('单位编号已存在')
    if Unit.query.filter_by(name=name).first():
        return api_error('单位名称已存在')
    unit = Unit(code=code, name=name)
    db.session.add(unit)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"数据库操作失败: {e}")
        return jsonify({"status": "error", "msg": "操作失败"}), 500
    return jsonify({'status': 'success', 'msg': '单位新增成功', 'id': unit.id, 'name': unit.name})


@unit_bp.route('/unit/delete', methods=['POST'])
@require_role('warehouse')
@login_required
def delete_unit():
    from app import Unit, api_error
    ids = request.json.get('ids', [])
    for id in ids:
        unit = db.session.get(Unit, id)
        if unit:
            # 单位被物料/委外/BOM/领料/调拨/调整/请购等单据引用时不能删除，
            # 否则 SQLite 不强制外键约束会导致单位记录被删除后引用方 unit_id 悬空
            if unit.materials:
                return api_error(f'单位“{unit.name}”已关联物料，不能删除')
            if unit.bom_items:
                return api_error(f'单位“{unit.name}”已被BOM引用，不能删除')
            if unit.requisition_items:
                return api_error(f'单位“{unit.name}”已被领料单引用，不能删除')
            if unit.subcontract_items or unit.subcontract_issue_items or unit.subcontract_receive_items:
                return api_error(f'单位“{unit.name}”已被委外单据引用，不能删除')
            if unit.transfer_items:
                return api_error(f'单位“{unit.name}”已被调拨单引用，不能删除')
            if unit.adjustment_items:
                return api_error(f'单位“{unit.name}”已被库存调整单引用，不能删除')
            if unit.purchase_request_items:
                return api_error(f'单位“{unit.name}”已被请购单引用，不能删除')
            db.session.delete(unit)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"数据库操作失败: {e}")
        return jsonify({"status": "error", "msg": "操作失败"}), 500
    return jsonify({'status': 'success'})


@unit_bp.route('/unit/<int:unit_id>')
@require_role('warehouse')
@login_required
def get_unit(unit_id):
    """M-01：行级编辑 - 返回单位详情 JSON。"""
    from app import Unit
    unit = db.session.get(Unit, unit_id)
    if not unit:
        return jsonify({'status': 'error', 'msg': '单位不存在'}), 404
    return jsonify({
        'status': 'success',
        'unit': {'id': unit.id, 'code': unit.code, 'name': unit.name}
    })


@unit_bp.route('/unit/<int:unit_id>/edit', methods=['POST'])
@require_role('warehouse')
@login_required
def edit_unit(unit_id):
    """M-01：单位行级编辑。"""
    from app import Unit, api_error
    unit = db.session.get(Unit, unit_id)
    if not unit:
        return jsonify({'status': 'error', 'msg': '单位不存在'}), 404
    code = (request.form.get('code') or '').strip()
    name = (request.form.get('name') or '').strip()
    if not code:
        return api_error('请输入单位编号')
    if not name:
        return api_error('请输入单位名称')
    dup = Unit.query.filter_by(code=code).first()
    if dup and dup.id != unit_id:
        return api_error('单位编号已存在')
    dup = Unit.query.filter_by(name=name).first()
    if dup and dup.id != unit_id:
        return api_error('单位名称已存在')
    unit.code = code
    unit.name = name
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'编辑单位失败: {e}')
        return jsonify({'status': 'error', 'msg': '编辑失败'}), 500
    return jsonify({'status': 'success', 'msg': '单位编辑成功'})