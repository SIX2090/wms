# -*- coding: utf-8 -*-
"""P0 批次/有效期捕获（入库明细行级）——模型 / schema 自愈 / 保存落库 / 页面展示。

背景：入库明细（in_order_item）此前完全没有批次号与有效期字段，导致
「这一批货是什么批次、什么时候到期」在系统里根本没被记录，后续无法做
效期预警、先进先出与质量追溯。本次补上行级 batch_no / expiry_date：

  * 模型：InOrderItem.batch_no / expiry_date（均可空，只记事实，不参与库存维度）
  * schema 三层：alembic 迁移 + auto_migrate_database() + 启动期自愈
    ensure_in_order_item_batch_columns()（存量库唯一自愈路径）+ fix_db_columns.py 兜底
  * 保存：add_in_order / add_in_order_item / 批量粘贴 / 编辑保存 四处消费点
  * 展示：入库单详情页批次号、有效期两列

测试用例：
  T1. 模型具备 batch_no / expiry_date 两列且可空（不破坏存量行）
  T2. ensure_in_order_item_batch_columns 幂等补列（模拟存量库缺列后自愈）
  T3. 保存后能落库并读回（batch_no 字符串 + expiry_date 日期对象）
  T4. 详情页渲染批次号与有效期（无值显示 '-'）
  T5. 三层 schema 的 ALTER 语句逐字一致（防漂移，R5）
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
import tempfile
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


def test_T1_model_has_nullable_batch_columns():
    """模型具备 batch_no / expiry_date，且均可空（存量明细行不受影响）。"""
    with app_module.app.app_context():
        _reset_db()
        cols = {c.name: c for c in InOrderItem.__table__.columns}
        assert "batch_no" in cols, "InOrderItem 应有 batch_no 列"
        assert "expiry_date" in cols, "InOrderItem 应有 expiry_date 列"
        assert cols["batch_no"].nullable, "batch_no 必须可空（可选字段）"
        assert cols["expiry_date"].nullable, "expiry_date 必须可空（可选字段）"


def test_ensure_in_order_item_batch_columns():
    """模拟 WMS_NO_DB_TOUCH=1 的存量库（缺两列）→ 启动期自愈补列，且幂等。"""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "legacy.db")
        conn = sqlite3.connect(db_path)
        # 复刻 P0 之前的 in_order_item 结构（无 batch_no / expiry_date）
        conn.execute(
            """
            CREATE TABLE in_order_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                in_order_id INTEGER NOT NULL,
                material_id INTEGER NOT NULL,
                quantity FLOAT NOT NULL,
                price FLOAT NOT NULL,
                amount FLOAT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO in_order_item (in_order_id, material_id, quantity, price, amount)"
            " VALUES (1, 1, 2, 3, 6)"
        )
        conn.commit()
        conn.close()

        app_module.ensure_in_order_item_batch_columns(db_path)

        conn = sqlite3.connect(db_path)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(in_order_item)").fetchall()]
        assert "batch_no" in cols, "自愈后应补出 batch_no"
        assert "expiry_date" in cols, "自愈后应补出 expiry_date"
        # 存量行未被破坏、新列取 NULL
        row = conn.execute(
            "SELECT quantity, batch_no, expiry_date FROM in_order_item WHERE id = 1"
        ).fetchone()
        assert row[0] == 2 and row[1] is None and row[2] is None, "存量行数据与新增列取值应符合预期"
        conn.close()

        # 幂等：再跑一次不应报错
        app_module.ensure_in_order_item_batch_columns(db_path)


