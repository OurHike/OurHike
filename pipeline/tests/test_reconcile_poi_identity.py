"""The POI identity ledger's tier-1 contract (#671, features/POI_IDENTITY.md).

reconcile() is pure - prior rows plus this snapshot's records in, the next
ledger and a named outcome out - so every branch is held here on synthetic
rows, no corridor on disk. The I/O half (published_records) reuses
export_poi's own reading functions and is exercised by the real seeding run
and the publish workflow's --check, per that function's docstring.
"""

import json

import pytest

import export_poi
from reconcile_poi_identity import (
    Outcome,
    load_ledger,
    mass_retirement_refusal,
    reconcile,
    render,
    summarize,
)

RELEASE = "2026-08-18"
LATER = "2027-09-14"


def _record(source="atc_shelters", sfid="glob-1", name="Test Shelter", lat=41.0, lon=-74.0, poi_type="shelter"):
    return {
        "id": f"{source}:{sfid}",
        "source": source,
        "source_feature_id": sfid,
        "name": name,
        "lat": lat,
        "lon": lon,
        "poi_type": poi_type,
    }


def _seeded(record):
    return reconcile({}, [record], RELEASE).pois


def test_seeding_mints_the_derived_id_as_the_birthmark():
    outcome = reconcile({}, [_record()], RELEASE)

    assert outcome.minted == ["atc_shelters:glob-1"]
    row = outcome.pois["atc_shelters:glob-1"]
    assert row["source"] == "atc_shelters"
    assert row["source_feature_id"] == "glob-1"
    assert row["first_seen"] == RELEASE
    assert row["history"] == []


def test_a_surviving_key_carries_the_id_and_takes_upstreams_edits_silently():
    """Tier 1: name and position are upstream's to change; the carry itself
    is the whole refresh under a key-stable year, and it writes no history -
    wholly unchanged places must produce no diff lines at all."""
    prior = _seeded(_record())
    moved = _record(name="Test Shelter (rebuilt)", lat=41.0001, lon=-74.0001)

    outcome = reconcile(prior, [moved], LATER)

    assert outcome.carried == ["atc_shelters:glob-1"]
    assert outcome.minted == [] and outcome.retired == [] and outcome.held == []
    row = outcome.pois["atc_shelters:glob-1"]
    assert row["name"] == "Test Shelter (rebuilt)"
    assert row["lat"] == 41.0001
    assert row["history"] == [], "a tier-1 carry is silent - history is for identity events"
    assert row["first_seen"] == RELEASE, "the birth date never moves"


def test_a_surviving_key_that_teleported_is_held_not_carried():
    """The teleport guard: ATC's real refresh moves things a few feet, and a
    surviving key a mile away is evidence of key REUSE - carrying it would
    put one place's history on another place's point."""
    prior = _seeded(_record())
    teleported = _record(lat=41.1, lon=-74.0)  # ~11 km north

    outcome = reconcile(prior, [teleported], LATER)

    assert outcome.carried == []
    assert len(outcome.held) == 1
    assert "moved" in outcome.held[0]
    assert outcome.retired == [], "the held row's fate is the question - retiring it would answer it"
    assert outcome.pois["atc_shelters:glob-1"]["lat"] == 41.0, "a held row is left exactly as it was"


def test_a_surviving_key_that_changed_poi_type_is_held():
    prior = _seeded(_record())

    outcome = reconcile(prior, [_record(poi_type="campsite")], LATER)

    assert outcome.carried == []
    assert len(outcome.held) == 1
    assert "poi_type" in outcome.held[0]


def test_a_disappeared_row_retires_with_its_history_written():
    """Tier 3's retire half - the default because it is the RECOVERABLE
    mistake: a tombstone re-unites with its successor by a later override,
    where a wrong merge cannot be unmade."""
    prior = _seeded(_record())

    outcome = reconcile(prior, [], LATER)

    assert outcome.retired == ["atc_shelters:glob-1"]
    row = outcome.pois["atc_shelters:glob-1"]
    assert row["retired"] == LATER
    assert row["history"] == [{"release": LATER, "event": "retired"}]
    assert row["name"] == "Test Shelter", "retirement keeps everything the row had"


def test_a_retired_id_resurfacing_is_held_because_ids_are_never_reused():
    prior = _seeded(_record())
    prior = reconcile(prior, [], LATER).pois  # retire it

    outcome = reconcile(prior, [_record()], "2028-09-12")

    assert outcome.minted == []
    assert len(outcome.held) == 1
    assert "never reused" in outcome.held[0]


def test_a_retired_row_is_never_matched_by_key():
    """Retired rows are out of the key index entirely - a new feature with
    the same key must not silently resurrect the old identity."""
    prior = _seeded(_record())
    prior = reconcile(prior, [], LATER).pois

    outcome = reconcile(prior, [_record(sfid="glob-2")], "2028-09-12")

    assert outcome.minted == ["atc_shelters:glob-2"]
    assert "retired" in outcome.pois["atc_shelters:glob-1"]


def test_duplicate_keys_in_one_snapshot_are_held():
    outcome = reconcile({}, [_record(), _record(name="Impostor")], RELEASE)

    assert len(outcome.held) == 1
    assert "duplicate" in outcome.held[0] or "same" in outcome.held[0]


