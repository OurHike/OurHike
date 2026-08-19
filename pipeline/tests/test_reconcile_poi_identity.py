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


def test_a_wholesale_re_mint_with_intact_evidence_is_carried_not_blocked():
    """The promotion #672 buys: every upstream key changes, and because the
    places themselves did not (same names, same spots), tier 2 carries
    every id and the refresh lands instead of blocking."""
    prior = {}
    records = [_record(sfid=f"old-{i}", name=f"Shelter {i}", lat=40.0 + i * 0.1) for i in range(30)]
    prior = reconcile(prior, records, RELEASE).pois
    re_minted = [_record(sfid=f"new-{i}", name=f"Shelter {i}", lat=40.0 + i * 0.1) for i in range(30)]

    outcome = reconcile(prior, re_minted, LATER)

    assert len(outcome.matched) == 30
    assert outcome.retired == [] and outcome.minted == []
    assert mass_retirement_refusal(outcome, prior) is None
    row = outcome.pois["atc_shelters:old-0"]
    assert row["source_feature_id"] == "new-0", "provenance tells the new truth"
    assert row["history"][-1]["source_feature_id_was"] == "old-0"


def test_the_mass_retirement_guard_refuses_what_evidence_cannot_carry():
    """The silent catastrophe made loud: every key changes AND nothing
    matches (new names, new spots), and instead of writing 3,000 tombstones
    the run refuses - a massacre nobody decided on stays unwritten."""
    prior = {}
    records = [_record(sfid=f"old-{i}", name=f"Shelter {i}", lat=40.0 + i * 0.1) for i in range(30)]
    prior = reconcile(prior, records, RELEASE).pois
    unrecognizable = [_record(sfid=f"new-{i}", name=f"Different {i}", lat=44.0 + i * 0.1) for i in range(30)]

    outcome = reconcile(prior, unrecognizable, LATER)
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


# --- tier 2: the evidence, and the three-condition acceptance (#672) ---------


def test_a_renamed_rekeyed_shelter_is_carried_by_its_fingerprint():
    """The design's own example: a renamed, moved-a-few-feet shelter that
    still says "built 1938, one storey, log" is carrying its own passport."""
    prior = _seeded({**_record(name="Winturri Shelter"), "fingerprint": {"Year_Built": 1938, "Stories": 1}})
    successor = {
        **_record(sfid="rekeyed", name="Wintturi Shelter", lat=41.0001),
        "fingerprint": {"Year_Built": 1938, "Stories": 1},
    }

    outcome = reconcile(prior, [successor], LATER)

    assert len(outcome.matched) == 1
    assert "fingerprint intact" in outcome.matched[0]
    row = outcome.pois["atc_shelters:glob-1"]
    assert row["name"] == "Wintturi Shelter"
    assert row["source_feature_id"] == "rekeyed"
    assert row["history"][-1]["event"] == "matched"
    assert row["history"][-1]["name_was"] == "Winturri Shelter"


def test_the_hard_ceiling_is_minned_against_everything():
    """The 903 km lesson: however perfect the name and fingerprint, a pair
    past the ceiling is not a candidate at all."""
    prior = _seeded({**_record(name="Generic Campsite"), "fingerprint": {"Year_Built": 1990}})
    far_twin = {
        **_record(sfid="far", name="Generic Campsite", lat=44.0),  # ~330 km
        "fingerprint": {"Year_Built": 1990},
    }

    outcome = reconcile(prior, [far_twin], LATER)

    assert outcome.matched == []
    assert outcome.retired == ["atc_shelters:glob-1"]
    assert outcome.minted == ["atc_shelters:far"]


def test_two_candidates_that_reduce_alike_go_to_review_not_to_a_guess():
    """The Laurel Ridge lesson: near-ties retire-and-create rather than
    pick a winner - the margin condition, not just the threshold."""
    prior = _seeded(_record(name="Laurel Ridge Campsite", poi_type="campsite"))
    twins = [
        _record(sfid="twin-a", name="Laurel Ridge Campsite", lat=41.0005, poi_type="campsite"),
        _record(sfid="twin-b", name="Laurel Ridge Campsite", lat=40.9995, poi_type="campsite"),
    ]

    outcome = reconcile(prior, twins, LATER)

    assert outcome.matched == []
    assert outcome.retired == ["atc_shelters:glob-1"]
    assert sorted(outcome.minted) == ["atc_shelters:twin-a", "atc_shelters:twin-b"]


