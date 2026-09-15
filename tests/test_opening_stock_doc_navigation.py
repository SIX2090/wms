# -*- coding: utf-8 -*-
"""ARCH-OS-DOC-01 回归：期初库存单据导航（首/上/下/末）。

用户要求「首 上下末功能要有」——原本期初库存不在 DOCUMENT_NAVIGATION_MODULES
可导航清单内，页面上那 4 个导航键是硬编码 disabled 的永久死按钮（BUG-2026-09-15-005
曾把它们删掉）。多单据化后必须提供真实导航。

覆盖：
  T1 模块已注册，number/date/detail_url 配置正确
  T2 API 返回 first/prev/next/last 正确（3 张单，位于第 2 张）
  T3 无 current_id 时 first/last 可用（前端 prev/next 兜底依赖它）
  T4 title 含仓库名与明细行数（用户靠它识别单据）
  T5 detail_url 末段为数字——与前端 getCurrentRecordId() 正则一致（防路由形态回归）
  T6 按单号/备注搜索能命中
  T7 查询关键字无命中时返回空列表而非报错
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import app as app_module  # noqa: E402
from app import app as flask_app  # noqa: E402
from app import (  # noqa: E402
    DOCUMENT_NAVIGATION_MODULES,
    Material,
    OpeningStock,
    OpeningStockDoc,
    User,
    Warehouse,
    db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# 与 app/static/js/app.js 的 getCurrentRecordId() 完全一致
_JS_CURRENT_RECORD_RE = re.compile(r'/(\d+)(?:/(?:edit|detail))?/?$')


class TestOpeningStockDocNavigation:
    """期初库存单据导航配置与 API。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        for model in (OpeningStock, OpeningStockDoc, Material, Warehouse):
            db.session.query(model).delete()
        db.session.commit()

        self.wh = Warehouse(code='WH001', name='主仓', status='active')
        self.wh2 = Warehouse(code='WH002', name='副仓', status='active')
        self.mat = Material(code='M001', name='螺栓', spec='M8', price=1.0, stock=0)
        db.session.add_all([self.wh, self.wh2, self.mat])
        db.session.commit()

        # 三张单据：A / B / C，B 在中间便于验证 prev/next
        self.docs = []
        for idx, (no, remark, wh) in enumerate((
            ('QS26090001', '第一批建账', self.wh),
            ('QS26090002', '第二批建账', self.wh2),
            ('QS26090003', '第三批建账', self.wh),
        ), start=1):
            doc = OpeningStockDoc(doc_no=no, date=date(2026, 9, idx),
                                  warehouse_id=wh.id, remark=remark, status='active')
            db.session.add(doc)
            db.session.commit()
            db.session.add(OpeningStock(doc_id=doc.id, material_id=self.mat.id,
                                        warehouse_id=wh.id, date=date(2026, 9, idx),
                                        quantity=100 * idx, price=1.0, amount=100.0 * idx))
            db.session.commit()
            self.docs.append(doc)

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        for model in (OpeningStock, OpeningStockDoc, Material, Warehouse, User):
            db.session.query(model).delete()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _login(self):
        """建管理员并登录测试客户端（与项目既有测试同款做法）。"""
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(
                username='admin',
                password_hash=generate_password_hash('admin'),
                role='admin',
                must_change_password=False,
            ))
            db.session.commit()
        self.client.post('/login',
                         data={'username': 'admin', 'password': 'admin'},
                         content_type='application/x-www-form-urlencoded')

    def test_t1_module_registered_with_correct_config(self):
        cfg = DOCUMENT_NAVIGATION_MODULES.get('opening_stock')
        assert cfg is not None, 'opening_stock 未注册到 DOCUMENT_NAVIGATION_MODULES'
        assert cfg['model'] is OpeningStockDoc, '导航单位必须是单据头而非明细行'
        assert cfg['number'] == 'doc_no'
        assert cfg['date'] == 'date'
        assert cfg['detail_url'] == '/opening_stock/{id}'
        assert callable(cfg['title'])
        assert isinstance(cfg['search'], list) and cfg['search']

    def test_t2_first_prev_next_last_around_middle_doc(self):
        """位于中间那张单时，四个导航目标全部正确。"""
        self._login()
        mid = self.docs[1]
        resp = self.client.get(
            f'/api/document_navigation/opening_stock?current_id={mid.id}')
        assert resp.status_code == 200, f'导航 API 返回 {resp.status_code}'
        data = resp.get_json()
        assert data['status'] == 'success'
        assert data['current_id'] == mid.id
        assert data['first_id'] == self.docs[0].id
        assert data['prev_id'] == self.docs[0].id
        assert data['next_id'] == self.docs[2].id
        assert data['last_id'] == self.docs[2].id
        assert data['total'] == 3

    def test_t3_navigation_without_current_id(self):
        """未传 current_id 时仍返回 first/last（前端 prev/next 兜底依赖）。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert data['first_id'] == self.docs[0].id
        assert data['last_id'] == self.docs[2].id
        assert data['current_id'] is None

    def test_t4_title_contains_warehouse_and_line_count(self):
        """标题含仓库名与明细行数，便于用户在导航列表里识别单据。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock')
        rows = resp.get_json()['list']
        assert rows, '导航列表不应为空'
        titles = {r['no']: r['title'] for r in rows}
        assert '主仓' in titles['QS26090001'], f"首单标题应含仓库名：{titles['QS26090001']}"
        assert '副仓' in titles['QS26090002'], f"次单标题应含仓库名：{titles['QS26090002']}"
        for no, title in titles.items():
            assert '行明细' in title, f'{no} 标题应含明细行数：{title}'

    def test_t5_detail_url_tail_is_numeric(self):
        """detail_url 末段必须是纯数字——前端 getCurrentRecordId() 靠它取当前单据。

        这是路由形态的硬约束：一旦把 detail_url 改成 /opening_stock/doc/{id}
        之类的形态，首/上/下/末 会全部失效且没有明显报错。
        """
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock')
        rows = resp.get_json()['list']
        assert rows
        for row in rows:
            assert _JS_CURRENT_RECORD_RE.search(row['url']), (
                f"detail_url 末段非数字，前端取不到单据 id：{row['url']}")
            captured = _JS_CURRENT_RECORD_RE.search(row['url']).group(1)
            assert int(captured) == row['id'], (
                f'detail_url 中的 id 与记录 id 不一致：{row["url"]} vs {row["id"]}')

    def test_t6_search_by_doc_no_and_remark(self):
        """按单号搜索与按备注搜索均能命中。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock?q=QS26090002')
        data = resp.get_json()
        assert [r['no'] for r in data['list']] == ['QS26090002']
        assert data['total'] == 1

        resp = self.client.get('/api/document_navigation/opening_stock?q=第三批')
        data = resp.get_json()
        assert [r['no'] for r in data['list']] == ['QS26090003']

    def test_t7_search_by_warehouse_name(self):
        """按仓库名搜索（用户场景：很多仓库）能命中该仓所有单据。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock?q=主仓')
        data = resp.get_json()
        nos = sorted(r['no'] for r in data['list'])
        assert nos == ['QS26090001', 'QS26090003'], f'主仓应有 2 张单：{nos}'

    def test_t8_no_match_returns_empty_not_error(self):
        """关键字无命中时返回空列表（不报错）。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock?q=不存在的单号xyz')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'
        assert data['list'] == []
        assert data['total'] == 0
        assert data['first_id'] is None
        assert data['last_id'] is None

    def test_t9_status_serialized(self):
        """status 字段正常序列化（供前端 formatDocumentStatus 展示）。"""
        self._login()
        resp = self.client.get('/api/document_navigation/opening_stock')
        rows = resp.get_json()['list']
        for row in rows:
            assert row['status'] == 'active', f"status 应为 active：{row['status']}"
            assert row['date'], 'date 字段不应为空'
