#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 用户/认证/管理员控制台/操作审计（user_auth）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_user_auth_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 change_own_password、login、
# logout、admin_console、admin_mobile_tokens、revoke_mobile_token、user_list、
# operation_audit_page、add_user、edit_user、edit_my_profile、update_user_status、
# delete_user、reset_user_password 等），与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（User、ApiToken、LoginLog、OperationLog、OperationAudit、
#   AIAcceptanceDailySnapshot、AIAcceptanceEvidencePackage、validate_password_strength、
#   add_login_log、get_request_ip、resolve_redirect_target、account_lock_minutes、
#   max_login_failures、log_operation、api_error、_get_master_list_filters、
#   _apply_master_order、_normalize_user_status、_user_status_label、
#   _has_other_active_admin、DISABLED_USER_STATUSES、_audit_date_arg、
#   _audit_datetime_bounds、_audit_risk_condition、_audit_iter_pages 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_user_auth_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, session, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 user_auth_* 各路由测试覆盖
def register_user_auth_routes(app):
    # 装饰器 role_required 为 app.py 内部定义（utils 仅提供 require_role），
    # 需在函数定义期（注册期）可用，故在 register 内延迟导入，避免 app.py 模块加载期触发循环导入。
    from app import role_required

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/change_password', methods=['GET', 'POST'])
    @login_required
    def change_own_password():
        from flask_login import current_user
        from werkzeug.security import check_password_hash, generate_password_hash
        from app import validate_password_strength
        if request.method == 'GET':
            return render_template('change_password.html')
        current_password = request.form.get('current_password') or ''
        new_password = request.form.get('new_password') or ''
        confirm_password = request.form.get('confirm_password') or ''
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({'status': 'error', 'msg': '当前密码不正确'}), 400
        if new_password != confirm_password:
            return jsonify({'status': 'error', 'msg': '两次输入的新密码不一致'}), 400
        valid, message = validate_password_strength(new_password)
        if not valid:
            return jsonify({'status': 'error', 'msg': message}), 400
        if new_password == current_password:
            return jsonify({'status': 'error', 'msg': '新密码不能与当前密码相同'}), 400
        try:
            current_user.password_hash = generate_password_hash(new_password)
            current_user.must_change_password = False
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error('用户修改密码失败: %s', e)
            return jsonify({'status': 'error', 'msg': '密码修改失败，请稍后重试'}), 500
        return jsonify({'status': 'success', 'msg': '密码修改成功', 'redirect': url_for('index')})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/login', methods=['GET', 'POST'])
    # AI_TASK: AI-LOGIN-F01
    def login():
        from datetime import date, datetime
        from flask_login import current_user, login_user
        from werkzeug.security import check_password_hash
        from app import (User, add_login_log, get_request_ip, resolve_redirect_target,
                         account_lock_minutes, max_login_failures)
        next_page = (request.values.get('next') or '').strip()
        login_date = date.today().strftime('%Y-%m-%d')
        # BUG-2026-07-28-011 修复：把锁定/失败相关上下文统一封装，默认空，避免每个分支重复
        login_ctx = {
            'next': next_page,
            'current_date': login_date,
            'locked': False,
            'lock_remaining_seconds': 0,
            'lock_remaining_minutes': 0,
            'ip_failed_count': 0,
            'remaining_attempts': 0,
        }

        if current_user.is_authenticated:
            return redirect(resolve_redirect_target(next_page))

        if request.method != 'POST':
            # BUG-2026-07-29-010: GET /login 显式探测 admin 用户锁定状态，
            # 把倒计时秒数传给模板（lockHint + JS 倒计时），避免锁定后用户看不到提示
            try:
                from datetime import datetime as _dt
                locked_admin = User.query.filter_by(username='admin').first()
                if locked_admin and locked_admin.locked_until and locked_admin.locked_until > _dt.now():
                    remaining = int((locked_admin.locked_until - _dt.now()).total_seconds())
                    if remaining > 0:
                        login_ctx.update({
                            'locked': True,
                            'lock_remaining_minutes': remaining // 60,
                            'lock_remaining_seconds': remaining,
                            'username': 'admin',
                        })
                elif locked_admin and locked_admin.login_ip_locked_until and locked_admin.login_ip_locked_until > _dt.now():
                    # IP 维度锁定
                    remaining = int((locked_admin.login_ip_locked_until - _dt.now()).total_seconds())
                    if remaining > 0:
                        login_ctx.update({
                            'locked': True,
                            'lock_remaining_minutes': remaining // 60,
                            'lock_remaining_seconds': remaining,
                            'username': 'admin',
                        })
            except Exception as _e:
                app.logger.warning('探测 admin 锁定状态失败: %s', _e)
            return render_template('login.html', **login_ctx)

        username = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        usage_consent = request.form.get('usage_consent') == '1'
        login_mode = request.form.get('login_mode', 'user')
        if login_mode not in {'user', 'admin'}:
            login_mode = 'user'

        if not username or not password:
            flash('请输入用户名和密码', 'danger')
            return render_template('login.html', **login_ctx), 400
        if len(username) > 80 or len(password) > 128:
            flash('用户名或密码长度不正确', 'danger')
            return render_template('login.html', **login_ctx), 400
        # BUG-2026-07-31-001 修复：usage_consent 之前是"未勾就 400"的硬阻断，
        # 但 HTML 模板硬编码了 checked，部分浏览器/扩展/隐身模式会把 checkbox 内部状态
        # 清成 unchecked，导致 POST 时 usage_consent 缺失 → 后端 400 → flash「请先阅读
        # 并同意使用本系统」→ HTML 仍渲染为 checked → 用户无法再勾选 → 死循环。
        # 修复：usage_consent 仅做审计/合规记录，不再阻断登录。
        if not usage_consent:
            app.logger.info('登录时未勾选 usage_consent（不阻断），username=%s', username)

        user = User.query.filter_by(username=username).first()
        if not user:
            add_login_log(status='failed', username=username, fail_reason='failed')
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
            flash('用户名或密码错误', 'danger')
            return render_template('login.html', **login_ctx), 401

        if not user.is_active:
            add_login_log(status='failed', username=username, user=user, fail_reason='failed')
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
            flash('账号已被禁用，请联系管理员', 'danger')
            return render_template('login.html', **login_ctx), 403

        if login_mode == 'admin' and user.role != 'admin':
            add_login_log(status='failed', username=username, user=user, fail_reason='admin_mode_role_mismatch')
            db.session.commit()
            flash('管理员模式仅允许管理员账号登录', 'danger')
            return render_template('login.html', **login_ctx), 403

        request_ip = get_request_ip()
        if user.is_locked_for(request_ip):
            remaining_min = user.login_lock_remaining(request_ip)
            remaining_sec = user.login_lock_remaining_seconds(request_ip)
            # BUG-2026-07-28-011 修复：锁定时向模板传精确剩余秒数，前端做倒计时
            login_ctx.update({
                'locked': True,
                'lock_remaining_minutes': remaining_min,
                'lock_remaining_seconds': remaining_sec,
                'ip_failed_count': user.ip_failed_count_for(request_ip),
                'username': username,
            })
            add_login_log(
                status='failed',
                username=username,
                user=user,
                fail_reason=f'{remaining_min}'
            )
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
            flash(f'账号已锁定，请 {remaining_min} 分钟后再试', 'danger')
            return render_template('login.html', **login_ctx), 423

        if check_password_hash(user.password_hash, password):
            session.clear()
            login_user(user)
            session.permanent = True
            session['login_at'] = datetime.now().isoformat()
            user.last_login_at = datetime.now()
            user.last_login_ip = get_request_ip()
            user.reset_failed_count()
            add_login_log(status='success', username=username, user=user)
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'数据库操作失败: {e}')
                return jsonify({'status': 'error', 'msg': '操作失败'}), 500
            if user.must_change_password:
                return redirect(url_for('change_own_password'))
            if login_mode == 'admin' and not next_page:
                return redirect(url_for('admin_console'))
            return redirect(resolve_redirect_target(next_page))

        user.increment_failed_count(request_ip)
        fail_reason = ''
        if user.is_locked_for(request_ip):
            fail_reason = f'{account_lock_minutes()}'
        add_login_log(status='failed', username=username, user=user, fail_reason=fail_reason)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'数据库操作失败: {e}')

        if user.is_locked_for(request_ip):
            remaining_min = user.login_lock_remaining(request_ip)
            remaining_sec = user.login_lock_remaining_seconds(request_ip)
            # BUG-2026-07-28-011 修复：本轮失败刚好触发锁定，立即进入锁定 UI
            login_ctx.update({
                'locked': True,
                'lock_remaining_minutes': remaining_min,
                'lock_remaining_seconds': remaining_sec,
                'ip_failed_count': user.ip_failed_count_for(request_ip),
                'username': username,
            })
            flash(f'密码错误次数过多，账号已锁定 {account_lock_minutes()} 分钟', 'danger')
            return render_template('login.html', **login_ctx), 423

        remaining = max(0, max_login_failures() - (user.login_failed_count or 0))
        ip_failed = user.ip_failed_count_for(request_ip)
        # BUG-2026-07-28-011 修复：未锁定时向模板传剩余尝试次数 + IP 失败次数
        login_ctx.update({
            'remaining_attempts': remaining,
            'ip_failed_count': ip_failed,
            'username': username,
        })
        flash(f'用户名或密码错误，还可尝试 {remaining} 次', 'danger')
        return render_template('login.html', **login_ctx), 401

    @app.route('/logout')
    @login_required
    def logout():
        from flask_login import logout_user
        logout_user()
        session.clear()
        return redirect(url_for('login'))

    @app.route('/admin/console')
    @login_required
    @role_required('admin')
    def admin_console():
        from datetime import date, datetime, time
        from app import (User, LoginLog, AIAcceptanceDailySnapshot, AIAcceptanceEvidencePackage)
        # 管理员统一工作台：只聚合管理入口，不绕过既有权限页面。
        today_start = datetime.combine(date.today(), time.min)
        return render_template(
            'admin_console.html',
            active_users=User.query.filter_by(status='normal').count(),
            total_users=User.query.count(),
            today_logins=LoginLog.query.filter(LoginLog.login_time >= today_start).count(),
            acceptance_snapshots=AIAcceptanceDailySnapshot.query.count(),
            evidence_packages=AIAcceptanceEvidencePackage.query.count(),
        )

    @app.route('/admin/mobile_tokens')
    @login_required
    @role_required('admin')
    def admin_mobile_tokens():
        from datetime import datetime
        from app import ApiToken, User
        tokens = ApiToken.query.join(User).order_by(ApiToken.created_at.desc()).limit(200).all()
        return render_template('admin_mobile_tokens.html', tokens=tokens, now=datetime.now())

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/admin/mobile_tokens/<int:token_id>/revoke', methods=['POST'])
    @login_required
    @role_required('admin')
    def revoke_mobile_token(token_id):
        from app import ApiToken, log_operation
        token = db.session.get(ApiToken, token_id)
        if not token:
            flash('移动 Token 不存在', 'warning')
            return redirect(url_for('admin_mobile_tokens'))
        if not token.revoked:
            token.revoked = True
            db.session.commit()
            log_operation('撤销移动 Token', f'用户：{token.user.username if token.user else token.user_id}', 'api_token', token.id)
            flash('移动 Token 已撤销', 'success')
        return redirect(url_for('admin_mobile_tokens'))

    @app.route('/user')
    @login_required
    @role_required('admin')
    def user_list():
        from app import User, _get_master_list_filters, _apply_master_order
        search, status_filter, sort_by, sort_order = _get_master_list_filters('created_at')
        role_filter = (request.args.get('role') or '').strip()
        allowed_roles = {'admin', 'warehouse', 'purchase', 'sales', 'production', 'user'}
        allowed_statuses = {'normal', 'disabled', 'inactive'}
        if role_filter not in allowed_roles:
            role_filter = ''
        if status_filter not in allowed_statuses:
            status_filter = ''

        query = User.query
        if search:
            search_like = f'%{search}%'
            role_terms = {
                '管理员': 'admin',
                '仓管员': 'warehouse',
                '仓管': 'warehouse',
                '采购': 'purchase',
                '生产': 'production',
                '普通用户': 'user',
                '普通': 'user',
            }
            status_terms = {
                '正常': 'normal',
                '启用': 'normal',
                '禁用': 'disabled',
                '停用': 'disabled',
                'inactive': 'inactive',
                'disabled': 'disabled',
            }
            role_from_search = role_terms.get(search) or (search if search in allowed_roles else None)
            status_from_search = status_terms.get(search) or (search if search in allowed_statuses else None)
            conditions = [
                User.username.like(search_like),
                User.role.like(search_like),
                User.status.like(search_like),
            ]
            if role_from_search:
                conditions.append(User.role == role_from_search)
            if status_from_search:
                conditions.append(User.status == status_from_search)
            query = query.filter(db.or_(*conditions))
        if role_filter:
            query = query.filter(User.role == role_filter)
        if status_filter:
            query = query.filter(User.status == status_filter)

        allowed_sorts = {'id', 'username', 'role', 'status', 'created_at', 'last_login_at'}
        query, sort_by = _apply_master_order(query, User, sort_by, sort_order, allowed_sorts, 'created_at')
        users = query.all()
        filters = {'search': search, 'status': status_filter, 'role': role_filter}
        return render_template('user.html', users=users, filters=filters, sort_by=sort_by, sort_order=sort_order)

    @app.route('/operation_audit')
    @login_required
    @role_required('admin')
    def operation_audit_page():
        from datetime import date, datetime, time, timedelta
        from sqlalchemy.orm import joinedload
        from app import (OperationLog, OperationAudit, User, LoginLog,
                         _audit_date_arg, _audit_datetime_bounds,
                         _audit_risk_condition, _audit_iter_pages)
        search = (request.args.get('search') or '').strip()
        username = (request.args.get('username') or '').strip()
        operation = (request.args.get('operation') or '').strip()
        target_type = (request.args.get('target_type') or '').strip()
        source = (request.args.get('source') or '').strip()
        risk = (request.args.get('risk') or '').strip()
        date_start = _audit_date_arg('date_start')
        date_end = _audit_date_arg('date_end')
        page = max(1, request.args.get('page', 1, type=int))
        per_page = request.args.get('per_page', 20, type=int)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        if source not in {'operation_log', 'operation_audit'}:
            source = ''
        if risk not in {'1'}:
            risk = ''

        start_dt, end_dt = _audit_datetime_bounds(date_start, date_end)

        log_query = OperationLog.query.options(joinedload(OperationLog.user)).filter(
            OperationLog.created_at >= start_dt,
            OperationLog.created_at < end_dt,
        )
        audit_query = OperationAudit.query.filter(
            OperationAudit.operation_time >= start_dt,
            OperationAudit.operation_time < end_dt,
        )

        if username:
            like = f'%{username}%'
            log_query = log_query.join(User, OperationLog.user_id == User.id, isouter=True).filter(User.username.like(like))
            audit_query = audit_query.filter(OperationAudit.username.like(like))
        if operation:
            like = f'%{operation}%'
            log_query = log_query.filter(OperationLog.operation_type.like(like))
            audit_query = audit_query.filter(OperationAudit.operation.like(like))
        if target_type:
            like = f'%{target_type}%'
            log_query = log_query.filter(OperationLog.target_type.like(like))
            audit_query = audit_query.filter(OperationAudit.target_type.like(like))
        if search:
            like = f'%{search}%'
            log_query = log_query.filter(db.or_(
                OperationLog.operation_type.like(like),
                OperationLog.operation_content.like(like),
                OperationLog.target_type.like(like),
                OperationLog.ip_address.like(like),
            ))
            audit_query = audit_query.filter(db.or_(
                OperationAudit.operation.like(like),
                OperationAudit.target_type.like(like),
                OperationAudit.target_name.like(like),
                OperationAudit.username.like(like),
                OperationAudit.reason.like(like),
                OperationAudit.ip_address.like(like),
            ))
        if risk:
            log_query = log_query.filter(_audit_risk_condition(OperationLog, OperationLog.operation_type, [OperationLog.operation_content]))
            audit_query = audit_query.filter(_audit_risk_condition(OperationAudit, OperationAudit.operation, [OperationAudit.target_name, OperationAudit.reason]))

        total_log_count = 0 if source == 'operation_audit' else log_query.count()
        total_audit_count = 0 if source == 'operation_log' else audit_query.count()

        rows = []
        max_fetch = max(500, page * per_page + per_page)
        if source != 'operation_audit':
            for log in log_query.order_by(OperationLog.created_at.desc()).limit(max_fetch).all():
                rows.append({
                    'source': '旧操作日志',
                    'time': log.created_at,
                    'username': log.user.username if log.user else '-',
                    'operation': log.operation_type or '-',
                    'target_type': log.target_type or '-',
                    'target_id': log.target_id,
                    'content': log.operation_content or '',
                    'ip_address': log.ip_address or '-',
                    'status': 'success',
                })
        if source != 'operation_log':
            for audit in audit_query.order_by(OperationAudit.operation_time.desc()).limit(max_fetch).all():
                details = audit.reason or audit.target_name or ''
                if audit.old_data or audit.new_data:
                    details = (details + '；' if details else '') + '包含变更前后数据'
                rows.append({
                    'source': '变更审计',
                    'time': audit.operation_time,
                    'username': audit.username or '-',
                    'operation': audit.operation or '-',
                    'target_type': audit.target_type or '-',
                    'target_id': audit.target_id,
                    'content': details,
                    'ip_address': audit.ip_address or '-',
                    'status': audit.status or '-',
                })

        rows.sort(key=lambda item: item['time'] or datetime.min, reverse=True)
        total = total_log_count + total_audit_count
        pages = (total + per_page - 1) // per_page if total else 0
        start = (page - 1) * per_page
        audit_rows = rows[start:start + per_page]

        risk_log_count = OperationLog.query.filter(
            OperationLog.created_at >= start_dt,
            OperationLog.created_at < end_dt,
            _audit_risk_condition(OperationLog, OperationLog.operation_type, [OperationLog.operation_content]),
        ).count()
        risk_audit_count = OperationAudit.query.filter(
            OperationAudit.operation_time >= start_dt,
            OperationAudit.operation_time < end_dt,
            _audit_risk_condition(OperationAudit, OperationAudit.operation, [OperationAudit.target_name, OperationAudit.reason]),
        ).count()
        failed_login_count = LoginLog.query.filter(
            LoginLog.login_time >= start_dt,
            LoginLog.login_time < end_dt,
            LoginLog.status == 'failed',
        ).count()

        pagination = {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': pages,
            'has_prev': page > 1,
            'has_next': pages > page,
            'prev_num': page - 1,
            'next_num': page + 1,
            'iter_pages': lambda: _audit_iter_pages(page, pages),
        }
        filters = {
            'search': search,
            'username': username,
            'operation': operation,
            'target_type': target_type,
            'source': source,
            'risk': risk,
            'date_start': date_start,
            'date_end': date_end,
        }
        stats = {
            'total': total,
            'operation_log': total_log_count,
            'operation_audit': total_audit_count,
            'risk': risk_log_count + risk_audit_count,
            'failed_login': failed_login_count,
        }
        return render_template(
            'operation_audit.html',
            rows=audit_rows,
            pagination=pagination,
            filters=filters,
            stats=stats,
            per_page=per_page,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/add', methods=['POST'])
    @require_role('admin')
    @login_required
    @role_required('admin')
    def add_user():
        from datetime import datetime
        from werkzeug.security import generate_password_hash
        from app import User, api_error, validate_password_strength
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = (request.form.get('role', 'user') or 'user').strip()
        allowed_roles = {'admin', 'warehouse', 'purchase', 'sales', 'production', 'user', 'viewer'}
        if role not in allowed_roles:
            return api_error('用户角色不合法')
        if len(username) > 80:
            return jsonify({'status': 'error', 'msg': '用户名不能超过 80 个字符'}), 400
        if len(password) > 128:
            return jsonify({'status': 'error', 'msg': '密码不能超过 128 个字符'}), 400
        if not username or not password:
            return api_error('请输入用户名和密码')
        if User.query.filter_by(username=username).first():
            return api_error('用户名已存在')
        # Password
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            return api_error(error_msg)
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            status='normal',
            created_at=datetime.now()
        )
        db.session.add(user)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'创建用户失败: {e}')
            return jsonify({'status': 'error', 'msg': '用户创建失败，用户名可能已存在'}), 500
        return jsonify({'status': 'success', 'msg': '用户创建成功'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/<int:user_id>/edit', methods=['POST'])
    @require_role('admin')
    @login_required
    @role_required('admin')
    def edit_user(user_id):
        from flask_login import current_user
        from app import (User, DISABLED_USER_STATUSES, _normalize_user_status,
                         _has_other_active_admin, log_operation)
        # Edit non-password user profile fields with last-admin protection.
        target = db.session.get(User, user_id)
        if not target:
            return jsonify({'status': 'error', 'msg': '用户不存在'}), 404
        username = (request.form.get('username') or '').strip()
        role = (request.form.get('role') or '').strip()
        status = _normalize_user_status(request.form.get('status'))
        allowed_roles = {'admin', 'warehouse', 'purchase', 'sales', 'production', 'user', 'viewer'}
        if not username or len(username) > 80:
            return jsonify({'status': 'error', 'msg': '用户名不能为空且不能超过 80 个字符'}), 400
        if role not in allowed_roles:
            return jsonify({'status': 'error', 'msg': '用户角色不合法'}), 400
        duplicate = User.query.filter(User.username == username, User.id != target.id).first()
        if duplicate:
            return jsonify({'status': 'error', 'msg': '用户名已存在'}), 409
        removing_active_admin = target.role == 'admin' and (role != 'admin' or status in DISABLED_USER_STATUSES)
        if removing_active_admin and not _has_other_active_admin(target.id):
            return jsonify({'status': 'error', 'msg': '至少保留一个启用状态的管理员'}), 400
        if target.id == current_user.id and (role != 'admin' or status in DISABLED_USER_STATUSES):
            return jsonify({'status': 'error', 'msg': '不能降级或禁用当前登录管理员'}), 400
        before = f'用户名={target.username}，角色={target.role}，状态={_normalize_user_status(target.status)}'
        target.username, target.role, target.status = username, role, status
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app.logger.error('编辑用户失败: %s', exc)
            return jsonify({'status': 'error', 'msg': '用户编辑失败'}), 500
        # BUG-F02-06 修复：审计 log_operation 显式带 last_modified_by=current_user.username
        log_operation(
            '编辑用户',
            f'{before} -> 用户名={username}，角色={role}，状态={status} (last_modified_by={current_user.username})',
            'user', target.id,
        )
        return jsonify({'status': 'success', 'msg': '用户资料已更新'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/profile/edit', methods=['GET', 'POST'])
    @login_required
    def edit_my_profile():
        import re
        from flask_login import current_user
        from app import log_operation
        user = current_user
        if request.method == 'GET':
            return render_template('my_profile.html', profile_user=user)
        email = (request.form.get('email') or '').strip()
        phone = (request.form.get('phone') or '').strip()
        bio = (request.form.get('bio') or '').strip()
        # BUG-F02-06 修复：先校验长度再保存，不允许静默截断
        if len(email) > 200:
            return jsonify({'status': 'error', 'msg': '邮箱不能超过 200 个字符（当前 '+str(len(email))+'）'}), 400
        if len(phone) > 30:
            return jsonify({'status': 'error', 'msg': '电话不能超过 30 个字符（当前 '+str(len(phone))+'）'}), 400
        if len(bio) > 500:
            return jsonify({'status': 'error', 'msg': '个人简介不能超过 500 个字符（当前 '+str(len(bio))+'）'}), 400
        if email and ('@' not in email or len(email) < 3):
            return jsonify({'status': 'error', 'msg': '邮箱格式不正确'}), 400
        if phone and not re.fullmatch(r'^[\d\-\+\s]{0,30}$', phone):
            return jsonify({'status': 'error', 'msg': '电话只能包含数字/-/+/空格'}), 400
        before = f'email={user.email or ""}, phone={user.phone or ""}, bio={user.bio or ""}'
        user.email = email or None
        user.phone = phone or None
        user.bio = bio or None
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            app.logger.error('个人资料保存失败: %s', exc)
            return jsonify({'status': 'error', 'msg': '保存失败，请稍后重试'}), 500
        after = f'email={user.email or ""}, phone={user.phone or ""}, bio={user.bio or ""}'
        log_operation('编辑自己的资料', f'{before} -> {after}', 'user', user.id)
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'success', 'msg': '资料已更新'})
        return redirect(url_for('edit_my_profile'))

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/status', methods=['POST'])
    @require_role('admin')
    @login_required
    @role_required('admin')
    def update_user_status():
        from flask_login import current_user
        from app import (User, DISABLED_USER_STATUSES, _normalize_user_status,
                         _user_status_label, _has_other_active_admin, log_operation, api_error)
        data = request.get_json(silent=True) if request.is_json else request.form
        data = data or {}
        user_id = data.get('user_id') or data.get('id')
        new_status = (data.get('status') or '').strip()

        if new_status not in {'normal', 'disabled'}:
            return api_error('用户状态不正确')
        try:
            user = db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return api_error('用户ID格式错误')
        if not user:
            return api_error('用户不存在')

        if user.id == current_user.id and new_status in DISABLED_USER_STATUSES:
            return api_error('不能禁用当前登录账号')
        if user.role == 'admin' and new_status in DISABLED_USER_STATUSES and not _has_other_active_admin(user.id):
            return api_error('至少保留一个启用状态的管理员')

        old_status = _normalize_user_status(user.status)
        if old_status == new_status:
            return jsonify({'status': 'success', 'msg': f'用户已经是{_user_status_label(new_status)}状态'})

        user.status = new_status
        if new_status == 'normal':
            user.login_failed_count = 0
            user.locked_until = None

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'更新用户状态失败: {e}')
            return jsonify({'status': 'error', 'msg': '用户状态更新失败'}), 500

        action = '启用用户' if new_status == 'normal' else '禁用用户'
        log_operation(action, f'用户：{user.username}，{_user_status_label(old_status)} -> {_user_status_label(new_status)}', 'user', user.id)
        msg = '用户已启用，可以重新登录' if new_status == 'normal' else '用户已禁用，禁用后不能登录'
        return jsonify({'status': 'success', 'msg': msg})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/delete', methods=['POST'])
    @require_role('admin')
    @login_required
    @role_required('admin')
    def delete_user():
        from flask_login import current_user
        from app import (User, OperationLog, DISABLED_USER_STATUSES,
                         _normalize_user_status, log_operation, api_error)
        data = request.get_json(silent=True) or {}
        ids = data.get('ids', [])
        if not ids:
            return api_error('请选择要删除的用户')
        try:
            ids = [int(str(i).strip()) for i in ids if str(i).strip().isdigit()]
        except (ValueError, TypeError):
            return api_error('用户ID格式错误')
        ids = list(dict.fromkeys(ids))
        if current_user.id in ids:
            return api_error('不能删除当前登录账号')
        if not ids:
            return api_error('请选择要删除的用户')
        if ids:
            users_to_delete = User.query.filter(User.id.in_(ids)).all()
            if not users_to_delete:
                return jsonify({'status': 'success', 'msg': '用户不存在或已被删除'})

            active_users = [user.username for user in users_to_delete if _normalize_user_status(user.status) not in DISABLED_USER_STATUSES]
            if active_users:
                preview = '、'.join(active_users[:5])
                more = f' 等 {len(active_users)} 个用户' if len(active_users) > 5 else ''
                return jsonify({'status': 'error', 'msg': f'请先禁用用户后再删除：{preview}{more}'}), 400

            related_logs = OperationLog.query.filter(OperationLog.user_id.in_(ids)).count()
            if related_logs > 0:
                return jsonify({'status': 'error', 'msg': f'选中的用户有 {related_logs} 条操作记录，无法删除。账号已禁用即可阻止登录'}), 400

            deleted_names = [user.username for user in users_to_delete]
            for user in users_to_delete:
                db.session.delete(user)
            try:
                db.session.commit()
                log_operation('删除用户', f'删除用户：{"、".join(deleted_names[:10])}', 'user')
            except Exception as e:
                db.session.rollback()
                app.logger.error(f'删除用户失败: {e}')
                return jsonify({'status': 'error', 'msg': '删除失败，用户可能存在关联数据'}), 500
        return jsonify({'status': 'success', 'msg': '用户删除成功'})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/user/reset_password', methods=['POST'])
    @require_role('admin')
    @login_required
    @role_required('admin')
    def reset_user_password():
        import os
        from flask_login import current_user
        from werkzeug.security import generate_password_hash
        from app import User, api_error, validate_password_strength
        user_id = request.form.get('user_id')
        new_password = request.form.get('new_password', '').strip()
        # BUG-2026-07-28-004 修复：禁止自助重置自己密码；重置 admin 目标必须二次确认
        if not user_id or not new_password:
            return api_error('缺少用户 ID 或新密码')
        # 重置密码必须复用 validate_password_strength，避免管理员重置出弱密码
        # （原先仅校验 6 位长度，与新增用户/修改密码的策略不一致）
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            return api_error(error_msg)
        try:
            user = db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return api_error('用户ID格式错误')
        if not user:
            return api_error('用户不存在')
        # 自助重置自己密码一律拒绝（即使非 admin）
        if user.id == current_user.id:
            return api_error('禁止自助重置当前登录账号的密码，请联系其他管理员')
        # 重置 admin 目标账号必须提供 WMS_BOOTSTRAP_PASSWORD 二次确认
        if user.role == 'admin' or user.username == 'admin':
            bootstrap_pwd = (request.form.get('bootstrap_pwd') or '').strip()
            expected = os.environ.get('WMS_BOOTSTRAP_PASSWORD', 'admin')
            if not bootstrap_pwd or bootstrap_pwd != expected:
                return api_error('重置管理员账号需要输入 WMS_BOOTSTRAP_PASSWORD 二次确认')
        user.password_hash = generate_password_hash(new_password)
        # 强制被重置用户下次登录必须改密
        user.must_change_password = True
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"数据库操作失败: {e}")
            return jsonify({"status": "error", "msg": "操作失败"}), 500
        return jsonify({'status': 'success', 'msg': '密码重置成功，被重置用户下次登录需修改密码'})