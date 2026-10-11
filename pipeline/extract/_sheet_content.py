"""Section K's hand-back: the challenges and suggested hikes a club publishes as an Excel workbook, one parser per
workbook family, beside extract/_pdf_content.py's PDFs.

Section K of decision 54 left two workbooks unread because the extract job could not open one: the Smoky Mountains
Hiking Club's 900 Miler trail list, an .xls, and the Wasatch Mountain Club's hike ratings, an .xlsx.
requirements-extract.in now pins a reader for each, xlrd for the old binary .xls and openpyxl for .xlsx, and says
why those two.

    content_sheet(key)        a club's workbook, one row per item its family's parser (SHEET_FAMILIES) reads

THE CELLS OF ONE SHEET, NEVER THE FILE'S PROPERTIES. A workbook's document properties name people: both workbooks
read on 2026-10-10 name their author and the person who last saved them, and WMC's cover sheet names its compilers.
So a family names the one sheet it reads, sheet_cells() opens that sheet alone, and nothing here reads a property.
A row is extract/_pages_content.py's TYPE_COLUMNS allowlist plus the family's own columns, held by checked_row():
facts and the link, never the club's prose (decision 55), and a text value past its MAX_FACT_CHARS raises.

REFUSED RATHER THAN RELABELLED, lib/club_pdfs.py's rule as extract/_pdf_content.py keeps it: a family reads the
header it was written for, and a sheet whose header moved, or that reads as no item, raises SheetLayoutChanged, so a
reordered sheet never lands a column under another's name.

THE CHANGE CHECK and ONE READ A RUN are ContentPdf's, which ContentSheet inherits: a conditional GET with the file's
own validators, a 304 FRESH; on a 200 its ETag, else its Last-Modified with its Content-Length, and UNKNOWN where the
host sends neither. The check's answer is kept for the read, every request passes polite() at the host's
Crawl-delay, and a wall or a redirect to a host the row does not name in `redirect_hosts` raises.

THE COUNT is the items the family reads out of the same file the rows come from (exact_proof), and proves no zero.
Where the workbook states a total of its own, the family checks its rows against it too: SMHC's sheet sums its
trails' miles.

NO FIXTURE: fixture mode serves an answer as text and a workbook is binary, so these tables are never in CI's
warehouse, as a PDF's are not (make_dbt_staging.py's Table.read_from_pdf), and their base models read no rows there
(dbt/macros/raw_or_empty.sql). tests/test_extract_sheet_content.py runs each family over cells shaped as the live
workbooks were, and opens a workbook of each format. The lane is the type's, monthly.
"""

from __future__ import annotations

import hashlib
import io
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime

from extract._notices import _recall
from extract._pages_content import TYPE_COLUMNS, checked_row, fact, guarded_get
from extract._pdf_content import ContentPdf, PdfLayoutChanged


class SheetLayoutChanged(PdfLayoutChanged):
    """A workbook that no longer reads as the layout its family's parser was written for: refused, never relabelled."""


#: The workbook's own manifest, on every row a workbook yields: where it was read, what its host said of it, and the
#: sheet read. Never a document property, which names people (the module docstring).
SHEET_DOCUMENT_COLUMNS = {
    "document_url": "text",
    "document_etag": "text",
    "document_last_modified": "text",
    "document_bytes": "bigint",
    "document_sha256": "text",
    "document_sheet": "text",
}

#: The first bytes of each format, by which a workbook is opened: an .xls is an OLE2 compound file, an .xlsx a zip.
OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_SIGNATURE = b"PK\x03\x04"


@dataclass(frozen=True)
class SheetFamily:
    """One workbook family: the one sheet it reads, how that sheet's cells become rows, and the columns it adds.

    `read(cells, url)` takes the sheet as rows of cell values (sheet_cells(): a number as a float or an int, a date
    as a datetime, an empty cell as None, text stripped) and returns the rows; it raises SheetLayoutChanged on a
    layout it was not written for."""

    sheet: str
    read: Callable[[list[list], str], list[dict]]
    columns: dict[str, str] = field(default_factory=dict)


