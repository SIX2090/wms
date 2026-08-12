# WMS FULL 审计问题逐项修复执行提示词

> 用途：将本文件完整交给具备仓库读写、测试、Git commit 和 Git push 权限的 AI 代码代理。该代理必须依据本提示词，逐个修复 WMS FULL 只读审计中已确认的问题。
>
> 执行原则：**一个 atomic action = 一个问题 = 一套针对性测试 = 一次独立 commit = 一次 push 到 `origin/main` = 一次 SHA 一致性核验。** 禁止把多个问题合并为一个提交。
>
> 当前修复范围仅包括本文件第 5 节列出的 5 个 action。不要顺带重构、改样式、修改无关 API、清理历史代码或修复未被确认的问题。

---

## 可直接复制的执行提示词

```text
你是 WMS（仓库管理系统）高级修复代理。请根据“WMS FULL 只读审计报告”逐项修复已确认问题。你必须严格执行本任务书；修复、验证、commit、push 形成闭环后，才能开始下一项。

审计结论中的修复范围：

1. P1-001：移动端库存、告警、首页统计及入/出库单读取接口未强制仓库筛选，可能返回跨仓数据。
2. P1-002：旧版 `/report/inout/print`、`/report/inout/export`、`/report/stock/print` 导出接口绕过仓库必填和过滤规则。
3. P2-001：`verify_ai_agents.py` 仍断言中文化页面中已经不存在的英文 Agent 文案。
4. P2-002：`verify_ai_stage5_ops.py` 仍断言中文化运维看板中已经不存在的英文工具 capability key。
5. P2-003：`verify_ai_business_quality_dashboard.py` 绑定历史显示词“Schema版本”，而页面当前合法显示词为“结构版本”。

# 0. 总原则、权限和禁止事项

1. 每个 action 必须独立可回滚、通过自己的测试、单独 commit、单独 push。禁止批量修复后再统一测试或统一提交。
2. 不得新建、切换、删除或推送任何非 `main` 分支。所有 commit 和 push 必须直接面向 `main`。
3. 不得使用 `git reset --hard`、`git checkout --`、`git clean -f`、`git commit --no-verify`、force push，或任何绕过 hooks/门禁的方式。
4. 不得修改、重置、设置或生成账号密码；不得泄露或写入 API Key、Token、Cookie、数据库密码或真实业务数据。
5. 不得修改数据库中的生产数据；测试必须使用 pytest/验证脚本的隔离数据库或现有测试 fixture。
6. 不得改变 AI 的人工确认边界：AI 只能查询、分析、建议和创建草稿；不得自动提交、审核、完成、反审、作废、删除单据或直接变更库存。
7. 不得把仓库（Warehouse）和库位（Location）混用。仓库始终必填；启用库位管理时库位也必填。
8. 业务 JS 的非 GET 请求必须使用 `WMS.api.get/post/put/delete`，不得新写裸 `fetch` 或 `csrfFetch`。
9. 新增 POST/PUT/DELETE 路由必须使用 Pydantic `BaseModel`；本任务预计不需要新增路由。若确有必要，必须先增加 Pydantic 校验和对应 pytest。
10. 新增或修改业务行为必须有至少一个 pytest 回归测试。测试必须验证实际行为，不得只搜索字符串或只断言实现细节。
11. 任何命令、测试、Git 操作失败都必须停在当前 action，先定位和修复失败原因；不得把失败标记为完成，不得进入下一项。

# 1. 开始前硬门禁

在做任何文件修改前，依次执行并检查：

```bash
pwd
git status --short
git branch --show-current
git log -1 --format='%H %s'
git config --get core.hooksPath
python3 scripts/check_hooks_installed.py
```

必须同时满足以下条件才允许继续：

1. `git branch --show-current` 输出严格等于 `main`。
2. `git status --short` 无输出；若有改动，先停止并向用户列出文件，不能覆盖、暂存或回滚未知改动。
3. `core.hooksPath` 指向 `.githooks`，且 `python3 scripts/check_hooks_installed.py` 通过。
4. 当前本地 `main` 与 `origin/main` 不存在未知偏差。执行：

```bash
git fetch origin main
git log -1 --format='%H' main
git log -1 --format='%H' origin/main
```

如果不一致：只能执行安全的 fast-forward 同步流程并说明原因；不得 rebase、不得强制覆盖、不得切换分支规避问题。若无法安全同步，停止并请求用户处理。

**当前已知阻断：审计执行时所在分支是 `trae/agent-D8mY9R`，不符合 main-only 规则。若仍在非 main 分支，立即停止，不要修改文件，不要切换分支，不要创建分支；报告“需要用户/运行环境将工作区提供为 main 后才能执行修复”。**

确认门禁后，阅读以下文件并将其作为约束来源：

```bash
cat AGENTS.md
cat DEVELOPMENT_RULES.md
cat AI_PERMISSION_MATRIX.md
cat WMS_BUG_BASELINE.md
cat WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md
cat Makefile
```

然后运行基础状态检查：

```bash
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
python3 -m pytest tests/ -q
```

记录已知验证失败。特别注意：本审计确认 `verify_wms_bugs.py` 和 `verify_ai_all.py --level core/full` 存在 3 个验证脚本契约漂移失败，它们正是 action 3 至 5 的修复对象；在对应 action 完成前不得把它们误称为新回归。

# 2. 统一执行闭环

必须对第 5 节每个 action 重复以下流程，严格按顺序执行，完成一个再开始下一个。

## 2.1 发现与范围确认

1. 阅读 action 指定的源文件、现有测试、相关模型、调用方和业务规则。
2. 使用代码搜索确认是否已有等价修复、未提交实现或已有 BUG ID。
3. 若 `WMS_BUG_BASELINE.md` 没有该问题，新增唯一 ID：`BUG-2026-08-12-004` 起按 action 顺序递增。不得重复已存在的 BUG 编号。
4. 只修改本 action 列出的文件或确实必要的紧邻测试/调用文件。扩大范围前先说明原因。

## 2.2 先测试后实现

1. 先新增或扩展回归 pytest，确保旧代码下会失败或能精确揭示缺陷。
2. 运行该测试确认 RED；如果旧代码并未失败，停止，重新检查测试是否真正覆盖缺陷，不得继续写“假测试”。
3. 以最小改动修复问题，不改变无关行为。
4. 再运行测试确认 GREEN。
5. 可使用 stash 做反向验证，但仅允许临时 stash 本 action 修改的文件；验证后必须完整恢复，且 `git status --short` 必须只显示本 action 已知修改。不要 stash 用户已有改动。

## 2.3 验证层级

每个 action 至少运行：

```bash
python3 -m pytest <本 action 专项测试> -q
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
```

并按 action 的“必跑验证”执行。若修改了后端路由、业务模型、库存或报表逻辑，还必须运行：

```bash
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

