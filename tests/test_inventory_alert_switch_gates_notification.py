# -*- coding: utf-8 -*-
"""AI-CI-GREEN-005-F02 回归：库存预警总开关必须同时管住「通知」。

背景：`inventory_alert_enabled` 是库存预警的总开关。列表与页面侧的判定统一走
`_material_low_stock_filter()`，它内部含 `inventory_alert_enabled()` 判断；但定时
任务 `NotificationManager.check_low_stock()` 是直接查 `stock <= min_stock`，
**没有开关判断**。结果开关关着时页面写「库存预警未启用」，APScheduler 却每天
9:00 照发站内通知 + 邮件 —— 同一个系统给出自相矛盾的答案。

断言：
  T1. 开关关闭（'0'）：check_low_stock 返回空，且不落任何 low_stock 通知。
  T2. 开关开启（'1'）：同一条低库存物料会产生 1 条 low_stock 通知。
  T3. 开关由开启切回关闭：不再新增通知（证明开关是真闸门而非只影响首轮）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import date, timedelta

import pytest

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
from app import Material, User, db  # noqa: E402
from notifications import NotificationManager  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset(alert_enabled: str):
    """重建内存库，并按要求设置总开关。"""
    from werkzeug.security import generate_password_hash

    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        ))
        # stock=2 < min_stock=10 → 稳定命中"低库存"
        db.session.add(Material(code="ALERT-SW-1", name="开关闸门口测试物料",
                                spec="SW", min_stock=10, stock=2))
        db.session.commit()
        app_module.set_system_setting("inventory_alert_enabled", alert_enabled)
        db.session.commit()


def _low_stock_notification_count():
    from app import Notification
    with app_module.app.app_context():
        return Notification.query.filter_by(type="low_stock").count()


def test_t1_switch_off_sends_no_notification():
    """T1：开关关闭时，定时任务不得发出任何库存预警通知。"""
    _reset("0")
    with app_module.app.app_context():
        result = NotificationManager().check_low_stock(db, Material, User)

    assert result == [], f"开关关闭时不应产生通知，实际 {len(result)} 条"
    assert _low_stock_notification_count() == 0, (
        "开关关闭时数据库不应出现 low_stock 通知"
    )


def test_expiry_notifications_use_material_window_and_deduplicate():
    _reset("1")
    with app_module.app.app_context():
        examples = [('LONG', 45, 60), ('SHORT', 20, 7), ('EDGE', 7, 7),
                    ('TODAY', 0, 7), ('PAST', -1, 60), ('DEFAULT', 30, 30)]
        materials = {code: Material(code=code, name=code, alert_days=window,
                                    expiry_date=date.today() + timedelta(days=days))
                     for code, days, window in examples}
        db.session.add_all(materials.values())
        db.session.flush()
        materials['DEFAULT'].alert_days = None
        db.session.commit()
        manager = NotificationManager()
        alerts = manager.check_expiring_materials(db, Material, User)
        assert {n.target_id for n in alerts} == {
            materials[key].id for key in ('LONG', 'EDGE', 'TODAY', 'DEFAULT')}
        assert manager.check_expiring_materials(db, Material, User) == []


def test_t2_switch_on_sends_notification():
    """T2：开关开启时，低库存物料应产生 1 条通知（保证 T1 不是"永远不发"）。"""
    _reset("1")
    with app_module.app.app_context():
        result = NotificationManager().check_low_stock(db, Material, User)

    assert len(result) == 1, f"开关开启应产生 1 条通知，实际 {len(result)} 条"
    assert _low_stock_notification_count() == 1


def test_t3_switch_flipped_back_off_stops_notifications():
    """T3：开关从开启切回关闭后，不再新增通知（去重逻辑之外的真闸门）。"""
    _reset("1")
    with app_module.app.app_context():
        NotificationManager().check_low_stock(db, Material, User)
    assert _low_stock_notification_count() == 1

    # 关掉开关：即使"今天已发过"的去重被绕过（换一天/清库），也必须不发
    with app_module.app.app_context():
        app_module.set_system_setting("inventory_alert_enabled", "0")
        db.session.commit()
        result = NotificationManager().check_low_stock(db, Material, User)

    assert result == [], "开关切回关闭后仍发出了通知"
    assert _low_stock_notification_count() == 1, (
        "开关关闭后通知数不应增长"
    )


def test_check_inventory_ledgers():
    from app import LocationInventory, Notification, StockTransaction, Warehouse
    _reset("0")
    with app_module.app.app_context():
        m = Material.query.one()
        wh = Warehouse(code="AUD", name="核对仓", status="active")
        db.session.add(wh)
        db.session.flush()
        db.session.add_all([
            StockTransaction(material_id=m.id, transaction_type="in", quantity=2, warehouse_id=wh.id),
            StockTransaction(material_id=m.id, transaction_type="in", quantity=1),
            LocationInventory(material_id=m.id, warehouse_id=wh.id, location="A", quantity=1),
        ])
        db.session.commit()
        manager = NotificationManager()
        manager.check_inventory_ledgers()
        notice = Notification.query.filter_by(type="inventory_reconciliation").one()
        assert "总账与流水差异 1" in notice.content and "库位核对关闭" in notice.content
        assert "仓库外键为空的流水 1" in notice.content and m.code in notice.content
        app_module.set_system_setting("location_management_enabled", "1")
        db.session.commit()
        manager.check_inventory_ledgers()
        notice = Notification.query.filter_by(type="inventory_reconciliation").one()
        assert "仓库分布差异 1" in notice.content and "总账与库位差异 1" in notice.content
        assert m.stock == 2 and StockTransaction.query.count() == 2
        client = app_module.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = str(User.query.one().id)
        page = client.get("/report/view/warehouse_monthly")
        assert page.status_code == 200 and notice.content in page.get_data(as_text=True)


def test_inventory_reconciliation_summary():
    from services.warehouse_stock_service import inventory_reconciliation_summary
    _reset("0")
    with app_module.app.app_context():
        Material.query.one().stock = 0
        db.session.flush()
        title, content = inventory_reconciliation_summary()
        assert "数量相符" in title and "总账与流水差异 0" in content
        assert "仓库外键为空的流水 0" in content


@pytest.mark.parametrize('kind, quantity, attribution', [
    ('in_order', 10, 'wrong'),
    ('out_order', -10, 'wrong'),
    ('in_order', 0.01, 'wrong'),
    ('in_order', 10, 'correct'),
    ('in_order', 10, 'unassigned'),
])
def test__warehouse_source_ledger_differences(kind, quantity, attribution):
    from app import InOrder, OutOrder, StockTransaction, Warehouse
    from services.warehouse_stock_service import inventory_reconciliation_summary

    _reset('0')
    with app_module.app.app_context():
        app_module.set_system_setting('location_management_enabled', '0')
        material = Material.query.one()
        first = Warehouse(code='SRC-A', name='来源仓', status='active')
        second = Warehouse(code='SRC-B', name='其他仓', status='active')
        db.session.add_all([first, second])
        db.session.flush()
        model = InOrder if kind == 'in_order' else OutOrder
        order = model(order_no='SOURCE-ONE', warehouse=first.code, status='completed')
        db.session.add(order)
        db.session.flush()
        # A previous receipt in the other warehouse has already been reversed.
        active_warehouse_id = {'wrong': second.id, 'correct': first.id, 'unassigned': None}[attribution]
        for change, warehouse_id in [(5, second.id), (-5, second.id), (quantity, active_warehouse_id)]:
            db.session.add(StockTransaction(material_id=material.id, transaction_type='in', quantity=change,
                                            warehouse_id=warehouse_id, reference_type=kind, reference_id=order.id))
        material.stock = quantity
        db.session.commit()

        title, content = inventory_reconciliation_summary()

        assert '总账与流水差异 0' in content and '库位核对关闭' in content
        assert StockTransaction.query.count() == 3
        if attribution == 'unassigned':
            assert '仓库归属待核' in title
            assert '仓库外键为空的流水 1 条' in content
        elif attribution == 'wrong':
            assert '发现差异' in title
            assert '流水与来源单据仓库不一致 1 组' in content
            assert f'流水仓库ID {second.id}' in content and f'单据仓库ID {first.id}' in content
        else:
            assert '数量相符' in title
            assert '流水与来源单据仓库不一致 0 组' in content
