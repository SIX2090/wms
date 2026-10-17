"""Repair task: AUDIT-FULL-20261016-001-F08; fixed backup sources, read-only metadata."""
from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sqlite3
import stat
import time

import backup_scheduler

_APP_DIR = Path(__file__).resolve().parent
# A flattened/offline install must not register an unrelated parent-drive directory.
UPDATE_BACKUP_DIR = (_APP_DIR.parent / 'backups'
                     if _APP_DIR.name.lower() == 'app' and (_APP_DIR.parent / 'scripts/update_from_github.py').is_file()
                     else _APP_DIR / 'backups')


def get_backup_settings():
    hour, minute = backup_scheduler._parse_hhmm(os.environ.get('AUTO_BACKUP_TIME') or '02:00')
    return {
        'enabled': (os.environ.get('AUTO_BACKUP_ENABLED') or 'true').strip().lower() in ('true', '1', 'yes'),
        'time': f'{hour:02d}:{minute:02d}',
        'retention_days': backup_scheduler.get_retention_days(),
    }


def get_backup_sources(manual_dir):
    """Source keys are fixed; request parameters can never register filesystem paths."""
    days = backup_scheduler.get_retention_days()
    return {
        'daily': {'directory': backup_scheduler.get_backup_dir(), 'label': '每日自动备份',
                  'retention': f'保留最近 {days} 天', 'auto_only': True},
        'manual': {'directory': Path(manual_dir), 'label': '手动 / 历史备份',
                   'retention': '不自动清理', 'auto_only': False},
        'update': {'directory': Path(UPDATE_BACKUP_DIR), 'label': '更新 / 维护目录',
                   'retention': '不自动清理', 'auto_only': False},
    }


def resolve_backup_file(sources, source, filename, protected_paths=()):
    """Resolve one regular DB file inside a registered root, never a file link."""
    if source not in sources:
        raise ValueError('未知备份来源')
    if (not isinstance(filename, str) or not filename or len(filename) > 255 or
            any(char in filename for char in '/\\:\x00') or '..' in filename or
            not filename.lower().endswith('.db')):
        raise ValueError('非法备份文件名')
    config = sources[source]
    if config['auto_only'] and not filename.startswith(backup_scheduler.AUTO_BACKUP_PREFIX):
        raise ValueError('该文件不属于每日自动备份')
    root = Path(config['directory']).resolve()
    candidate = root / filename
    info = candidate.lstat()
    if (not stat.S_ISREG(info.st_mode) or
            getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
        raise ValueError('不允许访问备份目录中的链接或非普通文件')
    resolved = candidate.resolve(strict=True)
    if resolved.parent != root:
        raise ValueError('备份路径超出注册目录')
    protected = {os.path.normcase(str(Path(value).resolve())) for value in protected_paths if value}
    if os.path.normcase(str(resolved)) in protected:
        raise ValueError('当前业务数据库不能作为备份文件操作')
    return resolved


def list_backup_files(sources, protected_paths=()):
    """Metadata only: listing never opens SQLite databases or creates directories."""
    files, warnings, seen = [], [], set()
    for source, config in sources.items():
        root = Path(config['directory'])
        try:
            if not root.exists():
                continue
            for entry in root.iterdir():
                if entry.suffix.lower() != '.db':
                    continue
                try:
                    path = resolve_backup_file(sources, source, entry.name, protected_paths)
                    key = os.path.normcase(str(path))
                    if key in seen:
                        continue
                    info = path.stat()
                    files.append({'id': f'{source}:{entry.name}', 'filename': entry.name,
                                  'source': source, 'source_label': config['label'],
                                  'retention': config['retention'], 'size_bytes': info.st_size,
                                  'created_at': datetime.fromtimestamp(info.st_mtime)})
                    seen.add(key)
                except (OSError, ValueError, OverflowError):
                    continue  # Expired/deleted files and disallowed links are not actionable rows.
        except OSError:
            warnings.append(config['label'] + '目录读取失败，请检查路径和权限')
    return files, warnings


def verify_backup_integrity(path, max_seconds=5):
    """Physical SQLite check only; immutable read-only access never restores or writes."""
    path = Path(path)
    connection = None
    deadline = time.monotonic() + max_seconds
    try:
        for suffix in ('-wal', '-journal'):
            sidecar = Path(str(path) + suffix)
            if sidecar.exists() and sidecar.stat().st_size:
                return {'valid': None, 'msg': '存在事务旁文件，请在离线维护副本中校验'}
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True, timeout=3)
        connection.execute('PRAGMA query_only=ON')
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10000)
        result = connection.execute('PRAGMA integrity_check').fetchone()
        valid = bool(result and result[0] == 'ok')
        return {'valid': valid, 'msg': 'SQLite 完整性通过；恢复仍须停机和结构校验' if valid else 'SQLite 完整性未通过，请保留文件并检查其他备份'}
    except sqlite3.OperationalError as error:
        if 'interrupted' in str(error).lower():
            return {'valid': None, 'msg': '校验未完成，文件较大时请在离线副本中校验'}
        return {'valid': None, 'msg': '文件无法读取或已变更，请检查后重试'}
    except sqlite3.DatabaseError:
        return {'valid': False, 'msg': '不是有效的 SQLite 备份，请保留文件并检查其他备份'}
    except OSError:
        return {'valid': None, 'msg': '文件无法读取或已变更，请检查后重试'}
    finally:
        if connection is not None:
            connection.close()
