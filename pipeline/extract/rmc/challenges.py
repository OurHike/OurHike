"""Randolph Mountain Club: challenges, published, and not landed (coverage audit 2026-10-01, batch
c1_at_clubs_north).

A trail-completion programme, not a place list.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "RMC 100 Challenge: walk all 100 miles of RMC trails (since 2010). Page `/trails/rmc-100-challenge/`; "
        "logbook `/wp-content/uploads/RMC-100-Challenge-Logbook.pdf` (PDF, 163,662 bytes, 2023-02-16).",
    ),
    where=("https://randolphmountainclub.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
