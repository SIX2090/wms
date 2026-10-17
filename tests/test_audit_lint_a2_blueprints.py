# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F07：A2 必须覆盖 blueprint 路由与 app/ai。

旧实现只认 @app.route 且整体豁免 app/ai，24 条 blueprint 路由 + 74 个 AI 文件脱管。
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'lint_wms_rules.py'


def _load():
    spec = importlib.util.spec_from_file_location('lint_wms_rules_module', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scan(tmp_path, source):
    app_dir = tmp_path / 'app' / 'routes'
    app_dir.mkdir(parents=True)
    target = app_dir / 'bp_routes.py'
    target.write_text(source, encoding='utf-8')
    rule = _load().RULES['a2']
    return rule.scan([target], tmp_path)


def test_blueprint_post_without_auth_is_reported(tmp_path):
    violations = _scan(tmp_path, "@bp.post('/x')\ndef x():\n    return 1\n")
    assert len(violations) == 1


def test_blueprint_post_with_login_is_allowed(tmp_path):
    violations = _scan(tmp_path, "@bp.post('/x')\n@login_required\ndef x():\n    return 1\n")
    assert violations == []


def test_blueprint_route_with_methods_is_reported(tmp_path):
    violations = _scan(tmp_path, "@bp.route('/y', methods=['PUT'])\ndef y():\n    return 1\n")
    assert len(violations) == 1


def test_a2_no_longer_excludes_ai(tmp_path):
    rule = _load().RULES['a2']
    assert rule.exclude_paths == ()
