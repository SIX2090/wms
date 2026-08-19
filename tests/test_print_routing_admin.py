# -*- coding: utf-8 -*-
"""PRINT-ROUTING-F01-P3 回归测试：打印工作台路由管理页（/print_routing）。

覆盖：
- 权限：仅 admin 可访问，仓库人员 403
- 工作站增删改 + 令牌生成/重置（令牌非空且变更）
- 删除保护：存在打印任务/路由规则时拒绝删除工作站；打印机被规则引用时拒绝删除
- 路由规则增删改 + 打印机归属校验（打印机不属于所选工作站时 400）
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

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
from app import (PrintDevice, PrintJob, PrintRouteRule, PrintWorkstation,
                 User, Warehouse, db)  # noqa: E402


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client, username="admin", password="admin"):
    resp = client.post(
        "/login",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code in (200, 302)


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add(User(
            username="wh1", password_hash=generate_password_hash("admin"),
            role="warehouse", must_change_password=False,
        ))
        db.session.add(Warehouse(code="RWH0", name="默认仓", status="active", is_default=True))
        db.session.commit()
    c = app_module.app.test_client()
    _login(c)
    yield c


def _add_workstation(client, code="WS-1"):
    return client.post("/print_routing/workstations", json={
        "code": code, "name": f"{code}工作站", "warehouse_id": None,
    })


def test_print_routing_page_requires_admin(client):
    resp = client.get("/print_routing")
    assert resp.status_code == 200
    assert "打印工作台路由".encode() in resp.data
    c = app_module.app.test_client()
    _login(c, "wh1")
    resp = c.get("/print_routing", headers={"X-Requested-With": "XMLHttpRequest"})
    assert resp.status_code == 403


def test_workstation_crud_and_token(client):
    resp = _add_workstation(client)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    token1 = body["token"]
    assert token1
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        ws_id = ws.id
        assert ws.auth_token == token1
        assert ws.device_id == "ws-WS-1"
    # 重复编码
    resp = _add_workstation(client, code="WS-1")
    assert resp.status_code == 400
    # 编辑：改名 + 停用
    resp = client.post(f"/print_routing/workstations/{ws_id}/edit", json={
        "name": "收货台", "warehouse_id": None, "enabled": False,
    })
    assert resp.status_code == 200
    # 重置令牌
    resp = client.post(f"/print_routing/workstations/{ws_id}/reset_token", json={})
    token2 = resp.get_json()["token"]
    assert token2 and token2 != token1
    # 删除
    resp = client.post(f"/print_routing/workstations/{ws_id}/delete", json={})
    assert resp.status_code == 200
    with app_module.app.app_context():
        assert db.session.get(PrintWorkstation, ws_id) is None


def test_workstation_delete_blocked_by_jobs_or_rules(client):
    _add_workstation(client)
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        ws_id = ws.id
        db.session.add(PrintJob(job_type="out_order", target_id=1, status="pending",
                                created_by=1, workstation_id=ws_id))
        db.session.commit()
    resp = client.post(f"/print_routing/workstations/{ws_id}/delete", json={})
    assert resp.status_code == 400
    with app_module.app.app_context():
        # 清空任务后建规则 → 仍被规则阻断
        PrintJob.query.delete()
        ws = db.session.get(PrintWorkstation, ws_id)
        printer = PrintDevice(workstation_id=ws_id, system_name="P1",
                              display_name="P1", status="online", enabled=True)
        db.session.add(printer)
        db.session.flush()
        db.session.add(PrintRouteRule(name="r", business_event="out_order",
                                      workstation_id=ws_id, printer_id=printer.id))
        db.session.commit()
    resp = client.post(f"/print_routing/workstations/{ws_id}/delete", json={})
    assert resp.status_code == 400


def test_download_agent_prefills_single_workstation_token(client):
    """下载代理部署包：仅一个工作站时 agent_config.json 自动预填其令牌，
    ?ws= 指定编码时同样预填；多工作站且未指定时才用占位符。"""
    import io
    import json as jsonlib
    import zipfile

    _add_workstation(client, code="1")
    resp = client.get("/print_routing/download_agent")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    cfg = jsonlib.loads(zf.read("agent_config.json").decode("utf-8"))
    with app_module.app.app_context():
        token = PrintWorkstation.query.filter_by(code="1").one().auth_token
    assert cfg["token"] == token
    # 指定 ws 编码同样预填
    resp = client.get("/print_routing/download_agent?ws=1")
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    cfg = jsonlib.loads(zf.read("agent_config.json").decode("utf-8"))
    assert cfg["token"] == token
    assert cfg["server_url"].startswith("http")
    # 多工作站且未指定 → 占位符
    _add_workstation(client, code="WS-2")
    resp = client.get("/print_routing/download_agent")
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    cfg = jsonlib.loads(zf.read("agent_config.json").decode("utf-8"))
    assert "在此粘贴工作站令牌" in cfg["token"]


def test_download_agent_bats_autolocate_python(client):
    """BUG-2026-08-19-012：部署包内 run.bat/start.bat 不得裸调 python/pythonw。

    Python 未加入 PATH 的电脑（如 Win7 手动装 3.8 没勾 Add to PATH）双击旧 bat
    即报「'python' 不是内部或外部命令」。新 bat 必须自动定位 Python（PATH 排除
    WindowsApps 假 python → 常见安装目录 → py 启动器），找不到时给中文指引。"""
    import io
    import zipfile

    _add_workstation(client, code="WS-1")
    resp = client.get("/print_routing/download_agent")
    assert resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(resp.data))
    run_bat = zf.read("run.bat").decode("gbk")
    start_bat = zf.read("start.bat").decode("gbk")
    for bat in (run_bat, start_bat):
        # 自动定位链
        assert 'where python.exe' in bat
        assert 'findstr /v /i "WindowsApps"' in bat  # 排除 Win10 商店假 python
        assert '%LocalAppData%\\Programs\\Python\\Python3*\\python.exe' in bat
        assert 'C:\\Python3*\\python.exe' in bat
        assert 'py.exe' in bat  # py 启动器兜底
        # 找不到时的中文指引 + 退出
        assert '未找到 Python' in bat
        assert 'Add Python to PATH' in bat
        assert 'exit /b 1' in bat
        # 不再裸调 python/pythonw（旧 BUG 形态）
        assert '\npython wms_print_agent.py' not in bat
        assert '\npythonw wms_print_agent.py' not in bat
        assert bat.startswith('@echo off\r\n')  # CRLF 行尾
    assert '"%PY%" wms_print_agent.py --config agent_config.json' in run_bat
    # start.bat 用同目录 pythonw 后台运行，取不到时回退 python
    assert '%PY:python.exe=pythonw.exe%' in start_bat
    assert 'if not exist "%PYW%" set "PYW=%PY%"' in start_bat
    assert 'start "" /min "%PYW%"' in start_bat


def test_add_printer_system_name_none_accepted(client):
    """BUG-2026-08-19-005：前端 system_name 留空时传 None，
    PrinterCreateRequest 应接受并自动用打印机名称填充，不应报 422。"""
    _add_workstation(client, code="WS-1")
    with app_module.app.app_context():
        ws_id = PrintWorkstation.query.filter_by(code="WS-1").one().id
    # system_name 传 None（前端留空）
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id,
        "display_name": "HP LaserJet",
        "system_name": None,
        "printer_type": "mixed",
        "enabled": True,
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    # system_name 为空字符串时也应成功
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id,
        "display_name": "HP LaserJet 2",
        "system_name": "",
        "printer_type": "mixed",
        "enabled": True,
    })
    assert resp.status_code == 200


def test_rule_crud_and_printer_ownership(client):
    _add_workstation(client)
    _add_workstation(client, code="WS-2")
    with app_module.app.app_context():
        ws1 = PrintWorkstation.query.filter_by(code="WS-1").one()
        ws2 = PrintWorkstation.query.filter_by(code="WS-2").one()
        p1 = PrintDevice(workstation_id=ws1.id, system_name="P1", display_name="P1",
                         status="online", enabled=True)
        p2 = PrintDevice(workstation_id=ws2.id, system_name="P2", display_name="P2",
                         status="online", enabled=True)
        db.session.add_all([p1, p2])
        db.session.commit()
        ws1_id, ws2_id, p1_id, p2_id = ws1.id, ws2.id, p1.id, p2.id
    # 打印机不属于所选工作站 → 400
    resp = client.post("/print_routing/rules", json={
        "name": "错配规则", "business_event": "out_order",
        "workstation_id": ws1_id, "printer_id": p2_id, "priority": 10,
    })
    assert resp.status_code == 400
    # 正常新增
    resp = client.post("/print_routing/rules", json={
        "name": "主仓领料", "business_event": "out_order", "warehouse_id": None,
        "workstation_id": ws1_id, "printer_id": p1_id, "priority": 10, "enabled": True,
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        rule = PrintRouteRule.query.filter_by(name="主仓领料").one()
        rule_id = rule.id
    # 非法业务事件 → 400
    resp = client.post("/print_routing/rules", json={
        "name": "x", "business_event": "bad_event",
        "workstation_id": ws1_id, "printer_id": p1_id,
    })
    assert resp.status_code == 400
    # 编辑：换工作站+打印机
    resp = client.post(f"/print_routing/rules/{rule_id}/edit", json={
        "name": "主仓领料改", "business_event": "in_order", "warehouse_id": None,
        "workstation_id": ws2_id, "printer_id": p2_id, "priority": 20, "enabled": True,
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        rule = db.session.get(PrintRouteRule, rule_id)
        assert rule.business_event == "in_order"
        assert rule.workstation_id == ws2_id
    # 打印机被规则引用 → 删除被拒
    resp = client.post(f"/print_routing/printers/{p2_id}/delete", json={})
    assert resp.status_code == 400
    # 删除规则后打印机可删
    resp = client.post(f"/print_routing/rules/{rule_id}/delete", json={})
    assert resp.status_code == 200
    resp = client.post(f"/print_routing/printers/{p2_id}/delete", json={})
    assert resp.status_code == 200


def test_printer_edit(client):
    _add_workstation(client)
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        printer = PrintDevice(workstation_id=ws.id, system_name="P1",
                              display_name="P1", status="online", enabled=True)
        db.session.add(printer)
        db.session.commit()
        printer_id = printer.id
    resp = client.post(f"/print_routing/printers/{printer_id}/edit", json={
        "display_name": "收货标签机", "printer_type": "label", "enabled": False,
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        printer = db.session.get(PrintDevice, printer_id)
        assert printer.display_name == "收货标签机"
        assert printer.printer_type == "label"
        assert printer.enabled is False
    # 非法类型 → 400
    resp = client.post(f"/print_routing/printers/{printer_id}/edit", json={
        "display_name": "x", "printer_type": "photo", "enabled": True,
    })
    assert resp.status_code == 400


def test_printer_edit_system_name(client):
    """BUG-2026-08-19-011：编辑打印机可修正 system_name。

    原编辑接口不能改 system_name，手填错系统名的打印机只能删除重建
    （且被路由规则引用时删除也被拒绝）。"""
    _add_workstation(client)
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        p1 = PrintDevice(workstation_id=ws.id, system_name="错名打印机",
                         display_name="标签机1", status="online", enabled=True)
        p2 = PrintDevice(workstation_id=ws.id, system_name="Zebra ZD421",
                         display_name="标签机2", status="online", enabled=True)
        db.session.add_all([p1, p2])
        db.session.commit()
        p1_id, p2_id = p1.id, p2.id
    # 修正 system_name → 成功
    resp = client.post(f"/print_routing/printers/{p1_id}/edit", json={
        "display_name": "标签机1", "system_name": "Zebra ZD421 (副本)",
        "printer_type": "label", "enabled": True,
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        p1 = db.session.get(PrintDevice, p1_id)
        assert p1.system_name == "Zebra ZD421 (副本)"
    # 与同工作站其他打印机重名 → 400
    resp = client.post(f"/print_routing/printers/{p1_id}/edit", json={
        "display_name": "标签机1", "system_name": "Zebra ZD421",
        "printer_type": "label", "enabled": True,
    })
    assert resp.status_code == 400
    # 留空 = 保持不变
    resp = client.post(f"/print_routing/printers/{p1_id}/edit", json={
        "display_name": "标签机1改", "system_name": "",
        "printer_type": "label", "enabled": True,
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        p1 = db.session.get(PrintDevice, p1_id)
        assert p1.system_name == "Zebra ZD421 (副本)"
        assert p1.display_name == "标签机1改"
        assert db.session.get(PrintDevice, p2_id).system_name == "Zebra ZD421"


def test_printer_add_manual(client):
    """手工新增打印机：正常创建 + 重名拒绝 + 非法工作站 404 + 非法类型 400。"""
    _add_workstation(client)
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        ws_id = ws.id
    # 正常新增
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id, "display_name": "HP LaserJet",
        "system_name": "HP LaserJet Pro", "printer_type": "document", "enabled": True,
    })
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "success"
    with app_module.app.app_context():
        printer = PrintDevice.query.filter_by(display_name="HP LaserJet").one()
        printer_id = printer.id
        assert printer.system_name == "HP LaserJet Pro"
        assert printer.printer_type == "document"
        assert printer.status == "offline"
    # 同一工作站下同 system_name 重名 → 400
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id, "display_name": "HP 2",
        "system_name": "HP LaserJet Pro", "printer_type": "mixed",
    })
    assert resp.status_code == 400
    # system_name 留空 → 自动取 display_name
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id, "display_name": "标签机A",
        "printer_type": "label",
    })
    assert resp.status_code == 200
    with app_module.app.app_context():
        p2 = PrintDevice.query.filter_by(display_name="标签机A").one()
        assert p2.system_name == "标签机A"
    # 非法工作站 → 404
    resp = client.post("/print_routing/printers", json={
        "workstation_id": 99999, "display_name": "x", "printer_type": "mixed",
    })
    assert resp.status_code == 404
    # 非法类型 → 400
    resp = client.post("/print_routing/printers", json={
        "workstation_id": ws_id, "display_name": "x", "printer_type": "photo",
    })
    assert resp.status_code == 400


def test_print_routing_page_selfheals_missing_tables(client):
    """BUG-2026-08-19-003：老库缺 print 系列表时 /print_routing 曾抛
    "no such table" 直接 500（页面显示"服务器内部错误"）。修复后路由惰性
    create_all 补齐缺表再重试，页面仍 200 且 print 表被自动重建。"""
    from sqlalchemy import inspect
    from sqlalchemy.exc import NoSuchTableError
    with app_module.app.app_context():
        for model in (PrintRouteRule, PrintJob, PrintDevice, PrintWorkstation):
            try:
                model.__table__.drop(db.engine)
            except NoSuchTableError:
                pass
        db.session.commit()
    resp = client.get("/print_routing")
    assert resp.status_code == 200
    assert "打印工作台路由".encode() in resp.data
    with app_module.app.app_context():
        assert inspect(db.engine).has_table("print_workstation")
        assert inspect(db.engine).has_table("print_route_rule")


def test_known_printers_returns_reported_system_names(client):
    """「新增打印机」系统名称下拉数据源：返回该工作站代理上报/登记过的
    本机系统打印机名列表（去重、排序），避免手填晦涩的系统名。"""
    _add_workstation(client)
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-1").one()
        ws_id = ws.id
        db.session.add(PrintDevice(workstation_id=ws_id, system_name="HP LaserJet 1020",
                                   display_name="HP", status="online", enabled=True))
        db.session.add(PrintDevice(workstation_id=ws_id, system_name="TSC TTP-244",
                                   display_name="TSC", status="online", enabled=True))
        db.session.commit()
    resp = client.get(f"/print_routing/workstations/{ws_id}/printers/known")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    names = body["data"]["known_printers"]
    assert names == ["HP LaserJet 1020", "TSC TTP-244"]
    # 不存在的 id → 404
    resp = client.get("/print_routing/workstations/99999/printers/known")
    assert resp.status_code == 404
