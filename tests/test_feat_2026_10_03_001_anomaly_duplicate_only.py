# -*- coding: utf-8 -*-
"""FEAT-2026-10-03-001：异常检测只保留「单据明细重复」（用户拍板 2026-10-03）。

现场（用户截图）：提交入库单时弹「异常检测提醒」——
「物料 电流端子 本次入库量 500.0 偏离近30天均值 250.0 达 100%（动态阈值 50%），
请确认是否正确」。用户明确：异常检测只需要检测单据明细重复的。

变更口径：
  * 移除数量偏离（quantity_deviation）与价格偏离（price_deviation）检测，
    连同专用辅助函数 _calc_smart_threshold 一并删除；
  * 保留重复单据检测（duplicate_order：同日同供应商/客户/部门）；
  * 口径补充（同日用户进一步明确）：「单据明细重复」指一张单据【所有明细】
    的重复（本单全部明细物料 ⊆ 另一张单），而非某一条明细撞车即报——
    同一供应商一天送多批货、物料有交集是正常业务，只有整单重复才是
    疑似重复录入；
  * check_anomalies 路由的 AI 分析 prompt 改用通用键（type/material/msg）——
    原 current/average/deviation 三键仅偏离类异常才有，重复单据直接索引
    会 KeyError（存量隐患，本次口径下必然触发，一并修复）。

断言（函数级 + 真实 HTTP 端到端，非源码字符串匹配）：
  T1 入库：数量偏离近30天均值 100%（截图场景复现）→ 不再报异常
  T2 入库：价格偏离近期均价 100% → 不再报异常
  T3 入库：同日同供应商整单明细全同 → 仍报 duplicate_order（保住要保留的能力）
  T4 入库路由：check_anomalies 偏离场景 has_anomalies=False；
     整单重复场景 anomalies 全为 duplicate_order 且含 existing_order
  T5 出库：数量偏离近30天均值 100% → 不再报异常
  T6 出库：同日同客户整单明细全同 → 仍报 duplicate_order
  T7 出库路由：check_anomalies 偏离场景 has_anomalies=False
  T8 入库：仅部分明细撞车（本单 2 项，另一张单只有其中 1 项）→ 不报
  T9 出库：仅部分明细撞车 → 不报
"""
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"


# --------------------------------------------------------------------------
# 函数级夹具：每条用例从干净 schema 开始，用后重建还库（R7/A12 同族教训，
# 禁止模块级常驻 app_context，避免跨文件顺序依赖假失败）
# --------------------------------------------------------------------------
@pytest.fixture
def wms_env():
    import sys

    if str(APP_DIR) not in sys.path:
        sys.path.insert(0, str(APP_DIR))
    import app as wms

    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    ctx = wms.app.app_context()
    ctx.push()
    try:
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        _seed(wms)
        yield wms
    finally:
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        ctx.pop()


def _seed(wms):
    from app import Material, Supplier, User, Warehouse

    wms.db.session.add_all([
        User(username="feat1003001", password_hash="unused-test-hash",
             role="admin", must_change_password=False),
        Warehouse(code="FEAT1003001-W", name="主仓库", status="active",
                  is_default=True),
        Material(code="FEAT1003001-M", name="电流端子", stock=0),
        Material(code="FEAT1003001-M2", name="入库物料二", stock=0),
        Material(code="FEAT1003001-OM", name="出库物料", stock=0),
        Material(code="FEAT1003001-OM2", name="出库物料二", stock=0),
        Supplier(code="FEAT1003001-S", name="测试供应商"),
    ])
    wms.db.session.commit()


def _login_client(wms):
    user = wms.User.query.filter_by(username="feat1003001").first()
    c = wms.app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return c


def _make_in_order(wms, order_no, order_date, qty, price, material,
                   status="pending", supplier=None):
    from app import InOrder, InOrderItem

    o = InOrder(order_no=order_no, date=order_date, business_type="采购入库",
                status=status, warehouse="主仓库",
                supplier_id=supplier.id if supplier else None)
    wms.db.session.add(o)
    wms.db.session.flush()
    wms.db.session.add(InOrderItem(in_order_id=o.id, material_id=material.id,
                                   quantity=qty, price=price,
                                   amount=qty * price))
    wms.db.session.commit()
    return o


