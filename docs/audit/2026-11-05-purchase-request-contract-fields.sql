-- 2026-11-05: user approved online backup followed by only these two nullable columns.
-- Existing records receive NULL; no UPDATE, DELETE, inventory or account operations.
-- Apply only after exact CI, release acceptance, and a verified online backup.
BEGIN IMMEDIATE;
ALTER TABLE purchase_request_item ADD COLUMN contract_no VARCHAR(50);
ALTER TABLE purchase_request_item ADD COLUMN project_name VARCHAR(200);
COMMIT;
