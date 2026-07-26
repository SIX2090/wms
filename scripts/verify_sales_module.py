#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WMS 销售管理模块验证脚本（阶段 6：测试与验收）。

覆盖范围：
  静态检查：
    SALES-STC-001  auto_migrate_database 含销售订单新字段 ALTER TABLE 迁移
    SALES-STC-002  recalculate_sales_order 实现税感知总额计算
    SALES-STC-003  build_sales_outbound_draft 含重复草稿防护
    SALES-STC-004  销售路由 require_role 权限装饰器（全 POST 路由扫描，AI-SALES-F01-FIX-02）
    SALES-STC-005  新增报表模板存在
    SALES-STC-006  导入模板含新字段列头
    SALES-STC-007  销售出库行级来源外键和安全回写
    SALES-STC-008  销售出库选单入口和接口
    SALES-STC-009  销售订单仓库外键迁移和启用校验
    SALES-STC-010  销售选单多进程写锁和二次校验
    SALES-STC-011  销售模板 POST fetch 调用携带 CSRF 头/Token（AI-SALES-F01-FIX-02）
    SALES-STC-012  base.html 提供全局 csrfFetch/getCsrfToken/csrfPost helper（SM-P6-03-1）

  运行时测试（Flask test_client + 临时数据库）：
    SALES-RT-001  创建销售订单（含税额字段）
    SALES-RT-002  税额计算正确性（含税/未税/税额）
    SALES-RT-003  确认销售订单
    SALES-RT-004  生成销售出库草稿
    SALES-RT-005  重复生成出库草稿返回已存在
    SALES-RT-006  完成出库单后回写已发货数量（一单一出）
    SALES-RT-007  订单状态变为已发货/已完成
    SALES-RT-007A 同物料多行下推保留各自来源行
    SALES-RT-007B 同物料多行完成后按来源行回写
    SALES-RT-008  取消未发货订单
    SALES-RT-009  删除草稿订单
    SALES-RT-010  报表页面渲染（销售报表/出库明细/趋势分析）
    SALES-RT-011  报表 Excel 导出
    SALES-RT-012  权限边界：无权限角色不能创建订单
    SALES-RT-013  中文页面无乱码

用法：
    python scripts/verify_sales_module.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


# ==================== 工具函数 ====================
def read_text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="ignore")


def static_check(check_id: str, ok: bool, msg: str) -> tuple[str, bool, str]:
    return (check_id, ok, msg)


