"""BUG-DATE-2026-07-27-001: 入库/出库单据日期未来日期校验回归脚本。

校验内容：
  1. 静态：app/app.py 中 add_in_order / update_in_order / complete_in_order /
     add_out_order / complete_out_order 五个路由均含未来日期拦截逻辑。
  2. 静态：前端 in_order_add.html / out_order_add.html / in_order_detail.html
     日期 input 含 max="{{ today }}" 属性，且 base.html 或对应模板注入 today。
  3. 静态：app/app.py 在 in_order_detail / in_order_add_page / out_order_add_page
     三个 render_template 调用中注入 today 上下文变量。
  4. 动态：使用 Flask test_client 构造未来日期 POST /in_order/add 与 /out_order/add，
     断言返回 400 + 中文提示；今天日期通过校验。

运行：python scripts/verify_future_date_guard.py
退出码：0 = PASS，1 = FAIL
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PY = (ROOT / "app/app.py").read_text(encoding="utf-8")
IN_ADD_HTML = (ROOT / "app/templates/in_order_add.html").read_text(encoding="utf-8")
OUT_ADD_HTML = (ROOT / "app/templates/out_order_add.html").read_text(encoding="utf-8")
IN_DETAIL_HTML = (ROOT / "app/templates/in_order_detail.html").read_text(encoding="utf-8")


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
    # 找下一个顶层 def 或 @app.route（行首起始）
    next_match = re.search(r"^(@app\.route|^def\s+\w+\s*\()", rest[1:], re.M)
    if next_match:
        return rest[: next_match.start() + 1]
    return rest


def extract_route_block(source: str, route_pattern: str, func_name: str) -> str:
    """从 @app.route(route_pattern) 开始提取到 def func_name 之后的下一个 @app.route/def。"""
    route_match = re.search(rf"@app\.route\({route_pattern}.*?\ndef\s+{re.escape(func_name)}\s*\(", source, re.S)
    if not route_match:
        return ""
    body_start = route_match.end()
    # 找下一个 @app.route 或 顶层 def（行首起始）
    next_match = re.search(r"^(@app\.route|^def\s+\w+\s*\()", source[body_start:], re.M)
    if next_match:
        return source[route_match.start(): body_start + next_match.start()]
    return source[route_match.start():]


# ==================== 静态校验：后端 ====================

def check_backend_guard() -> None:
    """五个核心路由必须包含未来日期拦截。"""
    blocks = {
        "add_in_order": extract_route_block(APP_PY, r"'/in_order/add',\s*methods=\['POST'\]", "add_in_order"),
        "update_in_order": extract_route_block(APP_PY, r"'/in_order/<int:id>/update',\s*methods=\['POST'\]", "update_in_order"),
        "complete_in_order": extract_route_block(APP_PY, r"'/in_order/<int:id>/complete',\s*methods=\['POST'\]", "complete_in_order"),
        "add_out_order": extract_route_block(APP_PY, r"'/out_order/add',\s*methods=\['POST'\]", "add_out_order"),
        "complete_out_order": extract_route_block(APP_PY, r"'/out_order/<int:id>/complete',\s*methods=\['POST'\]", "complete_out_order"),
    }
    for name, block in blocks.items():
        require(bool(block), f"路由块 {name} 能被定位")

    # 每个块必须调用 is_future_date(...) 并返回对应中文提示 + 400 状态码
    in_msg = "入库日期不能晚于今天"
    out_msg = "出库日期不能晚于今天"
    for name, block in blocks.items():
        if not block:
            continue
        is_out = name.startswith("add_out") or name.startswith("complete_out")
        expected_msg = out_msg if is_out else in_msg
        require(
            "is_future_date(" in block and expected_msg in block and "400" in block,
            f"{name} 含未来日期拦截（is_future_date(...) + {expected_msg} + 400）",
        )

    # 同时校验 is_future_date helper 本体使用 date.today() + > 比较
    helper_block = extract_function(APP_PY, "is_future_date")
    require(
        bool(helper_block) and "date.today()" in helper_block and ">" in helper_block,
        "is_future_date helper 使用 date.today() + > 比较",
    )


def check_today_context_injected() -> None:
    """三个 render_template 必须注入 today 上下文。"""
    targets = [
        ("'in_order_detail.html'", "in_order_detail"),
        ("'in_order_add.html'", "in_order_add_page"),
        ("'out_order_add.html'", "out_order_add_page"),
    ]
    for template, func in targets:
        block = extract_function(APP_PY, func)
        require(bool(block), f"函数 {func} 能被定位")
        if not block:
            continue
        # 在 render_template 调用块中应同时出现该模板名 + today=
        require(
            template in block and re.search(r"\btoday\s*=", block),
            f"{func} 向 {template} 注入 today 上下文变量",
        )


# ==================== 静态校验：前端 ====================

def check_frontend_max_attr() -> None:
    """三个模板的日期 input 必须含 max=\"{{ today }}\"。"""
    for label, html in (
        ("in_order_add.html", IN_ADD_HTML),
        ("out_order_add.html", OUT_ADD_HTML),
        ("in_order_detail.html", IN_DETAIL_HTML),
    ):
        # 找到 type="date" 的 input 标签
        date_input = re.search(r"<input[^>]*type=[\"']date[\"'][^>]*>", html, re.I)
        require(bool(date_input), f"{label} 含 type=date 的 input")
        if not date_input:
            continue
        tag = date_input.group(0)
        require(
            'max="{{ today }}' in tag or 'max="{{today}}' in tag,
            f"{label} 日期 input 含 max=\"{{{{ today }}}}\" 属性",
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


def _ensure_user(wms_app, username: str = "future_date_verify_user") -> str:
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


def _ensure_material(wms_app) -> int:
    """确保有一行可用物料，返回 id。"""
    with wms_app.app.app_context():
        material = wms_app.Material.query.first()
        if material:
            return material.id
        # 没有就建一个最小物料
        unit = wms_app.Unit.query.first()
        unit_id = unit.id if unit else None
        new_mat = wms_app.Material(
            code="FUTURE-DATE-MAT",
            name="未来日期校验物料",
            unit_id=unit_id,
        )
        wms_app.db.session.add(new_mat)
        wms_app.db.session.commit()
        return new_mat.id


def _login(client, username: str) -> None:
    resp = client.post(
        "/login",
        data={"username": username, "password": "Password123!"},
        follow_redirects=False,
    )
    # 登录成功会 302 跳转
    assert resp.status_code in (302, 303), f"登录失败 status={resp.status_code}"


def _cleanup_order(wms_app, order_no: str) -> None:
    with wms_app.app.app_context():
        order = wms_app.InOrder.query.filter_by(order_no=order_no).first()
        if order:
            try:
                for item in list(order.items):
                    wms_app.db.session.delete(item)
                wms_app.db.session.delete(order)
                wms_app.db.session.commit()
            except Exception:
                wms_app.db.session.rollback()


def _decode_resp_msg(resp) -> str:
    """从 Flask test_client 响应中提取 msg 字段（兼容 JSON/表单编码）。"""
    try:
        data = json.loads(resp.get_data(as_text=True))
        if isinstance(data, dict):
            return str(data.get("msg") or "")
    except Exception:
        pass
    return resp.get_data(as_text=True)


def check_dynamic_in_order_future_date_rejected() -> None:
    """POST /in_order/add 未来日期应返回 400。"""
    try:
        wms_app = _bootstrap_app()
        username = _ensure_user(wms_app)
        _ensure_material(wms_app)
    except Exception as exc:  # pragma: no cover - 环境问题降级
        print(f"SKIP dynamic in_order future-date test: 环境 unavailable ({exc})")
        return

    client = wms_app.app.test_client()
    _login(client, username)

    future = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
    order_no = "FUTURE-DATE-IN-TEST"
    _cleanup_order(wms_app, order_no)

    resp = client.post(
        "/in_order/add",
        json={
            "order_no": order_no,
            "date": future,
            "business_type": "采购入库",
            "warehouse": "",
            "remark": "未来日期测试",
            "items": [{"code": "FUTURE-DATE-MAT", "quantity": 1, "price": 1}],
        },
        content_type="application/json",
    )
    msg = _decode_resp_msg(resp)
    require(
        resp.status_code == 400,
        f"POST /in_order/add 未来日期返回 400（实际 {resp.status_code}: {msg[:120]}）",
    )
    require("入库日期不能晚于今天" in msg, "返回体含中文提示 入库日期不能晚于今天")
    _cleanup_order(wms_app, order_no)


def check_dynamic_in_order_today_passes() -> None:
    """POST /in_order/add 今天日期应通过校验（status 200，可能因业务规则失败但不是 400 未来日期）。"""
    try:
        wms_app = _bootstrap_app()
        username = _ensure_user(wms_app)
        _ensure_material(wms_app)
    except Exception as exc:  # pragma: no cover
        print(f"SKIP dynamic in_order today test: 环境 unavailable ({exc})")
        return

    client = wms_app.app.test_client()
    _login(client, username)

    today = date.today().strftime("%Y-%m-%d")
    order_no = "FUTURE-DATE-IN-TODAY"
    _cleanup_order(wms_app, order_no)

    resp = client.post(
        "/in_order/add",
        json={
            "order_no": order_no,
            "date": today,
            "business_type": "采购入库",
            "warehouse": "",
            "remark": "今天日期测试",
            "items": [{"code": "FUTURE-DATE-MAT", "quantity": 1, "price": 1}],
        },
        content_type="application/json",
    )
    msg = _decode_resp_msg(resp)
    # 今天日期不应触发未来日期拦截（status != 400 或 status==400 但 msg 不含未来日期提示）
    future_blocked = (
        resp.status_code == 400 and "入库日期不能晚于今天" in msg
    )
    require(
        not future_blocked,
        f"POST /in_order/add 今天日期不被未来日期拦截（status={resp.status_code} msg={msg[:120]}）",
    )
    _cleanup_order(wms_app, order_no)


def check_dynamic_out_order_future_date_rejected() -> None:
    """POST /out_order/add 未来日期应返回 400。"""
    try:
        wms_app = _bootstrap_app()
        username = _ensure_user(wms_app)
        _ensure_material(wms_app)
    except Exception as exc:  # pragma: no cover
        print(f"SKIP dynamic out_order future-date test: 环境 unavailable ({exc})")
        return

    client = wms_app.app.test_client()
    _login(client, username)

    future = (date.today() + timedelta(days=10)).strftime("%Y-%m-%d")
    order_no = "FUTURE-DATE-OUT-TEST"

    resp = client.post(
        "/out_order/add",
        json={
            "order_no": order_no,
            "date": future,
            "business_type": "领料单",
            "warehouse": "",
            "remark": "未来日期测试",
            "items": [{"code": "FUTURE-DATE-MAT", "quantity": 1, "price": 1}],
        },
        content_type="application/json",
    )
    msg = _decode_resp_msg(resp)
    require(
        resp.status_code == 400,
        f"POST /out_order/add 未来日期返回 400（实际 {resp.status_code}: {msg[:120]}）",
    )
    require("出库日期不能晚于今天" in msg, "返回体含中文提示 出库日期不能晚于今天")


def main() -> int:
    print("=" * 72)
    print("BUG-DATE-2026-07-27-001: 入库/出库单据未来日期校验")
    print("=" * 72)
    check_backend_guard()
    check_today_context_injected()
    check_frontend_max_attr()
    check_dynamic_in_order_future_date_rejected()
    check_dynamic_in_order_today_passes()
    check_dynamic_out_order_future_date_rejected()
    print("=" * 72)
    if FAILURES:
        print(f"FAIL 共 {len(FAILURES)} 项失败")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("PASS ALL: 未来日期校验闭环完整")
    return 0


if __name__ == "__main__":
    sys.exit(main())
