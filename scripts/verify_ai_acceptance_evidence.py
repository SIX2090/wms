"""AI-R17-F02 连续七天真实上线验收 专项验证。

# AI_TASK: AI-R17-F02

验收要求（台账 13.2）：
1. 四项绝对指标连续七天每日为 0。
2. 质量指标按天采集并汇总。
3. 口径修正：草稿采用率反查业务单据状态；低置信度未确认读取确认状态。
4. 验收证据包：七天每日快照+汇总+灰度矩阵+样本清单+回滚记录+go/no-go 结论。
5. 所有指标保存分子、分母、时间窗口和筛选条件，支持复算。
6. 管理员签字 go/no-go；任一绝对指标非 0 必须 no-go。

设计：纯逻辑模块 acceptance_evidence.py + Flask test_client 端到端混合模式。
8 项测试覆盖每日快照+七天证据包+口径修正+可复算+go/no-go+端到端 API 闭环。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-acceptance-evidence-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app
from ai.ops.acceptance_evidence import (
    ALL_SAMPLE_TYPES,
    DEFAULT_EVIDENCE_DAYS,
    GO_DECISION,
    NO_GO_DECISION,
    SAMPLE_CORRECTION,
    SAMPLE_DUPLICATE,
    SAMPLE_FAILURE,
    SAMPLE_FALLBACK,
    VALID_BUSINESS_STATUSES,
    INVALID_BUSINESS_STATUSES,
    AcceptanceEvidencePackage,
    DailyMetricSnapshot,
    EvidenceSample,
    RollbackEvidence,
    build_daily_snapshot,
    build_evidence_package,
    is_draft_adopted_by_business,
    is_low_confidence_unconfirmed,
    validate_all_evidence,
    validate_evidence_reproducible,
    validate_go_no_go,
    validate_rollback_evidence_present,
    validate_rollout_matrix_complete,
    validate_sample_lists_present,
    validate_seven_consecutive_days_zero,
)
from ai.ops.launch_acceptance import (
    ALL_ACCEPTANCE_METRICS,
    METRIC_AUTO_SUBMIT,
    METRIC_DUPLICATE_DRAFTS,
    METRIC_LOW_CONFIDENCE_UNCONFIRMED,
    METRIC_UNAUTHORIZED_SUCCESS,
)


# ===== Flask test_client 基础设施 =====

def _set_setting(key: str, value: str) -> None:
    row = wms_app.SystemSetting.query.filter_by(key=key).first()
    if not row:
        row = wms_app.SystemSetting(key=key)
        wms_app.db.session.add(row)
    row.value = value


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def _create_users() -> dict[str, int]:
    users = {}
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        wms_app.User.query.filter_by(username=f'f02-{role}').delete()
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User(
            username=f'f02-{role}',
            password_hash='not-used',
            role=role,
            status='normal',
        )
        wms_app.db.session.add(user)
    wms_app.db.session.commit()
    for role in ('admin', 'warehouse', 'purchase', 'production', 'user'):
        user = wms_app.User.query.filter_by(username=f'f02-{role}').first()
        users[role] = user.id
    return users


def _enable_ai_features() -> None:
    _set_setting('ai_feature_global_enabled', '1')
    _set_setting('ai_feature_rollout_mode', 'all')
    _set_setting('ai_feature_allowed_user_ids', '')
    _set_setting('ai_force_fallback', '0')
    _set_setting('ai_feature_drafts_enabled', '1')
    _set_setting('ai_feature_agents_enabled', '1')
    _set_setting('ai_feature_vision_enabled', '1')
    _set_setting('ai_degrade_local_only', '0')
    wms_app.db.session.commit()


def _make_zero_absolute_counts() -> dict[str, int]:
    return {m: 0 for m in ALL_ACCEPTANCE_METRICS}


def _make_zero_quality_metrics() -> dict[str, dict]:
    from ai.ops.business_quality import ALL_METRICS
    return {m: {'numerator': 0, 'denominator': 0, 'rate': 0.0} for m in ALL_METRICS}


def _make_quality_metrics_with_data() -> dict[str, dict]:
    from ai.ops.business_quality import ALL_METRICS
    result = {}
    for m in ALL_METRICS:
        result[m] = {'numerator': 8, 'denominator': 10, 'rate': 0.8}
    return result


# ===== 测试1：每日快照构造 + 四项绝对指标全 0 =====

def test1_daily_snapshot_construction():
    """测试1：每日快照构造正确性 + 四项绝对指标全 0 判定。"""
    now = datetime(2026, 7, 18, 12, 0, 0)
    # 全 0 快照
    snap = build_daily_snapshot(
        snapshot_date='2026-07-18',
        absolute_counts=_make_zero_absolute_counts(),
        quality_metrics=_make_quality_metrics_with_data(),
        rollout_user_count=3,
        rollout_role_count=3,
        rollout_roles=('admin', 'warehouse', 'purchase'),
        filter_applied={'snapshot_date': '2026-07-18', 'window_hours': 24, 'source': 'daily_snapshot'},
        now=now,
    )
    assert snap.snapshot_date == '2026-07-18'
    assert snap.all_absolute_zero, '全 0 快照应 all_absolute_zero=True'
    assert snap.rollout_user_count == 3
    assert len(snap.absolute_counts) == 4, '应有 4 项绝对指标'
    assert len(snap.quality_metrics) == 7, '应有 7 项质量指标'
    assert snap.window_hours == 24, '单日窗口应为 24'
    assert snap.filter_applied, '应有筛选条件追溯'

    # 非全 0 快照
    snap2 = build_daily_snapshot(
        snapshot_date='2026-07-18',
        absolute_counts={METRIC_UNAUTHORIZED_SUCCESS: 1, METRIC_DUPLICATE_DRAFTS: 0, METRIC_AUTO_SUBMIT: 0, METRIC_LOW_CONFIDENCE_UNCONFIRMED: 0},
        quality_metrics=_make_zero_quality_metrics(),
        now=now,
    )
    assert not snap2.all_absolute_zero, '越权成功=1 应 all_absolute_zero=False'

    # 缺失键补 0
    snap3 = build_daily_snapshot(
        snapshot_date='2026-07-18',
        absolute_counts={},
        quality_metrics={},
        now=now,
    )
    assert snap3.all_absolute_zero, '缺失键应补 0 后 all_absolute_zero=True'
    assert all(v == 0 for v in snap3.absolute_counts.values()), '缺失键应补 0'

    # to_dict 可序列化
    d = snap.to_dict()
    assert d['snapshot_date'] == '2026-07-18'
    assert d['absolute_counts'][METRIC_UNAUTHORIZED_SUCCESS] == 0

    print('PASS 测试1：每日快照构造+四项绝对指标全0判定（补0+all_absolute_zero+to_dict序列化）')


# ===== 测试2：连续七天四项绝对指标每日为 0 校验 =====

def test2_seven_consecutive_days_zero():
    """测试2：连续七天四项绝对指标每日为 0 校验。"""
    now = datetime(2026, 7, 18, 12, 0, 0)
    # 7 天连续全 0
    snapshots = []
    for i in range(7):
        d = (datetime(2026, 7, 12) + timedelta(days=i)).strftime('%Y-%m-%d')
        snapshots.append(build_daily_snapshot(
            snapshot_date=d,
            absolute_counts=_make_zero_absolute_counts(),
            quality_metrics=_make_zero_quality_metrics(),
            now=now,
        ))
    ok, reason = validate_seven_consecutive_days_zero(snapshots)
    assert ok, f'7 天连续全 0 应通过：{reason}'

    # 不足 7 天
    ok2, reason2 = validate_seven_consecutive_days_zero(snapshots[:5])
    assert not ok2, '5 天应失败'
    assert '不足' in reason2

    # 日期不连续
    bad_snapshots = list(snapshots)
    bad_snapshots[3] = build_daily_snapshot(
        snapshot_date='2026-07-20',  # 跳过 07-15
        absolute_counts=_make_zero_absolute_counts(),
        quality_metrics=_make_zero_quality_metrics(),
        now=now,
    )
    ok3, reason3 = validate_seven_consecutive_days_zero(bad_snapshots)
    assert not ok3, '日期不连续应失败'
    assert '不连续' in reason3

    # 某天非 0
    bad_snapshots2 = list(snapshots)
    bad_snapshots2[2] = build_daily_snapshot(
        snapshot_date='2026-07-14',
        absolute_counts={METRIC_DUPLICATE_DRAFTS: 2, METRIC_UNAUTHORIZED_SUCCESS: 0, METRIC_AUTO_SUBMIT: 0, METRIC_LOW_CONFIDENCE_UNCONFIRMED: 0},
        quality_metrics=_make_zero_quality_metrics(),
        now=now,
    )
    ok4, reason4 = validate_seven_consecutive_days_zero(bad_snapshots2)
    assert not ok4, '某天重复草稿=2 应失败'
    assert '2026-07-14' in reason4
    assert '非 0' in reason4

    print('PASS 测试2：连续七天四项绝对指标每日为0校验（7天通过/不足7天失败/日期不连续失败/某天非0失败）')


# ===== 测试3：口径修正 — 草稿采用率反查业务单据状态 =====

def test3_draft_adoption_reverse_check():
    """测试3：草稿采用率反查业务单据状态（口径修正）。"""
    # 有效状态 → 采用
    for status in VALID_BUSINESS_STATUSES:
        ok, reason = is_draft_adopted_by_business('in_order', 1, status)
        assert ok, f'status={status} 应采用：{reason}'

    # 无效状态 → 不采用
    for status in INVALID_BUSINESS_STATUSES:
        ok, reason = is_draft_adopted_by_business('in_order', 1, status)
        assert not ok, f'status={status} 不应采用：{reason}'
        assert status in reason, f'原因应含状态：{reason}'

    # draft_id 为空 → 不采用
    ok, reason = is_draft_adopted_by_business('in_order', None, 'pending')
    assert not ok, 'draft_id 为空不应采用'
    assert 'draft_id' in reason

    # draft_id <= 0 → 不采用
    ok, reason = is_draft_adopted_by_business('in_order', 0, 'pending')
    assert not ok, 'draft_id=0 不应采用'

    # 业务单据不存在 → 不采用
    ok, reason = is_draft_adopted_by_business('in_order', 999, None)
    assert not ok, 'business_status=None 不应采用'
    assert '不存在' in reason

    # 未知状态 → 保守判定不采用
    ok, reason = is_draft_adopted_by_business('in_order', 1, 'unknown_xyz')
    assert not ok, '未知状态应保守判定不采用'
    assert '保守' in reason

    print('PASS 测试3：草稿采用率反查业务单据状态（有效采用/作废不采用/draft_id空不采用/不存在不采用/未知保守不采用）')


# ===== 测试4：口径修正 — 低置信度未确认判定 =====

def test4_low_confidence_unconfirmed():
    """测试4：低置信度未确认判定（临时口径+R08-F01切换预留）。"""
    # 低置信度 + draft_created + 未确认 → True
    ok, reason = is_low_confidence_unconfirmed(0.5, 'draft_created', None)
    assert ok, 'confidence=0.5<0.85 + draft_created + None 应判定未确认'
    assert '0.5' in reason

    # 正常置信度 → False
    ok2, reason2 = is_low_confidence_unconfirmed(0.9, 'draft_created', None)
    assert not ok2, 'confidence=0.9 不应判定未确认'

    # 低置信度但非 draft_created → False
    ok3, reason3 = is_low_confidence_unconfirmed(0.5, 'recognized', None)
    assert not ok3, 'status=recognized 不应判定未确认'

    # 已确认（R08-F01 完成后）→ False
    for cs in ('confirmed_original', 'corrected', 'rejected'):
        ok4, reason4 = is_low_confidence_unconfirmed(0.5, 'draft_created', cs)
        assert not ok4, f'confirmation_status={cs} 不应判定未确认'

    # confidence=None → False
    ok5, reason5 = is_low_confidence_unconfirmed(None, 'draft_created', None)
    assert not ok5, 'confidence=None 不应判定未确认'

    print('PASS 测试4：低置信度未确认判定（临时口径confidence<0.85+draft_created+R08-F01切换预留）')


# ===== 测试5：验收数据可复算校验 =====

def test5_evidence_reproducible():
    """测试5：验收数据可复算（分子分母时间窗口筛选条件齐全）。"""
    now = datetime(2026, 7, 18, 12, 0, 0)
    # 可复算的证据包
    snapshots = []
    for i in range(7):
        d = (datetime(2026, 7, 12) + timedelta(days=i)).strftime('%Y-%m-%d')
        snapshots.append(build_daily_snapshot(
            snapshot_date=d,
            absolute_counts=_make_zero_absolute_counts(),
            quality_metrics=_make_quality_metrics_with_data(),
            rollout_user_count=3,
            rollout_role_count=3,
            rollout_roles=('admin', 'warehouse', 'purchase'),
            filter_applied={'date': d, 'source': 'daily_snapshot'},
            now=now,
        ))
    pkg = build_evidence_package(
        package_id='test-pkg-1',
        daily_snapshots=snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[RollbackEvidence(
            event_id='evt-1', action='shutdown', operator_id=1, operator_role='admin',
            started_at=now.isoformat(), completed_at=now.isoformat(),
            duration_seconds=60.0,
        ), RollbackEvidence(
            event_id='evt-2', action='restore', operator_id=1, operator_role='admin',
            started_at=now.isoformat(), completed_at=now.isoformat(),
            duration_seconds=120.0,
        )],
        go_no_go_decision=GO_DECISION,
        decided_by=1,
        now=now,
    )
    ok, reason = validate_evidence_reproducible(pkg)
    assert ok, f'可复算应通过：{reason}'

    # 缺少 filter_applied → 失败
    bad_snap = build_daily_snapshot(
        snapshot_date='2026-07-12',
        absolute_counts=_make_zero_absolute_counts(),
        quality_metrics=_make_quality_metrics_with_data(),
        filter_applied={},
        now=now,
    )
    bad_snapshots = list(snapshots)
    bad_snapshots[0] = bad_snap
    bad_pkg = build_evidence_package(
        package_id='test-pkg-2',
        daily_snapshots=bad_snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        now=now,
    )
    ok2, reason2 = validate_evidence_reproducible(bad_pkg)
    assert not ok2, '缺少 filter_applied 应失败'
    assert 'filter_applied' in reason2

    # rate 不可复算 → 失败
    bad_quality = _make_quality_metrics_with_data()
    bad_quality['classification_accuracy'] = {'numerator': 3, 'denominator': 10, 'rate': 0.5}  # 3/10=0.3 ≠ 0.5
    bad_snap2 = build_daily_snapshot(
        snapshot_date='2026-07-12',
        absolute_counts=_make_zero_absolute_counts(),
        quality_metrics=bad_quality,
        filter_applied={'date': '2026-07-12'},
        now=now,
    )
    bad_snapshots2 = list(snapshots)
    bad_snapshots2[0] = bad_snap2
    bad_pkg2 = build_evidence_package(
        package_id='test-pkg-3',
        daily_snapshots=bad_snapshots2,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        now=now,
    )
    ok3, reason3 = validate_evidence_reproducible(bad_pkg2)
    assert not ok3, 'rate 不可复算应失败'
    assert '不可复算' in reason3

    print('PASS 测试5：验收数据可复算（分子分母时间窗口筛选条件齐全+rate可复算+缺filter_applied失败）')


# ===== 测试6：go/no-go 结论校验 =====

def test6_go_no_go_decision():
    """测试6：go/no-go 结论校验（任一非0必须no-go+签字+原因）。"""
    now = datetime(2026, 7, 18, 12, 0, 0)
    # 全 0 + go + 签字 → 通过
    snapshots_all_zero = []
    for i in range(7):
        d = (datetime(2026, 7, 12) + timedelta(days=i)).strftime('%Y-%m-%d')
        snapshots_all_zero.append(build_daily_snapshot(
            snapshot_date=d,
            absolute_counts=_make_zero_absolute_counts(),
            quality_metrics=_make_zero_quality_metrics(),
            filter_applied={'date': d},
            now=now,
        ))
    pkg_go = build_evidence_package(
        package_id='pkg-go',
        daily_snapshots=snapshots_all_zero,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        go_no_go_decision=GO_DECISION,
        decided_by=1,
        decided_at=now.isoformat(),
        now=now,
    )
    ok, reason = validate_go_no_go(pkg_go)
    assert ok, f'全0+go+签字应通过：{reason}'

    # 全 0 + go 但无签字 → 失败
    pkg_go_no_sign = build_evidence_package(
        package_id='pkg-go-2',
        daily_snapshots=snapshots_all_zero,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        go_no_go_decision=GO_DECISION,
        decided_by=None,
        now=now,
    )
    ok2, reason2 = validate_go_no_go(pkg_go_no_sign)
    assert not ok2, 'go 无签字应失败'
    assert '签字' in reason2

    # 非 0 + go → 失败
    snapshots_nonzero = list(snapshots_all_zero)
    snapshots_nonzero[0] = build_daily_snapshot(
        snapshot_date='2026-07-12',
        absolute_counts={METRIC_UNAUTHORIZED_SUCCESS: 1, METRIC_DUPLICATE_DRAFTS: 0, METRIC_AUTO_SUBMIT: 0, METRIC_LOW_CONFIDENCE_UNCONFIRMED: 0},
        quality_metrics=_make_zero_quality_metrics(),
        filter_applied={'date': '2026-07-12'},
        now=now,
    )
    pkg_no_go_violation = build_evidence_package(
        package_id='pkg-violation',
        daily_snapshots=snapshots_nonzero,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        go_no_go_decision=GO_DECISION,
        decided_by=1,
        now=now,
    )
    ok3, reason3 = validate_go_no_go(pkg_no_go_violation)
    assert not ok3, '非0+go 应失败'
    assert '不得 go' in reason3

    # 非 0 + no_go + 原因 → 通过
    pkg_no_go_ok = build_evidence_package(
        package_id='pkg-no-go',
        daily_snapshots=snapshots_nonzero,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        go_no_go_decision=NO_GO_DECISION,
        decision_reason='越权成功=1，需修复',
        decided_by=1,
        now=now,
    )
    ok4, reason4 = validate_go_no_go(pkg_no_go_ok)
    assert ok4, f'非0+no_go+原因应通过：{reason4}'

    # pending → 失败
    pkg_pending = build_evidence_package(
        package_id='pkg-pending',
        daily_snapshots=snapshots_all_zero,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        go_no_go_decision='pending',
        now=now,
    )
    ok5, reason5 = validate_go_no_go(pkg_pending)
    assert not ok5, 'pending 应失败'
    assert '待定' in reason5

    print('PASS 测试6：go/no-go结论校验（全0+go+签字通过/无签字失败/非0不得go/no_go+原因通过/pending失败）')


# ===== 测试7：证据包完整性校验（灰度矩阵+回滚+样本清单）=====

def test7_evidence_package_completeness():
    """测试7：证据包完整性校验（灰度矩阵+回滚记录+四类样本清单）。"""
    now = datetime(2026, 7, 18, 12, 0, 0)
    snapshots = []
    for i in range(7):
        d = (datetime(2026, 7, 12) + timedelta(days=i)).strftime('%Y-%m-%d')
        snapshots.append(build_daily_snapshot(
            snapshot_date=d,
            absolute_counts=_make_zero_absolute_counts(),
            quality_metrics=_make_zero_quality_metrics(),
            rollout_user_count=3,
            rollout_role_count=3,
            rollout_roles=('admin', 'warehouse', 'purchase'),
            filter_applied={'date': d},
            now=now,
        ))
    # 完整证据包
    pkg = build_evidence_package(
        package_id='pkg-complete',
        daily_snapshots=snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        failure_samples=[EvidenceSample(SAMPLE_FAILURE, 'f-1', now.isoformat(), 'warehouse', 'api', '失败', 'AIToolCall', '1')],
        fallback_samples=[EvidenceSample(SAMPLE_FALLBACK, 'fb-1', now.isoformat(), '', '', '降级', 'AIManualFallbackTask', 'fb-1')],
        duplicate_samples=[EvidenceSample(SAMPLE_DUPLICATE, 'd-1', now.isoformat(), '', '', '重复', 'AIDraftIdempotency', '1')],
        correction_samples=[EvidenceSample(SAMPLE_CORRECTION, 'c-1', now.isoformat(), '', 'ocr', '修正', 'AIFieldFeedback', '1')],
        rollback_events=[
            RollbackEvidence('e-1', 'shutdown', 1, 'admin', now.isoformat(), now.isoformat(), 60.0),
            RollbackEvidence('e-2', 'restore', 1, 'admin', now.isoformat(), now.isoformat(), 120.0),
        ],
        go_no_go_decision=GO_DECISION,
        decided_by=1,
        now=now,
    )
    # 灰度矩阵完整性
    ok1, reason1 = validate_rollout_matrix_complete(pkg)
    assert ok1, f'灰度矩阵完整应通过：{reason1}'

    # 回滚证据存在
    ok2, reason2 = validate_rollback_evidence_present(pkg)
    assert ok2, f'回滚证据应通过：{reason2}'

    # 样本清单存在
    ok3, reason3 = validate_sample_lists_present(pkg)
    assert ok3, f'样本清单应通过：{reason3}'

    # 缺少核心角色
    pkg_missing_role = build_evidence_package(
        package_id='pkg-missing',
        daily_snapshots=snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True)],  # 缺 purchase
        rollback_events=[],
        now=now,
    )
    ok4, reason4 = validate_rollout_matrix_complete(pkg_missing_role)
    assert not ok4, '缺少核心角色应失败'
    assert 'purchase' in reason4

    # 缺少回滚记录
    pkg_no_rollback = build_evidence_package(
        package_id='pkg-no-rb',
        daily_snapshots=snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[],
        now=now,
    )
    ok5, reason5 = validate_rollback_evidence_present(pkg_no_rollback)
    assert not ok5, '缺少回滚记录应失败'
    assert '为空' in reason5

    # 缺少 restore
    pkg_no_restore = build_evidence_package(
        package_id='pkg-no-restore',
        daily_snapshots=snapshots,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[
            RollbackEvidence('e-1', 'shutdown', 1, 'admin', now.isoformat(), now.isoformat(), 60.0),
        ],
        now=now,
    )
    ok6, reason6 = validate_rollback_evidence_present(pkg_no_restore)
    assert not ok6, '缺少 restore 应失败'
    assert 'restore' in reason6

    # 综合校验
    ok7, failures7 = validate_all_evidence(pkg)
    # go 决策需要签字
    assert ok7 or any('签字' in f for f in failures7), f'综合校验结果：{failures7}'

    print('PASS 测试7：证据包完整性校验（灰度矩阵+回滚shutdown+restore+四类样本清单+缺角色/缺回滚/缺restore失败）')


# ===== 测试8：端到端 API 闭环 =====

def test8_e2e_api_closure():
    """测试8：端到端 API 闭环（采集快照→查询快照→构建证据包→签字go/no-go）。"""
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        users = _create_users()
        _enable_ai_features()

    client = app.test_client()
    admin_id = users['admin']
    warehouse_id = users['warehouse']

    # 非 admin 被拒
    _login(client, warehouse_id)
    resp_denied = client.post('/api/ai/acceptance/daily_snapshot', json={'date': '2026-07-18'})
    assert resp_denied.status_code == 403, f'非 admin 应 403，实际 {resp_denied.status_code}'

    # admin 采集 7 天快照
    _login(client, admin_id)
    for i in range(7):
        d = (datetime(2026, 7, 12) + timedelta(days=i)).strftime('%Y-%m-%d')
        resp = client.post('/api/ai/acceptance/daily_snapshot', json={'date': d})
        assert resp.status_code == 200, f'采集 {d} 应 200，实际 {resp.status_code}：{resp.get_json()}'
        body = resp.get_json()
        assert body['status'] == 'ok', f'采集状态应 ok：{body}'
        assert body['snapshot']['snapshot_date'] == d

    # 查询快照列表
    resp_list = client.get('/api/ai/acceptance/daily_snapshots?limit=10')
    assert resp_list.status_code == 200
    list_body = resp_list.get_json()
    assert list_body['count'] >= 7, f'应至少 7 条快照，实际 {list_body["count"]}'

    # 构建证据包
    resp_pkg = client.post('/api/ai/acceptance/evidence_package', json={
        'end_date': '2026-07-18',
        'days': 7,
    })
    assert resp_pkg.status_code == 200, f'构建证据包应 200，实际 {resp_pkg.status_code}：{resp_pkg.get_json()}'
    pkg_body = resp_pkg.get_json()
    assert pkg_body['status'] == 'ok'
    assert pkg_body['package']['start_date'] == '2026-07-12'
    assert pkg_body['package']['end_date'] == '2026-07-18'
    assert pkg_body['seven_days_zero'] is True, '7 天全 0 应 seven_days_zero=True'
    package_db_id = pkg_body['package_db_id']

    # 查询证据包详情
    resp_detail = client.get(f'/api/ai/acceptance/evidence_package/{package_db_id}')
    assert resp_detail.status_code == 200
    detail_body = resp_detail.get_json()
    assert detail_body['package']['go_no_go_decision'] == 'pending'

    # 签字 go
    resp_go = client.post('/api/ai/acceptance/go_no_go', json={
        'package_id': package_db_id,
        'decision': 'go',
        'reason': '连续七天四项绝对指标全 0，验收通过',
    })
    assert resp_go.status_code == 200, f'签字 go 应 200，实际 {resp_go.status_code}：{resp_go.get_json()}'
    go_body = resp_go.get_json()
    assert go_body['decision'] == 'go'
    assert go_body['decided_by'] == admin_id

    # 再次签字 no_go（覆盖）
    resp_no_go = client.post('/api/ai/acceptance/go_no_go', json={
        'package_id': package_db_id,
        'decision': 'no_go',
        'reason': '重新评估后决定 no_go',
    })
    assert resp_no_go.status_code == 200
    assert resp_no_go.get_json()['decision'] == 'no_go'

    # 非法 decision
    resp_bad = client.post('/api/ai/acceptance/go_no_go', json={
        'package_id': package_db_id,
        'decision': 'maybe',
    })
    assert resp_bad.status_code == 400

    # 不存在的证据包
    resp_404 = client.get('/api/ai/acceptance/evidence_package/99999')
    assert resp_404.status_code == 404

    # 验证不修改业务数据和密码
    with app.app_context():
        in_order_count = wms_app.InOrder.query.count()
        out_order_count = wms_app.OutOrder.query.count()
        admin_user = wms_app.User.query.filter_by(id=admin_id).first()
        admin_pwd = admin_user.password_hash
    assert in_order_count == 0, '采集快照不应创建入库单'
    assert out_order_count == 0, '采集快照不应创建出库单'

    with app.app_context():
        admin_user2 = wms_app.User.query.filter_by(id=admin_id).first()
        assert admin_user2.password_hash == admin_pwd, '不得修改 admin 密码'

    print('PASS 测试8：端到端API闭环（采集7天快照→查询→构建证据包→签字go/no_go→非admin拒绝+不修改业务数据和密码）')


# ===== 主入口 =====

def main() -> int:
    tests = [
        test1_daily_snapshot_construction,
        test2_seven_consecutive_days_zero,
        test3_draft_adoption_reverse_check,
        test4_low_confidence_unconfirmed,
        test5_evidence_reproducible,
        test6_go_no_go_decision,
        test7_evidence_package_completeness,
        test8_e2e_api_closure,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            print(f'FAIL {test.__name__}: {exc}')
            import traceback
            traceback.print_exc()

    print()
    print('=== AI-R17-F02 Acceptance Evidence Verification Summary ===')
    print(f'total={len(tests)} passed={passed} failed={failed}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
