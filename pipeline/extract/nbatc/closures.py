"""Natural Bridge Appalachian Trail Club: closures, published, and not landed (coverage audit
2026-10-01, batch c2_at_clubs_mid).

Semi-structured (date + title + body). Neither the burn closure nor the Parkway closure is in
`atc_updates.json`. Skeptic: the same feed also carries club news (2025-02-14 "Awards
Presentation"), so items need classifying. Skeptic new find: a second channel …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        "Announcements endpoint "
        "`https://home.nbatc.org/cgi-bin/nbatcNews.cgi?ACTION=getPosts&OFFSET=0&TYPE=updates&ROLES=` (an HTML "
        "fragment, paged by OFFSET; called without parameters it returns 500). The 5 newest: 2025-09-03 Blue "
        'Ridge Parkway James River bridge, a year-long detour; 2025-04-28 prescribed burn, "The Appalachian '
        'National Scenic Trail and Old Hotel Trail #515 will be closed throughout the day"; 2024-10-01 Blue '
        "Ridge Parkway closed",
    ),
    where=(
        "https://home.nbatc.org/cgi-bin/nbatcNews.cgi?ACTION=getPosts&OFFSET=0&TYPE=updates&ROLES=",
        "https://home.nbatc.org/cgi-bin/getNotice.cgi",
        "https://nbatc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
