"""AI-R10：仓库角色 AI 工作台整合。

# AI_TASK: AI-R10

设计目标（验收：数量与原业务列表一致；工作台只读或跳转对应流程，
不在报表卡片中直接提交或审核）：

- 整合 7 类仓库业务到单一工作台视图：
  1. today_inbound_pending  今日待收（InOrder status=pending）
  2. today_outbound_pending 今日待出（OutOrder status=pending）
  3. inventory_check_pending 待盘（InventoryCheck status=pending）
  4. abnormal_stock         异常库存（负库存 + 低库存）
  5. documents_pending_confirmation 文档待确认（AIDocumentJob status=pending_confirmation）
  6. failed_tasks           失败任务（AIDocumentJob status=failed + AIRun status=failed）
  7. unfinished_drafts      未完成草稿（AIDraftIdempotency status=processing）

- 数量与原业务列表一致：每个 section 的 count 由调用方注入的 query 回调返回，
  回调必须返回与原业务列表完全一致的计数（如 InOrder.query.filter_by(status='pending').count()）。

- 只读或跳转：每个 section 强制 read_only=True，仅展示卡片摘要 + jump_url 跳转链接，
  不含任何提交/审核/删除动作。jump_url 指向对应业务流程页面（如 /in_order/list）。

- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06/R07/R08/R09 一致。
  CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ---- 数据结构（纯 dataclass，不依赖 ORM）----

@dataclass(frozen=True)
class WorkbenchItem:
    """工作台卡片单项（如一张入库单/出库单/文档任务的摘要）。"""

    id: int
    title: str                          # 卡片标题（如 "RK202607170001"）
    subtitle: str                       # 副标题（如供应商名/部门名/物料名）
    detail: str                         # 详情（如 "3 项物料" / "负库存 -5"）
    jump_url: str                       # 跳转到该单详情页的 URL
    extra: dict[str, Any] = field(default_factory=dict)  # 额外字段（如 severity/created_at）

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'subtitle': self.subtitle,
            'detail': self.detail,
            'jump_url': self.jump_url,
            'extra': dict(self.extra),
        }


@dataclass(frozen=True)
class WorkbenchSection:
    """工作台卡片区（一类业务的汇总 + 前 N 条详情）。

    read_only 恒为 True：验收要求"工作台只读或跳转对应流程，
    不在报表卡片中直接提交或审核"。
    """

    key: str                            # section 唯一标识
    title: str                          # 中文标题
    count: int                          # 总数（与原业务列表一致）
    items: tuple[WorkbenchItem, ...]    # 前 N 条详情（默认 5 条）
    jump_url: str                       # 跳转到该业务列表页的 URL
    read_only: bool = True              # 恒为 True（验收约束）
    empty_hint: str = ''                # count=0 时的提示文案

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'title': self.title,
            'count': self.count,
            'items': [i.to_dict() for i in self.items],
            'jump_url': self.jump_url,
            'read_only': self.read_only,
            'empty_hint': self.empty_hint,
        }


@dataclass(frozen=True)
class WarehouseWorkbenchSnapshot:
    """仓库角色工作台快照（含 7 个 section + 汇总）。"""

    sections: tuple[WorkbenchSection, ...]
    total_pending_count: int            # 所有待处理项总数（待收+待出+待盘+文档待确认+失败任务+未完成草稿）
    abnormal_stock_count: int           # 异常库存数（单独统计，不计入 total_pending_count）
    generated_at: str
    user_id: int = 0
    role: str = 'warehouse'

    def to_dict(self) -> dict[str, Any]:
        return {
            'sections': [s.to_dict() for s in self.sections],
            'total_pending_count': self.total_pending_count,
            'abnormal_stock_count': self.abnormal_stock_count,
            'generated_at': self.generated_at,
            'user_id': self.user_id,
            'role': self.role,
        }


# ---- 依赖注入回调签名 ----

# 每个 query 回调返回 (count, list[dict]) 二元组：
#   - count: 该类业务的总数（与原业务列表一致）
#   - list[dict]: 前 N 条详情，每项含 id/title/subtitle/detail/jump_url/extra
# 生产环境由 app.py 提供 ORM adapter；CI 无 DB 时传 mock。
QueryFn = Callable[[], tuple[int, list[dict[str, Any]]]]


# ---- 主构建函数 ----

def build_warehouse_workbench(
    *,
    query_today_inbound_pending: Optional[QueryFn] = None,
    query_today_outbound_pending: Optional[QueryFn] = None,
    query_inventory_check_pending: Optional[QueryFn] = None,
    query_abnormal_stock: Optional[QueryFn] = None,
    query_documents_pending_confirmation: Optional[QueryFn] = None,
    query_failed_tasks: Optional[QueryFn] = None,
    query_unfinished_drafts: Optional[QueryFn] = None,
    user_id: int = 0,
    role: str = 'warehouse',
    now: Optional[str] = None,
) -> WarehouseWorkbenchSnapshot:
    """构建仓库角色工作台快照。

    Args:
        7 个 query 回调：每个返回 (count, list[dict])；None 时该 section count=0 items=()
        user_id: 当前用户 ID
        role: 当前角色（默认 warehouse）
        now: ISO 时间戳

    Returns:
        WarehouseWorkbenchSnapshot 含 7 个 section

    验收：
    - count 与原业务列表一致（由 query 回调保证）
    - read_only 恒 True（不直接提交/审核）
    - 每个 section 含 jump_url 跳转到对应业务流程
    """
    timestamp = now or datetime.now().isoformat()

    sections: list[WorkbenchSection] = []
    total_pending = 0

    # 1. 今日待收
    count, items = _safe_query(query_today_inbound_pending)
    sections.append(WorkbenchSection(
        key='today_inbound_pending',
        title='今日待收',
        count=count,
        items=_to_items(items),
        jump_url='/in_order/list',
        empty_hint='暂无待收入库单',
    ))
    total_pending += count

    # 2. 今日待出
    count, items = _safe_query(query_today_outbound_pending)
    sections.append(WorkbenchSection(
        key='today_outbound_pending',
        title='今日待出',
        count=count,
        items=_to_items(items),
        jump_url='/out_order/list',
        empty_hint='暂无待出出库单',
    ))
    total_pending += count

    # 3. 待盘
    count, items = _safe_query(query_inventory_check_pending)
    sections.append(WorkbenchSection(
        key='inventory_check_pending',
        title='待盘点',
        count=count,
        items=_to_items(items),
        jump_url='/inventory_check/list',
        empty_hint='暂无待盘点单',
    ))
    total_pending += count

    # 4. 异常库存（单独统计，不计入 total_pending）
    count, items = _safe_query(query_abnormal_stock)
    abnormal_count = count
    sections.append(WorkbenchSection(
        key='abnormal_stock',
        title='异常库存',
        count=count,
        items=_to_items(items),
        jump_url='/material/list?filter=abnormal',
        empty_hint='暂无异常库存',
    ))

    # 5. 文档待确认
    count, items = _safe_query(query_documents_pending_confirmation)
    sections.append(WorkbenchSection(
        key='documents_pending_confirmation',
        title='文档待确认',
        count=count,
        items=_to_items(items),
        jump_url='/ai/document_jobs?status=pending_confirmation',
        empty_hint='暂无待确认文档',
    ))
    total_pending += count

    # 6. 失败任务
    count, items = _safe_query(query_failed_tasks)
    sections.append(WorkbenchSection(
        key='failed_tasks',
        title='失败任务',
        count=count,
        items=_to_items(items),
        jump_url='/ai/document_jobs?status=failed',
        empty_hint='暂无失败任务',
    ))
    total_pending += count

    # 7. 未完成草稿
    count, items = _safe_query(query_unfinished_drafts)
    sections.append(WorkbenchSection(
        key='unfinished_drafts',
        title='未完成草稿',
        count=count,
        items=_to_items(items),
        jump_url='/ai/drafts?status=processing',
        empty_hint='暂无未完成草稿',
    ))
    total_pending += count

    return WarehouseWorkbenchSnapshot(
        sections=tuple(sections),
        total_pending_count=total_pending,
        abnormal_stock_count=abnormal_count,
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


def _to_items(items: list[dict[str, Any]]) -> tuple[WorkbenchItem, ...]:
    """将 dict 列表转为 WorkbenchItem 元组。"""
    result: list[WorkbenchItem] = []
    for d in items:
        if not isinstance(d, dict):
            continue
        result.append(WorkbenchItem(
            id=int(d.get('id') or 0),
            title=str(d.get('title') or ''),
            subtitle=str(d.get('subtitle') or ''),
            detail=str(d.get('detail') or ''),
            jump_url=str(d.get('jump_url') or ''),
            extra=dict(d.get('extra') or {}),
        ))
    return tuple(result)


# ---- 验收校验：确认工作台不包含任何写操作 ----

def validate_workbench_read_only(snapshot: WarehouseWorkbenchSnapshot) -> tuple[bool, list[str]]:
    """校验工作台快照满足"只读或跳转"约束。

    验收要求："工作台只读或跳转对应流程，不在报表卡片中直接提交或审核"。
    检查：
    - 每个 section.read_only == True
    - 每个 item.jump_url 是只读跳转（不含 submit/audit/delete/void/complete 等写动作路径）

    Returns:
        (is_valid, violations)
    """
    violations: list[str] = []
    forbidden_actions = ('submit', 'audit', 'delete', 'void', 'complete', 'confirm_post', 'cancel')

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

    return len(violations) == 0, violations


# ---- 验收校验：确认 count 与原业务列表一致 ----

def validate_count_consistency(
    snapshot: WarehouseWorkbenchSnapshot,
    *,
    expected_counts: dict[str, int],
) -> tuple[bool, list[str]]:
    """校验工作台各 section 的 count 与原业务列表一致。

    验收要求："数量与原业务列表一致"。
    调用方传入原业务列表的期望 count（如 {'today_inbound_pending': 5, ...}），
    本函数对比 snapshot 中各 section.count 是否匹配。

    Returns:
        (is_valid, mismatches)
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
