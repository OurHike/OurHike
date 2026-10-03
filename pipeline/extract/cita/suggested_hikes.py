"""Central Iowa Trail Association: suggested hikes, nothing published (coverage audit 2026-10-01, batch
c5_regional_2).

(Skeptic, 2026-10-01: `sitemap.xml` (121 URLs) read in full. Nothing in it is a route or hike
description; `/ride-with-us` and `/monday-night-dirt-rides` are group rides. The verdict stands.)

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "The area pages describe parks, not routes. `/latest-news?format=rss` has 11 items, newest 2026-05-06, "
        "none of them routes.",
    ),
    where=(
        "https://services.arcgis.com/HT7H9QGiZQoRJDpJ/arcgis/rest/services",
        "https://bikecita.org/",
    ),
)
