# 后端单据生命周期与路由业务逻辑审计（backend-flow）

> 审计日期：2026-10-18 ｜ 审计员：backend-flow ｜ 仓库 HEAD：`0f8442b3`（2026.09.1）
> 依据：`docs/audit/2026-10-18/_shared_brief.md`（分级/格式/不报项）
> 方法论：**纯静态分析**。本会话无法执行任何外部进程（pwsh 0xC0000142、python/git EPERM），
> 未运行 pytest / 服务 / 脚本；凡"运行时才能确认"的结论均标 `高度可疑`。

## ① 审计范围与覆盖度

### 1.1 路由地图（glob+grep 全量统计，非抽样）

| 范围 | 文件数 | @route 声明 | 写接口（POST/PUT/DELETE/PATCH） |
|---|---|---|---|
| `app/routes/*.py` | 49 | 611 | 316 |
| `app/app.py` | 1（35,995 行） | 94 | 43 |
| 蓝图注册 | — | `app.py:3417-3430` 仅 5 个（ai/ai_feedback/ai_excel/unit/v2） | — |
| `register_*_routes(app)` 调用点 | — | `app.py:3435-3526` 43 个 + `7096/7100` 2 个 | — |

- **重复注册检查**：对 705 条 (url, method) 去重比对，**0 组真冲突**；16 组同 URL 均为 GET 页面 + POST 提交的正常配对
  （如 `/in_order/add` GET=in_order.py:886 / POST=in_order.py:997）。
- 4 组"同功能多 URL"（`/subcontract_issue/...` 与 `/subcontract/issue/...` 三对别名，subcontract.py:1046-1048、1282-1284、1375-1377、1421-1425）= 多入口同一函数，无逻辑冲突。
- **唯一真正的双实现**：委外快速发料/收货同时存在 `app.py:7627/7756`（旧 JSON API）与 `routes/subcontract.py:308/405`（新表单路由），见 P1-4。

### 1.2 精读（行级）清单

- `app/app.py`：仅架构面 + 关键原语，**未逐行读**。已读：路由/蓝图/hook/errorhandler 统计（3417-3430、4395-4475、4522-4614、3557）、
  `api_error`(219)、`log_audit`(5118)、`log_operation`(7103)、`_acquire_order_write_lock`(25906)、`add_stock`(4824)、
  `deduct_stock_atomic`(4756)、`get_warehouse_stock_quantities`(5342)、`is_warehouse_active`(5261)、`get_default_warehouse`(5291)、
  `validate_purchase_receive_quantity`(6278)、`update_purchase_order_status`(6222)、`recalculate_sales_order`(35129)、
  `sync_sales_order_shipment`(35185-35233)、`_create_adjustment_drafts_from_check`(26767)、`_void_check_scan`(26974)、
  `get_bearer_user`(6937)、`api_role_required`(6980)、`web_or_api_required`(7049)、`debug_in_order`(26083)、
  `check_legacy_page`(26757)、`api_subcontract_quick_issue/receive`(7627-7815)。
- `app/routes/`（本任务核心 16 模块，逐函数读 complete/revert/delete/batch/审批类）：
  `in_order.py`（约 1,300 行：add / complete / update_completed / delete / revert / batch_complete / batch_revert / batch_delete / 明细增删改）、
  `out_order.py`（complete / revert / delete / batch_complete / batch_delete / `_out_order_stock_error`）、
  `transfer.py`（complete / revert / update / copy / delete / batch_delete）、
  `check.py`（complete / revert / delete / batch_delete / add_item）、
  `adjustment.py`（save / complete / revert / delete / batch_delete）、
  `opening_stock.py`（delete_all / delete_doc / lines_delete）、
  `purchase_order.py`（delete / batch_delete / close / reopen / create_in_order）、
  `purchase_request.py`（approve / reject / revert / complete / delete）、
  `sales.py`（confirm / create_outbound_draft / batch_confirm / cancel / delete）、
  `subcontract.py`（发料 complete/revert/delete、主单 complete/revert、batch_update_status、import）、
  `requisition.py`（complete / revert / delete / batch_delete）、`after_sale_out.py`（complete / revert / delete / edit 页）、
  `batch_import.py`（opening_stock_import 全流程 + import_in/out_order 路由）、`approval.py`（全文）、
  `pending_documents.py`（全文）、`report.py`（全部路由 + 仓库必填校验）、`stock_query.py`（路由清单）、
  `print_queue.py`（create_job 段 520-690）。
- 支撑：`app/utils.py`（require_role 758-795、serialize_material 164-186、round/normalize/parse/recalculate 26-256）、
  `app/services/warehouse_stock_service.py`（全文 396 行：apply_stock_delta / apply_transfer_pair / apply_opening_balance）、
  `app/models/documents.py`（InventoryCheck/TransferOrder/AdjustmentOrder/OpeningStockDoc/BOM）。

### 1.3 未覆盖 / 仅浅扫（明确声明，未据此下结论）

