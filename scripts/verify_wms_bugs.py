from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def function_body(source: str, name: str) -> str:
    m = re.search(rf"^([ \t]*)def\s+{re.escape(name)}\s*\([^)]*\):", source, re.M)
    if not m:
        return ""
    indent = len(m.group(1))
    # 边界取下一个同缩进或更浅缩进的 def（嵌套 def 不截断函数体）。
    rest = source[m.end() :]
    nm = re.search(rf"^[ \t]{{0,{indent}}}def\s+\w+\s*\(", rest, re.M)
    end = m.end() + nm.start() if nm else len(source)
    return source[m.start() : end]


def routes_source() -> str:
    """拼接 app/app.py 与 app/routes/*.py 的源码，供函数体/路由静态检索使用。

    路由拆分后，业务函数已从 app.py 迁移到 app/routes/ 各模块，
    静态检查需同时在两处查找，避免误报。
    """
    parts = [read_text("app/app.py")]
    for p in sorted((ROOT / "app" / "routes").glob("*.py")):
        parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def app_function_body(name: str) -> str:
    """在 app.py 与 app/routes/*.py 中查找函数体，返回首个匹配。"""
    for src in (read_text("app/app.py"), routes_source()):
        body = function_body(src, name)
        if body:
            return body
    return ""


def check_post_forms_have_csrf() -> tuple[bool, str]:
    missing: list[str] = []
    for path in (ROOT / "app" / "templates").rglob("*.html"):
        if "_disabled_unused" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r"<form\b[^>]*>", text, re.I):
            tag = match.group(0)
            if not re.search(r"method\s*=\s*[\"']?post", tag, re.I):
                continue
            end = text.find("</form>", match.end())
            body = text[match.end() : end if end != -1 else min(len(text), match.end() + 2000)]
            if "csrf_token" not in body:
                line = text.count("\n", 0, match.start()) + 1
                missing.append(f"{path.relative_to(ROOT)}:{line}")
    if missing:
        return False, "POST 表单缺 csrf_token: " + ", ".join(missing)
    return True, "POST 表单 CSRF 字段完整"


def check_add_stock_results_checked() -> tuple[bool, str]:
    source = read_text("app/app.py")
    lines = source.splitlines()
    missing: list[str] = []
    for index, line in enumerate(lines, start=1):
        if "add_stock(" not in line or line.lstrip().startswith("def add_stock"):
            continue
        prefix = line.split("add_stock(", 1)[0]
        previous = lines[index - 2].strip() if index >= 2 else ""
        checked = "=" in prefix or prefix.strip().startswith("return ")
        if not checked and not re.search(r"(ok|msg|err|success).*=", previous):
            missing.append(f"app/app.py:{index}")
    if missing:
        return False, "add_stock 返回值未检查: " + ", ".join(missing)
    return True, "所有 add_stock 调用均检查返回值"


def check_web_login_csrf() -> tuple[bool, str]:
    """LOGIN-CSRF-001: Web /login 必须校验 CSRF，原生 /api/login 可继续豁免。"""
    combined = routes_source()
    login_html = read_text("app/templates/login.html")

    web_login = re.search(
        r"@app\.route\('/login',\s*methods=\['GET',\s*'POST'\]\)(?P<body>.*?)\n[ \t]*def login\(",
        combined,
        re.S,
    )
    if not web_login:
        return False, "找不到 Web /login 路由"
    if "@csrf.exempt" in web_login.group("body"):
        return False, "Web /login 不得使用 @csrf.exempt"

    api_login = re.search(
        r"@app\.route\('/api/login',\s*methods=\['POST'\]\)(?P<body>.*?)\n[ \t]*def native_api_login\(",
        combined,
        re.S,
    )
    if not api_login or "@csrf.exempt" not in api_login.group("body"):
        return False, "原生 /api/login 必须保持 @csrf.exempt（SEC-NEW2-001）"

    if 'method="POST"' not in login_html or "csrf_token" not in login_html:
        return False, "login.html 登录表单必须包含 csrf_token"

    import os
    import sys

    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    os.environ.setdefault("FLASK_ENV", "testing")
    os.environ.setdefault("WMS_SKIP_DB_UPGRADE", "1")

    from werkzeug.security import generate_password_hash

    import app as wms_app

    wms_app.app.config["WTF_CSRF_ENABLED"] = True
    wms_app.app.config["TESTING"] = False
    with wms_app.app.app_context():
        wms_app.db.create_all()
        username = "login_csrf_verify_user"
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

        if "routes.native_api.native_api_login" not in wms_app.csrf._exempt_views:
            return False, "运行时 routes.native_api.native_api_login 必须在 csrf._exempt_views"
        if "login" in wms_app.csrf._exempt_views:
            return False, "运行时 login 不应在 csrf._exempt_views"

        client = wms_app.app.test_client()
        resp = client.post(
            "/login",
            data={"username": username, "password": "Password123!"},
            follow_redirects=False,
        )
        location = resp.headers.get("Location") or ""
        # CSRF 校验失败的有效拒绝方式有两种（均不应登录成功）：
        # 1) 400 + JSON：JSON 客户端（API 调用）
        # 2) 302 重定向到 /login：HTML 表单走 handle_csrf_error 的智能跳转
        #    （fc22f9c2 修复 WMS-BUG-2026-07-30-003 后的预期行为，让浏览器拿到新 csrftoken）
        if resp.status_code in (302, 303) and "/login" not in location:
            return False, f"无 CSRF token 的 POST /login 不应重定向到非登录页（status={resp.status_code}）"
        if resp.status_code not in (400, 302, 303):
            return False, f"无 CSRF token 的 POST /login 应返回 400/302/303，实际 {resp.status_code}"
    return True, "Web /login 强制 CSRF；/api/login 保持豁免；无 token 登录被拒绝"


