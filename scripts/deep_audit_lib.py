# -*- coding: utf-8 -*-
"""WMS 深度检测脚手架：全模块 E2E 探测的公共环境。

用法：PYTHONPATH=/tmp/wms_deps:<repo>/app WMS_ALLOW_INSECURE_COOKIE=1 \
      python3 <this> <module_name>
每个模块函数独立建库、独立 seed、独立 client，避免互相污染。
"""
import os
import re
import sys
import json
from pathlib import Path

REPO = Path("/Coze/Drive/扣子/wms")
APP_DIR = REPO / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
if not hasattr(app_module, "__path__"):
    app_module.__path__ = [str(APP_DIR)]
app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Warehouse, User, add_stock,
    StockTransaction,
)
from werkzeug.security import generate_password_hash  # noqa: E402


def fresh_env(two_warehouses=True):
    """重建内存库并 seed 基础数据，返回 (admin, mat)。"""
    db.drop_all()
    db.create_all()
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    rows = [Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WHA", name="A仓", is_default=True, status="active"),
            admin]
    if two_warehouses:
        rows.append(Warehouse(code="WHB", name="B仓", status="active"))
    db.session.add_all(rows)
    db.session.commit()
    app_module.set_system_setting("inventory_alert_enabled", "1")
    mat = Material(code="M001", name="铜排", spec="T2",
                   category_id=1, unit_id=1, stock=0, price=10, min_stock=5)
    db.session.add(mat)
    db.session.commit()
    return admin, mat


def stock_in(user, mat, qty, warehouse="A仓", ttype="in"):
    with app_module.app.test_request_context("/"):
        from flask_login import login_user
        login_user(user)
        ok, err = add_stock(mat, qty, transaction_type=ttype, warehouse=warehouse)
        assert ok, err
        db.session.commit()


def make_client():
    c = app_module.app.test_client()
    page = c.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    c.post("/login", data={"username": "admin", "password": "admin",
                           "csrf_token": m.group(1)})
    return c


def get_json(c, path):
    r = c.get(path)
    try:
        return r.status_code, json.loads(r.get_data(as_text=True))
    except Exception:
        return r.status_code, None


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    return cond


def csrf_from(c, path):
    html = c.get(path).get_data(as_text=True)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    return m.group(1) if m else ""