若修改了 AI 验证脚本、AI 模板或 AI 标识映射，还必须运行：

```bash
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

执行命令必须保留退出码和关键输出。因环境缺依赖而失败时，可仅安装 `app/requirements.txt` 或测试明确声明的依赖到隔离环境；不得修改 requirements/lockfile 以掩盖问题。

## 2.4 Commit 和 push 闭环

每个 action 所有验证通过后：

1. 运行 `git diff --check`，必须通过。
2. 用 `git diff -- <file...>` 复核只包含本 action 变更。
3. `git add` 只能暂存本 action 的源文件、测试文件和 `WMS_BUG_BASELINE.md`；不得 `git add .`。
4. 使用指定 conventional commit message，禁止 `--no-verify`。
5. 执行：

```bash
git commit -m "<指定 message>"
git push origin main
git log -1 --format='%H %s'
git log -1 origin/main --format='%H %s'
```

6. 必须读取实际 push 输出，确认包含 `main -> main` 且远程产生非空新 SHA。
7. 本地 HEAD SHA 与 `origin/main` HEAD SHA 必须完全相同；否则该 action 未完成，不能继续。
8. push 成功后立即在 `WMS_BUG_BASELINE.md` 记录：问题、根因、修复模块、专项验证命令和 commit SHA。注意：基线记录本身必须包含在本 action commit 中，因此先填“commit 待回填”不允许。正确做法是：先提交后获取 SHA，再用仅更新基线的独立提交会破坏“一项一提交”。因此在 commit 前将验证信息写入基线并在“提交”字段写 `本提交`，commit 后通过 `git show --format=%H -s HEAD` 将 SHA 在最终交付报告中说明；除非项目已有稳定的预计算写法，不要为了回填 SHA 额外创建提交。

# 3. 业务不变量

所有 action 都必须保持以下不变量：

1. 仓库和库位是不同层级；仓库始终必填。
2. 未开启库位管理时，仓库未传可使用默认仓库；没有默认仓库则拒绝保存、完成或查询。
3. 启用库位管理时，仓库和库位均必填；缺值不得猜测。
4. 库存查询、出入库报表、库存台账的后端入口无仓库时必须返回空数据或 400，绝不能返回跨仓汇总。
5. 采购订单只是采购入库的可选来源；采购入库允许手工新增、编辑、保存和完成。已关联订单时才保留来源、数量和执行进度。
6. 微信文本或截图送货通知是供应商到货通知，只能引导采购入库/其他入库草稿或人工确认，严禁生成采购申请。
7. 已完成采购入库单必须人工反提交为草稿、准确回退库存后才可删除；详情、列表、批量和后端 API 必须一致。
8. 移动 Bearer API 可以按既有设计 CSRF exempt，但每个读写接口都必须保留有效身份校验；写接口保留角色校验和幂等保护。
9. AI 只创建草稿；工具权限必须在服务端执行时校验；非 admin 不得覆盖 system prompt；管理员调试覆盖必须有长度上限和审计。

# 4. 测试设计要求

1. 新测试应优先放在 `tests/test_bug_2026_08_12_00X_*.py`，使用已有 `tests/conftest.py` 的内存数据库环境。
2. 对仓库隔离行为至少构造两个启用仓库（仓库 A、仓库 B）和两组数据；不能只断言参数是否读取，必须断言返回数据不含另一仓库。
3. 缺仓库情形必须覆盖：有默认仓库时自动使用默认仓；无默认仓库时拒绝或返回空结果，具体行为需和 `AGENTS.md` 保持一致。
4. 对报表导出，不能只断言 HTTP 200；必须读取 xlsx 输出并确认其中不存在另一仓库的单据/物料记录。
5. 对验证脚本修复，测试应锁定“行为/结构契约”，不要把用户可见中文文案绑定为唯一固定字符串。内部 capability key 的验证应在 Python 数据层/上下文中完成，用户可见层只验证经标签过滤器后的安全显示。
6. 测试不得依赖真实网络、生产数据库、真实密钥、文件系统中的历史图片或运行顺序。

# 5. 必须逐项执行的 atomic actions

## Action 1：修复移动端仓库级数据边界

**BUG ID：** `BUG-2026-08-12-004`  
**严重度：** P1  
**目标：** 移动端首页、库存、告警、入库单和出库单读取接口必须要求或解析仓库，并绝不返回跨仓数据。

### 受影响代码

- `app/routes/native_api.py`
  - `mobile_api_dashboard`，约 469-527 行
  - `mobile_api_stock_query`，约 529-581 行
  - `mobile_api_alert_list`，约 583-634 行
  - `mobile_api_in_order_list`，约 636-671 行
  - `mobile_api_in_order_detail`，约 673-690 行
  - `mobile_api_out_order_list`，约 692-728 行
  - `mobile_api_out_order_detail`，约 730-747 行
  - 同一文件内其他移动库存/单据读取端点也要检查，避免遗漏相同绕过路径。
- 现有模型和 helper：`get_default_warehouse()`、`Warehouse`、`InOrder.warehouse`、`OutOrder.warehouse`、仓库级库存/库位库存模型。
- 新增测试：`tests/test_bug_2026_08_12_004_mobile_warehouse_scope.py`。
- 基线：`WMS_BUG_BASELINE.md`。

### 实现要求

1. 在 `native_api.py` 内创建一个私有、可测试、最小化的仓库解析 helper，遵循当前路由的延迟导入风格：
   - 接受 `warehouse_id`、`warehouse_code` 或 `warehouse` 参数。
   - 指定仓库时必须验证仓库存在且 active。
   - 未指定时尝试 `get_default_warehouse()`。
   - 无指定仓库且无默认仓库时，对本规则适用的读取接口返回明确 400，或返回空结果；同类接口必须一致，不得回退跨仓结果。
   - 不依据请求中的用户角色猜测仓库，也不把库位字符串当仓库。
2. `mobile_api_dashboard` 的今日入库、今日出库、待处理入/出库必须按解析后的仓库过滤。库存告警必须基于该仓库的库存维度；如果当前模型只能保存全局 `Material.stock`，不得假装它是仓库库存。应复用项目既有 `LocationInventory` 或仓库库存数据结构，或在无可靠仓库维度数据时返回明确的不可用/空结果，不能跨仓聚合。
3. `mobile_api_stock_query` 和 `mobile_api_alert_list` 必须根据仓库级库存记录查询并返回该仓库存量、预警和金额口径；不能读取无筛选的 `Material.stock` 作为仓库库存。
4. 入/出库列表必须按 `InOrder.warehouse`、`OutOrder.warehouse` 过滤；详情接口必须校验目标单据的仓库等于已解析仓库，否则返回 404 或 403，避免 ID 枚举跨仓读取。
5. 保留 `@web_or_api_required` / Bearer 认证；不要把只读接口改为匿名。
6. 不新增高风险写接口，不改变移动写入接口已有的 `@api_role_required`、`@mobile_api_idempotent` 或 CSRF 策略。

### 必须覆盖的测试

1. 无仓库且无默认仓库：上述读取接口返回 400 或空结果，绝不能返回 A/B 任一仓的数据。
2. 无仓库但有默认仓库 A：接口只返回 A 的数据。
3. 显式仓库 B：库存、告警、入库列表、出库列表和 dashboard 只返回 B 的数据。
4. 请求仓库 A 的入库/出库详情，但 URL ID 属于仓库 B：必须拒绝或不暴露。
5. 无效/停用仓库返回明确错误。
6. 同时运行已有移动端和仓库规则回归：

```bash
python3 -m pytest tests/test_bug_2026_08_12_004_mobile_warehouse_scope.py -q
python3 scripts/verify_opening_stock_multi_warehouse.py
python3 scripts/verify_in_order_state_machine.py
python3 scripts/verify_out_order_state_machine.py
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

