"""Overmountain Victory Trail Association: suggested hikes, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The annual March (`ovta.org/event-6682414`) is a re-enactment event

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=("`NPSAPI/thingstodo` ovvi 2",),
    where=("https://ovta.org/event-6682414",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
