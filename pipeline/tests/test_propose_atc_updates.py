"""propose_atc_updates.py: the ambiguous residue #963's gate refuses,
drafted for a person rather than left in a workflow log (#463).
"""

from __future__ import annotations

import json
import re

import pytest

import propose_atc_updates


def reviewed(reviewed_at="2026-08-24", updates=None):
    return {"reviewed_at": reviewed_at, "updates": updates if updates is not None else []}


def cached_entry(**overrides) -> dict:
    """One entry as `fetch_atc_updates.py` writes it into the raw cache.

    Two disagreeing mile references by default - the Iron Mtn Gap shape this
    feature exists for - so a test that does not care about the reason stays
    actionable without having to say so.
    """
    return {
        "title": "NC/TN: Iron Mtn Gap Reopened",
        "category": "Detour",
        "states": ["NC", "TN"],
        "date_modified": "2026-08-27T13:58:38Z",
        "date_published": "2026-08-27T13:58:38Z",
        "miles": [
            {"direction": "NOBO", "start": 360.6, "end": 364.8, "raw": "NOBO mile 360.6 to 364.8"},
            {"direction": "NOBO", "start": 364.7, "end": None, "raw": "NOBO mile 364.7"},
        ],
        "text": "...",
        "listed": True,
        **overrides,
    }


@pytest.fixture
def propose(tmp_path, monkeypatch):
    def run(document: dict, cache_entries: dict | None = None):
        reviewed_path = tmp_path / "atc_updates.json"
        reviewed_path.write_text(json.dumps(document))
        out_path = tmp_path / "atc_updates_proposed.json"
        cache_path = tmp_path / "raw" / "atc_updates.json"
        if cache_entries is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"updates": cache_entries}))
        monkeypatch.setattr(propose_atc_updates, "REVIEWED_PATH", reviewed_path)
        monkeypatch.setattr(propose_atc_updates, "OUT_PATH", out_path)
        monkeypatch.setattr(propose_atc_updates, "CACHE_PATH", cache_path)
        return propose_atc_updates.main(), out_path

    return run


def test_an_ambiguous_update_becomes_a_candidate(propose):
    """The Iron Mtn Gap shape this whole feature was written about: several
    mile references, none of them mechanically distinguishable."""
    manifest, out_path = propose(
        reviewed(),
        {"iron-mtn-gap-detour": cached_entry()},
    )

    document = json.loads(out_path.read_text())
    assert [c["atc_id"] for c in document["candidates"]] == ["iron-mtn-gap-detour"]
    assert document["candidates"][0]["reason_not_auto_published"] == "2 mile references that do not agree on one place"
    assert manifest["candidate_count"] == 1


def test_a_candidate_carries_every_mile_reference_not_just_one(propose):
    """The whole reason this needs a person: which of several is current is
    not something the parse can decide, so nothing here decides it either."""
    entry = cached_entry(
        miles=[
            {"direction": "NOBO", "start": 360.6, "end": 364.8, "raw": "NOBO mile 360.6 to 364.8"},
            {"direction": "NOBO", "start": 364.7, "end": None, "raw": "NOBO mile 364.7"},
        ]
    )
    _, out_path = propose(reviewed(), {"iron-mtn-gap-detour": entry})

    candidate = json.loads(out_path.read_text())["candidates"][0]
    assert len(candidate["mile_references"]) == 2
    assert candidate["mile_references"][1]["raw"] == "NOBO mile 364.7"


def test_a_candidate_never_carries_a_mile_marker_of_its_own(propose):
    """No `start_mile_marker`/`end_mile_marker` at all - this is not a draft
    row in atc_updates.json's shape, it is a different file a person reads
    before ever typing one."""
    _, out_path = propose(reviewed(), {"iron-mtn-gap-detour": cached_entry()})

    candidate = json.loads(out_path.read_text())["candidates"][0]
    assert "start_mile_marker" not in candidate
    assert "end_mile_marker" not in candidate