### Commit message

```text
fix(mobile): BUG-2026-08-12-004 enforce warehouse scope for mobile inventory APIs
```

完成并 push 后才开始 Action 2。

---

## Action 2：修复旧版报表导出绕过仓库过滤

**BUG ID：** `BUG-2026-08-12-005`  
**严重度：** P1  
**目标：** 旧版出入库与库存导出接口必须复用仓库解析和过滤规则；无仓库不可导出跨仓数据。

### 受影响代码

- `app/routes/report.py`
  - `report_inout_print`，约 225-279 行
  - `report_inout_export`，约 281-284 行
  - `report_stock_print`，约 286 行起
- `app/templates/stock_query.html` 中 `/report/stock/print` 的旧直达链接。
- 优先复用 `app.py` 中已有 `_build_report_filters()`、`_build_report_payload()` 及对应 collector，而不是复制另一套仓库过滤逻辑。
- 新增测试：`tests/test_bug_2026_08_12_005_report_export_warehouse_scope.py`。
- 基线：`WMS_BUG_BASELINE.md`。

### 实现要求

1. 所有旧导出入口必须读取并验证 `warehouse_id`，使用既有默认仓库语义：未传时仅可使用 active 默认仓；没有默认仓则 400 或空导出，绝不导出全仓。
2. `/report/inout/print` 与 `/report/inout/export` 必须按仓库过滤入库与出库；两个 URL 的结果完全一致。
3. `/report/stock/print` 必须导出指定仓库的库存，不得 `Material.query.all()` 返回全局/跨仓库存。
4. 优先将旧导出入口委托给已有报表 filters/builders；不要在旧路由另写未覆盖的新查询分支。
5. 更新 `stock_query.html` 旧链接，使其携带当前 `filters.warehouse_id`；如果该旧接口不再应保留，可将入口改为统一新版报表导出，但不得留下绕过路径。
6. 保持导出文件名和基本列结构的兼容性；若为正确仓库口径必须调整字段，说明理由并添加测试。
7. 禁止将 `warehouse_id` 当作未校验字符串拼接进 SQL；使用 ORM/既有 helper。

