"""CI-side pytest wrapper for BUG-2026-11-11-006.

Runs the same offline regression lock as
``scripts/verify_wechat_activate_robustness.py``: the real helper functions are
lifted out of ``app/wechat_helper.py`` with the AST and executed against a fake
Win32 layer. No WeChat window, clipboard, keyboard, database or network is
touched, and the Windows-only helper module is never imported.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'verify_wechat_activate_robustness', ROOT / 'scripts' / 'verify_wechat_activate_robustness.py')
_guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_guard)

CORE = (
    'hotkey_default_is_ctrl_alt_w',
    'hotkey_parse_reads_env',
    'show_uses_hotkey_for_hidden',
    'show_falls_back_to_showwindow',
    'force_uses_attach_thread_input',
    'force_has_switch_backup',
    'force_verifies_with_get_foreground',
    'open_contact_checks_panel_width',
    'open_contact_raises_contact_not_opened',
    'open_contact_closes_panel_on_failure',
    'paste_passes_hwnd_to_open_contact',
    'activate_delegates_to_show_window',
    'dispatch_marks_contact_not_opened_safe',
    'behaviour_hotkey_default',
    'behaviour_hotkey_env_override',
    'behaviour_hotkey_can_be_disabled',
    'behaviour_force_plain_setforeground',
    'behaviour_force_attach_thread',
    'behaviour_force_switch_backup',
    'behaviour_force_always_detaches',
    'behaviour_show_hidden_uses_hotkey',
    'behaviour_show_hidden_presses_ctrl_alt_w',
    'behaviour_show_minimized_restores',
    'behaviour_show_visible_sends_no_hotkey',
    'behaviour_show_hidden_no_hotkey_falls_back',
    'behaviour_panel_open_is_true',
    'behaviour_panel_closed_is_false',
    'behaviour_open_contact_3x_single_enter',
    'behaviour_open_contact_4x_tabs_then_enters',
    'behaviour_open_contact_fails_closed',
    'behaviour_open_contact_closes_panel_when_giving_up',
)


@pytest.fixture(scope='module')
def results():
    return _guard.run_checks()


@pytest.mark.parametrize('key', CORE)
def test_check_passes(key, results):
    assert results[key] is True


def test_no_check_regressed(results):
    failed = [name for name, ok in results.items() if not ok]
    assert failed == [], failed


def test_show_hotkey_vks():
    """默认 Ctrl+Alt+W；环境变量可覆盖、可关掉、非法片段整条忽略。"""
    assert _guard._build(env={})['_show_hotkey_vks']() == (0x11, 0x12, 0x57)
    assert _guard._build(env={'WECHAT_SHOW_HOTKEY': 'ctrl+shift+x'})['_show_hotkey_vks']() == (
        0x11, 0x10, 0x58)
    assert _guard._build(env={'WECHAT_SHOW_HOTKEY': 'off'})['_show_hotkey_vks']() == ()
    assert _guard._build(env={'WECHAT_SHOW_HOTKEY': 'ctrl+bogus'})['_show_hotkey_vks']() == ()


def test_force_foreground():
    """三档兜底逐级生效；一次都抢不到时返回 None 而不是假报成功。"""
    assert _guard._build(fg_rule='ok')['_force_foreground'](_guard.HWND) == 'SetForegroundWindow'
    assert _guard._build(fg_rule='deny')['_force_foreground'](_guard.HWND) == 'AttachThreadInput'
    assert _guard._build(fg_rule='deny_all')['_force_foreground'](_guard.HWND) == 'SwitchToThisWindow'
    ns = _guard._build(fg_rule='deny')
    ns['_force_foreground'](_guard.HWND)
    attaches = [c for c in ns['_user32'].calls if c[0] == 'AttachThreadInput']
    assert attaches[0][1] is True and attaches[-1][1] is False


def test_show_wechat_window():
    """隐藏态走快捷键、最小化态走 SW_RESTORE、正常态不动窗口。"""
    assert _guard._build(state=_guard._State(visible=False))['_show_wechat_window'](
        _guard.HWND) == 'show_hotkey'
    ns = _guard._build(state=_guard._State(visible=True, iconic=True))
    assert ns['_show_wechat_window'](_guard.HWND) == 'restore'
    assert [c for c in ns['_user32'].calls if c[0] == 'ShowWindow'][-1][2] == 9
    ns = _guard._build(state=_guard._State(visible=True, iconic=False))
    assert ns['_show_wechat_window'](_guard.HWND) == 'already_visible'
    ns = _guard._build(state=_guard._State(visible=True, iconic=False))
    ns['_show_wechat_window'](_guard.HWND)
    assert [c for c in ns['_user32'].calls if c[0] == 'ShowWindow'] == []


def test_search_panel_open():
    """窗口宽度明显变大即判定搜索面板还挂着；基线未知时不误伤。"""
    ns = _guard._build(state=_guard._State(width=_guard.PANEL_WIDTH))
    assert ns['_search_panel_open'](_guard.HWND, _guard.NORMAL_WIDTH) is True
    ns = _guard._build(state=_guard._State(width=_guard.NORMAL_WIDTH))
    assert ns['_search_panel_open'](_guard.HWND, _guard.NORMAL_WIDTH) is False
    assert ns['_search_panel_open'](_guard.HWND, 0) is False


def test_open_contact():
    """3.x 一次回车、4.x 补 Tab；打不开必须抛 contact_not_opened 并收起面板。"""
    ns = _guard._build(panel=_guard._Panel(('enter',)))
    ns['open_contact']('文件传输助手', _guard.HWND)
    assert ns['_panel'].pressed == ['enter']

    ns = _guard._build(panel=_guard._Panel(('tab', 'enter')))
    ns['open_contact']('文件传输助手', _guard.HWND)
    assert 'tab' in ns['_panel'].pressed
    assert ns['_panel'].open is False

    ns = _guard._build(panel=_guard._Panel(()))
    with pytest.raises(ns['_SendError']) as excinfo:
        ns['open_contact']('文件传输助手', _guard.HWND)
    assert excinfo.value.code == 'contact_not_opened'
    assert ns['_panel'].pressed[-1] == 'esc'
