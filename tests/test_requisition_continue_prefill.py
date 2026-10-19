# -*- coding: utf-8 -*-
"""UI-REQUISITION-CONTINUE-001-F01 回归：完成领料后「完成并新增」带表头开新单。

需求：库存管理 → 领料单，完成一张领料单后要能立刻新增下一张，避免重复选
仓库/填工单，提高录单效率（连续录单）。

实现：
1. 列表页「完成」按钮弹确认框，确认按钮为「完成并新增」；选择它则在完成成功后
   跳转 `/requisition/add`，并把本单表头（warehouse / bom_id /
   production_order / picker / purpose）作为 query 参数带过去。
2. `_render_requisition_form()` 在**新建**时白名单回填这些参数；
   编辑/查看既有单据一律以数据库记录为准（query 参数不得覆盖既有单据）。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import BOM, ProductionRequisition, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

TEMPLATE = ROOT / "app/templates/requisition.html"


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add(Warehouse(code="WHA", name="仓库A", is_default=True, status="active"))
        db.session.add(BOM(bom_no="BOM-9", product_code="P9", product_name="产品九"))
        db.session.commit()
    c = app_module.app.test_client()
    c.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    yield c


def _selected_option_values(html):
    """返回所有 <option ... selected ...> 的 value。"""
    values = []
    for chunk in html.split("<option")[1:]:
        head = chunk.split(">", 1)[0]
        if "selected" in head and 'value="' in head:
            values.append(head.split('value="', 1)[1].split('"', 1)[0])
    return values


class TestNewFormPrefill:

    def test_warehouse_id_prefill_and_fresh_document(self, client):
        with app_module.app.app_context():
            other = Warehouse(code='WHB', name='仓库B', status='active')
            db.session.add(other)
            db.session.commit()
            wid = str(other.id)
            before = ProductionRequisition.query.count()
        html = client.get('/requisition/add', query_string={
            'warehouse_id': wid, 'order_id': '999', 'date': '2001-01-01',
        }).get_data(as_text=True)
        assert wid in _selected_option_values(html)
        assert 'value="2001-01-01"' not in html
        assert 'name="order_id" value=""' in html
        with app_module.app.app_context():
            assert ProductionRequisition.query.count() == before

    def test_new_form_prefills_header_from_query(self, client):
        """新建页按 query 参数回填表头（连续录单的关键）。"""
        with app_module.app.app_context():
            bom_id = BOM.query.filter_by(bom_no="BOM-9").first().id
            warehouse_id = str(Warehouse.query.filter_by(name="仓库A").first().id)
        resp = client.get(
            "/requisition/add",
            query_string={
                "warehouse": "仓库A",
                "bom_id": bom_id,
                "production_order": "PO-CONT-1",
                "picker": "李四",
                "purpose": "连续领料",
            },
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        html = resp.get_data(as_text=True)
        assert 'value="PO-CONT-1"' in html            # 工单
        assert 'value="李四"' in html                  # 领料人
        assert 'value="连续领料"' in html              # 用途
        assert f'value="{bom_id}" selected' in html    # 关联 BOM
        assert warehouse_id in _selected_option_values(html)  # 仓库按名称命中并选中

    def test_new_form_without_query_still_renders(self, client):
        """无 query 参数时行为不变（回填逻辑不得报错）。"""
        resp = client.get("/requisition/add")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        html = resp.get_data(as_text=True)
        assert 'value="PO-CONT-1"' not in html
        assert 'name="production_order"' in html

    def test_existing_document_ignores_query_prefill(self, client):
        """编辑既有单据时 query 参数不得覆盖数据库内容（防串单）。"""
        with app_module.app.app_context():
            requisition = ProductionRequisition(
                req_no="REQ-EXIST-1",
                production_order="PO-REAL",
                purpose="真实用途",
                picker="王五",
                warehouse="仓库A",
                location="",
                status="pending",
            )
            db.session.add(requisition)
            db.session.commit()
            req_id = requisition.id
        resp = client.get(
            f"/requisition/{req_id}",
            query_string={"production_order": "PO-HACK", "purpose": "注入用途"},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        html = resp.get_data(as_text=True)
        assert 'value="PO-REAL"' in html
        assert 'value="PO-HACK"' not in html
        assert 'value="注入用途"' not in html


class TestListPageContinueMarkup:

    def test_complete_button_carries_header_data_attributes(self):
        """完成按钮必须携带表头 data-*，前端才能带参开新单。"""
        source = TEMPLATE.read_text(encoding="utf-8")
        assert "complete-btn" in source
        for attribute in ("data-warehouse", "data-bom-id", "data-production-order",
                          "data-picker", "data-purpose"):
            assert attribute in source, attribute
        assert "buildRequisitionContinueUrl" in source
        assert "完成并新增" in source


def _extract(source, start_marker, end_marker):
    assert start_marker in source, start_marker
    body = source.split(start_marker, 1)[1]
    assert end_marker in body, end_marker
    return start_marker + body.split(end_marker, 1)[0]


@pytest.mark.parametrize("choice", ["ok", "cancel", "error", "network_error"])
def test_requisition_continue_navigation(choice):
    """跑列表页真实 JS：完成并新增 → 带表头参数跳新单；失败或取消不跳转。"""
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for browser callback execution")
    source = TEMPLATE.read_text(encoding="utf-8")
    helper = _extract(source,
                      "function buildRequisitionContinueUrl(button) {",
                      "\ndocument.querySelectorAll('.complete-btn')")
    handler = _extract(source,
                       "document.querySelectorAll('.complete-btn').forEach(function(button) {",
                       "\ndocument.querySelectorAll('.revert-btn')")

    prelude = """
