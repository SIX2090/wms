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

serve(app, host='127.0.0.1', port=8080, threads=4)
