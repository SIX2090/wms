# -*- coding: utf-8 -*-
"""BUG-2026-09-22-016 回归：手工采购单必须计入采购申请下推进度，禁止重复下推。

事故根因（R6 同模式：关联字段只在一条入口写入）：

``build_purchase_request_execution`` 只按 ``PurchaseOrderItem.purchase_request_item_id``
聚合「已下推量」。但该字段**只有两条下推入口会写**：

  - ``routes/purchase_request.py:284``（多供应商分组下推）
  - ``routes/purchase_request.py:339``（单供应商下推）

而手工建单的三条落库路径**全都不写**：

  - ``routes/purchase_order.py:566``  手工新增/编辑保存
  - ``routes/purchase_order.py:842``  复制采购单
  - ``routes/purchase_order.py:357``  Excel 导入

于是用户「先审核通过采购申请，再自己去采购单页手工建一张同样物料的采购单」时，
申请详情页的「已下推」恒为 0、「未下推」恒为满额，**同一申请可以被反复下推**
（实测：申请 100 → 手工采购 100 → 再次下推又生成 100，实际采购 200，超采一倍）。

修复口径（已与产品确认）：**下推时按物料自动关联**——
把这些「挂在同一采购申请下、但明细未标记来源行」的手工采购量，按 ``material_id``
回填到本申请的同物料申请行上；同一物料在本申请里出现多行时**按行序先到先得**
（依次填满第 1 行、剩余才进第 2 行）。

两条关联线索取并集：
  ① ``purchase_order.purchase_request_id == 本申请``（显式来源，最可靠）；
  ② 备注含本申请单号（``由采购申请 {request_no} 下推生成``），兼容早期未写表头
     字段的历史单据。

刻意不做：不回写 ``purchase_request_item_id``——手工单与具体申请行本无绑定，
硬写会篡改用户未表达过的意图，且「编辑采购单」整批重建明细时会丢该字段，重回本 BUG。

测试策略：
  T1. 核心：申请 100 + 手工采购单（同物料、同申请）100 → 未下推必须为 0、状态已完成。
      修复前此用例必红（未下推仍显示 100）。
  T2. 端到端堵漏：修复后再次调用下推接口，必须被拒（或返回「已全部下推」），
      且**不得新建采购单**——这是本 BUG 真正要挡住的行为。
  T3. 部分采购：手工采购 40/100 → 未下推 60，下推 60 成功、下推 70 被拒。
  T4. 分摊口径：同申请两行同物料各 50，手工采购 60 → 第 1 行已下推 50、第 2 行 10。
  T5. 不越界：另一张申请的手工采购单不得影响本申请（表头 purchase_request_id 隔离）；
      同为 NULL 关联但物料相同的「裸采购单」也不得被计入。
  T6. 历史数据线索：采购单表头 purchase_request_id 为 None 但备注含本申请单号时，
      仍须计入（兼容早期数据）。
  T7. 不回归：下推生成的标准采购单（有 purchase_request_item_id）计数不受影响，
      且不会被兜底逻辑重复计一次。
  T8. 已入库量回填不得让 remaining_to_receive 为负、也不得虚增已入库。
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
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    PurchaseRequest, PurchaseRequestItem, PurchaseOrder, PurchaseOrderItem,
    build_purchase_request_execution,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    m1 = Material(code="M001", name="物料一", spec="S1", category=cat, unit=unit,
                  supplier=sup, stock=0, price=10, min_stock=0, max_stock=9999, reorder_point=0)
    m2 = Material(code="M002", name="物料二", spec="S2", category=cat, unit=unit,
                  supplier=sup, stock=0, price=20, min_stock=0, max_stock=9999, reorder_point=0)
    db.session.add_all([unit, cat, sup, user, m1, m2])
    db.session.commit()
    return {"m1": m1, "m2": m2, "sup": sup, "user": user}


def _make_request(request_no, rows, status='approved'):
    """建采购申请；rows = [(material, qty), ...]"""
    req = PurchaseRequest(request_no=request_no, date=date.today(), status=status,
                          applicant='tester', department='生产一部')
    db.session.add(req)
    db.session.flush()
    items = []
    for material, qty in rows:
        it = PurchaseRequestItem(
            purchase_request_id=req.id, material_id=material.id,
            material_code=material.code, material_name=material.name,
            quantity=qty, estimated_price=material.price or 0,
            estimated_amount=(material.price or 0) * qty,
        )
        db.session.add(it)
        items.append(it)
    db.session.commit()
    return req, items


def _make_manual_po(order_no, items, purchase_request_id=None, remark=None, status='pending'):
    """手工采购单：明细**不带** purchase_request_item_id（与 save_purchase_order 落库一致）。"""
    po = PurchaseOrder(order_no=order_no, date=date.today(),
                       purchase_request_id=purchase_request_id, remark=remark, status=status)
    db.session.add(po)
    db.session.flush()
    for material, qty, received in items:
        db.session.add(PurchaseOrderItem(
            purchase_order_id=po.id, material_id=material.id,
            purchase_request_item_id=None,
            quantity=qty, received_quantity=received,
            price=material.price or 0, amount=(material.price or 0) * qty,
        ))
    db.session.commit()
    return po


def _make_client():
    import re
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    return client


def _exec(valid_items, request_order=None):
    return build_purchase_request_execution(valid_items, request_order)


# A9 规则要求「新增业务函数必须在 tests/ 至少有 1 个对应测试」，匹配形式为
# 文件 test_<func_name>.py 或函数 test_<func_name>。本函数在本次修复中新增了
# request_order 形参（属被改动的函数签名），故显式提供同名测试入口，
# 实际断言复用上面的类内用例，避免重复维护。
def test_build_purchase_request_execution():
    """A9 入口：build_purchase_request_execution 的核心契约。

    这里只做轻量冒烟（签名兼容 + 口径自洽），完整场景见
    ``TestBug20260922016ManualPoCountsTowardRequest`` 的 T1–T8。
    """
    with app_module.app.app_context():
        _reset_db()
        s = _seed()
        req, items = _make_request('PR-A9', [(s['m1'], 100)])

        # 1) 不传 request_order 也必须可用（向后兼容既有调用方）
        ex_legacy = _exec(items)
        assert ex_legacy[items[0].id]['ordered_quantity'] == 0, ex_legacy

        # 2) 传 request_order 时，手工采购单须被计入
        _make_manual_po('PO-A9', [(s['m1'], 100, 0)], purchase_request_id=req.id)
        ex = _exec(items, req)[items[0].id]
        assert ex['ordered_quantity'] == 100, ex
        assert ex['remaining_to_order'] == 0, ex

        # 3) 键集稳定（下游模板按这些键取值）
        assert set(ex.keys()) == {
            'request_quantity', 'ordered_quantity', 'received_quantity',
            'remaining_to_order', 'remaining_to_receive', 'status',
        }, sorted(ex.keys())


class TestBug20260922016ManualPoCountsTowardRequest:
    """手工采购单必须计入采购申请的下推进度。"""

    def test_T1_manual_po_fills_remaining_to_order(self):
        """申请 100 + 手工采购 100 → 未下推为 0（修复前仍显示 100）。

        注意 status 语义：本函数（以及列表页 execution_status）的 ``completed``
        判定条件是 ``received_qty >= request_qty``——**货物真的入库才算完成**，
        仅「已下单」只能到 ``partial``。这是既有口径，本次修复不动它，
        所以这里断言 ``partial`` 而非 ``completed``。
        """
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-001', [(s['m1'], 100)])
            _make_manual_po('PO-MANUAL-1', [(s['m1'], 100, 0)], purchase_request_id=req.id)

            ex = _exec(items, req)[items[0].id]
            assert ex['request_quantity'] == 100, ex
            assert ex['ordered_quantity'] == 100, (
                f"手工采购单未被计入已下推（ordered={ex['ordered_quantity']}）——"
                "BUG-2026-09-22-016 复发：申请可被重复下推"
            )
            assert ex['remaining_to_order'] == 0, (
                f"未下推量应为 0，实际 {ex['remaining_to_order']}——手工采购单未计入"
            )
            assert ex['status'] == 'partial', (
                f"已下单未入库应为 partial（completed 需 received 达标），实际 {ex['status']}"
            )
            assert ex['remaining_to_receive'] == 100, (
                f"未入库应为 100，实际 {ex['remaining_to_receive']}"
            )

    def test_T2_repush_is_blocked_end_to_end(self):
        """端到端：手工采购已满足申请后，再次下推必须被拒且不新建采购单。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-002', [(s['m1'], 100)])
            _make_manual_po('PO-MANUAL-2', [(s['m1'], 100, 0)], purchase_request_id=req.id)
            client = _make_client()
            before = PurchaseOrder.query.count()

            resp = client.post(f'/purchase_request/{req.id}/create_purchase_order', json={})
            body = resp.get_json(silent=True) or {}
            after = PurchaseOrder.query.count()

            # 两种可接受结局：直接拒绝，或返回「已全部下推」的成功提示；
            # 真正不可接受的是**又建了一张单**。
            assert after == before, (
                f"重复下推又新建了采购单（{before} → {after}）——"
                "BUG-2026-09-22-016 未修好：同一申请被重复执行"
            )
            msg = body.get('msg', '')
            assert body.get('status') == 'error' or '已全部下推' in msg, (
                f"应拒绝或提示已全部下推，实际：{resp.status_code} {body}"
            )

    def test_T3_partial_manual_po_narrows_remaining(self):
        """手工采购 40/100 → 未下推 60；下推 60 成功、下推 70 被拒。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-003', [(s['m1'], 100)])
            _make_manual_po('PO-MANUAL-3', [(s['m1'], 40, 0)], purchase_request_id=req.id)
            item_id = items[0].id
            client = _make_client()

            ex = _exec(items, req)[item_id]
            assert ex['ordered_quantity'] == 40, ex
            assert ex['remaining_to_order'] == 60, ex

            over = client.post(f'/purchase_request/{req.id}/create_purchase_order', json={
                'items': [{'purchase_request_item_id': item_id, 'quantity': 70}],
            })
            over_body = over.get_json(silent=True) or {}
            assert over_body.get('status') == 'error', (
                f"下推 70 > 未下推 60，应被拒：{over_body}"
            )

            ok = client.post(f'/purchase_request/{req.id}/create_purchase_order', json={
                'items': [{'purchase_request_item_id': item_id, 'quantity': 60}],
            })
            ok_body = ok.get_json(silent=True) or {}
            assert ok_body.get('status') == 'success', f"下推 60 应成功：{ok_body}"

    def test_T4_same_material_two_rows_fills_first_row_first(self):
        """分摊口径：两行各 50 + 手工 60 → 第 1 行已下推 50、第 2 行 10。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-004', [(s['m1'], 50), (s['m1'], 50)])
            body = _exec(items, req)
            assert len(items) == 2
            assert body[items[0].id]['ordered_quantity'] == 0, "先验证无手工单时基线为 0"

            _make_manual_po('PO-MANUAL-4', [(s['m1'], 60, 0)], purchase_request_id=req.id)
            body = _exec(items, req)
            assert body[items[0].id]['ordered_quantity'] == 50, (
                f"第 1 行应被填满 50，实际 {body[items[0].id]['ordered_quantity']}"
            )
            assert body[items[1].id]['ordered_quantity'] == 10, (
                f"第 2 行应分到 10，实际 {body[items[1].id]['ordered_quantity']}"
            )
            assert body[items[0].id]['remaining_to_order'] == 0, body[items[0].id]
            assert body[items[1].id]['remaining_to_order'] == 40, body[items[1].id]

    def test_T5_other_request_and_orphan_po_not_counted(self):
        """别的申请的手工单、以及无来源的裸采购单都不得计入本申请。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req_a, items_a = _make_request('PR-005A', [(s['m1'], 100)])
            req_b, _ = _make_request('PR-005B', [(s['m1'], 100)])
            # 挂到**别的申请**上
            _make_manual_po('PO-OTHER-REQ', [(s['m1'], 100, 0)], purchase_request_id=req_b.id)
            # 裸单：既不挂申请、备注也不含本申请单号
            _make_manual_po('PO-ORPHAN', [(s['m1'], 100, 0)], purchase_request_id=None,
                            remark='随手建的采购单')

            ex = _exec(items_a, req_a)[items_a[0].id]
            assert ex['ordered_quantity'] == 0, (
                f"别的申请/无来源的采购单被误计入本申请（ordered={ex['ordered_quantity']}）"
            )
            assert ex['remaining_to_order'] == 100, ex

            # 反向确认 req_b 能正确看到自己那张
            items_b = PurchaseRequestItem.query.filter_by(purchase_request_id=req_b.id).all()
            ex_b = _exec(items_b, req_b)[items_b[0].id]
            assert ex_b['ordered_quantity'] == 100, ex_b

    def test_T6_legacy_po_matched_by_remark(self):
        """历史数据：表头 purchase_request_id 为空但备注含本申请单号，仍须计入。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-006', [(s['m1'], 100)])
            _make_manual_po('PO-LEGACY', [(s['m1'], 100, 0)], purchase_request_id=None,
                            remark=f'由采购申请 {req.request_no} 下推生成')

            ex = _exec(items, req)[items[0].id]
            assert ex['ordered_quantity'] == 100, (
                "备注反查未命中——早期未写表头字段的单据会漏计，仍可重复下推"
            )
            assert ex['remaining_to_order'] == 0, ex

    def test_T7_standard_push_not_double_counted(self):
        """下推生成的标准采购单（带 purchase_request_item_id）只计一次。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-007', [(s['m1'], 100)])
            po = PurchaseOrder(order_no='PO-STD', date=date.today(),
                               purchase_request_id=req.id, status='pending')
            db.session.add(po)
            db.session.flush()
            db.session.add(PurchaseOrderItem(
                purchase_order_id=po.id, material_id=s['m1'].id,
                purchase_request_item_id=items[0].id,
                quantity=100, received_quantity=0, price=10, amount=1000,
            ))
            db.session.commit()

            ex = _exec(items, req)[items[0].id]
            assert ex['ordered_quantity'] == 100, (
                f"标准下推单被重复计数（ordered={ex['ordered_quantity']}，应为 100 而非 200）"
            )

    def test_T8_received_backfill_never_exceeds_ordered(self):
        """已入库量回填不得让 remaining_to_receive 为负、也不得虚增已入库。"""
        with app_module.app.app_context():
            _reset_db()
            s = _seed()
            req, items = _make_request('PR-008', [(s['m1'], 100)])
            # 手工单：下了 100、其中 30 已入库
            _make_manual_po('PO-RECV', [(s['m1'], 100, 30)], purchase_request_id=req.id)

            ex = _exec(items, req)[items[0].id]
            assert ex['ordered_quantity'] == 100, ex
            assert ex['received_quantity'] == 30, (
                f"已入库量应按同额度回填为 30，实际 {ex['received_quantity']}"
            )
            assert ex['remaining_to_receive'] == 70, (
                f"未入库应为 70，实际 {ex['remaining_to_receive']}"
            )
            assert ex['remaining_to_receive'] >= 0, "remaining_to_receive 不得为负"
            assert ex['received_quantity'] <= ex['ordered_quantity'], (
                "已入库量不得超过已下推量"
            )
