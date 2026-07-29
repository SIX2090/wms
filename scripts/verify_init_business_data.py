"""业务数据初始化（系统重置）专项验证（AI-INIT-001）。

校验：
  1. 静态：app.py 含 INIT_CONFIRM_PHRASE 常量与 6 张清理清单（业务/明细/库存/日志/AI/主数据）
  2. 静态：app.py 含 preview/execute 两条路由 + 反提交 + 库存归零 + 批量删除 helper
  3. 静态：system_settings.html 含危险卡片 + Modal + 二次确认 + 确认短语前端校验
  4. 静态：SystemSetting / WechatShareConfig 已在清理清单
  5. 动态：登录后访问 /system_settings/init_business_data/preview 返回 success
  6. 动态：execute 错密码 → 403
  7. 动态：execute 错确认短语 → 400
  8. 动态：execute 准备数据（物料+采购入库完成+草稿+流水）后正确密码+正确短语成功
        - completed 单据全部反提交为 pending
        - 物料库存归零
        - 单据+明细+流水清空
        - 物料/客户/供应商/仓库等主数据也清空
        - User 账号保留（admin 自身不删）
        - OperationAudit 至少保留本次 preview+done 两条
        - 再次 preview 应返回所有计数为 0
"""

from __future__ import annotations

import os
import re
import sys
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PY = (ROOT / "app/app.py").read_text(encoding="utf-8")
TEMPLATE_HTML = (ROOT / "app/templates/system_settings.html").read_text(encoding="utf-8")

FAILURES: list[str] = []
PASSED: list[str] = []


def require(condition: bool, message: str) -> None:
    if condition:
        print(f"PASS  {message}")
        PASSED.append(message)
    else:
        print(f"FAIL  {message}")
        FAILURES.append(message)


# ==================== 静态校验 ====================
print("== 静态校验 ==")

# 1. 关键常量与清单
require(
    "INIT_CONFIRM_PHRASE = '初始化业务数据'" in APP_PY,
    "INIT_CONFIRM_PHRASE = '初始化业务数据'"
)
require(
    "INIT_BUSINESS_TABLES = [" in APP_PY and "InOrder" in APP_PY and "OutOrder" in APP_PY,
    "INIT_BUSINESS_TABLES 清单存在"
)
require(
    "INIT_BUSINESS_ITEM_TABLES = [" in APP_PY and "InOrderItem" in APP_PY and "OutOrderItem" in APP_PY,
    "INIT_BUSINESS_ITEM_TABLES 清单存在"
)
require(
    "INIT_INVENTORY_TABLES = [" in APP_PY and "StockTransaction" in APP_PY and "OpeningStock" in APP_PY,
    "INIT_INVENTORY_TABLES 清单存在"
)
require(
    "INIT_LOG_TABLES = [" in APP_PY
    and "OperationLog" in APP_PY
    and "LoginLog" in APP_PY
    and "ApiToken" in APP_PY
    and "WechatShareLog" in APP_PY
    and "WechatShareConfig" in APP_PY
    and "SystemSetting" in APP_PY,
    "INIT_LOG_TABLES 清单含 OperationLog/LoginLog/ApiToken/WechatShareLog/WechatShareConfig/SystemSetting"
)
require(
    "INIT_AI_TABLES = [" in APP_PY and "AIRun" in APP_PY and "AIDocumentJob" in APP_PY,
    "INIT_AI_TABLES 清单存在"
)
require(
    "INIT_MASTER_TABLES = [" in APP_PY
    and "Material" in APP_PY
    and "Supplier" in APP_PY
    and "Customer" in APP_PY
    and "Warehouse" in APP_PY,
    "INIT_MASTER_TABLES 清单含 Material/Supplier/Customer/Warehouse"
)

