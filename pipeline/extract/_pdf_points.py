"""Decision 54, wave 4, section S: the points a club publishes in a PDF, read with a parser per document family.

    pdf_points(key)   one PDF's points, one row per row its parser reads (a water cache box, a trailhead, an
                      access point), each with the document's own manifest

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 4: "PDFs | the club-PDF kind exists
(GATC) | a parser per document family; a PDF that only a person can read stays a note". extract/_kinds.py's
ClubPdf (GATC's water sources) is the pattern, and lib/club_pdfs.py its parsers; this is section S's module
for the points-shaped ones (the content types' PDFs are section K's, extract/_pdf_content.py). A builder like
the rest: it takes a sources.json key, never a URL.

THE TEXT is pypdf's plain extraction, one string a page, through fetch_club_pdfs.py's extract_page_texts, the
reader ClubPdf uses. pypdf is pinned in requirements-extract.in, which the extract job installs, and not in the
pipeline or dbt jobs (requirements.in's note), so a parser is a function of those strings and its tests need no
pypdf; only the read itself does.

A PARSER REFUSES RATHER THAN RELABELS (test_a_club_pdf_whose_layout_changed_refuses_rather_than_relabelling's
rule): each is written against the document as it was read live on 2026-10-04 and raises PdfLayoutChanged when
the header it was written for is gone, a row has a shape it has not seen, or a land manager or a column it
splits on is not one it knows. A refusal is a failed read, so the table keeps its last committed rows. Where
pypdf hands over a row's columns run together and nothing in the text separates them, the parser keeps them
fused, as lib/club_pdfs.py keeps GATC's, rather than splitting them by guesswork.

THE ROW is the facts the parser reads, the point as GeoJSON in `geometry` (null where the row states none,
never looked up from a name), and the document's manifest: `source_url`, `document_etag`,
`document_last_modified`, `document_sha256` and `document_bytes`, so the date the club put on the file is in
the warehouse beside what it says. A sentence of the document's lands in no column (decision 55).

THE CHANGE CHECK is per file (the round brief): a HEAD, and its ETag, else its Last-Modified with its
Content-Length, compared with what the last load recorded; a file that sends neither is UNKNOWN and is read.
Every PDF registered here sent a strong ETag and a Last-Modified on 2026-10-04 (each row's `freshness`).

ACCESS. lib/user_agent.py's USER_AGENT through extract/_kinds.py's session(), behind extract/_notices.py's
per-host gate: DEFAULT_HOST_GAP_SECONDS, or the row's `crawl_delay` where the host's robots.txt asks for more
(bmta.org asks 60). A wall raises; an answer that is not a PDF raises.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from extract import _kinds, _notices
from extract._contract import Resource
from extract._pages_points import ddm, north_america, point
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry


class PdfLayoutChanged(ValueError):
    """The PDF answered, and its text is not laid out the way its parser was written against."""


#: A parser takes the PDF's page texts (pypdf's plain extraction, one string a page) and returns its rows.
Parser = Callable[[list[str]], list[dict]]

PDF_PARSERS: dict[str, Parser] = {}


def _parser(key: str):
    def register(function: Parser) -> Parser:
        PDF_PARSERS[key] = function
        return function

    return register


def _lines(texts: list[str]) -> list[str]:
    return [" ".join(line.split()) for text in texts for line in text.splitlines() if line.strip()]


# --- The Arizona Trail Association's bear box / water cache locations ------------------------------------------

ATA_TITLE = "Arizona Trail Bear Box/Water Cache Locations"
#: One location's numbers, as pypdf hands them over (read 2026-10-04): the FarOut waypoint the table names as
#: closest (one, or two joined by "/" at a passage boundary), the NOBO mile, then latitude and longitude in
#: decimal degrees. Navajo Trail Junction's latitude prints as "36. 851650", a space inside the number, which
#: is read as written without it.
ATA_ROW = re.compile(
    r"(?:^|\s)(?P<waypoint>\d{2}-\d{3}[a-z]?(?:/\d{2}-\d{3}[a-z]?)?)\s+(?P<mile>\d+(?:\.\d+)?)\s+"
    r"(?P<lat>\d{2}\.\s?\d+)\s+(?P<lon>-\d{2,3}\.\d+)(?:\s|$)"
)
#: The land managers the table named on 2026-10-04 other than a national forest, matched at the end of a
#: location's description. A manager outside these refuses the document, because the split between a
#: location's name and its manager is the one place this parser reads words.
ATA_LAND_MANAGERS = (
    "Borderlands Restoration Network",
    "Oracle State Park",
    "Pima County",
    "Pinal County",
)
#: A national forest is one word and "NF" ("Coronado NF", "Kaibab NF"): a two-word name would take the
#: location's last word ("Trailhead Coronado NF"), so the four the trail crosses are each one word.
ATA_FOREST = re.compile(r"^(?P<name>.+?)\s+(?P<manager>[A-Z][\w-]* NF)$")


def _ata_split(described: str, where: str) -> tuple[str, str]:
    for manager in ATA_LAND_MANAGERS:
        if described.endswith(" " + manager):
            return described[: -len(manager)].strip(), manager
    if found := ATA_FOREST.match(described):
        return found["name"], found["manager"]
    raise PdfLayoutChanged(f"{where}: {described!r} does not end in a land manager the parser knows")


@_parser("ata_water_cache_boxes")
def parse_ata_water_cache_boxes(texts: list[str]) -> list[dict]:
    """ATA's bear boxes for caching water: location, land manager, FarOut waypoint, NOBO mile and the box's fix.

    A water cache box holds only what hikers and trail angels leave in it ("Bear boxes are for caching water
    only", aztrail.org/explore/water-sources/, read 2026-10-04): it is never a water source, and a box can be
    empty. The table's "Location Notes" (where the box sits beside a kiosk or a fence) are the association's
    sentences and land nowhere; the fix places the box.

    A location's description sits on its numbers' line, or, when it wraps (Casa Blanca Canyon Trailhead's
    "Borderlands Restoration / Network"), on the lines before a numbers line that starts with its waypoint. Any
    other line between two numbers lines is the previous location's wrapped notes.
    """
    lines = _lines(texts)
    if not lines or lines[0] != ATA_TITLE or not any("Latitude Longitude" in line for line in lines[:4]):
        raise PdfLayoutChanged(f"the document does not open with {ATA_TITLE!r} and its Latitude/Longitude header")
    body = [line for line in lines[1:] if not line.startswith(("Location Land Manager", "Description Waypoint"))]
    rows, pending = [], []
    for line in body:
        found = ATA_ROW.search(line)
        if not found:
            pending.append(line)
            continue
        prefix = line[: found.start()].strip()
        described = prefix if prefix else " ".join(pending)
        pending = []
        if not described:
            raise PdfLayoutChanged(f"a numbers line with no location before it: {line!r}")
        name, manager = _ata_split(described, line)
        lat = float(found["lat"].replace(" ", ""))
        rows.append(
            {
                "name": name,
                "land_manager": manager,
                "farout_waypoint": found["waypoint"],
                "mile_nobo": float(found["mile"]),
                "geometry": point(lat, float(found["lon"]), line),
            }
        )
    if not rows:
        raise PdfLayoutChanged("the table holds no location")
    return rows


# --- The Benton MacKaye Trail Association's access points and trailheads -----------------------------------------

#: The header pypdf repeats at the top of each of the four pages, and the footer lines below each page's table
#: (read 2026-10-04: the state the page covers and the table's date, 5/24/2020).
BMTA_HEADER = (
    "At Mile: Location Trail Head Name",
    "BMT Section #",
    "Linked to REI:",
    "Hiking Project",
    "Road Name Link 2 Latitude Longitude",
)
BMTA_FOOTER = re.compile(r"^(?:Page \d+ of \d+|Access Points / Trailheads|[A-Z][A-Z .]+|\d{1,2}/\d{1,2}/\d{4})$")
BMTA_FIX = re.compile(
    r"\s*N(?P<latd>\d{2})°\s?(?P<latm>\d{1,2}(?:\.\d+)?)\s+W(?P<lond>\d{2,3})°\s?(?P<lonm>\d{1,2}(?:\.\d+)?)\s*$"
)
BMTA_MILE = re.compile(r"^(?P<mile>\d{1,3}(?:\.\d+)?)\s+(?P<rest>\S.*)$")


@_parser("bmta_access_points")
def parse_bmta_access_points(texts: list[str]) -> list[dict]:
    """BMTA's access points: the BMT mile, the row's text fused, and the fix where the row gives one.

    pypdf hands over each row's five text columns (location, trailhead name, BMT section, road name and its
    second link) run together with nothing between them, so they land fused in `description`, as GATC's water
    PDF's do (lib/club_pdfs.py), never split by guesswork. A row starts with its mile, or, once, with no mile
    ("End of Fontana Dam Rd", after Fontana Dam); it ends at its fix, or where the next row's mile starts
    (Weaver Creek Road, mile 46, has no fix). A page without the header refuses the document.
    """
    rows: list[dict] = []
    current: dict | None = None

    def close(fix: re.Match | None):
        nonlocal current
        if current is None:
            return
        description = " ".join(current.pop("parts")).strip()
        if not description:
            raise PdfLayoutChanged(f"an access point at mile {current['mile']} with no text")
        geometry = None
        if fix is not None:
            lat, lon = ddm(fix["latd"], fix["latm"]), ddm(fix["lond"], fix["lonm"])
            geometry = north_america(lat, lon, description)
        rows.append({"mile": current["mile"], "description": description, "geometry": geometry})
        current = None

    for number, text in enumerate(texts, 1):
        lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
        if not all(header in lines for header in BMTA_HEADER):
            raise PdfLayoutChanged(f"page {number} lacks the access-point table's header")
        for line in lines:
            if line in BMTA_HEADER or BMTA_FOOTER.match(line):
                continue
            mile = BMTA_MILE.match(line)
            if mile and current is not None:
                close(None)  # a row that ended without a fix, as Weaver Creek Road does
            if current is None:
                current = {"mile": float(mile["mile"]) if mile else None, "parts": []}
                line = mile["rest"] if mile else line
            fix = BMTA_FIX.search(line)
            current["parts"].append(line[: fix.start()] if fix else line)
            if fix:
                close(fix)
    close(None)
    if not rows:
        raise PdfLayoutChanged("the table holds no access point")
    return rows


# --- The resource -------------------------------------------------------------------------------------------------


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


@dataclass(frozen=True)
class PdfPoints(Resource):
    """One PDF read for its points: one row per row its parser reads, each with the document's manifest."""

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def url(self) -> str:
        return self.entry["url"]

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> None:
        """None: the count is the rows this key's parser reads out of a PDF's text layer, which a reworded or rescanned
        document can make none. A row whose `may_be_empty` lets it empty is still refused a zero (extract/_run.py)."""
        return None

    def column_hints(self) -> dict:
        return {"geometry": {"data_type": "json"}, "source_url": {"data_type": "text"}, "document_bytes": {"data_type": "bigint"}}

    def _session(self) -> requests.Session:
        delay = max(_notices.DEFAULT_HOST_GAP_SECONDS, float(self.entry.get("crawl_delay") or 0))
        return _notices.polite(_kinds.session(), delay)

    def _request(self, method: str) -> requests.Response:
        response = request_with_retry(self.url, session=self._session(), method=method, timeout=120, label=self.key)
        if reason := _notices.wall(response):
            raise PdfLayoutChanged(f"{self.key}: {self.url} answered as a wall ({reason})")
        return response

    @staticmethod
    def _validator(response: requests.Response) -> dict | None:
        """The file's own validator: its ETag, else its Last-Modified with its Content-Length, else None."""
        headers = response.headers
        if headers.get("ETag"):
            return {"etag": headers["ETag"]}
        if headers.get("Last-Modified") and headers.get("Content-Length"):
            return {"last_modified": headers["Last-Modified"], "content_length": headers["Content-Length"]}
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            marker = self._validator(self._request("head"))
        except (requests.RequestException, PdfLayoutChanged) as error:
            print(f"  {self.key}: change check failed ({error}); reading it")
            return Freshness.UNKNOWN, None
        if marker is None:
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        from fetch_club_pdfs import extract_page_texts  # pypdf: requirements-extract.in pins it (the module docstring)

        response = self._request("get")
        response.raise_for_status()
        body = response.content
        if not body.startswith(b"%PDF-"):
            raise PdfLayoutChanged(f"{self.key}: {self.url} answered {response.headers.get('Content-Type')!r}, not a PDF")
        rows = PDF_PARSERS[self.key](extract_page_texts(body))
        manifest = {
            "source_url": self.url,
            "document_etag": response.headers.get("ETag"),
            "document_last_modified": response.headers.get("Last-Modified"),
            "document_sha256": hashlib.sha256(body).hexdigest(),
            "document_bytes": len(body),
        }
        proofs[self.table] = len(rows)
        print(f"  {self.key}: {len(rows)} points from {len(body):,} bytes")
        for row in rows:
            yield {**row, **manifest}


def pdf_points(key: str, **overrides) -> PdfPoints:
    entry = _kinds.registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    if key not in PDF_PARSERS:
        raise KeyError(f"{key}: extract/_pdf_points.py's PDF_PARSERS has no parser for it")
    if urlparse(entry["url"]).scheme != "https":
        raise KeyError(f"{key}: {entry['url']} is not an https URL")
    return PdfPoints(key=key, **overrides)
