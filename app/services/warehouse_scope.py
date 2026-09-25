# -*- coding: utf-8 -*-
# 单据表仓库过滤的唯一判据（R6 收口，2026-09-25）。
#
# 背景：报表链路此前存在三种互斥的仓库判据——
#   A. 单据表裸字符串匹配（InOrder.warehouse == filters['warehouse']）
#   B. warehouse_id 外键 + 仓库级聚合（get_warehouse_stock_quantities）
#   C. warehouse_id 优先 + location 字符串兜底（_warehouse_scoped_txn_condition）
# A 最脆弱：单据表 warehouse 为 String(100)，改名即失配、混存即漏查、
# 且全程静默。台账「仓库」根因出现 198 次，为第一大来源。
#
# 本模块把「单据表（InOrder/OutOrder/InventoryCheck/SubcontractOrder/
# ProductionRequisition 等）」的仓库过滤收口到唯一函数，杜绝「修一处漏一处」。
#
# 判据演进（分阶段，不夹带）：
# - 阶段一（本文件当前实现）：单据表尚无 warehouse_id 外键，函数内只做
#   仓库名/编码字符串匹配，行为与既有 7 处调用点逐字一致（零行为变更）。
# - 阶段二（待专项评估）：照抄 OpeningStock / SalesOrder 已完成的改造模式
#   （加 warehouse_id 列 + 写入端落 ID + 启动幂等回填），届时仅需修改本
#   函数内部实现，即可全报表生效为 C 判据（ID 优先 + location 兜底）。
#   回填不了的历史行保留 NULL，不猜（INVENTORY_TRUTH.md §3.2）。
#
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明（lint 折叠行号偏移问题，
# 见 routes/adjustment.py 与 services/warehouse_stock_service.py 同注）。

from __future__ import annotations


def document_warehouse_filter(model, warehouse_name=None, warehouse_code=None):
    """单据表仓库过滤的唯一判据，返回 SQLAlchemy 条件或 None。

    参数：
        model: 单据模型类（需具备 `warehouse` 字符串列）。
        warehouse_name: 仓库名（filters['warehouse']）。
        warehouse_code: 仓库编码（filters['warehouse_code']）。

    返回：
        SQLAlchemy 布尔条件（`or_`）；两参数均为空时返回 None，调用方应
        跳过过滤（不得退化为「匹配全部」以外的语义）。

    兼容说明：单据 warehouse 字段历史上混存仓库名与仓库编码——
    手机端手工录入存编码、网页端存名称，故两者任一匹配（BUG-2026-08-02-014 /
    BUG-2026-08-18-004 既有口径）。名称与编码相同时不重复追加条件。
    """
    # 延迟导入 db：app.py 加载期即导入本模块会形成循环导入
    # （与 services/warehouse_stock_service.py 同一定式）。
    from app import db

    name = (warehouse_name or '').strip() if isinstance(warehouse_name, str) else (warehouse_name or '')
    code = (warehouse_code or '').strip() if isinstance(warehouse_code, str) else (warehouse_code or '')

    match_any = []
    if name:
        match_any.append(model.warehouse == name)
    if code and code != name:
        match_any.append(model.warehouse == code)
    if not match_any:
        return None
    return db.or_(*match_any)
