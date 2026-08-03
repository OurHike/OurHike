"""Tests for lib/elevation_gain.py - cumulative ascent that doesn't count
noise as climbing.

Why this exists
---------------
Summing every rise in the 25 m profile gives 594,520 ft for the full AT
against a ~510,000 ft consensus - 17% too high. The profile is not wrong; the
sum is. Summing is the one operation that turns measurement error into
signal, and there are ~141,000 samples, so half a metre of jitter each is tens
of thousands of feet.

Two ways to be wrong here, and the tests are mostly about holding both at
once:

- Count the noise, and every hiking time estimate downstream inflates.
- Reject the noise with something that also shaves real climbs - a moving
  average, or a dead band that quantises - and steep pitches get under-counted
  precisely where a hiker most wants them counted.

The second is the subtler failure and has no obvious symptom, so several
tests below exist only to pin it: a real climb must be counted at its true
size, not at a size reduced by however it was filtered.
"""

import json
from pathlib import Path

import pytest

from lib.elevation_gain import (
    DEFAULT_THRESHOLD_FT,
    DEFAULT_THRESHOLD_M,
    NOISE_FLOOR_M,
    cumulative_gain,
    cumulative_gain_over_gaps,
    gain_between,
    raw_cumulative_gain,
)

T = 3.0


def jitter(base, deltas):
    """A flat profile at `base` wobbled by `deltas` - what a DEM does to
    level ground."""
    return [base + d for d in deltas]


# --- Real climbs are counted at their real size ----------------------------


def test_a_single_climb_counts_its_whole_rise():
    assert cumulative_gain([100, 200, 300, 400], T) == pytest.approx(300)


def test_a_climb_is_not_shaved_by_the_threshold_it_was_filtered_with():
    """The failure mode of the obvious implementation. Carrying a running
    reference and adding whenever it moves more than the threshold loses up to
    one threshold at the top of every climb - across a few thousand real
    reversals on the AT that is itself tens of thousands of feet, an error in
    the opposite direction to the one being fixed."""
    profile = [0, 500, 0, 500, 0, 500]

    assert cumulative_gain(profile, T) == pytest.approx(1500)


def test_a_gentle_climb_below_the_step_size_still_counts():
    """Each step is 1 m, well under the 3 m threshold, but the climb is 100 m.
    A filter that compared consecutive samples against the threshold would see
    nothing here at all."""
    profile = [float(i) for i in range(101)]

    assert cumulative_gain(profile, T) == pytest.approx(100)


def test_every_separate_climb_in_a_rolling_profile_counts():
    profile = [0, 100, 50, 150, 100, 200]

    assert cumulative_gain(profile, T) == pytest.approx(100 + 100 + 100)


def test_a_climb_the_profile_ends_on_is_counted():
    """It has not been confirmed by a reversal, but discarding a real ascent
    because the samples ran out at the top of it is worse than counting it."""
    assert cumulative_gain([0, 100, 50, 400], T) == pytest.approx(100 + 350)


# --- Noise is not climbing -------------------------------------------------


def test_flat_ground_with_dem_jitter_has_no_gain():
    profile = jitter(1000, [0, 0.4, -0.7, 0.2, -0.3, 0.6, -0.5, 0.1])

    assert cumulative_gain(profile, T) == 0


# A gentle grade, in metres per 25 m sample, with DEM jitter of comparable
# size riding on it.
#
# Gentle is not an arbitrary choice - it is where the whole problem lives.
# On a steep pitch the ground rises further between samples than the noise
# can push it back down, so the series never actually reverses and the raw
# sum is already correct. Noise only manufactures climbing where the true
# slope is smaller than the noise, which is most of 2,190 miles: valley
# floors, ridge walks, road walks, everything that rolls.
GENTLE_RISE_PER_SAMPLE = 0.5
JITTER = [0.4, -0.6, 0.3, -0.2, 0.5, -0.4, 0.1, -0.3]


def gentle_noisy_climb(samples=100):
    clean = [i * GENTLE_RISE_PER_SAMPLE for i in range(samples + 1)]
    return [e + JITTER[i % len(JITTER)] for i, e in enumerate(clean)]


def test_jitter_riding_on_a_real_climb_does_not_inflate_it():
    """The realistic case: the ground is genuinely going up and the DEM is
    genuinely noisy at the same time."""
    true_rise = 100 * GENTLE_RISE_PER_SAMPLE

    assert cumulative_gain(gentle_noisy_climb(), T) == pytest.approx(true_rise, abs=2 * T)


def test_the_raw_sum_inflates_the_same_climb_by_roughly_what_the_at_shows():
    """The comparison the module exists to make, on the same series. No dead
    band means every wobble is counted, and the resulting over-count lands in
    the same range as the real 17% - which is the evidence that the noise
    model behind the threshold describes what is actually happening."""
    noisy = gentle_noisy_climb()
    true_rise = 100 * GENTLE_RISE_PER_SAMPLE

    inflation = (raw_cumulative_gain(noisy) - true_rise) / true_rise

    assert 0.10 < inflation < 0.35
    assert raw_cumulative_gain(noisy) > cumulative_gain(noisy, T)


def test_a_steep_climb_is_not_inflated_even_raw():
    """The other half of that reasoning, and the reason the fix belongs in the
    sum rather than in the DEM: where the ground climbs faster than the noise,
    the series never reverses and there is nothing to over-count."""
    steep = [i * 10.0 + JITTER[i % len(JITTER)] for i in range(51)]

    assert raw_cumulative_gain(steep) == pytest.approx(cumulative_gain(steep, T), abs=1)


