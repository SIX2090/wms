# -*- coding: utf-8 -*-
"""BUG-2026-11-13-002 回归锁：重复点击提示由绿色改为黄色。

纯静态形态断言，不导入 WMS 应用模块、不连接数据库、不访问现役服务。
与 scripts/verify_print_duplicate_toast.py 共用同一组检查，保证本地离线验证
和 CI 断言不会漂移。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / 'scripts' / 'verify_print_duplicate_toast.py'


def _load_verifier():
    spec = importlib.util.spec_from_file_location('verify_print_duplicate_toast', VERIFIER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKS = _load_verifier().collect_checks(ROOT)
GUARDED_SITES = {
    'app/static/js/pages/material-list.js',
    'app/templates/in_order_detail.html',
    'app/templates/out_order_detail.html',
}


@pytest.mark.parametrize('name, passed, detail', CHECKS, ids=[row[0] for row in CHECKS])
def test_duplicate_toast_shape(name, passed, detail):
    assert passed, f'{name}: {detail}'


def test_toast_suite_is_complete():
    """防止有人通过删减检查项把锁变没（R8 净收益原则）。"""
    assert len(CHECKS) >= 20, f'检查项被删减: {len(CHECKS)}'
    assert all(name.startswith('C') for name, _, _ in CHECKS)


def test_every_call_site_is_covered():
    """三处入口都必须有专属的 warning 断言，不能只覆盖其中一两个。"""
    for site in GUARDED_SITES:
        tag = site.rsplit('/', 1)[-1]
        assert any(name.endswith(tag + ' warning on duplicate') for name, _, _ in CHECKS), site