- `routes/native_api.py`（4,115 行，41 路由）：仅做装饰器/路由/CSRF 清单扫描，**未逐个审计**移动端入库/出库/盘点的幂等与库存写入；只在"CSRF 豁免端点是否 Bearer-only"上做了全局校验（结论：写端点均为 Bearer-only；3 个刻意匿名端点仅写日志/换 token）。
- `routes/mobile.py`、`export.py`、`sales.py` 报表段（L1116-2152）、`report.py` 的 `_build_report_payload`（在 app.py，未读）、`subcontract.py` 收料单段（L1564-2342）、`bom.py`、`batch_import.py` 的 in/out 导入逐行逻辑、打印链路（print_queue/print_routing/print_alerts 仅按安全面抽读）、AI 域（不在本任务范围）。
- 运行期行为（并发竞态、真实 500、SQLite 锁行为）**未验证**——相关条目标 `高度可疑`。

## ② 结论摘要

| 级别 | 数量 |
|---|---|
| **P0** | **0** |
| **P1** | **4** |
| **P2** | **8** |
| **P3** | **5** |

**一句话总评**：单据主链路（in_order / out_order / transfer / check / adjustment / opening_stock）的
"完成加库存 ↔ 反提交减库存"在**单张路径上高度对称且防护扎实**（写锁 + 条件 UPDATE + 三账单一入口 + 失败即 rollback 已到位），
本审计**未发现 P0 级账实分裂**；真正的风险集中在**批量入口与单体入口的门禁漂移**（P1-1/2/3）、
**两套并存实现**（P1-4）以及**编码/精度/异常详情等外围工程质量**（P2）。
按 R6（同根因排查全消费点）口径，P1-1/2/3 都是"单张修了、批量漏了"的同一根因多消费点。

## ③ 详细 findings

### [P1] 批量完成/反提交入库单不回写采购订单状态
- 位置：`app/routes/in_order.py:2714-2902`（batch_complete）、`app/routes/in_order.py:2908-3027`（batch_revert）；对照 `app/routes/in_order.py:1953-1956`、`2527-2530`
- 现象：单张 `complete_in_order` / `revert_in_order` 改完 `order.status` 后会调用 `update_purchase_order_status(purchase_order)` 重算来源采购订单状态；两个批量入口全程**没有任何一次**该调用。
- 证据：
  ```python
  # in_order.py:1953-1956（单张完成，有）
  order.status = 'completed'
  order.total_amount = sum((item.amount or 0) for item in order.items)
  for purchase_order in PurchaseOrder.query.filter(PurchaseOrder.id.in_(affected_purchase_order_ids)).all():
      update_purchase_order_status(purchase_order)

  # in_order.py:2853-2856（批量完成，无 affected ids / 无重算）
  order.status = 'completed'
  order.total_amount = sum((item.amount or 0) for item in order.items)
  db.session.commit()
  ```
  PO 状态是**派生值**：`app.py:6238-6260` 用 `InOrder.status=='completed'` 聚合 `received_qty` 后回写 pending/partial/completed。
- 影响：凡通过列表"批量审核/批量反审"操作的入库单，其来源采购订单状态**长期停留在旧值**（已全收货仍显示 pending/partial，或已反提交仍显示 completed）；采购执行报表、`/api/purchase_order/todo_summary`、待办单据均基于该状态 → 采购跟单口径错误、重复催货/漏采购。无库存数量错误（received_quantity 在 add/delete 维护），故非 P0。
- 根因：同一"派生状态回写"职责只在单张路径实现，批量路径复制时漏掉；无测试锁（`tests/` 中 batch_complete/batch_revert 的用例都只断言库存与跳过原因，无 PO 状态断言）。
- 建议：两个批量入口在每单 commit 前按 `item.source_purchase_order_item.purchase_order` 收集 affected ids 并调用 `update_purchase_order_status`（与 `batch_delete_in_order:2685-2695` 的收尾写法一致，那里已正确实现）；补回归测试断言 PO 状态。
- 确认程度：**已确认**（读代码 + grep 全文件 `update_purchase_order_status` 21 处定位，批量两函数内 0 处）
- 关联规则：R6（同根因全消费点）、§〇 状态权威表（PurchaseOrder）

### [P1] 批量反提交入库单缺少"下游有效下推"守卫
- 位置：`app/routes/in_order.py:2908-3027`（batch_revert_in_order）
- 现象：单张反提交、单张删除、批量删除都会先检查 `_source_has_active_push(order_id)`，**唯独批量反提交没有**；且该函数连 `_release_document_push_lines` 也未引入。
- 证据：
  ```python
  # in_order.py:2419-2420（单张反提交，有守卫）
  if _source_has_active_push(id):
      return jsonify({'status': 'error', 'msg': '该入库单存在有效下推单据，不能反提交；请先处理下游单据。'}), 409
  # in_order.py:2647-2649（批量删除，有守卫）
  if _source_has_active_push(order_id):
      skipped.append(f'{order_no}(存在下游单据)')
  # in_order.py:2908-2946（批量反提交：import 列表无 _source_has_active_push，函数内 0 次调用）
  ```
  全文件 `_source_has_active_push` 出现位置仅 2349 / 2419 / 2647 三处，均在批量反提交之外。
