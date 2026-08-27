# 手机端扫码（mobile）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（add_stock / deduct_stock / _create_adjustment_drafts_from_check_scan 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
import os
import threading
import time
from collections import defaultdict

from flask_login import login_required

from utils import sync_material_primary_image

# A2白名单：@_web_or_api_required / @_web_or_api_role_required 会在 lint_wms_rules.py KNOWN_DECORATOR_HINTS 注册

# 物料档案：每个物料最多归档 5 张图片（移动端上传数量上限）
MAX_MATERIAL_IMAGES = 5


def _web_or_api_required(f):
    """Accept a web session or a mobile Bearer token; lazily resolve app deps
    to avoid import-order issues (register_mobile_routes runs before the
    app.py auth decorators are defined)."""
    from functools import wraps
    from flask import jsonify, request
    from flask_login import current_user

    # no-test:reason=装饰器包装函数，由 endpoint 测试覆盖
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from app import get_bearer_user
        if current_user.is_authenticated:
            return f(*args, **kwargs)
        if get_bearer_user():
            return f(*args, **kwargs)
        return jsonify({'status': 'error', 'success': False, 'msg': '未登录或 Bearer Token 无效'}), 401
    return decorated_function


def _web_or_api_role_required(*roles):
    """Accept a web session or a mobile Bearer token AND require one of the
    given business roles. Mirrors app.web_or_api_role_required but resolves
    get_bearer_user lazily (register_mobile_routes runs before the app.py
    auth decorators are defined). Used to keep mobile write endpoints (e.g.
    material image upload/delete) consistent with their web-side role gates."""
    from functools import wraps
    allowed = set(roles or ())

    # no-test:reason=装饰器工厂，由 endpoint 测试覆盖
    def decorator(f):
        @wraps(f)  # no-test:reason=装饰器包装函数，由 endpoint 测试覆盖
        def decorated_function(*args, **kwargs):
            from flask import jsonify
            from flask_login import current_user
            from app import get_bearer_user
            user = current_user if current_user.is_authenticated else get_bearer_user()
            if user is None:
                return jsonify({'status': 'error', 'success': False, 'msg': '未登录或 Bearer Token 无效'}), 401
            if user.role != 'admin' and user.role not in allowed:
                return jsonify({'status': 'error', 'success': False, 'msg': '当前账号没有权限执行该操作'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# 识图速率限制：AI 识图耗时且昂贵，限制每个用户每分钟最多调用 N 次，
# 防止耗尽大模型 API 配额或导致服务超时。
_RECOGNIZE_RATE_LIMIT = 5
_RECOGNIZE_WINDOW = 60
_recognize_hits = defaultdict(list)
_recognize_lock = threading.Lock()


def _recognize_rate_limited(key):
    """记录一次识图调用并检查限流。超限返回需等待秒数（int），否则返回 None。"""
    now = time.time()
    with _recognize_lock:
        stamps = [t for t in _recognize_hits.get(key, []) if now - t < _RECOGNIZE_WINDOW]
        if len(stamps) >= _RECOGNIZE_RATE_LIMIT:
            _recognize_hits[key] = stamps
            return int(_RECOGNIZE_WINDOW - (now - stamps[0]))
        stamps.append(now)
        _recognize_hits[key] = stamps
        return None


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


def _match_material_by_description(description, query):
    """图形/外观识别回退匹配：用外观描述中的型号字母数字或关键词匹配物料库。

    当图片里没有清晰可读的文字（纯外观/图形/logo）时，视觉模型会输出一段
    description（如"深沟球轴承 6204 金属 银色"）。本函数优先从描述中抽取
    强标识的字母数字型号（如 6204、M8、SKF），再退化为整段描述关键词匹配
    Material 的 code/spec/name 字段。返回匹配到的 Material 列表（最多 5 条）。
    query 为已带 joinedload 的 Material 查询基座，需用 db.or_ 构造新查询。
    """
    from app import Material, db
    description = (description or '').strip()
    if not description:
        return []

    def _search(term):
        if len(term) < 2:
            return []
        search = f'%{term}%'
        return query.filter(
            db.or_(
                Material.code.like(search),
                Material.spec.like(search),
                Material.name.like(search),
            )
        ).limit(5).all()

    # 优先抽取字母数字型号（轴承 6204、螺纹 M8、品牌 SKF6204 等），强标识
    import re
    tokens = re.findall(r'[A-Za-z0-9][A-Za-z0-9.\-]*', description)
    for token in tokens:
        token = token.strip()
        if len(token) < 2:
            continue
        found = _search(token)
        if found:
            return found

    # 退化为中文外观描述匹配：物料名/规格作为外观描述的子串即命中。
    # 中文描述通常是一整段（如"红色塑料外壳继电器"），而物料名是其中的短片段（"继电器"），
    # 故用反向子串匹配（description LIKE '%'||name||'%'）。
    from sqlalchemy import func, literal
    return query.filter(db.or_(
        literal(description).like(func.concat('%', Material.name, '%')),
        literal(description).like(func.concat('%', Material.spec, '%')),
    )).limit(5).all()


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
        from app import ANDROID_APK_PATHS, os, send_file, render_template, redirect
        # BUG-2026-08-27-008：此前 APK 文件不在仓库（git 从未提交二进制）、CI 只构建
        # debug 上传 artifact 不落部署机，两个候选路径永远不存在 → abort(404)，
        # 用户点"下载扫码APP"看到裸 404 页，即"下载地址不正确"。
        # 修复为三级兜底：
        # 1. 管理员配置 WMS_ANDROID_APK_URL（内网文件服务器/GitHub Releases）→ 302 跳转；
        apk_url = (os.environ.get('WMS_ANDROID_APK_URL') or '').strip()
        if apk_url:
            return redirect(apk_url)
        # 2. 本地 APK 文件（仓库根 app-release.apk 或构建输出）→ 直接发送；
        apk_path = next((path for path in ANDROID_APK_PATHS if os.path.isfile(path)), None)
        if apk_path:
            return send_file(
                apk_path,
                mimetype='application/vnd.android.package-archive',
                as_attachment=True,
                download_name='wms-mobile-scan.apk'
            )
        # 3. 均无 → 友好说明页（200），含网页版扫码入口与管理员部署指引，不再裸 404。
        return render_template('mobile_app_download_fallback.html'), 200

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
    @_web_or_api_role_required('warehouse')
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
            get_bearer_user,
            get_warehouse_stock_quantities,
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
            resolve_request_warehouse,
            round_to_2_decimals,
            update_location_inventory,
            _create_adjustment_drafts_from_check_scan,
        )
        from pydantic import BaseModel, Field, field_validator
        from routes.print_queue import enqueue_auto_print_job

        # A8：提交参数用 pydantic 输入校验，避免数据类型 BUG / 字段漂移。
        # 仅校验核心必填字段（mode/code）；其余业务字段（quantity/target/
        # receiver/remark 等）仍由下方 data 原样解析，保持行为兼容，
        # 不在此声明以免造成"已校验"的误导。
        class ScanSubmitRequest(BaseModel):
            mode: str = Field(min_length=1)
            code: str = Field(min_length=1)

            @field_validator('mode')
            @classmethod
            def _norm_mode(cls, v):
                v = (v or '').strip()
                if v not in MOBILE_SCAN_MODES:
                    raise ValueError('扫码类型不正确')
                return v

        payload = request.get_json(silent=True) or {}
        data = dict(payload)
        try:
            req = ScanSubmitRequest.model_validate(payload)
        except Exception as exc:
            return jsonify({'status': 'error', 'success': False, 'msg': f'参数校验失败：{exc}'}), 400

        mode = req.mode
        code = req.code
        # BUG-2026-08-13-002：装饰器接受 Web 会话或 Bearer Token 任一，这里解析真实操作人
        actor = current_user if current_user.is_authenticated else get_bearer_user()

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

        # BUG-2026-08-13-002：统一用 actor（Web 会话或 Bearer Token）
        if actor.role not in ('admin', 'warehouse'):
            return jsonify({'status': 'error', 'success': False, 'msg': '当前账号没有仓库操作权限'}), 403

        # INV-AUDIT-003：仓库始终必填（AGENTS.md 规则），库位单独解析
        # 不再用 warehouse 字段同时充当仓库名和库位字符串，避免两者混淆。
        warehouse, wh_error = resolve_request_warehouse(data)
        if wh_error:
            return jsonify({'status': 'error', 'success': False, 'msg': wh_error}), 400
        # 库位字段独立解析：data.location 或 data.location_name
        location = (data.get('location') or data.get('location_name') or '').strip()
        # BUG-2026-08-18-003：手机端传仓库编号（如 WH001）作为 location，
        # 但 add_stock 会把 warehouse 对象转为仓库名写入流水，导致
        # 历史流水 location 不一致（有的写编号、有的写名称）。
        # 规范化：未开启库位管理时，location 统一用仓库名。
        if not location:
            location = (warehouse.name or '').strip()
        elif not location_management_enabled():
            # 关库位管理时 location 应等于仓库名；若客户端传的是仓库编号，
            # 检查是否匹配当前仓库的 code，是则替换为仓库名。
            if (warehouse.code or '').strip() and location == (warehouse.code or '').strip():
                location = (warehouse.name or '').strip()
        # 开启库位管理时 location 必填（AGENTS.md 规则二），未填且无默认库位时拒绝保存
        if mode in ('in', 'out') and location_management_enabled() and location_required_on_save() and not (data.get('location') or data.get('location_name') or '').strip():
            return jsonify({'status': 'error', 'success': False, 'msg': '启用库位管理后，扫码出入库必须填写库位'}), 400
        remark = (data.get('remark') or '').strip()

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
                    warehouse=warehouse.name,
                    location=location,
                    remark=remark or '手机端扫码提交',
                    status='completed',
                    operator_id=actor.id,
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
                ok, error_msg = add_stock(material, quantity, 'in', 'in_order', order.id, f'手机扫码入库 {order.order_no}', warehouse=warehouse)
                if not ok:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库存增加失败'}), 500
                if location_management_enabled():
                    ok, error_msg = update_location_inventory(material, location, quantity, warehouse=warehouse)
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库位库存更新失败'}), 400
                enqueue_auto_print_job(
                    'in_order', order.id, order.warehouse,
                    created_by=actor.id, source_event='scan_submit_in',
                )
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

                # INV-AUDIT-003：优先按仓库级库存校验，避免使用全局 Material.stock
                warehouse_stock_map = get_warehouse_stock_quantities(warehouse)
                current_stock = normalize_stock_quantity(warehouse_stock_map.get(material.id) or 0)
                if not allow_negative_stock() and not is_stock_sufficient(current_stock, quantity):
                    return jsonify({
                        'status': 'error',
                        'success': False,
                        'msg': f'物料 {material.code} 在仓库 [{warehouse.name}] 库存不足，当前仓库库存：{current_stock:.2f}',
                    }), 400
                if location_management_enabled() and location and location_available_stock_control() and not allow_negative_location_stock():
                    location_inventory = LocationInventory.query.filter_by(
                        material_id=material.id,
                        warehouse_id=warehouse.id,
                        location=location,
                    ).first()
                    location_stock = normalize_stock_quantity(location_inventory.quantity if location_inventory else 0)
                    if not is_stock_sufficient(location_stock, quantity):
                        return jsonify({
                            'status': 'error',
                            'success': False,
                            'msg': f'物料 {material.code} 在 {location} 库位库存不足，当前库位库存：{location_stock:.2f}',
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
                    warehouse=warehouse.name,
                    location=location,
                    purpose='手机扫码出库',
                    remark=remark or '手机端扫码提交',
                    status='completed',
                    operator_id=actor.id,
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
                ok, error_msg = deduct_stock(material, quantity, 'out', 'out_order', order.id, f'手机扫码出库 {order.order_no}', warehouse=warehouse)
                if not ok:
                    db.session.rollback()
                    return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库存扣减失败'}), 400
                if location_management_enabled():
                    ok, error_msg = update_location_inventory(material, location, -quantity, warehouse=warehouse)
                    if not ok:
                        db.session.rollback()
                        return jsonify({'status': 'error', 'success': False, 'msg': error_msg or '库位库存扣减失败'}), 400
                enqueue_auto_print_job(
                    'out_order', order.id, order.warehouse,
                    created_by=actor.id, source_event='scan_submit_out',
                )
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
                # INV-AUDIT-003：盘点按仓库级系统库存生成调整草稿，不再使用全局 Material.stock
                warehouse_stock_map = get_warehouse_stock_quantities(warehouse)
                system_stock = normalize_stock_quantity(warehouse_stock_map.get(material.id) or 0)
                check = InventoryCheckScan(
                    check_no=generate_order_no('CS'),
                    date=date.today(),
                    warehouse=warehouse.name,
                    remark=remark or '手机扫码盘点',
                    status='completed',
                    operator_id=actor.id,
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

    # ───────────────────────── 手机扫码出入库草稿制 ─────────────────────────
    # 目标：扫码出入库提交时先生成 status='pending' 草稿，不动库存、不打印；
    # 在手机端"待确认草稿清单"里人工核对确认后，才 add_stock/deduct_stock 动账 +
    # enqueue_auto_print_job 打印。降低手机端误扫/误输直接动库存的风险（A8 用 pydantic）。

    # 批量提交：一次扫码队列生成一张草稿（含多条明细），与"AUDIT 入库单"草稿流程一致
    @app.route('/mobile/api/scan_batch_draft', methods=['POST'])
    @_web_or_api_role_required('warehouse')
    def mobile_scan_batch_draft():
        from typing import Optional
        from pydantic import BaseModel, Field, field_validator
        from app import (InOrder, InOrderItem, Material, OutOrder, OutOrderItem,
                         current_user, date, db, generate_order_no,
                         get_bearer_user, jsonify, location_management_enabled,
                         location_required_on_save, request,
                         resolve_request_warehouse, round_to_2_decimals,
                         parse_float_value)

        class DraftLine(BaseModel):
            material_code: str = Field(min_length=1)
            quantity: float = Field(gt=0)
            price: Optional[float] = None
            location: Optional[str] = None
            target: Optional[str] = None

        class BatchDraftRequest(BaseModel):
            mode: str = 'in'
            lines: list[DraftLine] = Field(min_length=1)
            warehouse: Optional[str] = None
            warehouse_code: Optional[str] = None
            location: Optional[str] = None
            remark: Optional[str] = None

            @field_validator('mode')
            @classmethod
            def _norm_mode(cls, v):
                v = (v or '').strip()
                # FIX: BUG-2026-08-20-009 批量扫码仅支持入库/出库；
                # 盘点(check)等其它模式不应被静默当成入库，直接校验失败
                if v not in ('in', 'out'):
                    raise ValueError('批量扫码仅支持入库/出库模式')
                return v

        payload = request.get_json(silent=True) or {}
        try:
            req = BatchDraftRequest.model_validate(payload)
        except Exception as exc:
            return jsonify({'status': 'error', 'success': False, 'msg': f'参数校验失败：{exc}'}), 400

        # 仓库必填（未传时默认仓库兜底），库位独立解析
        resolve_data = dict(payload)
        if not resolve_data.get('warehouse') and not resolve_data.get('warehouse_code'):
            # 无法从 lines 推断仓库，保持原样由 resolve_request_warehouse 兜底
            pass
        warehouse, wh_error = resolve_request_warehouse(resolve_data)
        if wh_error:
            return jsonify({'status': 'error', 'success': False, 'msg': wh_error}), 400
        # BUG-2026-08-20-011：位置字段与 scan_submit 采用同一套规范化，保持一致。
        # 未开启库位管理时，库位应等于仓库名；若客户端传的是仓库编号，
        # 检查是否匹配当前仓库的 code，是则替换为仓库名。
        location = (req.location or '').strip()
        if not location:
            location = (warehouse.name or '').strip()
        elif not location_management_enabled():
            if (warehouse.code or '').strip() and location == (warehouse.code or '').strip():
                location = (warehouse.name or '').strip()

        # 解析物料
        resolved = []
        for idx, line in enumerate(req.lines, start=1):
            code = (line.material_code or '').strip()
            material = Material.query.filter_by(code=code).first()
            if not material:
                return jsonify({'status': 'error', 'success': False, 'msg': f'第 {idx} 行物料不存在：{code}'}), 404
            resolved.append((material, line))

        actor = current_user if current_user.is_authenticated else get_bearer_user()

        try:
            if req.mode == 'in':
                order = InOrder(
                    order_no=generate_order_no('IN'),
                    date=date.today(),
                    business_type='产品入库',
                    purpose='手机扫码入库（待确认）',
                    warehouse=warehouse.name,
                    location=location,
                    remark=(req.remark or '手机端扫码提交，待确认')[:200],
                    status='pending',  # 草稿：暂不动库存，人工确认后才 add_stock
                    operator_id=actor.id,
                )
                db.session.add(order)
                db.session.flush()
                for material, line in resolved:
                    price = round_to_2_decimals(parse_float_value(line.price, material.price or 0))
                    db.session.add(InOrderItem(
                        in_order_id=order.id,
                        material_id=material.id,
                        quantity=round_to_2_decimals(line.quantity),
                        price=price,
                        amount=round_to_2_decimals(round_to_2_decimals(line.quantity) * price),
                    ))
            else:
                order = OutOrder(
                    order_no=generate_order_no('OU'),
                    date=date.today(),
                    business_type='领料单',
                    warehouse=warehouse.name,
                    location=location,
                    purpose=(req.remark or '手机扫码出库（待确认）')[:200] or '手机扫码出库（待确认）',
                    remark='手机端扫码提交，待确认',
                    status='pending',  # 草稿：人工确认后才 deduct_stock
                    operator_id=actor.id,
                )
                db.session.add(order)
                db.session.flush()
                for material, line in resolved:
                    price = round_to_2_decimals(parse_float_value(line.price, material.price or 0))
                    db.session.add(OutOrderItem(
                        out_order_id=order.id,
                        material_id=material.id,
                        quantity=round_to_2_decimals(line.quantity),
                        price=price,
                        amount=round_to_2_decimals(round_to_2_decimals(line.quantity) * price),
                        remark=(line.target or '').strip() or None,
                    ))
            order.total_amount = sum(item.amount or 0 for item in order.items)
            db.session.commit()
            return jsonify({
                'status': 'success',
                'success': True,
                'msg': f'已生成待确认草稿：{order.order_no}',
                'data': {
                    'order_type': req.mode,
                    'order_id': order.id,
                    'order_no': order.order_no,
                    'item_count': len(resolved),
                },
            })
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Mobile scan batch draft failed')
            return jsonify({'status': 'error', 'success': False, 'msg': '生成草稿失败，请稍后重试'}), 500

    # 确认草稿：仅 status='pending' 且 admin/warehouse 角色可确认，动库存+打印
    @app.route('/mobile/api/scan_draft_confirm/<int:order_id>', methods=['POST'])
    @_web_or_api_role_required('warehouse')
    def mobile_scan_draft_confirm(order_id):
        from typing import Optional
        from pydantic import BaseModel, Field
        from sqlalchemy.orm import selectinload
        from flask import current_app
        from app import (InOrder, InOrderItem, OutOrder, OutOrderItem,
                         add_stock,
                         current_user, db, deduct_stock, get_bearer_user,
                         jsonify, location_management_enabled, normalize_stock_quantity,
                         request, update_location_inventory,
                         _acquire_order_write_lock)

        class ConfirmRequest(BaseModel):
            order_type: str = Field(pattern='^(in|out)$')

        payload = request.get_json(silent=True) or {}
        try:
            c_req = ConfirmRequest.model_validate(payload)
        except Exception as exc:
            return jsonify({'status': 'error', 'success': False, 'msg': f'参数校验失败：{exc}'}), 400

        from routes.print_queue import enqueue_auto_print_job
        actor = current_user if current_user.is_authenticated else get_bearer_user()

        try:
            if c_req.order_type == 'in':
                locked, ok = _acquire_order_write_lock(InOrder, order_id, 'pending', [
                    selectinload(InOrder.items).selectinload(InOrderItem.material),
                ])
                if not ok:
                    return jsonify({'status': 'error', 'success': False, 'msg': '该入库草稿已提交或不存在'}), 400
                order = locked
                if not order.items:
                    return jsonify({'status': 'error', 'success': False, 'msg': '入库草稿没有明细，无法确认'}), 400
                for item in order.items:
                    if item.material:
                        ok, err = add_stock(item.material, item.quantity,
                                            'in', 'in_order', order.id,
                                            f'手机确认入库 {order.order_no}', warehouse=order.warehouse)
                        if not ok:
                            db.session.rollback()
                            return jsonify({'status': 'error', 'success': False, 'msg': err or '库存增加失败'}), 500
                        if location_management_enabled() and (order.location or order.warehouse):
                            loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, item.quantity, warehouse=order.warehouse)
                            if not loc_ok:
                                db.session.rollback()
                                return jsonify({'status': 'error', 'success': False, 'msg': loc_err or '库位库存更新失败'}), 400
                order.status = 'completed'
                enqueue_auto_print_job('in_order', order.id, order.warehouse, created_by=actor.id, source_event='scan_draft_confirm_in')
                db.session.commit()
                order_no = order.order_no
            else:
                locked, ok = _acquire_order_write_lock(OutOrder, order_id, 'pending', [
                    selectinload(OutOrder.items).selectinload(OutOrderItem.material),
                ])
                if not ok:
                    return jsonify({'status': 'error', 'success': False, 'msg': '该出库草稿已提交或不存在'}), 400
                order = locked
                if not order.items:
                    return jsonify({'status': 'error', 'success': False, 'msg': '出库草稿没有明细，无法确认'}), 400
                for item in order.items:
                    if item.material:
                        ok, err = deduct_stock(item.material, item.quantity,
                                               'out', 'out_order', order.id,
                                               f'手机确认出库 {order.order_no}', warehouse=order.warehouse)
                        if not ok:
                            db.session.rollback()
                            return jsonify({'status': 'error', 'success': False, 'msg': err or '库存扣减失败'}), 400
                        if location_management_enabled() and (order.location or order.warehouse):
                            loc_ok, loc_err = update_location_inventory(item.material, order.location or order.warehouse, -item.quantity, warehouse=order.warehouse)
                            if not loc_ok:
                                db.session.rollback()
                                return jsonify({'status': 'error', 'success': False, 'msg': loc_err or '库位库存扣减失败'}), 400
                order.status = 'completed'
                enqueue_auto_print_job('out_order', order.id, order.warehouse, created_by=actor.id, source_event='scan_draft_confirm_out')
                db.session.commit()
                order_no = order.order_no
            return jsonify({'status': 'success', 'success': True, 'msg': f'确认成功：{order_no}', 'data': {'order_no': order_no}})
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Mobile scan draft confirm failed')
            return jsonify({'status': 'error', 'success': False, 'msg': '确认失败，请稍后重试'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/mobile/api/recognize_material', methods=['POST'])
    @_web_or_api_required
    def mobile_recognize_material():
        from flask import current_app
        from app import Material, db, joinedload, jsonify, request
        from app import _ai_call_llm_vision, _ai_llm_configured, _ai_llm_vision_enabled
        if not _ai_llm_configured() or not _ai_llm_vision_enabled():
            return jsonify({'status': 'error', 'success': False, 'msg': '请先在系统设置中启用大模型和图片识别'}), 400

        # 识图限流：按当前用户（web 会话或 Bearer token）限流，每分钟最多 5 次
        from flask_login import current_user
        from app import get_bearer_user
        _user = current_user if current_user.is_authenticated else get_bearer_user()
        rate_key = f'user:{_user.id}' if _user else f"ip:{request.remote_addr or 'unknown'}"
        wait = _recognize_rate_limited(rate_key)
        if wait is not None:
            return jsonify({'status': 'error', 'success': False, 'msg': f'识图过于频繁，请 {wait} 秒后再试'}), 429

        if 'image' not in request.files:
            return jsonify({'status': 'error', 'success': False, 'msg': '请上传图片'}), 400

        file = request.files['image']
        if not file.filename:
            return jsonify({'status': 'error', 'success': False, 'msg': '请选择图片文件'}), 400

        allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_ext:
            return jsonify({'status': 'error', 'success': False, 'msg': '不支持的图片格式'}), 400

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'status': 'error', 'success': False, 'msg': '图片大小不能超过10MB'}), 400

        try:
            import base64
            img_data = base64.b64encode(file.read()).decode('ascii')
            data_url = f'data:image/{ext};base64,{img_data}'

            material_system_prompt = '''你是仓库管理系统里的AI拍照识物助手。用户会上传物料的外包装、物品本身、物品表面标签或物品上的图形logo。

识别渠道（三条都要尽力）：
1. 外包装文字：箱标、唛头、条码旁文字、包装印刷文字等。
2. 物品表面文字/型号：物品上印刷、刻印的型号与厂商文字（如轴承型号 6204、螺纹规格 M8、品牌 SKF）。
3. 图形外观：当没有清晰可读文字时，根据物品的形状、颜色、结构、logo、材质等外观特征推断它是什么物料。

请提取：
1. 物料编码（如有）
2. 物料名称
3. 规格型号
4. 数量（如有）
5. description：无论文字是否可读，都用一句短语描述外观特征（如"深沟球轴承 6204 金属 银色"、"红色塑料外壳继电器"），供无文字时的外观匹配使用。

请在回答末尾追加 JSON 代码块（用 ```json 包裹），格式如下：
```json
{"code": "编码(无则空串)", "name": "名称(无则空串)", "spec": "规格(无则空串)", "quantity": 数量或null, "confidence": 0.8, "description": "外观描述(无则空串)"}
```
如果完全无法识别，code/name/spec/description 留空，confidence 设为 0。'''

            reply, extracted, error = _ai_call_llm_vision(
                '请识别这张图片中的物料，并输出结构化 JSON。',
                [{'data_url': data_url}],
                system_prompt=material_system_prompt,
            )
            if error:
                return jsonify({'status': 'error', 'success': False, 'msg': error}), 500

            matches = []
            if extracted:
                code = (extracted.get('code') or '').strip()
                name = (extracted.get('name') or '').strip()
                spec = (extracted.get('spec') or '').strip()
                description = (extracted.get('description') or '').strip()

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

                # 图形/外观识别回退：前三项文字匹配都失败时，用外观描述中的
                # 型号字母数字（如 6204、M8、SKF）或描述关键词匹配物料库。
                if not matches:
                    matches = _match_material_by_description(description, query)

            return jsonify({
                'status': 'success',
                'success': True,
                'data': {
                    'reply': reply,
                    'extracted': extracted,
                    'matches': [mobile_material_payload(m) for m in matches],
                    'match_count': len(matches),
                },
            })
        except Exception:
            # 记录堆栈但不记录异常字符串，避免大模型 API 响应等敏感信息写入日志
            current_app.logger.exception('拍照识物失败')
            return jsonify({'status': 'error', 'success': False, 'msg': '识别失败，请稍后重试'}), 500

    # pydantic:reason=文件上传（multipart/form-data）路由，非 JSON Body，pydantic 输入模型不适用；音频格式/大小在校验逻辑内手工校验
    @app.route('/mobile/api/asr', methods=['POST'])
    @_web_or_api_required
    def mobile_asr():
        """手机端语音指令：接收音频 -> 调腾讯云一句话识别 -> 返回中文文本。

        音频由 Android 端录音后上传（wav/mp3/m4a 等），短指令（<60s）走
        一句话识别，返回文本供 App 端做关键词指令解析。腾讯云密钥从环境变量读取：
        TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY / TENCENTCLOUD_REGION。
        """
        from flask import current_app, jsonify, request

        secret_id = os.environ.get('TENCENTCLOUD_SECRET_ID', '').strip()
        secret_key = os.environ.get('TENCENTCLOUD_SECRET_KEY', '').strip()
        region = os.environ.get('TENCENTCLOUD_REGION', 'ap-guangzhou').strip()
        if not secret_id or not secret_key:
            return jsonify({
                'status': 'error',
                'success': False,
                'msg': '未配置腾讯云 ASR 密钥（TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY）'
            }), 400

        if 'audio' not in request.files:
            return jsonify({'status': 'error', 'success': False, 'msg': '请上传音频文件'}), 400

        file = request.files['audio']
        if not file.filename:
            return jsonify({'status': 'error', 'success': False, 'msg': '请选择音频文件'}), 400

        allowed_ext = {'wav', 'mp3', 'm4a', 'aac', 'pcm', 'opus', 'spx', 'silk', 'amr', 'flac', 'ogg', 'wma', 'caf'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_ext:
            return jsonify({'status': 'error', 'success': False, 'msg': '不支持的音频格式'}), 400

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > 10 * 1024 * 1024:
            return jsonify({'status': 'error', 'success': False, 'msg': '音频大小不能超过10MB'}), 400

        try:
            from tencent_asr import TencentAsrError, sentence_recognition
            audio_bytes = file.read()
            text = sentence_recognition(
                audio_bytes,
                secret_id=secret_id,
                secret_key=secret_key,
                region=region,
                voice_format=ext,
                eng_service_type='16k_zh',
            )
            return jsonify({'status': 'success', 'success': True, 'text': text})
        except TencentAsrError:
            current_app.logger.exception('腾讯云 ASR 失败')
            return jsonify({'status': 'error', 'success': False, 'msg': '语音识别失败，请稍后重试'}), 502
        except Exception:
            current_app.logger.exception('语音识别失败')
            return jsonify({'status': 'error', 'success': False, 'msg': '语音识别失败，请稍后重试'}), 500

    # ───────────────────────── 物料档案（多图） ─────────────────────────
    # 移动端物料档案：每个物料最多 MAX_MATERIAL_IMAGES 张图片，存于
    # material_image 表（由 db.create_all() 自动创建）。图片保存到
    # static/uploads/material_images/ 子目录，路径存 relative，URL 走 url_for。
    # 认证复用 _web_or_api_required（web 会话或 Bearer token）。

    # no-test:reason=从 mobile_* 路由内联 JS 里抽出的辅助函数，能力由 mobile_material_archive_* 路由测试覆盖
    def _archive_image_payload(img):
        from flask import url_for as _url_for
        return {
            'id': img.id,
            'image': img.image,
            'sort_order': img.sort_order,
            'created_at': img.created_at.strftime('%Y-%m-%d %H:%M:%S') if img.created_at else '',
            'url': _url_for('static', filename=img.image),
        }

    # BUG-2026-08-10-002: material_image 表在 WMS_SKIP_STARTUP_DB_UPGRADE /
    # WMS_NO_DB_TOUCH 场景下不会由 db.create_all() 自动建好。两个专用端点
    # (mobile_material_archive_images / _upload) 历史裸调 MaterialImage.query
    # 一旦缺表直接 500；仅 _archive_material_payload 有 try/except 兜底。
    # 统一抽出 _safe_material_image_count / _list 复用，list 缺表回退 []、
    # count 缺表回退 0，与现有 _archive_material_payload 行为一致。
    def _has_material_image_table():
        from sqlalchemy import inspect as sa_inspect
        from app import db
        try:
            return bool(sa_inspect(db.engine).has_table('material_image'))
        except Exception:
            return False

    # no-test:reason=helper 函数，能力由 _archive_material_payload 已有 T12 + 本次新加 T13/T14 测试覆盖
    def _safe_material_image_count(material_id):
        from app import MaterialImage
        try:
            return MaterialImage.query.filter_by(material_id=material_id).count()
        except Exception:
            if _has_material_image_table():
                raise
            return 0

    # no-test:reason=helper 函数，能力由 mobile_material_archive_images T13 测试覆盖
    def _safe_material_image_list(material_id):
        from app import MaterialImage
        try:
            return (
                MaterialImage.query.filter_by(material_id=material_id)
                .order_by(MaterialImage.sort_order.asc(), MaterialImage.id.asc())
                .all()
            )
        except Exception:
            if _has_material_image_table():
                raise
            return []

    # no-test:reason=helper 函数，能力由 mobile_material_archive_upload T14 测试覆盖
    def _ensure_material_image_table_inline():
        """缺表时尝试用 SQLAlchemy 现场补建（兼容 sqlite/mysql/postgres）。

        启动期 fix_db_columns._ensure_material_image_table 只走 sqlite3；
        运行时本 helper 走 SQLAlchemy __table__.create，跨方言。
        失败返回 False，由调用方决定如何向用户报告。
        """
        from flask import current_app
        if _has_material_image_table():
            return True
        try:
            from app import MaterialImage, db
            MaterialImage.__table__.create(db.engine, checkfirst=True)
            return _has_material_image_table()
        except Exception:
            current_app.logger.warning('移动端 material_image 表补建失败', exc_info=True)
            return False

    # no-test:reason=从 mobile_* 路由内联 JS 里抽出的辅助函数，能力由 mobile_material_archive_* 路由测试覆盖
    def _archive_material_payload(material):
        return {
            'id': material.id,
            'code': material.code or '',
            'name': material.name or '',
            'spec': material.spec or '',
            'unit': material.unit.name if material.unit else '',
            'category': material.category.name if material.category else '',
            'image_count': _safe_material_image_count(material.id),
        }

    @app.route('/mobile/api/material_archive/search')
    @_web_or_api_required
    def mobile_material_archive_search():
        """按关键字搜索物料（编码/名称/规格/品牌），供物料档案定位目标物料。"""
        from flask import jsonify, request
        from app import Material, db
        keyword = (request.args.get('keyword') or '').strip()
        query = Material.query
        if keyword:
            like = f'%{keyword}%'
            query = query.filter(db.or_(
                Material.code.like(like),
                Material.name.like(like),
                Material.spec.like(like),
                Material.brand.like(like),
            ))
        materials = query.order_by(Material.code.asc()).limit(50).all()
        return jsonify({
            'status': 'success',
            'success': True,
            'data': [_archive_material_payload(m) for m in materials],
        })

    @app.route('/mobile/api/material_archive/<int:id>/images')
    @_web_or_api_required
    def mobile_material_archive_images(id):
        """列出某物料的全部档案图片。"""
        from flask import jsonify
        from app import Material, db
        material = db.session.get(Material, id)
        if not material:
            return jsonify({'status': 'error', 'success': False, 'msg': '物料不存在'}), 404
        # BUG-2026-08-10-002: 缺表时回退空列表，避免 500
        images = _safe_material_image_list(id)
        return jsonify({
            'status': 'success',
            'success': True,
            'data': {
                'material': _archive_material_payload(material),
                'images': [_archive_image_payload(img) for img in images],
            },
        })

    # pydantic:reason=文件上传（multipart/form-data）路由，非 JSON Body，pydantic 输入模型不适用；最多 5 张限制在路由内校验
    @app.route('/mobile/api/material_archive/<int:id>/images', methods=['POST'])
    @_web_or_api_role_required('warehouse')
    def mobile_material_archive_upload(id):
        """上传一张物料档案图片，超过 MAX_MATERIAL_IMAGES 拒绝。"""
        from flask import current_app, jsonify, request
        from app import Material, MaterialImage, db, save_upload_image
        material = db.session.get(Material, id)
        if not material:
            return jsonify({'status': 'error', 'success': False, 'msg': '物料不存在'}), 404

        # BUG-2026-08-10-002: 缺表时先尝试用 SQLAlchemy 现场补建（跨方言），
        # 仍失败则明确返回 500 提示用户，避免静默 500。
        if not _has_material_image_table() and not _ensure_material_image_table_inline():
            return jsonify({
                'status': 'error',
                'success': False,
                'msg': '物料档案表未就绪，请稍后重试或联系管理员',
            }), 500

        # BUG-2026-08-10-002: 缺表时回退 0，不阻断首张上传
        current_count = _safe_material_image_count(id)
        if current_count >= MAX_MATERIAL_IMAGES:
            return jsonify({
                'status': 'error',
                'success': False,
                'msg': f'每个物料最多上传 {MAX_MATERIAL_IMAGES} 张图片',
            }), 400

        file = request.files.get('image')
        if not file or not file.filename:
            return jsonify({'status': 'error', 'success': False, 'msg': '请选择要上传的图片'}), 400

        image_path, err = save_upload_image(file, subfolder='material_images')
        if err:
            return jsonify({'status': 'error', 'success': False, 'msg': err}), 400

        img = MaterialImage(material_id=id, image=image_path, sort_order=current_count)
        db.session.add(img)
        try:
            db.session.commit()
            sync_material_primary_image(material)  # 同步 Material.image 主图为首图
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'保存物料档案图片失败: {e}')
            return jsonify({'status': 'error', 'success': False, 'msg': '保存图片失败'}), 500

        return jsonify({'status': 'success', 'success': True, 'data': _archive_image_payload(img)})

    # pydantic:reason=DELETE 无请求体，pydantic 输入模型不适用
    @app.route('/mobile/api/material_archive/images/<int:image_id>', methods=['DELETE'])
    @_web_or_api_role_required('warehouse')
    def mobile_material_archive_delete_image(image_id):
        """删除一张物料档案图片。"""
        from flask import current_app, jsonify
        from app import MaterialImage, db
        img = db.session.get(MaterialImage, image_id)
        if not img:
            return jsonify({'status': 'error', 'success': False, 'msg': '图片不存在'}), 404
        material = img.material
        db.session.delete(img)
        try:
            db.session.commit()
            sync_material_primary_image(material)  # 删除后重新同步主图
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'删除物料档案图片失败: {e}')
            return jsonify({'status': 'error', 'success': False, 'msg': '删除图片失败'}), 500
        return jsonify({'status': 'success', 'success': True, 'msg': '图片已删除'})
