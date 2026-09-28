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

    def test_cross_wh_sql_columns_exist(self, mod, fixture_db):
        """P0-1：仓级串仓夹具的列名必须真实存在，且必须带 warehouse_id。

        不带 warehouse_id 的话，`find_warehouse_mismatches` 只会看到
        UNATTRIBUTED 桶、一条都报不出来 —— 第 4 步会假绿。
        """
        for table in ("warehouse", "material", "location_inventory",
                      "stock_transaction"):
            used = _insert_columns(mod._CROSS_WH_SQL, table)
            assert used, f"仓级夹具 SQL 未覆盖表 {table}"
            actual = _columns(fixture_db, table)
            assert used <= actual, (
                f"{table} 仓级夹具用了不存在的列：{sorted(used - actual)}；"
                f"实际列：{sorted(actual)}"
            )
        for table in ("location_inventory", "stock_transaction"):
            assert "warehouse_id" in _insert_columns(mod._CROSS_WH_SQL, table), (
                f"{table} 仓级夹具缺 warehouse_id —— 仓级判据将看不到任何仓库"
            )

    def test_cross_wh_sql_respects_not_null_columns(self, mod, fixture_db):
        """非空列（如 warehouse.is_default）必须显式赋值，否则 INSERT 炸。"""
        for table, sql in (
            ("warehouse", mod._CROSS_WH_SQL),
            ("material", mod._CROSS_WH_SQL),
            ("location_inventory", mod._CROSS_WH_SQL),
            ("stock_transaction", mod._CROSS_WH_SQL),
        ):
            conn = sqlite3.connect(str(fixture_db))
            try:
                cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            finally:
                conn.close()
            notnull = {c[1] for c in cols if c[3] and c[1] != "id"}
            missing = notnull - _insert_columns(sql, table)
            assert not missing, (
                f"{table} 非空列未赋值：{sorted(missing)}（INSERT 会失败）"
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

    def test_drift_sql_columns_exist(self, mod, fixture_db):
        """P2-1：①≠③ 夹具的列名必须真实存在。

        该夹具必须**刻意不带** warehouse_id —— 带上的话会被仓级判据兜住，
        就测不出「①≠③ 静默放行」这个 P2-1 缺陷了。
        """
        for table in ("material", "location_inventory", "stock_transaction"):
            used = _insert_columns(mod._P21_DRIFT_SQL, table)
            actual = _columns(fixture_db, table)
            assert used <= actual, (
                f"{table} P2-1 夹具用了不存在的列：{sorted(used - actual)}；"
                f"实际列：{sorted(actual)}"
            )
        for table in ("location_inventory", "stock_transaction"):
            assert "warehouse_id" not in _insert_columns(mod._P21_DRIFT_SQL, table), (
                f"{table} P2-1 夹具**不应**带 warehouse_id —— "
                "带了会被仓级判据兜住，失去区分度（P2-1 测的就是双重盲区）"
            )

    def test_drift_sql_respects_not_null_columns(self, mod, fixture_db):
        for table in ("material", "location_inventory", "stock_transaction"):
            conn = sqlite3.connect(str(fixture_db))
            try:
                cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
            finally:
                conn.close()
            notnull = {c[1] for c in cols if c[3] and c[1] != "id"}
            missing = notnull - _insert_columns(mod._P21_DRIFT_SQL, table)
            assert not missing, (
                f"{table} 非空列未赋值：{sorted(missing)}（INSERT 会失败）"
            )

    def test_p21_allowlist_is_valid_json(self, mod):
        """CI 自带的豁免登记必须是合法 JSON 且带非空理由。"""
        import json
        payload = json.loads(mod._P21_ALLOWLIST)
        assert isinstance(payload.get("materials"), dict)
        assert payload["materials"].get("CI-P21", "").strip(), (
            "CI 豁免登记必须给 CI-P21 一个非空理由（空理由会被视为未登记）"
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

    def test_cross_warehouse_contamination_is_caught(self, mod, fixture_db, tmp_path):
        """P0-1 反向验证：物料级合计相等但仓级串仓 → 必须报 wh_location_vs_txn。

        这是 AGENTS.md R2「多仓库隔离」的最低要求，也是 P0-1 修复的核心价值。
        若此用例失败，说明仓级维度没生效 —— 第 4 步门禁等于空转。
        """
        db = tmp_path / "crosswh.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._SEED_SQL)
        mod._sqlite_exec(db, mod._CROSS_WH_SQL)
        summary = _run_checker_summary(db)

        # 物料级：Σ② = 20 + 80 = 100 = ① → 物料级判据**全绿**（旧版在此漏网）
        assert summary["mismatch_ledger_vs_location"] == 0
        # 仓级：必须抓到 A(20 vs 60) 与 B(80 vs 40) 两处
        assert summary["mismatch_wh_location_vs_txn"] == 2
        deltas = sorted(f["delta"] for f in summary["warehouse_findings"])
        assert deltas == [-40.0, 40.0]
        assert all(f["dimension"] == "wh_location_vs_txn"
                   for f in summary["warehouse_findings"])

    def test_correct_warehouse_split_not_flagged(self, mod, fixture_db, tmp_path):
        """对照：仓级数据正确时不得误报（防止修成"见仓库就报"）。"""
        db = tmp_path / "crosswh_ok.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._SEED_SQL)
        mod._sqlite_exec(db, mod._CROSS_WH_SQL)
        # 让两仓各自自洽：A 仓库位账 20 → 60（对齐 A 仓流水 60）；
        #                   B 仓流水 40 → 80（对齐 B 仓库位账 80）。
        mod._sqlite_exec(db, """
            UPDATE location_inventory SET quantity = 60.0
            WHERE material_id IN (SELECT id FROM material WHERE code = 'CI-XWH')
              AND warehouse_id IN (SELECT id FROM warehouse WHERE code = 'CI-WHA');
            UPDATE stock_transaction SET quantity = 80.0
            WHERE material_id IN (SELECT id FROM material WHERE code = 'CI-XWH')
              AND warehouse_id IN (SELECT id FROM warehouse WHERE code = 'CI-WHB');
        """)
        summary = _run_checker_summary(db)
        assert summary["mismatch_wh_location_vs_txn"] == 0
        assert summary["warehouse_findings"] == []

    def test_p21_only_ledger_vs_txn_is_flagged(self, mod, fixture_db, tmp_path):
        """P2-1 反向验证：只有 ①≠③ 的物料必须被列为 drift_hard（阻断）。

        修复前此场景 `drift_hard` 键都不存在、退出码 0 —— 就是 P2-1 的漏网口。
        """
        db = tmp_path / "p21.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._P21_DRIFT_SQL)
        summary = _run_checker_summary(db)

        # ①=②：库位账 100 = 总账 100
        assert summary["mismatch_ledger_vs_location"] == 0
        # 仓级不覆盖（warehouse_id 全 NULL，进 UNATTRIBUTED 桶）
        assert summary["mismatch_wh_location_vs_txn"] == 0
        # 只有 ①≠③ 命中，且是**未登记 → 硬失败**
        assert summary["mismatch_ledger_vs_txn"] == 1
        assert summary["drift_hard"] == 1
        assert summary["drift_waived"] == 0
        assert summary["drift_hard_findings"][0]["code"] == "CI-P21"
        assert summary["drift_hard_findings"][0]["delta"] == 60.0

    def test_p21_allowlist_downgrades_to_waived(self, mod, fixture_db, tmp_path):
        """对照：同一脏数据 + 豁免登记 → drift_waived=1、drift_hard=0（不阻断）。

        这是防「修成一律硬失败」的控制组。
        """
        db = tmp_path / "p21_ok.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._P21_DRIFT_SQL)
        allow = tmp_path / "allow.json"
        allow.write_text(mod._P21_ALLOWLIST, encoding="utf-8")

        summary = _run_checker_summary(db, ["--allow-drift", str(allow)])
        assert summary["mismatch_ledger_vs_txn"] == 1
        assert summary["drift_hard"] == 0
        assert summary["drift_waived"] == 1
        assert summary["drift_waived_findings"][0]["waive_reason"].strip()

    def test_p21_blank_reason_allowlist_still_hard(self, mod, fixture_db, tmp_path):
        """名单内理由为空白 = 未登记 → 仍必须 drift_hard（防"空名单糊过去"）。"""
        db = tmp_path / "p21_blank.db"
        _copy_db(fixture_db, db)
        mod._sqlite_exec(db, mod._P21_DRIFT_SQL)
        allow = tmp_path / "blank.json"
        allow.write_text('{"materials": {"CI-P21": "   "}}', encoding="utf-8")

        summary = _run_checker_summary(db, ["--allow-drift", str(allow)])
        assert summary["drift_hard"] == 1
        assert summary["drift_waived"] == 0


def _copy_db(src: Path, dst: Path) -> None:
    import shutil
    shutil.copyfile(str(src), str(dst))


def _run_checker_summary(db_path: Path, extra_args=None) -> dict:
    """调用真判据脚本，解析 JSON 输出。"""
    import json
    cmd = [sys.executable, str(ROOT / "scripts" / "verify_inventory_identity.py"),
           "--db", f"sqlite:///{db_path}", "--json"]
    if extra_args:
        cmd += list(extra_args)
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    # 判据在有 ①≠②/①≠③ 时返回 1，这是预期行为，不当作错误
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