def _cell(value):
    """One cell as both readers are made to agree: text stripped, and an empty string as None."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def sheet_cells(content: bytes, sheet: str, url: str) -> list[list]:
    """The named sheet's cells, row by row, from an .xls (xlrd) or an .xlsx (openpyxl), chosen by the file's own
    first bytes, never its name or its Content-Type. Only that sheet is read, and no property. Raises
    SheetLayoutChanged for a file in neither format, or one without the sheet."""
    if content.startswith(OLE2_SIGNATURE):
        import xlrd

        book = xlrd.open_workbook(file_contents=content, on_demand=True)
        if sheet not in book.sheet_names():
            raise SheetLayoutChanged(f"{url}: no sheet {sheet!r} (it holds {book.sheet_names()})")
        found = book.sheet_by_name(sheet)
        rows = []
        for r in range(found.nrows):
            row = []
            for c in range(found.ncols):
                cell = found.cell(r, c)
                if cell.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate.xldate_as_datetime(cell.value, book.datemode))
                elif cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    row.append(None)
                else:
                    row.append(_cell(cell.value))
            rows.append(row)
        return rows
    if content.startswith(ZIP_SIGNATURE):
        import openpyxl

        book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        try:
            if sheet not in book.sheetnames:
                raise SheetLayoutChanged(f"{url}: no sheet {sheet!r} (it holds {book.sheetnames})")
            return [[_cell(value) for value in row] for row in book[sheet].iter_rows(values_only=True)]
        finally:
            book.close()
    raise SheetLayoutChanged(f"{url} is neither an .xls nor an .xlsx by its first bytes, so it is not read")


@dataclass(frozen=True)
class ContentSheet(ContentPdf):
    """A club's workbook, one row per item its family in SHEET_FAMILIES reads: ContentPdf's change check and manners,
    with one sheet's cells in place of a PDF's text layer."""

    @property
    def parser(self) -> SheetFamily:
        return SHEET_FAMILIES[self.family or self.key]

    @property
    def zero_proof(self) -> None:
        """None: the count is the items a workbook family's parser reads, and a sheet that reads as none raises first."""
        return None

    @property
    def columns(self) -> dict[str, str]:
        if self.type not in TYPE_COLUMNS:
            raise ValueError(f"{self.key}: a content sheet reader feeds {sorted(TYPE_COLUMNS)}, not {self.type}")
        return {**TYPE_COLUMNS[self.type], **self.parser.columns, **SHEET_DOCUMENT_COLUMNS}

    def _urls(self) -> list[str]:
        """The workbook this resource reads: its registry row's url, one file."""
        return [self.url]

    def rows(self, proofs: dict[str, int]):
        kept = _recall(self.table)
        response = (kept if isinstance(kept, dict) else {}).get(self.url)
        if response is None or response.status_code != 200:
            response = guarded_get(self, self.url)
        found = self.parser.read(sheet_cells(response.content, self.parser.sheet, self.url), self.url)
        if not found:
            raise SheetLayoutChanged(f"{self.key}: {self.url} reads as no item, which is a changed layout")
        document = {
            "document_url": self.url,
            "document_etag": response.headers.get("ETag"),
            "document_last_modified": response.headers.get("Last-Modified"),
            "document_bytes": len(response.content),
            "document_sha256": hashlib.sha256(response.content).hexdigest(),
            "document_sheet": self.parser.sheet,
        }
        rows = [checked_row(self.key, self.type, self.columns, {**row, **document}) for row in found]
        proofs[self.table] = len(rows)
        yield from rows


def content_sheet(key: str, *, family: str | None = None, crawl_delay: float = 0.0, **overrides) -> ContentSheet:
    """A ContentSheet for a registry key; `crawl_delay` is the host's robots.txt Crawl-delay, as its live read found."""
    resource = ContentSheet(key=key, family=family or key, crawl_delay=crawl_delay, **overrides)
    if resource.family not in SHEET_FAMILIES:
        raise KeyError(f"{key}: extract/_sheet_content.py's SHEET_FAMILIES has no family {resource.family!r}")
    resource.url  # an unregistered key fails at import, in the layout test
    return resource


# --- The families ---------------------------------------------------------------------------------------------------


def number(value) -> float | None:
    """A cell that holds a finite number, as a float; None for anything else (an empty cell, text, a date)."""
    if isinstance(value, bool) or isinstance(value, datetime | date) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


#: SMHC's header, the rows above its first trail (the sheet read 2026-10-10), by (row, column) from zero. Each cell
#: named here must read as written, or the sheet is refused.
SMHC_HEADER = {
    (1, 0): "Trails",
    (1, 3): "Section Miles",
    (1, 4): "Trail Totals",
    (2, 2): "Primary source data (feet)",
}
#: How far the trails' miles may sum from the sheet's own total. The total is Excel's sum of the same cells, so
#: anything past rounding is a trail this parser did not read, or read twice (Reasoned from the sheet's formula
#: column; the two agreed to 0.000001 mi on 2026-10-10).
SMHC_TOTAL_TOLERANCE_MI = 0.01


