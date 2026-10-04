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

The note this replaces read, whole:

Potomac Appalachian Trail Club: points of interest, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

The 14 Tuscarora shelters and the cabins are new to us (ATC's layer covers the A.T. only, Reasoned). Cabins are
under the Council-authorization term. Per the item text, 25 of 42 rentable cabins are members-only.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.

Its `checked` (confirmed 2026-10-01): `PATC_Shelters_AT_and_TT_2_view/0`: 47 (32 "Official A.T. Shelter", 14
"T.T. Shelter", 1 other; 2024-09-25; food-storage fields, no capacity). `Cabin_Locations/0`: 49 cabins (26
primitive, 14 modern, 7 semi-primitive; `Capacity`, `Hike_In`, `AT_Access`, costs, booking link; 2026-03-10).
`Cabin_Parking/0` 21 (2020). `Map_9_Revisted_2019_2020_POIs/0` 778 GPS-ranger waypoints (junctions, crossings,
blowdowns, about 28 springs; 2021-11). `Bull_Run_Occoquan_Trail/0` 112. `/shelters` page lists water facts, e.g.
"Charlie Irvin Shelter (no water)"

Its `where`: https://services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services
https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services https://patc.net/

Its `reason`: published and not landed: no sources.json row registers it, and a builder takes a registered key
"""

from extract._pages_points import page_points

CLAIMS = ("patc_tuscarora_points",)
RESOURCES = [page_points("patc_tuscarora_points")]
