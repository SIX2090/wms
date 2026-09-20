# WMS 完善现有功能开发计划

> 编制日期：2026-09-19 | 依据：代码/文档实测探查 + 台账/审计/BUG 台账交叉核证
> 范围：**不新增功能**，只完善现有系统，把"能用"做到"好用、实用、稳用"。
> 治理基调（来自 `WMS_BUSINESS_SCOPE.md` / 台账 §11）：一个人用，不搞复杂；巩固现有而非堆新功能。

---

## 0. 现状一句话

核心库存 Web 链路已较扎实（三工作流 CI 绿、pytest 1700+、A1–A12 lint 全过），**但系统处于"低配单机硬撑 + 存量多仓口径没清完 + Android 端靠用户现场当测试环境 + 部分页面交互粗糙"的亚健康状态**。BUG 月产量 78–241 条的供给源不是功能不够，是**运行时验证缺失**和**同一根因反复复发**。

---

## 1. 任务分级逻辑

| 级别 | 含义 | 判断依据 |
|---|---|---|
| **P0** | 不修就会继续发生产 BUG | AGENTS.md A11/R2/R4 点名、台账明确挂账、09-13 审计列为 P0 |
| **P1** | 修了立刻提升日常实用度 | 高频操作页面的交互缺口、必填空判、空状态缺失 |
| **P2** | 长期减债，降低未来 BUG 供给率 | 运行验证、压测基线、债务收敛 |

所有条目均须遵守 `AGENTS.md` 第三节的 **atomic action 粒度**（1 commit + 1 push、可独立 revert、自带测试）与**开工前 CI 全绿门禁**。

---

## 2. P0 — 收口现存生产 BUG 风险

> 目标：把台账/审计反复点名的根因**彻底掐死**，而不只修报告的那一处。

### P0-1 存量全局总账校验清零（A11 / R2，09-13 审计 P0）

- **问题**：仍有约 20 处业务路径用 `material.stock`（总账）而非仓库级口径做库存校验，存在"A 仓掩护 B 仓"可能。
- **实测证据**：`app/app.py` 内仍含 46 处 `material.stock` 引用（含读路径与注释）；`after_sale_out.py / adjustment.py / check.py / in_order.py / material.py / mobile.py / purchase_request.py / stock_query.py` 各有 1–8 处。
- **行动**：
  1. 按 09-13 审计 §5 路线图，把存量 `material.stock` 校验逐点迁移到 `get_warehouse_stock_quantities()`，**每类单据一个 atomic action**（销售出库、调拨、盘点、售后、领料等），配双仓隔离回归测试。
  2. 迁移过程中同步消除白名单残留，使 A11 lint 对**全量代码**（不止新增行）生效。
- **验收**：双仓并发场景下库存校验不出现跨仓误判；`scripts/lint_wms_rules.py` 全量扫描无存量违规。

- **✅ 已完成（2026-09-20，3 个 atomic action，已推送 origin/main）**：
  用 A11 规则同口径对全仓做**全量扫描**（非仅新增行），实际校验语境违规共 **20 处**
  （计划原文"8 个文件各有 1–8 处"是 raw grep 口径，含大量展示用途；A11 校验语境口径下
  仅 `app/app.py` 12 处 + `app/routes/in_order.py` 8 处）。逐点甄别：**2 处真违规迁移 +
  17 处存量兜底/报表口径豁免**（app.py L17542 一行含 2 个匹配）。
  - **1/3 `1900a54`**：`api_subcontract_quick_issue` 预校验全局 → 仓库级（与扣减端
    `deduct_stock_atomic` BUG-2026-09-19-001 严格对齐；未归属兜底同判据；仓库无效提前拒绝）。
    回归锁 `tests/test_p0_1_subcontract_quick_issue_warehouse_stock.py`（4 项）。
  - **2/3 `2379018`**：`api_ai_sales_order_anomaly_analysis` 缺货风险全局 → 订单仓库口径
    （只读提示；未归属/无仓库回退全局保持旧行为）。
    回归锁 `tests/test_p0_1_sales_order_anomaly_warehouse_stock.py`（4 项）。
  - **3/3 `fcce2bc`**：17 处存量引用补 `stock-truth:reason=` 豁免注释
    （in_order.py 8 处 BUG-2026-08-17-002/08-18-002/08-18-002-fix 登记兜底；
    app.py 单仓兜底 1 处 + AI 分析/健康度只读报表 8 处）。
  - **验证**：A11 全量扫描违规 **20 → 0**；反提交/兜底链路 31 项回归全绿；
    委外/售后/AI 销售相邻回归 25+4+2 项全绿；两个迁移 commit 的 pre-commit 钩子均 0 违规。
  - **遗留子项**：`lint_wms_rules.py` 的 A11 仍是"新增行生效"模式（存量已归零、无白名单残留），
    是否把 A11 升级为全量硬门禁（CI 直接跑全量扫描）留待 P2 运行验证批次一并评估。