def _smhc_900_miler(cells: list[list], url: str) -> list[dict]:
    """The Smoky Mountains Hiking Club's 900 Miler Club list: every official trail of Great Smoky Mountains National
    Park, the challenge being to hike them all.

    Read 2026-10-10: one sheet that matters, '900 Mile Club Spreadsheet', 401 rows by 7 columns. Below a three-row
    header (SMHC_HEADER), a trail is a row naming it in column A, with its length in feet in column C where it is one
    section, and its total in miles in column E. A trail of several sections is followed by a row per section, which
    names the section's two ends in column B ('Crib Gap - Russell Field'), with its feet in C and its miles in D. Rows
    at the foot hold the sheet's total in E and nothing else. Column F, 'Date Completed', is a member's own checklist,
    and G their notes: neither is read, so a copy a member filled in never lands. Each trail is one item: its name,
    its total miles as the sheet states them, the feet its sections sum to (or its own, for one section), and how
    many sections it has. The trails' miles must sum to the sheet's own total within SMHC_TOTAL_TOLERANCE_MI.
    """
    for (row, column), expected in SMHC_HEADER.items():
        found = cells[row][column] if row < len(cells) and column < len(cells[row]) else None
        if found != expected:
            raise SheetLayoutChanged(f"smhc: header cell {row + 1}:{column + 1} reads {found!r}, not {expected!r}")
    items: list[dict] = []
    totals: list[float] = []
    for row in cells[3:]:
        name, section, feet, section_miles, trail_miles = (list(row) + [None] * 5)[:5]
        if isinstance(name, str):
            if number(trail_miles) is None:
                raise SheetLayoutChanged(f"smhc: trail {name[:60]!r} states no total in column E")
            items.append({"name": name, "miles": number(trail_miles), "feet": [], "own_feet": number(feet)})
        elif isinstance(section, str):
            if not items or number(feet) is None or number(section_miles) is None:
                raise SheetLayoutChanged(f"smhc: section {section[:60]!r} is not under a trail, or states no length")
            items[-1]["feet"].append(number(feet))
        elif name is None and section is None and feet is None and number(trail_miles) is not None:
            totals.append(number(trail_miles))
        elif any(value is not None for value in (name, section, feet, section_miles, trail_miles)):
            raise SheetLayoutChanged(f"smhc: a row reads {row[:5]!r}, which is neither a trail, a section nor a total")
    if not items:
        raise SheetLayoutChanged("smhc: the sheet lists no trail")
    if not totals:
        raise SheetLayoutChanged("smhc: the sheet states no total to check its trails against")
    summed = sum(item["miles"] for item in items)
    if any(abs(summed - total) > SMHC_TOTAL_TOLERANCE_MI for total in totals):
        raise SheetLayoutChanged(f"smhc: the trails sum to {summed:.2f} mi, and the sheet's totals read {totals}")
    return [
        {
            "challenge": "900 Miler Club",
            "name": fact(item["name"]),
            "place": "Great Smoky Mountains National Park",
            "item_type": "trail",
            "distance_mi": item["miles"],
            "distance_text": f"{item['miles']:.2f} mi Trail Totals",
            "length_ft": sum(item["feet"]) if item["feet"] else item["own_feet"],
            "sections": len(item["feet"]),
            "link": url,
            "source_url": url,
        }
        for item in items
    ]


#: WMC's Hikes sheet header, as read 2026-10-10: its first 18 columns, in order. The 19th is the way's key ('1 =
#: Oneway 2 = Roundtrip', spaced in the sheet), checked by its two words. A sheet whose header differs is refused.
WMC_HEADER = (
    "Name",
    "Destination",
    "Start Location",
    "New Rating",
    "RT Miles",
    "Est Hrs",
    "Hiking Time",
    "Total Ascent",
    "TH Elev",
    "Max Elev",
    "Other Factors",
    "Wilderness Group Size Limit",
    "Avg Gain Per Mile",
    "Mileage Rating",
    "Ascent Rating",
    "Gain Per Mile Rating",
    "Other Factors Rating",
    "Location",
)


