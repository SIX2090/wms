# 期初库存（opening_stock）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（_opening_stock_payload_from_request / _apply_opening_stock_balance 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 opening_stock_* 各路由测试覆盖
def register_opening_stock_routes(app):
    @app.route('/opening_stock')
    @login_required
    def opening_stock_list():
        """期初库存列表"""
        from app import (
            Material,
            OpeningStock,
            date,
            db,
            get_active_warehouses,
            get_default_warehouse,
            joinedload,
            normalize_stock_quantity,
            render_template,
            request,
            round_to_2_decimals,
        )
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        per_page = per_page if per_page in [10, 20, 50, 100, 200] else 20
        search = (request.args.get('search') or '').strip()
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        warehouse_id = request.args.get('warehouse_id', type=int)  # AI-OS-MW-001: 仓库筛选

        query = OpeningStock.query.options(
            joinedload(OpeningStock.material).joinedload(Material.unit),
            joinedload(OpeningStock.operator),
            joinedload(OpeningStock.warehouse),
        ).join(Material)
        if search:
            like = f'%{search}%'
            query = query.filter(db.or_(
                Material.code.like(like),
                Material.name.like(like),
                Material.spec.like(like),
                OpeningStock.remark.like(like),
            ))
        if warehouse_id:
            query = query.filter(OpeningStock.warehouse_id == warehouse_id)

        allowed_sorts = {
            'id': OpeningStock.id,
            'material_code': Material.code,
            'material_name': Material.name,
            'quantity': OpeningStock.quantity,
            'price': OpeningStock.price,
            'amount': OpeningStock.amount,
            'created_at': OpeningStock.created_at,
            'updated_at': OpeningStock.updated_at,
        }
        sort_column = allowed_sorts.get(sort_by, OpeningStock.created_at)
        query = query.order_by(sort_column.asc() if sort_order == 'asc' else sort_column.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        materials = Material.query.options(joinedload(Material.unit)).order_by(Material.code.asc(), Material.id.asc()).all()
        material_options = [{
            'id': material.id,
            'code': material.code or '',
            'name': material.name or '',
            'spec': material.spec or '',
            'unit': material.unit.name if material.unit else '',
            'stock': normalize_stock_quantity(material.stock or 0),
            'price': round_to_2_decimals(material.price or 0),
        } for material in materials]
        warehouses = get_active_warehouses()  # AI-OS-MW-001
        opening_doc_no = f'OP{date.today().strftime("%Y%m%d")}'
        return render_template(
            'opening_stock.html',
            records=pagination.items,
            materials=materials,
            material_options=material_options,
            pagination=pagination,
            filters={'search': search, 'warehouse_id': warehouse_id},
            sort_by=sort_by,
            sort_order=sort_order,
            per_page=per_page,
            opening_doc_no=opening_doc_no,
            doc_date=date.today().isoformat(),
            warehouses=warehouses,
            # BUG-2026-08-02-017：期初建账仓库必填，新建时预选默认仓库
            default_warehouse=get_default_warehouse(),
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/opening_stock/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_opening_stock():
        """新增期初库存"""
        from app import (
            OpeningStock,
            _apply_opening_stock_balance,
            _opening_stock_payload_from_request,
            app,
            db,
            jsonify,
            log_operation,
        )
        payload, error = _opening_stock_payload_from_request()
        if error:
            return jsonify({'status': 'error', 'msg': error}), 400

        material = payload['material']
        warehouse = payload['warehouse']
        existing = OpeningStock.query.filter_by(
            material_id=material.id, warehouse_id=warehouse.id
        ).with_for_update().first()
        if existing:
            return jsonify({'status': 'error', 'msg': f'该物料在仓库 [{warehouse.name}] 已存在期初库存，请使用编辑按差额调整'}), 400

        try:
            opening, delta = _apply_opening_stock_balance(
                None, material, payload['quantity'], payload['price'], payload['amount'], payload['remark'], warehouse, payload.get('date')
            )
            db.session.commit()
            log_operation('新增期初库存', f'{material.code} @ {warehouse.name} 数量 {payload["quantity"]}', 'opening_stock', opening.id)
            return jsonify({'status': 'success', 'msg': '期初库存已保存', 'delta': delta})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'新增期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存保存失败'}), 500

    @app.route('/opening_stock/<int:id>')
    @login_required
    def get_opening_stock(id):
        """获取单条期初库存"""
        from app import Material, OpeningStock, joinedload, jsonify
        opening = OpeningStock.query.options(
            joinedload(OpeningStock.material).joinedload(Material.unit),
            joinedload(OpeningStock.warehouse),
        ).get(id)
        if not opening:
            return jsonify({'status': 'error', 'msg': '期初库存记录不存在'}), 404
        material = opening.material
        return jsonify({
            'status': 'success',
            'record': {
                'id': opening.id,
                'material_id': opening.material_id,
                'warehouse_id': opening.warehouse_id,
                'warehouse_name': opening.warehouse.name if opening.warehouse else '',
                'date': opening.date.isoformat() if opening.date else '',
                'material_code': material.code if material else '',
                'material_name': material.name if material else '',
                'spec': material.spec if material else '',
                'unit': material.unit.name if material and material.unit else '',
                'quantity': opening.quantity or 0,
                'price': opening.price or 0,
                'amount': opening.amount or 0,
                'remark': opening.remark or '',
            }
        })

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/opening_stock/edit/<int:id>', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def edit_opening_stock(id):
        """编辑期初库存（按差额调整）"""
        from app import (
            Material,
            OpeningStock,
            _apply_opening_stock_balance,
            _opening_stock_payload_from_request,
            app,
            db,
            joinedload,
            jsonify,
            log_operation,
        )
        opening = OpeningStock.query.options(joinedload(OpeningStock.material)).filter_by(id=id).with_for_update().first()
        if not opening:
            return jsonify({'status': 'error', 'msg': '期初库存记录不存在'}), 404

        payload, error = _opening_stock_payload_from_request()
        if error:
            return jsonify({'status': 'error', 'msg': error}), 400
        if payload['material'].id != opening.material_id:
            return jsonify({'status': 'error', 'msg': '期初库存编辑不能更换物料，请新增目标物料的期初记录'}), 400
        if payload['warehouse'].id != opening.warehouse_id:
            return jsonify({'status': 'error', 'msg': '期初库存编辑不能更换仓库，如需调整请到目标仓库新增'}), 400

        try:
            opening, delta = _apply_opening_stock_balance(
                opening, payload['material'], payload['quantity'], payload['price'], payload['amount'], payload['remark'], payload['warehouse'], payload.get('date')
            )
            db.session.commit()
            log_operation('编辑期初库存', f'{payload["material"].code} @ {payload["warehouse"].name} 差额 {delta}', 'opening_stock', opening.id)
            return jsonify({'status': 'success', 'msg': '期初库存已更新', 'delta': delta})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'编辑期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存更新失败'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/opening_stock/batch_save', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_save_opening_stock():
        """批量保存期初库存"""
        from app import (
            Material,
            OpeningStock,
            STOCK_COMPARE_EPSILON,
            Warehouse,
            _apply_opening_stock_balance,
            _parse_opening_stock_date,
            app,
            db,
            jsonify,
            log_operation,
            normalize_stock_quantity,
            parse_float_value,
            request,
            round_to_2_decimals,
        )
        data = request.get_json(silent=True) or {}
        items = data.get('items') or []
        if not isinstance(items, list):
            return jsonify({'status': 'error', 'msg': '明细数据格式错误'}), 400

        seen_keys = set()  # AI-OS-MW-001: (material_id, warehouse_id) 唯一
        normalized_items = []
        for index, item in enumerate(items, start=1):
            material_id = item.get('material_id')
            try:
                material_id = int(material_id)
            except (TypeError, ValueError):
                return jsonify({'status': 'error', 'msg': f'第 {index} 行请选择物料'}), 400
            warehouse_id = item.get('warehouse_id')
            try:
                warehouse_id = int(warehouse_id) if warehouse_id not in (None, '') else None
            except (TypeError, ValueError):
                warehouse_id = None
            if not warehouse_id:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行请选择仓库'}), 400
            dedup_key = (material_id, warehouse_id)
            if dedup_key in seen_keys:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行物料+仓库重复，请合并后保存'}), 400
            seen_keys.add(dedup_key)

            material = Material.query.filter_by(id=material_id).with_for_update().first()
            if not material:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行物料不存在'}), 400
            warehouse = Warehouse.query.filter_by(id=warehouse_id).with_for_update().first()
            if not warehouse:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行仓库不存在'}), 400
            if (warehouse.status or 'active') != 'active':
                return jsonify({'status': 'error', 'msg': f'第 {index} 行仓库 [{warehouse.name}] 已停用，禁止期初建账'}), 400

            quantity = parse_float_value(item.get('quantity'), None)
            price = parse_float_value(item.get('price'), 0)
            if quantity is None:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行请输入数量'}), 400
            if quantity < 0:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行期初数量不能小于 0'}), 400
            if price < 0:
                return jsonify({'status': 'error', 'msg': f'第 {index} 行单价不能小于 0'}), 400

            normalized_items.append({
                'material': material,
                'warehouse': warehouse,
                'date': _parse_opening_stock_date(item.get('date')),
                'quantity': normalize_stock_quantity(quantity),
                'price': round_to_2_decimals(price),
                'amount': round_to_2_decimals(quantity * price),
                'remark': ((item.get('remark') or '').strip() or None),
            })

        if not normalized_items:
            return jsonify({'status': 'error', 'msg': '请至少录入一行期初库存'}), 400

        try:
            changed_count = 0
            for item in normalized_items:
                material = item['material']
                warehouse = item['warehouse']
                opening = OpeningStock.query.filter_by(
                    material_id=material.id, warehouse_id=warehouse.id
                ).with_for_update().first()
                _, delta = _apply_opening_stock_balance(
                    opening,
                    material,
                    item['quantity'],
                    item['price'],
                    item['amount'],
                    item['remark'],
                    warehouse,
                    item['date'],
                )
                if opening is None or abs(delta) > STOCK_COMPARE_EPSILON:
                    changed_count += 1
            db.session.commit()
            log_operation('保存期初库存单据', f'保存 {len(normalized_items)} 行，库存变动 {changed_count} 行', 'opening_stock', None)
            return jsonify({'status': 'success', 'msg': f'期初库存已保存，共 {len(normalized_items)} 行', 'changed_count': changed_count})
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量保存期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存保存失败'}), 500