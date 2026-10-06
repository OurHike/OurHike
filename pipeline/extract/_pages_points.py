"""Decision 54, wave 5, section S: the points a club publishes on its own web pages, read with a parser per site.

    page_points(key)   the points one club's page or pages publish, one row per point (a shelter, a water cache,
                       a trailhead, a parking area), as the parser registered for the key reads them

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 5: "web pages | none | a parser per
site". This is the section S half (points of interest, trail lines, places, elevation); the content types'
pages are section K's, in extract/_pages_content.py. It is a builder like the rest: it takes a sources.json
key, never a URL, so a club file cannot fetch a page the registry does not hold.

WHAT A ROW IS. One point the page publishes, with only the facts the site's parser reads: a name, a kind as the
page states it, numbers with their units, a mile, and the point as GeoJSON in `geometry` under rule 1's JSON
hint. Every row also carries `source_url`, the page a hiker reads it on, and, for a WordPress page read through
its REST route, `page_modified_gmt`, the page's own modified date. A page's body text lands nowhere (the round
brief, item 3, and decision 55): a parser names the facts it keeps and drops everything else, so a sentence of
the club's lands in no column. A point the page states no coordinate for lands with `geometry` null, never a
coordinate looked up from its name (the round brief: "Coordinates come from the page's own data, never geocoded
from a name"); a staging model reads a null geometry as no place to draw.

A PARSER REFUSES RATHER THAN RELABELS. Each parser is written against the page as it was read live on
2026-10-04, and raises PageLayoutChanged when the page no longer looks like that: no item where items were, an
item without the field its kind always had, a coordinate outside the range its own sign convention allows. A
refusal is a failed read, so the run leaves the table on its last committed rows (extract/_run.py), which is
the GATC water PDF's rule (extract/_kinds.py's ClubPdf; test_a_club_pdf_whose_layout_changed_refuses_rather_
than_relabelling) carried to pages.

THE CHANGE CHECK IS THE READ, and FRESH only when what would land hashes exactly as the last load's rows. The
pages measured send no validator of their own: WordPress REST answers carry none, and the HTML pages' Last-
Modified is the request time (mdhta.com, friendsoftheouachita.org, aztrail.org, read 2026-10-04), which is
extract/_notices.py's finding for decision 53's pages too. So a site-wide or request-time validator never
decides FRESH (the dlt skill, rule 4). The check's answer is kept for the read in the same run
(extract/_notices.py's _remember), so a page costs one request a run, not two.

ACCESS. Every request sends lib/user_agent.py's USER_AGENT through extract/_kinds.py's session() and passes
extract/_notices.py's per-host gate: DEFAULT_HOST_GAP_SECONDS after the last request to that host ended, or the
row's `crawl_delay` where the host's robots.txt asks for more. robots.txt is read when a row is registered
(decision 53, "Access is checked, never assumed"), and each row says what it read. A wall, a refusal or a
redirect to another host raises (extract/_notices.py's NoticeUnreadable): never an empty answer.

PERSON FIELDS never load (ELT.md, "Who may publish", rule 8). A parser's columns are an allowlist that names no
person, so a page's byline (FoOT's shelters page carries its editor's name above the list, read 2026-10-04) and
a list's compiler never reach a row.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests

from extract import _kinds, _notices
from extract._contract import Resource
from extract._pages_content import MAX_FACT_CHARS, single_miles
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry


class PageLayoutChanged(ValueError):
    """The page answered, and does not look the way its parser was written against: refused, never relabelled."""


# --- Coordinates ------------------------------------------------------------------------------------------------


def point(lat: float, lon: float, where: str) -> dict:
    """A GeoJSON Point from a latitude and a longitude in degrees, refused where either is out of range."""
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise PageLayoutChanged(f"{where}: ({lat}, {lon}) is not a latitude and longitude in degrees")
    return {"type": "Point", "coordinates": [round(lon, 7), round(lat, 7)]}


def ddm(degrees: str, minutes: str) -> float:
    """Degrees and decimal minutes ("34", "46.387") as decimal degrees, unsigned: the caller gives the hemisphere."""
    whole, part = float(degrees), float(minutes)
    if not (0 <= part < 60):
        raise PageLayoutChanged(f"{degrees} {minutes}: minutes outside 0 to 60")
    return whole + part / 60


def north_america(lat: float, lon: float, where: str) -> dict:
    """A point the page writes unsigned or signed, read as the northern and western hemisphere it must be in.

    Every page here is a United States trail's, and several write a longitude with no sign or no W (Foothills
    Trail's "83 05.880", read 2026-10-04). A latitude that is not north of the equator, or a longitude that is
    east of Greenwich once given its western sign, is not a misprint this code can repair, so it refuses.
    """
    lon = -abs(lon)
    if not (0 < lat < 72 and -180 < lon < -60):
        raise PageLayoutChanged(f"{where}: ({lat}, {lon}) is not a United States trail's point")
    return point(lat, lon, where)


# --- HTML, read as lines ------------------------------------------------------------------------------------------

BLOCK_TAGS = frozenset(
    {"p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}
)
SKIPPED_TAGS = frozenset({"script", "style", "noscript", "template"})


class _Lines(HTMLParser):
    """An HTML fragment's visible text as lines: a block tag ends a line, a script or a style is skipped."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self.current: list[str] = []
        self.skipping = 0

    def _end_line(self):
        text = " ".join("".join(self.current).split())
        if text:
            self.lines.append(text)
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIPPED_TAGS:
            self.skipping += 1
        elif tag in BLOCK_TAGS:
            self._end_line()

    def handle_endtag(self, tag):
        if tag in SKIPPED_TAGS:
            self.skipping = max(0, self.skipping - 1)
        elif tag in BLOCK_TAGS:
            self._end_line()

    def handle_data(self, data):
        if not self.skipping:
            self.current.append(data)

    def close(self):
        super().close()
        self._end_line()


