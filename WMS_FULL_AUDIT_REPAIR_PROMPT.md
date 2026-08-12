# WMS FULL 审计问题逐项修复执行提示词

> 用途：将本文件“可直接复制的提示词”完整交给具备仓库读写、命令执行、Git 提交和推送权限的 AI 代码代理。
>
> 来源：2026-08-12 WMS FULL 只读审计报告。
>
> 执行策略：**一次只修复一个 atomic action；每项均按“定位 → RED 测试 → 最小修复 → 单项验证 → 反向验证 → 基线登记 → commit → push → SHA 核验”闭环完成，才允许开始下一项。**

---

## 可直接复制的提示词

```text
你是 WMS（仓库管理系统）高级修复代理。请根据下述已确认审计问题逐项修复。你必须严格遵守仓库规则、业务红线和 Git 流程；不得为了让检查通过而删除测试、降低断言、添加无理由豁免、跳过 hook、伪造验证结果或批量合并不相关改动。

# 0. 总目标

依次修复以下 5 个独立 atomic action：

1. AUDIT-2026-08-12-001：移动端库存/告警/单据读取接口缺失仓库必填筛选。
2. AUDIT-2026-08-12-002：旧版报表导出接口绕过仓库必填筛选。
3. AUDIT-2026-08-12-003：AI Agent 页面验证脚本仍断言旧英文文案。
4. AUDIT-2026-08-12-004：AI 运维看板验证脚本仍断言内部英文 capability key。
5. AUDIT-2026-08-12-005：AI 业务质量看板验证脚本仍绑定历史“Schema版本”显示词。

执行顺序不得调整。前两项是 WMS 数据范围和业务规则问题，必须优先。后三项是验证契约漂移问题，必须保持中文用户界面和内部 key 验证同时有效。

# 1. 硬规则与停止条件

## 1.1 分支硬门禁

开始任何编辑、测试、登记、提交前必须依次执行：

```bash
pwd
git status --short
git branch --show-current
git fetch origin main
git log -1 --format='%H %s'
git log origin/main -1 --format='%H %s'
```

- 当前分支必须恰好为 `main`。
- 当前工作树必须干净；若不干净，先列出改动并停止，等待用户决定。
- 若当前分支不是 `main`，**立即停止，不得编辑、不提交、不推送，不得创建、切换、删除任何分支，也不得执行 git reset/rebase/checkout/clean**。仅报告：`BLOCKED: 当前分支不是 main，需要仓库 owner 在当前环境手动切换到 main 后重试。`
- 不得以临时分支、worktree 分支、`trae/*` 分支、patch 文件、cherry-pick 或直接推远程分支的方式规避。
- 每个 atomic action 只允许提交到 `main` 并推送 `origin main`。

## 1.2 工作区与敏感信息

- 修改代码前必须阅读：`AGENTS.md`、`DEVELOPMENT_RULES.md`、`WMS_BUG_BASELINE.md`、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`、`AI_PERMISSION_MATRIX.md`、`Makefile`。
- 首先执行 `bash .githooks/install-hooks.sh`，再执行 `python3 scripts/check_hooks_installed.py`；若 hooks 安装失败，停止，不得 `--no-verify`。
- 不得输出或提交密码、API Key、Bearer Token、Cookie、私钥、连接串凭据或实例目录密钥文件。
- 不得修改用户密码、bootstrap 密码、用户角色、系统密钥、AI API Key 或生产配置。
- 不得执行破坏性数据库操作、清库、生产迁移、真实入库/出库/调拨/审核/完成/反审/作废/删除业务单据。
- 测试只能使用项目已有测试隔离机制、临时内存数据库或测试数据；测试结束不得污染工作树或业务数据库。

## 1.3 WMS 永久业务红线

以下规则来自 `AGENTS.md`，修复不得破坏：

1. 无论库位管理是否开启，仓库始终是必填项。
2. 未开启库位管理时，未选仓库可带入已配置默认仓库；没有默认仓库必须拒绝保存或查询。
3. 开启库位管理时，仓库和库位均必填；无默认值必须拒绝保存或完成。
4. 库存查询、出入库报表、库存台账必须指定仓库；未指定时后端必须返回空结果或 400，绝不能返回跨仓数据。
5. 采购订单是采购入库的可选来源，采购入库允许手工新增、编辑、保存和完成；关联采购订单时才跟踪来源、数量和执行进度。
6. 微信文字或截图送货通知属于供应商送货通知，只能生成采购入库/其他入库草稿或人工确认页，禁止生成采购申请。
7. AI 只能创建或检查草稿；提交、审核、完成、反审、作废、删除、直接改库存必须人工在业务页面执行。
8. 已完成入库单禁止直接删除；必须人工反提交回草稿并准确回退库存后才可删除。
9. AI 未获用户针对具体操作的明确授权，不得修改、设置、重置任何账号密码；系统不得自动生成随机密码。

## 1.4 工程与提交门禁

- 新增或修改业务 JavaScript 的非 GET 请求必须通过 `WMS.api.get/post/put/delete`，不得裸调 `fetch` 或 `csrfFetch`。
- 新增 POST/PUT/DELETE 路由必须使用 Pydantic `BaseModel`；本次原则上不新增写路由。
- 新增业务函数必须有至少一个 pytest 回归测试。
- 不得在 `app/app.py` 新增 `@app.route` 路由；当前路由归属必须维持在 `app/routes/`。
- 禁止 `git commit --no-verify`。
- 每项修复完成后必须在 `WMS_BUG_BASELINE.md` 新增或更新对应 BUG 记录；使用新 BUG ID，格式为 `BUG-2026-08-12-NNN`，不得与已有 001、002、003 重复。建议依次使用 004 至 008。
- 每项修复都必须先完成验证，随后独立 commit、独立 push。未成功 push、或本地 HEAD 和 `origin/main` SHA 不一致时，该项不算完成。

# 2. 每个 atomic action 的固定执行流程

以下流程对每一个 FIX 必须完整重复，不能只在最后一次统一执行。

## 2.1 检查与定位

1. 读取该 FIX 指定的文件和邻近实现、相关测试、相关 BUG 基线记录。
2. 使用项目已有 helper 和模式，不引入不必要的新框架或重复逻辑。
3. 记录修改前的精确文件、函数、路由和行为证据。
4. 确认改动不与已完成 BUG 或现有能力重复；若发现已修复，停止并报告实际证据，不要重复开发。

## 2.2 先 RED，再最小修复

1. 先新增或扩展回归测试，使旧代码失败，覆盖问题的最小可复现路径。
2. 运行该测试并保留 RED 证据。若旧代码意外通过，说明测试无效，必须先改进测试；不能继续实现。
3. 只修改完成当前 FIX 所必需的文件，不做格式化、重命名或无关重构。
4. 测试应覆盖正向行为、拒绝/空结果行为和跨仓隔离边界（适用时）。

## 2.3 验证

至少执行：

```bash
python3 -m pytest <当前 FIX 相关测试文件> -q
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
```

并执行当前 FIX 指定的专项验证。若改动触及 `app/routes/`、模板、API 或 AI，则必须额外执行相关 state machine / AI verification 脚本。

`python3 scripts/verify_wms_bugs.py` 存在历史失败时，必须逐条分析：

- 当前 FIX 是否造成新失败；
- 是否已登记在基线；
- 是否为本轮正要修复的脚本漂移；
- 未明确登记的失败不得称为“既有”。

## 2.4 反向验证

- 对新增的核心回归测试，使用不破坏用户改动的临时方式验证旧逻辑会失败。例如只 stash 当前 FIX 修改的受控文件后运行测试，再立即恢复。
- 若当前环境不适合 stash，使用测试中明确的旧行为断言或最小隔离 fixture 证明测试可以捕捉旧逻辑；不得伪造反向验证。
- 反向验证后再次运行正向测试，必须恢复 GREEN。

## 2.5 基线、commit 与 push

1. 更新 `WMS_BUG_BASELINE.md`：记录问题、影响、修复文件、回归测试、验证命令、反向验证结果。
2. 执行 `git diff --check`、`git status --short`、`git diff -- <当前 FIX 文件>`，确认 staged 文件只包含当前 atomic action。
3. `git add` 只添加当前 FIX 相关文件。
4. 使用指定 conventional commit message 提交。不得混入其它未跟踪文件、提示词文件或用户改动。
5. 读取 pre-commit 输出；若 hook 失败，修复后重新验证，禁止跳过。
6. 推送：

```bash
git push origin main
git log -1 --format='%H %s'
git log origin/main -1 --format='%H %s'
```

7. 只有 `git push` 输出明确出现 `main -> main`，且两条 log 的 SHA 一致且为本次新 SHA 时，才可报告当前 FIX 完成。
8. push 遇到鉴权、非 fast-forward、网络或保护规则失败时，不得报告完成。先停止并报告实际阻塞原因；不得绕过规则。

# 3. FIX-1：移动端库存与单据读取必须按仓库隔离

## 3.1 问题

**审计编号**：AUDIT-2026-08-12-001  
**新 BUG ID**：`BUG-2026-08-12-004`  
**等级**：P1  
**主要文件**：`app/routes/native_api.py`

当前以下移动端接口没有读取、默认、校验或过滤仓库，可能返回跨仓库存、告警、单据或今日统计：

- `/api/mobile/dashboard`
- `/api/mobile/stock/query`
- `/api/mobile/alert/list`
- `/api/mobile/in_order/list`
- `/api/mobile/in_order/<int:order_id>`
- `/api/mobile/out_order/list`
- `/api/mobile/out_order/<int:order_id>`
- `/api/opening_stock` GET

现有证据：

- `mobile_api_dashboard` 仅按日期/status 统计 InOrder/OutOrder；无 warehouse 条件。
- `mobile_api_stock_query` 和 `mobile_api_alert_list` 直接读取全局 `Material.stock`。
- 单据 list/detail 查询仅按 status、keyword 或 ID 读取，未验证仓库。
- `native_api_opening_stock_list` 仅在调用方主动传 `warehouse_id` 时过滤，否则返回跨仓记录。
- 规则要求缺仓库时“带入默认仓库；无默认仓库则 400 或空结果”，不能跨仓返回。

## 3.2 设计限制

1. 不要通过前端隐藏或仅要求 Android 传参解决；后端必须自行解析并强制生效。
2. 复用现有 `get_default_warehouse()`、`Warehouse`、`web_or_api_required`、`api_json_error`、`api_json_success` 和已有模型字段。
3. 不要把 `warehouse` 与 `location` 混用。仓库是物理仓，库位是仓内位置。
4. `Material.stock` 是全局聚合字段，不能伪装成仓库库存。移动端库存查询和告警必须使用已有的仓库维度数据源；先查模型和既有 Web 库存查询实现，优先复用 `LocationInventory` 或已存在的仓库库存汇总 helper。
5. 如果当前模型无法表达某个接口的仓库级库存，返回明确空结果或 400，不得回退到跨仓 `Material.stock`。
6. 对于 web session 与 Bearer Token 都可访问的接口，仓库参数必须由同一服务端解析规则处理。

## 3.3 实施要求

新增一个内部、可测试的仓库解析 helper，名称可自定，职责必须清晰：

输入：`warehouse_id`、`warehouse_code`、`warehouse` 或等价查询参数。  
输出：有效的 active Warehouse，或业务错误响应信息。

行为：

1. 显式提供 ID/名称/编码时，必须验证仓库存在且 active。
2. 未提供时，尝试 `get_default_warehouse()`。
3. 无显式仓库且无默认仓库时，读取接口统一返回 400 或统一空结果；本 FIX 选择一种并在所有所列接口保持一致。推荐 400，错误信息为“请选择仓库”。
4. 列表和详情接口均必须使用已解析仓库过滤；详情 ID 属于另一仓库时返回 404 或 403，所有接口保持一致。
5. dashboard 的入库、出库、待办统计必须按 `InOrder.warehouse`、`OutOrder.warehouse` 过滤。
6. opening stock GET 必须始终按解析后的 `warehouse.id` 过滤。
7. 移动库存查询/告警的数量、低库存判定必须针对该仓库。若现有 `LocationInventory` 数据不足，明确以仓库库存 records 汇总，不得读取全局总库存。
8. 若库位管理关闭但系统仍需要仓库库存，使用项目已有仓库字段/流水口径；不能把所有仓库合并。
9. 保持移动端写接口既有行为；本 FIX 不改入库、出库、盘点、期初建账写流程，除非为复用纯查询 helper 所必需。

## 3.4 测试要求

新增 `tests/test_bug_2026_08_12_004_mobile_warehouse_scope.py`，至少覆盖：

1. 无 warehouse 参数但存在默认仓库时，接口只返回默认仓数据。
2. 无 warehouse 参数且不存在默认仓库时，所列读取接口至少按分类覆盖并返回统一 400/空结果，绝不能跨仓返回。
3. 显式 warehouse_id/warehouse_code 指向仓库 A 时，列表、dashboard 和期初库存不包含仓库 B 数据。
4. 请求仓库 A 的入库/出库详情，但单据属于仓库 B 时，被拒绝（404 或 403，和实现约定一致）。
5. 移动库存查询和告警不再通过 `Material.stock` 返回全局汇总；必须验证仓库级数量/告警口径。
6. 仓库不存在或已停用时返回 400/403，并带用户可读错误。
7. 测试使用测试隔离数据库，不能触碰真实库。

先运行测试 RED；完成实现后运行 GREEN。

## 3.5 验收命令

```bash
python3 -m pytest tests/test_bug_2026_08_12_004_mobile_warehouse_scope.py -q
python3 scripts/verify_opening_stock_multi_warehouse.py
python3 scripts/verify_opening_stock_multi_warehouse.py
python3 scripts/verify_in_order_state_machine.py
python3 scripts/verify_out_order_state_machine.py
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
python3 scripts/verify_wms_bugs.py
```

如果 `verify_wms_bugs.py` 仍显示 AI 相关旧失败，逐条说明并在后续 FIX-3 至 FIX-5 完成后重新运行。

## 3.6 提交

```text
fix(mobile): BUG-2026-08-12-004 enforce warehouse scope for mobile inventory APIs
```

提交内容只能包括：`app/routes/native_api.py`、当前测试文件、`WMS_BUG_BASELINE.md`，以及确有必要的既有仓库库存 helper/模型文件。没有必要不得改 Android 客户端。

# 4. FIX-2：旧版报表导出必须复用仓库过滤

## 4.1 问题

**审计编号**：AUDIT-2026-08-12-002  
**新 BUG ID**：`BUG-2026-08-12-005`  
**等级**：P1  
**主要文件**：`app/routes/report.py`、`app/templates/stock_query.html`

以下旧入口绕过新版 `_build_report_filters()` 和 collectors：

- `/report/inout/print`
- `/report/inout/export`
- `/report/stock/print`

具体问题：

- `report_inout_print()` 只读取日期，直接用 `InOrder.query`、`OutOrder.query` 导出全部仓库。
- `report_stock_print()` 直接 `Material.query...all()` 导出全局库存。
- `stock_query.html` 暴露 `/report/stock/print` 直连入口。
- 新版 `/report/api/<report_type>` 已通过 `_build_report_filters()` 和 collectors 正确带入默认仓或在无仓库时返回空数据；旧入口必须和它一致。

## 4.2 实施要求

1. 优先删除重复查询，复用 `_build_report_filters()` 和已有 report builder / Excel response helper。
2. 无仓库时仅允许：带入 active 默认仓库；无默认仓库返回 400 或空结果。不得导出跨仓文件。
3. 所有旧导出 URL 必须接受与新版报表一致的 `warehouse_id` 参数。
4. 入库/出库导出必须按 `InOrder.warehouse` / `OutOrder.warehouse` 精确过滤。
5. 库存导出必须输出该仓库的库存，不得输出 `Material.stock` 的跨仓总数。
6. 如果旧 `/report/stock/print` 不具备正确仓库库存数据源，改为重定向或委托新版 `inventory` 报表导出，而不是保留错误实现。
7. 模板链接必须携带当前选中 `warehouse_id`，或移除旧直连入口并改为新版报表导出动作。
8. 保持导出文件名、Content-Type、日期筛选和权限规则的兼容性；不引入无认证导出。

## 4.3 测试要求

新增 `tests/test_bug_2026_08_12_005_report_export_warehouse_scope.py`，至少覆盖：

1. 建立仓库 A/B，各自有入库、出库、库存数据。
2. 请求 A 的 `/report/inout/print?warehouse_id=<A>`，解析 xlsx，断言不含 B 单据和数量。
3. 请求 B 时只含 B 数据。
4. 请求 `/report/stock/print?warehouse_id=<A>` 或新版委托等价入口，断言不含 B 库存。
5. 无参数且存在默认仓库时只返回默认仓数据。
6. 无参数且无默认仓库时返回 400/空文件/空数据，且绝不含 A/B 合并数据。
7. `/report/inout/export` 与 print 行为一致。
8. 模板/URL 测试确保库存查询页不会再产生无仓库旧导出链接。

测试必须先 RED，再 GREEN。对 xlsx 使用项目已有 `openpyxl` 读取方式，避免字符串猜测。

## 4.4 验收命令

```bash
python3 -m pytest tests/test_bug_2026_08_12_005_report_export_warehouse_scope.py -q
python3 -m pytest tests/verify_bug_2026_08_02_018_report.py -q
python3 scripts/verify_wms_bugs.py
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
```

## 4.5 提交

```text
fix(report): BUG-2026-08-12-005 scope legacy exports by warehouse
```

提交只包含当前导出修复、回归测试、BUG 基线及必要模板改动。

# 5. FIX-3：AI Agent 验证脚本改为验证中文渲染契约

## 5.1 问题

**审计编号**：AUDIT-2026-08-12-003  
**新 BUG ID**：`BUG-2026-08-12-006`  
**等级**：P2  
**主要文件**：`scripts/verify_ai_agents.py`

当前测试断言渲染 HTML 含旧英文：

```python
assert 'Stock risk scan' in warehouse_detail.get_data(as_text=True)
assert 'Low-stock replenishment scan' in purchase_html
```

当前生产模板通过 `ai_agent_text` 将 Agent 步骤、数据范围和结果渲染为中文。用户界面中文化是已完成的产品要求；验证脚本因此错误失败，导致 `verify_wms_bugs.py`、`verify_ai_all.py --level core/full` 失败。

## 5.2 实施要求

1. 只修改验证脚本和必要的验证测试；不要把用户界面改回英文，不要删除 `ai_agent_text`。
2. 仍需验证“步骤存在且来自可审计 Agent task/step”，不能将断言简化成页面状态码 200。
3. 在应用上下文中直接验证数据库中的 `AIAgentStep` 有预期内部语义（如 tool/risk/status/步骤数），并在 HTML 中验证中文化后的用户可见文本或过滤器输出。
4. 断言必须同时证明：
   - Agent 已创建 warehouse 和 purchase task；
   - 每类 task 至少有 4 步；
   - purchase 有且仅有一条 `risk_level='draft'` 步骤；
   - 任务详情页正常渲染；
   - 用户可见的步骤标签为中文，不泄露旧英文内部文案。
5. 不要硬编码可能变化的完整长句；应验证稳定中文标签、过滤器应用或结构化数据库字段。

## 5.3 测试与验收

该修复本身是测试修复，但必须先让旧脚本 RED、修改后 GREEN：

```bash
python3 scripts/verify_ai_agents.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
```

如果 core 仍有 FIX-4/FIX-5 的失败，仅报告它们，不能掩盖或标记全绿。

## 5.4 提交

```text
test(ai): BUG-2026-08-12-006 align agent verifier with Chinese UI labels
```

提交只包含：`scripts/verify_ai_agents.py`、必要回归测试（如需要）和 `WMS_BUG_BASELINE.md`。

# 6. FIX-4：AI 运维看板验证脚本区分内部 key 与中文显示标签

## 6.1 问题

**审计编号**：AUDIT-2026-08-12-004  
**新 BUG ID**：`BUG-2026-08-12-007`  
**等级**：P2  
**主要文件**：`scripts/verify_ai_stage5_ops.py`

脚本要求渲染 HTML 含 `warehouse_insights`。当前 `ai_ops_dashboard.html` 正确使用：

```jinja2
{{ name|ai_agent_label('tool') }}
```

因此用户可见页面显示中文工具名，内部 capability key 不应作为 UI 文案出现。

## 6.2 实施要求

1. 不得把 `warehouse_insights` 强行渲染回 HTML。
2. 测试必须分开验证两件事：
   - 后端审计数据/`AIToolCall.tool_name` 保存内部 `warehouse_insights`；
   - 模板使用 `ai_agent_label('tool')`，且最终页面显示对应中文标签。
3. 保留现有验证范围：admin 可访问运维页、warehouse 被拒绝、功能开关/降级/灰度对 capability 的影响、全局关闭后 AI 返回管理员关闭提示。
4. 禁止把断言弱化成只检查 `status_code == 200`。

## 6.3 验收命令

```bash
python3 scripts/verify_ai_stage5_ops.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
```

FIX-4 完成后，若仍只有 FIX-5 导致 core/full 失败，明确记录该剩余失败。

## 6.4 提交

```text
test(ai): BUG-2026-08-12-007 verify ops tool key and Chinese label separately
```

提交只包含：`scripts/verify_ai_stage5_ops.py`、必要测试和 `WMS_BUG_BASELINE.md`。

# 7. FIX-5：AI 业务质量看板验证不绑定历史显示词

## 7.1 问题

**审计编号**：AUDIT-2026-08-12-005  
**新 BUG ID**：`BUG-2026-08-12-008`  
**等级**：P2  
**主要文件**：`scripts/verify_ai_business_quality_dashboard.py`、`app/templates/ai_business_quality.html`

验证脚本要求源码含：

```python
'schema_version': 'Schema版本'
```

当前模板已正确提供 `schema_version` 维度，用户可见标签使用“结构版本”。功能存在、浏览器 E2E 通过，失败原因是测试错误绑定某个历史显示文案。

## 7.2 实施要求

1. 保持 `schema_version` 的结构化 key。
2. 保持中文标签；“结构版本”或产品当前约定的等价中文标签均可。
3. 测试必须验证：
   - `schema_version` 映射存在；
   - 映射标签为非空中文用户显示值；
   - `renderDimensionTable` 实际使用该映射；
   - 不接受直接输出原始 `schema_version` 作为用户可见标签。
4. 不得为满足旧测试把页面改回“Schema版本”或混入英文。
5. 保留质量看板既有维度、版本比较、下钻和权限测试。

## 7.3 验收命令

```bash
python3 scripts/verify_ai_business_quality_dashboard.py
python3 scripts/verify_ai_business_quality.py
python3 scripts/verify_ai_browser_e2e.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
```

FIX-5 是当前审计中最后一个已确认 AI 验证漂移项。完成后，`verify_ai_all.py --level core` 和 `verify_wms_bugs.py` 不得再因 AI-AGENTS-001、AI-STAGE5-OPS-001、业务质量看板 Schema 标签断言失败。

## 7.4 提交

```text
test(ai): BUG-2026-08-12-008 make quality dashboard schema label assertion locale-safe
```

提交只包含：`scripts/verify_ai_business_quality_dashboard.py`、必要模板/测试改动和 `WMS_BUG_BASELINE.md`。

# 8. 每项 push 后的强制报告格式

每完成一个 FIX，只输出以下内容后再继续下一项：

```text
FIX-N 状态：已完成 / 阻塞
BUG ID：...
修改文件：...
RED 证据：<旧代码测试失败摘要>
GREEN 证据：<当前专项测试与关键回归命令、退出码>
反向验证：<旧逻辑重新失败、恢复后转绿的证据；若无法执行，说明真实替代证据>
Commit：<完整 SHA> <subject>
Push：<git push 输出中 main -> main 的关键行>
Origin 核验：<local SHA> == <origin/main SHA>
剩余已知失败：...
```

- 若任何步骤失败，状态只能写“阻塞”，保留当前证据并停止；不得跳到下一项。
- 不得写“看起来通过”“应该没问题”或未核对的 SHA。

# 9. 全部 5 项完成后的最终验收

只有 5 个 FIX 都已经独立 commit、独立 push 且 SHA 核验一致，才能执行一次最终验证：

```bash
git status --short
git branch --show-current
git log --oneline -8
python3 scripts/check_hooks_installed.py
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
python3 scripts/verify_wms_bugs.py
python3 scripts/verify_ai_all.py --level core
python3 -m pytest tests/ -q
git diff --check
git status --short
git log -1 --format='%H %s'
git log origin/main -1 --format='%H %s'
```

最终完成条件：

1. 当前分支为 `main`。
2. 工作树干净。
3. lint 两项通过。
4. `verify_wms_bugs.py` 通过；若仍失败，必须逐项是新发现并已登记，不能笼统豁免。
5. `verify_ai_all.py --level core` 通过；不得再有本批三个 AI 验证脚本失败。
6. 全量 pytest 通过。
7. 本地 HEAD 与 `origin/main` HEAD 为同一新 SHA。
8. 每一个 BUG 004 至 008 均已在 `WMS_BUG_BASELINE.md` 记录真实修复、测试、验证和 commit SHA。
9. `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 如受本批 AI 验证基建改动影响，更新对应完成/修复子项；若不需要变更，最终报告明确说明理由。

最终报告必须按以下结构输出：

```markdown
# WMS 审计问题修复结果

## 原子提交
- BUG-2026-08-12-004: <SHA> <结果>
- BUG-2026-08-12-005: <SHA> <结果>
- BUG-2026-08-12-006: <SHA> <结果>
- BUG-2026-08-12-007: <SHA> <结果>
- BUG-2026-08-12-008: <SHA> <结果>

## 验证结果
- hooks:
- lint:
- BUG 静态回归:
- AI core:
- pytest:
- 本地/远程 SHA:

## 业务边界复核
- 移动端仓库隔离:
- 报表仓库过滤:
- AI 中文 UI 与内部 capability key:
- AI 只建草稿和人工确认:

## 未覆盖或阻塞项
- <没有则写“无”>
```

不得在最终报告前宣称整个任务完成。
```

---

## 使用说明

1. 在仓库 owner 已经手动确保当前工作分支为 `main` 且工作树干净后，再将上方完整提示词交给修复型代码代理。
2. 当前环境若显示 `trae/...` 或任何非 `main` 分支，修复代理应按提示词停止，不得擅自切换或创建分支。
3. 每个 FIX 都是单独的 atomic action，因此应产生 5 个独立 commit 与 5 次 `origin/main` push。
4. 这份提示词不授权自动修改业务密码、角色、密钥、生产数据或远程分支保护策略。
