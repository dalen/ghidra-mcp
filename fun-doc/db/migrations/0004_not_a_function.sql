-- fun-doc migration 0004: not_a_function / decompile_timeout persistence (Postgres).
--
-- These two one-shot blacklist flags were set in-memory by process_function
-- and "persisted" via update_function_state, but they had no backing column,
-- so the SQL round-trip dropped them. Because the worker reloads state from
-- the SQL backend on every selector pass (web.py: "Reload state each
-- iteration to get fresh scores/queue"), the selector never saw the flag and
-- re-picked the same address forever — re-detecting "not a function" /
-- "decompile timeout", re-logging the skip message, and never actually
-- skipping. See fun_doc.select_candidates gates on not_a_function /
-- decompile_timeout.
--
--   * not_a_function     — address the priority queue lists as a function but
--                          Ghidra returns no decompiled body and no
--                          function_name (raw data / un-disassembled dead
--                          code). Set in process_function.
--   * not_a_function_at  — when it was flagged (audit trail, like
--                          library_code_at / decompile_timeout_at).
--   * decompile_timeout  — boolean companion to the existing
--                          decompile_timeout_at column (0001). The selector
--                          gates on the boolean; only the timestamp persisted
--                          before, so the gate never fired after a reload.
--
-- All three clear on the existing refresh paths (--scan --refresh, dashboard
-- Refresh Top N), same as library_code. Mirrored at
-- 0004_not_a_function.sqlite.sql for the SQLite backend.

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS not_a_function BOOLEAN DEFAULT FALSE;

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS not_a_function_at TIMESTAMPTZ;

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS decompile_timeout BOOLEAN DEFAULT FALSE;
