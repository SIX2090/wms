# -*- coding: utf-8 -*-
"""BUG-2026-09-07-015 回归：库存报表每次查询/翻页重复全量计算的两处根因。

与 BUG-2026-09-07-012/013/014 不同：库存报表**没有** REPORT_ROW_LIMIT 截断
（`_collect_inventory_rows` 不调用 `_report_check_row_limit`），因此不存在
R2「汇总失真」。实测（2000 物料 / 15 万流水，内存 SQLite）真正的开销在：

  [1] 物料侧 category/unit/supplier 懒加载 N+1
      —— 每物料不同供应商时 2008 条 SQL / 0.380s（同供应商时仅 9 条 / 0.159s）
  [2] get_warehouse_stock_quantities 的空 location 回补扫描
      —— 把 22330 行流水加载进 Python，0.476s，占单次查询 0.51s 的约 70%
      且**每翻一页 / 每改一次排序都完整重算一遍**（翻 3 页 = 1.53s）

修复：
  [1] 统一 selectinload 预加载（不用 joinedload，避免与 supplier 关键词筛选的
      join(Material.supplier) 冲突）
  [2] 回补扫描在 SQL 侧剪掉「无来源单据」的历史行——这些行在
      _ledger_source_warehouse_map 中必然被跳过，三条保留条件全为假，
      永远不可能归属任何仓库（纯剪枝、语义等价，实测 -83%）

断言：
  T1. 预加载不改变库存报表口径（分类/单位/供应商字段仍正确）。
  T2. N+1 消除：每物料不同供应商时 SQL 语句数 ≤ 20（修复前 ≈ 物料数）。
  T3. 空 location 回补：无来源单据的行不计入库存（剪枝前后一致）。
  T4. 强等价性：有来源单据且属本仓的行计入、属他仓的不串入，数值精确匹配。
  T5. 多仓隔离（R2）：库存报表 B 仓数据不串入 A 仓。
  T6. API 回归：/report/api/inventory 正常返回且不报错。
"""
from __future__ import annotations

import os
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

import app as app_module  # noqa: E402
from app import (InOrder, Material, StockTransaction, Supplier,  # noqa: E402
                 Unit, User, Warehouse, db)
from sqlalchemy import event, inspect as sa_inspect  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

D1 = date(2026, 9, 1)


def _filters(**overrides):
    base = {
        'start_date': None, 'end_date': None,
        'warehouse_id': 0, 'warehouse': '', 'warehouse_code': '',
        'business_type': '', 'material_code': '',
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc',
        'page': 1, 'page_size': 20, 'hide_zero': False, 'export': '',
    }
    base.update(overrides)
    return base


def _count_sql(fn):
    """执行 fn 并返回其触发的 SQL 语句数。"""
    stmts = []

    def _before(conn, cursor, statement, params, context, executemany):
        stmts.append(statement)

    event.listen(db.engine, "before_cursor_execute", _before)
    try:
        result = fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", _before)
    return len(stmts), result