# 2. 关键函数与路由
require(
    "def _revert_completed_to_pending" in APP_PY,
    "辅助函数 _revert_completed_to_pending 存在"
)
require(
    "def _zero_all_material_stock" in APP_PY,
    "辅助函数 _zero_all_material_stock 存在"
)
require(
    "def _bulk_delete_model" in APP_PY,
    "辅助函数 _bulk_delete_model 存在"
)
require(
    "def _init_business_data_keep_users_and_settings" in APP_PY,
    "核心清理函数 _init_business_data_keep_users_and_settings 存在"
)
require(
    "@app.route('/system_settings/init_business_data/preview', methods=['GET'])" in APP_PY,
    "路由 /system_settings/init_business_data/preview 已注册"
)
require(
    "@app.route('/system_settings/init_business_data/execute', methods=['POST'])" in APP_PY,
    "路由 /system_settings/init_business_data/execute 已注册"
)
require(
    "check_password_hash(current_user.password_hash, admin_password)" in APP_PY,
    "execute 路由使用 check_password_hash 校验当前管理员密码"
)
require(
    "confirm_phrase != INIT_CONFIRM_PHRASE" in APP_PY,
    "execute 路由校验确认短语"
)
require(
    "'init_business_data_preview'" in APP_PY
    and "'init_business_data_done'" in APP_PY
    and "'init_business_data_failed'" in APP_PY,
    "OperationAudit 含 preview/done/failed 三种 operation"
)
# AGENTS.md 硬规则：禁止直接删除已完成单据 → 必须先反提交
require(
    "def _revert_completed_to_pending" in APP_PY
    and "filter_by(status='completed').update" in APP_PY,
    "执行前先 reverse completed -> pending（遵循 AGENTS.md 硬规则）"
)

# 3. 模板与前端
require(
    "id=\"openInitModalBtn\"" in TEMPLATE_HTML,
    "系统设置页含「打开初始化向导」按钮"
)
require(
    "id=\"initBusinessDataModal\"" in TEMPLATE_HTML,
    "系统设置页含 initBusinessDataModal 模态框"
)
require(
    "id=\"initAdminPassword\"" in TEMPLATE_HTML and "id=\"initConfirmPhrase\"" in TEMPLATE_HTML,
    "模态框含管理员密码 + 确认短语输入框"
)
require(
    "INIT_CONFIRM_PHRASE_FRONT = '初始化业务数据'" in TEMPLATE_HTML,
    "前端常量 INIT_CONFIRM_PHRASE_FRONT 同步"
)
require(
    "/system_settings/init_business_data/preview" in TEMPLATE_HTML
    and "/system_settings/init_business_data/execute" in TEMPLATE_HTML,
    "前端 fetch 调用 preview + execute 路由"
)
require(
    "init_business_data" in TEMPLATE_HTML.lower() and "initExec" not in TEMPLATE_HTML,
    "前端展示「初始化业务数据」标题"
)
# 危险提示
require(
    "exclamation-triangle" in TEMPLATE_HTML and "border-danger" in TEMPLATE_HTML,
    "危险卡片视觉提示"
)


# ==================== 动态校验 ====================
print("\n== 动态校验（Flask test_client）==")

