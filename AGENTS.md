# WMS 项目规则（AGENTS.md）

> 本文件是 AI 代理处理本仓库时必须遵守的最高优先级规则，与 [`DEVELOPMENT_RULES.md`](./DEVELOPMENT_RULES.md)、[`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md)、[`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 配套使用。
> 修改本文件本身属于独立 atomic action（1 commit + 1 push）；新增/修订规则必须注明日期。

## 目录

1. [业务操作铁律（AI 行为边界）](#一业务操作铁律ai-行为边界)
2. [仓库与库位必填规则](#二仓库与库位必填规则)
3. [任务粒度与提交流程](#三任务粒度与提交流程) —— 含 [CI 全绿门禁（开工前置条件）](#三任务粒度与提交流程)
4. [分支与前端约束](#四分支与前端约束)
5. [AI 开发台账](#五ai-开发台账)
6. [防 BUG 规则 A1–A14](#六防-bug-规则a1a142026-07-31-新增)
7. [反复 BUG 模式清单与强制防护 R1–R8](#七反复-bug-模式清单与强制防护r1r82026-08-28-新增)
8. [受限网络环境的 GitHub 推送与拉取](#八受限网络环境的-github-推送与拉取2026-08-23-新增2026-08-26-修订2026-09-30-修订)
   - [8.0 通道实测与决策表（含"建议不要用"清单）](#80-通道实测与决策表2026-09-30-新增)
   - [8.1 推送通道决策：PAT 直通 → MCP 端点 → API 重放](#81-推送通道决策pat-直通--mcp-端点--api-重放)

## 一、业务操作铁律（AI 行为边界）

- AI 处理中文仓库单据必须优先使用强 OCR/图像理解能力，尤其是生成入库草稿的送货单。
- AI 可以创建和查看草稿，但提交/审核/完成/作废/删除必须保持人工操作，除非用户明确授权高风险操作。
- 微信文字或截图发货通知（如"明天发鑫达 6204轴承 100套，M8螺母 500个"）属于供应商发货通知，必须生成入库送货/采购收货草稿，而非采购申请。
- 采购入库单允许手工新增、编辑、保存和完成，采购订单仅作为可选来源，不得强制要求采购入库关联采购订单；存在来源采购订单时，仍须保留来源、数量和执行进度跟踪。
- 已完成入库单禁止直接删除；必须先由人工反提交，使单据回到草稿状态并准确回退库存，然后才允许删除草稿。详情页、列表页和后端接口必须执行同一规则。
- AI 不得修改、重置或设置任何用户账号密码（包括 admin bootstrap 密码），除非用户明确授权该具体操作。密码操作需要事先明确批准。
- 系统不得为任何账号（包括 bootstrap admin）自动生成随机密码。当 `WMS_BOOTSTRAP_PASSWORD` 未设置时，系统必须使用固定默认密码（'admin'）并给出警告，而非 `secrets.token_urlsafe` 等随机生成器。随机密码会让凭证对操作员不可见，违反密码透明原则。

## 二、仓库与库位必填规则

> 仓库（Warehouse）是物理存储设施，库位（Location）是仓库内部的细分储位。两者是不同层级的概念，不得混淆或互相替代。无论库位管理是否启用，仓库始终是必填项。

### 规则一：未开启库位管理

- **出入库单据**（采购入库、产品入库、其他入库、销售出库、领料出库、其他出库、售后出库、调拨、盘点、调整等）：**仓库是必填项**。未选择仓库时自动带入默认仓库（若已配置），无默认仓库则拒绝保存。
- **库存查询、出入库报表、库存台账**：**仓库是必填筛选项**。不指定仓库时不得返回数据。

### 规则二：开启库位管理

- **出入库单据**：**仓库和库位均为必填项**。未选择时分别自动带入默认仓库和默认库位（若已配置），无默认值则拒绝保存。
- **库存查询、出入库报表、库存台账**：**仓库是必填筛选项**（库位为可选筛选）。

### 适用范围

- 后端：所有出入库新增/编辑/完成/批量完成路由必须校验仓库（及库位）必填。
- 前端：所有出入库表单的仓库（及库位）字段必须加 `required` 属性，并默认选中默认值。
- 报表：库存查询、出入库报表、库存台账的查询入口必须将仓库作为必填条件，后端未收到仓库参数时返回空结果或 400。

## 三、任务粒度与提交流程

> 一个 **AI task** = 一个用户请求的目标（例如"修删除物料 BUG"、"清理 14 个过期文件"、"加一种导出格式"）。
> 一个 **AI task** = 1 个或多个 **atomic actions**（每个 atomic action 是可独立 revert、自洽能过测试的最小改动）。
> 任务粒度不同时，提交流程也不同：atomic action 各自独立 commit + push，AI task 整体在台账里标记完成。

- **CI 全绿门禁（硬性规则，2026-09-18 新增）**：**开始任何任务前**，必须先确认以下三个工作流在 `main` 上**最近一次运行**全部为绿色（`success`）：

  | 工作流 | 文件 |
  |---|---|
  | `Android APK Build` | `.github/workflows/android-build.yml` |
  | `WMS AI Verification` | `.github/workflows/verify.yml` |
  | `WMS CI` | `.github/workflows/ci.yml` |

  **任一非绿即不得开工**——禁止开始新的功能任务、禁止提交新的 atomic action；必须先定位并修复红色工作流，使其回到全绿，再继续原任务。

  检查方式（任选其一，推荐第一种）：

  ```bash
  # ① 一键检查（推荐）：三个工作流全绿退出码 0；任一非绿退出码 1 并列出失败项与链接
  python scripts/check_ci_green.py

  # ② 看板页人工确认（读"最近一次 main 运行"的状态，不要看历史里旧的绿）
  #    https://github.com/SIX2090/wms/actions
  ```

  为什么是硬性规则：
  - 本仓库 CI 是**唯一能在沙箱之外做真实编译**的环节（本地无 Android SDK，`Android APK Build` 是 APK 能否构建成功的唯一证据）；本地那 50 多个 "Android 测试" 全是**源码字符串正则**，抓不到运行时/编译期问题。CI 红着干活 = 在无编译证据的前提下改代码。
  - `main` 上留红色 = 后面所有人（含 AI）的基线都是坏的，"新引入的失败"与"存量失败"混在一起无法区分，回归测试的说服力归零。
  - 每天检查一次（三个工作流均带 `schedule` 每日定时触发，见各文件 `on.schedule`），保证即使当天没人推代码，也能发现依赖变更、上游镜像失效等**时间性故障**。

  与既有规则的关系：本条是**前置条件**，先于"atomic action 推送"生效；"推送验证/完成标准"仍是**后置条件**，两者叠加即：开工前全绿 → 做完本 action → 推送并确认新 SHA，下一轮开工前再次全绿。

- **结果验证**：完成每个 atomic action 后（以及 AI task 整体结束时），必须先验证结果（如检查服务状态、测试功能、确认输出正确性）再向用户汇报。未验证的结果不得当作完成汇报。
- **atomic action 推送（硬性规则）**：完成**每一个** atomic action 后——不是每个"AI task"之后——AI 必须 commit 并 push 结果到 `https://github.com/SIX2090/wms.git` 的 `main` 分支，除非用户明确说不要。

  atomic action 是一个自洽的改动：
  - 有单一明确目的（一个规则修复、一批文件清理、一个文档更新、一个函数重写等）
  - 可独立 revert（一次 `git revert <sha>` 即可干净回退）
  - 自身能通过 lint / 构建 / 相关测试（main 上不留半残中间态）
  - 有规范 commit message（如 `fix(scope): ...`、`chore: ...`、`docs: ...`）

  示例：

  > "修 AGENTS.md 措辞" = 1 atomic action → 1 commit + 1 push
  > "删 14 个过期文件" = 3 atomic actions（类别 A、B、C）→ 3 commits + 3 pushes
  > "更新 README 20 处" = 1 atomic action（单文档、单提交）→ 1 commit + 1 push
  > **错误**：为"省 push"把 5 个不相关的规则修复塞进一个 commit

- **推送验证**：汇报任何 atomic action 完成前，必须读取实际 `git push` 输出（`` To <url> ... -> main ``）并确认 origin/main 出现非空新 SHA。push 失败（网络、non-fast-forward、认证）则该 action 不算完成——rebase/pull、修复、重推后再汇报。
- **完成标准**：一个 atomic action 只有本地 `git log -1` 与 `git log origin/main -1` 显示相同新 SHA 才算完成。仅本地提交不算完成。

## 四、分支与前端约束

- **分支策略（硬性规则，无例外）**：AI/TRAE 必须直接在 `main` 分支工作。严格禁止创建、切换到或推送任何新分支——包括 `feature/*`、`fix/*`、`chore/*` 或任何 `trae/*` worktree 分支。所有 commit 和 push 必须指向 `main`。本地 pre-push 钩子 `.githooks/pre-push` 在客户端强制执行（**允许删除非 `main` 远程分支**——如 `trae/*` 残留分支可按需清理；仅 `main` 禁止删除，防止误删丢失全部历史；除 `main` 外禁止创建、切换或推送任何新分支）。注意：在 GitHub 侧强制分支保护需要私有仓库的 GitHub Pro；免费私有仓库只有本地钩子 + CI 两层强制。
- **业务 JS 禁止原生非 GET `fetch`**：`app/static/js/*.js` 中所有非 GET 请求必须走 `WMS.api.get/post/put/delete(url, data)`（定义于 `app/static/js/api.js`）。业务代码中**禁止**直接使用 `fetch()` 或全局 `csrfFetch` 包装。本地 pre-commit 钩子 `.githooks/pre-commit` 先运行 `scripts/lint_wms_rules.py`（A1-A14），再运行 `scripts/lint_no_raw_post_fetch.py`；两者会拒绝白名单之外包含 `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` 的提交。白名单文件（base.html 全局 fetch 拦截器、`app/static/js/api.js`、`app/static/js/app.js`）可使用原生 `fetch`，因为它们就是统一层。每次克隆后执行一次 `bash .githooks/install-hooks.sh` 启用钩子（等同于 `git config core.hooksPath .githooks`）。

## 五、AI 开发台账

- [`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 是唯一的 AI 开发待办与完成台账。实现任何 AI 功能前，先查其唯一任务 ID、当前状态、现有代码、测试、页面和 Git 历史；绝不重复开发已完成或等价能力。
- 每个 AI 代码变更必须映射到唯一台账任务 ID。新增任务前必须做全仓库查重；对已完成能力的修复必须使用子修复 ID，不得重复原任务。
- 标记 AI 任务完成的前提：代码、权限、人工确认边界、测试、文档、验证，**以及所有 atomic action 按上述推送规则完成提交推送**，全部齐备。立即在台账记录完成日期、提交哈希、变更模块、验证命令、结果和遗留子项。权限边界见 [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md)。
- 每个 AI 任务结束时，将台账与 AI 路由、工具、模型、模板、特性开关、迁移和验证脚本对账，确保已实现的能力不被遗漏、计划中的能力不被误报为已实现。

## 六、防 BUG 规则（A1–A14，2026-07-31 新增）

**修改本仓库任何代码前，请先阅读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md)；且**必须** `bash .githooks/install-hooks.sh` 启用 pre-commit 钩子，否则 14 条防 BUG 规则不会自动跑。**

> 2026-09-19 同步：本速查表补登 **A11**（禁止裸用总账做库存校验，R2 机械化防护），并将本节约的"10 条"统一校正为"11 条"，与 `scripts/lint_wms_rules.py` 及 [DEVELOPMENT_RULES.md §六](./DEVELOPMENT_RULES.md) 对齐。
>
> 2026-09-19 同步：本速查表再补登 **A12**（测试文件顶层禁止裸 app context `.push()`/`.pop()`，R7 机械化防护），并将"11 条"统一校正为"12 条"。
>
> 2026-09-20 同步：本速查表补登 **A13**（台账新增 BUG 条目强制「生效确认」，R3 机械化防护）与 **A14**（`scripts/` 下新增 app 引用必须显式放行生产硬门禁，R6 机械化防护），并将"12 条"统一校正为"14 条"，与 `scripts/lint_wms_rules.py`（实跑 A1–A14 共 14 条）及 [DEVELOPMENT_RULES.md §六](./DEVELOPMENT_RULES.md) 对齐。

### 14 条核心规则速查

| 编号 | 规则 | 防的 BUG |
|---|---|---|
| A1 | `<form method="post">` 必须有 csrf_token | 表单 400 / 死循环 |
| A2 | Python POST 路由必须 @login_required 或 @csrf.exempt | 漏 CSRF 保护 |
| A3 | 业务 JS 不能 console.log | 调试代码泄漏 |
| A4 | 业务 JS 不能 debugger/alert | 调试残留 |
| A5 | 业务 JS 不能 eval/new Function | XSS / 注入 |
| A6 | 业务 Python 不能 print | 调试代码污染日志 |
| A7 | SQL 必须参数化，禁止字符串拼接 | SQL 注入 |
| **A8** | **新增** POST/PUT/DELETE 路由必须用 pydantic `BaseModel` 输入校验 | 数据类型 BUG / 字段漂移 |
| **A9** | **新增** 业务函数必须在 `tests/` 至少 1 个对应 pytest 测试 | 未测试代码上线 |
| **A10** | **新增** `app/app.py` 禁止新增 `@app.route` 路由，强制走 `app/routes/` 模块 | app.py 重新膨胀 |
| **A11** | **新增** 禁止裸用 `material.stock`（总账）做库存校验，必须用仓库级 `get_warehouse_stock_quantities()`（双模式：pre-commit 查新增行 + CI `--full-a11` 全量硬门禁，2026-09-20 起） | 多仓库口径串仓 / 同根因反复 BUG |
| **A12** | 测试文件模块顶层禁止裸 app context `.push()`/`.pop()`（R7 机械化） | 全量 pytest 顺序依赖假失败 |
| **A13** | `WMS_BUG_BASELINE.md` **新增** BUG 条目必须含「生效确认」字段（R3 机械化） | 修复→生效无确认回路 |
| **A14** | `scripts/` 下**新增** app 引用的脚本必须显式放行生产硬门禁（R6 机械化） | 生产硬门禁漏排查消费点 → CI 变红 |

> A8/A9/A10/A11/A13/A14 是"新增代码生效"规则：仅对 `git diff --cached` 的新增行强制，存量代码不会一次性报几百条违规。其中 **A11 自 2026-09-20 起为双模式**：pre-commit 维持新增行生效，`WMS CI` 追加 `python3 scripts/lint_wms_rules.py --rule a11 --full-a11` 全量硬门禁（P0-1 存量清零后启用，违规即红）。详见 [DEVELOPMENT_RULES.md §六](./DEVELOPMENT_RULES.md)。

### 强制门禁

- pre-commit 钩子（`.githooks/pre-commit`）会扫描以上规则
- 启用：`bash .githooks/install-hooks.sh`
- 跳过（不推荐）：`git commit --no-verify`

### 修复 BUG 流程

1. 在 [`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md) 登记（`BUG-YYYY-MM-DD-NNN: <标题>`）
2. commit message 关联 BUG ID：`fix: BUG-2026-07-31-001 xxx`
3. 加回归测试
4. 改状态为"已修复"

## 七、反复 BUG 模式清单与强制防护（R1–R8，2026-08-28 新增）

> 台账统计显示，大量 BUG 是**同一根因在不同消费点反复出现**（锁×17、多仓库×11、合同×9、分页/翻页×11、重启×6）。以下 R 系列规则针对已实证的反复模式，凡改动落入对应场景必须逐条自检。R 系列以人工/AI 自检为主（R7 已由 **A12** 做 lint 机械化防护），与 A1–A14 并列执行。
>
> 2026-09-19 同步：本节补登 **R7**（测试模块顶层禁止常驻 push app context），并将标题"R1–R6"校正为"R1–R7"、正文"与 A1–A10 并列执行"校正为"与 A1–A11 并列执行"，与 [DEVELOPMENT_RULES.md §七](./DEVELOPMENT_RULES.md) 对齐。
>
> 2026-09-20 同步：本节新增 **R8**（修 BUG 不得引入新 BUG；修不好就别修），并把正文口径统一为 A1–A14。

### R1 分页默认值不得当业务上限（实证：BUG-2026-08-28-001、002 等 10+ 条同类）

- **禁止**：数据消费方（前端页面、Android App、AI 工具、脚本）调用列表/明细接口时依赖默认 `page_size` 就当作"全量"。
- **必须**：①显式传足够大的 `page_size` 并按响应 `total_pages` 翻页合并取全；或 ②调用方明确知晓并注释"仅取前 N 条"。
- **新接口**：必须返回完整分页元数据（`total` / `page` / `page_size` / `total_pages`）；汇总统计必须与分页解耦（汇总基于全集，列表基于分页）。

### R2 库存/出入库/报表改动必验多仓库边界（实证：08-16/08-17/08-23/08-27 系列 20+ 条）

改动涉及库存数量、出入库单据、报表聚合时，必须同时验证三个口径，缺一不算完成：

1. **多仓库隔离**：两个及以上仓库之间数据互不串仓（汇总=各仓库之和）。
2. **历史脏数据兼容**：历史 `warehouse`/`location` 为空或解析不到的记录不得导致"查不出来/库存不足"误判。
3. **汇总 = 明细**：报表合计行必须等于明细行全集之和，不得以分页/抽样数据近似。

> **口径定义与写入/读取规范见 [`INVENTORY_TRUTH.md`](./INVENTORY_TRUTH.md)**（三份数据的权威关系、派生方向、归属铁律）。
> **R2 的机械化防护是 A11**（`scripts/lint_wms_rules.py`）：禁止新增代码裸用 `material.stock`（总账）做库存校验，强制用仓库级 `get_warehouse_stock_quantities()`。这直接掐断"同根因在多个消费点反复复发"（2026-09-11 新增）。

### R3 模板改动必须标重启（实证：6+ 条"改了没生效"）

- 凡改动 `app/templates/*.html`（Jinja 模板），commit message 与 BUG 台账记录**必须注明「生产需重启 WMS 服务生效」**（生产模式模板有缓存）。

> **R3 的机械化防护（2026-09-20 新增，双件）**：①启动自检——服务启动日志/控制台第一行输出 `wms vX.Y.Z (<git短SHA>) config-check: …`，初始化后输出 `db-check: migrate=…`（`app/startup_check.py`，核对"跑的是哪份代码、什么配置"）；②**A13 规则**（`scripts/lint_wms_rules.py`）——`WMS_BUG_BASELINE.md` 新增 BUG 条目（`### BUG-…` 等标题）必须含「生效确认」字段（确认人/时间/核对方式，允许「待确认」占位），否则 pre-commit 拦截。

### R4 打印/写库链路必须降级兜底（实证：锁相关 17 条）

- 改动打印代理、写库心跳、Spooler/WMI 依赖路径时，必须处理 `database is locked`（busy_timeout + 低频重试 + 降级静默），禁止裸抛 traceback 刷屏；Windows 打印服务异常必须给中文操作指引，不得抛英文原生错误。

### R5 AI 功能必须留人工确认边界与失败回退（实证：AI 相关 12 条）

- AI 识别/解读/生成的新能力：**低置信度必须回退人工**，禁止 AI 结果不经确认直接写入业务数据；失败/不确定时明确告知"我不确定"，禁止编造输出。

### R6 新 BUG 登记前必查同根因历史

- 登记新 BUG 前必须 grep 台账查同模式历史 BUG；若判定为**同一根因的复发**，必须同时排查并修复**所有同类消费点**（不只修报告的那一处），并在台账注明"同类点已排查"。

> **R6 的机械化防护是 A14**（`scripts/lint_wms_rules.py`，2026-09-20 新增）：`scripts/` 下新增 app 引用（`from app import app` / `import app`）的脚本必须显式放行生产硬门禁（如 `WMS_ALLOW_INSECURE_COOKIE=1`），否则 pre-commit 拦截。实证 BUG-2026-09-20-004——生产 Cookie 硬门禁（BUG-2026-09-19-003）引入后只给 `tests/conftest.py` 补 opt-in，漏排查 `scripts/` 消费点，使 `WMS CI` 与 `WMS AI Verification` 在 main 上变红，违反 §三 CI 全绿门禁。

### R7 测试模块顶层禁止常驻 push app context（实证：全量 pytest 81~221 项顺序依赖假失败，2026-09-03 治理归零）

> **R7 的机械化防护是 A12**（`scripts/lint_wms_rules.py`，2026-09-19 新增）：扫描 `tests/*.py`，拦截列 0（无缩进）的 `ctx/context .push()/.pop()` 裸调用，跳过三引号字符串块，行尾 `# allow-ctx-push` 可豁免。

- pytest **先收集（import）全部模块、再执行**。测试文件模块顶层写 `_ctx = app.app_context(); _ctx.push()` 会在收集期把所有模块的 ctx 全部压栈，执行时再各自 pop 会把栈弹乱，残留 ctx 导致**后续模块**的请求内事务/系统设置读取异常，全量失败项随顺序漂移。
- **必须**：顶层只保留 `_ctx = app.app_context()`，用模块级 autouse fixture 包住 push/pop；新增测试文件若沿用 `_ctx` 模板，禁止顶层裸 `_ctx.push()`。
- 详见 [DEVELOPMENT_RULES.md §七 R7](./DEVELOPMENT_RULES.md)。

### R8 修 BUG 不得引入新 BUG；修不好就别修（净收益原则，2026-09-20 新增）

- **铁律**：一次修复的**净收益必须为正**。带病交付（修了 A 坏了 B）比不修更糟——
  未修的 BUG 在台账里看得见、有人盯；新引入的 BUG 要等用户在现场踩到才发现。
- **禁止**：
  1. 为让测试变绿而**放宽/删除既有断言**（改测试迁就代码 = 伪修复）；
  2. 修复后只跑"我自己新增的用例"就宣称完成；
  3. 明知引入新失败仍推送（"先推上去再修"）——**main 留红违反 §三 CI 全绿门禁**；
  4. 口径未定 / 涉及面过大 / 无法验证时硬改业务账务逻辑（此时**只登记**，见下）。
- **修复"完成"的定义（缺一不算完成，不得向用户报完成）**：
  1. **修复前基线**：先跑受影响模块全量测试，记录本来就红的项，
     避免把存量失败算到本次头上、也避免误判"修好了"；
  2. **回归锁**：新增针对本次 BUG 的用例；
  3. **回退验证**：**把修复回退后新用例必须失败**——否则这个锁锁不住任何东西
     （自证陷阱）。回退用文件备份法（先 `cp` 备份 → `git checkout --` → 跑测试 → `cp` 恢复），
     **不要用 `git stash`**（本环境 2026-09-20 曾因 stash 被 SIGTERM 中断导致仓库损坏）；
  4. **全量 + 相邻**：受影响模块全量 + 相邻模块回归 + `scripts/lint_wms_rules.py` 0 违规；
  5. **CI 实证**：本地无法真实验证的改动（典型：Android/Kotlin，本地无 Android SDK）
     **必须等 §三三工作流转绿**才算完成；未绿前不得报完成、不得开始下一个任务；
  6. **登记闭环**：BUG 台账写清根因/危害/修复/回归/**生效确认**（A13，允许"待确认"占位）。
- **修不好就别修**：若判定无法在可控范围内修好（口径需用户拍板、涉及面过大、
  缺少验证手段），**只做登记**——台账记根因与建议方案、生效确认写「待确认」、
  **代码一行不动**，等用户确认后再单独 atomic action 实施。
  （实证：BUG-2026-09-20-008 先登记待修、口径经用户拍板后才动账，未造成二次伤害。）
- **已经引入新失败怎么办**：立即 `git revert` 回滚本次修复、回到"已登记未修"状态，
  重新评估；**不允许带着红灯继续做下一个任务**（§三门禁）。
- **实证（同日两次教训，均为"本地看着绿就推送"）**：
  ① `InOutDetailReportScreen.kt` 中文是合法标识符字符，`"$label前一天"` 被解析成
  标识符 → `compileReleaseKotlin` 失败（本地无 SDK，只能由 CI 暴露）；
  ② P2-4 归档误迁 `fix_inventory_check_columns.bat`，归档前只按字符串 grep 引用查漏
  （测试用 `ROOT / "xxx.bat"` **拼接路径**，文件名不以完整字面量出现）→ CI 单测红灯才暴露。
- 详见 [DEVELOPMENT_RULES.md §七 R8](./DEVELOPMENT_RULES.md)。

## 八、受限网络环境的 GitHub 推送与拉取（2026-08-23 新增，2026-08-26 修订，2026-09-30 修订）

> **2026-09-30 修订摘要**：本机环境（Windows 实机，非沙箱）实测证明**常规 git 直连 `github.com` 完全可用**，§8.2 原"必须走代理前缀浅克隆"的结论已过时。本次修订新增 [§8.0 通道实测与决策表](#80-通道实测与决策表2026-09-30-新增)（成功/失败方法全记录 + 建议不要用清单），并把 §8.2 首选通道改为**直连浅克隆**。原代理通道保留作为降级路径，但标注"建议不要用"。

### 8.0 通道实测与决策表（2026-09-30 新增）

> 来源：2026-09-30 在 Windows 实机（非沙箱）上对 `SIX2090/wms` 的完整拉取实测，成功克隆到 `a5d27af`，1492 文件，耗时 2m17s。
> **环境前提会随时间和网络变化，用前必须重新探测**；但判别方法（见 §8.0.2）是稳定的。

#### 8.0.1 实测结果总表

| 通道 | 用途 | 实测结果 | 结论 |
|---|---|---|---|
| **github.com 直连 git**<br>`git ls-remote` / `git clone --depth 1` | 拉取 | ✅ **成功**，2m17s，约 52KB/s，HEAD `a5d27af` 与网页端一致 | **首选** |
| **codeload.github.com**<br>tarball 下载 | 拉取（无 git 历史） | ✅ 成功，6.08MB / 4m03s，1577 条目 | **备选**（见 §8.0.3） |
| **api.github.com 直连** | 校验 HEAD / 推送 | ✅ `HTTP 200`，无需 DoH 解析、无需写 `/etc/hosts` | **可用** |
| **ghproxy.net 代理前缀浅克隆** | 拉取 | ❌ **连续 3 次失败**（5m14s / 8m04s / 1m44s），均在 ~4MB 处 `early EOF` + `curl 18 transfer closed` | **建议不要用** |
| **gitclone.com** | 拉取 | ❌ `curl (35) CRYPT_E_REVOCATION_OFFLINE`（吊销服务器不可达） | **建议不要用** |
| **github.com（curl 探测）** | 探测 | ❌ `curl (52) Empty reply from server` → `000` | **误判，见 §8.0.2** |

> **"建议不要用"清单（2026-09-30 实证）**：`ghproxy.net` 代理前缀浅克隆、`gitclone.com`、以及**用 `curl` 判定 git 通道可用性**。
> 历史记录（2026-08-23）曾实测 `ghproxy.net` ✅，本次 3/3 全部失败——代理可用性随时间漂移，这正是必须重新探测的原因；但在直连可用的前提下，**不应再把代理作为首选**。

#### 8.0.2 判别方法纠正（关键，防止反复踩坑）

**禁止用 `curl` 判定 git 通道是否可用。** `curl https://github.com` 返回 `000` / `Empty reply from server` **不代表 git 不可用**——2026-09-30 实测中 curl 报 `000`，但同一时刻 `git ls-remote` 正常返回 `a5d27af35e241f0a2f6d9218f38591796d8b5cf5`，且直连浅克隆成功。

**正确判别命令（廉价、只读、秒级）**：

```bash
timeout 45 git ls-remote https://github.com/SIX2090/wms.git main
# 返回 "<SHA>	refs/heads/main" 且退出码 0 → 直连可用，直接 git clone，不要再折腾代理
# 报 gnutls_handshake / SSL_ERROR_SYSCALL / 超时 → 直连不可用，才降级到 §8.2 代理路径
```

决策顺序：**① `git ls-remote` 直连探测 → ② 通就直连浅克隆 → ③ 不通才走代理/API 通道**。跳过第 ① 步直接上代理，是本条修订要杜绝的做法。

#### 8.0.3 备选方案：codeload tarball（无 git 历史时的兜底）

当 git 协议彻底不可用、但 `codeload.github.com` 可达时，可用 tarball 拿代码（**该方法不含 `.git`，无法直接满足 §8.2 验证标准，仅作最后兜底**）：

```bash
# 1. 取准确的 main HEAD SHA（api.github.com 直连可用）
curl -sS -m 20 https://api.github.com/repos/SIX2090/wms/commits/main | grep -m1 '"sha"'
# 2. 直接下载该 SHA 的 tarball（实测 6.08MB）
curl -sS -L -o wms_src.tar.gz "https://codeload.github.com/SIX2090/wms/tar.gz/<SHA>"
# 3. 校验完整性（两步都必须过，否则重下）
gzip -t wms_src.tar.gz && tar -tzf wms_src.tar.gz > /dev/null && echo OK
# 4. 解压
tar -xzf wms_src.tar.gz && mv wms-<SHA> wms
```

> 用 tarball 兜底时：需自行 `git init -b main` + 提交基线 + `git remote add origin https://github.com/SIX2090/wms.git`，并**在汇报中明确说明本地 HEAD 与上游 HEAD 不一致**（内容一致，SHA 不同）。后续推送走 §8.1 API 通道（以远程 HEAD 为 parent，不依赖本地历史对齐）。

#### 8.0.4 其他环境事实勘误（2026-09-30）

| 项目 | AGENTS.md 原文 | 2026-09-30 实测 |
|---|---|---|
| 仓库可见性 | §8.1 提及"免费私有仓库" | **`visibility: public`**（公开仓库，读取无需 token） |
| 凭证脚本 | `~/.codebuddy/skills/github-connector/scripts/get_token.sh` | 本机**该路径不存在**；且无 `gh` CLI。需凭证时改用 GitHub 连接器或用户提供的 PAT |
| api.github.com | 需 DoH 解析 + 写 `/etc/hosts` | **域名直连即 200**，无需任何 hosts 改动 |

### 8.1 推送（通道决策：PAT 直通 → MCP 端点 → API 重放）

> 适用场景：向 `main` 推送 atomic action，且本机没有可直接复用的 git 写凭证。
> **2026-09-30 修订**：实测确认 **PAT 直通 `git push` 在本环境完全可用**（TLS 可通），故推送首选由"API 通道重放"改为 **PAT 直通 push**。原 API 四步重放保留为无 PAT 时的兜底，另新增 **MCP 本地端点通道**（无需 PAT 即可推送）。

**凭证获取（2026-09-30 实测）**：

| 来源 | 实测 | 说明 |
|---|---|---|
| **用户直接提供 PAT**（`ghp_` / `github_pat_` 前缀） | ✅ **唯一实测有效**，`GET /user` 返回 200，`git push` 认证通过 | 首选。由用户在对话中给出。若要免重复输入，可存本机 `~/.git-credentials`，但属**明文存盘**，须用户明确同意 |
| `~/.codebuddy/skills/github-connector/scripts/get_token.sh` | ❌ **本机路径不存在** | 2026-08-23/26 曾有效，当前环境已无此脚本；不要假设它还在 |
| GitHub 连接器 / GitHub MCP server | ⚠️ 其 Bearer token 对 `api.github.com` 直连返回 **401** | 该 token 只对 WorkBuddy 的 MCP 代理有效，**不能**当 PAT 用；但 MCP 工具本身可推送（见 §8.1.2） |
| `gh` CLI | ❌ 本机未安装 | — |
| Windows 凭据管理器 | ❌ 无 github 条目 | `credential.helper=helper-selector` 存在但无凭证，裸 push 报 `could not read Username` |

> 2026-08-26 实测**不可用**的凭证/通道（不要再试）：
> - `git-credential-helper`（向 `git.auth-proxy.local` 查询）→ 404「git credentials not found in space labels」
> - SSH over 443 → 本环境无部署公钥
> - ghproxy.net / gitclone.com 代理前缀 **push** → 代理只对 github.com 域名供凭证，push 会卡在 `could not read Username`；**代理只能用于拉取，不能用于推送**

**通道探测（按序尝试，以实测为准）**：

1. **PAT 直通 push（首选，2026-09-30 实测可用）**——见 §8.1.1
2. 无 PAT → **MCP 本地端点通道**（2026-09-30 实证成功，提交 `fe3e86f`）——见 §8.1.2
3. 均不可用（如 `github.com` TLS 被拦）→ API 四步重放——见 §8.1.3

#### 8.1.1 首选：PAT 直通 push（2026-09-30 实测通过）

```bash
TOKEN='<用户提供的 PAT>'
git push "https://oauth2:${TOKEN}@github.com/SIX2090/wms.git" main 2>&1 \
  | sed -E 's#oauth2:[^@]*@#oauth2:***@#g'   # 输出脱敏，防止 token 进日志
```

**凭证安全红线（硬性）**：

- token **只在同一条 Bash 命令内以 shell 变量传入**，禁止写入仓库文件、脚本、`.git/config`、`git remote set-url`。
- 若临时用 `git remote set-url` 塞过 token，**推送后立即改回无 token 的 URL**。
- 输出必须脱敏；禁止把 token 回显到对话、日志或 commit message。
- 禁止把 PAT 写进 AGENTS.md 或任何会被提交的文件——本文档只记录用法，不记录值。
- 该 PAT 若曾在对话中明文出现，提醒用户到 GitHub → Settings → Developer settings → Personal access tokens **撤销轮换**。

> 实测：`git push` 返回 `Everything up-to-date`（退出码 0）= 认证通过且无待推送内容；
> 返回 `-> main` 且带新 SHA = 推送成功。**必须读取实际输出确认，不得凭假设报完成**（§三推送验证）。

#### 8.1.2 降级：MCP 本地端点通道（无 PAT 时，2026-09-30 实证）

GitHub MCP server 在本机以 **本地 HTTP 端点** 形式运行（`http://127.0.0.1:<port>/<id>/mcp`，地址见环境变量 `CODEBUDDY_MCP_CONFIG` 的 `mcpServers.github.url`）。用脚本走 MCP JSON-RPC 即可推送，**无需 PAT**，且文件内容可直接从磁盘读取（避免手工转义大文件）：

```python
# 握手：POST initialize（带 Authorization 头）→ 取响应头 Mcp-Session-Id
# 通知：POST notifications/initialized（带同一 Session-Id）
# 调用：POST tools/call  name=push_files
#       arguments={owner, repo, branch:"main", message, files:[{path, content}]}
```

- 该通道 2026-09-30 实证成功，产出提交 `fe3e86f`（AGENTS.md +105/-9）。
- 推送后 MCP 返回的 `object.sha` 即远程新 HEAD；**仍需按 §8.1.4 反查确认**。
- 脚本不要放进仓库（避免 A14 门禁与凭证泄漏），放在工作区根目录即可。

#### 8.1.3 兜底：API 四步重放（Git Data API，等效一次 git push）

> 该方法 2026-08-23 实际验证通过（提交 `f09e8215` / `f2709a8b` / `81a682a8`），2026-08-26 再次实测通过（提交 `39ee99c254a8` / `7fbae2ecdad1`）。仅当 §8.1.1 / §8.1.2 都不可用时使用。

**步骤**：

1. **打通 api.github.com**：`github.com` 被拦不代表 `api.github.com` 被拦，须分别实测。
   **2026-09-30 实测：域名直连即返回 200，无需 DoH 解析、无需写 `/etc/hosts`**（见 §8.0.4）。
   仅当直连返回 000 时才走 IP：用 DoH 解析真实 IP（如 `https://dns.alidns.com/resolve?name=api.github.com&type=A`），
   写入 `/etc/hosts`（2026-08-26 实测可用：`20.205.243.168 api.github.com`）。
2. **认证**：token 仅通过请求头 `Authorization: Bearer <TOKEN>` 使用；禁止写入仓库文件、脚本持久化或输出到日志；推送完成后若曾把 token 写进 `git remote set-url`，必须立即改回无 token 的 URL。
3. **四步重放**（全部走 `https://api.github.com`）：

   | 步骤 | API | 作用 |
   |---|---|---|
   | ① | `POST /repos/SIX2090/wms/git/blobs` | 上传文件内容（base64）→ blob SHA |
   | ② | `POST /repos/SIX2090/wms/git/trees` | `base_tree` = 远程 main HEAD 的 tree + 变更文件列表 → 新 tree SHA |
   | ③ | `POST /repos/SIX2090/wms/git/commits` | 新 tree + `parents=[当前HEAD]` + 提交信息 → 新 commit SHA |
   | ④ | `PATCH /repos/SIX2090/wms/git/refs/heads/main` | 把 main 指针移到新 commit |

4. **本地提交照常**：沙箱本地仍按常规 `git commit` 保持历史可续作。远程 commit SHA 与本地不同（时间戳/committer 信息差异）但内容一致，属预期，不算失败。

#### 8.1.4 验证与完成标准（三条通道通用，对接 §三推送验证）

1. **反查远程 HEAD**：`GET /repos/SIX2090/wms/commits/main` 确认 HEAD SHA 已更新、
   `parents` 为推送前的 SHA、`files` 变更列表与预期一致。
   （2026-09-30 实证：`fe3e86f` ← parent `a5d27af`，`AGENTS.md +105/-9`。）
2. **本地对齐（API/MCP 通道必做）**：这两条通道产生的远程 SHA 与本地不同，
   必须 `git fetch --depth 1 origin main` + `git reset --hard origin/main` 让本地与 origin/main 同 SHA，
   才算满足 §三「本地 `git log -1` 与 `git log origin/main -1` 相同」的完成标准。
   > 直连 fetch 有**间歇性** `schannel: failed to receive handshake` / SSL 错误，
   > **重试 1–2 次即可成功**，不要因此判定通道不可用（2026-09-30 实证：第 1 次失败、第 2 次成功）。
3. **PAT 直通 push** 天然满足本地=远程，无需第 2 步；但仍须读取实际 `git push` 输出确认（`-> main` + 新 SHA）。
4. 多文件改动：一次 commit 传入全部变更文件；禁止逐文件各建一个 commit。

### 8.2 拉取（浅克隆通道）

> 适用场景：AI 代理运行在沙箱/受限网络，`github.com` 的 git 协议（HTTPS TLS）被网络层拦截，常规 `git clone` 直接失败（报 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 或 `SSL_ERROR_SYSCALL`）。该方法 2026-08-23 实际验证通过（克隆到 `11cea47`，1171 个文件，约 26MB，工作树完整）。
>
> **2026-09-30 修订**：**先读 [§8.0 通道实测与决策表](#80-通道实测与决策表2026-09-30-新增)**。本环境已实测直连可用，**代理前缀不再是首选**。开工顺序必须是「`git ls-remote` 探测 → 直连浅克隆 → 失败才走代理」，禁止跳过探测直接套代理。

**通道探测（按序尝试，以实测为准）**：

1. **`git ls-remote` 直连探测（必做第一步，2026-09-30 新增）**：

   ```bash
   timeout 45 git ls-remote https://github.com/SIX2090/wms.git main
   ```

   返回 `<SHA>	refs/heads/main` 且退出码 0 → **直连可用，走下面的「首选：直连浅克隆」，不要碰代理**。

2. 直连探测失败 → 才考虑镜像/代理。历史实测（2026-08-23）：`ghproxy.net` ✅、`gitclone.com` ✅；`ghproxy.com`、`mirror.ghproxy.com`、`kgithub.com`、`github.com.cnpmjs.org` ❌ 均被拦。
   **2026-09-30 复测：`ghproxy.net` ❌ 3/3 失败、`gitclone.com` ❌——代理可用性随时间漂移，必须重新探测，且探测结果以"能否真的克隆成功"为准，不能以代理首页 200 为准**（本次 `ghproxy.net` 首页返回 `200`，但克隆 3 次全部在 ~4MB 处中断）。
3. 代理判别命令仅作**粗筛**：`curl -sS -m 15 -o /dev/null -w "%{http_code}" https://<host>` 返回 `200` 才可作代理前缀。**禁止用 curl 判定 `github.com` 本身是否可用**（§8.0.2）。

**首选：直连浅克隆（2026-09-30 实测成功，2m17s）**：

```bash
git config --global http.version HTTP/1.1      # 强制 HTTP/1.1，避开 HTTP/2 流被中间设备掐断
git config --global http.postBuffer 524288000  # 500MB 发送缓冲
git config --global core.compression 0         # 关闭传输压缩，减少中断概率
git clone --depth 1 https://github.com/SIX2090/wms.git wms
```

> 上述三条 git config 在直连场景同样建议保留（本次实测即在该配置下成功）。

**降级：代理前缀浅克隆（建议不要用，仅当直连探测失败时）**：

> **2026-09-30 实测 `ghproxy.net` 连续 3 次失败**：均在下载 ~4MB 时中断，报
> `error: RPC failed; curl 18 transfer closed with outstanding read data remaining` +
> `fetch-pack: unexpected disconnect while reading sideband packet` + `fatal: early EOF` +
> `fatal: fetch-pack: invalid index-pack output`。
> **结论：代理首页返回 `200` 不代表能克隆成功；本环境直连可用时，不建议走代理。**

```bash
git clone --depth 1 "https://ghproxy.net/https://github.com/SIX2090/wms.git" wms
# 备选代理（2026-08-23 曾可用，2026-09-30 实测失败）：
# git clone --depth 1 https://gitclone.com/github.com/SIX2090/wms.git wms
```

**浅克隆后的补全（按需）**：

- `git log` 只有 1 条提交属预期（`--depth 1` 只取最新快照），工作树完整、`git status` 干净即可正常开发。
- 需要完整历史时：`git fetch --unshallow`（URL 同样套代理前缀，且可能需多次重试）。
- 后续更新代码：`git pull --depth 1`。

**验证与完成标准**：

- 克隆后必须验证：`git status` 工作树干净；`git log --oneline -1` 与 GitHub 网页端 main HEAD 一致。
  2026-09-30 实证：直连克隆后 `git log --oneline -1` = `a5d27af`，与 `api.github.com` 反查的 main HEAD `a5d27af35e241f0a2f6d9218f38591796d8b5cf5` 一致，工作树干净，1492 文件。
- **判断是否"挂起"（2026-09-30 修订）**：不要只看"有无输出"，要**采样 pack 文件实际增长**：

  ```bash
  du -sh wms; ls -la wms/.git/objects/pack/   # 间隔 30s 采样两次
  # 有增长 → 只是慢，继续等；停止增长或超过 10 分钟 → 判定挂起
  ```

- 判定代理挂起后**不要再盲目重试同一代理**（本次 ghproxy.net 重试 3 次全败）。应先 `rm -rf wms` 清理，然后按 §8.0.1 决策：
  ① 先回 **`git ls-remote` 直连探测**——很多时候直连其实是通的，只是从没试过；
  ② 直连不通 → 换 `gitclone.com`（若其可用性复测通过）；
  ③ 全部不通 → 走 §8.0.3 codeload tarball 兜底（注意该方法无 git 历史，须按 §8.0.3 说明汇报 SHA 差异）。
