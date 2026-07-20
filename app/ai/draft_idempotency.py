"""AI 草稿统一幂等与审计闭环服务 (AI-R01)。
# AI_TASK: AI-R01

目标：
- 重复上传、重复点击、网络重试、Provider 重试或并发请求均不能创建重复草稿。
- 每张草稿可追溯完整 AI 链路（AIRun、AIToolCall、确认令牌、文档任务、业务草稿）。

设计：
- 幂等键 = sha256(user_id + capability + source + 业务关键字段排序)
- 数据库唯一约束 (user_id, capability, idempotency_key) 保证并发请求只成功一次。
- 状态流转：processing -> completed / failed；completed 命中即 replay，failed 允许重试。
- 失败重试保留原错误和运行证据，不覆盖历史记录（通过 status 流转而非删除）。
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from flask import g, has_request_context
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

DRAFT_STATUS_PROCESSING = 'processing'
DRAFT_STATUS_COMPLETED = 'completed'
DRAFT_STATUS_FAILED = 'failed'
DRAFT_STATUS_REPLAYED = 'replayed'


def compute_draft_idempotency_key(
    user_id: int,
    capability: str,
    source: str,
    business_fields: Mapping[str, Any] | None,
) -> str:
    """计算草稿创建请求的确定性幂等键。

    合并用户、能力、来源和排序后的业务关键字段，使语义相同的请求发生碰撞（用于去重），
    而任一字段变化产生新键（允许合法重建）。
    """
    normalized_business: Any = {}
    if business_fields:
        for key in sorted(business_fields):
            value = business_fields[key]
            if isinstance(value, (list, tuple)):
                normalized_business[key] = list(value)
            elif isinstance(value, dict):
                normalized_business[key] = dict(sorted(value.items()))
            else:
                normalized_business[key] = value
    payload = {
        'u': int(user_id or 0),
        'c': str(capability or ''),
        's': str(source or ''),
        'b': normalized_business,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


@dataclass
class DraftIdempotencySlot:
    """获取草稿幂等槽位的结果。"""
    acquired: bool
    record: Any = None
    replay: Any | None = None
    conflict_reason: str = ''
    is_replay: bool = False


class AIDraftIdempotencyService:
    """统一草稿幂等与审计闭环服务。"""

    def __init__(self, db, draft_model, run_model=None, tool_call_model=None):
        self.db = db
        self.draft_model = draft_model
        self.run_model = run_model
        self.tool_call_model = tool_call_model

    # ---- 幂等键计算 ----

    @staticmethod
    def compute_key(user_id, capability, source, business_fields):
        return compute_draft_idempotency_key(user_id, capability, source, business_fields)

    # ---- 槽位获取 ----

    def acquire(
        self,
        *,
        capability: str,
        source: str,
        business_fields: Mapping[str, Any] | None,
        draft_type: str,
        request_snapshot: Mapping[str, Any] | None = None,
        confirmation_token: str | None = None,
        document_job_id: int | None = None,
        user_id: int | None = None,
        ai_run_id: int | None = None,
        ai_tool_call_id: int | None = None,
    ) -> DraftIdempotencySlot:
        """尝试获取草稿创建的处理中槽位。

        返回：
          - acquired=True, record=<processing 行>  -> 继续创建草稿
          - acquired=False, is_replay=True, replay=<已存响应>  -> 返回已存草稿，不重复创建
          - acquired=False, conflict_reason=...  -> 处理中或并发，拒绝调用方
        """
        uid = int(user_id) if user_id is not None else self._current_user_id()
        key = self.compute_key(uid, capability, source, business_fields)

        existing = self.draft_model.query.filter_by(
            user_id=uid,
            capability=capability,
            idempotency_key=key,
        ).first()
        if existing:
            if existing.status == DRAFT_STATUS_COMPLETED:
                # 不修改历史状态：保持 completed 不变，避免丢失"已完成"语义。
                # 仅更新 updated_at 以记录本次 replay 活动。
                replay = self._decode(existing.response_snapshot)
                existing.updated_at = datetime.now()
                self.db.session.commit()
                return DraftIdempotencySlot(
                    acquired=False,
                    record=existing,
                    replay=replay,
                    is_replay=True,
                    conflict_reason='completed draft replayed',
                )
            if existing.status == DRAFT_STATUS_PROCESSING:
                return DraftIdempotencySlot(
                    acquired=False,
                    record=existing,
                    conflict_reason='该草稿请求正在处理中，请勿重复提交',
                )
            # failed -> 允许重试，复用原记录；清除上次错误以进入新一轮处理
            existing.status = DRAFT_STATUS_PROCESSING
            existing.error_message = None
            existing.ai_tool_call_id = ai_tool_call_id or existing.ai_tool_call_id
            existing.updated_at = datetime.now()
            self.db.session.commit()
            return DraftIdempotencySlot(acquired=True, record=existing)

        run_id = ai_run_id if ai_run_id is not None else self._current_run_id()
        source_hash = self._source_hash(source, business_fields)
        record = self.draft_model(
            user_id=uid,
            ai_run_id=run_id,
            ai_tool_call_id=ai_tool_call_id,
            capability=capability,
            idempotency_key=key,
            source=(source or 'text')[:30],
            source_hash=source_hash,
            business_key=self._encode(business_fields),
            confirmation_token=(confirmation_token or '')[:64] or None,
            document_job_id=document_job_id,
            draft_type=(draft_type or '')[:40],
            status=DRAFT_STATUS_PROCESSING,
            request_snapshot=self._encode(request_snapshot),
        )
        self.db.session.add(record)
        try:
            self.db.session.commit()
        except IntegrityError:
            self.db.session.rollback()
            existing = self.draft_model.query.filter_by(
                user_id=uid,
                capability=capability,
                idempotency_key=key,
            ).first()
            if existing and existing.status == DRAFT_STATUS_COMPLETED:
                replay = self._decode(existing.response_snapshot)
                return DraftIdempotencySlot(
                    acquired=False,
                    record=existing,
                    replay=replay,
                    is_replay=True,
                    conflict_reason='completed draft replayed (race)',
                )
            return DraftIdempotencySlot(
                acquired=False,
                record=existing,
                conflict_reason='该草稿请求已被并发接收，请勿重复提交',
            )
        return DraftIdempotencySlot(acquired=True, record=record)

    # ---- 结果记录 ----

    def complete(
        self,
        record,
        *,
        draft_type: str,
        draft_id: int | None,
        draft_no: str | None,
        response: Mapping[str, Any] | None,
    ) -> None:
        """标记槽位为已完成，记录业务草稿引用。"""
        if not record:
            return
        record.status = DRAFT_STATUS_COMPLETED
        record.draft_type = (draft_type or record.draft_type or '')[:40]
        record.draft_id = draft_id
        record.draft_no = (draft_no or '')[:60]
        record.response_snapshot = self._encode(response)
        record.error_message = None
        record.completed_at = datetime.now()
        record.updated_at = datetime.now()
        self.db.session.commit()

    def fail(self, record, error_message: str) -> None:
        """标记槽位为失败，保留原错误和运行证据，不覆盖历史记录。"""
        if not record:
            return
        record.status = DRAFT_STATUS_FAILED
        record.error_message = (error_message or '')[:500] or None
        record.updated_at = datetime.now()
        self.db.session.commit()

    def attach_tool_call(self, record, ai_tool_call_id: int | None) -> None:
        """补关联工具调用记录（当工具调用在槽位获取之后才创建时）。"""
        if not record or not ai_tool_call_id:
            return
        if record.ai_tool_call_id == ai_tool_call_id:
            return
        record.ai_tool_call_id = ai_tool_call_id
        self.db.session.commit()

    # ---- 反查链路 ----

    def find_by_draft(self, draft_type: str, draft_id: int):
        """由业务草稿反查 AI 幂等与审计记录。"""
        if not draft_type or not draft_id:
            return None
        return self.draft_model.query.filter_by(
            draft_type=draft_type,
            draft_id=draft_id,
        ).order_by(self.draft_model.id.desc()).first()

    def find_by_run(self, ai_run_id: int):
        """由 AIRun 反查其产生的全部草稿幂等记录。"""
        if not ai_run_id:
            return []
        return self.draft_model.query.filter_by(ai_run_id=ai_run_id).all()

    def find_by_confirmation(self, confirmation_token: str):
        """由确认令牌反查草稿幂等记录。"""
        if not confirmation_token:
            return None
        return self.draft_model.query.filter_by(
            confirmation_token=confirmation_token,
        ).order_by(self.draft_model.id.desc()).first()

    # ---- 辅助 ----

    def _current_user_id(self) -> int:
        if has_request_context() and getattr(current_user, 'is_authenticated', False):
            return int(current_user.id)
        return 0

    def _current_run_id(self):
        if has_request_context():
            return getattr(g, 'ai_run_id', None)
        return None

    @staticmethod
    def _encode(value) -> str | None:
        if value is None:
            return None
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _decode(text: str | None):
        if not text:
            return None
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _source_hash(source: str, business_fields) -> str:
        payload = {'s': str(source or ''), 'b': business_fields or {}}
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()


_CONFIGURED_DRAFT_SERVICE: AIDraftIdempotencyService | None = None


def configure_ai_draft_idempotency_service(
    db,
    draft_model,
    run_model=None,
    tool_call_model=None,
) -> AIDraftIdempotencyService:
    global _CONFIGURED_DRAFT_SERVICE
    _CONFIGURED_DRAFT_SERVICE = AIDraftIdempotencyService(
        db=db,
        draft_model=draft_model,
        run_model=run_model,
        tool_call_model=tool_call_model,
    )
    return _CONFIGURED_DRAFT_SERVICE


def get_ai_draft_idempotency_service() -> AIDraftIdempotencyService:
    if _CONFIGURED_DRAFT_SERVICE is None:
        raise RuntimeError('AI draft idempotency service has not been configured')
    return _CONFIGURED_DRAFT_SERVICE