### 必须覆盖的测试

构造仓库 A 和 B，各自有不同入库、出库、库存记录：

1. 无 `warehouse_id` 且无默认仓：三个导出入口返回 400 或无业务数据。
2. 指定仓库 A：xlsx 中仅包含 A 的记录，不出现 B 的订单号、物料或金额。
3. 指定仓库 B：同理。
4. `/report/inout/print` 与 `/report/inout/export` 的数据范围一致。
5. `stock_query.html` 导出链接携带仓库参数或转向统一安全入口。
6. 必跑：

```bash
python3 -m pytest tests/test_bug_2026_08_12_005_report_export_warehouse_scope.py -q
python3 -m pytest tests/verify_bug_2026_08_02_018_report.py -q
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

### Commit message

```text
fix(report): BUG-2026-08-12-005 scope legacy exports to selected warehouse
```

完成并 push 后才开始 Action 3。

---

## Action 3：修正 AI Agent 页面验证脚本的中文化契约

**BUG ID：** `BUG-2026-08-12-006`  
**严重度：** P2  
**目标：** `verify_ai_agents.py` 应验证受控 Agent 任务、步骤和审计链路真实存在，而不是要求中文页面显示历史英文文案。

### 受影响代码

- `scripts/verify_ai_agents.py`，当前约 76-83 行。
- 仅在确有必要时读取，不修改：`app/templates/ai_agent_task_detail.html`、`app/app.py` 中 `ai_agent_text`/`ai_agent_label` 映射。
- 基线：`WMS_BUG_BASELINE.md`。

### 实现要求

1. 不回退用户页面为英文，不删除 `ai_agent_text` 或 `ai_agent_label`。
2. 将以下旧断言：

```python
assert 'Stock risk scan' in warehouse_detail.get_data(as_text=True)
assert 'Low-stock replenishment scan' in purchase_html
```

改为验证稳定行为契约，至少包括：

- Agent 详情页成功渲染。
- 页面存在步骤表或步骤记录的稳定结构。
- `AIAgentStep` 数据库中对应任务具有至少 4 个步骤。
- warehouse patrol 和 purchase followup 均保留各自预期的 tool/risk/status/草稿步骤约束。
- 模板仍通过 `ai_agent_text` / `ai_agent_label` 过滤器安全渲染用户可见内容，或响应 HTML 包含与当前中文映射一致的可见文本。

3. 不要把内部英文名称当成用户可见 HTML 的固定断言。若需验证内部 key，直接查询模型字段或 Python 数据，而不是搜索渲染 HTML。
4. 测试脚本必须仍能发现下列回归：Agent 未创建任务、未创建步骤、草稿步骤丢失、详情页未授权或无法访问。

### 必须验证

```bash
python3 scripts/verify_ai_agents.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

