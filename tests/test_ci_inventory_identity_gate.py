# -*- coding: utf-8 -*-
"""BUG-2026-09-25-006：三账恒等式 CI 门禁脚本的自测。

`scripts/ci_check_inventory_identity.py` 是把 `verify_inventory_identity.py`
接进 CI 的适配器（该判据此前从未被任何 CI/Makefile/githook 调用过）。它需要
每轮建夹具库、跑判据、再反向验证判据会失败 —— 整轮约 3 个进程、几秒钟，
不适合在每个单测里跑。因此这里按"分层"测试：

* **纯函数层**（快、必跑）：夹具 SQL 与真实模型 schema 的一致性、`_verify_schema`
  的告警逻辑。这里能抓到最容易犯的错：夹具 SQL 写的列名和模型对不上。
* **端到端层**（慢、标记 skip 除非显式开启）：设置 `WMS_CI_E2E=1` 才跑，
  避免拖慢主套件；CI 里由 workflow 步骤直接调用脚本本身，等价覆盖。

为什么要单测夹具 SQL：夹具列名写错时，脚本只在 CI 里炸，本地很难发现
（已在开发中真实踩到：`material` 表用的是 `unit_id` 而不是 `unit`）。
"""
from __future__ import annotations

import importlib.util
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci_check_inventory_identity.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("ci_check_inv_identity", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load_script_module()


@pytest.fixture(scope="module")
def fixture_db(tmp_path_factory):
    """建一次夹具库，本模块内复用（建库约 2s，不值得每测重建）。"""
    workdir = tmp_path_factory.mktemp("identity_fixture")
    db_path = _load_script_module()._build_fixture_db(sys.executable, workdir)
    return db_path


def _columns(db_path: Path, table: str) -> set:
    conn = sqlite3.connect(str(db_path))
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def _insert_columns(sql: str, table: str) -> set:
    """从 INSERT INTO <table> (a, b, c) 里取出列名集合。"""
    out = set()
    for m in re.finditer(
        rf"INSERT\s+INTO\s+{table}\s*\(([^)]*)\)", sql, re.IGNORECASE
    ):
        out |= {c.strip() for c in m.group(1).split(",") if c.strip()}
    return out


class TestFixtureSchemaMatchesModels:
    """夹具 SQL 的列名必须真实存在于模型建出的表里（防止 CI 里才炸）。"""

    def test_seed_sql_columns_exist(self, mod, fixture_db):
        for table in ("material", "location_inventory", "stock_transaction"):
            used = _insert_columns(mod._SEED_SQL, table)
            assert used, f"夹具 SQL 未覆盖表 {table}"
            actual = _columns(fixture_db, table)
            assert used <= actual, (
                f"{table} 夹具 SQL 用了不存在的列：{sorted(used - actual)}；"
                f"实际列：{sorted(actual)}"
            )

    def test_dirty_sql_columns_exist(self, mod, fixture_db):
        for table in ("material", "location_inventory", "stock_transaction"):
            used = _insert_columns(mod._DIRTY_SQL, table)
            assert used, f"脏数据 SQL 未覆盖表 {table}"
            actual = _columns(fixture_db, table)
            assert used <= actual, (
                f"{table} 脏数据 SQL 用了不存在的列：{sorted(used - actual)}"
            )

    def test_seed_respects_not_null_columns(self, mod, fixture_db):
        """非空列必须都被显式赋值，否则 INSERT 必然失败。"""
        for table, sql in (
            ("material", mod._SEED_SQL),
            ("location_inventory", mod._SEED_SQL),
            ("stock_transaction", mod._SEED_SQL),
        ):
            conn = sqlite3.connect(str(fixture_db))
            try:
                cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            finally:
                conn.close()
            notnull = {c[1] for c in cols if c[3] and c[1] != "id"}
            used = _insert_columns(sql, table)
            missing = notnull - used
            assert not missing, (
                f"{table} 非空列未赋值：{sorted(missing)}（INSERT 会失败）"
            )

    def test_material_table_has_no_legacy_unit_column(self, fixture_db):
        """回归：material 用 unit_id 关联单位表，一度误写成 unit 导致 CI 炸。"""
        cols = _columns(fixture_db, "material")
        assert "unit_id" in cols
        assert "unit" not in cols


class TestVerifySchema:
    def test_detects_missing_tables(self, mod, tmp_path):
        empty = tmp_path / "empty.db"
        sqlite3.connect(str(empty)).close()
        with pytest.raises(SystemExit) as ei:
            mod._verify_schema(empty)
        assert "关键表" in str(ei.value)

    def test_passes_on_real_fixture(self, mod, fixture_db, capsys):
        mod._verify_schema(fixture_db)
        assert "schema 就绪" in capsys.readouterr().out


class TestIdentityAssertions:
    """直接对夹具库跑判据，验证三种形态的判定结果（不经过子进程）。"""

    def test_seeded_data_satisfies_identity(self, mod, fixture_db, tmp_path):
        db = tmp_path / "seed_only.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._SEED_SQL)
        summary = _run_checker_summary(db)
        assert summary["materials"] == 3
        assert summary["mismatch_ledger_vs_location"] == 0
        assert summary["mismatch_ledger_vs_txn"] == 0

    def test_dirty_row_is_caught_as_ledger_vs_location(self, mod, fixture_db, tmp_path):
        """反向验证：只写总账不写库位账 → 必须报 ①≠②。"""
        db = tmp_path / "dirty.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._SEED_SQL)
        mod._sqlite_exec(db, mod._DIRTY_SQL)
        summary = _run_checker_summary(db)
        assert summary["mismatch_ledger_vs_location"] == 1
        hit = [f for f in summary["findings"] if f["code"] == "CI-DIRTY"]
        assert len(hit) == 1
        assert hit[0]["dimension"] == "ledger_vs_location"
        assert hit[0]["delta"] == 998.0

    def test_material_without_location_rows_not_flagged(self, mod, fixture_db, tmp_path):
        """M3 无库位账（关库位管理场景）不应被判为不一致。"""
        db = tmp_path / "noloc.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._SEED_SQL)
        summary = _run_checker_summary(db)
        assert summary["materials"] == 3
        assert summary["materials_with_location_rows"] == 2


def _copy_db(src: Path, dst: Path) -> None:
    import shutil
    shutil.copyfile(str(src), str(dst))


def _run_checker_summary(db_path: Path) -> dict:
    """调用真判据脚本，解析 JSON 输出。"""
    import json
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_inventory_identity.py"),
         "--db", f"sqlite:///{db_path}", "--json"],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    # 判据在有 ①≠② 时返回 1，这是预期行为，不当作错误
    assert r.returncode in (0, 1), f"判据异常退出 rc={r.returncode}\n{r.stderr[-2000:]}"
    m = re.search(r"\{.*\}", r.stdout, re.DOTALL)
    assert m, f"判据未输出 JSON：{r.stdout[-2000:]}"
    return json.loads(m.group(0))


@pytest.mark.skipif(
    os.environ.get("WMS_CI_E2E") != "1",
    reason="端到端（建库+3 次子进程）较慢；CI 由 workflow 步骤直接调用脚本，"
           "本地需显式设 WMS_CI_E2E=1 才跑",
)
class TestEndToEnd:
    def test_script_exits_zero(self):
        r = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=str(ROOT),
            capture_output=True, text=True,
        )
        assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
        assert "反向验证" in r.stdout
