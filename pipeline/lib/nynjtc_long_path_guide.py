"""NYNJTC's Long Path End-to-End Section Guide, read for the places it names.

The New York-New Jersey Trail Conference publishes the Long Path as forty
web pages, one per section, at nynjtc.org/lp-section-N/ - the same pages
their Long Path layer links to from its `GuideURL` field (sources.json's
`nynjtc_long_path`, which this build already draws). Each page is the
guide's own mile-by-mile description of that section, and it carries the
only POI-shaped data NYNJTC publishes anywhere: POI_COVERAGE_SURVEY.md §6
probed all 25 services on their ArcGIS org and found one empty point layer
and one featured-hikes table. The waypoints are in the prose.

This module owns one job - **turn a section page into facts, and put each
fact on the map** - and deliberately owns nothing about whether those facts
may be published. That split is lib/nynjtc_alerts.py's and lib/club_pdfs.py's
and is kept for the same reason: the parse can be tested without a network,
and the policy (sources.json's `nynjtc_guide_licence`) without a parser.

WHAT A PAGE LOOKS LIKE, measured on all forty on 2026-09-08 (the pages are
WordPress, and every one had the same skeleton; section 22 adds a "Winter
Access" block, which is tolerated). A header carrying "Distance: 14.1 miles",
then four collapsible blocks:

    Access                       driving directions - prose, not read
    Parking                      "1.50  Fort Lee Historic Park ... (40.85181°, -73.96245°)"
    Camping                      "5.13 Mink Hollow Lean-to", or prose, or "None."
    Detailed Trail Description   "4.30  A sign marks the way to a spring, ..."

Every entry in the last three opens with a mile from the section's own
start - the guide restarts at 0.00 every section, so a mile here is never
the A.T.'s NOBO mile and is never written into the schema's `mile` field.
The Parking block is the structured prize: NYNJTC gives most lots their own
coordinates, in the text, to five decimals. 153 pairs across the forty pages
on 2026-09-08, against 1,256 mile-marked entries in total.

TWO KINDS OF POSITION, AND THEY ARE NOT THE SAME CONFIDENCE. An entry with
its own coordinates is placed where NYNJTC put it (`placement: "stated"`,
CONFIDENCE_HIGH). An entry with only a mile is placed by walking that many
miles along the section's line from the registered layer (`placement:
"interpolated"`, CONFIDENCE_LOW) - and that is an estimate, for two reasons
the measurement below puts numbers on: the layer's line is generalised (its
geometric length runs 83-105% of the guide's stated distance per section,
measured 2026-09-08), and a mile in the guide is where NYNJTC's walker read
it, not a survey. spike_long_path_guide_placement.py measures the estimate
against the lots that carry both a mile and coordinates, and its docstring
carries the result; INTERPOLATION_ERROR_M below is that result, so the
number the code rests on is the one the spike can re-derive.

WHAT IS NOT PLACED AT ALL, because a wrong pin is worse than none:

  - An entry NYNJTC marks "(unlocated)". Their word for it.
  - A mile past the section's stated distance. Section 40 lists a trailhead
    at 40.10 on a 36.6-mile section; there is no line to walk it along.
  - Camping that is an area rather than a point ("Camping is allowed in the
    state reforestation areas 150 feet from the trail") - kept as a note on
    the section, never a pin.

AND ONE THING THAT IS PLACED WITH A SENTENCE ON IT. An entry that says how
far off the trail it is ("1.05 miles from the Long Path", "on the Dutcher
Notch Trail at 0.35 miles") and gives no coordinates is pinned at ITS MILE
- where the walker leaves the Long Path for it - with `off_trail_miles`
carried and the description saying that the pin marks the turn-off, not
the place. The alternative, leaving it out, was weighed and lost on the
water path specifically: Dutcher Notch's spring is "the only reliable water
in this section" and is 0.35 mi down a side trail, and a hiker is better
served by a pin that says so than by no pin.

WATER IS THE SAFETY PATH and gets the narrowest rule in the file. An entry
becomes a water candidate only when it names a spring in the water sense,
or says "source of water" / "water source" outright. "In the spring, the
hobblebush puts on a spectacular show" is a season, "Cold Spring" is a
town, and both are refused by pattern rather than by luck - the tests name
each. What the rule does NOT do is read "crosses a stream" as water: the
guide says that 178 times and most of them are a thing to step over, not a
thing to drink from. A stream that is a water source will have to be said
to be one. Everything water-shaped that this places is CONFIDENCE_LOW
unless NYNJTC gave it coordinates, and none of them had on 2026-09-08.

THE PROSE STAYS ON NYNJTC'S PAGE. What a record carries is the fact - type,
position, section, mile, an off-trail distance where stated, a short name
where the entry has one - and a link to the page it came from. Not the
sentence. That is the split `nynjtc_notices_licence` already draws for
their alerts (headline and link, never body text), and it is drawn here
before anybody has said the sentence may travel.
"""

from __future__ import annotations

import html as html_module
import math
import re
from dataclasses import dataclass, field

from lib.poi_schema import CONFIDENCE_HIGH, CONFIDENCE_LOW, POI_TYPES

