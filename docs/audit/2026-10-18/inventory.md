# WMS 全面审计 · 库存口径与多仓一致性（inventory）

- 审计人：teammate `inventory`
- 审计日期：2026-10-18
- 代码基线：`0f8442b31e27845cac2f627424732624b0dba2a1`（版本 2026.09.1）
- 审计方式：**纯静态分析**。本会话无法执行任何外部进程（pwsh 0xC0000142 / python 与 git EPERM），因此所有结论均为读代码得出；凡需真实运行才能确认的均标注「[需运行验证]」。
- 明确不报（AGENTS.md §〇 已拍板接受，见共用简报 §3）：①入/出库单无作废态；②入/出库主链路无审核岗（仅 pending→completed 一跳）。库位管理当前关闭（默认 `'0'`，`app/app.py:4261-4262`），故「库位未填」不判缺陷；但**仓库必填**按硬性规则审查。

---

## 1. 审计范围与覆盖度

### 1.1 权威口径依据
- `INVENTORY_TRUTH.md` **全文 522 行精读**：三层账定义（①`material.stock` 全局 / ②`location_inventory` 仓库×库位 / ③`stock_transaction` append-only 流水）、派生方向（只允许 ③→②→①）、三个业务入口（`apply_stock_delta` / `apply_transfer_pair` / `apply_opening_balance`）、单仓短路与「全不可归属回退」两个兜底（§3.3）、期初多单据汇总口径（§2.1.2）。

### 1.2 全仓机械化扫描（覆盖 100% 的 `app/` Python 代码）
以脚本对 `app/` 下 **163 个 .py（105,911 行）** 做全量正则扫描，命中即逐条人工判定：
- `.stock` 出现 186 行（含注释/文档字符串；排除注释后约 120 行），逐条判定见 **附录 B**；
- `get_warehouse_stock_quantities(` 调用 70 处（15 个文件）；
- 三账入口 `apply_stock_delta/apply_transfer_pair/apply_opening_balance(` 调用 36 处（11 个文件）；
- `StockTransaction(` 构造 5 处（4 处在 `app/app.py` 原语内、1 处在文档字符串中）；
- 库存写原语 `add_stock` / `deduct_stock_atomic` / `add_stock_transaction` / `update_location_inventory` / `add_location_inventory_atomic` / `deduct_location_inventory_atomic` / `_apply_opening_stock_balance` / `_reverse_opening_stock_line` 的全部调用点；
- `BEGIN IMMEDIATE` / `with_for_update` / `busy_timeout` / `_acquire_order_write_lock` 的锁覆盖点；
- 各单据 delete/revert 路由中的 `StockTransaction` 清理点（19 处，逐一核对「净额必为 0」）。

### 1.3 全文精读（小文件）
`app/services/warehouse_stock_service.py`(396)、`app/services/warehouse_scope.py`(59)、`app/services/stock_unit_guard.py`(16)、`app/services/document_return_guard.py`(44)、`app/models/inventory.py`(84)、`app/routes/report.py`(520)、`app/routes/stock_query.py`(251)、`app/utils.py` 库存段(1-280)。

### 1.4 定点精读（大文件关键段，约 5,000 行）
- `app/app.py`：库存原语 4724-5116、`get_warehouse_stock_quantities`/`_material_stock_unattributed` 5330-5650、告警与口径 7180-7550、旧委外 API 7600-7900、初始化/期初 8100-8500、物料合并 8975-9080/9085-9260、AI 单据草稿 11200-11920、物料 API 25890-26090、表单序列化 26325-26365/26700-26760、扫码盘点辅助 26757-27100/27099-27160/27470-27560、仓库归属过滤 29202-29269/29615、回填 29400-29570、AI 分析 31930-32070/34820-34880、销售 AI 检查 35640-35725、`_require_report_warehouse` 35802-35868、`_wh_stock_guards` 35874-35939。
- routes：`in_order.py`(1837-2044、2044-2340、2340-2545、2711-3029)、`out_order.py`(36-59、1086-1390)、`transfer.py`(101-283、448-735)、`adjustment.py`(224-660)、`check.py`(257-966、1015-1155)、`opening_stock.py`(92-520、720-1030)、`batch_import.py`(62-300、760-1013)、`material.py`(300-420、462-506、660-740、840-935、960-1118)、`mobile.py`(380-570、950-1090)、`native_api.py`(1330-1480)、`inventory_alert.py`(55-380)、`subcontract.py`(655-725、1046-1152)、`requisition.py`(571-708)、`after_sale_out.py`(160-205、370-525)、`export.py`(413-440)、`system_settings.py`(174-386)。
- `app/ai/tools/inventory.py`(60-180、270-312)、`app/ai/patrol_scheduler.py`(55-195)、`app/ai/ops/sales_followup_workbench.py`(1-270)、`app/static/js/app.js`(1576-1630、1895-1930)、`app/models/documents.py`（类清单与 unit_id 列）。

### 1.5 未覆盖 / 限制（诚实声明）
- **未运行任何测试/脚本**（环境不允许），"运行时才成立"的均标 [需运行验证]。
- 未逐行精读：`sales.py`(2152 行，仅核对 get_committed_quantities 关键点)、`purchase_order.py`/`purchase_request.py` 全链路、`android-native-wms/` Kotlin 客户端、132 个模板页面的前端 `required` 属性（后端门禁是本报告主依据）。
- 未覆盖跨域：权限/CSRF/注入/前端 JS 规则、性能基准测试（由其他 teammate 负责）。
- 已知结论可能受「生产库实际数据形态」影响（如历史 NULL 归属流水是否存在），此类条目一律标「高度可疑」。

---

## 2. 结论摘要

| 级别 | 数量 |
|---|---|
| **P0 致命** | **0** |
| **P1 严重** | **3** |
| **P2 一般** | **8** |
| **P3 轻微** | **6** |

**总评**：三账收敛（P2-3/P1-7）与多仓判据（A11）的主体工程质量很高——主链路出入库、调拨、盘点、调整、期初均已收敛到 `warehouse_stock_service` 三个入口，反提交/删除基本对称，锁覆盖较完整。**本次未发现新的 P0**。剩余风险集中在三类「收口之外的旁路」：①**AI 助手 5 条草稿创建路径**（2026-09 前的老实现）未随仓库必填与多仓口径改造同步，其中 AI 盘点草稿**无仓库且无 UI 路径可补**，是功能性死路；②**「快照 + 逐行校验」型反提交校验**与 `_wh_stock_guards` 的下推豁免条件叠加时，多行同物料可能把单仓扣成负账；③**非主链路**（Excel 领料单导入、旧打印报表、预警仓库视图、业务数据初始化）与主链路口径分叉，属 R6「同根因多消费点」的典型存量。

