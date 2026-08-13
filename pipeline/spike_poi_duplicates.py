"""How much duplication is actually in the published POI set, and what a blind
radius rule would do to it (features/POI_DEDUPLICATION.md, #696).

Answers three questions the strategy doc could otherwise only assert:

  1. **How many same-type pairs sit within 25 m today?** The proposed rule is
     "no two POIs of the same type within 25 m". Every pair it would fire on
     today comes from ONE source - and a source does not publish a place
     twice, so every one of them is two real things. That is the measurement
     that decides the rule is cross-source rather than blind.
  2. **What would a blind rule delete?** Counted, and named, with the share
     whose two names differ - which is upstream saying, in its own words,
     that they are not the same place.
  3. **How far apart is the duplicate pair we ALREADY ship?** `resupply` is
     the one poi_type today with two sources (ATC's Communities layer and
     opentrail.org's "r" tag). If 25 m does not catch it, the radius is not
     the mechanism, and the doc has to say so.

WHY A SPIKE AND NOT A TEST

Nothing here ships. What survives is the numbers in the design doc and this
file as the way to re-derive them against fresher data - the same posture as
spike_poi_seam.py and spike_osm_water_census.py.

NETWORK, AND THE CACHE

Unlike spike_poi_seam.py this does NOT need fetch_all.py to have run: it
fetches the six ATC layers and opentrail.org itself into data/spike/
poi_duplicates/ and re-reads that cache on every later run. `--refetch`
forces a fresh pull. The cached files are named exactly as export_poi.py's
RAW_DIR expects them, because this measures the PUBLISHED set by pointing
that module's own RAW_DIR at the cache and calling its own unify_all_sources
- a second copy of the unification could measure a set the app does not ship.

WHAT IS NOT IN THE MEASUREMENT

  - **The corridor clip.** These are the raw layers, so 1,223 viewpoints
    where the corridor publishes 1,194. It cuts towards MORE duplication
    than the app ships, not less, which is the safe direction for a
    measurement whose conclusion is "there is very little".
  - **OSM water.** 7,574 nodes arriving on a branch (#529's work), which is
    the first real cross-source case and is measured there rather than here:
    41 of opentrail's 174 water points have an OSM twin within 25 m.
"""

import argparse
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import requests

import export_poi
from lib.arcgis import fetch_layer_to_file
from lib.poi_sites import base_name, normalise_name
from lib.spurs import distance_m

ROOT = Path(__file__).resolve().parent
CACHE_DIR = ROOT / "data" / "spike" / "poi_duplicates"

# sources.json keys -> the raw filename export_poi.py reads. Spelled out
# rather than read from sources.json because this spike wants exactly the six
# layers that become POIs, not the twelve that are registered.
ATC_LAYERS = {
    "shelters": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/4",
    "campsites": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/1",
    "viewpoints": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/5",
    "parking": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/2",
    "privies": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/3",
    "communities": "https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/AT_Communities/FeatureServer/0",
}

OPENTRAIL_URL = "https://opentrail.org/api/getData"

# The radii the doc reasons over. 25 m is the proposed rule; the others are
# what say whether it sits on a cliff or on a slope.
RADII = (10.0, 15.0, 25.0, 40.0, 60.0, 100.0)

PROPOSED_RADIUS_M = 25.0


