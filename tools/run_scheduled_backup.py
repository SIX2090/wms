#!/usr/bin/env python3
"""Independent daily backup entry; requires explicit source and destination."""
import argparse
import logging
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from backup_scheduler import run_backup_for_source


def main(argv=None):
    parser = argparse.ArgumentParser(description='独立执行每日在线备份，不加载WMS或启动任何外发任务')
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--retention-days', type=int)
    args = parser.parse_args(argv)
    if args.retention_days is not None:
        if args.retention_days < 1:
            parser.error('保留天数必须大于0')
        os.environ['BACKUP_RETENTION_DAYS'] = str(args.retention_days)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    os.environ['WMS_BACKUP_DIR'] = str(args.directory.resolve())
    if (os.environ.get('AUTO_BACKUP_ENABLED') or 'true').strip().lower() not in {'true', '1', 'yes'}:
        logging.info('自动备份配置已关闭，本次不访问源库')
        return 0
    try:
        run_backup_for_source(args.source)
    except Exception:
        logging.exception('每日自动备份失败，请检查源库、目录权限及磁盘空间；已有备份保留')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