- 影响：对`auto_push_requisition=True` 的采购入库单（完成时自动生成并完成一张领料单，in_order.py:1958-2011），批量反提交会把它拉回 pending，而下游领料单仍为 completed 且库存已扣；此后再次完成会被 `request_id='auto-requisition-{id}'` 的幂等校验拦下（in_order.py:1962-1968）→ **单据永久卡死**，只能人工改库。属于"下游已领料、上游回草稿"的账/流程脱钩。
- 根因：R6 同根因消费点漏排查——`BUG-2026-08-16-020` 类修复只补了单张路径。
- 建议：在 batch_revert_in_order 循环内、加锁前补 `if _source_has_active_push(order_id): skipped.append(...); continue`（与 batch_delete 同构）；补测试。
- 确认程度：**已确认**（静态可断定守卫缺失；实际触发需存在 auto_push 单据）
- 关联规则：R6、§〇 状态权威表

### [P1] 批量完成出库单缺仓库停用复核，且 0 成功仍回成功契约
- 位置：`app/routes/out_order.py:1396-1523`（batch_complete_out_order）；对照 `out_order.py:1151-1163` 与 `in_order.py:2886-2901`
- 现象：单张 `complete_out_order` 对非"销售出库"类型会 `assert_warehouse_active(order.warehouse, allow_empty=False)`；批量入口只对"销售出库"调 `validate_sales_outbound_warehouse`（L1458-1463），**领料单/其他出库/采购退货出库 三种 business_type 完全不校验仓库是否停用**。同时批量入口无论如何都返回 `status=success`（L1520-1523），而同类问题已在 in_order 修过（`BUG-2026-09-23-004`：completed==0 → 400 error）。
- 证据：
  ```python
  # out_order.py:1151-1156（单张，有）
  if order.business_type != '销售出库':
      wh_ok, wh_err = assert_warehouse_active(order.warehouse, allow_empty=False)
  # out_order.py:1457-1468（批量，只有销售出库分支 + 库位必填）
  if order.business_type == '销售出库':
      wh_ok, wh_err = validate_sales_outbound_warehouse(order)
  ...
  msg = f'批量审核完成，共审核 {completed} 张领料单'      # 1520
  return jsonify({'status': 'success', 'msg': msg, 'completed': completed})   # 1523，无 completed==0 分支
  ```
  （grep `assert_warehouse_active` 在 out_order.py 仅 4 处命中：2 处 import 行 + L1153 唯一调用 + 注释）
- 影响：(1) 草稿保存后仓库被停用 → 批量完成仍把库存记入停用仓（R2/PUR-AUDIT-003 同类；停用仓不进"新单据"口径，账面出现看不到的库存）；(2) 全部被跳过时前端收到绿色成功弹窗 + reload，用户以为批量已生效（in_order 已修的同款体验/数据一致性缺陷在 out_order 复发）。
- 根因：R6 同根因跨模块漏排查；批量入口复制自旧版，未跟随单张/兄弟模块修复。
- 建议：批量循环内对非销售出库补 `assert_warehouse_active` 并 skip+rollback；结尾补 `if completed == 0: return jsonify({...status:'error', completed:0}), 400`（照抄 in_order.py:2886-2901）。
- 确认程度：**已确认**
- 关联规则：R2、R6、AGENTS §二（仓库必填/有效）

### [P1] 委外快速发料存在两套实现，旧 API 无写锁/无校验/库位键错误
- 位置：`app/app.py:7627-7754`（`POST /api/subcontract/quick_issue`，旧）vs `app/routes/subcontract.py:308-402`（`POST /subcontract/<id>/issue`，新）
- 现象：同一业务动作两套代码并存且门禁不对等。旧实现：**不加 `_acquire_order_write_lock`、无幂等键、无 `assert_warehouse_active`、无库位入参**，且判空逻辑是 `if not material_id or quantity <= 0: continue`（静默跳过非法行）；新实现有写锁、`assert_warehouse_active`、`apply_stock_delta` 单入口、开启库位时库位必填。
- 证据：
  ```python
  # app.py:7664-7668（旧：静默 continue；quantity 为字符串时 '5' <= 0 抛 TypeError → 500）
  for item in items:
      material_id = item.get('material_id')
      quantity = item.get('quantity', 0)
      if not material_id or quantity <= 0:
          continue
  # app.py:7735-7738（旧：issue.location 从未被赋值，库位键退化为仓库名）
  if use_location and (issue.location or issue.warehouse):
      loc_ok, loc_err = update_location_inventory(
          material, issue.location or issue.warehouse, -(quantity or 0), ...)
  # routes/subcontract.py:358-361（新：写锁 + 状态复核）
  order, ok = _acquire_order_write_lock(
      SubcontractOrder, id, ('pending', 'processing', 'completed'))
  ```
  消费面：`grep -r "api/subcontract/quick_issue"` 仅命中测试（`tests/test_bug_2026_09_20_008_*.py`、`tests/test_p0_1_subcontract_quick_issue_warehouse_stock.py`），**前端模板/JS 与 Android 端零引用**——即已无消费方的可写库存遗留接口。
- 影响：(1) 若被脚本/旧 APK 调用，同一委外单可被重复发料（无锁+无幂等，每次 POST 新建一张 completed 发料单并再扣一次库存）→ 库存少计；(2) 库位管理一旦开启（当前默认 '0' 未开启，属**潜在**缺陷），该路径把仓库名当库位名写 ②库位账，造成 ①=Σ② 恒等式破裂（BUG-2026-08-20-008 / BUG-2026-08-16-002 同型）；(3) 与新建模重复维护，改一处漏一处。
- 根因：路由拆分时只把新版搬进 `routes/`，旧 API 未删除也未收敛到同一实现。
- 建议：删除 `app.py:7627-7815` 两个旧端点（连同其测试改为打新端点），或将其改为 `return quick_issue_subcontract(id)` 薄委托；上线前 grep 确认无外部调用。
- 确认程度：**已确认**（重复实现与缺锁/缺库位为静态事实）；"并发重复扣料"标 **高度可疑**（需运行验证）
- 关联规则：A10 精神（app.py 不再承载新路由）、R6、§二、INVENTORY_TRUTH 三账