def _make_out_order(wms, order_no, order_date, qty, price, material,
                    status="pending", customer="测试客户"):
    from app import OutOrder, OutOrderItem

    o = OutOrder(order_no=order_no, date=order_date, business_type="其他出库",
                 status=status, warehouse="主仓库", customer=customer)
    wms.db.session.add(o)
    wms.db.session.flush()
    wms.db.session.add(OutOrderItem(out_order_id=o.id, material_id=material.id,
                                    quantity=qty, price=price,
                                    amount=qty * price))
    wms.db.session.commit()
    return o


def _mat(wms, code="FEAT1003001-M"):
    return wms.Material.query.filter_by(code=code).first()


def _sup(wms):
    return wms.Supplier.query.filter_by(code="FEAT1003001-S").first()


# --------------------------------------------------------------------------
# 入库侧
# --------------------------------------------------------------------------
def test_t1_in_quantity_deviation_no_longer_reported(wms_env):
    """截图场景复现：本次入库 500 vs 近30天均值 250（偏离 100%）→ 不报异常。"""
    from app import _check_in_order_anomalies

    yesterday = date.today() - timedelta(days=1)
    _make_in_order(wms_env, "FEAT1003001-H1", yesterday, 250, 100,
                   _mat(wms_env), status="completed", supplier=_sup(wms_env))
    pending = _make_in_order(wms_env, "FEAT1003001-P1", date.today(), 500, 100,
                             _mat(wms_env), supplier=_sup(wms_env))

    assert _check_in_order_anomalies(pending) == []


def test_t2_in_price_deviation_no_longer_reported(wms_env):
    """本次单价 200 vs 近期均价 100（偏离 100%）→ 不报异常。"""
    from app import _check_in_order_anomalies

    yesterday = date.today() - timedelta(days=1)
    _make_in_order(wms_env, "FEAT1003001-H2", yesterday, 250, 100,
                   _mat(wms_env), status="completed", supplier=_sup(wms_env))
    pending = _make_in_order(wms_env, "FEAT1003001-P2", date.today(), 250, 200,
                             _mat(wms_env), supplier=_sup(wms_env))

    assert _check_in_order_anomalies(pending) == []


def test_t3_in_duplicate_still_reported(wms_env):
    """同日同供应商同物料（另一张单今天已入库）→ 仍报 duplicate_order。"""
    from app import _check_in_order_anomalies

    today = date.today()
    _make_in_order(wms_env, "FEAT1003001-H3", today, 100, 100,
                   _mat(wms_env), status="completed", supplier=_sup(wms_env))
    pending = _make_in_order(wms_env, "FEAT1003001-P3", today, 100, 100,
                             _mat(wms_env), supplier=_sup(wms_env))

    anomalies = _check_in_order_anomalies(pending)
    assert [a["type"] for a in anomalies] == ["duplicate_order"]
    assert anomalies[0]["existing_order"] == "FEAT1003001-H3"
    assert "重复" in anomalies[0]["msg"]


def test_t4_in_check_route_deviation_silent_duplicate_warns(wms_env):
    """路由端到端：偏离场景 has_anomalies=False；重复场景仅 duplicate_order。"""
    yesterday = date.today() - timedelta(days=1)
    _make_in_order(wms_env, "FEAT1003001-H4", yesterday, 250, 100,
                   _mat(wms_env), status="completed", supplier=_sup(wms_env))
    pending = _make_in_order(wms_env, "FEAT1003001-P4", date.today(), 500, 100,
                             _mat(wms_env), supplier=_sup(wms_env))

    client = _login_client(wms_env)
    r = client.post(f"/in_order/{pending.id}/check_anomalies")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "success"
    assert body["has_anomalies"] is False
    assert body["anomalies"] == []

    # 追加一张今天同供应商同物料的已入库单 → 重复场景
    _make_in_order(wms_env, "FEAT1003001-H5", date.today(), 100, 100,
                   _mat(wms_env), status="completed", supplier=_sup(wms_env))
    r2 = client.post(f"/in_order/{pending.id}/check_anomalies")
    assert r2.status_code == 200
    body2 = r2.get_json()
    assert body2["has_anomalies"] is True
    assert {a["type"] for a in body2["anomalies"]} == {"duplicate_order"}
    assert body2["anomalies"][0]["existing_order"] == "FEAT1003001-H5"