---

## 3. 详细 findings

### [P1] AI 助手生成的 5 类库存单据草稿绕过「仓库必填」，AI 盘点草稿无仓库且无任何路径可补
- 位置：
  - `app/app.py:11391-11399`（AI 领料单草稿：`OutOrder(...)` 无 warehouse）
  - `app/app.py:11462-11470`（AI 产品入库草稿：`InOrder(...)` 无 warehouse）
  - `app/app.py:11570-11578`（AI 调拨草稿：仓库名被写入 `from_location/to_location`，`from_warehouse/to_warehouse` 均未设置）
  - `app/app.py:11654-11671`（AI 盘点草稿：`InventoryCheck(...)` 无 warehouse；`11664` 的账面 `sys_stock` 取全局 `material.stock`）
  - `app/app.py:11747-11768`（AI 调整草稿：`AdjustmentOrder(...)` 无 warehouse；`11764` 把 `material.spec` 当 `location` 写入）
- 现象：AI 助手「生成盘点单/调整单/调拨单/入库单/领料单草稿」时一律不写仓库（调拨还把仓库名写进库位字段，调整单把物料规格写进库位字段），生成的草稿在完成环节被仓库必填门禁拦下；其中**盘点草稿没有任何 UI 路径可以补仓库**，成为永久不可完成、不可编辑的死单。
- 证据：
  1. 创建端（无 warehouse）：`app/app.py:11654-11659`
     ```python
     order = InventoryCheck(
         check_no=generate_order_no('CK'),
         date=date.today(),
         remark=(message or '')[:200],
         status='pending',
         operator_id=current_user.id,
     )   # ← 无 warehouse=
     ```
     且明细账面用全局总账：`app/app.py:11664  sys_stock = normalize_stock_quantity(material.stock or 0)`
  2. 完成端硬门禁：`app/routes/check.py:532-533`
     ```python
     if not check.warehouse:
         return api_error('盘点单未指定仓库，无法完成')
     ```
  3. 编辑端也补不了仓库：`app/routes/check.py:329-331`（已有明细且仓库不一致 → 拒绝，「盘点明细已冻结账面，不能更换仓库」）；`app/routes/check.py:690-692`（`add_check_item`：`if check.items or check.frozen_at is not None: return api_error('历史盘点单已有冻结明细但缺少仓库…')`）。全仓仅 `check.py:335` 与 `check.py:712` 两处会给 `check.warehouse` 赋值，均被上述门禁挡住。
  4. 其余四类同根因：`adjustment.py:427-428`（`if not adjustment.warehouse: return api_error('调整单未指定仓库，无法完成')`）、`transfer.py:469-474`（`调拨单缺少调出/调入仓库，无法完成`）、`in_order.py:1905-1911` / `out_order.py:1144-1150`（完成时静默落默认仓，无默认仓则拒绝）。
  5. 调拨/调整有「编辑页可补」的降级路径：`transfer.py:168-172`（save_table 写 from/to_warehouse）、`adjustment.py:338`（save_table 写 warehouse），但 AI 草稿里的 `from_location=仓库名`、`location=material.spec` 会作为库位数据残留（开启库位管理后直接错账）。
- 影响：多仓库生产环境（AGENTS.md §〇：4 仓）下，AI 助手产出的库存单据草稿大面积不可用；AI 盘点草稿 100% 不可完成（用户只能先删光明细再存仓库再重建，实操上等于功能失效）。盘点账面取全局总账还会把盘盈/盘亏算错（多仓串仓，A11/R2）。
- 根因：AI 草稿创建是 2026-09 多仓/仓库必填改造前的旁路实现，未随主链路收敛（R6：同类消费点遗漏 5 处；违反 AGENTS.md §二「出入库表单仓库必填」与 INVENTORY_TRUTH §2.2「业务校验读仓库级」）。
- 建议：抽一个 `_ai_draft_warehouse(payload/message)`：优先从用户消息解析仓库名→按 `validate_inventory_warehouse` 校验→缺省取默认仓→两处皆无则拒绝生成草稿；五处创建点统一补 `warehouse`/`from_warehouse,to_warehouse` 且 `location` 不再接收 `spec`。盘点草稿的 `system_stock` 必须改为 `get_warehouse_stock_quantities(wh).get(mid, 0)`（A11）。补 A9 回归测试（当前全仓无任何测试引用 `_ai_create_check_draft`）。
- 确认程度：**已确认**（创建端与完成端代码可闭环证明；其中「盘点草稿无路径可补」已逐一核对其余写 `check.warehouse` 的路由）
- 关联规则：A11 / R2 / R6 / AGENTS.md §二

### [P1] 反提交/售后出库/旧委外发料：多行同物料用「单次快照逐行比较」，仓库级原子护栏一旦不下推即可把单仓扣成负账
- 位置：
  - `app/routes/in_order.py:2450-2517`（`revert_in_order`：`warehouse_stock = get_warehouse_stock_quantities(wh_obj)` 只在 `2456` 取一次，`2457-2501` 逐行比较，`2504-2517` 才逐行扣减）
  - `app/routes/in_order.py:2953-3015`（`batch_revert_in_order`：同上，快照在 `2959`）
  - `app/routes/after_sale_out.py:423-460`（售后出库完成：快照在 `427`，校验 `428-442`，扣减 `444-460`）
  - `app/app.py:7656-7732`（旧委外发料 `api_subcontract_quick_issue`：快照在 `7661`，校验 `7664-7688`，扣减 `7725`）
- 现象：同一物料在同一张单中有多行时，每行都拿**同一份扣减前的仓库库存快照**做「够不够」判断，合计需求可以超过仓库实际库存；扣减侧的原子护栏 `_wh_stock_guards` 在遇到「历史脏数据」条件时**主动不下推**（返回 `[]`），此时扣减只剩全局 `Material.stock >= qty` 条件，多行合计扣减会让某仓库账面变负。
- 证据：
  1. `app/app.py:35898-35923`（`_wh_stock_guards` 的下推豁免）：
     ```python
     if not warehouse or location_management_enabled() or allow_negative_stock():
         return []
     ...
     if Warehouse.query.count() == 1: return []            # 单仓：全局条件等价
     if _material_stock_unattributed(material_id): return []
     _src = ... StockTransaction.warehouse_id.is_(None) 且 location 空 且 reference_type/id 非空 ...
     if _src is not None: return []                        # 口径不等价 → 不下推
     ```
  2. `app/app.py:4792-4799`（下推缺失时只剩总账条件，且 `4770` 的 Python 仓库级前置校验在开启库位管理时整段跳过）：
     ```python
     condition = Material.id == material_id
     if not allow_negative_stock():
         condition = db.and_(condition, Material.stock >= qty, *_wh_stock_guards(...))
     ```
  3. 校验端只做「逐行 ≥ 单行量」：`app/routes/in_order.py:2461-2468`、`2964-2971`、`app/routes/after_sale_out.py:432-437`、`app/app.py:7675-7682`——均无「按物料合计需求」这一步（对比：`transfer.py:516-526` 的调拨完成校验**做了** `required` 按物料累加，是正确写法）。
