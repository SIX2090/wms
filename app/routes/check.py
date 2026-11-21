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
import hashlib
import math
from datetime import datetime

from flask import current_app, jsonify, render_template, request, send_file
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import String, cast

from db import db
from services.import_validation import InactiveMaterialImportError
from services.web_document_idempotency import (web_document_idempotent,
                                                   web_document_command_idempotent, stage_document_response)
from utils import require_role


# no-test:reason=纯查询展开辅助，能力由 test_check_add_category_generate 测试覆盖
def _expand_check_category_ids(root_id):
    """展开分类及其全部子孙分类 id（FEATURE-2026-09-05-001）。

    分类为树形（MaterialCategory.parent_id），BFS 逐层取子级；
    seen 集合防 parent_id 脏数据成环导致死循环。
    """
    from app import MaterialCategory
    seen = {root_id}
    frontier = [root_id]
    while frontier:
        rows = (MaterialCategory.query
                .filter(MaterialCategory.parent_id.in_(frontier))
                .with_entities(MaterialCategory.id)
                .all())
        frontier = [cid for (cid,) in rows if cid not in seen]
        seen.update(frontier)
    return list(seen)


# no-test:reason=纯统计辅助，能力由 test_bug_2026_09_06_001 覆盖
def _check_uncounted_alerts(check):
    """按明细行核对是否有实盘记录，显式录入零也算已盘。"""
    rows = [it for it in (check.items or []) if it.material_id]
    uncounted = [it for it in rows if not it.has_actual_count]
    if not uncounted:
        return 0, len(rows), []
    samples = []
    for it in uncounted[:10]:
        mat = it.material
        samples.append({
            'code': mat.code if mat else '',
            'name': mat.name if mat else '',
        })
    return len(uncounted), len(rows), samples


def _resolve_check_warehouse(value):
    """Resolve a check warehouse without guessing across name/code collisions."""
    from app import Warehouse
    if not value:
        return None
    matches = (Warehouse.query.filter_by(name=value).all()
               + Warehouse.query.filter_by(code=value).all())
    warehouses = {wh.id: wh for wh in matches}
    return next(iter(warehouses.values())) if len(warehouses) == 1 else None


# no-test:reason=纯统计辅助，能力由 test_bug_2026_09_06_002 覆盖
def _check_period_movement_alerts(check):
    """统计盘点单冻结期间本仓库涉及物料的流水及出入库净变动。

    冻结口径下，过账后账面 = 实盘 − 期间净变动。但系统此前对盘点期间是
    否发生出入库（采购入库/销售出库/调拨/其他调整等外部单据）完全不查，
    用户完成盘点后才发现账面与实物对不上，无法回溯。盘点过程本身（PC
    录入、手机扫码）只写 InventoryCheckItem，不写流水，因此流水变动必
    来自盘点单之外的业务单据。

    实现要点：
    - 仅统计本盘点单所属仓库（``check.warehouse == stock_txn.warehouse``）
      的流水；历史脏数据（warehouse_id 为 NULL）按 R2 不归入任意仓库，
      因此不计入动销；
    - 仅盘点单涉及的物料（item.material_id in (...)），避免无关注入；
    - 时间窗：``check.frozen_at`` → ``now``；frozen_at 为空时直接放行
      （按设计 frozen_at 在首次保存时由 save_check_table 设置，遗留
      老单据无 frozen_at 是已知的脏数据，不强制拦截）；
    - ``reference_type == 'check'`` 且 ``reference_id == check.id`` 的
      流水来自盘点单自身（理论上不会产生，但防御性排除）；
    - 净变动按物料聚合 SUM(quantity)，quantity 本身有正负（in +，out -）。

    返回 (has_movement, moved_material_count, samples[{code, name, net}])；
    has_movement 为 None 表示仓库不存在或名称／编码存在歧义，调用方必须拒绝完成。
    has_movement 表示存在相关流水；等量入库和出库净额为零时也需提示。
    """
    # BUG-2026-09-06-003：本仓库 app/ 目录即包根（app.py 为顶层模块，无
    # __init__.py），`from app.utils import X` 在真实启动布局（python app.py /
    # run_server.py，app 目录在 sys.path）下必然 ModuleNotFoundError——pytest
    # 因 rootdir 插入把 app 当命名空间包而掩盖此错。仓库统一写法是
    # `from app import X`（app.py 已从 utils 转导出 normalize_stock_quantity）。
    from app import StockTransaction, normalize_stock_quantity

    # 完成校验同时接受仓库名称与编码；两种匹配指向不同仓库时不能猜测。
    wh = _resolve_check_warehouse(check.warehouse)
    if wh is None:
        return None, 0, []

    if not check.frozen_at:
        return False, 0, []

    material_ids = [it.material_id for it in (check.items or []) if it.material_id]
    if not material_ids:
        return False, 0, []

    # 单条 SQL：按物料 SUM(quantity)，限定仓库 + 物料 + 时间窗 + 排除盘点单自身
    # 排除条件必须显式处理 NULL：reference_type 为 NULL 的流水（盘点过程本身不
    # 写流水，但其他外部单据历史脏数据可能 NULL）不能因 NOT (... AND ...) 的
    # 三值逻辑被全部误杀。这里用 OR 拆开：ref_type != 'check' OR ref_id != self
    # 才视为"非自身"——任一为 NULL 仍判 True。
    q = (db.session.query(
            StockTransaction.material_id,
            db.func.sum(StockTransaction.quantity).label('net'),
            db.func.count(StockTransaction.id).label('movement_count'))
         .filter(StockTransaction.material_id.in_(material_ids))
         .filter(StockTransaction.created_at >= check.frozen_at)
         .filter(db.or_(
             StockTransaction.reference_type != 'check',
             StockTransaction.reference_type.is_(None),
             StockTransaction.reference_id != check.id,
             StockTransaction.reference_id.is_(None),
         ))
         .group_by(StockTransaction.material_id))
    # 按仓库过滤：warehouse_id 与本盘点单仓库一致；历史脏数据 NULL 不计入
    q = q.filter(StockTransaction.warehouse_id == wh.id)
    rows = q.all()

    moved = []
    for material_id, net, movement_count in rows:
        net_n = normalize_stock_quantity(net or 0)
        if not movement_count:
            continue
        # 取物料编码/名称
        item = next((it for it in check.items if it.material_id == material_id), None)
        code = item.material.code if item and item.material else ''
        name = item.material.name if item and item.material else ''
        moved.append({'code': code, 'name': name, 'net': net_n})

    if not moved:
        return False, 0, []
    return True, len(moved), moved[:10]


