"""export_suggested_hikes.py - the graded routes as the artifact the shelf
reads (#1427).

The synthetic graph from test_lib_trail_graph_route.py, a cache in the shape
fetch_hikefinder.py writes, and a routes file in the shape route_hikefinder.py
writes, all in a temp directory - never the real network, cache or graph
(TESTING.md).

What is pinned is the gate and the contract: nothing ships from an entry that
does not reach hikers, nothing ships from a route graded `rejected`, a
surveyed track that this build's lines cannot re-walk is dropped rather than
re-drawn, and what does ship is spelled the way lib/suggestedHikesData.ts
reads it - ends as snapped coordinates, a loop closed by repeating its first
end, and the publisher's own tags carried through.
"""

from __future__ import annotations

import json

import pytest

import export_suggested_hikes as exporter
from lib.hikefinder import SOURCE_KEY
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files

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

    def write(hikes: dict, routes: dict):
        monkeypatch.setattr(exporter, "load_cache", lambda *a, **k: hikes)
        (processed / "hikefinder_routes.json").write_text(json.dumps({"routes": routes}))

    return {"processed": processed, "write": write, "registry": registry, "out": processed / "suggested_hikes.json"}


def published(sandbox) -> list[dict]:
    return json.loads(sandbox["out"].read_text())["hikes"]


# --- the gates -----------------------------------------------------------------


def test_an_entry_that_does_not_reach_hikers_publishes_nothing(sandbox, capsys):
    sandbox["registry"](reaches=False)
    sandbox["write"]({"7": hike()}, {"7": route()})
    assert exporter.main() is None
    assert not sandbox["out"].exists()


def test_a_rejected_route_ships_nothing_and_is_named_in_the_manifest(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route(grade="rejected", ends=[], problems=["too far apart"])})
    manifest = exporter.main()
    assert published(sandbox) == []
    assert manifest["dropped"] == ["7"]


def test_a_hike_with_no_row_in_the_routes_file_is_dropped_rather_than_guessed(sandbox):
    sandbox["write"]({"7": hike()}, {})
    manifest = exporter.main()
    assert published(sandbox) == []
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
    assert record["detail"]["routeProvenance"] == "generated"
    assert record["detail"]["routeGrade"] == "strong"


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
    assert published(sandbox)[0]["detail"]["features"] == ["Views", "Waterfall"]


def test_everything_the_export_said_is_carried_onto_the_detail(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route()})
    exporter.main()
    detail = published(sandbox)[0]["detail"]
    assert detail["park"] == "Harriman State Park"
    assert detail["routeType"] == "Circuit"
    assert detail["dogs"] == "Allowed on leash"
    assert detail["author"] == "Daniel Chazin"
    assert detail["directions"] == ["Park at the gate."]
    assert detail["publishedMiles"] == 0.3


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
    assert record["detail"]["publishedDifficulty"] == "Very Strenuous"


def test_a_difficulty_the_client_has_no_slot_for_is_absent_rather_than_guessed(sandbox):
    sandbox["write"]({"7": hike(difficulty="Brutal")}, {"7": route()})
    exporter.main()
    assert published(sandbox)[0]["difficulty"] is None


# --- a surveyed track has to survive the round trip ----------------------------


def test_a_track_that_re_walks_on_this_builds_lines_ships_with_its_drift_recorded(sandbox):
    """The claim being made is "the phone walking these ends walks the
    surveyed route", and it is only made after measuring it."""
    ends = [[LON, LAT], [LON + STEP, LAT], [LON + 2 * STEP, LAT], [LON + 3 * STEP, LAT]]
    miles = exporter.router.metres_to_miles(exporter.router.metres_between((LON, LAT), (LON + 3 * STEP, LAT)))
    sandbox["write"](
        {"7": hike(has_published_route=True, route_type="Shuttle")},
        {"7": route(provenance="published", ends=ends, closed=False, miles=miles, stated_miles=miles)},
    )
    manifest = exporter.main()
    record = published(sandbox)[0]
    assert record["detail"]["routeProvenance"] == "published"
    assert "trackReproduction" in record["detail"]
    assert manifest["by_provenance"] == {"published": 1}


def test_a_track_that_leaves_this_builds_lines_is_dropped_rather_than_re_drawn(sandbox):
    """49 of the export's 113 tracks do this. Snapping them onto whatever
    happens to be nearest would publish a line the surveyor never walked."""
    ends = [[LON + 1.0, LAT + 1.0], [LON + 1.01, LAT + 1.0]]
    sandbox["write"](
        {"7": hike(has_published_route=True, route_type="Shuttle")},
        {"7": route(provenance="published", ends=ends, closed=False, miles=0.6, stated_miles=0.6)},
    )
    manifest = exporter.main()
    assert published(sandbox) == []
    assert manifest["dropped"] == ["7"]


# --- the manifest --------------------------------------------------------------


def test_the_manifest_counts_the_two_provenances_apart(sandbox):
    sandbox["write"]({"7": hike()}, {"7": route()})
    manifest = exporter.main()
    assert manifest["count"] == 1
    assert manifest["by_provenance"] == {"generated": 1}
    assert manifest["with_tags"] == 1
