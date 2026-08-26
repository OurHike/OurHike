"""Fetch OSM's water point sources across the fourteen A.T. states - the
option WATER_SOURCES.md §7 ranks first for #529: the census measured OSM
point sources within 250 m of 26% of the 280 shelters trail-wide and 40% in
the south, against 8% for the supply the app ships today.

Reads the same Geofabrik state extracts export_basemap.py already fetches,
from the same directory, so a machine that has built the basemap pays
nothing here. The census (spike_osm_water_census.py) proved this shape after
every remote Overpass route failed from CI-like machines - #529's comments
hold that account.

Point sources only, the census's exact clause set: `natural=spring`,
`amenity=drinking_water`, `man_made=water_tap`, `man_made=water_well`. A
node with one of those tags is a claim a hiker can verify at the spot -
somebody stood there and mapped a spring. What is deliberately NOT fetched
is `natural=water`: a pond polygon within 250 m of a shelter is true in New
England 73 times over (the census's composition finding), but a water pin
over a pond a hiker must filter, reach down a bank to, or find frozen is a
different promise than a pin over a spring, and WATER_SOURCES.md's honesty
section keeps polygon-water out until somebody designs what it may claim.

The reliability tags travel with each point (`seasonal`, `intermittent`,
`drinking_water`), because they are the only honesty OSM offers: the census
found `seasonal` on zero features trail-wide and `intermittent` on a
handful, so their absence is the normal state and nothing here may read
absence as "flows year-round". export_poi.py composes what a card may
actually say from them.

Fetching is skip-if-present rather than conditional-request change-aware,
exactly as export_basemap.py's docstring reasons: Geofabrik republishes
state extracts daily, so "has it changed" is always "yes" and an ETag check
buys nothing. --refetch forces current extracts; CI runners start empty
anyway. Since #1065 skip-if-present covers the OUTPUT too: a scan already
on disk whose fetch receipt verifies is reused rather than re-derived,
because the run most likely to hold one is the retry of a failed publish,
and re-paying the 3.5 GB of extracts to recompute a held file is what lost
run 33005545820. --refetch forces that too.
That is also why this source has no check_freshness.py entry - a
source whose upstream moves daily by definition would report "changed" at
every check, which is noise, not freshness. What guards the output instead
is the drop-ratio gate below, the same shape fetch_opentrail.py uses.

Licence: OSM data is ODbL - attribution plus share-alike, the terms the
self-built basemap already complies with, and the client's credits line
already names OpenStreetMap (client/src/lib/credits.ts). sources.json's
`osm_water` entry records this; nothing here rides the atc_licence block.
"""

import argparse
import json
import sys
from pathlib import Path

import duckdb

from export_basemap import AT_STATES, OSM_RAW_DIR, fetch_states
from lib import fetch_receipts

OUT_PATH = Path(__file__).parent / "data" / "raw" / "osm_water.geojson"

# The four point-source classes, keyed by (tag, value) exactly as the census
# queried them. The dict IS the clause set: the SQL filter below and the
# per-feature `kind` are both derived from it, so a class added here is added
# everywhere at once.
POINT_SOURCE_TAGS = {
    ("natural", "spring"): "spring",
    ("amenity", "drinking_water"): "drinking_water",
    ("man_made", "water_tap"): "water_tap",
    ("man_made", "water_well"): "water_well",
}

# The reliability tags that ride along verbatim - the census measured them
# nearly absent (seasonal: 0 features trail-wide), and absent must never be
# read as a claim. Plus `name`, which a minority of springs carry.
CARRIED_TAGS = ("name", "seasonal", "intermittent", "drinking_water")

# A well-formed-but-shrunken result must not overwrite good data - the same
# guard and threshold as fetch_opentrail.py, for the same reason: normal OSM
# editing between runs never deletes half the water points in fourteen
# states, so a drop past this line is a broken scan (a truncated extract, a
# schema surprise in st_readosm), not the community at work.
MAX_FEATURE_DROP_RATIO = 0.5

# And a floor for the first run, when there is nothing to compare against:
# the first full scan found 7,574 point-source nodes across the fourteen
# states (2026-08-13), so a scan finding fewer than this has not read the
# extracts it thinks it read. Far under half the measured figure on purpose -
# this floor is for catching a broken scan, and the drop guard above is what
# watches ordinary shrinkage.
MIN_FEATURES = 500


def water_node_query(pbf_path: Path) -> str:
    """The one SQL statement that pulls water point nodes from one state
    extract. The WHERE clause is derived from POINT_SOURCE_TAGS rather than
    spelled beside it, so the dict really is the clause set - and the filter
    must run in SQL, not Python, because a state extract holds millions of
    tagged nodes (every tree is `natural=tree`) and only the water ones may
    cross into a Python list. classify_tags() re-derives the class from the
    returned values, pure and tested, and scan_states asserts the two agree
    by dropping any row it cannot classify."""
    conditions = " OR ".join(f"tags['{tag}'] = '{value}'" for (tag, value) in POINT_SOURCE_TAGS)
    return f"""
        SELECT
            id,
            lat,
            lon,
            tags['natural'] AS natural_tag,
            tags['amenity'] AS amenity_tag,
            tags['man_made'] AS man_made_tag,
            tags['name'] AS name,
            tags['seasonal'] AS seasonal,
            tags['intermittent'] AS intermittent,
            tags['drinking_water'] AS drinking_water
        FROM st_readosm('{pbf_path.as_posix()}')
        WHERE kind = 'node'
          AND tags IS NOT NULL
          AND ({conditions})
    """


