"""Trailkeepers of Oregon: podcasts, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'REST search `podcast` finds only TKO\'s guest spots on others\' shows: "Explore Oregon Podcast" and "Peak Northwest".',
        'Skeptic: the Apple directory for "Trailkeepers of Oregon" and "Oregon Hikers" returns 16 shows, none of them TKO\'s.',
    ),
    where=(
        "https://services3.arcgis.com/3g7oRa9lIIf3eCBb/arcgis/rest/services",
        "https://trailkeepersoforegon.org/",
    ),
)
