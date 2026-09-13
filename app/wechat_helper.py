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
import logging
import os
import sys
import threading
import time
import traceback

logger = logging.getLogger(__name__)
from ctypes import wintypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urljoin, urlparse
# cgi 妯″潡鍦?Python 3.13 琚Щ闄わ紝鏀圭敤鏍囧噯搴?email 瑙ｆ瀽 multipart/form-data
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
WMS_HELPER_TOKEN = os.environ.get("WECHAT_HELPER_TOKEN")
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
# 鏄惧紡澹版槑 GlobalFree 绛惧悕锛屽惁鍒?ctypes 榛樿鎸?int 杩斿洖鍙兘鎴柇 64 浣嶅彞鏌?kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
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
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND


class _SendError(RuntimeError):
    """甯︽満鍣ㄥ彲璇婚敊璇爜鐨勫彂閫佸け璐ワ紝渚?WMS 涓绘湇鍔℃寜 code 褰掔被锛堟浛浠ｈ剢寮辩殑鍏抽敭璇嶅尮閰嶏級銆?""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# 鍓创鏉?/ 閿洏杈撳叆 / 鍓嶅彴鐒︾偣鏄叏灞€璧勬簮锛歍hreadingHTTPServer 姣忚姹備竴绾跨▼锛?# 骞跺彂 /send 浼氫簰鐩告姠鐒︾偣銆佷覆鍓创鏉垮鑷村彂閿欏浘鍙戦敊浜猴紝蹇呴』鍏ㄥ眬涓茶鍖栥€?SEND_LOCK = threading.Lock()


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
            # GlobalLock 澶辫触蹇呴』绔嬪嵆閲婃斁 GlobalAlloc 鍑烘潵鐨勫唴瀛橈紝鍚﹀垯娉勬紡
            kernel32.GlobalFree(handle)
            handle = 0
            raise RuntimeError("GlobalLock failed")
        try:
            ctypes.memmove(ptr, data, len(data))
        finally:
            kernel32.GlobalUnlock(handle)
        # SetClipboardData 鎴愬姛鍚庣郴缁熸帴绠¤鍐呭瓨鎵€鏈夋潈锛屼笉鑳藉啀 GlobalFree锛?        # 澶辫触鏃惰皟鐢ㄦ柟璐熻矗閲婃斁锛屽惁鍒欐瘡娆″け璐ラ兘浼氭硠婕忎竴娆?GlobalAlloc 鍐呭瓨
        if not user32.SetClipboardData(CF_DIB, handle):
            kernel32.GlobalFree(handle)
            handle = 0
            raise RuntimeError("SetClipboardData failed")
        # 鎴愬姛锛氫氦鍑烘墍鏈夋潈锛岄伩鍏?finally 鍐嶆閲婃斁
        handle = 0
    finally:
        user32.CloseClipboard()
        # 浠呭綋寮傚父璺緞鎴栨煇姝ュけ璐ユ椂锛宧andle 鎵嶉潪 0锛屾鏃堕渶瑕侀噴鏀?        if handle:
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
        has_wechat_title = "寰俊" in title_text or "WeChat" in title_text or "Weixin" in title_text
        has_wechat_class = "WeChat" in class_text or "Weixin" in class_text or class_text.startswith("Qt")
        if not (is_wechat_process or has_wechat_title or has_wechat_class):
            continue

        left, top, right, bottom, width, height = rect
        if width <= 0 or height <= 0:
            continue
        if class_text in ignored_classes:
            continue
        # Ignore small login/tip windows such as "璇ヨ处鍙峰凡鐧诲綍"; use the real main
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
        raise _SendError(
            "wechat_window_not_found",
            "鏈壘鍒板凡鎵撳紑鐨勫井淇′富绐楀彛锛岃鍏堢櫥褰曞井淇″苟鎶婂井淇′富绐楀彛鎵撳紑鍒版闈紝鍔╂墜涓嶄細鑷姩鍚姩寰俊",
        )

    user32.ShowWindow(hwnd, SW_RESTORE)
    time.sleep(0.2)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return hwnd


def _ensure_foreground(hwnd: int) -> None:
    """纭寰俊涓荤獥鍙ｄ粛鍦ㄥ墠鍙帮紝鍚﹀垯涓鏈鑷姩鍖栥€?
    閿佸睆銆佽繙绋嬫闈㈡柇寮€銆佸脊绐楁姠鐒︾偣鏃?SendInput 浼氭妸 Ctrl+V/鍥炶溅鎵撹繘鍒殑绐楀彛锛?    鍙兘鎶婂叆搴撳崟鍥剧墖绮樿创/鍙戦€佸埌閿欒浣嶇疆锛屽繀椤诲湪姣忎釜鍏抽敭姝ラ鍓嶆牎楠屻€?    """
    fg = int(user32.GetForegroundWindow() or 0)
    if not fg:
        raise _SendError("focus_lost", "鏃犳硶鑾峰彇鍓嶅彴绐楀彛锛堝彲鑳藉凡閿佸睆鎴栦細璇濇柇寮€锛夛紝宸蹭腑姝㈠彂閫?)
    if fg != hwnd and _window_pid(fg) != _window_pid(hwnd):
        raise _SendError("focus_lost", "寰俊绐楀彛涓嶅湪鍓嶅彴锛堢劍鐐硅鍏朵粬绐楀彛鎶㈣蛋锛夛紝宸蹭腑姝㈠彂閫?)


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
    # 鍏堟牎楠屾帴鏀朵汉鍐嶇鍓创鏉?寰俊绐楀彛锛屽け璐ユ椂涓嶄骇鐢熶换浣?UI 鍓綔鐢紙渚夸簬瀹夊叏閲嶈瘯锛?    receiver_search_key = (receiver_search_key or "").strip()
    if not receiver_search_key:
        raise _SendError("no_receiver", "receiver_search_key is empty")
    try:
        set_clipboard_dib(image_bytes)
    except Exception as exc:
        raise _SendError("clipboard_failed", f"鍐欏叆鍓创鏉垮け璐ワ細{exc}") from exc
    hwnd = activate_wechat()
    _ensure_foreground(hwnd)
    try:
        open_contact(receiver_search_key)
    except _SendError:
        raise
    except Exception as exc:
        raise _SendError("open_contact_failed", f"鎵撳紑寰俊浼氳瘽澶辫触锛歿exc}") from exc
    _ensure_foreground(hwnd)
    try:
        hotkey(VK_CONTROL, VK_V)
    except Exception as exc:
        raise _SendError("paste_failed", f"绮樿创鍥剧墖澶辫触锛歿exc}") from exc
    time.sleep(0.5)
    if auto_send:
        _ensure_foreground(hwnd)
        try:
            press_key(VK_RETURN)
        except Exception as exc:
            raise _SendError("send_key_failed", f"鍥炶溅鍙戦€佸け璐ワ細{exc}") from exc
        return "sent"
    return "ready"


def send_image_task(image_bytes: bytes, task: dict) -> tuple[str, str, str]:
    """鎵ц涓€娆″彂閫佷换鍔★紝杩斿洖 (status, code, message)銆?
    status: sent / ready / error锛沜ode 涓烘満鍣ㄥ彲璇婚敊璇爜锛堟垚鍔熸椂涓?ok锛夈€?    鍏ㄧ▼鎸佹湁 SEND_LOCK锛屼覆琛屽寲鍓创鏉夸笌閿洏杈撳叆锛岄伩鍏嶅苟鍙戜换鍔′簰鐩镐覆鎵般€?    """
    with SEND_LOCK:
        receiver_search_key = (
            task.get("receiver_search_key")
            or task.get("receiver_name")
            or task.get("receiver_wechat_id")
            or ""
        )
        auto_send = bool(task.get("auto_send"))
        try:
            status = paste_image_and_optionally_send(image_bytes, receiver_search_key, auto_send)
        except _SendError as exc:
            return "error", exc.code, str(exc)
        if status == "sent":
            return "sent", "ok", f"宸插彂閫佺粰锛歿receiver_search_key}"
        return "ready", "ok", f"宸茬矘璐村埌寰俊浼氳瘽锛歿receiver_search_key}锛岃浜哄伐纭鍙戦€?


def helper_headers() -> dict[str, str]:
    # 鏈厤缃?token 鏃舵嫆缁濆彂璧疯姹傦紝閬垮厤浣跨敤寮遍粯璁ゅ€煎鑷翠换鎰忓鎴风鍙Е鍙戞湰鏈哄井淇″彂閫?    if not WMS_HELPER_TOKEN:
        raise RuntimeError("WECHAT_HELPER_TOKEN 鏈厤缃紝鎷掔粷浠ユ棤璁よ瘉鏂瑰紡璋冪敤 WMS 涓绘湇鍔?)
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
            status, code, message = send_image_task(image_response.content, task)
            requests.post(report_url, headers=helper_headers(), json={"status": status, "code": code, "msg": message}, timeout=20).raise_for_status()
            processed += 1
            logger.info("[poll] task %s: %s(%s) %s", task_id, status, code, message)
        except Exception as exc:
            message = f"鏈満寰俊鍔╂墜鍙戦€佸け璐ワ細{exc}"
            try:
                requests.post(report_url, headers=helper_headers(), json={"status": "failed", "msg": message}, timeout=20)
            except Exception:
                pass
            logger.error("[poll] task %s failed: %s", task_id, exc)
    return processed


def poll_loop() -> None:
    while True:
        try:
            poll_once()
        except Exception as exc:
            logger.error("[poll] %s", exc)
        time.sleep(POLL_INTERVAL)


def parse_multipart(handler: BaseHTTPRequestHandler) -> tuple[dict[str, str], bytes]:
    """瑙ｆ瀽 multipart/form-data 璇锋眰浣撱€?
    鍘熷疄鐜颁緷璧?cgi.FieldStorage锛屼絾 cgi 妯″潡鑷?Python 3.13 璧疯绉婚櫎銆?    杩欓噷鏀圭敤鏍囧噯搴?email 妯″潡鏋勯€犲畬鏁?MIME 娑堟伅鍚庨亶鍘?parts锛岃涓轰笌
    FieldStorage 绛変环锛歵ext 瀛楁杩涘叆 fields锛宨mage 瀛楁璇诲彇涓?bytes銆?    """
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
    # email 瑙ｆ瀽鍣ㄩ渶瑕佸畬鏁寸殑 RFC 822 娑堟伅锛堝惈澶撮儴锛夛紝鎶?HTTP 澶存嫾鍒?body 鍓?    raw = b"Content-Type: " + ctype.encode("ascii") + b"\r\n\r\n" + body
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
                # 鏂囦欢绫诲瀷瀛楁
                if name == "image":
                    image_bytes = payload
            else:
                # 鏅€氭枃鏈瓧娈碉紝鎸?utf-8 瑙ｇ爜
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

    def _check_auth(self) -> bool:
        """鏍￠獙璇锋眰鏂规槸鍚︽寔鏈夋纭殑 helper token銆?
        /send 绔偣浼氳Е鍙戞湰鏈哄井淇″彂閫佸浘鐗囷紝蹇呴』涓?WMS 涓绘湇鍔♀啋helper 鐨勫嚭绔?        璇锋眰浣跨敤鍚屼竴 token锛岄伩鍏嶆湰鏈轰换鎰忚繘绋嬶紙鍖呮嫭鎭舵剰杞欢锛夌洿鎺?POST 鍗冲彲
        鍊熷姪鏈姪鎵嬪悜浠绘剰寰俊鑱旂郴浜哄彂閫佸浘鐗囥€倀oken 鏈厤缃椂涓€寰嬫嫆缁濄€?        """
        if not WMS_HELPER_TOKEN:
            return False
        incoming = self.headers.get("X-Wechat-Helper-Token", "")
        if not incoming:
            return False
        # 浣跨敤 hmac.compare_digest 閬垮厤鏃跺簭鏀诲嚮
        import hmac
        return hmac.compare_digest(incoming, WMS_HELPER_TOKEN)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            # /health 涓嶈Е鍙戝彂閫侊紝鍙斁琛屾棤璁よ瘉璁块棶浠ヤ究鏈湴鎺㈡椿
            self._json(200, {
                "status": "ok",
                "wechat_window_found": bool(find_wechat_window()),
                "auto_send_default": False,
                "poll_enabled": POLL_ENABLED,
                "wms_base_url": WMS_BASE_URL,
                "poll_interval": POLL_INTERVAL,
            })
            return
        # 鍏跺畠 GET 璺緞瑕佹眰璁よ瘉锛堜笌 POST /send 涓€鑷达級
        if not self._check_auth():
            self._json(403, {"status": "error", "msg": "forbidden: missing or invalid X-Wechat-Helper-Token"})
            return
        self._json(404, {"status": "error", "msg": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/send":
            self._json(404, {"status": "error", "msg": "not found"})
            return
        # /send 浼氱湡瀹炶Е鍙戞湰鏈哄井淇″彂閫佸浘鐗囷紝蹇呴』鏍￠獙 helper token
        if not self._check_auth():
            self._json(403, {"status": "error", "msg": "forbidden: missing or invalid X-Wechat-Helper-Token"})
            return
        try:
            fields, image_bytes = parse_multipart(self)
            task = {
                "receiver_search_key": fields.get("receiver_search_key") or "",
                "receiver_name": fields.get("receiver_name") or "",
                "receiver_wechat_id": fields.get("receiver_wechat_id") or "",
                "auto_send": str(fields.get("auto_send") or "0").lower() in {"1", "true", "yes", "on"},
            }
            status, code, message = send_image_task(image_bytes, task)
            self._json(200, {"status": status, "code": code, "msg": message})
        except Exception as exc:`r`n            logger.exception("微信发送失败")`r`n            self._json(500, {"status": "error", "code": "send_failed", "msg": "微信发送失败，请检查微信窗口和剪贴板状态后重试"})

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), fmt % args))
        sys.stdout.flush()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    if POLL_ENABLED:
        # poll 妯″紡闇€瑕佷富鍔ㄥ悜 WMS 涓绘湇鍔¤璇佹媺鍙栦换鍔★紝鏈厤缃?token 鏃舵嫆缁濆惎鍔紝
        # 閬垮厤浣跨敤寮遍粯璁?token 瀵艰嚧浠绘剰浜哄彲瑙﹀彂鏈満寰俊鍙戦€佸浘鐗?        if not WMS_HELPER_TOKEN:
            logger.critical("[FATAL] 宸插惎鐢ㄨ疆璇㈡ā寮?POLL_ENABLED=1)浣嗘湭閰嶇疆 WECHAT_HELPER_TOKEN 鐜鍙橀噺锛屾嫆缁濆惎鍔ㄣ€?)
            logger.critical("        璇峰湪鍚姩鍓嶈缃?WECHAT_HELPER_TOKEN锛堜笌 WMS 涓绘湇鍔?instance/wechat_helper_token 鏂囦欢涓殑鍊间竴鑷达級銆?)
            sys.exit(1)
        thread = threading.Thread(target=poll_loop, name="wechat-task-poller", daemon=True)
        thread.start()
        logger.info("Polling WMS tasks from %s every %ss", WMS_BASE_URL, POLL_INTERVAL)
    else:
        if not WMS_HELPER_TOKEN:
            logger.warning("[WARNING] 鏈厤缃?WECHAT_HELPER_TOKEN锛?send 绔偣灏嗘嫆缁濇墍鏈夎姹傘€?)
            logger.warning("          璇疯缃?WECHAT_HELPER_TOKEN 鍚庨噸鍚紝鎴栧湪 WMS 涓绘湇鍔″惎鐢ㄨ疆璇㈡ā寮忕敱鍏朵富鍔ㄦ帹閫佷换鍔°€?)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    logger.info("WMS WeChat helper listening on http://%s:%s", HOST, PORT)
    logger.info("Default mode: use already-open WeChat, paste image, and wait for manual confirmation.")
    server.serve_forever()


if __name__ == "__main__":
    main()


