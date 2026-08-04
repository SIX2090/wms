# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-011 回归测试：采购入库单明细合同编号/工程名称无法快速输入

原 Bug：
  后端 `/api/contracts` 返回裸对象 `{"contracts": [...]}`，缺少标准信封
  `{"status":"success","data":...}`。前端 `WMS.api.getContracts()`（经 api.js
  统一请求层 request）在 `res.status === 'success'` 判断处把该响应当作业务失败
  reject，导致 ContractAutocomplete 的 `.catch()` 吞掉错误，下拉永远不渲染，
  用户在采购入库单明细行输入合同编号/工程名称时看不到任何候选。

  同时 5 个单据页（in_order_add/sales_order_add/sales_order_edit/
  purchase_order_add/out_order_add）的头部分级合同搜索用裸 fetch 并判断
  `Array.isArray(list)`，对裸对象也永远为 false，同样失效。

修复：
  1. 后端 `/api/contracts` 改为返回标准信封 `{"status":"success","data":{"contracts":[...]}}`；
  2. 5 个单据页头部分级搜索改为从信封中提取 contracts（兼容 data/裸对象/裸数组）。

测试：
  T1. `/api/contracts` 返回标准信封 status==='success' 且 data.contracts 为数组
  T2. 关键词搜索（合同编号/工程名称）能命中对应合同
  T3. data.contracts 字段与前端 WMS.api.getContracts 读取的键一致
  T4. 明细行快速输入所需字段（contract_no/project_name/remark）齐全
"""
from __future__ import annotations

import os
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db, User, Contract  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _seed_contracts():
    db.session.add_all([
        Contract(contract_no="HD260713", project_name="鑫达产业园一期"),
        Contract(contract_no="HD260801", project_name="华宇钢结构厂房"),
        Contract(contract_no="HT2026-99", project_name="电梯井道加固"),
    ])
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


class TestBug20260804011ContractApiEnvelope:
    """/api/contracts 必须返回标准信封，否则前端快速输入下拉失效。"""

    def test_T1_returns_standard_envelope(self):
        """返回 status==='success' 且 data.contracts 为数组。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_contracts()
            client = app_module.app.test_client()
            _login(client)
            resp = client.get("/api/contracts")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success", \
                f"必须返回标准信封 status==='success'，实际 {data}"
            assert isinstance(data.get("data", {}).get("contracts"), list), \
                "data.contracts 应为数组（前端 WMS.api.getContracts 读取该键）"

    def test_T2_keyword_search(self):
        """按合同编号/工程名称关键词都能命中。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_contracts()
            client = app_module.app.test_client()
            _login(client)

            # 按合同编号关键词
            r = client.get("/api/contracts?keyword=HD2607")
            data = r.get_json()
            nos = [c["contract_no"] for c in data["data"]["contracts"]]
            assert "HD260713" in nos, f"应按合同编号命中，实际 {nos}"

            # 按工程名称关键词
            r2 = client.get("/api/contracts?keyword=鑫达")
            data2 = r2.get_json()
            names = [c["project_name"] for c in data2["data"]["contracts"]]
            assert "鑫达产业园一期" in names, f"应按工程名称命中，实际 {names}"

    def test_T3_data_contracts_readable_by_getContracts(self):
        """data.contracts 字段与前端 api.js 读取的键一致（前端用 data.contracts）。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_contracts()
            client = app_module.app.test_client()
            _login(client)
            data = client.get("/api/contracts").get_json()
            # 前端 ContractAutocomplete：data.contracts
            contracts = data["data"]["contracts"]
            assert len(contracts) == 3
            # 前端 renderDropdown 需要的字段
            for c in contracts:
                assert "contract_no" in c
                assert "project_name" in c
                assert "remark" in c

    def test_T4_no_keyword_returns_all(self):
        """不带关键词返回全部合同（前端聚焦时展示全部候选）。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            _seed_contracts()
            client = app_module.app.test_client()
            _login(client)
            data = client.get("/api/contracts").get_json()
            assert len(data["data"]["contracts"]) == 3