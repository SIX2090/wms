"""AI-SALES-F02：销售履约跟进 AI 工作台整合。

# AI_TASK: AI-SALES-F02

设计目标（验收：指标口径和时间范围明确；对外沟通和业务提交必须人工确认）：

- 整合 7 类销售履约跟进业务到单一工作台视图：
  1. pending_shipment       待发货（SalesOrder status in (draft,confirmed) 且 shipment_status in (pending,partial) 且 delivery_date >= today）
  2. overdue_shipment        逾期未发货（SalesOrder status in (draft,confirmed) 且 shipment_status in (pending,partial) 且 delivery_date < today）
  3. partial_stalled         部分发货停滞（SalesOrder shipment_status=partial 超 N 天未推进）
  4. short_stock             缺货待核对（SalesOrderItem.quantity > material.stock）
  5. customer_urgency        客户催发货话术（不自动发送，需人工确认）
  6. merge_candidates        多笔订单合并发货候选（同客户+同仓库+相近交期）
  7. customer_followup_list  客户履约/付款汇总（按客户归组的待跟进订单汇总）

- 指标口径和时间范围明确：每个 section 含 metric_scope（指标口径）和 time_range（时间范围）。

- 对外沟通和业务提交必须人工确认：customer_followup_list 的 followup_actions 恒为只读展示，
  催发货话术需 manual_confirmation=True 才能发送（不自动发送）；业务提交（如生成出库草稿）
  需 manual_confirmation=True。WorkbenchSection.read_only 恒 True。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06～R11 一致。
  CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class SalesFollowupItem:
    """跟进卡片单项（如一张销售订单/一条缺货明细/一个客户跟进汇总）。"""

    id: int
    title: str                          # 卡片标题（如 "SO-2026-001"）
    subtitle: str                       # 副标题（如客户名/物料名）
    detail: str                         # 详情（如 "应发 2026-07-15，已逾期 2 天" / "应发 100 已发 80，待发 20"）
    jump_url: str                       # 跳转到该单详情页的 URL
    metric_scope: str = ''              # 该项的指标口径说明
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'subtitle': self.subtitle,
            'detail': self.detail,
            'jump_url': self.jump_url,
            'metric_scope': self.metric_scope,
            'extra': dict(self.extra),
        }


@dataclass(frozen=True)
class SalesFollowupSection:
    """跟进卡片区（一类业务的汇总 + 前 N 条详情）。

    read_only 恒为 True：验收要求"对外沟通和业务提交必须人工确认"。
    metric_scope 和 time_range 明确指标口径和时间范围。
    """

    key: str                            # section 唯一标识
    title: str                          # 中文标题
    count: int                          # 总数（与原业务列表一致）
    items: tuple[SalesFollowupItem, ...]  # 前 N 条详情（默认 5 条）
    jump_url: str                       # 跳转到该业务列表页的 URL
    read_only: bool = True              # 恒为 True（验收约束）
    metric_scope: str = ''              # 指标口径
    time_range: str = ''                # 时间范围
    empty_hint: str = ''                # count=0 时的提示文案

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'title': self.title,
            'count': self.count,
            'items': [i.to_dict() for i in self.items],
            'jump_url': self.jump_url,
            'read_only': self.read_only,
            'metric_scope': self.metric_scope,
            'time_range': self.time_range,
            'empty_hint': self.empty_hint,
        }


@dataclass(frozen=True)
class CustomerFollowupSummary:
    """客户跟进清单单项（按客户归组的待跟进订单汇总）。

    验收要求"客户跟进清单"：每个客户汇总其待发/逾期/缺货订单数 + 催发货话术。
    followup_actions 恒为只读展示，催发货话术需 manual_confirmation=True 才能发送。
    """

    customer_id: int
    customer_name: str
    pending_count: int                  # 待发订单数
    overdue_count: int                  # 逾期订单数
    short_stock_count: int              # 缺货明细数
    followup_suggestion: str            # 催发货话术建议（不自动发送）
    needs_manual_confirmation: bool = True  # 恒为 True（对外沟通必须人工确认）
    jump_url: str = ''                  # 跳转到该客户订单列表

    def to_dict(self) -> dict[str, Any]:
        return {
            'customer_id': self.customer_id,
            'customer_name': self.customer_name,
            'pending_count': self.pending_count,
            'overdue_count': self.overdue_count,
            'short_stock_count': self.short_stock_count,
            'followup_suggestion': self.followup_suggestion,
            'needs_manual_confirmation': self.needs_manual_confirmation,
            'jump_url': self.jump_url,
        }


@dataclass(frozen=True)
class SalesFollowupSnapshot:
    """销售履约跟进工作台快照（含 7 个 section + 客户跟进清单 + 汇总）。"""

    sections: tuple[SalesFollowupSection, ...]
    customer_followup_list: tuple[CustomerFollowupSummary, ...]
    total_attention_count: int          # 需关注总数（待发+逾期+部分停滞+缺货+催发货+合并候选）
    generated_at: str
    user_id: int = 0
    role: str = 'sales'

    def to_dict(self) -> dict[str, Any]:
        return {
            'sections': [s.to_dict() for s in self.sections],
            'customer_followup_list': [s.to_dict() for s in self.customer_followup_list],
            'total_attention_count': self.total_attention_count,
            'generated_at': self.generated_at,
            'user_id': self.user_id,
            'role': self.role,
        }


# ---- 依赖注入回调签名 ----

# 每个 query 回调返回 (count, list[dict]) 二元组
QueryFn = Callable[[], tuple[int, list[dict[str, Any]]]]

# 客户跟进清单查询回调返回 list[CustomerFollowupSummary dict]
QueryCustomerFollowupFn = Callable[[], list[dict[str, Any]]]


# ---- 主构建函数 ----

def build_sales_followup_workbench(
    *,
    query_pending_shipment: Optional[QueryFn] = None,
    query_overdue_shipment: Optional[QueryFn] = None,
    query_partial_stalled: Optional[QueryFn] = None,
    query_short_stock: Optional[QueryFn] = None,
    query_customer_urgency: Optional[QueryFn] = None,
    query_merge_candidates: Optional[QueryFn] = None,
    query_customer_followup_list: Optional[QueryCustomerFollowupFn] = None,
    user_id: int = 0,
    role: str = 'sales',
    now: Optional[str] = None,
) -> SalesFollowupSnapshot:
    """构建销售履约跟进工作台快照。

    Args:
        6 个 section query 回调：每个返回 (count, list[dict])
        1 个 customer_followup_list query 回调：返回 list[dict]
        user_id: 当前用户 ID
        role: 当前角色（默认 sales）
        now: ISO 时间戳

    Returns:
        SalesFollowupSnapshot 含 7 个 section（含客户跟进清单作为第 7 个）

    验收：
    - 指标口径和时间范围明确（每个 section 含 metric_scope + time_range）
    - 对外沟通和业务提交必须人工确认（read_only 恒 True，customer_followup needs_manual_confirmation 恒 True）
    - count 与原业务列表一致（由 query 回调保证）
    """
    timestamp = now or datetime.now().isoformat()

    sections: list[SalesFollowupSection] = []
    total_attention = 0

    # 1. 待发货
    count, items = _safe_query(query_pending_shipment)
    sections.append(SalesFollowupSection(
        key='pending_shipment',
        title='待发货',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?shipment_status=pending',
        metric_scope='status in (draft,confirmed) 且 shipment_status in (pending,partial) 且 delivery_date>=today',
        time_range='未来到期',
        empty_hint='暂无待发货销售订单',
    ))
    total_attention += count

    # 2. 逾期未发货
    count, items = _safe_query(query_overdue_shipment)
    sections.append(SalesFollowupSection(
        key='overdue_shipment',
        title='逾期未发货',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?shipment_status=overdue',
        metric_scope='status in (draft,confirmed) 且 shipment_status in (pending,partial) 且 delivery_date<today',
        time_range='已过期未发货',
        empty_hint='暂无逾期销售订单',
    ))
    total_attention += count

    # 3. 部分发货停滞
    count, items = _safe_query(query_partial_stalled)
    sections.append(SalesFollowupSection(
        key='partial_stalled',
        title='部分发货停滞',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?shipment_status=partial',
        metric_scope='shipment_status=partial 超 N 天未推进',
        time_range='过去 7 天未更新',
        empty_hint='暂无部分发货停滞订单',
    ))
    total_attention += count

    # 4. 缺货待核对
    count, items = _safe_query(query_short_stock)
    sections.append(SalesFollowupSection(
        key='short_stock',
        title='缺货待核对',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?filter=short_stock',
        metric_scope='SalesOrderItem.quantity > Material.stock',
        time_range='全部未关闭订单',
        empty_hint='暂无缺货明细',
    ))
    total_attention += count

    # 5. 客户催发货话术（不自动发送，只读展示）
    count, items = _safe_query(query_customer_urgency)
    sections.append(SalesFollowupSection(
        key='customer_urgency',
        title='客户催发货话术',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?filter=customer_urgency',
        metric_scope='按客户归组的催发货话术建议，需人工确认后发送',
        time_range='最近 7 天逾期订单',
        empty_hint='暂无催发货话术',
    ))
    total_attention += count

    # 6. 多笔订单合并发货候选
    count, items = _safe_query(query_merge_candidates)
    sections.append(SalesFollowupSection(
        key='merge_candidates',
        title='合并发货候选',
        count=count,
        items=_to_items(items),
        jump_url='/sales_order/list?filter=merge_candidates',
        metric_scope='同客户+同仓库+相近交期的多笔订单候选',
        time_range='未来 7 天到期',
        empty_hint='暂无合并发货候选',
    ))
    total_attention += count

    # 7. 客户跟进清单
    customer_list_raw = _safe_query_list(query_customer_followup_list)
    customer_list = _to_customer_summaries(customer_list_raw)
    customer_count = len(customer_list)
    sections.append(SalesFollowupSection(
        key='customer_followup_list',
        title='客户跟进清单',
        count=customer_count,
        items=_customer_summaries_to_items(customer_list),
        jump_url='/sales_order/customer_followup',
        metric_scope='按客户归组的待跟进订单（待发+逾期+缺货）',
        time_range='全部未关闭订单',
        empty_hint='暂无待跟进客户',
    ))
    # 客户跟进清单不直接计入 total_attention（避免与待发/逾期/缺货重复计数）

    return SalesFollowupSnapshot(
        sections=tuple(sections),
        customer_followup_list=tuple(customer_list),
        total_attention_count=total_attention,
        generated_at=timestamp,
        user_id=user_id,
        role=role,
    )


# ---- 辅助函数 ----

def _safe_query(query_fn: Optional[QueryFn]) -> tuple[int, list[dict[str, Any]]]:
    """安全执行 query 回调，异常时返回 (0, [])。"""
    if query_fn is None:
        return 0, []
    try:
        result = query_fn()
        if not isinstance(result, tuple) or len(result) != 2:
            return 0, []
        count, items = result
        if not isinstance(count, int) or count < 0:
            count = 0
        if not isinstance(items, list):
            items = []
        return count, items
    except Exception:
        return 0, []


def _safe_query_list(query_fn: Optional[QueryCustomerFollowupFn]) -> list[dict[str, Any]]:
    """安全执行 list query 回调，异常时返回 []。"""
    if query_fn is None:
        return []
    try:
        result = query_fn()
        if not isinstance(result, list):
            return []
        return result
    except Exception:
        return []


def _to_items(items: list[dict[str, Any]]) -> tuple[SalesFollowupItem, ...]:
    """将 dict 列表转为 SalesFollowupItem 元组。"""
    result: list[SalesFollowupItem] = []
    for d in items:
        if not isinstance(d, dict):
            continue
        result.append(SalesFollowupItem(
            id=int(d.get('id') or 0),
            title=str(d.get('title') or ''),
            subtitle=str(d.get('subtitle') or ''),
            detail=str(d.get('detail') or ''),
            jump_url=str(d.get('jump_url') or ''),
            metric_scope=str(d.get('metric_scope') or ''),
            extra=dict(d.get('extra') or {}),
        ))
    return tuple(result)


def _to_customer_summaries(items: list[dict[str, Any]]) -> list[CustomerFollowupSummary]:
    """将 dict 列表转为 CustomerFollowupSummary 列表。"""
    result: list[CustomerFollowupSummary] = []
    for d in items:
        if not isinstance(d, dict):
            continue
        result.append(CustomerFollowupSummary(
            customer_id=int(d.get('customer_id') or 0),
            customer_name=str(d.get('customer_name') or ''),
            pending_count=int(d.get('pending_count') or 0),
            overdue_count=int(d.get('overdue_count') or 0),
            short_stock_count=int(d.get('short_stock_count') or 0),
            followup_suggestion=str(d.get('followup_suggestion') or ''),
            needs_manual_confirmation=bool(d.get('needs_manual_confirmation', True)),
            jump_url=str(d.get('jump_url') or ''),
        ))
    return result


def _customer_summaries_to_items(summaries: list[CustomerFollowupSummary]) -> tuple[SalesFollowupItem, ...]:
    """将 CustomerFollowupSummary 列表转为 SalesFollowupItem 元组（用于 section.items 展示）。"""
    result: list[SalesFollowupItem] = []
    for s in summaries:
        result.append(SalesFollowupItem(
            id=s.customer_id,
            title=s.customer_name or f'客户#{s.customer_id}',
            subtitle=f'待发 {s.pending_count} / 逾期 {s.overdue_count} / 缺货 {s.short_stock_count}',
            detail=s.followup_suggestion,
            jump_url=s.jump_url,
            metric_scope='按客户归组的待跟进订单',
            extra={
                'customer_id': s.customer_id,
                'pending_count': s.pending_count,
                'overdue_count': s.overdue_count,
                'short_stock_count': s.short_stock_count,
                'needs_manual_confirmation': s.needs_manual_confirmation,
            },
        ))
    return tuple(result)


# ---- 验收校验 ----

def validate_followup_read_only(snapshot: SalesFollowupSnapshot) -> tuple[bool, list[str]]:
    """校验工作台快照满足"只读或跳转"约束。

    验收要求："对外沟通和业务提交必须人工确认"。
    检查：
    - 每个 section.read_only == True
    - 每个 item.jump_url 不含 send/submit/audit/delete/void/complete 等写动作
    - 每个 customer_followup needs_manual_confirmation == True
    """
    violations: list[str] = []
    forbidden_actions = ('send', 'submit', 'audit', 'delete', 'void', 'complete', 'confirm_post', 'cancel', 'auto_dispatch')

    for section in snapshot.sections:
        if not section.read_only:
            violations.append(f'section {section.key} read_only=False（应为 True）')
        for item in section.items:
            url_lower = (item.jump_url or '').lower()
            for action in forbidden_actions:
                if action in url_lower:
                    violations.append(
                        f'section {section.key} item {item.id} jump_url 含写动作 {action}: {item.jump_url}'
                    )

    for s in snapshot.customer_followup_list:
        if not s.needs_manual_confirmation:
            violations.append(
                f'客户 {s.customer_name} needs_manual_confirmation=False（对外沟通必须人工确认）'
            )

    return len(violations) == 0, violations


def validate_metric_scope_clear(snapshot: SalesFollowupSnapshot) -> tuple[bool, list[str]]:
    """校验各 section 指标口径和时间范围明确。

    验收要求："指标口径和时间范围明确"。
    """
    violations: list[str] = []
    for section in snapshot.sections:
        if not section.metric_scope:
            violations.append(f'section {section.key} metric_scope 为空（指标口径不明确）')
        if not section.time_range:
            violations.append(f'section {section.key} time_range 为空（时间范围不明确）')
    return len(violations) == 0, violations


def validate_count_consistency(
    snapshot: SalesFollowupSnapshot,
    *,
    expected_counts: dict[str, int],
) -> tuple[bool, list[str]]:
    """校验工作台各 section 的 count 与原业务列表一致。

    验收要求："数量与原业务列表一致"（与 AI-R10/R11 一致）。
    """
    mismatches: list[str] = []
    actual = {s.key: s.count for s in snapshot.sections}
    for key, expected in expected_counts.items():
        actual_count = actual.get(key)
        if actual_count is None:
            mismatches.append(f'section {key} 不存在于工作台')
        elif actual_count != expected:
            mismatches.append(
                f'section {key} count 不一致：工作台={actual_count} 原业务列表={expected}'
            )
    return len(mismatches) == 0, mismatches
