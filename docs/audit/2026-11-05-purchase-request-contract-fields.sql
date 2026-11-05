-- 2026-11-05: review only; not authorized for the production database.
-- Existing records receive NULL; no UPDATE, DELETE, inventory or account operations.
-- Apply only to a confirmed target after the user resolves the no-production-database constraint.
BEGIN IMMEDIATE;
ALTER TABLE purchase_request_item ADD COLUMN contract_no VARCHAR(50);
ALTER TABLE purchase_request_item ADD COLUMN project_name VARCHAR(200);
COMMIT;
