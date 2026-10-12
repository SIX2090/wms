# BUG 基线 · 详情归档 2026-09

> 本分片由 `WMS_BUG_BASELINE.md BUG 详情小节（开工前置门禁段及文件尾部）` 拆出（F4.4（2026-10-13））。
> 新增 BUG 详情小节请写入当月分片，且必须含「生效确认」字段（A13）。

---

### 附：CI-GREEN-GATE-2026-09-18 门禁自身的两个「踩坑记录」

门禁工具 `scripts/check_ci_green.py` 首版有两处判断失误，均已实证修正并被回归测试锁住：

| # | 错误 | 症状 | 修正 |
|---|---|---|---|
| 1 | 用**相对路径**请求 workflow-runs 端点（`/actions/workflows/.github/workflows/ci.yml/runs`） | 三个工作流**一律 HTTP 404**。若把 404 当作"非绿"→ 门禁**永久阻断**、谁都不能开工；若当作"绿"→ **漏报放行**。两者都错 | 只用**文件名**（`os.path.basename`）。实证：完整路径 → 404；文件名 → 200；数字 ID → 200。注意 `/actions/workflows` **列表**接口返回的恰是带目录的 `path` 字段，极易照抄致错 —— 已写进代码注释与 T10/T11 测试 |
| 2 | 首版无 token 时靠匿名请求 | 私有仓库场景下必然 404，但与"工作流真的不存在"无法区分 | 明确 token 获取顺序（env → `/root/.wms_gh_token`），并把「无法确认」统一计为**阻断**而非放行 |

> 教训：**门禁工具自己必须被测试**。"检查工具坏了"有两种失效模式，都比"没有工具"更危险 —— 永久阻断会让人绕过规则，漏报放行会让人在红色基线上开工。故 T10（只传文件名 + basename 行为）、T11（**带 token 的真实端到端可达性**，无 token 时 skip）两道断言专防此类失效。

### BUG-2026-09-25-002（2026-09-25，AI 文档任务三个操作按钮全部指向不存在的路由，点击必然 404）

- **发现方式**：前端逐页核对路由可达性时发现——把模板里每个 `fetch`/`window.open`/
  `location.href` 的 URL 与 `@app.route` 注册表做集合比对，这三个 URL 一个都不存在。
- **位置**：`app/templates/base.html:3502-3528` 的 `handleDocumentTaskAction(taskId, action)`。
- **根因（代码实证）**：三个分支分别是 `view` → `/ai/document/<id>`、
  `create-draft` → `/ai/document/<id>/create-draft`、`retry` →
  `POST /api/ai/document/<id>/retry`。后端真实路由是
  `/ai/document_jobs/<id>`（详情页，`app.py:20547`）与
  `POST /ai/document_jobs/<id>/retry`（`app.py:20593`）——**命名空间是
  `document_jobs` 不是 `document`**，且 `retry` 是**表单式路由**（返回
  `redirect()` + `flash()`），不是 JSON 接口。原代码用 `fetch` 调它，
  即便路径对了也拿不到结果、跳不过去。
- **危害**：AI 文档任务面板的三个按钮**全是死的**。用户点"查看/生成草稿/重试"
  一律 404，且因无错误提示，表现为"点了没反应"。属 P1 功能性失效。
- **状态**：**已修复**（2026-09-25）。
- **修复**：三个分支改指真实路由；`retry` 由 `fetch` 改为**动态构造表单 POST 提交**
  （携带 csrf_token），随响应跟随后端 `redirect` 并由 `flash` 回显结果。
- **同类点一并修复**：`app/templates/sales_order_add.html:1066-1084` 与
  `app/templates/sales_order_edit.html:1020-1032` 的"刷新物料"按钮调用
  `fetch('/api/materials?limit=5000', ...)` —— `/api/materials` **后端不存在**
  （真实为 `/api/material/all`，`app.py:23984`）。更糟的是原 `.then` 里
  `data` 收到的是 404 错误页 HTML，代码却在数据结构不匹配时**静默走完**
  并提示"物料列表已刷新"——**谎报成功**比报错更危险。
  已改为 `/api/material/all` 并显式判断 `r.ok` 与响应结构，
  失败时提示"刷新物料失败"，不再谎报。
- **回归**：随本次 P0 一并纳入 lint 门禁视野（A 系列路由/前端规范）。
  未新增专项测试：三处均为模板内 JS 字符串替换，无业务逻辑，
  且已用"URL 必须在 `@app.route` 注册表中存在"做了集合级复核。
- **生效条件**：模板改动，**生产需重启 WMS 服务（或清模板缓存）生效**（R3）。
- **生效确认**：待确认（需在浏览器打开 AI 文档任务面板点三个按钮、
  以及销售订单新增/编辑页点"刷新物料"，确认无 404 且状态提示正确）。

### BUG-2026-09-25-003（2026-09-25，`start_qa_server.py` 绑定 0.0.0.0 且关闭 CSRF、口令固定为 admin，构成局域网未授权写入面）

- **位置**：`start_qa_server.py:41`（`serve(app, host='0.0.0.0', ...)`）、
  `:16` / `:21`（`WTF_CSRF_ENABLED = False`）、`:10`（`WMS_BOOTSTRAP_PASSWORD = 'admin'`）。
- **根因（代码实证）**：这是给"本机预览"用的 QA 服务，却同时满足三个条件：
  ① 监听 `0.0.0.0`（同网段任意设备可访问）；② 关闭 CSRF 校验；
  ③ bootstrap 口令硬编码为 `admin`。三者叠加 = **同网段任何人可用
  admin/admin 登录，并对全部写接口发起无 CSRF 校验的请求**。
- **危害**：在办公网/车间网运行该脚本时，等同把 WMS 写权限公开。属 P0 安全风险。
- **状态**：**已修复**（2026-09-25）。
- **修复**：绑定收敛为 `127.0.0.1`。QA 服务的用途就是本机预览，
  回环地址足够；若将来确需局域网访问，应改为「显式传入 host 参数 +
  恢复 CSRF + 从环境变量取口令」，而不是默认放开。
- **刻意未改**：未删除 `WTF_CSRF_ENABLED = False`。它是预览脚本为简化
  自动化操作而设，改绑回环后风险面已收敛到本机；同时在改绑处补注说明
  这三个条件为何叠加危险，避免后人单独把 host 改回 0.0.0.0。
- **回归**：`scripts/lint_no_raw_post_fetch.py` 通过；未新增专项测试
  （单行常量修改，断言价值低于维护成本）。
- **生效条件**：脚本改动，**下次启动该脚本时生效**。
- **生效确认**：待确认（启动脚本后从另一台设备访问
  `http://<本机IP>:8080` 应连接被拒，而本机 `http://127.0.0.1:8080` 正常）。

### BUG-2026-09-25-004（2026-09-25，A8/A9/A10/A13/A14 五条 lint 规则在 CI 中从未真正执行）

- **发现方式**：审计 CI 门禁实效性时，逐条比对「规则内部判据」与「CI 运行方式」。
- **根因（代码实证）**：这五条规则内部**统一以 `get_staged_added_lines()` 为判据**
  ——拿不到 staged 行就 `continue` 跳过整个文件
  （A8 `lint_wms_rules.py:838`、A9 `:970`、A10 `:1074`、A13 `:1370`、A14 `:1442`）。
  而 CI 是 `actions/checkout` 的**全新 checkout**，git 索引里**没有任何 staged 变更**
  → 五条规则每次都在**空集**上扫描，**恒为 0 违规**。
- **危害**：这五条规则**形同虚设**，从未拦住过任何东西。具体说：
  新增 `@app.route` 写回 `app.py`（A10）、新增 POST 路由不用 pydantic（A8）、
  新增业务函数无测试（A9）、CI 脚本漏配生产硬门禁 opt-in（A14）
  —— 这四类问题在 CI 里**全部不会亮红**。属 P0 门禁失效。
  A11 此前已被 `--full-a11` 单独修好（`ci.yml:58-59`），但其余五条一直漏着。
- **状态**：**已修复**（2026-09-25）。
- **修复**：新增 `--full` 开关，用**统一机制**切换：把模块级
  `get_staged_added_lines` 替换为 `_all_lines`（返回文件全部行号，
  等价于"整个文件都是新增行"）。之所以不在每条规则上各加一个 flag：
  那样容易漏配，且将来新增同类规则会重犯同一错误 —— 用统一机制后，
  任何新写的"以 `get_staged_added_lines` 为判据"的规则自动被覆盖。
- **存量处理（关键决策）**：打开后一次扫出 **417 处存量违规**
  （A8=66 / A9=217 / A10=102 / A13=0 / A14=32）。一次性清零是几周工作量，
  若直接当硬门禁则 CI 立刻全红、团队只会选择关掉它 —— 那等于没修。
  故采用**棘轮**语义：存量快照写入 `scripts/lint_full_scan_baseline.json`，
  **只允许减少、不允许增加**；任何新增违规列出具体文件行号并让 CI 亮红。
  存量降到 0 后从快照删除该条目，规则自动升级为无条件硬门禁。
  **A13 存量为 0，故现在已是无条件硬门禁。**
- **反向验证（证明门禁真会失败，非自证）**：向 `app/app.py` 尾部注入
  `@app.route('/api/__ratchet_probe__', methods=['POST'])` 探针后复跑，
  `--full-gate` **立即返回 rc=1** 并精确报出
  `[A8] 67 处 > 基线 66 处` / `[A10] 103 处 > 基线 102 处`；
  移除探针后恢复 rc=0。**证明这道门禁不是永远绿灯。**
- **回归**：新增 `tests/test_lint_full_scan_gate.py` **14 项**，
  覆盖：开关可逆与幂等、`_all_lines` 全量语义、缺失/损坏基线按 0 处理（安全默认）、
  `write`/`load` 互逆、`write` 保留既有说明字段、真实基线文件齐全且 A13 为 0；
  核心断言 `test_new_violation_blocks` 锁住"违规数增加必须返回 1"。
- **生效条件**：`lint_wms_rules.py` 与 `ci.yml` 改动，
  **下次 CI 运行（推送到 main 或 PR）即生效**；本地 pre-commit 行为不变。
- **生效确认**：待确认（推送后查看 CI 的
  `Lint - A8/A9/A10/A13/A14 全量棘轮门禁` 步骤为绿；
  故意注入一条 `@app.route` 到 `app.py` 后该步骤应转红）。

### BUG-2026-09-25-005（2026-09-25，三账恒等式校验器写了但从未被任何 CI/脚本调用）

- **位置**：`scripts/verify_inventory_identity.py`（195 行，全仓唯一的三账判据）。
- **根因（代码实证）**：全仓 grep `verify_inventory_identity` 命中 **0 次**
  —— 没有任何 `.github/workflows/*.yml`、`Makefile`、`.githooks/*` 调用它。
  它是 `INVENTORY_TRUTH.md §1`（① = Σ② = Σ③）的**唯一机械化判据**，
  此前只靠人工在需要时手动跑。同时其 `--db` 为必填，而 CI 里没有现成库。
- **危害**：三账恒等式**没有任何自动守护**。库位账静默分裂
  （BUG-2026-08-16-002 / 08-04-002 / 2026-09-25-001 同一族问题）
  只能等用户在报表里看到账实不符才发现 —— 这正是用户所说
  "库存问题被修 100 多次"的机制之一：**没有判据，就只能靠人肉复发兜底**。
- **状态**：**已修复**（2026-09-25）。
- **修复**：新增 `scripts/ci_check_inventory_identity.py` 作为 CI 适配器。
  直接拿空库跑判据是**无意义**的（三账全 0、恒等式天然成立、门禁永远绿），
  故适配器做四步：①用 app 真实模型 `db.create_all` 建夹具库
  （保证 schema 不漂移，而非手写 CREATE TABLE）；②灌入三账一致的夹具数据
  （含"无库位账"的关库位管理场景，确认不被误判）断言 rc=0；
  ③**反向验证**：注入一条"只写总账不写库位账"的记录，断言判据 rc=1
  且报出 `ledger_vs_location`；④清除脏数据后断言恢复 rc=0。
- **踩坑记录（已在代码注释中固化）**：`TestingConfig.SQLALCHEMY_DATABASE_URI`
  被**硬编码**为 `sqlite:///:memory:`（`app/config.py:128`），会盖掉
  `DATABASE_URL` 环境变量 → 建的表全在内存、文件里一张都没有。
  必须在 import app **之前**改写 `config.TestingConfig.SQLALCHEMY_DATABASE_URI`，
  并额外做一次 schema 校验（三账表必须真实存在）防复发。
  另：`material` 表用 `unit_id` 关联单位表，**没有** `unit` 列，夹具 SQL 一度写错。
- **回归**：新增 `tests/test_ci_inventory_identity_gate.py` **10 项**，
  含「夹具 SQL 列名必须真实存在于模型 schema」「非空列必须全赋值」
  ——直接针对上述两个踩坑点；另含判据三种形态的判定断言。
  端到端项默认 skip（`WMS_CI_E2E=1` 才跑），CI 由 workflow 步骤直接调用脚本本身覆盖。
- **生效条件**：`ci.yml` 改动，**下次 CI 运行即生效**。
- **生效确认**：待确认（推送后查看 CI 的
  `Inventory - 三账恒等式门禁（含反向验证）` 步骤为绿）。

---

### BUG-2026-09-25-006：库存查询页缺少「全部仓库」汇总视图

