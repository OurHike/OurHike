"""Reading the NYNJTC Hike Finder export - 385 hike pages at
heardimmunity.org/hikefinder - into facts a route can be built from (#1427).

This module owns one job: **turn one exported page into facts**. It owns
nothing about the network (`fetch_hikefinder.py`), nothing about where a
route goes on the ground (`lib/hike_route_builder.py`), and nothing about
whether any of it may be published (sources.json's `hike_finder_licence`).
That split is `lib/nynjtc_hikes.py`'s and is kept for its reason: the parse
is tested here without a network, and the policy without one.

WHY THIS REPLACES THE SCRAPE. `lib/nynjtc_hikes.py` reads nynjtc.org's
WordPress API and reaches 20 hikes of 59, because NYNJTC's own password gate
withholds the other 39. The maintainer has the full list as this export, and
the instruction of 2026-09-15 was to load it and stop scraping. The export is
a superset in both directions: more hikes, and a GPX track that nynjtc.org
never published at all - `route_nynjtc_hikes.py` records the maintainer
confirming "there is none to find".

WHAT A PAGE IS, measured against the live export on 2026-09-15 (385 pages
linked from `hikes.php`, which prints "Results (385 hikes found)"; ids run
1-450 with gaps, so the id is not a count):

    GET hike.php?id=<id>

Every page carries the same TWELVE labelled fields, in one shape -
`<strong>Label:</strong> value` - and all twelve appeared on all 160 pages of
the first sample. They are read by label rather than by position, so a page
that reorders them still parses:

    Length  Difficulty  Estimated Time  Route Type  Dogs  Park
    Region  Author  GPS Coordinates  Features  Publish Date  Last Updated

Around them sit free-text cards, each a `<h2>` header over a `card-body`:
Summary (158/160), Directions to Trailhead (158/160), Description (160/160),
Public Transportation (53/160), Parking Location (130/160), and on the routed
pages only, Route Map and Elevation Profile (30/160 each).

THE FEATURES ARE THE TAGS, and they are the reason this parse keeps
everything. The maintainer's instruction was explicit - "keep ALL the data
from these, especially the tags" - and the Features badges are the facets
#1284's Find-a-hike screen filters on. They are carried as published, in
page order, with no mapping onto a vocabulary of this build's own: a badge
that reads "Wildflowers" ships as "Wildflowers".

THE TWO KINDS OF PAGE, and the whole reason `route_hikefinder.py` exists:

  A ROUTED PAGE draws a Route Map and an Elevation Profile, and offers
  `download_gpx.php?id=<id>`, which answers `application/gpx+xml`. That track
  IS the route - 943 points on id 50, every one carrying `<ele>` in metres
  (315.08 m on the first, which the page's own `elevationData` array repeats
  as 1033.727 ft, so the page is derived and the GPX is the source). 30 of
  the first 160 pages sampled were routed.

  AN UNROUTED PAGE publishes one coordinate - the parking - and a
  turn-by-turn description somebody walked. Nothing on it places a line.
  `lib/hike_route_builder.py` is the attempt to form one; this module's job
  stops at saying, in `has_published_route`, which kind of page this was.

WHAT IS DELIBERATELY NOT READ. The `pdf.php` print view, which is the same
facts typeset. The `admin/` pages. The page's `elevationData` and
`routeCoordinates` arrays: both are the GPX rendered into JavaScript, and
reading the GPX instead means the track arrives with its own elevations
rather than through a unit conversion this build would have to undo.
"""

from __future__ import annotations

import html as html_module
import math
import re
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field

#: The registry key this source's records are namespaced by, matching its
#: `sources.json` entry.
SOURCE_KEY = "nynjtc_hike_finder"

#: The export's own paths, relative to the source URL in sources.json.
LISTING_PATH = "hikes.php"
DETAIL_PATH = "hike.php?id={id}"
GPX_PATH = "download_gpx.php?id={id}"

#: The twelve labels every page carries. Read by label, never by position.
FIELD_LABELS = (
    "Length",
    "Difficulty",
    "Estimated Time",
    "Route Type",
    "Dogs",
    "Park",
    "Region",
    "Author",
    "GPS Coordinates",
    "Features",
    "Publish Date",
    "Last Updated",
)

#: Where NYNJTC's hikes are: New York City to the Catskills, the Delaware
#: Water Gap to the Connecticut line, with a margin. Inherited verbatim from
#: lib/nynjtc_hikes.py, which took it from the same organization's ground, and
#: loose on purpose - the point is to catch the impossible, not the unlikely.
LAT_RANGE = (39.5, 43.6)
LON_RANGE = (-76.5, -72.0)

#: What the export calls a value it does not have. Read off the pages: the
#: `Last Updated` field prints this when a hike was never revised.
ABSENT_VALUES = {"", "n/a", "na", "none", "-", "unknown", "tbd"}

