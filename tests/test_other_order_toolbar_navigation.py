"""Unavailable navigation must never appear actionable on new or edited orders."""
from html.parser import HTMLParser
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.buttons = {}
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'button' and 'data-action' in attrs:
            self.buttons[attrs['data-action']] = attrs
        if tag == 'a':
            self.links.append(attrs)


@pytest.mark.parametrize('mode', ['in', 'out'])
@pytest.mark.parametrize('order_id', [None, 7])
def test_unimplemented_navigation_is_disabled_with_guidance(mode, order_id):
    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    controls = Controls(env.get_template('_other_order_toolbar.html').render(
        toolbar_mode=mode, order_id=order_id, has_complete_action=mode == 'in'))
    for action in ['nav-first', 'nav-prev', 'nav-next', 'nav-last']:
        assert 'disabled' in controls.buttons[action]
        assert '查找单据' in controls.buttons[action]['title']
    assert 'disabled' not in controls.buttons['save']
    assert controls.links[0]['href'] == '/other_' + mode + '_order'


@pytest.mark.parametrize('mode', ['in', 'out'])
def test_explicit_return_url_keeps_its_filter_query(mode):
    env = Environment(loader=FileSystemLoader(str(ROOT / 'app/templates')))
    url = '/other_' + mode + '_order?warehouse_id=2&search=M8'
    controls = Controls(env.get_template('_other_order_toolbar.html').render(
        toolbar_mode=mode, order_id=7, return_list_url=url))
    assert controls.links[0]['href'] == url