const requisitionUrls = {add: '/requisition/add', complete: '/requisition/0/complete'};
const CHOICE = %s;
let reloaded = 0, fetched = [], confirmOptions = null;
const location = {reload: function(){ reloaded += 1; }};
const window = {location: {href: ''}};
function urlWithId(url, id) { return url.replace(/\\/0(?=\\/|$)/, '/' + id); }
function showToast() {}
function showConfirm(message, options) {
    confirmOptions = options;
    // 取消 resolve(false)，确认返回 truthy 值
    return Promise.resolve(CHOICE === 'cancel' ? false : CHOICE);
}
const WMS = {api: {post: function(url) {
    fetched.push(url);
    if (CHOICE === 'network_error') return Promise.reject(new Error('network'));
    return Promise.resolve({status: CHOICE === 'error' ? 'error' : 'success'});
}}};
function setTimeout(fn) { fn(); }
""" % json.dumps(choice)

    after = """
let clickHandler = null;
const fakeButton = {
    dataset: {
        id: '7',
        warehouse: '仓库A',
        bomId: '3',
        productionOrder: 'PO-CONT-1',
        picker: '李四',
        purpose: '连续领料'
    },
    addEventListener: function(name, fn) { if (name === 'click') clickHandler = fn; }
};
global.document = {
    querySelectorAll: function(selector) { return selector === '.complete-btn' ? [fakeButton] : []; }
};
""" + handler + """
clickHandler.call(fakeButton);
setImmediate(function(){
    process.stdout.write(JSON.stringify({
        confirmOptions: confirmOptions,
        fetched: fetched,
        href: window.location.href,
        reloaded: reloaded
    }));
});
"""
    script = prelude + helper + after
    result = subprocess.run([node, "-e", script], text=True, encoding="utf-8",
                            capture_output=True, check=True)
    actual = json.loads(result.stdout)
    assert actual["confirmOptions"]["okText"] == "完成并新增"
    if choice == "cancel":
        assert actual["fetched"] == []
        assert actual["href"] == ""
        assert actual["reloaded"] == 0
        return
    assert actual["fetched"] == ["/requisition/7/complete"]
    if choice == "ok":
        parsed = urlparse(actual["href"])
        assert parsed.path == "/requisition/add"
        assert parse_qs(parsed.query) == {
            "warehouse": ["仓库A"],
            "bom_id": ["3"],
            "production_order": ["PO-CONT-1"],
            "picker": ["李四"],
            "purpose": ["连续领料"],
        }
        assert actual["reloaded"] == 0
    else:
        assert actual["href"] == ""
        assert actual["reloaded"] == 0
