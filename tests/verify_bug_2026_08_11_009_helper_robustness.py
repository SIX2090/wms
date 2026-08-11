# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-009 回归测试：微信发送助手健壮性（静态断言）。

助手是 Windows-only（模块级 ctypes.windll），Linux 沙箱无法 import，按仓库惯例做静态验证。

缺陷：
1. ThreadingHTTPServer 每请求一线程，但剪贴板/键盘输入/前台焦点是全局资源，
   并发 /send 互相抢焦点、串剪贴板 → 发错图、发错人。
2. 锁屏/远程桌面断开/弹窗抢焦点时，SendInput 把 Ctrl+V/回车打进别的窗口。
3. 失败只返回自由文本 msg，WMS 侧只能靠中英文关键词匹配判定 failed/pending，脆弱。
4. 先写剪贴板后校验接收人，无谓的副作用。

修复（app/wechat_helper.py）：
- 全局 SEND_LOCK 串行化 send_image_task；
- _ensure_foreground 在 激活后/打开会话后/回车前 三处校验微信窗口仍在前台；
- _SendError 携带机器可读 code（no_receiver/clipboard_failed/wechat_window_not_found/
  open_contact_failed/paste_failed/send_key_failed/focus_lost），do_POST 与 poll 回报均带 code；
- 接收人校验提前到写剪贴板之前。

验收点：
T1. SEND_LOCK 存在且 send_image_task 全程持锁。
T2. GetForegroundWindow 声明 + _ensure_foreground 三处关键校验在场。
T3. _SendError 错误码体系在场，do_POST/poll 响应含 code 字段。
T4. 接收人校验早于 set_clipboard_dib。
T5. 两个调用方（do_POST、poll_once）适配 (status, code, message) 三元组。
"""
from __future__ import annotations

import re
from pathlib import Path

HELPER = Path(__file__).resolve().parent.parent / "app" / "wechat_helper.py"
SRC = HELPER.read_text(encoding="utf-8")


def test_t1_send_lock_serializes_tasks():
    assert "SEND_LOCK = threading.Lock()" in SRC
    m = re.search(r"def send_image_task\(.*?\n(.*?)\n\ndef ", SRC, re.DOTALL)
    assert m, "send_image_task 未找到"
    assert "with SEND_LOCK:" in m.group(1), "send_image_task 必须全程持 SEND_LOCK"


def test_t2_foreground_guards():
    assert "user32.GetForegroundWindow.restype" in SRC
    assert "def _ensure_foreground(" in SRC
    m = re.search(r"def paste_image_and_optionally_send\(.*?\n(.*?)\n\ndef ", SRC, re.DOTALL)
    assert m
    body = m.group(1)
    # 激活后、打开会话后、回车发送前各一次校验
    assert body.count("_ensure_foreground(hwnd)") >= 3, body
    assert '"focus_lost"' in SRC


def test_t3_structured_error_codes():
    assert "class _SendError(" in SRC
    for code in ("no_receiver", "clipboard_failed", "wechat_window_not_found",
                 "open_contact_failed", "paste_failed", "send_key_failed", "focus_lost"):
        assert f'"{code}"' in SRC, f"缺少错误码 {code}"
    assert '"code": code' in SRC, "do_POST 响应必须带 code"
    assert '"status": "error", "code": "send_failed"' in SRC, "do_POST 兜底 500 必须带 code"
    assert 'json={"status": status, "code": code, "msg": message}' in SRC, "poll 回报必须带 code"


def test_t4_receiver_validated_before_clipboard():
    m = re.search(r"def paste_image_and_optionally_send\(.*?\n(.*?)\n\ndef ", SRC, re.DOTALL)
    body = m.group(1)
    assert body.index('raise _SendError("no_receiver"') < body.index("set_clipboard_dib(image_bytes)")


def test_t5_callers_unpack_triplet():
    assert "status, code, message = send_image_task(image_bytes, task)" in SRC
    assert "status, code, message = send_image_task(image_response.content, task)" in SRC
    assert "status, message = send_image_task" not in SRC, "旧的二元组解包必须清零"


if __name__ == "__main__":
    for name, fn in sorted(list(globals().items())):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"PASS {name}")
    print("ALL PASSED")
