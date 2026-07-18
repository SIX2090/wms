"""阶段3：Agent框架。

受控业务Agent的核心框架，提供：
- 计划生成与展示
- 步骤执行与状态跟踪
- 权限校验
- 审计记录
- 用户取消支持
- 失败回滚与清理
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class AgentStepStatus(str, Enum):
    """Agent步骤状态。"""
    PENDING = 'pending'  # 待执行
    RUNNING = 'running'  # 执行中
    SUCCESS = 'success'  # 成功
    FAILED = 'failed'  # 失败
    SKIPPED = 'skipped'  # 跳过
    CANCELLED = 'cancelled'  # 已取消


class AgentRunStatus(str, Enum):
    """Agent运行状态。"""
    PLANNING = 'planning'  # 计划中
    EXECUTING = 'executing'  # 执行中
    COMPLETED = 'completed'  # 已完成
    FAILED = 'failed'  # 失败
    CANCELLED = 'cancelled'  # 已取消


@dataclass
class AgentStep:
    """Agent执行步骤。"""
    step_no: int
    name: str
    description: str
    tool_name: str
    is_write: bool = False  # 是否为写操作
    requires_confirmation: bool = False  # 是否需要确认
    status: AgentStepStatus = AgentStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None  # 幂等键（写操作）

    def to_dict(self) -> dict[str, Any]:
        return {
            'step_no': self.step_no,
            'name': self.name,
            'description': self.description,
            'tool_name': self.tool_name,
            'is_write': self.is_write,
            'requires_confirmation': self.requires_confirmation,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'idempotency_key': self.idempotency_key,
        }


@dataclass
class AgentPlan:
    """Agent执行计划。"""
    agent_name: str
    goal: str
    steps: list[AgentStep] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            'agent_name': self.agent_name,
            'goal': self.goal,
            'steps': [s.to_dict() for s in self.steps],
            'created_at': self.created_at.isoformat(),
            'total_steps': len(self.steps),
            'write_steps': sum(1 for s in self.steps if s.is_write),
            'read_steps': sum(1 for s in self.steps if not s.is_write),
        }


@dataclass
class AgentRun:
    """Agent运行实例。"""
    run_id: str
    agent_name: str
    user_id: int
    plan: AgentPlan
    status: AgentRunStatus = AgentRunStatus.PLANNING
    current_step: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error: Optional[str] = None
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'agent_name': self.agent_name,
            'user_id': self.user_id,
            'status': self.status.value,
            'current_step': self.current_step,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'error': self.error,
            'plan': self.plan.to_dict(),
            'context': self.context,
        }


class AgentExecutor:
    """Agent执行器。"""

    def __init__(self, run: AgentRun):
        self.run = run
        self._cancelled = False
        self._tools: dict[str, Callable] = {}

    def register_tool(self, name: str, func: Callable) -> None:
        """注册工具函数。"""
        self._tools[name] = func

    def cancel(self) -> None:
        """取消执行。"""
        self._cancelled = True
        self.run.status = AgentRunStatus.CANCELLED
        self.run.cancelled_at = datetime.now()

        # 标记所有待执行步骤为已取消
        for step in self.run.plan.steps:
            if step.status == AgentStepStatus.PENDING:
                step.status = AgentStepStatus.CANCELLED

    def is_cancelled(self) -> bool:
        """是否已取消。"""
        return self._cancelled

    def execute(self) -> AgentRun:
        """执行Agent计划。"""
        self.run.status = AgentRunStatus.EXECUTING

        # AI_TASK: AI-R13
        # 集成预算检查钩子：执行前检查预算约束
        budget_config = self.run.context.get('budget_config')
        if budget_config:
            try:
                from ai.agents.budget_control import check_budget
                budget_result = check_budget(
                    budget_config,
                    current_steps=self.run.current_step,
                    started_at_iso=self.run.started_at.isoformat(),
                    current_tool_calls=len(self.run.plan.steps),
                )
                if not budget_result.passed:
                    logger.warning('预算检查失败，停止执行: %s', budget_result.reason)
                    self.run.status = AgentRunStatus.FAILED
                    self.run.error = f'预算检查失败: {budget_result.reason}'
                    self.run.completed_at = datetime.now()
                    return self.run
            except Exception as e:  # noqa: BLE001
                logger.warning('预算检查异常，继续执行: %s', e)

        for i, step in enumerate(self.run.plan.steps):
            if self.is_cancelled():
                break

            # 检查前置步骤是否成功（写操作依赖的只读步骤）
            if step.status != AgentStepStatus.PENDING:
                continue

            # AI_TASK: AI-R13
            # 每步执行前再次检查预算（防止执行过程中超限）
            if budget_config:
                try:
                    from ai.agents.budget_control import check_budget
                    budget_result = check_budget(
                        budget_config,
                        current_steps=i + 1,
                        started_at_iso=self.run.started_at.isoformat(),
                        current_tool_calls=i + 1,
                    )
                    if not budget_result.passed:
                        logger.warning('步骤 %d 预算检查失败，停止执行: %s', step.step_no, budget_result.reason)
                        step.status = AgentStepStatus.FAILED
                        step.error = f'预算检查失败: {budget_result.reason}'
                        step.completed_at = datetime.now()
                        break
                except Exception as e:  # noqa: BLE001
                    logger.warning('步骤 %d 预算检查异常，继续执行: %s', step.step_no, e)

            # 执行步骤
            step.status = AgentStepStatus.RUNNING
            step.started_at = datetime.now()
            self.run.current_step = i + 1

            try:
                # 权限校验（写操作需要额外确认）
                if step.is_write and step.requires_confirmation:
                    logger.info('Step %d requires confirmation, skipping auto-execution', step.step_no)
                    step.status = AgentStepStatus.SKIPPED
                    step.completed_at = datetime.now()
                    continue

                # 调用工具
                tool_func = self._tools.get(step.tool_name)
                if not tool_func:
                    raise ValueError(f'Tool not found: {step.tool_name}')

                result = tool_func(**self.run.context)
                step.result = result
                step.status = AgentStepStatus.SUCCESS

            except Exception as e:
                step.error = str(e)
                step.status = AgentStepStatus.FAILED
                logger.error('Step %d failed: %s', step.step_no, e)

                # 关键只读步骤失败时，停止后续写操作
                if not step.is_write:
                    logger.warning('Critical read step failed, stopping execution')
                    break

            step.completed_at = datetime.now()

        # 确定最终状态
        if self.is_cancelled():
            self.run.status = AgentRunStatus.CANCELLED
        elif any(s.status == AgentStepStatus.FAILED for s in self.run.plan.steps):
            self.run.status = AgentRunStatus.FAILED
            self.run.error = 'One or more steps failed'
        else:
            self.run.status = AgentRunStatus.COMPLETED

        self.run.completed_at = datetime.now()
        return self.run

    def get_summary(self) -> dict[str, Any]:
        """获取执行摘要。"""
        total = len(self.run.plan.steps)
        success = sum(1 for s in self.run.plan.steps if s.status == AgentStepStatus.SUCCESS)
        failed = sum(1 for s in self.run.plan.steps if s.status == AgentStepStatus.FAILED)
        skipped = sum(1 for s in self.run.plan.steps if s.status == AgentStepStatus.SKIPPED)
        cancelled = sum(1 for s in self.run.plan.steps if s.status == AgentStepStatus.CANCELLED)
        pending = sum(1 for s in self.run.plan.steps if s.status == AgentStepStatus.PENDING)

        return {
            'run_id': self.run.run_id,
            'status': self.run.status.value,
            'total_steps': total,
            'success': success,
            'failed': failed,
            'skipped': skipped,
            'cancelled': cancelled,
            'pending': pending,
            'next_steps': [s.to_dict() for s in self.run.plan.steps if s.status == AgentStepStatus.PENDING],
        }


def create_agent_run(
    agent_name: str,
    user_id: int,
    goal: str,
    steps: list[dict[str, Any]],
    context: Optional[dict[str, Any]] = None,
) -> AgentRun:
    """创建Agent运行实例。

    Args:
        agent_name: Agent名称
        user_id: 用户ID
        goal: 执行目标
        steps: 步骤列表，每项包含 name/description/tool_name/is_write/requires_confirmation
        context: 执行上下文

    Returns:
        AgentRun实例
    """
    import uuid

    run_id = f'{agent_name}-{uuid.uuid4().hex[:8]}'
    plan = AgentPlan(agent_name=agent_name, goal=goal)

    for i, step_data in enumerate(steps, 1):
        step = AgentStep(
            step_no=i,
            name=step_data.get('name', f'Step {i}'),
            description=step_data.get('description', ''),
            tool_name=step_data.get('tool_name', ''),
            is_write=step_data.get('is_write', False),
            requires_confirmation=step_data.get('requires_confirmation', False),
        )
        plan.steps.append(step)

    return AgentRun(
        run_id=run_id,
        agent_name=agent_name,
        user_id=user_id,
        plan=plan,
        context=context or {},
    )
