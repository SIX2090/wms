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

# P2b（2026-09-25）：三账恒等式运行时校验。
#   为什么不做数据库级约束（CHECK/触发器）：
#     - CHECK 不能跨表、不能写子查询聚合，而恒等式是跨表聚合，根本表达不出来；
#     - 触发器能做到，但每次写入都触发一次 SUM()，且本库历史上修过 100 多次
#       库存问题、存量脏数据未知——一上线就会把整库写入锁死。
#   故降级为：入口内可开关的运行时断言（测试默认开、生产默认关）+ 既有
#   scripts/verify_inventory_identity.py 的 CI 全库恒等式判据。
LEDGER_EPS = 0.01


def _recorded_quantity_matches(actual, expected, *operands):
    """Float 表示误差边界；绝不沿用普通三账检查的 0.01 容差。"""
    import math

    values = (actual, expected, *operands)
    if not all(math.isfinite(value) for value in values):
        return False
    tolerance = min(1e-9, 8 * max(math.ulp(value) for value in values))
    return abs(actual - expected) <= tolerance


def _reverse_recorded_order_stock(order):
    """已锁入/出库单的历史数量分支；普通两位返回None，交原业务路径。"""
    from decimal import Decimal, localcontext
    import math
    from sqlalchemy import update

    from app import (InOrder, OutOrder, LocationInventory, Material, StockTransaction,
                     Warehouse, add_stock_transaction, allow_negative_location_stock,
                     allow_negative_stock, db, location_management_enabled,
                     normalize_stock_quantity, resolve_inventory_warehouse_id,
                     _stock_location_from_warehouse)

    kinds = {InOrder: ('in_order', 1, 'revert_in'),
             OutOrder: ('out_order', -1, 'revert_out')}
    if type(order) not in kinds:
        return False, '该单据不支持历史数量逆向'
    source_type, sign, transaction_type = kinds[type(order)]
    connection = db.session.connection()
    if connection.dialect.name == 'sqlite' and not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    db.session.refresh(order, with_for_update=True)
    if order.status != 'completed':
        return False, '单据状态已变化，不能重复反提交'
    db.session.expire(order, ['items'])
    items = list(order.items)
    rows = (StockTransaction.query.filter_by(reference_type=source_type, reference_id=order.id)
            .populate_existing().with_for_update().all())
    try:
        raw = [float(item.quantity) for item in items] + [float(row.quantity) for row in rows]
    except (TypeError, ValueError, OverflowError):
        return False, '单据或原流水数量无效，无法安全回冲'
    if not all(math.isfinite(value) for value in raw):
        return False, '单据或原流水数量无效，无法安全回冲'
    if all(_recorded_quantity_matches(value, normalize_stock_quantity(value)) for value in raw):
        return None

    def _net(values):
        with localcontext() as context:
            context.prec = 1000
            return float(sum((Decimal(str(value)) for value in values), Decimal(0)))

    original_types = {'in', 'add_in_item', 'adjust_in_item', 'delete_in_item'} if sign>0 else {'out'}
    if any(row.transaction_type not in original_types | {transaction_type} for row in rows):
        return False, '历史单据流水阶段无法证明，无法安全回冲，请先人工核对'
    last_reversal = max((row.id for row in rows if row.transaction_type==transaction_type),default=0)
    closed = {}
    for row in rows:
        if row.id<=last_reversal:
            closed.setdefault((row.material_id,row.warehouse_id),[]).append(float(row.quantity))
    if any(not _recorded_quantity_matches(_net(values),0,*values) for values in closed.values()):
        return False, '此前完成周期未准确回退，不能与当前周期相抵，请先人工核对'
    rows = [row for row in rows if row.id>last_reversal]

    expected = {}
    normalized_expected = {}
    for item in items:
        if item.material_id is None or float(item.quantity) < 0:
            return False, '历史单据明细缺失物料或数量方向无效，无法安全回冲'
        expected.setdefault(item.material_id, []).append(sign * float(item.quantity))
        normalized_expected.setdefault(item.material_id, []).append(
            sign * normalize_stock_quantity(float(item.quantity)))
    grouped = {}
    for row in rows:
        grouped.setdefault(row.material_id, []).append(row)
    plans = []
    location_on = location_management_enabled()
    header_warehouse_id = resolve_inventory_warehouse_id(order.warehouse)
    normalized_compatible = all(_recorded_quantity_matches(float(row.quantity),
                                normalize_stock_quantity(float(row.quantity))) for row in rows)
    use_original_path = normalized_compatible
    for material_id in set(expected) | set(grouped):
        original = grouped.get(material_id, [])
        quantities = [float(row.quantity) for row in original]
        total = _net(quantities)
        matches_original = _recorded_quantity_matches(total, _net(expected.get(material_id, [])), *quantities)
        matches_normalized = (normalized_compatible and _recorded_quantity_matches(total,
                              _net(normalized_expected.get(material_id, [])), *quantities))
        use_original_path = use_original_path and matches_normalized
        if not matches_original and not matches_normalized:
            return False, '历史单据数量与已落流水净额不一致，无法安全回冲，请先人工核对'
        by_warehouse = {}
        for row in original:
            by_warehouse.setdefault(row.warehouse_id, []).append(row)
        active = [(warehouse_id, source, _net([float(row.quantity) for row in source]))
                  for warehouse_id, source in by_warehouse.items()]
        if location_on and any(_recorded_quantity_matches(group[2],0) for group in active):
            # 仓合计净零不证明各物理库位净零。原流水缺少行级物理键，
            # 不能跳过这种历史来源后让草稿删除抹去其最后可核对证据。
            return False, '历史净零仓的逐库位来源无法证明，不能安全回冲，请先人工核对'
        active = [group for group in active if not _recorded_quantity_matches(group[2], 0)]
        if not active:
            continue
        if len(active) != 1 or active[0][0] is None:
            return False, '历史单据原仓归属缺失或冲突，无法安全回冲，请先人工核对'
        warehouse_id, source, quantity = active[0]
        warehouse = db.session.get(Warehouse,warehouse_id)
        if warehouse is None:
            return False, '历史单据原仓记录不存在，无法安全回冲'
        if header_warehouse_id is not None and header_warehouse_id != warehouse_id:
            return False, '历史单据头仓库与原流水归属不一致，无法安全回冲，请先人工核对'
        if header_warehouse_id != warehouse_id:
            # 仓改名/头文本失效时只能走原FK能力，不能返回按旧文本选仓的路径。
            use_original_path = False
        material = (Material.query.filter_by(id=material_id).populate_existing()
                    .with_for_update().one_or_none())
        if material is None:
            return False, '历史单据物料不存在，无法安全回冲'
        ledger = (StockTransaction.query.filter_by(material_id=material_id)
                  .populate_existing().with_for_update().all())
        before = float(material.stock)
        ledger_values = [float(row.quantity) for row in ledger]
        if not _recorded_quantity_matches(before, math.fsum(ledger_values), *ledger_values):
            return False, '物料总账与流水账不一致，无法安全回冲，请先人工核对'
        warehouse_values = [float(row.quantity) for row in ledger if row.warehouse_id==warehouse_id]
        available = math.fsum(warehouse_values)
        after_warehouse = available - quantity
        if (quantity > 0 and after_warehouse < 0 and not _recorded_quantity_matches(after_warehouse, 0, available, quantity)
                and not allow_negative_stock()):
            return False, '历史单据原仓库存不足，无法安全反提交'
        delta = -quantity
        after = before + delta
        if (delta != 0 and after == before) or not _recorded_quantity_matches(after-before, delta, before, after):
            return False, '历史原数量超出总账Float可逆精度，无法安全回冲'
        if (delta < 0 and after < 0 and not _recorded_quantity_matches(after,0,before,delta)
                and not allow_negative_stock()):
            # 先保留上面的原仓约束，再保留deduct_stock_atomic的额外全局门槛。
            # 其他仓既存负数不能令本次扣减穿过总账零界，不据此调整其他仓。
            return False, '全局库存不足，无法安全反提交；请核对各仓及未归属库存'
        location_changes = []
        if location_on:
            locations = (LocationInventory.query.filter_by(material_id=material_id,warehouse_id=warehouse_id)
                         .populate_existing().with_for_update().all())
            values = [float(row.quantity) for row in locations]
            if not _recorded_quantity_matches(math.fsum(values),available,*values,*warehouse_values):
                return False, '历史原仓库位账与流水不一致，无法安全回冲，请先人工核对'
            explicit = (order.location or '').strip()
            by_location = {}
            for row in source:
                position = explicit or (row.location or '').strip()
                if not position:
                    return False, '历史单据原库位缺失，无法安全回冲'
                by_location.setdefault(position, []).append(float(row.quantity))
            for position, original_values in by_location.items():
                position_delta = -_net(original_values)
                if _recorded_quantity_matches(position_delta,0):
                    continue
                candidates = [row for row in locations if row.location==position]
                if len(candidates)!=1:
                    return False, '历史单据原库位记录缺失或重复，无法安全回冲'
                location = candidates[0]
                current = float(location.quantity)
                after_location = current + position_delta
                if ((position_delta != 0 and after_location == current)
                        or not _recorded_quantity_matches(after_location-current,position_delta,current,after_location)):
                    return False, '历史原数量超出库位Float可逆精度，无法安全回冲'
                if (position_delta<0 and after_location<0 and not _recorded_quantity_matches(after_location,0,current,position_delta)
                        and not allow_negative_location_stock()):
                    return False, '历史单据原库位库存不足，无法安全回冲'
                location_changes.append((location,current,position_delta))
            legacy_position = (order.location or '').strip() or (
                _stock_location_from_warehouse(order.warehouse) or '').strip()
            if any(location.location != legacy_position for location,_current,_delta in location_changes):
                # 仓编码/改名时旧入口的默认位可能与原流水保存的占位键不同。
                use_original_path = False
        plans.append((material,before,delta,warehouse,location_changes))
    if location_on and any(value != 0 for values in closed.values() for value in values):
        # 普通入/出库流水的location保存仓名，不是带语义标记的原bin。
        # 闭合记录净零、当前单头或当前库位唯一都不证明旧的逐位净零。
        # 只允许逐条数量确为零的无物理增量记录；其余缺结构来源须核对。
        return False, '闭合历史流水缺少逐库位原始来源，不能安全回冲，请先人工核对'
    if use_original_path:
        # 历史明细高精度不等于库存实际高精度。只有已证明当时逐行规范
        # 落账且原仓/库位/数量均匹配，才交还既有逐行规范回退语义。
        return None
    # 全单先完成来源、位置和数量核验，任何拒绝都不能留下半张单的增量。
    for material,before,delta,warehouse,location_changes in plans:
        result=db.session.execute(update(Material).where(Material.id==material.id,
            Material.stock==before).values(stock=Material.stock+delta))
        if result.rowcount!=1:
            return False, '物料库存已变化，请回滚并刷新后重试'
        for location,current,position_delta in location_changes:
            result=db.session.execute(update(LocationInventory).where(LocationInventory.id==location.id,
                LocationInventory.quantity==current).values(quantity=LocationInventory.quantity+position_delta))
            if result.rowcount!=1:
                return False, '库位库存已变化，请回滚并刷新后重试'
            db.session.expire(location,['quantity'])
        add_stock_transaction(material,delta,transaction_type,reference_type=source_type,
            reference_id=order.id,warehouse=warehouse,location=warehouse.name,remark='历史原数量反提交')
        db.session.expire(material,['stock'])
    db.session.flush()
    return True, ''