- **发现**：用户反馈"库存查询加全部仓库"——有 4 个仓库（项目仓/库存仓/客供仓/铜排仓），
  查库存要逐仓切换 4 次，无法一次性看到全局总量。
- **根因**：AGENTS.md §二规则一"库存查询仓库必填"的修复（BUG-2026-08-02-018）
  在堵住"不指定仓库就回退全局 `Material.stock`"这个 48-BUG 根因时，
  同时也堵住了多仓库汇总视图——`if warehouse_id:` 门禁导致不选仓库就无数据。
  规则的措辞是"不指定仓库时不得返回数据"，而"用户显式选全部仓库"≠"不指定"，
  但代码没有区分这两者。
- **修复**：新增 `get_all_warehouses_stock_quantities()`（`app.py:5183`），
  对每个 `status=active` 仓库分别调用 `get_warehouse_stock_quantities(w)` 再按物料求和——
  口径仍是仓库级②/③，**绝不回退全局 `Material.stock`**。
  库存查询路由（`stock_query.py`）识别 `warehouse_id=0` 哨兵值为"全部仓库"模式，
  放行数据门禁；模板（`stock_query.html`）增加 `<option value="0">全部仓库（逐仓汇总）</option>`
  并标注口径来源。打印按钮在全仓模式下禁用（`/report/stock/print` 不支持全仓参数）。
- **口径差异说明**：`/alert` 库存预警页的"全部仓库"使用全局 `Material.stock`（历史遗留），
  与本页的逐仓汇总**可能不同**——逐仓汇总排除了无来源单据的孤儿流水，全局口径会多算。
  差异是设计如此，页面上标注口径来源，避免用户误判为 bug。
  `/alert` 全局口径的统一留待 P1-6（统一仓库参数）时一并处理。
- **回归**：新增 `tests/test_p1_5_stock_query_all_warehouses.py` **7 项**，
  含直接函数测试（A9 合规）、HTTP 端点汇总测试、模板选项测试、口径标注测试、
  打印禁用测试、不回退全局 `Material.stock` 测试、翻页保留参数测试。
  全量 2715 passed / 87 skipped / 0 failed。
- **生效条件**：代码改动，立即生效（无需 CI 配置变更）。
- **生效确认**：本地全量回归 2715 passed / 0 failed；lint `--staged` 0 违规；
  `--full --full-gate` 通过（417 = 基线，无新增）。CI 推送后三个工作流
  （WMS CI / WMS AI Verification / WMS Perf Baseline）均 success。

---

### BUG-2026-09-25-007：单据仓库参数用名称字符串（改名即失配）——P1-6 首批改 in_order

- **发现**：审计 3.2 —— 13 个页面的仓库选择器是「名称模式」：
  `<select name="warehouse">` 的 option value 为 `{{ warehouse.name }}`。
  后端按名称反查仓库，**仓库一旦改名，历史筛选与草稿回填全部失配**。
- **根因（关键澄清）**：后端校验函数 `validate_inventory_warehouse(value, warehouse_id)`
  **本身已支持 ID 优先解析**（内部 `resolve_active_inventory_warehouse` 先按
  `warehouse_id` 整数主键查，再退回 name/code），但**路由层从未把表单里的
  `warehouse_id` 传进去**——只传了 `value`（名称）。能力已具备，接线缺失。
- **修复（零风险向后兼容，本次只做 in_order 单据类型）**：
  1. `in_order.py` 两处保存路由（`/in_order/<id>/update`、`/in_order/add`）
     同时收 `warehouse_id` 与 `warehouse`，**ID 优先**；
     两者都不传才回退默认仓（AGENTS.md 规则一），无默认则 400。
  2. `purchase_order.py` 的 `create_in_order_from_selection` 同样处理
     （`in_order_add.html` 的「选单下推」会带着仓库值调它，不一起改会断）。
  3. 前端 `in_order_add.html` / `in_order_detail.html` 改为
     `name="warehouse_id"` + `value="{{ warehouse.id }}"`，JS 6 处选择器
     同步更新（含 `refreshWarehouses()` 动态重建 option 的 value 与比较逻辑）。
- **为什么后端先改、前端后改**：只改前端会让后端收到 ID 却按名称解析 → 全崩；
  只改后端则旧前端（名称）仍走兜底分支 → 行为不变。**两端都兼容才安全**。
- **踩坑**：JSON 模式下 `warehouse_id` 是 **int**，直接 `.strip()` 会
  `AttributeError: 'int' object has no attribute 'strip'`（500）。
  表单模式是 str。统一不 strip，交给 `int()` 处理（已固化到代码注释）。
- **顺带修复**：`create_in_order_from_selection` 原写法
  `(get_default_warehouse() or '').strip()` —— `get_default_warehouse()` 返回
  **Warehouse 对象**，有默认仓时 `.strip()` 必崩（latent bug）。改为取 `.name`。
- **回归**：新增 `tests/test_p1_6_in_order_warehouse_id_param.py` **9 项**
  （后端 6：ID 解析/名称兜底/ID 优先/默认回退/无效 ID 400/停用仓 400；
   前端 3：字段名/option value 为 ID/默认仓按 ID 预选）。
  全量 2724 passed / 87 skipped / 0 failed。
- **覆盖范围说明**：P1-6 共 13 个页面，本次只迁移 **in_order（采购入库）**
  这一类（2 个模板）。其余 11 个页面仍走名称兜底分支，功能不受影响，
  后续按同样模式逐类迁移（out_order / requisition / check / adjustment /
  subcontract / sales / document_table_form）。
- **生效条件**：代码改动，立即生效。
- **生效确认**：本地全量 2724 passed / 0 failed；lint `--staged` 0 违规；
  `--full --full-gate` 通过（417 = 基线）。推送后 CI 验证。

---

### BUG-2026-09-25-008：P1-6 第二批 —— out_order（出库/领料单）仓库参数统一

- **关联**：同 BUG-2026-09-25-007（in_order 首批），同根因（审计 3.2 名称模式）。
- **本次范围**：`out_order` 单据类型的两处写入路径。
  - `/out_order/<id>/update`（草稿改表头，非销售单）：原只读名称 → 补 ID。
  - `/out_order/add` 非销售分支（领料单/其他出库）：原只读名称 → 补 ID。
  - **销售出库分支本来就支持**：`validate_sales_warehouse(warehouse, data.get('warehouse_id'))`
    早已传 ID（`out_order.py:637`）——印证「能力已具备、只是接线不全」的判断。
- **前端**：`out_order_add.html`（select + JS 5 处，含 `refreshWarehouses()`
  动态重建 option 的 value/比较）+ `out_order_detail.html`（select）。
- **回归**：新增 `tests/test_p1_6_out_order_warehouse_id_param.py` **6 项**
  （add 非销售分支 4：ID/名称兜底/ID 优先/无效 ID 400；update 分支 1；前端 1）。
  全量 2730 passed / 87 skipped / 0 failed。lint 0 违规，棘轮门禁 417 = 基线。
- **剩余**：13 个页面中已迁移 in_order(2) + out_order(2) = **4 个**，
  还剩 **9 个**：`requisition` / `check` / `adjustment_add` / `subcontract_issue` /
  `subcontract_receive` / `after_sale_out_add` / `sales_order_add` /
  `sales_order_edit` / `document_table_form`(×2 select)。
  未迁移页面走名称兜底分支，功能完全不受影响。
- **生效条件**：代码改动，立即生效。
- **生效确认**：本地全量 2730 passed / 0 failed；lint 0 违规；棘轮门禁通过。
  推送后 CI 验证。


---

### BUG-2026-09-25-009：P1-6 第三批 —— requisition / check / adjustment 仓库参数统一（含共用单据模板）

- **关联**：同 BUG-2026-09-25-007（in_order）、008（out_order），同根因（审计 3.2 名称模式）。
- **本次范围**：三类单据的写入路径。
  - `requisition.py`：`/requisition/save_table`（JSON，header/data 双取）、
    `/requisition/add`（表单）、`/requisition/<id>/update`（表单）——3 处用户输入点。
    第 4 处（导入路径自动取默认仓）非用户输入，保持原样。
  - `check.py`：`/check/save_table`（JSON）、`/check/add`（表单）——2 处。
  - `adjustment.py`：JSON 分支 + 表单分支——2 处。
- **关键发现（本批最大坑）**：`/requisition/add` 与 `/check/add` **并不渲染**
  `requisition.html` / `check.html`，而是走 `app.py` 的
  `_render_requisition_form()` / `_render_check_form()` 渲染共用模板
  **`document_table_form.html`**（`doc_type='requisition'` / `'check'`）。
  只改 `requisition.html` / `check.html` 会让「新增」按钮继续提交仓库名称，
  即迁移落空。已一并迁移该共用模板的：
  - 2 处 `<select name="warehouse">` → `name="warehouse_id"`，option `value="{{ warehouse.id }}"`，
    预选条件兼容 `header.warehouse_id`（ID）与 `header.warehouse`（历史名称）。
  - `refreshWarehouses()` 动态重建 option：选择器改 `[name="warehouse_id"]`，
    比较与 value 均改 `w.id`（原为 `w.name`）。
  - **`collectHeader()`**：`warehouse:get('warehouse')` → `warehouse_id:get('warehouse_id')`
    —— 这是保存时真正提交表头的入口，漏改则后端永远收不到 ID。
- **顺带**：`requisition.html`（列表页新增弹窗）、`check.html`、`adjustment_add.html`
  （select + JS）同步迁移。
- **回归**：新增 `tests/test_p1_6_requisition_check_adjustment_warehouse_id.py` **12 项**
  （后端 6：requisition add ID / 名称兜底 / update ID / 无效 ID 400 / check add ID /
  adjustment add ID；前端 3：requisition / check / adjustment 页面；
  共用模板 3：`/requisition/add`、`/check/add`、`/requisition` 列表页）。
  定向 `-k "requisition or check or adjustment or transfer or document_table or bom"`
  338 passed / 5 skipped / 0 failed；
  全量 **2742 passed / 87 skipped / 0 failed**（2730 + 本批 12）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线，无新增。
- **剩余**：13 个页面中已迁移 in_order(2) + out_order(2) + requisition(1) +
  check(1) + adjustment(1) + document_table_form(2 select) = **9 个**，
  还剩 **6 个**：`subcontract_issue` / `subcontract_receive` / `after_sale_out_add` /
  `sales_order_add` / `sales_order_edit`，以及 `document_table_form` 的
  transfer 分支（`from_location` / `to_location` 仍为名称，需随 P1-7 一并处理）。
  未迁移页面走名称兜底分支，功能完全不受影响。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2742 passed / 0 failed；lint 0 违规；棘轮门禁通过。
  推送后 CI 验证。


---

### BUG-2026-09-25-010：P1-6 第四批（收尾）—— subcontract / after_sale_out / sales_order 仓库参数统一

- **关联**：同 007（in_order）、008（out_order）、009（requisition/check/adjustment）。
- **后端**：
  - `subcontract.py` 3 处：`/subcontract/add`、`/subcontract_issue/add`、
    `/subcontract_receive/add`（后两处原还会从父委外单继承仓库名）。
  - `after_sale_out.py` 1 处：`/after_sale_out/add`（JSON 分支）。
  - `sales.py` **本就支持** `warehouse_id`（`validate_sales_warehouse(payload.get('warehouse'), payload.get('warehouse_id'))`，
    sales.py:545/691），本批只迁前端——再次印证「能力已具备、只是接线不全」。
- **前端 5 个页面**：`subcontract_issue.html`、`subcontract_receive.html`、
  `after_sale_out_add.html`、`sales_order_add.html`、`sales_order_edit.html`。
  至此全库 `grep 'name="warehouse"'` 模板**已清零**。
- **本批两个必须处理的坑**：
  1. **委外父单只存仓库名称**（`SubcontractOrder.warehouse`），下拉改 ID 后
     原 `data-warehouse` 名称无法回填。解决：模板用
     `warehouses|selectattr('name','equalto', ...)|map(attribute='id')|first`
     在委外单 option 上补 `data-warehouse-id`，JS 改 `.data('warehouse-id')` 回填。
  2. **售后出库「历史仓库名不在启用列表」分支**原输出
     `<option value="{{ order.warehouse }}">`（名称）。改 ID 后名称会被当成
     `warehouse_id` 提交，而 `resolve_active_inventory_warehouse` 对非数字
     warehouse_id 直接 `int()` 失败判无效（**不会回退按名称匹配**）→ 必 400。
     改为 `<option value="" disabled>` + 提示「仓库已变更，请重新选择」，
     强制用户改选有效仓库（原行为同样会保存失败，只是提示更晚）。
- **回归**：新增 `tests/test_p1_6_subcontract_after_sale_sales_warehouse_id.py` **14 项**
  （委外 4：发料 ID / 收料 ID / ID 优先于名称 / 无效 ID 400；
   售后 3：ID / 名称兜底 / 无效 ID 400；
   前端 4：`/subcontract_issue`、`/subcontract_receive`、`/after_sale_out/add`、`/sales/add`；
   销售编辑页 1；委外 data-warehouse-id 2）。
  定向 `-k "subcontract or after_sale or sales or warehouse"` 638 passed / 16 skipped / 0 failed；
  全量 **2756 passed / 87 skipped / 0 failed**（2742 + 本批 14）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线，无新增。
