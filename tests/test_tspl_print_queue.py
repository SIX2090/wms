# -*- coding: utf-8 -*-
"""PRINT-TEMPLATE-F07：打印队列 claim/next 附带芯烨 TSPL 负载（懒渲染）回归测试。

覆盖：
- _printer_supports_tspl：printer_type='tspl' / 名称关键词 / 普通 / None
- _material_label_data：物料字段映射（含 unit/category/supplier 为空）
- _build_label_tspl_payload：默认模板 + 物料 -> TSPL；无模板 / 空 ids -> None
- _job_tspl_view：非 label -> html；label+TSPL 打印机 -> tspl+payload；无模板回退 html
- agent API v1 claim：label+TSPL 打印机返回 print_method='tspl'+payload（含 SIZE/TEXT/BARCODE）；
  非 TSPL 打印机返回 print_method='html' + payload=None（向后兼容）
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (LabelTemplate, Material, PrintDevice, PrintJob, PrintWorkstation,
                 User, Warehouse, db)  # noqa: E402
from routes.print_queue import (  # noqa: E402
    _build_label_tspl_payload,
    _job_tspl_view,
    _material_label_data,
    _printer_supports_tspl,
)


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    db.session.add(User(
        username="admin", password_hash=generate_password_hash("admin"),
        role="admin", must_change_password=False,
    ))
    wh = Warehouse(code="RWH0", name="默认仓", status="active", is_default=True)
    db.session.add(wh)
    db.session.commit()
    return wh


def _seed_workstation(wh, code="WS-1", token="tok-ws-1"):
    ws = PrintWorkstation(
        code=code, name=code, device_id=f"device-{code}", warehouse_id=wh.id,
        status="online", enabled=True, auth_token=token, last_heartbeat=None,
    )
    db.session.add(ws)
    db.session.commit()
    return ws


def _seed_material(code="WL-6204", name="6204轴承"):
    m = Material(code=code, name=name, spec="20x47x14", stock=100, price=15.5)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_template():
    layout = {"cells": [
        {"row": 0, "col": 0, "field": "name", "style": {"fontSize": 13}},
        {"row": 1, "col": 0, "field": "barcode", "barcodeHeight": 14, "style": {}},
        {"row": 2, "col": 0, "field": "code", "style": {"fontSize": 10}},
    ]}
    t = LabelTemplate(
        name="默认标签", width=90, height=50, cell_width=18, cell_height=8,
        cols=5, rows=6, layout=json.dumps(layout, ensure_ascii=False), is_default=True,
    )
    db.session.add(t)
    db.session.commit()
    return t


def _seed_printer(ws, printer_type="tspl", system_name="Xprinter XP-DT325B",
                  display_name="芯烨标签机"):
    p = PrintDevice(
        workstation_id=ws.id, system_name=system_name, display_name=display_name,
        printer_type=printer_type, status="online", enabled=True,
    )
    db.session.add(p)
    db.session.commit()
    return p


def _seed_label_job(ws, printer, material):
    job = PrintJob(
        job_type="label", target_ids=str(material.id), copies=1, status="pending",
        created_by=1, workstation_id=ws.id,
        printer_id=printer.id if printer else None, source_event="manual",
    )
    db.session.add(job)
    db.session.commit()
    return job


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        _seed()
    c = app_module.app.test_client()
    c.post("/login", data={"username": "admin", "password": "admin"},
           content_type="application/x-www-form-urlencoded")
    yield c


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- _printer_supports_tspl ----------

def test_printer_supports_tspl_by_type():
    p = SimpleNamespace(printer_type="tspl", system_name="Foo", display_name="Bar")
    assert _printer_supports_tspl(p) is True


def test_printer_supports_tspl_by_keyword():
    for name in ("Xprinter XP-420B", "TSC TTP-244", "芯烨标签机", "TSPL Printer"):
        p = SimpleNamespace(printer_type="mixed", system_name=name, display_name="")
        assert _printer_supports_tspl(p) is True, name


def test_printer_supports_tspl_negative():
    assert _printer_supports_tspl(None) is False
    p = SimpleNamespace(printer_type="mixed", system_name="HP LaserJet", display_name="惠普")
    assert _printer_supports_tspl(p) is False


# ---------- _material_label_data ----------

def test_material_label_data():
    m = SimpleNamespace(
        code="C1", name="螺母", spec="M8", stock=50, price=0.5,
        unit=SimpleNamespace(name="个"), category=SimpleNamespace(name="五金"),
        supplier=SimpleNamespace(name="鑫达"),
    )
    d = _material_label_data(m)
    assert d["code"] == "C1" and d["barcode"] == "C1"
    assert d["unit_name"] == "个" and d["category_name"] == "五金"
    assert d["supplier_name"] == "鑫达" and d["stock"] == "50"


def test_material_label_data_none_relations():
    m = SimpleNamespace(code="C2", name="轴承", spec=None, stock=0, price=None,
                        unit=None, category=None, supplier=None)
    d = _material_label_data(m)
    assert d["unit_name"] == "" and d["category_name"] == "" and d["supplier_name"] == ""
    assert d["spec"] == "" and d["stock"] == "0"


# ---------- _build_label_tspl_payload ----------

def test_build_label_tspl_payload(client):
    with app_module.app.app_context():
        _seed_template()
        m = _seed_material()
        payload = _build_label_tspl_payload(str(m.id))
        assert payload is not None
        assert payload.startswith("SIZE 90 mm, 50 mm")
        assert "TEXT" in payload and "BARCODE" in payload
        assert "WL-6204" in payload and "6204轴承" in payload


def test_build_label_tspl_payload_no_template(client):
    with app_module.app.app_context():
        m = _seed_material()
        assert _build_label_tspl_payload(str(m.id)) is None
        assert _build_label_tspl_payload("") is None


# ---------- _job_tspl_view ----------

def test_job_tspl_view_non_label():
    job = SimpleNamespace(job_type="out_order", printer=None, target_ids=None)
    assert _job_tspl_view(job) == {"print_method": "html", "payload": None}


def test_job_tspl_view_tspl(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh)
        printer = _seed_printer(ws, printer_type="tspl")
        _seed_template()
        m = _seed_material()
        job = _seed_label_job(ws, printer, m)
        view = _job_tspl_view(job)
        assert view["print_method"] == "tspl"
        assert view["payload"] and "SIZE" in view["payload"]


def test_job_tspl_view_no_template_fallback(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh)
        printer = _seed_printer(ws, printer_type="tspl")
        m = _seed_material()
        job = _seed_label_job(ws, printer, m)
        # 无模板 -> 回退 html
        assert _job_tspl_view(job) == {"print_method": "html", "payload": None}


# ---------- agent API v1 claim 集成 ----------

def test_agent_claim_returns_tspl_payload(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh)
        printer = _seed_printer(ws, printer_type="tspl")
        _seed_template()
        m = _seed_material()
        job = _seed_label_job(ws, printer, m)
        job_id = job.id
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-ws-1"))
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["job"]["id"] == job_id
    assert body["job"]["print_method"] == "tspl"
    assert body["job"]["payload"].startswith("SIZE")
    assert "BARCODE" in body["job"]["payload"]


def test_agent_claim_html_when_not_tspl_printer(client):
    with app_module.app.app_context():
        wh = Warehouse.query.filter_by(code="RWH0").first()
        ws = _seed_workstation(wh)
        printer = _seed_printer(ws, printer_type="mixed",
                                system_name="HP LaserJet", display_name="惠普")
        _seed_template()
        m = _seed_material()
        _seed_label_job(ws, printer, m)
    resp = client.post("/print_queue/api/v1/claim", json={}, headers=_hdr("tok-ws-1"))
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["job"]["print_method"] == "html"
    assert body["job"]["payload"] is None
