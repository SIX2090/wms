# -*- coding: utf-8 -*-
"""A18 回归锁：在用脚本不得再绑定旧环境路径（/Coze/Drive、/workspace）。

AUDIT-FULL-20261016-001-F09-F08（原 A18）：deep_audit_lib 及 8 个 mod 脚本硬编码
/Coze/Drive/扣子/wms，scan_all_menus 硬编码 /workspace，换机即不可运行。
归档脚本（scripts/archive/**）与历史审计文档保留原样，不纳入本锁。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = [
    ROOT / 'scripts' / 'deep_audit_lib.py',
    ROOT / 'scripts' / 'deep_audit_mod1.py',
    ROOT / 'scripts' / 'deep_audit_mod1b.py',
    ROOT / 'scripts' / 'deep_audit_mod2.py',
    ROOT / 'scripts' / 'deep_audit_mod3.py',
    ROOT / 'scripts' / 'deep_audit_mod4.py',
    ROOT / 'scripts' / 'deep_audit_mod4b.py',
    ROOT / 'scripts' / 'deep_audit_mod5.py',
    ROOT / 'scripts' / 'deep_audit_mod6.py',
    ROOT / 'scripts' / 'audit' / 'scan_all_menus.py',
    ROOT / 'start_qa_server.py',
    ROOT / 'tools' / 'fix_bug_2026_10_07_004_vision_json_only.py',
]


def test_active_scripts_have_no_legacy_roots():
    for path in ACTIVE:
        text = path.read_text(encoding='utf-8')
        assert '/Coze/Drive' not in text, path.name
        assert '/workspace' not in text, path.name


def test_deep_audit_lib_resolves_repo_from_file():
    text = (ROOT / 'scripts' / 'deep_audit_lib.py').read_text(encoding='utf-8')
    assert 'Path(__file__).resolve().parents[1]' in text


def test_menu_scanner_resolves_repo_from_file():
    text = (ROOT / 'scripts' / 'audit' / 'scan_all_menus.py').read_text(encoding='utf-8')
    assert 'Path(__file__).resolve().parents[2]' in text