SOURCE_KEY = "nynjtc_long_path_guide"

#: The registered layer whose lines a mile is walked along. The join is by
#: that layer's own `LP_Section` field, which is why this module needs no
#: table of its own to say which line is section 18.
LINE_SOURCE_KEY = "nynjtc_long_path"

#: `trail_id` for every record here. export_nearby_poi.py keys its ids on the
#: PROVIDER because DEC's and OPRHP's rows belong to a land manager rather
#: than a trail; these rows belong to one trail and the guide is written
#: against it, so the record says which.
TRAIL_ID = "LP"

INDEX_URL = "https://www.nynjtc.org/long-path-end-to-end-section-guide/"

METERS_PER_MILE = 1609.344
EARTH_RADIUS_M = 6371000.0

#: How far an interpolated position can be expected to sit from where the
#: entry actually is, along the trail, in metres. MEASURED, not picked, and
#: rounded toward caution: over the 151 entries that carry both a mile and
#: NYNJTC's own coordinates (2026-09-08, all forty pages, the live layer),
#: the along-trail distance between the point the mile walks to and the
#: stated point's projection onto the line is median 86 m, p75 213 m, p90
#: 476 m, max 2,430 m. This is the p90, rounded up. The lots themselves sit
#: a median 28 m off the line, so the along-trail figure is the estimate's
#: own error rather than the lot's offset. Three sections measured worse
#: than the rest and are worth knowing about: 23 (median 573 m), 25 (950 m)
#: and 37 (1,223 m) - where the layer's line and the guide's mileage
#: plainly disagree, and a republish of either may move them.
#: `python spike_long_path_guide_placement.py` re-derives every number in
#: this paragraph. Carried on every interpolated record as
#: `position_error_m` so a card can say "about" and mean a number.
INTERPOLATION_ERROR_M = 500

#: The Long Path's own bounding box, with a margin: New York City to the
#: southern Adirondacks. A coordinate pair NYNJTC wrote outside it is a typo
#: (a dropped minus sign, a transposed pair) and is refused rather than
#: drawn in the Indian Ocean. Deliberately loose - a lot two miles off the
#: trail is inside it, and the point is to catch the impossible, not the
#: unlikely.
LAT_RANGE = (40.5, 43.6)
LON_RANGE = (-75.0, -73.5)

#: Endpoints closer than this are the same point when the layer's pieces
#: are chained into one line per section. The layer's segments meet exactly
#: on every section measured 2026-09-08 (largest gap 0 m); the tolerance is
#: for a republish that snaps a vertex.
CHAIN_TOLERANCE_M = 100.0

