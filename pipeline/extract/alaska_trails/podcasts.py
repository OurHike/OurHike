"""Alaska Trails: podcasts, nothing published (coverage audit 2026-10-01, batch b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Site navigation and `/trail-tales`, which is live storytelling at the Anchorage Museum. No podcast, "
        "Spotify, Anchor or Apple strings on the pages read.",
    ),
    where=(
        "https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services",
        "https://alaska-trails.org/",
    ),
)
