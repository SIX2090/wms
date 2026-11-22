"""首页领料待办计单，列表按行展示同一批领料单。"""
import re

import app as wms
from tests.test_document_create_number_conflicts import case  # noqa: F401


def test_requisition_filter_home_count_recent_and_list(case):
    clients, ids = case
    types = ['领料单', None, '销售出库', '采购退货出库', '其他出库', '领料单']
    numbers = [f'HOME-REQ-{i}' for i in range(len(types))]
    with wms.app.app_context():
        for i, kind in enumerate(types):
            order = wms.OutOrder(order_no=numbers[i], business_type=kind,
                                 status='completed' if i == 5 else 'pending', warehouse=ids['names'][0])
            wms.db.session.add(order)
            wms.db.session.flush()
            if i == 0:
                for material_id in ids['mats']:
                    wms.db.session.add(wms.OutOrderItem(out_order_id=order.id, material_id=material_id, quantity=1, price=2, amount=2))
        wms.db.session.commit()
    home = clients[0].get('/')
    assert home.status_code == 200
    card = home.get_data(as_text=True).split('<h4>待完成领料单</h4>', 1)[1].split('class="todo-card"', 1)[0]
    link, count = re.search(r'<a href="([^"]+)" class="todo-count[^"]*">(\d+)</a>', card).groups()
    assert int(count) == 2
    listing = clients[0].get(link)
    assert listing.status_code == 200
    for page in (card, listing.get_data(as_text=True)):
        assert all(number in page for number in numbers[:2])
        assert all(number not in page for number in numbers[2:])
