# WMS Stability Baseline

Task: AI-STAB-F01
Status: active stabilization baseline
Date: 2026-07-31

## Scope

The stabilization program blocks unrelated feature work while these business
chains are made reproducible and regression-tested:

1. Login, CSRF, initial-password policy, and account lockout.
2. Material, supplier, and customer master data.
3. Purchase inbound draft, completion, reversal, and inventory rollback.
4. Completed-document deletion protection.
5. Sales outbound stock validation, completion, and reversal.
6. Transfer, stocktaking, and inventory adjustment consistency.
7. AI delivery notice processing: inbound draft only, never purchase request.
8. AI draft confirmation, duplication protection, and permission boundaries.
9. Empty-database startup and database migration.
10. Windows offline installation and dependency resolution.

## Release Gate

Every stabilization fix must add a failing regression test before the code fix
and pass the commands below before it can be committed:

```text
py scripts/lint_wms_rules.py
py scripts/lint_no_raw_post_fetch.py
py scripts/verify_wms_bugs.py
py scripts/verify_offline_wheelhouse.py
pytest tests/ -q
```

## Current Evidence

- 2026-07-31: the existing suite passed with 103 tests.
- 2026-07-31: offline wheelhouse resolution passed with `--no-index` and
  `--ignore-installed`.
- The next atomic action is to add isolated state-transition coverage for
  purchase inbound completion, reversal, and deletion protection.

## Repair Rules

- One BUG ID per atomic fix; do not batch unrelated repairs.
- Record reproduction, root cause, test, verification, and commit SHA in
  `WMS_BUG_BASELINE.md`.
- AI may inspect or create drafts only. Submit, audit, complete, void, delete,
  and reversal actions remain explicit human operations.