- 影响：仓库级库存被扣成负数（① 与 Σ③ 仍对得上，但仓库分布错、且该仓后续出库/反提交全部被拒），典型触发示例：A 仓 10 件、B 仓 100 件，A 仓入库单两行 8+8 反提交——逐行都判「10 ≥ 8」通过；若该物料存在「空 location+带来源单据」的历史流水（B1 回填无法唯一归属的遗留行，`app.py:29458-29538` 明确保留 NULL），下推被关闭后两行都能扣成功，A 仓变 -6。是否已在生产触发取决于历史流水形态 → [需运行验证]。
- 根因：Python 侧预校验与 SQL 侧原子护栏是两套实现，预校验按行而不是按物料合计；护栏的下推豁免条件把「历史脏数据」当成了「不做仓库级校验」的理由（应为「保留 Python 仓库级校验」，而 Python 校验本身又没聚合）。R2「历史脏数据兼容」与「多仓隔离」两条要求在此处互相打掩护。
- 建议：把 4 处的校验统一改成「先按 `material_id` 聚合 `required`，再与快照比较」（照抄 `transfer.py:516-526`），或在循环内**逐行重取** `get_warehouse_stock_quantities`（照抄 `in_order.py:2134` F2.12 BUG-C 的修法）。更好的做法是把「仓库级扣减校验」彻底收口进 `apply_stock_delta`/入口层，禁止各路由自行预校验。
- 确认程度：**高度可疑**（代码路径已确认；需确认生产库是否存在令 `_wh_stock_guards` 返回 `[]` 的历史流水，或开启库位管理后复测）
- 关联规则：A11 / R2 / R6 / R4（并发与降级兜底）

### [P1] 业务数据初始化：先把 ① 总账全量归零再删流水，分表删除失败被静默吞掉 → 可能留下 ①=0 / ③≠0 且接口报成功
- 位置：`app/app.py:8121-8152`（`_revert_completed_to_pending` / `_zero_all_material_stock`）、`app/app.py:8154-8162`（`_bulk_delete_model` 吞异常）、`app/app.py:8193-8211`（编排顺序与 commit 点）、`app/routes/system_settings.py:260-308`（路由层只捕获整体异常）
- 现象：初始化流程顺序为「全部 completed 单据改 pending → `Material.query.update({Material.stock: 0})` 全表归零 ① → 提交 → 删业务表 → 删库存表」。库存表的删除是**逐表**执行且每张表失败都被 `_bulk_delete_model` 捕获后 `rollback`+返回 0、循环继续；最后一次提交后接口返回 success。若 `stock_transaction`（或 `location_inventory`）删除因锁/异常失败，则 ① 已全量归零而 ③ 仍在 → 三账恒等式永久分裂，且用户看到的是「初始化成功」。
- 证据：
  ```python
  # app/app.py:8146-8152
  def _zero_all_material_stock():
      try:
          return Material.query.update({Material.stock: 0}, synchronize_session=False)
      except Exception as exc:
          app.logger.warning('zero stock failed: %s', exc)
          return 0

  # app/app.py:8154-8162
  def _bulk_delete_model(model_cls):
      try:
          count = model_cls.query.delete(synchronize_session=False)
      except Exception as exc:
          app.logger.warning('delete %s failed: %s', model_cls.__name__, exc)
          db.session.rollback()      # ← 只回滚本表，调用方继续下一张表
          return 0
  ```
  ```python
  # app/app.py:8194-8211
  deleted['reverted_to_pending'] = _revert_completed_to_pending()
  deleted['zeroed_materials'] = _zero_all_material_stock()   # ① 归零
  ... db.session.commit()                                    # ①=0 落库
  for label, model_cls in INIT_INVENTORY_TABLES:             # ②③ 在这里删
      deleted['inventory'] += _bulk_delete_model(model_cls)  # 失败被吞
  db.session.commit()
  ```
- 影响：仓库级库存查询（关库位管理时按 ③ 聚合，`app.py:5396-5405`）仍显示历史库存，而所有出库/调整的扣减会被 ①=0 拒绝 → 「查询有货、操作全拒」，且三账判据 `scripts/verify_inventory_identity.py` 的 ①≠③ 会硬失败。属于管理员一键操作后长期潜伏的账实分裂。已有 admin 密码 + 确认短语双重门禁（`system_settings.py:224-233`），误触风险低，但失败可见性为零。
- 根因：批量维护流程以「先破坏后重建」顺序执行且逐表吞异常；库存表的删除无 savepoint/无整体事务、无结果校验（`deleted['inventory']` 与 `_init_business_data_preview_stats` 的预期数不比对）。`_zero_all_material_stock` 的注释「语义等价于逐张反提交」也不成立：期初建账、物料初始库存等并非「已完成单据」，直接归零属 INVENTORY_TRUTH §2「① 独立于②③变动」（无 `# stock-truth:reason=` 豁免）。
- 建议：删除顺序倒置（先删 ③/② 再归零 ①，或全部并入同一事务、任一表失败立即整体失败）；`_bulk_delete_model` 失败不得继续；执行后立即调用 `verify_inventory_identity` 同款断言并把结果写入响应/审计；为归零点补 `# stock-truth:reason=` 豁免说明。
- 确认程度：**已确认**（代码路径）；**触发需 DB 异常**，生产概率低 [需运行验证]
- 关联规则：INVENTORY_TRUTH §2 / §4.3 / A13（失败可见）/ R4

