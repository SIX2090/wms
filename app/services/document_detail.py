"""Read-only business fields shared by document details and print outputs."""
from db import db


def get_out_order_box_numbers(order):
    """Resolve cabinets by active source/target item identity, never by material alone."""
    if order.business_type != '销售出库':
        return {}
    from app import DocumentPushLine, InOrder, InOrderItem
    target_items = {item.id: item.material_id for item in order.items}
    if not target_items:
        return {}
    links = (db.session.query(DocumentPushLine, InOrderItem, InOrder)
             .outerjoin(InOrderItem, DocumentPushLine.source_item_id == InOrderItem.id)
             .outerjoin(InOrder, DocumentPushLine.source_document_id == InOrder.id)
             .filter(DocumentPushLine.source_document_type == 'product_in_order',
                     DocumentPushLine.target_document_type == 'sales_out',
                     DocumentPushLine.target_document_id == order.id,
                     DocumentPushLine.target_item_id.in_(target_items),
                     DocumentPushLine.status == 'active')
             .order_by(DocumentPushLine.id).all())
    boxes = {}
    for link, source_item, source in links:
        if (not source or source.business_type != '产品入库' or not source_item
                or source_item.in_order_id != source.id
                or source_item.material_id != target_items[link.target_item_id]):
            continue
        values = boxes.setdefault(link.target_item_id, [])
        if source_item.box_no and source_item.box_no not in values:
            values.append(source_item.box_no)
    return {item_id: '、'.join(values) for item_id, values in boxes.items()}
