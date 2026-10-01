"""Mount Rogers Appalachian Trail Club: warnings, published, and not landed (coverage audit 2026-10-01,
batch c3_at_clubs_south).

The RSS `description` is a truncated summary, so full text needs the post page. A naive keyword
filter matches "closure" inside `<enclosure>` on every item, as this audit found. ATC LOADED carries
Rhododendron Gap bears and the Mt Rogers fire restrictions.

Restated from reference/org_coverage.json, whose text is trimmed where it ends in '…'.
"""

from datetime import date

from extract._contract import NotAvailable

NOT_AVAILABLE = NotAvailable(
    confirmed=date(2026, 10, 1),
    checked=(
        'Weekly "MRATC Activities and Information" posts, RSS `https://www.mratc.org/blog-feed.xml` (20 items; '
        "newest 2026-09-27; weekly since 2025-12). For example, 2026-09-27 lists hunting seasons with dates "
        '("Deer archery: 10/3 to 11/13 … Rifle: 11/14 to 11/28") and points to `dwr.virginia.gov`. '
        "`/backpacking-rules`: camping prohibited on the A.T. in Grayson Highlands SP except inside Wise "
        "Shelter; group size limits (10 in Lewis Fork, Raccoon Branch and Little Wilson Creek Wilderness); bear"
        " food storage.",
    ),
    where=(
        "https://www.mratc.org/blog-feed.xml",
        "https://dwr.virginia.gov",
    ),
    reason="published and not landed: no sources.json row registers it, and a builder takes a registered key",
)
