"""Measure OurHike's water against a commercial guidebook — #97's validation
step 2, run and recorded rather than described.

#97 asks for two checks before NHD stream crossings can be trusted as a
water-source candidate list: put a sample on a map, and **cross-reference
against a verifiable source** to measure real overlap versus gap rather than
comparing raw totals. This is the second one. It ran against the maintainer's
own copy of The A.T. Guide (2025 edition) on 2026-08-14, and the results it
produced are recorded at the bottom of this docstring.

## The copyright position, which decides the shape of this file

**The A.T. Guide is copyright AntiGravityGear, LLC, all rights reserved**, and
[SOURCE_SURVEY.md](SOURCE_SURVEY.md) §8 files it under "closed, no path —
context only". Nothing here changes that. This script reads a copy the
maintainer bought in order to produce **statistics about our own data** — how
much of a guidebook's water we have something at, and how much of what we
publish a guidebook corroborates — and those statistics are ours to report.

So the file is arranged around one rule: **no guidebook row is written
anywhere.** The parse happens in memory, the results file holds counts and
percentages only, and the PDF itself lives in `personal_reference/`, the first
line of the repository's `.gitignore`. `.github/tests/test_no_committed_data.py`
holds the general form of that rule and why a commit is the one publication
that cannot be retracted.

That is also why the guide is a **parameter and not a dependency**: it is one
person's book, on one person's disk. Every other machine — CI, a contributor's
laptop, a future session — runs this script and gets told the PDF is missing,
which is correct. What survives on those machines is the method and the
numbers below, which is what a spike is for.

## Putting a guidebook and a hydrography on the same ruler

The guide numbers its rows in NoBo miles from Springer. Our features are
coordinates. ATC publishes 4,395 half-mile points along its own centerline,
each carrying its `Measure` in miles, so those are the shared ruler: a feature
is placed by projecting it onto the segment between the two mileposts that
bracket it and interpolating along that segment. Snapping to the nearest
milepost instead would quantise every position to ±0.25 mi, which is coarser
than the 0.1 mi the guide states its own rows to — the comparison would be
measuring its own rounding.

**The two mileages are not assumed to agree.** ATC remeasures its centerline,
the guide remeasures the walk, relocations land in one before the other, and a
systematic offset between them would turn agreement into apparent misses.
So the offset is measured first, from the minority of guide rows that print
coordinates, and — this is the part the first run got wrong — **interpolated
along the trail rather than averaged into one number.** Two independent
measurements of a 2,197-mile footpath drift apart and back; a single shift
fitted to the middle misplaces both ends.

## What the answer is worth

A match here is "the guide lists water within ±0.2 mi of something we
publish". It is not proof that we found *that* water: two sources within a
fifth of a mile of each other on a trail whose water averages one source every
two miles is strong evidence, not identity. The number that carries the
weight is the **stream** row, because a crossing and a guidebook's "Trout
Creek" are claiming the same physical thing in the same place, computed from
hydrography that has never seen the guidebook.

## Results, measured 2026-08-14

Against `data/raw/trail_water.json` as PR #695 — Give a shelter the water it
can walk to, and the map the water the trail crosses — published it, plus the
OSM and opentrail water points `export_poi.py` folds in:

    2854 rows parsed from the guide, 2693 consistent with a 2197.4-mile trail
    4395 ATC mileposts; 980 guide water rows
      ours:  1125 crossing
      ours:    39 site_water
      ours:   438 point_source

    mileage offset (ATC minus guide), from 44 on-trail rows with coordinates:
      median +0.51 mi, range -0.75 to +0.79
      control points span guide miles 17 to 2165

    agreement at +/-0.2 mi, guide miles aligned by the interpolated offset:
      all water rows    980 rows |  538 (55%) any OurHike water |  397 (41%) a crossing
      reliable only     873 rows |  495 (57%) any OurHike water |  376 (43%) a crossing
      seasonal only     102 rows |   42 (41%) any OurHike water |   21 (21%) a crossing

    by what the row describes:
      stream     460 rows | crossing within 0.2mi:  302 (66%) | any of ours:  320 (70%)
      other      310 rows | crossing within 0.2mi:   75 (24%) | any of ours:  141 (45%)
      spring     210 rows | crossing within 0.2mi:   20 (10%) | any of ours:   77 (37%)

    of our 1125 crossings, 455 (40%) sit within 0.2 mi of a guide water row

The 980 water rows land where #97 estimated (~989) from the book's own
advertised count, which is the check that the parse is not quietly dropping a
tenth of the table — the first three attempts at it were, in three different
ways (case-sensitive codes, rows run together by the text layer, and shelter
rows whose bracketed capacities stopped the code pattern dead).

Three readings, recorded on #97 and repeated here so the file carries its own
conclusion:

  - **The crossings do what they claim.** Two thirds of the guidebook's stream
    rows have one of our crossings within a fifth of a mile. That is the
    positional confirmation the issue wanted, and it bears on step 1 as well:
    a centerline systematically misaligned against the hydrography would not
    agree with a third, independent source this often.
  - **Springs are the structural gap, at 10%.** A spring does not cross the
    trail — you walk to it — so a crossing cannot find one by construction.
    The 37% that any OurHike water reaches comes from OSM's mapped points, and
    is the same shape #529 measured from the shelter end.
  - **60% of our crossings are not guidebook water**, which is #97's own
    warning ("full of minor unnamed streams no guidebook would list") measured
    instead of feared. It is the argument for what shipped: crossings publish
    as the `crossing` poi_type and never as water pins, because "the trail
    crosses a mapped stream here" and "there is water here" are different
    claims.

**Step 1 remains open.** Nothing here puts a sample on a map, which is the
check that catches a plausible-but-wrong crossing.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_ROOT.parent
RAW_DIR = PIPELINE_ROOT / "data" / "raw"

OUT_DIR = Path(os.environ.get("OUT_DIR", PIPELINE_ROOT / "data" / "spike"))
RESULTS_PATH = OUT_DIR / "guide_water_check_results.json"

#: The guidebook, as a parameter. Absent on every machine but one, and the
#: run says so rather than failing obscurely.
GUIDE_PDF = Path(os.environ.get("GUIDE_PDF", REPO_ROOT / "personal_reference" / "at_guide.pdf"))

MILEPOSTS_PATH = RAW_DIR / "half_mile_points_from_springer.geojson"
TRAIL_WATER_PATH = RAW_DIR / "trail_water.json"
OSM_WATER_PATH = RAW_DIR / "osm_water.geojson"
OPENTRAIL_PATH = RAW_DIR / "opentrail_at.geojson"

M_PER_DEG_LAT = 111_132.0

#: How close in trail miles counts as "the same water". The guide states rows
#: to 0.1 mi; our placement carries the interpolation's own error plus
#: whatever the two mileages still disagree by after alignment. 0.2 is loose
#: enough to survive that and tight enough that a match means something —
#: guidebook water averages one row every ~2.2 miles, so a 0.4-mile window is
#: not fishing.
MATCH_MI = 0.2

#: A coordinate-bearing guide row only calibrates the two mileages if the
#: coordinate really is on the trail. The guide prints positions for road
#: crossings and trailheads too, and one of those sitting half a mile off the
#: footpath would drag the offset curve with it.
CONTROL_MAX_OFFSET_M = 200.0

#: A point source this far off the trail is real water and not water a hiker
#: walking past would be offered. The guide only lists the second kind, so
#: counting the first would manufacture misses.
POINT_SOURCE_MAX_OFFSET_M = 1000.0

# --- reading the guide's mile table ----------------------------------------

#: The guide's own legend, page 2. Kept apart rather than collapsed into
#: "water", because a seasonal source is the one a hiker plans around, and
#: folding it in with the reliable ones would make this cross-check agree with
#: us for the wrong reason. Case is the whole distinction and cost this parse
#: a third of its rows on the first run: `"w" in codes` finds every reliable
#: source and silently drops every seasonal one.
WATER_CODES = {"w": "reliable", "W": "seasonal", "J": "potable_tap"}

#: Row starts, found ANYWHERE in the page text rather than anchored to a line.
#: The text layer runs consecutive rows together — one row's elevation and the
#: next row's mile arrive as a single token — so a line-anchored pattern reads
#: the first row on each extracted line and silently drops the rest. That cost
#: this parse two thirds of the table before the count was checked against the
#: book's own claim.
#:
#: Nothing here has to work out where the elevation ends and the mile begins:
#: the leftmost match that satisfies the pattern is the right one, and the
#: NoBo+SoBo sum check throws out any row where it was not.
ROW_START = re.compile(r"(?P<sobo>\d{1,4}\.\d)\s+(?P<nobo>\d{1,4}\.\d)\s")

#: The dot leader separating a row's description from its codes — the only
#: reliable landmark left in a flattened text layer.
LEADER = re.compile(r"(?:\.\s+){4,}\.?")

#: The code run that follows it. Letters, but also digits and brackets,
#: because two codes carry a number — `s(7)` is a shelter sleeping seven,
#: `t(4)` four tent sites — and a pattern of bare letters stops dead at the
#: first bracket. That is what it did: shelter rows read `pwt(4)s(7)/` and
#: were dropped whole, which cost the parse most of the shelters, and a
#: shelter row is the one most likely to carry water.
CODE_RUN = re.compile(r"[A-Za-z][A-Za-z0-9()/,]*")

#: Stripped before the codes are looked for, because a row that prints
#: coordinates puts them exactly where the codes would otherwise start.
COORD_STRIP = re.compile(r"\d{2}\s*\.\s*\d{3,6}\s*,\s*-\d{2,3}\s*\.\s*\d{3,6}")

#: Coordinates, with the spaces the text layer sprinkles through decimals.
COORDS = re.compile(r"(?P<lat>\d{2}\s*\.\s*\d{3,6})\s*,\s*(?P<lon>-\d{2,3}\s*\.\s*\d{3,6})")

ELEVATION = re.compile(r"(?P<elevation>-?\d{2,5})\s*$")

#: NoBo and SoBo miles sum to the trail's length in whichever edition this
#: is, and every row prints both — so the sum is a per-row parse check rather
#: than a constant to look up. A row whose halves disagree with the rest of
#: the book by more than this is a misparse and is dropped.
LENGTH_TOLERANCE_MI = 1.0

#: What the row is about, which is the breakdown that carries the finding: a
#: crossing and a guidebook's "Trout Creek" claim the same thing, a crossing
#: and a spring cannot. Springs win ties — "Spring, 200 yds down blue blaze to
#: creek" is a spring row.
SPRING_WORD = re.compile(r"\bspring", re.IGNORECASE)

#: Matched at a word start rather than as whole words, so plurals and
#: possessives count ("Creeks", "Rock Run's outlet"). "run" is a genuine
#: Appalachian stream word and earns its place; it is also the one entry here
#: loose enough to catch a verb, which is worth knowing before quoting the
#: stream count to two significant figures.
STREAM_WORD = re.compile(r"\b(?:creek|brook|river|stream|fork|run)", re.IGNORECASE)


def clean_number(text: str) -> float:
    return float(text.replace(" ", ""))


def parse_page(text: str) -> list[dict]:
    """Every mile-table row in one page's flattened text."""
    rows: list[dict] = []
    starts = list(ROW_START.finditer(text))
    for index, match in enumerate(starts):
        sobo, nobo = float(match["sobo"]), float(match["nobo"])
        # This row runs to wherever the next one begins.
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        rest = text[match.end() : end]

        coords = COORDS.search(rest)
        # Everything after the last dot leader is the codes and what follows
        # them; before it is prose, which may contain any letter at all.
        pieces = LEADER.split(rest)
        after = COORD_STRIP.sub(" ", pieces[-1] if len(pieces) > 1 else "").strip()
        run = CODE_RUN.match(after)
        elevation = ELEVATION.search(after)
        rows.append(
            {
                "nobo_mile": nobo,
                "sobo_mile": sobo,
                "length_check": round(nobo + sobo, 1),
                # Letters only: a digit inside a code is a capacity, not a
                # code of its own.
                "codes": "".join(char for char in run.group(0) if char.isalpha()) if run else "",
                "elevation_ft": int(elevation["elevation"]) if elevation else None,
                "lat": clean_number(coords["lat"]) if coords else None,
                "lon": clean_number(coords["lon"]) if coords else None,
                "description": (pieces[0].strip()[:120] if pieces else ""),
            }
        )
    return rows