def html_lines(fragment: str) -> list[str]:
    """The visible text of an HTML fragment, one line per block, whitespace folded."""
    parser = _Lines()
    parser.feed(fragment)
    parser.close()
    return parser.lines


def tag_attributes(fragment: str, tag: str) -> list[dict[str, str]]:
    """Every `<tag ...>` start tag's attributes, entities decoded, in document order."""
    found = []
    for match in re.finditer(rf"<{tag}\b([^>]*)>", fragment, re.IGNORECASE):
        attributes = {name.lower(): html.unescape(value) for name, value in re.findall(r'([\w:-]+)="([^"]*)"', match.group(1))}
        found.append(attributes)
    return found


def number(text: str | None) -> float | None:
    """A number written in a page (`1,000`, `9.4`), or None for none."""
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


# --- The parsers, one per site ------------------------------------------------------------------------------------

#: A parser takes the page's HTML (a WordPress REST answer's rendered content, or the page itself) and its URL,
#: and returns its rows, each a dict of facts with a `geometry`. It raises PageLayoutChanged on a page that no
#: longer looks the way it was written against.
Parser = Callable[[str, str], list[dict]]

PAGE_PARSERS: dict[str, Parser] = {}
#: The columns a parser writes that may be unknown on every row of a load, by key, with dlt's data type for each, so
#: the column exists whatever one read found (PagePoints.column_hints()).
PAGE_COLUMN_TYPES: dict[str, dict[str, str]] = {}


def _parser(key: str):
    def register(function: Parser) -> Parser:
        PAGE_PARSERS[key] = function
        return function

    return register


#: The kinds MDHTA's trail guide marks its points with (`data-type`, read 2026-10-04): 19 trailheads, 11
#: campgrounds, 8 waterboxes, 6 river crossings, 6 points of interest. A trail line's anchor carries a
#: `data-geojson` instead, which mdhta/trail_lines.py's mdhta_trail_guide reads; it has no point.
MDHTA_POINT_KINDS = frozenset({"trailheads", "campgrounds", "waterboxes", "river-crossings", "points-of-interest"})
#: The kinds a page with none of has stopped being the trail guide: the safety ones, which it has always had.
MDHTA_ALWAYS = frozenset({"trailheads", "campgrounds", "waterboxes"})


@_parser("mdhta_trail_guide_points")
def parse_mdhta_trail_guide(page: str, url: str) -> list[dict]:
    """The Maah Daah Hey Trail Association's trail guide: each `<a data-type data-lat data-long>` its map plots.

    The association's own map data, written into the page as attributes (read 2026-10-04: 50 points of 69
    anchors; the other 19 are trail lines). A point kind outside MDHTA_POINT_KINDS still lands, under its own
    `kind`, because a new kind is new data, not a relabelled column; an anchor of any kind that carries one
    coordinate and not the other, or one that is not a number, refuses the page.
    """
    rows = []
    for attributes in tag_attributes(page, "a"):
        kind = attributes.get("data-type")
        if not kind or ("data-lat" not in attributes and "data-long" not in attributes):
            continue
        where = f"{url} {attributes.get('data-slug')}"
        lat, lon = number(attributes.get("data-lat")), number(attributes.get("data-long"))
        if lat is None or lon is None:
            raise PageLayoutChanged(f"{where}: a {kind} anchor without both data-lat and data-long as numbers")
        rows.append(
            {
                "name": " ".join((attributes.get("data-title") or "").split()) or None,
                "kind": kind,
                "slug": attributes.get("data-slug"),
                "link": attributes.get("href"),
                "geometry": point(lat, lon, where),
            }
        )
    if not any(row["kind"] in MDHTA_ALWAYS for row in rows):
        raise PageLayoutChanged(f"{url}: no trailhead, campground or waterbox anchor, which the guide always had")
    return rows


#: FoOT's shelter list, one `<li>` each (read 2026-10-04, page 326's rendered content): "ROCK GARDEN – MM 9.4
#: N34 46.387 / W94 51.799" for the 12 with a fix, "JOHN ARCHER SHELTER at MM 122.6" for the 11 without, and
#: "BLACK FORK MOUNTAIN SHELTER – 57.8 N34 41.437 / W94 18.624" once with no MM.
FOOT_FIXED = re.compile(
    r"^(?P<name>.+?)\s+[–-]\s+(?:MM\s+)?(?P<mile>\d+(?:\.\d+)?)\s+N(?P<latd>\d{2})\s+(?P<latm>\d{1,2}\.\d+)\s*/\s*"
    r"W(?P<lond>\d{2,3})\s+(?P<lonm>\d{1,2}\.\d+)$"
)
FOOT_MILE_ONLY = re.compile(r"^(?P<name>.+?)\s+at\s+MM\s+(?P<mile>\d+(?:\.\d+)?)$")


@_parser("foot_trail_shelters")
def parse_foot_trail_shelters(page: str, url: str) -> list[dict]:
    """Friends of the Ouachita Trail's shelter list: a name, its Ouachita Trail mile marker, and a fix where given.

    The fixes are degrees and decimal minutes, N and W. The page names no datum (its water PDF says "Most fixes
    use NAD27 datum", which is that document's word, not this list's), so each fix is read as WGS84, where a
    NAD27 fix in Arkansas sits within a few tens of metres (Reasoned, @unvalidated: settled by comparing one
    shelter with a surveyed source). A `<li>` that is neither shape refuses the page, so a re-typed entry is
    never read as a different shelter.
    """
    start = page.find("<ul")
    end = page.find("</ul>", start)
    if start < 0 or end < 0:
        raise PageLayoutChanged(f"{url}: no list of shelters")
    rows = []
    for line in html_lines(page[start:end]):
        fixed, mile_only = FOOT_FIXED.match(line), FOOT_MILE_ONLY.match(line)
        if fixed:
            lat = ddm(fixed["latd"], fixed["latm"])
            lon = -ddm(fixed["lond"], fixed["lonm"])
            rows.append({"name": fixed["name"].strip(), "mile_marker": float(fixed["mile"]), "geometry": point(lat, lon, line)})
        elif mile_only:
            rows.append({"name": mile_only["name"].strip(), "mile_marker": float(mile_only["mile"]), "geometry": None})
        else:
            raise PageLayoutChanged(f"{url}: a shelter entry in neither measured shape: {line!r}")
    if not rows:
        raise PageLayoutChanged(f"{url}: the list holds no shelter")
    return rows