# --------------------------------------------------------------------------
# 出库侧
# --------------------------------------------------------------------------
def test_t5_out_quantity_deviation_no_longer_reported(wms_env):
    """本次出库 500 vs 近30天均值 250（偏离 100%）→ 不报异常。"""
    from app import _check_out_order_anomalies

    omat = _mat(wms_env, "FEAT1003001-OM")
    yesterday = date.today() - timedelta(days=1)
    _make_out_order(wms_env, "FEAT1003001-OH1", yesterday, 250, 100, omat,
                    status="completed")
    pending = _make_out_order(wms_env, "FEAT1003001-OP1", date.today(), 500,
                              100, omat)

    assert _check_out_order_anomalies(pending) == []


def test_t6_out_duplicate_still_reported(wms_env):
    """同日同客户同物料（另一张单今天已出库）→ 仍报 duplicate_order。"""
    from app import _check_out_order_anomalies

    omat = _mat(wms_env, "FEAT1003001-OM")
    today = date.today()
    _make_out_order(wms_env, "FEAT1003001-OH2", today, 100, 100, omat,
                    status="completed")
    pending = _make_out_order(wms_env, "FEAT1003001-OP2", today, 100, 100, omat)

    anomalies = _check_out_order_anomalies(pending)
    assert [a["type"] for a in anomalies] == ["duplicate_order"]
    assert anomalies[0]["existing_order"] == "FEAT1003001-OH2"
    assert "重复" in anomalies[0]["msg"]


def test_t7_out_check_route_deviation_silent(wms_env):
    """路由端到端：偏离场景 has_anomalies=False。"""
    omat = _mat(wms_env, "FEAT1003001-OM")
    yesterday = date.today() - timedelta(days=1)
    _make_out_order(wms_env, "FEAT1003001-OH3", yesterday, 250, 100, omat,
                    status="completed")
    pending = _make_out_order(wms_env, "FEAT1003001-OP3", date.today(), 500,
                              100, omat)

    client = _login_client(wms_env)
    r = client.post(f"/out_order/{pending.id}/check_anomalies")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "success"
    assert body["has_anomalies"] is False
    assert body["anomalies"] == []


# --------------------------------------------------------------------------
# 口径补充负向用例：仅部分明细撞车 → 不报（整单重复才是重复录入）
# --------------------------------------------------------------------------
def test_t8_in_partial_material_overlap_not_reported(wms_env):
    """本单 2 项明细，另一张同日同供应商单只含其中 1 项 → 不报重复。"""
    from app import _check_in_order_anomalies

    mat1, mat2 = _mat(wms_env), _mat(wms_env, "FEAT1003001-M2")
    today = date.today()
    _make_in_order(wms_env, "FEAT1003001-H8", today, 100, 100, mat1,
                   status="completed", supplier=_sup(wms_env))
    # 本单明细 [M1, M2]，H8 只有 [M1] → 仅部分撞车，非整单重复
    pending = _make_in_order(wms_env, "FEAT1003001-P8", today, 50, 100, mat1,
                             supplier=_sup(wms_env))
    wms_env.db.session.add(wms_env.InOrderItem(
        in_order_id=pending.id, material_id=mat2.id,
        quantity=50, price=100, amount=5000))
    wms_env.db.session.commit()

    assert _check_in_order_anomalies(pending) == []


def test_t9_out_partial_material_overlap_not_reported(wms_env):
    """本单 2 项明细，另一张同日同客户单只含其中 1 项 → 不报重复。"""
    from app import _check_out_order_anomalies

    omat1, omat2 = _mat(wms_env, "FEAT1003001-OM"), _mat(wms_env, "FEAT1003001-OM2")
    today = date.today()
    _make_out_order(wms_env, "FEAT1003001-OH9", today, 100, 100, omat1,
                    status="completed")
    pending = _make_out_order(wms_env, "FEAT1003001-OP9", today, 50, 100, omat1)
    wms_env.db.session.add(wms_env.OutOrderItem(
        out_order_id=pending.id, material_id=omat2.id,
        quantity=50, price=100, amount=5000))
    wms_env.db.session.commit()

    assert _check_out_order_anomalies(pending) == []
