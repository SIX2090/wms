# -*- coding: utf-8 -*-
"""BUG-2026-08-27-008 回归：手机 APP 下载地址（/mobile/app）无 APK 时返回裸 404。

根因：APK 二进制从未提交进 git 仓库（ANDROID_APK_PATHS 两个候选路径在部署机上
都不存在），CI 只构建 debug 上传 GitHub Actions artifact 不落部署机——用户点
"下载扫码APP"必然 404，即"下载地址不正确"。

修复为三级兜底：
1. 环境变量 WMS_ANDROID_APK_URL（管理员配置外部下载地址）→ 302 跳转；
2. 本地 APK 文件（仓库根 app-release.apk 或构建输出）→ 直接发送；
3. 均无 → 友好说明页（200），含网页版扫码入口与管理员部署指引，不再裸 404。

T1. 无 APK 无配置 → 200 说明页（含网页版入口与部署指引），不再 404。
T2. 配置 WMS_ANDROID_APK_URL → 302 重定向到该地址。
T3. 本地 APK 文件存在 → 200 发送 APK（正确 MIME 与附件文件名）。
T4. 配置与文件同时存在 → 配置优先（302）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
os.environ.pop("WMS_ANDROID_APK_URL", None)

import app as app_module  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _client():
    return app_module.app.test_client()


class TestMobileAppDownloadFallback:

    def test_no_apk_no_config_returns_guide_page(self):
        """T1：无 APK 无配置 → 200 说明页，不再裸 404。"""
        with app_module.app.test_request_context():
            resp = _client().get("/mobile/app")
            assert resp.status_code == 200, \
                f"无 APK 时应返回 200 说明页而非 404，实际 {resp.status_code}"
            body = resp.get_data(as_text=True)
            assert "扫码 APP 安装包暂未部署" in body, "说明页应包含标题"
            assert "网页版" in body, "说明页应包含网页版扫码入口"
            assert "WMS_ANDROID_APK_URL" in body, "说明页应包含管理员配置指引"

    def test_configured_url_redirects(self):
        """T2：配置 WMS_ANDROID_APK_URL → 302 重定向。"""
        with app_module.app.test_request_context():
            os.environ["WMS_ANDROID_APK_URL"] = "http://192.168.1.10/files/wms.apk"
            try:
                resp = _client().get("/mobile/app")
                assert resp.status_code == 302, \
                    f"配置下载地址后应 302 跳转，实际 {resp.status_code}"
                assert resp.headers["Location"] == "http://192.168.1.10/files/wms.apk"
            finally:
                os.environ.pop("WMS_ANDROID_APK_URL", None)

    def test_local_apk_sent_when_present(self, tmp_path, monkeypatch):
        """T3：本地 APK 文件存在 → 200 发送 APK。"""
        fake_apk = tmp_path / "app-release.apk"
        fake_apk.write_bytes(b"PK\x03\x04-fake-apk-content")
        monkeypatch.setattr(app_module, "ANDROID_APK_PATHS", (str(fake_apk),))
        with app_module.app.test_request_context():
            resp = _client().get("/mobile/app")
            assert resp.status_code == 200
            assert resp.mimetype == "application/vnd.android.package-archive", \
                f"MIME 应为 APK 类型，实际 {resp.mimetype}"
            disposition = resp.headers.get("Content-Disposition", "")
            assert "wms-mobile-scan.apk" in disposition, \
                f"附件文件名应为 wms-mobile-scan.apk，实际 {disposition}"
            assert resp.get_data() == b"PK\x03\x04-fake-apk-content"

    def test_config_takes_priority_over_file(self, tmp_path, monkeypatch):
        """T4：配置与文件同时存在 → 配置优先（302）。"""
        fake_apk = tmp_path / "app-release.apk"
        fake_apk.write_bytes(b"PK\x03\x04")
        monkeypatch.setattr(app_module, "ANDROID_APK_PATHS", (str(fake_apk),))
        with app_module.app.test_request_context():
            os.environ["WMS_ANDROID_APK_URL"] = "http://example.com/wms.apk"
            try:
                resp = _client().get("/mobile/app")
                assert resp.status_code == 302, \
                    f"配置应优先于本地文件（302），实际 {resp.status_code}"
            finally:
                os.environ.pop("WMS_ANDROID_APK_URL", None)
