"""Cumulative ascent from a dense elevation profile, without counting noise
as climbing.

The problem, measured rather than suspected: summing every rise in the 25 m
profile gives 594,520 ft for the full AT against a published consensus of
roughly 510,000 ft - about 17% too high.

That is not a data error. The profile is correct for *drawing*: the shape and
the elevations are right. It is wrong for *summing*, because summing is the
one operation that turns measurement error into signal. Every metre of
vertical jitter between adjacent samples reads as real climbing, and there
are ~141,000 samples, so a fraction of a metre each is tens of thousands of
feet by the end.

The arithmetic is worth doing, because it says the model is right rather than
merely plausible. 2,190 miles at 25 m spacing is ~141,000 samples. The excess
is 84,520 ft = 25,760 m, or 0.18 m of fake climbing per sample. Gain counts
only the positive half of the jitter, so that implies a sample-to-sample
error of roughly half a metre - which is what a 1/3 arc-second DEM resampled
to 25 m actually looks like. Nothing exotic is happening; the sum is just
integrating the error term.

WHY A DEAD BAND RATHER THAN SMOOTHING. A moving average would attenuate real
peaks along with the noise, and by an amount that depends on how sharp the
peak is - so it would under-count exactly the steep pitches a hiker most
wants counted. A dead band instead asks a yes/no question about each swing:
did the ground actually reverse direction by more than the DEM can resolve?
Swings smaller than that are dropped whole; swings larger than it are counted
*whole*, at their true size.

That last property is the one that matters and is easy to get wrong. The
obvious implementation - carry a running reference and add the difference
whenever it moves more than the threshold - loses up to one threshold at the
top of every climb, which across a few thousand real reversals is itself tens
of thousands of feet, an error in the opposite direction. This module finds
the confirmed turning points first and then sums peak-minus-trough exactly, so
a climb costs nothing to have been measured.

THE THRESHOLD IS NOT TUNED TO THE ANSWER. It is derived from the DEM's own
sample-to-sample error (see NOISE_FLOOR_M) and then checked, per section,
against published figures by check_elevation_gain.py. Picking it by adjusting
until the end-to-end total reads 510,000 would produce a number that agrees
with the consensus by construction and means nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

METERS_PER_FOOT = 0.3048

# Sample-to-sample vertical error of the 1/3 arc-second (~10 m) 3DEP DEM as
# this pipeline resamples it, in metres.
#
# NOT the product's headline accuracy. USGS quotes ~1.55 m RMSE absolute, but
# absolute error is dominated by long-wavelength bias - a whole hillside
# sitting a metre high - which cancels completely in a difference between two
# points 25 m apart. What survives is the short-range component, and that is
# what a gain sum integrates.
#
# 0.5 m is the figure the over-count itself implies (see the module
# docstring's arithmetic), which makes it a measurement of this pipeline's
# real output rather than a number carried over from a datasheet describing a
# different quantity.
NOISE_FLOOR_M = 0.5

# How far the ground must reverse before a turning point is believed, in
# metres.
#
# 3 m is 6x the noise floor above, so a swing produced purely by DEM error
# confirming a turning point is not a thing that happens in 141,000 samples.
# It also lands on the conventional dead band for DEM- and GPX-derived gain
# (3 m / 10 ft), so it is not a number invented here.
#
# What it costs: genuine undulation under 3 m is not counted. On foot that is
# the difference between a trail that rolls and one that is flat, which is
# real but is not climbing anyone plans around - and it is the honest price of
# a DEM that cannot resolve it from noise in the first place.
DEFAULT_THRESHOLD_M = 3.0
DEFAULT_THRESHOLD_FT = DEFAULT_THRESHOLD_M / METERS_PER_FOOT


def cumulative_gain(elevations: Sequence[float], threshold: float) -> float:
    """Total confirmed ascent over one unbroken run of samples.

    `elevations` and `threshold` must share a unit; the return is in that
    unit. Callers with a profile in feet want `DEFAULT_THRESHOLD_FT`.

    Walks the series tracking the running high and low since the last
    confirmed turning point. A climb is banked only once the ground has come
    back down by `threshold` - at which point the whole trough-to-peak rise is
    added at its true size, not at a quantised one. Swings that never reverse
    by that much are never banked at all, which is exactly the noise this
    exists to drop.
    """
    values = list(elevations)
    if len(values) < 2:
        return 0.0

    gain = 0.0
    low = high = values[0]
    rising: bool | None = None

    for value in values[1:]:
        if rising is True:
            if value > high:
                high = value
            elif value <= high - threshold:
                # The ground has turned over by more than the DEM can
                # invent. The peak was real, so bank the whole climb.
                gain += high - low
                low = value
                rising = False
        elif rising is False:
            if value < low:
                low = value
            elif value >= low + threshold:
                high = value
                rising = True
        else:
            # No direction established yet: the profile has not moved far
            # enough from where it started to say which way it is going.
            # Track both extremes so that when it does break out, the climb
            # is measured from the true trough rather than from wherever
            # sampling happened to begin.
            if value > high:
                high = value
            if value < low:
                low = value
            if high - low >= threshold:
                rising = value >= high

    if rising:
        # A climb still in progress when the samples ran out. It has not been
        # confirmed by a reversal, but the alternative is discarding a real
        # ascent for the sole reason that the profile ended at the top of it.
        gain += high - low

    return gain


def cumulative_gain_over_gaps(elevations: Iterable[float | None], threshold: float) -> float:
    """Total confirmed ascent across a profile that may contain nulls.

    A null is a real DEM coverage gap, kept in the profile so the distance
    axis a chart draws from stays continuous (see export_elevation.py). It
    must not be skipped over silently here: joining the samples either side of
    a gap invents a single step between two points that may be miles and
    hundreds of feet apart, and that step is then counted as a climb nobody
    made.

    So each unbroken run is measured on its own and the runs are added. A gap
    contributes nothing, which under-counts by however much real climbing
    happened inside it - the honest direction to be wrong in, and visible in
    the null coverage figures the manifest already records.
    """
    total = 0.0
    run: list[float] = []
    for value in elevations:
        if value is None:
            total += cumulative_gain(run, threshold)
            run = []
        else:
            run.append(value)
    return total + cumulative_gain(run, threshold)


def raw_cumulative_gain(elevations: Iterable[float | None]) -> float:
    """Every rise summed, noise included - what a zero threshold gives.

    Kept as its own named function rather than left implicit, because it is
    the number this module exists to replace and the comparison is the whole
    argument. check_elevation_gain.py reports both.
    """
    return cumulative_gain_over_gaps(elevations, 0.0)


def gain_between(
    profile: Sequence[dict],
    start_mi: float,
    end_mi: float,
    threshold: float = DEFAULT_THRESHOLD_FT,
) -> float:
    """Confirmed ascent between two mileposts, in feet.

    `profile` is elevation_profile.json's shape - records of `distance_mi` and
    `elevation_ft`, sorted by distance. Bounds are inclusive; a range that
    selects fewer than two samples has no gain rather than raising, since a
    caller asking about a 50 m window is asking a reasonable question about a
    25 m profile.
    """
    window = [record["elevation_ft"] for record in profile if start_mi <= record["distance_mi"] <= end_mi]
    return cumulative_gain_over_gaps(window, threshold)
