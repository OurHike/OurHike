"""export_suggested_hikes.py - the graded routes as the artifact the shelf
reads (#1427).

The synthetic graph from test_lib_trail_graph_route.py, a cache in the shape
fetch_hikefinder.py writes, and a routes file in the shape route_hikefinder.py
writes, all in a temp directory - never the real network, cache or graph
(TESTING.md).

What is pinned is the gate and the contract: nothing ships from an entry that
does not reach hikers, nothing ships from a route graded `rejected`, a
published line that this build's lines cannot re-walk is dropped rather than
re-drawn, and what does ship is spelled the way lib/suggestedHikesData.ts
reads it - ends as snapped coordinates, a loop closed by repeating its first
end, and the publisher's own tags carried through.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

import export_suggested_hikes as exporter
from lib.hikefinder import SOURCE_KEY
from lib.r2_keys import assert_valid_keys
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files

ROOT = pathlib.Path(__file__).resolve().parent.parent
STEWARD = "New York-New Jersey Trail Conference"


def hike(**overrides) -> dict:
    base = {
        "id": 7,
        "name": "Pine Meadow Loop",
        "source_url": "https://example.test/hikefinder/hike.php?id=7",
        "summary": "A short loop.",
        "stated_miles": 0.3,
        "difficulty": "Easy To Moderate",
        "estimated_hours": 1.0,
        "route_type": "Circuit",
        "dogs": "Allowed on leash",
        "park": "Harriman State Park",
        "region": "Lower Hudson",
        "author": "Daniel Chazin",
        "features": ["Views", "Waterfall"],
        "published_on": "July 11, 2013",
        "updated_on": None,
        "directions": ["Park at the gate."],
        "description": ["Follow the Pine Meadow Trail."],
        "public_transport": [],
        "has_published_route": False,
        "start": {"lat": LAT, "lon": LON, "label": "Parking location"},
    }
    base.update(overrides)
    return base


def route(**overrides) -> dict:
    base = {
        "hike_id": 7,
        "provenance": "generated",
        "grade": "strong",
        "ends": [[LON, LAT], [LON + 2 * STEP, LAT]],
        "closed": True,
        "miles": 0.3,
        "stated_miles": 0.3,
        "problems": [],
        "climb": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    graph_files(processed)
    sources = tmp_path / "sources.json"

    def registry(reaches: bool = True):
        sources.write_text(
            json.dumps(
                {"sources": [{"key": SOURCE_KEY, "kind": "published_hikes", "steward": STEWARD, "reaches_hikers": reaches}]}
            )
        )

    registry()
    monkeypatch.setattr(exporter, "SOURCES_PATH", sources)
    monkeypatch.setattr(exporter, "PROCESSED_DIR", processed)
    monkeypatch.setattr(exporter, "OUT_PATH", processed / "suggested_hikes.json")
    monkeypatch.setattr(exporter, "MANIFEST_PATH", processed / "suggested_hikes_manifest.json")
    monkeypatch.setattr(exporter, "ROUTES_PATH", processed / "hikefinder_routes.json")
    monkeypatch.setattr(exporter, "DETAIL_DIR", processed / "suggested_hikes_detail")
    monkeypatch.setattr(exporter, "DETAIL_MANIFEST_PATH", processed / "suggested_hikes_detail_manifest.json")

    def write(hikes: dict, routes: dict):
        monkeypatch.setattr(exporter, "load_cache", lambda *a, **k: hikes)
        (processed / "hikefinder_routes.json").write_text(json.dumps({"routes": routes}))

    return {"processed": processed, "write": write, "registry": registry, "out": processed / "suggested_hikes.json"}


def published(sandbox) -> list[dict]:
    return json.loads(sandbox["out"].read_text())["hikes"]


def detail_of(record: dict) -> dict:
    """The detail object published beside one shelf record (#1473).

    Keyed on the number off the record's own id, which is what the client
    builds its URL from - so reading it this way exercises the same lookup a
    phone does rather than trusting the filename.
    """
    number = record["id"].split(":", 1)[-1]
    return json.loads((exporter.DETAIL_DIR / f"{number}.json").read_text())


# --- the gates -----------------------------------------------------------------


def test_an_entry_that_does_not_reach_hikers_publishes_nothing(sandbox, capsys):
    sandbox["registry"](reaches=False)
    sandbox["write"]({"7": hike()}, {"7": route()})
    assert exporter.main() is None
    assert not sandbox["out"].exists()


def test_a_rejected_route_ships_nothing_and_is_named_in_the_manifest(sandbox):
    """Paired with a hike that DOES ship, because a run where nothing passes
    now writes no artifact at all - see
    test_a_run_where_nothing_passes_writes_no_artifact_at_all."""
    sandbox["write"](
        {"7": hike(), "8": hike(id=8, name="Ridge Walk")},
        {"7": route(grade="rejected", ends=[], problems=["too far apart"]), "8": route(hike_id=8)},
    )
    manifest = exporter.main()
    assert [record["id"] for record in published(sandbox)] == [f"{SOURCE_KEY}:8"]
    assert manifest["dropped"] == ["7"]


def test_a_hike_with_no_row_in_the_routes_file_is_dropped_rather_than_guessed(sandbox):
    sandbox["write"]({"7": hike(), "8": hike(id=8, name="Ridge Walk")}, {"8": route(hike_id=8)})
    manifest = exporter.main()
    assert [record["id"] for record in published(sandbox)] == [f"{SOURCE_KEY}:8"]
    assert manifest["dropped"] == ["7"]


# --- what a shipped record says ------------------------------------------------


def test_a_generated_route_ships_its_ends_and_says_it_was_generated(sandbox):
    """The distinction the maintainer asked for, on the record a phone holds:
    a screen that prints an inference in the voice of a survey is the failure
    this field exists to prevent."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    assert record["id"] == f"{SOURCE_KEY}:7"
    assert record["routeProvenance"] == "generated"
    assert record["routeGrade"] == "strong"


def test_a_closed_walk_repeats_its_first_end_so_the_phone_closes_it(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route(closed=True)})
    exporter.main()
    ends = published(sandbox)[0]["segments"][0]
    assert ends[0]["coord"] == ends[-1]["coord"]


