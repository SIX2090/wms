# 备份（backup）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（get_database_file_path / create_sqlite_online_backup 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

from utils import require_role
from backup_catalog import get_backup_settings, get_backup_sources, list_backup_files, resolve_backup_file, verify_backup_integrity

# Repair task: AUDIT-FULL-20261016-001-F08

def _backup_context():
    from app import BACKUP_DIR, get_database_file_path
    return get_backup_sources(BACKUP_DIR), (get_database_file_path(),)


def _registered_backup(filename, source):
    from flask import abort
    sources, protected = _backup_context()
    try:
        return resolve_backup_file(sources, source, filename, protected)
    except ValueError:
        abort(400)
    except OSError:
        abort(404)


# no-test:reason=路由注册辅助函数，能力由 backup_* 各路由测试覆盖
def register_backup_routes(app):
    @app.route('/backup')
    @login_required
    @require_role('admin')
    def backup_page():
        """显示备份列表"""
        from app import (
            datetime,
            format_file_size,
            render_template,
            request,
            url_for,
        )
        search = (request.args.get('search') or '').strip()
        source = (request.args.get('source') or '').strip()
        sources, protected = _backup_context()
        if source and source not in sources:
            from flask import abort
            abort(400)
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        if sort_by not in {'filename', 'created_at', 'size_bytes'}:
            sort_by = 'created_at'
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'
        entries, warnings = list_backup_files(sources, protected)
        backups = [item for item in entries if (not source or item['source'] == source)
                   and (not search or search.lower() in (item['filename'] or '').lower())]
        for item in backups:
            item['size'] = format_file_size(item['size_bytes'] or 0)
            item['url'] = url_for('download_backup', filename=item['filename'], source=item['source'])
            item['verify_url'] = url_for('verify_backup', filename=item['filename'], source=item['source'])
        # 排序键需稳定支持 datetime/int/str 混合类型；
        # 旧实现 `item.get(sort_by) or ''` 在 created_at 为 None 时会退化为 ''，
        # 与 datetime 比较抛 TypeError；这里为 None 字段提供类型一致的默认值。
        _SORT_DEFAULTS = {
            'created_at': datetime.min,
            'size_bytes': 0,
            'filename': '',
        }

        def _backup_sort_key(item):
            value = item.get(sort_by)
            if value is None:
                return _SORT_DEFAULTS.get(sort_by, '')
            return value

        backups.sort(key=_backup_sort_key, reverse=(sort_order == 'desc'))
        return render_template('backup.html', backups=backups, filters={'search': search, 'source': source},
                               sources=sources, backup_settings=get_backup_settings(), warnings=warnings,
                               sort_by=sort_by, sort_order=sort_order)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/backup/create', methods=['POST'])
    @login_required
    @require_role('admin')
    def create_backup():
        """创建数据库备份"""
        from app import (
            BACKUP_DIR,
            api_error,
            create_sqlite_online_backup,
            datetime,
            get_database_file_path,
            jsonify,
            log_operation,
            os,
        )
        try:
            db_path = get_database_file_path()
            if not os.path.exists(db_path):
                return api_error('数据库文件不存在')

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f'wms_backup_{timestamp}.db'
            backup_path = os.path.join(BACKUP_DIR, backup_filename)

            create_sqlite_online_backup(db_path, backup_path)

            log_operation('创建备份', f'备份文件：{backup_filename}', 'backup')

            return jsonify({
                'status': 'success',
                'msg': '备份成功',
                'filename': backup_filename
            })
        except Exception as e:
            return api_error('备份失败，请稍后重试')

    @app.route('/backup/download/<filename>')
    @login_required
    @require_role('admin')
    def download_backup(filename):
        """下载备份文件"""
        from flask import request, send_file
        backup_path = _registered_backup(filename, request.args.get('source', 'manual'))
        return send_file(backup_path, as_attachment=True, download_name=filename)

    @app.route('/backup/verify/<filename>')
    @login_required
    @require_role('admin')
    def verify_backup(filename):
        """显式只读检查，列表加载不扫描整个数据库，不恢复或修改业务数据。"""
        from flask import jsonify, request
        backup_path = _registered_backup(filename, request.args.get('source', 'manual'))
        return jsonify(status='success', **verify_backup_integrity(backup_path))

    @app.route('/backup/delete', methods=['POST'])
    @login_required
    @require_role('admin')
    def delete_backup():
        """删除备份文件"""
        from app import api_error, jsonify, log_operation, request

        class BackupSelection(BaseModel):
            filename: str = Field(min_length=1, max_length=255)
            source: Literal['manual', 'daily', 'update'] = 'manual'

        try:
            payload = request.get_json(silent=True) if request.is_json else dict(request.form)
            selection = BackupSelection.model_validate(payload)
            sources, protected = _backup_context()
            backup_path = resolve_backup_file(sources, selection.source, selection.filename, protected)
            backup_path.unlink()
            log_operation('删除备份', f'备份来源：{selection.source}；文件：{selection.filename}', 'backup')

            return jsonify({'status': 'success', 'msg': '删除成功'})
        except ValidationError:
            return api_error('请选择有效的备份文件和来源')
        except ValueError as error:
            return api_error(str(error))
        except FileNotFoundError:
            return api_error('备份文件不存在')
        except Exception as e:
            return api_error('删除失败，请稍后重试')

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/backup/restore', methods=['POST'])
    @login_required
    @require_role('admin')
    def restore_backup():
        """Disable online database restore in production."""
        from app import jsonify
        return jsonify({'status': 'error', 'msg': '线上系统已禁用页面恢复数据库，请走停机维护流程'}), 403