#: The four blocks a page carries. `Access` is driving directions and is not
#: read; the other three are. Their absence is the layout having changed,
#: which stops the parse rather than emptying it.
REQUIRED_BLOCKS = ("Parking", "Camping", "Detailed Trail Description")

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"[ \t\r\f\v\xa0]+")
_DROPPED = re.compile(r"<(script|style|figure|figcaption)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_LINE_BREAKS = re.compile(r"<br\s*/?>|</p>|</li>|</h[1-6]>|</div>", re.IGNORECASE)
_DETAILS = re.compile(r"<details[^>]*>\s*<summary>(.*?)</summary>(.*?)</details>", re.DOTALL | re.IGNORECASE)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_H2 = re.compile(r"<h2[^>]*>(.*?)</h2>", re.DOTALL | re.IGNORECASE)
_SECTION_LINK = re.compile(r'href="(?:https?://www\.nynjtc\.org)?/lp-section-(\d+)/?"')
_SECTION_TITLE = re.compile(r"Section\s+(\d+)\s*$")
_DISTANCE = re.compile(r"Distance:\s*([\d.]+)\s*miles?", re.IGNORECASE)
_PARKS = re.compile(r"Parks?:\s*(.*)")

#: An entry opens with a mile: one or two digits, a point, one or two more.
#: "0.00", "5.13", "36.60". Anchored to the start of a text line, which is
#: what the page's <br>/<p> boundaries become.
_MILE_LINE = re.compile(r"^\s*(\d{1,2}\.\d{1,2})(?![\d.])\s*(.*)$")

#: "(40.85181°, -73.96245°)" - and "(42.03576°, -74.36531)" too, because the
#: degree sign is dropped on some entries. Latitude first, as NYNJTC writes
#: them.
_COORDS = re.compile(r"\(\s*(-?\d{2}\.\d{3,6})\s*°?\s*,\s*(-?\d{2,3}\.\d{3,6})\s*°?\s*\)")
_UNLOCATED = re.compile(r"\(\s*unlocated\s*\)", re.IGNORECASE)

#: The three ways the guide says a place is off the trail, each read as
#: "this entry is that far off the tread, and its mile is where the walker
#: LEAVES the Long Path for it":
#:
#:   "0.2 mile from the Long Path", "1.05 miles ... from the Long Path",
#:   "1.2 miles from the trail", "2.75 miles along the Wittenberg-Cornell-Slide
#:   Trail (also called Burroughs Range Trail) from the Long Path"
#:
#:   "1.2 miles along the Phoenicia-East Branch Trail from the beginning of
#:   this section" - a distance walked along a NAMED side trail
#:
#:   "a reliable spring on the Dutcher Notch Trail at 0.35 miles"
#:
#: "0.35 miles south of the LP/SRT junction" is deliberately NOT matched: a
#: junction is not the trail. Nor is "passing a seasonal spring in about
#: 0.1 mile", which is a distance AHEAD along the Long Path, not off it -
#: reading it as off-trail would put a true sentence on the card that means
#: the wrong thing.
_OFF_TRAIL = (
    re.compile(
        r"(\d+(?:\.\d+)?)\s*-?\s*miles?\b[^.;]{0,120}?\b(?:from|off|to)\s+the\s+(?:Long\s+Path|LP|trail)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(\d+(?:\.\d+)?)\s*miles?\s+along\s+the\s+[^.;]{0,90}?\bTrail\b"),
    re.compile(r"\bon\s+the\s+[^.;]{0,60}?\bTrail\s+at\s+(\d+(?:\.\d+)?)\s*miles?\b"),
)

# --- classification -------------------------------------------------------
#
# The judgement about what a sentence means lives here, pattern by pattern,
# so a reviewer can reject one line rather than a total. Each pattern is
# applied to the entry's text; an entry may match more than one type (a
# lean-to with a spring beside it is both), and each match is one record.

#: Spring in the water sense. Lowercase, so that "Spring Glen" and "Cold
#: Spring" (place names, capitalised) do not match; the season is refused
#: separately below because it is lowercase too.
_SPRING = re.compile(r"\bsprings?\b")
#: The season: "in the spring", "in spring", "early spring", "spring of 2024",
#: "each spring". Removed from the text before the water sense is looked for,
#: so "In the spring, the hobblebush puts on a spectacular show" is not a
#: water source and "300 feet to a spring" in the same entry (section 18,
#: mile 5.00) still is.
_SEASON = re.compile(
    r"\b(?:in|during|each|every|early|late|by|until|through)\s+(?:the\s+)?spring\b(?!\s+(?:house|box|is|to|on|at|beside|near|behind|left|right))"
    r"|\bspring\s+(?:of\s+)?(?:19|20)\d\d\b|\bspring\s+(?:and|or)\s+(?:summer|fall|autumn)\b|\bspring\s+(?:snowmelt|runoff|thaw|flowers?|bloom|season)\b",
    re.IGNORECASE,
)
#: Water said outright: "a dependable source of water", "the last sure source
#: of water", "last sure water before Big Hill Shelter", "the only reliable
#: water in this section" - and the amenity list a park or snack bar gets,
#: "water, restrooms, phone", which is a tap when the place is open.
_WATER_PHRASE = re.compile(
    r"\b(?:source\s+of\s+water|water\s+source|piped\s+water|potable\s+water|drinking\s+water)\b"
    r"|\b(?:last|sure|only|reliable|dependable)\s+(?:sure\s+|reliable\s+|dependable\s+)?water\b"
    r"|\bwater,\s+(?:restrooms?|vending|food|phone|toilets?)\b|\b(?:restrooms?|food|phone),\s+(?:and\s+)?water\b|\boffers?\s+water\b",
    re.IGNORECASE,
)
#: Water that is not water to drink, or not water any more: a spring HOUSE
#: (a stone structure), "was the water source for the Kaatz mansion" (a
#: demolished one), and a spring that is a road, a hill or a town in
#: lowercase. Refused before anything else is asked of the entry.
_NOT_WATER = re.compile(
    r"\bspring\s*-?\s*houses?\b"
    r"|\b(?:was|were|former|formerly|historic|old|once)\s+(?:the\s+|a\s+)?(?:water\s+source|source\s+of\s+water)\b"
    r"|\bsprings?\s+(?:road|street|lane|avenue|mountain|hill|glen|farm|lake|pond|creek|brook|valley|trail)\b",
    re.IGNORECASE,
)
#: What the guide says about whether the water runs. Read in the cautious
#: direction: any word from the first list makes the source "unreliable"
#: whatever else the sentence says ("seasonal ... reliable in all but the
#: driest times" is seasonal), and only a sentence with none of them and one
#: of the second is "reliable". Neither word present is None, never a guess.
_UNRELIABLE = re.compile(
    r"\b(?:seasonal|intermittent|undependable|unreliable|not\s+reliable|sometimes\s+dry|may\s+be\s+dry|often\s+dry|dries\s+up|unsure|questionable)\b",
    re.IGNORECASE,
)
_RELIABLE = re.compile(
    r"\b(?:reliable|dependable|sure\s+(?:source|water)|piped?\s+spring|year-?round|always\s+(?:flowing|running))\b", re.IGNORECASE
)

_SHELTER = re.compile(r"\blean-?tos?\b|\bshelters?\b", re.IGNORECASE)
#: Not a trail shelter: a roof that is not for sleeping under, an overhang
#: "a good temporary shelter", the Rock Shelter Trail (named for a cave), a
#: former homeless shelter. Removed from the text before _SHELTER is asked,
#: so an entry that says only these is not a shelter and one that says
#: these AND names a lean-to still is.
_NOT_A_SHELTER = re.compile(
    r"\b(?:picnic|bus|pavilion|information|rain|temporary|emergency|rock|homeless|animal|fallout)\s+shelters?\b"
    r"|\bshelters?\s+(?:trail|road|rock|cave)\b",
    re.IGNORECASE,
)
_CAMPSITE = re.compile(
    r"\bcamp\s?sites?\b|\bcamping\s+areas?\b|\btent\s+sites?\b|\bcampgrounds?\b|\bcamping\s+spot\b", re.IGNORECASE
)
#: Camping as an AREA rather than a place - the guide's "camping is allowed
#: in the state forest between mile 21.6 and 22.5" - is a note, not a pin.
_CAMPING_AREA = re.compile(
    r"\bcamping\s+is\s+(?:also\s+)?(?:allowed|permitted|prohibited|not\s+(?:allowed|permitted))\b", re.IGNORECASE
)
#: A viewpoint the guide names as one (a lookout, an overlook, a vista) or
#: praises outright. Deliberately NOT "views of ..." on its own: the guide
#: says that on most ridge entries, and 167 pins for a trail's 358 miles
#: (measured 2026-09-08 with the looser rule) is a screen the map cannot
#: draw; the named-or-praised rule gives 93 on the same day.
_VIEWPOINT = re.compile(
    r"\b(?:lookouts?|overlooks?|viewpoints?|vistas?|view\s?points?)\b"
    r"|\b(?:spectacular|excellent|tremendous|panoramic|magnificent|fine|expansive|sweeping|superb|360-degree)\s+views?\b",
    re.IGNORECASE,
)
_PRIVY = re.compile(r"\bprivy\b|\bprivies\b|\bouthouses?\b|\brest\s?rooms?\b|\btoilets?\b|\bport-?a-?johns?\b", re.IGNORECASE)

#: A proper name for the place, when the entry has one: "Mink Hollow Lean-to",
#: "Big Hill Shelter", "Rockefeller Lookout", "Black Bear Campground". One
#: to four capitalised words ending in a word that names THIS type of place
#: - so a viewpoint that mentions Stoppel Point on the horizon is not named
#: after it. A leading verb ("Pass Cohasset Shelter") is dropped. Anything
#: the pattern does not find is left unnamed: the client prints "Unnamed",
#: which is honest, and a name invented from a sentence is not.
_NAME_ENDINGS = {
    "shelter": r"Lean-?[Tt]o|Leanto|Shelter",
    "campsite": r"Campsite|Campground|Camping\s+Area",
    "water": r"Spring",
    "viewpoint": r"Lookout|Overlook|Vista",
    "privy": r"Privy|Outhouse|Restrooms?",
}
_NAMED_PLACES = {
    poi_type: re.compile(r"\b((?:[A-Z][\w'’-]*\s+){1,4}(?:" + ending + r"))\b") for poi_type, ending in _NAME_ENDINGS.items()
}
#: Where a parking entry's name ends: a comma, a bracket, a dash, or a full
#: stop that is not an abbreviation's ("Parking lot at the end of St. Mary's
#: Road" keeps its saint).
_CLAUSE_BREAK = re.compile(r"[,(;:]|\s[–-]\s|(?<!\bSt)(?<!\bMt)(?<!\bRt)(?<!\bDr)(?<!\bRte)(?<!\bAve)\.(?:\s|$)")
_LEADING_VERB = re.compile(
    r"^(?:Pass|Reach|Arrive\s+at|Cross|Turn|Continue|Follow|The\s+trail\s+\w+|At|To|From)\s+", re.IGNORECASE
)


@dataclass
class Entry:
    """One mile-marked line of a block, as parsed."""

    mile: float
    text: str
    lat: float | None = None
    lon: float | None = None
    unlocated: bool = False
    off_trail_miles: float | None = None
    coordinates_rejected: bool = False


@dataclass
class Section:
    number: int
    title: str
    distance_miles: float | None
    parks: str | None
    url: str
    parking: list[Entry] = field(default_factory=list)
    camping: list[Entry] = field(default_factory=list)
    description: list[Entry] = field(default_factory=list)
    notes: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "distance_miles": self.distance_miles,
            "parks": self.parks,
            "url": self.url,
            "parking": [vars(e) for e in self.parking],
            "camping": [vars(e) for e in self.camping],
            "description": [vars(e) for e in self.description],
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Section:
        return cls(
            number=data["number"],
            title=data["title"],
            distance_miles=data.get("distance_miles"),
            parks=data.get("parks"),
            url=data["url"],
            parking=[Entry(**e) for e in data.get("parking", [])],
            camping=[Entry(**e) for e in data.get("camping", [])],
            description=[Entry(**e) for e in data.get("description", [])],
            notes=data.get("notes", {}),
        )


# --- parsing ----------------------------------------------------------------


def strip_html(markup: str) -> str:
    """Tags out, entities in, horizontal whitespace flattened, newlines kept."""
    text = html_module.unescape(_TAG.sub(" ", markup))
    return "\n".join(_WHITESPACE.sub(" ", line).strip() for line in text.split("\n"))


def parse_index(markup: str) -> list[tuple[int, str]]:
    """The section pages the guide's own index links to, in page order.

    Numbers rather than names, because the layer's `LP_Section` is a number
    and this list is what the fetch walks. Raises on an index that links to
    nothing - a redesign that stops linking the sections must stop the
    fetch, not empty it.
    """
    seen: dict[int, str] = {}
    for number in _SECTION_LINK.findall(markup):
        n = int(number)
        seen.setdefault(n, f"https://www.nynjtc.org/lp-section-{n}/")
    if not seen:
        raise ValueError("The Long Path guide index links to no /lp-section-N/ pages - its layout has changed")
    return sorted(seen.items())


def _main(markup: str) -> str:
    body = re.search(r"<main.*?</main>", markup, re.DOTALL | re.IGNORECASE)
    return body.group(0) if body else markup


def _block_text(inner: str) -> str:
    """One block's HTML as text with the page's own line boundaries."""
    return strip_html(_LINE_BREAKS.sub("\n", _DROPPED.sub(" ", inner)))


def parse_entries(block_text: str) -> tuple[list[Entry], list[str]]:
    """Mile-marked entries and the lines that are not one.

    A line that opens with a mile starts an entry; a following line that does
    not is appended to it (the guide breaks long entries with <br>). Lines
    before the first mile are notes - "Ample parking along roads..." in
    section 40, "None." in most Camping blocks.
    """
    entries: list[Entry] = []
    notes: list[str] = []
    for line in block_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        match = _MILE_LINE.match(line)
        if match:
            entries.append(Entry(mile=float(match.group(1)), text=match.group(2).strip()))
        elif entries:
            entries[-1].text = f"{entries[-1].text} {line}".strip()
        else:
            notes.append(line)
    for entry in entries:
        _read_position(entry)
    return entries, notes


def _read_position(entry: Entry) -> None:
    coords = _COORDS.search(entry.text)
    if coords:
        lat, lon = float(coords.group(1)), float(coords.group(2))
        if LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]:
            entry.lat, entry.lon = lat, lon
        else:
            entry.coordinates_rejected = True
    entry.unlocated = bool(_UNLOCATED.search(entry.text))
    for pattern in _OFF_TRAIL:
        off = pattern.search(entry.text)
        if off:
            entry.off_trail_miles = float(off.group(1))
            break


