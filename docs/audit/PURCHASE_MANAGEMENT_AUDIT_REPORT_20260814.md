# WMS 采购管理模块专项审计报告

## 0. 审计元信息

| 项目 | 内容 |
| --- | --- |
| 审计日期 | 2026-08-14 |
| 审计范围 | 供应商、采购申请、采购订单、采购入库，以及库存、仓库、来源单据和权限联动 |
| 审计基准提交 | `9066fc2303e7225be79feb744a1f59768cac90fb`（`docs: 登记采购入库自动下推领料功能`） |
| 审计分支 | `main` |
| 工作区状态 | 审计开始与报告编写前均无未提交改动 |
| 审计方式 | 源码与模型审查、路由权限审查、状态机和引用完整性审查、静态规则检查、隔离数据库回归测试、专项验证脚本 |
| 业务边界 | 未修改业务代码、数据库数据、账户密码、AI 权限或任何采购/入库单据 |

本报告以仓库根目录的 `AGENTS.md`、`DEVELOPMENT_RULES.md`、`WMS_BUG_BASELINE.md`、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 和 `AI_PERMISSION_MATRIX.md` 为审计依据。采购入库单的采购订单关联遵从“可选来源”规则：手工新增、编辑、保存和完成采购入库不应被采购订单关联强制阻断；但已关联来源时，系统必须保留来源、数量和执行进度追溯。

---

## 1. 执行摘要

采购模块的核心单据流已经具备较完整的基础闭环：采购申请可审批和下推采购订单，采购订单可下推采购入库草稿，采购入库完成与反提交会同步库存，已完成入库单禁止直接删除；单张入库完成、反提交和删除路径也使用写锁或原子库存操作控制并发风险。

本次专项审计确认 **3 项真实缺陷**：

| 级别 | ID | 问题 | 主要影响 | 状态 |
| --- | --- | --- | --- | --- |
| P1 | PUR-AUDIT-001 | 多采购订单选单生成采购入库时，仓库校验返回值被错误使用，合法请求始终被拒绝 | 多订单选单入库功能不可用 | 待修复 |
| P1 | PUR-AUDIT-002 | 多来源入库单未被采购订单删除检查覆盖 | 可删除仍被入库明细引用的采购订单，破坏来源追溯与执行进度 | 待修复 |
| P2 | PUR-AUDIT-003 | 入库完成与批量完成未在最终写入前重新检查仓库 active 状态 | 草稿建立后仓库被停用时仍可完成入库 | 待修复 |

未发现以下 P0 级问题：未经登录的采购写操作、采购入库完成后直接删除、采购入库强制关联采购订单、明显 SQL 注入、裸非 GET `fetch`、库存完成/反提交重复执行的已知并发缺陷、AI 自动审核或自动完成采购入库。

建议在修复前暂时避免使用“多采购订单选单生成采购入库”功能，并由采购人员在删除采购订单前人工确认是否存在任何来源入库明细。

---

## 2. 审计范围与模块地图

### 2.1 业务对象

| 业务对象 | 模型 | 关键关联 | 关键状态 |
| --- | --- | --- | --- |
| 供应商 | `Supplier` | 被采购申请、采购订单、采购入库引用 | 主数据 |
| 采购申请 | `PurchaseRequest` / `PurchaseRequestItem` | 申请明细可关联采购订单明细 | `pending`、`approved`、`rejected`、`completed` |
| 采购订单 | `PurchaseOrder` / `PurchaseOrderItem` | 表头可关联采购申请；明细通过来源外键关联采购入库明细 | `pending`、`partial`、`completed`、`closed` |
| 采购入库 | `InOrder` / `InOrderItem` | 表头可关联单一采购订单；明细可关联采购订单明细 | `pending`、`completed` |
| 库存流水 | `StockTransaction` | 由入库完成/反提交写入，以入库单为引用 | 入库、反提交等类型 |
| 库位库存 | `LocationInventory` | 开启库位管理时按仓库和库位同步 | 由入库完成/反提交对称更新 |

### 2.2 代码边界

