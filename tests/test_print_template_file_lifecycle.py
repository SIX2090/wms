"""打印模板文件生命周期：真实路由、内存库和隔离上传目录。"""
import io
import shutil
from pathlib import Path

import pytest
from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import app as w

MODELS = ('InOrderPrintTemplate', 'OutOrderPrintTemplate', 'ExcelPrintTemplate')
URLS = ('/in_order_print_template/{}/delete', '/out_order_print_template/{}/delete', '/print_templates/{}/delete')


def test_pytest_static_writes_use_external_directory():
    assert not Path(w.app.static_folder).resolve().is_relative_to(Path(w.__file__).resolve().parent)


@pytest.fixture
def case(tmp_path, monkeypatch):
    static = tmp_path / 'static'
    shutil.copytree(Path(w.__file__).parent / 'static' / 'templates', static / 'templates')
    (static / 'uploads' / 'print_templates').mkdir(parents=True)
    monkeypatch.setattr(w.app, 'static_folder', str(static))
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        w.db.session.add(w.User(id=1, username='file-test', role='admin', password_hash='synthetic-only', must_change_password=False))
        w.db.session.commit()
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = '1'
        session['_fresh'] = True
    yield client, static
    with w.app.app_context():
        w.db.session.remove()


def add_template(index, path):
    with w.app.app_context():
        values = dict(name='file lifecycle', template_type='excel', excel_template_path=path)
        if index == 2:
            values.update(target_type='document', target_code='in_order')
        row = getattr(w, MODELS[index])(**values)
        w.db.session.add(row)
        w.db.session.commit()
        return row.id


@pytest.mark.parametrize('index', range(3))
def test_delete_last_reference_removes_file(case, index):
    client, static = case
    path = static / 'uploads/print_templates/owned.xlsx'
    path.write_bytes(b'owned template')
    tid = add_template(index, '/static/uploads/print_templates/owned.xlsx')
    response = client.post(URLS[index].format(tid))
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
    assert not path.exists()


@pytest.mark.parametrize('index', range(3))
@pytest.mark.parametrize('alias', ['/static/uploads/print_templates/owned.xlsx', 'uploads/print_templates/owned.xlsx', 'owned.xlsx'])
def test_shared_reference_in_other_model_preserves_file(case, index, alias):
    client, static = case
    path = static / 'uploads/print_templates/owned.xlsx'
    path.write_bytes(b'shared')
    tid = add_template(index, '/static/uploads/print_templates/owned.xlsx')
    remaining_index = (index + 1) % 3
    remaining_id = add_template(remaining_index, alias)
    assert client.post(URLS[index].format(tid)).status_code == 200
    assert path.read_bytes() == b'shared'
    assert client.post(URLS[remaining_index].format(remaining_id)).status_code == 200
    assert not path.exists()


@pytest.mark.parametrize('index', range(3))
@pytest.mark.parametrize('kind', ['builtin', 'outside', 'source'])
def test_protected_template_files_survive_delete(case, index, kind):
    client, static = case
    if kind == 'builtin':
        path = static / 'uploads/print_templates/builtin_keep.xlsx'
        url = '/static/uploads/print_templates/builtin_keep.xlsx'
    elif kind == 'source':
        path = static / 'templates/source_keep.xlsx'
        url = '/static/templates/source_keep.xlsx'
    else:
        path = static.parent / 'outside.xlsx'
        url = '/static/../outside.xlsx'
    path.write_bytes(b'protected')
    tid = add_template(index, url)
    assert client.post(URLS[index].format(tid)).status_code == 200
    assert path.read_bytes() == b'protected'


@pytest.mark.parametrize('index', range(3))
def test_failed_delete_commit_keeps_row_and_file(case, index, monkeypatch):
    client, static = case
    path = static / 'uploads/print_templates/owned.xlsx'
    path.write_bytes(b'keep')
    tid = add_template(index, '/static/uploads/print_templates/owned.xlsx')
    def fail():
        raise RuntimeError('synthetic commit failure')
    monkeypatch.setattr(w.db.session, 'commit', fail)
    assert client.post(URLS[index].format(tid)).status_code >= 400
    assert path.read_bytes() == b'keep'
    with w.app.app_context():
        assert w.db.session.get(getattr(w, MODELS[index]), tid) is not None


