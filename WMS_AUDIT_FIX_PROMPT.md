# WMS 系统仓库必填规则全面修复 AI 提示词

> **使用说明**：把本文件全文作为 prompt 发给 AI 编码助手（如 TRAE/Cursor/Copilot），AI 会按顺序执行 P0 → P1 → P2 修复。每个修复项都是独立 atomic action，修一个 commit 一个 push 一个，不批量打包。
>
> **修复前必读**：
> 1. 先 `bash .githooks/install-hooks.sh` 启用 pre-commit 钩子（A1-A9 规则门禁）
> 2. 先 `cat AGENTS.md` 阅读仓库与库位必填规则全文
> 3. 先 `cat DEVELOPMENT_RULES.md` 阅读 9 条防 BUG 规则
> 4. 所有提交直接到 `main` 分支，**禁止建分支**
> 5. 业务 JS 禁止裸 `fetch`，必须用 `WMS.api.post/put/delete`
> 6. 新增 POST/PUT/DELETE 路由必须用 pydantic BaseModel 输入校验（A8）
> 7. 新增业务函数必须在 `tests/` 至少 1 个 pytest 测试（A9）

---

## 背景

依据 `AGENTS.md` 仓库与库位必填规则，对 WMS 系统做了一次全面审计，发现 **3 个 P0 数据正确性 BUG** + **4 类 P1 设计缺陷** + **5 个 P2 前端模板缺失**。本提示词逐项给出修复方案、关键代码位置、回归测试要求。

### 规则速查

| 规则 | 未开启库位管理 | 开启库位管理 |
|---|---|---|
| 出入库单据 | 仓库必填，可默认仓库 | 仓库+库位均必填，可默认 |
| 库存查询/报表/台账 | 仓库必填筛选项 | 仓库必填筛选，库位可选 |
| 仓库与库位 | 不同层级概念，**不得混淆或互相替代** | 同左 |

### 仓库与库位概念

- **仓库（Warehouse）**：物理存储设施（如"主仓库"、"原料仓"）
- **库位（Location）**：仓库内部的细分储位（如"A-01-02"）
- 仓库始终是必填项，库位管理未开启时不要求库位

---

## P0 修复（数据正确性，必须立即修复）

### P0-1：`complete_in_order` 仓库赋值被 SQLite rollback 丢弃

**BUG ID**：BUG-2026-08-02-009  
**位置**：`app/app.py` 函数 `complete_in_order`（约第 27257-27348 行）  
**根因**：`order.warehouse = default_wh.name` 写在 `_acquire_order_write_lock` **之前**，而该锁在 SQLite 分支会 `db.session.rollback()`，导致锁前赋值被丢弃，存量无仓库 pending 入库单完成时以 `warehouse=NULL` 落库 + 库位库存不同步。

**参照模板**：`complete_out_order`（约第 34692-34774 行）已正确实现此修复，注释明确说明"实际赋值放到加锁后完成"。

**修复方案**：

1. **锁前只做 fast-path 读校验**（不修改 order 对象）：
```python
# 锁前 fast-path：无仓库且无默认仓库时直接拒绝，不修改 order 对象
# 实际赋值放到加锁后完成，避免 SQLite 分支 rollback 丢弃
if not order.warehouse and not get_default_warehouse():
    return api_error('入库单必须填写仓库')
```

2. **删除锁前的 `order.warehouse = default_wh.name` 赋值代码块**

3. **加锁后 `order = locked` 之后再做实际赋值与必填校验**：
```python
locked, ok = _acquire_order_write_lock(InOrder, id, 'pending', selectinload(InOrder.items))
if not ok:
    return api_error('该入库单已提交，不能重复操作')
order = locked
if not order.items:
    db.session.rollback()
    return api_error('请至少添加一条入库明细')
# 加锁后再做仓库赋值与必填校验，避免锁前修改被 rollback 丢弃
if not order.warehouse:
    default_wh = get_default_warehouse()
    if default_wh:
        order.warehouse = default_wh.name
if not order.warehouse:
    db.session.rollback()
    return api_error('入库单必须填写仓库')
use_location = bool(location_management_enabled() and order.warehouse)
```

