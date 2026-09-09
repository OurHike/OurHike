"""Tests for spike_poi_trail_offset.py (#1101).

The measurement half needs the live artifacts and is not run here. What IS
tested is the arithmetic a reader would otherwise have to trust: that the
summary reports a DISTRIBUTION rather than a mean, that the threshold counts
are the ones `OFF_TRAIL_THRESHOLD_FT` names, and that the two distances are
taken against the two different sets of geometry the report claims.

The spike's own code is throwaway; these keep its numbers honest while it is
being read, which is the only time a spike's numbers matter.
"""

from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree

import spike_poi_trail_offset as offset

FOOT = offset.METERS_PER_FOOT


class TestSummarise:
    def test_an_empty_set_reports_a_count_and_claims_nothing_else(self):
        # Never a zero median: "nothing was measured" and "everything measured
        # zero" are the distinction this whole spike exists to keep.
        assert offset.summarise([]) == {"n": 0}

    def test_the_median_is_the_middle_not_the_mean(self):
        # The tail is the point. One waypoint a mile out must not drag the
        # figure a card would be designed against.
        values = [10.0, 20.0, 30.0, 40.0, 5000.0]
        assert offset.summarise(values)["median"] == 30.0

    def test_the_threshold_count_is_the_clients_own_ninety_feet(self):
        # 90 was read from wrongWay.ts before that file (and the wrong-way
        # alert it belonged to) was removed (#93, #308). Fixed at that value
        # now rather than re-derived - see the constant's own comment.
        assert offset.OFF_TRAIL_THRESHOLD_FT == 90
        values = [89.0, 90.0, 91.0, 1000.0]

        summary = offset.summarise(values)

        # 90 itself is NOT past the threshold - `>`, not `>=`.
        assert summary["past_threshold_pct"] == pytest.approx(50.0)

    def test_the_twenty_foot_share_is_the_mock_ups_number(self):
        """#941 drew `20 ft off trail`. The share of waypoints that actually
        sit within it is the figure that says whether that was typical."""
        summary = offset.summarise([5.0, 20.0, 21.0, 400.0])
        assert summary["under_20ft_pct"] == pytest.approx(50.0)

    def test_percentiles_do_not_run_off_the_end(self):
        # A one-element set has to answer p95 as that element rather than
        # raising, or a sparse poi_type takes the whole run down.
        summary = offset.summarise([42.0])
        assert summary["p95"] == 42.0 and summary["max"] == 42.0


class TestOffsetsFeet:
    def test_distance_is_reported_in_feet(self):
        line = LineString([(0, 0), (0, 100)])
        tree = STRtree([line])

        # 30.48 m due east of the line is exactly 100 ft.
        feet = offset.offsets_feet([Point(30.48, 50)], tree, [line])

        assert feet == [pytest.approx(100.0)]

    def test_the_nearest_geometry_wins_not_the_first(self):
        """STRtree.nearest returns an INDEX, so the distance still has to be
        taken against that geometry. Getting this wrong would report every
        waypoint's distance to whichever line happened to be first."""
        far = LineString([(1000, 0), (1000, 100)])
        near = LineString([(0, 0), (0, 100)])
        tree = STRtree([far, near])

        feet = offset.offsets_feet([Point(FOOT, 50)], tree, [far, near])

        assert feet == [pytest.approx(1.0)]


class TestLoadTrails:
    def test_the_centerline_is_split_out_from_the_side_trails(self, tmp_path):
        """The split the whole report rests on: `source` is what separates the
        A.T. from the blue-blazed trails beside it, and measuring against the
        wrong set would report a bushwhack where there is a path."""
        path = tmp_path / "trails.geojson"
        path.write_text(
            '{"type":"FeatureCollection","features":['
            '{"type":"Feature","properties":{"source":"centerline"},'
            '"geometry":{"type":"LineString","coordinates":[[-84.0,34.6],[-84.0,34.7]]}},'
            '{"type":"Feature","properties":{"source":"side_trails"},'
            '"geometry":{"type":"LineString","coordinates":[[-83.9,34.6],[-83.9,34.7]]}}]}',
            encoding="utf-8",
        )

        centerline, every = offset.load_trails(path)

        assert len(centerline) == 1
        assert len(every) == 2


class TestFarRecords:
    def _tree(self):
        line = LineString([(0, -100000), (0, 100000)])
        return line, STRtree([line])

    def _feature(self, x_meters, mile):
        return {
            "properties": {"mile": mile, "name": "somewhere"},
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
        }

    def test_a_waypoint_with_no_mile_is_never_listed(self, monkeypatch):
        """#1016 already established those are not on the A.T., so their
        distance to it is not a number about them."""
        line, tree = self._tree()
        monkeypatch.setattr(offset, "shapely_transform", lambda _project, geometry: Point(1_000_000, 0))

        assert offset.far_records([self._feature(0, None)], None, tree, [line], "water") == []

    def test_a_waypoint_inside_the_cutoff_is_not_listed(self, monkeypatch):
        line, tree = self._tree()
        monkeypatch.setattr(offset, "shapely_transform", lambda _project, geometry: Point(10.0, 0))

        assert offset.far_records([self._feature(0, 12.3)], None, tree, [line], "water") == []

    def test_a_far_waypoint_carries_its_distance_type_and_properties(self, monkeypatch):
        line, tree = self._tree()
        monkeypatch.setattr(offset, "shapely_transform", lambda _project, geometry: Point(5280 * FOOT * 2, 0))

        [(feet, poi_type, props)] = offset.far_records([self._feature(0, 12.3)], None, tree, [line], "shelter")

        assert feet == pytest.approx(5280 * 2)
        assert poi_type == "shelter"
        assert props["mile"] == 12.3
