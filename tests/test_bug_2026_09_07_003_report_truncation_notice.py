# -*- coding: utf-8 -*-
"""BUG-2026-09-07-003 回归：报表查询结果超限截断从「静默失真」改为「显式提示」。

背景：入库/出库/盘点/采购执行/台账流水超 REPORT_ROW_LIMIT(50000)/LEDGER_ROW_LIMIT
时，后端只写 warning 日志，页面 total 显示的是截断后的行数，汇总卡片也按截断
数据统计——用户不知道数据不完整（违反 AGENTS.md R2「汇总 = 明细」口径要求）。

修复：
  1. 新增 _report_check_row_limit() 统一截断检查：count 真实行数 → 超限记日志
     并把真实行数写入 flask.g._report_truncated_total（多次截断取最大值）；
  2. _build_report_payload 透传 truncated / raw_total / total_pages；
  3. /report/api/<type> 响应同步携带三个字段（R1：分页元数据完整）；
  4. report_view.html 截断时显示警告条「汇总按截断数据统计」，错误时隐藏。

断言：
  T1. 截断场景：payload truncated=True、raw_total=真实行数、total=截断后行数、
      total_pages 按截断后行数计算；g 标记读后即清不串下一次查询。
  T2. 未截断场景：truncated=False、raw_total==total、total_pages 正确。
  T3. API 层：/report/api/in_detail 响应含 truncated/raw_total/total_pages，
      截断时取值与函数层一致。
  T4. 模板锚点：report_view.html 含 truncationAlert 元素、renderTruncation
      调用与「汇总」「截断」提示文案。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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
from app import InOrder, InOrderItem, Material, Unit, User, Warehouse, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _filters(**overrides):
    base = {
        'start_date': None, 'end_date': None,
        'warehouse_id': 0, 'warehouse': '', 'warehouse_code': '',
        'business_type': '', 'material_code': '',
        'supplier_id': 0, 'supplier': '', 'customer': '', 'status': '',
        'sort_field': '', 'sort_order': 'asc',
        'page': 1, 'page_size': 20, 'hide_zero': False, 'export': '',
    }
    base.update(overrides)
    return base


class TestBug20260907003:
    def setup_method(self):
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            from werkzeug.security import generate_password_hash
            wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
            unit = Unit(code="PCS", name="个")
            user = User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False)
            db.session.add_all([wh, unit, user])
            db.session.flush()
            mat = Material(code="M001", name="电缆", unit_id=unit.id, price=10.0, stock=0.0)
            db.session.add(mat)
            db.session.flush()
            self.wh_id = wh.id
            # 3 张入库单 × 2 条明细 = 6 行
            for idx in range(3):
                order = InOrder(order_no=f"IN-{idx}", date=date.today(),
                                warehouse="仓库A", status="completed",
                                operator_id=user.id, business_type="采购入库")
                db.session.add(order)
                db.session.flush()
                for sub in range(2):
                    db.session.add(InOrderItem(
                        in_order_id=order.id, material_id=mat.id,
                        quantity=1, price=10.0, amount=10.0))
            db.session.commit()

    def test_T1_truncated_payload_marks_and_clears(self):
        """截断：导出路径超 REPORT_ROW_LIMIT 时 truncated=True、raw_total=真实行数。

        BUG-2026-09-07-004 起 in/out 明细展示路径改走 SQL 分页（每页最多
        page_size 行、total 为真实总数），截断只可能发生在导出的 5 万行
        上限保护；本用例以 export='excel' 验证截断透传与 g 读后清零。
        """
        with app_module.app.app_context():
            original = app_module.REPORT_ROW_LIMIT
            app_module.REPORT_ROW_LIMIT = 5
            try:
                payload = app_module._build_report_payload(
                    'in_detail', _filters(warehouse_id=self.wh_id, page_size=2,
                                          export='excel'))
            finally:
                app_module.REPORT_ROW_LIMIT = original
            assert payload['truncated'] is True, "导出超限必须标记截断"
            assert payload['raw_total'] == 6, f"raw_total 应为真实行数 6，实际 {payload['raw_total']}"
            assert len(payload['all_rows']) == 5, f"导出应截断到 5 行，实际 {len(payload['all_rows'])}"
            assert payload['total'] == 6, f"SQL 路径 total 为真实总数 6，实际 {payload['total']}"
            assert payload['total_pages'] == 3, f"6 行 / 每页 2 → 3 页，实际 {payload['total_pages']}"
            from flask import g as flask_g
            assert not getattr(flask_g, '_report_truncated_total', 0), "g 标记读后必须清零"

    def test_T2_not_truncated_payload(self):
        """未截断：truncated=False、raw_total==total、total_pages 向上取整。"""
        with app_module.app.app_context():
            payload = app_module._build_report_payload(
                'in_detail', _filters(warehouse_id=self.wh_id, page_size=4))
            assert payload['truncated'] is False
            assert payload['raw_total'] == 6
            assert payload['total'] == 6
            assert payload['total_pages'] == 2, f"6 行 / 每页 4 → 2 页，实际 {payload['total_pages']}"

    def test_T3_api_response_fields(self):
        """API：响应必含 truncated/raw_total/total_pages 分页元数据（R1）。

        BUG-2026-09-07-004 起 in_detail 展示路径走 SQL 分页：total 为真实
        总数 6、truncated=False（展示无截断概念）；truncated/raw_total 字段
        对未下沉报表与导出路径继续生效。
        """
        client = app_module.app.test_client()
        resp = client.post("/login", data={"username": "admin", "password": "admin"})
        assert resp.status_code in (200, 302), f"登录失败: {resp.status_code}"
        r = client.get(f"/report/api/in_detail?warehouse_id={self.wh_id}&page_size=2")
        assert r.status_code == 200, f"API 应 200，实际 {r.status_code}: {r.get_data(as_text=True)[:200]}"
        data = r.get_json()
        assert data['status'] == 'success'
        for field in ('truncated', 'raw_total', 'total_pages'):
            assert field in data, f"响应缺分页元数据字段 {field}"
        assert data['total'] == 6, f"SQL 路径 total 为真实总数 6，实际 {data['total']}"
        assert data['truncated'] is False
        assert data['raw_total'] == 6
        assert data['total_pages'] == 3

    def test_T4_template_anchors(self):
        """模板：截断警告条元素 + 渲染函数 + 提示文案锚点齐全。"""
        tpl = (ROOT / "app" / "templates" / "report_view.html").read_text(encoding="utf-8")
        assert 'id="truncationAlert"' in tpl, "缺截断警告条元素"
        assert 'renderTruncation(result)' in tpl, "loadData 成功分支必须渲染截断提示"
        assert 'renderTruncation(null)' in tpl, "错误分支必须隐藏截断提示"
        assert '汇总数据也按前' in tpl, "提示必须告知汇总按截断数据统计"
        assert '请缩小日期、仓库或物料范围' in tpl, "提示必须引导用户缩小查询范围"