### [P2] 委外批量状态接口可任意直改状态（含 cancelled），无校验/无审计/无锁
- 位置：`app/routes/subcontract.py:755-788`
- 现象：`POST /subcontract/batch_update_status` 接受 `ids[] + status`，白名单 `{'pending','processing','completed','cancelled'}` 直接 `order.status = status`；不校验当前状态、不校验是否存在未完成发料/收料、不用写锁、**不写 `log_operation`/`log_audit`**、ids 无上限。
- 证据：
  ```python
  if status not in {'pending', 'processing', 'completed', 'cancelled'}:   # 773
      return api_error('目标状态不合法')
  for oid in ids:
      order = db.session.get(SubcontractOrder, oid)
      if order:
          order.status = status          # 780：无任何前置校验
          updated += 1
  ```
- 影响：(1) 绕过 `complete_subcontract_order`/`revert_subcontract_order` 的状态语义（revert 时还做发料/收料回退推导，L982），把已完成单改回 pending 会让"主单 pending + 发料单 completed"并存；(2) **全系统唯一能写 `cancelled` 的入口**（其余 cancelled 只出现在筛选/标签），意味着委外取消无审计留痕；(3) 前端无调用方（grep 仅 `tests/test_finance_role_readonly.py` 命中）= 死能力但线上可调。
- 根因：批量工具的"通用状态设置"当成业务接口暴露；缺"状态机只允许相邻跃迁"的统一校验层。
- 建议：删除该路由；若确需批量，改为"仅允许 pending→cancelled"的显式语义 + `log_audit` + 写锁，并校验不存在 completed 发料/收料单。
- 确认程度：**已确认**
- 关联规则：A8（新写接口须 pydantic 校验——本路由无）、§〇 状态权威表、R6

### [P2] 中文用户可见文案出现 16 处乱码（????）
- 位置：`app/routes/subcontract.py:1260`、`app/routes/subcontract.py:1340`；`app/app.py:16177`、`16209`、`16217`、`16313`、`16355-16361`、`16370`、`17658`、`17664`、`17672`、`17674`、`17679`
- 现象：拆分/转码过程中中文字符被替换为字面 `?`，直接出现在前端提示或日志里。
- 证据：
  ```python
  # subcontract.py:1340
  'msg': f'?? {material.code} ????????????{current_stock:.2f}????{required_quantity:.2f}'
  # subcontract.py:1260
  return api_error(f'?? {material_code} ????????????{current_stock:.2f}????{required_quantity:.2f}')
  # app.py:17672-17679（库存校验 issues 列表，会渲染到页面）
  issues.append(f'{code} ?????? 0?')
  issues.append(f'{code} ?????? {qty}??? {current_stock}?')
  # app.py:16209  'subtitle': material.name or '????',
  ```
- 影响：委外发料库存不足时用户只看到 `?? 6204 ????????5.00????10.00`，无法判断缺多少/哪个物料（操作员只能凭位置猜）；`app.py:17658-17679` 的库存异常 issues 同样不可读。属可用性缺陷，不涉及数据正确性。
- 根因：文件编码转换失误（GBK→UTF-8 丢字符），且没有 lint 规则拦截"中文字符串里连续多个 ?"。
- 建议：逐行重写这 16 处中文文案；在 `scripts/lint_wms_rules.py` 增加"A15：.py 字符串内连续 ≥4 个 '?' 视为乱码"规则。
- 确认程度：**已确认**（grep `\?\?\?\?` 全仓 16 处，均为上述点位）
- 关联规则：A6/A7 无关；属工程质量项

### [P2] 数量/单价精度：系统设置是死代码，落库被硬编码 2 位，已完成单改量未归一
- 位置：`app/app.py:4336-4340`（`quantity_decimal_places`=`price_decimal_places` 定义，全仓**无任何其它引用**）、`app/utils.py:47`+`53-56`（`round_to_2_decimals` 固定 0.01、`normalize_stock_quantity` 固定 2 位）、`app/routes/in_order.py:1091/1122`（新增按 2 位舍入）vs `in_order.py:2182/2251`（已完成单改量 `float()` 不舍入）
- 现象：系统设置页暴露"数量小数位(默认3)/单价小数位(默认4)"，但代码从不读取；所有库存写入经 `normalize_stock_quantity` 强制 2 位；而"已完成入库单改明细"路径把用户输入原样 `float()` 存进 `item.quantity`，导致**单据明细数量（1.2345）与库存变动（1.23）不相等**。
- 证据：
  ```python
  # utils.py:47 / 55-56
  return float(Decimal(str(fval)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
  normalized = round_to_2_decimals(value)          # ← 固定 2 位，配置无效
  # in_order.py:1091（新增明细，有舍入）
  quantity = round_to_2_decimals(item_data.get('quantity', 0))
  # in_order.py:2182（已完成单新增明细，无舍入）/ 2251（改量，无舍入）
  quantity = float(item_data['quantity'])
  new_qty = float(item_data['quantity'])
  ```
