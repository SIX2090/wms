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

### P0-2 生产安全基线收敛（唯一真未修复项 + 两处加固）

- **问题**：台账明确登记 **BUG-2026-07-31-002**（main 分支保护未启用）是唯一真未修复项；另有两处安全加固被用户拍板"暂缓"（明文令牌 08-16-010、弱口令策略 08-16-011）。
- **行动**：
  1. **分支保护**：在 GitHub 设置里为 `main` 启用 PR 与状态检查（免费私有仓库只能依赖本地 pre-push 钩子 + CI，见 AGENTS.md §4；但公开仓库可直接启用）。
  2. **会话安全**：`config.py` 生产分支强制 `SESSION_COOKIE_SECURE=True` + 启动自检告警（09-13 审计 AUDIT-003）。
  3. **令牌**：把暂缓的"明文令牌"改为启动时生成一次性 token 文件 + 打印一次性并即时隐藏（保留运维便利，又不留明文）。
- **验收**：GitHub 侧确认 `main` 受保护；生产启动时日志出现 `SESSION_COOKIE_SECURE ok`；间接登录日记不会落明文令牌。

### P0-3 修复→生效闭环确认（R3 反复模式）

- **问题**：AGENTS.md 与台账反复出现"改了没重启/没装新包"（R3、R4 共 23+ 条），修复与生效之间没有确认回路。
- **行动**：
  1. 启动时把**版本号、配置项、关键迁移状态**写入日志并打印开机自检结果（可作为 `scripts/health_check.ps1` 的服务端版本）。
  2. 给 `AGENTS.md` R3 补一条机械化防护：模板/路由改动后自动生成"重启 WMS 服务生效"的提示通过启动 banner 输出，并在 `WMS_BUG_BASELINE.md` 登记时强制填"生效确认人/时间"。
- **验收**：启动日志第一行出现 `wms vX.Y.Z config-check: ...`；R3 类 BUG 登记必填生效确认字段。

---

## 3. P1 — 做好用：高频页面的交互完善

> 目标：不新增功能，只把现有页面从"能用"提到"好上手、不出错"。

### P1-1 仓库/库位必填落地缺口（AGENTS.md §二）

| 页面 | 现状（实测） | 行动 |
|---|---|---|
| `subcontract_issue.html` / `subcontract_receive.html` | **表单根本不带仓库字段**，只能依赖后端默认仓 | 添加 `name="warehouse"` `+ required` + 默认仓 selected；后端路由补必填校验 |
| `opening_stock.html` | 表头仓库无 `required`、无默认 selected 图 | `headerWarehouse` 加 `required`，并在加载时 带 `selected` |
| `transfer.html` | `to_warehouse` required 但**没选中默认仓** | 选中"默认仓"或提示必选 |
| `in_order_push.html` | 无 warehouse/location 字段，靠后端补齐 | 与同时期表单对齐：加 required + 默认值 |

- **验收**：每个表单本地保存时仓库非空即阻塞；双仓环境下委外发料/收料不再依赖默认仓兜底。

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

---

## 4. P2 — 减债与运行验证

> 目标：把"测试绿"从"证明正则锁住的源码形态"升级为"证明运行时不崩"。

### P2-1 业务接口压测基线（低配单机 + SQLite）

- **问题**：现有性能报告只是 AI 组件微基准（p95 0.0005–0.03ms），**证明不了业务接口快慢**。真实瓶颈散在台账：物料搜索 N+1（已修过一次 5.8x）、期初页整库内嵌物料 数 MB、waitress 线程与 2vCPU/2GB 脱钩、`database is locked` 排队。
- **行动**：
  1. 用脚本对 10 个最高频接口（库存查询、出入库列表、物料搜索、期初页、盘点）做 30 秒低压并发压测，输出 `scripts/perf_baseline.json`。
  2. 把该基线接入 CI 轻量任务（阈值告警而非硬门禁），回归时对比。
- **验收**：每次 commit 能知道"物料列表又慢了 20ms"这类回归。

### P2-2 Android 端运行时验证接入 CI

- **问题**：55 个"Android 测试"全是源码正则，抓不到运行时崩溃（冷启动闪退修 5 轮才定位）；09-14 才刚补 Robolectric 基础设施但**未进 CI 必过门禁**。
- **行动**：把现有 Robolectric 单测接入 `android-build.yml` 的 `testReleaseUnitTest` 必过门禁，不再"绿也能带病"。
- **验收**：CI 里 `Android APK Build` 显示 `testReleaseUnitTest` 通过，失败即红。

### P2-3 库存三账写入单点收敛（长债）

- **问题**：`add_stock` / `deduct_stock_atomic` **不自动同步库位账**，三账恒等式靠每个消费点手工双写。
- **行动**：把仓库级写入收口为**一个强制入口**（如 `warehouse_stock_service.apply(deltas)`），所有业务路径改道，A11 lint 全量生效。
- **验收**：任何入库路径不再裸调 `add_stock`/`deduct_stock_atomic`；恒等式 ①=Σ②=Σ③ 现量、静态、增量三口径校验通过。

### P2-4 清理技术债信号（低风险）

- **行动**：把根目录约 27 个一次性 `_audit_*.py / _verify_*.py / fix_*.bat` 归档到 `scripts/archive/` 或注明"`generated-留存`"，减少新进入的人的噪音；不删。
- **验收**：根目录只剩 `AGENTS.md`、README、台账、规则、启动脚本等核心文件。

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