"""Tests for export_network_profile.py - the dense per-edge profile a chart
draws a followed day hike from (#1045).

Small synthetic fixtures throughout: tiny real GeoTIFFs written by test code,
and graphs of two or three hand-placed edges - never the real 3DEP dataset or a
fetched trail layer (TESTING.md).

The DEM is the same RAMP test_export_network_elevation.py uses, and for the
same reason: a flat tile cannot tell a working profile from one that returns
the same number for the wrong reason. A ramp has an analytically known answer,
so the assertions below are against arithmetic rather than against a golden
number somebody recorded once.

TestTheSeamRule is the block that matters. The other classes check that the
artifact says what it means; that one checks that the thing the artifact exists
to prevent is still prevented - #559's ~36,800 ft of climbing nobody did,
arriving in a new file by way of a `.flat()` call.
"""

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds

import export_network_elevation as network_elevation
import export_network_profile as network_profile
from lib.elevation_gain import DEFAULT_THRESHOLD_FT, METERS_PER_FOOT, cumulative_gain_over_gaps, gain_over_profile

# A patch of ground inside the network's ring, in NY. Nothing is fetched for
# it; the coordinates only have to be somewhere EPSG:5070 is valid.
WEST, SOUTH, EAST, NORTH = -74.20, 41.20, -74.00, 41.40


def _write_ramp_tile(path, *, bounds=(WEST, SOUTH, EAST, NORTH), size=400, base=100.0, per_column=1.0, nodata=-9999.0):
    """A real GeoTIFF whose elevation rises linearly west to east.

    Column `c` reads `base + c * per_column` metres, so an edge running east
    climbs a known amount and the same edge reversed descends it.
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
    fixture tiles."""
    entries = []
    for tile in tiles:
        with rasterio.open(tile) as src:
            entries.append({"url": tile.as_posix(), "bounds": list(src.bounds)})
    out = tmp_path / "tile_index.json"
    out.write_text(json.dumps(entries))
    return out


def _sampler(index_path):
    return network_profile.ElevationSampler(network_profile.index_elevation_tiles(index_path))


def _graph(edges):
    """A graph from (from_node, to_node, source) triples, carrying only what
    these modules read."""
    highest = max((max(a, b) for a, b, _ in edges), default=0)
    return {
        "nodes": [[0.0, 0.0]] * (highest + 1),
        "edges": [{"from": a, "to": b, "source": source, "name": f"trail {i}"} for i, (a, b, source) in enumerate(edges)],
    }


def _elevation_at(lon, *, bounds=(WEST, SOUTH, EAST, NORTH), size=400, base=100.0, per_column=1.0):
    """What _write_ramp_tile put at this longitude, so a test can state its
    expectation as arithmetic rather than as a number read off a failure."""
    west, _south, east, _north = bounds
    column = int((lon - west) / (east - west) * size)
    return base + min(max(column, 0), size - 1) * per_column


def _built(tmp_path, geometry, edges):
    tile = _write_ramp_tile(tmp_path / "ramp.tif")
    sampler = _sampler(_index_for(tmp_path, tile))
    try:
        return network_profile.build(_graph(edges), geometry, sampler)
    finally:
        sampler.close()


class TestEdgeProfile:
    def test_an_edge_the_dem_never_covers_is_none_and_not_a_list_of_nulls(self):
        # The same claim `edge_climb` makes with its own None, in the same
        # place: nobody measured this edge. A consumer asking "is this edge
        # known?" gets one answer from both artifacts.
        assert network_profile.edge_profile([None, None, None]) is None

    def test_one_hole_keeps_its_place_on_the_axis(self):
        # Dropping it would silently rescale every sample after it, because
        # the distance axis is derived from the list's own length. A shape
        # that misplaces a climb it did measure is worse than one with a gap.
        profile = network_profile.edge_profile([100.0, None, 200.0])
        assert profile is not None
        assert len(profile) == 3
        assert profile[1] is None

    def test_samples_are_whole_feet(self):
        # Metres in, feet out, no decimals - 3DEP's sample-to-sample error is
        # ~0.5 m and a tenth of a foot is 3 cm.
        profile = network_profile.edge_profile([100.0, 200.0])
        assert profile == [round(100 / METERS_PER_FOOT), round(200 / METERS_PER_FOOT)]
        assert all(isinstance(value, int) for value in profile)

    def test_a_flat_edge_is_a_flat_profile_and_never_none(self):
        assert network_profile.edge_profile([100.0, 100.0, 100.0]) == [328, 328, 328]


