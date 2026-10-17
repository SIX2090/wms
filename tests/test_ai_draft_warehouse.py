# -*- coding: utf-8 -*-
"""BUG-2026-10-17-011-F03：AI 建单必须解析并写入仓库（审计 P1）。

- 草稿不再以空仓库落库；解析顺序：显式 > 指令中的仓库名/编码 > 默认仓 > 单仓。
- AI 盘点的 system_stock 必须取仓库级账面，不能取全局 material.stock。
本用例用假 Warehouse 替换 ORM，避免依赖数据库夹具。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import app as wms  # noqa: E402


class FakeWarehouse:
    def __init__(self, id, code, name, status='active', is_default=False):
        self.id = id
        self.code = code
        self.name = name
        self.status = status
        self.is_default = is_default


class FakeQuery:
    def __init__(self, items):
        self.items = items

    def filter_by(self, **kwargs):
        return FakeQuery([i for i in self.items
                          if all(getattr(i, k, None) == v for k, v in kwargs.items())])

    def all(self):
        return list(self.items)


def _install(monkeypatch, items):
    class QueryWarehouse(FakeWarehouse):
        query = FakeQuery(items)

    monkeypatch.setattr(wms, 'Warehouse', QueryWarehouse)


@pytest.fixture()
def shops(monkeypatch):
    items = [FakeWarehouse(1, 'WH-A', '项目仓', is_default=True),
             FakeWarehouse(2, 'WH-B', '库存仓'),
             FakeWarehouse(3, 'WH-C', '停用仓', status='inactive')]
    _install(monkeypatch, items)
    return items


def test_matches_by_name_and_code(shops):
    assert wms._ai_match_warehouse('项目仓').name == '项目仓'
    assert wms._ai_match_warehouse('wh-b').name == '库存仓'


def test_inactive_warehouse_is_ignored(shops):
    assert wms._ai_match_warehouse('停用仓') is None


def test_default_used_when_message_has_no_warehouse(shops):
    assert wms._ai_resolve_draft_warehouse('生成领料单 A001 20').name == '项目仓'


def test_explicit_wins_and_missing_everything_returns_none(shops, monkeypatch):
    assert wms._ai_resolve_draft_warehouse('生成领料单', explicit='库存仓').name == '库存仓'
    _install(monkeypatch, [])
    assert wms._ai_resolve_draft_warehouse('生成领料单') is None


def test_draft_sources_write_warehouse_and_use_warehouse_stock():
    source = (APP_DIR / 'app.py').read_text(encoding='utf-8')
    assert source.count('warehouse=warehouse.name,') >= 4
    assert 'from_warehouse=from_warehouse.name,' in source
    assert 'to_warehouse=to_warehouse.name,' in source
    assert 'warehouse_stock = get_warehouse_stock_quantities(warehouse)' in source
    assert 'sys_stock = normalize_stock_quantity(warehouse_stock.get(material.id, 0))' in source
    assert "'system_stock': normalize_stock_quantity(m.stock or 0)" not in source
