# 手机端扫码（mobile）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（add_stock / deduct_stock / _create_adjustment_drafts_from_check_scan 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=从 app.py 原样迁移的辅助函数，能力由 mobile_* 各路由测试覆盖
def mobile_material_payload(material):
    from app import (
        LocationInventory,
        location_management_enabled,
        normalize_stock_quantity,
        round_to_2_decimals,
    )
    locations = []
    if location_management_enabled():
        rows = LocationInventory.query.filter_by(material_id=material.id).order_by(LocationInventory.location.asc()).all()
        locations = [
            {
                'location': row.location,
                'quantity': normalize_stock_quantity(row.quantity or 0),
            }
            for row in rows
            if normalize_stock_quantity(row.quantity or 0) != 0
        ]

    return {
        'id': material.id,
        'code': material.code or '',
        'name': material.name or '',
        'spec': material.spec or '',
        'unit': material.unit.name if material.unit else '',
        'category': material.category.name if material.category else '',
        'supplier': material.supplier.name if material.supplier else '',
        'stock': normalize_stock_quantity(material.stock or 0),
        'price': round_to_2_decimals(material.price or 0),
        'locations': locations,
    }


# no-test:reason=从 app.py 原样迁移的辅助函数，能力由 mobile_* 各路由测试覆盖
def find_mobile_material(keyword):
    from app import Material, db, joinedload
    keyword = (keyword or '').strip()
    if not keyword:
        return None, []

    query_options = (
        joinedload(Material.unit),
        joinedload(Material.category),
        joinedload(Material.supplier),
    )
    exact = Material.query.options(*query_options).filter_by(code=keyword).first()
    if exact:
        return exact, []

    like = f'%{keyword}%'
    matches = (
        Material.query.options(*query_options)
        .filter(db.or_(
            Material.code.like(like),
            Material.name.like(like),
            Material.spec.like(like),
        ))
        .order_by(Material.code.asc(), Material.id.asc())
        .limit(10)
        .all()
    )
    if len(matches) == 1:
        return matches[0], []
    return None, matches


