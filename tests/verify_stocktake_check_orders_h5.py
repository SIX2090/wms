# -*- coding: utf-8 -*-
"""INV-BATCH-001-E / BUG-2026-09-04-005 H5 锚点：mobile_scan 盘点先选盘点单。

验证 mobile_scan.html：
- check 模式显示仓库选择（盘点也要先定仓库，与盘点单仓库一致）；
- check 模式新增「盘点单（必选）」下拉与"暂无进行中盘点单"提示；
- 提交 payload 携带 check_id；提交前校验已选盘点单（否则阻止）。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "app" / "templates" / "mobile_scan.html"


def _text():
    return TPL.read_text(encoding="utf-8")


def test_check_mode_shows_warehouse_field():
    """盘点模式仓库字段必须可见（与 in/out 同级）。"""
    src = _text()
    assert "mode not in ['in', 'out', 'check']" in src, (
        "仓库字段可见性须把 check 与 in/out 并列"
    )


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