### [P2] 领料单 Excel 导入不解析仓库：模板无仓库列 → 全部草稿 warehouse=NULL，完成时静默落到默认仓（多仓下扣错仓）
- 位置：`app/routes/batch_import.py:62-298`（`import_out_order`：表头映射 `100-133` 无 warehouse 分支；建单 `199-208` 无 warehouse/location）、`app/routes/export.py:434`（模板表头无「仓库」）、`app/routes/out_order.py:1144-1150`（完成时静默带入默认仓）
- 现象：与入库导入形成对称缺口——入库导入模板含「仓库/库位」列并逐单落库（`batch_import.py:356-359、502-508`），领料单导入模板**根本没有仓库列**，导入器也不解析，生成的全部领料单草稿 `warehouse=NULL、location=NULL`；完成时被 `complete_out_order` 静默补成默认仓并从默认仓扣库存。
- 证据：```python
# batch_import.py:199-208（领料单建单：无 warehouse/location）
current_order = OutOrder(
    order_no=order_no, date=date_val,
    purpose='领料单' if get_val('purpose') == '生产出库' else get_val('purpose'),
    business_type='领料单', department_id=..., picker=..., remark=...,
    operator_id=current_user.id,
)
# export.py:434（模板）
ws.append(['单据编号','日期','用途','领料部门','领料人','物料编码','物料名称','规格','单位','数量','单价','金额','备注'])
# out_order.py:1144-1150（完成时静默补默认仓）
if not order.warehouse:
    default_wh = get_default_warehouse()
    if default_wh:
        order.warehouse = default_wh.name
```
- 影响：4 仓环境下，导入的领料单若不逐张打开编辑补仓库，完成时会**从默认仓扣库存**——物料实际可能从别的仓库领出，导致扣错仓（A 仓被扣、B 仓不动）；无默认仓时则全部导入草稿无法完成。违反 AGENTS.md §二「未选择仓库时自动带入默认仓库（若已配置）」的**保存时**语义（此处在完成时才补，且用户不可见）。仓库级校验也因 NULL 归属退化为全局口径（`_material_stock_unattributed` 兜底）。
- 根因：out_order 导入是 in_order 导入的旧拷贝，未随 P1-6/仓库必填改造同步（R6 同根因另一消费点）。
- 建议：模板增加「仓库、库位」列并逐行解析（复用 `validate_inventory_warehouse`）；无仓库行直接跳过并给出中文原因（与期初导入 `batch_import.py:848-855` 同口径），**不要**留到完成时静默补默认仓。
- 确认程度：**已确认**
- 关联规则：AGENTS.md §二 / R2 / R6

### [P2] 期初库存「修改库位」不迁移 ② 库位账：只改行字段，差额仍写新库位 → 开启库位管理后 ② 分叉、删行回冲失败
- 位置：`app/app.py:8300/8318-8327`（编辑时 `opening.location = location`，仅改字符串）、`app/app.py:8331-8383`（差额按新 `location` 写 ②）、`app/app.py:8387-8443`（删除回冲按**当前** `line.location` 回冲）、`app/routes/opening_stock.py:660-671`（`save_opening_stock_doc` 把行 `location` 透传）
- 现象：编辑某期初明细行时若只改「库位」而不改数量（delta=0），`_apply_opening_stock_balance` 直接跳过所有账务写入，只把 `opening.location` 字段改成新库位；若同时改数量，差额只加到**新库位**。旧库位的 ② 库存从未回冲/迁移。
- 证据：```python
# app/app.py:8300 / 8318-8327
location = (location or getattr(opening, 'location', '') or '').strip()
...
else:
    opening.quantity = new_quantity
    ...
    opening.location = location          # ← 只改字段
# 8331
if abs(quantity_delta) > STOCK_COMPARE_EPSILON:
    ... sa_update(Material) ...          # ① 只按数量差
    apply_opening_balance(..., location=location or None, ...)  # ② 只写新库位
# 8387-8443 删除回冲：
effective_location = (line.location or '').strip() or (warehouse.name or '').strip()
update_location_inventory(material, effective_location, delta, warehouse=warehouse)
```
- 影响：开启库位管理后，旧库位 ② 残留、新库位 ② 虚增（物料级 ①=Σ② 仍可能成立，故 `verify_inventory_identity` 的物料级判据看不出来，只有仓级/库位级能暴露）；随后删行回冲会从新库位扣，若新库位不足 → 删单被拒（「删除失败：…无库位库存记录/库存不足」），单据卡死。当前库位管理关闭（生产默认 `'0'`），暂不触发，属「开启库位管理前必须修」的高危项（INVENTORY_TRUTH §6 自检清单「写入：三层是否同一事务维护」）。
- 根因：期初编辑的「行移动」语义（换库位）没有实现 ② 的搬迁/回冲；只实现了数量差。
- 建议：编辑时先按 `(旧 location, -旧数量)` 回冲 ②、再按 `(新 location, +新数量)` 建账（同一事务），或禁止在没有专门迁移逻辑时修改已建账行的库位（前端置灰 + 后端 400）。
- 确认程度：**已确认**（静态可断定；当前功能未启用故影响为零，开启后触发）
- 关联规则：INVENTORY_TRUTH §2.1.2 / §6 / R2

### [P2] Excel 期初导入逐行捕获异常后不回滚/不用 SAVEPOINT：失败行可能「报跳过但已落账」，② 与 ①③ 分叉
- 位置：`app/routes/batch_import.py:899-941`（`try/except ValueError` 只记录 error/skip，**不 rollback**）、`app/routes/batch_import.py:983`（循环外统一 commit）
- 现象：`_apply_opening_stock_balance` 的执行顺序是「① `sa_update(Material)` → （开库位时）legacy 回填 → ③ 流水 → ② 库位账」，任一步抛 `ValueError` 时前面已执行的写入仍留在 session 里；导入循环捕获 `ValueError` 后 `continue`（无 rollback、无 savepoint），循环末尾统一 `commit()` → 该行被报「跳过」但 ①（可能还有 ③）实际已提交。
- 证据：```python
# batch_import.py:936-941
preview_rows.append(outcome)
except ValueError as ve:
    errors.append(f'第 {row_no} 行：{ve}')   # ← 无 db.session.rollback()
    skipped += 1
    outcome.update(action='skip', reason=str(ve))
    preview_rows.append(outcome)
...
# batch_import.py:983
db.session.commit()          # ← 把上面"失败行"的部分写入一起提交
```
- 影响：开启库位管理后，若某行 ② 同步失败（库位库存不足是现实场景），该行会被报「跳过」但 ①③ 已落账，**② 缺失 → ①=Σ③ 成立但 ①≠Σ②**；用户按提示改表重传会重复加库存。当前库位管理关闭时 ② 分支不执行、无 ValueError 来源，暂不触发。
- 根因：逐行错误处理缺少事务边界（典型「一个事务里循环写、失败行不隔离」缺陷；同类正确写法见同文件 `dry_run` 分支会显式 rollback）。
- 建议：每行写账包在 `db.session.begin_nested()`（SAVEPOINT）中，失败回滚到保存点；或收集错误行后整批失败回滚（与「要么全导入要么全不导入」的期初导入语义一致）。
- 确认程度：**高度可疑**（静态路径已确认；触发需开启库位管理且 ② 失败）[需运行验证]
- 关联规则：INVENTORY_TRUTH §2.1.2 / R2 / R4

