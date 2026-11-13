#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WMS 业务接口压测基线（P2-1，AGENTS.md §三 atomic action）。

为什么要有它
------------
既有性能报告只是 AI 组件微基准（benchmark_performance.py，p95 0.0005–0.03ms），
证明不了业务接口快慢。本脚本对 10 个最高频业务 GET 接口做**低压并发**压测，
输出 ``output/perf_current.json``；``--compare`` 模式与既有基线对比，
回归超阈值打印 ``::warning::``（**阈值告警而非硬门禁**，退出码恒 0，除非压测
装置本身失败）。

用法
----
    python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py                 # 全量压测并写基线 JSON
    python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py --seconds 2     # 缩短每接口压测时长（CI 用）
    python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py --compare scripts/perf_baseline.json
    python scripts/run_ci_isolated.py -- python scripts/perf_baseline.py --compare ... --strict   # 本地自查：回归即 exit 1

设计要点
--------
* **自包含**：新建合成内存库 + 确定性种子数据（1 默认仓 + 300 物料
  + 300 条期初流水），不碰生产 ``c:\\wms`` 数据；waitress 后台线程起真实 HTTP
  服务（不是 test_client），测量值含完整 WSGI/模板/SQL 链路。
* **低压**：并发 2、每接口默认 3 秒（10 接口约 30 秒，符合 P2-1 的"30 秒低压"），
  先 1 次热身再计时。
* **零新依赖**：requests/waitress 均已在 app/requirements.txt；统计用标准库。
* A14 合规：本脚本引用 app，显式 opt-in 生产硬门禁（WMS_ALLOW_INSECURE_COOKIE=1，
  经内核证明的合成内存库 + 自有 HTTP 回环，与 tests/conftest.py 同模式）。