### P0-2 生产安全基线收敛（唯一真未修复项 + 两处加固）

- **问题**：台账明确登记 **BUG-2026-07-31-002**（main 分支保护未启用）是唯一真未修复项；另有两处安全加固被用户拍板"暂缓"（明文令牌 08-16-010、弱口令策略 08-16-011）。
- **行动**：
  1. **分支保护**：在 GitHub 设置里为 `main` 启用 PR 与状态检查（免费私有仓库只能依赖本地 pre-push 钩子 + CI，见 AGENTS.md §4；但公开仓库可直接启用）。
  2. **会话安全**：`config.py` 生产分支强制 `SESSION_COOKIE_SECURE=True` + 启动自检告警（09-13 审计 AUDIT-003）。
  3. **令牌**：把暂缓的"明文令牌"改为启动时生成一次性 token 文件 + 打印一次性并即时隐藏（保留运维便利，又不留明文）。
- **验收**：GitHub 侧确认 `main` 受保护；生产启动时日志出现 `SESSION_COOKIE_SECURE ok`；间接登录日记不会落明文令牌。

- **✅ 已完成（无需新开发，2026-09-20 源码核实）**：两项内容在计划编制当日/次日的 BUG 修复系列中已落地——
  - **会话安全**（行动 2）= **BUG-2026-09-19-003**：`validate_production_security_config` 生产硬门禁
    （未设 `SESSION_COOKIE_SECURE=true` 且未显式 `WMS_ALLOW_INSECURE_COOKIE=1` 则 `raise` 拒绝启动）
    + 显式放行后启动期告警升级为 CRITICAL 并点名放行依据 + 部署清单条目。
    开机首行 `config-check: ... session_cookie=...` 输出由 **BUG-2026-09-20-001**（启动自检）提供，
    覆盖"启动日志出现 SESSION_COOKIE_SECURE 状态"的验收。
  - **明文令牌**（行动 3）= **BUG-2026-09-19-004**（08-16-010 暂缓项按预案落地，比原行动更完整）：
    sha256 哈希入库 + 签发/重置仅一次性返显明文 + 存量明文首次使用原位升级（平滑迁移，App/打印代理零变更）
    + 页面与部署包回显收口。
  - **分支保护**（行动 1）：**2026-09-20 用户明确不做**（免费私有仓库本就无法强制，AGENTS.md §4 已述）。
  - **验证（2026-09-20）**：`test_production_security_config.py` + `test_bug_2026_09_19_004_token_hash_storage.py`
    + `test_bug_2026_09_20_001_startup_self_check.py` + `test_bug_2026_09_20_004_ci_cookie_optin.py`
    合计 **39 项全绿**。
  - **P0-2 状态：清零**（无新增代码，本登记为 docs 同步）。

### P0-3 修复→生效闭环确认（R3 反复模式）

- **问题**：AGENTS.md 与台账反复出现"改了没重启/没装新包"（R3、R4 共 23+ 条），修复与生效之间没有确认回路。
- **行动**：
  1. 启动时把**版本号、配置项、关键迁移状态**写入日志并打印开机自检结果（可作为 `scripts/health_check.ps1` 的服务端版本）。
  2. 给 `AGENTS.md` R3 补一条机械化防护：模板/路由改动后自动生成"重启 WMS 服务生效"的提示通过启动 banner 输出，并在 `WMS_BUG_BASELINE.md` 登记时强制填"生效确认人/时间"。
- **验收**：启动日志第一行出现 `wms vX.Y.Z config-check: ...`；R3 类 BUG 登记必填生效确认字段。

- **✅ 已完成（无需新开发，2026-09-20 源码核实）**：两项在计划编制次日已落地——
  - **启动自检**（行动 1）= **BUG-2026-09-20-001**：新增 `app/version.py`（日期基 semver）与
    `app/startup_check.py`——启动日志第一行落 `wms vX.Y.Z (<git短SHA>) config-check: env=…;
    session_cookie=…; csrf=…; secret_key=…; db=…`（只报状态不报敏感值），`initialize_database`
    后落 `db-check`（迁移哨兵缺失报 `missing:` 不阻断），控制台 banner 同步。
  - **生效确认强制字段**（行动 2）= **BUG-2026-09-20-002**（A13 机械化）：`lint_wms_rules.py`
    A13 规则——台账新增 BUG 条目必须含「生效确认」字段（允许「待确认」占位），pre-commit 拦截。
  - **验证（2026-09-20）**：`test_bug_2026_09_20_001_startup_self_check.py` 8 项 +
    `test_lint_wms_rules_a13_golden.py` 3 项全绿（后者需 PATH 含 git，fixture 起临时仓库）。
  - **P0-3 状态：清零**（无新增代码，本登记为 docs 同步）。