- 影响：(1) 配置项是"假旋钮"——用户按 3 位小数管理（如按 kg/米计量物料）时，库存每次写入被静默截到 2 位，逐单累积 0.005 级误差，长期形成账实不符；(2) 已完成单改量后 `item.quantity` 与库存流水数量不一致，单据/台账核对时对不上（R2「汇总=明细」口径）。(3) 单价同样被 47 处 `round_to_2_decimals` 压到 2 位（`grep 'price = round_to_2_decimals'` 47 处），低价物料（如 0.005 元/件）单价被放大 100%。
- 根因：`quantity_decimal_places()`/`price_decimal_places()` 只接进设置页，没有接进 `round_to_2_decimals` 家族；新增/修改两条路径舍入口径不一致（R6 同根因两消费点）。
- 建议：在 `utils` 增加 `quantize_quantity()/quantize_price()` 读系统设置（缓存），替换库存与单价的硬编码 2 位；`update_completed_in_order` 的 `float()` 改为同一量化函数；若确定只用 2 位，则删除两个设置项避免误导。
- 确认程度：**已确认**（配置零引用为 grep 事实；精度差异为静态可断定）
- 关联规则：R2、R6、A11 精神

### [P2] 40 处把底层异常原文回传给客户端
- 位置（代表）：`app/routes/batch_import.py:277,296,615,634`；`app/routes/material.py:773,1095,1452,1473`；`app/routes/in_order.py:2612`；`app/routes/transfer.py:968`；`app/routes/purchase_request.py:731`；`app/routes/check.py:1150`；`app/routes/adjustment.py:819`；`app/routes/after_sale_out.py:829`；`app/routes/subcontract.py:946,1658,2342`；`app/routes/purchase_order.py:374`；`app/routes/requisition.py:971`；`app/routes/print_queue.py:569,694,716,792,836,859,881`；`app/routes/print_routing.py:366,392,468,493,539,562`（共 40 处，正则 `msg.*\{str\(e\)\}|\{e\}` 全量扫描）
- 现象：`except Exception as e` 后直接 `api_error(f'删除失败：{str(e)}')` / `jsonify({'msg': f'导入失败：{e}'})`，把异常文本原样返回前端。
- 证据：
  ```python
  # purchase_request.py:728-731
  except Exception as e:
      db.session.rollback()
      app.logger.error(f'删除采购申请单失败: {str(e)}')
      return api_error(f'删除失败：{str(e)}')
  # batch_import.py:296
  return api_error(f'领料单导入失败：{str(e)}')
  ```
- 影响：把 SQLAlchemy/SQLite 的英文技术细节（表名、约束名、路径）暴露给任意登录用户；与 `app.py:4590-4614` 全局 errorhandler 已确立的"只回中文通用提示、细节进日志"口径自相矛盾；用户拿到的错误信息无法行动（"UNIQUE constraint failed: purchase_request.request_no"）。
- 根因：历史代码逐点 `str(e)` 拼接，未收敛到统一 `api_error` 契约（app.py:219 只做 jsonify，不含脱敏）。
- 建议：把 40 处统一改为固定中文提示 + `app.logger.exception`（保留排障细节在日志）；仅在`ValueError`（业务校验异常）分支允许回传业务文案。
- 确认程度：**已确认**
- 关联规则：A6（禁 print 的同类"日志卫生"精神）、错误处理规范

### [P2] 打印入队接口 CSRF 豁免但接受 Web 会话鉴权
- 位置：`app/routes/print_queue.py:549-564`
- 现象：`@app.route('/print_queue/jobs', methods=['POST'])` + `@csrf.exempt`，鉴权是"Web 会话 或 Bearer Token"二选一。
- 证据：
  ```python
  @app.route('/print_queue/jobs', methods=['POST'])
  @csrf.exempt
  def print_queue_create_job():
      user = current_user if current_user.is_authenticated else get_bearer_user()   # 560
      if user is None: ... 401
      if user.role != 'admin' and user.role != 'warehouse': ... 403
  ```
  对比：native_api 的 32 个 `@csrf.exempt` 端点里，写端点走 `api_role_required` → `get_bearer_user()`（Bearer-only，app.py:6980-6994，无会话回退，故不受 CSRF 影响）；例外是刻意设计的匿名端点 `/api/csrf_refresh`(:881)、`/api/login`(:899)、`/api/mobile/crash_report`(:3047，只追加写 logs/、不入业务库) 与只读的 `/api/mobile/profile`(:3026)。
- 影响：任意第三方站点可构造跨站表单，借已登录的 admin/warehouse Cookie 向打印队列塞入打印任务（打印垃圾/耗材浪费/打断生产打印队列）。不能改业务数据，故 P2。
- 根因：豁免 CSRF 的理由（移动端 Bearer 无会话）与鉴权实现的会话回退不一致。
- 建议：改为双分支——仅在携带 Bearer Token 时豁免 CSRF（用 `csrf.exempt` 的独立端点或校验 `Authorization` 头存在才放行），Web 会话分支强制 CSRF token。
- 确认程度：**已确认**
- 关联规则：A2、R4（打印链路）

