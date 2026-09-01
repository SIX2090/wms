# -*- coding: utf-8 -*-
"""AI-WMS-FINANCE-ROLE 回归：财务（finance）只读角色。

业务背景：WMS 主要由仓管一人做单，财务/采购/生产/销售只需要「看到记录」——
看报表、查单据、导 Excel，不参与任何录入。此前没有财务角色，财务只能借仓管
账号登录，等于把出入库权限一起交出去了。

本测试覆盖财务角色的行为契约：
- 可看：报表中心、库存报表、入库/出库明细、手工查询（全部 GET）
- 可导：/report/inout/export 导出 Excel
- 可查：/api/query/search 这类不落库的 POST 查询（白名单放行）
- 不可写：入库/出库/期初库存导入等所有 POST/PUT/PATCH/DELETE 一律 403，
  包括只挂了 @login_required、没有角色校验的写路由（/opening_stock/import）
- 不可看：用户管理、系统设置等管理页
- 可用：退出登录、修改自己的密码
"""
from __future__ import annotations

import io
import os
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
from app import db  # noqa: E402
from utils import (  # noqa: E402
    ASSIGNABLE_ROLES, READ_ONLY_ALLOWED_POST_ENDPOINTS, READ_ONLY_ROLES,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()


def _make_user(username, role, password="pass1234"):
    from werkzeug.security import generate_password_hash
    from app import User
    with app_module.app.app_context():
        user = User(username=username, password_hash=generate_password_hash(password),
                    role=role, must_change_password=False)
        db.session.add(user)
        db.session.commit()
    return user


def _seed_base():
    _reset_db()
    _make_user("admin", "admin", "admin")
    _make_user("finance01", "finance")
    # 一个仓管账号用于对照（finance 能看的，warehouse 也能看）
    _make_user("wh01", "warehouse")


def _login(client, username="finance01", password="pass1234"):
    resp = client.post(
        "/login",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code in (200, 302), f"登录失败: {resp.status_code}"


def _seed_material():
    """给查询类用例准备一个物料。"""
    from app import Material, Unit, MaterialCategory, Supplier, Warehouse
    from datetime import datetime
    with app_module.app.app_context():
        u = Unit(code="U-PC", name="个")
        c = MaterialCategory(code="C-ELEC", name="电气")
        s = Supplier(code="S-001", name="测试供应商")
        wh = Warehouse(name="主仓", code="WH01", status="active")
        db.session.add_all([u, c, s, wh])
        db.session.flush()
        m = Material(code="M-001", name="电线", spec="2.5mm2",
                     unit_id=u.id, category_id=c.id, supplier_id=s.id,
                     created_at=datetime.now())
        db.session.add(m)
        db.session.commit()
    return m, wh


# ==================== 只读角色定义 ====================

def test_finance_is_read_only_role():
    assert "finance" in READ_ONLY_ROLES
    assert "finance" in ASSIGNABLE_ROLES
    assert READ_ONLY_ROLES.issubset(ASSIGNABLE_ROLES)


def test_read_only_post_whitelist_only_contains_query_export():
    # 白名单里只能有「查询/导出」类端点，绝不能出现会落库的写操作
    for ep in READ_ONLY_ALLOWED_POST_ENDPOINTS:
        assert "export" in ep or "search" in ep or "query" in ep, ep


def test_ai_role_label_finance():
    from app import _ai_role_label
    assert _ai_role_label("finance") == "财务"


# ==================== 可看（GET 只读页面） ====================

def test_finance_can_view_report_center():
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    for url in ("/report", "/report/dashboard", "/report/view/inventory",
                "/report/view/summary", "/report/view/ledger",
                "/report/view/warehouse_monthly"):
        resp = client.get(url)
        assert resp.status_code == 200, f"finance 应能访问 {url}，实际 {resp.status_code}"


def test_finance_can_view_order_lists():
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    for url in ("/in_order", "/out_order", "/mobile/scan?mode=query",
                "/material", "/stock_query"):
        resp = client.get(url)
        assert resp.status_code == 200, f"finance 应能访问 {url}，实际 {resp.status_code}"


# ==================== 可导（Excel 导出） ====================

def test_finance_can_export_excel():
    _seed_base()
    _seed_material()
    client = app_module.app.test_client()
    _login(client)
    resp = client.get("/report/inout/export?report_type=in&warehouse_id=1")
    assert resp.status_code == 200, f"finance 应能导出 Excel，实际 {resp.status_code}"
    assert "application/vnd" in (resp.content_type or ""), resp.content_type


# ==================== 可查（不落库的 POST） ====================

def test_finance_can_post_query_search():
    _seed_base()
    _seed_material()
    client = app_module.app.test_client()
    _login(client)
    resp = client.post("/api/query/search", data={"keyword": "电线", "warehouse_id": "1"})
    assert resp.status_code == 200, f"finance 应能查询物料，实际 {resp.status_code}"


# ==================== 不可写（全局写拦截） ====================

def test_finance_blocked_from_order_add():
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    # 页面 POST 被拒时是 302 重定向（flash 后回首页），API POST 是 403；
    # 两者都算拦截成功——关键是绝不能 200 成功执行。
    for url in ("/in_order/add", "/out_order/add", "/other_in_order/add",
                "/check/add", "/transfer/add", "/adjustment/add"):
        resp = client.post(url, data={})
        assert resp.status_code != 200, f"finance POST {url} 不应成功，实际 {resp.status_code}"
        assert resp.status_code in (302, 403), f"finance POST {url} 意外状态 {resp.status_code}"


def test_finance_blocked_from_batch_import():
    # 批量导入是真正的库存写入口（/import/in_order、/import/out_order 会落库）
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    for url in ("/import/in_order", "/import/out_order", "/user/import",
                "/label_template/import"):
        resp = client.post(
            url,
            data={"file": (io.BytesIO(b"xlsx"), "x.xlsx")},
            content_type="multipart/form-data",
        )
        assert resp.status_code in (302, 403), (
            f"finance POST {url} 应被拦截，实际 {resp.status_code}"
        )


def test_finance_blocked_from_mobile_api():
    # native_api 走 bearer token + api_role_required 白名单，
    # 但 before_request 的只读拦截必须在视图之前生效
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    for url in ("/api/inbound", "/api/outbound", "/api/check"):
        resp = client.post(url, json={})
        assert resp.status_code == 403, f"finance POST {url} 应 403，实际 {resp.status_code}"


def test_finance_blocked_from_opening_stock_import():
    # 关键回归：/opening_stock/import 只挂了 @login_required、没有任何角色校验，
    # 且是期初库存（底账）的导入入口。光加角色枚举挡不住它，
    # 必须靠 before_request 的只读写拦截兜底。
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    resp = client.post(
        "/opening_stock/import",
        data={"file": (io.BytesIO(b"xlsx"), "opening.xlsx")},
        content_type="multipart/form-data",
    )
    assert resp.status_code in (302, 403), (
        f"finance POST /opening_stock/import 必须被拦截（无角色保护写路由的兜底），"
        f"实际 {resp.status_code}"
    )


def test_finance_blocked_from_put_delete():
    _seed_base()
    _seed_material()
    client = app_module.app.test_client()
    _login(client)
    # 找一个 PUT 语义的路由兜底验证（material update 类）。
    # 拦截结果可能是 403（JSON 请求）或 302/404/405（路由不匹配被重定向），
    # 核心是绝不能 200 成功执行。
    resp = client.put("/api/material/1", json={"name": "x"})
    assert resp.status_code != 200, resp.status_code
    resp = client.delete("/material/1")
    assert resp.status_code != 200, resp.status_code


def test_finance_blocked_from_batch_status_update():
    # 批量改状态属于写操作
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    resp = client.post("/subcontract/batch_update_status", json={})
    assert resp.status_code == 403, f"实际 {resp.status_code}"


# ==================== 不可看（管理页） ====================

def test_finance_denied_admin_pages():
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    for url in ("/user", "/system_settings", "/backup", "/print_routing",
                "/print_alerts", "/operation_audit"):
        resp = client.get(url)
        assert resp.status_code == 302 or resp.status_code == 403, (
            f"finance 访问管理页 {url} 应被拒绝，实际 {resp.status_code}"
        )


# ==================== 基础体验 ====================

def test_finance_can_logout_and_change_password():
    _seed_base()
    client = app_module.app.test_client()
    _login(client)
    resp = client.get("/user/change_password")
    assert resp.status_code == 200, f"finance 应能打开改密页，实际 {resp.status_code}"
    resp = client.post(
        "/user/change_password",
        data={"current_password": "pass1234", "new_password": "pass5678",
              "confirm_password": "pass5678"},
    )
    assert resp.status_code == 200, f"finance 应能改自己的密码，实际 {resp.status_code}"
    data = resp.get_json()
    assert data and data.get("status") == "success", resp.get_data(as_text=True)[:200]
    resp = client.get("/logout")
    assert resp.status_code in (200, 302)
    # 改密后旧密码登录应失败、新密码应成功
    resp = client.post("/login", data={"username": "finance01", "password": "pass1234"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code != 200  # 旧密码不能直接登录成功
    resp = client.post("/login", data={"username": "finance01", "password": "pass5678"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code in (200, 302)


def test_admin_can_create_finance_user():
    # 管理员建号时角色必须合法（ASSIGNABLE_ROLES 含 finance）
    _seed_base()
    client = app_module.app.test_client()
    _login(client, username="admin", password="admin")
    resp = client.post(
        "/user/add",
        data={"username": "finance02", "password": "pass1234", "role": "finance"},
    )
    assert resp.status_code == 200, f"admin 应能创建财务账号，实际 {resp.status_code}"
    data = resp.get_json()
    assert data and data.get("status") == "success", resp.get_data(as_text=True)[:200]


def test_admin_can_edit_user_to_finance():
    _seed_base()
    _make_user("to_finance", "user")
    client = app_module.app.test_client()
    _login(client, username="admin", password="admin")
    resp = client.post(
        "/user/4/edit",
        data={"username": "to_finance", "role": "finance", "status": "normal"},
    )
    assert resp.status_code == 200, f"admin 应能把用户改为财务角色，实际 {resp.status_code}"
    data = resp.get_json()
    assert data and data.get("status") == "success", resp.get_data(as_text=True)[:200]
