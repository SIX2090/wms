# -*- coding: utf-8 -*-
"""BUG-2026-09-21-003 回归：编辑草稿/自动草稿恢复不得丢失行级批次号与有效期。

事故经过：d0c53730（2026-09-19，入库明细新增批次号/有效期捕获）只覆盖了
「新增录入 → 保存落库」路径，漏了三条**回填**路径：

  1. ``routes/in_order.py`` 的 ``edit_items``（编辑草稿时服务端下发给页面的
     明细载荷）没有 batch_no / expiry_date；
  2. ``in_order_add.html`` DOMContentLoaded 的 editItems 回填循环不填
     ``.material-batch-no`` / ``.material-expiry``；
  3. 同页 localStorage 自动草稿（30s 一次）的 collectFormData / restoreDraft
     同样不收不恢。

而编辑保存的实现是「**整批删除旧明细 → 按页面提交重建**」
（add_in_order JSON 分支，order.items 逐条 delete 后按 items_data 新建），
所以草稿重开再保存 = 已录的批次号/有效期被**静默清空**（数据不可恢复）。
对照组：P1-7 出库侧 edit_items 回填 source_in_order_item_id 时就处理过
同一问题（见 routes/out_order.py 注释），入库侧属同根因漏改（R6）。

测试用例（context 用法符合 A12/R7）：
  T1. 编辑页内联的 edit_items 载荷必须携带 batch_no / expiry_date；
  T2. 模板 editItems 回填循环必须写 .material-batch-no / .material-expiry；
  T3. localStorage 草稿 collectFormData 必须收、restoreDraft 必须恢两字段；
  T4. 端到端：草稿含批次/有效期 → 打开编辑页 → 按页面载荷原样回存 →
      数据库中两字段保持不变（修复前此用例必红：载荷无两字段 → 重建后为 NULL）。
"""
from __future__ import annotations

import json
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
from app import db, Warehouse, User, Material, InOrder, InOrderItem  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TPL = ROOT / "app" / "templates" / "in_order_add.html"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    mat = Material(code="M001", name="测试物料", spec="S1", unit_id=None, price=5.5, stock=0)
    db.session.add_all([wh, user, mat])
    db.session.commit()


def _make_client():
    client = app_module.app.test_client()
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _make_draft_with_batch():
    _reset_db()
    _seed()
    order = InOrder(
        order_no="IN-EDIT-001", warehouse="仓库A",
        business_type="其他入库", status="pending",
    )
    db.session.add(order)
    db.session.flush()
    mat = Material.query.filter_by(code="M001").first()
    item = InOrderItem(
        in_order_id=order.id, material_id=mat.id,
        quantity=3, price=5.5, amount=16.5,
        batch_no="B20260921", expiry_date=date(2027, 1, 31),
    )
    db.session.add(item)
    db.session.commit()
    return order.id


def _extract_edit_items(html: str):
    m = re.search(r"const editItems = (\[.*?\]);", html, re.S)
    assert m, "编辑页应内联 editItems（{{ edit_items | tojson }}）"
    return json.loads(m.group(1))


def test_T1_edit_items_payload_carries_batch_and_expiry():
    """编辑页下发的 edit_items 必须携带批次号/有效期（缺失=再保存即清空）。"""
    with app_module.app.app_context():
        oid = _make_draft_with_batch()
        client = _make_client()
        html = client.get(f"/in_order/add?order_id={oid}").get_data(as_text=True)
        items = _extract_edit_items(html)
        assert len(items) == 1
        assert items[0].get("batch_no") == "B20260921", (
            f"edit_items 缺 batch_no（实际键：{sorted(items[0].keys())}）"
        )
        assert items[0].get("expiry_date") == "2027-01-31", (
            f"edit_items 缺 expiry_date 或格式不是 YYYY-MM-DD：{items[0].get('expiry_date')!r}"
        )


def test_T2_template_repopulation_fills_batch_and_expiry_inputs():
    """editItems 回填循环必须写 .material-batch-no / .material-expiry。"""
    src = TPL.read_text(encoding="utf-8")
    m = re.search(r"editItems\.forEach\(\(item\) => \{(.*?)\}\);", src, re.S)
    assert m, "未找到 editItems.forEach 回填循环"
    loop = m.group(1)
    assert ".material-batch-no" in loop, "回填循环未写 .material-batch-no"
    assert ".material-expiry" in loop, "回填循环未写 .material-expiry"


def test_T3_localstorage_draft_collects_and_restores_batch_and_expiry():
    """自动草稿：collectFormData 必须收 batch_no/expiry_date，restoreDraft 必须恢。"""
    src = TPL.read_text(encoding="utf-8")
    collect = re.search(r"function collectFormData\(\) \{(.*?)\n    \}", src, re.S)
    assert collect, "未找到 collectFormData"
    assert "material-batch-no" in collect.group(1), "草稿收集漏了批次号"
    assert "material-expiry" in collect.group(1), "草稿收集漏了有效期"
    restore = re.search(r"function restoreDraft\(\) \{(.*?)\n    \}", src, re.S)
    assert restore, "未找到 restoreDraft"
    assert "rowData.batch_no" in restore.group(1), "草稿恢复漏了批次号"
    assert "rowData.expiry_date" in restore.group(1), "草稿恢复漏了有效期"


def test_T4_edit_resave_preserves_batch_and_expiry_end_to_end():
    """端到端：打开编辑页 → 按页面载荷原样回存 → 批次/有效期不得丢失。"""
    with app_module.app.app_context():
        oid = _make_draft_with_batch()
        client = _make_client()
        html = client.get(f"/in_order/add?order_id={oid}").get_data(as_text=True)
        edit_items = _extract_edit_items(html)
        it = edit_items[0]
        # 模拟浏览器：页面回填后用户原样点保存（页面提交字段名是 code/quantity/...）
        resp = client.post("/in_order/add", json={
            "order_id": oid,
            "order_no": "IN-EDIT-001",
            "business_type": "其他入库",
            "warehouse": "仓库A",
            "items": [{
                "code": it["material_code"],
                "quantity": it["quantity"],
                "price": it["price"],
                "batch_no": it.get("batch_no", ""),
                "expiry_date": it.get("expiry_date", ""),
                "contract_no": it.get("contract_no", ""),
                "project_name": it.get("project_name", ""),
                "remark": it.get("remark", ""),
            }],
        })
        body = resp.get_json(silent=True) or {}
        assert resp.status_code == 200 and body.get("status") == "success", (
            f"编辑保存失败：{resp.status_code} {body}"
        )
        row = InOrderItem.query.filter_by(in_order_id=oid).one()
        assert row.batch_no == "B20260921", (
            f"编辑再保存后批次号丢失（现为 {row.batch_no!r}）——BUG-2026-09-21-003 复发"
        )
        assert row.expiry_date is not None and row.expiry_date.isoformat() == "2027-01-31", (
            f"编辑再保存后有效期丢失（现为 {row.expiry_date!r}）"
        )
