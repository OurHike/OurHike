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


# --- --derive: the monthly build's form, from files on disk alone (#1652) ----


def _as_landed(raw_dir, layer, features):
    """An as-landed ATC layer as extract/_run.py writes it: GeoJSON, the server's own field names."""
    (raw_dir / f"{layer}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _landed_site(global_id, name, lon=-74.0, lat=41.0):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"GlobalID": global_id, "Name": name},
    }


def _derive_on_disk(tmp_path, monkeypatch, states=("georgia", "maine")):
    monkeypatch.setattr(trail_water, "AT_STATES", list(states))
    monkeypatch.setattr(trail_water, "OSM_RAW_DIR", tmp_path / "osm")
    monkeypatch.setattr(trail_water, "RAW_DIR", tmp_path)
    monkeypatch.setattr(trail_water, "OUT_PATH", tmp_path / "trail_water.json")
    (tmp_path / "osm").mkdir()

    def never(*args, **kwargs):
        raise AssertionError("--derive fetches nothing: not ATC's layers, not an extract")

    monkeypatch.setattr(trail_water, "fetch_atc_features", never)
    monkeypatch.setattr(trail_water, "fetch_states", never)


def test_derive_reads_the_as_landed_sites_in_fetch_atc_features_shape_and_order(tmp_path, monkeypatch):
    _derive_on_disk(tmp_path, monkeypatch)
    _as_landed(
        tmp_path,
        "shelters",
        [
            _landed_site("{B}", "Zeta Shelter"),
            _landed_site("{A}", "Alpha Shelter"),
            {"type": "Feature", "geometry": None, "properties": {"GlobalID": "{C}"}},
        ],
    )
    _as_landed(tmp_path, "campsites", [_landed_site("{D}", None, lon=-74.5, lat=41.5)])

    sites = trail_water.from_disk_sites(tmp_path)

    assert [row["global_id"] for row in sites["shelters"]] == ["{A}", "{B}"], "by name then id, and no point no row"
    assert sites["campsites"] == [{"global_id": "{D}", "name": None, "lat": 41.5, "lon": -74.5}]


def test_derive_refuses_a_missing_extract_rather_than_fetching_it(tmp_path, monkeypatch, capsys):
    _derive_on_disk(tmp_path, monkeypatch)
    (tmp_path / "osm" / "georgia-latest.osm.pbf").write_bytes(b"present")

    assert trail_water.main(["--derive"]) == 1
    assert "no extract on disk for maine" in capsys.readouterr().out
    assert not (tmp_path / "trail_water.json").exists()


def test_derive_writes_the_same_file_from_the_sites_and_extracts_on_disk(tmp_path, monkeypatch):
    _derive_on_disk(tmp_path, monkeypatch)
    for state in ("georgia", "maine"):
        (tmp_path / "osm" / f"{state}-latest.osm.pbf").write_bytes(b"present")
    _as_landed(tmp_path, "shelters", [_landed_site("shelter-1", "Test Shelter")])
    _as_landed(tmp_path, "campsites", [_landed_site("camp-1", "Test Camp", lat=42.0)])
    asked = []

    def streams(sites, fetch_extracts=True):
        asked.append(fetch_extracts)
        return {"shelter-1": [_stream_beside(_site())]}

    monkeypatch.setattr(trail_water, "collect_streams", streams)
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    assert trail_water.main(["--derive"]) == 0

    written = json.loads((tmp_path / "trail_water.json").read_text())
    assert asked == [False], "the extracts are read off disk, never fetched"
    assert [(site["atc_global_id"], site["water"] is not None) for site in written["sites"]] == [
        ("shelter-1", True),
        ("camp-1", False),
    ]


# --- the elevation cache is written in batches (#1768) ----------------------


def _fake_epqs(monkeypatch, tmp_path):
    """Point the cache at tmp_path, answer every EPQS call with 1000 ft, and
    count how many times the cache file is written."""
    cache_path = tmp_path / "epqs_elevations.json"
    monkeypatch.setattr(trail_water, "ELEVATION_CACHE_PATH", cache_path)
    monkeypatch.setattr(trail_water, "_ELEVATION_CACHE", None)
    monkeypatch.setattr(trail_water, "_ELEVATION_UNSAVED", 0)
    writes = []
    real_write = trail_water._write_elevation_cache
    monkeypatch.setattr(trail_water, "_write_elevation_cache", lambda cache: (writes.append(len(cache)), real_write(cache)))

    class Answer:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": 1000.0}

    monkeypatch.setattr(trail_water.requests, "get", lambda *a, **k: Answer())
    return cache_path, writes


def test_a_run_of_lookups_writes_the_cache_once_per_batch_not_once_per_lookup(tmp_path, monkeypatch):
    """Before #1768, 120 lookups meant 120 writes of 1..120 rows (7,260 rows).
    With a batch of 50: two writes mid-run, one at the flush - 100 + 100 + 120
    rows, counted here as writes, not timed."""
    cache_path, writes = _fake_epqs(monkeypatch, tmp_path)

    for i in range(120):
        assert trail_water.elevation_ft(40.0 + i / 1000, -75.0) == 1000.0
    trail_water.flush_elevation_cache()

    assert writes == [50, 100, 120]
    assert len(json.loads(cache_path.read_text())) == 120


def test_a_flush_with_nothing_new_writes_nothing(tmp_path, monkeypatch):
    _cache_path, writes = _fake_epqs(monkeypatch, tmp_path)

    trail_water.flush_elevation_cache()

    assert writes == []