class TestBug20260907015:
    def setup_method(self):
        # 注意：只保存原始值（int/str）。SQLAlchemy expire_on_commit=True，
        # commit 后脱离 app_context 的 ORM 实例再访问属性会触发
        # DetachedInstanceError，故不在测试方法里触碰 setup 期间的实例。
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            cat_model = sa_inspect(Material).relationships["category"].mapper.class_
            cat = cat_model(code="CAT1", name="电气")
            sup_a = Supplier(code="S1", name="供应商甲")
            sup_b = Supplier(code="S2", name="供应商乙")
            db.session.add_all([wh_a, wh_b, unit, user, cat, sup_a, sup_b])
            db.session.commit()
            self.wh_a_id = wh_a.id
            self.wh_b_id = wh_b.id
            self.unit_id = unit.id
            self.cat_id = cat.id
            self.user_id = user.id
            self.sup_id_by_name = {sup_a.name: sup_a.id, sup_b.name: sup_b.id}
            self.a_kw = dict(warehouse_id=wh_a.id, warehouse="仓库A", warehouse_code="WHA")
            self.b_kw = dict(warehouse_id=wh_b.id, warehouse="仓库B", warehouse_code="WHB")

    def _material(self, code, name, supplier_name=None, price=10.0):
        m = Material(code=code, name=name, spec="SPEC-" + code,
                     unit_id=self.unit_id, category_id=self.cat_id,
                     supplier_id=(self.sup_id_by_name.get(supplier_name)
                                  if supplier_name else None),
                     price=price, stock=0.0)
        db.session.add(m)
        db.session.flush()
        return m

    def _txn(self, material_id, qty, location, warehouse_id, ref_type=None, ref_id=None):
        db.session.add(StockTransaction(
            material_id=material_id, transaction_type='in', quantity=qty,
            location=location, warehouse_id=warehouse_id,
            reference_type=ref_type, reference_id=ref_id, operator_id=self.user_id))

    def _in_order(self, order_no, warehouse_name):
        io = InOrder(order_no=order_no, date=D1, warehouse=warehouse_name,
                     status="completed", operator_id=self.user_id)
        db.session.add(io)
        db.session.flush()
        return io

    # ------------------------------------------------------------------ T1
    def test_T1_eager_load_keeps_report_semantics(self):
        """预加载不改变库存报表口径：分类/单位/供应商字段仍正确。"""
        with app_module.app.app_context():
            m1 = self._material("M001", "电缆", "供应商甲", price=10.0)
            m2 = self._material("M002", "开关", "供应商乙", price=20.0)
            self._txn(m1.id, 5.0, '仓库A', None)
            self._txn(m2.id, 2.0, '仓库A', self.wh_a_id)
            db.session.commit()
            _, rows, summary = app_module._build_inventory_report(_filters(**self.a_kw))
            by_code = {r['code']: r for r in rows}
            assert by_code['M001']['category'] == '电气'
            assert by_code['M001']['unit'] == '个'
            assert by_code['M001']['supplier'] == '供应商甲'
            assert by_code['M002']['supplier'] == '供应商乙'
            assert by_code['M001']['stock'] == 5.0
            assert by_code['M001']['stock_value'] == 50.0
            assert by_code['M002']['stock'] == 2.0
            assert by_code['M002']['stock_value'] == 40.0
            assert summary['count'] == 2
            assert summary['quantity'] == 7.0
            assert summary['amount'] == 90.0

    # ------------------------------------------------------------------ T2
    def test_T2_no_n_plus_one_on_material_relations(self):
        """每物料不同供应商时，SQL 语句数必须 ≤ 20（修复前 ≈ 物料数 + 常数）。"""
        with app_module.app.app_context():
            n = 300
            suppliers = [Supplier(code="S%04d" % i, name="供应商%d" % i) for i in range(n)]
            db.session.add_all(suppliers)
            db.session.flush()
            sup_ids = [s.id for s in suppliers]
            mats = []
            for i in range(n):
                m = Material(code="M%05d" % i, name="物料%d" % i,
                             unit_id=self.unit_id, category_id=self.cat_id,
                             supplier_id=sup_ids[i], price=1.0, stock=0.0)
                db.session.add(m)
                db.session.flush()
                mats.append(m)
                self._txn(m.id, float(i + 1), '仓库A', None)
            db.session.commit()
            count, rows = _count_sql(
                lambda: app_module._collect_inventory_rows(_filters(**self.a_kw)))
            assert len(rows) == n, f"行数应为 {n}，实际 {len(rows)}"
            assert count <= 20, \
                f"物料关系仍存在 N+1：{n} 物料触发 {count} 条 SQL（应 ≤ 20）"

    # ------------------------------------------------------------------ T3
    def test_T3_empty_location_without_source_doc_is_ignored(self):
        """空 location 且无来源单据的历史流水不计入任何仓库库存（剪枝前后一致）。"""
        with app_module.app.app_context():
            m1 = self._material("M001", "电缆", "供应商甲")
            # 无任何来源单据 → 永远不可能归属仓库，必须被排除
            self._txn(m1.id, 777.0, None, None, None, None)
            self._txn(m1.id, 888.0, '', None, None, None)
            self._txn(m1.id, 999.0, '', None, 'in_order', None)
            # 只有这条正常归属 A 仓
            self._txn(m1.id, 4.0, '仓库A', None)
            db.session.commit()
            wh_a = Warehouse.query.get(self.wh_a_id)
            stock_map = app_module.get_warehouse_stock_quantities(wh_a)
            assert stock_map.get(m1.id) == 4.0, \
                f"无来源单据的空 location 流水不得计入库存，实际 {stock_map.get(m1.id)}"

    # ------------------------------------------------------------------ T4
    def test_T4_backfill_attribution_exact_and_no_cross_warehouse(self):
        """强等价性：有来源单据且属本仓计入、属他仓不串入，数值精确匹配。"""
        with app_module.app.app_context():
            m1 = self._material("M001", "电缆", "供应商甲")
            m2 = self._material("M002", "开关", "供应商乙")
            io_a = self._in_order("IN-A", "仓库A")
            io_b = self._in_order("IN-B", "仓库B")
            # ① 空 location + 来源单据属 A 仓 → 计入 A 仓（10 + 5）
            self._txn(m1.id, 10.0, None, None, 'in_order', io_a.id)
            self._txn(m1.id, 5.0, '', None, 'in_order', io_a.id)
            # ② 空 location + 来源单据属 B 仓 → 不得计入 A 仓
            self._txn(m1.id, 999.0, None, None, 'in_order', io_b.id)
            # ③ 空 location + 无来源单据 → 剪枝，不计入
            self._txn(m1.id, 777.0, None, None, None, None)
            self._txn(m2.id, 888.0, '', None, 'in_order', None)
            # ④ 正常归属 A 仓（location 字符串 + warehouse_id 两种写法）
            self._txn(m2.id, 3.0, '仓库A', None, 'in_order', io_a.id)
            self._txn(m2.id, 2.0, '仓库A', self.wh_a_id, 'in_order', io_a.id)
            # ⑤ 有来源单据但单据不存在 → 不计入
            self._txn(m2.id, 555.0, None, None, 'in_order', 999999)
            db.session.commit()

            wh_a = Warehouse.query.get(self.wh_a_id)
            wh_b = Warehouse.query.get(self.wh_b_id)
            map_a = app_module.get_warehouse_stock_quantities(wh_a)
            map_b = app_module.get_warehouse_stock_quantities(wh_b)
            assert map_a.get(m1.id) == 15.0, f"A 仓 M001 应为 15，实际 {map_a.get(m1.id)}"
            assert map_a.get(m2.id) == 5.0, f"A 仓 M002 应为 5，实际 {map_a.get(m2.id)}"
            assert map_b.get(m1.id) == 999.0, f"B 仓 M001 应为 999，实际 {map_b.get(m1.id)}"

    # ------------------------------------------------------------------ T5
    def test_T5_report_warehouse_isolation(self):
        """库存报表多仓隔离（R2）：B 仓数据不串入 A 仓。"""
        with app_module.app.app_context():
            m1 = self._material("M001", "电缆", "供应商甲")
            m2 = self._material("M002", "开关", "供应商乙")
            self._txn(m1.id, 5.0, '仓库A', None)
            self._txn(m2.id, 777.0, '仓库B', None)
            db.session.commit()
            _, rows_a, sum_a = app_module._build_inventory_report(_filters(**self.a_kw))
            assert sum_a['quantity'] == 5.0, f"A 仓数量应为 5，实际 {sum_a['quantity']}"
            assert all(r['stock'] != 777 for r in rows_a), "B 仓 777 串入 A 仓"
            _, _, sum_b = app_module._build_inventory_report(_filters(**self.b_kw))
            assert sum_b['quantity'] == 777.0, f"B 仓数量应为 777，实际 {sum_b['quantity']}"

            _, rows_none, sum_none = app_module._build_inventory_report(_filters())
            assert rows_none == [] and sum_none == {'count': 0, 'quantity': 0, 'amount': 0}

    # ------------------------------------------------------------------ T6
    def test_T6_api_inventory_still_works(self):
        """API 回归：/report/api/inventory 正常返回、字段完整。"""
        with app_module.app.app_context():
            m1 = self._material("M001", "电缆", "供应商甲", price=10.0)
            self._txn(m1.id, 5.0, '仓库A', None)
            db.session.commit()
            wh_a_id = self.wh_a_id
        client = app_module.app.test_client()
        client.post("/login", data={"username": "admin", "password": "admin"})
        r = client.get(f"/report/api/inventory?warehouse_id={wh_a_id}&page=1&page_size=20")
        assert r.status_code == 200
        data = r.get_json()
        assert data['status'] == 'success'
        assert data['total'] == 1
        assert data['data'][0]['stock'] == 5.0
        assert data['data'][0]['supplier'] == '供应商甲'
