"""The ground the offline basemap build covers, as named regions (#1458).

WHY THIS EXISTS. BASEMAP.md has said since 2026-08 that "the corridor polygon
is a *parameter* end to end. Nothing in either script assumes the AT; today's
defaults point at it" - and that was true of the FUNCTIONS and false of the
one caller. export_basemap.main() built the A.T. corridor and handed it
straight to the clip, so there was no way to ask for a different shape
without editing the module. This is that parameter, made real.

WHAT IT IS FOR, MEASURED. The trail lines were cut into 1-degree coverage
cells nationwide by #1257 - 525 cells hold a tile. The sheet UNDER them was
not: 62 cells, because the basemap is built corridor-shaped around one trail.
So the phone can hold other organizations' lines over most of the country and
the ground to draw them on over a thin band of it.

New York City is the first case anybody can walk into, and it is the reason
this landed now: 7,059 NYC Parks trail segments and 3,030 NYC DOT greenway
segments ship in `nearby_trails` today (#1432), and the A.T. corridor passes
about forty miles north of them.

A REGION IS A BUFFER AROUND LINES, WHICH IS WHAT THE A.T.'S ALREADY IS. The
corridor is ST_Buffer around ATC's centerline; `nyc` below is the same
construction around the city's own two layers. That matters beyond tidiness:
it keeps the shape a statement about WHERE THE TRAILS ARE rather than a box
somebody drew around a city, which is the distinction the maintainer drew on
2026-08-25 when they struck the proposed ring around New York - "Don't limit
data from orgs based on geography." A build has to have some extent; this one
is derived from the same lines the app draws rather than from a boundary.

WHY 3 KM, AND IT IS BORROWED RATHER THAN PICKED. features/OFFLINE_COVERAGE.md
§4 already had to answer "how far past the edge of the data does somebody
need map", for the seam margin, and answered 3 km - cut_cells.SEAM_MARGIN_KM.
It is the same question here, so it gets the same number and inherits its
status: @unvalidated, picked and not found. What would settle it is what
would settle that one - how far past a boundary a hiker actually pans and
walks, once there is behaviour to measure. Stated in kilometres rather than
degrees for the reason that constant is: a degree of longitude is 111 km at
the equator and 85 km at New York, while the thing being promised is ground.

WHAT THIS DELIBERATELY DOES NOT DO. It does not try to cover the 525. The
whole US is marked "marginal" against a free runner's 88 GB and North America
"does not fit" (BASEMAP.md's measured table), so a region set that reached
them would be a promise this repository has already measured itself unable to
keep. Regions are added one at a time, each with its cost measured by the run
that builds it.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import shapely
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import unary_union

from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

#: The same number, for the same question, as cut_cells.SEAM_MARGIN_KM - see
#: the module docstring. @unvalidated.
REGION_BUFFER_KM = 3.0

#: The registered sources whose lines define the `nyc` region. Named by
#: registry key so a reader can find them in sources.json, and so adding the
#: city's next layer is one entry rather than a new polygon.
NYC_SOURCE_KEYS = ("nyc_parks_trails", "nyc_dot_greenways")

_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform
_TO_GEOGRAPHIC = Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True).transform


def _projected(geometry, transform):
    """`geometry` through a pyproj transform, one vectorised call for the lot.

    `shapely.transform` hands the WHOLE coordinate array to the callable;
    `shapely.ops.transform` walks the geometry part by part. On a city's
    lines that is the difference between a build and a dead runner - see
    buffer_km below for the measurement.
    """
    return shapely.transform(geometry, lambda coords: np.column_stack(transform(coords[:, 0], coords[:, 1])))


def buffer_km(geometry, km: float = REGION_BUFFER_KM):
    """`geometry` buffered by `km`, measured in metres rather than degrees.

    Projected to EPSG:5070 and back, the same round trip lib/corridor.py makes
    for the same reason: a buffer in degrees is a different amount of ground
    at each end of the country, and the thing being promised is ground.

    PART BY PART AND THEN UNIONED, WHICH IS THE WHOLE REASON THIS FUNCTION
    HAS A BODY WORTH READING. The obvious spelling - `ops.transform`, then
    `.buffer()` on the multi-part geometry - killed two GitHub runners before
    it was measured, and the failure gave no Python output at all, only the
    runner's own shutdown notice ninety seconds in. Measured 2026-09-15
    against New York City's real two layers, 13,581 parts and 92,174
    vertices after the union:

        ops.transform (part by part)             > 100 s, then the runner died
        shapely.transform (one array)               0.01 s

        MultiLineString.buffer(3000)             > 100 s, then the runner died
        shapely.buffer(parts) + union_all           0.53 s + 1.22 s

    Both halves had to change; either alone still fails. GEOS buffers a
    thousands-part geometry as one job and does it badly, while a cascaded
    union over the same parts already buffered is what it is good at, so
    the arc resolution stays the DEFAULT - lowering it was tried and bought
    nothing, and a coarser arc would have had to be paid back by buffering
    wider to keep the promise a superset.
    """
    parts = shapely.get_parts(_projected(geometry, _TO_METRIC))
    return _projected(shapely.union_all(shapely.buffer(parts, km * 1000.0)), _TO_GEOGRAPHIC)


def lines_of(path: Path):
    """Every geometry in a fetched GeoJSON layer, as one shapely collection.

    A feature with no geometry is skipped rather than raising - nine of the
    greenway rows are exactly that, and the export already drops them as
    `no geometry`, so a build that fell over on them would be the only thing
    in the pipeline that did.
    """
    features = json.loads(path.read_text()).get("features") or []
    geometries = [shape(f["geometry"]) for f in features if f.get("geometry") and f["geometry"].get("coordinates")]
    return unary_union(geometries) if geometries else None


def region_from_layers(paths: list[Path], km: float = REGION_BUFFER_KM):
    """One region: the union of several fetched layers' lines, buffered.

    Raises rather than returning an empty shape when nothing is readable. A
    region that silently came back empty would shrink the build's clip without
    failing it, and the first anybody would know is a hiker in a city with no
    map - the quiet failure this whole area keeps producing.
    """
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"build region needs {', '.join(p.name for p in missing)} - run fetch_external_layers.py first.")
    parts = [lines for lines in (lines_of(p) for p in paths) if lines is not None]
    if not parts:
        raise SystemExit(f"build region: {', '.join(p.name for p in paths)} hold no geometry between them.")
    return buffer_km(unary_union(parts), km)


def combined(shapes: list) -> object:
    """The build's clip shape: every requested region as one geometry.

    Overlapping regions are ordinary and union cleanly - New York City's
    northern edge and the A.T. corridor's southern one are 40 miles apart
    today, but a region added between them should cost nothing extra rather
    than being refused.
    """
    if not shapes:
        raise SystemExit("no regions selected - the build needs at least one shape to clip to.")
    return unary_union(shapes)
