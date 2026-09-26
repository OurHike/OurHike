"""Tests for fetch_trail_water.py - which sites have water a hiker can reach
(#529). It derived stream crossings too until #1674 removed them; the tests
that were about crossings went with them, and the lineage tests that used
crossings as their fixture are written against site water now.

Synthetic geometry and canned elevations throughout, never a state extract or
a USGS subregion: the smallest of either is hundreds of megabytes, and
everything decision-shaped here - the two gates, the merge, the point-to-
segment distance - is pure or monkeypatchable without one (TESTING.md).
"""

import json
import math
from pathlib import Path

import fetch_trail_water as trail_water
from fetch_trail_water import (
    MATCH_RADIUS_FT,
    MAX_GRADE,
    MIN_GRADE_RUN_FT,
    NHD_LINEAGE_TAGS,
    build,
    closest_point_on_paths,
    grade_gate,
    merge_osm_lineage,
    merge_stream_facts,
    nearest_stream,
    osm_stream_table,
    render,
    resolve_site,
    state_site_candidates,
)
from tests.conftest import spatial_connection
from tests.synthetic import CENTERLINE_COORDS

M_PER_DEG_LAT = 111_132.0


def _north(metres):
    """A latitude offset, so a fixture can say how far apart two things are."""
    return metres / M_PER_DEG_LAT


# --- the merge ------------------------------------------------------------


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


# --- the write guards ----------------------------------------------------


def _stream_beside(site, metres_north=10.0, stream_id="1"):
    """One candidate reach running east-west a few metres north of a site -
    inside MATCH_RADIUS_FT, so with flat ground the site has water."""
    lat = site["lat"] + _north(metres_north)
    return {
        "source": "nhd",
        "stream_id": stream_id,
        "name": None,
        "flow": "perennial",
        "osm_from_nhd": None,
        "paths": [[[site["lon"] - 0.001, lat], [site["lon"] + 0.001, lat]]],
    }


def _many_sites(count):
    return [
        {"global_id": f"shelter-{index}", "name": f"Shelter {index}", "lat": 41.0 + _north(500 * index), "lon": -74.0}
        for index in range(count)
    ]


def test_a_derivation_that_lost_most_of_its_site_water_refuses_to_overwrite(tmp_path, monkeypatch):
    """A read that half-failed must not be able to replace good output with
    less of it. Crossings were this guard's figure until #1674 removed them;
    site water is what the file publishes now, so it is what is counted."""
    out = tmp_path / "trail_water.json"
    sites = _many_sites(8)
    monkeypatch.setattr(trail_water, "OUT_PATH", out)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: sites if layer == "shelters" else [])
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    every_site = {site["global_id"]: [_stream_beside(site)] for site in sites}
    monkeypatch.setattr(trail_water, "collect_streams", lambda _sites: every_site)
    assert trail_water.main([]) == 0
    written = out.read_text()
    assert json.loads(written)["counts"]["sites_with_water"] == 8

    a_quarter = {site["global_id"]: [_stream_beside(site)] for site in sites[:2]}
    monkeypatch.setattr(trail_water, "collect_streams", lambda _sites: a_quarter)
    assert trail_water.main([]) == 1
    assert out.read_text() == written


def test_the_drop_guard_reads_a_file_written_before_crossings_were_removed(tmp_path):
    """The workflow restores the PUBLISHED trail_water.json before deriving
    (publish-vector-data.yml), so the first run after #1674 compares against a
    file that still carries `crossings`. Its `sites` are the same shape, and
    are what gets counted."""
    old = tmp_path / "trail_water.json"
    old.write_text(
        json.dumps(
            {
                "counts": {"crossings": 1125, "sites": 3, "sites_with_water": 2},
                "crossings": [{"lat": 41.0, "lon": -74.0}],
                "sites": [{"water": {"lat": 41.0}}, {"water": None}, {"water": {"lat": 42.0}}],
            }
        )
    )

    assert trail_water.existing_site_water_count(old) == 2


def test_a_hydrography_read_that_loads_no_streams_refuses_and_writes_nothing(tmp_path, monkeypatch):
    """The other half of the guard, and the one a first run depends on, since
    there is no previous file to compare against. Every state extract and
    subregion this walks has streams, so zero reaches is a broken read, not a
    dry state - and without this it would write a file with no site water."""
    monkeypatch.setattr(trail_water, "AT_STATES", ["georgia"])
    monkeypatch.setattr(trail_water, "OSM_RAW_DIR", tmp_path)
    monkeypatch.setattr(trail_water, "ensure_state_extracts", lambda: None)
    (tmp_path / "georgia-latest.osm.pbf").write_bytes(b"present")
    monkeypatch.setattr(trail_water, "osm_stream_table", lambda con, pbf: 0)
    out = tmp_path / "trail_water.json"
    monkeypatch.setattr(trail_water, "OUT_PATH", out)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [_site()] if layer == "shelters" else [])

    assert trail_water.main([]) == 1
    assert not out.exists()