- **同步更新的既有测试**（契约迁移，非弱化）：
  - `test_bug_2026_09_20_003_subcontract_warehouse_form.py`：断言从
    `name="warehouse"` / `value="主仓"` 改为 `name="warehouse_id"` / `value=仓库ID`，
    并新增 `data-warehouse-id` 断言；新增 `_default_warehouse_id()` 辅助。
  - `test_p1_2_after_sale_out_validation.py::test_aso_t3_warehouse_keeps_required`：
    正则改 `name="warehouse_id"`，`required` 语义不变。
- **P1-6 收尾状态**：13 个页面全部迁移完成。剩余唯一名称态字段是
  `document_table_form.html` 的 **transfer 分支**（`from_location` / `to_location`
  仍是仓库名称），属 P1-7 调拨单收敛范围，不在 P1-6 内。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2756 passed / 0 failed；lint 0 违规；棘轮门禁通过。
  推送后 CI 验证。


---

### BUG-2026-09-25-011：P1-7 前置判据 —— transfer / requisition / material 三账行为基线

- **性质**：**判据先行，不改业务代码**。审计 1.2 指出这三条路径完全绕过
  `apply_stock_delta`，但收敛是有风险的重构（会改账的走向），
  在动手术前必须先把当前行为钉死，否则改错了没人能发现。
- **新增**：`tests/test_p1_7_three_ledgers_business_paths.py` **7 项**，
  逐条固化三条路径在 ①总账 / ②库位账 / ③流水账 上的真实语义：
  | 路径 | ① 总账 | ③ 流水 | ② 库位账 |
  |---|---|---|---|
  | 调拨完成 | **不动**（物料没离开公司） | transfer_out(-q) + transfer_in(+q)，净 0 | 开库位时 from 减 to 加，净 0 |
  | 调拨反提交 | 不动 | 回到调拨前 | 回到调拨前 |
  | 领料完成 | -q | -q | 开库位时 -q |
  | 领料撤销 | 回到 +q | 回到领料前 | 回到领料前 |
  | 物料初始库存 | = initial | 一条 'opening' +q | 开库位时 +q |
  每步都断言恒等式 ① == Σ③（开库位时再断言 ① == Σ②），
  与 `scripts/verify_inventory_identity.py` 的 `no_location_rows` 口径一致
  （关库位时 ② 为空属预期，不参与校验）。
- **踩坑记录（供后续收敛复用）**：
  - 种子数据里调 `add_stock` / `update_location_inventory` 必须在
    **请求上下文**（`test_request_context`）里跑：底层写 StockTransaction 时读
    `current_user.id`，纯 `app_context` 下 `current_user` 是 None → AttributeError。
  - `/requisition/<id>/update` **只改表头**，明细必须单独调
    `/requisition/<id>/item/add`（按 material_code / quantity / unit_id 单行提交，
    不是 items JSON）。
  - 物料初始库存的表单字段名是 **`stock`**（`material.py:239`），不是 `initial_stock`。
- **为什么 transfer 不能简单套 apply_stock_delta**（本判据直接证明）：
  调拨 ① 必须保持不动，而 `apply_stock_delta` 走 `add_stock` / `deduct_stock_atomic`
  **必然改 ①**，且会给调拨凭空引入一次「全局/仓库级库存不足」校验
  （`deduct_stock_atomic` 内的 `get_warehouse_stock_quantities` 分支）。
  故调拨需要的是「只写双流水 + 库位账、不动总账」的专用入口，不能硬套入/出库入口。
- **回归**：定向 7 passed；全量 **2763 passed / 87 skipped / 0 failed**（2756 + 本批 7）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **下一步（P1-7 正题）**：按判据逐条收敛
  ① `apply_transfer_pair`（双流水 + 库位账、不动总账）→ 迁 transfer complete/revert；
  ② requisition 的 `deduct_stock`（**非原子**）→ `deduct_stock_atomic`
     + `apply_stock_delta` 的库位分支；
  ③ material 初始库存 / `app.py:8060` 期初手写 SQL → 走入口。
  每步单独一个 atomic action，改完复跑本判据。
- **生效条件**：仅新增测试，不影响线上；无需重启。
- **生效确认**：本地全量 2763 passed / 0 failed；lint 0 违规；棘轮门禁通过。
  推送后 CI 验证。


---

### BUG-2026-09-25-012：P1-7① —— 调拨收敛到专用入口 apply_transfer_pair

- **关联**：BUG-2026-09-25-011（同一条路径的判据，先建判据再动手术）。
- **做法**：新增 `services/warehouse_stock_service.py: apply_transfer_pair()`，
  `transfer.py` 的 `complete_transfer` / `revert_transfer` 两处手写逻辑全部改为
  经此入口。
- **为什么不复用 apply_stock_delta**（判据 T1~T3 直接证明）：
  调拨是物料在公司内部搬家，**①总账必须不变**。而 `apply_stock_delta` 走
  `add_stock` / `deduct_stock_atomic`，**必然改 ①**，还会给调拨凭空引入一次
  「仓库级库存不足」校验（`deduct_stock_atomic` 内的
  `get_warehouse_stock_quantities` 分支）——那正是审计 1.1 反复复发的
  「读全局账」错误方向。调拨需要的是「只写双流水 + 库位账、不动总账」的语义，
  不是入/出库语义。
- **反提交无需额外开关**：**把 from / to 对调**再调一次同一个入口即可，
  out 落在原调入仓、in 落在原调出仓，库位账同步反向。路由层因此少一个分支。
- **库位两条腿刻意不对称**（沿用存量定式，不改行为）：
  调出腿 `deduct_location_inventory_atomic`（原子扣，防超发/重复反提交）；
  调入腿 `update_location_inventory`（自动建账，不会为负）。
  反提交的调出腿因此从原来的非原子 `update_location_inventory` **升级为原子扣**
  ——严格更安全的方向性变更，回归全绿。
- **quantity<=0**：直接返回成功且不写任何账（避免 0 数量噪声流水）。
- **回归**：新增 `tests/test_p1_7_transfer_converged.py` **6 项**
  （A9 精确命名 `test_apply_transfer_pair` 1 项 + 库位/零数量 1 + 对调反提交 1 +
  库位不足拒绝 1 + 路由端到端往返 1 + 库位漂移拒绝 1）。
  定向 `-k transfer` 49 passed / 1 skipped / 0 failed；
  全量 **2769 passed / 87 skipped / 0 failed**（2763 + 本批 6）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **踩坑**：
  - `revert_transfer` 里 `resolve_inventory_warehouse_id` 还在「调入仓库存在性
    校验」处使用，收敛时误删 → NameError 被 try/except 吞成「反提交失败，请稍后
    重试」，表现像业务失败而非代码错误。**收敛时必须逐个核对符号残余**。
  - 测试"调出腿库位不足"不能靠建一张超库存的单：`/transfer/save_table` 本身就
    预检库存会先拒绝。改为建单成功后人为把库位账漂移成更小值——这恰好是现场最
    真实的账实不符场景。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2769 passed / 0 failed；lint 0 违规；棘轮门禁通过。
  推送后 CI 验证。

---

### BUG-2026-09-25-013：P1-7② —— 领料扣减收敛到 apply_stock_delta（纯重构）

- **关联**：BUG-2026-09-25-011（判据先行，先钉死行为再动手术）、
  BUG-2026-09-25-012（调拨专用入口，同批收敛的另一条路径）。
- **做法**：`app/routes/requisition.py` 的 `complete_requisition` / `revert_requisition`
  两处手写三账，改为经 `services/warehouse_stock_service.apply_stock_delta()` 单点入口；
  移除因此不再使用的底层原语导入（`deduct_stock` / `deduct_location_inventory_atomic` /
  `resolve_inventory_warehouse_id` / `add_stock` / `update_location_inventory` /
  `location_management_enabled`）。
- **为什么是纯重构（三条逐字核对，不靠"应该没变"）**：
  1. `deduct_stock`（app/app.py:4478）本就是 `deduct_stock_atomic` 的薄包装，
     原子条件扣减与失败语义原样保留；
  2. 入口的库位分支对负 delta 最终落到 `deduct_location_inventory_atomic`
     （app/app.py:4692），且在调用前多做一步「无库位记录且不允许负库存 → 失败」的
     显式校验（方向是**严格更强**，不是放宽）；
  3. 库位键口径一致：原写法 `(location or '').strip() or requisition.warehouse`，入口是
     `(location or '').strip() or _stock_location_from_warehouse(warehouse)`，
     而 `_stock_location_from_warehouse` 对字符串入参返回其 strip 后的自身
     （app/app.py:4493）。
- **唯一真实口径差（已显式补回，不许"顺手放宽"）**：
  `apply_stock_delta` 对 `delta == 0` **直接成功且不写账**；而原来的
  `deduct_stock(material, 0)` 会走进 `deduct_stock_atomic` 的 `qty <= 0` 分支返回
  `(False, '扣减数量必须大于 0')`，**整单失败**。直接替换会把 0 数量明细行从
  「拒绝整单」悄悄放宽为「放行且全程无报错」——与 BUG-2026-09-20-008 同型的
  静默账实分裂温床。故在循环内显式保留 `if item.material and qty <= 0: 拒绝整单`；
  物料为空仍交由入口返回「物料不存在」，与原 `deduct_stock` 逐字一致。
- **钉子（判据 T8）**：`tests/test_p1_7_three_ledgers_business_paths.py` 新增 T8——
  0 数量明细必须拒绝整单、① 总账不变、不产生任何 `requisition` 流水。
  HTTP 入口 `/requisition/<id>/item/add` 本身拒绝 `quantity<=0`，故 T8 直接落
  历史脏数据行来覆盖该分支。
  **已做反向验证**：把守卫临时改成 `if False` 后 T8 立即变红（响应 `status` 由
  `error` 变 `success`），证明该测试能真正抓到回归，不是常绿摆设。
- **防回退门禁**：新增 `tests/test_p1_7_convergence_guards.py` **15 项**静态门禁——
  已收敛的 `transfer.py` / `requisition.py` 必须引用各自入口，且不得再出现
  `add_stock` / `deduct_stock` / `deduct_stock_atomic` / `add_stock_transaction` /
  `update_location_inventory` / `deduct_location_inventory_atomic` 的**实际调用**
  （先剥掉 Python 行注释再匹配「名字后紧跟 `(`」，避免把注释里的函数名误判为违规）。
  行为正确性由判据文件覆盖，本门禁只管「不许再有人手写绕过」。
- **回归**：定向 `-k requisition` 84 passed / 1 skipped / 0 failed；
  判据 + 门禁 23 passed；全量 **2785 passed / 87 skipped / 0 failed**（2784 + T8）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **剩余同类未收敛**（下一个 atomic）：物料初始库存（`material.py:239/275` 的
  `add_stock_transaction` + `update_location_inventory`）与期初建账手写 SQL
  （`app/app.py:_apply_opening_stock_balance`，文档标 8406，用户点名 8060 一带）。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2785 passed / 0 failed；lint 双门禁通过；推送后 CI 验证。

---

### BUG-2026-09-25-014：P1-7③ —— 建账语义收敛到专用入口 apply_opening_balance

- **关联**：BUG-2026-09-25-011（判据，T7 已钉死物料初始库存三账行为）、
  BUG-2026-09-25-012（调拨专用入口）、BUG-2026-09-25-013（领料收敛 + 防回退门禁）。
- **做法**：新增 `services/warehouse_stock_service.py: apply_opening_balance()`，
  `material.py` 新增物料的初始库存段（`add_stock_transaction` + `update_location_inventory`
  手工双写）改为经此入口。
- **为什么必须是「第三个」入口（不能用 apply_stock_delta 顶替）**：
  建账的 **①总账是调用方自己定的**——新增物料时 `Material.stock` 在构造时就被赋成
  `initial_stock`。若走 `apply_stock_delta`，它会 `add_stock` 再涨一次 ①，
  **初始库存直接翻倍**（12 变 24）。期初单据同理（① 由 `sa_update` 自己加减差额）。
  三个入口的语义边界至此成型：

  | 语义 | 入口 | ①总账 | ③流水 | ②库位账 |
  |---|---|---|---|---|
  | 入/出库 | `apply_stock_delta` | 改 | 写 | 写（开库位） |
  | 调拨 | `apply_transfer_pair` | **不动** | 写双向 | 调出减/调入加 |
  | 建账 | `apply_opening_balance` | **不动（调用方负责）** | 写 `opening` | 写（开库位） |

- **行为等价核对（逐条，不靠"应该没变"）**：
  ① 不动（与构造赋值一致）；③ 一条 `opening` 流水，`reference_type='opening_stock'` /
  `reference_id=material.id` / `remark='新增物料初始库存'` / `location` / `warehouse`
  与原调用**逐字一致**；② 仅在开库位时写，库位键 `(location or '').strip() or 仓库名`
  与原 `_loc` 回退口径一致（`_default_wh` 为空时新旧两边都不写库位账）。
  负数量支持（期初改单调减差额可为负）：③ 写负、② 同步减，`quantity == 0` 不写任何账
  （与 `material.py` 的 `initial_stock > 0` 口径一致）。
