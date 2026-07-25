"""AI-R12 知识库发布、版本和失效管理专项验证。

# AI_TASK: AI-R12

8 项测试覆盖：
1. 未发布内容不可检索
2. 回答显示来源和更新时间
3. 实时库存问题路由到实时数据工具
4. 发布操作同 key published 唯一（旧版本自动 deprecated）
5. 回滚操作（当前 published 标记为 deprecated，目标版本设为 published）
6. 失效操作（published → deprecated 立即不可检索）
7. 检索权限按角色过滤
8. 同 key published 唯一校验

设计：纯逻辑测试，不依赖 Flask/ORM，使用内存数据结构模拟版本。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-knowledge-lifecycle-secret'
sys.path.insert(0, str(APP_DIR))

from ai.knowledge_lifecycle import (
    KnowledgeVersion,
    KnowledgePublishResult,
    KnowledgeRollbackResult,
    KnowledgeRetrievalResult,
    STATUS_DRAFT,
    STATUS_IN_REVIEW,
    STATUS_PUBLISHED,
    STATUS_DEPRECATED,
    STATUS_ARCHIVED,
    REALTIME_KEYWORDS,
    is_realtime_question,
    is_retrievable,
    is_visible_to_role,
    search_published_knowledge,
    publish_knowledge_version,
    rollback_knowledge_version,
    deprecate_knowledge_version,
    submit_for_review,
    build_knowledge_answer,
    validate_unpublished_not_retrievable,
    validate_answer_shows_source_and_time,
    validate_realtime_question_routed,
    validate_published_unique_per_key,
)


def _make_version(
    version_id: int,
    knowledge_key: str = 'purchase_receive_sop',
    version: int = 1,
    title: str = '采购到货入库 SOP',
    keywords: tuple[str, ...] = ('采购入库', '到货入库', '送货单入库'),
    status: str = STATUS_PUBLISHED,
    allowed_roles: tuple[str, ...] = (),
    page_endpoint: str = 'purchase_order_list',
    page_label: str = '采购订单',
    updated_at: str = '2026-07-17T10:00:00',
    published_by: int | None = 1,
    published_at: str | None = '2026-07-17T10:00:00',
    superseded_by: int | None = None,
) -> KnowledgeVersion:
    return KnowledgeVersion(
        id=version_id,
        knowledge_key=knowledge_key,
        version=version,
        title=title,
        summary='采购入库可手工录入，也可从采购订单下推并跟踪来源。',
        content='采购订单是采购入库的可选来源；送货单识别只能生成草稿。',
        rule='AI 可以生成采购收货草稿，但不得自动完成入库。',
        page_endpoint=page_endpoint,
        page_label=page_label,
        keywords=keywords,
        source='manual',
        status=status,
        allowed_roles=allowed_roles,
        published_by=published_by,
        published_at=published_at,
        updated_at=updated_at,
        created_at='2026-07-16T09:00:00',
        superseded_by=superseded_by,
    )


def test1_unpublished_not_retrievable():
    """测试1：未发布内容不可检索（验收1）。"""
    # 创建一个 published 版本和一个 draft 版本
    published = _make_version(version_id=1, status=STATUS_PUBLISHED)
    draft = _make_version(
        version_id=2,
        version=2,
        status=STATUS_DRAFT,
        title='采购到货入库 SOP v2 草稿',
    )
    all_versions = [published, draft]

    # query_published 仅返回 published 版本
    def query_published():
        return [v for v in all_versions if v.status == STATUS_PUBLISHED]

    results = search_published_knowledge(
        '采购入库SOP',
        role='admin',
        query_published=query_published,
    )
    # draft 版本不应被检索到
    retrieved_ids = {r.entry.id for r in results}
    assert draft.id not in retrieved_ids, f'未发布内容（draft v2）被检索到：{retrieved_ids}'
    assert published.id in retrieved_ids, f'已发布内容未被检索到：{retrieved_ids}'

    # 校验函数也应通过
    ok, msg = validate_unpublished_not_retrievable(
        all_versions,
        query_published=query_published,
        role='admin',
    )
    assert ok, f'未发布不可检索校验失败：{msg}'

    # 测试 draft/in_review/deprecated/archived 都不可检索
    for blocked_status in (STATUS_DRAFT, STATUS_IN_REVIEW, STATUS_DEPRECATED, STATUS_ARCHIVED):
        blocked_version = _make_version(
            version_id=100 + hash(blocked_status) % 100,
            version=10,
            status=blocked_status,
            title=f'测试 {blocked_status}',
        )
        assert not is_retrievable(blocked_version), f'{blocked_status} 状态不应可检索'

    print('PASS 测试1：未发布内容不可检索（draft/in_review/deprecated/archived 均不可检索）')


def test2_answer_shows_source_and_time():
    """测试2：回答显示来源和更新时间（验收2）。"""
    published = _make_version(version_id=1, status=STATUS_PUBLISHED, updated_at='2026-07-17T10:00:00')
    results = [KnowledgeRetrievalResult(
        entry=published,
        score=10,
        source='知识库版本 v1',
        updated_at='2026-07-17T10:00:00',
        needs_realtime_tool=False,
    )]
    answer = build_knowledge_answer(results, message='采购入库SOP')
    reply = answer['reply']
    assert '来源' in reply, f'回答未显示来源：{reply}'
    assert '更新时间' in reply, f'回答未显示更新时间：{reply}'
    assert '知识库版本 v1' in reply, f'回答未包含来源版本信息：{reply}'
    assert '2026-07-17T10:00:00' in reply, f'回答未包含更新时间值：{reply}'
    assert len(answer['sources']) == 1, f'sources 数量错误：{answer["sources"]}'
    assert answer['sources'][0]['source'] == '知识库版本 v1'
    assert answer['sources'][0]['updated_at'] == '2026-07-17T10:00:00'

    # 校验函数通过
    ok, msg = validate_answer_shows_source_and_time(answer)
    assert ok, f'回答显示来源时间校验失败：{msg}'

    # 空结果也应通过校验
    empty_answer = build_knowledge_answer([], message='未知问题')
    ok, msg = validate_answer_shows_source_and_time(empty_answer)
    assert ok, f'空结果校验失败：{msg}'

    print('PASS 测试2：回答显示来源和更新时间（来源=知识库版本 vX + 更新时间=ISO8601）')


def test3_realtime_question_routed():
    """测试3：实时库存问题路由到实时数据工具（验收3）。"""
    # 实时问题识别
    realtime_questions = (
        '当前库存多少',
        '现在的库存数量',
        '今天的余额',
        '可用库存还有多少',
        '剩余数量',
        '在途数量',
    )
    for q in realtime_questions:
        assert is_realtime_question(q), f'未识别为实时问题：{q}'

    # 非实时问题
    non_realtime_questions = (
        '采购入库SOP',
        '出库流程规则',
        '单据状态机',
    )
    for q in non_realtime_questions:
        assert not is_realtime_question(q), f'误识别为实时问题：{q}'

    # 实时问题检索结果标记 needs_realtime_tool=True
    published = _make_version(version_id=1, status=STATUS_PUBLISHED)
    results = search_published_knowledge(
        '当前库存多少',
        role='admin',
        query_published=lambda: [published],
    )
    # 即使有知识命中（关键词匹配），needs_realtime_tool 也应为 True
    for r in results:
        assert r.needs_realtime_tool, f'实时问题检索结果未标记 needs_realtime_tool：{r}'

    # 回答应包含实时数据工具提示
    answer = build_knowledge_answer(results, message='当前库存多少')
    assert answer['needs_realtime_tool'], '回答未标记 needs_realtime_tool'
    assert '实时数据工具' in answer['reply'], f'回答未提示使用实时数据工具：{answer["reply"]}'

    # 校验函数通过
    ok, msg = validate_realtime_question_routed('当前库存多少', answer)
    assert ok, f'实时问题路由校验失败：{msg}'

    # 非实时问题校验也通过（跳过）
    ok, msg = validate_realtime_question_routed('采购入库SOP', answer)
    assert ok, f'非实时问题校验失败：{msg}'

    print('PASS 测试3：实时库存问题路由到实时数据工具（needs_realtime_tool=True + 回答提示）')


def test4_publish_supersedes_old():
    """测试4：发布操作同 key published 唯一（旧版本自动 deprecated）。"""
    old_published = _make_version(version_id=1, version=1, status=STATUS_PUBLISHED)
    new_draft = _make_version(
        version_id=2,
        version=2,
        status=STATUS_DRAFT,
        title='采购到货入库 SOP v2',
        keywords=('采购入库', '到货入库', '送货单入库', '新版'),
    )

    # 内存状态存储
    state = {1: dict(old_published.__dict__), 2: dict(new_draft.__dict__)}

    def update_status(version_id, status, published_by=None, published_at=None, superseded_by=None):
        row = state[version_id].copy()
        row['status'] = status
        if status == STATUS_PUBLISHED:
            row['published_by'] = published_by
            row['published_at'] = published_at
        elif status == STATUS_DEPRECATED:
            row['superseded_by'] = superseded_by
        state[version_id].update(row)
        return KnowledgeVersion(**{k: v for k, v in row.items() if k in KnowledgeVersion.__dataclass_fields__})

    def query_published_by_key(knowledge_key):
        for vid, row in state.items():
            if row['knowledge_key'] == knowledge_key and row['status'] == STATUS_PUBLISHED:
                return KnowledgeVersion(**{k: v for k, v in row.items() if k in KnowledgeVersion.__dataclass_fields__})
        return None

    # 发布新版本
    result = publish_knowledge_version(
        new_draft,
        published_by=1,
        published_at='2026-07-17T11:00:00',
        update_status=update_status,
        query_published_by_key=query_published_by_key,
    )
    assert result.success, f'发布失败：{result.reason}'
    assert result.published_version is not None
    assert result.published_version.id == 2
    assert result.published_version.status == STATUS_PUBLISHED
    # 旧版本应被标记为 deprecated，superseded_by 指向新版本
    assert result.superseded_version is not None
    assert result.superseded_version.id == 1

    # 验证内存状态：旧版本已 deprecated
    assert state[1]['status'] == STATUS_DEPRECATED, f'旧版本未标记为 deprecated：{state[1]["status"]}'
    assert state[1]['superseded_by'] == 2
    assert state[2]['status'] == STATUS_PUBLISHED

    # 重复发布 published 状态应失败
    result2 = publish_knowledge_version(
        result.published_version,
        published_by=1,
        published_at='2026-07-17T12:00:00',
        update_status=update_status,
        query_published_by_key=query_published_by_key,
    )
    assert not result2.success, f'published 状态重复发布应失败：{result2.reason}'

    print('PASS 测试4：发布操作同 key published 唯一（旧版本自动 deprecated + 重复发布拒绝）')


def test5_rollback():
    """测试5：回滚操作（当前 published 标记为 deprecated，目标版本设为 published）。"""
    current_published = _make_version(version_id=2, version=2, status=STATUS_PUBLISHED)
    target_deprecated = _make_version(
        version_id=1,
        version=1,
        status=STATUS_DEPRECATED,
        title='采购到货入库 SOP v1（旧版）',
    )

    state = {1: dict(target_deprecated.__dict__), 2: dict(current_published.__dict__)}

    def update_status(version_id, status, published_by=None, published_at=None, superseded_by=None):
        row = state[version_id].copy()
        row['status'] = status
        if status == STATUS_PUBLISHED:
            row['published_by'] = published_by
            row['published_at'] = published_at
        elif status == STATUS_DEPRECATED:
            row['superseded_by'] = superseded_by
        state[version_id].update(row)
        return KnowledgeVersion(**{k: v for k, v in row.items() if k in KnowledgeVersion.__dataclass_fields__})

    result = rollback_knowledge_version(
        target_deprecated,
        current_published=current_published,
        rolled_back_by=1,
        rolled_back_at='2026-07-17T13:00:00',
        update_status=update_status,
    )
    assert result.success, f'回滚失败：{result.reason}'
    assert result.active_version.id == 1
    assert result.active_version.status == STATUS_PUBLISHED
    assert result.deactivated_version is not None
    assert result.deactivated_version.id == 2

    # 验证状态
    assert state[1]['status'] == STATUS_PUBLISHED, f'目标版本未设为 published：{state[1]["status"]}'
    assert state[2]['status'] == STATUS_DEPRECATED
    assert state[2]['superseded_by'] == 1

    # 回滚到已 published 状态应失败
    result2 = rollback_knowledge_version(
        result.active_version,
        current_published=None,
        rolled_back_by=1,
        rolled_back_at='2026-07-17T14:00:00',
        update_status=update_status,
    )
    assert not result2.success, f'已 published 版本回滚应失败：{result2.reason}'

    print('PASS 测试5：回滚操作（目标 published + 当前 deprecated + superseded_by 追溯）')


def test6_deprecate_makes_unretrievable():
    """测试6：失效操作（published → deprecated 立即不可检索）。"""
    published = _make_version(version_id=1, status=STATUS_PUBLISHED)
    state = {1: dict(published.__dict__)}

    def update_status(version_id, status, published_by=None, published_at=None, superseded_by=None):
        row = state[version_id].copy()
        row['status'] = status
        state[version_id].update(row)
        return KnowledgeVersion(**{k: v for k, v in row.items() if k in KnowledgeVersion.__dataclass_fields__})

    # 失效前可检索
    results_before = search_published_knowledge(
        '采购入库SOP',
        role='admin',
        query_published=lambda: [KnowledgeVersion(**{k: v for k, v in state[1].items() if k in KnowledgeVersion.__dataclass_fields__})],
    )
    assert len(results_before) > 0, '失效前应可检索'

    # 执行失效
    updated = deprecate_knowledge_version(published, update_status=update_status)
    assert updated.status == STATUS_DEPRECATED

    # 失效后不可检索
    results_after = search_published_knowledge(
        '采购入库SOP',
        role='admin',
        query_published=lambda: [KnowledgeVersion(**{k: v for k, v in state[1].items() if k in KnowledgeVersion.__dataclass_fields__})],
    )
    assert len(results_after) == 0, f'失效后仍可检索：{results_after}'

    # 非 published 状态失效应报错
    try:
        deprecate_knowledge_version(updated, update_status=update_status)
        raise AssertionError('非 published 状态失效应报错')
    except ValueError as e:
        assert '仅 published' in str(e), f'错误信息不符：{e}'

    print('PASS 测试6：失效操作（published → deprecated 立即不可检索）')


def test7_role_visibility():
    """测试7：检索权限按角色过滤。"""
    # 限制 admin 才可见的版本
    admin_only = _make_version(
        version_id=1,
        status=STATUS_PUBLISHED,
        allowed_roles=('admin',),
        title='管理员专用规则',
        keywords=('规则',),
    )
    # 全部角色可见的版本
    public = _make_version(
        version_id=2,
        version=1,
        knowledge_key='public_sop',
        status=STATUS_PUBLISHED,
        allowed_roles=(),
        title='通用规则',
        keywords=('规则',),
    )
    # 仓库可见的版本
    warehouse_only = _make_version(
        version_id=3,
        version=1,
        knowledge_key='warehouse_sop',
        status=STATUS_PUBLISHED,
        allowed_roles=('warehouse',),
        title='仓库专用规则',
        keywords=('规则',),
    )

    all_versions = [admin_only, public, warehouse_only]

    # warehouse 角色只能看到 public + warehouse_only
    results_warehouse = search_published_knowledge(
        '规则',
        role='warehouse',
        query_published=lambda: all_versions,
    )
    retrieved_ids_w = {r.entry.id for r in results_warehouse}
    assert admin_only.id not in retrieved_ids_w, f'warehouse 角色不应看到 admin_only：{retrieved_ids_w}'
    assert public.id in retrieved_ids_w, f'warehouse 角色应看到 public：{retrieved_ids_w}'
    assert warehouse_only.id in retrieved_ids_w, f'warehouse 角色应看到 warehouse_only：{retrieved_ids_w}'

    # admin 角色应看到全部
    results_admin = search_published_knowledge(
        '规则',
        role='admin',
        query_published=lambda: all_versions,
    )
    retrieved_ids_a = {r.entry.id for r in results_admin}
    assert admin_only.id in retrieved_ids_a, f'admin 角色应看到 admin_only：{retrieved_ids_a}'
    assert public.id in retrieved_ids_a
    assert warehouse_only.id in retrieved_ids_a

    # guest 角色只能看到 public
    results_guest = search_published_knowledge(
        '规则',
        role='guest',
        query_published=lambda: all_versions,
    )
    retrieved_ids_g = {r.entry.id for r in results_guest}
    assert admin_only.id not in retrieved_ids_g
    assert public.id in retrieved_ids_g
    assert warehouse_only.id not in retrieved_ids_g

    # is_visible_to_role 单元测试
    assert is_visible_to_role(admin_only, 'admin') is True
    assert is_visible_to_role(admin_only, 'warehouse') is False
    assert is_visible_to_role(public, 'guest') is True
    assert is_visible_to_role(warehouse_only, 'warehouse') is True
    assert is_visible_to_role(warehouse_only, 'purchase') is False

    print('PASS 测试7：检索权限按角色过滤（admin 全可见 + allowed_roles 限制 + guest 仅公开）')


def test8_published_unique_per_key():
    """测试8：同 key published 唯一校验。"""
    # 正常情况：同 key 仅一个 published
    versions_ok = [
        _make_version(version_id=1, version=1, status=STATUS_PUBLISHED),
        _make_version(version_id=2, version=2, status=STATUS_DEPRECATED, superseded_by=1),
        _make_version(version_id=3, version=1, knowledge_key='other_sop', status=STATUS_PUBLISHED),
    ]
    ok, msg = validate_published_unique_per_key(versions_ok)
    assert ok, f'正常情况校验失败：{msg}'

    # 异常情况：同 key 多个 published
    versions_bad = [
        _make_version(version_id=1, version=1, status=STATUS_PUBLISHED),
        _make_version(version_id=2, version=2, status=STATUS_PUBLISHED),
    ]
    ok, msg = validate_published_unique_per_key(versions_bad)
    assert not ok, f'同 key 多个 published 应校验失败：{msg}'
    assert '多个 published' in msg, f'错误信息不符：{msg}'

    # 提交审核流程测试（draft → in_review）
    draft = _make_version(version_id=10, version=5, status=STATUS_DRAFT)
    state = {10: dict(draft.__dict__)}

    def update_status(version_id, status, published_by=None, published_at=None, superseded_by=None):
        row = state[version_id].copy()
        row['status'] = status
        state[version_id].update(row)
        return KnowledgeVersion(**{k: v for k, v in row.items() if k in KnowledgeVersion.__dataclass_fields__})

    in_review = submit_for_review(draft, update_status=update_status)
    assert in_review.status == STATUS_IN_REVIEW

    # 非 draft 状态提交审核应报错
    try:
        submit_for_review(in_review, update_status=update_status)
        raise AssertionError('非 draft 状态提交审核应报错')
    except ValueError as e:
        assert '仅 draft' in str(e)

    print('PASS 测试8：同 key published 唯一校验 + submit_for_review 流程')


def main() -> int:
    print('=== AI-R12 知识库发布、版本和失效管理验证 ===')
    tests = [
        test1_unpublished_not_retrievable,
        test2_answer_shows_source_and_time,
        test3_realtime_question_routed,
        test4_publish_supersedes_old,
        test5_rollback,
        test6_deprecate_makes_unretrievable,
        test7_role_visibility,
        test8_published_unique_per_key,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as e:
            print(f'FAIL {test.__name__}: {e}')
            failed += 1
        except Exception as e:
            print(f'ERROR {test.__name__}: {type(e).__name__}: {e}')
            failed += 1
    print(f'\n=== AI-R12 知识库发布、版本和失效管理: {len(tests) - failed} PASS / {failed} FAIL ===')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
