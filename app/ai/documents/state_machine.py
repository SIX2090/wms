"""阶段2：文档任务状态机。

管理文档识别任务的生命周期：
uploading → recognizing → pending_confirm → draft_created
                                    ↓
                                  failed / cancelled

每个状态转换都记录时间戳和操作人。
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from .schemas import DocumentStatus


class StateMachineError(Exception):
    """状态机转换错误。"""
    pass


# 合法的状态转换
VALID_TRANSITIONS = {
    DocumentStatus.UPLOADING: [DocumentStatus.RECOGNIZING, DocumentStatus.FAILED],
    DocumentStatus.RECOGNIZING: [DocumentStatus.PENDING_CONFIRM, DocumentStatus.FAILED],
    DocumentStatus.PENDING_CONFIRM: [DocumentStatus.DRAFT_CREATED, DocumentStatus.FAILED, DocumentStatus.CANCELLED],
    DocumentStatus.DRAFT_CREATED: [],  # 终态
    DocumentStatus.FAILED: [],  # 终态
    DocumentStatus.CANCELLED: [],  # 终态
}


class DocumentTaskStateMachine:
    """文档任务状态机。"""

    def __init__(
        self,
        task_id: int,
        current_status: DocumentStatus,
        user_id: Optional[int] = None,
    ):
        self.task_id = task_id
        self.current_status = current_status
        self.user_id = user_id
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.status_history = [(current_status, self.created_at, user_id)]

    def transition(self, new_status: DocumentStatus, user_id: Optional[int] = None) -> None:
        """执行状态转换。

        Args:
            new_status: 目标状态
            user_id: 操作人ID

        Raises:
            StateMachineError: 非法的状态转换
        """
        allowed = VALID_TRANSITIONS.get(self.current_status, [])
        if new_status not in allowed:
            raise StateMachineError(
                f'非法状态转换: {self.current_status.value} → {new_status.value} '
                f'(任务 {self.task_id})'
            )

        self.current_status = new_status
        self.updated_at = datetime.now()
        self.status_history.append((new_status, self.updated_at, user_id))

    def can_transition_to(self, new_status: DocumentStatus) -> bool:
        """检查是否可以转换到目标状态。"""
        return new_status in VALID_TRANSITIONS.get(self.current_status, [])

    def is_terminal(self) -> bool:
        """是否处于终态。"""
        return self.current_status in (
            DocumentStatus.DRAFT_CREATED,
            DocumentStatus.FAILED,
            DocumentStatus.CANCELLED,
        )

    def get_history(self) -> list[dict]:
        """获取状态历史。"""
        return [
            {
                'status': status.value,
                'timestamp': timestamp.isoformat(),
                'user_id': user_id,
            }
            for status, timestamp, user_id in self.status_history
        ]

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            'task_id': self.task_id,
            'current_status': self.current_status.value,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_terminal': self.is_terminal(),
            'status_history': self.get_history(),
        }


def create_task(user_id: int) -> DocumentTaskStateMachine:
    """创建新的文档任务（初始状态：uploading）。"""
    return DocumentTaskStateMachine(
        task_id=0,  # 实际ID由数据库生成
        current_status=DocumentStatus.UPLOADING,
        user_id=user_id,
    )


def start_recognition(task: DocumentTaskStateMachine, user_id: Optional[int] = None) -> None:
    """开始识别（uploading → recognizing）。"""
    task.transition(DocumentStatus.RECOGNIZING, user_id)


def complete_recognition(task: DocumentTaskStateMachine, user_id: Optional[int] = None) -> None:
    """识别完成（recognizing → pending_confirm）。"""
    task.transition(DocumentStatus.PENDING_CONFIRM, user_id)


def create_draft(task: DocumentTaskStateMachine, user_id: Optional[int] = None) -> None:
    """生成草稿（pending_confirm → draft_created）。"""
    task.transition(DocumentStatus.DRAFT_CREATED, user_id)


def fail_task(task: DocumentTaskStateMachine, user_id: Optional[int] = None) -> None:
    """任务失败（任意状态 → failed）。"""
    task.transition(DocumentStatus.FAILED, user_id)


def cancel_task(task: DocumentTaskStateMachine, user_id: Optional[int] = None) -> None:
    """取消任务（pending_confirm → cancelled）。"""
    task.transition(DocumentStatus.CANCELLED, user_id)