def test_noise_accumulates_without_bound_as_samples_get_denser():
    """Why 'sample more finely' is not the fix, stated as a test. Doubling the
    sample count on the same flat ground doubles the fake climbing, forever."""
    coarse = jitter(1000, [0.3, -0.4] * 50)
    fine = jitter(1000, [0.3, -0.4] * 100)

    assert raw_cumulative_gain(fine) > 1.9 * raw_cumulative_gain(coarse)
    assert cumulative_gain(fine, T) == cumulative_gain(coarse, T) == 0


def test_a_swing_just_under_the_threshold_is_dropped_whole():
    assert cumulative_gain([100, 102.9, 100, 102.9, 100], T) == 0


def test_a_swing_just_over_the_threshold_is_kept_whole():
    assert cumulative_gain([100, 103.1, 100, 103.1], T) == pytest.approx(3.1 + 3.1)


# --- Where the profile begins must not change the answer -------------------


def test_a_climb_is_measured_from_the_true_low_not_the_first_sample():
    """If the profile happens to start partway up, then dips slightly before
    climbing, the dip is the real trough. Measuring from sample zero instead
    would quietly lose it."""
    from_dip = cumulative_gain([100, 98, 500], T)

    assert from_dip == pytest.approx(402)


def test_leading_noise_does_not_establish_a_false_direction():
    profile = jitter(1000, [0, 0.3, -0.4, 0.2, -0.1]) + [1500.0]

    assert cumulative_gain(profile, T) == pytest.approx(500, abs=1)


# --- Coverage gaps ---------------------------------------------------------


def test_a_dem_gap_is_not_bridged_into_a_climb():
    """Nulls are real DEM coverage gaps, kept in the profile so a chart's
    distance axis stays continuous. Joining the samples either side invents a
    single step between two points that may be miles and hundreds of feet
    apart, and counts it as a climb nobody made."""
    with_gap = [100.0, 110.0, None, 3000.0, 3010.0]

    assert cumulative_gain_over_gaps(with_gap, T) == pytest.approx(10 + 10)


def test_each_side_of_a_gap_is_still_measured():
    with_gap = [0.0, 500.0, None, 0.0, 500.0]

    assert cumulative_gain_over_gaps(with_gap, T) == pytest.approx(1000)


def test_a_profile_that_is_entirely_nulls_has_no_gain():
    assert cumulative_gain_over_gaps([None, None, None], T) == 0


# --- Degenerate input ------------------------------------------------------


@pytest.mark.parametrize("profile", [[], [42.0]])
def test_too_few_samples_to_have_climbed(profile):
    assert cumulative_gain(profile, T) == 0


def test_a_perfectly_flat_profile_has_no_gain():
    assert cumulative_gain([1000.0] * 50, T) == 0


def test_a_pure_descent_has_no_gain():
    assert cumulative_gain([500, 400, 300, 200, 100], T) == 0


# --- Windowing -------------------------------------------------------------


def test_gain_between_two_mileposts_uses_only_that_window():
    profile = [
        {"distance_mi": 0.0, "elevation_ft": 1000},
        {"distance_mi": 1.0, "elevation_ft": 2000},
        {"distance_mi": 2.0, "elevation_ft": 1000},
        {"distance_mi": 3.0, "elevation_ft": 2000},
    ]

    assert gain_between(profile, 0.0, 1.0) == pytest.approx(1000)
    assert gain_between(profile, 0.0, 3.0) == pytest.approx(2000)


def test_a_window_too_short_to_hold_two_samples_has_no_gain():
    """A caller asking about a 50 m window of a 25 m profile is asking a
    reasonable question and should not get an exception for it."""
    profile = [{"distance_mi": 0.0, "elevation_ft": 1000}]

    assert gain_between(profile, 0.0, 0.01) == 0


# --- The constants themselves ----------------------------------------------


def test_the_threshold_sits_well_clear_of_the_noise_floor():
    """Not a tautology: it is the one relationship that has to hold for the
    dead band to mean anything, and it would be easy to change one constant
    later without the other."""
    assert DEFAULT_THRESHOLD_M >= 4 * NOISE_FLOOR_M


def test_the_foot_threshold_is_the_metre_threshold():
    """Two units, one number. They are used in different call sites - the
    profile is in feet, the DEM reasoning is in metres - and a copy that
    drifted would be invisible."""
    assert DEFAULT_THRESHOLD_FT * 0.3048 == pytest.approx(DEFAULT_THRESHOLD_M)


# --- Shared with the TypeScript implementation -----------------------------
#
# The algorithm exists twice - here and in client/src/lib/elevationGain.ts -
# because it is asked two different questions: the pipeline asks once about
# the whole trail, the app asks about a window that moves as a hiker walks.
# Two implementations of one number drift, and not gradually or visibly: they
# drift the first time someone fixes an edge case in one language and does not
# think to open the other file.
#
# Both suites read the same vectors, so that becomes a failing test in
# whichever language was not updated.

VECTORS = json.loads((Path(__file__).parent.parent / "reference" / "gain_vectors.json").read_text())


@pytest.mark.parametrize("case", VECTORS["cases"], ids=lambda c: c["name"])
def test_shared_vector(case):
    assert cumulative_gain(case["elevations"], case["threshold"]) == pytest.approx(case["expected_gain"])


@pytest.mark.parametrize("case", VECTORS["gap_cases"], ids=lambda c: c["name"])
def test_shared_gap_vector(case):
    assert cumulative_gain_over_gaps(case["elevations"], case["threshold"]) == pytest.approx(case["expected_gain"])


def test_the_shared_vectors_actually_have_something_in_them():
    """A vector file that silently emptied would turn every parametrised test
    above into zero tests, and a suite that runs nothing passes."""
    assert len(VECTORS["cases"]) >= 10
    assert len(VECTORS["gap_cases"]) >= 3
