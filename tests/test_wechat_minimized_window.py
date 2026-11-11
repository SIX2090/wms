"""CI-side pytest wrapper for BUG-2026-11-11-005.

Runs the same offline regression lock as
``scripts/verify_wechat_minimized_window.py``: the real helper functions are
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
    'verify_wechat_minimized_window', ROOT / 'scripts' / 'verify_wechat_minimized_window.py')
_guard = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_guard)

CORE = (
    'size_gate_asks_normal_size',
    'size_gate_no_longer_measures_raw_rect',
    'normal_size_reads_window_placement',
    'normal_size_fails_closed_when_api_returns_false',
    'behaviour_minimized_window_found',
    'behaviour_tiny_normal_rect_still_rejected',
    'behaviour_unreadable_placement_rejected',
    'behaviour_score_uses_restored_area',
    'capture_checks_visibility_first',
    'restore_swallows_showwindow_failure',
    'activate_returns_handle_and_state',
    'activate_captures_before_restoring',
    'paste_restores_in_finally',
    'behaviour_send_from_minimized_succeeds',
    'behaviour_send_from_minimized_collapses_after',
    'behaviour_send_from_tray_hides_after',
    'behaviour_send_from_normal_leaves_window_alone',
    'behaviour_focus_lost_still_collapses',
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


def test_activate_wechat():
    """最小化窗口也能被找到并唤醒，且先记录形态再 ShowWindow；无窗口 fail-closed。"""
    table = {6: {'visible': True, 'iconic': True, 'normal': (800, 600)}}
    ns = _guard._build_ns(
        table, [(6, 100, 'WeChatMainWndForPC', '微信', _guard.ICONIC_RECT)])
    assert ns['activate_wechat']() == (6, 'minimized')
    order = [call[0] for call in ns['_user32'].calls
             if call[0] in ('IsWindowVisible', 'IsIconic', 'ShowWindow')]
    assert order[:2] == ['IsWindowVisible', 'IsIconic']
    assert order.index('ShowWindow') > order.index('IsIconic')
    empty = _guard._build_ns({}, [])
    with pytest.raises(empty['_SendError']) as excinfo:
        empty['activate_wechat']()
    assert excinfo.value.code == 'wechat_window_not_found'


def test_capture_window_state():
    """托盘隐藏优先于最小化；没有窗口句柄时必须 fail-closed。"""
    ns = _guard._build_ns({5: {'visible': False, 'iconic': True, 'normal': (800, 600)}}, [])
    assert ns['capture_window_state'](5) == 'hidden'
    ns = _guard._build_ns({5: {'visible': True, 'iconic': True, 'normal': (800, 600)}}, [])
    assert ns['capture_window_state'](5) == 'minimized'
    ns = _guard._build_ns({5: {'visible': True, 'iconic': False, 'normal': (800, 600)}}, [])
    assert ns['capture_window_state'](5) == 'normal'
    with pytest.raises(ns['_SendError']) as excinfo:
        ns['capture_window_state'](0)
    assert excinfo.value.code == 'wechat_window_not_found'


def test_restore_window_state():
    """最小化/隐藏各用对应命令；正常态不动窗口；Win32 失败不得冒泡。"""
    ns = _guard._build_ns({}, [])
    ns['restore_window_state'](5, 'minimized')
    assert ns['_user32'].calls == [('ShowWindow', 5, 6)]
    ns = _guard._build_ns({}, [])
    ns['restore_window_state'](5, 'hidden')
    assert ns['_user32'].calls == [('ShowWindow', 5, 0)]
    ns = _guard._build_ns({}, [])
    ns['restore_window_state'](5, 'normal')
    assert ns['_user32'].calls == []
    ns = _guard._build_ns({}, [])
    ns['restore_window_state'](0, 'minimized')
    assert ns['_user32'].calls == []
    ns = _guard._build_ns({}, [], raise_show=True)
    ns['restore_window_state'](5, 'minimized')
    assert len(ns['_logger'].warnings) == 1
