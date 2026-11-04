#!/usr/bin/env python3
"""SQLite 在线一致性备份小工具（F1.2 / P0-1）。

用法:
    python scripts/online_backup.py <源库路径> <目标备份路径>

语义与 app.py create_sqlite_online_backup 一致：
- 源库以只读 URI 打开（mode=ro），通过 sqlite3 backup API 取一致性快照，
  源库运行中也可安全备份，不会拷到 WAL 中间态的撕裂文件；
- 临时快照完整性检查通过后才原子发布；失败只清理本次临时文件，保留旧备份；
- 拒绝源库与目标同文件（含硬链接），备份等待有上限，源文件名按URI正确转义。

仅依赖标准库，供 update_from_github.bat / 运维脚本在业务模块加载前调用。
退出码：0 成功；1 参数错误；2 备份或校验失败。
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from sqlite_snapshot import create_snapshot


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: online_backup.py <source_db> <dest_db>", file=sys.stderr)
        return 1
    source, dest = argv[0], argv[1]
    if not os.path.exists(source):
        print(f"[online_backup] source not found: {source}", file=sys.stderr)
        return 2
    try:
        create_snapshot(source, dest)
    except (OSError, sqlite3.Error) as exc:
        print(f"[online_backup] FAILED: {exc}", file=sys.stderr)
        return 2
    print(f"[online_backup] ok: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