#: Each parking area on AMC Western Massachusetts' A.T. parking page (read 2026-10-04, dated 11-Jan-2025 on the
#: page) is an `<h3>` naming it, then a `<ul class="bullets02">` of facts. The coordinate is written
#: "Lat/Lon: 42.69936, -73.15358." on 24, "Lat.Lon:" on 1 (Mt Greylock Summit) and "Lon/Lat:" on 1 (Blotz Rd),
#: whose numbers are still latitude then longitude; the values' own signs place them, north and west.
AMC_COORDINATE = re.compile(r"^L(?:at|on)[./](?:Lon|Lat):\s*(?P<a>-?\d+\.\d+),\s*(?P<b>-?\d+\.\d+)\.?$")
AMC_CAPACITY = re.compile(r"^Capacity:?\s*(?:~\s*)?(?P<n>\d+)\s+vehicles\b")
#: The four overnight grades the page defines at its top, in its own words.
AMC_OVERNIGHT = (
    ("Suitable for overnight parking", "suitable"),
    ("Short term overnight use", "short_term"),
    ("Not recommended for overnight use", "not_recommended"),
    ("Day use only", "day_use_only"),
)
#: How the page states winter plowing, longest first so "Not plowed" is not read as "plowed".
AMC_PLOWING = (
    ("Not plowed in winter", "not_plowed"),
    ("Plowed to gate in winter", "plowed_to_gate"),
    ("Plowed in winter (mostly)", "plowed_mostly"),
    ("Plowed in winter, mostly", "plowed_mostly"),
    ("Plowed in winter", "plowed"),
)


def _amc_entries(page: str) -> list[tuple[str, list[str]]]:
    """Each `<h3>` heading's text and the top-level `<li>` texts of the list that follows it."""
    entries = []
    # A heading never spans another (Outlook Ave's has no list, and its <h3> runs straight into School St's).
    for match in re.finditer(r"(?is)<h3\b[^>]*>((?:(?!</?h3\b).)*)</h3>((?:(?!<h[23]\b).)*)", page):
        heading = " ".join(html_lines(match.group(1)))
        body = match.group(2)
        # A nested list is a day-use mention inside an entry (Mt Greylock's Gould Trail and Hairpin Turn), with no
        # coordinate of its own; only the entry's own items are its facts.
        depth, items, buffer = 0, [], []
        for token in re.split(r"(?i)(</?ul\b[^>]*>|</?li\b[^>]*>)", body):
            lowered = token.lower()
            if lowered.startswith("<ul"):
                depth += 1
            elif lowered.startswith("</ul"):
                depth -= 1
                if depth == 0:
                    break
            elif lowered.startswith("<li") and depth == 1:
                # School St's "Capacity: 20 vehicles (no campers)." is never closed: the next <li> ends it.
                text = " ".join(" ".join(html_lines("".join(buffer))).split())
                if text:
                    items.append(text)
                buffer = []
            elif lowered.startswith("</li") and depth == 1:
                text = " ".join(" ".join(html_lines("".join(buffer))).split())
                if text:
                    items.append(text)
                buffer = []
            elif depth == 1:
                buffer.append(token)
        entries.append((heading, items))
    return entries


@_parser("amc_wma_at_parking_points")
def parse_amc_berkshire_at_parking(page: str, url: str) -> list[dict]:
    """AMC Western Massachusetts' A.T. parking areas: name, capacity, overnight grade, winter plowing, kiosk, fee.

    Facts only, each from a fixed phrase the page uses; an item no phrase matches is the club's sentence and
    lands nowhere (Notch Rd's winter closure, the water-plant gates at Pattison Rd: a gap in the notes, never a
    guess). An entry with no coordinate lands with no geometry. An entry whose coordinate is neither north nor
    west, or that states two, refuses the page.
    """
    rows = []
    for heading, items in _amc_entries(page):
        name = heading.split(":", 1)[0].strip()
        if not name:
            raise PageLayoutChanged(f"{url}: a parking heading with no name: {heading!r}")
        row: dict = {
            "name": name,
            "capacity_vehicles": None,
            "overnight": None,
            "winter_plowing": None,
            "map_kiosk": None,
            "fee_required": None,
            "geometry": None,
        }
        coordinates = []
        for item in items:
            if found := AMC_COORDINATE.match(item):
                coordinates.append((float(found["a"]), float(found["b"])))
            elif found := AMC_CAPACITY.match(item):
                row["capacity_vehicles"] = int(found["n"])
            elif item.startswith("Map kiosk:"):
                answer = item.removeprefix("Map kiosk:").strip(" .").lower()
                row["map_kiosk"] = {"yes": True, "no": False}.get(answer)
            elif item.startswith("Fee required"):
                row["fee_required"] = True
            for phrase, grade in AMC_OVERNIGHT:
                if item.startswith(phrase):
                    row["overnight"] = grade
            for phrase, plowing in AMC_PLOWING:
                if item.startswith(phrase):
                    row["winter_plowing"] = plowing
                    break
        if "(fee)" in heading.lower():
            row["fee_required"] = True  # Benedict Pond's heading: "Parking at boat launch area (fee)."
        if len(coordinates) > 1:
            raise PageLayoutChanged(f"{url}: {name} states {len(coordinates)} coordinates")
        if coordinates:
            a, b = coordinates[0]
            lat, lon = (a, b) if a > 0 > b else (b, a) if b > 0 > a else (None, None)
            if lat is None:
                raise PageLayoutChanged(f"{url}: {name}'s coordinate ({a}, {b}) is not one north and one west value")
            row["geometry"] = north_america(lat, lon, f"{url} {name}")
        rows.append(row)
    if not any(row["geometry"] for row in rows):
        raise PageLayoutChanged(f"{url}: no parking area with a coordinate")
    return rows


