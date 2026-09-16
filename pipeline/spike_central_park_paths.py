"""Why Central Park draws almost none of its paths (#1530).

The maintainer's report, 2026-09-16: *"Central park is missing most of its
paths."* The first guess was that a filter dropped them - something classed as
a sidewalk, thrown away on the way through. Nothing was dropped.
`export_nearby_trails.keep_reason` has no test `nyc_parks_trails` can fail: the
entry carries no `foot_field`, no `excluded_when` and no `status_field`, so all
312 of the park's rows reach the artifact. The gap is in the layer, not in us.

WHAT THIS MEASURES, AND WHY EACH NUMBER IS HERE.

1. **How thin the registered layer is**, in miles inside NYC Parks' own park
   boundary rather than in the segment COUNT that #1432 read as coverage.
   Prospect Park runs beside it as a control, because a mileage figure alone
   says nothing about whether it is low - two parks out of the same layer,
   compared per acre, do.

2. **Whether the city's street centerline holds the rest**, and whether it is
   the same tread drawn twice or path we do not have at all. #1453 asked the
   first question of the two REGISTERED city layers and found real overlap, so
   the question has to be asked again of any third one rather than assumed.

3. **What the paved-walkway polygons imply**, which is the only measurement
   here that reaches the whole park. It is an AREA divided by a width band
   nobody surveyed, and it is labelled that way wherever it is printed - see
   WALKWAY_WIDTH_BAND_M below for why the band is picked and what would settle
   it.

THIS IS A SPIKE. The measurement is the deliverable and the assembly is
throwaway; what should survive is the SHAPE of the answer - how much of a city
park's path network a trail layer knows, and what it would take to know the
rest. The pure halves are kept honest by tests/test_spike_central_park_paths.py
and take geometries already projected into metres, so the arithmetic is
testable without a projection or a fetch.

INPUTS. The two registered layers come from the files the exporter itself
reads, because "what we ship" has to be measured against what we ship:

  - data/raw/external/nyc_parks_trails.geojson
  - data/raw/external/nyc_park_polygons.geojson

both written by `fetch_external_layers.py`. The two UNREGISTERED layers are
fetched live through lib/socrata.py and cached under data/spike/, which is
gitignored with the rest of data/ - CONTRIBUTING.md's "Data does not go in
commits". Nothing here publishes and nothing here writes to data/processed/.

Run:  python fetch_external_layers.py --only nyc_parks_trails nyc_park_polygons
      python spike_central_park_paths.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from lib.socrata import fetch_dataset_geojson

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw" / "external"
CACHE_DIR = ROOT / "data" / "spike" / "central_park_paths"

PARKS_TRAILS_KEY = "nyc_parks_trails"
PARK_POLYGONS_KEY = "nyc_park_polygons"

SOCRATA_DOMAIN = "data.cityofnewyork.us"

#: NYC's street centerline (CSCL). Not registered, and the candidate answer to
#: where the missing path is.
CENTERLINE_DATASET = "inkn-q76z"

#: NYC's planimetric sidewalk layer - POLYGONS of paved walkway surface, which
#: is why it can only bound the answer rather than supply it.
SIDEWALK_DATASET = "52n9-sdep"

#: WHAT `rw_type` MEANS IS READ FROM THE ROWS, NOT FROM A DICTIONARY, and that
#: is the weakest link in this measurement. @unvalidated. The portal publishes
#: no description for the column (api/views/inkn-q76z.json, read 2026-09-16,
#: returns an empty `description` for it) and NYC Planning's CSCL metadata PDF
#: answers 403 from this sandbox, so the class below is inferred from the 5,990
#: values themselves: 3,041 of their names end in PATH, 1,023 GREENWAY, 250
#: LINK, 197 TRL, 129 WALK, 71 ESPL, 61 TRAIL. That is a pedestrian-path class
#: on the evidence available. Reading the published data dictionary is what
#: would settle it, and #1533 makes that reading a precondition of the
#: registration it decides.
PATH_RW_TYPE = "6"

#: The class the park drives fall in, measured for #1533's decision 2 rather
#: than proposed. East Dr and West Dr are car-free and are the most
#: walked route in Central Park; the 65/79/86/97 St transverses are in the
#: SAME class and carry through traffic in a cut. One value, two opposite
#: answers - which is why this is printed and not filtered on.
STREET_RW_TYPE = "1"

#: A SoQL box around the parks studied, so the two citywide layers are never
#: fetched whole. Manhattan and western Brooklyn, W S E N.
STUDY_BOX = (-74.010, 40.640, -73.940, 40.805)

#: The parks measured, by the `signname` NYC Parks' boundary layer uses, and
#: the `park_name` its trail layer uses for the same ground. Central Park is
#: the subject; Prospect Park is the control, and it is the right control
#: because it comes out of the SAME layer surveyed by the SAME steward - so a
#: difference between them cannot be explained by either.
PARKS = (
    ("Central Park", "Central Park"),
    ("Prospect Park", "Prospect Park"),
)

#: UTM 18N covers all five boroughs, and metres in it are close enough to true
#: ground distance over one park that the projection contributes nothing to
#: the finding. Distances below are metres in this projection.
WGS84_TO_UTM18 = Transformer.from_crs("EPSG:4326", "EPSG:32618", always_xy=True).transform

METRES_PER_MILE = 1609.344
SQ_METRES_PER_ACRE = 4046.8564224

#: How far a centerline path has to be from a registered trail line before it
#: counts as path we do not already draw. @unvalidated, and deliberately the
#: GENEROUS direction: at 25 m two independent digitisations of one tread are
#: still the same tread, so this under-states the new mileage rather than
#: inflating it. spike_nyc_overlap.py picked the same number for the same
#: reason and that is where the reasoning is written out.
DISJOINT_RADIUS_M = 25.0

#: The width band the walkway AREA is divided by to bound a centerline length.
#: THE OUTPUT OF THAT DIVISION IS NOT A MEASUREMENT AND MUST NEVER BE QUOTED AS
#: ONE - it is an area, and the band is picked rather than surveyed
#: (@unvalidated). What it is good for is an order of magnitude that does not
#: depend on anybody's published mileage: 3 m is about a two-abreast park walk,
#: 5 m a main promenade, and Central Park's walkways are a mix of both. What
#: would settle it is measuring a sample of these polygons' short axes, which
#: nobody has done.
WALKWAY_WIDTH_BAND_M = (3.0, 5.0)


def miles(metres: float) -> float:
    return metres / METRES_PER_MILE


def acres(square_metres: float) -> float:
    return square_metres / SQ_METRES_PER_ACRE


def clip(geometries: list, boundary) -> list:
    """Every part of `geometries` that falls inside `boundary`, dropping the
    ones that fall entirely outside.

    Takes geometries ALREADY IN METRES - see WGS84_TO_UTM18. Keeping the
    projection out of the arithmetic is what lets the tests build a park out
    of a 1 km box and check the answers by hand.
    """
    kept = []
    for geometry in geometries:
        piece = geometry.intersection(boundary)
        if not piece.is_empty:
            kept.append(piece)
    return kept


def total_length(geometries: list) -> float:
    return sum(geometry.length for geometry in geometries)


def length_beyond(geometries: list, reference: list, radius_m: float) -> float:
    """Length of `geometries` lying further than `radius_m` from `reference`.

    The question this answers is "is this path we do not already draw, or the
    same tread digitised twice", and it is answered by SUBTRACTING a buffered
    union rather than by a nearest-neighbour test, so a line that runs
    alongside a reference for half its length contributes only its other half.
    An empty `reference` returns the whole length, which is the right answer
    and not an edge case: it means nothing is drawn there at all.
    """
    if not reference:
        return total_length(geometries)
    covered = unary_union([geometry.buffer(radius_m) for geometry in reference])
    return sum(geometry.difference(covered).length for geometry in geometries)


def implied_centerline_miles(area_m2: float, width_band_m: tuple[float, float]) -> tuple[float, float]:
    """The centerline length a paved AREA implies, as a (low, high) band.

    Read WALKWAY_WIDTH_BAND_M before using this for anything. A wider assumed
    walkway implies less centerline, so the band's WIDE end gives the LOW
    mileage - the tuple is returned smallest-first regardless of which way the
    band was written, because a reader comparing it against a published figure
    should not have to work that out.
    """
    lengths = sorted(miles(area_m2 / width) for width in width_band_m)
    return lengths[0], lengths[-1]


def to_metres(features: list[dict]) -> list:
    """Fetched GeoJSON features as shapely geometries in UTM 18N metres.

    A feature with no geometry, or one whose geometry object carries no
    coordinates, is skipped rather than raising - nine rows of the greenway
    layer are exactly that shape (sources.json's `nyc_dot_greenways` notes
    carries the count) and a spike that fell over on them would be measuring
    its own fragility.
    """
    geometries = []
    for feature in features:
        raw = feature.get("geometry")
        if not raw or not raw.get("coordinates"):
            continue
        geometry = transform(WGS84_TO_UTM18, shape(raw))
        if not geometry.is_empty:
            geometries.append(geometry)
    return geometries


def _registered(key: str) -> list[dict]:
    path = RAW_DIR / f"{key}.geojson"
    if not path.exists():
        raise SystemExit(
            f"{path} is missing. Run:\n"
            f"  python fetch_external_layers.py --only {PARKS_TRAILS_KEY} {PARK_POLYGONS_KEY}\n"
            "This spike measures the files the exporter reads, so it does not fetch these itself."
        )
    return json.loads(path.read_text())["features"]


def _cached(name: str, dataset_id: str, where: str, refetch: bool = False) -> list[dict]:
    """One unregistered layer, fetched through lib/socrata.py and cached.

    `where` filters AT THE PORTAL, so the citywide layers are never pulled
    whole - the same reason sources.json puts `nyc_dot_greenways`' filter in
    the registry rather than in the exporter.
    """
    path = CACHE_DIR / f"{name}.geojson"
    if path.exists() and not refetch:
        return json.loads(path.read_text())["features"]
    print(f"  fetching {name} ({dataset_id})...")
    collection = fetch_dataset_geojson(SOCRATA_DOMAIN, dataset_id, where=where)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collection))
    return collection["features"]


def _box_clause(column: str = "the_geom") -> str:
    west, south, east, north = STUDY_BOX
    return f"within_box({column}, {north}, {west}, {south}, {east})"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refetch", action="store_true", help="re-pull the two unregistered layers instead of reading the cache")
    args = parser.parse_args()

    trails = _registered(PARKS_TRAILS_KEY)
    boundaries = _registered(PARK_POLYGONS_KEY)
    print(f"{PARKS_TRAILS_KEY}: {len(trails):,} segments")

    box = _box_clause()
    centerline_paths = _cached("cscl_paths", CENTERLINE_DATASET, f"{box} AND rw_type='{PATH_RW_TYPE}'", args.refetch)
    centerline_streets = _cached("cscl_streets", CENTERLINE_DATASET, f"{box} AND rw_type='{STREET_RW_TYPE}'", args.refetch)
    walkways = _cached("planimetric_sidewalk", SIDEWALK_DATASET, box, args.refetch)
    print(
        f"CSCL {CENTERLINE_DATASET}: {len(centerline_paths):,} rw_type={PATH_RW_TYPE} rows, "
        f"{len(centerline_streets):,} rw_type={STREET_RW_TYPE} rows in the study box"
    )
    print(f"planimetric sidewalk {SIDEWALK_DATASET}: {len(walkways):,} polygons in the study box\n")

    paths_m = to_metres(centerline_paths)
    streets_m = to_metres(centerline_streets)
    walkways_m = to_metres(walkways)

    for sign_name, park_name in PARKS:
        named = [f for f in boundaries if (f.get("properties") or {}).get("signname") == sign_name]
        boundary = unary_union(to_metres(named))
        if boundary.is_empty:
            print(f"{sign_name}: no boundary polygon under signname={sign_name!r}, skipped\n")
            continue

        shipped = clip(to_metres([f for f in trails if (f.get("properties") or {}).get("park_name") == park_name]), boundary)
        shipped_mi = miles(total_length(shipped))
        park_acres = acres(boundary.area)

        print(f"--- {sign_name}, {park_acres:,.0f} acres ---")
        print(
            f"  {PARKS_TRAILS_KEY}, what OurHike draws : {len(shipped):4,} features  {shipped_mi:6.2f} mi"
            f"   {shipped_mi / park_acres:.4f} mi/acre"
        )

        inside_paths = clip(paths_m, boundary)
        inside_paths_mi = miles(total_length(inside_paths))
        print(f"  CSCL rw_type={PATH_RW_TYPE}, Path/Trail           : {len(inside_paths):4,} features  {inside_paths_mi:6.2f} mi")
        if inside_paths_mi:
            beyond_mi = miles(length_beyond(inside_paths, shipped, DISJOINT_RADIUS_M))
            print(
                f"     further than {DISJOINT_RADIUS_M:.0f} m from a drawn line : {beyond_mi:6.2f} mi "
                f"({beyond_mi / inside_paths_mi * 100:.0f}%) - path we do not have, not a second copy of one"
            )

        inside_streets = clip(streets_m, boundary)
        print(
            f"  CSCL rw_type={STREET_RW_TYPE}, Street               : {len(inside_streets):4,} features  "
            f"{miles(total_length(inside_streets)):6.2f} mi   the drives AND the transverses - see STREET_RW_TYPE"
        )

        inside_walkways = clip(walkways_m, boundary)
        walkway_area = sum(piece.area for piece in inside_walkways)
        low, high = implied_centerline_miles(walkway_area, WALKWAY_WIDTH_BAND_M)
        print(
            f"  paved walkway polygons               : {len(inside_walkways):4,} polygons "
            f"{acres(walkway_area):6.1f} acres of surface"
        )
        print(
            f"     at an assumed {WALKWAY_WIDTH_BAND_M[0]:.0f}-{WALKWAY_WIDTH_BAND_M[1]:.0f} m width         : "
            f"{low:5.0f}-{high:.0f} mi of centerline - an AREA divided by a picked number, "
            "NOT a measured mileage. See WALKWAY_WIDTH_BAND_M."
        )
        if low:
            print(
                f"  SO: OurHike draws {shipped_mi / high * 100:.0f}-{shipped_mi / low * 100:.0f}% of this park's "
                f"paved walkway, and {shipped_mi / (shipped_mi + inside_paths_mi) * 100:.0f}% of what the city's "
                "two line layers hold between them.\n"
            )


if __name__ == "__main__":
    main()
