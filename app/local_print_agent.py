#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 内置本机打印代理（SERVER-AUTOPRINT-01）。
#
# 解决「打印工作站网页必须一直开着才能自动打印」的痛点：
# WMS 服务端进程内嵌一个后台线程，相当于把 tools/print_agent/wms_print_agent.py
# 的能力直接搬进服务器——启动即自动注册内置工作站（LOCAL-SERVER）、上报本机
# 打印机、认领定向到本机的打印任务，并用 Edge/Chrome 的 --kiosk-printing 模式
# 跳过打印对话框静默出纸，全程无人值守、无需开任何页面。
#
# 架构说明：
#   - 认领/僵尸回收/ptoken 签发等队列逻辑复用 routes/print_queue.py 的既有函数，
#     不在本模块另造一套（单一事实来源）。
#   - Windows 打印机操作原语（枚举/默认打印机切换/kiosk 打印）与独立版代理
#     tools/print_agent/wms_print_agent.py 保持一致。独立版必须单文件自包含
#     （部署包 zip 只发一个 .py，无法 import 服务端代码），故原语在此内聚一份，
#     两处修改需同步（含 BUG-2026-08-19-006/007、BUG-2026-08-20-005 的兼容回退）。
#   - 本模块不得在 import 期加载 app/routes（循环依赖），所有 ORM 操作
#     延迟到函数内部 import。
#
# 开关与配置（环境变量）：
#   WMS_LOCAL_PRINT_AGENT=0      关闭内置代理（默认开启）
#   WMS_LOCAL_PRINT_BASE_URL     打印页基础地址（默认 http://127.0.0.1:<启动端口>）
#
# 零配置兜底：enqueue_auto_print_job 在「无任何匹配路由规则」且内置代理在线、
# 有可用打印机时，自动把任务定向到内置工作站（见 routes/print_queue.py 的
# _resolve_job_assignment）。配了显式路由规则时规则永远优先。
from __future__ import annotations

import csv
import io
import json
import logging
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime

log = logging.getLogger('wms.local_print_agent')

# 内置工作站的固定标识（ensure_builtin_print_workstation 幂等键）。
BUILTIN_WS_CODE = 'LOCAL-SERVER'
BUILTIN_WS_NAME = '本机打印工作站（内置）'
BUILTIN_WS_DEVICE_ID = 'local-server'

POLL_INTERVAL = 3            # 认领轮询间隔（秒）
HEARTBEAT_INTERVAL = 60      # 心跳间隔（秒），服务端在线窗口 300 秒
PRINT_TIMEOUT = 120          # 单任务浏览器打印超时（秒）
SCHEMA_WAIT_INTERVAL = 60    # 数据库 schema 未就绪时的低频静默重试间隔（秒）

# schema 未就绪类错误关键字（sqlite OperationalError: no such table / no such column）
_SCHEMA_NOT_READY_KEYWORDS = ('no such table', 'no such column')


def _is_schema_not_ready(exc) -> bool:
    """判断异常是否属于数据库 schema 未就绪（缺表/缺列）的等待态。

    数据库文件丢失、路径错配或被外部重建时，代理轮询会持续撞 sqlite
    OperationalError；这类"等待数据库就绪"场景不该按通用异常每 3s 刷
    完整 traceback（启动窗口刷屏正是用户误报的"启动报错"）。
    """
    text = str(exc).lower()
    return any(keyword in text for keyword in _SCHEMA_NOT_READY_KEYWORDS)

_DISABLE_VALUES = ('0', 'false', 'no', 'off')
_started = False             # start_local_print_agent 幂等标记
_started_lock = threading.Lock()


# ==================== Windows 打印机原语（与独立代理保持同步） ====================

