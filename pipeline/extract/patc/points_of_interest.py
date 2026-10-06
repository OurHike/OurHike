"""Potomac Appalachian Trail Club: points of interest, the Tuscarora Trail's road access and camping off the
club's section pages (decision 54 wave 5, section S, read 2026-10-04).

- `patc_tuscarora_points`: hikethetuscarora.org's seven section pages, 22 sections, each section's Access and
  Camping paragraphs read for their fixes: 55 access points, 15 shelters and 10 camping places, 80 rows, a
  point at a section's end once for each section that lists it. The 14 Tuscarora shelters are new to us: ATC's
  layer covers the A.T. only (Reasoned).

The reader is extract/_pages_points.py's PagePoints with the `patc_tuscarora_points` site parser. The same pages
are read by patc_tuscarora_sections (patc/suggested_hikes.py, section K) for each section's span and elevations,
which is a second dataset of one upstream. patc.net/shelters, PATC's list of the shelters it maintains, gives
mileage between shelters and no fix, so it is not read; its one water fact, 'Charlie Irvin Shelter (no water)',
is quoted on the row.

Not read here: PATC's ArcGIS layers, which the old note below lists. They are ArcGIS, the lead's to wire with
decision 54's wave 1 layers.
"""

from extract._pages_points import page_points

CLAIMS = ("patc_tuscarora_points",)
RESOURCES = [page_points("patc_tuscarora_points")]
