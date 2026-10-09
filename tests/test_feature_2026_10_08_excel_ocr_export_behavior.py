# -*- coding: utf-8 -*-
"""FEATURE-2026-10-08-EXCEL 行为测试：/api/ai/document_ocr_excel

与静态契约测试（test_feature_2026_10_08_excel_ocr_export.py）不同，
本文件做**运行时行为验证**：
1. CSRF：Bearer 请求不再被 CSRF 400 拦截（BUG：App 原生端无 CSRF token）
2. 权限：未登录 401 / 无权限 403 / 合法 Bearer 通过
3. 输入校验：无图 400 / 非图片后缀 400 / 超 10MB 400
4. 正常导出：mock 视觉模型 → xlsx 下载 → openpyxl 回读核对内容
5. 识别失败：模型报错 500 / 无 JSON 422

安全说明：全程 sqlite:///:memory:，不触碰生产库。
"""
from __future__ import annotations

import io

import pytest

from app import app as flask_app, db as _db

from routes.ai_excel import api_document_ocr_excel as _excel_view


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(monkeypatch):
    """测试客户端：内存库 + 系统设置置为已配置视觉模型。"""
    with flask_app.app_context():
        _db.create_all()

    # 绕过「请先启用大模型」前置校验
    monkeypatch.setattr(
        'routes.ai_excel._ai_llm_configured', lambda: True, raising=False)
    # 该函数在视图函数体内延迟 import，需要 patch app 模块上的名字
    import app as app_mod
    monkeypatch.setattr(app_mod, '_ai_llm_configured', lambda: True)
    monkeypatch.setattr(app_mod, '_ai_llm_vision_enabled',
                        lambda *a, **k: True)

    flask_app.config['TESTING'] = True
    with flask_app.test_client() as c:
        yield c


@pytest.fixture()
def vision_ok(monkeypatch):
    """mock 视觉模型：返回标准送货单 JSON。"""
    import app as app_mod

    def fake_vision(prompt, images, **kwargs):
        reply = (
            '这是一张送货单，共3行物料。\n'
            '```json\n'
            '{\n'
            '  "document_type": "in_order",\n'
            '  "supplier": "上海轴承有限公司",\n'
            '  "order_no": "SH-20261008-001",\n'
            '  "date": "2026-10-08",\n'
            '  "items": [\n'
            '    {"code": "0010", "name": "深沟球轴承6204", "spec": "6204-2RS", '
            '"quantity": 100, "price": 10.5, "amount": 1050, "unit": "个"},\n'
            '    {"code": "0020", "name": "油脂", "spec": "SKF LGMT2", '
            '"quantity": 2, "price": 80, "amount": 160, "unit": "kg"},\n'
            '    {"code": "0030", "name": "包装盒", "spec": "100x60x30", '
            '"quantity": 100, "price": 0.5, "amount": 50, "unit": "个"}\n'
            '  ],\n'
            '  "remarks": "含运费"\n'
            '}\n'
            '```'
        )
        extracted = {
            'document_type': 'in_order',
            'supplier': '上海轴承有限公司',
            'order_no': 'SH-20261008-001',
            'date': '2026-10-08',
            'items': [
                {'code': '0010', 'name': '深沟球轴承6204', 'spec': '6204-2RS',
                 'quantity': 100, 'price': 10.5, 'amount': 1050, 'unit': '个'},
                {'code': '0020', 'name': '油脂', 'spec': 'SKF LGMT2',
                 'quantity': 2, 'price': 80, 'amount': 160, 'unit': 'kg'},
                {'code': '0030', 'name': '包装盒', 'spec': '100x60x30',
                 'quantity': 100, 'price': 0.5, 'amount': 50, 'unit': '个'},
            ],
            'remarks': '含运费',
        }
        return reply, extracted, None

    monkeypatch.setattr(app_mod, '_ai_call_llm_vision', fake_vision)