#: The Foothills Trail Conservancy's "GPS Coordinates" table (page 603's rendered content, read 2026-10-04): a
#: row per access point, its name, then its latitude and longitude as degrees and decimal minutes with no
#: hemisphere ("34 51.807", "83 05.880").
FOOTHILLS_DDM = re.compile(r"^(?P<d>\d{2})\s+(?P<m>\d{1,2}\.\d+)$")


@_parser("foothills_gps_coordinates")
def parse_foothills_gps_coordinates(page: str, url: str) -> list[dict]:
    """The Foothills Trail's access points: name and fix, the fix read north and west (north_america())."""
    start = page.find("GPS Coordinates")
    table_start = page.find("<table", start)
    table_end = page.find("</table>", table_start)
    if start < 0 or table_start < 0 or table_end < 0:
        raise PageLayoutChanged(f"{url}: no GPS Coordinates table")
    rows = []
    for row_html in re.findall(r"(?is)<tr\b[^>]*>(.*?)</tr>", page[table_start:table_end]):
        cells = [" ".join(html_lines(cell)) for cell in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", row_html)]
        if len(cells) != 3:
            raise PageLayoutChanged(f"{url}: a coordinates row with {len(cells)} cells, not 3: {cells}")
        name, latitude, longitude = cells
        lat, lon = FOOTHILLS_DDM.match(latitude), FOOTHILLS_DDM.match(longitude)
        if not (name and lat and lon):
            raise PageLayoutChanged(f"{url}: a coordinates row in another shape: {cells}")
        rows.append({"name": name, "geometry": north_america(ddm(lat["d"], lat["m"]), ddm(lon["d"], lon["m"]), f"{url} {name}")})
    if not rows:
        raise PageLayoutChanged(f"{url}: the coordinates table holds no row")
    return rows


#: A BRBTC section page (blueridgebartram.org/trail/<section>/, read 2026-10-04): an `<h5>` "Section 2", an `<h1>`
#: of two `<span>`s, from and to, a "Length" `<h4>` and its figure ("9.3 miles" on 11 of 13 pages, a bare "10.8" on
#: Hale Ridge Road's and Jones Gap's), and the section's starting trailhead as an `<h4>` name over a `<p>` fix in
#: decimal degrees, "34.8671, -83.2523".
#: The `<h5>` read is the one straight above the `<h1>`: the site's menu lists "Section 1" in an `<h5>` too.
BRBTC_SECTION = re.compile(r"(?is)<h5[^>]*>\s*Section\s+(?P<section>\d+[A-Za-z]?)\s*</h5>\s*<h1[^>]*>(?P<title>.*?)</h1>")
BRBTC_LENGTH = re.compile(r"(?is)<h4[^>]*>\s*Length\s*</h4>\s*(?P<miles>\d+(?:\.\d+)?)(?:\s*miles)?\s*<")
BRBTC_TRAILHEAD = re.compile(r"(?s)<h4>(?P<name>[^<]+)</h4>\s*<p>\s*(?P<lat>-?\d+\.\d+),\s*(?P<lon>-?\d+\.\d+)\s*</p>")


@_parser("brbtc_section_trailheads")
def parse_brbtc_section(page: str, url: str) -> list[dict]:
    """One Bartram Trail section page: its number, its name, its length in miles and its starting trailhead's fix.

    The page's length is read as miles where it states no unit, as it does on 2 of 13, because the other 11 say
    "miles" (Reasoned). The section's prose (camping, water, the road to the trailhead) lands nowhere, among it
    Sandy Ford's "it is now posted Private Property and not advised" about the old parking at Dicks Creek. A page
    that states no section number, or not exactly one trailhead fix, refuses.
    """
    section = BRBTC_SECTION.search(page)
    trailheads = list(BRBTC_TRAILHEAD.finditer(page))
    if section is None or len(trailheads) != 1:
        raise PageLayoutChanged(
            f"{url}: a section page states its Section number, its title and one trailhead fix ({len(trailheads)} found)"
        )
    length = BRBTC_LENGTH.search(page)
    name = " ".join(html.unescape(trailheads[0]["name"]).split())
    return [
        {
            "section": section["section"],
            "section_name": " ".join(" ".join(html_lines(section["title"])).split()),
            "length_miles": float(length["miles"]) if length else None,
            "name": name,
            "geometry": point(float(trailheads[0]["lat"]), float(trailheads[0]["lon"]), f"{url} {name}"),
        }
    ]


#: A Palmetto Trail passage page (www.palmettotrail.org/trails/trail/<passage>, read 2026-10-04) draws its map from
#: calls in its own script: `trailPage.helper.addMarker(lat, lon, 'Parking', '', [])` for each typed marker (363 on
#: the 33 pages: Parking 72, Trail Head 52, Information Sign 40, Point of Interest 39, Camping 34, Water Launch 19
#: and 15 other types, 14 of them typed 'NULL'), and `trailPage.helper.addSegment('Palmetto Trail', [{"lng": "...",
#: "lat": "..."}, ...], [])` for the passage's line, one a page. The `<h1>` names the passage.
PALMETTO_MARKER = re.compile(
    r"trailPage\.helper\.addMarker\(\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)\s*,\s*'(?P<type>(?:[^'\\]|\\.)*)'"
    r"\s*,\s*'(?P<label>(?:[^'\\]|\\.)*)'\s*,\s*\[[^\]]*\]\s*\)"
)
PALMETTO_SEGMENT = re.compile(
    r"(?s)trailPage\.helper\.addSegment\(\s*'(?P<name>(?:[^'\\]|\\.)*)'\s*,\s*(?P<points>\[\{.*?\}\])\s*,\s*\[[^\]]*\]\s*\)"
)
PALMETTO_CALL = re.compile(r"trailPage\.helper\.(addMarker|addSegment)\(")
#: The same page's facts, read in the same fetch for not_available.toml [palmetto.suggested_hikes], which SHARES this table (the lead's
#: ruling of 2026-10-04: one reader of the 33 passage pages). Under the title, div.Trail-meta holds
#: span.Trail-length ('7.1 miles', with an icon before it) and span.Trail-difficulty ('Easy'); then div.Trail-detailGrid
#: pairs each div.Trail-detailGridHeading ('Camping Allowed') with the div.Trail-detailGridData after it, whose first
#: line is the answer ('Depends') and whose lines after a <br> are the foundation's explanation, which is not read.
PALMETTO_LENGTH = re.compile(r'(?is)<span class="[^"]*\bTrail-length\b[^"]*">(?P<text>.*?)</span>')
PALMETTO_DIFFICULTY = re.compile(r'(?is)<span class="[^"]*\bTrail-difficulty\b[^"]*">(?P<text>.*?)</span>')
PALMETTO_GRID = re.compile(
    r'(?is)<div class="Trail-detailGridHeading">(?P<label>.*?)</div>\s*<div class="Trail-detailGridData">(?P<data>.*?)</div>'
)
#: The grid's labels read, each to the column it lands in; Activities, Offline Map and Printable Maps are not read.
PALMETTO_FACTS = {
    "Region": "region",
    "Surface": "surface",
    "Pets": "pets",
    "Fees": "fees",
    "Camping Allowed": "camping",
    "Trail on Hunting Grounds": "hunting_grounds",
}
#: Every fact column a passage's rows carry, with its type, so each exists on a load where every value is unknown.
PALMETTO_FACT_COLUMNS = {
    "length_miles": "double",
    "length_text": "text",
    "difficulty": "text",
    **{name: "text" for name in PALMETTO_FACTS.values()},
}
PAGE_COLUMN_TYPES["palmetto_trail_passages"] = PALMETTO_FACT_COLUMNS


def _palmetto_first_line(fragment: str, url: str, what: str) -> str | None:
    """A fragment's first visible line, or None for none; a line longer than a fact refuses (it caught prose)."""
    lines = html_lines(fragment)
    if not lines:
        return None
    if len(lines[0]) > MAX_FACT_CHARS:
        raise PageLayoutChanged(f"{url}: {what} is {len(lines[0])} characters, prose rather than a fact")
    return lines[0]


def palmetto_passage_facts(page: str, url: str) -> dict:
    """The passage's length (its text, and its miles where the text states one figure), difficulty and the grid's
    first-line answers. A page whose grid answers none of PALMETTO_FACTS' labels refuses: all 33 answered at least
    Region on 2026-10-04, so a page with none no longer looks the way this was written against."""
    length = PALMETTO_LENGTH.search(page)
    difficulty = PALMETTO_DIFFICULTY.search(page)
    length_text = _palmetto_first_line(length["text"], url, "the length") if length else None
    facts = {name: None for name in PALMETTO_FACT_COLUMNS}
    found = 0
    for pair in PALMETTO_GRID.finditer(page):
        label = " ".join(html_lines(pair["label"]))
        if label in PALMETTO_FACTS:
            facts[PALMETTO_FACTS[label]] = _palmetto_first_line(pair["data"], url, label)
            found += 1
    if not found:
        raise PageLayoutChanged(f"{url}: a passage page whose fact grid answers none of {sorted(PALMETTO_FACTS)}")
    miles, _ = single_miles(length_text)
    facts.update(
        {
            "length_miles": miles,
            "length_text": length_text,
            "difficulty": _palmetto_first_line(difficulty["text"], url, "the difficulty") if difficulty else None,
        }
    )
    return facts


@_parser("palmetto_trail_passages")
def parse_palmetto_passage(page: str, url: str) -> list[dict]:
    """One Palmetto Trail passage: each marker its map plots, typed as the page types it, and the passage's line.

    A marker row is `kind` 'marker' with the page's own `marker_type` and a Point; a line row is `kind` 'segment'
    with the segment's own name and a LineString, which not_available.toml [palmetto.trail_lines]'s SHARES reads (one page, one
    resource). A 'NULL' marker type lands as the page writes it, untyped: no type is guessed for it. Every call the
    page makes must parse, so a page whose script changed shape refuses rather than landing the calls that still
    happen to match.

    Every row also carries the page's facts (palmetto_passage_facts()), alike on each row of one page, for
    not_available.toml [palmetto.suggested_hikes]: a page always yields its line's row, so no page's facts are lost with its markers.
    """
    title = re.search(r"(?is)<h1[^>]*>(?P<title>.*?)</h1>", page)
    if title is None:
        raise PageLayoutChanged(f"{url}: a passage page with no <h1>")
    passage = " ".join(" ".join(html_lines(title["title"])).split())
    calls = PALMETTO_CALL.findall(page)
    markers, segments = list(PALMETTO_MARKER.finditer(page)), list(PALMETTO_SEGMENT.finditer(page))
    if len(markers) != calls.count("addMarker") or len(segments) != calls.count("addSegment") or not segments:
        raise PageLayoutChanged(
            f"{url}: {calls.count('addMarker')} addMarker and {calls.count('addSegment')} addSegment calls, of which "
            f"{len(markers)} and {len(segments)} parse"
        )
    rows = [
        {
            "passage": passage,
            "kind": "marker",
            "marker_type": found["type"].replace("\\'", "'"),
            "name": None,
            "geometry": point(float(found["lat"]), float(found["lon"]), f"{url} marker"),
        }
        for found in markers
    ]
    for found in segments:
        try:
            vertices = [[float(vertex["lng"]), float(vertex["lat"])] for vertex in json.loads(found["points"])]
        except (ValueError, KeyError, TypeError) as error:
            raise PageLayoutChanged(f"{url}: a segment whose vertices are not lng/lat pairs") from error
        if len(vertices) < 2:
            raise PageLayoutChanged(f"{url}: a segment with {len(vertices)} vertex")
        point(vertices[0][1], vertices[0][0], f"{url} segment")  # the first vertex in range, as GisFile checks
        rows.append(
            {
                "passage": passage,
                "kind": "segment",
                "marker_type": None,
                "name": found["name"].replace("\\'", "'"),
                "geometry": {"type": "LineString", "coordinates": vertices},
            }
        )
    facts = palmetto_passage_facts(page, url)
    return [{**row, **facts} for row in rows]


#: OHTA's trail page (WordPress page 15, read 2026-10-04, modified 2026-09-10): a "Major trail heads" `<h4>` and
#: `<ul>` under each segment's heading (Boston Mountains, Buffalo River, Sylamore, Norfork Lake), each `<li>`
#: "Name (mile N): lat, lon" with the mile left out on Norfork Lake's and the two Lower Buffalo Wilderness
#: accesses, and a lead before the fix on some: "Parking at", "Parking area at", "Park at", "approximately". What
#: follows the fix ("The river level here can be too high to cross after big rains.") is the club's sentence.
OHTA_LIST = re.compile(r"(?is)<h4[^>]*>\s*Major trail heads\s*</h4>\s*<ul[^>]*>(?P<items>.*?)</ul>")
OHTA_SEGMENT = re.compile(r"(?is)<h[23][^>]*>(?P<segment>.*?)</h[23]>")
OHTA_ITEM = re.compile(
    r"^(?P<name>.+?)(?:\s*\(mile\s+(?P<mile>\d+(?:\.\d+)?)\))?:\s*"
    r"(?P<lead>Parking area at|Parking at|Park at|approximately)?\s*(?P<lat>\d{2}\.\d+),\s*(?P<lon>-\d{2,3}\.\d+)"
)
#: What a lead says about the fix: where the car goes, or that the club calls the fix approximate.
OHTA_LEADS = {"Parking area at": "parking", "Parking at": "parking", "Park at": "parking", "approximately": "approximate"}


@_parser("ohta_major_trailheads")
def parse_ohta_major_trailheads(page: str, url: str) -> list[dict]:
    """The Ozark Highlands Trail's major trailheads, segment by segment: name, mile where given, and the fix.

    A trailhead at a segment's end is listed under both segments (Woolum Ford, Spring Creek, Matney Knob), once
    a segment, and lands once a segment, as the page lists it. `fix_note` says what the page's lead says of the
    fix ("parking", "approximate"), and is null where it says nothing. A list item in another shape refuses.
    """
    rows = []
    for found in OHTA_LIST.finditer(page):
        headings = OHTA_SEGMENT.findall(page[: found.start()])
        if not headings:
            raise PageLayoutChanged(f"{url}: a trailhead list under no segment heading")
        segment = " ".join(" ".join(html_lines(headings[-1])).split())
        for item in re.findall(r"(?is)<li[^>]*>(.*?)</li>", found["items"]):
            text = " ".join(" ".join(html_lines(item)).split())
            entry = OHTA_ITEM.match(text)
            if entry is None:
                raise PageLayoutChanged(f"{url}: a trailhead entry in no measured shape: {text!r}")
            rows.append(
                {
                    "segment": segment,
                    "name": entry["name"].strip(),
                    "mile": float(entry["mile"]) if entry["mile"] else None,
                    "fix_note": OHTA_LEADS.get(entry["lead"] or ""),
                    "geometry": north_america(float(entry["lat"]), float(entry["lon"]), f"{url} {entry['name']}"),
                }
            )
    if not rows:
        raise PageLayoutChanged(f"{url}: no Major trail heads list")
    return rows


#: hikethetuscarora.org's section pages (PATC's Tuscarora Trail site on Wix, seven pages of 22 sections, read
#: 2026-10-04): each section opens with a "Section N: Name" paragraph (section 8's has no colon), and its
#: "Access:" and "Camping:" paragraphs give points as "<label> (lat, lon)", three or four decimals. The labels are
#: the club's own and take several shapes, each measured: "Waggoners Gap: Parking at Audubon Hawk Watch", "Limited
#: parking at Cowpens Road", "US Route 50, limited shoulder parking", "No direct access to southern terminus, but
#: can be accessed from the Lucas Woods side trail with road access at WV 23/2". A Camping paragraph lists several,
#: a comma apart, with names that have no fix among them ("Col. Denning State Park"), and once a group ("Sleepy
#: Creek WMA campgrounds; Lower (...), Middle (...), Upper (...)"). Two fixes are written oddly and read as the
#: numbers they state: "Wagon Wheel Shelter,(40.267,-77.414)" and "(39.633), -78.109)".
TUSCARORA_SECTION = re.compile(r"^Section\s+(?P<section>\d+)(?!\s*-\s*\d)\s*:?\s*(?P<name>[A-Z].*)$")
TUSCARORA_BLOCK = re.compile(r"^(?P<block>Access|Advisory|Camping|Highlights|Links)\s*:?", re.IGNORECASE)
#: A paragraph's own heading before its first item ("Camping: Charlie Irvin Shelter (...)"), cut from that label.
TUSCARORA_LEAD = re.compile(r"^(?:Access|Camping)\s*:\s*", re.IGNORECASE)
TUSCARORA_FIX = re.compile(r"\(\s*(?:(?P<lead>[^()@]*)@\s*)?(?P<lat>\d{2}\.\d+)\s*\)?\s*,\s*(?P<lon>-\d{2,3}\.\d+)\s*\)")
TUSCARORA_NO_DIRECT = re.compile(
    r"^No direct access to (?:the )?(?:northern|southern) terminus, but can be accessed from the "
    r"(?P<via>.+?) with road access at (?P<road>.+)$"
)
TUSCARORA_PARKING_LEAD = re.compile(r"^(?:very\s+)?(?:limited\s+)?(?:shoulder\s+)?parking\s+(?:at|on)\s+", re.IGNORECASE)
TUSCARORA_PARKING_TAIL = re.compile(r",\s*(?:very\s+)?limited\s+shoulder\s+parking$", re.IGNORECASE)
#: A distance the page gives beside a fix: "(0.2 mi NB on AT @ ...)" before it, ", 0.3 mi SB on Cedar Creek Trail
#: ..." after it. Only the number is kept: how far the point sits from the Tuscarora itself.
TUSCARORA_MILES = re.compile(r"^\s*,?\s*(?P<mi>\d+(?:\.\d+)?)\s*mi\b")


def _tuscarora_access(label: str) -> tuple[str, str | None]:
    """An Access label's name and what it says of parking ("limited", "stated", or None for nothing said)."""
    parking = "limited" if re.search(r"\blimited\b", label, re.IGNORECASE) else None
    parking = parking or ("stated" if re.search(r"\bparking\b", label, re.IGNORECASE) else None)
    if found := TUSCARORA_NO_DIRECT.match(label):
        return found["road"].strip(" .,"), parking
    if ":" in label:
        return label.split(":", 1)[0].strip(" .,"), parking
    name = TUSCARORA_PARKING_TAIL.sub("", TUSCARORA_PARKING_LEAD.sub("", label)).strip(" .,")
    return name, parking


@_parser("patc_tuscarora_points")
def parse_patc_tuscarora_points(page: str, url: str) -> list[dict]:
    """The Tuscarora Trail's access points and camping, section by section, each with its fix.

    `kind` is the paragraph a point is listed in: "access" under Access, and under Camping "shelter" where the
    page's own name for it carries the word Shelter, else "camping" (a campground, a campsite, a hiker camp).
    `name` is the label before the fix: an Access label's place before its colon, or the road it names with a
    parking lead cut off; a Camping item's name as listed, with a group's heading before the item that opens the
    group and each one-word item after it ("Sleepy Creek WMA campgrounds; Lower", then "...; Middle"), never
    before a name of its own (a shelter listed after the group stays itself). `parking` says what an Access label says of parking, and `approach_mi` the distance
    the page gives beside a fix. A point listed under two sections lands once a section, as the page lists it.
    An item with no fix is not landed (a name only, which the module docstring never geocodes), and so is
    every sentence around the fixes. A fix outside Access and Camping, or two on one Access line, refuses.
    """
    rows, section, section_name, block = [], None, None, None
    for line in html_lines(page):
        line = " ".join(line.replace("\u200b", " ").split())
        if not line:
            continue
        if heading := TUSCARORA_SECTION.match(line):
            section, section_name, block = int(heading["section"]), heading["name"].strip(), None
            continue
        if opened := TUSCARORA_BLOCK.match(line):
            block = opened["block"].title()
        fixes = list(TUSCARORA_FIX.finditer(line))
        if not fixes:
            continue
        if section is None or block not in ("Access", "Camping"):
            raise PageLayoutChanged(f"{url}: a fix outside a section's Access or Camping paragraph: {line!r}")
        if block == "Access" and len(fixes) > 1:
            raise PageLayoutChanged(f"{url}: section {section}: an Access line with {len(fixes)} fixes: {line!r}")
        start, group = 0, None
        for fix in fixes:
            label = line[start : fix.start()]
            start = fix.end()
            label = TUSCARORA_LEAD.sub("", label.strip(" ,.;"), count=1).strip(" ,.;")
            if block == "Camping":
                label = label.rsplit(",", 1)[-1].strip()
                if ";" in label:
                    group, label = (part.strip() for part in label.split(";", 1))
                    name = f"{group}; {label}"
                elif group and " " not in label:
                    name = f"{group}; {label}"
                else:
                    group, name = None, label
                kind = "shelter" if re.search(r"\bShelter\b", label) else "camping"
                parking = None
            else:
                name, parking = _tuscarora_access(label)
                kind = "access"
            if not name:
                raise PageLayoutChanged(f"{url}: section {section}: a fix with no label: {line!r}")
            near = TUSCARORA_MILES.match(fix["lead"] or "") or TUSCARORA_MILES.match(line[fix.end() :])
            where = f"{url} section {section} {name}"
            rows.append(
                {
                    "section": section,
                    "section_name": section_name,
                    "kind": kind,
                    "name": name,
                    "parking": parking,
                    "approach_mi": float(near["mi"]) if near else None,
                    "geometry": north_america(float(fix["lat"]), float(fix["lon"]), where),
                }
            )
    if not rows:
        raise PageLayoutChanged(f"{url}: no section with an Access or Camping fix")
    return rows


# --- The resource -------------------------------------------------------------------------------------------------

WP_ROUTE = "/wp-json/wp/v2/"


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


@dataclass(frozen=True)
class PagePoints(Resource):
    """A club's page, or pages, read for the points it publishes: one row per point (the module docstring)."""

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def pages(self) -> tuple[tuple[str, str], ...]:
        """(what is asked, the page a hiker reads it on) for each page: the row's `pages`, or its `read_url` and `url`.

        A WordPress page is asked through its REST route (`read_url`, `/wp-json/wp/v2/pages/<id>`, no query
        string, which foothillstrail.org's `Disallow: /*?` leaves allowed), and its rows link the page itself.
        A row with a `sitemap` lists its pages there instead (_page_list()).
        """
        entry = self.entry
        if entry.get("pages"):
            return tuple((page, page) for page in entry["pages"])
        return ((entry.get("read_url") or entry["url"], entry["url"]),)

    def _page_list(self, http: requests.Session) -> list[tuple[str, str]]:
        """The pages this run reads: the sitemap's <loc>s under the row's `page_prefix`, where the row names a
        `sitemap` (BRBTC's 13 trail sections, read 2026-10-04), so a section the club adds is read without a
        registry edit; else `pages`. A sitemap that lists none under the prefix refuses, and so does one that
        lists a page on another host, whose robots.txt nobody read for this row."""
        entry = self.entry
        if not entry.get("sitemap"):
            return list(self.pages)
        sitemap = self._get(http, entry["sitemap"])
        listed = [html.unescape(loc) for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap.text)]
        prefix = entry.get("page_prefix") or ""
        pages = [loc for loc in listed if loc.startswith(prefix)]
        if not pages:
            raise PageLayoutChanged(f"{self.key}: {entry['sitemap']} lists no page under {prefix!r}")
        for page in pages:
            if not _notices.same_site(entry["sitemap"], page) or urlparse(page).scheme != "https":
                raise PageLayoutChanged(f"{self.key}: the sitemap lists {page}, not an https page on its own host")
        return [(page, page) for page in pages]

    @property
    def part(self) -> str:
        """ "points": a page another row also registers for something else (MDHTA's trail guide, whose lines
        mdhta_trail_guide reads from the GeoJSON files it links) is two datasets, not one read twice."""
        return "points"

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def crawl_delay(self) -> float:
        return max(_notices.DEFAULT_HOST_GAP_SECONDS, float(self.entry.get("crawl_delay") or 0))

    def column_hints(self) -> dict:
        extra = {name: {"data_type": type_} for name, type_ in PAGE_COLUMN_TYPES.get(self.key, {}).items()}
        return {"geometry": {"data_type": "json"}, "source_url": {"data_type": "text"}, **extra}

    def _get(self, http: requests.Session, url: str) -> requests.Response:
        """One guarded GET: a wall, another host or a status that is not a page raises NoticeUnreadable."""
        try:
            response = request_with_retry(
                url, session=http, timeout=60, retryable_statuses=_notices.RETRYABLE_STATUSES, label=f"{self.key} {url}"
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            raise _notices.NoticeUnreadable(f"{self.key}: {url} answered HTTP {status}") from error
        if reason := _notices.wall(response):
            raise _notices.NoticeUnreadable(f"{self.key}: {url} answered with a challenge ({reason}); not solved")
        if not _notices.same_site(url, response.url):
            raise _notices.NoticeUnreadable(f"{self.key}: {url} now redirects to {response.url}, another host")
        if response.status_code != 200:
            raise _notices.NoticeUnreadable(f"{self.key}: {url} answered HTTP {response.status_code}")
        return response

    def _read(self) -> list[dict]:
        """Every page asked and parsed: the rows, each with its page's link and, through REST, its modified date."""
        parse = PAGE_PARSERS[self.key]
        http = _notices.polite(_kinds.session(), self.crawl_delay)
        rows = []
        for asked, link in self._page_list(http):
            response = self._get(http, asked)
            modified = None
            if WP_ROUTE in urlparse(asked).path + "/":
                try:
                    document = response.json()
                    page, modified = document["content"]["rendered"], document.get("modified_gmt")
                except (ValueError, KeyError, TypeError) as error:
                    raise PageLayoutChanged(f"{self.key}: {asked} is not a WordPress page's REST answer") from error
            else:
                if "html" not in (response.headers.get("Content-Type") or "").lower():
                    raise PageLayoutChanged(f"{self.key}: {asked} answered {response.headers.get('Content-Type')!r}, not HTML")
                page = response.text
            for row in parse(page, link):
                rows.append({**row, "source_url": link, **({"page_modified_gmt": modified} if modified else {})})
        if not rows and not self.may_be_empty:
            raise PageLayoutChanged(f"{self.key}: the pages read hold no point")
        return rows

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """The read itself, and FRESH only when its rows hash as the last load's (the module docstring)."""
        _notices._forget(self.table)
        try:
            rows = self._read()
        except Exception as error:  # noqa: BLE001 - a check that errors is UNKNOWN (ELT.md); the read raises it again
            _notices._remember(self.table, error)
            print(f"  {self.key}: change check failed ({error}); reading it")
            return Freshness.UNKNOWN, None
        _notices._remember(self.table, rows)
        marker = {"rows": len(rows), "sha256": hashlib.sha256(_canonical({"rows": rows}).encode("utf-8")).hexdigest()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        kept = _notices._recall(self.table)
        if isinstance(kept, BaseException):
            raise kept
        rows = kept if kept is not None else self._read()
        proofs[self.table] = len(rows)
        print(f"  {self.key}: {len(rows)} points from {len({row['source_url'] for row in rows})} page(s)")
        yield from (dict(row) for row in rows)


def page_points(key: str, **overrides) -> PagePoints:
    entry = _kinds.registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    if key not in PAGE_PARSERS:
        raise KeyError(f"{key}: extract/_pages_points.py's PAGE_PARSERS has no parser for it")
    for url in [entry["url"], entry.get("read_url"), entry.get("sitemap"), *(entry.get("pages") or [])]:
        if url is not None and urlparse(url).scheme != "https":
            raise KeyError(f"{key}: {url} is not an https URL")
        if url is not None and urlparse(url).query and (refused := _notices.query_refused(url)):
            raise KeyError(f"{key}: {refused}")
    return PagePoints(key=key, **overrides)