- **回归**：新增 `tests/test_p1_7_material_opening_converged.py` **6 项**
  （A9 精确命名 `test_apply_opening_balance` 1 项 + 关库位 1 + 零数量 1 + 负差额 1 +
  路由端到端「① 没被翻倍」1 + 开库位三账恒等 1）。
  防回退门禁 `test_p1_7_convergence_guards.py` 扩到 **22 项**（`material.py` 纳入
  CONVERGED，同样禁止再手工调用 6 个底层原语）。
  定向 `-k "material or opening"` 475 passed / 2 skipped / 0 failed；
  P1-7 四个测试文件合计 42 passed；全量 **2798 passed / 87 skipped / 0 failed**。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **刻意未动（下一个 atomic，不是遗漏）**：期初单据
  `_apply_opening_stock_balance`（app/app.py:8030，用户点名的 8060 一带）与其对称的
  `_reverse_opening_stock_line`（app/app.py:8128）**本次不动**，原因：
  1. 它的流水 `location` 恒写 `warehouse.name`，而库位账用 `location or warehouse.name`
     ——两处口径本就不一致，收敛前必须先补判据钉死当前行为；
  2. `warehouse` 为 None 时流水 location 还要回退 `opening.warehouse.name`，
     与入口的回退口径不同，直接替换会改变落库值；
  3. 库位段带「历史库位账缺行时先按旧期初数量补基线」的 legacy 回填，属准备动作。
  故本次只收敛 `material.py` 那一半，期初单据账务单独一个 atomic 处理。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2798 passed / 0 failed；lint 双门禁通过；推送后 CI 验证。

---

### BUG-2026-09-25-015：P1-7③ 下半 —— 期初建账 `_apply_opening_stock_balance` 收敛到建账入口

- **关联**：BUG-2026-09-25-014（建账专用入口 `apply_opening_balance` 与
  `material.py` 那一半）。本条收敛用户点名的 `app/app.py:8060` 一带的期初手写 SQL。
- **做法**：`_apply_opening_stock_balance` 里手写的 `StockTransaction(` 与库位账
  双写，改为经 `apply_opening_balance`；**①总账仍由原有的 `sa_update` 自己改**
  （建账语义：① 由调用方负责，入口绝不碰，否则与 `Material.stock` 双改直接翻倍）。
- **入口为此扩展两个参数（不是加戏，是旧实现真有两个不同口径）**：
  - `txn_location`：③流水的 location，**必须与②的库位键分开**。旧实现里
    流水 location **恒记 `warehouse.name`**，而库位账记的是**明细行库位**
    ——两处本就不一致，共用一个参数会把流水的落库值改掉。
  - `sync_location`：是否同步②。旧实现在 `warehouse` 为 None 时**根本不写库位账**
    （旧条件 `and warehouse`），由调用方显式传 `False` 保持该口径。
- **判据当场抓出两个真实偏差（这正是先写判据的价值，不是事后补记）**：
  1. 收敛第一版把明细行库位 `LOC-1` 写进了**流水** location（旧值应为 `仓库A`）
     ——因为入口把同一个 `location` 参数同时喂给了 ③ 和 ②；
  2. `warehouse=None` 时流水 location 变成 `None`（旧值应回退 `opening.warehouse.name`）
     ——`add_stock_transaction` 只把 warehouse 解析成 `warehouse_id`，
     **不会顺带填 location**，回退必须由入口自己做
     （`_stock_location_from_warehouse`）。
  两处都由 `tests/test_p1_7_opening_stock_balance_converged.py` 钉死。
- **刻意保留的旧口径（逐条核对，不是照抄）**：
  ① `sa_update` 自改；③ 一条 `opening` 流水（`reference_type='opening_stock'`、
  `reference_id=opening.id`）；② 库位键 `location or warehouse.name`；
  `abs(delta) > STOCK_COMPARE_EPSILON(1e-6)` 门槛（小于它一笔账都不写）；
  **legacy 回填**（老库位账缺行时先按旧期初数量补基线再扣差额，使最终行值 ==
  `new_quantity`）作为**准备动作**保留在入口调用之前。
  顺序变化：旧实现 ③ → 回填 → ②，现为 回填 → ③+②；回填只动
  `LocationInventory`、③只动 `StockTransaction`，两者无交互，安全。
- **回归**：新增 `tests/test_p1_7_opening_stock_balance_converged.py` **6 项**
  （新建 1 + 改小 1 + 库位/流水口径分离 1 + legacy 回填 1 + warehouse=None 回退 1 +
  EPSILON 门槛 1）。防回退门禁扩到 **23 项**，新增**函数级**门禁：
  `app.py` 有 3.4 万行、全库原语都在里面，按文件粒度必然误报，故只卡
  `_apply_opening_stock_balance` 的函数体——不得再手写 `StockTransaction(` /
  `update_location_inventory(`。
  P1-7 五个测试文件合计 48 passed；全量 **2805 passed / 87 skipped / 0 failed**。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **剩余同类未收敛（下一个 atomic）**：`_reverse_opening_stock_line`
  （app/app.py:8134，期初删除回冲 + 流水物理清理）。它是"回冲 + 删流水"语义，
  不是建账，需先判定应落在哪个入口（或直接沿用现有原语）再动。
- **生效条件**：代码改动，重启 WMS 服务后生效。
- **生效确认**：本地全量 2805 passed / 0 failed；lint 双门禁通过；推送后 CI 验证。

---

### BUG-2026-09-25-016：P1-8 —— INVENTORY_TRUTH.md 行号引用全线过期（含一处文件都写错）

- **现象**：文档里 11 处 `app/app.py:NNNN` 定位全部失效，普遍差 1000 行上下
  （`deduct_stock_atomic` 标 3464、实际 4510）。文档是"库存以哪份数据为准"的
  唯一真相源，行号烂掉等于让后续改库存的人按错的位置去找代码。
- **逐条修正（标 → 实际）**：

  | 引用 | 文档旧值 | 实际 |
  |---|---|---|
  | `deduct_stock_atomic` | 3464 | 4510 |
  | `add_stock` | 3510 | 4578 |
  | `_apply_opening_stock_balance` | 8406 | 8030 |
  | `add_stock_transaction` | 3784 | 4852 |
  | `add_location_inventory_atomic` | 3641 | 4709 |
  | `deduct_location_inventory_atomic` | 3740 附近 | 4794 |
  | `update_location_inventory` | 3579 | 4647 |
  | `backfill_stock_txn_warehouse_id` | 27244 | 27658 |
  | 单仓库短路 `Warehouse.query.count() == 1` | 4318 | 5137 |
  | `_material_stock_unattributed` | 4362 | 5320 |
  | `StockTransaction.warehouse_id` 列定义 | **app/app.py:6286** | **app/models/inventory.py:73** |

  最后一条不只是行号错，**连文件都错了**：列定义在模型文件里，不在 app.py。
- **行号是必腐信息，光修一次没用**——新增
  `tests/test_inventory_truth_line_refs.py` **22 项**双向防腐：
  1. 代码侧：文档标的行号处（±2 行容错）必须还能找到那个符号；
  2. 文档侧：清单里的行号必须真的写在文档里（防止只改代码清单、文档继续骗人）。
  app.py 一改行数 → 测试红 → 顺手更新清单与文档。
- **当场被自己的上一个 commit 打脸（活证据）**：修文档时按旧 grep 填了
  `backfill... 27652`，但上一个 atomic（期初收敛）刚在 `app.py:8030` 插入代码，
  把后面的行号整体推后 6 行 → 实际已是 **27658**。防腐测试第一次运行就红了，
  修正后才绿。**这恰好证明这类引用必须自动校验，不能靠人记。**
- **顺带补的内容（零风险，但很关键）**：文档原本只写"总账只有三个写入函数"，
  容易被读成"可以直接调这些原语"。已在表后补上 P1-7 收敛后的**入口层指引**
  （入/出库 → `apply_stock_delta`、调拨 → `apply_transfer_pair`、
  建账 → `apply_opening_balance`），并注明由
  `tests/test_p1_7_convergence_guards.py` 拦截手写回退；另加一条
  "行号会漂移、以函数名为准"的维护约定。
- **回归**：全量 **2827 passed / 87 skipped / 0 failed**（2805 + 本批 22）。
  lint `--staged` 0 违规；`--full --full-gate` 417 = 基线。
- **生效条件**：文档改动，无需重启；防腐测试纳入 CI。
- **生效确认**：本地全量 2827 passed / 0 failed；lint 双门禁通过；推送后 CI 验证。

---

### BUG-2026-09-25-017：P2b —— 三账恒等式约束（**降级为可开关运行时断言**，不做数据库级约束）

- **诉求**：给三账恒等式 ① == Σ② == Σ③ 加约束。**结论是不做数据库级**，理由：
  - `CHECK` **不能跨表、不能写子查询聚合**，而恒等式是跨表聚合，用 CHECK 根本表达不出来；
  - 触发器能表达，但每次写入都触发一次 `SUM()`，且本库历史上修过 100 多次库存问题、
    **存量脏数据未知**——一上线就会把整库写入锁死，风险远大于收益。
- **降级方案**（用户已拍板"按建议降级"）：两层
  1. **入口内可开关的运行时断言**（本次实现）：
     `services/warehouse_stock_service.py` 新增
     `verify_material_three_ledgers()` / `guard_three_ledgers()` /
     `three_ledger_guard_enabled()` / `three_ledger_guard_strict()`，
     挂在**入/出库入口 `apply_stock_delta` 末尾**；
  2. 既有的 CI 全库判据 `scripts/verify_inventory_identity.py`（不动）。
- **开关设计**（生产零成本、测试默认开）：
  环境变量 `WMS_THREE_LEDGER_ASSERT`：`1/true/yes/on/strict` 开、
  `0/false/no/off` 关；**未设置时** pytest / Flask `TESTING` 下开、生产关。
  生产想临时排查，设成 `1` 即可（只告警、不阻断）。
- **开了也只告警，不阻断**——这是刻意的：
  不能让一条对不上账的历史行把正常业务写挂。只有显式 `strict` 才抛
  `AssertionError`（供专项测试证明"这套校验真能抓到分叉"）。
  告警带明细 `①=? ②=? ③Σ=?`，一眼看出是哪一层的账先歪。
- **只挂在入/出库入口，不挂调拨与建账**：调拨（①不动、③双向净 0）与建账
  （①由调用方在入口外改）的恒等式都依赖入口之外的动作，在入口内校验会产生
  **误报窗口**（调用方还没改①就先调入口）。这两条由 P1-7 判据与 CI 全库校验守着。
- **回归**：新增 `tests/test_p2b_three_ledger_guard.py` **9 项**——
  账平时说平 / 账歪时说歪并指出哪层歪 / 开库位时②参与校验 /
  默认只告警不阻断 / `strict` 抛错 / 生产模式完全不校验 / 开关本身听环境变量 /
  连续入出库后仍恒等（含 A9 精确命名的 4 项）。
  **关键验证：守卫在 pytest 下全开，2833 passed 存量测试零误伤**
  （说明存量路径没把账写歪，也说明告警不会打断业务）。
  全量 **2836 passed / 87 skipped / 0 failed**。lint `--staged` 0 违规；
  `--full --full-gate` 417 = 基线。
- **踩坑**：A9 棘轮要求每个新增业务函数都有精确命名测试，本批 4 个函数
  一开始只写了 1 个（`verify_material_three_ledgers`），lint 当场报 3 处违规，
  补齐 `test_three_ledger_guard_enabled` / `test_three_ledger_guard_strict` /
  `test_guard_three_ledgers` 后才过。
- **生效条件**：代码改动，重启 WMS 服务后生效（默认生产关闭，行为零变化）。
- **生效确认**：本地全量 2836 passed / 0 failed；lint 双门禁通过；推送后 CI 验证。

### BUG-2026-09-26-001（2026-09-26，WMS 手机端首页：13 张卡滚两屏 + 副标题截断 + 概览条错位）

- **现场**：用户截图（Screenshot_20260926_121717）暴露三个可见问题——
  ① 13 张功能卡 2 列 × 168dp 高，首屏只能看 4 张，要滚两屏才能看完；
  ② 卡片副标题（如"手工/扫码 · 多物料入库"、"搜索物料 · 拍照上传档案照片"）
     在窄卡内被 Ellipsis 截断；
  ③ 今日概览条四格副标题（"入0 出0"、"低于安全库存"）未设 maxLines，
     换行导致四格基线错位（"0单据"、"低于安全库/存"断裂）。
- **决策（用户确认三选）**：数据口径**不动**（数字 0 是真实数据，用户自己切仓看）；
  卡片**全部保留但缩小**；副标题**保留**，只修截断。
- **修复**（仅 `HomeScreen.kt`，约 40 行，零外溢——FunctionCardItem/TodayOverviewBar
  均为本文件私有组件）：

  | 区域 | 原值 | 新值 |
  |---|---|---|
  | 卡片网格 | 2 列 × 168dp | **3 列 × 104dp**，末行补 Spacer 占位防变形 |
  | 卡片副标题 | 2 行 12sp | **1 行 11sp + Ellipsis**，5 条超长文案精简 |
  | 概览条四格 | 无 maxLines | label/sub 均 **maxLines=1 + 顶对齐** |
  | 库存告警文案 | "低于安全库存" | "低库存" |
  | Hero 区 | 概览条平铺下方 | **半悬浮**——Hero 底部留 48dp，标题+概览条整体上探 28dp 压住下边缘 |

  **半悬浮实现要点**：`Column(modifier = Modifier.offset(y = (-28).dp))` 包裹
  「今日概览」标题 Row + TodayOverviewBar，骨架同形。Compose 负 offset 仅视觉位移、
  不影响布局空间，外滚 Column 自动补偿。**踩过的坑**：一开始同时在调用点 Column 和
  概览条 Card 上都加了 offset，导致概览条被上移 56dp 叠穿 Hero——审 diff 时发现，
  已改为只在调用点 Column 上 offset，Card 只加深投影（2dp→4dp）。