| 领域 | 主要文件 | 职责 |
| --- | --- | --- |
| 供应商 | `app/routes/supplier.py` | 供应商主数据的增删改查和导入导出 |
| 采购申请 | `app/routes/purchase_request.py` | 申请保存、审批、驳回、反审、完成、删除、下推采购订单 |
| 采购订单 | `app/routes/purchase_order.py` | 订单保存、导入导出、复制、关闭、重开、删除、下推或选单生成入库 |
| 采购入库 | `app/routes/in_order.py` | 入库保存、明细维护、完成、反提交、删除、批量状态操作、库存联动 |
| 数据模型与通用规则 | `app/app.py` | SQLAlchemy 模型、采购执行量计算、采购订单状态更新、仓库解析与库存原子操作 |
| 前端页面 | `app/templates/purchase_*.html`、`app/templates/in_order*.html` | 列表、编辑、详情、来源单据联查与业务操作 |
| AI 采购辅助 | `app/ai/tools/purchase.py`、`app/ai/agents/purchase_followup.py` | 草稿创建、只读检查、采购跟进；不自动完成单据 |

### 2.3 主流程与数据责任

```text
供应商主数据
  -> 采购申请（可审批）
  -> 采购订单（可由申请部分下推，也可手工创建）
  -> 采购入库草稿（可由订单下推、选单生成，也可手工新增）
  -> 人工完成入库
  -> Material.stock + StockTransaction + LocationInventory（启用库位时）

采购订单明细 PurchaseOrderItem
  <- InOrderItem.source_purchase_order_item_id
  <- received_quantity 预留/执行进度
  <- update_purchase_order_status() 根据已完成入库量计算订单状态
```

采购入库的来源字段分两层：

- `InOrder.source_purchase_order_id`：单一来源订单时记录表头级来源。
- `InOrderItem.source_purchase_order_item_id`：每一条采购入库明细的实际来源，支持多采购订单选单生成同一张采购入库单。

后者是采购执行追溯和删除保护的权威数据来源，不能仅依赖表头级来源字段。

---

## 3. 审计方法

1. 阅读项目规则和已登记的采购、入库、仓库库存相关缺陷，确认采购订单仅可选关联、已完成入库单先反提交后删除、仓库始终必填等硬约束。
2. 追踪 `PurchaseRequest`、`PurchaseOrder`、`InOrder` 和明细模型的外键、关系、状态和值回写路径。
3. 阅读采购申请下推、采购订单下推、选单下推、入库保存、完成、反提交、删除、批量完成和批量删除路由。
4. 对照单张与批量操作，检查权限、状态机、写锁、库存原子性、仓库 active 校验和来源数据释放逻辑。
5. 执行仓库规则检查及采购/入库相关回归测试；对环境配置导致的测试失败进行隔离重跑并区分业务失败与测试基建问题。
6. 检查现有回归测试是否覆盖各发现的入口和重要边界。

审计结论仅将能由源码路径、数据流或运行输出直接佐证的问题列为真实缺陷；测试环境和工具认证限制单独列在第 7 节。

---

## 4. 详细发现

### 4.1 [P1][PUR-AUDIT-001] 选单生成采购入库时合法仓库被错误拒绝

**受影响入口**：`POST /purchase_order/create_in_order_from_selection`

**证据位置**：

- `app/routes/purchase_order.py:626-633`
- `app/app.py:3239-3245`

**当前逻辑**：

```python
wh_err = assert_warehouse_active(warehouse)
if wh_err:
    return api_error(wh_err)
```

`assert_warehouse_active()` 返回 `(ok, message)` 二元组，而不是错误字符串。Python 中任何非空元组均为真，包括成功结果 `(True, '')`。因此只要请求已提供仓库，`if wh_err` 恒成立，接口会错误返回失败，选单生成采购入库草稿无法执行。

**业务影响**：

- 采购人员无法将多个同供应商采购订单的部分明细合并为一张采购入库草稿。
- 绕过该功能后需要拆分为多张单据或手工新建，增加录入成本和来源追溯错误的概率。
- 功能失败发生在后端，前端无法通过额外校验规避。

**复现条件**：

1. 创建两个状态为 `pending` 或 `partial`、供应商相同的采购订单。
2. 选择两个订单中的有效明细，传入启用仓库名称。
3. 调用选单下推接口。
4. 预期：返回新的采购入库草稿。
5. 实际：即使仓库存在且状态为 `active`，仍在仓库校验处被拒绝。

**根因**：调用方未按 `assert_warehouse_active()` 的返回契约解构结果。相同函数在采购入库新增和编辑入口已经采用正确模式：`ok, wh_msg = ...` 后检查 `not ok`。

**修复建议**：

```python
ok, wh_msg = assert_warehouse_active(warehouse, allow_empty=False)
if not ok:
    return api_error(wh_msg)
```

同时应在函数中保留当前默认仓库回退逻辑，并统一使用 `allow_empty=False` 明确表达采购入库仓库必填。

**必须新增的回归测试**：

