# -*- coding: utf-8 -*-
"""P2-1 回归锁（2026-09-27）：`①≠③`（总账 vs 流水）差异**不得静默放行**。

锁死的契约
----------
    ✅ 存在 `①≠③` 且该物料**无豁免登记** → 退出码 **1**（硬失败，阻断）
    ✅ 存在 `①≠③` 且该物料**在豁免名单且理由非空** → 退出码 **0**（🟡 告警）
    ❌ 而非「①≠③ 无论多少条都返回 0」（修复前的行为，即本 BUG）

为什么这是 BUG 而不是有意设计
-----------------------------
`INVENTORY_TRUTH.md:70` 文档正文写明：

    ① 独立于 ②③ 变动 | ❌ 禁止 | 除非 # stock-truth:reason= 显式豁免

只有 `scripts/verify_inventory_identity.py` 的**注释**单方把它降级为「待确认不阻断」。
仓库里 `WMS_BUG_BASELINE.md` / `AGENTS.md` / `WMS_BUSINESS_SCOPE.md`
**无任何条目**把 `①≠③` 登记为「允许保留」。

双重盲区（本 BUG 的成因）
-----------------------
物料级判据（`ledger_vs_txn`）不阻断，而 P0-1 新增的仓级判据**主动跳过**
`warehouse_id IS NULL` 的 `UNATTRIBUTED` 桶（那是「不猜归属」的刻意设计）。
两者交集 —— NULL 归属历史行造成的 `①≠③` —— **没有任何判据覆盖**。

覆盖形态
--------
1. 默认（不传豁免）：`①≠③` → rc=1；
2. 传豁免文件且命中：`①≠③` → rc=0，且被标为 waived；
3. 豁免文件里**理由为空/空白** → 视为未登记 → 仍 rc=1；
4. 豁免文件不存在 / JSON 非法 / 结构不符 → **报错退出，不静默降级**；
5. 键支持 `material.code` 与 `material_id`（字符串）；
6. 向后兼容：`summarize()` 不传新参数时，返回键与旧版**逐字节一致**；
7. 控制组：**无误报** —— 真正的历史差有登记则转绿，真缺陷无登记则阻断。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
SCRIPTS_DIR = ROOT / "scripts"
for p in (str(APP_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("WMS_ALLOW_INSECURE_COOKIE", "1")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
# 与 tests/test_p1_1_identity_aggregation.py 同一隔离模式：内存库 + 每测试 drop/create。
# 踩过的坑（P1-1 首版即栽在此）：改写 config.TestingConfig.SQLALCHEMY_DATABASE_URI
# 对**已初始化**的 app **不生效**，全量 pytest 下会读到前序模块残留的库（R7 顺序依赖）。
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"

import verify_inventory_identity as v  # noqa: E402


# ---------------------------------------------------------------------------
# 纯函数级：分级判定
# ---------------------------------------------------------------------------
class TestDriftAllowlistLoading:
    """豁免文件的加载与校验（失败必须可见，A12 精神）。"""

    def test_loads_valid_allowlist(self, tmp_path):
        p = tmp_path / "drift.json"
        p.write_text(json.dumps({"materials": {"P21-M1": "期初历史差"}}),
                     encoding="utf-8")
        allow = v.load_drift_allowlist(str(p))
        assert allow["P21-M1"] == "期初历史差"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(v.DriftAllowlistError):
            v.load_drift_allowlist(str(tmp_path / "nope.json"))

    def test_invalid_json_raises(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        with pytest.raises(v.DriftAllowlistError):
            v.load_drift_allowlist(str(p))

    def test_wrong_structure_raises(self, tmp_path):
        """顶层缺 materials / materials 不是对象 → 必须报错，不得静默当空名单。"""
        p1 = tmp_path / "a.json"
        p1.write_text(json.dumps({"other": {}}), encoding="utf-8")
        with pytest.raises(v.DriftAllowlistError):
            v.load_drift_allowlist(str(p1))

        p2 = tmp_path / "b.json"
        p2.write_text(json.dumps({"materials": ["P21-M1"]}), encoding="utf-8")
        with pytest.raises(v.DriftAllowlistError):
            v.load_drift_allowlist(str(p2))

    def test_blank_reason_treated_as_unregistered(self, tmp_path):
        """理由为空/空白 → 视为未登记（防"空名单糊过去"）。"""
        p = tmp_path / "blank.json"
        p.write_text(json.dumps({"materials": {"P21-M1": "   ", "P21-M2": ""}}),
                     encoding="utf-8")
        allow = v.load_drift_allowlist(str(p))
        assert "P21-M1" not in allow
        assert "P21-M2" not in allow

    def test_reason_must_be_string(self, tmp_path):
        p = tmp_path / "num.json"
        p.write_text(json.dumps({"materials": {"P21-M1": 123}}), encoding="utf-8")
        with pytest.raises(v.DriftAllowlistError):
            v.load_drift_allowlist(str(p))


class TestDriftSplitting:
    """把 `ledger_vs_txn` findings 拆成 hard / waived 两组。"""

    def _rows(self):
        materials = [(1, "P21-M1", 100.0), (2, "P21-M2", 80.0), (3, "P21-M3", 50.0)]
        locations = [(1, 100.0, None), (2, 80.0, None), (3, 50.0, None)]
        transactions = [(1, 40.0, None), (2, 80.0, None), (3, 50.0, None)]
        rows = v.build_identity_rows(materials, locations, transactions)
        findings = v.find_mismatches(rows)
        return rows, findings

    def test_no_allowlist_means_all_hard(self):
        rows, findings = self._rows()
        hard, waived = v.split_drift_findings(rows, findings, None)
        assert len(hard) == 1
        assert hard[0]["material_id"] == 1
        assert waived == []

    def test_allowlist_by_code_waives(self):
        rows, findings = self._rows()
        hard, waived = v.split_drift_findings(rows, findings, {"P21-M1": "历史差"})
        assert hard == []
        assert len(waived) == 1
        assert waived[0]["waive_reason"] == "历史差"

    def test_allowlist_by_material_id_waives(self):
        """键支持 material_id 的字符串形式。"""
        rows, findings = self._rows()
        hard, waived = v.split_drift_findings(rows, findings, {"1": "历史差"})
        assert hard == []
        assert len(waived) == 1

    def test_allowlist_for_other_material_does_not_waive(self):
        """名单里的物料与实际差异物料**不匹配**时必须仍硬失败（防误豁免）。"""
        rows, findings = self._rows()
        hard, waived = v.split_drift_findings(rows, findings, {"P21-M2": "不相干"})
        assert len(hard) == 1
        assert hard[0]["material_id"] == 1
        assert waived == []

    def test_non_drift_findings_untouched(self):
        """`ledger_vs_location` 类 finding 不得被豁免机制吞掉。"""
        materials = [(1, "P21-X", 100.0)]
        locations = [(1, 5.0, None)]
        transactions = [(1, 100.0, None)]
        rows = v.build_identity_rows(materials, locations, transactions)
        findings = v.find_mismatches(rows)
        # 有 ledger_vs_location（100 vs 5）
        assert any(f["dimension"] == "ledger_vs_location" for f in findings)
        hard, waived = v.split_drift_findings(rows, findings, {"P21-X": "编个理由"})
        # 该物料在名单里，但豁免只作用于 ledger_vs_txn；
        # ledger_vs_location 仍由 find_mismatches 原样报出（不进 hard/waived）
        assert all(f["dimension"] == "ledger_vs_txn" for f in hard + waived)


class TestSummarizeBackwardCompat:
    """向后兼容：不传新参数时，返回键与旧版**逐字节一致**（P0-1 同款策略）。"""

    def _rows(self):
        materials = [(1, "M", 100.0)]
        locations = [(1, 100.0, None)]
        transactions = [(1, 40.0, None)]
        return v.build_identity_rows(materials, locations, transactions)

    def test_legacy_keys_unchanged_without_new_args(self):
        rows = self._rows()
        findings = v.find_mismatches(rows)
        s = v.summarize(rows, findings)
        assert "drift_hard" not in s
        assert "drift_waived" not in s

    def test_new_keys_present_when_passed(self):
        rows = self._rows()
        findings = v.find_mismatches(rows)
        s = v.summarize(rows, findings, drift_hard=[{"x": 1}], drift_waived=[])
        assert s["drift_hard"] == 1
        assert s["drift_waived"] == 0


# ---------------------------------------------------------------------------
# 端到端：真跑判据脚本，断言退出码（这是 CI 真正依赖的契约）
#
# 注意：判据是**子进程**，读不到测试进程内存里的 `:memory:` 库（内存库不跨进程）。
# 因此这里必须落**真文件库**，与 scripts/ci_check_inventory_identity.py 同一做法。
# ---------------------------------------------------------------------------
import sqlite3  # noqa: E402


def _build_fixture_file_db(db_path, seed_sql):
    """用 app 的真实模型建表到文件库，再灌夹具。

    踩过的坑（与 ci_check_inventory_identity.py 同源）：不能只设 `DATABASE_URL`
    —— `TestingConfig.SQLALCHEMY_DATABASE_URI` 硬编码为 `:memory:`，会盖掉
    DATABASE_URL。必须在 **import app 之前**改写 config。
    """
    bootstrap = db_path.parent / "_bootstrap_p21.py"
    bootstrap.write_text(
        "import os, sys\n"
        "os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')\n"
        "os.environ.setdefault('WMS_SKIP_AUTO_UPDATE', '1')\n"
        "os.environ.setdefault('WMS_DEBUG', '0')\n"
        "os.environ['FLASK_ENV'] = 'testing'\n"
        "os.environ['SECRET_KEY'] = 'p21-fixture-secret'\n"
        "os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'p21-fixture-admin'\n"
        "sys.path.insert(0, 'app')\n"
        "import config\n"
        f"config.TestingConfig.SQLALCHEMY_DATABASE_URI = 'sqlite:///{db_path}'\n"
        "from app import app, db, initialize_database\n"
        "with app.app_context():\n"
        "    initialize_database()\n"
        "    db.session.commit()\n",
        encoding="utf-8",
    )
    subprocess.run([sys.executable, str(bootstrap)],
                   capture_output=True, text=True, cwd=str(ROOT), check=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(seed_sql)
        conn.commit()
    finally:
        conn.close()


# 只有 ①≠③ 的夹具：总账 100 / 库位账 100（①=② 成立）/ 流水 40
# warehouse_id 全为 NULL → 仓级判据不覆盖（P0-1 的 UNATTRIBUTED 跳过）。
# 这正是 P2-1 的双重盲区：修复前这里 rc=0。
_P21_SEED_SQL = """
INSERT INTO material (code, name, stock, created_at)
VALUES ('P21-M1', '夹具-只有1v3差异', 100.0, datetime('now')),
       ('P21-M2', '夹具-三账一致',     80.0, datetime('now'));

INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'P21-L1', 100.0 FROM material WHERE code = 'P21-M1';
INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'P21-L2',  80.0 FROM material WHERE code = 'P21-M2';

INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in', 40.0, datetime('now') FROM material WHERE code = 'P21-M1';
INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in', 80.0, datetime('now') FROM material WHERE code = 'P21-M2';
"""


@pytest.fixture(scope="module")
def base_db(tmp_path_factory):
    """真文件库（子进程判据能读到）。

    `scope="module"`：bootstrap app 建库较慢（约 10s），只在模块内建**一次**；
    每个用例用 `file_db` 把它重置回已知数据状态。这不引入顺序依赖——
    重置是「删三表数据 + 重新灌夹具」的确定性操作，与执行顺序无关。
    """
    workdir = tmp_path_factory.mktemp("p21_fixture")
    db_path = workdir / "p21_fixture.db"
    _build_fixture_file_db(db_path, "")
    return db_path


@pytest.fixture
def file_db(base_db):
    """把模块级库重置回本模块的已知夹具状态（每个用例都一样）。"""
    conn = sqlite3.connect(str(base_db))
    try:
        for table in ("stock_transaction", "location_inventory", "material"):
            conn.execute(f"DELETE FROM {table}")
        conn.executescript(_P21_SEED_SQL)
        conn.commit()
    finally:
        conn.close()
    return base_db


def _run_checker_on(db_path, extra_args=None):
    cmd = [sys.executable, str(SCRIPTS_DIR / "verify_inventory_identity.py"),
           "--db", f"sqlite:///{db_path}"]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))


def _extract_json(stdout):
    """从混有 app 启动日志的 stdout 里截出 JSON 主体。

    app 导入期会往 stdout 打日志（`Flask config loaded` / `[DB] ...` 等），
    直接 `json.loads` 会报 `Extra data`。判据的 JSON 主体必然从**第一个 `{`
    且位于行首**的位置开始——按此截取。
    """
    lines = stdout.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("{"))
    return json.loads("\n".join(lines[start:]))


class TestExitCodeContract:
    """退出码契约——本 BUG 的核心。用**真子进程 + 真文件库**验证，不 mock。"""

    def test_drift_without_allowlist_blocks(self, file_db):
        """只有 ①≠③ → 必须 rc=1（修复前这里是 0，即 P2-1）。"""
        r = _run_checker_on(file_db)
        assert r.returncode == 1, (
            f"①≠③ 存在时判据必须硬失败，实际 rc={r.returncode}\n{r.stdout}")
        assert "ledger_vs_txn" in r.stdout

    def test_drift_with_allowlist_passes(self, file_db, tmp_path):
        """登记豁免后 → rc=0。"""
        p = tmp_path / "drift.json"
        p.write_text(json.dumps({"materials": {"P21-M1": "期初历史差，已验证"}}),
                     encoding="utf-8")
        r = _run_checker_on(file_db, ["--allow-drift", str(p)])
        assert r.returncode == 0, (
            f"已登记的 ①≠③ 不应阻断，实际 rc={r.returncode}\n{r.stdout}")

    def test_drift_allowlist_blank_reason_still_blocks(self, file_db, tmp_path):
        """名单里理由为空白 = 未登记 → 仍必须 rc=1。"""
        p = tmp_path / "blank.json"
        p.write_text(json.dumps({"materials": {"P21-M1": "  "}}), encoding="utf-8")
        r = _run_checker_on(file_db, ["--allow-drift", str(p)])
        assert r.returncode == 1

    def test_partial_allowlist_only_waives_listed(self, file_db, tmp_path):
        """只登记 M1、不登记 M2 → 只豁免 M1（这里 M2 本就一致，故 rc=0）。"""
        p = tmp_path / "partial.json"
        p.write_text(json.dumps({"materials": {"P21-M2": "不相干登记"}}),
                     encoding="utf-8")
        r = _run_checker_on(file_db, ["--allow-drift", str(p)])
        # M2 登记了但它没差异；M1 有差异但没登记 → 仍 rc=1（防误豁免）
        assert r.returncode == 1
        assert "ledger_vs_txn" in r.stdout

    def test_missing_allowlist_file_fails_loudly(self, file_db, tmp_path):
        """文件不存在 → 报错退出（rc=2），**不得静默当空名单放过**。"""
        r = _run_checker_on(file_db, ["--allow-drift", str(tmp_path / "nope.json")])
        assert r.returncode == 2, (
            f"豁免文件缺失必须显式报错，实际 rc={r.returncode}\n{r.stderr}")

    def test_json_output_carries_drift_keys(self, file_db):
        """`--json` 输出必须带 drift_hard / drift_waived（供流水线消费）。"""
        r = _run_checker_on(file_db, ["--json"])
        assert r.returncode == 1
        payload = _extract_json(r.stdout)
        assert payload["drift_hard"] == 1
        assert payload["drift_waived"] == 0


class TestAntiRegression:
    """静态兜底：防止退出码再次被改回不判 ①≠③。"""

    def test_exit_code_includes_drift(self):
        src = (SCRIPTS_DIR / "verify_inventory_identity.py").read_text(encoding="utf-8")
        # 退出码表达式必须提到 drift_hard（否则 ①≠③ 又变成静默放行）
        assert "drift_hard" in src, (
            "退出码判定必须纳入 drift_hard，否则 ①≠③ 会再次静默放行")
        assert "--allow-drift" in src

    def test_allowlist_error_class_exists(self):
        assert hasattr(v, "DriftAllowlistError")
        assert hasattr(v, "load_drift_allowlist")
        assert hasattr(v, "split_drift_findings")
