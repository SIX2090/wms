#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local Windows WeChat sender helper for WMS.

This helper intentionally binds to 127.0.0.1 only. It receives a PNG from WMS,
copies it to the Windows clipboard, uses the already-open WeChat window,
searches the configured contact/group, pastes the image, and by default leaves
the final send for manual confirmation.
"""

from __future__ import annotations

import ctypes
import io
import json
import os
import sys
import threading
import time
import traceback
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse
# cgi 模块在 Python 3.13 被移除，改用标准库 email 解析 multipart/form-data
from email.parser import BytesParser
from email.policy import default as default_email_policy

import requests

try:
    from PIL import Image
except Exception:  # pragma: no cover - reported in health check.
    Image = None


HOST = "127.0.0.1"
PORT = int(os.environ.get("WMS_WECHAT_HELPER_PORT", "8765"))
WMS_BASE_URL = os.environ.get("WMS_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
WMS_HELPER_TOKEN = os.environ.get("WECHAT_HELPER_TOKEN", "change-this-wechat-helper-token")
POLL_ENABLED = os.environ.get("WMS_WECHAT_HELPER_POLL", "0").lower() in {"1", "true", "yes"}
POLL_INTERVAL = max(5, int(os.environ.get("WMS_WECHAT_HELPER_INTERVAL", "30")))


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
gdi32 = ctypes.windll.gdi32
psapi = ctypes.windll.psapi

CF_DIB = 8
GMEM_MOVEABLE = 0x0002
SW_RESTORE = 9
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_VM_READ = 0x0010
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_ESCAPE = 0x1B
VK_F = 0x46
VK_V = 0x56
VK_A = 0x41

user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL
# 显式声明 GlobalFree 签名，否则 ctypes 默认按 int 返回可能截断 64 位句柄
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.restype = wintypes.HGLOBAL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
psapi.GetModuleBaseNameW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
psapi.GetModuleBaseNameW.restype = wintypes.DWORD

ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong


class KEYBDINPUT(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _pack_ = 8
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _pack_ = 8
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send_input(*inputs: INPUT) -> None:
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        raise RuntimeError(f"SendInput failed, sent={sent}, last_error={kernel32.GetLastError()}")


def _key_input(vk: int, keyup: bool = False) -> INPUT:
    flags = KEYEVENTF_KEYUP if keyup else 0
    return INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(vk, 0, flags, 0, 0)))


def press_key(vk: int) -> None:
    _send_input(_key_input(vk), _key_input(vk, True))


def hotkey(*keys: int) -> None:
    inputs = []
    for key in keys:
        inputs.append(_key_input(key))
    for key in reversed(keys):
        inputs.append(_key_input(key, True))
    _send_input(*inputs)
    time.sleep(0.15)


def type_text(text: str) -> None:
    inputs = []
    for char in text:
        code = ord(char)
        inputs.append(INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE, 0, 0))))
        inputs.append(INPUT(type=INPUT_KEYBOARD, union=INPUTUNION(ki=KEYBDINPUT(0, code, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0))))
    for index in range(0, len(inputs), 32):
        _send_input(*inputs[index:index + 32])
        time.sleep(0.02)


def set_clipboard_dib(image_bytes: bytes) -> None:
    if Image is None:
        raise RuntimeError("Pillow is not installed")
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    dib = io.BytesIO()
    image.save(dib, "BMP")
    data = dib.getvalue()[14:]

    if not user32.OpenClipboard(None):
        raise RuntimeError("OpenClipboard failed")
    handle = 0
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not handle:
            raise RuntimeError("GlobalAlloc failed")
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            # GlobalLock 失败必须立即释放 GlobalAlloc 出来的内存，否则泄漏
            kernel32.GlobalFree(handle)
            handle = 0
            raise RuntimeError("GlobalLock failed")
        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        # SetClipboardData 成功后系统接管该内存所有权，不能再 GlobalFree；
        # 失败时调用方负责释放，否则每次失败都会泄漏一次 GlobalAlloc 内存
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            handle = 0
            raise RuntimeError("SetClipboardData failed")
        # 成功：交出所有权，避免 finally 再次释放
        handle = 0
    finally:
        user32.CloseClipboard()
        # 仅当异常路径或某步失败时，handle 才非 0，此时需要释放
        if handle:
            kernel32.GlobalFree(handle)


def _window_title(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _window_class(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _window_pid(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _process_name(pid: int) -> str:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(handle, None, buffer, len(buffer)):
            return buffer.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _window_rect(hwnd: int) -> tuple[int, int, int, int, int, int]:
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = int(rect.right - rect.left)
    height = int(rect.bottom - rect.top)
    return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom), width, height


def enum_windows() -> list[tuple[int, int, str, str, tuple[int, int, int, int, int, int]]]:
    items: list[tuple[int, int, str, str, tuple[int, int, int, int, int, int]]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, lparam: int) -> bool:
        items.append((int(hwnd), _window_pid(hwnd), _window_class(hwnd), _window_title(hwnd), _window_rect(hwnd)))
        return True

    user32.EnumWindows(callback, 0)
    return items


def find_wechat_window() -> int | None:
    candidates = []
    ignored_classes = {
        'Base_PowerMessageWindow',
        'Chrome_SystemMessageWindow',
        'DisplayICC_SystemMessageWindow',
        'IME',
        'MSCTFIME UI',
        'Qt51514WxTrayIconMessageWindowClass',
        'Sogou_TSF_UI',
        'SoWB_UI',
        'SoWB_Comp',
    }

    for hwnd, pid, class_name, title, rect in enum_windows():
        title_text = title or ""
        class_text = class_name or ""
        name = _process_name(pid).lower()
        is_wechat_process = "wechat" in name or "weixin" in name
        has_wechat_title = "微信" in title_text or "WeChat" in title_text or "Weixin" in title_text
        has_wechat_class = "WeChat" in class_text or "Weixin" in class_text or class_text.startswith("Qt")
        if not (is_wechat_process or has_wechat_title or has_wechat_class):
            continue

        left, top, right, bottom, width, height = rect
        if width <= 0 or height <= 0:
            continue
        if class_text in ignored_classes:
            continue
        # Ignore small login/tip windows such as "该账号已登录"; use the real main
        # chat window, which is large enough to contain the conversation list.
        if width < 520 or height < 420:
            continue

        score = width * height
        if class_text == "WeChatMainWndForPC":
            score += 10_000_000
        if name == "weixin.exe":
            score += 2_000_000
        if has_wechat_title:
            score += 1_000_000
        if "Chrome_WidgetWin" in class_text:
            score += 500_000
        candidates.append((score, hwnd))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def activate_wechat() -> int:
    hwnd = find_wechat_window()
    if not hwnd:
        raise RuntimeError("未找到已打开的微信主窗口，请先登录微信并把微信主窗口打开到桌面，助手不会自动启动微信")

    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return hwnd


def open_contact(receiver_search_key: str) -> None:
    receiver_search_key = (receiver_search_key or "").strip()
    if not receiver_search_key:
        raise RuntimeError("receiver_search_key is empty")

    hotkey(VK_CONTROL, VK_F)
    time.sleep(0.2)
    hotkey(VK_CONTROL, VK_A)
    type_text(receiver_search_key)
    time.sleep(0.8)
    press_key(VK_RETURN)
    time.sleep(0.8)


def paste_image_and_optionally_send(image_bytes: bytes, receiver_search_key: str, auto_send: bool) -> str:
    set_clipboard_dib(image_bytes)
    activate_wechat()
    open_contact(receiver_search_key)
    hotkey(VK_CONTROL, VK_V)
    time.sleep(0.5)
    if auto_send:
        press_key(VK_RETURN)
        return "sent"
    return "ready"


def send_image_task(image_bytes: bytes, task: dict) -> tuple[str, str]:
    receiver_search_key = (
        task.get("receiver_search_key")
        or task.get("receiver_name")
        or task.get("receiver_wechat_id")
        or ""
    )
    auto_send = bool(task.get("auto_send"))
    status = paste_image_and_optionally_send(image_bytes, receiver_search_key, auto_send)
    if status == "sent":
        return "sent", f"已发送给：{receiver_search_key}"
    return "ready", f"已粘贴到微信会话：{receiver_search_key}，请人工确认发送"


def helper_headers() -> dict[str, str]:
    return {"X-Wechat-Helper-Token": WMS_HELPER_TOKEN}


def absolute_wms_url(url: str) -> str:
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return urljoin(WMS_BASE_URL + "/", url.lstrip("/"))


def poll_once() -> int:
    tasks_url = f"{WMS_BASE_URL}/api/wechat_helper/tasks"
    response = requests.get(tasks_url, headers=helper_headers(), params={"limit": 3}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "success":
        raise RuntimeError(payload.get("msg") or "task query failed")
    tasks = payload.get("tasks") or []
    processed = 0
    for task in tasks:
        task_id = task.get("id")
        report_url = absolute_wms_url(task.get("report_url") or f"/api/wechat_helper/task/{task_id}/report")
        try:
            image_url = absolute_wms_url(task.get("image_url") or f"/api/wechat_helper/task/{task_id}/image")
            image_response = requests.get(image_url, headers=helper_headers(), timeout=30)
            image_response.raise_for_status()
            status, message = send_image_task(image_response.content, task)
            requests.post(report_url, headers=helper_headers(), json={"status": status, "msg": message}, timeout=20).raise_for_status()
            processed += 1
            print(f"[poll] task {task_id}: {status} {message}", flush=True)
        except Exception as exc:
            message = f"本机微信助手发送失败：{exc}"
            try:
                requests.post(report_url, headers=helper_headers(), json={"status": "failed", "msg": message}, timeout=20)
            except Exception:
                pass
            print(f"[poll] task {task_id} failed: {exc}", flush=True)
    return processed


def poll_loop() -> None:
    while True:
        try:
            poll_once()
        except Exception as exc:
            print(f"[poll] {exc}", flush=True)
        time.sleep(POLL_INTERVAL)


def parse_multipart(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], bytes]:
    """解析 multipart/form-data 请求体。

    原实现依赖 cgi.FieldStorage，但 cgi 模块自 Python 3.13 起被移除。
    这里改用标准库 email 模块构造完整 MIME 消息后遍历 parts，行为与
    FieldStorage 等价：text 字段进入 fields，image 字段读取为 bytes。
    """
    ctype = handler.headers.get("content-type", "")
    if not ctype.startswith("multipart/form-data"):
        raise RuntimeError("Content-Type must be multipart/form-data")
    try:
        content_length = int(handler.headers.get("content-length", "0"))
    except ValueError:
        content_length = 0
    if content_length <= 0:
        raise RuntimeError("Content-Length missing or invalid")
    body = handler.rfile.read(content_length)
    # email 解析器需要完整的 RFC 822 消息（含头部），把 HTTP 头拼到 body 前
    raw = b"Content-Type: " + ctype.encode("ascii") + b"\r\n\r\n" + body
    message = BytesParser(policy=default_email_policy).parsebytes(raw)

    fields: dict[str, str] = {}
    image_bytes = b""
    for part in message.iter_parts():
        if not part.is_multipart():
            name = part.get_param("name", header="content-disposition")
            if not name:
                continue
            payload = part.get_payload(decode=True) or b""
            filename = part.get_filename()
            if filename is not None or name == "image":
                # 文件类型字段
                if name == "image":
                    image_bytes = payload
            else:
                # 普通文本字段，按 utf-8 解码
                try:
                    fields[name] = payload.decode("utf-8")
                except UnicodeDecodeError:
                    fields[name] = payload.decode("utf-8", errors="replace")
    if not image_bytes:
        raise RuntimeError("image file is required")
    return fields, image_bytes


class Handler(BaseHTTPRequestHandler):
    server_version = "WMSWeChatHelper/1.0"

    def _json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/health":
            self._json(404, {"status": "error", "msg": "not found"})
            return
        self._json(200, {
            "status": "ok",
            "wechat_window_found": bool(find_wechat_window()),
            "auto_send_default": False,
            "poll_enabled": POLL_ENABLED,
            "wms_base_url": WMS_BASE_URL,
            "poll_interval": POLL_INTERVAL,
        })

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/send":
            self._json(404, {"status": "error", "msg": "not found"})
            return
        try:
            fields, image_bytes = parse_multipart(self)
            task = {
                "receiver_search_key": fields.get("receiver_search_key") or "",
                "receiver_name": fields.get("receiver_name") or "",
                "receiver_wechat_id": fields.get("receiver_wechat_id") or "",
                "auto_send": str(fields.get("auto_send") or "0").lower() in {"1", "true", "yes", "on"},
            }
            status, message = send_image_task(image_bytes, task)
            self._json(200, {"status": status, "msg": message})
        except Exception as exc:
            traceback.print_exc()
            self._json(500, {"status": "error", "msg": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args))
        sys.stdout.flush()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if POLL_ENABLED:
        thread = threading.Thread(target=poll_loop, name="wechat-task-poller", daemon=True)
        thread.start()
        print(f"Polling WMS tasks from {WMS_BASE_URL} every {POLL_INTERVAL}s", flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"WMS WeChat helper listening on http://{HOST}:{PORT}", flush=True)
    print("Default mode: use already-open WeChat, paste image, and wait for manual confirmation.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
