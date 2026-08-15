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

THE CLASSES ARRIVE DISJOINT, WHICH IS THE OPPOSITE OF WHAT WAS ASSUMED
----------------------------------------------------------------------
This export was first written to subtract each class from the one below it,
on the widely-repeated understanding that USDM ships D0 as a polygon
CONTAINING D1, which contains D2, and so on - the form its shapefiles are
usually described in, and a form that would matter here, because translucent
fills over nested sheets paint a D3 area four times and put the darkest ink
wherever polygons stack rather than where the drought is worst.

**Measured against the 2026-08-11 release, that is not what this endpoint
serves.** All ten class pairs intersect in exactly zero area, and the five
class areas sum to 629.563 square degrees against a union of 629.563 - so
`droughtmonitor.unl.edu/data/json/usdm_*.json` publishes mutually exclusive
classes and the subtraction was a no-op that tripled the artifact's size for
nothing. `spike_water_conditions.py`'s `measure_class_overlap` is that
measurement, re-runnable, and this note exists so the next reader does not
re-add the difference on the strength of the same reasonable assumption.

What follows from it: one pixel already carries exactly one class, a
translucent fill is safe as-is, and every `trail_miles` below is the mileage
whose class is exactly this one - NOT "this class or worse". They sum to the
total under any drought at all.

**The trail miles are measured here and shipped with the bands.** The client
could not compute them without the centerline index and a spherical length
routine, and a hiker reading "206 miles of severe drought ahead" is reading
the claim this artifact exists to make.

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

# How hard the centerline is simplified before it is buffered. About 110 m,
# against a 10 km buffer - three orders of magnitude of headroom, and
# `verify_corridor_covers_trail` re-proves it every run against the FULL
# line rather than this simplified one.
CORRIDOR_SIMPLIFY_DEG = 0.001

# How hard the buffered corridor's own outline is smoothed, about 550 m.
#
# This is the single biggest lever on the artifact's size, and it is safe to
# pull because the corridor edge is OURS: it is an arbitrary 10 km choice,
# not a boundary in anybody's data, and every published polygon that follows
# it is following a line we invented. The drought boundaries inside it are
# untouched, which is the half that is somebody's measurement.
#
# Measured on the 2026-08-11 release: without this the artifact is 749,464
# bytes, because the clip makes every band trace the trail's own switchbacks
# at 110 m. With it, see the size the export prints.
CORRIDOR_SMOOTH_DEG = 0.005

# Area, in square degrees, below which two classes count as non-overlapping.
# The measured value across all ten pairs of the 2026-08-11 release is
# exactly 0.0; this is slack for a future release whose rings touch.
OVERLAP_TOLERANCE_SQ_DEG = 1e-6

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


def source_classes(document: dict) -> dict[int, object]:
    """USDM's polygons as one geometry per class, exactly as published."""
    by_class: dict[int, list] = {}
    for feature in document["features"]:
        by_class.setdefault(feature["properties"]["DM"], []).append(shape(feature["geometry"]))
    return {level: unary_union(parts).buffer(0) for level, parts in sorted(by_class.items())}


def verify_classes_disjoint(classes: dict[int, object]) -> None:
    """Refuse if a release ever does ship overlapping classes.

    The module docstring records that this endpoint's classes are mutually
    exclusive, measured. That is a fact about NDMC's output rather than a
    promise they have made, so it is checked on every run instead of trusted:
    if a future release nests them, translucent fills would silently paint the
    worst areas darkest-by-stacking, and the artifact's `trail_miles` would
    quietly change meaning from "exactly this class" to "this class or worse".
    Both are wrong quietly, which is the kind this pipeline checks for.
    """
    levels = sorted(classes)
    for index, level in enumerate(levels):
        for worse in levels[index + 1 :]:
            overlap = classes[level].intersection(classes[worse]).area
            if overlap > OVERLAP_TOLERANCE_SQ_DEG:
                raise SystemExit(
                    f"D{level} and D{worse} overlap by {overlap:.6f} sq deg, so this release "
                    "nests its classes where every measured one has not. Nothing was published: "
                    "the bands would need differencing before they could be drawn or counted. "
                    "See this module's docstring and spike_water_conditions.py's "
                    "measure_class_overlap."
                )


def verify_corridor_covers_trail(line: MultiLineString, corridor) -> None:
    """Prove the clip cannot have lost trail, rather than sampling for it.

    If the centerline lies entirely within the corridor then for ANY geometry
    X, `line n (X n corridor)` equals `line n X` - the clip cannot change a
    trail measurement it cannot reach. Proving containment once therefore
    proves it for every class, this week and every week, where the spike this
    descends from re-measured each class against the unclipped national
    polygons and could only ever prove it for the classes that happened to be
    present (and cost minutes doing it, meeting a 27 MB multipolygon each
    time).

    WHAT IT ACTUALLY GUARDS, which is narrower than it first looks. The
    BUFFER can never fail this: a buffer always contains the geometry it was
    grown from, at any radius. The two simplifications are the real risk, and
    `CORRIDOR_SIMPLIFY_DEG` is the sharp one - it cuts corners off the line
    *before* the buffer is grown, so a switchback whose corner is trimmed by
    more than the buffer's width ends up outside the corridor. That cannot
    happen at the shipped settings, where the buffer is ninety times the
    simplification, and this is here for the change that alters one of them
    without the other.
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

    `trail_miles` is the mileage whose class is EXACTLY this one, because
    that is how NDMC publishes the polygons (see the module docstring's
    measurement). The numbers therefore sum to the total under any drought at
    all, and none of them is a "this class or worse" figure - a distinction
    worth keeping straight, because the first draft of this pipeline and of
    WATER_CONDITIONS.md §4 both read them the other way and were wrong by
    511 trail miles.

    THE PAYLOAD IS A LIST OF FEATURES, NOT A FeatureCollection, and that is
    for the client's benefit rather than a GeoJSON opinion.
    `lib/publishedConditions.ts` reads every artifact in this family through
    one validated function, and that function refuses a document whose payload
    is not an array - which is what makes a reports document served on the
    closures key read as "no usable baseline" instead of as an empty trail.
    Wrapping these features into a FeatureCollection is one line in the client
    and MapLibre wants that shape anyway; earning the shared reader's
    `generated_at` strictness is worth more than matching a file format here.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        "valid_start": stamp.isoformat(),
        "valid_end": (stamp + timedelta(days=6)).isoformat(),
        PAYLOAD: [
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
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> dict:
    release_path, stamp = newest_release()
    document = json.loads(release_path.read_text())
    line = load_centerline()

    # Simplified BEFORE buffering, which is the difference between a job that
    # runs in seconds and one that runs in four minutes: buffering the
    # centerline at full resolution took 235 s measured here, against 0.7 s
    # for the containment check that follows it. The tolerance is ~110 m
    # against a 10 km buffer, so it cannot move the corridor edge anywhere
    # near the trail - and `verify_corridor_covers_trail` proves that on every
    # run rather than leaving it as an argument.
    corridor = line.simplify(CORRIDOR_SIMPLIFY_DEG).buffer(CORRIDOR_BUFFER_DEG).simplify(CORRIDOR_SMOOTH_DEG)
    verify_corridor_covers_trail(line, corridor)

    classes = source_classes(document)
    verify_classes_disjoint(classes)

    bands = {}
    for level, geometry in classes.items():
        piece = geometry.intersection(corridor)
        if not piece.is_empty:
            bands[level] = piece
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
