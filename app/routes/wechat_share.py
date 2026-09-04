# 微信分享（wechat_share）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（_wechat_share_* / run_wechat_share_for_today 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 wechat_share_* 各路由测试覆盖
def register_wechat_share_routes(app):
    @app.route('/wechat_share')
    @login_required
    @require_role('admin')
    def wechat_share_page():
        from app import (
            WechatShareLog,
            _wechat_share_default_config,
            _wechat_share_get_helper_health,
            _wechat_share_log_message_summary,
            _wechat_share_log_status_label,
            _wechat_share_log_trigger_label,
            _wechat_share_master_enabled,
            _wechat_share_today_in_orders,
            date,
            format_file_size,
            os,
            render_template,
            request,
        )
        config = _wechat_share_default_config()
        master_enabled = _wechat_share_master_enabled()
        status_filter = (request.args.get('status') or '').strip()
        if status_filter not in {'', 'pending', 'failed', 'sent', 'skipped'}:
            status_filter = ''
        log_limit = request.args.get('limit', 10, type=int)
        if log_limit not in {10, 20, 50}:
            log_limit = 10
        logs_query = WechatShareLog.query
        if status_filter:
            logs_query = logs_query.filter(WechatShareLog.status == status_filter)
        log_total_count = logs_query.count()
        logs = logs_query.order_by(WechatShareLog.created_at.desc()).limit(log_limit).all()
        today_orders = _wechat_share_today_in_orders()
        helper_configured = bool((config.helper_url or '').strip() or os.environ.get('WMS_WECHAT_HELPER_URL', '').strip())
        helper_health = _wechat_share_get_helper_health(config)
        latest_log = next((log for log in logs if log.module_key == 'in_order'), None)
        log_counts = {
            'pending': WechatShareLog.query.filter_by(status='pending').count(),
            'failed': WechatShareLog.query.filter_by(status='failed').count(),
            'sent_today': WechatShareLog.query.filter(
                WechatShareLog.status == 'sent',
                WechatShareLog.share_date == date.today(),
            ).count(),
        }
        return render_template(
            'wechat_share.html',
            share_config=config,
            master_enabled=master_enabled,
            logs=logs,
            today_orders=today_orders,
            today_count=len(today_orders),
            helper_configured=helper_configured,
            helper_health=helper_health,
            latest_log=latest_log,
            log_counts=log_counts,
            log_filters={'status': status_filter, 'limit': log_limit},
            log_total_count=log_total_count,
            status_label=_wechat_share_log_status_label,
            trigger_label=_wechat_share_log_trigger_label,
            message_summary=_wechat_share_log_message_summary,
            format_file_size=format_file_size,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/wechat_share/save', methods=['POST'])
    @login_required
    @require_role('admin')
    def save_wechat_share_config():
        from flask import current_app
        from app import (
            _wechat_share_default_config,
            _wechat_share_helper_url_allowed,
            _wechat_share_time_is_valid,
            api_error,
            datetime,
            db,
            jsonify,
            log_operation,
            request,
            set_system_setting,
        )
        config = _wechat_share_default_config()
        # 总开关（2026-09-04）：一键整体停用微信分享（含定时/立即/手动）
        master_enabled = request.form.get('master_enabled') == '1'
        set_system_setting('wechat_share_enabled', '1' if master_enabled else '0')
        share_time = (request.form.get('share_time') or '15:30').strip()
        if not _wechat_share_time_is_valid(share_time):
            return api_error('分享时间格式不正确，请使用 HH:MM')

        receiver_type = (request.form.get('receiver_type') or 'person').strip()
        if receiver_type not in {'person', 'group'}:
            receiver_type = 'person'

        config.sender_name = (request.form.get('sender_name') or '').strip()
        config.sender_wechat_id = (request.form.get('sender_wechat_id') or '').strip()
        config.receiver_name = (request.form.get('receiver_name') or '').strip()
        config.receiver_wechat_id = (request.form.get('receiver_wechat_id') or '').strip()
        config.receiver_search_key = (request.form.get('receiver_search_key') or '').strip()
        config.receiver_type = receiver_type
        config.share_time = share_time
        config.share_in_order = request.form.get('share_in_order') == '1'
        config.immediate_on_complete = request.form.get('immediate_on_complete') == '1'
        config.enabled = request.form.get('enabled') == '1'
        config.auto_send = request.form.get('auto_send') == '1'
        helper_url = (request.form.get('helper_url') or '').strip() or 'http://127.0.0.1:8765/send'
        # BUG-2026-08-11-008：直推会携带 helper token，仅允许本机回环地址，防止 token 泄露给第三方主机
        if not _wechat_share_helper_url_allowed(helper_url):
            return api_error('发送助手地址仅允许本机回环地址（http://127.0.0.1 或 http://localhost）')
        config.helper_url = helper_url
        config.updated_at = datetime.now()

        if not config.receiver_search_key:
            config.receiver_search_key = config.receiver_name or config.receiver_wechat_id
        if not config.receiver_name and not config.receiver_wechat_id:
            return api_error('请填写接收人名称或接收人微信号')

        try:
            db.session.commit()
            log_operation('保存微信分享设置', f'接收人：{config.receiver_name or config.receiver_wechat_id}，时间：{config.share_time}', 'wechat_share', config.id)
            return jsonify({'status': 'success', 'msg': '微信分享设置已保存'})
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error('保存微信分享设置失败: %s', exc)
            return jsonify({'status': 'error', 'msg': '保存失败，请稍后重试'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/wechat_share/run_now', methods=['POST'])
    @login_required
    @require_role('admin')
    def run_wechat_share_now():
        from flask import current_app
        from app import db, jsonify, log_operation, request, run_wechat_share_for_today
        force = request.form.get('force') == '1'
        try:
            result = run_wechat_share_for_today(trigger_type='manual', force=force)
            log_operation('立即执行微信分享', result.get('msg', ''), 'wechat_share')
            return jsonify(result)
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('立即执行微信分享失败')
            return jsonify({'status': 'error', 'msg': f'执行失败：{exc}'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/wechat_share/log/<int:log_id>/resend', methods=['POST'])
    @login_required
    @require_role('admin')
    def resend_wechat_share_log(log_id):
        from flask import current_app
        from app import (
            WechatShareLog,
            _wechat_share_default_config,
            _wechat_share_output_dir,
            _wechat_share_send_image,
            datetime,
            db,
            jsonify,
            log_operation,
            os,
            request,
        )
        log = WechatShareLog.query.get_or_404(log_id)
        config = log.config or _wechat_share_default_config()
        if log.module_key != 'in_order':
            return jsonify({'status': 'error', 'msg': '当前只支持重发入库单分享记录'}), 400
        if not log.image_path:
            return jsonify({'status': 'error', 'msg': '该记录没有可重发的图片'}), 400
        base_dir = os.path.abspath(_wechat_share_output_dir())
        image_path = os.path.abspath(log.image_path)
        if not image_path.startswith(base_dir + os.sep) or not os.path.exists(image_path):
            return jsonify({'status': 'error', 'msg': '分享图片不存在，请重新生成今日图片'}), 404

        try:
            # BUG-2026-08-11-014：重发冻结使用日志记录的历史接收人。
            # 列表"接收人"列展示的是分享时冻结的 receiver，若重发改用当前配置
            # 接收人，实际收件人与页面展示不一致（配置中途修改后会发错人）。
            import types as _types
            frozen_name = (log.receiver_name or '').strip()
            frozen_id = (log.receiver_wechat_id or '').strip()
            send_config = config
            used_frozen_receiver = False
            if frozen_name or frozen_id:
                send_config = _types.SimpleNamespace(
                    helper_url=config.helper_url,
                    sender_name=config.sender_name,
                    sender_wechat_id=config.sender_wechat_id,
                    receiver_name=frozen_name or config.receiver_name,
                    receiver_wechat_id=frozen_id or config.receiver_wechat_id,
                    receiver_search_key=frozen_name or frozen_id,
                    receiver_type=config.receiver_type,
                    auto_send=config.auto_send,
                )
                used_frozen_receiver = True
            # BUG-2026-08-11-010：结构化三元组直取状态，错误码附在 message 便于排查
            status, result_code, message = _wechat_share_send_image(send_config, image_path)
            if used_frozen_receiver:
                message = f'{message}（按历史接收人 {frozen_name or frozen_id} 重发）'
            log.status = status
            if status == 'failed' and result_code not in ('ok', ''):
                message = f'{message}（错误码：{result_code}）'
            log.message = message
            log.trigger_type = 'manual_resend'
            log.receiver_name = config.receiver_name
            log.receiver_wechat_id = config.receiver_wechat_id
            log.sent_at = datetime.now() if status == 'sent' else None
            db.session.commit()
            log_operation('重发微信分享', f'记录：{log.id}，单据：{log.order_no or "-"}，状态：{log.status}', 'wechat_share', log.id)
            return jsonify({'status': 'success', 'msg': message or '已重新提交微信助手', 'log_status': log.status})
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('重发微信分享失败: log_id=%s', log_id)
            return jsonify({'status': 'error', 'msg': f'重发失败：{exc}'}), 500

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/wechat_share/logs/clear', methods=['POST'])
    @login_required
    @require_role('admin')
    def clear_wechat_share_logs():
        from flask import current_app
        from app import (
            WechatShareLog,
            _wechat_share_log_status_label,
            db,
            jsonify,
            log_operation,
            request,
        )
        clear_status = (request.form.get('status') or '').strip()
        if clear_status not in {'failed', 'skipped'}:
            return jsonify({'status': 'error', 'msg': '只能清理失败或跳过的分享记录'}), 400

        try:
            deleted = WechatShareLog.query.filter(WechatShareLog.status == clear_status).delete(synchronize_session=False)
            db.session.commit()
            log_operation('清理微信分享记录', f'状态：{_wechat_share_log_status_label(clear_status)}，数量：{deleted}', 'wechat_share')
            return jsonify({'status': 'success', 'msg': f'已清理 {deleted} 条{_wechat_share_log_status_label(clear_status)}记录', 'deleted': deleted})
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('清理微信分享记录失败: status=%s', clear_status)
            return jsonify({'status': 'error', 'msg': f'清理失败：{exc}'}), 500

    @app.route('/wechat_share/log/<int:log_id>/image')
    @login_required
    @require_role('admin')
    def download_wechat_share_log_image(log_id):
        from app import (
            WechatShareLog,
            _wechat_share_output_dir,
            abort,
            os,
            send_file,
        )
        log = WechatShareLog.query.get_or_404(log_id)
        if not log.image_path:
            abort(404)
        base_dir = os.path.abspath(_wechat_share_output_dir())
        image_path = os.path.abspath(log.image_path)
        if not image_path.startswith(base_dir + os.sep) or not os.path.exists(image_path):
            abort(404)
        filename = os.path.basename(image_path)
        return send_file(image_path, mimetype='image/png', as_attachment=True, download_name=filename)