def test_a_good_derivation_records_a_receipt(tmp_path, monkeypatch):
    """The completion record check_output_quality.py re-hashes (#542) - a
    derived input nobody can prove was derived this run is the gap that gate
    exists to close."""
    out = tmp_path / "trail_water.json"
    site = _site()
    monkeypatch.setattr(trail_water, "OUT_PATH", out)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [site] if layer == "shelters" else [])
    monkeypatch.setattr(trail_water, "collect_streams", lambda _sites: {site["global_id"]: [_stream_beside(site)]})
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    assert trail_water.main([]) == 0

    from lib import fetch_receipts

    receipt = fetch_receipts.load("fetch_trail_water")
    assert receipt is not None
    assert [output["path"] for output in receipt["outputs"]] == [str(out)]


def test_the_file_carries_no_crossings_any_more():
    """#1674. Neither the document nor its rendering names the array, so
    nothing downstream can go on reading an empty one as "no crossings
    here" rather than "not derived"."""
    document = build({"shelters": [_site()]}, {})

    assert "crossings" not in document
    assert not any(key.startswith("crossings") for key in document["counts"])
    assert '"crossings"' not in render(document)
    assert json.loads(render(document))["sites"][0]["atc_global_id"] == "shelter-1"


def test_the_files_own_header_quotes_the_gates_it_was_written_under():
    """The header said "under a 35% grade" for as long as MAX_GRADE was 0.15,
    and the script's name in it stayed `build_trail_water.py` through the
    rename that moved this output out of the repository.

    Neither is cosmetic. `_README` is the first thing anybody opening
    trail_water.json reads, and both errors point a reader at a gate twice as
    loose as the real one and at a script that does not exist. The strings are
    interpolated from the constants now, so this test is what keeps them
    honest rather than the next author noticing."""
    header = "\n".join(trail_water.README)

    assert f"{MATCH_RADIUS_FT:.0f} ft" in header
    assert f"{MAX_GRADE:.0%}" in header
    assert "build_trail_water.py" not in header
    assert "fetch_trail_water.py" in header


# --- the grade gate itself, shared with build_osm_water_reach.py (#815) ------


def test_a_walk_under_the_grade_passes():
    grade, walkable = grade_gate(drop_ft=10.0, distance_ft=100.0)

    assert grade == 0.1
    assert walkable is True


def test_a_scramble_over_a_run_long_enough_to_mean_it_is_refused():
    grade, walkable = grade_gate(drop_ft=50.0, distance_ft=100.0)

    assert grade == 0.5
    assert walkable is False


def test_a_run_too_short_to_have_a_grade_is_not_called_steep():
    """#815: below MIN_GRADE_RUN_FT the ratio is noise, and this module's own
    comment has said so since #529 - a spring a foot from the trail is not a
    scramble because the arithmetic divided by a foot."""
    grade, walkable = grade_gate(drop_ft=1.5, distance_ft=1.0)

    assert grade > MAX_GRADE
    assert walkable is True


def test_the_ratio_is_still_returned_when_the_floor_carries_the_verdict():
    """Both callers record the number whatever the verdict, because a file that
    keeps its numbers can be re-argued rather than re-run in the dark."""
    grade, _ = grade_gate(drop_ft=2.0, distance_ft=2.0)

    assert grade == 1.0


def test_a_zero_length_walk_does_not_raise():
    """A site sitting exactly on its stream. The floor already carries the
    verdict here; the guard is only so the recorded ratio can be computed."""
    grade, walkable = grade_gate(drop_ft=3.0, distance_ft=0.0)

    assert grade == 3.0
    assert walkable is True


def test_the_floor_sits_below_the_runs_the_census_defended():
    """#815 measured the surviving refusals at 10-100 ft runs (2026-08-18) and
    the rescued ones under 5 ft. A floor that climbed past 10 ft would start
    passing points that census called defensible."""
    assert 5.0 <= MIN_GRADE_RUN_FT <= 10.0


# --- whether "both databases" is two opinions or one (#710) -----------------


def test_two_ids_are_not_two_opinions_when_osm_imported_the_line():
    """The whole subject of #710. Measured 2026-08-14: 77% of Virginia's OSM
    stream ways carry NHD's tags against 0% of New Hampshire's, so a merged
    stream there is NHD agreeing with itself under a second id."""
    merged = merge_stream_facts(
        {"sources": ["nhd"], "stream_id": "usgs-1", "name": None, "flow": "perennial", "osm_from_nhd": None},
        {"sources": ["osm"], "stream_id": "osm-1", "name": "Stony Brook", "flow": None, "osm_from_nhd": True},
    )

    assert merged["sources"] == ["nhd", "osm"]
    assert merged["osm_from_nhd"] is True


def test_a_line_somebody_drew_is_a_real_second_opinion():
    merged = merge_stream_facts(
        {"sources": ["nhd"], "stream_id": "usgs-1", "name": None, "flow": "perennial", "osm_from_nhd": None},
        {"sources": ["osm"], "stream_id": "osm-1", "name": None, "flow": None, "osm_from_nhd": False},
    )

    assert merged["osm_from_nhd"] is False