**回归测试**：扩展 `scripts/verify_bug_2026_08_02_001.py`，新增 D5 用例：
- 创建一个 `warehouse=""` 的 pending 入库单
- 调用 `/in_order/<id>/complete`
- 断言 `order.warehouse == default_wh.name`（不是空字符串）
- 断言响应 200

**验收命令**：
```bash
python3 scripts/verify_bug_2026_08_02_001.py  # 必须全绿
python3 scripts/verify_in_order_state_machine.py  # 不能回归
```

**commit message**：
```
fix(in_order): BUG-2026-08-02-009 complete_in_order 仓库赋值移到锁后

锁前 order.warehouse = default_wh.name 被 _acquire_order_write_lock
的 SQLite 分支 rollback 丢弃，导致存量无仓库 pending 入库单完成时
以 warehouse=NULL 落库 + 库位库存不同步。

改为锁前只做 fast-path 读校验，实际赋值移到 order = locked 之后，
与 complete_out_order 实现对齐。
```

---

### P0-2：`complete_adjustment` / `revert_adjustment` 不同步库位库存

**BUG ID**：BUG-2026-08-02-010  
**位置**：`app/app.py` 函数 `complete_adjustment`（约第 33090-33142 行）、`revert_adjustment`（约第 33148-33195 行）  
**根因**：只调 `add_stock`/`deduct_stock_atomic` 改 `Material.stock` 总库存，**完全不调 `update_location_inventory`**，`AdjustmentOrderItem.location` 字段存在却被忽略。开启库位管理后，每次调整完成都让总库存与库位库存之和产生偏差，且无法通过对称回退修复。

**参照模板**：`complete_in_order`（约第 27313-27317 行）的正确写法：
```python
if location_management_enabled() and order.warehouse:
    loc_ok, loc_err = update_location_inventory(item.material, order.warehouse, item.quantity or 0)
```

**修复方案**：

1. **`complete_adjustment`** 在 `add_stock` / `deduct_stock_atomic` 之后补库位同步：
```python
for item in adjustment.items:
    if not item.material_id:
        continue
    quantity = item.quantity or 0
    if quantity > 0:
        ok, err = add_stock(item.material, quantity, transaction_type='adjustment_in', ...)
    elif quantity < 0:
        ok, err, _ = deduct_stock_atomic(item.material_id, abs(quantity), transaction_type='adjustment_out', ...)
    # BUG-2026-08-02-010 修复：开启库位管理时同步库位库存
    # 使用 item.location（如有）或 adjustment 的仓库字段作为库位 key
    if location_management_enabled():
        loc_key = item.location or adjustment.warehouse  # 优先 item.location，回退单据仓库
        if loc_key:
            if quantity > 0:
                update_location_inventory(item.material, loc_key, quantity)
            elif quantity < 0:
                deduct_location_inventory_atomic(item.material_id, loc_key, abs(quantity))
```

2. **`revert_adjustment`** 对称回退库位库存（与 complete 相反方向）。

**前置依赖**：本修复依赖 P1-2（AdjustmentOrder 模型加 warehouse 字段）。若 P1-2 未完成，先用 `item.location` 作为库位 key，注释标记 TODO 等模型字段补齐后切换为 `adjustment.warehouse`。

**回归测试**：创建 `scripts/verify_bug_2026_08_02_003.py`：
- 开启 `location_management_enabled`
- 创建一个带 `item.location='测试库位'` 的 pending 调整单
- 调用 `/adjustment/<id>/complete`
- 断言 `LocationInventory` 中该库位的数量已更新
- 断言 `Material.stock` 也已更新（总库存与库位库存一致）
- 调用 `/adjustment/<id>/revert`
- 断言 `LocationInventory` 已回退

**验收命令**：
```bash
python3 scripts/verify_bug_2026_08_02_003.py
python3 scripts/verify_adjustment_state_machine.py  # 不能回归
```

**commit message**：
```
fix(adjustment): BUG-2026-08-02-010 complete/revert_adjustment 同步库位库存

之前只改 Material.stock 总库存，不调 update_location_inventory，
导致开启库位管理后总库存与库位库存之和产生偏差，且无法对称回退。

补齐库位同步逻辑，与 complete_in_order 对齐。
```

---

### P0-3：`batch_delete_in_order` 未回退采购订单进度 + 未加写锁

