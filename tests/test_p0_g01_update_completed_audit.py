# -*- coding: utf-8 -*-
"""P0 闸门 G-01 回归：已完成入库单「改数」必须留痕。

体检缺口（`output/仓库业务流程与单据设计方案_20261111.md` §14.2 G-01）：

    ``POST /in_order/<id>/update_completed`` 允许对**已完成**的入库单
    改数量 / 改单价 / 删行 / 加行，并同步改库存与金额，但整个函数体内
    **没有任何 log_audit / log_operation**——而同文件的 delete / revert
    两个路由都有。后果：改完账面自洽（库存、金额、采购已收量都跟着变了），
    肉眼查不出；事后无法回答"谁把 800 改成了 80"。

修复要点（三条，缺一条就等于没修）：

  1. **old 值必须在任何写入之前快照**。函数是"边写边校验"的：删除分支会
     ``db.session.delete(item)``、改量分支会就地改写 ``item.quantity``。
     改完再取只能拿到新值，审计会变成"新值 == 新值"的自证为空。
  2. **必须在业务 commit 之后写**。``log_audit`` / ``log_operation`` 内部
     各自 ``db.session.commit()``；写在主 commit 之前会把半成品业务状态
     提前提交，破坏"要么全成、要么全不成"。
  3. **审计自身失败不得回传为"保存失败"**。业务已经提交，若此时报错，
     用户会以为没存、实际已改（与 BUG-2026-09-22-015 同一类认知错位）。

测试策略：

  T1 改量       → 审计行存在、operation/target 正确、changed 里 old/new 都是真值
  T2 删行       → new_data.removed 含该行的原数量（不是删除后的空值）
  T3 加行       → new_data.added 含新行
  T4 不传 reason → 仍然 200（不改变接口契约），reason 落固定文案
  T5 超长 reason → 落库截断到 200（换库时会 DataError，被 log_audit 吞掉）
  T6 无实际变更 → 不写审计（否则"点一次保存一条"，审计表失去可读性）
  T7 库存失败   → 不写审计（证明顺序正确：没提交就不该有成功痕迹）
  T8 结构断言   → 源码里 log_audit 必须出现在该函数的 db.session.commit() 之后

修复前 T1~T3、T8 必红（失败信息即"缺口复现"证据）。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from unittest.mock import patch

from tests.document_revision_client import document_post

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
    InOrder, InOrderItem, OperationAudit,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ROUTE_SRC = APP_DIR / "routes" / "in_order.py"
AUDIT_OP = "update_completed_in_order"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    unit = Unit(name="个", code="PCS")
    cat = MaterialCategory(name="默认分类", code="CAT-DEFAULT")
    sup = Supplier(code="SUP001", name="测试供应商")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(
        code="M001", name="测试物料", spec="S1",
        category=cat, unit=unit, supplier=sup,
        stock=100, price=10, min_stock=0, max_stock=9999, reorder_point=0,
    )
    db.session.add_all([unit, cat, sup, wh, user, mat])
    db.session.commit()
    return {"mat": mat, "wh": wh, "user": user}


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    document_post(client,
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _make_completed_in_order(mat, qty=50, items=None):
    """已完成入库单；material.stock 已置 100，相当于首行库存已入账。"""
    order = InOrder(
        order_no="IN-AUDIT-001",
        status="completed",
        warehouse="仓库A",
        business_type="其他入库",
        total_amount=qty * 10,
    )
    db.session.add(order)
    db.session.flush()
    spec = items if items is not None else [(qty, 10)]
    rows = []
    for q, p in spec:
        it = InOrderItem(
            in_order_id=order.id,
            material_id=mat.id,
            quantity=q,
            price=p,
            amount=round(q * p, 2),
        )
        db.session.add(it)
        rows.append(it)
    db.session.commit()
    return order, rows


def _audits(order_id):
    db.session.expire_all()
    return OperationAudit.query.filter_by(
        operation=AUDIT_OP, target_id=order_id
    ).order_by(OperationAudit.id).all()


def _payload(audit):
    return json.loads(audit.new_data or "{}")


class TestP0G01UpdateCompletedAudit:
    """已完成入库单改数必须写结构化审计（old → new 可回溯）。"""

    def test_T1_change_quantity_writes_audit_with_old_and_new(self):
        """核心：数量 50 → 80，审计里必须能读到 old=50 / new=80。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            item_id, order_id = rows[0].id, order.id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [{"id": item_id, "quantity": 80, "price": 10}],
                "deleted_items": [],
                "reason": "盘点差异修正",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            audits = _audits(order_id)
            assert len(audits) == 1, f"改数应写 1 条审计，实际 {len(audits)}"
            audit = audits[0]
            assert audit.operation == AUDIT_OP
            assert audit.target_type == "in_order"
            assert audit.target_name == "IN-AUDIT-001"
            assert audit.username, "审计必须记录操作人"
            assert audit.reason == "盘点差异修正"

            new_data = _payload(audit)
            changed = new_data.get("changed") or []
            assert len(changed) == 1, f"应记录 1 行变更，实际 {changed}"
            assert changed[0]["item_id"] == item_id
            assert changed[0]["old"]["qty"] == 50.0, "old 必须是改动前的真值"
            assert changed[0]["new"]["qty"] == 80.0, "new 必须是改动后的真值"

            old_data = json.loads(audit.old_data or "{}")
            assert old_data["warehouse"] == "仓库A"
            assert old_data["items"][str(item_id)]["qty"] == 50.0

    def test_T2_delete_item_records_removed_row(self):
        """删行：removed 里必须留着被删行的原数量，否则审计等于没写。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(
                seeds["mat"], items=[(30, 10), (20, 10)])
            order_id = order.id
            first_id, second_id = rows[0].id, rows[1].id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [{"id": second_id, "quantity": 20, "price": 10}],
                "deleted_items": [first_id],
                "reason": "录错了",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            audits = _audits(order_id)
            assert len(audits) == 1
            removed = _payload(audits[0]).get("removed") or []
            assert len(removed) == 1, f"应记录 1 行删除，实际 {removed}"
            assert removed[0]["item_id"] == first_id
            assert removed[0]["qty"] == 30.0, "被删行的原数量必须留存"
            assert db.session.get(InOrderItem, first_id) is None

    def test_T3_add_item_records_added_row(self):
        """加行：added 里必须有新行及其数量。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            order_id, first_id = order.id, rows[0].id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [
                    {"id": first_id, "quantity": 50, "price": 10},
                    {"is_new": True, "code": "M001", "quantity": 15, "price": 10},
                ],
                "deleted_items": [],
                "reason": "补录漏登",
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)

            added = _payload(_audits(order_id)[0]).get("added") or []
            assert len(added) == 1, f"应记录 1 行新增，实际 {added}"
            assert added[0]["qty"] == 15.0

    def test_T4_missing_reason_defaults_without_rejecting(self):
        """不传 reason 不得 400（不改变既有接口契约），落固定文案。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            order_id, item_id = order.id, rows[0].id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [{"id": item_id, "quantity": 60, "price": 10}],
                "deleted_items": [],
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            audits = _audits(order_id)
            assert len(audits) == 1
            assert audits[0].reason and "未填写原因" in audits[0].reason

    def test_T5_reason_truncated_to_column_length(self):
        """reason 是 String(200)；超长必须截断，否则换库会静默丢审计。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            order_id, item_id = order.id, rows[0].id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [{"id": item_id, "quantity": 70, "price": 10}],
                "deleted_items": [],
                "reason": "长" * 500,
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            audits = _audits(order_id)
            assert len(audits) == 1
            assert len(audits[0].reason) == 200

    def test_T6_no_change_writes_no_audit(self):
        """原值提交（只点了保存）：不留噪，否则审计表被保存动作淹没。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            order_id, item_id = order.id, rows[0].id

            resp = document_post(client, f"/in_order/{order_id}/update_completed", json={
                "items": [{"id": item_id, "quantity": 50, "price": 10}],
                "deleted_items": [],
            })
            assert resp.status_code == 200, resp.get_data(as_text=True)
            assert _audits(order_id) == [], "无实际变更不应写审计"

    def test_T7_stock_failure_writes_no_audit(self):
        """库存入口失败 → 整体回滚 → 不得留下"成功"审计（证顺序正确）。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            order_id, item_id = order.id, rows[0].id

            with patch("services.warehouse_stock_service.apply_stock_delta",
                       return_value=(False, "模拟库存写入失败")):
                resp = document_post(client,
                    f"/in_order/{order_id}/update_completed", json={
                        "items": [{"id": item_id, "quantity": 80, "price": 10}],
                        "deleted_items": [],
                        "reason": "测试回滚",
                    })
            assert resp.status_code == 400, resp.get_data(as_text=True)
            assert _audits(order_id) == [], "业务未提交就不应有审计"

    def test_T8_audit_call_after_commit(self):
        """结构断言：log_audit 必须在该函数的 commit 之后（防将来被前移）。"""
        src = ROUTE_SRC.read_text(encoding="utf-8")
        start = src.index("def update_completed_in_order(id):")
        end = src.index("def delete_in_order(id):")
        body = src[start:end]
        commit_at = body.index("db.session.commit()")
        audit_at = body.index(f"'{AUDIT_OP}', 'in_order'")
        assert audit_at > commit_at, (
            "log_audit 必须写在主 commit 之后：log_audit 内部自行 commit，"
            "前移会把半成品业务写提前落库"
        )
