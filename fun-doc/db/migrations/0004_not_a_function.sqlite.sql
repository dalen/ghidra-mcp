-- fun-doc migration 0004: not_a_function / decompile_timeout persistence (SQLite).
--
-- Mirror of 0004_not_a_function.sql for the SQLite backend. Differences are
-- dialect-only (TIMESTAMPTZ -> TEXT, BOOLEAN -> INTEGER 0/1). See the Postgres
-- file for design rationale and the consumer wiring in fun_doc.py
-- (select_candidates, _state_func_to_row, _row_to_state_func).
--
-- SQLite doesn't support ALTER TABLE ADD COLUMN IF NOT EXISTS. fun-doc's
-- migration runner (db/migrate.py) makes this idempotent automatically by
-- inspecting PRAGMA table_info(functions_workflow) before each ADD COLUMN and
-- skipping ones whose column is already present, so a crashed-mid-script retry
-- (column landed but the schema_versions row didn't) succeeds on the next run.

ALTER TABLE functions_workflow ADD COLUMN not_a_function INTEGER DEFAULT 0;
ALTER TABLE functions_workflow ADD COLUMN not_a_function_at TEXT;
ALTER TABLE functions_workflow ADD COLUMN decompile_timeout INTEGER DEFAULT 0;
