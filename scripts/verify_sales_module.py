#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WMS 销售管理模块验证脚本（阶段 6：测试与验收）。

覆盖范围：
  静态检查：
    SALES-STC-001  auto_migrate_database 含销售订单新字段 ALTER TABLE 迁移
    SALES-STC-002  recalculate_sales_order 实现税感知总额计算
    SALES-STC-003  build_sales_outbound_draft 含重复草稿防护
    SALES-STC-004  销售路由 require_role 权限装饰器
    SALES-STC-005  新增报表模板存在
    SALES-STC-006  导入模板含新字段列头

  运行时测试（Flask test_client + 临时数据库）：
    SALES-RT-001  创建销售订单（含税额字段）
    SALES-RT-002  税额计算正确性（含税/未税/税额）
    SALES-RT-003  确认销售订单
    SALES-RT-004  生成销售出库草稿
    SALES-RT-005  重复生成出库草稿返回已存在
    SALES-RT-006  完成出库单后回写已发货数量（一单一出）
    SALES-RT-007  订单状态变为已发货/已完成
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

    # SALES-STC-004: 销售路由权限装饰器
    sales_routes_section = app_py[app_py.index("def sales_order_add():"):]
    has_require_role = "@require_role" in sales_routes_section[:5000]
    results.append(static_check("SALES-STC-004", has_require_role,
        "销售订单写入路由使用 require_role 权限装饰器"))

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
    os.environ["WMS_BOOTSTRAP_PASSWORD"] = "TestAdmin@2026"
    os.environ["WMS_DATABASE_URI"] = f"sqlite:///{_db_path}"

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

            # 确保 admin 密码已知
            from werkzeug.security import generate_password_hash
            admin = User.query.filter_by(username="admin").first()
            if admin:
                admin.password_hash = generate_password_hash("TestAdmin@2026")
                admin.status = "normal"
            db.session.commit()

            # 创建只读角色用户（用于权限边界测试）
            viewer = User.query.filter_by(username="viewer_test").first()
            if not viewer:
                viewer = User(username="viewer_test",
                              password_hash=generate_password_hash("Viewer@2026"),
                              role="viewer", status="normal")
                db.session.add(viewer)
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

            db.session.commit()

            # 保存 fixture ID 供 test_client 使用（避免 ORM 对象脱离 session）
            fixture_ids = {
                "customer_id": customer.id,
                "employee_id": employee.id,
                "material_id": material.id,
                "material2_id": material2.id,
            }

        with app.test_client() as c:
            # 登录 admin
            r = c.post("/login", data={"username": "admin", "password": "TestAdmin@2026"})
            if r.status_code not in (302, 200):
                results.append(("SALES-RT-001", False, f"登录失败 HTTP {r.status_code}"))
                return results

            cid = fixture_ids["customer_id"]
            eid = fixture_ids["employee_id"]

            # ---- SALES-RT-001: 创建销售订单 ----
            order_payload = {
                "order_no": "SOTEST-001",
                "date": "2026-07-16",
                "customer_id": cid,
                "warehouse": "测试仓库",
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

            # ---- SALES-RT-008: 取消未发货订单 ----
            # 创建新订单并取消
            cancel_payload = dict(order_payload)
            cancel_payload["order_no"] = "SOTEST-002"
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
            delete_payload["order_no"] = "SOTEST-003"
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
                ("/sales/report?customer_id=" + str(cid), "销售报表-客户钻取"),
                ("/sales/outflow_report", "销售出库明细表"),
                ("/sales/trend_report", "销售趋势分析表"),
                ("/sales/trend_report?months=6", "销售趋势分析表-6月"),
                ("/sales", "销售订单列表"),
                ("/sales/add", "新建销售订单页"),
                ("/sales/dashboard", "销售工作台"),
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
                ("/sales/download_template", "导入模板下载"),
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

            # ---- SALES-RT-012: 权限边界：无权限角色不能创建订单 ----
            # 登出并登录 viewer
            c.get("/logout")
            r = c.post("/login", data={"username": "viewer_test", "password": "Viewer@2026"})
            viewer_login_ok = r.status_code in (302, 200)
            if viewer_login_ok:
                payload = dict(order_payload)
                payload["order_no"] = "SOTEST-DENIED"
                r = c.post("/sales/add", data=json.dumps(payload), content_type="application/json")
                # viewer 角色无权限，应返回 403 或重定向
                ok = r.status_code in (403, 302)
                results.append(("SALES-RT-012", ok,
                    f"权限边界: viewer 创建订单 -> HTTP {r.status_code} (期望 403/302)"))
            else:
                results.append(("SALES-RT-012", False, "viewer 登录失败"))

            # ---- SALES-RT-013: 中文页面无乱码 ----
            # 重新登录 admin 查看详情页中文
            c.get("/logout")
            c.post("/login", data={"username": "admin", "password": "TestAdmin@2026"})
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
        for key in ("WMS_DATABASE_URI", "WMS_ALLOW_AUTO_SECRET_KEY", "WMS_BOOTSTRAP_PASSWORD"):
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
