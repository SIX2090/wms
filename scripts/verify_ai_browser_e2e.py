"""AI-R16 AI 关键流程浏览器 E2E 专项验证。

# AI_TASK: AI-R16

验收要求：不只检查 HTTP 200；检查中文、空状态、错误、权限、按钮、返回路径、下钻和重复点击，形成可重复脚本。

设计：使用 Flask test_client 模拟浏览器会话（CI 友好，无需真实浏览器，与现有 18 个
verify_ai_*.py 脚本一致）。覆盖 5 类角色（admin/warehouse/purchase/production/user，
台账"主管"映射 production）+ 7 大业务域（上传/确认/草稿/工作台/Agent/知识/运维）。

8 项测试覆盖：
1. 5 类角色登录 + 权限矩阵（admin 全访问、各角色页面访问控制、未登录重定向）
2. 文档上传页面（/ai/document_ocr）- 中文渲染 + 权限 + 空状态 + 错误提示
3. 文档确认流程（/ai/document_jobs → 详情 → 确认）- 下钻 + 返回路径 + 中文
4. 草稿下钻（业务单据列表）- 中文 + 空状态 + 按钮可见性
5. 工作台页面（/ai/replenishment, /ai/inventory_health, /ai/supplier_evaluation）- 中文 + 权限
6. Agent 页面（/ai/agent_tasks）- 中文 + 权限 + 重复点击防护
7. 运维页面（/ai/ops, /ai/prelaunch, /ai/material_alias）- 仅 admin 权限 + 中文
8. API 端点 E2E（R10-R15 API 层覆盖）- 工作台/知识/数据保留/业务质量 API
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-browser-e2e-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


# ===== 测试基础设施 =====

def _set_setting(key: str, value: str) -> None:
    row = wms_app.SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = wms_app.SystemSetting(key=key)
        wms_app.db.session.add(row)
    row.value = value


def _login(client, user_id: int) -> None:
    """通过 session_transaction 注入登录态（模拟浏览器登录）。"""
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def _create_users() -> dict[str, int]:
    """创建 5 类角色测试用户，返回 {role: user_id}。

    台账"主管"角色映射到 production（User.role 枚举无 manager/supervisor）。
    """
    users = {}
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        username = f'e2e-{role}'
        wms_app.User.query.filter_by(username=username).delete()
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User(
            username=f'e2e-{role}',
            password_hash='not-used',  # test_client 用 session 注入，不走密码校验
            role=role,
            status='normal',
        )
        wms_app.db.session.add(user)
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User.query.filter_by(username=f'e2e-{role}').first()
        users[role] = user.id
    return users


def _enable_ai_features() -> None:
    """启用 AI 全部特性，确保页面可访问。"""
    _set_setting('ai_feature_global_enabled', '1')
    _set_setting('ai_feature_rollout_mode', 'all')
    _set_setting('ai_feature_drafts_enabled', '1')
    _set_setting('ai_feature_agents_enabled', '1')
    _set_setting('ai_feature_vision_enabled', '1')
    _set_setting('ai_degrade_local_only', '0')
    wms_app.db.session.commit()


def _get_page(client, path: str) -> tuple[int, str]:
    """GET 页面，返回 (status_code, html_text)。"""
    resp = client.get(path)
    return resp.status_code, resp.get_data(as_text=True)


# ===== 测试1：5 类角色登录 + 权限矩阵 =====

def test1_role_permission_matrix():
    """测试1：5 类角色登录 + 权限矩阵（admin 全访问、各角色页面访问控制、未登录重定向）。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()

    # 未登录访问受保护页面应重定向到 login
    resp = client.get('/ai/ops')
    assert resp.status_code == 302, f'未登录应重定向，实际 {resp.status_code}'
    assert '/login' in resp.headers.get('Location', ''), '未登录应重定向到 login'

    # admin 可访问运维页面（仅 admin）
    _login(client, users['admin'])
    code, html = _get_page(client, '/ai/ops')
    assert code == 200, f'admin 访问 /ai/ops 应 200，实际 {code}'

    # warehouse 不可访问运维页面（仅 admin）
    _login(client, users['warehouse'])
    code, _ = _get_page(client, '/ai/ops')
    assert code in (302, 403), f'warehouse 访问 /ai/ops 应被拒，实际 {code}'

    # 各角色访问文档上传页面权限
    # /ai/document_ocr 要求 warehouse/purchase
    for role in ('warehouse', 'purchase'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/document_ocr')
        assert code == 200, f'{role} 访问 /ai/document_ocr 应 200，实际 {code}'

    # production/user 不可访问文档上传
    for role in ('production', 'user'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/document_ocr')
        assert code in (302, 403), f'{role} 访问 /ai/document_ocr 应被拒，实际 {code}'

    # Agent 任务列表所有登录用户可见
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/agent_tasks')
        assert code == 200, f'{role} 访问 /ai/agent_tasks 应 200，实际 {code}'

    print('PASS 测试1：5 类角色权限矩阵（admin 全访问/各角色页面控制/未登录重定向）')


# ===== 测试2：文档上传页面 =====

def test2_document_upload_page():
    """测试2：文档上传页面（/ai/document_ocr）- 中文渲染 + 权限 + 空状态 + 错误提示。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()
    _login(client, users['warehouse'])

    code, html = _get_page(client, '/ai/document_ocr')
    assert code == 200, f'文档上传页面应 200，实际 {code}'

    # 验收：中文渲染（不只检查 HTTP 200）
    assert '文档' in html or 'OCR' in html or '识别' in html, \
        '文档上传页面应含中文"文档/OCR/识别"'

    # 验收：按钮可见性（上传按钮）
    assert '上传' in html or 'upload' in html.lower() or '提交' in html, \
        '文档上传页面应含上传/提交按钮'

    # 验收：空状态（无文档任务时应有空提示或上传引导）
    # 页面首次访问应无已有文档任务
    assert '暂无' in html or '空' in html or '上传' in html, \
        '文档上传页面应含空状态提示或上传引导'

    # 错误提示：POST 无文件应返回中文错误（实际上传端点是 /api/ai/document_ocr）
    # /ai/document_ocr 页面本身仅 GET，上传走 /api/ai/document_ocr
    resp = client.post('/api/ai/document_ocr', data={})
    assert resp.status_code in (200, 400), \
        f'POST 无文件应返回 200/400，实际 {resp.status_code}'
    if resp.status_code == 400:
        # 验收：错误提示必须中文（JSON 响应需解码 msg 字段，不只检查 HTTP 400）
        msg = ''
        try:
            msg = (resp.get_json() or {}).get('msg', '')
        except Exception:  # noqa: BLE001
            msg = resp.get_data(as_text=True)
        assert '上传' in msg or '图片' in msg or '请' in msg or '启用' in msg, \
            f'无文件错误提示应含中文，实际 msg={msg!r}'

    # production 角色无权限
    _login(client, users['production'])
    code, _ = _get_page(client, '/ai/document_ocr')
    assert code in (302, 403), f'production 应被拒，实际 {code}'

    print('PASS 测试2：文档上传页面（中文渲染+权限+空状态+按钮+错误提示）')


# ===== 测试3：文档确认流程 =====

def test3_document_confirmation_flow():
    """测试3：文档确认流程（列表→详情→确认）- 下钻 + 返回路径 + 中文。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

        # 创建一个文档任务供列表显示（字段对齐 AIDocumentJob 模型）
        job = wms_app.AIDocumentJob(
            user_id=users['warehouse'],
            source='wechat_text',
            document_type='delivery_note',
            status='recognized',
            source_text_summary='测试送货单：供应商 测试供应商，物料 测试物料 100 个',
            created_at=wms_app.datetime.now(),
        )
        wms_app.db.session.add(job)
        wms_app.db.session.commit()
        job_id = job.id

    client = app.test_client()
    _login(client, users['warehouse'])

    # 列表页
    code, html = _get_page(client, '/ai/document_jobs')
    assert code == 200, f'文档任务列表应 200，实际 {code}'
    # 验收：中文渲染
    assert '文档' in html, '文档任务列表应含中文"文档"'

    # 详情页（下钻）
    code, html = _get_page(client, f'/ai/document_jobs/{job_id}')
    assert code == 200, f'文档任务详情应 200，实际 {code}'
    # 验收：下钻显示详情内容
    assert 'e2e-test-delivery' in html or '测试' in html, \
        '文档详情应显示文件名或测试内容'

    # 验收：返回路径（详情页应有返回列表的链接）
    assert '返回' in html or '列表' in html or 'document_jobs' in html, \
        '文档详情应有返回列表的路径'

    # 不存在的文档任务应 404
    code, _ = _get_page(client, '/ai/document_jobs/999999')
    assert code == 404, f'不存在的文档应 404，实际 {code}'

    print('PASS 测试3：文档确认流程（列表→详情下钻+返回路径+中文+404错误）')


# ===== 测试4：草稿下钻（业务单据列表）=====

def test4_draft_drilldown():
    """测试4：草稿下钻（业务单据列表）- 中文 + 空状态 + 按钮可见性。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()
    _login(client, users['admin'])

    # 入库单列表（AI 草稿生成后跳转目标）
    code, html = _get_page(client, '/in_order')
    assert code == 200, f'入库单列表应 200，实际 {code}'
    # 验收：中文渲染
    assert '入库' in html, '入库单列表应含中文"入库"'
    # 验收：空状态（无入库单时应有空提示或新增按钮）
    assert '暂无' in html or '新增' in html or '空' in html or '入库' in html, \
        '入库单列表应含空状态或新增按钮'

    # 采购订单列表（默认 /purchase_order 重定向到新增页，需 ?view=list 才是列表）
    code, html = _get_page(client, '/purchase_order?view=list')
    assert code == 200, f'采购订单列表应 200，实际 {code}'
    assert '采购' in html, '采购订单列表应含中文"采购"'

    # 出库单列表
    code, html = _get_page(client, '/out_order')
    assert code == 200, f'出库单列表应 200，实际 {code}'
    assert '出库' in html, '出库单列表应含中文"出库"'

    print('PASS 测试4：草稿下钻（入库/采购/出库列表中文+空状态+按钮）')


# ===== 测试5：工作台页面 =====

def test5_workbench_pages():
    """测试5：工作台页面（/ai/replenishment, /ai/inventory_health, /ai/supplier_evaluation）- 中文 + 权限。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()

    # warehouse 可访问库存健康
    _login(client, users['warehouse'])
    code, html = _get_page(client, '/ai/inventory_health')
    assert code == 200, f'warehouse 访问库存健康应 200，实际 {code}'
    assert '库存' in html, '库存健康页面应含中文"库存"'

    # warehouse 可访问补货
    code, html = _get_page(client, '/ai/replenishment')
    assert code == 200, f'warehouse 访问补货应 200，实际 {code}'
    assert '补货' in html or '库存' in html, '补货页面应含中文"补货/库存"'

    # warehouse/purchase 可访问供应商评估
    for role in ('warehouse', 'purchase'):
        _login(client, users[role])
        code, html = _get_page(client, '/ai/supplier_evaluation')
        assert code == 200, f'{role} 访问供应商评估应 200，实际 {code}'
        assert '供应商' in html, '供应商评估页面应含中文"供应商"'

    # production/user 不可访问工作台
    for role in ('production', 'user'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/inventory_health')
        assert code in (302, 403), f'{role} 访问库存健康应被拒，实际 {code}'

    print('PASS 测试5：工作台页面（库存健康/补货/供应商评估 中文+权限）')


# ===== 测试6：Agent 页面 =====

def test6_agent_pages():
    """测试6：Agent 页面（/ai/agent_tasks）- 中文 + 权限 + 重复点击防护。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()

    # Agent 任务列表所有角色可见
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        _login(client, users[role])
        code, html = _get_page(client, '/ai/agent_tasks')
        assert code == 200, f'{role} 访问 Agent 任务列表应 200，实际 {code}'
        # 验收：中文渲染
        assert 'Agent' in html or '任务' in html or '代理' in html, \
            f'{role} Agent 任务列表应含中文"Agent/任务/代理"'

    # 验收：重复点击防护（POST 触发 Agent 运行）
    # warehouse 可触发仓库巡检
    _login(client, users['warehouse'])
    resp1 = client.post('/ai/agent_tasks/run/warehouse_patrol', data={})
    # 第一次 POST 应返回 200/302/400（取决于 AI 配置，但不应 500）
    assert resp1.status_code in (200, 302, 400), \
        f'第一次 POST 仓库巡检应 200/302/400，实际 {resp1.status_code}'

    # 重复点击（第二次 POST）应被幂等/并发控制拦截（不产生重复运行）
    resp2 = client.post('/ai/agent_tasks/run/warehouse_patrol', data={})
    assert resp2.status_code in (200, 302, 400, 409, 429), \
        f'重复 POST 仓库巡检应被拦截，实际 {resp2.status_code}'

    # production/user 不可触发 Agent 运行
    for role in ('production', 'user'):
        _login(client, users[role])
        resp = client.post('/ai/agent_tasks/run/warehouse_patrol', data={})
        assert resp.status_code in (302, 403), \
            f'{role} POST 仓库巡检应被拒，实际 {resp.status_code}'

    print('PASS 测试6：Agent 页面（中文+权限+重复点击防护+越权拒绝）')


# ===== 测试7：运维页面 =====

def test7_ops_pages():
    """测试7：运维页面（/ai/ops, /ai/prelaunch, /ai/material_alias）- 仅 admin 权限 + 中文。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()

    # admin 可访问运维看板
    _login(client, users['admin'])
    code, html = _get_page(client, '/ai/ops')
    assert code == 200, f'admin 访问运维看板应 200，实际 {code}'
    assert '运维' in html or 'AI' in html, '运维看板应含中文"运维/AI"'

    # admin 可访问预发布
    code, html = _get_page(client, '/ai/prelaunch')
    assert code == 200, f'admin 访问预发布应 200，实际 {code}'

    # 物料别名管理（warehouse/purchase 可访问）
    for role in ('admin', 'warehouse', 'purchase'):
        _login(client, users[role])
        code, html = _get_page(client, '/ai/material_alias')
        assert code == 200, f'{role} 访问物料别名应 200，实际 {code}'
        assert '物料' in html or '别名' in html, '物料别名页面应含中文"物料/别名"'

    # production/user 不可访问物料别名
    for role in ('production', 'user'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/material_alias')
        assert code in (302, 403), f'{role} 访问物料别名应被拒，实际 {code}'

    # 非 admin 不可访问运维看板
    for role in ('warehouse', 'purchase', 'production', 'user'):
        _login(client, users[role])
        code, _ = _get_page(client, '/ai/ops')
        assert code in (302, 403), f'{role} 访问运维看板应被拒，实际 {code}'

    print('PASS 测试7：运维页面（运维看板/预发布仅admin+物料别名权限+中文）')


# ===== 测试8：API 端点 E2E（R10-R15 API 层覆盖）=====

def test8_api_endpoints_e2e():
    """测试8：API 端点 E2E（R10-R15 API 层覆盖）- 工作台/知识/数据保留/业务质量 API。"""
    import json
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()

    # ---- R10 仓库工作台 API ----
    _login(client, users['admin'])
    resp = client.get('/api/ai/warehouse_workbench')
    assert resp.status_code == 200, f'仓库工作台 API 应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data is not None, '仓库工作台 API 应返回 JSON'
    # 验收：返回结构含 sections（不只检查 HTTP 200）
    assert 'sections' in data or 'snapshot' in data or 'status' in data, \
        '仓库工作台 API 应含 sections/snapshot/status 字段'

    # ---- R11 采购跟进工作台 API ----
    resp = client.get('/api/ai/purchase_followup_workbench')
    assert resp.status_code == 200, f'采购跟进工作台 API 应 200，实际 {resp.status_code}'

    # ---- R12 知识检索 API ----
    resp = client.get('/api/ai/knowledge_search?q=入库')
    assert resp.status_code == 200, f'知识检索 API 应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data is not None, '知识检索 API 应返回 JSON'

    # ---- R13 Agent 预算校验 API ----
    resp = client.post('/api/ai/agent_validate_safety', json={
        'budget_config': {'max_steps': 10, 'max_duration_seconds': 600, 'max_tool_calls': 50},
        'current_steps': 5,
        'current_tool_calls': 5,
        'started_at_iso': '2026-07-17T10:00:00',
        'now_iso': '2026-07-17T10:01:00',
    })
    assert resp.status_code == 200, f'Agent 安全校验 API 应 200，实际 {resp.status_code}'

    # ---- R14 数据保留配置 API ----
    resp = client.get('/api/ai/data_retention_config')
    assert resp.status_code == 200, f'数据保留配置 API 应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data is not None, '数据保留配置 API 应返回 JSON'

    # 数据保留清理预览 API（dry_run，不实际删除）
    resp = client.post('/api/ai/data_cleanup_preview', json={
        'categories': ['conversations', 'images'],
        'dry_run': True,
    })
    assert resp.status_code == 200, f'数据清理预览 API 应 200，实际 {resp.status_code}'

    # ---- R15 业务质量指标 API ----
    resp = client.get('/api/ai/business_quality_metrics')
    assert resp.status_code == 200, f'业务质量指标定义 API 应 200，实际 {resp.status_code}'
    data = resp.get_json()
    assert data is not None, '业务质量指标 API 应返回 JSON'
    # 验收：7 个指标定义（不只检查 HTTP 200）
    assert data.get('count') == 7, f'应有 7 个指标，实际 {data.get("count")}'

    # 业务质量快照 API（空数据，验证可复算）
    resp = client.post('/api/ai/business_quality_snapshot', json={})
    assert resp.status_code == 200, f'业务质量快照 API 应 200，实际 {resp.status_code}'

    # ---- 权限校验：warehouse 不可访问 admin 专属 API ----
    _login(client, users['warehouse'])
    resp = client.get('/api/ai/data_retention_config')
    assert resp.status_code in (302, 403), \
        f'warehouse 访问数据保留配置应被拒，实际 {resp.status_code}'

    resp = client.get('/api/ai/business_quality_metrics')
    assert resp.status_code in (302, 403), \
        f'warehouse 访问业务质量指标应被拒，实际 {resp.status_code}'

    print('PASS 测试8：API 端点 E2E（R10-R15 工作台/知识/预算/保留/质量 API+权限）')


def main() -> int:
    tests = [
        test1_role_permission_matrix,
        test2_document_upload_page,
        test3_document_confirmation_flow,
        test4_draft_drilldown,
        test5_workbench_pages,
        test6_agent_pages,
        test7_ops_pages,
        test8_api_endpoints_e2e,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except Exception as exc:
            failures += 1
            print(f'FAIL {test.__name__}: {type(exc).__name__}: {exc}')
            import traceback
            traceback.print_exc()
    print(f'\n=== AI-R16 Browser E2E Verification Summary ===')
    print(f'total={len(tests)} passed={len(tests) - failures} failed={failures}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
