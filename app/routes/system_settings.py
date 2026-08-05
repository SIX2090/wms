#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 系统设置（system_settings）域路由。
#
# register-on-app 模式：与销售（sales）域一致，采用「register_system_settings_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（system_settings_page、
# save_system_settings、test_ai_llm_settings、preview_init_business_data、
# execute_init_business_data、system_settings_add_stub、
# system_settings_import_stub、system_settings_export_stub 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / utils / db），不导入 app，避免循环导入。
# - app.py 内部定义（SYSTEM_SETTING_DEFINITIONS、get_grouped_system_settings、
#   get_system_setting、set_system_setting、log_operation、api_error、
#   _ai_llm_configured / _ai_test_llm_vision / _ai_llm_model / _ai_llm_endpoint /
#   _ai_call_llm_intent、_init_business_data_preview_stats、
#   _init_business_data_keep_users_and_settings、OperationAudit、INIT_CONFIRM_PHRASE 等）
#   在各路由函数内延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import json

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 system_settings_* 各路由测试覆盖
def register_system_settings_routes(app):
    @app.route('/system_settings')
    @require_role('admin')
    @login_required
    def system_settings_page():
        from app import get_grouped_system_settings
        return render_template('system_settings.html', setting_groups=get_grouped_system_settings())

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/system_settings/save', methods=['POST'])
    @require_role('admin')
    @login_required
    def save_system_settings():
        from app import (SYSTEM_SETTING_DEFINITIONS, api_error, get_system_setting,
                         log_operation, set_system_setting)
        try:
            changed = []
            for key, definition in SYSTEM_SETTING_DEFINITIONS.items():
                setting_type = definition.get('type', 'text')
                if setting_type == 'bool':
                    value = '1' if request.form.get(key) == '1' else '0'
                elif setting_type == 'int':
                    raw_value = (request.form.get(key) or definition.get('default') or '').strip()
                    try:
                        parsed_value = int(raw_value)
                    except ValueError:
                        return jsonify({'status': 'error', 'msg': f'{definition["label"]} 必须是整数'}), 400
                    min_value = definition.get('min')
                    max_value = definition.get('max')
                    if min_value is not None and parsed_value < int(min_value):
                        return jsonify({'status': 'error', 'msg': f'{definition["label"]} 不能小于 {min_value}'}), 400
                    if max_value is not None and parsed_value > int(max_value):
                        return jsonify({'status': 'error', 'msg': f'{definition["label"]} 不能大于 {max_value}'}), 400
                    value = str(parsed_value)
                elif setting_type == 'select':
                    value = (request.form.get(key) or definition.get('default') or '').strip()
                    allowed_values = {str(option.get('value')) for option in definition.get('options', [])}
                    if value not in allowed_values:
                        return jsonify({'status': 'error', 'msg': f'{definition["label"]} 选项不正确'}), 400
                elif setting_type == 'secret':
                    raw_value = (request.form.get(key) or '').strip()
                    if not raw_value and get_system_setting(key, ''):
                        continue
                    value = raw_value
                else:
                    value = (request.form.get(key) or '').strip()

                current_value = get_system_setting(key, definition.get('default', ''))
                if current_value != value:
                    changed.append(definition['label'])
                setting = set_system_setting(key, value)
                setting.remark = definition.get('remark', '')

            db.session.commit()
            content = '更新参数：' + ('、'.join(changed) if changed else '无变化')
            log_operation('保存系统设置', content, 'system_settings', 0)
            return jsonify({'status': 'success', 'msg': '系统参数已保存'})
        except Exception as exc:
            db.session.rollback()
            app.logger.error(f'保存系统设置失败: {exc}')
            return api_error('保存失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/system_settings/test_ai_llm', methods=['POST'])
    @require_role('admin')
    @login_required
    def test_ai_llm_settings():
        from app import (_ai_call_llm_intent, _ai_llm_configured, _ai_llm_endpoint,
                         _ai_llm_model, _ai_test_llm_vision, log_operation)
        overrides = {
            'ai_llm_enabled': '1' if request.form.get('ai_llm_enabled') == '1' else '0',
            'ai_llm_base_url': (request.form.get('ai_llm_base_url') or '').strip(),
            'ai_llm_model': (request.form.get('ai_llm_model') or '').strip(),
            'ai_llm_vision_enabled': '1' if request.form.get('ai_llm_vision_enabled') == '1' else '0',
            'ai_llm_api_key': (request.form.get('ai_llm_api_key') or '').strip(),
            'ai_llm_timeout_seconds': (request.form.get('ai_llm_timeout_seconds') or '').strip(),
            'ai_llm_max_tokens': (request.form.get('ai_llm_max_tokens') or '').strip(),
        }
        if not _ai_llm_configured(overrides):
            return jsonify({'status': 'error', 'msg': '请先启用大模型并保存 API Key'}), 400

        try:
            test_type = (request.form.get('test_type') or 'text').strip()
            if test_type == 'vision':
                vision_reply, vision_error = _ai_test_llm_vision(overrides)
                if not vision_reply:
                    detail = f' 供应商返回：{vision_error}' if vision_error else ''
                    return jsonify({'status': 'error', 'msg': '已连接大模型，但图片识别测试没有得到有效结果。请确认模型名称支持视觉/图片理解，并且供应商兼容 image_url 消息格式。' + detail}), 502
                log_operation('测试AI图片识别连接', f'模型：{_ai_llm_model(overrides)}，接口：{_ai_llm_endpoint(overrides)}', 'system_settings', 0)
                return jsonify({
                    'status': 'success',
                    'msg': f'图片识别测试成功：{vision_reply[:80]}',
                    'reply': vision_reply,
                })

            intent = _ai_call_llm_intent('查 A001 库存', overrides=overrides)
            if not intent:
                return jsonify({'status': 'error', 'msg': '已请求大模型，但没有得到有效 JSON 意图'}), 502
            log_operation('测试AI大模型连接', f'模型：{_ai_llm_model(overrides)}，接口：{_ai_llm_endpoint(overrides)}', 'system_settings', 0)
            return jsonify({
                'status': 'success',
                'msg': f'连接成功，模型返回意图：{intent.get("intent")}',
                'intent': intent,
            })
        except Exception as exc:
            app.logger.exception('AI大模型连接测试失败')
            return jsonify({'status': 'error', 'msg': f'连接失败：{exc}'}), 500

    @app.route('/system_settings/init_business_data/preview', methods=['GET'])
    @require_role('admin')
    @login_required
    def preview_init_business_data():
        """预览将要清空的记录数。"""
        from app import _init_business_data_preview_stats
        stats = _init_business_data_preview_stats()
        return jsonify({'status': 'success', 'data': stats})

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/system_settings/init_business_data/execute', methods=['POST'])
    @require_role('admin')
    @login_required
    def execute_init_business_data():
        # 多行 docstring 会触发 lint strip_py_comments 行号偏移，导致下方豁免注释检测失效，故用单行注释替代。
        # 必传参数：admin_password=当前管理员密码、confirm_phrase=INIT_CONFIRM_PHRASE、include_master_data='1'/'0'。
        from datetime import datetime
        from werkzeug.security import check_password_hash
        from flask_login import current_user
        from app import (INIT_CONFIRM_PHRASE, OperationAudit,
                         _init_business_data_keep_users_and_settings,
                         _init_business_data_preview_stats)
        try:
            admin_password = (request.form.get('admin_password') or '').strip()
            confirm_phrase = (request.form.get('confirm_phrase') or '').strip()
            include_master_data = request.form.get('include_master_data', '0') == '1'

            if confirm_phrase != INIT_CONFIRM_PHRASE:
                return jsonify({
                    'status': 'error',
                    'msg': f'确认短语不正确，请输入：{INIT_CONFIRM_PHRASE}',
                }), 400

            if not admin_password:
                return jsonify({'status': 'error', 'msg': '请输入当前管理员密码'}), 400

            if not current_user or not current_user.is_authenticated:
                return jsonify({'status': 'error', 'msg': '未登录'}), 401
            if not check_password_hash(current_user.password_hash, admin_password):
                return jsonify({'status': 'error', 'msg': '管理员密码不正确'}), 403

            # 先写入「预览」审计（包含统计），保证 init_business_data_preview 与 done 都在审计里
            stats = _init_business_data_preview_stats()
            preview_audit = OperationAudit(
                user_id=current_user.id,
                username=current_user.username,
                operation='init_business_data_preview',
                target_type='system',
                target_id=0,
                target_name='业务数据初始化预览',
                old_data=json.dumps(stats, ensure_ascii=False, default=str),
                new_data=json.dumps({'include_master_data': include_master_data}, ensure_ascii=False),
                operation_time=datetime.now(),
                ip_address=request.remote_addr,
                user_agent=(request.headers.get('User-Agent') or '')[:500],
                status='success',
                reason=f'确认短语+管理员密码二次校验通过（含主数据：{include_master_data}）',
            )
            db.session.add(preview_audit)
            try:
                db.session.commit()
            except Exception as exc:
                app.logger.error('init preview audit 写入失败: %s', exc)
                db.session.rollback()
                return jsonify({'status': 'error', 'msg': '审计写入失败，请稍后重试'}), 500

            # 核心清理
            try:
                deleted = _init_business_data_keep_users_and_settings(include_master_data=include_master_data)
            except Exception as exc:
                app.logger.exception('init_business_data 核心清理失败')
                db.session.rollback()
                fail_audit = OperationAudit(
                    user_id=current_user.id,
                    username=current_user.username,
                    operation='init_business_data_failed',
                    target_type='system',
                    target_id=0,
                    target_name='业务数据初始化失败',
                    old_data=None,
                    new_data=json.dumps({'error': str(exc)}, ensure_ascii=False),
                    operation_time=datetime.now(),
                    ip_address=request.remote_addr,
                    user_agent=(request.headers.get('User-Agent') or '')[:500],
                    status='failed',
                    reason=str(exc)[:200],
                )
                db.session.add(fail_audit)
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                return jsonify({'status': 'error', 'msg': f'初始化失败：{exc}'}), 500

            # 清理成功后写 done 审计
            done_audit = OperationAudit(
                user_id=current_user.id,
                username=current_user.username,
                operation='init_business_data_done',
                target_type='system',
                target_id=0,
                target_name='业务数据初始化完成',
                old_data=None,
                new_data=json.dumps(deleted, ensure_ascii=False, default=str),
                operation_time=datetime.now(),
                ip_address=request.remote_addr,
                user_agent=(request.headers.get('User-Agent') or '')[:500],
                status='success',
                reason=f'清理成功（含主数据：{include_master_data}）',
            )
            db.session.add(done_audit)

            # 最后清空 OperationAudit 自身（保留本次的 preview+done 两条不会被删，因为本次 commit 时已被排除）
            # 实际上 done 审计在当前事务内，会被下面的 .delete() 影响，所以先 commit，再单独清
            db.session.commit()

            # 清空历史 OperationAudit（清理除刚才两条外的所有记录）
            try:
                keep_ids = [preview_audit.id, done_audit.id]
                OperationAudit.query.filter(~OperationAudit.id.in_(keep_ids)).delete(synchronize_session=False)
                db.session.commit()
            except Exception as exc:
                app.logger.warning('清理 OperationAudit 历史失败: %s', exc)
                db.session.rollback()

            # 不再调用 log_operation(...)：因为 OperationLog 已被本路由清理，重新写一条会破坏「再次 preview logs 全部为 0」约束。
            # 本次 init 的执行记录已通过 OperationAudit(init_business_data_done) 留下审计，可通过审计页查阅。

            return jsonify({
                'status': 'success',
                'msg': '业务数据初始化完成，User / SystemSetting / 当前管理员账号已保留',
                'data': deleted,
            })
        except Exception as exc:
            app.logger.exception('init_business_data 路由异常')
            try:
                db.session.rollback()
            except Exception:
                pass
            return jsonify({'status': 'error', 'msg': f'初始化异常：{exc}'}), 500

    @app.route('/system_settings/add', methods=['GET'])
    @login_required
    @require_role('admin')
    def system_settings_add_stub():
        flash('系统设置项请前往"系统设置"页面维护', 'info')
        return redirect(url_for('system_settings_page'))

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/system_settings/import', methods=['POST'])
    @login_required
    @require_role('admin')
    def system_settings_import_stub():
        return redirect(url_for('batch_import_page', type='system_settings'))

    @app.route('/system_settings/export')
    @login_required
    @require_role('admin')
    def system_settings_export_stub():
        return redirect(url_for('batch_import_page', type='system_settings'))