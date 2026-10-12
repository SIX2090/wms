"""location_inventory.warehouse_id 兼容迁移测试（F3.1 后）。

F3.1 废弃 Alembic（app/migrations/ 已删除），schema 迁移机制唯一 =
auto_migrate_database() 启动幂等补列。本文件保留两条契约：
模型声明（nullable warehouse_id + 外键）与启动迁移回填行为
（仅唯一匹配仓库名才回填，撞名/未知/带空格一律不动）。
"""
from __future__ import annotations

import sqlite3

import sqlalchemy as sa


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