class TestBuild:
    def test_an_edge_climbing_the_ramp_reports_the_ramp(self, tmp_path):
        start_lon, end_lon = -74.15, -74.05
        geometry = [[[start_lon, 41.30], [end_lon, 41.30]]]
        profiles, _stats, _seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails")])

        profile = profiles[0]
        assert profile[0] == pytest.approx(_elevation_at(start_lon) / METERS_PER_FOOT, abs=4)
        assert profile[-1] == pytest.approx(_elevation_at(end_lon) / METERS_PER_FOOT, abs=4)
        # Monotone, because the ground is. This is what two scalars cannot say
        # and is the whole reason the artifact exists.
        assert profile == sorted(profile)

    def test_a_profile_starts_at_zero_metres_and_ends_at_the_edges_full_length(self, tmp_path):
        """The count is the client's ONLY source of spacing, so it has to be
        the sampler's count and both ends have to be in it."""
        geometry = [[[-74.15, 41.30], [-74.05, 41.30]]]
        to_projected, to_geographic = network_profile._transformers()
        expected = len(network_elevation.edge_sample_points(geometry[0], to_projected, to_geographic))

        profiles, _stats, _seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails")])

        assert len(profiles[0]) == expected
        assert expected > 2  # a ~8 km edge at 25 m is not two endpoints

    def test_a_short_edge_still_gets_both_of_its_ends(self, tmp_path):
        # 28.8% of the live graph's edges are shorter than the interval
        # (measured 2026-08-27). Sampled from one point they would all read as
        # flat ground.
        geometry = [[[-74.1000, 41.30], [-74.09995, 41.30]]]
        profiles, _stats, _seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails")])
        assert len(profiles[0]) == 2

    def test_an_edge_no_tile_covers_publishes_null(self, tmp_path):
        # The failure mode a newly registered source arrives with: real trail,
        # no DEM cell. It must never read as flat ground.
        geometry = [[[-70.00, 44.00], [-70.01, 44.00]]]
        profiles, stats, _seam = _built(tmp_path, geometry, [(0, 1, "dec_catskills")])

        assert profiles == [None]
        assert stats["dec_catskills"]["unmeasured"] == 1
        assert stats["dec_catskills"]["measured"] == 0

    def test_an_edge_that_runs_off_the_dem_is_measured_and_counted_partial(self, tmp_path):
        """Half on the tile, half past its eastern edge.

        Measured over the samples it has, with the holes left in place - and
        counted as `partial` so the manifest says how much of the network is
        in that state rather than leaving a client to discover it a route at a
        time.
        """
        geometry = [[[-74.05, 41.30], [-73.95, 41.30]]]
        profiles, stats, _seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails")])

        profile = profiles[0]
        assert profile is not None
        assert any(value is None for value in profile)
        assert any(value is not None for value in profile)
        assert stats["oprhp_trails"] == {
            "edges": 1,
            "measured": 1,
            "partial": 1,
            "unmeasured": 0,
            "samples": len(profile),
            "null_samples": sum(1 for value in profile if value is None),
        }

    def test_coverage_and_samples_are_counted_per_source(self, tmp_path):
        geometry = [
            [[-74.15, 41.30], [-74.05, 41.30]],  # covered
            [[-70.00, 44.00], [-70.01, 44.00]],  # not covered
        ]
        _profiles, stats, _seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails"), (2, 3, "dec_catskills")])

        assert stats["oprhp_trails"]["measured"] == 1
        assert stats["oprhp_trails"]["null_samples"] == 0
        assert stats["dec_catskills"]["unmeasured"] == 1
        assert stats["dec_catskills"]["null_samples"] == stats["dec_catskills"]["samples"]

        summary = network_profile.coverage_summary(stats)
        assert summary["edges"] == 2
        assert summary["measured"] == 1
        assert summary["unmeasured"] == 1
        assert summary["samples"] == stats["oprhp_trails"]["samples"] + stats["dec_catskills"]["samples"]

    def test_a_geometry_count_mismatch_refuses_rather_than_guessing(self, tmp_path):
        """Edge 40's terrain drawn under edge 41's name is silent and wrong,
        which is why build_trail_graph.py binds the pair in one manifest."""
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            with pytest.raises(ValueError, match="refusing to guess"):
                network_profile.build(_graph([(0, 1, "a"), (1, 2, "b")]), [[[-74.1, 41.3], [-74.0, 41.3]]], sampler)
        finally:
            sampler.close()

    def test_an_empty_graph_is_an_empty_artifact_not_a_crash(self, tmp_path):
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            profiles, stats, seam = network_profile.build({"nodes": [], "edges": []}, [], sampler)
        finally:
            sampler.close()
        assert profiles == []
        assert network_profile.coverage_summary(stats)["edges"] == 0
        assert seam["shared_nodes"] == 0


