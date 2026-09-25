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


def apply_transfer_pair(material, quantity, *, from_warehouse=None, to_warehouse=None,
                        from_location=None, to_location=None,
                        reference_type='transfer', reference_id=None,
                        out_remark='', in_remark=''):
    """调拨专用库存入口：写**双向流水** + **库位账**，①总账**不动**。

    为什么单列一个入口而不复用 apply_stock_delta
    ---------------------------------------------
    调拨是物料在公司内部搬家，物料没离开公司，①总账必须保持原值。
    而 apply_stock_delta 走 add_stock / deduct_stock_atomic，**必然改 ①**，
    还会给调拨凭空引入一次「仓库级库存不足」校验
    （deduct_stock_atomic 内的 get_warehouse_stock_quantities 分支）——
    那正是审计 1.1 里反复复发的「读全局账」错误方向。
    判据见 tests/test_p1_7_three_ledgers_business_paths.py T1~T3：
    调拨后 ① 必须不变、Σ③ 净增 0。

    反提交也用本函数：**把 from / to 对调**即可，无需额外开关。
        complete: from=A, to=B  → out(-q)@A, in(+q)@B；库位 A:-q, B:+q
        revert:   from=B, to=A  → out(-q)@B, in(+q)@A；库位 B:-q, A:+q

    库位账两条腿刻意不对称（沿用存量定式）：
      - 调出腿用 deduct_location_inventory_atomic：原子扣，防超发/重复反提交；
      - 调入腿用 update_location_inventory：自动建账，不会为负，无需原子性。

    参数：
        quantity: 调拨数量（>0）。quantity<=0 时不写库位账也不写流水，
            直接返回成功（避免出现 0 数量噪声流水）。
    返回：(是否成功, 错误信息)。失败时调用方负责 db.session.rollback()。
    """
    from app import (_stock_location_from_warehouse, add_stock_transaction,
                     deduct_location_inventory_atomic,
                     location_management_enabled, resolve_inventory_warehouse_id,
                     update_location_inventory)

    if not material:
        return False, '物料不存在'
    qty = quantity or 0
    if qty <= 0:
        return True, ''

    use_location = location_management_enabled()
    if use_location:
        # 调出腿：原子扣库位（防超发）。库位键口径与存量定式一致：
        # 行级库位为空时回退仓库（_stock_location_from_warehouse）。
        out_loc = (from_location or '').strip() or (_stock_location_from_warehouse(from_warehouse) or '')
        if out_loc:
            ok, err = deduct_location_inventory_atomic(
                material.id, out_loc, qty,
                material_code_hint=getattr(material, 'code', None),
                warehouse_id=resolve_inventory_warehouse_id(from_warehouse),
            )
            if not ok:
                return False, err or '调出库位库存扣减失败'
        # 调入腿：自动建账，非破坏性
        in_loc = (to_location or '').strip() or (_stock_location_from_warehouse(to_warehouse) or '')
        if in_loc:
            ok_in, err_in = update_location_inventory(
                material, in_loc, qty, warehouse=to_warehouse)
            if not ok_in:
                return False, err_in or '调入库位库存更新失败'

    # ③流水账：一对异号流水，净增 0；①总账完全不动
    add_stock_transaction(
        material, -qty, 'transfer_out',
        reference_type=reference_type,
        reference_id=reference_id,
        location=from_location,
        warehouse=from_warehouse,
        remark=out_remark or '',
    )
    add_stock_transaction(
        material, qty, 'transfer_in',
        reference_type=reference_type,
        reference_id=reference_id,
        location=to_location,
        warehouse=to_warehouse,
        remark=in_remark or '',
    )
    return True, ''


def apply_opening_balance(material, quantity, *, warehouse=None, location=None,
                          reference_type='opening_stock', reference_id=None,
                          remark=''):
    """建账专用库存入口：只写 ③流水 + ②库位账，**①总账不动**。

    与另两个入口的语义边界（P1-7③，2026-09-25）：
      - apply_stock_delta   入/出库：**改 ①** + ③ + ②
      - apply_transfer_pair 调拨：① 不动 + 双向 ③ + ②
      - apply_opening_balance 建账：① **由调用方自己定**（物料新增时构造赋值、
        期初单据里 sa_update 改），入口只负责把 ① 的成因补记成 ③、并同步 ②。

    **为什么建账不能复用 apply_stock_delta**：新增物料时 Material.stock 已经在
    构造时赋成 initial_stock；若再走 apply_stock_delta 的 add_stock，① 会
    **再涨一次 → 初始库存翻倍**。期初同理（① 由 sa_update 自己加减差额）。

    参数：
        quantity: 有符号数量；>0 建账、<0 调减（期初改单的差额可为负）；
            ==0 不写任何账、直接成功（与 material.py `initial_stock > 0` 口径一致）。
        location: 行级库位；缺省时库位键回退 warehouse（既有定式逐字沿用）。
    返回：(是否成功, 错误信息)。失败时调用方负责 db.session.rollback()。
    """
    # 延迟导入 app 原语：服务层由路由函数在请求期导入，模块级 import app 会
    # 在 app.py 加载期形成循环导入（与 routes/* 同一定式）。
    from app import (_stock_location_from_warehouse, add_stock_transaction,
                     location_management_enabled, update_location_inventory)

    if not material:
        return False, '物料不存在'
    qty = quantity or 0
    if qty == 0:
        return True, ''

    add_stock_transaction(
        material, qty, 'opening',
        reference_type=reference_type,
        reference_id=reference_id,
        location=location or None,
        warehouse=warehouse,
        remark=remark or '',
    )

    # ②库位账同步：仅在开启库位管理时写；qty 同号（正加负减），
    # update_location_inventory 内部按正负自动分发 add/deduct 原语。
    if location_management_enabled():
        loc_key = (location or '').strip() or (_stock_location_from_warehouse(warehouse) or '')
        if loc_key:
            loc_ok, loc_err = update_location_inventory(
                material, loc_key, qty, warehouse=warehouse)
            if not loc_ok:
                return False, loc_err or '库位库存更新失败'
    return True, ''