**BUG ID**：BUG-2026-08-02-011  
**位置**：`app/app.py` 函数 `batch_delete_in_order`（约第 27915-27949 行）  
**根因**：
1. 删除循环未回退 `source_purchase_order_item.received_quantity`，未调用 `update_purchase_order_status`，与单条删除 `delete_in_order`（约第 27766-27780 行）逻辑不对称
2. 未调用 `_acquire_order_write_lock`，存在并发完成导致已完成单被删的竞态

**参照模板**：`delete_in_order`（约第 27745-27787 行）的正确实现。

**修复方案**：

```python
@app.route('/in_order/batch_delete', methods=['POST'])
@login_required
def batch_delete_in_order():
    # ... 读取 ids ...
    orders = InOrder.query.filter(InOrder.id.in_(ids)).all()
    blocked = [o.order_no for o in orders if o.status != 'pending']
    if blocked:
        return api_error(f'以下入库单不是草稿状态，不能删除：{", ".join(blocked)}')

    deleted_count = 0
    affected_purchase_order_ids = set()
    for order in orders:
        # BUG-2026-08-02-011 修复：逐条加写锁，防止并发完成后误删
        locked, ok = _acquire_order_write_lock(InOrder, order.id, 'pending', selectinload(InOrder.items))
        if not ok:
            db.session.rollback()
            continue  # 已被并发完成，跳过
        order = locked
        # 回退采购订单来源进度（与 delete_in_order 对齐）
        for item in list(order.items):
            if item.source_purchase_order_item_id:
                poi = SourcePurchaseOrderItem.query.get(item.source_purchase_order_item_id)
                if poi:
                    poi.received_quantity = (poi.received_quantity or 0) - (item.quantity or 0)
                    affected_purchase_order_ids.add(poi.purchase_order_id)
            db.session.delete(item)
        db.session.delete(order)
        deleted_count += 1

    # 更新受影响的采购订单状态
    from app import update_purchase_order_status
    for po_id in affected_purchase_order_ids:
        po = PurchaseOrder.query.get(po_id)
        if po:
            update_purchase_order_status(po)

    db.session.commit()
    return jsonify({'status': 'success', 'deleted_count': deleted_count})
```

**回归测试**：创建 `scripts/verify_bug_2026_08_02_004.py`：
- 创建一个带 `source_purchase_order_item_id` 的 pending 入库单
- 调用 `/in_order/batch_delete` 删除它
- 断言 `source_purchase_order_item.received_quantity` 已回退
- 断言采购订单状态已更新
- 断言入库单已删除

**验收命令**：
```bash
python3 scripts/verify_bug_2026_08_02_004.py
python3 scripts/verify_in_order_state_machine.py  # 不能回归
```

**commit message**：
```
fix(in_order): BUG-2026-08-02-011 batch_delete_in_order 补采购订单进度回退+写锁

与 delete_in_order 逻辑对齐：
1. 逐条加 _acquire_order_write_lock，防止并发完成后误删
2. 删除前回退 source_purchase_order_item.received_quantity
3. 删除后调用 update_purchase_order_status 更新采购订单状态
```

---

## P1 修复（设计缺陷，需模型 migration）

### P1-1：TransferOrder / InventoryCheck / AdjustmentOrder 模型加 warehouse 字段

**BUG ID**：BUG-2026-08-02-012  
**位置**：
- `TransferOrder` 模型（约第 4350-4364 行）
- `InventoryCheck` 模型（约第 3725-3735 行）
- `AdjustmentOrder` 模型（约第 4385-4402 行）

**根因**：三个模型均无 `warehouse` 字段，导致无法满足 AGENTS.md "调拨、盘点、调整…仓库是必填项"规则。TransferOrder 用 `from_location`/`to_location` 存储 `Warehouse.name`，仓库与库位概念混淆。

**修复方案**：

