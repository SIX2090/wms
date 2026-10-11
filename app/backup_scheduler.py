"""每日自动备份调度器（F1.2 / P0-1 / 审计 §5.2）。

把 config.py 中既有的 AUTO_BACKUP_* 死配置接入真实调度：
- AUTO_BACKUP_ENABLED（env，默认 true）：总开关；
- AUTO_BACKUP_TIME（env，默认 '02:00'）：每日备份时刻（HH:MM）；
- BACKUP_RETENTION_DAYS（env，默认 30）：自动备份保留天数，
  只清理本调度器产出的 auto_daily_*.db，绝不动更新前备份等其他文件；
- WMS_BACKUP_DIR（env，默认 C:\\wms_backups）：备份目标目录。
  拍板 #8：本机仅 C 盘，先放独立目录（与安装目录/数据目录隔离，避免误删连带），
  将来接 NAS 时改环境变量即切换，代码不动。

备份使用 sqlite3 在线备份 API（app.create_sqlite_online_backup），
运行中也可取得一致性快照；每次备份后 PRAGMA integrity_check，
失败抛错并删除坏文件——坏备份比没备份更危险。
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_BACKUP_DIR = r'C:\wms_backups'
AUTO_BACKUP_PREFIX = 'auto_daily_'


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
    from app import create_sqlite_online_backup, get_database_file_path

    source = get_database_file_path()
    backup_dir = get_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = backup_dir / f'{AUTO_BACKUP_PREFIX}{stamp}_inventory.db'

    create_sqlite_online_backup(source, dest)

    # 完整性校验：坏备份比没备份更危险。
    import sqlite3
    check_conn = sqlite3.connect(str(dest), timeout=30)
    try:
        row = check_conn.execute('PRAGMA integrity_check').fetchone()
        if not row or row[0] != 'ok':
            try:
                dest.unlink()
            except OSError:
                pass
            raise RuntimeError(f'备份完整性校验失败: {row[0] if row else "no result"}')
    finally:
        check_conn.close()

    logger.info('每日自动备份完成: %s', dest)
    _cleanup_expired(backup_dir)
    return dest


def _cleanup_expired(backup_dir: Path) -> int:
    """清理超过 BACKUP_RETENTION_DAYS 天的自动备份（只动 auto_daily_*.db）。"""
    retention_raw = (os.environ.get('BACKUP_RETENTION_DAYS') or '30').strip()
    try:
        retention_days = max(1, int(retention_raw))
    except ValueError:
        logger.warning('BACKUP_RETENTION_DAYS=%r 非法，回退 30', retention_raw)
        retention_days = 30
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for f in backup_dir.glob(f'{AUTO_BACKUP_PREFIX}*.db'):
        try:
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
