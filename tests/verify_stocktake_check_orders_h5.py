# -*- coding: utf-8 -*-
"""INV-BATCH-001-E / BUG-2026-09-04-005 H5 锚点：mobile_scan 盘点先选盘点单。

验证 mobile_scan.html：
- check 模式显示仓库选择（盘点也要先定仓库，与盘点单仓库一致）；
- check 模式新增「盘点单（必选）」下拉与"暂无进行中盘点单"提示；
- 提交 payload 携带 check_id；提交前校验已选盘点单（否则阻止）。
"""
from pathlib import Path
import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "mobile_scan.html"


def _text():
    return TPL.read_text(encoding="utf-8")


@pytest.mark.parametrize('mode', ['in', 'out', 'check', 'query', 'confirm'])
def test_check_mode_shows_warehouse_field(mode):
    """Check actual rendering: four stock modes require a visible warehouse, confirm has its own filter."""
    template = Environment(loader=FileSystemLoader(str(TPL.parent))).get_template(TPL.name)
    context = template.new_context(dict(mode=mode, mode_config={'title':'test','icon':''},
        warehouses=[], departments=[], default_warehouse=None, location_management_enabled=False,
        can_write=False, csrf_token=lambda:'test', url_for=lambda *a,**kw:'#'))
    html = BeautifulSoup(''.join(template.blocks['content'](context)), 'html.parser')
    field = html.select_one('#warehouseInput')
    if mode == 'confirm':
        assert field is None and html.select_one('#confirmWarehouseSelect') is not None
    else:
        assert field is not None and field.has_attr('required')
        assert 'd-none' not in field.parent.get('class', [])


def test_check_order_dropdown_present():
    """check 模式必须含「盘点单（必选）」下拉与无单提示。"""
    src = _text()
    assert 'id="checkOrderSelect"' in src
    assert "盘点单（必选）" in src
    assert "电脑端「盘点管理」" in src
    assert "/mobile/api/check_orders?warehouse=" in src


def test_payload_carries_check_id():
    """提交 payload 必须携带 check_id（仅盘点模式）。"""
    src = _text()
    assert "check_id: mode === 'check' && checkOrderSelect ? checkOrderSelect.value : undefined" in src


def test_submit_blocked_without_selected_order():
    """未选盘点单时必须在提交前拦截并提示。"""
    src = _text()
    assert "!checkOrderSelect.value" in src
    assert "请选择盘点单" in src
    assert "暂无进行中的盘点单" in src


def test_warehouse_change_reloads_orders():
    """切换仓库后必须重置并重新加载盘点单列表。"""
    src = _text()
    assert "lastCheckWh" in src
    assert "warehouseInput.addEventListener('change'" in src