def test_an_open_walk_does_not(sandbox):
    sandbox["write"]({"7": hike(route_type="Shuttle")}, {"7": route(closed=False)})
    exporter.main()
    ends = published(sandbox)[0]["segments"][0]
    assert ends[0]["coord"] != ends[-1]["coord"]


def test_the_publishers_tags_ride_through_to_the_record(sandbox):
    """ "Especially the tags" - they are the facets the finder filters on."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    assert published(sandbox)[0]["features"] == ["Views", "Waterfall"]


def test_everything_the_export_said_is_carried_across_the_two_objects(sandbox):
    """#1473 split the record; it did not drop anything out of it. What the
    export said still all ships - the finder's facts on the shelf, the prose
    in the hike's own object - and this walks both sides to prove it."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    detail = detail_of(record)

    # On the shelf, because a finder filters what it already holds.
    assert record["park"] == "Harriman State Park"
    assert record["routeType"] == "Circuit"
    assert record["dogs"] == "Allowed on leash"

    # In the hike's own object, because only its screen reads them.
    assert detail["directions"] == ["Park at the gate."]
    assert detail["publishedMiles"] == 0.3
    assert detail["overview"] == ["A short loop."]


def test_the_two_authors_are_kept_apart(sandbox):
    """A collision flattening the record exposed. `author` at the top level is
    the client's own field and means the PUBLISHING ORGANIZATION - it is what
    the card's "by" line names, and features/SUGGESTED_HIKES.md makes naming
    that organization the premise of showing a route at all. The person who
    wrote this particular hike up is a different fact, and it goes where the
    client reads it: `publication.submittedBy`."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    assert record["author"] == {"kind": "club", "name": STEWARD}
    assert detail_of(record)["publication"]["submittedBy"] == "Daniel Chazin"


def test_a_hike_naming_no_author_ships_no_publication_block(sandbox):
    """validPublication refuses a block with no submittedBy, so an empty one
    would be a field the client drops anyway - and a card printing "written by"
    with nobody after it is worse than one printing nothing."""
    sandbox["write"]({"7": hike(author=None)}, {"7": route()})
    exporter.main()
    assert "publication" not in published(sandbox)[0]


# --- difficulty is quoted, and one level does not fit --------------------------


def test_the_publishers_difficulty_becomes_the_slug_the_client_holds(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    assert published(sandbox)[0]["difficulty"] == "easy-moderate"


def test_very_strenuous_takes_the_hardest_slug_there_is_and_keeps_its_own_word(sandbox):
    """The client holds five levels and the export publishes six. Mapping it
    down UNDERSTATES the hike, which is the unsafe direction, so the
    publisher's own label rides along and the card can print it."""
    sandbox["write"]({"7": hike(difficulty="Very Strenuous")}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    assert record["difficulty"] == "strenuous"
    assert record["publishedDifficulty"] == "Very Strenuous"


def test_a_difficulty_the_client_has_no_slot_for_is_absent_rather_than_guessed(sandbox):
    sandbox["write"]({"7": hike(difficulty="Brutal")}, {"7": route()})
    exporter.main()
    assert published(sandbox)[0]["difficulty"] is None


# --- a published line has to survive the round trip ----------------------------


def test_a_track_that_re_walks_on_this_builds_lines_ships_with_its_drift_recorded(sandbox):
    """The claim being made is "the phone walking these ends walks the line the
    publisher drew", and it is only made after measuring it."""
    ends = [[LON, LAT], [LON + STEP, LAT], [LON + 2 * STEP, LAT], [LON + 3 * STEP, LAT]]
    miles = exporter.router.metres_to_miles(exporter.router.metres_between((LON, LAT), (LON + 3 * STEP, LAT)))
    sandbox["write"](
        {"7": hike(has_published_route=True, route_type="Shuttle")},
        {"7": route(provenance="published", ends=ends, closed=False, miles=miles, stated_miles=miles)},
    )
    manifest = exporter.main()
    record = published(sandbox)[0]
    assert record["routeProvenance"] == "published", "provenance rides the SHELF, beside the line it describes"
    assert "trackReproduction" in detail_of(record)
    assert manifest["by_provenance"] == {"published": 1}


def test_a_track_that_leaves_this_builds_lines_is_dropped_rather_than_re_drawn(sandbox):
    """49 of the export's 113 tracks do this. Snapping them onto whatever
    happens to be nearest would publish a line the surveyor never walked."""
    ends = [[LON + 1.0, LAT + 1.0], [LON + 1.01, LAT + 1.0]]
    sandbox["write"](
        {"7": hike(has_published_route=True, route_type="Shuttle"), "8": hike(id=8, name="Ridge Walk")},
        {
            "7": route(provenance="published", ends=ends, closed=False, miles=0.6, stated_miles=0.6),
            "8": route(hike_id=8),
        },
    )
    manifest = exporter.main()
    assert [record["id"] for record in published(sandbox)] == [f"{SOURCE_KEY}:8"]
    assert manifest["dropped"] == ["7"]


# --- the manifest --------------------------------------------------------------


def test_the_manifest_counts_the_two_provenances_apart(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route()})
    manifest = exporter.main()
    assert manifest["count"] == 1
    assert manifest["by_provenance"] == {"generated": 1}
    assert manifest["with_tags"] == 1


