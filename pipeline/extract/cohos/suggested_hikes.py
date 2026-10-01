"""The Cohos Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page. Digital databooks are sold.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`/day-hike/` (Mt. Crawford, Owls Head, …) and `/through-hike/`.",),
    where=("https://cohostrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
