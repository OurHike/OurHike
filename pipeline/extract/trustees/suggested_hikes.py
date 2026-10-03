"""The Trustees of Reservations: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

A page.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=('`/program/the-trustee-hikers-top-ten/` and "Ideas for Your Visit" on place pages.',),
    where=("https://thetrustees.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