def classify_tags(natural: str | None, amenity: str | None, man_made: str | None) -> str | None:
    """Which point-source class a node's tag values put it in, or None.

    First match wins in POINT_SOURCE_TAGS order; in practice the classes are
    disjoint (a spring is not also a tap), and a node perverse enough to be
    both is one point source either way.
    """
    values = {"natural": natural, "amenity": amenity, "man_made": man_made}
    for (tag, value), kind in POINT_SOURCE_TAGS.items():
        if values[tag] == value:
            return kind
    return None


def feature(row: dict) -> dict:
    """One GeoJSON Feature from one classified node row.

    `osm_id` is the node's OSM id as a string - the stable identity
    export_poi.py builds the unified id from, string because unify_poi
    stringifies every source_feature_id and a numeric id that round-trips
    through JSON as a float would corrupt it first.
    """
    properties = {"osm_id": str(row["id"]), "kind": row["kind"]}
    for tag in CARRIED_TAGS:
        if row.get(tag) is not None:
            properties[tag] = row[tag]
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        "properties": properties,
    }


def scan_states(paths: list[Path]) -> list[dict]:
    """Every classified water node across the given extracts, deduplicated
    by OSM node id - states overlap at their borders (the trail rides the
    NC/TN line for ~200 miles), and Geofabrik's extract shapes carry a
    margin, so the same node arrives from both sides."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows_by_id: dict[int, dict] = {}
    for path in paths:
        columns = ("id", "lat", "lon", "natural_tag", "amenity_tag", "man_made_tag", *CARRIED_TAGS)
        state_rows = 0
        for values in con.execute(water_node_query(path)).fetchall():
            row = dict(zip(columns, values))
            kind = classify_tags(row["natural_tag"], row["amenity_tag"], row["man_made_tag"])
            if kind is None or row["lat"] is None or row["lon"] is None:
                continue
            row["kind"] = kind
            state_rows += 1
            rows_by_id[row["id"]] = row
        print(f"  {path.name}: {state_rows} water point nodes")
    return [rows_by_id[node_id] for node_id in sorted(rows_by_id)]


def existing_feature_count(path: Path) -> int | None:
    if not path.exists():
        return None
    return len(json.loads(path.read_text(encoding="utf-8")).get("features", []))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refetch", action="store_true", help="re-download extracts even when present")
    parser.add_argument(
        "--states",
        nargs="+",
        default=AT_STATES,
        help="Geofabrik state names (default: the 14 AT states)",
    )
    args = parser.parse_args(argv)

    # An output already on disk, standing behind a verifying receipt, is not
    # re-derived (#1065). Run 33005545820 attempt 2 measured why: the scan
    # output rode the Actions cache back onto the runner, and this script
    # re-downloaded the 3.5 GB of extracts anyway - solely to recompute a
    # file it held - and the production publish died with the download.
    #
    # The receipt is the condition, not a nicety. A copy the workflow
    # restored from the published bucket carries no receipt, and reusing it
    # here would leave check_output_quality's `--fetched fetch_osm_water`
    # failing on the absence - rightly, since no finished fetch stands
    # behind that copy. So a receiptless or drifted copy still gets a real
    # fetch, and the skip path records NO new receipt: writing one would
    # claim a fetch that never happened, and the standing receipt already
    # describes the file, age and all.
    if not args.refetch and OUT_PATH.exists():
        receipt = fetch_receipts.load("fetch_osm_water")
        if receipt is not None and not fetch_receipts.verify(receipt):
            days = fetch_receipts.age_days(receipt)
            age = "of unknown age" if days is None else f"{days:.1f} days old"
            print(
                f"{OUT_PATH.name} is already on disk ({existing_feature_count(OUT_PATH)} features, "
                f"{age}) and its receipt verifies - skipping the ~3.5 GB extract fetch. "
                "--refetch forces a fresh scan."
            )
            return 0

    print(f"Fetching {len(args.states)} state extracts into {OSM_RAW_DIR} ...")
    paths = fetch_states(args.states, OSM_RAW_DIR, refetch=args.refetch)

    print("Scanning for water point sources ...")
    rows = scan_states(paths)
    print(f"  {len(rows)} distinct water point nodes across {len(args.states)} states.")

    if len(rows) < MIN_FEATURES:
        print(f"Refusing to write: {len(rows)} features is below the floor of {MIN_FEATURES} - see MIN_FEATURES.")
        return 1
    previous = existing_feature_count(OUT_PATH)
    if previous and len(rows) < previous * MAX_FEATURE_DROP_RATIO:
        print(
            f"Refusing to overwrite {OUT_PATH.name}: {len(rows)} features against "
            f"{previous} on disk is past the {MAX_FEATURE_DROP_RATIO:.0%} drop guard."
        )
        return 1

    collection = {"type": "FeatureCollection", "features": [feature(row) for row in rows]}
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(collection), encoding="utf-8")
    tmp.replace(OUT_PATH)
    print(f"Wrote {len(rows)} features -> {OUT_PATH}")

    fetch_receipts.record("fetch_osm_water", [OUT_PATH])
    return 0


if __name__ == "__main__":
    sys.exit(main())
