# -*- coding: utf-8 -*-
# 库存三账写入唯一入口（P2-3 收敛，2026-09-20）。
#
# 背景（INVENTORY_TRUTH.md §2.1）：add_stock / deduct_stock_atomic 只写
# ①总账 + ③流水，②库位账必须由调用方再调 update_location_inventory
# （「新代码必须两层同时写」）。历史上漏写导致 BUG-2026-09-20-008 型
# 静默账实分裂（①减②不变、无任何报错）。本模块把「总账 + 流水 + 库位账」
# 收敛为一次调用，业务路径只允许经此入口写库存。
#
# 设计约束（纯重构，不改行为）：
# - 内部原样调用 app.py 既有原语，保留全部既有修复（原子条件扣减、
#   BUG-2026-09-19-001 未归属兜底、BUG-2026-08-04-002 无库位记录显式报错）。
# - 库位键口径 location or warehouse，与存量 22 处双写定式逐字一致。
# - 失败语义与底层一致：返回 (False, msg)，由调用方负责 db.session.rollback()。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明（lint 折叠行号偏移问题，
# 见 routes/adjustment.py 同注）。

from __future__ import annotations


def apply_stock_delta(material, delta, *, transaction_type, reference_type=None,
                      reference_id=None, remark='', warehouse=None, location=None):
    """库存三账（①总账 + ③流水 + ②库位账）写入唯一入口。

    参数：
        material: Material 对象（add/deduct 均从它取 id 与实例）。
        delta: 有符号数量；>0 入库（add_stock），<0 出库（deduct_stock_atomic），
            ==0 不写任何账、直接成功（与存量调用点 quantity==0 跳过的口径一致）。
        transaction_type: 流水类型（必传；原样写入 StockTransaction）。
        warehouse: 仓库（str 或 Warehouse 对象，原样透传底层原语）。
        location: 行级库位；缺省时库位键回退 warehouse（既有定式逐字沿用）。
    返回：(是否成功, 错误信息)。失败时调用方负责 db.session.rollback()。
    """
    # 延迟导入 app 原语：服务层由路由函数在请求期导入，模块级 import app 会
    # 在 app.py 加载期形成循环导入（与 routes/* 同一定式）。
    from app import (_stock_location_from_warehouse, add_stock,
                     deduct_stock_atomic, location_management_enabled,
                     update_location_inventory)

    if not material:
        return False, '物料不存在'
    delta = delta or 0
    if delta > 0:
        ok, err = add_stock(
            material, delta,
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            remark=remark,
            warehouse=warehouse,
        )
        if not ok:
            return False, err or '库存增加失败'
    elif delta < 0:
        ok, err, _mat = deduct_stock_atomic(
            material.id, abs(delta),
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            remark=remark,
            warehouse=warehouse,
        )
        if not ok:
            return False, err
    else:
        return True, ''

    # ②库位账同步：仅在开启库位管理时写；delta 同号（入正出负），
    # update_location_inventory 内部按正负自动分发 add/deduct 原语。
    if location_management_enabled():
        loc_key = (location or '').strip() or (_stock_location_from_warehouse(warehouse) or '')
        if loc_key:
            loc_ok, loc_err = update_location_inventory(
                material, loc_key, delta, warehouse=warehouse)
            if not loc_ok:
                return False, loc_err or '库位库存更新失败'
    return True, ''
