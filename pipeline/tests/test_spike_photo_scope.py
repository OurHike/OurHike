"""Tests for the pure half of spike_photo_scope.py.

The script's data half (read_photo_features, and main()'s whole path) is
hardcoded to real fetched files and is verified by running it, the same way
spike_day_planner.py's is - see TESTING.md's "what's intentionally
manual-only". What is tested here is everything that decides an ANSWER rather
than reads a file: the windowing, the two different samplings and why they
differ, the linear referencing that turns a POI into a mile, and the one
estimated number in the script.

A spike's findings are only worth as much as its arithmetic, which is the
whole reason a throwaway script has tests at all - and this one's arithmetic
is what a download ceiling would be chosen against.
"""

import json

import pytest
from shapely.geometry import LineString, Point

from spike_photo_scope import (
    METERS_PER_MILE,
    PhotoPoi,
    load_photo_sizes,
    locate,
    modelled_bytes,
    percentile,
    rolling_stats,
    window_bytes,
)


def poi(mile: float, card_bytes: int = 100_000, photo_count: int = 1) -> PhotoPoi:
    """A placed POI, for the tests that only care about mile and bytes."""
    return PhotoPoi(
        poi_id=f"atc_shelters:{mile}",
        name=f"mile {mile}",
        kind="atc_shelters",
        mile=mile,
        off_trail_mi=0.0,
        card_bytes=card_bytes,
        photo_count=photo_count,
    )


class TestWindowBytes:
    def test_sums_only_photos_inside_the_window(self):
        positions = [(1.0, 100), (5.0, 200), (12.0, 400)]
        assert window_bytes(positions, 0.0, 10.0) == 300

    def test_the_window_is_half_open_so_adjacent_windows_do_not_double_count(self):
        """A photo exactly on a boundary belongs to the window that starts
        there, not to both. Tiling the trail must total the corpus once."""
        positions = [(10.0, 500)]
        assert window_bytes(positions, 0.0, 10.0) == 0
        assert window_bytes(positions, 10.0, 10.0) == 500

    def test_an_empty_stretch_costs_nothing(self):
        assert window_bytes([(50.0, 100)], 0.0, 10.0) == 0


class TestPercentile:
    def test_returns_a_value_that_actually_occurs(self):
        """Nearest rank rather than interpolated, deliberately: these are sums
        over real windows, and a value between two of them describes a section
        that does not exist."""
        assert percentile([1.0, 2.0, 100.0], 0.5) == 2.0

    def test_handles_an_empty_sample(self):
        assert percentile([], 0.95) == 0.0

    def test_the_top_of_the_range_is_the_largest_value(self):
        assert percentile([5.0, 1.0, 3.0], 1.0) == 5.0


class TestRollingStats:
    def test_the_maximum_finds_a_cluster_that_uniform_sampling_would_straddle(self):
        """The reason the script samples twice.

        Three photos packed inside a tenth of a mile, offset so no multiple of
        the 0.5-mile step starts on them. A uniform sample can still catch all
        three here (the window is wide), so what this pins is that the
        photo-anchored maximum reports the full cluster rather than a partial
        one - the number a ceiling gets chosen against.
        """
        positions = [(10.05, 400_000), (10.10, 400_000), (10.12, 400_000)]
        stats = rolling_stats(positions, window_mi=1.0, trail_miles=100.0)

        assert stats.max_bytes == 1_200_000
        assert stats.max_start_mi == pytest.approx(10.05)

    def test_the_maximum_is_anchored_at_a_photo_not_at_a_sample_point(self):
        """A cluster narrower than the sample step, sitting between two steps,
        is invisible to uniform sampling and must not be invisible to the max.
        """
        positions = [(7.30, 300_000), (7.35, 300_000)]
        stats = rolling_stats(positions, window_mi=0.2, trail_miles=50.0)

        assert stats.max_bytes == 600_000
        assert stats.max_start_mi == pytest.approx(7.30)

    def test_the_median_describes_a_typical_stretch_not_a_busy_one(self):
        """Most of this trail is empty, so a section picked at random costs
        nothing - even though one section costs a lot. Reporting only the mean
        would hide both facts."""
        positions = [(1.0, 900_000), (1.5, 900_000)]
        stats = rolling_stats(positions, window_mi=10.0, trail_miles=200.0)

        assert stats.p50_bytes == 0.0
        assert stats.max_bytes == 1_800_000

    def test_a_window_as_long_as_the_trail_costs_the_whole_corpus(self):
        positions = [(1.0, 100), (100.0, 200), (199.0, 300)]
        stats = rolling_stats(positions, window_mi=200.0, trail_miles=200.0)

        assert stats.max_bytes == 600

    def test_no_photos_anywhere_is_zero_rather_than_an_error(self):
        stats = rolling_stats([], window_mi=15.0, trail_miles=100.0)

        assert stats.max_bytes == 0
        assert stats.p95_bytes == 0.0

    def test_a_trail_with_no_length_reports_nothing_rather_than_dividing_by_it(self):
        stats = rolling_stats([(0.0, 100)], window_mi=15.0, trail_miles=0.0)

        assert stats.max_bytes == 0


