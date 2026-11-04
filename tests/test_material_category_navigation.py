"""Follow rendered category links after a material keyword search, using an isolated DB."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def category_links(html):
    # Header "all", tree "all categories", then the category nodes in display order.
    panel = html.split('<aside class="material-category-panel">', 1)[1].split('</aside>', 1)[0]
    return [attrs['href'] for tag, attrs in Elements(panel).tags if tag == 'a']


@pytest.fixture
def category_case(bom_case):
    from app import db, Material, MaterialCategory, set_system_setting
    client, ids = bom_case
    set_system_setting('inventory_alert_enabled', '1')
    parent = MaterialCategory(code='CAT-P', name='导航父分类')
    db.session.add(parent)
    db.session.flush()
    child = MaterialCategory(code='CAT-P-C', name='导航子分类', parent_id=parent.id)
    db.session.add(child)
    db.session.flush()
    db.session.add_all([
        Material(code='NAV-PARENT', name='父类明细', category_id=parent.id, unit_id=ids['unit']),
        Material(code='NAV-CHILD', name='子类明细', category_id=child.id, unit_id=ids['unit']),
    ])
    db.session.get(Material, ids['material']).spec = 'RNB1.25-8'
    db.session.commit()
    return client, parent.id, child.id


@pytest.mark.parametrize('entry', ['parent', 'child', 'header_all', 'tree_all'])
def test_category_navigation_clears_keyword_and_page(category_case, entry):
    client, parent_id, child_id = category_case
    response = client.get('/material', query_string={
        'search': '1.25-8', 'category_id': child_id, 'page': 2,
        'status': 'active', 'embedded': '1',
    })
    assert response.status_code == 200
    links = category_links(response.get_data(as_text=True))
    if entry in ('header_all', 'tree_all'):
        link = links[0 if entry == 'header_all' else 1]
    else:
        wanted = str(parent_id if entry == 'parent' else child_id)
        link = next(url for url in links if parse_qs(urlsplit(url).query).get('category_id') == [wanted])
    params = parse_qs(urlsplit(link).query)
    assert 'search' not in params
    assert 'page' not in params
    assert params['status'] == ['active']
    assert params['embedded'] == ['1']
    result = client.get(link)
    assert result.status_code == 200
    html = result.get_data(as_text=True)
    tags = Elements(html).tags
    search = next(a for t, a in tags if t == 'input' and a.get('name') == 'search')
    assert search['value'] == ''
    body = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert 'NAV-CHILD' in body
    assert ('NAV-PARENT' in body) == (entry != 'child')
    assert ('B-M' in body) == (entry in ('header_all', 'tree_all'))


@pytest.mark.parametrize('status', ['inactive', 'all'])
def test_category_navigation_keeps_explicit_other_filters(category_case, status):
    client, _, _ = category_case
    response = client.get('/material', query_string={
        'search': '1.25-8', 'stock_filter': 'low', 'status': status, 'embedded': '1',
    })
    assert response.status_code == 200
    for link in category_links(response.get_data(as_text=True)):
        params = parse_qs(urlsplit(link).query)
        assert 'search' not in params
        assert params['stock_filter'] == ['low']
        assert params['status'] == [status]
        assert params['embedded'] == ['1']


def test_search_within_selected_category_remains_scoped(category_case):
    client, parent_id, _ = category_case
    response = client.get('/material', query_string={'category_id': parent_id, 'search': '子类'})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    attrs = next(a for t, a in Elements(html).tags if t == 'input' and a.get('name') == 'category_id')
    assert attrs['value'] == str(parent_id)
    body = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
    assert 'NAV-CHILD' in body
    assert 'NAV-PARENT' not in body
    assert 'B-M' not in body