class TestTheSeamRule:
    """#559's failure, in the shape a dense per-edge artifact would meet it.

    Two edges that share a graph node but sit at opposite ends of the ramp -
    `ENDPOINT_SNAP_M = 8.0` is what makes that representable, and on the live
    artifacts 2,451 of 21,149 shared nodes really do have their incident ends
    at different coordinates (measured 2026-08-27). Concatenating their samples
    into one route profile reads the step between them as climbing.
    """

    SEAM_GEOMETRY = [
        [[-74.19, 41.30], [-74.18, 41.30]],  # low end of the ramp
        [[-74.02, 41.30], [-74.01, 41.30]],  # high end, ~1,500 ft above
    ]
    SEAM_EDGES = [(0, 1, "oprhp_trails"), (1, 2, "nynjtc_long_path")]

    def test_the_artifact_holds_one_array_per_edge_and_no_concatenation(self, tmp_path):
        # The structural half of the rule: there is nothing in the file to sum
        # by accident. Flattening is something a consumer has to decide to do.
        profiles, _stats, _seam = _built(tmp_path, self.SEAM_GEOMETRY, self.SEAM_EDGES)
        assert len(profiles) == 2
        assert all(isinstance(profile, list) for profile in profiles)

    def test_a_flat_concatenation_re_creates_the_phantom_climb(self, tmp_path):
        """What happens if somebody ignores the rule, in feet.

        Not a hypothetical: this is exactly what a route ribbon does if it
        builds its samples with `profiles.flat()` and hands them to a gain sum.
        """
        profiles, _stats, _seam = _built(tmp_path, self.SEAM_GEOMETRY, self.SEAM_EDGES)

        per_edge = sum(cumulative_gain_over_gaps(profile, DEFAULT_THRESHOLD_FT) for profile in profiles)
        flattened = cumulative_gain_over_gaps([value for profile in profiles for value in profile], DEFAULT_THRESHOLD_FT)

        step_ft = (_elevation_at(-74.02) - _elevation_at(-74.18)) / METERS_PER_FOOT
        # The step is ~1,500 ft of ground nobody walks. The honest sum does not
        # contain it; the flat one is almost entirely made of it.
        assert per_edge < step_ft / 2
        assert flattened > per_edge + step_ft / 2

    def test_the_documented_flattening_rule_does_not_re_create_it(self, tmp_path):
        """The rule this artifact publishes: a consumer flattening per-edge
        profiles writes `part_start: true` on the first sample of every edge.

        `lib/elevation_gain.py:profile_runs` already breaks a run there - the
        marker exists for export_elevation.py's 558 disconnected centerline
        pieces - so the correct behaviour needs no new mechanism on either side
        of the language boundary. This is that claim, run.
        """
        profiles, _stats, _seam = _built(tmp_path, self.SEAM_GEOMETRY, self.SEAM_EDGES)

        records = []
        for profile in profiles:
            for index, value in enumerate(profile):
                record = {"elevation_ft": value}
                if index == 0:
                    record["part_start"] = True
                records.append(record)

        per_edge = sum(cumulative_gain_over_gaps(profile, DEFAULT_THRESHOLD_FT) for profile in profiles)
        assert gain_over_profile(records, DEFAULT_THRESHOLD_FT) == pytest.approx(per_edge)

        # And the same records WITHOUT the markers are the bug, so the test is
        # about the markers rather than about the arithmetic being small.
        unmarked = [{"elevation_ft": record["elevation_ft"]} for record in records]
        assert gain_over_profile(unmarked, DEFAULT_THRESHOLD_FT) > per_edge

    def test_the_run_measures_its_own_seam_rather_than_asserting_it(self, tmp_path):
        _profiles, _stats, seam = _built(tmp_path, self.SEAM_GEOMETRY, self.SEAM_EDGES)

        assert seam["shared_nodes"] == 1
        # The two ends welded onto node 1 are at different coordinates, which
        # is the whole hazard: no coincidence, and a step far over the band.
        assert seam["coincident_ends"] == 0
        assert seam["steps_over_dead_band"] == 1
        assert seam["step_ft_max"] == pytest.approx((_elevation_at(-74.02) - _elevation_at(-74.18)) / METERS_PER_FOOT, rel=0.02)

    def test_two_edges_that_genuinely_meet_report_no_step(self, tmp_path):
        """88.41% of the live graph's shared nodes have every incident end at
        one published coordinate (measured 2026-08-27). The same lon/lat reads
        the same DEM pixel, so those joins have no step by construction - and
        the diagnostic has to be able to tell them apart from the welded ones,
        or its count means nothing."""
        geometry = [
            [[-74.15, 41.30], [-74.10, 41.30]],
            [[-74.10, 41.30], [-74.05, 41.30]],
        ]
        _profiles, _stats, seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails"), (1, 2, "oprhp_trails")])

        assert seam["shared_nodes"] == 1
        assert seam["coincident_ends"] == 1
        assert seam["nodes_with_a_step"] == 0
        assert seam["steps_over_dead_band"] == 0

    def test_an_unmeasured_edge_end_contributes_no_step(self, tmp_path):
        # One measured end cannot disagree with anything, and inventing a step
        # from a null would put a hazard figure in the manifest that no ground
        # supports.
        geometry = [
            [[-74.15, 41.30], [-74.10, 41.30]],  # covered
            [[-70.00, 44.00], [-70.01, 44.00]],  # not covered - profile is None
        ]
        _profiles, _stats, seam = _built(tmp_path, geometry, [(0, 1, "oprhp_trails"), (1, 2, "dec_catskills")])

        assert seam["shared_nodes"] == 1
        assert seam["measured_nodes"] == 0
        assert seam["step_ft_max"] == 0.0

    def test_the_profile_and_the_two_scalar_artifact_are_sampled_alike(self, tmp_path):
        """The two files describe one walk, so they have to describe the same
        points. They share `edge_sample_points`, and this is that sharing
        checked end to end rather than assumed from an import.
        """
        geometry = [[[-74.15, 41.30], [-74.05, 41.30]], [[-74.05, 41.31], [-74.12, 41.31]]]
        edges = [(0, 1, "oprhp_trails"), (1, 2, "oprhp_trails")]
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        sampler = _sampler(_index_for(tmp_path, tile))
        try:
            profiles, _stats, _seam = network_profile.build(_graph(edges), geometry, sampler)
            climbs, _stats = network_elevation.build(_graph(edges), geometry, sampler)
        finally:
            sampler.close()

        to_projected, to_geographic = network_profile._transformers()
        expected = [len(network_elevation.edge_sample_points(edge, to_projected, to_geographic)) for edge in geometry]
        assert [len(profile) for profile in profiles] == expected

        for profile, climb in zip(profiles, climbs):
            gain = cumulative_gain_over_gaps(profile, DEFAULT_THRESHOLD_FT)
            # Recomputing from the published WHOLE FEET does not reproduce the
            # scalars exactly - measured on the real A.T. profile, whole-foot
            # rounding moves a six-mile window's ascent by a median 1.1 ft and
            # up to 30.5 ft. It agrees to within the dead band, which is the
            # most that can honestly be claimed, and is the second reason the
            # scalars stay the sanctioned total.
            assert gain == pytest.approx(climb[0], abs=DEFAULT_THRESHOLD_FT)


