"""Publish the routes somebody wrote up - NYNJTC's reviewed Favorite Hikes
first - as `suggested_hikes.json` (#1290, features/SUGGESTED_HIKES.md).

    python export_suggested_hikes.py

The client half landed first (#1284): a Today shelf and a Find-a-hike
screen reading an optional artifact that nothing wrote. This writes it.

WHAT A RECORD IS. The contract lib/suggestedHikesData.ts validates - an id,
a name, its miles, a NAMED publisher, and its ENDS as segments of
`{coord, poiId}` points the phone routes between when the card opens - plus
everything the detail screen prints and the shelf ignores: NYNJTC's own
prose, their photograph with its credit, their categorisation, the
publication line, the page URL, and the figures this build measured beside
theirs. A field the shipped client does not read costs it nothing; a field
it does read is spelled exactly as that module spells it.

THREE GATES, AND EVERY ONE IS SOMEBODY'S DECISION RATHER THAN THIS SCRIPT'S:

  1. sources.json's `reaches_hikers` on the entry. False writes nothing -
     the same gate every other organization's data ships behind.
  2. reference/nynjtc_hike_routes.json's `status`. Only `reviewed` rows
     ship: a person has read the sign-off sheet route_nynjtc_hikes.py
     renders and stands behind these ends. `proposed` is not close enough
     (the maintainer: "let me see the edits and approve first"), and
     `held` says in its own words why there is no route.
  3. The graph. A reviewed row whose ends no longer route on THIS build's
     lines is dropped with a line on stderr and its slug in the manifest's
     `dropped` list - never published as a route with a hole in it, and
     never silent, for export_highlights.py's reason: "a curated list
     quietly shrinking is the failure nobody notices".

THE FIGURES, AND WHICH IS WHOSE. `miles` is lib/trail_graph_route.py's -
the pipeline's twin of the phone's router - measured over this graph's
lines between the reviewed ends; the phone redoes the same arithmetic when
the card opens, so this is the number it will agree with. `publishedMiles`
is NYNJTC's own figure from their overview. They differ, by the
digitisation of somebody's survey and by the side trips no line carries
(each row's `hikerNote` says which), and both ship so the screen can print
them side by side rather than one dressed as the other. `climb` ships only
when the elevation sidecar fits this graph and every edge on the walk is
measured; otherwise it is ABSENT, which the client reads as "never priced"
and never as flat.

THE PHOTOGRAPH is a bucket key, `photos/<digest>.jpg`, the same
content-addressed store the POI cards draw from; publish.py uploads the
bytes and verify_photo_promises() refuses to publish a key it cannot back.
The credit line is the licence's condition (nynjtc_hikes_licence) and a
hike whose photo has none ships with no photo.

Runs AFTER build_trail_graph.py and, where the run has it,
export_network_elevation.py: it needs the graph to measure and the sidecar
to price. NO NETWORK.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib import trail_graph_route as router
from lib.hashing import sha256_file
from lib.manifest_paths import to_manifest_path
from lib.nynjtc_hikes import SOURCE_KEY
from lib.source_registry import find_source, load_registry
from lib.stamps import utc_stamp
from route_nynjtc_hikes import (
    STATUS_REVIEWED,
    base_slug,
    load_cache,
    load_graph,
    load_routes,
    measure,
    published_miles,
    row_name,
)

ROOT = Path(__file__).resolve().parent
SOURCES_PATH = ROOT / "sources.json"
PROCESSED_DIR = ROOT / "data" / "processed"
OUT_PATH = PROCESSED_DIR / "suggested_hikes.json"
MANIFEST_PATH = PROCESSED_DIR / "suggested_hikes_manifest.json"

#: The client's AUTHOR_KINDS member for a maintaining organization
#: (lib/suggestedHikes.ts). A route a club wrote up is the club's.
AUTHOR_KIND = "club"

#: The licence line a card prints under the credit. The weaker true
#: sentence: the permission reached this repository through the maintainer
#: (nynjtc_hikes_licence records the words), so it names who gave it and
#: not a licence NYNJTC never wrote.
PHOTO_LICENCE = "By permission of the New York-New Jersey Trail Conference"


def _term_names(hike: dict, taxonomy: str) -> list[str]:
    return [term["name"] for term in (hike.get("terms") or {}).get(taxonomy, []) if isinstance(term, dict) and term.get("name")]


def _first(names: list[str]) -> str | None:
    return names[0] if names else None


def segments_for(row: dict, points: list[router.GraphPoint]) -> list[list[dict]]:
    """The ends as the client stores a day hike's: one segment of
    `{coord, poiId}` points in walking order, the first repeated at the end
    of a closed walk so that routeThrough closes it exactly as closeTheLoop
    would. Coordinates are the SNAPPED points, so the phone finds each one
    at zero offset from the line."""
    coords = [[round(point.at[0], 6), round(point.at[1], 6)] for point in points]
    if row.get("closed") and coords:
        coords.append(coords[0])
    return [[{"coord": coord, "poiId": None} for coord in coords]]


def photo_for(hike: dict) -> dict | None:
    """The client's photo block, or None when there is nothing publishable:
    no photograph, no stored bytes, or no credit to carry."""
    photo = hike.get("photo") or {}
    key, credit = photo.get("key"), photo.get("credit")
    if not key or not credit:
        return None
    return {"url": key, "credit": f"Photo by {credit}", "licence": PHOTO_LICENCE}


def record_for(slug: str, row: dict, hike: dict, route: router.Route, points: list[router.GraphPoint], steward: str) -> dict:
    publication = hike.get("publication") or {}
    start = hike.get("start") or {}
    record = {
        # The FULL key, variant and all: three walks share one NYNJTC page
        # and would otherwise share one id, which the client dedupes on -
        # two of the three would silently never reach a shelf.
        "id": f"{SOURCE_KEY}:{slug}",
        "name": row_name(slug, row, hike),
        "miles": round(route.miles, 2),
        "difficulty": hike.get("difficulty"),
        "author": {"kind": AUTHOR_KIND, "name": steward},
        "segments": segments_for(row, points),
        # Everything below is the detail screen's (features/SUGGESTED_HIKES.md
        # frame 1g); the shelf and the finder ignore it.
        "url": hike["source_url"],
        "publishedMiles": published_miles(row, hike),
        "routeType": _first(_term_names(hike, "route-type")),
        "timeCommitment": _first(_term_names(hike, "time-commitment")),
        "distanceBucket": _first(_term_names(hike, "distance")),
        "park": _first(_term_names(hike, "park")),
        "region": _first(_term_names(hike, "region")),
        "state": _first(_term_names(hike, "state")),
        "county": _first(_term_names(hike, "county")),
        "trails": _term_names(hike, "trail"),
        "accessibility": _term_names(hike, "accessibility"),
        "overview": list(hike.get("overview") or []),
        "description": list(hike.get("description") or []),
        "publication": {
            "submittedBy": publication.get("submitted_by"),
            "submittedOn": publication.get("submitted_on"),
            "verifiedOn": publication.get("verified_on"),
        }
        if publication
        else None,
        "start": {"lat": start.get("lat"), "lon": start.get("lon"), "basis": start.get("basis")} if start else None,
        "closed": bool(row.get("closed")),
        "reviewed": row.get("reviewed"),
        "hikerNote": row.get("hiker_note"),
        "measured": {
            "miles": round(route.miles, 2),
            "legs": [leg.to_dict() | {"miles": round(leg.miles, 2)} for leg in route.legs],
            "note": router.SAME_TREAD_NOTE,
        },
    }
    if route.climb is not None:
        record["climb"] = {"gainFt": round(route.climb[0]), "lossFt": round(route.climb[1])}
    photo = photo_for(hike)
    if photo is not None:
        record["photo"] = photo
    return record


def build_document(
    graph: router.Graph, routes: dict, cache: dict, steward: str, generated_at: datetime
) -> tuple[dict, list[tuple[str, str]]]:
    """The artifact and what was dropped, in slug order."""
    hikes: list[dict] = []
    dropped: list[tuple[str, str]] = []
    for slug in sorted(routes):
        row = routes[slug]
        if row.get("status") != STATUS_REVIEWED:
            continue
        hike = cache.get(base_slug(slug))
        if hike is None:
            dropped.append(
                (slug, "reviewed in reference/nynjtc_hike_routes.json but not in the fetch cache - run fetch_nynjtc_hikes.py")
            )
            continue
        measured = measure(graph, row)
        if measured["route"] is None:
            dropped.append((slug, "; ".join(measured["problems"])))
            continue
        hikes.append(record_for(slug, row, hike, measured["route"], measured["points"], steward))
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

    routes = load_routes()
    cache = load_cache()
    reviewed = [slug for slug, row in routes.items() if row.get("status") == STATUS_REVIEWED]
    if not reviewed:
        # Not a failure and not an empty artifact. "Nobody has signed one
        # off yet" and "there are no suggested hikes" are different claims,
        # and an empty document would make the client read the second.
        proposed = sum(1 for row in routes.values() if row.get("status") == "proposed")
        print(
            f"No reviewed rows in reference/nynjtc_hike_routes.json ({proposed} proposed, waiting for sign-off), so nothing is published."
        )
        return None
    if not cache:
        raise SystemExit(
            f"{len(reviewed)} reviewed row(s) and no fetch cache to build them from - run fetch_nynjtc_hikes.py first"
        )

    graph = load_graph(PROCESSED_DIR, routes)
    if graph.climb_note:
        print(f"climb: {graph.climb_note}")
    generated_at = datetime.now(timezone.utc)
    document, dropped = build_document(graph, routes, cache, steward, generated_at)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest = {
        "path": to_manifest_path(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "count": len(document["hikes"]),
        "with_climb": sum(1 for hike in document["hikes"] if "climb" in hike),
        "with_photo": sum(1 for hike in document["hikes"] if "photo" in hike),
        "dropped": [slug for slug, _ in dropped],
        "generated_at": document["generated_at"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"{len(document['hikes'])} suggested hike(s) -> {OUT_PATH}")
    for hike in document["hikes"]:
        climb = f"+{hike['climb']['gainFt']} ft" if "climb" in hike else "climb unknown"
        photo = "photo" if "photo" in hike else "no photo"
        print(f"  {hike['id'].split(':', 1)[1][:52]:52} {hike['miles']:5.2f} mi  {climb:14} {photo}")
    if dropped:
        print(f"\n{len(dropped)} reviewed row(s) did not publish:", file=sys.stderr)
        for slug, why in dropped:
            print(f"  {slug}: {why}", file=sys.stderr)
    return manifest


if __name__ == "__main__":
    main()
