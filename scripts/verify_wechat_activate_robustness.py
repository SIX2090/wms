"""Offline regression lock for BUG-2026-11-11-006.

真机（微信 4.x）验收暴露三个问题，旧实现全都过不去：

1. 缩到托盘时窗口仍是 ``WS_VISIBLE`` 的"空壳"，``ShowWindow(SW_RESTORE)``
   叫不出界面（屏幕上一个像素都不画），必须用微信自己的"显示/隐藏微信"
   全局快捷键才能唤出（默认 Ctrl+Alt+W，可被环境变量覆盖）。
2. 后台进程单靠 ``SetForegroundWindow`` 抢前台会被前台锁静默拒绝，真机上
   表现为"窗口唤出来了、前台还是别的程序"，随后 ``_ensure_foreground``
   直接中止发送。需要挂线程 / 系统旧接口逐级兜底，每档都用
   ``GetForegroundWindow`` 实测确认。
3. ``Ctrl+F`` 在 4.x 是独立搜索面板，回车不切会话，于是"搜索框里有名字、
   聊天区还停在原会话"，而助手照样报 ``sent`` —— 静默丢单。修复后
   ``open_contact`` 多档尝试并用窗口宽度实测确认，打不开就抛
   ``contact_not_opened``，绝不假装成功。

验证手段：真实函数体用 AST 从 ``app/wechat_helper.py`` 取出，注入纯 Python
假 Win32 层执行。不 import 助手模块、不碰真实窗口/剪贴板/键盘/数据库/网络。
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / 'app' / 'wechat_helper.py'
DISPATCH = ROOT / 'app' / 'services' / 'wechat_share_dispatch.py'

FUNCS = ('_show_hotkey_vks', '_force_foreground', '_show_wechat_window',
         'activate_wechat', '_search_panel_open', 'open_contact',
         '_window_rect', 'capture_window_state', 'paste_image_and_optionally_send')
CONSTS = ('SW_HIDE', 'SW_SHOW', 'SW_MINIMIZE', 'SW_RESTORE', 'VK_CONTROL', 'VK_MENU',
          'VK_RETURN', 'VK_TAB', 'VK_DOWN', 'VK_ESCAPE', 'VK_F', 'VK_A',
          'WECHAT_SHOW_HOTKEY_DEFAULT', '_HOTKEY_TOKENS',
          'WINDOW_STATE_NORMAL', 'WINDOW_STATE_MINIMIZED', 'WINDOW_STATE_HIDDEN')

NORMAL_WIDTH = 896
PANEL_WIDTH = 1340     # 真机实测：搜索面板打开后窗口由 896 变 1340
HWND = 216925290


def _tree():
    return ast.parse(HELPER.read_text(encoding='utf-8-sig'))


def _defs(tree, names):
    found = {n.name: n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names}
    missing = [n for n in names if n not in found]
    if missing:
        raise AssertionError('缺少待验证的定义：' + ', '.join(missing))
    return found


def _module_consts(tree):
    """取模块级常量。字典字面量的值可能是别的常量名（如 _HOTKEY_TOKENS），二次解析。"""
    values = {}
    pending = []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name) or target.id not in CONSTS:
                continue
            try:
                values[target.id] = ast.literal_eval(node.value)
            except ValueError:
                pending.append((target.id, node.value))
    for name, node in pending:
        try:
            values[name] = ast.literal_eval(_resolve_names(node, values))
        except (ValueError, KeyError):
            continue
    return values


def _resolve_names(node, values):
    """把表达式里的常量名替换成实际值，好让 literal_eval 能吃掉整个字典。"""
    if isinstance(node, ast.Name):
        return ast.Constant(value=values[node.id])
    if isinstance(node, ast.Dict):
        return ast.Dict(keys=[_resolve_names(k, values) if k is not None else None for k in node.keys],
                        values=[_resolve_names(v, values) for v in node.values])
    return node


class _Rect:
    def __init__(self):
        self.left = self.top = self.right = self.bottom = 0


class _State:
    """一块窗口的全部可观测状态，假 user32 直接改它。"""

    def __init__(self, visible=True, iconic=False, width=NORMAL_WIDTH, height=648):
        self.visible = visible
        self.iconic = iconic
        self.width = width
        self.height = height
        self.left = 100
        self.top = 100


class _FakeUser32:
    def __init__(self, state, fg=0, fg_rule='ok'):
        self.state = state
        self.fg = fg
        self.fg_rule = fg_rule          # ok / deny / deny_all / never
        self.attached = False
        self.calls = []

    # --- 窗口形态 ---
    def IsWindowVisible(self, hwnd):
        self.calls.append(('IsWindowVisible', hwnd))
        return 1 if self.state.visible else 0

    def IsIconic(self, hwnd):
        self.calls.append(('IsIconic', hwnd))
        return 1 if self.state.iconic else 0

    def ShowWindow(self, hwnd, command):
        self.calls.append(('ShowWindow', hwnd, command))
        if command == 0:            # SW_HIDE
            self.state.visible = False
        elif command == 6:          # SW_MINIMIZE
            self.state.iconic = True
        else:                       # SW_SHOW / SW_RESTORE
            self.state.visible = True
            self.state.iconic = False
        return 1

    def GetWindowRect(self, hwnd, rect_ref):
        self.calls.append(('GetWindowRect', hwnd))
        rect_ref.left = self.state.left
        rect_ref.top = self.state.top
        rect_ref.right = self.state.left + self.state.width
        rect_ref.bottom = self.state.top + self.state.height
        return 1

    # --- 前台 ---
    def SetForegroundWindow(self, hwnd):
        self.calls.append(('SetForegroundWindow', hwnd))
        if self.fg_rule == 'ok':
            self.fg = hwnd
            return 1
        if self.fg_rule == 'deny' and self.attached:
            self.fg = hwnd
            return 1
        if self.fg_rule == 'never':
            return 0
        return 0

    def GetForegroundWindow(self):
        self.calls.append(('GetForegroundWindow', 0))
        return self.fg

    def GetWindowThreadProcessId(self, hwnd, _pid):
        self.calls.append(('GetWindowThreadProcessId', hwnd))
        return 4321

    def AttachThreadInput(self, _self_tid, _target_tid, flag):
        self.calls.append(('AttachThreadInput', bool(flag)))
        if self.fg_rule in ('deny', 'deny_all'):
            self.attached = bool(flag)
        return 1

    def BringWindowToTop(self, hwnd):
        self.calls.append(('BringWindowToTop', hwnd))
        if self.fg_rule == 'deny':
            self.fg = hwnd
        return 1

    def SwitchToThisWindow(self, hwnd, _flag):
        self.calls.append(('SwitchToThisWindow', hwnd))
        if self.fg_rule in ('deny_all', 'never'):
            self.fg = hwnd
        return 1


class _Logger:
    def __init__(self):
        self.warnings = []
        self.infos = []

    def warning(self, *args, **_kwargs):
        self.warnings.append(args)

    def info(self, *args, **_kwargs):
        self.infos.append(args)

    def error(self, *args, **_kwargs):
        pass


class _Panel:
    """模拟微信搜索面板：Ctrl+F 后窗口变宽，某一组按键能把它关掉。"""

    def __init__(self, opener):
        self.opener = tuple(opener)   # 例如 ('enter',) / ('tab', 'enter') / ()
        self.open = False
        self.pressed = []

    def key(self, name, user32):
        self.pressed.append(name)
        if not self.open:
            return
        if tuple(self.pressed[-len(self.opener):]) == self.opener and self.opener:
            self.open = False
            user32.state.width = NORMAL_WIDTH


def _resolve_hotkey(consts, env):
    raw = (env or {}).get('WECHAT_SHOW_HOTKEY', consts['WECHAT_SHOW_HOTKEY_DEFAULT'])
    tokens = consts['_HOTKEY_TOKENS']
    keys = []
    for token in str(raw).strip().lower().replace(' ', '').split('+'):
        if token in tokens:
            keys.append(tokens[token])
        elif len(token) == 1:
            keys.append(ord(token.upper()))
    return keys


def _build(state=None, panel=None, env=None, fg=0, fg_rule='ok'):
    tree = _tree()
    consts = _module_consts(tree)
    defs = _defs(tree, ('_SendError',) + FUNCS)
    state = state or _State()
    user32 = _FakeUser32(state, fg=fg, fg_rule=fg_rule)
    logger = _Logger()
    panel = panel or _Panel(())
    hotkeys = []

    def _hotkey(*keys):
        hotkeys.append(tuple(keys))
        if tuple(keys) == (consts['VK_CONTROL'], consts['VK_F']):
            panel.open = True
            state.width = PANEL_WIDTH
        elif tuple(keys) == ns_show_hotkey[0]:
            # 模拟微信全局快捷键真的把窗口唤出来（真机 3/3 一次即出）
            state.visible = True
            state.iconic = False
            user32.fg = HWND

    def _press(key):
        name = {consts['VK_RETURN']: 'enter', consts['VK_TAB']: 'tab',
                consts['VK_DOWN']: 'down', consts['VK_ESCAPE']: 'esc'}.get(key, str(key))
        panel.key(name, user32)

    ns_show_hotkey = [tuple(_resolve_hotkey(consts, env))]
    ns = {
        'user32': user32,
        'kernel32': types.SimpleNamespace(GetCurrentThreadId=lambda: 1111),
        'ctypes': types.SimpleNamespace(byref=lambda obj: obj),
        'wintypes': types.SimpleNamespace(RECT=_Rect),
        'logger': logger,
        'time': types.SimpleNamespace(sleep=lambda _s: None),
        'os': types.SimpleNamespace(environ={} if env is None else env),
        'hotkey': _hotkey,
        'press_key': _press,
        'type_text': lambda _t: None,
    }
    ns.update(consts)
    body = [defs['_SendError']] + [defs[name] for name in FUNCS]
    body.sort(key=lambda node: (node.lineno, node.col_offset))
    exec(compile(ast.Module(body=body, type_ignores=[]), str(HELPER), 'exec'), ns)
    ns['_user32'] = user32
    ns['_logger'] = logger
    ns['_hotkeys'] = hotkeys
    ns['_panel'] = panel
    ns['_state'] = state
    return ns


def _static_checks() -> dict:
    results = {}
    tree = _tree()
    defs = _defs(tree, ('_SendError',) + FUNCS)
    show = defs['_show_wechat_window']
    force = defs['_force_foreground']
    keys = defs['_show_hotkey_vks']
    openc = defs['open_contact']
    panel = defs['_search_panel_open']
    activate = defs['activate_wechat']

    def _calls(node, attr):
        return [n for n in ast.walk(node) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute) and n.func.attr == attr]

    results['hotkey_parse_reads_env'] = any(
        isinstance(n, ast.Attribute) and n.attr == 'environ' for n in ast.walk(keys))
    results['hotkey_parse_can_be_disabled'] = any(
        isinstance(n, ast.Constant) and n.value in ('off', 'none') for n in ast.walk(keys))
    results['hotkey_default_is_ctrl_alt_w'] = (
        _module_consts(tree).get('WECHAT_SHOW_HOTKEY_DEFAULT') == 'ctrl+alt+w')

    results['show_uses_hotkey_for_hidden'] = bool(
        _calls(show, 'IsWindowVisible')) and any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'hotkey'
        for n in ast.walk(show))
    results['show_falls_back_to_showwindow'] = bool(_calls(show, 'ShowWindow'))
    results['show_forces_foreground_after'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == '_force_foreground'
        for n in ast.walk(show))

    results['force_uses_attach_thread_input'] = bool(_calls(force, 'AttachThreadInput'))
    results['force_verifies_with_get_foreground'] = (
        len(_calls(force, 'GetForegroundWindow')) >= 2)
    results['force_has_switch_backup'] = any(
        isinstance(n, ast.Constant) and n.value == 'SwitchToThisWindow' for n in ast.walk(force))

    results['open_contact_accepts_hwnd'] = (
        len(openc.args.args) == 2 and openc.args.args[1].arg == 'hwnd')
    results['open_contact_checks_panel_width'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == '_search_panel_open' for n in ast.walk(openc))
    results['open_contact_retries_more_than_once'] = (
        len([n for n in ast.walk(openc) if isinstance(n, ast.For)]) >= 1)
    results['open_contact_raises_contact_not_opened'] = any(
        isinstance(n, ast.Constant) and n.value == 'contact_not_opened' for n in ast.walk(openc))
    results['open_contact_closes_panel_on_failure'] = any(
        isinstance(n, ast.Name) and n.id == 'VK_ESCAPE' for n in ast.walk(openc))
    results['panel_check_uses_width_threshold'] = any(
        isinstance(n, ast.Constant) and n.value == 40 for n in ast.walk(panel))

    paste = defs.get('paste_image_and_optionally_send')
    if paste is not None:
        results['paste_passes_hwnd_to_open_contact'] = any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == 'open_contact' and len(n.args) == 2 for n in ast.walk(paste))
    results['activate_delegates_to_show_window'] = any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == '_show_wechat_window' for n in ast.walk(activate))
    results['activate_no_longer_calls_raw_restore_only'] = not any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == 'ShowWindow' for n in ast.walk(activate))

    dispatch = ast.parse(DISPATCH.read_text(encoding='utf-8-sig'))
    results['dispatch_marks_contact_not_opened_safe'] = any(
        isinstance(n, ast.Constant) and n.value == 'contact_not_opened'
        for n in ast.walk(dispatch))
    return results


def _dynamic_checks() -> dict:
    results = {}

    # ---- 快捷键解析 ----
    ns = _build(env={})
    results['behaviour_hotkey_default'] = ns['_show_hotkey_vks']() == (0x11, 0x12, 0x57)
    ns = _build(env={'WECHAT_SHOW_HOTKEY': 'ctrl+shift+x'})
    results['behaviour_hotkey_env_override'] = ns['_show_hotkey_vks']() == (0x11, 0x10, 0x58)
    ns = _build(env={'WECHAT_SHOW_HOTKEY': 'off'})
    results['behaviour_hotkey_can_be_disabled'] = ns['_show_hotkey_vks']() == ()
    ns = _build(env={'WECHAT_SHOW_HOTKEY': 'ctrl+bogus+9'})
    results['behaviour_hotkey_rejects_unknown_token'] = ns['_show_hotkey_vks']() == ()

    # ---- 抢前台三档兜底 ----
    ns = _build(fg_rule='ok')
    results['behaviour_force_plain_setforeground'] = ns['_force_foreground'](HWND) == 'SetForegroundWindow'
    ns = _build(fg_rule='deny')
    results['behaviour_force_attach_thread'] = ns['_force_foreground'](HWND) == 'AttachThreadInput'
    ns = _build(fg_rule='deny_all')
    results['behaviour_force_switch_backup'] = ns['_force_foreground'](HWND) == 'SwitchToThisWindow'
    ns = _build(fg_rule='never')
    got = ns['_force_foreground'](HWND)
    results['behaviour_force_returns_none_when_hopeless'] = got in (None, 'SwitchToThisWindow')
    attaches = [c for c in ns['_user32'].calls if c[0] == 'AttachThreadInput']
    results['behaviour_force_always_detaches'] = (
        len(attaches) >= 2 and attaches[0][1] is True and attaches[-1][1] is False)

    # ---- 唤出分支 ----
    ns = _build(state=_State(visible=True, iconic=False))
    results['behaviour_show_visible_is_cheap'] = ns['_show_wechat_window'](HWND) == 'already_visible'
    results['behaviour_show_visible_sends_no_hotkey'] = ns['_hotkeys'] == []

    ns = _build(state=_State(visible=False, iconic=False))
    results['behaviour_show_hidden_uses_hotkey'] = ns['_show_wechat_window'](HWND) == 'show_hotkey'
    results['behaviour_show_hidden_presses_ctrl_alt_w'] = ns['_hotkeys'] == [(0x11, 0x12, 0x57)]

    ns = _build(state=_State(visible=True, iconic=True))
    results['behaviour_show_minimized_restores'] = ns['_show_wechat_window'](HWND) == 'restore'
    results['behaviour_show_minimized_no_hotkey'] = ns['_hotkeys'] == []
    shows = [c for c in ns['_user32'].calls if c[0] == 'ShowWindow']
    results['behaviour_show_minimized_uses_sw_restore'] = shows and shows[-1][2] == 9

    # 快捷键被关掉时退回 ShowWindow，不能直接抛
    ns = _build(env={'WECHAT_SHOW_HOTKEY': 'off'}, state=_State(visible=False))
    results['behaviour_show_hidden_no_hotkey_falls_back'] = ns['_show_wechat_window'](HWND) == 'show_window'
    results['behaviour_show_hidden_fallback_shows_window'] = ns['_state'].visible is True

    # ---- 搜索面板判定 ----
    ns = _build(state=_State(width=NORMAL_WIDTH))
    results['behaviour_panel_closed_is_false'] = ns['_search_panel_open'](HWND, NORMAL_WIDTH) is False
    ns = _build(state=_State(width=PANEL_WIDTH))
    results['behaviour_panel_open_is_true'] = ns['_search_panel_open'](HWND, NORMAL_WIDTH) is True
    ns = _build(state=_State(width=NORMAL_WIDTH + 20))
    results['behaviour_panel_tolerates_small_jitter'] = ns['_search_panel_open'](HWND, NORMAL_WIDTH) is False
    ns = _build(state=_State(width=PANEL_WIDTH))
    results['behaviour_panel_unknown_baseline_is_lenient'] = ns['_search_panel_open'](HWND, 0) is False

    # ---- open_contact：3.x 一次回车即开 ----
    ns = _build(panel=_Panel(('enter',)))
    ns['open_contact']('文件传输助手', HWND)
    results['behaviour_open_contact_3x_single_enter'] = ns['_panel'].pressed == ['enter']
    results['behaviour_open_contact_3x_panel_closed'] = ns['_panel'].open is False

    # ---- open_contact：4.x 需要 Tab 进结果列表 ----
    ns = _build(panel=_Panel(('tab', 'enter')))
    ns['open_contact']('文件传输助手', HWND)
    results['behaviour_open_contact_4x_tabs_then_enters'] = 'tab' in ns['_panel'].pressed
    results['behaviour_open_contact_4x_opens'] = ns['_panel'].open is False

    # ---- open_contact：打不开必须 fail-closed，不能假装成功 ----
    ns = _build(panel=_Panel(()))
    raised = None
    try:
        ns['open_contact']('文件传输助手', HWND)
    except Exception as exc:  # noqa: BLE001 - 就是要看它抛什么
        raised = exc
    results['behaviour_open_contact_fails_closed'] = (
        raised is not None and getattr(raised, 'code', '') == 'contact_not_opened')
    results['behaviour_open_contact_escalates'] = ns['_panel'].pressed[:1] == ['enter']
    results['behaviour_open_contact_closes_panel_when_giving_up'] = ns['_panel'].pressed[-1] == 'esc'

    ns = _build(panel=_Panel(()))
    raised = None
    try:
        ns['open_contact']('   ', HWND)
    except Exception as exc:  # noqa: BLE001
        raised = exc
    results['behaviour_open_contact_rejects_empty_receiver'] = (
        isinstance(raised, RuntimeError) and ns['_panel'].pressed == [])
    return results


def run_checks() -> dict:
    try:
        results = _static_checks()
    except AssertionError as exc:
        if '缺少待验证的定义' in str(exc):
            return {'source_definitions_present': False}
        raise
    results.update(_dynamic_checks())
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description='BUG-2026-11-11-006 离线锁')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    results = run_checks()
    failed = [k for k, v in results.items() if not v]
    if args.json:
        print(json.dumps({'total': len(results), 'failed': failed,
                          'results': results}, ensure_ascii=False, indent=2))
    else:
        for key in sorted(results):
            if not results[key]:
                print(f'FAIL {key}')
        print(f'{len(results) - len(failed)}/{len(results)} passed')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
