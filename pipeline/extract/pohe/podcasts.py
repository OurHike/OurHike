"""Potomac Heritage Trail Association: podcasts, nothing published (coverage audit 2026-10-01, batch
c10_nst_rest).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "NPS `/multimedia/audio`: 0 for `pohe`. The association: none.",
        'Skeptic: kept. The first 50 of the 189 ArcGIS "Potomac Heritage" results hold no audio item. iTunes '
        '"Potomac Heritage" finds no association or NPS show. The NPS audio count could not be re-checked, '
        "because `DEMO_KEY` returned `OVER_RATE_LIMIT` both times it was tried.",
    ),
    where=("https://nps.gov/pohe/",),
)
