"""Green Mountain Club: suggested hikes, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

The REST content is prose with no GPX (2 of 57 mention a map or coordinates). The route may be
recoverable from the web maps' "Featured" layer definition (@unvalidated).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "WP REST `https://greenmountainclub.org/wp-json/wp/v2/hikes`: 57 hikes (newest 2026-09-30). Taxonomies:"
        " `difficulty`, `distance`, `hike-type`, `region`, `hike-feature` (11 terms, e.g. Day Hiking 48, Views "
        '48, Summits 27, 4,000 Footers 18). Also the ArcGIS dashboards "Suggested Day Hikes" (`f86d3dfc…`) and '
        '"Suggested Section Hikes" (`d0fa7da2…`), and the web maps Day Hikes and Section Hikes, which draw a '
        "featured hike from `TRAIL_MASTER`.",
    ),
    where=(
        "https://greenmountainclub.org/wp-json/wp/v2/hikes",
        "https://greenmountainclub.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
