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
    """统计盘点单的未盘明细行（BUG-2026-09-06-001）。

    未盘判定：行级归属 ``counted_at`` 或 ``counted_by`` 至少其一为空。分
    类建单（FEATURE-2026-09-05-001）预生成的待盘行 actual_stock = system_stock
    、difference = 0，与"盘了没有差异"在系统里完全同形，完成盘点时既不生
    成调整也不提示——一单 500 行只盘 50 行同样能直接完成，事后无法与真实
    无差异区分。

    已盘信号源是 INV-BATCH-001-A 引入的行级归属字段：手机扫码盘点与
    /check/<id>/item/<item_id> 路由都会写 ``counted_by`` + ``counted_at``。
    PC 表格纯录入不写这两个字段，本判定会把它视为未盘——这正是漏盘拦截的
    预期行为：纯 PC 盘点单弹出确认后用户主动 force=1 放行（账面 0 无实物
    等合法未盘场景仍可完成），分类建单 + 手机补盘的混合模式则自然漏出。

    返回 (未盘行数, 有效行数, 前 10 条样例[{code, name}])。
    """
    rows = [it for it in (check.items or []) if it.material_id]
    uncounted = [it for it in rows
                 if not (getattr(it, 'counted_at', None)
                         or getattr(it, 'counted_by', None))]
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


