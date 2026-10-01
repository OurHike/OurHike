"""Tidewater Appalachian Trail Club: elevation, published, and not landed (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Recommend not loading it (Reasoned). These are 2009 spot heights in a PDF, and USGS 3DEP (`_shared`)
covers the same ground. The matrix also names Gid Spring, which is a water point ATC's layers lack,
but it has no coordinates.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf` (PDF, 74 "
        'KB), "A.T. Distances and Elevations – from Paul Wolf Shelter to Priest Shelter", a named individual, '
        "rev. 2009-02-20: a 14-landmark distance matrix plus 10 spot elevations (Reeds Gap 2,645 ft, Three "
        "Ridges 3,970 ft, Tye River 997 ft, Priest Shelter 4,063 ft…). Linked from `/tatc-education/`",
    ),
    where=(
        "https://tidewateratc.com/wp-content/uploads/2026/01/AT-Distances-and-Elevation-Info.pdf",
        "https://tidewateratc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
