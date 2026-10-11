# -*- coding: utf-8 -*-
"""WMS Schema 元数据摘要（AI 提示词注入用）。

依据：开源 WMS/ERP AI 助手调研（ERPNext Copilot / SuperSonic / GenAI Protos）
——为 LLM 提供表结构、字段语义和常用查询模式，可将自然语言查询准确率
从 40-55% 提升至 70-85%。

设计约束（AGENTS.md）：
- 纯常量文本，不做数据库反射（表结构稳定，避免每次请求额外查询）。
- 只在调用 LLM 的路径注入；机械回退路径不注入（不增加耗时）。
- 字段语义必须与 models 里的命名约定一致（如 reorder_point 对外叫「安全库存」）。
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# 物料档案（material 表）
# ---------------------------------------------------------------------------
MATERIAL_SCHEMA = """【物料档案表 material】（约千级记录，中文主数据）
- code: 物料编码（唯一，如 LPY0001、207012），用户常用编码或名称指代物料
- name: 物料名称（如「铜排」「指示灯」；同名不同规格的物料有多条记录，如 38 种「铜排」）
- spec: 规格型号（如 140*6、AD16-22D/S红色、M8*20；可能含颜色/单位后缀）
- brand: 品牌；category/unit/supplier: 关联类别、计量单位、供应商
- stock: 当前库存（冗余汇总值，精确库存按仓库流水聚合）
- min_stock: 最低库存（红线）；reorder_point: 安全库存（对外叫「安全库存」，低于它建议补货）
- status: active/inactive（停用物料历史数据照常可查）
常用查询：按名称/编码模糊搜物料；按规格过滤（注意规格边界，6*10 不能匹配 SM76*10）"""

# ---------------------------------------------------------------------------
# 库存流水（stock_transaction 表）
# ---------------------------------------------------------------------------
STOCK_TRANSACTION_SCHEMA = """【库存流水表 stock_transaction】（只增不改，按时间倒序查）
- material_id: 关联物料（同名多规格需聚合全部 material_id 一起查）
- transaction_type: in入库 / out出库 / transfer_in调入 / transfer_out调出 / adjustment_in盘盈 / adjustment_out盘亏
- quantity: 变动数量（正=增加，负=减少；出库合计取负数绝对值）
- warehouse_id / location: 仓库归属（历史行可能为 NULL）
- reference_type / reference_id: 关联单据（in_order/out_order/transfer/adjustment/check）
- created_at: 发生时间；operator_id: 操作员
常用查询：某物料近 N 天入库/出库合计与笔数；按时间范围（今天/昨天/本周/上周/本月/上月/最近N天）"""

# ---------------------------------------------------------------------------
# 单据表（简要）
# ---------------------------------------------------------------------------
ORDER_SCHEMA = """【单据表】
- in_order / in_order_item: 入库单及明细（status: 草稿→待审核→已完成）
- out_order / out_order_item: 出库/领料单及明细（含 picker 领料人、location 库位）
- adjustment_order / inventory_check: 库存调整单、盘点单（草稿不扣库存，提交后才生效）"""

SCHEMA_BY_QUERY_TYPE = {
    'stock': MATERIAL_SCHEMA,
    'flow': MATERIAL_SCHEMA + '\n\n' + STOCK_TRANSACTION_SCHEMA,
    'order': MATERIAL_SCHEMA + '\n\n' + ORDER_SCHEMA,
    'all': MATERIAL_SCHEMA + '\n\n' + STOCK_TRANSACTION_SCHEMA + '\n\n' + ORDER_SCHEMA,
}


def get_schema_meta(query_type: str = 'all') -> str:
    """按查询类型返回 Schema 摘要文本（未知类型返回全集）。"""
    return SCHEMA_BY_QUERY_TYPE.get(query_type, SCHEMA_BY_QUERY_TYPE['all'])
