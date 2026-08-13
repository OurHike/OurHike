"""Tests for build_trail_water.py - where the trail meets water, and which
sites have water a hiker can reach (#529).

Synthetic geometry and canned elevations throughout, never a state extract or
a USGS subregion: the smallest of either is hundreds of megabytes, and
everything decision-shaped here - the two gates, the merge, the point-to-
segment distance - is pure or monkeypatchable without one (TESTING.md).
"""

import json
import math

import build_trail_water as trail_water
from build_trail_water import (
    CROSSING_DEDUPE_M,
    MATCH_RADIUS_FT,
    MAX_GRADE,
    closest_point_on_paths,
    dedupe_crossings,
    merge_stream_facts,
    nearest_stream,
    resolve_site,
)

M_PER_DEG_LAT = 111_132.0


def _crossing(source, lat, lon, name=None, flow=None, stream_id="1"):
    return {"sources": [source], "stream_id": stream_id, "name": name, "flow": flow, "lat": lat, "lon": lon}


def _north(metres):
    """A latitude offset, so a fixture can say how far apart two things are."""
    return metres / M_PER_DEG_LAT


# --- the merge, which is the half that failed silently --------------------


def test_two_databases_crossing_the_same_water_become_one_stop():
    """The bug this pins shipped once and counted itself as working: the
    dedupe collapsed the pair but kept only the winner's facts, so every
    published crossing claimed a single source and USGS's flow class never
    reached an OSM crossing. `crossings_from_both` read 0 across the whole
    corridor, which is what gave it away."""
    kept = dedupe_crossings(
        [
            _crossing("nhd", 41.0, -74.0, flow="perennial", stream_id="usgs-1"),
            _crossing("osm", 41.0 + _north(30), -74.0, name="Stony Brook", stream_id="osm-1"),
        ]
    )

    assert len(kept) == 1
    (merged,) = kept
    assert merged["sources"] == ["nhd", "osm"]
    # Each database's own contribution survives: OSM had the name, USGS the
    # flow class, and the claim is attributed to whoever made it.
    assert merged["name"] == "Stony Brook"
    assert merged["flow"] == "perennial"
    assert merged["flow_source"] == "nhd"


def test_water_further_apart_than_a_stop_stays_two_crossings():
    kept = dedupe_crossings(
        [
            _crossing("nhd", 41.0, -74.0, name="First"),
            _crossing("osm", 41.0 + _north(CROSSING_DEDUPE_M + 20), -74.0, name="Second"),
        ]
    )

    assert [crossing["name"] for crossing in kept] == ["First", "Second"]


def test_the_surveyed_position_is_the_one_kept():
    """USGS is sorted first so a merged crossing keeps its position, which is
    what the published id is built from - an id that changed depending on
    which database happened to be read first would not survive a re-run."""
    kept = dedupe_crossings(
        [
            _crossing("osm", 41.0 + _north(20), -74.0, name="Stony Brook"),
            _crossing("nhd", 41.0, -74.0, flow="perennial"),
        ]
    )

    (merged,) = kept
    assert merged["lat"] == 41.0


def test_merge_keeps_a_flow_class_the_winner_lacked_and_says_whose_it_is():
    merged = merge_stream_facts(
        {"sources": ["osm"], "name": "Stony Brook", "flow": None},
        {"sources": ["nhd"], "name": None, "flow": "intermittent", "flow_source": "nhd"},
    )

    assert merged["flow"] == "intermittent"
    assert merged["flow_source"] == "nhd"
    assert merged["name"] == "Stony Brook"


# --- the two gates --------------------------------------------------------


def _site(lat=41.0, lon=-74.0):
    return {"global_id": "shelter-1", "name": "Test Shelter", "lat": lat, "lon": lon}


def _stream_at(metres_north, source="osm", name="Stony Brook", flow=None):
    """A stream running east-west, `metres_north` north of (41, -74)."""
    lat = 41.0 + _north(metres_north)
    return {
        "source": source,
        "stream_id": "1",
        "name": name,
        "flow": flow,
        "paths": [[[-74.001, lat], [-73.999, lat]]],
    }


def test_a_stream_inside_both_gates_is_this_sites_water(monkeypatch):
    # 20 m away and 1 ft below: a walk.
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0 if lat == 41.0 else 1999.0)

    record = resolve_site(_site(), "shelters", [_stream_at(20)])

    assert record["water"] is not None
    assert record["water"]["name"] == "Stony Brook"
    assert "unresolved" not in record


