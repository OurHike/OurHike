"""ATC Trail Updates feasibility spike (features/ATC_TRAIL_UPDATES.md).

Answers one question, and only one: **can the ATC's published Trail Updates
be placed on OurHike's map automatically, and how many of them cannot be?**

That is a property of how ATC actually writes those pages, not of any
algorithm - so it has to be measured against the real pages rather than
argued about, which is what this script is for.

The claim it exists to test is that ATC and OurHike already share a
coordinate system. ATC writes locations as NOBO miles from Springer
("NOBO mile 360.6 to 364.8"), `closures.start_mile_marker`/`end_mile_marker`
are that same number, and `half_mile_points_from_springer` - source #9 in
sources.json, already registered, already fetched by fetch_all.py - is ATC's
own table turning one into a coordinate. If that holds, placing an update is
a join against data this pipeline already has, not a geocoding problem.

THIS IS A SPIKE, AND NOTHING HERE SHIPS TO A HIKER. It reads public pages to
produce numbers. It writes no artifact, holds no credential, and deliberately
stops at the point where a human would have to decide whether a parsed range
is right - features/ATC_TRAIL_UPDATES.md argues that the decision is the
whole design, and this script is what tells that argument its numbers.

The redistribution question is why this reads the pages instead of building
a fetcher: ATC's terms are one of two unresolved data-terms questions this
project carries (features/SOURCE_REGISTRY.md), and its diagnosis is that both
happened by fetching first and asking afterwards. Measuring is not shipping.

    python spike_atc_updates.py              # measure against the live pages
    python spike_atc_updates.py --no-resolve # parse only, no ArcGIS queries
"""

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import requests

from lib.arcgis import fetch_layer_geojson

FEED_URL = "https://appalachiantrail.org/trail-updates/feed/"

# sources.json's `half_mile_points_from_springer` entry, quoted rather than
# read, because a spike that parses the registry to prove a point about the
# registry has one more thing that can break for reasons unrelated to the
# question. The real ingest would resolve this through sources.json.
HALF_MILE_LAYER_URL = (
    "https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/Half_Mile_Points040726_NoM/FeatureServer/18"
)

# The layer's real extent, measured 2026-08-09 against the live service:
# 4,395 points, Measure 0.5 to 2197.5, one every half mile. A parsed mile
# outside this is not a location - it is a parse that went wrong, and saying
# so is the difference between an empty map band and a wrong one.
TRAIL_MILE_MIN = 0.5
TRAIL_MILE_MAX = 2197.5

# How ATC actually writes a location, from all nine updates live on
# 2026-08-09. Every form below is real, taken from the pages, not imagined:
#
#   "NOBO mile 364.7"                  a point
#   "NOBO mile 360.6 to 364.8"         a range, singular "mile"
#   "NOBO miles 239.4 to 637.8"        a range, plural
#   "NOBO mile 1,503.6"                thousands separator, past mile 1000
#   "at NOBO mile 485.8. NOBO hikers"  sentence-final, and the period is not
#                                      part of the number
#
# The thousands comma is the detail worth naming: a number pattern that omits
# it silently truncates "NOBO mile 1,503.6" to mile 1, which is a shelter in
# Connecticut reported as a spot in Georgia. Wrong beats missing here, and it
# would have looked like a plausible result rather than a crash.
_MILE_NUMBER = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?"

