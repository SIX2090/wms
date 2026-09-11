#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 反馈待修清单（ai_feedback）域 Blueprint。

AI-FEEDBACK-LOOP-001：闭环的"读取端"——把散在 AIFeedback（AI 助手运行反馈）
与 AIDocumentFeedback（单据识别 job 反馈）里的差评聚合成 admin 可消费的
待修清单——按 error_type 分组计数 + 最近差评样例。

- 只读页面，无 LLM 参与，不登记 AI 能力键（不是 AI 能力，是管理报表）。
- 写入端修复见 base.html submitFeedback（AI-FEEDBACK-LOOP-001）。
- A10 架构约束：新路由必须放 app/routes/ 模块，不得进 app.py。
"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, render_template
from flask_login import login_required

from utils import require_role

ai_feedback_bp = Blueprint('ai_feedback', __name__)


@ai_feedback_bp.route('/ai/feedback_review')
@require_role('admin')
@login_required
def ai_feedback_review_page():
    """AI 反馈待修清单：差评按 error_type 聚合 + 最近样例（只读）。"""
    from sqlalchemy import func as sa_func

    from app import (
        AI_FEEDBACK_ERROR_TYPE_LABELS,
        AI_FEEDBACK_RATING_LABELS,
        AIDocumentFeedback,
        AIFeedback,
        db,
    )

    def _aggregate(model, join_user=False):
        q = db.session.query(
            model.rating,
            model.error_type,
            sa_func.count(model.id).label('cnt'),
            sa_func.max(model.created_at).label('last_at'),
        )
        if join_user:
            q = q.join(model.user)
        rows = q.group_by(model.rating, model.error_type).all()
        return [
            {
                'rating': r.rating,
                'rating_label': AI_FEEDBACK_RATING_LABELS.get(r.rating, r.rating),
                'error_type': r.error_type or '',
                'error_label': AI_FEEDBACK_ERROR_TYPE_LABELS.get(r.error_type or '', r.error_type or '未分类'),
                'count': r.cnt,
                'last_at': r.last_at,
            }
            for r in rows
        ]

    # 运行反馈（助手 👍👎）：差评优先展示
    assistant_groups = _aggregate(AIFeedback)
    assistant_bad = [g for g in assistant_groups if g['rating'] != 'helpful']
    assistant_bad.sort(key=lambda g: (-g['count'], g['last_at'] or datetime.min))

    # 单据识别 job 反馈：差评优先展示
    document_groups = _aggregate(AIDocumentFeedback, join_user=True)
    document_bad = [g for g in document_groups if g['rating'] != 'helpful']
    document_bad.sort(key=lambda g: (-g['count'], g['last_at'] or datetime.min))

    # 最近差评样例（各取 8 条，含 note 供定位问题）
    recent_assistant_bad = (
        AIFeedback.query.filter(AIFeedback.rating != 'helpful')
        .order_by(AIFeedback.created_at.desc()).limit(8).all()
    )
    recent_document_bad = (
        AIDocumentFeedback.query.filter(AIDocumentFeedback.rating != 'helpful')
        .order_by(AIDocumentFeedback.created_at.desc()).limit(8).all()
    )

    return render_template(
        'ai_feedback_review.html',
        assistant_groups=assistant_groups,
        assistant_bad=assistant_bad,
        document_groups=document_groups,
        document_bad=document_bad,
        recent_assistant_bad=recent_assistant_bad,
        recent_document_bad=recent_document_bad,
        rating_labels=AI_FEEDBACK_RATING_LABELS,
        error_labels=AI_FEEDBACK_ERROR_TYPE_LABELS,
    )