def test_a_stream_past_the_radius_is_refused_with_its_distance(monkeypatch):
    """Most A.T. shelters have had their own spring built out over decades,
    so the nearest blue line is usually not the shelter's water - which is
    why this gate is tight and why the refusal keeps the number that would
    let somebody argue it wider."""
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    record = resolve_site(_site(), "shelters", [_stream_at(60)])  # ~197 ft

    assert record["water"] is None
    assert "past the" in record["unresolved"]
    assert record["candidate"]["distance_ft"] > MATCH_RADIUS_FT


def test_a_stream_down_a_cliff_is_refused_however_close_it_is(monkeypatch):
    """The whole point of the second gate: 90 ft away and 120 ft below is not
    a water source, it is a fall. The refusal records the grade so the
    threshold is arguable from the file."""
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0 if lat == 41.0 else 1880.0)

    record = resolve_site(_site(), "shelters", [_stream_at(25)])

    assert record["water"] is None
    assert "scramble" in record["unresolved"]
    assert record["candidate"]["grade"] > MAX_GRADE


def test_an_elevation_usgs_will_not_give_publishes_nothing(monkeypatch):
    """The safe direction: with no ground between the two points known,
    nothing here can say the walk is a walk."""
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: None)

    record = resolve_site(_site(), "shelters", [_stream_at(20)])

    assert record["water"] is None
    assert "elevation" in record["unresolved"]


def test_a_site_with_no_stream_nearby_says_so(monkeypatch):
    record = resolve_site(_site(), "shelters", [])

    assert record["water"] is None
    assert record["unresolved"] == trail_water.NO_STREAM_NEARBY


# --- the geometry ---------------------------------------------------------


def test_the_nearest_point_is_on_the_segment_not_at_a_vertex():
    """A shelter beside the middle of a long reach is beside the stream
    there, and there is where a hiker walks. Measuring to the endpoints would
    put the published water point somewhere nobody goes - and would refuse
    the site for distance while it does it."""
    distance, lat, lon = closest_point_on_paths(41.0, -74.0, [[[-74.5, 41.0 + _north(30)], [-73.5, 41.0 + _north(30)]]])

    assert 29 < distance < 31
    assert math.isclose(lon, -74.0, abs_tol=1e-6)
    assert lat > 41.0


def test_the_nearest_point_across_two_databases_merges_when_they_agree():
    """Both hydrographies draw the same stream past the same shelter, tens of
    metres apart. The closer point is published and the other's facts fold
    onto it, so the site gets one water POI carrying both."""
    found = nearest_stream(
        41.0, -74.0, [_stream_at(15, source="osm", name="Stony Brook"), _stream_at(25, source="nhd", name=None, flow="perennial")]
    )

    assert found["sources"] == ["nhd", "osm"]
    assert found["name"] == "Stony Brook"
    assert found["flow"] == "perennial"
    assert found["distance_m"] < 20


def test_streams_further_apart_than_the_merge_radius_are_different_water():
    """A shelter's spring and the creek below it are two things a hiker
    chooses between, so the closer one answers and the other is not folded
    into it."""
    found = nearest_stream(
        41.0,
        -74.0,
        [_stream_at(10, source="osm", name="The Spring"), _stream_at(90, source="nhd", name="The Creek", flow="perennial")],
    )

    assert found["sources"] == ["osm"]
    assert found["name"] == "The Spring"
    assert found["flow"] is None


# --- the file contract ----------------------------------------------------


def test_check_mode_compares_without_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(trail_water, "OUT_PATH", tmp_path / "trail_water.json")
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [_site()] if layer == "shelters" else [])
    monkeypatch.setattr(
        trail_water, "collect_streams", lambda sites: ([_crossing("nhd", 41.0, -74.0)], {"shelter-1": [_stream_at(20)]})
    )
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    assert trail_water.main(["--check"]) == 1  # nothing on disk yet
    assert not (tmp_path / "trail_water.json").exists()

    assert trail_water.main([]) == 0
    assert trail_water.main(["--check"]) == 0

    drifted = json.loads((tmp_path / "trail_water.json").read_text())
    drifted["crossings"] = []
    (tmp_path / "trail_water.json").write_text(json.dumps(drifted))
    assert trail_water.main(["--check"]) == 1
