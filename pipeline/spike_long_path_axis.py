"""Does the Long Path's guide mileage add up to an axis a hiker could navigate by?

    cd pipeline && python spike_long_path_axis.py

THE QUESTION, and why it is not the one spike_long_path_guide_placement.py
already answered. That spike measured placement WITHIN a section: walk the
guide's mile along the section's own line and see how far from NYNJTC's
stated point you land (median 86 m, p90 476 m). It says nothing about
whether the forty sections compose. A cumulative axis - section 1's miles,
then section 2's on top, all the way to the Adirondacks - is only as honest
as the agreement between each section's PUBLISHED length and the length of
the line the layer actually draws for it. Where those disagree, every mile
north of the disagreement inherits the error, and the error accumulates.

So this measures the composition:

  * per section, the guide's `Distance: N miles` header against the geodesic
    length of that section's chained line;
  * the drift between the two cumulative axes at every section boundary -
    which is the number that decides whether "mi 231" in this app and
    "mi 231" in NYNJTC's guide are the same place;
  * the gaps between one section's end and the next one's start, because a
    layer that does not physically continue is a layer whose summed length
    is missing trail.

WHAT IT DELIBERATELY DOES NOT DO. It does not pick an axis, publish one, or
write anything into `mile`. #1368 is where the choice between a
published-mileage axis and a geometry axis is argued; this is the evidence
that argument was missing.

RESULT, measured 2026-09-09 against all forty cached pages and the live
layer (`Long_Path_2023/FeatureServer/0`, 43 features):

    guide's published total     433.95 mi
    layer's geometry total      415.11 mi
    end-to-end drift            -18.84 mi  (-4.3%)

    per-section |difference|    median 0.47 mi / 4.5%, p90 0.85 mi / 10.1%,
                                max 2.15 mi / 16.6% (section 21)

The geometry is shorter than the guide in 37 of 40 sections, and the drift
accumulates monotonically: -1.98 mi by section 5, -9.63 by section 20,
-18.84 by the Adirondacks. THAT IS THE FINDING. The two candidate axes in
#1368 are not two roundings of one number - they are nineteen miles apart at
the northern end, which is #753's "this codebase measures a mile two
different ways" arriving on a second trail.

THREE EXPLANATIONS TESTED AND RULED OUT, so the number cannot be waved away:

  * Missing trail at the seams. No: all 39 section boundaries meet at 0 m.
    The layer is one continuous line end to end.
  * A coarsely drawn line cutting corners. No: the line carries a median 111
    vertices per mile (median step 11.6 m), and the correlation between
    shortfall and vertex density is -0.327 - the WRONG SIGN. Section 19 is
    digitised at 0.3 m steps and still runs 10.4% short.
  * The sections not composing. No: they compose exactly; it is the
    published numbers and the drawn line that disagree, inside sections.

WHAT THIS DOES NOT SETTLE, and it is the maintainer's call in #1368: which
of the two is right. The published distances are all multiples of 0.05 mi,
which reads as hand-maintained rather than re-measured, and they may include
road walks or approaches the layer does not draw. Nothing here can say.

WHAT IT DOES SETTLE, and it is the useful half: a cumulative-published axis
is INTERNALLY CONSISTENT even though it disagrees with the geometry. Within
a section `interpolate()` scales mile/section_miles along the line, so a
uniform shortfall cancels - which is why placement error is a median 86 m
(spike_long_path_guide_placement.py) despite a median 4.5% length
disagreement. A geometry axis would be self-consistent too, and 18.84 mi
adrift from every printed NYNJTC source a hiker might cross-reference.

Note the three sections lib/nynjtc_long_path_guide.py flags as placing badly
(23, 25, 37) are NOT the worst here - they sit at 4.6%, 4.0% and 4.5%,
around the median. The worst are 21, 19, 22, 18, 17, all in the Catskills.
Bad placement and bad length are different faults in different places.

NO OFFICIAL TOTAL TO CHECK AGAINST. #1368 assumed NYNJTC states an
end-to-end mileage somewhere the pipeline could cite. The forty cached
section pages and the guide index do not carry one (checked 2026-09-09), so
the third number that issue asked for does not exist in the data this
project holds, and the two axes below are compared to each other rather than
to a published total.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from lib.nynjtc_long_path_guide import (
    LINE_SOURCE_KEY,
    METERS_PER_MILE,
    haversine_m,
    line_length_m,
    section_lines,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_SECTIONS = ROOT / "data" / "raw" / "nynjtc_long_path_guide" / "sections.json"
DEFAULT_LINES = ROOT / "data" / "raw" / "external" / f"{LINE_SOURCE_KEY}.geojson"

#: Sections lib/nynjtc_long_path_guide.py already measured as placing badly
#: (median 573 m, 950 m, 1,223 m) - "where the layer's line and the guide's
#: mileage plainly disagree". Marked in the table so the two measurements can
#: be read against each other.
KNOWN_BAD = {23, 25, 37}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sections", type=Path, default=DEFAULT_SECTIONS)
    parser.add_argument("--lines", type=Path, default=DEFAULT_LINES)
    args = parser.parse_args()

    if not args.sections.exists():
        raise SystemExit(f"{args.sections} missing - run fetch_nynjtc_long_path_guide.py first")
    if not args.lines.exists():
        raise SystemExit(f"{args.lines} missing - fetch the {LINE_SOURCE_KEY} layer first")

    sections = json.loads(args.sections.read_text())
    published = {int(s["number"]): s.get("distance_miles") for s in sections}
    titles = {int(s["number"]): s.get("title") or "" for s in sections}

    features = json.loads(args.lines.read_text())["features"]
    lines = section_lines(features)

    print(f"sections in the guide: {len(published)}   sections in the layer: {len(lines)}")
    missing_line = sorted(n for n in published if n not in lines)
    missing_page = sorted(n for n in lines if n not in published)
    if missing_line:
        print(f"  guide sections with NO line in the layer: {missing_line}")
    if missing_page:
        print(f"  layer sections with NO guide page: {missing_page}")
    no_distance = sorted(n for n, d in published.items() if d is None)
    if no_distance:
        print(f"  guide sections with NO published distance: {no_distance}")
    print()

    rows = []
    pub_cum = 0.0
    geo_cum = 0.0
    for number in sorted(set(published) & set(lines)):
        pub = published[number]
        geo = line_length_m(lines[number]) / METERS_PER_MILE
        if pub is None:
            continue
        pub_cum += pub
        geo_cum += geo
        rows.append(
            {
                "n": number,
                "pub": pub,
                "geo": geo,
                "diff": geo - pub,
                "pct": (geo - pub) / pub * 100 if pub else float("nan"),
                "pub_cum": pub_cum,
                "geo_cum": geo_cum,
                "drift": geo_cum - pub_cum,
                "title": titles.get(number, ""),
            }
        )

    print("per section: the guide's published distance against the line the layer draws")
    print(f"{'sec':>4} {'published':>10} {'geometry':>10} {'diff':>8} {'diff %':>8} {'cum drift':>10}  title")
    for r in rows:
        flag = " *" if r["n"] in KNOWN_BAD else "  "
        print(
            f"{r['n']:>4}{flag}{r['pub']:>8.2f} {r['geo']:>10.2f} "
            f"{r['diff']:>+8.2f} {r['pct']:>+7.1f}% {r['drift']:>+10.2f}  {r['title'][:44]}"
        )
    print("  * = a section lib/nynjtc_long_path_guide.py already measured as placing badly")
    print()

    diffs = [r["diff"] for r in rows]
    absdiffs = sorted(abs(d) for d in diffs)
    pcts = sorted(abs(r["pct"]) for r in rows)
    print("TOTALS")
    print(f"  sections compared                {len(rows)}")
    print(f"  guide's published total          {rows[-1]['pub_cum']:.2f} mi")
    print(f"  layer's geometry total           {rows[-1]['geo_cum']:.2f} mi")
    print(
        f"  end-to-end drift                 {rows[-1]['drift']:+.2f} mi ({rows[-1]['drift'] / rows[-1]['pub_cum'] * 100:+.1f}%)"
    )
    print()
    print("  per-section |difference|, miles")
    print(f"    median {statistics.median(absdiffs):.2f}   p90 {absdiffs[int(len(absdiffs) * 0.9)]:.2f}   max {absdiffs[-1]:.2f}")
    print("  per-section |difference|, percent of the published length")
    print(f"    median {statistics.median(pcts):.1f}%   p90 {pcts[int(len(pcts) * 0.9)]:.1f}%   max {pcts[-1]:.1f}%")
    print()
    worst = sorted(rows, key=lambda r: abs(r["diff"]), reverse=True)[:6]
    print("  worst six by absolute difference")
    for r in worst:
        print(
            f"    section {r['n']:>2}: published {r['pub']:.2f}, geometry {r['geo']:.2f} ({r['diff']:+.2f} mi, {r['pct']:+.1f}%)"
        )
    print()

    # The cumulative drift is what a hiker would feel: how far apart the two
    # axes have grown by the time they reach a given section.
    print("  cumulative drift at every fifth boundary (geometry minus published)")
    for r in rows:
        if r["n"] % 5 == 0 or r is rows[-1]:
            print(f"    after section {r['n']:>2}: {r['drift']:+7.2f} mi")
    print()

    # Is the shortfall just a coarsely drawn line? A generalised polyline cuts
    # corners and under-measures, so if that were the cause the sections with
    # the fewest vertices per mile would be the ones running shortest. Tested
    # rather than assumed, because it is the explanation everyone reaches for
    # first and the recommendation changes completely if it is true.
    print("IS IT A COARSE LINE? vertices per mile against the shortfall")
    density = []
    for number in sorted(set(published) & set(lines)):
        pub = published[number]
        if pub is None:
            continue
        line = lines[number]
        geo = line_length_m(line) / METERS_PER_MILE
        steps = [s for s in (haversine_m(a, b) for a, b in zip(line, line[1:])) if s > 0]
        density.append(((geo - pub) / pub * 100, len(line) / geo, statistics.median(steps), number))
    pcts = [d[0] for d in density]
    vpms = [d[1] for d in density]
    mean_p, mean_v = statistics.mean(pcts), statistics.mean(vpms)
    cov = sum((p - mean_p) * (v - mean_v) for p, v in zip(pcts, vpms))
    den = (sum((p - mean_p) ** 2 for p in pcts) * sum((v - mean_v) ** 2 for v in vpms)) ** 0.5
    steps_all = sorted(d[2] for d in density)
    print(f"  vertices per mile   median {statistics.median(vpms):.0f}   min {min(vpms):.0f}   max {max(vpms):.0f}")
    print(f"  median step between vertices   median {statistics.median(steps_all):.1f} m")
    print(f"  correlation(shortfall %, vertices per mile) = {cov / den:+.3f}")
    print("  A coarse line would show MORE shortfall where there are FEWER vertices")
    print("  (a positive correlation here, since shortfall is negative). It does not.")
    print()

    print("CONTINUITY - the gap between one section's end and the next one's start")
    gaps = []
    ordered = sorted(lines)
    for a, b in zip(ordered, ordered[1:]):
        if b != a + 1:
            continue
        gap = haversine_m(lines[a][-1], lines[b][0])
        gaps.append((a, b, gap))
    if gaps:
        sizes = sorted(g for _, _, g in gaps)
        print(f"  boundaries measured {len(gaps)}   median {statistics.median(sizes):.0f} m   max {sizes[-1]:.0f} m")
        big = [g for g in gaps if g[2] > 100]
        if big:
            print("  boundaries more than 100 m apart:")
            for a, b, gap in sorted(big, key=lambda g: -g[2]):
                print(f"    section {a} -> {b}: {gap:,.0f} m")
        else:
            print("  no boundary is more than 100 m apart")


if __name__ == "__main__":
    main()
