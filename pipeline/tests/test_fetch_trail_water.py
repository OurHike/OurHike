"""Tests for fetch_trail_water.py - where the trail meets water, and which
sites have water a hiker can reach (#529).

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
    CROSSING_DEDUPE_M,
    MATCH_RADIUS_FT,
    MAX_GRADE,
    MIN_GRADE_RUN_FT,
    NHD_LINEAGE_TAGS,
    build,
    closest_point_on_paths,
    dedupe_crossings,
    grade_gate,
    merge_osm_lineage,
    merge_stream_facts,
    nearest_stream,
    osm_stream_table,
    resolve_site,
    state_crossings,
    state_site_candidates,
)
from tests.conftest import spatial_connection
from tests.synthetic import CENTERLINE_COORDS, write_centerline

M_PER_DEG_LAT = 111_132.0


def _crossing(source, lat, lon, name=None, flow=None, stream_id="1", osm_from_nhd=None):
    return {
        "sources": [source],
        "stream_id": stream_id,
        "name": name,
        "flow": flow,
        "osm_from_nhd": osm_from_nhd if source == "osm" else None,
        "lat": lat,
        "lon": lon,
    }


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


# --- the write guards ----------------------------------------------------


def test_a_derivation_that_lost_most_of_its_crossings_refuses_to_overwrite(tmp_path, monkeypatch):
    """A read that half-failed must not be able to replace good output with
    less of it. Ordinary editing of either hydrography never halves a
    corridor's crossings; a broken subregion does."""
    out = tmp_path / "trail_water.json"
    monkeypatch.setattr(trail_water, "OUT_PATH", out)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [_site()] if layer == "shelters" else [])
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    plenty = [
        _crossing("nhd", 41.0 + _north(60 * index), -74.0, stream_id=str(index)) for index in range(trail_water.MIN_CROSSINGS * 2)
    ]
    monkeypatch.setattr(trail_water, "collect_streams", lambda sites: (plenty, {}))
    assert trail_water.main([]) == 0
    kept = len(json.loads(out.read_text())["crossings"])

    monkeypatch.setattr(trail_water, "collect_streams", lambda sites: (plenty[: len(plenty) // 4], {}))
    assert trail_water.main([]) == 1
    assert len(json.loads(out.read_text())["crossings"]) == kept


def test_a_derivation_below_the_floor_refuses_even_with_nothing_on_disk(tmp_path, monkeypatch):
    """The first run has no previous file to compare against, so the floor is
    the only thing between a broken read and an empty success."""
    monkeypatch.setattr(trail_water, "OUT_PATH", tmp_path / "trail_water.json")
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [_site()] if layer == "shelters" else [])
    monkeypatch.setattr(trail_water, "collect_streams", lambda sites: ([_crossing("nhd", 41.0, -74.0)], {}))
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    assert trail_water.main([]) == 1
    assert not (tmp_path / "trail_water.json").exists()


def test_a_good_derivation_records_a_receipt(tmp_path, monkeypatch):
    """The completion record check_output_quality.py re-hashes (#542) - a
    derived input nobody can prove was derived this run is the gap that gate
    exists to close."""
    out = tmp_path / "trail_water.json"
    monkeypatch.setattr(trail_water, "OUT_PATH", out)
    monkeypatch.setattr(trail_water, "fetch_atc_features", lambda layer: [_site()] if layer == "shelters" else [])
    monkeypatch.setattr(
        trail_water,
        "collect_streams",
        lambda sites: (
            [
                _crossing("nhd", 41.0 + _north(60 * index), -74.0, stream_id=str(index))
                for index in range(trail_water.MIN_CROSSINGS)
            ],
            {},
        ),
    )
    monkeypatch.setattr(trail_water, "elevation_ft", lambda lat, lon: 2000.0)

    assert trail_water.main([]) == 0

    from lib import fetch_receipts

    receipt = fetch_receipts.load("fetch_trail_water")
    assert receipt is not None
    assert [output["path"] for output in receipt["outputs"]] == [str(out)]


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
    crossing there is NHD agreeing with itself under a second id."""
    kept = dedupe_crossings(
        [
            _crossing("nhd", 41.0, -74.0, flow="perennial", stream_id="usgs-1"),
            _crossing("osm", 41.0 + _north(30), -74.0, stream_id="osm-1", osm_from_nhd=True),
        ]
    )

    (merged,) = kept
    assert merged["sources"] == ["nhd", "osm"]
    assert merged["osm_from_nhd"] is True


def test_a_line_somebody_drew_is_a_real_second_opinion():
    kept = dedupe_crossings(
        [
            _crossing("nhd", 41.0, -74.0, flow="perennial", stream_id="usgs-1"),
            _crossing("osm", 41.0 + _north(30), -74.0, stream_id="osm-1", osm_from_nhd=False),
        ]
    )

    (merged,) = kept
    assert merged["osm_from_nhd"] is False


def test_a_crossing_no_osm_way_reached_says_nothing_either_way():
    """None, not False: "nobody from OSM said anything" and "OSM said
    something of its own" are different claims about the same crossing."""
    (only_nhd,) = dedupe_crossings([_crossing("nhd", 41.0, -74.0, flow="perennial")])

    assert only_nhd["osm_from_nhd"] is None


def test_one_drawn_way_carries_the_corroboration_for_the_pile():
    """all(), not any(). A stop can fold in several OSM ways; if one of them
    is a line somebody actually drew, the independent observation is there
    whatever the imported one beside it descends from."""
    assert merge_osm_lineage(True, False) is False
    assert merge_osm_lineage(True, True) is True
    assert merge_osm_lineage(None, True) is True
    assert merge_osm_lineage(None, False) is False
    assert merge_osm_lineage(None, None) is None


def test_the_count_splits_what_sources_alone_could_not():
    """`crossings_from_both` counts two ids and reads as independent
    confirmation. Only one of these two counts two opinions, and the
    difference is what a reader would otherwise have concluded wrongly."""
    crossings = [
        {**_crossing("nhd", 41.0, -74.0), "sources": ["nhd", "osm"], "osm_from_nhd": True},
        {**_crossing("nhd", 42.0, -74.0), "sources": ["nhd", "osm"], "osm_from_nhd": False},
        _crossing("nhd", 43.0, -74.0),
    ]

    counts = build({}, {}, crossings)["counts"]

    assert counts["crossings_from_both"] == 2
    assert counts["crossings_corroborated_independently"] == 1
    assert counts["crossings_from_both_shared_lineage"] == 1


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


def test_state_crossings_reads_the_column_both_loaders_write():
    """Run against real DuckDB, because nothing else in this suite does.

    The lineage column is written by two different CREATE TABLE statements
    (osm_stream_table and nhd_stream_table both build `streams`) and read by
    two more. Those four only meet on a full run over hundreds of megabytes of
    extract, so a column named in one and not another would ship. This builds
    the same table shape by hand and makes the reader prove it.
    """
    con = spatial_connection()
    try:
        (start_lon, start_lat), (end_lon, end_lat) = CENTERLINE_COORDS
        mid_lon = (start_lon + end_lon) / 2
        mid_lat = (start_lat + end_lat) / 2
        # `routes` rather than `centerline` since #1016, and with the three
        # columns build_routes adds - an A.T.-only row is the false/NULL/NULL
        # case, which is what this table was before that.
        con.execute(
            f"""
            CREATE TABLE routes AS
            SELECT ST_GeomFromText('LINESTRING({start_lon} {start_lat}, {end_lon} {end_lat})') AS geom,
                   false AS on_network, NULL::VARCHAR AS src, NULL::VARCHAR AS trail_name
            """
        )
        # Columns and order exactly as the two loaders emit them.
        con.execute(
            f"""
            CREATE TABLE streams AS
            SELECT 'osm' AS source, 'osm-1' AS id, TRUE AS osm_from_nhd, 'Imported Brook' AS name,
                   NULL AS flow,
                   ST_GeomFromText('LINESTRING({mid_lon} {mid_lat - 0.01}, {mid_lon} {mid_lat + 0.01})') AS geom
            UNION ALL
            SELECT 'nhd', 'usgs-1', FALSE, 'Surveyed Brook', 'perennial',
                   ST_GeomFromText('LINESTRING({mid_lon - 0.001} {mid_lat - 0.01}, {mid_lon - 0.001} {mid_lat + 0.01})')
            """
        )

        crossings = {crossing["stream_id"]: crossing for crossing in state_crossings(con)}
    finally:
        con.close()

    assert crossings["osm-1"]["osm_from_nhd"] is True
    # NHD is the source rather than an import of it, so the question does not
    # apply to its own row and the answer is absent, not False.
    assert crossings["usgs-1"]["osm_from_nhd"] is None


def test_site_candidates_read_the_same_column():
    """The other reader of `streams.osm_from_nhd`, and the one whose unpack
    would silently shift every field if the column landed in the wrong place -
    a name arriving where a flow class belongs is not an error DuckDB raises.
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


# --- crossings on the network's trails (#1016) ------------------------------
#
# Until this, `state_crossings` intersected streams with ATC's centerline
# alone, so a stream crossing a Long Path section was geometry this file never
# asked about. Four organizations' trails shipped with no crossing at all.


def _network_file(tmp_path, features):
    path = tmp_path / "nearby_trails.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def _network_line(coords, source="oprhp_trails", name="A Park Trail"):
    return {
        "type": "Feature",
        "properties": {"source": source, "name": name},
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
    }


def _routes_fixture(tmp_path, monkeypatch, network_features=None, shipped=None):
    """A `routes` table over the synthetic centerline, with network lines only
    when a test asks for them.

    CENTERLINE_PATH is redirected too: build_routes reads the real
    data/raw/centerline.geojson otherwise, which is 690,040 vertices of real
    trail on a machine that has fetched it and absent on one that has not.
    """
    centerline = tmp_path / "centerline.geojson"
    write_centerline(centerline)
    monkeypatch.setattr(trail_water, "CENTERLINE_PATH", centerline)
    network = _network_file(tmp_path, network_features or [])
    if network_features is None:
        network = tmp_path / "nowhere.geojson"
    monkeypatch.setattr(trail_water, "NETWORK_LINES_PATH", network)
    if shipped is None:
        shipped = {feature["properties"]["source"] for feature in network_features or []}
    monkeypatch.setattr(trail_water, "shipped_network_keys", lambda: shipped)
    return spatial_connection()


def _stream_across(con, coords):
    """One stream crossing the line between `coords`, in the column shape both
    loaders emit."""
    (start_lon, start_lat), (end_lon, end_lat) = coords
    mid_lon, mid_lat = (start_lon + end_lon) / 2, (start_lat + end_lat) / 2
    con.execute(
        f"""
        CREATE OR REPLACE TABLE streams AS
        SELECT 'nhd' AS source, 'usgs-1' AS id, FALSE AS osm_from_nhd, 'A Brook' AS name,
               'perennial' AS flow,
               ST_GeomFromText('LINESTRING({mid_lon - 0.02} {mid_lat}, {mid_lon + 0.02} {mid_lat})') AS geom
        """
    )


def test_a_stream_crossing_a_network_trail_is_a_crossing(tmp_path, monkeypatch):
    """#1016 for the second hydrography: the crossing exists on the ground and
    this file simply never looked at that line."""
    network_coords = [(-74.0, 43.0), (-73.9, 43.1)]
    con = _routes_fixture(tmp_path, monkeypatch, [_network_line(network_coords)])
    try:
        assert trail_water.build_routes(con) == 1
        _stream_across(con, network_coords)
        crossings = trail_water.state_crossings(con)
    finally:
        con.close()

    assert len(crossings) == 1
    assert crossings[0]["on_network"] is True
    assert crossings[0]["network_source"] == "oprhp_trails"
    assert crossings[0]["trail_name"] == "A Park Trail"


def test_an_at_crossing_says_it_is_not_on_a_network_trail(tmp_path, monkeypatch):
    """The column that keeps the A.T.'s own crossings carrying their mile.
    False rather than absent, so export_poi.py reads an answer rather than a
    silence."""
    con = _routes_fixture(tmp_path, monkeypatch, [_network_line([(-74.0, 43.0), (-73.9, 43.1)])])
    try:
        trail_water.build_routes(con)
        _stream_across(con, CENTERLINE_COORDS)
        crossings = trail_water.state_crossings(con)
    finally:
        con.close()

    assert len(crossings) == 1
    assert crossings[0]["on_network"] is False
    assert crossings[0]["network_source"] is None


def test_no_network_artifact_leaves_the_at_alone_in_routes(tmp_path, monkeypatch):
    con = _routes_fixture(tmp_path, monkeypatch)
    try:
        assert trail_water.build_routes(con) == 0
        _stream_across(con, CENTERLINE_COORDS)
        crossings = trail_water.state_crossings(con)
    finally:
        con.close()

    assert [c["on_network"] for c in crossings] == [False]


def test_an_empty_network_artifact_adds_no_routes(tmp_path, monkeypatch):
    """The licence-gate state, and the one that makes ST_Read yield a table
    with no `source` column to name."""
    con = _routes_fixture(tmp_path, monkeypatch, [])
    try:
        assert trail_water.build_routes(con) == 0
    finally:
        con.close()


def test_a_crossing_both_trails_make_is_still_on_the_at(tmp_path, monkeypatch):
    """Through Harriman the Long Path runs beside the A.T., so the two cross
    the same brook within CROSSING_DEDUPE_M and arrive at the dedupe as a pair.

    Taking the kept record's answer would decide which trail the merged pin is
    on by which HYDROGRAPHY saw the water first - the sort is USGS-first for id
    stability, which has nothing to say about trails - and half the time that
    would strip the A.T. mile off a stream the A.T. genuinely crosses, dropping
    it out of a day plan's water.
    """
    on_network = _crossing("nhd", 41.0, -74.0, flow="perennial", stream_id="usgs-1")
    on_network.update({"on_network": True, "network_source": "nynjtc_long_path", "trail_name": "Long Path"})
    on_at = _crossing("osm", 41.0 + _north(20), -74.0, name="Stony Brook", stream_id="osm-1")
    on_at.update({"on_network": False, "network_source": None, "trail_name": None})

    (merged,) = dedupe_crossings([on_network, on_at])

    assert merged["on_network"] is False
    # Combine, never drop the loser: the pin still says whose trail also
    # crosses here, even though the mile it carries is the A.T.'s.
    assert merged["network_source"] == "nynjtc_long_path"


def test_a_crossing_only_network_trails_make_stays_off_the_at():
    """The other direction, and the one that must not soften: two organizations
    crossing the same brook away from the A.T. is not an A.T. crossing."""
    first = _crossing("nhd", 41.0, -74.0, stream_id="usgs-1")
    first.update({"on_network": True, "network_source": "oprhp_trails", "trail_name": "A Park Trail"})
    second = _crossing("osm", 41.0 + _north(20), -74.0, name="Stony Brook", stream_id="osm-1")
    second.update({"on_network": True, "network_source": "nynjtc_long_path", "trail_name": "Long Path"})

    (merged,) = dedupe_crossings([first, second])

    assert merged["on_network"] is True


def test_a_review_only_organizations_lines_get_no_crossings(tmp_path, monkeypatch):
    """The same rule as the reach gate's, for the same reason: a crossing
    derived from a held-back organization's line is that organization's data
    reaching a hiker."""
    network_coords = [(-74.0, 43.0), (-73.9, 43.1)]
    con = _routes_fixture(
        tmp_path,
        monkeypatch,
        [_network_line(network_coords, source="dec_catskills_trails")],
        shipped=set(),
    )
    try:
        assert trail_water.build_routes(con) == 0
        _stream_across(con, network_coords)
        crossings = trail_water.state_crossings(con)
    finally:
        con.close()

    assert crossings == []


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
