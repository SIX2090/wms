#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
采购到销售全链路 20 组数据全流程测试。

链路：基础数据 → 采购订单(保存) → 采购下推入库单 → 入库完成(库存↑)
      → 销售订单(创建→修改→确认) → 生成出库草稿(外键#4) → 出库完成(库存↓+回写)
      → 验证订单状态/发货状态/金额精度(Numeric#6)/已发货数量

数据库：独立文件 instance/test_full_flow.db，不污染运行中服务。
驱动：Flask test_client + 登录 session + 禁用 CSRF。
"""

import os
import sys
import json
import shutil
import traceback
from datetime import date, timedelta

# 测试用独立 DB（与运行中服务隔离）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))          # .../scripts
REPO_DIR = os.path.dirname(BASE_DIR)                            # .../workspace
APP_DIR = os.path.join(REPO_DIR, 'app')                         # .../workspace/app
TEST_DB_PATH = os.environ.get(
    'WMS_FULL_FLOW_TEST_DB',
    os.path.join(APP_DIR, 'instance', 'test_full_flow.db'),
)

os.environ['SECRET_KEY'] = 'test-full-flow-secret'
os.environ['WMS_ALLOW_AUTO_SECRET_KEY'] = '1'
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
os.environ['WMS_DATABASE_URI'] = f'sqlite:///{TEST_DB_PATH}'

sys.path.insert(0, APP_DIR)

# 启动前清理旧测试 DB
for suffix in ('', '-shm', '-wal'):
    p = TEST_DB_PATH + suffix
    if os.path.exists(p):
        os.remove(p)

from app import (
    app, db, User, Material, MaterialCategory, Unit, Supplier, Customer,
    Warehouse, Employee, PurchaseOrder, PurchaseOrderItem, InOrder, InOrderItem,
    OutOrder, SalesOrder, SalesOrderItem, AfterSaleOutOrder, AfterSaleOutOrderItem,
    initialize_database,
)
from werkzeug.security import generate_password_hash

# 禁用 CSRF，简化 test_client POST
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True


# ========== 工具 ==========

class Result:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.records = []  # (group_id, step, ok, detail)

    def record(self, group, step, ok, detail=''):
        self.records.append((group, step, ok, detail))
        if ok:
            self.passed += 1
        else:
            self.failed += 1

    def summary(self):
        total = self.passed + self.failed
        return f"总计 {total} 步 | 通过 {self.passed} | 失败 {self.failed}"


R = Result()


def login_client():
    """登录 admin，返回带 session 的 test_client。"""
    client = app.test_client()
    resp = client.post('/login', data={'username': 'admin', 'password': 'admin'}, follow_redirects=False)
    assert resp.status_code == 302, f"登录失败 status={resp.status_code}"
    return client


def post_json(client, path, payload):
    """POST JSON 并返回 (status_code, json_body)。"""
    resp = client.post(path, data=json.dumps(payload), content_type='application/json')
    try:
        body = resp.get_json()
    except Exception:
        body = None
    return resp.status_code, body


def fresh_db():
    """初始化测试数据库 schema + bootstrap admin。"""
    with app.app_context():
        initialize_database()


def seed_master_data():
    """创建 20 组测试所需基础数据。"""
    with app.app_context():
        # 分类/单位
        cat = MaterialCategory.query.first()
        if not cat:
            cat = MaterialCategory(code='CAT01', name='测试分类')
            db.session.add(cat)
            db.session.flush()
        unit = Unit.query.first()
        if not unit:
            unit = Unit(code='PCS', name='个')
            db.session.add(unit)
            db.session.flush()
        # 仓库
        wh = Warehouse.query.filter_by(name='测试仓').first()
        if not wh:
            wh = Warehouse(code='TWH01', name='测试仓', type='成品仓', status='active')
            db.session.add(wh)
            db.session.flush()
        # 供应商
        for i in range(1, 6):
            code = f'SUP{i:03d}'
            if not Supplier.query.filter_by(code=code).first():
                db.session.add(Supplier(code=code, name=f'供应商{i}', contact=f'联系人{i}', phone=f'1380000{i:04d}'))
        # 客户
        for i in range(1, 11):
            code = f'CUS{i:03d}'
            if not Customer.query.filter_by(code=code).first():
                db.session.add(Customer(code=code, name=f'客户{i}', contact=f'联系人{i}', phone=f'1390000{i:04d}'))
        # 业务员
        for i in range(1, 4):
            if not Employee.query.filter_by(name=f'业务员{i}').first():
                db.session.add(Employee(name=f'业务员{i}', position='销售'))
        # 物料（10 种，不同单价，覆盖整数/小数/高单价）
        materials_spec = [
            ('M001', '轴承6204', 25.00),
            ('M002', '螺栓M8', 0.50),
            ('M003', '电机3kW', 850.00),
            ('M004', '密封圈', 2.50),
            ('M005', '电阻1K', 0.10),
            ('M006', '电容100uF', 0.15),
            ('M007', '钢板1m²', 120.00),
            ('M008', '导线1m', 1.20),
            ('M009', '芯片X1', 99.99),
            ('M010', '外壳A', 15.50),
        ]
        for code, name, price in materials_spec:
            if not Material.query.filter_by(code=code).first():
                db.session.add(Material(
                    code=code, name=name, spec=name, category_id=cat.id, unit_id=unit.id,
                    stock=0, price=price, min_stock=10,
                ))
        db.session.commit()


# ========== 20 组测试数据定义 ==========
# 每组: {purchase_items, sales_items, tax_rates, project_no, partial, currency, settlement, batch, expect_qty}
# purchase_items: [(material_code, qty, price), ...]
# sales_items:    [(material_code, qty, price, tax_rate), ...]
# partial: None=全发, 数量=部分发货数量（覆盖部分发货场景）

TEST_GROUPS = [
    # 1. 单明细标准 13% 税率
    {'purchase': [('M001', 100, 25.00)], 'sales': [('M001', 50, 28.00, 0.13)], 'project': 'P001', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None},
    # 2. 多明细混合税率
    {'purchase': [('M001', 200, 25.00), ('M002', 1000, 0.50)], 'sales': [('M001', 80, 28.00, 0.13), ('M002', 400, 0.80, 0.09)], 'project': 'P002', 'currency': 'CNY', 'settlement': '现结', 'partial': None},
    # 3. 零税率
    {'purchase': [('M003', 10, 850.00)], 'sales': [('M003', 5, 920.00, 0.00)], 'project': None, 'currency': 'CNY', 'settlement': None, 'partial': None},
    # 4. 6% 税率
    {'purchase': [('M005', 5000, 0.10)], 'sales': [('M005', 2000, 0.15, 0.06)], 'project': 'P004', 'currency': 'CNY', 'settlement': '月结60天', 'partial': None},
    # 5. 部分发货（发一半）
    {'purchase': [('M004', 500, 2.50)], 'sales': [('M004', 300, 3.50, 0.13)], 'project': 'P005', 'currency': 'CNY', 'settlement': '现结', 'partial': 150},
    # 6. 大批量低单价
    {'purchase': [('M005', 50000, 0.10), ('M006', 30000, 0.15)], 'sales': [('M005', 20000, 0.13, 0.06), ('M006', 10000, 0.18, 0.06)], 'project': 'P006', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None},
    # 7. 高单价小批量
    {'purchase': [('M003', 5, 850.00)], 'sales': [('M003', 3, 920.00, 0.13)], 'project': 'P007', 'currency': 'USD', 'settlement': 'L/C', 'partial': None},
    # 8. 含批次号和序列号
    {'purchase': [('M007', 50, 120.00)], 'sales': [('M007', 20, 138.00, 0.13)], 'project': 'P008', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None, 'batch': 'B202607', 'serial': 'S001'},
    # 9. 多明细单客户
    {'purchase': [('M001', 100, 25.00), ('M002', 500, 0.50), ('M004', 300, 2.50)], 'sales': [('M001', 40, 28.00, 0.13), ('M002', 200, 0.80, 0.09), ('M004', 100, 3.50, 0.13)], 'project': 'P009', 'currency': 'CNY', 'settlement': '现结', 'partial': None},
    # 10. 整数价格无小数
    {'purchase': [('M008', 1000, 1.00)], 'sales': [('M008', 600, 2.00, 0.13)], 'project': None, 'currency': 'CNY', 'settlement': None, 'partial': None},
    # 11. 小数价格精度
    {'purchase': [('M009', 100, 99.99)], 'sales': [('M009', 50, 109.99, 0.13)], 'project': 'P011', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None},
    # 12. 含外币
    {'purchase': [('M010', 200, 15.50)], 'sales': [('M010', 100, 18.00, 0.13)], 'project': 'P012', 'currency': 'USD', 'settlement': 'T/T', 'partial': None},
    # 13. 全部发货后无剩余
    {'purchase': [('M001', 30, 25.00)], 'sales': [('M001', 30, 28.00, 0.13)], 'project': 'P013', 'currency': 'CNY', 'settlement': '现结', 'partial': None},
    # 14. 部分发货后部分
    {'purchase': [('M002', 800, 0.50)], 'sales': [('M002', 500, 0.80, 0.09)], 'project': 'P014', 'currency': 'CNY', 'settlement': '月结30天', 'partial': 200},
    # 15. 多物料大批量
    {'purchase': [('M001', 500, 25.00), ('M004', 2000, 2.50), ('M008', 5000, 1.20)], 'sales': [('M001', 200, 28.00, 0.13), ('M004', 800, 3.50, 0.13), ('M008', 2000, 1.80, 0.13)], 'project': 'P015', 'currency': 'CNY', 'settlement': '月结60天', 'partial': None},
    # 16. 单明细低税率
    {'purchase': [('M006', 10000, 0.15)], 'sales': [('M006', 5000, 0.20, 0.06)], 'project': 'P016', 'currency': 'CNY', 'settlement': '现结', 'partial': None},
    # 17. 含项目号无结算
    {'purchase': [('M007', 100, 120.00)], 'sales': [('M007', 50, 138.00, 0.13)], 'project': 'PROJ-2026-001', 'currency': 'CNY', 'settlement': None, 'partial': None},
    # 18. 大额订单金额精度验证
    {'purchase': [('M003', 100, 850.00)], 'sales': [('M003', 50, 920.00, 0.13)], 'project': 'P018', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None},
    # 19. 混合税率多明细部分发货
    {'purchase': [('M001', 300, 25.00), ('M003', 20, 850.00), ('M005', 8000, 0.10)], 'sales': [('M001', 100, 28.00, 0.13), ('M003', 10, 920.00, 0.13), ('M005', 3000, 0.15, 0.06)], 'project': 'P019', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None},
    # 20. 完整字段含备注
    {'purchase': [('M010', 300, 15.50), ('M009', 50, 99.99)], 'sales': [('M010', 150, 18.00, 0.13), ('M009', 25, 109.99, 0.13)], 'project': 'P020-FINAL', 'currency': 'CNY', 'settlement': '月结30天', 'partial': None, 'remark': '月度补货订单'},
]


def run_group(client, idx, g):
    """运行单组全流程测试。"""
    gid = f"G{idx:02d}"
    with app.app_context():
        supplier = Supplier.query.first()
        customer = Customer.query.offset((idx - 1) % 10).first()
        employee = Employee.query.first()
        wh = Warehouse.query.filter_by(name='测试仓').first()

        # ===== 步骤1: 采购订单保存 =====
        po_items = [{'material_code': mc, 'quantity': qty, 'price': pr} for mc, qty, pr in g['purchase']]
        code, body = post_json(client, '/purchase_order/save', {
            'supplier_id': supplier.id,
            'date': date.today().isoformat(),
            'expected_date': (date.today() + timedelta(days=7)).isoformat(),
            'remark': f'{gid} 采购',
            'items': po_items,
        })
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '1.采购订单保存', ok, f"code={code} body={body}")
        if not ok:
            return
        po_id = body['id']

        # ===== 步骤2: 采购下推入库单 =====
        po = PurchaseOrder.query.get(po_id)
        submit_items = [{'item_id': item.id, 'quantity': item.quantity} for item in po.items]
        code, body = post_json(client, f'/purchase_order/{po_id}/create_in_order', {
            'warehouse': wh.name,
            'remark': f'{gid} 入库',
            'items': submit_items,
        })
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '2.采购下推入库单', ok, f"code={code} body={body}")
        if not ok:
            return
        in_order_id = body['id']

        # ===== 步骤3: 入库完成（库存↑）=====
        # 先查异常（force 跳过）
        code, body = post_json(client, f'/in_order/{in_order_id}/complete?force=true', {})
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '3.入库完成', ok, f"code={code} body={body}")
        if not ok:
            return

        # 验证库存增加
        stock_ok = True
        stock_detail = []
        for mc, qty, _ in g['purchase']:
            m = Material.query.filter_by(code=mc).first()
            if m.stock < qty:
                stock_ok = False
            stock_detail.append(f"{mc}={m.stock}")
        R.record(gid, '3.1库存增加校验', stock_ok, ' | '.join(stock_detail))

        # ===== 步骤4: 销售订单创建 =====
        sales_items = []
        for entry in g['sales']:
            mc, qty, pr, tr = entry
            item = {'code': mc, 'quantity': qty, 'price': pr, 'tax_rate': tr}
            if g.get('batch'):
                item['batch_no'] = g['batch']
            if g.get('serial'):
                item['serial_no'] = g['serial']
            if g.get('remark'):
                item['remark'] = g['remark']
            sales_items.append(item)
        code, body = post_json(client, '/sales/add', {
            'customer_id': customer.id,
            'date': date.today().isoformat(),
            'delivery_date': (date.today() + timedelta(days=5)).isoformat(),
            'warehouse': wh.name,
            'salesperson_id': employee.id,
            'project_no': g.get('project'),
            'currency': g.get('currency', 'CNY'),
            'settlement_method': g.get('settlement'),
            'remark': f'{gid} 销售',
            'items': sales_items,
        })
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '4.销售订单创建', ok, f"code={code} body={body}")
        if not ok:
            return
        so_id = body['id']

        # ===== 步骤5: 销售订单修改（验证 #1，改备注）=====
        code, body = post_json(client, f'/sales/{so_id}/edit', {
            'customer_id': customer.id,
            'date': date.today().isoformat(),
            'warehouse': wh.name,
            'salesperson_id': employee.id,
            'project_no': g.get('project'),
            'currency': g.get('currency', 'CNY'),
            'settlement_method': g.get('settlement'),
            'remark': f'{gid} 销售已修改',
            'items': sales_items,
        })
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '5.销售订单修改(#1)', ok, f"code={code} body={body}")
        if not ok:
            return
        # 验证备注已更新
        so = SalesOrder.query.get(so_id)
        R.record(gid, '5.1备注已更新', so.remark == f'{gid} 销售已修改', f"remark={so.remark}")

        # ===== 步骤6: 销售订单确认 =====
        code, body = post_json(client, f'/sales/{so_id}/confirm', {})
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '6.销售订单确认', ok, f"code={code} body={body}")
        if not ok:
            return
        so = SalesOrder.query.get(so_id)
        R.record(gid, '6.1状态=confirmed', so.status == 'confirmed', f"status={so.status}")

        # ===== 步骤7: 生成出库草稿（验证 #4 外键）=====
        code, body = post_json(client, f'/sales/{so_id}/create_outbound', {})
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '7.生成出库草稿', ok, f"code={code} body={body}")
        if not ok:
            return
        out_order_id = body['id']

        # 验证外键关联（#4）
        oo = OutOrder.query.get(out_order_id)
        R.record(gid, '7.1外键source_sales_order_id(#4)', oo.source_sales_order_id == so_id, f"fk={oo.source_sales_order_id} expected={so_id}")

        # ===== 步骤8: 出库完成（库存↓ + 回写 shipped_quantity）=====
        if g.get('partial'):
            # 部分发货：修改出库单明细数量为 partial 值
            for item in oo.items:
                item.quantity = g['partial']
                item.amount = round((item.quantity or 0) * (item.price or 0), 2)
            oo.total_amount = round(sum((item.amount or 0) for item in oo.items), 2)
            db.session.commit()

        code, body = post_json(client, f'/out_order/{out_order_id}/complete?force=true', {})
        ok = code == 200 and body and body.get('status') == 'success'
        R.record(gid, '8.出库完成', ok, f"code={code} body={body}")
        if not ok:
            return

        # ===== 步骤9: 验证销售订单状态回写 =====
        db.session.expire_all()
        so = SalesOrder.query.get(so_id)
        if g.get('partial'):
            # 部分发货：shipment_status=partial, status 仍 confirmed
            ship_ok = so.shipment_status == 'partial'
            R.record(gid, '9.部分发货shipment=partial', ship_ok, f"shipment_status={so.shipment_status}")
            # 验证 shipped_quantity
            shipped_qty = sum(i.shipped_quantity or 0 for i in so.items)
            R.record(gid, '9.1已发数量=partial', shipped_qty == g['partial'], f"shipped={shipped_qty} expected={g['partial']}")
        else:
            # 全发：shipment_status=shipped, status=closed
            ship_ok = so.shipment_status == 'shipped'
            R.record(gid, '9.全发shipment=shipped', ship_ok, f"shipment_status={so.shipment_status}")
            status_ok = so.status == 'closed'
            R.record(gid, '9.1全发status=closed', status_ok, f"status={so.status}")
            # 验证 shipped_quantity 等于订单数量
            for i, entry in enumerate(g['sales']):
                mc, qty, _, _ = entry
                si = next((x for x in so.items if x.material.code == mc), None)
                if si:
                    R.record(gid, f'9.2已发数量[{mc}]', (si.shipped_quantity or 0) == qty, f"shipped={si.shipped_quantity} expected={qty}")

        # ===== 步骤10: 金额精度验证（#6 Numeric）=====
        so = SalesOrder.query.get(so_id)
        # 验证字段类型为 Decimal（Numeric）
        from decimal import Decimal
        amt_ok = isinstance(so.total_amount, Decimal) and isinstance(so.untaxed_amount, Decimal) and isinstance(so.tax_amount, Decimal)
        R.record(gid, '10.金额字段为Decimal(#6)', amt_ok, f"total={so.total_amount} type={type(so.total_amount).__name__}")

        # 验证金额计算正确性：untaxed + tax ≈ total
        calc_ok = abs(float(so.untaxed_amount or 0) + float(so.tax_amount or 0) - float(so.total_amount or 0)) < 0.01
        R.record(gid, '10.1金额等式校验', calc_ok, f"untaxed={so.untaxed_amount} tax={so.tax_amount} total={so.total_amount}")

        # 验证明细金额
        for entry in g['sales']:
            mc, qty, pr, tr = entry
            si = next((x for x in so.items if x.material.code == mc), None)
            if si:
                exp_total = round(qty * pr, 2)
                got_total = float(si.tax_included_amount or si.amount or 0)
                R.record(gid, f'10.2明细金额[{mc}]', abs(got_total - exp_total) < 0.01, f"got={got_total} exp={exp_total}")


def main():
    print("=" * 70)
    print("采购到销售全链路 20 组数据全流程测试")
    print(f"测试 DB: {TEST_DB_PATH}")
    print("=" * 70, flush=True)

    # 初始化
    fresh_db()
    seed_master_data()
    print("[INIT] 基础数据已就绪", flush=True)

    client = login_client()
    print("[INIT] 登录成功 admin/admin", flush=True)

    # 运行 20 组
    for i, g in enumerate(TEST_GROUPS, 1):
        print(f"\n----- 第 {i:02d} 组 -----", flush=True)
        try:
            run_group(client, i, g)
        except Exception as e:
            R.record(f"G{i:02d}", 'EXCEPTION', False, f"{e}\n{traceback.format_exc()}")
            print(f"[G{i:02d}] 异常: {e}", flush=True)

    # 输出报告
    print("\n" + "=" * 70)
    print("测试报告")
    print("=" * 70)
    print(R.summary())
    print("-" * 70)
    # 失败项明细
    failures = [r for r in R.records if not r[2]]
    if failures:
        print(f"\n失败项明细（{len(failures)} 项）:")
        for gid, step, ok, detail in failures:
            print(f"  [{gid}] {step}")
            print(f"    -> {detail[:200]}")
    else:
        print("\n全部通过，无失败项。")

    # 各组通过情况
    print("-" * 70)
    print("各组通过步数:")
    group_stats = {}
    for gid, step, ok, _ in R.records:
        group_stats.setdefault(gid, [0, 0])
        if ok:
            group_stats[gid][0] += 1
        else:
            group_stats[gid][1] += 1
    for gid in sorted(group_stats.keys()):
        p, f = group_stats[gid]
        mark = '✓' if f == 0 else '✗'
        print(f"  {mark} {gid}: 通过 {p} / 失败 {f}")

    return 0 if R.failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
