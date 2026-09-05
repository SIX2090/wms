# -*- coding: utf-8 -*-
"""BUG-2026-09-05-001 回归测试：物料编辑的级联统计查询必须可降级。

原 Bug：
  存量库 inventory_check_item 缺 counted_by / counted_at 列（迁移列只在
  auto_migrate_database 里 ADD，WMS_NO_DB_TOUCH=1 时补不上），
  edit_material 第 5 步「盘点单明细」统计查询抛
  sqlite3.OperationalError: no such column: inventory_check_item.counted_by，
  改个物料名称就 500。

修复（两层）：
  1. app.py ensure_inventory_check_columns()：启动期无条件幂等补列（根因自愈，
     覆盖盘点域全部新增列，见 test_ensure_inventory_check_columns.py）。
  2. material.py：编辑保存时的 5 项「仅统计条数、无冗余字段需同步」的查询
     改为可降级（失败只记日志并跳过该项提示），数据库与代码不同步时不再
     把物料保存打成 500。

覆盖：
  T1. 盘点明细查询抛缺列错误时，编辑物料仍返回 success 且改名生效
  T2. 降级时提示信息中不再包含「盘点单」，其余项照常统计
  T3. 查询正常时不改变原有成功路径（盘点单计数仍在提示里）
"""
from __future__ import annotations

import os
import re
import sqlite3
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

import app as app_module  # noqa: E402
from app import db, Material, User  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402
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


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _missing_column_error(table_col="inventory_check_item.counted_by"):
    """构造与线上一致的 sqlite 缺列 OperationalError。"""
    orig = sqlite3.OperationalError(f"no such column: {table_col}")
    return OperationalError("SELECT inventory_check_item.id FROM inventory_check_item", {}, orig)


class _ExplodingQuery:
    """模拟缺列表查询：filter_by 直接抛缺列错误（与线上 500 一致）。"""

    def filter_by(self, *args, **kwargs):
        raise _missing_column_error()

    def filter(self, *args, **kwargs):
        raise _missing_column_error()


def _edit_material(client, mat, new_name):
    return client.post(f"/material/edit/{mat.id}", data={
        "code": mat.code,
        "name": new_name,
        "spec": mat.spec or "",
        "brand": "",
    })


def test_t1_missing_check_column_does_not_break_material_edit(monkeypatch):
    """盘点明细缺列时编辑物料不 500，改名照常生效。"""
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        mat = Material(code="M001", name="轴承", spec="6204")
        db.session.add(mat)
        db.session.commit()
        mat_id = mat.id

        from app import InventoryCheckItem
        monkeypatch.setattr(InventoryCheckItem, "query", _ExplodingQuery())

        client = app_module.app.test_client()
        _login(client)
        resp = _edit_material(client, mat, "轴承6204")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data["status"] == "success", data

        db.session.expire_all()
        refreshed = db.session.get(Material, mat_id)
        assert refreshed.name == "轴承6204", "缺列不应阻断物料名称保存"


def test_t2_degraded_message_skips_check_items(monkeypatch):
    """降级时提示信息剔除「盘点单」项，其余统计项不受影响。"""
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        mat = Material(code="M002", name="螺母", spec="M8")
        db.session.add(mat)
        db.session.commit()

        from app import InventoryCheckItem
        monkeypatch.setattr(InventoryCheckItem, "query", _ExplodingQuery())

        client = app_module.app.test_client()
        _login(client)
        resp = _edit_material(client, mat, "螺母M8")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "盘点单" not in data["msg"], f"降级项不应出现在提示里: {data['msg']}"
        assert "物料更新成功" in data["msg"]


def test_t3_normal_path_still_reports_check_items():
    """查询正常时保持原行为：盘点单关联条数仍在提示信息中。"""
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        mat = Material(code="M003", name="螺栓", spec="M10")
        db.session.add(mat)
        db.session.commit()

        from app import InventoryCheck, InventoryCheckItem
        check = InventoryCheck(check_no="PC20260905001", status="pending", warehouse="主仓库")
        db.session.add(check)
        db.session.commit()
        db.session.add(InventoryCheckItem(
            inventory_check_id=check.id, material_id=mat.id,
            system_stock=10, actual_stock=10, difference=0,
        ))
        db.session.commit()

        client = app_module.app.test_client()
        _login(client)
        resp = _edit_material(client, mat, "螺栓M10")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert "盘点单 1 条" in data["msg"], f"正常路径应统计盘点单: {data['msg']}"