### [P2] 旧打印报表 /report/inout/print：含未完成草稿、丢弃列表筛选、仓库判据未走唯一实现
- 位置：`app/routes/report.py:334-426`（`report_inout_print`）、`app/static/js/app.js:1903-1927`（`WMS_REPORT_PRINT_PARAM_MAP` 只保留 warehouse_id/start_date/end_date）、对比 `app/services/warehouse_scope.py:33-59`（报表仓库唯一判据）
- 现象：in_order / out_order 列表页的「打印列表」按钮指向该路由，但：
  1. 查询**不过滤单据状态**（`report.py:366、395`），pending 草稿与 completed 一起被计为「入库统计/领料统计」；
  2. 列表页的 status/search/supplier_id 等筛选在 JS 层被主动丢弃（`app.js:1903-1909` 注释自述），打印结果 ≠ 屏幕筛选结果；
  3. 仓库过滤用 `db.or_(InOrder.warehouse == name, == code)`（`report.py:349-356`）手工拼装，未走 2026-09-25 收口的 `document_warehouse_filter`（`warehouse_scope.py`），历史脏数据（warehouse 为 NULL/库位名）的单据被静默漏查——恰是该唯一判据要消灭的口径分叉（R6）。
- 证据：
  ```python
  # report.py:366-378  无 status 条件
  in_query = InOrder.query.filter(_wh_clause)
  if start_date: in_query = in_query.filter(InOrder.date >= start_date)
  if end_date:   in_query = in_query.filter(InOrder.date <= end_date)
  for order in in_query.order_by(InOrder.date.desc()).all():
  ```
  ```javascript
  // app.js:1910-1914  只映射 3 个参数，status/search/supplier 被丢弃
  var WMS_REPORT_PRINT_PARAM_MAP = [
      { from: 'warehouse_id', to: 'warehouse_id' },
      { from: 'date_start', to: 'start_date' },
      { from: 'date_end', to: 'end_date' }
  ];
  ```
- 影响：月结对账/打印归档时，未发生的 pending 草稿被当成已入库/已领料计入报表；用户按筛选条件打印出的结果与屏幕不一致；历史脏数据单据在打印报表中凭空消失（「有单据查不出」）。违反 R1（打印≠全量语义）、R2（汇总口径）、AGENTS.md 报表仓库必填的「同一判据」精神。
- 建议：打印路由默认只取 `status='completed'`（或把 status 作为白名单参数透传）；把列表筛选白名单补齐（status、search、supplier_id、contract_no 等受支持项）；仓库过滤改用 `document_warehouse_filter(InOrder, warehouse_name, warehouse_code)`。
- 确认程度：**已确认**（行为）；是否为业务预期需产品确认（若是「单据清单打印」则应改标题与口径说明）
- 关联规则：R1 / R2 / R6

### [P2] 库存预警「仓库视图」的业务物料判据只按 warehouse_id 过滤流水，缺 NULL+location 历史兜底 → 仓库缺货静默漏报
- 位置：`app/routes/inventory_alert.py:85-117`（`_warehouse_scoped_material_ids`：判据 b/c 仅 `StockTransaction.warehouse_id == warehouse.id`）、对比 `app/app.py:5396-5423`（`get_warehouse_stock_quantities` 的 OFF 分支含 NULL+location / 来源单据兜底）、`app/routes/inventory_alert.py:271`（`disabled_stock_count` 统计）
- 现象：选定仓库查看 /alert 时，先算「本仓业务物料」范围；该范围的三条判据（库位账行/流水净额/存在 out 流水）里，判据 b、c 只认 `warehouse_id`，而同一页面的库存数量来自 `get_warehouse_stock_quantities`——后者会把 `warehouse_id IS NULL AND location IN (仓库名/编码/库位名)` 的历史行、以及空 location+来源单据行计入。两套判据在历史数据上分叉：物料在本仓有库存（数量口径算得到），却不被判定为「本仓业务物料」→ `continue` 跳过，**不告警也不计入任何状态分组**。
- 证据：
  ```python
  # inventory_alert.py:85-90（判据 b：只认 warehouse_id）
  net = (db.session.query(StockTransaction.material_id,
         func.coalesce(func.sum(StockTransaction.quantity), 0))
         .filter(StockTransaction.warehouse_id == warehouse.id)   # ← 无 NULL+location 兜底
         .group_by(StockTransaction.material_id).all())
  ...
  # app.py:5398-5404（同口径查询却有兜底）
  .filter(db.or_(
      StockTransaction.warehouse_id == warehouse.id,
      db.and_(StockTransaction.warehouse_id.is_(None),
              StockTransaction.location.in_(loc_names)),
  ))
  ```
- 影响：多仓环境下，靠历史 NULL 归属流水维持库存的物料在仓库视图**不告警**（缺货漏报）；同时这些被跳过的物料落入 `disabled_stock_count`（`271` 行用减法计算），页脚「未启用预警」计数被污染。违反 R2（历史脏数据兼容）与 R6（同根因判据分叉）。
- 建议：判据 b/c 复用 `_warehouse_location_filter_values` + `_filter_txn_list_by_warehouse_scope`（`app/app.py:29202/29615`），或直接以 `get_warehouse_stock_quantities(warehouse)` 的 keys 作为 scoped 集合基线，再叠加误录冲回过滤。
- 确认程度：**已确认**（判据分叉）；实际漏报量取决于历史数据 → [需运行验证]
- 关联规则：A11 / R2 / R6

### [P2] 库存查询传无效 warehouse_id 时不校验不回退，渲染全部物料且库存全部为 0
- 位置：`app/routes/stock_query.py:94-100`（`warehouse = Warehouse.query.get(warehouse_id)` 不做存在/启用校验；`if warehouse_id or all_warehouses_mode:` 仍进入渲染）
- 现象：`?warehouse_id=999999`（或已删除仓库 id）时 `warehouse=None` → `warehouse_stock_map={}`，但入口判断只看 `warehouse_id` 真值 → 返回**全部物料 + 全 0 库存**页面，无任何「仓库不存在」提示。
- 证据：
  ```python
  # stock_query.py:94-100
  warehouse = Warehouse.query.get(warehouse_id) if (warehouse_id and warehouse_id > 0) else None
  if all_warehouses_mode:
      warehouse_stock_map = get_all_warehouses_stock_quantities()
  elif warehouse:
      warehouse_stock_map = get_warehouse_stock_quantities(warehouse)
  if warehouse_id or all_warehouses_mode:   # ← warehouse 为 None 也放行
      ...渲染...
  ```
- 影响：用户/书签/旧链接指向已删仓库时，页面表现为「所有物料库存为 0」，极易被误判为「库存被清空/账实不符」而引发错误操作（该页是库存查询主入口）。违反 AGENTS.md §二「不指定仓库时不得返回数据」的口径精神（这里是指定了一个无效仓库）。
- 建议：`warehouse_id` 非 0 时必须解析成功且 active，否则 400/空页并提示「仓库不存在或已停用」。
- 确认程度：**已确认**
- 关联规则：AGENTS.md §二 / R2