def check_field_settings_scroll() -> tuple[bool, str]:
    """BUG-2026-08-19-001: 字段设置弹窗字段多时必须出现滚动条，列表不能溢出弹窗。"""
    css = read_text("app/static/css/custom.css")
    app_js = read_text("app/static/js/app.js")

    content = re.search(r"\.wms-field-settings__content\{([^}]*)\}", css)
    if not content or "grid-template-rows:minmax(0,1fr)" not in content.group(1):
        return False, "字段设置内容区必须用 minmax(0,1fr) 行约束，否则表格撑破弹窗"
    wrap = re.search(r"\.wms-field-settings__table-wrap\{([^}]*)\}", css)
    if not wrap or "overflow:auto" not in wrap.group(1) or "min-height:0" not in wrap.group(1):
        return False, "字段设置表格容器必须 overflow:auto + min-height:0 才能出现滚动条"
    if "display:contents" in app_js:
        return False, "明细面板不得再用 display:contents（会绕过行约束导致无滚动条）"
    return True, "字段设置弹窗字段多时出现滚动条（BUG-2026-08-19-001 回归）"


def main() -> int:
    app_py = read_text("app/app.py")
    config_py = read_text("app/config.py")
    utils_py = read_text("app/utils.py")
    app_js = read_text("app/static/js/app.js")
    excel_table_js = read_text("app/static/js/excel-table.js")
    excel_import_js = read_text("app/static/js/excel-import-export.js")
    base_html = read_text("app/templates/base.html")

    checks: list[tuple[str, bool, str]] = []

    checks.append((
        "CONF-001",
        "env == 'production'" in app_py
        and "SECRET_KEY" in app_py
        and "WMS_ALLOW_AUTO_SECRET_KEY" in app_py
        and "raise RuntimeError" in app_py,
        "生产环境必须强制配置 SECRET_KEY，除非显式 WMS_ALLOW_AUTO_SECRET_KEY",
    ))

    deduct_body = function_body(app_py, "deduct_stock")
    checks.append((
        "BUG-002",
        "deduct_stock_atomic" in deduct_body
        and not re.search(r"material\.stock\s*=\s*material\.stock\s*-", deduct_body),
        "deduct_stock() 应委托原子扣减，不能读改写扣库存",
    ))

    add_body = function_body(app_py, "add_stock")
    checks.append((
        "STOCK-ADD",
        "sa_update(Material)" in add_body and "Material.stock + qty" in add_body,
        "add_stock() 应使用数据库原子增量更新",
    ))

    opening_body = function_body(app_py, "_apply_opening_stock_balance")
    checks.append((
        "BUG-006",
        "sa_update(Material)" in opening_body and "Material.stock + quantity_delta" in opening_body,
        "期初库存调整应使用原子增量更新",
    ))

    checks.append((
        "VULN-001",
        "sanitize_print_html" in utils_py
        and "净化失败" in utils_py
        and "<div" in utils_py
        and "打印模板内容净化失败" in function_body(utils_py, "sanitize_print_html"),
        "打印 HTML 净化失败不能返回空白",
    ))

    checks.append((
        "BUG-009",
        "_columnPanelClickHandler" in app_js and "removeEventListener('click'" in app_js,
        "setupDetailTable() 重新绑定 document click 前应移除旧 handler",
    ))

    checks.append((
        "BUG-010",
        "_excelTableHandlers" in excel_table_js and "cloneNode(true)" not in excel_table_js,
        "ExcelTable 不应通过 cloneNode 清事件，需显式移除旧监听器",
    ))

    checks.append((
        "BUG-011",
        "getElementById('excelImportModal')" in excel_import_js and "return;" in excel_import_js,
        "导入模态框重复创建前应复用已有 DOM",
    ))

    checks.append((
        "BUG-012",
        "exportColumns" in excel_import_js and "column.index" in excel_import_js,
        "导出应按导出列索引映射，避免隐藏列导致错位",
    ))

    checks.append((
        "CONF-002",
        "SQLALCHEMY_ECHO" in config_py and "'false'" in config_py and "os.environ.get('SQLALCHEMY_ECHO'" in config_py,
        "开发配置 SQL_ECHO 默认应关闭，仅由环境变量启用",
    ))

    checks.append((
        "CONF-004",
        "journal_mode=WAL" in app_py
        and "busy_timeout" in app_py
        and "foreign_keys=ON" in app_py
        and "BEGIN EXCLUSIVE" in app_py,
        "SQLite 应启用 WAL、busy_timeout、外键约束并串行执行启动迁移",
    ))

    purchase_status_body = function_body(app_py, "update_purchase_order_status")
    checks.append((
        "BUG-NEW-004",
        "InOrder.status == 'completed'" in purchase_status_body
        and "completed_by_item.get(item.id, 0)" in purchase_status_body
        and "received_qty += item.received_quantity" not in purchase_status_body,
        "采购订单状态必须按已完成入库数量计算，不能把草稿占用量当作已收货量",
    ))

    migration_body = function_body(app_py, "auto_migrate_database")
    checks.append((
        "BUG-NEW-016",
        "BEGIN EXCLUSIVE" in migration_body
        and "timeout=60" in migration_body
        and "raise" in migration_body,
        "多进程启动迁移必须串行等待，且迁移失败时停止启动",
    ))

    delete_in_order_body = app_function_body("delete_in_order")
    checks.append((
        "BUG-NEW-001",
        "order.status != 'pending'" in delete_in_order_body
        and "请先反提交回到草稿后再删除" in delete_in_order_body
        and "('pending', 'completed')" not in delete_in_order_body
        and "transaction_type='delete_in'" not in delete_in_order_body,
        "已完成入库单必须先反提交，后端只允许物理删除草稿",
    ))

    native_inbound_body = app_function_body("native_api_inbound")
    checks.append((
        "BUG-NEW-003",
        "def purchase_in_order_requires_order():\n    # Permanent business rule" in app_py
        and "return False" in function_body(app_py, "purchase_in_order_requires_order"),
        "采购入库允许不关联采购订单手工录入",
    ))
    checks.append((
        "BUG-NEW2-001",
        "ok, msg = add_stock" in native_inbound_body
        and "loc_ok, loc_msg = update_location_inventory" in native_inbound_body
        and "return api_json_error" in native_inbound_body,
        "Android 入库必须检查 add_stock 和库位库存更新返回值",
    ))
    ok, message = check_add_stock_results_checked()
    checks.append(("BUG-NEW3-001", ok, message))

    ok, message = check_web_login_csrf()
    checks.append(("LOGIN-CSRF-001", ok, message))

    ok, message = check_field_settings_scroll()
    checks.append(("BUG-2026-08-19-001", ok, message))

    mobile_scan_body = app_function_body("mobile_scan_submit")
    checks.append((
        "BUG-NEW2-006",
        "ok, error_msg = add_stock" in mobile_scan_body
        and "库位库存更新失败" in mobile_scan_body,
        "手机扫码入库必须检查 add_stock 和库位库存更新返回值",
    ))

    opening_add_body = app_function_body("add_opening_stock")
    opening_edit_body = app_function_body("edit_opening_stock")
    opening_batch_body = app_function_body("batch_save_opening_stock")
    checks.append((
        "BUG-NEW2-003",
        ".with_for_update().first()" in opening_add_body
        and ".with_for_update().first()" in opening_edit_body
        and ".with_for_update().first()" in opening_batch_body
        and "Material.stock + quantity_delta" in function_body(app_py, "_apply_opening_stock_balance"),
        "期初库存调整应锁定读取记录并使用原子增量更新库存",
    ))

    complete_check_body = app_function_body("complete_check")
    stocktake_body = app_function_body("native_api_stocktake")
    checks.append((
        "BUG-NEW2-004",
        "_create_adjustment_drafts_from_check(check)" in complete_check_body
        and "check_in" not in complete_check_body
        and "check_out" not in complete_check_body
        and "_create_adjustment_drafts_from_check_scan(check)" in stocktake_body,
        "盘点完成必须生成库存调整草稿，不能直接改库存",
    ))

    convert_body = app_function_body("convert_in_order_to_out_order")
    checks.append((
        "BUG-NEW-013",
        "in_order.business_type != '产品入库'" in convert_body,
        "入库单转领料单必须限制为产品入库，禁止采购入库转换",
    ))

    checks.append((
        "BUG-NEW-005",
        "os.environ.get('WMS_BOOTSTRAP_PASSWORD') or 'admin'" in app_py
        and "reset_admin_password.py" not in read_text("install.bat")
        and "admin123" not in read_text("install.bat")
        and "admin123" not in read_text("README.md")
        and "系统不会生成随机密码" in read_text("app/说明.txt"),
        "默认管理员密码必须遵循 WMS_BOOTSTRAP_PASSWORD/admin 首次创建规则，安装不得重置已有密码",
    ))

    checks.append((
        "BUG-NEW-008",
        "OK1949-2024" not in app_py and "山清酒里" not in app_py,
        "微信分享默认配置不能硬编码私人姓名或微信号",
    ))

    checks.append((
        "BUG-NEW-009",
        "excelRequiredColumns" in excel_import_js and "必填列：${this.getRequiredColumns()}" not in excel_import_js,
        "Excel 导入组件列名应使用 textContent 写入，不能拼入 HTML",
    ))

    checks.append((
        "AI-WECHAT-001",
        "_ai_is_wechat_delivery_notice" in app_py
        and "_ai_try_wechat_document_from_vision_json" in app_py
        and "明天发鑫达 6204轴承 100套，M8螺母 500个" in app_py
        and "classify it as in_order" in app_py
        and "source_text" in function_body(app_py, "_ai_call_llm_document_vision_extract")
        and "ocr_text" in function_body(app_py, "_ai_call_llm_document_vision_extract"),
        "微信出货通知截图/文本必须按供应商送货生成入库草稿",
    ))

    checks.append((
        "BUG-NEW-015",
        "last_no[-4:]" not in app_py and "suffix = last_no[len(base):]" in app_py,
        "单号生成不能固定截取末尾 4 位序列",
    ))

    batch_complete_out_body = app_function_body("batch_complete_out_order")
    checks.append((
        "BUG-NEW-014",
        "db.session.commit()" in batch_complete_out_body
        and batch_complete_out_body.find("db.session.commit()") < batch_complete_out_body.find("completed += 1")
        and "操作失败：" not in batch_complete_out_body,
        "批量完成出库单应按单据独立提交，失败只回滚当前单",
    ))

    add_user_body = app_function_body("add_user")
    reset_body = app_function_body("reset_user_password")
    checks.append((
        "VULN-004",
        "validate_password_strength(password)" in add_user_body
        and "validate_password_strength(new_password)" in reset_body,
        "新增用户和重置密码必须复用 validate_password_strength()",
    ))

    checks.append((
        'AI-AUTH-001',
        'AI_CAPABILITY_ROLES' in app_py
        and '_ai_draft_execution_allowed(\'out_order_draft\'' in function_body(app_py, '_ai_create_out_order_draft')
        and '_ai_draft_execution_allowed(\'in_order_draft\'' in function_body(app_py, '_ai_create_in_order_draft')
        and '_ai_capability_allowed(\'purchase_request_draft\')' in function_body(app_py, '_ai_create_purchase_request_draft_response')
        and '_ai_capability_allowed(\'purchase_receive_draft\')' in function_body(app_py, '_ai_purchase_order_receive_response')
        and '_ai_capability_allowed(\'admin_insights\')' in function_body(app_py, '_ai_user_permission_response')
        and '_ai_capability_allowed(\'admin_insights\')' in function_body(app_py, '_ai_operation_audit_response')
        and '_ai_capability_allowed(capability)' in function_body(app_py, '_ai_create_draft_from_extracted')
        and '_ai_capability_allowed(capability)' in function_body(app_py, '_ai_document_confirm_allowed'),
        'AI 草稿、敏感分析和文档确认必须通过统一能力权限矩阵校验',
    ))

    permission_matrix = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_permission_matrix.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if permission_matrix.stdout:
        print(permission_matrix.stdout.rstrip())
    if permission_matrix.stderr:
        print(permission_matrix.stderr.rstrip())
    checks.append((
        'AI-AUTH-002',
        permission_matrix.returncode == 0,
        'AI permission matrix must have automated role coverage and deny undeclared capabilities',
    ))

    tool_registry = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_tool_registry.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if tool_registry.stdout:
        print(tool_registry.stdout.rstrip())
    if tool_registry.stderr:
        print(tool_registry.stderr.rstrip())
    checks.append((
        'AI-TOOL-REGISTRY-001',
        tool_registry.returncode == 0,
        'AI tool registry metadata and role-filtered listings must match policy capabilities',
    ))

    platform_foundations = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_platform_foundations.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if platform_foundations.stdout:
        print(platform_foundations.stdout.rstrip())
    if platform_foundations.stderr:
        print(platform_foundations.stderr.rstrip())
    checks.append((
        'AI-PLATFORM-FOUNDATIONS-001',
        platform_foundations.returncode == 0,
        'AI platform schemas, prompts, provider config, and tool input validation must stay stable',
    ))

    tools_endpoint = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_tools_endpoint.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if tools_endpoint.stdout:
        print(tools_endpoint.stdout.rstrip())
    if tools_endpoint.stderr:
        print(tools_endpoint.stderr.rstrip())
    checks.append((
        'AI-TOOLS-ENDPOINT-001',
        tools_endpoint.returncode == 0,
        'AI tools endpoint must require login and return role-filtered tool metadata',
    ))

    ai_routes_py = read_text('app/ai/routes.py')
    ai_handlers_py = read_text('app/ai/handlers.py')
    ai_legacy_py = read_text('app/ai/legacy.py')
    checks.append((
        'AI-ROUTES-BLUEPRINT-001',
        "from ai.routes import ai_bp" in app_py
        and "app.register_blueprint(ai_bp)" in app_py
        and "ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')" in ai_routes_py
        and "from ai.handlers import handle_chat_stream, handle_draft_check, handle_warehouse_assistant" in ai_routes_py
        and "from app import _ai_" not in ai_routes_py
        and "@ai_bp.get('/tools')" in ai_routes_py
        and "@ai_bp.post('/chat/clear')" in ai_routes_py
        and "@ai_bp.post('/draft_check')" in ai_routes_py
        and "@ai_bp.post('/warehouse_assistant')" in ai_routes_py
        and "@ai_bp.post('/chat/stream')" in ai_routes_py
        and "def api_ai_tools" not in app_py
        and "def api_ai_chat_clear" not in app_py
        and "def api_ai_draft_check" not in app_py
        and "def api_ai_warehouse_assistant" not in app_py
        and "def api_ai_chat_stream" not in app_py
        and "@app.route('/api/ai/tools'" not in app_py
        and "@app.route('/api/ai/chat/clear'" not in app_py
        and "@app.route('/api/ai/draft_check'" not in app_py
        and "@app.route('/api/ai/warehouse_assistant'" not in app_py
        and "@app.route('/api/ai/chat/stream'" not in app_py,
        'AI API endpoints must live on the ai Blueprint instead of the monolithic app route table',
    ))

    platform_boundaries = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_platform_boundaries.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if platform_boundaries.stdout:
        print(platform_boundaries.stdout.rstrip())
    if platform_boundaries.stderr:
        print(platform_boundaries.stderr.rstrip())
    checks.append((
        'AI-PLATFORM-BOUNDARIES-001',
        platform_boundaries.returncode == 0,
        'AI Blueprint routes, handler proxies, and idempotency boundaries must stay separated',
    ))

    ai_handlers = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_handlers.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_handlers.stdout:
        print(ai_handlers.stdout.rstrip())
    if ai_handlers.stderr:
        print(ai_handlers.stderr.rstrip())
    checks.append((
        'AI-HANDLERS-001',
        ai_handlers.returncode == 0,
        'AI route handlers must delegate through the centralized legacy bridge',
    ))

    ai_streaming = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_streaming.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_streaming.stdout:
        print(ai_streaming.stdout.rstrip())
    if ai_streaming.stderr:
        print(ai_streaming.stderr.rstrip())
    checks.append((
        'AI-STREAMING-001',
        ai_streaming.returncode == 0,
        'AI SSE event formatting and streamed response ordering must stay stable',
    ))

    history_endpoint = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_history.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if history_endpoint.stdout:
        print(history_endpoint.stdout.rstrip())
    if history_endpoint.stderr:
        print(history_endpoint.stderr.rstrip())
    checks.append((
        'AI-CHAT-HISTORY-001',
        history_endpoint.returncode == 0,
        'AI chat clear endpoint must require login and clear only the current user history',
    ))

    draft_check_endpoint = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_draft_check_endpoint.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if draft_check_endpoint.stdout:
        print(draft_check_endpoint.stdout.rstrip())
    if draft_check_endpoint.stderr:
        print(draft_check_endpoint.stderr.rstrip())
    checks.append((
        'AI-DRAFT-CHECK-ENDPOINT-001',
        draft_check_endpoint.returncode == 0,
        'AI draft check endpoint must require login and delegate through the ai Blueprint',
    ))

    warehouse_assistant_endpoint = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_warehouse_assistant_endpoint.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if warehouse_assistant_endpoint.stdout:
        print(warehouse_assistant_endpoint.stdout.rstrip())
    if warehouse_assistant_endpoint.stderr:
        print(warehouse_assistant_endpoint.stderr.rstrip())
    checks.append((
        'AI-WAREHOUSE-ASSISTANT-ENDPOINT-001',
        warehouse_assistant_endpoint.returncode == 0,
        'AI warehouse assistant endpoint must live on the ai Blueprint and keep request_id idempotency',
    ))

    chat_stream_endpoint = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_chat_stream_endpoint.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if chat_stream_endpoint.stdout:
        print(chat_stream_endpoint.stdout.rstrip())
    if chat_stream_endpoint.stderr:
        print(chat_stream_endpoint.stderr.rstrip())
    checks.append((
        'AI-CHAT-STREAM-ENDPOINT-001',
        chat_stream_endpoint.returncode == 0,
        'AI chat stream endpoint must live on the ai Blueprint and keep request_id idempotency',
    ))

    document_jobs = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_document_jobs.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if document_jobs.stdout:
        print(document_jobs.stdout.rstrip())
    if document_jobs.stderr:
        print(document_jobs.stderr.rstrip())
    checks.append((
        'AI-DOCUMENT-JOBS-001',
        document_jobs.returncode == 0,
        'AI document recognition jobs must persist status, items, confirmation links, and draft results',
    ))

    document_evaluation = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_document_evaluation.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if document_evaluation.stdout:
        print(document_evaluation.stdout.rstrip())
    if document_evaluation.stderr:
        print(document_evaluation.stderr.rstrip())
    checks.append((
        'AI-DOCUMENT-EVALUATION-001',
        document_evaluation.returncode == 0,
        'AI document golden-sample evaluation metrics must be deterministic',
    ))

    ai_agents = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_agents.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_agents.stdout:
        print(ai_agents.stdout.rstrip())
    if ai_agents.stderr:
        print(ai_agents.stderr.rstrip())
    checks.append((
        'AI-AGENTS-001',
        ai_agents.returncode == 0,
        'AI controlled agents must create auditable tasks and steps',
    ))

    ai_stage4 = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_stage4_knowledge.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_stage4.stdout:
        print(ai_stage4.stdout.rstrip())
    if ai_stage4.stderr:
        print(ai_stage4.stderr.rstrip())
    checks.append((
        'AI-STAGE4-KNOWLEDGE-001',
        ai_stage4.returncode == 0,
        'AI knowledge grounding, source annotations, and master-data scoring must stay stable',
    ))

    ai_stage5 = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_stage5_ops.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_stage5.stdout:
        print(ai_stage5.stdout.rstrip())
    if ai_stage5.stderr:
        print(ai_stage5.stderr.rstrip())
    checks.append((
        'AI-STAGE5-OPS-001',
        ai_stage5.returncode == 0,
        'AI production flags, degradation, metrics dashboard, and rollout controls must stay stable',
    ))

    ai_stage6 = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_stage6_prelaunch.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_stage6.stdout:
        print(ai_stage6.stdout.rstrip())
    if ai_stage6.stderr:
        print(ai_stage6.stderr.rstrip())
    checks.append((
        'AI-STAGE6-PRELAUNCH-001',
        ai_stage6.returncode == 0,
        'AI prelaunch checks, access control, rollback readiness, and regression guidance must stay stable',
    ))

    ai_stage7 = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_stage7_replenishment.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if ai_stage7.stdout:
        print(ai_stage7.stdout.rstrip())
    if ai_stage7.stderr:
        print(ai_stage7.stderr.rstrip())
    checks.append((
        'AI-STAGE7-REPLENISHMENT-001',
        ai_stage7.returncode == 0,
        'AI PC replenishment planning, risk calculation, permissions, and entrypoint must stay stable',
    ))

    warehouse_handler_body = function_body(app_py, '_ai_handle_warehouse_assistant_request')
    checks.append((
        'AI-WAREHOUSE-ROUTE-SHELL-001',
        "def api_ai_warehouse_assistant" not in app_py
        and "@ai_bp.post('/warehouse_assistant')" in ai_routes_py
        and "return handle_warehouse_assistant(payload)" in ai_routes_py
        and "def handle_warehouse_assistant(payload)" in ai_handlers_py
        and "return warehouse_assistant_request(payload or {})" in ai_handlers_py
        and "'_ai_handle_warehouse_assistant_request'" in ai_legacy_py
        and "_ai_normalize_image_attachments" in warehouse_handler_body
        and "_ai_dispatch_registered_tool('warehouse_insights', augmented_message, context)" in warehouse_handler_body,
        'AI warehouse assistant route must be a Blueprint shell backed by the extracted handler',
    ))

    chat_stream_handler_body = function_body(app_py, '_ai_handle_chat_stream_request')
    checks.append((
        'AI-CHAT-STREAM-ROUTE-SHELL-001',
        "def api_ai_chat_stream" not in app_py
        and "@ai_bp.post('/chat/stream')" in ai_routes_py
        and "return handle_chat_stream(payload)" in ai_routes_py
        and "def handle_chat_stream(payload)" in ai_handlers_py
        and "return chat_stream_request(payload or {})" in ai_handlers_py
        and "'_ai_handle_chat_stream_request'" in ai_legacy_py
        and "from ai.streaming import sse_event, stream_response_payload" in app_py
        and "yield from stream_response_payload(reply_text, body.get('cards'), body.get('actions'))" in chat_stream_handler_body
        and "yield from stream_response_payload(reply_text, cards, actions)" in chat_stream_handler_body
        and "yield f'data: {json.dumps({\"type\"" not in chat_stream_handler_body
        and "def generate()" in chat_stream_handler_body
        and "Response(stream_with_context(generate())" in chat_stream_handler_body
        and "_ai_dispatch_registered_tool('warehouse_insights', message, context)" in chat_stream_handler_body,
        'AI chat stream route must be a Blueprint shell backed by the extracted handler',
    ))

    orchestrator = subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / 'verify_ai_orchestrator.py')],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
    )
    if orchestrator.stdout:
        print(orchestrator.stdout.rstrip())
    if orchestrator.stderr:
        print(orchestrator.stderr.rstrip())
    checks.append((
        'AI-ORCHESTRATOR-001',
        orchestrator.returncode == 0,
        'AI orchestrator must dispatch registered tools and reject handler mismatches',
    ))

    warehouse_dispatch_body = function_body(app_py, '_ai_warehouse_insights_response')
    checks.append((
        'AI-WAREHOUSE-DISPATCH-001',
        '_ai_agent_patrol_response' in warehouse_dispatch_body
        and '_ai_exception_workbench_response' in warehouse_dispatch_body
        and '_ai_inventory_discrepancy_response' in warehouse_dispatch_body
        and '_ai_exception_explain_response' in warehouse_dispatch_body
        and "'warehouse_insights': _ai_warehouse_insights_response" in app_py,
        'AI warehouse insight fallbacks must dispatch through the unified warehouse_insights path',
    ))

    purchase_dispatch_body = function_body(app_py, '_ai_purchase_insights_response')
    checks.append((
        'AI-PURCHASE-DISPATCH-001',
        '_ai_supplier_profile_response' in purchase_dispatch_body
        and '_ai_supplier_followup_response' in purchase_dispatch_body
        and '_ai_purchase_workbench_response' in purchase_dispatch_body
        and "'purchase_insights': _ai_purchase_insights_response" in app_py,
        'AI purchase insight fallbacks must dispatch through the unified purchase_insights path',
    ))

    master_data_dispatch_body = function_body(app_py, '_ai_master_data_insights_response')
    checks.append((
        'AI-MASTER-DATA-DISPATCH-001',
        '_ai_master_data_health_response' in master_data_dispatch_body
        and '_ai_master_data_fix_list_response' in master_data_dispatch_body
        and '_ai_master_data_import_response' in master_data_dispatch_body
        and "'master_data_insights': _ai_master_data_insights_response" in app_py,
        'AI master-data insight fallbacks must dispatch through the unified master_data_insights path',
    ))

    admin_dispatch_body = function_body(app_py, '_ai_admin_insights_response')
    checks.append((
        'AI-ADMIN-DISPATCH-001',
        '_ai_system_health_response' in admin_dispatch_body
        and '_ai_system_fix_list_response' in admin_dispatch_body
        and '_ai_user_permission_response' in admin_dispatch_body
        and '_ai_operation_audit_response' in admin_dispatch_body
        and "'admin_insights': _ai_admin_insights_response" in app_py,
        'AI admin insight fallbacks must dispatch through the unified admin_insights path',
    ))

    warehouse_assistant_body = function_body(app_py, '_ai_handle_warehouse_assistant_request')
    chat_stream_body = function_body(app_py, '_ai_handle_chat_stream_request')
    checks.append((
        'AI-TOOL-DISPATCH-001',
        'from ai.orchestrator import dispatch_registered_tool' in app_py
        and 'AI_TOOL_DISPATCHERS' in app_py
        and 'def _ai_dispatch_registered_tool' in app_py
        and 'dispatch_registered_tool(tool_name, message, context, AI_TOOL_DISPATCHERS, app.logger)' in app_py
        and "'warehouse_insights': _ai_warehouse_insights_response" in app_py
        and "'purchase_insights': _ai_purchase_insights_response" in app_py
        and "'master_data_insights': _ai_master_data_insights_response" in app_py
        and "'admin_insights': _ai_admin_insights_response" in app_py
        and "_ai_dispatch_registered_tool('warehouse_insights', augmented_message, context)" in warehouse_assistant_body
        and "_ai_dispatch_registered_tool('purchase_insights', augmented_message, context)" in warehouse_assistant_body
        and "_ai_dispatch_registered_tool('master_data_insights', augmented_message, context)" in warehouse_assistant_body
        and "_ai_dispatch_registered_tool('admin_insights', augmented_message, context)" in warehouse_assistant_body
        and "_ai_dispatch_registered_tool('warehouse_insights', message, context)" in chat_stream_body
        and "_ai_dispatch_registered_tool('purchase_insights', message, context)" in chat_stream_body
        and "_ai_dispatch_registered_tool('master_data_insights', message, context)" in chat_stream_body
        and "_ai_dispatch_registered_tool('admin_insights', message, context)" in chat_stream_body,
        'AI insight fallbacks must execute registered tools through the registry dispatch layer',
    ))

    checks.append((
        'AI-ENCODING-001',
        '閲囪喘鍏ュ簱' not in app_py
        and '璇风‘璁ゆ搷浣' not in base_html
        and '纭畾缁х画' not in base_html
        and '鐢遍噰璐敵璇' not in app_py,
        'AI 采购入库业务类型和全局确认框不得包含已知乱码',
    ))

    ai_idempotency_py = read_text('app/ai/idempotency.py')
    ai_schemas_py = read_text('app/ai/schemas.py')
    ai_prompts_py = read_text('app/ai/prompts.py')
    ai_providers_py = read_text('app/ai/providers.py')
    ai_registry_py = read_text('app/ai/tools/registry.py')
    ai_orchestrator_py = read_text('app/ai/orchestrator.py')
    checks.append((
        'AI-FOUNDATION-MODULES-001',
        'def validate_json_schema_payload' in ai_schemas_py
        and 'CURRENT_PROMPT_VERSION' in ai_prompts_py
        and 'class OpenAICompatibleConfig' in ai_providers_py
        and 'def build_chat_payload' in ai_providers_py
        and 'def validate_ai_tool_input' in ai_registry_py
        and 'validate_ai_tool_input(tool_name, context or {})' in ai_orchestrator_py
        and 'from ai.prompts import CURRENT_PROMPT_VERSION' in ai_idempotency_py
        and 'prompt_version=CURRENT_PROMPT_VERSION' in ai_idempotency_py,
        'AI platform foundation modules must provide schema validation, prompt versioning, provider config, and dispatch-time input validation',
    ))

    checks.append((
        'AI-DOCUMENT-JOB-MODELS-001',
        'class AIDocumentJob' in app_py
        and 'class AIDocumentItem' in app_py
        and 'class AIDocumentAttempt' in app_py
        and 'class AIDocumentFeedback' in app_py
        and "@app.route('/ai/document_jobs')" in app_py
        and "@app.route('/ai/document_jobs/<int:id>')" in app_py
        and "@app.route('/ai/document_jobs/<int:id>/confirm', methods=['POST'])" in app_py
        and "@app.route('/ai/document_jobs/<int:id>/retry', methods=['POST'])" in app_py
        and "@app.route('/ai/document_jobs/<int:id>/feedback', methods=['POST'])" in app_py
        and "def _ai_record_document_job" in app_py
        and "def _ai_record_document_attempt" in app_py
        and "def _ai_update_document_job" in app_py
        and "def _ai_mark_document_job_draft_created" in app_py
        and "def _ai_document_job_confirmation_payload" in app_py
        and "_ai_record_document_job(" in function_body(app_py, '_ai_create_draft_from_extracted')
        and "_ai_mark_document_job_draft_created(" in function_body(app_py, 'ai_document_confirm')
        and 'ai_document_jobs.html' in app_py
        and 'ai_document_job_detail.html' in app_py,
        'AI document recognition must be tracked in durable job/item/attempt/feedback records with list/detail visibility, retry, recovery, and draft result updates',
    ))

    ai_document_eval_py = read_text('app/ai/documents/evaluation.py')
    checks.append((
        'AI-DOCUMENT-EVALUATION-MODULE-001',
        'def evaluate_document_samples' in ai_document_eval_py
        and 'header_accuracy' in ai_document_eval_py
        and 'line_recall' in ai_document_eval_py
        and 'quantity_accuracy' in ai_document_eval_py
        and 'material_match_accuracy' in ai_document_eval_py
        and read_text('scripts/evaluate_ai_document_samples.py').find("samples' / 'ai_documents") > -1,
        'AI document intelligence must include a reusable golden-sample evaluation framework',
    ))

    checks.append((
        'AI-CONTROLLED-AGENTS-001',
        'class AIAgentTask' in app_py
        and 'class AIAgentStep' in app_py
        and 'def _ai_run_warehouse_patrol_agent' in app_py
        and 'def _ai_run_purchase_followup_agent' in app_py
        and "@app.route('/ai/agent_tasks')" in app_py
        and "@app.route('/ai/agent_tasks/<int:id>')" in app_py
        and "@app.route('/ai/agent_tasks/run/warehouse_patrol', methods=['POST'])" in app_py
        and "@app.route('/ai/agent_tasks/run/purchase_followup', methods=['POST'])" in app_py
        and 'ai_agent_tasks.html' in app_py
        and 'ai_agent_task_detail.html' in app_py
        and "risk_level='draft'" in function_body(app_py, '_ai_run_purchase_followup_agent')
        and '.submit(' not in function_body(app_py, '_ai_run_warehouse_patrol_agent').lower()
        and '.audit(' not in function_body(app_py, '_ai_run_warehouse_patrol_agent').lower()
        and '.complete(' not in function_body(app_py, '_ai_run_warehouse_patrol_agent').lower(),
        'AI Agent phase must persist auditable tasks/steps and keep high-risk workflow actions out of autonomous execution',
    ))

    checks.append((
        'AI-IDEMPOTENCY-001',
        'class AIRequestIdempotency' in app_py
        and 'uix_ai_request_user_request' in app_py
        and 'from ai.idempotency import configure_ai_idempotency_service' in app_py
        and '_ai_idempotency = configure_ai_idempotency_service(' in app_py
        and '_ai_idempotent_request = _ai_idempotency.idempotent_request' in app_py
        and 'class AIIdempotencyService' in ai_idempotency_py
        and 'def idempotent_request(self, view_function)' in ai_idempotency_py
        and 'hashlib.sha256' in ai_idempotency_py
        and 'IntegrityError' in ai_idempotency_py
        and 'stream_with_context(record_stream())' in ai_idempotency_py
        and '@ai_idempotent_request\ndef warehouse_assistant' in ai_routes_py
        and '@ai_idempotent_request\ndef chat_stream' in ai_routes_py
        and 'request_id: requestId' in base_html
        and 'createAIRequestId()' in base_html,
        'AI 普通响应和流式响应必须使用持久化 request_id 幂等保护',
    ))

    checks.append((
        'AI-AUDIT-001',
        'class AIRun' in app_py
        and 'class AIToolCall' in app_py
        and 'ai_run_id = db.Column' in app_py
        and 'def finish_run(self, run_id: int, status: str, error_message: str = \'\')' in ai_idempotency_py
        and 'self.finish_run(record.ai_run_id' in ai_idempotency_py
        and re.search(
            r'_ai_record_capability_audit\(capability,\s*allowed(?:\s*,|\s*\))',
            function_body(app_py, '_ai_capability_allowed'),
        ),
        'AI 请求必须记录运行状态、模型、耗时，并将能力授权结果写入工具调用审计',
    ))

    ok, message = check_post_forms_have_csrf()
    checks.append(("VULN-003", ok, message))

    checks.append((
        "BUG-NEW-017",
        "request.args.get('embedded') == '1'" in base_html
        and '<body class="{% block body_class %}{% endblock %}{% if request.args.get(\'embedded\') == \'1\' %} embedded-page{% endif %}">' in base_html
        and "if (document.body.classList.contains('embedded-page')) return;" in app_js
        and "target.searchParams.set('embedded', '1');" in app_js,
        'Embedded tab pages must render one shell and keep add-page navigation embedded',
    ))

    print_labels_html = read_text('app/templates/print_batch_labels.html')
    # VULN-005: Batch label 模板必须用 Jinja tojson 渲染（不能用 | safe 直接注入原始字符串）
    # 修复脚本误报：变量名可能是 materials_data / materials_json / 其他，统一用正则匹配
    # 但要排除 | safe 的使用（因为 | safe 会绕开转义，等同 XSS）
    has_tojson = bool(re.search(r'materials_\w+\s*\|\s*tojson', print_labels_html))
    has_safe_on_materials = bool(re.search(r'materials_\w+\s*\|\s*safe', print_labels_html))
    checks.append((
        'VULN-005',
        has_tojson and not has_safe_on_materials,
        'Batch label JSON must use Jinja tojson instead of raw safe script injection',
    ))

    failed = [(code, message) for code, ok, message in checks if not ok]
    for code, ok, message in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status} {code}: {message}")

    if failed:
        print("\n回归检查失败，需先修复以上 FAIL 项。")
        return 1
    print("\n回归检查通过：已修复 BUG 未发现明显回归。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