_TAG = re.compile(r"<[^>]+>")
_INLINE_TAG = re.compile(r"</?(?:strong|em|b|i|a|span|u|sup|sub)\b[^>]*>", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_DROPPED = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_PARAGRAPH = re.compile(r"<(p|li)\b[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_TITLE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.DOTALL | re.IGNORECASE)
_BADGE = re.compile(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE)
_LISTING_ID = re.compile(r"hike\.php\?id=(\d+)")
_LISTING_COUNT = re.compile(r"Results\s*\((\d+)\s+hikes?\s+found\)", re.IGNORECASE)
_GPX_LINK = re.compile(r"download_gpx\.php\?id=(\d+)", re.IGNORECASE)
_NUMBER = re.compile(r"(-?\d+(?:\.\d+)?)")
_COORD_PAIR = re.compile(r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)")
#: `<small class="text-muted">(Parking location)</small>` - what the export
#: says the one coordinate it publishes actually IS. Kept as published,
#: because "the parking" and "the trailhead" are not the same claim.
_COORD_LABEL = re.compile(r"<small[^>]*>\s*\((.*?)\)\s*</small>", re.DOTALL | re.IGNORECASE)


def strip_html(markup: str) -> str:
    """Tags out, entities in, whitespace flattened."""
    return _WHITESPACE.sub(" ", html_module.unescape(_TAG.sub(" ", _INLINE_TAG.sub("", markup)))).strip()


def paragraphs(markup: str) -> list[str]:
    """The prose in a block of markup: every `<p>` and `<li>`, as plain text,
    empties dropped. Falls back to the whole block when it carries no
    paragraph element at all - the Directions card is a bare `<div>` on the
    pages sampled, and dropping it would lose the only text saying where to
    park."""
    found = []
    for _, body in _PARAGRAPH.findall(markup):
        text = strip_html(body)
        if text:
            found.append(text)
    if found:
        return found
    whole = strip_html(markup)
    return [whole] if whole else []


def _absent(value: str | None) -> bool:
    return value is None or value.strip().lower() in ABSENT_VALUES


def _clean(value: str | None) -> str | None:
    """A field value, or None when the page said it has none. `N/A` is the
    export's own word for absent and is read as absent rather than carried as
    the string "N/A", which would print on a card as though it meant
    something."""
    return None if _absent(value) else _WHITESPACE.sub(" ", str(value)).strip()


def _number(value: str | None) -> float | None:
    """The first number in a field, or None. `4.8 miles` is 4.8; `3.0 hours`
    is 3.0. The unit is not read because the label already fixes it and the
    pages sampled never varied it."""
    if _absent(value):
        return None
    match = _NUMBER.search(value)
    return float(match.group(1)) if match else None


@dataclass
class Coordinate:
    """The one point the export publishes, with the export's OWN word for
    what it is. `label` is "Parking location" on every page sampled, and it
    is carried rather than renamed: a parking lot is where a hike starts from,
    not where the trail begins, and a route built from it has to cross that
    gap knowingly."""

    lat: float
    lon: float
    label: str | None

    def to_dict(self) -> dict:
        return {"lat": self.lat, "lon": self.lon, "label": self.label}


@dataclass
class TrackPoint:
    lat: float
    lon: float
    #: Metres, as the GPX spec has it and as the file carries it.
    ele_m: float | None


@dataclass
class Track:
    """A published GPX track: the route as whoever drew it drew it.

    This build does not re-derive it, smooth it, or snap it to its own trail
    lines. It is somebody's survey and the most authoritative thing in this
    whole import.
    """

    name: str | None
    points: list[TrackPoint] = field(default_factory=list)

    @property
    def length_miles(self) -> float:
        return metres_between_points(self.points) / METRES_PER_MILE

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "points": [[p.lat, p.lon] + ([p.ele_m] if p.ele_m is not None else []) for p in self.points],
        }


METRES_PER_MILE = 1609.344
#: WGS84 equatorial, matching lib/trail_graph_route.py's EARTH_RADIUS_M, so a
#: GPX measured here and a route measured there are measured on one sphere.
EARTH_RADIUS_M = 6_378_137


def metres_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle metres between two `(lat, lon)` points."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def metres_between_points(points: list[TrackPoint]) -> float:
    return sum(metres_between((a.lat, a.lon), (b.lat, b.lon)) for a, b in zip(points, points[1:]))


@dataclass
class ParsedHike:
    """One exported hike, as facts. Says nothing about whether it may ship or
    where a route for it would go.

    EVERY FIELD THE PAGE CARRIES IS HERE. That is the maintainer's
    instruction rather than this module's taste, and it is why `features` and
    `raw_fields` both exist: the first is the tag list the app will facet on,
    the second is every labelled value exactly as the page printed it, so a
    field this build has not thought of yet is still in the cache when
    somebody wants it.
    """

    id: int
    name: str
    source_url: str
    summary: str | None = None
    stated_miles: float | None = None
    difficulty: str | None = None
    estimated_hours: float | None = None
    route_type: str | None = None
    dogs: str | None = None
    park: str | None = None
    region: str | None = None
    author: str | None = None
    start: Coordinate | None = None
    features: list[str] = field(default_factory=list)
    published_on: str | None = None
    updated_on: str | None = None
    directions: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)
    public_transport: list[str] = field(default_factory=list)
    has_published_route: bool = False
    gpx_url: str | None = None
    raw_fields: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_url": self.source_url,
            "summary": self.summary,
            "stated_miles": self.stated_miles,
            "difficulty": self.difficulty,
            "estimated_hours": self.estimated_hours,
            "route_type": self.route_type,
            "dogs": self.dogs,
            "park": self.park,
            "region": self.region,
            "author": self.author,
            "start": self.start.to_dict() if self.start else None,
            "features": list(self.features),
            "published_on": self.published_on,
            "updated_on": self.updated_on,
            "directions": list(self.directions),
            "description": list(self.description),
            "public_transport": list(self.public_transport),
            "has_published_route": self.has_published_route,
            "gpx_url": self.gpx_url,
            "raw_fields": dict(self.raw_fields),
        }


