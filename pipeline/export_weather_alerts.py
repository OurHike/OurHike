"""Fetch every active NWS alert and publish the ones that reach a trail square (#1056).

The warnings slice of features/WEATHER.md's build step 1, and the seventh
artifact family in the conditions prefix:

    conditions/weather_alerts.json      every active NWS alert over a trail square   (this)

ONE REQUEST. `api.weather.gov/alerts/active` returns every active US alert in
one response (486 of them, 2.6 MB, at 2026-09-25 20:54 UTC), so this asks NWS
once a run and no phone has to ask on OurHike's behalf for the published copy.

RELAY, DON'T ORIGINATE (HIKER_SAFETY.md §3; the maintainer confirmed "relay
all" on 2026-09-26). Every alert NWS marks `Actual` that reaches a trail square
is published with NWS's own words - event, headline, description, instruction,
severity, times - and none is left out for being the wrong kind. A Rip Current
Statement on a beach-side square around New York is NWS's call to issue, not
OurHike's to drop. What is left out: `Test` and other non-`Actual` messages,
cancellations, and alerts that reach no trail square.

WHERE AN ALERT LANDS (WEATHER.md §6). On the squares `build_weather_squares.py`
chose, by the rule `lib/nbm_grid.overlapping` states: an alert reaches a square
when any part of the square is inside the area it warns. That area is
the alert's own polygon when it has one - storm and flood warnings are drawn
by the forecaster, and also list every county the drawing touches, for the
systems that broadcast by county - and otherwise the zones it names. Measured on the alerts
above: 68 of 486 reached a trail square, covering 6,723 of 72,720 squares.
Warning each whole 1-degree cell instead would have covered 22,079.

WHAT THIS FILE IS NOT. It is the offline copy, as old as the run that made it.
Storm warnings are short: scheduled for a median of 43 minutes (15,238
severe thunderstorm warnings) and 31 (1,311 tornado warnings), from Iowa
Environmental Mesonet's archive of every one NWS issued, 2026-06-01 to 09-01.
At GitHub's measured ~4-hour clock (#1346) about one in six of those is live
at any run at all, and fewer if they are cancelled early. So a phone with signal asks NWS
itself, for its square's zones (the maintainer's choice of 2026-09-26, build
step 4), and falls back to this file when it cannot. `fetched_at` is the
moment this run asked NWS, and it is the age the phone has to show.

IF NWS DOES NOT ANSWER, NOTHING IS WRITTEN. Neither this file nor its
manifest. `publish.py` then carries the previous copy forward, stamped with its
own `fetched_at`, and the phone says how old that is. An empty list published
because the request failed would read as "no warnings", which is the one
thing the warnings line must never say by mistake (WEATHER.md §5).

    python export_weather_alerts.py
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import requests
import shapely

from lib import nbm_grid
from lib.atomic_write import write_text_atomically
from lib.hashing import sha256_file
from lib.http_retry import request_with_retry
from lib.manifest_paths import to_manifest_path

ROOT = Path(__file__).resolve().parent
SQUARES_PATH = ROOT / "data" / "raw" / "weather" / "squares.json"
CONDITIONS_DIR = ROOT / "data" / "processed" / "conditions"
ALERTS_PATH = CONDITIONS_DIR / "weather_alerts.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "weather_alerts_manifest.json"

ALERTS_URL = "https://api.weather.gov/alerts/active"
# NWS asks every caller for a User-Agent that identifies the app and a way to
# reach it (weather.gov/documentation/services-web-api). The repository is
# the contact: no person's address goes in a request header.
USER_AGENT = "OurHike (github.com/OurHike/OurHike)"

# `conditions/weather_alerts.json` is a URL deployed clients will request, and
# a key in that bucket can never be renamed (pipeline/R2_LAYOUT.md).
PAYLOAD = "weather_alerts"
SCHEMA = 1
SOURCE = "National Weather Service, api.weather.gov/alerts/active"
CREDIT = "National Weather Service"

# NWS's property -> the name it is published under. The text fields are
# relayed exactly as NWS wrote them; `null` stays `null` (an alert with no
# `ends` has not been given one, which is not the same as ending now).
RELAYED = {
    "id": "id",
    "event": "event",
    "headline": "headline",
    "description": "description",
    "instruction": "instruction",
    "severity": "severity",
    "urgency": "urgency",
    "certainty": "certainty",
    "response": "response",
    "messageType": "message_type",
    "sent": "sent",
    "effective": "effective",
    "onset": "onset",
    "expires": "expires",
    "ends": "ends",
    "senderName": "sender_name",
    "areaDesc": "area_desc",
}

ZONE_URL = re.compile(r"/zones/([a-z]+)/([A-Z0-9]+)$")


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Pure pieces - what the tests pin.


def check_response(body: object) -> list[dict]:
    """The alert features, refusing anything that is not the GeoJSON
    FeatureCollection NWS documents. A 200 carrying some other shape is a
    changed API, and publishing its absence of alerts would say "none"."""
    if not isinstance(body, dict) or body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
        raise RuntimeError(f"{ALERTS_URL} did not answer with a FeatureCollection; refusing to publish its alerts as none")
    return body["features"]


def relayed(feature: dict) -> bool:
    properties = feature.get("properties") or {}
    return properties.get("status") == "Actual" and properties.get("messageType") != "Cancel"


def zone_keys(properties: dict) -> list[str]:
    """`affectedZones` URLs as "<kind>/<id>", the keys squares.json uses.
    The kind matters: forecast zone NHZ010 and fire weather zone NHZ010 are
    different outlines under the same id."""
    keys = []
    for url in properties.get("affectedZones") or []:
        match = ZONE_URL.search(url)
        if match:
            keys.append(f"{match[1]}/{match[2]}")
    return keys


def unknown_zones(keys: list[str], known: dict[str, set[str]], states: set[str]) -> list[str]:
    """Zone keys the pinned outlines have never heard of, in a state they
    cover. Marine zones (ANZ335, a stretch of sea) belong to no state and are
    not in these files by design, so they are not reported."""
    missing = []
    for key in keys:
        kind, zone_id = key.split("/", 1)
        if zone_id[:2] in states and zone_id not in known.get(kind, set()):
            missing.append(key)
    return missing


def bake(squares_doc: dict, body: dict, fetched_at: datetime, generated_at: datetime) -> dict:
    """The published document, with nothing written."""
    features = [f for f in check_response(body) if relayed(f)]
    trail = sorted({tuple(sq) for squares in squares_doc["cells"].values() for sq in squares})
    by_zone = {key: [tuple(sq) for sq in squares] for key, squares in squares_doc["zones"].items()}
    known = {kind: set(ids) for kind, ids in squares_doc["known_zones"].items()}
    states = {zone_id[:2] for ids in known.values() for zone_id in ids}

    drawn = [n for n, f in enumerate(features) if f.get("geometry")]
    shapes = [shapely.from_geojson(json.dumps(features[n]["geometry"])) for n in drawn]
    polygon_squares = {n: {trail[i] for i in hits} for n, hits in zip(drawn, nbm_grid.overlapping(shapes, trail), strict=True)}

    alerts, missing = [], set()
    for n, feature in enumerate(features):
        properties = feature["properties"]
        if n in polygon_squares:
            squares, placed_by = polygon_squares[n], "polygon"
        else:
            keys = zone_keys(properties)
            missing.update(unknown_zones(keys, known, states))
            squares, placed_by = {sq for key in keys for sq in by_zone.get(key, [])}, "zones"
        if not squares:
            continue
        alert = {published: properties.get(nws) for nws, published in RELAYED.items()}
        alert["placed_by"] = placed_by
        alert["squares"] = [list(sq) for sq in sorted(squares)]
        alerts.append(alert)
    alerts.sort(key=lambda a: a["id"])

    return {
        "payload": PAYLOAD,
        "schema": SCHEMA,
        "source": SOURCE,
        "credit": CREDIT,
        "fetched_at": _stamp(fetched_at),
        "nws_updated": body.get("updated"),
        "generated_at": _stamp(generated_at),
        "release": squares_doc["release"],
        "zone_files": squares_doc["zone_files"],
        "alerts": alerts,
        "unknown_zones": sorted(missing),
    }


# --------------------------------------------------------------------------
# NWS. Network.


def fetch() -> tuple[dict, datetime]:
    """(the response body, when it was asked for)."""
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    session.headers["Accept"] = "application/geo+json"
    asked = datetime.now(UTC)
    body = request_with_retry(ALERTS_URL, session=session, timeout=60, label="NWS active alerts").json()
    return body, asked


def main() -> dict:
    squares_doc = json.loads(SQUARES_PATH.read_text())
    if "zones" not in squares_doc:
        raise SystemExit(f"{SQUARES_PATH} predates each square's zones; run build_weather_squares.py first")
    body, fetched_at = fetch()
    document = bake(squares_doc, body, fetched_at, datetime.now(UTC))

    CONDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    write_text_atomically(ALERTS_PATH, json.dumps(document, separators=(",", ":")) + "\n")
    manifest = {
        "artifacts": {
            PAYLOAD: {
                "path": to_manifest_path(ALERTS_PATH),
                "sha256": sha256_file(ALERTS_PATH),
                "count": len(document["alerts"]),
                "generated_at": document["generated_at"],
            }
        }
    }
    write_text_atomically(MANIFEST_PATH, json.dumps(manifest, indent=2) + "\n")

    total = len(check_response(body))
    squares = {tuple(sq) for alert in document["alerts"] for sq in alert["squares"]}
    print(
        f"{len(document['alerts'])} of {total} active NWS alerts reach a trail square "
        f"({len(squares):,} squares); asked at {document['fetched_at']}, NWS updated {document['nws_updated']}"
    )
    if document["unknown_zones"]:
        # A GitHub annotation, so a stale pin shows on the run page rather
        # than only in a log nobody opens. The alerts naming these zones are
        # published where their other zones or polygon place them, and not
        # at all if these were their only zones.
        print(
            f"::warning title=NWS zones the pinned outlines do not know::{', '.join(document['unknown_zones'])} - "
            "NWS may have replaced its zone files; see ZONE_FILES in build_weather_squares.py"
        )
    return manifest


if __name__ == "__main__":
    main()