try:
    # 隔离 DB
    test_db = '/tmp/test_init_business_data.db'
    if os.path.exists(test_db):
        os.unlink(test_db)

    os.environ['WMS_TEST_DB'] = test_db
    os.environ['WTF_CSRF_ENABLED'] = 'false'
    os.environ['WMS_SKIP_DB_UPGRADE'] = '1'
    os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
    os.makedirs('/workspace/logs', exist_ok=True)
    os.environ['LOG_FILE'] = '/workspace/logs/app.log'

    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    for mod_name in list(sys.modules):
        if mod_name == 'app' or mod_name.startswith('app.'):
            del sys.modules[mod_name]

    import app as wms_app
    flask_app = wms_app.app
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{test_db}'

    with flask_app.app_context():
        db = wms_app.db
        db.create_all()

        # 准备 admin + 2 个普通用户
        from werkzeug.security import generate_password_hash
        admin = wms_app.User.query.filter_by(username='admin').first()
        if not admin:
            admin = wms_app.User(
                username='admin', role='admin',
                password_hash=generate_password_hash('admin'),
            )
            db.session.add(admin)
        u1 = wms_app.User.query.filter_by(username='init_user1').first()
        if not u1:
            u1 = wms_app.User(
                username='init_user1', role='warehouse',
                password_hash=generate_password_hash('pw1'),
            )
            db.session.add(u1)
        u2 = wms_app.User.query.filter_by(username='init_user2').first()
        if not u2:
            u2 = wms_app.User(
                username='init_user2', role='sales',
                password_hash=generate_password_hash('pw2'),
            )
            db.session.add(u2)
        db.session.commit()

        # 准备主数据：单位、分类、供应商、客户、仓库、物料
        unit = wms_app.Unit.query.first()
        if not unit:
            unit = wms_app.Unit(name='个', code='PCS')
            db.session.add(unit)
            db.session.commit()
        cat = wms_app.MaterialCategory.query.first()
        if not cat:
            cat = wms_app.MaterialCategory(name='默认分类', code='CAT-INIT')
            db.session.add(cat)
            db.session.commit()
        sup = wms_app.Supplier.query.first()
        if not sup:
            sup = wms_app.Supplier(name='初始化供应商', code='SUP-INIT')
            db.session.add(sup)
            db.session.commit()
        cust = wms_app.Customer.query.first()
        if not cust:
            cust = wms_app.Customer(name='初始化客户', code='CUS-INIT')
            db.session.add(cust)
            db.session.commit()
        wh = wms_app.Warehouse.query.first()
        if not wh:
            wh = wms_app.Warehouse(name='初始化仓库', code='WH-INIT', status='active')
            db.session.add(wh)
            db.session.commit()
        m1 = wms_app.Material.query.filter_by(code='MAT-INIT-001').first()
        if not m1:
            m1 = wms_app.Material(
                code='MAT-INIT-001', name='初始化物料A', spec='M8',
                unit_id=unit.id, category_id=cat.id, supplier_id=sup.id,
                stock=100.0, price=5.0,
            )
            db.session.add(m1)
        m2 = wms_app.Material.query.filter_by(code='MAT-INIT-002').first()
        if not m2:
            m2 = wms_app.Material(
                code='MAT-INIT-002', name='初始化物料B', spec='M10',
                unit_id=unit.id, category_id=cat.id, supplier_id=sup.id,
                stock=50.0, price=8.0,
            )
            db.session.add(m2)
        db.session.commit()
        m1 = wms_app.Material.query.filter_by(code='MAT-INIT-001').first()
        m2 = wms_app.Material.query.filter_by(code='MAT-INIT-002').first()

        # 准备业务数据：1 张 completed 采购入库 + 1 张草稿 + StockTransaction
        from datetime import datetime
        in_completed = wms_app.InOrder(
            order_no='IN-INIT-COMPLETED-001',
            business_type='采购入库',
            supplier_id=sup.id,
            warehouse='初始化仓库',
            operator_id=admin.id,
            status='completed',
            date=datetime.now(),
        )
        db.session.add(in_completed)
        db.session.flush()
        db.session.add(wms_app.InOrderItem(
            in_order_id=in_completed.id,
            material_id=m1.id, quantity=10.0, price=5.0, amount=50.0,
        ))

        in_draft = wms_app.InOrder(
            order_no='IN-INIT-DRAFT-001',
            business_type='采购入库',
            supplier_id=sup.id,
            warehouse='初始化仓库',
            operator_id=admin.id,
            status='pending',
            date=datetime.now(),
        )
        db.session.add(in_draft)
        db.session.flush()
        db.session.add(wms_app.InOrderItem(
            in_order_id=in_draft.id,
            material_id=m2.id, quantity=5.0, price=8.0, amount=40.0,
        ))

        # 库存流水
        db.session.add(wms_app.StockTransaction(
            material_id=m1.id, transaction_type='in', quantity=10.0,
            location='初始化仓库', reference_type='in_order', reference_id=in_completed.id,
            remark='INIT-TEST',
        ))
        # 系统参数
        existing_setting = wms_app.SystemSetting.query.filter_by(key='test_init_setting').first()
        if not existing_setting:
            db.session.add(wms_app.SystemSetting(key='test_init_setting', value='hello'))
        # 微信分享配置
        if not wms_app.WechatShareConfig.query.first():
            db.session.add(wms_app.WechatShareConfig(
                sender_name='init_sender', receiver_name='init_receiver',
            ))
        # 登录日志
        db.session.add(wms_app.LoginLog(username='admin', status='success'))
        # 业务日志
        db.session.add(wms_app.OperationLog(
            user_id=admin.id, operation_type='init_test', operation_content='prep',
        ))
        # AI 运行
        db.session.add(wms_app.AIRun(
            user_id=admin.id, request_id='init-test-req-001',
            request_hash='deadbeef', endpoint='/test/init',
        ))
        db.session.commit()

        with flask_app.test_client() as client:
            # 登录 admin
            resp = client.post('/login', data={
                'username': 'admin', 'password': 'admin', 'usage_consent': '1',
            }, follow_redirects=False)
            require(resp.status_code in (200, 302), f"admin 登录成功 (status={resp.status_code})")

            # 1) preview 接口
            resp = client.get('/system_settings/init_business_data/preview')
            require(resp.status_code == 200, f"preview 接口返回 200 (实际 {resp.status_code})")
            data = resp.get_json() or {}
            require(data.get('status') == 'success', f"preview status=success (实际 {data.get('status')})")
            preview_data = data.get('data') or {}
            require(preview_data.get('user_count', 0) >= 3, f"preview 报告 user_count≥3 (实际 {preview_data.get('user_count')})")
            # 业务单据主表应包含 InOrder
            business_counts = {it['label']: it['count'] for it in preview_data.get('business', [])}
            require(business_counts.get('采购入库单', 0) >= 2, f"preview 报告 InOrder 计数≥2 (实际 {business_counts})")
            require(
                preview_data.get('inventory') and any(it.get('count', 0) > 0 for it in preview_data['inventory']),
                "preview 报告库存/流水计数 > 0"
            )

            # 2) execute 错密码 → 403
            resp = client.post('/system_settings/init_business_data/execute', data={
                'admin_password': 'wrong_pwd',
                'confirm_phrase': '初始化业务数据',
                'include_master_data': '1',
            })
            require(resp.status_code == 403, f"错密码 403 (实际 {resp.status_code})")
            err = resp.get_json() or {}
            require('密码' in (err.get('msg') or ''), f"错密码错误消息含「密码」(实际 {err.get('msg')})")

            # 3) execute 错确认短语 → 400
            resp = client.post('/system_settings/init_business_data/execute', data={
                'admin_password': 'admin',
                'confirm_phrase': '不对的短语',
                'include_master_data': '1',
            })
            require(resp.status_code == 400, f"错确认短语 400 (实际 {resp.status_code})")
            err = resp.get_json() or {}
            require('确认短语' in (err.get('msg') or ''), f"错短语错误消息含「确认短语」(实际 {err.get('msg')})")

            # 4) execute 正确密码+正确短语 → success
            resp = client.post('/system_settings/init_business_data/execute', data={
                'admin_password': 'admin',
                'confirm_phrase': '初始化业务数据',
                'include_master_data': '1',
            })
            require(resp.status_code == 200, f"正确凭据 execute 200 (实际 {resp.status_code})")
            result = resp.get_json() or {}
            require(result.get('status') == 'success', f"正确凭据 success (实际 {result.get('status')})")
            data_data = result.get('data') or {}
            require(
                data_data.get('reverted_to_pending', 0) >= 1,
                f"execute 后 reverted_to_pending≥1 (实际 {data_data.get('reverted_to_pending')})"
            )
            require(
                data_data.get('zeroed_materials', 0) >= 2,
                f"execute 后 zeroed_materials≥2 (实际 {data_data.get('zeroed_materials')})"
            )
            require(
                data_data.get('business', 0) >= 2,
                f"execute 后 business 计数≥2 (实际 {data_data.get('business')})"
            )
            require(
                data_data.get('master', 0) >= 4,
                f"execute 后 master 计数≥4 (实际 {data_data.get('master')})"
            )

            # 5) 数据已被清空
            in_orders = wms_app.InOrder.query.count()
            require(in_orders == 0, f"InOrder 表清空 (实际 {in_orders})")
            in_items = wms_app.InOrderItem.query.count()
            require(in_items == 0, f"InOrderItem 表清空 (实际 {in_items})")
            stock_tx = wms_app.StockTransaction.query.count()
            require(stock_tx == 0, f"StockTransaction 表清空 (实际 {stock_tx})")
            mats = wms_app.Material.query.count()
            require(mats == 0, f"Material 表清空 (实际 {mats})")
            sups = wms_app.Supplier.query.count()
            require(sups == 0, f"Supplier 表清空 (实际 {sups})")
            whs = wms_app.Warehouse.query.count()
            require(whs == 0, f"Warehouse 表清空 (实际 {whs})")
            ai_runs = wms_app.AIRun.query.count()
            require(ai_runs == 0, f"AIRun 表清空 (实际 {ai_runs})")
            op_logs = wms_app.OperationLog.query.count()
            require(op_logs == 0, f"OperationLog 表清空 (实际 {op_logs})")
            login_logs = wms_app.LoginLog.query.count()
            require(login_logs == 0, f"LoginLog 表清空 (实际 {login_logs})")
            settings = wms_app.SystemSetting.query.count()
            require(settings == 0, f"SystemSetting 表清空 (实际 {settings})")
            wechat_cfg = wms_app.WechatShareConfig.query.count()
            require(wechat_cfg == 0, f"WechatShareConfig 表清空 (实际 {wechat_cfg})")

            # 6) User 账号保留
            users = wms_app.User.query.count()
            require(users >= 3, f"User 保留 ≥3 (实际 {users})")
            admin_after = wms_app.User.query.filter_by(username='admin').first()
            require(admin_after is not None, "admin 账号自身被保留")
            from werkzeug.security import check_password_hash
            require(
                check_password_hash(admin_after.password_hash, 'admin'),
                "admin 密码哈希仍可校验 'admin'"
            )

            # 7) OperationAudit 至少保留 preview+done 两条
            audits = wms_app.OperationAudit.query.filter(
                wms_app.OperationAudit.operation.in_([
                    'init_business_data_preview',
                    'init_business_data_done',
                ])
            ).all()
            require(
                len(audits) >= 2,
                f"OperationAudit 至少保留 preview+done 两条 (实际 {len(audits)})"
            )
            ops = {a.operation for a in audits}
            require(
                'init_business_data_preview' in ops and 'init_business_data_done' in ops,
                f"OperationAudit 包含 preview + done (实际 {ops})"
            )

            # 8) 再次 preview 应全部为 0
            resp = client.get('/system_settings/init_business_data/preview')
            data = resp.get_json() or {}
            preview_data2 = data.get('data') or {}
            for group_key in ('business', 'business_items', 'inventory', 'logs', 'ai', 'master'):
                items = preview_data2.get(group_key) or []
                nonzero = [(it.get('label'), it.get('count')) for it in items if (it.get('count') or 0) > 0]
                require(
                    not nonzero,
                    f"再次 preview {group_key} 全部为 0 (实际非零 {nonzero})"
                )

except Exception:
    traceback.print_exc()
    FAILURES.append('动态校验异常')


print(f"\n通过: {len(PASSED)}")
print(f"失败: {len(FAILURES)}")
if FAILURES:
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
sys.exit(0)
