# -*- coding: utf-8 -*-
"""BUG-2026-08-29-004：采购入库明细表工程名称筛选框无候选下拉。

背景：供应商输入框已有「输入即弹候选」自动补全（supplierFilterDropdown，
BUG-2026-08-29-003 配套），工程名称框（name=project_name）却是纯文本——
输入「东莞」命中多个工程时用户看不到候选、只能凭记忆输入全名。

修复：in_order.html 工程名称框复用供应商下拉模式加自动补全——数据源为
现成接口 /api/contracts?keyword=（contract_no/project_name ilike 模糊，
标准信封 {status,data:{contracts}}，限 50 条），候选行显示「工程名称 +
合同编号」，键盘上下/回车/Escape/mousedown 选择回填完整工程名；后端零改动。

T1. 模板契约：projectNameFilterInput 输入框 + projectNameDropdown 候选容器。
T2. 交互契约：input/focus/blur/keydown(ArrowDown/ArrowUp/Enter/Escape)/mousedown 齐全。
T3. 数据源契约：fetch /api/contracts?keyword= 并按 {status:'success',data:{contracts}} 信封解析。
T4. /api/contracts 按 keyword 模糊匹配工程名称（真实路由 + 会话登录）。
T5. /api/contracts 按 keyword 模糊匹配合同编号。
T6. /api/contracts 响应字段含 project_name/contract_no；无匹配返回空数组。
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import Contract, User, db  # noqa: E402

import pytest  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


@pytest.fixture(autouse=True)
def _app_ctx():
    """每个用例包在 app context 内（db 操作必需）。"""
    with app_module.app.app_context():
        yield


TPL = (ROOT / "app" / "templates" / "in_order.html").read_text(encoding="utf-8")


def _uid():
    return uuid.uuid4().hex[:8]


def _seed_contracts():
    db.drop_all()
    db.create_all()
    db.session.add(User(username="qa-" + _uid(), password_hash="x"))
    rows = [
        Contract(contract_no="HD-DG-001", project_name="东莞市长安镇变配电工程", status="active"),
        Contract(contract_no="HD-SZ-002", project_name="深圳市福田区照明工程", status="active"),
        Contract(contract_no="HD-DG-003", project_name="东莞市厚街医院配电改造", status="active"),
    ]
    db.session.add_all(rows)
    db.session.commit()
    return rows


def _client():
    c = app_module.app.test_client()
    with c.session_transaction() as s:
        s["_user_id"] = "1"
        s["user_id"] = "1"
    return c


def test_t1_template_has_suggest_widgets():
    assert 'id="projectNameFilterInput"' in TPL, "工程名称框应有 projectNameFilterInput"
    assert 'id="projectNameDropdown"' in TPL, "应有 projectNameDropdown 候选容器"
    assert 'name="project_name"' in TPL, "提交参数名不得变化"


def test_t2_template_binds_full_interaction():
    for token in (
        "addEventListener('input'",
        "addEventListener('focus'",
        "addEventListener('blur'",
        "addEventListener('keydown'",
        "'ArrowDown'",
        "'ArrowUp'",
        "'Enter'",
        "'Escape'",
        "addEventListener('mousedown'",
    ):
        assert token in TPL, f"工程候选下拉缺少交互绑定：{token}"


def test_t3_template_uses_contracts_api_envelope():
    assert "/api/contracts?keyword=" in TPL, "数据源应为 /api/contracts"
    assert "j.status === 'success'" in TPL, "应按标准信封解析 status"
    assert "j.data.contracts" in TPL, "应按标准信封解析 data.contracts"
    assert "data-pn" in TPL and "pf-item" in TPL, "候选行应带 data-pn/pf-item"


def test_t4_api_matches_project_name_keyword():
    _seed_contracts()
    c = _client()
    r = c.get("/api/contracts?keyword=" + quote("东莞"))
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "success"
    names = {x["project_name"] for x in body["data"]["contracts"]}
    assert names == {"东莞市长安镇变配电工程", "东莞市厚街医院配电改造"}, names


def test_t5_api_matches_contract_no_keyword():
    _seed_contracts()
    c = _client()
    r = c.get("/api/contracts?keyword=HD-SZ")
    assert r.status_code == 200
    names = {x["project_name"] for x in r.get_json()["data"]["contracts"]}
    assert names == {"深圳市福田区照明工程"}, names


def test_t6_api_returns_contract_no_and_empty_case():
    _seed_contracts()
    c = _client()
    r = c.get("/api/contracts")
    body = r.get_json()
    assert body["status"] == "success"
    rows = body["data"]["contracts"]
    assert len(rows) == 3
    assert {"id", "contract_no", "project_name"} <= set(rows[0].keys())
    empty = c.get("/api/contracts?keyword=" + quote("不存在的工程XYZ"))
    assert empty.get_json()["data"]["contracts"] == []
