"""Behaviour of the sharded-vs-control build comparison (compare_shards.py).

The thing worth protecting here is the DISTINCTION the script exists to
draw: a difference at the cut and a difference deep inside a shard have
different causes and different futures, and a comparison that blurred them
would report "1,412 tiles differ" and settle nothing. Most of these tests
are about that reading rather than about counting differences.

Synthetic stats rather than a checked-in Planetiler run, per TESTING.md: a
hand-built TSV states what "a re-ranked city" looks like in the data, where
a captured blob would only assert that today's output equals today's output.
"""

import gzip

import pytest
from shapely.geometry import GeometryCollection, LineString, box

from compare_shards import (
    MAX_SEAM_DISTANCE,
    Difference,
    attribute,
    compare_hashes,
    compare_stats,
    distance_to_seam,
    merge_shard_stats,
    read_layer_stats,
    seam_distance_histogram,
    seam_geometry,
    seam_tiles,
    verdict,
)

COLUMNS = [
    "z",
    "x",
    "y",
    "hilbert",
    "archived_tile_bytes",
    "layer",
    "layer_bytes",
    "layer_features",
    "layer_geometries",
    "layer_attr_bytes",
    "layer_attr_keys",
    "layer_attr_values",
]


def write_stats(path, rows):
    """A gzipped layer-stats TSV shaped like Planetiler's, from
    (z, x, y, layer, bytes, features, geometries, attr_bytes, attr_values)."""
    lines = ["\t".join(COLUMNS)]
    for z, x, y, layer, nbytes, features, geometries, attr_bytes, attr_values in rows:
        lines.append(
            "\t".join(str(v) for v in [z, x, y, 0, nbytes, layer, nbytes, features, geometries, attr_bytes, 3, attr_values])
        )
    with gzip.open(path, "wt") as f:
        f.write("\n".join(lines) + "\n")
    return path


def stats_for(tmp_path, name, rows):
    return read_layer_stats(write_stats(tmp_path / name, rows))


def test_layer_stats_are_read_by_column_name_not_position(tmp_path):
    path = tmp_path / "shuffled.tsv.gz"
    reordered = [
        "layer",
        "layer_features",
        "z",
        "x",
        "y",
        "layer_bytes",
        "layer_geometries",
        "layer_attr_bytes",
        "layer_attr_values",
    ]
    with gzip.open(path, "wt") as f:
        f.write("\t".join(reordered) + "\n")
        f.write("\t".join(["water", "7", "14", "100", "200", "512", "9", "48", "5"]) + "\n")

    stats = read_layer_stats(path)

    assert stats[(14, 100, 200)]["water"]["layer_features"] == 7
    assert stats[(14, 100, 200)]["water"]["layer_bytes"] == 512


def test_reading_stats_fails_loudly_when_planetiler_stops_emitting_a_compared_column(tmp_path):
    path = tmp_path / "old.tsv.gz"
    with gzip.open(path, "wt") as f:
        f.write("z\tx\ty\tlayer\tlayer_bytes\n14\t1\t1\twater\t10\n")

    with pytest.raises(SystemExit, match="layer_features"):
        read_layer_stats(path)


def test_planetilers_per_tile_summary_row_is_not_treated_as_a_layer(tmp_path):
    path = tmp_path / "with-summary.tsv.gz"
    with gzip.open(path, "wt") as f:
        f.write("\t".join(COLUMNS) + "\n")
        f.write("\t".join(["14", "1", "1", "0", "900", "", "900", "0", "0", "0", "0", "0"]) + "\n")
        f.write("\t".join(["14", "1", "1", "0", "900", "water", "900", "4", "4", "40", "3", "6"]) + "\n")

    assert set(read_layer_stats(path)[(14, 1, 1)]) == {"water"}


