"""Deterministic read-only answers for existing assistant queries.

AI_TASK: AI-C01
Fix: AI-C01-FIX-TEXT-QUERIES-20261101-001
Only query facts are inherited from recent user turns. Never inherit an action,
assistant instruction, or confirmation; this module cannot create documents.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from importlib import import_module
import re

from flask import url_for


def _app():
    return import_module('app')


def _number(value):
    return format(Decimal(str(value or 0)).normalize(), 'f')


def material_label_parts(token):
    match = re.fullmatch(r'([A-Za-z]*\d[A-Za-z0-9*./×_-]*)([\u4e00-\u9fff].+)', token or '')
    return {'name':match[2], 'spec':match[1]} if match else {'name':'', 'spec':''}


def parse_material_segments(text):
    """Require a quantity delimiter or a unit, never split digits inside a code."""
    unit = r'(?:个|只|套|件|箱|包|PCS|pcs|kg|KG|米|支|条|根|台|卷)'
    rows = []
    for segment in re.split(r'[\r\n,，;；、]+', text or ''):
        segment = segment.strip()
        if not segment or re.match(r'^(仓库|库位|客户|备注|请登记)', segment):
            continue
        spaced = list(re.finditer(r'([^\s]{2,80})\s+(-?\d+(?:\.\d+)?)\s*(' + unit + r')?(?=\s|$)', segment))
        compact = [m for m in re.finditer(r'([^\s]{2,80}?)\s*(-?\d+(?:\.\d+)?)\s*(' + unit + r')(?=\s|$)', segment)
                   if not any(m.start() < s.end() and m.end() > s.start() for s in spaced)]
        for match in sorted([*spaced, *compact], key=lambda m:m.start()):
            token = match[1]
            token = re.sub(r'^(?:(?:请|帮我|开|生成|创建|新增|做一张|开一张|领料单|领料|出库单|出库|入库单|入库|采购入库|草稿|送货单|明天|今天|后天|发货|发|送货|送))+', '', token)
            ambiguous_code = match in compact and (token[-1:].isdigit() or re.fullmatch(r'[A-Za-z0-9_.-]+', token))
            if len(token) < 2 or ambiguous_code or not 0 < Decimal(match[2]) <= 1_000_000_000:
                continue
            parts = material_label_parts(token)
            rows.append({'name':token,'quantity':float(match[2]),'unit':match[3] or '', 'raw':match[0],
                         'parsed_name':parts['name'], 'spec':parts['spec']})
    return rows


def supplier_label(text):
    """Parse sender-before-verb and the accepted 发供应商 notice form."""
    patterns = (
        r'(?:今天|明天|后天|上午|下午|晚上)\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,30}?)\s*(?:发货|送货|发|送)(?=\s*\d)',
        r'(?:今天|明天|后天|上午|下午|晚上)?\s*(?:发货|送货|出货|发|送)\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,30})',
        r'(?:供应商|厂家)\s*[:：]\s*([\u4e00-\u9fffA-Za-z0-9_\-]{2,30})',
    )
    for pattern in patterns:
        match = re.search(pattern, text or '')
        if match:
            value = match[1]
            if value not in {'货', '货单', '送货单', '出货通知', '通知', '一下'}:
                return value
    return ''


def _explicit_materials(text):
    w = _app()
    tokens = re.findall(r'[A-Za-z0-9][A-Za-z0-9_.-]*', text or '')[:40]
    if not tokens:
        return []
    return w.Material.query.filter(w.db.func.lower(w.Material.code).in_([t.lower() for t in tokens])).all()


def _materials(text):
    exact = _explicit_materials(text)
    if exact:
        return exact
    found = _app()._ai_find_materials_from_message(text, limit=8)
    precise = [m for m in found if m.spec and m.spec in text]
    return precise or found


def _warehouse(text):
    """Explicit unknown/ambiguous warehouses must never fall back to default."""
    w = _app()
    if re.search(r'所有仓库|各仓库|每个仓库|全部仓库', text):
        return None, None
    hits = []
    for warehouse in w.get_active_warehouses():
        if any(alias and len(alias) >= 2 and alias in text for alias in (warehouse.name, warehouse.code)):
            hits.append(warehouse)
    if len(hits) > 1:
        # A shorter warehouse name may be contained in the longer one.
        hits = [wh for wh in hits if not any(wh.name != other.name and wh.name in other.name for other in hits)]
    if len(hits) == 1:
        return hits[0], None
    if hits:
        return None, '请明确要查询的一个仓库，不能把多个仓库的数量合并判断。'
    if re.search(r'仓|库房', text) and not re.search(r'仓库(?:库存|物料|中|里|内|有|的|？|\?|$)', text):
        return None, '没有找到仓库，请明确有效的仓库名称或编码。'
    return None, None


def _quantity(text, unit):
    units = sorted({unit, '套', '个', '件', '米', '根', '条', '箱', '包', '公斤', '千克', 'kg', '克', 'g', '吨', '台', '只', '把', '支', '片', '张', '卷', '块'} - {''}, key=len, reverse=True)
    pattern = r'(?<![A-Za-z0-9_.])(-?\d+(?:\.\d+)?)\s*(' + '|'.join(map(re.escape, units)) + r')'
    values = re.findall(pattern, text)
    if not values:
        values = [(m, unit) for m in re.findall(r'数量\s*(?:改成|改为|换成|为|是|[:：])?\s*(-?\d+(?:\.\d+)?)(?![\d.])', text)]
    if not values:
        return None, None
    if len(values) != 1:
        return None, '请明确本次需求数量，只能对一个物料的一种数量计算缺口。'
    raw, stated_unit = values[0]
    try:
        value = Decimal(raw)
        if not value.is_finite() or value <= 0:
            return None, '请明确大于0的本次需求数量。'
    except InvalidOperation:
        return None, '请明确有效的本次需求数量。'
    if not unit or stated_unit != unit:
        return None, f'请明确按档案单位「{unit or "未配置"}」填写需求数量；不同单位不能直接比较。'
    return value, None


def _query_turn(text, previous=None):
    """Resolve bounded stock-only context; an unrelated topic clears the state."""
    compact = re.sub(r'\s+', '', text or '')[:2000]
    followup = bool(re.match(r'^(那|那么|数量|改成|改为|换成|单位|它的|这个物料|两个仓)', compact))
    stock = bool(re.search(r'库存|存量|有多少|还剩多少|够不够|够用|缺多少|差多少|还差|能领|查实.*对不对', compact))
    if re.search(r'流水|报表|金额|价值|来源|入库|出库|草稿|开单|生成|创建|登记|新增', compact):
        return None
    if not stock and not followup:
        return None
    state = dict(previous or {}) if followup else {}
    combine_two = bool(re.search(r'两个仓.*(?:加起来|合计|总共)', compact))
    warehouse, error = (None, None) if combine_two else _warehouse(compact)
    if error:
        state['error'] = error
    if warehouse:
        state['warehouse'] = warehouse
        compared = list(state.get('comparison_warehouses') or [])
        if warehouse not in compared:
            compared.append(warehouse)
        state['comparison_warehouses'] = compared
        state.pop('all_warehouses', None)
    if re.search(r'所有仓库|各仓库|每个仓库|全部仓库', compact):
        state['all_warehouses'] = True
    if combine_two:
        if len(state.get('comparison_warehouses') or []) != 2:
            state['error'] = '请明确要相加的两个仓库名称，当前上下文不足。'
        state['all_warehouses'] = True
        state['combine_two'] = True
    materials = _materials(compact)
    if materials:
        state['materials'] = materials
    if state.get('error'):
        return state
    if not state.get('materials'):
        if followup or re.search(r'够不够|缺多少|差多少|能领', compact):
            return {'error': '请明确物料编码、仓库和需求数量；当前没有可延续的库存查询对象。'}
        return None
    if len(state['materials']) == 1:
        material = state['materials'][0]
        unit = material.unit.name if material.unit else ''
        quantity, quantity_error = _quantity(compact, unit)
        if quantity_error:
            state['error'] = quantity_error
        if quantity is not None:
            state['quantity'] = quantity
    state['demand'] = state.get('demand', False) or bool(re.search(r'够不够|够用|缺多少|差多少|还差|能领|数量.*(?:改|换)', compact))
    state['unit_question'] = '单位' in compact
    return state


def _stock_response(message, history):
    w = _app()
    state = None
    # History can supply object facts, never instructions or write operations.
    for turn in (history if isinstance(history, list) else [])[-20:]:
        if isinstance(turn, dict) and turn.get('role') == 'user' and isinstance(turn.get('content'), str):
            state = _query_turn(turn['content'], state)
    state = _query_turn(message, state)
    if state is None:
        return None
    if not w._ai_capability_allowed('warehouse_insights'):
        return w._ai_permission_denied_response('warehouse_insights')
    if state.get('error'):
        return w._ai_json_response(state['error'])
    if state.get('all_warehouses'):
        if len(state['materials']) != 1 or state.get('demand'):
            return w._ai_json_response('请明确一个物料和领用仓库，不能把不同物料或不同仓库混合判断需求缺口。')
        material = state['materials'][0]
        unit = material.unit.name if material.unit else ''
        lines, cards, total = [], [], Decimal(0)
        warehouses = (state['comparison_warehouses'] if state.get('combine_two') else
                      w.Warehouse.query.order_by(w.Warehouse.id).all())
        for wh in warehouses:
            quantity = Decimal(str(w.get_warehouse_stock_quantities(wh).get(material.id, 0) or 0))
            total += quantity
            lines.append(f'{wh.name}：{_number(quantity)}{unit}')
            cards.append({'title':wh.name, 'meta':f'{material.code} {material.name} {material.spec or ""}，库存 {_number(quantity)}{unit}'})
        return w._ai_json_response(f'{material.code} {material.name} 各仓已归属库存合计 {_number(total)}{unit}。\n' + '\n'.join(lines), cards)
    warehouse = state.get('warehouse') or w.get_default_warehouse()
    if not warehouse:
        cards = [{'title':f'{m.code} {m.name}', 'meta':'未选择仓库，未查询库存数量。'} for m in state['materials']]
        return w._ai_json_response('请选择仓库；系统没有可用的默认仓库，尚未查询 ' + '、'.join(m.code for m in state['materials']) + ' 的库存。', cards)
    materials = state['materials']
    stock = w.get_warehouse_stock_quantities(warehouse)
    cards = []
    for material in materials:
        card = w._ai_material_payload(material)
        card.update(stock=w.normalize_stock_quantity(stock.get(material.id, 0)), warehouse=warehouse.name)
        cards.append(card)
    if len(materials) > 1:
        reply = ('请明确物料编码，存在多个候选，不能混合计算需求缺口。' if state.get('demand') else
                 f'仓库「{warehouse.name}」匹配到 {len(materials)} 种物料，按编码和规格分别列出，不混合合计。')
        return w._ai_json_response(reply, cards)
    material = materials[0]
    unit = material.unit.name if material.unit else ''
    current = Decimal(str(stock.get(material.id, 0) or 0))
    reply = f'仓库「{warehouse.name}」物料 {material.code} {material.name}（{material.spec or "无规格"}），库存 {_number(current)}{unit}。'
    if state.get('unit_question'):
        reply += f'档案单位：{unit or "未配置"}。'
    if state.get('demand'):
        quantity = state.get('quantity')
        if quantity is None:
            reply += '请明确本次需求数量，安全库存不能代替本次需求判断。'
        else:
            shortage = max(quantity - current, Decimal(0))
            reply += f'本次需求 {_number(quantity)}{unit}，缺口 {_number(shortage)}{unit}，' + ('库存不足。' if shortage > 0 else '数量足够。')
    return w._ai_json_response(reply, cards, [{'label':'打开库存查询','url':url_for('stock_query',warehouse_id=warehouse.id,search=material.code)}])


def _purchase_progress(message):
    w = _app()
    numbers = re.findall(r'(?i)(?<![A-Za-z0-9])PO[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*', message)
    if not numbers or not re.search(r'查|订购|已收|欠|未收|进度|还差|入库多少', message):
        return None
    if not w._ai_capability_allowed('purchase_insights'):
        return w._ai_permission_denied_response('purchase_insights')
    if len(set(numbers)) != 1:
        return w._ai_json_response('请明确一张采购订单编号。')
    order = w.PurchaseOrder.query.filter(w.db.func.lower(w.PurchaseOrder.order_no) == numbers[0].lower()).first()
    if not order:
        return w._ai_json_response(f'没有找到采购订单 {numbers[0]}。')
    execution = w.build_purchase_order_execution(order)
    lines = [f'采购订单 {order.order_no}，以下数量按全部明细及已完成的关联入库统计：']
    cards = []
    for item in order.items:
        row = execution[item.id]
        material = item.material
        unit = material.unit.name if material and material.unit else ''
        remaining = max(Decimal(str(row['order_quantity'])) - Decimal(str(row['completed_quantity'])), Decimal(0))
        description = f'订购 {_number(row["order_quantity"])}{unit}，已入库 {_number(row["completed_quantity"])}{unit}，未入库 {_number(remaining)}{unit}，其中待完成入库 {_number(row["pending_receive_quantity"])}{unit}。'
        title = f'{material.code} {material.name} {material.spec or ""}' if material else f'物料ID {item.material_id}'
        lines.append(title + '：' + description)
        cards.append({'title':title,'meta':description,'url':url_for('purchase_order_detail',id=order.id)})
    return w._ai_json_response('\n'.join(lines), cards, [{'label':'打开采购订单','url':url_for('purchase_order_detail',id=order.id)}])


def _manual_inbound_rules(message):
    if not (re.search(r'采购订单|采购单|\bPO\b', message, re.I) and re.search(r'没有|无需|无采购|不关联|未关联|必须|必填', message)
            and re.search(r'入库', message) and re.search(r'吗|能否|能不能|是否|规则|解释|可以', message)):
        return None
    w = _app()
    if not w._ai_capability_allowed('knowledge_base'):
        return w._ai_permission_denied_response('knowledge_base')
    return w._ai_json_response(
        '可以手工新增采购入库单。采购订单是可选来源，不强制关联；有关联时保留来源及执行进度。'
        '仓库始终必填：启用默认仓库带入且已配置有效默认仓库时可自动带入，否则须手工选择。'
        '开启库位管理时库位也必填，可带入有效默认库位，否则须选择。'
        '保存草稿不改变库存，人工在业务页点击完成后才写入库存。',
        actions=[{'label':'打开采购入库','url':url_for('in_order_list')}])


def read_query_response(message, context=None, history=None):
    """Shared JSON/SSE read path. None means preserve the existing handler chain."""
    w = _app()
    if re.fullmatch(r'(今天|今日)(概况|汇总)[？?]?', message.strip()):
        if not w._ai_capability_allowed('warehouse_insights'):
            return w._ai_permission_denied_response('warehouse_insights')
        reply, cards = w._ai_today_summary()
        return w._ai_json_response(reply, cards, [{'label':'打开首页','url':url_for('index')}])
    if re.search(r'你会什么|你能做什么|哪些事情不能替我做', message):
        return w._ai_json_response('我可以按权限查询库存、单据和待处理事项，解释流程，识别文本/图片并提供人工确认页。库存和金额以实时查询为准；未配置模型时部分推理或图片能力不可用。提交、审核、完成、删除、改库存、恢复备份及修改密码须由人工在业务页面操作。')
    if re.search(r'数量先不填|不填数量|数量待定|不知道数量', message) and re.search(r'单|草稿', message):
        return w._ai_json_response('请先补充物料、仓库及大于0的数量；数量未知时不会猜测数量或创建业务单据。')
    response = _manual_inbound_rules(message)
    if response is not None:
        return response
    if re.search(r'有哪些物料|所有物料', message) and not re.search(r'低库存|预警|异常|缺货', message):
        if not w._ai_capability_allowed('warehouse_insights'):
            return w._ai_permission_denied_response('warehouse_insights')
        warehouse, error = _warehouse(message)
        if error:
            return w._ai_json_response(error)
        warehouse = warehouse or w.get_default_warehouse()
        if not warehouse:
            return w._ai_json_response('请选择一个有效仓库。')
        quantities = w.get_warehouse_stock_quantities(warehouse)
        query = w.Material.query.order_by(w.Material.code)
        total = query.count()
        cards = []
        for material in query.limit(20).all():
            card = w._ai_material_payload(material)
            card.update(stock=w.normalize_stock_quantity(quantities.get(material.id,0)), warehouse=warehouse.name)
            cards.append(card)
        return w._ai_json_response(f'仓库「{warehouse.name}」按物料档案列出前{len(cards)}条，共{total}条；无此仓库存记录显示0，不同单位不合计。', cards,
                                  [{'label':'完整库存列表','url':url_for('stock_query',warehouse_id=warehouse.id)}])
    if re.search(r'哪些|什么|多少|几张|列出|查询|查看', message) and re.search(r'今天|今日', message):
        inbound = bool(re.search(r'入库|到货|收货|送了', message))
        outbound = bool(re.search(r'出库|领料|发出', message))
        if inbound or outbound:
            if not w._ai_capability_allowed('warehouse_insights'):
                return w._ai_permission_denied_response('warehouse_insights')
            warehouse, error = _warehouse(message)
            if error:
                return w._ai_json_response(error)
            suppliers = [s for s in w.Supplier.query.all() if (s.name and s.name in message) or (s.code and s.code in message)] if inbound else []
            if len(suppliers) > 1:
                return w._ai_json_response('请明确一个供应商名称或编码。')
            if inbound and '供应商' in message and not suppliers:
                return w._ai_json_response('没有找到供应商，请明确有效的供应商名称或编码。')
            if suppliers:
                reply, cards = w._ai_supplier_deliveries(suppliers[0].name, warehouse=warehouse)
            else:
                reply, cards = (w._ai_today_received_materials(warehouse=warehouse) if inbound
                                else w._ai_today_issued_materials(warehouse=warehouse))
            scope = f'仓库「{warehouse.name}」' if warehouse else '全部仓库'
            return w._ai_json_response(f'{scope}，仅统计已完成单据。' + reply, cards,
                [{'label':'打开单据列表', 'url':url_for('in_order_list' if inbound else 'out_order_list')}])
    response = _purchase_progress(message)
    if response is not None:
        return response
    numbers = re.findall(r'(?i)(?<![A-Za-z0-9])(?:PO|IN|OUT|SO|PR|ADJ|CK|SUB|REQ)\d{5,}', message)
    if numbers and re.search(r'查|查询|查看|单号|单据', message):
        capability = 'purchase_insights' if numbers[0].upper().startswith(('PO','PR')) else ('sales_insights' if numbers[0].upper().startswith('SO') else 'warehouse_insights')
        if not w._ai_capability_allowed(capability):
            return w._ai_permission_denied_response(capability)
        if len(set(numbers)) != 1:
            return w._ai_json_response('请明确一个单据编号。')
        cards = w._ai_find_orders(numbers[0])
        return w._ai_json_response(f'找到 {len(cards)} 张相关单据。' if cards else f'没有找到单据 {numbers[0]}，请核对单号；不会猜测单据数据。', cards)
    if w._ai_is_page_navigation_question(message):
        response = w._ai_page_navigation_response(message, context)
        if response is not None:
            return response
    if re.search(r'库存.*(?:报表|台账).*(?:来源|口径)|库存.*数据来源', message):
        if not w._ai_capability_allowed('warehouse_insights'):
            return w._ai_permission_denied_response('warehouse_insights')
        return w._ai_json_response('当前库存按选定仓库的库存账/库存流水查询；实际出入库按已完成单据统计，未完成草稿不算实际入库或出库。报表的数量汇总按完整筛选范围计算，不把当前页当全部。')
    if re.search(r'库存金额|库存价值|资金占用', message):
        if not w._ai_capability_allowed('warehouse_insights'):
            return w._ai_permission_denied_response('warehouse_insights')
        warehouse, error = _warehouse(message)
        if error:
            return w._ai_json_response(error)
        if warehouse:
            quantities = w.get_warehouse_stock_quantities(warehouse)
            materials = w.Material.query.filter(w.Material.id.in_(list(quantities))).all()
            amount = sum((Decimal(str(quantities[m.id])) * Decimal(str(m.price or 0)) for m in materials), Decimal(0))
            return w._ai_json_response(f'仓库「{warehouse.name}」库存金额 {_number(amount)}元，按该仓全部物料库存 × 档案单价计算。')
        response = w._ai_execute_intent(message, {'intent':'analysis_stock_value','params':{}}, context)
        body = response.get_json()
        return w._ai_json_response('全系统口径。' + body['reply'], body.get('cards'), body.get('actions'))
    if re.search(r'缺料.*(?:原因|一定|步骤)|库存.*(?:错了|为什么|怎么办)', message):
        if not w._ai_capability_allowed('knowledge_base'):
            return w._ai_permission_denied_response('knowledge_base')
        return w._ai_json_response('缺料不一定是账错。请依次核查：\n1. 实际可用数量不足：按物料编码、规格和领用仓库核对本次需求及实物。\n2. 单据仍是草稿：检查入库单是否pending；保存不增加库存，需人工完成。\n3. 仓库或物料选错：对照库存查询和流水，检查是否入到其他仓库或相似规格。\n确认实物差异后先盘点，再由人工核对调整草稿，不直接改库存。')
    # A narrow arithmetic form is safe offline; never evaluate user expressions.
    stocktake = re.search(r'账面\s*(\d+(?:\.\d+)?)\s*(套|个|件|米).*实盘\s*(\d+(?:\.\d+)?)\s*\2', message)
    if stocktake and re.search(r'怎么|如何|处理', message):
        difference = Decimal(stocktake[3]) - Decimal(stocktake[1])
        return w._ai_json_response(f'按你提供的数量，实盘减账面差异 {_number(difference)}{stocktake[2]}。先核对物料、仓库和实盘数，再录入盘点单；差异通过调整草稿人工确认完成，不直接修改库存。')
    packages = re.search(r'(\d+(?:\.\d+)?)\s*个零件.*每箱\s*(\d+(?:\.\d+)?)\s*个.*已发\s*(\d+(?:\.\d+)?)\s*箱', message)
    if packages and re.search(r'算|剩多少', message):
        remaining = Decimal(packages[1]) - Decimal(packages[2]) * Decimal(packages[3])
        return w._ai_json_response(f'按你提供的数量计算，还剩 {_number(remaining)}个；没有查询或修改业务单据。')
    receipt = re.search(r'订\s*(\d+(?:\.\d+)?)\s*(套|个|件|米).*已到\s*(\d+(?:\.\d+)?)\s*\2.*其中\s*(\d+(?:\.\d+)?)\s*\2退', message)
    if receipt and re.search(r'净收|还欠', message):
        net = Decimal(receipt[3]) - Decimal(receipt[4])
        remaining = max(Decimal(receipt[1]) - net, Decimal(0))
        return w._ai_json_response(f'按你提供的数量计算，净收到 {_number(net)}{receipt[2]}，还欠 {_number(remaining)}{receipt[2]}；不是系统单据查询结果，也没有修改单据。')
    per = re.search(r'每件(?:要|需|需要)?\s*(\d+(?:\.\d+)?)\s*米', message)
    count = re.search(r'(?:做|生产)\s*(\d+(?:\.\d+)?)\s*件', message)
    loss = re.search(r'(\d+(?:\.\d+)?)\s*%\s*损耗', message)
    if per and count and loss and re.search(r'多少|计算', message):
        if not w._ai_capability_allowed('knowledge_base'):
            return w._ai_permission_denied_response('knowledge_base')
        total = Decimal(per[1]) * Decimal(count[1]) * (1 + Decimal(loss[1])/100)
        return w._ai_json_response(f'共需 {_number(total)}米（每件{per[1]}米 × {count[1]}件，另加{loss[1]}%损耗）。这里只计算，不创建单据。')
    return _stock_response(message, history)
