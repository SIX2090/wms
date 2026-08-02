"""BUG-2026-08-02-021：采购入库单明细合同/项目列 + 向下填充只填有数据行

回归测试两个修复：
1. setupColumnFillDown（Ctrl+D 向下填充）增加 .line-contract-no / .line-project-name，
   并只填充 material-code 非空的行（跳过空行）。
2. ContractAutocomplete.bind 在 focus 时也触发搜索（点击单元格即可看到匹配项）。

由于项目无前端测试框架（无 JSDOM/Selenium），本测试做：
- T1-T4：静态 HTML/JS 内容断言（防止代码回退）
- T5：Flask test client GET /in_order/add 渲染后包含修复 JS（运行时集成验证）
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_ORDER_ADD = ROOT / "app" / "templates" / "in_order_add.html"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_T1_setup_fill_down_includes_contract_columns():
    """修复 1：setupColumnFillDown 包含合同编号/工程名称列。"""
    html = _read(IN_ORDER_ADD)
    assert "line-contract-no" in html, "未找到 .line-contract-no 绑定"
    assert "line-project-name" in html, "未找到 .line-project-name 绑定"
    # 两个 class 应出现在 setupColumnFillDown 的 Ctrl+D 分支里
    setup_block = html[html.index("function setupColumnFillDown"):html.index("setupColumnFillDown();", html.index("function setupColumnFillDown")) + len("setupColumnFillDown();")]
    assert ".line-contract-no" in setup_block, "Ctrl+D 未绑定合同编号列"
    assert ".line-project-name" in setup_block, "Ctrl+D 未绑定工程名称列"


def test_T2_setup_fill_down_skips_empty_rows():
    """修复 1：Ctrl+D 向下填充跳过 material-code 为空的行。"""
    html = _read(IN_ORDER_ADD)
    setup_block = html[html.index("function setupColumnFillDown"):html.index("setupColumnFillDown();", html.index("function setupColumnFillDown")) + len("setupColumnFillDown();")]
    # 跳过空行的判断逻辑
    assert "material-code" in setup_block, "Ctrl+D 未检查 material-code（应跳过空行）"
    assert "codeVal" in setup_block, "Ctrl+D 未提取 codeVal 用于空行判断"
    assert "skipped" in setup_block, "Ctrl+D 未记录跳过空行计数"
    # 提示文案应含"跳过 ... 个空行"
    assert "跳过" in setup_block and "空行" in setup_block, "Ctrl+D 提示文案未含跳过空行说明"


def test_T3_contract_autocomplete_focus_trigger():
    """修复 2：ContractAutocomplete.bind 在 focus 时触发搜索。"""
    js = _read(APP_JS)
    # bind 函数内应包含 focus 事件 + triggerSearch 调用
    bind_match = re.search(r"function bind\(input\)\s*\{.*?input\.addEventListener\('focus'", js, re.DOTALL)
    assert bind_match is not None, "ContractAutocomplete.bind 未绑定 focus 事件"
    # triggerSearch 辅助函数被定义并被 focus 调用
    assert "function triggerSearch(value)" in js, "未定义 triggerSearch 辅助函数"
    # focus handler 调用 triggerSearch
    focus_block = js[bind_match.end():js.index("input.addEventListener('keydown'", bind_match.end())]
    assert "triggerSearch" in focus_block, "focus 事件未调用 triggerSearch"


def test_T4_getContracts_unavailable_guard():
    """ContractAutocomplete 模块应在 WMS.api.getContracts 缺失时安全跳过（不抛错）。"""
    js = _read(APP_JS)
    assert "global.WMS.api.getContracts" in js, "getContracts 检测丢失"


def test_T5_in_order_add_renders_with_fixes():
    """运行时集成：登录后 GET /in_order/add 渲染的 HTML 包含修复后的关键逻辑。"""
    import sys
    sys.path.insert(0, str(ROOT / "app"))
    import os
    os.chdir(ROOT / "app")
    sys.modules.pop("app", None)

    import app as app_module
    from app import db, Warehouse, Supplier, User, Material, MaterialCategory, Unit
    from werkzeug.security import generate_password_hash

    client = app_module.app.test_client()
    with app_module.app.app_context():
        db.create_all()
        # 最小种子：admin 用户 + 默认仓库（确保页面渲染）
        if not User.query.filter_by(username="admin").first():
            user = User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            )
            db.session.add(user)
        if not Warehouse.query.filter_by(is_default=True).first():
            wh = Warehouse(code="WHD", name="默认仓", is_default=True, status="active")
            db.session.add(wh)
        if not Unit.query.first():
            db.session.add(Unit(name="个", code="PCS"))
        if not MaterialCategory.query.first():
            db.session.add(MaterialCategory(name="默认", code="CAT"))
        if not Supplier.query.first():
            db.session.add(Supplier(code="SUP001", name="默认供应商"))
        db.session.commit()

        # 登录拿 csrf + session
        r = client.get("/login")
        assert r.status_code == 200
        m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data) or \
            re.search(rb'value="([^"]+)"[^>]*name="csrf_token"', r.data) or \
            re.search(rb'id="csrf_token"[^>]*value="([^"]+)"', r.data)
        # 直接从 session 拿 csrf（更可靠）
        with client.session_transaction() as sess:
            from flask.sessions import SecureCookieSessionInterface
            pass

    # 登录（admin/admin，无 must_change_password 跳转）—— 需带 csrf_token
    r = client.get("/login")
    assert r.status_code == 200
    csrf_match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data) or \
        re.search(rb'value="([^"]+)"[^>]*name="csrf_token"', r.data) or \
        re.search(rb'id="csrf_token"[^>]*value="([^"]+)"', r.data)
    assert csrf_match is not None, "未找到 csrf_token"
    csrf_token = csrf_match.group(1).decode("utf-8")
    r = client.post("/login", data={
        "username": "admin",
        "password": "admin",
        "csrf_token": csrf_token,
    }, follow_redirects=False)
    assert r.status_code in (200, 302), f"/login POST 返回 {r.status_code}"
    r = client.get("/in_order/add")
    assert r.status_code == 200, f"/in_order/add 返回 {r.status_code}：{r.data[:200]!r}"
    body = r.data.decode("utf-8", errors="replace")
    # 关键修复特征应出现在渲染后的 HTML 里
    assert "setupColumnFillDown" in body, "渲染后 HTML 未包含 setupColumnFillDown"
    assert "line-contract-no" in body, "渲染后 HTML 未包含 line-contract-no"
    assert "line-project-name" in body, "渲染后 HTML 未包含 line-project-name"
    assert "跳过" in body and "空行" in body, "渲染后 HTML 未含跳过空行提示文案"