"""Publish the hikes somebody wrote up - the NYNJTC Hike Finder export - as
`suggested_hikes.json` (#1427, features/SUGGESTED_HIKES.md).

    python export_suggested_hikes.py

WHAT CHANGED, AND WHAT DID NOT. This exporter used to read nynjtc.org's twenty
public write-ups through `fetch_nynjtc_hikes.py`, and shipped a hike only once
a person had signed its ends off by hand in `reference/nynjtc_hike_routes.json`
(#1290). The maintainer supplied the full list as an export on 2026-09-15 and
asked for the scrape to stop, so the input is now `fetch_hikefinder.py`'s cache
of 385 hikes and `route_hikefinder.py`'s routes. THE CLIENT CONTRACT IS
UNTOUCHED: `lib/suggestedHikesData.ts` validates exactly what it validated
before, and a field it reads is spelled exactly as that module spells it.

WHAT A RECORD IS. An id, a name, its miles, a NAMED publisher, and its ENDS as
segments of `{coord, poiId}` points the phone routes between when the card
opens - plus everything the detail screen prints and the shelf ignores: the
export's prose, its categorisation, its tags, the page URL, and the figures
this build measured beside the publisher's own.

THE GATE IS THE ROUTE'S GRADE, and it replaces a person's signature with a
published rule. That is a real loss and worth naming: #1290's 20 hikes were
each read by the maintainer before they shipped, and 385 cannot be. What
stands in its place is `lib/hike_route_builder.py`'s grading, which refuses a
route that disagrees with the publisher's own stated mileage, walks trails the
description does not name, or closes a "Circuit" by doubling back - and
`route_hikefinder.py` renders the sheet a person reads to disagree with any of
it. A `rejected` route ships nothing.

THE TWO PROVENANCES SHIP DIFFERENTLY, and this is the part to read before
changing anything here.

  A GENERATED route already stores what the client wants: ends on the network,
  snapped, which the phone re-routes between exactly as this build measured
  them.

  A PUBLISHED route does not. It is a GPX track - 943 points on some hikes -
  and `SuggestedHike.segments` is "the ends, never the route" (dayHikes.ts):
  the phone will re-route between whatever points it is given, over the trail
  graph. So a track cannot be handed over as a line, and this exporter does
  NOT pretend otherwise. What it does is sample the track, snap each sample to
  the network, and then CHECK that re-routing between those samples reproduces
  the track's own length within TRACK_REPRODUCTION_TOLERANCE. If it does, the
  phone walking those ends walks the surveyed route, and that is a claim this
  file can make with a measurement behind it. If it does not - the track goes
  somewhere this build draws no line - the hike ships no route rather than a
  re-drawn one.

  MEASURED 2026-09-15: of the 113 tracks, 64 have every 400 m sample within
  the phone's own 45.7 m of a line drawn here, and among those the re-route
  comes back within 2.4% of the track's length at the median - so where the
  ground IS drawn, this reproduces the survey closely. The other 49 leave the
  trails in the layers registered here (14 of them by more than a kilometre),
  and no tolerance recovers them: it is missing lines, not a loose threshold.
  47 tracks pass both gates and ship.

  THE 66 THAT DO NOT SHIP ARE NOT LOST, and are not shipped half-drawn either.
  Their full geometry, every point and every elevation, is in
  data/processed/hikefinder_routes.json and data/raw/hikefinder_gpx/. What
  would let them reach a hiker is a `track` field on SuggestedHike, so a
  surveyed line ships as a line and nothing is re-derived - and that cannot be
  added here without also splitting this artifact, because it is already
  1.44 MB for 171 records (most of it the export's prose) against the
  client's 2 MB cache ceiling (conditionsCache.ts, itself @unvalidated), and
  113 tracks would go straight through it. Both are #1428.

DIFFICULTY IS QUOTED, AND ONE LEVEL DOES NOT FIT. The client's `DIFFICULTIES`
holds five slugs; the export publishes SIX labels, the extra one being "Very
Strenuous" (one hike). It is mapped to `strenuous`, which UNDERSTATES it, so
the publisher's own label rides along in `detail.publishedDifficulty` and the
card can print the word the publisher used. Rounding a difficulty downward is
the unsafe direction and is not done silently.

Runs AFTER fetch_hikefinder.py and route_hikefinder.py. NO NETWORK.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib import trail_graph_route as router
from lib.hashing import sha256_file
from lib.hike_route_builder import PUBLISHED
from lib.hikefinder import SOURCE_KEY
from lib.manifest_paths import to_manifest_path
from lib.source_registry import find_source, load_registry
from lib.stamps import utc_stamp
from route_hikefinder import load_cache, load_graph

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.json"
PROCESSED_DIR = ROOT / "data" / "processed"
ROUTES_PATH = PROCESSED_DIR / "hikefinder_routes.json"
OUT_PATH = PROCESSED_DIR / "suggested_hikes.json"
MANIFEST_PATH = PROCESSED_DIR / "suggested_hikes_manifest.json"

#: The client's AUTHOR_KINDS member for a maintaining organization
#: (lib/suggestedHikes.ts). A route a club wrote up is the club's.
AUTHOR_KIND = "club"

#: The export's difficulty labels onto the five slugs the client holds
#: (lib/suggestedHikes.ts DIFFICULTIES). "Very Strenuous" has no slot and
#: takes the hardest one there is; see this module's docstring for why that is
#: said out loud rather than done quietly.
DIFFICULTY_SLUGS = {
    "easy": "easy",
    "easy to moderate": "easy-moderate",
    "moderate": "moderate",
    "moderate to strenuous": "moderate-strenuous",
    "strenuous": "strenuous",
    "very strenuous": "strenuous",
}

#: How far apart the samples taken along a published track are. @unvalidated -
#: 400 m is short enough that the shortest path between two consecutive
#: samples has no room to take a different trail, and long enough that a
#: 10-mile track becomes about 40 ends rather than 900 points.
TRACK_SAMPLE_M = 400.0

#: How far the phone's re-route between a track's samples may sit from the
#: track's own measured length before the track is judged not reproducible on
#: this build's lines. @unvalidated - 0.10 is tighter than any grading band in
#: hike_route_builder.py on purpose: this is not "is this roughly the right
#: walk", it is "does re-routing give back the line we already have".
TRACK_REPRODUCTION_TOLERANCE = 0.10

#: The licence line a card prints under the credit. The weaker true sentence:
#: the permission reached this repository through the maintainer
#: (nynjtc_hikes_licence records the words), so it names who gave it and not a
#: licence NYNJTC never wrote.
CONTENT_LICENCE = "By permission of the New York-New Jersey Trail Conference"


def load_routes(path: Path | None = None) -> dict:
    path = ROUTES_PATH if path is None else path
    if not path.exists():
        raise SystemExit(f"{path} is missing - run route_hikefinder.py first; it is what decides which hikes have a route")
    return json.loads(path.read_text(encoding="utf-8")).get("routes") or {}


def difficulty_slug(label: str | None) -> str | None:
    """The client's slug for the export's label, or None when it has no slot
    for it - absent means the card prints no badge, never a guessed one."""
    return DIFFICULTY_SLUGS.get((label or "").strip().lower())


def sample_track(points: list[tuple[float, float]], spacing_m: float = TRACK_SAMPLE_M) -> list[tuple[float, float]]:
    """A track thinned to points about `spacing_m` apart, ends always kept."""
    if len(points) < 2:
        return list(points)
    kept = [points[0]]
    since = 0.0
    for previous, point in zip(points, points[1:]):
        since += router.metres_between(previous, point)
        if since >= spacing_m:
            kept.append(point)
            since = 0.0
    if kept[-1] != points[-1]:
        kept.append(points[-1])
    return kept


def track_ends(
    graph: router.Graph, points: list[tuple[float, float]], track_miles: float
) -> tuple[list[list[float]], str] | None:
    """A published track as ends the phone can re-walk, or None with a reason.

    Two gates, and the second is the one that matters. Every sample must snap
    onto a line this build draws, and then the walk the phone would make
    between those snapped ends must come back the same length as the track. A
    track that passes both is one the phone reproduces; a track that passes
    only the first has snapped onto lines that go somewhere else.
    """
    samples = sample_track(points)
    snapped: list[router.GraphPoint] = []
    for lon, lat in samples:
        found = router.nearest_point(graph, lon, lat, max_off_m=router.MAX_OFF_NETWORK_M)
        if found is None:
            return None
        snapped.append(found)
    if len(snapped) < 2:
        return None
    route = router.route_through(graph, snapped)
    if route is None:
        return None
    if not track_miles:
        return None
    drift = abs(route.miles - track_miles) / track_miles
    if drift > TRACK_REPRODUCTION_TOLERANCE:
        return None
    return [[round(point.at[0], 6), round(point.at[1], 6)] for point in snapped], f"{drift * 100:.1f}%"


def segments_for(coords: list[list[float]], closed: bool) -> list[list[dict]]:
    """The ends as the client stores a day hike's: one segment of
    `{coord, poiId}` points in walking order, the first repeated at the end of
    a closed walk so routeThrough closes it exactly as closeTheLoop would."""
    walking = list(coords)
    if closed and walking and walking[0] != walking[-1]:
        walking.append(walking[0])
    return [[{"coord": coord, "poiId": None} for coord in walking]]


def record_for(hike: dict, route: dict, coords: list[list[float]], steward: str, reproduced: str | None) -> dict:
    start = hike.get("start") or {}
    record = {
        "id": f"{SOURCE_KEY}:{hike['id']}",
        "name": hike["name"],
        "miles": round(route["miles"], 2),
        "difficulty": difficulty_slug(hike.get("difficulty")),
        "author": {"kind": AUTHOR_KIND, "name": steward},
        "segments": segments_for(coords, bool(route.get("closed"))),
        # Everything below is the detail screen's; the shelf and the finder
        # ignore it, so a document carrying only the fields above is complete.
        "detail": {
            "url": hike["source_url"],
            "summary": hike.get("summary"),
            "publishedMiles": hike.get("stated_miles"),
            # The publisher's own word, because the five-slug mapping above
            # cannot spell "Very Strenuous" and a card should be able to.
            "publishedDifficulty": hike.get("difficulty"),
            "routeType": hike.get("route_type"),
            "estimatedHours": hike.get("estimated_hours"),
            "dogs": hike.get("dogs"),
            "park": hike.get("park"),
            "region": hike.get("region"),
            # The maintainer's "especially the tags": the export's Features
            # badges, as published, in page order.
            "features": list(hike.get("features") or []),
            "publishedOn": hike.get("published_on"),
            "updatedOn": hike.get("updated_on"),
            "directions": list(hike.get("directions") or []),
            "description": list(hike.get("description") or []),
            "publicTransport": list(hike.get("public_transport") or []),
            "author": hike.get("author"),
            "licence": CONTENT_LICENCE,
            # THE WHOLE POINT OF #1427's grading, on the record a hiker's phone
            # holds: `published` is a track somebody surveyed, `generated` is a
            # line this pipeline inferred from their prose. A screen that
            # prints one in the voice of the other is the failure this field
            # exists to prevent.
            "routeProvenance": route["provenance"],
            "routeGrade": route["grade"],
            "routeNotes": list(route.get("problems") or []),
        },
        "start": {"lat": start.get("lat"), "lon": start.get("lon"), "basis": start.get("label")} if start else None,
        "closed": bool(route.get("closed")),
        "measured": {"miles": round(route["miles"], 2), "note": router.SAME_TREAD_NOTE},
    }
    if reproduced is not None:
        record["detail"]["trackReproduction"] = reproduced
    return record


def build_document(graph: router.Graph, cache: dict, routes: dict, steward: str, generated_at: datetime) -> tuple[dict, list]:
    hikes: list[dict] = []
    dropped: list[tuple[str, str]] = []
    for key in sorted(cache, key=lambda k: int(k)):
        hike, route = cache[key], routes.get(key)
        if route is None:
            dropped.append((key, "no row in hikefinder_routes.json - re-run route_hikefinder.py"))
            continue
        if route["grade"] == "rejected" or not route.get("ends"):
            dropped.append((key, "; ".join(route.get("problems") or ["no route"])))
            continue

        reproduced = None
        if route["provenance"] == PUBLISHED:
            found = track_ends(graph, [tuple(end) for end in route["ends"]], route["miles"] or 0.0)
            if found is None:
                dropped.append(
                    (
                        key,
                        "the published track does not re-walk on this build's lines - it leaves the trails drawn here, "
                        "so the phone cannot be given ends that reproduce it",
                    )
                )
                continue
            coords, reproduced = found
        else:
            coords = [[round(end[0], 6), round(end[1], 6)] for end in route["ends"]]

        hikes.append(record_for(hike, route, coords, steward, reproduced))

    document = {"generated_at": utc_stamp(generated_at), "source": SOURCE_KEY, "hikes": hikes}
    return document, dropped


def main() -> dict | None:
    registry = load_registry(SOURCES_PATH)
    source = find_source(registry, SOURCE_KEY)
    if source is None:
        raise SystemExit(f"{SOURCE_KEY} is not registered in sources.json")
    if not source.get("reaches_hikers"):
        print(f"{SOURCE_KEY} carries reaches_hikers: false, so nothing is published (sources.json's nynjtc_hikes_licence).")
        return None
    steward = source.get("steward") or source.get("attribution")
    if not steward:
        raise SystemExit(
            f"{SOURCE_KEY} names no steward, and a route with no named publisher is not shown at all (features/SUGGESTED_HIKES.md)"
        )

    cache = load_cache()
    if not cache:
        raise SystemExit("No fetch cache to build from - run fetch_hikefinder.py first")
    routes = load_routes()

    starts = [(hike["start"]["lon"], hike["start"]["lat"]) for hike in cache.values() if hike.get("start")]
    graph = load_graph(PROCESSED_DIR, starts)
    if graph.climb_note:
        print(f"climb: {graph.climb_note}")

    generated_at = datetime.now(timezone.utc)
    document, dropped = build_document(graph, cache, routes, steward, generated_at)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    by_provenance: dict[str, int] = {}
    for hike in document["hikes"]:
        kind = hike["detail"]["routeProvenance"]
        by_provenance[kind] = by_provenance.get(kind, 0) + 1
    manifest = {
        "path": to_manifest_path(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "count": len(document["hikes"]),
        "by_provenance": by_provenance,
        "with_tags": sum(1 for hike in document["hikes"] if hike["detail"]["features"]),
        "dropped": [key for key, _ in dropped],
        "generated_at": document["generated_at"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"{len(document['hikes'])} suggested hike(s) of {len(cache)} -> {OUT_PATH}")
    for kind, count in sorted(by_provenance.items()):
        print(f"  {count:4}  {kind}")
    if dropped:
        print(f"\n{len(dropped)} hike(s) ship no route:", file=sys.stderr)
        reasons: dict[str, int] = {}
        for _, why in dropped:
            head = why.split(" - ")[0][:78]
            reasons[head] = reasons.get(head, 0) + 1
        for why, count in sorted(reasons.items(), key=lambda pair: -pair[1]):
            print(f"  {count:4}  {why}", file=sys.stderr)
    return manifest


if __name__ == "__main__":
    main()