并反向确认：暂时恢复旧断言或破坏步骤创建逻辑时，脚本应失败；恢复后必须通过。

### Commit message

```text
test(ai): BUG-2026-08-12-006 align agent verification with localized UI
```

完成并 push 后才开始 Action 4。

---

## Action 4：修正 AI 运维看板验证脚本的内部 key/UI 文案混淆

**BUG ID：** `BUG-2026-08-12-007`  
**严重度：** P2  
**目标：** `verify_ai_stage5_ops.py` 必须在数据层验证 `warehouse_insights`，在显示层验证中文化工具标签；不得把内部 capability key 强行断言为用户可见 HTML 文本。

### 受影响代码

- `scripts/verify_ai_stage5_ops.py`，当前约 82-87 行。
- 仅供参考：`app/templates/ai_ops_dashboard.html` 的 `metrics_7d.tool_rows` 和 `ai_agent_label('tool')` 渲染；`app/ai/policies.py`、工具注册表。
- 基线：`WMS_BUG_BASELINE.md`。

### 实现要求

1. 不改回英文 UI，不移除 `ai_agent_label('tool')`。
2. 将：

```python
assert 'warehouse_insights' in ops_html
```

替换为双层验证：

- `AIToolCall` / metrics 聚合数据确实包含 capability/tool key `warehouse_insights`；
- 运维 HTML 确实渲染工具调用区域并使用当前中文标签过滤器，或包含由该过滤器生成的中文标签。

3. 保留 `verify-model` 的运行模型展示检查，但确认它验证的是安全脱敏后的模型标识而不是 API Key/endpoint。
4. 保持原有：admin 能访问运维页、warehouse 被拒绝、全局开关/草稿开关/agent 开关/灰度/本地降级均生效的检查。
5. 不能降低测试强度为“页面返回 200 即通过”。

### 必须验证

