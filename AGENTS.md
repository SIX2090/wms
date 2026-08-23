# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- 采购入库单允许手工新增、编辑、保存和完成，采购订单仅作为可选来源，不得强制要求采购入库关联采购订单；存在来源采购订单时，仍须保留来源、数量和执行进度跟踪。
- 已完成入库单禁止直接删除；必须先由人工反提交，使单据回到草稿状态并准确回退库存，然后才允许删除草稿。详情页、列表页和后端接口必须执行同一规则。
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
- The system must never auto-generate a random password for any account (including the bootstrap admin). When `WMS_BOOTSTRAP_PASSWORD` is not set, the system must use a fixed default password ('admin') with a warning, not `secrets.token_urlsafe` or any random generator. Random password generation hides credentials from the operator and violates password transparency.

## 仓库与库位必填规则

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

## 任务粒度与提交流程

> 一个 **AI task** = 一个用户请求的目标（例如"修删除物料 BUG"、"清理 14 个过期文件"、"加一种导出格式"）。
> 一个 **AI task** = 1 个或多个 **atomic actions**（每个 atomic action 是可独立 revert、自洽能过测试的最小改动）。
> 任务粒度不同时，提交流程也不同：atomic action 各自独立 commit + push，AI task 整体在 ledger 里 mark complete。

- **Verify result**: After completing each atomic action (and again at the end of the AI task), AI must verify the result (e.g., check service status, test functionality, confirm output correctness) before reporting to the user. Unverified results must not be presented as done.
- **Atomic-action push (hard rule)**: After completing EACH atomic action -- not after each "AI task" -- AI must commit AND push the result to `https://github.com/SIX2090/wms.git` on the `main` branch, unless the user explicitly says not to.

  An atomic action is one self-contained change that:
  - has a single clear purpose (one rule fix, one file cleanup batch, one doc update, one function rewrite, etc.)
  - can be reverted independently (one `git revert <sha>` undoes it cleanly)
  - passes lint / build / relevant tests on its own (no half-broken intermediate state on main)
  - has a conventional commit message (e.g. `fix(scope): ...`, `chore: ...`, `docs: ...`)

  Examples:

  > "Fix AGENTS.md wording" = 1 atomic action -> 1 commit + 1 push
  > "Delete 14 unused files" = 3 atomic actions (category A, B, C) -> 3 commits + 3 pushes
  > "Update README 20 places" = 1 atomic action (single doc, single commit) -> 1 commit + 1 push
  > **Wrong**: batching 5 unrelated rule fixes into one commit just to "save pushes"

- **Push verification**: Before reporting completion of any atomic action, AI MUST verify the push result by reading the actual `git push` output (`` To <url> ... -> main ``) and confirming a non-empty new SHA on origin/main. If the push fails (network, non-fast-forward, auth), the action is NOT done -- rebase/pull, fix, and re-push before reporting.
- **Completion criterion**: An atomic action is considered done only when both `git log -1` locally and `git log origin/main -1` show the same new SHA. Local-only commits do not count as completed.

## 受限网络环境的 GitHub 推送（API 通道，2026-08-23 新增）

> 适用场景：AI 代理运行在沙箱/受限网络，`github.com` 的 git 协议（HTTPS TLS / SSH 22）被网络层拦截，常规 `git push` 与 SSH 均不可用，但持有用户授权的 GitHub OAuth token（如 CodeBuddy 连接器）。该方法 2026-08-23 实际验证通过（提交 `f09e8215` / `f2709a8b` / `81a682a8`）。

### 通道探测（按序尝试，以实测为准）

1. 常规 HTTPS push（`git push https://oauth2:<TOKEN>@github.com/SIX2090/wms.git main`）——TLS 可通则优先走常规通道
2. SSH over 443（`ssh -T -p 443 git@ssh.github.com`）——部署公钥已授权时走 SSH
3. 均失败 → 使用下述 API 通道

### API 通道步骤（Git Data API 重放提交，等效一次 git push）

1. **打通 api.github.com**：`github.com` 被拦不代表 `api.github.com` 被拦，须分别实测。用 DoH 解析真实 IP（如 `https://dns.alidns.com/resolve?name=api.github.com&type=A`），将可用 IP 写入 `/etc/hosts`（例：`20.205.243.168 api.github.com`）。
2. **认证**：token 仅通过请求头 `Authorization: Bearer <TOKEN>` 使用；禁止写入仓库文件、脚本持久化或输出到日志。
3. **四步重放**（全部走 `https://api.github.com`）：

   | 步骤 | API | 作用 |
   |---|---|---|
   | ① | `POST /repos/SIX2090/wms/git/blobs` | 上传文件内容（base64）→ blob SHA |
   | ② | `POST /repos/SIX2090/wms/git/trees` | `base_tree` = 远程 main HEAD 的 tree + 变更文件列表 → 新 tree SHA |
   | ③ | `POST /repos/SIX2090/wms/git/commits` | 新 tree + `parents=[当前HEAD]` + 提交信息 → 新 commit SHA |
   | ④ | `PATCH /repos/SIX2090/wms/git/refs/heads/main` | 把 main 指针移到新 commit |

4. **本地提交照常**：沙箱本地仍按常规 `git commit` 保持历史可续作。远程 commit SHA 与本地不同（时间戳/committer 信息差异）但内容一致，属预期，不算失败。