def listing_ids(markup: str) -> list[int]:
    """Every hike id the browse page links, in ascending order, deduplicated.

    The listing is this import's INDEX - the export publishes no other list -
    so a page that parses to nothing is a changed export rather than an empty
    one, and `fetch_hikefinder.py` refuses the run on it.
    """
    return sorted({int(found) for found in _LISTING_ID.findall(markup)})


def listing_count(markup: str) -> int | None:
    """The total the listing prints about itself ("Results (385 hikes
    found)"), or None when it prints none.

    Kept apart from `listing_ids` on purpose: the two disagreeing is the
    signal that the page paginates, or that a row lost its link, and a
    fetcher that silently took the shorter answer would report a shrunken
    export as a complete one.
    """
    match = _LISTING_COUNT.search(markup)
    return int(match.group(1)) if match else None


def _cards(markup: str) -> dict[str, str]:
    """Each `<h2>` card header on the page, mapped to the markup of the
    `card-body` that follows it.

    Read by walking from each header to the next rather than by matching a
    nested `<div>` shape: `card-body` blocks here hold further `<div>`s, and a
    regex that tried to balance them would stop at the first inner close.
    """
    headers = [
        (m.start(), strip_html(m.group(1))) for m in re.finditer(r"<h2[^>]*>(.*?)</h2>", markup, re.DOTALL | re.IGNORECASE)
    ]
    found: dict[str, str] = {}
    for index, (at, title) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(markup)
        block = markup[at:end]
        body = re.search(r'<div[^>]*class="[^"]*card-body[^"]*"[^>]*>(.*)', block, re.DOTALL | re.IGNORECASE)
        if body and title and title not in found:
            found[title] = body.group(1)
    return found


def _fields(markup: str) -> dict[str, str]:
    """Each `<strong>Label:</strong>` on the page, mapped to the markup
    between it and whatever ends it.

    A field's value runs to the next `<strong>` label or the end of its
    enclosing `</div>`, whichever comes first. Both are needed: the labels sit
    two to a row, so the next label ends the first of a pair, and a closing
    div ends the second.
    """
    marks = [
        (m.start(), m.end(), strip_html(m.group(1)))
        for m in re.finditer(r"<strong>([^<]{1,40}?):</strong>", markup, re.IGNORECASE)
    ]
    found: dict[str, str] = {}
    for index, (_, value_from, label) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(markup)
        chunk = markup[value_from:stop]
        closed = re.search(r"</div>", chunk, re.IGNORECASE)
        if closed:
            chunk = chunk[: closed.start()]
        if label not in found:
            found[label] = chunk
    return found


def _in_range(lat: float, lon: float) -> bool:
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def parse_coordinate(markup: str) -> Coordinate | None:
    """The GPS Coordinates field as a point, or None when the page carries
    none or carries one off this ground.

    The range check is the guard lib/nynjtc_hikes.py's `parse_start` needed
    for the same reason: a number in a coordinate field is not a coordinate,
    and a hike placed at 0,0 or at a transposed lon,lat would be a pin in the
    ocean rather than a missing pin - which a reviewer can see.
    """
    pair = _COORD_PAIR.search(_WHITESPACE.sub(" ", strip_html(_COORD_LABEL.sub(" ", markup))))
    if pair is None:
        return None
    lat, lon = float(pair.group(1)), float(pair.group(2))
    if not _in_range(lat, lon):
        return None
    label = _COORD_LABEL.search(markup)
    return Coordinate(lat=lat, lon=lon, label=strip_html(label.group(1)) if label else None)