def _reverse_recorded_opening_stock(line):
    """仅供既有期初逆向入口使用；已落原数量不再量化，失败由调用方回滚。"""
    from decimal import Decimal, localcontext
    import math
    from sqlalchemy import update

    from app import (LocationInventory, Material, StockTransaction, Warehouse,
                     _opening_stock_line_transaction_ids,
                     allow_negative_location_stock, db, location_management_enabled)

    # 分类本身取得 SQLite 短写锁或刷新调用方已有事务，不能跨事务复用证明。
    transaction_ids, error = _opening_stock_line_transaction_ids(line)
    if error:
        return False, error
    rows = (StockTransaction.query.filter(StockTransaction.id.in_(transaction_ids))
            .populate_existing().with_for_update().all()) if transaction_ids else []
    if len(rows) != len(transaction_ids) or any(
            row.reference_type != 'opening_stock' or row.reference_id != line.id
            or row.material_id != line.material_id for row in rows):
        return False, '期初流水来源已变化，无法安全回冲，请刷新核对后重试'
    try:
        quantity = float(line.quantity)
        recorded = [float(row.quantity) for row in rows]
        if not all(math.isfinite(value) for value in (quantity, *recorded)):
            raise ValueError('nonfinite')
        with localcontext() as context:
            context.prec = 1000
            net = float(sum((Decimal(str(value)) for value in recorded), Decimal(0)))
    except (TypeError, ValueError, OverflowError):
        return False, '期初数量或流水包含无效数值，无法安全回冲'
    if not _recorded_quantity_matches(net, quantity, *recorded):
        return False, '期初数量与已落流水净额不一致，无法安全回冲，请先人工核对'
    if not rows and quantity == 0:
        return True, ''
    warehouse_id = line.warehouse_id
    location_on = location_management_enabled()
    if ((warehouse_id is None and location_on)
            or (warehouse_id is not None and db.session.get(Warehouse, warehouse_id) is None)
            or any(row.warehouse_id != warehouse_id for row in rows)):
        return False, '期初原仓库归属缺失或冲突，无法安全回冲，请先人工核对'
    material = (Material.query.filter_by(id=line.material_id)
                .populate_existing().with_for_update().one_or_none())
    if material is None:
        return False, '期初物料不存在，无法安全回冲'
    all_rows = (StockTransaction.query.filter_by(material_id=material.id)
                .populate_existing().with_for_update().all())
    try:
        before = float(material.stock)
        ledger_values = [float(row.quantity) for row in all_rows]
        ledger_total = math.fsum(ledger_values)
    except (TypeError, ValueError, OverflowError):
        return False, '库存账包含无效数值，无法安全回冲'
    if not _recorded_quantity_matches(before, ledger_total, *ledger_values):
        return False, '物料总账与流水账不一致，无法安全回冲，请先人工核对'
    changes = []
    if location_on:
        # 显式库位是不可改的期初行字段；空库位只接受原流水保存的占位键。
        # 不按现在的仓库名称、默认仓库或其他库位余额推测历史物理位置。
        positions = {}
        explicit_location = (line.location or '').strip()
        for row in rows:
            location = explicit_location or (row.location or '').strip()
            if not location:
                return False, '期初原库位缺失，无法安全回冲，请先人工核对'
            positions.setdefault(location, []).append(float(row.quantity))
        locations = (LocationInventory.query.filter_by(material_id=material.id, warehouse_id=warehouse_id)
                     .populate_existing().with_for_update().all())
        try:
            location_values = [float(row.quantity) for row in locations]
            warehouse_total = math.fsum(location_values)
            transaction_total = math.fsum(float(row.quantity) for row in all_rows
                                          if row.warehouse_id == warehouse_id)
        except (TypeError, ValueError, OverflowError):
            return False, '库位账包含无效数值，无法安全回冲'
        if not _recorded_quantity_matches(warehouse_total, transaction_total,
                                          *location_values, *ledger_values):
            return False, '期初库位账与总账或原仓流水不一致，无法安全回冲，请先人工核对'
        for location, values in positions.items():
            matches = [row for row in locations if row.warehouse_id == warehouse_id
                       and row.location == location]
            if len(matches) != 1:
                return False, '期初原库位记录缺失或重复，无法安全回冲，请先人工核对'
            current = float(matches[0].quantity)
            with localcontext() as context:
                context.prec = 1000
                delta = -float(sum((Decimal(str(value)) for value in values), Decimal(0)))
            after = current + delta
            if ((delta != 0 and after == current)
                    or not _recorded_quantity_matches(after - current, delta, current, after)):
                return False, '期初原数量超出当前库位 Float 可逆精度，无法安全回冲'
            if (delta < 0 and after < 0 and not _recorded_quantity_matches(after, 0, current, delta)
                    and not allow_negative_location_stock()):
                return False, '期初原库位库存不足，无法安全回冲'
            changes.append((matches[0], current, delta))
    after = before - net
    if ((net != 0 and after == before)
            or not _recorded_quantity_matches(before - after, net, before, after)):
        return False, '期初原数量超出当前总账 Float 可逆精度，无法安全回冲'
    result = db.session.execute(update(Material).where(
        Material.id == material.id, Material.stock == before).values(stock=Material.stock - net))
    if result.rowcount != 1:
        return False, '物料库存已变化，请刷新核对后重试'
    for location, current, delta in changes:
        result = db.session.execute(update(LocationInventory).where(
            LocationInventory.id == location.id, LocationInventory.quantity == current
        ).values(quantity=LocationInventory.quantity + delta))
        if result.rowcount != 1:
            return False, '库位库存已变化，请刷新核对后重试'
        db.session.expire(location, ['quantity'])
    if rows:
        count = StockTransaction.query.filter(StockTransaction.id.in_(transaction_ids)).delete(
            synchronize_session=False)
        if count != len(transaction_ids):
            return False, '期初流水已变化，请回滚后重新核对'
    db.session.expire(material, ['stock'])
    return True, ''


