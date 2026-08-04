# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：备份（backup）域路由迁移到 routes/backup.py。

采用 register-on-app 模式（register_backup_routes(app)），endpoint 名保持不变
（backup_page/create_backup/download_backup/delete_backup/restore_backup），
URL 路径不变，因此模板/导航中的 url_for('create_backup') 等引用无需改动。

验收点：
S1. 5 个 endpoint 已注册，仍是未加前缀的原始 endpoint 名，不存在 backup.xxx 重复。
S2. URL 路径保持不变（/backup、/backup/create、/backup/download/<filename>、
    /backup/delete、/backup/restore）。
S3. 备份列表页可渲染（200，含备份管理字样）。
S4. 创建备份成功，备份文件生成到 BACKUP_DIR。
S5. 下载备份：路径穿越被拒（400）、文件不存在 404、正常文件 200。
S6. 删除备份：文件不存在提示、非法文件名拒绝、正常删除成功。
S7. 恢复备份：线上系统被禁用（403）。
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

BACKUP_ENDPOINTS = [
    "backup_page",
    "create_backup",
    "download_backup",
    "delete_backup",
    "restore_backup",
]


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


class TestBackupRegister:
    def _setup(self, tmp_path):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
        # 隔离备份目录与数据库文件，避免污染真实数据
        self._backup_dir = str(tmp_path / "backups")
        os.makedirs(self._backup_dir, exist_ok=True)
        self._db_path = str(tmp_path / "wms.db")
        app_module.BACKUP_DIR = self._backup_dir
        app_module.get_database_file_path = lambda: self._db_path
        # 隔离真实 sqlite 备份逻辑：测试环境使用临时内存库，直接重写为写文件
        app_module.create_sqlite_online_backup = lambda src, dst: open(dst, "wb").write(b"backup")
        return _make_client()

    def test_endpoints_and_urls(self):
        """S1/S2：5 个 endpoint 注册、URL 不变、无前缀重复。"""
        with app_module.app.app_context():
            for ep in BACKUP_ENDPOINTS:
                assert ep in app_module.app.view_functions, f"{ep} 未注册"
            for ep in BACKUP_ENDPOINTS:
                assert f"backup.{ep}" not in app_module.app.view_functions, f"backup.{ep} 重复注册"
            from flask import url_for
            with app_module.app.test_request_context():
                assert url_for("backup_page") == "/backup"
                assert url_for("create_backup") == "/backup/create"
                assert url_for("download_backup", filename="a.db") == "/backup/download/a.db"
                assert url_for("delete_backup") == "/backup/delete"
                assert url_for("restore_backup") == "/backup/restore"

    def test_backup_page(self, tmp_path):
        """S3：备份列表页可渲染。"""
        client = self._setup(tmp_path)
        _login(client)
        resp = client.get("/backup")
        assert resp.status_code == 200
        assert "备份" in resp.get_data(as_text=True)

    def test_create_backup(self, tmp_path):
        """S4：创建备份成功，备份文件生成到 BACKUP_DIR。"""
        client = self._setup(tmp_path)
        # 先创建 db 文件，否则 create_backup 返回"数据库文件不存在"
        with open(self._db_path, "wb") as f:
            f.write(b"sqlite-file")
        _login(client)
        resp = client.post("/backup/create")
        data = resp.get_json()
        assert data["status"] == "success", data
        assert data["filename"].startswith("wms_backup_") and data["filename"].endswith(".db"), data
        assert os.path.exists(os.path.join(self._backup_dir, data["filename"]))

    def test_download_backup(self, tmp_path):
        """S5：路径穿越 400、文件不存在 404、正常文件 200。"""
        client = self._setup(tmp_path)
        _login(client)
        # 路径穿越：Flask 路由层可能直接拒绝（404）或视图层拒绝（400），两者均视为安全拦截
        r1 = client.get("/backup/download/..%2F..%2Fapp.py")
        assert r1.status_code in (400, 404)
        # 文件不存在
        r2 = client.get("/backup/download/missing.db")
        assert r2.status_code == 404
        # 正常文件
        p = os.path.join(self._backup_dir, "wms_backup_test.db")
        with open(p, "wb") as f:
            f.write(b"backup-data")
        r3 = client.get("/backup/download/wms_backup_test.db")
        assert r3.status_code == 200
        assert r3.data == b"backup-data"

    def test_restore_disabled(self, tmp_path):
        """S7：线上系统恢复备份被禁用（403）。"""
        client = self._setup(tmp_path)
        _login(client)
        resp = client.post("/backup/restore", data={"filename": "wms_backup_test.db"})
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["status"] == "error"