### [P2] 新增物料带初始库存且未配置默认仓库时，写入无仓库归属的 ③ 流水（多仓下成为不可见库存）
- 位置：`app/routes/material.py:336-356`（`_default_wh = get_default_warehouse(); _loc = _default_wh.name if _default_wh else None`；`apply_opening_balance(warehouse=_default_wh, ...)`）、`app/services/warehouse_stock_service.py:373-384`（`add_stock_transaction` 只把 warehouse 解析成 warehouse_id，None 就落 NULL）、`app/app.py:4863-4891`（`resolve_inventory_warehouse_id(None) → None`）
- 现象：新增物料时的「初始库存」在没有默认仓库的库上照样放行：① `Material(stock=initial_stock)` 直接构造、③ 写一条 `warehouse_id=NULL` 的 opening 流水，没有任何仓库归属。多仓环境下该库存不进入任何仓库的仓库级查询/报表（`get_all_warehouses_stock_quantities` 逐仓汇总排除它），只在全局 `material.stock` 可见；后续出库依赖 `_material_stock_unattributed` 回退全局兜底才能勉强操作。
- 证据：
  ```python
  # material.py:336-353
  if initial_stock and initial_stock > 0:
      _default_wh = get_default_warehouse()
      _loc = _default_wh.name if _default_wh else None
      ok_open, msg_open = apply_opening_balance(material, initial_stock,
          warehouse=_default_wh, location=_loc, reference_id=material.id, ...)
  # services/warehouse_stock_service.py:377-384
  add_stock_transaction(material, qty, 'opening', ..., warehouse=warehouse, ...)
  ```
- 影响：多仓下「新物料初始库存」凭空落在无归属池（INVENTORY_TRUTH §3.2 保留 NULL 本意是「历史无法归属」，新数据不应再造新的不可归属行）；库存查询/仓库报表看不到该库存，可能重复采购；出库时靠兜底放行后又产生新归属流水，仓库账面出现「先 0 后负」噪声。
- 建议：无默认仓库时拒绝「初始库存 > 0」的新建（提示「请先配置默认仓库或改用期初库存单并指定仓库」），或要求表单显式选仓库（`apply_opening_balance` 已有 warehouse 参数）。
- 确认程度：**已确认**（代码路径）；影响取决于是否配置默认仓 [需运行验证]
- 关联规则：INVENTORY_TRUTH §3.2 / A11 / R2 / AGENTS.md §二

### [P2] AI 出库异常分析用全局总账判定「超库存出库」（已拿到订单仓库却不用仓库级口径）
- 位置：`app/app.py:10560-10592`（`api_ai_out_order_anomaly_analysis` 分析循环：`current_stock = float(m.stock or 0)`、`if item_qty > current_stock`、`current_stock <= min_stock`）
- 现象：该分析针对**某一张出库单**（订单有 warehouse 字段），却用全系统合计 `material.stock` 判断「出库数量超过当前库存」与「出库后低于最低库存」。多仓下 A 仓库存可掩护 B 仓超卖：B 仓订单 100、B 仓库存 0、A 仓库存 1000 → 分析静默放行（不报异常）。
- 证据：```python
# app.py:10561-10577
for item in order.items:
    m = item.material
    current_stock = float(m.stock or 0)     # ← 全局总账
    ...
    if item_qty > current_stock and current_stock >= 0:
        anomalies.append({'anomaly_type': '超库存出库', ...})
```
  对比同文件 `app.py:35680-35701` 的「缺货风险」分析已改为 `get_warehouse_stock_quantities(wh_obj)` + 兜底（正确写法，可直接照抄）。
- 影响：AI 异常提示是提交前用户唯一可见的「超库存」告警（`_check_out_order_anomalies` 已在 FEAT-2026-10-03-001 移除数量类检测，只保留整单重复），该分析用错口径会让多仓超发更隐蔽。违反 A11 / R2。
- 建议：解析 `order.warehouse`/`order.warehouse_id` → `get_warehouse_stock_quantities`，无仓库/无法解析时才回退全局并加 `# stock-truth:reason=`。
- 确认程度：**已确认**
- 关联规则：A11 / R2

### [P3] `utils.check_stock_sufficient()` 裸用全局总账做库存校验（A11 潜在违规，当前无调用点）
- 位置：`app/utils.py:238-246`；被 `app/app.py:166` `from utils import ... check_stock_sufficient` 拉进主命名空间
- 证据：`current_stock = normalize_stock_quantity(material.stock or 0)` 后 `is_stock_sufficient` 判不足——正是 A11 明令禁止的「裸用总账做校验」写法，且无 `# stock-truth:reason=` 豁免。
- 影响：当前业务无调用点（grep 全仓仅 import），但主命名空间可随时被新代码误用，属「违规样板留在库里」；A11 的 pre-commit 只查新增行，存量不报。
- 建议：删除该函数（无调用点）或改写为接受 `warehouse` 参数并调用 `get_warehouse_stock_quantities`，同时去掉 `app.py:166` 的导入。
- 关联规则：A11

### [P3] 报表库存状态判定在打印路由内联重复实现（违反「唯一实现」约定，R6 漂移风险）
- 位置：`app/routes/report.py:502-514`；权威实现 `app/app.py:7458-7476` `_alert_status_for()`（注释自述为「全系统两级口径的唯一实现」）
- 证据：`report.py:506-513` 用 if/elif 重写 disabled/low/danger/normal 四级判定，逻辑目前与权威实现一致但无共享；任一改动（如新增「安全库存=0 视为关闭」细则）必然分叉。
- 建议：改为 `_material_alert_status_values(m, stock=stock)[3]` 或 `_alert_status_for(stock, min_stock, safety_stock)`。
- 关联规则：R6 / A11（口径一致性）

### [P3] AI 销售履约工作台的 metric_scope 文案仍写 `Material.stock`（实现已改仓库级，文档漂移）
- 位置：`app/ai/ops/sales_followup_workbench.py:11、238`（`metric_scope='SalesOrderItem.quantity > Material.stock'`）；实际 provider `app/app.py:16176-16215` 已使用 `get_warehouse_stock_quantities(warehouse)`
- 影响：对外展示的「指标口径」与实际计算不一致，审计/复核时会被误判为 A11 违规（本次已核实实现正确）；属文档漂移，但会误导后续维护者把正确实现改回全局。
- 建议：文案改为 `SalesOrderItem.pending_quantity > 该订单仓库库存`。
- 关联规则：A11 / R6（文档口径）

