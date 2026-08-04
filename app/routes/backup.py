# 备份（backup）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（get_database_file_path / create_sqlite_online_backup 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 backup_* 各路由测试覆盖
def register_backup_routes(app):
    @app.route('/backup')
    @login_required
    @require_role('admin')
    def backup_page():
        """显示备份列表"""
        from app import (
            BACKUP_DIR,
            datetime,
            format_file_size,
            glob,
            os,
            render_template,
            request,
            url_for,
        )
        search = (request.args.get('search') or '').strip()
        sort_by = request.args.get('sort', 'created_at')
        sort_order = request.args.get('order', 'desc')
        if sort_by not in {'filename', 'created_at', 'size_bytes'}:
            sort_by = 'created_at'
        if sort_order not in ('asc', 'desc'):
            sort_order = 'desc'
        backups = []
        if os.path.exists(BACKUP_DIR):
            for f in glob.glob(os.path.join(BACKUP_DIR, '*.db')):
                stat = os.stat(f)
                filename = os.path.basename(f)
                if search and search.lower() not in filename.lower():
                    continue
                backups.append({
                    'id': filename,
                    'filename': filename,
                    'created_at': datetime.fromtimestamp(stat.st_mtime),
                    'size': format_file_size(stat.st_size),
                    'size_bytes': stat.st_size,
                    'url': url_for('download_backup', filename=os.path.basename(f))
                })
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
        return render_template('backup.html', backups=backups, filters={'search': search}, sort_by=sort_by, sort_order=sort_order)

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
        from app import BACKUP_DIR, abort, os, send_file
        # 防止路径穿越攻击
        safe_filename = os.path.basename(filename)
        if safe_filename != filename or '..' in filename:
            abort(400)
        backup_path = os.path.join(BACKUP_DIR, safe_filename)
        if not os.path.exists(backup_path) or not os.path.isfile(backup_path):
            abort(404)
        return send_file(backup_path, as_attachment=True, download_name=safe_filename)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/backup/delete', methods=['POST'])
    @login_required
    @require_role('admin')
    def delete_backup():
        """删除备份文件"""
        from app import BACKUP_DIR, api_error, jsonify, log_operation, os, request
        try:
            filename = request.form.get('filename', '').strip()
            if not filename:
                return api_error('请指定备份文件')

            # 防止路径穿越攻击
            safe_filename = os.path.basename(filename)
            if safe_filename != filename or '..' in filename:
                return api_error('非法文件名')

            backup_path = os.path.join(BACKUP_DIR, safe_filename)
            if not os.path.exists(backup_path) or not os.path.isfile(backup_path):
                return api_error('备份文件不存在')

            os.remove(backup_path)
            log_operation('删除备份', f'备份文件：{safe_filename}', 'backup')

            return jsonify({'status': 'success', 'msg': '删除成功'})
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