"""Build reference/shelter_capacity.json - how many people each A.T. shelter
sleeps, keyed to ATC's own shelter ids.

**No ATC source carries capacity.** Searched rather than assumed, against
the live services (2026-08-09), because a field we already had would beat
anything below:

  - All twelve registered sources in `sources.json`. The shelter layer's own
    135 fields are an FMSS asset inventory - exterior length and width, roof
    area, door and window counts, `FMSS_QTY` (floor area, not people:
    15.6 x 15.6 = 243.36 exactly). Nothing in any of them is a person count.
    The only near-misses are `parking`'s space counts.
  - `ANST_Facilities`' three asset tables (`Assets_Structures`,
    `Assets_Trail`, `Assets_Bridges`), which are not in `sources.json` and
    are what the shelter layer's one relationship points at, joined on
    `FMSS_LocID`. They are a maintenance inventory - asset number,
    replacement cost, quantity in EA/LF/SF. There are `Sleeping Platform`
    asset types, and they are 6 rows across the whole trail, all measured in
    square feet.
  - The shelter layer's free text (`Comments`, `Descriptio`, `Feat_Name`) on
    all 280 features. Twenty-odd mention sleeping space; every one is a
    dimension - "272 sq ft sleeping space", "sleeping loft 8 x 7 plywood".
    Floor area could be divided into a person count, and that would be an
    invention, not a reading.
  - The sibling A.T. services in the same NPS org
    (`ANST_Administrative_Features`, `AT_Lands`, `AT_Communities`).

So capacity has to come from somewhere else, and the somewhere else is a
hiker-maintained list rather than a GIS layer.

*One layer in that org does have a real capacity field and is deliberately
not used:* `GRSM_BACKCOUNTRY_SHELTERS`, the Smokies park layer, covers 15
shelters of which 12 are in ATC's. A source for a twentieth of the trail
would buy a second join, a second provenance and a precedence rule, and it
is worth knowing what it would buy them for: its numbers agree with this
file on all 12, exactly. That agreement is the useful part - an independent
NPS-published check on the list below, wherever the two can be compared -
and it is recorded here rather than wired in.

Source: https://www.greenbelly.co/pages/appalachian-trail-shelters, a single
HTML table of every shelter with a `Capacity` column, which the page credits
to "Whiteblaze, Appalachian Trail Conservancy, TNlandforums". **Its terms are
not formally confirmed** - the page carries no licence statement - which puts
it in the same position as opentrail.org (#98) and is recorded the same way,
in `sources.json` and in README.md, rather than left to be discovered later
(CONTRIBUTING.md, "A note on data and licences").

Two things narrow what is taken. Only the capacity number is kept: not the
mileages, the next-shelter distances, the elevations, or the ordering, all of
which OurHike either has from ATC already or does not want. And what is kept
is re-keyed onto ATC GlobalIDs, so the output is a set of facts about
shelters this project already knows about, not a copy of somebody's table.

## Why the output is checked in rather than fetched at build time

The join between the two lists is by *name*, and names disagree: ATC's
"Doc's Knob Shelter" is the source's "Docs Knob Shelter", ATC's "Winturri"
is its "Wintturi", and ATC splits into "Rocky Run Shelter 1"/"2" what the
source lists once as "Rocky Run Shelters". A fuzzy join that runs
unsupervised inside a data build is a join nobody ever reads. Checking the
resolved file in makes every one of those decisions a reviewable line in a
diff, and means a release build needs neither the network nor the page
continuing to exist.

Re-run this script when the upstream list changes; review the diff it makes.

Usage:
    python build_shelter_capacity.py [--check]

`--check` re-derives the file and exits non-zero if it differs from what is
on disk, without writing - for confirming the checked-in file still matches
what the sources say.

## What "unresolved" means, and why so much of it is deliberate

A shelter with no capacity here is a shelter this script refused to guess
about, and each one records why. The refusals are not incidental: capacity
is a number a hiker plans an evening around, and an invented one is worse
than a blank. Three kinds recur:

  - The source lists one row for a *pair* of shelters ATC holds separately
    ("Rocky Run Shelters", capacity 16, against ATC's "Rocky Run Shelter 1"
    and "2"). 16 might be the pair's total or each one's - the row does not
    say. The exception is a row that gives both numbers and they agree
    ("8+8" for the two Horns Pond lean-tos), which resolves to 8 each with
    nothing assumed.
  - The row gives two different numbers for one shelter ("6o/8n" at Carter
    Gap, an old structure and a new one; "9+8" at Rock Spring Hut). Picking
    one is a coin flip.
  - The row's capacity is not a number at all - "xxx", "???", "A lot",
    "6 ?". Blank is the honest reading of every one of those.
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path

import requests

# The one home of the source name (#671): the ledger id this file is keyed
# by is `{SHELTER_SOURCE}:{GlobalID}`, and spelling it locally would be the
# second copy that drifts.
from export_poi import SHELTER_SOURCE

ROOT = Path(__file__).parent
SOURCES_PATH = ROOT / "sources.json"
OUT_PATH = ROOT / "reference" / "shelter_capacity.json"

GREENBELLY_URL = "https://www.greenbelly.co/pages/appalachian-trail-shelters"

# The page is served by a CMS that returns 403 to an unadorned client.
USER_AGENT = "OurHike-pipeline/1.0 (+https://github.com/OurHike/OurHike)"

TIMEOUT = 60

# Generic words that say what a structure *is* rather than which one it is.
# Dropping them is what lets "Chairback Gap Lean-to" meet ATC's "Chairback
# Gap Lean-to Shelter" without either list being edited.
GENERIC_WORDS = frozenset(
    ("shelter", "shelters", "leanto", "leantos", "lean", "to", "tos", "hut", "cabin", "campsite", "campsites", "camp")
)

# Abbreviations each list expands differently. ATC writes "Mtn" and "Rd";
# the source writes them out.
ABBREVIATIONS = {
    "mt": "mountain",
    "mtn": "mountain",
    "mtns": "mountains",
    "br": "branch",
    "ck": "creek",
    "cr": "creek",
    "rd": "road",
}

# ATC shelter name -> the (name, state) of its row in the source list, for
# the pairs normalise() cannot bring together on its own. Every one was read
# by hand against both lists; the state is carried because two rows share a
# name ("Cove Mountain Shelter" exists in both VA and PA, which is exactly
# why ATC disambiguates its own two with a parenthesis).
ALIASES = {
    "Allentown Shelter": ("Allentown Hiking Club Shelter", "PA"),
    "Amicalola Falls (Max Epperson) Shelter": ("Max Epperson Shelter", "GA"),
    "Carlo Col Shelter": ("Carlo Col Shelter & Campsite", "ME"),
    "Chatfield Memorial Shelter": ("Chatfield Shelter", "VA"),
    "Cove Mtn (PA) Shelter": ("Cove Mountain Shelter", "PA"),
    "Cove Mtn (VA) Shelter": ("Cove Mountain Shelter", "VA"),
    "East Branch (Pleasant River) Lean-to Shelter": ("East Branch Lean-to", "ME"),
    "Garfield Ridge Shelter": ("Garfield Ridge Campsite & Shelter", "NH"),
    "Gentian Pond Shelter": ("Gentian Pond Shelter & Campsite", "NH"),
    "James Fry at Tagg Run Shelter": ("James Fry (Tagg Run) Shelter", "PA"),
    "Morgan Stewart Shelter": ("Morgan Stewart Memorial Shelter", "NY"),
    "Mountaineer Falls Shelter": ("Mountaineer Shelter", "TN"),
    "Plumorchard Shelter": ("Plumorchard Gap Shelter", "GA"),
    "Smarts Mtn Fire Warden's Cabin Shelter": ("Smarts Mountain Cabin", "NH"),
    "Speck Pond Shelter": ("Speck Pond Shelter & Campsite", "ME"),
    "The Perch Shelter": ("The RMS Perch Shelter", "NH"),
    "Wayah Shelter": ("Wayah Bald Shelter", "NC"),
    "Winturri Shelter": ("Wintturi Shelter", "VT"),
}

# Source rows covering more than one ATC shelter. Both tables map a row onto
# the ATC names it spans; the difference is only whether the row's capacity
# survives the split.
#
# PAIRS: the row states both numbers *and they agree* - "8+8" over two
# lean-tos is 8 each however it is read, so nothing is assumed by splitting.
PAIRS = {
    ("Horns Pond Lean-tos", "ME"): ("Horns Pond Lean-to Shelter 1", "Horns Pond Lean-to Shelter 2"),
    ("The Birches Lean-tos & Campsite", "ME"): ("The Birches Lean-to Shelter 1", "The Birches Lean-to Shelter 2"),
}

# SHARED_ROWS: the row gives one capacity for shelters ATC holds separately,
# and does not say whether that number is each shelter's or the group's.
# These are listed rather than left to fall through as "no row" so the file
# records the real reason - the row exists and was read, and splitting it
# would be a guess. "Deer Lick Shelters" is here for the neighbouring reason:
# its "2+5" names two different numbers without saying which shelter is
# which. The Johns Spring row names a second shelter (Boy Scout) that is not
# in ATC's layer at all, which leaves its single 6 just as unattributable.
SHARED_ROWS = {
    ("Deer Lick Shelters", "PA"): ("Deer Lick Shelter 1", "Deer Lick Shelter 2"),
    ("Johns Spring/Boy Scout Shelter", "VA"): ("Johns Spring Shelter",),
    ("Mt. Wilcox South Shelters", "MA"): ("Mt. Wilcox South Shelter 1", "Mt. Wilcox South Shelter 2"),
    ("Rocky Mountain Shelters", "PA"): ("Rocky Mtn Shelter 1", "Rocky Mtn Shelter 2"),
    ("Rocky Run Shelters", "MD"): ("Rocky Run Shelter 1", "Rocky Run Shelter 2"),
    ("Tumbling Run Shelters", "PA"): ("Tumbling Run Shelter 1", "Tumbling Run Shelter 2"),
}

# Shelter-and-campsite rows: "16s/4c" is 16 sleeping in the shelter and 4
# tent sites beside it. Only the shelter figure is a shelter's capacity.
SHELTER_AND_CAMPSITE = re.compile(r"^(\d+)\s*s\s*/\s*\d+\s*c$", re.IGNORECASE)

# Two structures under one row: "8+8" for a pair of lean-tos, "6o/8n" for an
# old shelter and its replacement standing at the same site. Only equal
# halves are usable.
TWO_STRUCTURES = re.compile(r"^(\d+)\s*\+\s*(\d+)$")
OLD_AND_NEW = re.compile(r"^(\d+)\s*o\s*/\s*(\d+)\s*n$", re.IGNORECASE)

PLAIN_NUMBER = re.compile(r"^\d+$")

NO_ROW = "no row in the source list"


def normalise(name: str) -> str:
    """A shelter name reduced to the words that identify *which* shelter it
    is - lowercased, punctuation dropped, abbreviations expanded, and the
    generic structure words removed."""
    text = name.lower().replace("&", " and ")
    # Apostrophes close up rather than split: "Doc's" is one word, and
    # splitting it strands an "s" that stops it meeting the other list's
    # "Docs". Every other punctuation mark separates.
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [ABBREVIATIONS.get(word, word) for word in text.split()]
    return " ".join(word for word in words if word not in GENERIC_WORDS)


def parse_capacity(raw: str) -> tuple[int | None, str | None]:
    """Read the source's `Capacity` cell as (capacity, reason it is blank).

    Exactly one of the two is set. The reason travels with the record so a
    blank in the output is always a stated refusal rather than a hole.
    """
    value = raw.strip()

    if PLAIN_NUMBER.match(value):
        people = int(value)
        # The one 0 in the list is a state-park campground with no shelter.
        # Zero is not a capacity; it is the absence of one.
        if people == 0:
            return None, f"the source gives {value!r}, which is not a shelter capacity"
        return people, None

    split = SHELTER_AND_CAMPSITE.match(value)
    if split:
        return int(split.group(1)), None

    both = TWO_STRUCTURES.match(value) or OLD_AND_NEW.match(value)
    if both:
        first, second = int(both.group(1)), int(both.group(2))
        if first == second:
            return first, None
        return None, f"the source gives {value!r} for two structures and does not say which is which"

    return None, f"the source gives {value!r}, which is not a number"


def fetch_page(url: str = GREENBELLY_URL) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_rows(page: str) -> list[dict]:
    """The source page's one table, as {name, state, capacity} dicts.

    Deliberately strict about the header: this is scraped HTML, and a column
    order that has quietly changed should stop the build rather than write a
    file of elevations labelled as capacities.
    """
    match = re.search(r"<table.*?</table>", page, re.DOTALL)
    if match is None:
        raise ValueError(f"No table found at {GREENBELLY_URL} - the page's structure has changed")

    def cells(row: str) -> list[str]:
        found = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.DOTALL)
        return [html.unescape(re.sub(r"<[^>]+>", "", cell)).replace("\xa0", " ").strip() for cell in found]

    rows = [cells(row) for row in re.findall(r"<tr.*?</tr>", match.group(0), re.DOTALL)]
    rows = [row for row in rows if row]
    if not rows:
        raise ValueError("The source table has no rows")

    header = rows[0]
    expected = ("Name", "State", "Capacity")
    positions = {}
    for column in expected:
        if column not in header:
            raise ValueError(f"The source table has no {column!r} column - found {header}. Column names have changed.")
        positions[column] = header.index(column)

    parsed = []
    for row in rows[1:]:
        if len(row) != len(header):
            continue
        parsed.append(
            {
                "name": row[positions["Name"]],
                "state": row[positions["State"]],
                "capacity": row[positions["Capacity"]],
            }
        )
    return parsed


def shelters_layer_url() -> str:
    """The ATC shelters layer, read from sources.json rather than repeated
    here - the registry is where an upstream url has its one home."""
    registry = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    for source in registry["sources"]:
        if source["key"] == "shelters":
            return source["url"]
    raise ValueError(f"No 'shelters' entry in {SOURCES_PATH}")


def fetch_atc_shelters() -> list[dict]:
    """Every ATC shelter as {global_id, name}, ordered by name."""
    response = requests.get(
        f"{shelters_layer_url()}/query",
        params={"where": "1=1", "outFields": "GlobalID,Name", "returnGeometry": "false", "f": "json"},
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    features = response.json().get("features", [])
    if not features:
        raise ValueError("The ATC shelters layer returned no features")
    shelters = [{"global_id": f["attributes"]["GlobalID"], "name": f["attributes"]["Name"]} for f in features]
    return sorted(shelters, key=lambda s: s["name"])


def index_rows(rows: list[dict]) -> dict[str, dict]:
    """Source rows by normalised name, for the shelters whose names already
    agree with ATC's.

    Two rows can normalise the same way. Where one of them names a structure
    ("Springer Mountain Shelter") and the other names the landmark it sits
    below ("Springer Mountain", a summit with no capacity at all), the
    structure wins. Where both name structures - the two "Cove Mountain
    Shelter" rows, one in VA and one in PA - neither wins, and the pair is
    left to ALIASES, which carries the state that tells them apart.
    """
    by_name: dict[str, list[dict]] = {}
    for row in rows:
        by_name.setdefault(normalise(row["name"]), []).append(row)

    index = {}
    for key, matches in by_name.items():
        if len(matches) == 1:
            index[key] = matches[0]
            continue
        structures = [
            row for row in matches if any(word in row["name"].lower() for word in ("shelter", "lean-to", "hut", "cabin"))
        ]
        if len(structures) == 1:
            index[key] = structures[0]
    return index


def resolve(shelters: list[dict], rows: list[dict]) -> list[dict]:
    """One output record per ATC shelter, in ATC name order.

    Every shelter appears, with or without a capacity, so that the file is a
    complete statement about the layer rather than only its good news - and
    so a shelter that loses its match on a later run shows up in the diff as
    a change rather than a disappearance.
    """
    by_normalised = index_rows(rows)
    by_name_state = {(row["name"], row["state"]): row for row in rows}

    def spread(table: dict) -> dict[str, dict]:
        """One of the multi-shelter tables flattened to ATC name -> row, so
        the loop below treats a shared row like any other match."""
        out = {}
        for key, atc_names in table.items():
            row = by_name_state.get(key)
            if row is None:
                continue
            for atc_name in atc_names:
                out[atc_name] = row
        return out

    paired = spread(PAIRS)
    shared = spread(SHARED_ROWS)

    records = []
    for shelter in shelters:
        name = shelter["name"]
        row = paired.get(name) or shared.get(name)
        if row is None and name in ALIASES:
            row = by_name_state.get(ALIASES[name])
        if row is None:
            row = by_normalised.get(normalise(name))

        # Keyed by the LEDGER id, not the bare GlobalID (#671): the ledger
        # owns published identity across upstream refreshes, so this file
        # stops depending on GlobalID stability the day the two diverge.
        # The spelling matches at seeding (a ledger id is minted as
        # `atc_shelters:{GlobalID}` and kept as a birthmark), which is what
        # made the re-key a no-op diff on published bytes.
        record = {"poi_id": f"{SHELTER_SOURCE}:{shelter['global_id']}", "atc_name": name}
        if row is None:
            record.update({"capacity": None, "listed_as": None, "listed_capacity": None, "unresolved": NO_ROW})
            records.append(record)
            continue

        record.update({"capacity": None, "listed_as": row["name"], "listed_capacity": row["capacity"]})
        if name in shared:
            # Read but not split: the row's one capacity covers shelters ATC
            # keeps apart, and nothing in it says which number is whose.
            record["unresolved"] = (
                f"the source's {row['name']!r} row covers more than one shelter with a single "
                f"capacity of {row['capacity']!r} and does not say which is which"
            )
            records.append(record)
            continue

        capacity, reason = parse_capacity(row["capacity"])
        record["capacity"] = capacity
        if reason is not None:
            record["unresolved"] = reason
        records.append(record)
    return records


README = [
    "How many people each A.T. shelter sleeps, keyed by the POI identity",
    "ledger's id (reference/poi_identity.json, #671) - the id export_poi.py",
    "publishes, durable across upstream refreshes where a bare GlobalID is",
    "not.",
    "",
    "GENERATED by build_shelter_capacity.py - re-run that script rather than",
    "editing rows here, and review the diff it produces. export_poi.py reads",
    "this file and publishes `capacity` on shelter features; a record with a",
    "null capacity publishes none.",
    "",
    "ATC's own shelter layer has no capacity field (its 135 fields are an FMSS",
    "asset inventory - roof area, door counts, floor space). These numbers come",
    "from greenbelly.co's A.T. shelter list, which credits Whiteblaze, the",
    "Appalachian Trail Conservancy and TNlandforums. That page states no licence,",
    "so its terms are unconfirmed in the same way opentrail.org's are (#98) -",
    "see pipeline/README.md.",
    "",
    "A null capacity always carries an `unresolved` reason. Most are shelters",
    "the source lists in pairs, or with a capacity that is not a number. None",
    "is a guess: a hiker plans an evening around this number, so a blank beats",
    "an invention. Every ATC shelter is listed either way, so a match lost on a",
    "later run shows up as a changed line rather than a vanished one.",
]


def build(page: str, atc_shelters: list[dict]) -> dict:
    records = resolve(atc_shelters, parse_rows(page))
    known = [r for r in records if r["capacity"] is not None]
    return {
        "_README": README,
        "source": {
            "title": "Appalachian Trail Shelters (capacity column)",
            "url": GREENBELLY_URL,
            "provider": "Greenbelly",
            "credits": "Whiteblaze, Appalachian Trail Conservancy, TNlandforums",
            "licence": "unstated - see #98's equivalent question for opentrail.org",
        },
        "counts": {"shelters": len(records), "with_capacity": len(known)},
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

    print(f"Fetching {GREENBELLY_URL} ...")
    page = fetch_page()
    print("Fetching the ATC shelters layer ...")
    atc_shelters = fetch_atc_shelters()

    document = build(page, atc_shelters)
    counts = document["counts"]
    print(f"  {counts['with_capacity']}/{counts['shelters']} ATC shelters resolved to a capacity.")

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