```bash
python3 scripts/verify_ai_stage5_ops.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_ai_rollout_control.py
python3 scripts/verify_ai_launch_acceptance.py
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

### Commit message

```text
test(ai): BUG-2026-08-12-007 verify ops metrics separately from localized labels
```

完成并 push 后才开始 Action 5。

---

## Action 5：修正 AI 业务质量看板的标签脆弱断言

**BUG ID：** `BUG-2026-08-12-008`  
**严重度：** P2  
**目标：** `verify_ai_business_quality_dashboard.py` 应验证 `schema_version` 维度及本地化标签映射存在，不应把历史显示词“Schema版本”当作唯一正确结果。

### 受影响代码

- `scripts/verify_ai_business_quality_dashboard.py`，当前失败在约 128 行。
- 只读参考：`app/templates/ai_business_quality.html` 约 271-278 行，当前映射为：

```javascript
'prompt_hash': '提示词',
'schema_version': '结构版本'
```

- 基线：`WMS_BUG_BASELINE.md`。

### 实现要求

1. 不将页面由“结构版本”改回“Schema版本”，因为当前中文化实现合法且浏览器 E2E 已通过。
2. 替换脆弱字符串断言，验证：

- JavaScript 映射中存在 `schema_version` key；
- key 对应一个非空中文显示标签；
- 维度表渲染函数确实使用该映射；
- 过滤器/API 数据的 `schema_version` 字段仍能从筛选条件、快照或维度分组正确传递。

3. 保持脚本可捕获：`schema_version` 被删除、映射为空、维度表未渲染、筛选参数被遗漏等真实回归。
4. 不要以单一自然语言文案判断功能正确性。

### 必须验证

```bash
python3 scripts/verify_ai_business_quality_dashboard.py
python3 scripts/verify_ai_business_quality.py
python3 scripts/verify_ai_browser_e2e.py
python3 scripts/verify_ai_all.py --level core
python3 scripts/verify_wms_bugs.py
python3 -m pytest tests/ -q
```

### Commit message

```text
test(ai): BUG-2026-08-12-008 make quality dashboard label assertion localization-safe
```

完成并 push 后执行第 6 节最终验收。

# 6. 全部 action 完成后的最终验收

只有 Action 1 至 Action 5 均完成独立 commit + push 且本地/远程 SHA 一致，才可运行最终验证：

```bash
python3 scripts/check_hooks_installed.py
python3 scripts/lint_wms_rules.py
python3 scripts/lint_no_raw_post_fetch.py
python3 scripts/verify_wms_bugs.py
python3 scripts/verify_ai_all.py --level full
python3 -m pytest tests/ -q
git diff --check
git status --short
git log -1 --format='%H %s'
git log -1 origin/main --format='%H %s'
```

完成标准：

1. lint 两项通过。
2. `verify_wms_bugs.py` 不再有 `FAIL`。
3. `verify_ai_all.py --level full` 不再有失败，特别是 `verify_ai_agents.py`、`verify_ai_stage5_ops.py`、`verify_ai_business_quality_dashboard.py`。
4. pytest 全量通过。
5. `git diff --check` 通过，`git status --short` 无输出。
6. 本地 HEAD 与 `origin/main` HEAD 是相同的非空 SHA。
7. 所有 BUG 基线条目已记录，且每一项描述与实际测试、提交和源文件一致。
8. 没有新建分支、没有修改密码、没有执行高风险业务操作、没有泄露密钥。

# 7. 最终交付格式

执行完毕后只输出简洁、事实性的修复报告：

## 修复结果

按 Action 1 至 Action 5 分别列出：

- BUG ID、标题、修复的实际文件。
- 关键行为变化。
- 专项测试命令和结果。
- commit SHA、push 输出中确认的 `main -> main`、本地/远端 SHA 一致性。

## 最终验证

列出 lint、BUG 回归、AI full、pytest 的结果；若任何项失败，不得说“完成”，应明确停在对应 action 并说明阻塞原因。

## 安全与流程核验

确认：

- 始终在 `main`；
- 未创建或切换分支；
- 没有 `--no-verify`；
- 未修改账号密码、密钥或生产数据；
- 工作树是否干净。

不要写营销式总结，不要隐藏失败，不要将环境问题误报为代码修复完成。
```

---

## 使用说明

1. 该提示词要求执行环境从一开始就处于 `main`。若环境仍是 `trae/*`、`feature/*` 或其他分支，代码代理必须停止并请求用户提供符合项目规则的 main 工作区。
2. 不要让代码代理为绕过 main-only 规则自行 `git checkout main` 或新建 worktree；这违反本仓库硬规则。应由拥有工作区控制权的用户或执行器提供 main。
3. 修复顺序不可调整：先修仓库数据边界，再修报表导出边界，最后修验证基建。这样可以先消除跨仓业务风险，再恢复 AI 全量验证可信度。
4. Action 1 的仓库级库存实现必须先阅读现有数据模型；如果全局 `Material.stock` 无法表示单仓库存，必须采用现有仓库/库位库存记录作为事实来源，不能用全局总库存伪装为单仓数据。
