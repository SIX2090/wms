"""Offline regression lock for BUG-2026-11-11-005.

微信被缩到任务栏（最小化）或右下角托盘时，助手原本完全发不出去：

* 最小化窗口的 ``GetWindowRect`` 只有 160x28、坐标固定在 -32000，
  ``find_wechat_window`` 的"主窗口要够大"门禁（宽>=520、高>=420）直接把它滤掉，
  助手报"未找到已打开的主窗口"——用户看起来像微信明明开着。
* 即使找到窗口，唤醒后也不会还原，发完一直摊在桌面上挡住用户工作。

修复：门禁改用 ``WINDOWPLACEMENT.rcNormalPosition``（还原后的真实尺寸）判断；
``activate_wechat`` 返回唤醒前的形态，``paste_image_and_optionally_send`` 在
``finally`` 里把它还原成最小化/托盘隐藏。

验证手段：真实函数体从 ``app/wechat_helper.py`` 用 AST 取出，注入纯 Python 的假
Win32 层执行。不 import 助手模块（Windows-only），不碰真实窗口、剪贴板、键盘、
数据库或网络。
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'app' / 'wechat_helper.py'

FUNCS = ('_normal_window_size', 'capture_window_state', 'restore_window_state',
         'activate_wechat', 'paste_image_and_optionally_send', 'find_wechat_window',
         # BUG-2026-11-11-006 后 activate_wechat 委托给这三个；本锁仍需能跑通
         '_show_wechat_window', '_force_foreground', '_show_hotkey_vks')
CONSTS = ('SW_HIDE', 'SW_SHOW', 'SW_MINIMIZE', 'SW_RESTORE',
          'WINDOW_STATE_NORMAL', 'WINDOW_STATE_MINIMIZED', 'WINDOW_STATE_HIDDEN',
          'WECHAT_SHOW_HOTKEY_DEFAULT', '_HOTKEY_TOKENS')

SW_HIDE, SW_MINIMIZE, SW_RESTORE = 0, 6, 9
STATE_NORMAL, STATE_MINIMIZED, STATE_HIDDEN = 'normal', 'minimized', 'hidden'

# 最小化窗口在 Windows 上的实际观测值（屏幕外 160x28）
ICONIC_RECT = (-32000, -32000, -31840, -31972, 160, 28)


def _tree():
    return ast.parse(HELPER.read_text(encoding='utf-8-sig'))


def _source_lines():
    return HELPER.read_text(encoding='utf-8-sig').splitlines()


def _defs(tree, names):
    found = {n.name: n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names}
    missing = [n for n in names if n not in found]
    if missing:
        raise AssertionError('缺少待验证的定义：' + ', '.join(missing))
    return found


def _module_consts(tree):
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in CONSTS:
                values[target.id] = node.value.value
    return values


class _Placement:
    """WINDOWPLACEMENT 的替身，只保留被读取的字段。"""

    def __init__(self):
        self.length = 0
        self.rcNormalPosition = types.SimpleNamespace(left=0, top=0, right=0, bottom=0)


class _FakeUser32:
    """记录调用的假 user32；窗口形态由 table 描述。"""

    def __init__(self, table, fg_hwnd):
        self.table = table
        self.calls = []
        self.fg_hwnd = fg_hwnd
        self.raise_show = False
        self.deny_fg = False

    def IsWindowVisible(self, hwnd):
        self.calls.append(('IsWindowVisible', hwnd))
        return 1 if self.table.get(hwnd, {}).get('visible', True) else 0

    def IsIconic(self, hwnd):
        self.calls.append(('IsIconic', hwnd))
        return 1 if self.table.get(hwnd, {}).get('iconic', False) else 0

    def GetWindowPlacement(self, hwnd, placement):
        self.calls.append(('GetWindowPlacement', hwnd))
        normal = self.table.get(hwnd, {}).get('normal')
        if normal is None:
            return 0
        width, height = normal
        placement.rcNormalPosition = types.SimpleNamespace(
            left=0, top=0, right=width, bottom=height)
        return 1

    def ShowWindow(self, hwnd, command):
        self.calls.append(('ShowWindow', hwnd, command))
        if self.raise_show:
            raise OSError('synthetic ShowWindow failure')
        return 1

    def SetForegroundWindow(self, hwnd):
        self.calls.append(('SetForegroundWindow', hwnd))
        if self.deny_fg:
            return 0
        # 真实 API 成功即成为前台窗口；_force_foreground 靠这个判定生效
        self.fg_hwnd = hwnd
        return 1

    def GetForegroundWindow(self):
        self.calls.append(('GetForegroundWindow', 0))
        return self.fg_hwnd

    def GetWindowThreadProcessId(self, hwnd, _pid):
        return 4321

    def AttachThreadInput(self, _a, _b, _flag):
        return 1

    def BringWindowToTop(self, hwnd):
        if not self.deny_fg:
            self.fg_hwnd = hwnd
        return 1

    def SwitchToThisWindow(self, hwnd, _flag):
        if not self.deny_fg:
            self.fg_hwnd = hwnd
        return 1

    def GetWindowRect(self, hwnd, rect_ref):
        width = self.table.get(hwnd, {}).get('normal', (800, 600))[0]
        height = self.table.get(hwnd, {}).get('normal', (800, 600))[1]
        rect_ref.left, rect_ref.top = 0, 0
        rect_ref.right, rect_ref.bottom = width, height
        return 1


class _Logger:
    def __init__(self):
        self.warnings = []
        self.errors = []

    def warning(self, *args, **_kwargs):
        self.warnings.append(args)

    def error(self, *args, **_kwargs):
        self.errors.append(args)

    def info(self, *args, **_kwargs):
        pass


def _build_ns(table, windows, fg_hwnd=1, raise_show=False, consts=None, deny_fg=False):
    """把真实函数体装进完全合成的命名空间。"""
    tree = _tree()
    consts = _module_consts(tree) if consts is None else consts
    defs = _defs(tree, ('_SendError',) + FUNCS)
    user32 = _FakeUser32(table, fg_hwnd)
    user32.raise_show = raise_show
    user32.deny_fg = deny_fg
    logger = _Logger()
    calls = []
    holder = {}

    def _focus(hwnd):
        calls.append('ensure_foreground')
        # 假 Win32 层里"前台"就是 user32.fg_hwnd：不一致时按真实实现抛 focus_lost
        if user32.fg_hwnd != hwnd:
            raise holder['ns']['_SendError']('focus_lost', 'synthetic focus lost')

    ns = {
        'ctypes': types.SimpleNamespace(sizeof=lambda _cls: 44, byref=lambda obj: obj),
        'wintypes': types.SimpleNamespace(RECT=types.SimpleNamespace),
        'kernel32': types.SimpleNamespace(GetCurrentThreadId=lambda: 1111),
        'os': types.SimpleNamespace(environ={}),
        'WINDOWPLACEMENT': _Placement,
        'user32': user32,
        'logger': logger,
        'time': types.SimpleNamespace(sleep=lambda _seconds: None),
        'enum_windows': lambda: list(windows),
        '_process_name': lambda _pid: 'Weixin.exe',
        'SEND_LOCK': contextlib.nullcontext(),
        'set_clipboard_dib': lambda _bytes: calls.append('clipboard'),
        '_ensure_foreground': _focus,
        'open_contact': lambda _name, _hwnd=None: calls.append('open_contact'),
        'hotkey': lambda *keys: calls.append(
            'paste' if tuple(keys) == (17, 86) else 'show_hotkey'),
        'press_key': lambda _key: calls.append('send'),
        'VK_CONTROL': 17, 'VK_V': 86, 'VK_RETURN': 13,
        'VK_MENU': 0x12, 'VK_TAB': 0x09, 'VK_DOWN': 0x28, 'VK_ESCAPE': 0x1B, 'VK_F': 0x46,
        'WECHAT_SHOW_HOTKEY_DEFAULT': 'ctrl+alt+w',
        '_HOTKEY_TOKENS': {'ctrl': 0x11, 'control': 0x11, 'alt': 0x12, 'shift': 0x10,
                           'win': 0x5B, 'tab': 0x09, 'enter': 0x0D, 'esc': 0x1B, 'space': 0x20},
    }
    ns.update(consts)
    body = [defs['_SendError']] + [defs[name] for name in FUNCS]
    body.sort(key=lambda node: (node.lineno, node.col_offset))
    exec(compile(ast.Module(body=body, type_ignores=[]), str(HELPER), 'exec'), ns)
    ns['_user32'] = user32
    ns['_logger'] = logger
    ns['_calls'] = calls
    holder['ns'] = ns
    return ns


def _show_calls(user32):
    return [c for c in user32.calls if c[0] == 'ShowWindow']


def _last_show(user32):
    shows = _show_calls(user32)
    return shows[-1] if shows else None


def _comparison_uses_names(node, names):
    for child in ast.walk(node):
        if isinstance(child, ast.Compare):
            for side in [child.left, *child.comparators]:
                if isinstance(side, ast.Name) and side.id in names:
                    return True
    return False


def _static_checks() -> dict:
    results = {}
    tree = _tree()
    lines = _source_lines()
    consts = _module_consts(tree)
    defs = _defs(tree, ('_SendError',) + FUNCS)
    find = defs['find_wechat_window']
    normal = defs['_normal_window_size']
    capture = defs['capture_window_state']
    restore = defs['restore_window_state']
    activate = defs['activate_wechat']
    paste = defs['paste_image_and_optionally_send']

    results['constants_sw_hide_zero'] = consts.get('SW_HIDE') == SW_HIDE
    results['constants_sw_minimize_six'] = consts.get('SW_MINIMIZE') == SW_MINIMIZE
    results['constants_states_complete'] = (
        consts.get('WINDOW_STATE_NORMAL') == STATE_NORMAL
        and consts.get('WINDOW_STATE_MINIMIZED') == STATE_MINIMIZED
        and consts.get('WINDOW_STATE_HIDDEN') == STATE_HIDDEN)

    gate_calls = [n for n in ast.walk(find) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Name) and n.func.id == '_normal_window_size']
    results['size_gate_asks_normal_size'] = len(gate_calls) == 1
    threshold_compares = [n for n in ast.walk(find) if isinstance(n, ast.Compare)
                          and any(isinstance(c, ast.Constant) and c.value in (520, 420)
                                  for c in ast.walk(n))]
    results['size_gate_no_longer_measures_raw_rect'] = bool(threshold_compares) and not any(
        _comparison_uses_names(n, {'width', 'height'}) for n in threshold_compares)
    results['size_gate_still_requires_520x420'] = any(
        isinstance(n, ast.Constant) and n.value == 520 for n in ast.walk(find)) and any(
        isinstance(n, ast.Constant) and n.value == 420 for n in ast.walk(find))
    results['size_gate_score_uses_normal_size'] = any(
        isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult)
        and isinstance(n.left, ast.Name) and n.left.id == 'measured_width'
        for n in ast.walk(find))

    placement_calls = [n for n in ast.walk(normal) if isinstance(n, ast.Call)
                       and isinstance(n.func, ast.Attribute)
                       and n.func.attr == 'GetWindowPlacement']
    results['normal_size_reads_window_placement'] = len(placement_calls) == 1
    results['normal_size_uses_rc_normal_position'] = any(
        isinstance(n, ast.Attribute) and n.attr == 'rcNormalPosition' for n in ast.walk(normal))
    results['normal_size_fails_closed_when_api_returns_false'] = any(
        isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp)
        and isinstance(n.test.op, ast.Not) for n in ast.walk(normal))
    results['normal_size_rejects_zero_area'] = any(
        isinstance(n, ast.Compare) and any(
            isinstance(c, ast.Constant) and c.value == 0 for c in n.comparators)
        for n in ast.walk(normal))

    capture_ifs = [n for n in ast.walk(capture) if isinstance(n, ast.If)]

    def _first_if_using(attr):
        hits = [n for n in capture_ifs if any(
            isinstance(c, ast.Attribute) and c.attr == attr for c in ast.walk(n.test))]
        return hits[0].lineno if hits else None

    visibility_line = _first_if_using('IsWindowVisible')
    iconic_line = _first_if_using('IsIconic')
    results['capture_checks_visibility_first'] = (
        visibility_line is not None and iconic_line is not None
        and visibility_line < iconic_line)
    results['capture_then_checks_iconic'] = iconic_line is not None
    results['capture_rejects_missing_handle'] = any(
        isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)
        and isinstance(n.exc.func, ast.Name) and n.exc.func.id == '_SendError'
        for n in ast.walk(capture))

    restore_shows = [n for n in ast.walk(restore) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and n.func.attr == 'ShowWindow']
    restore_commands = [n.args[1].id for n in restore_shows
                        if len(n.args) > 1 and isinstance(n.args[1], ast.Name)]
    results['restore_minimized_uses_sw_minimize'] = (
        restore_commands.count('SW_MINIMIZE') == 1)
    results['restore_hidden_uses_sw_hide'] = restore_commands.count('SW_HIDE') == 1
    results['restore_never_touches_normal_window'] = (
        len(restore_shows) == 2 and 'SW_RESTORE' not in restore_commands)
    restore_try = [n for n in ast.walk(restore) if isinstance(n, ast.Try)]
    results['restore_swallows_showwindow_failure'] = bool(restore_try) and any(
        isinstance(handler.type, ast.Name) and handler.type.id == 'Exception'
        for handler in restore_try[0].handlers) and not any(
        isinstance(n, ast.Raise) for n in ast.walk(restore))
    results['restore_logs_failure_warning'] = 'logger.warning' in ''.join(
        ast.unparse(h) for h in restore_try[0].handlers) if restore_try else False

    activate_returns = [n for n in ast.walk(activate) if isinstance(n, ast.Return)]
    results['activate_returns_handle_and_state'] = any(
        isinstance(n.value, ast.Tuple) and len(n.value.elts) == 2 for n in activate_returns)
    activate_src = '\n'.join(lines[activate.lineno - 1:activate.end_lineno])
    capture_line = activate_src.find('prior_state = capture_window_state(hwnd)')
    # BUG-2026-11-11-006 后唤出动作收敛到 _show_wechat_window，捕获顺序仍必须在前
    show_line = activate_src.find('_show_wechat_window(hwnd)')
    results['activate_captures_before_restoring'] = (
        0 <= capture_line < show_line)
    results['activate_mentions_minimized_or_tray'] = (
        '最小化' in activate_src and '托盘' in activate_src)

    paste_try = [n for n in ast.walk(paste) if isinstance(n, ast.Try)]
    results['paste_has_finally_branch'] = bool(paste_try) and any(n.finalbody for n in paste_try)
    finally_nodes = [n for n in paste_try if n.finalbody]
    results['paste_restores_in_finally'] = bool(finally_nodes) and any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == 'restore_window_state'
        for n in ast.walk(finally_nodes[0].finalbody[0]) if finally_nodes) if finally_nodes else False
    results['paste_restores_with_prior_state'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == 'restore_window_state' and len(n.args) == 2
        and isinstance(n.args[1], ast.Name) and n.args[1].id == 'prior_state'
        for n in ast.walk(finally_nodes[0])) if finally_nodes else False
    results['paste_finally_covers_both_send_outcomes'] = bool(finally_nodes) and any(
        isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
        and n.value.value in ('sent', 'ready') for n in ast.walk(finally_nodes[0]))
    paste_src = '\n'.join(lines[paste.lineno - 1:paste.end_lineno])
    results['paste_keeps_three_foreground_guards'] = (
        paste_src.count('_ensure_foreground(hwnd)') >= 3)
    return results


def _dynamic_checks() -> dict:
    results = {}

    # ---- 找窗口：最小化窗口按"还原后尺寸"通过门禁 ----
    table = {7: {'visible': True, 'iconic': True, 'normal': (800, 600)}}
    ns = _build_ns(table, [(7, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT)])
    results['behaviour_minimized_window_found'] = ns['find_wechat_window']() == 7
    results['behaviour_minimized_uses_placement'] = (
        ('GetWindowPlacement', 7) in ns['_user32'].calls)

    table = {8: {'visible': True, 'iconic': True, 'normal': (300, 200)}}
    ns = _build_ns(table, [(8, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT)])
    results['behaviour_tiny_normal_rect_still_rejected'] = ns['find_wechat_window']() is None

    table = {9: {'visible': True, 'iconic': True, 'normal': None}}
    ns = _build_ns(table, [(9, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT)])
    results['behaviour_unreadable_placement_rejected'] = ns['find_wechat_window']() is None

    table = {10: {'visible': True, 'iconic': False, 'normal': (800, 600)}}
    ns = _build_ns(table, [(10, 100, 'WeChatMainWndForPC', '微信', (0, 0, 800, 600, 800, 600))])
    results['behaviour_normal_window_found'] = ns['find_wechat_window']() == 10
    results['behaviour_normal_window_skips_placement'] = (
        'GetWindowPlacement' not in [c[0] for c in ns['_user32'].calls])

    # 打分也必须用还原后面积：最小化的大窗口应胜过正常的小窗口
    table = {
        11: {'visible': True, 'iconic': True, 'normal': (900, 700)},
        12: {'visible': True, 'iconic': False, 'normal': (700, 500)},
    }
    ns = _build_ns(table, [
        (11, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT),
        (12, 100, 'WeChatMainWndForPC', '微信', (0, 0, 700, 500, 700, 500)),
    ])
    results['behaviour_score_uses_restored_area'] = ns['find_wechat_window']() == 11

    # ---- 记录形态 ----
    def capture(state, hwnd=5):
        table = {hwnd: state}
        return _build_ns(table, [])

    ns = capture({'visible': False, 'iconic': False, 'normal': (800, 600)})
    results['behaviour_capture_hidden'] = ns['capture_window_state'](5) == STATE_HIDDEN
    ns = capture({'visible': False, 'iconic': True, 'normal': (800, 600)})
    results['behaviour_capture_hidden_wins_over_iconic'] = (
        ns['capture_window_state'](5) == STATE_HIDDEN)
    ns = capture({'visible': True, 'iconic': True, 'normal': (800, 600)})
    results['behaviour_capture_minimized'] = ns['capture_window_state'](5) == STATE_MINIMIZED
    ns = capture({'visible': True, 'iconic': False, 'normal': (800, 600)})
    results['behaviour_capture_normal'] = ns['capture_window_state'](5) == STATE_NORMAL
    ns = _build_ns({}, [])
    raised = None
    try:
        ns['capture_window_state'](0)
    except Exception as exc:  # noqa: BLE001 - 就是要看它抛什么
        raised = exc
    results['behaviour_capture_rejects_zero_handle'] = (
        isinstance(raised, ns['_SendError'])
        and getattr(raised, 'code', '') == 'wechat_window_not_found')

    # ---- 还原形态 ----
    ns = _build_ns({}, [])
    ns['restore_window_state'](5, STATE_NORMAL)
    results['behaviour_restore_normal_is_noop'] = _show_calls(ns['_user32']) == []
    ns = _build_ns({}, [])
    ns['restore_window_state'](5, STATE_MINIMIZED)
    results['behaviour_restore_minimized'] = _show_calls(ns['_user32']) == [
        ('ShowWindow', 5, SW_MINIMIZE)]
    ns = _build_ns({}, [])
    ns['restore_window_state'](5, STATE_HIDDEN)
    results['behaviour_restore_hidden'] = _show_calls(ns['_user32']) == [
        ('ShowWindow', 5, SW_HIDE)]
    ns = _build_ns({}, [])
    ns['restore_window_state'](0, STATE_MINIMIZED)
    results['behaviour_restore_skips_missing_handle'] = _show_calls(ns['_user32']) == []
    ns = _build_ns({}, [], raise_show=True)
    restore_error = None
    try:
        ns['restore_window_state'](5, STATE_MINIMIZED)
    except Exception as exc:  # noqa: BLE001 - 还原失败不得冒泡
        restore_error = exc
    results['behaviour_restore_failure_does_not_raise'] = restore_error is None
    results['behaviour_restore_failure_is_logged'] = len(ns['_logger'].warnings) == 1

    # ---- 唤醒 ----
    table = {6: {'visible': True, 'iconic': True, 'normal': (800, 600)}}
    ns = _build_ns(table, [(6, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT)])
    activated = None
    try:
        activated = ns['activate_wechat']()
    except Exception:  # noqa: BLE001 - 回退版本找不到最小化窗口，按失败记录而不是崩
        activated = None
    results['behaviour_activate_returns_minimized_state'] = (
        activated == (6, STATE_MINIMIZED))
    order = [c for c in ns['_user32'].calls if c[0] in ('IsWindowVisible', 'IsIconic', 'ShowWindow')]
    calls = ns['_user32'].calls
    first_show = next((i for i, c in enumerate(calls) if c[0] == 'ShowWindow'), None)
    first_fg = next((i for i, c in enumerate(calls) if c[0] == 'SetForegroundWindow'), None)
    results['behaviour_activate_captures_before_show'] = (
        order[:2] == [('IsWindowVisible', 6), ('IsIconic', 6)]
        and ('ShowWindow', 6, SW_RESTORE) in order)
    results['behaviour_activate_restores_before_taking_focus'] = (
        first_show is not None and first_fg is not None and first_show < first_fg)
    results['behaviour_activate_still_brings_to_front'] = (
        ('SetForegroundWindow', 6) in ns['_user32'].calls)

    ns = _build_ns({}, [])
    raised = None
    try:
        ns['activate_wechat']()
    except Exception as exc:  # noqa: BLE001 - 无窗口必须fail-closed
        raised = exc
    results['behaviour_activate_fails_without_window'] = (
        isinstance(raised, ns['_SendError'])
        and getattr(raised, 'code', '') == 'wechat_window_not_found')

    # ---- 端到端：发送后缩回 ----
    def send(state, auto_send=True, fg=5, receiver='张三', deny_fg=False):
        table = {5: state}
        ns = _build_ns(table, [(5, 100, 'WeChatMainWndForPC', '微信', ICONIC_RECT)],
                       fg_hwnd=fg, deny_fg=deny_fg)
        error = None
        status = None
        try:
            status = ns['paste_image_and_optionally_send'](b'synthetic', receiver, auto_send)
        except Exception as exc:  # noqa: BLE001 - 失败分支也要检查收尾
            error = exc
        return ns, status, error

    minimized = {'visible': True, 'iconic': True, 'normal': (800, 600)}
    ns, status, error = send(minimized)
    results['behaviour_send_from_minimized_succeeds'] = status == 'sent' and error is None
    results['behaviour_send_from_minimized_collapses_after'] = _last_show(ns['_user32']) == ('ShowWindow', 5, SW_MINIMIZE)

    hidden = {'visible': False, 'iconic': False, 'normal': (800, 600)}
    ns, status, error = send(hidden)
    results['behaviour_send_from_tray_succeeds'] = status == 'sent' and error is None
    results['behaviour_send_from_tray_hides_after'] = _last_show(ns['_user32']) == ('ShowWindow', 5, SW_HIDE)

    normal = {'visible': True, 'iconic': False, 'normal': (800, 600)}
    ns, status, error = send(normal)
    results['behaviour_send_from_normal_succeeds'] = status == 'sent' and error is None
    results['behaviour_send_from_normal_leaves_window_alone'] = _show_calls(ns['_user32']) == []

    ns, status, error = send(minimized, auto_send=False)
    results['behaviour_manual_confirm_still_collapses'] = (
        status == 'ready' and _last_show(ns['_user32']) == ('ShowWindow', 5, SW_MINIMIZE))

    ns, status, error = send(minimized, fg=999, deny_fg=True)
    results['behaviour_focus_lost_aborts'] = (
        isinstance(error, ns['_SendError']) and getattr(error, 'code', '') == 'focus_lost')
    results['behaviour_focus_lost_still_collapses'] = _last_show(ns['_user32']) == ('ShowWindow', 5, SW_MINIMIZE)
    results['behaviour_focus_lost_never_pastes'] = 'paste' not in ns['_calls']

    ns, status, error = send(minimized, receiver='   ')
    results['behaviour_no_receiver_collapses_nothing'] = (
        isinstance(error, ns['_SendError'])
        and getattr(error, 'code', '') == 'no_receiver'
        and _show_calls(ns['_user32']) == [])
    return results


def run_checks() -> dict:
    try:
        results = _static_checks()
    except AssertionError as exc:
        # 旧版助手没有这三个新函数；此时锁无法逐项比对，直接判整批不成立，
        # 而不是让脚本崩掉把失败藏在 traceback 里。
        if '缺少待验证的定义' in str(exc):
            return {'source_definitions_present': False}
        raise
    results.update(_dynamic_checks())
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = run_checks()
    failed = [name for name, ok in results.items() if not ok]
    if args.json:
        print(json.dumps({'total': len(results), 'passed': len(results) - len(failed),
                          'failed': failed, 'success': not failed}, ensure_ascii=False))
    else:
        for name, ok in results.items():
            print(('  PASS  ' if ok else '  FAIL  ') + name)
        print('\n  %d/%d checks passed' % (len(results) - len(failed), len(results)))
    return 0 if not failed else 1


if __name__ == '__main__':
    raise SystemExit(main())
