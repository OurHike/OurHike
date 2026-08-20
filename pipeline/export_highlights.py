"""Publish the stretches of trail somebody says are worth going to (#595).

features/CORRIDOR_VIEW.md's second subject. Below the seam the map draws the
thirty maintained sections (#594, #598) and, on top of them, a short list of
places worth crossing a state for - each one saying WHO says so, because
"popular" is three questions with completely different evidence behind them and
the app must never blend them into one number that means none of them.

WHAT THIS SHIPS, AND WHAT IT DOES NOT

`named` only. It is the editorial basis, the weakest of the three, and the only
one that works on day one:

  - `published` cites ATC's own day-hike material and waits on that source
    being registered (features/SOURCE_REGISTRY.md). Ordinary work, not started.
  - `visited` is a count across hikers and is #596's. It is ALSO now blocked on
    an explicit decision about features/EVENTING.md rule 2 that has not been
    taken - see CORRIDOR_VIEW.md's own note. A per-hiker "you have walked this"
    ships separately from #598, computed on the phone and uploading nothing;
    that is a different fact and does not become this one.

WHERE THE JUDGEMENT IS AND WHERE THE NUMBERS ARE

reference/highlights.json is the judgement - which stretches, and why - and it
is committed so a diff of it reviews those decisions row by row. It contains no
miles at all. Each leg names two POIs, and this script resolves them against
the PUBLISHED POI records to get the range.

RUNS AFTER export_poi.py, and that ordering is load-bearing for the reason
export_spurs.py's is: the ids have to be the ones already on the device, and
the miles have to be the ones the client already agrees with. Resolving against
raw ATC points would produce a range calibrated differently from every other
mile in the app.

It also runs after export_club_sections.py where it can, but only to REPORT:
each highlight records the club whose section it starts in, so "about thirty,
one per maintaining club" is a fact this script can check instead of a claim the
reference file makes about itself. Missing club sections cost the report and
nothing else.

NOTHING DERIVED IS STORED. No length, no ascent, no Naismith time. The phone
holds ~141,000 elevation samples already and derives all three
(elevationGain.ts into naismith.ts), so a better profile improves every
highlight without a republish.

NO NETWORK - reads data/processed/, which export_poi.py and
export_club_sections.py write.

    .venv/Scripts/python export_highlights.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from lib.highlights import (
    as_published,
    clubs_without_a_highlight,
    resolve,
)
from lib.poi_schema import POI_TYPES, poi_output_name

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
POI_DIR = PROCESSED_DIR / "poi"
CLUB_SECTIONS_PATH = PROCESSED_DIR / "club_sections.json"
CURATED_PATH = ROOT / "reference" / "highlights.json"

OUT_PATH = PROCESSED_DIR / "highlights.json"
MANIFEST_PATH = PROCESSED_DIR / "highlights_manifest.json"


def load_curated(path: Path | None = None) -> list[dict]:
    """The editorial list. Absent is fatal: this script has nothing to say
    without it, and an empty highlights.json looks exactly like a trail with
    nothing on it worth going to."""
    path = CURATED_PATH if path is None else path
    if not path.exists():
        raise SystemExit(f"{path} is missing - the curated list is this script's whole input")
    return json.loads(path.read_text()).get("highlights") or []


def load_published_pois(poi_dir: Path | None = None) -> list[dict]:
    """Every published POI's properties, across every type.

    Every type rather than a chosen few, unlike export_spurs.py's destination
    list: an anchor here can be any named thing ATC carries - a summit, a
    parking area, a gap, a shelter - and narrowing the set would silently drop
    a highlight rather than refuse it.

    None-sentinel default so a test pointing the module constant elsewhere is
    actually followed, the trap export_spurs.py's own loader documents.
    """
    poi_dir = POI_DIR if poi_dir is None else poi_dir
    pois: list[dict] = []
    for poi_type in POI_TYPES:
        path = poi_dir / poi_output_name(poi_type)
        if not path.exists():
            continue
        for feature in json.loads(path.read_text()).get("features") or []:
            properties = feature.get("properties") or {}
            if properties.get("id"):
                pois.append(properties)
    return pois


def load_club_runs(path: Path | None = None) -> list[dict]:
    """The clubs, for the coverage report. Absent is not fatal - it costs the
    report and nothing that publishes."""
    path = CLUB_SECTIONS_PATH if path is None else path
    if not path.exists():
        return []
    return json.loads(path.read_text()).get("clubs") or []


def build_output(curated: list[dict], pois: list[dict], club_runs: list[dict]) -> tuple[dict, list[tuple[str, str]], list[str]]:
    resolution = resolve(curated, pois, club_runs)
    output = {
        # Named rather than dated: the reference file carries a `reviewed` date
        # per row, because rows are added one at a time and one date for the
        # file would say the whole list was last considered when its newest
        # entry was.
        "source": "reference/highlights.json",
        "highlights": [as_published(h) for h in resolution.highlights],
    }
    gaps = clubs_without_a_highlight(resolution.highlights, club_runs)
    return output, resolution.dropped, gaps


def main() -> dict:
    curated = load_curated()
    pois = load_published_pois()
    club_runs = load_club_runs()

    if not pois:
        # Not fatal and not silent, the stance export_spurs.py takes on the
        # same input: every highlight would drop, which looks exactly like a
        # trail with nothing on it worth going to. Naming both sides, because
        # "run export_poi.py first" is false when it already ran and wrote
        # files under names this was not asking for (#469).
        print(f"WARNING: no published POIs under {POI_DIR} - run export_poi.py first.")
        found = sorted(p.name for p in POI_DIR.glob("*.geojson")) if POI_DIR.is_dir() else []
        print(f"  found: {', '.join(found) if found else '(nothing - directory is empty or absent)'}")

    output, dropped, gaps = build_output(curated, pois, club_runs)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    # ABSOLUTE path, like every sibling manifest - publish.py resolves this
    # string against its own CWD (#659).
    manifest = {"path": str(OUT_PATH), "sha256": digest}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    published = output["highlights"]
    print(f"{len(published)} highlights -> {OUT_PATH}")
    for record in published:
        legs = record["legs"]
        span = f"mi {legs[0]['start_mile']:.1f}-{legs[-1]['end_mile']:.1f}"
        print(f"  {record['id']:<16} {span:<20} {record['club'] or 'club not recorded'}")

    # A curated list quietly shrinking is the failure nobody notices, so a
    # drop is never just an absence from the output.
    if dropped:
        print(f"\n{len(dropped)} curated entries did not publish:", file=sys.stderr)
        for highlight_id, why in dropped:
            print(f"  {highlight_id}: {why}", file=sys.stderr)

    # Reported on every run rather than only when somebody counts, and
    # deliberately not a failure: a club with no well-known stretch is a fact
    # about the trail, and filling the list with entries nobody stands behind
    # to silence a check would be worse than the gap.
    if gaps:
        print(f"\n{len(gaps)} clubs have no highlight yet ({len(club_runs)} clubs in all):")
        print(f"  {', '.join(gaps)}")

    return manifest


if __name__ == "__main__":
    main()