class TestWriteArtifact:
    def test_the_manifest_carries_the_edge_count_the_client_checks_alignment_against(self, tmp_path, monkeypatch):
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        manifest = network_profile.write_artifact([[10, 12], None], {}, {})

        assert manifest["edges"] == 2
        assert json.loads((tmp_path / network_profile.ARTIFACT_NAME).read_text()) == [[10, 12], None]

    def test_the_edge_count_is_the_files_own_length_and_not_the_coverage_total(self, tmp_path, monkeypatch):
        """The two are different questions, and only one of them is the
        alignment check. Coverage counts what the sources accounted for; the
        client checks the number of ENTRIES against the graph it holds, so a
        run whose stats disagree with its array must publish the array's
        length or the mismatch it exists to catch is papered over."""
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        stats = {"oprhp_trails": {"edges": 99, "measured": 99, "partial": 0, "unmeasured": 0, "samples": 0, "null_samples": 0}}

        manifest = network_profile.write_artifact([[10, 12], None], stats, {})

        assert manifest["edges"] == 2

    def test_the_manifest_names_where_a_routes_climb_comes_from(self, tmp_path, monkeypatch):
        # The seam rule as a field rather than as prose: a consumer that never
        # reads the module still finds out that summing this file is not how
        # a walk gets priced.
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        manifest = network_profile.write_artifact([], {}, {})

        assert manifest["route_gain_source"] == "trail_graph_elevation.json"
        assert manifest["sample_interval_m"] == network_profile.SAMPLE_INTERVAL_METERS

    def test_the_manifest_says_out_loud_that_these_are_estimates(self, tmp_path, monkeypatch):
        # No published gain figure exists for any NYNJTC or OPRHP trail, so the
        # dead band checked on the A.T. arrives on this ground unchecked. A
        # consumer should not have to infer that from a docstring.
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        assert network_profile.write_artifact([], {}, {})["estimate"] is True

    def test_the_manifest_carries_the_seam_measurement(self, tmp_path, monkeypatch):
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        seam = {"shared_nodes": 3, "coincident_ends": 2, "steps_over_dead_band": 1}
        assert network_profile.write_artifact([], {}, seam)["seam"] == seam

    def test_the_licence_gate_travels_with_the_derivation(self, tmp_path, monkeypatch):
        # A profile measured along a steward's line is still that steward's
        # data, so publish.py must be able to apply the same reaches_hikers
        # check it applies to the lines themselves.
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        sources = {"oprhp_trails": {"reaches_hikers": False}}

        assert network_profile.write_artifact([None], {}, {}, sources)["sources"] == sources

    def test_the_published_bytes_carry_no_decimals(self, tmp_path, monkeypatch):
        """Whole feet is a size decision as much as an honesty one - one
        decimal place measured 4.86 MB against 3.47 MB on the modelled
        artifact - so a float leaking in is a regression worth failing on."""
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)
        network_profile.write_artifact([[100, None, 102]], {}, {})

        body = (tmp_path / network_profile.ARTIFACT_NAME).read_text()
        assert "." not in body
        assert body == "[[100,null,102]]"