### [P3] 遗留旧 API `/api/subcontract/quick_issue` / `quick_receive`：无调用方仍在线，可写库存但无写锁/无幂等
- 位置：`app/app.py:7627-7754`（quick_issue）、`app/app.py:7756-7853`（quick_receive）
- 证据：全仓 grep（templates/static/js/android-native-wms/tests）无任何调用点；`quick_issue` 直接 `deduct_stock_atomic` + 手工 `update_location_inventory` 双写（`7725-7741`），未使用 `_acquire_order_write_lock`/BEGIN IMMEDIATE（对比同期 mobile/native 扫码链路已加锁）。重复提交会各建一张 completed 发料单并双扣库存。
- 影响：死代码但仍是可写库存的 POST 入口（有 @login_required/@require_role，认证在）；若被旧客户端或脚本调用，重复/并发提交可造成双扣。属 R6 双轨实现残留。
- 建议：下线两个路由（返回 410）或迁移到 `apply_stock_delta` + `_acquire_order_write_lock` 并补 A9 测试。
- 关联规则：R6 / R4

### [P3] 物料表单/编辑页的库存提示字段暴露全局总账（与后端仓库级校验口径不一致）
- 位置：`app/app.py:26335-26351` `_material_line_data()`、`app/app.py:26721-26740` `_serialize_adjustment_item_for_form()`、`app/routes/after_sale_out.py:182-193`（编辑页 initial_items）、`app/routes/mobile.py:153-155`（无仓上下文回退）
- 现象：合计约 10 处页面序列化把 `material.stock`（全局）作为行内「当前库存」提示回填给前端；而同一单据的完成预校验是仓库级口径。多仓下用户会看到「库存 100」而按本仓 0 被拒，或反之。
- 建议：表单上下文有仓库时（入/出/调拨/售后单的编辑页）改用 `get_warehouse_stock_quantities`；若刻意保留全局展示，必须在字段名/页面标注「全系统合计」。
- 关联规则：A11（展示允许但需标注口径）/ INVENTORY_TRUTH §2.2

### [P3] 开发探针脚本 `app/logs/flow_logic_probe.py` 位于 app 包内并直写 `StockTransaction`（不改 ①）
- 位置：`app/logs/flow_logic_probe.py:22`（`w.db.session.add(w.StockTransaction(material_id=mat.id, quantity=100, transaction_type='opening', warehouse_id=wh.id, location=wh.name))`）
- 现象：脚本用 `sys.path.insert(0,'C:/wms/app')` 硬编码路径、内存库 fixture，直接写 ③ 而不改 ①——一旦被误当应用脚本运行/导入，会立刻制造 ①≠③。当前无任何文件引用它（grep 全仓零引用），属「装在 app/ 里的开发残留」。
- 建议：移出 `app/`（如 `scripts/dev/` 或 `tests/fixtures/`），并删除硬编码路径。
- 关联规则：A14（scripts 引用 app 的门禁精神）

---

## 4. 附录 A：写库存代码点全景（本次逐点核对）

| # | 代码点 | 位置 | 维护的账层 | 调用方/备注 |
|---|---|---|---|---|
| 1 | `deduct_stock_atomic` | app/app.py:4756-4822 | ① 原子条件扣 + ③（有 transaction_type 时） | 唯一扣减原语；不写 ②（由调用方负责） |
| 2 | `add_stock` | app/app.py:4824-4861 | ① + ③ | 只经入口调用；不写 ② |
| 3 | `deduct_stock`（旧薄包装） | app/app.py:4724-4737 | 委托 #1 | **全仓无调用点**（死代码） |
| 4 | `add_stock_transaction` | app/app.py:5098-5115 | 仅 ③ | 调拨/建账用；**不动 ①** |
| 5 | `update_location_inventory` | app/app.py:4893-4953 | ②（正负分发，#6/#7） | 入口层 + app.py:7736 旧 API 直调 |
| 6 | `add_location_inventory_atomic` | app/app.py:4955-5038 | ② 增（自动建账，SAVEPOINT） | 被 #5、期初 legacy 回填调用 |
| 7 | `deduct_location_inventory_atomic` | app/app.py:5040-5096 | ② 减（原子条件，防超发） | 被 #5 调用 |
| 8 | `apply_stock_delta` | services/warehouse_stock_service.py:188-250 | ①+③+②（开关控制） | **业务唯一入口**，36 处调用（in/out/adjust/after_sale/requisition/subcontract/mobile/native/app） |
| 9 | `apply_transfer_pair` | services/warehouse_stock_service.py:253-331 | ③ 双向 + ②；**① 不动** | transfer complete/revert（2 处） |
| 10 | `apply_opening_balance` | services/warehouse_stock_service.py:334-395 | ③ + ②；**① 由调用方** | 期初建账/物料初始库存（3 处直调 + 经 #11） |
| 11 | `_apply_opening_stock_balance` | app/app.py:8286-8384 | ① `sa_update` + 委托 #10 | 期初所有写路径（opening_stock 9 处、batch_import、native_api） |
| 12 | `_reverse_opening_stock_line` | app/app.py:8387-8443 | ③ 物理删除 + ① 回冲 + ② 回冲 | 期初删行/删单/清空（7 处调用） |
| 13 | `_zero_all_material_stock` | app/app.py:8146-8152 | **仅 ①** 全表归零 | 仅「业务数据初始化」；见 P1-3 |
| 14 | `merge_material_duplicates` | app/app.py:9133-9238 | ① 累加 + ② 合并 + ③ 改指 | 物料合并；7 步复检 ①=Σ③，回调侧 `material.py:889-893` 在 `ledger_regressed` 时回滚 |
| 15 | 新建物料 `Material(stock=initial_stock)` | routes/material.py:303-321 | ① 构造赋值 + 委托 #10 写 ③② | 见 P2「无默认仓 → 无归属流水」 |
| 16 | 旧 /api/subcontract/quick_issue | app/app.py:7725-7741 | 直调 #1 + 手工 #5 双写 | 旧双轨残留，无锁，见 P3 |
| 17 | 旧 /api/subcontract/quick_receive | app/app.py:7821-7826 | 经 #8 | 已收敛 |
| 18 | `StockTransaction(` 直接构造（非原语） | app/app.py:4809、4848、5103 | ③ | 全部在原语内部（合规）；全仓无其它位置直写 |
| 19 | 探针脚本直写 ③ | app/logs/flow_logic_probe.py:22 | 仅 ③ | 开发残留，见 P3 |

**反提交/删除对称性核对结论**：in_order / out_order / transfer / adjustment / after_sale_out / requisition / subcontract_issue / subcontract_receive 的 complete↔revert 均经同一入口异号对称；草稿物理删除时均清理 `StockTransaction`（19 处清理点，逐一核对「已反提交单的流水净额恒为 0」，删流水不改变 Σ③ 净额）；期初删单/删行走 ③ 物理删除 + ① 回冲 + ② 回冲。**未发现「只改其中一层」的现存主链路写路径**（缺陷集中在上述 P1/P2 旁路）。