def test_a_recomputed_attribute_is_caught_even_though_the_feature_count_is_unchanged(tmp_path):
    """The failure mode BASEMAP.md flags: a city keeps its feature but gets a
    different `rank`. Comparing feature counts alone would call this clean."""
    control = stats_for(tmp_path, "c.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 9)])
    sharded = stats_for(tmp_path, "s.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 7)])

    differences = compare_stats(control, sharded)

    assert [(d.layer, d.metric, d.control, d.sharded) for d in differences] == [("place", "layer_attr_values", 9, 7)]


def test_identical_builds_produce_no_differences(tmp_path):
    rows = [(14, 10, 20, "place", 400, 3, 3, 60, 9), (14, 10, 21, "water", 900, 4, 4, 40, 6)]
    assert compare_stats(stats_for(tmp_path, "c.tsv.gz", rows), stats_for(tmp_path, "s.tsv.gz", rows)) == []


def test_a_tile_the_shards_never_produced_is_reported_as_missing_not_as_a_value_change(tmp_path):
    control = stats_for(tmp_path, "c.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 9)])
    sharded = stats_for(tmp_path, "s.tsv.gz", [])

    differences = compare_stats(control, sharded)

    assert [d.kind for d in differences] == ["missing-from-shards"]
    assert differences[0].tile == (14, 10, 20)


def test_a_tile_only_the_shards_produced_is_reported_as_extra(tmp_path):
    control = stats_for(tmp_path, "c.tsv.gz", [])
    sharded = stats_for(tmp_path, "s.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 9)])

    assert [d.kind for d in compare_stats(control, sharded)] == ["extra-in-shards"]


def test_a_layer_missing_from_one_side_is_reported_per_metric(tmp_path):
    control = stats_for(tmp_path, "c.tsv.gz", [(14, 1, 1, "place", 400, 3, 3, 60, 9), (14, 1, 1, "water", 900, 4, 4, 40, 6)])
    sharded = stats_for(tmp_path, "s.tsv.gz", [(14, 1, 1, "place", 400, 3, 3, 60, 9)])

    differences = compare_stats(control, sharded)

    assert {d.layer for d in differences} == {"water"}
    assert all(d.sharded is None for d in differences)


def test_shards_that_both_wrote_a_tile_are_reported_as_overlapping(tmp_path):
    """The design's claim is that shards are disjoint, which is what makes
    combining them a concatenation. A tile two shards both produced is that
    claim failing, so it is surfaced rather than silently resolved."""
    a = stats_for(tmp_path, "a.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 9)])
    b = stats_for(tmp_path, "b.tsv.gz", [(14, 10, 20, "place", 111, 1, 1, 10, 2)])

    merged, overlaps = merge_shard_stats([a, b])

    assert overlaps == {(14, 10, 20)}
    assert merged[(14, 10, 20)]["place"]["layer_bytes"] == 400


def test_disjoint_shards_merge_without_overlap(tmp_path):
    a = stats_for(tmp_path, "a.tsv.gz", [(14, 10, 20, "place", 400, 3, 3, 60, 9)])
    b = stats_for(tmp_path, "b.tsv.gz", [(14, 11, 20, "place", 111, 1, 1, 10, 2)])

    merged, overlaps = merge_shard_stats([a, b])

    assert overlaps == set()
    assert set(merged) == {(14, 10, 20), (14, 11, 20)}


def test_byte_comparison_only_judges_tiles_both_builds_produced():
    """Presence is compare_stats()' finding. Hashes answer the narrower
    question layer stats cannot: same size, different bytes."""
    control = {(14, 1, 1): "aa", (14, 2, 2): "bb", (14, 3, 3): "cc"}
    sharded = {(14, 1, 1): "aa", (14, 2, 2): "ZZ"}

    assert compare_hashes(control, sharded) == [(14, 2, 2)]


def test_seam_tiles_are_the_ones_the_cut_passes_through():
    seam = LineString([(1_000_000, 1_000_000), (1_000_000, 2_000_000)])

    assert seam_tiles(seam, 2) == {(2, 1)}


def test_a_tile_on_the_cut_is_zero_tiles_away():
    assert distance_to_seam((14, 5, 5), {(5, 5)}) == 0


def test_distance_is_measured_ring_by_ring_outward():
    assert distance_to_seam((14, 7, 5), {(5, 5)}) == 2
    assert distance_to_seam((14, 6, 6), {(5, 5)}) == 1


def test_a_tile_far_from_the_cut_reports_no_distance_rather_than_a_huge_one():
    """None is what the histogram prints as '>8' and what the verdict counts
    as not-seam-local; an unbounded search would cost more and say the same
    thing."""
    assert distance_to_seam((14, 5 + MAX_SEAM_DISTANCE + 1, 5), {(5, 5)}) is None


def test_the_histogram_uses_each_tiles_own_zoom():
    """Seam tiles at z13 do not describe where a z14 tile sits, so a tile is
    measured against the cut at its own zoom or not at all."""
    histogram = seam_distance_histogram([(14, 5, 5), (13, 5, 5)], {14: {(5, 5)}})

    assert histogram[0] == 1
    assert histogram[None] == 1


def test_no_differences_reads_as_lossless():
    assert verdict(seam_distance_histogram([], {})).startswith("LOSSLESS")


def test_differences_hugging_the_cut_read_as_a_padding_problem():
    histogram = seam_distance_histogram([(14, 5, 5), (14, 6, 5)], {14: {(5, 5)}})

    assert verdict(histogram, padding_tiles=2).startswith("SEAM-LOCAL")


def test_one_difference_deep_inside_a_shard_overrides_a_mostly_clean_histogram():
    """The finding that matters is rare by construction - a single tile far
    from the cut is the evidence that padding is not the explanation, and it
    must not be averaged away by the hundreds of seam tiles around it."""
    tiles = [(14, 5, 5)] * 0 + [(14, 5 + d, 5) for d in (0, 1, 1, 2)] + [(14, 40, 40)]
    histogram = seam_distance_histogram(tiles, {14: {(5, 5)}})

    assert verdict(histogram, padding_tiles=2).startswith("NOT SEAM-LOCAL")


def test_the_padding_threshold_is_what_decides_seam_local_not_a_baked_in_constant():
    histogram = seam_distance_histogram([(14, 8, 5)], {14: {(5, 5)}})

    assert verdict(histogram, padding_tiles=2).startswith("NOT SEAM-LOCAL")
    assert verdict(histogram, padding_tiles=3).startswith("SEAM-LOCAL")


def test_differences_sort_stably_so_two_runs_can_be_diffed(tmp_path):
    control = stats_for(tmp_path, "c.tsv.gz", [(14, 2, 2, "water", 900, 4, 4, 40, 6), (14, 1, 1, "place", 400, 3, 3, 60, 9)])
    sharded = stats_for(tmp_path, "s.tsv.gz", [])

    assert [d.tile for d in compare_stats(control, sharded)] == [(14, 1, 1), (14, 2, 2)]


def test_a_difference_knows_which_side_it_came_from():
    assert Difference((14, 1, 1), "place", "layer_features", 3, 2).kind == "value"
    assert Difference((14, 1, 1), None, None, 1, None).kind == "missing-from-shards"
    assert Difference((14, 1, 1), None, None, None, 1).kind == "extra-in-shards"


# Geofabrik's .poly shapes carry a margin so features near a state line
# arrive whole in both extracts, which means neighbouring shards OVERLAP
# rather than abut. The first run that got far enough to compare died on
# that: two overlapping polygons share no boundary line, their outlines meet
# at points, and a point-set's boundary is empty - whose bounds are NaN.


def test_an_overlap_band_is_used_as_an_area_not_reduced_to_its_outline():
    """Converting the band to its boundary would measure the wrong thing:
    the tiles at the cut are the ones the band COVERS, since those are the
    tiles both shards were asked to produce."""
    band = box(0, 0, 1, 10)

    assert seam_geometry(band).equals(band)


def test_a_line_seam_is_passed_through_unchanged():
    line = LineString([(5, 0), (5, 10)])

    assert seam_geometry(line).equals(line)


def test_an_empty_seam_is_refused_where_it_can_still_be_named():
    """An empty geometry's bounds are NaN, which otherwise surfaces three
    frames away as `cannot convert float NaN to integer` - a stack trace that
    mentions neither the seam nor the file it came from."""
    with pytest.raises(SystemExit, match="seam geometry is empty"):
        seam_geometry(GeometryCollection())


def test_differences_on_tiles_two_shards_both_produced_are_kept_separate():
    """A tile both shards wrote is one where first-wins picked the survivor,
    so it differs from the control by construction. Counting it against the
    build would indict Planetiler for the merge rule's choice."""
    differing = [(4, 1, 1), (14, 100, 200), (14, 100, 201)]
    overlaps = {(4, 1, 1)}

    single, shared = attribute(differing, overlaps)

    assert shared == [(4, 1, 1)]
    assert single == [(14, 100, 200), (14, 100, 201)]


def test_with_no_overlaps_every_difference_is_the_builds_own():
    differing = [(14, 1, 1), (14, 2, 2)]

    single, shared = attribute(differing, set())

    assert shared == []
    assert single == differing
