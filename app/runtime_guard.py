"""运行服务与离线维护共用的OS锁；不导入Flask，不读取/修改业务库。"""
import os
from pathlib import Path

# Repair task: AUDIT-FULL-20261016-001-F01


def acquire_database_lease(path, create_parent=False):
    """返回持锁文件句柄；关闭/进程退出自动释放，残留锁文件不表示占用。"""
    target = Path(path).resolve()
    if create_parent:
        target.parent.mkdir(parents=True, exist_ok=True)
    handle = open(target.with_name('.' + target.name + '.wms.lock'), 'a+b')
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError) as exc:
        handle.close()
        raise RuntimeError('数据库正在运行或维护，无法取得独占运行锁；请先停止对应WMS服务。') from exc
    return handle


def server_database_path(environ):
    """按Flask SQLite相对路径语义定位；测试内存库、非SQLite不取文件锁。"""
    if environ.get('FLASK_ENV') == 'testing':
        return None
    uri = environ.get('DATABASE_URL') or 'sqlite:///inventory.db'
    if not uri.startswith('sqlite:///') or uri == 'sqlite:///:memory:':
        return None
    raw = uri[len('sqlite:///'):]
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent / 'instance' / path
    return path.resolve()