def parse_section(markup: str, url: str, expected_number: int | None = None) -> Section:
    """One section page, or a ValueError naming what has changed about it."""
    main = _main(markup)
    h1 = _H1.search(main)
    heading = strip_html(h1.group(1)) if h1 else ""
    number_match = _SECTION_TITLE.search(heading)
    if not number_match:
        raise ValueError(f"{url}: no 'Section N' heading found (read {heading!r}) - the page layout has changed")
    number = int(number_match.group(1))
    if expected_number is not None and number != expected_number:
        raise ValueError(f"{url}: page says Section {number}, expected {expected_number}")

    h2 = _H2.search(main)
    title = strip_html(h2.group(1)) if h2 else ""

    header_text = strip_html(_LINE_BREAKS.sub("\n", main))
    distance_match = _DISTANCE.search(header_text)
    distance = float(distance_match.group(1)) if distance_match else None
    parks = None
    for line in header_text.split("\n"):
        parks_match = _PARKS.match(line.strip())
        if parks_match:
            parks = parks_match.group(1).strip() or None
            break

    blocks = {strip_html(name).strip(): inner for name, inner in _DETAILS.findall(main)}
    missing = [name for name in REQUIRED_BLOCKS if name not in blocks]
    if missing:
        raise ValueError(
            f"{url}: section {number} has no {missing} block(s) - found {sorted(blocks)}; the page layout has changed"
        )

    section = Section(number=number, title=title, distance_miles=distance, parks=parks, url=url)
    section.parking, section.notes["parking"] = parse_entries(_block_text(blocks["Parking"]))
    section.camping, section.notes["camping"] = parse_entries(_block_text(blocks["Camping"]))
    section.description, section.notes["description"] = parse_entries(_block_text(blocks["Detailed Trail Description"]))
    if not section.description:
        raise ValueError(f"{url}: section {number}'s trail description parsed to zero mile-marked entries")
    return section


