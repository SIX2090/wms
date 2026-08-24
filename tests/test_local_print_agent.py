# -*- coding: utf-8 -*-
"""内置本机打印代理（SERVER-AUTOPRINT-01）回归测试。

覆盖：
- local_print_agent：打印机枚举解析、默认打印机读写、kiosk 浏览器定位、
  静默打印进程管理、内置工作站幂等确保、兜底派发、单轮心跳/认领打印、启动开关
- routes/print_queue 共用助手：sync_workstation_printers / build_agent_print_url /
  mark_job_printed / _resolve_job_assignment（含内置代理兜底优先级）
- enqueue_auto_print_job 无规则时兜底到内置代理
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

import app as app_module  # noqa: E402
import local_print_agent as lpa  # noqa: E402
from app import PrintDevice, PrintJob, PrintRouteRule, PrintWorkstation, db  # noqa: E402
from routes.print_queue import (  # noqa: E402
    _resolve_job_assignment,
    build_agent_print_url,
    enqueue_auto_print_job,
    mark_job_printed,
    sync_workstation_printers,
)


@pytest.fixture()
def app_ctx():
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        yield


def _seed_builtin_ws(online=True, with_printer=True):
    """建内置工作站（可选在线/带打印机）。"""
    ws = PrintWorkstation(
        code=lpa.BUILTIN_WS_CODE, name=lpa.BUILTIN_WS_NAME,
        device_id=lpa.BUILTIN_WS_DEVICE_ID,
        status='online' if online else 'offline', enabled=True,
        auth_token='test-token',
        last_heartbeat=datetime.now() if online else None,
    )
    db.session.add(ws)
    db.session.flush()
    printer = None
    if with_printer:
        printer = PrintDevice(
            workstation_id=ws.id, system_name='HP LaserJet', display_name='HP LaserJet',
            printer_type='mixed', status='online', enabled=True, is_default=True,
        )
        db.session.add(printer)
        db.session.flush()
    db.session.commit()
    return ws, printer


# ==================== 打印机枚举与解析 ====================

def test_enumerate_local_printers(monkeypatch):
    """三条 PowerShell 回退链：前两条失败取第三条 CSV；三态区分 list/[]/None。"""
    csv_payload = 'Name,Default,PrinterStatus,WorkOffline\n"HP LaserJet",True,3,False\n'
    calls = []

    def fake_ps(cmd):
        calls.append(cmd)
        if 'ConvertTo-Csv' in cmd:
            return True, csv_payload
        return False, ''  # 前两条命令失败（退出码非 0）

    monkeypatch.setattr(lpa, '_run_powershell_status', fake_ps)
    printers = lpa.enumerate_local_printers()
    assert printers == [{'system_name': 'HP LaserJet', 'status': 'ready', 'is_default': True}]
    assert len(calls) == 3  # 前两条 JSON 路线失败后才走 CSV

    # 命令执行成功但本机确实无打印机 → []（可与失败 None 区分，此时置 offline 才对）
    monkeypatch.setattr(lpa, '_run_powershell_status', lambda cmd: (True, ''))
    assert lpa.enumerate_local_printers() == []

    # 三条命令全部失败（Print Spooler 停止 / WMI 异常）→ None，不得误当「无打印机」
    monkeypatch.setattr(lpa, '_run_powershell_status', lambda cmd: (False, ''))
    assert lpa.enumerate_local_printers() is None


def test_get_default_printer(monkeypatch):
    """CimInstance 读不到时回退 WmiObject；结果去引号。"""
    outputs = iter(['', '"HP LaserJet"'])
    monkeypatch.setattr(lpa, '_run_powershell', lambda cmd: next(outputs))
    assert lpa.get_default_printer() == 'HP LaserJet'


def test_set_default_printer(monkeypatch):
    """按 $? 回写 OK 判定成功；空名直接失败；打印机名单引号转义。"""
    seen = []
    monkeypatch.setattr(lpa, '_run_powershell', lambda cmd: seen.append(cmd) or 'OK')
    assert lpa.set_default_printer("O'Brien Printer") is True
    assert "''Brien" in seen[0]  # 单引号翻倍转义
    assert lpa.set_default_printer('') is False

    monkeypatch.setattr(lpa, '_run_powershell', lambda cmd: '')
    assert lpa.set_default_printer('X') is False


def test_find_kiosk_browser(monkeypatch):
    """固定目录找不到时走注册表回退；都没有返回 None。"""
    monkeypatch.setattr(lpa.os.path, 'isfile', lambda p: False)
    monkeypatch.setattr(lpa, '_registry_chrome_path', lambda: r'C:\chrome\chrome.exe')
    assert lpa.find_kiosk_browser() == r'C:\chrome\chrome.exe'

    monkeypatch.setattr(lpa, '_registry_chrome_path', lambda: None)
    monkeypatch.setattr(lpa.shutil, 'which', lambda name: None)
    assert lpa.find_kiosk_browser() is None


def test_print_url_via_browser(monkeypatch):
    """正常退出返回 True；超时杀进程返回 False；启动异常返回 False。"""

    class FakeProc:
        def __init__(self, *a, **kw):
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(lpa.subprocess, 'Popen', FakeProc)
    assert lpa.print_url_via_browser('browser.exe', 'http://x/print', timeout=5) is True

    class TimeoutProc(FakeProc):
        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd='b', timeout=timeout)

        def terminate(self):
            return None

        def kill(self):
            return None

    monkeypatch.setattr(lpa.subprocess, 'Popen', TimeoutProc)
    assert lpa.print_url_via_browser('browser.exe', 'http://x/print', timeout=5) is False

    def raising_popen(*a, **kw):
        raise OSError('no exe')

    monkeypatch.setattr(lpa.subprocess, 'Popen', raising_popen)
    assert lpa.print_url_via_browser('missing.exe', 'http://x/print', timeout=5) is False


# ==================== 内置工作站确保 ====================

def test_ensure_builtin_print_workstation(tmp_path):
    """空库建表 + 插入内置工作站；二次执行幂等（令牌不重新生成）。"""
    import sqlite3
    db_file = tmp_path / 'inventory.db'
    db_file.touch()  # 模拟已存在的库文件

    lpa.ensure_builtin_print_workstation(db_path=str(db_file))
    conn = sqlite3.connect(str(db_file))
    rows = conn.execute(
        "SELECT code, status, enabled, auth_token FROM print_workstation").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == lpa.BUILTIN_WS_CODE
    assert rows[0][1] == 'offline'  # 初始离线，等代理心跳置在线
    assert rows[0][2] == 1
    token1 = rows[0][3]
    assert token1
    # 打印系列表同步建出
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {'print_workstation', 'print_device', 'print_route_rule'} <= tables
    conn.close()

    lpa.ensure_builtin_print_workstation(db_path=str(db_file))
    conn = sqlite3.connect(str(db_file))
    rows2 = conn.execute(
        "SELECT auth_token FROM print_workstation WHERE code=?",
        (lpa.BUILTIN_WS_CODE,)).fetchall()
    conn.close()
    assert len(rows2) == 1 and rows2[0][0] == token1  # 幂等，不动令牌

    # 库文件不存在时直接返回（全新部署交给 initialize_database + 心跳补建）
    lpa.ensure_builtin_print_workstation(db_path=str(tmp_path / 'missing.db'))
    assert not (tmp_path / 'missing.db').exists()


# ==================== 兜底派发与共用助手 ====================

def test_builtin_local_assignment(app_ctx):
    """内置代理在线且有打印机 → (ws_id, printer_id)；否则 None。"""
    assert lpa.builtin_local_assignment() is None  # 无工作站

    ws, printer = _seed_builtin_ws(online=True, with_printer=True)
    assert lpa.builtin_local_assignment() == (ws.id, printer.id)

    # 工作站离线 → None
    ws.status = 'offline'
    ws.last_heartbeat = None
    db.session.commit()
    assert lpa.builtin_local_assignment() is None

    # 在线但无在线打印机 → None
    ws.status = 'online'
    ws.last_heartbeat = datetime.now()
    printer.status = 'offline'
    db.session.commit()
    assert lpa.builtin_local_assignment() is None


def test_sync_workstation_printers(app_ctx):
    """dict 与对象两种载荷均可；未上报的存量打印机置 offline。"""
    ws, printer = _seed_builtin_ws(online=True, with_printer=True)
    created, online = sync_workstation_printers(ws, [
        {'system_name': 'HP LaserJet', 'status': 'ready', 'is_default': True},
        {'system_name': 'EPSON TM', 'status': 'error', 'is_default': False},
    ])
    db.session.commit()
    assert (created, online) == (1, 2)  # HP 已存在不重复建，EPSON 新增
    devices = {d.system_name: d for d in PrintDevice.query.filter_by(workstation_id=ws.id)}
    assert devices['HP LaserJet'].status == 'online'
    assert devices['EPSON TM'].status == 'error'

    # 第二轮只上报 EPSON → HP 置 offline
    class P:  # 模拟 pydantic 心跳对象（属性访问）
        system_name = 'EPSON TM'
        status = 'ready'
        is_default = False

    created, online = sync_workstation_printers(ws, [P()])
    db.session.commit()
    assert (created, online) == (0, 1)
    db.session.refresh(devices['HP LaserJet'])
    assert devices['HP LaserJet'].status == 'offline'


def test_build_agent_print_url(app_ctx):
    """打印 URL 必带 ptoken 与 autoprint=1，路径按 job_type 生成。"""
    ws, printer = _seed_builtin_ws()
    job = PrintJob(job_type='out_order', target_id=1, copies=2, status='pending',
                   workstation_id=ws.id, printer_id=printer.id)
    db.session.add(job)
    db.session.commit()
    url = build_agent_print_url(job)
    assert url.startswith('/out_order/1/print?copies=2&')
    assert 'ptoken=' in url
    assert url.endswith('autoprint=1')


def test_mark_job_printed(app_ctx):
    """成功置 done + printed_at；失败置 failed + error_msg 截断。"""
    ws, _ = _seed_builtin_ws()
    job = PrintJob(job_type='in_order', target_id=1, status='printing',
                   workstation_id=ws.id)
    db.session.add(job)
    db.session.commit()

    mark_job_printed(job, True)
    assert job.status == 'done' and job.printed_at is not None

    job.status = 'printing'
    db.session.commit()
    mark_job_printed(job, False, 'x' * 600)
    assert job.status == 'failed'
    assert len(job.error_msg) == 500


def test__resolve_job_assignment(app_ctx):
    """派发优先级：在线规则 > 离线规则 > 内置代理兜底 > 非定向。"""
    ws, printer = _seed_builtin_ws(online=True, with_printer=True)

    # 无规则 + 内置在线 → 兜底到内置代理（route_rule_id 为 None）
    r = _resolve_job_assignment('out_order', '')
    assert r == {'workstation_id': ws.id, 'printer_id': printer.id, 'route_rule_id': None}

    # 内置离线 → 非定向
    ws.status = 'offline'
    ws.last_heartbeat = None
    db.session.commit()
    assert _resolve_job_assignment('out_order', '') == {
        'workstation_id': None, 'printer_id': None, 'route_rule_id': None}

    # 存在规则（离线）→ 仍定向规则工作站（等其上线），不降级到内置
    rule_ws = PrintWorkstation(code='WS-A', name='仓库A', device_id='dev-a',
                               status='offline', enabled=True)
    db.session.add(rule_ws)
    db.session.flush()
    rule_printer = PrintDevice(workstation_id=rule_ws.id, system_name='P-A',
                               display_name='P-A', printer_type='mixed',
                               status='offline', enabled=True)
    db.session.add(rule_printer)
    db.session.flush()
    rule = PrintRouteRule(name='出库到A', business_event='out_order',
                          workstation_id=rule_ws.id, printer_id=rule_printer.id,
                          priority=100, enabled=True)
    db.session.add(rule)
    db.session.commit()
    r = _resolve_job_assignment('out_order', '')
    assert r == {'workstation_id': rule_ws.id, 'printer_id': rule_printer.id,
                 'route_rule_id': rule.id}
    # in_order 无规则且内置离线 → 非定向
    assert _resolve_job_assignment('in_order', '')['workstation_id'] is None

    # 规则在线 → 在线规则优先（同离线分支值相同，但来源是第一条分支）
    rule_ws.status = 'online'
    rule_ws.last_heartbeat = datetime.now()
    rule_printer.status = 'online'
    db.session.commit()
    r = _resolve_job_assignment('out_order', '')
    assert r['route_rule_id'] == rule.id


def test_enqueue_auto_print_job_builtin_fallback(app_ctx):
    """手机扫码自动入队：无规则时兜底内置代理；内置不可用则非定向。"""
    ws, printer = _seed_builtin_ws(online=True, with_printer=True)
    job = enqueue_auto_print_job('out_order', 1, '', source_event='scan_draft_confirm_out')
    db.session.commit()
    assert job.workstation_id == ws.id
    assert job.printer_id == printer.id
    assert job.route_rule_id is None

    ws.enabled = False  # 内置停用 → 非定向兜底
    db.session.commit()
    job2 = enqueue_auto_print_job('out_order', 2, '')
    db.session.commit()
    assert job2.workstation_id is None


# ==================== 单轮心跳与认领打印 ====================

def test__heartbeat(app_ctx, monkeypatch):
    """心跳置在线 + upsert 打印机；工作站缺失时当场补建；停用时空转。"""
    monkeypatch.setattr(lpa, 'enumerate_local_printers', lambda: [
        {'system_name': 'HP LaserJet', 'status': 'ready', 'is_default': True}])
    state = {'first_heartbeat': True}

    # 工作站不存在 → 补建（走 ensure 文件库路径，:memory: 下建不出 → False）
    assert lpa._heartbeat(state) is False

    _seed_builtin_ws(online=False, with_printer=False)
    assert lpa._heartbeat(state) is True
    ws = PrintWorkstation.query.filter_by(code=lpa.BUILTIN_WS_CODE).first()
    assert ws.status == 'online' and ws.last_heartbeat is not None
    device = PrintDevice.query.filter_by(workstation_id=ws.id).one()
    assert device.system_name == 'HP LaserJet' and device.status == 'online'

    # 停用 → False 并标记
    ws.enabled = False
    db.session.commit()
    assert lpa._heartbeat(state) is False
    assert state['disabled_noted'] is True


def test__heartbeat_printer_enum_failure_keeps_devices(app_ctx, monkeypatch, caplog):
    """BUG-2026-08-24-004：枚举失败（None）只保活工作站、不把已有打印机误标 offline；
    进入失败打一条 WARNING、连续失败不刷屏、恢复打一条 INFO 并重新同步。"""
    import logging as _logging
    ws, printer = _seed_builtin_ws(online=False, with_printer=True)

    # 枚举失败 → None：工作站保活在线，打印机保持原状态（关键：不被误标 offline）
    monkeypatch.setattr(lpa, 'enumerate_local_printers', lambda: None)
    state = {'first_heartbeat': True}
    with caplog.at_level(_logging.INFO, logger='wms.local_print_agent'):
        assert lpa._heartbeat(state) is True
    db.session.refresh(ws)
    db.session.refresh(printer)
    assert ws.status == 'online' and ws.last_heartbeat is not None
    assert printer.status == 'online'  # 未被误标 offline（证明未走 sync 空上报）
    assert state['printer_enum_failed'] is True
    warns = [r for r in caplog.records if r.levelname == 'WARNING' and '枚举失败' in r.getMessage()]
    assert len(warns) == 1  # 进入失败仅一条

    # 连续失败第二轮：状态未翻转，不再重复告警（节流，不每 60s 刷屏）
    caplog.clear()
    with caplog.at_level(_logging.INFO, logger='wms.local_print_agent'):
        assert lpa._heartbeat(state) is True
    warns2 = [r for r in caplog.records if r.levelname == 'WARNING' and '枚举失败' in r.getMessage()]
    assert len(warns2) == 0

    # 枚举恢复 → 重新同步打印机并打一条恢复日志
    monkeypatch.setattr(lpa, 'enumerate_local_printers', lambda: [
        {'system_name': 'HP LaserJet', 'status': 'ready', 'is_default': True}])
    caplog.clear()
    with caplog.at_level(_logging.INFO, logger='wms.local_print_agent'):
        assert lpa._heartbeat(state) is True
    recovers = [r for r in caplog.records if r.levelname == 'INFO' and '已恢复' in r.getMessage()]
    assert len(recovers) == 1
    assert 'printer_enum_failed' not in state


def test__claim_and_print(app_ctx, monkeypatch):
    """认领→kiosk 打印→回写 done；打印失败回写 failed；无浏览器直接失败。"""
    ws, printer = _seed_builtin_ws(online=True, with_printer=True)
    job = PrintJob(job_type='out_order', target_id=1, copies=1, status='pending',
                   workstation_id=ws.id, printer_id=printer.id)
    db.session.add(job)
    db.session.commit()

    printed_urls = []
    monkeypatch.setattr(lpa, 'print_url_via_browser',
                        lambda browser, url, timeout: printed_urls.append(url) or True)
    monkeypatch.setattr(lpa, 'get_default_printer', lambda: 'HP LaserJet')
    monkeypatch.setattr(lpa, 'set_default_printer', lambda name: True)

    result = lpa._claim_and_print('http://127.0.0.1:8080', 'browser.exe')
    assert result == {'job_id': job.id, 'ok': True}
    db.session.refresh(job)
    assert job.status == 'done'
    assert printed_urls[0].startswith('http://127.0.0.1:8080/out_order/1/print?')
    assert 'ptoken=' in printed_urls[0] and 'autoprint=1' in printed_urls[0]

    # 队列空 → None
    assert lpa._claim_and_print('http://127.0.0.1:8080', 'browser.exe') is None

    # 打印失败 → failed + error_msg
    job2 = PrintJob(job_type='in_order', target_id=2, copies=1, status='pending',
                    workstation_id=ws.id, printer_id=printer.id)
    db.session.add(job2)
    db.session.commit()
    monkeypatch.setattr(lpa, 'print_url_via_browser', lambda *a: False)
    result = lpa._claim_and_print('http://127.0.0.1:8080', 'browser.exe')
    assert result['ok'] is False
    db.session.refresh(job2)
    assert job2.status == 'failed' and '超时' in job2.error_msg

    # 无浏览器 → failed（不崩溃）
    job3 = PrintJob(job_type='in_order', target_id=3, copies=1, status='pending',
                    workstation_id=ws.id, printer_id=printer.id)
    db.session.add(job3)
    db.session.commit()
    result = lpa._claim_and_print('http://127.0.0.1:8080', None)
    assert result['ok'] is False
    db.session.refresh(job3)
    assert job3.status == 'failed' and '浏览器' in job3.error_msg


# ==================== 启动开关 ====================

def test_start_local_print_agent(monkeypatch):
    """环境变量关闭 / TESTING 模式 / 重复启动均返回 None 且不建线程。"""
    monkeypatch.setattr(lpa, '_started', False)
    monkeypatch.setenv('WMS_LOCAL_PRINT_AGENT', '0')
    assert lpa.start_local_print_agent(app_module.app, 'http://127.0.0.1:8080') is None

    monkeypatch.delenv('WMS_LOCAL_PRINT_AGENT')
    monkeypatch.setitem(app_module.app.config, 'TESTING', True)
    assert lpa.start_local_print_agent(app_module.app, 'http://127.0.0.1:8080') is None

    # 非测试模式也不允许重复启动（不真正起线程：打桩 Thread）
    started = []

    class FakeThread:
        def __init__(self, target=None, args=(), name=None, daemon=None):
            self.name = name

        def start(self):
            started.append(self.name)

    monkeypatch.setitem(app_module.app.config, 'TESTING', False)
    monkeypatch.setattr(lpa.threading, 'Thread', FakeThread)
    monkeypatch.setattr(lpa, '_started', False)
    thread = lpa.start_local_print_agent(app_module.app, 'http://127.0.0.1:8080')
    assert thread is not None and started == ['wms-local-print-agent']
    assert lpa.start_local_print_agent(app_module.app, 'http://127.0.0.1:8080') is None
    assert started == ['wms-local-print-agent']  # 幂等


# ==================== schema 未就绪静默等待（BUG-2026-08-23-003） ====================

def test__is_schema_not_ready():
    """缺表/缺列识别为等待态（大小写不敏感）；其他异常不误判。"""
    import sqlite3

    assert lpa._is_schema_not_ready(sqlite3.OperationalError('no such table: print_workstation'))
    assert lpa._is_schema_not_ready(sqlite3.OperationalError('no such column: print_job.route_rule_id'))
    assert lpa._is_schema_not_ready(RuntimeError('NO SUCH TABLE: foo'))
    assert not lpa._is_schema_not_ready(sqlite3.OperationalError('database is locked'))
    assert not lpa._is_schema_not_ready(ValueError('boom'))


def test__agent_loop_schema_wait_quiet(app_ctx, monkeypatch, caplog):
    """schema 未就绪：仅首条警告 + SCHEMA_WAIT_INTERVAL 静默重试，不刷 traceback；
    就绪后打一条恢复日志并回到正常轮询。"""
    import sqlite3
    import logging as _logging

    calls = {'claim': 0, 'sleeps': []}

    def fake_claim(base_url, browser):
        calls['claim'] += 1
        n = calls['claim']
        if n <= 2:
            raise sqlite3.OperationalError('no such table: print_workstation')
        if n == 3:
            return None  # 数据库就绪，正常空轮
        raise KeyboardInterrupt  # 终止循环（BaseException 不被代理兜底捕获）

    monkeypatch.setattr(lpa, 'find_kiosk_browser', lambda: None)
    monkeypatch.setattr(lpa, '_heartbeat', lambda state: True)
    monkeypatch.setattr(lpa, '_claim_and_print', fake_claim)
    monkeypatch.setattr(lpa.time, 'sleep', lambda s: calls['sleeps'].append(s))

    with caplog.at_level(_logging.INFO, logger='wms.local_print_agent'):
        with pytest.raises(KeyboardInterrupt):
            lpa._agent_loop(app_module.app, 'http://127.0.0.1:8080')

    schema_warnings = [r for r in caplog.records
                       if r.levelname == 'WARNING' and 'schema 未就绪' in r.getMessage()]
    recoveries = [r for r in caplog.records
                  if r.levelname == 'INFO' and '已就绪' in r.getMessage()]
    with_traceback = [r for r in caplog.records if r.exc_info]
    assert len(schema_warnings) == 1        # 只警告一次，不刷屏
    assert len(recoveries) == 1             # 就绪后恢复提示
    assert len(with_traceback) == 0         # schema 等待期间不 log.exception
    assert calls['sleeps'].count(lpa.SCHEMA_WAIT_INTERVAL) == 2   # 两轮等待各睡 60s
    assert calls['sleeps'].count(lpa.POLL_INTERVAL) == 1          # 正常一轮睡 3s
