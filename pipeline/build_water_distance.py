"""Build reference/water_distance.json - how far the nearest water source is
from each A.T. shelter and campsite, keyed to ATC's own GlobalIDs.

**No facility layer carries water at all.** Checked field by field against the
live services (2026-08-13), the same way build_shelter_capacity.py checked for
capacity: the shelter layer's 135 fields and the campsite layer's 98 are an
FMSS asset inventory with not one water column between them, the `ATX_Ratings`
overnight-sites layer carries privy and food storage but no water (all five of
its overnight-site layer variants were probed; WATER_SOURCES.md §4 and the
dated correction in SOURCE_SURVEY.md §3a record the same finding), and the org
hosts no water layer under any name. Water POINTS come from opentrail.org
(#98), and only 9 of them fold into a shelter or campsite site over the whole
corridor - so at nearly every overnight site the card says nothing about the
one thing a hiker asks first after the privy. WATER_SOURCES.md is the full
option ranking for #529; this file is the CSI-distance slice of it, scoped by
the provenance rule below.

**What ATC does publish is a distance.** The `Campsite_Sustainability_Index`
layer on ATC's own ArcGIS org (SOURCE_SURVEY.md §3b) carries `Proximity_Water_ft`
on every one of its 1,013 official sites - 531 shelters and 482 club/agency
campsites, data-edited 2026-06-02 - together with `Nearest_Water_Source`, which
despite the name is the *provenance* of each measurement rather than a source
name: `FarOut` (641 rows - measured against the waypoints in ATC's official
app), `NHDP_HR_Stream`/`NHDP_HR_Pond` (185 - the USGS National Hydrography
Dataset), or `OSA_Field_Estimate` (187 - a steward's estimate, typically a
round 250 or 300). The provenance travels onto every record below, verbatim,
so nobody has to rediscover what each number is worth.

**Only the official sites are ever requested.** The CSI layer's other 2,333
rows are user-created campsites - the ones land managers are often trying to
close - and SOURCE_SURVEY.md §3b says publishing their locations would put
OurHike on the wrong side of every partner it depends on. The WHERE clause
asks for the two official site types by name, so those rows never reach this
machine, let alone the output. What ships is a set of distances attached to
sites this project already publishes, never a CSI site itself.

## The join, and why it is spatial first

CSI carries no FMSS id and no ATC GlobalID, so the join build_shelter_capacity.py
does by name has to lean on geometry here - and geometry is the stronger
evidence anyway, because a CSI row and an ATC feature describing the same site
are two surveys of one physical place. Measured over the live layers before any
of this was written: the median offset from an ATC shelter to its nearest CSI
shelter row is 21 m. Names corroborate rather than decide: CSI's are messy
("West Mountain Sh tent site 1", "1088.1 Quarry Gap Shelters Campsite 2",
"Campsite @ mile 1924.3"), and CSI records individual numbered tent pads where
ATC records one campsite, so several CSI rows can honestly describe one ATC
feature. The gates mirror lib/poi_sites.py's, for the same reason it has two:

  - A candidate whose name agrees may match from up to 150 m
    (NAME_MATCH_RADIUS_M there; the name is carrying the argument).
  - With no name agreement, only 60 m (PROXIMITY_RADIUS_M; geometry is all
    the evidence there is).

**Coverage is partial and the blanks are honest.** ~182 of 280 shelters and
~72 of 232 campsites have any CSI row within 150 m; the gaps are mostly Maine,
where CSI simply has no rows near MATC's lean-tos. Every unmatched feature is
listed with a reason rather than dropped, the same complete-statement shape as
shelter_capacity.json, so a match lost on a later run is a changed line in a
diff rather than a disappearance.

A `Proximity_Water_ft` of 0 (35 of the 1,013) resolves to nothing published:
zero reads as at-the-source or as unmeasured, and the row does not say which.
A distance a hiker plans an evening around has to be a statement, not a shrug.

## The provenance rule: an allowlist, and how the FarOut rows joined it

CSI's `Nearest_Water_Source` says what each distance was measured against.
`NHDP_HR_Stream` and `NHDP_HR_Pond` rows are measured against USGS
hydrography - public domain - and `OSA_Field_Estimate` rows are ATC's own
stewards' numbers. `FarOut` rows - the largest bucket - are measured against
the waypoints in ATC's official app, and #668 first shipped with those 218
matches held back: WATER_SOURCES.md §4 flagged the derivation from a
commercial dataset this project has no independent rights to, and §7 kept
unblessed CSI derivation on "what not to build". The holdback existed to
leave that call visible for the maintainer rather than make it in code.

The maintainer made it on 2026-08-13 - "anything from the ATC is reusable",
then, asked specifically about these rows, "go ahead and include those 218
rows" (#688). The reading that authorises: the distance is ATC's own derived
fact, published by ATC in ATC's own public layer, and the maintainer takes
ATC-published data as reusable on the `photo_licence` footing. sources.json's
`atc_licence` block records the declaration; WATER_SOURCES.md §4's amendment
records the release.

PUBLISHABLE_PROVENANCES stays an allowlist all the same. A provenance value
ATC introduces later publishes nothing until a human reads what it derives
from and adds it deliberately - a matched row with an unknown provenance
keeps its join evidence and listed value (the number is one public `?f=json`
query away on ATC's own service regardless) with the reason stated.

## Licence, stated rather than discovered later

The CSI layer sits on ATC's own ArcGIS org, whose formal reuse terms remain
unstated - the ATC row of SOURCE_SURVEY.md §9's table, the analogue of #98's
opentrail question. Ingestion rides sources.json's `atc_licence` block:
maintainer authorisation on the basis of ATC affiliation, dated, recorded
rather than assumed. ATC's own written answer stays the ideal - §10's
combined ask is now a confirmation rather than a blocker - and a club
inheriting this project should re-confirm all of it in its own name.

## Why the output is checked in rather than fetched at build time

The same reason shelter_capacity.json is: the join encodes judgement calls -
which CSI row is this shelter, which blanks are refusals - and a join that
runs unsupervised inside a data build is a join nobody ever reads. Checked in,
every decision is a reviewable line in a diff, and a release build needs
neither the network nor ATC's org continuing to answer.

Re-run this script when the CSI layer changes; review the diff it makes.

Usage:
    python build_water_distance.py [--check]

`--check` re-derives the file and exits non-zero if it differs from what is
on disk, without writing.
"""

