"""Potomac Appalachian Trail Club: elevation, published as A.T.-corridor contours, not registered in
decision 54's wave 1.

Contours are vectors, so decision 35 does not cover them, but no mart reads them and they are
background-map material: decision 54's wave 1 registers none, and loading them is the maintainer's
call (decided 2026-10-03). PATC's two contour layers are 19,311 lines (re-counted 2026-10-03). The
hikethetuscarora.org section guides' maximum and minimum elevations are web pages, decision 54's
wave 5.

Recommend not loading (Reasoned). USGS 3DEP is the elevation source, and contours would add bytes
without adding information. The contours' own source is not stated (Unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        "re-read 2026-10-03: `Contours_5ft_2ft_AT/FeatureServer` (item 999edce773394454aa554df8816b9e7d) on "
        "PATC's own organization, 'Potomac Appalachian Trail Club GIS': layer 0 '2_ft_Countour_AT' 13,762 "
        "polylines and layer 1 '5_ft_Countour_AT' 5,549, both hasZ false, edited 2022-05-09, fields FID, Id, "
        "Contour, Shape__Length and GlobalID; the contours' source is not stated",
        "`Contours_5ft_2ft_AT/0`: 13,762 two-foot contour polylines (layer 1 holds the five-foot set), "
        "2022-05-09. The hikethetuscarora.org section guides give max/min elevation per section (page)",
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
