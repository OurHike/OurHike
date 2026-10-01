"""North Country Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch b7_long_trails_states).

Format: arcgis + page. The ArcGIS hikes are stale (2016, 2023 event). The live candidate is the
chapter pages. Someone with a browser should confirm the section exists before
`ncta/suggested_hikes.py` scrapes it.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'WordPress search for "featured hike", "great hikes", "itinerar" and "day hikes" returned only news '
        "posts and event write-ups.",
        'Skeptic adds: (1) ArcGIS, owner `nctgis`: the MapTour app "Mineral Springs and Waterfall Hike - North '
        'Dakota" (`cfc67e8a7fc74e039dfd29822acbbba2`, 2016-09-28) and its web map "ND Waterfall Hike". (2) The '
        "feature service `2023___Transportation_and_Hike_Mapping/FeatureServer/0`: 24 points with `Hike`, "
        "`Day`, `Parking_Location`, `Start_Times`, last edit 2023-05-23. These are the 2023 Celebration's event"
        " hikes. (3) A web search excerpt of …",
    ),
    where=(
        "https://services2.arcgis.com/UfGVyqUm4GHa2zrj/arcgis/rest/services/2023___Transportation_and_Hike_Mapping/FeatureServer/0",
        "https://northcountrytrail.org/",
        "https://northcountrytrail.org/trail/north-dakota/dpc/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
