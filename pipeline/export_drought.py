"""Clip the week's drought polygons to the corridor and publish them (#720).

The fourth artifact in the family
[CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) established:

    conditions/closures.json        verified OurHike closures
    conditions/reports.json         verified public reports
    conditions/atc_updates.json     the ATC's own notices
    conditions/drought.json         this week's drought, along the trail   (this)

It belongs in that family rather than in the basemap for one measured reason:
the national file is 27.6 MB and this artifact is about 10 KB gzipped
([WATER_CONDITIONS.md](WATER_CONDITIONS.md) §4), so the weekly refresh costs a
hiker nothing and does not need a map package rebuilt to stay current. A
drought layer baked into a downloaded package would be stale the moment
NDMC's next Thursday release landed, and a hiker in the Hundred-Mile
Wilderness would have no way to know.

TWO DECISIONS THAT ARE NOT COSMETIC
-----------------------------------
**The classes are un-nested here, not in the client.** USDM ships D0 as a
polygon that CONTAINS D1, which contains D2, and so on - five overlapping
sheets. Drawn as translucent fills in that form, a D3 area is painted four
times and comes out darker than its own colour, so the map's darkest ink
would land wherever the polygons happen to stack rather than where the
drought is worst. This subtracts each class from the one below it, so every
published band is disjoint and one pixel carries exactly one class. Doing it
in the pipeline rather than the client is deliberate: it is a property of the
data, and a client that got it wrong would be wrong quietly.

**The trail miles are measured here and shipped with the bands.** The client
could not compute them without the centerline index and a spherical length
routine, and a hiker reading "206 miles of severe drought ahead" is reading
the claim this artifact exists to make. Measuring it beside the clip also
gives the export something to check itself against - see `verify_clip`.

WHAT THIS ARTIFACT DOES NOT CLAIM
---------------------------------
Nothing about any water source. WATER_CONDITIONS.md is emphatic that this is
a regional signal and that the failure mode worth designing against is a
hiker reading it as a promise about the spring at the next shelter. The
artifact carries no POI reference, no water field and no per-source anything,
and the client draws it as a background wash for the same reason.

    python export_drought.py
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from shapely.geometry import MultiLineString, mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw" / "drought"
CENTERLINE_PATH = ROOT / "data" / "raw" / "centerline.geojson"
OUT_DIR = ROOT / "data" / "processed" / "conditions"
OUT_PATH = OUT_DIR / "drought.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "drought_manifest.json"

# The payload name, which becomes `conditions/<name>.json` in the bucket and
# the field the client validates the document by. A key in that bucket is a
# URL deployed clients already request and can never be renamed
# (lib/r2_keys.py), so it is spelled once, here.
PAYLOAD = "drought"

# Half-width of the published corridor, in degrees of latitude - about 10 km.
#
# Wide enough that the band still reads as a *region* rather than as a stripe
# painted along the footpath, which is the whole point of drawing it: the
# claim is "this area is dry", and a tint exactly as wide as the trail would
# look like a claim about the trail. Narrow enough that the artifact stays
# small - measured 2026-08-15 at 32,359 bytes, 10,163 gzipped, with the clip
# reproducing every class's trail mileage to within 0.002 mi
# (spike_water_conditions.py's `measure_drought_layer`).
CORRIDOR_BUFFER_DEG = 0.09

# How far a clipped band's measured trail mileage may sit from the same
# measurement against the unclipped national polygon before the export
# refuses. The measured worst case is 0.002 mi; 0.05 leaves room for a week
# whose polygons happen to graze the corridor edge without leaving room for a
# clip that actually lost a stretch of trail.
CLIP_TOLERANCE_MI = 0.05

# USDM's own names, in its own order. `DM` is the numeric class on every
# feature; the labels ride along so the client renders NDMC's vocabulary
# rather than a paraphrase of it.
CLASS_LABELS = {
    0: "Abnormally dry",
    1: "Moderate drought",
    2: "Severe drought",
    3: "Extreme drought",
    4: "Exceptional drought",
}

EARTH_R_M = 6_371_008.8
METRES_PER_MILE = 1609.344


def _stamp_utc(value: datetime) -> str:
    """The same `...Z` stamping the rest of this family uses: a naive
    timestamp is read as *local* by `new Date()`, which moves every date a
    hiker reads by their own offset."""
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def haversine_m(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(h))


def line_miles(geometry) -> float:
    """Great-circle length of whatever line geometry it is handed.

    Spherical rather than planar because the trail spans eleven degrees of
    latitude: a degree of longitude is 1.4 km shorter at Katahdin than at
    Springer, and a planar length would quietly overstate the north.
    """
    parts = [geometry] if geometry.geom_type == "LineString" else list(getattr(geometry, "geoms", []))
    total = 0.0
    for part in parts:
        if part.geom_type != "LineString":
            continue
        coords = list(part.coords)
        for i in range(1, len(coords)):
            total += haversine_m(coords[i - 1], coords[i])
    return total / METRES_PER_MILE


def load_centerline() -> MultiLineString:
    """ATC's centerline as separate parts.

    Separate parts, emphatically: joining the ~3,000 features into one line
    draws a jump between every pair and measures the A.T. at about 108,000
    miles instead of 2,172. That mistake was made once, in the spike this
    export descends from, and the guard against repeating it is that this
    function is the only place the geometry is assembled.
    """
    document = json.loads(CENTERLINE_PATH.read_text())
    parts: list[list] = []
    for feature in document["features"]:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "LineString":
            parts.append(geometry["coordinates"])
        elif geometry.get("type") == "MultiLineString":
            parts.extend(geometry["coordinates"])
    parts = [part for part in parts if len(part) > 1]
    if not parts:
        raise SystemExit(f"{CENTERLINE_PATH} holds no line geometry, so there is no corridor to clip to.")
    return MultiLineString(parts)


def newest_release() -> tuple[Path, date]:
    releases = sorted(RAW_DIR.glob("usdm_*.json"))
    if not releases:
        raise SystemExit(
            f"No drought release under {RAW_DIR}. Run fetch_drought.py first - this script "
            "publishes what was fetched and never reaches upstream itself."
        )
    newest = releases[-1]
    stamp = datetime.strptime(newest.stem.removeprefix("usdm_"), "%Y%m%d").date()
    return newest, stamp


def nested_classes(document: dict) -> dict[int, object]:
    """USDM's polygons as one geometry per class, still nested."""
    by_class: dict[int, list] = {}
    for feature in document["features"]:
        by_class.setdefault(feature["properties"]["DM"], []).append(shape(feature["geometry"]))
    return {level: unary_union(parts).buffer(0) for level, parts in sorted(by_class.items())}