def _make_test_image() -> bytes:
    """600x400 白底黑框图，通过图片质量预处理（1x1 会被拦）。"""
    from PIL import Image, ImageDraw
    import io as _io
    img = Image.new('RGB', (600, 400), 'white')
    d = ImageDraw.Draw(img)
    d.rectangle([20, 20, 580, 380], outline='black', width=3)
    for y in range(60, 360, 40):
        d.line([30, y, 570, y], fill='black', width=1)
    buf = _io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


@pytest.fixture()
def bearer_header():
    """造一个合法 Bearer token（admin 角色，与生产校验逻辑一致）。"""
    import hashlib
    from datetime import datetime, timedelta
    from app import ApiToken, User, hash_access_token
    from werkzeug.security import generate_password_hash

    with flask_app.app_context():
        _db.create_all()
        user = User.query.filter_by(role='admin').first()
        if user is None:
            user = User(username='excel_admin', role='admin',
                        must_change_password=False, status='normal',
                        password_hash=generate_password_hash('Test12345!x'))
            _db.session.add(user)
            _db.session.commit()

        import uuid
        raw = f'test-token-excel-{uuid.uuid4().hex}'
        token = ApiToken(
            user_id=user.id,
            token=hash_access_token(raw),
            expires_at=datetime.now() + timedelta(days=1))
        _db.session.add(token)
        _db.session.commit()
        return {'Authorization': f'Bearer {raw}'}


# ---------------------------------------------------------------------------
# 1. CSRF 行为
# ---------------------------------------------------------------------------

def test_bearer_post_not_blocked_by_csrf(client):
    """BUG 验证：Bearer POST 不带 CSRF token 不应再 400（此前被 CSRF 拦截）。"""
    r = client.post('/api/ai/document_ocr_excel',
                    environ_overrides={'HTTP_AUTHORIZATION': 'Bearer whatever'})
    # 不再是 CSRF 的 400「请求已过期」；应进入权限层 → 401
    assert r.status_code != 400 or '安全令牌' not in (r.get_json(silent=True) or {}).get('msg', ''), \
        'Bearer 请求仍被 CSRF 拦截'
    assert r.status_code == 401
    assert '未登录' in r.get_json(silent=True)['msg']


def test_old_document_ocr_not_blocked_by_csrf(client):
    """旧 /api/ai/document_ocr 也已豁免（App 端识别单据同样依赖）。"""
    r = client.post('/api/ai/document_ocr',
                    environ_overrides={'HTTP_AUTHORIZATION': 'Bearer whatever'})
    assert r.status_code == 401, '应进入权限层 401 而非 CSRF 400'
    data = r.get_json(silent=True) or {}
    assert '安全令牌' not in data.get('msg', ''), '仍被 CSRF 拦截'


# ---------------------------------------------------------------------------
# 2. 权限行为
# ---------------------------------------------------------------------------

def test_no_auth_401(client):
    r = client.post('/api/ai/document_ocr_excel')
    assert r.status_code == 401


def test_invalid_bearer_401(client):
    r = client.post('/api/ai/document_ocr_excel',
                    environ_overrides={'HTTP_AUTHORIZATION': 'Bearer bad-token'})
    assert r.status_code == 401
    assert '无效' in r.get_json(silent=True)['msg']


# ---------------------------------------------------------------------------
# 3. 输入校验（合法 Bearer + 各种坏输入）
# ---------------------------------------------------------------------------

def test_missing_image_400(client, bearer_header):
    r = client.post('/api/ai/document_ocr_excel', headers=bearer_header)
    assert r.status_code == 400
    assert '图片' in r.get_json(silent=True)['msg']


def test_bad_extension_400(client, bearer_header):
    from werkzeug.datastructures import FileStorage
    data = {'image': (io.BytesIO(b'not an image'), 'virus.exe')}
    r = client.post('/api/ai/document_ocr_excel',
                    headers=bearer_header, data=data, content_type='multipart/form-data')
    assert r.status_code == 400
    assert '格式' in r.get_json(silent=True)['msg']


def test_oversize_400(client, bearer_header):
    from werkzeug.datastructures import FileStorage
    big = io.BytesIO(b'\x89PNG' + b'0' * (10 * 1024 * 1024 + 1))
    data = {'image': (big, 'big.png')}
    r = client.post('/api/ai/document_ocr_excel',
                    headers=bearer_header, data=data, content_type='multipart/form-data')
    assert r.status_code == 400
    assert '10MB' in r.get_json(silent=True)['msg']


