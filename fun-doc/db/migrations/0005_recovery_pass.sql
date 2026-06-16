-- fun-doc migration 0005: recovery_pass one-shot persistence (Postgres).
--
-- Same class of bug as 0004 (not_a_function / decompile_timeout): the
-- recovery_pass one-shot is set in-memory by process_function and "saved" via
-- update_function_state, but had no backing column, so the SQL round-trip
-- dropped it. The worker reloads state every selector pass, so the selector
-- never saw recovery_pass_done and re-ran the (opus-expensive) complexity-
-- forced recovery pass on the same massive function repeatedly — the exact
-- "re-queue forever below good_enough" loop the one-shot was meant to stop.
-- See the select_candidates gate on recovery_pass_done.
--
--   * recovery_pass_done  — the function already got its single complexity-
--                           forced recovery pass; exclude until refresh.
--   * recovery_pass_score — score captured at that pass (audit trail).
--   * recovery_pass_at    — when it ran (audit trail; cleared on refresh).
--
-- Cleared on the existing refresh paths, same as the other one-shots.
-- Mirrored at 0005_recovery_pass.sqlite.sql for the SQLite backend.

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS recovery_pass_done BOOLEAN DEFAULT FALSE;

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS recovery_pass_score INTEGER;

ALTER TABLE fun_doc.functions_workflow
    ADD COLUMN IF NOT EXISTS recovery_pass_at TIMESTAMPTZ;