### [P2] recalculate_order_total 不做金额量化，表头金额带浮点尾差
- 位置：`app/utils.py:250-255`（被 in_order/out_order/transfer/check/adjustment 等十余处调用）
- 现象：`total = sum((item.amount or 0) for item in order.items)` 直接 Python float 累加后赋给 `order.total_amount`，无 `round_to_2_decimals`。
- 证据：
  ```python
  # utils.py:250-255
  def recalculate_order_total(order):
      total = sum((item.amount or 0) for item in order.items)
      order.total_amount = total        # 0.1+0.2 → 0.30000000000000004
      return total
  # 对照：app.py:35165-35169（销售单口径，每步都 round_to_2_decimals）
  order.total_amount = round_to_2_decimals(total_included)
  ```
- 影响：`Document.total_amount` 落库出现 `1234.5600000000001` 形态；报表/导出/打印按 2 位格式化时通常无感，但任何"汇总==明细"（R2 第 3 条）或 `==` 比较（如对账脚本、AI 财务校验）可能因 1e-12 级差异判不等；同一系统内两套金额口径（销售 round、其他不 round）。
- 根因：金额量化只在部分路径手工调用。
- 建议：`recalculate_order_total` 返回前统一 `round_to_2_decimals`（与 app.py:35165 对齐）。
- 确认程度：**已确认**
- 关联规则：R2

### [P2] 前端"可用库存"取全局总账，跨仓误导
- 位置：`app/utils.py:164-186`（`serialize_material`，L184 `'stock': float(material.stock or 0)`）；消费点如 `app/routes/after_sale_out.py:155`（新增页 materials）、`app/routes/after_sale_out.py:189`（编辑页 initial_items[`stock`]）
- 现象：所有 add/edit 页面通过 `serialize_material` 把**全局** `Material.stock` 交给前端做"库存"展示/前端预校验；而完成时后端按单据仓库做严格校验。
- 证据：
  ```python
  # utils.py:183-185
  'price': float(material.price or 0),
  'stock': float(material.stock or 0),     # ← 全局总账，非单据仓库口径
  # after_sale_out.py:189
  'stock': float(material.stock or 0) if material else 0,
  ```
- 影响：4 仓环境下，用户为 A 仓做售后出库时看到的是 A+B+C+D 合计库存，前端可能放行任意数量；提交时才被后端仓库级校验拒绝（`after_sale_out.py:428-442` 已按仓库口径），造成"填得进、提交不了"的体验断层；若绕过前端（脚本/API）也不影响数据正确性。属 R2/A11 的"前端消费点"残留。
- 根因：`serialize_material` 是档案序列化函数，被复用于"库存上下文"场景。
- 建议：单据页改为新增 `serialize_material_with_stock(material, warehouse)`（内部用 `get_warehouse_stock_quantities`）；或前端不再展示库存，只由后端在完成时提示。
- 确认程度：**已确认**（代码事实）；具体哪些页面受影响需逐个模板核对，本次未全量列举 → 影响面标 `高度可疑`
- 关联规则：A11、R2

### [P2] 批量操作 select_all 绕过 100 条上限，批量反提交完全无上限
- 位置：`app/routes/in_order.py:2725-2741`（batch_complete 显式 ids 限 100，但 `select_all` 分支无限制）、`app/routes/in_order.py:2917-2927`（batch_revert 两条路径都无 100 条限制）
- 现象：三个批量入口对"显式勾选"有 100 条上限与 400，但 `select_all=True` 时直接 `.all()` 全表捞取并在同一请求内逐单加锁 + 逐单 commit；batch_revert 连显式 ids 也不限。
- 证据：
  ```python
  # in_order.py:2730-2741
  if select_all:
      query = InOrder.query
      if status_filter:
          query = query.filter(InOrder.status == status_filter)
      orders = query.options(joinedload(InOrder.items)).all()      # 无 limit
  else:
      ...
      if len(ids) > 100:
          return jsonify({'status': 'error', 'msg': '单次批量操作不能超过 100 条，请分批处理'}), 400
  ```
- 影响：全量完成/反审 N 千张单 → 请求内 N 次 `BEGIN IMMEDIATE`（SQLite 全局写锁）+ N 次 commit，HTTP 超时/被 waitress 掐断后**前 K 张已提交、其余未执行**，前端只看到超时；用户重试时已完成的会被跳过（不重复扣账，安全），但操作结果不可知，需要人工核对。属性能悬崖 + 操作原子性缺失。
- 根因：`select_all` 是为"全选当前筛选"设计的交互捷径，未纳入批量上限与异步化设计（R1 同类：把默认/全量当成业务上限）。
- 建议：`select_all` 也强制 `limit(100)`（或改为前端分页全选=显式传 ids）；批量接口改为任务化（后台 job + 进度查询）。
- 确认程度：**已确认**（代码事实），实际规模未验证 → 性能影响标 `高度可疑`
- 关联规则：R1、R4（降级兜底精神）