def xlsx():
    from openpyxl import Workbook
    book = Workbook()
    book.active['A1'] = '模板'
    output = io.BytesIO()
    book.save(output)
    book.close()
    output.seek(0)
    return output


CREATE = ('/in_order_print_template/add', '/out_order_print_template/add', '/print_templates/upload', '/print_templates/create_blank')


def payload(endpoint):
    data = dict(name='new file', target_type='document', target_code='check' if endpoint.endswith('create_blank') else 'in_order')
    if not endpoint.endswith('create_blank'):
        data['excel_file'] = (xlsx(), 'same.xlsx')
    return data


@pytest.mark.parametrize('endpoint', CREATE)
def test_create_failure_does_not_leak_new_file(case, endpoint, monkeypatch):
    client, static = case
    def fail():
        raise RuntimeError('synthetic commit failure')
    monkeypatch.setattr(w.db.session, 'commit', fail)
    response = client.post(endpoint, data=payload(endpoint))
    assert response.status_code == 500
    leftovers = list((static / 'uploads/print_templates').glob('*'))
    assert not [path for path in leftovers if not path.name.startswith('builtin_')]


@pytest.mark.parametrize('endpoint', CREATE[:3])
def test_partial_upload_failure_does_not_leak_new_file(case, endpoint, monkeypatch):
    from werkzeug.datastructures import FileStorage
    client, static = case
    def fail(self, destination, *args, **kwargs):
        Path(destination).write_bytes(b'partial')
        raise OSError('synthetic disk write failure')
    monkeypatch.setattr(FileStorage, 'save', fail)
    assert client.post(endpoint, data=payload(endpoint)).status_code == 500
    assert not list((static / 'uploads/print_templates').glob('*'))


def test_new_uploads_with_same_filename_are_independent(case):
    client, static = case
    first = client.post(CREATE[0], data=payload(CREATE[0])).get_json()['id']
    second = client.post(CREATE[0], data=payload(CREATE[0])).get_json()['id']
    with w.app.app_context():
        paths = [w.db.session.get(w.InOrderPrintTemplate, tid).excel_template_path for tid in (first, second)]
    assert paths[0] != paths[1]
    assert len(list((static / 'uploads/print_templates').glob('*'))) == 2
    assert client.post(URLS[0].format(first)).status_code == 200
    assert len(list((static / 'uploads/print_templates').glob('*'))) == 1


def test_partial_blank_copy_is_removed(case, monkeypatch):
    client, static = case
    original_copy = shutil.copyfile
    def fail(source, destination, *args, **kwargs):
        if Path(destination).name.startswith('custom_'):
            Path(destination).write_bytes(b'partial')
            raise OSError('synthetic partial copy')
        return original_copy(source, destination, *args, **kwargs)
    monkeypatch.setattr(shutil, 'copyfile', fail)
    assert client.post(CREATE[3], data=payload(CREATE[3])).status_code == 500
    assert not list((static / 'uploads/print_templates').glob('custom_*'))


@pytest.mark.parametrize('index', range(3))
def test_file_locked_after_committed_delete_keeps_success(case, index, monkeypatch):
    client, static = case
    path = static / 'uploads/print_templates/owned.xlsx'
    path.write_bytes(b'locked')
    tid = add_template(index, '/static/uploads/print_templates/owned.xlsx')
    original_unlink = Path.unlink
    def fail(target, *args, **kwargs):
        if target == path:
            raise PermissionError('synthetic sharing violation')
        return original_unlink(target, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', fail)
    response = client.post(URLS[index].format(tid))
    assert response.status_code == 200
    assert response.get_json()['status'] == 'success'
    assert path.read_bytes() == b'locked'
    with w.app.app_context():
        assert w.db.session.get(getattr(w, MODELS[index]), tid) is None