MILE_REFERENCE = re.compile(
    rf"""
    (?P<direction>NOBO|SOBO)\s+miles?\s+
    (?P<start>{_MILE_NUMBER})
    (?:\s*(?:to|through|-|–|—)\s*(?P<end>{_MILE_NUMBER}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


@dataclass
class MileReference:
    """One "NOBO mile X to Y" as ATC wrote it, and as a number.

    `end is None` means ATC named a point, not a range. That distinction is
    kept rather than collapsed to a zero-length range: a shelter at a mile and
    a nine-mile construction closure are different things to draw, and
    features/ATC_TRAIL_UPDATES.md argues the second is the one that must never
    be guessed at.
    """

    direction: str
    start: float
    end: float | None
    raw: str

    @property
    def is_range(self) -> bool:
        return self.end is not None

    @property
    def in_trail_extent(self) -> bool:
        ends = [self.start] + ([self.end] if self.end is not None else [])
        return all(TRAIL_MILE_MIN <= m <= TRAIL_MILE_MAX for m in ends)


@dataclass
class Update:
    title: str
    link: str
    published: str
    text: str
    references: list[MileReference] = field(default_factory=list)

    @property
    def mappable(self) -> bool:
        return any(r.in_trail_extent for r in self.references)


def strip_html(markup: str) -> str:
    """Tags out, entities in, whitespace flattened.

    Deliberately not an HTML parser: the input is one WordPress
    `content:encoded` block of paragraphs and lists, and the only thing this
    has to get right is that words either side of a tag do not run together
    into a token the mile pattern could misread.
    """
    import html as html_module

    return _WHITESPACE.sub(" ", html_module.unescape(_TAG.sub(" ", markup))).strip()


def parse_mile(number: str) -> float:
    """ "1,503.6" -> 1503.6. See _MILE_NUMBER for why the comma matters."""
    return float(number.replace(",", ""))


def extract_mile_references(text: str) -> list[MileReference]:
    """Every NOBO/SOBO mile reference in a block of update prose.

    Order is document order, and duplicates are kept. An update that says the
    same range three times as it is edited over months (iron-mtn-gap-detour
    does exactly this) is telling us something about its history, and
    deduplicating here would throw that away before a reviewer sees it.
    """
    references = []
    for match in MILE_REFERENCE.finditer(text):
        end = match.group("end")
        references.append(
            MileReference(
                direction=match.group("direction").upper(),
                start=parse_mile(match.group("start")),
                end=parse_mile(end) if end else None,
                raw=match.group(0),
            )
        )
    return references


def fetch_updates(feed_url: str = FEED_URL, timeout: int = 60) -> list[Update]:
    """The Trail Updates RSS feed, parsed.

    The feed carries `content:encoded` - the full body, not a teaser - which
    is what makes this readable without scraping the rendered page. It also
    carries fewer items than the page shows (3 of the 9 live on 2026-08-09),
    and that gap is a finding rather than a bug to route around: see this
    script's output and the design doc's "what the feed does not carry".
    """
    resp = requests.get(feed_url, timeout=timeout)
    resp.raise_for_status()
    channel = ET.fromstring(resp.content).find("channel")
    if channel is None:
        return []

    namespaces = {"content": "http://purl.org/rss/1.0/modules/content/"}
    updates = []
    for item in channel.findall("item"):
        body = item.findtext("content:encoded", default="", namespaces=namespaces) or ""
        text = strip_html(body)
        updates.append(
            Update(
                title=(item.findtext("title") or "").strip(),
                link=(item.findtext("link") or "").strip(),
                published=(item.findtext("pubDate") or "").strip(),
                text=text,
                references=extract_mile_references(text),
            )
        )
    return updates


def load_mile_index() -> dict[float, tuple[float, float]]:
    """ATC's own half-mile markers as {mile: (lon, lat)}.

    This is the join that the whole feasibility argument rests on, and it is
    one existing fetcher against one already-registered source - not new
    machinery. `Measure` is the mile from Springer; `MeasureM` is the same
    distance in meters and is ignored here.
    """
    collection = fetch_layer_geojson(HALF_MILE_LAYER_URL)
    index = {}
    for feature in collection.get("features", []):
        measure = (feature.get("properties") or {}).get("Measure")
        geometry = feature.get("geometry") or {}
        if measure is None or geometry.get("type") != "Point":
            continue
        lon, lat = geometry["coordinates"][:2]
        index[round(float(measure), 1)] = (lon, lat)
    return index


def nearest_marker(index: dict[float, tuple[float, float]], mile: float) -> tuple[float, tuple[float, float]] | None:
    """The half-mile marker nearest a parsed mile, and which one it was.

    Markers land every half mile and ATC quotes tenths, so an exact hit is the
    exception - "NOBO mile 360.6" has no marker of its own. Returning the
    marker actually used, rather than only its coordinates, keeps the
    approximation visible: up to a quarter mile of slop, which the design doc
    treats as the reason a published band should come from the centerline
    rather than from these points.
    """
    if not index:
        return None
    nearest = min(index, key=lambda m: abs(m - mile))
    return nearest, index[nearest]


def report(updates: list[Update], index: dict[float, tuple[float, float]] | None) -> None:
    print(f"Trail Updates in the feed: {len(updates)}\n")

    for update in updates:
        placed = "MAPPABLE" if update.mappable else "not mappable"
        print(f"[{placed}] {update.title}")
        print(f"    {update.link}")
        if not update.references:
            print("    no NOBO/SOBO mile reference in the body")
        for reference in update.references:
            span = f"{reference.start}" + (f" to {reference.end}" if reference.is_range else " (point)")
            note = "" if reference.in_trail_extent else "  <- OUTSIDE THE TRAIL EXTENT"
            print(f"    {reference.raw!r} -> {span}{note}")
            if index and reference.in_trail_extent:
                for label, mile in [("start", reference.start), ("end", reference.end)]:
                    if mile is None:
                        continue
                    found = nearest_marker(index, mile)
                    if found:
                        marker, (lon, lat) = found
                        print(f"        {label} mi {mile} ~ marker {marker}: {lat:.5f}, {lon:.5f}")
        print()

    mappable = sum(1 for u in updates if u.mappable)
    print("-" * 60)
    print(f"Mappable from a mile reference alone: {mappable}/{len(updates)}")
    if mappable < len(updates):
        print(f"Needing a human to place them (or not places at all): {len(updates) - mappable}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        help="parse the feed only; skip the ArcGIS queries that turn miles into coordinates",
    )
    args = parser.parse_args(argv)

    updates = fetch_updates()
    if not updates:
        print("No updates in the feed - nothing to measure.", file=sys.stderr)
        return 1

    index = None
    if not args.no_resolve:
        print("Loading ATC half-mile markers...", file=sys.stderr)
        index = load_mile_index()
        print(f"  {len(index)} markers\n", file=sys.stderr)

    report(updates, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
