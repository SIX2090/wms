# 期初库存（opening_stock）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（_opening_stock_payload_from_request / _apply_opening_stock_balance 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask import abort
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 opening_stock_* 各路由测试覆盖
def register_opening_stock_routes(app):
    @app.route('/opening_stock')
    @login_required
    def opening_stock_list():
        """期初库存单据列表（BUG-2026-09-15-009：单据列表 + 单据编辑分离）。

        列表页只列**单据**（单据号/日期/仓库/明细行数/合计金额/备注），点开某张
        才进单据编辑页（/opening_stock/<id>）；不再同页堆叠"台账查询 + 录入网格"
        ——那是用户说的"乱七八糟"。新建走 /opening_stock/add（纯单据编辑页）。
        """
        from app import (
            OpeningStock,
            OpeningStockDoc,
            Warehouse,
            db,
            get_active_warehouses,
            render_template,
            request,
        )
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        per_page = per_page if per_page in [10, 20, 50, 100, 200] else 20
        search = (request.args.get('search') or '').strip()
        warehouse_id = request.args.get('warehouse_id', type=int)

        query = OpeningStockDoc.query
        if search:
            like = f'%{search}%'
            query = query.filter(db.or_(
                OpeningStockDoc.doc_no.like(like),
                OpeningStockDoc.remark.like(like),
                OpeningStockDoc.warehouse.has(db.or_(
                    Warehouse.name.like(like), Warehouse.code.like(like))),
            ))
        if warehouse_id:
            # 表头仓库或任一明细行仓库命中，即算该单据涉及此仓
            query = query.filter(db.or_(
                OpeningStockDoc.warehouse_id == warehouse_id,
                OpeningStockDoc.lines.any(OpeningStock.warehouse_id == warehouse_id),
            ))
        query = query.order_by(OpeningStockDoc.created_at.desc(), OpeningStockDoc.id.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        docs = []
        for doc in pagination.items:
            lines = list(doc.lines)
            wh_names = []
            for line in lines:
                if line.warehouse and line.warehouse.name and line.warehouse.name not in wh_names:
                    wh_names.append(line.warehouse.name)
            if doc.warehouse:
                wh_display = doc.warehouse.name
            elif len(wh_names) == 1:
                wh_display = wh_names[0]
            elif len(wh_names) > 1:
                wh_display = '多仓库'
            else:
                wh_display = '未指定'
            docs.append({
                'id': doc.id,
                'doc_no': doc.doc_no,
                'date': doc.date,
                'warehouse_display': wh_display,
                'line_count': len(lines),
                'total_amount': sum((line.amount or 0) for line in lines),
                'remark': doc.remark or '',
                'updated_at': doc.updated_at,
            })

        return render_template(
            'opening_stock_list.html',
            docs=docs,
            pagination=pagination,
            filters={'search': search, 'warehouse_id': warehouse_id},
            per_page=per_page,
            warehouses=get_active_warehouses(),
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
                None, material, payload['quantity'], payload['price'], payload['amount'], payload['remark'], warehouse, payload.get('date'), payload.get('location', '')
            )
            db.session.commit()
            log_operation('新增期初库存', f'{material.code} @ {warehouse.name} 数量 {payload["quantity"]}', 'opening_stock', opening.id)
            return jsonify({'status': 'success', 'msg': '期初库存已保存', 'delta': delta})
        except ValueError as ve:
            # BUG-2026-08-16-002：库位账同步失败（如库位库存不足）返回明确原因并整体回滚
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'新增期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存保存失败'}), 500

    @app.route('/opening_stock/<int:id>')
    @login_required
    def opening_stock_doc_detail(id):
        """期初库存单据编辑页（ARCH-OS-DOC-01）。

        路径形态 /opening_stock/<id> 是硬约束：前端 getCurrentRecordId() 用
        /\\/(\\d+)(?:\\/(?:edit|detail))?\\/?\\$/ 从路径末段取当前单据 id，
        首/上/下/末 导航与"保存到该单据"都依赖它。改成别的形态会让导航
        静默失效。
        """
        from app import (
            Material,
            OpeningStock,
            OpeningStockDoc,
            date,
            get_active_warehouses,
            get_default_warehouse,
            joinedload,
            normalize_stock_quantity,
            render_template,
            round_to_2_decimals,
        )
        doc = OpeningStockDoc.query.options(
            joinedload(OpeningStockDoc.warehouse),
            joinedload(OpeningStockDoc.lines).joinedload(OpeningStock.material).joinedload(Material.unit),
            joinedload(OpeningStockDoc.lines).joinedload(OpeningStock.warehouse),
        ).filter_by(id=id).first()
        if not doc:
            abort(404)

        # 明细回填：字段名与前端 rows / collectItems() 保持一致，
        # 否则打开单据后明细会显示为空白行。
        edit_rows = [{
            'line_id': line.id,
            'doc_id': line.doc_id,
            'material_id': line.material_id,
            'material_code': line.material.code if line.material else '',
            'material_name': line.material.name if line.material else '',
            'spec': line.material.spec if line.material else '',
            'unit': line.material.unit.name if line.material and line.material.unit else '',
            'warehouse_id': line.warehouse_id,
            'quantity': normalize_stock_quantity(line.quantity or 0),
            'price': round_to_2_decimals(line.price or 0),
            'remark': line.remark or '',
            'date': line.date.isoformat() if line.date else '',
            'location': line.location or '',
        } for line in doc.lines]

        materials = Material.query.options(joinedload(Material.unit)).order_by(
            Material.code.asc(), Material.id.asc()).all()
        material_options = [{
            'id': material.id,
            'code': material.code or '',
            'name': material.name or '',
            'spec': material.spec or '',
            'unit': material.unit.name if material.unit else '',
            'stock': normalize_stock_quantity(material.stock or 0),
            'price': round_to_2_decimals(material.price or 0),
        } for material in materials]

        return render_template(
            'opening_stock.html',
            records=[],
            materials=materials,
            material_options=material_options,
            pagination=None,
            filters={'search': '', 'warehouse_id': None},
            sort_by='created_at',
            sort_order='desc',
            per_page=20,
            doc_date=(doc.date.isoformat() if doc.date else date.today().isoformat()),
            warehouses=get_active_warehouses(),
            default_warehouse=doc.warehouse or get_default_warehouse(),
            editing_doc=doc,
            edit_rows=edit_rows,
        )

    @app.route('/opening_stock/add')
    @login_required
    def opening_stock_doc_add():
        """新建期初库存单据页（ARCH-OS-DOC-01）。

        与列表页同一模板，只是不绑定任何单据；/add 结尾会被前端
        isFormPage() 识别为录入态。
        """
        from app import (
            Material,
            date,
            get_active_warehouses,
            get_default_warehouse,
            joinedload,
            normalize_stock_quantity,
            render_template,
            round_to_2_decimals,
        )
        materials = Material.query.options(joinedload(Material.unit)).order_by(
            Material.code.asc(), Material.id.asc()).all()
        material_options = [{
            'id': material.id,
            'code': material.code or '',
            'name': material.name or '',
            'spec': material.spec or '',
            'unit': material.unit.name if material.unit else '',
            'stock': normalize_stock_quantity(material.stock or 0),
            'price': round_to_2_decimals(material.price or 0),
        } for material in materials]
        return render_template(
            'opening_stock.html',
            records=[],
            materials=materials,
            material_options=material_options,
            pagination=None,
            filters={'search': '', 'warehouse_id': None},
            sort_by='created_at',
            sort_order='desc',
            per_page=20,
            doc_date=date.today().isoformat(),
            warehouses=get_active_warehouses(),
            default_warehouse=get_default_warehouse(),
            editing_doc=None,
            edit_rows=[],
        )

    @app.route('/opening_stock/line/<int:id>')
    @login_required
    def get_opening_stock(id):
        """获取单条期初库存明细（JSON）。

        路径从 /opening_stock/<id> 改为 /opening_stock/line/<id>——
        前者已让给单据编辑页（导航需要末段数字指向单据）。
        """
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
                'doc_id': opening.doc_id,
                'material_id': opening.material_id,
                'warehouse_id': opening.warehouse_id,
                'warehouse_name': opening.warehouse.name if opening.warehouse else '',
                'location': getattr(opening, 'location', '') or '',
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
                opening, payload['material'], payload['quantity'], payload['price'], payload['amount'], payload['remark'], payload['warehouse'], payload.get('date'), payload.get('location', '')
            )
            db.session.commit()
            log_operation('编辑期初库存', f'{payload["material"].code} @ {payload["warehouse"].name} 差额 {delta}', 'opening_stock', opening.id)
            return jsonify({'status': 'success', 'msg': '期初库存已更新', 'delta': delta})
        except ValueError as ve:
            # BUG-2026-08-16-002：库位账同步失败（如库位库存不足）返回明确原因并整体回滚
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'编辑期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存更新失败'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/opening_stock/batch_save', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def batch_save_opening_stock():
        """批量保存期初库存（ARCH-OS-DOC-01 双分支）。

        兼容设计（关键）：本路由的调用方有两代——
          · 老调用方（粘贴导入、移动端、既有测试、外部脚本）提交 {items:[...]}，
            不带 doc_id；
          · 新前端提交 {doc_id, date, warehouse_id, remark, items:[...]}。
        两代必须同时正确，因此：

        - 无 doc_id：懒创建一张「兼容单」并归入，保持原「同 (物料,仓库) 只有
          一行、重复保存即覆盖」的 upsert 语义。老测试断言 len(recs)==1 与
          date 覆盖行为依赖这一点，不能改成每次新建行。
        - 有 doc_id：单据内按 (doc_id, 物料, 仓库) 行级 upsert，并把提交集中
          不存在的旧行回冲后删除——这就是用户要的「导入的单据可改明细」。
        """
        from app import (
            Material,
            OpeningStock,
            OpeningStockDoc,
            STOCK_COMPARE_EPSILON,
            Warehouse,
            _apply_opening_stock_balance,
            _opening_stock_compat_doc,
            _opening_stock_normalize_items,
            _reverse_opening_stock_line,
            app,
            date,
            datetime,
            db,
            generate_order_no,
            jsonify,
            log_operation,
            normalize_stock_quantity,
            parse_float_value,
            request,
            round_to_2_decimals,
        )
        data = request.get_json(silent=True) or {}

        # 单据头字段：doc_id 缺省即走兼容路径
        try:
            doc_id = data.get('doc_id')
            doc_id = int(doc_id) if doc_id not in (None, '') else None
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'msg': '单据标识格式错误'}), 400

        normalized_items, error = _opening_stock_normalize_items(
            data.get('items'),
            Material=Material,
            Warehouse=Warehouse,
            normalize_stock_quantity=normalize_stock_quantity,
            parse_float_value=parse_float_value,
            round_to_2_decimals=round_to_2_decimals,
        )
        if error:
            return jsonify({'status': 'error', 'msg': error['msg']}), error['code']

        try:
            changed_count = 0
            removed_count = 0

            if doc_id is None:
                # ---- 兼容分支：老调用方，保持单行 upsert 语义 ----
                doc = _opening_stock_compat_doc(data.get('date'), generate_order_no)
                for item in normalized_items:
                    item['doc_id'] = doc.id
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
                        item.get('location', ''),
                        doc_id=doc.id,
                    )
                    if opening is None or abs(delta) > STOCK_COMPARE_EPSILON:
                        changed_count += 1
                msg = f'期初库存已保存，共 {len(normalized_items)} 行'
            else:
                # ---- 单据分支：行级 upsert + 差集删除（可改明细） ----
                doc = OpeningStockDoc.query.filter_by(id=doc_id).with_for_update().first()
                if not doc:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': '期初库存单据不存在'}), 404

                header_date = data.get('date')
                if header_date:
                    doc.date = _parse_opening_stock_date(header_date)
                header_wh = data.get('warehouse_id')
                if header_wh not in (None, ''):
                    try:
                        doc.warehouse_id = int(header_wh)
                    except (TypeError, ValueError):
                        db.session.rollback()
                        return jsonify({'status': 'error', 'msg': '单据仓库格式错误'}), 400
                if 'remark' in data:
                    doc.remark = ((data.get('remark') or '').strip() or None)

                submitted_keys = set()
                for item in normalized_items:
                    material = item['material']
                    warehouse = item['warehouse']
                    submitted_keys.add((material.id, warehouse.id))
                    opening = OpeningStock.query.filter_by(
                        doc_id=doc.id, material_id=material.id, warehouse_id=warehouse.id
                    ).with_for_update().first()
                    # 单头日期是权威值：明细未显式给日期时跟随单头
                    item_date = item['date'] or doc.date
                    _, delta = _apply_opening_stock_balance(
                        opening,
                        material,
                        item['quantity'],
                        item['price'],
                        item['amount'],
                        item['remark'],
                        warehouse,
                        item_date,
                        item.get('location', ''),
                        doc_id=doc.id,
                    )
                    if opening is None or abs(delta) > STOCK_COMPARE_EPSILON:
                        changed_count += 1

                # 提交集中已消失的旧行 = 用户删掉了明细行 → 回冲库存后删除
                for stale in list(doc.lines):
                    if (stale.material_id, stale.warehouse_id) in submitted_keys:
                        continue
                    ok, msg_rev = _reverse_opening_stock_line(
                        stale, reason='期初单据删行回冲')
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'msg': msg_rev}), 400
                    db.session.delete(stale)
                    removed_count += 1

                doc.updated_at = datetime.now()
                msg = f'期初库存单据已保存，共 {len(normalized_items)} 行'
                if removed_count:
                    msg += f'，删除 {removed_count} 行并已回冲库存'
                if doc.date:
                    # 单头日期覆盖全部明细行（用户要求"导入的单据改日期"）
                    for line in doc.lines:
                        line.date = doc.date

            db.session.commit()
            log_operation(
                '保存期初库存单据',
                f'单据 {doc.doc_no if doc else "-"}：保存 {len(normalized_items)} 行，'
                f'库存变动 {changed_count} 行，删除 {removed_count} 行',
                'opening_stock', doc.id if doc else None,
            )
            return jsonify({
                'status': 'success',
                'msg': msg,
                'doc_id': doc.id if doc else None,
                'doc_no': doc.doc_no if doc else None,
                'changed_count': changed_count,
                'removed_count': removed_count,
            })
        except ValueError as ve:
            # BUG-2026-08-16-002：库位账同步失败（如库位库存不足）返回明确原因并整体回滚
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'批量保存期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存保存失败'}), 500

    @app.route('/opening_stock/save', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def save_opening_stock_doc():
        """保存期初库存单据（新建 / 编辑统一入口，ARCH-OS-DOC-01）。

        新建：不传 doc_id 或传 null → 取号 QS+YYMM+4位建单头，再落明细。
        编辑：传 doc_id → 更新单头（日期/仓库/备注），明细按 (物料,仓库) 行级
              upsert，提交集中消失的旧行回冲库存后删除（用户要求"可改明细"）。

        与 batch_save 的区别：本路由**只走单据路径**，不产生兼容单；
        老调用方继续用 batch_save。前端新页面统一走这里。
        """
        from app import (
            Material,
            OpeningStock,
            OpeningStockDoc,
            STOCK_COMPARE_EPSILON,
            Warehouse,
            _apply_opening_stock_balance,
            _opening_stock_normalize_items,
            _parse_opening_stock_date,
            _reverse_opening_stock_line,
            app,
            current_user,
            date,
            datetime,
            db,
            generate_order_no,
            jsonify,
            log_operation,
            normalize_stock_quantity,
            parse_float_value,
            request,
            round_to_2_decimals,
        )
        from pydantic import BaseModel, Field, ValidationError

        class OpeningStockItemIn(BaseModel):
            """期初库存明细行入参（字段类型/范围在这里定死）。"""
            material_id: int = Field(gt=0)
            warehouse_id: int = Field(gt=0)
            quantity: float = Field(ge=0, allow_inf_nan=False)
            price: float = Field(default=0, ge=0, allow_inf_nan=False)
            remark: str | None = None
            date: str | None = None
            location: str | None = None

        class OpeningStockDocRequest(BaseModel):
            """期初库存单据保存入参（新建不传 doc_id）。"""
            doc_id: int | None = None
            date: str | None = None
            warehouse_id: int | None = None
            remark: str | None = None
            items: list[OpeningStockItemIn] = Field(default_factory=list)

        data = request.get_json(silent=True) or {}
        try:
            data = OpeningStockDocRequest.model_validate(data).model_dump()
        except ValidationError as ve:
            # 本地化提示：pydantic 的英文错误直接抛给仓管人员等于没提示。
            # 字段名到中文的映射只覆盖明细行最常填错的几个，其余原样回显定位。
            _field_cn = {
                'material_id': '物料',
                'warehouse_id': '仓库',
                'quantity': '数量',
                'price': '单价',
                'date': '日期',
                'items': '明细',
                'doc_id': '单据标识',
            }
            errs = ve.errors()
            first = errs[0] if errs else {}
            loc_parts = [p for p in first.get('loc', ()) if not isinstance(p, int)]
            field = '.'.join(str(p) for p in loc_parts) or '请求体'
            cn = _field_cn.get(str(loc_parts[-1]) if loc_parts else '', None)
            row_idx = next((p for p in first.get('loc', ()) if isinstance(p, int)), None)
            where = f'第 {row_idx + 1} 行' if row_idx is not None else ''
            label = cn or field
            hint = {
                'missing': '为必填项',
                'greater_than_equal': '不能小于 0',
                'greater_than': '必须大于 0',
                'float_parsing': '必须是数字',
                'int_parsing': '必须是整数',
                'list_type': '格式不正确',
            }.get(first.get('type', ''), first.get('msg', '格式不正确'))
            if cn == '明细' and first.get('type') not in (None, 'missing'):
                hint = '格式不正确，应为明细列表'
            return jsonify({
                'status': 'error',
                'msg': f'参数格式错误：{where}{label}{hint}',
            }), 400

        try:
            doc_id = data.get('doc_id')
            doc_id = int(doc_id) if doc_id not in (None, '') else None
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'msg': '单据标识格式错误'}), 400

        normalized_items, error = _opening_stock_normalize_items(
            data.get('items'),
            Material=Material,
            Warehouse=Warehouse,
            normalize_stock_quantity=normalize_stock_quantity,
            parse_float_value=parse_float_value,
            round_to_2_decimals=round_to_2_decimals,
        )
        if error:
            return jsonify({'status': 'error', 'msg': error['msg']}), error['code']

        try:
            header_date_raw = (data.get('date') or '').strip()
            header_date = _parse_opening_stock_date(header_date_raw) if header_date_raw else date.today()

            header_wh = data.get('warehouse_id')
            header_warehouse_id = None
            if header_wh not in (None, ''):
                try:
                    header_warehouse_id = int(header_wh)
                except (TypeError, ValueError):
                    return jsonify({'status': 'error', 'msg': '单据仓库格式错误'}), 400
                warehouse = Warehouse.query.filter_by(id=header_warehouse_id).first()
                if not warehouse:
                    return jsonify({'status': 'error', 'msg': '单据仓库不存在'}), 400
                if (warehouse.status or 'active') != 'active':
                    return jsonify({'status': 'error', 'msg': f'仓库 [{warehouse.name}] 已停用，禁止期初建账'}), 400

            header_remark = ((data.get('remark') or '').strip() or None)

            if doc_id is None:
                doc = OpeningStockDoc(
                    doc_no=generate_order_no('QS'),
                    date=header_date,
                    warehouse_id=header_warehouse_id,
                    status='active',
                    remark=header_remark,
                    operator_id=current_user.id if current_user.is_authenticated else None,
                )
                db.session.add(doc)
                db.session.flush()
                is_new = True
            else:
                doc = OpeningStockDoc.query.filter_by(id=doc_id).with_for_update().first()
                if not doc:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': '期初库存单据不存在'}), 404
                doc.date = header_date
                doc.warehouse_id = header_warehouse_id
                doc.remark = header_remark
                doc.updated_at = datetime.now()
                is_new = False

            changed_count = 0
            submitted_keys = set()
            for item in normalized_items:
                material = item['material']
                warehouse = item['warehouse']
                submitted_keys.add((material.id, warehouse.id))
                opening = OpeningStock.query.filter_by(
                    doc_id=doc.id, material_id=material.id, warehouse_id=warehouse.id
                ).with_for_update().first()
                # 明细未显式给日期时跟随单头（用户要求"改日期"对整单生效）
                item_date = item['date'] or doc.date
                _, delta = _apply_opening_stock_balance(
                    opening,
                    material,
                    item['quantity'],
                    item['price'],
                    item['amount'],
                    item['remark'],
                    warehouse,
                    item_date,
                    item.get('location', ''),
                    doc_id=doc.id,
                )
                if opening is None or abs(delta) > STOCK_COMPARE_EPSILON:
                    changed_count += 1

            removed_count = 0
            if not is_new:
                for stale in list(doc.lines):
                    if (stale.material_id, stale.warehouse_id) in submitted_keys:
                        continue
                    ok, msg_rev = _reverse_opening_stock_line(
                        stale, reason='期初单据删行回冲')
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'msg': msg_rev}), 400
                    db.session.delete(stale)
                    removed_count += 1

            # 单头日期覆盖全部明细行
            db.session.flush()
            for line in doc.lines:
                line.date = doc.date

            db.session.commit()
            log_operation(
                '新增期初库存单据' if is_new else '编辑期初库存单据',
                f'单据 {doc.doc_no}：{len(normalized_items)} 行，'
                f'库存变动 {changed_count} 行，删除 {removed_count} 行',
                'opening_stock', doc.id,
            )
            msg = f'期初库存单据 {doc.doc_no} 已保存，共 {len(normalized_items)} 行'
            if removed_count:
                msg += f'，删除 {removed_count} 行并已回冲库存'
            return jsonify({
                'status': 'success',
                'msg': msg,
                'doc_id': doc.id,
                'doc_no': doc.doc_no,
                'changed_count': changed_count,
                'removed_count': removed_count,
            })
        except ValueError as ve:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'保存期初库存单据失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存单据保存失败'}), 500

    # pydantic:reason=DELETE 无请求体，id 由路由 <int:> 转换器完成类型校验，无需 pydantic 模型
    @app.route('/opening_stock/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_opening_stock_doc(id):
        """删除期初库存单据（物理删除 + 库存回冲，ARCH-OS-DOC-01）。

        用户确认：物理删除 + 库存回冲；若回冲后库存变负，**照常删除**并在
        返回消息里给出中文提示（不阻断，由用户核对后续出库单据）。
        """
        from app import (
            OpeningStockDoc,
            _opening_stock_negative_hint,
            _opening_stock_reverse_all_lines,
            app,
            db,
            jsonify,
            log_operation,
        )
        doc = OpeningStockDoc.query.filter_by(id=id).with_for_update().first()
        if not doc:
            return jsonify({'status': 'error', 'msg': '期初库存单据不存在'}), 404

        try:
            lines = list(doc.lines)
            ok, msg_rev, reversed_count = _opening_stock_reverse_all_lines(doc)
            if not ok:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': f'删除失败：{msg_rev}'}), 400

            hints = _opening_stock_negative_hint(lines)
            doc_no = doc.doc_no
            db.session.delete(doc)
            db.session.commit()
            log_operation('删除期初库存单据', f'单据 {doc_no}：回冲 {reversed_count} 行',
                          'opening_stock', None)
            msg = f'期初库存单据 {doc_no} 已删除，已回冲 {reversed_count} 行库存'
            if hints:
                # 用户确认：照常删除，仅提示；用分号拼接避免消息过长刷屏
                msg += '；注意：' + '；'.join(hints[:3])
            return jsonify({'status': 'success', 'msg': msg, 'reversed_count': reversed_count})
        except ValueError as ve:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'删除期初库存单据失败: {e}')
            return jsonify({'status': 'error', 'msg': '期初库存单据删除失败'}), 500

    # pydantic:reason=DELETE 无请求体，id/line_id 由路由 <int:> 转换器完成类型校验，无需 pydantic 模型
    @app.route('/opening_stock/<int:id>/line/<int:line_id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_opening_stock_line(id, line_id):
        """删除单据内的一条明细行（回冲该行库存，ARCH-OS-DOC-01）。"""
        from app import (
            OpeningStock,
            OpeningStockDoc,
            _opening_stock_negative_hint,
            _reverse_opening_stock_line,
            app,
            db,
            jsonify,
            log_operation,
        )
        doc = OpeningStockDoc.query.filter_by(id=id).first()
        if not doc:
            return jsonify({'status': 'error', 'msg': '期初库存单据不存在'}), 404
        line = OpeningStock.query.filter_by(id=line_id, doc_id=id).with_for_update().first()
        if not line:
            # 防越权：行必须属于该单据，避免用别的单据 id 删这里的行
            return jsonify({'status': 'error', 'msg': '该单据下不存在这行明细'}), 404

        try:
            lines = [line]
            ok, msg_rev = _reverse_opening_stock_line(line, reason='期初单据删行回冲')
            if not ok:
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': f'删除失败：{msg_rev}'}), 400
            hints = _opening_stock_negative_hint(lines)
            db.session.delete(line)
            db.session.commit()
            log_operation('删除期初库存明细行',
                          f'单据 {doc.doc_no}：删除 1 行明细', 'opening_stock', doc.id)
            msg = '明细行已删除，库存已回冲'
            if hints:
                msg += '；注意：' + '；'.join(hints[:3])
            return jsonify({'status': 'success', 'msg': msg})
        except ValueError as ve:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'删除期初库存明细行失败: {e}')
            return jsonify({'status': 'error', 'msg': '明细行删除失败'}), 500

    @app.route('/opening_stock/delete_all', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_all_opening_stock():
        """一键删除全部期初库存（物理删除全部明细行 + 全部单据头，逐行回冲库存）。

        用户诉求（BUG-2026-09-15-008）：导入/建账的期初库存要能一键清空重来。
        与"删除本单"同一规则：物理删除 + 库存回冲；回冲后库存变负照常删除，
        仅在返回消息里中文提示（不阻断）。doc_id 为 NULL 的历史直连台账行也
        逐行回冲后删除，保证清空后 Material.stock / 库位账都不留期初残影。
        """
        from app import (
            OpeningStock,
            OpeningStockDoc,
            _opening_stock_negative_hint,
            _reverse_opening_stock_line,
            app,
            db,
            jsonify,
            log_operation,
            request,
        )
        from pydantic import BaseModel, ValidationError

        class OpeningStockDeleteAllRequest(BaseModel):
            """全量删除入参：必须显式 confirm=true，服务端二次确认防误触（A8）。"""
            confirm: bool

        try:
            payload = OpeningStockDeleteAllRequest.model_validate(
                request.get_json(silent=True) or {})
        except ValidationError:
            return jsonify({'status': 'error', 'msg': '请确认删除操作'}), 400
        if payload.confirm is not True:
            return jsonify({'status': 'error', 'msg': '请确认删除操作'}), 400

        try:
            lines = OpeningStock.query.with_for_update().all()
            reversed_count = 0
            for line in lines:
                ok, msg_rev = _reverse_opening_stock_line(line, reason='期初库存全量删除回冲')
                if not ok:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'msg': f'删除失败：{msg_rev}'}), 400
                reversed_count += 1

            hints = _opening_stock_negative_hint(lines)
            # 先删全部明细行（解除对单据头的引用），再删全部单据头。
            for line in lines:
                db.session.delete(line)
            docs = OpeningStockDoc.query.all()
            deleted_docs = len(docs)
            for doc in docs:
                db.session.delete(doc)
            db.session.commit()
            log_operation('删除全部期初库存',
                          f'回冲 {reversed_count} 行，删除 {deleted_docs} 张单据',
                          'opening_stock', None)
            msg = f'已删除全部期初库存：回冲 {reversed_count} 行明细，删除 {deleted_docs} 张单据'
            if hints:
                # 用户确认：照常删除，仅提示；用分号拼接避免消息过长刷屏
                msg += '；注意：' + '；'.join(hints[:3])
            return jsonify({
                'status': 'success',
                'msg': msg,
                'reversed_count': reversed_count,
                'deleted_docs': deleted_docs,
            })
        except ValueError as ve:
            db.session.rollback()
            return jsonify({'status': 'error', 'msg': str(ve)}), 400
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'删除全部期初库存失败: {e}')
            return jsonify({'status': 'error', 'msg': '删除全部期初库存失败'}), 500

    @app.route('/opening_stock/<int:id>/date', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def update_opening_stock_doc_date(id):
        """修改期初库存单据的建账日期（同步该单所有明细行）。

        用户诉求核心：Excel 导入进来的期初数据要能"改日期"。单头日期是权威值，
        改单头即整单生效；单改日期不动账（不涉及 quantity/amount）。
        """
        from app import (
            OpeningStockDoc,
            _parse_opening_stock_date,
            app,
            datetime,
            db,
            jsonify,
            log_operation,
            request,
        )
        from pydantic import BaseModel, ValidationError

        class OpeningStockDateRequest(BaseModel):
            """改建账日期入参。"""
            date: str

        doc = OpeningStockDoc.query.filter_by(id=id).with_for_update().first()
        if not doc:
            return jsonify({'status': 'error', 'msg': '期初库存单据不存在'}), 404

        try:
            payload = OpeningStockDateRequest.model_validate(
                request.get_json(silent=True) or {}
            )
        except ValidationError:
            return jsonify({'status': 'error', 'msg': '请选择建账日期'}), 400

        raw = payload.date.strip()
        if not raw:
            return jsonify({'status': 'error', 'msg': '请选择建账日期'}), 400

        try:
            new_date = _parse_opening_stock_date(raw)
            doc.date = new_date
            doc.updated_at = datetime.now()
            line_count = 0
            for line in doc.lines:
                line.date = new_date
                line_count += 1
            db.session.commit()
            log_operation('修改期初库存单据日期',
                          f'单据 {doc.doc_no}：改期为 {new_date.isoformat()}，同步 {line_count} 行',
                          'opening_stock', doc.id)
            return jsonify({
                'status': 'success',
                'msg': f'单据 {doc.doc_no} 建账日期已改为 {new_date.isoformat()}，同步 {line_count} 行明细',
                'date': new_date.isoformat(),
                'line_count': line_count,
            })
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'修改期初库存单据日期失败: {e}')
            return jsonify({'status': 'error', 'msg': '建账日期修改失败'}), 500

    # no-test:reason=纯 Excel 模板下载，能力由 verify_opening_stock_import_template 脚本覆盖
    @app.route('/opening_stock/import/template')
    @login_required
    def download_opening_stock_import_template():
        """期初库存 Excel 导入模板下载（含表头 + 示例行）。

        列与粘贴导入 / batch_save 的字段一一对应，供用户填好后走"批量导入"上传。
        """
        from io import BytesIO

        from flask import send_file

        from openpyxl import Workbook
        from openpyxl.styles import Font

        wb = Workbook()
        ws = wb.active
        ws.title = '期初库存导入'
        headers = ['仓库编码', '物料编码', '物料名称', '规格', '单位', '数量', '单价', '备注', '日期']
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        # 示例行：帮助用户理解格式，导入时按"物料名称含'示例'"行跳过
        # 日期列（I 列）格式 YYYY-MM-DD，留空则按导入当天建账
        ws.append(['WH001', 'M-0001', '示例-轴承6204', '内径20mm', '套', '100', '25.50', '示例行，导入时自动忽略', '2026-01-01'])
        for col, width in zip('ABCDEFGHI', (12, 14, 20, 14, 8, 10, 10, 24, 14)):
            ws.column_dimensions[col].width = width
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(
            output,
            download_name='opening_stock_import_template.xlsx',
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )