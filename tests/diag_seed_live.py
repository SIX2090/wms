# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：在真实服务库 app/instance/inventory.db 造一条完成入库单，供下推实测。"""
import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app import (Department, InOrder, InOrderItem, Material, Unit, Warehouse, User, db)  # noqa: E402
import app as app_module  # noqa: E402

with app_module.app.app_context():
    # 若已有完成入库单则跳过
    if InOrder.query.first() is None:
        unit = Unit(code="U1", name="个")
        wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        dept = Department(code="D001", name="生产部", status="active")
        mats = [Material(code=f"M{i:03d}", name=f"物料{i}", spec=f"S{i}", stock=100, price=10)
                for i in range(1, 26)]
        db.session.add_all([unit, wh, dept, *mats])
        db.session.flush()
        order = InOrder(order_no="IN-PUSH-001", business_type="采购入库",
                        status="completed", warehouse="仓库A", total_amount=0)
        db.session.add(order)
        db.session.flush()
        for m in mats:
            db.session.add(InOrderItem(in_order_id=order.id, material_id=m.id,
                                       quantity=10, price=10, amount=100))
        db.session.commit()
        print("SEEDED in_order id=", order.id, "items=", len(order.items))
    else:
        o = InOrder.query.first()
        print("EXISTS in_order id=", o.id, "status=", o.status, "items=", len(o.items))