class TestMain:
    """The end-to-end path, because the three inputs arrive from three
    different scripts and the wiring between them is where a run breaks."""

    def _inputs(self, tmp_path):
        tile = _write_ramp_tile(tmp_path / "ramp.tif")
        index = _index_for(tmp_path, tile)
        graph = tmp_path / "trail_graph.json"
        graph.write_text(json.dumps(_graph([(0, 1, "oprhp_trails"), (1, 2, "oprhp_trails")])))
        geometry = tmp_path / "trail_graph_geometry.json"
        geometry.write_text(json.dumps([[[-74.15, 41.30], [-74.10, 41.30]], [[-74.10, 41.30], [-74.05, 41.30]]]))
        return graph, geometry, index

    def test_a_run_writes_an_aligned_artifact_and_carries_the_licence_gate_forward(self, tmp_path, monkeypatch):
        graph, geometry, index = self._inputs(tmp_path)
        # The graph manifest is where `sources` comes from - publish.py holds
        # this artifact back on exactly that block, so a run that dropped it
        # would publish terrain whose licence nobody had checked.
        (tmp_path / "trail_graph_manifest.json").write_text(json.dumps({"sources": {"oprhp_trails": {"reaches_hikers": False}}}))
        monkeypatch.setattr(network_profile, "IN_DIR", tmp_path)
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)

        manifest = network_profile.main(["--graph", str(graph), "--geometry", str(geometry), "--tile-index", str(index)])

        assert manifest["edges"] == 2
        assert manifest["sources"] == {"oprhp_trails": {"reaches_hikers": False}}
        published = json.loads((tmp_path / network_profile.ARTIFACT_NAME).read_text())
        assert len(published) == 2
        assert manifest["sha256"] == json.loads((tmp_path / network_profile.MANIFEST_NAME).read_text())["sha256"]

    def test_a_missing_input_says_which_script_to_run_rather_than_tracebacking(self, tmp_path, monkeypatch):
        graph, geometry, index = self._inputs(tmp_path)
        monkeypatch.setattr(network_profile, "IN_DIR", tmp_path)
        monkeypatch.setattr(network_profile, "OUT_DIR", tmp_path)

        with pytest.raises(SystemExit, match="build_trail_graph.py"):
            network_profile.main(
                ["--graph", str(tmp_path / "absent.json"), "--geometry", str(geometry), "--tile-index", str(index)]
            )
        with pytest.raises(SystemExit, match="fetch_elevation.py"):
            network_profile.main(
                ["--graph", str(graph), "--geometry", str(geometry), "--tile-index", str(tmp_path / "absent.json")]
            )