### 验证与完成标准（对接上文 Push verification）

- API 推送后必须反查 `GET /repos/SIX2090/wms/commits/main`：确认 HEAD SHA 已更新、`files` 变更列表与预期一致，才可报告完成。
- 多文件改动：步骤 ② 的 `tree` 数组一次传入全部变更文件；禁止逐文件各建一个 commit。

## 受限网络环境的 GitHub 拉取（浅克隆通道，2026-08-23 新增）

> 适用场景：AI 代理运行在沙箱/受限网络，`github.com` 的 git 协议（HTTPS TLS）被网络层拦截，常规 `git clone` 直接失败（报 `gnutls_handshake() failed: The TLS connection was non-properly terminated` 或 `SSL_ERROR_SYSCALL`）。该方法 2026-08-23 实际验证通过（克隆到 `11cea47`，1171 个文件，约 26MB，工作树完整）。

### 通道探测（按序尝试，以实测为准）

1. 常规 HTTPS clone（`git clone https://github.com/SIX2090/wms.git wms`）——TLS 可通则优先走常规通道。
2. 均失败 → 实测可用镜像/代理（2026-08-23 结果）：`ghproxy.net` ✅、`gitclone.com` ✅；`ghproxy.com`、`mirror.ghproxy.com`、`kgithub.com`、`github.com.cnpmjs.org` ❌ 均被拦。镜像可用性随时间变化，用前必须重新探测。
3. 判别命令：`curl -sS -m 15 -o /dev/null -w "%{http_code}" https://<host>` 返回 `200` 才可作代理前缀。

### 浅克隆步骤（代理前缀 + HTTP/1.1 + 浅克隆）

> 全量克隆走代理易在收尾被中断（`curl 92 HTTP/2 stream ... INTERNAL_ERROR` + `early EOF` + `fetch-pack: invalid index-pack output`），必须用以下参数组合：

```bash
git config --global http.version HTTP/1.1      # 强制 HTTP/1.1，避开 HTTP/2 流被代理掐断
git config --global http.postBuffer 524288000  # 500MB 发送缓冲
git config --global core.compression 0         # 关闭传输压缩，减少中断概率
git clone --depth 1 "https://ghproxy.net/https://github.com/SIX2090/wms.git" wms
```

### 浅克隆后的补全（按需）

- `git log` 只有 1 条提交属预期（`--depth 1` 只取最新快照），工作树完整、`git status` 干净即可正常开发。
- 需要完整历史时：`git fetch --unshallow`（URL 同样套代理前缀，且可能需多次重试）。
- 后续更新代码：`git pull --depth 1`。

### 验证与完成标准

- 克隆后必须验证：`git status` 工作树干净；`git log --oneline -1` 与 GitHub 网页端 main HEAD 一致。
- 克隆超过 10 分钟无输出视为代理挂起：`rm -rf wms` 后换 `gitclone.com` 通道（`git clone --depth 1 https://gitclone.com/github.com/SIX2090/wms.git wms`）重试。


## AI 开发台账

- [`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) is the sole AI development backlog and completion ledger. Before implementing an AI feature, check its unique task ID, current status, existing code, tests, pages, and Git history; never redevelop a completed or equivalent capability.
- Every AI code change must map to one unique ledger task ID. Add a new task only after a repository-wide duplicate check; fixes to completed capabilities must use a child fix ID instead of duplicating the original task.
- Mark an AI task complete only after code, permissions, human-confirmation boundaries, tests, documentation, verification, **and all its atomic actions are committed and pushed per the push rule above**, are complete. Immediately record completion date, commit hash(es), changed modules, validation commands, result, and remaining child items in the ledger. See [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md) for permission boundaries.
- At the end of each AI task, reconcile the ledger against AI routes, tools, models, templates, feature flags, migrations, and verification scripts so implemented capabilities are not omitted and planned capabilities are not falsely reported as implemented.

## 分支与前端约束

- **Branch policy (hard rule, no exceptions)**: AI/TRAE must work directly on `main`. It is strictly forbidden to create, switch to, or push to any new branch -- including `feature/*`, `fix/*`, `chore/*`, or any `trae/*` worktree branch. All commits and pushes MUST target `main`. The local pre-push hook `.githooks/pre-push` enforces this client-side (it also blocks deletion of any remote branch, including `main`). Note: enforcing branch protection on the GitHub side requires GitHub Pro on private repos; on free private repos the local hook + CI are the only enforcement layers.
- **No raw non-GET `fetch` in JS**: All non-GET requests in `app/static/js/*.js` MUST go through `WMS.api.get/post/put/delete(url, data)` (defined in `app/static/js/api.js`). Direct use of `fetch()` or the global `csrfFetch` wrapper is **forbidden** in business code. The local pre-commit hook `.githooks/pre-commit` runs `scripts/lint_wms_rules.py` (A1-A10) first and `scripts/lint_no_raw_post_fetch.py` second; together they reject commits that contain `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` outside the allow-list. Whitelisted files (the base.html global fetch interceptor, `app/static/js/api.js`, and `app/static/js/app.js`) may use raw `fetch` because they ARE the unified layer. Enable the hook once per clone with `bash .githooks/install-hooks.sh` (equivalent to `git config core.hooksPath .githooks`).

## 防 BUG 规则（2026-07-31 新增）

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
