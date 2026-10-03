"""Lewis & Clark Trail Heritage Foundation: challenges, published, and not landed (coverage audit
2026-10-01, batch c11_nht).

The Wellness Challenge does not fit #1780's places model. The passport stamps do

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Own: `https://lewisandclark.org/wellness-challenge/`, a members-only team mileage challenge (Sept 1 – "
        "June 30), not place-based. `NPSAPI/passportstamplocations` lecl 45",
    ),
    where=("https://lewisandclark.org/wellness-challenge/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