# --- the wire shape, guarded across the two suites -----------------------------

CLIENT_VALIDATOR = ROOT.parent / "client" / "src" / "lib" / "suggestedHikesData.ts"


def _fields_the_client_reads() -> set[str]:
    """Every `raw.<name>` inside the client's `validDetail`, read from the
    client's own source rather than copied here.

    Copying the list would be a second place for it to be wrong, which is the
    whole defect this guards against.
    """
    source = CLIENT_VALIDATOR.read_text(encoding="utf-8")
    body = source[source.index("function validDetail(") :]
    body = body[: body.index("\n}\n")]
    return set(re.findall(r"raw\.(\w+)", body))


def test_the_record_is_flat_because_the_client_reads_it_flat(sandbox):
    """THE BUG THIS EXISTS FOR, and it shipped green.

    `validDetail` is handed the WHOLE record and reads `raw.url`,
    `raw.publishedMiles`, `raw.description` off the top level - its own test
    pins it as "reads nothing out of a nested `detail`, which is not the wire
    shape". An earlier version of the exporter nested them under a `detail`
    key, which dropped every one on the phone while BOTH suites stayed green:
    this one asserted the nested shape, the client's asserted the flat one,
    and they never met.

    So this test reads the client's own validator and checks the exporter
    against it. It fails if either side moves without the other.

    #1473 SPLIT THE RECORD AND THIS GOT STRONGER RATHER THAN WEAKER. The
    fields are still flat - `validDetail` is handed a whole object either way
    - but they now live across two of them, so what has to hold is that the
    UNION covers what the client reads. A field that fell out of the shelf and
    never landed in the detail would be exactly the original bug wearing a new
    coat.
    """
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    detail = detail_of(record)

    for obj, where in ((record, "shelf record"), (detail, "detail object")):
        assert "detail" not in obj, f"the fields are flat on the wire - validDetail reads the whole {where}"

    wanted = _fields_the_client_reads()
    carried = set(record) | set(detail)
    missing = wanted - carried
    # `hikerNote` is deliberately never written: its contract is that a person
    # reviewed the route, and nobody has reviewed these.
    assert missing <= {"hikerNote"}, f"the client reads {sorted(missing)} and neither object carries them"


