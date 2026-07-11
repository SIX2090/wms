from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class AIKnowledgeEntry:
    key: str
    title: str
    summary: str
    rule: str
    page_endpoint: str
    page_label: str
    keywords: tuple[str, ...]
    data_boundary: str = '知识库只解释规则和入口；库存、单据、金额和数量必须实时查询数据库。'


AI_KNOWLEDGE_BASE: tuple[AIKnowledgeEntry, ...] = (
    AIKnowledgeEntry(
        key='purchase_receive_sop',
        title='采购到货入库 SOP',
        summary='采购订单到货后，从采购订单下推采购入库草稿，核对仓库、物料和数量后再提交完成。',
        rule='采购入库必须关联采购订单；送货单识别只能生成草稿或确认页，不能直接完成入库。',
        page_endpoint='purchase_order_list',
        page_label='采购订单',
        keywords=('采购入库', '到货入库', '送货单入库', '收货', '来料', '采购订单下推', '入库SOP', '采购SOP'),
    ),
    AIKnowledgeEntry(
        key='warehouse_issue_sop',
        title='领料/出库 SOP',
        summary='领料出库先创建出库草稿，核对物料、数量、用途和库存后提交，完成时才扣减库存。',
        rule='AI 可以生成领料草稿，但不得自动完成出库；库存不足时需要先处理负库存、调拨或采购补货。',
        page_endpoint='out_order_list',
        page_label='出库/领料单',
        keywords=('领料', '出库', '发料', '扣库存', '领料SOP', '出库SOP'),
    ),
    AIKnowledgeEntry(
        key='stocktake_sop',
        title='盘点差异 SOP',
        summary='盘点先生成盘点单，录入实盘数后完成盘点；差异通过库存调整草稿闭环。',
        rule='盘点完成不得直接静默改库存，必须保留盘点单、差异和调整草稿的审计链路。',
        page_endpoint='check_list',
        page_label='盘点单',
        keywords=('盘点', '盘库', '盘点差异', '库存差异', '调整库存', '盘点SOP'),
    ),
    AIKnowledgeEntry(
        key='master_data_sop',
        title='基础资料维护 SOP',
        summary='基础资料按仓库、单位、分类、供应商/客户、物料档案顺序维护，导入后运行基础资料体检。',
        rule='物料编码必须稳定唯一；单位、分类、默认供应商和库存预警规则会影响扫码、采购和库存分析。',
        page_endpoint='material_list',
        page_label='物料档案',
        keywords=('基础资料', '主数据', '物料档案', '供应商档案', '客户档案', '资料导入', '主数据SOP'),
    ),
    AIKnowledgeEntry(
        key='pending_status_rule',
        title='单据状态和待办规则',
        summary='草稿/待审核/处理中单据进入待处理中心，完成、关闭、作废类状态不再作为待办。',
        rule='AI 只能定位待办和解释下一动作，提交、审核、完成、反审、作废和删除必须由用户在业务页面确认。',
        page_endpoint='pending_documents',
        page_label='待处理中心',
        keywords=('待办', '待处理', '单据状态', '状态机', '下一步', '审核', '完成', '作废'),
    ),
    AIKnowledgeEntry(
        key='inventory_report_basis',
        title='库存分析报表口径',
        summary='库存金额按当前库存数量乘物料参考价估算；周转和消耗趋势按库存流水统计。',
        rule='报表口径必须标注查询时间、范围和数据表；知识库不能替代实时库存查询。',
        page_endpoint='stock_query',
        page_label='库存查询',
        keywords=('库存金额', '周转', '滞销', '消耗趋势', '报表口径', '数据来源', '库存分析'),
    ),
)


def search_knowledge_entries(message: str, limit: int = 4) -> list[AIKnowledgeEntry]:
    compact = (message or '').replace(' ', '').lower()
    if not compact:
        return []

    scored: list[tuple[int, AIKnowledgeEntry]] = []
    for entry in AI_KNOWLEDGE_BASE:
        score = 0
        for keyword in entry.keywords:
            normalized = keyword.replace(' ', '').lower()
            if normalized and normalized in compact:
                score += max(1, len(normalized))
        if score:
            scored.append((score, entry))

    scored.sort(key=lambda row: (row[0], row[1].key), reverse=True)
    return [entry for _score, entry in scored[:limit]]


def is_knowledge_question(message: str) -> bool:
    compact = (message or '').replace(' ', '').lower()
    if not compact:
        return False
    markers: Iterable[str] = (
        'sop', '流程', '怎么操作', '怎么处理', '规则', '口径', '字段', '状态',
        '知识库', '数据来源', '页面入口', '到哪里', '怎么入库', '怎么出库',
    )
    return any(marker in compact for marker in markers) and bool(search_knowledge_entries(message, limit=1))
