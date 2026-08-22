# -*- coding: utf-8 -*-
"""内置默认打印模板补 Excel 文件回归（BUG-2026-08-22-002）。

背景：「系统默认入库单模板」「系统默认领料单模板」历史只有
html_template_content、excel_template_path 为空，模板管理页下载/在线编辑
按钮不显示、「下载当前默认打印模板」入口隐藏，用户反馈"内置的模板下载不了"。

修复：启动同步（_ensure_default_print_templates_unconditional /
ensure_default_print_templates）在内置模板缺 Excel 文件时，把
static/templates 示例 xlsx 复制为 uploads/print_templates 内置副本并回填
excel_template_path；用户已换过自己文件的模板不覆盖。

覆盖：
- 缺路径的内置模板被回填，且文件真实存在、可被填充引擎填充
- 幂等：重复执行路径不变
- 用户自定义路径不被覆盖
- 下载路由 200 返回 xlsx
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

import app as m  # noqa: E402

STATIC_ROOT = APP_DIR / "static"


def _make_old_db(db_path: Path) -> Path:
    """构造存量库：内置默认模板存在但 excel_template_path 为空。"""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE in_order_print_template (
                id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL,
                template_type VARCHAR(20), excel_template_path VARCHAR(500),
                html_template_content TEXT, is_default BOOLEAN,
                created_at DATETIME, updated_at DATETIME
            );
            CREATE TABLE out_order_print_template (
                id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL,
                template_type VARCHAR(20), excel_template_path VARCHAR(500),
                html_template_content TEXT, is_default BOOLEAN,
                created_at DATETIME, updated_at DATETIME
            );
            INSERT INTO in_order_print_template
                (name, template_type, excel_template_path, html_template_content, is_default)
                VALUES ('系统默认入库单模板', 'excel', NULL, '<div>old</div>', 1);
            INSERT INTO out_order_print_template
                (name, template_type, excel_template_path, html_template_content, is_default)
                VALUES ('系统默认领料单模板', 'excel', '', '<div>old</div>', 1);
            """
        )
    return db_path


def _get_path(db_path: Path, table: str) -> str:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            f"SELECT excel_template_path FROM {table} WHERE is_default=1"
        ).fetchone()
        return row[0] if row else None


def test_builtin_templates_get_excel_file(tmp_path):
    """入库/领料内置模板均被回填 Excel 路径，文件存在且可被填充引擎使用。"""
    db_path = _make_old_db(tmp_path / "inventory.db")
    m._ensure_default_print_templates_unconditional(db_path=str(db_path))

    for table, expect_name in (
        ('in_order_print_template', 'builtin_in_order_default.xlsx'),
        ('out_order_print_template', 'builtin_out_order_default.xlsx'),
    ):
        path = _get_path(db_path, table)
        assert path and path.endswith(expect_name), f"{table} 未回填: {path}"
        assert path.startswith('/static/uploads/print_templates/')
        from print_fill import template_file_abspath
        abspath = template_file_abspath(path, str(STATIC_ROOT))
        assert os.path.exists(abspath), f"文件不存在: {abspath}"

    # 填充引擎可直接使用回填的模板
    from print_fill import build_filled_print_excel, template_file_abspath
    path = _get_path(db_path, 'in_order_print_template')
    abspath = template_file_abspath(path, str(STATIC_ROOT))

    class _FakeOrder:
        order_no = 'IN26080001'
        total_amount = 1260.0
        remark = '测试备注'
        items = []

    output = build_filled_print_excel(abspath, _FakeOrder(), items=[], date_str='2026-08-22')
    assert output.getbuffer().nbytes > 1000


def test_idempotent_and_user_file_untouched(tmp_path):
    """重复执行路径不变；用户已自定义 excel_template_path 的模板不被覆盖。"""
    db_path = _make_old_db(tmp_path / "inventory.db")
    m._ensure_default_print_templates_unconditional(db_path=str(db_path))
    in_path = _get_path(db_path, 'in_order_print_template')
    m._ensure_default_print_templates_unconditional(db_path=str(db_path))
    assert _get_path(db_path, 'in_order_print_template') == in_path

    # 用户换过自己的模板文件：路径非空即不动
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE in_order_print_template SET excel_template_path=? WHERE is_default=1",
            ('/static/uploads/print_templates/user_custom.xlsx',),
        )
    m._ensure_default_print_templates_unconditional(db_path=str(db_path))
    assert _get_path(db_path, 'in_order_print_template') == '/static/uploads/print_templates/user_custom.xlsx'


def test_download_route_serves_builtin_template(tmp_path):
    """回填后下载路由 200 返回 xlsx（内存库 + ORM 同步路径）。"""
    m.app.config['TESTING'] = True
    with m.app.app_context():
        m.db.drop_all()
        m.db.create_all()
        m.ensure_default_print_templates()
        from werkzeug.security import generate_password_hash
        m.db.session.add(m.User(username='admin', password_hash=generate_password_hash('admin'),
                                role='admin', must_change_password=False))
        m.db.session.commit()
        tpl = m.InOrderPrintTemplate.query.filter_by(name='系统默认入库单模板').first()
        assert tpl is not None
        assert tpl.excel_template_path, 'ORM 同步未回填 excel_template_path'
        tpl_id = tpl.id
    m.app.config['WTF_CSRF_ENABLED'] = False
    client = m.app.test_client()
    client.post('/login', data={'username': 'admin', 'password': 'admin'})
    resp = client.get(f'/in_order_print_template/{tpl_id}/download')
    assert resp.status_code == 200
    assert len(resp.data) > 1000
    assert 'spreadsheetml' in resp.headers.get('Content-Type', '')
