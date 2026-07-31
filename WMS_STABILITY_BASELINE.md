# WMS Stability Baseline

Task: AI-STAB-F01

The required release gate covers these ten critical chains:

1. Login, CSRF, initial-password policy, and account lockout.
2. Material, supplier, customer, warehouse, and unit master data.
3. Purchase inbound draft, completion, reversal, deletion, and stock rollback.
4. Sales and requisition outbound stock protection and reversal.
5. Transfer, stocktaking, adjustment, and opening-stock consistency.
6. Customer-supplied material ownership and downstream restrictions.
7. AI/OCR delivery notices: draft-only creation and human confirmation.
8. AI duplicate prevention, authorization, and audit boundaries.
9. Empty-database migration and application startup.
10. Windows offline installation and wheelhouse dependency resolution.

Every confirmed defect requires a reproducible test, an isolated test database,
and a dedicated commit before it can be marked resolved.
