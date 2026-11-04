"""Fresh-install reservation must never overwrite existing user data."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_init', ROOT / 'tools/init_portable_database.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_existing_database_preserved_before_app_import(tmp_path):
    app_dir = tmp_path / 'app'
    (app_dir / 'instance').mkdir(parents=True)
    (app_dir / 'app.py').write_text("raise AssertionError('must not import application')")
    database = app_dir / 'instance/inventory.db'
    database.write_bytes(b'existing user data')
    with pytest.raises(FileExistsError):
        module.initialize_fresh(tmp_path)
    assert database.read_bytes() == b'existing user data'


def test_missing_app_does_not_create_database(tmp_path):
    with pytest.raises(ValueError):
        module.initialize_fresh(tmp_path)
    assert not (tmp_path / 'app').exists()