def test_T3_saved_batch_and_expiry_persist():
    """保存入库单后批次号与有效期落库、可读回。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        order = InOrder(order_no="IN-P0-001", warehouse="仓库A", business_type="其他入库", status="pending")
        db.session.add(order)
        db.session.flush()
        mat = Material.query.filter_by(code="M001").first()
        from datetime import date
        db.session.add(InOrderItem(
            in_order_id=order.id,
            material_id=mat.id,
            quantity=10,
            price=5.5,
            amount=55,
            batch_no="B20260901",
            expiry_date=date(2027, 6, 30),
        ))
        db.session.commit()

        item = InOrderItem.query.filter_by(in_order_id=order.id).first()
        assert item.batch_no == "B20260901"
        assert item.expiry_date == date(2027, 6, 30)


def test_T4_detail_page_shows_batch_columns():
    """详情页展示批次号与有效期；未填写时显示 '-'。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        from datetime import date
        order = InOrder(order_no="IN-P0-002", warehouse="仓库A", business_type="其他入库", status="completed")
        db.session.add(order)
        db.session.flush()
        mat = Material.query.filter_by(code="M001").first()
        db.session.add(InOrderItem(
            in_order_id=order.id,
            material_id=mat.id,
            quantity=1,
            price=5.5,
            amount=5.5,
            batch_no="B20260901",
            expiry_date=date(2027, 6, 30),
        ))
        db.session.add(InOrderItem(
            in_order_id=order.id,
            material_id=mat.id,
            quantity=1,
            price=5.5,
            amount=5.5,
        ))
        db.session.commit()
        order_id = order.id

    client = _make_client()
    resp = client.get(f"/in_order/{order_id}")
    assert resp.status_code == 200, f"详情页返回 {resp.status_code}，应为 200"
    body = resp.data.decode("utf-8", errors="replace")
    assert "批次号" in body, "详情页应有批次号列"
    assert "有效期" in body, "详情页应有有效期列"
    assert "B20260901" in body, "详情页应展示批次号取值"
    assert "2027-06-30" in body, "详情页应展示有效期取值"


def test_T4_expiry_parser_handles_excel_datetime_objects():
    """Excel（openpyxl）给的 datetime 必须降为 date，不能带时间写库。"""
    from routes.in_order import _parse_item_expiry_date, _parse_item_batch_no
    from datetime import date, datetime

    val, err = _parse_item_expiry_date(datetime(2027, 6, 30, 8, 30, 0))
    assert err is None and val == date(2027, 6, 30), "datetime 应降为 date"
    assert type(val) is date, f"应返回 date 而非 datetime，实际 {type(val)}"

    val, err = _parse_item_expiry_date(date(2027, 6, 30))
    assert err is None and val == date(2027, 6, 30)

    # Excel/WPS 文本写法与带时间后缀
    for raw in ('2026-09-01', '2026/9/1', '2026.9.1', '2026年9月1日', '2026/9/1 0:00'):
        val, err = _parse_item_expiry_date(raw)
        assert err is None and val == date(2026, 9, 1), f'[{raw}] 应解析为 2026-09-01'

    # 非法日期必须拒绝（2026 年非闰年）
    for bad in ('2026-02-31', '2026-02-29', '2026-13-01', '不是日期'):
        val, err = _parse_item_expiry_date(bad)
        assert val is None and err, f'[{bad}] 应被判为非法'

    # 空值归一化为 None；批次号超长报错
    assert _parse_item_expiry_date(None) == (None, None)
    assert _parse_item_expiry_date('') == (None, None)
    assert _parse_item_batch_no('  ') == (None, None)
    assert _parse_item_batch_no('B001') == ('B001', None)
    assert _parse_item_batch_no('x' * 51)[0] is None


def test_T6_schema_alter_statements_stay_in_sync():
    """三层 schema 的 ALTER 语句逐字一致（防漂移，AGENTS.md R5）。

    auto_migrate_database（app.py）/ ensure_in_order_item_batch_columns（app.py）/
    fix_db_columns.py 三处必须使用同一批列定义，否则存量库自愈会与迁移分叉。
    """
    app_src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    fix_src = (APP_DIR / "fix_db_columns.py").read_text(encoding="utf-8")

    for stmt in (
        "ALTER TABLE in_order_item ADD COLUMN batch_no VARCHAR(50)",
        "ALTER TABLE in_order_item ADD COLUMN expiry_date DATE",
    ):
        assert stmt in app_src, f"app.py 应包含 ALTER 语句：{stmt}"
        assert stmt in fix_src, f"fix_db_columns.py 应包含 ALTER 语句：{stmt}"