- 合法启用仓库、同供应商的多订单选单，可成功创建一张 `pending` 采购入库草稿。
- 不存在仓库和停用仓库均返回业务错误。
- 不同供应商明细仍被拒绝。
- 新草稿表头的 `source_purchase_order_id` 为 `None`，各明细的 `source_purchase_order_item_id` 正确保留。

---

### 4.2 [P1][PUR-AUDIT-002] 多来源入库明细引用未阻止采购订单删除

**受影响入口**：

- `POST /purchase_order/<id>/delete`
- `POST /purchase_order/batch_delete`

**证据位置**：

- 多来源选单创建逻辑：`app/routes/purchase_order.py:660-712`
- 采购订单单张删除检查：`app/routes/purchase_order.py:895-905`
- 采购订单批量删除检查：`app/routes/purchase_order.py:927-948`
- 明细级来源外键：`app/app.py:4362-4380`

**当前逻辑**：

多订单选单时，系统有意将 `InOrder.source_purchase_order_id` 设为 `None`，并在每一个 `InOrderItem.source_purchase_order_item_id` 上保存真实订单明细来源。这是支持多来源单据的正确建模方式。

但采购订单删除前只检查：

```python
InOrder.query.filter_by(source_purchase_order_id=order.id).first()
```

该检查无法发现表头来源为空、但入库明细仍指向该订单明细的多来源入库单。

**业务影响**：

- 可删除尚被采购入库草稿或已完成入库明细引用的采购订单。
- 如果生产数据库未严格启用外键约束，可能遗留失效的 `source_purchase_order_item_id`，之后在入库删除、复制、反提交或执行进度计算中无法可靠回溯来源。
- 如果数据库启用外键约束，删除可能直接抛数据库异常并返回泛化的“删除失败”，而非向业务人员解释应先处理下游入库单。
- 已下推数量 `received_quantity` 与订单状态可能无法在后续删除草稿时正确回退，破坏采购申请、采购订单与入库执行进度的一致性。

**复现条件**：

1. 创建两个同供应商、均为 `pending` 的采购订单，各包含至少一条明细。
2. 通过多订单选单接口生成一张采购入库草稿；该草稿的 `source_purchase_order_id` 为 `None`，但两个入库明细分别指向两张采购订单的明细。
3. 尝试删除其中任一来源采购订单。
4. 预期：返回“已有下游入库单，不能删除”，并保持订单及明细完整。
5. 实际：表头来源检查无法匹配，删除会继续执行或在数据库层失败。

**根因**：来源追溯模型已迁移至行级外键，但删除保护仍仅依赖单来源表头字段，造成引用完整性规则与数据模型不一致。

**修复建议**：

抽取采购订单“是否存在下游入库引用”的统一查询，单张和批量删除共同调用。查询必须同时覆盖：

```text
InOrder.source_purchase_order_id == purchase_order.id
OR
InOrderItem.source_purchase_order_item_id
  -> PurchaseOrderItem.purchase_order_id == purchase_order.id
```

建议用 `exists()` 或 `join` 完成数据库级判断，避免在循环内加载全部单据。若存在任何已删除/草稿/完成状态的来源入库单，均禁止删除采购订单，因为其均承载来源追溯或库存历史。

**必须新增的回归测试**：

- 单一来源下推入库时，删除采购订单继续被拒绝。
- 多来源选单入库草稿存在时，两个来源订单都被拒绝删除。
- 多来源入库已完成时，两个来源订单仍被拒绝删除。
- 删除入库草稿后，其来源订单的删除保护解除，并同步释放 `received_quantity` 预留。
- 批量删除返回明确的被阻断订单清单，不允许部分绕过。

---

### 4.3 [P2][PUR-AUDIT-003] 入库完成入口未复核仓库启用状态

**受影响入口**：

- `POST /in_order/<id>/complete`
- `POST /in_order/batch_complete`

**证据位置**：

- 新建草稿仓库校验：`app/routes/in_order.py:744-750`
- 编辑草稿仓库校验：`app/routes/in_order.py:493-496`
- 单张完成逻辑：`app/routes/in_order.py:1337-1419`
- 批量完成逻辑：`app/routes/in_order.py:2047-2112`
- 仓库 active 规则：`app/app.py:3221-3245`

**当前逻辑**：

新增和编辑采购入库草稿时，系统调用 `assert_warehouse_active(..., allow_empty=False)`，能够拒绝不存在或停用仓库。但单张完成仅检查：

- 单据仓库是否为空；为空时是否能回退到默认仓库。
- 启用库位管理时库位是否为空。

批量完成的检查也只覆盖默认仓库回填和非空校验。两个完成入口在加写锁后的最终库存写入之前，均未重新调用仓库 active 校验。

