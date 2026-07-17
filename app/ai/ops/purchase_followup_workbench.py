"""AI-R11：采购到货跟进 AI 工作台整合。

# AI_TASK: AI-R11

设计目标（验收：指标口径和时间范围明确；对外沟通和业务提交必须人工确认）：

- 整合 7 类采购到货跟进业务到单一工作台视图：
  1. pending_arrival        待到（PurchaseOrder status in pending/partial 且 expected_date >= today）
  2. delayed_arrival        延期（PurchaseOrder status in pending/partial 且 expected_date < today）
  3. short_delivery         短交（PurchaseOrderItem received_quantity < quantity）
  4. over_receive           超收（PurchaseOrderItem received_quantity > quantity）
  5. unlinked_notices       未关联通知（AIDocumentJob 含送货通知但 source_purchase_order_id 为空）
  6. multi_order_candidates 多订单候选（AI-R06 delivery_match 多候选未自动选单）
  7. supplier_followup_list 供应商跟进清单（按供应商归组的待跟进订单汇总）

- 指标口径和时间范围明确：每个 section 含 metric_scope（指标口径）和 time_range（时间范围），
  如待到="expected_date>=today 且 status in pending/partial"，延期="expected_date<today 且 status in pending/partial"。

- 对外沟通和业务提交必须人工确认：supplier_followup_list 的 followup_actions 恒为只读展示，
  催交话术需 manual_confirmation=True 才能发送（不自动发送）；业务提交（如创建入库单）
  需 manual_confirmation=True。WorkbenchSection.read_only 恒 True。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06～R10 一致。
  CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class FollowupItem:
    """跟进卡片单项（如一张采购订单/一条短交明细/一个供应商跟进汇总）。"""

    id: int
    title: str                          # 卡片标题（如 "PO-2026-001"）
    subtitle: str                       # 副标题（如供应商名/物料名）
    detail: str                         # 详情（如 "应到 2026-07-15，已延期 2 天" / "应到 100 已到 80，短交 20"）
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
class FollowupSection:
    """跟进卡片区（一类业务的汇总 + 前 N 条详情）。

    read_only 恒为 True：验收要求"对外沟通和业务提交必须人工确认"。
    metric_scope 和 time_range 明确指标口径和时间范围。
    """

    key: str                            # section 唯一标识
    title: str                          # 中文标题
    count: int                          # 总数（与原业务列表一致）
    items: tuple[FollowupItem, ...]     # 前 N 条详情（默认 5 条）
    jump_url: str                       # 跳转到该业务列表页的 URL
    read_only: bool = True              # 恒为 True（验收约束）
    metric_scope: str = ''              # 指标口径（如 "expected_date>=today 且 status in pending/partial"）
    time_range: str = ''                # 时间范围（如 "未来 7 天" / "过去 30 天"）
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
class SupplierFollowupSummary:
    """供应商跟进清单单项（按供应商归组的待跟进订单汇总）。

    验收要求"供应商跟进清单"：每个供应商汇总其待到/延期/短交订单数 + 催交话术。
    followup_actions 恒为只读展示，催交话术需 manual_confirmation=True 才能发送。
    """

    supplier_id: int
    supplier_name: str
    pending_count: int                  # 待到订单数
    delayed_count: int                  # 延期订单数
    short_delivery_count: int           # 短交明细数
    followup_suggestion: str            # 催交话术建议（不自动发送）
    needs_manual_confirmation: bool = True  # 恒为 True（对外沟通必须人工确认）
    jump_url: str = ''                  # 跳转到该供应商订单列表

    def to_dict(self) -> dict[str, Any]:
        return {
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier_name,
            'pending_count': self.pending_count,
            'delayed_count': self.delayed_count,
            'short_delivery_count': self.short_delivery_count,
            'followup_suggestion': self.followup_suggestion,
            'needs_manual_confirmation': self.needs_manual_confirmation,
            'jump_url': self.jump_url,
        }


@dataclass(frozen=True)
class PurchaseFollowupSnapshot:
    """采购到货跟进工作台快照（含 7 个 section + 供应商跟进清单 + 汇总）。"""

    sections: tuple[FollowupSection, ...]
    supplier_followup_list: tuple[SupplierFollowupSummary, ...]
    total_attention_count: int          # 需关注总数（待到+延期+短交+超收+未关联+多候选）
    generated_at: str
    user_id: int = 0
    role: str = 'purchase'

    def to_dict(self) -> dict[str, Any]:
        return {
            'sections': [s.to_dict() for s in self.sections],
            'supplier_followup_list': [s.to_dict() for s in self.supplier_followup_list],
            'total_attention_count': self.total_attention_count,
            'generated_at': self.generated_at,
            'user_id': self.user_id,
            'role': self.role,
        }


# ---- 依赖注入回调签名 ----

# 每个 query 回调返回 (count, list[dict]) 二元组
QueryFn = Callable[[], tuple[int, list[dict[str, Any]]]]

# 供应商跟进清单查询回调返回 list[SupplierFollowupSummary dict]
QuerySupplierFollowupFn = Callable[[], list[dict[str, Any]]]


# ---- 主构建函数 ----

def build_purchase_followup_workbench(
    *,
    query_pending_arrival: Optional[QueryFn] = None,
    query_delayed_arrival: Optional[QueryFn] = None,
    query_short_delivery: Optional[QueryFn] = None,
    query_over_receive: Optional[QueryFn] = None,
    query_unlinked_notices: Optional[QueryFn] = None,
    query_multi_order_candidates: Optional[QueryFn] = None,
    query_supplier_followup_list: Optional[QuerySupplierFollowupFn] = None,
    user_id: int = 0,
    role: str = 'purchase',
    now: Optional[str] = None,
) -> PurchaseFollowupSnapshot:
    """构建采购到货跟进工作台快照。

    Args:
        6 个 section query 回调：每个返回 (count, list[dict])
        1 个 supplier_followup_list query 回调：返回 list[dict]
        user_id: 当前用户 ID
        role: 当前角色（默认 purchase）
        now: ISO 时间戳

    Returns:
        PurchaseFollowupSnapshot 含 7 个 section（含供应商跟进清单作为第 7 个）

    验收：
    - 指标口径和时间范围明确（每个 section 含 metric_scope + time_range）
    - 对外沟通和业务提交必须人工确认（read_only 恒 True，supplier_followup needs_manual_confirmation 恒 True）
    - count 与原业务列表一致（由 query 回调保证）
    """
    timestamp = now or datetime.now().isoformat()

    sections: list[FollowupSection] = []
    total_attention = 0

    # 1. 待到
    count, items = _safe_query(query_pending_arrival)
    sections.append(FollowupSection(
        key='pending_arrival',
        title='待到货',
        count=count,
        items=_to_items(items),
        jump_url='/purchase_order/list?status=pending',
        metric_scope='expected_date>=today 且 status in (pending,partial)',
        time_range='未来到期',
        empty_hint='暂无待到货采购订单',
    ))
    total_attention += count

    # 2. 延期
    count, items = _safe_query(query_delayed_arrival)
    sections.append(FollowupSection(
        key='delayed_arrival',
        title='延期到货',
        count=count,
        items=_to_items(items),
        jump_url='/purchase_order/list?status=delayed',
        metric_scope='expected_date<today 且 status in (pending,partial)',
        time_range='已过期未到货',
        empty_hint='暂无延期采购订单',
    ))
    total_attention += count

    # 3. 短交
    count, items = _safe_query(query_short_delivery)
    sections.append(FollowupSection(
        key='short_delivery',
        title='短交明细',
        count=count,
        items=_to_items(items),
        jump_url='/purchase_order/list?filter=short_delivery',
        metric_scope='PurchaseOrderItem.received_quantity < quantity',
        time_range='全部在途订单',
        empty_hint='暂无短交明细',
    ))
    total_attention += count

    # 4. 超收
    count, items = _safe_query(query_over_receive)
    sections.append(FollowupSection(
        key='over_receive',
        title='超收明细',
        count=count,
        items=_to_items(items),
        jump_url='/purchase_order/list?filter=over_receive',
        metric_scope='PurchaseOrderItem.received_quantity > quantity',
        time_range='全部在途订单',
        empty_hint='暂无超收明细',
    ))
    total_attention += count

    # 5. 未关联通知
    count, items = _safe_query(query_unlinked_notices)
    sections.append(FollowupSection(
        key='unlinked_notices',
        title='未关联通知',
        count=count,
        items=_to_items(items),
        jump_url='/ai/document_jobs?filter=unlinked_notice',
        metric_scope='AIDocumentJob 含送货通知但 source_purchase_order_id 为空',
        time_range='最近 7 天',
        empty_hint='暂无未关联送货通知',
    ))
    total_attention += count

    # 6. 多订单候选
    count, items = _safe_query(query_multi_order_candidates)
    sections.append(FollowupSection(
        key='multi_order_candidates',
        title='多订单候选',
        count=count,
        items=_to_items(items),
        jump_url='/ai/document_jobs?filter=multi_candidate',
        metric_scope='AI-R06 delivery_match 多候选未自动选单',
        time_range='最近 7 天',
        empty_hint='暂无多订单候选',
    ))
    total_attention += count

    # 7. 供应商跟进清单
    supplier_list_raw = _safe_query_list(query_supplier_followup_list)
    supplier_list = _to_supplier_summaries(supplier_list_raw)
    supplier_count = len(supplier_list)
    sections.append(FollowupSection(
        key='supplier_followup_list',
        title='供应商跟进清单',
        count=supplier_count,
        items=_supplier_summaries_to_items(supplier_list),
        jump_url='/purchase_order/supplier_followup',
        metric_scope='按供应商归组的待跟进订单（待到+延期+短交）',
        time_range='全部在途订单',
        empty_hint='暂无待跟进供应商',
    ))
    # 供应商跟进清单不直接计入 total_attention（避免与待到/延期/短交重复计数）

    return PurchaseFollowupSnapshot(
        sections=tuple(sections),
        supplier_followup_list=tuple(supplier_list),
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


def _safe_query_list(query_fn: Optional[QuerySupplierFollowupFn]) -> list[dict[str, Any]]:
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


def _to_items(items: list[dict[str, Any]]) -> tuple[FollowupItem, ...]:
    """将 dict 列表转为 FollowupItem 元组。"""
    result: list[FollowupItem] = []
    for d in items:
        if not isinstance(d, dict):
            continue
        result.append(FollowupItem(
            id=int(d.get('id') or 0),
            title=str(d.get('title') or ''),
            subtitle=str(d.get('subtitle') or ''),
            detail=str(d.get('detail') or ''),
            jump_url=str(d.get('jump_url') or ''),
            metric_scope=str(d.get('metric_scope') or ''),
            extra=dict(d.get('extra') or {}),
        ))
    return tuple(result)


def _to_supplier_summaries(items: list[dict[str, Any]]) -> list[SupplierFollowupSummary]:
    """将 dict 列表转为 SupplierFollowupSummary 列表。"""
    result: list[SupplierFollowupSummary] = []
    for d in items:
        if not isinstance(d, dict):
            continue
        result.append(SupplierFollowupSummary(
            supplier_id=int(d.get('supplier_id') or 0),
            supplier_name=str(d.get('supplier_name') or ''),
            pending_count=int(d.get('pending_count') or 0),
            delayed_count=int(d.get('delayed_count') or 0),
            short_delivery_count=int(d.get('short_delivery_count') or 0),
            followup_suggestion=str(d.get('followup_suggestion') or ''),
            needs_manual_confirmation=bool(d.get('needs_manual_confirmation', True)),
            jump_url=str(d.get('jump_url') or ''),
        ))
    return result


def _supplier_summaries_to_items(summaries: list[SupplierFollowupSummary]) -> tuple[FollowupItem, ...]:
    """将 SupplierFollowupSummary 列表转为 FollowupItem 元组（用于 section.items 展示）。"""
    result: list[FollowupItem] = []
    for s in summaries:
        result.append(FollowupItem(
            id=s.supplier_id,
            title=s.supplier_name or f'供应商#{s.supplier_id}',
            subtitle=f'待到 {s.pending_count} / 延期 {s.delayed_count} / 短交 {s.short_delivery_count}',
            detail=s.followup_suggestion,
            jump_url=s.jump_url,
            metric_scope='按供应商归组的待跟进订单',
            extra={
                'supplier_id': s.supplier_id,
                'pending_count': s.pending_count,
                'delayed_count': s.delayed_count,
                'short_delivery_count': s.short_delivery_count,
                'needs_manual_confirmation': s.needs_manual_confirmation,
            },
        ))
    return tuple(result)


# ---- 验收校验 ----

def validate_followup_read_only(snapshot: PurchaseFollowupSnapshot) -> tuple[bool, list[str]]:
    """校验工作台快照满足"只读或跳转"约束。

    验收要求："对外沟通和业务提交必须人工确认"。
    检查：
    - 每个 section.read_only == True
    - 每个 item.jump_url 不含 send/submit/audit/delete/void/complete 等写动作
    - 每个 supplier_followup needs_manual_confirmation == True
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

    for s in snapshot.supplier_followup_list:
        if not s.needs_manual_confirmation:
            violations.append(
                f'供应商 {s.supplier_name} needs_manual_confirmation=False（对外沟通必须人工确认）'
            )

    return len(violations) == 0, violations


def validate_metric_scope_clear(snapshot: PurchaseFollowupSnapshot) -> tuple[bool, list[str]]:
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
    snapshot: PurchaseFollowupSnapshot,
    *,
    expected_counts: dict[str, int],
) -> tuple[bool, list[str]]:
    """校验工作台各 section 的 count 与原业务列表一致。

    验收要求："数量与原业务列表一致"（与 AI-R10 一致）。
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