- **R6 同类排查**：副标题 `maxLines=2` 仅 `FunctionCardItem` 一处；`OverviewItemCell`
  的 label/sub 未设 maxLines 仅首页概览条一处；网格 Row/Column 手动循环仅首页一处。
- **回归**：新增 `tests/test_android_home_3col_compact.py` 11 项（3 列生效/末行占位/
  卡片高度/副标题单行/概览条单行/顶对齐/文案精简/Hero padding/半悬浮 offset/卡片数不变），
  **反向破坏验证 5 场景全部精准捕获**（3列改回2列、高度改回168、文案改回长、去掉占位、
  Hero padding 改回32 各命中 1 项）。
- **生效条件**：Android 改动需 CI `assembleRelease` 产出新 APK 后用户重装（本地沙箱无
  Java/Android SDK，编译验收以 CI 为准，BUG-2026-09-12-006 规则）。
- **生效确认**：全量测试见 CI；lint 双门禁通过；推送后 CI 验证。


### BUG-2026-09-27-001：采购入库单/库存调整单「保存失败：仓库不存在或已停用：1」——P1-6 前端提交字段改漏

- **现场**（用户截图，2026-09-27）：新增采购入库单，仓库选「项目仓」，
  明细 1 行（`112016` 欧姆龙继电器 × 80），点保存弹
  **「保存失败：仓库不存在或已停用：1」**。用户原话：
  「为什么这样，用了二个月都没有问题，越修问题越多？」
- **根因**：P1-6（`BUG-2026-09-25-007`）把仓库参数统一为 `warehouse_id`，
  分三处改造，其中**第三处「JS 提交字段名」改漏**：

  | 层次 | P1-6 改动 | 验证 |
  |---|---|---|
  | ① 下拉渲染 `name="warehouse_id"` + `value="{{ warehouse.id }}"` | ✅ 已改 | ✅ T7/T8/T9 静态断言 |
  | ② 后端 `validate_inventory_warehouse(value, warehouse_id)` ID 优先 | ✅ 已改 | ✅ 后端 6 项 |
  | ③ **JS payload 发 `warehouse_id`** | ❌ **改漏** | ❌ **无覆盖** |

  `in_order_add.html` 的 `submitForm()` 从 `[name="warehouse_id"]` 读到的是
  **仓库 ID 字符串**（`"1"`），却塞进 `warehouse` 字段。后端
  `data.get('warehouse_id')` 为 `None`，只拿到 `warehouse="1"`，于是
  **拿 `"1"` 当仓库名去匹配 `Warehouse.name`/`code`** → 查不到 → 400
  「仓库不存在或已停用：1」。**用户选的「项目仓」从未被传出去**（报错里的
  `1` 正是被误当名称的 ID）。
- **为什么原有 21 项 P1-6 测试全绿却没拦住**（关键教训）：
  - `test_p1_6_in_order_warehouse_id_param.py` 的后端 6 项**自己构造**
    符合新契约的请求（`_post_in_order(..., warehouse_id=wh_b.id)`）直接打后端，
    **从不经过前端**；
  - 其「前端 3 项」（T7/T8/T9）只是**静态字符串断言** `'name="warehouse_id"' in html`，
    测的是**下拉的属性**，不是**提交的 payload**。
  - 结论：**后端 + 下拉两层被测住，前端提交字段名这一层完全在雷达外**。
    绿灯证明的是「已知检查都过了」，不是「功能是好的」。
- **同类点全量排查（R6，脚本化对账而非抽样）**：扫描全部模板的仓库提交点
  （JS payload / `FormData` / 原生表单 / URL 参数四种方式）与全部后端接收参数路由
  （21 个前端提交点 × 64 处后端接收点交叉比对），确认**同根因共 2 处**：

  | # | 位置 | 状态 |
  |---|---|---|
  | 1 | `in_order_add.html:1629` `warehouse: warehouse` | 🔴 **本次修复** |
  | 2 | `adjustment_add.html:698` `warehouse: warehouse` | 🔴 **同根因，一并修复** |

  已核实**正常、无需改动**的消费点：`in_order_add.html:1462`、
  `out_order_add.html:1290`、`after_sale_out_add.html:651`、
  `document_table_form.html:707/710`（均已正确发 `warehouse_id`）；
  `subcontract_issue/receive.html`（`FormData` 整表单序列化，字段名天然正确）；
  `purchase_order_detail.html:374`（前端发名称/后端收名称，两端一致）；
  `mobile_scan.html` 5 处（datalist/select 的 value 均为仓库名，后端按名称解析，一致）。
- **修复**：
  - `app/templates/in_order_add.html`：`submitForm()` 内变量
    `const warehouse = ...` → `const warehouseId = ...`（含 2 处引用），
    payload `warehouse: warehouse` → **`warehouse_id: warehouseId`**；
    补注释说明「下拉 value 是仓库 ID，承载 ID 的变量必须放进 `warehouse_id` 字段」。
  - `app/templates/adjustment_add.html`：同款修复（`warehouse` → `warehouseId`，
    payload 改发 `warehouse_id`）。
- **回归（防假绿设计，R8 第 3 条）**：新增
  `tests/test_bug_2026_09_27_001_in_order_warehouse_submit_field.py` **8 项**。
  **刻意不满足于「源码里有 `warehouse_id` 字符串」**（注释里写一句就能骗过），
  而是用 **node 真实执行**从模板抽取的「取数语句 + payload 字段行」——
  在假 DOM 上执行 `querySelector('[name="warehouse_id"]').value`，
  再代入对象字面量，断言**执行结果的字段名与取值**：
  T1 payload 存在 `warehouse_id`／T2 不存在旧字段 `warehouse`（防复活）／
  T3 值为仓库 ID 而非显示文本（名称）／T4 取数选择器是 `[name="warehouse_id"]`／
  T5 提交端点是 `/in_order/add`；T6~T8 下拉 `name`/option `value`/JS 语法静态契约。
  **回退验证（文件备份法 `cp` + `git checkout --`，未用 `git stash`）**：
  把 `warehouse_id: warehouseId` 退回 `warehouse: warehouseId` 后，
  **4 项精准变红**（T1/T2/T3 + 语法项），失败信息直指现场
  （`assert 'warehouse' == 'warehouse_id'`），4 项对照（T4/T5/T6/T7）保持绿；
  恢复后 `diff` 与备份**字节一致**、8 项全绿。**证明该锁真能拦住复发**。
- **受影响模块全量 + 相邻回归**：P1-6 四个专项文件
  （in_order / out_order / requisition_check_adjustment / subcontract_after_sale_sales）
  + 本次新测试共 **49 passed / 0 failed**；`scripts/lint_wms_rules.py --staged`
  A1–A14 **0 违规**；`scripts/lint_no_raw_post_fetch.py` 通过。
- **生效条件（R3）**：纯 Jinja 模板内联 JS 改动，**生产需重启 WMS 服务生效**，
  浏览器 `Ctrl+F5` 清缓存。
- **生效确认**：**推送已实证（2026-09-27）**——API 通道（§8.1）推送后反查
  `GET /repos/SIX2090/wms/commits/main`：远程 main `914a9e40db38`，
  父提交 `3f3382ab9c5a`，files 变更与预期逐一致（3 个文件：
  `WMS_BUG_BASELINE.md` M、`app/templates/in_order_add.html` M、
  `tests/test_bug_2026_09_27_001_in_order_warehouse_submit_field.py` A）；
  并以 `git/trees?recursive=1` 逐文件比对 blob SHA，本地与远程**字节一致**。
  **业务生效仍待确认**——待用户在生产环境重启 WMS 服务后实测
  「新增采购入库单 → 选仓库 → 保存」返回「草稿保存成功」，并由确认人补记。
- **关联**：`BUG-2026-09-25-007`（P1-6 首批 in_order，该次改造未覆盖前端提交层）。

### BUG-2026-09-27-002：采购入库单自动草稿的仓库与备注「静默失效」（取值选择器指向不存在的元素）

- **发现**：在 BUG-2026-09-27-001 的 R6 全量排查中顺带发现（同批 P1-6 改动遗留）。
- **根因**：`in_order_add.html` 的自动草稿（localStorage，30 秒一次）用两个
  **在本模板中根本不存在**的 id 取值：

  | 字段 | 草稿代码用的选择器 | 元素真实标识 | 结果 |
  |---|---|---|---|
  | 仓库 | `#warehouseSelect` | `<select name="warehouse_id">`（**无 id**） | ❌ 恒为空 |
  | 备注 | `#remarkInput` | `<textarea name="remark">`（**无 id**） | ❌ 恒为空 |

  `querySelector('#...')` 对不存在的元素返回 `null`，`?.value` 为 `undefined`，
  `|| ''` 兜成空串 → **草稿里仓库与备注永远是空的**；恢复时
  `if (data.warehouse)` / `if (data.remark)` 恒为假，**也永远回填不上**。
- **危害（典型静默失效）**：不报错、不崩溃、无提示，功能就是不生效。用户在录单
  中途关掉页面，30 秒前「自动保存」的草稿丢失仓库与备注，误以为系统已保存完整。
  与 BUG-001 的区别：001 是**看得见**的失败（弹窗报错），本条是**看不见**的失败
  （用户以为存了，其实没存对），排查难度更高。
- **佐证（本模板内自相矛盾）**：同一模板其他 4 处读备注一律用 `[name="remark"]`
  （1465 / 1633 / 2181 / 2427 行），**只有草稿这 2 处**用了不存在的 `#remarkInput`
  ——说明是写草稿功能时凭记忆写错 id，从未与其他读取路径对齐。
- **修复**：
  - `collectFormData()`：`warehouse: querySelector('#warehouseSelect')` →
    **`warehouse_id: querySelector('[name="warehouse_id"]')`**；
    `remark: querySelector('#remarkInput')` → **`querySelector('[name="remark"]')`**。
  - `restoreDraft()`：恢复仓库改读 `data.warehouse_id` 并写入
    `[name="warehouse_id"]`；恢复备注写入 `[name="remark"]`。
  - 备注键名保持 `remark` 不变（本就正确），只修选择器。
- **回归（防假绿设计，R8 第 3 条）**：新增
  `tests/test_bug_2026_09_27_002_in_order_draft_warehouse_roundtrip.py` **7 项**。
  用 node **真实执行**「取数 → 存草稿 → 恢复」闭环：假 DOM 中
  `querySelector` 对不存在的 id **返回 null**（复现原缺陷），对真实存在
  `[name=...]` 返回带 getter/setter 的元素（可记录回填动作）。
  断言 T1 存出的 `warehouse_id` **值非空**／T2 无旧键 `warehouse`
  （**刻意用「值非空」而非「字段存在」**：旧代码字段存在但恒为空，
  只断言存在会漏掉本缺陷）／T3 备注值非空／T4 恢复后下拉被写入且值一致／
  T5 恢复后备注被写入；T6~T7 静态兜底——JS 代码行不得再出现
  `#warehouseSelect` / `#remarkInput`（**剔除 `//` 注释后判定**，
  避免被本次新增的说明性注释误伤——初版曾因此假红，已修正）。
  **回退验证（文件备份法，未用 `git stash`）**：退回旧字段名与旧选择器后
  **7 项全部变红**，恢复后 `diff` 字节一致。
- **踩坑记录（测试自身）**：初版 `_harness()` 用**字面量列表**拼装 JS
  harness，其中含 `'[name="warehouse_id"]'` 这类既需转义双引号、又需配对
  方括号的混合字面量，导致 Python 报 `'[' was never closed`（行号指向
  `parts = [`，误导排查方向）。**改用 `parts = []` + 逐条 `append` 后立即通过**。
  另：抽出的 `collectFormData` 字面量引用了函数内变量 `rows`，
  harness 需先 `const rows = [];` 否则 `ReferenceError: rows is not defined`。
- **受影响模块相邻回归**：与 BUG-2026-09-27-001 两个测试文件合计
  **23 passed / 0 failed**；`scripts/lint_wms_rules.py --staged` A1–A14 **0 违规**。
- **生效条件（R3）**：纯 Jinja 模板内联 JS 改动，**生产需重启 WMS 服务生效**，
  浏览器 `Ctrl+F5` 清缓存。
- **生效确认**：**推送已实证（2026-09-27）**——API 通道（§8.1）推送后反查
  `GET /repos/SIX2090/wms/commits/main`：远程 main `45f8c09d2ce1`，
  父提交 `f747e8ca3e`，files 变更与预期逐一致（3 个文件：
  `WMS_BUG_BASELINE.md` M、`app/templates/in_order_add.html` M、
  `tests/test_bug_2026_09_27_002_in_order_draft_warehouse_roundtrip.py` A）；
  并以 `git/trees?recursive=1` 逐文件比对 blob SHA，本地与远程**字节一致**。
  **业务生效仍待确认**——待用户在生产环境重启服务后实测
  「录单中途关闭页面 → 重新打开新增页 → 草稿恢复」，确认仓库与备注被正确回填，
  并由确认人补记。
