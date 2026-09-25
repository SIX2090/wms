#!/usr/bin/env python3
"""QA test server startup script."""
import os
import sys

os.chdir('/workspace/app')
os.environ['WMS_SKIP_AUTO_UPDATE'] = '1'
os.environ['FLASK_ENV'] = 'testing'
os.environ['SECRET_KEY'] = 'test-secret-key-for-qa'
os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'admin'

sys.path.insert(0, '/workspace/app')

import config
config.TestingConfig.SQLALCHEMY_DATABASE_URI = 'sqlite:///inventory_qa.db'
config.TestingConfig.WTF_CSRF_ENABLED = False
config.TestingConfig.SESSION_COOKIE_SECURE = False

from app import app, db, initialize_database

app.config['WTF_CSRF_ENABLED'] = False
# Trae 预览浏览器走 HTTPS 代理域名（remote-agent.svc.cluster.local），
# 浏览器把 127.0.0.1 视为第三方站点，默认 SameSite=Lax 会拒绝回传 session cookie，
# 表现为"点登录没反应"。SameSite 必须显式设为字符串 'None' 并启用 Secure，
# 浏览器才会接受跨站 cookie。
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

with app.app_context():
    initialize_database()
    db.session.commit()

from waitress import serve

print('=' * 60, flush=True)
print('WMS QA server starting on http://127.0.0.1:8080', flush=True)
print('Login: admin / admin', flush=True)
print('=' * 60, flush=True)

# 安全修复 BUG-2026-09-25-004：原先绑定 0.0.0.0 且 WTF_CSRF_ENABLED=False、
# bootstrap 密码固定为 admin，任何同网段设备都能直接以 admin/admin 登录并执行
# 无 CSRF 校验的写操作。QA 服务只服务于本机预览，必须收敛到回环地址。
serve(app, host='127.0.0.1', port=8080, threads=4)