def test_the_shelf_and_the_detail_share_no_field(sandbox):
    """What lib/useHikeDetail.ts's merge rests on (#1473).

    It spreads the fetched detail OVER the shelf's own fields, which is only
    safe while the two carry nothing in common - the moment they overlap,
    spread order silently becomes a precedence decision nobody made, and the
    field it would quietly win is `routeProvenance`: the one that says whether
    a hiker is looking at a line somebody drew or a line this pipeline
    inferred.

    Disjoint by construction today, since the detail is built by excluding
    SHELF_FIELDS. This is the guard for the day somebody adds a field to both
    lists by hand.
    """
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    detail = detail_of(record)

    shared = (set(record) & set(detail)) - {"id"}
    assert shared == set(), f"{sorted(shared)} is on both objects - useHikeDetail's merge would pick a winner silently"
    assert detail["id"] == record["id"], "a detail fetched on its own has to say which hike it is"


def test_every_detail_key_is_one_the_bucket_will_accept(sandbox):
    """The check that would have caught this split breaking the whole publish.

    publish.py calls `assert_valid_keys` over every artifact BEFORE it opens a
    connection, and that call RAISES - so one illegal name among the details
    does not skip those objects, it aborts the vector-data publish entirely
    and the bucket goes on serving the release before it. The first version of
    #1473 keyed these `suggested_hikes_detail/<n>.json`, which is a top-level
    prefix nobody declared in lib/r2_keys.py, and CI was green on it: no suite
    ran a real key through the validator.

    This runs the manifest publish.py actually reads, rather than a key built
    by hand here, so a template changed in one place and not the other fails
    here instead of in the bucket.
    """
    sandbox["write"](
        {"7": hike(), "1234": hike(id=1234, name="Another Walk")},
        {"7": route(), "1234": route(hike_id=1234)},
    )
    exporter.main()

    keys = list(json.loads(exporter.DETAIL_MANIFEST_PATH.read_text())["artifacts"])
    assert keys, "the manifest is what publish.py uploads from; an empty one publishes no prose at all"
    assert_valid_keys(keys)


def test_a_stale_detail_from_an_earlier_run_is_not_left_behind(sandbox):
    """A hike dropped or renumbered between runs leaves prose in the bucket
    that no shelf record points at. Harmless to a phone, which never asks for
    it - and exactly the kind of debris that makes a later reader mistrust the
    whole family."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    orphan = exporter.DETAIL_DIR / "999.json"
    orphan.write_text('{"id": "gone:999"}')

    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    assert not orphan.exists(), "the detail directory is rebuilt, not added to"
    assert sorted(path.name for path in exporter.DETAIL_DIR.glob("*.json")) == ["7.json"]


def test_an_id_this_scheme_cannot_name_costs_the_run_and_not_the_last_good_one(sandbox):
    """A bad id raises BEFORE anything is deleted, and takes the manifest with
    it rather than leaving one that names files this run just removed.

    Two ways to get this wrong and one of them is worse than the failure it
    is reporting: a manifest naming deleted paths is read by publish.py on
    the NEXT run and aborts the whole vector-data upload, where a missing
    manifest is read as "this run published no prose" and costs the release
    its prose alone.
    """
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    kept = sorted(path.name for path in exporter.DETAIL_DIR.glob("*.json"))
    assert kept == ["7.json"]

    with pytest.raises(ValueError, match="detailKeyFor"):
        exporter.write_details([{"id": "nynjtc_favorite_hikes:hike-vista-loop-trail"}])
    # And the other half of the same gate: a bare number is an id the client
    # answers null for, so writing its detail would publish prose nothing can
    # ask for.
    with pytest.raises(ValueError, match="detailKeyFor"):
        exporter.write_details([{"id": "50"}])

    assert sorted(path.name for path in exporter.DETAIL_DIR.glob("*.json")) == kept, (
        "the check runs before the delete, so a bad id leaves the last good run intact"
    )
    assert exporter.DETAIL_MANIFEST_PATH.exists(), "nothing was deleted, so the manifest still describes what is there"


def test_a_manifest_never_outlives_the_files_it_names(sandbox):
    """The manifest goes first, so a crash between the delete and the rewrite
    leaves publish.py with no manifest rather than one pointing at nothing."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    named = json.loads(exporter.DETAIL_MANIFEST_PATH.read_text())["artifacts"]
    assert all(pathlib.Path(entry["path"]).exists() for entry in named.values())

    # Every id checks out, so this run reaches the delete - and dies there,
    # the way a killed CI job would.
    def die(*_args, **_kwargs):
        raise KeyboardInterrupt

    original = exporter.sha256_file
    exporter.sha256_file = die
    try:
        with pytest.raises(KeyboardInterrupt):
            exporter.write_details([{"id": f"{SOURCE_KEY}:7"}])
    finally:
        exporter.sha256_file = original

    assert not exporter.DETAIL_MANIFEST_PATH.exists(), (
        "publish.py reads a missing manifest as 'no prose this run'; one naming deleted paths aborts the publish"
    )


