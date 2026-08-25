"""Tests for export_network_elevation.py - per-edge climb for the junction
graph (#1011).

Small synthetic fixtures throughout: tiny real GeoTIFFs written by test code,
and graphs of two or three hand-placed edges - never the real 3DEP dataset or a
fetched trail layer (TESTING.md).

The DEM here is a RAMP rather than the flat fixture test_export_elevation.py
mostly uses, because a flat tile cannot tell a working gain sum from one that
returns zero for the wrong reason. A monotonic ramp has an analytically known
answer - `cumulative_gain` banks the whole rise of an unreversed climb - so
every assertion below is against arithmetic rather than against a golden number
somebody recorded once.
"""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

import export_network_elevation as network_elevation
from lib.elevation_gain import METERS_PER_FOOT

# A patch of ground inside the network's ring, in NY. Nothing is fetched for
# it; the coordinates only have to be somewhere EPSG:5070 is valid.
WEST, SOUTH, EAST, NORTH = -74.20, 41.20, -74.00, 41.40


def _write_ramp_tile(path, *, bounds=(WEST, SOUTH, EAST, NORTH), size=400, base=100.0, per_column=1.0, nodata=-9999.0):
    """A real GeoTIFF whose elevation rises linearly west to east.

    Column `c` reads `base + c * per_column` metres, so an edge running east
    climbs a known amount and the same edge reversed descends it. Written to
    real bytes via rasterio rather than committed as an opaque binary.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    transform = from_bounds(*bounds, size, size)
    profile = {
        "driver": "GTiff",
        "height": size,
        "width": size,
        "count": 1,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": nodata,
    }
    ramp = np.tile((base + np.arange(size) * per_column).astype("float32"), (size, 1))
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(ramp[np.newaxis, :, :])
    return path


def _index_for(tmp_path, *tiles):
    """The {url, bounds} index index_elevation_tiles() reads, pointed at local
    fixture tiles (see test_export_elevation.py's equivalent)."""
    entries = []
    for tile in tiles:
        with rasterio.open(tile) as src:
            entries.append({"url": tile.as_posix(), "bounds": list(src.bounds)})
    out = tmp_path / "tile_index.json"
    out.write_text(json.dumps(entries))
    return out


def _sampler(index_path):
    return network_elevation.ElevationSampler(network_elevation.index_elevation_tiles(index_path))


def _graph(*sources):
    """A graph of N edges, each carrying only what this module reads."""
    return {
        "nodes": [[0.0, 0.0]] * (len(sources) + 1),
        "edges": [{"from": i, "to": i + 1, "source": source, "name": f"trail {i}"} for i, source in enumerate(sources)],
    }


def _elevation_at(lon, *, bounds=(WEST, SOUTH, EAST, NORTH), size=400, base=100.0, per_column=1.0):
    """What _write_ramp_tile put at this longitude, so a test can state its
    expectation as arithmetic rather than as a number read off a failure."""
    west, _south, east, _north = bounds
    column = int((lon - west) / (east - west) * size)
    return base + min(max(column, 0), size - 1) * per_column


class TestSamplePositions:
    def test_includes_both_ends(self):
        positions = network_elevation.sample_positions(100.0, interval_m=25.0)
        assert positions[0] == 0.0
        assert positions[-1] == 100.0

    def test_a_short_edge_still_gets_its_two_ends(self):
        # The case the docstring calls out: without this an edge shorter than
        # the interval would be measured from a single point and read as flat.
        positions = network_elevation.sample_positions(4.0, interval_m=25.0)
        assert positions == [0.0, 4.0]

    def test_spacing_lands_near_the_interval_not_under_it(self):
        # round() rather than ceil(): a 30 m edge is one interval, not two.
        assert network_elevation.sample_positions(30.0, interval_m=25.0) == [0.0, 30.0]

    def test_a_degenerate_length_yields_one_point_rather_than_raising(self):
        assert network_elevation.sample_positions(0.0) == [0.0]


class TestEdgeClimb:
    def test_an_unmeasured_edge_is_none_and_never_zero(self):
        # The distinction the whole artifact turns on: "nobody measured this"
        # is not "this is flat".
        assert network_elevation.edge_climb([None, None, None]) is None

    def test_a_flat_edge_is_zero_and_not_none(self):
        assert network_elevation.edge_climb([100.0, 100.0, 100.0]) == [0, 0]

    def test_gain_and_loss_are_both_positive_numbers(self):
        # A hill up and back down: frame `1l` prints its own signs, so the
        # artifact carries magnitudes.
        climb = network_elevation.edge_climb([100.0, 200.0, 100.0])
        assert climb == [round(100 / METERS_PER_FOOT), round(100 / METERS_PER_FOOT)]

    def test_noise_below_the_dead_band_is_not_climbing(self):
        # Half a metre of jitter is what the dead band exists to drop - the
        # 17% over-count lib/elevation_gain.py's docstring measures.
        jitter = [100.0, 100.5, 100.0, 100.5, 100.0, 100.5]
        assert network_elevation.edge_climb(jitter) == [0, 0]

    def test_a_partially_covered_edge_is_measured_over_the_runs_it_has(self):
        # Under-counts by whatever happened inside the gap, which is the
        # honest direction, and is what the manifest's `partial` count exists
        # to make visible.
        climb = network_elevation.edge_climb([100.0, 130.0, None, 200.0, 230.0])
        assert climb == [round(60 / METERS_PER_FOOT), 0]


class TestBuild:
    def test_an_edge_climbing_the_ramp_reports_the_ramp(self, tmp_path):
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            start_lon, end_lon = -74.15, -74.05
            geometry = [[[start_lon, 41.30], [end_lon, 41.30]]]
            climbs, _stats = network_elevation.build(_graph("oprhp_trails"), geometry, sampler)
        finally:
            sampler.close()

        expected_ft = (_elevation_at(end_lon) - _elevation_at(start_lon)) / METERS_PER_FOOT
        gain, loss = climbs[0]
        assert gain == pytest.approx(expected_ft, rel=0.02)
        assert loss == 0

    def test_the_same_edge_reversed_is_all_loss_and_no_gain(self, tmp_path):
        # Not a tautology: it is the check that `cumulative_loss`'s negation
        # is symmetric on real sampled ground, not just on hand-written lists.
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            geometry = [[[-74.05, 41.30], [-74.15, 41.30]]]
            climbs, _stats = network_elevation.build(_graph("oprhp_trails"), geometry, sampler)
        finally:
            sampler.close()

        gain, loss = climbs[0]
        expected_ft = (_elevation_at(-74.05) - _elevation_at(-74.15)) / METERS_PER_FOOT
        assert gain == 0
        assert loss == pytest.approx(expected_ft, rel=0.02)

    def test_climb_is_never_summed_across_a_node_join(self, tmp_path):
        """#559's failure, in the shape a junction graph would meet it.

        Two edges that share a node in the graph but sit at opposite ends of
        the ramp. Concatenating their samples into one profile would read the
        step between them - hundreds of feet across no ground at all - as
        climbing. Measured per edge, that step does not exist to be counted.
        """
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            geometry = [
                [[-74.19, 41.30], [-74.18, 41.30]],  # low end of the ramp
                [[-74.02, 41.30], [-74.01, 41.30]],  # high end, ~1,500 ft above
            ]
            climbs, _stats = network_elevation.build(_graph("oprhp_trails", "nynjtc_long_path"), geometry, sampler)
        finally:
            sampler.close()

        # Each edge climbs only its own 0.01 degrees of ramp. The ~1,500 ft
        # jump BETWEEN them appears in neither.
        #
        # Tolerance is TWO RAMP COLUMNS rather than a percentage, because the
        # error here is quantisation and not proportion: a sample lands in
        # whichever pixel contains it, so each end of a short edge can round to
        # a neighbouring column. On these 20-column edges one column is 5% of
        # the answer, which a relative tolerance would either fail on or have
        # to be loosened past the point of testing anything.
        one_column_ft = 1.0 / METERS_PER_FOOT
        one_hundredth_degree_ft = (_elevation_at(-74.18) - _elevation_at(-74.19)) / METERS_PER_FOOT
        assert climbs[0][0] == pytest.approx(one_hundredth_degree_ft, abs=2 * one_column_ft)
        assert climbs[1][0] == pytest.approx(one_hundredth_degree_ft, abs=2 * one_column_ft)
        gap_ft = (_elevation_at(-74.02) - _elevation_at(-74.18)) / METERS_PER_FOOT
        assert sum(climb[0] for climb in climbs) < gap_ft / 2

    def test_an_edge_no_tile_covers_publishes_null(self, tmp_path):
        # The failure mode a newly registered source arrives with: real trail,
        # no DEM cell. It must not read as flat ground.
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            geometry = [[[-70.00, 44.00], [-70.01, 44.00]]]
            climbs, stats = network_elevation.build(_graph("dec_catskills"), geometry, sampler)
        finally:
            sampler.close()

        assert climbs == [None]
        assert stats["dec_catskills"]["unmeasured"] == 1
        assert stats["dec_catskills"]["measured"] == 0

    def test_coverage_is_counted_per_source(self, tmp_path):
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            geometry = [
                [[-74.15, 41.30], [-74.05, 41.30]],  # covered
                [[-70.00, 44.00], [-70.01, 44.00]],  # not covered
            ]
            _climbs, stats = network_elevation.build(_graph("oprhp_trails", "dec_catskills"), geometry, sampler)
        finally:
            sampler.close()

        assert stats["oprhp_trails"]["measured"] == 1
        assert stats["dec_catskills"]["unmeasured"] == 1
        summary = network_elevation.coverage_summary(stats)
        assert summary == {
            "edges": 2,
            "measured": 1,
            "unmeasured": 1,
            "partially_covered": 0,
            "measured_pct": 50.0,
        }

    def test_a_geometry_count_mismatch_refuses_rather_than_guessing(self, tmp_path):
        """Edge 40's climb printed against edge 41's name is silent and wrong,
        which is why build_trail_graph.py binds the pair in one manifest. The
        same invariant, checked again at the point of writing."""
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            with pytest.raises(ValueError, match="refusing to guess"):
                network_elevation.build(_graph("a", "b"), [[[-74.1, 41.3], [-74.0, 41.3]]], sampler)
        finally:
            sampler.close()

    def test_an_empty_graph_is_an_empty_artifact_not_a_crash(self, tmp_path):
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            climbs, stats = network_elevation.build({"nodes": [], "edges": []}, [], sampler)
        finally:
            sampler.close()
        assert climbs == []
        assert network_elevation.coverage_summary(stats)["edges"] == 0


class TestWriteArtifact:
    def test_the_manifest_carries_the_edge_count_the_client_checks_alignment_against(self, tmp_path, monkeypatch):
        monkeypatch.setattr(network_elevation, "OUT_DIR", tmp_path)
        manifest = network_elevation.write_artifact(
            [[10, 5], None], {"oprhp_trails": {"edges": 2, "measured": 1, "partial": 0, "unmeasured": 1}}
        )
        assert manifest["edges"] == 2
        assert json.loads((tmp_path / network_elevation.ARTIFACT_NAME).read_text()) == [[10, 5], None]

    def test_the_manifest_says_out_loud_that_these_are_estimates(self, tmp_path, monkeypatch):
        # The maintainer's decision, 2026-08-25: ship the figure and frame it
        # as an estimate. A consumer should not have to infer that from a
        # docstring it cannot read.
        monkeypatch.setattr(network_elevation, "OUT_DIR", tmp_path)
        manifest = network_elevation.write_artifact([], {})
        assert manifest["estimate"] is True

    def test_the_licence_gate_travels_with_the_derivation(self, tmp_path, monkeypatch):
        # Climb measured along a steward's line is still that steward's data,
        # so publish.py must be able to apply the same reaches_hikers check it
        # applies to the lines themselves.
        monkeypatch.setattr(network_elevation, "OUT_DIR", tmp_path)
        sources = {"oprhp_trails": {"reaches_hikers": False}}
        manifest = network_elevation.write_artifact([None], {}, sources)
        assert manifest["sources"] == sources
