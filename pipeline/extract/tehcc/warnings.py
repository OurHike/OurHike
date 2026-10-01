"""Tennessee Eastman Hiking & Canoeing Club: warnings, published, and not landed (coverage audit
2026-10-01, batch c3_at_clubs_south).

ATC LOADED carries the Roan five-year burn ban. The Iron Mountain bear notice is six years old.
(skeptic) The best live channel in the batch was missed:
`https://tehcc.org/trail-maintenance/recent-at-maintenance/` (WP page, public, also `GET
/wp-json/wp/v2/pages?slug=recent-at-maintenance`) is a …

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Post "Roan Mountain Fire Restrictions extended to 2030" (2025-09-12; title public, body gated). "Alert'
        ' – Storm Damage – North side of White Rocks" (2023-08-17). Wiki `Shelter:Iron Mountain` bear notice '
        '(2020-07-09). "Chimney Top" (private property, permission needed) and "Brumley Mountain Trail" '
        "(parking limited to 10 vehicles) announcements, both edited 2026-07-28.",
    ),
    where=(
        "https://tehcc.org/trail-maintenance/recent-at-maintenance/",
        "https://tehcc.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
