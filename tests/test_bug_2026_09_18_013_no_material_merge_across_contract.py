# -*- coding: utf-8 -*-
"""BUG-2026-09-18-013 回归测试：禁止单据明细「同物料跨合同」合并。

## 需求
禁止把「物料编号/名称/规格相同但合同编号不同」的单据明细合并成一行。
同一物料按不同合同编号分批入库是常见业务，合并会把合同归属与金额溯源全部搞错。

## 根因
`find_duplicate_in_order_item` 只按 `(material_id, source_purchase_order_item_id)` 判重，
**完全不看合同编号**；且入库侧存在两个口径不一致的合并入口：

  - 入口 A：`POST /in_order/<id>/item/add`（`add_in_order_item`）
    key = `(material_id, source_purchase_order_item_id)`
  - 入口 B：`POST /in_order/add` 的 JSON items 分支（`add_in_order`）
    key = `(material_id, source_purchase_order_item_id,
            source_sales_order_item_id, is_customer_supplied)`

由配置项 `in_order_duplicate_material_mode`（默认 `merge`）控制合并 / 报错。
出库侧与手机端从来不做物料合并。

## 修复
**彻底删除合并能力**（不是改为默认 forbid）：
  - 删除 `find_duplicate_in_order_item` 函数
  - 删除设置项 `in_order_duplicate_material_mode` 的定义、getter 与全部读取点
  - 两个入口都改为**无条件新增一行**，不判重、不提示

为什么删干净而不是留作提示：用户明确要求"直接新增，不提示"。保留函数会给
日后"把合并加回来"留抓手 —— **删干净是防回归最硬的保证**。

## 用例
  T1.  同物料无合同连加两次 → 2 行（本 BUG 核心断言）
  T2.  同物料同合同加两次 → 2 行
  T3.  同物料不同合同 → 2 行且合同号各自正确
  T4.  同物料同合同但不同采购来源行 → 2 行
  T5.  采购来源行带合同号 → 新增行继承（AA2 能力，防回退）
  T6.  采购来源重复录入 → received_quantity 累加正确（防删 merge 丢回写）
  T7.  用户输入合同号优先于表头
  T8.  表头合同号兜底
  T9.  入口 B JSON 同物料两行 → 落库 2 行
  T10. 两个入口行为一致（结构性：两处都不得再出现判重）
  T11. 设置项定义已从 SYSTEM_SETTING_DEFINITIONS 移除
  T12. 源码不再出现 in_order_duplicate_material_mode / find_duplicate_in_order_item
  T13. 旧配置残留（手动写回 merge）添加两次仍 2 行（向后兼容核心断言）
  T14. 采购单选单生成入库单 → 明细带采购明细的合同号（AA2 用户明确诉求）
  T15. 采购单下推入库单 → 明细带采购明细的合同号（AA2）
  T16. 已完成入库单 is_new 新增明细 → 按优先级解析合同号（AA2）
  T17. Excel 导入入库 → 明细兜底继承表头合同号（AA2）
  T18. Android 扫码入库 → 明细继承表头合同号（AA2）
  T19. 出库逐行 add → 明细带合同号（用户输入 > 表头）（AA2）
  T20. 结构性：收口函数 resolve_item_contract 在各明细构造点被调用
  T21. resolve_item_contract 优先级与「字段独立取值」语义（单元级）
"""
from __future__ import annotations

import os
import re
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
    db, Warehouse, User, Material, MaterialCategory, Unit,
    InOrder, InOrderItem, Supplier, PurchaseOrder, PurchaseOrderItem,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


# ---------- 夹具 ----------

