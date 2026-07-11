from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Callable

from flask import Response, current_app, g, jsonify, request, stream_with_context
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from ai.prompts import CURRENT_PROMPT_VERSION


_CONFIGURED_SERVICE: AIIdempotencyService | None = None


@dataclass(frozen=True)
class AIIdempotencyService:
    db: object
    run_model: type
    request_model: type
    model_name_getter: Callable[[], str]

    def error(self, message: str, status_code: int = 409):
        return jsonify({'status': 'error', 'msg': message}), status_code

    def replay(self, record):
        return Response(
            record.response_body or '',
            status=record.response_status or 200,
            content_type=record.response_content_type or 'application/json; charset=utf-8',
        )

    def finish_run(self, run_id: int, status: str, error_message: str = '') -> None:
        run = self.db.session.get(self.run_model, run_id)
        if not run:
            return
        completed_at = datetime.now()
        run.status = status
        run.completed_at = completed_at
        run.duration_ms = max(0, int((completed_at - run.started_at).total_seconds() * 1000))
        run.error_message = (error_message or '')[:500] or None

    def finish_request(self, record_id: int, response_status: int, content_type: str, response_body: str) -> None:
        record = self.db.session.get(self.request_model, record_id)
        if not record:
            return
        record.status = 'completed'
        record.response_status = response_status
        record.response_content_type = (content_type or '')[:120]
        record.response_body = response_body
        record.completed_at = datetime.now()
        record.updated_at = datetime.now()
        run_failed = response_status >= 500 or bool(re.search(r'"type"\s*:\s*"error"', response_body or ''))
        if record.ai_run_id:
            self.finish_run(record.ai_run_id, 'failed' if run_failed else 'completed')
        self.db.session.commit()

    def fail_request(self, record_id: int, error_message: str = '') -> None:
        self.db.session.rollback()
        record = self.db.session.get(self.request_model, record_id)
        if not record:
            return
        record.status = 'failed'
        record.updated_at = datetime.now()
        if record.ai_run_id:
            self.finish_run(record.ai_run_id, 'failed', error_message)
        self.db.session.commit()

    def idempotent_request(self, view_function):
        @wraps(view_function)
        def wrapped(*args, **kwargs):
            payload = request.get_json(silent=True) or {}
            request_id = str(payload.get('request_id') or '').strip()
            if not request_id:
                return self.error('缺少 request_id，无法安全处理 AI 请求', 400)
            if not re.fullmatch(r'[A-Za-z0-9._:-]{8,80}', request_id):
                return self.error('request_id 格式不正确', 400)

            request_hash = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
            ).hexdigest()
            record = self.request_model.query.filter_by(
                user_id=current_user.id,
                request_id=request_id,
            ).first()
            if record:
                if record.request_hash != request_hash:
                    return self.error('request_id 已用于不同请求')
                if record.status == 'completed':
                    return self.replay(record)
                return self.error('该 AI 请求正在处理或此前处理失败，请先检查是否已生成草稿')

            run = self.run_model(
                user_id=current_user.id,
                request_id=request_id,
                request_hash=request_hash,
                endpoint=request.path[:100],
                status='running',
                model=self.model_name_getter()[:100],
                prompt_version=CURRENT_PROMPT_VERSION,
            )
            record = self.request_model(
                user_id=current_user.id,
                request_id=request_id,
                request_hash=request_hash,
                endpoint=request.path[:100],
                status='processing',
            )
            self.db.session.add(run)
            self.db.session.add(record)
            try:
                self.db.session.flush()
                record.ai_run_id = run.id
                self.db.session.commit()
            except IntegrityError:
                self.db.session.rollback()
                existing = self.request_model.query.filter_by(
                    user_id=current_user.id,
                    request_id=request_id,
                ).first()
                if existing and existing.request_hash == request_hash and existing.status == 'completed':
                    return self.replay(existing)
                return self.error('该 AI 请求已被接收，请勿重复提交')

            record_id = record.id
            g.ai_run_id = run.id
            try:
                response = current_app.make_response(view_function(*args, **kwargs))
            except Exception as exc:
                self.fail_request(record_id, str(exc))
                raise

            if response.is_streamed:
                original_iterator = response.response
                response_status = response.status_code
                content_type = response.content_type

                def record_stream():
                    body_parts: list[str] = []
                    try:
                        for chunk in original_iterator:
                            if isinstance(chunk, bytes):
                                body_parts.append(chunk.decode('utf-8', errors='replace'))
                            else:
                                body_parts.append(str(chunk))
                            yield chunk
                        self.finish_request(
                            record_id,
                            response_status,
                            content_type,
                            ''.join(body_parts),
                        )
                    except BaseException as exc:
                        self.fail_request(record_id, str(exc))
                        raise

                response.response = stream_with_context(record_stream())
                return response

            response_body = response.get_data(as_text=True)
            self.finish_request(
                record_id,
                response.status_code,
                response.content_type,
                response_body,
            )
            return response

        return wrapped


def create_ai_idempotency_service(db, run_model, request_model, model_name_getter: Callable[[], str]) -> AIIdempotencyService:
    return AIIdempotencyService(
        db=db,
        run_model=run_model,
        request_model=request_model,
        model_name_getter=model_name_getter,
    )


def configure_ai_idempotency_service(db, run_model, request_model, model_name_getter: Callable[[], str]) -> AIIdempotencyService:
    global _CONFIGURED_SERVICE
    _CONFIGURED_SERVICE = create_ai_idempotency_service(db, run_model, request_model, model_name_getter)
    return _CONFIGURED_SERVICE


def get_ai_idempotency_service() -> AIIdempotencyService:
    if _CONFIGURED_SERVICE is None:
        raise RuntimeError('AI idempotency service has not been configured')
    return _CONFIGURED_SERVICE


def ai_idempotent_request(view_function):
    @wraps(view_function)
    def wrapped(*args, **kwargs):
        return get_ai_idempotency_service().idempotent_request(view_function)(*args, **kwargs)

    return wrapped
