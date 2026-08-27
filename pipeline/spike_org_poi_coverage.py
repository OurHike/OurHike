"""Probe every org whose trails the map draws for the eight POI types we publish (#1092).

The maintainer's ask, 2026-08-27: *"We don't have POI for the org's outside of
ATC. Search those sources for the POI types we have. For example, DEC has
Shelters & Campsites mapped. Maybe we need to track each of the POI types for
the org, and whether or not it is provided."*

This is the measuring half of that ask. `POI_COVERAGE_SURVEY.md` is the prose,
and `sources.json`'s `poi_coverage` block is the answer in a form a test can
read - **every number in both of them comes from this script**, so a reader who
doubts one can re-run it rather than re-deriving it by hand:

    cd pipeline && python spike_org_poi_coverage.py

WHAT IT DOES, and the one thing that makes it more than a row count. Each org
publishes its POIs as one big point layer typed by a free-text column - DEC's
`ASSET` (234 distinct values across 21,468 points), OPRHP's `Sub_Asset` (158
across 8,823) - rather than as a layer per category. So "does DEC have
shelters" is not a question about which layers exist; it is a question about
which values that column takes. This script pages the type column whole and
buckets its values into `lib/poi_schema.POI_TYPES`, which is the only way to
get a per-type count that is not a guess.

The buckets below are OURS, not the orgs'. Nobody at DEC decided that
`PRIMITIVE TENT SITE` is the same category as ATC's `campsite`; this file did,
and the mapping is written out value by value so the next reader can disagree
with a specific line rather than with a total. Values NOT in a bucket are
counted as unmapped and reported, so a category we invented a meaning for and a
category we ignored look different from each other.

TWO FIELDS DECIDE WHETHER A COUNT MEANS ANYTHING, and they are the reason this
prints two numbers per cell rather than one:

  - **DEC's `PUBLICUSE`** splits the layer 13,823 N / 7,645 Y (measured
    2026-08-27). It is a real filter: DEC's own layer description calls this
    "assets on state lands... man-made items, which require periodic
    maintenance or inspection", and 4,290 of the rows are culverts. The `Y`
    slice is DEC's own answer to "what would you show a visitor".
  - **OPRHP's `Public`** looks like the same field and is not: it reads `Y` on
    all 8,823 rows, so it filters nothing. `ParksApp` is the field that
    discriminates there (5,822 Y / 3,000 N), and it is uneven in ways worth
    seeing - 0 of 37 lean-tos are in it, and 15 of 151 drinking-water points.

So the "public" column below is per-org: DEC's `PUBLICUSE`, OPRHP's `ParksApp`.
Naming it generically would flatten exactly the difference that matters.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO: decide anything. It does not clip to
a corridor, dedupe against ATC's POIs, judge whether a `SPRING` is drinkable, or
write anything into `data/processed/`. Those are the ingest questions and they
belong to per-org issues with their own review - CLAUDE.md's "four ways this app
can hurt somebody" sets the evidence bar for the water rows in particular, and a
point dump would not clear it. Findings belong in POI_COVERAGE_SURVEY.md.

Everything fetched is cached under OUT_DIR, so a re-run only re-reports. Pass
--refetch to go back to the network.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

from lib.http_retry import request_with_retry
from lib.poi_schema import POI_TYPES

OUT_DIR = Path(os.environ.get("OUT_DIR", "data/spike"))

# How many features to ask for per page. ArcGIS caps this server-side
# (maxRecordCount); asking for more than the cap is not an error, it just
# returns the cap, which is why the paging loop trusts the response length
# rather than this number.
PAGE_SIZE = 2000

# ---------------------------------------------------------------------------
# The buckets. One regex per poi_type per org, matched against the whole type
# value (case-insensitively, after stripping - both layers carry trailing-space
# dirt: DEC has 'FORD ' beside 'FORD', 'WATER HOLE ' beside 'WATER HOLE').
#
# Three rules held while writing these, and each one is a decision a reviewer
# can reject:
#
# 1. **`PROPOSED *` is not a feature.** DEC's ASSET column carries 'PROPOSED
#    LEAN-TO' (11), 'PROPOSED PIT PRIVY' (5), 'PROPOSED CAMPSITE' (5) and a
#    dozen more. A hiker who walks to a proposed lean-to finds trees. They are
#    excluded from every bucket and counted separately, because a shelter that
#    does not exist yet is the exact shape of "a confidently wrong prediction is
#    more dangerous than an honest unknown" (FEATURES.md).
# 2. **A bridge is a crossing; a culvert is not.** DEC's 4,290 culverts and
#    1,088 bridges are both drainage assets to DEC. The bridge is a thing a
#    hiker walks across and the culvert is a pipe under the road, so only the
#    first is `crossing`.
# 3. **Nothing goes in `water` on the strength of its name.** See WATER_LOOKALIKES
#    below - this is the bucket the survey argues about at length rather than
#    the one it fills.
ORGS: dict[str, dict] = {
    "NYS DEC": {
        "layer": "https://gisservices.dec.ny.gov/arcgis/rest/services/dec_backcountry_features/MapServer/0",
        "label": "Back Country Features",
        "type_field": "ASSET",
        "public_field": "PUBLICUSE",
        "public_yes": "Y",
        "buckets": {
            "shelter": r"^(LEAN-TO|SHELTER)$",
            "campsite": r"^(PRIMITIVE TENT SITE|PRIMITIVE CAMPSITE|PRIMATIVE CAMPSITE|CAMPSITE)$",
            # 'WATER SUPPLY SYSTEM' is the only DEC value whose sampled rows
            # are plumbed drinking water ('Water Spigot' x8 of the 14 sampled)
            # - and one of those same 14 reads "Not Approved For Human
            # Consum[ption]". It is bucketed so the count is visible, NOT
            # because it is publishable. WATERHOLE/WELL/SPRING/CISTERN are
            # excluded outright; the evidence is in WATER_LOOKALIKES.
            "water": r"^WATER SUPPLY SYSTEM$",
            "privy": r"^(PIT PRIVY|PORT-A-JOHN|RESTROOM|BATHROOM)$",
            "viewpoint": r"^(SCENIC VISTA|OBSERVATION PLATFORM|OBSERVATION TOWER|FIRE TOWER)$",
            "parking": r"^(UNPAVED PARKING LOT|PAVED PARKING LOT|DESIGNATED HUNTER PARKING AREA"
            r"|UNPAVED PARKING|ACCESSIBLE PARKING SPOT|PULL[- ]?OFF|ROAD PULLOFF)$",
            "crossing": r"^(BRIDGE|FOOT ?BRIDGE|BOARDWALK|FORD|HARDENED CROSSING|CABLE CROSSING)$",
            # DEC publishes no store, outfitter or hostel layer at all - see
            # the survey. An empty pattern is how this file says "probed, and
            # the answer is none", which is a different statement from a
            # poi_type being absent from this dict.
            "resupply": None,
        },
    },
    "NYS OPRHP": {
        "layer": "https://services.arcgis.com/1xFZPtKn1wKC6POA/arcgis/rest/services/NY_State_Park_Facilities/FeatureServer/0",
        "label": "NY State Park Facilities",
        "type_field": "Sub_Asset",
        # NOT `Public_`, which reads Y on all 8,823 rows and therefore says
        # nothing. See the module docstring.
        "public_field": "ParksApp",
        "public_yes": "Y",
        "buckets": {
            "shelter": r"^Lean-to$",
            # OPRHP's are drive-in campgrounds and group camps, not backcountry
            # sites, and one row is one CAMPGROUND rather than one site. The
            # count is of facilities; treating it as a tent-site count would
            # overstate it by orders of magnitude.
            "campsite": r"^(Campground|Group Camp)$",
            # The one org with unambiguous drinking water: 'Water Spigot' and
            # 'Drinking Fountain' are plumbed fixtures and are named as such.
            # 'Mineral Spring' (17), 'Water Tower' (12) and 'Waterfall' (55)
            # are excluded - they are none of them a place to fill a bottle.
            "water": r"^(Water Spigot|Drinking Fountain)$",
            "privy": r"^(Public Restroom|Pit Toilet|Portable Toilet)$",
            "viewpoint": r"^(Scenic View|Fire Tower|Wildlife Viewpoint)$",
            "parking": r"^(Parking Area|Accessible Parking Area|Pull Off)$",
            "crossing": r"^(Trail Bridge|Vehicle Bridge|Stairs)$",
            # 'Concession' (91) and 'Store' (18). Whether a park concession
            # stand is 'resupply' in the sense a thru-hiker means is exactly
            # the kind of thing #806 got wrong about opentrail's 'r' tag, so
            # the count is reported and the judgement is left to the survey.
            "resupply": r"^(Concession|Store)$",
        },
    },
}

# The DEC values that sound like drinking water and are not, kept as data
# rather than prose because the survey quotes them and a reader will want to
# re-run the sampling. Counts measured 2026-08-27 by this script.
#
# Sampling 14 rows of each (NAME/DESCRIP/NOTES) found: WATERHOLE is fire-and-
# wildlife impoundments ("Wetland Pool", "Made by Tioga County SWCD in 2016");
# WELL is dominated by NATURAL GAS WELLS and historic stacked-stone wells;
# CISTERN is CCC-era fire cisterns; SPRING includes "Unnoffical Unsanctioned
# Traditional Public Wa[ter]" and one "Untested". Every row of all four reads
# PUBLICUSE 'N' - DEC's own flag says none of it is for visitors.
WATER_LOOKALIKES = ("WATERHOLE", "WATER HOLE", "WELL", "STONE WELL", "SPRING", "CISTERN", "WATERFALL", "POND")

PROPOSED = re.compile(r"^PROPOSED\b", re.IGNORECASE)


def fetch_column(layer_url: str, fields: list[str], cache: Path, refetch: bool) -> list[dict]:
    """Page one layer's attribute columns whole, caching the result.

    Attributes only - `returnGeometry=false` - because every question here is
    "how many of these are there", and DEC's 21,468-point layer is a great deal
    slower to move with its geometry attached.
    """
    if cache.exists() and not refetch:
        return json.loads(cache.read_text())
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": ",".join(fields),
            "returnGeometry": "false",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        payload = request_with_retry(layer_url.rstrip("/") + "/query", params=params, timeout=90).json()
        if "error" in payload:
            raise RuntimeError(f"{layer_url} -> {payload['error']}")
        batch = payload.get("features", [])
        if not batch:
            break
        rows.extend(f["attributes"] for f in batch)
        offset += len(batch)
        # An on-prem MapServer answers a short page without setting
        # exceededTransferLimit; a hosted FeatureServer sets it. Trusting
        # either alone under-reads one of the two.
        if len(batch) < PAGE_SIZE and not payload.get("exceededTransferLimit"):
            break
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(rows))
    return rows


def tally(rows: list[dict], spec: dict) -> dict:
    """Bucket one org's rows into poi_types, splitting each by the org's public flag."""
    type_field, public_field, public_yes = spec["type_field"], spec["public_field"], spec["public_yes"]
    result = {t: {"total": 0, "public": 0, "values": collections.Counter()} for t in POI_TYPES}
    unmapped: collections.Counter = collections.Counter()
    proposed: collections.Counter = collections.Counter()
    for row in rows:
        value = (row.get(type_field) or "").strip()
        if not value:
            continue
        if PROPOSED.match(value):
            proposed[value] += 1
            continue
        is_public = (row.get(public_field) or "").strip().upper() == public_yes.upper()
        for poi_type, pattern in spec["buckets"].items():
            if pattern and re.match(pattern, value, re.IGNORECASE):
                result[poi_type]["total"] += 1
                result[poi_type]["public"] += int(is_public)
                result[poi_type]["values"][value] += 1
                break
        else:
            unmapped[value] += 1
    return {"types": result, "unmapped": unmapped, "proposed": proposed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refetch", action="store_true", help="ignore the cache under OUT_DIR and re-read every layer")
    args = parser.parse_args()

    summary: dict[str, dict] = {}
    for org, spec in ORGS.items():
        fields = [spec["type_field"], spec["public_field"]]
        cache = OUT_DIR / f"poi_coverage_{org.lower().replace(' ', '_')}.json"
        print(f"\n{'=' * 78}\n{org} - {spec['label']}\n{spec['layer']}")
        rows = fetch_column(spec["layer"], fields, cache, args.refetch)
        counted = tally(rows, spec)
        print(
            f"  {len(rows):,} features, {spec['type_field']} takes {len({(r.get(spec['type_field']) or '').strip() for r in rows})} distinct values"
        )
        print(
            f"  {spec['public_field']} splits them "
            f"{sum(1 for r in rows if (r.get(spec['public_field']) or '').strip().upper() == spec['public_yes'])}"
            f" public / {len(rows)} total\n"
        )
        print(f"  {'poi_type':<10} {'total':>7} {'public':>7}   values")
        org_summary = {}
        for poi_type in POI_TYPES:
            cell = counted["types"][poi_type]
            declared = spec["buckets"].get(poi_type, "absent-from-spec")
            if declared is None:
                print(f"  {poi_type:<10} {'—':>7} {'—':>7}   org publishes no layer of this kind")
                org_summary[poi_type] = {"total": 0, "public": 0, "values": {}}
                continue
            shown = ", ".join(f"{v} x{n}" for v, n in cell["values"].most_common(4))
            print(f"  {poi_type:<10} {cell['total']:>7,} {cell['public']:>7,}   {shown}")
            org_summary[poi_type] = {"total": cell["total"], "public": cell["public"], "values": dict(cell["values"])}
        summary[org] = {"layer": spec["layer"], "features": len(rows), "types": org_summary}

        # The two honesty columns. Unmapped is how much of the layer this
        # script declined to categorise; proposed is how much of it does not
        # exist on the ground yet.
        unmapped_total = sum(counted["unmapped"].values())
        print(
            f"\n  unmapped: {unmapped_total:,} features across {len(counted['unmapped'])} values "
            f"({100 * unmapped_total / max(len(rows), 1):.0f}% of the layer)"
        )
        print(f"    biggest: {', '.join(f'{v} x{n}' for v, n in counted['unmapped'].most_common(6))}")
        proposed_total = sum(counted["proposed"].values())
        print(f"  PROPOSED (excluded from every bucket): {proposed_total} features across {len(counted['proposed'])} values")
        if counted["proposed"]:
            print(f"    {', '.join(f'{v} x{n}' for v, n in counted['proposed'].most_common(6))}")

        if org == "NYS DEC":
            print("\n  the water lookalikes, excluded from the water bucket on purpose:")
            for value in WATER_LOOKALIKES:
                matching = [r for r in rows if (r.get("ASSET") or "").strip().upper() == value]
                if not matching:
                    continue
                public = sum(1 for r in matching if (r.get("PUBLICUSE") or "").strip().upper() == "Y")
                print(f"    {value:<16} {len(matching):>4} features, {public} flagged PUBLICUSE=Y")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "poi_coverage_summary.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
