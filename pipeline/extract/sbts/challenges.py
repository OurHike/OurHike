"""Sierra Buttes Trail Stewardship: challenges, nothing published (coverage audit 2026-10-01, batch
c6_regional_3).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "`/race-festivals`, `/mountain-epic` and the events (Downieville Classic, Lost and Found) are races.",
        "Skeptic: a re-grep of the 171 sitemap URLs and Yuba Expeditions' 26 for `challenge`, `passport`, "
        "`badge` and `bingo` found 0.",
    ),
    where=(
        "https://services6.arcgis.com/t5asxkRF7xoBwgqv/arcgis/rest/services",
        "https://sierratrails.org/",
    ),
)
