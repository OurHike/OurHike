"""Tidewater Appalachian Trail Club: suggested hikes, nothing published (coverage audit 2026-10-01,
batch c2_at_clubs_mid).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("REST pages. `/tatc-schedule/` is dated events",),
    where=("https://tidewateratc.org/",),
)
