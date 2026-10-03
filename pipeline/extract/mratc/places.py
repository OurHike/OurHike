"""Mount Rogers Appalachian Trail Club: places, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

Thin: one paragraph.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`/backpacking-rules` "PARKING": Damascus public long-term lots by the Library and Town Pool, '
        '"overnight parking up to 30 days". It links to `visitdamascus.org/parking/`.',
    ),
    where=("https://visitdamascus.org/parking/",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
