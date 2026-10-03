"""Continental Divide Trail Coalition: elevation, sold rather than published (coverage audit 2026-10-01, batch
b7_long_trails_states).

The CDT's elevation charts are in the CDT Map Set, which CDTC sells; the free
section PDFs off the Interactive Map are maps, and none of CDTC's 133 ArcGIS
items is an elevation layer. A sold product is not something this pipeline
loads, so 3DEP (_shared/usgs/) is the profile. Not re-read for decision 54.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Format pdf. The CDT Map Set v4.0 "includes topographic data, elevation charts" (maps-and-data page, '
        "via WebFetch). It is sold through the NeonCRM store; free section PDFs come off the Interactive Map "
        "(`Mapset_Pages/0`). No elevation layer among the 133 items.",
    ),
    where=("https://services.wygisc.org/HostGIS/rest/services",),
    reason="sold, not published: the elevation charts are in a map set CDTC sells",
)