# --- classification ---------------------------------------------------------


def is_water(text: str) -> bool:
    """The narrowest rule in the file - see the module docstring."""
    cleaned = _SEASON.sub(" ", _NOT_WATER.sub(" ", text))
    return bool(_WATER_PHRASE.search(cleaned) or _SPRING.search(cleaned))


def water_reliability(text: str) -> str | None:
    """ "reliable", "unreliable", or None when the guide does not say."""
    if _UNRELIABLE.search(text):
        return "unreliable"
    if _RELIABLE.search(text):
        return "reliable"
    return None


def classify(text: str) -> list[str]:
    """Every POI type this entry's text supports, in POI_TYPES order."""
    found: set[str] = set()
    if is_water(text):
        found.add("water")
    if _SHELTER.search(_NOT_A_SHELTER.sub(" ", text)):
        found.add("shelter")
    if _CAMPSITE.search(text):
        found.add("campsite")
    if _VIEWPOINT.search(text):
        found.add("viewpoint")
    if _PRIVY.search(text):
        found.add("privy")
    return [poi_type for poi_type in POI_TYPES if poi_type in found]


def classify_camping(text: str) -> list[str]:
    """A Camping-block entry is a campsite unless it says what else it is.

    The block's own heading is the evidence: an entry there with a mile is a
    place to sleep. One that names a lean-to is a shelter; one that also
    names a spring is water as well; one describing an AREA is nothing.
    """
    if _CAMPING_AREA.search(text):
        return [t for t in classify(text) if t != "campsite"]
    types = classify(text)
    if "shelter" not in types and "campsite" not in types:
        types.append("campsite")
    return [poi_type for poi_type in POI_TYPES if poi_type in types]


