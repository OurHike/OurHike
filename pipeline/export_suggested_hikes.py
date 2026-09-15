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
  phone walking those ends walks the publisher's own route, and that is a claim this
  file can make with a measurement behind it. If it does not - the track goes
  somewhere this build draws no line - the hike ships no route rather than a
  re-drawn one.

  MEASURED 2026-09-15: of the 113 tracks, 64 have every 400 m sample within
  the phone's own 45.7 m of a line drawn here, and among those the re-route
  comes back within 2.4% of the track's length at the median - so where the
  ground IS drawn, this reproduces the publisher's line closely. The other 49
  leave the trails in the layers registered here (14 by more than a kilometre),
  and no tolerance recovers them: it is missing lines, not a loose threshold.
  47 tracks pass both gates and ship.

  THE 66 THAT DO NOT SHIP ARE NOT LOST, and are not shipped half-drawn either.
  Their full geometry, every point and every elevation, is in
  data/processed/hikefinder_routes.json and data/raw/hikefinder_gpx/. What
  would let them reach a hiker is a `track` field on SuggestedHike, so a
  published line ships as a line and nothing is re-derived - and that cannot be
  added here without also splitting this artifact, because it is already
  1.68 MB for 201 records (most of it the export's prose) against the
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
DETAIL_DIR = PROCESSED_DIR / "suggested_hikes_detail"
DETAIL_MANIFEST_PATH = PROCESSED_DIR / "suggested_hikes_detail_manifest.json"

#: The key a hike's detail is published under, formatted with its numeric id.
#:
#: A FLAT ROOT NAME, NOT A DIRECTORY, and that is the bucket's rule rather
#: than a preference. `suggested_hikes_detail/50.json` is illegal:
#: lib/r2_keys.py's TOP_LEVEL_PREFIXES declares five prefixes and this is not
#: one of them, so `assert_valid_keys` - which publish.py calls before it
#: opens a connection - raises on all 201 keys at once and uploads NOTHING,
#: taking the whole vector-data publish down with it. Adding a prefix is a
#: design decision with a retention rule attached (R2_LAYOUT.md), not a side
#: effect of this split.
#:
#: The flat name is also what every other runtime-named family here already
#: does: cut_cells.py writes `at_basemap_cell_n40w074.pmtiles`, and
#: config.ts's trailGraphCellKey writes `trail_graph_cell_<name>.json`. One
#: shape for "many objects, named at runtime, indexed by something else".
DETAIL_KEY = "suggested_hikes_detail_{id}.json"

#: WHAT STAYS ON THE SHELF (#1473). Everything else in a record moves to that
#: hike's own detail object, fetched when somebody opens it.
#:
#: The shelf was 1.70 MB of 2 MB and the ceiling is a CLIFF, not a slope:
#: conditionsCache.ts deletes the copy it holds rather than trimming it, so
#: the run the artifact crosses 2 MB is the run every phone loses the shelf
#: offline. Measured 2026-09-15 by rebuilding the artifact without each
#: field, over the 201 published records and in the shape that shipped:
#: `description` was 989,145 B of the 1,703,940 (58.1%) and `directions`
#: another 111,945 (6.6%) - prose the shelf and the finder never read.
#:
#: MEASURED, same 201 records, each rung the artifact rebuilt with that
#: much of this list and dumped the way it ships (compact):
#:     what the client reads today          111,380 B   554.1 B/record
#:     + the three provenance fields        131,447 B   +99.8 B/record
#:     + the finder fields and the tags     176,303 B  +223.2 B/record
#: The last rung IS the published shelf, byte for byte. 877.1 B a record
#: leaves room for ~2,391 hikes under the ceiling, against 247 on the old
#: shape - and the export is 385 hikes today.
#:
#: THREE CHOICES IN THIS LIST ARE NOT OBVIOUS:
#:
#: - `routeProvenance`, `routeGrade` and `routeNotes` are detail fields in the
#:   client's own type, and they are here anyway. App.tsx draws `segments` on
#:   the map from the SHELF record, nowhere near the detail screen, so leaving
#:   provenance in detail would let a generated line be drawn with its
#:   provenance still in flight - a display outrunning its source, which is
#:   the thing #1427 built the field to stop. 106 bytes is a cheap way to keep
#:   the answer wherever the line is.
#: - `features` and the finder fields ride along at 240 B/record because the
#:   maintainer asked for the tags kept ("especially the tags", #1427) and
#:   because a facet finder filters the SHELF - it cannot filter what it would
#:   have to fetch 200 objects to see.
#: - `directions`, `publicTransport`, `measured` and the rest are NOT here.
#:   Nothing in the client reads them today; they are kept in full, in detail.
SHELF_FIELDS = (
    # What lib/suggestedHikesData.ts reads off a shelf record today.
    "id",
    "name",
    "miles",
    "climb",
    "difficulty",
    "author",
    "transit",
    "photo",
    "segments",
    # Where the drawn line came from - see the note above.
    "routeProvenance",
    "routeGrade",
    "routeNotes",
    # What a finder filters on, the publisher's tags among them.
    "features",
    "region",
    "park",
    "publishedDifficulty",
    "estimatedHours",
    "dogs",
    "routeType",
    "closed",
)

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
    """What route_hikefinder.py decided, or {} when it wrote nothing.

    The same split load_cache makes (#1462): a missing artifact means that
    script had no hikes to route this run, which a publish forgives, while an
    artifact that is there and will not parse is a defect and raises.
    """
    path = ROUTES_PATH if path is None else path
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("routes") or {}
    except (OSError, ValueError) as error:
        raise SystemExit(
            f"{path} is present but unreadable, which is a defect rather than a skipped route pass: {error}"
        ) from error


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
    # The route is handed back as well as the ends, because it is the only
    # place a published hike's CLIMB can come from: the track's own `<ele>`
    # values are a DEM sampled along a drawn line (#1451) and are not used, so
    # the figure comes from this build's sidecar over this walk - the same
    # source, and the same arithmetic, as a generated route's.
    return [[round(point.at[0], 6), round(point.at[1], 6)] for point in snapped], f"{drift * 100:.1f}%", route


def segments_for(coords: list[list[float]], closed: bool) -> list[list[dict]]:
    """The ends as the client stores a day hike's: one segment of
    `{coord, poiId}` points in walking order, the first repeated at the end of
    a closed walk so routeThrough closes it exactly as closeTheLoop would."""
    walking = list(coords)
    if closed and walking and walking[0] != walking[-1]:
        walking.append(walking[0])
    return [[{"coord": coord, "poiId": None} for coord in walking]]


def record_for(hike: dict, route: dict, coords: list[list[float]], steward: str, reproduced: str | None) -> dict:
    """One hike as the client reads it.

    THE DETAIL FIELDS ARE FLAT, NOT NESTED, and that is not a style choice.
    `lib/suggestedHikesData.ts`'s `validDetail` is handed the WHOLE record and
    reads `raw.url`, `raw.publishedMiles`, `raw.description` off the top level;
    its own test pins the mistake by name - "reads nothing out of a nested
    `detail`, which is not the wire shape". An earlier version of this file
    nested them, which dropped every one of them on the phone while both test
    suites stayed green, because the pipeline suite asserted the nested shape
    and the client suite asserted the flat one and the two never met.
    `test_the_record_is_flat_because_the_client_reads_it_flat` is the guard
    against that happening again.
    """
    start = hike.get("start") or {}
    summary = hike.get("summary")
    author = hike.get("author")
    record = {
        "id": f"{SOURCE_KEY}:{hike['id']}",
        "name": hike["name"],
        "miles": round(route["miles"], 2),
        "difficulty": difficulty_slug(hike.get("difficulty")),
        "author": {"kind": AUTHOR_KIND, "name": steward},
        "segments": segments_for(coords, bool(route.get("closed"))),
        # --- everything below is read by validDetail, off the top level ---
        "url": hike["source_url"],
        "publishedMiles": hike.get("stated_miles"),
        "overview": [summary] if summary else [],
        "description": list(hike.get("description") or []),
        "routeType": hike.get("route_type"),
        "park": hike.get("park"),
        "trails": list(route.get("walked_trails") or []),
        "start": {"lat": start.get("lat"), "lon": start.get("lon"), "basis": start.get("label")} if start else None,
        # THE WHOLE POINT OF #1427, on the record a hiker's phone holds:
        # `published` is a line the publisher drew, `generated` is a line this
        # pipeline inferred from their prose. A screen that prints one in the
        # voice of the other is the failure these fields exist to prevent.
        "routeProvenance": route["provenance"],
        "routeGrade": route["grade"],
        "routeNotes": list(route.get("problems") or []),
        # NO `hikerNote`. That field's contract is that a PERSON wrote it -
        # "it says what somebody checked" - and nobody has checked these 385.
        # Putting the machine's own account of itself there would be exactly
        # the display outrunning its source that routeProvenance exists to stop.
        # --- kept for the finder and for screens that do not exist yet ---
        "publishedDifficulty": hike.get("difficulty"),
        "estimatedHours": hike.get("estimated_hours"),
        "dogs": hike.get("dogs"),
        "region": hike.get("region"),
        # The maintainer's "especially the tags": the export's Features
        # badges, as published, in page order.
        "features": list(hike.get("features") or []),
        "publishedOn": hike.get("published_on"),
        "updatedOn": hike.get("updated_on"),
        "directions": list(hike.get("directions") or []),
        "publicTransport": list(hike.get("public_transport") or []),
        "licence": CONTENT_LICENCE,
        "closed": bool(route.get("closed")),
        "measured": {"miles": round(route["miles"], 2), "note": router.SAME_TREAD_NOTE},
    }
    if author:
        # validPublication refuses a block with no submittedBy, so a hike whose
        # page names nobody ships no publication rather than an empty one.
        record["publication"] = {
            "submittedBy": author,
            "submittedOn": hike.get("published_on"),
            "verifiedOn": hike.get("updated_on"),
        }
    climb = route.get("climb")
    if climb:
        # Absent means never priced, which the client reads as unknown. Never
        # 0 as a stand-in: a walk with one unmeasured edge reported as flat
        # fails SHORT, and short is what gets somebody caught by the dark.
        record["climb"] = {"gainFt": round(climb[0]), "lossFt": round(climb[1])}
    if reproduced is not None:
        record["trackReproduction"] = reproduced
    return record


def write_details(details: list[dict]) -> dict[str, dict]:
    """Each hike's detail as its own object, and the manifest publish.py reads.

    ONE OBJECT PER HIKE rather than shards, because a hiker opens one walk. A
    shard holding a region's prose would download dozens of descriptions for a
    single tap, which is the cost this split exists to remove. The SHELF is
    what gets cut into 1-degree cells later (#1473's follow-on) - that is the
    artifact whose size scales with how much ground a phone has downloaded.

    The directory is emptied first. A detail left behind by an earlier run is
    a hike that has since been dropped or renumbered, and publishing it would
    put prose in the bucket that no shelf record points at - harmless to a
    phone, which never asks for it, and exactly the kind of thing that makes a
    later reader mistrust the whole family.

    The manifest shape is `_collect_cells`'s, deliberately: publish.py already
    knows how to read `{"artifacts": {name: {path, sha256}}}` from a file an
    exporter wrote, and a second shape would be a second thing to get wrong.

    RAISES on an id this scheme cannot address, rather than writing the key
    and letting publish.py find out. `assert_valid_keys` fails the whole
    vector-data publish on one bad name, so a source whose ids are not numbers
    would take the trails down with it - and it would do so a run later, in a
    workflow log, rather than here beside the reason.

    THE ORDER OF THE THREE STEPS IS THE CARE HERE, because the manifest and
    the files it names are two objects a crash can separate:

    1. Every id is checked BEFORE anything is deleted, so a bad one raises
       with the directory and the manifest still describing the last good
       run rather than half-emptied against a manifest that no longer
       matches it.
    2. The old manifest goes BEFORE the old files, so the window where one
       is stale against the other never opens. publish.py reads a missing
       manifest as "this run published no prose" and uploads the shelf alone
       - every hike reading as a publisher who said nothing more, a state
       the screen was built for. A manifest naming deleted paths is not a
       state anything was built for: it aborts the publish.
    3. Only then the files, and main() rewrites the manifest last.

    So a run killed partway costs this release its prose and nothing else.
    """
    numbered = []
    for detail in details:
        # The record id is "<source>:<n>"; the key is the number alone, which
        # is what the client has on the shelf record and can build a URL from
        # without knowing this pipeline's naming.
        #
        # CHARACTER FOR CHARACTER lib/suggestedHikesData.ts's `detailKeyFor`,
        # because the two build the same string from opposite ends of the
        # wire and a gate that is merely similar publishes objects nobody
        # asks for. Both take everything after the LAST colon, both require
        # that a colon was there, and both require digits: `50` alone is a
        # record the client will not fetch, and `hike-vista-loop-trail` - the
        # retired scraper's shape - builds a name NAME_PATTERN rejects.
        source, colon, number = detail["id"].rpartition(":")
        if not colon or not source or not number.isdigit():
            raise ValueError(
                f"{detail['id']!r} is not '<source>:<number>', so lib/suggestedHikesData.ts's detailKeyFor "
                f"would answer null for it and no phone would ever fetch the detail this would write"
            )
        numbered.append((number, detail))

    DETAIL_MANIFEST_PATH.unlink(missing_ok=True)
    if DETAIL_DIR.exists():
        for stale in DETAIL_DIR.glob("*.json"):
            stale.unlink()
    DETAIL_DIR.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, dict] = {}
    for number, detail in numbered:
        path = DETAIL_DIR / f"{number}.json"
        path.write_text(json.dumps(detail, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        artifacts[DETAIL_KEY.format(id=number)] = {
            "path": to_manifest_path(path),
            "sha256": sha256_file(path),
        }
    return artifacts


def split_record(record: dict) -> tuple[dict, dict]:
    """One full record as (shelf, detail) - SHELF_FIELDS and everything else.

    Absent stays absent on both sides. A field the publisher never said is
    left out rather than written as null, which is the rule the whole export
    already follows and the reason the client reads absent as "they did not
    say" rather than as a default.

    The detail carries its own `id`, because an object fetched on its own has
    to be able to say which hike it is - a phone that asked for one and was
    handed another by a stale cache or a mis-keyed upload would render the
    wrong prose under the right name, silently.
    """
    shelf = {key: record[key] for key in SHELF_FIELDS if key in record}
    detail = {key: value for key, value in record.items() if key not in SHELF_FIELDS}
    detail["id"] = record["id"]
    return shelf, detail


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
            coords, reproduced, rewalk = found
            if rewalk.climb is not None:
                route = {**route, "climb": [round(rewalk.climb[0]), round(rewalk.climb[1])]}
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
    routes = load_routes()
    if not cache or not routes:
        # NOT a failure, for the same reason as route_hikefinder.py's own
        # guard (#1462): a publish whose hike fetch could not reach the export
        # ships no hikes and keeps everything else. Saying which of the two is
        # missing matters, because "the fetch did not land" and "the route
        # pass wrote nothing" are different things to go and look at.
        missing = "No fetch cache" if not cache else "No routes artifact"
        print(f"{missing}, so nothing is published.", file=sys.stderr)
        print("Run fetch_hikefinder.py and route_hikefinder.py to build one.", file=sys.stderr)
        return None

    starts = [(hike["start"]["lon"], hike["start"]["lat"]) for hike in cache.values() if hike.get("start")]
    graph = load_graph(PROCESSED_DIR, starts)
    if graph.climb_note:
        print(f"climb: {graph.climb_note}")

    generated_at = datetime.now(timezone.utc)
    document, dropped = build_document(graph, cache, routes, steward, generated_at)

    if not document["hikes"]:
        # NOT a failure, and NOT an empty artifact. "Nothing passed grading"
        # and "there are no suggested hikes" are different claims, and an
        # empty document would make the client read the second - the Today
        # shelf silently emptying on every phone that downloads it, over an
        # artifact that was fine. publish.py collects whatever manifest exists
        # with no count of its own, so this is the only place that can refuse.
        print(f"No hike of {len(cache)} has a route that passed grading, so nothing is published.", file=sys.stderr)
        return None

    # #1473: the shelf keeps SHELF_FIELDS, every hike's prose becomes its own
    # object. Written before the shelf is, so a run that dies between the two
    # leaves the OLD shelf beside NO detail manifest - see write_details for
    # why that is the safe pairing. The reverse order would publish a new
    # shelf whose every hike points at prose that is not there yet, which on
    # a phone reads as 201 publishers who said nothing more.
    full = document["hikes"]
    details = []
    document = {**document, "hikes": []}
    for record in full:
        shelf, detail = split_record(record)
        document["hikes"].append(shelf)
        details.append(detail)
    detail_artifacts = write_details(details)

    # COMPACT, like every other artifact a phone downloads (#1473):
    # build_trail_graph.py, cut_trail_graph.py, export_nearby_poi.py and
    # export_nearby_trails.py all write `separators=(",", ":")`, and this file
    # was the outlier still paying for indentation. Measured on the 201
    # records: whitespace was 51% of the shelf - 0.363 MB indented against
    # 0.176 MB compact, which is the difference between room for 1,162 hikes
    # under the client's cache ceiling and room for 2,391.
    #
    # The MANIFESTS below stay indented. They are read by people, they are
    # small, and nothing downloads them to a phone.
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    by_provenance: dict[str, int] = {}
    for hike in document["hikes"]:
        kind = hike["routeProvenance"]
        by_provenance[kind] = by_provenance.get(kind, 0) + 1
    manifest = {
        "path": to_manifest_path(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "count": len(document["hikes"]),
        "by_provenance": by_provenance,
        "with_tags": sum(1 for hike in document["hikes"] if hike["features"]),
        "with_climb": sum(1 for hike in document["hikes"] if "climb" in hike),
        "dropped": [key for key, _ in dropped],
        "generated_at": document["generated_at"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    DETAIL_MANIFEST_PATH.write_text(
        json.dumps({"artifacts": detail_artifacts, "generated_at": document["generated_at"]}, indent=2) + "\n",
        encoding="utf-8",
    )

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