def test_the_provenance_fields_are_spelled_the_way_the_client_reads_them(sandbox):
    """The point of #1427 reaching a phone at all. These three were added to
    `validDetail` in the same pull request; if either side is renamed, an
    inferred line arrives indistinguishable from a published one."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    record = published(sandbox)[0]
    assert _fields_the_client_reads() >= {"routeProvenance", "routeGrade", "routeNotes"}
    assert record["routeProvenance"] == "generated"
    assert record["routeGrade"] == "strong"


def test_no_hiker_note_is_written_because_nobody_reviewed_these(sandbox):
    """`hikerNote` says what a PERSON checked. The machine's account of itself
    is `routeProvenance`, and the two must not be confused."""
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    assert "hikerNote" not in published(sandbox)[0]


def test_climb_ships_when_the_route_was_priced_and_is_absent_when_it_was_not(sandbox):
    """Absent means never measured, which the client reads as unknown. Never 0:
    a walk with one unpriced edge reported as flat fails SHORT, and short is
    the direction that gets somebody caught by the dark."""
    sandbox["write"]({"7": hike()}, {"7": route(climb=[420, 380])})
    exporter.main()
    assert published(sandbox)[0]["climb"] == {"gainFt": 420, "lossFt": 380}

    sandbox["write"]({"7": hike()}, {"7": route(climb=None)})
    exporter.main()
    assert "climb" not in published(sandbox)[0]


def test_a_run_where_nothing_passes_writes_no_artifact_at_all(sandbox):
    """ "Nothing passed grading" and "there are no suggested hikes" are
    different claims. Writing an empty document makes the client read the
    second, and publish.py uploads whatever manifest exists with no count of
    its own - so refusing here is the only thing standing between a bad run
    and every phone's Today shelf emptying."""
    sandbox["write"]({"7": hike()}, {"7": route(grade="rejected", ends=[], problems=["too far apart"])})
    assert exporter.main() is None
    assert not sandbox["out"].exists()


def test_a_published_hikes_climb_is_priced_from_this_builds_graph(sandbox):
    """#1451. The track's own `<ele>` values are not used; the figure comes
    from the re-walk that `track_ends` already performs to prove the phone can
    reproduce the line, which prices climb from this build's sidecar exactly as
    a generated route's does. One source for one number."""
    ends = [[LON, LAT], [LON + STEP, LAT], [LON + 2 * STEP, LAT], [LON + 3 * STEP, LAT]]
    miles = exporter.router.metres_to_miles(exporter.router.metres_between((LON, LAT), (LON + 3 * STEP, LAT)))
    sandbox["write"](
        {"7": hike(has_published_route=True, route_type="Shuttle")},
        {"7": route(provenance="published", ends=ends, closed=False, miles=miles, stated_miles=miles, climb=None)},
    )
    exporter.main()
    record = published(sandbox)[0]
    # The synthetic graph carries an elevation sidecar that fits it, so the
    # re-walk prices the climb even though the routes artifact carried none.
    assert record["climb"]["gainFt"] > 0


def test_a_missing_fetch_or_route_pass_publishes_nothing_rather_than_failing(sandbox, monkeypatch, capsys):
    """#1462. The exporter is the second of the two scripts that used to treat
    a skipped hike fetch as fatal, and between them they threw away a whole
    A.T. publish (run 114 of publish-vector-data.yml) because one website
    timed out. Both now return "nothing to publish", which is what the
    workflow's `continue-on-error` on that fetch always meant."""
    monkeypatch.setattr(exporter, "load_cache", lambda *a, **k: {})
    assert exporter.main() is None
    assert "No fetch cache" in capsys.readouterr().err

    monkeypatch.setattr(exporter, "load_cache", lambda *a, **k: {"7": {"id": 7}})
    assert not exporter.ROUTES_PATH.exists()
    assert exporter.main() is None
    assert "No routes artifact" in capsys.readouterr().err


def test_a_routes_artifact_that_will_not_parse_still_fails_loudly(sandbox):
    """The other half, and the reason the one above is safe: absence is a fact
    about this run, corruption is a defect, and softening both together would
    turn a loud failure into a silent one."""
    exporter.ROUTES_PATH.write_text("{ not json at all")
    with pytest.raises(SystemExit, match="unreadable"):
        exporter.load_routes()
