"""Initialize WMS DB tables and then run auto_migrate."""
import os
import sys
sys.path.insert(0, '/workspace/app')
sys.path.insert(0, '/workspace')
os.chdir('/workspace')

# Force skip the auto_migrate at import time
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'

# Import the app and db
from app import app, db, initialize_database

# First create all tables
with app.app_context():
    db.create_all()
    print('[INIT] Tables created')
    # Now run the data initialization (admin, defaults)
    initialize_database()
    print('[INIT] initialize_database done')

# Verify tables
with app.app_context():
    tables = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")).fetchall()
    print(f'[INIT] Total tables: {len(tables)}')
    for t in tables:
        print(f'  - {t[0]}')