---

## 3. P1 — 做好用：高频页面的交互完善

> 目标：不新增功能，只把现有页面从"能用"提到"好上手、不出错"。

### P1-1 仓库/库位必填落地缺口（AGENTS.md §二）

- **⚠️ 原 4 条描述全部过时（2026-09-20 源码核实）**：
  | 页面 | 原描述 | 实测结论 |
  |---|---|---|
  | `subcontract_issue.html` / `subcontract_receive.html` | 表单根本不带仓库字段 | **已完成**：`required` + 默认仓 selected + JS 校验；后端必填 + `assert_warehouse_active` + 仓库级库存口径 |
  | `opening_stock.html` | 无 required、无默认 selected | **已完成**：默认仓 selected + AI-OS-MW-001 表头/明细仓库兜底 + 库位必填（BUG-2026-09-16-011） |
  | `transfer.html` | `to_warehouse` 没选中默认仓 | **刻意设计**：原生 submit 校验生效（`type="submit"` + `required` 浏览器先拦）；后端拒同仓（L253）——调入仓必须主动选择，给默认仓反而会造同仓废单 |
  | `in_order_push.html` | 无 warehouse 字段靠后端补齐 | **继承源单仓库是正确设计**（从哪个仓入就从哪个仓出）；真缺口只有下面这一条 ↓ |

- **真缺口（已修，2026-09-20）**：`in_order_push` 下推目标草稿直接继承 `order.warehouse`，
  来源单无仓库时会写出**空仓库死单草稿**（出库/售后出库完成时仓库必填，永远无法完成）。
  - 后端 `create_in_order_push`：来源单无仓库 → 400 拒绝，不允许静默写空仓库
  - 前端 `in_order_push.html`：无仓库时顶部警示 + 禁用「创建目标草稿」按钮
  - 回归锁 `tests/test_p1_1_in_order_push_warehouse_required.py`（4 项：拒绝 / 有仓库控制组 / 页面两态）
  - 本地 `589ea7d` / 远端 `1f198e0`

- **P1-1 状态：清零**。

### P1-2 新建类大表单本地必填

- **⚠️ 原描述有误（2026-09-20 源码核实）**：原文写「4 个页面全页 `required=0`，提交后靠 JS `alert()` 一次性报错」。
  实测这四个页面**一个 `alert(` 都没有**；`sales_order_add.html` / `sales_order_edit.html` 早已具备
  `save()` 包装 + `showValidation(messages)` 面板的「一次收集全部」机制，只是校验项只有 2 条。
  真正缺的只有 `purchase_order_add.html` 与 `after_sale_out_add.html` 两个页面。
- **另有一处反直觉**：这些页面的保存按钮都是 `type="button"`，表单**从不原生提交**，
  所以模板上的 `required` 属性自己不会拦人——必须配套 JS 才会真的生效。
  （`after_sale_out_add` 的仓库/库位早就是 `required`，旧 JS 却只校验仓库，库位的红色星号形同虚设。）
- **行动**：表头补 `required`；明细行数量 `min` 由 `0` 改 `0.01`（单价仍允许 0，赠品场景）；
  保存前一次收集全部问题 → 面板列出全部 → 一次性高亮（`wms-row-error` / `wms-cell-error`）；
  表头校验直接读 `[required]`，杜绝「属性写了但 JS 不认」的假必填。
- **验收**：缺字段时一次指出全部遗漏项，且点击条目可定位到出错字段；不再逐条提示。

- **进度（2026-09-20 第 1 批）**：`purchase_order_add.html`（本地 `3948923` / 远端 `1cbd7d5`）
  - 采购日期、供应商加 `required`；数量 `min` 0 → 0.01
  - `submitForm` 由「逐条 showToast + return」改为一次收集全部错误
  - 新增 `wms-validation-panel` 面板（沿用 `in_order_add.html` 的成熟契约）+ 一次性高亮
  - 回归锁 `tests/test_p1_2_purchase_order_validation.py`（15 项）
- **进度（2026-09-20 第 2 批）**：`after_sale_out_add.html`（本地 `2dc5fc4` / 远端 `f1f5ee9`）
  - **关键修复**：旧实现把 `return` 写在明细行 `for` 循环**内部**，第 1 行数量为空就退出，
    后面 29 行根本不检查；改为一次遍历同时产出明细与全部行级错误
  - 日期、客户名称加 `required`；数量 `min` 0 → 0.01
  - 表头校验直接读 `[required]` → 仓库/库位的红色星号从此真的拦得住
    （库位仅在 `location_management_enabled` 开启时渲染，与后端 `BUG-2026-08-16-014` 口径一致）
  - 回归锁 `tests/test_p1_2_after_sale_out_validation.py`（17 项）