def _check_complete_snapshot(check, warehouse_id):
    """Hash the complete check and relevant movement state, and summarize its risks.

    Call only inside the short, isolated write transaction used to complete the check.
    Unknown warehouse/time are reported separately and never assigned to this warehouse.
    """
    from app import StockTransaction, Warehouse, normalize_stock_quantity, location_management_enabled

    digest = hashlib.sha256()

    def _scalar(value):
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        return str(value)

    def _add(value):
        digest.update(json.dumps(value, ensure_ascii=True, separators=(',', ':'),
                                 allow_nan=False).encode('utf-8'))
        digest.update(b'\n')

    _add(['check', *[_scalar(getattr(check, key, None)) for key in (
        'id', 'check_no', 'status', 'warehouse', 'date', 'frozen_at', 'remark', 'operator_id')],
         _scalar(warehouse_id), bool(location_management_enabled())])
    items = list(check.items or [])
    materials = {}
    for item in items:
        material = getattr(item, 'material', None)
        material_id = getattr(item, 'material_id', None)
        if material_id:
            materials.setdefault(material_id, material)
        _add(['item', *[_scalar(getattr(item, key, None)) for key in (
            'id', 'material_id', 'system_stock', 'actual_stock', 'difference', 'reason',
            'area', 'counted_by', 'counted_at')],
             _scalar(getattr(material, 'code', None)), _scalar(getattr(material, 'name', None)),
             _scalar(getattr(material, 'unit_id', None))])

    uncounted, total, uncounted_samples = _check_uncounted_alerts(check)
    incomplete_count = sum(bool(getattr(item, 'counted_by', None)) !=
                           bool(getattr(item, 'counted_at', None)) for item in items)
    movement = {}
    unknown_warehouse = unknown_time = invalid_quantity = 0
    now = datetime.now()
    material_ids = sorted(materials)
    for offset in range(0, len(material_ids), 500):
        ids = material_ids[offset:offset + 500]
        query = (db.session.query(StockTransaction.id, StockTransaction.material_id,
                                  StockTransaction.warehouse_id, StockTransaction.quantity,
                                  cast(StockTransaction.created_at, String), StockTransaction.transaction_type,
                                  StockTransaction.reference_type, StockTransaction.reference_id)
                 .filter(StockTransaction.material_id.in_(ids))
                 .filter(db.or_(StockTransaction.warehouse_id == warehouse_id,
                                StockTransaction.warehouse_id.is_(None),
                                ~StockTransaction.warehouse_id.in_(db.session.query(Warehouse.id))))
                 .filter(db.or_(StockTransaction.reference_type != 'check',
                                StockTransaction.reference_type.is_(None),
                                StockTransaction.reference_id != check.id,
                                StockTransaction.reference_id.is_(None)))
                 .order_by(StockTransaction.id))
        for row in query.yield_per(500):
            tx_id, material_id, tx_warehouse, quantity, raw_created_at, tx_type, ref_type, ref_id = row
            try:
                created_at = datetime.fromisoformat(raw_created_at) if raw_created_at else None
                time_unknown = created_at is None or created_at > now
                if not time_unknown and check.frozen_at is not None and created_at < check.frozen_at:
                    continue
            except (TypeError, ValueError, OverflowError):
                time_unknown = True
            _add(['movement', *[_scalar(value) for value in row], time_unknown])
            if tx_warehouse != warehouse_id:
                unknown_warehouse += 1
            if time_unknown:
                unknown_time += 1
            try:
                qty = float(quantity)
                if not math.isfinite(qty):
                    raise ValueError('nonfinite quantity')
            except (TypeError, ValueError, OverflowError):
                invalid_quantity += 1
                continue
            if tx_warehouse == warehouse_id and not time_unknown and check.frozen_at is not None:
                previous = movement.get(material_id, 0.0)
                if previous is None:
                    continue
                net = previous + qty
                if not math.isfinite(net):
                    invalid_quantity += 1
                    movement[material_id] = None
                else:
                    movement[material_id] = net
    movement_samples = []
    for material_id in sorted(movement):
        material = materials[material_id]
        net = None
        if movement[material_id] is not None:
            try:
                net = normalize_stock_quantity(movement[material_id])
            except (ArithmeticError, ValueError, TypeError):
                # 极大有限数也可能超出 Decimal 量化精度，不能显示成零。
                invalid_quantity += 1
        movement_samples.append({'code': getattr(material, 'code', '') if material else '',
                                 'name': getattr(material, 'name', '') if material else '',
                                 'net': net})
    risks = {'uncounted': uncounted, 'total': total, 'uncounted_samples': uncounted_samples,
             'incomplete_count': incomplete_count,
             'movement_count': len(movement), 'movement_samples': movement_samples[:10],
             'unknown_warehouse_count': unknown_warehouse, 'unknown_time_count': unknown_time,
             'invalid_quantity_count': invalid_quantity, 'unknown_freeze': check.frozen_at is None}
    risks['has_risk'] = bool(uncounted or incomplete_count or movement or unknown_warehouse or unknown_time
                             or invalid_quantity or risks['unknown_freeze'])
    _add(['risk', *[_scalar(risks[key]) for key in (
        'uncounted', 'total', 'incomplete_count', 'movement_count', 'unknown_warehouse_count', 'unknown_time_count',
        'invalid_quantity_count', 'unknown_freeze')]])
    return digest.hexdigest(), risks


def _issue_check_confirmation(check_id, user_id, fingerprint):
    """Sign a short-lived acknowledgment bound to the user, check and full snapshot."""
    if not current_app.secret_key or user_id is None:
        raise ValueError('无法签发盘点确认凭据')
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt='wms-check-complete-v1')
    return serializer.dumps({'check_id': check_id, 'user_id': str(user_id), 'snapshot': fingerprint})


def _accept_check_confirmation(token, check_id, user_id, fingerprint):
    if not isinstance(token, str) or not token or len(token) > 1024 or user_id is None:
        return False
    if not current_app.secret_key:
        return False
    serializer = URLSafeTimedSerializer(current_app.secret_key, salt='wms-check-complete-v1')
    try:
        payload = serializer.loads(token, max_age=600)
    except (BadSignature, TypeError, ValueError):
        return False
    return payload == {'check_id': check_id, 'user_id': str(user_id), 'snapshot': fingerprint}


def _stage_inventory_check_audit(check, operation, previous_status, *, created=(), removed=()):
    """Save the count and any generated or withdrawn adjustments in the caller's transaction."""
    from services.document_stock_audit import stage_order_audit

    old = {'status': previous_status}
    new = {
        'status': check.status,
        'warehouse': check.warehouse,
        'items': [{
            'material_id': item.material_id, 'system_stock': item.system_stock,
            'actual_stock': item.actual_stock, 'difference': item.difference,
            'area': item.area, 'counted_by': item.counted_by, 'counted_at': item.counted_at,
        } for item in check.items],
        'moves_inventory': False,
    }
    for drafts, snapshot in ((created, new), (removed, old)):
        if drafts:
            snapshot['adjustments'] = [{
                'id': draft.id, 'number': draft.adjustment_no, 'warehouse': draft.warehouse,
                'items': [{'material_id': line.material_id, 'quantity': line.quantity,
                           'location': line.location} for line in draft.items],
            } for draft in drafts]
    stage_order_audit(
        operation, check, old=old, new=new, target_type='check', target_name=check.check_no,
        reason='盘点完成' if operation == 'complete_check' else '反提交盘点',
    )