import argparse
import json
import re
import sys
from pathlib import Path

import requests

from lib.spurs import distance_m

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
OUT_PATH = ROOT / "reference" / "water_distance.json"

# The Campsite_Sustainability_Index "Overnight Site" layer on ATC's own org.
# Deliberately NOT in sources.json: the registry is what fetch_all.py fetches
# on a schedule, and SOURCE_SURVEY.md §10 keeps ATC-org layers out of it until
# the terms conversation happens. This script's docstring is where the layer's
# provenance and licence position live, exactly as build_shelter_capacity.py
# holds greenbelly's.
CSI_LAYER_URL = "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/Campsite_Sustainability_Index/FeatureServer/0"

# The two official site types, spelled exactly as the layer spells them. The
# third value, "User Created Campsite", is never requested - see the module
# docstring. (A fourth value, a literal " ", exists on a handful of rows and
# is likewise excluded by asking for what is wanted rather than filtering out
# what is not.)
OFFICIAL_SITE_TYPES = ("Shelter", "A.T. Club or Agency Created Campsite")

# The registered layers whose features get a distance, by sources.json key.
# Also the `layer` value each output record carries, so the file speaks the
# registry's language rather than inventing a third name for the same thing.
ATC_LAYERS = ("shelters", "campsites")

# Which `Nearest_Water_Source` provenances may publish a distance - the
# module docstring's provenance rule. NHD is public domain, a field estimate
# is ATC's own steward speaking, and the FarOut-measured rows were held back
# until 2026-08-13, when the maintainer authorised them ("anything from the
# ATC is reusable", asked again specifically about these 218 rows) - the
# `atc_licence` block in sources.json records that basis, and #688 the
# release. Still an allowlist on purpose: a provenance value ATC introduces
# later refuses until a human reads what it derives from and adds it here
# deliberately.
PUBLISHABLE_PROVENANCES = frozenset({"NHDP_HR_Stream", "NHDP_HR_Pond", "OSA_Field_Estimate", "FarOut"})

UNKNOWN_PROVENANCE = (
    "the CSI row's provenance {provenance!r} is not one this build knows - held back "
    "until a human reads what it derives from and adds it to PUBLISHABLE_PROVENANCES deliberately"
)

USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"
TIMEOUT = 60
PAGE_SIZE = 1000

# lib/poi_sites.py's two gates, restated here with that module's reasoning:
# a name match is the better evidence and may reach further; proximity alone
# is the fallback and stays tight. The numbers are copied rather than imported
# because poi_sites measured them for pin-folding between ATC's own layers,
# and this join is between two different surveys of one place - they happen
# to be the right scale for both, but they are two decisions, not one.
NAME_MATCH_RADIUS_M = 150.0
PROXIMITY_RADIUS_M = 60.0

# Words that say what a site *is* rather than which one it is, dropped before
# names are compared. CSI abbreviates freely ("Sh" for shelter, "tent site 1",
# "mile 1924.3" as a whole name), so this list is longer than
# build_shelter_capacity.py's GENERIC_WORDS.
GENERIC_WORDS = frozenset(
    (
        "shelter",
        "shelters",
        "sh",
        "leanto",
        "leantos",
        "lean",
        "to",
        "tos",
        "hut",
        "cabin",
        "campsite",
        "campsites",
        "camp",
        "campground",
        "tentsite",
        "tentsites",
        "tent",
        "tents",
        "site",
        "sites",
        "pad",
        "pads",
        "group",
        "area",
        "the",
        "at",
        "mile",
        "mp",
    )
)

# The same expansions build_shelter_capacity.py needed, for the same reason:
# ATC writes "Mtn" where CSI writes "Mountain".
ABBREVIATIONS = {
    "mt": "mountain",
    "mtn": "mountain",
    "mtns": "mountains",
    "br": "branch",
    "ck": "creek",
    "cr": "creek",
    "rd": "road",
}

NO_ROW_NEARBY = f"no CSI row within {NAME_MATCH_RADIUS_M:.0f} m"


def normalise(name: str | None) -> str:
    """A site name reduced to the words that identify *which* site it is.

    Lowercased, punctuation to spaces, abbreviations expanded, generic type
    words dropped - and every pure-digit token dropped with them, because a
    digit here is a sibling number ("tent site 1"), a mile prefix ("1088.1
    Quarry Gap..."), or CSI's whole name for an unnamed spot ("Campsite @
    mile 1924.3"), none of which identifies a place. The one name that IS a
    number - PA's 501 Shelter - would reduce to nothing, so a name whose
    only identifying tokens are digits keeps them instead.
    """
    text = re.sub(r"[^a-z0-9]+", " ", (name or "").lower())
    words = [ABBREVIATIONS.get(word, word) for word in text.split()]
    kept = [word for word in words if word not in GENERIC_WORDS and not word.isdigit()]
    if kept:
        return " ".join(kept)
    return " ".join(word for word in words if word not in GENERIC_WORDS)


def names_agree(atc_name: str | None, csi_name: str | None) -> bool:
    """Whether two names identify the same place, on the normalised forms.

    Containment either way, not just equality: ATC's "Springer Mtn Shelter
    Campsite 1" and CSI's "Springer mountain shelter site 9" both reduce to
    "springer mountain", but CSI also writes rows like "Wise Shelter spring
    side" whose extra words are its own and should not break the match.
    An empty normalised form agrees with nothing - "Campsite @ mile 1924.3"
    reduces to nothing and must not thereby match everything.
    """
    ours, theirs = normalise(atc_name), normalise(csi_name)
    if not ours or not theirs:
        return False
    return ours == theirs or ours in theirs or theirs in ours


