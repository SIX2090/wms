"""Render actual shell/footer templates and preserve safe feedback navigation."""
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader
from tests.test_shell_navigation_asset import render_shell

ROOT = Path(__file__).resolve().parents[1]


class Footer(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.footers = []
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'footer' and 'wms-copyright' in values.get('class', '').split():
            self.footers.append(values)
        if tag == 'a' and values.get('href') == 'https://github.com/SIX2090/wms/issues':
            self.links.append(values)


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'viewer'])
def test_shell_has_one_copyright_and_non_destructive_feedback_link(role):
    html = render_shell(role)
    parsed = Footer(html)
    assert len(parsed.footers) == 1
    assert 'no-print' in parsed.footers[0]['class'].split()
    assert len(parsed.links) == 1
    assert parsed.links[0]['target'] == '_blank'
    assert {'noopener', 'noreferrer'} <= set(parsed.links[0]['rel'].split())
    assert '© 2026 OK1949-2024 版权所有' in html
    assert '联系微信：' in html and '问题反馈' in html
    assert '/static/css/copyright.css' in html


def test_login_renders_same_footer_and_styles():
    env = Environment(autoescape=True, loader=FileSystemLoader(ROOT / 'app/templates'))
    html = env.get_template('login.html').render(
        config={}, csrf_token=lambda: 'fixture-token',
        max_login_failures=lambda: 5, account_lock_minutes=lambda: 15,
        get_flashed_messages=lambda **kw: [],
        url_for=lambda endpoint, **kw: '/static/' + kw['filename'] if endpoint == 'static' else '/' + endpoint,
    )
    assert len(Footer(html).footers) == 1
    assert '© 2026 OK1949-2024 版权所有' in html
    assert '/static/css/copyright.css' in html