def disjoint_bands(classes: dict[int, object]) -> dict[int, object]:
    """Each class minus the worse one inside it - see the module docstring."""
    levels = sorted(classes)
    bands = {}
    for index, level in enumerate(levels):
        band = classes[level]
        for worse in levels[index + 1 :]:
            band = band.difference(classes[worse])
        if not band.is_empty:
            bands[level] = band
    return bands


def verify_corridor_covers_trail(line: MultiLineString, corridor) -> None:
    """Prove the clip cannot have lost trail, rather than sampling for it.

    A buffer slightly too tight loses a stretch of trail near the corridor
    edge, and nothing downstream would notice: the artifact would still be a
    valid map of *something*. The spike this descends from caught that by
    re-measuring every class against the unclipped national polygons and
    comparing - which works, and costs minutes, because each comparison
    intersects the whole centerline with a 27 MB multipolygon.

    This checks the stronger property directly and in seconds. If the
    centerline lies entirely within the corridor, then for ANY geometry X,
    `line n (X n corridor)` equals `line n X` - the clip cannot change a trail
    measurement it cannot reach. Proving containment once therefore proves it
    for every class, this week and every week, where the sampled version only
    ever proved it for the classes that happened to be present.
    """
    outside = line.difference(corridor)
    stray = line_miles(outside)
    if stray > CLIP_TOLERANCE_MI:
        raise SystemExit(
            f"{stray:.3f} mi of centerline lies outside the {CORRIDOR_BUFFER_DEG} deg corridor "
            f"buffer, past the {CLIP_TOLERANCE_MI} mi tolerance, so a clipped band could be "
            "missing trail. Nothing was published. Widen CORRIDOR_BUFFER_DEG, or find out why "
            "the centerline moved."
        )