1. **模型层加字段**（migration）：
```python
class TransferOrder(db.Model):
    # 保留 from_location/to_location 作为库位字段（开启库位管理时使用）
    from_location = db.Column(db.String(100), nullable=False)  # 调出仓库（未开库位）或调出库位（开库位）
    to_location = db.Column(db.String(100), nullable=False)
    # 新增：调出仓库 + 调入仓库（仓库必填，库位可选）
    from_warehouse = db.Column(db.String(100), nullable=False)  # 调出仓库
    to_warehouse = db.Column(db.String(100), nullable=False)    # 调入仓库

class InventoryCheck(db.Model):
    warehouse = db.Column(db.String(100), nullable=False)  # 盘点仓库，必填

class AdjustmentOrder(db.Model):
    warehouse = db.Column(db.String(100), nullable=False)  # 调整仓库，必填
```

2. **migration 脚本**：创建 `scripts/migrate_add_warehouse_to_transfer_check_adjustment.py`
   - 对 TransferOrder：从 `from_location`/`to_location`（当前存的是仓库名）回填到 `from_warehouse`/`to_warehouse`
   - 对 InventoryCheck/AdjustmentOrder：存量数据回填默认仓库名

3. **路由层补校验**：
   - `save_transfer_table` / `add_transfer`：读取 `from_warehouse`/`to_warehouse`，未填时自动带入默认仓库，无默认仓库拒绝保存
   - `save_check_table` / `add_check`：读取 `warehouse`，未填时自动带入默认仓库
   - `add_adjustment`：读取 `warehouse`，未填时自动带入默认仓库

4. **前端模板补字段**：
   - `transfer.html`：新增"调出仓库"/"调入仓库"下拉，保留 `from_location`/`to_location` 作为库位字段
   - `check.html`：新增盘点仓库下拉
   - `adjustment_add.html`：新增调整仓库下拉

**回归测试**：创建 `scripts/verify_bug_2026_08_02_005.py`：
- 静态检查模型字段存在
- 动态测试：无仓库时拒绝保存、有默认仓库时自动带入、complete 时 warehouse 落库

**注意**：本修复涉及 migration，需在维护窗口执行。`nullable=False` 加字段对存量数据需先回填再 alter。

**commit message**：
```
feat(model): BUG-2026-08-02-012 TransferOrder/InventoryCheck/AdjustmentOrder 加 warehouse 字段

三个模型原本无 warehouse 字段，违反 AGENTS.md 仓库必填规则。
TransferOrder 用 from_location/to_location 存仓库名，概念混淆。

- TransferOrder 新增 from_warehouse/to_warehouse（保留 from_location/to_location 作库位）
- InventoryCheck 新增 warehouse
- AdjustmentOrder 新增 warehouse
- 路由层补仓库必填校验 + 默认仓库带入
- 前端模板补仓库下拉
- migration 脚本回填存量数据
```

---

### P1-2：`complete_adjustment` 使用 `adjustment.warehouse` 同步库位（依赖 P1-1）

**位置**：`app/app.py` 函数 `complete_adjustment`  
**说明**：P0-2 修复中用 `item.location or adjustment.warehouse` 作为 loc_key，P1-1 完成后改为优先用 `adjustment.warehouse`：
```python
loc_key = adjustment.warehouse or item.location
```

---

### P1-3：调拨/盘点/调整三类路由补 `location_management_enabled()` 判断

**BUG ID**：BUG-2026-08-02-013  
**位置**：
- `complete_transfer`（约第 32306 行）
- `complete_check`（约第 33659 行）
- `complete_adjustment`（约第 33090 行，P0-2 已部分修复）

**根因**：三类路由均未调用 `location_management_enabled()`，与入库/出库的 `if location_management_enabled() and order.warehouse:` 模式不一致。

**修复方案**：
- `complete_transfer`：把 `update_location_inventory` 调用包在 `if location_management_enabled() and transfer.from_warehouse:` 内
- `complete_check`：生成的调整草稿带上 warehouse 信息
- `complete_adjustment`：P0-2 已补，确认判断开关

**commit message**：
```
fix(transfer_check_adjust): BUG-2026-08-02-013 三类路由补 location_management_enabled 判断

与入库/出库对齐，未开启库位管理时不写 LocationInventory，避免冗余记录。
```

---

### P1-4：库存查询/报表/台账仓库必填筛选

**BUG ID**：BUG-2026-08-02-014  
**位置**：22 个路由（详见审计报告），核心是 `_build_report_filters`（约第 38003-38017 行）无 warehouse 字段  
**根因**：系统不存在 `StockBalance` 按仓库维度的当前库存余额表，`Material.stock` 是单一聚合值，无法按仓库拆分当前库存。