def _run_powershell_status(command: str, *, log_failure: bool = False) -> tuple[bool, str]:
    """执行 PowerShell 命令，返回 (ok, stdout)。

    ok=True：进程退出码为 0（stdout 可能为空，如本机确实一台打印机都没有）。
    ok=False：非 Windows / 进程异常 / 退出码非 0——典型如 Print Spooler 服务停止、
    WMI 库损坏，此时 Get-CimInstance/Get-WmiObject Win32_Printer 直接报错。
    枚举场景必须靠 ok 区分「命令失败」与「成功但无打印机」，不能只看 stdout 空。
    log_failure=True 时对失败打 WARNING（逐条回退探测传 False，由调用方统一告警，
    避免每轮心跳刷 3 条 stderr）。
    """
    if os.name != 'nt':
        return False, ''
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        if result.returncode != 0:
            if log_failure:
                log.warning('PowerShell 命令失败（exit=%s）：%s',
                            result.returncode, (result.stderr or '').strip()[:300])
            return False, ''
        return True, result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        if log_failure:
            log.warning('PowerShell 执行失败：%s', e)
        return False, ''


def _run_powershell(command: str) -> str:
    """执行 PowerShell 命令并返回 stdout（非 Windows 或执行失败返回空串）。

    对外行为与独立代理 tools/print_agent/wms_print_agent.py 保持一致（失败即空串
    并打 WARNING）；需要区分「失败」与「空结果」的调用方改用 _run_powershell_status。
    """
    _ok, out = _run_powershell_status(command, log_failure=True)
    return out


def _to_bool(v) -> bool:
    return str(v).strip().lower() in ('true', '1')


def _to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _ps_quote(value: str) -> str:
    """转义为 PowerShell 单引号字符串字面量（单引号翻倍）。"""
    return "'" + str(value).replace("'", "''") + "'"


def _map_printer_status(printer_status, work_offline) -> str:
    """Win32_Printer 状态值 → 服务端约定（ready/error）；7=脱机。"""
    if work_offline or printer_status == 7:
        return 'error'
    return 'ready'


def _parse_printer_output(raw: str) -> list[dict]:
    """解析 PowerShell 输出（JSON 或 CSV）为打印机列表；失败返回 []。"""
    try:
        data = json.loads(raw)
        rows = data if isinstance(data, list) else [data]
    except ValueError:
        try:
            rows = list(csv.DictReader(io.StringIO(raw)))
        except Exception:
            return []
    result = []
    for p in rows:
        name = str(p.get('Name') or '').strip()
        if not name or len(name) > 200:
            continue
        result.append({
            'system_name': name,
            'status': _map_printer_status(
                _to_int(p.get('PrinterStatus')), _to_bool(p.get('WorkOffline'))),
            'is_default': _to_bool(p.get('Default')),
        })
    return result


def enumerate_local_printers():
    """枚举本机打印机。返回值三态，调用方据 None 与 [] 做不同处理。

    - list[dict]：成功枚举到打印机 [{system_name, status, is_default}]；
    - []：命令执行成功但本机确实一台打印机都没有（此时把已有打印机置 offline 是对的）；
    - None：枚举失败——三条命令全部退出码非 0（Print Spooler 服务停止 / WMI 库损坏）。
      与 [] 严格区分：BUG-2026-08-24-004，调用方不得据 None 将打印机置 offline。

    BUG-2026-08-19-006 回退链：CimInstance+Json（PS 3.0+）→ WmiObject+Json
    → WmiObject+Csv（Win7 PS 2.0 自带 ConvertTo-Csv）。
    """
    query = 'Win32_Printer | Select-Object Name, Default, PrinterStatus, WorkOffline'
    commands = [
        f'Get-CimInstance {query} | ConvertTo-Json -Compress',
        f'Get-WmiObject {query} | ConvertTo-Json -Compress',
        f'Get-WmiObject {query} | ConvertTo-Csv -NoTypeInformation',
    ]
    saw_success = False
    for cmd in commands:
        # 逐条静默探测（log_failure=False）：失败由 _heartbeat 按状态翻转统一告警，
        # 避免 Spooler 停止时每 60s 刷 3 条 PowerShell stderr。
        ok, raw = _run_powershell_status(cmd)
        if not ok:
            continue
        saw_success = True
        printers = _parse_printer_output(raw)
        if printers:
            return printers
    return [] if saw_success else None


