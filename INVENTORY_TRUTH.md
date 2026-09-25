# 库存真相（INVENTORY_TRUTH.md）

> **文档定位**：本文件回答一个问题——**这个系统里的"库存"到底以哪份数据为准？**
> 与 [`AGENTS.md`](./AGENTS.md)、[`WMS_BUSINESS_SCOPE.md`](./WMS_BUSINESS_SCOPE.md)、[`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md) 配套使用。
> 新增日期：2026-09-11。修改本文件属于独立 atomic action（1 commit + 1 push）。

---

## 0. 为什么需要这份文档

实测数据（2026-09-11）：

- `WMS_BUG_BASELINE.md` 累计 **322 条** BUG，其中 9 月 52 条里 **39 条为 P1**。
- `AGENTS.md` R2（多仓库边界）的实证来源写着"08-16/08-17/08-23/08-27 系列 **20+ 条**"同类 BUG。
- 同一根因（取了全局库存而非仓库级库存）在 **四个不同消费点**分别复发：
  `BUG-2026-09-02-001`（`native_api` 盘点）、`BUG-2026-09-03-001`（Excel 导入盘点）、
  `BUG-2026-09-03-002`（`mobile` 展示）、`BUG-2026-09-03-004`（Android 展示）。

**根因不是某个人写错了某一行，而是"库存"在系统里不只有一个定义。**
任何一次库存相关改动，都必须同时想清楚 6 种组合（总账 / 库位账 / 流水 × 开库位 / 关库位），
而这份组合关系此前只散落在代码注释里。本文档把它固化下来。

---

## 1. 三份数据是什么

| # | 数据 | 物理位置 | 粒度 | 语义 |
|---|---|---|---|---|
| ① | **总账** | `material.stock` | 物料 | 该物料**全系统合计**在库数量 |
| ② | **库位账** | `location_inventory.quantity` | 物料 × 仓库 × 库位 | 该物料**在该仓库该库位**的在库数量 |
| ③ | **流水账** | `stock_transaction.quantity` | 物料 × 单据 × 时间 | 一次库存变动的**带符号增量**（只增不改） |

三者的权威关系：

```
                    ┌─────────────────────────────┐
                    │  ③ stock_transaction        │  ← 事实来源（append-only）
                    │     唯一不可篡改的账本        │
                    └──────────────┬──────────────┘
                                   │ 累加（按 warehouse_id 归属）
                                   ▼
                    ┌─────────────────────────────┐
                    │  ② location_inventory       │  ← 开启库位管理时的仓库级真相
                    │     = 各库位流水净额的物化    │
                    └──────────────┬──────────────┘
                                   │ 累加（跨仓库跨库位）
                                   ▼
                    ┌─────────────────────────────┐
                    │  ① material.stock           │  ← 全局合计（恒等式主体）
                    └─────────────────────────────┘
```

**核心恒等式（必须始终成立）**：

> **① = Σ(② 按物料汇总) = Σ(③ 按物料汇总)**

任何一次库存写入，都必须在同一事务内维护这条恒等式所涉及的全部层级。**只改其中一层就是账实分裂。**

---

## 2. 派生方向（谁由谁算出来）

| 方向 | 是否允许 | 说明 |
|---|---|---|
| ③ → ② → ① | ✅ **唯一正确方向** | 流水是因，库位账与总账是果 |
| ② → ① | ✅ | 库位账变动后总账同步同额变动 |
| ③ → ① | ✅ | 关库位管理时由流水净额汇总 |
| ① → ② | ❌ **禁止** | 从全局倒推库位会丢失仓库/库位维度 |
| ② 独立于 ③ 变动 | ❌ **禁止** | 库位账必须有对应流水可追溯 |
| ① 独立于 ②③ 变动 | ❌ **禁止** | 除非 `# stock-truth:reason=` 显式豁免（见 §6） |

### 2.1 写入端的唯一入口

代码实证（2026-09-11），总账只有 **三个** 写入函数：

| 函数 | 位置 | 作用 | 同步库位账？ |
|---|---|---|---|
| `deduct_stock_atomic` | `app/app.py:4719` | 原子扣减总账 + 写 `out`/`adjustment_out` 等流水 | ❌ 由调用方负责 |
| `add_stock` | `app/app.py:4787` | 原子增加总账 + 写 `in`/`adjustment_in` 等流水 | ❌ 由调用方负责 |
| `_apply_opening_stock_balance` | `app/app.py:8239` | 期初建账（改总账 + 写 `opening` 流水） | ✅ 内部同步 |
| `add_stock_transaction` | `app/app.py:5061` | **只写流水，不动总账**（调拨/审计用） | ❌ 由调用方负责 |

**新代码不要直接调上面这些原语**（P1-7，2026-09-25）。三账写入已收敛到
`app/services/warehouse_stock_service.py` 的三个入口，按语义选：

| 语义 | 入口 | ①总账 | ③流水 | ②库位账 |
|---|---|---|---|---|
| 入/出库 | `apply_stock_delta` | 改 | 写 | 写（开库位） |
| 调拨 | `apply_transfer_pair` | **不动** | 写双向 | 调出减/调入加 |
| 建账（初始库存/期初） | `apply_opening_balance` | **不动（调用方负责）** | 写 `opening` | 写（开库位） |

入口内部原样调用上面的原语，失败语义与底层一致（返回 `(False, msg)`，
由调用方 `db.session.rollback()`）。直接手写原语 = 手工双写三账，是
BUG-2026-09-20-008 型静默账实分裂的温床，`tests/test_p1_7_convergence_guards.py`
会拦截已收敛路径上的手写回退。

库位账只有 **两个** 原子写入函数：

| 函数 | 位置 | 作用 |
|---|---|---|
| `add_location_inventory_atomic` | `app/app.py:4918` | 原子增加库位数量（自动建账） |
| `deduct_location_inventory_atomic` | `app/app.py:5003` | 原子扣减库位数量 |
| `update_location_inventory` | `app/app.py:4856` | 分发器：按 delta 正负调用上面两个 |

> 📌 **行号会漂移**：本文件里的 `app/app.py:NNNN` 只是定位提示，
> 以**函数名**为准。`tests/test_inventory_truth_line_refs.py` 会自动校验本文件的
> 函数↔行号引用，行号漂了 CI 会红——改完 app.py 记得顺手跑它。
>
> ⚠️ **注意**：`add_stock` / `deduct_stock_atomic` **不会自动同步库位账**。
> 调用方必须自己再调一次 `update_location_inventory`。这是历史设计，
> 也是 `BUG-2026-08-16-002`（期初只改总账）与 `BUG-2026-08-04-002`（库位静默成功）
> 的温床。**新代码必须两层同时写。**

#### 2.1.1 业务路径的唯一入口：`apply_stock_delta`（P2-3 收敛）

上述「两层同时写」由**调用方负责**的定式是缺陷温床（漏写即**静默**账实分裂，
无任何报错）。P2-3 把三账收敛为**一次调用**，业务路径**只允许经此入口**：

```python
from services.warehouse_stock_service import apply_stock_delta

ok, err = apply_stock_delta(
    material, delta,                     # delta<0 出库 / >0 入库 / ==0 不写账
    transaction_type='...',              # 必传，原样写入 StockTransaction
    reference_type='...', reference_id=...,
    warehouse=warehouse, location=location,   # location 缺省时回退 warehouse
)
# 失败必须 rollback 并显式报错 —— 不得静默成功
```

入口内部按 `delta` 正负分发 `add_stock` / `deduct_stock_atomic`，
并在 `location_management_enabled()` 为真时同步 `update_location_inventory`
（库位键 `location or _stock_location_from_warehouse(warehouse)`，与存量定式逐字一致）。

**收敛进度（P2-3）**：

| 批次 | 范围 | 状态 |
|---|---|---|
| 批 1–2 | in_order / out_order 主链路 | ✅ |
| 批 3 | out_order + after_sale_out（5 路由） | ✅ |
| 批 4 | subcontract 网页版（6 路由） | ✅ |
| **批 5** | **mobile 4 处 + native_api 2 处 + 委外快速收货老 API 1 处** | **✅（2026-09-25）** |
| 批 6（待评估） | `requisition.py` 扣减侧（语义不同，见下） | ⏳ |

> **批 5 的额外收获**：收敛侦察发现 **BUG-2026-09-20-008 的 R6 结论不完备**——
> 它漏掉了 `app/app.py` 的**老 API** `api_subcontract_quick_receive`
> （收货方向漏写库位账，与 008 同型）。根因是**同一业务存在"网页版 + 老 API"
> 双轨实现时，排查只覆盖了其中一套**。教训：R6 排查必须按**路由**而非按
> **文件**清点，双轨实现要两套都查。

> **`requisition.py` 为何单列**：其扣减侧直接调 `deduct_location_inventory_atomic`，
> **绕过** `update_location_inventory` 的「无库位记录且不允许负库存即失败」检查
> （BUG-2026-08-04-002 口径）。收敛到入口会**改变失败语义**（从"静默建负账"
> 变为"显式报错"），属净行为变更，按 R8 单独评估，不夹带。

### 2.1.1 业务单据的库存流入/流出路径（新增单据类型必登记）

| 单据类型 | `business_type` | 库存写库管道 | 数量限额 |
|---|---|---|---|
| 采购/产品/其他入库 | `采购入库` / `产品入库` / `其他入库` | `complete_in_order` → `add_stock` + `update_location_inventory` | 采购行按 `received_quantity` 跟踪 |
| **销售退货入库**（P1-5） | `销售退货入库` | **同上，复用 complete_in_order，不新增写入口** | 退货量 ≤ 原销售行 `shipped_quantity` − 已退量聚合（`sales_return_remaining_check`，无来源行跳过） |
| 销售出库/领料等出库 | `销售出库` / … | `complete_out_order` → `deduct_stock_atomic` + `deduct_location_inventory_atomic` | 销售行按 `sales_outbound_remaining_check` 防超发 |
| **采购退货出库**（P1-7） | `采购退货出库` | **同上，复用 complete_out_order，不新增写入口** | 退货量 ≤ 原入库行量 − 已退量聚合（`purchase_return_remaining_check`；`purchase_return_requires_order=1` 时强制关联来源） |

> 退货类单据**只动库存三账，不改原单计数**（不写 `shipped_quantity` / `received_quantity` 的逆操作）——
> 已退量永远是"聚合查询"而不是"状态字段"，与 §2.2 销售可承诺量的派生哲学一致（STOCK-TRUTH-P16 同源决策）。

### 2.1.2 期初库存的口径：多单据汇总（ARCH-OS-DOC-01）

**期初建账不是"一条记录"，而是"若干张单据的明细行集合"。** 这是改造后
最容易踩错的一处口径，单独说明。

改造背景：用户有多仓库、多物料、多仓管人员，要求期初库存能"分几张单做"，
导入进来的单据还要能改日期。改造前 `opening_stock` 是一张平铺台账，唯一约束
钉死在 `(material_id, warehouse_id)`——同物料同仓只能有一行，分单做不到。

改造后的数据模型：

| 概念 | 表 | 说明 |
|---|---|---|
| 单据头 | `opening_stock_doc` | `doc_no`（QS+YYMM+4位）、`date`（建账日期）、`warehouse_id`（可空，仓库可下放到行）、`status`、`remark`、`operator_id` |
| 明细行 | `opening_stock` | 每行一个 `doc_id` 归属某张单；唯一键收窄为 `(material_id, warehouse_id, doc_id)` |

**核心口径（写代码前必须记住）：**

> 某物料在某仓库的**期初库存** = 该 `(material_id, warehouse_id)` 在
> **所有单据**中明细行 `quantity` 的**合计**。

由此推出三条必须遵守的规则：

1. **同一 `(物料, 仓库)` 可以出现在多张单据里**——这是特性不是脏数据。
   唯一约束只在**单张单内部**生效（防止一张单里重复录同一物料同仓）。
2. **查询期初余额必须聚合，不能取单行。** 任何"按物料+仓库查一行当作期初库存"
   的写法在多单据下都会漏算其他单据的数量（表现为账实不符、差异凭空出现）。
3. **库存是靠差额增量维护的，不是靠重算覆盖。** `_apply_opening_stock_balance`
   的语义是 `delta = 新数量 − 该行旧数量`，然后 `Material.stock += delta`。
   它是**行级**算法，所以天然支持同物料多行——这正是多单据化几乎没动账务
   代码的原因（§2.1 的写入端入口不变）。

**删除/改动的账务后果（必须成对处理）：**

| 操作 | 对 `Material.stock` 的影响 |
|---|---|
| 新建某单据的一行 | `+= 该行数量` |
| 修改某单据某行数量 | `+= (新数量 − 旧数量)` |
| 删除某单据某行 | `+= (−该行数量)`（回冲） |
| 删除整张单据 | 逐行回冲，再物理删除单据头与明细 |
| 修改单据日期 | **不动账**（只改 `date`，同步该单全部明细行） |

> ⚠️ **只删行不回冲 = 库存虚高**，且不会有任何报错——账面静默变错是最难查的一类。
> 删单/删行统一走 `_reverse_opening_stock_line`，它同时写 `opening` 反向流水
> （`StockTransaction`）并同步库位账，保证三账一致（§2.1 的"两层同时写"）。

### 2.2 读取端的口径选择
| 场景 | 应读 | 函数 | 说明 |
|---|---|---|---|
| **业务校验**（够不够扣） | 仓库级 | `get_warehouse_stock_quantities(warehouse)` | **绝不回退全局**，防 A 仓掩护 B 仓 |
| **库存查询/报表** | 仓库级 | 同上 | 仓库是必填筛选项（AGENTS.md 规则一） |
| **物料列表展示** | 全局 | `material.stock` | 仅用于"全系统合计"展示 |
| **反提交兜底校验** | 仓库级 → 全局兜底 | `_material_stock_unattributed` | 见 §4 |
| **销售可承诺量**（STOCK-TRUTH-P16） | 仓库级派生 | `get_warehouse_stock_quantities(wh) − get_committed_quantities(wh.id)` | 占用账是**派生查询不是状态**：不落库、不加第四套口径字段。占用 = `status='confirmed'` 且未发完订单的行级 `quantity−shipped_quantity` 之和（D1：审批通过后占用，草稿不占）。下单/改单软校验（warning），下推硬校验（400/skipped） |
| **采购在途量**（P2-9） | 单据口径（与仓库无关） | `get_purchase_in_transit(...)` / `get_purchase_in_transit_by_material(ids)` | 在途 = Σ **行级** `max(quantity − coalesce(received_quantity,0), 0)`，默认仅 `status in ('pending','partial')`。行级 max(0)：超收行不得以负数抵消其他行的在途；`case` 表达式跨库（MySQL 无标量 `MAX(a,b)`）。**禁止再内联 `sum(quantity − received_quantity)` 聚合**（历史上 6 处消费点三种截断层次同数据不同值，已全部收口；供应商档案卡显式传 `statuses=('pending','partial','completed')` 保留尾差语义） |

---

## 3. 仓库归属：`warehouse_id` 是唯一判据

```python
# app/models/inventory.py:73
warehouse_id = db.Column(db.Integer, db.ForeignKey('warehouse.id'))  # Warehouse ID (NULL = 历史未归属)
```

### 3.1 为什么有 `location` 字符串的历史包袱

`stock_transaction.location` 历史上**混存四种语义**：仓库名 / 仓库编码 / 库位名 / NULL。
`BUG-2026-08-16-006` 与 `BUG-2026-08-27-004` 均由此产生。修复路径（代码自述）：

- **B1（已做）**：新增 `warehouse_id` 外键列 + 索引 `idx_stock_txn_warehouse_id`。
- **B2（已做）**：写入端（`add_stock` / `deduct_stock_atomic` / `add_stock_transaction`）统一落 `warehouse_id`。
- **启动回填（已做）**：`backfill_stock_txn_warehouse_id()`（`app/app.py:28251`）幂等回填历史行。
- **兼容读取**：查询时 `warehouse_id == X` **OR**（`warehouse_id IS NULL` AND `location IN (仓库名/编码/库位名)`）。

### 3.2 铁律：不猜

> **无法唯一确定归属的历史行，`warehouse_id` 保留 NULL，不得自动归入任意默认仓库。**
> —— 依据 AGENTS.md「不猜，不自动归入任意默认仓库」

**这是有意为之的"看得见的空洞"，不是缺陷。** 伪造一个看起来正确的归属，
会让 `BUG-2026-09-02-001` 那类"多仓合计当单仓账面"的错误永远无法被发现。

### 3.3 两个特殊兜底（**改动库存前必读**）

这两处是当前系统里**唯一**允许口径切换的地方，改动前必须理解其条件：

**(a) 单仓库短路**（`app/app.py:5346`，`get_warehouse_stock_quantities` 内）

```python
if Warehouse.query.count() == 1:
    return {m.id: float(m.stock or 0) for m in Material.query.all()}
```

> ⚠️ **这是定时炸弹**：一旦系统新增第二个仓库，所有历史 NULL-location 流水的归属语义**瞬间改变**。
> 新增仓库前必须先在测试库验证该分支退出后的库存数值是否连续。

**(b) 全不可归属回退**（`_material_stock_unattributed`，`app/app.py:5529`）

仅当"该物料**全部**流水都无法归属"时，才允许回退全局 `material.stock` 口径；
只要存在**任意一条**可归属流水，就必须保持仓库级严格校验。
> 存在意义：防止反提交时误报"库存不足"导致单据卡在 `completed` 无法删除（`BUG-2026-08-18-002`）。
> 保持意义：防止 A 仓掩护 B 仓（`BUG-2026-08-16-009`）。

---

## 4. 已知的口径分裂与处理

| 编号 | 现象 | 根因 | 现状 |
|---|---|---|---|
| `BUG-2026-08-16-002` | 期初只改总账，库存查询/报表/移动端全部看不见 | 写入端未同步库位账 | 已修：`_apply_opening_stock_balance` 内部同步 |
| `BUG-2026-08-04-002` | 库位记录不存在时返回 `(True, '')`，账实静默分裂 | 静默成功 | 已修：改为显式失败 |
| `BUG-2026-09-02-001` | 盘点取全局 `Material.stock` 当单仓账面 | 读取口径错 | 已修：改 `get_warehouse_stock_quantities` |
| `BUG-2026-09-03-001/002/004` | 同根因在 Excel 导入 / mobile / Android 三处复发 | 消费点多、无收口 | 已修，靠 R6 人工排查 |
| `BUG-2026-09-10-001` | 反提交+删除草稿后台账仍显示已删单据 | 流水清理遗漏 | 已修 |
| P2-9 在途口径分裂 | 同一物料在途量三处三个值：采购待办完全不截断（超收负数进汇总）、补货候选/缺料分析聚合后截断（超收抵消他行）、供应商履约行级截断 | 消费点各自内联 `sum(quantity − received_quantity)`、无收口 | 已修：统一入口 `get_purchase_in_transit[_by_material]`（行级 max(0)），6 处消费点接线 + 数值 diff 验证 + 防再膨胀静态测试 |

> **R6 机械化的意义**：以上"同根因多消费点"的排查此前完全依赖人记住去查。
> §5 的 A11 规则把"读取口径"从"靠人记住"变成"工具不让写"。

---

## 5. 强制约束（A11）

新增 lint 规则 **A11：业务代码禁止裸用 `material.stock` 做业务判断**。

- **允许**：展示用途（列表、报表、AI 分析里注明"全局合计"的只读展示）。
- **禁止**：**校验**用途（`if material.stock < qty`、`is_stock_sufficient(material.stock, ...)`、
  `stock = normalize_stock_quantity(material.stock or 0)` 后用于比较/拦截）。
- **豁免**：同 `# stock-truth:reason=<说明>` 注释（行内或上一行）。
- **强制范围**：仅对 **git staged 新增行**生效（同 A8/A9/A10），
  存量 36 处已登记白名单，不一次性报错。

**新代码写库存校验的标准姿势**：

```python
from app import get_warehouse_stock_quantities

wh_stock = get_warehouse_stock_quantities(warehouse)      # 仓库级，绝不回退全局
available = wh_stock.get(material.id, 0.0)
if not is_stock_sufficient(available, quantity):
    return api_error(f'物料 {material.code} 在 {warehouse.name} 库存不足：需 {quantity:g}，可用 {available:g}')
```

---

## 6. 改动库存相关代码的自检清单

改动涉及库存数量、出入库单据、报表聚合时，逐条勾选（与 AGENTS.md R2 配套）：

- [ ] **写入**：总账、库位账、流水 —— **三层是否都在同一事务内维护**？
- [ ] **方向**：是否沿着 ③→②→① 派生？有没有从全局倒推仓库级？
- [ ] **多仓隔离**：两个及以上仓库之间是否互不串仓（汇总 = 各仓库之和）？
- [ ] **历史脏数据**：`warehouse_id IS NULL` 的历史行是否会导致"查不出来/库存不足"误判？
- [ ] **汇总 = 明细**：报表合计是否等于明细行全集之和？是否被 `REPORT_ROW_LIMIT`(50000) 静默截断？
- [ ] **失败可见**：库位为空、记录不存在等边界是否**显式失败**而非静默返回成功？
- [ ] **归属不猜**：新增的回填/推断逻辑是否会在无法唯一确定时**保留 NULL**？
- [ ] **单仓短路**：本次改动是否会使 `Warehouse.query.count() == 1` 分支被跳过（新增仓库）？
- [ ] **展示口径**：给用户看的"库存"数字是哪个口径？是否与后端校验口径**一致**？

---

## 7. 一句话总结

> **流水（③）是唯一的事实来源；库位账（②）是仓库级真相；总账（①）是全局合计。**
> **三者必须始终满足 ① = Σ② = Σ③，且只能沿 ③→②→① 方向派生。**
> **任何一层单独变动、任何读取口径不一致、任何无法归属的行被强行猜测——都是账实分裂的起点。**
>
> 遇到不确定的归属：**保留 NULL，让人看见，而不是猜一个看起来对的。**
