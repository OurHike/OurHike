"""Tests for build_shelter_capacity.py - the ATC-shelter-to-capacity join
whose reviewed output is reference/shelter_capacity.json.

Two halves. Most of this is the usual synthetic fixtures (a five-row HTML
table written in test code, never the real page - see TESTING.md). The last
few read the checked-in reference file itself, which is not "the real data"
in the sense TESTING.md warns about: it is reviewed source in this
repository, the same way reference/gain_vectors.json is, and nothing else
would catch a hand-edit that put a capacity where its reason should be.
"""

import json

import pytest

import build_shelter_capacity as build

# One row per shape the join has to handle, in the source page's column order.
FIXTURE_ROWS = [
    ("Springer Mountain", "GA", "xxx"),
    ("Springer Mountain Shelter", "GA", "12"),
    ("Docs Knob Shelter", "VA", "8"),
    ("Rocky Run Shelters", "MD", "16"),
    ("Horns Pond Lean-tos", "ME", "8+8"),
]


def _page(rows=FIXTURE_ROWS, header=("Name", "State", "Mile (NOBO)", "Capacity")):
    """A stand-in for the source page: one table, same markup shape (a
    <strong> around each name, values otherwise bare)."""
    head = "".join(f"<th>{column}\n</th>" for column in header)
    body = ""
    for name, state, capacity in rows:
        body += f"<tr><td><strong>{name}</strong></td><td>{state}</td><td>0.0</td><td>{capacity}</td></tr>"
    return f"<html><body><table><tbody><tr>{head}</tr>{body}</tbody></table></body></html>"


def _shelters(*names):
    return [{"global_id": f"glob-{i}", "name": name} for i, name in enumerate(names)]


def _by_name(records):
    return {record["atc_name"]: record for record in records}


@pytest.mark.parametrize(
    ("atc", "listed"),
    [
        # The generic structure words each list attaches differently.
        ("Chairback Gap Lean-to Shelter", "Chairback Gap Lean-to"),
        ("Ethan Pond Campsite Shelter", "Ethan Pond Campsite"),
        # ATC abbreviates; the source spells out.
        ("Tray Mtn Shelter", "Tray Mountain Shelter"),
        ("Brink Rd Shelter", "Brink Road Shelter"),
        # Punctuation only.
        ("Doc's Knob Shelter", "Docs Knob Shelter"),
    ],
)
def test_normalise_brings_the_two_lists_names_together(atc, listed):
    assert build.normalise(atc) == build.normalise(listed)


def test_normalise_keeps_genuinely_different_shelters_apart():
    """The words it strips are the ones that say what a structure is. What
    identifies *which* one must survive, or two shelters merge into one."""
    assert build.normalise("Mt. Wilcox North Shelter") != build.normalise("Mt. Wilcox South Shelter 1")
    assert build.normalise("Rocky Run Shelter 1") != build.normalise("Rocky Run Shelter 2")
    assert build.normalise("Cold Spring Shelter") != build.normalise("Rock Spring Hut")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8", 8),
        ("16", 16),
        ("90", 90),
        # Shelter-and-campsite: the shelter figure is the shelter's capacity,
        # the tent sites beside it are not.
        ("16s/4c", 16),
        ("12s/7c", 12),
        # Two structures, same number: 8 each however the row is read.
        ("8+8", 8),
    ],
)
def test_parse_capacity_reads_the_numeric_forms(raw, expected):
    capacity, reason = build.parse_capacity(raw)
    assert capacity == expected
    assert reason is None


@pytest.mark.parametrize("raw", ["xxx", "???", "A lot", "6 ?", "", "2+5", "6o/8n", "9+8", "0"])
def test_parse_capacity_refuses_rather_than_guesses(raw):
    """Every unreadable form comes back blank *with a stated reason*. The
    reason is the point: it is what makes a blank in the output file a
    decision somebody can review instead of a gap.

    "6 ?" and "2+5" are the two worth naming. Both contain a number a
    looser parser would happily take - and taking either would put a figure
    on a card that the source itself hedged or split."""
    capacity, reason = build.parse_capacity(raw)
    assert capacity is None
    assert reason
    assert raw.strip() in reason or "not a number" in reason


def test_parse_rows_reads_the_columns_it_needs():
    rows = build.parse_rows(_page())
    assert [row["name"] for row in rows] == [name for name, _, _ in FIXTURE_ROWS]
    assert rows[2] == {"name": "Docs Knob Shelter", "state": "VA", "capacity": "8"}


def test_parse_rows_stops_when_the_page_has_no_table():
    with pytest.raises(ValueError, match="No table found"):
        build.parse_rows("<html><body><p>Sorry, this page has moved.</p></body></html>")


def test_parse_rows_stops_when_a_column_it_reads_by_name_is_gone():
    """This is scraped HTML: the columns can be renamed or reordered upstream
    with nothing to announce it. Failing here beats writing a file of
    elevations labelled as capacities."""
    with pytest.raises(ValueError, match="Capacity"):
        build.parse_rows(_page(header=("Name", "State", "Mile (NOBO)", "Sleeps")))


