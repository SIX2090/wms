#!/usr/bin/env python3
"""SQLite 在线一致性备份小工具（F1.2 / P0-1）。

用法:
    python scripts/online_backup.py <源库路径> <目标备份路径>

语义与 app.py create_sqlite_online_backup 一致：
- 源库以只读 URI 打开（mode=ro），通过 sqlite3 backup API 取一致性快照，
  源库运行中也可安全备份，不会拷到 WAL 中间态的撕裂文件；
- 备份完成后立即 PRAGMA integrity_check，校验失败返回非零并删除坏备份——
  坏备份比没备份更危险（给人虚假安全感）。

仅依赖标准库，供 update_from_github.bat / 运维脚本在业务模块加载前调用。
退出码：0 成功；1 参数错误；2 备份或校验失败。
"""
import os
import sqlite3
import sys


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: online_backup.py <source_db> <dest_db>", file=sys.stderr)
        return 1
    source, dest = argv[0], argv[1]
    if not os.path.exists(source):
        print(f"[online_backup] source not found: {source}", file=sys.stderr)
        return 2
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    try:
        src_uri = f"file:{os.path.abspath(source).replace(os.sep, '/')}?mode=ro"
        src_conn = sqlite3.connect(src_uri, uri=True, timeout=30)
        try:
            dst_conn = sqlite3.connect(dest, timeout=30)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()
        check_conn = sqlite3.connect(dest, timeout=30)
        try:
            row = check_conn.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise sqlite3.Error(f"integrity_check: {row[0] if row else 'no result'}")
        finally:
            check_conn.close()
    except (OSError, sqlite3.Error) as exc:
        print(f"[online_backup] FAILED: {exc}", file=sys.stderr)
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except OSError:
            pass
        return 2
    print(f"[online_backup] ok: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