def test_a_conflicting_fingerprint_blocks_a_plausible_match():
    """Upstream does not rebuild a shelter by accident: same name a few
    feet away, but the inventory says a different structure - the negative
    evidence outweighs everything positive here."""
    prior = _seeded({**_record(), "fingerprint": {"Year_Built": 1938, "Stories": 1}})
    impostor = {
        **_record(sfid="impostor", lat=41.0001),
        "fingerprint": {"Year_Built": 2019, "Stories": 2},
    }

    outcome = reconcile(prior, [impostor], LATER)

    assert outcome.matched == []
    assert outcome.retired == ["atc_shelters:glob-1"]


def test_an_id_never_crosses_poi_type_in_tier_2():
    prior = _seeded(_record(name="Reclassified Spot"))

    outcome = reconcile(prior, [_record(sfid="as-campsite", name="Reclassified Spot", poi_type="campsite")], LATER)

    assert outcome.matched == []
    assert outcome.retired == ["atc_shelters:glob-1"]


def test_the_along_trail_signal_carries_a_lateral_correction(monkeypatch):
    """A lateral centerline correction moves lat/lon while the place stays
    at the same trail mile - the signal that is robust to exactly that."""
    prior = _seeded(_record(name="Trailside Shelter"))
    # ~160 m away: name (2.0) alone misses the 2.5 threshold without either
    # the near-distance or the mile signal.
    nudged = _record(sfid="corrected", name="Trailside Shelter", lat=41.0015)

    def mile_of(points):
        return [1407.2 for _ in points]

    outcome = reconcile(prior, [nudged], LATER, mile_of=mile_of)

    assert len(outcome.matched) == 1
    assert "Δmile" in outcome.matched[0]


def test_a_not_same_override_forbids_the_pair():
    prior = _seeded({**_record(name="Rocky Run Shelter"), "fingerprint": {"Year_Built": 1938, "Stories": 1}})
    lookalike = {
        **_record(sfid="lookalike", name="Rocky Run Shelter", lat=41.0001),
        "fingerprint": {"Year_Built": 1938, "Stories": 1},
    }
    overrides = {
        "not_same": [
            {
                "id": "atc_shelters:glob-1",
                "source": "atc_shelters",
                "source_feature_id": "lookalike",
                "reason": "ATC keeps 1 and 2 apart; this is the other one",
            }
        ]
    }

    outcome = reconcile(prior, [lookalike], LATER, overrides=overrides)

    assert outcome.matched == []
    assert outcome.retired == ["atc_shelters:glob-1"]


def test_a_same_override_reunites_a_tombstone_with_its_successor():
    """Retirement is the recoverable mistake because of exactly this: one
    reviewed line re-anchors every photo and note the tombstone held."""
    prior = _seeded(_record(name="Come-Back Shelter"))
    prior = reconcile(prior, [], LATER).pois  # retired
    returned = _record(sfid="returned", name="Renamed Beyond Recognition", lat=41.002)
    overrides = {
        "same": [
            {
                "id": "atc_shelters:glob-1",
                "source": "atc_shelters",
                "source_feature_id": "returned",
                "reason": "rebuilt after the 2027 fire; ATC re-keyed and renamed it",
            }
        ]
    }

    outcome = reconcile(prior, [returned], "2028-09-12", overrides=overrides)

    assert len(outcome.matched) == 1
    row = outcome.pois["atc_shelters:glob-1"]
    assert "retired" not in row, "the override is the one door back in"
    assert row["source_feature_id"] == "returned"
    assert row["history"][-1]["by"] == "override"
    assert row["history"][-1]["was_retired"] == LATER
    assert outcome.minted == []


def test_a_stale_same_override_is_held_rather_than_silently_skipped():
    prior = _seeded(_record())
    overrides = {
        "same": [
            {
                "id": "atc_shelters:glob-1",
                "source": "atc_shelters",
                "source_feature_id": "no-such-key",
                "reason": "left over from last year's refresh",
            }
        ]
    }

    outcome = reconcile(prior, [_record()], LATER, overrides=overrides)

    assert len(outcome.held) == 1
    assert "stale" in outcome.held[0]