### [P3] AGENTS.md「单据状态权威表」与实现漂移（含 2 处死态、2 处"无反提交"误标）
- 位置：`AGENTS.md:44-56`；实现：`transfer.py:559`、`requisition.py:661`、`transfer.py:39`、`adjustment.py:46`、`purchase_order.py:941`、`app.py:6225`、`sales.py:1258`、`app.py:35106-35124`、`subcontract.py:773`
- 现象：该表自称"唯一权威来源"，但与代码至少 6 处不一致：
  1. `AGENTS.md:46` 调拨单「反提交 —」→ 实际存在 `revert_transfer`（transfer.py:557-625）；
  2. `AGENTS.md:51` 工单领料「反提交 —」→ 实际存在 `revert_requisition`（requisition.py:658-707）；
  3. `AGENTS.md:46/47` 调拨/调整单含 `cancelled` → **全仓无任何代码写入** cancelled（只有列表筛选 `transfer.py:39`、`adjustment.py:46` 与模板下拉）；
  4. `AGENTS.md:54` 采购订单 pending/partial/completed → 另有 `closed`（purchase_order.py:930-950，app.py:6225 的早退）；
  5. `AGENTS.md:55` 销售订单 draft/confirmed → 另有 `closed`（app.py:35179）与 `cancelled`（sales.py:1258）；
  6. `AGENTS.md:56` 委外订单 pending/processing/completed → 另有 `cancelled`（subcontract.py:773 唯一写入口）。
  另：`AGENTS.md:47` 引用的 `adjustment.py:505`、`AGENTS.md:48` 引用的 `check.py:634` 行号已偏移（现分别 503 / 622+635-639）。
- 证据：`grep "'cancelled'"` 在 app/ 命中的 135 处中，**没有一处对 TransferOrder/AdjustmentOrder 赋值**（仅 `_get_order_list_filters` 与模板 option）。
- 影响：维护者按表判断"调拨/领料不能反提交"会做出错误设计；UI 上「已取消」筛选永远为空（`transfer.html:43`、`adjustment.html:47`）属可见的死选项。
- 根因：表以 `models/documents.py` 的 status 列注释为源（注释本身就写了 cancelled），而注释/派生逻辑未随实现收敛；表未随拆分后的实际路由回填。
- 建议：修正 AGENTS.md:44-56 六行 + 两处行号；或补齐 Transfer/Adjustment 的 cancel 路由（若产品确实需要）并删除不用的注释枚举；同时删掉两个模板的死 option。
- 确认程度：**已确认**
- 关联规则：§〇 自身、R6