def test_a_cached_lookup_is_neither_asked_again_nor_a_reason_to_write(tmp_path, monkeypatch):
    _cache_path, writes = _fake_epqs(monkeypatch, tmp_path)
    trail_water.elevation_ft(40.0, -75.0)
    trail_water.flush_elevation_cache()

    monkeypatch.setattr(trail_water.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("asked again")))
    assert trail_water.elevation_ft(40.0, -75.0) == 1000.0
    trail_water.flush_elevation_cache()

    assert writes == [1]


def test_main_flushes_the_cache_even_when_it_refuses(tmp_path, monkeypatch):
    """The refusal path returns 1 before any output is written; the lookups
    already answered must still reach disk or the next run re-asks EPQS."""
    cache_path, _writes = _fake_epqs(monkeypatch, tmp_path)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [])

    def refuse(_sites):
        trail_water.elevation_ft(40.0, -75.0)
        raise ValueError("no streams")

    monkeypatch.setattr(trail_water, "collect_streams", refuse)

    assert trail_water.main([]) == 1
    assert len(json.loads(cache_path.read_text())) == 1


def test_an_epqs_lookup_that_fails_or_answers_null_is_not_cached_so_the_next_attempt_asks_again(tmp_path, monkeypatch):
    """The rule that makes carrying this file between runs safe (publish-vector-data.yml's FETCH_OUTPUTS, and
    refresh-reference.yml's build job since ARC-3 of PR #1805's second review): only an answered elevation is kept.
    A null value, or five failed tries, must reach the next attempt as a question, never as a cached unknown."""
    cache_path, _writes = _fake_epqs(monkeypatch, tmp_path)
    monkeypatch.setattr(trail_water.time, "sleep", lambda _seconds: None)

    class Null:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": None}

    def down(*_args, **_kwargs):
        raise trail_water.requests.ConnectionError("EPQS is down")

    monkeypatch.setattr(trail_water.requests, "get", lambda *a, **k: Null())
    assert trail_water.elevation_ft(40.0, -75.0) is None
    monkeypatch.setattr(trail_water.requests, "get", down)
    assert trail_water.elevation_ft(41.0, -75.0) is None
    trail_water.flush_elevation_cache()

    assert not cache_path.exists() or json.loads(cache_path.read_text()) == {}
    assert trail_water._elevation_cache() == {}


def test_prefetching_asks_each_uncached_point_once_never_more_than_epqs_at_once_together_and_the_gate_then_asks_nothing(
    tmp_path, monkeypatch
):
    """Monthly run 23 (37408053482, 2026-10-06) spent 2 h 56 min in step_osm_water_grade asking EPQS one point at a
    time, silently, until the job's 240 minutes ran out. prefetch_elevations() asks several at once and logs as it
    goes; elevation_ft() then answers every prefetched point from memory."""
    import threading
    import time as real_time

    cache_path, _writes = _fake_epqs(monkeypatch, tmp_path)
    monkeypatch.setattr(trail_water, "_EPQS_DECLINED", set())
    lock = threading.Lock()
    in_flight = [0]
    most = [0]
    asked = []

    class Answer:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": 1234.0}

    def slow_get(_url, params, **_kwargs):
        with lock:
            in_flight[0] += 1
            most[0] = max(most[0], in_flight[0])
            asked.append((params["y"], params["x"]))
        real_time.sleep(0.02)
        with lock:
            in_flight[0] -= 1
        return Answer()

    monkeypatch.setattr(trail_water.requests, "get", slow_get)
    points = [(40.0 + i / 1000, -75.0) for i in range(40)]
    said = []
    assert trail_water.prefetch_elevations(points + points[:5], say=said.append, every=10) == 40

    assert sorted(asked) == sorted(points)
    assert 2 <= most[0] <= trail_water.EPQS_AT_ONCE
    assert said[0].startswith("EPQS: 40 points to look up")
    assert said[-1].startswith("  EPQS: 40/40 asked, 40 answered")

    def no_network(*_args, **_kwargs):
        raise AssertionError("elevation_ft asked EPQS for a point the prefetch already answered")

    monkeypatch.setattr(trail_water.requests, "get", no_network)
    assert [trail_water.elevation_ft(lat, lon) for lat, lon in points] == [1234.0] * 40
    trail_water.flush_elevation_cache()
    assert len(json.loads(cache_path.read_text())) == 40


def test_a_point_the_prefetch_got_no_answer_for_is_declined_this_run_without_asking_again_and_is_never_cached(
    tmp_path, monkeypatch
):
    """The prefetch spends a point's TRIES, so elevation_ft() must not spend them a second time in the same run.
    The decline stays in memory: the cache file holds only answered elevations, so the next run asks again."""
    cache_path, _writes = _fake_epqs(monkeypatch, tmp_path)
    monkeypatch.setattr(trail_water, "_EPQS_DECLINED", set())
    monkeypatch.setattr(trail_water.time, "sleep", lambda _seconds: None)

    class Null:
        def raise_for_status(self):
            pass

        def json(self):
            return {"value": None}

    calls = []

    def null_or_down(_url, params, **_kwargs):
        calls.append(params["y"])
        if params["y"] < 41:
            return Null()
        raise trail_water.requests.ConnectionError("EPQS is down")

    monkeypatch.setattr(trail_water.requests, "get", null_or_down)
    trail_water.prefetch_elevations([(40.0, -75.0), (41.0, -75.0)], say=lambda _message: None)
    assert sorted(calls) == [40.0] + [41.0] * trail_water.TRIES

    calls.clear()
    assert trail_water.elevation_ft(40.0, -75.0) is None
    assert trail_water.elevation_ft(41.0, -75.0) is None
    assert calls == []
    trail_water.flush_elevation_cache()
    assert not cache_path.exists() or json.loads(cache_path.read_text()) == {}
