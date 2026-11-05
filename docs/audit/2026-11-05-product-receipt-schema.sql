-- FEAT-2026-11-05-107, 2026-11-05.
-- Apply only after explicit authorization, verified backup, stopped service
-- and acquisition of the existing runtime_guard database lease.
-- Existing rows remain NULL; no inventory or document data is rewritten.
ALTER TABLE in_order_item ADD COLUMN box_no VARCHAR(100);
