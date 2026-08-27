# -*- coding: utf-8 -*-
"""A/B/C 独立验证的对抗性测试：C 切换引入的两个边界漏洞。

漏洞 1（串仓回归）：`_filter_txn_list_by_warehouse_scope` 用
`t.warehouse_id == warehouse_id` 判断精确命中。当调用方传入
warehouse_id=None（降级场景：filters 传了不存在的仓库名，loc_names 非空
但仓库解析失败）时，Python 的 `None == None` 为 True——所有
warehouse_id IS NULL 的行（含其他仓库的空 location 流水）被全部保留，
绕过空 location 按来源单据归属过滤，报表串仓。A 版本（两参数）无此问题，
C 引入回归。

漏洞 2（归属判定回归）：`_material_stock_unattributed` 关库位分支改为仅
`warehouse_id IS NOT NULL` 判归属。未回填的非空 location 行（如跨仓同名
库位歧义保留 NULL 的行）在旧逻辑下算"可归属"（仓库级严格校验，防 A 仓
掩护 B 仓，BUG-2026-08-16-009），新逻辑误判"不可归属"→ 回退全局
Material.stock 口径，保护被削弱。

T1. 降级场景（不存在仓库名）：空 location 的其他仓库流水不得计入（修复前会串仓）。
T2. 降级场景：location=仓库名 的流水仍按字符串口径计入（正常路径不受影响）。
T3. 未回填非空 location 行（歧义保留 NULL）：仍视为可归属，不回退全局口径。
"""
from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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
    db, InOrder, Material, MaterialCategory, StockTransaction, Unit, Warehouse,
    _collect_ledger_rows, _material_stock_unattributed, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    set_system_setting("location_management_enabled", "0")
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT"),
        Warehouse(id=1, code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(id=2, code="WHB", name="仓库B", status="active"),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204", category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _mk_in_order(warehouse_name, no="IN-1"):
    o = InOrder(order_no=no, date=date.today(), warehouse=warehouse_name,
                status='completed', business_type='采购入库')
    db.session.add(o)
    db.session.commit()
    return o


def _degraded_filters(ghost_name, mat):
    """降级场景：只传不存在的仓库名（无 warehouse_id / warehouse_code）。"""
    return {
        'start_date': None, 'end_date': None,
        'warehouse_id': 0, 'warehouse': ghost_name, 'warehouse_code': '',
        'business_type': '', 'material_code': mat.code,
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc', 'page': 1, 'page_size': 20,
        'hide_zero': False, 'export': '',
    }


class TestDegradedGhostWarehouseNoLeak:

    def test_null_location_other_warehouse_not_leaked(self):
        """T1：查询不存在的仓库名时，空 location 的仓库A 流水不得计入（修复前串仓）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            order_a = _mk_in_order('仓库A', no='IN-A')
            db.session.add_all([
                # 仓库A 的空 location 历史流水（warehouse_id IS NULL，无法回填的场景）
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=50,
                                 location=None, warehouse_id=None,
                                 reference_type='in_order', reference_id=order_a.id),
                # 仓库B 的空 location 流水
                StockTransaction(material_id=mat.id, transaction_type='in', quantity=99,
                                 location=None, warehouse_id=None,
                                 reference_type='in_order', reference_id=_mk_in_order('仓库B', no='IN-B').id),
            ])
            db.session.commit()
            rows = _collect_ledger_rows(_degraded_filters('幽灵仓库X', mat))
            total_in = sum(r['in_quantity'] for r in rows)
            assert abs(total_in) < 1e-6, \
                f"不存在仓库名的查询不应计入任何空 location 流水，实际 in={total_in}（串仓）"

    def test_named_location_still_matches(self):
        """T2：降级场景下 location=仓库名 的流水仍按字符串口径计入（正常路径不回归）。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            order_a = _mk_in_order('仓库A', no='IN-A')
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=30,
                                            location='仓库A', warehouse_id=None,
                                            reference_type='in_order', reference_id=order_a.id))
            db.session.commit()
            rows = _collect_ledger_rows(_degraded_filters('仓库A', mat))
            total_in = sum(r['in_quantity'] for r in rows)
            assert abs(total_in - 30) < 1e-6, \
                f"location='仓库A' 按字符串口径应计入 30，实际 {total_in}"


class TestUnattributedFallbackNotWeakened:

    def test_unbackfilled_named_location_still_attributed(self):
        """T3：warehouse_id NULL + location 非空（歧义未回填行）仍视为可归属。"""
        with app_module.app.test_request_context():
            _reset_db()
            mat = _seed()
            db.session.add(StockTransaction(material_id=mat.id, transaction_type='in', quantity=8,
                                            location='共用位', warehouse_id=None,
                                            reference_type='in_order', reference_id=1))
            db.session.commit()
            assert _material_stock_unattributed(mat.id) is False, \
                "非空 location 的未回填行应视为可归属（保持 BUG-2026-08-18-002 严格校验），" \
                "误判不可归属会回退全局口径、削弱 A 仓掩护 B 仓的防护"