def test_the_mass_retirement_guard_refuses_the_wholesale_re_mint():
    """The silent catastrophe made loud: every key changes, and instead of
    writing 3,000 tombstones the run refuses - #672's evidence matching is
    the recovery, not a massacre nobody decided on."""
    prior = {}
    records = [_record(sfid=f"old-{i}", lat=40.0 + i * 0.01) for i in range(30)]
    prior = reconcile(prior, records, RELEASE).pois
    re_minted = [_record(sfid=f"new-{i}", lat=40.0 + i * 0.01) for i in range(30)]

    outcome = reconcile(prior, re_minted, LATER)
    refusal = mass_retirement_refusal(outcome, prior)

    assert refusal is not None
    assert "REFUSED" in refusal


def test_a_refresh_sized_retirement_is_not_refused():
    prior = {}
    records = [_record(sfid=f"s-{i}", lat=40.0 + i * 0.01) for i in range(30)]
    prior = reconcile(prior, records, RELEASE).pois

    outcome = reconcile(prior, records[:-2], LATER)  # two features genuinely gone

    assert mass_retirement_refusal(outcome, prior) is None
    assert len(outcome.retired) == 2


def test_render_is_one_row_per_line_sorted_and_json(tmp_path):
    """The serialization IS the review surface: one line per place keeps a
    refresh's identity outcome readable as a per-place diff, and keeps the
    file under test_no_committed_data.py's reference-review ceiling."""
    pois = reconcile({}, [_record(sfid="b"), _record(sfid="a", name="Alpha")], RELEASE).pois

    rendered = render(pois)

    parsed = json.loads(rendered)
    assert list(parsed["pois"]) == ["atc_shelters:a", "atc_shelters:b"]
    row_lines = [line for line in rendered.splitlines() if line.startswith('"atc_shelters:')]
    assert len(row_lines) == 2, "one line per row, or the diff stops being per-place"

    path = tmp_path / "poi_identity.json"
    path.write_text(rendered)
    assert load_ledger(path) == parsed["pois"]


def test_summarize_names_every_new_and_retired_row():
    prior = _seeded(_record())
    outcome = reconcile(prior, [_record(sfid="glob-2", name="Newcomer")], LATER)

    text = summarize(outcome, seeded=False)

    assert "+ atc_shelters:glob-2" in text and "Newcomer" in text
    assert "- atc_shelters:glob-1" in text and "Test Shelter" in text


def test_summarize_does_not_name_three_thousand_seed_rows():
    outcome = Outcome(pois={}, minted=[f"id-{i}" for i in range(3000)])

    text = summarize(outcome, seeded=True)

    assert len(text.splitlines()) < 5


# --- the export side: publishing under ledger ids ---------------------------


def _write_ledger(tmp_path, pois):
    path = tmp_path / "poi_identity.json"
    path.write_text(render(pois))
    return path


def test_export_applies_a_carried_ledger_id(tmp_path):
    """The load-bearing line: upstream re-keyed the feature, the ledger
    carried the id, and the export publishes the CARRIED id so everything
    anchored to it survives."""
    pois = {
        "atc_shelters:old-key": {
            "poi_type": "shelter",
            "source": "atc_shelters",
            "source_feature_id": "new-key",  # tier 2 carried it onto the new key
            "name": "Test Shelter",
            "lat": 41.0,
            "lon": -74.0,
            "first_seen": RELEASE,
            "history": [],
        }
    }
    records = [_record(sfid="new-key")]

    changed = export_poi.apply_ledger_ids(records, _write_ledger(tmp_path, pois))

    assert changed == 1
    assert records[0]["id"] == "atc_shelters:old-key"


def test_export_leaves_a_record_the_ledger_does_not_know_on_its_derived_id(tmp_path):
    """A brand-new feature before reconcile has run keeps its derived id -
    which is exactly the id reconcile will mint for it, so the two spellings
    agree by construction."""
    records = [_record(sfid="unseen")]

    changed = export_poi.apply_ledger_ids(records, _write_ledger(tmp_path, {}))

    assert changed == 0
    assert records[0]["id"] == "atc_shelters:unseen"


def test_export_never_publishes_under_a_retired_rows_id(tmp_path):
    pois = {
        "atc_shelters:old-key": {
            "poi_type": "shelter",
            "source": "atc_shelters",
            "source_feature_id": "new-key",
            "name": "Test Shelter",
            "lat": 41.0,
            "lon": -74.0,
            "first_seen": RELEASE,
            "history": [{"release": LATER, "event": "retired"}],
            "retired": LATER,
        }
    }
    records = [_record(sfid="new-key")]

    changed = export_poi.apply_ledger_ids(records, _write_ledger(tmp_path, pois))

    assert changed == 0
    assert records[0]["id"] == "atc_shelters:new-key"


def test_export_without_a_ledger_is_the_pre_671_world(tmp_path):
    records = [_record()]

    changed = export_poi.apply_ledger_ids(records, tmp_path / "absent.json")

    assert changed == 0
    assert records[0]["id"] == "atc_shelters:glob-1"


def test_the_real_ledger_stays_under_the_reference_review_ceiling():
    """test_no_committed_data.py holds reference/ files to 8,000 lines; the
    ledger's one-row-per-line serialization is what keeps ~3,000 published
    POIs inside it. This trips BEFORE that guard does, with a message that
    says what to do about it."""
    if not export_poi.LEDGER_PATH.exists():
        pytest.skip("no seeded ledger in this checkout")
    lines = export_poi.LEDGER_PATH.read_text(encoding="utf-8").count("\n")
    assert lines < 7_500, (
        "the ledger is approaching the reference-review ceiling - time to decide its next shelf "
        "(features/POI_IDENTITY.md's open question) rather than trip the committed-data guard cold"
    )
