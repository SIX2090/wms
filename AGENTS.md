# Project Rules

- AI document workflows must prioritize strong OCR/image understanding for Chinese warehouse documents, especially delivery notes that generate inbound drafts.
- AI may create and inspect drafts, but submit/audit/complete/void/delete actions must stay manual unless the user explicitly authorizes a high-risk operation.
- WeChat text or screenshot shipment notices such as "明天发鑫达 6204轴承 100套，M8螺母 500个" are supplier delivery notices and must generate inbound delivery/purchase receipt drafts, not purchase requests.
- AI must never modify, reset, or set any user account password (including the admin bootstrap password) unless the user explicitly authorizes the specific operation. Password operations require explicit prior approval.
- The system must never auto-generate a random password for any account (including the bootstrap admin). When `WMS_BOOTSTRAP_PASSWORD` is not set, the system must use a fixed default password ('admin') with a warning, not `secrets.token_urlsafe` or any random generator. Random password generation hides credentials from the operator and violates password transparency.
- After completing any task, AI must verify the result (e.g., check service status, test functionality, confirm output correctness) before reporting to the user. Unverified results must not be presented as done.
- After completing any task, AI must commit and push changes to GitHub unless the user explicitly says not to.
- `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` is the sole AI development backlog and completion ledger. Before implementing an AI feature, check its unique task ID, current status, existing code, tests, pages, and Git history; never redevelop a completed or equivalent capability.
- Every AI code change must map to one unique ledger task ID. Add a new task only after a repository-wide duplicate check; fixes to completed capabilities must use a child fix ID instead of duplicating the original task.
- Mark an AI task complete only after code, permissions, human-confirmation boundaries, tests, documentation, verification, commit, and push are complete. Immediately record completion date, commit hash, changed modules, validation commands, result, and remaining child items in the ledger.
- At the end of each AI task, reconcile the ledger against AI routes, tools, models, templates, feature flags, migrations, and verification scripts so implemented capabilities are not omitted and planned capabilities are not falsely reported as implemented.
