# -*- coding: utf-8 -*-
"""BUG-2026-10-05-004 回归：仓库级告警对"非本仓业务物料"误报。

场景（生产实测，4 仓环境）：
  S1. 专仓物料误报：铜排只入铜排仓（阈值挂物料全局）；选"项目仓库"视图
      不应出现铜排告警（从未进过该仓）。
  S2. 真缺货照常告警：铜排入项目仓 3 件、阈值 5 → 项目仓视图应报 low。
  S3. 误录已冲回：铜排误入项目仓 20 后又反提交/删除（净流水 0、库位行 0）
      → 项目仓视图不应告警。
  S5. 真用光照常告警（v2 漏报回归）：铜排入项目仓 20、正常出库 20（净 0、
      关库位管理无库位行）→ 项目仓视图应告警（004 v1 判据误杀，v2 补
      判据 c"存在 out 正常出库流水"修复）。
  S6. 手机端同口径：S3/S5 场景在 /api/mobile/alert/list 一致。

口径：/alert 仓库视图仅对"本仓业务物料"（库位有行 或 净流水>0 或 有
正常出库流水）判定；全部仓库视图行为不变。手机端同口径。
"""
from __future__ import annotations

import os
import re
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

import app as app_module  # noqa: E402
if not hasattr(app_module, "__path__"):
    app_module.__path__ = [str(APP_DIR)]
from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Warehouse, User, add_stock,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset():
    db.drop_all()
    db.create_all()


def _seed():
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHCU", name="铜排仓", is_default=True, status="active"),
        Warehouse(code="WHPJ", name="项目仓库", status="active"),
        admin,
    ])
    db.session.commit()
    # 库存预警开关默认关闭（关闭时 /alert 直接 302 回物料页），显式打开
    app_module.set_system_setting("inventory_alert_enabled", "1")
    mat = Material(code="M001", name="铜排", spec="T2",
                   category_id=1, unit_id=1, stock=0, price=10, min_stock=5)
    db.session.add(mat)
    db.session.commit()
    return mat, admin


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _wh_id(code):
    return Warehouse.query.filter_by(code=code).first().id


