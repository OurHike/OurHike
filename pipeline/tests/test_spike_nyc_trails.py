"""The pure halves of spike_nyc_trails.py (#771) — the filters and the
geometry summaries, against tiny synthetic fixtures. The measurement half
runs against real fetched data and is not re-run here; these keep the
arithmetic honest so the numbers in the issue mean what they say."""

from shapely.geometry import LineString

from spike_nyc_trails import (
    blaze_report,
    chain_report,
    junction_count,
    keep_hiking,
    named_groups,
    offset_stats,
)


def _feature(coords, **props):
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coords},
        "properties": props,
    }


def test_keep_hiking_applies_the_maintainer_filter_and_reports_drops():
    """Foot != 'Y' drops; Open AND Closed both ship (the maintainer's
    2026-08-18 call — Closed ships so the map can draw it barred); Proposed
    and blank drop, and every drop is counted — the run must say what it
    excluded rather than silently shrinking."""
    features = [
        _feature([(0, 0), (1, 1)], Foot="Y", Status="Open"),
        _feature([(0, 0), (1, 1)], Foot="N", Status="Open"),
        _feature([(0, 0), (1, 1)], Foot="Y", Status="Closed"),
        _feature([(0, 0), (1, 1)], Foot="Y", Status="Proposed"),
        _feature([(0, 0), (1, 1)], Foot="Y", Status=None),
    ]

    kept, dropped = keep_hiking(features)

    assert len(kept) == 2
    assert {(f["properties"]["Status"]) for f in kept} == {"Open", "Closed"}
    assert dropped["not foot travel (Foot != 'Y')"] == 1
    assert dropped["Status: Proposed"] == 1
    assert dropped["Status: None"] == 1


def test_chain_report_tells_a_walkable_trail_from_a_broken_one():
    """Two touching segments of one name merge to one chain; a third segment
    of the same name floating elsewhere makes it multi-part; a nameless
    segment lands in the unnamed count instead of pretending to be a trail."""
    features = [
        _feature([(0, 0), (1, 0)], Facility="Harriman State Park", Name="Ramapo-Dunderberg"),
        _feature([(1, 0), (2, 0)], Facility="Harriman State Park", Name="Ramapo-Dunderberg"),
        _feature([(0, 0), (0, 1)], Facility="Harriman State Park", Name="Broken Trail"),
        _feature([(5, 5), (6, 5)], Facility="Harriman State Park", Name="Broken Trail"),
        _feature([(9, 9), (9, 8)], Facility="Harriman State Park", Name=""),
    ]

    report = chain_report(named_groups(features))

    assert report["named_trails"] == 2
    assert report["single_chain"] == 1
    assert report["multi_part"] == {"Harriman State Park / Broken Trail": 2}
    assert report["unnamed_segments"] == 1


def test_junction_count_needs_two_different_names_at_one_point():
    """A trail meeting itself is not a junction; two named trails sharing an
    endpoint is one junction, counted once."""
    features = [
        _feature([(0, 0), (1, 1)], Name="A"),
        _feature([(1, 1), (2, 2)], Name="A"),
        _feature([(1, 1), (1, 0)], Name="B"),
    ]

    assert junction_count(features) == 1


def test_blaze_report_separates_the_client_palette_from_the_novel():
    features = [
        _feature([(0, 0), (1, 1)], Blaze="Blue", Map_Blaze="Blue"),
        _feature([(0, 0), (1, 1)], Blaze="Aqua", Map_Blaze="Blue"),
        _feature([(0, 0), (1, 1)], Blaze=None),
    ]

    report = blaze_report(features, {"Blue"})

    assert report["client_palette_hits"] == {"Blue": 1}
    assert report["novel_to_client"] == {"Aqua": 1}
    assert report["unblazed_or_unrecorded"] == 1
    assert report["blaze_vs_map_blaze_disagreements"] == (1, 2)


def test_offset_stats_measures_a_known_separation():
    """Two parallel lines 0.001 degrees apart at this latitude are ~111 m
    apart on the ground; the sampled median must land there, not at zero and
    not at the degree value — the projection is the point of the helper."""
    subject = [LineString([(-74.10, 41.25), (-74.09, 41.25)])]
    others = [LineString([(-74.10, 41.251), (-74.09, 41.251)])]

    stats = offset_stats(subject, others, stride_m=100.0)

    assert stats["samples"] >= 2
    assert 100 <= stats["median_m"] <= 120
    assert stats["share_within_150m"] == 1.0
