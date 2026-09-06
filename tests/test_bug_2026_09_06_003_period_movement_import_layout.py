# -*- coding: utf-8 -*-
"""BUG-2026-09-06-003 回归：盘点完成路径在生产模块布局下的导入错误。

问题：`_check_period_movement_alerts`（BUG-2026-09-06-002 引入）用了
`from app.utils import normalize_stock_quantity`。本仓库 app/ 目录即包根
（app.py 是顶层模块、无 __init__.py，全部路由模块按 `from app import X`
读 app.py 属性、`from utils import Y` 读顶层模块），**没有任何
`from app.<子模块> import` 的先例**。真实启动布局（python app.py /
run_server.py，app 目录在 sys.path[0]）下，`app` 是普通模块而非包，
此行必然 `ModuleNotFoundError` → 每次"完成盘点"（凡是没有未盘行、走到
动销校验的无 force 完成，如手机扫码空单全盘完）在生产环境 500。

为何既有测试未抓出：pytest 把仓库根目录插进 sys.path（tests 是包，
rootdir 插入其父目录），`app` 被解析成命名空间包，`app.utils` 恰好可导——
**生产与测试的导入布局不一致**，此错误被掩盖。

修复：改为仓库统一写法 `from app import StockTransaction, normalize_stock_quantity`
（app.py 已从 utils 转导出该符号，与全仓其余消费点一致）。

覆盖：
T1. 静态契约：全仓 app/**/*.py 禁止 `from app.<子模块> import`（app 非包，
    此类写法必然在生产炸；防同类复发）
T2. 子进程按生产模块布局（cwd=app 目录直接 `python -c`）完成一次
    "空单+手机扫码全盘" → complete 无 force 必须 success（修复前 500）
T3. 动销校验本体在模块布局下仍能正确命中期间流水并返回 period_movement
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
TESTS_DIR = ROOT / "tests"

CHILD = r"""
import os, sys, json
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
import app as m
m.app.config["TESTING"] = True
m.app.config["WTF_CSRF_ENABLED"] = False
ctx = m.app.app_context(); ctx.push()
m.db.drop_all(); m.db.create_all()
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from app import (AdjustmentOrder, InventoryCheck, Material, StockTransaction,
                 User, Warehouse)
m.db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                     role="admin", must_change_password=False))
wh = Warehouse(code="WA", name="A仓", status="active", is_default=True)
m.db.session.add(wh); m.db.session.commit()
mat = Material(code="M001", name="物料M001", stock=10.0)
m.db.session.add(mat); m.db.session.flush()
m.db.session.add(StockTransaction(material_id=mat.id, transaction_type="in", quantity=10.0,
    location="A仓", warehouse_id=wh.id, created_at=datetime.now() - timedelta(minutes=5)))
m.db.session.commit()
c = m.app.test_client()
c.post("/login", data={"username": "admin", "password": "admin"})
tok = c.post("/api/login", json={"username": "admin", "password": "admin"}).get_json()["data"]["token"]
h = {"Authorization": "Bearer " + tok}

def run_scan():
    r = c.post("/check/add", data={"warehouse": "A仓", "remark": "生产布局回归"})
    cid = r.get_json()["id"]
    s = c.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check", "code": "M001", "warehouse": "A仓",
        "actual_stock": 9, "check_id": cid})
    assert s.status_code == 200, s.get_data(as_text=True)
    return cid

# T2 场景：空单 + 手机全盘（无未盘行）→ 无 force 完成必成功（修复前 500）
cid = run_scan()
r = c.post(f"/check/{cid}/complete")
body = r.get_json() if r.is_json else {}
assert r.status_code == 200, r.get_data(as_text=True)
assert body.get("status") == "success", body
print("T2_OK")

# T3 场景：期间流水命中动销校验仍生效
cid2 = c.post("/check/add", data={"warehouse": "A仓", "scope": "all"}).get_json()["id"]
chk = m.db.session.get(InventoryCheck, cid2)
m.db.session.add(StockTransaction(material_id=mat.id, transaction_type="out", quantity=-3.0,
    location="A仓", warehouse_id=wh.id, created_at=chk.frozen_at + timedelta(seconds=2)))
m.db.session.commit()
s2 = c.post("/mobile/api/scan_submit", headers=h, json={
    "mode": "check", "code": "M001", "warehouse": "A仓",
    "actual_stock": 7, "check_id": cid2})
assert s2.status_code == 200, s2.get_data(as_text=True)
r2 = c.post(f"/check/{cid2}/complete")
b2 = r2.get_json()
assert r2.status_code == 200, r2.get_data(as_text=True)
assert b2.get("status") == "confirm" and b2.get("code") == "period_movement", b2
r3 = c.post(f"/check/{cid2}/complete", json={"force": 1})
assert r3.get_json().get("status") == "success", r3.get_json()
print("T3_OK")
"""


def _child_env():
    env = dict(os.environ)
    env["PYTHONPATH"] = str(APP_DIR)
    return env


def _run_child():
    result = subprocess.run(
        [sys.executable, "-c", CHILD],
        cwd=str(APP_DIR),  # 生产模块布局：app 目录在 sys.path[0]，app.py 为顶层模块
        env=_child_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result


# T1 ───────────────────────────────────────────────────────────────
def test_t1_no_app_submodule_import_anywhere():
    """全仓禁止 `from app.<子模块> import`——app 目录即包根（无 __init__.py），
    此类导入在生产布局必然 ModuleNotFoundError（BUG-2026-09-06-003）。"""
    pattern = re.compile(r"^\s*from\s+app\.[A-Za-z_][\w.]*\s+import", re.M)
    offenders = []
    for py in sorted((APP_DIR).rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for mt in pattern.finditer(text):
            # 行内如 `from app.utils import x` 立即命中；排除注释行由正则行首保证
            offenders.append(f"{py.relative_to(ROOT)}:{text[:mt.start()].count(chr(10))+1}")
    assert not offenders, "禁止 `from app.<子模块> import`（app 非包），违反处：\n" + "\n".join(offenders)


# T2+T3 ────────────────────────────────────────────────────────────
def test_t2_t3_production_layout_complete_ok():
    result = _run_child()
    assert result.returncode == 0, (
        f"子进程失败:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    assert "T2_OK" in result.stdout and "T3_OK" in result.stdout, result.stdout