## 5. 附录 B：A11 消费点清单（全局总账 `material.stock` 读取点判定）

> 判定口径（INVENTORY_TRUTH §2.2/§5）：**业务校验必须读仓库级** `get_warehouse_stock_quantities()`；**展示允许**全局总账；有仓库上下文却用全局 = 违规；历史脏数据兜底必须带 `# stock-truth:reason=`。

| 分类 | 点位（file:line） | 判定 |
|---|---|---|
| **违规/待修** | app/app.py:11635、11664、11683（AI 盘点草稿账面） | 违反，见 P1（AI 草稿） |
| | app/app.py:10564、10572、10592（AI 出库异常分析，订单有仓库） | 违反，见 P2 |
| | app/utils.py:238-246 `check_stock_sufficient`（无调用点） | A11 潜在违规，见 P3 |
| **已登记兜底（合规）** | app/app.py:7681（委外发料未归属兜底，注释） | ✅ |
| | app/app.py:7488/7494（`_material_alert_status_values` 全局视角回退，`stock-truth:reason`） | ✅ |
| | app/app.py:5383-5385（单仓短路，`stock-truth:reason`，INVENTORY_TRUTH §3.3a） | ✅（新增第二仓前必须复测） |
| | app/app.py:35694/35698（缺货风险提示兜底，`stock-truth:reason`） | ✅ |
| | routes/in_order.py:2140、2143、2271、2274、2468、2474、2494（反提交/改单兜底，均有注释） | ✅（但见 P1「逐行快照」） |
| | routes/in_order.py:2971、2977、2993（批量反提交兜底，注释） | ✅（同上） |
| | routes/adjustment.py:380（报损校验兜底，注释） | ✅ |
| | routes/after_sale_out.py:437、440（售后出库兜底，注释） | ✅（同上） |
| | app/ai/tools/inventory.py:299（库存价值展示，`stock-truth:reason`） | ✅ |
| **展示（允许，建议标注口径）** | app/app.py:7216（`api_material_payload` 无仓上下文回退）、9124/9127/9128/9157/9158（合并预览）、10110-10160/10240-10293（AI 报告）、10393/10422-10444（AI 健康分析）、10776-10840（AI 报告）、10974/12117-12120/12513-12515/15664-15687/18402-18469/18528/19472/20270/20520-20544/22140/23031-23033（AI/仪表盘全局概览）、14499/17745/17822（AI 文案）、19566（主数据体检，`stock-truth:reason`）、19637、26346/26736（表单序列化，见 P3）、31946/31951/32000-32068（AI 补货/健康，全局分析）、34855（AI 需求预测） | 展示允许；其中 31946-32068、34855 属「全局视角分析」，建议标注「全系统合计」 |
| **设计内的全局总览** | app/app.py:7442-7454（`_material_low_stock_filter` 首页/列表全局低库存筛选）、7514-7521、routes/inventory_alert.py:222-224（`/alert` 不选仓时的全局总览，注释自述设计） | ✅（选仓后已切仓库级） |
| **全局总览型 AI/通知** | app/ai/patrol_scheduler.py:74、89、177（负库存/低库存/呆滞巡检）、app/notifications.py:130、201（通知文案） | 巡查总览语义可接受；建议在文案标注「全系统合计」 |
| **口径文案漂移** | app/ai/ops/sales_followup_workbench.py:11、238（实际实现已仓库级） | 见 P3 |
| **写入口内部（非校验读数）** | app/app.py:4776、4794、4798、4802、4842、8335、8430、9202-9203、services/warehouse_stock_service.py:79、128 | 属于 ① 的原子维护/复检，非 A11 对象 |
| **仓库级读取（正确范式，供参考）** | app/app.py:7161、7611、16800+、35680、35890；routes/*: adjustment.py:375-376、after_sale_out.py:427-433、check.py:297/478/711/815/1106、inventory_alert.py:175/220、in_order.py:2134/2268/2456/2959、mobile.py:153/571/658、native_api.py:193/1408/1842/1851/1982/2123/2614/2991、out_order.py:53、report.py:445、requisition.py:164/378/432/527、sales.py:42/70/103、stock_query.py:96-98、subcontract.py、transfer.py:515/584（共 70 处调用） | ✅ |

**扫描统计**：`app/` 下 163 个 .py / 105,911 行；`.stock` 代码行 186（含注释与字符串），其中真正参与「校验/决策」的约 30（含 8 处已登记兜底），**本次新增确认的违规/待修 3 类**（AI 盘点草稿、AI 出库异常分析、utils 遗留函数）。

## 6. 建议优先级路线图（≤10 条）

1. **（P1）修 AI 草稿仓库必填**：5 个 `_ai_create_*_draft` 统一解析/校验/回退默认仓；盘点草稿账面改仓库级。先修盘点（死路），再修其余 4 条。
2. **（P1）把「仓库级扣减校验」收口进入口层**：4 处「快照+逐行」预校验改为按物料聚合（照抄 `transfer.py:516-526`）；顺带在 `apply_stock_delta` 内固化仓库级校验，禁止路由自写。
3. **（P1）业务数据初始化改为「整体事务 + 先删流水后归零」**，`_bulk_delete_model` 失败必须整体失败，并在响应/审计中回显三账判据结果。
4. **（P2）领料单 Excel 导入补仓库/库位列**（与入库导入对齐），无仓库行跳过并提示；禁止完成时静默落默认仓。
5. **（P2）期初编辑库位变更补 ② 搬迁**（或暂时禁止改已建账行库位）；Excel 期初导入逐行加 SAVEPOINT。两项一起做，避免开库位后连环故障。
6. **（P2）旧打印报表 /report/inout/print** 增加状态过滤（默认 completed）、补齐筛选白名单、仓库判据改 `document_warehouse_filter`。
7. **（P2）/alert 仓库视图 scoped 判据复用 `_warehouse_location_filter_values`/`get_warehouse_stock_quantities`**，并修正 `disabled_stock_count` 统计。
8. **（P2）stock_query 无效仓库 400/空页显式化**；新增物料初始库存无默认仓时拒绝或强制选仓。
9. **（P2）AI 出库异常分析改仓库级口径**（照抄 `app.py:35680-35701`）。
10. **（P3 批量清理）**：删除 `check_stock_sufficient` 与 `app.py:166` 导入；report 库存状态复用 `_alert_status_for`；修 workbench metric_scope 文案；下线两个旧委外 API；移出 `app/logs/flow_logic_probe.py`；表单库存提示标注口径。
