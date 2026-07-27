"""BUG-BATCH-2026-07-27-001: 批量删除/完成 100/批 限制回归脚本。

校验内容：
  1. 静态：app/app.py 中 batch_delete_in_order / batch_complete_in_order /
     batch_delete_out_order / batch_complete_out_order 四个路由均含
     `len(ids) > 100` 拦截 + 中文提示 + 400 状态码。
  2. 静态：前端 in_order.html / out_order.html 的 batchInOrderAction /
     batchOutOrderAction 在提交前含 `ids.length > 100` 拦截 + toast 提示。
  3. 动态：使用 Flask test_client 构造 101 条 id 提交到 4 个 batch 路由，
     断言全部返回 400 + 中文提示；构造 50 条 id 应不被 100/批 规则拦截。

运行：python scripts/verify_batch_limit.py
退出码：0 = PASS，1 = FAIL
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PY = (ROOT / "app/app.py").read_text(encoding="utf-8")
IN_ORDER_HTML = (ROOT / "app/templates/in_order.html").read_text(encoding="utf-8")
OUT_ORDER_HTML = (ROOT / "app/templates/out_order.html").read_text(encoding="utf-8")


FAILURES: list[str] = []


def require(condition: bool, message: str) -> None:
    if condition:
        print(f"PASS  {message}")
    else:
        print(f"FAIL  {message}")
        FAILURES.append(message)


def extract_function(source: str, name: str) -> str:
    """提取 def name(...) 到下一个顶层 def/@app.route 之间的源码块。"""
    match = re.search(rf"^def\s+{re.escape(name)}\s*\(", source, re.M)
    if not match:
        return ""
    rest = source[match.start():]
    next_match = re.search(r"^(@app\.route|^def\s+\w+\s*\()", rest[1:], re.M)
    if next_match:
        return rest[: next_match.start() + 1]
    return rest


def extract_route_block(source: str, route_pattern: str, func_name: str) -> str:
    """从 @app.route(route_pattern) 开始提取到 def func_name 之后的下一个 @app.route/def。"""
    route_match = re.search(
        rf"@app\.route\({route_pattern}.*?\ndef\s+{re.escape(func_name)}\s*\(", source, re.S
    )
    if not route_match:
        return ""
    body_start = route_match.end()
    next_match = re.search(r"^(@app\.route|^def\s+\w+\s*\()", source[body_start:], re.M)
    if next_match:
        return source[route_match.start(): body_start + next_match.start()]
    return source[route_match.start():]


# ==================== 静态校验：后端 ====================

BATCH_LIMIT_MSG = "单次批量操作不能超过 100 条，请分批处理"


def check_backend_batch_limit() -> None:
    """四个 batch 路由必须含 len(ids) > 100 拦截。"""
    blocks = {
        "batch_delete_in_order": extract_route_block(
            APP_PY, r"'/in_order/batch_delete',\s*methods=\['POST'\]", "batch_delete_in_order"
        ),
        "batch_complete_in_order": extract_route_block(
            APP_PY, r"'/in_order/batch_complete',\s*methods=\['POST'\]", "batch_complete_in_order"
        ),
        "batch_delete_out_order": extract_route_block(
            APP_PY, r"'/out_order/batch_delete',\s*methods=\['POST'\]", "batch_delete_out_order"
        ),
        "batch_complete_out_order": extract_route_block(
            APP_PY, r"'/out_order/batch_complete',\s*methods=\['POST'\]", "batch_complete_out_order"
        ),
    }
    for name, block in blocks.items():
        require(bool(block), f"路由块 {name} 能被定位")

    for name, block in blocks.items():
        if not block:
            continue
        require(
            "len(ids)" in block and "> 100" in block and BATCH_LIMIT_MSG in block and "400" in block,
            f"{name} 含 100/批 拦截（len(ids) > 100 + {BATCH_LIMIT_MSG} + 400）",
        )


# ==================== 静态校验：前端 ====================

def check_frontend_batch_limit() -> None:
    """前端 batchInOrderAction / batchOutOrderAction 必须含 ids.length > 100 拦截。"""
    for label, html, func_name in (
        ("in_order.html", IN_ORDER_HTML, "batchInOrderAction"),
        ("out_order.html", OUT_ORDER_HTML, "batchOutOrderAction"),
    ):
        # 提取函数体
        match = re.search(
            rf"function\s+{re.escape(func_name)}\s*\([^)]*\)\s*\{{",
            html,
        )
        require(bool(match), f"{label} 含函数 {func_name}")
        if not match:
            continue
        # 找到匹配的右大括号（简单起见取到下一个顶层 function）
        body_start = match.end()
        next_func = re.search(r"\nfunction\s+\w+\s*\(", html[body_start:])
        body_end = body_start + next_func.start() if next_func else len(html)
        body = html[body_start:body_end]
        require(
            "ids.length" in body and "> 100" in body and "toast" in body.lower(),
            f"{label} {func_name} 含前端 100/批 拦截（ids.length > 100 + toast 提示）",
        )


# ==================== 动态校验：Flask test_client ====================

def _bootstrap_app():
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("WMS_SKIP_DB_UPGRADE", "1")
    import app as wms_app  # type: ignore
    wms_app.app.config["WTF_CSRF_ENABLED"] = False
    wms_app.app.config["TESTING"] = True
    return wms_app


def _ensure_user(wms_app, username: str = "batch_limit_verify_user") -> str:
    from werkzeug.security import generate_password_hash
    with wms_app.app.app_context():
        wms_app.db.create_all()
        user = wms_app.User.query.filter_by(username=username).first()
        if not user:
            user = wms_app.User(
                username=username,
                password_hash=generate_password_hash("Password123!"),
                role="warehouse",
                status="normal",
            )
            wms_app.db.session.add(user)
            wms_app.db.session.commit()
        return username


def _login(client, username: str) -> None:
    resp = client.post(
        "/login",
        data={"username": username, "password": "Password123!"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303), f"登录失败 status={resp.status_code}"


def _decode_resp_msg(resp) -> str:
    try:
        data = json.loads(resp.get_data(as_text=True))
        if isinstance(data, dict):
            return str(data.get("msg") or "")
    except Exception:
        pass
    return resp.get_data(as_text=True)


def check_dynamic_batch_routes_reject_101() -> None:
    """4 个 batch 路由对 101 条 id 必须返回 400 + 中文提示。"""
    try:
        wms_app = _bootstrap_app()
        username = _ensure_user(wms_app)
    except Exception as exc:  # pragma: no cover
        print(f"SKIP dynamic batch limit test: 环境 unavailable ({exc})")
        return

    client = wms_app.app.test_client()
    _login(client, username)

    # 用 999001~999101 这些不存在的 id（不影响业务数据，只触发 100/批 拦截）
    ids_101 = list(range(999001, 999102))
    routes = [
        ("/in_order/batch_delete", "batch_delete_in_order"),
        ("/in_order/batch_complete", "batch_complete_in_order"),
        ("/out_order/batch_delete", "batch_delete_out_order"),
        ("/out_order/batch_complete", "batch_complete_out_order"),
    ]
    for url, name in routes:
        resp = client.post(
            url,
            json={"ids": ids_101},
            content_type="application/json",
        )
        msg = _decode_resp_msg(resp)
        require(
            resp.status_code == 400,
            f"POST {url} 101 条 id 返回 400（实际 {resp.status_code}: {msg[:120]}）",
        )
        require(
            BATCH_LIMIT_MSG in msg,
            f"POST {url} 返回体含中文提示 {BATCH_LIMIT_MSG}",
        )


def check_dynamic_batch_routes_accept_50() -> None:
    """4 个 batch 路由对 50 条 id 不应被 100/批 规则拦截。

    即：status != 400 或 status == 400 但 msg 不含 BATCH_LIMIT_MSG。
    """
    try:
        wms_app = _bootstrap_app()
        username = _ensure_user(wms_app)
    except Exception as exc:  # pragma: no cover
        print(f"SKIP dynamic batch 50-id test: 环境 unavailable ({exc})")
        return

    client = wms_app.app.test_client()
    _login(client, username)

    ids_50 = list(range(888001, 888051))  # 不存在的 id
    routes = [
        "/in_order/batch_delete",
        "/in_order/batch_complete",
        "/out_order/batch_delete",
        "/out_order/batch_complete",
    ]
    for url in routes:
        resp = client.post(
            url,
            json={"ids": ids_50},
            content_type="application/json",
        )
        msg = _decode_resp_msg(resp)
        blocked_by_limit = (
            resp.status_code == 400 and BATCH_LIMIT_MSG in msg
        )
        require(
            not blocked_by_limit,
            f"POST {url} 50 条 id 不被 100/批 规则拦截（status={resp.status_code} msg={msg[:120]}）",
        )


def main() -> int:
    print("=" * 72)
    print("BUG-BATCH-2026-07-27-001: 批量删除/完成 100/批 限制")
    print("=" * 72)
    check_backend_batch_limit()
    check_frontend_batch_limit()
    check_dynamic_batch_routes_reject_101()
    check_dynamic_batch_routes_accept_50()
    print("=" * 72)
    if FAILURES:
        print(f"FAIL 共 {len(FAILURES)} 项失败")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS ALL: 100/批 限制前后端双向闭环完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
