#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WMS Windows 本地打印代理（PRINT-ROUTING-F01-P3）。

部署在一台 Windows 工作站上，凭管理页（/print_routing）签发的工作站令牌，
循环执行：心跳上报 → 认领任务 → 调起浏览器静默打印 → 上报结果。

与服务器交互（agent API v1，均为 POST + Bearer 令牌，免账号密码）：
  POST /print_queue/api/v1/heartbeat           心跳 + 本地打印机列表
  POST /print_queue/api/v1/claim               认领本工作站下一条任务
  POST /print_queue/api/v1/jobs/<id>/complete  上报打印完成
  POST /print_queue/api/v1/jobs/<id>/fail      上报打印失败

打印原理：
  claim 返回 print_url（已附 10 分钟短时效 ptoken 与 autoprint=1）。
  代理以 Edge/Chrome 的 --kiosk-printing 模式打开该 URL，页面上的
  autoprint 脚本自动调起 window.print()，kiosk-printing 使浏览器跳过
  打印对话框、直接用「Windows 默认打印机」静默出纸；份数由服务端
  autoprint 脚本按 copies 循环触发。
  定向到指定打印机：打印前临时把 Windows 默认打印机切换为目标打印机，
  打印完成后恢复原默认打印机（--no-directed-printer 可关闭此行为）。

环境要求：Windows 10/11 + Python 3.9+（仅标准库，无需 pip 安装任何依赖）。

用法：
  python wms_print_agent.py --server http://192.168.1.10:5000 --token <工作站令牌>
  python wms_print_agent.py --config agent_config.json
  python wms_print_agent.py --list-printers          # 仅列出本机打印机（配置诊断用）
  python wms_print_agent.py ... --once               # 只跑一轮（联调测试用）

配置优先级：命令行参数 > 环境变量 > 配置文件 > 默认值。
  环境变量：WMS_AGENT_SERVER_URL / WMS_AGENT_TOKEN
  配置文件（--config，默认读取脚本同目录 agent_config.json，可不存在）：
  {
    "server_url": "http://192.168.1.10:5000",
    "token": "在工作站管理页复制",
    "poll_interval": 3,
    "heartbeat_interval": 60,
    "print_timeout": 120
  }

开机自启（推荐任务计划程序，勿用交互式登录脚本）：
  schtasks /Create /TN "WMS Print Agent" /SC ONSTART /RU SYSTEM ^
    /TR "\"C:\\Path\\To\\pythonw.exe\" C:\\wms_agent\\wms_print_agent.py --config C:\\wms_agent\\agent_config.json"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime

AGENT_VERSION = "1.0.0"

# 心跳在线窗口：服务端 WORKSTATION_ONLINE_WINDOW 为 5 分钟，
# 代理按其 1/3 周期上报，网络抖动丢一两次也不会掉线。
DEFAULT_HEARTBEAT_INTERVAL = 60
DEFAULT_POLL_INTERVAL = 3
DEFAULT_PRINT_TIMEOUT = 120

log = logging.getLogger("wms_print_agent")


# ==================== 配置 ====================

def load_config(args: argparse.Namespace) -> dict:
    """合并配置：命令行 > 环境变量 > 配置文件 > 默认值。"""
    cfg = {
        "server_url": "",
        "token": "",
        "poll_interval": DEFAULT_POLL_INTERVAL,
        "heartbeat_interval": DEFAULT_HEARTBEAT_INTERVAL,
        "print_timeout": DEFAULT_PRINT_TIMEOUT,
        "directed_printer": True,
    }
    path = args.config or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "agent_config.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in cfg})
            log.info("已加载配置文件 %s", path)
        except (OSError, ValueError) as e:
            log.warning("配置文件 %s 读取失败（%s），使用默认配置", path, e)
    if os.environ.get("WMS_AGENT_SERVER_URL"):
        cfg["server_url"] = os.environ["WMS_AGENT_SERVER_URL"]
    if os.environ.get("WMS_AGENT_TOKEN"):
        cfg["token"] = os.environ["WMS_AGENT_TOKEN"]
    for key in ("server_url", "token", "poll_interval", "heartbeat_interval",
                "print_timeout", "directed_printer"):
        value = getattr(args, key, None)
        if value is not None:
            cfg[key] = value
    cfg["server_url"] = str(cfg["server_url"] or "").rstrip("/")
    if not cfg["server_url"] or not cfg["token"]:
        raise SystemExit(
            "缺少 server_url / token：请用 --server/--token、环境变量或配置文件提供")
    return cfg


# ==================== HTTP ====================

def _join_url(server_url: str, path: str) -> str:
    """拼接服务端地址与 API 路径（server_url 已去除尾部斜杠）。"""
    return f"{server_url.rstrip('/')}/{path.lstrip('/')}"