def read_guide(pdf_path: Path) -> list[dict]:
    """The guide's water rows, in memory and going no further.

    pypdf is imported here rather than at module top, following
    `fetch_club_pdfs.py`: it is not in `requirements.txt` (requirements.in
    says why), and a spike nobody but the maintainer can run should not make
    the whole pipeline carry a dependency for it.
    """
    try:
        import pypdf
    except ModuleNotFoundError as error:  # pragma: no cover - environment
        raise SystemExit(
            "spike_guide_water_check.py needs pypdf to read the guide - `pip install pypdf` "
            "(pure Python, ~2MB; requirements.in explains why it is not pinned)."
        ) from error

    reader = pypdf.PdfReader(str(pdf_path))
    rows: list[dict] = []
    for page in reader.pages:
        rows.extend(parse_page((page.extract_text() or "").replace("\n", " ")))
    if not rows:
        raise SystemExit(f"No mile-table rows parsed from {pdf_path} - the text layer or the layout has changed.")

    # The book's own length, taken as the median of every row's two halves,
    # then used to throw out the rows whose halves disagree with it.
    lengths = sorted(row["length_check"] for row in rows)
    trail_length = lengths[len(lengths) // 2]
    good = [row for row in rows if abs(row["length_check"] - trail_length) <= LENGTH_TOLERANCE_MI]
    for row in good:
        row["water_kinds"] = sorted(WATER_CODES[code] for code in set(row["codes"]) if code in WATER_CODES)
        row["describes"] = describes(row["description"])
    print(f"{len(rows)} rows parsed from the guide, {len(good)} consistent with a {trail_length:.1f}-mile trail")
    return [row for row in good if row["water_kinds"]]


def describes(description: str) -> str:
    if SPRING_WORD.search(description):
        return "spring"
    if STREAM_WORD.search(description):
        return "stream"
    return "other"


# --- putting both on ATC's ruler -------------------------------------------


def load_mileposts(path: Path = MILEPOSTS_PATH) -> list[tuple[float, float, float]]:
    """(mile, lat, lon) for ATC's half-mile points, in mile order."""
    posts = []
    for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
        mile = (feature.get("properties") or {}).get("Measure")
        geometry = feature.get("geometry") or {}
        if mile is None or geometry.get("type") != "Point":
            continue
        lon, lat = geometry["coordinates"][:2]
        posts.append((float(mile), lat, lon))
    posts.sort()
    return posts


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Equirectangular distance, the approximation the rest of the pipeline
    uses at corridor scale (`lib/spurs.py`) — good to well under a metre over
    the half-mile spans this file measures."""
    mx = M_PER_DEG_LAT * math.cos(math.radians(lat1))
    return math.hypot((lon2 - lon1) * mx, (lat2 - lat1) * M_PER_DEG_LAT)


def trail_mile(lat: float, lon: float, posts: list[tuple[float, float, float]]) -> tuple[float, float]:
    """(mile, metres off the milepost line) for one coordinate.

    Projected onto the segment between the bracketing mileposts, so the answer
    is continuous rather than snapped to the nearest half mile. The second
    value is how far the point sits from that segment: a feature hundreds of
    metres off the trail is placed less confidently, and every caller here
    uses that to decide whether to trust the placement at all.
    """
    nearest = min(range(len(posts)), key=lambda index: metres(lat, lon, posts[index][1], posts[index][2]))
    best = (posts[nearest][0], metres(lat, lon, posts[nearest][1], posts[nearest][2]))
    for other in (nearest - 1, nearest + 1):
        if not 0 <= other < len(posts):
            continue
        mile_a, lat_a, lon_a = posts[nearest]
        mile_b, lat_b, lon_b = posts[other]
        mx = M_PER_DEG_LAT * math.cos(math.radians(lat_a))
        bx, by = (lon_b - lon_a) * mx, (lat_b - lat_a) * M_PER_DEG_LAT
        px, py = (lon - lon_a) * mx, (lat - lat_a) * M_PER_DEG_LAT
        length_sq = bx**2 + by**2
        if length_sq == 0:
            continue
        along = max(0.0, min(1.0, (px * bx + py * by) / length_sq))
        offset = math.hypot(px - along * bx, py - along * by)
        if offset < best[1]:
            best = (mile_a + along * (mile_b - mile_a), offset)
    return best


def our_features(posts: list[tuple[float, float, float]]) -> dict[str, list[float]]:
    """Every water feature OurHike publishes, as trail miles, by kind."""
    features: dict[str, list[float]] = {"crossing": [], "site_water": [], "point_source": []}

    trail_water = json.loads(TRAIL_WATER_PATH.read_text(encoding="utf-8"))
    for crossing in trail_water["crossings"]:
        features["crossing"].append(trail_mile(crossing["lat"], crossing["lon"], posts)[0])
    for site in trail_water["sites"]:
        if site.get("water"):
            features["site_water"].append(trail_mile(site["water"]["lat"], site["water"]["lon"], posts)[0])

    # The published water pins, from the two sources export_poi.py folds into
    # poi_type `water`: every OSM node fetch_osm_water.py keeps, and
    # opentrail's `w`/`s` icons.
    sources = (
        (OSM_WATER_PATH, lambda properties: True),
        (OPENTRAIL_PATH, lambda properties: properties.get("icon") in ("w", "s")),
    )
    for path, keep in sources:
        if not path.exists():
            print(f"  (no {path.name} - point sources from it are not counted)")
            continue
        for feature in json.loads(path.read_text(encoding="utf-8"))["features"]:
            geometry = feature.get("geometry") or {}
            if geometry.get("type") != "Point" or not keep(feature.get("properties") or {}):
                continue
            lon, lat = geometry["coordinates"][:2]
            mile, offset = trail_mile(lat, lon, posts)
            if offset <= POINT_SOURCE_MAX_OFFSET_M:
                features["point_source"].append(mile)
    return features


def control_points(guide: list[dict], posts: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    """(guide mile, ATC mile minus guide mile) for the rows that print an
    on-trail coordinate — the measured disagreement between the two rulers."""
    controls = []
    for row in guide:
        if row["lat"] is None:
            continue
        placed, offset_m = trail_mile(row["lat"], row["lon"], posts)
        if offset_m <= CONTROL_MAX_OFFSET_M:
            controls.append((row["nobo_mile"], placed - row["nobo_mile"]))
    controls.sort()
    return controls


def offset_at(mile: float, controls: list[tuple[float, float]]) -> float:
    """The two mileages' disagreement at a point, interpolated between the
    control points and held flat beyond the outermost ones."""
    if not controls:
        return 0.0
    if mile <= controls[0][0]:
        return controls[0][1]
    if mile >= controls[-1][0]:
        return controls[-1][1]
    for (mile_a, offset_a), (mile_b, offset_b) in zip(controls, controls[1:]):
        if mile_a <= mile <= mile_b:
            span = mile_b - mile_a
            if span == 0:
                return offset_a
            return offset_a + (mile - mile_a) / span * (offset_b - offset_a)
    return controls[-1][1]


def nearest_gap(mile: float, ours: list[float]) -> float:
    return min((abs(mile - other) for other in ours), default=math.inf)


def agreement(subset: list[dict], controls, everything: list[float], crossings: list[float]) -> dict:
    """How much of one slice of the guide's water we have something at."""
    aligned = [row["nobo_mile"] + offset_at(row["nobo_mile"], controls) for row in subset]
    any_water = sum(1 for mile in aligned if nearest_gap(mile, everything) <= MATCH_MI)
    a_crossing = sum(1 for mile in aligned if nearest_gap(mile, crossings) <= MATCH_MI)
    return {"rows": len(subset), "any_water": any_water, "crossing": a_crossing}


def share(part: int, whole: int) -> str:
    return f"{part / whole:.0%}" if whole else "n/a"


def results_payload(
    *,
    features: dict[str, list[float]],
    guide_rows: int,
    controls: list[tuple[float, float]],
    by_reliability: dict[str, dict],
    by_description: dict[str, dict],
    corroborated: int,
) -> dict:
    """What gets written to disk: counts and percentages, and nothing else.

    Built as its own function so the rule at the top of this file is a thing a
    test can check rather than a thing the author remembered. Every leaf here
    is a number - a statement about OurHike's data, or about how many
    guidebook rows fell into a bucket. Nothing that could reconstruct a row,
    a position or a description.
    """
    offsets = sorted(offset for _, offset in controls)
    return {
        "_README": "Aggregate counts only - no guidebook content. spike_guide_water_check.py says why.",
        "match_mi": MATCH_MI,
        "guide_water_rows": guide_rows,
        "ours": {kind: len(miles) for kind, miles in features.items()},
        "mileage_offset_mi": {
            "control_points": len(controls),
            "median": round(offsets[len(offsets) // 2], 3) if offsets else None,
            "min": round(offsets[0], 3) if offsets else None,
            "max": round(offsets[-1], 3) if offsets else None,
        },
        "by_reliability": by_reliability,
        "by_description": by_description,
        "crossings_corroborated": corroborated,
    }


def main(argv: list[str] | None = None) -> int:
    for path in (GUIDE_PDF, MILEPOSTS_PATH, TRAIL_WATER_PATH):
        if not path.exists():
            print(f"{path} is missing.")
            if path == GUIDE_PDF:
                print(
                    "  The A.T. Guide is a personal copy, not a repository asset - this spike is\n"
                    "  reproducible only on a machine that has one. Set GUIDE_PDF to point at it.\n"
                    "  The results of the run that has been done are in this file's docstring."
                )
            return 1

    posts = load_mileposts()
    guide = read_guide(GUIDE_PDF)
    print(f"{len(posts)} ATC mileposts; {len(guide)} guide water rows")

    features = our_features(posts)
    for kind, miles in features.items():
        print(f"  ours: {len(miles):>5} {kind}")
    everything = sorted(mile for miles in features.values() for mile in miles)
    crossings = sorted(features["crossing"])

    controls = control_points(guide, posts)
    offsets = sorted(offset for _, offset in controls)
    if controls:
        print(f"\nmileage offset (ATC minus guide), from {len(controls)} on-trail rows with coordinates:")
        print(f"  median {offsets[len(offsets) // 2]:+.2f} mi, range {offsets[0]:+.2f} to {offsets[-1]:+.2f}")
        print(f"  control points span guide miles {controls[0][0]:.0f} to {controls[-1][0]:.0f}")
    else:
        print("\nno on-trail control points - the two mileages are compared unaligned")

    print(f"\nagreement at +/-{MATCH_MI} mi, guide miles aligned by the interpolated offset:")
    by_reliability = {}
    for label, subset in (
        ("all water rows", guide),
        ("reliable only", [row for row in guide if "reliable" in row["water_kinds"]]),
        ("seasonal only", [row for row in guide if "seasonal" in row["water_kinds"]]),
    ):
        result = by_reliability[label] = agreement(subset, controls, everything, crossings)
        print(
            f"  {label:16} {result['rows']:>4} rows | {result['any_water']:>4} "
            f"({share(result['any_water'], result['rows'])}) any OurHike water | "
            f"{result['crossing']:>4} ({share(result['crossing'], result['rows'])}) a crossing"
        )

    print("\nby what the row describes:")
    by_description = {}
    for kind in ("stream", "other", "spring"):
        subset = [row for row in guide if row["describes"] == kind]
        result = by_description[kind] = agreement(subset, controls, everything, crossings)
        print(
            f"  {kind:9} {result['rows']:>4} rows | crossing within {MATCH_MI}mi: "
            f"{result['crossing']:>4} ({share(result['crossing'], result['rows'])}) | "
            f"any of ours: {result['any_water']:>4} ({share(result['any_water'], result['rows'])})"
        )

    guide_miles = sorted(row["nobo_mile"] + offset_at(row["nobo_mile"], controls) for row in guide)
    corroborated = sum(1 for mile in crossings if nearest_gap(mile, guide_miles) <= MATCH_MI)
    print(
        f"\nof our {len(crossings)} crossings, {corroborated} ({share(corroborated, len(crossings))}) "
        f"sit within {MATCH_MI} mi of a guide water row"
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = results_payload(
        features=features,
        guide_rows=len(guide),
        controls=controls,
        by_reliability=by_reliability,
        by_description=by_description,
        corroborated=corroborated,
    )
    RESULTS_PATH.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"Wrote {RESULTS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
