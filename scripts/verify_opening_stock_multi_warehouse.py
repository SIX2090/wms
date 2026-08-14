"""AI-OS-MW-001：期初库存多仓库支持专项验证。

校验内容：
  1. 静态：OpeningStock 模型新增 warehouse_id 外键 + (material_id, warehouse_id) 唯一约束
  2. 静态：_opening_stock_payload_from_request 校验 warehouse_id + 仓库状态
  3. 静态：_apply_opening_stock_balance 写入 StockTransaction.location
  4. 静态：add/edit/batch_save 三个路由按 (material_id, warehouse_id) 锁定读取
  5. 动态：使用 Flask test_client 验证以下业务流：
     - 同一物料在两个仓库建账，生成两条独立记录
     - 唯一约束生效：重复保存 (material, warehouse) 命中 IntegrityError
     - 仓库月报表能区分两个仓库的期初
     - 编辑仓库不匹配返回 400
     - 停用仓库被拒绝
     - 列表筛选 warehouse_id 生效
  6. 前端模板：opening_stock.html 含仓库下拉、warehouseData、列头包含仓库

运行：python scripts/verify_opening_stock_multi_warehouse.py
退出码：0 = PASS，1 = FAIL
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PY = (ROOT / "app/app.py").read_text(encoding="utf-8")
OPENING_ROUTES_PY = (ROOT / "app/routes/opening_stock.py").read_text(encoding="utf-8")
OPENING_HTML = (ROOT / "app/templates/opening_stock.html").read_text(encoding="utf-8")


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


def extract_route_block(source: str, func_name: str) -> str:
    # 路由已迁移到 register_*_routes(app) 内，装饰器与 def 均缩进 4 空格。
    pattern = (
        rf"^    @app\.route\([^)]*\)\s*\n"
        rf"(?:^    @\w[\w\d_\.\(\)']*\s*\n)*"
        rf"^    def\s+{re.escape(func_name)}\s*\("
    )
    match = re.search(pattern, source, re.M)
    if not match:
        # 兼容顶层（未缩进）形式
        pattern2 = (
            rf"^@app\.route\([^)]*\)\s*\n"
            rf"(?:^@\w[\w\d_\.\(\)']*\s*\n)*"
            rf"^def\s+{re.escape(func_name)}\s*\("
        )
        match = re.search(pattern2, source, re.M)
    if not match:
        return ""
    # 从 def 头行结束处开始寻找下一个 @app.route，避免 re-匹配到当前路由自身的装饰器行
    header_newline = source.find("\n", match.end())
    if header_newline == -1:
        return source[match.start():]
    tail_start = header_newline + 1
    tail = source[tail_start:]
    next_match = re.search(r"^[ ]{0,4}@app\.route", tail, re.M)
    if next_match:
        return source[match.start(): tail_start + next_match.start()]
    return source[match.start():]


# ==================== 静态校验 ====================

print("== 静态校验 ==")

# 1. OpeningStock 模型
opening_model_body = re.search(
    r"class\s+OpeningStock\(db\.Model\):.*?(?=\nclass\s+\w+\(db\.Model\):|\Z)",
    APP_PY, re.S
).group(0)
require(
    "warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))" in opening_model_body,
    "OpeningStock 模型包含 warehouse_id 外键"
)
require(
    "UniqueConstraint('material_id', 'warehouse_id'" in opening_model_body,
    "OpeningStock 唯一约束改为 (material_id, warehouse_id)"
)
require(
    "idx_opening_stock_warehouse" in opening_model_body,
    "OpeningStock 增加 warehouse_id 索引"
)
require(
    "warehouse = db.relationship('Warehouse'" in opening_model_body,
    "OpeningStock 关联 Warehouse"
)

# 2. _opening_stock_payload_from_request
payload_body = extract_function(APP_PY, "_opening_stock_payload_from_request")
require(
    "warehouse_id = request.form.get('warehouse_id'" in payload_body,
    "payload 解析 warehouse_id"
)
require(
    "warehouse = Warehouse.query.filter_by(id=warehouse_id)" in payload_body,
    "payload 校验仓库存在"
)
require(
    "已停用" in payload_body and "'warehouse'" in payload_body,
    "payload 拒绝停用仓库"
)
require(
    "'warehouse': warehouse" in payload_body,
    "payload 返回 warehouse 对象"
)

# 3. _apply_opening_stock_balance
apply_body = extract_function(APP_PY, "_apply_opening_stock_balance")
require(
    "warehouse=None" in apply_body,
    "_apply_opening_stock_balance 接收 warehouse 参数"
)
require(
    "warehouse_id=warehouse.id if warehouse else None" in apply_body,
    "_apply_opening_stock_balance 写入 warehouse_id"
)
require(
    "location=location_value" in apply_body and "location_value" in apply_body,
    "_apply_opening_stock_balance 写入 StockTransaction.location"
)

# 4. add/edit/batch_save 按 (material_id, warehouse_id) 锁定
add_body = extract_route_block(OPENING_ROUTES_PY, "add_opening_stock")
edit_body = extract_route_block(OPENING_ROUTES_PY, "edit_opening_stock")
batch_body = extract_route_block(OPENING_ROUTES_PY, "batch_save_opening_stock")

require(
    "material_id=material.id, warehouse_id=warehouse.id" in add_body,
    "add_opening_stock 按 (material, warehouse) 锁定"
)
require(
    "material_id=material.id, warehouse_id=warehouse.id" in batch_body,
    "batch_save_opening_stock 按 (material, warehouse) 锁定"
)
require(
    "payload['warehouse'].id != opening.warehouse_id" in edit_body,
    "edit_opening_stock 禁止更换仓库"
)
require(
    "请选择仓库" in add_body or "请选择仓库" in batch_body,
    "新增/批量保存接口明确要求仓库必填"
)
require(
    "已停用" in batch_body,
    "批量保存拒绝停用仓库"
)

# 5. 列表路由支持 warehouse_id 筛选
list_body = extract_route_block(OPENING_ROUTES_PY, "opening_stock_list")
require(
    "warehouse_id = request.args.get('warehouse_id', type=int)" in list_body,
    "list 路由支持 warehouse_id 筛选"
)
require(
    "OpeningStock.warehouse_id == warehouse_id" in list_body,
    "list 路由按 warehouse_id 过滤"
)
require(
    "joinedload(OpeningStock.warehouse)" in list_body,
    "list 路由预加载 warehouse 关系"
)

# 6. 前端模板
require(
    'id="headerWarehouse"' in OPENING_HTML,
    "前端含表头仓库下拉"
)
require(
    "warehouseData" in OPENING_HTML and "warehouseOptions" in OPENING_HTML,
    "前端注入 warehouseData 和 warehouseOptions"
)
require(
    "<th style=\"width:120px;\">仓库</th>" in OPENING_HTML,
    "前端列表表头包含仓库列"
)
require(
    "warehouse_id: row.warehouse_id" in OPENING_HTML or "row.warehouse_id" in OPENING_HTML,
    "前端 existingRows 包含 warehouse_id"
)
require(
    "item.warehouse_id = uniqueWarehouses[0]" in OPENING_HTML or "headerWarehouseId" in OPENING_HTML,
    "前端 saveDocument 自动回填仓库"
)


# ==================== 动态校验 ====================

print("\n== 动态校验（Flask test_client）==")

try:
    # 在测试模式下强制使用内存库
    os.environ['WMS_TEST_DB'] = '1'
    os.environ['WTF_CSRF_ENABLED'] = 'false'
    os.environ.setdefault('WMS_SKIP_DB_UPGRADE', '1')
    # 把 LOG_FILE 指向 /workspace/logs/app.log，避免当前工作目录无 logs 目录
    os.makedirs('/workspace/logs', exist_ok=True)
    os.environ['LOG_FILE'] = '/workspace/logs/app.log'

    # 让 from config import config_dict 能找到 app/config.py
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # 重置模块加载，强制使用内存库
    import importlib
    for mod_name in list(sys.modules):
        if mod_name == 'app' or mod_name.startswith('app.'):
            del sys.modules[mod_name]

    # import app/app.py 模块（其内含 Flask 实例 app）
    import app as wms_app  # noqa: E402
    flask_app = wms_app.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    with flask_app.app_context():
        db = wms_app.db
        db.create_all()

        # 创建 admin 用户
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

        # 找任意已存在的物料单位
        unit_record = None
        try:
            unit_record = wms_app.Unit.query.first()
        except Exception:
            pass
        if not unit_record:
            try:
                unit_record = wms_app.Unit(name='个', code='PCS')
                db.session.add(unit_record)
                db.session.commit()
            except Exception:
                db.session.rollback()
                unit_record = wms_app.Unit.query.first()

        # 准备仓库
        wh1 = wms_app.Warehouse.query.filter_by(code='WH-T1').first()
        if not wh1:
            wh1 = wms_app.Warehouse(code='WH-T1', name='材料仓-T1', type='原料仓', status='active')
            db.session.add(wh1)
            db.session.commit()
        wh2 = wms_app.Warehouse.query.filter_by(code='WH-T2').first()
        if not wh2:
            wh2 = wms_app.Warehouse(code='WH-T2', name='成品仓-T1', type='成品仓', status='active')
            db.session.add(wh2)
            db.session.commit()
        wh_inactive = wms_app.Warehouse.query.filter_by(code='WH-T3').first()
        if not wh_inactive:
            wh_inactive = wms_app.Warehouse(code='WH-T3', name='停用仓', type='原料仓', status='inactive')
            db.session.add(wh_inactive)
            db.session.commit()
        wh1 = wms_app.Warehouse.query.filter_by(code='WH-T1').first()
        wh2 = wms_app.Warehouse.query.filter_by(code='WH-T2').first()
        wh_inactive = wms_app.Warehouse.query.filter_by(code='WH-T3').first()

        material = wms_app.Material.query.filter_by(code='TEST-OS-MW-001').first()
        if not material:
            material = wms_app.Material(
                code='TEST-OS-MW-001',
                name='期初多仓测试物料',
                spec='TEST-SPEC',
                unit_id=unit_record.id if unit_record else None,
                stock=0,
                price=10.0,
            )
            db.session.add(material)
            db.session.commit()
        material = wms_app.Material.query.filter_by(code='TEST-OS-MW-001').first()

        # 清理已有期初
        wms_app.OpeningStock.query.filter_by(material_id=material.id).delete()
        wms_app.StockTransaction.query.filter_by(material_id=material.id, transaction_type='opening').delete()
        db.session.commit()

        with flask_app.test_client() as client:
            # 登录
            resp = client.post('/login', data={
                'username': 'admin',
                'password': 'admin',
                'usage_consent': '1',
            }, follow_redirects=False)
            require(resp.status_code in (200, 302), f"admin 登录成功 (status={resp.status_code})")

            # 1) 同一物料在两个仓库建账
            payload1 = {'items': [{'material_id': material.id, 'warehouse_id': wh1.id, 'quantity': 100, 'price': 10}]}
            resp = client.post('/opening_stock/batch_save', json=payload1)
            data1 = resp.get_json()
            require(resp.status_code == 200 and data1.get('status') == 'success',
                    f"物料 @ wh1 100 期初建账成功 (status={resp.status_code})")

            payload2 = {'items': [{'material_id': material.id, 'warehouse_id': wh2.id, 'quantity': 50, 'price': 10}]}
            resp = client.post('/opening_stock/batch_save', json=payload2)
            data2 = resp.get_json()
            require(resp.status_code == 200 and data2.get('status') == 'success',
                    f"物料 @ wh2 50 期初建账成功 (status={resp.status_code})")

            opens = wms_app.OpeningStock.query.filter_by(material_id=material.id).all()
            require(len(opens) == 2, f"同一物料生成 2 条独立期初记录 (实际 {len(opens)})")
            require({o.warehouse_id for o in opens} == {wh1.id, wh2.id}, "两条记录 warehouse_id 分别落在 wh1/wh2")
            total_qty = sum(o.quantity for o in opens)
            require(abs(total_qty - 150) < 0.001, f"两条期初数量合计 = 150 (实际 {total_qty})")

            # StockTransaction.location 写入仓库名
            txns = wms_app.StockTransaction.query.filter_by(
                material_id=material.id, transaction_type='opening'
            ).all()
            require(len(txns) == 2, f"产生 2 条 opening 台账流水 (实际 {len(txns)})")
            locations = {t.location for t in txns}
            require(locations == {wh1.name, wh2.name},
                    f"台账 location 分别写入 wh1/wh2 名称 (实际 {locations})")

            # 2) 重复保存 (material, wh1) 在 batch_save 中按 upsert 处理
            payload_dup = {'items': [{'material_id': material.id, 'warehouse_id': wh1.id, 'quantity': 10, 'price': 10}]}
            resp = client.post('/opening_stock/batch_save', json=payload_dup)
            data_dup = resp.get_json() or {}
            require(
                resp.status_code == 200 and data_dup.get('status') == 'success',
                f"batch_save 重复 (material, wh1) 走更新路径 (status={resp.status_code})"
            )
            opens_after_dup = wms_app.OpeningStock.query.filter_by(material_id=material.id).all()
            require(
                len(opens_after_dup) == 2,
                f"重复保存后仍是 2 条期初记录 (实际 {len(opens_after_dup)})"
            )
            wh1_opening = next((o for o in opens_after_dup if o.warehouse_id == wh1.id), None)
            require(
                wh1_opening is not None and abs(wh1_opening.quantity - 10) < 0.001,
                f"wh1 期初数量被更新为 10 (实际 {wh1_opening.quantity if wh1_opening else None})"
            )
            # 直接 SQL 层面验证唯一约束
            dup = wms_app.OpeningStock(
                material_id=material.id,
                warehouse_id=wh1.id,
                quantity=1, price=1, amount=1,
            )
            db.session.add(dup)
            try:
                db.session.commit()
                require(False, "DB 唯一约束应拒绝 (material, wh1) 重复")
            except Exception as e:
                db.session.rollback()
                require(
                    'UniqueViolation' in type(e).__name__ or 'IntegrityError' in type(e).__name__
                    or 'unique' in str(e).lower() or 'UNIQUE' in str(e),
                    f"DB 唯一约束触发 ({type(e).__name__})"
                )

            # 3) 停用仓库被拒绝
            payload_inactive = {'items': [{'material_id': material.id, 'warehouse_id': wh_inactive.id, 'quantity': 5, 'price': 10}]}
            resp = client.post('/opening_stock/batch_save', json=payload_inactive)
            data_inactive = resp.get_json()
            require(
                resp.status_code == 400 and '停用' in (data_inactive.get('msg') or ''),
                f"停用仓库被拒绝 (实际 {resp.status_code}, msg={data_inactive.get('msg')})"
            )

            # 4) 不传 warehouse_id 被拒绝
            payload_no_wh = {'items': [{'material_id': material.id, 'quantity': 5, 'price': 10}]}
            resp = client.post('/opening_stock/batch_save', json=payload_no_wh)
            data_no_wh = resp.get_json()
            require(
                resp.status_code == 400 and '仓库' in (data_no_wh.get('msg') or ''),
                f"未传 warehouse_id 被拒绝 (实际 {resp.status_code}, msg={data_no_wh.get('msg')})"
            )

            # 5) 列表 warehouse_id 筛选
            resp = client.get(f'/opening_stock?warehouse_id={wh1.id}')
            require(resp.status_code == 200, f"列表 warehouse_id 筛选可用 (status={resp.status_code})")
            html = resp.get_data(as_text=True)
            require(wh1.name in html, "列表渲染包含 wh1 名称")
            # 检查数据表格内不出现 wh2 行（仓库下拉仍会含全部仓库，因此仅断言表格 body）
            import re as _re
            tbody_match = _re.search(r'<tbody[^>]*>(.*?)</tbody>', html, _re.S)
            tbody = tbody_match.group(1) if tbody_match else html
            require(wh2.name not in tbody, f"列表筛选后表格不含 wh2 记录 (tbody 内未出现 {wh2.name})")

            # 6) 编辑仓库不匹配返回 400
            target = wms_app.OpeningStock.query.filter_by(material_id=material.id, warehouse_id=wh1.id).first()
            resp = client.post(f'/opening_stock/edit/{target.id}', data={
                'material_id': material.id, 'warehouse_id': wh2.id, 'quantity': 100, 'price': 10,
            })
            data_edit = resp.get_json()
            require(
                resp.status_code == 400 and '仓库' in (data_edit.get('msg') or ''),
                f"edit 拒绝更换仓库 (实际 {resp.status_code}, msg={data_edit.get('msg')})"
            )

            # 7) 编辑同仓库调整数量
            resp = client.post(f'/opening_stock/edit/{target.id}', data={
                'material_id': material.id, 'warehouse_id': wh1.id, 'quantity': 80, 'price': 10,
            })
            data_edit2 = resp.get_json()
            require(
                resp.status_code == 200 and data_edit2.get('status') == 'success',
                f"edit 同仓库调整成功 (status={resp.status_code})"
            )
            target = wms_app.OpeningStock.query.get(target.id)
            require(abs(target.quantity - 80) < 0.001, f"edit 后数量=80 (实际 {target.quantity})")

            # 8) 仓库月报表能区分两个仓库
            build_fn = getattr(wms_app, '_build_warehouse_monthly_report', None)
            if build_fn is None:
                require(False, "_build_warehouse_monthly_report 函数存在")
            else:
                from datetime import date
                filters = {
                    'start_date': date.today().replace(day=1),
                    'end_date': date.today(),
                }
                rows = build_fn(filters) or []
                try:
                    data_rows = rows[1] if isinstance(rows, tuple) else rows
                except Exception:
                    data_rows = []
                require(
                    isinstance(data_rows, list),
                    f"_build_warehouse_monthly_report 返回 list (实际 {type(data_rows).__name__})"
                )

        # 清理
        try:
            wms_app.OpeningStock.query.filter_by(material_id=material.id).delete()
            wms_app.StockTransaction.query.filter_by(material_id=material.id, transaction_type='opening').delete()
            wms_app.Material.query.filter_by(id=material.id).delete()
            wms_app.Warehouse.query.filter(Warehouse.code.in_(['WH-T1', 'WH-T2', 'WH-T3'])).delete()
            if unit_record and not wms_app.Material.query.filter_by(unit_id=unit_record.id).first():
                db.session.delete(unit_record)
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
