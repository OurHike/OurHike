"""Parsers for the club-published PDFs sources.json registers as
`kind: "club_pdf"` (#669) - one function per document that has earned one,
dispatched by registry key from PARSERS at the bottom.

Pure module: text in, rows out, no I/O and no pypdf import - fetch_club_pdfs.py
owns the download and the text extraction, so these functions can be tested
against strings and re-run against cached text without a PDF library in sight.

THE POSTURE IS build_shelter_capacity.py's, FOR THE SAME REASON. A club PDF is
a print of somebody's spreadsheet, and a layout that quietly changes must stop
the build rather than relabel one column as another. Every parser here fails
loudly on a header it does not recognise and on any line it cannot place -
the enumerated title/footer lines ARE the leniency, and a line outside them is
a document this code has not seen before.

## GATC water sources, and what its text layer can actually support

The printed table has three columns - "Mile Point", "Source Name",
"Distance Off AT" - but the PDF's text layer stores each row as ONE string
("0.2 Springer Mountain Shelter Piped Spring beyond lower bear cables"), single
spaces throughout, and the boundary between the second and third columns is
simply not in the file. Measured rather than assumed (2026-08-13): plain
extraction, layout-mode extraction and per-fragment coordinates all agree -
each row is one fragment, headers included. So the parser keeps `mile` and
`entry` (name and off-trail directions fused, exactly as GATC printed them)
and does not pretend to a column split the bytes cannot support. Guessing the
boundary ("the name probably ends before the first comma") would be wrong on
rows like "Woody Gap .2 E, to left of campsite on Blue Blaze".

The document is two lists in one table: the approach trail's rows first
(miles from Amicalola Falls), then the A.T.'s (GATC miles from Springer,
restarting at 0.2). The restart is the boundary - the one place the mile
sequence may fall - and a second fall is a document shape this parser does
not know, so it raises rather than guessing which list a row belongs to.
"""

from __future__ import annotations

import re

# The GATC table's header, as the text layer flattens it. Its presence is the
# proof this is still the document the parser was written for.
GATC_HEADER = "Mile Point Source Name Distance Off AT"

# Lines that are page furniture rather than data, matched exactly (or by the
# page-footer pattern below). Enumerated so that anything NEW is an error
# rather than silently skipped - see the module docstring.
GATC_FURNITURE = frozenset(
    (
        GATC_HEADER,
        "Water Sources in Georgia",
        "Approach Trail & Appalachian Trail",
        "APPALACHIAN TRAIL",
        "APPROACH TRAIL",
    )
)

GATC_PAGE_FOOTER = re.compile(r"^Page \d+ of \d+$")

GATC_ROW = re.compile(r"^(\d+(?:\.\d+)?)\s+(.+)$")

TRAIL_APPROACH = "approach"
TRAIL_AT = "at"


def parse_gatc_water_sources(page_texts: list[str]) -> list[dict]:
    """The GATC water-sources PDF's rows, as
    {"trail": "approach"|"at", "mile": float, "entry": str}.

    `page_texts` is one extracted-text string per page, in page order.
    Raises ValueError - naming the offending line - on a missing header, a
    line that is neither furniture nor a row, or a mile sequence that falls
    more than once. All three mean the document's shape has changed and a
    human needs to look before anything downstream trusts the output.
    """
    lines = [line.strip() for text in page_texts for line in text.splitlines() if line.strip()]
    if GATC_HEADER not in lines:
        raise ValueError(f"The GATC water PDF no longer carries the header {GATC_HEADER!r} - its layout has changed")

    rows = []
    for line in lines:
        if line in GATC_FURNITURE or GATC_PAGE_FOOTER.match(line):
            continue
        match = GATC_ROW.match(line)
        if match is None:
            raise ValueError(f"Unrecognised line in the GATC water PDF: {line!r} - neither a row nor known furniture")
        rows.append({"mile": float(match.group(1)), "entry": match.group(2)})

    if not rows:
        raise ValueError("The GATC water PDF parsed to zero rows")

    # The approach-trail list comes first; the A.T. list restarts the miles.
    # One fall in the sequence is that restart. Zero falls means the approach
    # block is gone (fine - every row is the A.T.'s). Two means a shape this
    # parser has not seen.
    falls = [index for index in range(1, len(rows)) if rows[index]["mile"] < rows[index - 1]["mile"]]
    if len(falls) > 1:
        positions = ", ".join(f"row {index} (mile {rows[index]['mile']})" for index in falls)
        raise ValueError(f"The GATC water PDF's mile sequence falls more than once ({positions}) - section structure has changed")
    boundary = falls[0] if falls else 0
    for index, row in enumerate(rows):
        row["trail"] = TRAIL_APPROACH if index < boundary else TRAIL_AT
    return rows


# Registry key -> parser. A club_pdf entry with no line here still gets
# fetched (the PDF lands and hashes into the manifest); it just produces no
# rows file until somebody writes its parser - fetch_club_pdfs.py says so out
# loud rather than failing, because fetching-for-review is the kind's whole
# job and a parser is the second step, not the price of entry.
PARSERS = {
    "gatc_water_sources": parse_gatc_water_sources,
}
