#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 子系统模型（19 张 AI 运行/审计/文档/知识/智能体/巡检相关表）。

ARCH-MODELS-01（2026-09-15）自 app/app.py 模型区迁入，类定义逐字保留。
统一平铺导入 ``from db import db``（与 core.py 等域模块一致）。
"""

from db import db
from datetime import datetime

__all__ = [
    'AIAcceptanceDailySnapshot',
    'AIAcceptanceEvidencePackage',
    'AIAgentHumanConfirmation',
    'AIAgentRetryRecord',
    'AIAgentRunLock',
    'AIAgentStep',
    'AIAgentTask',
    'AICleanupLog',
    'AIDocumentAttempt',
    'AIDocumentFeedback',
    'AIDocumentFieldConfirmation',
    'AIDocumentItem',
    'AIDocumentJob',
    'AIDraftIdempotency',
    'AIFieldFeedback',
    'AIKnowledgeVersion',
    'AIManualFallbackTask',
    'AIMaterialAlias',
    'AIPatrolAlert',
    'AIPatrolRule',
    'AIPatrolSchedule',
    'AIRequestIdempotency',
    'AIRollbackEvent',
    'AIRolloutAudit',
    'AIRun',
    'AIToolCall',
]


class AIMaterialAlias(db.Model):
    """Learned external material name/code mapped to a material."""
    __tablename__ = 'ai_material_alias'
    __table_args__ = (
        db.Index('idx_ai_material_alias_material', 'material_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    alias = db.Column(db.String(100), nullable=False)
    alias_key = db.Column(db.String(120), unique=True, nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'), nullable=False)
    source = db.Column(db.String(50))
    use_count = db.Column(db.Integer, default=0)
    # AI_TASK: AI-R07 新增：别名软删除（修复 revoke_alias bug，原 confirmation.py
    # 试图设置 disabled/disabled_reason 但模型缺字段导致 AttributeError）
    disabled = db.Column(db.Boolean, default=False, nullable=False)
    disabled_reason = db.Column(db.String(100), default='')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    material = db.relationship('Material', backref=db.backref('ai_aliases', cascade='all, delete-orphan'))
    creator = db.relationship('User', backref='ai_material_aliases')


class AIRun(db.Model):
    __tablename__ = 'ai_run'
    __table_args__ = (
        db.Index('idx_ai_run_user_started', 'user_id', 'started_at'),
        db.Index('idx_ai_run_status_started', 'status', 'started_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_id = db.Column(db.String(80), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    endpoint = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='running')
    model = db.Column(db.String(100))
    prompt_version = db.Column(db.String(50), default='legacy-v1')
    duration_ms = db.Column(db.Integer)
    error_message = db.Column(db.String(500))
    started_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='ai_runs')


class AIToolCall(db.Model):
    __tablename__ = 'ai_tool_call'
    __table_args__ = (
        db.Index('idx_ai_tool_call_run', 'ai_run_id'),
        db.Index('idx_ai_tool_call_name_created', 'tool_name', 'created_at'),
        # AI_TASK: AI-R17-F01 灰度拒绝审计索引
        db.Index('idx_ai_tool_call_denied', 'permission_allowed', 'created_at'),
        db.Index('idx_ai_tool_call_user_source', 'user_id', 'source', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'), nullable=False)
    tool_name = db.Column(db.String(100), nullable=False)
    capability = db.Column(db.String(100))
    risk_level = db.Column(db.String(20), nullable=False, default='read')
    status = db.Column(db.String(20), nullable=False)
    permission_allowed = db.Column(db.Boolean, nullable=False)
    duration_ms = db.Column(db.Integer, default=0)
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    # AI_TASK: AI-R17-F01 灰度拒绝审计扩展字段（记录用户/角色/原因/来源，便于反查与统计）
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    role = db.Column(db.String(20))
    denied_reason = db.Column(db.String(300))
    source = db.Column(db.String(20))  # api/page/agent/background
    denied_stage = db.Column(db.String(20))  # global/flag/role/allowlist/risk/confirmation

    ai_run = db.relationship('AIRun', backref=db.backref('tool_calls', cascade='all, delete-orphan'))


class AIRollbackEvent(db.Model):
    """AI-R17-F01 回滚事件记录（一键关闭/恢复）。

    记录每次 shutdown/restore 动作的快照前后状态、操作人、时间，用于
    校验"10 分钟内关闭 AI 并恢复配置"和"不修改业务数据或用户密码"。
    """
    __tablename__ = 'ai_rollback_event'
    __table_args__ = (
        db.Index('idx_ai_rollback_event_action_created', 'action', 'created_at'),
    )
    # AI_TASK: AI-R17-F01

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(64), unique=True, nullable=False)
    action = db.Column(db.String(20), nullable=False)  # shutdown/restore
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    operator_role = db.Column(db.String(20), nullable=False)
    previous_snapshot = db.Column(db.Text)  # JSON
    new_snapshot = db.Column(db.Text)  # JSON
    started_at = db.Column(db.DateTime, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIManualFallbackTask(db.Model):
    """AI-R17-F01 人工降级任务（Provider 故障等场景保留证据）。

    Provider 故障/预算耗尽/熔断/取消/低置信度时降级为人工流程，
    保留已上传文件和待确认草稿证据，由人工处理。
    """
    __tablename__ = 'ai_manual_fallback_task'
    __table_args__ = (
        db.Index('idx_ai_fallback_task_status_created', 'status', 'created_at'),
        db.Index('idx_ai_fallback_task_reason', 'reason'),
    )
    # AI_TASK: AI-R17-F01

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(64), unique=True, nullable=False)
    original_run_id = db.Column(db.Integer)
    reason = db.Column(db.String(30), nullable=False)  # provider_fault/budget_exhausted/circuit_breaker/cancelled/low_confidence
    preserved_files = db.Column(db.Text)  # JSON
    preserved_drafts = db.Column(db.Text)  # JSON
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending/handled/rejected
    operator_id = db.Column(db.Integer)
    handled_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIRolloutAudit(db.Model):
    """AI-R17-F01 灰度拒绝审计记录。

    记录每次灰度判定的拒绝事件：用户/角色/能力/原因/阶段/请求来源/时间，
    不保存密钥或完整敏感原文。供上线验收统计与反查。
    """
    __tablename__ = 'ai_rollout_audit'
    __table_args__ = (
        db.Index('idx_ai_rollout_audit_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_rollout_audit_capability_stage', 'capability', 'stage'),
    )
    # AI_TASK: AI-R17-F01

    id = db.Column(db.Integer, primary_key=True)
    audit_id = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer)
    role = db.Column(db.String(20))
    capability = db.Column(db.String(100), nullable=False)
    reason = db.Column(db.String(300), nullable=False)
    stage = db.Column(db.String(20), nullable=False)  # global/flag/role/allowlist/risk/confirmation
    source = db.Column(db.String(20), nullable=False)  # api/page/agent/background
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIAcceptanceDailySnapshot(db.Model):
    """AI-R17-F02 每日验收指标快照。

    持久化每日四项绝对指标计数和七项质量指标聚合，
    以及灰度用户/角色信息，支持连续七天验收证据包构建。
    """
    __tablename__ = 'ai_acceptance_daily_snapshot'
    __table_args__ = (
        db.UniqueConstraint('snapshot_date', name='uix_ai_acceptance_snapshot_date'),
        db.Index('idx_ai_acceptance_snapshot_created', 'created_at'),
    )
    # AI_TASK: AI-R17-F02

    id = db.Column(db.Integer, primary_key=True)
    snapshot_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    absolute_counts = db.Column(db.Text, nullable=False)  # JSON: 4 项绝对指标
    quality_metrics = db.Column(db.Text, nullable=False)  # JSON: 7 项质量指标
    rollout_user_count = db.Column(db.Integer, default=0)
    rollout_role_count = db.Column(db.Integer, default=0)
    rollout_roles = db.Column(db.Text)  # JSON: 角色列表
    window_hours = db.Column(db.Integer, default=24)
    filter_applied = db.Column(db.Text)  # JSON: 筛选条件追溯
    generated_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIAcceptanceEvidencePackage(db.Model):
    """AI-R17-F02 七天验收证据包。

    聚合连续七天的每日快照、样本清单、回滚记录和 go/no-go 结论。
    """
    __tablename__ = 'ai_acceptance_evidence_package'
    __table_args__ = (
        db.Index('idx_ai_evidence_package_dates', 'start_date', 'end_date'),
        db.Index('idx_ai_evidence_package_decision', 'go_no_go_decision'),
    )
    # AI_TASK: AI-R17-F02

    id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.String(64), unique=True, nullable=False)
    start_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    end_date = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    daily_snapshot_dates = db.Column(db.Text, nullable=False)  # JSON: 日期列表
    seven_day_summary = db.Column(db.Text, nullable=False)  # JSON: 七天汇总
    rollout_role_matrix = db.Column(db.Text)  # JSON: 角色矩阵
    failure_samples = db.Column(db.Text)  # JSON: 失败样本
    fallback_samples = db.Column(db.Text)  # JSON: 降级样本
    duplicate_samples = db.Column(db.Text)  # JSON: 重复样本
    correction_samples = db.Column(db.Text)  # JSON: 人工修正样本
    rollback_events = db.Column(db.Text)  # JSON: 回滚记录
    go_no_go_decision = db.Column(db.String(10), nullable=False, default='pending')
    decision_reason = db.Column(db.Text)
    decided_by = db.Column(db.Integer)
    decided_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIRequestIdempotency(db.Model):
    __tablename__ = 'ai_request_idempotency'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'request_id', name='uix_ai_request_user_request'),
        db.Index('idx_ai_request_status_updated', 'status', 'updated_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    request_id = db.Column(db.String(80), nullable=False)
    request_hash = db.Column(db.String(64), nullable=False)
    endpoint = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='processing')
    response_status = db.Column(db.Integer)
    response_content_type = db.Column(db.String(120))
    response_body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='ai_idempotent_requests')
    ai_run = db.relationship('AIRun', backref=db.backref('idempotent_request', uselist=False))


class AIDraftIdempotency(db.Model):
    """AI 草稿统一幂等与审计闭环记录 (AI-R01)。

    确保重复上传、重复点击、网络重试、Provider 重试或并发请求均不能创建重复草稿，
    并关联 AIRun、AIToolCall、确认令牌、文档任务和业务草稿，支持完整反查。
    """
    __tablename__ = 'ai_draft_idempotency'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'capability', 'idempotency_key', name='uix_ai_draft_user_cap_key'),
        db.Index('idx_ai_draft_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_draft_status', 'status'),
        db.Index('idx_ai_draft_lookup', 'draft_type', 'draft_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    ai_tool_call_id = db.Column(db.Integer, db.ForeignKey('ai_tool_call.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    capability = db.Column(db.String(60), nullable=False)
    idempotency_key = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(30), nullable=False, default='text')
    source_hash = db.Column(db.String(64))
    business_key = db.Column(db.Text)
    confirmation_token = db.Column(db.String(64))
    document_job_id = db.Column(db.Integer)
    draft_type = db.Column(db.String(40))
    draft_id = db.Column(db.Integer)
    draft_no = db.Column(db.String(60))
    status = db.Column(db.String(20), nullable=False, default='processing')
    error_message = db.Column(db.String(500))
    request_snapshot = db.Column(db.Text)
    response_snapshot = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    user = db.relationship('User', backref='ai_draft_idempotency_records')
    ai_run = db.relationship('AIRun', backref=db.backref('draft_idempotency_records', cascade='all, delete-orphan'))
    ai_tool_call = db.relationship('AIToolCall', backref=db.backref('draft_idempotency_records'))


class AIFieldFeedback(db.Model):
    """AI 字段级反馈记录 (AI-R09)。

    记录 OCR 提取字段被用户修正的反馈：字段名/原值/新值/修正原因/是否采纳/
    模型/提示词/Schema 版本/来源/行号。用于按来源与版本聚合准确率和修正率，
    定位质量下降的字段和版本。
    敏感原文经 mask_sensitive_value 脱敏后存储，不保存不必要的敏感原文。
    """
    __tablename__ = 'ai_field_feedback'
    __table_args__ = (
        db.Index('idx_ai_ff_lookup', 'source', 'model', 'schema_version', 'field_name'),
        db.Index('idx_ai_ff_user_created', 'user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    field_name = db.Column(db.String(40), nullable=False)
    line_index = db.Column(db.Integer, default=-1)
    original_value = db.Column(db.String(500), default='')
    corrected_value = db.Column(db.String(500), default='')
    correction_reason = db.Column(db.String(60), default='')
    adopted = db.Column(db.Boolean, default=False)
    model = db.Column(db.String(100), default='')
    prompt_hash = db.Column(db.String(20), default='')
    schema_version = db.Column(db.String(40), default='')
    source = db.Column(db.String(30), default='ocr_upload')
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    user = db.relationship('User', backref='ai_field_feedback_records')
    ai_run = db.relationship('AIRun', backref=db.backref('field_feedback_records', cascade='all, delete-orphan'))


class AIKnowledgeVersion(db.Model):
    """AI 知识库版本记录 (AI-R12)。

    支持知识草稿、审核、发布、失效、版本、来源、更新时间、发布人、检索权限和回滚。
    同 knowledge_key 可有多版本，published 状态同 key 唯一。
    未发布内容不可检索；回答显示来源和更新时间；实时库存问题必须使用实时数据工具。
    """
    __tablename__ = 'ai_knowledge_version'
    __table_args__ = (
        db.Index('idx_ai_kv_key_version', 'knowledge_key', 'version'),
        db.Index('idx_ai_kv_status_key', 'status', 'knowledge_key'),
        db.Index('idx_ai_kv_published_at', 'published_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    knowledge_key = db.Column(db.String(80), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    title = db.Column(db.String(200), nullable=False, default='')
    summary = db.Column(db.Text, default='')
    content = db.Column(db.Text, default='')
    rule = db.Column(db.Text, default='')
    page_endpoint = db.Column(db.String(80), default='')
    page_label = db.Column(db.String(80), default='')
    keywords = db.Column(db.Text, default='')  # 逗号分隔
    source = db.Column(db.String(20), default='manual')
    status = db.Column(db.String(20), nullable=False, default='draft')
    allowed_roles = db.Column(db.Text, default='')  # 逗号分隔，空表示全部可见
    published_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    published_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    superseded_by = db.Column(db.Integer)  # 被哪个版本替代

    published_by_user = db.relationship('User', foreign_keys=[published_by], backref='published_knowledge_versions')


class AIAgentRunLock(db.Model):
    """Agent 并发互斥锁 (AI-R13)。

    同 concurrency_key 同时只能有一个 Agent 运行；含 TTL 防死锁。
    """
    __tablename__ = 'ai_agent_run_lock'
    __table_args__ = (
        db.Index('idx_ai_lock_key', 'concurrency_key'),
        db.Index('idx_ai_lock_holder', 'holder_run_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    concurrency_key = db.Column(db.String(120), nullable=False)
    holder_run_id = db.Column(db.String(80), nullable=False)
    locked_until = db.Column(db.DateTime, nullable=False)
    acquired_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    released_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='held', nullable=False)


class AIAgentRetryRecord(db.Model):
    """Agent 重试记录 (AI-R13，保留原证据)。"""
    __tablename__ = 'ai_agent_retry_record'
    __table_args__ = (
        db.Index('idx_ai_retry_original', 'original_run_id'),
        db.Index('idx_ai_retry_run', 'retry_run_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    retry_id = db.Column(db.String(60), nullable=False, unique=True)
    original_run_id = db.Column(db.String(80), nullable=False)
    retry_run_id = db.Column(db.String(80), nullable=False)
    retry_reason = db.Column(db.Text, default='')
    original_evidence = db.Column(db.Text, default='{}')  # JSON
    retry_count = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)


class AIAgentHumanConfirmation(db.Model):
    """Agent 人工确认请求 (AI-R13，自动提交业务单据次数为 0)。"""
    __tablename__ = 'ai_agent_human_confirmation'
    __table_args__ = (
        db.Index('idx_ai_human_run', 'run_id'),
        db.Index('idx_ai_human_status', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.String(80), nullable=False)
    step_no = db.Column(db.Integer, default=0, nullable=False)
    action = db.Column(db.String(40), nullable=False)
    target_type = db.Column(db.String(40), default='')
    target_id = db.Column(db.Integer)
    reason = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    decided_at = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='waiting_human', nullable=False)


class AICleanupLog(db.Model):
    """AI 数据清理日志 (AI-R14)。

    记录每次清理操作的统计：类别/删除数/保留数/豁免数/保护数/失败数/截止日期。
    关键审计豁免；业务草稿和确认记录受保护不得清理。
    """
    __tablename__ = 'ai_cleanup_log'
    __table_args__ = (
        db.Index('idx_ai_cleanup_executed_at', 'executed_at'),
        db.Index('idx_ai_cleanup_executed_by', 'executed_by'),
    )

    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.String(60), nullable=False, unique=True)
    executed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    categories = db.Column(db.String(200), default='', nullable=False)  # 逗号分隔
    dry_run = db.Column(db.Boolean, default=False, nullable=False)
    deleted_count = db.Column(db.Integer, default=0, nullable=False)
    kept_count = db.Column(db.Integer, default=0, nullable=False)
    exempt_count = db.Column(db.Integer, default=0, nullable=False)
    protected_count = db.Column(db.Integer, default=0, nullable=False)
    failed_count = db.Column(db.Integer, default=0, nullable=False)
    cutoff_date = db.Column(db.String(40), default='', nullable=False)
    executed_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    notes = db.Column(db.Text, default='')

    executed_by_user = db.relationship('User', backref='ai_cleanup_logs')


class AIDocumentJob(db.Model):
    # AI_TASK: AI-R08-F01
    __tablename__ = 'ai_document_job'
    __table_args__ = (
        db.Index('idx_ai_document_job_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_document_job_status_created', 'status', 'created_at'),
        db.Index('idx_ai_document_job_confirmation_status', 'confirmation_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    source = db.Column(db.String(30), nullable=False)
    document_type = db.Column(db.String(40))
    status = db.Column(db.String(30), nullable=False, default='recognized')
    supplier = db.Column(db.String(100))
    customer = db.Column(db.String(100))
    order_no = db.Column(db.String(100))
    source_text_summary = db.Column(db.String(500))
    source_purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'))
    confirmation_token = db.Column(db.String(40))
    generated_document_type = db.Column(db.String(40))
    generated_document_id = db.Column(db.Integer)
    generated_document_no = db.Column(db.String(100))
    error_message = db.Column(db.String(500))
    image_path = db.Column(db.String(500))
    # AI-R08-F01: 表头字段确认状态
    confirmation_status = db.Column(db.String(30), nullable=False, default='pending')
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    confirmed_at = db.Column(db.DateTime)
    # AI-R08-F01: 风险标记字段（门禁校验用）
    duplicate_risk = db.Column(db.Boolean, nullable=False, default=False)
    low_confidence_fields = db.Column(db.Text)  # JSON 列表，如 '["material_name","quantity"]'
    material_ambiguity = db.Column(db.Boolean, nullable=False, default=False)
    specification_conflict = db.Column(db.Boolean, nullable=False, default=False)
    high_risk_material = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='ai_document_jobs', foreign_keys=[user_id])
    confirmer = db.relationship('User', backref='confirmed_document_jobs', foreign_keys=[confirmed_by])
    ai_run = db.relationship('AIRun', backref='document_jobs')
    source_purchase_order = db.relationship('PurchaseOrder', foreign_keys=[source_purchase_order_id])


class AIDocumentItem(db.Model):
    # AI_TASK: AI-R08-F01
    __tablename__ = 'ai_document_item'
    __table_args__ = (
        db.Index('idx_ai_document_item_job', 'job_id'),
        db.Index('idx_ai_document_item_material', 'material_id'),
        db.Index('idx_ai_document_item_confirmation_status', 'confirmation_status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ai_document_job.id'), nullable=False)
    line_no = db.Column(db.Integer, nullable=False, default=0)
    material_id = db.Column(db.Integer, db.ForeignKey('material.id'))
    raw_text = db.Column(db.String(500))
    code = db.Column(db.String(100))
    name = db.Column(db.String(200))
    spec = db.Column(db.String(200))
    unit = db.Column(db.String(50))
    quantity = db.Column(db.Float, default=0)
    confidence = db.Column(db.Float)
    match_status = db.Column(db.String(30), nullable=False, default='unmatched')
    match_reason = db.Column(db.String(300))
    # AI-R08-F01: 明细行确认状态
    confirmation_status = db.Column(db.String(30), nullable=False, default='pending')
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    job = db.relationship('AIDocumentJob', backref=db.backref('items', cascade='all, delete-orphan'))
    material = db.relationship('Material', backref='ai_document_items')
    confirmer = db.relationship('User', backref='confirmed_document_items', foreign_keys=[confirmed_by])


class AIDocumentFieldConfirmation(db.Model):
    """AI-R08-F01 字段级确认记录。

    存储每个字段的确认状态、原值、确认值、修正原因、证据来源等。
    用于服务端门禁校验和审计追溯。
    """
    # AI_TASK: AI-R08-F01
    __tablename__ = 'ai_document_field_confirmation'
    __table_args__ = (
        db.Index('idx_ai_doc_field_conf_job', 'job_id'),
        db.Index('idx_ai_doc_field_conf_item', 'item_id'),
        db.Index('idx_ai_doc_field_conf_field_name', 'field_name'),
        db.Index('idx_ai_doc_field_conf_status', 'confirmation_status'),
        db.Index('idx_ai_doc_field_conf_confirmed_by', 'confirmed_by'),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ai_document_job.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('ai_document_item.id'))  # 表头字段为 None
    field_name = db.Column(db.String(100), nullable=False)  # 字段名（如 material_name、quantity、unit）
    confirmation_status = db.Column(db.String(30), nullable=False, default='pending')
    original_value = db.Column(db.Text)  # 原值（OCR/视觉/Excel 识别结果）
    confirmed_value = db.Column(db.Text)  # 确认值（用户确认或修正后的值）
    correction_reason = db.Column(db.String(500))  # 修正原因（corrected 状态时必填）
    evidence_source = db.Column(db.String(30), nullable=False)  # 证据来源（ocr/vision/excel/gpt/manual）
    model = db.Column(db.String(100))  # 模型名（如 gpt-4o、qwen-vl-max）
    prompt_version = db.Column(db.String(50))  # 提示词版本
    schema_version = db.Column(db.String(50))  # Schema 版本
    confirmed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    confirmed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    job = db.relationship('AIDocumentJob', backref=db.backref('field_confirmations', cascade='all, delete-orphan'))
    item = db.relationship('AIDocumentItem', backref=db.backref('field_confirmations', cascade='all, delete-orphan'))
    confirmer = db.relationship('User', backref='field_confirmations')


class AIDocumentAttempt(db.Model):
    __tablename__ = 'ai_document_attempt'
    __table_args__ = (
        db.Index('idx_ai_document_attempt_job', 'job_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ai_document_job.id'), nullable=False)
    attempt_no = db.Column(db.Integer, nullable=False, default=1)
    source = db.Column(db.String(30), nullable=False)
    model = db.Column(db.String(100))
    prompt_version = db.Column(db.String(50), default='legacy-v1')
    status = db.Column(db.String(30), nullable=False, default='started')
    item_count = db.Column(db.Integer, default=0)
    matched_count = db.Column(db.Integer, default=0)
    unmatched_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)

    job = db.relationship('AIDocumentJob', backref=db.backref('attempts', cascade='all, delete-orphan'))


class AIDocumentFeedback(db.Model):
    __tablename__ = 'ai_document_feedback'
    __table_args__ = (
        db.Index('idx_ai_document_feedback_job', 'job_id'),
        db.Index('idx_ai_document_feedback_user_created', 'user_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('ai_document_job.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.String(20), nullable=False)
    error_type = db.Column(db.String(50))
    note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    job = db.relationship('AIDocumentJob', backref=db.backref('feedbacks', cascade='all, delete-orphan'))
    user = db.relationship('User', backref='ai_document_feedbacks')


class AIAgentTask(db.Model):
    __tablename__ = 'ai_agent_task'
    __table_args__ = (
        db.Index('idx_ai_agent_task_user_created', 'user_id', 'created_at'),
        db.Index('idx_ai_agent_task_type_status', 'agent_type', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    ai_run_id = db.Column(db.Integer, db.ForeignKey('ai_run.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    agent_type = db.Column(db.String(50), nullable=False)
    objective = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(30), nullable=False, default='running')
    summary = db.Column(db.String(1000))
    next_action_url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', backref='ai_agent_tasks')
    ai_run = db.relationship('AIRun', backref='agent_tasks')


class AIAgentStep(db.Model):
    __tablename__ = 'ai_agent_step'
    __table_args__ = (
        db.Index('idx_ai_agent_step_task', 'task_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('ai_agent_task.id'), nullable=False)
    step_no = db.Column(db.Integer, nullable=False, default=1)
    name = db.Column(db.String(120), nullable=False)
    tool_name = db.Column(db.String(100))
    risk_level = db.Column(db.String(30), nullable=False, default='read')
    status = db.Column(db.String(30), nullable=False, default='completed')
    data_scope = db.Column(db.String(300))
    result_summary = db.Column(db.String(1000))
    action_label = db.Column(db.String(100))
    action_url = db.Column(db.String(300))
    error_message = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    task = db.relationship('AIAgentTask', backref=db.backref('steps', cascade='all, delete-orphan'))


class AIPatrolRule(db.Model):
    """AI巡检规则配置"""
    __tablename__ = 'ai_patrol_rule'
    __table_args__ = (
        db.Index('idx_ai_patrol_rule_enabled', 'enabled'),
        db.Index('idx_ai_patrol_rule_type', 'rule_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    rule_type = db.Column(db.String(50), nullable=False)  # negative_stock, low_stock, overdue_order, pending_draft, purchase_delay
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    threshold_value = db.Column(db.Float)  # 阈值（如低库存数量）
    threshold_days = db.Column(db.Integer)  # 阈值天数（如逾期天数）
    severity = db.Column(db.String(20), default='warning')  # info, warning, critical
    notify_roles = db.Column(db.String(500))  # JSON数组，如 '["admin","warehouse"]'
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    creator = db.relationship('User', backref='ai_patrol_rules')


class AIPatrolAlert(db.Model):
    """AI巡检告警记录"""
    __tablename__ = 'ai_patrol_alert'
    __table_args__ = (
        db.Index('idx_ai_patrol_alert_rule', 'rule_id'),
        db.Index('idx_ai_patrol_alert_status', 'status'),
        db.Index('idx_ai_patrol_alert_created', 'created_at'),
        db.Index('idx_ai_patrol_alert_acknowledged', 'acknowledged_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey('ai_patrol_rule.id'), nullable=False)
    alert_type = db.Column(db.String(50), nullable=False)  # 与rule.rule_type一致
    severity = db.Column(db.String(20), nullable=False, default='warning')
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    data_context = db.Column(db.Text)  # JSON格式，存储告警相关数据
    status = db.Column(db.String(20), nullable=False, default='active')  # active, acknowledged, resolved, dismissed
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    acknowledged_at = db.Column(db.DateTime)
    resolved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    resolved_at = db.Column(db.DateTime)
    resolution_note = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)

    rule = db.relationship('AIPatrolRule', backref=db.backref('alerts', cascade='all, delete-orphan'))
    acknowledger = db.relationship('User', foreign_keys=[acknowledged_by], backref='acknowledged_alerts')
    resolver = db.relationship('User', foreign_keys=[resolved_by], backref='resolved_alerts')


class AIPatrolSchedule(db.Model):
    """AI巡检调度配置"""
    __tablename__ = 'ai_patrol_schedule'
    __table_args__ = (
        db.Index('idx_ai_patrol_schedule_enabled', 'enabled'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    cron_expression = db.Column(db.String(50), nullable=False)  # 如 '0 8 * * *' 表示每天8点
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    last_run_at = db.Column(db.DateTime)
    next_run_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    creator = db.relationship('User', backref='ai_patrol_schedules')
