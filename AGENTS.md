# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- 采购入库单允许手工新增、编辑、保存和完成，采购订单仅作为可选来源，不得强制要求采购入库关联采购订单；存在来源采购订单时，仍须保留来源、数量和执行进度跟踪。
- 已完成入库单禁止直接删除；必须先由人工反提交，使单据回到草稿状态并准确回退库存，然后才允许删除草稿。详情页、列表页和后端接口必须执行同一规则。
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
- The system must never auto-generate a random password for any account (including the bootstrap admin). When `WMS_BOOTSTRAP_PASSWORD` is not set, the system must use a fixed default password ('admin') with a warning, not `secrets.token_urlsafe` or any random generator. Random password generation hides credentials from the operator and violates password transparency.
- After completing any task, AI must verify the result (e.g., check service status, test functionality, confirm output correctness) before reporting to the user. Unverified results must not be presented as done.
- After completing any task, AI must commit and push changes to GitHub unless the user explicitly says not to.
- Every completed task must push its task commit to `https://github.com/SIX2090/wms.git` on the `main` branch unless the user explicitly says not to. Before reporting completion, verify the push result or clearly report any network failure.
- `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` is the sole AI development backlog and completion ledger. Before implementing an AI feature, check its unique task ID, current status, existing code, tests, pages, and Git history; never redevelop a completed or equivalent capability.
- Every AI code change must map to one unique ledger task ID. Add a new task only after a repository-wide duplicate check; fixes to completed capabilities must use a child fix ID instead of duplicating the original task.
- Mark an AI task complete only after code, permissions, human-confirmation boundaries, tests, documentation, verification, commit, and push are complete. Immediately record completion date, commit hash, changed modules, validation commands, result, and remaining child items in the ledger.
- At the end of each AI task, reconcile the ledger against AI routes, tools, models, templates, feature flags, migrations, and verification scripts so implemented capabilities are not omitted and planned capabilities are not falsely reported as implemented.
- **Branch policy (hard rule, no exceptions)**: AI/TRAE must work directly on `main`. It is strictly forbidden to create, switch to, or push to any new branch — including `feature/*`, `fix/*`, `chore/*`, or any `trae/*` worktree branch. All commits and pushes MUST target `main`. Local pre-push hook `.githooks/pre-push` enforces this client-side; GitHub-side branch creation requires GitHub Pro on private repos. Any remote branch other than `main` is treated as a policy violation and must be deleted in the same audit cycle.
- **No raw non-GET `fetch` in JS**: All non-GET requests in `app/static/js/*.js` MUST go through `csrfFetch(url, options)` (or the `api` helper). Local pre-commit hook `.githooks/pre-commit` runs `scripts/lint_no_raw_post_fetch.py` and rejects commits that contain `fetch(url, { method: 'POST'|'PUT'|'DELETE'|'PATCH' })`. Enable it once per clone with `git config core.hooksPath .githooks`.

## 防 BUG 规则（2026-07-31 新增）

**修改本仓库任何代码前，请先阅读 [DEVELOPMENT_RULES.md](./DEVELOPMENT_RULES.md)。**

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
- 启用：`git config core.hooksPath .githooks`
- 跳过（不推荐）：`git commit --no-verify`

### 修复 BUG 流程

1. 在 `WMS_BUG_BASELINE.md` 登记（`BUG-YYYY-MM-DD-NNN: <标题>`）
2. commit message 关联 BUG ID：`fix: BUG-2026-07-31-001 xxx`
3. 加回归测试
4. 改状态为"已修复"