def place_name(text: str, poi_type: str) -> str | None:
    pattern = _NAMED_PLACES.get(poi_type)
    if pattern is None:
        return None
    match = pattern.search(text)
    if not match:
        return None
    name = _LEADING_VERB.sub("", match.group(1).strip()).strip()
    return name or None


def short_name(text: str) -> str | None:
    """A parking entry's own label: its text up to the first clause break.

    "Fort Lee Historic Park, just south of the bridge (metered parking)."
    -> "Fort Lee Historic Park". Capped, and dropped when what is left is not
    a name (a bare "Parking", or a sentence that starts with a verb) - the
    client's "Unnamed" is better than a fragment.
    """
    head = _CLAUSE_BREAK.split(_COORDS.sub("", text), maxsplit=1)[0].strip()
    if not head or len(head) > 60 or head.lower() in {"parking", "parking area", "parking lot"}:
        return None
    if re.match(
        r"^(?:turn|walk|continue|follow|take|reach|cross|the trail|it is|there is|there are|also)\b", head, re.IGNORECASE
    ):
        return None
    return head


# --- geometry ---------------------------------------------------------------


def haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Metres between two (lon, lat) points."""
    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _parts(geometry: dict) -> list[list[tuple[float, float]]]:
    kind = geometry.get("type")
    if kind == "LineString":
        return [[(float(x), float(y)) for x, y, *_ in geometry["coordinates"]]]
    if kind == "MultiLineString":
        return [[(float(x), float(y)) for x, y, *_ in part] for part in geometry["coordinates"]]
    raise ValueError(f"Long Path geometry must be a LineString or MultiLineString, got {kind!r}")


def chain_parts(parts: list[list[tuple[float, float]]], tolerance_m: float = CHAIN_TOLERANCE_M) -> list[tuple[float, float]]:
    """Every piece of one section, joined end to end into a single line.

    Greedy: start from any piece and extend either end with whichever
    unused piece begins or ends within `tolerance_m` of it, reversing the
    piece if it arrives backwards. Raises if a piece cannot be joined - a
    section in two disconnected halves is a layer this code has not seen,
    and walking a mile along the wrong half is the failure to stop.
    """
    if not parts:
        raise ValueError("no line parts to chain")
    remaining = [list(p) for p in parts if len(p) >= 2]
    chain = remaining.pop(0)
    while remaining:
        joined = False
        for index, part in enumerate(remaining):
            if haversine_m(chain[-1], part[0]) <= tolerance_m:
                chain.extend(part[1:])
            elif haversine_m(chain[-1], part[-1]) <= tolerance_m:
                chain.extend(reversed(part[:-1]))
            elif haversine_m(chain[0], part[-1]) <= tolerance_m:
                chain = part[:-1] + chain
            elif haversine_m(chain[0], part[0]) <= tolerance_m:
                chain = list(reversed(part[1:])) + chain
            else:
                continue
            remaining.pop(index)
            joined = True
            break
        if not joined:
            raise ValueError(f"{len(remaining)} line part(s) of a section do not connect to the rest within {tolerance_m} m")
    return chain


def line_length_m(line: list[tuple[float, float]]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(line, line[1:]))


def section_lines(features: list[dict]) -> dict[int, list[tuple[float, float]]]:
    """One oriented line per section, keyed by the layer's `LP_Section`.

    Orientation is the guide's: mile 0.00 of every section is its SOUTHERN
    end, because the guide walks New York City to the Adirondacks and
    restarts the count each section. The layer does not say which end is
    which - its segments run both ways, measured 2026-09-08 - so section 1
    is oriented by latitude (the George Washington Bridge is its southern
    end) and every later section by continuity: whichever end is nearer the
    previous section's end is its start. A section the chain cannot reach
    (no previous section in the features handed in) falls back to latitude.
    """
    by_section: dict[int, list[list[tuple[float, float]]]] = {}
    for feature in features:
        properties = feature.get("properties") or {}
        number = properties.get("LP_Section")
        if number is None:
            continue
        by_section.setdefault(int(number), []).extend(_parts(feature.get("geometry") or {}))

    oriented: dict[int, list[tuple[float, float]]] = {}
    previous_end: tuple[float, float] | None = None
    previous_number: int | None = None
    for number in sorted(by_section):
        line = chain_parts(by_section[number])
        if previous_end is not None and previous_number == number - 1:
            if haversine_m(line[-1], previous_end) < haversine_m(line[0], previous_end):
                line = list(reversed(line))
        elif line[0][1] > line[-1][1]:
            line = list(reversed(line))
        oriented[number] = line
        previous_end, previous_number = line[-1], number
    return oriented


def point_at_fraction(line: list[tuple[float, float]], fraction: float) -> tuple[float, float]:
    """The (lon, lat) `fraction` of the way along `line`, by geodesic length."""
    fraction = min(max(fraction, 0.0), 1.0)
    total = line_length_m(line)
    if total == 0:
        return line[0]
    target = fraction * total
    walked = 0.0
    for a, b in zip(line, line[1:]):
        step = haversine_m(a, b)
        if walked + step >= target and step > 0:
            t = (target - walked) / step
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        walked += step
    return line[-1]


def interpolate(line: list[tuple[float, float]], mile: float, section_miles: float) -> tuple[float, float]:
    """Where mile `mile` of a `section_miles`-long section falls on `line`.

    Scaled to the guide's stated distance rather than walked as raw metres:
    the layer's line is shorter than the section it draws on 37 of 40
    sections (generalised geometry), so 8.4 raw miles along a line that is
    7.55 miles long would run off its end. The measurement that chose this
    over raw metres is in spike_long_path_guide_placement.py.
    """
    if section_miles <= 0:
        raise ValueError("a section's stated distance must be positive to walk a mile along it")
    return point_at_fraction(line, mile / section_miles)


# --- records ----------------------------------------------------------------


def compose_description(section: Section, entry: Entry, poi_type: str, placement: str) -> str:
    """One sentence about the place, from facts the guide states - never its prose.

    Three shapes, and the difference between them is the thing a hiker most
    needs to know before walking to the pin:

      stated        NYNJTC gave coordinates; the pin is where they put it.
      interpolated  the pin is the guide's mile walked along the line, and
                    the sentence says so.
      off the trail the guide says the place is N miles OFF the Long Path.
                    The pin marks where the walker LEAVES the trail for it -
                    the guide's mile - and the sentence says that too,
                    because a shelter pin a mile from the shelter with no
                    words on it would be exactly the display outrunning its
                    source that CLAUDE.md forbids.
    """
    mile = f"{entry.mile:.2f}"
    label = {"water": "Water source"}.get(poi_type, poi_type.capitalize())
    where = f"mile {mile} of Long Path section {section.number}"
    if entry.off_trail_miles is not None and placement == "interpolated":
        sentence = (
            f"{label} about {entry.off_trail_miles:g} mi off the Long Path from {where}; "
            "the pin marks where the guide leaves the trail for it, not the place itself."
        )
    elif placement == "stated":
        sentence = f"{label} at {where}, located by NYNJTC's section guide."
        if entry.off_trail_miles is not None:
            sentence = f"{sentence} About {entry.off_trail_miles:g} mi off the Long Path."
    else:
        sentence = f"{label} at {where}; position estimated from the guide's mile marker, not surveyed."
    if poi_type == "water":
        reliability = water_reliability(entry.text)
        if reliability == "unreliable":
            sentence = f"{sentence} The guide calls it seasonal or undependable."
        elif reliability == "reliable":
            sentence = f"{sentence} The guide calls it reliable."
    return sentence


def _record(
    section: Section,
    entry: Entry,
    poi_type: str,
    block: str,
    ordinal: int,
    position: tuple[float, float],
    placement: str,
    name: str | None,
) -> dict:
    mile = f"{entry.mile:.2f}"
    description = compose_description(section, entry, poi_type, placement)
    record = {
        "id": f"{SOURCE_KEY}:s{section.number}-{block}-{mile}-{poi_type}-{ordinal}",
        "poi_type": poi_type,
        "trail_id": TRAIL_ID,
        "source": SOURCE_KEY,
        "source_feature_id": f"s{section.number}-{block}-{mile}-{ordinal}",
        "name": name,
        "lat": position[1],
        "lon": position[0],
        "confidence": CONFIDENCE_HIGH if placement == "stated" else CONFIDENCE_LOW,
        "description": description,
        "lp_section": section.number,
        "section_mile": entry.mile,
        "placement": placement,
        "source_url": section.url,
    }
    if placement == "interpolated":
        record["position_error_m"] = INTERPOLATION_ERROR_M
    if entry.off_trail_miles is not None:
        record["off_trail_miles"] = entry.off_trail_miles
    if poi_type == "water":
        reliability = water_reliability(entry.text)
        if reliability:
            record["water_reliability"] = reliability
    return record


#: Two records of one type closer than this are the same place said twice,
#: when both carry NYNJTC's own coordinates: the lot at the end of Big Hollow
#: Road is listed at the end of section 24 as (42.28932, -74.11610) and at
#: the start of section 25 as (42.28932, -74.11602), nine metres apart. Two
#: real lots closer than this would draw on top of each other anyway.
STATED_DUPLICATE_M = 100.0


def _normalised(name: str | None) -> str | None:
    """A name as a de-duplication key: case, punctuation and a leading "The"
    dropped, and the guide's three spellings of lean-to made one."""
    if not name:
        return None
    key = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    key = re.sub(r"^the\s+", "", key)
    return re.sub(r"\blean\s*to\b|\bleanto\b", "leanto", key)


