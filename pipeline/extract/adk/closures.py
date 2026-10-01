"""Adirondack Mountain Club: closures, published, and not landed (coverage audit 2026-10-01, batch
c4_regional_1).

A page, updated frequently. Terms bar automated access. DEC is the land manager.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://adk.org/explore/high-peaks-conditions-report/`, dated "Wednesday, September 30". It lists '
        "closures: Lapland and Black Mountain Pond lean-tos closed, Fishbrook Pond North lean-to burned down, "
        "the Calamity Brook high-water bridge washed out, Avalanche Pass reopened. Also "
        "`https://nptrail.org/current-trail-conditions/` (Sucuri JS wall, not fetched).",
    ),
    where=(
        "https://adk.org/explore/high-peaks-conditions-report/",
        "https://nptrail.org/current-trail-conditions/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