def parse_hike(markup: str, hike_id: int, source_url: str) -> ParsedHike | None:
    """One exported page as facts, or None if the payload was not understood.

    THE REQUIRED TWO are the id and a title. Everything else may be
    legitimately absent on a real hike - two of the first 160 pages carry no
    Summary and no Directions - and refusing those would be this module
    inventing a completeness the export does not promise. `hike_problems()`
    says what is missing; the route build decides what to do about it.
    """
    body = _DROPPED.sub(" ", markup)
    title = _TITLE.search(body)
    name = strip_html(title.group(1)) if title else ""
    if not name:
        return None

    cards = _cards(body)
    fields = _fields(body)
    raw = {label: strip_html(value) for label, value in fields.items() if strip_html(value)}

    features = [strip_html(found) for found in _BADGE.findall(fields.get("Features", ""))]
    gpx = _GPX_LINK.search(body)

    summary = cards.get("Summary")
    return ParsedHike(
        id=hike_id,
        name=name,
        source_url=source_url,
        summary=" ".join(paragraphs(summary)) or None if summary else None,
        stated_miles=_number(raw.get("Length")),
        # NYNJTC's own words, as printed. The export spells them "Moderate To
        # Strenuous" where nynjtc.org's slug was `moderate-strenuous`; neither
        # is mapped onto the other, because a badge should quote its publisher.
        difficulty=_clean(raw.get("Difficulty")),
        estimated_hours=_number(raw.get("Estimated Time")),
        route_type=_clean(raw.get("Route Type")),
        dogs=_clean(raw.get("Dogs")),
        park=_clean(raw.get("Park")),
        region=_clean(raw.get("Region")),
        author=_clean(raw.get("Author")),
        start=parse_coordinate(fields.get("GPS Coordinates", "")),
        features=[f for f in features if f],
        published_on=_clean(raw.get("Publish Date")),
        updated_on=_clean(raw.get("Last Updated")),
        directions=paragraphs(cards.get("Directions to Trailhead", "")),
        description=paragraphs(cards.get("Description", "")),
        public_transport=paragraphs(cards.get("Public Transportation", "")),
        has_published_route=gpx is not None,
        gpx_url=GPX_PATH.format(id=hike_id) if gpx else None,
        raw_fields=raw,
    )


def parse_gpx(xml: str) -> Track | None:
    """A downloaded GPX as a track, or None when it holds no point.

    Namespace-agnostic: the export's files are written by gpx.studio and
    declare the GPX 1.1 namespace, but a file that declared none, or declared
    1.0, holds the same `trkpt` elements and there is no reason to refuse it.
    A point with no `<ele>` keeps its position and carries None - absent
    means unmeasured, never zero.
    """
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return None

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    points: list[TrackPoint] = []
    name = None
    for element in root.iter():
        if local(element.tag) == "name" and name is None and (element.text or "").strip():
            name = element.text.strip()
        if local(element.tag) != "trkpt":
            continue
        try:
            lat, lon = float(element.attrib["lat"]), float(element.attrib["lon"])
        except (KeyError, ValueError):
            continue
        ele = None
        for child in element:
            if local(child.tag) == "ele":
                try:
                    ele = float((child.text or "").strip())
                except ValueError:
                    ele = None
        points.append(TrackPoint(lat=lat, lon=lon, ele_m=ele))
    if not points:
        return None
    return Track(name=name, points=points)


def hike_problems(hike: ParsedHike) -> list[str]:
    """What stops this hike reaching a phone as it stands, in the order a
    reviewer should read them.

    A REVIEW AID RATHER THAN A GATE - `lib/nynjtc_hikes.py`'s rule, kept.
    Nothing refuses to cache a hike for having problems; the cache is what a
    person reads. An empty list means "everything a route needs was on the
    page", NOT "this hike is publishable".
    """
    problems = []
    if hike.start is None:
        problems.append("no GPS coordinate on the page - a route has nowhere to start from")
    if not hike.description:
        problems.append("no Description card - nothing to build a route from and nothing to print")
    if hike.stated_miles is None:
        problems.append("no stated Length to check a built route against")
    if hike.route_type is None:
        problems.append("no Route Type, so whether the walk closes back on itself is unknown")
    if not hike.features:
        problems.append("no Features tags")
    if hike.author is None:
        problems.append("no Author - nobody's name to carry with the write-up")
    return problems


def as_cache_entry(hike: ParsedHike, fetched_at: str) -> dict:
    """One parsed hike, flattened for the cache, with the fetch clock kept
    apart from the export's own Last Updated - the one that says whether the
    page changed."""
    return {**hike.to_dict(), "fetched_at": fetched_at, "problems": hike_problems(hike)}