def fetch_csi_sites() -> list[dict]:
    """Every official CSI site, paginated past the layer's record cap.

    The WHERE clause names the official types - the user-created rows are
    never requested (module docstring). Rows are (RIMS_ID, Location,
    Site_Type, Proximity_Water_ft, Nearest_Water_Source, Latitude, Longitude);
    the layer populates Latitude/Longitude on every row, and a row that
    somehow lacks them is skipped rather than placed at (0, 0).
    """
    quoted = ", ".join("'" + site_type.replace("'", "''") + "'" for site_type in OFFICIAL_SITE_TYPES)
    where = f"Site_Type IN ({quoted})"
    fields = "RIMS_ID,Location,Site_Type,Proximity_Water_ft,Nearest_Water_Source,Latitude,Longitude"

    rows: list[dict] = []
    offset = 0
    while True:
        response = requests.get(
            f"{CSI_LAYER_URL}/query",
            params={
                "where": where,
                "outFields": fields,
                "returnGeometry": "false",
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": PAGE_SIZE,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise ValueError(f"The CSI layer answered with an error: {payload['error']}")
        page = [feature["attributes"] for feature in payload.get("features", [])]
        rows.extend(row for row in page if row.get("Latitude") is not None and row.get("Longitude") is not None)
        if not payload.get("exceededTransferLimit"):
            break
        offset += len(page)

    if not rows:
        raise ValueError("The CSI layer returned no official sites - the layer or its Site_Type values have changed")
    return rows


def layer_url(key: str) -> str:
    """A registered layer's URL, read from sources.json rather than repeated
    here - the registry is where an upstream url has its one home."""
    registry = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    for source in registry["sources"]:
        if source["key"] == key:
            return source["url"]
    raise ValueError(f"No {key!r} entry in {SOURCES_PATH}")


def fetch_atc_features(key: str) -> list[dict]:
    """Every feature of one registered layer as {global_id, name, lat, lon},
    ordered by name then id so the output file is stable run to run."""
    response = requests.get(
        f"{layer_url(key)}/query",
        params={"where": "1=1", "outFields": "GlobalID,Name", "returnGeometry": "true", "outSR": 4326, "f": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        raise ValueError(f"The ATC {key} layer returned no features")
    rows = [
        {
            "global_id": feature["attributes"]["GlobalID"],
            "name": feature["attributes"]["Name"],
            "lat": feature["geometry"]["y"],
            "lon": feature["geometry"]["x"],
        }
        for feature in features
        if feature.get("geometry")
    ]
    return sorted(rows, key=lambda row: (row["name"] or "", row["global_id"]))


def match_csi_row(feature: dict, csi_rows: list[dict]) -> tuple[dict | None, str | None, float | None]:
    """The CSI row for one ATC feature: (row, how it matched, offset in m).

    Name-agreeing candidates win over nearer strangers, and the nearest
    name-agreeing candidate wins over further ones - CSI's per-pad rows mean
    several can agree, and the nearest pad is the site as CSI surveyed it
    closest to where ATC put the feature. With no name evidence at all, only
    a row within PROXIMITY_RADIUS_M may match.
    """
    candidates = []
    for row in csi_rows:
        metres = distance_m(feature["lat"], feature["lon"], row["Latitude"], row["Longitude"])
        if metres <= NAME_MATCH_RADIUS_M:
            candidates.append((metres, row))
    if not candidates:
        return None, None, None

    candidates.sort(key=lambda candidate: candidate[0])
    for metres, row in candidates:
        if names_agree(feature["name"], row.get("Location")):
            return row, "name", metres

    nearest_metres, nearest_row = candidates[0]
    if nearest_metres <= PROXIMITY_RADIUS_M:
        return nearest_row, "proximity", nearest_metres
    return None, None, None


def resolve_layer(layer: str, features: list[dict], csi_rows: list[dict]) -> list[dict]:
    """One output record per ATC feature, every feature present.

    Exactly one of `distance_ft` and `unresolved` is meaningful: a record
    either states a distance or states why it will not, so a blank in the
    output is always a refusal with a reason rather than a hole.
    """
    records = []
    for feature in features:
        record = {
            "layer": layer,
            "atc_global_id": feature["global_id"],
            "atc_name": feature["name"],
            "distance_ft": None,
            "listed_distance_ft": None,
            "provenance": None,
            "csi_rims_id": None,
            "csi_location": None,
            "match": None,
            "offset_m": None,
        }
        row, how, offset = match_csi_row(feature, csi_rows)
        if row is None:
            record["unresolved"] = NO_ROW_NEARBY
            records.append(record)
            continue

        record.update(
            {
                "csi_rims_id": row.get("RIMS_ID"),
                "csi_location": row.get("Location"),
                "match": how,
                "offset_m": round(offset),
            }
        )
        listed = row.get("Proximity_Water_ft")
        provenance = row.get("Nearest_Water_Source")
        if listed is None:
            record["unresolved"] = "the CSI row carries no distance"
        elif listed == 0:
            record["unresolved"] = "the CSI row gives 0 ft, which reads as at-the-source or unmeasured, and does not say which"
        elif provenance not in PUBLISHABLE_PROVENANCES:
            # The join evidence and the listed value stay - the holdback has
            # to be reviewable, and the value is public on ATC's own service
            # regardless - but nothing here reaches an artifact.
            record["listed_distance_ft"] = listed
            record["provenance"] = provenance
            record["unresolved"] = UNKNOWN_PROVENANCE.format(provenance=provenance)
        else:
            record["listed_distance_ft"] = listed
            record["distance_ft"] = max(1, round(listed))
            record["provenance"] = provenance
        records.append(record)
    return records


README = [
    "How far the nearest water source is from each A.T. shelter and campsite,",
    "in feet, keyed to ATC's GlobalIDs.",
    "",
    "GENERATED by build_water_distance.py - re-run that script rather than",
    "editing rows here, and review the diff it produces. export_poi.py reads",
    "this file and publishes `water_distance_ft` on shelter and campsite",
    "features; a record with a null distance publishes none.",
    "",
    "No ATC facility layer carries water at all (the shelter layer's 135 fields",
    "and the campsite layer's 98 were checked one by one, 2026-08-13). The",
    "distances come from the Campsite_Sustainability_Index layer on ATC's own",
    "ArcGIS org - official sites only, the user-created rows are never even",
    "requested - joined to ATC's features spatially with name agreement",
    "preferred. `provenance` is CSI's own `Nearest_Water_Source` value,",
    "verbatim: how ATC measured that row (FarOut waypoints, NHD hydrography,",
    "or a steward's field estimate), which is what each number is worth.",
    "",
    "A null distance always carries an `unresolved` reason - no CSI row near",
    "the feature (most of Maine), a 0 ft value that reads as at-the-source or",
    "unmeasured without saying which, or a provenance value this build does",
    "not know (an allowlist: FarOut joined it 2026-08-13 on the maintainer's",
    "authorisation, #688; anything newer waits for a human). None is a guess:",
    "where water is matters more than most numbers here, so a blank beats an",
    "invention. Every shelter and campsite is listed either way, so a match",
    "lost on a later run shows up as a changed line rather than a vanished",
    "one.",
]


def build(csi_rows: list[dict], features_by_layer: dict[str, list[dict]]) -> dict:
    records = []
    for layer in ATC_LAYERS:
        records.extend(resolve_layer(layer, features_by_layer[layer], csi_rows))
    resolved = [record for record in records if record["distance_ft"] is not None]
    counts = {
        "features": len(records),
        "with_distance": len(resolved),
    }
    for layer in ATC_LAYERS:
        counts[layer] = sum(1 for record in records if record["layer"] == layer)
        counts[f"{layer}_with_distance"] = sum(1 for record in resolved if record["layer"] == layer)
    return {
        "_README": README,
        "source": {
            "title": "Campsite Sustainability Index - Overnight Site (official sites only)",
            "url": CSI_LAYER_URL,
            "provider": "Appalachian Trail Conservancy",
            "licence": (
                "ATC's formal org terms remain unstated (SOURCE_SURVEY.md §9); reuse rides "
                "sources.json's atc_licence block - maintainer authorisation on the basis of ATC "
                "affiliation, 2026-08-13, FarOut-measured rows included on the maintainer's "
                "specific direction (#688). ATC's own written answer stays the ideal; a club "
                "inheriting this project should re-confirm all of it in its own name."
            ),
            "note": (
                "Only Site_Type in ('Shelter', 'A.T. Club or Agency Created Campsite') is ever "
                "requested; the layer's 2,333 user-created campsites never reach this build. "
                "Distances attach to features already published from ATC's facility layers."
            ),
        },
        "counts": counts,
        "sites": records,
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

    print(f"Fetching official CSI sites from {CSI_LAYER_URL} ...")
    csi_rows = fetch_csi_sites()
    print(f"  {len(csi_rows)} official sites.")

    features_by_layer = {}
    for layer in ATC_LAYERS:
        print(f"Fetching the ATC {layer} layer ...")
        features_by_layer[layer] = fetch_atc_features(layer)

    document = build(csi_rows, features_by_layer)
    counts = document["counts"]
    for layer in ATC_LAYERS:
        print(f"  {counts[f'{layer}_with_distance']}/{counts[layer]} {layer} resolved to a water distance.")

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