def three_ledger_guard_enabled() -> bool:
    """三账运行时校验开关。

    取值优先级：环境变量 WMS_THREE_LEDGER_ASSERT > 运行环境推断。
      - 1/true/yes/on/strict → 开
      - 0/false/no/off       → 关（生产默认走这条）
      - 未设置：pytest 或 Flask TESTING 下开，生产关
    """
    import os

    env = (os.environ.get('WMS_THREE_LEDGER_ASSERT') or '').strip().lower()
    if env in ('1', 'true', 'yes', 'on', 'strict'):
        return True
    if env in ('0', 'false', 'no', 'off'):
        return False
    if os.environ.get('PYTEST_CURRENT_TEST'):
        return True
    try:
        from flask import current_app
        return bool(current_app.config.get('TESTING'))
    except Exception:
        return False


def three_ledger_guard_strict() -> bool:
    """是否把恒等式不成立视为致命错误（抛 AssertionError）。

    只有显式 WMS_THREE_LEDGER_ASSERT=strict 才抛。默认即便开启也只告警——
    存量脏数据未知，不能让一条对不上账的历史行把正常业务写挂。
    """
    import os

    return (os.environ.get('WMS_THREE_LEDGER_ASSERT') or '').strip().lower() == 'strict'


def verify_material_three_ledgers(material) -> tuple[bool, dict]:
    """校验单个物料的三账恒等式：① == Σ③；开启库位管理时还要求 ① == Σ②。

    返回 (是否成立, 明细 dict)。明细含 one/two/three/location_on，便于告警
    与测试定位是哪一层的账先歪了。

    注意：读的是**当前 session/库里的真实值**，不是 ORM 实例的缓存值
    （入口内部 expire 过 Material.stock，直接读实例会拿到旧值）。
    """
    from app import (LocationInventory, Material, StockTransaction,
                     location_management_enabled, db)

    mid = getattr(material, 'id', material)
    mat = db.session.get(Material, mid)
    one = float(mat.stock or 0) if mat else 0.0
    three = float(sum((r.quantity or 0)
                      for r in StockTransaction.query.filter_by(material_id=mid).all()))
    location_on = location_management_enabled()
    two = None
    if location_on:
        two = float(sum((r.quantity or 0)
                        for r in LocationInventory.query.filter_by(material_id=mid).all()))
    ok = abs(one - three) <= LEDGER_EPS
    if location_on and two is not None:
        ok = ok and abs(one - two) <= LEDGER_EPS
    return ok, {'one': one, 'two': two, 'three': three, 'location_on': location_on}


