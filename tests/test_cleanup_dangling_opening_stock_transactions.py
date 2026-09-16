# -*- coding: utf-8 -*-
"""「删除了就没有流水」回归（BUG-2026-09-16-007）。

背景：此前删除期初单据/明细行走"追加一条 quantity=-N 回冲流水"，明细行
物理删除后 +N/-N 流水仍留在 stock_transaction，库存台账继续显示单据编号
opening_stock-<id> 指向不存在明细行的记录（用户原话：期初库存被我删除了
怎么还有单据，搞得乱七八糟的）。修复分两路：
  1. 删除路径：_reverse_opening_stock_line 改为物理删除该行全部流水
     （建账 +N 与历次编辑差额），不再追加 -N 回冲流水——与入库单/出库单/
     调整单/售后出库单删除时清理自身流水的既有惯例一致；
  2. 历史数据：cleanup_dangling_opening_stock_transactions() 启动期无条件
     幂等清理「reference_type='opening_stock' 且 reference_id 已不在
     opening_stock 表」的悬挂流水；「新增物料初始库存」流水（reference_id
     是 material.id，remark='新增物料初始库存'）按 remark 排除不误删。

覆盖：
  - 悬挂 +N/-N 成对流水被清理、存世明细行流水保留
  - 新增物料初始库存流水（material.id 域）不误删
  - 其他 reference_type 流水不受影响；remark 为 NULL 的悬挂行也能清
  - 幂等：第二次执行 0 条；缺表/缺库文件静默跳过
  - 整单删除集成：库存回冲归零、流水物理清零、不新增负向流水
  - 启动接线：清理函数注册在 ensure_opening_stock_doc_table() 之后
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

_SCHEMA = """
CREATE TABLE opening_stock (
    id INTEGER PRIMARY KEY, material_id INTEGER, warehouse_id INTEGER,
    date DATE, quantity FLOAT DEFAULT 0
);
CREATE TABLE stock_transaction (
    id INTEGER PRIMARY KEY, material_id INTEGER, transaction_type VARCHAR(20),
    quantity FLOAT, location VARCHAR(100), warehouse_id INTEGER,
    reference_type VARCHAR(50), reference_id INTEGER, operator_id INTEGER,
    remark VARCHAR(200)
);
"""

# (reference_type, reference_id, quantity, remark)
_ROWS = (
    ("opening_stock", 1, 10.0, "期初库存调整"),        # 存世明细行 → 保留
    ("opening_stock", 99, 5.0, "期初库存调整"),        # 悬挂（明细行已删）→ 清
    ("opening_stock", 99, -5.0, "期初单据删除回冲"),   # 悬挂回冲流水 → 清
    ("opening_stock", 55, 8.0, None),                  # 悬挂且 remark NULL → 清
    ("opening_stock", 7, 3.0, "新增物料初始库存"),     # material.id 域 → 保留（误删防护）
    ("in_order", 99, 20.0, "采购入库"),                # 其他单据类型 → 保留
)


def _make_db(db_path: Path) -> Path:
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT INTO opening_stock (id, material_id, warehouse_id, date, quantity) "
            "VALUES (1, 1, 1, '2026-09-15', 10)")
        for rtype, rid, qty, remark in _ROWS:
            conn.execute(
                "INSERT INTO stock_transaction "
                "(material_id, transaction_type, quantity, reference_type, reference_id, remark) "
                "VALUES (1, 'opening', ?, ?, ?, ?)", (qty, rtype, rid, remark))
    return db_path


def _remaining(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT reference_type, reference_id, quantity, remark "
            "FROM stock_transaction ORDER BY id"
        ).fetchall()


# A9:no-test=reason=以下 test_ 函数即被测函数的回归测试本体


def test_dangling_transactions_removed_live_kept(tmp_path):
    """悬挂 +N/-N/NULL-remark 流水被清理；存世行、material.id 域、他类流水保留。"""
    from app import cleanup_dangling_opening_stock_transactions
    db_path = _make_db(tmp_path / "inventory.db")

    cleanup_dangling_opening_stock_transactions(db_path=str(db_path))

    assert _remaining(db_path) == [
        ("opening_stock", 1, 10.0, "期初库存调整"),
        ("opening_stock", 7, 3.0, "新增物料初始库存"),
        ("in_order", 99, 20.0, "采购入库"),
    ]


def test_idempotent_second_run(tmp_path):
    """存量清完后每次启动 0 条，重复执行不报错、数据不动。"""
    from app import cleanup_dangling_opening_stock_transactions
    db_path = _make_db(tmp_path / "inventory.db")
    cleanup_dangling_opening_stock_transactions(db_path=str(db_path))
    first = _remaining(db_path)
    cleanup_dangling_opening_stock_transactions(db_path=str(db_path))
    assert _remaining(db_path) == first


def test_missing_table_or_file_is_noop(tmp_path):
    """缺 stock_transaction/opening_stock 表或库文件不存在：静默返回。"""
    from app import cleanup_dangling_opening_stock_transactions
    # 缺 opening_stock 表
    db_path = tmp_path / "half.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("CREATE TABLE stock_transaction (id INTEGER PRIMARY KEY)")
    cleanup_dangling_opening_stock_transactions(db_path=str(db_path))
    # 库文件不存在
    ghost = tmp_path / "nonexistent" / "inventory.db"
    cleanup_dangling_opening_stock_transactions(db_path=str(ghost))
    assert not ghost.exists()


def test_startup_wiring_and_delete_semantics_static():
    """静态契约：清理函数注册在 ensure_opening_stock_doc_table() 之后；
    _reverse_opening_stock_line 已切换为物理删除流水（不再追加回冲流水）。"""
    src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    tbl_call = src.index("\nensure_opening_stock_doc_table()")
    clean_call = src.index("\ncleanup_dangling_opening_stock_transactions()")
    assert clean_call > tbl_call
    # 删除语义：物理删除该行流水
    assert "StockTransaction.query.filter_by(" in src
    assert "reference_id=line.id" in src
    # 旧的"追加回冲流水（remark=reason,）"代码实现不得复活
    assert "remark=reason," not in src
    # 清理 SQL 必须排除新增物料初始库存流水
    assert "新增物料初始库存" in src


class TestDocDeleteRemovesTransactions:
    """整单删除集成：库存全额回冲、流水物理清零、不新增负向流水。"""

    def setup_method(self):
        from app import app as flask_app
        from app import db as _db
        flask_app.config["TESTING"] = True
        flask_app.config["WTF_CSRF_ENABLED"] = False
        self.app = flask_app
        self.db = _db
        self.ctx = flask_app.app_context()
        self.ctx.push()
        # 全量 pytest 下与数十个测试模块共享内存库，引擎对所有连接强制
        # foreign_keys=ON（app.py:6062）；前置模块可能在任意 FK 引用表里
        # 留行，逐表 wipe 必然撞 FOREIGN KEY 约束（test_material_delete_missing_ai_table
        # 同款处理：drop_all + create_all 全量重建，免疫未知残留）。
        _db.drop_all()
        _db.create_all()

        from app import Material, Unit, User, Warehouse
        unit = Unit(code="PCS", name="个")
        _db.session.add(unit)
        _db.session.flush()
        self.wh = Warehouse(code="W1", name="一号仓", status="active")
        _db.session.add(self.wh)
        _db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0)
        self.m2 = Material(code="M002", name="螺母", unit_id=unit.id, stock=0)
        _db.session.add_all([self.m1, self.m2])
        from werkzeug.security import generate_password_hash
        _db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False))
        _db.session.commit()
        self.client = flask_app.test_client()
        self.client.post("/login",
                         data={"username": "admin", "password": "admin"},
                         content_type="application/x-www-form-urlencoded")

    def teardown_method(self):
        # 不做逐表 wipe：共享内存库里其它模块的表与行不归本类管，
        # 留少量无主数据（物料/仓库/单位/账号）对后续模块无害——后续模块
        # 要清场时自行 drop_all/create_all（test_material_delete_missing_ai_table 模式）。
        self.db.session.remove()
        self.ctx.pop()

    def test_doc_delete_removes_all_line_transactions(self):
        from app import Material, OpeningStock, OpeningStockDoc, StockTransaction
        resp = self.client.post("/opening_stock/save", json={
            "warehouse_id": self.wh.id, "date": "2026-09-16",
            "items": [
                {"material_id": self.m1.id, "warehouse_id": self.wh.id,
                 "quantity": 10, "price": 5},
                {"material_id": self.m2.id, "warehouse_id": self.wh.id,
                 "quantity": 20, "price": 2},
            ],
        })
        assert resp.status_code == 200, resp.get_json()
        doc_id = resp.get_json()["doc_id"]
        assert StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening").count() == 2
        neg_before = StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0).count()

        resp = self.client.post(f"/opening_stock/{doc_id}/delete")
        assert resp.status_code == 200, resp.data[:300]

        # 库存全额回冲；单据与明细物理删除
        self.db.session.expire_all()
        assert self.db.session.get(Material, self.m1.id).stock == 0.0
        assert self.db.session.get(Material, self.m2.id).stock == 0.0
        assert OpeningStock.query.count() == 0
        assert OpeningStockDoc.query.count() == 0
        # 删除了就没有流水：两行流水物理移除、无新增负向回冲流水
        assert StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening").count() == 0
        assert StockTransaction.query.filter(
            StockTransaction.transaction_type == "opening",
            StockTransaction.quantity < 0).count() == neg_before