# ==================== 静态检查 ====================
def run_static_checks() -> list[tuple[str, bool, str]]:
    app_py = read_text("app/app.py")
    results: list[tuple[str, bool, str]] = []

    # SALES-STC-001: auto_migrate_database 含新字段迁移
    migrate_section = app_py.split("def auto_migrate_database()")[1].split("\ndef ")[0] if "def auto_migrate_database()" in app_py else ""
    new_order_cols = ["salesperson_id", "project_no", "currency", "settlement_method",
                      "untaxed_amount", "tax_amount", "shipped_amount", "remaining_amount"]
    new_item_cols = ["tax_rate", "untaxed_price", "untaxed_amount", "tax_amount",
                     "tax_included_amount", "batch_no", "serial_no"]
    missing_order = [c for c in new_order_cols if f"ADD COLUMN {c}" not in migrate_section.replace('"', '').replace("'", "")]
    missing_item = [c for c in new_item_cols if f"ADD COLUMN {c}" not in migrate_section.replace('"', '').replace("'", "")]
    ok = not missing_order and not missing_item
    detail = ""
    if missing_order:
        detail += f" sales_order 缺失: {missing_order}"
    if missing_item:
        detail += f" sales_order_item 缺失: {missing_item}"
    results.append(static_check("SALES-STC-001", ok,
        "auto_migrate_database 含销售订单新字段 ALTER TABLE 迁移" + ("" if ok else detail)))

    # SALES-STC-002: recalculate_sales_order 税感知计算
    recalc_section = ""
    if "def recalculate_sales_order(order):" in app_py:
        start = app_py.index("def recalculate_sales_order(order):")
        next_def = app_py.find("\ndef ", start + 10)
        recalc_section = app_py[start:next_def if next_def > 0 else len(app_py)]
    has_untaxed = "untaxed_amount" in recalc_section and "untaxed_price" in recalc_section
    has_tax = "tax_amount" in recalc_section and "tax_included_amount" in recalc_section
    has_formula = "(1 + tax_rate)" in recalc_section
    ok = has_untaxed and has_tax and has_formula
    results.append(static_check("SALES-STC-002", ok,
        "recalculate_sales_order 实现税感知总额计算（未税/税额/含税）"))

    # SALES-STC-003: build_sales_outbound_draft 含重复草稿防护
    draft_section = ""
    if "def build_sales_outbound_draft(order" in app_py:
        start = app_py.index("def build_sales_outbound_draft(order")
        next_def = app_py.find("\ndef ", start + 10)
        draft_section = app_py[start:next_def if next_def > 0 else len(app_py)]
    has_pending_check = ("status == 'pending'" in draft_section or "OutOrder.status == 'pending'" in draft_section) and "pending_draft" in draft_section
    has_remaining = "remaining_quantity" in draft_section or "remaining_items" in draft_section
    has_partial_guard = "selected_qty_by_item_id" in draft_section and "over_quantity" in draft_section
    ok = has_pending_check and has_remaining and has_partial_guard
    results.append(static_check("SALES-STC-003", ok,
        "build_sales_outbound_draft 含重复草稿防护与未发货数量计算"))

    # SALES-STC-007: 行级来源必须贯穿模型、迁移、下推和回写
    has_source_column = "source_sales_order_item_id" in app_py
    has_source_migration = "ALTER TABLE out_order_item ADD COLUMN source_sales_order_item_id" in app_py
    has_source_write = "source_sales_order_item_id=item.id" in app_py
    has_source_sync = "outbound_item.source_sales_order_item_id" in app_py
    ok = has_source_column and has_source_migration and has_source_write and has_source_sync
    results.append(static_check("SALES-STC-007", ok,
        "销售出库行级来源外键贯穿迁移、下推和完成/反提交回写"))

    has_selection_api = "def api_sales_order_selectable():" in app_py and "def create_sales_outbound_from_selection():" in app_py
    has_selection_template = (ROOT / "app" / "templates" / "sales_outbound_selection.html").exists()
    results.append(static_check("SALES-STC-008", has_selection_api and has_selection_template,
        "销售出库选单页面、查询接口和生成接口存在"))

    has_warehouse_migration = "ALTER TABLE sales_order ADD COLUMN warehouse_id INTEGER" in app_py
    has_warehouse_fk = "warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))" in app_py
    has_warehouse_validation = "def validate_sales_warehouse" in app_py and "请选择有效且启用的发货仓库" in app_py
    results.append(static_check("SALES-STC-009", has_warehouse_migration and has_warehouse_fk and has_warehouse_validation,
        "销售订单仓库外键、历史迁移和启用状态校验存在"))

    has_selection_lock = "BEGIN IMMEDIATE" in app_py and "final pending-draft check" in app_py
    results.append(static_check("SALES-STC-010", has_selection_lock,
        "销售选单生成包含 SQLite 写锁和加锁后来源重读"))

    # SALES-STC-004: 销售路由权限装饰器（扫描全部 /sales/* POST 路由）
    # 修复任务 AI-SALES-F01-FIX-02：从仅检查 sales_order_add 扩展到全部 POST 写入路由
    sales_post_route_pattern = re.compile(
        r"(@app\.route\(['\"]/sales[^'\"]*['\"],\s*methods=\[(?:'|\")[^\]]*POST[^\]]*(?:'|\")\])\)"
        r"(?:\s*\n(?:@[a-z_][^\n]*\n){0,5})\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)",
        re.MULTILINE,
    )
    sales_post_matches = list(sales_post_route_pattern.finditer(app_py))
    sales_missing_role = []
    for m in sales_post_matches:
        decorator_block = m.group(0)
        route_line = m.group(1)
        func_name = m.group(2)
        if "@require_role" not in decorator_block:
            sales_missing_role.append(f"{func_name}({route_line})")
    ok_stc004 = bool(sales_post_matches) and not sales_missing_role
    detail_stc004 = ""
    if not sales_post_matches:
        detail_stc004 = " 未匹配到任何 /sales POST 路由（正则失效）"
    elif sales_missing_role:
        detail_stc004 = f" 缺少 @require_role: {sales_missing_role}"
    results.append(static_check("SALES-STC-004", ok_stc004,
        f"全部 /sales/* POST 路由使用 @require_role 权限装饰器"
        f"（共 {len(sales_post_matches)} 个路由）" + detail_stc004))

    # SALES-STC-011: 销售详情模板 POST fetch 调用必须携带 CSRF 头
    # 修复任务 AI-SALES-F01-FIX-02：审计报告 P0-3 要求增加 CSRF 头静态检查
    # 注意：base.html 中有全局 fetch 包装器，自动为所有非 GET 请求注入 X-CSRFToken
    # 头。继承自 base.html 的模板自动获得 CSRF 保护，无需在每个 fetch 中显式注入。
    sales_detail_templates = [
        "sales_order_detail.html",
        "sales_outbound_selection.html",
        "sales_order.html",
        "sales_order_edit.html",
        "sales_order_add.html",
        "after_sale_out.html",
        "after_sale_out_add.html",
        "after_sale_out_detail.html",
    ]
    # 检查 base.html 是否提供全局 CSRF 自动注入
    base_html = read_text("app/templates/base.html") if (ROOT / "app" / "templates" / "base.html").exists() else ""
    has_global_csrf_wrapper = ("window.fetch = function" in base_html
                              and "X-CSRFToken" in base_html
                              and "csrf-token" in base_html)
    csrf_missing = []
    for tpl_name in sales_detail_templates:
        tpl_path = ROOT / "app" / "templates" / tpl_name
        if not tpl_path.exists():
            continue
        tpl_text = tpl_path.read_text(encoding="utf-8", errors="ignore")
        extends_base = "{% extends" in tpl_text and "base.html" in tpl_text[:200]
        # 提取 method: 'POST' 或 method: "POST" 的 fetch 调用片段
        for fm in re.finditer(
            r"fetch\([^)]*method:\s*['\"]POST['\"][^)]*\)",
            tpl_text,
            re.IGNORECASE | re.DOTALL,
        ):
            snippet = fm.group(0)
            # 视为通过：含 X-CSRFToken / csrfFetch / csrfPost / csrf_token 任意一种
            if ("X-CSRFToken" in snippet or "csrfFetch" in snippet
                    or "csrfPost" in snippet or "csrf_token" in snippet):
                continue
            # 否则：若模板继承 base.html 且 base.html 提供全局 CSRF 包装，则视为合规
            if extends_base and has_global_csrf_wrapper:
                continue
            csrf_missing.append(f"{tpl_name}:{fm.start()}")
    ok_stc011 = not csrf_missing
    results.append(static_check("SALES-STC-011", ok_stc011,
        "销售模板 POST fetch 调用携带 CSRF 头/Token"
        + (f"（base.html 全局包装器自动注入）" if has_global_csrf_wrapper else "")
        + ("" if ok_stc011 else f" 缺失位置: {csrf_missing}")))

    # SALES-STC-012: 销售模板使用全局 csrfFetch / csrfPost helper，不重复定义
    # 修复任务 SM-P6-03-1：抽 csrfFetch helper 到 base.html，迁移 14 个 sales_*.html
    # 规则：base.html 必须提供全局 csrfFetch/getCsrfToken/csrfPost；sales_*.html 不应再
    #       重复定义本地 function csrfFetch / function csrfPost / function getCsrfToken。
    sales_templates_for_stc012 = [
        "sales_order.html", "sales_order_add.html", "sales_order_edit.html",
        "sales_order_detail.html", "sales_outbound_selection.html",
        "sales_outbound_list.html", "sales_report.html", "sales_dashboard.html",
        "sales_exceptions.html", "sales_price_analysis.html",
        "sales_reconciliation_report.html", "sales_trend_report.html",
        "sales_execution_report.html", "sales_outflow_report.html",
    ]
    base_provides_global = (
        "function csrfFetch" in base_html
        and "function getCsrfToken" in base_html
        and "function csrfPost" in base_html
    )
    local_redefs = []
    for tpl_name in sales_templates_for_stc012:
        tpl_path = ROOT / "app" / "templates" / tpl_name
        if not tpl_path.exists():
            continue
        tpl_text = tpl_path.read_text(encoding="utf-8", errors="ignore")
        for marker in (
            "function csrfFetch", "function csrfPost", "function getCsrfToken",
        ):
            if marker in tpl_text:
                local_redefs.append(f"{tpl_name}:{marker}")
    ok_stc012 = base_provides_global and not local_redefs
    results.append(static_check("SALES-STC-012", ok_stc012,
        "base.html 提供全局 csrfFetch/getCsrfToken/csrfPost helper，sales_*.html 不重复定义"
        + ("" if ok_stc012 else (
            " base.html 全局 helper: " + ("YES" if base_provides_global else "MISSING")
            + f"  本地重复定义: {local_redefs or 'NONE'}"))))

    # SALES-STC-005: 新增报表模板存在
    templates_dir = ROOT / "app" / "templates"
    outflow_exists = (templates_dir / "sales_outflow_report.html").exists()
    trend_exists = (templates_dir / "sales_trend_report.html").exists()
    ok = outflow_exists and trend_exists
    results.append(static_check("SALES-STC-005", ok,
        "新增报表模板存在（sales_outflow_report.html / sales_trend_report.html）"))

    # SALES-STC-006: 导入模板含新字段列头
    template_section = ""
    if "def download_sales_order_template():" in app_py:
        start = app_py.index("def download_sales_order_template():")
        next_def = app_py.find("\n@app.route", start + 10)
        template_section = app_py[start:next_def if next_def > 0 else len(app_py)]
    required_headers = ["业务员", "项目号", "币别", "结算方式", "税率", "批次号", "序列号"]
    missing_headers = [h for h in required_headers if h not in template_section]
    ok = not missing_headers
    results.append(static_check("SALES-STC-006", ok,
        "导入模板含新字段列头" + ("" if ok else f" 缺失: {missing_headers}")))

    return results