def test_resolve_matches_by_name_and_through_the_alias_table():
    records = _by_name(build.resolve(_shelters("Springer Mtn Shelter", "Doc's Knob Shelter"), build.parse_rows(_page())))

    # Matched on the normalised name alone, past a same-named summit row.
    assert records["Springer Mtn Shelter"]["capacity"] == 12
    assert records["Springer Mtn Shelter"]["listed_as"] == "Springer Mountain Shelter"
    # And where the apostrophe is the whole difference.
    assert records["Doc's Knob Shelter"]["capacity"] == 8


def test_resolve_prefers_the_structure_over_the_landmark_it_sits_below():
    """ "Springer Mountain" (a summit, capacity "xxx") and "Springer Mountain
    Shelter" normalise identically. Taking the summit row would blank a
    shelter whose capacity the source actually states."""
    records = _by_name(build.resolve(_shelters("Springer Mtn Shelter"), build.parse_rows(_page())))
    assert records["Springer Mtn Shelter"]["listed_capacity"] == "12"


def test_resolve_splits_a_pair_only_when_both_halves_agree():
    """ "8+8" over two lean-tos is 8 each on any reading, so it splits. "16"
    over two shelters might be each or the pair, so it does not - and says
    so, rather than falling through as though the row were missing."""
    records = _by_name(
        build.resolve(
            _shelters(
                "Horns Pond Lean-to Shelter 1",
                "Horns Pond Lean-to Shelter 2",
                "Rocky Run Shelter 1",
                "Rocky Run Shelter 2",
            ),
            build.parse_rows(_page()),
        )
    )

    assert records["Horns Pond Lean-to Shelter 1"]["capacity"] == 8
    assert records["Horns Pond Lean-to Shelter 2"]["capacity"] == 8

    for name in ("Rocky Run Shelter 1", "Rocky Run Shelter 2"):
        assert records[name]["capacity"] is None
        assert records[name]["listed_as"] == "Rocky Run Shelters"
        assert "more than one shelter" in records[name]["unresolved"]


def test_resolve_lists_every_atc_shelter_including_the_ones_with_no_row():
    """The file is a complete statement about the layer, not a highlight
    reel. A shelter that loses its match on a later run has to show up in the
    diff as a changed line - which only works if it was there to change."""
    records = _by_name(build.resolve(_shelters("Springer Mtn Shelter", "Whiskey Hollow Shelter"), build.parse_rows(_page())))

    assert set(records) == {"Springer Mtn Shelter", "Whiskey Hollow Shelter"}
    assert records["Whiskey Hollow Shelter"] == {
        "poi_id": "atc_shelters:glob-1",
        "atc_name": "Whiskey Hollow Shelter",
        "capacity": None,
        "listed_as": None,
        "listed_capacity": None,
        "unresolved": build.NO_ROW,
    }


def test_build_reports_what_it_resolved():
    document = build.build(_page(), _shelters("Springer Mtn Shelter", "Whiskey Hollow Shelter"))
    assert document["counts"] == {"shelters": 2, "with_capacity": 1}
    assert document["source"]["url"] == build.GREENBELLY_URL
    # The licence position travels with the data rather than only in a doc -
    # CONTRIBUTING.md's "establish its licence first and record it".
    assert document["source"]["licence"]
    assert document["source"]["credits"]


# --- the checked-in file itself ---


@pytest.fixture(scope="module")
def reference():
    return json.loads(build.OUT_PATH.read_text(encoding="utf-8"))


def test_reference_file_states_a_reason_for_every_blank(reference):
    """The invariant the whole file rests on: a capacity is either a number
    or a stated refusal. A blank with no reason is a hole somebody would
    later fill by guessing."""
    for record in reference["shelters"]:
        if record["capacity"] is None:
            assert record.get("unresolved"), f"{record['atc_name']} is blank with no reason"
        else:
            assert "unresolved" not in record, f"{record['atc_name']} has both a capacity and a reason"
            assert isinstance(record["capacity"], int) and record["capacity"] > 0


def test_reference_file_has_one_record_per_shelter_and_no_repeated_ids(reference):
    # poi_id since #671: the ledger id export_poi.py publishes, not the
    # bare GlobalID whose stability nobody audited.
    ids = [record["poi_id"] for record in reference["shelters"]]
    assert len(set(ids)) == len(ids)
    assert reference["counts"]["shelters"] == len(ids)
    assert reference["counts"]["with_capacity"] == sum(1 for r in reference["shelters"] if r["capacity"] is not None)


def test_reference_file_still_covers_most_of_the_layer(reference):
    """A coverage floor, not a target. The join is by name against a list
    somebody else maintains, so the way it breaks is quietly: a renamed
    column, a restructured page, and the next run resolves forty shelters
    instead of two hundred and sixty. 80% is far below the 93% it stands at
    and far above what a broken join would produce."""
    counts = reference["counts"]
    assert counts["with_capacity"] / counts["shelters"] > 0.8
