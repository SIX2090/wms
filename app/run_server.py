import logging
import os
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


LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"


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


def main():
    _configure_console_logging()

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

    try:
        scheduler = init_notification_scheduler(app, db, Material, User)
        scheduler.add_job(
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