def _seed(business_type="其他入库", header_contract="HDR-CT", po_contract="PO-CT"):
    """建一张待处理入库单（+ 可选采购来源行），返回 (order_id, material_code, po_item_id)。"""
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    unit = Unit(code="PCS", name="个")
    sup = Supplier(code="SUP001", name="供应商甲")
    user = User(username="admin", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    db.session.add_all([wh, cat, unit, sup, user])
    db.session.flush()
    mat = Material(code="M001", name="电缆", spec="3x2.5", category_id=cat.id,
                   unit_id=unit.id, price=10.0, stock=0.0)
    db.session.add(mat)
    db.session.flush()

    order = InOrder(
        order_no="IN-013-001", date=date.today(), business_type=business_type,
        warehouse="仓库A", supplier_id=sup.id, status="pending",
        contract_no=header_contract, project_name="工程甲",
        operator_id=user.id,
    )
    db.session.add(order)
    db.session.flush()

    po_item_id = None
    if po_contract is not None:
        po = PurchaseOrder(order_no="PO-013-001", date=date.today(),
                           supplier_id=sup.id, status="pending",
                           contract_no=po_contract,
                           project_name="工程乙")
        db.session.add(po)
        db.session.flush()
        poi = PurchaseOrderItem(purchase_order_id=po.id, material_id=mat.id,
                                quantity=100.0, price=10.0, amount=1000.0,
                                received_quantity=0.0, contract_no=po_contract,
                                project_name="工程乙")
        db.session.add(poi)
        db.session.flush()
        po_item_id = poi.id

    db.session.commit()
    return order.id, mat.code, po_item_id


def _login():
    c = app_module.app.test_client()
    page = c.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    c.post("/login", data={"username": "admin", "password": "admin",
                           "csrf_token": m.group(1) if m else ""})
    return c


def _reset():
    db.drop_all()
    db.create_all()


def _add_item(client, order_id, code, qty=1, price=10, contract_no=None,
              po_item_id=None):
    """调入口 A 加一行明细。"""
    body = {"material_code": code, "quantity": qty, "price": price}
    if contract_no is not None:
        body["contract_no"] = contract_no
    if po_item_id is not None:
        body["source_purchase_order_item_id"] = po_item_id
    return client.post(f"/in_order/{order_id}/item/add", data=body)


def _items(order_id):
    with app_module.app.app_context():
        return InOrderItem.query.filter_by(in_order_id=order_id).order_by(InOrderItem.id).all()


# ---------- T1~T4：不合并 ----------

def test_T1_same_material_no_contract_added_twice_creates_two_rows():
    """本 BUG 核心断言：同物料无合同连加两次，必须 2 行（此前被合并成 1 行）。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed()
    c = _login()
    _add_item(c, oid, code, qty=5)
    _add_item(c, oid, code, qty=3)
    rows = _items(oid)
    assert len(rows) == 2, f"同物料应保留 2 行不合并，实际 {len(rows)} 行"
    assert sorted(r.quantity for r in rows) == [3.0, 5.0]


def test_T2_same_material_same_contract_added_twice_creates_two_rows():
    """同物料 + 同合同号，仍是 2 行（合同号不再是合并开关，合并已彻底取消）。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed()
    c = _login()
    _add_item(c, oid, code, qty=5, contract_no="HD260909")
    _add_item(c, oid, code, qty=3, contract_no="HD260909")
    rows = _items(oid)
    assert len(rows) == 2, f"应保留 2 行，实际 {len(rows)} 行"
    assert all(r.contract_no == "HD260909" for r in rows)


def test_T3_same_material_different_contract_keeps_both_contract_nos():
    """同物料 + 不同合同号 → 2 行，且各自保留自己的合同号（本 BUG 的业务本意）。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed()
    c = _login()
    _add_item(c, oid, code, qty=5, contract_no="HD260909")
    _add_item(c, oid, code, qty=3, contract_no="HD260708")
    rows = _items(oid)
    assert len(rows) == 2, f"不同合同必须分开成 2 行，实际 {len(rows)} 行"
    assert sorted(r.contract_no for r in rows) == ["HD260708", "HD260909"]


def test_T4_same_material_different_source_po_creates_two_rows():
    """同物料 + 同合同 + 不同来源采购行 → 2 行（来源行不再触发合并）。"""
    with app_module.app.app_context():
        _reset()
        oid, code, po_item_id = _seed()
    c = _login()
    _add_item(c, oid, code, qty=5, po_item_id=po_item_id)
    _add_item(c, oid, code, qty=3, po_item_id=po_item_id)
    assert len(_items(oid)) == 2, "同一来源行重复录入也应保留 2 行"


# ---------- T5~T8：合同号传播 ----------

def test_T5_source_purchase_order_item_contract_inherited():
    """采购来源行的合同号应写入明细行。"""
    with app_module.app.app_context():
        _reset()
        oid, code, po_item_id = _seed(po_contract="PO-CT-9")
    c = _login()
    _add_item(c, oid, code, qty=5, po_item_id=po_item_id)
    rows = _items(oid)
    assert rows[0].contract_no == "PO-CT-9", (
        f"应继承采购来源行合同号 PO-CT-9，实际 {rows[0].contract_no!r}")


def test_T6_source_received_quantity_accumulates_per_row():
    """删除 merge 分支后，每行都必须回写 received_quantity，不能丢累加。"""
    with app_module.app.app_context():
        _reset()
        oid, code, po_item_id = _seed()
    c = _login()
    _add_item(c, oid, code, qty=5, po_item_id=po_item_id)
    _add_item(c, oid, code, qty=3, po_item_id=po_item_id)
    with app_module.app.app_context():
        poi = db.session.get(PurchaseOrderItem, po_item_id)
        assert poi.received_quantity == 8.0, (
            f"采购行已入库数量应为 5+3=8，实际 {poi.received_quantity}")


def test_T7_user_input_contract_wins_over_header():
    """用户在本行显式输入的合同号优先于表头。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed(header_contract="HDR-CT")
    c = _login()
    _add_item(c, oid, code, qty=1, contract_no="USER-CT")
    rows = _items(oid)
    assert rows[0].contract_no == "USER-CT", (
        f"应取用户输入 USER-CT，实际 {rows[0].contract_no!r}")


def test_T8_header_contract_fallback():
    """无用户输入、无采购来源时，明细继承表头合同号。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed(header_contract="HDR-CT", po_contract=None)
    c = _login()
    _add_item(c, oid, code, qty=1)
    rows = _items(oid)
    assert rows[0].contract_no == "HDR-CT", (
        f"应兜底取表头 HDR-CT，实际 {rows[0].contract_no!r}")


# ---------- T9~T10：入口 B 与口径统一 ----------

def test_T9_entry_b_json_same_material_twice_creates_two_rows():
    """入口 B（/in_order/add JSON 分支）同样不合并。"""
    with app_module.app.app_context():
        _reset()
        _seed(po_contract=None)
    c = _login()
    payload = {
        "business_type": "其他入库",
        "warehouse": "仓库A",
        "status": "pending",
        "contract_no": "HDR-CT",
        "items": [
            {"code": "M001", "quantity": 5, "price": 10, "contract_no": "HD260909"},
            {"code": "M001", "quantity": 3, "price": 10, "contract_no": "HD260708"},
        ],
    }
    resp = c.post("/in_order/add", json=payload)
    assert resp.status_code in (200, 201, 302), f"add 返回 {resp.status_code}"
    with app_module.app.app_context():
        # 入口 B 新建一张单（单号由后端生成），取其明细校验
        # 注意不能用夹具里的 IN-013-001（那张单没有明细）
        order = InOrder.query.filter(InOrder.order_no != "IN-013-001") \
                             .order_by(InOrder.id.desc()).first()
        assert order is not None, "入口 B 应新建一张入库单"
        rows = InOrderItem.query.filter_by(in_order_id=order.id).all()
    assert len(rows) == 2, f"入口 B 应保留 2 行，实际 {len(rows)} 行"
    assert sorted(r.contract_no for r in rows) == ["HD260708", "HD260909"]


def test_T10_both_entries_have_no_dedup_logic():
    """结构性断言：两个入口都不得再出现任何判重/合并代码。"""
    src = (ROOT / "app" / "routes" / "in_order.py").read_text(encoding="utf-8")
    # 去掉注释行，避免命中说明性文字
    code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    for token in ("duplicate_key", "duplicate_item", "duplicate_mode",
                  "existing_item", "pending_in_order_items"):
        assert token not in code, f"入口仍残留合并相关标识符：{token}"


# ---------- T11~T13：设置项移除与向后兼容 ----------

def test_T11_setting_definition_removed():
    """设置项定义已从 SYSTEM_SETTING_DEFINITIONS 移除。"""
    defs = app_module.SYSTEM_SETTING_DEFINITIONS
    keys = set()
    if isinstance(defs, dict):
        keys = set(defs.keys())
    else:
        for group in defs:
            items = group.get("items", group.get("settings", [])) if isinstance(group, dict) else []
            for it in items:
                if isinstance(it, dict) and "key" in it:
                    keys.add(it["key"])
    assert "in_order_duplicate_material_mode" not in keys, (
        "设置项 in_order_duplicate_material_mode 应从定义中移除")


def test_T12_source_has_no_merge_symbols():
    """结构性断言：源码不再出现判重函数与设置项（防合并复活）。"""
    for rel in ("app/app.py", "app/routes/in_order.py"):
        code = "\n".join(
            l for l in (ROOT / rel).read_text(encoding="utf-8").splitlines()
            if not l.strip().startswith("#")
        )
        assert "find_duplicate_in_order_item" not in code, (
            f"{rel} 仍残留 find_duplicate_in_order_item")
        assert "in_order_duplicate_material_mode" not in code, (
            f"{rel} 仍残留 in_order_duplicate_material_mode")


def test_T13_legacy_merge_setting_has_no_effect():
    """向后兼容核心断言：旧库残留 merge 配置时，仍然不合并。"""
    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed()
        # 模拟旧库里残留的配置值
        from app import set_system_setting
        set_system_setting("in_order_duplicate_material_mode", "merge")
    c = _login()
    _add_item(c, oid, code, qty=5)
    _add_item(c, oid, code, qty=3)
    assert len(_items(oid)) == 2, "旧配置 merge 残留不得恢复合并行为"


# ---------- T14~T19：合同号传播（AA2） ----------
#
# 为什么这些用例重要：AA1 只是「不再合并」，若不把合同号传播到各录入路径，
# 明细行仍会丢合同归属，「同物料跨合同分开成多行」就失去了业务意义
# —— 分开的行无法区分是哪张合同。以下逐条锁死每个录入路径。

def test_T14_purchase_order_selection_carries_item_contract():
    """采购单选单生成入库单：明细行必须带采购明细的合同号（用户明确诉求）。"""
    with app_module.app.app_context():
        _reset()
        # 这里必须建出采购来源行（po_contract 传非 None），否则没有可选的采购明细
        _seed(po_contract="SEED-CT")
        po_item = PurchaseOrderItem.query.first()
        assert po_item is not None
        po_item.contract_id = None
        po_item.contract_no = "PO-ITEM-CT"
        po_item.project_name = "工程丙"
        db.session.commit()
        po_item_id = po_item.id
    c = _login()
    resp = c.post("/purchase_order/create_in_order_from_selection", json={
        "items": [{"purchase_order_item_id": po_item_id, "quantity": 5}],
        "warehouse": "仓库A",
    })
    assert resp.status_code in (200, 201, 302), (
        f"选单生成返回 {resp.status_code}：{resp.get_data(as_text=True)[:300]}")
    with app_module.app.app_context():
        order = InOrder.query.filter(InOrder.business_type == "采购入库") \
                             .order_by(InOrder.id.desc()).first()
        assert order is not None, "应生成一张采购入库单"
        rows = InOrderItem.query.filter_by(in_order_id=order.id).all()
    assert len(rows) == 1
    assert rows[0].contract_no == "PO-ITEM-CT", (
        f"入库明细应带采购明细合同号 PO-ITEM-CT，实际 {rows[0].contract_no!r}")
    assert rows[0].project_name == "工程丙"


def test_T15_purchase_order_downpush_carries_item_contract():
    """采购单下推入库单（_create_in_order_from_purchase_order_core）同样带合同号。"""
    with app_module.app.app_context():
        _reset()
        _seed(po_contract="SEED-CT")
        po = PurchaseOrder.query.first()
        po_item = PurchaseOrderItem.query.first()
        assert po_item is not None
        po_item.contract_no = "PUSH-CT"
        po_item.project_name = "工程丁"
        db.session.commit()
        po_id = po.id
    c = _login()
    # 下推函数内部用 current_user.id 记操作人，必须在「已登录」的请求上下文里调用。
    # 借 test_client 的一个真实请求上下文承载登录态。
    with c.session_transaction() as _sess:
        pass
    with c.application.test_request_context("/"):
        from flask_login import login_user
        from app import User
        login_user(db.session.get(User, 1))
        from app import _create_in_order_from_purchase_order_core
        in_order, err = _create_in_order_from_purchase_order_core(
            db.session.get(PurchaseOrder, po_id), warehouse="仓库A")
        assert err is None, f"下推应成功，实际错误：{err}"
        in_order_id = in_order.id
    with app_module.app.app_context():
        rows = InOrderItem.query.filter_by(in_order_id=in_order_id).all()
    assert len(rows) >= 1
    assert any(r.contract_no == "PUSH-CT" for r in rows), (
        f"下推明细应带采购明细合同号 PUSH-CT，实际 {[r.contract_no for r in rows]}")


def test_T16_completed_in_order_new_item_resolves_contract():
    """已完成入库单新增明细：合同号按「用户输入 > 来源行 > 表头」解析。"""
    with app_module.app.app_context():
        _reset()
        oid, code, po_item_id = _seed(header_contract="HDR-CT", po_contract=None)
        order = db.session.get(InOrder, oid)
        order.status = "completed"
        db.session.commit()
    c = _login()
    resp = c.post(f"/in_order/{oid}/update_completed", json={
        "items": [{"id": None, "is_new": True, "code": code, "material_code": code,
                   "quantity": 2, "price": 10, "contract_no": "DONE-CT"}],
    })
    assert resp.status_code in (200, 201, 302), (
        f"已完成单加明细返回 {resp.status_code}：{resp.get_data(as_text=True)[:300]}")
    rows = _items(oid)
    assert len(rows) == 1, f"应新增 1 行，实际 {len(rows)} 行"
    assert rows[0].contract_no == "DONE-CT", (
        f"应取用户输入 DONE-CT，实际 {rows[0].contract_no!r}")


def test_T17_excel_inbound_import_falls_back_to_header_contract():
    """Excel 导入入库：明细无合同列，兜底继承表头合同号。"""
    with app_module.app.app_context():
        _reset()
        _seed(header_contract=None, po_contract=None)

    from openpyxl import Workbook
    import io

    wb = Workbook()
    ws = wb.active
    ws.append(["入库单号", "日期", "业务类型", "仓库", "供应商", "合同编号",
               "物料编码", "数量", "单价"])
    ws.append(["IN-XLS-001", "2026-09-18", "采购入库", "仓库A", "SUP001", "XLS-CT",
               "M001", 4, 10])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    c = _login()
    resp = c.post("/import/in_order", data={
        "file": (buf, "in.xlsx"),
    }, content_type="multipart/form-data")
    assert resp.status_code in (200, 201, 302), (
        f"Excel 导入返回 {resp.status_code}：{resp.get_data(as_text=True)[:300]}")
    with app_module.app.app_context():
        order = InOrder.query.filter_by(order_no="IN-XLS-001").first()
        assert order is not None, "Excel 应导入一张入库单"
        rows = InOrderItem.query.filter_by(in_order_id=order.id).all()
    assert len(rows) == 1, f"应导入 1 行明细，实际 {len(rows)} 行"
    assert rows[0].contract_no == "XLS-CT", (
        f"明细应兜底继承表头合同号 XLS-CT，实际 {rows[0].contract_no!r}")


def test_T18_android_scan_inbound_inherits_header_contract():
    """Android 扫码入库：明细继承单据表头合同号。"""
    from datetime import datetime, timedelta
    from app import ApiToken, User

    with app_module.app.app_context():
        _reset()
        _seed(header_contract=None, po_contract=None)
        user = User.query.first()
        # 原生端 API 走 Bearer Token（不是 session 登录），直接播种一枚有效令牌
        token = ApiToken(token="T013-BEARER", user_id=user.id,
                         expires_at=datetime.now() + timedelta(days=1),
                         revoked=False)
        db.session.add(token)
        db.session.commit()
    c = app_module.app.test_client()
    resp = c.post("/api/inbound", json={
        "warehouse": "仓库A",
        "business_type": "其他入库",
        "contract_no": "AND-CT",
        "lines": [{"material_code": "M001", "quantity": 3, "price": 10}],
    }, headers={"Authorization": "Bearer T013-BEARER"})
    assert resp.status_code in (200, 201), (
        f"Android 入库返回 {resp.status_code}：{resp.get_data(as_text=True)[:300]}")
    body = resp.get_json() or {}
    assert body.get("status") in ("success", "ok", None), f"返回体：{body}"
    with app_module.app.app_context():
        order = InOrder.query.filter_by(contract_no="AND-CT").first()
        assert order is not None, "Android 应生成带合同号的入库单"
        rows = InOrderItem.query.filter_by(in_order_id=order.id).all()
    assert len(rows) == 1
    assert rows[0].contract_no == "AND-CT", (
        f"明细应继承表头 AND-CT，实际 {rows[0].contract_no!r}")


def test_T19_out_order_add_item_carries_contract():
    """出库逐行 add：用户输入合同号写入明细；无输入时兜底表头。"""
    from app import OutOrder, OutOrderItem

    with app_module.app.app_context():
        _reset()
        oid, code, _ = _seed(header_contract="OUT-HDR")
        out = OutOrder(order_no="OUT-013-001", date=date.today(),
                       business_type="领料出库", warehouse="仓库A",
                       status="pending", contract_no="OUT-HDR",
                       operator_id=1)
        db.session.add(out)
        db.session.commit()
        out_id = out.id
    c = _login()
    r1 = c.post(f"/out_order/{out_id}/item/add", data={
        "material_code": code, "quantity": 1, "price": 10,
        "contract_no": "OUT-USER"})
    assert r1.status_code == 200, f"出库加明细返回 {r1.status_code}"
    r2 = c.post(f"/out_order/{out_id}/item/add", data={
        "material_code": code, "quantity": 2, "price": 10})
    assert r2.status_code == 200
    with app_module.app.app_context():
        rows = OutOrderItem.query.filter_by(out_order_id=out_id).order_by(OutOrderItem.id).all()
    assert len(rows) == 2, f"出库侧本就不合并，应 2 行，实际 {len(rows)}"
    assert rows[0].contract_no == "OUT-USER", (
        f"第一行应取用户输入 OUT-USER，实际 {rows[0].contract_no!r}")
    assert rows[1].contract_no == "OUT-HDR", (
        f"第二行应兜底表头 OUT-HDR，实际 {rows[1].contract_no!r}")


# ---------- T20~T22：收口函数与结构性断言 ----------

def test_T20_all_in_order_item_creations_use_resolve_helper():
    """结构性断言：各「无逐行合同输入」的明细构造点必须调用 resolve_item_contract。

    防止日后有人新增录入路径时又各自决定要不要带合同号（这正是本 BUG 的成因）。
    """
    checks = {
        "app/app.py": 2,              # 采购下推 + resolve_item_contract 定义本身所在文件
        "app/routes/batch_import.py": 1,
        "app/routes/native_api.py": 2,
    }
    for rel, min_count in checks.items():
        code = (ROOT / rel).read_text(encoding="utf-8")
        n = code.count("resolve_item_contract")
        assert n >= min_count, (
            f"{rel} 中 resolve_item_contract 出现 {n} 次，应 >= {min_count} 次")


def test_resolve_item_contract():
    """resolve_item_contract 的优先级与「字段独立取值」语义（单元级）。

    这是 AA2 的收口函数本体测试 —— 前面 T5/T7/T8 走的是 HTTP 路径，
    这里直接对函数做边界验证：
      - 用户输入 > 来源行 > 表头
      - 三字段各自独立，不因某一层缺值为空而整体降级
      - 空字符串 / 纯空白视为「未填」而不是「填了空」
      - contract_id 字符串转 int，非法值退化为 None
    """
    from types import SimpleNamespace
    from app import resolve_item_contract

    header = SimpleNamespace(contract_id=1, contract_no="HDR", project_name="工程表头")
    source = SimpleNamespace(contract_id=2, contract_no="SRC", project_name="工程来源")

    # 用户输入最高优先
    assert resolve_item_contract(
        header, source_purchase_order_item=source,
        user_contract_no="USER")[:2] == (2, "USER")
    # 无用户输入时取来源行
    assert resolve_item_contract(header, source_purchase_order_item=source) == (
        2, "SRC", "工程来源")
    # 无来源行时取表头
    assert resolve_item_contract(header) == (1, "HDR", "工程表头")

    # 字段独立：来源行只有工程名称，合同号仍取表头
    partial = SimpleNamespace(contract_id=None, contract_no=None, project_name="只有工程名")
    cid, cno, pname = resolve_item_contract(header, source_purchase_order_item=partial)
    assert (cid, cno, pname) == (1, "HDR", "只有工程名"), (
        "三字段应各自独立取值，不因来源行缺合同号就整体退回表头")

    # 空字符串 / 纯空白 = 未填
    blank = SimpleNamespace(contract_id=None, contract_no="   ", project_name="")
    assert resolve_item_contract(header, source_purchase_order_item=blank)[1] == "HDR"

    # item_data 优先于来源行（JSON 入口语义）
    assert resolve_item_contract(
        header, item_data={"contract_no": "JSON-CT"},
        source_purchase_order_item=source)[1] == "JSON-CT"

    # contract_id 字符串 → int；非法 → None
    assert resolve_item_contract(header, user_contract_id="42")[0] == 42
    assert resolve_item_contract(header, user_contract_id="not-a-number")[0] is None

    # order=None（极端兜底）不抛异常
    assert resolve_item_contract(None) == (None, None, None)

