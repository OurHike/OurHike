"""Mountains to Sound Greenway Trust: podcasts, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "REST search `podcast` returns only oral-history pages and blog posts.",
        "Skeptic: REST search `audio` returns oral-history posts and one itinerary. The `yt-embeds` type holds "
        '1 video. The Apple directory for "Mountains to Sound Greenway" returns 8 shows, none of them the '
        "Trust's.",
    ),
    where=(
        "https://gis.dnr.wa.gov/site3/rest/services",
        "https://services.arcgis.com/b2nA3bRpH9jJyZOr/arcgis/rest/services",
        "https://mtsgreenway.org/",
    ),
)
