"""Regression tests for the project-folder scope guard.

Root cause of a "every real function is flagged NOT A FUNCTION" incident:
`_get_project_folder()` read the project folder from the legacy state.json,
which went dead with the state.json->SQL persistence swap and still held a
stale folder ('/Mods/PD2-S12') from a previous project. The live project was
WAR.exe, so every '/WAR.exe' Ghidra call was scope-blocked client-side;
`fetch_function_data` then mis-read that block as not_a_function — and once
not_a_function began persisting (blacklist columns), the false hits became
permanent.

Two fixes, pinned here:
  1. `_get_project_folder` reads the SQL meta (live source), falling back to
     state.json only when no backend is available.
  2. `fetch_function_data` treats a scope-guard block as retryable
     (ghidra_offline), never as not_a_function.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FUNDOC_DIR = Path(__file__).resolve().parent.parent.parent / "fun-doc"
if str(_FUNDOC_DIR) not in sys.path:
    sys.path.insert(0, str(_FUNDOC_DIR))


def _temp_repo(tmp_path):
    from storage import StorageConfig, make_engine
    from storage.repository import Repository

    cfg = StorageConfig(backend="sqlite", url=f"sqlite:///{tmp_path / 's.db'}", schema=None)
    engine = make_engine(cfg)
    repo = Repository(engine, cfg)
    repo.bootstrap_schema()
    return engine, repo


def test_get_project_folder_prefers_sql_meta_over_stale_state_json(tmp_path, monkeypatch):
    import fun_doc

    engine, repo = _temp_repo(tmp_path)
    repo.set_meta(project_folder="/Live/WAR")
    stale = tmp_path / "state.json"
    stale.write_text('{"project_folder": "/Mods/PD2-S12"}', encoding="utf-8")

    monkeypatch.setattr(fun_doc, "_storage_repo", repo)
    monkeypatch.setattr(fun_doc, "_storage_repo_failed", False)
    monkeypatch.setattr(fun_doc, "STATE_FILE", stale)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_CACHED", None)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_OVERRIDE", "")

    assert fun_doc._get_project_folder() == "/Live/WAR"
    engine.dispose()


def test_get_project_folder_root_meta_disables_enforcement(tmp_path, monkeypatch):
    """The observed live value was '/' (no scoping). It must normalize to ''
    so the guard passes every program — not block them all."""
    import fun_doc

    engine, repo = _temp_repo(tmp_path)
    repo.set_meta(project_folder="/")
    stale = tmp_path / "state.json"
    stale.write_text('{"project_folder": "/Mods/PD2-S12"}', encoding="utf-8")

    monkeypatch.setattr(fun_doc, "_storage_repo", repo)
    monkeypatch.setattr(fun_doc, "_storage_repo_failed", False)
    monkeypatch.setattr(fun_doc, "STATE_FILE", stale)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_CACHED", None)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_OVERRIDE", "")

    assert fun_doc._get_project_folder() == ""
    # And a real WAR.exe program is therefore in-scope (no error).
    norm, err = fun_doc._validate_program_param("/WAR.exe")
    assert err is None and norm == "/WAR.exe"
    engine.dispose()


def test_get_project_folder_env_override_wins(tmp_path, monkeypatch):
    import fun_doc

    engine, repo = _temp_repo(tmp_path)
    repo.set_meta(project_folder="/Live/WAR")
    monkeypatch.setattr(fun_doc, "_storage_repo", repo)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_CACHED", None)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_OVERRIDE", "/Env/Override")

    assert fun_doc._get_project_folder() == "/Env/Override"
    engine.dispose()


def test_get_project_folder_falls_back_to_state_json_without_repo(tmp_path, monkeypatch):
    import fun_doc

    stale = tmp_path / "state.json"
    stale.write_text('{"project_folder": "/Legacy/Proj"}', encoding="utf-8")
    monkeypatch.setattr(fun_doc, "_storage_repo", None)
    monkeypatch.setattr(fun_doc, "_storage_repo_failed", True)  # _get_storage_repo -> None
    monkeypatch.setattr(fun_doc, "STATE_FILE", stale)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_CACHED", None)
    monkeypatch.setattr(fun_doc, "_PROJECT_FOLDER_OVERRIDE", "")

    assert fun_doc._get_project_folder() == "/Legacy/Proj"


def test_is_scope_blocked_detection():
    import fun_doc

    blocked = {
        "error": "scope guard blocked call: program path '/WAR.exe' is outside "
        "scoped project folder '/Mods/PD2-S12'"
    }
    assert fun_doc._is_scope_blocked(blocked) is True
    # Real Ghidra errors / answers must NOT match.
    assert fun_doc._is_scope_blocked({"error": "No function at address"}) is False
    assert fun_doc._is_scope_blocked({"function_name": "Foo"}) is False
    assert fun_doc._is_scope_blocked("/* decompiled body */") is False
    assert fun_doc._is_scope_blocked(None) is False


def test_fetch_function_data_scope_block_is_offline_not_not_a_function(monkeypatch):
    """A scope-guard block must surface as ghidra_offline (retryable), never
    not_a_function — otherwise a misconfigured project_folder permanently
    blacklists every real function it touches."""
    import fun_doc

    def fake_get(path, params=None, timeout=60):
        return {
            "error": "scope guard blocked call: program path '/WAR.exe' is "
            "outside scoped project folder '/Mods/PD2-S12'"
        }

    monkeypatch.setattr(fun_doc, "ghidra_get", fake_get)
    monkeypatch.setattr(fun_doc, "ghidra_last_call_timed_out", lambda: False)
    monkeypatch.setattr(fun_doc, "ghidra_last_call_offline", lambda: False)

    d = fun_doc.fetch_function_data("/WAR.exe", "005760c9", mode="FIX")
    assert d["ghidra_offline"] is True
    assert d["not_a_function"] is False