def find_location_ledger_mismatches(tolerance=LEDGER_EPS, limit=20):
    """开启库位管理前的防爆前置校验（F2.10 ①，审计报告 §1.3）。

    「库位管理」是**高危开关**：开启后 `get_warehouse_stock_quantities` 由按流水
    `location` 聚合切换为按 `LocationInventory` 聚合。若库位账（②）与流水账（③）
    不一致（典型：历史库位账为空），开启后库存查询/报表/手机端会大面积显示 0、
    出库被拒、存量单据调整/调拨完成失败。故由 0→1 前必须先跑本判据。

    判据与 `scripts/verify_inventory_identity.py` 的**硬失败维度**对齐（只读）：
      - 仓级 ②≠③：逐 (material_id, warehouse_id) 比对库位账净额与流水净额；
        `warehouse_id IS NULL` 的历史行**不猜归属**、跳过（与脚本 UNATTRIBUTED 桶一致）；
      - 物料级 ①≠Σ②：仅对**存在库位账行**的物料判——库位账整体为空是"关库位管理"
        的预期状态，与脚本 `find_mismatches`（`location_rows > 0` 才判）同口径。

    返回不一致清单（每条 dict，最多 limit 条）；空列表表示可以安全开启。
    只读，不写任何账。
    """
    import sqlalchemy as sa

    from app import LocationInventory, Material, StockTransaction, db

    loc_rows = (db.session.query(
                    LocationInventory.material_id,
                    LocationInventory.warehouse_id,
                    sa.func.sum(LocationInventory.quantity))
                .group_by(LocationInventory.material_id,
                          LocationInventory.warehouse_id).all())
    txn_rows = (db.session.query(
                    StockTransaction.material_id,
                    StockTransaction.warehouse_id,
                    sa.func.sum(StockTransaction.quantity))
                .group_by(StockTransaction.material_id,
                          StockTransaction.warehouse_id).all())
    codes = dict(db.session.query(Material.id, Material.code).all())
    ledger = {mid: float(stock or 0)
              for mid, stock in db.session.query(Material.id, Material.stock).all()}

    loc_by_key = {(mid, wid): float(qty or 0) for mid, wid, qty in loc_rows}
    txn_by_key = {(mid, wid): float(qty or 0) for mid, wid, qty in txn_rows}

    findings = []
    # 仓级 ②≠③：遍历两边的并集（仅出现在流水侧、库位账缺行的仓也必须判出来）
    for key in sorted(set(loc_by_key) | set(txn_by_key), key=lambda k: (str(k[0]), str(k[1]))):
        mid, wid = key
        if wid is None:
            continue  # 未归属历史行不猜归属
        loc_q = loc_by_key.get(key, 0.0)
        txn_q = txn_by_key.get(key, 0.0)
        if abs(loc_q - txn_q) > tolerance:
            findings.append({
                "dimension": "wh_location_vs_txn", "material_id": mid,
                "code": codes.get(mid, ""), "warehouse_id": wid,
                "location": round(loc_q, 2), "txn": round(txn_q, 2),
                "delta": round(loc_q - txn_q, 2)})
    # 物料级 ①≠Σ②：仅对存在库位账行的物料判
    loc_total_by_mid = {}
    for (mid, _wid), q in loc_by_key.items():
        loc_total_by_mid[mid] = loc_total_by_mid.get(mid, 0.0) + q
    for mid, loc_total in loc_total_by_mid.items():
        one = ledger.get(mid, 0.0)
        if abs(one - loc_total) > tolerance:
            findings.append({
                "dimension": "ledger_vs_location", "material_id": mid,
                "code": codes.get(mid, ""), "warehouse_id": None,
                "location": round(loc_total, 2), "txn": round(one, 2),
                "delta": round(one - loc_total, 2)})
    return findings[:limit]


