"""Outdoor Club at Virginia Tech: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Dormant since 2022-01 and second-hand. Same low value as closures; re-read by decision 53's inventory
(2026-10-03), still nothing newer.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 3),
    checked=(
        '`https://ocvt.club/news/83` "Winter Weather Safety Hazards in George Washington and Jefferson National'
        ' Forests" (2022-01-07, relays a GWJ NF statement) and "Burn Bans In Effect" (2016-11-18). Page, HTML '
        "only.",
        "(decision 53 inventory, batch 1, 2026-10-03) the archive, re-read: no warning newer than /news/83 (2022-01-07).",
    ),
    where=("https://ocvt.club/news/83",),
    reason=(
        "published and dormant: the newest warning item is from 2022-01 and every one relays ATC's, RATC's or the "
        "national forest's notice, so there is nothing current to land; recheck the archive for a new item"
    ),
)