### [P3] app.py 仍承载 94 条路由（含 2 组死路由），与 A10 的拆分目标背离
- 位置：`app/app.py` 全文（`@app.route` 94 条 / 其中写接口 43 条）；死路由：`app.py:26083-26087`（`/debug/in_order/<order_no>` → `abort(404)`）、`app.py:26757-26759`（`/inventory_check`、`/inventory_check/add`、`/check/add` → `check_legacy_page` 兼容重定向）
- 现象：`app/routes/` 拆分已迁出 611 条路由，但 app.py 仍留 94 条（36k 行文件），其中 AI 域约 70 条、若干个 `/api/material/*`、委外旧 API（见 P1-4）与上述死路由。
- 证据：`grep -c "@app.route"` = 94；路由表见附录统计；`debug_in_order` 函数体仅 `abort(404)`。
- 影响：A10 规则只对"新增行"生效，故不算规则违反；但阅读/审计成本、误判"哪些是活跃入口"的风险仍在（本次就需人工确认 `/api/subcontract/quick_issue` 是否仍被调用）。死路由保留 `/debug/` 前缀的 URL 面（虽有 login_required+abort）属可清理项。
- 根因：拆分按批次推进，AI 域与旧 API 未纳入。
- 建议：删除 3 条死路由；`/api/subcontract/quick_*\' 按 P1-4 收敛；剩余 AI 域路由作为后续拆分批次登记台账。
- 确认程度：**已确认**
- 关联规则：A10（精神）

### [P3] app/routes/ 与 app/templates/ 混入 10 个 .bak 备份文件
- 位置：`app/routes/customer.py.bak_p2b`、`stock_query.py.bak_p1`、`supplier.py.bak_p2b`、`unit_supplier_import.py.bak_p2b`；`app/templates/adjustment.html.bak_f1`、`check.html.bak_f1`、`customer.html.bak_p2c`、`stock_query.html.bak_p1`、`subcontract.html.bak_f1`、`supplier.html.bak_p2c`
- 现象：历史迁移留下的整份源码备份与业务代码同目录。
- 证据：全仓 glob `*.bak*` 命中 10 个文件（见上）。
- 影响：被打包/部署同步带上生产；若被误当模板渲染（Jinja 按 extends 找模板不会命中 .bak，风险低），或参与 grep/审计噪音；`adjustment.html.bak_f1` 等仍是旧版 UI，可能误导后续维护者"改错了文件"。
- 根因：拆分任务收尾未清理。
- 建议：删除 10 个 .bak（历史留在 git 即可）；在 `.gitignore` 增 `*.bak*`。
- 确认程度：**已确认**
- 关联规则：无（工程卫生）

### [P3] log_operation / log_audit 内部 commit：事务中途调用会静默半提交
- 位置：`app/app.py:5118-5145`（`log_audit`，内层 `db.session.commit()` 在 5138）、`app/app.py:7103-7125`（`log_operation`，commit 在 7119）
- 现象：两个"写审计"辅助函数自带 `db.session.add(...) + db.session.commit()`（失败再 rollback），即**任何在业务事务中途调用它们的地方，会把当时未提交的业务改动一起提交**。
- 证据：
  ```python
  # app.py:7117-7122
  db.session.add(log)
  try:
      db.session.commit()        # ← 提交整个 session，不只是 OperationLog
  except Exception as e:
      db.session.rollback()      # ← 失败时回滚整个 session
  ```
  本次已用脚本核对：`app/routes/*.py` 内所有 `log_operation/log_audit` 调用点均在主业务 commit 之后（**0 例违反**）；app.py 内 4 个"日志先于最后一次 commit"的函数逐一人工核对（`_void_check_scan` 27075 先 commit 再 log 27081、`edit_material` 692 先 commit 再 log 698、`batch_delete_in_order` 逐单 commit 后 log）均安全。**当前无实际缺陷**，属"未来隐患"。
- 影响：新增代码只要在事务中途调一次 `log_operation`，就会把半成品业务改动落库且无告警（R4/R8 类二次伤害风险）。
- 根因：审计写入与业务写入共用同一 Session 且不自建事务边界。
- 建议：`log_operation/log_audit` 内改为独立 Session（`db.sessionmaker`）或 `flush` + 由调用方提交；至少在函数 docstring 顶部标注"必须在 commit 之后调用"并加 lint 检查。
- 确认程度：**已确认**（机制）；当前触发点 0 个 → 系统性风险标 `风险提示`
- 关联规则：R4、R8

### [P3] 采购审批存在两套完全重复的实现，且都无并发保护
- 位置：`app/routes/approval.py:76-92`（`/approval/<id>/approve`）与 `app/routes/purchase_request.py:622-634`（`/purchase_request/<id>/approve`）；驳回：`approval.py:98-121` ↔ `purchase_request.py:640-659`
- 现象：审批中心页与采购申请页各自暴露一个"审批通过/驳回"POST 端点，函数体逐行相同（`status != 'pending'` → `status='approved'` → `commit` → `log_operation`），都**没有写锁/条件 UPDATE**，两个入口可同时对同一单据操作。
- 证据：
  ```python
  # approval.py:76-89 与 purchase_request.py:622-631 逐行等价
  request_order = PurchaseRequest.query.get_or_404(id)
  if request_order.status != 'pending':
      return api_error('只有待审批的采购申请单可以审批')
  request_order.status = 'approved'
  db.session.commit()
  ```
- 影响：并发"通过+驳回"两个请求都可能通过 status 检查，后提交者覆盖前者（SQLite 下概率低但非零）；实际后果是审批结果与 `log_operation` 记录不一致（一个单据留下两条互相矛盾的操作日志）。当前单人使用，风险极低。
- 根因：拆分 purchase_request 域时内联复制而非委托（approval.py:77-78 注释自认"内联复现原逻辑"）。
- 建议：approval.py 两路由改为 `return approve_purchase_request(id)` 薄委托；两处统一加 `_acquire_order_write_lock(PurchaseRequest, id, 'pending')`。
- 确认程度：**已确认**（重复与缺锁）；并发后果标 `高度可疑`
- 关联规则：R6、§〇（PurchaseRequest 有审批态）

## ④ 建议优先级路线图（≤10 条）

| # | 动作 | 对应条目 | 预期收益 | 成本 |
|---|---|---|---|---|
| 1 | in_order 两个批量入口补 `update_purchase_order_status` 收尾（照抄 batch_delete_in_order:2685-2695） | P1-1 | 采购执行/待办口径立刻正确；纯派生重算，零数据迁移 | S |
| 2 | batch_revert_in_order 补 `_source_has_active_push` 守卫 + 测试 | P1-2 | 消除"下游已领料、上游回草稿"的卡死路径 | S |
| 3 | batch_complete_out_order 补 `assert_warehouse_active` + `completed==0 → 400` | P1-3 | 消除停用仓入库 + 假成功提示 | S |
| 4 | 删除/收敛 app.py 旧委外 quick_issue & quick_receive（先 grep 确认无外部调用） | P1-4 | 去掉无锁可扣库存的遗留写接口与双实现 | S |
| 5 | 删除 `batch_update_subcontract_status` 或改为"仅 pending→cancelled + 审计 + 写锁" | P2-1 | 关掉任意状态直改/无审计缺口 | S |
| 6 | 16 处乱码重写 + lint 增"连续 '?' 视为乱码"规则 | P2-2 | 一线操作员错误提示可读 | S |
| 7 | 40 处异常详情回传收敛为固定中文提示 | P2-4 | 不泄露内部结构，错误信息可行动 | M |
| 8 | 精度决策：二选一——接 `quantity_decimal_places` 到量化函数，或删除两个假设置项；并把 `update_completed_in_order` 的 `float()` 归一到同一函数 | P2-3 | 消除"配置无效 + 单据数量≠库存变动" | M |
| 9 | 批量接口统一限流（select_all 也限 100）+ 大批量改后台任务化 | P2-8 | 消除长事务超时导致的"部分提交"不可知 | M |
| 10 | 一次性订正 AGENTS.md:44-56 状态权威表（6 行 + 2 行号）+ 删两个模板死 option + 清理 10 个 .bak | P3-1/P3-3 | 权威表重新可信，减少后续误设计 | S |

> 说明：P2-5（CSRF）、P2-6（金额量化）、P2-7（前端库存口径）、P3-4/P3-5 可分批随相关模块修复顺带处理，不需要单独排期。