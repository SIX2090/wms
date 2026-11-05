"""每日自动备份调度器（F1.2 / P0-1 / 审计 §5.2）。

把 config.py 中既有的 AUTO_BACKUP_* 死配置接入真实调度：
- AUTO_BACKUP_ENABLED（env，默认 true）：总开关；
- AUTO_BACKUP_TIME（env，默认 '02:00'）：每日备份时刻（HH:MM）；
- BACKUP_RETENTION_DAYS（env，默认 30）：自动备份保留天数，
  只清理本调度器产出的 auto_daily_*.db，绝不动更新前备份等其他文件；
- WMS_BACKUP_DIR（env，默认 C:\\wms_backups）：备份目标目录。
  拍板 #8：本机仅 C 盘，先放独立目录（与安装目录/数据目录隔离，避免误删连带），
  将来接 NAS 时改环境变量即切换，代码不动。

备份复用 sqlite_snapshot 的只读源连接、在线快照、完整性检查及原子发布。
独立命令不加载Flask；失败保留已有快照，执行结果持久化供管理页面核对。
"""
import json
import logging
import os
import stat
import tempfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = r'C:\wms_backups'
AUTO_BACKUP_PREFIX = 'auto_daily_'
DAILY_STATUS_NAME = '.daily-backup-status.json'


def get_backup_dir() -> Path:
    """备份目标目录：WMS_BACKUP_DIR 环境变量优先，默认 C:\\wms_backups。"""
    raw = (os.environ.get('WMS_BACKUP_DIR') or '').strip()
    return Path(raw) if raw else Path(DEFAULT_BACKUP_DIR)


def _parse_hhmm(raw: str) -> tuple[int, int]:
    """解析 'HH:MM'，非法值回退 02:00 并告警（配置笔误不应让备份静默消失）。"""
    try:
        hour_s, minute_s = raw.strip().split(':', 1)
        hour, minute = int(hour_s), int(minute_s)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
        return hour, minute
    except (ValueError, AttributeError):
        logger.warning("AUTO_BACKUP_TIME=%r 非法，回退 02:00", raw)
        return 2, 0


def run_daily_backup(app) -> Path:
    """执行一次在线一致性备份 + 完整性校验 + 到期清理，返回备份文件路径。

    任何失败都抛异常（由调度器 job 包装层记录 logger.exception）——
    备份失败必须可见，绝不能静默跳过。
    """
    # 延迟导入：避免模块加载期循环依赖（app.py 在导入本模块前尚未就绪）。
    from app import get_database_file_path
    return run_backup_for_source(get_database_file_path())