**修复方案**（分两步）：

**步骤 1（最小改动，先满足规则）**：
- `_build_report_filters` 增加 `warehouse` 字段，为空时 `raise ValueError`
- `report_api_query` 捕获 ValueError 返回 400 "请选择仓库"
- `/stock_query`、`/alert`、`/opening_stock`、`/sales/outflow_report` 等查询入口增加 warehouse 必填校验
- `in_detail`/`out_detail`/`ledger`/`summary` 等 builder 的 SQL 加 `.filter(InOrder.warehouse == warehouse)` / `.filter(OutOrder.warehouse == warehouse)`
- `/report/view/<report_type>` 模板加仓库必填下拉

**步骤 2（架构改造，可选）**：
- 引入 `StockBalance(material_id, warehouse_id, quantity)` 表
- `Material.stock` 改为按仓库汇总的视图或冗余字段
- `StockTransaction` / `LocationInventory` 加 `warehouse_id` 外键 + migration 回填

**回归测试**：创建 `scripts/verify_bug_2026_08_02_006.py`：
- 无 warehouse 参数调用 `/report/api/query` 返回 400
- 有 warehouse 参数时 SQL 带 warehouse 过滤
- `/stock_query` 无 warehouse 参数返回 400 或空结果

**commit message**：
```
feat(report): BUG-2026-08-02-014 库存查询/报表/台账仓库必填筛选

22 个路由全部缺失仓库必填筛选，违反 AGENTS.md 规则。
- _build_report_filters 增加 warehouse 字段，为空时 raise
- report_api_query 捕获返回 400
- /stock_query /alert /opening_stock /sales_outflow_report 补必填校验
- in_detail/out_detail/ledger/summary builder SQL 加 warehouse 过滤
```

---

## P2 修复（前端模板缺失）

### P2-1：`after_sale_out_detail.html` 详情页补显示仓库

**位置**：`app/templates/after_sale_out_detail.html` 基本信息卡片（约第 56-95 行）  
**修复**：在基本信息卡片中补：
```html
<p><strong>仓库：</strong>{{ order.warehouse or '-' }}</p>
```

**commit message**：
```
fix(template): 售后出库详情页补显示仓库字段
```

---

### P2-2：`check.html` 新增盘点单模态框补仓库字段

**位置**：`app/templates/check.html` 新增盘点单模态框（约第 134-155 行）  
**修复**：
```html
<div class="mb-3">
    <label class="form-label">仓库 <span class="text-danger">*</span></label>
    <select class="form-select" name="warehouse" required>
        <option value="">请选择仓库</option>
        {% for warehouse in warehouses %}
        <option value="{{ warehouse.name }}" {% if default_warehouse and default_warehouse.name == warehouse.name %}selected{% endif %}>{{ warehouse.name }}</option>
        {% endfor %}
    </select>
</div>
```
JS 提交前校验：`if (!warehouse) { showToast('仓库不能为空', 'warning'); return; }`

**依赖**：P1-1（InventoryCheck 模型加 warehouse 字段）

**commit message**：
```
fix(template): 盘点单新增模态框补仓库必填字段
```

---

### P2-3：`adjustment_add.html` 表头补仓库字段

**位置**：`app/templates/adjustment_add.html` 表头区域（约第 287-321 行）  
**修复**：表头补仓库下拉（与 P2-2 同款），保留 `adjust-location` 作为库位字段。  
**依赖**：P1-1（AdjustmentOrder 模型加 warehouse 字段）

**commit message**：
```
fix(template): 调整单表头补仓库必填字段，保留库位字段
```

---

### P2-4：`transfer.html` 调拨新增模态框补 default_warehouse 预选

**位置**：`app/templates/transfer.html`（约第 149-162 行）  
**修复**：调出/调入仓库下拉按 `default_warehouse` 预选：
```html
<option value="{{ warehouse.name }}" {% if default_warehouse and default_warehouse.name == warehouse.name %}selected{% endif %}>{{ warehouse.name }}</option>
```
JS 补"调出仓库 ≠ 调入仓库"前端校验。

