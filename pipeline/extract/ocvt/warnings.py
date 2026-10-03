"""Outdoor Club at Virginia Tech: warnings, published, and not landed (coverage audit 2026-10-01, batch
c3_at_clubs_south).

Dormant since 2022-01 and second-hand. Same low value as closures.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://ocvt.club/news/83` "Winter Weather Safety Hazards in George Washington and Jefferson National'
        ' Forests" (2022-01-07, relays a GWJ NF statement) and "Burn Bans In Effect" (2016-11-18). Page, HTML '
        "only.",
    ),
    where=("https://ocvt.club/news/83",),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
