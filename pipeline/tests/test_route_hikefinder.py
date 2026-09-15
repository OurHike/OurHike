"""route_hikefinder.py - which road each hike's route came by, and the sheet a
person reads (#1427).

The synthetic graph from test_lib_trail_graph_route.py and a cache in the
shape fetch_hikefinder.py writes, in a temp directory - never the real cache
or graph (TESTING.md).

What is pinned is the split this script exists to keep: a hike with a cached
GPX is read from that track and never re-routed over the graph, a hike without
one is formed and graded, and both end up in one artifact that says which is
which. Plus the thing a sheet has to do to be worth rendering - show the
refusals, not only the successes.
"""

from __future__ import annotations

import json

import pytest

import route_hikefinder as script
from lib.hikefinder import Track
from tests.test_lib_hikefinder import GPX
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files


def hike(**overrides) -> dict:
    base = {
        "id": 7,
        "name": "Pine Meadow Loop",
        "source_url": "https://example.test/hikefinder/hike.php?id=7",
        "route_type": "Circuit",
        "stated_miles": 0.3,
        "difficulty": "Moderate",
        "park": "Harriman State Park",
        "region": "Lower Hudson",
        "features": ["Views"],
        "description": ["Follow the Pine Meadow Trail east, then the Ridge Loop."],
        "start": {"lat": LAT, "lon": LON, "label": "Parking location"},
        "has_published_route": False,
        "gpx_file": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    processed.mkdir()
    graph_files(processed)
    gpx_dir = tmp_path / "gpx"
    gpx_dir.mkdir()
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(script, "PROCESSED_DIR", processed)
    monkeypatch.setattr(script, "GPX_DIR", gpx_dir)
    monkeypatch.setattr(script, "OUT_PATH", processed / "hikefinder_routes.json")
    monkeypatch.setattr(script, "REVIEW_PATH", processed / "review.html")
    return {"processed": processed, "gpx": gpx_dir, "raw": raw}


def run(sandbox, monkeypatch, hikes: dict) -> dict:
    monkeypatch.setattr(script, "load_cache", lambda *a, **k: hikes)
    assert script.main([]) == 0
    return json.loads((sandbox["processed"] / "hikefinder_routes.json").read_text())


def test_a_hike_with_a_cached_track_is_read_from_it_and_marked_published(sandbox, monkeypatch):
    (sandbox["gpx"] / "7.gpx").write_text(GPX)
    document = run(
        sandbox, monkeypatch, {"7": hike(has_published_route=True, gpx_file="7.gpx", route_type="Shuttle", stated_miles=1.38)}
    )
    row = document["routes"]["7"]
    assert row["provenance"] == "published"
    assert row["grade"] == "strong"
    # The track's own length, measured on its own points - not the graph's.
    assert row["miles"] == pytest.approx(1.38, abs=0.05)


def test_a_published_track_is_never_measured_against_this_builds_lines(sandbox, monkeypatch):
    """A survey somebody walked outranks a different survey of the same
    ground. The track here runs nowhere near the synthetic graph, and that
    costs it nothing."""
    (sandbox["gpx"] / "7.gpx").write_text(GPX)
    document = run(
        sandbox, monkeypatch, {"7": hike(has_published_route=True, gpx_file="7.gpx", route_type="Shuttle", stated_miles=1.38)}
    )
    assert document["routes"]["7"]["grade"] != "rejected"


def test_a_hike_whose_track_is_missing_from_the_cache_is_rejected_rather_than_formed(sandbox, monkeypatch):
    """It said it had a survey. Quietly inferring one instead would put a
    generated line under a `published` badge."""
    document = run(sandbox, monkeypatch, {"7": hike(has_published_route=True, gpx_file="7.gpx")})
    row = document["routes"]["7"]
    assert row["provenance"] == "published"
    assert row["grade"] == "rejected"


def test_a_hike_with_no_track_is_formed_over_the_graph_and_marked_generated(sandbox, monkeypatch):
    document = run(sandbox, monkeypatch, {"7": hike()})
    assert document["routes"]["7"]["provenance"] == "generated"


def test_the_artifact_counts_the_roads_apart(sandbox, monkeypatch):
    (sandbox["gpx"] / "1.gpx").write_text(GPX)
    document = run(
        sandbox,
        monkeypatch,
        {
            "1": hike(id=1, has_published_route=True, gpx_file="1.gpx", route_type="Shuttle", stated_miles=1.38),
            "7": hike(),
        },
    )
    assert any(key.startswith("published/") for key in document["counts"])
    assert any(key.startswith("generated/") for key in document["counts"])


def test_a_hike_that_got_no_route_is_still_in_the_artifact_with_its_reason(sandbox, monkeypatch):
    """ "This hike got no line, and here is why" is the answer a reviewer
    needs. An absent row would make a refusal indistinguishable from a hike
    nobody tried."""
    document = run(sandbox, monkeypatch, {"7": hike(start=None)})
    row = document["routes"]["7"]
    assert row["grade"] == "rejected"
    assert row["ends"] == []
    assert row["problems"]


def test_the_sheet_shows_the_refusals_and_not_only_the_successes(sandbox, monkeypatch):
    run(sandbox, monkeypatch, {"7": hike(start=None)})
    sheet = (sandbox["processed"] / "review.html").read_text()
    assert "No route ships for this hike" in sheet
    assert "Pine Meadow Loop" in sheet


def test_the_sheet_prints_the_publishers_tags(sandbox, monkeypatch):
    run(sandbox, monkeypatch, {"7": hike()})
    assert "Views" in (sandbox["processed"] / "review.html").read_text()


def test_a_cache_with_no_hikes_routes_nothing_and_lets_the_publish_through(sandbox, monkeypatch):
    """#1462, and it is the whole reason that issue exists. This used to raise
    SystemExit, which cost publish-vector-data.yml run 114 forty-two minutes of
    built trails, POIs and junction graph because one website timed out for
    three of them. Nothing downstream of the A.T. data needs NYNJTC's day
    hikes, so a run that has none writes no artifact and exits clean."""
    monkeypatch.setattr(script, "load_cache", lambda *a, **k: {})
    assert script.main([]) == 0
    assert not (sandbox["processed"] / "hikefinder_routes.json").exists()


def test_a_cache_that_is_absent_is_quiet_but_one_that_will_not_parse_is_not(sandbox):
    """The other half of #1462, and the half that keeps it honest. Absence is a
    fact about this run; a file that is there and unreadable is a defect, and
    softening both together would trade a loud failure for a silent one."""
    missing = sandbox["raw"] / "nothing_here.json"
    assert script.load_cache(missing) == {}

    corrupt = sandbox["raw"] / "hikefinder.json"
    corrupt.write_text("{ this is not json")
    with pytest.raises(SystemExit, match="unreadable"):
        script.load_cache(corrupt)


def test_only_narrows_the_run_to_the_ids_named(sandbox, monkeypatch):
    monkeypatch.setattr(script, "load_cache", lambda *a, **k: {"1": hike(id=1), "7": hike()})
    assert script.main(["--only", "7"]) == 0
    document = json.loads((sandbox["processed"] / "hikefinder_routes.json").read_text())
    assert set(document["routes"]) == {"7"}


def test_load_track_reads_the_cached_file_and_returns_none_when_there_is_not_one(sandbox):
    (sandbox["gpx"] / "7.gpx").write_text(GPX)
    assert isinstance(script.load_track({"gpx_file": "7.gpx"}, sandbox["gpx"]), Track)
    assert script.load_track({"gpx_file": None}, sandbox["gpx"]) is None
    assert script.load_track({"gpx_file": "missing.gpx"}, sandbox["gpx"]) is None


def test_the_sketch_draws_a_track_and_a_formed_walk_with_the_same_code():
    """So a published line and an inferred one can be compared by eye without
    one of them flattering itself."""
    line = [[LON, LAT], [LON + STEP, LAT], [LON + STEP, LAT + STEP]]
    svg = script.sketch_svg([line], [], [(LON, LAT)])
    assert svg.startswith("<svg")
    assert "500 m" in svg
    assert script.sketch_svg([], [], []).startswith("<p")