class TestModelledBytes:
    def test_today_is_one_real_file_size_with_nothing_estimated(self):
        assert modelled_bytes(poi(1.0, card_bytes=123_456, photo_count=4), 100_000, all_photos=False) == 123_456

    def test_all_photos_adds_the_extras_at_the_measured_mean(self):
        """The count is real (from the layer); only the bytes of photos never
        downloaded are the corpus mean. One estimated number, applied to a
        measured count."""
        assert modelled_bytes(poi(1.0, card_bytes=100_000, photo_count=3), 150_000, all_photos=True) == 400_000

    def test_a_single_photo_poi_is_unchanged_by_the_all_photos_model(self):
        assert modelled_bytes(poi(1.0, card_bytes=100_000, photo_count=1), 150_000, all_photos=True) == 100_000

    def test_a_photo_count_below_one_never_subtracts_bytes(self):
        """A layer that lost its Photo1..Photo10 fields must not produce a
        negative contribution to a size budget."""
        assert modelled_bytes(poi(1.0, card_bytes=100_000, photo_count=0), 150_000, all_photos=True) == 100_000


class TestLoadPhotoSizes:
    def test_reads_real_sizes_and_reports_bytes_that_have_gone_missing(self, tmp_path):
        """A cleared cache under a surviving outcomes file makes every total
        low. It is reported rather than estimated, because a guessed size is
        what this script exists to replace."""
        digest_present = "a" * 64
        digest_gone = "b" * 64
        photo_dir = tmp_path / "poi_photos"
        photo_dir.mkdir()
        (photo_dir / f"{digest_present}.jpg").write_bytes(b"x" * 4_096)

        outcomes = tmp_path / "poi_images_atc.json"
        outcomes.write_text(
            json.dumps(
                {
                    "pois": {
                        "atc_shelters:1": {"status": "found", "photo": {"digest": digest_present}},
                        "atc_shelters:2": {"status": "found", "photo": {"digest": digest_gone}},
                        "atc_shelters:3": {"status": "none"},
                    }
                }
            )
        )

        sizes, missing = load_photo_sizes(outcomes, tmp_path)

        assert sizes == {"atc_shelters:1": 4_096}
        assert missing == ["atc_shelters:2"]

    def test_a_found_record_with_no_digest_is_skipped_rather_than_crashing(self, tmp_path):
        outcomes = tmp_path / "poi_images_atc.json"
        outcomes.write_text(json.dumps({"pois": {"atc_shelters:1": {"status": "found"}}}))

        sizes, missing = load_photo_sizes(outcomes, tmp_path)

        assert sizes == {}
        assert missing == []


class TestLocate:
    @staticmethod
    def straight_line(miles: float) -> list[LineString]:
        """One projected piece running due east, `miles` long in metres."""
        return [LineString([(0.0, 0.0), (miles * METERS_PER_MILE, 0.0)])]

    def test_a_poi_lands_at_its_distance_along_the_line(self):
        parts = self.straight_line(10.0)
        features = [("atc_shelters:1", "Lost Mtn", 2, Point(3 * METERS_PER_MILE, 0.0))]

        placed = locate(parts, features, "atc_shelters", {"atc_shelters:1": 50_000})

        assert placed[0].mile == pytest.approx(3.0)
        assert placed[0].off_trail_mi == pytest.approx(0.0)
        assert placed[0].card_bytes == 50_000
        assert placed[0].photo_count == 2

    def test_distance_off_the_line_is_carried_rather_than_applied(self):
        """The caller drops what is too far off-trail, so this reports the
        offset instead of filtering on it - which is what lets the script say
        how much it excluded."""
        parts = self.straight_line(10.0)
        features = [("atc_shelters:1", "Down a blaze", 1, Point(2 * METERS_PER_MILE, 0.75 * METERS_PER_MILE))]

        placed = locate(parts, features, "atc_shelters", {"atc_shelters:1": 50_000})

        assert placed[0].off_trail_mi == pytest.approx(0.75)

    def test_a_poi_with_no_downloaded_photo_contributes_nothing_and_is_dropped(self):
        parts = self.straight_line(10.0)
        features = [("atc_shelters:1", "No photo yet", 3, Point(1 * METERS_PER_MILE, 0.0))]

        assert locate(parts, features, "atc_shelters", {}) == []

    def test_results_come_back_ordered_by_mile(self):
        """Every window calculation downstream walks this list in trail
        order."""
        parts = self.straight_line(10.0)
        features = [
            ("atc_shelters:north", "North", 1, Point(8 * METERS_PER_MILE, 0.0)),
            ("atc_shelters:south", "South", 1, Point(2 * METERS_PER_MILE, 0.0)),
        ]
        sizes = {"atc_shelters:north": 1, "atc_shelters:south": 1}

        placed = locate(parts, features, "atc_shelters", sizes)

        assert [p.name for p in placed] == ["South", "North"]

    def test_miles_accumulate_across_the_ordered_pieces(self):
        """The centerline arrives as several pieces; a POI on the second one
        is measured from the southern terminus, not from that piece's start -
        the same measurement export_elevation.py's distance_mi is."""
        parts = [
            LineString([(0.0, 0.0), (5 * METERS_PER_MILE, 0.0)]),
            LineString([(5 * METERS_PER_MILE, 0.0), (10 * METERS_PER_MILE, 0.0)]),
        ]
        features = [("atc_shelters:1", "Second piece", 1, Point(7 * METERS_PER_MILE, 0.0))]

        placed = locate(parts, features, "atc_shelters", {"atc_shelters:1": 1})

        assert placed[0].mile == pytest.approx(7.0)