def test_an_update_the_gate_already_auto_publishes_is_not_proposed(propose):
    """#963's whole point: an unambiguous update since the review ships on
    its own. Proposing it too would be asking a person to re-check something
    that already reached the map."""
    entry = cached_entry(
        title="A clean one-reference update",
        miles=[{"direction": "NOBO", "start": 500.0, "end": None, "raw": "NOBO mile 500.0"}],
    )
    _, out_path = propose(reviewed(), {"clean-update": entry})

    assert json.loads(out_path.read_text())["candidates"] == []


def test_an_already_reviewed_update_is_not_proposed(propose):
    """A person's row always wins - re-proposing something already in
    atc_updates.json would ask them to redo work they finished."""
    row = {
        "atc_id": "already-reviewed",
        "title": "x",
        "category": "Closure",
        "states": ["VA"],
        "start_mile_marker": 100.0,
        "end_mile_marker": 101.0,
        "obstructs_trail": False,
        "updated_at": "2026-08-01T00:00:00Z",
        "source_url": "https://appalachiantrail.org/trail-updates/already-reviewed/",
    }
    entry = cached_entry(
        title="x",
        miles=[
            {"direction": "NOBO", "start": 100.0, "end": None, "raw": "a"},
            {"direction": "NOBO", "start": 200.0, "end": None, "raw": "b"},
        ],
    )
    _, out_path = propose(reviewed(updates=[row]), {"already-reviewed": entry})

    assert json.loads(out_path.read_text())["candidates"] == []


def test_an_update_not_edited_since_the_review_is_not_proposed(propose):
    """The other steady-state refusal: everything unreviewed IS the
    reviewer's reject pile until ATC touches it again after the review date."""
    entry = cached_entry(date_modified="2026-08-01T00:00:00Z")
    _, out_path = propose(reviewed(reviewed_at="2026-08-24"), {"old-and-refused": entry})

    assert json.loads(out_path.read_text())["candidates"] == []


def test_an_unreviewed_file_proposes_nothing_and_does_not_fail(propose, capsys):
    """No baseline to measure "posted since" against - same stance as
    export_atc_updates.py, and for the same reason."""
    manifest, out_path = propose(reviewed(reviewed_at=None), {"x": cached_entry()})

    assert manifest is None
    assert not out_path.exists()
    assert "reviewed_at" in capsys.readouterr().out


def test_a_missing_cache_proposes_nothing_rather_than_failing(propose):
    """`fetch_atc_updates.py` not having run yet, or having failed, costs the
    proposal and nothing else - the reviewed rows this file never touches are
    unaffected either way."""
    manifest, out_path = propose(reviewed(), None)

    assert manifest["candidate_count"] == 0
    assert json.loads(out_path.read_text())["candidates"] == []


def test_the_output_carries_the_review_baseline_it_was_measured_against(propose):
    """A reader of this file alone should be able to tell how old the review
    is - the same reason export_atc_updates.py's own artifact carries it."""
    _, out_path = propose(reviewed(reviewed_at="2026-08-24"), {"iron-mtn-gap-detour": cached_entry()})

    assert json.loads(out_path.read_text())["reviewed_at"] == "2026-08-24"


def test_rerunning_with_nothing_new_produces_the_same_candidates(propose):
    """The workflow decides whether to open a pull request from whether this
    file's content changed, so a rerun against the same inputs must not
    reorder or reshape anything on its own."""
    cache = {"iron-mtn-gap-detour": cached_entry(), "nc-tn-elk-river": cached_entry(title="Elk River")}
    _, first_path = propose(reviewed(), cache)
    first = first_path.read_text()

    _, second_path = propose(reviewed(), cache)
    second = second_path.read_text()

    def strip_generated_at(text: str) -> str:
        return re.sub(r'"generated_at": "[^"]+"', '"generated_at": "X"', text)

    assert strip_generated_at(first) == strip_generated_at(second)
