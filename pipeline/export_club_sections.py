"""Publish which club maintains which stretch of trail (#594).

Thirty clubs maintain the A.T. `sources.json` has registered
`trail_club_sections` since 2026-07-25 and `pipeline/README.md` records that
nothing downstream reads it, so the app has never been able to answer "who
looks after this?" on the map - a question features/VOLUNTEERING.md,
features/SAYING_THANKS.md and the backend's `Club`/`MaintainerAssignment`
models are all already built around.

WHY THIS IS A SEPARATE ARTIFACT RATHER THAN A PROPERTY ON trails.geojson

Same reason export_spurs.py is: the client stores `trails.geojson` as an opaque
Blob (client/src/lib/trailData.ts) and never reads a property off it, and its
record schema is checked by verify_release.py and the schema-drift job. A small
keyed artifact is additive and costs those nothing.

MapLibre *does* read that file's properties - `blaze_color` is how a line gets
its colour - so drawing the corridor as thirty coloured stretches will likely
want an `Acronym` on the centerline records too. That is a change to a
published schema, so it belongs with the issue that draws the map (#598) rather
than being smuggled in here.

WHERE THE ATTRIBUTION COMES FROM

lib/club_sections.py's docstring carries the argument and the measurements. The
short version: the CENTERLINE carries the club on every feature and was edited
2026-08-04; the polygon layer was edited 2024-08-15. Fresh source decides which
stretch; stale source decides only how a name is spelled.

The mile itself comes from `half_mile_points_from_springer`, which is the
pipeline's existing answer to "where am I along the trail" - 4,395 points
carrying `Measure` from 0.5 to 2197.5. Each milepost is snapped to the nearest
centerline vertex and inherits its club.

NO NETWORK - reads data/raw/<key>.geojson, which fetch_all.py writes.

    .venv/Scripts/python export_club_sections.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.club_sections import (
    CENTERLINE_ACRONYM_FIELD,
    MILEPOST_SNAP_M,
    assemble,
    canonical_clubs,
    is_attributable,
)
from lib.spurs import PointIndex

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "club_sections.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "club_sections_manifest.json"

CENTERLINE_KEY = "centerline"
MILEPOSTS_KEY = "half_mile_points_from_springer"
POLYGONS_KEY = "trail_club_sections"

# half_mile_points_from_springer's mile-from-Springer field, 0.5 to 2197.5.
# lib/atc_updates.py pins the same field for the same reason.
MEASURE_FIELD = "Measure"


def load_features(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path} is missing - run fetch_all.py first")
    return json.loads(path.read_text()).get("features", [])


def build_club_index(centerline_features: list[dict]) -> PointIndex:
    """Every centerline vertex, carrying its feature's club acronym.

    Vertices rather than segments, which is lib/spurs.py's own approximation
    and is bounded by the centerline's vertex spacing - metres, in ATC's data.
    Against a milepost that sits on the line, that changes no answer.

    A feature whose acronym is one of the 47 broken numeric values indexes as
    None, so a milepost there comes back unattributed rather than snapping past
    it to a neighbouring club's vertex and being quietly mis-credited.
    """
    points: list[tuple[float, float, object]] = []
    for feature in centerline_features:
        properties = feature.get("properties") or {}
        raw = properties.get(CENTERLINE_ACRONYM_FIELD)
        acronym = raw.strip() if is_attributable(raw) else None
        for lon, lat in _iter_line_coordinates(feature.get("geometry") or {}):
            points.append((lat, lon, acronym))
    return PointIndex(points, MILEPOST_SNAP_M)


def _iter_line_coordinates(geometry: dict):
    """LineString and MultiLineString both, which the real data has - see
    export_trails.py's geometry_to_wkt, where treating them as one type would
    have erased real trail mileage."""
    coordinates = geometry.get("coordinates") or []
    if geometry.get("type") == "LineString":
        yield from ((point[0], point[1]) for point in coordinates if len(point) >= 2)
    elif geometry.get("type") == "MultiLineString":
        for line in coordinates:
            yield from ((point[0], point[1]) for point in line if len(point) >= 2)


def attribute_mileposts(milepost_features: list[dict], index: PointIndex) -> list[tuple[float, str | None]]:
    """(mile, acronym) for every milepost, acronym None where unknown."""
    attributed = []
    for feature in milepost_features:
        properties = feature.get("properties") or {}
        mile = properties.get(MEASURE_FIELD)
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if mile is None or len(coordinates) < 2:
            continue
        acronym, _ = index.nearest(coordinates[1], coordinates[0])
        attributed.append((float(mile), acronym))
    return attributed


def build_output(raw_dir: Path = RAW_DIR) -> dict:
    centerline = load_features(raw_dir / f"{CENTERLINE_KEY}.geojson")
    mileposts = load_features(raw_dir / f"{MILEPOSTS_KEY}.geojson")
    polygons = load_features(raw_dir / f"{POLYGONS_KEY}.geojson")

    attributed = attribute_mileposts(mileposts, build_club_index(centerline))
    clubs, unattributed = assemble(attributed, canonical_clubs(polygons))

    return {
        # Named per source rather than as one "as of" date, because they are
        # two years apart and a hiker reading a club name is entitled to know
        # which half of that they are looking at.
        "sources": {
            "attribution": CENTERLINE_KEY,
            "names": POLYGONS_KEY,
            "miles": MILEPOSTS_KEY,
        },
        "clubs": [
            {
                "acronym": club.acronym,
                "name": club.name,
                "region": club.region,
                "stretches": [{"start_mile": start, "end_mile": end} for start, end in club.stretches],
                "miles": round(club.miles, 1),
            }
            for club in clubs
        ],
        # Published, not omitted. 41 miles the fresh source cannot name reads
        # as "not recorded"; leaving it out would read as "no trail here".
        "unattributed": [{"start_mile": start, "end_mile": end} for start, end in unattributed],
    }


def main() -> dict:
    output = build_output()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")

    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    # ABSOLUTE path, like every sibling manifest (export_trails.py's is the
    # precedent publish-vector-data.yml cites): publish.py resolves this
    # string against its own CWD, so the relative path this used to store
    # crashed any publish not started from pipeline/ - mid-loop, which is
    # exactly how a partial flat-key state gets made (#659).
    manifest = {"path": str(OUT_PATH), "sha256": digest}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    unattributed_miles = sum(r["end_mile"] - r["start_mile"] for r in output["unattributed"])
    print(f"{len(output['clubs'])} clubs -> {OUT_PATH}")
    print(f"  unattributed: {len(output['unattributed'])} runs, {unattributed_miles:.1f} mi")
    for club in output["clubs"]:
        stretches = len(club["stretches"])
        suffix = f"  ({stretches} stretches)" if stretches > 1 else ""
        print(f"  {club['acronym']:<8} {club['miles']:>7.1f} mi  {club['name']}{suffix}")
    # The manifest, not the artifact body - the shape every sibling
    # exporter's main() returns, and the thing a caller chaining into
    # publish.py actually needs (#659).
    return manifest


if __name__ == "__main__":
    main()
