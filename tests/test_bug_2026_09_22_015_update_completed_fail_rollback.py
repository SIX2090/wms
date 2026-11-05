# -*- coding: utf-8 -*-
"""BUG-2026-09-22-015 回归：编辑已完成入库单，任何校验失败必须整体回滚。

事故根因（R6 同模式：既有局部修复未覆盖全量出口）：

``routes/in_order.py::update_completed_in_order`` 在 try 块内是
「**边写边校验**」的顺序：

  1. 先做删除明细回退（``apply_stock_delta`` 取负）→ 库存已落账；
  2. 再做已有行的数量/单价调整（``apply_stock_delta`` 取带符号 delta
     → ``item.quantity`` / ``item.price`` / ``item.amount`` 已改）；
  3. **之后**才做行级批次号 / 有效期格式校验
     （``_parse_item_batch_no`` / ``_parse_item_expiry_date``）。

而 ``api_error``（``app/app.py:205``）的实现是
``return jsonify({'status': 'error', 'msg': msg}), code``——**只返回 JSON，
不做 ``db.session.rollback()``**。于是第 3 步报错的同一个请求里，第 1、2 步
的库存变动与明细改动**留在未提交事务中**：

  - 请求返回 400「保存失败」，用户以为没存，实际会话里的改动仍在；
  - 一旦该未提交事务在后续（同请求内的其它写操作、连接复用、会话清理
    前的任意一次 commit）被提交，就变成**报错单却改了库存**的静默脏数据，
    典型表现是「明细数量没变，但总库存变了」。

修复前的覆盖率是 **3/20**：本函数 20 个错误出口里只有 3 个手写了
``db.session.rollback()``（逐个补的历史遗留），新增校验一律漏。故本次不
逐个补，而是在函数内定义统一出口 ``fail()``：

    def fail(message, code=400):
        db.session.rollback()
        return api_error(message, code)

并把本函数所有错误 ``return`` 一律改为 ``return fail(...)``，以结构性手段
保证「将来新增校验也不会漏」。原 3 处手写 rollback 随之收敛删除（避免重复
rollback）。

测试策略（先写红、注入缺陷验证、再转绿）：

  T1. 核心：已有行提交**非法批次号**（>50 字符）→ 接口报错，且
      ``item.quantity`` 与 ``material.stock`` **都**必须保持原值。
      修复前此用例必红：数量与库存已改，只是返回了 400。
  T2. 同上，非法**有效期**格式（"not-a-date"）走另一分支，同样要求整体回滚。
  T3. 删除明细在「后续行校验失败」时也必须回滚——明细不得被删掉。
  T4. 成功路径不受影响：合法批次号/有效期编辑照常提交并落库。
  T5. 结构断言：函数内不得再出现裸 ``return api_error(...)``（除 fail 自身
      实现外），防止将来又加回一个漏 rollback 的出口。

用例注意（R7）：``api_error`` 返回 400 时响应体是 JSON，需用
``get_json(silent=True)`` 取值；SQLAlchemy 会话内对象在 rollback 后会被
expire，断言前需 ``db.session.expire(...)`` 或 ``db.session.refresh(...)``
从库中重新读，否则读到的是内存里被改过的脏值而非库值。
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
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
    InOrder, InOrderItem,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ROUTE_SRC = APP_DIR / "routes" / "in_order.py"

# 非法批次号：>50 字符，命中 _parse_item_batch_no 的「批次号不能超过 50 个字符」
BAD_BATCH_NO = "B" * 51
# 非法有效期：三段式但月/日越界，命中 _parse_item_expiry_date 中文错误提示
BAD_EXPIRY_DATE = "not-a-date"


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
    client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
    )
    return client


def _make_completed_in_order(mat, qty=50, items=None):
    """创建一张已完成的入库单。

    ``items`` 为 None 时建单行（数量 qty）；否则按 [(qty, price), ...] 建多行。
    ``mat.stock`` 已在 _seed 中置为 100，对应首行数量，故库存基线取 100。
    """
    order = InOrder(
        order_no="IN-ROLLBACK-001",
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


def _db_item(item_id):
    """从库中重新读明细（rollback 后内存对象已 expire，需绕过身份映射）。"""
    db.session.expire_all()
    return db.session.get(InOrderItem, item_id)


def _db_stock(mat_id):
    db.session.expire_all()
    return db.session.get(Material, mat_id).stock


def _db_item_ids(order_id):
    db.session.expire_all()
    return sorted(r.id for r in InOrderItem.query.filter_by(in_order_id=order_id).all())


class TestBug20260922015FailRollsBack:
    """任何校验失败都不得留下库存/明细的半成品改动。"""

    def test_T1_bad_batch_no_leaves_quantity_and_stock_untouched(self):
        """非法批次号：明细数量与库存都必须保持原值（修复前二者已改）。

        这是本 BUG 的核心复现：请求体把数量从 50 改到 80，同时把批次号写成
        51 个字符。数量调整（apply_stock_delta +30）先执行，批次号校验后执行
        并报错——修复前库存变 130、明细变 80，只是返回了 400。
        """
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            item = rows[0]
            item_id, mat_id = item.id, seeds["mat"].id
            stock_before = _db_stock(mat_id)
            qty_before = _db_item(item_id).quantity

            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{
                    "id": item_id,
                    "quantity": 80,
                    "price": 10,
                    "batch_no": BAD_BATCH_NO,
                }],
                "deleted_items": [],
            })
            body = resp.get_json(silent=True) or {}
            assert resp.status_code == 400, f"非法批次号应被判为 400，实际 {resp.status_code}"
            assert body.get("status") == "error", f"应返回 error：{body}"
            assert "批次号" in body.get("msg", ""), f"错误提示应指向批次号：{body}"

            assert _db_item(item_id).quantity == qty_before, (
                "报错请求后明细数量被改了——校验失败未回滚（BUG-2026-09-22-015 复发）"
            )
            assert _db_stock(mat_id) == stock_before, (
                f"报错请求后库存被改了（{stock_before} → {_db_stock(mat_id)}）——"
                "库存调整发生在批次号校验之前且未回滚（BUG-2026-09-22-015 复发）"
            )

    def test_T2_bad_expiry_date_leaves_quantity_and_stock_untouched(self):
        """非法有效期：走另一校验分支，同样要求整体回滚。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], qty=50)
            item = rows[0]
            item_id, mat_id = item.id, seeds["mat"].id
            stock_before = _db_stock(mat_id)
            qty_before = _db_item(item_id).quantity

            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{
                    "id": item_id,
                    "quantity": 80,
                    "price": 10,
                    "expiry_date": BAD_EXPIRY_DATE,
                }],
                "deleted_items": [],
            })
            body = resp.get_json(silent=True) or {}
            assert resp.status_code == 400, f"非法有效期应被判为 400，实际 {resp.status_code}"
            assert "有效期" in body.get("msg", ""), f"错误提示应指向有效期：{body}"

            assert _db_item(item_id).quantity == qty_before, (
                "报错请求后明细数量被改了——有效期校验失败未回滚"
            )
            assert _db_stock(mat_id) == stock_before, (
                f"报错请求后库存被改了（{stock_before} → {_db_stock(mat_id)}）——"
                "有效期校验失败未回滚"
            )

    def test_T3_deleted_item_survives_later_validation_failure(self):
        """先删明细、后撞校验失败：被删的明细必须还在，库存也不得回退。

        覆盖另一个错序场景：``deleted_items`` 循环在 ``items`` 循环之前执行，
        前者已 ``apply_stock_delta`` 取负回退库存并 ``db.session.delete(item)``，
        之后 items 循环里的非法批次号才报错——若不回滚，明细凭空消失。
        """
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            client = _make_client()
            order, rows = _make_completed_in_order(seeds["mat"], items=[(50, 10), (20, 10)])
            first, second = rows[0], rows[1]
            first_id, second_id, mat_id = first.id, second.id, seeds["mat"].id
            ids_before = _db_item_ids(order.id)
            stock_before = _db_stock(mat_id)

            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{
                    "id": second_id,
                    "quantity": 30,
                    "price": 10,
                    "batch_no": BAD_BATCH_NO,
                }],
                "deleted_items": [first_id],
            })
            body = resp.get_json(silent=True) or {}
            assert resp.status_code == 400 and body.get("status") == "error", (
                f"非法批次号应报错：{resp.status_code} {body}"
            )

            assert _db_item_ids(order.id) == ids_before, (
                "报错请求后被删明细没有回来——删除回退未随校验失败回滚"
            )
            assert _db_stock(mat_id) == stock_before, (
                f"报错请求后库存被改了（{stock_before} → {_db_stock(mat_id)}）——"
                "删除回退未随校验失败回滚"
            )

    def test_T4_valid_edit_still_commits(self):
        """成功路径不受影响：合法批次号/有效期编辑照常落库、库存同步。"""
        with app_module.app.app_context():
            _reset_db()
            _seed()
            client = _make_client()
            mat = Material.query.filter_by(code="M001").one()
            order, rows = _make_completed_in_order(mat, qty=50)
            item = rows[0]
            item_id, mat_id = item.id, mat.id
            stock_before = _db_stock(mat_id)

            resp = client.post(f"/in_order/{order.id}/update_completed", json={
                "items": [{
                    "id": item_id,
                    "quantity": 80,
                    "price": 10,
                    "batch_no": "B20260922",
                    "expiry_date": "2027-01-31",
                }],
                "deleted_items": [],
            })
            body = resp.get_json(silent=True) or {}
            assert resp.status_code == 200 and body.get("status") == "success", (
                f"合法编辑应成功：{resp.status_code} {body}"
            )

            saved = _db_item(item_id)
            assert saved.quantity == 80, f"数量应落库为 80，实际 {saved.quantity}"
            assert saved.batch_no == "B20260922", f"批次号应落库，实际 {saved.batch_no!r}"
            assert saved.expiry_date == date(2027, 1, 31), (
                f"有效期应落库为 2027-01-31，实际 {saved.expiry_date!r}"
            )
            assert _db_stock(mat_id) == stock_before + 30, (
                f"库存应 +30（{stock_before} → {_db_stock(mat_id)}）"
            )

    def test_T5_no_bare_api_error_remains_in_route(self):
        """结构断言：update_completed_in_order 内不得再有裸 ``api_error`` 出口。

        本 BUG 的成因是「逐个出口手写 rollback」这种修法必然漏；改用统一
        ``fail()`` 出口后，任何新加回 ``return api_error(...)`` 的写法都会
        让本用例变红，从而挡住回归。
        """
        src = ROUTE_SRC.read_text(encoding="utf-8")
        start = src.index("def update_completed_in_order(id):")
        end = src.index("def delete_in_order(id):", start)
        body = src[start:end]

        assert "def fail(message, code=400):" in body, (
            "update_completed_in_order 内应有统一失败出口 fail()"
        )
        # fail 自身实现里是允许出现 api_error 的唯一位置。
        # 注意：正则不能写成 ``def fail\(message, code=400\):\n``——def 行尾可能
        # 挂 ``# no-test:reason=...`` 等注释，会漏匹配。这里用宽松签名 + 函数体
        # 到下一个空行为止的取法。
        stub = re.search(r"def fail\(message[^\n]*\n(.*?)\n\n", body, re.S)
        assert stub, "未找到 fail() 函数体"
        assert "db.session.rollback()" in stub.group(1), (
            "fail() 必须先回滚再返回"
        )
        assert "return api_error(message, code)" in stub.group(1), (
            "fail() 内部应调用 api_error 生成响应"
        )
        body = body.replace(stub.group(0), "")

        # 进入 try 块之前的状态闸门无需回滚（此时本请求还没有任何写操作），
        # 保留裸 api_error 是刻意的；本用例的断言范围从 try 起算。
        try_at = body.index("        try:\n")
        risk_zone = body[try_at:]

        # 反向护栏：进入 try 后所有错误出口都经 fail()，数量应保持有意义量级
        assert risk_zone.count("return fail(") >= 20, (
            f"经 fail() 的出口数异常偏少（{risk_zone.count('return fail(')}）——"
            "可能有出口被误删或改回裸 api_error"
        )
        offenders = [
            ln.strip()
            for ln in risk_zone.splitlines()
            if "return api_error(" in ln and not ln.strip().startswith("#")
        ]
        assert not offenders, (
            "update_completed_in_order 的 try 块内仍存在裸 return api_error(...) 出口——"
            "该出口不会回滚，会再次产生 BUG-2026-09-22-015 型脏数据：" + repr(offenders)
        )
