#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""三账恒等式 CI 门禁：用夹具库真跑一遍 verify_inventory_identity.py（BUG-2026-09-25-006）。

为什么需要它
------------
`scripts/verify_inventory_identity.py` 是全仓库**唯一**的三账恒等式判据
（INVENTORY_TRUTH.md §1：① material.stock = Σ② location_inventory.quantity
= Σ③ stock_transaction.quantity）。但它的 `--db` 是必填项，而 CI 里没有任何
现成数据库 —— 结果就是它从未被任何 CI / Makefile / githook 调用过（全仓
grep 命中 0），等于一个写了但从没运行过的判据。

直接用空库跑也没意义：空库三账全是 0，恒等式天然成立，门禁永远是绿的。
所以本脚本负责**先把夹具数据灌进去，再让真判据去判**，并额外做两件事：

1. **反向验证（元测试）**：故意造一条"只写总账不写库位账"的记录，确认判据
   **会**报错、退出码为 1。若判据被改坏成恒返回 0，本步立刻发现 ——
   这防的是"门禁看起来在跑，其实永远绿灯"。
2. 清掉那条脏数据后复跑，确认判据回到 0。

这样 CI 里这道门禁才同时具备"能跑"和"会失败"两个属性。

A14 合规：本脚本不 import app（只 subprocess 调用子脚本），无需 opt-in。
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "scripts" / "verify_inventory_identity.py"

# 夹具：三个物料，覆盖三种应当成立的形态
#   M1  三账齐全且一致            → 恒等式成立
#   M2  多库位、三账一致          → 恒等式成立
#   M3  无库位账（关库位管理场景）→ 恒等式成立（location_rows=0 不判 ①≠②）
# 列名以 app 真实模型为准：material 用 unit_id（非 unit），
# location_inventory/stock_transaction 的非空列见各表 NOT NULL 约束。
_SEED_SQL = """
INSERT INTO material (code, name, stock, created_at)
VALUES
  ('CI-M1', '夹具-三账齐全', 100.0, datetime('now')),
  ('CI-M2', '夹具-多库位',    75.0, datetime('now')),
  ('CI-M3', '夹具-无库位账',  20.0, datetime('now'));

INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'A-01', 60.0 FROM material WHERE code = 'CI-M1';
INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'A-02', 40.0 FROM material WHERE code = 'CI-M1';

INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'B-01', 30.0 FROM material WHERE code = 'CI-M2';
INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'B-02', 45.0 FROM material WHERE code = 'CI-M2';

INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in', 100.0, datetime('now') FROM material WHERE code = 'CI-M1';
INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in',  75.0, datetime('now') FROM material WHERE code = 'CI-M2';
INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in',  20.0, datetime('now') FROM material WHERE code = 'CI-M3';
"""

# 故意制造的 ①≠②：总账 999.0，但库位账只有 1.0 —— 判据必须抓到
_DIRTY_SQL = """
INSERT INTO material (code, name, stock, created_at)
VALUES ('CI-DIRTY', '夹具-故意不一致', 999.0, datetime('now'));

INSERT INTO location_inventory (material_id, location, quantity)
SELECT id, 'Z-99', 1.0 FROM material WHERE code = 'CI-DIRTY';

INSERT INTO stock_transaction (material_id, transaction_type, quantity, created_at)
SELECT id, 'in', 999.0, datetime('now') FROM material WHERE code = 'CI-DIRTY';
"""


def _run(cmd, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}", flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _build_fixture_db(python: str, workdir: Path) -> Path:
    """用 app 的真实模型建表，再灌夹具数据。

    注意（踩过的坑）：不能只设 `DATABASE_URL` + `FLASK_ENV=testing` ——
    `TestingConfig.SQLALCHEMY_DATABASE_URI` 被**硬编码**为 `sqlite:///:memory:`，
    会直接盖掉 DATABASE_URL，导致建的表全在内存里、文件里一张表都没有。
    因此这里在 import app **之前**先把 TestingConfig 的 URI 改到目标文件路径，
    与 `start_qa_server.py` 的做法一致。
    """
    db_path = workdir / "identity_fixture.db"
    bootstrap = workdir / "_bootstrap_fixture.py"
    bootstrap.write_text(
        "import os, sys\n"
        "os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')\n"
        "os.environ.setdefault('WMS_SKIP_AUTO_UPDATE', '1')\n"
        "os.environ.setdefault('WMS_DEBUG', '0')\n"
        "os.environ['FLASK_ENV'] = 'testing'\n"
        "os.environ['SECRET_KEY'] = 'ci-fixture-secret'\n"
        "os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'ci-fixture-admin'\n"
        "sys.path.insert(0, 'app')\n"
        "import config\n"
        # 关键：TestingConfig 的 URI 是硬编码 :memory:，必须在 import app 前改写
        f"config.TestingConfig.SQLALCHEMY_DATABASE_URI = 'sqlite:///{db_path}'\n"
        "from app import app, db, initialize_database\n"
        "with app.app_context():\n"
        "    initialize_database()\n"
        "    db.session.commit()\n"
        "print('fixture schema ready ->', app.config['SQLALCHEMY_DATABASE_URI'])\n",
        encoding="utf-8",
    )
    r = _run([python, str(bootstrap)], cwd=str(ROOT))
    if r.returncode != 0:
        print(r.stdout)
        print(r.stderr, file=sys.stderr)
        raise SystemExit("✗ 夹具库建表失败")
    if not db_path.exists():
        print(r.stdout)
        raise SystemExit(f"✗ 夹具库文件未生成：{db_path}")
    _verify_schema(db_path)
    return db_path