def band_miles(line: MultiLineString, bands: dict[int, object]) -> dict[int, float]:
    """Trail miles whose worst class is exactly this band's."""
    return {level: line_miles(line.intersection(band)) for level, band in bands.items()}


def build_document(
    bands: dict[int, object],
    miles: dict[int, float],
    stamp: date,
    generated_at: datetime,
) -> dict:
    """The artifact.

    `valid_start` and `valid_end` are USDM's own week, and they are the dates
    the client renders. The bake's `generated_at` is here too and is the less
    interesting of the two: a nightly bake of a Tuesday release would
    otherwise claim a freshness nobody has, which is the trap
    export_atc_updates.py records for the ATC file and which applies to every
    weekly source.

    `trail_miles` is the *disjoint* band's mileage - the miles whose worst
    class is exactly this one - so the numbers sum to the total affected
    rather than nesting. That is the opposite convention from
    WATER_CONDITIONS.md §4's table, which reports "this class or worse", and
    the difference is called out in `label` so a reader cannot silently
    compare the two.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        "valid_start": stamp.isoformat(),
        "valid_end": (stamp + timedelta(days=6)).isoformat(),
        PAYLOAD: {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {
                        "dm": level,
                        "label": CLASS_LABELS[level],
                        "trail_miles": round(miles[level], 1),
                    },
                    "geometry": mapping(band),
                }
                for level, band in sorted(bands.items())
            ],
        },
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> dict:
    release_path, stamp = newest_release()
    document = json.loads(release_path.read_text())
    line = load_centerline()

    corridor = line.buffer(CORRIDOR_BUFFER_DEG).simplify(0.01)
    verify_corridor_covers_trail(line, corridor)

    # Un-nest first, then clip. The other order also works and is slower for
    # nothing: differencing five national sheets against each other costs far
    # more than differencing five corridor slivers, and the result is the same
    # because intersection distributes over difference.
    clipped = {}
    for level, geometry in nested_classes(document).items():
        piece = geometry.intersection(corridor)
        if not piece.is_empty:
            clipped[level] = piece
    bands = disjoint_bands(clipped)
    miles = band_miles(line, bands)

    if not bands:
        # Not a failure, and not an empty artifact either. A trail with no
        # drought on it is the good week, and it has to be publishable as
        # such - a missing file would render as "no layer", which is a
        # different claim from "no drought".
        print("No drought class touches the corridor this week. Publishing an empty band set.")

    generated_at = datetime.now(timezone.utc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(build_document(bands, miles, stamp, generated_at), indent=2) + "\n")

    manifest = {
        "artifacts": {
            PAYLOAD: {
                "path": str(OUT_PATH),
                "sha256": sha256_file(OUT_PATH),
                "count": len(bands),
                "generated_at": _stamp_utc(generated_at),
                "valid_start": stamp.isoformat(),
            }
        }
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    summary = ", ".join(f"D{level} {miles[level]:.1f} mi" for level in sorted(bands))
    print(f"Wrote {OUT_PATH} for the week of {stamp:%Y-%m-%d}: {summary or 'no drought on the trail'}.")
    print(f"  {OUT_PATH.stat().st_size} bytes")
    return manifest


if __name__ == "__main__":
    main()
