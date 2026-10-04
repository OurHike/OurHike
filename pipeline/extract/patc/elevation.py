"""Potomac Appalachian Trail Club: elevation, published as A.T.-corridor contours, not registered in
decision 54's wave 1.

Contours are vectors, so decision 35 does not cover them, but no mart reads them and they are
background-map material: decision 54's wave 1 registers none, and loading them is the maintainer's
call (decided 2026-10-03). PATC's two contour layers are 19,311 lines (re-counted 2026-10-03). They
are ArcGIS, the lead's to route with decision 54's wave 1 layers.

The hikethetuscarora.org section guides (decision 54's wave 5, read 2026-10-04) give each of the 22
sections a maximum and a minimum elevation and no place for either: patc_tuscarora_sections
(patc/suggested_hikes.py, section K) lands both as facts of the section, and
patc_tuscarora_points (patc/points_of_interest.py) lands the pages' fixes. A section's extremes are
not samples: int_elevation__club_samples holds one elevation at one point, and these have no point,
so no elevation resource reads the pages. Section 10's stated maximum (395 ft) is below its minimum
(415 ft), as patc_tuscarora_sections' notes record.

Recommend not loading (Reasoned). USGS 3DEP is the elevation source, and contours would add bytes
without adding information. The contours' own source is not stated (Unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 4),
    checked=(
        "re-read 2026-10-03: `Contours_5ft_2ft_AT/FeatureServer` (item 999edce773394454aa554df8816b9e7d) on "
        "PATC's own organization, 'Potomac Appalachian Trail Club GIS': layer 0 '2_ft_Countour_AT' 13,762 "
        "polylines and layer 1 '5_ft_Countour_AT' 5,549, both hasZ false, edited 2022-05-09, fields FID, Id, "
        "Contour, Shape__Length and GlobalID; the contours' source is not stated",
        "`Contours_5ft_2ft_AT/0`: 13,762 two-foot contour polylines (layer 1 holds the five-foot set), "
        "2022-05-09. The hikethetuscarora.org section guides give max/min elevation per section (page)",
        "hikethetuscarora.org's seven section pages, read 2026-10-04 after robots.txt (no Crawl-delay for our "
        "agent): 'Max Elevation: 1620 ft. Min Elevation: 930 ft.' and the like, one pair a section, with no "
        "place; read as section facts by patc_tuscarora_sections",
    ),
    where=(
        "https://services7.arcgis.com/BbnVmymrKxjFL0SO/arcgis/rest/services/Contours_5ft_2ft_AT/FeatureServer",
        "https://hikethetuscarora.org",
    ),
    reason=(
        "vector contours, not registered in decision 54's wave 1: background-map material that decision 35 "
        "does not cover, so loading them is the maintainer's call; checked gives the measured counts"
    ),
)
