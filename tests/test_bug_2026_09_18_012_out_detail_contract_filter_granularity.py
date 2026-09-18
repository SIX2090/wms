# -*- coding: utf-8 -*-
"""BUG-2026-09-18-012 回归测试：出库明细表按「合同编号/工程名称」筛选粒度错配。

## 现象（用户截图）
筛选条件填「合同编号 = HD260909」，列表却出现 `HD260708` 的行，看起来"筛选完全没生效"。

## 根因
`_apply_header_or_item_contract_filters` 的语义是**单据级**：
「表头命中 OR **任一**明细命中」→ 整张单据通过筛选；而 `out_order_list` 的外层查询
是 `db.session.query(OutOrder, OutOrderItem).outerjoin(OutOrderItem, ...)`，
**按明细行展开**，一个单据有几条明细就渲染几行。

两者粒度不一致 → 只要单据里有**一条**明细的合同号匹配，该单据的**全部**明细行
（含合同号不匹配的行）都会显示出来。用户按 HD260909 筛选，却看到 HD260708 的行。

## 修复
对函数新增**显式**参数 `item_level`（默认 False 保持原单据级语义，避免影响
`sales.py` 等「每行=一张单据」的调用点）：
  - `item_level=False`：`表头命中 OR EXISTS(任一明细命中)`（原行为，不变）
  - `item_level=True` ：筛选**落到明细行**——
      `本行命中 OR (本行无合同标记 AND 表头命中)`
    即「筛选哪行就只显示哪行」；明细行自身未填合同号时仍归属表头合同，
    不会因为 `item.contract_no IS NULL` 被误过滤。

出库/入库/采购明细列表与导出走 `item_level=True`；
`sales.py`（`.distinct()`，每行=一张单据）保持默认 `False`。

## 用例
  T1. 明细级：筛选 HD260909，同单据内 HD260708 的明细行**不得**出现（本 BUG 断言）
  T2. 明细级：命中的 HD260909 明细行**必须**出现
  T3. 明细级：明细行合同号为空时，按表头合同号筛选仍应命中该行（不过度过滤）
  T4. 明细级：表头命中但明细行填了别的合同号 → 该行不出现（本行优先）
  T5. 单据级（默认 item_level=False）：语义不变，整单通过（防回归）
  T6. 明细级：不匹配的关键词 → 结果为空
  T7. 出库列表路由集成了 item_level=True（结构性断言：调用点传参）
  T8. 销售列表**不得**开启 item_level（结构性断言：单据级口径保持）
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit,
    Department, OutOrder, OutOrderItem, _apply_header_or_item_contract_filters,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed():
    """一张单据两条明细：明细1 合同号 HD260909，明细2 合同号 HD260708；表头 HD260708。"""
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    unit = Unit(code="PCS", name="个")
    dept = Department(code="D1", name="生产一部")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([wh, cat, unit, dept, user])
    db.session.flush()
    m1 = Material(code="M001", name="电缆", spec="3x2.5", category_id=cat.id,
                  unit_id=unit.id, price=10.0, stock=100.0)
    m2 = Material(code="M002", name="开关", spec="S2", category_id=cat.id,
                  unit_id=unit.id, price=5.0, stock=100.0)
    db.session.add_all([m1, m2])
    db.session.flush()

    order = OutOrder(order_no="OUT2609180001", date=date.today(), warehouse="仓库A",
                     department_id=dept.id, business_type="领料单", status="completed",
                     contract_no="HD260708", project_name="工程甲", operator_id=user.id)
    db.session.add(order)
    db.session.flush()
    db.session.add_all([
        OutOrderItem(out_order_id=order.id, material_id=m1.id, quantity=1, price=10.0,
                     amount=10.0, contract_no="HD260909", project_name="工程乙"),
        OutOrderItem(out_order_id=order.id, material_id=m2.id, quantity=2, price=5.0,
                     amount=10.0, contract_no="HD260708", project_name="工程甲"),
    ])
    db.session.commit()
    return wh.id


def _seed_null_item_contract():
    """一单两明细：明细1 合同号为空（归属表头），明细2 填了别的合同号。表头 HD260909。"""
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    unit = Unit(code="PCS", name="个")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([wh, cat, unit, user])
    db.session.flush()
    m1 = Material(code="M101", name="线缆", category_id=cat.id, unit_id=unit.id,
                  price=1.0, stock=10.0)
    m2 = Material(code="M102", name="插座", category_id=cat.id, unit_id=unit.id,
                  price=1.0, stock=10.0)
    db.session.add_all([m1, m2])
    db.session.flush()
    order = OutOrder(order_no="OUT2609180100", date=date.today(), warehouse="仓库B",
                     business_type="领料单", status="completed",
                     contract_no="HD260909", project_name="工程乙", operator_id=user.id)
    db.session.add(order)
    db.session.flush()
    db.session.add_all([
        OutOrderItem(out_order_id=order.id, material_id=m1.id, quantity=1, price=1.0,
                     amount=1.0, contract_no=None, project_name=None),
        OutOrderItem(out_order_id=order.id, material_id=m2.id, quantity=1, price=1.0,
                     amount=1.0, contract_no="HD260708", project_name="工程甲"),
    ])
    db.session.commit()
    return wh.id


def _codes(**kwargs):
    """按明细级筛选返回命中的物料编码集合（用于区分「哪一行」）。"""
    with app_module.app.app_context():
        from sqlalchemy.orm import joinedload
        query = db.session.query(OutOrder, OutOrderItem).outerjoin(
            OutOrderItem, OutOrderItem.out_order_id == OutOrder.id
        ).options(joinedload(OutOrderItem.material))
        query = _apply_header_or_item_contract_filters(
            query, OutOrder, OutOrderItem, 'out_order_id',
            contract_no_filter=kwargs.get('contract_no', ''),
            project_name_filter=kwargs.get('project_name', ''),
            item_level=kwargs.get('item_level', False),
        )
        return sorted(row[1].material.code for row in query.all() if row[1] is not None)


def _reset():
    db.drop_all()
    db.create_all()


def test_T1_item_level_excludes_other_contract_rows():
    """本 BUG 核心断言：明细级筛选 HD260909，HD260708 的明细行不得出现。"""
    with app_module.app.app_context():
        _reset()
        _seed()
    codes = _codes(contract_no="HD260909", item_level=True)
    assert codes == ["M001"], f"明细级筛选应只返回命中行 M001，实际 {codes}"


def test_T2_item_level_includes_matched_row():
    """命中的 HD260909 明细行必须出现。"""
    with app_module.app.app_context():
        _reset()
        _seed()
    assert "M001" in _codes(contract_no="HD260909", item_level=True)


def test_T3_item_level_null_item_contract_falls_back_to_header():
    """明细行自身无合同号时归属表头：按表头合同号筛选仍应命中该行。"""
    with app_module.app.app_context():
        _reset()
        _seed_null_item_contract()
    codes = _codes(contract_no="HD260909", item_level=True)
    assert codes == ["M101"], f"明细无合同号应回退表头命中 M101，实际 {codes}"


def test_T4_item_level_row_contract_wins_over_header():
    """明细行填了别的合同号 → 即使表头命中，该行也不出现（本行优先）。"""
    with app_module.app.app_context():
        _reset()
        _seed_null_item_contract()
    codes = _codes(contract_no="HD260909", item_level=True)
    assert "M102" not in codes, "明细行已显式填写 HD260708，不应被表头 HD260909 带出"


def test_T5_document_level_default_unchanged():
    """默认 item_level=False 时保持原单据级语义：整单通过（两条明细都在）。"""
    with app_module.app.app_context():
        _reset()
        _seed()
    codes = _codes(contract_no="HD260909", item_level=False)
    assert codes == ["M001", "M002"], f"单据级语义应整单通过，实际 {codes}"


def test_T6_item_level_no_match_returns_empty():
    """不匹配的关键词 → 明细级筛选结果为空。"""
    with app_module.app.app_context():
        _reset()
        _seed()
    assert _codes(contract_no="NOT_EXISTS", item_level=True) == []


def test_T7_out_order_list_uses_item_level():
    """结构性断言：出库列表与导出调用点开启 item_level=True。"""
    src = (ROOT / "app" / "routes" / "out_order.py").read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(
        r'_apply_header_or_item_contract_filters\(\s*\n\s*query,\s*OutOrder', src)]
    assert len(calls) == 2, f"预期出库有 2 个调用点（列表+导出），实际 {len(calls)}"
    bounds = calls + [len(src)]
    for idx in range(len(calls)):
        seg = src[bounds[idx]:bounds[idx + 1]]
        assert re.search(r'item_level\s*=\s*True', seg), (
            f"出库调用点 #{idx + 1} 未开启 item_level=True")


def test_T8_sales_list_keeps_document_level():
    """结构性断言：销售列表（每行=一张单据）不得开启 item_level。"""
    src = (ROOT / "app" / "routes" / "sales.py").read_text(encoding="utf-8")
    calls = [m.start() for m in re.finditer(
        r'_apply_header_or_item_contract_filters\(', src)]
    assert len(calls) == 2, f"预期销售有 2 个调用点，实际 {len(calls)}"
    bounds = calls + [len(src)]
    for idx in range(len(calls)):
        seg = src[bounds[idx]:bounds[idx + 1]]
        assert not re.search(r'item_level\s*=\s*True', seg), (
            f"销售调用点 #{idx + 1} 不应开启 item_level（其外层查询有 .distinct()，每行一张单据）")