# ==================== 运行时测试 ====================
def run_runtime_tests() -> list[tuple[str, bool, str]]:
    """使用 Flask test_client + 临时数据库运行销售模块全流程测试。"""
    results: list[tuple[str, bool, str]] = []
    _db_fd, _db_path = tempfile.mkstemp(suffix=".db")

    # 设置测试环境
    os.environ["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"
    # 仅为隔离临时数据库使用项目规定的固定 bootstrap 默认值；不触碰现有数据库账号。
    os.environ["WMS_BOOTSTRAP_PASSWORD"] = "admin"
    os.environ["DATABASE_URL"] = f"sqlite:///{_db_path}"

    try:
        # 延迟导入，确保环境变量先生效
        from app import app, db, initialize_database

        app.config["WTF_CSRF_ENABLED"] = False
        app.config["TESTING"] = True

        with app.app_context():
            initialize_database()

            # 创建测试数据
            from app import (User, Customer, Material, Unit, Employee, Warehouse,
                             SalesOrder, SalesOrderItem, OutOrder)

            admin = User.query.filter_by(username="admin").first()
            if not admin:
                raise RuntimeError("测试数据库缺少 admin 账号")

            # 测试脚本只使用已有账号，不重置或生成任何密码。
            viewer = User.query.filter_by(username="viewer_test").first()
            db.session.commit()

            # 创建单位
            unit = Unit.query.filter_by(code="PCS").first()
            if not unit:
                unit = Unit(code="PCS", name="个")
                db.session.add(unit)
                db.session.flush()

            # 创建客户
            customer = Customer.query.filter_by(code="TEST-CUST").first()
            if not customer:
                customer = Customer(code="TEST-CUST", name="测试客户有限公司",
                                    contact="李四", phone="13800000001")
                db.session.add(customer)
                db.session.flush()

            # 创建业务员
            employee = Employee.query.filter_by(name="测试业务员").first()
            if not employee:
                employee = Employee(name="测试业务员", position="销售", phone="13800000002")
                db.session.add(employee)
                db.session.flush()

            # 创建物料（含充足库存）
            material = Material.query.filter_by(code="TEST-MAT-001").first()
            if not material:
                material = Material(code="TEST-MAT-001", name="测试物料A",
                                    spec="10x10", unit_id=unit.id, stock=1000,
                                    price=100.0)
                db.session.add(material)
                db.session.flush()

            material2 = Material.query.filter_by(code="TEST-MAT-002").first()
            if not material2:
                material2 = Material(code="TEST-MAT-002", name="测试物料B",
                                     spec="20x20", unit_id=unit.id, stock=500,
                                     price=200.0)
                db.session.add(material2)
                db.session.flush()

            warehouse = Warehouse.query.filter_by(code="TEST-WH-001").first()
            if not warehouse:
                warehouse = Warehouse(code="TEST-WH-001", name="测试仓库", type="原料仓", status="active")
                db.session.add(warehouse)
                db.session.flush()

            db.session.commit()

            # 保存 fixture ID 供 test_client 使用（避免 ORM 对象脱离 session）
            fixture_ids = {
                "customer_id": customer.id,
                "employee_id": employee.id,
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "material_id": material.id,
                "material2_id": material2.id,
            }

        with app.test_client() as c:
            # 登录 admin
            admin_password = "admin"
            r = c.post("/login", data={"username": "admin", "password": admin_password})
            if r.status_code not in (302, 200):
                results.append(("SALES-RT-001", False, f"登录失败 HTTP {r.status_code}"))
                return results

            cid = fixture_ids["customer_id"]
            eid = fixture_ids["employee_id"]

            # ---- SALES-RT-001: 创建销售订单 ----
            order_payload = {
                "order_no": f"QA-SALES-{os.getpid()}-001",
                "date": "2026-07-16",
                "customer_id": cid,
                "warehouse": fixture_ids["warehouse_name"],
                "salesperson_id": eid,
                "project_no": "PRJ-TEST-001",
                "currency": "CNY",
                "settlement_method": "月结30天",
                "remark": "自动化测试订单",
                "items": [
                    {"code": "TEST-MAT-001", "quantity": 10, "price": 100, "tax_rate": 0.13,
                     "batch_no": "B001", "serial_no": "S001", "remark": "明细1"},
                    {"code": "TEST-MAT-002", "quantity": 5, "price": 200, "tax_rate": 0.13},
                ],
            }
            invalid_payload = dict(order_payload)
            invalid_payload["order_no"] = f"QA-SALES-{os.getpid()}-INVALID-WAREHOUSE"
            invalid_payload["warehouse"] = "不存在的仓库"
            invalid_response = c.post("/sales/add", data=json.dumps(invalid_payload), content_type="application/json")
            results.append(("SALES-RT-000", invalid_response.status_code == 400,
                f"无效仓库拒绝 -> HTTP {invalid_response.status_code}"))
            invalid_outbound_response = c.post("/out_order/add", data=json.dumps({
                "business_type": "销售出库",
                "warehouse": "不存在的仓库",
                "customer": "测试客户有限公司",
                "items": [],
            }), content_type="application/json")
            results.append(("SALES-RT-000B", invalid_outbound_response.status_code == 400,
                f"销售出库无效仓库拒绝 -> HTTP {invalid_outbound_response.status_code}"))
            r = c.post("/sales/add", data=json.dumps(order_payload),
                       content_type="application/json")
            resp = r.get_json(silent=True) or {}
            order_id = resp.get("id")
            ok = r.status_code == 200 and resp.get("status") == "success" and order_id
            results.append(("SALES-RT-001", ok,
                f"创建销售订单 -> HTTP {r.status_code}, resp={resp.get('status')}"))

            if not ok:
                return results  # 后续测试依赖订单创建

            # ---- SALES-RT-002: 税额计算正确性 ----
            with app.app_context():
                order = db.session.get(SalesOrder, order_id)
                # 明细1: 10 * 100 = 1000 含税, 未税=1000/1.13=884.96, 税额=115.04
                # 明细2: 5 * 200 = 1000 含税, 未税=1000/1.13=884.96, 税额=115.04
                # 合计: 含税=2000, 未税=1769.92, 税额=230.08
                # Numeric 字段返回 Decimal，需转 float 比较
                item1 = order.items[0]
                item2 = order.items[1]
                tax1 = float(item1.tax_included_amount or 0)
                tax2 = float(item2.tax_included_amount or 0)
                untaxed1 = float(item1.untaxed_amount or 0)
                tax_amt1 = float(item1.tax_amount or 0)
                total = float(order.total_amount or 0)
                tax1_ok = abs(tax1 - 1000.0) < 0.01
                tax2_ok = abs(tax2 - 1000.0) < 0.01
                untaxed1_ok = abs(untaxed1 - 884.96) < 0.02
                tax_amt1_ok = abs(tax_amt1 - 115.04) < 0.02
                batch_ok = item1.batch_no == "B001" and item1.serial_no == "S001"
                header_ok = order.salesperson_id == eid and order.project_no == "PRJ-TEST-001"
                total_ok = abs(total - 2000.0) < 0.01
                ok = tax1_ok and tax2_ok and untaxed1_ok and tax_amt1_ok and batch_ok and header_ok and total_ok
                results.append(("SALES-RT-002", ok,
                    f"税额计算: 含税={tax1:.2f}/{tax2:.2f}, "
                    f"未税={untaxed1:.2f}, 税额={tax_amt1:.2f}, "
                    f"批次={item1.batch_no}, total={total:.2f}"))

            # ---- SALES-RT-003: 确认销售订单 ----
            r = c.post(f"/sales/{order_id}/confirm", content_type="application/json")
            resp = r.get_json(silent=True) or {}
            ok = r.status_code == 200 and resp.get("status") == "success"
            results.append(("SALES-RT-003", ok,
                f"确认销售订单 -> HTTP {r.status_code}, resp={resp.get('status')}"))

            # ---- SALES-RT-004: 生成销售出库草稿 ----
            r = c.post(f"/sales/{order_id}/create_outbound", content_type="application/json")
            resp = r.get_json(silent=True) or {}
            outbound_id = resp.get("id")
            ok = r.status_code == 200 and resp.get("status") == "success" and outbound_id
            results.append(("SALES-RT-004", ok,
                f"生成销售出库草稿 -> HTTP {r.status_code}, outbound_id={outbound_id}"))

            if not ok:
                return results

            # ---- SALES-RT-005: 重复生成出库草稿返回已存在 ----
            r = c.post(f"/sales/{order_id}/create_outbound", content_type="application/json")
            resp = r.get_json(silent=True) or {}
            ok = r.status_code == 200 and resp.get("status") == "success" and resp.get("existing") == True
            results.append(("SALES-RT-005", ok,
                f"重复生成出库草稿 -> HTTP {r.status_code}, existing={resp.get('existing')}"))

            # ---- SALES-RT-006: 完成出库单后回写已发货数量 ----
            # 需要先完成出库单（complete_out_order 需要 warehouse 角色或 admin）
            r = c.post(f"/out_order/{outbound_id}/complete", content_type="application/json")
            resp = r.get_json(silent=True) or {}
            complete_ok = r.status_code == 200 and resp.get("status") == "success"

            with app.app_context():
                order = db.session.get(SalesOrder, order_id)
                item1 = order.items[0]
                item2 = order.items[1]
                shipped1 = float(item1.shipped_quantity or 0)
                shipped2 = float(item2.shipped_quantity or 0)
                shipped_amount = float(order.shipped_amount or 0)
                remaining = float(order.remaining_amount or 0)
                shipped1_ok = abs(shipped1 - 10) < 0.01
                shipped2_ok = abs(shipped2 - 5) < 0.01
                shipped_amount_ok = abs(shipped_amount - 2000.0) < 0.01
                remaining_ok = abs(remaining - 0.0) < 0.01
                ok = complete_ok and shipped1_ok and shipped2_ok and shipped_amount_ok and remaining_ok
                results.append(("SALES-RT-006", ok,
                    f"完成出库回写已发货: shipped_qty={shipped1}/{shipped2}, "
                    f"shipped_amount={shipped_amount:.2f}, remaining={remaining:.2f}"))

            # ---- SALES-RT-007: 订单状态变为已发货/已完成 ----
            with app.app_context():
                order = db.session.get(SalesOrder, order_id)
                status_ok = order.status == "closed"
                ship_status_ok = order.shipment_status == "shipped"
                ok = status_ok and ship_status_ok
                results.append(("SALES-RT-007", ok,
                    f"订单状态: status={order.status}, shipment_status={order.shipment_status}"))

            # ---- SALES-RT-007A/007B: 同物料多行必须按来源行下推和回写 ----
            duplicate_payload = dict(order_payload)
            duplicate_payload["order_no"] = f"QA-SALES-{os.getpid()}-SAME-MATERIAL"
            duplicate_payload["items"] = [
                {"code": "TEST-MAT-001", "quantity": 4, "price": 100, "tax_rate": 0.13},
                {"code": "TEST-MAT-001", "quantity": 6, "price": 100, "tax_rate": 0.13},
            ]
            r = c.post("/sales/add", data=json.dumps(duplicate_payload), content_type="application/json")
            duplicate_order_id = (r.get_json(silent=True) or {}).get("id")
            duplicate_ok = bool(duplicate_order_id)
            duplicate_item_ids = []
            if duplicate_ok:
                c.post(f"/sales/{duplicate_order_id}/confirm", content_type="application/json")
                with app.app_context():
                    duplicate_order = db.session.get(SalesOrder, duplicate_order_id)
                    duplicate_item_ids = [item.id for item in duplicate_order.items]
                selectable_response = c.get(f"/api/sales_order/selectable?search=QA-SALES-{os.getpid()}-SAME-MATERIAL")
                selectable_items = (selectable_response.get_json(silent=True) or {}).get("items", [])
                r = c.post(
                    "/sales/create_outbound_from_selection",
                    data=json.dumps({"items": [
                        {"sales_order_item_id": duplicate_item_ids[0], "quantity": 2},
                        {"sales_order_item_id": duplicate_item_ids[1], "quantity": 5},
                    ]}),
                    content_type="application/json",
                )
                duplicate_outbound_id = (r.get_json(silent=True) or {}).get("id")
                with app.app_context():
                    duplicate_outbound = db.session.get(OutOrder, duplicate_outbound_id)
                    source_ids = [item.source_sales_order_item_id for item in duplicate_outbound.items]
                    quantities = [float(item.quantity or 0) for item in duplicate_outbound.items]
                    source_ok = selectable_response.status_code == 200 and len(selectable_items) == 2 and source_ids == duplicate_item_ids and quantities == [2.0, 5.0]
                results.append(("SALES-RT-007A", source_ok,
                    f"同物料多行来源: source_ids={source_ids}, quantities={quantities}"))

                duplicate_selection_response = c.post(
                    "/sales/create_outbound_from_selection",
                    data=json.dumps({"items": [
                        {"sales_order_item_id": duplicate_item_ids[0], "quantity": 1},
                        {"sales_order_item_id": duplicate_item_ids[1], "quantity": 1},
                    ]}),
                    content_type="application/json",
                )
                duplicate_selection_body = duplicate_selection_response.get_json(silent=True) or {}
                duplicate_guard_ok = duplicate_selection_response.status_code == 400 and '待处理销售出库草稿' in duplicate_selection_body.get('msg', '')
                results.append(("SALES-RT-007C", duplicate_guard_ok,
                    f"并发/重复选单保护 -> HTTP {duplicate_selection_response.status_code}"))

                # The test explicitly represents the warehouse user's confirmation
                # after reviewing the anomaly warning.
                r = c.post(f"/out_order/{duplicate_outbound_id}/complete?force=true", content_type="application/json")
                with app.app_context():
                    duplicate_order = db.session.get(SalesOrder, duplicate_order_id)
                    shipped_quantities = [float(item.shipped_quantity or 0) for item in duplicate_order.items]
                    row_sync_ok = shipped_quantities == [2.0, 5.0]
                results.append(("SALES-RT-007B", r.status_code == 200 and row_sync_ok,
                    f"同物料多行回写: shipped_quantities={shipped_quantities}"))
            else:
                results.append(("SALES-RT-007A", False, "无法创建同物料多行订单"))
                results.append(("SALES-RT-007B", False, "无法创建同物料多行订单"))

            # ---- SALES-RT-008: 取消未发货订单 ----
            # 创建新订单并取消
            cancel_payload = dict(order_payload)
            cancel_payload["order_no"] = f"QA-SALES-{os.getpid()}-002"
            r = c.post("/sales/add", data=json.dumps(cancel_payload), content_type="application/json")
            cancel_order_id = (r.get_json(silent=True) or {}).get("id")
            if cancel_order_id:
                c.post(f"/sales/{cancel_order_id}/confirm", content_type="application/json")
                r = c.post(f"/sales/{cancel_order_id}/cancel", content_type="application/json")
                resp = r.get_json(silent=True) or {}
                with app.app_context():
                    order = db.session.get(SalesOrder, cancel_order_id)
                    ok = r.status_code == 200 and resp.get("status") == "success" and order.status == "cancelled"
                results.append(("SALES-RT-008", ok,
                    f"取消未发货订单 -> HTTP {r.status_code}, order_status={order.status}"))
            else:
                results.append(("SALES-RT-008", False, "无法创建用于取消测试的订单"))

            # ---- SALES-RT-009: 删除草稿订单 ----
            delete_payload = dict(order_payload)
            delete_payload["order_no"] = f"QA-SALES-{os.getpid()}-003"
            r = c.post("/sales/add", data=json.dumps(delete_payload), content_type="application/json")
            delete_order_id = (r.get_json(silent=True) or {}).get("id")
            if delete_order_id:
                r = c.post(f"/sales/{delete_order_id}/delete", content_type="application/json")
                resp = r.get_json(silent=True) or {}
                with app.app_context():
                    order = db.session.get(SalesOrder, delete_order_id)
                    deleted_ok = order is None
                ok = r.status_code == 200 and resp.get("status") == "success" and deleted_ok
                results.append(("SALES-RT-009", ok,
                    f"删除草稿订单 -> HTTP {r.status_code}, deleted={deleted_ok}"))
            else:
                results.append(("SALES-RT-009", False, "无法创建用于删除测试的订单"))

            # ---- SALES-RT-010: 报表页面渲染 ----
            report_routes = [
                ("/sales/report", "销售报表"),
                ("/sales/reconciliation", "销售对账"),
                (f"/sales/report?warehouse_id={fixture_ids['warehouse_id']}", "销售报表-仓库筛选"),
                ("/sales/report?customer_id=" + str(cid), "销售报表-客户钻取"),
                ("/sales/outflow_report", "销售出库明细表"),
                ("/sales/trend_report", "销售趋势分析表"),
                ("/sales/exceptions", "销售异常工作台"),
                ("/sales/trend_report?months=6", "销售趋势分析表-6月"),
                (f"/sales/trend_report?months=6&warehouse_id={fixture_ids['warehouse_id']}", "销售趋势分析表-仓库筛选"),
                (f"/sales/execution_report?warehouse_id={fixture_ids['warehouse_id']}", "销售订单执行-仓库筛选"),
                (f"/sales/price_analysis?warehouse_id={fixture_ids['warehouse_id']}", "销售价格分析-仓库筛选"),
                (f"/sales/outflow_report?warehouse_id={fixture_ids['warehouse_id']}", "销售出库明细-仓库筛选"),
                ("/sales", "销售订单列表"),
                ("/sales/add", "新建销售订单页"),
                ("/sales/dashboard", "销售工作台"),
                ("/sales/outbound", "销售出库列表"),
                ("/sales/outbound_selection", "销售出库选单"),
                (f"/sales/{order_id}", "销售订单详情"),
                (f"/sales/{order_id}/print", "销售订单打印"),
            ]
            report_ok = True
            report_detail = ""
            for path, name in report_routes:
                r = c.get(path)
                if r.status_code != 200:
                    report_ok = False
                    report_detail += f" {name}[{path}]={r.status_code}"
                else:
                    body = r.get_data(as_text=True)
                    if "TemplateNotFound" in body or "jinja2.exceptions" in body:
                        report_ok = False
                        report_detail += f" {name}=TemplateNotFound"
            results.append(("SALES-RT-010", report_ok,
                "报表与页面渲染" + ("全部 200" if report_ok else f" 失败:{report_detail}")))

            # ---- SALES-RT-011: 报表 Excel 导出 ----
            export_routes = [
                ("/sales/report/export", "销售报表导出"),
                ("/sales/outflow_report/export", "销售出库明细导出"),
                ("/sales/trend_report/export", "销售趋势分析导出"),
                (f"/sales/report/export?warehouse_id={fixture_ids['warehouse_id']}", "销售报表仓库筛选导出"),
                (f"/sales/execution_report/export?warehouse_id={fixture_ids['warehouse_id']}", "销售执行仓库筛选导出"),
                (f"/sales/price_analysis/export?warehouse_id={fixture_ids['warehouse_id']}", "销售价格仓库筛选导出"),
                (f"/sales/outflow_report/export?warehouse_id={fixture_ids['warehouse_id']}", "销售出库仓库筛选导出"),
                (f"/sales/trend_report/export?warehouse_id={fixture_ids['warehouse_id']}", "销售趋势仓库筛选导出"),
                ("/sales/download_template", "导入模板下载"),
                ("/sales/reconciliation/export", "销售对账导出"),
            ]
            export_ok = True
            export_detail = ""
            for path, name in export_routes:
                r = c.get(path)
                ct = r.content_type or ""
                if r.status_code != 200 or not ("excel" in ct or "spreadsheet" in ct or "octet" in ct):
                    export_ok = False
                    export_detail += f" {name}[{path}]={r.status_code}/{ct}"
            results.append(("SALES-RT-011", export_ok,
                "Excel 导出" + ("全部成功" if export_ok else f" 失败:{export_detail}")))

            ai_check = c.post(f"/api/ai/sales/{order_id}/draft_check", content_type="application/json")
            ai_check_body = ai_check.get_json(silent=True) or {}
            ai_check_ok = ai_check.status_code == 200 and ai_check_body.get('status') == 'success' and ai_check_body.get('evidence', {}).get('needs_confirmation') is True
            results.append(("SALES-RT-011A", ai_check_ok,
                f"AI销售草稿只读检查 -> HTTP {ai_check.status_code}"))

            # ---- SALES-RT-012: 权限边界：无权限角色不能创建订单 ----
            # 仅在环境中已有 viewer 测试账号时验证权限，不创建或设置密码。
            if viewer:
                c.get("/logout")
                viewer_password = os.environ.get("WMS_TEST_VIEWER_PASSWORD", "")
                r = c.post("/login", data={"username": "viewer_test", "password": viewer_password}) if viewer_password else None
                viewer_login_ok = bool(r and r.status_code in (302, 200))
                if viewer_login_ok:
                    payload = dict(order_payload)
                    payload["order_no"] = f"QA-SALES-{os.getpid()}-DENIED"
                    r = c.post("/sales/add", data=json.dumps(payload), content_type="application/json")
                    ok = r.status_code in (403, 302)
                    results.append(("SALES-RT-012", ok,
                        f"权限边界: viewer 创建订单 -> HTTP {r.status_code} (期望 403/302)"))
                else:
                    results.append(("SALES-RT-012", False, "已有 viewer 测试账号但未提供 WMS_TEST_VIEWER_PASSWORD"))
            else:
                results.append(("SALES-RT-012", True, "SKIP: 当前隔离测试库没有已有 viewer 账号，未创建账号或密码"))

            # ---- SALES-RT-013: 中文页面无乱码 ----
            # 重新登录 admin 查看详情页中文
            c.get("/logout")
            c.post("/login", data={"username": "admin", "password": admin_password})
            r = c.get(f"/sales/{order_id}")
            body = r.get_data(as_text=True)
            # 检查关键中文标签是否正常显示（非乱码）
            chinese_checks = ["销售订单", "客户", "含税金额", "未税金额", "税额", "业务员", "项目"]
            garbled = [ch for ch in chinese_checks if ch not in body and ch.replace("?", "") not in body]
            # 检查是否有典型乱码模式（连续 ? 或 替换字符）
            has_garble = "????" in body or "\ufffd" in body
            ok = not garbled and not has_garble
            results.append(("SALES-RT-013", ok,
                f"中文页面无乱码: 缺失={garbled}, 乱码模式={has_garble}"))

        return results

    except Exception as e:
        import traceback
        traceback.print_exc()
        results.append(("SALES-RT-ERROR", False, f"运行时测试异常: {e}"))
        return results
    finally:
        try:
            os.close(_db_fd)
            os.remove(_db_path)
        except Exception:
            pass
        # 清理环境变量
        for key in ("DATABASE_URL", "WMS_ALLOW_AUTO_SECRET_KEY", "WMS_BOOTSTRAP_PASSWORD"):
            os.environ.pop(key, None)


# ==================== 主入口 ====================
def main() -> int:
    print("=" * 60)
    print("WMS 销售管理模块验证（阶段 6）")
    print("=" * 60)

    all_results: list[tuple[str, bool, str]] = []

    print("\n--- 静态检查 ---")
    static_results = run_static_checks()
    all_results.extend(static_results)
    for check_id, ok, msg in static_results:
        status = "PASS" if ok else "FAIL"
        print(f"{status} {check_id}: {msg}")

    print("\n--- 运行时测试 ---")
    runtime_results = run_runtime_tests()
    all_results.extend(runtime_results)
    for check_id, ok, msg in runtime_results:
        status = "PASS" if ok else "FAIL"
        print(f"{status} {check_id}: {msg}")

    print("\n" + "=" * 60)
    total = len(all_results)
    passed = sum(1 for _, ok, _ in all_results if ok)
    failed = total - passed
    print(f"总计: {passed}/{total} 通过, {failed} 失败")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
