# -*- coding: utf-8 -*-
"""Run 10 isolated WMS end-to-end groups with 10 transparent test users.

The database is instance/test_full_flow_10users.db and is never the live service DB.
Each group covers purchase -> receipt -> stock -> sales -> shipment -> order write-back.
An after-sales outbound draft is added with source links for reconciliation; it is not
completed and therefore does not change inventory.
"""

import importlib.util
import os
import sys
from datetime import date

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)
FLOW_PATH = os.path.join(SCRIPT_DIR, 'verify_full_flow_20groups.py')
TEST_PASSWORD = 'WmsTest123!'
APP_DIR = os.path.join(REPO_DIR, 'app')
os.environ['WMS_FULL_FLOW_TEST_DB'] = os.path.join(APP_DIR, 'instance', 'test_full_flow_10users.db')

spec = importlib.util.spec_from_file_location('wms_flow_20', FLOW_PATH)
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)

from werkzeug.security import generate_password_hash

app = flow.app
db = flow.db
User = flow.User
AfterSaleOutOrder = flow.AfterSaleOutOrder
AfterSaleOutOrderItem = flow.AfterSaleOutOrderItem
Material = flow.Material
SalesOrder = flow.SalesOrder
OutOrder = flow.OutOrder


def seed_test_users():
    users = [
        ('wms_admin_01', 'admin'),
        ('wms_purchase_01', 'purchase'),
        ('wms_purchase_02', 'purchase'),
        ('wms_sales_01', 'sales'),
        ('wms_sales_02', 'sales'),
        ('wms_sales_03', 'sales'),
        ('wms_warehouse_01', 'warehouse'),
        ('wms_warehouse_02', 'warehouse'),
        ('wms_warehouse_03', 'warehouse'),
        ('wms_viewer_01', 'user'),
    ]
    with app.app_context():
        for username, role in users:
            user = User.query.filter_by(username=username).first()
            if not user:
                user = User(username=username, role=role, status='normal',
                            password_hash=generate_password_hash(TEST_PASSWORD))
                db.session.add(user)
        db.session.commit()
        return {username: User.query.filter_by(username=username).first()
                for username, _ in users}


def login_user(username):
    client = app.test_client()
    response = client.post('/login', data={'username': username, 'password': TEST_PASSWORD},
                           follow_redirects=False)
    if response.status_code != 302:
        raise RuntimeError(f'登录测试账号失败: {username}, HTTP {response.status_code}')
    return client


def create_after_sale_draft(operator_id, group_no):
    with app.app_context():
        order = SalesOrder.query.order_by(SalesOrder.id.desc()).first()
        if not order:
            raise RuntimeError(f'G{group_no:02d} 未生成销售订单，前置全流程失败')
        outbound = OutOrder.query.filter_by(source_sales_order_id=order.id).order_by(OutOrder.id.desc()).first()
        material_code = flow.TEST_GROUPS[group_no - 1]['sales'][0][0]
        material = Material.query.filter_by(code=material_code).first()
        after_sale = AfterSaleOutOrder(
            order_no=f'ASO-TEST-{group_no:02d}', date=date.today(),
            customer=order.customer.name if order.customer else '测试客户',
            reason=f'G{group_no:02d} 售后测试草稿',
            source_sales_order_id=order.id,
            source_out_order_id=outbound.id if outbound else None,
            responsibility='测试责任人', customer_feedback='待业务确认',
            status='pending', operator_id=operator_id,
            total_amount=round(material.price or 0, 2),
        )
        db.session.add(after_sale)
        db.session.flush()
        db.session.add(AfterSaleOutOrderItem(
            after_sale_out_order_id=after_sale.id, material_id=material.id,
            quantity=1, price=material.price or 0,
            amount=round(material.price or 0, 2), remark='隔离测试草稿',
        ))
        db.session.commit()


def main():
    flow.fresh_db()
    flow.seed_master_data()
    users = seed_test_users()
    clients = {}
    for user in users.values():
        clients.setdefault(user.role, login_user(user.username))
    # The existing deterministic flow uses the admin client for document creation;
    # role clients are validated separately below to keep Flask test contexts isolated.
    routed_client = clients['admin']

    for index, group in enumerate(flow.TEST_GROUPS[:10], 1):
        flow.run_group(routed_client, index, group)
        with app.app_context():
            latest_order = SalesOrder.query.order_by(SalesOrder.id.desc()).first()
        if flow.R.failed and not latest_order:
            print('首组失败记录:')
            for record in flow.R.records:
                if not record[2]:
                    print(record)
            return 1
        warehouse_user = next(user for user in users.values() if user.role == 'warehouse')
        create_after_sale_draft(warehouse_user.id, index)

    with app.app_context():
        user_count = User.query.filter(User.username.like('wms_%')).count()
        after_sale_count = AfterSaleOutOrder.query.count()
        linked_count = AfterSaleOutOrder.query.filter(
            AfterSaleOutOrder.source_sales_order_id.isnot(None),
            AfterSaleOutOrder.source_out_order_id.isnot(None),
        ).count()
        completed_after_sales = AfterSaleOutOrder.query.filter_by(status='completed').count()
        print(f'测试用户数: {user_count}（期望 10）')
        print(f'售后草稿数: {after_sale_count}（期望 10）')
        print(f'售后双来源关联数: {linked_count}（期望 10）')
        print(f'已完成售后单: {completed_after_sales}（期望 0，避免测试扣库存）')
        checks = [user_count == 10, after_sale_count == 10,
                  linked_count == 10, completed_after_sales == 0]

    role_checks = [
        ('viewer POST 销售订单被拒绝', clients['user'].post('/sales/add', json={}).status_code in (302, 403)),
        ('sales POST 销售出库完成被拒绝', clients['sales'].post('/out_order/999999/complete', json={}).status_code in (302, 403, 404)),
        ('warehouse 可访问销售异常页', clients['warehouse'].get('/sales/exceptions').status_code == 200),
        ('purchase 可访问销售报表', clients['purchase'].get('/sales/report').status_code == 200),
    ]
    for name, ok in role_checks:
        print(('PASS ' if ok else 'FAIL ') + name)
    checks.extend(ok for _, ok in role_checks)
    if flow.R.failed or not all(checks):
        print(f'全流程失败项: {flow.R.failed}')
        return 1
    print(f'全流程业务步骤: {flow.R.summary()}')
    print('10 用户、10 组数据、售后来源草稿和角色边界全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
