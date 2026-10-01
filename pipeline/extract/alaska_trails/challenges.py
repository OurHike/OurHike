"""Alaska Trails: challenges, nothing published (coverage audit 2026-10-01, batch
b7_long_trails_states).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Homepage navigation (35 links): no patch, peak-list or completion programme.",
        "Skeptic adds: none of the 90 ArcGIS items is a challenge. A web search turns up Alaska challenges (the"
        " 12-Peak Challenge, the Alaska Mountain Wilderness Classic), but none is run by Alaska Trails. Apple "
        'Podcasts searches for "Alaska Trails" and "Alaska Long Trail" (16 shows) found none of Alaska Trails\' '
        "own, which supports the podcasts row too.",
    ),
    where=("https://services.arcgis.com/E4aLbdRuC2azR6Sw/arcgis/rest/services",),
)