**业务影响**：

- 草稿保存后，若管理员停用该仓库，采购人员仍可完成该入库单。
- 这会把新的库存、库存流水或库位库存归属到一个已停用仓库，使运营语义与仓库主数据状态不一致。
- 单张和批量入口存在相同缺陷，无法由前端规避。

**复现条件**：

1. 以启用仓库保存一张采购入库草稿。
2. 将该仓库状态改为 `inactive`。
3. 调用单张完成或批量完成。
4. 预期：返回仓库已停用的业务错误，库存不变化。
5. 实际：只要仓库名称非空且库位条件满足，入库仍可能完成并写入库存。

**根因**：仓库规则仅在草稿录入阶段校验，未在产生库存副作用的最终状态转换阶段重验；与“所有出入库新增/编辑/完成/批量完成路由必须校验仓库”的规则不一致。

**修复建议**：

在单张完成和批量完成中，均应在 `_acquire_order_write_lock()` 成功之后、开始调用 `add_stock()` 之前执行：

```python
ok, wh_msg = assert_warehouse_active(order.warehouse, allow_empty=False)
if not ok:
    db.session.rollback()
    return api_error(wh_msg)
```

批量完成应将该单据加入 `skipped`，并继续处理其他单据；不得让一张停用仓库单据回滚或中断整个批次。

**必须新增的回归测试**：

- 草稿保存后仓库被停用，单张完成返回 400，库存、库存流水和单据状态不变。
- 同一条件下批量完成跳过该单据，其他合法单据仍可完成。
- 不存在仓库名称也被拒绝。
- 启用仓库的正常完成路径继续通过。

---

## 5. 已确认符合预期的控制项

### 5.1 采购入库可不关联采购订单

`AGENTS.md` 明确要求采购订单是可选来源。`validate_purchase_in_order_source()` 在未开启“强制来源”系统设置时直接通过，手工新增采购入库单可保存和完成；关联采购订单时才由来源明细维护执行进度。这与业务规则一致。

### 5.2 已完成采购入库单禁止直接删除

`delete_in_order()` 在删除前要求单据状态为 `pending`，已完成单据会被明确拒绝并提示先反提交。批量删除同样拒绝非草稿单据。反提交会执行库存回退，符合库存生命周期要求。

### 5.3 单据完成与反提交有并发控制

单张完成、反提交、已完成明细编辑与批量操作均使用 `_acquire_order_write_lock()` 或原子库存更新，避免相同单据在并发请求下重复完成或重复扣回库存。专项隔离回归覆盖该场景并通过。

### 5.4 采购订单执行状态按已完成入库量计算

`update_purchase_order_status()` 从状态为 `completed` 的 `InOrderItem` 聚合数量，而不是仅信任草稿预留量；订单状态会据此成为 `pending`、`partial` 或 `completed`。这使反提交后的订单状态可正确回退。

### 5.5 权限和高风险边界

采购申请审批、采购订单删除、采购订单下推、采购入库完成/反提交/删除均有 `@login_required` 和对应业务角色限制。AI 采购工具的职责保持在草稿创建、检查和跟进，审计范围内未发现 AI 自动完成、删除、审核或绕过人工确认的入口。

---

## 6. 验证结果

### 6.1 已通过的检查

| 验证项 | 结果 | 说明 |
| --- | --- | --- |
| `bash .githooks/install-hooks.sh` | 通过 | 启用仓库提交前规则 |
| `python scripts/check_hooks_installed.py` | 通过 | 提交钩子已安装 |
| `python scripts/lint_wms_rules.py` | 通过 | A1-A10 规则无违规 |
| `python scripts/lint_no_raw_post_fetch.py` | 通过 | 业务 JS 未发现裸非 GET `fetch` |
| 采购/入库拆分及既有回归集合 | 30 passed | 覆盖采购申请、采购订单、供应商、入库已知缺陷和主要契约 |
| `tests/verify_bug_2026_08_04_003_update_completed_in_order_lock.py` | 通过 | 已完成入库单编辑写锁回归 |
| `tests/verify_in_order_complete_perf.py` | 通过 | 5/20 明细完成正确性、查询斜率和性能回归 |
| `python scripts/verify_in_order_state_machine.py` | 通过 | 完成、反提交、删除边界与库存回退 |
| `python scripts/verify_inbound_push.py` | 通过 | 下游单据追溯、数量限制、幂等、权限和库存生命周期 |

隔离回归使用：

