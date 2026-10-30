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

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 system_settings_* 各路由测试覆盖
def register_system_settings_routes(app):
    @app.route('/system_settings')
    @login_required
    @require_role('admin')
    def system_settings_page():
        from app import get_grouped_system_settings
        from services.business_initialization import initialization_enabled
        return render_template('system_settings.html', setting_groups=get_grouped_system_settings(),
                               init_enabled=initialization_enabled())

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/system_settings/save', methods=['POST'])
    @login_required
    @require_role('admin')
    def save_system_settings():
        from app import (SYSTEM_SETTING_DEFINITIONS, _secret_encrypt, api_error,
                         get_system_setting, location_management_enabled,
                         log_operation, set_system_setting)
        from services.warehouse_stock_service import find_location_ledger_mismatches
        try:
            # F2.10 ①（审计 §1.3）：捕获"开启库位管理"的原值。set_system_setting 会
            # 同步请求级缓存（app.py get_system_setting 的 BUG-2026-08-23-002 缓存），
            # 循环内再读已是新值，故必须在循环前取原值。
            was_location_enabled = location_management_enabled()
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
                    # BUG-2026-08-16-019：API Key 对称加密后再落库，避免明文存储
                    value = _secret_encrypt(raw_value)
                else:
                    value = (request.form.get(key) or '').strip()

                current_value = get_system_setting(key, definition.get('default', ''))
                if current_value != value:
                    changed.append(definition['label'])
                # F2.10 ①（审计 §1.3 高危）：库位管理由「关」→「开」前强制跑三账恒等式。
                # 开启后 get_warehouse_stock_quantities 会切换到读 location_inventory，
                # 若库位账与流水账不一致（历史库位账为空是常态），开启即生产事故：
                # 库存查询/报表/手机端大面积显示 0、出库被拒、存量单据调整/调拨完成失败。
                # 有差异则拒绝开启，并指引用 backfill 工具先回填。
                if (key == 'location_management_enabled' and value == '1'
                        and not was_location_enabled):
                    mismatches = find_location_ledger_mismatches(limit=20)
                    if mismatches:
                        db.session.rollback()
                        sample = '；'.join(
                            f"{m['code'] or m['material_id']}"
                            f"@{m['warehouse_id'] if m['warehouse_id'] is not None else '总账'}"
                            f"(库位账{m['location']}/流水{m['txn']})"
                            for m in mismatches[:5])
                        return jsonify({
                            'status': 'error',
                            'msg': (f'拒绝开启库位管理：库位账与流水账存在 {len(mismatches)} 处'
                                    f'（含更多）不一致，开启后会导致库存查询/出库大面积失效。'
                                    f'请先执行 scripts/backfill_location_inventory.py 回填并对齐'
                                    f'库位账（建议先 --dry-run 核对）后重试。示例：{sample}'),
                        }), 400
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
    @login_required
    @require_role('admin')
    def test_ai_llm_settings():
        from app import (_ai_call_llm_intent, _ai_llm_configured, _ai_llm_endpoint,
                         _ai_llm_model, _ai_test_llm_vision, log_operation)
        overrides = {
            'ai_llm_enabled': '1' if request.form.get('ai_llm_enabled') == '1' else '0',
            'ai_llm_base_url': (request.form.get('ai_llm_base_url') or '').strip(),
            'ai_llm_model': (request.form.get('ai_llm_model') or '').strip(),
            'ai_llm_vision_enabled': '1' if request.form.get('ai_llm_vision_enabled') == '1' else '0',
            'ai_llm_timeout_seconds': (request.form.get('ai_llm_timeout_seconds') or '').strip(),
            'ai_llm_max_tokens': (request.form.get('ai_llm_max_tokens') or '').strip(),
        }
        # API Key 留空表示保留原值，不要覆盖
        api_key = (request.form.get('ai_llm_api_key') or '').strip()
        if api_key:
            overrides['ai_llm_api_key'] = api_key
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
            # SYS-AUDIT-008：不向浏览器暴露原始异常（可能含 API Key/URL）
            return jsonify({'status': 'error', 'msg': '连接失败，请查看服务器日志获取详情'}), 500

    @app.route('/system_settings/init_business_data/preview', methods=['GET'])
    @login_required
    @require_role('admin')
    def preview_init_business_data():
        """预览将要清空的记录数。"""
        from flask_login import current_user
        from services.business_initialization import prepare_preview
        try:
            stats, tokens = prepare_preview(current_user.id)
            return jsonify({'status': 'success', 'data': stats, 'preview_tokens': tokens})
        except Exception:
            app.logger.exception('初始化预览失败')
            return jsonify({'status': 'error', 'msg': '预览失败，已禁止初始化'}), 503

    @app.route('/system_settings/init_business_data/execute', methods=['POST'])
    @login_required
    @require_role('admin')
    def execute_init_business_data():
        from flask_login import current_user
        from pydantic import BaseModel, Field, ValidationError
        from werkzeug.security import check_password_hash
        from app import INIT_CONFIRM_PHRASE
        from services.business_initialization import (
            InitializationRefused, execute_initialization, initialization_enabled)

        if not initialization_enabled():
            return jsonify({'status': 'error', 'msg': '网页初始化未开放；仅允许在明确启用的维护窗口执行'}), 403

        class InitBusinessDataExecuteForm(BaseModel):
            admin_password: str = Field(..., min_length=1)
            confirm_phrase: str = Field(..., min_length=1)
            include_master_data: str = Field('0', pattern='^[01]$')
            preview_token: str = ''

        try:
            req = InitBusinessDataExecuteForm.model_validate(request.form.to_dict())
        except ValidationError:
            # Never echo validation input: it contains the administrator password.
            return jsonify({'status': 'error', 'msg': '参数校验失败，请填写管理员密码和确认短语'}), 400
        if req.confirm_phrase != INIT_CONFIRM_PHRASE:
            return jsonify({'status': 'error', 'msg': '确认短语不正确'}), 400
        if not check_password_hash(current_user.password_hash, req.admin_password):
            return jsonify({'status': 'error', 'msg': '管理员密码不正确'}), 403
        if not req.preview_token:
            return jsonify({'status': 'error', 'msg': '缺少有效初始化预览，请重新打开向导并确认'}), 409
        try:
            deleted, backup = execute_initialization(req.preview_token, req.include_master_data == '1',
                                                     current_user.id, current_user.username)
            return jsonify({'status': 'success', 'msg': '业务数据初始化完成，账号保留，系统参数重置为默认值；初始化前完整备份已校验',
                            'data': deleted, 'backup': backup})
        except InitializationRefused as exc:
            return jsonify({'status': 'error', 'msg': str(exc)}), 409
        except Exception:
            db.session.rollback()
            app.logger.exception('初始化失败，清理事务已回滚')
            return jsonify({'status': 'error', 'msg': '初始化未完成，清理事务已回滚；请核对日志及初始化前备份'}), 503

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