def api_call(server_url: str, token: str, path: str, payload: dict | None = None):
    """调用 agent API，返回 (status_code, body_dict)；网络异常返回 (0, {})。"""
    req = urllib.request.Request(
        _join_url(server_url, path),
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, _parse_json(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, _parse_json(e.read())
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        log.error("无法连接服务器 %s：%s", server_url, e)
        return 0, {}


def _parse_json(raw: bytes) -> dict:
    try:
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (UnicodeDecodeError, ValueError):
        return {}


# ==================== Windows 打印机操作 ====================

def _run_powershell(command: str) -> str:
    """执行 PowerShell 命令并返回 stdout（非 Windows 或执行失败返回空串）。"""
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("PowerShell 执行失败：%s", e)
        return ""


def _map_printer_status(printer_status, work_offline) -> str:
    """Win32_Printer 状态值 → 服务端约定（ready/error）。

    PrinterStatus：3=空闲 4=打印中 5=预热 7=脱机；其余视为就绪。
    """
    if work_offline or printer_status == 7:
        return "error"
    return "ready"


def enumerate_printers() -> list[dict]:
    """枚举本机打印机，转换为心跳上报格式 [{system_name, status, is_default}]。"""
    raw = _run_powershell(
        "Get-CimInstance Win32_Printer | Select-Object Name, Default, "
        "PrinterStatus, WorkOffline | ConvertTo-Json -Compress")
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    printers = data if isinstance(data, list) else [data]
    result = []
    for p in printers:
        name = str(p.get("Name") or "").strip()
        if not name or len(name) > 200:
            continue
        result.append({
            "system_name": name,
            "status": _map_printer_status(p.get("PrinterStatus"), p.get("WorkOffline")),
            "is_default": bool(p.get("Default")),
        })
    return result


def get_default_printer() -> str:
    """读取当前 Windows 默认打印机名（读不到返回空串）。"""
    raw = _run_powershell(
        "(Get-CimInstance Win32_Printer -Filter 'Default=True').Name")
    return raw.strip().strip('"')


def set_default_printer(name: str) -> bool:
    """临时切换 Windows 默认打印机（WScript.Network COM，无需管理员权限）。"""
    if not name:
        return False
    ok = bool(_run_powershell(
        f"(New-Object -ComObject WScript.Network).SetDefaultPrinter('{name}')"))
    if ok:
        log.info("默认打印机已切换为：%s", name)
    else:
        log.warning("切换默认打印机失败：%s（将使用当前默认打印机出纸）", name)
    return ok


# ==================== 浏览器静默打印 ====================

def find_browser() -> str | None:
    """定位 Edge / Chrome 可执行文件（kiosk-printing 支持静默出纸）。"""
    candidates = []
    if os.name == "nt":
        candidates = [
            os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        ]
    else:  # 开发联调：Linux 上找 chromium/chrome/google-chrome
        candidates = [shutil.which(n) or "" for n in
                      ("microsoft-edge", "chromium", "chromium-browser", "google-chrome")]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return shutil.which("msedge") or shutil.which("chrome") or None


def print_via_browser(browser: str, url: str, timeout: int) -> bool:
    """以 kiosk-printing 打开打印页并等待退出，返回是否正常结束。

    使用独立 user-data-dir：不污染操作员日常浏览器配置，且允许代理
    并行/重复拉起浏览器实例；页面 autoprint 完成后代理主动结束进程。
    """
    user_data_dir = os.path.join(tempfile.gettempdir(), "wms_print_agent_profile")
    cmd = [browser, "--kiosk-printing", f"--app={url}",
           f"--user-data-dir={user_data_dir}",
           "--no-first-run", "--disable-extensions"]
    log.info("调起浏览器打印：%s", " ".join(cmd[:4]))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.error("浏览器启动失败：%s", e)
        return False
    try:
        proc.wait(timeout=timeout)
        log.info("浏览器打印进程已退出（code=%s）", proc.returncode)
        return True
    except subprocess.TimeoutExpired:
        log.warning("打印超时（%ss），结束浏览器进程", timeout)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False


# ==================== 主流程 ====================

def send_heartbeat(cfg: dict) -> bool:
    """上报心跳与打印机列表，返回服务器是否接受。"""
    payload = {"version": AGENT_VERSION, "printers": enumerate_printers()}
    code, body = api_call(cfg["server_url"], cfg["token"],
                          "/print_queue/api/v1/heartbeat", payload)
    if code == 200 and body.get("status") == "success":
        data = body.get("data") or {}
        log.info("心跳成功：本机打印机 %s 台（在线 %s）",
                 len(payload["printers"]), data.get("printers_online", "?"))
        return True
    if code == 401:
        log.error("工作站令牌无效或已停用：请在 /print_routing 管理页核对令牌")
    else:
        log.warning("心跳失败：HTTP %s %s", code, body.get("msg", ""))
    return False


def claim_job(cfg: dict) -> dict | None:
    """认领一条任务，返回 job 字典；无任务或失败返回 None。"""
    code, body = api_call(cfg["server_url"], cfg["token"],
                          "/print_queue/api/v1/claim", {})
    if code == 200 and body.get("status") == "success":
        return body.get("job") or None
    if code == 401:
        log.error("工作站令牌无效或已停用：请在 /print_routing 管理页核对令牌")
    elif code != 200 or body.get("status") != "empty":
        log.warning("认领失败：HTTP %s %s", code, body.get("msg", ""))
    return None


def report_result(cfg: dict, job_id: int, ok: bool, error_msg: str = "") -> None:
    """上报打印结果（complete/fail）；失败仅记日志，不影响主循环。"""
    path = f"/print_queue/api/v1/jobs/{job_id}/{'complete' if ok else 'fail'}"
    code, body = api_call(cfg["server_url"], cfg["token"], path,
                          {"error_msg": error_msg or None})
    if code == 200 and body.get("status") == "success":
        log.info("任务 #%s 已上报%s", job_id, "完成" if ok else "失败")
    else:
        log.error("任务 #%s 结果上报失败：HTTP %s %s", job_id, code, body.get("msg", ""))


def process_job(cfg: dict, job: dict, browser: str) -> None:
    """处理单条任务：定向切打印机 → 浏览器打印 → 恢复默认打印机 → 上报。"""
    job_id = job.get("id")
    url = _join_url(cfg["server_url"], job.get("print_url", ""))
    target_printer = job.get("printer_system_name") or ""
    log.info("开始打印任务 #%s：%s 份数=%s 目标打印机=%s",
             job_id, job.get("job_type"), job.get("copies"), target_printer or "（默认）")

    switched_from = ""
    if cfg["directed_printer"] and target_printer:
        switched_from = get_default_printer()
        if switched_from == target_printer:
            switched_from = ""  # 本来就是目标打印机，无需恢复
            log.info("当前默认打印机即目标打印机：%s", target_printer)
        elif not set_default_printer(target_printer):
            switched_from = ""  # 切换失败，按当前默认打印机出纸
    try:
        ok = print_via_browser(browser, url, int(cfg["print_timeout"]))
        report_result(cfg, job_id, ok,
                      "" if ok else f"浏览器打印超时（{cfg['print_timeout']}s）")
    except Exception as e:  # noqa: BLE001 代理进程不允许因单任务异常退出
        log.exception("任务 #%s 处理异常", job_id)
        report_result(cfg, job_id, False, f"代理异常：{e}")
    finally:
        if switched_from:
            set_default_printer(switched_from)


def run_agent(cfg: dict, once: bool = False) -> None:
    """代理主循环：心跳按期上报，其余时间轮询认领并同步打印。"""
    browser = find_browser()
    if not browser:
        log.warning("未找到 Edge/Chrome，将退化为系统默认程序打开打印页（可能非静默）")
    next_heartbeat = 0.0  # 立即先报一次心跳
    while True:
        now = time.monotonic()
        if now >= next_heartbeat:
            if send_heartbeat(cfg):
                next_heartbeat = now + float(cfg["heartbeat_interval"])
            else:  # 失败退避，避免疯狂重试
                next_heartbeat = now + min(float(cfg["heartbeat_interval"]), 30)
        job = claim_job(cfg)
        if job:
            if browser:
                process_job(cfg, job, browser)
            else:
                import webbrowser
                webbrowser.open(_join_url(cfg["server_url"], job.get("print_url", "")))
                report_result(cfg, job["id"], True, "无浏览器内核，已用系统默认程序打开")
            if once:
                break
            continue  # 队列可能还有任务，立即再认领
        if once:
            break
        time.sleep(float(cfg["poll_interval"]))


def setup_logging(verbose: bool, log_file: str | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WMS Windows 本地打印代理")
    parser.add_argument("--server", dest="server_url", help="服务器地址，如 http://192.168.1.10:5000")
    parser.add_argument("--token", help="工作站令牌（/print_routing 管理页复制）")
    parser.add_argument("--config", help="配置文件路径（默认脚本同目录 agent_config.json）")
    parser.add_argument("--poll-interval", type=int, dest="poll_interval",
                        help="认领轮询间隔秒（默认 3）")
    parser.add_argument("--heartbeat-interval", type=int, dest="heartbeat_interval",
                        help="心跳间隔秒（默认 60，服务端在线窗口 300）")
    parser.add_argument("--print-timeout", type=int, dest="print_timeout",
                        help="单任务浏览器打印超时秒（默认 120）")
    parser.add_argument("--no-directed-printer", action="store_false",
                        dest="directed_printer", help="不切换默认打印机（统一用当前默认打印机）")
    parser.add_argument("--once", action="store_true", help="只跑一轮（联调用）")
    parser.add_argument("--list-printers", action="store_true", help="列出本机打印机后退出")
    parser.add_argument("--log-file", help="日志文件路径（默认只输出到控制台）")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if args.list_printers:
        setup_logging(True, None)
        for p in enumerate_printers():
            mark = " *" if p["is_default"] else ""
            print(f"{p['system_name']}{mark}  [{p['status']}]")
        if os.name != "nt":
            print("（当前非 Windows 系统，仅返回空列表）")
        return 0
    setup_logging(args.verbose, args.log_file)
    cfg = load_config(args)
    log.info("WMS 打印代理 v%s 启动：server=%s poll=%ss heartbeat=%ss",
             AGENT_VERSION, cfg["server_url"], cfg["poll_interval"], cfg["heartbeat_interval"])
    try:
        run_agent(cfg, once=args.once)
    except KeyboardInterrupt:
        log.info("收到中断，代理退出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
