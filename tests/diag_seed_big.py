# -*- coding: utf-8 -*-
"""临时诊断（用完即删）：造一条 500 条明细的完成入库单，测大单下推/详情页渲染。"""
import os
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

from app import (InOrder, InOrderItem, Material, db)  # noqa: E402
import app as app_module  # noqa: E402

with app_module.app.app_context():
    # 造 500 个物料（若不足）
    have = Material.query.count()
    need = 500
    mats = []
    if have < need:
        new = [Material(code=f"BIG{i:04d}", name=f"批量物料{i}", spec=f"SP{i}", stock=1000, price=i % 20 + 1)
               for i in range(have + 1, need + 1)]
        db.session.add_all(new)
        db.session.flush()
        mats = new
    else:
        mats = Material.query.limit(500).all()

    order = InOrder(order_no="IN-PUSH-BIG", business_type="采购入库",
                    status="completed", warehouse="仓库A", total_amount=0)
    db.session.add(order)
    db.session.flush()
    for m in mats:
        db.session.add(InOrderItem(in_order_id=order.id, material_id=m.id,
                                   quantity=10, price=10, amount=100))
    db.session.commit()
    print("SEEDED big in_order id=", order.id, "items=", len(order.items))