def test_a_stream_no_osm_way_reached_says_nothing_either_way():
    """None, not False: "nobody from OSM said anything" and "OSM said
    something of its own" are different claims about the same water."""
    site = _site()
    found = nearest_stream(site["lat"], site["lon"], [_stream_beside(site)])

    assert found["osm_from_nhd"] is None


def test_one_drawn_way_carries_the_corroboration_for_the_pile():
    """all(), not any(). A stop can fold in several OSM ways; if one of them
    is a line somebody actually drew, the independent observation is there
    whatever the imported one beside it descends from."""
    assert merge_osm_lineage(True, False) is False
    assert merge_osm_lineage(True, True) is True
    assert merge_osm_lineage(None, True) is True
    assert merge_osm_lineage(None, False) is False
    assert merge_osm_lineage(None, None) is None


def test_the_query_asks_for_every_lineage_tag_the_constant_names():
    """The constant is the reviewable thing, so the query has to be built from
    it - a tag added to NHD_LINEAGE_TAGS and not asked for would silently
    label imported ways as independent."""
    asked = []

    class _Recorder:
        def execute(self, sql):
            asked.append(sql)
            return self

        def fetchone(self):
            return (0,)

    osm_stream_table(_Recorder(), Path("nowhere.osm.pbf"))

    ways_query = asked[0]
    for tag in NHD_LINEAGE_TAGS:
        assert f"tags['{tag}']" in ways_query


def test_gnis_is_not_treated_as_lineage():
    """#710 lists `gnis:feature_id` with the NHD tags, and this build reads it
    as a narrower claim: it attests where the NAME came from, not the line. A
    stream digitised from a walk and labelled from USGS's gazetteer is still
    an independent opinion about where the water is."""
    assert not any("gnis" in tag.lower() for tag in NHD_LINEAGE_TAGS)


def test_site_candidates_read_the_column_both_loaders_write():
    """Run against real DuckDB, because nothing else in this suite does.

    The lineage column is written by two different CREATE TABLE statements
    (osm_stream_table and nhd_stream_table both build `streams`) and read
    here - the only reader since #1674 took state_crossings away. Those only
    meet on a full run over hundreds of megabytes of extract, and a column
    landing in the wrong place would silently shift every field: a name
    arriving where a flow class belongs is not an error DuckDB raises.
    """
    con = spatial_connection()
    try:
        lon, lat = CENTERLINE_COORDS[0]
        con.execute(
            f"""
            CREATE TABLE sites AS
            SELECT 'site-1' AS global_id, ST_Point({lon}, {lat}) AS geom
            """
        )
        con.execute(
            f"""
            CREATE TABLE streams AS
            SELECT 'osm' AS source, 'osm-1' AS id, TRUE AS osm_from_nhd, 'Imported Brook' AS name,
                   'intermittent' AS flow,
                   ST_GeomFromText('LINESTRING({lon} {lat}, {lon} {lat + 0.0001})') AS geom
            """
        )

        candidates = state_site_candidates(con)
    finally:
        con.close()

    (candidate,) = candidates["site-1"]
    assert candidate["name"] == "Imported Brook"
    assert candidate["flow"] == "intermittent"
    assert candidate["osm_from_nhd"] is True


# --- fetching its own input (#1066) ----------------------------------------


def test_missing_extracts_are_fetched_rather_than_instructed_about(tmp_path, monkeypatch):
    """#1066: run 33009118830 ticked include_trail_water without
    include_osm_water and died two minutes in on a FileNotFoundError telling
    a human to run another script - dead advice mid-CI. The missing extracts
    are this derivation's input, so it fetches them itself."""
    monkeypatch.setattr(trail_water, "AT_STATES", ["georgia", "vermont", "maine"])
    monkeypatch.setattr(trail_water, "OSM_RAW_DIR", tmp_path)
    (tmp_path / "georgia-latest.osm.pbf").write_bytes(b"present")
    (tmp_path / "maine-latest.osm.pbf").write_bytes(b"present")

    fetched = []
    monkeypatch.setattr(trail_water, "fetch_states", lambda states, dest: fetched.append((states, dest)))

    trail_water.ensure_state_extracts()

    assert fetched == [(["vermont"], tmp_path)]


def test_extracts_already_on_disk_cost_nothing(tmp_path, monkeypatch):
    """The run where the OSM water step already downloaded them - the normal
    ticked-both dispatch - pays one stat call per state, no network."""
    monkeypatch.setattr(trail_water, "AT_STATES", ["georgia"])
    monkeypatch.setattr(trail_water, "OSM_RAW_DIR", tmp_path)
    (tmp_path / "georgia-latest.osm.pbf").write_bytes(b"present")

    def boom(*args, **kwargs):
        raise AssertionError("nothing was missing, so nothing may be fetched")

    monkeypatch.setattr(trail_water, "fetch_states", boom)

    trail_water.ensure_state_extracts()
