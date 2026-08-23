"""BUG-2026-08-23-004 回归：run_server 端口占用识别与中文启动指引。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"
os.environ["WMS_SKIP_AUTO_UPDATE"] = "1"

import run_server  # noqa: E402


def test__is_addr_in_use_error():
    """Linux 98 / Windows 10048 / macOS 48 / 仅消息匹配 均识别；其他 OSError 不误判。"""
    assert run_server._is_addr_in_use_error(OSError(98, 'Address already in use'))
    assert run_server._is_addr_in_use_error(OSError(10048, '通常每个套接字地址只允许使用一次'))
    assert run_server._is_addr_in_use_error(OSError(48, 'Address already in use'))
    assert run_server._is_addr_in_use_error(OSError('Address already in use'))
    assert not run_server._is_addr_in_use_error(OSError(13, 'Permission denied'))
    assert not run_server._is_addr_in_use_error(OSError(99, 'Cannot assign requested address'))
