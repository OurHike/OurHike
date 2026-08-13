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
    cumulative_gain_over_gaps,
    gain_between,
    raw_cumulative_gain,
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
    """Total gain in feet at each threshold in SWEEP_M."""
    elevations = [record.get("elevation_ft") for record in profile]
    return [(m, cumulative_gain_over_gaps(elevations, m / METERS_PER_FOOT)) for m in SWEEP_M]


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
            steps.append({"from_mi": a["distance_mi"], "to_mi": b["distance_mi"], "delta_ft": delta})
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
    """
    suspect_steps = suspect_steps or []
    rows = []
    for section in sections:
        measured = gain_between(profile, section["start_mi"], section["end_mi"], threshold_ft)
        published = section["published_gain_ft"]
        error = None if not published else (measured - published) / published
        inside = [step for step in suspect_steps if section["start_mi"] <= step["from_mi"] and step["to_mi"] <= section["end_mi"]]
        rows.append(
            {
                "name": section["name"],
                "start_mi": section["start_mi"],
                "end_mi": section["end_mi"],
                "measured_ft": measured,
                "published_ft": published,
                "source": section.get("source", ""),
                "error": error,
                "within_tolerance": error is not None and abs(error) <= SECTION_TOLERANCE,
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
    elevations = [record.get("elevation_ft") for record in profile]

    raw = raw_cumulative_gain(elevations)
    chosen = cumulative_gain_over_gaps(elevations, DEFAULT_THRESHOLD_FT)

    print(f"{len(profile):,} samples")
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
            climbing = ascending_total(suspect)
            share = f" ({climbing / chosen:.1%} of the {DEFAULT_THRESHOLD_M} m total)" if chosen else ""
            print(f"  {len(suspect)} step(s) too steep to be trail, {climbing:,.0f} ft of it ascending{share}")
            for step in sorted(suspect, key=lambda s: abs(s["delta_ft"]), reverse=True)[:3]:
                print(f"    mi {step['from_mi']:>9.3f} -> {step['to_mi']:>9.3f}  {step['delta_ft']:+9,.0f} ft")
            # Named rather than diagnosed here: this script measures the
            # profile it is handed and cannot see part boundaries, so it says
            # what is impossible and points at the issue that knows why.
            print("  Not terrain. See #559 - cross-part boundaries summed as climbing.")

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
        print(
            f"  {mark} {row['name']:<28} {row['measured_ft']:>9,.0f} vs {row['published_ft']:>9,.0f} ft  {row['error']:+6.1%}"
            f"   {row['source']}"
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
        print(f"\n{len(failed)} of {len(rows)} sections outside {SECTION_TOLERANCE:.0%}: {', '.join(failed)}")
        return 1

    checked = len(rows) - len(unvalidated)
    if checked == 0:
        # Same verdict as an empty section list: nothing has been validated.
        print("\nNo section has a published figure to compare against yet.")
        return 1

    print(f"\nAll {checked} sections with published figures within {SECTION_TOLERANCE:.0%} at one threshold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
