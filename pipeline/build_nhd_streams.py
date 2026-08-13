"""Build reference/nhd_streams.json - the nearest USGS-mapped stream to each
A.T. shelter, keyed to ATC's own GlobalIDs.

This is WATER_SOURCES.md §7's option 2, the sentence half of #529: 58% of
the 280 shelters have a mapped flowing stream within 250 m (measured against
every shelter, spike_shelter_water.py), but NHD often does not know the
shelter's *actual* source - Thomas Knob's spring is 707 m from the nearest
mapped perennial stream - so what this data may honestly become is a
proximity sentence on the shelter card ("Nearest mapped stream: Stony Brook,
about 70 m"), never a water pin. lib/poi_description.stream_sentence
composes the words; this file holds the facts it composes from.

**Streams only, and which FCodes that means.** NHDPlus HR flowlines carry a
five-digit FCode: 46006 is a stream mapped as perennial, 46003 intermittent,
46007 ephemeral, 46000 a stream with no flow classification. Those four are
what "stream" means here. Artificial paths (55800 - the centerline threads
drawn through lakes so the network stays connected) and canals/ditches are
excluded by asking for what is wanted: an artificial path is not a stream a
hiker walks to, and a pond's honesty question is deliberately unanswered
(see fetch_osm_water.py's docstring for the same line drawn on the OSM
side).

**"Mapped as", never "is".** The perennial/intermittent code was largely
transcribed from decades-old topo surveys: measured against 10,055 field
observations it agrees 80.5% of the time overall and ~50% at headwater
sites, with dry observations five times likelier to disagree
(WATER_SOURCES.md §5 holds the citations). The composed sentence says
"mapped as year-round" for exactly that reason, and nothing downstream may
strengthen it.

**Why the output is checked in rather than fetched at build time.** The same
reason shelter_capacity.json and water_distance.json are - the derivation
encodes judgement (which FCodes are streams, what radius the claim stops at)
and a checked-in file makes every change a reviewable diff - plus one more
this source adds: **NHD is a frozen snapshot.** USGS retired it 2023-10-01;
it is served but never updated, and its 3DHP successor drops the
perennial/intermittent attribute entirely (§5). A fetch at every build would
re-download an unchanging answer and put the release at the mercy of a
service USGS keeps up only "while 3DHP is populated". Fetch once, review,
check in.

Re-run this script if the shelter layer gains features (the join is by
GlobalID, so new shelters arrive as new rows) or if USGS ever revises the
snapshot; review the diff it makes.

Licence: NHD is U.S. federal work, public domain. USGS asks for a courtesy
citation; the source block below carries it.

Usage:
    python build_nhd_streams.py [--check]

`--check` re-derives the file and exits non-zero if it differs from what is
on disk, without writing.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import requests

from build_water_distance import fetch_atc_features

ROOT = Path(__file__).parent
OUT_PATH = ROOT / "reference" / "nhd_streams.json"

# The two flowline layers of the NHDPlus HR service on The National Map -
# network (participates in flow routing) and non-network (isolated reaches).
# A shelter's nearest stream can honestly be either. Deliberately NOT in
# sources.json: the registry is what the fetchers pull on a schedule, and
# this source is a frozen snapshot read once by a build script - the same
# standing build_water_distance.py gives the CSI layer, with this docstring
# as the provenance record.
NHDPLUS_HR = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer"
FLOWLINE_LAYERS = (3, 4)

# StreamRiver FCodes: unclassified, intermittent, perennial, ephemeral.
STREAM_FCODES = (46000, 46003, 46006, 46007)

# What each FCode's flow classification is called in this file. The composed
# sentence maps these to words ("mapped as year-round"); the file keeps the
# code's own vocabulary so nothing is lost between here and the wording.
FLOW_CLASSES = {46000: "unclassified", 46003: "intermittent", 46006: "perennial", 46007: "ephemeral"}

# The claim's edge: a stream further than this publishes nothing, and the
# sentence says "no mapped stream within 1 km" - which is also worth
# printing (Blood Mountain's card should say it, because it is true and a
# hiker plans around it). The envelope queried is slightly wider so a stream
# just past a corner of the box cannot be missed at the boundary.
MAX_DISTANCE_M = 1000.0
ENVELOPE_HALF_M = 1200.0

NO_STREAM = f"no mapped stream within {MAX_DISTANCE_M / 1000:g} km"

USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"
TIMEOUT = 90
TRIES = 5

M_PER_DEG_LAT = 111_132.0


def envelope(lat: float, lon: float, half_m: float) -> dict:
    dlat = half_m / M_PER_DEG_LAT
    dlon = half_m / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    return {
        "xmin": lon - dlon,
        "ymin": lat - dlat,
        "xmax": lon + dlon,
        "ymax": lat + dlat,
        "spatialReference": {"wkid": 4326},
    }


def nearest_distance_m(lat: float, lon: float, paths: list[list[list[float]]]) -> float:
    """True minimum distance from (lat, lon) to a flowline's polylines -
    point-to-segment, not vertex-only, because a shelter beside the middle of
    a long straight reach is beside the stream, not beside its endpoints.
    Equirectangular projection around the shelter; exact to well under a
    metre at these radii."""
    mx = M_PER_DEG_LAT * math.cos(math.radians(lat))
    best = math.inf
    for path in paths:
        points = [((x - lon) * mx, (y - lat) * M_PER_DEG_LAT) for x, y in path]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            dx, dy = bx - ax, by - ay
            length_sq = dx * dx + dy * dy
            if length_sq == 0:
                distance = math.hypot(ax, ay)
            else:
                t = max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq))
                distance = math.hypot(ax + t * dx, ay + t * dy)
            if distance < best:
                best = distance
    return best


def query_layer(layer: int, lat: float, lon: float) -> list[dict]:
    """One layer's stream flowlines around one shelter, with geometry.

    Retries with backoff, then raises: a query that ultimately fails must
    stop the build, because the hole it would leave is indistinguishable
    from "no stream within 1 km" - the exact confusion this file exists to
    prevent."""
    params = {
        "geometry": json.dumps(envelope(lat, lon, ENVELOPE_HALF_M)),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
        "where": f"fcode IN ({', '.join(str(code) for code in STREAM_FCODES)})",
        "outFields": "fcode,gnis_name",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "json",
    }
    last: Exception | None = None
    for attempt in range(TRIES):
        try:
            response = requests.get(
                f"{NHDPLUS_HR}/{layer}/query", params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise ValueError(f"NHDPlus HR layer {layer} answered with an error: {payload['error']}")
            return payload.get("features", [])
        except Exception as error:  # noqa: BLE001 - every transport failure retries the same way
            last = error
            time.sleep(2**attempt)
    raise RuntimeError(f"NHDPlus HR layer {layer} failed after {TRIES} tries at ({lat:.4f}, {lon:.4f}): {last}")


def nearest_stream(lat: float, lon: float) -> dict | None:
    """The nearest mapped stream within MAX_DISTANCE_M, or None.

    {distance_m, flow, gnis_name} - gnis_name None where USGS mapped the
    reach without naming it (roughly half of them near shelters)."""
    best: dict | None = None
    for layer in FLOWLINE_LAYERS:
        for feature in query_layer(layer, lat, lon):
            geometry = feature.get("geometry") or {}
            paths = geometry.get("paths") or []
            if not paths:
                continue
            distance = nearest_distance_m(lat, lon, paths)
            if distance > MAX_DISTANCE_M:
                continue
            if best is None or distance < best["distance_m"]:
                attributes = {key.lower(): value for key, value in feature["attributes"].items()}
                best = {
                    "distance_m": round(distance),
                    "flow": FLOW_CLASSES[attributes["fcode"]],
                    "gnis_name": attributes.get("gnis_name"),
                }
    return best


README = [
    "The nearest USGS-mapped stream to each A.T. shelter, keyed to ATC's",
    "GlobalIDs - WATER_SOURCES.md §7 option 2, the facts behind the shelter",
    "card's stream sentence (#529).",
    "",
    "GENERATED by build_nhd_streams.py - re-run that script rather than",
    "editing rows here, and review the diff it produces. export_poi.py reads",
    "this file and lib/poi_description.stream_sentence composes the words; a",
    "record with no stream states that instead, and the card prints it,",
    "because 'no mapped stream within 1 km' is a fact a hiker plans around.",
    "",
    "Streams only (StreamRiver FCodes 46000/46003/46006/46007) - artificial",
    "paths through lakes and canals are not streams and are never requested.",
    "`flow` is the FCode's own classification, verbatim: perennial,",
    "intermittent, ephemeral, or unclassified. The sentence says 'mapped as'",
    "because that classification was largely transcribed from decades-old",
    "topo surveys and disagrees with field observations ~20% of the time",
    "(WATER_SOURCES.md §5) - nothing downstream may strengthen it.",
    "",
    "NHD is a frozen snapshot (USGS retired it 2023-10-01; its successor",
    "drops the flow classification), which is why this is a checked-in file",
    "rather than a per-build fetch: the answer does not change, and a",
    "release should not depend on a service kept up only during a",
    "transition. U.S. federal work, public domain.",
]


def build(features: list[dict]) -> dict:
    records = []
    for feature in features:
        record = {
            "atc_global_id": feature["global_id"],
            "atc_name": feature["name"],
            "distance_m": None,
            "flow": None,
            "gnis_name": None,
        }
        stream = nearest_stream(feature["lat"], feature["lon"])
        if stream is None:
            record["unresolved"] = NO_STREAM
        else:
            record.update(stream)
        records.append(record)

    with_stream = [record for record in records if record["distance_m"] is not None]
    counts = {
        "shelters": len(records),
        "with_stream": len(with_stream),
        "named": sum(1 for record in with_stream if record["gnis_name"]),
    }
    for flow in sorted(set(FLOW_CLASSES.values())):
        counts[flow] = sum(1 for record in with_stream if record["flow"] == flow)

    return {
        "_README": README,
        "source": {
            "title": "NHDPlus High Resolution flowlines (The National Map)",
            "url": NHDPLUS_HR,
            "provider": "U.S. Geological Survey",
            "licence": (
                "U.S. federal work, public domain. Courtesy citation: National Hydrography "
                "Dataset Plus High Resolution, U.S. Geological Survey. Snapshot: NHD was "
                "retired 2023-10-01 and is served unchanged - WATER_SOURCES.md §5."
            ),
            "note": (
                f"Nearest StreamRiver flowline within {MAX_DISTANCE_M:.0f} m of each shelter, "
                "true point-to-segment distance, both network and non-network layers. "
                "Artificial paths and canals excluded by FCode."
            ),
        },
        "counts": counts,
        "shelters": records,
    }


def render(document: dict) -> str:
    return json.dumps(document, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--check",
        action="store_true",
        help="re-derive and compare against the checked-in file instead of writing it",
    )
    args = parser.parse_args(argv)

    print("Fetching the ATC shelters layer ...")
    features = fetch_atc_features("shelters")
    print(f"  {len(features)} shelters.")

    print(f"Querying NHDPlus HR around each shelter ({NHDPLUS_HR}) ...")
    document = build(features)
    counts = document["counts"]
    print(
        f"  {counts['with_stream']}/{counts['shelters']} shelters have a mapped stream "
        f"within {MAX_DISTANCE_M:.0f} m ({counts['named']} of them named)."
    )

    rendered = render(document)
    if args.check:
        current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        if current == rendered:
            print(f"{OUT_PATH} is up to date.")
            return 0
        print(f"{OUT_PATH} differs from what the sources now say - re-run without --check and review the diff.")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