def dedupe(records: list[dict]) -> tuple[list[dict], int]:
    """One record per place, where the guide says one place several times.

    It does, three ways, all measured on the forty pages (2026-09-08):

      - The Camping block lists Big Hill Shelter at 5.65, and the description
        mentions it at 4.65 ("last sure water before"), 5.45 ("climb up to")
        and 5.70 ("Arrive at"). One shelter, four miles.
      - The description and the Camping block both carry the same unnamed
        campsite at the same mile.
      - The lot at a section boundary is on both pages, with its coordinates.

    Preference, in order: a record from the Parking or Camping block over one
    from the description (those blocks are the guide's own list of the
    place); then the earliest in section-and-mile order. Keys: (type, name)
    where the record has a name; (section, type, mile to 0.05) where it does
    not; and, for stated coordinates, any earlier record of the type within
    STATED_DUPLICATE_M. Returns (kept, dropped_count).
    """
    ranked = sorted(
        enumerate(records),
        key=lambda pair: (0 if pair[1]["source_feature_id"].split("-")[1] in ("parking", "camping") else 1, pair[0]),
    )
    kept_by_index: dict[int, dict] = {}
    seen_names: set[tuple[str, str]] = set()
    seen_miles: set[tuple[int, str, float]] = set()
    stated: list[tuple[str, tuple[float, float]]] = []
    for index, record in ranked:
        poi_type = record["poi_type"]
        name = _normalised(record.get("name"))
        if name and (poi_type, name) in seen_names:
            continue
        mile_key = (record["lp_section"], poi_type, round(record["section_mile"] / 0.05) * 0.05)
        if not name and mile_key in seen_miles:
            continue
        if record["placement"] == "stated":
            here = (record["lon"], record["lat"])
            if any(t == poi_type and haversine_m(here, there) <= STATED_DUPLICATE_M for t, there in stated):
                continue
            stated.append((poi_type, here))
        if name:
            seen_names.add((poi_type, name))
        seen_miles.add(mile_key)
        kept_by_index[index] = record
    kept = [kept_by_index[i] for i in sorted(kept_by_index)]
    return kept, len(records) - len(kept)


