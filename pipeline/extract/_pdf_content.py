"""Decision 54 wave 4's PDF readers for the content types (section K): the suggested hikes and challenges a club
publishes as PDFs, one parser per document family.

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 4, is the plan: "a parser per document
family; a PDF that only a person can read stays a note". extract/_kinds.py's ClubPdf (GATC's water sources) is the
pattern, and lib/club_pdfs.py's rule is this module's: a parser reads the layout it was written for and REFUSES
RATHER THAN RELABELS when the layout changes (PdfLayoutChanged), so a redrawn document never lands its columns under
the wrong names. A scanned PDF has no text layer and parses to nothing, which refuses too.

    content_pdf(key)          a club's PDF, or the PDFs its index page links, one row per item its family's
                              parser (PDF_FAMILIES) reads

WHAT A ROW CARRIES is extract/_pages_content.py's rule, the same allowlist (its TYPE_COLUMNS, the family's own
`columns`, and DOCUMENT_COLUMNS): facts and the link, never the document's prose (decision 55), and a text value
longer than its MAX_FACT_CHARS raises. Each row also carries its document's manifest (DOCUMENT_COLUMNS: the URL, the
validators, the sha256, the byte count and the date the PDF's own metadata states), so the date a club put on its
file is in the warehouse. A PDF's metadata names a person more often than not (RMC's /Author is a member's name,
2026-10-04), so no metadata field lands but the ModDate and CreationDate days.

THE CHANGE CHECK IS PER FILE, as the round brief asks: a conditional GET with the file's own validators, a 304
FRESH; on a 200 the marker is the file's ETag, else its Last-Modified with its Content-Length, and a host that sends
neither answers UNKNOWN, so the file is read every run. A family read through an index page (a club's page linking
one PDF a hike) checks every file the index links, and the index's own link set is part of the marker, so a PDF
added or dropped is STALE. A static file's validators are the file's (decision 53's inventory measured strong ETags
on four clubs' PDFs; extract/_notices.py's PageNotice docstring), unlike an HTML page's, which is why a validator
decides FRESH here and not in the page readers. That they move only with the file is @unvalidated for each host;
what would settle it is a 304 followed, on the next 200, by an unchanged sha256.

ONE READ A RUN AND POLITE, as extract/_notices.py's sources are: the check's answers are kept for the read, every
request passes polite() at the host's Crawl-delay or DEFAULT_HOST_GAP_SECONDS, and a wall, a challenge or a redirect
to another host raises. The text comes from extract/_notices.py's read_pdf, which needs pypdf: requirements-extract.in
pins it, and the pipeline suite and scripts/test.sh's fixture build do not, so these resources have no fixture-mode
fixture (as the notice PDFs have none, tests/test_extract_fixtures.py's NOTICE_PDFS): their tables land only where
pypdf is installed, the monthly extract job's venv. make_dbt_staging.py stages them all the same, and their base
models read no rows in the fixture build (dbt/macros/raw_or_empty.sql); tests/test_extract_pdf_content.py runs
each family over an invented text layer, which needs no pypdf. The lane is the type's, monthly.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

import requests

from extract._notices import NoticeUnreadable, PdfFacts, _canonical, _forget, _NoticeSource, _recall, _remember, read_pdf
from extract._pages_content import (
    TYPE_COLUMNS,
    LayoutChanged,
    Page,
    checked_row,
    fact,
    guarded_get,
    parse_html,
    single_miles,
)
from lib.freshness_state import Freshness, compare_marker


class PdfLayoutChanged(LayoutChanged):
    """A PDF that no longer reads as the layout its family's parser was written for: refused, never relabelled."""


#: The document's own manifest, on every row a PDF yields (the module docstring).
DOCUMENT_COLUMNS = {
    "document_url": "text",
    "document_etag": "text",
    "document_last_modified": "text",
    "document_bytes": "bigint",
    "document_sha256": "text",
    "document_modified": "text",
    "document_created": "text",
}