def get_default_printer() -> str:
    """读取当前 Windows 默认打印机名（读不到返回空串）。

    BUG-2026-08-19-007：Get-CimInstance 需 PS 3.0+，回退 Get-WmiObject。
    """
    raw = _run_powershell(
        "(Get-CimInstance Win32_Printer -Filter 'Default=True').Name")
    if not raw:
        raw = _run_powershell(
            "(Get-WmiObject Win32_Printer -Filter 'Default=True').Name")
    return raw.strip().strip('"')


def set_default_printer(name: str) -> bool:
    """临时切换 Windows 默认打印机（WScript.Network COM，无需管理员权限）。

    BUG-2026-08-19-007：SetDefaultPrinter 成功时无输出，按 $? 显式回写 OK。
    """
    if not name:
        return False
    ok = bool(_run_powershell(
        f'(New-Object -ComObject WScript.Network).SetDefaultPrinter({_ps_quote(name)}); '
        'if ($?) { Write-Output OK }'))
    if ok:
        log.info('默认打印机已切换为：%s', name)
    else:
        log.warning('切换默认打印机失败：%s（将使用当前默认打印机出纸）', name)
    return ok


def _registry_chrome_path():
    """从注册表（卸载项/App Paths）读取 Chrome 实际安装路径（BUG-2026-08-20-005）。"""
    if os.name != 'nt':
        return None
    import winreg
    keys = [
        (winreg.HKEY_LOCAL_MACHINE,
         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome'),
        (winreg.HKEY_LOCAL_MACHINE,
         r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome'),
        (winreg.HKEY_CURRENT_USER,
         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome'),
        (winreg.HKEY_CURRENT_USER,
         r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'),
    ]
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as k:
                for value_name in ('DisplayIcon', 'InstallLocation', ''):
                    try:
                        val, _ = winreg.QueryValueEx(k, value_name)
                    except OSError:
                        continue
                    if isinstance(val, str) and val.strip():
                        val = val.strip().strip('"').strip()
                        numpart, _, _ = val.partition(',')
                        val = numpart.strip('"').strip()
                        if value_name == 'InstallLocation':
                            val = os.path.join(val, 'chrome.exe')
                        if os.path.isfile(val):
                            return val
        except OSError:
            continue
    return None


def find_kiosk_browser():
    """定位 Edge / Chrome 可执行文件（kiosk-printing 支持静默出纸）。"""
    candidates = []
    if os.name == 'nt':
        candidates = [
            os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
            os.path.expandvars(r'%ProgramFiles%\Microsoft\Edge\Application\msedge.exe'),
            os.path.expandvars(r'%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe'),
        ]
    else:  # 开发联调：Linux 上找 chromium/chrome
        candidates = [shutil.which(n) or '' for n in
                      ('microsoft-edge', 'chromium', 'chromium-browser', 'google-chrome')]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    reg = _registry_chrome_path()
    if reg:
        return reg
    return shutil.which('msedge') or shutil.which('chrome') or None


def print_url_via_browser(browser: str, url: str, timeout: int = PRINT_TIMEOUT) -> bool:
    """以 kiosk-printing 打开打印页并等待退出，返回是否正常结束。

    独立 user-data-dir：不污染日常浏览器配置；页面 autoprint 完成后进程退出。
    """
    user_data_dir = os.path.join(tempfile.gettempdir(), 'wms_local_print_agent_profile')
    cmd = [browser, '--kiosk-printing', f'--app={url}',
           f'--user-data-dir={user_data_dir}',
           '--no-first-run', '--disable-extensions']
    log.info('调起浏览器静默打印：%s %s', os.path.basename(browser), url[:120])
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.error('浏览器启动失败：%s', e)
        return False
    try:
        proc.wait(timeout=timeout)
        log.info('浏览器打印进程已退出（code=%s）', proc.returncode)
        return True
    except subprocess.TimeoutExpired:
        log.warning('打印超时（%ss），结束浏览器进程', timeout)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False


# ==================== 内置工作站确保（NO_DB_TOUCH 安全，幂等） ====================

# 与 app.py 模型列定义保持一致；表已存在时一律不动。
_BUILTIN_DDL = (
    """CREATE TABLE IF NOT EXISTS print_workstation (
        id INTEGER PRIMARY KEY,
        code VARCHAR(64) NOT NULL UNIQUE,
        name VARCHAR(100) NOT NULL,
        device_id VARCHAR(128) NOT NULL UNIQUE,
        warehouse_id INTEGER REFERENCES warehouse(id),
        status VARCHAR(20) NOT NULL DEFAULT 'offline',
        enabled BOOLEAN NOT NULL DEFAULT 1,
        auth_token VARCHAR(128) UNIQUE,
        last_heartbeat DATETIME,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS print_device (
        id INTEGER PRIMARY KEY,
        workstation_id INTEGER NOT NULL REFERENCES print_workstation(id),
        system_name VARCHAR(200) NOT NULL,
        display_name VARCHAR(100) NOT NULL,
        printer_type VARCHAR(20) NOT NULL DEFAULT 'mixed',
        status VARCHAR(20) NOT NULL DEFAULT 'offline',
        enabled BOOLEAN NOT NULL DEFAULT 1,
        is_default BOOLEAN NOT NULL DEFAULT 0,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL,
        CONSTRAINT uq_print_device_system_name UNIQUE (workstation_id, system_name)
    )""",
    """CREATE TABLE IF NOT EXISTS print_route_rule (
        id INTEGER PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        business_event VARCHAR(30) NOT NULL,
        warehouse_id INTEGER REFERENCES warehouse(id),
        workstation_id INTEGER NOT NULL REFERENCES print_workstation(id),
        printer_id INTEGER NOT NULL REFERENCES print_device(id),
        priority INTEGER NOT NULL DEFAULT 100,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        created_at DATETIME NOT NULL,
        updated_at DATETIME NOT NULL
    )""",
    'CREATE INDEX IF NOT EXISTS idx_print_route_match '
    'ON print_route_rule (business_event, warehouse_id, priority)',
)


def ensure_builtin_print_workstation(db_path: str | None = None):
    """启动期无条件确保内置打印工作站存在（SERVER-AUTOPRINT-01）。

    与 ensure_print_job_columns / ensure_excel_print_template_table 同一套路：
    独立 sqlite 连接、独立于迁移开关（WMS_NO_DB_TOUCH=1 也执行）、幂等——
    表缺失则按模型 DDL 补建（IF NOT EXISTS），内置工作站行缺失才插入，
    已存在时连 auth_token 都不动（现场可能已把令牌配进独立代理）。
    """
    conn = None
    try:
        if db_path is None:
            from app import _resolve_sqlite_db_path
            db_path = _resolve_sqlite_db_path()
            if db_path is None:
                db_path = os.path.join(os.path.dirname(__file__), 'instance', 'inventory.db')
        if not os.path.exists(db_path):
            return  # 全新部署：库文件未建，交给 initialize_database/create_all + 本函数下次启动
        import sqlite3
        conn = sqlite3.connect(db_path, timeout=60)
        cur = conn.cursor()
        cur.execute('PRAGMA busy_timeout=60000')
        for ddl in _BUILTIN_DDL:
            cur.execute(ddl)
        row = cur.execute(
            'SELECT id FROM print_workstation WHERE code = ?',
            (BUILTIN_WS_CODE,)).fetchone()
        if row is None:
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cur.execute(
                'INSERT INTO print_workstation '
                '(code, name, device_id, status, enabled, auth_token, created_at, updated_at) '
                "VALUES (?, ?, ?, 'offline', 1, ?, ?, ?)",
                (BUILTIN_WS_CODE, BUILTIN_WS_NAME, BUILTIN_WS_DEVICE_ID,
                 secrets.token_urlsafe(32), now, now))
            conn.commit()
            logging.getLogger(__name__).info(
                '[打印] 内置本机打印工作站已创建（%s）', BUILTIN_WS_CODE)
        else:
            conn.commit()
    except Exception as e:
        try:
            logging.getLogger(__name__).error(
                f'ensure_builtin_print_workstation 执行失败: {e}', exc_info=True)
        except Exception:
            pass
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


# ==================== 代理主循环 ====================

def builtin_local_assignment():
    """内置本机代理可用时返回 (workstation_id, printer_id)，否则 None。

    「可用」= 内置工作站启用且心跳在线 + 至少一台启用的在线打印机
    （优先 Windows 默认打印机）。供 enqueue_auto_print_job 零配置兜底调用。
    """
    from app import PrintDevice, PrintWorkstation
    from routes.print_queue import workstation_is_online
    ws = PrintWorkstation.query.filter_by(code=BUILTIN_WS_CODE, enabled=True).first()
    if not workstation_is_online(ws):
        return None
    printers = [d for d in PrintDevice.query.filter_by(
        workstation_id=ws.id, enabled=True).all() if d.status == 'online']
    if not printers:
        return None
    default = next((d for d in printers if d.is_default), printers[0])
    return ws.id, default.id


def _heartbeat(state):
    """心跳：内置工作站置在线 + 同步本机打印机列表（复用路由层同步逻辑）。

    工作站行缺失时（如全新部署首启：ensure 跑在库文件创建之前）当场补建，
    避免「必须重启第二次内置代理才可用」。
    """
    from app import PrintWorkstation, db
    from routes.print_queue import sync_workstation_printers
    ws = PrintWorkstation.query.filter_by(code=BUILTIN_WS_CODE).first()
    if ws is None:
        ensure_builtin_print_workstation()
        ws = PrintWorkstation.query.filter_by(code=BUILTIN_WS_CODE).first()
        if ws is None:
            return False
    if not ws.enabled:
        state['disabled_noted'] = True
        return False
    printers = enumerate_local_printers()
    ws.status = 'online'
    ws.last_heartbeat = datetime.now()
    if printers is None:
        # BUG-2026-08-24-004：枚举失败（Print Spooler 停止/WMI 异常）时只保活工作站，
        # 不调用 sync_workstation_printers——否则空上报会把已有打印机全部误标 offline、
        # 打印路由随之瘫痪。保留上次已知状态；按状态翻转节流告警（进入失败打一条
        # WARNING、恢复打一条 INFO），不再每 60s 刷 PowerShell stderr。
        created, online = 0, None
        if not state.get('printer_enum_failed'):
            state['printer_enum_failed'] = True
            log.warning('内置打印代理：本机打印机枚举失败（可能 Print Spooler 服务未运行或 '
                        'WMI 异常），已保留现有打印机状态、不置 offline；请在服务器 '
                        'services.msc 启动 "Print Spooler" 服务，恢复后自动重新同步')
    else:
        if state.pop('printer_enum_failed', False):
            log.info('内置打印代理：本机打印机枚举已恢复，重新同步打印机状态')
        created, online = sync_workstation_printers(ws, printers)
    db.session.commit()
    if online is not None and (created or state.get('first_heartbeat')):
        log.info('内置打印代理心跳：本机打印机 %s 台在线（新增 %s）', online, created)
        state['first_heartbeat'] = False
    return True


def _claim_and_print(base_url, browser):
    """认领一条定向到内置工作站的任务并静默打印，返回处理信息（无任务返回 None）。"""
    from app import PrintJob, PrintWorkstation
    from routes.print_queue import (
        _claim_pending_job,
        _recover_zombie_printing_jobs,
        build_agent_print_url,
        mark_job_printed,
    )
    ws = PrintWorkstation.query.filter_by(code=BUILTIN_WS_CODE).first()
    if ws is None:
        return None
    _recover_zombie_printing_jobs(workstation_id=ws.id)
    job = _claim_pending_job(PrintJob, ws.id)
    if not job:
        return None
    url = base_url.rstrip('/') + build_agent_print_url(job)
    target_printer = job.printer.system_name if job.printer else ''
    log.info('内置代理开始打印任务 #%s：%s 份数=%s 目标打印机=%s',
             job.id, job.job_type, job.copies, target_printer or '（默认）')
    if not browser:
        mark_job_printed(job, False, '服务器本机未找到支持静默打印的 Edge/Chrome 浏览器')
        return {'job_id': job.id, 'ok': False, 'msg': 'no browser'}
    switched_from = ''
    if target_printer:
        switched_from = get_default_printer()
        if switched_from == target_printer or not set_default_printer(target_printer):
            switched_from = ''  # 已是目标打印机或切换失败：无需/无法恢复
    try:
        ok = print_url_via_browser(browser, url, PRINT_TIMEOUT)
        mark_job_printed(job, ok, '' if ok else f'浏览器打印超时（{PRINT_TIMEOUT}s）')
        return {'job_id': job.id, 'ok': ok}
    except Exception as e:  # noqa: BLE001 代理线程不允许因单任务异常退出
        log.exception('任务 #%s 处理异常', job.id)
        mark_job_printed(job, False, f'内置代理异常：{e}')
        return {'job_id': job.id, 'ok': False, 'msg': str(e)}
    finally:
        if switched_from:
            set_default_printer(switched_from)


def _agent_loop(app, base_url):
    """代理主循环：按期心跳，持续认领打印；任何单轮异常都只记日志不退出。"""
    state = {'next_heartbeat': 0.0, 'first_heartbeat': True, 'disabled_noted': False}
    browser = find_kiosk_browser()
    if not browser:
        log.warning('未找到 Edge/Chrome，内置打印代理将只上报心跳；打印任务会标记失败')
    while True:
        try:
            with app.app_context():
                from db import db as _db
                now = time.monotonic()
                if now >= state['next_heartbeat']:
                    if _heartbeat(state):
                        state['next_heartbeat'] = now + HEARTBEAT_INTERVAL
                    else:
                        if state.get('disabled_noted'):
                            state['disabled_noted'] = False
                            log.warning('内置打印工作站已停用（%s），代理进入空转；'
                                        '在 /print_routing 启用后恢复', BUILTIN_WS_CODE)
                        state['next_heartbeat'] = now + 30
                result = _claim_and_print(base_url, browser)
                _db.session.remove()
            if state.pop('schema_waiting', False):
                log.info('内置打印代理：数据库 schema 已就绪，恢复正常轮询')
            if result is not None:
                continue  # 刚打完一张，队列可能还有，立即再认领
        except Exception as exc:  # noqa: BLE001 守护线程不允许退出
            if _is_schema_not_ready(exc):
                # schema 未就绪：只打一条警告，转低频静默重试，不再每轮刷 traceback
                if not state.get('schema_waiting'):
                    state['schema_waiting'] = True
                    summary = str(exc).split('\n', 1)[0][:120]
                    log.warning('内置打印代理：数据库 schema 未就绪（%s）；转为每 %ss '
                                '静默重试，就绪后自动恢复，不影响 WMS 主服务',
                                summary, SCHEMA_WAIT_INTERVAL)
                time.sleep(SCHEMA_WAIT_INTERVAL)
                continue
            log.exception('内置打印代理本轮异常，%ss 后重试', POLL_INTERVAL)
        time.sleep(POLL_INTERVAL)


def start_local_print_agent(app, base_url: str):
    """启动内置本机打印代理后台线程；返回线程对象，未启动返回 None。

    启动条件（任一不满足则跳过）：
    - 环境变量 WMS_LOCAL_PRINT_AGENT 未显式关闭
    - 非测试模式（app.config TESTING）
    - 本进程尚未启动过（幂等）
    """
    global _started
    if os.environ.get('WMS_LOCAL_PRINT_AGENT', '').strip().lower() in _DISABLE_VALUES:
        log.info('WMS_LOCAL_PRINT_AGENT 已关闭，内置打印代理不启动')
        return None
    if app.config.get('TESTING'):
        return None
    with _started_lock:
        if _started:
            return None
        _started = True
    base_url = (os.environ.get('WMS_LOCAL_PRINT_BASE_URL') or base_url).rstrip('/')
    thread = threading.Thread(
        target=_agent_loop, args=(app, base_url),
        name='wms-local-print-agent', daemon=True)
    thread.start()
    log.info('内置本机打印代理已启动（base_url=%s，poll=%ss）', base_url, POLL_INTERVAL)
    return thread
