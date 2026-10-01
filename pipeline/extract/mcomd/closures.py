"""Mountain Club of Maryland: closures, published, and not landed (coverage audit 2026-10-01, batch
c2_at_clubs_mid).

This channel is ahead of our loaded ATC copy (finding 1). The posts carry dates and `modified`, so
an ETag/`modified` freshness marker would work here.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        '`https://www.mcomd.org/wp-json/wp/v2/posts` (JSON; category 216 "Club News & Announcements", 94 posts)'
        ' and `/feed/` (RSS). Search hits: "closed" 6, "closure" 3, "detour" 1. Among them: post 72468 (date '
        "2026-09-25, modified 2026-09-26), James Fry reopened 09/24/2026 plus the Harpers Ferry footbridge "
        'still closed; "Route MD-77 Detour Affecting Access to Catoctin Mountain Park" (2024-01-08); PVSP Grist'
        " Mill Trail closures (2022)",
    ),
    where=(
        "https://www.mcomd.org/wp-json/wp/v2/posts",
        "https://mcomd.org/",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