# no-test:reason=路由注册辅助函数，能力由 check_* 各路由测试覆盖
def register_check_routes(app):
    @app.route('/check')
    @login_required
    def check_list():
        from sqlalchemy.orm import joinedload, selectinload
        from app import (InventoryCheck, InventoryCheckItem, Material,
                         _apply_status_date_filters, _get_order_list_filters,
                         _status_from_search_keyword, get_active_warehouses,
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
            query = query.filter(InventoryCheck.warehouse == warehouse.name)
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
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
            'warehouse_id': warehouse.id if warehouse else '',
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
    def save_check_table():
        from datetime import date, datetime
        from flask_login import current_user
        from sqlalchemy.orm import selectinload
        from app import (InventoryCheck, InventoryCheckItem,
                         _acquire_order_write_lock, _clean_int,
                         _material_from_payload, _parse_form_date, api_error,
                         generate_order_no, get_default_warehouse,
                         get_warehouse_stock_quantities, log_operation,
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
        # W1：盘点「系统库存」按仓库级口径取数（与库存查询/库存报表一致），
        # 此前取全局 material.stock，多仓库下 A+B 合计会把盘盈盘亏算错。
        warehouse_stock_map = get_warehouse_stock_quantities(wh_obj)

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
                # INV-BATCH-001-B：单据写锁，防多人并发保存同一盘点单互相覆盖
                locked, ok = _acquire_order_write_lock(
                    InventoryCheck, order_id, 'pending', selectinload(InventoryCheck.items))
                if not ok:
                    return api_error('该盘点单状态已变更，请刷新后重试')
                check = locked
            else:
                check = InventoryCheck.query.filter_by(check_no=check_no).first()
                if check:
                    if check.status != 'pending':
                        return api_error('盘点单号已存在')
                    locked, ok = _acquire_order_write_lock(
                        InventoryCheck, check.id, 'pending', selectinload(InventoryCheck.items))
                    if not ok:
                        return api_error('该盘点单状态已变更，请刷新后重试')
                    check = locked
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
            existing_items = {item.material_id: item for item in check.items}
            submitted_material_ids = set()
            for item_data in items_data:
                material = _material_from_payload(item_data)
                if not material:
                    return api_error(f'物料不存在：{item_data.get("code") or ""}')
                submitted_material_ids.add(material.id)
                raw_actual = item_data.get('actual_stock')
                has_actual = raw_actual is not None and str(raw_actual).strip() != ''
                row = existing_items.get(material.id)
                if row is not None:
                    # 已有行：冻结账面保留，只更新实盘/原因/差异
                    if has_actual:
                        row.actual_stock = round_to_2_decimals(parse_float_value(raw_actual, row.actual_stock))
                    row.difference = round_to_2_decimals(row.actual_stock - row.system_stock)
                    row.reason = (item_data.get('reason') or item_data.get('remark') or '').strip()
                else:
                    # 新增行：账面取当前仓库级（该行首次录入时点）
                    system_stock = round_to_2_decimals(parse_float_value(
                        item_data.get('system_stock'), warehouse_stock_map.get(material.id, 0) or 0))
                    actual_stock = round_to_2_decimals(parse_float_value(raw_actual, system_stock)) if has_actual else system_stock
                    db.session.add(InventoryCheckItem(
                        inventory_check_id=check.id,
                        material_id=material.id,
                        system_stock=system_stock,
                        actual_stock=actual_stock,
                        difference=round_to_2_decimals(actual_stock - system_stock),
                        reason=(item_data.get('reason') or item_data.get('remark') or '').strip()
                    ))
            # 删除提交集之外的旧行
            for material_id, row in existing_items.items():
                if material_id not in submitted_material_ids:
                    db.session.delete(row)
            # 首次写入明细即冻结账面基准
            if check.frozen_at is None:
                check.frozen_at = datetime.now()

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
            # FEATURE-2026-09-05-001：可选盘点分类。选中后按分类（含子分类）
            # 为分类下全部物料预生成"未盘"明细行（actual=system、counted_at 空）：
            # 账面 0 也建行——账面 0 实物有货正是要盘出的盘盈；未盘行差异恒 0，
            # 完成盘点不生成调整，详情页可按"盘点人/时间"列核对漏盘。
            category = None
            materials = []
            category_id = request.form.get('category_id', type=int) or 0
            if category_id:
                category = db.session.get(MaterialCategory, category_id)
                if category is None:
                    return api_error('所选分类不存在，请重新选择')
                cat_ids = _expand_check_category_ids(category_id)
                materials = (Material.query
                             .filter(Material.category_id.in_(cat_ids))
                             .order_by(Material.code.asc())
                             .all())
                max_rows = import_max_rows()
                if len(materials) > max_rows:
                    return api_error(
                        f'分类「{category.name}」（含子分类）共 {len(materials)} 个物料，'
                        f'超过单次建单上限 {max_rows} 个，请改用更细的分类或分批建单')
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
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败，请稍后重试'}), 500
            if category is not None:
                log_operation('盘点单创建',
                              f'盘点单：{check.check_no}，按分类「{category.name}」生成 {len(materials)} 行待盘明细',
                              'check', check.id)
                return jsonify({
                    'status': 'success', 'id': check.id,
                    'msg': (f'盘点单已创建，按分类「{category.name}」（含子分类）生成 '
                            f'{len(materials)} 行待盘明细' if materials else
                            f'分类「{category.name}」下暂无物料，已创建空盘点单'),
                })
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

        # BUG-2026-09-06-001：完成前二次确认（漏盘）。未盘行差异恒 0、不生成
        # 调整，系统此前对"没盘"与"盘了无差异"不加区分。此处软拦截——返回
        # status='confirm' 由前端弹窗列出未盘明细，用户确认后带 force=1 放行，
        # 不硬阻断（账面 0 无实物等合法未盘场景仍须可完成）。
        # 旧客户端不带 body 调用时 get_json(silent=True) 返回 None，force=False。
        payload = request.get_json(silent=True) or {}
        force = str(payload.get('force') or '').strip().lower() in ('1', 'true', 'yes')
        if not force:
            uncounted, total_rows, samples = _check_uncounted_alerts(check)
            if uncounted:
                preview = '、'.join(
                    (s['code'] or '?') for s in samples[:5])
                more_tip = '等' if uncounted > len(samples) else ''
                return jsonify({
                    'status': 'confirm',
                    'code': 'uncounted',
                    'msg': (f'本单共 {total_rows} 行明细，其中 {uncounted} 行尚未盘点'
                            f'（无盘点人/时间记录）：{preview}{more_tip}。'
                            '未盘行不会产生库存差异，请确认是否已全部盘完。'),
                    'count': uncounted,
                    'total': total_rows,
                    'samples': samples,
                })

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
        from app import (AdjustmentOrder, InventoryCheck,
                         _acquire_order_write_lock, api_error, log_operation)
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
            for order in linked_adjustments:
                if order.status == 'pending':
                    for item in list(order.items):
                        db.session.delete(item)
                    db.session.delete(order)
            check.status = 'pending'
            db.session.commit()
            log_operation('反提交盘点', f'盘点单：{check.check_no}', 'check', id)
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
        from app import (InventoryCheck, InventoryCheckItem, Material, Warehouse,
                         api_error, get_warehouse_stock_quantities, log_operation)
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
            # 创建盘点明细，系统库存为该仓库级当前库存，实际库存默认为系统库存
            # W1：仓库级口径（与 save_check_table 一致），仓库解析失败时回退全局库存
            wh_obj = None
            if check.warehouse:
                wh_obj = Warehouse.query.filter(db.or_(
                    Warehouse.name == check.warehouse,
                    Warehouse.code == check.warehouse,
                )).first()
            if wh_obj:
                system_stock = get_warehouse_stock_quantities(wh_obj).get(material_id, 0) or 0
            else:
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
        from datetime import datetime
        from flask_login import current_user
        from app import (InventoryCheck, InventoryCheckItem,
                         _acquire_order_write_lock, api_error, log_operation)
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
            # INV-BATCH-001-B：单据写锁，防多人并发改行互相覆盖/改到已提交单
            locked, ok = _acquire_order_write_lock(InventoryCheck, id, 'pending')
            if not ok:
                return api_error('该盘点单状态已变更，请刷新后重试')
            item.actual_stock = actual_stock
            item.difference = actual_stock - item.system_stock
            # INV-BATCH-001-B：行级盘点归属（多人协作批次下谁改的、何时改的）
            item.counted_by = current_user.id
            item.counted_at = datetime.now()
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
                         _status_from_search_keyword, _workbook_response,
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
        query = query.filter(InventoryCheck.warehouse == warehouse.name)
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
                        check.warehouse or '',
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
                rows.append([check.check_no, check.date.strftime('%Y-%m-%d') if check.date else '', check.warehouse or '', '', '', '', '', 0, 0, 0, '', '草稿' if check.status == 'pending' else ('已完成' if check.status == 'completed' else (check.status or '')), check.remark or ''])
        return _workbook_response(
            'inventory_checks.xlsx',
            '库存盘点',
            ['单据编号', '日期', '仓库', '物料编码', '物料名称', '规格', '单位', '系统库存', '实际库存', '差异数量', '差异原因', '状态', '备注'],
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
                         round_to_2_decimals, validate_excel_extension,
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
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                material_code = _get_excel_cell(row, col_map, 'material_code')
                if not material_code:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：物料编码为空')
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
                )
                # BUG-2026-09-03-001：账面缺省取该单据仓库的仓库级库存（此前用全局
                # Material.stock，多仓库下会算错差异）；Excel 显式填写账面时以文件为准。
                book_stock = normalize_stock_quantity((checks_wh_stock.get(order_no) or {}).get(material.id) or 0)
                system_stock = _get_excel_number(row, col_map, 'system_stock', book_stock)
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
