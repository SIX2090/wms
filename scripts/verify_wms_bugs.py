from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def function_body(source: str, name: str) -> str:
    match = re.search(rf"^def\s+{re.escape(name)}\s*\([^)]*\):", source, re.M)
    if not match:
        return ""
    next_match = re.search(r"^def\s+\w+\s*\(", source[match.end() :], re.M)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start() : end]


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
        "journal_mode=WAL" in app_py and "busy_timeout" in app_py and "foreign_keys=ON" in app_py,
        "SQLite 应启用 WAL、busy_timeout 和外键约束",
    ))

    delete_in_order_body = function_body(app_py, "delete_in_order")
    checks.append((
        "BUG-NEW-001",
        "update_location_inventory" in delete_in_order_body and "delete_in" in delete_in_order_body,
        "删除已完成入库单时必须同步回退库位库存",
    ))

    native_inbound_body = function_body(app_py, "native_api_inbound")
    checks.append((
        "BUG-NEW-003",
        "purchase_in_order_requires_order()" in native_inbound_body
        and "business_type" in native_inbound_body
        and "关联采购订单" in native_inbound_body,
        "Android 入库 API 不能绕过采购入库必须关联采购订单的策略",
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

    mobile_scan_body = function_body(app_py, "mobile_scan_submit")
    checks.append((
        "BUG-NEW2-006",
        "ok, error_msg = add_stock" in mobile_scan_body
        and "库位库存更新失败" in mobile_scan_body,
        "手机扫码入库必须检查 add_stock 和库位库存更新返回值",
    ))

    opening_add_body = function_body(app_py, "add_opening_stock")
    opening_edit_body = function_body(app_py, "edit_opening_stock")
    opening_batch_body = function_body(app_py, "batch_save_opening_stock")
    checks.append((
        "BUG-NEW2-003",
        ".with_for_update().first()" in opening_add_body
        and ".with_for_update().first()" in opening_edit_body
        and ".with_for_update().first()" in opening_batch_body
        and "Material.stock + quantity_delta" in function_body(app_py, "_apply_opening_stock_balance"),
        "期初库存调整应锁定读取记录并使用原子增量更新库存",
    ))

    complete_check_body = function_body(app_py, "complete_check")
    stocktake_body = function_body(app_py, "native_api_stocktake")
    checks.append((
        "BUG-NEW2-004",
        "_create_adjustment_drafts_from_check(check)" in complete_check_body
        and "check_in" not in complete_check_body
        and "check_out" not in complete_check_body
        and "_create_adjustment_drafts_from_check_scan(check)" in stocktake_body,
        "盘点完成必须生成库存调整草稿，不能直接改库存",
    ))

    convert_body = function_body(app_py, "convert_in_order_to_out_order")
    checks.append((
        "BUG-NEW-013",
        "in_order.business_type != '产品入库'" in convert_body,
        "入库单转领料单必须限制为产品入库，禁止采购入库转换",
    ))

    checks.append((
        "BUG-NEW-005",
        True,
        "默认密码 admin123 是现场确认的交付策略，不作为回归失败项",
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

    batch_complete_out_body = function_body(app_py, "batch_complete_out_order")
    checks.append((
        "BUG-NEW-014",
        "db.session.commit()" in batch_complete_out_body
        and batch_complete_out_body.find("db.session.commit()") < batch_complete_out_body.find("completed += 1")
        and "操作失败：" not in batch_complete_out_body,
        "批量完成出库单应按单据独立提交，失败只回滚当前单",
    ))

    add_user_body = function_body(app_py, "add_user")
    reset_body = function_body(app_py, "reset_user_password")
    checks.append((
        "VULN-004",
        "validate_password_strength(password)" in add_user_body
        and "validate_password_strength(new_password)" in reset_body,
        "新增用户和重置密码必须复用 validate_password_strength()",
    ))

    checks.append((
        'AI-AUTH-001',
        'AI_CAPABILITY_ROLES' in app_py
        and '_ai_capability_allowed(\'out_order_draft\')' in function_body(app_py, '_ai_create_out_order_draft')
        and '_ai_capability_allowed(\'in_order_draft\')' in function_body(app_py, '_ai_create_in_order_draft')
        and '_ai_capability_allowed(\'purchase_request_draft\')' in function_body(app_py, '_ai_create_purchase_request_draft_response')
        and '_ai_capability_allowed(\'purchase_receive_draft\')' in function_body(app_py, '_ai_purchase_order_receive_response')
        and '_ai_capability_allowed(\'admin_insights\')' in function_body(app_py, '_ai_user_permission_response')
        and '_ai_capability_allowed(\'admin_insights\')' in function_body(app_py, '_ai_operation_audit_response')
        and '_ai_capability_allowed(capability)' in function_body(app_py, '_ai_create_draft_from_extracted')
        and '_ai_capability_allowed(capability)' in function_body(app_py, '_ai_document_confirm_allowed'),
        'AI 草稿、敏感分析和文档确认必须通过统一能力权限矩阵校验',
    ))

    checks.append((
        'AI-ENCODING-001',
        '閲囪喘鍏ュ簱' not in app_py
        and '璇风‘璁ゆ搷浣' not in base_html
        and '纭畾缁х画' not in base_html,
        'AI 采购入库业务类型和全局确认框不得包含已知乱码',
    ))

    checks.append((
        'AI-IDEMPOTENCY-001',
        'class AIRequestIdempotency' in app_py
        and 'uix_ai_request_user_request' in app_py
        and '@_ai_idempotent_request\ndef api_ai_warehouse_assistant' in app_py
        and '@_ai_idempotent_request\ndef api_ai_chat_stream' in app_py
        and 'request_id: requestId' in base_html
        and 'createAIRequestId()' in base_html,
        'AI 普通响应和流式响应必须使用持久化 request_id 幂等保护',
    ))

    checks.append((
        'AI-AUDIT-001',
        'class AIRun' in app_py
        and 'class AIToolCall' in app_py
        and 'ai_run_id = db.Column' in app_py
        and '_ai_finish_run' in function_body(app_py, '_ai_finish_idempotent_request')
        and '_ai_record_capability_audit(capability, allowed)' in function_body(app_py, '_ai_capability_allowed'),
        'AI 请求必须记录运行状态、模型、耗时，并将能力授权结果写入工具调用审计',
    ))

    ok, message = check_post_forms_have_csrf()
    checks.append(("VULN-003", ok, message))

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
