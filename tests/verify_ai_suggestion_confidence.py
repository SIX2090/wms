# -*- coding: utf-8 -*-
"""AI-SUGG-CONF-001（P0-3）回归：规则型建议带可解释置信度。

根因：AGENTS.md R5 要求"AI 低置信度必须回落人工"，但规则型建议
（占比 94.4%）完全没有置信度概念——建议只有结论没有可信度，
用户无法区分"断货铁律"与"30 天小样本趋势猜测"。

修复：_ai_smart_replenishment_report 每行新增
- suggestion_basis：'rule'（本报告为规则引擎，AI-NAMING-TRUTH-001）
- suggestion_confidence：可解释折算，不编造模型概率
  * 库存缺口类（断货/低于安全线）：0.5 + 缺口比例 * 0.45，上限 0.95
  * 趋势/可用天数类：min(0.9, 样本天数/90 * 0.9)，样本越短越不可信
  * 库存充足（简单阈值比较）：0.9
- needs_review：confidence < 0.6（AI_SUGGESTION_CONFIDENCE_REVIEW_THRESHOLD）
前端：needs_review 行 table-warning 标黄 + "待复核"徽章（hover 说明）；
CSV 导出加"置信度/待复核"列。第一版只标黄提示，不自动阻断。
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (Material, MaterialCategory, StockTransaction, Unit, User,  # noqa: E402
                 Warehouse, db)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

THRESHOLD = app_module.AI_SUGGESTION_CONFIDENCE_REVIEW_THRESHOLD


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    """四类物料：断货 / 小库存高消耗（趋势类）/ 健康 / 无消耗低于安全线。"""
    db.session.add(User(username="warehouse", password_hash=generate_password_hash("admin"),
                        role="warehouse", must_change_password=False))
    db.session.add(Warehouse(name="主仓", code="WHA", status="active", is_default=True))
    unit = Unit(code="GE", name="个")
    cat = MaterialCategory(code="WJ", name="五金")
    db.session.add_all([unit, cat])
    db.session.flush()

    out = []
    # CONF-A：断货（stock=0，min_stock=100）+ 在消耗 → 缺口类，confidence 应 >= 0.9
    out.append(Material(code="CONF-A", name="断货件", spec="A", stock=0,
                        min_stock=100, max_stock=500, reorder_point=80,
                        price=1.0, unit_id=unit.id, category_id=cat.id))
    # CONF-B：小库存高消耗 → 趋势/可用天数类，30 天样本 confidence=0.3
    out.append(Material(code="CONF-B", name="趋势件", spec="B", stock=10,
                        min_stock=100, max_stock=500, reorder_point=80,
                        price=1.0, unit_id=unit.id, category_id=cat.id))
    # CONF-C：健康库存 → "库存充足"，简单阈值比较，0.9
    out.append(Material(code="CONF-C", name="健康件", spec="C", stock=900,
                        min_stock=100, max_stock=500, reorder_point=80,
                        price=1.0, unit_id=unit.id, category_id=cat.id))
    # CONF-D：无消耗、低于安全线 → 缺口类（0.5 + 50/100*0.45 = 0.72）
    out.append(Material(code="CONF-D", name="呆滞缺货件", spec="D", stock=50,
                        min_stock=100, max_stock=500, reorder_point=80,
                        price=1.0, unit_id=unit.id, category_id=cat.id))
    db.session.add_all(out)
    db.session.flush()

    # CONF-A/CONF-B：近 15 天出库 300（3×-100），触发断货/趋势分支
    for m in (out[0], out[1]):
        for _ in range(3):
            db.session.add(StockTransaction(
                material_id=m.id, transaction_type="out", quantity=-100,
            ))
    db.session.commit()
    return {m.code: m.id for m in out}


def _report(days=30, coverage_days=30):
    return app_module._ai_smart_replenishment_report(
        days=days, coverage_days=coverage_days, limit=50)


def _rows_by_code(report):
    return {r["code"]: r for r in report["rows"]}


def test_t1_fields_present_on_every_row():
    """T1: 每行都含 suggestion_basis / suggestion_confidence / needs_review，且 basis=rule。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        report = _report()
        assert report["rows"], "种子数据必须产出报告行"
        for row in report["rows"]:
            assert row["suggestion_basis"] == "rule"
            assert 0.0 <= row["suggestion_confidence"] <= 1.0
            assert isinstance(row["needs_review"], bool)
        # 薄适配层（legacy）继承同字段：老页面 /ai/replenishment 同样可用
        legacy = app_module._ai_replenishment_report(days=30, coverage_days=30, limit=50)
        for row in legacy["rows"]:
            assert row["suggestion_basis"] == "rule"
            assert "suggestion_confidence" in row and "needs_review" in row


def test_t2_stockout_confidence_high():
    """T2: stock=0, min_stock=100 → confidence >= 0.9（缺口满格判定最强）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        row = _rows_by_code(_report())["CONF-A"]
        assert row["suggestion_confidence"] >= 0.9
        assert row["needs_review"] is False


def test_t3_short_sample_confidence_low():
    """T3: 样本天数=10 的趋势类建议 → confidence <= 0.1（证明是折算值不是常量）。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        row = _rows_by_code(_report(days=10))["CONF-B"]
        assert row["trend"] == "increasing", "种子必须命中趋势分支"
        assert row["suggestion_confidence"] <= 0.1
        assert row["needs_review"] is True


def test_t4_needs_review_matches_threshold():
    """T4: 全表 needs_review 与 confidence < 0.6 严格一致。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        for days in (10, 30, 90):
            for row in _report(days=days)["rows"]:
                assert row["needs_review"] == (row["suggestion_confidence"] < THRESHOLD), (
                    f"days={days} {row['code']}: confidence={row['suggestion_confidence']} "
                    f"needs_review={row['needs_review']}"
                )


def test_t5_page_marks_needs_review_and_csv_has_confidence():
    """T5: 页面标黄（table-warning + 待复核徽章），CSV 导出含置信度/待复核列。"""
    with app_module.app.app_context():
        _reset_db()
        _seed()
        app_module.set_system_setting("ai_feature_rollout_mode", "all")
        db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": "warehouse", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    resp = client.get("/ai/replenishment_smart?risk=all")
    if resp.status_code == 302:
        # 诊断：区分未登录（/login）与能力门禁拒绝（/，带 flash）
        assert False, f"302 → {resp.headers.get('Location')}"
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "table-warning" in html, "低置信行必须整行标黄"
    assert "待复核" in html, "低置信行必须有待复核徽章"
    assert "该建议依据不足" in html, "徽章 hover 必须说明原因"
    resp = client.get("/ai/replenishment_smart?risk=all&export=csv")
    assert resp.status_code == 200
    csv_text = resp.get_data(as_text="utf-8-sig")
    assert "置信度" in csv_text and "待复核" in csv_text
