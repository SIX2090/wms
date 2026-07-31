# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- 采购入库单允许手工新增、编辑、保存和完成，采购订单仅作为可选来源，不得强制要求采购入库关联采购订单；存在来源采购订单时，仍须保留来源、数量和执行进度跟踪。
- 已完成入库单禁止直接删除；必须先由人工反提交，使单据回到草稿状态并准确回退库存，然后才允许删除草稿。详情页、列表页和后端接口必须执行同一规则。
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
- The system must never auto-generate a random password for any account (including the bootstrap admin). When `WMS_BOOTSTRAP_PASSWORD` is not set, the system must use a fixed default password ('admin') with a warning, not `secrets.token_urlsafe` or any random generator. Random password generation hides credentials from the operator and violates password transparency.

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

## AI 开发台账

- [`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`](./WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md) is the sole AI development backlog and completion ledger. Before implementing an AI feature, check its unique task ID, current status, existing code, tests, pages, and Git history; never redevelop a completed or equivalent capability.
- Every AI code change must map to one unique ledger task ID. Add a new task only after a repository-wide duplicate check; fixes to completed capabilities must use a child fix ID instead of duplicating the original task.
- Mark an AI task complete only after code, permissions, human-confirmation boundaries, tests, documentation, verification, **and all its atomic actions are committed and pushed per the push rule above**, are complete. Immediately record completion date, commit hash(es), changed modules, validation commands, result, and remaining child items in the ledger. See [`AI_PERMISSION_MATRIX.md`](./AI_PERMISSION_MATRIX.md) for permission boundaries.
- At the end of each AI task, reconcile the ledger against AI routes, tools, models, templates, feature flags, migrations, and verification scripts so implemented capabilities are not omitted and planned capabilities are not falsely reported as implemented.

## 分支与前端约束

- **Branch policy (hard rule, no exceptions)**: AI/TRAE must work directly on `main`. It is strictly forbidden to create, switch to, or push to any new branch -- including `feature/*`, `fix/*`, `chore/*`, or any `trae/*` worktree branch. All commits and pushes MUST target `main`. The local pre-push hook `.githooks/pre-push` enforces this client-side (it also blocks deletion of any remote branch, including `main`). Note: enforcing branch protection on the GitHub side requires GitHub Pro on private repos; on free private repos the local hook + CI are the only enforcement layers.
- **No raw non-GET `fetch` in JS**: All non-GET requests in `app/static/js/*.js` MUST go through `WMS.api.get/post/put/delete(url, data)` (defined in `app/static/js/api.js`). Direct use of `fetch()` or the global `csrfFetch` wrapper is **forbidden** in business code. The local pre-commit hook `.githooks/pre-commit` runs `scripts/lint_wms_rules.py` (A1-A7) first and `scripts/lint_no_raw_post_fetch.py` second; together they reject commits that contain `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })` outside the allow-list. Whitelisted files (the base.html global fetch interceptor, `app/static/js/api.js`, and `app/static/js/app.js`) may use raw `fetch` because they ARE the unified layer. Enable the hook once per clone with `bash .githooks/install-hooks.sh` (equivalent to `git config core.hooksPath .githooks`).

## 防 BUG 规则（2026-07-31 新增）

**修改本仓库任何代码前，请先阅读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md)；且**必须** `bash .githooks/install-hooks.sh` 启用 pre-commit 钩子，否则 7 条防 BUG 规则不会自动跑。**

### 7 条核心规则速查

| 编号 | 规则 | 防的 BUG |
|---|---|---|
| A1 | `<form method="post">` 必须有 csrf_token | 表单 400 / 死循环 |
| A2 | Python POST 路由必须 @login_required 或 @csrf.exempt | 漏 CSRF 保护 |
| A3 | 业务 JS 不能 console.log | 调试代码泄漏 |
| A4 | 业务 JS 不能 debugger/alert | 调试残留 |
| A5 | 业务 JS 不能 eval/new Function | XSS / 注入 |
| A6 | 业务 Python 不能 print | 调试代码污染日志 |
| A7 | SQL 必须参数化，禁止字符串拼接 | SQL 注入 |

### 强制门禁

- pre-commit 钩子（`.githooks/pre-commit`）会扫描以上规则
- 启用：`bash .githooks/install-hooks.sh`
- 跳过（不推荐）：`git commit --no-verify`

### 修复 BUG 流程

1. 在 [`WMS_BUG_BASELINE.md`](./WMS_BUG_BASELINE.md) 登记（`BUG-YYYY-MM-DD-NNN: <标题>`）
2. commit message 关联 BUG ID：`fix: BUG-2026-07-31-001 xxx`
3. 加回归测试
4. 改状态为"已修复"
