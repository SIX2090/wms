# -*- coding: utf-8 -*-
"""启动自检（P0-3 / R3 生效闭环）：版本号、关键配置项、关键迁移状态。

验收：启动日志第一行出现 ``wms vX.Y.Z config-check: ...``。
设计要点：
- 不调用 git 命令（生产 PATH 受限），直接读 .git/HEAD 与 refs 解析短 SHA；
- 只输出配置"状态"，绝不输出 SECRET_KEY、数据库口令等敏感值本体；
- 数据库迁移哨兵在 initialize_database 之后检查（build_db_check_line），
  此前一律报告 pending-init，全新部署不报错。
"""
from __future__ import annotations

import os

from version import __version__

# 关键迁移哨兵：(表, 列 or None)。列=None 表示只要求表存在。
# 选取依据：近三年反复出现"改了没生效"（R3）的迁移点。
_MIGRATION_SENTINELS = (
    ('api_token', None),                    # 移动端 Bearer 令牌表
    ('print_workstation', 'auth_token'),    # PRINT-ROUTING-F01-P3
    ('opening_stock', 'location'),          # BUG-2026-08-16-002
    ('location_inventory', 'warehouse_id'), # 双仓隔离三账之一
)


def git_short_sha():
    """从 .git 元数据解析当前提交短 SHA；非仓库/浅克隆异常时返回 None。"""
    try:
        git_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.git')
        head_file = os.path.join(git_dir, 'HEAD')
        with open(head_file, 'r', encoding='utf-8') as f:
            head = f.read().strip()
        if head.startswith('ref:'):
            ref = head.split(' ', 1)[1].strip()
            ref_file = os.path.join(git_dir, *ref.split('/'))
            if os.path.isfile(ref_file):
                with open(ref_file, 'r', encoding='utf-8') as f:
                    return f.read().strip()[:7]
            packed = os.path.join(git_dir, 'packed-refs')
            if os.path.isfile(packed):
                with open(packed, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.rstrip().endswith(' ' + ref):
                            return line.split(' ', 1)[0].strip()[:7]
            return None
        # detached HEAD：HEAD 内容即完整 SHA
        return head[:7] if head else None
    except OSError:
        return None


def version_string():
    """wms 版本串：vX.Y.Z（仓库内运行时追加 git 短 SHA）。"""
    sha = git_short_sha()
    return f"v{__version__} ({sha})" if sha else f"v{__version__}"


def _secret_key_source(app):
    """SECRET_KEY 来源（只报来源，不报值）：env / file / ephemeral。"""
    if os.environ.get('SECRET_KEY'):
        return 'env'
    key_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'secret_key')
    if app.config.get('SECRET_KEY') and os.path.isfile(key_file):
        return 'file'
    return 'ephemeral!'


def _session_cookie_state(app, env_name):
    if app.config.get('SESSION_COOKIE_SECURE'):
        return 'secure'
    if env_name == 'production':
        # 能启动说明已显式放行（validate_production_security_config 硬门禁）
        return 'insecure-explicit-optin!'
    return 'insecure-dev'


def build_config_check_line(app, env_name=None):
    """生成 ``wms vX.Y.Z config-check: ...`` 启动自检行（不含敏感值）。"""
    env_name = env_name or os.environ.get('FLASK_ENV', 'production')
    db_uri = str(app.config.get('SQLALCHEMY_DATABASE_URI') or '')
    parts = [
        f"env={env_name}",
        f"session_cookie={_session_cookie_state(app, env_name)}",
        f"csrf={'on' if app.config.get('WTF_CSRF_ENABLED', True) else 'OFF!'}",
        f"secret_key={_secret_key_source(app)}",
        f"db={db_uri.split(':', 1)[0] or 'unknown'}",
        "migrate=pending-init",
    ]
    return f"wms {version_string()} config-check: " + '; '.join(parts)


def build_db_check_line(app, db):
    """生成 ``wms vX.Y.Z db-check: ...`` 迁移哨兵状态行（initialize_database 后调用）。"""
    try:
        from sqlalchemy import inspect as sa_inspect
        with app.app_context():
            inspector = sa_inspect(db.engine)
            tables = set(inspector.get_table_names())
            missing = []
            for table, column in _MIGRATION_SENTINELS:
                if table not in tables:
                    missing.append(f"{table}(table)")
                    continue
                if column is not None:
                    cols = {c['name'] for c in inspector.get_columns(table)}
                    if column not in cols:
                        missing.append(f"{table}.{column}")
        status = 'ok' if not missing else 'missing: ' + ','.join(missing)
    except Exception as e:  # noqa: BLE001 自检永不阻断启动
        status = f"check-failed: {type(e).__name__}"
    return f"wms {version_string()} db-check: migrate={status}"


def log_startup_self_check(app, db=None, include_db=False):
    """把自检行写入应用日志（logger.info）并返回该行，供控制台 banner 复用。"""
    if include_db and db is not None:
        line = build_db_check_line(app, db)
    else:
        line = build_config_check_line(app)
    try:
        app.logger.info(line)
    except Exception:  # noqa: BLE001 日志失败不影响启动
        pass
    return line
