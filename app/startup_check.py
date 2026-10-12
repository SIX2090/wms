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


# ==========================================================================
# F3.3：表/列/类型/FK 四维 schema diff（审计 §3.3）
#
# 设计要点：
# - 比对 SQLAlchemy metadata（代码声明）与实物库（inspect 反射）；
# - 表缺失 / 列缺失 / 类型 confidently 不一致 → 硬错误，阻断启动；
# - FK 差异仅警告：SQLite ALTER 无法补外键（auto_migrate 加列本就无 FK），
#   存量库硬阻断会让所有库起不来——FK 维度是「可见性」而非「门禁」；
# - 实物库多出 metadata 没有的表/列（如 alembic_version 等历史遗留）一律忽略；
# - WMS_SCHEMA_CHECK=off 显式关闭（排障逃生门）；WMS_NO_DB_TOUCH 等
#   启动迁移禁用场景由调用方跳过（schema 本就声明不管理）。
# ==========================================================================

_SCHEMA_CHECK_OFF = ('1', 'true', 'yes', 'on', 'off')


def _model_type_family(col_type):
    """模型列类型 → 粗粒度家族。无法确定返回 None（该列跳过类型比对）。"""
    import datetime as _dt
    from decimal import Decimal
    try:
        py = col_type.python_type
    except (NotImplementedError, AttributeError):
        return None
    if py is bool:
        return 'bool'
    if py is int:
        return 'int'
    if py in (float, Decimal):
        return 'float'
    if py is str:
        return 'str'
    if py is _dt.datetime:
        return 'datetime'
    if py is _dt.date:
        return 'date'
    if py is bytes:
        return 'bytes'
    return None


def _reflected_type_family(col_type):
    """反射列类型 → 与模型侧同一套粗粒度家族。未知（NullType 等）返回 None。"""
    import sqlalchemy as sa
    # DateTime 是 Date 的子类，顺序必须 DateTime 在前
    if isinstance(col_type, sa.Boolean):
        return 'bool'
    if isinstance(col_type, sa.Integer):
        return 'int'
    if isinstance(col_type, (sa.Float, sa.Numeric)):
        return 'float'
    if isinstance(col_type, (sa.String, sa.Text)):
        return 'str'
    if isinstance(col_type, sa.DateTime):
        return 'datetime'
    if isinstance(col_type, sa.Date):
        return 'date'
    if isinstance(col_type, sa.LargeBinary):
        return 'bytes'
    return None


def schema_diff(app, db, engine=None):
    """四维 diff，返回 (errors, warnings)。

    errors:   表缺失 / 列缺失 / 类型不一致（人类可读描述列表）
    warnings: FK 缺失等不阻断项
    engine:   可选，指定要反射的目标库引擎（默认 db.engine）；测试/排障用。
    """
    from sqlalchemy import inspect as sa_inspect

    errors: list[str] = []
    warnings: list[str] = []
    with app.app_context():
        inspector = sa_inspect(engine or db.engine)
        actual_tables = set(inspector.get_table_names())
        for table in db.metadata.sorted_tables:
            tname = table.name
            if tname not in actual_tables:
                errors.append(f'缺表: {tname}')
                continue
            actual_cols = {c['name']: c for c in inspector.get_columns(tname)}
            for column in table.columns:
                if column.name not in actual_cols:
                    errors.append(f'缺列: {tname}.{column.name}')
                    continue
                mf = _model_type_family(column.type)
                rf = _reflected_type_family(actual_cols[column.name]['type'])
                if mf and rf and mf != rf:
                    errors.append(
                        f'类型不一致: {tname}.{column.name} '
                        f'模型={column.type} 实物={actual_cols[column.name]["type"]}'
                    )
            # FK 维度（仅警告）
            actual_fks = {
                (tuple(sorted(fk['constrained_columns'])), fk['referred_table'])
                for fk in inspector.get_foreign_keys(tname)
            }
            for fk in table.foreign_keys:
                key = (tuple(sorted([fk.parent.name])), fk.column.table.name)
                if key not in actual_fks:
                    warnings.append(
                        f'缺外键(仅警告): {tname}.{fk.parent.name} -> '
                        f'{fk.column.table.name}.{fk.column.name}'
                    )
    return errors, warnings


def verify_schema_or_raise(app, db, engine=None):
    """启动门禁：schema diff 有硬错误即 RuntimeError（阻断启动）并明示差异。

    WMS_SCHEMA_CHECK=off/1/true 可显式关闭（排障逃生门）。
    engine 可选：指定反射目标库引擎（默认 db.engine），测试/排障用。
    """
    if os.environ.get('WMS_SCHEMA_CHECK', '').strip().lower() in _SCHEMA_CHECK_OFF:
        return 'wms %s schema-check: skipped (WMS_SCHEMA_CHECK)' % version_string()
    errors, warnings = schema_diff(app, db, engine=engine)
    for w in warnings:
        try:
            app.logger.warning('schema-check FK: %s', w)
        except Exception:  # noqa: BLE001
            pass
    if errors:
        detail = '\n  - '.join(errors)
        raise RuntimeError(
            'F3.3 schema-check 失败，启动被拒绝。实物库与代码声明不一致：\n'
            f'  - {detail}\n'
            '排查方向：是否连错了库 / 版本回滚后未处理 schema / '
            '确需跳过可设 WMS_SCHEMA_CHECK=off（仅排障）'
        )
    return 'wms %s schema-check: ok（表/列/类型一致；FK 警告 %d 条）' % (
        version_string(), len(warnings))