- **关联**：`BUG-2026-09-27-001`（同批排查发现）、`BUG-2026-09-25-007`（P1-6 改造）。

### BUG-2026-09-27-003（2026-09-27，三账恒等式判据无仓库维度 → 仓级串仓全绿放行）

- **位置**：`scripts/verify_inventory_identity.py`（全仓唯一的三账恒等式判据）。
- **根因（代码实证）**：判据**全文零次出现 `warehouse`**，
  `build_identity_rows()` 只按 `material_id` 汇总；而 `location_inventory`
  （唯一约束 `(material_id, warehouse_id, location)`）与 `stock_transaction`
  （`idx_stock_txn_warehouse_id`）**都带 `warehouse_id` 维度**。
  即 §1 恒等式 `① = Σ② = Σ③` 是**物料级**的：只能证明**总数**对，
  **不能证明分布对**。
- **危害（实测复现，非理论推测）**：
  ```
  物料 M1 应为 A仓 60 + B仓 40 = 100（总账 100 正确）
  库位账被写坏成 A仓 20、B仓 80（合计仍 100，两仓各自都错）
  修复前：findings=[]  ①≠② 条数=0  退出码=0   ← 全绿放行
  ```
  门禁在 CI 里打 ✓，给人"三账已对齐"的错觉。**这正是 AGENTS.md R2
  「多仓库隔离」明令必验项，也是 `BUG-2026-09-02-001`（全局当单仓账面）、
  `BUG-2026-09-03-001/002/004`（同根因四处复发）的同一根因方向**——
  判据在架构上抓不到这一类，等于 R2 在"核对"环节无守护。
- **R6 同类点排查**：本判据是**全仓唯一**三账恒等式入口
  （`grep verify_inventory_identity` 仅命中 CI 适配器 `ci_check_inventory_identity.py`
  与文档/测试，无第二个消费点）。同类"物料级判据冒充全局判据"的形态已一并检查：
  `_material_stock_unattributed`（反提交兜底）与 `get_warehouse_stock_quantities`
  （仓库级读取）均已是仓库级口径，不属同根因，不需同批修改。
- **修复（判据扩展，**净增强**）**：新增两个纯函数
  `build_warehouse_rows(locations, transactions)`（按 `(material_id, warehouse_id)`
  汇总库位账与流水账）与 `find_warehouse_mismatches(rows, wh_rows, tol)`
  （逐 (物料, 仓库) 比对，报 `wh_location_vs_txn`）；`warehouse_id IS NULL`
  的历史行入 `UNATTRIBUTED` 桶**单列待确认**，**不猜归属**
  （INVENTORY_TRUTH.md §3.2）。硬失败条件由 `①≠②` 扩展为
  **`①≠②` 或 仓级 `②≠③`**。
- **向后兼容（关键约束）**：`build_identity_rows` / `find_mismatches` 的返回值
  与调用签名**逐字不变**（已实测旧式 2 元组入参返回结果与旧版一致）；
  `summarize` 不传仓级参数时输出键与旧版一致。既有调用方与测试零改动。
- **CI 门禁同步强化**：`scripts/ci_check_inventory_identity.py` 由 3 步扩为 4 步，
  新增第 4 步"注入仓级串仓（物料级合计仍相等）→ 断言判据报出
  `wh_location_vs_txn`（rc=1）"。无此步则本能力在 CI 里无守护、被改坏也无人知
  （与 `BUG-2026-09-25-006` 的教训同一逻辑：门禁必须"会失败"）。
- **回归**：`tests/test_inventory_identity_checker.py` 新增 `TestP01WarehouseDimension`
  **6 项**（仓级串仓必被抓／正确分布不误报／NULL 不猜归属／"一仓多一仓等额少"最刁钻形态／
  2 元组向后兼容／summarize 无仓级参数保持旧键）；
  `tests/test_ci_inventory_identity_gate.py` 新增 **3 项**（`_CROSS_WH_SQL` 列名与
  非空列校验、仓级反向验证、仓级正确时不误报）。
- **回退验证（R8 第 3 条，双件）**：① 用文件备份法回退 `verify_inventory_identity.py`
  → **5 项新用例全部失败**（`AttributeError: no attribute 'build_warehouse_rows'`），
  原 10 项仍通过；② 回退判据后跑 CI 门禁 → 第 4 步**正确报错**
  「P0-1 的仓级维度没生效或已被改坏」。**两道锁都锁得住，非自证陷阱**。
  回退用 `cp` 文件备份法，**未用 `git stash`**（R8 明令，本环境曾因 stash 被
  SIGTERM 中断致仓库损坏）。
- **生效确认**：**已确认（2026-09-28）**——
  受影响与相邻模块 `pytest`（checker + gate + p2b + p1_7 三条链 + warehouse_stock_service）
  **72 passed / 1 skipped / 0 failed**，与修复前基线（35 passed / 1 skipped）相比
  **无任何回归**；**全量 `tests/` 2933 passed / 87 skipped / 0 failed（828s）**；
  `scripts/lint_wms_rules.py` 全量与 `--staged` 均 A1–A14 **0 违规**；
  `scripts/lint_no_raw_post_fetch.py` 通过；`scripts/ci_check_inventory_identity.py`
  **4 步全绿**（含 ①≠② 与 仓级②≠③ 双反向验证）。
  **推送已实证（2026-09-28）**——API 通道（§8.1）推送后反查
  `GET /repos/SIX2090/wms/commits/main`：远程 main `3d4eba3af617`，
  父提交 `1f8df6f424c6`，files 变更 6 个与预期逐一致
  （`INVENTORY_TRUTH.md` +39、`WMS_BUG_BASELINE.md` +63、
  `scripts/ci_check_inventory_identity.py` +52/-5、
  `scripts/verify_inventory_identity.py` +166/-14、
  `tests/test_ci_inventory_identity_gate.py` +80、
  `tests/test_inventory_identity_checker.py` +95）；
  `git diff FETCH_HEAD HEAD` **零差异**，本地与远程 tree 同为 `927c209455`，**字节级一致**。
  **CI 实证（§三 门禁，最强证据）**：`scripts/check_ci_green.py` rc=0，三工作流全绿且
  `WMS CI` #1286 与 `WMS AI Verification` #1581 **均指向本次提交 `3d4eba3a`**
  （2026-09-28T00:21:17Z）——即本次修改的三账门禁**在真实 CI 环境中已跑通**
  （`Android APK Build` #756 仍指 `1f8df6f`：本改动无 Android 文件，
  该工作流按路径过滤未触发新运行，不构成未验证项）。
  **本改动纯 Python（scripts + tests + 文档），不涉及 Jinja 模板与 `app/` 运行时代码，
  无 R3 重启要求。**
- **踩坑记录（通道细节，与 §8.1 有出入）**：本环境实测 token 认证头是
  **`Authorization: token <T>`**，而 §8.1 记载的 `Bearer` 返回
  401 `Bad credentials`；`get_token.sh` 必须与后续 curl/脚本写在**同一条命令**里
  （子 shell 导出会丢，实测出现 `token 长度: 0`）。另：`git push` 走 ghproxy
  前缀报 `could not read Username`（与 §8.1「代理只能拉取不能推送」一致）；
  `api.github.com` 经 DoH 解析 IP 写 `/etc/hosts` 后直连可用（200）。
  **§8.1 的 `Bearer` 写法建议后续修订**。
- **关联**：`INVENTORY_TRUTH.md` §4.1（新增章节）、`BUG-2026-09-25-005/006`（判据写了没跑）、
  `BUG-2026-09-02-001` / `BUG-2026-09-03-001/002/004`（同根因方向）、
  `AGENTS.md` §七 R2 / R8。

### BUG-2026-09-27-004（2026-09-27，三账判据全表逐行拉取，生产库内存/耗时随流水线性膨胀）

- **位置**：`scripts/verify_inventory_identity.py` 的 `collect_from_app()`。
- **根因（代码实证）**：三张表**逐行**实例化为 ORM 对象再拉进内存，只为算两个
  `GROUP BY ... SUM(quantity)` 聚合：
  ```python
  transactions = [(t.material_id, t.quantity, t.warehouse_id)
                  for t in StockTransaction.query.all()]
  ```
  `stock_transaction` 是 **append-only 流水表**（`INVENTORY_TRUTH.md §1`
  的"唯一不可篡改的账本"），只增不改，是仓库里增长最快的表；每行含
  `location` / `remark` / `reference_type` / `reference_id` / `operator_id` /
  `created_at` 等 8 个与本判据**无关**的列，却全部加载、全部实例化。
- **危害（实测量化，非理论推测）**：20 万条流水夹具下

  | 指标 | 旧法 | 新法 | 改善 |
  |---|---|---|---|
  | 返回行数 | 200,000 | 1,000 | **200×** |
  | 耗时 | 10,846 ms | 165 ms | **66×** |
  | 峰值内存 | 326.6 MB | 0.4 MB | **~800×** |

  且随流水**线性增长**（append-only，只增不减）。**CI 夹具库仅 3–4 行，
  此问题在门禁中完全不可见** —— 属"本地/CI 全绿、现场趴窝"型风险，
  与 R1（分页默认值不得当业务上限）的教训同源。
- **R6 同类点排查**：本判据取数点是 `collect_from_app()` **唯一一处**
  （`scripts/verify_inventory_identity.py` 内不存在第二个取数入口）；
  CI 适配器 `ci_check_inventory_identity.py` 通过 subprocess 调子脚本，
  **不自行取数**，无同类点。`app/` 内其他库存聚合点（`get_warehouse_stock_quantities`
  等）已是 SQL 聚合口径（`INVENTORY_TRUTH.md §2.2`），不属同根因。
- **修复**：`GROUP BY (material_id, warehouse_id)` + `SUM(quantity)` 下推到 SQL，
  库位账与流水账**两条都下推**（保持口径一致）；ORM 对象降为裸元组。
  新增 `--no-pushdown` 开关保留旧路径供对照排障。
- **语义变化（已显式声明，非静默改变）**：返回列表由「逐行明细」变为
  「已按 (物料,仓库) 聚合」——同一 `(material_id, warehouse_id)` 下推版出 1 行、
  旧版出 N 行。对判据**无影响**（下游只做累加，**累加结果逐位相同**），
  但属**对外可观测的返回语义变更**，已在 docstring、`INVENTORY_TRUTH.md §4.2`
  与本条目三处写明，不得当作"完全等价"轻描淡写。
- **回归**：新增 `tests/test_p1_1_identity_aggregation.py` **11 项**，覆盖
  ①累加等价（流水/库位/物料三项）②聚合语义（同仓折叠为一行／多仓隔离不串仓／
  **NULL 归属行不得被 GROUP BY 静默丢弃**／返回裸元组非 ORM）
  ③**判定结果完全一致**（summary / findings / warehouse_findings 两路径相等）
  ④场景自检（确认夹具真产出预期账，防夹具写错导致假绿）
  ⑤静态兜底（推送路径不得再出现 `StockTransaction.query.all()`，防被改回去）。
- **回退验证（R8 第 3 条）**：文件备份法回退 `verify_inventory_identity.py`
  → **11 项新用例全部失败**，恢复后全过。**锁真实有效，非自证陷阱**。
  回退用 `cp` 文件备份法，**未用 `git stash`**（R8 明令）。
- **等价性交叉验证**：随机 3000 条流水（`random.seed(42)`，含负数/零/多仓/NULL）
  下，两路径 `summary` **完全一致**（正确检出 2 条 ①≠③、4 条仓级差异）；
  真实夹具库对比 materials / locations / txn 累加结果逐位相同。
- **生效确认**：**已确认（2026-09-28）**——推送 `d85b8a23`（本地 `d4fc065`，API 推送，
  远端 tree 与本地 tree 逐位一致 `5439769e`，`git diff FETCH_HEAD HEAD` 零差异）；
  `WMS AI Verification` **#1583** ✅、`WMS CI` **#1288** ✅（均 @`d85b8a23`），
  `Android APK Build` #756 ✅，三工作流全绿（`scripts/check_ci_green.py` 判定
  「允许开工」）。本地实证：受影响模块 **39 passed / 1 skipped / 0 failed**，
  全量 `tests/` **2944 passed / 87 skipped / 0 failed**（828s）；
  `scripts/lint_wms_rules.py` 全量与 `--staged` 均 **0 违规**（含 pre-commit hook 实跑通过）；
  `scripts/ci_check_inventory_identity.py` **4 步全绿**。
  **本改动纯 Python（scripts + tests + 文档），`collect_from_app` 只被 `main()` 与
  测试调用，不涉及 `app/` 运行时代码与 Jinja 模板，无 R3 重启要求。**
