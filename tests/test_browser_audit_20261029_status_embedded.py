"""Browser audit regressions against the isolated pytest database."""
from datetime import date

import pytest
from bs4 import BeautifulSoup


def test_approval_completed_and_other_statuses(bom_case):
    from app import db, PurchaseRequest
    client, _ = bom_case
    statuses = {'pending': '待审批', 'approved': '已通过',
                'rejected': '已驳回', 'completed': '已完成'}
    for status in statuses:
        db.session.add(PurchaseRequest(request_no='AUD-' + status, date=date(2026, 10, 29), status=status))
    db.session.commit()
    for status, label in statuses.items():
        response = client.get('/approval', query_string={'status': status, 'embedded': '1'})
        assert response.status_code == 200
        soup = BeautifulSoup(response.data, 'html.parser')
        row = next(row for row in soup.select('tbody tr') if 'AUD-' + status in row.get_text())
        assert label in row.get_text()
        assert '未知' not in row.get_text()


@pytest.mark.parametrize('path', [
    '/ai/inventory_health', '/ai/replenishment', '/ai/replenishment_live',
    '/ai/replenishment_smart', '/ai/document_jobs', '/ai/material_alias',
])
@pytest.mark.parametrize('embedded', [True, False])
def test_query_form_preserves_embedded_mode(bom_case, monkeypatch, path, embedded):
    import app as wms
    client, _ = bom_case
    monkeypatch.setattr(wms, '_ai_capability_allowed', lambda *args: True)
    response = client.get(path, query_string={'embedded': '1'} if embedded else {})
    assert response.status_code == 200
    soup = BeautifulSoup(response.data, 'html.parser')
    form = soup.find('form', attrs={'method': 'get'})
    assert form is not None
    hidden = form.find('input', attrs={'name': 'embedded'})
    assert (hidden is not None) == embedded
    if embedded:
        assert hidden.get('value') == '1'


@pytest.mark.parametrize('embedded', [True, False])
def test_alias_clear_keeps_embedding_only_when_needed(bom_case, embedded):
    client, _ = bom_case
    query = {'search': 'sample'}
    if embedded:
        query['embedded'] = '1'
    response = client.get('/ai/material_alias', query_string=query)
    soup = BeautifulSoup(response.data, 'html.parser')
    clear = next(a for a in soup.select('form.alias-search a') if a.get_text(strip=True) == '清空')
    assert ('embedded=1' in clear['href']) == embedded
