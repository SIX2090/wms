# WMS 项目规则（AGENTS.md）

> 本文件是 AI 代理处理本仓库时必须遵守的最高优先级规则，与 [`DEVELOPMENT_RULES.md`](./DEVELOPMENT_RULES.md)、[`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md)、[`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 配套使用。
> 修改本文件本身属于独立 atomic action（1 commit + 1 push）；新增/修订规则必须注明日期。
> 2026-10-21 校订：同步生产启动、文档维护、CI 查询失败处理、A13 分片范围及 Git 同步安全要求；业务铁律和 main 分支策略不变。

## 目录

0. [环境画像与已拍板决策](#〇环境画像与已拍板决策2026-10-03-新增)
1. [业务操作铁律（AI 行为边界）](#一业务操作铁律ai-行为边界)
2. [仓库与库位必填规则](#二仓库与库位必填规则)
3. [任务粒度与提交流程](#三任务粒度与提交流程) —— 含 [CI 全绿门禁（开工前置条件）](#三任务粒度与提交流程)
4. [分支与前端约束](#四分支与前端约束)
5. [AI 开发台账](#五ai-开发台账)
6. [防 BUG 规则 A1–A14](#六防-bug-规则a1a142026-07-31-新增)
7. [反复 BUG 模式清单与强制防护 R1–R8](#七反复-bug-模式清单与强制防护r1r82026-08-28-新增)
8. [受限网络环境的 GitHub 推送与拉取](#git-network)
   - [8.0 通道探测与本机事实](#git-probe)
   - [8.1 推送通道与安全同步](#git-push)

## 〇、环境画像与已拍板决策（2026-10-03 新增）

> **本节数据会随时间漂移**（加人、加仓库、开库位、换部署方式），任何一项变化时必须同步更新本表并评估关联规则。AI 代理做风险评估前必须先读本表，判断哪些规则"当前活跃"、哪些是"未来防御"。

### 环境画像（2026-10-03 经用户确认）

| 项 | 当前值 | 影响的规则 |
|---|---|---|
| 用户规模 | **单人使用** | §一 中审计追溯/双岗制衡类要求降级为可选；下方"已拍板决策"两项据此成立 |
| 仓库数 | **4 个** | R2 多仓边界规则处于**活跃防御**状态（历史 20+ 条同类 BUG）；[`INVENTORY_TRUTH.md`](./INVENTORY_TRUTH.md) §3.3a 单仓短路分支**未激活**——增减仓库时必须重读本条并验证库存连续性 |
| 库位管理 | **未开启**（代码默认 `'0'`，见 `app/app.py` 的 `location_management_enabled()`） | §二 适用**规则一**（仅仓库必填）；开启前由 `find_location_ledger_mismatches()` 校验，仍需核对存量账务，不得自动回填 |
| 部署形态 | Windows 实机生产部署（见 §8.0.4） | R3 模板改动"生产需重启生效"提示适用 |
| WMS 服务启动 | **`C:\wms\start_wms_offline.bat`**（标准启动脚本） | 使用 `app\instance\inventory.db` 作为生产数据库；自动设置 `WMS_NO_DB_TOUCH=1` 保护数据库；服务运行在 `http://127.0.0.1:8080` |

> **2026-10-21 生产核验补充**：当前常驻实例由 `WMS-Warehouse` 计划任务以 SYSTEM/Session 0 拉起本地 `run_wms_task.bat`；标准手工入口仍是上述脚本。重启前核对实际进程、端口、解释器和托管方式，沿用实际部署入口，不得另起第二实例。生产 Python 3.11 的 Pillow 已升级为 13.0.0。此处为日期快照，后续须现场核验。`WMS_NO_DB_TOUCH=1` 禁用启动升级/初始化，不表示数据库只读或所有运行期写入均禁用。

### 已知设计取舍（经用户拍板，AI 不得重复报告为问题）

> 以下两项已经用户（2026-10-03）明确拍板接受现状。AI 代理在代码审查/流程分析中**不得再次作为缺陷或风险报告**；仅当环境画像发生变化（如转为多人使用）时才需重新评估。

1. **入/出库单无作废（cancelled）态**：错误草稿只能物理删除，无作废留痕。单人使用，无审计追溯需求——接受现状。
2. **§一"提交/审核/完成"措辞与实现的口径差**：主链路（in_order/out_order）实际仅 `pending → completed` 一跳，无审核岗（审核态仅存在于采购申请与销售订单）。接受现状，§一 措辞不改。

### 单据状态权威表（2026-10-03 依据 `app/models/documents.py` @ `d2f0fad` 整理）

| 单据 | status 取值 | 反提交 | 草稿可删 | 备注 |
|---|---|---|---|---|
| 入库单 InOrder | pending / completed | ✅ `revert_in_order` | ✅（completed 须先反提交） | business_type 4 种 |
| 出库单 OutOrder | pending / completed | ✅ `revert_out_order` | ✅（同上） | business_type 4 种 |
| 调拨单 Transfer | pending / completed / cancelled | — | ✅ | cancelled 为软终态 |
| 调整单 Adjustment | pending / completed / cancelled | ✅（对称回退，`adjustment.py:505`） | ✅ | 差异来源于盘点 |
| 盘点单 InventoryCheck | pending / completed | ✅（须其调整单未提交，`check.py:634`） | ✅ | 差异自动生成调整单 |
| 扫码盘点 Scan | pending / completed / void | — | — | void 作废留痕（INV-REVERT-001） |
| 售后出库 AfterSaleOut | pending / completed | ✅ | ✅ | |
| 工单领料 Requisition | pending / completed | — | ✅ | |
| 期初库存单 OpeningStockDoc | active | — | ✅（逐行回冲，见 INVENTORY_TRUTH §2.1.2） | 多单据汇总口径 |
| 采购申请 PurchaseRequest | pending / approved / rejected / completed | — | — | 有审批态 |
| 采购订单 PurchaseOrder | pending / partial / completed | — | — | 行级 received_quantity 跟踪 |
| 销售订单 SalesOrder | draft / confirmed | — | — | 另有 shipment_status：pending/partial/shipped |
| 委外订单 Subcontract | pending / processing / completed | — | — | 发料/收料单为 pending/completed |

> 本表的状态取值以 `app/models/documents.py` 为依据；反提交、删除等操作能力还须核对对应路由及测试（2026-10-21 修订）。模型或操作能力变更时同步回填，不能只凭列注释断言接口行为。

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

  **查询失败处理（2026-10-21新增）**：HTTP403限流、认证失败或网络异常仅表示本次未能核实，不等同工作流已经失败，仍不得视为放行。可通过已连接的GitHub工具或Actions页面逐一核对三个工作流在main的最近一次运行，记录运行链接、SHA、状态及结论，必须全部completed/success。列表分页时必须找到全部三项，不得用旧绿记录替代较新的失败或运行中记录。仅在已满足上述全绿前置条件、而本地pre-push因同一查询故障无法复核时，可为该次push临时设置钩子已有的 `WMS_SKIP_CI_GATE=1`，并记录替代证据；禁止借此跳过未核实或实际非绿的门禁。

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

### 文档维护边界（2026-10-21 新增）

- 修 BUG 必须更新对应月度 BUG 台账及必要索引，记录根因、修复、回归和生效确认；不要求每次都修改 README。
- 使用方式、启动/安装命令、配置、接口约定、功能入口或项目事实发生变化时，更新 README 或对应专题文档；README 提供入口，具体证据放台账/专项记录，避免复制全部历史。
- 修改代理规则时更新 AGENTS，并注明日期；不得用改文档的方式掩盖代码未满足的业务要求。
- 代码修改按既有模块、相邻和全量验证规则执行；纯文档修订核对引用、命令、链接和对应契约测试，并验收推送后的 CI。验证必须使用隔离数据库；默认连接生产地址的冒烟脚本可能登录、创建或修改数据，禁止未授权对生产运行。

## 四、分支与前端约束

- **分支策略（硬性规则，无例外）**：AI/TRAE 必须直接在 `main` 分支工作。严格禁止创建、切换到或推送任何新分支——包括 `feature/*`、`fix/*`、`chore/*` 或任何 `trae/*` worktree 分支。所有 commit 和 push 必须指向 `main`。本地 `.githooks/pre-push` 检查分支及CI门禁。规则允许按需清理非 `main` 残留远程分支，禁止删除 `main`；实际删除前仍须核对目标及钩子行为。**2026-10-21修订**：仓库当前公开，不再套用“免费私有仓库无服务端保护”的旧结论；GitHub规则集、分支保护及绕过权限以现场只读核验为准，不把存在保护等同强制PR或强制CI。
- **业务 JS 禁止原生非 GET `fetch`**：`app/static/js/*.js` 中所有非 GET 请求必须走 `WMS.api.get/post/put/delete(url, data)`（定义于 `app/static/js/api.js`）。业务代码中**禁止**直接使用 `fetch()` 或全局 `csrfFetch` 包装——统一推荐口径是 `WMS.api.*`，pre-commit 钩子提示与本条一致（F3.7 已消除历史上钩子提示 `csrfFetch` 的矛盾）。本地 pre-commit 钩子 `.githooks/pre-commit` 先运行 `scripts/lint_wms_rules.py`（A1-A14），再运行 `scripts/lint_no_raw_post_fetch.py`；两者会拒绝白名单之外包含 `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` 的提交。F3.7（2026-10-12）起 `lint_no_raw_post_fetch.py` 同时扫描 `app/templates/` 内联 `<script>`，**暂为 warn 模式**（只打印不计退出码；存量实测 166 处，观察 3 周后定棘轮基线转 `--templates-strict`）。白名单文件（base.html 全局 fetch 拦截器、`app/static/js/api.js`、`app/static/js/app.js`）可使用原生 `fetch`，因为它们就是统一层。每次克隆后执行一次 `bash .githooks/install-hooks.sh` 启用钩子（等同于 `git config core.hooksPath .githooks`）。

## 五、AI 开发台账

- [`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 是唯一的 AI 开发待办与完成台账。实现任何 AI 功能前，先查其唯一任务 ID、当前状态、现有代码、测试、页面和 Git 历史；绝不重复开发已完成或等价能力。
- 每个 AI 代码变更必须映射到唯一台账任务 ID。新增任务前必须做全仓库查重；对已完成能力的修复必须使用子修复 ID，不得重复原任务。
- 标记 AI 任务完成的前提：代码、权限、人工确认边界、测试、文档、验证，**以及所有 atomic action 按上述推送规则完成提交推送**，全部齐备。立即在台账记录完成日期、提交哈希、变更模块、验证命令、结果和遗留子项（F4.4 拆分后完成记录登记到 `docs/ledger/ai/completions-<当月>.md` 表尾并更新索引 `docs/ledger/INDEX.md`，用 `python scripts/query_ledger.py --rebuild-index` 重建）。权限边界见 [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md)。
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
| **A13** | `WMS_BUG_BASELINE.md` 及 `docs/ledger/bugs/` **新增** BUG 条目必须含「生效确认」字段（R3 机械化） | 修复→生效无确认回路 |
| **A14** | `scripts/` 下**新增** app 引用的脚本必须显式放行生产硬门禁（R6 机械化） | 生产硬门禁漏排查消费点 → CI 变红 |

> A8/A9/A10/A11/A13/A14 是"新增代码生效"规则：仅对 `git diff --cached` 的新增行强制，存量代码不会一次性报几百条违规。其中 **A11 自 2026-09-20 起为双模式**：pre-commit 维持新增行生效，`WMS CI` 追加 `python3 scripts/lint_wms_rules.py --rule a11 --full-a11` 全量硬门禁（P0-1 存量清零后启用，违规即红）。详见 [DEVELOPMENT_RULES.md §六](./DEVELOPMENT_RULES.md)。

### 强制门禁

- pre-commit 钩子（`.githooks/pre-commit`）会扫描以上规则
- 启用：`bash .githooks/install-hooks.sh`
- 跳过（不推荐）：`git commit --no-verify`

### 修复 BUG 流程

1. 在 BUG 台账分片 `docs/ledger/bugs/entries-<当月>.md` 登记（`### BUG-YYYY-MM-DD-NNN: <标题>`，含「生效确认」字段；主文件 `WMS_BUG_BASELINE.md` 只承载规则与索引，查询用 `python scripts/query_ledger.py --task <ID>`）
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

> **R3的机械化防护（2026-09-20新增，2026-10-21校订）**：①启动日志包含 `wms vX.Y.Z (<git短SHA>) config-check: …` 及 `db-check: migrate=…`（`app/startup_check.py`），不保证是控制台第一行；核对代码、配置和schema-check，不能仅凭 `migrate=ok` 断言执行过迁移。②A13扫描 `WMS_BUG_BASELINE.md` 及 `docs/ledger/bugs/` 新增条目，必须含「生效确认」（确认人/时间/核对方式，允许「待确认」占位），否则pre-commit拦截。

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

<a id="git-network"></a>
## 八、受限网络环境的 GitHub 推送与拉取（2026-10-21 修订）

本节区分当前操作规范与历史网络实测。2026-09-30曾验证直连可用、部分代理失败；2026-10-21本机普通 `git push origin main` 成功。网络、凭据和连接器会变化，每次按实际证据判断。

<a id="git-probe"></a>
### 8.0 通道探测与本机事实

#### 8.0.1 先用Git验证Git通道

在已有仓库内优先使用 `git ls-remote origin refs/heads/main`；需要新克隆时使用：

```powershell
git ls-remote https://github.com/SIX2090/wms.git refs/heads/main
```

返回SHA和refs/heads/main且退出0，才说明该次读取成功；读取成功不证明具备推送权限。不要用浏览器首页或curl的HTTP状态推断Git协议可用性，也不要为探测读取/输出凭证。

#### 8.0.2 直连优先，代理必须重新验证

直连可用就直连；失败再检查认证、网络或使用已连接的GitHub工具。ghproxy.net、gitclone.com的历史成功/失败均不是当前可用性保证。代理首页HTTP200不能证明可克隆，更不能证明可推送。不要反复盲试已失败代理，不要默认修改hosts或全局Git配置。

#### 8.0.3 ZIP/tarball仅作源码参考

下载包不含Git历史，不能当成已与main同步的工作区。不得为“对齐”自行创建伪基线提交再覆盖远端。需要提交时取得真实仓库历史，或经已授权的GitHub工具基于远端main创建准确变更；拿不到可靠历史/完整文件集合就停止写入，保留现场。

#### 8.0.4 本机环境与凭据事实

- 仓库当前公开；公开读取无需PAT，匿名API可能限流。
- WMS运行在Windows，常驻实例和标准手工入口见§〇；不要套用Linux命令到PowerShell。
- gh CLI、历史codebuddy脚本和旧MCP本地端点不保证存在。优先使用当前可发现的连接器及其公开工具，不提取或复用连接器内部token。
- 已有Git凭据可用时直接 `git push origin main`，不得因旧文档写着“无凭据”而要求用户重新提供PAT。

<a id="git-push"></a>
### 8.1 推送通道：已有Git凭据 → 已连接工具 → 经核验的API操作

#### 8.1.1 首选普通Git推送

```powershell
git push origin main
```

读取实际输出并核对本地HEAD、origin/main及实际远端main；新SHA必须一致。Everything up-to-date只能说明本次没有新增推送内容，不能当作新改动已发布。禁止force push、创建新分支或删除main。

凭据只能经安全的凭据管理器、环境注入或连接器使用。不得要求用户把PAT发到聊天，不得将token拼进命令行URL、remote、Git配置、仓库文件、日志或提交信息。避免从credential helper或连接器提取明文token用于诊断。确需新凭据时引导用户在本机安全配置，禁止打印秘密。

#### 8.1.2 已连接的GitHub工具

普通Git不可用时先检查当前连接器是否支持所需写入。沿用main、远端当前parent和本次准确文件集合；不得从旧环境变量猜测私有MCP地址。多文件变更按atomic action一次提交，不把无关内容或本地秘密打包上传。若API生成不同SHA，必须按§8.1.4保留本地工作并对齐真实远端历史。

#### 8.1.3 Git Data API仅作受控兜底

仅在已有工具能力和授权足够时使用：上传准确blobs、以远端当前tree为base构建新tree、以当前main为parent创建commit、非强制更新main ref。禁止从部分文件生成残缺tree；推送前核对新增/修改/删除集合及完整文件清单。更新期间main已前进就重新读取、合并并验证，不强行覆盖。

#### 8.1.4 安全同步与完成标准

1. 推送前检查 `git status --short`、diff及远端main，保留用户未提交和未跟踪文件。
2. 推送后fetch并核对远端parent/tree及变更集合；API/MCP产生不同SHA时先保存必要的本地提交和工作文件，再制定非破坏性的对齐步骤。
3. 禁止把 `git reset --hard origin/main`、删除目录或git stash当作例行对齐手段；没有备份及明确授权不得丢弃本地内容。
4. 本地与origin/main新SHA一致才满足§三完成标准；API写入没有git push输出时记录API返回及反查证据，不伪造push结果。
5. 后续CI必须按§三重新验收；本地测试通过不代替远端实际运行。

### 8.2 克隆与拉取

```powershell
git clone --depth 1 --branch main https://github.com/SIX2090/wms.git wms
```

目标目录已有内容时先停止并核对，不自动删除或覆盖。现有工作区先看状态和历史，再按需要 `git fetch origin main`；本地无分叉且工作区允许时才快进合并。需要更多历史时按需加深fetch，不默认给URL加代理前缀。

不要常规设置全局http.postBuffer、core.compression或协议版本来“加速”；只有实证对应网络问题时才做可回退、限定范围的调整。判断传输是否停滞可观察pack增长及进程状态；失败后保留现场，更换已验证通道，不直接递归删除工作区。
