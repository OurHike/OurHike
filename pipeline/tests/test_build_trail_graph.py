"""Tests for build_trail_graph.py - the junction graph a day hike routes over
(#974, features/HIKE_PLANNING.md "The day hike on a network").

Small synthetic fixtures, in and around NYC_SOURCE_SURVEY.md section 1's ring so
nothing here can be mistaken for a measurement of real data. Coordinates are
chosen so the metre distances they imply are stated in the test that uses them.

THE ASYMMETRY THIS SUITE IS WRITTEN AROUND, which is the opposite of
test_export_nearby_trails.py's and deliberately so.

That module draws lines, and its expensive failure is dropping a real trail: a
hiker who cannot see the trail they are standing on is worse off than one who
sees a duplicate. This module ROUTES over them, and the expensive failure flips.

  A MISSING JUNCTION means the router refuses a route. The hiker is told
  OurHike cannot build that walk, which is annoying, honest, and safe.

  AN INVENTED JUNCTION means the router hands somebody a path across ground
  with no trail on it, on the one screen they use to decide where to walk. That
  is FEATURES.md's confidently wrong answer.

So several tests below exist only to pin that direction, and they assert the
absence of an edge rather than its presence. A change that makes this suite
fail by connecting MORE is not obviously an improvement.
"""

import json

import pytest

import build_trail_graph as graph_builder

# Harriman-ish, inside the ring. At 41.25 N one degree of longitude is about
# 83.9 km, so 0.00012 deg is roughly 10 m - the figures each test needs are
# recomputed from the built graph rather than trusted to this note.
LON = -74.10
LAT = 41.25


def _feature(coords, feature_id="oprhp_trails:1", name="Pine Meadow Trail", **overrides):
    properties = {
        "id": feature_id,
        "source": "oprhp_trails",
        "name": name,
        "blaze_color": "blue",
        "trail_status": "open",
    }
    properties.update(overrides)
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "LineString", "coordinates": [[lon, lat] for lon, lat in coords]},
    }


def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def _build(*features, snap=graph_builder.ENDPOINT_SNAP_M):
    return graph_builder.build(_collection(*features), endpoint_snap_m=snap)


def _degrees_east(metres):
    """Longitude degrees that are roughly `metres` at LAT. Only used to place
    fixtures; every assertion measures the result rather than this."""
    return metres / (111_320 * 0.7513)


# ---------------------------------------------------------------- crossings


def test_two_lines_that_cross_are_split_and_share_one_node():
    east_west = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    north_south = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT + 0.01)],
        feature_id="nynjtc_long_path:2",
        name="Seven Hills Trail",
        source="nynjtc_long_path",
    )

    graph, stats = _build(east_west, north_south)

    # Four arms out of one crossing.
    assert stats["edges"] == 4
    assert stats["junctions"] == 1
    assert stats["components"] == 1

    # The junction is one node, reached by all four arms.
    ends = [edge["from"] for edge in graph["edges"]] + [edge["to"] for edge in graph["edges"]]
    shared = [node for node in set(ends) if ends.count(node) == 4]
    assert len(shared) == 1


def test_a_split_piece_keeps_its_parent_trails_attribution():
    east_west = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    north_south = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT + 0.01)],
        feature_id="nynjtc_long_path:2",
        name="Seven Hills Trail",
        source="nynjtc_long_path",
        blaze_color="white",
    )

    graph, _ = _build(east_west, north_south)

    # Frame 1j tallies legs per organization WHILE the hiker builds, so every
    # edge has to know its own org rather than it being re-derived at the end.
    by_source = {}
    for edge in graph["edges"]:
        by_source.setdefault(edge["source"], []).append(edge)
    assert set(by_source) == {"oprhp_trails", "nynjtc_long_path"}
    assert len(by_source["oprhp_trails"]) == 2
    assert len(by_source["nynjtc_long_path"]) == 2

    # And its name and blaze, which is the turn list's whole vocabulary.
    seven_hills = by_source["nynjtc_long_path"][0]
    assert seven_hills["name"] == "Seven Hills Trail"
    assert seven_hills["blaze_color"] == "white"
    assert seven_hills["trail_id"] == "nynjtc_long_path:2"