def guard_three_ledgers(material) -> bool:
    """入口内调用的三账守卫：开了才校验，默认只告警、不阻断。

    - 未开启：直接返回 True（生产零成本，只有一次环境变量读取）。
    - 开启且恒等式不成立：logger.error 记明细；strict 模式下抛 AssertionError
      （供专项测试证明"这套校验真能抓到分叉"）。
    """
    if not three_ledger_guard_enabled():
        return True
    ok, detail = verify_material_three_ledgers(material)
    if ok:
        return True
    mid = getattr(material, 'id', material)
    msg = (f'三账恒等式不成立 material_id={mid}：'
           f"①={detail['one']} ②={detail['two']} ③Σ={detail['three']} "
           f"(location_on={detail['location_on']})")
    try:
        from flask import current_app
        current_app.logger.error(msg)
    except Exception:
        pass
    if three_ledger_guard_strict():
        raise AssertionError(msg)
    return False


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
    # P2b：写入后立刻校验三账恒等式（开关默认生产关 / 测试开，只告警不阻断）。
    # 只挂在入/出库入口：调拨（①不动、③双向净 0）与建账（①由调用方在入口外改）
    # 的恒等式都依赖入口之外的动作，在入口内校验会产生**误报窗口**
    # （调用方还没改①就先调入口），故不挂。这两条路径由
    # tests/test_p1_7_* 的判据与 scripts/verify_inventory_identity.py 守着。
    guard_three_ledgers(material)
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
                          txn_location=None, reference_type='opening_stock',
                          reference_id=None, remark='', sync_location=True):
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
        location: ②库位账的库位键；缺省时回退 warehouse（既有定式逐字沿用）。
        txn_location: ③流水的 location，**缺省时回退 warehouse 名**。
            必须与 location 分开：期初建账的旧实现里流水 location 恒记仓库名，
            而库位账记的是明细行库位（两处本就不一致，P1-7③ 判据已钉死），
            共用一个参数会把流水的落库值改掉。
        sync_location: 是否同步 ②库位账，默认 True。期初单据在 warehouse 为
            None 时原本就不写库位账（app.py 旧条件 `and warehouse`），故由调用方
            显式传 False 保持该口径。
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

    # ③流水：location 默认回退仓库名（与期初旧实现「流水恒记仓库名」同口径），
    # 与 ② 的库位键 location 互不干扰。
    # 注意 add_stock_transaction 只把 warehouse 解析成 warehouse_id，**不会**
    # 顺带填 location，所以这里必须自己用 _stock_location_from_warehouse 回退。
    add_stock_transaction(
        material, qty, 'opening',
        reference_type=reference_type,
        reference_id=reference_id,
        location=(txn_location or _stock_location_from_warehouse(warehouse) or None),
        warehouse=warehouse,
        remark=remark or '',
    )

    # ②库位账同步：仅在开启库位管理时写；qty 同号（正加负减），
    # update_location_inventory 内部按正负自动分发 add/deduct 原语。
    if sync_location and location_management_enabled():
        loc_key = (location or '').strip() or (_stock_location_from_warehouse(warehouse) or '')
        if loc_key:
            loc_ok, loc_err = update_location_inventory(
                material, loc_key, qty, warehouse=warehouse)
            if not loc_ok:
                return False, loc_err or '库位库存更新失败'
    return True, ''
