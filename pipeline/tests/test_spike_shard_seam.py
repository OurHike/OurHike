"""Behaviour of the shard-seam spike's measuring parts (spike_shard_seam.py).

The builds themselves need Planetiler, a network and minutes, so they are
CI's job. What is tested here is everything that decides whether the numbers
those builds produce mean anything: which line counts as the seam, and
whether the temp-disk peak is a peak rather than whatever happened to be on
disk when the process exited.

The sampler tests drive sample() directly rather than racing the thread. A
test that started a real sampler, wrote files, deleted them and asserted on
the peak would pass or fail on where the poll landed - which is the same
class of bug the sampler exists to avoid.
"""

import pytest
from shapely.geometry import box

from spike_shard_seam import BuildResult, PeakDiskSampler, directory_bytes, seam_between


def test_the_seam_is_where_two_shards_touch():
    west, east = box(0, 0, 5, 10), box(5, 0, 10, 10)

    seam = seam_between([west, east])

    assert seam.length == pytest.approx(10.0)
    assert seam.geom_type in ("LineString", "MultiLineString")


def test_the_seam_excludes_the_regions_outer_edge():
    """A shard's outer edge is the region's edge - the control build is cut
    there identically, so a difference cannot be blamed on sharding. Counting
    it as seam would let a real interior finding hide in the noise."""
    west, east = box(0, 0, 5, 10), box(5, 0, 10, 10)

    seam = seam_between([west, east])

    # The shared border only: the full outline of both boxes would be 60.
    assert seam.length == pytest.approx(10.0)
    assert seam.bounds == (5.0, 0.0, 5.0, 10.0)


def test_three_shards_in_a_row_contribute_both_of_their_seams():
    shapes = [box(0, 0, 5, 10), box(5, 0, 10, 10), box(10, 0, 15, 10)]

    assert seam_between(shapes).length == pytest.approx(20.0)


def test_regions_that_do_not_touch_are_refused_rather_than_measured_against_nothing():
    """Without a shared border every difference would report as 'far from the
    seam', which is the NOT-SEAM-LOCAL verdict - the alarming one - arrived
    at by measuring against a seam that does not exist."""
    with pytest.raises(SystemExit, match="do not share a border"):
        seam_between([box(0, 0, 1, 1), box(50, 50, 51, 51)])


def test_directory_bytes_totals_everything_underneath(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    (tmp_path / "nested" / "b.bin").write_bytes(b"y" * 50)

    assert directory_bytes(tmp_path) == 150


def test_a_directory_planetiler_has_not_created_yet_measures_zero(tmp_path):
    assert directory_bytes(tmp_path / "not-yet") == 0


def test_the_peak_survives_the_directory_shrinking_again():
    """The measurement that matters. Planetiler deletes intermediates as
    phases end, so the final size understates what the build needed - and
    understating it is what would make a sub-region look like it fits a free
    runner when it does not."""
    readings = iter([10, 400, 90, 20])
    sampler = PeakDiskSampler(path=None, measure=lambda _: next(readings))

    for _ in range(4):
        sampler.sample()

    assert sampler.peak == 400


def test_the_peak_ignores_the_order_the_readings_arrive_in():
    for readings in ([5, 100], [100, 5]):
        sampler = PeakDiskSampler(path=None, measure=lambda _, r=iter(readings): next(r))
        sampler.sample()
        sampler.sample()
        assert sampler.peak == 100


def test_a_build_shorter_than_one_poll_is_still_measured(tmp_path):
    """__exit__ takes a final sample, so a build that finishes between polls
    reports its size rather than zero. The interval here is longer than the
    body deliberately: without that final sample this reads 0."""
    (tmp_path / "written-during-the-build.bin").write_bytes(b"z" * 4096)

    with PeakDiskSampler(tmp_path, interval=3600) as sampler:
        pass

    assert sampler.peak == 4096


def test_the_multiplier_is_peak_temp_over_input():
    """The number BASEMAP.md's fits-a-free-runner table is built on."""
    result = BuildResult("control", None, input_bytes=2_000_000_000, output_bytes=0, peak_tmp_bytes=9_000_000_000, seconds=0)

    assert result.disk_multiplier == pytest.approx(4.5)


def test_an_empty_input_reports_no_multiplier_rather_than_dividing_by_zero():
    result = BuildResult("control", None, input_bytes=0, output_bytes=0, peak_tmp_bytes=100, seconds=0)

    assert result.disk_multiplier == 0.0