# no-test:reason=路由注册辅助函数，能力由 mobile_* 各路由测试覆盖
def register_mobile_routes(app):
    @app.route('/mobile/app')
    def mobile_app_download():
        from app import ANDROID_APK_PATHS, abort, os, send_file
        apk_path = next((path for path in ANDROID_APK_PATHS if os.path.isfile(path)), None)
        if not apk_path:
            abort(404)
        return send_file(
            apk_path,
            mimetype='application/vnd.android.package-archive',
            as_attachment=True,
            download_name='wms-mobile-scan.apk'
        )

    @app.route('/mobile/connect')
    @login_required
    def mobile_connect():
        from app import render_template, request, url_for
        base_url = request.url_root.rstrip('/')
        return render_template(
            'mobile_connect.html',
            base_url=base_url,
            qr_url=url_for('api_qrcode_image', data=base_url),
        )

    @app.route('/mobile/scan')
    @login_required
    def mobile_scan():
        from app import (
            Department,
            MOBILE_SCAN_MODES,
            Warehouse,
            current_user,
            render_template,
            request,
        )
        mode = (request.args.get('mode') or 'query').strip()
        if mode not in MOBILE_SCAN_MODES:
            mode = 'query'
        warehouses = Warehouse.query.filter_by(status='active').order_by(Warehouse.code.asc(), Warehouse.id.asc()).all()
        departments = Department.query.filter_by(status='active').order_by(Department.code.asc(), Department.id.asc()).all()
        return render_template(
            'mobile_scan.html',
            mode=mode,
            modes=MOBILE_SCAN_MODES,
            mode_config=MOBILE_SCAN_MODES[mode],
            warehouses=warehouses,
            departments=departments,
            can_write=current_user.role in ('admin', 'warehouse'),
        )

    @app.route('/mobile/api/material_lookup')
    @login_required
    def mobile_material_lookup():
        from app import jsonify, request
        keyword = (request.args.get('code') or request.args.get('q') or '').strip()
        material, matches = find_mobile_material(keyword)
        if material:
            return jsonify({
                'status': 'success',
                'success': True,
                'data': mobile_material_payload(material),
            })
        if matches:
            return jsonify({
                'status': 'multiple',
                'success': True,
                'msg': '请选择物料',
                'data': {
                    'matches': [mobile_material_payload(item) for item in matches],
                },
            })
        return jsonify({'status': 'error', 'success': False, 'msg': '物料不存在'}), 404

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/mobile/api/scan_submit', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def mobile_scan_submit():
        from flask import current_app
        from app import (
            Department,
            InOrder,
            InOrderItem,
            InventoryCheckScan,
            InventoryCheckScanItem,
            LocationInventory,
            MOBILE_SCAN_MODES,
            Material,
            OutOrder,
            OutOrderItem,
            add_stock,
            allow_negative_location_stock,
            allow_negative_stock,
            current_user,
            date,
            db,
            deduct_stock,
            generate_order_no,
            is_stock_sufficient,
            joinedload,
            jsonify,
            location_available_stock_control,
            location_management_enabled,
            location_required_on_save,
            log_operation,
            normalize_stock_quantity,
            parse_float_value,
            request,
            round_to_2_decimals,
            update_location_inventory,
            _create_adjustment_drafts_from_check_scan,
        )
        data = request.get_json(silent=True) or {}
        mode = (data.get('mode') or '').strip()
        code = (data.get('code') or '').strip()
        if mode not in MOBILE_SCAN_MODES:
            return jsonify({'status': 'error', 'success': False, 'msg': '扫码类型不正确'}), 400
        if not code:
            return jsonify({'status': 'error', 'success': False, 'msg': '请输入物料编码'}), 400

        material = (
            Material.query.options(joinedload(Material.unit), joinedload(Material.category), joinedload(Material.supplier))
            .filter_by(code=code)
            .first()
        )
        if not material:
            return jsonify({'status': 'error', 'success': False, 'msg': f'物料不存在：{code}'}), 404

        if mode == 'query':
            return jsonify({
                'status': 'success',
                'success': True,
                'msg': '查询成功',
                'data': {'material': mobile_material_payload(material)},
            })

        if current_user.role not in ('admin', 'warehouse'):
            return jsonify({'status': 'error', 'success': False, 'msg': '当前账号没有仓库操作权限'}), 403

        warehouse = (data.get('warehouse') or data.get('location') or '').strip()
        remark = (data.get('remark') or '').strip()
        if mode in ('in', 'out') and location_management_enabled() and location_required_on_save() and not warehouse:
            return jsonify({'status': 'error', 'success': False, 'msg': '启用库位管理后，扫码出入库必须填写仓库/库位'}), 400

        try:
            if mode == 'in':
                quantity = round_to_2_decimals(parse_float_value(data.get('quantity'), 0))
                if quantity <= 0:
                    return jsonify({'status': 'error', 'success': False, 'msg': '入库数量必须大于0'}), 400

                price = round_to_2_decimals(material.price or 0)
                order = InOrder(
                    order_no=generate_order_no('IN'),
                    date=date.today(),
                    business_type='产品入库',
                    purpose='手机扫码入库',
                    warehouse=warehouse or None,
                    remark=remark or '手机端扫码提交',
                    status='completed',
                    operator_id=current_user.id,
                    total_amount=round_to_2_decimals(quantity * price),
                )
                db.session.add(order)
                db.session.flush()
                db.session.add(InOrderItem(
                    in_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                ))
                ok, error_msg = add_stock(material, quantity, 'in', 'in_order', order.id, f'手机扫码入库 {order.order_no}')
                if not ok:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库存增加失败'}), 500
                if location_management_enabled() and warehouse:
                    ok, error_msg = update_location_inventory(material, warehouse, quantity)
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库位库存更新失败'}), 400
                db.session.commit()
                log_operation('手机扫码入库', f'入库单：{order.order_no}', 'in_order', order.id)
                return jsonify({
                    'status': 'success',
                    'success': True,
                    'msg': f'入库成功：{order.order_no}',
                    'data': {'order_no': order.order_no, 'material': mobile_material_payload(material)},
                })

            if mode == 'out':
                quantity = round_to_2_decimals(parse_float_value(data.get('quantity'), 0))
                if quantity <= 0:
                    return jsonify({'status': 'error', 'success': False, 'msg': '出库数量必须大于0'}), 400

                current_stock = normalize_stock_quantity(material.stock or 0)
                if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                    return jsonify({
                        'status': 'error',
                        'success': False,
                        'msg': f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}',
                    }), 400
                if location_management_enabled() and warehouse and location_available_stock_control() and not allow_negative_location_stock():
                    location_inventory = LocationInventory.query.filter_by(
                        material_id=material.id,
                        location=warehouse
                    ).first()
                    location_stock = normalize_stock_quantity(location_inventory.quantity if location_inventory else 0)
                    if not is_stock_sufficient(location_stock, quantity):
                        return jsonify({
                            'status': 'error',
                            'success': False,
                            'msg': f'物料 {material.code} 在 {warehouse} 库位库存不足，当前库位库存：{location_stock:.2f}',
                        }), 400

                target = (data.get('target') or data.get('receiver') or '').strip()
                department = None
                if target:
                    department = Department.query.filter(db.or_(Department.code == target, Department.name == target)).first()
                price = round_to_2_decimals(material.price or 0)
                order = OutOrder(
                    order_no=generate_order_no('OU'),
                    date=date.today(),
                    department_id=department.id if department else None,
                    customer=(department.name if department else target) or None,
                    business_type='领料单',
                    warehouse=warehouse or None,
                    purpose='手机扫码出库',
                    remark=remark or '手机端扫码提交',
                    status='completed',
                    operator_id=current_user.id,
                    total_amount=round_to_2_decimals(quantity * price),
                )
                db.session.add(order)
                db.session.flush()
                db.session.add(OutOrderItem(
                    out_order_id=order.id,
                    material_id=material.id,
                    quantity=quantity,
                    price=price,
                    amount=round_to_2_decimals(quantity * price),
                ))
                ok, error_msg = deduct_stock(material, quantity, 'out', 'out_order', order.id, f'手机扫码出库 {order.order_no}')
                if not ok:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库存扣减失败'}), 400
                if location_management_enabled() and warehouse:
                    ok, error_msg = update_location_inventory(material, warehouse, -quantity)
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库位库存扣减失败'}), 400
                db.session.commit()
                log_operation('手机扫码出库', f'领料单：{order.order_no}', 'out_order', order.id)
                return jsonify({
                    'status': 'success',
                    'success': True,
                    'msg': f'出库成功：{order.order_no}',
                    'data': {'order_no': order.order_no, 'material': mobile_material_payload(material)},
                })

            if mode == 'check':
                actual_raw = data.get('actual_stock')
                if actual_raw is None or str(actual_raw).strip() == '':
                    actual_raw = data.get('quantity')
                if actual_raw is None or str(actual_raw).strip() == '':
                    return jsonify({'status': 'error', 'success': False, 'msg': '请输入盘点数量'}), 400
                actual_stock = round_to_2_decimals(parse_float_value(actual_raw, 0))
                system_stock = normalize_stock_quantity(material.stock or 0)
                check = InventoryCheckScan(
                    check_no=generate_order_no('CS'),
                    date=date.today(),
                    remark=remark or '手机扫码盘点',
                    status='completed',
                    operator_id=current_user.id,
                )
                db.session.add(check)
                db.session.flush()
                db.session.add(InventoryCheckScanItem(
                    check_scan_id=check.id,
                    material_id=material.id,
                    system_stock=system_stock,
                    actual_stock=actual_stock,
                    difference=round_to_2_decimals(actual_stock - system_stock),
                ))
                drafts, error = _create_adjustment_drafts_from_check_scan(check)
                if error:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'success': False, 'msg': error}), 400
                db.session.commit()
                log_operation('手机扫码盘点', f'扫码盘点单：{check.check_no}', 'inventory_check_scan', check.id)
                msg = f'盘点保存成功：{check.check_no}'
                if drafts:
                    msg += '，已生成库存调整草稿，请审核后提交'
                return jsonify({
                    'status': 'success',
                    'success': True,
                    'msg': msg,
                    'data': {
                        'check_no': check.check_no,
                        'adjustment_nos': [order.adjustment_no for order in drafts],
                        'material': mobile_material_payload(material),
                    },
                })
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Mobile scan submit failed')
            return jsonify({'status': 'error', 'success': False, 'msg': '提交失败，请稍后重试'}), 500

        return jsonify({'status': 'error', 'success': False, 'msg': '扫码类型不正确'}), 400

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/mobile/api/recognize_material', methods=['POST'])
    @login_required
    def mobile_recognize_material():
        from flask import current_app
        from app import Material, db, joinedload, jsonify, request
        from app import _ai_call_llm_vision, _ai_llm_configured, _ai_llm_vision_enabled
        if not _ai_llm_configured() or not _ai_llm_vision_enabled():
            return jsonify({'status': 'error', 'msg': '请先在系统设置中启用大模型和图片识别'}), 400

        if 'image' not in request.files:
            return jsonify({'status': 'error', 'msg': '请上传图片'}), 400

        file = request.files['image']
        if not file.filename:
            return jsonify({'status': 'error', 'msg': '请选择图片文件'}), 400

        allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_ext:
            return jsonify({'status': 'error', 'msg': '不支持的图片格式'}), 400

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'status': 'error', 'msg': '图片大小不能超过10MB'}), 400

        try:
            import base64
            img_data = base64.b64encode(file.read()).decode('ascii')
            data_url = f'data:image/{ext};base64,{img_data}'

            prompt = '''请识别这张图片中的物料。如果是物料标签、物料实物或包装，请提取：
1. 物料编码（如有）
2. 物料名称
3. 规格型号
4. 数量（如有）

请在回答末尾追加 JSON 代码块，格式如下：
```json
{"code": "编码", "name": "名称", "spec": "规格", "quantity": 数量或null, "confidence": 0.8}
```
如果无法识别，code和name留空，confidence设为0。'''

            reply, extracted, error = _ai_call_llm_vision(prompt, [{'data_url': data_url}])
            if error:
                return jsonify({'status': 'error', 'msg': error}), 500

            matches = []
            if extracted:
                code = (extracted.get('code') or '').strip()
                name = (extracted.get('name') or '').strip()
                spec = (extracted.get('spec') or '').strip()

                query = Material.query.options(
                    joinedload(Material.unit),
                    joinedload(Material.category),
                    joinedload(Material.supplier)
                )
                if code:
                    exact = query.filter_by(code=code).first()
                    if exact:
                        matches = [exact]
                    else:
                        search = f'%{code}%'
                        matches = query.filter(Material.code.like(search)).limit(5).all()
                if not matches and name:
                    search = f'%{name}%'
                    matches = query.filter(
                        db.or_(Material.name.like(search), Material.code.like(search))
                    ).limit(5).all()
                if not matches and spec:
                    search = f'%{spec}%'
                    matches = query.filter(Material.spec.like(search)).limit(5).all()

            return jsonify({
                'status': 'success',
                'reply': reply,
                'extracted': extracted,
                'matches': [mobile_material_payload(m) for m in matches],
                'match_count': len(matches)
            })
        except Exception as e:
            current_app.logger.error(f'拍照识物失败: {e}')
            return jsonify({'status': 'error', 'msg': '识别失败，请稍后重试'}), 500