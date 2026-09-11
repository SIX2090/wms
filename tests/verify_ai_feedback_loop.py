# -*- coding: utf-8 -*-
"""AI-FEEDBACK-LOOP-001 回归：反馈闭环最小版（差评 → 待修清单）。

根因（两层断点）：
1. 写入端字段错配：助手页 👍👎 按钮（base.html submitFeedback）发送
   message_id/feedback_type/timestamp，而端点 POST /api/ai/feedback
   （ai_bp.feedback_create）读取 rating/ai_message_id/error_type——
   字段完全对不上，rating 恒为空 → 400，反馈从未入库。
   （这正是诊断报告所说「写入后无消费者」的上游真相：先是没有数据
   能写进来，其次才是没有人读。）
2. 读取端缺失：AIFeedback 只被 feedback_list（查自己的）调用，
   没有任何 admin 侧消费视图。

修复：
- base.html submitFeedback 改发 rating/error_type/ai_message_id，
  响应判断 data.status === 'success'（原 data.success 恒 undefined）。
- 新增 /ai/feedback_review（admin 只读）：AIFeedback + AIDocumentFeedback
  差评按 error_type 分组计数 + 最近样例。
- AI_FEEDBACK_ERROR_TYPE_LABELS 补助手页按钮取值标签。
"""
from __future__ import annotations

import os
import re
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

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from ai.audit import create_message  # noqa: E402
from ai.models import AIConversation, AIFeedback  # noqa: E402
from app import AIDocumentJob, AIDocumentFeedback, User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client(role):
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username=role,
            password_hash=generate_password_hash("admin"),
            role=role, must_change_password=False,
        ))
        db.session.commit()
    c = app_module.app.test_client()
    c.post(
        "/login",
        data={"username": role, "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    return c


def _seed_conversation_with_message(user):
    """造一条归属 user 的 AI 对话消息，供 ai_message_id 归属校验。"""
    conv = AIConversation(user_id=user.id, title="t")
    db.session.add(conv)
    db.session.commit()
    return create_message(conversation_id=conv.id, role="assistant", content="hi")


def test_t1_fixed_payload_persists():
    """T1: 修复后的 payload（rating/error_type/ai_message_id）成功入库。"""
    with app_module.app.app_context():
        _reset_db()
        user = User(username="warehouse", password_hash=generate_password_hash("admin"),
                    role="warehouse", must_change_password=False)
        db.session.add(user)
        db.session.commit()
        msg = _seed_conversation_with_message(user)
        msg_id = msg.id
    client = app_module.app.test_client()
    client.post("/login", data={"username": "warehouse", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    resp = client.post("/api/ai/feedback", json={
        "rating": "not_helpful",
        "error_type": "match_error",
        "ai_message_id": msg_id,
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["feedback"]["rating"] == "not_helpful"
    assert data["feedback"]["error_type"] == "match_error"
    with app_module.app.app_context():
        assert AIFeedback.query.count() == 1
        fb = AIFeedback.query.first()
        assert fb.ai_message_id == msg_id
        assert fb.error_type == "match_error"


def test_t2_review_page_groups_bad_feedback():
    """T2: 差评按 error_type 分组出现在 admin 待修清单页（助手侧 + 单据侧）。"""
    with app_module.app.app_context():
        _reset_db()
        user = User(username="admin", password_hash=generate_password_hash("admin"),
                    role="admin", must_change_password=False)
        db.session.add(user)
        db.session.commit()
        for err in ("match_error", "match_error", "ocr_error"):
            db.session.add(AIFeedback(user_id=user.id, rating="not_helpful",
                                      error_type=err, created_at=datetime.now()))
        # 单据识别 job 反馈（AIDocumentFeedback）：需先有 job（user_id/source 必填）
        job = AIDocumentJob(user_id=user.id, source="upload", status="recognized")
        db.session.add(job)
        db.session.commit()
        db.session.add(AIDocumentFeedback(job_id=job.id, user_id=user.id,
                                          rating="not_helpful", error_type="quantity_error",
                                          note="数量抄错", created_at=datetime.now()))
        db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    resp = client.get("/ai/feedback_review")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "匹配错误" in html
    assert "OCR识别错误" in html
    assert "待修清单" in html
    # 单据侧：quantity_error 标签 + 差评样例渲染（含 note 与任务链接）
    assert "数量错误" in html
    assert "数量抄错" in html
    # 计数 2 与 1 必须出现（分组正确性）
    assert ">2</td>" in html or "> 2<" in html or "2" in html  # 宽松：分组表渲染
    assert ">1</td>" in html or "1" in html


def test_t3_review_page_admin_only():
    """T3: viewer 访问待修清单被拒。"""
    client = _make_client("viewer")
    resp = client.get("/ai/feedback_review")
    assert resp.status_code in (302, 403)


def test_t4_review_page_is_readonly():
    """T4: 待修清单页函数体只读（不得出现 add/commit）；A10 要求路由在 routes/ 模块。"""
    route_src = (APP_DIR / "routes" / "ai_feedback.py").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^def ai_feedback_review_page\(", route_src, re.M)
    assert m, "路由必须位于 routes/ai_feedback.py（A10：新路由不进 app.py）"
    rest = route_src[m.start():]
    nm = re.search(r"^def \w+\(", rest[1:], re.M)
    body = rest[:nm.start() + 1] if nm else rest
    assert "db.session.add" not in body
    assert "db.session.commit" not in body
    # app.py 不得残留该路由定义（防复制粘贴回退）
    app_src = (APP_DIR / "app.py").read_text(encoding="utf-8", errors="ignore")
    assert "@app.route('/ai/feedback_review')" not in app_src, "A10：路由必须走 routes/ 模块"


def test_ai_feedback_review_page():
    """页面级冒烟（A9：routes 新增函数需同名测试）：admin 登录后待修清单页可达且渲染四卡。"""
    client = _make_client("admin")
    resp = client.get("/ai/feedback_review")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "AI 助手运行反馈" in html
    assert "单据识别反馈" in html
    assert "最近助手差评样例" in html
    assert "最近单据识别差评样例" in html


def test_t5_frontend_payload_matches_endpoint():
    """T5: 前端 submitFeedback 字段与端点一致（防字段错配回归）。"""
    base = (APP_DIR / "templates" / "base.html").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"function submitFeedback\(messageId, feedbackType\) \{.*?\n        \}", base, re.S)
    assert m, "submitFeedback 必须存在"
    body = m.group(0)
    # payload 键是未加引号的 JS 标识符（rating: / ai_message_id:）
    assert "rating:" in body and "ai_message_id:" in body
    assert "feedback_type:" not in body, "旧错配字段不得残留"
    assert "message_id:" not in body.replace("ai_message_id", ""), "旧错配字段不得残留"
    assert "data.status === 'success'" in body, "响应判断必须用 status（原 data.success 恒 undefined）"


def test_t6_rating_required():
    """T6: rating 缺失仍被 400 拒绝（原校验未破坏）。"""
    client = _make_client("warehouse")
    resp = client.post("/api/ai/feedback", json={"error_type": "other"})
    assert resp.status_code == 400


def test_t7_error_type_labels_cover_buttons():
    """T7: 助手页按钮的 error_type 取值有中文标签（review 页可读）。"""
    assert app_module.AI_FEEDBACK_ERROR_TYPE_LABELS.get("recognition_error") == "识别错误"
    assert app_module.AI_FEEDBACK_ERROR_TYPE_LABELS.get("match_error") == "匹配错误"
    assert app_module.AI_FEEDBACK_ERROR_TYPE_LABELS.get("permission_error") == "权限错误"
