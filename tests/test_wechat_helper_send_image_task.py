# -*- coding: utf-8 -*-
"""wechat_helper.send_image_task 单元测试。

wechat_helper 是 Windows 专用（ctypes.windll），Linux CI 下注入 MagicMock
以便导入模块并测试纯 Python 的发送任务编排逻辑（SEND_LOCK 串行化、
结构化错误码透传、接收人回退链）。
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from pathlib import Path
from unittest import mock

# Linux 无 ctypes.windll：导入前注入 MagicMock，argtypes/restype 赋值均可承载
if not hasattr(ctypes, "windll"):
    ctypes.windll = mock.MagicMock()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import wechat_helper  # noqa: E402


def test_send_image_task():
    """主路径聚合：ready / sent / error 三态与错误码透传。"""
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", return_value="ready"
    ):
        assert wechat_helper.send_image_task(b"p", {"receiver_name": "赵六"})[0] == "ready"
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", return_value="sent"
    ):
        assert wechat_helper.send_image_task(b"p", {"receiver_name": "赵六"})[0] == "sent"
    err = wechat_helper._SendError("clipboard_failed", "写入剪贴板失败")
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", side_effect=err
    ):
        status, code, _msg = wechat_helper.send_image_task(b"p", {"receiver_name": "赵六"})
    assert (status, code) == ("error", "clipboard_failed")


def test_send_image_task_ready_path():
    """auto_send=False：粘贴成功返回 (ready, ok, ...)，消息含接收人。"""
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", return_value="ready"
    ) as paste:
        status, code, msg = wechat_helper.send_image_task(
            b"png-bytes", {"receiver_name": "张三", "auto_send": False}
        )
    assert status == "ready"
    assert code == "ok"
    assert "张三" in msg
    paste.assert_called_once_with(b"png-bytes", "张三", False)


def test_send_image_task_sent_path():
    """auto_send=True 且底层返回 sent：返回 (sent, ok, ...)。"""
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", return_value="sent"
    ):
        status, code, msg = wechat_helper.send_image_task(
            b"png", {"receiver_search_key": "售后群", "auto_send": True}
        )
    assert status == "sent"
    assert code == "ok"
    assert "售后群" in msg


def test_send_image_task_senderror_code_passthrough():
    """_SendError 结构化错误码原样透传为 (error, code, msg)。"""
    err = wechat_helper._SendError("focus_lost", "微信窗口不在前台")
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", side_effect=err
    ):
        status, code, msg = wechat_helper.send_image_task(b"png", {"receiver_name": "李四"})
    assert status == "error"
    assert code == "focus_lost"
    assert "前台" in msg


def test_send_image_task_receiver_fallback_chain():
    """接收人回退链：receiver_search_key > receiver_name > receiver_wechat_id。"""
    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", return_value="ready"
    ) as paste:
        wechat_helper.send_image_task(b"png", {"receiver_wechat_id": "wxid_abc"})
    assert paste.call_args[0][1] == "wxid_abc"


def test_send_image_task_serialized_by_send_lock():
    """两个并发任务必须串行执行（SEND_LOCK 全程持有）。"""
    order = []

    def fake_paste(image_bytes, key, auto_send):
        order.append(("enter", key))
        time.sleep(0.05)
        order.append(("exit", key))
        return "ready"

    with mock.patch.object(
        wechat_helper, "paste_image_and_optionally_send", side_effect=fake_paste
    ):
        t1 = threading.Thread(
            target=wechat_helper.send_image_task, args=(b"a", {"receiver_name": "A"})
        )
        t2 = threading.Thread(
            target=wechat_helper.send_image_task, args=(b"b", {"receiver_name": "B"})
        )
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    # 串行化：第一个任务的 exit 必须早于第二个任务的 enter
    # （锁内执行时顺序必为 enter X -> exit X -> enter Y -> exit Y）
    assert order[0][0] == "enter"
    assert order[1] == ("exit", order[0][1])
    assert order[2][0] == "enter"
    assert order[3] == ("exit", order[2][1])