def build_records(sections: list[Section], line_features: list[dict]) -> tuple[list[dict], dict]:
    """Unified POI records for every placeable entry, and a tally of the rest.

    Returns (records, stats). Every entry the guide carries ends up either as
    a record or as one of the counted reasons in stats["skipped"], so the
    run can say what it left out and why - the same shape
    export_nearby_poi.build_records reports.
    """
    lines = section_lines(line_features)
    records: list[dict] = []
    skipped: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_placement = {"stated": 0, "interpolated": 0}
    seen_ids: dict[str, int] = {}

    def skip(reason: str) -> None:
        skipped[reason] = skipped.get(reason, 0) + 1

    for section in sections:
        line = lines.get(section.number)
        for block, entries, classifier in (
            ("parking", section.parking, lambda text: ["parking"]),
            ("camping", section.camping, classify_camping),
            ("description", section.description, classify),
        ):
            for entry in entries:
                types = classifier(entry.text)
                if not types:
                    if block != "description":
                        skip(f"{block}: no place in the entry")
                    continue
                if entry.lat is not None and entry.lon is not None:
                    position, placement = (entry.lon, entry.lat), "stated"
                elif entry.coordinates_rejected:
                    skip("coordinates outside the Long Path's extent (a typo on the page)")
                    continue
                elif entry.unlocated:
                    skip("marked (unlocated) by NYNJTC")
                    continue
                elif line is None:
                    skip(f"section {section.number} has no line in the layer")
                    continue
                elif section.distance_miles is None:
                    skip(f"section {section.number} states no distance")
                    continue
                elif entry.mile > section.distance_miles + 0.05:
                    skip("mile past the section's stated distance")
                    continue
                else:
                    position, placement = interpolate(line, entry.mile, section.distance_miles), "interpolated"

                for poi_type in types:
                    name = short_name(entry.text) if block == "parking" else place_name(entry.text, poi_type)
                    base = f"s{section.number}-{block}-{entry.mile:.2f}-{poi_type}"
                    ordinal = seen_ids.get(base, 0)
                    seen_ids[base] = ordinal + 1
                    records.append(_record(section, entry, poi_type, block, ordinal, position, placement, name))
                    by_type[poi_type] = by_type.get(poi_type, 0) + 1
                by_placement[placement] += 1

    records, duplicates = dedupe(records)
    by_type = {}
    for record in records:
        by_type[record["poi_type"]] = by_type.get(record["poi_type"], 0) + 1
    stats = {
        "kept": len(records),
        "by_type": by_type,
        "duplicates_merged": duplicates,
        "entries_placed": by_placement,
        "skipped": dict(sorted(skipped.items(), key=lambda kv: -kv[1])),
        "sections": len(sections),
        "sections_with_a_line": sum(1 for s in sections if s.number in lines),
        "low_confidence": sum(1 for r in records if r["confidence"] == CONFIDENCE_LOW),
        "off_trail": sum(1 for r in records if "off_trail_miles" in r),
        "named": sum(1 for r in records if r.get("name")),
    }
    return records, stats