"""
from __future__ import annotations

import argparse
import os
import json
import platform
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"

# ---------------------------------------------------------------------------
# 压测目标：10 个最高频业务 GET 接口（P2-1：库存查询/出入库列表/物料搜索/
# 期初页/盘点 + 首页/物料列表/报表/预警，均为日常操作入口）。
# 选 GET 页面/只读 API：压测只读链路，零写操作（R5 边界天然满足）。
# ---------------------------------------------------------------------------
ENDPOINTS = [
    {"key": "dashboard", "path": "/", "label": "首页工作台"},
    {"key": "stock_query", "path": "/stock_query", "label": "库存查询"},
    {"key": "in_order_list", "path": "/in_order", "label": "入库单列表"},
    {"key": "out_order_list", "path": "/out_order", "label": "出库单列表"},
    {"key": "material_list", "path": "/material", "label": "物料列表"},
    {"key": "material_search", "path": "/material/api/list?keyword=%E8%BD%B4%E6%89%BF",
     "label": "物料搜索 API（keyword=轴承）"},
    {"key": "opening_stock", "path": "/opening_stock", "label": "期初库存页"},
    {"key": "check_list", "path": "/check", "label": "盘点单列表"},
    {"key": "report", "path": "/report", "label": "出入库报表"},
    {"key": "inventory_alert", "path": "/alert", "label": "库存预警"},
]

SEED_MATERIALS = 300          # 确定性种子：物料数（列表/搜索/期初页数据量来源）
DEFAULT_SECONDS = 3.0         # 每接口默认压测秒数（10 接口 ≈ 30s 总预算）
DEFAULT_CONCURRENCY = 2       # 低压并发
WARMUP_REQUESTS = 1           # 每接口热身请求数（JIT/连接池预热，不计入统计）

# compare 模式告警阈值：p95 相对回归 > 50% 且绝对回归 > 50ms 才告警
# （绝对值小的接口避免百分比噪声；绝对值大的接口避免绝对值噪声）。
ALERT_REL_PCT = 50.0
ALERT_ABS_MS = 50.0
MEASUREMENT_PROFILE = "sqlite-memory-waitress-v2"
LEGACY_PROFILE = "sqlite-file-waitress-v1"


# ---------------------------------------------------------------------------
# 纯函数（不依赖 Flask/app，供 tests/test_perf_baseline.py 直接单测，A9）
# ---------------------------------------------------------------------------
def percentile(sorted_values, pct):
    """已升序序列的 pct 分位数（0-100），线性插值；空序列返回 0.0。"""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return float(sorted_values[low] * (1 - frac) + sorted_values[high] * frac)


def summarize(latencies_ms, elapsed_s, errors):
    """把一组延迟样本汇总为基线 JSON 的统计结构。"""
    ordered = sorted(latencies_ms)
    count = len(ordered)
    return {
        "count": count,
        "errors": errors,
        "rps": round(count / elapsed_s, 2) if elapsed_s > 0 else 0.0,
        "mean_ms": round(statistics.fmean(ordered), 2) if ordered else 0.0,
        "p50_ms": round(percentile(ordered, 50), 2),
        "p95_ms": round(percentile(ordered, 95), 2),
        "max_ms": round(max(ordered), 2) if ordered else 0.0,
    }


def regression_alerts(baseline_eps, current_eps, rel_pct=ALERT_REL_PCT, abs_ms=ALERT_ABS_MS):
    """对比基线与本次测量，返回需要告警的接口清单。

    判定：p95 相对回归 > rel_pct 且绝对回归 > abs_ms（双条件降噪）。
    基线缺失的接口跳过；本次新增的接口以 INFO 返回（不算告警）。
    """
    alerts = []
    for key, cur in current_eps.items():
        base = baseline_eps.get(key)
        if not base:
            continue
        base_p95 = float(base.get("p95_ms") or 0)
        cur_p95 = float(cur.get("p95_ms") or 0)
        delta_ms = cur_p95 - base_p95
        delta_pct = (delta_ms / base_p95 * 100.0) if base_p95 > 0 else 0.0
        if delta_ms > abs_ms and delta_pct > rel_pct:
            alerts.append({
                "key": key,
                "label": cur.get("label") or base.get("label") or key,
                "base_p95_ms": base_p95,
                "current_p95_ms": cur_p95,
                "delta_ms": round(delta_ms, 2),
                "delta_pct": round(delta_pct, 1),
            })
    return alerts


def compare_measurement_profiles(baseline, current):
    """Never turn changed storage/transport conditions into a performance PASS."""
    base_profile = baseline.get('measurement_profile', LEGACY_PROFILE)
    current_profile = current.get('measurement_profile', LEGACY_PROFILE)
    if base_profile != current_profile:
        return dict(status='incomparable', baseline_profile=base_profile,
                    current_profile=current_profile, alerts=[])
    baseline_endpoints, current_endpoints = baseline.get('endpoints', {}), current.get('endpoints', {})
    if not set(baseline_endpoints).intersection(current_endpoints):
        return dict(status='incomparable', baseline_profile=base_profile,
                    current_profile=current_profile, reason='no shared measured targets', alerts=[])
    alerts = regression_alerts(baseline_endpoints, current_endpoints)
    return dict(status='regression' if alerts else 'no_regression',
                baseline_profile=base_profile, current_profile=current_profile, alerts=alerts)


# ---------------------------------------------------------------------------
# 压测装置（Flask app + waitress + 种子数据，全部延迟导入 app）
# ---------------------------------------------------------------------------
def _seed_database(app_mod, db):
    """确定性种子：1 默认仓 + 300 物料（含库存阈值，预警页有数据）+ 300 期初流水。"""
    from perf_runtime import require_runtime
    require_runtime()
    os.environ.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')
    from app import Material, MaterialCategory, StockTransaction, Supplier, Unit, User, Warehouse

    with app_mod.app_context():
        if str(db.engine.url) != 'sqlite:///:memory:':
            raise ValueError('安全阻断：性能造数只允许新建内存库')
        if any(row[2] for row in db.session.execute(db.text('PRAGMA database_list'))):
            raise ValueError('安全阻断：性能造数不能附加文件库')
        wh = Warehouse.query.filter_by(is_default=True).first()
        if wh is None:
            wh = Warehouse(code="WH01", name="主仓库", type="raw", status="active", is_default=True)
            db.session.add(wh)
        category = MaterialCategory.query.first() or MaterialCategory(code="C01", name="五金")
        unit = Unit.query.first() or Unit(code="J01", name="件")
        supplier = Supplier.query.first() or Supplier(code="S01", name="默认供应商")
        db.session.add_all([category, unit, supplier])
        db.session.flush()

        admin = User.query.filter_by(username="admin").first()
        if Material.query.count() >= SEED_MATERIALS:
            return wh
        for i in range(1, SEED_MATERIALS + 1):
            stock = float((i * 37) % 500)
            mat = Material(
                code=f"M{i:04d}",
                name=f"轴承物料{i}" if i % 10 == 0 else f"物料{i}",
                spec=f"规格{i % 40}",
                category_id=category.id,
                unit_id=unit.id,
                supplier_id=supplier.id,
                stock=stock,
                price=round((i % 100) * 1.5, 2),
                min_stock=10,
                created_at=__import__("datetime").datetime.now(),
            )
            # 库存阈值列（安全库存=reorder_point，见 Material 命名约定注释）：
            # 每 7 个物料让 stock < reorder_point，预警页有真实数据。
            if hasattr(Material, "reorder_point"):
                mat.reorder_point = 100.0 if i % 7 == 0 else 10.0
            db.session.add(mat)
            db.session.flush()
            db.session.add(StockTransaction(
                material_id=mat.id,
                transaction_type="opening",
                quantity=stock,
                location=wh.name,
                warehouse_id=wh.id,
                reference_type="opening",
                remark="perf baseline seed",
                operator_id=admin.id if admin else None,
            ))
        db.session.commit()
        return wh


def _login_session(server):
    """Authenticate only a server capability created by this owned runtime."""
    from perf_runtime import OwnedPerfHTTP
    if type(server) is not OwnedPerfHTTP:
        raise ValueError('安全阻断：需要本次自有性能服务能力')
    session = server.session()
    response = session.get(server.base_url + '/login', timeout=30, allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError('合成登录页不可用')
    response = session.post(server.base_url + '/login', data={
        'username': server.username, 'password': server.password,
        'usage_consent': '1', 'login_mode': 'admin',
    }, timeout=30, allow_redirects=False)
    if response.status_code not in (200, 302):
        raise RuntimeError('合成账号登录失败')
    if session.get(server.base_url + '/', timeout=30, allow_redirects=False).status_code != 200:
        raise RuntimeError('合成账号登录状态未生效')
    return session


def _measure_endpoint(session, base_url, path, seconds, concurrency):
    """单接口：热身后在 seconds 秒内以 concurrency 个worker 循环发请求，收集延迟。"""
    from perf_runtime import relative_target, require_runtime
    require_runtime()
    from scripts.smoke_isolation import IsolationError, IsolatedSession
    if not isinstance(session, IsolatedSession):
        raise IsolationError('安全阻断：需要自有监听与 nonce 保护的会话')
    relative_target(path)
    if base_url != session.base_url:
        raise ValueError('安全阻断：请求目标与自有监听能力不符')
    errors = 0
    for _ in range(WARMUP_REQUESTS):
        try:
            session.get(base_url + path, timeout=30, allow_redirects=False)
        except IsolationError:
            raise
        except Exception:  # noqa: BLE001 —— 热身失败也继续，正式测量会记 errors
            pass

    latencies = []
    stop_at = time.monotonic() + seconds
    lock = threading.Lock()

    def worker():
        nonlocal errors
        while time.monotonic() < stop_at:
            t0 = time.monotonic()
            try:
                resp = session.get(base_url + path, timeout=30, allow_redirects=False)
                ok = resp.status_code == 200
            except IsolationError:
                raise
            except Exception:  # noqa: BLE001 —— 网络异常计入 errors，不中断压测
                ok = False
            dt = (time.monotonic() - t0) * 1000.0
            with lock:
                if ok:
                    latencies.append(dt)
                else:
                    errors += 1

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker) for _ in range(concurrency)]
        for f in futures:
            f.result()
    elapsed = time.monotonic() - started
    return summarize(latencies, elapsed, errors)


def run_benchmark(seconds, concurrency):
    """Measure real waitress HTTP in the authentic, network-none test container."""
    if not 0 < seconds <= 30 or not 1 <= concurrency <= 4:
        raise ValueError('性能窗口必须为 (0,30] 秒，并发必须为 1 至 4')
    from perf_runtime import initialize_synthetic_app, OwnedPerfHTTP
    w, username, password = initialize_synthetic_app()
    _seed_database(w.app, w.db)
    results = {}
    with OwnedPerfHTTP(w, username, password) as server:
        session = _login_session(server)
        for endpoint in ENDPOINTS:
            stats = _measure_endpoint(session, server.base_url, endpoint['path'], seconds, concurrency)
            if stats['count'] == 0:
                raise RuntimeError(f"性能端点 {endpoint['key']} 没有成功样本，错误数={stats['errors']}")
            stats.update(label=endpoint['label'], path=endpoint['path'])
            results[endpoint['key']] = stats
            print(f"  {endpoint['label']:<24} p95={stats['p95_ms']:>8.2f}ms  "
                  f"mean={stats['mean_ms']:>8.2f}ms n={stats['count']} err={stats['errors']}", flush=True)
    return results


def _git_sha():
    from perf_runtime import source_sha
    return source_sha()


def main():
    ap = argparse.ArgumentParser(description="WMS 业务接口压测基线（P2-1）")
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS,
                    help=f"每接口压测秒数（默认 {DEFAULT_SECONDS}，10 接口约 30s）")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                    help=f"并发 worker 数（默认 {DEFAULT_CONCURRENCY}，低压）")
    ap.add_argument("--output", default=str(ROOT / "output" / "perf_current.json"),
                    help="基线 JSON 输出路径")
    ap.add_argument("--compare", metavar="BASELINE_JSON",
                    help="与既有基线对比：回归超阈值打 ::warning::（告警非门禁）")
    ap.add_argument("--strict", action="store_true",
                    help="对比出现回归时退出码 1（本地自查用；CI 不加此旗标）")
    args = ap.parse_args()

    from perf_runtime import require_runtime, output_path
    require_runtime()
    out_path = output_path(args.output, 'perf_current.json')
    if args.compare and Path(args.compare).absolute() != ROOT / 'scripts' / 'perf_baseline.json':
        raise ValueError('安全阻断：只能对比只读源码内置性能基线')

    print(f"WMS 业务接口压测基线：{len(ENDPOINTS)} 接口 × {args.seconds}s × 并发 {args.concurrency}",
          flush=True)
    current = run_benchmark(args.seconds, args.concurrency)

    payload = {
        "version": 2,
        "measurement_profile": MEASUREMENT_PROFILE,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "git_sha": _git_sha(),
        "platform": f"{platform.system()} {platform.release()}",
        "python": platform.python_version(),
        "config": {"seconds": args.seconds, "concurrency": args.concurrency,
                   "seed_materials": SEED_MATERIALS, "database": "synthetic sqlite memory",
                   "transport": "owned waitress HTTP"},
        "note": "绝对值与机器与存储模式相关，旧文件库基线与本次内存库不能视为同口径；告警阈值见 ALERT_* 常量。",
        "endpoints": current,
    }
    baseline = json.loads(Path(args.compare).read_text(encoding='utf-8')) if args.compare else None
    payload['comparison'] = (compare_measurement_profiles(baseline, payload) if baseline is not None
                             else dict(status='not_requested', alerts=[]))
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n基线已写入: {out_path}", flush=True)

    if not args.compare:
        return 0

    comparison = payload['comparison']
    if comparison['status'] == 'incomparable':
        print('::warning::性能口径不可比：' + str(comparison['baseline_profile']) + ' -> '
              + str(comparison['current_profile']) + '；未作性能通过或回归判定。', flush=True)
        return 2 if args.strict else 0
    alerts = comparison['alerts']
    print(f"\n与基线（{baseline.get('generated_at')} @{baseline.get('git_sha')}）对比：", flush=True)
    for key, cur in current.items():
        base = baseline.get("endpoints", {}).get(key)
        if not base:
            print(f"  [NEW] {cur['label']}: 基线无记录", flush=True)
            continue
        delta = cur["p95_ms"] - base.get("p95_ms", 0)
        sign = "+" if delta >= 0 else ""
        print(f"  {cur['label']:<24} p95 {base.get('p95_ms', 0):.2f} -> "
              f"{cur['p95_ms']:.2f}ms ({sign}{delta:.2f}ms)", flush=True)
    for a in alerts:
        # GitHub Actions 告警注解（阈值告警而非硬门禁，不改变退出码）
        print(f"::warning::perf regression {a['label']}: p95 {a['base_p95_ms']}ms -> "
              f"{a['current_p95_ms']}ms (+{a['delta_ms']}ms, +{a['delta_pct']}%)", flush=True)
    if alerts:
        print(f"\n⚠️  {len(alerts)} 个接口 p95 回归超阈值（>{ALERT_REL_PCT}% 且 "
              f">{ALERT_ABS_MS}ms），请确认是否有性能回退。", flush=True)
        return 1 if args.strict else 0
    print("\n✅ 无超阈值回归。", flush=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