**commit message**：
```
fix(template): 调拨单补默认仓库预选+调出调入不能相同校验
```

---

### P2-5：`opening_stock.html` 表头仓库补 default_warehouse 预选

**位置**：`app/templates/opening_stock.html`（约第 194 行）  
**修复**：表头仓库下拉按 `default_warehouse` 预选。

**commit message**：
```
fix(template): 期初库存表头仓库补默认预选
```

---

## 执行顺序与依赖关系

```
P0-1 (complete_in_order 锁后赋值)        ── 独立，立即执行
P0-3 (batch_delete_in_order 补回退+锁)    ── 独立，立即执行
P1-1 (三个模型加 warehouse 字段+migration) ── 独立，但需维护窗口
P0-2 (complete_adjustment 同步库位)        ── 依赖 P1-1（用 adjustment.warehouse）
P1-3 (三类路由补 location_management 判断) ── 依赖 P1-1
P1-4 (库存查询/报表仓库必填筛选)           ── 独立，但 in_detail/out_detail/ledger 依赖 InOrder/OutOrder.warehouse（已有）
P2-1 (after_sale_out_detail 显示仓库)      ── 独立，立即执行
P2-2 (check.html 补仓库字段)               ── 依赖 P1-1
P2-3 (adjustment_add.html 补仓库字段)      ── 依赖 P1-1
P2-4 (transfer.html 补默认预选)            ── 独立，立即执行
P2-5 (opening_stock.html 补默认预选)       ── 独立，立即执行
```

**推荐执行顺序**：
1. P0-1 → P0-3（立即，数据正确性）
2. P2-1 → P2-4 → P2-5（立即，前端模板，无依赖）
3. P1-1（维护窗口，模型 migration）
4. P0-2 → P1-3（依赖 P1-1）
5. P1-4（报表改造，较大）
6. P2-2 → P2-3（依赖 P1-1）

---

## 每个 atomic action 的验收清单

每个修复完成后必须逐项确认：

- [ ] 代码改动符合本提示词方案
- [ ] 新增/扩展的回归脚本全绿
- [ ] 原有 `scripts/verify_*_state_machine.py` 不回归
- [ ] `python3 scripts/verify_stability_gate.py` 通过
- [ ] `python3 -m pytest tests/ -q` 全过
- [ ] `WMS_BUG_BASELINE.md` 添加对应 BUG 条目
- [ ] `scripts/verify_stability_gate.py` 注册新回归脚本
- [ ] `tests/test_stability_gate.py` 添加对新脚本的断言
- [ ] commit message 关联 BUG ID
- [ ] `git push origin main` 成功，本地与 origin/main SHA 一致

---

## 禁止事项

- ❌ 禁止建分支，所有提交直接到 `main`
- ❌ 禁止批量打包多个修复到一个 commit
- ❌ 禁止用 `git commit --no-verify` 跳过钩子
- ❌ 禁止修改用户密码（规则 B）
- ❌ 禁止强制采购入库关联采购订单（规则 C，`purchase_in_order_requires_order()` 恒 `False`）
- ❌ 禁止业务 JS 裸 `fetch`（必须 `WMS.api`）
- ❌ 禁止把仓库和库位概念混淆（`from_location` 不能再存仓库名）
- ❌ 禁止 AI 自动完成入库单/出库单（只能创建草稿，完成需人工）
- ❌ 禁止删除已完成入库单（必须先反提交回草稿）

---

## 参考文件

- [AGENTS.md](file:///workspace/AGENTS.md) — 仓库与库位必填规则全文
- [DEVELOPMENT_RULES.md](file:///workspace/DEVELOPMENT_RULES.md) — 9 条防 BUG 规则
- [WMS_BUG_BASELINE.md](file:///workspace/WMS_BUG_BASELINE.md) — BUG 台账
- [WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md](file:///workspace/WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) — AI 开发台账
- [scripts/verify_bug_2026_08_02_001.py](file:///workspace/scripts/verify_bug_2026_08_02_001.py) — 入库仓库必填回归
- [scripts/verify_bug_2026_08_02_002.py](file:///workspace/scripts/verify_bug_2026_08_02_002.py) — 出库/售后出库仓库必填回归
- [app/app.py](file:///workspace/app/app.py) — 主应用代码
