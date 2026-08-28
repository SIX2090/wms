# -*- coding: utf-8 -*-
"""BUG-2026-08-28-003 回归：报表查询接口 /report/api/ 异常回 JSON。

背景：库存台账（/report/view/ledger）点击"查询"后前端发
``fetch('/report/api/ledger?warehouse_id=...&material_code=101009')``，
浏览器默认 Accept: */*、不带 X-Requested-With；视图一旦抛错（如物料参数解析
异常、stock_transaction 查询抛 OperationalError 等），旧版
``wants_json_error_response()`` 既不以 /api/ 也不以 /mobile/api/ 起头，
``handle_exception`` 回落到纯文本 ``'服务器内部错误，请稍后重试'``。
前端 ``await response.json()`` 抛 ``SyntaxError: Unexpected token '服'...``，
根因被吞、用户看不到具体错；表格行渲染 ``Unexpected token '服'，服务器内部错误，请稍后重试' is not valid JSON``。

修复：``wants_json_error_response()`` 显式识别 ``/report/api/`` 前缀，
错误处理器据此回 JSON；同步对意外 4xx/5xx 仍可经 404/CSRF/500 处理器一致处理。
非 /api/ 路径（/report/view/<type> 渲染页、/report/print 等下载/HTML 路径）
保持原 HTML/纯文本行为不变。

验收：
T1. GET /report/api/<type> 触发 500 → 响应是 JSON、status=error、含中文 msg，
    body 不再以"服"开头。
T2. wants_json_error_response() 对 /report/api/ledger 的 GET 请求识别为 True，
    对 /report/print (HTML 路径) 仍识别为 False，避免意外把报表 HTML 也 JSON 化。
T3. 错误处理器自身 rollback 失败也不得逃出（与 BUG-2026-08-05-005 一致）。
T4. 浏览器 fetch 默认头（Accept=*/*，无 X-Requested-With）下路径同样命中，
    模拟截图场景复现前后差异。
"""
from __future__ import annotations

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

# 必须关闭 TESTING，否则异常直接传播给测试客户端，走不到错误处理器
app_module.app.config["TESTING"] = False
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _register_raising_route():
    """注册一个 report/api 下必抛异常的测试路由（仅测试用）。"""
    if "__test_report_api_raise" in app_module.app.view_functions:
        return

    @app_module.app.route("/report/api/__test_report_api_raise", methods=["GET"])
    def __test_report_api_raise():
        raise RuntimeError("boom-from-report-api")


_register_raising_route()


def _client():
    return app_module.app.test_client()


class TestReportApiJsonError:
    def test_500_returns_json_for_report_api(self):
        """T1：GET /report/api/<type> 触发 500 时必须返回 JSON，body 不再以"服"开头。"""
        resp = _client().get("/report/api/__test_report_api_raise")
        assert resp.status_code == 500, f"status 应为 500，实际 {resp.status_code}"
        body = resp.get_data(as_text=True)
        assert resp.is_json, (
            "/report/api/ 5xx 必须 JSON 化，但收到 body: "
            + body[:200]
        )
        data = resp.get_json()
        assert data["status"] == "error"
        assert "服务器内部错误" in data["msg"]
        # 关键断言：body 不再被中文纯文本"服"开头污染，前端 r.json() 不会再抛
        # "Unexpected token '服'...is not valid JSON"
        assert not body.lstrip().startswith("服"), (
            "BUG-2026-08-28-003 复发：/report/api/ 仍返回纯文本，body="
            + body[:200]
        )

    def test_wants_json_detects_report_api_prefix(self):
        """T2a：wants_json_error_response 识别 /report/api/ 前缀。"""
        with app_module.app.test_request_context(
            "/report/api/ledger",
            method="GET",
            headers={"Accept": "*/*"},
        ):
            assert app_module.wants_json_error_response() is True, (
                "/report/api/ 前缀必须被识别为 AJAX JSON 调用"
            )

    def test_wants_json_keeps_non_api_paths_as_html(self):
        """T2b：/report/print、/report/view/<type>、/report/<type>/print_excel
        等非 /api/ 路径保持非 JSON 行为，避免把报表 HTML/下载意外 JSON 化。"""
        for path in (
            "/report/view/ledger",
            "/report/print",
            "/report/inout/print",
            "/report/stock/print",
            "/report/inventory/print_excel",
        ):
            with app_module.app.test_request_context(
                path, method="GET", headers={"Accept": "text/html,*/*"}
            ):
                assert app_module.wants_json_error_response() is False, (
                    f"{path} 不应被识别为 JSON 调用，否则浏览器渲染会失败"
                )

    def test_browser_default_headers_still_routed_to_json(self):
        """T3：浏览器默认 Accept=*/*、无 X-Requested-With 的 fetch
        （截图场景）依然命中 JSON 分支。"""
        with app_module.app.test_request_context(
            "/report/api/ledger?warehouse_id=1&material_code=101009"
            "&start_date=2026-08-01&end_date=2026-08-28",
            method="GET",
            headers={
                # 与截图场景一致：浏览器 fetch 默认头
                "Accept": "*/*",
            },
        ):
            assert app_module.wants_json_error_response() is True

    def test_500_json_even_when_rollback_fails(self):
        """T4：db.session.rollback 抛错时错误处理路径仍能完成（与 BUG-2026-08-05-005 同源）。

        ``_db_safe_rollback`` 内部 try/except 已经把 rollback 失败吞掉，
        验证这条路径在 /report/api/ 下仍能正常返回 JSON 即可。
        """
        from app import db  # noqa: E402

        original = db.session.rollback

        def _broken_rollback(*a, **kw):
            raise RuntimeError("rollback broken")

        db.session.rollback = _broken_rollback  # type: ignore[assignment]
        try:
            resp = _client().get("/report/api/__test_report_api_raise")
        finally:
            db.session.rollback = original  # type: ignore[assignment]
        body = resp.get_data(as_text=True)
        assert resp.status_code == 500
        assert resp.is_json, (
            "错误处理器自身 rollback 失败时也必须返回 JSON，body=" + body[:200]
        )
        assert resp.get_json()["status"] == "error"
        assert "服务器内部错误" in resp.get_json()["msg"]
