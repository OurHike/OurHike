"""Sheltowee Trace Association: places, published, and not landed (coverage audit 2026-10-01, batch
c8_regional_5).

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/thru-hikers`: 5 Kentucky-designated trail towns ("Morehead, McKee, Livingston, London, and '
        'Stearns"). `/shuttle-services`. `/passes-and-permits` (DBNF, Big South Fork $5 backcountry permit, Red'
        " River Gorge overnight pass). Resupply PDF (`/s/2023_resupply_and_trail_angels.pdf`, 154,886 B).",
    ),
    where=("https://sheltoweetrace.org/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