def _verify_schema(db_path: Path) -> None:
    """确认三账相关表真的落到文件里了（防止再次踩 :memory: 的坑）。"""
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        names = {
            r[0]
            for r in conn.execute(
                "select name from sqlite_master where type='table'"
            ).fetchall()
        }
    finally:
        conn.close()
    required = {"material", "location_inventory", "stock_transaction"}
    missing = required - names
    if missing:
        raise SystemExit(
            f"✗ 夹具库缺少关键表 {sorted(missing)}；"
            f"实际共 {len(names)} 张表。多半是 DB URI 被 TestingConfig 的 :memory: 覆盖了。"
        )
    print(f"  ✓ 夹具库 schema 就绪（{len(names)} 张表，三账表齐全）")


def _sqlite_exec(db_path: Path, sql: str) -> None:
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def _checker(python: str, db_path: Path):
    return _run(
        [python, str(CHECKER), "--db", f"sqlite:///{db_path}", "--json"],
        cwd=str(ROOT),
    )


def main() -> int:
    python = sys.executable
    env_note = os.environ.get("VIRTUAL_ENV") or python
    print("=" * 66)
    print("  三账恒等式 CI 门禁（BUG-2026-09-25-006）")
    print(f"  python: {env_note}")
    print("=" * 66)

    with tempfile.TemporaryDirectory(prefix="wms_identity_ci_") as td:
        workdir = Path(td)
        db_path = _build_fixture_db(python, workdir)

        # ---- 第 1 步：干净夹具，恒等式必须成立 ----
        print("\n[1/3] 灌入一致夹具数据，期望恒等式成立（rc=0）")
        _sqlite_exec(db_path, _SEED_SQL)
        r = _checker(python, db_path)
        print(r.stdout.rstrip())
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            print("\n✗ 夹具数据本身应当满足恒等式，判据却报错。"
                  "可能是判据口径变了，或夹具与模型脱节。")
            return 1
        print("  ✓ 通过")

        # ---- 第 2 步：反向验证 —— 判据必须能报错 ----
        print("\n[2/3] 注入『只写总账不写库位账』脏数据，期望判据报错（rc=1）")
        _sqlite_exec(db_path, _DIRTY_SQL)
        r = _checker(python, db_path)
        print(r.stdout.rstrip())
        if r.returncode == 0:
            print("\n✗ 脏数据存在时判据仍返回 0 —— 这道门禁等于永远绿灯，"
                  "比没有门禁更危险。请检查 find_mismatches 的判定逻辑。")
            return 1
        if "ledger_vs_location" not in r.stdout:
            print("\n✗ 判据失败原因不是 ①≠②，不符合预期。")
            return 1
        print("  ✓ 判据正确报出 ①≠②（反向验证通过）")

        # ---- 第 3 步：清除脏数据，恒等式恢复 ----
        print("\n[3/3] 清除脏数据，期望恒等式恢复（rc=0）")
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "DELETE FROM stock_transaction WHERE material_id IN "
                "(SELECT id FROM material WHERE code = 'CI-DIRTY')"
            )
            conn.execute(
                "DELETE FROM location_inventory WHERE material_id IN "
                "(SELECT id FROM material WHERE code = 'CI-DIRTY')"
            )
            conn.execute("DELETE FROM material WHERE code = 'CI-DIRTY'")
            conn.commit()
        finally:
            conn.close()
        r = _checker(python, db_path)
        print(r.stdout.rstrip())
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            print("\n✗ 脏数据已清除，恒等式却仍不成立。")
            return 1
        print("  ✓ 通过")

    print("\n" + "=" * 66)
    print("  ✓ 三账恒等式门禁通过（含反向验证：判据确实会失败）")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    sys.exit(main())
