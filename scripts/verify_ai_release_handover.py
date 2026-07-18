"""AI-R17-F03 正式发布、备份恢复和运营交接验证脚本。
# AI_TASK: AI-R17-F03

验证内容：
1. 发布清单创建和验证流程
2. 备份记录创建、完成、失败和恢复
3. 恢复演练通过和失败场景
4. 回滚演练通过和失败场景
5. 交接文档创建和完成流程
6. 发布包组装和就绪度检查
7. 发布和回滚操作
8. 端到端闭环：清单→备份→演练→交接→发布→回滚

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ai.ops.release_handover import (  # noqa: E402
    BackupStatus,
    HandoverStatus,
    ReleaseStatus,
    attach_backup_to_release,
    attach_handover_document,
    attach_restore_drill,
    attach_rollback_drill,
    complete_backup,
    complete_handover,
    create_backup_record,
    create_handover_document,
    create_release_checklist,
    create_release_package,
    create_restore_drill,
    create_rollback_drill,
    fail_restore_drill,
    fail_rollback_drill,
    mark_backup_failed,
    pass_restore_drill,
    pass_rollback_drill,
    release_package,
    restore_backup,
    rollback_release,
    validate_release_readiness,
    verify_checklist_item,
)


def test1_release_checklist_creation() -> None:
    """测试1：发布清单创建和验证流程。"""
    checklist = create_release_checklist(
        release_id='REL-001',
        release_version='v1.0.0',
        created_by='admin',
    )

    assert checklist.release_id == 'REL-001'
    assert checklist.release_version == 'v1.0.0'
    assert checklist.status == ReleaseStatus.DRAFT
    assert checklist.total_items > 0, '应有清单项'
    assert len(checklist.required_items) > 0, '应有必填项'
    assert checklist.verified_items == 0, '初始无验证项'
    assert not checklist.is_ready, '初始未就绪'

    # 验证必填项
    required_item = checklist.required_items[0]
    updated = verify_checklist_item(
        checklist=checklist,
        item_id=required_item.item_id,
        verified_by='admin',
        evidence='测试证据',
    )

    assert updated.verified_items == 1, '应有1项已验证'
    assert updated.required_verified == 1, '必填项验证+1'
    assert not updated.is_ready, '部分验证仍不就绪'

    print('测试1 通过: 发布清单创建和验证流程')


def test2_backup_lifecycle() -> None:
    """测试2：备份记录创建、完成、失败和恢复。"""
    # 创建备份记录
    backup = create_backup_record(
        backup_id='BACKUP-001',
        backup_type='full',
        source_path='/data/wms.db',
        target_path='/backup/wms-20260718.db',
        created_by='admin',
    )

    assert backup.backup_id == 'BACKUP-001'
    assert backup.status == BackupStatus.PENDING
    assert not backup.is_valid, '待执行备份无效'

    # 完成备份
    completed = complete_backup(
        backup=backup,
        size_bytes=1024000,
        checksum='sha256:abc123',
    )

    assert completed.status == BackupStatus.COMPLETED
    assert completed.is_valid, '已完成且有校验和的备份有效'
    assert completed.duration_seconds >= 0, '耗时非负'

    # 恢复备份
    restored = restore_backup(
        backup=completed,
        restored_by='ops',
    )

    assert restored.status == BackupStatus.RESTORED
    assert restored.restored_by == 'ops'

    # 失败备份
    failed_backup = create_backup_record(
        backup_id='BACKUP-002',
        backup_type='full',
        source_path='/data/wms.db',
        target_path='/backup/wms-failed.db',
    )
    failed = mark_backup_failed(
        backup=failed_backup,
        notes='磁盘空间不足',
    )

    assert failed.status == BackupStatus.FAILED
    assert not failed.is_valid, '失败备份无效'

    # 尝试恢复失败备份应抛异常
    try:
        restore_backup(backup=failed, restored_by='ops')
        raise AssertionError('恢复失败备份应抛异常')
    except ValueError as e:
        assert '无效' in str(e)

    print('测试2 通过: 备份记录创建、完成、失败和恢复')


def test3_restore_drill() -> None:
    """测试3：恢复演练通过和失败场景。"""
    # 通过场景
    drill = create_restore_drill(
        drill_id='RESTORE-DRILL-001',
        backup_id='BACKUP-001',
    )

    assert drill.status == 'pending'
    assert not drill.is_passed, '初始未通过'

    passed = pass_restore_drill(
        drill=drill,
        restored_to='/test/wms.db',
        verified_by='ops',
    )

    assert passed.status == 'passed'
    assert passed.verified is True
    assert passed.is_passed, '已通过且已验证'
    assert passed.duration_seconds >= 0

    # 失败场景
    failed_drill = create_restore_drill(
        drill_id='RESTORE-DRILL-002',
        backup_id='BACKUP-002',
    )

    failed = fail_restore_drill(
        drill=failed_drill,
        issues=('备份文件损坏', '校验和不匹配'),
        notes='需要重新备份',
    )

    assert failed.status == 'failed'
    assert not failed.verified
    assert not failed.is_passed, '失败演练未通过'
    assert len(failed.issues) == 2

    print('测试3 通过: 恢复演练通过和失败场景')


def test4_rollback_drill() -> None:
    """测试4：回滚演练通过和失败场景。"""
    # 通过场景
    drill = create_rollback_drill(
        drill_id='ROLLBACK-DRILL-001',
        release_id='REL-001',
    )

    assert drill.status == 'pending'
    assert not drill.is_passed

    passed = pass_rollback_drill(
        drill=drill,
        rollback_target='v0.9.0',
        verified_by='ops',
    )

    assert passed.status == 'passed'
    assert passed.verified is True
    assert passed.is_passed
    assert passed.rollback_target == 'v0.9.0'

    # 失败场景
    failed_drill = create_rollback_drill(
        drill_id='ROLLBACK-DRILL-002',
        release_id='REL-002',
    )

    failed = fail_rollback_drill(
        drill=failed_drill,
        issues=('回滚脚本执行失败', '数据库迁移未回退'),
        notes='需要手动处理',
    )

    assert failed.status == 'failed'
    assert not failed.is_passed
    assert len(failed.issues) == 2

    print('测试4 通过: 回滚演练通过和失败场景')


def test5_handover_document() -> None:
    """测试5：交接文档创建和完成流程。"""
    doc = create_handover_document(
        document_id='HANDOVER-001',
        title='AI功能运维手册',
        content='包含监控、告警、应急处理等内容',
        author='dev-team',
    )

    assert doc.document_id == 'HANDOVER-001'
    assert doc.status == HandoverStatus.PENDING
    assert not doc.is_complete, '初始未完成'

    completed = complete_handover(
        document=doc,
        reviewers=('ops-team', 'admin'),
        verified_by='ops-lead',
    )

    assert completed.status == HandoverStatus.VERIFIED
    assert completed.is_complete, '已完成交接'
    assert len(completed.reviewers) == 2
    assert completed.verified_by == 'ops-lead'

    print('测试5 通过: 交接文档创建和完成流程')


def test6_release_package_readiness() -> None:
    """测试6：发布包组装和就绪度检查。"""
    # 创建清单
    checklist = create_release_checklist(
        release_id='REL-001',
        release_version='v1.0.0',
    )

    # 创建发布包
    package = create_release_package(
        release_id='REL-001',
        release_version='v1.0.0',
        checklist=checklist,
    )

    assert package.status == ReleaseStatus.DRAFT
    assert not package.is_ready_for_release, '初始不就绪'

    # 验证发布就绪度（缺少备份和演练）
    ready, reason, issues = validate_release_readiness(package=package)
    assert not ready, '缺少组件不就绪'
    assert '未附加备份记录' in issues

    # 附加备份
    backup = create_backup_record(
        backup_id='BACKUP-001',
        backup_type='full',
        source_path='/data/wms.db',
        target_path='/backup/wms.db',
    )
    completed_backup = complete_backup(
        backup=backup,
        size_bytes=1024000,
        checksum='sha256:abc123',
    )
    package = attach_backup_to_release(package=package, backup=completed_backup)

    # 附加恢复演练
    restore_drill = create_restore_drill(
        drill_id='RESTORE-001',
        backup_id='BACKUP-001',
    )
    passed_restore = pass_restore_drill(
        drill=restore_drill,
        restored_to='/test/wms.db',
        verified_by='ops',
    )
    package = attach_restore_drill(package=package, drill=passed_restore)

    # 附加回滚演练
    rollback_drill = create_rollback_drill(
        drill_id='ROLLBACK-001',
        release_id='REL-001',
    )
    passed_rollback = pass_rollback_drill(
        drill=rollback_drill,
        rollback_target='v0.9.0',
        verified_by='ops',
    )
    package = attach_rollback_drill(package=package, drill=passed_rollback)

    # 附加交接文档
    handover = create_handover_document(
        document_id='HANDOVER-001',
        title='运维手册',
        content='内容',
    )
    completed_handover = complete_handover(
        document=handover,
        reviewers=('ops',),
        verified_by='ops-lead',
    )
    package = attach_handover_document(package=package, document=completed_handover)

    # 验证清单未完成时仍不就绪
    ready, reason, issues = validate_release_readiness(package=package)
    assert not ready, '清单未完成不就绪'
    assert any('清单未完成' in issue for issue in issues)

    print('测试6 通过: 发布包组装和就绪度检查')


def test7_release_and_rollback() -> None:
    """测试7：发布和回滚操作。"""
    # 构建完整就绪的发布包
    checklist = create_release_checklist(
        release_id='REL-001',
        release_version='v1.0.0',
    )

    # 验证所有必填项
    for item in checklist.required_items:
        checklist = verify_checklist_item(
            checklist=checklist,
            item_id=item.item_id,
            verified_by='admin',
        )

    assert checklist.is_ready, '所有必填项验证后应就绪'

    package = create_release_package(
        release_id='REL-001',
        release_version='v1.0.0',
        checklist=checklist,
    )

    # 附加所有必需组件
    backup = complete_backup(
        backup=create_backup_record(
            backup_id='BACKUP-001',
            backup_type='full',
            source_path='/data/wms.db',
            target_path='/backup/wms.db',
        ),
        size_bytes=1024000,
        checksum='sha256:abc123',
    )
    package = attach_backup_to_release(package=package, backup=backup)

    restore_drill = pass_restore_drill(
        drill=create_restore_drill(drill_id='RESTORE-001', backup_id='BACKUP-001'),
        restored_to='/test/wms.db',
        verified_by='ops',
    )
    package = attach_restore_drill(package=package, drill=restore_drill)

    rollback_drill = pass_rollback_drill(
        drill=create_rollback_drill(drill_id='ROLLBACK-001', release_id='REL-001'),
        rollback_target='v0.9.0',
        verified_by='ops',
    )
    package = attach_rollback_drill(package=package, drill=rollback_drill)

    handover = complete_handover(
        document=create_handover_document(
            document_id='HANDOVER-001',
            title='运维手册',
            content='内容',
        ),
        reviewers=('ops',),
        verified_by='ops-lead',
    )
    package = attach_handover_document(package=package, document=handover)

    # 验证就绪
    ready, reason, issues = validate_release_readiness(package=package)
    assert ready, f'应就绪: {issues}'
    assert package.is_ready_for_release, '应可发布'

    # 发布
    released = release_package(
        package=package,
        released_by='admin',
    )

    assert released.status == ReleaseStatus.RELEASED
    assert released.released_by == 'admin'
    assert released.released_at is not None

    # 回滚
    rolled_back = rollback_release(
        package=released,
        rolled_back_by='ops',
    )

    assert rolled_back.status == ReleaseStatus.ROLLED_BACK
    assert rolled_back.rolled_back_by == 'ops'
    assert rolled_back.rolled_back_at is not None

    print('测试7 通过: 发布和回滚操作')


def test8_end_to_end() -> None:
    """测试8：端到端闭环。"""
    # 1. 创建发布清单
    checklist = create_release_checklist(
        release_id='REL-E2E',
        release_version='v2.0.0',
        created_by='dev-team',
    )
    assert checklist.total_items > 0

    # 2. 验证所有必填项
    for item in checklist.required_items:
        checklist = verify_checklist_item(
            checklist=checklist,
            item_id=item.item_id,
            verified_by='admin',
            evidence=f'证据-{item.item_id}',
        )

    assert checklist.is_ready
    assert checklist.required_completion_rate == 1.0

    # 3. 创建备份并完成
    backup = create_backup_record(
        backup_id='BACKUP-E2E',
        backup_type='full',
        source_path='/data/wms.db',
        target_path='/backup/wms-e2e.db',
        created_by='ops',
    )
    backup = complete_backup(
        backup=backup,
        size_bytes=2048000,
        checksum='sha256:e2e123',
    )
    assert backup.is_valid

    # 4. 恢复演练通过
    restore_drill = create_restore_drill(
        drill_id='RESTORE-E2E',
        backup_id='BACKUP-E2E',
    )
    restore_drill = pass_restore_drill(
        drill=restore_drill,
        restored_to='/test/wms-e2e.db',
        verified_by='ops',
    )
    assert restore_drill.is_passed

    # 5. 回滚演练通过
    rollback_drill = create_rollback_drill(
        drill_id='ROLLBACK-E2E',
        release_id='REL-E2E',
    )
    rollback_drill = pass_rollback_drill(
        drill=rollback_drill,
        rollback_target='v1.0.0',
        verified_by='ops',
    )
    assert rollback_drill.is_passed

    # 6. 交接文档完成
    handover = create_handover_document(
        document_id='HANDOVER-E2E',
        title='AI功能运维交接',
        content='包含监控、告警、应急处理',
        author='dev-team',
    )
    handover = complete_handover(
        document=handover,
        reviewers=('ops-team', 'admin'),
        verified_by='ops-lead',
    )
    assert handover.is_complete

    # 7. 组装发布包
    package = create_release_package(
        release_id='REL-E2E',
        release_version='v2.0.0',
        checklist=checklist,
    )
    package = attach_backup_to_release(package=package, backup=backup)
    package = attach_restore_drill(package=package, drill=restore_drill)
    package = attach_rollback_drill(package=package, drill=rollback_drill)
    package = attach_handover_document(package=package, document=handover)

    # 8. 验证就绪
    ready, reason, issues = validate_release_readiness(package=package)
    assert ready, f'应就绪: {issues}'
    assert package.is_ready_for_release

    # 9. 发布
    released = release_package(
        package=package,
        released_by='admin',
    )
    assert released.status == ReleaseStatus.RELEASED

    # 10. 回滚
    rolled_back = rollback_release(
        package=released,
        rolled_back_by='ops',
    )
    assert rolled_back.status == ReleaseStatus.ROLLED_BACK

    print('测试8 通过: 端到端闭环（清单→备份→演练→交接→发布→回滚）')


def main() -> int:
    try:
        test1_release_checklist_creation()
        test2_backup_lifecycle()
        test3_restore_drill()
        test4_rollback_drill()
        test5_handover_document()
        test6_release_package_readiness()
        test7_release_and_rollback()
        test8_end_to_end()
    except AssertionError as exc:
        print(f'FAIL AI-RELEASE-HANDOVER: {exc}')
        return 1
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        print(f'FAIL AI-RELEASE-HANDOVER: 异常 {exc}')
        return 1

    print('PASS AI-RELEASE-HANDOVER: 正式发布、备份恢复和运营交接 8 项测试全部通过')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