def test_lines_that_merely_touch_at_a_shared_end_make_one_node_and_no_split():
    first = _feature([(LON, LAT), (LON + 0.01, LAT)], feature_id="oprhp_trails:1")
    second = _feature([(LON + 0.01, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:2")

    graph, stats = _build(first, second)

    assert stats["edges"] == 2
    assert stats["components"] == 1
    assert len(graph["nodes"]) == 3


# ---------------------------------------------------------------- refusals


def test_a_closed_trail_is_never_routable_and_the_refusal_is_counted():
    open_trail = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    closed_trail = _feature(
        [(LON, LAT + 0.01), (LON + 0.02, LAT + 0.01)],
        feature_id="oprhp_trails:9",
        trail_status="Closed",
    )

    graph, stats = _build(open_trail, closed_trail)

    assert stats["lines_routable"] == 1
    assert stats["refused"]["closed"] == 1
    # A router that paths down a trail NYS OPRHP marks closed is the failure
    # this assertion exists to prevent.
    assert all(edge["trail_id"] != "oprhp_trails:9" for edge in graph["edges"])


def test_closed_matching_ignores_case_and_padding_because_stewards_publish_both():
    for status in ("closed", "CLOSED", " Closed "):
        _, stats = _build(_feature([(LON, LAT), (LON + 0.01, LAT)], trail_status=status))
        assert stats["refused"]["closed"] == 1, status


def test_a_feature_with_no_geometry_is_counted_rather_than_crashing():
    broken = _feature([(LON, LAT), (LON + 0.01, LAT)])
    broken["geometry"] = None

    _, stats = _build(broken)

    assert stats["refused"]["empty"] == 1
    assert stats["edges"] == 0


def test_a_polygon_is_refused_as_not_a_line():
    polygon = _feature([(LON, LAT), (LON + 0.01, LAT)])
    polygon["geometry"] = {
        "type": "Polygon",
        "coordinates": [[[LON, LAT], [LON + 0.01, LAT], [LON + 0.01, LAT + 0.01], [LON, LAT]]],
    }

    _, stats = _build(polygon)

    assert stats["refused"]["not_a_line"] == 1


def test_a_multilinestring_becomes_one_routable_line_per_part():
    # Real cause: NEARBY_TRAILS.md records "multi-part trails" that are
    # place-labels for path networks - Beaver Pond Campground has 34 disjoint
    # parts. Each part is walkable; the collection as a whole is not one line.
    multi = _feature([(LON, LAT), (LON + 0.01, LAT)])
    multi["geometry"] = {
        "type": "MultiLineString",
        "coordinates": [
            [[LON, LAT], [LON + 0.01, LAT]],
            [[LON, LAT + 0.02], [LON + 0.01, LAT + 0.02]],
        ],
    }

    _, stats = _build(multi)

    assert stats["lines_routable"] == 2
    assert stats["edges"] == 2
    assert stats["components"] == 2


# ------------------------------------------------------- endpoint tolerance


def test_an_end_stopping_short_of_another_line_is_joined_within_the_tolerance():
    # The cross-source case: two surveys of ground that meets, missing each
    # other by a few metres.
    main = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    gap_degrees = _degrees_east(5)
    stub = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT - gap_degrees)],
        feature_id="nynjtc_long_path:2",
        name="Stub Trail",
        source="nynjtc_long_path",
    )

    graph, stats = _build(main, stub, snap=graph_builder.ENDPOINT_SNAP_M)

    assert stats["endpoint_joins"] >= 1
    assert stats["components"] == 1, "a 5 m gap at the default tolerance should be one junction"
    assert stats["junctions"] == 1


def test_the_same_gap_is_left_open_when_the_tolerance_is_zero():
    main = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    gap_degrees = _degrees_east(5)
    stub = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT - gap_degrees)],
        feature_id="nynjtc_long_path:2",
        source="nynjtc_long_path",
    )

    _, stats = _build(main, stub, snap=0.0)

    assert stats["endpoint_joins"] == 0
    assert stats["components"] == 2


def test_parallel_trails_are_not_welded_together_at_the_default_tolerance():
    """The failure the endpoint-only rule exists to prevent.

    #771 measured that 48% of sampled A.T. points through Harriman sit within
    150 m of a different marked trail. A blanket proximity tolerance would weld
    those two lines into one along half that corridor and invent junctions
    nobody can walk. These two run 33 m apart for their whole length.
    """
    offset = _degrees_east(33)
    first = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    second = _feature(
        [(LON, LAT + offset), (LON + 0.02, LAT + offset)],
        feature_id="nynjtc_long_path:2",
        source="nynjtc_long_path",
    )

    _, stats = _build(first, second)

    assert stats["endpoint_joins"] == 0
    assert stats["components"] == 2, "two trails running alongside each other are two trails"