- **踩坑记录（供后续复用）**：
  1. **推送通道**：`github.com` 的 git 协议在沙箱内 TLS 被封，`git push` 走 `ghproxy.net`
     报 `could not read Username`（代理只读）。改走 §8.1 的 Git Data API 四步重放。
     实测 **`Authorization` 头正确写法是 `token <T>`，不是 §8.1 记的 `Bearer <T>`**
     （`Bearer` 返回 `401 Bad credentials`）——建议后续把 §8.1 订正。
  2. **`get_token.sh` 必须与使用同一条命令**：`source` 的 export 在子 shell 里丢，
     分两条命令会出现 `token 长度: 0`。
  3. **本地无远端对象**：API 推的 commit 在本地对象库不存在，
     `git update-ref refs/remotes/origin/main <remote-sha>` 会报 `nonexistent object`。
     正确做法是先 `git fetch --depth 1 <proxy-url> main` 再 `update-ref … FETCH_HEAD`。
  4. **测试顺序依赖（本次真实踩到）**：`tests/test_p1_1_identity_aggregation.py`
     初版用 `scope="module"` 夹具 + `config.TestingConfig.SQLALCHEMY_DATABASE_URI = …`
     切库，**单独跑 11 passed，全量跑 1 failed（`assert 3 == 2`）**——原因是 app 已初始化，
     事后改 config 的 URI **不生效**，判据读到了上一模块残留的库。
     已按仓库既有标准写法重写（`sqlite:///:memory:` 走环境变量 + 函数级夹具
     `db.drop_all()/db.create_all()`），全量复跑消除。**教训：新增测试必须跑全量，
     只跑单模块会漏掉顺序依赖**（R7 的正确用法不是"避免全局 config"，
     而是"新测试必须经全量顺序验证"）。
- **关联**：`INVENTORY_TRUTH.md` §4.2（新增章节）、`BUG-2026-09-27-003`（同判据的
  口径缺口 P0-1，同日修复）、`BUG-2026-09-25-005/006`（判据写了没跑）、
  `AGENTS.md` §七 R1 / R8。

---

### BUG-2026-09-27-005（2026-09-27，三账判据 `①≠③` 无论多少条都静默返回 0，形成双重盲区）

- **位置**：`scripts/verify_inventory_identity.py` 的退出码判定
  （修复前 :365-366 的 `--json` 分支与 :397-400 的文本分支）。
- **根因（代码实证）**：退出码只读两个条件，**不读 `①≠③`**：
  ```python
  return 1 if (summary["mismatch_ledger_vs_location"]           # ①≠②
               or summary.get("mismatch_wh_location_vs_txn")) else 0   # 仓级 ②≠③
  ```
  更糟的是它与 P0-1（`BUG-2026-09-27-003`）新增的仓级维度形成**双重盲区**：

  | 层次 | 对 `warehouse_id IS NULL` 行的行为 |
  |---|---|
  | 物料级 `ledger_vs_txn` | 不阻断（退出码不读它） |
  | 仓级 `wh_location_vs_txn` | **主动跳过** `UNATTRIBUTED` 桶（`INVENTORY_TRUTH.md` §3.2「不猜归属」的刻意设计） |

  两者交集 —— NULL 归属历史行造成的 `①≠③` —— **没有任何判据覆盖**。
- **危害（实测复现，非理论推测）**：纯函数直测
  ```
  总账 100；库位账 仓7=100；流水 仓7=100 外加一笔 NULL 仓流水 -60
    ①≠② 条数       : 0
    ①≠③ 条数       : 1      ← 总账 100 vs 流水 40，差 60
    仓级 ②≠③ 条数  : 0
    退出码          : 0      ← ❌ 全绿放行
  ```
  > 用 CLI 跑真库不易复现：app 启动的 `backfill_stock_txn_warehouse_id`
  > （`app/app.py:28251`）会把**能唯一确定**归属的 NULL 行填上、从而被仓级判据兜住。
  > 但**歧义行与无法解析行有意保留 NULL**（`app/app.py:28264`，符合 §3.2）——
  > 这些行永远落在双重盲区里。
- **为什么是缺陷而非有意设计**：`INVENTORY_TRUTH.md` §2 派生方向表文档正文写明
  `① 独立于 ②③ 变动 | ❌ 禁止 | 除非 # stock-truth:reason= 显式豁免`；
  此前**只有判据脚本自己的注释**单方把它降级为「待确认不阻断」。
  `WMS_BUG_BASELINE.md` / `AGENTS.md` / `WMS_BUSINESS_SCOPE.md`
  **无任何条目**把 `①≠③` 登记为「允许保留」。
- **R6 同类点排查**：全仓 grep `ledger_vs_txn` / `①≠③` 的判定点，
  **只有本判据一处**。CI 适配器 `ci_check_inventory_identity.py` 通过 subprocess
  调子脚本、不自行判定，无同类点。`app/services/warehouse_stock_service.py`
  的 `verify_material_three_ledgers` 读的是同一恒等式，但它是**运时守卫**
  （默认只告警，`WMS_THREE_LEDGER_ASSERT=strict` 才抛），语义不同、不改动。
- **修复（分级判定 + 显式豁免登记）**：

  | 级别 | 条件 | 退出码 |
  |---|---|---|
  | 🔴 硬失败 | 有 `①≠③` 且该物料**无豁免登记** | **1** |
  | 🟡 豁免（告警） | 有 `①≠③`，物料在名单内且**理由非空** | 0 |
  | ✅ 通过 | 无 `①≠③` | 0 |

  新增 `--allow-drift <json>`：`{"materials": {"物料编码或ID": "必填理由"}}`。
  **不传 = 全部 `①≠③` 硬失败**（默认严格）；名单内**理由为空/空白 = 未登记**，
  仍硬失败（防"空名单糊过去"）；文件缺失/JSON 非法/结构不符 → **rc=2 显式报错，
  绝不静默当空名单**（A12 精神）。
- **为什么不用阈值**：阈值只能回答"差多少算多"，**不能回答"这条差是不是已知的"**——
  差 1e-9 的真 BUG 与差 10 万的历史建账在阈值法下无法区分，且阈值本身是新的魔法数（R1）。
  用「是否可指名解释」作判据更接近真相。
- **语义变化（已显式声明）**：`summarize()` 新增 `drift_hard` / `drift_waived` /
  `drift_hard_findings` / `drift_waived_findings` 四个键——**仅在显式传参时出现**，
  既有调用（不传 `drift_*`）返回**逐字节不变**（P0-1 同款向后兼容策略）。
  `ledger_vs_location` 与仓级 findings **不参与豁免**，其硬失败地位不变。
- **回归**：
  - 新建 `tests/test_p2_1_drift_gate.py` **21 项**（真子进程 + 真文件库，锁退出码契约）：
    ①只有 `①≠③` → rc=1；②登记后 → rc=0；③空理由 → 仍 rc=1；
    ④文件缺失 → rc=2；⑤只登记不相干物料 → 不得误豁免；⑥`--json` 带 drift 键；
    ⑦静态兜底（退出码表达式必须含 `drift_hard`，防被改回去）。
  - `tests/test_inventory_identity_checker.py::TestP21DriftGate` **8 项**（纯函数分级）。
  - `tests/test_ci_inventory_identity_gate.py` 新增**6 项**（夹具列名校验 +
    「豁免后必须转绿」控制组 + 空白理由仍硬失败）。
- **回退验证（R8 第 3 条）**：实现前先写回归锁 → **旧代码上 18 failed**（锁得住）；
  实现后全过。回退用 `cp` 文件备份法，**未用 `git stash`**（R8 明令）。
- **生效确认**：**已确认（2026-09-28）**——推送 `48ad15f3`（本地 `58c1c9f`，API 推送，
  远端 tree 与本地 tree 逐位一致 `a5ab4e1b`，`git diff FETCH_HEAD HEAD` 零差异）；
  `WMS AI Verification` **#1585** ✅、`WMS CI` **#1290** ✅（均 @`48ad15f3`），
  `Android APK Build` #756 ✅，三工作流全绿（`scripts/check_ci_green.py` 判定
  「允许开工」）。本地实证：全量 `tests/` **2979 passed / 87 skipped / 0 failed**（878s，
  较修复前基线 2944 增加 35 个新用例）；相邻模块 **91 passed / 1 skipped**；
  `scripts/lint_wms_rules.py` 全量与 `--staged` 均 **0 违规**（含 pre-commit hook 实跑通过）；
  `scripts/ci_check_inventory_identity.py` **5 步全绿**。
  **本改动纯 Python（scripts + tests + 文档），不涉及 `app/` 运行时代码与 Jinja 模板，
  无 R3 重启要求。**
- **踩坑记录（供后续复用）**：
  1. **端到端用例必须用真文件库，不能用 `:memory:`**：判据是**子进程**，
     读不到测试进程内存里的内存库（内存库不跨进程）。首版 3 个端到端用例因此失败。
     改用文件库 + `sqlite:///{path}` 后通过。
  2. **`scope="module"` 建库 + 每用例重置数据** 比"每用例建库"快 3 倍
     （111s → 36s）。重置是「删三表数据 + 重灌夹具」的确定性操作，不引入顺序依赖。
  3. **app 启动日志会混进 stdout**，`json.loads` 报 `Extra data`。
     判据的 JSON 主体必然从**行首的 `{`** 开始——按此截取（`_extract_json`）。
  4. **CLI 复现不出 P2-1**：`app` 启动的 `backfill_stock_txn_warehouse_id`
     （`app/app.py:28251`）会把能唯一确定归属的 NULL 行填上，从而被仓级判据兜住。
     只有**歧义行/无法解析行**（`app/app.py:28264` 有意保留 NULL）才落在盲区里——
     所以复现必须用**纯函数**直测，或用**刻意不带 warehouse_id** 的夹具。
     这也是 CI 第 5 步夹具的设计依据（`tests/test_ci_inventory_identity_gate.py`
     有一条测试专门断言该夹具**不得**带 `warehouse_id`）。
- **现场升级路径（开硬门禁前必读）**：现有库若存在历史 `①≠③`，升级后判据会直接变红。
  有序做法：① `--json` 摸底条数与物料 → ② 逐条查清成因（真缺陷去修 / 历史建账登记）
  → ③ 确认无碍者写入 `--allow-drift` 并写清理由 → ④ 复核后固化为日常检查。
  详见 `INVENTORY_TRUTH.md` §4.3。
- **关联**：`INVENTORY_TRUTH.md` §4.3（新增章节）+ §2 派生方向表 + §6 自检清单新增项；
  `BUG-2026-09-27-003`（同判据的仓库维度缺口 P0-1）、`BUG-2026-09-27-004`（同判据取数 P1-1）、
  `BUG-2026-09-25-005/006`（判据写了没跑）、`BUG-2026-08-16-002`（期初只改总账，
  历史差的主要来源）、`AGENTS.md` §七 R1 / R8 / A12。

### BUG-2026-09-30-001（2026-09-30，打印告警铃铛角标把库存预警也算进"打印告警"未读，与页面口径打架）

- **发现方式**：用户走查「打印告警」页截图——页面显示"暂无未读告警，打印链路运行正常"，但右下角悬浮铃铛角标显示 2。
- **根因**：`Notification` 表被两类功能域共用：打印告警（`print_failed`/`print_pending_timeout`/`print_workstation_offline`，写于 `app/routes/print_alerts.py`）与库存预警（`low_stock`/`expiring`，写于 `app/notifications.py` 定时任务）。打印告警域的三处查询——铃铛未读数 context_processor（`print_alerts.py:370`）、页面列表（`:384`）、"全部标为已读"（`:408`）——全部 `Notification.query.filter(...)` **未加 `type` 过滤**，把库存预警也计入"打印告警"未读，导致铃铛数字与页面/实际打印告警不符。
- **R6 同类点排查**：grep 全仓 `Notification` 读取点，仅 `app/routes/print_alerts.py` 一处消费该表（`low_stock`/`expiring` 无移动端 /alert 之外的展示入口），故库存告警从打印告警域移出后不会在其他页面重复出现、也无需改其他消费点；其展示职责本就由「库存预警 /alert」实时计算承担（与 `app/notifications.py` 写入冗余，属镜像）。
- **修复**：新增常量 `PRINT_ALERT_TYPES = ('print_failed','print_pending_timeout','print_workstation_offline')`，铃铛未读计数、页面列表（含"查看全部"近 30 天）、"全部标为已读"三处统一加 `Notification.type.in_(PRINT_ALERT_TYPES)` 过滤。铃铛从此只代表打印告警、与页面严格一致；库存预警不再出现在打印告警页与铃铛（按用户拍板"库存告警移出"执行）。
- **回归**：新增 `tests/test_print_alerts.py::test_print_alert_domain_only_counts_print_types`——1 条打印失败 + 1 条 low_stock 未读 → 铃铛角标=1、页面只列打印告警且不出现 `low_stock` 原始英文标签、"全部标为已读"只清打印告警不动库存告警；既有 `test_bell_badge_shows_unread_count`/`test_mark_read_all`/`test_page_renders_for_admin` 不受影响。
- **回退验证（R8 第 3 条）**：实现前在旧代码上跑新用例 → 铃铛=2、页面列 2 条（含 `low_stock`）→ 失败（锁得住）；加 `type.in_` 过滤后全绿。回退用 `cp` 文件备份法，**未用 `git stash`**。
- **生效确认**：**已确认（2026-09-30）**——用户授权 GitHub PAT，经 `scripts/api_push.py`（Git Data API 四步重放）推送至 main；反查 `GET /repos/SIX2090/wms/commits/main` → HEAD=`94042fe9e167a7b21836561220f1de9bd3046c20`，parent=`768a86d`（克隆时远端 HEAD），变更文件 3（`WMS_BUG_BASELINE.md`/`app/routes/print_alerts.py`/`tests/test_print_alerts.py`），与本地提交 `82410c7` 内容一致；`verify_remote_sync.py` 全量 tree 比对通过（1492 文件完全一致）。三工作流（Android APK Build / WMS AI Verification / WMS CI）将在推送后自动触发，待其转绿即满足 §三 下一轮开工门禁。后端改动，**生产需重启 WMS 服务生效（R3）**。
- **关联**：`app/routes/print_alerts.py`、`app/notifications.py`、`AGENTS.md` §七 R2 / R6、A13。

