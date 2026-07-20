"""AI-R02: AI 工具合规检查
# AI_TASK: AI-R02

校验 AI_TOOL_REGISTRY 中每个工具的权限、风险级别、审计类别是否齐全且合法。
扩展 verify_ai_tool_schemas 的 Schema 检查，覆盖权限/风险维度。

检查项：
1. 每个工具必须有非空 allowed_roles（至少一个合法角色）
2. risk_level 必须在合法集合 {read, sensitive_read, draft, submit, audit,
   complete, void, delete, stock_write} 内
3. audit_category 非空
4. risk_level='draft' 的工具必须 confirmation_required=True（草稿需人工确认）
5. AI_CAPABILITY_ROLES / AI_CAPABILITY_RISK_LEVELS 与 AI_TOOL_REGISTRY 三者键一致

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.tools.registry import AI_TOOL_REGISTRY
from ai.policies import (
    AI_CAPABILITY_ROLES,
    AI_CAPABILITY_RISK_LEVELS,
    AI_AUTONOMOUS_RISK_LEVELS,
    AI_MANUAL_CONFIRMATION_RISK_LEVELS,
    AI_FORBIDDEN_RISK_LEVELS,
)


VALID_RISK_LEVELS = (
    AI_AUTONOMOUS_RISK_LEVELS
    | AI_MANUAL_CONFIRMATION_RISK_LEVELS
    | AI_FORBIDDEN_RISK_LEVELS
)

VALID_ROLES = frozenset({'admin', 'warehouse', 'purchase', 'sales', 'production', 'user'})


def main() -> int:
    failures: list[str] = []

    # 1. 三表键一致性：AI_TOOL_REGISTRY / AI_CAPABILITY_ROLES / AI_CAPABILITY_RISK_LEVELS
    registry_keys = set(AI_TOOL_REGISTRY)
    roles_keys = set(AI_CAPABILITY_ROLES)
    risk_keys = set(AI_CAPABILITY_RISK_LEVELS)

    if registry_keys != roles_keys:
        missing_roles = registry_keys - roles_keys
        extra_roles = roles_keys - registry_keys
        failures.append(
            f'AI_CAPABILITY_ROLES 与 AI_TOOL_REGISTRY 键不一致: '
            f'missing={sorted(missing_roles)} extra={sorted(extra_roles)}'
        )
    if registry_keys != risk_keys:
        missing_risk = registry_keys - risk_keys
        extra_risk = risk_keys - registry_keys
        failures.append(
            f'AI_CAPABILITY_RISK_LEVELS 与 AI_TOOL_REGISTRY 键不一致: '
            f'missing={sorted(missing_risk)} extra={sorted(extra_risk)}'
        )

    # 2. 逐工具检查字段合规性
    for name, spec in AI_TOOL_REGISTRY.items():
        # allowed_roles 非空且均为合法角色
        if not spec.allowed_roles:
            failures.append(f'{name}: allowed_roles 为空')
        else:
            invalid_roles = set(spec.allowed_roles) - VALID_ROLES
            if invalid_roles:
                failures.append(f'{name}: allowed_roles 含非法角色 {sorted(invalid_roles)}')

        # risk_level 合法
        if spec.risk_level not in VALID_RISK_LEVELS:
            failures.append(
                f'{name}: risk_level={spec.risk_level!r} 不在合法集合 {sorted(VALID_RISK_LEVELS)}'
            )

        # audit_category 非空
        if not spec.audit_category or not spec.audit_category.strip():
            failures.append(f'{name}: audit_category 为空')

        # 草稿级风险必须要求人工确认
        if spec.risk_level in AI_MANUAL_CONFIRMATION_RISK_LEVELS and not spec.confirmation_required:
            failures.append(
                f'{name}: risk_level={spec.risk_level} 但 confirmation_required=False，草稿必须人工确认'
            )

        # 禁止级风险不应出现在已注册工具中（AI 不得执行 submit/audit/complete 等）
        if spec.risk_level in AI_FORBIDDEN_RISK_LEVELS:
            failures.append(
                f'{name}: risk_level={spec.risk_level} 属于禁止级，不应注册为 AI 工具'
            )

        # 风险级别与 policies 表声明一致
        declared_risk = AI_CAPABILITY_RISK_LEVELS.get(name)
        if declared_risk is not None and declared_risk != spec.risk_level:
            failures.append(
                f'{name}: registry risk_level={spec.risk_level!r} 与 policies 声明 {declared_risk!r} 不一致'
            )

        # 角色与 policies 表声明一致
        declared_roles = AI_CAPABILITY_ROLES.get(name)
        if declared_roles is not None and set(declared_roles) != set(spec.allowed_roles):
            failures.append(
                f'{name}: registry allowed_roles={sorted(spec.allowed_roles)} 与 '
                f'policies 声明 {sorted(declared_roles)} 不一致'
            )

    if failures:
        print('FAIL AI-TOOL-COMPLIANCE:')
        for failure in failures:
            print(f'  - {failure}')
        return 1

    print(
        f'PASS AI-TOOL-COMPLIANCE: {len(AI_TOOL_REGISTRY)} 个工具权限/风险级别/审计类别均合法，'
        f'三表键一致，草稿级工具均要求人工确认'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
