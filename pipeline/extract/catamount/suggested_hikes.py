"""Catamount Trail Association: suggested hikes, published, and not landed (coverage audit 2026-10-01,
batch c4_regional_1).

These are ski tours, not hikes.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "31 section pages under `/ski-the-trail/ct-section-list/`. Each has a length, a difficulty, a GeoPDF "
        'and a "Written Description & Shuttle Directions" PDF.',
    ),
    where=("https://catamounttrail.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