```bash
env DATABASE_URL='sqlite:///:memory:' \
    WMS_DATABASE_URI='sqlite:///:memory:' \
    WMS_SKIP_AUTO_UPDATE=1 \
    WMS_BOOTSTRAP_PASSWORD=admin \
    python -m pytest -q \
      tests/verify_bug_2026_08_04_003_update_completed_in_order_lock.py \
      tests/verify_in_order_complete_perf.py
```

结果为 `7 passed`。

### 6.2 未能作为产品失败计入的验证限制

| 项目 | 结果 | 原因 | 审计处理 |
| --- | --- | --- | --- |
| `tests/verify_bug_2026_08_02_021_in_order_contract.py` | 4 passed，1 failed | 测试在同一 Python 进程删除并重复导入 `app`，导致 SQLAlchemy 报 `Table 'user' is already defined` | 属测试隔离问题，未作为采购业务缺陷计数 |
| `scripts/e2e_business_flow.py` | 未完成 | 依赖 `127.0.0.1:8080` 的运行中服务；审计环境没有启动该服务 | 未将其结果作为业务通过或失败依据 |
| CodeRabbit 自动审计 | 未执行 | CLI 已安装，但代理身份未认证 | 本报告所有问题均来自仓库内可验证证据，不宣称为 CodeRabbit 结论 |

---

## 7. 修复优先级与实施顺序

1. **PUR-AUDIT-001**：修正选单下推仓库校验的二元组解构。该缺陷直接导致功能不可用，修改局部、回归清晰，应优先处理。
2. **PUR-AUDIT-002**：统一采购订单删除前的下游入库引用检查。该缺陷影响来源追溯和采购执行量完整性，需同时修改单张和批量删除入口，并补充多来源入库回归。
3. **PUR-AUDIT-003**：在单张和批量完成的写锁后加入仓库 active 复核，确保主数据状态变化不会被旧草稿绕过。
4. **测试基建修正**：单独修复重复导入 `app` 的测试隔离问题，保证采购契约测试可稳定执行；该项不应与三个业务缺陷混在同一原子提交中。

每项业务修复均应：

- 在 `WMS_BUG_BASELINE.md` 登记唯一 BUG ID；
- 在 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 建立或关联子任务；
- 新增对应 pytest 回归测试；
- 运行 A1-A10、裸 fetch、专项回归和相关状态机验证；
- 按项目规则单独 commit 并推送 `main`，确认本地和 `origin/main` 为同一提交后再更新台账。

---

## 8. 建议的回归验收矩阵

| 场景 | 入口 | 预期 |
| --- | --- | --- |
| 两张同供应商订单选单下推 | `/purchase_order/create_in_order_from_selection` | 生成一张采购入库草稿，明细来源完整 |
| 停用仓库选单下推 | 同上 | 返回仓库已停用，不生成草稿 |
| 多来源草稿存在时删任一来源订单 | `/purchase_order/<id>/delete` | 返回下游引用错误，数据不变 |
| 多来源已完成入库存在时批量删订单 | `/purchase_order/batch_delete` | 将所有受引用订单列为阻断项 |
| 删除多来源草稿后删来源订单 | 入库删除后采购订单删除 | 草稿释放来源预留后，订单可按状态规则删除 |
| 保存草稿后停用仓库再完成 | `/in_order/<id>/complete` | 拒绝完成，不增加库存和流水 |
| 批量完成包含停用仓库草稿 | `/in_order/batch_complete` | 跳过停用仓草稿，其余合法草稿完成 |
| 手工采购入库未关联订单 | `/in_order/add`、`/in_order/<id>/complete` | 在规则允许时可保存并由人工完成 |
| 已完成采购入库直接删除 | `/in_order/<id>/delete` | 拒绝，要求先反提交 |
| 完成后反提交 | `/in_order/<id>/revert` | 库存和库位库存对称回退，采购订单执行状态重算 |

---

## 9. 结论

采购模块的主流程和既有入库状态机具备可用基础，尤其在已完成入库删除边界、库存回退、并发写锁和采购订单执行状态计算方面已有实质保护。

但采购订单选单入库和多来源追溯仍存在关键缺口：一项使选单功能不可用，另一项使多来源单据的引用完整性无法被删除保护覆盖。仓库状态复核缺失则会允许旧草稿绕过已停用仓库限制。三个问题均可局部修复，但必须配套端到端数据关系回归，避免在修复单个入口时遗漏批量入口或行级来源关系。

本报告为只读审计产物。报告中所有“待修复”项在修复完成、测试通过、提交推送并更新 BUG 基线与 AI 台账前，不应视为已关闭。
