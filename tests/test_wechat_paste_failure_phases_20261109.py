"""Actual helper phase classification with fake UI operations only."""
import ast
import contextlib
from pathlib import Path
import socket
import sqlite3
import subprocess
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def deny(*_a, **_kw): raise AssertionError('DB, network and subprocess forbidden')


class WechatPastePhaseTests(unittest.TestCase):
    def setUp(self):
        for target, name in ((socket.socket, 'connect'), (socket.socket, 'connect_ex'),
                             (socket, 'getaddrinfo'), (socket, 'create_connection'),
                             (sqlite3, 'connect'), (subprocess, 'Popen')):
            guard = patch.object(target, name, deny)
            guard.start()
            self.addCleanup(guard.stop)
        tree = ast.parse((ROOT / 'app/wechat_helper.py').read_text(encoding='utf-8-sig'))
        names = {'_SendError', 'paste_image_and_optionally_send', 'send_image_task'}
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        self.calls, self.focus_count, self.fail_paste = [], 0, False
        def focus(_hwnd):
            self.focus_count += 1
            if self.focus_count == 3:
                raise self.env['_SendError']('focus_lost', 'synthetic focus lost after paste')
        def hotkey(*_args):
            self.calls.append('paste')
            if self.fail_paste:
                raise RuntimeError('synthetic partial key delivery')
        self.env = {'SEND_LOCK': contextlib.nullcontext(), 'set_clipboard_dib': lambda _bytes: None,
                    'activate_wechat': lambda: (1, 'normal'),
                    'restore_window_state': lambda _hwnd, _state: None,
                    '_ensure_foreground': focus,
                    'open_contact': lambda _name: None, 'hotkey': hotkey,
                    'press_key': lambda _key: self.calls.append('send'),
                    'VK_CONTROL': 17, 'VK_V': 86, 'VK_RETURN': 13,
                    'time': types.SimpleNamespace(sleep=lambda _seconds: None)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                     '<synthetic-helper-paste>', 'exec'), self.env)

    def test_focus_lost_can_happen_after_paste(self):
        result = self.env['send_image_task'](b'synthetic', {'receiver_name': 'synthetic', 'auto_send': True})
        self.assertEqual(self.calls, ['paste'])
        self.assertEqual(result[:2], ('error', 'focus_lost'))

    def test_paste_failed_can_follow_partial_hotkey_delivery(self):
        self.fail_paste = True
        result = self.env['send_image_task'](b'synthetic', {'receiver_name': 'synthetic', 'auto_send': True})
        self.assertEqual(self.calls, ['paste'])
        self.assertEqual(result[:2], ('error', 'paste_failed'))


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(WechatPastePhaseTests)
    if suite.countTestCases() != 2: raise SystemExit('synthetic test list incomplete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