- **R3 生效注意**：改的是 Jinja 模板，Flask 非 debug 下模板缓存不会自动失效，**必须重启服务才看得到新校验**。
- **未纳入**：`sales_order_add` / `sales_order_edit` 已具备「一次收集」框架，仅校验项偏少
  （只校验客户 + 至少一条明细），留待后续按需扩充，不在本次 P1-2 范围。

### P1-3 空数据页面"只剩表头"（影响日常实用第 1 位）

- **实测缺口**：委外进度、库存预警、物料、批量导入、打印路由等列表页在 `_无数据_时只剩一个 `thead`，分不清"加载失败"还是"真没数据"（子代理统计：`subcontract.html`、`warehouse.html`、`in_order_push.html`、`document_ocr.html`、`batch_import.html` 等）。
- **行动**：给这些列表页加 Jinja `{% else %}` 空态（"暂无数据/点击新增"），不动逻辑。
- **验收**：无数据页明确显示空态文案；有数据照旧。
- **进度（2026-09-20）**：第 1 批已落地 —— 委外三页主列表（`subcontract.html` colspan=12、`subcontract_issue.html` colspan=9、`subcontract_receive.html` colspan=11）。
  - 回归锁 `tests/test_p1_3_subcontract_list_empty_state.py`（10 项：空态存在 / colspan 与 `<th>` 数一致 / 空列表渲染空态、有数据不渲染 / 文案必须在模板源码里）。
  - 本地 `9176eb6`，远端 `552eff88`；`pytest tests/test_p1_3_subcontract_list_empty_state.py` 10 passed、委外相关 29 项全过、`lint_wms_rules.py` 0 违规。
  - **R3 生效注意**：改的是 Jinja 模板，Flask 非 debug 下模板缓存不会自动失效，**必须重启服务才看得到空态**（测试里用独立 `Environment` 渲染，不受缓存影响）。
- **进度（2026-09-20 第 2 批）**：全仓用**正确判据**重扫后补齐 7 处真缺口（本地 `f5eb05f` / 远端 `d0889ee`）：
  `print_in.html`(9) / `print_out.html`(9) / `print_in_with_excel.html`(9) / `print_out_with_excel.html`(9) /
  `print_in_with_html.html`(8) / `sales_report.html`(11，钻取卡片) / `document_table_form.html`(5，批次扫码)。
  - 两个 `_with_excel` 变体另需把「补 8 行空白」的填充循环用 `{% if order.items %}` 包住，否则空态行后会跟 8 行空格。
  - `sales_report` / `document_table_form` 的整表被 `{% if 集合 %}` 包住，空数据**整块消失**（比"只剩表头"更隐蔽），
    故守卫分别放宽为 `{% if drill_material_code %}`、`{% if batch_meta.scans is defined %}`，让 `{% else %}` 有机会渲染。
  - 回归锁 `tests/test_p1_3_remaining_list_empty_state.py` 30 项。
- **⚠️ 第 1 批的「遗留子项」清单是错的**：当时判据只认 `{% for %}` 块内的 `{% else %}`，
  把 `ai_feedback_review.html` / `_list_macros.html` / `ai_ops_dashboard.html` / `opening_stock_list.html`
  **误判为缺口**——它们其实都有空态，只是写在 `<table>` **外面**（`{% if 集合 %}`…`{% else %}`）或 `{% endfor %}` 之后
  （`{% if not 集合 %}`）。空态至少有三种合法写法，扫描时必须都认。
- **进度（2026-09-20 第 3 批，P1-3 收口）**：剩下 2 处是 **JS 拼 HTML** 的列表，加不了 Jinja `{% else %}`，
  改在 JS 分支里补（本地 `c08b4b4` / 远端 `aa5168a`）：
  - `batch_import.html`：`renderOpeningStockPreview()` 里 rows 为空时，tbody 补「预检结果为空：文件里没有解析到任何数据行」
    （colspan=7，与 JS 里 thead 的 7 列实测一致）。
  - `document_ocr.html`：`renderResult()` 里给 items 的非空判断补 `else if (res.items)` 分支，
    显示「未识别到物料明细行」；**用 `else if (res.items)` 而不是独立的 `if (!res.items.length)`**，
    否则 items 为 undefined（错误响应）时会误报。原有「整份结果为空」的兜底保留。
  - 回归锁 `tests/test_p1_3_js_list_empty_state.py` 12 项。pytest 无 JS 引擎，故锁**结构与口径**
    （守卫存在 / 空态行拼进 `tbl` / colspan == 实测 `<th>` 数 / 文案在分支内 / 文案必须在源码里），不断言实现细节。
  - **至此 P1-3 全仓清零**（第 1 批 3 处 + 第 2 批 7 处 + 第 3 批 2 处 = 12 处）。

### P1-4 业务页面 fetch 绕过统一层（孤立的 401/419 信号）

- **问题**：实测 `app/templates/*.html` 内 raw `fetch(` 共 311 处（含大量 GET），其中 `in_order_add.html:1920`、`out_order_add.html:1479` 绕过 `WMS.api`，导致 session 过期时列表静默失败、用户只能刷新页面。
- **行动**：把业务页面内**错误处理/401 跳转**的 GET 请求统一收口到 `WMS.api.get()`；纯静态资源 `fetch`（如 CSRF/登录）保留。
- **验收**：session 过期后任何页面列报错会统一跳登录页，不再静默。

- **✅ 已完成（2026-09-20，1 个 atomic action，已推送 origin/main）**：
  侦察发现原行动（前端 233 处逐一收口 WMS.api.get）**不可行也无必要**，改用单点治本方案——
  - **真缺口定位**：静默失败的根因不是"绕过 WMS.api"，而是**伪 API 路径**
    （`/warehouse/api/list`、`/material/api/all` 等，实测 **29 处 / 19 文件**）的 GET fetch
    不带 `X-Requested-With` 头 → `wants_json_error_response()` 不命中 → 未登录时后端按页面请求
    **302 到登录页** → 前端 `r.json()` 解析 HTML 失败静默。`/api/`、`/mobile/api/`、
    `/report/api/` 前缀的请求后端本就直接 401，由 base.html 既有全局 401/419 拦截器统一跳登录。
  - **不能收口 WMS.api 的实证**：`/warehouse/api/list` 返回 `{warehouses: [...]}` 裸对象
    （无 `status: 'success'` 包装），WMS.api.get 会误判为业务失败 throw；逐接口改后端契约
    侵入面大且影响既有消费点。
  - **解法（`bc1f7d7`）**：base.html 全局 fetch 拦截器对**所有同源请求**统一注入
    `X-Requested-With: XMLHttpRequest`（Headers/普通对象双形态、已有头不覆盖、外部 URL 跳过
    避免 CORS preflight 变更）→ 未登录 AJAX 统一拿到 401 JSON → 拦截器既有 401/419 处理
    confirm 跳登录。**1 处改动覆盖全部 29 处缺口及未来新增调用**，前端 233 处与后端路由零改动。
  - **回归锁** `tests/test_p1_4_fetch_interceptor_ajax_header.py`（8 项：行为契约——未登录
    伪 API 带头→401 JSON、不带→302 证明缺口真实；结构断言——注入/同源/双形态/不覆盖/CSRF 与
    401 保留）+ CSRF/会话/登录相关 35 项全绿；pre-commit 钩子 0 违规。
  - **R3 生效注意**：改的是 Jinja 模板（base.html 拦截器），**必须重启服务才生效**。
  - **P1-4 状态：清零**。前端 233 处 raw fetch 的"风格统一"无功能收益，不再推进；
    新增代码仍受 `lint_no_raw_post_fetch.py` 约束（非 GET 必须走 WMS.api）。

---

## 4. P2 — 减债与运行验证

> 目标：把"测试绿"从"证明正则锁住的源码形态"升级为"证明运行时不崩"。

### P2-1 业务接口压测基线（低配单机 + SQLite）

- **问题**：现有性能报告只是 AI 组件微基准（p95 0.0005–0.03ms），**证明不了业务接口快慢**。真实瓶颈散在台账：物料搜索 N+1（已修过一次 5.8x）、期初页整库内嵌物料 数 MB、waitress 线程与 2vCPU/2GB 脱钩、`database is locked` 排队。
- **行动**：
  1. 用脚本对 10 个最高频接口（库存查询、出入库列表、物料搜索、期初页、盘点）做 30 秒低压并发压测，输出 `scripts/perf_baseline.json`。
  2. 把该基线接入 CI 轻量任务（阈值告警而非硬门禁），回归时对比。
- **验收**：每次 commit 能知道"物料列表又慢了 20ms"这类回归。

- **✅ 已完成（2026-09-20，2 个 atomic action）**：
  - **1/2 `258d351`**：`scripts/perf_baseline.py`——临时 SQLite 文件库 + 确定性种子
    （1 默认仓 + 300 物料 + 300 期初流水，不碰生产数据），waitress 真实 HTTP 服务
    （非 test_client，测量含完整 WSGI/模板/SQL 链路），并发 2 × 每接口 3s（30s 预算）。
    10 个只读 GET 接口：首页/库存查询/入库列表/出库列表/物料列表/物料搜索 API/
    期初页/盘点列表/出入库报表/库存预警。`--compare` 逐接口打 p95 增量表，
    回归 >50% 且 >50ms 打 `::warning::`（退出码恒 0，`--strict` 才非零）。
    纯逻辑（percentile/summarize/regression_alerts）与 app 导入分离，
    `tests/test_perf_baseline.py` **11 项全绿**（A9）；A14 显式 opt-in 已含。
    首份基线入档（本机 3s 窗口 10 接口 0 错误，p95 12.9–48.9ms，git_sha 入档）。
  - **2/2 `ca3bd8c`**：`.github/workflows/perf.yml`——push/workflow_dispatch/每日
    UTC 18:45（错开 18:30 三门禁）；`--seconds 2 --compare` 仓库基线，超阈值打
    `::warning::` 注解；job 级 `continue-on-error` + 脚本回归恒 0 退出，**双重保证
    只告警不拦合并**；测量结果传 artifact 留存 30 天；不入三工作流全绿门禁
    （观测性任务）。基线更新为显式人为动作（本地全量跑后 commit，CI 不自动回写）。
  - **验证**：compare 模式本机实测——逐接口增量表正常输出（如「物料列表
    -16.02ms」）、回归判定无误报；pre-commit lint 0 违规。

### P2-2 Android 端运行时验证接入 CI

- **问题**：55 个"Android 测试"全是源码正则，抓不到运行时崩溃（冷启动闪退修 5 轮才定位）；09-14 才刚补 Robolectric 基础设施但**未进 CI 必过门禁**。
- **行动**：把现有 Robolectric 单测接入 `android-build.yml` 的 `testReleaseUnitTest` 必过门禁，不再"绿也能带病"。
- **验收**：CI 里 `Android APK Build` 显示 `testReleaseUnitTest` 通过，失败即红。

- **✅ 已完成（无需新开发，2026-09-20 源码核实）**：验收条件在计划编制前已逐条满足——
  - **Robolectric 基础设施**：`app/build.gradle.kts` 钉版 `org.robolectric:robolectric:4.14.1`
    + `includeAndroidResources = true`（JVM 上模拟 Android 运行时，可真实实例化 Room/ViewModel）。
  - **真实运行时单测已在跑**：`OfflineQueueStateMachineTest`（Robolectric + 真实 Room 库
    验证离线队列状态机）、`RetrofitClientSessionTest`（Robolectric）两个文件均
    `@RunWith(RobolectricTestRunner::class)`；另有纯 JUnit 逻辑测试
    `StockDailyPagerTest`（7 用例）与 2026-09-20 新增 `InOutDetailDateLogicTest`（7 用例）。
  - **必过门禁**：`android-build.yml` 第 87–89 行 `Unit tests (BUG-2026-08-16-021)`
    步骤跑 `./gradlew testReleaseUnitTest`，**无 continue-on-error**，失败即红；
    同 workflow 还有 `lintRelease` 静态检查门禁。
  - **CI 实证**：最近一次 main 运行 #655 @2ea773c2（2026-09-20T00:17Z）全绿
    = assembleRelease + lintRelease + testReleaseUnitTest 全部通过。
  - **P2-2 状态：清零**（无新增代码，本登记为 docs 同步）。

### P2-3 库存三账写入单点收敛（长债）

- **问题**：`add_stock` / `deduct_stock_atomic` **不自动同步库位账**，三账恒等式靠每个消费点手工双写。
- **行动**：把仓库级写入收口为**一个强制入口**（如 `warehouse_stock_service.apply(deltas)`），所有业务路径改道，A11 lint 全量生效。
- **验收**：任何入库路径不再裸调 `add_stock`/`deduct_stock_atomic`；恒等式 ①=Σ②=Σ③ 现量、静态、增量三口径校验通过。

- **进度（2026-09-20 更新）：判据、侦察、唯一缺口修复已完成；收敛主体（单一入口 + 分批改道）待实施**
  - **为什么先做判据**：恒等式 ①=Σ②=Σ③ 此前**没有任何工具能验证**，直接收敛 23 个写入点
    无法判断改前/改后是否账实一致。故先交付校验器，再动手术。
  - **判据（`1 个 atomic action`）**：`scripts/verify_inventory_identity.py`——纯函数可单测
    + `--db` 扫真实库（只读零写）；两维度分开报（①vs② 硬失败 / ①vs③ 列待确认）；
    `tests/test_inventory_identity_checker.py` **9 项全绿**；真实库冒烟：构造
    stock=100 + 库位账 60 的分裂场景，校验器正确报 delta=40 ✅；A14 显式 opt-in。
  - **全量侦察结论**：`add_stock`/`deduct_stock_atomic` 业务调用点 **29 → 排除函数定义与
    旧包装 `deduct_stock()` 后 23 个**，分布 9 个文件（app.py 5 / in_order 6 / subcontract 5 /
    out_order 3 / adjustment 4 / after_sale_out 2 / mobile 2 / requisition 1 / native_api 1）。
    **22 处已按「两层同时写」正确双写，仅 1 处真缺口**——委外发料 `app/app.py:7218`
    只扣总账不扣库位账，已登记 **BUG-2026-09-20-008**。
  - **进展（2026-09-20）**：BUG-2026-09-20-008 已修——库位键口径经用户拍板
    （`issue.location or issue.warehouse`，与反提交端 `subcontract.py:1380`
    BUG-2026-08-16-001 逐字一致），修复提交 `eafec63` + 生效确认回填 `ec56acc`，
    推送后三工作流全绿（Android #661 / AI 验证 #1445 / WMS CI #1150）；回归锁
    `tests/test_bug_2026_09_20_008_subcontract_issue_location_sync.py` 4 项，
    回退验证已证锁有效（修复前第 1/4 项失败）。
  - **进展（2026-09-20 批 1）**：单点入口已落地——`app/services/warehouse_stock_service.py::apply_stock_delta(material, delta, *, transaction_type, ...)`：
    delta>0 → `add_stock`、delta<0 → `deduct_stock_atomic`、==0 不写账；开库位管理时
    同步 `update_location_inventory(material, location or warehouse, delta)`。
    **纯包装不重写**（BUG-2026-09-19-001 兜底、原子扣减、无记录报错全部保留）。
    **adjustment 4 处首批改道**（complete adjustment_in/out + revert delta 取负对称），
    本地 `787aea1`+导入布局修复 `187aff1` / 远端 `6528b3d8`+`6afb0093`
    （修复：services 按顶级包导入，BUG-2026-09-06-003 生产布局 app 非包）；
    服务层测试 `tests/test_warehouse_stock_service.py`
    8 项 + adjustment 现有回归 12 项 + 库存口径相邻 23 项 + 导入布局 T1/T2/T3 全绿，
    CI 实证 WMS CI #1159 / AI 验证 #1454 绿。
  - **进展（2026-09-20 批 2）**：in_order 全量改道——9 处写入点（complete 含自动下推
    领料 / update_completed 删·增·改量 / revert / batch_complete / batch_revert，
    含 3 处旧包装 `deduct_stock()`，比侦察口径的 6 处多 3 处）全部改经
    `apply_stock_delta`，提交 `d933c9d`。
    - **行为差异说明（纯重构的唯一口径变化）**：`delta==0` 统一为「不写任何账、
      直接成功」（入口既定语义）；存量 `add_stock(0)`/`deduct_stock(0)` 会报错
      「数量必须大于 0」。入库明细数量在创建/编辑校验时已强制 >0，实际路径
      不触发；该变化只会让"0 数量明细"这类脏数据不再导致整单完成失败。
    - **回归锁** `tests/test_p2_3_in_order_apply_stock_delta.py` 7 项：结构锁 2
      （in_order.py 禁裸调 5 原语 + 5 个路由函数按顶级包 `services` 导入）+
      行为锁 5（完成 / 反提交 / 批量完成反审 / 改量增减 / 删明细，开库位管理
      下真实路由断言①总账=③流水净额、②库位账同步、方向对称）。
    - **验证**：本批 7 项 + 相邻回归 28 项 + 全量 2392 passed（2 failed + 27 errors
      经复核为本机 PATH/git 子进程环境噪音，补全 PATH 后 39 项全过，与本改动无关）；
      pre-commit lint 0 违规；CI 实证 WMS AI Verification #1456 / WMS CI #1161 绿。
  - **进展（2026-09-20 批 3）**：out_order 3 处（complete / revert / batch_complete）
    + after_sale_out 2 处（complete / revert）全量改经 `apply_stock_delta`，提交 `da29ddf`。
    after_sale_out 的显式 `loc_dim` 口径与入口内部 loc_key 逐字一致，无行为差异。
    回归锁 `tests/test_p2_3_out_order_after_sale_apply_stock_delta.py` 6 项（结构锁 2 +
    行为锁 4：出库完成/反提交/批量完成双单、售后完成+反提交 三账一致）；
    相邻回归 54 项全绿；lint 0 违规；CI 实证 Android #675 / AI 验证 #1459 / WMS CI #1164 绿。
  - **剩余工作（批 4–5）**：subcontract（6，含 revert_receive 旧包装）→
    mobile + native_api + requisition + app.py（8），
    每类单据 1 个 atomic action，每批改完用
    `scripts/verify_inventory_identity.py` 复跑 + 双仓回归；
    收尾评估 lint 新规则禁止业务代码直调原语。

### P2-4 清理技术债信号（低风险）

- **行动**：把根目录约 27 个一次性 `_audit_*.py / _verify_*.py / fix_*.bat` 归档到 `scripts/archive/` 或注明"`generated-留存`"，减少新进入的人的噪音；不删。
- **验收**：根目录只剩 `AGENTS.md`、README、台账、规则、启动脚本等核心文件。

- **✅ 已完成（2026-09-20，3 个 atomic action，已推送 origin/main）**：
  实测根目录一次性文件共 **31 个**（比计划估计的 27 多 4），按类别分 3 批 `git mv`
  归档（100% rename 相似度，历史可溯，**只归档不删除**）：
  - **A 批 `abe6c83`**：审计/E2E 9 个（`_audit_*`×3 + `_audit_state.pkl` + `_browser_test_wms`
    + `_e2e_audit_*`×2 + `_wms_browser_e2e_*`×2）+ `scripts/archive/README.md`（归档说明）。
  - **B 批 `abfcac4`**：验证/压测 11 个（`_verify_*`×7 + `_bench_*`×3 + `_check_import_validations`）。
  - **C 批 `3b44684`**：演示/登录/报告/止血残留 10 个（`_demo_login` / `_full_demo`×2 /
    `_trae_login` / `_challenge` / `_generate_report` / `_render_evidence` / `fix_*.bat`×2 /
    `fix_picker_helper`）。
  - **例外留根目录**：`fix_p15_columns.py`——`tests/test_fix_db_columns.py` 活引用其
    `MIGRATIONS` 做"止血脚本与应用代码一致性"断言，属活依赖，已在 archive README 注明。
  - **验证**：归档前全仓 grep 引用排查（`_generate_report` 的 tests 命中为同名函数误报、
    `fix_inventory_check_columns` 的 tests 命中为 app/ 同名 .py，均非根目录文件）；
    归档后 `tests/test_fix_db_columns.py` **17 passed**；pre-commit lint 0 违规。
  - **P2-4 状态：清零**。

---

## 5. 执行节奏建议（不改台账架构，只提需求）

> 台账第 11 节显示"当前下一项：待用户指派"。本计划的任务**不替代台账**，而是作为本阶段指派的候选池。建议分批派活：

| 批次 | 内容 | 预计 atomic action 数 | 依赖 |
|---|---|---|---|
| **第 1 批（本周）** | P0-1 总账清零 + P0-2 分支保护 + P1-1 委外/期初/调拨仓库必填 | 6–8 | 台账指派 + CI 全绿 |
| **第 2 批** | P1-2 新建表单 required + P1-3 空态 + P0-3 生效确认闭环 | 4–6 | - |
| **第 3 批** | P2-1 压测基线 + P2-2 Android Robolectric 进 CI | 3–4 | 第 1 批完成 |
| **第 4 批（长债）** | P2-3 三账写入收口 + P2-4 债务清理 | 4–6 | 前批回归稳定后 |

---

## 6. 每条行动的通用验收门禁（AGENTS.md 第三节）

1. 开工前 `python scripts/check_ci_green.py` 三绿，任一红即先修 CI 再动工。
2. 每个 atomic action：`commit` + `push`，推送后读取 `git log origin/main` 与本地 SHA 比对。
3. 符合 A1–A12 门禁 + 对应 R1–R7 自检（尤其 R2 多仓边界、R3 模板必注重启、R5 AI 确认边界）。
4. 修改后必须跑受影响模块的 pytest + `lint_wms_rules.py`，不得 `--no-verify` 跳过钩子。
5. 完成后在 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 登记完成日期、SHA、验证命令、结果、遗留子项。

---

## 7. 我核实过的数字（供引用）

| 指标 | 实测值 | 备注 |
|---|---|---|
| routes 模块 | 47 个文件 | 42 业务模块 + AI/.init |
| `app.py` 行数 | 31,900+ | 拆分进行中，仍留大量路由/库存原语 |
| `test_*.py` / `verify_*.py` | 302 / 176 | 测试以 BUG 回归驱动 |
| 模板 | 131 个 | 含 `_disabled_unused_20260506/` |
| 模板内 raw `fetch(` | 311 处 | 业务页缺口见 P1-4 |
| 台账BUG | 402 条、真未修复 1 条 | 09-14 更新 |
| 三工作流 CI | #602 / #1386 / #1091 全绿 | 2026-09-19 @611c1c9 |
| 最新 HEAD | `611c1c9` | 台账登记 AI-MOB-CRASH-01 |

> 本文件为**下一个 atomic action**（文档类）：你认为计划方向 OK 后，我把它 `commit + push` 到 `main` 并登记台账；不主张一次性全部开发，而是按第 5 节批次派活。