def _read_daily_record():
    path = get_backup_dir() / DAILY_STATUS_NAME
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_size > 8192 or
                getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            return {}
        record = json.loads(path.read_text(encoding='utf-8'))
        return record if isinstance(record, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _write_daily_record(record):
    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.backup-status-', dir=backup_dir)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(record, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, backup_dir / DAILY_STATUS_NAME)
    finally:
        Path(name).unlink(missing_ok=True)


def get_daily_backup_status():
    """Only an execution record proves success; missing/invalid/old records warn."""
    record = _read_daily_record()
    state = record.get('state')
    if state not in {'success', 'failure'}:
        return {'state': 'unknown', 'last_attempt': None, 'last_success': None}
    success = record.get('last_success')
    try:
        if success is not None and not isinstance(success, str):
            raise ValueError('invalid timestamp')
        stamp = datetime.fromisoformat(success) if isinstance(success, str) else None
        if stamp is not None:
            age = (datetime.now().astimezone() - stamp).total_seconds()
            if age < -300:
                raise ValueError('future timestamp')
            if state == 'success' and age > 36 * 3600:
                state = 'stale'
        elif state == 'success':
            state = 'unknown'
    except (ValueError, TypeError, OverflowError):
        state, success = 'unknown', None
    attempt = record.get('last_attempt')
    retention = record.get('retention_days')
    return {'state': state, 'last_attempt': attempt if isinstance(attempt, str) else None,
            'last_success': success, 'retention_days': retention if type(retention) is int and retention > 0 else None}


def run_backup_for_source(source) -> Path:
    """Independent daily runner: no Flask import, shared atomic online snapshot."""
    from sqlite_snapshot import create_snapshot
    source = Path(source).resolve()
    status_path = get_backup_dir() / DAILY_STATUS_NAME
    if source == status_path.resolve() or (source.exists() and status_path.exists() and
                                          os.path.samefile(source, status_path)):
        raise ValueError('源库与备份状态文件冲突，拒绝覆盖')
    previous = get_daily_backup_status()
    backup_dir = get_backup_dir()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    dest = backup_dir / f'{AUTO_BACKUP_PREFIX}{stamp}_inventory.db'
    try:
        create_snapshot(source, dest)
        _cleanup_expired(backup_dir, protected_source=source)
        now = datetime.now().astimezone().isoformat()
        _write_daily_record({'state': 'success', 'last_attempt': now, 'last_success': now,
                             'retention_days': get_retention_days()})
    except Exception:
        try:
            _write_daily_record({'state': 'failure', 'last_attempt': datetime.now().astimezone().isoformat(),
                                 'last_success': previous['last_success'], 'retention_days': get_retention_days()})
        except OSError:
            logger.exception('备份执行状态无法保存，请检查目录权限和磁盘空间')
        raise
    logger.info('每日自动备份完成: %s', dest)
    return dest


def get_retention_days() -> int:
    """Repair task: AUDIT-FULL-20261016-001-F08; one policy for cleanup and display."""
    retention_raw = (os.environ.get('BACKUP_RETENTION_DAYS') or '30').strip()
    try:
        retention_days = max(1, int(retention_raw))
    except ValueError:
        logger.warning('BACKUP_RETENTION_DAYS=%r 非法，回退 30', retention_raw)
        retention_days = 30
    return retention_days


def _cleanup_expired(backup_dir: Path, protected_source=None) -> int:
    """清理超过 BACKUP_RETENTION_DAYS 天的自动备份（只动 auto_daily_*.db）。"""
    retention_days = get_retention_days()
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for f in backup_dir.glob(f'{AUTO_BACKUP_PREFIX}*.db'):
        try:
            if protected_source is not None and os.path.samefile(f, protected_source):
                continue
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        except OSError:
            logger.warning('清理过期备份失败: %s', f, exc_info=True)
    if removed:
        logger.info('清理过期自动备份 %d 个（保留 %d 天）', removed, retention_days)
    return removed


def register_backup_jobs(scheduler, app) -> bool:
    """把每日自动备份注册到既有 BackgroundScheduler（与通知任务共享实例）。

    返回是否实际注册（AUTO_BACKUP_ENABLED=0 时跳过并返回 False）。
    """
    enabled_raw = (os.environ.get('AUTO_BACKUP_ENABLED') or 'true').strip().lower()
    if enabled_raw not in ('true', '1', 'yes'):
        logger.info('AUTO_BACKUP_ENABLED=%r，每日自动备份未启用', enabled_raw)
        return False

    hour, minute = _parse_hhmm(os.environ.get('AUTO_BACKUP_TIME') or '02:00')

    # no-test:reason=调度器闭包，逻辑由 run_daily_backup 测试与 register_backup_jobs 注册断言覆盖
    def daily_backup_job():
        with app.app_context():
            try:
                run_daily_backup(app)
            except Exception:
                app.logger.exception('每日自动备份失败')

    scheduler.add_job(
        daily_backup_job,
        'cron',
        hour=hour,
        minute=minute,
        id='daily_auto_backup',
        replace_existing=True,
        max_instances=1,
    )
    logger.info('每日自动备份已注册: %02d:%02d -> %s', hour, minute, get_backup_dir())
    return True
