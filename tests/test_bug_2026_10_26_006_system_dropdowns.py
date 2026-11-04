"""System candidate completeness and viewport regression, using real page scripts."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_actual_system_dropdown_scripts():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for actual dropdown scripts')
    run = subprocess.run([node, '--max-old-space-size=96', str(ROOT / 'tests/frontend_system_dropdowns.cjs')],
                         cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert run.returncode == 0, run.stdout + run.stderr
    result = json.loads(run.stdout)
    assert result['passed'] == 31 and result['failed'] == 0


@pytest.fixture
def picker_client():
    sys.path.insert(0, str(ROOT / 'app'))
    import app as module
    with module.app.app_context():
        module.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        module.db.drop_all()
        module.db.create_all()
        user = module.User(username='dropdown-qa', password_hash='qa-no-login')
        module.db.session.add(user)
        for n in range(1, 126):
            module.db.session.add(module.Contract(contract_no='QA-%03d' % n,
                                                  project_name='候选工程%03d' % n, status='active'))
            module.db.session.add(module.Employee(code='QA-%03d' % n, name='候选员工%03d' % n))
        module.db.session.add(module.Contract(contract_no='OTHER', project_name='其他工程', status='active'))
        module.db.session.add(module.Employee(code='OTHER', name='其他员工'))
        module.db.session.commit()
        user_id = user.id
    client = module.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(user_id)
        session['user_id'] = str(user_id)
        session['_fresh'] = True
    yield client, module


@pytest.mark.parametrize('entity', ['contract', 'employee'])
def test_picker_api_does_not_silently_drop_match_51_and_later(picker_client, entity):
    client, _ = picker_client
    url = '/api/contracts?keyword=候选' if entity == 'contract' else '/employee/api/search?q=候选'
    response = client.get(url)
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    rows = data['data']['contracts'] if entity == 'contract' else data['data']
    assert len(rows) == 125
    codes = [row['contract_no'] if entity == 'contract' else row['code'] for row in rows]
    assert codes == ['QA-%03d' % n for n in range(1, 126)]
    assert (data['data']['total'] if entity == 'contract' else data['total']) == 125
    assert len(set(codes)) == 125


@pytest.mark.parametrize('entity', ['contract', 'employee'])
def test_picker_exact_empty_and_auth_contracts_are_preserved(picker_client, entity):
    client, module = picker_client
    url = '/api/contracts?keyword=' if entity == 'contract' else '/employee/api/search?q='
    exact = client.get(url + 'QA-125').get_json()
    rows = exact['data']['contracts'] if entity == 'contract' else exact['data']
    assert len(rows) == 1
    missing = client.get(url + 'missing-candidate').get_json()
    assert (missing['data']['contracts'] if entity == 'contract' else missing['data']) == []
    anonymous = module.app.test_client().get(url + '候选')
    assert anonymous.status_code in (302, 401)


@pytest.mark.parametrize('page,expected', [
    ('material_add.html', ['WMS.positionDropdown(unitSearch', 'WMS.positionDropdown(supplierSearch']),
    ('in_order_add.html', ['WMS.positionDropdown(searchInput']),
    ('in_order.html', ['WMS.positionDropdown(input, dropdown']),
    ('out_order_add.html', ['WMS.positionDropdown(pickerInput, pickerDropdown']),
    ('material.html', ['WMS.positionDropdown(input, menu']),
    ('subcontract_detail.html', ['WMS.positionDropdown(input, dropdown']),
    ('ai_location_recommendation.html', ['WMS.positionDropdown(this, document.getElementById']),
])
def test_custom_picker_uses_existing_viewport_helper(page, expected):
    source = (ROOT / 'app/templates' / page).read_text(encoding='utf-8')
    assert all(call in source for call in expected)
