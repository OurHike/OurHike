"""Measure how far a mile walked along the Long Path layer lands from where
NYNJTC says the place is - the number lib/nynjtc_long_path_guide.py's
INTERPOLATION_ERROR_M rests on.

    cd pipeline && python spike_long_path_guide_placement.py
    # or, against pages cached somewhere else:
    python spike_long_path_guide_placement.py --pages-dir /path --lines /path/nynjtc_long_path.geojson

THE MEASUREMENT. The guide's Parking entries carry both a mile ("1.50") and
NYNJTC's own coordinates ("(40.85181°, -73.96245°)"). Those are the only
entries where the estimate and the truth sit side by side, so every one of
them is walked along its section's line - two ways, raw metres and scaled to
the section's stated distance - and the distance to the stated point is
recorded. A parking lot sits OFF the tread by construction (a car cannot
park on a footpath), so this measures the interpolation's error PLUS the
lot's genuine offset, which makes it a ceiling on the error for a spring or
a lean-to beside the trail rather than an estimate of it. A ceiling is the
right thing to carry on a safety path.

RESULT, measured 2026-09-08 on all forty pages against the live layer
(`Long_Path_2023/FeatureServer/0`, dataLastEditDate 2026-08-04):

    entries with both a mile and coordinates   see the run's own output
    scaled to stated distance (the method used)  median / p90 / max in the output
    raw metres along the line                    the same, for comparison

The script prints the table because the numbers move when NYNJTC edits a
page or republishes the layer; the commit that set INTERPOLATION_ERROR_M
carries the run it was set from in its pull request.

ALSO PRINTED, because a reader deciding whether to trust the pins wants
them: every WATER candidate the classifier found, in full, since that is
the safety path and a list of forty lines is readable in one sitting; the
per-type counts; the gaps between consecutive sections' ends (continuity of
the layer, which the orientation rule depends on); and every reason an
entry was not placed.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from lib.nynjtc_long_path_guide import (
    LINE_SOURCE_KEY,
    Section,
    build_records,
    classify,
    haversine_m,
    interpolate,
    line_length_m,
    parse_section,
    point_at_fraction,
    section_lines,
)

ROOT = Path(__file__).parent
DEFAULT_PAGES = ROOT / "data" / "raw" / "nynjtc_long_path_guide"
DEFAULT_LINES = ROOT / "data" / "raw" / "external" / f"{LINE_SOURCE_KEY}.geojson"
METERS_PER_MILE = 1609.344


def load_sections(pages_dir: Path) -> list[Section]:
    sections = []
    for path in sorted(pages_dir.glob("lp-section-*.html"), key=lambda p: int(p.stem.rsplit("-", 1)[1])):
        number = int(path.stem.rsplit("-", 1)[1])
        sections.append(parse_section(path.read_text(encoding="utf-8"), f"https://www.nynjtc.org/lp-section-{number}/", number))
    if not sections:
        raise SystemExit(f"no lp-section-N.html pages under {pages_dir} - run fetch_nynjtc_long_path_guide.py first")
    return sections


def quantiles(values: list[float]) -> str:
    if not values:
        return "n=0"
    values = sorted(values)
    p90 = values[min(len(values) - 1, int(round(0.9 * (len(values) - 1))))]
    return f"n={len(values)}  median {statistics.median(values):.0f} m  p90 {p90:.0f} m  max {values[-1]:.0f} m"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--lines", type=Path, default=DEFAULT_LINES)
    args = parser.parse_args()

    sections = load_sections(args.pages_dir)
    features = json.loads(args.lines.read_text(encoding="utf-8"))["features"]
    lines = section_lines(features)

    print(f"{len(sections)} sections parsed, {len(lines)} sections with a line in the layer\n")

    print("section  stated mi  line mi  ratio   parking  camping  description  coords")
    for s in sections:
        line = lines.get(s.number)
        length = line_length_m(line) / METERS_PER_MILE if line else float("nan")
        ratio = length / s.distance_miles if line and s.distance_miles else float("nan")
        coords = sum(1 for e in s.parking + s.camping + s.description if e.lat is not None)
        print(
            f"{s.number:>7}  {s.distance_miles!s:>9}  {length:7.2f}  {ratio:5.3f}   {len(s.parking):>7}  {len(s.camping):>7}  {len(s.description):>11}  {coords:>6}"
        )

    print("\nContinuity: distance from each section's end to the next section's start")
    gaps = []
    for number in sorted(lines):
        if number + 1 in lines:
            gaps.append((number, haversine_m(lines[number][-1], lines[number + 1][0])))
    for number, gap in gaps:
        if gap > 50:
            print(f"  {number} -> {number + 1}: {gap:.0f} m")
    print(f"  largest gap {max(g for _, g in gaps):.0f} m over {len(gaps)} joins")

    print("\nInterpolation error on the entries carrying both a mile and coordinates")
    scaled, raw, rows = [], [], []
    for s in sections:
        line = lines.get(s.number)
        if line is None or not s.distance_miles:
            continue
        for e in s.parking + s.camping + s.description:
            if e.lat is None or e.mile > s.distance_miles + 0.05:
                continue
            stated = (e.lon, e.lat)
            a = interpolate(line, e.mile, s.distance_miles)
            b = point_at_fraction(line, (e.mile * METERS_PER_MILE) / line_length_m(line))
            da, db = haversine_m(a, stated), haversine_m(b, stated)
            scaled.append(da)
            raw.append(db)
            rows.append((da, s.number, e.mile, e.off_trail_miles, e.text[:70]))
    print(f"  scaled to stated distance:  {quantiles(scaled)}")
    print(f"  raw metres along the line:  {quantiles(raw)}")
    on_trail = [r[0] for r in rows if r[3] is None]
    print(f"  scaled, entries stating no off-trail distance:  {quantiles(on_trail)}")
    print("  worst ten (scaled):")
    for da, number, mile, off, text in sorted(rows, reverse=True)[:10]:
        print(f"    {da:6.0f} m  s{number:<2} {mile:6.2f}  off={off}  {text}")

    print("\nWater candidates, every one (the safety path):")
    for s in sections:
        for block, entries in (("camping", s.camping), ("description", s.description)):
            for e in entries:
                if "water" in classify(e.text):
                    print(f"  s{s.number:<2} {e.mile:6.2f} [{block}] {e.text[:150]}")

    records, stats = build_records(sections, features)
    print(f"\nRecords: {stats['kept']}  by type {stats['by_type']}")
    print(f"  placed: {stats['entries_placed']}   low confidence: {stats['low_confidence']}")
    print("  skipped:")
    for reason, count in stats["skipped"].items():
        print(f"    {count:>4}  {reason}")
    for poi_type in ("shelter", "campsite", "privy"):
        print(f"\n{poi_type} records:")
        for r in records:
            if r["poi_type"] == poi_type:
                print(f"  s{r['lp_section']:<2} {r['section_mile']:6.2f} {r['placement']:<12} {r['name'] or '-'}")
    views = [r for r in records if r["poi_type"] == "viewpoint"]
    print(f"\nviewpoint records: {len(views)}; first ten:")
    for r in views[:10]:
        print(f"  s{r['lp_section']:<2} {r['section_mile']:6.2f} {r['name'] or '-'}")


if __name__ == "__main__":
    main()