def _wmc_hike_ratings(cells: list[list], url: str) -> list[dict]:
    """The Wasatch Mountain Club's Hiking Trail Database workbook (WMCHikesCopyToWeb.xlsx), its Hikes sheet.

    Read 2026-10-10: Last-Modified 2023-06-15, 66,121 bytes, three sheets. Only 'Hikes' is read: 'CoverSheet' names
    the people who compiled the table, and 'DownloadFiles' links each hike's tracks, which are the trail_lines cell's.
    One hike a row under the header (WMC_HEADER and the way's column): its name, destination and start, the club's
    rating, round-trip miles, two hour estimates, total ascent, trailhead and highest elevations, the other-factor
    codes, whether a wilderness group-size limit applies, average gain a mile, the rating's four parts, the location,
    and 1 (one way) or 2 (round trip). The columns landed are those extract/_pdf_content.py's family of the same name
    landed from the 2012 PDF of this table, so the table keeps its shape: the two hour estimates are the document's
    pace model and are not read (a pace a hiker plans a day by is left to a source that stands behind it), nor are
    the rating's parts, which the rating is made from. A cell the sheet leaves empty lands as unknown, never zero.
    A row naming no hike ends the table only when every row after it is empty too.
    """
    header = list(cells[0]) if cells else []
    if tuple(header[: len(WMC_HEADER)]) != WMC_HEADER:
        raise SheetLayoutChanged(f"wmc: the Hikes sheet's header reads {header[: len(WMC_HEADER)]!r}")
    way_header = header[len(WMC_HEADER)] if len(header) > len(WMC_HEADER) else None
    if not isinstance(way_header, str) or "Oneway" not in way_header or "Roundtrip" not in way_header:
        raise SheetLayoutChanged(f"wmc: the way column's header reads {way_header!r}")
    rows = []
    body = cells[1:]
    for index, row in enumerate(body):
        row = (list(row) + [None] * 19)[:19]
        name = row[0]
        if name is None:
            if any(value is not None for later in body[index:] for value in later):
                raise SheetLayoutChanged(f"wmc: row {index + 2} names no hike, and a row after it is not empty")
            break
        if not isinstance(name, str):
            raise SheetLayoutChanged(f"wmc: row {index + 2}'s name is {name!r}")
        way = number(row[18])
        if way not in (1.0, 2.0):
            raise SheetLayoutChanged(f"wmc: {name[:60]!r}'s way is {row[18]!r}, neither 1 nor 2")
        rating, miles, ascent = number(row[3]), number(row[4]), number(row[7])
        factors, wilderness, location = row[10], row[11], row[17]
        rows.append(
            {
                "name": fact(name),
                "place": fact(location) if isinstance(location, str) else None,
                "distance_mi": miles,
                "distance_text": f"{row[4]} RT Miles" if miles is not None else None,
                "elevation_gain_ft": ascent,
                "elevation_gain_text": f"{row[7]} Total Ascent" if ascent is not None else None,
                "route_type": "one way" if way == 1.0 else "round trip",
                # The rating at the one decimal the club printed it to in its 2012 PDF: the sheet keeps the formula's
                # unrounded result. All 155 hikes both rate agree so (measured 2026-10-10).
                "difficulty": None if rating is None else f"{rating:.1f}",
                "trailhead_elevation_ft": number(row[8]),
                "max_elevation_ft": number(row[9]),
                "other_factors": None if factors in (None, "None") else fact(str(factors)),
                "wilderness_group_limit": fact(wilderness) if isinstance(wilderness, str) else None,
                "gain_per_mile_ft": number(row[12]),
                "link": url,
                "source_url": url,
            }
        )
    if not rows:
        raise SheetLayoutChanged("wmc: the Hikes sheet holds no hike")
    return rows


#: Every workbook family's parser, by the registry key (or the `family`) its resource names.
SHEET_FAMILIES: dict[str, SheetFamily] = {
    "smhc_900_miler_trails": SheetFamily(
        "900 Mile Club Spreadsheet", _smhc_900_miler, columns={"length_ft": "double", "sections": "bigint"}
    ),
    "wmc_hike_ratings": SheetFamily(
        "Hikes",
        _wmc_hike_ratings,
        columns={
            "trailhead_elevation_ft": "double",
            "max_elevation_ft": "double",
            "other_factors": "text",
            "wilderness_group_limit": "text",
            "gain_per_mile_ft": "double",
        },
    ),
}
