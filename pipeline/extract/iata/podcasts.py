"""Ice Age Trail Alliance: podcasts, nothing published (coverage audit 2026-10-01, batch c10_nst_rest).

The 180-day recheck (decision 14) should look for that project. Skeptic, kept NOT_PUBLISHED: iTunes
podcast searches for "Ice Age Trail Alliance", "Ice Age Trail" and "Ho-Chunk Ice Age" find no
IATA-produced show. An ArcGIS search of `owner:a personal ArcGIS account for "podcast OR audio"
returns 0 …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Web search finds guest appearances only (the "Hike" podcast; Outdoor Adventure Series; WXPR "Explore '
        'Up North" 2022-10-20). It also finds mention of an "Inclusive Storytelling podcast" project with the '
        "Ho-Chunk Nation that may be in development.",
    ),
    where=(
        "https://dnrmaps.wi.gov/arcgis/rest/services",
        "https://iceagetrail.org/",
    ),
)
