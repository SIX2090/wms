# 标签模板 + 条码 + 二维码（label + barcode + qrcode）域路由：register-on-app 模式，
# endpoint 名与 app.py 原实现一致。
# 共享辅助函数（_get_master_list_filters / _apply_master_order / _normalize_label_template_layout
# 等）与模型（LabelTemplate / Material）仍留在 app.py，各路由函数内部延迟导入，
# 避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 label_barcode_* 各路由测试覆盖
def register_label_barcode_routes(app):
    @app.route('/label_template')
    @login_required
    def label_template_list():
        from app import (
            LabelTemplate,
            _apply_master_order,
            _get_master_list_filters,
            db,
            render_template,
        )
        search, status_filter, sort_by, sort_order = _get_master_list_filters('created_at')
        if status_filter not in ('default', 'normal'):
            status_filter = ''
        allowed_sorts = {'name', 'width', 'height', 'cols', 'rows', 'is_default', 'created_at', 'updated_at'}
        query = LabelTemplate.query
        if search:
            search_like = f'%{search}%'
            default_terms = {'默认', 'default'}
            normal_terms = {'普通', 'normal', '非默认'}
            conditions = [LabelTemplate.name.like(search_like)]
            search_lower = search.lower()
            if search_lower in default_terms:
                conditions.append(LabelTemplate.is_default.is_(True))
            if search_lower in normal_terms:
                conditions.append(LabelTemplate.is_default.is_(False))
            query = query.filter(db.or_(*conditions))
        if status_filter == 'default':
            query = query.filter(LabelTemplate.is_default.is_(True))
        elif status_filter == 'normal':
            query = query.filter(LabelTemplate.is_default.is_(False))
        query, sort_by = _apply_master_order(query, LabelTemplate, sort_by, sort_order, allowed_sorts, 'created_at')
        if sort_by != 'is_default':
            query = query.order_by(LabelTemplate.is_default.desc())
        templates = query.all()
        return render_template('label_template.html', templates=templates, filters={'search': search, 'status': status_filter}, sort_by=sort_by, sort_order=sort_order)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/label_template/add', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def add_label_template():
        from app import (
            LabelTemplate,
            api_error,
            db,
            jsonify,
            parse_float_value,
            parse_int_value,
            request,
        )
        try:
            name = (request.form.get('name') or '').strip()
            width = parse_float_value(request.form.get('width'), 100)
            height = parse_float_value(request.form.get('height'), 60)
            cols = parse_int_value(request.form.get('cols'), 5, minimum=1, maximum=100)
            rows = parse_int_value(request.form.get('rows'), 6, minimum=1, maximum=100)
            is_default = request.form.get('is_default') == 'on'
            layout = request.form.get('layout', '{}')

            if not name:
                return api_error('请输入模板名称')

            existing = LabelTemplate.query.filter_by(name=name).first()
            if existing:
                return jsonify({'status': 'error', 'msg': '模板名称已存在，请从模板设计页面编辑'}), 409
            if is_default:
                LabelTemplate.query.update({'is_default': False})
            template = LabelTemplate(
                name=name, width=width, height=height,
                cols=cols, rows=rows, is_default=is_default, layout=layout
            )
            db.session.add(template)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500
            return jsonify({'status': 'success'})
        except Exception as e:
            db.session.rollback()
            return api_error('操作失败，请稍后重试')

    @app.route('/label_template/<int:id>')
    @require_role('admin', 'warehouse')  # BUG-F02-08 修复：模板设计页只允许 admin/warehouse 进入
    @login_required
    def label_template_detail(id):
        from app import LabelTemplate, render_template
        template = LabelTemplate.query.get_or_404(id)
        return render_template('label_template_detail.html', template=template)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/label_template/<int:id>/delete', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def delete_label_template(id):
        from app import LabelTemplate, db, jsonify
        template = LabelTemplate.query.get_or_404(id)
        db.session.delete(template)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/label_template/<int:id>/save_layout', methods=['POST'])
    @require_role('admin', 'warehouse')
    @login_required
    def save_label_template_layout(id):
        """BUG-F02-03 修复：标签模板保存布局路由（之前完全缺失，前端误报成功）"""
        from app import (
            LabelTemplate,
            datetime,
            db,
            json,
            jsonify,
            log_operation,
            request,
        )
        template = LabelTemplate.query.get_or_404(id)
        payload = request.get_json(silent=True) or {}
        layout = payload.get('layout')
        if layout is None:
            return jsonify({'status': 'error', 'msg': '布局数据不能为空'}), 400
        if not isinstance(layout, (dict, list)):
            return jsonify({'status': 'error', 'msg': '布局数据格式不正确（必须为对象或数组）'}), 400
        try:
            template.layout = json.dumps(layout, ensure_ascii=False)
            template.updated_at = datetime.now()
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app.logger.error('标签模板布局保存失败: %s', exc)
            return jsonify({'status': 'error', 'msg': '保存失败，请稍后重试'}), 500
        log_operation(
            '更新标签模板布局',
            f'template_id={id}, name={template.name}, keys={list(layout.keys()) if isinstance(layout, dict) else len(layout)}',
            'label_template', id,
        )
        return jsonify({'status': 'success', 'msg': '布局已保存', 'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S') if template.updated_at else ''})

    @app.route('/label_template/<int:id>/preview')
    @login_required
    def preview_label_template(id):
        from app import LabelTemplate, Material, joinedload, render_template
        template = LabelTemplate.query.get_or_404(id)
        materials = Material.query.options(joinedload(Material.unit)).all()
        return render_template('label_preview.html', template=template, materials=materials)

    @app.route('/label_template/<int:id>/print')
    @login_required
    def print_labels(id):
        from app import LabelTemplate, Material, render_template, request
        template = LabelTemplate.query.get_or_404(id)
        material_ids = request.args.get('ids', '').split(',')
        materials = Material.query.filter(Material.id.in_(material_ids)).all() if material_ids and material_ids[0] else []
        all_templates = LabelTemplate.query.all()
        return render_template('print_label.html', template=template, materials=materials, templates=all_templates)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/label_template/<int:id>/set_default', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def set_default_template(id):
        from app import LabelTemplate, db, jsonify
        LabelTemplate.query.update({'is_default': False})
        template = LabelTemplate.query.get_or_404(id)
        template.is_default = True
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success'})

    @app.route('/label_template/api/list')
    @login_required
    def api_label_template_list():
        """获取标签模板列表（JSON API）"""
        from app import LabelTemplate, jsonify
        templates = LabelTemplate.query.order_by(LabelTemplate.is_default.desc(), LabelTemplate.created_at.desc()).all()
        result = []
        for t in templates:
            result.append({
                'id': t.id,
                'name': t.name,
                'width': t.width,
                'height': t.height,
                'cols': t.cols,
                'rows': t.rows,
                'is_default': t.is_default
            })
        return jsonify({'status': 'success', 'templates': result})

    @app.route('/label_template/api/<int:id>/detail')
    @login_required
    def api_label_template_detail(id):
        """获取单个模板详情（包含cells布局数据）"""
        from app import LabelTemplate, _normalize_label_template_layout, jsonify
        template = LabelTemplate.query.get_or_404(id)
        import json as _json
        layout = {}
        if template.layout:
            try:
                layout = _json.loads(template.layout) if isinstance(template.layout, str) else template.layout
            except (ValueError, TypeError):
                # 裸 except 会吞掉 KeyboardInterrupt/SystemExit 等不应被捕获的异常，
                # 这里仅需处理 JSON 解析失败与类型不符的情况
                layout = {}
        layout = _normalize_label_template_layout(layout)
        
        data = {
            'id': template.id,
            'name': template.name,
            'width': template.width,
            'height': template.height,
            'cols': template.cols,
            'rows': template.rows,
            'is_default': template.is_default,
            'layout': layout
        }
        return jsonify({'status': 'success', 'template': data})

    @app.route('/barcode/generate')
    @login_required
    def generate_barcode():
        from app import api_error, io, request, send_file
        code = request.args.get('code', '')
        if not code:
            return api_error('缺少条码内容')
        from reportlab.graphics.barcode import createBarcodeDrawing
        from reportlab.graphics import renderPDF

        drawing = createBarcodeDrawing(
            'Code128',
            value=code,
            barHeight=36,
            barWidth=1.0,
            humanReadable=True,
        )
        output = io.BytesIO(renderPDF.drawToString(drawing))
        output.seek(0)
        return send_file(output, mimetype='application/pdf', download_name=f'{code}.pdf')

    @app.route('/api/barcode/<path:code>')
    def api_barcode_image(code):
        """生成条码图片（PNG格式）"""
        from app import io, jsonify, send_file
        if not code:
            return jsonify({'status': 'error', 'msg': '缺少条码内容'}), 400
        try:
            import barcode
            from barcode.writer import ImageWriter

            Code128 = barcode.get_barcode_class('code128')
            code128 = Code128(code, writer=ImageWriter())
            output = io.BytesIO()
            # BUG-2026-08-22-001：600 DPI 高分辨率输出，避免浏览器/打印机
            # 把低分辨率 PNG 放大到毫米级尺寸时产生模糊灰边
            code128.write(output, {'module_width': 0.33, 'module_height': 15.0, 'font_size': 10, 'text_distance': 5, 'quiet_zone': 2, 'dpi': 600})
            output.seek(0)
            return send_file(output, mimetype='image/png')
        except Exception as e:
            app.logger.error(f'生成条码失败: {e}')
            return jsonify({'status': 'error', 'msg': '生成条码失败'}), 500

    @app.route('/api/qrcode/<path:data>')
    def api_qrcode_image(data):
        """生成二维码图片（PNG格式）
        
        支持查询参数：
        - size: 图片尺寸（像素，默认 200）
        - error_correction: 纠错级别 L/M/Q/H（默认 M）
        - border: 边框宽度（模块数，默认 1）
        """
        from app import io, jsonify, request, send_file
        if not data:
            return jsonify({'status': 'error', 'msg': '缺少二维码内容'}), 400
        try:
            import qrcode

            # 解析参数
            size = request.args.get('size', '200')
            try:
                size = max(100, min(600, int(size)))
            except (ValueError, TypeError):
                size = 200

            ec_level = request.args.get('error_correction', 'M').upper()
            ec_map = {'L': qrcode.constants.ERROR_CORRECT_L,
                      'M': qrcode.constants.ERROR_CORRECT_M,
                      'Q': qrcode.constants.ERROR_CORRECT_Q,
                      'H': qrcode.constants.ERROR_CORRECT_H}
            error_correction = ec_map.get(ec_level, qrcode.constants.ERROR_CORRECT_M)

            border = request.args.get('border', '1')
            try:
                border = max(0, min(4, int(border)))
            except (ValueError, TypeError):
                border = 1

            # 自动适配版本（fit=True 根据数据长度自动选择）
            qr = qrcode.QRCode(version=None, box_size=10, border=border, error_correction=error_correction)
            qr.add_data(data)
            qr.make(fit=True)
            # BUG-2026-08-22-001：二维码禁止 LANCZOS 重采样（灰边导致打印模糊），
            # 改用整数 box_size 让输出尺寸恰好是模块数的整数倍，边缘 100% 锐利
            total_modules = qr.modules_count + border * 2
            qr.box_size = max(4, -(-size // total_modules))  # 向上取整，不小于请求尺寸
            img = qr.make_image(fill_color='black', back_color='white')
            output = io.BytesIO()
            img.save(output, format='PNG')
            output.seek(0)
            return send_file(output, mimetype='image/png')
        except Exception as e:
            app.logger.error(f'生成二维码失败: {e}')
            return jsonify({'status': 'error', 'msg': '生成二维码失败'}), 500