def fetch(refetch: bool) -> None:
    """Populate the cache. Skip-if-present unless --refetch, so re-running the
    measurement costs nothing upstream - the same courtesy fetch_all.py's
    manifest extends to ATC."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for stem, url in ATC_LAYERS.items():
        path = CACHE_DIR / f"{stem}.geojson"
        if path.exists() and not refetch:
            continue
        count = fetch_layer_to_file(url, path)
        print(f"  fetched {stem}: {count} features")

    path = CACHE_DIR / "opentrail_at.geojson"
    if not path.exists() or refetch:
        resp = requests.get(OPENTRAIL_URL, params={"trail": "AT"}, timeout=60)
        resp.raise_for_status()
        collection = resp.json()
        for feature in collection["features"]:
            # Same consent position fetch_opentrail.py takes - user comments
            # are not ours to redistribute, and nothing here needs them.
            feature["properties"].pop("comments", None)
            feature["properties"].pop("commentCount", None)
        path.write_text(json.dumps(collection))
        print(f"  fetched opentrail: {len(collection['features'])} features")


def load_published_records() -> list[dict]:
    """The unified POI set, through export_poi.py's own code path.

    Pointing that module's RAW_DIR at the cache rather than reimplementing the
    unification is the whole reason this measures the app's set: the source
    names, the poi_type mapping and the confidences are the ones that ship.
    """
    export_poi.RAW_DIR = CACHE_DIR
    return export_poi.unify_all_sources(skipped=[])


def same_type_pairs(records: list[dict], radius_m: float) -> list[tuple[dict, dict, float]]:
    """Every unordered pair of same-`poi_type` records within radius_m.

    Bucketed by type first, which is what keeps this an O(n^2) over each
    type's few hundred points rather than over all 2,800.
    """
    by_type: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_type[record["poi_type"]].append(record)

    pairs = []
    for type_records in by_type.values():
        for left, right in combinations(type_records, 2):
            metres = distance_m(left["lat"], left["lon"], right["lat"], right["lon"])
            if metres <= radius_m:
                pairs.append((left, right, metres))
    return pairs


def report_radii(records: list[dict]) -> None:
    print("\n=== 1. Same-type pairs by radius, split by source ===\n")
    print(f"{'radius':>8} | {'pairs':>6} | {'within one source':>18} | {'cross-source':>13}")
    print("-" * 56)
    for radius in RADII:
        pairs = same_type_pairs(records, radius)
        within = sum(1 for left, right, _ in pairs if left["source"] == right["source"])
        print(f"{radius:>6.0f} m | {len(pairs):>6} | {within:>18} | {len(pairs) - within:>13}")

    print("\nBy poi_type at the proposed radius:\n")
    pairs = same_type_pairs(records, PROPOSED_RADIUS_M)
    by_type = Counter(left["poi_type"] for left, _, _ in pairs)
    for poi_type, count in sorted(by_type.items(), key=lambda item: -item[1]):
        print(f"  {poi_type:<10} {count}")
    if not by_type:
        print("  (none)")


def report_blind_rule(records: list[dict]) -> None:
    """What "no two of a type within 25 m" would actually delete, and how much
    of it upstream has already told us is two places."""
    print(f"\n=== 2. What a blind {PROPOSED_RADIUS_M:.0f} m same-type rule would merge ===\n")
    pairs = same_type_pairs(records, PROPOSED_RADIUS_M)
    if not pairs:
        print("  Nothing - no same-type pair on the trail is within the radius.")
        return

    distinct_names = 0
    for left, right, metres in sorted(pairs, key=lambda pair: pair[2]):
        left_name = normalise_name(left.get("name"))
        right_name = normalise_name(right.get("name"))
        distinct = left_name != right_name
        distinct_names += distinct
        shared_base = base_name(left.get("name")) == base_name(right.get("name"))
        print(f"  {metres:6.1f} m  {left['poi_type']:<9} {left.get('name')!r} + {right.get('name')!r}")
        print(
            f"           {'names differ' if distinct else 'names identical'}"
            f"{', same base name' if shared_base else ''}"
            f"{', same source' if left['source'] == right['source'] else ', CROSS-SOURCE'}"
        )

    print(f"\n  {len(pairs)} pair(s); {distinct_names} carry two different names.")
    print(f"  A blind rule deletes one side of each: {len(pairs)} POI(s) off the map.")


# Tokens ATC uses to distinguish two real things standing next to each other.
# Measured from the pairs this spike prints: (N)/(S), (East)/(West), Upper/
# Lower, and a trailing sibling digit. A pair separated by one of these is
# upstream saying, in its own words, that they are two places.
DIRECTION_WORDS = frozenset({"n", "s", "e", "w", "ne", "nw", "se", "sw", "north", "south", "east", "west", "upper", "lower"})


def name_relation(left: dict, right: dict) -> str:
    """What the two names say about whether this is one place or two.

    The classes are ordered by how strongly they argue for TWO, because the
    expensive mistake is merging two real places and the cheap one is leaving
    a duplicate on the map for a human to spot.
    """
    left_name, right_name = normalise_name(left.get("name")), normalise_name(right.get("name"))
    left_tokens, right_tokens = left_name.split(), right_name.split()

    if left_name == right_name:
        return "identical"

    # A trailing sibling digit: "Tumbling Run Shelter 1" / "... 2".
    if (
        left_tokens
        and right_tokens
        and left_tokens[-1].isdigit()
        and right_tokens[-1].isdigit()
        and left_tokens[:-1] == right_tokens[:-1]
    ):
        return "sibling number"

    # A direction token anywhere, differing: "The Horn (S)" / "The Horn (N)".
    left_directions = [token for token in left_tokens if token in DIRECTION_WORDS]
    right_directions = [token for token in right_tokens if token in DIRECTION_WORDS]
    if (left_directions or right_directions) and left_directions != right_directions:
        stripped_left = [token for token in left_tokens if token not in DIRECTION_WORDS]
        stripped_right = [token for token in right_tokens if token not in DIRECTION_WORDS]
        if stripped_left == stripped_right:
            return "direction"

    # One name is the other plus trailing words: "Bears Den Rocks" is inside
    # "Bears Den Rocks Vista".
    if left_tokens[: len(right_tokens)] == right_tokens or right_tokens[: len(left_tokens)] == left_tokens:
        return "one name contains the other"

    return "unrelated names"


def report_name_evidence(records: list[dict]) -> None:
    """The 25 m pairs, classified by what their names argue for.

    This is the measurement the rule turns on: distance says these pairs are
    indistinguishable, and the name separates them cleanly into two real
    things and one thing entered twice.
    """
    print(f"\n=== 4. The {PROPOSED_RADIUS_M:.0f} m pairs, by what the names say ===\n")
    pairs = same_type_pairs(records, PROPOSED_RADIUS_M)
    grouped: dict[str, list[tuple[dict, dict, float]]] = defaultdict(list)
    for left, right, metres in pairs:
        grouped[name_relation(left, right)].append((left, right, metres))

    order = ("sibling number", "direction", "unrelated names", "one name contains the other", "identical")
    for relation in order:
        entries = grouped.get(relation, [])
        verdict = "ONE PLACE, candidate" if relation in ("identical", "one name contains the other") else "two places"
        print(f"  {relation:<28} {len(entries):>3}   ({verdict})")

    candidates = grouped["identical"] + grouped["one name contains the other"]

    # Pairs are not places. Wayah Bald carries THREE records - "Wayah Bald
    # Summit", "... Lookout Tower" and "... Lookout Tower Vista" - which is
    # three pairs and one place, so a pair count overstates the load by the
    # size of every cluster past two. Single-link components over the
    # candidate pairs is what turns one into the other.
    parent: dict[str, str] = {}

    def find(poi_id: str) -> str:
        parent.setdefault(poi_id, poi_id)
        while parent[poi_id] != poi_id:
            parent[poi_id] = parent[parent[poi_id]]
            poi_id = parent[poi_id]
        return poi_id

    for left, right, _ in candidates:
        parent[find(left["id"])] = find(right["id"])

    clusters: dict[str, list[str]] = defaultdict(list)
    for poi_id in list(parent):
        clusters[find(poi_id)].append(poi_id)
    surplus = sum(len(members) - 1 for members in clusters.values())

    print(f"\n  Candidate duplicates: {len(candidates)} of {len(pairs)} pairs.")
    print(f"  Those pairs are {len(clusters)} place(s) holding {len(parent)} records: {surplus} surplus point(s).")
    print(f"  {surplus / len(records):.2%} of the {len(records)} published points.")
    for left, right, metres in sorted(candidates, key=lambda entry: entry[2]):
        print(f"    {metres:6.1f} m  {left['poi_type']:<9} {left['source']:<16} {left.get('name')!r} + {right.get('name')!r}")


def report_existing_cross_source(records: list[dict]) -> None:
    """`resupply` is the one poi_type today fed by two sources. If the radius
    does not reach it, the radius is not what finds a duplicate."""
    print("\n=== 3. The duplicate pair we already ship: resupply ===\n")
    communities = [r for r in records if r["source"] == "atc_communities"]
    opentrail = [r for r in records if r["source"] == export_poi.OPENTRAIL_SOURCE and r["poi_type"] == "resupply"]
    print(f"  {len(communities)} ATC Community towns, {len(opentrail)} opentrail resupply points.")
    if not communities or not opentrail:
        return

    nearest = []
    for point in opentrail:
        best = min(
            ((distance_m(point["lat"], point["lon"], town["lat"], town["lon"]), town) for town in communities),
            key=lambda entry: entry[0],
        )
        nearest.append((point, *best))

    for label, limit in (("25 m", 25.0), ("100 m", 100.0), ("250 m", 250.0), ("1 km", 1000.0), ("5 km", 5000.0)):
        count = sum(1 for _, metres, _ in nearest if metres <= limit)
        print(f"  within {label:>5}: {count:>3} of {len(opentrail)}")

    ordered = sorted(nearest, key=lambda entry: entry[1])
    median = ordered[len(ordered) // 2][1]
    print(f"  nearest-community distance: min {ordered[0][1]:.0f} m, median {median:.0f} m")
    print("\n  Closest five:")
    for point, metres, town in ordered[:5]:
        print(f"    {metres:8.0f} m  {point.get('name')!r} -> {town.get('name')!r}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refetch", action="store_true", help="re-pull upstream instead of reading the cache")
    args = parser.parse_args(argv)

    print(f"Cache: {CACHE_DIR}")
    fetch(args.refetch)

    records = load_published_records()
    print(f"\n{len(records)} POIs unified (pre-corridor-clip) across {len(set(r['source'] for r in records))} sources.")
    for source, count in sorted(Counter(r["source"] for r in records).items()):
        print(f"  {source:<20} {count}")

    report_radii(records)
    report_blind_rule(records)
    report_name_evidence(records)
    report_existing_cross_source(records)


if __name__ == "__main__":
    main()