class TestAlertWarehouseScope:

    def test_s1_material_never_in_warehouse_not_alerted(self):
        """S1：铜排只入铜排仓，项目仓库视图不告警。"""
        with app_module.app.app_context():
            _reset()
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="铜排仓")
                assert ok, err
                db.session.commit()

            c = app_module.app.test_client()
            _login(c)
            resp = c.get(f"/alert?warehouse_id={_wh_id('WHPJ')}")
            assert resp.status_code == 200, f"S1 状态码 {resp.status_code}"
            html = resp.get_data(as_text=True)
            # 行级判定：物料编码 M001 不得出现在告警表格（"铜排仓"字样在下拉框属正常 UI）
            assert "M001" not in html, "S1 失败：从未进项目仓的铜排出现在告警页"

    def test_s2_real_shortage_still_alerted(self):
        """S2：铜排真入项目仓 3 件（阈值 5），照常告警。"""
        with app_module.app.app_context():
            _reset()
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 3, transaction_type="in", warehouse="项目仓库")
                assert ok, err
                db.session.commit()

            c = app_module.app.test_client()
            _login(c)
            resp = c.get(f"/alert?warehouse_id={_wh_id('WHPJ')}")
            assert resp.status_code == 200, f"S2 状态码 {resp.status_code}"
            html = resp.get_data(as_text=True)
            assert "M001" in html, "S2 失败：真缺货（3<5）未告警"

    def test_s3_misrecord_then_reverted_not_alerted(self):
        """S3：铜排误入项目仓 20 后冲回 20（净 0、库位行数量 0），不告警。"""
        with app_module.app.app_context():
            _reset()
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="项目仓库")
                assert ok, err
                # 冲回：负 delta 同仓回退（模拟删除明细/反提交的库存路径）
                from app.services.warehouse_stock_service import apply_stock_delta
                ok2, err2 = apply_stock_delta(
                    mat, -20, transaction_type="delete_in_item",
                    reference_type="in_order", reference_id=1,
                    remark="误录删除冲回", warehouse="项目仓库")
                assert ok2, err2
                db.session.commit()

            # 前置事实核验：净流水 0（+20 - 20），流水已按 warehouse_id 归属
            from app import StockTransaction, LocationInventory
            txns = StockTransaction.query.filter_by(
                material_id=mat.id, warehouse_id=_wh_id("WHPJ")).all()
            assert txns, "S3 前置失败：流水未按仓库归属"
            net = sum(t.quantity or 0 for t in txns)
            assert net == 0, f"S3 前置失败：净流水应为 0，实际 {net}"
            # 开库位管理时库位行存在且归 0（本测试默认关库位管理，行可不存在）
            li = LocationInventory.query.filter_by(
                material_id=mat.id, warehouse_id=_wh_id("WHPJ")).all()
            assert all((r.quantity or 0) == 0 for r in li)

            c = app_module.app.test_client()
            _login(c)
            resp = c.get(f"/alert?warehouse_id={_wh_id('WHPJ')}")
            assert resp.status_code == 200, f"S3 状态码 {resp.status_code}"
            html = resp.get_data(as_text=True)
            assert "M001" not in html, "S3 失败：误录已冲回（净 0）仍误报"

    def test_s4_global_view_unchanged(self):
        """S4：全部仓库视图行为不变——铜排在铜排仓 20 件（阈值 5）不告警。"""
        with app_module.app.app_context():
            _reset()
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="铜排仓")
                assert ok, err
                db.session.commit()

            c = app_module.app.test_client()
            _login(c)
            resp = c.get("/alert")
            assert resp.status_code == 200, f"S4 状态码 {resp.status_code}"
            html = resp.get_data(as_text=True)
            assert "M001" not in html, "S4 失败：全局视图 20>5 不应告警"

    def test_s5_real_depletion_still_alerted(self):
        """S5（v2 漏报回归）：真用光——入 20 正常出库 20（净 0、无库位行），应告警。"""
        with app_module.app.app_context():
            _reset()
            mat, admin = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="项目仓库")
                assert ok, err
                # 正常出库（transaction_type='out'）——与误录冲回
                # （delete_in_item）的唯一区分信号
                from app.services.warehouse_stock_service import apply_stock_delta
                ok2, err2 = apply_stock_delta(
                    mat, -20, transaction_type="out",
                    reference_type="out_order", reference_id=1,
                    remark="真实出库", warehouse="项目仓库")
                assert ok2, err2
                db.session.commit()

            # 前置事实核验：净流水 0、存在 out 流水、无库位行（关库位管理）
            from app import StockTransaction, LocationInventory
            txns = StockTransaction.query.filter_by(
                material_id=mat.id, warehouse_id=_wh_id("WHPJ")).all()
            assert txns, "S5 前置失败：流水未按仓库归属"
            net = sum(t.quantity or 0 for t in txns)
            assert net == 0, f"S5 前置失败：净流水应为 0，实际 {net}"
            assert any(t.transaction_type == "out" for t in txns), \
                "S5 前置失败：缺少 out 正常出库流水"
            li = LocationInventory.query.filter_by(
                material_id=mat.id, warehouse_id=_wh_id("WHPJ")).all()
            assert not li, "S5 前置失败：关库位管理不应产生库位行"

            c = app_module.app.test_client()
            _login(c)
            resp = c.get(f"/alert?warehouse_id={_wh_id('WHPJ')}")
            assert resp.status_code == 200, f"S5 状态码 {resp.status_code}"
            html = resp.get_data(as_text=True)
            assert "M001" in html, "S5 失败：真用光（净 0 但有 out 流水）被漏报"

    def test_s6_mobile_api_same_scope(self):
        """S6：手机端同口径——S5 场景告警 / S3 场景不告警。"""
        from app import StockTransaction
        for expected, kind in [(True, "out"), (False, "revert")]:
            with app_module.app.app_context():
                _reset()
                mat, admin = _seed()
                with app_module.app.test_request_context("/"):
                    from flask_login import login_user
                    login_user(admin)
                    ok, err = add_stock(mat, 20, transaction_type="in",
                                        warehouse="项目仓库")
                    assert ok, err
                    from app.services.warehouse_stock_service import apply_stock_delta
                    ttype = "out" if kind == "out" else "delete_in_item"
                    ok2, err2 = apply_stock_delta(
                        mat, -20, transaction_type=ttype,
                        reference_type="out_order" if kind == "out" else "in_order",
                        reference_id=1, remark="S6", warehouse="项目仓库")
                    assert ok2, err2
                    db.session.commit()

                c = app_module.app.test_client()
                _login(c)
                resp = c.get(
                    f"/api/mobile/alert/list?warehouse_id={_wh_id('WHPJ')}")
                assert resp.status_code == 200, f"S6({kind}) 状态码 {resp.status_code}"
                body = resp.get_data(as_text=True)
                if expected:
                    assert "M001" in body, \
                        "S6 失败：真用光在手机端被漏报（out 判据未同步）"
                else:
                    assert "M001" not in body, \
                        "S6 失败：误录已冲回在手机端仍误报"
