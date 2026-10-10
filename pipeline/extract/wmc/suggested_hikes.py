"""Wasatch Mountain Club: suggested hikes, its Hiking Trail Database workbook read here (decision 54 wave 4, section
K, 2026-10-04; read from the workbook since section K's hand-back, 2026-10-10).

- `wmc_hike_ratings`: /hike/WMCHikesCopyToWeb.xlsx, the club's hike-ratings spreadsheet, its Hikes sheet, 157 hikes,
  each its rating, miles, ascent, trailhead and highest elevations, other-factor codes, whether a wilderness
  group-size limit applies, average gain a mile, location and way. The two hour estimates are its pace model and
  are not read, nor are the rating's parts. wasatchmountainclub.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_sheet_content.py's ContentSheet with the `wmc_hike_ratings` family: a conditional GET with the
file's own validators (Last-Modified 2023-06-15 with its Content-Length; the host sends no ETag), openpyxl for the
.xlsx, and the one sheet 'Hikes' read: 'CoverSheet' names the people who compiled the table, and no property of the
file is read either. Facts and the link only. Its row in sources.json holds the terms as found, the live read and
the measured key, the hike's name and its total ascent.

Until 2026-10-10 the extract read the 2012 PDF of this table (extract/_pdf_content.py's family of the same name),
because it could open no workbook. The PDF is an export of the same table, so it is a SAME_AS copy now, never a
second read: the same 157 hikes, figure for figure, but for the two whose miles its text leaves unreadable and the
workbook states. The 156 GPX and 157 KMZ tracks are the trail_lines cell's, and /trip-reports are members' writing.
"""

from datetime import date

from extract._contract import SameAs
from extract._sheet_content import content_sheet

CLAIMS = ("wmc_hike_ratings",)
RESOURCES = [content_sheet("wmc_hike_ratings", crawl_delay=10.0)]

SAME_AS = (
    SameAs(
        original="wmc_hike_ratings",
        copy=("https://www.wasatchmountainclub.org/hike/WMCHikesCopyToWeb.pdf",),
        confirmed=date(2026, 10, 10),
        checked=(
            "Both read on 2026-10-10, the PDF (Last-Modified 2012-09-17, 252,399 bytes) by extract/_pdf_content.py's "
            "wmc_hike_ratings family and the workbook (Last-Modified 2023-06-15) by extract/_sheet_content.py's: 157 "
            "hikes each, all 157 alike on the name (the PDF's U+2010 hyphen read as '-') and the total ascent, and "
            "alike on the way, the trailhead and highest elevations, the location and the other-factor codes; all "
            "155 ratings both state agree to the one decimal the PDF prints. The two rows the PDF leaves without "
            "miles (Perkins Peak from Little Mountain, Twin Lakes from Brighton Lakes TH) are 8.3 and 3.8 in the "
            "workbook.",
        ),
    ),
)
