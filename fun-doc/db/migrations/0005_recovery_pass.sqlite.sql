-- fun-doc migration 0005: recovery_pass one-shot persistence (SQLite).
--
-- Mirror of 0005_recovery_pass.sql for the SQLite backend. Differences are
-- dialect-only (TIMESTAMPTZ -> TEXT, BOOLEAN -> INTEGER 0/1). See the Postgres
-- file for design rationale and the consumer wiring in fun_doc.py.
--
-- SQLite has no ALTER TABLE ADD COLUMN IF NOT EXISTS; db/migrate.py makes each
-- ADD COLUMN idempotent by inspecting PRAGMA table_info first.

ALTER TABLE functions_workflow ADD COLUMN recovery_pass_done INTEGER DEFAULT 0;
ALTER TABLE functions_workflow ADD COLUMN recovery_pass_score INTEGER;
ALTER TABLE functions_workflow ADD COLUMN recovery_pass_at TEXT;