def test_summarize_names_every_evidence_match_with_its_evidence():
    prior = _seeded({**_record(name="Winturri Shelter"), "fingerprint": {"Year_Built": 1938, "Stories": 1}})
    successor = {
        **_record(sfid="rekeyed", name="Wintturi Shelter", lat=41.0001),
        "fingerprint": {"Year_Built": 1938, "Stories": 1},
    }
    outcome = reconcile(prior, [successor], LATER)

    text = summarize(outcome, seeded=False)

    assert "matched by evidence: 1" in text
    assert "'Winturri Shelter' -> 'Wintturi Shelter'" in text
    assert "fingerprint intact" in text


# --- main()'s two exit paths, which publish-vector-data.yml now depends on ---
#
# Everything above holds reconcile() itself. These hold the CLI wrapper, and
# they were added when #811 gave `regenerate_identity_ledger` a step in
# publish-vector-data.yml: that step pipes the write mode to `tee` under
# `set -o pipefail`, and uploads the ledger on `always()`. Both choices are
# bets on main()'s exit codes - that 2 means "wrote nothing, a human is
# needed" and 0 means "the file on disk is the reconciled one" - and until
# now nothing checked either. A wrapper that exited 0 after refusing to write
# would have turned the whole gate green while publishing an unreviewed
# ledger.


@pytest.fixture
def ledger_at(tmp_path, monkeypatch):
    """Point the module's paths at tmp_path and let a test set the snapshot.

    main() reads its file locations off module constants, so redirecting them
    is what lets the write path run without a corridor on disk - the same
    trick export_poi's CAPACITY_PATH tests use."""
    import reconcile_poi_identity as identity

    path = tmp_path / "poi_identity.json"
    monkeypatch.setattr(identity, "LEDGER_PATH", path)
    monkeypatch.setattr(identity, "OVERRIDES_PATH", tmp_path / "absent_overrides.json")
    monkeypatch.setattr(identity, "real_mile_of", lambda points: [None] * len(points))

    def snapshot(records):
        monkeypatch.setattr(identity, "published_records", lambda: list(records))

    return path, snapshot


def _seed_ledger_file(path, pois):
    path.write_text(render(pois), encoding="utf-8")


def test_the_write_mode_writes_the_ledger_and_exits_zero(ledger_at):
    from reconcile_poi_identity import main

    path, snapshot = ledger_at
    snapshot([_record()])

    assert main(["--release", RELEASE]) == 0
    assert json.loads(path.read_text())["pois"]["atc_shelters:glob-1"]["first_seen"] == RELEASE


def test_check_agrees_with_what_the_write_mode_just_wrote(ledger_at):
    """The gate and the generator must be the same function or the gate is
    unfollowable - which is exactly the state #811 found."""
    from reconcile_poi_identity import main

    path, snapshot = ledger_at
    snapshot([_record()])
    main(["--release", RELEASE])

    assert main(["--check", "--release", RELEASE]) == 0


def test_check_exits_one_when_the_snapshot_moved_on(ledger_at):
    from reconcile_poi_identity import main

    path, snapshot = ledger_at
    snapshot([_record()])
    main(["--release", RELEASE])
    snapshot([_record(), _record(sfid="glob-2", name="Second Shelter", lat=42.0)])

    assert main(["--check", "--release", LATER]) == 1


def test_a_held_item_exits_two_and_writes_nothing(ledger_at):
    """Exit 2 is what the workflow's `always()` upload exists for: no ledger
    is written, and the held list it printed is the only reason a human was
    called."""
    from reconcile_poi_identity import main

    path, snapshot = ledger_at
    seeded = reconcile({}, [_record()], RELEASE).pois
    retired = reconcile(seeded, [], LATER).pois  # the row goes to a tombstone
    _seed_ledger_file(path, retired)
    before = path.read_text()
    snapshot([_record()])  # ... and upstream re-presents its key

    assert main(["--release", LATER]) == 2
    assert path.read_text() == before, "a held run must not write the ledger it refused to reconcile"


def test_the_mass_retirement_refusal_exits_two_and_writes_nothing(ledger_at):
    from reconcile_poi_identity import main

    path, snapshot = ledger_at
    seeded = reconcile({}, [_record(sfid=f"old-{i}", name=f"Shelter {i}", lat=40.0 + i * 0.1) for i in range(30)], RELEASE).pois
    _seed_ledger_file(path, seeded)
    before = path.read_text()
    snapshot([_record(sfid=f"new-{i}", name=f"Different {i}", lat=44.0 + i * 0.1) for i in range(30)])

    assert main(["--release", LATER]) == 2
    assert path.read_text() == before
