"""Wasatch Mountain Club: suggested hikes, its Hiking Trail Database PDF read here (decision 54 wave 4,
section K, 2026-10-04).

- `wmc_hike_ratings`: /hike/WMCHikesCopyToWeb.pdf, the HIKES tab of the club's hike-ratings spreadsheet as a PDF,
  157 hikes, each its rating, miles, ascent, trailhead and highest elevations, other-factor codes, whether a
  wilderness group-size limit applies, average gain a mile, location and way. The table's two hour estimates are
  its pace model and are not read. wasatchmountainclub.org's robots.txt asks `Crawl-delay: 10`.

The reader is extract/_pdf_content.py's ContentPdf with the `wmc_hike_ratings` family: a conditional GET with the
file's own validators (Last-Modified 2012-09-17 with its Content-Length; the host sends no ETag), facts and the link
only. Its row in sources.json holds the terms as found, the live read and the measured key, the hike's name and
its total ascent.

The spreadsheet itself (WMCHikesCopyToWeb.xlsx, Last-Modified 2023-06-15, 66,121 bytes) is not read: the extract
venv has no spreadsheet reader, and adding one is a dependency the maintainer decides (requirements.in's note on
pypdf). Whether its HIKES tab still matches the 2012 PDF is unchecked. The 156 GPX and 157 KMZ tracks are the
trail_lines cell's, and /trip-reports are members' writing.
"""

from extract._pdf_content import content_pdf

CLAIMS = ("wmc_hike_ratings",)
RESOURCES = [content_pdf("wmc_hike_ratings", crawl_delay=10.0)]
