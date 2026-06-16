"""Regression tests: refresh_candidate_scores must persist to the SQL backend.

The pre-SQL refresh path wrote ``_atomic_write_state(latest)`` — the legacy
state.json. After the persistence-layer swap (state.json -> SQL) the worker and
dashboard read state via ``load_state()`` (SQL only), so the refresh — both the
re-scored values AND the one-shot-flag clears — silently never persisted. The
swap updated ``save_state`` but missed this direct call site.

A naive fix (``save_state(latest)``) would be worse: it bulk-upserts every
function through ``_state_func_to_row``, which derives ``run_count`` from the
inline attempts list — and ``_row_to_state_func`` loads that list as ``[]`` for
cost reasons, so a full save would zero ``run_count`` / ``last_run_*`` across the
whole table. The fix uses ``repo.update_function_fields`` to patch only the
columns refresh owns; these tests pin both the persistence and the accumulator
safety.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_FUNDOC_DIR = Path(__file__).resolve().parent.parent.parent / "fun-doc"
if str(_FUNDOC_DIR) not in sys.path:
    sys.path.insert(0, str(_FUNDOC_DIR))


@pytest.fixture
def fundoc_with_repo(tmp_path, monkeypatch):
    """Import fun_doc wired to a fresh temp SQLite repo, with the priority
    queue and batch scorer stubbed so refresh runs without Ghidra."""
    import fun_doc
    from storage import StorageConfig, make_engine
    from storage.repository import Repository

    url = f"sqlite:///{tmp_path / 'state.db'}"
    cfg = StorageConfig(backend="sqlite", url=url, schema=None)
    engine = make_engine(cfg)
    repo = Repository(engine, cfg)
    repo.bootstrap_schema()

    monkeypatch.setattr(fun_doc, "_storage_repo", repo)
    monkeypatch.setattr(fun_doc, "_storage_repo_failed", False)
    # Keep the legacy-fallback writer off the real state.json (only reached if
    # the SQL path regresses, but we never want a test touching live state).
    monkeypatch.setattr(fun_doc, "STATE_FILE", tmp_path / "state.json")

    # Keep refresh's queue-meta bookkeeping off the real priority_queue.json.
    queue = {"pinned": [], "config": {"good_enough_score": 80}, "meta": {}}
    monkeypatch.setattr(fun_doc, "load_priority_queue", lambda: queue)
    monkeypatch.setattr(fun_doc, "save_priority_queue", lambda q: None)

    yield fun_doc, repo, queue, monkeypatch
    engine.dispose()


def _seed_function(repo, *, addr="00400000", score=50, **extra):
    rec = {
        "program_path": "/test/foo.dll",
        "binary_name": "foo.dll",
        "version": "v1",
        "address": addr,
        "name": f"TestFn_{addr}",
        "score": score,
        "fixable": 20.0,
        "has_custom_name": True,
        "has_plate_comment": False,
        "classification": "worker",
        "queue_status": "queued",
        "is_thunk": False,
        "is_external": False,
        "caller_count": 3,
        "last_processed": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }
    rec.update(extra)
    repo.upsert_function(rec)


def _fake_batch_score(score):
    def _inner(addresses, prog_path=None, **kwargs):
        return {
            a: {
                "score": score,
                "fixable": 6.0,
                "has_custom_name": True,
                "has_plate_comment": True,
                "is_leaf": True,
                "classification": "leaf",
                "deductions": [{"category": "plate", "points": 6.0}],
            }
            for a in addresses
        }

    return _inner


def test_refresh_persists_score_to_sql_and_preserves_run_count(fundoc_with_repo):
    fun_doc, repo, _queue, monkeypatch = fundoc_with_repo
    _seed_function(repo, addr="00400000", score=50)
    # Two prior doc runs → run_count == 2. A correct refresh must NOT reset it.
    for delta in (10, 5):
        repo.record_run(
            "/test/foo.dll",
            "00400000",
            {"run_kind": "doc", "provider": "claude", "model": "sonnet", "delta": delta},
        )
    assert repo.get_function("/test/foo.dll", "00400000")["run_count"] == 2

    monkeypatch.setattr(fun_doc, "_batch_score", _fake_batch_score(72))
    state = fun_doc.load_state()
    result = fun_doc.refresh_candidate_scores(
        state, active_binary="foo.dll", count=10, fallback=False
    )
    assert result["refreshed"] == 1

    # The re-scored value must be visible through the SQL store (load_state),
    # not stranded in a dead state.json.
    got = repo.get_function("/test/foo.dll", "00400000")
    assert got["score"] == 72
    assert got["classification"] == "leaf"
    # Accumulator columns are untouched — the landmine save_state() would trip.
    assert got["run_count"] == 2
    assert got["last_run_delta"] == 5


def test_refresh_clears_blacklist_flag_in_sql_for_pinned(fundoc_with_repo):
    """A pinned not_a_function row is admitted (pin bypass) and re-scored;
    refresh must clear the persisted flag, not just the in-memory dict."""
    fun_doc, repo, queue, monkeypatch = fundoc_with_repo
    _seed_function(
        repo,
        addr="00400abc",
        score=50,
        not_a_function=True,
        not_a_function_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        decompile_timeout=True,
    )
    queue["pinned"] = ["/test/foo.dll::00400abc"]

    monkeypatch.setattr(fun_doc, "_batch_score", _fake_batch_score(66))
    state = fun_doc.load_state()
    fun_doc.refresh_candidate_scores(
        state, active_binary="foo.dll", count=10, fallback=False
    )

    got = repo.get_function("/test/foo.dll", "00400abc")
    assert got["score"] == 66
    assert not got["not_a_function"]
    assert not got["decompile_timeout"]
    assert got["not_a_function_at"] is None
