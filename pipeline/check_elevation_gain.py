"""Check the cumulative-ascent threshold against published figures, per
section.

lib/elevation_gain.py picks its dead band from the DEM's sample-to-sample
error, not from the answer. This is the other half of that discipline: it says
out loud what the chosen threshold actually produces, and compares it against
figures somebody else published, section by section.

WHY PER SECTION AND NOT END TO END. Matching one 2,190-mile total is a single
scalar with one free parameter behind it - there is always some threshold that
hits it, and hitting it proves only that a search succeeded. Per-section
agreement is a real test: one threshold has to work for the Whites and for
Virginia at the same time, and a threshold that is merely tuned will do well
on whichever section it was tuned against and badly on the rest.

The sweep is printed for the same reason. A threshold whose neighbours give
wildly different totals is a knob the answer is balanced on, and that is worth
seeing rather than discovering later.

    .venv/Scripts/python check_elevation_gain.py
    .venv/Scripts/python check_elevation_gain.py --profile path/to/profile.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib.elevation_gain import (
    DEFAULT_THRESHOLD_FT,
    DEFAULT_THRESHOLD_M,
    METERS_PER_FOOT,
    gain_between,
    gain_over_profile,
)

ROOT = Path(__file__).parent
PROFILE_PATH = ROOT / "data" / "processed" / "elevation_profile.json"
REFERENCE_PATH = ROOT / "reference" / "published_gain.json"

# Thresholds to report alongside the chosen one, in metres. Spread either side
# of DEFAULT_THRESHOLD_M so the shape of the curve is visible - a total that
# barely moves between 2 m and 4 m is a robust answer; one that halves is a
# knob, and the difference should not have to be inferred.
SWEEP_M = (0.0, 1.0, 2.0, DEFAULT_THRESHOLD_M, 4.0, 6.0, 10.0)

# Feet in a mile, for turning the profile's own `distance_mi` axis into the
# units its elevations are already in.
FEET_PER_MILE = 5280

# The steepest a step between neighbouring samples may be and still be trail.
#
# 1.0 is a 100% grade - 45 degrees, sustained, between two samples. The A.T.
# has nothing like it: the steepest named scrambles are short scrambles, not
# a sustained 45 degrees held across the whole spacing. So this is a ceiling
# on the physically possible rather than a judgement about what is steep, and
# it is set loose on purpose - every real case measured so far clears it by a
# wide margin (the largest by 30x), so nothing is gained by arguing the
# ceiling down to something a hiker might dispute.
MAX_PLAUSIBLE_GRADE = 1.0

# How far a section may sit from its published figure before it is called a
# failure, as a fraction.
#
# 10% is deliberately loose, because the published figures are themselves not
# a gold standard: guidebooks, FarOut and the ATC disagree with each other by
# more than a little, and they measure along a tread whose exact line moves
# between relocations. A tolerance tight enough to distinguish 5% error would
# mostly be measuring which source was quoted. What 10% can still catch is the
# thing this exists to catch - a 17% systematic over-count.
SECTION_TOLERANCE = 0.10


def load_profile(path: Path) -> list[dict]:
    """The profile, or a ValueError naming what is wrong with it.

    Anything unreadable is one outcome rather than several: a truncated write,
    a JSON document of the wrong shape and an empty array all mean the same
    thing to a caller - there is nothing here to measure - and each would
    otherwise surface as a different traceback from a different library.
    """
    try:
        records = json.loads(path.read_text())
    except ValueError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(records, list) or not records:
        raise ValueError(f"{path} does not look like an elevation profile")
    return records


def load_reference(path: Path) -> dict:
    """Published gain figures to check against, or an empty reference.

    Absent rather than fabricated is the point. A reference table invented to
    make the harness run would make an unvalidated threshold *look* validated,
    which is worse than having no check at all - the whole reason this file
    exists is that a number can agree with a consensus by construction and
    mean nothing.
    """
    if not path.exists():
        return {"whole_trail": None, "sections": []}
    try:
        return json.loads(path.read_text())
    except ValueError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc


def sweep(profile: list[dict]) -> list[tuple[float, float]]:
    """Total gain in feet at each threshold in SWEEP_M.

    Over records rather than bare elevations, so the sweep breaks at part
    boundaries as well as DEM nulls (#559). It has to: the contamination is
    flat at ~36,800 ft across the whole sweep, so reading it off elevations
    alone would shift every row by the same amount and leave the SHAPE - the
    one thing the sweep exists to show - looking identical while every number
    in it was wrong.
    """
    return [(m, gain_over_profile(profile, m / METERS_PER_FOOT)) for m in SWEEP_M]


def marks_part_boundaries(profile: list[dict]) -> bool:
    """Whether this profile records where its centerline pieces break.

    A profile published before `export_elevation.py` started marking them
    carries none, and is measured exactly as it was before - the honest
    reading of a file that does not say. Reported rather than assumed, because
    a fix that silently does nothing on old data is worse than no fix: the run
    would print the old contaminated total under the new code and look
    corrected.
    """
    return any(record.get("part_start") for record in profile)


def sample_spacing_ft(profile: list[dict]) -> float | None:
    """The profile's own along-trail spacing in feet, from the median step.

    Read off the data rather than taken from export_elevation.py's
    SAMPLE_INTERVAL_METERS, because this script is handed a profile - possibly
    an older one, possibly the published artifact from a run whose interval
    differed - and the grade ceiling below is only meaningful against the
    spacing the file it is measuring actually used.

    Median rather than mean: cross-part boundaries carry the distance axis
    straight across (export_elevation.py docstring point 4), so a handful of
    steps are far longer than the interval and would drag an average.

    Expect a couple of feet of slack rather than the exact interval, and that
    is fine here. `distance_mi` is written to three decimals, so a true 25 m
    step (0.015534 mi) lands as either 0.016 or 0.015 - the median picks the
    commoner, giving ~84 ft where the interval is 82. The ceiling below is a
    bound on the physically possible and every real finding clears it by
    roughly 30x, so a 3% loose ceiling costs nothing and errs toward reporting
    fewer steps rather than inventing one. It does mean a count here can differ
    by one or two from a count taken against the unrounded geometry.
    """
    steps = [
        b["distance_mi"] - a["distance_mi"]
        for a, b in zip(profile, profile[1:])
        if a.get("distance_mi") is not None and b.get("distance_mi") is not None
    ]
    positive = sorted(step for step in steps if step > 0)
    if not positive:
        return None
    return positive[len(positive) // 2] * FEET_PER_MILE


def implausible_steps(profile: list[dict], spacing_ft: float | None = None) -> list[dict]:
    """Steps too steep to be trail, whatever produced them.

    A step's grade is computable from the artifact alone, which is what makes
    this checkable here: the published profile records nothing about where the
    centerline pieces break (#559), but it does not have to - a rise past
    MAX_PLAUSIBLE_GRADE between neighbouring samples is not a slope anybody
    walks, so it is not terrain, so whatever it is it is not gain.

    Deliberately NOT used to correct the totals. That is #559's option (4),
    which that issue argues against and I agree with: subtracting these would
    delete the evidence of a real geometry fault and leave a number that
    merely looks right. This only reports.
    """
    if spacing_ft is None:
        spacing_ft = sample_spacing_ft(profile)
    if not spacing_ft:
        return []

    ceiling_ft = spacing_ft * MAX_PLAUSIBLE_GRADE
    steps = []
    for a, b in zip(profile, profile[1:]):
        first, second = a.get("elevation_ft"), b.get("elevation_ft")
        if first is None or second is None:
            continue
        delta = second - first
        if abs(delta) > ceiling_ft:
            steps.append(
                {
                    "from_mi": a["distance_mi"],
                    "to_mi": b["distance_mi"],
                    "delta_ft": delta,
                    # A step INTO a marked first-sample crosses a seam, so the
                    # gain already excludes it (#559). One that is not at a
                    # seam is the interesting case: something is wrong that
                    # part boundaries do not explain.
                    "at_seam": bool(b.get("part_start")),
                }
            )
    return steps


def ascending_total(steps: list[dict]) -> float:
    """The climbing half of a set of steps - what they add to a gain figure.

    A descent contributes nothing to cumulative ascent, so only the rises are
    the over-count. Both halves are equally impossible; only one inflates.
    """
    return sum(step["delta_ft"] for step in steps if step["delta_ft"] > 0)


def check_sections(
    profile: list[dict],
    sections: list[dict],
    threshold_ft: float,
    suspect_steps: list[dict] | None = None,
) -> list[dict]:
    """One row per published section: measured, published, and the error.

    `suspect_steps` are implausible_steps()' findings. A section containing
    one is marked `contaminated` and its comparison is not to be believed in
    either direction - see main() for why that is reported rather than
    failed.

    **Only steps that are NOT at a marked seam contaminate.** Once a profile
    records its centerline boundaries (#559), a step across one is already
    excluded from `gain_between`, so the section's figure is sound and
    withholding a verdict would refuse to validate for a reason that has been
    fixed. An impossible step somewhere the pipeline calls continuous trail is
    a different matter: nothing excludes that one, and it is still summed.
    """
    suspect_steps = [step for step in (suspect_steps or []) if not step.get("at_seam")]
    rows = []
    for section in sections:
        measured = gain_between(profile, section["start_mi"], section["end_mi"], threshold_ft)
        published = section["published_gain_ft"]
        error = None if not published else (measured - published) / published
        inside = [step for step in suspect_steps if section["start_mi"] <= step["from_mi"] and step["to_mi"] <= section["end_mi"]]
        # A section may carry its own tolerance, wider than the default, for
        # exactly one reason: cumulative gain is methodology-dependent, and
        # on rolling low-gain terrain the spread BETWEEN honest published
        # sources exceeds 10% of the small denominator (#133's Roan finding:
        # no threshold in the whole sweep reconciles a densely-sampled DEM
        # sum with the club's smoothed figure, while the same thresholds sit
        # within ±4% on both pure ascents). An override without a stated
        # reason is refused - a silently widened gate is a gate that was
        # quietly turned off.
        tolerance = section.get("tolerance", SECTION_TOLERANCE)
        if tolerance != SECTION_TOLERANCE and not section.get("tolerance_reason"):
            raise ValueError(
                f"section {section['name']!r} overrides the tolerance to {tolerance} "
                "without a tolerance_reason. Say why, or use the default."
            )
        rows.append(
            {
                "name": section["name"],
                "start_mi": section["start_mi"],
                "end_mi": section["end_mi"],
                "measured_ft": measured,
                "published_ft": published,
                "source": section.get("source", ""),
                "error": error,
                "tolerance": tolerance,
                "within_tolerance": error is not None and abs(error) <= tolerance,
                "contaminated_ft": ascending_total(inside),
                "contaminated": bool(inside),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profile", type=Path, default=PROFILE_PATH)
    parser.add_argument("--reference", type=Path, default=REFERENCE_PATH)
    args = parser.parse_args(argv)

    if not args.profile.exists():
        print(f"No profile at {args.profile} - run export_elevation.py first.", file=sys.stderr)
        return 2

    try:
        profile = load_profile(args.profile)
    except ValueError as exc:
        # Same exit code as an absent profile, and for the same reason: in
        # both cases nothing has been measured, which is a different thing
        # from having measured something and disagreed with it.
        print(f"Cannot read the profile: {exc}", file=sys.stderr)
        return 2

    try:
        reference = load_reference(args.reference)
    except ValueError as exc:
        # A reference that exists but cannot be read is the profile case
        # again: nothing has been checked, and a traceback would say less.
        print(f"Cannot read the reference: {exc}", file=sys.stderr)
        return 2
    raw = gain_over_profile(profile, 0.0)
    chosen = gain_over_profile(profile, DEFAULT_THRESHOLD_FT)

    print(f"{len(profile):,} samples")
    if marks_part_boundaries(profile):
        seams = sum(1 for record in profile if record.get("part_start"))
        print(f"  {seams} centerline seam(s) marked and excluded from the sums below (#559).")
    else:
        print("  No part_start markers: this profile predates them, so every centerline")
        print("  seam in it is still summed as climbing (#559). The figures below are the")
        print("  OLD, contaminated ones - re-run export_elevation.py for corrected numbers.")
    print(f"  raw (every rise summed)     {raw:>12,.0f} ft")
    print(f"  at {DEFAULT_THRESHOLD_M} m dead band          {chosen:>12,.0f} ft")
    if raw:
        print(f"  difference                  {raw - chosen:>12,.0f} ft ({(raw - chosen) / raw:.1%} of raw)")

    print("\nthreshold sweep")
    for meters, total in sweep(profile):
        marker = "  <- chosen" if meters == DEFAULT_THRESHOLD_M else ""
        print(f"  {meters:>5.1f} m  {total:>12,.0f} ft{marker}")

    spacing_ft = sample_spacing_ft(profile)
    suspect = implausible_steps(profile, spacing_ft)
    if spacing_ft:
        print(f"\nstep plausibility (spacing {spacing_ft:,.0f} ft, ceiling {spacing_ft * MAX_PLAUSIBLE_GRADE:,.0f} ft)")
        if not suspect:
            print("  no step exceeds a 100% grade.")
        else:
            unexplained = [step for step in suspect if not step["at_seam"]]
            print(f"  {len(suspect)} step(s) too steep to be trail")
            for step in sorted(suspect, key=lambda s: abs(s["delta_ft"]), reverse=True)[:3]:
                at = "seam" if step["at_seam"] else "NOT a seam"
                print(f"    mi {step['from_mi']:>9.3f} -> {step['to_mi']:>9.3f}  {step['delta_ft']:+9,.0f} ft  ({at})")
            seamed = len(suspect) - len(unexplained)
            if seamed:
                print(f"  {seamed} at a marked centerline seam, already excluded from the sums above (#559).")
            if unexplained:
                # The finding worth acting on once #559's markers exist. A step
                # nothing walks, at a place the pipeline says is continuous
                # trail, is a defect the markers do not explain - and unlike a
                # seam it IS still being summed as climbing.
                climbing = ascending_total(unexplained)
                share = f" ({climbing / chosen:.1%} of the {DEFAULT_THRESHOLD_M} m total)" if chosen else ""
                print(f"  {len(unexplained)} NOT at any seam, {climbing:,.0f} ft of it ascending{share} - and still summed.")

    whole = reference.get("whole_trail")
    if whole and whole.get("published_gain_ft"):
        published = whole["published_gain_ft"]
        print(f"\nwhole trail vs {whole.get('source', 'published')}: {(chosen - published) / published:+.1%}")
        print("  A single total is the weak check - one free parameter can always hit one number.")

    sections = reference.get("sections") or []
    if not sections:
        # Not a pass. The threshold has not been validated, and saying so is
        # the entire value of running this.
        print("\nNo published section figures recorded in", args.reference)
        print("The threshold is derived, not validated. Add sections with cited sources to")
        print("check it - see that file's `_schema` for the shape, and lib/elevation_gain.py")
        print("for why one end-to-end number is not a substitute.")
        return 1

    print(f"\nper-section, at {DEFAULT_THRESHOLD_M} m (tolerance {SECTION_TOLERANCE:.0%})")
    rows = check_sections(profile, sections, DEFAULT_THRESHOLD_FT, suspect_steps=suspect)
    failed = []
    unvalidated = []
    for row in rows:
        # A null published figure is a stub awaiting its citation, not a
        # failed comparison: it renders as "-" and stays out of the verdict,
        # because "not validated" and "validated and wrong" are the two
        # states this whole file exists to keep apart.
        if row["error"] is None:
            print(f"   -  {row['name']:<28} {row['measured_ft']:>9,.0f} vs         - ft       -   {row['source']}")
            unvalidated.append(row["name"])
            continue
        # A section with an impossible step inside it lands in that same
        # third state, and it is the more dangerous of the two: its measured
        # figure is inflated by an amount that has nothing to do with the
        # threshold, so BOTH answers are worthless. Passing would record the
        # threshold as validated by a phantom climb; failing would send
        # somebody to tune a dead band that is not the problem.
        if row["contaminated"]:
            print(
                f"   ?  {row['name']:<28} {row['measured_ft']:>9,.0f} vs {row['published_ft']:>9,.0f} ft"
                f"  +{row['contaminated_ft']:,.0f} ft impossible   {row['source']}"
            )
            unvalidated.append(row["name"])
            continue
        mark = "ok " if row["within_tolerance"] else "OFF"
        own_tolerance = f" (±{row['tolerance']:.0%})" if row["tolerance"] != SECTION_TOLERANCE else ""
        print(
            f"  {mark} {row['name']:<28} {row['measured_ft']:>9,.0f} vs {row['published_ft']:>9,.0f} ft  {row['error']:+6.1%}"
            f"{own_tolerance}   {row['source']}"
        )
        if not row["within_tolerance"]:
            failed.append(row["name"])

    contaminated = [row["name"] for row in rows if row["contaminated"]]
    missing = [row["name"] for row in rows if row["error"] is None and not row["contaminated"]]
    if missing:
        print(f"\n{len(missing)} of {len(rows)} sections have no published figure yet: {', '.join(missing)}")
    if contaminated:
        print(f"\n{len(contaminated)} of {len(rows)} sections contain a step too steep to be trail: {', '.join(contaminated)}")
        print("Their measured gain is inflated by a geometry fault, not by the dead band, so")
        print("neither a pass nor a failure would mean anything. Fix #559 before citing these.")

    if failed:
        print(f"\n{len(failed)} of {len(rows)} sections outside their tolerance: {', '.join(failed)}")
        return 1

    checked = len(rows) - len(unvalidated)
    if checked == 0:
        # Same verdict as an empty section list: nothing has been validated.
        print("\nNo section has a published figure to compare against yet.")
        return 1

    print(f"\nAll {checked} sections with published figures inside their tolerance at one threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
