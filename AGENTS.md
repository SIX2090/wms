# WMS 项目规则（AGENTS.md）

> 本文件是 AI 代理处理本仓库时必须遵守的最高优先级规则，与 [`DEVELOPMENT_RULES.md`](./DEVELOPMENT_RULES.md)、[`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md)、[`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 配套使用。
> 修改本文件本身属于独立 atomic action（1 commit + 1 push）；新增/修订规则必须注明日期。

## 目录

1. [业务操作铁律（AI 行为边界）](#一业务操作铁律ai-行为边界)
2. [仓库与库位必填规则](#二仓库与库位必填规则)
3. [任务粒度与提交流程](#三任务粒度与提交流程)
4. [分支与前端约束](#四分支与前端约束)
5. [AI 开发台账](#五ai-开发台账)
6. [防 BUG 规则 A1–A10](#六防-bug-规则a1a102026-07-31-新增)
7. [反复 BUG 模式清单与强制防护 R1–R6](#七反复-bug-模式清单与强制防护r1r62026-08-28-新增)
8. [受限网络环境的 GitHub 推送与拉取](#八受限网络环境的-github-推送与拉取2026-08-23-新增2026-08-26-修订)

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
- **业务 JS 禁止原生非 GET `fetch`**：`app/static/js/*.js` 中所有非 GET 请求必须走 `WMS.api.get/post/put/delete(url, data)`（定义于 `app/static/js/api.js`）。业务代码中**禁止**直接使用 `fetch()` 或全局 `csrfFetch` 包装。本地 pre-commit 钩子 `.githooks/pre-commit` 先运行 `scripts/lint_wms_rules.py`（A1-A10），再运行 `scripts/lint_no_raw_post_fetch.py`；两者会拒绝白名单之外包含 `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` 的提交。白名单文件（base.html 全局 fetch 拦截器、`app/static/js/api.js`、`app/static/js/app.js`）可使用原生 `fetch`，因为它们就是统一层。每次克隆后执行一次 `bash .githooks/install-hooks.sh` 启用钩子（等同于 `git config core.hooksPath .githooks`）。

## 五、AI 开发台账

- [`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) 是唯一的 AI 开发待办与完成台账。实现任何 AI 功能前，先查其唯一任务 ID、当前状态、现有代码、测试、页面和 Git 历史；绝不重复开发已完成或等价能力。
- 每个 AI 代码变更必须映射到唯一台账任务 ID。新增任务前必须做全仓库查重；对已完成能力的修复必须使用子修复 ID，不得重复原任务。
- 标记 AI 任务完成的前提：代码、权限、人工确认边界、测试、文档、验证，**以及所有 atomic action 按上述推送规则完成提交推送**，全部齐备。立即在台账记录完成日期、提交哈希、变更模块、验证命令、结果和遗留子项。权限边界见 [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md)。
- 每个 AI 任务结束时，将台账与 AI 路由、工具、模型、模板、特性开关、迁移和验证脚本对账，确保已实现的能力不被遗漏、计划中的能力不被误报为已实现。

## 六、防 BUG 规则（A1–A10，2026-07-31 新增）

**修改本仓库任何代码前，请先阅读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md)；且**必须** `bash .githooks/install-hooks.sh` 启用 pre-commit 钩子，否则 10 条防 BUG 规则不会自动跑。**

### 10 条核心规则速查

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

> A8/A9/A10 是"新增代码生效"规则：仅对 `git diff --cached` 的新增行强制，存量代码不会一次性报几百条违规。详见 [DEVELOPMENT_RULES.md §六](./DEVELOPMENT_RULES.md)。

### 强制门禁

- pre-commit 钩子（`.githooks/pre-commit`）会扫描以上规则
- 启用：`bash .githooks/install-hooks.sh`
- 跳过（不推荐）：`git commit --no-verify`

### 修复 BUG 流程

1. 在 [`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md) 登记（`BUG-YYYY-MM-DD-NNN: <标题>`）
2. commit message 关联 BUG ID：`fix: BUG-2026-07-31-001 xxx`
3. 加回归测试
4. 改状态为"已修复"

## 七、反复 BUG 模式清单与强制防护（R1–R6，2026-08-28 新增）

> 台账统计显示，大量 BUG 是**同一根因在不同消费点反复出现**（锁×17、多仓库×11、合同×9、分页/翻页×11、重启×6）。以下 R 系列规则针对已实证的反复模式，凡改动落入对应场景必须逐条自检。R 系列目前为人工/AI 自检规则（不做 lint 门禁），与 A1–A10 并列执行。

### R1 分页默认值不得当业务上限（实证：BUG-2026-08-28-001、002 等 10+ 条同类）

- **禁止**：数据消费方（前端页面、Android App、AI 工具、脚本）调用列表/明细接口时依赖默认 `page_size` 就当作"全量"。
- **必须**：①显式传足够大的 `page_size` 并按响应 `total_pages` 翻页合并取全；或 ②调用方明确知晓并注释"仅取前 N 条"。
- **新接口**：必须返回完整分页元数据（`total` / `page` / `page_size` / `total_pages`）；汇总统计必须与分页解耦（汇总基于全集，列表基于分页）。

### R2 库存/出入库/报表改动必验多仓库边界（实证：08-16/08-17/08-23/08-27 系列 20+ 条）

改动涉及库存数量、出入库单据、报表聚合时，必须同时验证三个口径，缺一不算完成：

1. **多仓库隔离**：两个及以上仓库之间数据互不串仓（汇总=各仓库之和）。
2. **历史脏数据兼容**：历史 `warehouse`/`location` 为空或解析不到的记录不得导致"查不出来/库存不足"误判。
3. **汇总 = 明细**：报表合计行必须等于明细行全集之和，不得以分页/抽样数据近似。

### R3 模板改动必须标重启（实证：6+ 条"改了没生效"）

- 凡改动 `app/templates/*.html`（Jinja 模板），commit message 与 BUG 台账记录**必须注明「生产需重启 WMS 服务生效」**（生产模式模板有缓存）。

### R4 打印/写库链路必须降级兜底（实证：锁相关 17 条）

- 改动打印代理、写库心跳、Spooler/WMI 依赖路径时，必须处理 `database is locked`（busy_timeout + 低频重试 + 降级静默），禁止裸抛 traceback 刷屏；Windows 打印服务异常必须给中文操作指引，不得抛英文原生错误。

### R5 AI 功能必须留人工确认边界与失败回退（实证：AI 相关 12 条）

- AI 识别/解读/生成的新能力：**低置信度必须回退人工**，禁止 AI 结果不经确认直接写入业务数据；失败/不确定时明确告知"我不确定"，禁止编造输出。

### R6 新 BUG 登记前必查同根因历史

- 登记新 BUG 前必须 grep 台账查同模式历史 BUG；若判定为**同一根因的复发**，必须同时排查并修复**所有同类消费点**（不只修报告的那一处），并在台账注明"同类点已排查"。

## 八、受限网络环境的 GitHub 推送与拉取（2026-08-23 新增，2026-08-26 修订）

### 8.1 推送（API 通道）

> 适用场景：AI 代理运行在沙箱/受限网络，`github.com` 的 git 协议（HTTPS TLS / SSH 22）被网络层拦截，常规 `git push` 不可用，但持有用户授权的 GitHub OAuth token（CodeBuddy 连接器）。该方法 2026-08-23 实际验证通过（提交 `f09e8215` / `f2709a8b` / `81a682a8`），2026-08-26 再次实测通过（提交 `39ee99c254a8` / `7fbae2ecdad1`）。

**凭证获取（唯一实测有效来源）**：

```bash
source ~/.codebuddy/skills/github-connector/scripts/get_token.sh github
# 成功后环境变量 GITHUB_TOKEN 就绪（ghu_ 开头的 OAuth user token）
# 注意：每个 Bash 调用是新 shell，取 token 与后续 git/curl 必须写在同一条命令里
```

> 2026-08-26 实测**不可用**的凭证/通道（不要再试）：
> - `git-credential-helper`（向 `git.auth-proxy.local` 查询）→ 404「git credentials not found in space labels」
> - GitHub MCP server（github-remote）→ 会话内连接失败，界面绿点不代表可用
> - SSH over 443 → 本环境无部署公钥
> - ghproxy.net / gitclone.com 代理前缀 **push** → 代理只对 github.com 域名供凭证，push 会卡在 `could not read Username`；**代理只能用于拉取，不能用于推送**

**通道探测（按序尝试，以实测为准）**：

1. 常规 HTTPS push（`git push https://oauth2:<TOKEN>@github.com/SIX2090/wms.git main`）——TLS 可通则优先走常规通道（2026-08-26 实测仍被拦，报 `gnutls_handshake() failed`）
2. 失败 → 使用下述 API 通道

**API 通道步骤（Git Data API 重放提交，等效一次 git push）**：

1. **打通 api.github.com**：`github.com` 被拦不代表 `api.github.com` 被拦，须分别实测（域名直连实测 000，须走 IP）。用 DoH 解析真实 IP（如 `https://dns.alidns.com/resolve?name=api.github.com&type=A`），将可用 IP 写入 `/etc/hosts`（2026-08-26 实测可用：`20.205.243.168 api.github.com`）。
2. **认证**：token 仅通过请求头 `Authorization: Bearer <TOKEN>` 使用；禁止写入仓库文件、脚本持久化或输出到日志；推送完成后若曾把 token 写进 `git remote set-url`，必须立即改回无 token 的 URL。
3. **四步重放**（全部走 `https://api.github.com`）：

   | 步骤 | API | 作用 |
   |---|---|---|
   | ① | `POST /repos/SIX2090/wms/git/blobs` | 上传文件内容（base64）→ blob SHA |
   | ② | `POST /repos/SIX2090/wms/git/trees` | `base_tree` = 远程 main HEAD 的 tree + 变更文件列表 → 新 tree SHA |
   | ③ | `POST /repos/SIX2090/wms/git/commits` | 新 tree + `parents=[当前HEAD]` + 提交信息 → 新 commit SHA |
   | ④ | `PATCH /repos/SIX2090/wms/git/refs/heads/main` | 把 main 指针移到新 commit |

4. **本地提交照常**：沙箱本地仍按常规 `git commit` 保持历史可续作。远程 commit SHA 与本地不同（时间戳/committer 信息差异）但内容一致，属预期，不算失败。

**验证与完成标准（对接第三节推送验证）**：

- API 推送后必须反查 `GET /repos/SIX2090/wms/commits/main`：确认 HEAD SHA 已更新、`files` 变更列表与预期一致，才可报告完成。
- 多文件改动：步骤 ② 的 `tree` 数组一次传入全部变更文件；禁止逐文件各建一个 commit。

### 8.2 拉取（浅克隆通道）

> 适用场景：AI 代理运行在沙箱/受限网络，`github.com` 的 git 协议（HTTPS TLS）被网络层拦截，常规 `git clone` 直接失败（报 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 或 `SSL_ERROR_SYSCALL`）。该方法 2026-08-23 实际验证通过（克隆到 `11cea47`，1171 个文件，约 26MB，工作树完整）。

**通道探测（按序尝试，以实测为准）**：

1. 常规 HTTPS clone（`git clone https://github.com/SIX2090/wms.git wms`）——TLS 可通则优先走常规通道。
2. 均失败 → 实测可用镜像/代理（2026-08-23 结果）：`ghproxy.net` ✅、`gitclone.com` ✅；`ghproxy.com`、`mirror.ghproxy.com`、`kgithub.com`、`github.com.cnpmjs.org` ❌ 均被拦。镜像可用性随时间变化，用前必须重新探测。
3. 判别命令：`curl -sS -m 15 -o /dev/null -w "%{http_code}" https://<host>` 返回 `200` 才可作代理前缀。

**浅克隆步骤（代理前缀 + HTTP/1.1 + 浅克隆）**：

> 全量克隆走代理易在收尾被中断（`curl 92 HTTP/2 stream ... INTERNAL_ERROR` + `early EOF` + `fetch-pack: invalid index-pack output`），必须用以下参数组合：

```bash
git config --global http.version HTTP/1.1      # 强制 HTTP/1.1，避开 HTTP/2 流被代理掐断
git config --global http.postBuffer 524288000  # 500MB 发送缓冲
git config --global core.compression 0         # 关闭传输压缩，减少中断概率
git clone --depth 1 "https://ghproxy.net/https://github.com/SIX2090/wms.git" wms
```

**浅克隆后的补全（按需）**：

- `git log` 只有 1 条提交属预期（`--depth 1` 只取最新快照），工作树完整、`git status` 干净即可正常开发。
- 需要完整历史时：`git fetch --unshallow`（URL 同样套代理前缀，且可能需多次重试）。
- 后续更新代码：`git pull --depth 1`。

**验证与完成标准**：

- 克隆后必须验证：`git status` 工作树干净；`git log --oneline -1` 与 GitHub 网页端 main HEAD 一致。
- 克隆超过 10 分钟无输出视为代理挂起：`rm -rf wms` 后换 `gitclone.com` 通道（`git clone --depth 1 https://gitclone.com/github.com/SIX2090/wms.git wms`）重试。
