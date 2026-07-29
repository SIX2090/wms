"""库存台账必须按单一物料查询 + 物料名称/规格列专项验证。

校验：
  1. 静态：_ledger_columns 含 物料编码/物料名称/规格型号 列
  2. 静态：_build_ledger_report 未传 material_code 返回空 + 零汇总
  3. 静态：report_view.html 物料搜索在 ledger 报为 required 并显示提示
  4. 静态：report_view.html loadData 在 material_code 为空时不发请求
  5. 动态：ledger 报表无 material_code 返回 columns + 空 data + 0/0/0 汇总
  6. 动态：ledger 报表带 material_code 返回带物料编码/名称/规格的行
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PY = (ROOT / "app/app.py").read_text(encoding="utf-8")
REPORT_HTML = (ROOT / "app/templates/report_view.html").read_text(encoding="utf-8")

FAILURES: list[str] = []
PASSED: list[str] = []


def require(condition: bool, message: str) -> None:
    if condition:
        print(f"PASS  {message}")
        PASSED.append(message)
    else:
        print(f"FAIL  {message}")
        FAILURES.append(message)


def extract_function(source: str, name: str) -> str:
    match = re.search(rf"^def\s+{re.escape(name)}\s*\(", source, re.M)
    if not match:
        return ""
    rest = source[match.start():]
    next_match = re.search(r"^(@app\.route|^def\s+\w+\s*\()", rest[1:], re.M)
    if next_match:
        return rest[: next_match.start() + 1]
    return rest


# ==================== 静态校验 ====================
print("== 静态校验 ==")

# 1. _ledger_columns 含物料三列
ledger_cols = extract_function(APP_PY, "_ledger_columns")
require(
    "'material_code', 'title': '物料编码'" in ledger_cols,
    "_ledger_columns 含「物料编码」列"
)
require(
    "'material_name', 'title': '物料名称'" in ledger_cols,
    "_ledger_columns 含「物料名称」列"
)
require(
    "'spec', 'title': '规格型号'" in ledger_cols,
    "_ledger_columns 含「规格型号」列"
)

# 2. _build_ledger_report 未传物料时返回空数据
build_ledger = extract_function(APP_PY, "_build_ledger_report")
require(
    "if not (filters.get('material_code') or '').strip():" in build_ledger,
    "_build_ledger_report 检测 material_code 为空"
)
require(
    "return _ledger_columns(), [], empty_summary" in build_ledger,
    "_build_ledger_report 未传物料返回空 rows + 零汇总"
)

# 3. report_view.html 物料搜索在 ledger 报为必填
require(
    "{% if report_type == 'ledger' %} <span class=\"text-danger\">*</span>{% endif %}" in REPORT_HTML,
    "report_view.html 物料标签含 ledger 必填星号"
)
require(
    "{% if report_type == 'ledger' %} required{% endif %}" in REPORT_HTML,
    "report_view.html 物料输入框在 ledger 添加 required"
)
require(
    "库存台账需按单一物料查询" in REPORT_HTML,
    "report_view.html 显示 ledger 物料必填提示"
)

# 4. loadData 在 material_code 空时不发请求
require(
    "reportType === 'ledger' && !filterForm.querySelector('#material_code').value.trim()" in REPORT_HTML,
    "loadData 在 ledger 物料为空时拦截请求"
)
require(
    "_defaultLedgerColumns" in REPORT_HTML,
    "loadData 命中拦截时使用 ledger 默认表头"
)

# 5. 空数据提示
require(
    "请先在筛选条件中选择一个物料" in REPORT_HTML,
    "report_view.html ledger 空数据提示引导选择物料"
)


# ==================== 动态校验 ====================
print("\n== 动态校验（Flask test_client）==")

try:
    os.environ['WMS_TEST_DB'] = '1'
    os.environ['WTF_CSRF_ENABLED'] = 'false'
    os.environ.setdefault('WMS_SKIP_DB_UPGRADE', '1')
    os.makedirs('/workspace/logs', exist_ok=True)
    os.environ['LOG_FILE'] = '/workspace/logs/app.log'

    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    import importlib
    for mod_name in list(sys.modules):
        if mod_name == 'app' or mod_name.startswith('app.'):
            del sys.modules[mod_name]

    import app as wms_app
    flask_app = wms_app.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app_context():
        db = wms_app.db
        db.create_all()

        admin = wms_app.User.query.filter_by(username='admin').first()
        if not admin:
            admin = wms_app.User(username='admin', role='admin')
            if hasattr(admin, 'set_password'):
                admin.set_password('admin')
            else:
                from werkzeug.security import generate_password_hash
                admin.password_hash = generate_password_hash('admin')
            db.session.add(admin)
            db.session.commit()

        unit = wms_app.Unit.query.first()
        if not unit:
            try:
                unit = wms_app.Unit(name='个', code='PCS')
                db.session.add(unit)
                db.session.commit()
            except Exception:
                db.session.rollback()
                unit = wms_app.Unit.query.first()

        # 准备两个物料用于测试
        m1 = wms_app.Material.query.filter_by(code='TEST-LEDGER-001').first()
        if not m1:
            m1 = wms_app.Material(
                code='TEST-LEDGER-001',
                name='库存台账测试物料A',
                spec='M8×20',
                unit_id=unit.id if unit else None,
                stock=100.0,
                price=5.0,
            )
            db.session.add(m1)
            db.session.commit()
        m1 = wms_app.Material.query.filter_by(code='TEST-LEDGER-001').first()

        m2 = wms_app.Material.query.filter_by(code='TEST-LEDGER-002').first()
        if not m2:
            m2 = wms_app.Material(
                code='TEST-LEDGER-002',
                name='库存台账测试物料B',
                spec='M10×30',
                unit_id=unit.id if unit else None,
                stock=50.0,
                price=8.0,
            )
            db.session.add(m2)
            db.session.commit()
        m2 = wms_app.Material.query.filter_by(code='TEST-LEDGER-002').first()

        # 清理已有流水
        wms_app.StockTransaction.query.filter(
            wms_app.StockTransaction.material_id.in_([m1.id, m2.id])
        ).delete(synchronize_session=False)
        db.session.commit()

        # 创建物料 A 的两条流水
        db.session.add(wms_app.StockTransaction(
            material_id=m1.id, transaction_type='in', quantity=10,
            location='主仓', reference_type='in_order', reference_id=1,
            remark='入库A', created_at=__import__('datetime').datetime(2026, 1, 1, 10, 0, 0),
        ))
        db.session.add(wms_app.StockTransaction(
            material_id=m1.id, transaction_type='out', quantity=-3,
            location='主仓', reference_type='out_order', reference_id=2,
            remark='出库A', created_at=__import__('datetime').datetime(2026, 1, 2, 10, 0, 0),
        ))
        # 物料 B 也来一条
        db.session.add(wms_app.StockTransaction(
            material_id=m2.id, transaction_type='in', quantity=5,
            location='主仓', reference_type='in_order', reference_id=3,
            remark='入库B', created_at=__import__('datetime').datetime(2026, 1, 3, 10, 0, 0),
        ))
        db.session.commit()

        with flask_app.test_client() as client:
            resp = client.post('/login', data={
                'username': 'admin', 'password': 'admin', 'usage_consent': '1',
            }, follow_redirects=False)
            require(resp.status_code in (200, 302), f"admin 登录成功 (status={resp.status_code})")

            # 1) 不传 material_code：返回空 + 列齐全
            resp = client.get('/report/api/ledger?report_type=ledger')
            require(resp.status_code == 200, f"ledger 报表接口可访问 (status={resp.status_code})")
            data = resp.get_json()
            require(data.get('status') == 'success', f"ledger 返回 success 状态 (实际 {data.get('status')})")
            columns = data.get('columns') or []
            column_fields = [c.get('field') for c in columns]
            require('material_code' in column_fields, f"columns 含 material_code 字段 (实际 {column_fields})")
            require('material_name' in column_fields, f"columns 含 material_name 字段 (实际 {column_fields})")
            require('spec' in column_fields, f"columns 含 spec 字段 (实际 {column_fields})")
            require(len(data.get('data') or []) == 0, f"未传物料时 data 为空 (实际 {len(data.get('data') or [])} 行)")
            summary = data.get('summary') or {}
            require(summary.get('count') == 0, f"未传物料时 count=0 (实际 {summary.get('count')})")
            require(summary.get('quantity') == 0, f"未传物料时 quantity=0 (实际 {summary.get('quantity')})")
            require(summary.get('amount') == 0, f"未传物料时 amount=0 (实际 {summary.get('amount')})")

            # 2) 传 material_code=A：只返回 A 的流水
            resp = client.get(f'/report/api/ledger?report_type=ledger&material_code={m1.code}')
            data = resp.get_json()
            require(data.get('status') == 'success', f"ledger 按物料 A 查询 success (实际 {data.get('status')})")
            rows = data.get('data') or []
            require(len(rows) == 2, f"物料 A 返回 2 条流水 (实际 {len(rows)})")
            material_codes = {row.get('material_code') for row in rows}
            require(material_codes == {m1.code}, f"全部 row 物料编码 = {m1.code} (实际 {material_codes})")
            material_names = {row.get('material_name') for row in rows}
            require(m1.name in material_names, f"row 物料名称 = {m1.name} (实际 {material_names})")
            specs = {row.get('spec') for row in rows}
            require('M8×20' in specs, f"row 规格 = M8×20 (实际 {specs})")
            summary = data.get('summary') or {}
            require(summary.get('count') == 2, f"物料 A count=2 (实际 {summary.get('count')})")
            # 10 入库 + 3 出库 = 13
            require(abs(summary.get('quantity') - 13) < 0.001, f"物料 A quantity=13 (实际 {summary.get('quantity')})")

            # 3) 物料 B：只返回 B 的 1 条
            resp = client.get(f'/report/api/ledger?report_type=ledger&material_code={m2.code}')
            data = resp.get_json()
            rows = data.get('data') or []
            require(len(rows) == 1, f"物料 B 返回 1 条流水 (实际 {len(rows)})")
            require((rows[0].get('material_code') if rows else '') == m2.code, f"物料 B 唯一 row 物料编码正确")

            # 4) 物料名称模糊查询：A
            resp = client.get('/report/api/ledger?report_type=ledger&material_code=' + '库存台账测试物料A')
            data = resp.get_json()
            rows = data.get('data') or []
            require(len(rows) == 2, f"按物料名称模糊查询 A 返回 2 条 (实际 {len(rows)})")

            # 5) 规格模糊查询：M10
            resp = client.get('/report/api/ledger?report_type=ledger&material_code=M10')
            data = resp.get_json()
            rows = data.get('data') or []
            require(len(rows) == 1, f"按规格 M10 模糊查询返回 1 条 (实际 {len(rows)})")

        # 清理
        try:
            wms_app.StockTransaction.query.filter(
                wms_app.StockTransaction.material_id.in_([m1.id, m2.id])
            ).delete(synchronize_session=False)
            wms_app.Material.query.filter(Material.id.in_([m1.id, m2.id])).delete(synchronize_session=False)
            db.session.commit()
        except Exception:
            db.session.rollback()

except Exception as e:
    FAILURES.append(f"动态校验异常: {type(e).__name__}: {e}")
    print(f"FAIL  动态校验异常: {type(e).__name__}: {e}")
    traceback.print_exc()


# ==================== 汇总 ====================
print()
print(f"通过: {len(PASSED)}")
print(f"失败: {len(FAILURES)}")

if FAILURES:
    print("\n失败项：")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
sys.exit(0)
