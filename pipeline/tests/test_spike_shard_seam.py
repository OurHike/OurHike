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

from spike_shard_seam import (
    BuildResult,
    PeakDiskSampler,
    directory_apparent_bytes,
    directory_bytes,
    fit_fixed_and_marginal,
    seam_between,
)


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
    with pytest.raises(SystemExit, match="neither overlap nor share a border"):
        seam_between([box(0, 0, 1, 1), box(50, 50, 51, 51)])


def test_apparent_bytes_totals_everything_underneath(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    (tmp_path / "nested" / "b.bin").write_bytes(b"y" * 50)

    assert directory_apparent_bytes(tmp_path) == 150


def test_a_sparse_file_costs_the_disk_almost_nothing_however_big_it_claims_to_be(tmp_path):
    """The bug that made the first run of this spike report a number it had
    not measured. Planetiler's node map is created at the size of the node-ID
    space and only the pages it touches are allocated, so apparent size is
    near-constant across builds - and dividing one constant by five different
    inputs produced five different 'multipliers' that were all fiction.

    st_blocks is what the runner's free space actually loses."""
    sparse = tmp_path / "node.db"
    with open(sparse, "wb") as f:
        f.truncate(2_000_000_000)
        f.write(b"x" * 4096)

    assert directory_apparent_bytes(tmp_path) == 2_000_000_000
    assert directory_bytes(tmp_path) < 1_000_000


def test_allocated_bytes_rounds_up_to_whole_blocks(tmp_path):
    """A 100-byte file does not cost 100 bytes of disk. Allocated is always
    at least a block, which is why this number is never below apparent for
    small dense files and wildly below it for sparse ones."""
    (tmp_path / "small.bin").write_bytes(b"x" * 100)

    assert directory_bytes(tmp_path) >= 512


def test_a_directory_planetiler_has_not_created_yet_measures_zero(tmp_path):
    assert directory_bytes(tmp_path / "not-yet") == 0


def test_the_peak_survives_the_directory_shrinking_again():
    """The measurement that matters. Planetiler deletes intermediates as
    phases end, so the final size understates what the build needed - and
    understating it is what would make a sub-region look like it fits a free
    runner when it does not."""
    readings = iter([(10, 10), (400, 400), (90, 90), (20, 20)])
    sampler = PeakDiskSampler(path=None, measure=lambda _: next(readings))

    for _ in range(4):
        sampler.sample()

    assert sampler.peak == 400


def test_the_peak_ignores_the_order_the_readings_arrive_in():
    for readings in ([(5, 5), (100, 100)], [(100, 100), (5, 5)]):
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

    assert sampler.peak >= 4096


def test_the_multiplier_is_peak_temp_over_input():
    """The number BASEMAP.md's fits-a-free-runner table is built on."""
    result = BuildResult(
        "control", None, input_bytes=2_000_000_000, output_bytes=0, peak_tmp_bytes=9_000_000_000, peak_apparent_bytes=0, seconds=0
    )

    assert result.disk_multiplier == pytest.approx(4.5)


def test_an_empty_input_reports_no_multiplier_rather_than_dividing_by_zero():
    result = BuildResult("control", None, input_bytes=0, output_bytes=0, peak_tmp_bytes=100, peak_apparent_bytes=100, seconds=0)

    assert result.disk_multiplier == 0.0
    assert result.apparent_multiplier == 0.0


def test_both_peaks_are_tracked_independently():
    """They need not peak together: the node map inflates apparent size early
    and the feature file fills real disk later. Taking the apparent figure
    from whichever moment allocated peaked would understate it, and the gap
    between the two is the whole point of printing both."""
    readings = iter([(10, 900), (500, 100)])
    sampler = PeakDiskSampler(path=None, measure=lambda _: next(readings))

    sampler.sample()
    sampler.sample()

    assert sampler.peak == 500
    assert sampler.peak_apparent == 900


# run_planetiler and download_sources_cmd moved to export_basemap.py on
# 2026-11-04, and their tests to tests/test_export_basemap.py with them.


def test_shards_that_overlap_report_the_overlapping_band_as_the_seam():
    """Geofabrik's .poly shapes carry a margin, so real neighbours overlap
    rather than abut. Their outlines then meet only at points, and a
    point-set has an empty boundary whose bounds are NaN - which is exactly
    how the first run that got this far died. The band both shards cover is
    the truer seam anyway: every tile in it is one both were asked to build."""
    west, east = box(0, 0, 6, 10), box(4, 0, 10, 10)

    seam = seam_between([west, east])

    assert seam.area > 0
    assert seam.bounds == (4.0, 0.0, 6.0, 10.0)


def test_shards_that_merely_abut_still_report_their_shared_border():
    west, east = box(0, 0, 5, 10), box(5, 0, 10, 10)

    seam = seam_between([west, east])

    assert seam.area == 0
    assert seam.length == pytest.approx(10.0)


# The disk probe. VT/NH could not answer the multiplier question because
# Planetiler's fixed overhead was larger than the inputs: five builds all
# peaked at 0.85 GB, and dividing one constant by five denominators produced
# five "multipliers" that were all the same number in disguise. Separating
# fixed from marginal is what makes a bigger run mean something.


def test_the_fit_recovers_a_fixed_cost_and_a_marginal_rate():
    """peak = 1 GB fixed + 5x input, sampled at three sizes."""
    points = [(1_000_000_000, 6_000_000_000), (2_000_000_000, 11_000_000_000), (4_000_000_000, 21_000_000_000)]

    fixed, marginal = fit_fixed_and_marginal(points)

    assert fixed == pytest.approx(1_000_000_000)
    assert marginal == pytest.approx(5.0)


def test_a_dominant_fixed_cost_is_reported_as_fixed_rather_than_as_a_huge_multiplier():
    """The VT/NH shape of failure: a large constant and tiny inputs. The
    naive ratio says 17x and 8.5x; the fit says the marginal rate is 1x and
    the rest is overhead - which is the number that predicts a big build."""
    points = [(50_000_000, 850_000_000), (100_000_000, 900_000_000)]

    fixed, marginal = fit_fixed_and_marginal(points)

    assert fixed == pytest.approx(800_000_000)
    assert marginal == pytest.approx(1.0)


def test_one_build_cannot_separate_the_two():
    with pytest.raises(ValueError, match="at least two builds"):
        fit_fixed_and_marginal([(1_000, 2_000)])


def test_builds_of_identical_size_cannot_separate_the_two_either():
    """Two points on the same vertical line have no slope to solve for, and
    silently returning one would be worse than refusing."""
    with pytest.raises(ValueError, match="same input size"):
        fit_fixed_and_marginal([(1_000, 2_000), (1_000, 3_000)])
