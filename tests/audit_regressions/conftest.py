"""Scoped boundaries for portable synthetic regressions; no production defaults."""
from pathlib import Path
import re
import socket
import sqlite3
import subprocess

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine

from tests.audit_regressions.support import _evidence


@pytest.fixture(autouse=True)
def audit_boundaries(tmp_path, monkeypatch):
    import app as m
    import werkzeug.security

    output = tmp_path / 'evidence'
    output.mkdir()
    token = _evidence.set(output)

    def denied(*args, **kwargs):
        raise AssertionError('Audit regression forbids real network or usable credential generation')

    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)
    monkeypatch.setattr(socket, 'getaddrinfo', denied)
    monkeypatch.setattr(werkzeug.security, 'generate_password_hash', denied)
    monkeypatch.setattr(m, 'generate_password_hash', denied, raising=False)

    def sql_boundary(conn, cursor, sql, parameters, context, many):
        normalized = re.sub(r'/\*.*?\*/|--[^\n]*', ' ', sql, flags=re.S).strip().upper()
        assert not re.match(r'^(?:DELETE|DROP|ALTER|REPLACE)\b|^INSERT\s+OR\s+REPLACE\b', normalized), sql
        database = conn.engine.url.database
        assert not database or database == ':memory:' or Path(database).resolve().is_relative_to(tmp_path.resolve()), database

    event.listen(Engine, 'before_cursor_execute', sql_boundary)
    original_connect = sqlite3.connect

    def fresh_connect(database, *args, **kwargs):
        assert str(database) == ':memory:' or Path(database).resolve().is_relative_to(tmp_path.resolve()), database
        return original_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, 'connect', fresh_connect)
    original_run = subprocess.run
    guard = Path(__file__).with_name('network_guard.cjs')

    def local_node_only(command, *args, **kwargs):
        assert isinstance(command, (list, tuple)) and command and Path(command[0]).stem.lower() == 'node', command
        return original_run([command[0], '--require', str(guard), *command[1:]], *args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', local_node_only)
    try:
        yield
    finally:
        event.remove(Engine, 'before_cursor_execute', sql_boundary)
        _evidence.reset(token)
