# -*- coding: utf-8 -*-
"""C1 导出/大数据量接口性能基线脚本（P0 三项计划 §三）。

背景：审查报告 §四.4——分页改造只做了列表页，导出/搜索/预警仍是
全量内存计算（report.py:439/463、:220/370/392、stock_query.py:218、:134）。
perf_baseline.py（P2-1）只覆盖 10 个只读 GET 列表接口，本脚本补导出侧基线，
为 C2–C5 修复提供"修复前耗时/内存"对照（R8 第 1 条：修复前基线）。

测量目标（登录态，隔离 SQLite 合成内存库，仅限新建合成内存库）：
  E1 GET  /report/stock/print          库存 Excel 导出（Material.query.all() 全量）
  E2 GET  /report/inout/export          出入库 Excel 导出（单据 .all() 聚合）
  E3 GET  /report/supplier/print_excel  供应商报表模板导出（:220 Supplier.query.all()）
  E4 POST /api/query/search             移动端/全局搜索（:218 无分页无 LIMIT）

每档造数：N 物料（每物料独立供应商，最坏 N+1 场景）+ 分类/单位/双仓 +
每物料 1 张已完成入库单（N 张单据、N 行明细）。
记录：耗时（均值/最大，重复 R 次）、tracemalloc 峰值、响应字节数。

用法：
  python scripts/run_ci_isolated.py -- python scripts/perf_export_baseline.py                 # 默认 2000 物料 × 3 轮
  python scripts/run_ci_isolated.py -- python scripts/perf_export_baseline.py --materials 5000 --rounds 3
  python scripts/run_ci_isolated.py -- python scripts/perf_export_baseline.py --out output/perf_export_current.json

A14 合规：本脚本引用 app，显式 opt-in 生产硬门禁（WMS_ALLOW_INSECURE_COOKIE=1，
同 scripts/perf_baseline.py 先例，见 AGENTS.md §六 A14 / R6）。
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import tracemalloc
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
D1 = date(2026, 9, 1)


def seed(w, n_materials: int) -> dict:
    """造数：n 物料（各配独立供应商）+ 分类/单位/双仓 + 每物料 1 张已完成入库单。"""
    from perf_runtime import assert_memory_app
    assert_memory_app(w)
    if not 1 <= n_materials <= 10000:
        raise ValueError('合成物料数必须为 1 至 10000')
    InOrder, InOrderItem, Material = w.InOrder, w.InOrderItem, w.Material
    Supplier, Unit, User, Warehouse, db = w.Supplier, w.Unit, w.User, w.Warehouse, w.db
    with w.app.app_context():
        # 本次内核隔离进程的新内存库，无需 drop_all——
        # guarded_drop_all 也只放行 TESTING+内存库，此处空库直接建表即可。
        db.create_all()
        wh_a = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
        wh_b = Warehouse(code="WHB", name="仓库B", is_default=False, status="active")
        unit = Unit(code="PCS", name="个")
        user = User.query.filter_by(role="admin").order_by(User.id.desc()).first()
        from sqlalchemy import inspect as sa_inspect
        cat_cls = sa_inspect(Material).relationships["category"].mapper.class_
        cat = cat_cls(code="CAT1", name="电气")
        db.session.add_all([wh_a, wh_b, unit, cat])
        db.session.commit()
        wh_a_id = wh_a.id
        unit_id = unit.id
        cat_id = cat.id
        user_id = user.id

        # 供应商分批 flush，避免单次会话对象过多
        BATCH = 500
        for base in range(0, n_materials, BATCH):
            objs = []
            upto = min(base + BATCH, n_materials)
            for i in range(base, upto):
                objs.append(Supplier(code=f"S{i:05d}", name=f"供应商{i}"))
            db.session.add_all(objs)
            db.session.flush()
            sup_ids = [s.id for s in objs]
            for j, i in enumerate(range(base, upto)):
                m = Material(code=f"M{i:05d}", name=f"物料{i}",
                             spec=f"SPEC-{i}", unit_id=unit_id, category_id=cat_id,
                             supplier_id=sup_ids[j], price=1.0 + (i % 90), stock=0.0)
                db.session.add(m)
            db.session.flush()
        # 入库单：每物料 1 张（分批提交，避免大事务）
        for base in range(0, n_materials, BATCH):
            upto = min(base + BATCH, n_materials)
            mats = (Material.query
                    .filter(Material.code >= f"M{base:05d}",
                            Material.code < f"M{upto:05d}").all())
            for k, m in enumerate(mats):
                io = InOrder(order_no=f"IN-{m.code}", date=D1, warehouse="仓库A",
                             status="completed", operator_id=user_id)
                db.session.add(io)
                db.session.flush()
                db.session.add(InOrderItem(
                    in_order_id=io.id, material_id=m.id, quantity=10.0,
                    price=m.price, amount=10.0 * m.price))
            db.session.commit()
    return {"warehouse_id": wh_a_id, "n": n_materials}


def login(w, client, username, password):
    from perf_runtime import assert_memory_app
    assert_memory_app(w)
    if client.application is not w.app:
        raise ValueError('安全阻断：客户端不属于本次合成应用')
    response = client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)
    with client.session_transaction() as session:
        if response.status_code not in (200, 302) or not session.get('_user_id'):
            raise RuntimeError('合成账号登录失败')


def measure(w, client, method, url, rounds: int) -> dict:
    """对单个端点重复测量：耗时 + tracemalloc 峰值 + 响应大小。"""
    from perf_runtime import assert_memory_app, relative_target
    assert_memory_app(w)
    relative_target(url)
    if client.application is not w.app or method not in ('GET', 'POST') or not 1 <= rounds <= 10:
        raise ValueError('安全阻断：导出客户端、方法或轮数无效')
    times, peak_bytes, resp_len, status = [], 0, 0, 0
    for r in range(rounds):
        gc.collect()
        tracemalloc.start()
        t0 = time.perf_counter()
        if method == "GET":
            resp = client.get(url, follow_redirects=False)
        else:
            resp = client.post(url, data={"warehouse": "仓库A", "keyword": "M"}, follow_redirects=False)
        elapsed = time.perf_counter() - t0
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        times.append(elapsed)
        peak_bytes = max(peak_bytes, peak)
        resp_len = len(resp.data) if resp.data else 0
        status = resp.status_code
    return {
        "rounds": rounds,
        "status": status,
        "mean_s": round(sum(times) / len(times), 3),
        "max_s": round(max(times), 3),
        "peak_mem_mb": round(peak_bytes / 1024 / 1024, 1),
        "resp_kb": round(resp_len / 1024, 1),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--materials", type=int, default=2000)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--out", default=str(ROOT / "output" / "perf_export_current.json"))
    args = parser.parse_args()
    from perf_runtime import initialize_synthetic_app, output_path
    if not 1 <= args.materials <= 10000 or not 1 <= args.rounds <= 10:
        parser.error('物料数必须为 1 至 10000，轮数必须为 1 至 10')
    out_path = output_path(args.out, 'perf_export_current.json')
    w, username, password = initialize_synthetic_app()

    print(f"[seed] 造数 {args.materials} 物料（各配独立供应商+1 张已完成入库单）...")
    t0 = time.perf_counter()
    ctx = seed(w, args.materials)
    print(f"[seed] 完成，{time.perf_counter() - t0:.1f}s，仓库A id={ctx['warehouse_id']}")

    client = w.app.test_client()
    login(w, client, username, password)

    wid = ctx["warehouse_id"]
    endpoints = [
        ("E1_stock_print", "GET", f"/report/stock/print?warehouse_id={wid}"),
        ("E2_inout_export", "GET",
         f"/report/inout/export?warehouse_id={wid}&warehouse=%E4%BB%93%E5%BA%93A"
         f"&warehouse_code=WHA&start_date=2026-09-01&end_date=2026-09-30"),
        ("E3_supplier_print_excel", "GET",
         "/report/supplier_purchase_summary/print_excel?warehouse_id=" + str(wid)),
        ("E4_query_search", "POST", "/api/query/search"),
    ]
    results = {"meta": {
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "materials": args.materials,
        "rounds": args.rounds,
        "db": "synthetic sqlite memory",
        "measurement_profile": "sqlite-memory-flask-test-client-export-v2",
    }, "endpoints": {}}
    print(f"\n[measure] 每端点 {args.rounds} 轮：")
    for key, method, url in endpoints:
        label = {"E1_stock_print": "库存 Excel 导出",
                 "E2_inout_export": "出入库 Excel 导出",
                 "E3_supplier_print_excel": "供应商报表模板导出",
                 "E4_query_search": "全局搜索（无 LIMIT）"}[key]
        r = measure(w, client, method, url, args.rounds)
        results["endpoints"][key] = {"label": label, "method": method,
                                      "url": url, **r}
        print(f"  {key:<24} {label:<18} status={r['status']} "
              f"mean={r['mean_s']}s max={r['max_s']}s "
              f"peak_mem={r['peak_mem_mb']}MB resp={r['resp_kb']}KB")

    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n[out] 基线已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
