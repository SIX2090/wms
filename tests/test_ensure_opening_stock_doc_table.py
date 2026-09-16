# -*- coding: utf-8 -*-
"""ensure_opening_stock_doc_table 回归测试（BUG-2026-09-16-006）。

背景：ARCH-OS-DOC-01 期初库存多单据化引入单据头表 opening_stock_doc，
建表只在 db.create_all() / auto_migrate_database()（Step 1），历史行归单
只在 auto_migrate_database()（Step 5）。start_wms_offline.bat /
start_wms_auto.bat 默认 WMS_NO_DB_TOUCH=1 会把迁移整体跳过；
ensure_opening_stock_doc_columns() 只补 opening_stock.doc_id **列**、没建
**表**——「功能上线前建的存量库 + WMS_NO_DB_TOUCH=1 重启」叠加态下表根本
不存在，打开期初库存单据列表 /opening_stock 即抛
no such table: opening_stock_doc → 500（2026-09-16 生产实测，
opening_stock.py:54 paginate 处）。R6 同根因：BUG-2026-08-22-001
（excel_print_template 表）、BUG-2026-09-12（department 表）。

修复：app.py 新增 ensure_opening_stock_doc_table()，独立 sqlite 连接、
独立于迁移开关无条件执行、幂等——建表 DDL 与历史回填复用
auto_migrate_database() 抽出的公共函数（_create_opening_stock_doc_table /
_backfill_opening_stock_docs），两处同一实现防口径漂移（R6）。

覆盖：
- 缺表补建：列与模型一致、4 个索引齐全、doc_id 列顺带兜底
- 历史回填：按 (建账日期, 仓库) 归单、单号 QS+YYMM+4位、date NULL 不归单、
  只加归属不改账（quantity/price/amount 不动）
- 原 500 查询（列表页 ORDER BY created_at DESC LIMIT 分页）恢复可用
- 幂等：重复执行不重复建单、数据不动
- 已有表/全新库/库文件不存在三种边界
- 接线：子进程 `import app` + WMS_NO_DB_TOUCH=1 模拟生产启动，缺表被补建
  且历史被归单（本次线上真 bug 的完整复现场景）
- 防漂移：auto_migrate 与 ensure 共用同一公共函数（静态断言）
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

DOC_COLUMNS = (
    "id", "doc_no", "date", "warehouse_id", "status", "remark",
    "operator_id", "created_at", "updated_at",
)
DOC_INDEXES = (
    "idx_opening_stock_doc_no", "idx_opening_stock_doc_date",
    "idx_opening_stock_doc_warehouse", "idx_opening_stock_doc_created",
)

# 模拟老库：opening_stock 带 AI-OS-MW-001 全局唯一约束，无 doc_id 列、无单据头表
_LEGACY_SCHEMA = """
CREATE TABLE material (
    id INTEGER PRIMARY KEY, code VARCHAR(50), name VARCHAR(200),
    stock FLOAT DEFAULT 0, spec VARCHAR(200), price FLOAT DEFAULT 0
);
CREATE TABLE warehouse (
    id INTEGER PRIMARY KEY, code VARCHAR(50), name VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active', is_default BOOLEAN DEFAULT 0
);
CREATE TABLE user (
    id INTEGER PRIMARY KEY, username VARCHAR(80), password_hash VARCHAR(200)
);
CREATE TABLE opening_stock (
    id INTEGER PRIMARY KEY,
    material_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    date DATE,
    location VARCHAR(100) NOT NULL DEFAULT '',
    quantity FLOAT NOT NULL DEFAULT 0,
    price FLOAT NOT NULL DEFAULT 0,
    amount FLOAT NOT NULL DEFAULT 0,
    remark VARCHAR(500),
    operator_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uix_opening_stock_material_warehouse UNIQUE (material_id, warehouse_id)
);
"""

# (material_id, warehouse_id, date, quantity, price, amount)
_LEGACY_ROWS = (
    (1, 1, '2026-09-01', 10, 2.0, 20.0),   # M001 主仓 09-01 ┐ 同一张单
    (2, 1, '2026-09-01', 5, 1.0, 5.0),     # M002 主仓 09-01 ┘
    (1, 2, '2026-09-01', 7, 2.0, 14.0),    # M001 副仓 09-01 → 另一张单
    (2, 2, '2026-09-05', 3, 1.0, 3.0),     # M002 副仓 09-05 → 第三张单
    (3, 1, None, 1, 9.0, 9.0),             # M003 主仓 无日期 → 不归单
)


def _make_legacy_db(db_path: Path) -> Path:
    """造一个功能上线前的存量老库：有 opening_stock 数据、无 opening_stock_doc。"""
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(_LEGACY_SCHEMA)
        for mid, code, name in ((1, 'M001', '螺栓'), (2, 'M002', '螺母'), (3, 'M003', '垫片')):
            conn.execute(
                "INSERT INTO material (id, code, name, stock, spec, price) "
                "VALUES (?,?,?,'0','M8',1.0)", (mid, code, name))
        for wid, code, name in ((1, 'WH001', '主仓'), (2, 'WH002', '副仓')):
            conn.execute(
                "INSERT INTO warehouse (id, code, name, status) VALUES (?,?,?,'active')",
                (wid, code, name))
        for mid, wid, d, qty, price, amount in _LEGACY_ROWS:
            conn.execute(
                "INSERT INTO opening_stock "
                "(material_id, warehouse_id, date, quantity, price, amount) "
                "VALUES (?,?,?,?,?,?)", (mid, wid, d, qty, price, amount))
    return db_path


def _table_exists(db_path: Path, name: str) -> bool:
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone() is not None


def _cols(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _indexes(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        return [r[1] for r in conn.execute(f"PRAGMA index_list({table})").fetchall()]


def _docs_with_lines(db_path: Path):
    """返回 [(doc_no, date, warehouse_id, line_count)]，按单号排序。"""
    with sqlite3.connect(db_path) as conn:
        return conn.execute(
            "SELECT d.doc_no, d.date, d.warehouse_id, "
            "       (SELECT COUNT(*) FROM opening_stock s WHERE s.doc_id = d.id) "
            "FROM opening_stock_doc d ORDER BY d.doc_no"
        ).fetchall()


# A9:no-test=reason=以下 test_ 函数即被测函数的回归测试本体


def test_missing_table_created_and_history_backfilled(tmp_path):
    """存量老库缺 opening_stock_doc：补建表 + doc_id 列兜底 + 按 (日期,仓库) 归单。"""
    from app import ensure_opening_stock_doc_table
    db_path = _make_legacy_db(tmp_path / "inventory.db")
    assert not _table_exists(db_path, "opening_stock_doc")

    ensure_opening_stock_doc_table(db_path=str(db_path))

    # 1) 表已建，列与模型一致、索引齐全
    assert _table_exists(db_path, "opening_stock_doc")
    for expected in DOC_COLUMNS:
        assert expected in _cols(db_path, "opening_stock_doc"), f"缺列: {expected}"
    for expected in DOC_INDEXES:
        assert expected in _indexes(db_path, "opening_stock_doc"), f"缺索引: {expected}"

    # 2) doc_id 列顺带兜底（与 ensure_opening_stock_doc_columns 同口径）
    assert "doc_id" in _cols(db_path, "opening_stock")
    assert "idx_opening_stock_doc" in _indexes(db_path, "opening_stock")

    # 3) 按 (建账日期, 仓库) 归成 3 张单，单号 QS+YYMM+4位 顺序递增
    docs = _docs_with_lines(db_path)
    assert docs == [
        ("QS26090001", "2026-09-01", 1, 2),   # 主仓 09-01 两行归一张单
        ("QS26090002", "2026-09-01", 2, 1),   # 副仓 09-01 单独一张单
        ("QS26090003", "2026-09-05", 2, 1),   # 副仓 09-05 单独一张单
    ]

    # 4) date 为 NULL 的行保守不归单，留 doc_id 为 NULL 等人工处理
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT doc_id FROM opening_stock WHERE material_id = 3"
        ).fetchone() == (None,)

    # 5) 只加归属不改账：quantity/price/amount 一律不动
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT material_id, warehouse_id, quantity, price, amount "
            "FROM opening_stock ORDER BY id"
        ).fetchall()
    assert rows == [(r[0], r[1], r[3], r[4], r[5]) for r in _LEGACY_ROWS]


def test_original_500_list_query_now_works(tmp_path):
    """原报错 SQL（列表页分页查询）不再抛 no such table: opening_stock_doc。"""
    from app import ensure_opening_stock_doc_table
    db_path = _make_legacy_db(tmp_path / "inventory.db")
    ensure_opening_stock_doc_table(db_path=str(db_path))
    with sqlite3.connect(db_path) as conn:
        # 与 routes/opening_stock.py opening_stock_list 的 ORM 分页同形态
        rows = conn.execute(
            "SELECT id, doc_no, date, warehouse_id, status, remark, "
            "operator_id, created_at, updated_at FROM opening_stock_doc "
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?", (20, 0)
        ).fetchall()
    assert len(rows) == 3


def test_idempotent_repeat_run(tmp_path):
    """重复执行不重复建单、不重复回填，已有归属一律不动。"""
    from app import ensure_opening_stock_doc_table
    db_path = _make_legacy_db(tmp_path / "inventory.db")
    ensure_opening_stock_doc_table(db_path=str(db_path))
    first = _docs_with_lines(db_path)
    with sqlite3.connect(db_path) as conn:
        assigned_first = conn.execute(
            "SELECT id, doc_id FROM opening_stock ORDER BY id").fetchall()

    ensure_opening_stock_doc_table(db_path=str(db_path))
    ensure_opening_stock_doc_table(db_path=str(db_path))

    assert _docs_with_lines(db_path) == first
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM opening_stock_doc").fetchone()[0] == 3
        assert conn.execute(
            "SELECT id, doc_id FROM opening_stock ORDER BY id").fetchall() == assigned_first


def test_existing_table_and_assigned_rows_untouched(tmp_path):
    """表已存在且历史已归单时静默跳过，结构与数据一律不动。"""
    from app import ensure_opening_stock_doc_table
    db_path = _make_legacy_db(tmp_path / "inventory.db")
    ensure_opening_stock_doc_table(db_path=str(db_path))
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE opening_stock_doc SET remark = '人工修改过的备注' WHERE doc_no = 'QS26090001'")
    before = _docs_with_lines(db_path)

    ensure_opening_stock_doc_table(db_path=str(db_path))

    assert _docs_with_lines(db_path) == before
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT remark FROM opening_stock_doc WHERE doc_no = 'QS26090001'"
        ).fetchone() == ("人工修改过的备注",)


def test_fresh_db_without_opening_stock_creates_empty_table(tmp_path):
    """全新库（无 opening_stock）：只建空单据头表，不报错、不造单。"""
    from app import ensure_opening_stock_doc_table
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(
            "CREATE TABLE warehouse (id INTEGER PRIMARY KEY, code TEXT, name TEXT);"
            "CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT);"
        )
    ensure_opening_stock_doc_table(db_path=str(db_path))
    assert _table_exists(db_path, "opening_stock_doc")
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM opening_stock_doc").fetchone()[0] == 0


def test_missing_db_file_is_noop(tmp_path):
    """库文件不存在（全新部署未建库）：静默返回，交由 create_all 建全量表。"""
    from app import ensure_opening_stock_doc_table
    db_path = tmp_path / "nonexistent" / "inventory.db"
    ensure_opening_stock_doc_table(db_path=str(db_path))  # 不应抛异常
    assert not db_path.exists()


def test_migration_and_ensure_share_same_helpers():
    """防 R6 漂移：建表 DDL 与历史回填在仓库内只有一份实现，
    auto_migrate_database 与 ensure_opening_stock_doc_table 共用。"""
    src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    assert "def _create_opening_stock_doc_table(cursor):" in src
    assert "def _backfill_opening_stock_docs(cursor):" in src
    # DDL 只出现一次（在公共函数内）；若有人复制粘贴第二份即报红
    assert src.count("CREATE TABLE IF NOT EXISTS opening_stock_doc") == 1
    assert src.count("INSERT INTO opening_stock_doc") == 1
    # 两条链路都必须接线到公共函数
    assert "_create_opening_stock_doc_table(cursor)" in src   # auto_migrate Step 1
    assert "_backfill_opening_stock_docs(cursor)" in src      # auto_migrate Step 5
    assert "_create_opening_stock_doc_table(cur)" in src      # ensure 兜底
    assert "_backfill_opening_stock_docs(cur)" in src         # ensure 兜底
    # 启动注册：ensure_opening_stock_doc_table() 必须在 ensure_opening_stock_doc_columns() 之后
    col_call = src.index("\nensure_opening_stock_doc_columns()")
    tbl_call = src.index("\nensure_opening_stock_doc_table()")
    assert tbl_call > col_call, "建表+回填必须注册在补列之后（先列后表再回填）"


def test_startup_wiring_creates_table_when_no_db_touch(tmp_path):
    """接线：生产启动脚本默认 WMS_NO_DB_TOUCH=1，create_all/迁移被整体跳过
    （本次线上真 bug 场景）。子进程 `import app` 模拟完整启动，缺表必须被
    补建、历史必须被归单。"""
    db_path = _make_legacy_db(tmp_path / "inventory.db")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["WMS_NO_DB_TOUCH"] = "1"
    env["WMS_SKIP_STARTUP_DB_UPGRADE"] = "1"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    env["WMS_BOOTSTRAP_PASSWORD"] = "admin"
    env["WMS_SKIP_AUTO_UPDATE"] = "1"
    env["WMS_DEBUG"] = "0"
    env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"

    result = subprocess.run(
        [sys.executable, "-c", "import app"],
        cwd=str(APP_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
    )
    assert result.returncode == 0, f"app import failed:\n{result.stdout}\n{result.stderr}"

    assert _table_exists(db_path, "opening_stock_doc"), (
        f"WMS_NO_DB_TOUCH=1 启动后 opening_stock_doc 仍缺失:\n{result.stdout}\n{result.stderr}"
    )
    # 历史已归单：3 张单据、归属正确，期初库存列表页不再 500 且能看到历史数据
    docs = _docs_with_lines(db_path)
    assert [d[0] for d in docs] == ["QS26090001", "QS26090002", "QS26090003"]
    assert [d[3] for d in docs] == [2, 1, 1]
