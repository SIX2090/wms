# -*- coding: utf-8 -*-
"""模块2：告警/报表/库存查询口径一致性深度检测。

对照 BUG-2026-10-06-001 教训：同一语义的多入口（PC 页面/手机 API/报表/AI 工具）
口径必须一致。逐个入口拉数据对比。
入口清单：
  - PC /alert（告警页）
  - 手机 /api/mobile/alert/list
  - 手机 /api/mobile/dashboard alert_count
  - PC / (首页 库存预警物料计数)
  - /stock_query（库存查询）
  - AI /api/ai/v2/tools/inventory/low-stock
  - 报表 /report*
"""
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import (app_module, fresh_env, stock_in, make_client,
                             check, get_json)
from app import (Warehouse, Material, db,
                 get_warehouse_stock_quantities)
import json


def alert_count_from_pc_home(c, wh_id=None):
    qs = f"?alert_warehouse_id={wh_id}" if wh_id else ""
    html = c.get(f"/{qs}").get_data(as_text=True)
    import re
    # 首页「库存预警物料」计数（从 html 里抠数字，宽匹配）
    m = re.search(r'库存预警[^0-9]{0,200}(\d+)', html)
    return int(m.group(1)) if m else None


def mobile_alert_list(c, wh_id):
    st, j = get_json(c, f"/api/mobile/alert/list?warehouse_id={wh_id}")
    if j and j.get("data"):
        return j["data"].get("total"), [i.get("code") for i in j["data"].get("items", [])]
    return None, None


def pc_alert_codes(c, wh_id):
    html = c.get(f"/alert?warehouse_id={wh_id}").get_data(as_text=True)
    return ("M001" in html), ("M002" in html)


def ai_low_stock(c, wh=None):
    qs = f"?warehouse={wh}" if wh else ""
    st, j = get_json(c, f"/api/ai/v2/tools/inventory/low-stock{qs}")
    return st, j


def mod2_consistency():
    with app_module.app.app_context():
        admin, mat = fresh_env()
        # 再建一个物料 M002：只进 B 仓（阈值 5，B 仓 3 件 → B 仓告警；A 仓无业务不告警）
        m2 = Material(code="M002", name="端子", spec="T2",
                      category_id=1, unit_id=1, stock=0, price=1, min_stock=5)
        db.session.add(m2); db.session.commit()
        c = make_client()
        stock_in(admin, mat, 3, "A仓")      # M001 A仓 3 < 5 → A 仓告警
        stock_in(admin, m2, 3, "B仓")       # M002 B仓 3 < 5 → B 仓告警
        wa = Warehouse.query.filter_by(code="WHA").first()
        wb = Warehouse.query.filter_by(code="WHB").first()

        print("== A 仓视角 ==")
        p1, p2 = pc_alert_codes(c, wa.id)
        check("PC /alert A仓: M001 告警", p1)
        check("PC /alert A仓: M002 不告警（非本仓业务）", not p2)
        total, codes = mobile_alert_list(c, wa.id)
        check("手机 alert/list A仓 total=1", total == 1, f"total={total} codes={codes}")
        st, d = get_json(c, f"/api/mobile/dashboard?warehouse_id={wa.id}")
        check("手机 dashboard A仓 alert_count=1",
              d and d.get("data", {}).get("alert_count") == 1,
              str(d)[:100] if d else "no json")

        print("== B 仓视角 ==")
        p1, p2 = pc_alert_codes(c, wb.id)
        check("PC /alert B仓: M002 告警", p2)
        check("PC /alert B仓: M001 不告警", not p1)
        total, codes = mobile_alert_list(c, wb.id)
        check("手机 alert/list B仓 total=1", total == 1, f"total={total} codes={codes}")

        print("== 全部仓库视角 ==")
        total, codes = mobile_alert_list(c, "all")
        check("手机 alert/list all total=2", total == 2, f"total={total} codes={codes}")
        st, d = get_json(c, "/api/mobile/dashboard?warehouse_id=all")
        check("手机 dashboard all alert_count=2",
              d and d.get("data", {}).get("alert_count") == 2,
              str(d)[:100] if d else "no json")
        # PC 全局首页
        n = alert_count_from_pc_home(c)
        print("PC 首页库存预警计数（全局）:", n)

        print("== AI 工具口径 ==")
        st, j = ai_low_stock(c)
        print("AI low-stock 全局:", st, json.dumps(j, ensure_ascii=False)[:200] if j else None)
        st, j = ai_low_stock(c, wh="A仓")
        print("AI low-stock A仓:", st, json.dumps(j, ensure_ascii=False)[:200] if j else None)

        print("== 报表入口 ==")
        for path in ["/report", "/report/dashboard", "/stock_query"]:
            r = c.get(path)
            print(f"GET {path}: {r.status_code}")


def mod2_stock_query():
    """库存查询页按仓过滤正确性。"""
    with app_module.app.app_context():
        admin, mat = fresh_env()
        m2 = Material(code="M002", name="端子", spec="T2",
                      category_id=1, unit_id=1, stock=0, price=1, min_stock=5)
        db.session.add(m2); db.session.commit()
        c = make_client()
        stock_in(admin, mat, 30, "A仓")
        stock_in(admin, m2, 20, "B仓")
        wa = Warehouse.query.filter_by(code="WHA").first()
        wb = Warehouse.query.filter_by(code="WHB").first()

        # A 仓查询：M001=30，M002 应为 0 或不显示
        html = c.get(f"/stock_query?warehouse_id={wa.id}").get_data(as_text=True)
        check("stock_query A仓含 M001", "M001" in html)
        # B 仓查询
        html_b = c.get(f"/stock_query?warehouse_id={wb.id}").get_data(as_text=True)
        check("stock_query B仓含 M002", "M002" in html_b)


if __name__ == "__main__":
    mod2_consistency()
    mod2_stock_query()
