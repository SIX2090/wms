# -*- coding: utf-8 -*-
"""语音建单端点 /api/mobile/voice_out_draft 测试（AA3）。

需求：用户说「领8*25螺丝 1000个」→ 生成领料单草稿 → 人工在出库页核对。

两阶段协议：
  dry_run=true  → 只解析+匹配，返回候选供用户点选（不建单）
  dry_run=false → 用用户确认的物料+数量建草稿

AI 边界（AGENTS.md:20 / R5）：
  - 只建 status='pending' 草稿，**不扣库存**
  - 多命中不得擅自建单
  - 无数量不得猜，要求补充

验收：
- T1 端点已注册且要求认证
- T2 dry_run=true 唯一命中 → preview，不建单
- T3 dry_run=true 多命中 → multiple + matches（含 score/strategy）
- T4 dry_run=true 词根降级 → 仍返回候选（不放弃）
- T5 dry_run=false + 明确物料 → 建 pending 草稿，库存不变
- T6 草稿 business_type='领料单'
- T7 多命中时 dry_run=false 无 material_code → 400
- T8 无数量时 dry_run=false → 400（不猜数量）
- T9 仓库必填：无默认仓库且未传 → 400
- T10 纯导航语（"领料"）→ 400
- T11 空文本 → 400（pydantic）
- T12 建草稿不写 StockTransaction（只读性）
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    ApiToken, Material, MaterialCategory, OutOrder, StockTransaction, Unit,
    User, Warehouse, db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINT = "/api/mobile/voice_out_draft"
_TOKEN = None


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(with_default_warehouse=True):
    global _TOKEN
    from werkzeug.security import generate_password_hash
    with app_module.app.app_context():
        _reset_db()
        # AI-VOICE-OUT-F01：/api/mobile/voice_out_draft 是按能力键
        # voice_out_draft 注册的 AI 草稿能力，端点走 _ai_capability_allowed 校验，
        # 灰度默认 off 会拒掉 warehouse 角色。这里按项目既有做法把灰度开到 all
        # （与 scripts/verify_ai_permission_matrix.py 一致）——
        # "没权限时该拒"由 scripts/verify_ai_permission_matrix.py 单独覆盖。
        app_module.set_system_setting('ai_feature_rollout_mode', 'all')
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            User(username="wh1", password_hash=generate_password_hash("wh1"),
                 role="warehouse", must_change_password=False),
        ])
        if with_default_warehouse:
            db.session.add(Warehouse(code="WHA", name="仓库A",
                                     is_default=True, status="active"))
        db.session.commit()
        rows = [
            ("M001", "内六角螺丝", "8*25"),
            ("M002", "内六角螺丝", "8*30"),
            ("M003", "外六角螺栓", "8*25"),
            ("M005", "轴承", "6204"),
        ]
        for code, name, spec in rows:
            db.session.add(Material(code=code, name=name, spec=spec,
                                    category_id=1, unit_id=1, stock=100, price=2))
        user = User.query.filter_by(username="wh1").first()
        from datetime import datetime, timedelta
        token = ApiToken(user_id=user.id, token="voice-out-test-token",
                         expires_at=datetime.now() + timedelta(days=1),
                         revoked=False)
        db.session.add(token)
        db.session.commit()
        _TOKEN = "voice-out-test-token"


def _client():
    return app_module.app.test_client()


def _post(payload):
    return _client().post(
        ENDPOINT,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {_TOKEN}"},
    )


def _body(resp):
    return json.loads(resp.get_data(as_text=True))


# ── T1 端点注册与鉴权 ───────────────────────────────────────────

def test_t1_endpoint_registered_and_requires_auth():
    rules = [r.rule for r in app_module.app.url_map.iter_rules()]
    assert ENDPOINT in rules, "端点未注册"
    _seed()
    resp = _client().post(ENDPOINT, json={"text": "领8*25螺丝 1000个"})
    assert resp.status_code in (401, 403), "必须要求认证"


# ── T2 dry_run 唯一命中 ─────────────────────────────────────────

def test_t2_dry_run_unique_hit_preview_only():
    _seed()
    resp = _post({"text": "领轴承6204 10个", "dry_run": True})
    assert resp.status_code == 200
    body = _body(resp)
    data = body["data"]
    assert data["stage"] == "preview"
    assert data["match_status"] == "success"
    assert data["matches"][0]["code"] == "M005"
    # 不建单
    with app_module.app.app_context():
        assert OutOrder.query.count() == 0, "dry_run 不得建单"


# ── T3 dry_run 多命中 ───────────────────────────────────────────

def test_t3_dry_run_multiple_returns_candidates():
    _seed()
    resp = _post({"text": "领内六角螺丝 100个", "dry_run": True})
    body = _body(resp)
    data = body["data"]
    assert data["match_status"] == "multiple"
    assert len(data["matches"]) >= 2
    for m in data["matches"]:
        assert "code" in m and "score" in m and "strategy" in m
    # 不得建单
    with app_module.app.app_context():
        assert OutOrder.query.count() == 0


# ── T4 词根降级 ─────────────────────────────────────────────────

def test_t4_root_fallback_still_returns_candidates():
    """8*25螺丝 整体匹配不到 → 必须给候选而非空（不轻易说"没听清"）。

    注意：解析器已把关键词抽成「螺丝」（规格单独放在 spec_hint），
    所以这里通常直接命中 fuzzy_full，不需再走 root_fallback 降级——
    这说明多了一层前置解析，反而少一次降级。断言重点是**结果**：
    永不返回空候选，且规格 8*25 排第一。
    """
    _seed()
    resp = _post({"text": "领8*25螺丝 1000个", "dry_run": True})
    body = _body(resp)
    data = body["data"]
    assert data["match_status"] in ("success", "multiple"), data
    assert data["matches"], "降级后不得返回空候选"
    assert data["spec"] == "8*25"
    # 必须能向用户解释做过哪些尝试
    assert data["strategies_tried"]
    # 规格 8*25 完全匹配的应排第一
    assert data["matches"][0]["spec"] == "8*25"


# ── T5 建草稿 + 库存不变 ────────────────────────────────────────

def test_t5_create_draft_does_not_touch_stock():
    _seed()
    with app_module.app.app_context():
        before = Material.query.filter_by(code="M001").first().stock
        txn_before = StockTransaction.query.count()

    resp = _post({
        "text": "领8*25螺丝 1000个", "dry_run": False,
        "material_code": "M001", "quantity": 1000,
    })
    assert resp.status_code == 200, _body(resp)
    data = _body(resp)["data"]
    assert data["stage"] == "created"
    assert data["order_no"]
    assert data["items"][0]["code"] == "M001"
    assert data["items"][0]["quantity"] == 1000.0

    with app_module.app.app_context():
        order = OutOrder.query.filter_by(order_no=data["order_no"]).first()
        assert order is not None
        assert order.status == "pending", "必须是 pending 草稿"
        # 库存与流水都不得变化（草稿不扣库存）
        after = Material.query.filter_by(code="M001").first().stock
        assert after == before, "草稿不得改库存"
        assert StockTransaction.query.count() == txn_before, "草稿不得写库存流水"


# ── T6 business_type ────────────────────────────────────────────

def test_t6_business_type_is_requisition():
    _seed()
    resp = _post({
        "text": "领8*25螺丝 100个", "dry_run": False,
        "material_code": "M001", "quantity": 100,
    })
    order_no = _body(resp)["data"]["order_no"]
    with app_module.app.app_context():
        order = OutOrder.query.filter_by(order_no=order_no).first()
        assert order.business_type == "领料单"


# ── T7 多命中不擅自建单 ─────────────────────────────────────────

def test_t7_multiple_without_choice_is_rejected():
    _seed()
    resp = _post({"text": "领内六角螺丝 100个", "dry_run": False})
    assert resp.status_code == 400, _body(resp)
    with app_module.app.app_context():
        assert OutOrder.query.count() == 0


# ── T8 无数量不猜 ───────────────────────────────────────────────

def test_t8_missing_quantity_rejected():
    _seed()
    resp = _post({
        "text": "领8*25螺丝", "dry_run": False, "material_code": "M001",
    })
    assert resp.status_code == 400, _body(resp)
    assert "数量" in _body(resp)["msg"]
    with app_module.app.app_context():
        assert OutOrder.query.count() == 0


# ── T9 仓库必填 ─────────────────────────────────────────────────

def test_t9_warehouse_required():
    _seed(with_default_warehouse=False)
    resp = _post({"text": "领8*25螺丝 100个", "dry_run": True})
    assert resp.status_code == 400, _body(resp)
    assert "仓库" in _body(resp)["msg"]


# ── T10 纯导航语 ────────────────────────────────────────────────

def test_t10_navigation_only_rejected():
    _seed()
    resp = _post({"text": "领料", "dry_run": True})
    assert resp.status_code == 400, _body(resp)
    assert "物料" in _body(resp)["msg"]


# ── T11 空文本 ──────────────────────────────────────────────────

def test_t11_empty_text_rejected():
    _seed()
    resp = _post({"text": "", "dry_run": True})
    assert resp.status_code == 400


# ── T12 幂等键 ──────────────────────────────────────────────────

def test_t12_idempotency_key_supported():
    _seed()
    payload = {"text": "领8*25螺丝 100个", "dry_run": False,
               "material_code": "M001", "quantity": 100}
    headers = {"Authorization": f"Bearer {_TOKEN}", "X-Idempotency-Key": "voice-key-1"}
    c = _client()
    r1 = c.post(ENDPOINT, json=payload, headers=headers)
    r2 = c.post(ENDPOINT, json=payload, headers=headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert _body(r1)["data"]["order_no"] == _body(r2)["data"]["order_no"], \
        "同幂等键必须重放同一张草稿，不得重复建单"
    with app_module.app.app_context():
        assert OutOrder.query.count() == 1


# ── T13 能力矩阵真正生效（不只是装饰器）────────────────────────────
#
# AI-VOICE-OUT-F01 / AI_PERMISSION_MATRIX.md「维护要求 1」：语音建单必须是
# **按能力键注册**的 AI 草稿能力，能被权限矩阵 / 灰度统一治理。
#
# 这里专门钉住"能力校验确实在端点里跑"——把灰度关掉（off），
# warehouse 角色必须被 403 拒掉；这正是 @api_role_required('warehouse')
# 单独做不到的（它只看角色，不看 AI 能力治理）。

def test_t13_capability_matrix_really_gates_endpoint():
    _seed()
    # 基线：灰度 all 时 warehouse 可用
    ok = _post({"text": "领轴承6204 10个", "dry_run": True})
    assert ok.status_code == 200, _body(ok)

    # 关掉灰度 → 同一请求必须被能力矩阵拒掉
    with app_module.app.app_context():
        # 必须 commit：set_system_setting 只写 session，不落库时新请求读不到
        app_module.set_system_setting('ai_feature_rollout_mode', 'off')
        db.session.commit()
    denied = _post({"text": "领轴承6204 10个", "dry_run": True})
    assert denied.status_code == 403, \
        f"灰度 off 时 warehouse 角色必须被能力矩阵拒绝，实际 {denied.status_code}"
    assert "voice_out_draft" in _body(denied)["msg"], \
        "拒绝信息必须点名能力键，便于排查"


# ── T14 能力键已在三张治理表登记齐（防漏登记）──────────────────────

def test_t14_capability_registered_everywhere():
    from ai.policies import (AI_CAPABILITY_BUSINESS_ENDPOINTS,
                             AI_CAPABILITY_RISK_LEVELS, AI_CAPABILITY_ROLES)
    from ai.tools.registry import get_ai_tool_spec

    cap = 'voice_out_draft'
    assert cap in AI_CAPABILITY_ROLES, "未登记角色矩阵"
    assert AI_CAPABILITY_ROLES[cap] == frozenset({'warehouse'}), "角色集应为 warehouse"
    assert cap in AI_CAPABILITY_BUSINESS_ENDPOINTS, "未登记业务端点"
    assert cap in AI_CAPABILITY_RISK_LEVELS, "未登记风险级别"
    assert AI_CAPABILITY_RISK_LEVELS[cap] == 'draft', "语音建单必须是草稿级"

    spec = get_ai_tool_spec(cap)
    assert spec is not None, "未登记 AI 工具规范（缺它会让能力校验直接拒绝）"
    assert spec.risk_level == 'draft'
    assert spec.confirmation_required is True, "草稿能力必须要求人工确认"
    assert spec.idempotent is True, "草稿能力必须幂等"
    assert spec.allowed_roles == frozenset({'warehouse'})