@dataclass(frozen=True)
class PdfFamily:
    """One document family: how its text becomes rows, the columns it adds, and, for a family behind an index page,
    how the index names its PDFs.

    `read(facts, url)` takes the PDF's text layer and metadata dates (extract/_notices.py's PdfFacts) and returns
    the rows; it raises PdfLayoutChanged on a layout it was not written for. `documents(page)`, when set, takes the
    registry row's page and returns the PDFs it links, in order; without it the registry row's url is the PDF.
    """

    read: Callable[[PdfFacts, str], list[dict]]
    columns: dict[str, str] = field(default_factory=dict)
    documents: Callable[[Page], list[str]] | None = None


@dataclass(frozen=True)
class ContentPdf(_NoticeSource):
    """A club's PDF, or the PDFs its index page links, one row per item its family in PDF_FAMILIES reads."""

    family: str = ""

    @property
    def parser(self) -> PdfFamily:
        return PDF_FAMILIES[self.family or self.key]

    @property
    def timeout(self) -> int:
        """ClubPdf's 120 s: a PDF can be megabytes."""
        return 120

    @property
    def columns(self) -> dict[str, str]:
        if self.type not in TYPE_COLUMNS:
            raise ValueError(f"{self.key}: a content PDF reader feeds {sorted(TYPE_COLUMNS)}, not {self.type}")
        return {**TYPE_COLUMNS[self.type], **self.parser.columns, **DOCUMENT_COLUMNS}

    def column_hints(self) -> dict:
        return {name: {"data_type": kind} for name, kind in self.columns.items()}

    def _urls(self) -> list[str]:
        """The PDFs this resource reads: the registry row's url, or the ones its index page links, on its own host."""
        if self.parser.documents is None:
            return [self.url]
        response = guarded_get(self, self.url)
        urls = self.parser.documents(Page(self.url, parse_html(response.text), response.text))
        if not urls:
            raise PdfLayoutChanged(f"{self.key}: the index links no PDF, which is a changed shape")
        for url in urls:
            if urlparse(url).hostname != urlparse(self.url).hostname:
                raise PdfLayoutChanged(f"{self.key}: the index links {url}, off its own host, which is not read")
        return urls

    @staticmethod
    def _validator(response: requests.Response) -> dict | None:
        """The file's own validator: its ETag, else its Last-Modified with its Content-Length, else None."""
        etag = response.headers.get("ETag")
        if etag:
            return {"etag": etag}
        modified, length = response.headers.get("Last-Modified"), response.headers.get("Content-Length")
        if modified and length:
            return {"last_modified": modified, "content_length": length}
        return None

    @staticmethod
    def _conditional(recorded: dict | None) -> dict | None:
        if not recorded:
            return None
        if recorded.get("etag"):
            return {"If-None-Match": recorded["etag"]}
        if recorded.get("last_modified"):
            return {"If-Modified-Since": recorded["last_modified"]}
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """Every file's own validator, by a conditional GET each; UNKNOWN where any file sends none (module docstring)."""
        _forget(self.table)
        files = (recorded or {}).get("files") or {}
        bodies: dict[str, requests.Response] = {}
        marker: dict[str, dict] = {}
        try:
            urls = self._urls()
            for url in urls:
                response = guarded_get(self, url, self._conditional(files.get(url)))
                if response.status_code == 304:
                    marker[url] = files[url]
                    continue
                validator = self._validator(response)
                bodies[url] = response
                if validator is None:
                    _remember(self.table, bodies)
                    return Freshness.UNKNOWN, None
                marker[url] = validator
        except (requests.RequestException, NoticeUnreadable, ValueError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        _remember(self.table, bodies)
        stamped = {"files": marker}
        if recorded is None:
            return Freshness.STALE, stamped
        return compare_marker(_canonical(recorded), _canonical(stamped)), stamped

    @property
    def exact_proof(self) -> bool:
        return True

    def rows(self, proofs: dict[str, int]):
        kept = _recall(self.table)
        bodies = kept if isinstance(kept, dict) else {}
        rows = []
        for url in self._urls():
            response = bodies.get(url) or guarded_get(self, url)
            if response.status_code != 200:
                response = guarded_get(self, url)
            facts = read_pdf(response.content)
            if not any(text.strip() for text in facts.texts):
                raise PdfLayoutChanged(f"{self.key}: {url} has no text layer, so only a person can read it")
            found = self.parser.read(facts, url)
            if not found:
                raise PdfLayoutChanged(f"{self.key}: {url} reads as no item, which is a changed layout")
            document = {
                "document_url": url,
                "document_etag": response.headers.get("ETag"),
                "document_last_modified": response.headers.get("Last-Modified"),
                "document_bytes": len(response.content),
                "document_sha256": hashlib.sha256(response.content).hexdigest(),
                "document_modified": facts.modified[1] if facts.modified else None,
                "document_created": facts.created[1] if facts.created else None,
            }
            rows.extend(checked_row(self.key, self.type, self.columns, {**row, **document}) for row in found)
        proofs[self.table] = len(rows)
        yield from rows


def content_pdf(key: str, *, family: str | None = None, crawl_delay: float = 0.0, **overrides) -> ContentPdf:
    """A ContentPdf for a registry key; `crawl_delay` is the host's robots.txt Crawl-delay, as its live read found."""
    resource = ContentPdf(key=key, family=family or key, crawl_delay=crawl_delay, **overrides)
    if resource.family not in PDF_FAMILIES:
        raise KeyError(f"{key}: extract/_pdf_content.py's PDF_FAMILIES has no family {resource.family!r}")
    resource.url  # an unregistered key fails at import, in the layout test
    return resource


# --- The families ---------------------------------------------------------------------------------------------------


def lines(facts: PdfFacts) -> list[str]:
    """The text layer's lines in page order, each whitespace folded, empty ones left out."""
    return [folded for text in facts.texts for line in text.splitlines() if (folded := " ".join(line.split()))]


_RMC_STATS = re.compile(
    r"(?P<miles>\d+(?:\.\d+)?) mi(?: (?P<shape>round trip|loop|one way))?, (?P<feet>\d[\d,]*)(?:-ft| ft)"
    r"(?: (?:ascent|elevation gain))?(?P<rest>.*)"
)
_RMC_TIME = re.compile(r"(\d+ hr(?: \d+ min)?|\d+ min)")
#: The headings RMC's 'Suggested Walks' uses for its groups: three of walks, then one per Northern Peak.
RMC_WALK_GROUPS = ("EASY WALKS", "MODERATE WALKS", "STRENUOUS WALKS")
RMC_PEAK_GROUPS = ("MT MADISON", "MT ADAMS", "MT JEFFERSON")


def _rmc_name(found: list[str], index: int) -> str:
    """The name above the statistics line at `index`: its line, and the one or two before it when the name wraps.

    A peak route's name is a list of trails that can run onto a second line ('Castle Trail, Israel Ridge Path,
    Castle Ravine Trail, Randolph Path, Gulfside' / 'Trail, Mt Jefferson Loop'). The line before a name ends the
    previous walk's description, a sentence ending '.', ')', ':' or '!', or is a heading, a statistics line or a
    Trailhead line; any other line above the name is the name's own first part.
    """
    parts = [found[index - 1]]
    for above in (index - 2, index - 3):
        if above < 0:
            break
        line = found[above]
        if (
            line.endswith((".", ")", ":", "!"))
            or line in RMC_WALK_GROUPS
            or line in RMC_PEAK_GROUPS
            or line.startswith(("Trailhead:", "Suggested Routes"))
            or _RMC_STATS.fullmatch(line)
        ):
            break
        parts.insert(0, line)
    return " ".join(parts)


def _rmc_recommended_hikes(facts: PdfFacts, url: str) -> list[dict]:
    """The Randolph Mountain Club's 'Suggested Walks' and 'Suggested Routes to the Northern Peaks' (Recommended-Hikes-1.pdf).

    Eight pages, read 2026-10-04 (Last-Modified 2023-02-20, 104,747 bytes, no ETag). Each walk is a name line, a
    statistics line ('0.5 mi round trip, 100-ft ascent, 30 min'; on the peak routes '4.3 mi, 4100-ft ascent, 4 hr
    10 min', or '0.9 mi, 1000 ft, 55 min' for a route from a hut) and, for most, 'Trailhead: <place>', under a group
    heading: EASY, MODERATE and STRENUOUS WALKS, then MT MADISON, MT ADAMS and MT JEFFERSON, whose distances the
    document says "are one-way to the summit". The paragraph after each is RMC's description and lands nowhere.
    The time is the document's own estimate and lands as its text (`time_text`), never a pace this module made. A
    peak route's name can wrap onto a second line (_rmc_name).

    A statistics line before any group heading, a group missing, or no walk read raises PdfLayoutChanged.
    """
    found = lines(facts)
    rows, group, peaks_section = [], None, False
    for index, line in enumerate(found):
        if line in RMC_WALK_GROUPS or line in RMC_PEAK_GROUPS:
            group = line.title()
            continue
        if line.startswith("Suggested Routes to the Northern Peaks"):
            peaks_section, group = True, None
            continue
        stats = _RMC_STATS.fullmatch(line)
        if not stats:
            continue
        if group is None or index == 0:
            raise PdfLayoutChanged(f"rmc: a statistics line {line!r} sits under no group heading")
        name = _rmc_name(found, index)
        trailhead = None
        for after in found[index + 1 : index + 3]:
            if after.startswith("Trailhead:"):
                trailhead = fact(after.removeprefix("Trailhead:"))
                break
        time = _RMC_TIME.search(stats["rest"])
        shape = stats["shape"] or ("one way" if peaks_section else None)
        rows.append(
            {
                "name": fact(name),
                "section": group,
                "distance_mi": float(stats["miles"]),
                "distance_text": f"{stats['miles']} mi" + (f" {stats['shape']}" if stats["shape"] else ""),
                "elevation_gain_ft": float(stats["feet"].replace(",", "")),
                "elevation_gain_text": f"{stats['feet']} ft",
                "route_type": shape,
                "place": trailhead,
                "time_text": time.group(1) if time else None,
                "link": url,
                "source_url": url,
            }
        )
    groups = {row["section"] for row in rows}
    expected = {name.title() for name in (*RMC_WALK_GROUPS, *RMC_PEAK_GROUPS)}
    if groups != expected:
        raise PdfLayoutChanged(f"rmc: the walks fall under {sorted(groups)}, not {sorted(expected)}")
    return rows


#: One hike's row of the Wasatch Mountain Club's table: its name in capitals, eleven figures and codes, its
#: location in capitals and its way (1 one way, 2 round trip), as the 2012 text layer reads, e.g. 'AMERICAN FORK
#: SILVER LAKE FROM SILVER FLAT TH 4.5 4.4 1.9 2.4 1,660 7536 8,976 None Yes 755 UTAH COUNTY 2'.
_WMC_ROW = re.compile(
    r"(?P<name>[A-Z0-9][A-Z0-9 .,'()&/‐-]*?) (?P<lead>(?:\d+(?:\.\d+)? ){3,4})(?P<ascent>[\d,]+) (?P<trailhead>[\d,]+) "
    r"(?P<max>[\d,]+) (?P<factors>None|[BEMRSX]+) (?P<wilderness>Yes|No) (?P<gain_per_mile>[\d,]+) "
    r"(?P<location>[A-Z][A-Z ]*?) (?P<way>[12])"
)
#: The table's header, which every page of it repeats, and the words the document's first page opens with.
WMC_HEADER = ("Name", "New", "Rating", "RT", "Miles", "Est", "Hrs", "Hiking", "Time", "Total", "Ascent", "TH", "Elev",
              "Max", "Other", "Factors", "Wilderness", "Group Size", "Limit", "Avg Gain", "Per Mile Location",
              "1 = Oneway", "2 = Roundtrip")  # fmt: skip


def _wmc_hike_ratings(facts: PdfFacts, url: str) -> list[dict]:
    """The Wasatch Mountain Club's 'Hiking Trail Database' (WMCHikesCopyToWeb.pdf), its hike ratings table.

    Read 2026-10-04: 5 pages, Last-Modified 2012-09-17, 252,399 bytes, no ETag; the first page is the rating's key
    and its compilers' names, which are people's and not read, and pages 2 to 5 the table, its header repeated on
    each, one hike a line (_WMC_ROW): name, the club's rating, round-trip miles, two hour estimates, total ascent,
    trailhead and highest elevations, the other-factor codes (B boulders or bushwhacking, E over 5,000 ft of change,
    M over 15 miles, R ridgeline or route finding, S scrambling, X exposure), whether a wilderness group-size limit
    applies, average gain a mile, the location and 1 (one way) or 2 (round trip). All but the two hour estimates are
    read: those are the document's pace model ('Hiking at an average pace of 2.0 miles per hour', 'Estimated
    Only!'), and a pace a hiker plans a day by is a figure this pipeline leaves to a source that stands behind it.
    The rating's class (NTD, MOD, MSD, EXT) is a range of the rating the first page states, and the number is what
    lands. The table's 'RT Miles' on a one-way hike (way 1) is that hike's one-way miles as the club measured it,
    landed as stated with its way beside it. Two rows (Perkins Peak from Little Mountain, Twin Lakes from Brighton
    Lakes TH) state three of the four leading figures, and which cell is empty the text does not say, so their rating
    and miles land as unknown; 155 rows state all four. A line after the header that is not a row, or no row at all,
    raises.
    """
    found = lines(facts)
    try:
        start = found.index("Name")
    except ValueError:
        raise PdfLayoutChanged("wmc: the PDF has no 'Name' header") from None
    rows = []
    for line in found[start:]:
        if line in WMC_HEADER or line.startswith("=== "):
            continue
        row = _WMC_ROW.fullmatch(line)
        if row is None:
            raise PdfLayoutChanged(f"wmc: {line[:80]!r} is neither the table's header nor one of its rows")
        lead = row["lead"].split()
        # four leading figures are the rating, the miles and the two hour estimates; a row with three has one cell
        # empty and does not say which, so its rating and miles are unknown rather than guessed
        rating, miles = (lead[0], lead[1]) if len(lead) == 4 else (None, None)
        rows.append(
            {
                "name": fact(row["name"]),
                "place": fact(row["location"]),
                "distance_mi": float(miles) if miles else None,
                "distance_text": f"{miles} RT Miles" if miles else None,
                "elevation_gain_ft": float(row["ascent"].replace(",", "")),
                "elevation_gain_text": f"{row['ascent']} Total Ascent",
                "route_type": "one way" if row["way"] == "1" else "round trip",
                "difficulty": rating,
                "trailhead_elevation_ft": float(row["trailhead"].replace(",", "")),
                "max_elevation_ft": float(row["max"].replace(",", "")),
                "other_factors": None if row["factors"] == "None" else row["factors"],
                "wilderness_group_limit": row["wilderness"],
                "gain_per_mile_ft": float(row["gain_per_mile"].replace(",", "")),
                "link": url,
                "source_url": url,
            }
        )
    if not rows:
        raise PdfLayoutChanged("wmc: the table holds no row")
    return rows


#: A map panel's title in GMC's tracker ('Big Rock to Styles Peak'), which names a stretch of the Long Trail, not a side
#: trail: two places joined by 'to', and no trail word.
_GMC_PANEL = re.compile(r"[A-Z][\w’'. -]+ to [A-Z][\w’'. -]+")
_GMC_TRAIL_WORD = re.compile(r"\b(Trail|Spur|Loop|Cutoff|Link|Connector|Bypass|Extension)\b")
_GMC_STATED = re.compile(r"hiking all (\d+) designated Long Trail side trails")


def _gmc_side_to_side(facts: PdfFacts, url: str) -> list[dict]:
    """The Green Mountain Club's Long Trail Side-to-Side Tracker (Long-Trail-Side-to-Side-Tracker.pdf), a Canva form.

    Read 2026-10-04: 4 pages, Last-Modified 2026-08-12, an ETag. The Side-to-Side Challenge is 'hiking all 88
    designated Long Trail side trails (166 miles)'; the tracker lists them in tables headed 'Trail Date(s) Comments',
    one name a line, divided by the Long Trail Map's 8 panels. The text layer sets some panels' titles ('Big Rock to
    Styles Peak') before their trails and some after, so a trail's panel cannot be read reliably and is not; a
    title is told from a trail by _GMC_PANEL. Two placeholder lines ('*Stratton Ski Area trails') are left out. The
    names are read and held to the count the document states, so a redrawn tracker that loses or gains a line
    refuses rather than lands the wrong list. The form's fields (name, date) are a hiker's and are never read; the
    PDF's /Author names a person and no metadata field lands but the dates.
    """
    found = lines(facts)
    stated = next((int(m.group(1)) for line in found if (m := _GMC_STATED.search(line))), None)
    names, inside = [], False
    for line in found:
        if line == "Trail Date(s) Comments":
            inside = True
            continue
        if line.startswith(("Total mileage", "Hiker Information")):
            break
        if not inside or line.startswith("*"):
            continue
        if _GMC_PANEL.fullmatch(line) and not _GMC_TRAIL_WORD.search(line):
            continue
        if line.startswith(("Long Trail Side-to-Side Tracker", "The Green Mountain Club recognizes")):
            inside = False
            continue
        names.append(line)
    if stated is None or len(names) != stated:
        raise PdfLayoutChanged(f"gmc: the tracker lists {len(names)} side trails and states {stated}")
    return [
        {
            "challenge": "Long Trail Side-to-Side Challenge",
            "name": fact(name),
            "item_type": "side trail",
            "link": url,
            "source_url": url,
        }
        for name in names
    ]


_NBATC_ENTRY = re.compile(r"(?P<number>\d{1,2}) (?P<rest>.+)")
_NBATC_MILE = re.compile(r"\(@ ?(?P<text>[^)]+)\)")
#: Where an entry's description starts, when the text layer runs it onto the name's line ('Matts Creek Connects AT
#: with US 501 ...').
_NBATC_DESCRIPTION = re.compile(r" (Connects|Loop Trail with) ")


def _nbatc_blue_blazer(facts: PdfFacts, url: str) -> list[dict]:
    """The Natural Bridge A.T. Club's Blue Blazer Program form (home.nbatc.org/pdfs/BlueBlazeTrailHike.pdf).

    Read 2026-10-04: 3 pages, Last-Modified 2026-07-09, no ETag, 79,282 bytes. Page 1 is the program's rules and a
    hiker's form (name, signature, e-mail, telephone, address), whose fields are never read, beside a club officer's
    e-mail address, which is not either. Pages 2 and 3 are the table: each blue-blazed trail numbered, its name, the
    A.T. mile north of Black Horse Gap where it joins ('(@ 1.8 mi.)'; two on some), a description, and its '88
    Milers #'. The number, the name (a name the text layer wraps onto a second line is joined) and the mile are
    read; the description is the club's prose. The entries must run 1, 2, 3 ... without a gap, or the family
    refuses. A note under the table records why a trail was taken off the list ('The Little Rocky Row Trail hike ...
    later deleted because the NBATC believed hiking this trail, puts hikers at risk ...'); it is the club's prose
    and is not read here.
    """
    found = lines(facts)
    try:
        start = next(i for i, line in enumerate(found) if line.startswith("No. Name"))
    except StopIteration:
        raise PdfLayoutChanged("nbatc: the PDF has no 'No. Name' table header") from None
    rows: list[dict] = []
    current = None
    for line in found[start + 1 :]:
        if line.startswith(("Total Miles", "*Do not duplicate")):
            break
        entry = _NBATC_ENTRY.fullmatch(line)
        if entry and int(entry["number"]) == len(rows) + 1:
            name = _NBATC_DESCRIPTION.split(entry["rest"], maxsplit=1)[0]
            current = {"number": int(entry["number"]), "name": name, "mile": None, "complete": name != entry["rest"]}
            rows.append(current)
            continue
        if current is None:
            continue
        mile = _NBATC_MILE.fullmatch(line)
        if mile and current["mile"] is None:
            current["mile"], current["complete"] = mile["text"], True
        elif not current["complete"] and not line.startswith(("Connects", "Loop Trail")):
            current["name"] = f"{current['name']} {line}"
        else:
            current["complete"] = True
    if not rows:
        raise PdfLayoutChanged("nbatc: the table holds no numbered trail")
    out = []
    for row in rows:
        at_mile, at_mile_text = single_miles(row["mile"]) if row["mile"] else (None, None)
        out.append(
            {
                "challenge": "Blue Blazer Program",
                "name": fact(row["name"]),
                "item_type": "blue-blazed trail",
                "number": row["number"],
                "at_mile": at_mile,
                "at_mile_text": at_mile_text,
                "link": url,
                "source_url": url,
            }
        )
    return out


_TTA_TITLE = re.compile(r".*'s (?P<count>\d+) Great Hikes")
_TTA_LIST_START = "I attest to having hiked all the trails listed above:"


def _tta_great_hikes(facts: PdfFacts, url: str) -> list[dict]:
    """The Tennessee Trails Association's 36 Great Hikes qualification form ('I hiked 'em all'), one page.

    Read 2026-10-04: Last-Modified 2020-12-21, an ETag, 95,680 bytes; tennesseetrails.org's robots.txt asks
    `Crawl-delay: 60`. The form is titled for the person the hikes are named after ("<name>'s 36 Great Hikes"), which
    no row carries; its fields (a hiker's name, address, e-mail and telephone) are blank and never read. The text
    layer sets the hikes after the attestation line, one a line, most a park and a trail joined by a dash ('Fall
    Creek Falls – Cable Trail'). Each name is read as written; a name the form marks '*' lands with
    `cave_entry_forbidden`, the form's footnote reading "Until the ban is lifted, entry to state owned caves is
    forbidden due to the presence of white nose syndrome in the resident bat population." The hikes are held to the
    count in the title, so a redrawn form refuses rather than lands a different list.
    """
    found = lines(facts)
    title = next((m for line in found if (m := _TTA_TITLE.fullmatch(line))), None)
    try:
        start = found.index(_TTA_LIST_START)
    except ValueError:
        raise PdfLayoutChanged("tta: the form has no attestation line before its list") from None
    names = found[start + 1 :]
    if title is None or len(names) != int(title["count"]):
        raise PdfLayoutChanged(f"tta: the form lists {len(names)} hikes and its title states {title and title['count']}")
    return [
        {
            "challenge": "36 Great Hikes",
            "name": fact(name.rstrip("*")),
            "item_type": "hike",
            "cave_entry_forbidden": name.endswith("*"),
            "link": url,
            "source_url": url,
        }
        for name in names
    ]


#: Every document family's parser, by the registry key (or the `family`) its resource names.
PDF_FAMILIES: dict[str, PdfFamily] = {
    "rmc_recommended_hikes": PdfFamily(_rmc_recommended_hikes, columns={"time_text": "text"}),
    "wmc_hike_ratings": PdfFamily(
        _wmc_hike_ratings,
        columns={
            "trailhead_elevation_ft": "double",
            "max_elevation_ft": "double",
            "other_factors": "text",
            "wilderness_group_limit": "text",
            "gain_per_mile_ft": "double",
        },
    ),
    "gmc_side_to_side": PdfFamily(_gmc_side_to_side),
    "nbatc_blue_blazer": PdfFamily(_nbatc_blue_blazer, columns={"number": "bigint", "at_mile": "double", "at_mile_text": "text"}),
    "tta_great_hikes": PdfFamily(_tta_great_hikes, columns={"cave_entry_forbidden": "bool"}),
}
