# -*- coding: utf-8 -*-
"""模块6：系统设置 / 用户权限 / 打印 / 备份 深度检查。

结构注意：全程不得维持外层 app_context——Flask 在外层 app ctx 存活时
test_client/test_request_context 会复用同一个 g，login_user() 写入的
g._login_user 会泄漏到后续所有请求（历史踩坑，勿删）。
"""
import re
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import app_module, fresh_env, check, csrf_from, make_client
from app import db, User
from werkzeug.security import generate_password_hash


def login_as(username, password):
    """独立登录，返回 (client, csrf_token)。"""
    cv = app_module.app.test_client()
    page = cv.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    tok = m.group(1) if m else ""
    cv.post("/login", data={"username": username, "password": password,
                            "csrf_token": tok})
    return cv, tok


def mod6_system():
    # ---- 阶段1：seed（ctx 内）----
    with app_module.app.app_context():
        fresh_env()
        viewer = User(username="viewer",
                      password_hash=generate_password_hash("v"),
                      role="finance", must_change_password=False)
        db.session.add(viewer)
        db.session.commit()

    # ---- 阶段2：全部在无外层 ctx 下操作 client ----
    c = make_client()

    # S1. 保存设置 + 开关立即生效
    tok = csrf_from(c, "/system_settings")
    r = c.post("/system_settings/save", data={
        "csrf_token": tok,
        "inventory_alert_enabled": "1",
        "location_management_enabled": "1",
    }, follow_redirects=False)
    with app_module.app.test_request_context("/"):
        from app import (inventory_alert_enabled,
                         location_management_enabled)
        ok = inventory_alert_enabled() and location_management_enabled()
        detail = (f"st={r.status_code} alert={inventory_alert_enabled()} "
                  f"loc={location_management_enabled()}")
    check("设置保存生效", ok, detail)

    # S2. 关闭告警后 dashboard 不 500、口径变 disabled
    # 注意：system_settings/save 是整表语义，未提交的 bool 会被写成 0；
    # prefer_default_warehouse 必须显式带上，否则默认仓库失效 → dashboard 400。
    r = c.post("/system_settings/save", data={
        "csrf_token": tok,
        "inventory_alert_enabled": "0",
        "location_management_enabled": "0",
        "prefer_default_warehouse": "1",
    }, follow_redirects=False)
    rd = c.get("/api/mobile/dashboard")
    detail = f"st={rd.status_code}"
    if rd.status_code == 200:
        body = rd.get_json() or {}
        detail += f" alert_count={body.get('data', {}).get('alert_count')}"
    check("关闭告警后 dashboard 正常 200", rd.status_code == 200, detail)

    # S2b. 重开告警后 dashboard 恢复（同表单语义带上 prefer）
    r = c.post("/system_settings/save", data={
        "csrf_token": tok,
        "inventory_alert_enabled": "1",
        "location_management_enabled": "1",
        "prefer_default_warehouse": "1",
    }, follow_redirects=False)
    rd2 = c.get("/api/mobile/dashboard")
    body2 = (rd2.get_json() or {}).get("data", {})
    check("重开告警后 dashboard 200", rd2.status_code == 200,
          f"st={rd2.status_code} alert_count={body2.get('alert_count')}")

    # ---- 用户权限 ----
    # U1. finance 只读角色：写操作被权限层拦截
    cv, tokv = login_as("viewer", "v")
    r = cv.get("/")
    check("viewer 可看首页", r.status_code == 200, f"st={r.status_code}")
    # 重新取登录后的 token（session 已换）
    tokv2 = csrf_from(cv, "/material")
    r = cv.post("/material/edit/999", data={"csrf_token": tokv2, "code": "X"},
                follow_redirects=False)
    check("viewer 写操作被拦", r.status_code in (301, 302, 403),
          f"st={r.status_code}")
    r = cv.get("/system_settings", follow_redirects=False)
    check("viewer 无权设置页", r.status_code in (301, 302, 403),
          f"st={r.status_code}")

    # U2. 改密后旧密码失效、新密码可用
    c, tok = login_as("admin", "admin")  # 重登录取干净 session
    tok2 = csrf_from(c, "/user/change_password")
    r = c.post("/user/change_password", data={
        "csrf_token": tok2,
        "current_password": "admin",
        "new_password": "newpass123",
        "confirm_password": "newpass123",
    }, follow_redirects=False)
    body = None
    try:
        body = r.get_json()
    except Exception:
        pass
    c2 = app_module.app.test_client()
    page = c2.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page)
    tok3 = m.group(1) if m else ""
    r_old = c2.post("/login", data={"username": "admin", "password": "admin",
                                    "csrf_token": tok3},
                    follow_redirects=False)
    r_new = c2.post("/login", data={"username": "admin",
                                    "password": "newpass123",
                                    "csrf_token": tok3},
                    follow_redirects=False)
    # 登录失败 = 渲染 401（表单带错误提示）；成功 = 302
    check("改密后旧密码失效新密码可用",
          r_new.status_code in (301, 302) and r_old.status_code == 401,
          f"old_st={r_old.status_code} new_st={r_new.status_code} "
          f"chg={r.status_code} msg={(body or {}).get('msg', '')}")

    # ---- 打印 ----
    c, _ = login_as("admin", "newpass123")
    for ep in ["/print_template_center", "/print_queue",
               "/print_template_editor"]:
        r = c.get(ep)
        check(f"{ep} 非500", r.status_code < 500, f"st={r.status_code}")

    # ---- 备份 ----
    for ep in ["/backup", "/backup/list"]:
        r = c.get(ep)
        check(f"{ep} 非500", r.status_code < 500, f"st={r.status_code}")


if __name__ == "__main__":
    mod6_system()
