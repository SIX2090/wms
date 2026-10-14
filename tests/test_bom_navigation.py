"""BOM belongs to master data in both menus, without changing role access."""
import re

import pytest
from flask import render_template
from types import SimpleNamespace
from app import app, db


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'production'])
def test_bom_is_under_master_data_for_existing_roles(role, monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    with app.app_context():
        db.create_all()
        with app.test_request_context('/bom'):
            html = render_template('base.html', current_user=SimpleNamespace(
                is_authenticated=True, role=role, username='navigation-test', id=1))
    modules = re.findall(r'<li class="nav-item module-menu">(.*?)</li>', html, re.S)
    owners = [section for section in modules if 'href="/bom"' in section]
    assert len(owners) == 1
    assert '<div class="flyout-title">基础资料</div>' in owners[0]
    assert 'BOM表管理' in owners[0]
    submenus = re.findall(r'<ul class="submenu-list">(.*?)</ul>', html, re.S)
    assert sum('href="/bom"' in section for section in submenus) == 1
    assert html.count('href="/bom"') == 2
    if role != 'admin':
        assert not any('href="/material"' in section for section in owners)
