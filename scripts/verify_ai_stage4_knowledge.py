from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage4-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.knowledge import is_knowledge_question, search_knowledge_entries
from ai.tools.registry import AI_TOOL_REGISTRY


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    assert 'knowledge_base' in wms_app.AI_CAPABILITY_ROLES
    assert 'knowledge_base' in AI_TOOL_REGISTRY
    assert AI_TOOL_REGISTRY['knowledge_base'].risk_level == 'read'
    assert search_knowledge_entries('采购入库SOP')
    assert is_knowledge_question('采购入库SOP怎么操作')

    with app.app_context():
        wms_app.db.create_all()
        username = 'stage4-verifier-admin'
        wms_app.User.query.filter_by(username=username).delete()
        setting = wms_app.SystemSetting.query.filter_by(key='inventory_alert_enabled').first()
        if setting:
            setting.value = '1'
        else:
            wms_app.db.session.add(wms_app.SystemSetting(key='inventory_alert_enabled', value='1'))
        for code in ('STAGE4-A', 'STAGE4-B'):
            material = wms_app.Material.query.filter_by(code=code).first()
            if material:
                wms_app.StockTransaction.query.filter_by(material_id=material.id).delete()
                wms_app.PurchaseOrderItem.query.filter_by(material_id=material.id).delete()
                wms_app.InventoryCheckItem.query.filter_by(material_id=material.id).delete()
                wms_app.db.session.delete(material)
        wms_app.PurchaseOrder.query.filter_by(order_no='PO-STAGE4').delete()
        wms_app.InventoryCheck.query.filter_by(check_no='CHK-STAGE4').delete()
        wms_app.Supplier.query.filter_by(code='SUP-STAGE4').delete()
        wms_app.db.session.commit()
        user = wms_app.User(
            username=username,
            password_hash='not-used',
            role='admin',
            status='normal',
        )
        wms_app.db.session.add(user)
        supplier = wms_app.Supplier(code='SUP-STAGE4', name='Stage4 Supplier')
        unit = wms_app.Unit.query.first() or wms_app.Unit(code='PCS', name='PCS')
        wms_app.db.session.add(supplier)
        wms_app.db.session.add(unit)
        wms_app.db.session.flush()
        material_a = wms_app.Material(
            code='STAGE4-A',
            name='Stage4 Fast',
            unit_id=unit.id,
            supplier_id=supplier.id,
            stock=20,
            min_stock=30,
            max_stock=100,
            price=5,
        )
        material_b = wms_app.Material(
            code='STAGE4-B',
            name='Stage4 Slow',
            unit_id=unit.id,
            supplier_id=supplier.id,
            stock=80,
            min_stock=10,
            max_stock=100,
            price=3,
        )
        wms_app.db.session.add_all([material_a, material_b])
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.StockTransaction(
            material_id=material_a.id,
            transaction_type='out',
            quantity=-30,
            created_at=wms_app.datetime.now() - wms_app.timedelta(days=5),
            remark='stage4 verify consumption',
        ))
        purchase_order = wms_app.PurchaseOrder(
            order_no='PO-STAGE4',
            date=wms_app.date.today() - wms_app.timedelta(days=20),
            supplier_id=supplier.id,
            expected_date=wms_app.date.today() - wms_app.timedelta(days=3),
            status='pending',
            total_amount=100,
        )
        wms_app.db.session.add(purchase_order)
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.PurchaseOrderItem(
            purchase_order_id=purchase_order.id,
            material_id=material_a.id,
            quantity=50,
            received_quantity=10,
            price=2,
            amount=100,
        ))
        check = wms_app.InventoryCheck(
            check_no='CHK-STAGE4',
            date=wms_app.date.today(),
            status='completed',
            operator_id=user.id,
        )
        wms_app.db.session.add(check)
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.InventoryCheckItem(
            inventory_check_id=check.id,
            material_id=material_a.id,
            system_stock=20,
            actual_stock=15,
            difference=-5,
            reason='verify variance',
        ))
        wms_app.db.session.commit()
        user_id = user.id

    client = app.test_client()
    _login(client, user_id)

    knowledge = client.post(
        '/api/ai/warehouse_assistant',
        json={'message': '采购入库SOP怎么操作', 'request_id': 'stage4-knowledge-sop'},
    )
    assert knowledge.status_code == 200
    knowledge_data = knowledge.get_json()
    assert knowledge_data['status'] == 'success'
    knowledge_reply = knowledge_data['reply']
    assert 'WMS知识库命中' in knowledge_reply
    assert '数据来源：AI知识库' in knowledge_reply
    assert '查询时间：' in knowledge_reply
    assert '查询范围：' in knowledge_reply
    assert any(action.get('url') for action in knowledge_data.get('actions', []))

    master_data = client.post(
        '/api/ai/warehouse_assistant',
        json={'message': '基础资料AI体检', 'request_id': 'stage4-master-data-health'},
    )
    assert master_data.status_code == 200
    master_data_data = master_data.get_json()
    assert master_data_data['status'] == 'success'
    master_reply = master_data_data['reply']
    assert '质量评分' in master_reply
    assert '数据来源：实时数据库查询' in master_reply
    assert '查询时间：' in master_reply
    assert '查询范围：' in master_reply

    deep = client.post(
        '/api/ai/warehouse_assistant',
        json={'message': 'stage4 deep analysis supply_days slow_moving shortage stocktake_variance', 'request_id': 'stage4-deep-inventory'},
    )
    assert deep.status_code == 200
    deep_data = deep.get_json()
    assert deep_data['status'] == 'success'
    deep_reply = deep_data['reply']
    assert '\u9884\u8ba1\u53ef\u7528\u5929\u6570\u5206\u6790' in deep_reply
    assert '\u6ede\u9500/\u5446\u6ede\u5e93\u5b58\u5206\u6790' in deep_reply
    assert '\u7f3a\u6599/\u8865\u8d27\u7f3a\u53e3\u5206\u6790' in deep_reply
    assert '\u76d8\u70b9\u5dee\u5f02\u5206\u6790' in deep_reply
    assert '数据来源：实时数据库查询' in deep_reply
    assert '查询时间：' in deep_reply
    assert '查询范围：' in deep_reply

    supplier = client.post(
        '/api/ai/warehouse_assistant',
        json={'message': 'supplier_performance', 'request_id': 'stage4-supplier-performance'},
    )
    assert supplier.status_code == 200
    supplier_data = supplier.get_json()
    assert supplier_data['status'] == 'success'
    supplier_reply = supplier_data['reply']
    assert '\u4f9b\u5e94\u5546\u5c65\u7ea6\u5206\u6790' in supplier_reply
    assert 'Stage4 Supplier' in supplier_reply
    assert '数据来源：实时数据库查询' in supplier_reply

    print('PASS AI-STAGE4-KNOWLEDGE: knowledge grounding, source annotations, and master-data scoring are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
