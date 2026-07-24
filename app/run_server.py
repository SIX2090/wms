import atexit
import logging
import os
import signal
import sys
from datetime import datetime

from waitress import serve

from app import (
    Material,
    User,
    app,
    db,
    MaterialCategory,
    Unit,
    Supplier,
    initialize_database,
    run_due_wechat_share_jobs,
)
from notifications import init_notification_scheduler

# AI_TASK: AI-DEPLOY-F01
# AI_TASK: AI-DEPLOY-F01-FIX-01
# 启动前可选从 GitHub main 更新：仅当系统设置 github_auto_update_enabled 开启时执行（默认关闭）。
# 环境变量 WMS_SKIP_AUTO_UPDATE=1 可强制跳过（测试、安装、特殊运维）。
import auto_update  # noqa: E402


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

# Module-level scheduler reference for graceful shutdown.
_scheduler = None


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _log_level():
    level_name = str(app.config.get("LOG_LEVEL", "INFO")).upper()
    return getattr(logging, level_name, logging.INFO)


def _configure_console_logging():
    level = _log_level()
    formatter = logging.Formatter(LOG_FORMAT)

    for logger_name in ("waitress", "waitress.queue", "waitress.error"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.propagate = False
        logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)


def _shutdown_scheduler(signum=None, frame=None):
    """Gracefully shut down the background scheduler on SIGTERM/SIGINT/exit."""
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
                app.logger.info("Notification scheduler shut down (signal=%s)", signum)
        except Exception:
            app.logger.exception("Error shutting down scheduler")
        _scheduler = None


def _github_auto_update_setting_enabled() -> bool:
    """Read system setting github_auto_update_enabled; default False if unavailable."""
    try:
        with app.app_context():
            from app import github_auto_update_enabled
            return bool(github_auto_update_enabled())
    except Exception as e:  # noqa: BLE001
        print(f"[AUTO_UPDATE] 读取自动更新开关失败，默认关闭: {e}", flush=True)
        return False


def _run_startup_auto_update():
    """AI-DEPLOY-F01 / AI-DEPLOY-F01-FIX-01: 可选的启动前 GitHub 更新。

    默认关闭；仅当系统设置「启动时自动从 GitHub 更新」开启时执行。
    任何步骤失败都不阻断 WMS 启动。WMS_SKIP_AUTO_UPDATE=1 可强制跳过。
    """
    if os.environ.get("WMS_SKIP_AUTO_UPDATE", "").strip().lower() in ("1", "true", "yes", "on"):
        print("[AUTO_UPDATE] WMS_SKIP_AUTO_UPDATE=1, 跳过启动前自动更新", flush=True)
        return
    if not _github_auto_update_setting_enabled():
        print(
            "[AUTO_UPDATE] 系统设置「启动时自动从 GitHub 更新」未开启（默认关闭），跳过自动更新",
            flush=True,
        )
        return
    print("=" * 60, flush=True)
    print("WMS 启动前自动更新检查（AI-DEPLOY-F01）", flush=True)
    print("=" * 60, flush=True)
    try:
        auto_update.main()
    except Exception as e:  # noqa: BLE001
        # 自动更新失败不阻断 WMS 启动，用现有代码启动保证可用性
        print(f"[AUTO_UPDATE][警告] 自动更新异常（不阻断启动）: {e}", flush=True)
    print("=" * 60, flush=True)


def main():
    _configure_console_logging()

    # AI-DEPLOY-F01: 启动前自动从 GitHub 更新代码和依赖（失败不阻断启动）
    _run_startup_auto_update()

    host = app.config.get("HOST", "0.0.0.0")
    port = int(app.config.get("PORT", 8080))
    threads = 8

    print("=" * 60, flush=True)
    print("WMS server starting", flush=True)
    print(f"URL: http://127.0.0.1:{port}", flush=True)
    print(f"Bind: http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop", flush=True)
    print("=" * 60, flush=True)

    # Initialize schema and bootstrap admin during explicit server startup only.
    try:
        with app.app_context():
            initialize_database()
            if os.environ.get("WMS_INIT_SAMPLE_DATA") == "1":
                init_test_data()
    except Exception:
        app.logger.exception("Database initialization failed")
        raise

    global _scheduler
    try:
        _scheduler = init_notification_scheduler(app, db, Material, User)
        _scheduler.add_job(
            lambda: run_due_wechat_share_jobs(),
            "interval",
            minutes=1,
            id="wechat_share_due_check",
            replace_existing=True,
            max_instances=1,
        )
        app.logger.info("Notification scheduler started")
    except Exception:
        app.logger.exception("Notification scheduler failed to start")
        raise

    # Register graceful shutdown handlers: SIGTERM (container/service stop),
    # SIGINT (Ctrl+C), and atexit (normal interpreter exit).
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _shutdown_scheduler)
        except (ValueError, OSError):
            # signal.signal can fail when not in the main thread
            pass
    atexit.register(_shutdown_scheduler)

    try:
        app.logger.info("Starting Waitress on %s:%s with %s threads", host, port, threads)
        serve(app, host=host, port=port, threads=threads)
    except Exception:
        app.logger.exception("Server failed to start")
        raise


def init_test_data():
    """初始化测试数据，确保系统有可用的物料数据"""
    # 检查是否已有物料数据
    if Material.query.count() > 0:
        return

    print("[INIT] 创建默认测试物料数据...", flush=True)

    # 创建基础数据
    category = MaterialCategory.query.first()
    if not category:
        category = MaterialCategory(name="默认分类")
        db.session.add(category)

    unit = Unit.query.first()
    if not unit:
        unit = Unit(name="件")
        db.session.add(unit)

    supplier = Supplier.query.first()
    if not supplier:
        supplier = Supplier(name="默认供应商", contact="联系人", phone="13800138000")
        db.session.add(supplier)

    db.session.flush()

    # 创建测试物料
    materials = [
        {"code": "001", "name": "螺丝钉", "spec": "M4x20", "stock": 1000, "price": 0.5},
        {"code": "002", "name": "螺母", "spec": "M4", "stock": 500, "price": 0.3},
        {"code": "003", "name": "垫片", "spec": "Φ10", "stock": 800, "price": 0.2},
        {"code": "1001", "name": "电阻", "spec": "1KΩ", "stock": 2000, "price": 0.1},
        {"code": "1002", "name": "电容", "spec": "100μF", "stock": 1500, "price": 0.15},
        {"code": "A001", "name": "轴承", "spec": "6204", "stock": 100, "price": 25.0},
        {"code": "B001", "name": "密封圈", "spec": "O型", "stock": 300, "price": 2.5},
    ]

    for m in materials:
        if not Material.query.filter_by(code=m["code"]).first():
            mat = Material(
                code=m["code"],
                name=m["name"],
                spec=m["spec"],
                category_id=category.id,
                unit_id=unit.id,
                supplier_id=supplier.id,
                stock=m["stock"],
                price=m["price"],
                min_stock=10,
                created_at=datetime.now(),
            )
            db.session.add(mat)

    db.session.commit()
    print(f"[INIT] 已创建 {len(materials)} 条测试物料数据", flush=True)


if __name__ == "__main__":
    main()
