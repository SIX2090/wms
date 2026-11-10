"""Read-only release identity and the protected deployment's external-operation policy."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import re
import sys

from flask import current_app, has_app_context, jsonify, request

from services.release_manifest import MANIFEST_NAME, verify_release_manifest

_KEY = 'wms_runtime_status'
PAUSED_MESSAGE = '当前部署已暂停微信发送、设备队列及分享配置修改；请联系管理员安排单独验收。'


def preflight_runtime_identity(application_root):
    """Verify an explicit/packaged manifest before importing WMS or opening its DB."""
    application = Path(application_root).resolve()
    explicit = os.environ.get('WMS_RELEASE_MANIFEST', '').strip()
    path = Path(explicit) if explicit else application.parent / MANIFEST_NAME
    if not explicit and not path.exists():
        return None
    if path.is_symlink():
        raise ValueError('发布清单不能使用符号链接')
    manifest = verify_release_manifest(path.parent,
                                      json.loads(path.read_text(encoding='utf-8-sig')))
    if (path.parent / manifest['application_root']).resolve() != application:
        raise ValueError('发布清单与实际运行的应用目录不一致')
    if manifest['runtime']['python_version'] != sys.version.split()[0]:
        raise ValueError('实际Python版本与发布制品不一致')
    for package in manifest['runtime']['packages']:
        name, version = package['name'], package['version']
        if metadata.version(name) != version:
            raise ValueError('实际依赖与发布制品不一致：' + name)
        if name.lower() in {'certifi', 'pypdf'}:
            loaded = importlib.import_module(name)
            if str(getattr(loaded, '__version__', 'unknown')) != version:
                raise ValueError('实际导入与发布制品不一致：' + name)
    return manifest


def external_operations_paused(app=None):
    """One effective policy for UI, background work and device/share request handlers."""
    if app is None:
        if not has_app_context():
            return False
        app = current_app
    return bool(app.extensions.get(_KEY, {}).get('paused', False))


def initialize_runtime_status(app):
    """Preserve ordinary deployments; recognize sealed recovery launchers as paused."""
    if _KEY in app.extensions:
        return
    manifest = preflight_runtime_identity(app.root_path)
    raw = os.environ.get('WMS_EXTERNAL_OPERATIONS_PAUSED', '').strip().lower()
    if raw not in {'', '0', 'false', 'off', 'no', '1', 'true', 'on', 'yes'}:
        raise ValueError('WMS_EXTERNAL_OPERATIONS_PAUSED必须使用明确布尔值')
    paused = bool(os.environ.get('WMS_RELEASE_STATE_ROOT', '').strip())
    paused = paused or raw in {'1', 'true', 'on', 'yes'}
    paused = paused or bool(manifest and manifest['external_operations_paused'])
    app.extensions[_KEY] = {
        'manifest': manifest, 'paused': paused,
        'checked_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
    }

    @app.context_processor
    def runtime_status_context():  # no-test:reason=运行状态页面及暂停入口实际渲染和浏览器验收覆盖
        return {'runtime_external_paused': external_operations_paused()}

    @app.before_request
    def runtime_pause_guard():  # no-test:reason=暂停副作用路由参数化测试覆盖
        if not external_operations_paused():
            return None
        path = request.path
        device_write = path.startswith(('/print_queue/', '/print_agent/')) and request.method != 'GET'
        queue_claim = path == '/print_queue/next' or bool(re.fullmatch(r'/print_queue/workstations/\d+/next', path))
        # 清理预览是带签名的只读选择，保持放行；两条清理 POST 会删记录/图片并改写领取保护。
        share_write = (path in {'/wechat_share/save', '/wechat_share/run', '/wechat_share/run_now',
                                '/wechat_share/logs/clear', '/wechat_share/logs/cleanup'}
                       or bool(re.fullmatch(r'/wechat_share/log/\d+/resend', path))
                       or request.endpoint in {'save_wechat_share_config', 'run_wechat_share_now',
                                               'resend_wechat_share_log', 'clear_wechat_share_logs',
                                               'cleanup_wechat_share_history'})
        helper = request.endpoint in {'wechat_helper_tasks', 'wechat_helper_task_image',
                                     'wechat_helper_report_task'}
        if device_write or queue_claim or share_write or helper:
            # This dual-channel route validates session CSRF inside its handler.
            # Preserve that check when the deployment guard returns before the handler.
            if (path == '/print_queue/jobs' and 'csrf' in current_app.extensions
                    and not request.headers.get('Authorization')):
                from session_csrf import validate_session_write
                error = validate_session_write()
                if error is not None:
                    return error
            return jsonify(status='error', msg=PAUSED_MESSAGE), 503
        return None


def get_runtime_status():
    """Display safe fields only: no DB URL, filesystem paths, tokens or provider secrets."""
    state = current_app.extensions[_KEY]
    manifest = state['manifest']
    safe = {
        'external_operations_paused': external_operations_paused(),
        'session_cookie_secure': bool(current_app.config.get('SESSION_COOKIE_SECURE')),
        'session_cookie_httponly': bool(current_app.config.get('SESSION_COOKIE_HTTPONLY')),
        'session_cookie_samesite': str(current_app.config.get('SESSION_COOKIE_SAMESITE') or ''),
        'startup_db_maintenance_disabled': os.environ.get('WMS_NO_DB_TOUCH', '').lower() in {'1', 'true', 'yes', 'on'},
    }
    fingerprint = hashlib.sha256(json.dumps(safe, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    result = {'registered': manifest is not None, 'artifact_id': None, 'source_sha': None,
              'ui_sha': None, 'file_count': 0, 'overlay_file_count': 0,
              'python_version': sys.version.split()[0], 'runtime_verified': manifest is not None,
              'dependency_count': 0, 'checked_at': state['checked_at'],
              'config_fingerprint': fingerprint, 'safe_config': safe,
              'external_operations_paused': external_operations_paused()}
    if manifest:
        result.update(artifact_id=manifest['artifact_id'], source_sha=manifest['source_sha'],
            ui_sha=manifest['ui_sha'], file_count=len(manifest['files']),
            dependency_count=len(manifest['runtime']['packages']),
            overlay_file_count=sum(any(row['path'] == base or row['path'].startswith(base + '/')
                                      for base in manifest['overlay_roots']) for row in manifest['files']))
    return result
