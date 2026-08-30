#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 库存查询（stock_query）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_<domain>_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 stock_query、api_query_search），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db），不导入 app，避免循环导入。
# - app.py 内部定义（Material 模型、api_error、get_default_warehouse 等）在各路由
#   函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志统一使用 current_app.logger 替代 app.logger。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import jsonify, render_template, request
from flask_login import login_required

from db import db


# no-test:reason=路由注册辅助函数，能力由 stock_query_* 各路由测试覆盖
def register_stock_query_routes(app):
    # BUG-2026-07-29-006: 打印/导出路由 404 显式化
    # 历史审计中发现 /material/print_label、/stock_query/print、/report/print 等 URL 直接访问返回 404，
    # 但经全量 grep 后确认：app/templates/ 中没有任何 href/url_for 引用上述 URL。
    # 显式注册为 404 + 提示，避免误判为程序 bug，同时防止未来重新引入。
    @app.route('/stock_query/print')
    @login_required
    def stock_query_print_not_implemented():
        from app import api_error
        return api_error('库存查询打印功能未实现', code=404)

    @app.route('/stock_query')
    @login_required
    def stock_query():
        """库存查询"""
        from sqlalchemy.orm import joinedload
        from app import (
            Material,
            Supplier,
            MaterialCategory,
            Unit,
            Warehouse,
            LocationInventory,
            get_default_warehouse,
            get_active_warehouses,
            get_warehouse_stock_quantities,
            inventory_alert_enabled,
            location_management_enabled,
        )
        search = (request.args.get('search') or '').strip()
        category_id = request.args.get('category_id', type=int)
        stock_filter = (request.args.get('stock_filter') or '').strip()
        sort_by = request.args.get('sort', 'code')
        sort_order = request.args.get('order', 'asc')
        # BUG-2026-08-02-018：库存查询仓库必填（AGENTS.md 规则），未指定时带入默认仓库
        warehouse_id = request.args.get('warehouse_id', type=int)
        if not warehouse_id:
            default_wh = get_default_warehouse()
            if default_wh:
                warehouse_id = default_wh.id
        allowed_sorts = {'code', 'name', 'spec', 'stock', 'min_stock', 'price', 'created_at', 'category_id', 'supplier_id'}
        if sort_by not in allowed_sorts:
            sort_by = 'code'
        if sort_order not in ('asc', 'desc'):
            sort_order = 'asc'
        if stock_filter not in ('low', 'normal'):
            stock_filter = ''
        if not inventory_alert_enabled() and stock_filter in {'low', 'normal'}:
            stock_filter = ''
        # AI-WMS-FILTER-003：库存查询分页（默认每页 50 条，per_page 走白名单防滥用）
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        if not page or page < 1:
            page = 1
        if per_page not in (20, 50, 100, 200):
            per_page = 50

        materials = []
        location_map = {}
        warehouse_stock_map = {}
        pagination = None
        # BUG-2026-08-16-007：库存按仓库级口径展示，不再用全局 material.stock，
        # 与 api_query_search 的 get_warehouse_stock_quantities 口径保持一致。
        warehouse = Warehouse.query.get(warehouse_id) if warehouse_id else None
        if warehouse:
            warehouse_stock_map = get_warehouse_stock_quantities(warehouse)
        # AGENTS.md：不指定仓库时不得返回数据
        if warehouse_id:
            def _base_query(with_options):
                q = Material.query
                if with_options:
                    q = q.options(joinedload(Material.unit), joinedload(Material.category), joinedload(Material.supplier))
                if search:
                    search_like = f'%{search}%'
                    q = q.filter(
                        db.or_(
                            Material.code.like(search_like),
                            Material.name.like(search_like),
                            Material.spec.like(search_like),
                            Material.purpose.like(search_like),
                            Supplier.name.like(search_like),
                            MaterialCategory.name.like(search_like),
                            Unit.name.like(search_like)
                        )
                    ).outerjoin(Supplier, Material.supplier_id == Supplier.id).outerjoin(
                        MaterialCategory, Material.category_id == MaterialCategory.id
                    ).outerjoin(Unit, Material.unit_id == Unit.id)
                if category_id:
                    q = q.filter(Material.category_id == category_id)
                return q

            query = _base_query(True)
            # AI-WMS-FILTER-003：stock_filter(low/normal) 依赖仓库级库存口径，
            # 而 get_warehouse_stock_quantities 在单仓场景还会回退全局 Material.stock，
            # 无法翻译成等价 SQL 谓词。因此先按同一口径算出命中 id 集合，再交给 SQL
            # 分页——保证总条数与页数准确，不会出现「过滤后仍按全量分页」的错。
            if stock_filter:
                candidates = _base_query(False).with_entities(Material.id, Material.min_stock).all()
                if stock_filter == 'low':
                    matched = [mid for mid, ms in candidates
                               if (ms or 0) > 0 and (warehouse_stock_map.get(mid) or 0) <= (ms or 0)]
                else:
                    matched = [mid for mid, ms in candidates
                               if (ms or 0) <= 0 or (warehouse_stock_map.get(mid) or 0) > (ms or 0)]
                hit = set(matched)
                miss = [mid for mid, _ in candidates if mid not in hit]
                # 命中集与补集取较小的一侧，避免超长 IN 列表撞上 SQLite 变量上限
                if len(matched) <= len(miss):
                    query = query.filter(Material.id.in_(matched))
                else:
                    query = query.filter(Material.id.notin_(miss))
            sort_col = getattr(Material, sort_by, Material.code)
            query = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc())
            pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
            materials = pagination.items
            # 开启库位管理时，库位行只取当前所选仓库的（BUG-2026-08-16-007），
            # 不再把全仓库库位混入展示；兼容历史 warehouse_id IS NULL 且
            # location == 仓库名的旧行。
            if location_management_enabled() and materials and warehouse:
                material_ids = [material.id for material in materials]
                filters_expr = [LocationInventory.material_id.in_(material_ids)]
                name_clauses = [
                    LocationInventory.warehouse_id == warehouse.id,
                    db.and_(
                        LocationInventory.warehouse_id.is_(None),
                        db.or_(
                            LocationInventory.location == (warehouse.name or '').strip(),
                            LocationInventory.location == (warehouse.code or '').strip(),
                        ),
                    ),
                ]
                filters_expr.append(db.or_(*name_clauses))
                rows = LocationInventory.query.filter(*filters_expr).order_by(
                    LocationInventory.location.asc()
                ).all()
                for row in rows:
                    if not row.quantity:
                        continue
                    location_map.setdefault(row.material_id, []).append(row)
        categories = MaterialCategory.query.order_by(MaterialCategory.code.asc(), MaterialCategory.name.asc()).all()
        filters = {'search': search, 'category_id': category_id or '', 'stock_filter': stock_filter, 'warehouse_id': warehouse_id or '', 'per_page': per_page}
        return render_template('stock_query.html', materials=materials, categories=categories, filters=filters, sort_by=sort_by, sort_order=sort_order, location_map=location_map, warehouse_stock_map=warehouse_stock_map, warehouses=get_active_warehouses(), default_warehouse=get_default_warehouse(),
                                   pagination=pagination, page=page, per_page=per_page)

    @app.route('/api/query/search', methods=['POST'])
    @login_required
    def api_query_search():
        """模糊查询物料"""
        from app import (Material, Supplier, MaterialCategory, Unit,
                         api_error, get_warehouse_stock_quantities,
                         normalize_stock_quantity, resolve_request_warehouse)
        keyword = request.form.get('keyword', '').strip()
        if not keyword:
            return api_error('请输入搜索关键词')

        # INV-AUDIT-004：仓库必填（AGENTS.md 规则），未提供时回退默认仓库；
        # 无默认仓库则拒绝查询，避免返回全局 Material.stock。
        warehouse, wh_error = resolve_request_warehouse(request.form)
        if wh_error:
            return api_error(wh_error, 400)

        keyword_like = f'%{keyword}%'
        materials = Material.query.outerjoin(Supplier, Material.supplier_id == Supplier.id).outerjoin(
            MaterialCategory, Material.category_id == MaterialCategory.id
        ).outerjoin(Unit, Material.unit_id == Unit.id).filter(
            db.or_(
                Material.code.like(keyword_like),
                Material.name.like(keyword_like),
                Material.spec.like(keyword_like),
                Material.purpose.like(keyword_like),
                Supplier.name.like(keyword_like),
                MaterialCategory.name.like(keyword_like),
                Unit.name.like(keyword_like)
            )
        ).order_by(Material.code.asc()).all()

        # INV-AUDIT-004：库存按仓库级返回，不再回退全局 Material.stock
        warehouse_stock_map = get_warehouse_stock_quantities(warehouse)

        data = []
        for m in materials:
            data.append({
                'id': m.id,
                'code': m.code,
                'name': m.name,
                'spec': m.spec or '',
                'stock': normalize_stock_quantity(warehouse_stock_map.get(m.id) or 0),
                'unit': m.unit.name if m.unit else '',
                'supplier': m.supplier.name if m.supplier else ''
            })

        return jsonify({'status': 'success', 'data': data})