# ---------------------------------------------------------------------------
# 4. 正常导出：mock 模型 → xlsx 回读
# ---------------------------------------------------------------------------

def test_export_success_returns_valid_xlsx(client, bearer_header, vision_ok):
    from werkzeug.datastructures import FileStorage
    # 1x1 红色 PNG
    png = _make_test_image()
    data = {'image': (io.BytesIO(png), 'delivery_note.png')}
    r = client.post('/api/ai/document_ocr_excel',
                    headers=bearer_header, data=data,
                    content_type='multipart/form-data')

    assert r.status_code == 200, f'导出失败: {r.get_json(silent=True)}'
    assert 'spreadsheetml' in r.headers.get('Content-Type', '')
    assert 'attachment' in r.headers.get('Content-Disposition', '')

    # openpyxl 回读验证
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(r.data))
    ws = wb.active
    values = [[(c.value if c.value is not None else '') for c in row[:7]]
              for row in ws.iter_rows()]

    # 头部
    assert values[0][:2] == ['单据类型', '入库/送货单']
    assert values[1][:2] == ['供应商/客户', '上海轴承有限公司']
    assert values[2][:2] == ['单据编号', 'SH-20261008-001']
    assert values[3][:2] == ['日期', '2026-10-08']
    assert values[4][:2] == ['备注', '含运费']
    # 表头
    assert values[6][:7] == ['物料编码', '物料名称', '规格型号', '数量', '单价', '金额', '单位']
    # 第 1 行明细：前导零编码必须保留为字符串 "0010"
    assert values[7][0] == '0010', f'前导零丢失: {values[7][0]!r}'
    assert values[7][1] == '深沟球轴承6204'
    assert values[7][3] == 100
    assert values[7][4] == 10.5
    assert values[7][5] == 1050
    # 3 行明细
    assert values[9][0] == '0030'
    assert len([v for v in values[7:10]]) == 3


def test_export_no_json_reply_422(client, bearer_header, monkeypatch):
    """模型没返回 JSON 块 → 422，不能返回损坏的 Excel。"""
    import app as app_mod

    def fake_vision(prompt, images, **kwargs):
        return ('我看不清这张图片，无法提取内容。', None, None)

    monkeypatch.setattr(app_mod, '_ai_call_llm_vision', fake_vision)
    png = _make_test_image()
    data = {'image': (io.BytesIO(png), 'blurry.png')}
    r = client.post('/api/ai/document_ocr_excel',
                    headers=bearer_header, data=data,
                    content_type='multipart/form-data')
    assert r.status_code == 422
    assert '未识别' in r.get_json(silent=True)['msg']


def test_export_model_error_500(client, bearer_header, monkeypatch):
    import app as app_mod

    def fake_vision(prompt, images, **kwargs):
        return ('', None, 'timeout after 60s')

    monkeypatch.setattr(app_mod, '_ai_call_llm_vision', fake_vision)
    png = _make_test_image()
    data = {'image': (io.BytesIO(png), 'error.png')}
    r = client.post('/api/ai/document_ocr_excel',
                    headers=bearer_header, data=data,
                    content_type='multipart/form-data')
    assert r.status_code == 500
    assert '视觉模型' in r.get_json(silent=True)['msg']


# ---------------------------------------------------------------------------
# 5. CSRF 豁免不扩大攻击面：豁免视图仍是权限装饰器保护的
# ---------------------------------------------------------------------------

def test_exempt_view_still_guarded(client):
    """被 csrf.exempt 的视图必须仍挂权限装饰器（401 而非 200）。"""
    from flask import current_app
    with flask_app.test_request_context('/api/ai/document_ocr_excel'):
        view = current_app.view_functions['ai_excel.api_document_ocr_excel']
    assert view is _excel_view
    # 无认证访问 → 401（权限层生效）
    r = client.post('/api/ai/document_ocr_excel')
    assert r.status_code == 401
