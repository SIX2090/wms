"""Use the real matcher with SQLite CONCAT deliberately unavailable."""
import ast
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, String, create_engine, or_
from sqlalchemy.orm import declarative_base, Session


@pytest.fixture
def matcher():
    root = Path(__file__).resolve().parents[1]
    tree = ast.parse((root / 'app/routes/mobile.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == '_match_material_by_description')
    node.body = [n for n in node.body if not (isinstance(n, ast.ImportFrom) and n.module == 'app')]
    base = declarative_base()
    class Material(base):
        __tablename__ = 'synthetic_material'
        id = Column(Integer, primary_key=True)
        code = Column(String)
        name = Column(String)
        spec = Column(String)
    def connect():
        connection = sqlite3.connect(':memory:')
        assert all(not row[2] for row in connection.execute('PRAGMA database_list'))
        # Ubuntu's older SQLite lacks CONCAT; emulate that capability on newer hosts.
        connection.create_function('concat', -1, None)
        return connection
    engine = create_engine('sqlite://', creator=connect)
    base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            Material(code='R111', name='继电器', spec='红色塑料外壳 24V'),
            Material(code='6204', name='深沟球轴承', spec='6204'),
            Material(code='EMPTY', name='其他零件', spec=''),
        ])
        session.commit()
        scope = {'Material': Material, 'db': SimpleNamespace(or_=or_)}
        exec(compile(ast.Module(body=[node], type_ignores=[]), '<real-mobile-matcher>', 'exec'), scope)
        yield lambda description: [row.code for row in scope[node.name](description, session.query(Material))]
    engine.dispose()


@pytest.mark.parametrize('description,expected', [
    ('红色塑料外壳继电器', ['R111']),
    ('无法识别的黑色物体', []),
    ('银色轴承 6204', ['6204']),
    ('', []),
])
def test_description_lookup_works_without_sqlite_concat(matcher, description, expected):
    assert matcher(description) == expected
