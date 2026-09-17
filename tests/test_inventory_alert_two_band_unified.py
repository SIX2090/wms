# -*- coding: utf-8 -*-
"""AI-CI-GREEN-005-F04 回归：库存预警判定统一为「两级」，且手机端与 PC 同口径。

背景：同一套数据，系统里曾经同时存在 5 种预警判定方言（详见台账 §5）。其中危害
最大的是「列表/首页只比 min_stock、/alert 页比两级」——同一个物料在首页看到 3 条、
点进预警页看到 5 条，用户只能怀疑系统坏了。手机端更彻底：整个「低于安全库存」
档（danger）从未出现过。

统一后的口径（唯一真源 `_material_alert_status_values`）：

    safety_stock = max(reorder_point, min_stock)
    low    = stock <= min_stock       → 已破红线（对外：低于最低库存）
    danger = stock <= safety_stock    → 已到预警线（对外：低于安全库存）
    normal = 其余
    disabled = 总开关关闭 / 两个阈值都没设

断言：
  T1. 四档状态机取值正确（low / danger / normal / disabled）。
  T2. SQL 过滤器 `_material_low_stock_filter()` 与状态函数给出**同一批物料**
      （拦截"列表一套、页面另一套"，本次的核心缺陷）。
  T3. 手机端 /api/mobile/alert/list 必须返回 danger 档，且下发 safety_stock/status。
  T4. 手机端 stock/query?stock_filter=low 同样含 danger 档（与告警页同口径）。
  T5. 缺口按安全库存算（补货目标是拉回预警线，不是只拉回红线）。
  T6. 判定用量是**仓库级**库存，不是全局 Material.stock（A11）。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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

import app as app_module  # noqa: E402
from app import Material, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_ctx = app_module.app.app_context()

import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _seed_user(username="al", password="pw"):
    from werkzeug.security import generate_password_hash
    from app import User
    if User.query.filter_by(username=username).first():
        return
    db.session.add(User(username=username,
                        password_hash=generate_password_hash(password),
                        role="warehouse", must_change_password=False))
    db.session.commit()


def _bearer(client, username="al", password="pw"):
    r = client.post("/api/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, *, min_stock=0.0, reorder_point=0.0, global_stock=0.0):
    m = Material(code=code, name=f"物料{code}", stock=global_stock,
                 min_stock=min_stock, reorder_point=reorder_point)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_stock(material, warehouse, qty):
    """按仓库写流水（StockTransaction.location = 仓库名）。"""
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type="in",
        quantity=qty,
        location=warehouse.name,
        warehouse_id=warehouse.id,
        created_at=datetime.now(),
    ))
    db.session.commit()


def _seed_global_scene():
    """全局视角场景：直接给 Material.stock 赋值，覆盖四档。

    T1/T2 用这份数据 —— 判定的分辨力全在 stock 与两个阈值的相对位置上，
    只有把全局库存摆成 5 / 30 / 80 三档，单级与两级口径才会分道扬镳。
    """
    db.drop_all()
    db.create_all()
    _seed_user()
    app_module.set_system_setting("inventory_alert_enabled", "1")
    db.session.commit()
    _seed_material("G-DANGER", min_stock=10, reorder_point=50, global_stock=30)
    _seed_material("G-LOW", min_stock=10, reorder_point=50, global_stock=5)
    _seed_material("G-OK", min_stock=10, reorder_point=50, global_stock=80)
    _seed_material("G-X", global_stock=0)
    return None, None, {}


def _seed_scene():
    """两仓 + 4 个物料，A 仓覆盖 danger / low / normal / 未设阈值四种情形。

    注意：所有物料的**全局** Material.stock 一律设 0 —— 若哪天判定回退到读全局
    库存，T3/T4/T6 会立刻红（每个物料都变成"低于最低库存"）。这是故意埋的探针。
    """
    db.drop_all()
    db.create_all()
    _seed_user()
    wh_a = _seed_warehouse("TBA", "A仓", is_default=True)
    wh_b = _seed_warehouse("TBB", "B仓")
    app_module.set_system_setting("inventory_alert_enabled", "1")
    db.session.commit()

    materials = {
        # min=10, 安全库存=50, A仓 30 → 30>10 但 30<=50 → danger（旧口径完全漏掉）
        "D1": _seed_material("D1", min_stock=10, reorder_point=50),
        # 同上阈值，A仓 5 → low
        "L1": _seed_material("L1", min_stock=10, reorder_point=50),
        # 同上阈值，A仓 80 → normal
        "N1": _seed_material("N1", min_stock=10, reorder_point=50),
        # 两个阈值都没设 → disabled
        "X1": _seed_material("X1"),
    }
    _seed_stock(materials["D1"], wh_a, 30)
    _seed_stock(materials["L1"], wh_a, 5)
    _seed_stock(materials["N1"], wh_a, 80)
    _seed_stock(materials["X1"], wh_a, 999)
    return wh_a, wh_b, materials


def test_t1_four_band_state_machine():
    """T1：low / danger / normal / disabled 四档取值正确。"""
    _seed_global_scene()
    f = app_module._material_alert_status_values

    m = Material.query.filter_by(code="G-DANGER").first()
    assert f(m, stock=5)[3] == "low", "5 <= min_stock(10) 应为 low"
    assert f(m, stock=30)[3] == "danger", (
        "30 > min_stock(10) 但 <= safety_stock(50)，应为 danger；"
        "若这里返回 normal，说明两级判定被改回单级了"
    )
    assert f(m, stock=50)[3] == "danger", "正好等于安全库存仍是 danger（<= 语义）"
    assert f(m, stock=51)[3] == "normal"
    assert f(m, stock=30)[2] == 50, "safety_stock 应为 max(50, 10) = 50"

    # 安全库存取"较大者"：只设 min_stock 时，安全库存 == 最低库存
    m2 = Material.query.filter_by(code="G-LOW").first()
    m2.reorder_point = 0
    db.session.commit()
    assert f(m2, stock=8)[3] == "low"
    assert f(m2, stock=12)[3] == "normal", (
        "只设 min_stock=10 时 12 > 10 应为 normal（安全库存不另起一条线）"
    )

    # 总开关关闭 → disabled
    with app_module.app.app_context():
        app_module.set_system_setting("inventory_alert_enabled", "0")
        db.session.commit()
        assert f(m, stock=1)[3] == "disabled"
        app_module.set_system_setting("inventory_alert_enabled", "1")
        db.session.commit()


def test_t2_sql_filter_matches_status_function():
    """T2：SQL 过滤器与状态函数必须给出同一批物料（拦截列表/页面两套答案）。"""
    _seed_global_scene()
    f = app_module._material_alert_status_values

    all_materials = Material.query.all()
    by_function = {m.code for m in all_materials if f(m)[3] in ("low", "danger")}
    by_filter = {m.code for m in Material.query.filter(
        app_module._material_low_stock_filter()).all()}

    assert by_function == {"G-DANGER", "G-LOW"}, (
        f"两级判定应命中 danger(30<=50) 与 low(5<=10)，实际 {sorted(by_function)}"
    )
    assert by_function == by_filter, (
        f"口径分叉：状态函数判出 {sorted(by_function)}，SQL 过滤器判出 "
        f"{sorted(by_filter)}。两者必须逐条一致（本次缺陷的根因就是这里不一致）"
    )
    # 补集也必须自洽：normal 过滤器的结果与上面互斥且并集为全集
    rest = {m.code for m in Material.query.filter(
        app_module._material_normal_stock_filter()).all()}
    assert rest.isdisjoint(by_filter), "同一物料同时被判为告警与正常"
    assert rest | by_filter == {m.code for m in all_materials}, (
        "告警与正常之外还有第三种状态，说明过滤器不再互补"
    )


def test_t3_mobile_alert_list_returns_danger_band():
    """T3：手机端告警清单必须含 danger 档，并下发 safety_stock / status。"""
    wh_a, _wh_b, _materials = _seed_scene()
    client = app_module.app.test_client()
    h = _bearer(client)

    r = client.get(f"/api/mobile/alert/list?warehouse_id={wh_a.id}&page_size=50",
                   headers=h)
    assert r.status_code == 200, r.get_data(as_text=True)
    items = {it["code"]: it for it in r.get_json()["data"]["items"]}

    assert set(items) == {"D1", "L1"}, (
        f"告警清单应为 danger(D1) + low(L1)，实际 {sorted(items)}；"
        "若只有 L1，说明手机端又退回只比最低库存了"
    )
    assert items["D1"]["status"] == "danger", items["D1"]
    assert items["L1"]["status"] == "low", items["L1"]
    assert items["D1"]["safety_stock"] == 50, "必须下发计算值安全库存"
    assert items["D1"]["stock"] == 30 and items["D1"]["min_stock"] == 10
    # 缺口按安全库存算：50 - 30 = 20（旧实现按 min_stock 算会是 0）
    assert items["D1"]["gap"] == 20, f"缺口应按安全库存算，实际 {items['D1']['gap']}"
    assert items["L1"]["gap"] == 45, items["L1"]


def test_t4_mobile_stock_query_low_filter_is_two_band():
    """T4：查库存 stock_filter=low 与告警页同口径（含 danger 档）。"""
    wh_a, _wh_b, _materials = _seed_scene()
    client = app_module.app.test_client()
    h = _bearer(client)

    r = client.get(
        "/api/mobile/stock/query?warehouse_code=TBA&stock_filter=low&page_size=50",
        headers=h,
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    codes = sorted(it["code"] for it in r.get_json()["data"]["items"])
    assert codes == ["D1", "L1"], (
        f"low 筛选应为两级口径（D1 + L1），实际 {codes}"
    )


def test_t5_gap_targets_safety_stock_not_min_stock():
    """T5：补货缺口以安全库存为目标，不是只补到红线。"""
    wh_a, _wh_b, _materials = _seed_scene()
    client = app_module.app.test_client()
    h = _bearer(client)

    items = client.get(f"/api/mobile/alert/list?warehouse_id={wh_a.id}&page_size=50",
                       headers=h).get_json()["data"]["items"]
    for it in items:
        expected = max(0.0, it["safety_stock"] - it["stock"])
        assert it["gap"] == expected, (
            f"{it['code']} 缺口错误：{it['gap']} != 安全库存{it['safety_stock']}"
            f" - 库存{it['stock']}"
        )
        assert it["gap"] >= 0, "缺口不得为负（补货提示出现负数等于教用户退货）"


def test_t6_judgment_uses_warehouse_level_stock():
    """T6：判定用仓库级库存，不得回退到全局 Material.stock（A11）。

    场景里所有物料的全局 stock 都是 0，而 A 仓库存分别是 30 / 5 / 80 / 999。
    若判定读了全局值，D1 会变成 low、N1 会变成 low —— 全乱。
    """
    wh_a, _wh_b, _materials = _seed_scene()
    client = app_module.app.test_client()
    h = _bearer(client)

    # N1 在 A 仓有 80，全局却是 0：它绝不能出现在告警清单里
    items = client.get(f"/api/mobile/alert/list?warehouse_id={wh_a.id}&page_size=50",
                       headers=h).get_json()["data"]["items"]
    codes = {it["code"] for it in items}
    assert "N1" not in codes, (
        "N1 在 A 仓有 80（高于安全库存 50），却出现在告警清单——"
        "说明判定读了全局 Material.stock(0) 而非仓库级数量"
    )
    assert "X1" not in codes, "X1 未设阈值，不应告警"

    # 首页面板计数同样走仓库级 + 两级口径：应为 2（D1 + L1）
    dash = client.get(f"/api/mobile/dashboard?warehouse_id={wh_a.id}", headers=h)
    assert dash.status_code == 200, dash.get_data(as_text=True)
    assert dash.get_json()["data"]["alert_count"] == 2, (
        "首页告警数应为 2（danger + low），与告警清单同口径"
    )
