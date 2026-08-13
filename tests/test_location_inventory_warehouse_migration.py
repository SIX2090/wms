from __future__ import annotations

import importlib.util
import sqlite3
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


ROOT = Path(__file__).resolve().parent.parent
MIGRATION_PATH = ROOT / 'app' / 'migrations' / 'versions' / '8b17c4d90a2e_location_inventory_warehouse_compat.py'


def _load_migration():
    spec = importlib.util.spec_from_file_location('location_inventory_warehouse_compat', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _create_legacy_schema(connection):
    connection.exec_driver_sql(
        """
        CREATE TABLE warehouse (
            id INTEGER PRIMARY KEY,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE TABLE location_inventory (
            id INTEGER PRIMARY KEY,
            material_id INTEGER NOT NULL,
            location VARCHAR(100) NOT NULL,
            quantity FLOAT
        )
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO warehouse (id, code, name) VALUES
        (1, 'WH-A', '材料仓'),
        (2, 'WH-B', '成品仓'),
        (3, '材料仓', '另一仓'),
        (4, 'WH-C', '原料仓')
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO location_inventory (id, material_id, location, quantity) VALUES
        (1, 10, '材料仓', 1),
        (2, 11, 'WH-B', 2),
        (3, 12, '不存在仓', 3),
        (4, 13, '材料仓 ', 4),
        (5, 14, '原料仓', 5)
        """
    )


def test_location_inventory_migration_backfills_only_unique_warehouse_matches():
    engine = sa.create_engine('sqlite:///:memory:')
    migration = _load_migration()
    with engine.begin() as connection:
        _create_legacy_schema(connection)
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.upgrade()

        columns = {
            row[1]: row for row in connection.exec_driver_sql(
                'PRAGMA table_info(location_inventory)'
            ).fetchall()
        }
        assert columns['warehouse_id'][3] == 0

        rows = connection.exec_driver_sql(
            'SELECT id, warehouse_id FROM location_inventory ORDER BY id'
        ).fetchall()
        assert rows == [(1, None), (2, 2), (3, None), (4, None), (5, 4)]

        indexes = connection.exec_driver_sql(
            'PRAGMA index_list(location_inventory)'
        ).fetchall()
        assert any(row[1] == 'idx_location_inventory_warehouse' for row in indexes)

        foreign_keys = connection.exec_driver_sql(
            'PRAGMA foreign_key_list(location_inventory)'
        ).fetchall()
        assert any(row[2] == 'warehouse' and row[3] == 'warehouse_id' for row in foreign_keys)


def test_location_inventory_model_declares_nullable_warehouse_id():
    from app import LocationInventory

    column = LocationInventory.__table__.c.warehouse_id
    assert column.nullable is True
    assert {foreign_key.target_fullname for foreign_key in column.foreign_keys} == {'warehouse.id'}


def test_startup_sqlite_migration_backfills_only_unique_warehouse_matches(tmp_path):
    from app import app as flask_app, auto_migrate_database, db

    db_path = tmp_path / 'legacy.db'
    engine = sa.create_engine(f'sqlite:///{db_path}')
    db.metadata.create_all(engine)
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            DROP TABLE location_inventory;
            CREATE TABLE location_inventory (
                id INTEGER PRIMARY KEY,
                material_id INTEGER NOT NULL,
                location VARCHAR(100) NOT NULL,
                quantity FLOAT
            );
            INSERT INTO warehouse (id, code, name, is_default) VALUES
                (1, 'WH-A', '材料仓', 1),
                (2, 'WH-B', '成品仓', 0),
                (3, '材料仓', '另一仓', 0),
                (4, 'WH-C', '原料仓', 0);
            INSERT INTO location_inventory (id, material_id, location, quantity) VALUES
                (1, 10, '材料仓', 1),
                (2, 11, 'WH-B', 2),
                (3, 12, '不存在仓', 3),
                (4, 13, '材料仓 ', 4),
                (5, 14, '原料仓', 5);
            """
        )
        connection.commit()
    finally:
        connection.close()

    previous_uri = flask_app.config['SQLALCHEMY_DATABASE_URI']
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    try:
        auto_migrate_database()
    finally:
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = previous_uri

    connection = sqlite3.connect(db_path)
    try:
        columns = {
            row[1] for row in connection.execute(
                'PRAGMA table_info(location_inventory)'
            ).fetchall()
        }
        rows = connection.execute(
            'SELECT id, warehouse_id FROM location_inventory ORDER BY id'
        ).fetchall()
        indexes = connection.execute(
            'PRAGMA index_list(location_inventory)'
        ).fetchall()
    finally:
        connection.close()

    assert 'warehouse_id' in columns
    assert rows == [(1, None), (2, 2), (3, None), (4, None), (5, 4)]
    assert any(row[1] == 'idx_location_inventory_warehouse' for row in indexes)
