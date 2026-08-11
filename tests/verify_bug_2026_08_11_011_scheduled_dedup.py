# -*- coding: utf-8 -*-
"""
BUG-2026-08-11-011 回归测试：微信分享定时任务去重（防重复发送）。

根因：
- `run_due_wechat_share_jobs` 调 `run_wechat_share_for_today(force=True)`，
  force=True 绕过 `_wechat_share_order` 的"今日已有 pending/sent 记录即跳过"检查，
  同一分钟内的重复触发（scheduler misfire 补跑、服务重启）会对同一入库单
  重复生成图片并重复直推微信，接收人收到多张相同分享图。
- 每次触发都无条件写一条 in_order_daily marker，重复触发会写多条 marker。

修复：
- 定时任务改用 force=False，尊重"今日已分享不重复发"语义；
- 执行前检查今日 scheduled marker，已存在则整个 config 跳过，每日最多执行一次。

验收点：
T1. force=False 时，今日已有 pending/sent 记录的订单被跳过（不重复生成）。
T2. 今日已有 scheduled marker 时，run_due_wechat_share_jobs 不再执行分享。
T3. 无 marker 且时间匹配时正常执行一次并写入恰好 1 条 marker。
T4. 源码静态断言：定时任务调用点使用 force=False。
"""
from __future__ import annotations

import datetime as dt
import os
import sys
import types
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
app_module.app.config["WECHAT_HELPER_TOKEN"] = "test-helper-token-011"


def _seed_config_and_order(**cfg_over):
    from app import InOrder, WechatShareConfig

    config = WechatShareConfig(
        sender_name="", sender_wechat_id="",
        receiver_name="张三", receiver_wechat_id="",
        receiver_search_key="张三", receiver_type="person",
        share_time=cfg_over.pop("share_time", "15:30"),
        share_in_order=True, immediate_on_complete=False,
        enabled=cfg_over.pop("enabled", True),
        auto_send=False, helper_url="http://127.0.0.1:8765/send",
        **cfg_over,
    )
    db.session.add(config)
    order = InOrder(
        order_no="RK20260811002", warehouse="默认仓库",
        date=dt.date.today(), status="completed", purpose="测试",
    )
    db.session.add(order)
    db.session.commit()
    return config, order


class _FixedDatetime(dt.datetime):
    """固定当前时间为 15:30，使 share_time 匹配。"""

    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 11, 15, 30, 0)


class TestScheduledDedup:
    def test_t1_existing_pending_skipped_when_not_force(self, tmp_path, monkeypatch):
        """T1：force=False 时今日已有 pending 记录的订单被跳过。"""
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            config, order = _seed_config_and_order()
            from app import WechatShareLog

            db.session.add(WechatShareLog(
                config_id=config.id, module_key="in_order", order_id=order.id,
                order_no=order.order_no, share_date=dt.date.today(),
                trigger_type="manual", status="pending", message="已生成",
            ))
            db.session.commit()

            monkeypatch.setattr(
                app_module, "_build_order_share_image",
                lambda o, k: (types.SimpleNamespace(getvalue=lambda: b"\x89PNG"), "x.png"),
            )
            monkeypatch.setattr(
                app_module, "_wechat_share_output_dir", lambda: str(tmp_path)
            )
            result = app_module.run_wechat_share_for_today(
                trigger_type="scheduled", force=False, config=config
            )
            assert result["created"] == 0
            assert result["skipped"] == 1
            # 未生成新文件（跳过即不渲染不直推）
            assert list(Path(tmp_path).glob("*.png")) == []

    def test_t2_marker_exists_skips_whole_run(self, monkeypatch):
        """T2：今日已有 scheduled marker 时整个 config 跳过。"""
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            config, _order = _seed_config_and_order()
            from app import WechatShareLog

            db.session.add(WechatShareLog(
                config_id=config.id, module_key="in_order_daily", order_id=0,
                order_no="今日入库单", share_date=dt.date.today(),
                trigger_type="scheduled", status="sent", message="已执行",
            ))
            db.session.commit()

            calls = []
            monkeypatch.setattr(
                app_module, "run_wechat_share_for_today",
                lambda **kw: calls.append(kw) or {"status": "success", "created": 0},
            )
            monkeypatch.setattr(app_module, "datetime", _FixedDatetime)
            try:
                app_module.run_due_wechat_share_jobs()
            finally:
                monkeypatch.setattr(app_module, "datetime", dt.datetime)
            assert calls == [], "已有今日 marker 不得重复执行"
            assert WechatShareLog.query.filter_by(
                module_key="in_order_daily", trigger_type="scheduled"
            ).count() == 1

    def test_t3_first_run_executes_once_with_single_marker(self, tmp_path, monkeypatch):
        """T3：无 marker 且时间匹配时执行一次并写恰好 1 条 marker。"""
        with app_module.app.app_context():
            db.drop_all()
            db.create_all()
            config, _order = _seed_config_and_order()

            monkeypatch.setattr(
                app_module, "run_wechat_share_for_today",
                lambda **kw: {"status": "success", "msg": "已处理", "created": 0},
            )
            monkeypatch.setattr(app_module, "datetime", _FixedDatetime)
            try:
                app_module.run_due_wechat_share_jobs()
                # 模拟同一分钟内的第二次触发（misfire 补跑）
                app_module.run_due_wechat_share_jobs()
            finally:
                monkeypatch.setattr(app_module, "datetime", dt.datetime)

            from app import WechatShareLog
            markers = WechatShareLog.query.filter_by(
                module_key="in_order_daily",
                share_date=dt.date.today(),
                trigger_type="scheduled",
            ).all()
            assert len(markers) == 1, f"同分钟重复触发只应产生 1 条 marker，实际 {len(markers)}"

    def test_t4_source_uses_force_false(self):
        """T4：静态断言定时任务调用点为 force=False。"""
        src = (APP_DIR / "app.py").read_text(encoding="utf-8")
        assert "run_wechat_share_for_today(trigger_type='scheduled', force=False" in src
        assert "run_wechat_share_for_today(trigger_type='scheduled', force=True" not in src
