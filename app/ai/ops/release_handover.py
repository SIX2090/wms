"""AI-R17-F03 正式发布、备份恢复和运营交接。

提供发布清单、备份恢复和运营交接的纯逻辑实现,与 ORM 和 Flask 解耦。

# AI_TASK: AI-R17-F03
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ReleaseStatus(str, Enum):
    """发布状态。"""
    DRAFT = 'draft'  # 草稿
    READY = 'ready'  # 待发布
    RELEASED = 'released'  # 已发布
    ROLLED_BACK = 'rolled_back'  # 已回滚
    FAILED = 'failed'  # 失败


class BackupStatus(str, Enum):
    """备份状态。"""
    PENDING = 'pending'  # 待执行
    IN_PROGRESS = 'in_progress'  # 执行中
    COMPLETED = 'completed'  # 已完成
    FAILED = 'failed'  # 失败
    RESTORED = 'restored'  # 已恢复


class HandoverStatus(str, Enum):
    """交接状态。"""
    PENDING = 'pending'  # 待交接
    IN_PROGRESS = 'in_progress'  # 交接中
    COMPLETED = 'completed'  # 已完成
    VERIFIED = 'verified'  # 已验收


@dataclass(frozen=True)
class ReleaseChecklistItem:
    """发布清单项。"""
    item_id: str
    category: str  # code/test/data/config/ops/training
    title: str
    description: str
    required: bool = True
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    evidence: Optional[str] = None  # 证据描述或链接

    @property
    def is_complete(self) -> bool:
        """是否完成(必填项必须验证)。"""
        if self.required:
            return self.verified
        return True


@dataclass(frozen=True)
class ReleaseChecklist:
    """发布清单。"""
    release_id: str
    release_version: str
    created_at: datetime
    items: tuple[ReleaseChecklistItem, ...]
    status: ReleaseStatus = ReleaseStatus.DRAFT
    created_by: Optional[str] = None
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None

    @property
    def total_items(self) -> int:
        return len(self.items)

    @property
    def verified_items(self) -> int:
        return sum(1 for item in self.items if item.verified)

    @property
    def required_items(self) -> tuple[ReleaseChecklistItem, ...]:
        return tuple(item for item in self.items if item.required)

    @property
    def required_verified(self) -> int:
        return sum(1 for item in self.required_items if item.verified)

    @property
    def is_ready(self) -> bool:
        """是否就绪(所有必填项已验证)。"""
        return all(item.is_complete for item in self.required_items)

    @property
    def completion_rate(self) -> float:
        """完成率。"""
        if self.total_items == 0:
            return 0.0
        return self.verified_items / self.total_items

    @property
    def required_completion_rate(self) -> float:
        """必填项完成率。"""
        required = self.required_items
        if not required:
            return 0.0
        return self.required_verified / len(required)


@dataclass(frozen=True)
class BackupRecord:
    """备份记录。"""
    backup_id: str
    backup_type: str  # full/incremental/config
    source_path: str
    target_path: str
    created_at: datetime
    status: BackupStatus = BackupStatus.PENDING
    size_bytes: int = 0
    checksum: Optional[str] = None
    created_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    restored_at: Optional[datetime] = None
    restored_by: Optional[str] = None
    notes: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """备份耗时(秒)。"""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.created_at).total_seconds()

    @property
    def is_valid(self) -> bool:
        """备份是否有效(已完成且有校验和)。"""
        return self.status == BackupStatus.COMPLETED and self.checksum is not None


@dataclass(frozen=True)
class RestoreDrill:
    """恢复演练记录。"""
    drill_id: str
    backup_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = 'pending'  # pending/running/passed/failed
    restored_to: Optional[str] = None
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    issues: tuple[str, ...] = ()
    notes: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """演练耗时(秒)。"""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def is_passed(self) -> bool:
        """演练是否通过。"""
        return self.status == 'passed' and self.verified


@dataclass(frozen=True)
class RollbackDrill:
    """回滚演练记录。"""
    drill_id: str
    release_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = 'pending'  # pending/running/passed/failed
    rollback_target: Optional[str] = None
    verified: bool = False
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    issues: tuple[str, ...] = ()
    notes: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        """演练耗时(秒)。"""
        if not self.completed_at:
            return 0.0
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def is_passed(self) -> bool:
        """演练是否通过。"""
        return self.status == 'passed' and self.verified


@dataclass(frozen=True)
class HandoverDocument:
    """交接文档。"""
    document_id: str
    title: str
    content: str
    created_at: datetime
    status: HandoverStatus = HandoverStatus.PENDING
    author: Optional[str] = None
    reviewers: tuple[str, ...] = ()
    reviewed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    attachments: tuple[str, ...] = ()  # 附件路径

    @property
    def is_complete(self) -> bool:
        """交接是否完成。"""
        return self.status in (HandoverStatus.COMPLETED, HandoverStatus.VERIFIED)


@dataclass(frozen=True)
class ReleasePackage:
    """发布包。"""
    release_id: str
    release_version: str
    created_at: datetime
    checklist: ReleaseChecklist
    backup: Optional[BackupRecord] = None
    restore_drills: tuple[RestoreDrill, ...] = ()
    rollback_drills: tuple[RollbackDrill, ...] = ()
    handover_documents: tuple[HandoverDocument, ...] = ()
    status: ReleaseStatus = ReleaseStatus.DRAFT
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None
    rolled_back_at: Optional[datetime] = None
    rolled_back_by: Optional[str] = None

    @property
    def is_ready_for_release(self) -> bool:
        """是否可发布。"""
        if not self.checklist.is_ready:
            return False
        if not self.backup or not self.backup.is_valid:
            return False
        if not all(drill.is_passed for drill in self.restore_drills):
            return False
        if not all(drill.is_passed for drill in self.rollback_drills):
            return False
        if not all(doc.is_complete for doc in self.handover_documents):
            return False
        return True

    @property
    def has_critical_issues(self) -> bool:
        """是否有严重问题。"""
        for drill in self.restore_drills:
            if drill.status == 'failed':
                return True
        for drill in self.rollback_drills:
            if drill.status == 'failed':
                return True
        return False


# 依赖注入类型别名
QueryChecklistFn = Callable[[str], Optional[ReleaseChecklist]]
QueryBackupFn = Callable[[str], Optional[BackupRecord]]
QueryDrillFn = Callable[[str], Optional[RestoreDrill | RollbackDrill]]
QueryHandoverFn = Callable[[str], Optional[HandoverDocument]]


def create_release_checklist(
    *,
    release_id: str,
    release_version: str,
    created_at: Optional[datetime] = None,
    created_by: Optional[str] = None,
) -> ReleaseChecklist:
    """创建发布清单。

    包含标准发布清单项:代码、测试、数据、配置、运维、培训。
    """
    now = created_at or datetime.utcnow()

    items = [
        ReleaseChecklistItem(
            item_id=f'{release_id}-CODE-001',
            category='code',
            title='代码已合并 main',
            description='所有功能代码已合并到 main 分支,无未解决冲突',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-CODE-002',
            category='code',
            title='编码检查通过',
            description='Python 源码编码检查(UTF-8)通过',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TEST-001',
            category='test',
            title='full 验证通过',
            description='verify_ai_all.py --level full 全部通过',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TEST-002',
            category='test',
            title='专项测试通过',
            description='所有新增功能的专项测试脚本通过',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TEST-003',
            category='test',
            title='回归测试通过',
            description='WMS 回归测试无新增失败',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-DATA-001',
            category='data',
            title='数据库迁移已准备',
            description='数据库 Schema 变更已准备迁移脚本',
            required=False,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-DATA-002',
            category='data',
            title='数据备份已完成',
            description='生产数据库已备份,备份文件可恢复',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-CONFIG-001',
            category='config',
            title='配置已更新',
            description='环境变量、配置文件已更新',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-CONFIG-002',
            category='config',
            title='Feature Flag 已配置',
            description='新功能开关已配置,默认关闭',
            required=False,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-OPS-001',
            category='ops',
            title='监控告警已配置',
            description='关键指标监控和告警已配置',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-OPS-002',
            category='ops',
            title='回滚方案已准备',
            description='回滚步骤和回滚脚本已准备',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-OPS-003',
            category='ops',
            title='恢复演练已通过',
            description='备份恢复演练通过,恢复时间 < 30 分钟',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-OPS-004',
            category='ops',
            title='回滚演练已通过',
            description='回滚演练通过,回滚时间 < 10 分钟',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TRAIN-001',
            category='training',
            title='用户培训已完成',
            description='目标用户已完成培训,了解新功能',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TRAIN-002',
            category='training',
            title='运维交接已完成',
            description='运维团队已完成交接,了解监控和应急处理',
            required=True,
        ),
        ReleaseChecklistItem(
            item_id=f'{release_id}-TRAIN-003',
            category='training',
            title='文档已更新',
            description='用户手册、运维手册已更新',
            required=True,
        ),
    ]

    return ReleaseChecklist(
        release_id=release_id,
        release_version=release_version,
        created_at=now,
        items=tuple(items),
        status=ReleaseStatus.DRAFT,
        created_by=created_by,
    )


def verify_checklist_item(
    *,
    checklist: ReleaseChecklist,
    item_id: str,
    verified_by: str,
    verified_at: Optional[datetime] = None,
    evidence: Optional[str] = None,
) -> ReleaseChecklist:
    """验证清单项。

    返回更新后的清单(不可变数据结构的副本)。
    """
    now = verified_at or datetime.utcnow()
    updated_items = []
    found = False

    for item in checklist.items:
        if item.item_id == item_id:
            found = True
            updated_items.append(ReleaseChecklistItem(
                item_id=item.item_id,
                category=item.category,
                title=item.title,
                description=item.description,
                required=item.required,
                verified=True,
                verified_by=verified_by,
                verified_at=now,
                evidence=evidence or item.evidence,
            ))
        else:
            updated_items.append(item)

    if not found:
        raise ValueError(f'清单项 {item_id} 不存在')

    new_status = ReleaseStatus.READY if all(
        item.is_complete for item in updated_items if item.required
    ) else checklist.status

    return ReleaseChecklist(
        release_id=checklist.release_id,
        release_version=checklist.release_version,
        created_at=checklist.created_at,
        items=tuple(updated_items),
        status=new_status,
        created_by=checklist.created_by,
        released_at=checklist.released_at,
        released_by=checklist.released_by,
    )


def create_backup_record(
    *,
    backup_id: str,
    backup_type: str,
    source_path: str,
    target_path: str,
    created_by: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> BackupRecord:
    """创建备份记录。"""
    return BackupRecord(
        backup_id=backup_id,
        backup_type=backup_type,
        source_path=source_path,
        target_path=target_path,
        created_at=created_at or datetime.utcnow(),
        status=BackupStatus.PENDING,
        created_by=created_by,
    )


def complete_backup(
    *,
    backup: BackupRecord,
    size_bytes: int,
    checksum: str,
    completed_at: Optional[datetime] = None,
) -> BackupRecord:
    """完成备份。"""
    return BackupRecord(
        backup_id=backup.backup_id,
        backup_type=backup.backup_type,
        source_path=backup.source_path,
        target_path=backup.target_path,
        created_at=backup.created_at,
        status=BackupStatus.COMPLETED,
        size_bytes=size_bytes,
        checksum=checksum,
        created_by=backup.created_by,
        completed_at=completed_at or datetime.utcnow(),
        restored_at=backup.restored_at,
        restored_by=backup.restored_by,
        notes=backup.notes,
    )


def mark_backup_failed(
    *,
    backup: BackupRecord,
    notes: Optional[str] = None,
) -> BackupRecord:
    """标记备份失败。"""
    return BackupRecord(
        backup_id=backup.backup_id,
        backup_type=backup.backup_type,
        source_path=backup.source_path,
        target_path=backup.target_path,
        created_at=backup.created_at,
        status=BackupStatus.FAILED,
        size_bytes=backup.size_bytes,
        checksum=backup.checksum,
        created_by=backup.created_by,
        completed_at=backup.completed_at,
        restored_at=backup.restored_at,
        restored_by=backup.restored_by,
        notes=notes or backup.notes,
    )


def restore_backup(
    *,
    backup: BackupRecord,
    restored_by: str,
    restored_at: Optional[datetime] = None,
) -> BackupRecord:
    """恢复备份。"""
    if not backup.is_valid:
        raise ValueError(f'备份 {backup.backup_id} 无效,无法恢复')

    return BackupRecord(
        backup_id=backup.backup_id,
        backup_type=backup.backup_type,
        source_path=backup.source_path,
        target_path=backup.target_path,
        created_at=backup.created_at,
        status=BackupStatus.RESTORED,
        size_bytes=backup.size_bytes,
        checksum=backup.checksum,
        created_by=backup.created_by,
        completed_at=backup.completed_at,
        restored_at=restored_at or datetime.utcnow(),
        restored_by=restored_by,
        notes=backup.notes,
    )


def create_restore_drill(
    *,
    drill_id: str,
    backup_id: str,
    started_at: Optional[datetime] = None,
) -> RestoreDrill:
    """创建恢复演练记录。"""
    return RestoreDrill(
        drill_id=drill_id,
        backup_id=backup_id,
        started_at=started_at or datetime.utcnow(),
    )


def pass_restore_drill(
    *,
    drill: RestoreDrill,
    restored_to: str,
    verified_by: str,
    completed_at: Optional[datetime] = None,
    verified_at: Optional[datetime] = None,
) -> RestoreDrill:
    """通过恢复演练。"""
    now = completed_at or datetime.utcnow()
    return RestoreDrill(
        drill_id=drill.drill_id,
        backup_id=drill.backup_id,
        started_at=drill.started_at,
        completed_at=now,
        status='passed',
        restored_to=restored_to,
        verified=True,
        verified_by=verified_by,
        verified_at=verified_at or now,
        issues=drill.issues,
        notes=drill.notes,
    )


def fail_restore_drill(
    *,
    drill: RestoreDrill,
    issues: tuple[str, ...],
    completed_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> RestoreDrill:
    """失败恢复演练。"""
    return RestoreDrill(
        drill_id=drill.drill_id,
        backup_id=drill.backup_id,
        started_at=drill.started_at,
        completed_at=completed_at or datetime.utcnow(),
        status='failed',
        restored_to=drill.restored_to,
        verified=False,
        verified_by=drill.verified_by,
        verified_at=drill.verified_at,
        issues=issues,
        notes=notes or drill.notes,
    )


def create_rollback_drill(
    *,
    drill_id: str,
    release_id: str,
    started_at: Optional[datetime] = None,
) -> RollbackDrill:
    """创建回滚演练记录。"""
    return RollbackDrill(
        drill_id=drill_id,
        release_id=release_id,
        started_at=started_at or datetime.utcnow(),
    )


def pass_rollback_drill(
    *,
    drill: RollbackDrill,
    rollback_target: str,
    verified_by: str,
    completed_at: Optional[datetime] = None,
    verified_at: Optional[datetime] = None,
) -> RollbackDrill:
    """通过回滚演练。"""
    now = completed_at or datetime.utcnow()
    return RollbackDrill(
        drill_id=drill.drill_id,
        release_id=drill.release_id,
        started_at=drill.started_at,
        completed_at=now,
        status='passed',
        rollback_target=rollback_target,
        verified=True,
        verified_by=verified_by,
        verified_at=verified_at or now,
        issues=drill.issues,
        notes=drill.notes,
    )


def fail_rollback_drill(
    *,
    drill: RollbackDrill,
    issues: tuple[str, ...],
    completed_at: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> RollbackDrill:
    """失败回滚演练。"""
    return RollbackDrill(
        drill_id=drill.drill_id,
        release_id=drill.release_id,
        started_at=drill.started_at,
        completed_at=completed_at or datetime.utcnow(),
        status='failed',
        rollback_target=drill.rollback_target,
        verified=False,
        verified_by=drill.verified_by,
        verified_at=drill.verified_at,
        issues=issues,
        notes=notes or drill.notes,
    )


def create_handover_document(
    *,
    document_id: str,
    title: str,
    content: str,
    author: Optional[str] = None,
    created_at: Optional[datetime] = None,
) -> HandoverDocument:
    """创建交接文档。"""
    return HandoverDocument(
        document_id=document_id,
        title=title,
        content=content,
        created_at=created_at or datetime.utcnow(),
        status=HandoverStatus.PENDING,
        author=author,
    )


def complete_handover(
    *,
    document: HandoverDocument,
    reviewers: tuple[str, ...],
    verified_by: str,
    reviewed_at: Optional[datetime] = None,
    verified_at: Optional[datetime] = None,
) -> HandoverDocument:
    """完成交接。"""
    now_reviewed = reviewed_at or datetime.utcnow()
    now_verified = verified_at or now_reviewed

    return HandoverDocument(
        document_id=document.document_id,
        title=document.title,
        content=document.content,
        created_at=document.created_at,
        status=HandoverStatus.VERIFIED,
        author=document.author,
        reviewers=reviewers,
        reviewed_at=now_reviewed,
        verified_at=now_verified,
        verified_by=verified_by,
        attachments=document.attachments,
    )


def create_release_package(
    *,
    release_id: str,
    release_version: str,
    checklist: ReleaseChecklist,
    created_at: Optional[datetime] = None,
) -> ReleasePackage:
    """创建发布包。"""
    return ReleasePackage(
        release_id=release_id,
        release_version=release_version,
        created_at=created_at or datetime.utcnow(),
        checklist=checklist,
    )


def attach_backup_to_release(
    *,
    package: ReleasePackage,
    backup: BackupRecord,
) -> ReleasePackage:
    """附加备份到发布包。"""
    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=backup,
        restore_drills=package.restore_drills,
        rollback_drills=package.rollback_drills,
        handover_documents=package.handover_documents,
        status=package.status,
        released_at=package.released_at,
        released_by=package.released_by,
        rolled_back_at=package.rolled_back_at,
        rolled_back_by=package.rolled_back_by,
    )


def attach_restore_drill(
    *,
    package: ReleasePackage,
    drill: RestoreDrill,
) -> ReleasePackage:
    """附加恢复演练到发布包。"""
    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=package.backup,
        restore_drills=package.restore_drills + (drill,),
        rollback_drills=package.rollback_drills,
        handover_documents=package.handover_documents,
        status=package.status,
        released_at=package.released_at,
        released_by=package.released_by,
        rolled_back_at=package.rolled_back_at,
        rolled_back_by=package.rolled_back_by,
    )


def attach_rollback_drill(
    *,
    package: ReleasePackage,
    drill: RollbackDrill,
) -> ReleasePackage:
    """附加回滚演练到发布包。"""
    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=package.backup,
        restore_drills=package.restore_drills,
        rollback_drills=package.rollback_drills + (drill,),
        handover_documents=package.handover_documents,
        status=package.status,
        released_at=package.released_at,
        released_by=package.released_by,
        rolled_back_at=package.rolled_back_at,
        rolled_back_by=package.rolled_back_by,
    )


def attach_handover_document(
    *,
    package: ReleasePackage,
    document: HandoverDocument,
) -> ReleasePackage:
    """附加交接文档到发布包。"""
    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=package.backup,
        restore_drills=package.restore_drills,
        rollback_drills=package.rollback_drills,
        handover_documents=package.handover_documents + (document,),
        status=package.status,
        released_at=package.released_at,
        released_by=package.released_by,
        rolled_back_at=package.rolled_back_at,
        rolled_back_by=package.rolled_back_by,
    )


def release_package(
    *,
    package: ReleasePackage,
    released_by: str,
    released_at: Optional[datetime] = None,
) -> ReleasePackage:
    """发布。"""
    if not package.is_ready_for_release:
        raise ValueError('发布包未就绪,无法发布')

    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=package.backup,
        restore_drills=package.restore_drills,
        rollback_drills=package.rollback_drills,
        handover_documents=package.handover_documents,
        status=ReleaseStatus.RELEASED,
        released_at=released_at or datetime.utcnow(),
        released_by=released_by,
        rolled_back_at=package.rolled_back_at,
        rolled_back_by=package.rolled_back_by,
    )


def rollback_release(
    *,
    package: ReleasePackage,
    rolled_back_by: str,
    rolled_back_at: Optional[datetime] = None,
) -> ReleasePackage:
    """回滚发布。"""
    return ReleasePackage(
        release_id=package.release_id,
        release_version=package.release_version,
        created_at=package.created_at,
        checklist=package.checklist,
        backup=package.backup,
        restore_drills=package.restore_drills,
        rollback_drills=package.rollback_drills,
        handover_documents=package.handover_documents,
        status=ReleaseStatus.ROLLED_BACK,
        released_at=package.released_at,
        released_by=package.released_by,
        rolled_back_at=rolled_back_at or datetime.utcnow(),
        rolled_back_by=rolled_back_by,
    )


def validate_release_readiness(
    *,
    package: ReleasePackage,
) -> tuple[bool, str, list[str]]:
    """验证发布就绪度。

    返回 (是否就绪, 原因, 问题列表)。
    """
    issues = []

    if not package.checklist.is_ready:
        missing = [
            item.item_id for item in package.checklist.required_items
            if not item.verified
        ]
        issues.append(f'发布清单未完成,缺少验证: {", ".join(missing[:5])}')

    if not package.backup:
        issues.append('未附加备份记录')
    elif not package.backup.is_valid:
        issues.append(f'备份 {package.backup.backup_id} 无效')

    failed_restore = [d for d in package.restore_drills if d.status == 'failed']
    if failed_restore:
        issues.append(f'恢复演练失败: {", ".join(d.drill_id for d in failed_restore)}')

    unverified_restore = [d for d in package.restore_drills if not d.verified]
    if unverified_restore:
        issues.append(f'恢复演练未验证: {", ".join(d.drill_id for d in unverified_restore)}')

    failed_rollback = [d for d in package.rollback_drills if d.status == 'failed']
    if failed_rollback:
        issues.append(f'回滚演练失败: {", ".join(d.drill_id for d in failed_rollback)}')

    unverified_rollback = [d for d in package.rollback_drills if not d.verified]
    if unverified_rollback:
        issues.append(f'回滚演练未验证: {", ".join(d.drill_id for d in unverified_rollback)}')

    incomplete_handover = [d for d in package.handover_documents if not d.is_complete]
    if incomplete_handover:
        issues.append(f'交接文档未完成: {", ".join(d.document_id for d in incomplete_handover)}')

    if issues:
        return False, '发布未就绪', issues

    return True, '发布就绪', []