def test_a_line_running_beside_another_is_untouched_however_long_it_runs():
    """The same rule from the other side: proximity along a line's INTERIOR
    never creates a node, only an endpoint can. A long parallel stretch is the
    case a blanket tolerance gets most wrong."""
    offset = _degrees_east(20)
    long_line = _feature([(LON, LAT), (LON + 0.05, LAT)], feature_id="oprhp_trails:1")
    beside = _feature(
        [(LON + 0.01, LAT + offset), (LON + 0.04, LAT + offset)],
        feature_id="nynjtc_long_path:2",
        source="nynjtc_long_path",
    )

    _, stats = _build(long_line, beside, snap=graph_builder.ENDPOINT_SNAP_M)

    assert stats["components"] == 2


# ------------------------------------------------------------------- sweep


def test_the_sweep_reports_a_row_per_tolerance_and_never_disconnects_more():
    main = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    gap_degrees = _degrees_east(5)
    stub = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT - gap_degrees)],
        feature_id="nynjtc_long_path:2",
        source="nynjtc_long_path",
    )

    rows = graph_builder.sweep(_collection(main, stub), tolerances=(0.0, 2.0, 8.0, 20.0))

    assert [row["endpoint_snap_m"] for row in rows] == [0.0, 2.0, 8.0, 20.0]
    # Raising the tolerance can only ever join more, so component counts fall
    # or hold. A rise would mean the sweep is not measuring what it claims.
    components = [row["components"] for row in rows]
    assert components == sorted(components, reverse=True)


# --------------------------------------------------------------- artifact


def test_every_edge_points_at_a_node_that_exists():
    east_west = _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1")
    north_south = _feature(
        [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT + 0.01)],
        feature_id="nynjtc_long_path:2",
        source="nynjtc_long_path",
    )

    graph, _ = _build(east_west, north_south)

    for edge in graph["edges"]:
        assert 0 <= edge["from"] < len(graph["nodes"])
        assert 0 <= edge["to"] < len(graph["nodes"])
        assert edge["from"] != edge["to"]


def test_nodes_are_lon_lat_pairs_back_in_wgs84():
    graph, _ = _build(_feature([(LON, LAT), (LON + 0.01, LAT)]))

    for lon, lat in graph["nodes"]:
        assert LON - 0.5 < lon < LON + 0.5
        assert LAT - 0.5 < lat < LAT + 0.5


def test_the_graph_is_json_serialisable_because_that_is_what_ships():
    graph, _ = _build(_feature([(LON, LAT), (LON + 0.01, LAT)]))

    assert json.loads(json.dumps(graph)) == graph


def test_edge_lengths_are_metres_and_roughly_the_ground_distance():
    # 0.01 deg of longitude at 41.25 N is about 836 m. The assertion is loose
    # on purpose - it is checking the units are metres, not re-deriving the
    # projection.
    graph, _ = _build(_feature([(LON, LAT), (LON + 0.01, LAT)]))

    assert len(graph["edges"]) == 1
    assert 700 < graph["edges"][0]["length_m"] < 950


def test_an_empty_collection_builds_an_empty_graph_rather_than_failing():
    graph, stats = graph_builder.build({"type": "FeatureCollection", "features": []})

    assert graph == {"nodes": [], "edges": []}
    assert stats["edges"] == 0
    assert stats["components"] == 0


def test_load_input_says_which_script_to_run_when_the_artifact_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="export_nearby_trails.py"):
        graph_builder.load_input(tmp_path / "nope.geojson")


# ------------------------------------------------------------- graph maths


def test_junction_count_only_counts_nodes_where_three_or_more_arms_meet():
    # A single line has two ends and no junction; a crossing has one.
    line_only, _ = _build(_feature([(LON, LAT), (LON + 0.01, LAT)]))
    assert graph_builder.junction_count(line_only) == 0

    crossing, _ = _build(
        _feature([(LON, LAT), (LON + 0.02, LAT)], feature_id="oprhp_trails:1"),
        _feature(
            [(LON + 0.01, LAT - 0.01), (LON + 0.01, LAT + 0.01)],
            feature_id="oprhp_trails:2",
        ),
    )
    assert graph_builder.junction_count(crossing) == 1


def test_connected_components_counts_islands():
    far_apart, _ = _build(
        _feature([(LON, LAT), (LON + 0.01, LAT)], feature_id="oprhp_trails:1"),
        _feature([(LON, LAT + 0.2), (LON + 0.01, LAT + 0.2)], feature_id="oprhp_trails:2"),
    )
    assert graph_builder.connected_components(far_apart) == 2