# no-test:reason=路由注册辅助函数，能力由 check_* 各路由测试覆盖
def register_check_routes(app):
    @app.route('/check')
    @login_required
    def check_list():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword, _warehouse_document_match_clause,
                         get_active_warehouses,
                         get_default_warehouse, resolve_request_warehouse)
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
        warehouse, warehouse_error = resolve_request_warehouse(request.args)
        if warehouse:
            # BUG-2026-09-22-014：兼容仓库名/编码两种历史写法（R6 同根因收敛）
            query = query.filter(
                _warehouse_document_match_clause(InventoryCheck.warehouse, warehouse))
        elif warehouse_error:
            query = query.filter(db.false())
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
        from app import AdjustmentOrder
        retained = {row.source_id for row in db.session.query(AdjustmentOrder.source_id).filter(
            AdjustmentOrder.source_type == 'check', AdjustmentOrder.source_id.in_([c.id for c in checks])).distinct()}
        deletable_ids = {c.id for c in checks if c.status == 'pending' and c.id not in retained}
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'warehouse_id': warehouse.id if warehouse else '',
        }
        return render_template(
            'check.html',
            checks=checks, deletable_ids=deletable_ids,
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
        # INV-BATCH-001-D：行级盘点归属（counted_by_user）随 items 一并加载，
        # 避免 _build_check_batch_meta 逐行 lazy 查 User 造成 N+1。
        check = InventoryCheck.query.options(
            joinedload(InventoryCheck.operator),
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit),
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.counted_by_user),
        ).get_or_404(id)
        return _render_check_form(check)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/save_table', methods=['POST'])
    @require_role('warehouse')
    @login_required
    @web_document_idempotent
    def save_check_table():
        from datetime import date, datetime
        from flask_login import current_user
        from sqlalchemy.orm import selectinload
        from app import (InventoryCheck, InventoryCheckItem, InventoryCheckScanItem,
                         _acquire_order_write_lock, _clean_int,
                         _material_from_payload, _parse_form_date, api_error,
                         generate_order_no, get_default_warehouse,
                         get_warehouse_stock_quantities, log_operation,
                         location_management_enabled, parse_float_value, round_to_2_decimals,
                         resolve_inventory_warehouse_id, validate_inventory_warehouse)
        data = request.get_json(silent=True) or {}
        order_id = _clean_int(data.get('order_id'))
        check_no = (data.get('order_no') or data.get('check_no') or '').strip()
        header = data.get('header') or {}
        items_data = data.get('items') or []

        if not items_data:
            return api_error('请至少填写一条盘点明细')

        # BUG-2026-08-02-013：仓库必填（AGENTS.md 规则），未填写时自动带入默认仓库
        # P1-6：同时收 warehouse_id（ID 优先）与 warehouse 名称（旧客户端兜底）
        warehouse = (header.get('warehouse') or data.get('warehouse') or '').strip()
        raw_warehouse_id = header.get('warehouse_id') or data.get('warehouse_id')
        if not warehouse and not raw_warehouse_id:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse = default_wh.name
        if not warehouse and not raw_warehouse_id:
            return api_error('请选择仓库')
        # INV-AUDIT-005：仓库必须存在且 active
        wh_obj, wh_err = validate_inventory_warehouse(warehouse, raw_warehouse_id)
        if wh_err:
            return api_error(wh_err)
        warehouse = wh_obj.name
        # W1：盘点「系统库存」按仓库级口径取数（与库存查询/库存报表一致），
        # 此前取全局 material.stock，多仓库下 A+B 合计会把盘盈盘亏算错。
        warehouse_stock_map = get_warehouse_stock_quantities(wh_obj)

        try:
            if order_id:
                check = db.session.get(InventoryCheck, order_id)
                if not check:
                    return api_error('盘点单不存在，请刷新后重试')
                check_no = check.check_no
                if check.status != 'pending':
                    return api_error('只有草稿状态的盘点单可以修改')
                duplicate = InventoryCheck.query.filter(InventoryCheck.check_no == check_no, InventoryCheck.id != order_id).first()
                if duplicate:
                    return api_error('盘点单号已存在')
                # INV-BATCH-001-B：单据写锁，防多人并发保存同一盘点单互相覆盖
                locked, ok = _acquire_order_write_lock(
                    InventoryCheck, order_id, 'pending', selectinload(InventoryCheck.items))
                if not ok:
                    return api_error('该盘点单状态已变更，请刷新后重试')
                check = locked
            else:
                check_no = generate_order_no('CK')
                check = InventoryCheck.query.filter_by(check_no=check_no).first()
                if check:
                    if check.status != 'pending':
                        return api_error('盘点单号已存在')
                    db.session.rollback()
                    return api_error('盘点单号已存在，不能覆盖原单据。请刷新新增页面后重试；编辑原单请从原单据打开。', 409)
                else:
                    check = InventoryCheck(check_no=check_no, status='pending', operator_id=current_user.id)
                    db.session.add(check)

            if check.items and resolve_inventory_warehouse_id(check.warehouse) != wh_obj.id:
                db.session.rollback()
                return api_error('盘点明细已冻结账面，不能更换仓库；请新建盘点单')
            check.check_no = check_no
            check.date = _parse_form_date(data.get('date'), check.date if order_id else date.today())
            check.remark = (header.get('remark') or '').strip()
            check.warehouse = warehouse
            if not check.operator_id:
                check.operator_id = current_user.id
            db.session.flush()

            # INV-BATCH-001-B（BUG-2026-09-02-004）：行级 upsert 替换全删重建。
            # 旧行为每次保存删除全部明细再重建，且每行 system_stock 一律取
            # 保存时点的当前账面——多人轮流保存同一盘点单时账面基准被悄悄
            # 刷新：A 上午按账面 60 实盘 58（差 -2）；期间出库 30，B 下午
            # 补充一行再保存，A 的行账面被刷成 30，差异从 -2 变 +28，差异
            # 含义被改变且无任何提示。
            # 新行为（冻结快照语义）：
            # - 已有行（按物料匹配）保留 system_stock 冻结值，仅更新实盘/原因；
            # - 新增行取当前仓库级账面（视为该行首次录入时点的基准）；
            # - 提交集之外的旧行删除（全量提交语义与旧版一致）；
            # - 首次写入明细时设置 frozen_at，一经设置不再变更。
            existing_items = {item.id: item for item in check.items}
            legacy_rows = {}
            frozen_by_material = {}
            for item in sorted(check.items, key=lambda row: row.id):
                legacy_rows.setdefault((item.material_id, (item.area or '').strip()), []).append(item)
                frozen_by_material.setdefault(item.material_id, item.system_stock)
            claimed_ids = set()
            retained_ids = set()
            saved_rows = []
            submitted_keys = set()
            locations = location_management_enabled()
            for item_data in items_data:
                material = _material_from_payload(item_data)
                if not material:
                    return api_error(f'物料不存在：{item_data.get("code") or ""}')
                area = (item_data.get('area') or item_data.get('location') or '').strip()
                if locations and not area:
                    db.session.rollback()
                    return api_error(f'库位管理已启用，物料 {material.code} 请填写库位/区域')
                row_key = (material.id, area)
                if area and row_key in submitted_keys:
                    db.session.rollback()
                    return api_error(f'物料 {material.code} 在区域 {area or "未分区"} 重复，请合并后保存')
                submitted_keys.add(row_key)
                raw_actual = item_data.get('actual_stock')
                has_actual = raw_actual is not None and str(raw_actual).strip() != ''
                row = None
                if item_data.get('line_id') is not None:
                    row = existing_items.get(_clean_int(item_data['line_id']))
                    if row is None or row.id in claimed_ids:
                        db.session.rollback()
                        return api_error('盘点明细已变化或行号重复，请刷新后重试', 409)
                elif 'line_id' not in item_data and legacy_rows.get(row_key):
                    candidates = legacy_rows[row_key]
                    if len(candidates) != 1:
                        db.session.rollback()
                        return api_error('同物料存在多条盘点明细，请刷新后按原行编辑', 409)
                    if candidates[0].id not in claimed_ids:
                        row = candidates[0]
                if row is not None:
                    claimed_ids.add(row.id)
                    if row.material_id != material.id:
                        row = None
                if row is not None:
                    # 已有行：冻结账面保留，只更新实盘/原因/差异
                    retained_ids.add(row.id)
                    actual = round_to_2_decimals(parse_float_value(raw_actual, row.actual_stock)) if has_actual else row.actual_stock
                    cleared = 'line_id' in item_data and not has_actual and bool(
                        row.counted_at or row.counted_by or row.actual_stock != row.system_stock)
                    changed = has_actual and (row.counted_at is None or actual != row.actual_stock)
                    if (row.area or '') != area or changed or cleared:
                        InventoryCheckScanItem.query.filter_by(batch_item_id=row.id).update({'batch_item_id': None})
                    row.area = area
                    if cleared:
                        row.actual_stock = row.system_stock
                        row.counted_by = row.counted_at = None
                    elif changed:
                        row.actual_stock = actual
                        row.counted_by = current_user.id
                        row.counted_at = datetime.now()
                    row.difference = round_to_2_decimals(row.actual_stock - row.system_stock)
                    row.reason = (item_data.get('reason') or item_data.get('remark') or '').strip()
                else:
                    # 新增行：账面取当前仓库级（该行首次录入时点）
                    system_stock = round_to_2_decimals(warehouse_stock_map.get(material.id, 0) or 0)
                    if not area:
                        system_stock = frozen_by_material.setdefault(material.id, system_stock)
                    actual_stock = round_to_2_decimals(parse_float_value(raw_actual, system_stock)) if has_actual else system_stock
                    row = InventoryCheckItem(
                        inventory_check_id=check.id,
                        material_id=material.id,
                        area=area,
                        system_stock=system_stock,
                        actual_stock=actual_stock,
                        counted_by=current_user.id if has_actual else None,
                        counted_at=datetime.now() if has_actual else None,
                        difference=round_to_2_decimals(actual_stock - system_stock),
                        reason=(item_data.get('reason') or item_data.get('remark') or '').strip()
                    )
                    db.session.add(row)
                saved_rows.append(row)
            # 删除提交集之外的旧行
            for row_id, row in existing_items.items():
                if row_id not in retained_ids:
                    db.session.delete(row)
            # 首次写入明细即冻结账面基准
            if check.frozen_at is None:
                check.frozen_at = datetime.now()

            db.session.flush()
            response = {'status': 'success', 'msg': '保存成功', 'id': check.id,
                        'order_no': check.check_no, 'line_ids': [row.id for row in saved_rows]}
            stage_document_response(response)
            db.session.commit()
            log_operation('保存盘点单', f'盘点单：{check.check_no}', 'check', check.id)
            return jsonify(response)
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存盘点单表格失败: {e}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    @web_document_idempotent
    def add_check():
        from datetime import datetime
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         MaterialCategory, api_error, generate_order_no,
                         get_default_warehouse, get_warehouse_stock_quantities,
                         import_max_rows, log_operation,
                         normalize_stock_quantity, validate_inventory_warehouse)
        try:
            remark = (request.form.get('remark') or '').strip()
            # BUG-2026-08-02-013：仓库必填，未填写时自动带入默认仓库
            # P1-6：同时收 warehouse_id（ID 优先）与 warehouse 名称（旧客户端兜底）
            warehouse = (request.form.get('warehouse') or '').strip()
            raw_warehouse_id = request.form.get('warehouse_id')
            if not warehouse and not raw_warehouse_id:
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            if not warehouse and not raw_warehouse_id:
                return api_error('请选择仓库')
            # INV-AUDIT-005：仓库必须存在且 active
            wh_obj, wh_err = validate_inventory_warehouse(warehouse, raw_warehouse_id)
            if wh_err:
                return api_error(wh_err)
            warehouse = wh_obj.name
            # FEATURE-2026-09-05-001：可选盘点分类。选中后按分类（含子分类）
            # 为分类下全部物料预生成"未盘"明细行（actual=system、counted_at 空）：
            # 账面 0 也建行——账面 0 实物有货正是要盘出的盘盈；未盘行差异恒 0，
            # 完成盘点不生成调整，详情页可按"盘点人/时间"列核对漏盘。
            # FEATURE-2026-09-05-002：scope=all 整仓全盘——全部物料一键建行，
            # 行语义与按分类完全一致；scope 与 category_id 同时给出时 scope 优先。
            category = None
            materials = []
            scope_label = ''
            scope_all = (request.form.get('scope') or '').strip() == 'all'
            category_id = request.form.get('category_id', type=int) or 0
            if scope_all:
                scope_label = '整仓全部物料'
                materials = Material.query.order_by(Material.code.asc()).all()
            elif category_id:
                category = db.session.get(MaterialCategory, category_id)
                if category is None:
                    return api_error('所选分类不存在，请重新选择')
                scope_label = f'分类「{category.name}」（含子分类）'
                cat_ids = _expand_check_category_ids(category_id)
                materials = (Material.query
                             .filter(Material.category_id.in_(cat_ids))
                             .order_by(Material.code.asc())
                             .all())
            if scope_all or category is not None:
                max_rows = import_max_rows()
                if len(materials) > max_rows:
                    return api_error(
                        f'{scope_label}共 {len(materials)} 个物料，'
                        f'超过单次建单上限 {max_rows} 个，请按分类分批建单')
            check_no = generate_order_no('CK')
            check = InventoryCheck(
                check_no=check_no,
                remark=remark,
                warehouse=warehouse,
                status='pending',
                operator_id=current_user.id
            )
            db.session.add(check)
            db.session.flush()
            if materials:
                wh_stock_map = get_warehouse_stock_quantities(wh_obj)
                for m in materials:
                    book_qty = normalize_stock_quantity(wh_stock_map.get(m.id) or 0)
                    db.session.add(InventoryCheckItem(
                        inventory_check_id=check.id,
                        material_id=m.id,
                        system_stock=book_qty,
                        actual_stock=book_qty,
                        difference=0,
                    ))
                # 明细在建单时写入，账面同步冻结（与 save_check_table 首次写入语义一致）
                check.frozen_at = datetime.now()
            try:
                db.session.flush()
                replay_payload = {'status': 'success', 'id': check.id}
                if scope_all:
                    replay_payload['msg'] = (f'盘点单已创建，整仓全部物料生成 {len(materials)} 行待盘明细'
                                             if materials else '当前无任何物料，已创建空盘点单')
                elif category is not None:
                    replay_payload['msg'] = (f'盘点单已创建，按分类「{category.name}」（含子分类）生成 '
                                             f'{len(materials)} 行待盘明细' if materials else
                                             f'分类「{category.name}」下暂无物料，已创建空盘点单')
                stage_document_response(replay_payload)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500
            if scope_all or category is not None:
                log_operation('盘点单创建',
                              f'盘点单：{check.check_no}，{scope_label}生成 {len(materials)} 行待盘明细',
                              'check', check.id)
                if scope_all:
                    msg = (f'盘点单已创建，整仓全部物料生成 {len(materials)} 行待盘明细'
                           if materials else '当前无任何物料，已创建空盘点单')
                else:
                    msg = (f'盘点单已创建，按分类「{category.name}」（含子分类）生成 '
                           f'{len(materials)} 行待盘明细' if materials else
                           f'分类「{category.name}」下暂无物料，已创建空盘点单')
                return jsonify({'status': 'success', 'id': check.id, 'msg': msg})
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
        from app import (InventoryCheck, InventoryCheckItem,
                         _acquire_order_write_lock,
                         _create_adjustment_drafts_from_check, api_error, log_operation)
        # 完成前校验需要逐行读 material / counted_at，预加载消除 N+1
        check = InventoryCheck.query.options(
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material)
        ).get_or_404(id)
        if check.status != 'pending':
            return api_error('当前盘点单状态不可完结')

        if not check.items:
            return api_error('盘点单没有明细，无法完成')
        if not check.warehouse:
            return api_error('盘点单未指定仓库，无法完成')

        from request_input import CheckCompleteInput, json_object_body
        try:
            complete_input = CheckCompleteInput.model_validate(json_object_body())
            force = complete_input.force
            confirmation_token = complete_input.confirmation_token
        except (ValueError, TypeError):
            return api_error('完成参数格式不正确，请核对后重试')
        # 其他数据库的行锁不能阻止关联流水插入；未证明隔离前保守拒绝。
        if db.session.get_bind().dialect.name != 'sqlite':
            db.session.rollback()
            return api_error('当前数据库无法确保盘点风险检查的并发隔离，请联系管理员')
        reviewed_wh = _resolve_check_warehouse(check.warehouse)
        if reviewed_wh is None:
            return api_error('盘点仓库不存在或名称与编码存在歧义，请先核对仓库后再完成')
        reviewed_warehouse_id = reviewed_wh.id
        reviewed_warehouse = check.warehouse

        try:
            # 加写锁并重新读取状态，避免多 worker 并发重复生成调整草稿
            locked, ok = _acquire_order_write_lock(
                InventoryCheck, id, 'pending',
                selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material))
            if not ok:
                return api_error('该盘点单已提交，不能重复操作')
            # rollback 后单据可能仍在 identity map；强制刷新使关联加载选项生效。
            check = db.session.get(
                InventoryCheck, id, populate_existing=True,
                options=[selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material)])
            if check is None or check.status != 'pending':
                db.session.rollback()
                return api_error('该盘点单已提交，不能重复操作')
            if check.warehouse != reviewed_warehouse:
                db.session.rollback()
                return api_error('盘点仓库已发生变化，请重新核对后再完成')
            locked_wh = _resolve_check_warehouse(check.warehouse)
            if locked_wh is None or locked_wh.id != reviewed_warehouse_id:
                db.session.rollback()
                return api_error('盘点仓库归属已发生变化或存在歧义，请重新核对后再完成')
            from app import assert_warehouse_active
            warehouse_ok, warehouse_message = assert_warehouse_active(check.warehouse, allow_empty=False)
            if not warehouse_ok:
                db.session.rollback()
                return api_error(warehouse_message)
            if not check.items:
                db.session.rollback()
                return api_error('盘点单没有明细，无法完成')
            try:
                finite_actual = all(math.isfinite(float(item.actual_stock)) for item in check.items)
            except (ValueError, TypeError, OverflowError):
                finite_actual = False
            if not finite_actual:
                db.session.rollback()
                return api_error('盘点实盘数必须是有限数字，请先修正明细')
            if any(item.has_actual_count and float(item.actual_stock) < 0 for item in check.items):
                db.session.rollback()
                return api_error('实盘数量不能为负数，请先修正盘点明细')
            snapshot, risks = _check_complete_snapshot(check, locked_wh.id)
            if risks['uncounted']:
                db.session.rollback()
                return jsonify({
                    'status': 'error', 'code': 'check_uncounted',
                    'msg': f"共 {risks['total']} 行，其中 {risks['uncounted']} 行未盘。请补齐实盘数量后再完成盘点",
                    'samples': risks['uncounted_samples'],
                    'risks': {'uncounted': risks['uncounted'], 'total': risks['total']},
                }), 400
            user_id = current_user.get_id()
            confirmed = force and _accept_check_confirmation(
                confirmation_token, check.id, user_id, snapshot)
            if (risks['has_risk'] or confirmation_token is not None) and not confirmed:
                messages = []
                if risks['incomplete_count']:
                    messages.append(f"{risks['incomplete_count']} 行盘点人或盘点时间缺失，归属信息不完整")
                if risks['movement_count']:
                    messages.append(f"冻结期间本仓 {risks['movement_count']} 个物料发生出入库流水，净额为零也可能存在动销风险")
                if risks['unknown_warehouse_count']:
                    messages.append(f"{risks['unknown_warehouse_count']} 条相关流水仓库归属未知")
                if risks['unknown_time_count']:
                    messages.append(f"{risks['unknown_time_count']} 条相关流水时间缺失或异常")
                if risks['invalid_quantity_count']:
                    messages.append(f"{risks['invalid_quantity_count']} 处相关流水数量或合计无法准确表示")
                if risks['unknown_freeze']:
                    messages.append('盘点冻结时间未知，无法确定期间流水')
                if not messages:
                    messages.append('当前未发现未盘或流水风险')
                if force:
                    messages.append('确认凭据缺失、过期或状态已变化，请重新核对')
                response = {'status': 'confirm', 'code': 'check_risks',
                            'msg': '；'.join(messages) + '。请核对所有风险后确认继续。',
                            'samples': (risks['uncounted_samples'] + risks['movement_samples'])[:10],
                            'risks': {key: risks[key] for key in (
                                'uncounted', 'total', 'incomplete_count', 'movement_count',
                                'unknown_warehouse_count', 'unknown_time_count',
                                'invalid_quantity_count', 'unknown_freeze')},
                            'confirmation_token': _issue_check_confirmation(check.id, user_id, snapshot)}
                db.session.rollback()
                return jsonify(response)
            drafts, error = _create_adjustment_drafts_from_check(check)
            if error:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': error}), 400

            check.status = 'completed'
            _stage_inventory_check_audit(check, 'complete_check', 'pending', created=drafts)
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
        from app import (AdjustmentOrder, InventoryCheck,
                         _acquire_order_write_lock, api_error, log_operation)
        from services.stocktake import stocktake_adjustment_history
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

            # BUG-2026-08-16-020：删除死分支——全库无任何代码写入 check_in/check_out
            # 类型流水，原 316-351 行按 transaction_type.in_(('check_in','check_out'))
            # 查询并回退库存的分支永不执行。盘点库存变动真实路径是：盘点单生成
            # 未提交调整单草稿 → 人工完成调整单作用于库存。故反提交只需删除未提交的
            # 调整草稿即可恢复，删除该死代码避免误导后续维护者以为存在独立库存回退。
            drafts = [order for order in linked_adjustments if order.status == 'pending']
            check.status = 'pending'
            _stage_inventory_check_audit(check, 'revert_check', 'completed', removed=drafts)
            for order in drafts:
                if stocktake_adjustment_history(order.id):
                    order.status = 'cancelled'
                else:
                    for item in list(order.items):
                        db.session.delete(item)
                    db.session.delete(order)
            db.session.commit()
            log_operation('反提交盘点', f'盘点单：{check.check_no}', 'check', id)
            return jsonify({'status': 'success', 'msg': '反提交成功，已撤回关联调整草稿，过账历史已保留'})
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
        from datetime import datetime
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         _acquire_order_write_lock, api_error, get_default_warehouse,
                         get_warehouse_stock_quantities, location_management_enabled,
                         log_operation, validate_inventory_warehouse)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以添加明细')
        try:
            material_id = int(request.form.get('material_id', ''))
        except (ValueError, TypeError):
            return api_error('请选择有效物料')
        area = (request.form.get('area') or request.form.get('location') or '').strip()
        try:
            check, locked = _acquire_order_write_lock(InventoryCheck, id, 'pending')
            if not locked or check is None:
                db.session.rollback()
                return api_error('盘点单状态已变更，请刷新后重试')
            material = db.session.get(Material, material_id)
            if not material:
                db.session.rollback()
                return api_error('物料不存在')
            warehouse = (check.warehouse or '').strip()
            if not warehouse:
                if check.items or check.frozen_at is not None:
                    db.session.rollback()
                    return api_error('历史盘点单已有冻结明细但缺少仓库，请人工核实归属后处理')
                default_wh = get_default_warehouse()
                if default_wh:
                    warehouse = default_wh.name
            wh_obj, wh_err = validate_inventory_warehouse(warehouse)
            if wh_err:
                db.session.rollback()
                return api_error(wh_err)
            if location_management_enabled() and not area:
                db.session.rollback()
                return api_error('库位管理已启用，请填写库位/区域')
            existing_item = InventoryCheckItem.query.filter(
                InventoryCheckItem.inventory_check_id == id,
                InventoryCheckItem.material_id == material_id,
                db.func.coalesce(InventoryCheckItem.area, '') == area,
            ).order_by(InventoryCheckItem.id).first()
            if area and existing_item:
                db.session.rollback()
                return api_error('该物料在此区域已存在，请修改现有明细')
            system_stock = get_warehouse_stock_quantities(wh_obj).get(material_id, 0) or 0
            if not area and existing_item:
                system_stock = existing_item.system_stock
            check.warehouse = wh_obj.name
            if check.frozen_at is None:
                check.frozen_at = datetime.now()
            db.session.add(InventoryCheckItem(
                inventory_check_id=id, material_id=material_id, area=area,
                system_stock=system_stock, actual_stock=system_stock, difference=0,
            ))
            db.session.commit()
            log_operation('添加盘点明细', f'盘点单：{check.check_no}，物料：{material.code}', 'check', id)
            return jsonify({'status': 'success', 'msg': '盘点明细添加成功'})
        except Exception:
            db.session.rollback()
            app.logger.warning('盘点明细添加失败：check_id=%s', id)
            return api_error('添加失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/item/<int:item_id>', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_check_item(id, item_id):
        """更新盘点明细的实际库存"""
        from datetime import datetime
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, InventoryCheckScanItem,
                         _acquire_order_write_lock, api_error, log_operation)
        check = InventoryCheck.query.get_or_404(id)
        if check.status != 'pending':
            return api_error('只有草稿状态的盘点单可以修改明细')

        item = InventoryCheckItem.query.get_or_404(item_id)
        if item.inventory_check_id != id:
            return api_error('盘点明细不属于当前盘点单')

        try:
            raw_actual = request.form.get('actual_stock')
            if raw_actual is None:
                return jsonify({'status': 'success', 'msg': '实盘数量未修改'})
            actual_stock = float(raw_actual) if raw_actual.strip() else None
        except (ValueError, TypeError):
            return api_error('实际库存必须是数字')
        if actual_stock is not None and (not math.isfinite(actual_stock) or actual_stock < 0):
            return api_error('实际库存必须是有限数字且不能为负数')

        try:
            # INV-BATCH-001-B：单据写锁，防多人并发改行互相覆盖/改到已提交单
            locked, ok = _acquire_order_write_lock(InventoryCheck, id, 'pending')
            if not ok:
                return api_error('该盘点单状态已变更，请刷新后重试')
            InventoryCheckScanItem.query.filter_by(batch_item_id=item.id).update({'batch_item_id': None})
            item.actual_stock = actual_stock if actual_stock is not None else item.system_stock
            item.difference = item.actual_stock - item.system_stock
            # INV-BATCH-001-B：行级盘点归属（多人协作批次下谁改的、何时改的）
            item.counted_by = current_user.id if actual_stock is not None else None
            item.counted_at = datetime.now() if actual_stock is not None else None
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
    @web_document_command_idempotent
    def copy_check(id):
        from datetime import datetime
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem, api_error,
                         generate_order_no, get_warehouse_stock_quantities,
                         log_operation, validate_inventory_warehouse)
        check = InventoryCheck.query.get_or_404(id)
        warehouse = (check.warehouse or '').strip()
        if not warehouse:
            return api_error('原盘点单未指定仓库，无法复制')
        warehouse_obj, warehouse_error = validate_inventory_warehouse(warehouse)
        if warehouse_error:
            return api_error(warehouse_error)
        try:
            check_no = generate_order_no('CK')
            new_check = InventoryCheck(
                check_no=check_no,
                remark=check.remark,
                status='pending',
                warehouse=warehouse_obj.name,
                operator_id=current_user.id
            )
            db.session.add(new_check)
            db.session.flush()
            stock_map = get_warehouse_stock_quantities(warehouse_obj)
            for item in check.items:
                system_stock = stock_map.get(item.material_id, 0) or 0
                new_item = InventoryCheckItem(
                    inventory_check_id=new_check.id,
                    material_id=item.material_id,
                    system_stock=system_stock,
                    actual_stock=system_stock,
                    difference=0,
                    reason='',
                    area=item.area or '',
                )
                db.session.add(new_item)
            if check.items:
                new_check.frozen_at = datetime.now()
            response_payload = {'status': 'success', 'msg': '复制成功'}
            stage_document_response(response_payload)
            db.session.commit()
            log_operation('复制盘点单', f'从 {check.check_no} 复制为 {new_check.check_no}', 'check', new_check.id)
            return jsonify(response_payload)
        except Exception as e:
            db.session.rollback()
            return api_error('复制失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/check/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_check(id):
        """删除盘点单"""
        from app import (AdjustmentOrder, InventoryCheck, InventoryCheckItem,
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
            if AdjustmentOrder.query.filter_by(source_type='check', source_id=check.id).first():
                db.session.rollback()
                return api_error('存在关联调整记录，须保留来源盘点单')
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
        from app import (AdjustmentOrder, InventoryCheck, InventoryCheckItem,
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
                    if AdjustmentOrder.query.filter_by(source_type='check', source_id=check.id).first():
                        skipped.append(f'{check_no}(存在关联调整记录)')
                        db.session.rollback()
                        continue
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
                         _status_from_search_keyword, _warehouse_document_match_clause,
                         _workbook_response,
                         resolve_request_warehouse)
        rows = []
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'completed'))
        allowed_sorts = {'check_no', 'date', 'status', 'created_at'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'
        query = InventoryCheck.query.options(
            selectinload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit)
        )
        query = _apply_status_date_filters(query, InventoryCheck, status_filter, date_start, date_end)
        warehouse, warehouse_error = resolve_request_warehouse(request.args)
        if warehouse_error:
            from app import api_error
            return api_error(warehouse_error, 400)
        query = query.filter(
            _warehouse_document_match_clause(InventoryCheck.warehouse, warehouse))
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
        from services.stocktake import stocktake_display_values
        for check in checks:
            values = stocktake_display_values(check.items)
            if check.items:
                for item in check.items:
                    material = item.material
                    rows.append([
                        check.check_no,
                        check.date.strftime('%Y-%m-%d') if check.date else '',
                        check.warehouse or '',
                        material.code if material else '',
                        material.name if material else '',
                        material.spec if material else '',
                        material.unit.name if material and material.unit else '',
                        values[item.id]['system_stock'],
                        values[item.id]['actual_stock'],
                        values[item.id]['difference'],
                        item.reason or '',
                        '草稿' if check.status == 'pending' else ('已完成' if check.status == 'completed' else (check.status or '')),
                        check.remark or '',
                        item.area or '', values[item.id]['count_total'],
                    ])
            else:
                rows.append([check.check_no, check.date.strftime('%Y-%m-%d') if check.date else '', check.warehouse or '', '', '', '', '', 0, None, None, '', '草稿' if check.status == 'pending' else ('已完成' if check.status == 'completed' else (check.status or '')), check.remark or '', '', None])
        return _workbook_response(
            'inventory_checks.xlsx',
            '库存盘点',
            ['单据编号', '日期', '仓库', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异数量', '差异原因', '状态', '备注', '区域', '物料实盘合计'],
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
                         api_error, get_default_warehouse,
                         get_warehouse_stock_quantities, normalize_stock_quantity,
                         location_management_enabled, parse_float_value, round_to_2_decimals, validate_excel_extension,
                         validate_excel_size, validate_inventory_warehouse)
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
            # BUG-2026-09-03-001：导入支持"仓库"列（仓库名或编码），缺省带入默认仓库
            'warehouse': ['仓库', '仓库名称', '仓库编码'],
            'material_code': ['物料编码', '材料编码'],
            'material_name': ['物料名称', '材料名称'],
            'spec': ['规格'],
            'unit': ['单位'],
            'system_stock': ['系统库存', '账面库存'],
            'actual_stock': ['实际库存', '盘点库存'],
            'area': ['区域', '库位', '盘点区域'],
            'reason': ['差异原因', '原因'],
            'remark': ['备注'],
        }
        try:
            ws, col_map, header_row = _read_import_sheet(file, aliases)
            required = {'material_code', 'actual_stock'}
            if not required.issubset(col_map):
                return api_error(f'Excel表头缺少必要列（物料编码、实际库存）。检测到的表头：{", ".join(header_row)}')
            checks_by_no = {}
            # BUG-2026-09-03-001：每个导入盘点单缓存其仓库级账面映射，避免逐行重算流水聚合
            checks_wh_stock = {}
            order_count = 0
            item_count = 0
            skip = 0
            skip_details = []
            warnings = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                material_code = _get_excel_cell(row, col_map, 'material_code')
                if not material_code:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料编码为空')
                    continue
                from request_input import StockDocumentItemInput
                try:
                    StockDocumentItemInput.model_validate({'actual_stock': _get_excel_cell(row, col_map, 'actual_stock')})
                except (ValueError, TypeError):
                    skip += 1
                    skip_details.append(f'第{row_idx}行：实际库存必须是有限数字且不能为负数')
                    continue
                # BUG-2026-09-03-001：行仓库解析（Excel 未提供该列时为空，交由默认仓库回退）
                row_warehouse_raw = (_get_excel_cell(row, col_map, 'warehouse') or '').strip()
                row_warehouse_name = None
                if row_warehouse_raw:
                    wh_obj, wh_err = validate_inventory_warehouse(row_warehouse_raw)
                    if wh_err:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：仓库无效「{row_warehouse_raw}」({wh_err})，跳过')
                        continue
                    row_warehouse_name = wh_obj.name
                area = (_get_excel_cell(row, col_map, 'area') or '').strip()
                if location_management_enabled() and not area:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：库位管理已启用，请填写库位/区域')
                    continue
                order_no = _order_no_from_row(row, col_map, 'order_no', 'CK')
                check = checks_by_no.get(order_no)
                if not check:
                    if InventoryCheck.query.filter_by(check_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：盘点单号 {order_no} 已存在')
                        continue
                    # 单据仓库：Excel 行值优先，缺省带入默认仓库
                    warehouse = row_warehouse_name or (get_default_warehouse().name if get_default_warehouse() else '')
                    if not warehouse:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：盘点单 {order_no} 未指定仓库且系统无默认仓库，跳过')
                        continue
                    check = InventoryCheck(
                        check_no=order_no,
                        date=_parse_excel_date(_get_excel_cell(row, col_map, 'date')),
                        remark=_get_excel_cell(row, col_map, 'remark'),
                        warehouse=warehouse,
                        status='pending',
                        operator_id=current_user.id,
                    )
                    db.session.add(check)
                    db.session.flush()
                    checks_by_no[order_no] = check
                    order_count += 1
                    _wh_obj, _wh_err = validate_inventory_warehouse(warehouse)
                    check.frozen_at = datetime.now()
                    checks_wh_stock[order_no] = get_warehouse_stock_quantities(_wh_obj) if _wh_obj else {}
                elif row_warehouse_name and row_warehouse_name != check.warehouse:
                    # 同一盘点单内多行必须归属同一仓库，避免一单多仓串账
                    skip += 1
                    skip_details.append(f'第{row_idx}行：仓库「{row_warehouse_name}」与盘点单 {order_no} 不一致（{check.warehouse}），跳过')
                    continue
                material = _find_or_create_material(
                    material_code,
                    _get_excel_cell(row, col_map, 'material_name'),
                    _get_excel_cell(row, col_map, 'spec'),
                    _get_excel_cell(row, col_map, 'unit'),
                    warnings=warnings,
                )
                system_stock = normalize_stock_quantity(checks_wh_stock[order_no].get(material.id, 0))
                actual_stock = _get_excel_number(row, col_map, 'actual_stock', system_stock)
                if area and InventoryCheckItem.query.filter_by(
                    inventory_check_id=check.id, material_id=material.id, area=area
                ).first():
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料 {material.code} 与区域 {area or "未分区"} 重复')
                    continue
                file_stock = _get_excel_cell(row, col_map, 'system_stock')
                if file_stock and parse_float_value(file_stock, None) != system_stock:
                    warnings.append(
                        f'第{row_idx}行：{check.warehouse}的物料 {material.code} '
                        f'使用仓库账面 {system_stock:.2f}（Excel 填写 {file_stock[:40]}）'
                    )
                entered_actual = bool(_get_excel_cell(row, col_map, 'actual_stock'))
                db.session.add(InventoryCheckItem(
                    inventory_check_id=check.id,
                    material_id=material.id,
                    area=area,
                    system_stock=system_stock,
                    actual_stock=actual_stock,
                    difference=round_to_2_decimals(actual_stock - system_stock),
                    counted_by=current_user.id if entered_actual else None,
                    counted_at=datetime.now() if entered_actual else None,
                    reason=_get_excel_cell(row, col_map, 'reason'),
                ))
                item_count += 1
            if not item_count:
                db.session.rollback()
                message = f'没有有效盘点明细，跳过 {skip} 行。' + '；'.join(skip_details[:10])
                return _import_result('库存盘点单', 0, 0, skip, skip_details,
                                      extra={'status': 'error', 'msg': message}), 400
            db.session.commit()
            return _import_result('库存盘点单', order_count, item_count, skip, skip_details, notes=warnings)
        except InactiveMaterialImportError as exc:
            db.session.rollback()
            return api_error(str(exc))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'库存盘点导入失败: {e}')
            return api_error(f'库存盘点导入失败，请稍后重试或联系管理员')

    @app.route('/check/<int:id>/export')
    @login_required
    def export_single_check(id):
        from services.stocktake import stocktake_display_values
        import io
        from openpyxl import Workbook
        from app import InventoryCheck
        check = InventoryCheck.query.get_or_404(id)
        wb = Workbook()
        ws = wb.active
        ws.title = '盘点单'
        # BUG-2026-09-05-006：补「盘点人/盘点时间」两列——页面早有行级盘点归属
        # 回查（INV-BATCH-001-D），导出却没有，Excel 里无法筛漏盘行；末列表头
        # 由「备注」正名为「差异原因」（写入的一直是 item.reason，且与导入别名对齐）。
        ws.append(['单据编号', '日期', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异数量', '差异原因', '盘点人', '盘点时间', '仓库', '区域', '物料实盘合计'])
        values = stocktake_display_values(check.items)
        if check.items:
            for item in check.items:
                ws.append([
                    check.check_no,
                    check.date.strftime('%Y-%m-%d') if check.date else '',
                    item.material.code if item.material else '',
                    item.material.name if item.material else '',
                    item.material.spec if item.material else '',
                    item.material.unit.name if item.material and item.material.unit else '',
                    values[item.id]['system_stock'],
                    values[item.id]['actual_stock'],
                    values[item.id]['difference'],
                    item.reason or '',
                    item.counted_by_user.username if getattr(item, 'counted_by_user', None) else '',
                    item.counted_at.strftime('%Y-%m-%d %H:%M') if getattr(item, 'counted_at', None) else '',
                    check.warehouse or '',
                    item.area or '', values[item.id]['count_total'],
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name=f'check_{check.check_no}.xlsx', as_attachment=True)

    @app.route('/check/<int:id>/print')
    @login_required
    def print_single_check(id):
        from services.stocktake import stocktake_display_values
        from sqlalchemy.orm import joinedload
        from app import InventoryCheck, InventoryCheckItem, Material
        check = InventoryCheck.query.options(
            joinedload(InventoryCheck.items).joinedload(InventoryCheckItem.material).joinedload(Material.unit),
            joinedload(InventoryCheck.operator)
        ).get_or_404(id)
        return render_template('check_print.html', check=check, values=stocktake_display_values(check.items))
