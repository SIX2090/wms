"""AI-R12：知识库发布、版本和失效管理。

# AI_TASK: AI-R12

范围：知识草稿、审核、发布、失效、版本、来源、更新时间、发布人、检索权限和回滚。

设计：
- 纯逻辑 + 依赖注入：不依赖 Flask/ORM，与 AI-R06/R07/R08/R09/R10/R11 一致。
- CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter。
- 知识条目状态机：draft → in_review → published → deprecated → archived。
- 版本管理：同 knowledge_key 可有多版本，published 状态同 key 唯一。
- 检索权限：按角色限制可见范围，未发布内容不可检索。
- 回答显示来源和更新时间。
- 实时库存问题路由到实时数据工具，不混入知识库回答。

验收：
1. 未发布内容不可检索。
2. 回答显示来源和更新时间。
3. 实时库存问题必须使用实时数据工具。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional


# ===== 状态常量 =====

STATUS_DRAFT = 'draft'              # 草稿：创建中，不可检索
STATUS_IN_REVIEW = 'in_review'      # 待审核：提交审核，仍不可检索
STATUS_PUBLISHED = 'published'      # 已发布：可检索，同 key 唯一
STATUS_DEPRECATED = 'deprecated'    # 已失效：旧版本标记失效，不可检索
STATUS_ARCHIVED = 'archived'        # 已归档：历史版本，不可检索

RETRIEVABLE_STATUSES = (STATUS_PUBLISHED,)
WRITE_BLOCKED_STATUSES = (STATUS_PUBLISHED, STATUS_DEPRECATED, STATUS_ARCHIVED)

# 实时数据关键词：命中时必须路由到实时数据工具，不能仅用知识库回答
REALTIME_KEYWORDS = (
    '库存', '数量', '余额', '当前', '现在', '今天', '实时', '剩余',
    'stock', 'quantity', 'balance', 'current', 'now', 'today', 'realtime',
    '可用', '在途', '在制', '已收', '已发', '未收', '未发',
)

# 默认角色权限：admin 全部可见，其他角色需显式 allowed_roles 包含
DEFAULT_ADMIN_ROLE = 'admin'


# ===== 数据结构 =====

@dataclass(frozen=True)
class KnowledgeVersion:
    """知识版本记录（纯数据，对应 ORM AIKnowledgeVersion 行）。"""

    id: int
    knowledge_key: str               # 知识唯一 key，同 key 多版本
    version: int                     # 版本号，从 1 递增
    title: str
    summary: str
    content: str
    rule: str
    page_endpoint: str
    page_label: str
    keywords: tuple[str, ...]
    source: str                      # 来源：manual/system/imported/ai_generated
    status: str                      # 状态：draft/in_review/published/deprecated/archived
    allowed_roles: tuple[str, ...]   # 检索权限：哪些角色可见，空表示全部可见
    published_by: Optional[int]      # 发布人 user_id
    published_at: Optional[str]      # 发布时间 ISO8601
    updated_at: str                  # 更新时间 ISO8601
    created_at: str                  # 创建时间 ISO8601
    superseded_by: Optional[int]     # 被哪个版本替代（回滚/失效追溯）
    data_boundary: str = '知识库只解释规则和入口；库存、单据、金额和数量必须实时查询数据库。'

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'knowledge_key': self.knowledge_key,
            'version': self.version,
            'title': self.title,
            'summary': self.summary,
            'content': self.content,
            'rule': self.rule,
            'page_endpoint': self.page_endpoint,
            'page_label': self.page_label,
            'keywords': list(self.keywords),
            'source': self.source,
            'status': self.status,
            'allowed_roles': list(self.allowed_roles),
            'published_by': self.published_by,
            'published_at': self.published_at,
            'updated_at': self.updated_at,
            'created_at': self.created_at,
            'superseded_by': self.superseded_by,
            'data_boundary': self.data_boundary,
        }


@dataclass(frozen=True)
class KnowledgeRetrievalResult:
    """检索结果（含来源和更新时间，满足验收2）。"""

    entry: KnowledgeVersion
    score: int
    source: str                      # 来源标签：知识库版本 vX / 实时数据工具
    updated_at: str
    needs_realtime_tool: bool        # 是否需要路由到实时数据工具

    def to_dict(self) -> dict[str, Any]:
        return {
            'entry': self.entry.to_dict(),
            'score': self.score,
            'source': self.source,
            'updated_at': self.updated_at,
            'needs_realtime_tool': self.needs_realtime_tool,
        }


@dataclass(frozen=True)
class KnowledgePublishResult:
    """发布操作结果。"""

    success: bool
    published_version: Optional[KnowledgeVersion]
    superseded_version: Optional[KnowledgeVersion]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'published_version': self.published_version.to_dict() if self.published_version else None,
            'superseded_version': self.superseded_version.to_dict() if self.superseded_version else None,
            'reason': self.reason,
        }


@dataclass(frozen=True)
class KnowledgeRollbackResult:
    """回滚操作结果。"""

    success: bool
    active_version: Optional[KnowledgeVersion]
    deactivated_version: Optional[KnowledgeVersion]
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'success': self.success,
            'active_version': self.active_version.to_dict() if self.active_version else None,
            'deactivated_version': self.deactivated_version.to_dict() if self.deactivated_version else None,
            'reason': self.reason,
        }


# ===== 依赖注入回调类型 =====

SaveVersionFn = Callable[[dict[str, Any]], KnowledgeVersion]
UpdateVersionStatusFn = Callable[[int, str, Optional[int], Optional[str], Optional[int]], KnowledgeVersion]
QueryVersionsFn = Callable[..., list[KnowledgeVersion]]
QueryPublishedByKeyFn = Callable[[str], Optional[KnowledgeVersion]]


# ===== 核心逻辑 =====

def is_realtime_question(message: str) -> bool:
    """判断问题是否需要实时数据工具（验收3）。

    命中实时关键词的问题必须路由到实时数据工具，不能仅用知识库回答。
    """
    compact = (message or '').replace(' ', '').lower()
    if not compact:
        return False
    for keyword in REALTIME_KEYWORDS:
        if keyword.lower() in compact:
            return True
    return False


def is_retrievable(version: KnowledgeVersion) -> bool:
    """判断版本是否可检索（验收1：未发布内容不可检索）。"""
    return version.status in RETRIEVABLE_STATUSES


def is_visible_to_role(version: KnowledgeVersion, role: str) -> bool:
    """判断版本对角色是否可见（检索权限）。

    allowed_roles 为空表示全部可见；admin 始终可见。
    """
    if not version.allowed_roles:
        return True
    if role == DEFAULT_ADMIN_ROLE:
        return True
    return role in version.allowed_roles


def search_published_knowledge(
    message: str,
    *,
    role: str = DEFAULT_ADMIN_ROLE,
    query_published: Optional[QueryVersionsFn] = None,
    limit: int = 4,
) -> list[KnowledgeRetrievalResult]:
    """检索已发布知识（验收1+2）。

    - 仅检索 status=published 的版本，未发布内容不可检索。
    - 按角色过滤可见范围。
    - 返回结果含 source 和 updated_at。
    - 命中实时关键词的问题标记 needs_realtime_tool=True，但不阻止知识检索（SOP 类问题可能同时需要规则和实时数据）。
    """
    compact = (message or '').replace(' ', '').lower()
    if not compact:
        return []

    needs_realtime = is_realtime_question(message)

    published_versions: list[KnowledgeVersion] = []
    if query_published is not None:
        try:
            published_versions = list(query_published() or [])
        except Exception:
            published_versions = []

    # 验收1：未发布内容不可检索
    published_versions = [v for v in published_versions if is_retrievable(v)]
    # 检索权限：按角色过滤
    published_versions = [v for v in published_versions if is_visible_to_role(v, role)]

    scored: list[tuple[int, KnowledgeVersion]] = []
    for version in published_versions:
        score = _score_version(version, compact)
        if score > 0:
            scored.append((score, version))

    scored.sort(key=lambda row: (row[0], row[1].knowledge_key, row[1].version), reverse=True)

    results: list[KnowledgeRetrievalResult] = []
    for score, version in scored[:limit]:
        results.append(KnowledgeRetrievalResult(
            entry=version,
            score=score,
            source=f'知识库版本 v{version.version}',
            updated_at=version.updated_at,
            needs_realtime_tool=needs_realtime,
        ))
    return results


def _score_version(version: KnowledgeVersion, compact: str) -> int:
    """关键词评分。"""
    score = 0
    for keyword in version.keywords:
        normalized = keyword.replace(' ', '').lower()
        if normalized and normalized in compact:
            score += max(1, len(normalized))
    # 标题命中加权
    title_compact = version.title.replace(' ', '').lower()
    if title_compact and title_compact in compact:
        score += max(2, len(title_compact))
    return score


def publish_knowledge_version(
    version: KnowledgeVersion,
    *,
    published_by: int,
    published_at: str,
    update_status: UpdateVersionStatusFn,
    query_published_by_key: Optional[QueryPublishedByKeyFn] = None,
) -> KnowledgePublishResult:
    """发布知识版本（同 key published 唯一）。

    - 若同 key 已有 published 版本，旧版本标记为 deprecated，superseded_by 指向新版本。
    - draft/in_review 状态可发布；published/deprecated/archived 状态不可重复发布。
    """
    if version.status in WRITE_BLOCKED_STATUSES:
        return KnowledgePublishResult(
            success=False,
            published_version=None,
            superseded_version=None,
            reason=f'版本状态为 {version.status}，不可重复发布',
        )

    # 查找同 key 已发布版本
    superseded: Optional[KnowledgeVersion] = None
    if query_published_by_key is not None:
        try:
            superseded = query_published_by_key(version.knowledge_key)
        except Exception:
            superseded = None

    # 旧版本标记 deprecated
    if superseded is not None and superseded.id != version.id and superseded.status == STATUS_PUBLISHED:
        try:
            update_status(
                superseded.id,
                STATUS_DEPRECATED,
                None,
                None,
                version.id,
            )
        except Exception:
            pass

    # 新版本标记 published
    try:
        published_version = update_status(
            version.id,
            STATUS_PUBLISHED,
            published_by,
            published_at,
            None,
        )
    except Exception as exc:
        return KnowledgePublishResult(
            success=False,
            published_version=None,
            superseded_version=superseded,
            reason=f'发布失败：{exc}',
        )

    return KnowledgePublishResult(
        success=True,
        published_version=published_version,
        superseded_version=superseded,
        reason='发布成功',
    )


def rollback_knowledge_version(
    target_version: KnowledgeVersion,
    *,
    current_published: Optional[KnowledgeVersion],
    rolled_back_by: int,
    rolled_back_at: str,
    update_status: UpdateVersionStatusFn,
) -> KnowledgeRollbackResult:
    """回滚到指定版本（将目标版本设为 published，当前 published 版本设为 deprecated）。

    - 目标版本必须是 draft/in_review/deprecated/archived 状态才能回滚。
    - 当前 published 版本（若存在且非目标）标记为 deprecated。
    """
    if target_version.status == STATUS_PUBLISHED:
        return KnowledgeRollbackResult(
            success=False,
            active_version=None,
            deactivated_version=None,
            reason='目标版本已是 published 状态，无需回滚',
        )

    deactivated: Optional[KnowledgeVersion] = None
    if current_published is not None and current_published.id != target_version.id:
        try:
            update_status(
                current_published.id,
                STATUS_DEPRECATED,
                None,
                None,
                target_version.id,
            )
            deactivated = current_published
        except Exception:
            pass

    try:
        active_version = update_status(
            target_version.id,
            STATUS_PUBLISHED,
            rolled_back_by,
            rolled_back_at,
            None,
        )
    except Exception as exc:
        return KnowledgeRollbackResult(
            success=False,
            active_version=None,
            deactivated_version=deactivated,
            reason=f'回滚失败：{exc}',
        )

    return KnowledgeRollbackResult(
        success=True,
        active_version=active_version,
        deactivated_version=deactivated,
        reason='回滚成功',
    )


def deprecate_knowledge_version(
    version: KnowledgeVersion,
    *,
    update_status: UpdateVersionStatusFn,
) -> KnowledgeVersion:
    """失效知识版本（已发布版本标记为 deprecated，立即不可检索）。"""
    if version.status != STATUS_PUBLISHED:
        raise ValueError(f'仅 published 状态可失效，当前状态为 {version.status}')
    return update_status(version.id, STATUS_DEPRECATED, None, None, None)


def archive_knowledge_version(
    version: KnowledgeVersion,
    *,
    update_status: UpdateVersionStatusFn,
) -> KnowledgeVersion:
    """归档知识版本（历史版本归档，不可检索）。"""
    if version.status == STATUS_ARCHIVED:
        return version
    return update_status(version.id, STATUS_ARCHIVED, None, None, None)


def submit_for_review(
    version: KnowledgeVersion,
    *,
    update_status: UpdateVersionStatusFn,
) -> KnowledgeVersion:
    """提交审核（draft → in_review）。"""
    if version.status != STATUS_DRAFT:
        raise ValueError(f'仅 draft 状态可提交审核，当前状态为 {version.status}')
    return update_status(version.id, STATUS_IN_REVIEW, None, None, None)


# ===== 回答构建 =====

def build_knowledge_answer(
    results: list[KnowledgeRetrievalResult],
    *,
    message: str,
    page_url_resolver: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """构建知识库回答（验收2：显示来源和更新时间）。

    返回结构：
    - reply：Markdown 回答文本
    - cards：卡片列表
    - actions：跳转动作列表
    - needs_realtime_tool：是否需要路由到实时数据工具
    - sources：来源列表（含版本和更新时间）
    """
    lines: list[str] = []
    cards: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    seen_endpoints: set[str] = set()
    needs_realtime = is_realtime_question(message)

    if needs_realtime:
        lines.append('**提示**：本问题涉及实时库存/数量，知识库仅提供规则说明，实际数据必须使用实时数据工具查询。')
        lines.append('')

    if not results:
        if needs_realtime:
            lines.append('知识库无匹配规则，请使用实时数据工具查询。')
        else:
            lines.append('知识库未命中相关内容。')
        return {
            'reply': '\n'.join(lines),
            'cards': cards,
            'actions': actions,
            'needs_realtime_tool': needs_realtime,
            'sources': sources,
        }

    lines.append('**WMS知识库命中**')
    for index, result in enumerate(results, 1):
        version = result.entry
        page_url = ''
        if page_url_resolver is not None and version.page_endpoint:
            try:
                page_url = page_url_resolver(version.page_endpoint)
            except Exception:
                page_url = ''
        lines.extend([
            f'{index}. **{version.title}**',
            f'- 操作说明：{version.summary}',
            f'- 业务规则：{version.rule}',
            f'- 页面入口：{version.page_label}',
            f'- 来源：{result.source}',
            f'- 更新时间：{result.updated_at}',
            f'- 边界：{version.data_boundary}',
        ])
        cards.append({
            'title': version.title,
            'meta': f'{version.page_label}；v{version.version}；{result.updated_at}',
            'url': page_url,
        })
        if page_url and version.page_endpoint not in seen_endpoints:
            actions.append({'label': version.page_label, 'url': page_url})
            seen_endpoints.add(version.page_endpoint)
        sources.append({
            'title': version.title,
            'version': f'v{version.version}',
            'source': result.source,
            'updated_at': result.updated_at,
            'knowledge_key': version.knowledge_key,
        })

    if needs_realtime:
        lines.append('')
        lines.append('**重要**：以上为规则说明，实际库存/数量请使用实时数据工具查询。')

    return {
        'reply': '\n'.join(lines),
        'cards': cards,
        'actions': actions[:4],
        'needs_realtime_tool': needs_realtime,
        'sources': sources,
    }


# ===== 校验函数 =====

def validate_unpublished_not_retrievable(
    all_versions: list[KnowledgeVersion],
    *,
    query_published: QueryVersionsFn,
    role: str = DEFAULT_ADMIN_ROLE,
) -> tuple[bool, str]:
    """校验未发布内容不可检索（验收1）。"""
    try:
        retrieved = list(query_published() or [])
    except Exception as exc:
        return False, f'查询异常：{exc}'
    retrieved_ids = {v.id for v in retrieved}
    for version in all_versions:
        if version.status not in RETRIEVABLE_STATUSES and version.id in retrieved_ids:
            return False, f'版本 {version.knowledge_key} v{version.version} 状态为 {version.status} 但被检索到'
    return True, '未发布内容不可检索校验通过'


def validate_answer_shows_source_and_time(answer: dict[str, Any]) -> tuple[bool, str]:
    """校验回答显示来源和更新时间（验收2）。"""
    reply = answer.get('reply', '')
    sources = answer.get('sources', [])
    if not sources:
        return True, '无命中内容，跳过校验'
    if '来源' not in reply:
        return False, '回答未显示来源'
    if '更新时间' not in reply:
        return False, '回答未显示更新时间'
    for src in sources:
        if not src.get('source'):
            return False, f'来源 {src.get("title")} 缺少 source 字段'
        if not src.get('updated_at'):
            return False, f'来源 {src.get("title")} 缺少 updated_at 字段'
    return True, '回答显示来源和更新时间校验通过'


def validate_realtime_question_routed(message: str, answer: dict[str, Any]) -> tuple[bool, str]:
    """校验实时库存问题路由到实时数据工具（验收3）。"""
    if not is_realtime_question(message):
        return True, '非实时问题，跳过校验'
    if not answer.get('needs_realtime_tool'):
        return False, '实时问题未标记 needs_realtime_tool'
    reply = answer.get('reply', '')
    if '实时数据工具' not in reply:
        return False, '回答未提示使用实时数据工具'
    return True, '实时库存问题路由到实时数据工具校验通过'


def validate_published_unique_per_key(versions: list[KnowledgeVersion]) -> tuple[bool, str]:
    """校验同 key published 状态唯一。"""
    seen: dict[str, int] = {}
    for version in versions:
        if version.status == STATUS_PUBLISHED:
            if version.knowledge_key in seen:
                return False, f'知识 {version.knowledge_key} 有多个 published 版本（v{seen[version.knowledge_key]} 和 v{version.version}）'
            seen[version.knowledge_key] = version.version
    return True, '同 key published 唯一校验通过'
