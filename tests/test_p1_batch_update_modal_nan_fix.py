# -*- coding: utf-8 -*-
"""P1 批量修改：弹窗化 + NaN 修复（入库 / 出库两个页面）。

背景：原有 batchUpdateField 用串行 prompt 收集字段与取值，存在一个会写坏
数据的缺陷——输入非数字时 `parseFloat(value).toFixed(2)` 得到字符串 "NaN"，
被静默写进**所有已录入行**的单价/数量，并进一步污染 calcAmount 的金额与
页面合计。同时 prompt 无法预览「会改多少行」，误操作只能逐行撤销。

本次改造：
  * 弹窗选择字段（入库多支持 批次号 / 有效期）+ 输入值 + 影响行数预览
  * 数字字段走 Number.isFinite 校验，非法直接拒绝
  * 数量必须 > 0、单价不得 < 0
  * 入库侧批次号做长度与公式前缀校验，有效期做格式校验
  * R6：出库页同名函数同根因，一并修复（出库明细无批次/有效期列）

测试用例：
  T1. 两个页面都不再存在 NaN 写入写法，且都改为弹窗 + 校验 + applyBatchUpdate
  T2. 入库页面批次/有效期批量设置存在，且校验分支齐备
  T3. 两个页面均渲染 200（模板无结构性破坏）
  T4. 批量修改不再使用 prompt 串行交互
"""
from __future__ import annotations

import os
import re
import sys
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
from app import db, Warehouse, User  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

IN_ADD = APP_DIR / "templates" / "in_order_add.html"
OUT_ADD = APP_DIR / "templates" / "out_order_add.html"


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
    db.session.add_all([wh, user])
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


def _batch_update_body(path: Path) -> str:
    """抽出页面里 batchUpdateField + applyBatchUpdate 的实现。"""
    src = path.read_text(encoding="utf-8")
    start = src.index("function batchUpdateField(")
    end = src.index("function applyBatchUpdate(")
    tail = src[end:]
    # applyBatchUpdate 的函数体（按大括号配平）
    idx = tail.index("{")
    depth = 0
    for pos in range(idx, len(tail)):
        if tail[pos] == "{":
            depth += 1
        elif tail[pos] == "}":
            depth -= 1
            if depth == 0:
                return src[start:end] + tail[:pos + 1]
    raise AssertionError(f"{path} 未能抽出 applyBatchUpdate")


def test_T1_no_nan_write_and_modal_flow_present():
    """两个页面都不再有 NaN 写入写法；都已改为弹窗 + 独立应用函数。"""
    for path in (IN_ADD, OUT_ADD):
        src = path.read_text(encoding="utf-8")
        assert "parseFloat(value).toFixed" not in src, \
            f"{path.name} 不应再有 parseFloat(value).toFixed 的 NaN 写入写法"
        body = _batch_update_body(path)
        assert "Number.isFinite(num)" in body, f"{path.name} 应对数字做 isFinite 校验"
        assert "batchUpdateModal" in body, f"{path.name} 应用弹窗实现批量修改"
        assert "applyBatchUpdate" in body, f"{path.name} 应拆分出独立的应用函数"
        assert "行已录入明细" in body or "将修改" in body, f"{path.name} 应有影响行数预览"


def test_T2_in_order_supports_batch_and_expiry_bulk_set():
    """入库页批量修改支持批次号 / 有效期，并带长度、公式前缀与格式校验。"""
    body = _batch_update_body(IN_ADD)
    assert "batch_no" in body and "expiry_date" in body, "入库批量修改应支持批次号与有效期"
    assert "批次号不能超过 50 个字符" in body, "批次号应有长度校验"
    assert "避免被表格软件当公式执行" in body, "批次号应拒绝公式前缀"
    assert re.search(r"\\d\{4\}-\\d\{2\}-\\d\{2\}", body), "有效期应有 YYYY-MM-DD 格式校验"


def test_T3_both_add_pages_render():
    """两个新增页仍渲染 200（弹窗模板无结构性破坏）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
    client = _make_client()
    for url in ("/in_order/add", "/out_order/add"):
        resp = client.get(url)
        assert resp.status_code == 200, f"{url} 返回 {resp.status_code}，应为 200"
        assert "materialTableBody" in resp.data.decode("utf-8", errors="replace")


def test_T4_no_prompt_based_batch_update_left():
    """批量修改不再使用 prompt 串行交互（无法预览、不能校验）。"""
    for path in (IN_ADD, OUT_ADD):
        body = _batch_update_body(path)
        assert "prompt(" not in body, f"{path.name} 的批量修改不应再用 prompt 交互"