### BUG-2026-09-30-002（2026-09-30，系统设置「采购退货必须关联订单」remark 仍写"为后续采购退货流程预留"，文案与已上线实现不符）

- **发现方式**：P0 三项深度测试计划制定时核证——审查报告 §二.2 判"采购退货为预留状态"，实测台账 P1-7（`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md:3036`，2026-09-20）已全量实现（选源接口 `app/routes/in_order.py:214` 只列已完成入库单并带可退数量、行级防超退闸 `app/routes/out_order.py:859-863`、来源归属 `app/models/documents.py:234-260`），`app/app.py:3726` remark 为唯一残留过时表述，误导后续 AI/开发者对功能现状的判断。
- **根因**：P1-7 实现时遗漏同步系统设置页的 remark 文案——设置项 `purchase_return_requires_order` 早在 P1-7 之前即存在，remark 写于"预留"期，功能落地后未回写。
- **R6 同类点排查**：grep 全仓 `为后续采购退货流程预留`，仅 `app/app.py:3726` 一处（`app/routes/`、`app/templates/` 均无同文案残留）；`documents.py:83` 的"预留作废流转"是真实未实现的另一功能域（单据作废流转），不属于本条。
- **修复**：remark 改写为与 P1-7 实现及开关实际语义一致的描述：默认开=强制关联来源采购入库单（仅已完成单可选源、按行防超退）；关=允许免关联创建，退货供应商必填仍生效（`out_order.py:676-681`），无来源时无法做行级防超退。纯文案改动，不触及任何业务逻辑、开关默认值与校验路径。
- **回归**：无行为改动，文案不参与逻辑，无新增测试必要；grep 复核全仓无第二处同文案。门禁：pre-commit A1–A14 通过。
- **回退验证（R8 第 3 条）**：纯展示文案无行为可回退，以 grep 复核代替（新文案落位、旧文案全仓清零）。
- **生效确认**：已确认（2026-09-30）——PAT 直通 git push 推送至 main；反查 `GET /repos/SIX2090/wms/commits/main` 确认 HEAD、parent、变更文件与本地提交一致。后端 Python 改动，**设置页文案需重启 WMS 服务生效（R3）**。
- **关联**：`app/app.py:3726`、台账 P1-7、AGENTS.md §七 R6 / A13。

### BUG-2026-09-30-003（2026-09-30，urllib3 2.7.0 新披露 3 个 CVE 触发 pip-audit 阻塞门禁，WMS CI main 转 红）

- **发现方式**：M3 性能修复开工前例行 CI 全绿门禁检查（§三）——`WMS CI #1318 @f24908a` 的 `lint-and-static` job「Security scan - pip-audit（BUG-2026-08-16-018 阻塞门禁）」步骤失败：`Found 3 known vulnerabilities in 1 package`——urllib3 2.7.0 命中 CVE-2026-97687 / CVE-2026-97688 / CVE-2026-97689，修复版本 2.8.0。同 SHA 下单元测试与 verify 分片全绿，`WMS AI Verification #1613` 亦绿，确认为**时间性故障**（CVE 数据库新披露，与同批推送内容无关）。
- **根因**：`app/requirements.txt` 钉版 `urllib3==2.7.0`；该版本在 2026-09-30 前无已知 CVE，pip-audit 当时放行；新 CVE 披露后同配置即红。
- **R6 同类点排查**：grep 全仓 `import urllib3|from urllib3` 零命中——纯 requests 传递依赖，无直接消费点需同步排查；`requirements-test.txt` 未单独钉 urllib3（经 requirements.txt 传导），无需第二处修改。
- **修复**：`app/requirements.txt` 钉版升级 `urllib3==2.7.0 → 2.8.0`（PyPI 实测存在，requires_python>=3.10，CI 3.11 / 本机 3.13 均满足；requests==2.33.0 兼容约束 `urllib3<3,>=1.21.1` 满足）。
- **回归**：本机 venv 升级 2.8.0 后冒烟 `tests/test_perf_baseline.py + tests/test_purchase_return_e2e_p0.py` 20 passed；urllib3 无直接 import，行为面为 requests HTTP 传输层，兼容性由 requests 导入与既有 HTTP 测试覆盖。
- **回退验证（R8 第 3 条）**：依赖版本回退无行为断言可锁，以 CI 实证代替——推送后 WMS CI 的 pip-audit 步骤必须转绿；若仍红则回退本提交并升级 pip-audit 排查口径。
- **生效确认**：已确认（2026-09-30）——推送 `a0f201a` 后 `WMS CI #1319 @a0f201a` 的 `lint-and-static` job（含 pip-audit 步骤）转绿，全 9 job success；生产部署需按新 requirements.txt 重建依赖并重启 WMS 服务生效（R3）。
- **关联**：`app/requirements.txt`、AGENTS.md §三 CI 全绿门禁、BUG-2026-08-16-018（pip-audit 门禁引入）。

### BUG-2026-09-30-004（2026-09-30，/report/inout/print 与 /report/inout/export N+1 懒加载，5000 单导出 15.57s/45.3MB）

- **发现方式**：M1 C1 性能基线实测（`scripts/perf_export_baseline_5000.json`）——E2 出入库导出 5000 物料/单 3 轮均值 15.57s、tracemalloc 峰值 45.3MB，而响应体仅 172KB：耗时全在 SQL 查询而非 Excel 写入。线性外推 1 万物料约 31s，生产网关超时风险实锤。
- **根因**：`app/routes/report.py` `report_inout_print`（`/report/inout/export` 委托同一函数）双层循环内触发三条懒加载链——① `order.items` 逐单 1 次；② `order.supplier` 逐单 1 次（入库侧）；③ `item.material` 逐行 1 次。每单 ≈ 3 次额外查询，5000 单 ≈ 1.5 万次 SQL。
- **R6 同类点排查**：grep `app/routes/` + `app/app.py` 同模式（`.all():` 后循环访问 `order.items` / `item.material` 的导出/报表路径）——`report_stock_print`（本批 C3 处理）、`report_supplier_print_excel`（2026-09 已修 SQL 分页）之外，其余 `order.items` 循环点均在分页列表页（页大小 ≤100，懒加载量级可接受），暂不属同根因急修范围。
- **修复**：两查询加 `selectinload` 批量预加载——入库侧 `selectinload(InOrder.items).selectinload(InOrderItem.material)` + `selectinload(InOrder.supplier)`，出库侧同构。查询数与单据数解耦（selectin 每批 500），5000 单查询数从 ~1.5 万降至 ~30。导出内容、排序、仓库过滤逻辑零改动（A11 不涉及：本修复不新增库存校验口径）。
- **回归**：新增 `tests/test_bug_2026_09_30_004_inout_export_n_plus_one.py`（A9）：① 查询计数锁——80 入库单 + 40 出库单导出期间 SQL ≤50 条（修复前实测 ~320 条）；② 内容正确性锁——行数/编号/供应商名/物料/数量/金额与造数一致，supplier 批量预加载全集校验。
- **回退验证（R8 第 3 条）**：cp 备份法回退修复后新测试失败（查询计数锁触发）→ 恢复修复后通过，锁有效性实证。
- **修复后实测**：5000 物料 3 轮均值 **15.57s → 4.277s（3.6×）**，内存峰值 45.3MB → 44.2MB（剩余耗时为 openpyxl 两 sheet 万行写入本身）；数据见 `scripts/perf_export_baseline_5000_after_c2.json`。
- **生效确认**：已确认（2026-09-30）——推送 `9fa0468` 后 `WMS CI #1321` / `WMS AI Verification #1616` / `WMS Perf Baseline #176` 全绿；本改动为 Python 路由代码，**生产需重启 WMS 服务生效（R3）**。
- **关联**：`app/routes/report.py` `report_inout_print`、P0 计划 §三 C2'、M1 基线 E2。

### BUG-2026-09-30-005（2026-09-30，/api/query/search 无 LIMIT 无分页，5000 物料单请求 4.73s/664KB 全量返回）

- **发现方式**：M1 C1 性能基线实测（`scripts/perf_export_baseline_5000.json` E4）——宽关键词（"M"）命中全部 5000 物料时，单请求返回全量行：4.73s / 响应 664KB / 内存峰值 23.3MB，违反 AGENTS.md §七 R1（列表接口必须让调用方显式知晓取的是"前 N 条"或显式翻页取全）。
- **根因**：`app/routes/stock_query.py` `api_query_search` 查询链 `.order_by(Material.code.asc()).all()`——无 LIMIT 无分页元数据，命中数即返回数。
- **R6 同类点排查**：全仓 grep `/api/query/search` 消费点——无前端模板/静态 JS/Android 消费（仅 `scripts/e2e_purchase_flow_10sets.py` e2e 助手与 3 个测试文件引用，均为小结果集，不受默认 limit=100 影响）；`mobile.py:161 _search` 已有 `.limit(5)`；`native_api` 各搜索端点均带 limit。无其他同类漏网点。
- **修复**：探测式有界分页——`limit` 表单参数（默认 100、上限 500、下限 1、非法值回退 100），查询取 `limit+1` 条判断 `has_more` 后截断（免 COUNT 全表扫描）；响应增加 `limit` / `has_more` 元数据字段，调用方可按 R1 显式知晓"仅前 N 条"。命中排序（Material.code 升序）、仓库级库存口径（INV-AUDIT-004）零改动。
- **回归**：新增 `tests/test_bug_2026_09_30_005_query_search_limit.py`（A9）6 项：默认 100+has_more / 自定义 limit / 上限钳 500 / 非法回退 / 小结果集全量返回+字段完整性 / code 升序首页。
- **回退验证（R8 第 3 条）**：cp 备份法回退修复后 6 项全失败（limit/has_more 字段不存在+全量返回）→ 恢复后全过，锁有效性实证。
- **修复后实测**：5000 物料宽关键词 **4.73s/664KB → 0.108s/12.6KB（44× 提速，内存 23.3MB → 0.7MB）**，数据见 `scripts/perf_export_baseline_5000_after_c4.json`。
- **生效确认**：已确认（2026-09-30）——推送 `74fbe73` 后 `WMS CI #1322` / `WMS AI Verification #1617` / `WMS Perf Baseline #177` 全绿；Python 路由代码，**生产需重启 WMS 服务生效（R3）**。
- **关联**：`app/routes/stock_query.py` `api_query_search`、AGENTS.md §七 R1、P0 计划 §三 C4、M1 基线 E4。

### BUG-2026-09-30-006（2026-09-30，/report/stock/print 硬编码版式路径 m.category 逐物料懒加载 N+1）

- **发现方式**：M1 C1 基线 E1（5000 物料 2.68s/20.7MB 线性增长）+ C2' 同模式排查——`report_stock_print` 查询仅 `joinedload(Material.unit)`，循环体 `m.category.name` 走懒加载；物料**有分类**时每物料触发 1 次 SQL（5000 物料 = 5000 次额外查询）。
- **重要口径说明**：物料 category_id 为 NULL 时 SQLAlchemy 跳过 many-to-one 懒加载查询——M1 基线造数不配分类，故 E1 基线耗时中不含此 N+1（本次修复后复测 2.68s→2.44s 仅 9%，余量为 openpyxl 万行写入+主查询+库存聚合，属写入侧固有成本）。**真实生产物料普遍配分类，N+1 实际触发**，本修复消除该场景的 5000 次查询（回归锁实证：60 物料各配独立分类，修复前 ~70 条 SQL，修复后 ~10 条）。
- **R6 同类点排查**：grep `app/routes/` `joinedload(Material.unit)` 无 category 预加载的同款查询——`report_stock_print` 模板路径（只访问 unit，不触 category）与本处共 2 处，仅本处需修；其余 Material 循环消费点均已有完整预加载或走分页。
- **修复**：硬编码版式路径查询追加 `joinedload(Material.category)`。导出内容、库存口径（BUG-2026-08-12-005 仓库级）、预警列零改动。
- **回归**：新增 `tests/test_bug_2026_09_30_006_stock_print_category_n_plus_one.py`（A9）：① 查询计数锁——60 物料各配独立分类导出 SQL ≤20（修复前 ~70）；② 内容锁——「分类」列全集显示分类名。
- **回退验证（R8 第 3 条）**：cp 备份法回退修复（git checkout 仅回退本改动，不影响已提交的 C2'）后锁失败 → 恢复后通过。
- **修复后实测**：5000 物料（无分类造数）2.68s→2.439s；有分类场景查询数 ~N→~2（锁实证 60:70→10）；数据见 `scripts/perf_export_baseline_5000_after_c3.json`。注：基线脚本造数不含分类，未覆盖该 N+1 场景，后续如需可扩展 seed 加分类（本条不扩展，避免基线口径漂移）。
- **生效确认**：已确认（2026-09-30）——推送 `15f034c` 后 `WMS CI #1323` / `WMS AI Verification #1618` / `WMS Perf Baseline #178` 全绿；Python 路由代码，**生产需重启 WMS 服务生效（R3）**。
- **关联**：`app/routes/report.py` `report_stock_print`、P0 计划 §三 C3、M1 基线 E1、BUG-2026-09-30-004（同模式）。

