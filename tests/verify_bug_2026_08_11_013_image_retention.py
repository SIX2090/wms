# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-013 回归测试：微信分享图片 30 天保留期自动清理。

根因：
- 分享图片每天生成且永久累积在 output/wechat_share/，无任何清理机制，
  目录无限膨胀；超期图片对应的日志记录仍保留 image_path，
  列表页出现必然 404 的下载链接。

修复：
- 新增 `_wechat_share_cleanup_old_images(retention_days=30)`：仅删除符合
  分享命名规则（YYYYMMDD_HHMMSS_*.png）且 mtime 超过保留期的文件，
  并同步清空对应 WechatShareLog 的 image_path/image_size；
- 新增 `_wechat_share_cleanup_old_images_daily()` 每日守卫，
  挂入 `run_due_wechat_share_jobs`（每分钟 scheduler）每日执行一次。

验收点：
T1. 超过 30 天的分享图片被删除，对应日志 image_path/image_size 清空。
T2. 30 天内的分享图片保留，日志不受影响。
T3. 不符合分享命名规则的文件即使超期也不删除。
T4. 每日守卫同一天重复调用只执行一次清理。
T5. run_due_wechat_share_jobs 源码挂接每日清理调用。
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import time
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
from app import WechatShareLog, db  # noqa: E402

app_module.app.config["TESTING"] = True


def _setup_db():
    db.drop_all()
    db.create_all()


def _make_file(folder, name, age_days):
    path = Path(folder) / name
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))
    return str(path)


def _make_log(image_path):
    log = WechatShareLog(
        config_id=0,
        module_key="in_order",
        order_id=1,
        order_no="RK20260811-0001",
        share_date=dt.date.today(),
        trigger_type="manual",
        status="sent",
        message="ok",
        image_path=image_path,
        image_size=15,
    )
    db.session.add(log)
    db.session.commit()
    return log


class TestImageRetentionCleanup:
    def test_t1_expired_image_deleted_and_log_detached(self, tmp_path, monkeypatch):
        """T1：超期图片删除 + 日志 image_path/image_size 清空。"""
        monkeypatch.setattr(app_module, "_wechat_share_output_dir", lambda: str(tmp_path))
        with app_module.app.app_context():
            _setup_db()
            old_path = _make_file(tmp_path, "20260701_120000_RK20260701-0001.png", age_days=31)
            log = _make_log(old_path)
            deleted = app_module._wechat_share_cleanup_old_images()
            assert deleted == 1
            assert not os.path.exists(old_path)
            db.session.refresh(log)
            assert log.image_path is None
            assert log.image_size is None

    def test_t2_recent_image_kept(self, tmp_path, monkeypatch):
        """T2：30 天内图片保留，日志不动。"""
        monkeypatch.setattr(app_module, "_wechat_share_output_dir", lambda: str(tmp_path))
        with app_module.app.app_context():
            _setup_db()
            new_path = _make_file(tmp_path, "20260810_153000_RK20260810-0001.png", age_days=1)
            log = _make_log(new_path)
            deleted = app_module._wechat_share_cleanup_old_images()
            assert deleted == 0
            assert os.path.exists(new_path)
            db.session.refresh(log)
            assert log.image_path == new_path
            assert log.image_size == 15

    def test_t3_non_share_files_untouched(self, tmp_path, monkeypatch):
        """T3：不符合分享命名规则的文件超期也不删。"""
        monkeypatch.setattr(app_module, "_wechat_share_output_dir", lambda: str(tmp_path))
        with app_module.app.app_context():
            _setup_db()
            foreign_png = _make_file(tmp_path, "random.png", age_days=365)
            foreign_txt = _make_file(tmp_path, "20260701_120000_notes.txt", age_days=365)
            deleted = app_module._wechat_share_cleanup_old_images()
            assert deleted == 0
            assert os.path.exists(foreign_png)
            assert os.path.exists(foreign_txt)

    def test_t4_daily_guard_runs_once_per_day(self, tmp_path, monkeypatch):
        """T4：每日守卫同一天第二次调用直接跳过。"""
        monkeypatch.setattr(app_module, "_wechat_share_output_dir", lambda: str(tmp_path))
        app_module._WECHAT_SHARE_CLEANUP_STATE["last_run_date"] = None
        calls = []
        real_cleanup = app_module._wechat_share_cleanup_old_images

        def _spy():
            calls.append(1)
            return real_cleanup()

        monkeypatch.setattr(app_module, "_wechat_share_cleanup_old_images", _spy)
        try:
            with app_module.app.app_context():
                _setup_db()
                _make_file(tmp_path, "20260701_120000_RK20260701-0001.png", age_days=31)
                first = app_module._wechat_share_cleanup_old_images_daily()
                second = app_module._wechat_share_cleanup_old_images_daily()
        finally:
            monkeypatch.setattr(app_module, "_wechat_share_cleanup_old_images", real_cleanup)
            app_module._WECHAT_SHARE_CLEANUP_STATE["last_run_date"] = None
        assert first == 1
        assert second == 0
        assert len(calls) == 1, f"同一天应只清理一次，实际 {len(calls)} 次"

    def test_t5_scheduler_hooked(self):
        """T5：run_due_wechat_share_jobs 挂接每日清理（静态断言）。"""
        import inspect

        source = inspect.getsource(app_module.run_due_wechat_share_jobs)
        assert "_wechat_share_cleanup_old_images_daily()" in source
